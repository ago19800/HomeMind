"""
agent/automation_engine.py — Motore Automazioni Intelligenti HomeMind.

Permette di creare automazioni event-driven in linguaggio naturale su Telegram.
Le automazioni vengono mantenute in memoria finché l'utente non le cancella.

Esempi:
  "se sono le 23 e c'è movimento in cucina accendi la luce mario"
  "se i consumi superano 2700W per 3 minuti mandami un messaggio"
  "se la porta di ingresso viene aperta dopo le 22 avvisami su telegram"
  "se il termostato scende sotto 18 gradi accendi la caldaia"
  "se tutti escono di casa spegni le luci del soggiorno"
  "se sono le 8 di mattina e l'allarme è disarmato mandami un avviso"

Come funziona:
  1. L'utente descrive l'automazione in linguaggio naturale
  2. L'AI converte il testo in una struttura JSON con trigger, condizioni, azione
  3. Il motore valuta le condizioni ad ogni evento HA (cambio stato, orario)
  4. Quando le condizioni sono soddisfatte, esegue l'azione
  5. Le automazioni restano attive finché l'utente non le cancella

Salvataggio: /data/homemind_automations.json
Comandi Telegram:
  /automazioni_hm              → lista automazioni attive
  /cancella_automazione N      → cancella automazione numero N
  /cancella_automazione tutti  → cancella tutte
  /pausa_automazione N         → mette in pausa (senza cancellare)
  /riprendi_automazione N      → riattiva dopo pausa
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.automations")

AUTOMATIONS_PATH = Path("/data/homemind_automations.json")

# Cooldown minimo tra due esecuzioni della stessa automazione (evita loop)
DEFAULT_COOLDOWN = 300   # 5 minuti
NOTIFY_COOLDOWN  = 60    # 1 minuto per automazioni di sola notifica


class AutomationEngine:
    def __init__(self, notifier=None, rest_client=None,
                 ai=None, action_cb=None, state_cache_cb=None):
        self.notifier      = notifier
        self.rest          = rest_client
        self.ai            = ai
        self.action_cb     = action_cb        # _exec_actions di main.py
        self._cache_cb     = state_cache_cb
        self._automations: list = []
        # Stato interno per condizioni temporali (debounce)
        self._condition_state: dict = {}      # auto_id → {since_ts, active}
        self._last_run: dict = {}             # auto_id → timestamp ultima esecuzione
        self._time_check_task: Optional[asyncio.Task] = None
        self._load()

    # ─────────────────────────────────────────────────────────────────────────
    # Persistenza

    def _load(self):
        try:
            if AUTOMATIONS_PATH.exists():
                data = json.loads(AUTOMATIONS_PATH.read_text(encoding="utf-8"))
                self._automations = data.get("automations", [])
                logger.info("AutomationEngine: caricate %d automazioni", len(self._automations))
        except Exception as e:
            logger.warning("AutomationEngine load error: %s", e)
            self._automations = []

    def _save(self):
        try:
            AUTOMATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
            AUTOMATIONS_PATH.write_text(
                json.dumps({"automations": self._automations}, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning("AutomationEngine save error: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Avvio

    async def start(self):
        self._time_check_task = asyncio.create_task(
            self._time_loop(), name="automation_time_loop"
        )
        logger.info("AutomationEngine avviato — controllo orario ogni 30s")

    # ─────────────────────────────────────────────────────────────────────────
    # Loop controllo condizioni temporali (trigger orario)

    async def _time_loop(self):
        await asyncio.sleep(20)
        while True:
            try:
                await self._check_time_triggers()
            except Exception as e:
                logger.warning("AutomationEngine time_loop error: %s", e)
            await asyncio.sleep(30)

    async def _check_time_triggers(self):
        now = now_local()
        cache = self._cache_cb() if self._cache_cb else {}

        for auto in self._automations:
            if not auto.get("enabled", True):
                continue
            trigger = auto.get("trigger", {})
            if trigger.get("type") not in ("time", "time_and_state"):
                continue
            # Controlla orario
            t_hour = trigger.get("hour")
            t_min  = trigger.get("minute", 0)
            if t_hour is None:
                continue
            if now.hour != t_hour or now.minute != t_min:
                continue
            # Anti-doppio: non eseguire due volte nello stesso minuto
            last = self._last_run.get(auto["id"], 0)
            if time.time() - last < 90:
                continue
            # Verifica condizioni extra (se presenti)
            if trigger.get("type") == "time_and_state":
                if not self._check_conditions(auto.get("conditions", []), cache):
                    continue
            # Esegui
            await self._execute(auto, cache, trigger_info="orario")

    # ─────────────────────────────────────────────────────────────────────────
    # Gestione eventi state_changed da WebSocket

    async def on_state_changed(self, entity_id: str, old_state: str, new_state: str):
        """Chiamato da main.py ad ogni cambio di stato HA."""
        cache = self._cache_cb() if self._cache_cb else {}

        for auto in self._automations:
            if not auto.get("enabled", True):
                continue
            trigger = auto.get("trigger", {})
            ttype   = trigger.get("type", "")

            if ttype not in ("state", "state_above", "state_below",
                             "state_change", "time_and_state"):
                continue

            # Verifica che il trigger riguardi questa entità
            trigger_entity = trigger.get("entity_id", "")
            if trigger_entity and trigger_entity != entity_id:
                continue

            # Logica trigger per tipo
            triggered = False

            if ttype == "state":
                # Trigger su stato specifico
                target_state = trigger.get("to_state", "")
                if target_state and new_state == target_state:
                    triggered = True
                elif not target_state:
                    # Qualsiasi cambio
                    triggered = (old_state != new_state)

            elif ttype == "state_change":
                # Qualsiasi cambio su questa entità
                triggered = (old_state != new_state)

            elif ttype in ("state_above", "state_below"):
                # Soglia numerica con debounce temporale
                threshold = trigger.get("threshold")
                duration  = trigger.get("duration_seconds", 0)
                if threshold is None:
                    continue
                try:
                    val = float(new_state)
                    cond_met = (val > threshold) if ttype == "state_above" else (val < threshold)
                    state_key = auto["id"]
                    cs = self._condition_state.setdefault(state_key, {"active": False, "since_ts": 0})
                    if cond_met:
                        if not cs["active"]:
                            cs["active"]    = True
                            cs["since_ts"]  = time.time()
                        # Controlla durata minima
                        if duration > 0:
                            elapsed = time.time() - cs["since_ts"]
                            triggered = elapsed >= duration
                        else:
                            triggered = True
                    else:
                        cs["active"]   = False
                        cs["since_ts"] = 0
                except (ValueError, TypeError):
                    pass

            elif ttype == "time_and_state":
                # Già gestito nel loop orario — skip qui
                continue

            if not triggered:
                continue

            # Verifica condizioni aggiuntive
            conditions = auto.get("conditions", [])
            if conditions and not self._check_conditions(conditions, cache):
                continue

            # Cooldown anti-ripetizione
            cooldown = auto.get("cooldown_seconds", DEFAULT_COOLDOWN)
            last = self._last_run.get(auto["id"], 0)
            if time.time() - last < cooldown:
                logger.debug("AutomationEngine: '%s' in cooldown", auto.get("label", "?"))
                continue

            await self._execute(auto, cache, trigger_info=f"{entity_id}: {old_state}→{new_state}")

    # ─────────────────────────────────────────────────────────────────────────
    # Valutazione condizioni

    def _check_conditions(self, conditions: list, cache: dict) -> bool:
        """Valuta tutte le condizioni (AND). Ritorna True se tutte soddisfatte."""
        for cond in conditions:
            ctype = cond.get("type", "")

            if ctype == "time_range":
                now = now_local()
                h_from = cond.get("from_hour", 0)
                h_to   = cond.get("to_hour", 24)
                in_range = (h_from <= now.hour < h_to) if h_from <= h_to else \
                           (now.hour >= h_from or now.hour < h_to)
                if not in_range:
                    return False

            elif ctype == "state":
                eid      = cond.get("entity_id", "")
                expected = cond.get("state", "")
                actual   = cache.get(eid, {}).get("state", "")
                if actual != expected:
                    return False

            elif ctype == "numeric_above":
                eid       = cond.get("entity_id", "")
                threshold = cond.get("threshold", 0)
                try:
                    val = float(cache.get(eid, {}).get("state", "0"))
                    if val <= threshold:
                        return False
                except (ValueError, TypeError):
                    return False

            elif ctype == "numeric_below":
                eid       = cond.get("entity_id", "")
                threshold = cond.get("threshold", 0)
                try:
                    val = float(cache.get(eid, {}).get("state", "0"))
                    if val >= threshold:
                        return False
                except (ValueError, TypeError):
                    return False

            elif ctype == "everyone_away":
                # Tutti fuori casa
                persons_away = all(
                    cache.get(eid, {}).get("state") in ("not_home", "away")
                    for eid in cache if eid.startswith("person.")
                    and cache[eid].get("state") not in ("unavailable", "unknown")
                )
                if not persons_away:
                    return False

            elif ctype == "someone_home":
                persons_home = any(
                    cache.get(eid, {}).get("state") == "home"
                    for eid in cache if eid.startswith("person.")
                )
                if not persons_home:
                    return False

        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Esecuzione automazione

    async def _execute(self, auto: dict, cache: dict, trigger_info: str = ""):
        label    = auto.get("label", "automazione")
        action   = auto.get("action", {})
        atype    = action.get("type", "notify")
        chat_id  = auto.get("chat_id", "")

        logger.info("AutomationEngine: eseguo '%s' (trigger: %s)", label, trigger_info)

        # Aggiorna contatori
        self._last_run[auto["id"]] = time.time()
        auto["run_count"] = auto.get("run_count", 0) + 1
        self._save()

        try:
            if atype == "notify":
                # Solo notifica Telegram
                msg_template = action.get("message", f"⚡ Automazione: {label}")
                msg = self._render_message(msg_template, cache, trigger_info)
                if self.notifier:
                    if chat_id:
                        await self.notifier.send_html_to(chat_id, msg)
                    else:
                        await self.notifier.send_html(msg)

            elif atype == "call_service":
                # Esegui azione HA
                service_tag = action.get("service_tag", "")
                if service_tag and self.action_cb:
                    await self.action_cb(service_tag)
                # Notifica opzionale
                notify_msg = action.get("notify_message", "")
                if notify_msg and self.notifier:
                    msg = self._render_message(notify_msg, cache, trigger_info)
                    if chat_id:
                        await self.notifier.send_html_to(chat_id, msg)
                    else:
                        await self.notifier.send_html(msg)

            elif atype == "ai_command":
                # Esegui comando tramite AI (per azioni complesse)
                command = action.get("command", "")
                if command and self.ai and self.action_cb:
                    sys_prompt = (
                        "Sei HomeMind. Esegui il comando domotico ricevuto.\n"
                        "Rispondi SOLO con i tag [CALL_SERVICE:] necessari, nessun testo.\n"
                        "Usa SEMPRE l'entity_id ESATTO dalla lista dispositivi.\n"
                        "Esempi:\n"
                        "  [CALL_SERVICE:light.turn_on:light.faretti]\n"
                        "  [CALL_SERVICE:switch.turn_off:switch.scaldabagno]\n"
                        "  [CALL_SERVICE:climate.set_temperature:climate.termostato:{\"temperature\":22}]\n"
                    )
                    if self._cache_cb:
                        entities = []
                        for eid, s in cache.items():
                            if eid.startswith(("light.", "switch.", "climate.",
                                               "cover.", "fan.", "media_player.")):
                                name = s.get("attributes", {}).get("friendly_name", eid)
                                state = s.get("state", "?")
                                entities.append(f"{name} → {eid} (stato: {state})")
                        if entities:
                            sys_prompt += "\n\nDISPOSITIVI:\n" + "\n".join(entities)
                    ai_reply = await self.ai.ask(sys_prompt, command, max_tokens=300)
                    if ai_reply:
                        await self.action_cb(ai_reply)
                # Notifica opzionale
                notify_msg = action.get("notify_message", "")
                if notify_msg and self.notifier:
                    msg = self._render_message(notify_msg, cache, trigger_info)
                    if chat_id:
                        await self.notifier.send_html_to(chat_id, msg)
                    else:
                        await self.notifier.send_html(msg)

        except Exception as e:
            logger.error("AutomationEngine: errore esecuzione '%s': %s", label, e)
            if self.notifier:
                err = f"⚠️ Errore automazione <b>{label}</b>: {e}"
                if chat_id:
                    await self.notifier.send_html_to(chat_id, err)
                else:
                    await self.notifier.send_html(err)

    def _render_message(self, template: str, cache: dict, trigger_info: str) -> str:
        """Sostituisce placeholder nel messaggio."""
        now = now_local()
        msg = template
        msg = msg.replace("{ora}", now.strftime("%H:%M"))
        msg = msg.replace("{data}", now.strftime("%d/%m/%Y"))
        msg = msg.replace("{trigger}", trigger_info)
        # Sostituisce {entity_id.state} con il valore reale
        for match in re.finditer(r'\{([a-z_]+\.[a-z0-9_]+)\.state\}', msg):
            eid = match.group(1)
            state = cache.get(eid, {}).get("state", "?")
            msg = msg.replace(match.group(0), state)
        return msg

    # ─────────────────────────────────────────────────────────────────────────
    # Parsing linguaggio naturale → struttura JSON (via AI)

    async def parse_automation(self, text: str, chat_id: str) -> Optional[dict]:
        """
        Converte una descrizione testuale in una struttura automazione JSON.
        Usa l'AI una sola volta alla creazione — poi il motore valuta la struttura.
        """
        if not self.ai:
            return None

        cache = self._cache_cb() if self._cache_cb else {}

        # Costruisci lista entità disponibili per dare contesto all'AI
        entities_ctx = []
        for eid, s in cache.items():
            name  = s.get("attributes", {}).get("friendly_name", eid)
            state = s.get("state", "?")
            if eid.startswith(("binary_sensor.", "sensor.", "light.", "switch.",
                                "climate.", "person.", "alarm_control_panel.",
                                "cover.", "input_boolean.", "media_player.")):
                entities_ctx.append(f"{name} → {eid} (stato: {state})")

        entities_str = "\n".join(entities_ctx[:80])  # max 80 entità

        sys_prompt = f"""Sei HomeMind, un assistente domotico. Il tuo compito è convertire una descrizione di automazione in linguaggio naturale in una struttura JSON precisa.

ENTITÀ DISPONIBILI IN HOME ASSISTANT:
{entities_str}

Rispondi SOLO con un JSON valido, senza markdown, senza commenti, senza testo aggiuntivo.

Struttura JSON da produrre:
{{
  "label": "descrizione breve dell'automazione",
  "trigger": {{
    "type": "state|state_above|state_below|state_change|time|time_and_state",
    "entity_id": "entity_id del sensore trigger (se applicabile)",
    "to_state": "stato target (es. on, off, home, not_home) — solo per type=state",
    "threshold": 2700,
    "duration_seconds": 180,
    "hour": 23,
    "minute": 0
  }},
  "conditions": [
    {{"type": "time_range", "from_hour": 22, "to_hour": 7}},
    {{"type": "state", "entity_id": "binary_sensor.xxx", "state": "on"}},
    {{"type": "numeric_above", "entity_id": "sensor.xxx", "threshold": 100}},
    {{"type": "numeric_below", "entity_id": "sensor.xxx", "threshold": 18}},
    {{"type": "everyone_away"}},
    {{"type": "someone_home"}}
  ],
  "action": {{
    "type": "notify|call_service|ai_command",
    "message": "messaggio Telegram con placeholder {{ora}}, {{trigger}}",
    "service_tag": "[CALL_SERVICE:light.turn_on:light.faretti]",
    "command": "testo comando domotico per AI",
    "notify_message": "messaggio opzionale dopo aver eseguito l'azione"
  }},
  "cooldown_seconds": 300
}}

REGOLE IMPORTANTI:
- trigger.type "state_above"/"state_below" = soglia numerica su sensore (es. watt, temperatura)
- trigger.duration_seconds = secondi che la condizione deve essere vera prima di scattare
- conditions = lista di condizioni aggiuntive (tutte devono essere vere, AND)
- action.type "notify" = solo messaggio Telegram, nessuna azione HA
- action.type "call_service" = esegui servizio HA con service_tag nel formato [CALL_SERVICE:domain.service:entity_id]
- action.type "ai_command" = esegui comando complesso tramite AI (usa per azioni che richiedono ragionamento)
- cooldown_seconds = secondi minimi tra due esecuzioni (default 300 = 5 minuti)
- Per notifiche pure usa cooldown_seconds 60
- Usa entity_id ESATTI dalla lista entità disponibili

ESEMPI:

Input: "se sono le 23 e c'è movimento in cucina accendi la luce mario"
Output: {{"label": "Movimento cucina ore 23 → accendi luce mario", "trigger": {{"type": "state", "entity_id": "binary_sensor.0x00158d000224fb57_occupancy", "to_state": "on"}}, "conditions": [{{"type": "time_range", "from_hour": 23, "to_hour": 7}}], "action": {{"type": "call_service", "service_tag": "[CALL_SERVICE:light.turn_on:light.mario]", "notify_message": "💡 Luce mario accesa (movimento cucina ore {{ora}})"}}, "cooldown_seconds": 300}}

Input: "se i consumi superano 2700W per 3 minuti mandami un messaggio telegram"
Output: {{"label": "Consumo > 2700W per 3 min → avviso", "trigger": {{"type": "state_above", "entity_id": "sensor.shellyem_channel_1_power", "threshold": 2700, "duration_seconds": 180}}, "conditions": [], "action": {{"type": "notify", "message": "⚡ Attenzione! Consumi sopra 2700W da 3 minuti (ora: {{ora}})"}}, "cooldown_seconds": 60}}

Input: "se la porta ingresso viene aperta dopo le 22 avvisami"
Output: {{"label": "Porta ingresso aperta dopo le 22 → avviso", "trigger": {{"type": "state", "entity_id": "binary_sensor.0xa4c138b1260d8136_contact", "to_state": "on"}}, "conditions": [{{"type": "time_range", "from_hour": 22, "to_hour": 7}}], "action": {{"type": "notify", "message": "🚪 Porta ingresso aperta alle {{ora}}!"}}, "cooldown_seconds": 60}}"""

        try:
            raw = await self.ai.ask(sys_prompt, f"Crea automazione: {text}", max_tokens=800)
            if not raw:
                return None

            # Pulisci risposta (rimuovi markdown code block se presente)
            raw = raw.strip()
            raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
            raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
            raw = raw.strip()

            parsed = json.loads(raw)

            # Aggiungi metadati
            auto_id = f"auto_{int(time.time() * 1000)}"
            parsed["id"]         = auto_id
            parsed["chat_id"]    = chat_id
            parsed["created_at"] = time.time()
            parsed["run_count"]  = 0
            parsed["enabled"]    = True
            parsed["raw_text"]   = text  # testo originale utente

            # Valori default
            parsed.setdefault("conditions", [])
            parsed.setdefault("cooldown_seconds", DEFAULT_COOLDOWN)

            return parsed

        except json.JSONDecodeError as e:
            logger.warning("AutomationEngine parse JSON error: %s | raw: %s", e, raw[:200] if raw else "")
            return None
        except Exception as e:
            logger.warning("AutomationEngine parse error: %s", e)
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Aggiunta / rimozione automazioni

    def add_automation(self, auto: dict) -> dict:
        self._automations.append(auto)
        self._save()
        logger.info("AutomationEngine: aggiunta automazione '%s'", auto.get("label", "?"))
        return auto

    def cancel_by_index(self, index: int) -> Optional[dict]:
        sorted_autos = self._sorted()
        idx = index - 1
        if 0 <= idx < len(sorted_autos):
            auto = sorted_autos[idx]
            self._automations = [a for a in self._automations if a["id"] != auto["id"]]
            self._save()
            return auto
        return None

    def pause_by_index(self, index: int) -> Optional[dict]:
        sorted_autos = self._sorted()
        idx = index - 1
        if 0 <= idx < len(sorted_autos):
            auto = sorted_autos[idx]
            for a in self._automations:
                if a["id"] == auto["id"]:
                    a["enabled"] = False
                    self._save()
                    return a
        return None

    def resume_by_index(self, index: int) -> Optional[dict]:
        sorted_autos = self._sorted()
        idx = index - 1
        if 0 <= idx < len(sorted_autos):
            auto = sorted_autos[idx]
            for a in self._automations:
                if a["id"] == auto["id"]:
                    a["enabled"] = True
                    self._save()
                    return a
        return None

    def clear_all(self):
        self._automations = []
        self._last_run = {}
        self._condition_state = {}
        self._save()

    # ─────────────────────────────────────────────────────────────────────────
    # Visualizzazione

    def _sorted(self) -> list:
        return sorted(self._automations, key=lambda a: a.get("created_at", 0))

    def get_display(self, lang: str = "it") -> str:
        if not self._automations:
            return (
                "🤖 <b>Nessuna automazione attiva.</b>\n\n"
                "<i>Esempi di automazioni:\n"
                "  se sono le 23 e c'è movimento in cucina accendi la luce mario\n"
                "  se i consumi superano 2700W per 3 minuti avvisami\n"
                "  se la porta viene aperta dopo le 22 mandami un messaggio\n"
                "  se il termostato scende sotto 18 gradi accendi la caldaia</i>\n\n"
                "<i>Scrivi la tua automazione in linguaggio naturale!</i>"
            )

        st = self._sorted()
        lines = [f"🤖 <b>Automazioni attive ({len(st)})</b>\n"]
        for i, auto in enumerate(st, 1):
            label    = auto.get("label", "?")
            enabled  = auto.get("enabled", True)
            runs     = auto.get("run_count", 0)
            status   = "✅" if enabled else "⏸️"
            last_ts  = self._last_run.get(auto["id"], 0)
            last_str = ""
            if last_ts:
                import time as _t
                mins_ago = int((_t.time() - last_ts) / 60)
                if mins_ago < 60:
                    last_str = f" | ultima: {mins_ago} min fa"
                else:
                    last_str = f" | ultima: {mins_ago // 60}h fa"

            lines.append(f"  {status} <b>{i}.</b> {label}")
            lines.append(f"      🔁 eseguita {runs}×{last_str}")

        lines.append(
            "\n<i>"
            "/cancella_automazione N — cancella\n"
            "/pausa_automazione N — metti in pausa\n"
            "/riprendi_automazione N — riattiva"
            "</i>"
        )
        return "\n".join(lines)

    def automation_detail(self, index: int) -> str:
        """Mostra dettaglio di una singola automazione."""
        st = self._sorted()
        idx = index - 1
        if not (0 <= idx < len(st)):
            return f"⚠️ Nessuna automazione numero {index}."
        auto   = st[idx]
        label  = auto.get("label", "?")
        text   = auto.get("raw_text", "")
        trigger = auto.get("trigger", {})
        conds   = auto.get("conditions", [])
        action  = auto.get("action", {})
        enabled = auto.get("enabled", True)
        runs    = auto.get("run_count", 0)
        cooldown = auto.get("cooldown_seconds", DEFAULT_COOLDOWN)

        lines = [f"🤖 <b>Automazione {index}: {label}</b>\n"]
        lines.append(f"📝 Descrizione: <i>{text}</i>")
        lines.append(f"{'✅ Attiva' if enabled else '⏸️ In pausa'} | eseguita {runs}× | cooldown {cooldown}s\n")
        lines.append(f"⚡ <b>Trigger:</b> {json.dumps(trigger, ensure_ascii=False)}")
        if conds:
            lines.append(f"🔍 <b>Condizioni:</b> {json.dumps(conds, ensure_ascii=False)}")
        lines.append(f"🎯 <b>Azione:</b> {json.dumps(action, ensure_ascii=False)}")
        return "\n".join(lines)
