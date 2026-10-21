"""
agent/frigate_alerts.py — Avvisi istantanei Frigate per tipo di oggetto.

Quando Frigate rileva un oggetto (persona, cane, auto, ...) per cui lo switch
è attivo nella pagina web (tab 📹 Frigate), manda subito la foto su Telegram.

Funzionamento (indipendente da antifurto e snapshot su allarme):
  • ogni POLL_SECONDS interroga GET /api/events di Frigate
  • gli eventi già esistenti all'avvio (o a switch appena attivati) vengono
    solo "memorizzati": nessun avviso per eventi vecchi
  • per ogni NUOVO evento con etichetta abilitata scarica lo snapshot e lo
    invia a tutte le chat Telegram autorizzate
  • cooldown per (etichetta, camera) per evitare raffiche di foto

Configurazione (person_config.json → sezione "frigate"), scritta dalla pagina web:
  "alerts": {
      "labels": {"person": true, "dog": true, "car": false},
      "cooldown_s": 60,
      "min_score_pct": 80          (0 = nessun filtro)
  }
Il file viene riletto ad ogni ciclo (se cambia): gli switch valgono subito,
senza riavvio. Se "alerts" manca o tutti gli switch sono spenti, il modulo
resta inattivo e non fa nessuna richiesta a Frigate.
"""

import asyncio
import json
import logging
import time
from pathlib import Path

from agent.frigate_client import FrigateClient

logger = logging.getLogger("homemind.frigate_alerts")

CONFIG_PATH        = Path("/config/homemind_patches/person_config.json")
POLL_SECONDS       = 4      # frequenza controllo eventi
DOWN_POLL_SECONDS  = 15     # frequenza quando Frigate non risponde
OVERLAP_S          = 60     # finestra di sovrapposizione sulle query (dedup via event_id)
PRIME_WINDOW_S     = 600    # al primo giro: eventi degli ultimi 10 min solo memorizzati
SNAPSHOT_RETRY_S   = 45     # per quanto riprovare se lo snapshot non è ancora pronto
DEFAULT_COOLDOWN_S = 60
SEEN_TTL_S         = 3600   # per quanto ricordare gli event_id già visti
CONFIRM_TIMEOUT_S  = 60     # con confidenza minima: quanto attendere che lo score salga
BUILD              = "1.11.15"   # marcatore versione (visibile nel log all'avvio)

# etichetta Frigate → (emoji, nome)
_LABELS = {
    "person":     ("👤", "Persona"),
    "dog":        ("🐕", "Cane"),
    "cat":        ("🐈", "Gatto"),
    "car":        ("🚗", "Auto"),
    "motorcycle": ("🏍️", "Moto"),
    "bicycle":    ("🚲", "Bici"),
    "package":    ("📦", "Pacco"),
    "bird":       ("🐦", "Uccello"),
}


def _meta(label: str) -> tuple[str, str]:
    return _LABELS.get(label, ("🔹", label.capitalize() if label else "Oggetto"))


class FrigateAlertWatcher:
    """Controlla Frigate e manda su Telegram la foto degli oggetti abilitati."""

    def __init__(self, tg_bot, config_path: Path = CONFIG_PATH):
        self._tg = tg_bot
        self._path = Path(config_path)

        self._cfg: dict = {}              # sezione "frigate" di person_config.json
        self._cfg_mtime = None

        self._client: FrigateClient | None = None
        self._client_sig = None

        self._seen: dict[str, tuple] = {}      # event_id → (quando l'ho visto, start_time Frigate)
        self._pending: dict[str, dict] = {}    # eventi in attesa dello snapshot
        self._last_sent: dict[tuple, float] = {}   # (label, camera) → ultimo avviso
        self._cursor: float | None = None      # max start_time visto (orologio Frigate)
        self._primed = False
        self._down = False

    # ── Configurazione ─────────────────────────────────────────────────────

    def _load_cfg(self) -> dict:
        """Rilegge person_config.json solo se è cambiato (mtime)."""
        try:
            mtime = self._path.stat().st_mtime
        except OSError:
            return self._cfg
        if mtime != self._cfg_mtime:
            self._cfg_mtime = mtime
            try:
                data = json.loads(self._path.read_text(encoding="utf-8-sig"))
                fg = data.get("frigate")
                self._cfg = fg if isinstance(fg, dict) else {}
            except Exception as e:
                logger.warning("FrigateAlerts: lettura config fallita: %s", e)
        return self._cfg

    def _settings(self):
        """(labels_abilitate, cooldown_s, min_score 0-1, frigate_cfg) oppure None se inattivo."""
        fg = self._load_cfg()
        if not fg.get("enabled", False) or not str(fg.get("host", "")).strip():
            return None
        alerts = fg.get("alerts")
        if not isinstance(alerts, dict):
            return None
        raw = alerts.get("labels")
        labels = {str(k) for k, v in (raw.items() if isinstance(raw, dict) else []) if v is True}
        if not labels:
            return None
        try:
            cooldown = int(alerts.get("cooldown_s", DEFAULT_COOLDOWN_S))
        except (TypeError, ValueError):
            cooldown = DEFAULT_COOLDOWN_S
        cooldown = max(0, min(cooldown, 3600))
        try:
            min_score = max(0, min(int(alerts.get("min_score_pct", 0)), 100)) / 100.0
        except (TypeError, ValueError):
            min_score = 0.0
        return labels, cooldown, min_score, fg

    def _get_client(self, fg: dict) -> FrigateClient | None:
        sig = (str(fg.get("host", "")).strip(), int(fg.get("port", 5000) or 5000))
        if self._client is None or sig != self._client_sig:
            self._client = FrigateClient({**fg, "enabled": True})
            self._client_sig = sig
            self._reset()   # host cambiato: ricomincia da capo senza avvisi vecchi
        return self._client if self._client.is_ready() else None

    def _reset(self):
        self._seen.clear()
        self._pending.clear()
        self._cursor = None
        self._primed = False

    # ── Loop principale ────────────────────────────────────────────────────

    async def run(self):
        logger.info("FrigateAlertWatcher avviato — build %s (switch letti da person_config.json)", BUILD)
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # il watcher non deve MAI fermarsi o rompere altro
                logger.warning("FrigateAlerts tick errore: %s", e)
            await asyncio.sleep(DOWN_POLL_SECONDS if self._down else POLL_SECONDS)

    async def _tick(self):
        st = self._settings()
        if not st:
            # Nessuno switch attivo: inattivo. Reset così, riattivando uno switch,
            # non partono avvisi per eventi precedenti.
            if self._primed or self._seen or self._pending:
                self._reset()
            return
        labels, cooldown, min_score, fg = st
        client = self._get_client(fg)
        if not client:
            return

        now = time.time()
        after = (self._cursor - OVERLAP_S) if self._cursor else now - PRIME_WINDOW_S
        dets = await client.get_recent_detections(labels=None, after_ts=after, limit=200)

        if dets is None:
            if not self._down:
                logger.warning("FrigateAlerts: Frigate non raggiungibile — riprovo tra %ds",
                               DOWN_POLL_SECONDS)
            self._down = True
            return
        if self._down:
            logger.info("FrigateAlerts: Frigate di nuovo raggiungibile")
        self._down = False

        # Primo giro: memorizza gli eventi esistenti, nessun avviso
        if not self._primed:
            for d in dets:
                if d["event_id"]:
                    self._seen[d["event_id"]] = (now, d["time"])
                if d["time"] > 0:
                    self._cursor = max(self._cursor or 0.0, d["time"])
            self._primed = True
            logger.info("FrigateAlerts: attivo — switch: %s, cooldown %ds, confidenza minima %d%% (%d eventi esistenti ignorati)",
                        ", ".join(sorted(labels)), cooldown, int(round(min_score * 100)), len(dets))
            return

        # Nuovi eventi (dal più vecchio al più recente)
        new = [d for d in dets if d["event_id"] and d["event_id"] not in self._seen]
        for d in sorted(new, key=lambda x: x["time"]):
            self._seen[d["event_id"]] = (now, d["time"])
            if d["time"] > 0:
                self._cursor = max(self._cursor or 0.0, d["time"])
            if d["label"] not in labels:
                continue
            key = (d["label"], d["camera"])
            if cooldown > 0 and now - self._last_sent.get(key, 0.0) < cooldown:
                logger.debug("FrigateAlerts: cooldown %s/%s — skip", *key)
                continue
            prev = self._last_sent.get(key)
            self._last_sent[key] = now
            self._pending[d["event_id"]] = {"det": d, "first": now, "key": key, "prev": prev}

        # Invia (o riprova) gli eventi in attesa dello snapshot
        for eid in list(self._pending):
            info = self._pending[eid]

            # Confidenza minima: attende che lo score salga (al primo avvistamento è il più basso)
            if min_score > 0:
                ev = await client.get_event(eid)
                ended = False
                if ev:
                    data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
                    sc = data.get("top_score", ev.get("top_score"))
                    try:
                        if sc is not None:
                            info["det"]["score"] = float(sc)
                    except (TypeError, ValueError):
                        pass
                    ended = ev.get("end_time") is not None
                cur = info["det"].get("score")
                if cur is None or cur < min_score:
                    if ended or time.time() - info["first"] >= CONFIRM_TIMEOUT_S:
                        logger.info("FrigateAlerts: %s/%s scartato (confidenza %s < %d%%)",
                                    info["det"]["label"], info["det"]["camera"],
                                    f"{int(round(cur * 100))}%" if cur is not None else "?",
                                    int(round(min_score * 100)))
                        # rilascia il cooldown: un evento successivo valido potrà avvisare
                        if info.get("prev") is None:
                            self._last_sent.pop(info["key"], None)
                        else:
                            self._last_sent[info["key"]] = info["prev"]
                        self._pending.pop(eid, None)
                    continue   # altrimenti riprova al prossimo giro

            img = await client.get_event_snapshot(eid)
            waited = time.time() - info["first"]
            if img:
                await self._deliver(info["det"], img)
                self._pending.pop(eid, None)
            elif waited >= SNAPSHOT_RETRY_S:
                logger.warning("FrigateAlerts: snapshot non disponibile per %s — avviso senza foto", eid)
                await self._deliver(info["det"], None)
                self._pending.pop(eid, None)

        # Pulizia memoria — SOLO degli eventi che Frigate non può più restituire.
        # La query chiede gli eventi con start_time >= (cursore - OVERLAP): finché un evento
        # sta in quella finestra va ricordato, altrimenti verrebbe rinotificato come "nuovo"
        # (succedeva dopo 1 ora se nel frattempo non arrivavano altri eventi).
        if self._cursor:
            horizon = self._cursor - OVERLAP_S - 600
            cutoff = now - SEEN_TTL_S
            for k, (seen_at, start) in list(self._seen.items()):
                if seen_at < cutoff and start < horizon:
                    self._seen.pop(k, None)
        if len(self._seen) > 5000:   # tetto di sicurezza sulla memoria
            for k, _ in sorted(self._seen.items(), key=lambda kv: kv[1][0])[:len(self._seen) - 5000]:
                self._seen.pop(k, None)

    # ── Invio Telegram ─────────────────────────────────────────────────────

    async def _deliver(self, det: dict, img: bytes | None):
        try:
            from utils.timezone_helper import now_local
            hhmmss = now_local().strftime("%H:%M:%S")
        except Exception:
            hhmmss = time.strftime("%H:%M:%S")
        emoji, name = _meta(det["label"])
        extra = f" · {det['name']}" if det.get("name") else ""
        conf = f" · ~{int(round(det['score'] * 100))}%" if det.get("score") is not None else ""
        caption = f"{emoji} {name}{extra} — {det['camera']} · {hhmmss}{conf}"
        for cid in list(getattr(self._tg, "allowed", []) or []):
            try:
                if img:
                    await self._tg.send_photo(cid, img, caption)
                else:
                    await self._tg._send(cid, f"{caption}\n<i>(foto non disponibile)</i>")
            except Exception as e:
                logger.warning("FrigateAlerts: invio a %s fallito: %s", cid, e)
        logger.info("FrigateAlerts: avviso inviato — %s", caption)
