"""
agent/routine_manager.py — Smart Daily Routine Manager v3.

Impara le abitudini di ogni persona tracciata in Home Assistant:
  - Orari uscita/rientro
  - Zone visitate durante il giorno (lavoro, palestra, ecc.)
  - Durata delle soste
  - Pattern settimanali (lunedì/martedì/ecc.)

Ogni notte alle 23:45 aggiorna un file markdown per persona:
  /config/homemind_patches/routines/Agostino.md
  /config/homemind_patches/routines/Rosa.md
  ecc.

Funziona con qualsiasi nome utente configurato in HA.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from utils.timezone_helper import now_local
try:
    from agent.location_tracker import get_person_stops, _get_tracker_eid
    _HAS_LOCATION_TRACKER = True
except ImportError:
    _HAS_LOCATION_TRACKER = False

logger = logging.getLogger("homemind.routine")

ROUTINE_PATH = Path("/data/homemind_routine.json")
ROUTINES_DIR = Path("/config/homemind_patches/routines")
MIN_DAYS     = 3

DAYS_IT = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

# Zone speciali che non vogliamo mostrare come "sosta"
_SKIP_ZONES = {"not_home", "unknown", "unavailable", ""}


def _avg_time(times: list):
    if not times:
        return None
    avg = sum(times) / len(times)
    return int(avg), int((avg % 1) * 60)


def _fmt(h, m) -> str:
    return f"{h:02d}:{m:02d}"


def _std_min(times: list) -> float:
    if len(times) < 2:
        return 0.0
    avg = sum(times) / len(times)
    return (sum((t - avg) ** 2 for t in times) / len(times)) ** 0.5 * 60


def _friendly_zone(zone: str) -> str:
    """Rende leggibile il nome zona (rimuove prefissi HA, capitalizza)."""
    z = zone.strip().lower()
    if z in ("home", "casa"):
        return "🏠 Casa"
    if z in ("not_home",):
        return "🚗 Fuori casa"
    # Rimuovi prefisso "zone." se presente
    if z.startswith("zone."):
        z = z[5:]
    return "📍 " + z.replace("_", " ").capitalize()


class RoutineManager:
    def __init__(self, home=None, notifier=None, rest_client=None,
                 state_cache_cb=None, ai=None, security_manager=None, db=None):
        self.home      = home
        self.notifier  = notifier
        self.rest      = rest_client
        self._cache_cb = state_cache_cb
        self.ai        = ai
        self.security  = security_manager
        self._db       = db

        self._patterns: dict = {}
        self._today_events: list = []
        # Traccia la zona corrente per persona: {name: {zone, since_ts}}
        self._current_zone: dict = {}
        self._last_suggestion_ts = 0.0
        self._pending_action: Optional[str] = None
        self._task: Optional[asyncio.Task] = None
        self._rest = rest_client  # alias per location_tracker
        self._load()

    @property
    def _cache(self) -> dict:
        return self._cache_cb() if self._cache_cb else {}

    # ─────────────────────────────────────────────────────────────────────────
    # Persistenza JSON

    def _load(self):
        try:
            if ROUTINE_PATH.exists():
                data = json.loads(ROUTINE_PATH.read_text())
                self._patterns = data.get("patterns", {})
                n = len(self._patterns.get("per_person", {}))
                logger.info("RoutineManager: caricati pattern per %d giorni di storico", n)
        except Exception as e:
            logger.warning("RoutineManager load error: %s", e)
            self._patterns = {}

    def _save(self):
        try:
            ROUTINE_PATH.parent.mkdir(parents=True, exist_ok=True)
            ROUTINE_PATH.write_text(json.dumps(
                {"patterns": self._patterns, "updated": time.time()},
                indent=2, ensure_ascii=False
            ))
        except Exception as e:
            logger.warning("RoutineManager save error: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Tracking zone in tempo reale

    def record_zone_change(self, person_name: str, old_zone: str, new_zone: str):
        """Chiamato da security_manager quando person.* cambia stato.
        Registra la sosta nella zona precedente e inizia il tracking della nuova."""
        now = now_local()
        ts  = time.time()
        old_z = (old_zone or "").lower().strip()
        new_z = (new_zone or "").lower().strip()

        # Chiudi sosta precedente
        if person_name in self._current_zone:
            prev = self._current_zone[person_name]
            prev_zone  = prev.get("zone", "")
            prev_since = prev.get("since_ts", ts)
            duration_min = int((ts - prev_since) / 60)

            # Registra solo soste > 5 minuti e zone significative
            if duration_min >= 5 and prev_zone.lower() not in _SKIP_ZONES:
                self._today_events.append({
                    "type":         "zone_visit",
                    "person":       person_name,
                    "zone":         prev_zone,
                    "start_hour":   prev.get("start_hour", now.hour),
                    "start_minute": prev.get("start_minute", now.minute),
                    "end_hour":     now.hour,
                    "end_minute":   now.minute,
                    "duration_min": duration_min,
                    "ts":           ts,
                    "weekday":      now.weekday(),
                })
                logger.debug("RoutineManager zone_visit: %s @ %s per %d min",
                             person_name, prev_zone, duration_min)

        # Inizia tracking nuova zona
        if new_z not in _SKIP_ZONES:
            self._current_zone[person_name] = {
                "zone":         new_z,
                "since_ts":     ts,
                "start_hour":   now.hour,
                "start_minute": now.minute,
            }
        elif person_name in self._current_zone:
            del self._current_zone[person_name]

    def record_event(self, event_type: str, person: str = "", zone: str = ""):
        """Registra eventi di partenza/arrivo/cucina. Chiamato da security_manager."""
        now = now_local()
        self._today_events.append({
            "type":    event_type,
            "person":  person,
            "zone":    zone,
            "hour":    now.hour,
            "minute":  now.minute,
            "ts":      time.time(),
            "weekday": now.weekday(),
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Apprendimento pattern

    async def _update_patterns_from_today(self):
        """Analizza eventi di oggi e aggiorna i pattern per ogni persona."""
        if not self.home:
            return

        now = now_local()
        weekday = now.weekday()  # 0=lunedì, 6=domenica

        patterns = self._patterns
        if "per_person" not in patterns:
            patterns["per_person"] = {}
        patterns.setdefault("departure_times", [])
        patterns.setdefault("arrival_times", [])
        patterns.setdefault("kitchen_morning", [])
        patterns.setdefault("days_learned", 0)

        # Inizializza entry per TUTTE le persone conosciute da HA
        # anche se oggi non hanno avuto eventi — così i file .md vengono
        # creati per tutti gli utenti, non solo per chi si è mosso
        if self.home and hasattr(self.home, "persons"):
            for _peid, _pdata in self.home.persons.items():
                _pname = _pdata.get("name", "").strip()
                if _pname and _pname != "sconosciuto":
                    patterns["per_person"].setdefault(_pname, {
                        "departure_times": [],
                        "arrival_times":   [],
                        "kitchen_morning": [],
                        "zone_visits":     {},
                        "weekly":          {},
                        "frequent_places": {},
                        "days_observed":   0,
                    })

        sorted_events = sorted(self._today_events, key=lambda e: e.get("ts", 0))
        last_by_key = {}

        for event in sorted_events:
            etype  = event.get("type")
            hour   = event.get("hour")
            minute = event.get("minute", 0)
            person = event.get("person", "") or "sconosciuto"
            zone   = event.get("zone", "")
            ts     = event.get("ts", 0)
            wday   = event.get("weekday", weekday)

            if hour is None:
                continue
            if 1 <= hour <= 5:
                continue

            pp = patterns["per_person"].setdefault(person, {
                "departure_times": [],
                "arrival_times":   [],
                "kitchen_morning": [],
                "zone_visits":     {},   # zona → lista {h_start, m_start, h_end, m_end, dur}
                "weekly":          {},   # "0"→lun … "6"→dom → lista descrizioni giorno
                "days_observed":   0,
            })

            time_val = hour + minute / 60

            if etype in ("departure", "arrival", "kitchen_morning"):
                key = (person, etype)
                if key in last_by_key and (ts - last_by_key[key]) < 1800:
                    continue
                last_by_key[key] = ts

                if etype == "departure":
                    pp["departure_times"].append(time_val)
                    pp["departure_times"] = pp["departure_times"][-30:]
                    patterns["departure_times"].append(time_val)
                    patterns["departure_times"] = patterns["departure_times"][-30:]
                elif etype == "arrival":
                    pp["arrival_times"].append(time_val)
                    pp["arrival_times"] = pp["arrival_times"][-30:]
                    patterns["arrival_times"].append(time_val)
                    patterns["arrival_times"] = patterns["arrival_times"][-30:]
                elif etype == "kitchen_morning":
                    pp["kitchen_morning"].append(time_val)
                    pp["kitchen_morning"] = pp["kitchen_morning"][-30:]
                    patterns["kitchen_morning"].append(time_val)
                    patterns["kitchen_morning"] = patterns["kitchen_morning"][-30:]

            elif etype == "zone_visit" and zone and zone.lower() not in _SKIP_ZONES:
                dur  = event.get("duration_min", 0)
                hs   = event.get("start_hour", hour)
                ms   = event.get("start_minute", minute)
                he   = event.get("end_hour", hour)
                me   = event.get("end_minute", minute)

                # Accumula statistiche per zona
                zv = pp.setdefault("zone_visits", {})
                zv.setdefault(zone, []).append({
                    "h_start": hs, "m_start": ms,
                    "h_end":   he, "m_end":   me,
                    "dur":     dur,
                })
                zv[zone] = zv[zone][-30:]

                # Aggiungi al diario settimanale
                wk = pp.setdefault("weekly", {})
                day_key = str(wday)
                entry = f"{_fmt(hs, ms)}–{_fmt(he, me)}: {_friendly_zone(zone)} ({dur} min)"
                wk.setdefault(day_key, []).append(entry)
                wk[day_key] = wk[day_key][-10:]  # max 10 soste per giorno

        # Aggiorna contatore giorni
        for person, pp in patterns["per_person"].items():
            pp["days_observed"] = pp.get("days_observed", 0) + 1

        patterns["days_learned"] = patterns.get("days_learned", 0) + 1
        self._today_events = []
        self._patterns = patterns
        self._save()
        logger.info("RoutineManager: pattern aggiornati (giorno %d, persone=%d)",
                    patterns["days_learned"], len(patterns["per_person"]))

    # ─────────────────────────────────────────────────────────────────────────
    # Scrittura file markdown

    def _apply_stop_to_person(self, pp: dict, stop: dict) -> bool:
        """Applica una sosta GPS ai pattern della persona (frequent_places,
        gps_stops_by_date, weekly). Usato da enrich giornaliero e backfill.
        Ritorna True se applicata, False se scartata."""
        if "error" in stop:
            return False
        addr    = stop.get("address", "")
        is_home = stop.get("is_home", False) or addr == "\U0001f3e0 Casa"
        dur     = int(stop.get("minutes", 0))
        lat     = stop.get("lat", 0)
        lon     = stop.get("lon", 0)
        if is_home or dur < 10:
            return False

        # Ricava data/orari dal campo start (datetime oggetto) se disponibile
        start_dt = stop.get("start")
        if start_dt:
            try:
                local_start = start_dt.astimezone()
                date_str = local_start.strftime("%Y-%m-%d")
                wday     = local_start.weekday()
                h_start  = local_start.hour
                m_start  = local_start.minute
            except Exception:
                _n = now_local()
                date_str, wday = _n.strftime("%Y-%m-%d"), _n.weekday()
                h_start = stop.get("start_local_hour", _n.hour)
                m_start = stop.get("start_local_minute", 0)
        else:
            _n = now_local()
            date_str, wday = _n.strftime("%Y-%m-%d"), _n.weekday()
            h_start = stop.get("start_local_hour", _n.hour)
            m_start = stop.get("start_local_minute", 0)

        end_dt = stop.get("end")
        if end_dt:
            try:
                local_end = end_dt.astimezone()
                h_end, m_end = local_end.hour, local_end.minute
            except Exception:
                h_end = stop.get("end_local_hour", h_start)
                m_end = stop.get("end_local_minute", m_start)
        else:
            h_end = stop.get("end_local_hour", h_start)
            m_end = stop.get("end_local_minute", m_start)

        stop_entry = {"addr": addr, "dur": dur,
                      "h_start": h_start, "m_start": m_start,
                      "h_end": h_end, "m_end": m_end}

        # gps_stops_by_date: mantieni ultimi 7 giorni
        gsbd = pp.setdefault("gps_stops_by_date", {})
        day_stops = gsbd.setdefault(date_str, [])
        if not any(s.get("addr") == addr and abs(s.get("h_start", -99) - h_start) < 1
                   for s in day_stops):
            day_stops.append(stop_entry)
        if len(gsbd) > 7:
            del gsbd[min(gsbd.keys())]

        # frequent_places: conta una volta per data per luogo
        fp = pp.setdefault("frequent_places", {})
        coord_key = f"{lat:.3f},{lon:.3f}"
        has_real_addr = addr and not addr.startswith("(")

        # Se l'indirizzo è reale, cerca se esiste già una chiave con coordinate
        # vicine (stesso posto già salvato come coordinate) e fondila
        if has_real_addr and coord_key in fp and addr not in fp:
            # Sposta i dati dalla chiave-coordinate alla chiave-indirizzo
            fp[addr] = fp.pop(coord_key)
            fp[addr]["addr"] = addr
        fp_key = addr if has_real_addr else coord_key

        if fp_key not in fp:
            fp[fp_key] = {"addr": addr or fp_key, "lat": lat, "lon": lon,
                          "visit_count": 0, "total_min": 0,
                          "first_seen": date_str, "last_seen": date_str,
                          "hours": [], "counted_dates": []}
        counted = fp[fp_key].setdefault("counted_dates", [])
        if date_str not in counted:
            fp[fp_key]["visit_count"] += 1
            fp[fp_key]["total_min"]   += dur
            fp[fp_key]["hours"].append(h_start)
            fp[fp_key]["hours"] = fp[fp_key]["hours"][-60:]
            counted.append(date_str)
            counted[:] = counted[-90:]
        if date_str > fp[fp_key].get("last_seen", ""):
            fp[fp_key]["last_seen"] = date_str
        if date_str < fp[fp_key].get("first_seen", "9999"):
            fp[fp_key]["first_seen"] = date_str
        if has_real_addr:
            fp[fp_key]["addr"] = addr

        # weekly diary
        wk = pp.setdefault("weekly", {})
        label = f"\U0001f4cd {addr}" if addr else "\U0001f4cd Luogo sconosciuto"
        entry = f"{_fmt(h_start,m_start)}\u2013{_fmt(h_end,m_end)}: {label} ({dur} min)"
        day_entries = wk.setdefault(str(wday), [])
        if entry not in day_entries:
            day_entries.append(entry)
        wk[str(wday)] = sorted(set(day_entries))[-10:]

        return True

    async def _enrich_with_gps_stops(self, hours: int = 26):
        """Arricchisce i pattern con soste GPS + indirizzi Nominatim.
        hours=26 copre la giornata con margine."""
        if not _HAS_LOCATION_TRACKER or not self.rest:
            return
        per_person = self._patterns.get("per_person", {})
        for name in list(per_person.keys()):
            if name == "sconosciuto":
                continue
            if not _get_tracker_eid(name):
                logger.debug("RoutineManager GPS: nessun tracker per %s", name)
                continue
            try:
                stops = await get_person_stops(self.rest, name,
                                               hours=hours, min_stop_min=10, radius_m=150)
                if not stops:
                    continue
                if len(stops) == 1 and "error" in stops[0]:
                    logger.warning("RoutineManager GPS [%s]: %s", name, stops[0]["error"])
                    continue
                pp = per_person[name]
                count = sum(1 for s in stops if self._apply_stop_to_person(pp, s))
                logger.info("RoutineManager GPS: %s \u2014 %d soste", name, count)
                if hasattr(self, "_db") and self._db:
                    today_str = now_local().strftime("%Y-%m-%d")
                    today_stops = pp.get("gps_stops_by_date", {}).get(today_str, [])
                    if today_stops:
                        try:
                            await self._db.save_person_stops(name, today_str, today_stops)
                        except Exception as _dbe:
                            logger.debug("RoutineManager DB stops error: %s", _dbe)
            except Exception as e:
                logger.warning("RoutineManager GPS enrich error [%s]: %s", name, e)
        self._save()

    async def _backfill_gps_history(self, days: int = 30):
        """Legge storico GPS degli ultimi N giorni da HA e popola
        frequent_places e gps_stops_by_date. Eseguito una sola volta
        (flag _backfill_done). Forzabile da force_write_md_async."""
        if not _HAS_LOCATION_TRACKER or not self.rest:
            return
        PARAMS_VERSION = "v2"
        cached_ver = self._patterns.get("_backfill_params_version", "")
        already_done = self._patterns.get("_backfill_done") and days <= 30
        if already_done and cached_ver == PARAMS_VERSION:
            logger.debug("RoutineManager: backfill già eseguito (params %s), skip", PARAMS_VERSION)
            return
        if cached_ver != PARAMS_VERSION:
            logger.info("RoutineManager: parametri GPS cambiati (%s→%s) — ricalcolo",
                        cached_ver, PARAMS_VERSION)
            for pp in self._patterns.get("per_person", {}).values():
                if isinstance(pp, dict):
                    pp["gps_stops_by_date"] = {}
        logger.info("RoutineManager: avvio backfill GPS %d giorni...", days)
        per_person = self._patterns.get("per_person", {})
        for name in list(per_person.keys()):
            if name == "sconosciuto":
                continue
            if not _get_tracker_eid(name):
                continue
            try:
                stops = await get_person_stops(self.rest, name,
                                               hours=days * 24, min_stop_min=8, radius_m=200)
                if not stops:
                    continue
                if len(stops) == 1 and "error" in stops[0]:
                    logger.warning("RoutineManager backfill [%s]: %s", name, stops[0]["error"])
                    continue
                pp = per_person[name]
                count = sum(1 for s in stops if self._apply_stop_to_person(pp, s))
                logger.info("RoutineManager backfill: %s \u2014 %d soste su %d giorni",
                            name, count, days)
                if hasattr(self, "_db") and self._db:
                    for date_str, day_stops in pp.get("gps_stops_by_date", {}).items():
                        if day_stops:
                            try:
                                await self._db.save_person_stops(name, date_str, day_stops)
                            except Exception as _dbe:
                                logger.debug("RoutineManager backfill DB error: %s", _dbe)
            except Exception as e:
                logger.warning("RoutineManager backfill error [%s]: %s", name, e)
        self._patterns["_backfill_done"] = True
        self._patterns["_backfill_params_version"] = PARAMS_VERSION
        self._save()
        logger.info("RoutineManager: backfill GPS completato")

    def _write_person_md(self, name: str, data: dict, days_learned: int):
        """Scrive il file markdown con abitudini complete della persona."""
        try:
            ROUTINES_DIR.mkdir(parents=True, exist_ok=True)
            fname = ROUTINES_DIR / f"{name.capitalize()}.md"

            dep   = data.get("departure_times", [])
            arr   = data.get("arrival_times", [])
            kit   = data.get("kitchen_morning", [])
            zv    = data.get("zone_visits", {})
            wk    = data.get("weekly", {})
            obs   = data.get("days_observed", days_learned)

            lines = [
                f"# 👤 Routine di {name.capitalize()}",
                f"",
                f"> Aggiornato: {now_local().strftime('%d/%m/%Y %H:%M')} — basato su **{obs} giorni** osservati",
                f"",
                f"---",
                f"",
                f"## 🕐 Orari abituali",
                f"",
            ]

            has_times = False
            rows = []
            if len(dep) >= 2:
                t  = _avg_time(dep)
                sd = _std_min(dep)
                if t:
                    rows.append(f"| 🚗 Uscita di casa | **{_fmt(*t)}** | ±{sd:.0f} min |")
                    has_times = True
            if len(arr) >= 2:
                t  = _avg_time(arr)
                sd = _std_min(arr)
                if t:
                    rows.append(f"| 🏠 Rientro a casa | **{_fmt(*t)}** | ±{sd:.0f} min |")
                    has_times = True
            if len(kit) >= 2:
                t = _avg_time(kit)
                if t:
                    rows.append(f"| 🌅 Attività mattutina | **{_fmt(*t)}** | — |")
                    has_times = True

            if has_times:
                lines += [
                    "| Evento | Orario tipico | Variabilità |",
                    "|--------|:------------:|:-----------:|",
                ] + rows
            else:
                lines.append("*Dati insufficienti per calcolare orari tipici.*")

            # ── Luoghi frequenti (GPS cumulativo) ───────────────────────────
            lines += ["", "---", "", "## 📍 Luoghi più frequentati", ""]
            fp = data.get("frequent_places", {})
            if fp:
                # Ordina per visite decrescenti
                fp_sorted = sorted(fp.values(), key=lambda x: x["visit_count"], reverse=True)
                lines += [
                    "| # | Luogo | Visite | Tempo totale | Orario tipico | Prima visita |",
                    "|---|-------|:------:|:------------:|:-------------:|:------------:|",
                ]
                for i, place in enumerate(fp_sorted[:15], 1):  # max 15 luoghi
                    addr      = place.get("addr", "—")
                    visits    = place.get("visit_count", 0)
                    total_min = place.get("total_min", 0)
                    hours_list = place.get("hours", [])
                    first     = place.get("first_seen", "—")

                    # Durata totale formattata
                    if total_min >= 60:
                        tot_str = f"{total_min//60}h {total_min%60}m"
                    else:
                        tot_str = f"{total_min}m"

                    # Orario medio di arrivo
                    if hours_list:
                        avg_h = int(sum(hours_list) / len(hours_list))
                        typ_time = f"~{avg_h:02d}:xx"
                    else:
                        typ_time = "—"

                    lines.append(
                        f"| {i} | **{addr}** | {visits}x | {tot_str} | {typ_time} | {first} |"
                    )
            elif zv:
                # Fallback: zone HA senza GPS
                for zone, visits in sorted(zv.items()):
                    if not visits:
                        continue
                    durs   = [v["dur"] for v in visits]
                    avg_d  = int(sum(durs) / len(durs))
                    starts = [v["h_start"] + v["m_start"]/60 for v in visits]
                    t = _avg_time(starts)
                    t_str = f"verso le {_fmt(*t)}" if t else ""
                    lines.append(
                        f"- **{_friendly_zone(zone)}** — "
                        f"visitato {len(visits)} volte, media {avg_d} min {t_str}"
                    )
            else:
                lines.append("*Nessun dato GPS ancora. Configura `location_tracker` nel person_config.json.*")

            # ── Soste GPS ultimi 7 giorni ────────────────────────────────────
            gsbd = data.get("gps_stops_by_date", {})
            if gsbd:
                lines += ["", "### 📡 Soste recenti (ultimi 7 giorni)", ""]
                import re as _re_md
                _coord_pattern = _re_md.compile(r"^\(\d+\.\d+,\s*\d+\.\d+\)$")
                for date_key in sorted(gsbd.keys(), reverse=True):
                    raw_stops = gsbd[date_key]
                    # Deduplicazione: per ogni finestra oraria (±10min) tieni solo
                    # la versione con indirizzo reale, scarta le coordinate grezze
                    seen_windows = {}  # h_start arrotondato → stop scelto
                    for s in raw_stops:
                        addr = s.get("addr", "")
                        if addr == "🏠 Casa":
                            continue
                        win = round(s.get("h_start", 0) * 6 + s.get("m_start", 0) / 10)
                        is_coord = bool(_coord_pattern.match(addr))
                        existing = seen_windows.get(win)
                        if existing is None:
                            seen_windows[win] = s
                        elif is_coord:
                            pass  # già esiste uno migliore, skip coordinate
                        else:
                            seen_windows[win] = s  # sostituisci coordinate con indirizzo reale
                    day_stops = sorted(seen_windows.values(), key=lambda s: (s.get("h_start",0), s.get("m_start",0)))
                    if not day_stops:
                        continue
                    lines.append(f"**{date_key}**")
                    for s in day_stops:
                        addr = s.get("addr", "?")
                        lines.append(
                            f"- {addr} — "
                            f"{_fmt(s['h_start'],s['m_start'])}–{_fmt(s['h_end'],s['m_end'])} "
                            f"({s['dur']} min)"
                        )
                    lines.append("")

            # ── Diario settimanale ───────────────────────────────────────────
            lines += ["", "---", "", "## 📅 Diario settimanale", ""]
            if wk:
                for day_idx in range(7):
                    day_key = str(day_idx)
                    if day_key not in wk or not wk[day_key]:
                        continue
                    lines.append(f"### {DAYS_IT[day_idx]}")
                    lines.append("")
                    for entry in wk[day_key]:
                        lines.append(f"- {entry}")
                    lines.append("")
            else:
                lines.append("*Il diario si compila automaticamente man mano che i dati vengono raccolti.*")

            # ── Storico uscite ───────────────────────────────────────────────
            lines += ["---", "", "## 📊 Ultime uscite registrate", ""]
            if dep:
                lines += ["| # | Orario |", "|---|--------|"]
                for i, v in enumerate(reversed(dep[-10:]), 1):
                    h, m = int(v), int((v % 1) * 60)
                    lines.append(f"| {i} | {h:02d}:{m:02d} |")
            else:
                lines.append("*Nessuna uscita registrata ancora.*")

            # ── Note manuali ─────────────────────────────────────────────────
            lines += [
                "",
                "---",
                "",
                "## 📝 Note personali",
                "",
                "<!-- Le note scritte qui sotto non verranno mai sovrascritte da HomeMind -->",
                "",
            ]

            # Preserva note manuali esistenti
            manual = ""
            if fname.exists():
                old = fname.read_text(encoding="utf-8")
                marker = "<!-- Le note scritte qui sotto non verranno mai sovrascritte da HomeMind -->"
                if marker in old:
                    after = old.split(marker, 1)[1].strip()
                    if after:
                        manual = "\n" + after

            content = "\n".join(lines)
            if manual:
                content += manual

            fname.write_text(content, encoding="utf-8")
            logger.info("RoutineManager: aggiornato %s (%d bytes)", fname.name, len(content))

        except Exception as e:
            logger.warning("RoutineManager write_md error [%s]: %s", name, e)

    def _write_all_person_md(self):
        per_person = self._patterns.get("per_person", {})
        days = self._patterns.get("days_learned", 0)
        for name, data in per_person.items():
            if name and name != "sconosciuto":
                self._write_person_md(name, data, days)

    # ─────────────────────────────────────────────────────────────────────────
    # Loop principale

    async def start(self):
        self._task = asyncio.create_task(self._main_loop(), name="routine_manager")
        logger.info("RoutineManager avviato — monitoro routine e anticipo bisogni")

    async def _main_loop(self):
        await asyncio.sleep(90)  # aspetta che tutto sia avviato
        # Backfill storico al primo avvio (una sola volta)
        try:
            self._ensure_all_persons_initialized()
            await self._backfill_gps_history(days=30)
            self._write_all_person_md()
        except Exception as _be:
            logger.warning("RoutineManager: backfill avvio fallito: %s", _be)

        while True:
            try:
                now = now_local()
                if now.hour == 23 and now.minute == 45:
                    await self._update_patterns_from_today()
                    await self._enrich_with_gps_stops(hours=26)
                    self._write_all_person_md()
                    await asyncio.sleep(60)
                await self._proactive_check()
            except Exception as e:
                logger.warning("RoutineManager loop error: %s", e)
            await asyncio.sleep(120)

    # ─────────────────────────────────────────────────────────────────────────
    # Controllo proattivo

    async def _proactive_check(self):
        if not self.home:
            return
        now  = now_local()
        if not (6 <= now.hour <= 23):
            return
        if time.time() - self._last_suggestion_ts < 1800:
            return
        _, alarm_st = self.home.primary_alarm()
        if alarm_st in ("armed_away", "arming"):
            return
        if self._patterns.get("days_learned", 0) < MIN_DAYS:
            return
        await self._check_departure_prediction()

    async def _check_departure_prediction(self):
        now  = now_local()
        hour = now.hour + now.minute / 60
        if not (6 <= now.hour <= 10):
            return
        dep = self._patterns.get("departure_times", [])
        if len(dep) < MIN_DAYS:
            return
        avg = sum(dep) / len(dep)
        avg_h = int(avg); avg_m = int((avg - avg_h) * 60)
        diff_min = (avg - hour) * 60
        if not (5 <= diff_min <= 30):
            return
        kitchen_active = any(
            v["state"] == "on" and "cucina" in v.get("zone", "").lower()
            for v in self.home.motion_sensors.values()
        )
        if not kitchen_active or not self.home.who_is_home():
            return
        self._last_suggestion_ts = time.time()
        self._pending_action = "prepare_departure"
        msg = (f"🏃 Di solito esci intorno alle {avg_h:02d}:{avg_m:02d} — "
               f"mancano circa {int(diff_min)} minuti.\n\n"
               f"Vuoi che preparo la casa? (riscaldamento + luci)\n\nRispondi <b>sì</b>")
        if self.notifier:
            await self.notifier.send_html(msg)

    async def handle_confirm(self, text: str) -> bool:
        if not self._pending_action:
            return False
        if time.time() - self._last_suggestion_ts > 600:
            self._pending_action = None
            return False
        text_low = text.lower().strip()
        is_yes = text_low in ("sì", "si", "yes", "ok", "conferma", "vai")
        is_no  = text_low in ("no", "non ora", "dopo", "annulla")
        if not (is_yes or is_no):
            return False
        action = self._pending_action
        self._pending_action = None
        if is_no:
            if self.notifier:
                await self.notifier.send_html("👍 Ok, non faccio nulla.")
            return True
        if action == "prepare_departure":
            await self._execute_prepare_departure()
        return True

    async def _execute_prepare_departure(self):
        done = []
        if self.rest and self.home:
            for eid in self.home.climate:
                try:
                    await self.rest.call_service("climate", "set_temperature",
                                                  {"temperature": 18}, target={"entity_id": eid})
                    done.append("🌡️ Riscaldamento abbassato a 18°")
                except Exception:
                    pass
            lights = self.home.lights_on()
            if lights:
                try:
                    await self.rest.call_service("light", "turn_off", {},
                                                  target={"entity_id": lights})
                    done.append(f"💡 Spente {len(lights)} luci")
                except Exception:
                    pass
        msg = ("✅ Fatto!\n" + "\n".join(done) if done else "✅ Già tutto a posto!") + "\n\n🚪 Buona giornata!"
        if self.notifier:
            await self.notifier.send_html(msg)

    # ─────────────────────────────────────────────────────────────────────────
    # API pubblica

    def get_status(self) -> str:
        days = self._patterns.get("days_learned", 0)
        per_person = self._patterns.get("per_person", {})

        if days < MIN_DAYS and not per_person:
            return (f"📅 <b>Routine Manager</b>\n\n"
                    f"⏳ Sto imparando...\n"
                    f"Giorni osservati: <b>{days}/{MIN_DAYS}</b>")

        lines = [f"📅 <b>Routine apprese</b> ({days} giorni)\n"]

        for name in sorted(per_person.keys()):
            if name == "sconosciuto":
                continue
            data = per_person[name]
            dep  = data.get("departure_times", [])
            arr  = data.get("arrival_times", [])
            zv   = data.get("zone_visits", {})
            obs  = data.get("days_observed", 0)

            lines.append(f"\n<b>👤 {name.capitalize()}</b> ({obs} giorni osservati)")

            if len(dep) >= 2:
                t = _avg_time(dep)
                if t:
                    lines.append(f"  🚗 Uscita tipica: <b>{_fmt(*t)}</b> (±{_std_min(dep):.0f} min)")
            else:
                lines.append("  🚗 Uscita: <i>dati insufficienti</i>")

            if len(arr) >= 2:
                t = _avg_time(arr)
                if t:
                    lines.append(f"  🏠 Rientro tipico: <b>{_fmt(*t)}</b> (±{_std_min(arr):.0f} min)")
            else:
                lines.append("  🏠 Rientro: <i>dati insufficienti</i>")

            if zv:
                top = sorted(zv.items(), key=lambda x: len(x[1]), reverse=True)[:3]
                zones_str = " · ".join(_friendly_zone(z) for z, _ in top)
                lines.append(f"  📍 Zone frequenti: {zones_str}")

            md = ROUTINES_DIR / f"{name.capitalize()}.md"
            if md.exists():
                lines.append(f"  📄 <code>{md}</code>")

        lines.append("\n<i>File .md aggiornati ogni notte alle 23:45</i>")
        return "\n".join(lines)

    def get_routine_summary(self) -> str:
        days = self._patterns.get("days_learned", 0)
        if days < MIN_DAYS:
            return ""
        per_person = self._patterns.get("per_person", {})
        lines = ["📅 <b>Routine di oggi</b>"]
        for name in sorted(per_person.keys()):
            if name == "sconosciuto":
                continue
            data = per_person[name]
            p_lines = []
            t = _avg_time(data.get("departure_times", []))
            if t and len(data.get("departure_times", [])) >= 2:
                p_lines.append(f"  🚗 Esci verso le {_fmt(*t)}")
            t = _avg_time(data.get("arrival_times", []))
            if t and len(data.get("arrival_times", [])) >= 2:
                p_lines.append(f"  🏠 Rientri verso le {_fmt(*t)}")
            if p_lines:
                lines.append(f"\n<b>👤 {name.capitalize()}</b>")
                lines.extend(p_lines)
        return "\n".join(lines) if len(lines) > 1 else ""

    def reset_routine(self) -> str:
        self._patterns = {
            "per_person":      {},
            "departure_times": [],
            "arrival_times":   [],
            "kitchen_morning": [],
            "days_learned":    0,
        }
        self._today_events = []
        self._current_zone = {}
        self._save()
        return "🔄 Routine azzerata. HomeMind ricomincerà ad apprendere da zero."

    def _ensure_all_persons_initialized(self):
        """Crea entry in per_person per tutte le persone conosciute da HA."""
        if self.home and hasattr(self.home, "persons"):
            per_person = self._patterns.setdefault("per_person", {})
            for _peid, _pdata in self.home.persons.items():
                _pname = _pdata.get("name", "").strip()
                if _pname and _pname != "sconosciuto":
                    per_person.setdefault(_pname, {
                        "departure_times": [], "arrival_times":   [],
                        "kitchen_morning": [], "zone_visits":     {},
                        "weekly":          {}, "frequent_places": {},
                        "gps_stops_by_date": {}, "days_observed": 0,
                    })

    async def force_write_md_async(self) -> str:
        """Versione asincrona: backfill GPS + enrichment oggi + scrivi file.
        Chiamata dal handler Telegram __ROUTINE_MD__."""
        self._ensure_all_persons_initialized()
        per_person = self._patterns.get("per_person", {})
        if not per_person:
            return "⚠️ Nessun dato — aggiungi i tracker GPS nel person_config.json."
        # Backfill 30 giorni (se non già fatto)
        await self._backfill_gps_history(days=30)
        # Enrichment odierno
        await self._enrich_with_gps_stops(hours=26)
        # Scrivi file
        self._write_all_person_md()
        files = [f"{ROUTINES_DIR}/{n.capitalize()}.md"
                 for n in per_person if n != "sconosciuto"]
        return "✅ File aggiornati:\n" + "\n".join(f"  📄 <code>{f}</code>" for f in files)

    def force_write_md(self) -> str:
        """Versione sincrona legacy — usata solo come fallback."""
        self._ensure_all_persons_initialized()
        per_person = self._patterns.get("per_person", {})
        if not per_person:
            return "⚠️ Nessun dato ancora — i file si creano dopo qualche giorno."
        self._write_all_person_md()
        files = [f"{ROUTINES_DIR}/{n.capitalize()}.md"
                 for n in per_person if n != "sconosciuto"]
        return "✅ File aggiornati:\n" + "\n".join(f"  📄 <code>{f}</code>" for f in files)
