"""
agent/task_scheduler.py — Task Scheduler per HomeMind.

Permette di schedulare azioni future parlando in modo naturale su Telegram.

Esempi:
  "Accendi la luce di Mario alle 19:00"
  "Tra 30 minuti spegni le luci"
  "Alle 20:30 accendi caldaia e metti 22 gradi"
  "Domani mattina alle 7 accendi il riscaldamento"

Come funziona:
  1. L'utente scrive un comando con indicazione temporale
  2. L'AI estrae: orario, azione da eseguire
  3. HomeMind salva il task e lo esegue all'ora giusta
  4. Manda una notifica di conferma quando eseguito

Salvataggio: /data/homemind_tasks.json
Comandi Telegram:
  /task            → lista task in coda
  /cancella task N → cancella task numero N
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

logger = logging.getLogger("homemind.tasks")

TASKS_PATH = Path("/data/homemind_tasks.json")


class TaskScheduler:
    def __init__(self, notifier=None, rest_client=None,
                 ai=None, action_cb=None, state_cache_cb=None):
        self.notifier       = notifier
        self.rest           = rest_client
        self.ai             = ai
        self.action_cb      = action_cb   # callback _exec_actions di main.py
        self._cache_cb      = state_cache_cb
        self._tasks: list   = []          # lista task attivi
        self._task_loop: Optional[asyncio.Task] = None
        self._load()

    # ─────────────────────────────────────────────────────────────────────────
    # Persistenza

    def _load(self):
        try:
            if TASKS_PATH.exists():
                data = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
                # Carica solo task futuri
                now_ts = time.time()
                self._tasks = [t for t in data.get("tasks", [])
                               if t.get("execute_at", 0) > now_ts]
                logger.info("TaskScheduler: caricati %d task in coda", len(self._tasks))
        except Exception as e:
            logger.warning("TaskScheduler load error: %s", e)
            self._tasks = []

    def _save(self):
        try:
            TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
            TASKS_PATH.write_text(
                json.dumps({"tasks": self._tasks}, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning("TaskScheduler save error: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Avvio

    async def start(self):
        self._task_loop = asyncio.create_task(
            self._main_loop(), name="task_scheduler"
        )
        logger.info("TaskScheduler avviato — controllo task ogni 30s")

    # ─────────────────────────────────────────────────────────────────────────
    # Loop principale

    async def _main_loop(self):
        await asyncio.sleep(10)  # delay iniziale avvio
        while True:
            try:
                await self._check_and_execute()
            except Exception as e:
                logger.warning("TaskScheduler loop error: %s", e)
            await asyncio.sleep(30)  # check ogni 30 secondi

    async def _check_and_execute(self):
        now_ts = time.time()
        executed = []

        for task in self._tasks:
            if task.get("execute_at", 0) <= now_ts:
                await self._execute_task(task)
                executed.append(task["id"])

        if executed:
            self._tasks = [t for t in self._tasks if t["id"] not in executed]
            self._save()

    async def _execute_task(self, task: dict):
        label   = task.get("label", "task")
        command = task.get("command", "")
        chat_id = task.get("chat_id", "")

        logger.info("TaskScheduler: eseguo task '%s' — comando: %s", label, command[:60])

        try:
            # Promemoria puro — manda solo notifica Telegram senza AI
            if command.startswith("__REMINDER__:"):
                reminder_text = command[len("__REMINDER__:"):]
                # Rimuovi le parole "ricordami", "avvisami" ecc. dal testo
                import re as _re_rem
                reminder_text = _re_rem.sub(
                    r'^(ricordami|ricorda|avvisami|avvisa|remind me|remind|'
                    r'promemoria|remember|alert me|notificami|notifica)\s*',
                    "", reminder_text, flags=_re_rem.IGNORECASE
                ).strip()
                msg = f"⏰ <b>Promemoria!</b>\n{reminder_text}"
                if self.notifier:
                    if chat_id:
                        await self.notifier.send_html_to(chat_id, msg)
                    else:
                        await self.notifier.send_html(msg)
                logger.info("TaskScheduler: promemoria inviato '%s'", reminder_text[:60])
                return

            # Chiedi all'AI di tradurre il comando in [CALL_SERVICE:...]
            # poi esegui le azioni risultanti
            if self.ai and self.action_cb and command:
                sys_prompt = (
                    "Sei HomeMind. Esegui il comando domotico ricevuto.\n"
                    "Rispondi SOLO con i tag [CALL_SERVICE:] necessari, nessun testo.\n"
                    "REGOLA CRITICA: usa SEMPRE l'entity_id ESATTO dalla lista dispositivi.\n"
                    "NON inventare entity_id — cerca il nome nel testo del comando e usa\n"
                    "l'entity_id corrispondente dalla lista.\n"
                    "Esempi:\n"
                    "  [CALL_SERVICE:light.turn_on:light.faretti]\n"
                    "  [CALL_SERVICE:switch.turn_off:switch.scaldabagno]\n"
                    "  [CALL_SERVICE:climate.set_temperature:climate.termostato:{\"temperature\":22}]\n"
                )
                # Aggiungi contesto COMPLETO di luci, switch e climate
                if self._cache_cb:
                    cache = self._cache_cb()
                    entities = []
                    for eid, s in cache.items():
                        if eid.startswith(("light.", "switch.", "climate.",
                                           "cover.", "fan.", "media_player.")):
                            name = s.get("attributes", {}).get("friendly_name", eid)
                            state = s.get("state", "?")
                            # Includi TUTTI — nessun limite di 30
                            entities.append(f"{name} → {eid} (stato: {state})")
                    if entities:
                        sys_prompt += ("\n\nLISTA COMPLETA DISPOSITIVI (usa entity_id esatto):\n"
                                       + "\n".join(entities))

                ai_reply = await self.ai.ask(sys_prompt, command, max_tokens=300)
                if ai_reply:
                    logger.info("TaskScheduler: AI risposta: %s", ai_reply[:100])
                    await self.action_cb(ai_reply)
                else:
                    logger.warning("TaskScheduler: AI non ha restituito azioni per: %s", command)

            # Notifica all'utente
            msg = f"⏰ <b>Task eseguito!</b>\n{label}"
            if self.notifier:
                if chat_id:
                    await self.notifier.send_html_to(chat_id, msg)
                else:
                    await self.notifier.send_html(msg)

        except Exception as e:
            logger.error("TaskScheduler: errore esecuzione task '%s': %s", label, e)
            if self.notifier:
                err_msg = f"⚠️ Errore eseguendo task: {label}\n{e}"
                if chat_id:
                    await self.notifier.send_html_to(chat_id, err_msg)
                else:
                    await self.notifier.send_html(err_msg)

    # ─────────────────────────────────────────────────────────────────────────
    # Parsing orario — converte testo italiano/inglese in timestamp

    # Mappa giorni della settimana IT e EN
    _DAYS_IT = {"lunedi": 0, "lunedì": 0, "martedi": 1, "martedì": 1,
                "mercoledi": 2, "mercoledì": 2, "giovedi": 3, "giovedì": 3,
                "venerdi": 4, "venerdì": 4, "sabato": 5, "domenica": 6}
    _DAYS_EN = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6}

    def parse_time(self, text: str) -> Optional[float]:
        """
        Prova a estrarre un timestamp dal testo.
        Supporta IT e EN:
          - "alle 19:00" / "at 19:00"
          - "alle ore 19:30" / "ore 19:30"
          - "tra 30 minuti" / "in 30 minutes"
          - "tra 2 ore" / "in 2 hours"
          - "tra 3 giorni" / "in 3 days"
          - "domani alle 7" / "tomorrow at 7"
          - "venerdì alle 19" / "friday at 7pm"
          - "il 25 marzo alle 9" / "march 25 at 9"
        Ritorna timestamp Unix o None se non trovato.
        """
        now = now_local()
        text_low = text.lower()

        # tra N minuti / in N minutes
        m = re.search(r'tra\s+(\d+)\s+minut|in\s+(\d+)\s+minut', text_low)
        if m:
            mins = int(m.group(1) or m.group(2))
            return (now + timedelta(minutes=mins)).timestamp()

        # tra N ore / in N hours
        m = re.search(r'tra\s+(\d+)\s+or[ae]|in\s+(\d+)\s+hour', text_low)
        if m:
            hours = int(m.group(1) or m.group(2))
            return (now + timedelta(hours=hours)).timestamp()

        # tra N giorni / in N days
        m = re.search(r'tra\s+(\d+)\s+giorni?|in\s+(\d+)\s+days?', text_low)
        if m:
            days = int(m.group(1) or m.group(2))
            target = now + timedelta(days=days)
            # Cerca anche un orario nello stesso testo
            mh = re.search(r'alle\s+(\d{1,2})(?::(\d{2}))?|at\s+(\d{1,2})(?::(\d{2}))?', text_low)
            if mh:
                h  = int(mh.group(1) or mh.group(3) or 8)
                mi = int(mh.group(2) or mh.group(4) or 0)
                target = target.replace(hour=h, minute=mi, second=0, microsecond=0)
            else:
                target = target.replace(second=0, microsecond=0)
            return target.timestamp()

        # domani/tomorrow
        is_tomorrow = bool(re.search(r'domani|tomorrow', text_low))

        # Giorno della settimana IT/EN (es. "venerdì alle 19", "friday at 7")
        all_days = {**self._DAYS_IT, **self._DAYS_EN}
        for day_name, day_num in all_days.items():
            if day_name in text_low:
                days_ahead = (day_num - now.weekday()) % 7
                if days_ahead == 0:  # stesso giorno → prossima settimana
                    days_ahead = 7
                target = now + timedelta(days=days_ahead)
                # Cerca orario abbinato
                mh = re.search(r'alle\s+(\d{1,2})(?::(\d{2}))?|at\s+(\d{1,2})(?::(\d{2}))?', text_low)
                if mh:
                    h  = int(mh.group(1) or mh.group(3) or 8)
                    mi = int(mh.group(2) or mh.group(4) or 0)
                    target = target.replace(hour=h, minute=mi, second=0, microsecond=0)
                else:
                    target = target.replace(hour=8, minute=0, second=0, microsecond=0)
                return target.timestamp()

        # Data specifica IT: "il 25 marzo" / "25 marzo"
        MONTHS_IT = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,
                     "giugno":6,"luglio":7,"agosto":8,"settembre":9,
                     "ottobre":10,"novembre":11,"dicembre":12}
        MONTHS_EN = {"january":1,"february":2,"march":3,"april":4,"may":5,
                     "june":6,"july":7,"august":8,"september":9,
                     "october":10,"november":11,"december":12}
        all_months = {**MONTHS_IT, **MONTHS_EN}
        for month_name, month_num in all_months.items():
            if month_name in text_low:
                md = re.search(r'(\d{1,2})\s+' + month_name, text_low)
                if not md:
                    md = re.search(month_name + r'\s+(\d{1,2})', text_low)
                if md:
                    day = int(md.group(1))
                    year = now.year if month_num >= now.month else now.year + 1
                    try:
                        target = now.replace(year=year, month=month_num,
                                             day=day, second=0, microsecond=0)
                        # Orario opzionale
                        mh = re.search(r'alle\s+(\d{1,2})(?::(\d{2}))?|at\s+(\d{1,2})(?::(\d{2}))?', text_low)
                        if mh:
                            h  = int(mh.group(1) or mh.group(3) or 8)
                            mi = int(mh.group(2) or mh.group(4) or 0)
                            target = target.replace(hour=h, minute=mi)
                        else:
                            target = target.replace(hour=8, minute=0)
                        if target > now:
                            return target.timestamp()
                    except ValueError:
                        pass
                break

        # alle ore HH:MM / ore HH:MM
        m = re.search(r'(?:alle\s+ore|ore)\s+(\d{1,2}):(\d{2})', text_low)
        if m:
            h = int(m.group(1))
            mi = int(m.group(2))
            target = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            if is_tomorrow:
                target += timedelta(days=1)
            elif target <= now:
                target += timedelta(days=1)
            return target.timestamp()

        # alle HH:MM / at HH:MM
        m = re.search(r'alle\s+(\d{1,2}):(\d{2})|at\s+(\d{1,2}):(\d{2})', text_low)
        if m:
            h = int(m.group(1) or m.group(3))
            mi = int(m.group(2) or m.group(4))
            target = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            if is_tomorrow:
                target += timedelta(days=1)
            elif target <= now:
                target += timedelta(days=1)
            return target.timestamp()

        # alle HH / at HH (solo ore)
        m = re.search(r'alle\s+(\d{1,2})(?!\s*:)|at\s+(\d{1,2})(?!\s*:)', text_low)
        if m:
            h = int(m.group(1) or m.group(2))
            target = now.replace(hour=h, minute=0, second=0, microsecond=0)
            if is_tomorrow:
                target += timedelta(days=1)
            elif target <= now:
                target += timedelta(days=1)
            return target.timestamp()

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Aggiunta task

    def add_task(self, execute_at: float, label: str,
                 command: str, chat_id: str = "") -> dict:
        """Aggiunge un task alla coda. Ritorna il task creato."""
        task_id = f"task_{int(time.time() * 1000)}"
        task = {
            "id":         task_id,
            "execute_at": execute_at,
            "label":      label,
            "command":    command,
            "chat_id":    chat_id,
            "created_at": time.time(),
        }
        self._tasks.append(task)
        self._save()
        logger.info("TaskScheduler: aggiunto task '%s' alle %s",
                    label, datetime.fromtimestamp(execute_at).strftime("%H:%M"))
        return task

    # ─────────────────────────────────────────────────────────────────────────
    # Cancellazione task

    def cancel_task(self, task_id: str) -> bool:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t["id"] != task_id]
        if len(self._tasks) < before:
            self._save()
            return True
        return False

    def cancel_by_index(self, index: int) -> Optional[dict]:
        """Cancella task per indice (1-based) dalla lista ORDINATA per orario.
        Stesso ordine mostrato da get_tasks_display."""
        sorted_tasks = sorted(self._tasks, key=lambda t: t["execute_at"])
        idx = index - 1
        if 0 <= idx < len(sorted_tasks):
            task = sorted_tasks[idx]
            # Rimuovi dalla lista originale per ID
            self._tasks = [t for t in self._tasks if t["id"] != task["id"]]
            self._save()
            return task
        return None

    def clear_all(self):
        self._tasks = []
        self._save()

    # ─────────────────────────────────────────────────────────────────────────
    # Visualizzazione

    def get_tasks_display(self) -> str:
        """Testo per il comando /task."""
        if not self._tasks:
            return "⏰ <b>Nessun task in coda.</b>\n\n<i>Esempio: \"Accendi la luce alle 19:00\"</i>"

        # Ordina per orario
        sorted_tasks = sorted(self._tasks, key=lambda t: t["execute_at"])
        lines = [f"⏰ <b>Task in coda ({len(sorted_tasks)})</b>\n"]

        for i, task in enumerate(sorted_tasks, 1):
            dt = datetime.fromtimestamp(task["execute_at"])
            now = now_local()
            diff = task["execute_at"] - time.time()

            if diff < 3600:
                time_str = f"tra {int(diff/60)} min"
            elif diff < 86400:
                time_str = dt.strftime("oggi alle %H:%M")
            else:
                time_str = dt.strftime("domani alle %H:%M")

            lines.append(f"  <b>{i}.</b> {task['label']}")
            lines.append(f"      🕐 {time_str}")

        lines.append("\n<i>Usa /cancella_task N per cancellare (es. /cancella_task 1)</i>")
        return "\n".join(lines)

    def get_tasks_display_en(self) -> str:
        """English version of task display."""
        if not self._tasks:
            return "⏰ <b>No tasks scheduled.</b>\n\n<i>Example: \"Turn on the light at 7pm\"</i>"

        sorted_tasks = sorted(self._tasks, key=lambda t: t["execute_at"])
        lines = [f"⏰ <b>Scheduled tasks ({len(sorted_tasks)})</b>\n"]

        for i, task in enumerate(sorted_tasks, 1):
            dt = datetime.fromtimestamp(task["execute_at"])
            diff = task["execute_at"] - time.time()

            if diff < 3600:
                time_str = f"in {int(diff/60)} min"
            elif diff < 86400:
                time_str = dt.strftime("today at %H:%M")
            else:
                time_str = dt.strftime("tomorrow at %H:%M")

            lines.append(f"  <b>{i}.</b> {task['label']}")
            lines.append(f"      🕐 {time_str}")

        lines.append("\n<i>Use /cancella_task N to cancel (e.g. /cancella_task 1)</i>")
        return "\n".join(lines)
