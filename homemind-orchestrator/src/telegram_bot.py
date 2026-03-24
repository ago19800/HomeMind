"""
telegram_bot.py — Bot Telegram bidirezionale per HomeMind.
Risposte formattate con emoji e HTML Telegram.
"""
import asyncio, logging, json, re
import aiohttp
from pathlib import Path
from datetime import datetime
from translations import t, set_lang, get_lang, alarm_state_label, load_lang_from_config
from agent.location_tracker import get_person_stops, format_stops_message
from agent.memory_manager  import MemoryManager
from agent.routine_manager  import RoutineManager

# Carica lingua salvata in person_config.json all'avvio
load_lang_from_config()

logger = logging.getLogger("homemind.tgbot")
TG_API = "https://api.telegram.org"
POLL_TIMEOUT = 30



def _remove_action_tags(text: str) -> str:
    """Rimuove [CALL_SERVICE:...] e [GET_HISTORY:...] anche con JSON annidato (es. rgb_color:[255,0,0])."""
    import re as _re
    # Prima rimuovi i tag semplici (senza JSON annidato) con regex veloce
    # Poi usa bracket-counting per quelli con JSON che contengono ]
    result = []
    i = 0
    tags = ("[CALL_SERVICE:", "[GET_HISTORY:", "[CREATE_AUTOMATION:")
    while i < len(text):
        matched = False
        for tag in tags:
            if text[i:i+len(tag)] == tag:
                depth = 1
                j = i + 1
                while j < len(text) and depth > 0:
                    if text[j] == "[":
                        depth += 1
                    elif text[j] == "]":
                        depth -= 1
                    j += 1
                i = j
                matched = True
                break
        if not matched:
            result.append(text[i])
            i += 1
    # Pulizia spazi multipli residui
    cleaned = _re.sub(r" {2,}", " ", "".join(result)).strip()
    return cleaned

class TelegramBot:
    def __init__(self, token, allowed_chat_ids, ai_callback, action_callback,
                 context_callback, spazzatura_callback=None, update_checker=None,
                 automations_mgr=None, history_client=None,
                 repairs_checker=None, state_cache_cb=None, briefing_cb=None,
                 genera_dashboard_cb=None, ai_action_cb=None, card_luci_cb=None,
                 ai_provider=None, energy_analyzer=None, appliance_monitor=None,
                 solar_optimizer=None, routine_manager=None, task_scheduler=None,
                 power_guard=None, config_editor=None,
                 rest_client=None, frigate_client=None):
        self.token    = token.strip()
        self.allowed  = {str(c).strip() for c in allowed_chat_ids if c}
        self.ai_cb    = ai_callback
        self.action_cb= action_callback
        self.context_cb=context_callback
        self.spazzatura_cb   = spazzatura_callback
        self.update_checker  = update_checker
        self.automations_mgr = automations_mgr
        self.history_client  = history_client
        self.repairs_checker = repairs_checker
        self.state_cache_cb  = state_cache_cb
        self.briefing_cb     = briefing_cb
        self.genera_dashboard_cb = genera_dashboard_cb
        self.ai_action_cb    = ai_action_cb
        self.card_luci_cb    = card_luci_cb
        self._ai_provider_ref   = ai_provider
        self._energy_analyzer   = energy_analyzer
        self._appliance_monitor = appliance_monitor
        self._solar_optimizer   = solar_optimizer
        self._memory = MemoryManager(ai=ai_provider)
        self._routine = routine_manager
        self._task_scheduler = task_scheduler
        self._power_guard    = power_guard
        self._config_editor  = config_editor
        self._rest_client       = rest_client
        self._frigate_client    = frigate_client
        self._session = None
        self._offset  = 0
        self._running = False
        self._histories = {}          # entity_id storico HA
        self._conv_memory: dict = {}  # chat_id → [(role, text, timestamp), ...]

    async def start(self):
        if not self.token:
            logger.info("Telegram bot: token mancante — disabilitato")
            return
        self._session = aiohttp.ClientSession()
        try:
            info = await self._api("getMe")
            name = info.get("result",{}).get("username","?")
            logger.info("Telegram bot connesso: @%s | Chat autorizzate: %s", name, self.allowed)
        except Exception as e:
            logger.error("Telegram bot getMe FAIL: %s", e)
            return
        try:
            await self._api("getUpdates", {"offset": -1, "timeout": 1})
            logger.info("Telegram: coda update resettata")
        except Exception:
            pass
        self._running = True
        asyncio.create_task(self._poll_loop(), name="tg_poll")

    async def stop(self):
        self._running = False
        if self._session:
            await self._session.close()

    async def _poll_loop(self):
        logger.info("Telegram bot: avvio polling...")
        while self._running:
            try:
                updates = await self._api("getUpdates", {
                    "offset": self._offset,
                    "timeout": POLL_TIMEOUT,
                    "allowed_updates": ["message"],
                })
                for upd in updates.get("result", []):
                    self._offset = upd["update_id"] + 1
                    asyncio.create_task(self._handle_update(upd))
            except asyncio.CancelledError:
                break
            except Exception as e:
                err = str(e)
                if "409" in err or "Conflict" in err:
                    logger.warning("TG 409: altra istanza attiva — riprovo tra 30s. "
                                   "Crea un bot separato con @BotFather per HomeMind.")
                    try:
                        await self._api("getUpdates", {"offset": -1, "timeout": 1})
                    except Exception:
                        pass
                    await asyncio.sleep(30)
                elif "401" in err:
                    logger.error("TG 401: token non valido — bot disabilitato")
                    self._running = False
                    break
                else:
                    logger.warning("Poll error: %s", e)
                    await asyncio.sleep(5)

    async def _handle_update(self, upd):
        msg     = upd.get("message", {})
        if not msg:
            return
        chat_id  = str(msg.get("chat",{}).get("id",""))
        text     = msg.get("text","").strip()
        username = msg.get("from",{}).get("username","?")

        # ── Gestione messaggi vocali ──────────────────────────────────────────
        voice   = msg.get("voice") or msg.get("audio")
        if voice and not text:
            if self.allowed and chat_id not in self.allowed:
                logger.warning("TG: accesso negato chat_id=%s", chat_id)
                await self._send(chat_id, t("unauthorized"))
                return
            await self._typing(chat_id)
            transcribed = await self._transcribe_voice(chat_id, voice)
            if transcribed:
                text = transcribed
                await self._send(chat_id, f"🎙️ <i>Ho capito: {text}</i>")
            else:
                await self._send(chat_id, "❌ Non sono riuscito a trascrivere il messaggio vocale.\nAssicurati di avere una API key OpenAI configurata.")
                return

        if not text:
            return
        if self.allowed and chat_id not in self.allowed:
            logger.warning("TG: accesso negato chat_id=%s", chat_id)  # username omesso per privacy
            await self._send(chat_id, t("unauthorized"))
            return
        logger.debug("TG msg da %s: [%d chars]", chat_id, len(text))  # contenuto non loggato per privacy
        await self._typing(chat_id)

        # Intercetta conferme solare — solo se NON è un comando esplicito
        _is_command = text.strip().startswith("/") or len(text.strip()) > 30
        if (self._solar_optimizer and self._solar_optimizer._pending_confirm
                and not _is_command):
            handled = await self._solar_optimizer.handle_confirm(text)
            if handled:
                return

        # Intercetta conferme routine
        if (self._routine and self._routine._pending_action
                and not _is_command):
            handled = await self._routine.handle_confirm(text)
            if handled:
                return

        # Intercetta conferme power guard
        if (self._power_guard and self._power_guard._pending_off
                and not _is_command):
            handled = await self._power_guard.handle_confirm(text)
            if handled:
                return

        # Intercetta conferme config editor
        if self._config_editor and self._config_editor._pending:
            handled = await self._config_editor.handle_confirm(text)
            if handled:
                return

        # Rilevamento modifiche config in linguaggio naturale
        if self._config_editor and not _is_command:
            handled = await self._try_config_edit(chat_id, text)
            if handled:
                return

        # Rilevamento task temporali — "accendi X alle 19"
        if self._task_scheduler:
            handled = await self._try_schedule_task(chat_id, text)
            if handled:
                return

        quick = self._quick_command(text)

        # Gestione comandi async speciali
        if quick == "__RICARICA_SPAZZATURA__":
            await self._send(chat_id, t("trash_loading"))
            if self.spazzatura_cb:
                sz = self.spazzatura_cb()
                if sz:
                    result = await sz.reload()
                    await self._send(chat_id, result)
                    if sz.calendar:
                        await self._send(chat_id, sz.telegram_summary())
                else:
                    await self._send(chat_id, t("trash_unavailable"))
            else:
                await self._send(chat_id, t("trash_unavailable"))
            return

        if quick == "__AUTO_HELP__":
            await self._send(chat_id, t("auto_help"))
            return

        if quick == "__CHECK_UPDATES__":
            await self._send(chat_id, t("checking_updates"))
            try:
                result = await self.update_checker.check_now()
                await self._send(chat_id, result)
            except Exception as e:
                await self._send(chat_id, t("error_update", msg=str(e)[:100]))
            return

        if quick == "__CARD_LUCI__":
            if self.card_luci_cb:
                raw = text.strip()
                user_yaml = ""
                for trigger in ("crea card luci:", "crea card luci", "card luci:", "card luci",
                                "create card lights:", "create card lights"):
                    if raw.lower().startswith(trigger):
                        rest = raw[len(trigger):].strip()
                        if rest:
                            user_yaml = rest
                        break
                yaml_out = self.card_luci_cb(user_yaml)
                await self._send(chat_id, t("card_luci_header") + "\n\n" + yaml_out)
            else:
                await self._send(chat_id, t("module_unavailable"))
            return

        if quick == "__CREA_CARD__":
            raw_text = text.strip()

            # Estrai eventuale stile richiesto: "crea card mushroom: ..." o "crea card energia:"
            card_style = "mushroom"  # default
            yaml_base  = None

            STYLE_ALIASES = {
                "mushroom":   "mushroom",
                "bubble":     "bubble",
                "gauge":      "gauge",
                "energia":    "energia",
                "energy":     "energia",
                "tile":       "tile",
                "minimal":    "tile",
                "grafico":    "gauge",
                "termometro": "gauge",
                # English aliases
                "lights":     "mushroom",   # "create card lights: ..." → mushroom
                "security":   "mushroom",
                "sicurezza":  "mushroom",
                "chart":      "gauge",
                "graph":      "gauge",
            }

            # Analizza il testo: cerca trigger + stile opzionale + YAML
            for trigger in ("/crea_card", "/create_card",
                            "crea card:", "crea card", "genera card:", "genera card", "crea una card",
                            "create card:", "create card", "generate card:", "generate card"):
                if raw_text.lower().startswith(trigger.lower()):
                    rest = raw_text[len(trigger):].strip()
                    # Controlla se la prima parola è uno stile (con o senza ":")
                    first_word = rest.split()[0].lower().rstrip(":") if rest.split() else ""
                    if first_word in STYLE_ALIASES:
                        card_style = STYLE_ALIASES[first_word]
                        # Salta la prima parola (stile) per estrarre lo YAML
                        after_style = rest.split(None, 1)
                        rest = after_style[1].strip(" :\n") if len(after_style) > 1 else ""
                    # Il resto è lo YAML
                    if rest and any(k in rest for k in ("entity", "type:", "sensor", "binary", "light", "sensor", "input_")):
                        yaml_base = rest
                    elif rest:
                        # Non è YAML ma potrebbe essere una descrizione ("tutte le temperature")
                        # Passa al genera_dashboard_cb come keyword hint nel titolo dello YAML
                        yaml_base = (
                            f"type: entities\n"
                            f"title: {rest.strip(': ')}\n"
                            f"entities: []\n"
                            f"# KEYWORD_HINT: {rest.strip()}"
                        )
                    break

            # Senza YAML: per stili noti auto-genera YAML da state_cache
            if not yaml_base:
                AUTO_STYLES = {
                    "energia", "energy", "lights", "mushroom", "tile", "gauge", "bubble",
                }
                if card_style in AUTO_STYLES and self.state_cache_cb:
                    cache = self.state_cache_cb()
                    # Seleziona entità rilevanti per lo stile
                    if card_style in ("energia", "energy"):
                        energy_kw = ("fv", "solar", "enel", "grid", "consumo", "consumption",
                                     "energy", "batteria", "battery", "watt", "power", "pv")
                        ents = [eid for eid in cache
                                if any(k in eid.lower() for k in energy_kw)
                                and cache[eid].get("state") not in ("unavailable", "unknown")][:12]
                        title = "Energy" if get_lang() == "en" else "Energia"
                    elif card_style in ("lights",):
                        card_style = "mushroom"  # lights → mushroom style
                        ents = [eid for eid in cache if eid.startswith("light.")][:12]
                        title = "Lights" if get_lang() == "en" else "Luci"
                    else:
                        ents = []
                        title = card_style.title()

                    if ents:
                        ent_lines_yaml = "\n".join(f"  - {e}" for e in ents)
                        yaml_base = f"type: entities\ntitle: {title}\nentities:\n{ent_lines_yaml}"
                    else:
                        # Nessuna entità trovata → mostra guida
                        await self._send(chat_id, t("card_style_help", style=card_style))
                        return
                else:
                    await self._send(chat_id, t("card_style_help", style=card_style))
                    return

            await self._send(chat_id, t("card_generating", style=card_style))

            if self.genera_dashboard_cb:
                try:
                    card_yaml = await self.genera_dashboard_cb(yaml_base, mode=f"card_{card_style}")
                    import html as _html
                    card_yaml_safe = _html.escape(card_yaml)
                    await self._send(chat_id,
                        t("card_ready", style=card_style) + f"\n\n<pre>{card_yaml_safe[:3800]}</pre>")
                except Exception as e:
                    logger.error("CREA_CARD error: %s", e, exc_info=True)
                    await self._send(chat_id, t("card_error", msg=str(e)[:200]))
            else:
                await self._send(chat_id, t("ai_unavailable"))
            return


        if quick == "__CHECK_REPAIRS__":
            await self._send(chat_id, t("checking_repairs"))
            try:
                result = await self.repairs_checker.get_repairs_summary()
                await self._send(chat_id, result)
            except Exception as e:
                await self._send(chat_id, t("error_short", msg=str(e)[:100]))
            return

        if quick == "__RESET_MEMORY__":
            self._conv_memory[chat_id] = []
            await self._send(chat_id, "🧹 Memoria conversazione azzerata. Ripartiamo da zero!")
            return

        if quick == "__ROUTINE__":
            if self._routine:
                await self._send(chat_id, self._routine.get_status())
            else:
                await self._send(chat_id, "📅 Routine Manager non disponibile.")
            return

        if quick == "__POWER_GUARD_STATUS__":
            if self._power_guard:
                await self._send(chat_id, self._power_guard.get_status())
            else:
                await self._send(chat_id, "⚡ Power Guard non disponibile.")
            return

        if quick == "__POWERGUARD__":
            if self._power_guard:
                await self._send(chat_id, self._power_guard.get_status())
            else:
                await self._send(chat_id, "⚡ Power Guard non disponibile.")
            return

        if quick == "__TASK_LIST__":
            if self._task_scheduler:
                from translations import get_lang
                lang = get_lang()
                if lang == "en":
                    msg = self._task_scheduler.get_tasks_display_en()
                else:
                    msg = self._task_scheduler.get_tasks_display()
                await self._send(chat_id, msg)
            else:
                await self._send(chat_id, "⏰ Task Scheduler non disponibile.")
            return

        if quick == "__CONFIG_SHOW__":
            if self._config_editor:
                await self._send(chat_id, self._config_editor.get_config_display())
            else:
                await self._send(chat_id, "⚙️ Config Editor non disponibile.")
            return

        if quick == "__CONFIG_RESET__":
            if self._config_editor:
                self._config_editor.set_pending({"action": "__reset__", "preview": "reset"})
                await self._send(chat_id,
                    "⚠️ <b>Attenzione!</b>\n"
                    "Stai per ripristinare il config di default.\n"
                    "Il backup attuale verrà conservato.\n\n"
                    "Confermi? (sì/no)")
            return

        if quick == "__TASK_CLEAR__":
            if self._task_scheduler:
                self._task_scheduler.clear_all()
                await self._send(chat_id, "⏰ Tutti i task cancellati.")
            return

        if isinstance(quick, str) and quick.startswith("__TASK_CANCEL__"):
            if self._task_scheduler:
                num_str = quick.replace("__TASK_CANCEL__", "").strip()
                try:
                    num = int(num_str)
                    task = self._task_scheduler.cancel_by_index(num)
                    if task:
                        await self._send(chat_id,
                            f"⏰ Task cancellato: <b>{task['label']}</b>")
                    else:
                        await self._send(chat_id, f"⏰ Nessun task numero {num}.")
                except ValueError:
                    await self._send(chat_id,
                        "⏰ Scrivi /cancella_task N (es. /cancella_task 1)")
            return

        if quick == "__MEMORY__":
            await self._send(chat_id, self._memory.get_facts_display())
            return

        if quick == "__MEMORY_RESET__":
            count = self._memory.reset()
            await self._send(chat_id, f"🧠 Memoria cancellata — {count} fatti rimossi.")
            return

        if isinstance(quick, str) and quick.startswith("__MEMORY_FORGET__"):
            query = quick.replace("__MEMORY_FORGET__", "")
            removed = self._memory.forget(query)
            if removed:
                await self._send(chat_id, f"🧠 Rimossi {removed} fatti contenenti \"{query}\"")
            else:
                await self._send(chat_id, f"🧠 Nessun fatto trovato contenente \"{query}\"")
            return

        if quick == "__SOLAR__":
            so = self._solar_optimizer
            if so:
                await self._send(chat_id, so.get_status_message())
            else:
                await self._send(chat_id, "☀️ Ottimizzatore solare non configurato.")
            return

        if quick == "__APPLIANCES__":
            am = self._appliance_monitor
            if am:
                await self._send(chat_id, am.status_message())
            else:
                await self._send(chat_id, "🔌 Appliance monitor non disponibile.")
            return

        if quick == "__APPLIANCES_DEBUG__":
            am = self._appliance_monitor
            if am:
                await self._send(chat_id, am.debug_sensor())
            else:
                await self._send(chat_id, "🔌 Appliance monitor non disponibile.")
            return

        if quick == "__ENERGY_ANALYSIS__":
            if self._energy_analyzer:
                await self._typing(chat_id)
                report = await self._energy_analyzer.analyze_on_demand(period_days=7)
                await self._send(chat_id, report + self._ai_footer())
            else:
                await self._send(chat_id, "📊 Energy Analyzer non disponibile.")
            return

        if quick in ("__ENERGY_TODAY__", "__ENERGY_YESTERDAY__"):
            period = t("energy_period_today") if quick == "__ENERGY_TODAY__" else t("energy_period_yesterday")
            await self._typing(chat_id)
            try:
                result = await self.history_client.energy_summary(period)
                await self._send(chat_id, result)
                # Salva in memoria per contesto "e ieri?" successivo
                import time as _t
                _mem = self._conv_memory.get(chat_id, [])
                _mem.append(("user",      text,   _t.time()))
                _mem.append(("assistant", result, _t.time()))
                self._conv_memory[chat_id] = _mem[-16:]
            except Exception as e:
                await self._send(chat_id, t("error_short", msg=str(e)[:100]))
            return

        if quick == "__LIST_AUTOMATIONS__":
            await self._typing(chat_id)
            try:
                cache = self.state_cache_cb() if self.state_cache_cb else {}
                result = await self.automations_mgr.list_automations(cache)
                await self._send(chat_id, result)
            except Exception as e:
                await self._send(chat_id, t("error_short", msg=str(e)[:100]))
            return

        if quick == "__PROVIDERS__":
            if not (hasattr(self, "_ai_provider_ref") and self._ai_provider_ref):
                await self._send(chat_id, "🤖 <b>AI Provider:</b> info non disponibile")
                return

            import html as _html
            ai_ref = self._ai_provider_ref
            medals = ["🥇","🥈","🥉"]

            await self._typing(chat_id)
            lines = ["🤖 <b>Test AI Provider</b>\n"]

            for i, p in enumerate(ai_ref._providers):
                m = medals[i] if i < 3 else f"{i+1}."
                try:
                    reply = await p.ask(
                        system="You are a test. Reply with exactly one word: OK",
                        user="Say OK",
                        max_tokens=10,
                    )
                    r = _html.escape(reply.strip()[:30])
                    lines.append(f"{m} ✅ <b>{_html.escape(p.display)}</b>")
                    lines.append(f"   <code>{_html.escape(p.model)}</code>")
                    lines.append(f"   <i>Risposta: {r}</i>")
                except Exception as e:
                    err = str(e); el = err.lower()
                    if "401" in err or "invalid_api_key" in el or "unauthorized" in el:
                        reason = "API key non valida — controlla le Opzioni addon"
                    elif "429" in err or "rate_limit" in el:
                        reason = "Rate limit — riprova tra un minuto"
                    elif "quota" in el:
                        reason = "Quota giornaliera esaurita"
                    elif "model_not_found" in el or "404" in err:
                        reason = "Modello non trovato — cambia nome nelle Opzioni"
                    elif "connection" in el or "timeout" in el:
                        reason = "Connessione fallita"
                    else:
                        reason = _html.escape(err[:80])
                    lines.append(f"{m} ❌ <b>{_html.escape(p.display)}</b>")
                    lines.append(f"   <code>{_html.escape(p.model)}</code>")
                    lines.append(f"   <i>⚠️ {reason}</i>")
                lines.append("")

            last = getattr(ai_ref, "_last_used", None)
            if last:
                lines.append(f"⚡ <b>Attivo ora:</b> {_html.escape(last.display)}")

            await self._send(chat_id, "\n".join(lines))
            return

        if quick == "__BRIEFING_NOW__":
            await self._send(chat_id, t("briefing_loading"))
            try:
                if self.briefing_cb:
                    await self.briefing_cb()
                else:
                    await self._send(chat_id, t("briefing_unavailable"))
            except Exception as e:
                await self._send(chat_id, t("error_short", msg=str(e)[:100]))
            return

        if quick is not None:
            await self._send(chat_id, quick)
            return
        await self._ai_reply(chat_id, text)

    def _quick_command(self, text):
        cmd = text.lower().strip()

        if cmd in ("/start", "start", "ciao", "hello", "help", "/help"):
            return t("start_msg")

        if cmd in ("/comandi", "comandi", "/aiuto", "aiuto", "/commands", "commands",
                   "/help it", "/help en", "lista comandi", "elenco comandi",
                   "cosa sai fare", "cosa puoi fare", "quali comandi", "che comandi",
                   "what can you do", "list commands", "show commands"):
            return t("commands_list")

        if cmd in ("/lingua", "/lang"):
            return t("lang_current")

        if cmd.startswith("/lingua ") or cmd.startswith("/lang "):
            lang_arg = cmd.split(None, 1)[-1].strip().lower()
            if set_lang(lang_arg):
                return t("lang_changed")
            return t("lang_unknown")

        if cmd in ("/spazzatura", "spazzatura", "raccolta", "rifiuti", "/trash", "trash"):
            if self.spazzatura_cb:
                sz = self.spazzatura_cb()
                if sz:
                    return sz.telegram_summary()
            return "Modulo spazzatura non disponibile."

        if cmd in ("/ricarica_spazzatura", "ricarica spazzatura", "/reload_trash", "reload trash", "reload_trash"):
            return "__RICARICA_SPAZZATURA__"

        if cmd in ("/aggiornamenti", "aggiornamenti", "update", "updates", "controlla aggiornamenti",
                   "/updates", "/update", "check updates"):
            if self.update_checker:
                return "__CHECK_UPDATES__"
            return "Modulo aggiornamenti non disponibile."

        if cmd in ("/riparazioni", "riparazioni", "repairs", "problemi ha", "/repairs", "repair"):
            return "__CHECK_REPAIRS__"

        if cmd in ("/energia", "energia oggi", "energia", "produzione oggi", "/energy", "energy", "energy today"):
            return "__ENERGY_TODAY__"

        if cmd in ("/dimentica", "dimentica", "resetta memoria", "nuova conversazione",
                   "/reset", "reset chat", "forget", "/forget"):
            return "__RESET_MEMORY__"

        if cmd in ("/routine", "routine", "mia routine", "le mie abitudini",
                   "cosa hai imparato", "abitudini", "/abitudini"):
            return "__ROUTINE__"

        if cmd in ("/powerguard", "/pg", "powerguard", "power guard",
                   "protezione enel", "soglia enel", "consumo soglia",
                   "power protection", "enel limit"):
            return "__POWER_GUARD_STATUS__"

        if cmd in ("/powerguard", "/pg", "powerguard", "power guard",
                   "soglia enel", "protezione soglia", "consumo soglia",
                   "power protection", "energy guard"):
            return "__POWERGUARD__"

        if cmd in ("/task", "/tasks", "task", "tasks",
                   "lista task", "task in coda", "cosa hai schedulato",
                   "scheduled tasks", "what is scheduled"):
            return "__TASK_LIST__"

        if cmd in ("/config", "config", "configurazione",
                   "mostra config", "show config", "impostazioni"):
            return "__CONFIG_SHOW__"

        if cmd in ("/config reset", "config reset",
                   "reset config", "ripristina config"):
            return "__CONFIG_RESET__"

        if cmd in ("/cancella_task", "cancella tutti task",
                   "svuota task", "clear all tasks", "cancella tutti i task"):
            return "__TASK_CLEAR__"

        # /cancella_task N
        _cancel_m = re.match(r'^/?(cancella_task|cancel_task)\s+(\d+)$', cmd)
        if _cancel_m:
            return f"__TASK_CANCEL__{_cancel_m.group(2)}"

        if cmd in ("/memoria", "memoria", "cosa sai", "cosa ricordi",
                   "cosa sai di me", "memory", "/memory"):
            return "__MEMORY__"

        if cmd in ("/memoria reset", "memoria reset", "dimentica tutto",
                   "cancella memoria", "reset memoria", "memory reset"):
            return "__MEMORY_RESET__"

        if cmd.startswith("/dimentica ") or cmd.startswith("dimentica "):
            query = text.split(" ", 1)[1] if " " in text else ""
            return f"__MEMORY_FORGET__{query}"

        if cmd in ("/solare", "solare", "surplus", "fotovoltaico", "solar",
                   "ottimizzatore", "/solar", "energia solare"):
            return "__SOLAR__"

        if cmd in ("/elettrodomestici", "elettrodomestici", "stato elettrodomestici",
                   "/appliances", "appliances", "lavatrice", "/lavatrice",
                   "lavastoviglie", "/lavastoviglie", "asciugatrice", "/asciugatrice",
                   "forno", "/forno", "stato lavatrice", "stato lavastoviglie"):
            return "__APPLIANCES__"

        if cmd in ("/debug_elettrodomestici", "debug elettrodomestici",
                   "/debug_appliances", "test elettrodomestici", "test lavatrice"):
            return "__APPLIANCES_DEBUG__"

        if cmd in ("/energia_analisi", "energia analisi", "analisi energia",
                   "/energy_analysis", "energy analysis", "analizza energia storico"):
            return "__ENERGY_ANALYSIS__"

        if cmd in ("/ieri", "energia ieri", "ieri", "/yesterday", "yesterday", "energy yesterday",
                   "e ieri", "e ieri?", "e ieri ?", "ieri?", "e ieri cosa", "e ieri come"):
            return "__ENERGY_YESTERDAY__"

        if cmd in ("/automazioni", "automazioni", "lista automazioni", "/automations", "automations"):
            return "__LIST_AUTOMATIONS__"

        if cmd in ("/automazioni_help", "automazioni help", "guida automazioni", "come creare automazioni",
                   "help automazioni", "/automations_help", "automations help", "automation guide"):
            return "__AUTO_HELP__"

        if cmd in ("/crea_card", "crea card", "genera card", "crea una card",
                   "/create_card", "create card", "generate card"):
            return "__CREA_CARD__"

        ml_cmd = cmd.lower()

        # Card luci stanze — Room Lights Graph Card (controlla PRIMA degli stili generici)
        import re as _re
        if (_re.search(r'\bcard luci\b', ml_cmd) or
                _re.search(r'\bcard stanze\b', ml_cmd) or
                "room lights" in ml_cmd or
                _re.search(r'\bcard lights?\b', ml_cmd)):
            return "__CARD_LUCI__"

        # "crea card X" / "create card X" con qualsiasi stile o YAML → sempre __CREA_CARD__
        CARD_TRIGGERS = (
            "crea card ", "genera card ", "/crea_card ", "crea una card ",
            "create card ", "generate card ", "/create_card ",
        )
        for ct in CARD_TRIGGERS:
            if ml_cmd.startswith(ct):
                rest = ml_cmd[len(ct):].strip()
                if rest:  # c'è qualcosa dopo il trigger (stile o YAML)
                    return "__CREA_CARD__"

        # Accetta "crea card:" / "create card:" con YAML inline
        if (cmd.startswith("crea card:") or cmd.startswith("genera card:") or
                cmd.startswith("create card:") or cmd.startswith("generate card:")):
            return "__CREA_CARD__"

        if cmd in ("/providers", "providers", "ai providers", "/ai_providers"):
            return "__PROVIDERS__"

        if cmd in ("/briefing", "briefing", "buongiorno", "riassunto", "morning briefing"):
            return "__BRIEFING_NOW__"

        if cmd in ("/allarme", "allarme", "stato allarme", "allarme stato", "/alarm", "alarm", "alarm status"):
            if self.state_cache_cb:
                cache = self.state_cache_cb()
                alarm = next(
                    ((eid, s) for eid, s in cache.items()
                     if eid.startswith("alarm_control_panel.")),
                    None
                )
                if alarm:
                    eid, s = alarm
                    st   = s.get("state", "unknown")
                    name = s.get("attributes", {}).get("friendly_name", eid)
                    stato_str = alarm_state_label(st) or f"❓ {st}"
                    return f"🔔 <b>Allarme:</b> {stato_str}\n<i>{name}</i>"
            return None  # lascia all'AI

        if cmd in ("/stato", "stato casa", "stato della casa", "/status", "home status"):
            if not self.state_cache_cb:
                return None
            cache = self.state_cache_cb()
            lines = [t("home_status_header"), "──────────────────"]

            # Persone — applica whitelist e blacklist dal config
            from agent.home_model import HomeModel as _HM
            _cfg_path = Path("/config/homemind_patches/person_config.json")
            _whitelist, _blacklist = [], []
            try:
                if _cfg_path.exists():
                    _cfg = json.loads(_cfg_path.read_text(encoding="utf-8-sig"))
                    _whitelist = [e.lower() for e in _cfg.get("person_whitelist", [])]
                    _blacklist  = [e.lower() for e in _cfg.get("person_blacklist", [])]
            except Exception:
                pass
            persons = {}
            for eid, s in cache.items():
                if not eid.startswith("person."):
                    continue
                eid_low = eid.lower()
                if eid_low in _blacklist:
                    continue  # escludi blacklist
                if _whitelist and eid_low not in _whitelist:
                    continue  # escludi se non in whitelist
                persons[eid] = s
            in_casa = [s.get("attributes", {}).get("friendly_name", eid)
                       for eid, s in persons.items() if s.get("state") == "home"]
            fuori   = [s.get("attributes", {}).get("friendly_name", eid)
                       for eid, s in persons.items() if s.get("state") != "home"]
            if in_casa:
                lines.append("👤 <b>In casa:</b> " + ", ".join(in_casa))
            else:
                lines.append("👤 <b>In casa:</b> Nessuno")
            if fuori:
                lines.append("🚗 <b>Fuori:</b> " + ", ".join(fuori))

            # Allarme
            # Usa alarm_panel dal config se disponibile
            _ap_override = getattr(self._home_ref, "_alarm_panel_override", "") if hasattr(self, "_home_ref") else ""
            if _ap_override and _ap_override in cache:
                alarm = (_ap_override, cache[_ap_override])
            else:
                alarm = next(((eid, s) for eid, s in cache.items()
                              if eid.startswith("alarm_control_panel.")), None)
            if alarm:
                st = alarm[1].get("state", "unknown")
                lines.append("🔔 <b>Allarme:</b> " + alarm_state_label(st))

            # Luci accese
            luci_on = [s.get("attributes", {}).get("friendly_name", eid)
                       for eid, s in cache.items()
                       if eid.startswith("light.") and s.get("state") == "on"]
            if luci_on:
                lines.append(t("lights_on", n=len(luci_on), names=", ".join(luci_on[:5])
                              + ("…" if len(luci_on) > 5 else "")))
            else:
                lines.append(t("lights_all_off"))

            # Temperature principali
            temp_sensors = [(eid, s) for eid, s in cache.items()
                            if eid.startswith("sensor.") and
                            s.get("attributes", {}).get("unit_of_measurement") == "°C" and
                            s.get("state") not in ("unavailable", "unknown")]
            # Filtra sensori temperatura rilevanti (escludi CPU, sistema, ecc.)
            TEMP_EXCLUDE = ("cpu", "processor", "system", "proxmox", "cpu_temp",
                            "raspberry", "board", "soc", "thermal")
            temp_filtered = [(eid, s) for eid, s in temp_sensors
                             if not any(k in eid.lower() or
                                        k in s.get("attributes",{}).get("friendly_name","").lower()
                                        for k in TEMP_EXCLUDE)]
            # Se dopo filtro non rimane nulla, mostra tutti
            temp_show = temp_filtered if temp_filtered else temp_sensors
            if temp_show:
                lines.append("🌡️ <b>Temperature:</b>")
                for eid, s in temp_show:
                    name = s.get("attributes", {}).get("friendly_name", eid)
                    lines.append(f"   {name}: {s.get('state')}°C")

            return "\n".join(lines)

        return None

    async def _try_config_edit(self, chat_id: str, text: str) -> bool:
        """
        Rileva se il messaggio è una richiesta di modifica config.
        Se sì, mostra anteprima e chiede conferma.
        Ritorna True se il messaggio è stato gestito.
        """
        if not self._config_editor:
            return False
        # Parole chiave che indicano intenzione di modifica config
        CONFIG_TRIGGERS = [
            "aggiungi person.", "add person.",
            "escludi person.", "blacklist person.",
            "rimuovi person.", "remove person.",
            "soglia enel", "soglia power", "enel watt",
            "power guard", "powerguard",
            "notifica spazzatura", "trash notification",
            "soglia proximity", "proximity threshold",
            "temperatura massima clima", "max temp clima",
            "cambia lingua", "change language",
        ]
        text_low = text.lower()
        if not any(trigger in text_low for trigger in CONFIG_TRIGGERS):
            return False
        intent = self._config_editor.detect_intent(text)
        if not intent:
            return False
        # Mostra anteprima e chiedi conferma
        from translations import get_lang
        lang = get_lang()
        preview = intent.get("preview", "modifica config")
        if lang == "en":
            msg = (f"⚙️ <b>Config change detected:</b>\n"
                   f"{preview}\n\n"
                   f"Apply this change? (yes/no)")
        else:
            msg = (f"⚙️ <b>Modifica config rilevata:</b>\n"
                   f"{preview}\n\n"
                   f"Applico questa modifica? (sì/no)")
        self._config_editor.set_pending(intent)
        await self._send(chat_id, msg)
        return True

    async def _try_schedule_task(self, chat_id: str, text: str) -> bool:
        """
        Controlla se il messaggio contiene un'indicazione temporale.
        Se sì, schedula il task e ritorna True (messaggio già gestito).
        Se no, ritorna False (il messaggio va processato normalmente).
        """
        import re as _re
        text_low = text.lower().strip()

        # Pattern temporali IT e EN
        TIME_PATTERNS = [
            r'alle\s+ore\s+\d{1,2}(:\d{2})?',   # alle ore 21:38
            r'alle\s+\d{1,2}(:\d{2})?',          # alle 19 / alle 19:30
            r'ore\s+\d{1,2}(:\d{2})?',           # ore 21:38
            r'at\s+\d{1,2}(:\d{2})?',             # at 7 / at 19:30
            r'tra\s+\d+\s+(minut|or[ae]|giorni?)', # tra 30 min / tra 2 ore / tra 3 giorni
            r'in\s+\d+\s+(minute|hour|day)',      # in 30 min / in 2 hours / in 3 days
            r'domani',                               # domani (qualsiasi forma)
            r'tomorrow',                             # tomorrow
            r'(lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)', # giorni IT
            r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', # giorni EN
            r'\d{1,2}\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|'
            r'luglio|agosto|settembre|ottobre|novembre|dicembre)',          # date IT
            r'(january|february|march|april|may|june|july|august|'
            r'september|october|november|december)\s+\d{1,2}',            # date EN
        ]

        has_time = any(_re.search(p, text_low) for p in TIME_PATTERNS)
        if not has_time:
            return False

        # Controlla che ci sia anche un'azione (non solo un'ora)
        ACTION_WORDS_IT = ['accendi', 'spegni', 'imposta', 'avvia', 'ferma',
                          'abbassa', 'alza', 'apri', 'chiudi', 'arma', 'disarma']
        ACTION_WORDS_EN = ['turn on', 'turn off', 'set', 'start', 'stop',
                          'lower', 'raise', 'open', 'close', 'arm', 'disarm']
        all_actions = ACTION_WORDS_IT + ACTION_WORDS_EN
        has_action = any(w in text_low for w in all_actions)
        if not has_action:
            return False

        # Estrai orario
        execute_at = self._task_scheduler.parse_time(text)
        if not execute_at:
            return False

        # Costruisci label leggibile
        from datetime import datetime as _dt
        dt = _dt.fromtimestamp(execute_at)
        import time as _time
        diff = execute_at - _time.time()
        if diff < 120:  # meno di 2 minuti
            time_label = dt.strftime("%H:%M")  # mostra ora esatta
        elif diff < 3600:
            time_label = f"tra {int(diff/60)} min ({dt.strftime('%H:%M')})"
        else:
            time_label = dt.strftime("%H:%M")

        # La label è il testo originale troncato
        label = text[:80] if len(text) <= 80 else text[:77] + "..."

        # Salva il task — il comando da eseguire è il testo originale
        # ma senza l'indicazione temporale (la rimuoviamo)
        import re as _re2
        cmd_text = _re2.sub(
            r'alle\s+ore\s+\d{1,2}(:\d{2})?|'
            r'ore\s+\d{1,2}(:\d{2})?|'
            r'(alle|at)\s+\d{1,2}(:\d{2})?|'
            r'(tra|in)\s+\d+\s+(minut\w+|or[ae]|hour\w+|minute\w*)|'
            r'domani\s+(alle\s+\d{1,2}(:\d{2})?|mattina|sera)|'
            r'tomorrow\s+(at\s+\d{1,2}(:\d{2})?|morning|evening)',
            "", text, flags=_re2.IGNORECASE
        ).strip()

        self._task_scheduler.add_task(
            execute_at = execute_at,
            label      = label,
            command    = cmd_text or text,
            chat_id    = chat_id,
        )

        # Conferma all'utente
        from translations import get_lang
        lang = get_lang()
        if lang == "en":
            confirm = (f"⏰ <b>Scheduled!</b>\n"
                       f"{label}\n"
                       f"🕐 Will execute at <b>{time_label}</b>\n\n"
                       f"Use /task to see all scheduled tasks.")
        else:
            confirm = (f"⏰ <b>Schedulato!</b>\n"
                       f"{label}\n"
                       f"🕐 Eseguirò alle <b>{time_label}</b>\n\n"
                       f"Usa /task per vedere i task in coda.")
        await self._send(chat_id, confirm)
        return True

    async def _typing(self, chat_id):
        try:
            await self._api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        except Exception:
            pass

    async def _ai_reply(self, chat_id, user_msg):
        # ── Intercetta automazioni con regex flessibile ─────────────────
        msg_low = user_msg.lower().strip()

        def _is_create(t):
            return bool(re.match(r"^(crea|nuova|aggiungi|create|fai)\s+automazion[ei]", t, re.IGNORECASE))
        def _is_modify(t):
            return bool(re.match(r"^(modifica|cambia|aggiorna|edit)\s+automazion[ei]", t, re.IGNORECASE))
        def _is_delete(t):
            return bool(re.match(r"^(elimina|cancella|rimuovi|delete|remove)\s+automazion[ei]", t, re.IGNORECASE))
        def _is_toggle(t):
            return bool(re.match(r"^(attiva|disattiva|abilita|disabilita)\s+automazion[ei]", t, re.IGNORECASE))

        cache = (self.state_cache_cb() if self.state_cache_cb else {}) if self.automations_mgr else {}

        # ── CREA ─────────────────────────────────────────────────────────
        if self.automations_mgr and _is_create(msg_low):
            await self._typing(chat_id)
            descr = re.sub(r"^(crea|nuova|aggiungi|create|fai)\s+automazion[ei]\s*[:—\-]?\s*",
                           "", user_msg, flags=re.IGNORECASE).strip()
            if not descr:
                await self._send(chat_id,
                    "Dimmi cosa deve fare l\'automazione. Esempio:\n"
                    "<i>crea automazione che spegne le luci alle 23:00</i>")
                return
            await self._send(chat_id, "⚙️ <b>Genero e installo l\'automazione…</b>")
            result = await self.automations_mgr.create_automation(descr, cache)
            await self._send(chat_id, result)
            return

        # ── MODIFICA ─────────────────────────────────────────────────────
        if self.automations_mgr and _is_modify(msg_low):
            await self._typing(chat_id)
            body = re.sub(r"^(modifica|cambia|aggiorna|edit)\s+automazion[ei]\s*",
                          "", user_msg, flags=re.IGNORECASE).strip()
            sep = re.search(r"\s[—\-–]\s", body)
            if not sep:
                await self._send(chat_id,
                    "Usa il formato:\n"
                    "<code>modifica automazione [nome] — [cosa cambiare]</code>\n\n"
                    "Esempio:\n"
                    "<i>modifica automazione luci sera — aggiungi condizione: solo se Rosa è a casa</i>")
                return
            await self._send(chat_id, "✏️ <b>Modifico l\'automazione…</b>")
            result = await self.automations_mgr.modify_automation(
                body[:sep.start()].strip(), body[sep.end():].strip(), cache)
            await self._send(chat_id, result)
            return

        # ── ELIMINA ──────────────────────────────────────────────────────
        if self.automations_mgr and _is_delete(msg_low):
            await self._typing(chat_id)
            body = re.sub(r"^(elimina|cancella|rimuovi|delete|remove)\s+automazion[ei]\s*",
                          "", user_msg, flags=re.IGNORECASE).strip()
            if not body:
                await self._send(chat_id, "Dimmi il nome dell\'automazione da eliminare.")
                return
            result = await self.automations_mgr.delete_automation(body, cache)
            await self._send(chat_id, result)
            return

        # ── ATTIVA / DISATTIVA ────────────────────────────────────────────
        if self.automations_mgr and _is_toggle(msg_low):
            await self._typing(chat_id)
            force = "on" if re.match(r"^(attiva|abilita)", msg_low) else "off"
            body  = re.sub(r"^(attiva|disattiva|abilita|disabilita)\s+automazion[ei]\s*",
                           "", user_msg, flags=re.IGNORECASE).strip()
            result = await self.automations_mgr.toggle_automation(body, cache, force=force)
            await self._send(chat_id, result)
            return

        # "quanta energia ieri/oggi/settimana" → HistoryClient
        if self.history_client and any(
            k in msg_low for k in ("energia ieri", "produzione ieri", "kwh ieri",
                                   "consumo ieri", "energia settimana", "energia mese",
                                   "quanta energia", "quanto ho prodotto")
        ):
            await self._typing(chat_id)
            period = "ieri" if "ieri" in msg_low else ("settimana" if "settimana" in msg_low else ("mese" if "mese" in msg_low else "oggi"))
            result = await self.history_client.energy_summary(period)
            await self._send(chat_id, result)
            return

        # ── POSIZIONE ORA — risposta istantanea senza history ───────────────────────
        _now_kw = (
            "dove si trova ora", "dove è ora", "dove sei ora", "posizione attuale",
            "dov è ora", "dove so trova", "dove si trova adesso", "dove è adesso",
            "where is now", "current location", "dove si trova rosa ora",
            "dove si trova agostino ora"
        )
        if any(k in msg_low for k in _now_kw):
            await self._typing(chat_id)
            try:
                import json as _json, aiohttp as _aiohttp
                from agent.location_tracker import _get_tracker_eid, _reverse_geocode
                # Determina persona
                _pname = "agostino"
                if self.state_cache_cb:
                    for _eid in self.state_cache_cb():
                        if _eid.startswith("person."):
                            _n = _eid.split(".")[1].lower()
                            if _n in msg_low:
                                _pname = _n
                                break
                _tracker = _get_tracker_eid(_pname)
                if not _tracker:
                    await self._send(chat_id, f"⚠️ Nessun tracker configurato per {_pname.capitalize()}")
                else:
                    # Legge stato attuale — nessun history, risposta immediata
                    _st = await self._rest_client.get_state(_tracker)
                    _attrs = _st.get("attributes", {}) if _st else {}
                    _lat = _attrs.get("latitude")
                    _lon = _attrs.get("longitude")
                    _updated = (_st or {}).get("last_updated", "")[:16].replace("T", " ")
                    if _lat and _lon:
                        async with _aiohttp.ClientSession() as _sess:
                            _addr = await _reverse_geocode(float(_lat), float(_lon), _sess)
                        _bat = _attrs.get("battery_level", "")
                        _bat_str = f" 🔋{_bat}%" if _bat else ""
                        _msg = (f"📍 <b>{_pname.capitalize()} ora</b>\n\n"
                                f"📌 {_addr}\n"
                                f"🕐 Aggiornato: {_updated}{_bat_str}")
                    else:
                        _zone = (_st or {}).get("state", "sconosciuta")
                        _msg = f"📍 <b>{_pname.capitalize()}</b> — zona: {_zone} (no GPS)"
                    await self._send(chat_id, _msg)
            except Exception as _e:
                logger.warning("location now error: %s", _e)
                await self._send(chat_id, f"⚠️ Errore: {_e}")
            return

        # ── LOCATION TRACKER — soste GPS reali ──────────────────────────────────────
        _loc_kw = (
            "dove ha sostato", "dove è stato", "dove è stata", "dove si è fermato",
            "dove si è fermata", "soste di", "soste agostino", "soste rosa",
            "percorso di", "dove ha passato", "spostamenti di", "dove era",
            "where was", "stops of", "dove ha girato", "stosta", "sosta di",
            "posizioni di", "traccia di", "dov era",
            "spostamenti rosa", "spostamenti agostino", "spostamenti mario",
            "spostamenti lucia", "spostamenti",
            "dove rosa", "dove agostino", "dove mario", "dove lucia"
        )
        if any(k in msg_low for k in _loc_kw):
            await self._typing(chat_id)
            try:
                # Determina persona citata nel messaggio
                _pname = "agostino"
                if self.state_cache_cb:
                    for _eid in self.state_cache_cb():
                        if _eid.startswith("person."):
                            _n = _eid.split(".")[1].lower()
                            if _n in msg_low:
                                _pname = _n
                                break
                # Parsing ore personalizzate: "ultime 5h", "ultime 10 ore", "5h", "3 ore" ecc
                import re as _re
                _hours_match = _re.search(r"(\d+)\s*(?:h\b|ore?\b|hour)", msg_low)
                if _hours_match:
                    _hours = max(1, min(int(_hours_match.group(1)), 168))  # 1h min, 7gg max
                elif any(k in msg_low for k in ["settimana","week","7 giorni"]):
                    _hours = 168
                elif any(k in msg_low for k in ["ieri","yesterday"]):
                    _hours = 48
                else:
                    _hours = 24
                _min_stop = 10
                _stops = await get_person_stops(
                    self._rest_client,
                    _pname, hours=_hours, min_stop_min=_min_stop
                )
                await self._send(chat_id, format_stops_message(
                    _stops, _pname.capitalize(), _hours, _min_stop
                ))
            except Exception as _e:
                logger.warning("location_tracker error: %s", _e)
                await self._send(chat_id, f"⚠️ Errore: {_e}")
            return

        # ── FALLBACK AI — linguaggio naturale con formato [CALL_SERVICE:] collaudato ──
        if self.ai_cb and self.context_cb:
            await self._typing(chat_id)
            try:
                ctx = self.context_cb()
                _lang = get_lang()
                _lang_instruction = (
                    "Rispondi SEMPRE in italiano, in modo conciso e visivamente ricco."
                    if _lang == "it" else
                    "Always respond in English, concisely and with rich formatting."
                )
                # ── Costruisci memoria PRIMA di usarla nel prompt ─────────
                import time as _time
                _now = _time.time()
                _MAX_TURNS = 8
                _MAX_AGE   = 1800
                mem = self._conv_memory.get(chat_id, [])
                mem = [(r, t, ts) for r, t, ts in mem if _now - ts < _MAX_AGE]
                ai_history = [{"role": r, "content": t} for r, t, _ in mem]
                # ────────────────────────────────────────────────────────
                # ── Check contestuale energia: "e ieri?" dopo domanda energia
                _last_user = next((t for r, t, _ in reversed(mem) if r == "user"), "")
                _last_bot  = next((t for r, t, _ in reversed(mem) if r == "assistant"), "")
                _energy_ctx = any(k in _last_bot for k in ["Produzione FV", "Consumo casa", "⚡", "kWh", "Autosufficienza"])
                _asking_yesterday = any(k in user_msg.lower() for k in ["ieri", "yesterday", "e ieri", "giorno prima"])
                if _energy_ctx and _asking_yesterday:
                    await self._typing(chat_id)
                    try:
                        _period_ieri = t("energy_period_yesterday")
                        report = await self.history_client.energy_summary(_period_ieri)
                    except Exception as _e:
                        report = f"⚠️ Errore recupero energia ieri: {_e}"
                    await self._send(chat_id, report)
                    mem.append(("user",      user_msg, _now))
                    mem.append(("assistant", report,   _now))
                    mem = mem[-(_MAX_TURNS * 2):]
                    self._conv_memory[chat_id] = mem
                    return
                # ────────────────────────────────────────────────────────
                _mem_note = (
                    f"Hai memoria degli ultimi {len(ai_history)//2} scambi. "
                    "Usala per riferimenti tipo 'quella luce', 'e ieri?', 'spegnila'.\n"
                ) if ai_history else ""

                _memory_block = self._memory.get_memory_prompt()
                sys_prompt = (
                    "Sei HomeMind, assistente AI per la domotica.\n"
                    + _lang_instruction + "\n"
                    + _mem_note
                    + (_memory_block + "\n" if _memory_block else "")
                    + "\n=== STILE RISPOSTE ===\n"
                    "Usa sempre emoji appropriate:\n"
                    "  💡 luci  🌡️ temperatura  🔒 sicurezza/allarme  🏠 casa\n"
                    "  🌤️ meteo  ⚡ energia  🔌 prese/switch  🌬️ clima/AC\n"
                    "  ✅ azione eseguita  ⚠️ attenzione  ℹ️ informazione\n"
                    "  👤 persona  📍 posizione  🔓 aperto  🔐 chiuso\n"
                    "Usa <b>grassetto</b> per valori importanti (temperature, stati, nomi).\n"
                    "Usa elenchi puntati per più elementi.\n\n"
                    "=== CONTROLLARE DISPOSITIVI ===\n"
                    "Usa tag [CALL_SERVICE:] — vengono eseguiti automaticamente:\n"
                    "  [CALL_SERVICE:light.turn_on:light.mario]\n"
                    "  [CALL_SERVICE:light.turn_off:light.bagno]\n"
                    "  [CALL_SERVICE:light.turn_on:all]\n"
                    "  [CALL_SERVICE:switch.turn_on:switch.presa_1]\n"
                    "  [CALL_SERVICE:climate.set_temperature:climate.termostato:{\"temperature\":21}]\n"
                    "  REGOLE CLIMA — segui RIGOROSAMENTE in base al tipo:\n"
                    "  A) Se nel contesto CLIMA vedi tipo=SmartIR:\n"
                    "     Accendi: [CALL_SERVICE:climate.turn_on:climate.xxx]\n"
                    "     Spegni:  [CALL_SERVICE:climate.turn_off:climate.xxx]\n"
                    "     Temperatura: [CALL_SERVICE:climate.set_temperature:climate.xxx:{\"temperature\":22}]\n"
                    "     MAI usare set_hvac_mode con SmartIR — dà errore 400!\n"
                    "  B) Se il contesto CLIMA mostra hvac_modes=[heat,cool,...] (senza tipo=SmartIR):\n"
                    "     Accendi: [CALL_SERVICE:climate.set_hvac_mode:climate.xxx:{\"hvac_mode\":\"heat\"}]\n"
                    "     Spegni:  [CALL_SERVICE:climate.set_hvac_mode:climate.xxx:{\"hvac_mode\":\"off\"}]\n"
                    "     Poi temperatura: [CALL_SERVICE:climate.set_temperature:climate.xxx:{\"temperature\":22}]\n"
                    "  C) Se vedi switch caldaia nel contesto SWITCH/PRESE:\n"
                    "     Accendi: switch.turn_on sullo switch fisico\n"
                    "     Spegni:  switch.turn_off sullo switch fisico\n"
                    "     Temperatura: set_temperature sul termostato\n"
                    "  D) Regola temperatura: set_temperature SEMPRE con {\"temperature\":N}\n"
                    "     MAI chiamare set_hvac_mode senza il campo hvac_mode nel payload\n"
                    "  [CALL_SERVICE:media_player.turn_on:media_player.tv]\n"
                    "  Per BIANCO usa color_temp_kelvin: [CALL_SERVICE:light.turn_on:light.faretti:{\"color_temp_kelvin\":4000}]\n"
                    "  Per COLORI RGB: [CALL_SERVICE:light.turn_on:light.faretti:{\"rgb_color\":[255,0,0]}]\n"
                    "  BIANCO CALDO=2700K NEUTRO=4000K FREDDO=6500K — usa SEMPRE color_temp_kelvin per il bianco\n"
                    "REGOLA: terzo campo = entity_id esatto dal contesto, MAI 'entity_id=xxx'\n"
                    "Per più dispositivi: un [CALL_SERVICE] per ognuno.\n\n"
                    "=== CONTESTO CONVERSAZIONE ===\n"
                    "Se la risposta precedente conteneva dati energetici (kWh, Produzione FV, Consumo)\n"
                    "e l'utente dice 'e ieri?' / 'ieri?' / 'e ieri come' → rispondi con i dati energia di ieri,\n"
                    "NON con storico generico di presenza o movimento.\n\n"
                    "=== STORICO ENTITÀ ===\n"
                    "⚠️ REGOLA FONDAMENTALE: se l'utente chiede cosa è successo in passato,\n"
                    "quante volte qualcosa ha scattato, quando è cambiato uno stato, ecc.,\n"
                    "NON rispondere 'non ho accesso ai dati storici'.\n"
                    "USA SEMPRE il tag [GET_HISTORY:entity_id:ore] con l'entity_id esatto dal contesto.\n"
                    "  [GET_HISTORY:binary_sensor.0x00158d000224fb57_occupancy:24]  ← movimento cucina oggi\n"
                    "  [GET_HISTORY:alarm_control_panel.home_alarm:48]              ← allarme 2 giorni\n"
                    "  [GET_HISTORY:person.mario:12]                               ← presenza oggi\n"
                    "Gli entity_id disponibili sono nella sezione 'ENTITY_ID PER GET_HISTORY' del contesto.\n\n"
                    "=== CREARE AUTOMAZIONI ===\n"
                    "Usa [CREATE_AUTOMATION:yaml_content] per creare automazioni HA.\n"
                    "Prima mostra il YAML all'utente e spiega cosa fa.\n\n"
                    "=== REGOLE UNIVERSALI (per qualsiasi AI provider) ===\n"
                    "\n"
                    "⛔ NON usare [CALL_SERVICE] quando:\n"
                    "- L'utente fa una DOMANDA (chi/cosa/quanto/dove/quando)\n"
                    "- L'utente chiede lo STATO di qualcosa\n"
                    "- L'utente chiede ANALISI, STORICO o SUGGERIMENTI\n"
                    "- Stai mostrando un ESEMPIO — mai eseguire azioni negli esempi\n"
                    "- Non hai la certezza di quale entità controllare\n"
                    "\n"
                    "✅ USA [CALL_SERVICE] SOLO quando:\n"
                    "- Comando esplicito: accendi/spegni/imposta/arma/disarma\n"
                    "- L'utente ha confermato un'azione (sì/ok/vai/fallo)\n"
                    "\n"
                    "📋 ALTRE REGOLE FONDAMENTALI:\n"
                    "- NON inventare entity_id — usa SOLO quelli nel contesto\n"
                    "- Se hai dubbi se eseguire o meno — NON eseguire, chiedi prima\n"
                    "- NON aggiungere azioni 'utili' non richieste dall'utente\n"
                    "- Rispondi nella lingua dell'utente (italiano se scrive in italiano)\n"
                    + ctx
                )

                reply = await self.ai_cb(sys_prompt, user_msg, ai_history)

                # Salva questo scambio in memoria
                mem.append(("user",      user_msg, _now))
                mem.append(("assistant", reply,    _now))
                mem = mem[-(_MAX_TURNS * 2):]  # tieni solo gli ultimi N scambi
                self._conv_memory[chat_id] = mem

                # ── Estrai fatti utili in background ────────────────
                if len(mem) >= 4:
                    import asyncio as _asyncio
                    _ai_hist = [{"role": r, "content": t} for r, t, _ in mem]
                    _asyncio.create_task(
                        self._memory.extract_from_conversation(_ai_hist),
                        name="memory_extract"
                    )

                # Converti markdown → HTML (l'AI tende a usare **bold** ma Telegram vuole <b>)
                import re as _re
                reply_html = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', reply)
                reply_html = _re.sub(r'\*(.+?)\*',   r'<i>\1</i>', reply_html)

                # Usa lo stesso parser [CALL_SERVICE:] del main loop — già collaudato
                # Validazione uguale per tutti i provider AI
                _QUERY_KW = ("quali luci", "che luci", "luci accese", "dimmi lo stato",
                             "stato completo", "tutte le temperature", "elenca", "mostrami",
                             "quali sensori", "stato antifurto", "analizza energia",
                             "which lights", "lights on", "tell me", "show me", "list all")
                _ACTION_KW = ("accendi", "spegni", "imposta", "arma", "disarma",
                              "turn on", "turn off", "set", "arm", "open", "close")
                _msg_low = user_msg.lower()
                _is_query = (any(q in _msg_low for q in _QUERY_KW)
                             and not any(a in _msg_low for a in _ACTION_KW))
                if self.ai_action_cb:
                    if _is_query:
                        results = []  # blocca azioni per domande informative
                    else:
                        results = await self.ai_action_cb(reply)
                    # Testo pulito (senza tag azione)
                    clean = _remove_action_tags(reply_html)

                    ok       = [r for r in results if r.startswith("✅")]
                    fails    = [r for r in results if "FAIL" in r]
                    history  = [r for r in results if r.startswith("📊")]
                    info     = [r for r in results if not r.startswith(("✅","📊")) and "FAIL" not in r]

                    # Mostra grafici/storici direttamente senza riscriverli
                    # Il secondo giro AI è già fatto in main.py — qui mostriamo il risultato
                    # I 📊 ora contengono grafico ASCII + stats già formattati

                    if ok or fails or history or info:
                        clean_no_ok = _re.sub(r'✅[^\n]*\n?', '', clean).strip()
                        # Manda i grafici storici come messaggi separati
                        # (contengono <pre> che Telegram gestisce meglio da soli)
                        for hist_msg in history:
                            await self._send(chat_id, hist_msg)
                        # Manda il resto
                        parts = []
                        if clean_no_ok and not history:
                            parts.append(clean_no_ok)
                        parts.extend(info)
                        parts.extend(ok)
                        if fails:
                            parts.append("⚠️ " + " | ".join(fails))
                        if parts:
                            await self._send(chat_id, "\n\n".join(parts) + self._ai_footer())
                        elif history:
                            # Solo storico — manda footer separato
                            await self._send(chat_id, self._ai_footer().strip() or "")
                    else:
                        # Nessuna azione: risposta testuale pura
                        await self._send(chat_id, (clean or reply_html[:3000]) + self._ai_footer())
                else:
                    await self._send(chat_id, reply_html[:3000] + self._ai_footer())

            except Exception as e:
                import traceback
                logger.error("TG AI fallback error: %s\n%s", e, traceback.format_exc())
                await self._send(chat_id, t("ai_error", msg=str(e)[:200]))


    def _ai_footer(self) -> str:
        """Footer con il provider che ha risposto."""
        if self._ai_provider_ref:
            try:
                p = getattr(self._ai_provider_ref, "_last_used", None)
                if p:
                    # Se sta usando un fallback (non il primo) evidenzialo
                    providers = self._ai_provider_ref._providers
                    if providers and p.name != providers[0].name:
                        return f'\n<i>🔀 via {p.display} (fallback)</i>'
                    return f'\n<i>🤖 via {p.display}</i>'
            except Exception:
                pass
        return ""

    async def _transcribe_voice(self, chat_id: str, voice: dict) -> str | None:
        """Scarica il vocale da Telegram e lo trascrive con Whisper (OpenAI)."""
        try:
            # Recupera la API key OpenAI dal provider AI
            openai_key = None
            # Cerca la key OpenAI in ordine di priorità:
            # 1. Dai provider AI già caricati in memoria
            if self._ai_provider_ref:
                for p in getattr(self._ai_provider_ref, "_providers", []):
                    if getattr(p, "name", "") == "openai" and getattr(p, "api_key", ""):
                        openai_key = p.api_key
                        break

            # 2. Fallback: leggi direttamente dalla variabile d'ambiente
            if not openai_key:
                import os as _os, json as _json
                # Prima prova HM_AI_PROVIDERS (lista JSON dei provider)
                raw = _os.getenv("HM_AI_PROVIDERS", "")
                if raw:
                    try:
                        for p in _json.loads(raw):
                            if p.get("name") == "openai" and p.get("api_key"):
                                openai_key = p["api_key"]
                                break
                    except Exception:
                        pass
                # Poi prova HM_AI_API_KEY se il provider attivo è openai
                if not openai_key:
                    if _os.getenv("HM_AI_PROVIDER", "") == "openai":
                        openai_key = _os.getenv("HM_AI_API_KEY", "")
                # Infine prova direttamente la variabile OpenAI standard
                if not openai_key:
                    openai_key = _os.getenv("OPENAI_API_KEY", "")

            if not openai_key:
                logger.warning("Voce: nessuna API key OpenAI trovata — verifica che openai_api_key sia impostato nelle Opzioni addon")
                return None

            logger.info("Voce: API key OpenAI trovata — avvio trascrizione")
            file_id = voice.get("file_id", "")
            if not file_id:
                return None

            # 1. Ottieni il path del file da Telegram
            file_info = await self._api("getFile", {"file_id": file_id})
            file_path = file_info["result"]["file_path"]
            file_url  = f"https://api.telegram.org/file/bot{self.token}/{file_path}"

            # 2. Scarica il file audio
            async with self._session.get(file_url) as resp:
                if resp.status != 200:
                    logger.warning("Voce: download fallito HTTP %s", resp.status)
                    return None
                audio_bytes = await resp.read()

            logger.info("Voce: scaricati %d bytes — invio a Whisper...", len(audio_bytes))

            # 3. Invia a Whisper API
            import aiohttp as _ah
            data = _ah.FormData()
            data.add_field("model", "whisper-1")
            data.add_field("language", "it")
            data.add_field(
                "file",
                audio_bytes,
                filename="voice.ogg",
                content_type="audio/ogg"
            )
            headers = {"Authorization": f"Bearer {openai_key}"}
            async with self._session.post(
                "https://api.openai.com/v1/audio/transcriptions",
                data=data,
                headers=headers,
                timeout=_ah.ClientTimeout(total=30)
            ) as resp:
                result = await resp.json()
                transcript = result.get("text", "").strip()
                if transcript:
                    logger.info("Voce: trascritto [%d chars]", len(transcript))
                    return transcript
                logger.warning("Voce: Whisper risposta vuota: %s", result)
                return None

        except Exception as e:
            logger.error("Voce: errore trascrizione: %s", e, exc_info=True)
            return None

    async def _send(self, chat_id, text):
        if not text.strip():
            return
        # Telegram max 4096 caratteri per messaggio — spezza se necessario
        MAX = 4000  # un po' meno del limite per margine sicurezza
        chunks = []
        if len(text) <= MAX:
            chunks = [text]
        else:
            # Se c'è un blocco <pre>, mandalo separato per non troncare il codice
            import re as _re
            pre_match = _re.search(r'(<pre>.*?</pre>)', text, _re.DOTALL)
            if pre_match:
                before = text[:pre_match.start()].strip()
                pre_block = pre_match.group(1)
                after = text[pre_match.end():].strip()
                if before:
                    chunks.append(before)
                # spezza il pre in blocchi da MAX
                inner = pre_match.group(1)[5:-6]  # togli <pre> e </pre>
                while inner:
                    part = inner[:MAX-13]
                    inner = inner[MAX-13:]
                    chunks.append("<pre>" + part + "</pre>")
                if after:
                    chunks.append(after)
            else:
                # Spezza per righe senza tagliare a metà
                current = ""
                for line in text.split("\n"):
                    if len(current) + len(line) + 1 > MAX:
                        chunks.append(current)
                        current = line
                    else:
                        current = current + "\n" + line if current else line
                if current:
                    chunks.append(current)

        for chunk in chunks:
            if not chunk.strip():
                continue
            try:
                await self._api("sendMessage", {
                    "chat_id":    chat_id,
                    "text":       chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                })
            except Exception as e:
                # Fallback plain text
                try:
                    plain = re.sub(r"<[^>]+>", "", chunk)
                    await self._api("sendMessage", {
                        "chat_id": chat_id, "text": plain[:4000],
                        "disable_web_page_preview": True,
                    })
                except Exception as e2:
                    logger.warning("TG send fail: %s / %s", e, e2)

    async def _typing(self, chat_id):
        try:
            await self._api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        except Exception:
            pass

    async def _api(self, method, params=None):
        url     = f"{TG_API}/bot{self.token}/{method}"
        timeout = aiohttp.ClientTimeout(total=POLL_TIMEOUT + 5)
        async with self._session.post(url, json=params or {}, timeout=timeout) as r:
            data = await r.json()
            if not data.get("ok"):
                raise Exception(f"TG API error: {data}")
            return data

    async def send_photo(self, chat_id: str, photo_bytes: bytes, caption: str = "") -> bool:
        """Manda una foto JPEG su Telegram tramite multipart/form-data."""
        try:
            url = f"{TG_API}/bot{self.token}/sendPhoto"
            data = aiohttp.FormData()
            data.add_field("chat_id", str(chat_id))
            data.add_field("photo", photo_bytes, filename="snapshot.jpg", content_type="image/jpeg")
            if caption:
                data.add_field("caption", caption)
            timeout = aiohttp.ClientTimeout(total=30)
            async with self._session.post(url, data=data, timeout=timeout) as r:
                result = await r.json()
                if result.get("ok"):
                    logger.info("Foto inviata su Telegram chat %s", chat_id)
                    return True
                else:
                    logger.error("Errore invio foto Telegram: %s", result)
                    return False
        except Exception as e:
            logger.error("send_photo errore: %s", e)
            return False

    async def send_frigate_snapshot(self, chat_id: str, camera_name: str, caption: str = "") -> bool:
        """Recupera snapshot da Frigate e lo manda su Telegram."""
        if not self._frigate_client or not self._frigate_client.is_ready():
            return False
        photo_bytes = await self._frigate_client.get_snapshot(camera_name)
        if not photo_bytes:
            logger.warning("Frigate: snapshot '%s' non disponibile", camera_name)
            return False
        cap = caption or f"📷 Camera: {camera_name}"
        return await self.send_photo(chat_id, photo_bytes, cap)
