"""
agent/habit_learner.py — Abitudini d'uso dei dispositivi, calcolate dai dati reali di Home Assistant.

Ogni notte legge lo storico (14 giorni) di luci, prese/interruttori e tapparelle e cerca gli orari in cui
SI RIPETONO ogni giorno (o nei feriali / nel weekend): «la luce Cucina si accende di solito verso le 19:10».

Niente AI: solo statistica, quindi niente fatti inventati e nessun costo. Le righe prodotte vengono
mostrate in /memoria e iniettate nel prompt come «abitudini osservate».

Persistenza: /data/homemind_habits.json
"""

import asyncio
import json
import logging
import re
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("homemind.habits")

HABITS_PATH   = Path("/data/homemind_habits.json")
DAYS_WINDOW   = 14           # giorni di storico analizzati
MIN_DAYS      = 5            # giorni distinti minimi perché sia un'abitudine
MIN_RATIO     = 0.40         # almeno il 40% dei giorni osservati
MAX_STD_MIN   = 45           # variabilità massima dell'orario (minuti)
CLUSTER_GAP   = 40           # minuti: eventi più vicini di così = stesso orario
MAX_PER_DAY   = 6            # più accensioni/giorno di media = dispositivo che sfarfalla (automazioni)
MAX_ENTITIES  = 80
BATCH         = 12
MAX_LINES     = 25
DAY_START_MIN = 180          # il «giorno» comincia alle 03:00: le 23:50 e le 00:10 restano vicine

DOMAINS = ("light", "switch", "cover")
_ON = {"light": {"on"}, "switch": {"on"}, "cover": {"open", "opening"}}
_VERB = {"light": ("La luce", "si accende"), "switch": ("L'interruttore", "si accende"),
         "cover": ("La tapparella", "si apre")}
# interruttori «tecnici» che non sono abitudini di nessuno: parole intere (così «presa remota» o
# «luce led cucina» NON vengono scartate) + qualche frase fissa
_SKIP_TOKENS = {"led", "ota", "dnd", "wifi", "bluetooth", "beep", "buzzer", "firmware", "debug", "backup", "reset",
                "update", "restart", "reboot", "identify", "record", "snapshot", "schedule", "automation",
                "indicator", "backlight"}
_SKIP_PHRASES = ("child_lock", "child lock", "permit_join", "permit join", "do_not_disturb", "do not disturb",
                 "night_mode", "sleep_mode", "motion_detection", "auto_update", "auto update", "enable_",
                 "presence_simulation", "calibrat", "detect")


def _is_technical(domain: str, text: str) -> bool:
    t = text.lower()
    if domain == "light":                      # le luci sono quasi sempre vere luci: filtro minimo
        return any(w in t for w in ("identify", "permit_join", "update"))
    if any(p in t for p in _SKIP_PHRASES):
        return True
    return any(tok in _SKIP_TOKENS for tok in re.split(r"[^a-z0-9àèéìòù]+", t) if tok)


# ─────────────────────────────────────────────────────────────────────────────
# Analisi pura (testabile senza Home Assistant)

def _shift(minute: int) -> int:
    return (minute - DAY_START_MIN) % 1440


def _unshift(minute: float) -> int:
    return int(round(minute + DAY_START_MIN)) % 1440


def find_habits(events: list, observed_days: int = DAYS_WINDOW) -> list:
    """events: datetime locali in cui il dispositivo è passato a «acceso/aperto».
    Ritorna [{minute, std, days, weekdays, daytype}] — una per ogni orario ricorrente."""
    if not events or observed_days <= 0:
        return []
    by_day: dict = {}
    for e in events:
        by_day.setdefault(e.date(), []).append(e)
    if len(events) / max(len(by_day), 1) > MAX_PER_DAY:
        return []                                         # sfarfalla: non è un'abitudine di una persona
    pts = sorted((_shift(e.hour * 60 + e.minute), e.date(), e.weekday()) for e in events)
    clusters, cur = [], [pts[0]]
    for p in pts[1:]:
        if p[0] - cur[-1][0] > CLUSTER_GAP:
            clusters.append(cur)
            cur = [p]
        else:
            cur.append(p)
    clusters.append(cur)

    out = []
    for c in clusters:
        days = {d for _, d, _ in c}
        if len(days) < MIN_DAYS or len(days) / observed_days < MIN_RATIO:
            continue
        mins = [m for m, _, _ in c]
        sd = statistics.pstdev(mins) if len(mins) > 1 else 0.0
        if sd > MAX_STD_MIN:
            continue
        wdays = {w for _, d, w in c if d in days}
        if len(days) >= 4 and wdays <= {0, 1, 2, 3, 4}:
            daytype = "nei giorni feriali"
        elif len(days) >= 3 and wdays <= {5, 6}:
            daytype = "nel weekend"
        else:
            daytype = ""
        out.append({"minute": _unshift(statistics.mean(mins)), "std": sd, "days": len(days),
                    "weekdays": sorted(wdays), "daytype": daytype})
    return out


def habit_line(domain: str, name: str, h: dict, observed_days: int = DAYS_WINDOW) -> str:
    kind, verb = _VERB.get(domain, ("Il dispositivo", "si accende"))
    hh, mm = divmod(int(h["minute"]), 60)
    extra = f", {h['daytype']}" if h.get("daytype") else ""
    return (f"{kind} «{name}» {verb} di solito verso le {hh:02d}:{mm:02d} "
            f"(±{h['std']:.0f} min, {h['days']} giorni su {observed_days}{extra})")


def events_from_rows(rows: list, domain: str, tz) -> list:
    """Righe della history HA (ordinate) → datetime locali dei passaggi a «acceso/aperto».
    La prima riga è lo stato iniziale della finestra, non un evento."""
    on = _ON.get(domain, {"on"})
    out, prev = [], None
    for r in rows:
        st = (r.get("state") or "").lower()
        if prev is not None and st in on and prev not in on:
            ts = r.get("last_changed") or r.get("last_updated") or ""
            try:
                out.append(datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz))
            except ValueError:
                pass
        prev = st
    return out


def eligible_entities(states: dict) -> dict:
    """{entity_id: nome} delle luci/prese/tapparelle di cui ha senso imparare l'orario."""
    out = {}
    for eid, st in (states or {}).items():
        dom = eid.split(".", 1)[0]
        if dom not in DOMAINS or not isinstance(st, dict):
            continue
        if st.get("state") in ("unavailable", "unknown"):
            continue
        if _is_technical(dom, eid.split(".", 1)[1]):
            continue
        name = (st.get("attributes") or {}).get("friendly_name") or eid.split(".", 1)[1].replace("_", " ").title()
        if _is_technical(dom, name):
            continue
        out[eid] = name
    return dict(list(out.items())[:MAX_ENTITIES])


# ─────────────────────────────────────────────────────────────────────────────

class HabitLearner:
    def __init__(self, rest_client=None, state_cache_cb=None):
        self.rest = rest_client
        self.state_cache_cb = state_cache_cb
        self._lines: list = []
        self._updated = 0.0
        self._task: Optional[asyncio.Task] = None
        self._load()

    # persistenza
    def _load(self):
        try:
            if HABITS_PATH.exists():
                d = json.loads(HABITS_PATH.read_text(encoding="utf-8"))
                self._lines = [str(x) for x in d.get("lines", [])]
                self._updated = float(d.get("updated", 0))
        except Exception as e:
            logger.debug("HabitLearner load: %s", e)

    def _save(self):
        try:
            HABITS_PATH.parent.mkdir(parents=True, exist_ok=True)
            HABITS_PATH.write_text(json.dumps({"lines": self._lines, "updated": self._updated},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            logger.warning("HabitLearner save: %s", e)

    def get_lines(self) -> list:
        return list(self._lines)

    # fetch (solo cambi di stato, risposta minimale: leggero anche con molte entità)
    async def _fetch(self, eids: list) -> dict:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=DAYS_WINDOW)
        fmt = "%Y-%m-%dT%H:%M:%S.000Z"
        url = (f"{self.rest.base}/history/period/{start.strftime(fmt)}"
               f"?filter_entity_id={','.join(eids)}&end_time={end.strftime(fmt)}"
               f"&minimal_response&no_attributes&significant_changes_only=1")
        async with self.rest._session.get(url) as r:
            if r.status != 200:
                logger.warning("HabitLearner history HTTP %s", r.status)
                return {}
            data = await r.json()
        out = {}
        for group in data or []:
            if group and group[0].get("entity_id"):
                out[group[0]["entity_id"]] = group
        return out

    async def refresh(self) -> int:
        """Ricalcola le abitudini. Ritorna quante righe ha prodotto (0 se non può)."""
        if not self.rest or not getattr(self.rest, "_session", None) or not self.state_cache_cb:
            return 0
        from utils.timezone_helper import local_tz
        tz = local_tz()
        ents = eligible_entities(self.state_cache_cb() or {})
        if not ents:
            return 0
        scored = []
        items = list(ents.items())
        for i in range(0, len(items), BATCH):
            batch = dict(items[i:i + BATCH])
            try:
                hist = await self._fetch(list(batch))
            except Exception as e:
                logger.warning("HabitLearner fetch: %s", e)
                continue
            for eid, rows in hist.items():
                dom = eid.split(".", 1)[0]
                for h in find_habits(events_from_rows(rows, dom, tz)):
                    scored.append((h["days"], habit_line(dom, batch.get(eid, eid), h)))
            await asyncio.sleep(0.2)
        scored.sort(key=lambda x: -x[0])
        self._lines = [ln for _, ln in scored[:MAX_LINES]]
        self._updated = time.time()
        self._save()
        logger.info("HabitLearner: %d abitudini d'uso trovate su %d dispositivi", len(self._lines), len(ents))
        return len(self._lines)

    # ciclo notturno
    async def _loop(self):
        await asyncio.sleep(300)                              # lascia finire l'avvio
        while True:
            try:
                if time.time() - self._updated > 20 * 3600:
                    await self.refresh()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("HabitLearner ciclo: %s", e)
            await asyncio.sleep(3600)                         # ricontrolla ogni ora, ricalcola ~1 volta al giorno

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="habit_learner")
