"""
agent/power_guard.py — Power Guard: protezione automatica soglia Enel.

Monitora il consumo istantaneo e agisce quando si avvicina alla soglia
contrattuale, spegnendo gli elettrodomestici meno prioritari.

Configurazione in person_config.json:

  "power_guard": {
    "enabled": true,
    "sensor": "sensor.consumo_casa_w",
    "threshold_w": 3000,
    "warning_pct": 90,
    "mode": "ask",
    "appliances": [
      {"name": "Lavatrice",    "switch": "switch.presa_lavatrice",  "priority": 1},
      {"name": "Lavastoviglie","switch": "switch.presa_lavastoviglie","priority": 2},
      {"name": "Scaldabagno",  "switch": "switch.scaldabagno",      "priority": 3}
    ]
  }

mode:
  "warn_only" — solo notifica, non spegne nulla
  "ask"       — chiede conferma prima di spegnere
  "auto"      — spegne automaticamente senza chiedere

Comandi Telegram:
  /powerguard  — stato attuale + elettrodomestici monitorati
  /pg          — alias breve
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional

from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.powerguard")

CONFIG_FILE    = Path("/config/homemind_patches/person_config.json")
CHECK_INTERVAL = 30    # secondi tra un check e l'altro
COOLDOWN_SEC   = 120   # secondi minimi tra due azioni sullo stesso switch
RECOVERY_PCT   = 75    # % soglia sotto cui si considera "tornato in sicurezza"


class PowerGuard:
    def __init__(self, notifier=None, rest_client=None,
                 state_cache_cb=None, lang_cb=None):
        self.notifier     = notifier
        self.rest         = rest_client
        self._cache_cb    = state_cache_cb
        self._lang_cb     = lang_cb

        self._cfg         = {}
        self._enabled     = False
        self._sensor      = ""
        self._threshold_w = 0.0
        self._warning_w   = 0.0
        self._recovery_w  = 0.0
        self._mode        = "ask"
        self._appliances  = []

        self._pending_off: Optional[dict] = None
        self._pending_ts    = 0.0
        self._last_action: dict = {}
        self._notified_high = False
        self._notified_ok   = False
        self._overload_since: float = 0.0  # quando è iniziato il superamento
        self._delay_minutes: int = 0
        self._task: Optional[asyncio.Task] = None

        self._load_config()

    # ─────────────────────────────────────────────────────────────────────────
    # Config

    def _load_config(self):
        try:
            if not CONFIG_FILE.exists():
                return
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
            pg  = cfg.get("power_guard", {})
            if not pg or not pg.get("enabled", False):
                self._enabled = False
                return
            self._enabled     = True
            # Supporta sia "sensor" che "power_sensor"
            self._sensor      = pg.get("sensor") or pg.get("power_sensor", "")
            self._threshold_w = float(pg.get("threshold_w", 3000))
            warn_pct          = float(pg.get("warning_pct", 90)) / 100
            self._warning_w   = self._threshold_w * warn_pct
            self._recovery_w  = self._threshold_w * (RECOVERY_PCT / 100)
            self._mode           = pg.get("mode", "ask")
            self._delay_minutes  = int(pg.get("delay_minutes", 0))  # minuti di attesa prima di notificare
            # Supporta sia "appliances" che "appliances_priority"
            raw_apps = pg.get("appliances") or pg.get("appliances_priority", [])
            # Normalizza: se oggetto semplice {name, switch} aggiungi priority
            normalized = []
            for i, a in enumerate(raw_apps):
                if isinstance(a, dict):
                    if "priority" not in a:
                        a = dict(a, priority=i+1)
                    normalized.append(a)
            self._appliances = sorted(normalized, key=lambda x: x.get("priority", 99))
            logger.info(
                "PowerGuard caricato: soglia=%.0fW warning=%.0fW mode=%s app=%d",
                self._threshold_w, self._warning_w, self._mode, len(self._appliances)
            )
        except Exception as e:
            logger.warning("PowerGuard config error: %s", e)
            self._enabled = False

    # ─────────────────────────────────────────────────────────────────────────
    # Avvio

    async def start(self):
        if not self._enabled:
            logger.info("PowerGuard: disabilitato — configura power_guard nel person_config.json")
            return
        self._task = asyncio.create_task(self._main_loop(), name="power_guard")
        logger.info("PowerGuard avviato — monitoraggio ogni %ds", CHECK_INTERVAL)

    async def reload(self):
        self._load_config()

    # ─────────────────────────────────────────────────────────────────────────
    # Loop

    async def _main_loop(self):
        await asyncio.sleep(15)
        while True:
            try:
                self._load_config()
                if self._enabled:
                    await self._check()
            except Exception as e:
                logger.warning("PowerGuard loop error: %s", e)
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check(self):
        if not self._sensor or not self._cache_cb:
            return
        cache = self._cache_cb()
        state = cache.get(self._sensor, {})
        raw   = state.get("state", "")
        if not raw or raw in ("unavailable", "unknown"):
            logger.warning("PowerGuard: sensore %s non disponibile (state=%r)", self._sensor, raw)
            return
        try:
            current_w = float(raw)
        except (ValueError, TypeError):
            logger.warning("PowerGuard: valore non numerico da %s: %r", self._sensor, raw)
            return
        unit = state.get("attributes", {}).get("unit_of_measurement", "W")
        if unit in ("kW", "kw"):
            current_w *= 1000

        pct = (current_w / self._threshold_w * 100) if self._threshold_w else 0

        if current_w >= self._warning_w:
            if self._overload_since == 0.0:
                self._overload_since = time.time()
                logger.info("PowerGuard OVERLOAD iniziato: %.1fW / %.0fW | delay=%dmin — attendo...",
                            current_w, self._threshold_w, self._delay_minutes)
            elapsed_min = (time.time() - self._overload_since) / 60
            remaining   = max(0.0, self._delay_minutes - elapsed_min)
            if not self._notified_high and elapsed_min >= self._delay_minutes:
                logger.info("PowerGuard: delay trascorso (%.1f min) — invio notifica", elapsed_min)
                self._notified_high = True
                self._notified_ok   = False
                await self._handle_overload(current_w, pct)
            else:
                logger.info("PowerGuard check: %.1fW (%.0f%%) | overload da %.1fmin | restano %.1fmin | notified=%s",
                            current_w, pct, elapsed_min, remaining, self._notified_high)
        else:
            if self._overload_since != 0.0:
                logger.info("PowerGuard: consumo tornato normale (%.1fW) — reset timer", current_w)
                self._overload_since = 0.0
            if self._notified_high and not self._notified_ok and current_w < self._recovery_w:
                self._notified_ok   = True
                self._notified_high = False
                await self._handle_recovery(current_w, pct)

    # ─────────────────────────────────────────────────────────────────────────
    # Overload

    async def _handle_overload(self, current_w: float, pct: float):
        logger.info("PowerGuard: *** NOTIFICA IN INVIO *** %.1fW / %.0fW (%.0f%%) mode=%s",
                    current_w, self._threshold_w, pct, self._mode)
        lang   = self._lang_cb() if self._lang_cb else "it"
        target = self._find_target()
        logger.info("PowerGuard: target=%s notifier=%s", target, self.notifier is not None)

        if self._mode == "warn_only" or not target:
            if lang == "en":
                msg = (
                    f"⚡ <b>Power Guard Warning!</b>\n"
                    f"Consumption: <b>{current_w:.0f}W</b> ({pct:.0f}% of {self._threshold_w:.0f}W)\n"
                    + (f"ℹ️ Mode: notify only." if target else
                       "⚠️ No controllable appliances currently on.")
                )
            else:
                msg = (
                    f"⚡ <b>Power Guard — Attenzione!</b>\n"
                    f"Consumo: <b>{current_w:.0f}W</b> ({pct:.0f}% del limite {self._threshold_w:.0f}W)\n"
                    + (f"ℹ️ Modalità: solo notifica — non spengo nulla." if target else
                       "⚠️ Nessun elettrodomestico controllabile attivo.")
                )
            if self.notifier:
                try:
                    await self.notifier.send_html(msg)
                    logger.info("PowerGuard: notifica warn_only inviata ✅")
                except Exception as e_send:
                    logger.error("PowerGuard: ERRORE invio notifica: %s", e_send)
            else:
                logger.error("PowerGuard: notifier=None — impossibile inviare!")
            return

        if self._mode == "ask":
            self._pending_off = target
            self._pending_ts  = time.time()
            if lang == "en":
                msg = (
                    f"⚡ <b>Power Guard Alert!</b>\n"
                    f"Consumption: <b>{current_w:.0f}W</b> ({pct:.0f}% of {self._threshold_w:.0f}W)\n\n"
                    f"To avoid a power cut, I suggest turning off:\n"
                    f"🔌 <b>{target['name']}</b>\n\n"
                    f"Reply <b>yes</b> to turn it off or <b>no</b> to skip."
                )
            else:
                msg = (
                    f"⚡ <b>Power Guard — Soglia raggiunta!</b>\n"
                    f"Consumo: <b>{current_w:.0f}W</b> ({pct:.0f}% del limite {self._threshold_w:.0f}W)\n\n"
                    f"Per evitare il distacco Enel, suggerisco di spegnere:\n"
                    f"🔌 <b>{target['name']}</b>\n\n"
                    f"Rispondi <b>sì</b> per spegnerlo o <b>no</b> per ignorare."
                )
            if self.notifier:
                try:
                    await self.notifier.send_html(msg)
                    logger.info("PowerGuard: notifica ask inviata ✅")
                except Exception as e_send:
                    logger.error("PowerGuard: ERRORE invio notifica ask: %s", e_send)
            else:
                logger.error("PowerGuard: notifier=None — impossibile inviare!")

        elif self._mode == "auto":
            await self._turn_off(target)
            if lang == "en":
                msg = (
                    f"⚡ <b>Power Guard — Auto action!</b>\n"
                    f"Consumption: <b>{current_w:.0f}W</b> ({pct:.0f}% of {self._threshold_w:.0f}W)\n\n"
                    f"✅ Turned off automatically: <b>{target['name']}</b>\n"
                    f"You'll be notified when consumption drops."
                )
            else:
                msg = (
                    f"⚡ <b>Power Guard — Azione automatica!</b>\n"
                    f"Consumo: <b>{current_w:.0f}W</b> ({pct:.0f}% del limite {self._threshold_w:.0f}W)\n\n"
                    f"✅ Spento automaticamente: <b>{target['name']}</b>\n"
                    f"Ti avviso quando il consumo scende."
                )
            if self.notifier:
                await self.notifier.send_html(msg)

    # ─────────────────────────────────────────────────────────────────────────
    # Recovery

    async def _handle_recovery(self, current_w: float, pct: float):
        lang = self._lang_cb() if self._lang_cb else "it"
        if lang == "en":
            msg = (
                f"✅ <b>Power Guard — Safe again!</b>\n"
                f"Consumption back to <b>{current_w:.0f}W</b> ({pct:.0f}% of limit)\n\n"
                f"💡 You can turn your appliances back on if needed."
            )
        else:
            msg = (
                f"✅ <b>Power Guard — Consumo rientrato!</b>\n"
                f"Consumo sceso a <b>{current_w:.0f}W</b> ({pct:.0f}% del limite)\n\n"
                f"💡 Puoi riaccendere gli elettrodomestici se vuoi."
            )
        if self.notifier:
            await self.notifier.send_html(msg)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers

    def _find_target(self) -> Optional[dict]:
        if not self._cache_cb:
            return None
        cache  = self._cache_cb()
        now_ts = time.time()
        for app in self._appliances:
            sw = app.get("switch", "")
            if not sw:
                continue
            st = cache.get(sw, {}).get("state", "off")
            if st != "on":
                continue
            if now_ts - self._last_action.get(sw, 0) < COOLDOWN_SEC:
                continue
            return app
        return None

    async def _turn_off(self, app: dict):
        sw = app.get("switch", "")
        if not sw or not self.rest:
            return
        try:
            await self.rest.call_service(
                "switch", "turn_off", {},
                target={"entity_id": sw}
            )
            self._last_action[sw] = time.time()
            logger.info("PowerGuard: spento %s (%s)", app.get("name"), sw)
        except Exception as e:
            logger.error("PowerGuard: errore spegnendo %s: %s", sw, e)

    # ─────────────────────────────────────────────────────────────────────────
    # Conferme Telegram

    async def handle_confirm(self, text: str) -> bool:
        if not self._pending_off:
            return False
        if time.time() - self._pending_ts > 300:
            self._pending_off = None
            return False
        text_low = text.lower().strip()
        is_yes = text_low in ("sì", "si", "yes", "ok", "spegni", "vai", "conferma")
        is_no  = text_low in ("no", "non ora", "ignora", "skip", "annulla")
        if not (is_yes or is_no):
            return False
        target = self._pending_off
        self._pending_off = None
        lang = self._lang_cb() if self._lang_cb else "it"
        if is_no:
            msg = "👍 Ok, non spegno nulla." if lang == "it" else "👍 Ok, not turning off anything."
            if self.notifier:
                await self.notifier.send_html(msg)
            return True
        await self._turn_off(target)
        msg = (f"✅ Spento: <b>{target['name']}</b>" if lang == "it"
               else f"✅ Turned off: <b>{target['name']}</b>")
        if self.notifier:
            await self.notifier.send_html(msg)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Display per /powerguard

    def get_status(self) -> str:
        lang = self._lang_cb() if self._lang_cb else "it"
        if not self._enabled:
            if lang == "en":
                return (
                    "⚡ <b>Power Guard</b> — Disabled\n\n"
                    "<i>To enable, add power_guard section in person_config.json</i>\n\n"
                    "<b>Example:</b>\n"
                    '<pre>"power_guard": {\n'
                    '  "enabled": true,\n'
                    '  "sensor": "sensor.power_watts",\n'
                    '  "threshold_w": 3000,\n'
                    '  "warning_pct": 90,\n'
                    '  "mode": "ask",\n'
                    '  "appliances": [\n'
                    '    {"name":"Washer","switch":"switch.washer","priority":1}\n'
                    '  ]\n'
                    '}</pre>'
                )
            return (
                "⚡ <b>Power Guard</b> — Disabilitato\n\n"
                "<i>Per abilitare, aggiungi la sezione power_guard nel person_config.json</i>\n\n"
                "<b>Esempio:</b>\n"
                '<pre>"power_guard": {\n'
                '  "enabled": true,\n'
                '  "sensor": "sensor.consumo_casa_w",\n'
                '  "threshold_w": 3000,\n'
                '  "warning_pct": 90,\n'
                '  "mode": "ask",\n'
                '  "appliances": [\n'
                '    {"name":"Lavatrice","switch":"switch.presa_lavatrice","priority":1}\n'
                '  ]\n'
                '}</pre>'
            )

        current_w = None
        pct       = 0.0
        if self._sensor and self._cache_cb:
            cache = self._cache_cb()
            raw   = cache.get(self._sensor, {}).get("state", "")
            try:
                current_w = float(raw)
                unit = cache.get(self._sensor, {}).get(
                    "attributes", {}).get("unit_of_measurement", "W")
                if unit in ("kW", "kw"):
                    current_w *= 1000
                pct = current_w / self._threshold_w * 100
            except (ValueError, TypeError):
                pass

        mode_map = {
            "warn_only": ("⚠️ Solo notifica",   "⚠️ Notify only"),
            "ask":       ("💬 Chiede conferma",  "💬 Ask confirm"),
            "auto":      ("🤖 Automatico",       "🤖 Automatic"),
        }
        m_it, m_en = mode_map.get(self._mode, (self._mode, self._mode))

        if lang == "en":
            lines = [
                "⚡ <b>Power Guard</b> — Active",
                f"📊 Threshold: <b>{self._threshold_w:.0f}W</b>",
                f"⚠️ Warning at: <b>{self._warning_w:.0f}W</b> "
                f"({int(self._warning_w/self._threshold_w*100)}%)",
                f"⚙️ Mode: {m_en}",
            ]
        else:
            lines = [
                "⚡ <b>Power Guard</b> — Attivo",
                f"📊 Soglia: <b>{self._threshold_w:.0f}W</b>",
                f"⚠️ Avviso a: <b>{self._warning_w:.0f}W</b> "
                f"({int(self._warning_w/self._threshold_w*100)}%)",
                f"⚙️ Modalità: {m_it}",
            ]

        if current_w is not None:
            bar = self._power_bar(pct)
            label = "Current" if lang == "en" else "Consumo attuale"
            lines.append(
                f"\n🔌 {label}: <b>{current_w:.0f}W</b> ({pct:.0f}%)\n{bar}"
            )

        title = "\n📋 <b>Monitored appliances (priority order):</b>" if lang == "en" \
                else "\n📋 <b>Elettrodomestici monitorati (priorità):</b>"
        lines.append(title)

        cache = self._cache_cb() if self._cache_cb else {}
        for i, app in enumerate(self._appliances, 1):
            sw   = app.get("switch", "")
            st   = cache.get(sw, {}).get("state", "?")
            icon = "🟢" if st == "on" else ("⚫" if st == "off" else "❓")
            prio_note = f" (priority {app.get('priority',i)})" if lang == "en" \
                        else f" (priorità {app.get('priority',i)})"
            lines.append(f"  {i}. {icon} <b>{app['name']}</b>{prio_note} — {st}")

        if lang == "en":
            lines.append(
                "\n<i>First in list = first to turn off when threshold is reached</i>"
            )
        else:
            lines.append(
                "\n<i>Il primo della lista è il primo ad essere spento al superamento della soglia</i>"
            )
        return "\n".join(lines)

    def _power_bar(self, pct: float) -> str:
        filled = min(20, int(pct / 5))
        empty  = 20 - filled
        if pct >= 90:
            color = "🟥"
        elif pct >= 75:
            color = "🟧"
        else:
            color = "🟩"
        return color + "█" * filled + "░" * empty + f" {pct:.0f}%"
