"""
agent/routine_manager.py — Smart Daily Routine Manager.

Impara la routine reale dell'utente dai dati HA e agisce proattivamente.

Come funziona:
  1. Ogni giorno alle 23:45 analizza i log di movimento/presenza e salva
     i pattern rilevati (orari uscita, rientro, attività per stanza)
  2. Durante la giornata confronta i pattern attesi con quello che succede
  3. Anticipa i bisogni:
     - Rileva che stai per uscire → chiede se preparare la casa
     - Stai rientrando → pre-riscalda, avvisa
     - Anomalia rispetto alla routine → notifica discreta
  4. Nel briefing mattutino aggiunge suggerimenti personalizzati sulla routine

Salvataggio: /data/homemind_routine.json
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

logger = logging.getLogger("homemind.routine")

ROUTINE_PATH = Path("/data/homemind_routine.json")
MIN_DAYS     = 3   # giorni minimi per iniziare a fare previsioni


class RoutineManager:
    def __init__(self, home=None, notifier=None, rest_client=None,
                 state_cache_cb=None, ai=None, security_manager=None):
        self.home       = home
        self.notifier   = notifier
        self.rest       = rest_client
        self._cache_cb  = state_cache_cb
        self.ai         = ai
        self.security   = security_manager

        self._patterns: dict = {}      # pattern appresi
        self._today_events: list = []  # eventi di oggi
        self._last_suggestion_ts = 0.0 # anti-spam suggerimenti
        self._pending_action: Optional[str] = None  # azione in attesa conferma
        self._task: Optional[asyncio.Task] = None
        self._load()

    @property
    def _cache(self) -> dict:
        return self._cache_cb() if self._cache_cb else {}

    # ─────────────────────────────────────────────────────────────────────────
    # Persistenza

    def _load(self):
        try:
            if ROUTINE_PATH.exists():
                data = json.loads(ROUTINE_PATH.read_text())
                self._patterns = data.get("patterns", {})
                logger.info("RoutineManager: caricati pattern per %d giorni di storico",
                            len(self._patterns.get("departure_times", [])))
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
    # Avvio

    async def start(self):
        self._task = asyncio.create_task(self._main_loop(), name="routine_manager")
        logger.info("RoutineManager avviato — monitoro routine e anticipo bisogni")

    # ─────────────────────────────────────────────────────────────────────────
    # Loop principale

    async def _main_loop(self):
        await asyncio.sleep(60)  # delay iniziale
        while True:
            try:
                now = now_local()

                # Ogni notte alle 23:45 → aggiorna pattern dal giorno
                if now.hour == 23 and now.minute == 45:
                    await self._update_patterns_from_today()
                    await asyncio.sleep(60)

                # Durante il giorno → controlla anomalie e anticipa
                await self._proactive_check()

            except Exception as e:
                logger.warning("RoutineManager loop error: %s", e)

            await asyncio.sleep(120)  # check ogni 2 minuti

    # ─────────────────────────────────────────────────────────────────────────
    # Apprendimento pattern

    async def _update_patterns_from_today(self):
        """Analizza gli eventi di oggi e aggiorna i pattern."""
        if not self.home:
            return

        now = now_local()
        today_str = now.strftime("%A").lower()  # lunedi, martedi ecc.

        # Leggi storia presence di oggi dalle persone
        patterns = self._patterns

        # Inizializza struttura se vuota
        if "departure_times" not in patterns:
            patterns["departure_times"] = []
        if "arrival_times" not in patterns:
            patterns["arrival_times"] = []
        if "kitchen_morning" not in patterns:
            patterns["kitchen_morning"] = []
        if "days_learned" not in patterns:
            patterns["days_learned"] = 0

        # Aggiungi eventi di oggi
        for event in self._today_events:
            etype = event.get("type")
            hour  = event.get("hour")
            minute = event.get("minute", 0)
            if etype == "departure" and hour is not None:
                patterns["departure_times"].append(hour + minute/60)
                patterns["departure_times"] = patterns["departure_times"][-30:]  # ultimi 30
            elif etype == "arrival" and hour is not None:
                patterns["arrival_times"].append(hour + minute/60)
                patterns["arrival_times"] = patterns["arrival_times"][-30:]
            elif etype == "kitchen_morning" and hour is not None:
                patterns["kitchen_morning"].append(hour + minute/60)
                patterns["kitchen_morning"] = patterns["kitchen_morning"][-30:]

        patterns["days_learned"] = patterns.get("days_learned", 0) + 1
        self._today_events = []
        self._patterns = patterns
        self._save()
        logger.info("RoutineManager: pattern aggiornati (giorno %d)",
                    patterns["days_learned"])

    def record_event(self, event_type: str, person: str = "", zone: str = ""):
        """Registra un evento per l'apprendimento. Chiamato da security_manager."""
        now = now_local()
        self._today_events.append({
            "type":   event_type,
            "person": person,
            "zone":   zone,
            "hour":   now.hour,
            "minute": now.minute,
            "ts":     time.time()
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Controllo proattivo

    async def _proactive_check(self):
        """Controlla se c'è qualcosa da anticipare o segnalare."""
        if not self.home:
            return

        now  = now_local()
        hour = now.hour

        # Solo nelle ore attive (6:00-23:00)
        if not (6 <= hour <= 23):
            return

        # Anti-spam: max 1 suggerimento ogni 30 minuti
        if time.time() - self._last_suggestion_ts < 1800:
            return

        # Non disturbare se casa vuota o allarme armato
        _, alarm_st = self.home.primary_alarm()
        if alarm_st in ("armed_away", "arming"):
            return

        days_learned = self._patterns.get("days_learned", 0)
        if days_learned < MIN_DAYS:
            return

        # ── Controlla partenza imminente ─────────────────────────────────────
        await self._check_departure_prediction()

    async def _check_departure_prediction(self):
        """Se c'è movimento in cucina di mattina vicino all'orario solito di uscita,
        suggerisci di preparare la casa."""
        now  = now_local()
        hour = now.hour + now.minute / 60

        # Solo mattina (6-10)
        if not (6 <= now.hour <= 10):
            return

        departure_times = self._patterns.get("departure_times", [])
        if len(departure_times) < MIN_DAYS:
            return

        # Calcola orario medio di partenza
        avg_departure = sum(departure_times) / len(departure_times)
        avg_h = int(avg_departure)
        avg_m = int((avg_departure - avg_h) * 60)

        # Siamo entro 30 minuti dall'orario tipico di partenza?
        diff_min = (avg_departure - hour) * 60
        if not (5 <= diff_min <= 30):
            return

        # C'è movimento in cucina?
        kitchen_active = any(
            v["state"] == "on" and "cucina" in v.get("zone", "").lower()
            for v in self.home.motion_sensors.values()
        )
        if not kitchen_active:
            return

        # Tutti ancora a casa?
        if not self.home.everyone_away() is False:
            return
        if not self.home.who_is_home():
            return

        # Manda suggerimento
        self._last_suggestion_ts = time.time()
        self._pending_action = "prepare_departure"

        msg = (
            f"🏃 Di solito esci intorno alle {avg_h:02d}:{avg_m:02d} — "
            f"mancano circa {int(diff_min)} minuti.\n\n"
            f"Vuoi che preparo la casa?\n"
            f"(abbasso riscaldamento + spengo le luci)\n\n"
            f"Rispondi <b>sì</b> per confermare"
        )

        logger.info("RoutineManager: suggerisco preparazione partenza (media %02d:%02d, diff %.0fmin)",
                    avg_h, avg_m, diff_min)

        if self.notifier:
            await self.notifier.send_html(msg)

    # ─────────────────────────────────────────────────────────────────────────
    # Gestione conferme Telegram

    async def handle_confirm(self, text: str) -> bool:
        """Gestisce la risposta dell'utente a un suggerimento. Ritorna True se gestito."""
        if not self._pending_action:
            return False

        # Timeout 10 minuti
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

        # Esegui azione
        if action == "prepare_departure":
            await self._execute_prepare_departure()

        return True

    async def _execute_prepare_departure(self):
        """Prepara la casa per la partenza."""
        done = []

        # 1. Abbassa riscaldamento
        if self.rest and self.home:
            for eid in self.home.climate:
                try:
                    await self.rest.call_service(
                        "climate", "set_temperature", {"temperature": 18},
                        target={"entity_id": eid}
                    )
                    done.append("🌡️ Riscaldamento abbassato a 18°")
                except Exception:
                    pass

        # 2. Spegni luci
        if self.rest and self.home:
            lights = self.home.lights_on()
            if lights:
                try:
                    await self.rest.call_service(
                        "light", "turn_off", {},
                        target={"entity_id": lights}
                    )
                    done.append(f"💡 Spente {len(lights)} luci")
                except Exception:
                    pass

        msg = "✅ Fatto!\n" + "\n".join(done) if done else "✅ Già tutto a posto!"
        msg += "\n\n🚪 Buona giornata!"

        logger.info("RoutineManager: partenza preparata — %s", done)
        if self.notifier:
            await self.notifier.send_html(msg)

    # ─────────────────────────────────────────────────────────────────────────
    # Info per briefing

    def get_routine_summary(self) -> str:
        """Restituisce un riepilogo della routine per il briefing mattutino."""
        days = self._patterns.get("days_learned", 0)
        if days < MIN_DAYS:
            return ""

        dep = self._patterns.get("departure_times", [])
        arr = self._patterns.get("arrival_times", [])

        lines = ["📅 <b>La tua routine</b>"]

        if dep:
            avg_dep = sum(dep) / len(dep)
            h, m = int(avg_dep), int((avg_dep % 1) * 60)
            lines.append(f"  🚗 Di solito esci verso le {h:02d}:{m:02d}")

        if arr:
            avg_arr = sum(arr) / len(arr)
            h, m = int(avg_arr), int((avg_arr % 1) * 60)
            lines.append(f"  🏠 Di solito rientri verso le {h:02d}:{m:02d}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def get_status(self) -> str:
        """Stato per comando /routine."""
        days = self._patterns.get("days_learned", 0)
        dep  = self._patterns.get("departure_times", [])
        arr  = self._patterns.get("arrival_times", [])

        if days < MIN_DAYS:
            return (f"📅 <b>Routine Manager</b>\n\n"
                    f"⏳ Sto imparando la tua routine...\n"
                    f"Ho bisogno di almeno {MIN_DAYS} giorni di dati.\n"
                    f"Giorni osservati: <b>{days}/{MIN_DAYS}</b>")

        lines = [f"📅 <b>Routine appresa</b> ({days} giorni osservati)\n"]

        if dep:
            avg = sum(dep)/len(dep)
            h, m = int(avg), int((avg % 1)*60)
            lines.append(f"🚗 Uscita tipica: <b>{h:02d}:{m:02d}</b>")

        if arr:
            avg = sum(arr)/len(arr)
            h, m = int(avg), int((avg % 1)*60)
            lines.append(f"🏠 Rientro tipico: <b>{h:02d}:{m:02d}</b>")

        lines.append("\n<i>HomeMind ti avviserà 10-30 min prima dell'orario tipico "
                     "se rileva movimento in cucina.</i>")
        return "\n".join(lines)
