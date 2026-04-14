"""
agent/recurring_task_scheduler.py — Task Ripetuti per HomeMind.

Permette di schedulare azioni che si ripetono ogni giorno (o ogni settimana)
alla stessa ora, finché l'utente non le cancella esplicitamente.

Esempi:
  "ogni giorno alle 19 accendi la luce soggiorno"
  "ogni mattina alle 7:30 imposta termostato 21 gradi"
  "tutti i giorni alle 23 spegni le luci"
  "ogni lunedì alle 9 accendi la presa lavatrice"
  "every day at 8pm turn on the garden lights"

Come funziona:
  1. L'utente scrive un comando con "ogni giorno alle HH:MM <azione>"
  2. HomeMind salva il task ricorrente con orario e azione
  3. Ogni giorno all'orario impostato il task viene eseguito
  4. I task rimangono attivi finché non vengono cancellati con /cancella_task_ripetuto N
  5. Manda notifica di conferma ad ogni esecuzione

Salvataggio: /data/homemind_recurring_tasks.json
Comandi Telegram:
  /task_ripetuti              → lista task ricorrenti attivi
  /cancella_task_ripetuto N   → cancella task numero N
  /cancella_task_ripetuto tutti → cancella tutti
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.recurring_tasks")

RECURRING_TASKS_PATH = Path("/data/homemind_recurring_tasks.json")

# Mappa giorni della settimana IT e EN
_DAYS_IT = {
    "lunedi": 0, "lunedì": 0,
    "martedi": 1, "martedì": 1,
    "mercoledi": 2, "mercoledì": 2,
    "giovedi": 3, "giovedì": 3,
    "venerdi": 4, "venerdì": 4,
    "sabato": 5,
    "domenica": 6,
}
_DAYS_EN = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


class RecurringTaskScheduler:
    def __init__(self, notifier=None, rest_client=None,
                 ai=None, action_cb=None, state_cache_cb=None):
        self.notifier       = notifier
        self.rest           = rest_client
        self.ai             = ai
        self.action_cb      = action_cb       # callback _exec_actions di main.py
        self._cache_cb      = state_cache_cb
        self._tasks: list   = []              # lista task ricorrenti attivi
        self._task_loop: Optional[asyncio.Task] = None
        self._load()

    # ─────────────────────────────────────────────────────────────────────────
    # Persistenza

    def _load(self):
        try:
            if RECURRING_TASKS_PATH.exists():
                data = json.loads(RECURRING_TASKS_PATH.read_text(encoding="utf-8"))
                self._tasks = data.get("tasks", [])
                logger.info("RecurringTaskScheduler: caricati %d task ricorrenti", len(self._tasks))
        except Exception as e:
            logger.warning("RecurringTaskScheduler load error: %s", e)
            self._tasks = []

    def _save(self):
        try:
            RECURRING_TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
            RECURRING_TASKS_PATH.write_text(
                json.dumps({"tasks": self._tasks}, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning("RecurringTaskScheduler save error: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Avvio

    async def start(self):
        self._task_loop = asyncio.create_task(
            self._main_loop(), name="recurring_task_scheduler"
        )
        logger.info("RecurringTaskScheduler avviato — controllo ogni 60s")

    # ─────────────────────────────────────────────────────────────────────────
    # Loop principale

    async def _main_loop(self):
        await asyncio.sleep(15)  # delay iniziale avvio
        while True:
            try:
                await self._check_and_execute()
            except Exception as e:
                logger.warning("RecurringTaskScheduler loop error: %s", e)
            await asyncio.sleep(60)  # check ogni minuto

    async def _check_and_execute(self):
        now = now_local()
        now_h = now.hour
        now_m = now.minute
        now_dow = now.weekday()  # 0=lunedì, 6=domenica
        now_ts = time.time()

        for task in self._tasks:
            if not task.get("enabled", True):
                continue

            task_h = task.get("hour", -1)
            task_m = task.get("minute", 0)
            task_dow = task.get("day_of_week", None)  # None = ogni giorno

            # Controlla se siamo nell'orario giusto (finestra di 60 secondi)
            if now_h != task_h or now_m != task_m:
                continue

            # Controlla giorno della settimana (se specificato)
            if task_dow is not None and now_dow != task_dow:
                continue

            # Anti-doppio-esecuzione: controlla che non sia stato eseguito
            # negli ultimi 90 secondi
            last_run = task.get("last_run_ts", 0)
            if now_ts - last_run < 90:
                continue

            # Esegui
            task["last_run_ts"] = now_ts
            task["run_count"] = task.get("run_count", 0) + 1
            self._save()
            await self._execute_task(task)

    async def _execute_task(self, task: dict):
        label   = task.get("label", "task ricorrente")
        command = task.get("command", "")
        chat_id = task.get("chat_id", "")
        run_count = task.get("run_count", 1)

        logger.info("RecurringTaskScheduler: eseguo task ricorrente '%s' (run #%d) — cmd: %s",
                    label, run_count, command[:60])

        try:
            # Promemoria puro — solo notifica
            if command.startswith("__REMINDER__:"):
                reminder_text = command[len("__REMINDER__:"):]
                msg = f"🔁 <b>Promemoria ricorrente!</b>\n{reminder_text}"
                if self.notifier:
                    if chat_id:
                        await self.notifier.send_html_to(chat_id, msg)
                    else:
                        await self.notifier.send_html(msg)
                return

            # Azione domotica via AI
            if self.ai and self.action_cb and command:
                sys_prompt = (
                    "Sei HomeMind. Esegui il comando domotico ricevuto.\n"
                    "Rispondi SOLO con i tag [CALL_SERVICE:] necessari, nessun testo.\n"
                    "REGOLA CRITICA: usa SEMPRE l'entity_id ESATTO dalla lista dispositivi.\n"
                    "NON inventare entity_id.\n"
                    "Esempi:\n"
                    "  [CALL_SERVICE:light.turn_on:light.faretti]\n"
                    "  [CALL_SERVICE:switch.turn_off:switch.scaldabagno]\n"
                    "  [CALL_SERVICE:climate.set_temperature:climate.termostato:{\"temperature\":22}]\n"
                )
                if self._cache_cb:
                    cache = self._cache_cb()
                    entities = []
                    for eid, s in cache.items():
                        if eid.startswith(("light.", "switch.", "climate.",
                                           "cover.", "fan.", "media_player.")):
                            name = s.get("attributes", {}).get("friendly_name", eid)
                            state = s.get("state", "?")
                            entities.append(f"{name} → {eid} (stato: {state})")
                    if entities:
                        sys_prompt += ("\n\nLISTA COMPLETA DISPOSITIVI:\n"
                                       + "\n".join(entities))

                ai_reply = await self.ai.ask(sys_prompt, command, max_tokens=300)
                if ai_reply:
                    logger.info("RecurringTaskScheduler: AI risposta: %s", ai_reply[:100])
                    await self.action_cb(ai_reply)

            # Notifica all'utente
            msg = f"🔁 <b>Task ricorrente eseguito!</b>\n{label}"
            if self.notifier:
                if chat_id:
                    await self.notifier.send_html_to(chat_id, msg)
                else:
                    await self.notifier.send_html(msg)

        except Exception as e:
            logger.error("RecurringTaskScheduler: errore '%s': %s", label, e)
            if self.notifier:
                err_msg = f"⚠️ Errore task ricorrente: {label}\n{e}"
                if chat_id:
                    await self.notifier.send_html_to(chat_id, err_msg)
                else:
                    await self.notifier.send_html(err_msg)

    # ─────────────────────────────────────────────────────────────────────────
    # Parsing — estrae orario e giorno dal testo

    def parse_recurring_time(self, text: str) -> Optional[dict]:
        """
        Prova a estrarre orario e ricorrenza dal testo.
        Ritorna dict con {hour, minute, day_of_week (opzionale)} o None.

        Supporta:
          - "ogni giorno alle 19:00"
          - "tutti i giorni alle 8"
          - "ogni mattina alle 7:30"
          - "ogni sera alle 22"
          - "ogni lunedì alle 9"
          - "ogni venerdì alle 20:30"
          - "every day at 8pm"
          - "every monday at 9am"
        """
        text_low = text.lower()

        # Estrai orario — HH:MM o HH
        hour, minute = None, 0
        m = re.search(r'(?:alle\s+ore|alle|ore|at)\s+(\d{1,2}):(\d{2})', text_low)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))
        else:
            m = re.search(r'(?:alle\s+ore|alle|ore|at)\s+(\d{1,2})(?!\s*:)', text_low)
            if m:
                hour = int(m.group(1))
                minute = 0

        if hour is None:
            return None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None

        # Controlla se è un giorno specifico della settimana
        all_days = {**_DAYS_IT, **_DAYS_EN}
        for day_name, day_num in all_days.items():
            if re.search(r'\b' + re.escape(day_name) + r'\b', text_low):
                return {"hour": hour, "minute": minute, "day_of_week": day_num, "day_name": day_name}

        # Ogni giorno / tutti i giorni / every day
        daily_patterns = [
            r'ogni\s+giorno', r'tutti\s+i\s+giorni', r'ogni\s+mattina',
            r'ogni\s+sera', r'ogni\s+notte', r'daily', r'every\s+day',
            r'ogni\s+giornata', r'tutte\s+le\s+mattine', r'tutte\s+le\s+sere',
        ]
        for pat in daily_patterns:
            if re.search(pat, text_low):
                return {"hour": hour, "minute": minute, "day_of_week": None}

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Aggiunta task

    def add_task(self, hour: int, minute: int, label: str,
                 command: str, chat_id: str = "",
                 day_of_week: Optional[int] = None) -> dict:
        """Aggiunge un task ricorrente. Ritorna il task creato."""
        task_id = f"rtask_{int(time.time() * 1000)}"
        task = {
            "id":           task_id,
            "hour":         hour,
            "minute":       minute,
            "day_of_week":  day_of_week,   # None = ogni giorno
            "label":        label,
            "command":      command,
            "chat_id":      chat_id,
            "enabled":      True,
            "created_at":   time.time(),
            "last_run_ts":  0,
            "run_count":    0,
        }
        self._tasks.append(task)
        self._save()
        dow_str = self._dow_label(day_of_week) if day_of_week is not None else "ogni giorno"
        logger.info("RecurringTaskScheduler: aggiunto task '%s' alle %02d:%02d (%s)",
                    label, hour, minute, dow_str)
        return task

    # ─────────────────────────────────────────────────────────────────────────
    # Cancellazione

    def cancel_by_index(self, index: int) -> Optional[dict]:
        """Cancella task per indice 1-based (stesso ordine di get_tasks_display)."""
        sorted_tasks = self._sorted()
        idx = index - 1
        if 0 <= idx < len(sorted_tasks):
            task = sorted_tasks[idx]
            self._tasks = [t for t in self._tasks if t["id"] != task["id"]]
            self._save()
            return task
        return None

    def clear_all(self):
        self._tasks = []
        self._save()

    # ─────────────────────────────────────────────────────────────────────────
    # Visualizzazione

    def _sorted(self) -> list:
        """Task ordinati per ora, poi minuto, poi giorno."""
        return sorted(self._tasks,
                      key=lambda t: (t.get("hour", 0), t.get("minute", 0),
                                     t.get("day_of_week") if t.get("day_of_week") is not None else -1))

    def _dow_label(self, dow: Optional[int], lang: str = "it") -> str:
        if dow is None:
            return "ogni giorno" if lang == "it" else "every day"
        days_it = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
        days_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        days = days_en if lang == "en" else days_it
        return "ogni " + days[dow] if lang == "it" else "every " + days[dow]

    def get_tasks_display(self, lang: str = "it") -> str:
        if lang == "it":
            return self._display_it()
        return self._display_en()

    def _display_it(self) -> str:
        if not self._tasks:
            return (
                "🔁 <b>Nessun task ricorrente attivo.</b>\n\n"
                "<i>Esempio:\n"
                "  ogni giorno alle 19 accendi la luce soggiorno\n"
                "  ogni lunedì alle 9 accendi la presa lavatrice\n"
                "  ogni sera alle 23 ricordami di prendere le medicine</i>"
            )

        st = self._sorted()
        lines = [f"🔁 <b>Task ricorrenti attivi ({len(st)})</b>\n"]
        for i, task in enumerate(st, 1):
            h = task.get("hour", 0)
            m = task.get("minute", 0)
            dow = task.get("day_of_week", None)
            runs = task.get("run_count", 0)
            sched = f"{self._dow_label(dow)} alle {h:02d}:{m:02d}"
            lines.append(f"  <b>{i}.</b> {task['label']}")
            lines.append(f"      🕐 {sched}  |  eseguito {runs}×")

        lines.append(
            "\n<i>Usa /cancella_task_ripetuto N per cancellare\n"
            "Usa /cancella_task_ripetuto tutti per cancellare tutti</i>"
        )
        return "\n".join(lines)

    def _display_en(self) -> str:
        if not self._tasks:
            return (
                "🔁 <b>No recurring tasks active.</b>\n\n"
                "<i>Example:\n"
                "  every day at 7pm turn on living room light\n"
                "  every monday at 9am turn on washing machine\n"
                "  every evening at 11pm remind me to take medicine</i>"
            )

        st = self._sorted()
        lines = [f"🔁 <b>Active recurring tasks ({len(st)})</b>\n"]
        for i, task in enumerate(st, 1):
            h = task.get("hour", 0)
            m = task.get("minute", 0)
            dow = task.get("day_of_week", None)
            runs = task.get("run_count", 0)
            sched = f"{self._dow_label(dow, 'en')} at {h:02d}:{m:02d}"
            lines.append(f"  <b>{i}.</b> {task['label']}")
            lines.append(f"      🕐 {sched}  |  executed {runs}×")

        lines.append(
            "\n<i>Use /cancella_task_ripetuto N to cancel one\n"
            "Use /cancella_task_ripetuto tutti to cancel all</i>"
        )
        return "\n".join(lines)
