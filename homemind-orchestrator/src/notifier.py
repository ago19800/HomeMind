"""
notifier.py — Unified notification system.
Sends alerts via Telegram Bot API and/or HA notify service.
"""
import logging
import time
from datetime import datetime
import aiohttp

logger = logging.getLogger("homemind.notify")

TELEGRAM_API = "https://api.telegram.org"

# Rate-limiting: quante volte ogni "tipo" di notifica può essere inviata
ERROR_COOLDOWN   = 1800   # 30 min tra due notifiche dello stesso modulo/errore
ANOMALY_COOLDOWN = 3600   # 1 ora tra due notifiche della stessa anomalia
PATCH_COOLDOWN   = 300    # 5 min tra due notifiche patch


class Notifier:
    def __init__(self, rest_client, telegram_token: str = "", telegram_chat_id: str = "",
                 ha_notify_entity: str = ""):
        self.rest = rest_client
        self.tg_token = telegram_token.strip()
        self.tg_chat = telegram_chat_id.strip()
        # Strip virgolette letterali che jq può passare se il campo è vuoto
        self.ha_entity = ha_notify_entity.strip().strip('"').strip("'").strip()
        self._session: aiohttp.ClientSession | None = None
        # Rate-limit tracking: key → last_sent_timestamp
        self._last_sent: dict[str, float] = {}
        # Do Not Disturb: ore in cui bloccare le notifiche non critiche
        # Default: nessun DND (start=end=None)
        self._dnd_start: int | None = None   # ora inizio (es. 23)
        self._dnd_end:   int | None = None   # ora fine   (es. 7)

    async def start(self):
        self._session = aiohttp.ClientSession()
        if self.tg_token and self.tg_chat:
            logger.info(f"Telegram notifications enabled → chat {self.tg_chat}")
        if self.ha_entity:
            logger.info(f"HA notifications enabled → {self.ha_entity}")

    def set_quiet_hours(self, start: int | None, end: int | None):
        """Configura le ore di silenzio (Do Not Disturb).
        start=23, end=7 → blocca notifiche non critiche dalle 23:00 alle 07:00.
        start=None → DND disabilitato.
        """
        self._dnd_start = start
        self._dnd_end   = end
        if start is not None:
            logger.info("DND configurato: %02d:00 → %02d:00 (notifiche non critiche bloccate)",
                        start, end)

    def _is_quiet_time(self) -> bool:
        """Ritorna True se siamo nelle ore di silenzio.
        Non blocca MAI: allarmi, errori, anomalie (quelli usano send/send_error/send_anomaly).
        Blocca solo: send_html() = notifiche di servizio (lavatrice, solare, spazzatura, ecc.)
        """
        if self._dnd_start is None or self._dnd_end is None:
            return False
        h = datetime.now().hour
        s, e = self._dnd_start, self._dnd_end
        if s < e:
            # Intervallo semplice: es. 1:00 → 6:00
            return s <= h < e
        else:
            # Intervallo a cavallo della mezzanotte: es. 23:00 → 7:00
            return h >= s or h < e

    async def stop(self):
        if self._session:
            await self._session.close()

    # ── Rate-limit helper ─────────────────────────────────────────────────────

    def _throttle(self, key: str, cooldown: float) -> bool:
        """Ritorna True se il messaggio PUÒ essere inviato, False se in cooldown."""
        now = time.time()
        last = self._last_sent.get(key, 0.0)
        if now - last < cooldown:
            remaining = int((cooldown - (now - last)) / 60)
            logger.debug("Notifica '%s' soppressa (cooldown %d min rimanenti)", key, remaining)
            return False
        self._last_sent[key] = now
        return True

    # ── Public API ─────────────────────────────────────────────────────────────

    async def send(self, title: str, message: str):
        """Simple text notification — nessun rate-limit (eventi importanti)."""
        await self._telegram(f"*{self._esc(title)}*\n{self._esc(message)}")
        await self._ha_notify(title, message)

    async def send_html(self, message: str, force: bool = False):
        """Notifica con formattazione HTML.
        Rispetta le ore di silenzio (DND) a meno che force=True.
        Le notifiche critiche (allarmi, errori) usano send() o send_error() — non questo metodo.
        """
        if not force and self._is_quiet_time():
            logger.debug("DND: notifica soppressa (ora silenziosa): %s", message[:60])
            return
        await self._telegram(message, parse_mode="HTML")

    async def send_html_to(self, chat_id: str, message: str):
        """Invia HTML a un chat_id specifico (per multi-utente)."""
        if not self.tg_token or not chat_id:
            return
        url = f"{TELEGRAM_API}/bot{self.tg_token}/sendMessage"
        payload = {
            "chat_id": str(chat_id).strip(),
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            async with self._session.post(url, json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    logger.warning("send_html_to %s failed: %s", chat_id, r.status)
        except Exception as e:
            logger.warning("send_html_to error: %s", e)

    async def send_anomaly(self, anomaly: dict):
        """Rich anomaly notification — rate-limit 1h per entità."""
        eid      = anomaly.get("entity_id", "?")
        reason   = anomaly.get("reason", "")
        severity = anomaly.get("severity", "low").upper()
        patch    = anomaly.get("patch_yaml", "")

        # Rate-limit: una notifica per entità ogni ora
        key = f"anomaly:{eid}:{severity}"
        if not self._throttle(key, ANOMALY_COOLDOWN):
            return

        sev_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚠️")

        tg_text = (
            f"{sev_icon} *HomeMind — Anomalia {severity}*\n\n"
            f"📍 Entità: `{self._esc(eid)}`\n"
            f"❗ Problema: {self._esc(reason)}\n"
        )
        if patch:
            patch_preview = patch[:600] + ("..." if len(patch) > 600 else "")
            tg_text += f"\n📋 *Patch proposta \\(formato moderno HA 2024\\+\\):*\n```yaml\n{patch_preview}\n```"
        tg_text += "\n\n💡 Apri HomeMind per applicare la patch automaticamente\\."

        await self._telegram(tg_text, parse_mode="MarkdownV2")
        await self._ha_notify(
            f"HomeMind: Anomalia {severity}",
            f"{eid}: {reason}"
        )

    async def send_patch_applied(self, entity_id: str, patch_file: str):
        """Notification quando una patch viene applicata — rate-limit 5 min."""
        key = f"patch:{entity_id}"
        if not self._throttle(key, PATCH_COOLDOWN):
            return

        tg_text = (
            f"✅ *HomeMind — Patch Applicata*\n\n"
            f"📍 Entità: `{self._esc(entity_id)}`\n"
            f"💾 File: `{self._esc(patch_file)}`\n\n"
            f"🔄 I template di HA sono stati ricaricati\\."
        )
        await self._telegram(tg_text, parse_mode="MarkdownV2")
        await self._ha_notify("HomeMind: Patch applicata", f"Fix applicato per {entity_id}")

    async def send_error(self, module: str, message: str):
        """Errore da log — rate-limit 30 min per modulo."""
        # Chiave basata su modulo+inizio messaggio (stessi errori ripetuti → soppressi)
        msg_key = message[:60].strip()
        key = f"error:{module}:{msg_key}"
        if not self._throttle(key, ERROR_COOLDOWN):
            return

        tg_text = (
            f"🔴 *HomeMind — Errore rilevato*\n\n"
            f"📦 Modulo: `{self._esc(module)}`\n"
            f"❗ {self._esc(message[:300])}"
        )
        await self._telegram(tg_text, parse_mode="MarkdownV2")
        await self._ha_notify(f"HomeMind: Errore in {module}", message[:200])

    # ── Internal ────────────────────────────────────────────────────────────────

    async def _telegram(self, text: str, parse_mode: str = "MarkdownV2"):
        if not self.tg_token or not self.tg_chat:
            return
        url = f"{TELEGRAM_API}/bot{self.tg_token}/sendMessage"
        payload = {
            "chat_id": self.tg_chat,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            async with self._session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    logger.debug("Telegram message sent OK")
                else:
                    body = await r.text()
                    if r.status == 400 and "chat not found" in body:
                        logger.warning(
                            "Telegram 400 chat not found: "
                            "il bot e nuovo e non hai ancora scritto /start. "
                            "Apri Telegram, cerca @MioHomeMind_bot (o il nome del tuo bot) "
                            "e invia /start — poi riavvia l addon."
                        )
                    else:
                        logger.warning(f"Telegram error {r.status}: {body[:200]}")
        except Exception as e:
            logger.warning(f"Telegram send failed: {e}")

    async def _ha_notify(self, title: str, message: str):
        # Strip e controlla — evita chiamate con entity vuoto o solo spazi/virgolette
        entity = self.ha_entity.strip().strip('"').strip("'").strip()
        if not entity or entity in ('""', "''") or not self.rest:
            return
        service = entity.removeprefix("notify.")
        try:
            await self.rest.call_service("notify", service,
                                         {"title": title, "message": message})
            logger.debug("HA notify OK: %s", service)
        except Exception as e:
            logger.warning("HA notify failed (%s): %s", service, e)

    @staticmethod
    def _esc(text: str) -> str:
        """Escape special chars for Telegram MarkdownV2."""
        special = r"_*[]()~`>#+-=|{}.!\\"
        return "".join(f"\\{c}" if c in special else c for c in str(text))
