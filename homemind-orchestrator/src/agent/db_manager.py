"""
agent/db_manager.py — HomeMind Local Database

SQLite in /config/homemind_patches/db/homemind.db

Tabelle:
  energy_daily    — snapshot energetico giornaliero (da EnergyAnalyzer)
  appliance_cycles — cicli elettrodomestici (da ApplianceMonitor)
  person_stops    — soste GPS per persona (da RoutineManager/LocationTracker)
  energy_monthly  — aggregato mensile (compressione automatica fine mese)

Query veloci senza toccare HA:
  "quanta energia ho prodotto il 1 aprile?"
  "dove era Agostino giovedì scorso?"
  "quante volte ho usato la lavatrice questo mese?"
  "media produzione FV di aprile?"
"""

import asyncio
import logging
import sqlite3
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.db")

DB_DIR  = Path("/config/homemind_patches/db")
DB_PATH = DB_DIR / "homemind.db"

# ─────────────────────────────────────────────────────────────────────────────
# Schema SQL

_SCHEMA = """
CREATE TABLE IF NOT EXISTS energy_daily (
    date        TEXT PRIMARY KEY,   -- YYYY-MM-DD
    solar_kwh   REAL,               -- produzione FV del giorno
    grid_in_kwh REAL,               -- importata dalla rete
    grid_out_kwh REAL,              -- esportata in rete
    consume_kwh REAL,               -- consumo totale casa
    raw_json    TEXT,               -- snapshot completo JSON
    created_at  INTEGER             -- unix timestamp inserimento
);

CREATE TABLE IF NOT EXISTS energy_monthly (
    month           TEXT PRIMARY KEY,   -- YYYY-MM
    solar_total     REAL,
    grid_in_total   REAL,
    grid_out_total  REAL,
    consume_total   REAL,
    solar_avg_day   REAL,
    solar_max_day   REAL,
    solar_max_date  TEXT,
    days_count      INTEGER,
    created_at      INTEGER
);

CREATE TABLE IF NOT EXISTS appliance_cycles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    appliance   TEXT NOT NULL,      -- lavatrice, lavastoviglie, ecc.
    start_time  TEXT NOT NULL,      -- ISO datetime locale
    end_time    TEXT,               -- ISO datetime locale
    duration_min INTEGER,           -- durata ciclo in minuti
    kwh         REAL,               -- stima energia consumata (se disponibile)
    date        TEXT NOT NULL,      -- YYYY-MM-DD (per query rapide)
    created_at  INTEGER
);

CREATE TABLE IF NOT EXISTS person_stops (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    person       TEXT NOT NULL,     -- nome persona (Agostino, Rosa, ecc.)
    date         TEXT NOT NULL,     -- YYYY-MM-DD
    address      TEXT,              -- indirizzo reale (Nominatim)
    lat          REAL,
    lon          REAL,
    start_time   TEXT,              -- HH:MM
    end_time     TEXT,              -- HH:MM
    duration_min INTEGER,
    is_home      INTEGER DEFAULT 0, -- 1 se sosta a casa
    created_at   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_energy_daily_date    ON energy_daily(date);
CREATE INDEX IF NOT EXISTS idx_appliance_date       ON appliance_cycles(date, appliance);
CREATE INDEX IF NOT EXISTS idx_person_stops_person  ON person_stops(person, date);
"""

# ─────────────────────────────────────────────────────────────────────────────

class HomeMindDB:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self):
        """Crea DB e schema se non esistono."""
        try:
            DB_DIR.mkdir(parents=True, exist_ok=True)
            with self._conn() as conn:
                conn.executescript(_SCHEMA)
            logger.info("HomeMindDB: pronto in %s", DB_PATH)
        except Exception as e:
            logger.error("HomeMindDB init error: %s", e)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────────────────
    # ENERGIA

    async def save_energy_day(self, date_str: str, snap: dict):
        """Salva snapshot energetico giornaliero. Chiamato da EnergyAnalyzer."""
        import json
        async with self._lock:
            try:
                def _pick(*keys):
                    """Restituisce il primo valore non-None tra le chiavi date."""
                    for k in keys:
                        v = snap.get(k)
                        if v is not None:
                            return v
                    return None

                solar   = _pick("solar", "solar_kwh", "solar_production",
                                "fotovoltaico", "produzione_fv", "fv", "pv")
                grid_in = _pick("grid_in", "grid_in_kwh", "import",
                                "rete_import", "rete_enel", "grid_import",
                                "importazione_rete", "enel")
                grid_out= _pick("grid_out", "grid_out_kwh", "export",
                                "rete_export", "grid_export", "esportazione_rete")
                consume = _pick("consume", "consume_kwh", "consumption",
                                "consumo", "consumo_casa", "home_energy",
                                "casa")

                with self._conn() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO energy_daily
                        (date, solar_kwh, grid_in_kwh, grid_out_kwh, consume_kwh, raw_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        date_str,
                        solar,
                        grid_in,
                        grid_out,
                        consume,
                        json.dumps(snap, ensure_ascii=False),
                        int(time.time()),
                    ))
                logger.debug("HomeMindDB: energia %s salvata (solar=%s consume=%s grid_in=%s grid_out=%s)",
                             date_str, solar, consume, grid_in, grid_out)
            except Exception as e:
                logger.warning("HomeMindDB save_energy_day: %s", e)

    def query_energy_day(self, date_str: str) -> Optional[dict]:
        """Recupera energia di un giorno specifico. Risposta immediata."""
        try:
            import json
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM energy_daily WHERE date = ?", (date_str,)
                ).fetchone()
                if row:
                    result = dict(row)
                    if result.get("raw_json"):
                        result["raw"] = json.loads(result["raw_json"])
                    return result
        except Exception as e:
            logger.warning("HomeMindDB query_energy_day: %s", e)
        return None

    def query_energy_range(self, from_date: str, to_date: str) -> list:
        """Recupera energia per un range di date."""
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT date, solar_kwh, grid_in_kwh, grid_out_kwh, consume_kwh
                    FROM energy_daily
                    WHERE date BETWEEN ? AND ?
                    ORDER BY date
                """, (from_date, to_date)).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("HomeMindDB query_energy_range: %s", e)
        return []

    def query_energy_month(self, year_month: str) -> Optional[dict]:
        """Recupera aggregato mensile (YYYY-MM). Prima cerca in energy_monthly,
        poi calcola al volo da energy_daily se non compresso."""
        try:
            with self._conn() as conn:
                # Prova prima tabella aggregata
                row = conn.execute(
                    "SELECT * FROM energy_monthly WHERE month = ?", (year_month,)
                ).fetchone()
                if row:
                    return dict(row)
                # Calcola al volo
                rows = conn.execute("""
                    SELECT solar_kwh, grid_in_kwh, grid_out_kwh, consume_kwh, date
                    FROM energy_daily
                    WHERE date LIKE ?
                    ORDER BY date
                """, (f"{year_month}-%",)).fetchall()
                if not rows:
                    return None
                solar_vals = [r["solar_kwh"] for r in rows if r["solar_kwh"] is not None]
                return {
                    "month":          year_month,
                    "solar_total":    round(sum(solar_vals), 2),
                    "grid_in_total":  round(sum(r["grid_in_kwh"] for r in rows if r["grid_in_kwh"]), 2),
                    "grid_out_total": round(sum(r["grid_out_kwh"] for r in rows if r["grid_out_kwh"]), 2),
                    "consume_total":  round(sum(r["consume_kwh"] for r in rows if r["consume_kwh"]), 2),
                    "solar_avg_day":  round(sum(solar_vals)/len(solar_vals), 2) if solar_vals else 0,
                    "solar_max_day":  round(max(solar_vals), 2) if solar_vals else 0,
                    "solar_max_date": next((r["date"] for r in rows if r["solar_kwh"] == max(solar_vals, default=0)), ""),
                    "days_count":     len(rows),
                    "computed":       True,  # non da tabella aggregata
                }
        except Exception as e:
            logger.warning("HomeMindDB query_energy_month: %s", e)
        return None

    async def compress_month(self, year_month: str):
        """Aggrega il mese in energy_monthly e conserva i daily (non cancella)."""
        data = self.query_energy_month(year_month)
        if not data or data.get("days_count", 0) < 20:
            return  # mese incompleto, salta
        async with self._lock:
            try:
                with self._conn() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO energy_monthly
                        (month, solar_total, grid_in_total, grid_out_total,
                         consume_total, solar_avg_day, solar_max_day,
                         solar_max_date, days_count, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        year_month,
                        data.get("solar_total"), data.get("grid_in_total"),
                        data.get("grid_out_total"), data.get("consume_total"),
                        data.get("solar_avg_day"), data.get("solar_max_day"),
                        data.get("solar_max_date"), data.get("days_count"),
                        int(time.time()),
                    ))
                logger.info("HomeMindDB: mese %s compresso (%d giorni)", year_month, data["days_count"])
            except Exception as e:
                logger.warning("HomeMindDB compress_month: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # ELETTRODOMESTICI

    async def save_appliance_cycle(self, appliance: str, start_dt: datetime,
                                   end_dt: Optional[datetime] = None,
                                   duration_min: int = 0, kwh: float = 0.0):
        """Salva ciclo elettrodomestico. Chiamato da ApplianceMonitor."""
        async with self._lock:
            try:
                with self._conn() as conn:
                    conn.execute("""
                        INSERT INTO appliance_cycles
                        (appliance, start_time, end_time, duration_min, kwh, date, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        appliance,
                        start_dt.strftime("%Y-%m-%dT%H:%M"),
                        end_dt.strftime("%Y-%m-%dT%H:%M") if end_dt else None,
                        duration_min,
                        kwh if kwh else None,
                        start_dt.strftime("%Y-%m-%d"),
                        int(time.time()),
                    ))
                logger.debug("HomeMindDB: ciclo %s salvato (%d min)", appliance, duration_min)
            except Exception as e:
                logger.warning("HomeMindDB save_appliance_cycle: %s", e)

    def query_appliance_cycles(self, appliance: str = None,
                                from_date: str = None, to_date: str = None,
                                limit: int = 50) -> list:
        """Recupera cicli elettrodomestici con filtri opzionali."""
        try:
            conditions = []
            params = []
            if appliance:
                conditions.append("appliance LIKE ?")
                params.append(f"%{appliance}%")
            if from_date:
                conditions.append("date >= ?")
                params.append(from_date)
            if to_date:
                conditions.append("date <= ?")
                params.append(to_date)
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            params.append(limit)
            with self._conn() as conn:
                rows = conn.execute(f"""
                    SELECT * FROM appliance_cycles
                    {where}
                    ORDER BY start_time DESC
                    LIMIT ?
                """, params).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("HomeMindDB query_appliance_cycles: %s", e)
        return []

    def count_appliance_month(self, appliance: str, year_month: str) -> dict:
        """Conta cicli e durata totale di un elettrodomestico nel mese."""
        try:
            with self._conn() as conn:
                row = conn.execute("""
                    SELECT COUNT(*) as count,
                           SUM(duration_min) as total_min,
                           AVG(duration_min) as avg_min
                    FROM appliance_cycles
                    WHERE appliance LIKE ? AND date LIKE ?
                """, (f"%{appliance}%", f"{year_month}-%")).fetchone()
                if row:
                    return {
                        "count":     row["count"] or 0,
                        "total_min": int(row["total_min"] or 0),
                        "avg_min":   int(row["avg_min"] or 0),
                    }
        except Exception as e:
            logger.warning("HomeMindDB count_appliance_month: %s", e)
        return {"count": 0, "total_min": 0, "avg_min": 0}

    # ─────────────────────────────────────────────────────────────────────────
    # SOSTE GPS PERSONE

    async def save_person_stops(self, person: str, date_str: str, stops: list):
        """Salva soste GPS della giornata per una persona.
        Deduplica: per la stessa finestra oraria (±10 min) tiene solo
        la versione con indirizzo reale, scartando le coordinate grezze."""
        import re as _re_coord
        _coord_re = _re_coord.compile(r"^\(\d+\.\d+,\s*\d+\.\d+\)$")

        def _is_coord(addr):
            return bool(_coord_re.match(addr or ""))

        def _time_window(stop):
            """Finestra oraria arrotondata a 10 min per deduplicazione."""
            return stop.get("h_start", 0) * 6 + stop.get("m_start", 0) // 10

        # Deduplicazione: per ogni finestra oraria tieni solo indirizzo reale
        deduped = {}
        for stop in stops:
            addr = stop.get("addr") or stop.get("address", "")
            if addr == "🏠 Casa":
                continue  # le soste a casa non servono (is_home=1 già filtrato)
            win = _time_window(stop)
            existing = deduped.get(win)
            if existing is None:
                deduped[win] = stop
            else:
                existing_addr = existing.get("addr") or existing.get("address", "")
                # Preferisci indirizzo reale rispetto a coordinate grezze
                if _is_coord(existing_addr) and not _is_coord(addr):
                    deduped[win] = stop  # sostituisci coordinate con indirizzo reale

        async with self._lock:
            try:
                with self._conn() as conn:
                    # Elimina soste già salvate per questo giorno (riscrittura)
                    conn.execute(
                        "DELETE FROM person_stops WHERE person = ? AND date = ?",
                        (person, date_str)
                    )
                    for stop in sorted(deduped.values(),
                                       key=lambda s: (s.get("h_start",0), s.get("m_start",0))):
                        addr = stop.get("addr") or stop.get("address", "")
                        conn.execute("""
                            INSERT INTO person_stops
                            (person, date, address, lat, lon,
                             start_time, end_time, duration_min, is_home, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            person, date_str, addr,
                            stop.get("lat"), stop.get("lon"),
                            f"{stop.get('h_start',0):02d}:{stop.get('m_start',0):02d}",
                            f"{stop.get('h_end',0):02d}:{stop.get('m_end',0):02d}",
                            stop.get("dur") or stop.get("duration_min", 0),
                            0,  # is_home sempre 0 (Casa già filtrata sopra)
                            int(time.time()),
                        ))
                logger.debug("HomeMindDB: %d soste deduplicate %s @ %s",
                             len(deduped), person, date_str)
            except Exception as e:
                logger.warning("HomeMindDB save_person_stops: %s", e)

    def query_person_day(self, person: str, date_str: str) -> list:
        """Dove era una persona in un giorno specifico.
        Filtra automaticamente le coordinate grezze se esiste già
        una versione con indirizzo reale nella stessa finestra oraria."""
        import re as _re_q
        _coord_re_q = _re_q.compile(r"^\(\d+\.\d+,\s*\d+\.\d+\)$")

        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT address, start_time, end_time, duration_min
                    FROM person_stops
                    WHERE person = ? AND date = ? AND is_home = 0
                    ORDER BY start_time
                """, (person, date_str)).fetchall()
                raw = [dict(r) for r in rows]

            # Deduplicazione in lettura: raggruppa per finestra oraria (±10 min)
            # e preferisci indirizzo reale rispetto a coordinate grezze
            seen = {}
            for row in raw:
                t = row.get("start_time", "00:00")
                try:
                    h, m = int(t[:2]), int(t[3:5])
                except Exception:
                    h, m = 0, 0
                win = h * 6 + m // 10
                addr = row.get("address", "")
                existing = seen.get(win)
                if existing is None:
                    seen[win] = row
                else:
                    ex_addr = existing.get("address", "")
                    # Sostituisci coordinate con indirizzo reale
                    if bool(_coord_re_q.match(ex_addr)) and not bool(_coord_re_q.match(addr)):
                        seen[win] = row

            return sorted(seen.values(), key=lambda r: r.get("start_time", ""))
        except Exception as e:
            logger.warning("HomeMindDB query_person_day: %s", e)
        return []

    def query_person_frequent_places(self, person: str, limit: int = 10) -> list:
        """Luoghi più frequentati da una persona (aggregato)."""
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT address,
                           COUNT(*) as visit_count,
                           SUM(duration_min) as total_min,
                           AVG(duration_min) as avg_min,
                           MAX(date) as last_seen,
                           MIN(date) as first_seen
                    FROM person_stops
                    WHERE person = ? AND is_home = 0
                      AND address IS NOT NULL AND address != ''
                    GROUP BY address
                    ORDER BY visit_count DESC
                    LIMIT ?
                """, (person, limit)).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("HomeMindDB query_person_frequent: %s", e)
        return []

    # ─────────────────────────────────────────────────────────────────────────
    # QUERY LINGUAGGIO NATURALE (helper per AI)

    def natural_query_energy(self, question: str) -> Optional[str]:
        """Prova a rispondere a domande energetiche dal DB senza AI.
        Es: '1 aprile', 'aprile 2026', 'ieri', 'questa settimana'"""
        import re
        now = now_local()
        q = question.lower()

        # Ieri
        if "ieri" in q:
            d = (now.date() - timedelta(days=1)).isoformat()
            return self._format_energy_day(d)

        # Oggi
        if "oggi" in q:
            return self._format_energy_day(now.date().isoformat())

        # "il 1 aprile" / "1 aprile 2026" / "aprile 2026"
        MONTHS = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,
                  "giugno":6,"luglio":7,"agosto":8,"settembre":9,
                  "ottobre":10,"novembre":11,"dicembre":12}
        m_month = re.search(
            r"(\d{1,2})?\s*(" + "|".join(MONTHS.keys()) + r")\s*(\d{4})?", q
        )
        if m_month:
            day_n   = int(m_month.group(1)) if m_month.group(1) else None
            month_n = MONTHS[m_month.group(2)]
            year_n  = int(m_month.group(3)) if m_month.group(3) else now.year
            if day_n:
                try:
                    d = date(year_n, month_n, day_n).isoformat()
                    return self._format_energy_day(d)
                except ValueError:
                    pass
            else:
                ym = f"{year_n}-{month_n:02d}"
                return self._format_energy_month(ym)

        # "questa settimana"
        if "settimana" in q:
            monday = now.date() - timedelta(days=now.weekday())
            rows = self.query_energy_range(monday.isoformat(), now.date().isoformat())
            if rows:
                total = sum(r["solar_kwh"] or 0 for r in rows)
                return f"⚡ Questa settimana: {total:.1f} kWh prodotti FV ({len(rows)} giorni)"

        return None

    def _format_energy_day(self, date_str: str) -> Optional[str]:
        row = self.query_energy_day(date_str)
        if not row:
            return None

        # Leggi colonne dedicate; se None (righe salvate prima del fix),
        # prova a recuperare dal raw_json con tutte le varianti di chiave
        def _pick_raw(raw: dict, *keys):
            for k in keys:
                v = raw.get(k)
                if v is not None:
                    return v
            return None

        raw = row.get("raw") or {}
        solar    = row.get("solar_kwh")    if row.get("solar_kwh")    is not None else _pick_raw(raw, "produzione_fv", "solar", "fotovoltaico", "fv", "pv")
        consume  = row.get("consume_kwh")  if row.get("consume_kwh")  is not None else _pick_raw(raw, "consumo_casa", "consume", "consumo", "casa")
        grid_in  = row.get("grid_in_kwh")  if row.get("grid_in_kwh")  is not None else _pick_raw(raw, "rete_enel", "grid_in", "importazione_rete", "enel")
        grid_out = row.get("grid_out_kwh") if row.get("grid_out_kwh") is not None else _pick_raw(raw, "esportazione_rete", "grid_out", "export")

        parts = [f"⚡ <b>Energia {date_str}</b>"]
        if solar is not None:
            parts.append(f"☀️ FV prodotto: <b>{float(solar):.1f} kWh</b>")
        if consume is not None:
            parts.append(f"🏠 Consumo casa: <b>{float(consume):.1f} kWh</b>")
        if grid_in is not None:
            parts.append(f"🔌 Importata rete: {float(grid_in):.1f} kWh")
        if grid_out is not None:
            parts.append(f"📤 Esportata: {float(grid_out):.1f} kWh")
        if solar is not None and consume is not None:
            auto = round(min(float(solar), float(consume)), 1)
            parts.append(f"⚡ Autoconsumo stimato: {auto:.1f} kWh")
        if len(parts) == 1:
            # Nessun dato numerico trovato neanche nel raw_json
            parts.append(f"⚠️ Dati non ancora disponibili per {date_str}")
        return "\n".join(parts)

    def _format_energy_month(self, year_month: str) -> Optional[str]:
        data = self.query_energy_month(year_month)
        if not data:
            return None
        note = " *(stima)*" if data.get("computed") else ""
        parts = [f"⚡ <b>Energia {year_month}</b>{note}"]
        if data.get("solar_total") is not None:
            parts.append(f"☀️ FV totale: <b>{data['solar_total']:.1f} kWh</b>")
            parts.append(f"  Media/giorno: {data.get('solar_avg_day',0):.1f} kWh")
            if data.get("solar_max_date"):
                parts.append(f"  Giornata record: {data['solar_max_day']:.1f} kWh ({data['solar_max_date']})")
        if data.get("consume_total"):
            parts.append(f"🏠 Consumo totale: {data['consume_total']:.1f} kWh")
        parts.append(f"📅 Giorni registrati: {data.get('days_count',0)}")
        return "\n".join(parts)

    def get_known_persons(self) -> list:
        """Restituisce lista nomi distinti delle persone nel DB GPS."""
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT DISTINCT person FROM person_stops ORDER BY person"
                ).fetchall()
                return [r["person"] for r in rows]
        except Exception as e:
            logger.warning("HomeMindDB get_known_persons: %s", e)
        return []

    def natural_query_person(self, person: str, question: str) -> Optional[str]:
        """Dove era una persona? Risponde dal DB."""
        import re
        now = now_local()
        q = question.lower()

        DAYS_IT = ["lunedì","martedì","mercoledì","giovedì","venerdì","sabato","domenica"]

        # Ieri
        if "ieri" in q:
            d = (now.date() - timedelta(days=1)).isoformat()
            return self._format_person_day(person, d)

        # Giorno della settimana ("giovedì scorso")
        for i, day_name in enumerate(DAYS_IT):
            if day_name in q:
                days_back = (now.weekday() - i) % 7 or 7
                d = (now.date() - timedelta(days=days_back)).isoformat()
                return self._format_person_day(person, d)

        # Data esplicita "il 1 aprile"
        MONTHS = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,
                  "giugno":6,"luglio":7,"agosto":8,"settembre":9,
                  "ottobre":10,"novembre":11,"dicembre":12}
        m = re.search(r"(\d{1,2})\s*(" + "|".join(MONTHS.keys()) + r")\s*(\d{4})?", q)
        if m:
            try:
                d = date(int(m.group(3) or now.year), MONTHS[m.group(2)], int(m.group(1))).isoformat()
                return self._format_person_day(person, d)
            except ValueError:
                pass

        # Luoghi frequenti
        if any(w in q for w in ("frequen", "spesso", "solito", "sempre")):
            return self._format_frequent_places(person)

        return None

    def _format_person_day(self, person: str, date_str: str) -> Optional[str]:
        stops = self.query_person_day(person, date_str)
        if not stops:
            return None
        lines = [f"📍 <b>{person.capitalize()} — {date_str}</b>\n"]
        for s in stops:
            dur = s.get("duration_min", 0)
            dur_str = f"{dur//60}h {dur%60}m" if dur >= 60 else f"{dur}m"
            lines.append(
                f"• <b>{s['address']}</b>\n"
                f"  {s['start_time']} → {s['end_time']} ({dur_str})"
            )
        return "\n".join(lines)

    def _format_frequent_places(self, person: str) -> Optional[str]:
        places = self.query_person_frequent_places(person, limit=8)
        if not places:
            return None
        lines = [f"📍 <b>Luoghi frequenti di {person.capitalize()}</b>\n"]
        for i, p in enumerate(places, 1):
            tot = p.get("total_min", 0)
            tot_str = f"{tot//60}h" if tot >= 60 else f"{tot}m"
            lines.append(
                f"{i}. <b>{p['address']}</b> — "
                f"{p['visit_count']}x, {tot_str} totali"
            )
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # QUERY LINGUAGGIO NATURALE — ELETTRODOMESTICI

    def get_known_appliances(self) -> list:
        """Restituisce lista nomi distinti degli elettrodomestici nel DB."""
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT DISTINCT appliance FROM appliance_cycles ORDER BY appliance"
                ).fetchall()
                return [r["appliance"] for r in rows]
        except Exception as e:
            logger.warning("HomeMindDB get_known_appliances: %s", e)
        return []

    def get_cycles_for_fix(self, appliance: str = None, limit: int = 20) -> list:
        """Restituisce cicli recenti con id, per il menu /db_fix."""
        try:
            cond  = "WHERE appliance LIKE ?" if appliance else ""
            param = [f"%{appliance}%"] if appliance else []
            param.append(limit)
            with self._conn() as conn:
                rows = conn.execute(f"""
                    SELECT id, appliance, start_time, end_time, duration_min, kwh
                    FROM appliance_cycles
                    {cond}
                    ORDER BY start_time DESC
                    LIMIT ?
                """, param).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("HomeMindDB get_cycles_for_fix: %s", e)
        return []

    def delete_cycle_by_id(self, cycle_id: int) -> bool:
        """Cancella un singolo ciclo per ID. Ritorna True se cancellato."""
        try:
            with self._conn() as conn:
                cur = conn.execute("DELETE FROM appliance_cycles WHERE id = ?", (cycle_id,))
                return cur.rowcount > 0
        except Exception as e:
            logger.warning("HomeMindDB delete_cycle_by_id: %s", e)
        return False

    def delete_cycles_filter(self, appliance: str = None,
                              max_duration_min: int = None,
                              date: str = None) -> int:
        """Cancella cicli per filtro. Ritorna numero righe cancellate."""
        try:
            conds, params = [], []
            if appliance:
                conds.append("appliance LIKE ?"); params.append(f"%{appliance}%")
            if max_duration_min is not None:
                conds.append("duration_min <= ?"); params.append(max_duration_min)
            if date:
                conds.append("date = ?"); params.append(date)
            if not conds:
                return 0
            where = "WHERE " + " AND ".join(conds)
            with self._conn() as conn:
                cur = conn.execute(f"DELETE FROM appliance_cycles {where}", params)
                return cur.rowcount
        except Exception as e:
            logger.warning("HomeMindDB delete_cycles_filter: %s", e)
        return 0

    def natural_query_appliance(self, question: str) -> Optional[str]:
        """Prova a rispondere a domande su cicli elettrodomestici dal DB senza AI.
        Es: 'cicli lavatrice', 'lavatrice cicli oggi', 'lavastoviglie ieri',
            'quante volte lavatrice questo mese', 'ultime 5 lavate',
            'lavatrice lunedì', 'cicli lavatrice aprile 2026'
        """
        import re
        now = now_local()
        q = question.lower()

        # Nomi elettrodomestici noti: DB + alias comuni hardcoded come fallback
        _STATIC_ALIASES = {
            "lavatrice":     ["lavatrice", "lavabiancheria", "lavat"],
            "lavastoviglie": ["lavastoviglie", "stoviglie", "piatti"],
            "asciugatrice":  ["asciugatrice", "asciugat"],
            "forno":         ["forno"],
            "scaldabagno":   ["scaldabagno", "boiler", "scalda"],
        }
        # Carica nomi reali dal DB (dinamici, include qualsiasi futuro elettrodomestico)
        db_appliances = self.get_known_appliances()  # es. ["Lavatrice", "Lavastoviglie Vario speed +"]

        MONTHS = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,
                  "giugno":6,"luglio":7,"agosto":8,"settembre":9,
                  "ottobre":10,"novembre":11,"dicembre":12}
        DAYS_IT = ["lunedì","martedì","mercoledì","giovedì","venerdì","sabato","domenica"]

        # Identifica elettrodomestico nella domanda
        # Prima cerca match esatto/parziale nei nomi reali del DB
        target_appliance = None
        for db_name in db_appliances:
            if db_name.lower() in q or q in db_name.lower():
                target_appliance = db_name  # usa il nome esatto del DB
                break
            # Match parziale: ogni parola del nome DB nella domanda
            words = [w for w in db_name.lower().split() if len(w) > 3]
            if words and all(w in q for w in words):
                target_appliance = db_name
                break
            # Match prima parola significativa (es. "Lavatrice" da "Lavatrice Vario")
            first_word = db_name.lower().split()[0] if db_name else ""
            if len(first_word) > 4 and first_word in q:
                if target_appliance is None:  # non sovrascrivere match migliore
                    target_appliance = db_name
        # Fallback: alias statici (utile se il DB è vuoto o l'elettrodomestico non ha ancora cicli)
        if not target_appliance:
            for name, aliases in _STATIC_ALIASES.items():
                if any(alias in q for alias in aliases):
                    target_appliance = name
                    break

        # ── 1. "ultime N" / "ultimi N cicli" ──────────────────────────────
        m_limit = re.search(r"ultim[ie]\s+(\d+)", q)
        if m_limit or any(w in q for w in ("ultimi cicli","ultimi lavaggi","ultime lavate",
                                            "ultime lavat","ultimi utilizzi")):
            limit = int(m_limit.group(1)) if m_limit else 5
            cycles = self.query_appliance_cycles(appliance=target_appliance, limit=limit)
            if not cycles:
                return None
            return self._format_appliance_cycles(cycles, target_appliance,
                                                  date_label=f"ultimi {len(cycles)}")

        # ── 2. Oggi ────────────────────────────────────────────────────────
        if "oggi" in q or "stamattina" in q or "stamani" in q:
            d = now.date().isoformat()
            cycles = self.query_appliance_cycles(
                appliance=target_appliance, from_date=d, to_date=d, limit=20)
            if cycles is None:
                return None
            return self._format_appliance_cycles(cycles, target_appliance, date_label="oggi")

        # ── 3. Ieri ────────────────────────────────────────────────────────
        if "ieri" in q or "ieri sera" in q or "ieri mattina" in q:
            d = (now.date() - timedelta(days=1)).isoformat()
            cycles = self.query_appliance_cycles(
                appliance=target_appliance, from_date=d, to_date=d, limit=20)
            if cycles is None:
                return None
            return self._format_appliance_cycles(cycles, target_appliance, date_label="ieri")

        # ── 4. Tutti i giorni della settimana (lunedì…domenica) ───────────
        for i, day_name in enumerate(DAYS_IT):
            if day_name in q:
                days_back = (now.weekday() - i) % 7
                # Se chiede "lunedì" e oggi è lunedì → oggi; altrimenti scorso
                if days_back == 0 and "scorso" not in q and "scorsa" not in q:
                    days_back = 0   # oggi
                elif days_back == 0:
                    days_back = 7   # lunedì scorso
                d = (now.date() - timedelta(days=days_back)).isoformat()
                cycles = self.query_appliance_cycles(
                    appliance=target_appliance, from_date=d, to_date=d, limit=20)
                if cycles is None:
                    return None
                return self._format_appliance_cycles(cycles, target_appliance,
                                                      date_label=f"{day_name} ({d})")

        # ── 5. Questa settimana ────────────────────────────────────────────
        if "settimana" in q and "scorsa" not in q and "passata" not in q:
            monday = now.date() - timedelta(days=now.weekday())
            cycles = self.query_appliance_cycles(
                appliance=target_appliance,
                from_date=monday.isoformat(), to_date=now.date().isoformat(), limit=30)
            if cycles is None:
                return None
            return self._format_appliance_cycles(cycles, target_appliance,
                                                  date_label="questa settimana")

        if "settimana scorsa" in q or "settimana passata" in q:
            monday = now.date() - timedelta(days=now.weekday() + 7)
            sunday = monday + timedelta(days=6)
            cycles = self.query_appliance_cycles(
                appliance=target_appliance,
                from_date=monday.isoformat(), to_date=sunday.isoformat(), limit=30)
            if cycles is None:
                return None
            return self._format_appliance_cycles(cycles, target_appliance,
                                                  date_label="settimana scorsa")

        # ── 6. Mese specifico ("aprile", "aprile 2026") ───────────────────
        year_month = None
        m_month = re.search(r"(" + "|".join(MONTHS.keys()) + r")\s*(\d{4})?", q)
        if m_month:
            month_n = MONTHS[m_month.group(1)]
            year_n  = int(m_month.group(2)) if m_month.group(2) else now.year
            year_month = f"{year_n}-{month_n:02d}"
        elif any(w in q for w in ("questo mese", "mese corrente", "mese attuale")):
            year_month = now.strftime("%Y-%m")
        elif any(w in q for w in ("mese scorso", "scorso mese", "mese precedente", "mese passato")):
            first = now.date().replace(day=1)
            year_month = (first - timedelta(days=1)).strftime("%Y-%m")

        if year_month:
            if not target_appliance:
                return self._format_all_appliances_month(year_month)
            stats = self.count_appliance_month(target_appliance, year_month)
            if stats["count"] == 0:
                return None
            avg_str = f"{stats['avg_min']} min" if stats['avg_min'] else "n/d"
            tot_h   = stats['total_min'] // 60
            tot_m   = stats['total_min'] % 60
            tot_str = f"{tot_h}h {tot_m}m" if tot_h else f"{tot_m}m"
            # Mostra anche lista cicli del mese
            from_d = f"{year_month}-01"
            import calendar
            last_day = calendar.monthrange(int(year_month[:4]), int(year_month[5:]))[1]
            to_d = f"{year_month}-{last_day:02d}"
            cycles = self.query_appliance_cycles(
                appliance=target_appliance, from_date=from_d, to_date=to_d, limit=50)
            summary = (
                f"🫧 <b>{target_appliance.capitalize()} — {year_month}</b>\n"
                f"🔢 Cicli: <b>{stats['count']}</b>\n"
                f"⏱️ Durata totale: {tot_str}\n"
                f"📊 Media ciclo: {avg_str}"
            )
            if cycles and len(cycles) <= 10:
                detail = self._format_appliance_cycles(cycles, target_appliance)
                return f"{summary}\n\n{detail}" if detail else summary
            return summary

        # ── 7. Fallback senza data: mese corrente + ultimi cicli ──────────
        #    Es: "cicli lavatrice", "lavatrice cicli", "storico lavatrice"
        if target_appliance:
            ym = now.strftime("%Y-%m")
            stats = self.count_appliance_month(target_appliance, ym)
            cycles = self.query_appliance_cycles(appliance=target_appliance, limit=10)
            if not cycles and stats["count"] == 0:
                return None   # Nessun dato → lascia passare all'AI
            lines = [f"🫧 <b>{target_appliance.capitalize()} — storico</b>\n"]
            if stats["count"] > 0:
                tot_h = stats['total_min'] // 60
                tot_m = stats['total_min'] % 60
                tot_str = f"{tot_h}h {tot_m}m" if tot_h else f"{tot_m}m"
                lines.append(f"📅 Questo mese ({ym}): <b>{stats['count']} cicli</b> · {tot_str} totali")
            if cycles:
                lines.append("")
                lines.append(f"🕐 Ultimi {len(cycles)} cicli:")
                for c in cycles:
                    start = c.get("start_time", "?")[:16].replace("T", " ")
                    end   = c.get("end_time", "")
                    end_s = end[:16].replace("T", " ") if end else "in corso"
                    dur   = c.get("duration_min", 0) or 0
                    dur_s = f"{dur//60}h {dur%60}m" if dur >= 60 else f"{dur}m"
                    kwh   = c.get("kwh")
                    kwh_s = f" · {kwh:.2f} kWh" if kwh else ""
                    lines.append(f"• {start} → {end_s} ({dur_s}){kwh_s}")
            return "\n".join(lines)

        # Nessun elettrodomestico identificato → None = passa all'AI
        return None


    def _format_appliance_cycles(self, cycles: list, appliance: str = None,
                                  date_label: str = None) -> Optional[str]:
        """Formatta lista cicli per Telegram."""
        if not cycles:
            who = appliance.capitalize() if appliance else "Elettrodomestici"
            when = f" — {date_label}" if date_label else ""
            return f"🫧 <b>{who}{when}</b>\nNessun ciclo trovato nel DB."
        who = appliance.capitalize() if appliance else "Cicli"
        when = f" — {date_label}" if date_label else f" — ultimi {len(cycles)}"
        lines = [f"🫧 <b>{who}{when}</b>\n"]
        for c in cycles:
            name = c.get("appliance", who)
            start = c.get("start_time", "?")[:16].replace("T", " ")
            end   = c.get("end_time", "")
            end_s = end[:16].replace("T", " ") if end else "in corso"
            dur   = c.get("duration_min", 0) or 0
            dur_s = f"{dur//60}h {dur%60}m" if dur >= 60 else f"{dur}m"
            kwh   = c.get("kwh")
            kwh_s = f" · {kwh:.2f} kWh" if kwh else ""
            lines.append(f"• <b>{name}</b> {start} → {end_s} ({dur_s}){kwh_s}")
        return "\n".join(lines)

    def _format_all_appliances_month(self, year_month: str) -> Optional[str]:
        """Conta cicli di tutti gli elettrodomestici in un mese."""
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT appliance, COUNT(*) as count,
                           SUM(duration_min) as total_min
                    FROM appliance_cycles
                    WHERE date LIKE ?
                    GROUP BY appliance
                    ORDER BY count DESC
                """, (f"{year_month}-%",)).fetchall()
            if not rows:
                return None
            lines = [f"🫧 <b>Cicli elettrodomestici — {year_month}</b>\n"]
            for r in rows:
                tot = int(r["total_min"] or 0)
                tot_s = f"{tot//60}h {tot%60}m" if tot >= 60 else f"{tot}m"
                lines.append(f"• <b>{r['appliance']}</b>: {r['count']} cicli · {tot_s}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("HomeMindDB _format_all_appliances_month: %s", e)
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # MANUTENZIONE

    async def run_monthly_maintenance(self):
        """Da chiamare il primo del mese: comprime il mese precedente."""
        now = now_local()
        if now.day != 1:
            return
        last_month = (now.date().replace(day=1) - timedelta(days=1))
        ym = last_month.strftime("%Y-%m")
        logger.info("HomeMindDB: compressione mese %s", ym)
        await self.compress_month(ym)

    def get_stats(self) -> str:
        """Statistiche DB per debug."""
        try:
            with self._conn() as conn:
                e = conn.execute("SELECT COUNT(*) as n, MIN(date) as from_, MAX(date) as to_ FROM energy_daily").fetchone()
                a = conn.execute("SELECT COUNT(*) as n FROM appliance_cycles").fetchone()
                p = conn.execute("SELECT COUNT(*) as n, COUNT(DISTINCT person) as persons FROM person_stops").fetchone()
                size_kb = DB_PATH.stat().st_size // 1024 if DB_PATH.exists() else 0
                return (
                    f"🗄️ <b>HomeMind DB</b> ({size_kb} KB)\n"
                    f"⚡ Energia: {e['n']} giorni ({e['from_']} → {e['to_']})\n"
                    f"🫧 Cicli: {a['n']} elettrodomestici\n"
                    f"📍 Soste: {p['n']} ({p['persons']} persone)"
                )
        except Exception as ex:
            return f"🗄️ DB error: {ex}"
