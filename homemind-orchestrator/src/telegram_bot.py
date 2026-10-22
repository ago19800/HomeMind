"""
telegram_bot.py — Bot Telegram bidirezionale per HomeMind.
Risposte formattate con emoji e HTML Telegram.
"""
import asyncio, logging, json, re, os
import aiohttp
from pathlib import Path
_ROUTINES_DIR = Path("/config/homemind_patches/routines")
from datetime import datetime
from translations import t, set_lang, get_lang, alarm_state_label, load_lang_from_config
from config_file_manager import ConfigFileManager
from github_installer import GitHubInstaller, parse_github_url
import tools_system as _tools
import json
import agentic_executor as _agent
from ha_terminal import HATerminal


def _html_escape(s: str) -> str:
    """Escape HTML per Telegram."""
    import html as _h
    return _h.escape(s or "")


def _get_default_path_from_rules() -> str:
    """Cerca /config/... in righe di regole.md che contengono parole chiave
    di percorso. Strategia semplice e robusta senza regex complessi."""
    try:
        from pathlib import Path as _Path
        import re as _re_p
        rp = _Path("/config/homemind_patches/regole.md")
        if not rp.exists():
            return "/config"
        lines = rp.read_text(encoding="utf-8").splitlines()
        _KEYWORDS = ("percorso", "default", "salvare", "salva", "sempre in",
                     "usa sempre", "directory", "cartella", "folder")
        for line in lines:
            ls = line.strip()
            if not ls or ls.startswith("#"):
                continue
            if not any(k in ls.lower() for k in _KEYWORDS):
                continue
            # Cerca SOLO path assoluti /config/... nella riga
            m = _re_p.search(r"/config/[\w/.\-]+", ls)
            if m:
                return m.group(0).rstrip("/")
    except Exception:
        pass
    return "/config"


def _normalize_user_path(path: str) -> str:
    """Pulisce path inserito dall'utente e normalizza sempre verso /config/...

    Gestisce:
    - Markdown link Telegram: [classifica.md](http://classifica.md) → classifica.md
    - Embedded markdown: /ago/[file.md](http://file.md) → /ago/file.md
    - Quote: "path" o 'path' → path
    - Prefix "config/..." → "/config/..." (senza doppio /config/)
    - "/config/ago/..." rimane invariato
    - "ago/..." → "/config/ago/..."  (relativo → assoluto dentro /config)
    - Solo nome file (es. "ago.txt") → usa percorso default da regole.md
    """
    import re
    if not path:
        return path
    p = path.strip().strip('"').strip("'")
    # Decodifica TUTTI i markdown link [text](url) → text
    p = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", p)
    p = p.strip()
    # Normalizza separatori Windows
    p = p.replace("\\", "/")
    # Canonicalizza prefissi: già assoluto con /config
    if p.startswith("/config/") or p == "/config":
        return p
    # Prefisso "config/" senza slash → aggiungi
    if p.startswith("config/"):
        return "/" + p
    # Path assoluto: lascia invariato (/, /etc, /var, ecc.)
    if p.startswith("/"):
        return p
    # Path relativo con cartella (es. "ago/file.txt") → /config/ago/file.txt
    if "/" in p:
        return "/config/" + p
    # Solo nome file senza cartella (es. "ago.txt") → usa default da regole
    default_dir = _get_default_path_from_rules()
    return default_dir.rstrip("/") + "/" + p


def _validate_entities_in_yaml(yaml_text: str, state_cache: dict) -> list:
    """Trova entity_id menzionate nel YAML che NON esistono nella state_cache.

    Returns: lista di entity_id inventate (vuota se tutte ok)
    """
    import re
    if not state_cache:
        return []
    # Pattern entity_id Home Assistant: dominio.nome_snake_case
    # Dominî validi più comuni
    domains = (r"sensor|binary_sensor|switch|light|input_boolean|input_number|input_text|"
               r"input_select|input_datetime|automation|script|scene|climate|cover|fan|"
               r"media_player|alarm_control_panel|person|zone|sun|weather|number|select|"
               r"button|device_tracker|camera|notify|group|counter|timer|template|"
               r"calendar|todo|date|time")
    pattern = re.compile(rf"\b({domains})\.([a-z0-9_]+)\b", re.IGNORECASE)

    found = set()
    for m in pattern.finditer(yaml_text):
        eid = f"{m.group(1).lower()}.{m.group(2).lower()}"
        found.add(eid)

    invented = [eid for eid in found if eid not in state_cache]
    return sorted(invented)


def _smart_entity_match(state_cache: dict, description: str, max_results: int = 50) -> list:
    """Trova entità HA pertinenti a una descrizione utente.

    Strategia multi-livello:
    1. Estrai keyword significative (>= 3 char, niente stop-words)
    2. Match diretto: keyword in entity_id o friendly_name
    3. Match substring partial (es. "scaldabagno" → "energiascaldabagno")
    4. Match su parti del entity_id senza prefisso dominio
    5. Se servono sensori/consumi/energia → includi anche dominio sensor.*
    """
    if not state_cache:
        return []

    # Stop-words italiane comuni che non aiutano nel matching
    STOP_WORDS = {
        "il", "lo", "la", "le", "gli", "i", "un", "una", "uno",
        "del", "della", "dei", "delle", "degli", "al", "alla", "ai", "alle",
        "in", "su", "per", "con", "tra", "fra", "da", "di", "a",
        "e", "o", "ma", "se", "che", "chi", "cui",
        "mi", "ti", "ci", "vi", "lo", "la", "li",
        "sono", "sei", "è", "siamo", "siete",
        "ho", "hai", "ha", "abbiamo", "avete", "hanno",
        "questo", "quello", "questi", "quelli",
        "creami", "fammi", "dammi", "mostrami", "leggi",
        "sensore", "sensori", "automazione", "automazioni", "template", "scena", "scene",
        "valore", "stato", "attuale", "ora",
        "the", "and", "for", "with",
    }

    # Pulisci la descrizione
    import re
    text = description.lower()
    # Rimuovi punteggiatura
    text = re.sub(r'[^\w\sàèéìòù]', ' ', text)
    words = text.split()
    keywords = [w for w in words if len(w) >= 3 and w not in STOP_WORDS]

    if not keywords:
        # Fallback: usa parole con lunghezza >= 4
        keywords = [w for w in words if len(w) >= 4]

    matched = []
    matched_ids = set()

    # PASSO 1: match esatto su parola intera (priorità alta)
    for eid, s in state_cache.items():
        if eid in matched_ids:
            continue
        attrs = s.get("attributes") or {}
        fname = (attrs.get("friendly_name") or "").lower()
        # Estrai parte dopo il dominio: sensor.foo_bar → foo_bar
        eid_clean = eid.split(".", 1)[1].lower() if "." in eid else eid.lower()
        # Spezza l'entity_id in tokens (foo_bar → ['foo', 'bar'])
        eid_tokens = re.findall(r'[a-z]+', eid_clean)
        fname_tokens = re.findall(r'[a-z]+', fname)
        all_tokens = set(eid_tokens) | set(fname_tokens)

        for kw in keywords:
            # Match esatto come token
            if kw in all_tokens:
                matched.append((eid, s, "exact_token"))
                matched_ids.add(eid)
                break

    # PASSO 2: match substring (es. "scaldabagno" in "energiascaldabagno")
    for eid, s in state_cache.items():
        if eid in matched_ids:
            continue
        attrs = s.get("attributes") or {}
        fname = (attrs.get("friendly_name") or "").lower()
        eid_clean = eid.split(".", 1)[1].lower() if "." in eid else eid.lower()
        haystack = f"{eid_clean} {fname}"

        for kw in keywords:
            if len(kw) >= 5 and kw in haystack:  # substring solo per keyword lunghe
                matched.append((eid, s, "substring"))
                matched_ids.add(eid)
                break

    # PASSO 3: se richiesta riguarda energia/consumi e ho poche entità → aggiungi domain sensor
    energy_terms = {"energia", "consumo", "consumi", "watt", "kwh", "kw", "potenza", "corrente"}
    if any(t in keywords for t in energy_terms) and len(matched) < 5:
        for eid, s in state_cache.items():
            if eid in matched_ids:
                continue
            if not eid.startswith("sensor."):
                continue
            attrs = s.get("attributes") or {}
            unit = (attrs.get("unit_of_measurement") or "").lower()
            dev_class = (attrs.get("device_class") or "").lower()
            if unit in ("w", "kwh", "wh", "kw") or dev_class in ("energy", "power"):
                matched.append((eid, s, "energy_domain"))
                matched_ids.add(eid)
                if len(matched) >= max_results:
                    break

    return matched[:max_results]


def _format_entities_for_ai(matches: list) -> str:
    """Formatta entità trovate in stringa leggibile per il prompt AI."""
    if not matches:
        return "(nessuna entità pertinente trovata — l\'utente probabilmente vuole un sensore generico)"
    lines = []
    for eid, s, source in matches:
        attrs = s.get("attributes") or {}
        fname = attrs.get("friendly_name", "")
        unit = attrs.get("unit_of_measurement", "")
        dev_class = attrs.get("device_class", "")
        state = s.get("state", "")
        meta = []
        if fname:    meta.append(f'friendly_name="{fname}"')
        if unit:     meta.append(f'unit="{unit}"')
        if dev_class: meta.append(f'device_class="{dev_class}"')
        meta_str = ", ".join(meta) if meta else ""
        lines.append(f"  • {eid} = {state}  [{meta_str}]")
    return "\n".join(lines)


async def _send_long_file(bot, chat_id: str, title: str, content: str,
                           lang_hint: str = "yaml"):
    """Invia file lungo spezzato in più messaggi Telegram.

    Telegram limit: 4096 char per messaggio. Spezziamo per righe.
    """
    import html as _h
    MAX = 3500  # lasciamo margine per tag HTML
    lines = content.split("\n")
    chunks = []
    current = ""
    for line in lines:
        line_out = line + "\n"
        if len(current) + len(line_out) > MAX:
            chunks.append(current)
            current = line_out
        else:
            current += line_out
    if current:
        chunks.append(current)

    total = len(chunks)
    for i, chunk in enumerate(chunks, 1):
        header = f"📄 <b>{title}</b>" if total == 1 else f"📄 <b>{title}</b> <i>({i}/{total})</i>"
        body = f"{header}\n\n<pre>{_h.escape(chunk)}</pre>"
        await bot._send(chat_id, body)


def _extract_yaml(ai_response: str) -> str:
    """Estrae blocco YAML pulito dalla risposta AI.

    Gestisce:
    - ```yaml ... ```
    - ``` ... ```
    - YAML puro senza markdown
    """
    import re
    text = ai_response.strip()
    # Cerca blocco ```yaml ... ```
    m = re.search(r'```(?:yaml|yml)?\s*\n(.*?)```', text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Nessun fence: prendi tutto dalla prima chiave YAML valida
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Riga che sembra una chiave YAML top-level
        if re.match(r'^[a-z_][a-z0-9_]*:', stripped, re.IGNORECASE):
            return "\n".join(lines[i:]).strip()
    return text


from agent.location_tracker import get_person_stops, format_stops_message
from agent.weather_external import detect_city, get_weather_for_city
from agent.memory_manager  import MemoryManager

# ─── Regole comportamentali utente ────────────────────────────────────────────
_RULES_PATH = Path("/config/homemind_patches/regole.md")

def _make_rules_ai_cb(original_ai_cb):
    """Avvolge ai_cb iniettando le regole utente in OGNI system prompt.
    Tutti gli agenti (ssh, natural, agentic, ecc.) ricevono le regole automaticamente.
    """
    async def _wrapped(system_prompt: str, user_prompt: str, history):
        # Inline: non dipende da _load_rules per evitare problemi di ordine definizione
        try:
            _rp = Path("/config/homemind_patches/regole.md")
            if _rp.exists():
                _lines = _rp.read_text(encoding="utf-8").splitlines()
                _rules = [l.strip() for l in _lines if l.strip() and not l.strip().startswith("#")]
                if _rules:
                    rules_block = "=== REGOLE UTENTE — rispettale in ogni azione ===\n" \
                                  + "\n".join(_rules) + "\n=== FINE REGOLE ===\n\n"
                    return await original_ai_cb(rules_block + system_prompt, user_prompt, history)
        except Exception:
            pass
        return await original_ai_cb(system_prompt, user_prompt, history)
    return _wrapped


def _load_rules() -> str:
    """Carica regole.md e restituisce un blocco testo da iniettare nel prompt.
    Ignora righe vuote e righe che iniziano con #."""
    try:
        if not _RULES_PATH.exists():
            return ""
        lines = _RULES_PATH.read_text(encoding="utf-8").splitlines()
        rules = [l.strip() for l in lines
                 if l.strip() and not l.strip().startswith("#")]
        if not rules:
            return ""
        logger.info("regole.md: %d regole attive → %s", len(rules),
                    " | ".join(r[:40] for r in rules))
        return "=== REGOLE UTENTE ===\n" + "\n".join(rules) + "\n"
    except Exception as e:
        logger.warning("regole.md load error: %s", e)
        return ""


def _get_active_rules() -> list:
    """Ritorna lista delle regole attive (non-commento) da regole.md."""
    try:
        if not _RULES_PATH.exists():
            return []
        lines = _RULES_PATH.read_text(encoding="utf-8").splitlines()
        return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
    except Exception:
        return []


def _save_active_rules(rules: list):
    """Riscrive regole.md preservando header/commenti e sostituendo le regole attive."""
    try:
        existing = _RULES_PATH.read_text(encoding="utf-8") if _RULES_PATH.exists() else ""
        marker = "# REGOLE ATTIVE (scrivi qui sotto le tue regole, una per riga)"
        if marker in existing:
            header = existing[:existing.index(marker) + len(marker)]
            new_content = header + "\n\n" + ("\n".join(rules) + "\n" if rules else "")
        else:
            new_content = ("\n".join(rules) + "\n") if rules else ""
        _RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _RULES_PATH.write_text(new_content, encoding="utf-8")
        logger.info("regole.md: salvate %d regole", len(rules))
    except Exception as e:
        logger.warning("regole.md save error: %s", e)
from agent.shortcuts_manager import ShortcutsManager
from agent.local_parser     import LocalParser
from agent.routine_manager  import RoutineManager

# Carica lingua salvata in person_config.json all'avvio
load_lang_from_config()


# ═══════════════════════════════════════════════════════════════
# README COMANDI — aggiornato automaticamente
# ═══════════════════════════════════════════════════════════════
_COMANDI_README = """# 🧠 HomeMind — Tutti i Comandi Telegram

## 🔐 SSH & Terminale
/ssh — Menu SSH con esempi
/ssh &lt;testo&gt; — Esegue su HA via SSH (AI sceglie il canale)
/ssh cmd: &lt;cmd&gt; — SSH diretto senza AI (es. /ssh cmd: df -h)
/ssh mostrami ram e cpu — Info sistema host
/ssh lista addon installati — Addon HA attivi
/ssh riavvia addon &lt;nome&gt; — Riavvia addon
/ssh ping &lt;ip&gt; — Ping
/ssh ls /config — Lista file

## 🔍 Ricerca Web
/cerca &lt;query&gt; — Cerca e mostra risultati con AI
/cerca &lt;query&gt; salva in &lt;path&gt; — Cerca e salva file
/cerca &lt;query&gt; → &lt;path&gt; — Alias con freccia
/cerca &lt;query&gt; sovrascrivi &lt;path&gt; — Sovrascrive file esistente

## 🤖 Agente AI
/fai &lt;obiettivo&gt; — Agente autonomo multi-step
/fai leggi automations.yaml e correggi luci salotto
/fai crea riepilogo sensori energia in note/energia.md

## 📁 File & Config
/scrivi &lt;path&gt; &lt;testo&gt; — Scrive un file
/leggi &lt;path&gt; — Legge un file
/ls [path] — Lista file/cartelle in /config
/mkdir &lt;path&gt; — Crea cartella
/elimina &lt;path&gt; — Elimina file
/scarica &lt;url&gt; &lt;path&gt; — Scarica da URL
/modifica &lt;file&gt; &lt;descr&gt; — Modifica file con AI
/crea_sensore &lt;descr&gt; — Crea sensor in configuration.yaml
/leggi_config — Mostra configuration.yaml
/files_config — Lista file /config

## 🏠 Home Assistant
/stato — Stato casa (luci, persone, sensori)
/ha_sistema — Info sistema HA (versione, uptime, RAM)
/ha_addons — Lista addon
/aggiornamenti — Controlla aggiornamenti
/riparazioni — Problemi HA
/automazioni — Lista automazioni
/allarme — Stato allarme

## ⚡ Energia
/energia — Consumo e produzione oggi
/ieri — Energia di ieri
/solare — Stato fotovoltaico
/elettrodomestici — Elettrodomestici rilevati
/powerguard — Soglia ENEL e protezione consumi

## 📅 Task
/task — Lista task in coda
/task_agent &lt;descr&gt; — Programma task AI
/task_shell &lt;cmd&gt; — Programma task shell
/cancella_task — Cancella tutti i task

## 🤖 AI & Providers
/providers — Provider AI attivi e configurati
/ai_mode — Cambia modalità AI
/ai_domotica — Modalità focalizzata HA
/ai_libera — Chat generica

## 🧠 Memoria
/memoria — Cosa HomeMind sa di te
/memoria reset — Reset memoria
/alias — Lista alias
/comandi_appresi — Comandi SSH memorizzati
/routine — Abitudini apprese

## 🌅 Briefing
/briefing — Morning briefing immediato
/spazzatura — Raccolta rifiuti

## 📚 Aiuto
/help — Start screen
/comandi — Menu principale
/comandi full — Questo documento completo
/ssh help — Guida SSH con esempi
/readme — Documentazione configurazione
"""


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
                 recurring_task_scheduler=None,
                 power_guard=None, config_editor=None,
                 rest_client=None, frigate_client=None,
                 alarm_code: str = "",
                 ws_client=None,
                 supervisor_token: str = "",
                 db=None):
        self.token    = token.strip()
        self._alarm_code = str(alarm_code or "").strip()
        self._ws_client  = ws_client
        self.allowed  = {str(c).strip() for c in allowed_chat_ids if c}
        self.ai_cb    = _make_rules_ai_cb(ai_callback)  # wrapper regole — copre tutti gli agenti
        self.action_cb= action_callback
        self.context_cb=context_callback
        self._db      = db
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
        self._memory    = MemoryManager(ai=ai_provider)
        self._shortcuts    = ShortcutsManager(state_cache_cb=state_cache_cb)
        self._local_parser = None  # inizializzato dopo home/rest disponibili
        self._routine = routine_manager
        self._task_scheduler            = task_scheduler
        self._recurring_task_scheduler  = recurring_task_scheduler
        self._power_guard    = power_guard
        self._config_editor  = config_editor
        self._rest_client       = rest_client
        self._frigate_client    = frigate_client
        self._session = None
        self._offset  = 0
        self._running = False
        self._histories = {}          # entity_id storico HA
        self._pending_alarm_confirm: dict = {}  # chat_id → asyncio.Future (risolto al click bottone)
        # Stato multi-step creazione task Alexa: chat_id → {step, message, when, speakers, volume, recurring}
        self._alexa_task_pending: dict = {}
        self._last_user_msg_id: dict = {}  # chat_id → id ultimo msg utente (per cancella)
        self._config_mgr = ConfigFileManager()
        self._config_pending: dict = {}  # chat_id → {file, new_content, diff, description}
        self._modify_target: dict = {}  # chat_id → file in attesa di descrizione modifica
        self._github_installer = GitHubInstaller(supervisor_token=supervisor_token)
        # HA Terminal: accesso info sistema e shell_command via Supervisor REST
        # Per ha_token usiamo la stessa supervisor_token (Supervisor proxy → Core API)
        self._ha_terminal = HATerminal(
            supervisor_token=supervisor_token,
            ha_token=supervisor_token,
        )
        self._github_pending: dict = {}  # chat_id → {step, type, url}
        self._agent_confirm: dict = {}  # chat_id → asyncio.Future per conferma agentic
        self._ai_mode: dict = {}  # chat_id → 'domotica' (default) | 'libera' (chat AI generica)
        # Cache temporanea speakers selezionabili nel picker inline
        self._alexa_speakers_cache: dict = {}  # chat_id → list[dict(eid,name,state)]
        self._conv_memory: dict = {}  # chat_id → [(role, text, timestamp), ...]
        self._email_wizard: dict = {}  # chat_id → stato wizard email multi-step

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
                    "allowed_updates": ["message", "callback_query"],
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
        # Salva l'id dell'ultimo messaggio utente per chat (per cancellazione con Cancella)
        _msg_store = upd.get("message") or {}
        _chat_inf = _msg_store.get("chat") or {}
        if _chat_inf.get("id") and _msg_store.get("message_id"):
            self._last_user_msg_id[str(_chat_inf["id"])] = _msg_store["message_id"]
        # ── Gestione callback_query (bottoni inline) ─────────────────────────
        cbq = upd.get("callback_query", {})
        if cbq:
            await self._handle_callback_query(cbq)
            return

        msg     = upd.get("message", {})
        if not msg:
            return
        chat_id  = str(msg.get("chat",{}).get("id",""))
        text     = msg.get("text","").strip()
        username = msg.get("from",{}).get("username","?")

        # ── Salva file in cartella ("invia nella cartella") ───────────────────
        # Attivo solo se abilitato nella pagina web (tab 📁 File); altrimenti non fa nulla
        # e il flusso resta identico a prima.
        try:
            if not text and await self._file_inbox_handle(chat_id, msg):
                return
        except Exception as _fie:
            logger.warning("file_inbox errore: %s", _fie)

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

        # ── Gestione foto/documenti per allegati email ────────────────────────
        _photo   = msg.get("photo")
        _doc     = msg.get("document")
        if (_photo or _doc) and not text:
            if self.allowed and chat_id not in self.allowed:
                await self._send(chat_id, t("unauthorized"))
                return
            # Solo se siamo in un wizard email in attesa di allegato
            wz = self._email_wizard.get(chat_id, {})
            if wz.get("step") == "attach":
                await self._email_handle_attachment(chat_id, msg)
            else:
                await self._send(chat_id,
                    "📎 <i>Hai inviato un file. Per allegarlo a un'email avvia prima il wizard:\n"
                    "scrivi /email → Nuova email o Rispondi, poi usa 📎 Aggiungi allegato.</i>")
            return
        if self.allowed and chat_id not in self.allowed:
            logger.warning("TG: accesso negato chat_id=%s", chat_id)  # username omesso per privacy
            await self._send(chat_id, t("unauthorized"))
            return
        logger.debug("TG msg da %s: [%d chars]", chat_id, len(text))  # contenuto non loggato per privacy
        await self._typing(chat_id)

        # ── Intercetta wizard "Modifica file con AI" ────────────────────
        if chat_id in self._modify_target:
            target_file = self._modify_target[chat_id]
            # Annulla con /annulla
            if text.strip().lower() in ("/annulla", "annulla"):
                self._modify_target.pop(chat_id, None)
                await self._send(chat_id, "❌ Modifica annullata.")
                return
            # Se è un altro comando di sistema, esce dal wizard
            if text.strip().startswith("/"):
                self._modify_target.pop(chat_id, None)
                # Continua col comando normale
            else:
                # Tratta il messaggio come descrizione modifica per file selezionato
                description = text.strip()
                # Rimuovi target dallo stato (non ripeterà su prossimo msg)
                self._modify_target.pop(chat_id, None)
                # Riusa la stessa pipeline di __CONFIG_CREATE_SENSOR__ ma con file specifico
                await self._do_ai_modify_file(chat_id, target_file, description)
                return

        # ── Intercetta wizard GitHub installer (input URL) ─────────────
        if chat_id in self._github_pending:
            pending = self._github_pending[chat_id]
            if text.strip().lower() in ("/annulla", "annulla"):
                self._github_pending.pop(chat_id, None)
                await self._send(chat_id, "❌ Installazione annullata.")
                return
            if text.strip().startswith("/"):
                self._github_pending.pop(chat_id, None)
                # Esce dal wizard, continua col comando
            elif pending.get("step") == "url":
                # L'utente ha scritto l'URL — verifica e mostra conferma
                info = parse_github_url(text.strip())
                if not info:
                    await self._send(chat_id,
                        f"⚠️ URL non valido: <code>{_html_escape(text[:200])}</code>\n\n"
                        f"Riprova con un URL nel formato <code>owner/repo</code>")
                    return
                # Salva URL e chiedi conferma
                pending["url"] = text.strip()
                full_url = f"https://github.com/{info['owner']}/{info['repo']}"
                type_labels = {
                    "addon":     "📦 Add-on Repository",
                    "component": "🧩 Custom Component",
                    "card":      "🎴 Card Lovelace",
                }
                body = (
                    f"🔗 <b>Conferma installazione</b>\n\n"
                    f"<i>Tipo:</i> {type_labels.get(pending['type'], pending['type'])}\n"
                    f"<i>Repository:</i> <code>{info['owner']}/{info['repo']}</code>\n"
                    f"<i>Branch:</i> <code>{info['branch']}</code>\n"
                    f"<i>URL:</i> {full_url}\n\n"
                    f"⚠️ <b>Procedere?</b>"
                )
                kb = {"inline_keyboard": [
                    [{"text": "✅ Installa", "callback_data": f"gh_confirm:{pending['type']}"}],
                    [{"text": "❌ Annulla",  "callback_data": "gh_cancel"}],
                ]}
                await self._send_with_keyboard(chat_id, body, kb)
                return

        # ── Intercetta wizard task Alexa (multi-step) ──────────────────
        if chat_id in self._alexa_task_pending:
            # Se non è il comando /annulla e non è un altro comando di sistema, passa al wizard
            if text.strip().startswith("/") and text.strip().lower() not in ("/annulla",):
                # Se l'utente scrive un altro comando, annulla il wizard silenziosamente
                self._alexa_task_pending.pop(chat_id, None)
                self._alexa_speakers_cache.pop(chat_id, None)
            else:
                handled = await self._handle_alexa_task_step(chat_id, text)
                if handled:
                    return

        # ── Intercetta wizard Email multi-step ────────────────────────────────
        if chat_id in self._email_wizard:
            if text.strip().lower() in ("/annulla", "annulla", "/cancel"):
                self._email_wizard.pop(chat_id, None)
                await self._send(chat_id, "❌ Wizard email annullato.")
                return
            if not text.strip().startswith("/"):
                handled = await self._handle_email_wizard_step(chat_id, text)
                if handled:
                    return

        # Intercetta conferme solare — solo se NON è un comando esplicito
        # Nota: len > 30 NON significa comando — frasi config possono essere lunghe
        _is_command = text.strip().startswith("/")
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

        # ── Meteo città esterne — DOPO config per non interferire ────────
        _weather_city = detect_city(text)
        # Non attivare per comandi config/briefing
        _is_config_phrase = any(k in text.lower() for k in (
            "rimuovi", "escludi", "aggiungi", "mostra", "ripristina",
            "briefing", "power guard", "soglia", "whitelist", "blacklist",
        ))
        if _weather_city and not text.strip().startswith("/") and not _is_config_phrase:
            try:
                _weather_result = await get_weather_for_city(_weather_city, self._session)
                await self._send(chat_id, _weather_result)
                return
            except Exception as _we:
                logger.warning("weather_external error: %s", _we)

        # Intercetta conferme config editor
        if self._config_editor and self._config_editor._pending:
            handled = await self._config_editor.handle_confirm(text)
            if handled:
                return

        # Gestione wizard config multi-step
        if self._config_editor and self._config_editor._wizard:
            handled = await self._config_editor.handle_wizard_step(text)
            if handled:
                return

        # Rilevamento modifiche config in linguaggio naturale
        if self._config_editor and not _is_command:
            handled = await self._try_config_edit(chat_id, text)
            if handled:
                return


        # ── DB INTERCEPT — prima del task scheduler per evitare scheduling di domande ──
        if hasattr(self, "_db") and self._db:
            try:
                _db_answer = None
                _q = text.lower()

                # Domande energetiche con keyword esplicite passato/ieri/data
                _energy_kw  = ("energia", "prodotto", "produzione", "fotovoltaic",
                               "kwh", "solare", "pannelli", "ho prodotto", "abbiamo prodotto")
                _time_kw    = ("ieri", "oggi", "gennaio","febbraio","marzo","aprile",
                               "maggio","giugno","luglio","agosto","settembre",
                               "ottobre","novembre","dicembre","settimana","mese",
                               "scorso","scorsa","fa","quant",
                               "lunedì","martedì","mercoledì","giovedì","venerdì",
                               "sabato","domenica")
                _is_energy_q = any(w in _q for w in _energy_kw) and any(w in _q for w in _time_kw)

                # Domande GPS persone — keyword verbo + keyword persona/luogo
                _gps_verbs = ("dove era", "dove si trovava", "dov'era", "dove stava",
                              "dove stato", "dove stata", "dove è stato", "dove è stata",
                              "dove ha sostato", "dove è andato", "dove è andata",
                              "dove si è fermato", "dove si è fermata",
                              "luoghi frequenti", "spesso va", "dove va di solito",
                              "dove era", "dove è stato", "dove è stata")
                _gps_time  = ("ieri", "oggi", "lunedì", "martedì", "mercoledì",
                              "giovedì", "venerdì", "sabato", "domenica",
                              "gennaio","febbraio","marzo","aprile","maggio",
                              "giugno","luglio","agosto","settembre","ottobre",
                              "novembre","dicembre","settimana","scorso","scorsa",
                              "stamattina","stamani","stanotte","ieri sera","ieri mattina")
                _is_gps_q = (
                    any(w in _q for w in _gps_verbs) or
                    (any(w in _q for w in ("dove", "stato", "stata", "andato", "andata"))
                     and any(w in _q for w in _gps_time))
                )

                # Domande elettrodomestici — rilevamento dinamico
                # Nomi statici (fallback se DB vuoto)
                _appliance_names_static = (
                    "lavatrice", "lavastoviglie", "lavabiancheria", "stoviglie",
                    "asciugatrice", "forno", "scaldabagno", "boiler",
                )
                # Nomi dal DB (include qualsiasi futuro elettrodomestico registrato)
                _db_appliance_names = []
                if self._db and hasattr(self._db, "get_known_appliances"):
                    _db_appliance_names = [a.lower() for a in self._db.get_known_appliances()]
                _all_appliance_names = list(set(list(_appliance_names_static) + _db_appliance_names))

                # Keyword storico/cicli → DB
                _cycle_kw = (
                    "cicli", "ciclo", "lavate", "lavaggio", "lavaggi",
                    "quante volte", "quanti cicli", "ultime lavat", "ultimi cicli",
                    "ultime 24", "ultime 48", "ha usato", "ho usato",
                    "ha girato", "ha finito", "utilizzi", "utilizzo",
                    "quante", "quanti", "ultimo ciclo", "ultima lavata",
                    "storico", "storia", "riepilogo",
                )
                _has_appliance  = any(w in _q for w in _all_appliance_names)
                _has_cycle_kw   = any(w in _q for w in _cycle_kw)
                _has_time_kw    = any(w in _q for w in list(_time_kw) + ["ultime", "ultimi", "24h", "48h"])
                _has_history_kw = _has_cycle_kw or _has_time_kw

                # Caso 1: solo nome elettrodomestico (max 4 parole, niente storico/tempo)
                #   → stato live da HA (es. "lavatrice", "lavastoviglie")
                _is_live_appliance_q = _has_appliance and not _has_history_kw and len(_q.split()) <= 4

                # Caso 2: nome + keyword storico/temporale → DB
                _is_appliance_history_q = _has_appliance and _has_history_kw

                if _is_live_appliance_q and self._appliance_monitor:
                    # Trova il nome più lungo che matcha (priorità nomi specifici)
                    _live_name = None
                    for _n in sorted(_all_appliance_names, key=len, reverse=True):
                        if _n in _q:
                            _live_name = _n
                            break
                    if _live_name:
                        _db_answer = self._appliance_monitor.status_message_single(_live_name)

                if _is_appliance_history_q and not _db_answer:
                    if self._db and hasattr(self._db, "natural_query_appliance"):
                        _db_answer = self._db.natural_query_appliance(text)

                if _is_energy_q and not _db_answer:
                    _db_answer = self._db.natural_query_energy(text)

                if not _db_answer and _is_gps_q:
                    # Cerca persona: prima in per_person (routine), poi nel DB
                    per_person = {}
                    if hasattr(self, "_routine") and self._routine:
                        per_person = self._routine._patterns.get("per_person", {})
                    # Candidati: nomi dalla routine + nomi distinti nel DB GPS
                    _person_candidates = list(per_person.keys())
                    if self._db and hasattr(self._db, "get_known_persons"):
                        _person_candidates += self._db.get_known_persons()
                    # Deduplicazione case-insensitive
                    _seen_low = set()
                    _person_candidates = [
                        p for p in _person_candidates
                        if p.lower() not in _seen_low and not _seen_low.add(p.lower())
                    ]
                    _target_person = None
                    for _pname in _person_candidates:
                        if _pname.lower() in _q:
                            _target_person = _pname
                            break
                    # Fallback: unica persona nel sistema
                    if not _target_person and len(_person_candidates) == 1:
                        _target_person = _person_candidates[0]
                    if _target_person:
                        # Prima prova a rinfrescare i dati da HA (se la routine è disponibile)
                        _refreshed = False
                        try:
                            import re as _re_date
                            import calendar as _cal
                            from datetime import date as _date_cls, timedelta as _td
                            from utils.timezone_helper import now_local as _now_local_fix
                            _now_d = _now_local_fix().date()
                            # Estrai la data dalla domanda
                            _MONTHS = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,
                                       "giugno":6,"luglio":7,"agosto":8,"settembre":9,
                                       "ottobre":10,"novembre":11,"dicembre":12}
                            _dm = _re_date.search(r"(\d{1,2})\s*(" + "|".join(_MONTHS.keys()) + r")\s*(\d{4})?", _q)
                            _target_date = None
                            if _dm:
                                try:
                                    _target_date = _date_cls(
                                        int(_dm.group(3) or _now_d.year),
                                        _MONTHS[_dm.group(2)],
                                        int(_dm.group(1))
                                    )
                                except ValueError:
                                    pass
                            elif "ieri" in _q:
                                _target_date = _now_d - _td(days=1)
                            # Se abbiamo una data specifica, ricarica da HA e aggiorna il DB
                            if _target_date and hasattr(self, "_routine") and self._routine and self._routine.rest:
                                from agent.location_tracker import get_person_stops, _get_tracker_eid
                                if _get_tracker_eid(_target_person):
                                    _days_back = (_now_d - _target_date).days + 1
                                    _hours_needed = min(_days_back * 24 + 12, 720)  # max 30 giorni
                                    logger.info("DB intercept: refresh GPS da HA per %s @ %s (%dh)",
                                                _target_person, _target_date, _hours_needed)
                                    _fresh_stops = await get_person_stops(
                                        self._routine.rest, _target_person,
                                        hours=_hours_needed, min_stop_min=8, radius_m=200
                                    )
                                    if _fresh_stops and not (len(_fresh_stops)==1 and "error" in _fresh_stops[0]):
                                        # Aggiorna il DB con i dati freschi
                                        if self._db:
                                            _pp = self._routine._patterns.get("per_person", {}).get(_target_person, {})
                                            for _fs in _fresh_stops:
                                                self._routine._apply_stop_to_person(_pp, _fs)
                                            _date_str = _target_date.isoformat()
                                            _day_stops = _pp.get("gps_stops_by_date", {}).get(_date_str, [])
                                            if _day_stops:
                                                await self._db.save_person_stops(_target_person, _date_str, _day_stops)
                                                logger.info("DB intercept: salvate %d soste nel DB per %s @ %s",
                                                            len(_day_stops), _target_person, _date_str)
                                        _refreshed = True
                        except Exception as _ref_ex:
                            logger.debug("DB intercept refresh error: %s", _ref_ex)
                        _db_answer = self._db.natural_query_person(_target_person, text)

                if _db_answer:
                    logger.info("DB intercept: risposta dal DB per: %s", text[:60])
                    await self._send(chat_id, _db_answer)
                    return
            except Exception as _dbi_ex:
                logger.debug("DB intercept error: %s", _dbi_ex)

        # Rilevamento task RIPETUTI — "ogni giorno alle 19 accendi X"
        # DEVE stare PRIMA di _try_schedule_task per avere priorità
        if self._recurring_task_scheduler:
            handled = await self._try_schedule_recurring(chat_id, text)
            if handled:
                return

        # Rilevamento task temporali UNA TANTUM — "accendi X alle 19"
        if self._task_scheduler:
            handled = await self._try_schedule_task(chat_id, text)
            if handled:
                return

        # ── Alias deterministici (prima dell'AI e dei quick command) ───────
        shortcut = self._shortcuts.match(text)
        if shortcut:
            cache = self.state_cache_cb() if self.state_cache_cb else {}
            result = await self._shortcuts.execute(shortcut, cache)
            if isinstance(result, str) and result.startswith("__SHORTCUT_CMD__"):
                cmd_target = result[len("__SHORTCUT_CMD__"):]
                # Simula un messaggio con il comando target
                # Crea un fake upd e passa al gestore principale
                _fake_upd = {"message": {"chat": {"id": int(chat_id)}, "from": {}, "text": cmd_target}}
                await self._handle_update(_fake_upd)
            else:
                await self._send(chat_id, result)
            return

        quick = self._quick_command(text)

        # Gestione comandi async speciali
        if quick == "__RICARICA_SPAZZATURA__":
            await self._send(chat_id, t("trash_loading"))
            if self.spazzatura_cb:
                sz = self.spazzatura_cb()
                if sz:
                    result = await sz.reload()
                    if sz.calendar:
                        await self._send(chat_id, result)
                        kb = {"inline_keyboard": [
                            [{"text": "🔄 Ricarica di nuovo", "callback_data": "menu_cmd:/ricarica_spazzatura"}],
                            [{"text": "🎩 Briefing",          "callback_data": "menu_cmd:/briefing"}],
                            [{"text": "🏠 Menu principale",   "callback_data": "menu_back"},
                             {"text": "🗑 Cancella",           "callback_data": "msg_delete"}],
                        ]}
                        await self._send_with_keyboard(chat_id, sz.telegram_summary(), kb)
                    else:
                        kb = {"inline_keyboard": [
                            [{"text": "🔄 Riprova",          "callback_data": "menu_cmd:/ricarica_spazzatura"}],
                            [{"text": "🏠 Menu principale",  "callback_data": "menu_back"},
                             {"text": "🗑 Cancella",          "callback_data": "msg_delete"}],
                        ]}
                        await self._send_with_keyboard(chat_id, result, kb)
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
                kb = {"inline_keyboard": [
                    [{"text": "🔄 Controlla di nuovo", "callback_data": "menu_cmd:/aggiornamenti"}],
                    [{"text": "🛠️ Riparazioni HA",     "callback_data": "menu_cmd:/riparazioni"}],
                    [{"text": "🏠 Menu principale",    "callback_data": "menu_back"},
                     {"text": "🗑 Cancella",            "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, result, kb)
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
                kb = {"inline_keyboard": [
                    [{"text": "🔄 Ricontrolla",    "callback_data": "menu_cmd:/riparazioni"}],
                    [{"text": "🔄 Aggiornamenti",  "callback_data": "menu_cmd:/aggiornamenti"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
                     {"text": "🗑 Cancella",        "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, result, kb)
            except Exception as e:
                await self._send(chat_id, t("error_short", msg=str(e)[:100]))
            return

        if quick == "__RESET_MEMORY__":
            self._conv_memory[chat_id] = []
            await self._send(chat_id, "🧹 Memoria conversazione azzerata. Ripartiamo da zero!")
            return

        if quick == "__ROUTINE__":
            if self._routine:
                _person_btns = []
                try:
                    _md_files = sorted(_ROUTINES_DIR.glob("*.md"))
                    _row = []
                    for _mf in _md_files:
                        _pname = _mf.stem
                        _row.append({"text": f"👤 {_pname}",
                                     "callback_data": f"menu_cmd:/routine leggi {_pname}"})
                        if len(_row) == 2:
                            _person_btns.append(_row)
                            _row = []
                    if _row:
                        _person_btns.append(_row)
                except Exception:
                    pass
                kb = {"inline_keyboard":
                    _person_btns +
                    [[{"text": "📄 Aggiorna .md", "callback_data": "menu_cmd:/routine aggiorna"},
                      {"text": "🔄 Rileggi GPS",  "callback_data": "menu_cmd:/routine rileggi"}],
                    [{"text": "♻️ Azzera",         "callback_data": "menu_cmd:/routine reset"},
                     {"text": "🏠 Menu",            "callback_data": "menu_back"}]]
                }
                await self._send_with_keyboard(chat_id, self._routine.get_status(), kb)
            else:
                await self._send(chat_id, "📅 Routine Manager non disponibile.")
            return

        if quick == "__ROUTINE_MD__":
            if self._routine and hasattr(self._routine, "force_write_md_async"):
                await self._send(chat_id,
                    "⏳ Leggo storico GPS 30 giorni + dati di oggi...\n"
                    "Può richiedere 1-2 minuti (reverse geocoding Nominatim).")
                async def _routine_md_task():
                    try:
                        result = await self._routine.force_write_md_async()
                        await self._send(chat_id, result)
                    except Exception as _rme:
                        await self._send(chat_id, f"❌ Errore: {_rme}")
                asyncio.create_task(_routine_md_task())
            else:
                await self._send(chat_id, "📅 Routine Manager non disponibile.")
            return

        if quick and quick.startswith("__ROUTINE_READ__:"):
            person_name = quick.split(":", 1)[1].strip().capitalize()
            md_path = _ROUTINES_DIR / f"{person_name}.md"
            if not md_path.exists():
                await self._send(chat_id, "⚠️ Nessun file routine per " + person_name + ".\nUsa /routine aggiorna per crearlo.")
                return
            try:
                raw = md_path.read_text(encoding="utf-8")
                msg = self._format_routine_for_telegram(person_name, raw)
                kb = {"inline_keyboard": [[
                    {"text": "🔄 Aggiorna", "callback_data": "menu_cmd:/routine aggiorna"},
                    {"text": "◀️ Routine",  "callback_data": "menu_cmd:/routine"},
                ]]}
                await self._send_with_keyboard(chat_id, msg, kb)
            except Exception as _re:
                await self._send(chat_id, f"❌ Errore lettura: {_re}")
            return

        if quick == "__ROUTINE_BACKFILL__":
            if self._routine:
                # Resetta il flag backfill e rilancia
                self._routine._patterns.pop("_backfill_done", None)
                await self._send(chat_id,
                    "🔄 Forzo la rilettura GPS 30 giorni con geocoding aggiornato...\n"
                    "Attendi 2-3 minuti.")
                async def _backfill_task():
                    try:
                        await self._routine._backfill_gps_history(days=31)
                        self._routine._write_all_person_md()
                        await self._send(chat_id, "✅ Backfill completato — file .md aggiornati con indirizzi reali.")
                    except Exception as _be:
                        await self._send(chat_id, f"❌ Errore backfill: {_be}")
                asyncio.create_task(_backfill_task())
            else:
                await self._send(chat_id, "📅 Routine Manager non disponibile.")
            return

        if quick == "__ROUTINE_RESET__":
            if self._routine and hasattr(self._routine, "reset_routine"):
                await self._send(chat_id, self._routine.reset_routine())
            else:
                await self._send(chat_id, "📅 Routine Manager non disponibile.")
            return

        if quick == "__DBTEST__":
            if not hasattr(self, "_db") or not self._db:
                await self._send(chat_id, "❌ DB non disponibile.")
                return
            try:
                import time as _t
                await self._db.save_energy_day("2026-04-01", {
                    "solar": 18.5, "grid_in": 2.1,
                    "grid_out": 9.3, "consume": 11.2
                })
                await self._send(chat_id,
                    "✅ <b>Dato test inserito nel DB</b>\n\n"
                    "📅 Data: 2026-04-01\n"
                    "☀️ FV: 18.5 kWh\n"
                    "🏠 Consumo: 11.2 kWh\n"
                    "🔌 Importata: 2.1 kWh\n"
                    "📤 Esportata: 9.3 kWh\n\n"
                    "Ora prova: <i>quanta energia ho prodotto il 1 aprile?</i>"
                )
            except Exception as _dte:
                await self._send(chat_id, f"❌ Errore DB test: {_dte}")
            return

        if quick == "__DB_STATS__":
            if self._db:
                await self._send(chat_id, self._db.get_stats())
            else:
                await self._send(chat_id, "🗄️ Database non disponibile.")
            return

        if quick in ("__POWER_GUARD_STATUS__", "__POWERGUARD__"):
            if self._power_guard:
                kb = {"inline_keyboard": [
                    [{"text": "🫧 Elettrodomestici", "callback_data": "menu_cmd:/elettrodomestici"}],
                    [{"text": "📊 Energia oggi",    "callback_data": "menu_cmd:/energia"},
                     {"text": "☀️ Surplus FV",       "callback_data": "menu_cmd:/solare"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"}, {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, self._power_guard.get_status(), kb)
            else:
                await self._send(chat_id, "⚡ Power Guard non disponibile.")
            return

        if quick == "__TASK_LIST__":
            if self._task_scheduler:
                from translations import get_lang
                lang = get_lang()
                text, kb = self._task_scheduler.get_tasks_interactive(lang)
                await self._send_with_keyboard(chat_id, text, kb)
            else:
                await self._send(chat_id, "⏰ Task Scheduler non disponibile.")
            return

        if quick == "__CONFIG_SHOW__":
            if self._config_editor:
                kb = {"inline_keyboard": [
                    [{"text": "🔄 Reset config",   "callback_data": "menu_cmd:/config reset"}],
                    [{"text": "🤖 Provider AI",    "callback_data": "menu_cmd:/providers"},
                     {"text": "🌐 Lingua",         "callback_data": "menu_cmd:/lingua"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
                     {"text": "🗑 Cancella",        "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, self._config_editor.get_config_display(), kb)
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

        if quick == "__RECURRING_TASK_LIST__":
            if self._recurring_task_scheduler:
                from translations import get_lang
                lang = get_lang()
                text, kb = self._recurring_task_scheduler.get_tasks_interactive(lang)
                await self._send_with_keyboard(chat_id, text, kb)
            else:
                await self._send(chat_id, "🔁 Task Ripetuti non disponibile.")
            return

        if quick == "__RECURRING_TASK_CLEAR__":
            if self._recurring_task_scheduler:
                self._recurring_task_scheduler.clear_all()
                await self._send(chat_id, "🔁 Tutti i task ripetuti cancellati.")
            return

        if isinstance(quick, str) and quick.startswith("__RECURRING_TASK_CANCEL__"):
            if self._recurring_task_scheduler:
                num_str = quick.replace("__RECURRING_TASK_CANCEL__", "").strip()
                try:
                    num = int(num_str)
                    task = self._recurring_task_scheduler.cancel_by_index(num)
                    if task:
                        await self._send(chat_id,
                            f"🔁 Task ripetuto cancellato: <b>{task['label']}</b>")
                    else:
                        await self._send(chat_id, f"🔁 Nessun task ripetuto numero {num}.")
                except ValueError:
                    await self._send(chat_id,
                        "🔁 Scrivi /cancella_task_ripetuto N (es. /cancella_task_ripetuto 1)")
            return

        # ── Handler Task Alexa ──────────────────────────────────────────────
        if quick == "__ALEXA_TASK_NEW__":
            await self._start_alexa_task(chat_id, is_recurring=False)
            return

        if quick == "__ALEXA_TASK_NEW_RECURRING__":
            await self._start_alexa_task(chat_id, is_recurring=True)
            return

        if quick == "__ALEXA_TASK_LIST__":
            # Lista task Alexa attivi (singoli + ricorrenti) con indici e bottoni
            lines = ["🔊 <b>Task Alexa attivi</b>", ""]
            idx = 1
            _rows = []
            if self._task_scheduler:
                for _tk in sorted(self._task_scheduler._tasks, key=lambda x: x["execute_at"]):
                    if _tk.get("command", "").startswith("__ALEXA_TTS__:"):
                        from datetime import datetime as _dt
                        when = _dt.fromtimestamp(_tk["execute_at"]).strftime("%d/%m %H:%M")
                        lbl = _tk["label"]
                        short_lbl = lbl[:25] + ("…" if len(lbl) > 25 else "")
                        lines.append(f"  <b>{idx}.</b> 🔊 {lbl}")
                        lines.append(f"      🕐 {when}")
                        _rows.append([{
                            "text": f"❌ Cancella #{idx}: {short_lbl}",
                            "callback_data": f"alxtask_del:{idx}"
                        }])
                        idx += 1
            if self._recurring_task_scheduler:
                for _tk in self._recurring_task_scheduler._sorted():
                    if _tk.get("command", "").startswith("__ALEXA_TTS__:"):
                        h, m = _tk.get("hour", 0), _tk.get("minute", 0)
                        dow = _tk.get("day_of_week")
                        sched = self._recurring_task_scheduler._dow_label(dow) + f" alle {h:02d}:{m:02d}"
                        lbl = _tk["label"]
                        short_lbl = lbl[:25] + ("…" if len(lbl) > 25 else "")
                        lines.append(f"  <b>{idx}.</b> 🔁🔊 {lbl}")
                        lines.append(f"      🕐 {sched}")
                        _rows.append([{
                            "text": f"❌ Cancella #{idx}: {short_lbl}",
                            "callback_data": f"alxtask_del:{idx}"
                        }])
                        idx += 1
            if idx == 1:
                # Nessun task → menu base con bottoni per creare nuovo
                text_empty = ("🔊 <b>Nessun task Alexa attivo</b>\n\n"
                              "<i>Crea il primo annuncio vocale!</i>")
                kb_empty = {"inline_keyboard": [
                    [{"text": "🆕 Nuovo annuncio singolo", "callback_data": "menu_cmd:/task_alexa"}],
                    [{"text": "🔁 Nuovo ricorrente",      "callback_data": "menu_cmd:/task_alexa_ripetuto"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"}, {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, text_empty, kb_empty)
                return
            # Pulsanti finali
            _rows.append([
                {"text": "🆕 Nuovo singolo",    "callback_data": "menu_cmd:/task_alexa"},
                {"text": "🔁 Nuovo ricorrente", "callback_data": "menu_cmd:/task_alexa_ripetuto"},
            ])
            _rows.append([{"text": "🏠 Menu principale", "callback_data": "menu_back"}, {"text": "🗑 Cancella", "callback_data": "msg_delete"}])
            await self._send_with_keyboard(chat_id, "\n".join(lines), {"inline_keyboard": _rows})
            return

        if isinstance(quick, str) and quick.startswith("__ALEXA_TASK_CANCEL__"):
            num_str = quick.replace("__ALEXA_TASK_CANCEL__", "").strip()
            try:
                num = int(num_str)
            except ValueError:
                await self._send(chat_id, "🔊 Scrivi /task_alexa_cancella N (es. /task_alexa_cancella 1)")
                return
            # Ricostruisci la lista unificata nello stesso ordine della visualizzazione
            unified = []
            if self._task_scheduler:
                for _tk in sorted(self._task_scheduler._tasks, key=lambda x: x["execute_at"]):
                    if _tk.get("command", "").startswith("__ALEXA_TTS__:"):
                        unified.append(("single", _tk))
            if self._recurring_task_scheduler:
                for _tk in self._recurring_task_scheduler._sorted():
                    if _tk.get("command", "").startswith("__ALEXA_TTS__:"):
                        unified.append(("recurring", _tk))
            if num < 1 or num > len(unified):
                await self._send(chat_id, f"🔊 Nessun task Alexa numero {num}.")
                return
            kind, task = unified[num - 1]
            if kind == "single":
                self._task_scheduler.cancel_task(task["id"])
            else:
                # Rimuovi per id dalla lista ricorrenti
                self._recurring_task_scheduler._tasks = [
                    x for x in self._recurring_task_scheduler._tasks if x["id"] != task["id"]
                ]
                self._recurring_task_scheduler._save()
            await self._send(chat_id, f"🔊 Task Alexa cancellato: <b>{task['label']}</b>")
            return

        # ── Schermata di benvenuto interattiva ──────────────────────────
        if quick == "__START_SCREEN__":
            await self._send_start_screen(chat_id)
            return

        # ── Menu principale a categorie ────────────────────────────────
        if quick == "__MENU_MAIN__":
            await self._send_main_menu(chat_id)
            return


        if quick == "__TOOLS_LIST__":
            _tl_lines = [
                "\U0001f6e0\ufe0f <b>Tool HomeMind</b> \u2014 disponibili in /fai, /ssh, /cerca\n",
                "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n",
                "\U0001f4c1 <b>FILE</b>\n",
                "\u2022 <code>tool_scrittura</code>   \u2014 crea/sovrascrive file\n",
                "\u2022 <code>tool_lettura</code>    \u2014 legge file (30k chars)\n",
                "\u2022 <code>tool_append</code>     \u2014 aggiunge testo in coda\n",
                "\u2022 <code>tool_mkdir</code>      \u2014 crea cartella\n",
                "\u2022 <code>tool_ls</code>         \u2014 lista cartella\n",
                "\u2022 <code>tool_delete</code>     \u2014 elimina file/cartella\n",
                "\u2022 <code>tool_file_info</code>  \u2014 info file (size, data, tipo)\n",
                "\u2022 <code>tool_find_files</code> \u2014 cerca file per nome/contenuto\n",
                "\u2022 <code>tool_move_file</code>  \u2014 sposta/rinomina\n",
                "\u2022 <code>tool_copy_file</code>  \u2014 copia file/cartella\n",
                "\u2022 <code>tool_replace_in_file</code> \u2014 trova e sostituisce in file\n",
                "\u2022 <code>tool_json_read</code>  \u2014 legge/naviga JSON o YAML\n\n",
                "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n",
                "\U0001f310 <b>WEB &amp; RETE</b>\n",
                "\u2022 <code>tool_search_web</code>       \u2014 ricerca DuckDuckGo\n",
                "\u2022 <code>tool_fetch_page</code>       \u2014 scarica pagina web\n",
                "\u2022 <code>tool_download</code>         \u2014 scarica file da URL\n",
                "\u2022 <code>tool_ping_python</code>      \u2014 ping host/IP\n",
                "\u2022 <code>tool_portscan_python</code>  \u2014 scansione porte\n",
                "\u2022 <code>tool_github_clone</code>     \u2014 clona repo GitHub (ZIP, no git)\n\n",
                "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n",
                "\U0001f4bb <b>SHELL &amp; SISTEMA</b>\n",
                "\u2022 <code>tool_shell_exec</code>       \u2014 shell nel container\n",
                "\u2022 <code>tool_natural_shell</code>    \u2014 NL \u2192 comando AI\n",
                "\u2022 <code>tool_install_package</code>  \u2014 apk add pacchetto\n",
                "\u2022 <code>tool_unzip_python</code>     \u2014 estrae .zip (Python nativo)\n",
                "\u2022 <code>tool_extract_tar_python</code> \u2014 estrae .tar.gz\n\n",
                "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n",
                "\U0001f9e0 <b>MEMORIA &amp; SSH</b>\n",
                "\u2022 <code>remember_command</code>       \u2014 memorizza cmd shell\n",
                "\u2022 <code>list_learned_commands</code>  \u2014 lista comandi appresi\n",
                "\u2022 <code>HATerminal.ssh_exec</code>    \u2014 SSH su host HA\n",
                "\u2022 <code>HATerminal.run_natural</code> \u2014 NL \u2192 SSH/Supervisor\n\n",
                "\U0001f4a1 <b>Esempi:</b>\n",
                "\u2022 <code>/ssh ram e cpu \u2192 ago/sistema.md</code>\n",
                "\u2022 <code>/fai cerca tutti i yaml in /config e listali</code>\n",
                "\u2022 <code>/fai sostituisci testo nel file ago/note.md</code>",
            ]
            _tl = "".join(_tl_lines)
            _kb_tl = {"inline_keyboard": [
                [{"text": "\U0001f916 Agente /fai", "callback_data": "menu_cmd:/agent"},
                 {"text": "\U0001f510 SSH",         "callback_data": "menu_cmd:/ssh"}],
                [{"text": "\U0001f4da Tutti i comandi", "callback_data": "menu_cmd:/comandi full"}],
                [{"text": "\U0001f3e0 Menu", "callback_data": "menu_back"}],
            ]}
            await self._send_with_keyboard(chat_id, _tl, _kb_tl)
            return

        if quick == "__COMANDI_FULL__":
            # Invia COMANDI.md come file Telegram + anteprima inline
            readme_paths = [
                "/app/COMANDI.md",
                "/config/ago/COMANDI.md",
                os.path.join(os.path.dirname(__file__), "..", "COMANDI.md"),
            ]
            readme_text = None
            for rp in readme_paths:
                try:
                    with open(rp, "r", encoding="utf-8") as f_r:
                        readme_text = f_r.read()
                    break
                except Exception:
                    pass
            if not readme_text:
                # Genera on-the-fly dalla lista interna
                readme_text = _COMANDI_README
            # Invia prime 3500 chars inline + bottone per leggerlo tutto
            preview = readme_text[:3500] + ("\n\n<i>... (usa /cerca leggi COMANDI.md per il testo completo)</i>" if len(readme_text) > 3500 else "")
            kb = {"inline_keyboard": [
                [{"text": "📖 Leggi tutto", "callback_data": "menu_cmd:/leggi /config/ago/COMANDI.md"}],
                [{"text": "🏠 Menu",        "callback_data": "menu_back"}],
            ]}
            await self._send_with_keyboard(chat_id, preview, kb)
            return

        if quick == "__RULES__":
            rules = _get_active_rules()
            if not rules:
                kb = {"inline_keyboard": [[{"text": "🏠 Menu", "callback_data": "menu_back"}]]}
                await self._send_with_keyboard(chat_id, "📋 <b>Nessuna regola attiva.</b>\n\nAggiungi regole dalla pagina web 📋 oppure modificando:\n<code>/config/homemind_patches/regole.md</code>", kb)
                return
            lines = ["📋 <b>Regole comportamentali attive</b>\n"]
            for i, r in enumerate(rules, 1):
                lines.append(f"  <b>{i}.</b> {r}")
            lines.append("\n<i>Premi ❌ per eliminare una regola</i>")
            # Bottoni elimina — uno per riga
            del_buttons = [[{"text": f"❌ Elimina regola {i}", "callback_data": f"rule_del:{i-1}"}]
                           for i in range(1, len(rules) + 1)]
            del_buttons.append([{"text": "🗑️ Elimina tutte", "callback_data": "rule_del_all"},
                                 {"text": "🏠 Menu",          "callback_data": "menu_back"}])
            kb = {"inline_keyboard": del_buttons}
            await self._send_with_keyboard(chat_id, "\n".join(lines), kb)
            return

        if isinstance(quick, str) and quick.startswith("__RULES_DEL__"):
            idx = int(quick.replace("__RULES_DEL__", ""))
            rules = _get_active_rules()
            if 0 <= idx < len(rules):
                removed = rules.pop(idx)
                _save_active_rules(rules)
                await self._send(chat_id, f"✅ Regola {idx+1} eliminata:\n<i>{removed}</i>")
            else:
                await self._send(chat_id, "⚠️ Regola non trovata.")
            return

        if quick == "__RULES_DEL_ALL__":
            _save_active_rules([])
            await self._send(chat_id, "🗑️ Tutte le regole sono state eliminate.")
            return

        if quick == "__MEMORY__":
            kb = {"inline_keyboard": [
                [{"text": "🗑️ Reset memoria", "callback_data": "menu_cmd:/memoria reset"}],
                [{"text": "🔗 Alias",         "callback_data": "menu_cmd:/alias"},
                 {"text": "🧠 Reset chat",    "callback_data": "menu_cmd:/dimentica"}],
                [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella",        "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, self._memory.get_facts_display(), kb)
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
                kb = {"inline_keyboard": [
                    [{"text": "📊 Energia oggi",  "callback_data": "menu_cmd:/energia"},
                     {"text": "🔍 Analisi 7gg",   "callback_data": "menu_cmd:/energia_analisi"}],
                    [{"text": "🫧 Elettrodomestici", "callback_data": "menu_cmd:/elettrodomestici"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"}, {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, so.get_status_message(), kb)
            else:
                await self._send(chat_id, "☀️ Ottimizzatore solare non configurato.")
            return

        if quick == "__APPLIANCES__":
            am = self._appliance_monitor
            if am:
                kb = {"inline_keyboard": [
                    [{"text": "🔍 Debug sensori",   "callback_data": "menu_cmd:/debug_elettrodomestici"}],
                    [{"text": "🗄️ Gestisci cicli DB", "callback_data": "menu_cmd:/db_fix"}],
                    [{"text": "⚡ Power Guard",     "callback_data": "menu_cmd:/powerguard"},
                     {"text": "☀️ Surplus FV",      "callback_data": "menu_cmd:/solare"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"}, {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, am.status_message(), kb)
            else:
                await self._send(chat_id, "🔌 Appliance monitor non disponibile.")
            return

        if quick and quick.startswith("__APPLIANCE_SINGLE:"):
            appliance_name = quick[len("__APPLIANCE_SINGLE:"):-2]
            am = self._appliance_monitor
            if am:
                await self._send(chat_id, am.status_message_single(appliance_name))
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

        # ── /db_fix — menu gestione cicli DB ─────────────────────────────────
        if quick == "__DB_FIX__":
            if not self._db:
                await self._send(chat_id, "❌ DB non disponibile.")
                return
            appliances = self._db.get_known_appliances()
            if not appliances:
                await self._send(chat_id, "🗄️ Nessun ciclo nel DB.")
                return
            kb_rows = []
            for ap in appliances:
                kb_rows.append([{
                    "text": f"🔧 {ap}",
                    "callback_data": f"dbfix:show:{ap}"
                }])
            kb_rows.append([
                {"text": "🗑 Cancella TUTTI i cicli", "callback_data": "dbfix:all:"},
                {"text": "🗑 Chiudi", "callback_data": "msg_delete"},
            ])
            kb = {"inline_keyboard": kb_rows}
            await self._send_with_keyboard(
                chat_id,
                "🗄️ <b>DB Fix — Gestione cicli</b>\n\nScegli un elettrodomestico per vedere e cancellare i suoi cicli:",
                kb
            )
            return


        if quick == "__ENERGY_ANALYSIS__":
            if self._energy_analyzer:
                await self._typing(chat_id)
                report = await self._energy_analyzer.analyze_on_demand(period_days=7)
                kb = {"inline_keyboard": [
                    [{"text": "📊 Energia oggi",  "callback_data": "menu_cmd:/energia"},
                     {"text": "📉 Energia ieri",  "callback_data": "menu_cmd:/ieri"}],
                    [{"text": "☀️ Surplus FV",    "callback_data": "menu_cmd:/solare"},
                     {"text": "⚡ Power Guard",   "callback_data": "menu_cmd:/powerguard"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"}, {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, report + self._ai_footer(), kb)
            else:
                await self._send(chat_id, "📊 Energy Analyzer non disponibile.")
            return

        if quick in ("__ENERGY_TODAY__", "__ENERGY_YESTERDAY__"):
            period = t("energy_period_today") if quick == "__ENERGY_TODAY__" else t("energy_period_yesterday")
            await self._typing(chat_id)
            try:
                result = await self.history_client.energy_summary(period)
                # Bottoni navigazione contestuali
                if quick == "__ENERGY_TODAY__":
                    nav_btn = {"text": "📉 Confronta con ieri", "callback_data": "menu_cmd:/ieri"}
                else:
                    nav_btn = {"text": "📊 Oggi",               "callback_data": "menu_cmd:/energia"}
                kb = {"inline_keyboard": [
                    [nav_btn,
                     {"text": "🔍 Analisi 7gg",   "callback_data": "menu_cmd:/energia_analisi"}],
                    [{"text": "☀️ Surplus FV",    "callback_data": "menu_cmd:/solare"},
                     {"text": "⚡ Power Guard",   "callback_data": "menu_cmd:/powerguard"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"}, {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, result, kb)
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
                kb = {"inline_keyboard": [
                    [{"text": "📖 Guida creazione", "callback_data": "menu_cmd:/automazioni_help"}],
                    [{"text": "🎨 Crea una card",   "callback_data": "menu_cmd:/crea_card"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"}, {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, result, kb)
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
                    _src = {"dashboard": " · pagina web", "opzioni": " · Opzioni add-on"}.get(getattr(p, "source", ""), "")
                    lines.append(f"{m} ✅ <b>{_html.escape(p.display)}</b>{_src}")
                    lines.append(f"   <code>{_html.escape(p.model)}</code>")
                    lines.append(f"   <i>Risposta: {r}</i>")
                except Exception as e:
                    err = str(e); el = err.lower()
                    _where = {"dashboard": "nella pagina web (AI Providers)",
                              "opzioni": "nelle Opzioni dell'add-on"}.get(getattr(p, "source", ""), "nelle Opzioni addon")
                    if "401" in err or "invalid_api_key" in el or "unauthorized" in el:
                        reason = f"API key non valida — controlla la chiave {_where}"
                    elif "429" in err or "rate_limit" in el:
                        reason = "Rate limit — riprova tra un minuto"
                    elif "quota" in el:
                        reason = "Quota giornaliera esaurita"
                    elif "model_not_found" in el or "404" in err:
                        reason = "Modello non trovato — cambia nome nelle Opzioni"
                    elif "timed out" in el or "timeout" in el:
                        reason = ("Nessuna risposta in tempo — modello non più disponibile, servizio lento o rete. "
                                  "Controlla il nome del modello")
                    elif "connection" in el:
                        reason = "Connessione fallita"
                    else:
                        reason = _html.escape(err[:80])
                    _src = {"dashboard": " · pagina web", "opzioni": " · Opzioni add-on"}.get(getattr(p, "source", ""), "")
                    lines.append(f"{m} ❌ <b>{_html.escape(p.display)}</b>{_src}")
                    lines.append(f"   <code>{_html.escape(p.model)}</code>")
                    lines.append(f"   <i>⚠️ {reason}</i>")
                lines.append("")

            last = getattr(ai_ref, "_last_used", None)
            if last:
                lines.append(f"⚡ <b>Attivo ora:</b> {_html.escape(last.display)}")

            kb = {"inline_keyboard": [
                [{"text": "⚙️ Config",          "callback_data": "menu_cmd:/config"},
                 {"text": "🔄 Aggiornamenti",   "callback_data": "menu_cmd:/aggiornamenti"}],
                [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella",        "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, "\n".join(lines), kb)
            return

        if quick == "__ALARM_INTERACTIVE__":
            if not self.state_cache_cb:
                await self._send(chat_id, "🔔 Allarme non disponibile.")
                return
            cache = self.state_cache_cb()
            alarm = next(
                ((eid, s) for eid, s in cache.items()
                 if eid.startswith("alarm_control_panel.")),
                None
            )
            if not alarm:
                await self._send(chat_id, "🔔 Nessun pannello allarme trovato.")
                return
            eid, s = alarm
            st   = s.get("state", "unknown")
            name = s.get("attributes", {}).get("friendly_name", eid)
            alarm_icons = {
                "armed_away":    "🔒 Armato (fuori)",
                "armed_home":    "🏠 Armato (in casa)",
                "armed_night":   "🌙 Armato (notte)",
                "armed_vacation": "✈️ Armato (vacanza)",
                "disarmed":      "🔓 Disarmato",
                "pending":       "⏳ In attivazione",
                "triggered":     "🚨 IN ALLARME!",
            }
            stato_str = alarm_icons.get(st, f"❓ {st}")
            # Testo
            body = (
                f"🛡️ <b>Pannello allarme</b>\n\n"
                f"<b>Stato:</b> {stato_str}\n"
                f"<b>Entità:</b> <code>{name}</code>\n\n"
                f"<i>Tocca un\'azione per cambiare modalità</i>"
            )
            # Tastiera: azioni rapide per cambiare modalità
            # Le callback usano il pattern __ALARM_MODE__:<mode> già esistente
            kb = {"inline_keyboard": [
                [{"text": "🔒 Armato (fuori)",  "callback_data": "__ALARM_MODE__:armed_away"},
                 {"text": "🏠 In casa",          "callback_data": "__ALARM_MODE__:armed_home"}],
                [{"text": "🌙 Notte",            "callback_data": "__ALARM_MODE__:armed_night"},
                 {"text": "🔓 Disarma",          "callback_data": "__ALARM_MODE__:disarmed"}],
                [{"text": "🎛️ Modalità auto/notify/off", "callback_data": "menu_cmd:/comandi allarme"}],
                [{"text": "🏠 Menu principale",  "callback_data": "menu_back"},
                 {"text": "🗑 Cancella",         "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return

        # ── Config editor: lettura file ─────────────────────────────────
        if quick == "__CONFIG_READ__":
            # Se c'è argomento dopo /leggi_config, quello è il file
            requested_file = "configuration.yaml"
            low = text.strip().lower()
            for prefix in ("/leggi_config ", "leggi config ", "leggi configurazione ",
                           "mostra configurazione ", "mostra config "):
                if low.startswith(prefix):
                    requested_file = text.strip()[len(prefix):].strip()
                    break
            try:
                content = self._config_mgr.read_file(requested_file)
                analysis = self._config_mgr.analyze_yaml_structure(content)

                # Header informativo con sezioni e include
                sections = ", ".join(analysis["sections"][:20]) or "(nessuna)"
                includes_info = ""
                if analysis["includes"]:
                    incs = "\n".join(f"  • <code>{i['key']}</code> → {i['path']} ({i['type']})"
                                      for i in analysis["includes"][:20])
                    includes_info = f"\n\n📂 <b>File inclusi:</b>\n{incs}"
                header = (
                    f"📄 <b>{requested_file}</b>\n"
                    f"<i>{analysis['num_lines']} righe · {len(analysis['sections'])} sezioni</i>\n\n"
                    f"📋 <b>Sezioni top-level:</b> {sections}"
                    f"{includes_info}"
                )
                await self._send(chat_id, header)
                # Invia contenuto completo spezzato in chunk
                await _send_long_file(self, chat_id, requested_file, content)
                # Bottoni azione
                kb = {"inline_keyboard": [
                    [{"text": "📁 Tutti i file",    "callback_data": "menu_cmd:/files_config"}],
                    [{"text": "💾 Lista backup",    "callback_data": "menu_cmd:/backups_config"}],
                    [{"text": "🛠️ Modifica con AI", "callback_data": "menu_cmd:/crea_sensore"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
                     {"text": "🗑 Cancella",         "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, "<i>Fine file</i>", kb)
            except FileNotFoundError:
                await self._send(chat_id, f"⚠️ File non trovato: <code>{requested_file}</code>")
            except Exception as e:
                logger.exception("CONFIG_READ FAIL")
                await self._send(chat_id, f"⚠️ Errore lettura: {str(e)[:300]}")
            return

        # ── Config editor: lista file configurazione ────────────────────
        if quick == "__CONFIG_FILES__":
            try:
                files = self._config_mgr.list_config_files()
                if not files:
                    await self._send(chat_id, "📁 Nessun file di configurazione trovato.")
                    return
                body = "📁 <b>File di configurazione HA</b>\n\n"
                rows = []
                for f in files:
                    size_kb = f["size"] / 1024
                    body += f"  📄 <code>{f['path']}</code>  <i>({f['lines']} righe, {size_kb:.1f}KB)</i>\n"
                    # Bottone per ogni file (troncare path per non superare 64 char callback)
                    btn_label = f["path"] if len(f["path"]) <= 30 else "…" + f["path"][-29:]
                    rows.append([{"text": f"📖 {btn_label}",
                                  "callback_data": f"cfg_read:{f['path']}"}])
                rows.append([
                    {"text": "🏠 Menu principale", "callback_data": "menu_back"},
                    {"text": "🗑 Cancella",         "callback_data": "msg_delete"},
                ])
                await self._send_with_keyboard(chat_id, body, {"inline_keyboard": rows})
            except Exception as e:
                logger.exception("CONFIG_FILES FAIL")
                await self._send(chat_id, f"⚠️ Errore: {str(e)[:200]}")
            return

        # ── Config editor: help ─────────────────────────────────────────
        if quick == "__CONFIG_CREATE_SENSOR_HELP__":
            body = (
                "🛠️ <b>Crea/modifica configurazione con AI</b>\n\n"
                "Uso: <code>/crea_sensore &lt;descrizione&gt;</code>\n\n"
                "<b>Esempi base (modifica configuration.yaml):</b>\n"
                "• <code>/crea_sensore consumo giornaliero scaldabagno</code>\n"
                "• <code>/crea_sensore template temperatura media casa</code>\n"
                "• <code>/crea_sensore utility_meter mensile bolletta luce</code>\n\n"
                "<b>Modifica altri file (<code>--file &lt;path&gt;</code>):</b>\n"
                "• <code>/crea_sensore --file automations.yaml automazione "
                "accendi luci alle 19</code>\n"
                "• <code>/crea_sensore --file scripts.yaml script saluto mattino</code>\n"
                "• <code>/crea_sensore --file packages/energia.yaml "
                "sensore costo bolletta</code>\n\n"
                "<i>HomeMind fa automaticamente:\n"
                "1. Legge il file esistente\n"
                "2. Analizza le tue entità HA pertinenti\n"
                "3. Genera codice coerente con lo stile esistente\n"
                "4. Mostra dove verrà inserito e chiede conferma\n"
                "5. Prima di scrivere → backup automatico in\n"
                "   <code>/config/homemind_patches/</code></i>"
            )
            kb = {"inline_keyboard": [
                [{"text": "📁 Tutti i file",    "callback_data": "menu_cmd:/files_config"}],
                [{"text": "📄 Leggi config",    "callback_data": "menu_cmd:/leggi_config"}],
                [{"text": "💾 Lista backup",    "callback_data": "menu_cmd:/backups_config"}],
                [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella",         "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return

        # ── Config editor: crea sensore ─────────────────────────────────
        if quick == "__CONFIG_CREATE_SENSOR__":
            # Estrai descrizione dal testo originale
            description = text.strip()
            # Rimuovi comando iniziale
            for prefix in ("/crea_sensore ", "crea sensore ",
                           "/modifica_config ", "modifica config ",
                           "/modifica ", "modifica file "):
                if description.lower().startswith(prefix.lower()):
                    description = description[len(prefix):].strip()
                    break
            if not description:
                await self._send(chat_id, "⚠️ Usa: <code>/crea_sensore &lt;descrizione&gt;</code>")
                return

            # ── Estrai istruzioni extra: "scrivi in PATH", "leggi PATH" ────────
            import re as _re_cs
            _extra_write_path = None
            _extra_read_after = False

            # "scrivi risultato in ago/..." o "scrivi in ago/..."
            _m_write = _re_cs.search(
                r"scrivi(?:\s+(?:il\s+)?(?:risultato|codice|yaml|output))?\s+(?:in\s+)?([^\s]+\.md|[^\s]+\.yaml|[^\s]+\.txt)",
                description, _re_cs.IGNORECASE
            )
            if _m_write:
                _extra_write_path = _m_write.group(1).strip()
                # Rimuovi questa parte dalla description principale
                description = description[:_m_write.start()].strip() + " " + description[_m_write.end():].strip()
                description = description.strip()

            # "leggi PATH" o "mostra" dopo scrivi
            _m_read = _re_cs.search(
                r"(?:leggi|mostra(?:mi)?|visualizza|apri)\s+(?:il\s+)?(?:file\s+)?([^\s]+\.md|[^\s]+\.yaml|ago/[^\s]+)",
                description, _re_cs.IGNORECASE
            )
            if _m_read or _re_cs.search(r"\bmostra(?:mi)?\b|\bleggi\b|\bvedi\b", description, _re_cs.IGNORECASE):
                _extra_read_after = True
                # Rimuovi dalla description
                if _m_read:
                    description = description[:_m_read.start()].strip() + " " + description[_m_read.end():].strip()
                    description = description.strip()

            await self._typing(chat_id)
            try:
                # 1. Determina file target (default configuration.yaml)
                pending_file = "configuration.yaml"
                # Se l'utente scrive "--file nomefile.yaml descrizione" lo estraggo
                if "--file" in description:
                    import re as _re
                    m = _re.search(r'--file\s+(\S+)', description)
                    if m:
                        pending_file = m.group(1)
                        description = description.replace(m.group(0), "").strip()
                # 2. Leggi config esistente
                existing = self._config_mgr.read_file(pending_file)
                analysis = self._config_mgr.analyze_yaml_structure(existing)

                # 2. Prepara contesto entità per AI (smart match con friendly_name + tokens)
                cache = self.state_cache_cb() if self.state_cache_cb else {}
                matches = _smart_entity_match(cache, description, max_results=50)
                entities_ctx = _format_entities_for_ai(matches)

                # 3. Prepara lista sezioni esistenti per AI
                sections_list = ", ".join(analysis["sections"][:20]) or "(vuota)"
                includes_txt = ""
                for inc in analysis["includes"][:10]:
                    includes_txt += f"\n  - {inc['key']} viene da {inc['path']} ({inc['type']})"

                # 4. Sistema AI specifico
                system_prompt = (
                    "Sei un esperto Home Assistant. L'utente vuole creare un sensore/template "
                    "per la sua configurazione.\n\n"
                    "REGOLE STRETTE:\n"
                    "1. Rispondi SOLO con YAML valido, niente markdown, niente testo extra.\n"
                    "2. Il YAML deve iniziare con la sezione top-level corretta "
                    "(es. `utility_meter:`, `sensor:`, `template:`).\n"
                    "3. ⚠️ USA SOLO ed ESCLUSIVAMENTE gli entity_id forniti nella lista "
                    "'Entità HA disponibili' qui sotto. NON inventare entity_id come "
                    "'sensor.sensori_watt' o nomi generici. Se l'entità che ti serve non "
                    "è nella lista, scegli quella più simile dalla lista o dichiaralo "
                    "esplicitamente come commento YAML.\n"
                    "4. Rispetta la sintassi HA moderna (template come lista con `- sensor:`).\n"
                    "5. Niente commenti eccessivi dentro il YAML."
                )
                user_prompt = (
                    f"Richiesta: {description}\n\n"
                    f"Sezioni già presenti in configuration.yaml: {sections_list}\n"
                    f"File inclusi:{includes_txt or ' (nessuno)'}\n\n"
                    f"Entità HA pertinenti:\n{entities_ctx}\n\n"
                    f"Genera SOLO il YAML da aggiungere (inizia con la chiave top-level)."
                )

                if not self.ai_cb:
                    await self._send(chat_id, "⚠️ AI non disponibile.")
                    return

                ai_response = await self.ai_cb(system_prompt, user_prompt, None)
                if not ai_response:
                    await self._send(chat_id, "⚠️ AI non ha risposto.")
                    return

                # Estrai YAML pulito dalla risposta
                yaml_snippet = _extract_yaml(ai_response)
                if not yaml_snippet:
                    await self._send(chat_id, f"⚠️ AI ha risposto ma non ho trovato YAML valido:\n\n<pre>{_html_escape(ai_response[:1500])}</pre>")
                    return

                # 4b. Validazione: l'AI ha usato solo entità reali?
                invented = _validate_entities_in_yaml(yaml_snippet, cache)
                invented_warning = ""
                if invented:
                    invented_warning = (
                        f"\n\n⚠️ <b>ATTENZIONE — entity_id inventate dall\'AI:</b>\n"
                        + "\n".join(f"  • <code>{e}</code>" for e in invented[:8])
                        + "\n\n<i>Queste entità NON esistono in HA. "
                        f"Verifica e correggi manualmente prima di applicare.</i>"
                    )

                # 5. Smart insert
                result = self._config_mgr.smart_insert(existing, yaml_snippet)

                if not result["success"]:
                    if result.get("strategy") == "include_warning":
                        warn_msg = (
                            f"⚠️ <b>Attenzione</b>\n\n{result['warning']}\n\n"
                            f"<b>YAML generato:</b>\n<pre>{_html_escape(yaml_snippet[:2000])}</pre>"
                        )
                        await self._send(chat_id, warn_msg)
                    else:
                        await self._send(chat_id, f"⚠️ {result.get('error', 'Errore sconosciuto')}")
                    return

                # 6. Salva pending e mostra preview con bottoni
                self._config_pending[chat_id] = {
                    "file":        pending_file,
                    "new_content": result["new_content"],
                    "description": description,
                    "section":     result["section"],
                    "strategy":    result["strategy"],
                    "yaml_added":  yaml_snippet,
                    # Istruzioni extra post-apply
                    "extra_write_path": _extra_write_path,
                    "extra_read_after": _extra_read_after,
                }

                strategy_lbl = "🔄 Merge nella sezione esistente" if result["strategy"] == "merged" \
                               else "➕ Nuova sezione in fondo"

                header = (
                    f"🛠️ <b>Proposta modifica</b>\n"
                    f"<i>File:</i> <code>{pending_file}</code>\n"
                    f"<i>Sezione:</i> <code>{result['section']}</code>\n"
                    f"<i>Strategia:</i> {strategy_lbl}"
                    f"{invented_warning}\n\n"
                    f"<b>📝 YAML da aggiungere ({len(yaml_snippet.splitlines())} righe):</b>"
                )
                await self._send(chat_id, header)
                # Invia YAML completo senza troncare
                await _send_long_file(self, chat_id, f"Nuovo YAML → {pending_file}", yaml_snippet)
                # Bottoni finali
                footer = ("💾 Se procedi, sarà creato un backup in "
                          "<code>/config/homemind_patches/</code>")
                kb = {"inline_keyboard": [
                    [{"text": "✅ Applica modifica", "callback_data": "config_apply"}],
                    [{"text": "📊 Mostra diff",     "callback_data": "config_diff"}],
                    [{"text": "❌ Annulla",          "callback_data": "config_cancel"}],
                ]}
                await self._send_with_keyboard(chat_id, footer, kb)

            except Exception as e:
                logger.exception("create_sensor FAIL")
                await self._send(chat_id, f"⚠️ Errore: {str(e)[:300]}")
            return

        # ── GitHub Installer: menu principale ──────────────────────────
        if quick == "__GITHUB_MENU__":
            body = (
                "🔗 <b>Installa da GitHub</b>\n\n"
                "<i>Wizard guidato per installare componenti dal mondo GitHub.</i>\n\n"
                "<b>Cosa vuoi installare?</b>\n\n"
                "📦 <b>Add-on</b> — repository di addon (estende le funzionalità di HA)\n"
                "🧩 <b>Custom Component</b> — integrazione custom (es. da HACS)\n"
                "🎴 <b>Card Lovelace</b> — card UI per dashboard\n"
            )
            kb = {"inline_keyboard": [
                [{"text": "📦 Add-on Repository",  "callback_data": "gh_type:addon"}],
                [{"text": "🧩 Custom Component",   "callback_data": "gh_type:component"}],
                [{"text": "🎴 Card Lovelace",      "callback_data": "gh_type:card"}],
                [{"text": "🏠 Menu",                "callback_data": "menu_back"},
                 {"text": "🗑 Cancella",            "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return

        # ── Agent: help ─────────────────────────────────────────────────
        if quick == "__AGENT_HELP__":
            body = (
                "🤖 <b>Modalità Agente Autonomo</b>\n\n"
                "<i>HomeMind esegue task complessi in autonomia, scegliendo i tool giusti.</i>\n\n"
                "<b>Uso:</b>\n"
                "<code>/fai &lt;descrizione del task&gt;</code>\n\n"
                "<b>Esempi pratici:</b>\n\n"
                "📦 <code>/fai scarica github.com/user/repo in ago/test poi mostrami struttura</code>\n"
                "📝 <code>/fai leggi ago/main.py e correggi gli errori di sintassi</code>\n"
                "🔄 <code>/fai sposta tutti i .py da ago in ago/progetti</code>\n"
                "🔍 <code>/fai cerca dove esce questa documentazione card x e creami file con guida</code>\n"
                "📊 <code>/fai elencami i miei sensori energia e crea un riepilogo in note/energia.md</code>\n"
                "🛠️ <code>/fai leggi automations.yaml e correggi automazione luci salotto</code>\n\n"
                "<b>L\'agente ha questi strumenti:</b>\n"
                "  📁 ls / read / write / append / mkdir\n"
                "  📦 move / copy / delete (con conferma)\n"
                "  ⬇️ download / clone\n"
                "  🔍 search_web / fetch_page\n"
                "  🤖 ai_generate (per correggere/riscrivere)\n"
                "  🏠 list_entities (entità HA)\n\n"
                "<i>Sicurezza: tutto dentro /config, file protetti non toccati, "
                "delete chiede conferma.</i>"
            )
            kb = {"inline_keyboard": [
                [{"text": "🧰 Tool diretti", "callback_data": "menu_cmd:/tools"}],
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return

        # ── Shell help ──────────────────────────────────────────────────
        if quick == "__SSH_COMMANDS_README__":
            # Invia il README comandi come documento .md
            readme_paths = [
                os.path.join(os.path.dirname(__file__), "..", "README_COMANDI.md"),
                "/opt/homemind/README_COMANDI.md",
                "/app/README_COMANDI.md",
                "/config/homemind_patches/README_COMANDI.md",
            ]
            readme_text = None
            for rp in readme_paths:
                try:
                    with open(rp, "r", encoding="utf-8") as _rf:
                        readme_text = _rf.read()
                    break
                except FileNotFoundError:
                    continue
            if readme_text:
                # Invia come file .md (se lungo) o come testo (se breve)
                if len(readme_text) > 3800:
                    await _send_long_file(self, chat_id, "HomeMind_Comandi.md", readme_text)
                else:
                    await self._send(chat_id, readme_text)
            else:
                # Fallback: mostra lista comandi inline
                body = (
                    "📋 <b>HomeMind — Comandi principali</b>\n\n"
                    "<b>🔐 SSH & Terminale</b>\n"
                    "• <code>/ssh</code> — menu SSH\n"
                    "• <code>/ssh <richiesta></code> — esegui naturale (host HA o container)\n"
                    "• <code>/ssh cmd: <cmd></code> — SSH diretto senza AI\n\n"
                    "<b>🔍 Ricerca & File</b>\n"
                    "• <code>/cerca <query></code> — cerca sul web\n"
                    "• <code>/cerca <query> salva in <path></code> — cerca e salva\n"
                    "• <code>/cerca <query> sovrascrivi <path></code> — cerca e sovrascrivi\n"
                    "• <code>/scrivi <path> <testo></code> — scrivi file\n"
                    "• <code>/leggi <path></code> — leggi file\n"
                    "• <code>/ls <path></code> — lista cartella\n\n"
                    "<b>🤖 AI & Agente</b>\n"
                    "• <code>/fai <obiettivo></code> — agente AI\n"
                    "• <code>/providers</code> — gestisci provider AI\n\n"
                    "<b>🏠 Home Assistant</b>\n"
                    "• <code>/ha_sistema</code> — info HA\n"
                    "• <code>/automazioni</code> — lista automazioni\n"
                    "• <code>/modifica <file> <istruzione></code> — modifica yaml\n\n"
                    "💡 <i>Path file: usa sempre <code>config/ago/...</code> o <code>/config/ago/...</code></i>\n"
                    "💡 <i>Append vs sovrascrittura: default aggiunge, scrivi 'sovrascrivi' per rimpiazzare</i>"
                )
                kb = {"inline_keyboard": [
                    [{"text": "🔐 SSH", "callback_data": "menu_cmd:/ssh"}],
                    [{"text": "🏠 Menu", "callback_data": "menu_back"}],
                ]}
                await self._send_with_keyboard(chat_id, body, kb)
            return

        if quick == "__SSH_HELP__":
            body = (
                "🔐 <b>/ssh — Terminale unificato</b>\n\n"
                "<i>Unico comando per eseguire qualsiasi cosa: comandi shell sul container HomeMind "
                "OPPURE comandi sull'host HA via SSH. L'AI capisce cosa vuoi e sceglie il canale giusto.</i>\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🖥️ <b>COMANDI HOST (via SSH su HA)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "• <code>/ssh mostrami ram e cpu</code>\n"
                "• <code>/ssh quanto disco è occupato</code>\n"
                "• <code>/ssh lista tutti gli addon installati</code>\n"
                "• <code>/ssh riavvia l'addon mosquitto</code>\n"
                "• <code>/ssh mostrami il log di homeassistant</code>\n"
                "• <code>/ssh apri porta 80 sul firewall</code>\n"
                "• <code>/ssh ping 192.168.1.1</code>\n"
                "• <code>/ssh scansiona porte aperte su 192.168.1.90</code>\n"
                "• <code>/ssh qual è l'ip del server</code>\n"
                "• <code>/ssh temperatura cpu</code>\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📦 <b>GESTIONE ADDON (ha CLI)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "• <code>/ssh ha addons list</code> — elenca addon (con slug)\n"
                "• <code>/ssh ha addons stop &lt;slug&gt;</code> — ferma addon\n"
                "• <code>/ssh ha addons start &lt;slug&gt;</code> — avvia addon\n"
                "• <code>/ssh ha addons restart &lt;slug&gt;</code> — riavvia addon\n"
                "• <code>/ssh ha addons info &lt;slug&gt;</code> — info dettagliate\n"
                "• <code>/ssh ha addons logs &lt;slug&gt;</code> — log addon\n"
                "• <code>/ssh ha addons uninstall &lt;slug&gt;</code> — disinstalla\n"
                "<i>💡 Lo slug NON contiene spazi. Esempio: <code>core_mosquitto</code>, "
                "<code>a0d7b954_aiautomation</code>. Usa <code>ha addons list</code> "
                "per scoprire lo slug esatto.</i>\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🏠 <b>GESTIONE HOME ASSISTANT</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "• <code>/ssh ha core restart</code> — riavvia HA Core\n"
                "• <code>/ssh ha core stop</code> — ferma HA Core\n"
                "• <code>/ssh ha core check</code> — valida config prima di restart\n"
                "• <code>/ssh ha core logs</code> — log HA Core\n"
                "• <code>/ssh ha supervisor info</code> — info Supervisor\n"
                "• <code>/ssh ha supervisor logs</code> — log Supervisor\n"
                "• <code>/ssh ha host reboot</code> — riavvia il sistema HA OS\n"
                "• <code>/ssh ha host shutdown</code> — spegne il sistema HA OS\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "💻 <b>COMANDI CONTAINER (HomeMind)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "• <code>/ssh ls /config</code>\n"
                "• <code>/ssh dimmi i permessi di /config/ago</code>\n"
                "• <code>/ssh elenca i file in ago ordinati per dimensione</code>\n"
                "• <code>/ssh crea un .tar.gz di ago/progetto in ago/backup.tar.gz</code>\n"
                "• <code>/ssh quanto spazio occupa la cartella media</code>\n"
                "• <code>/ssh cerca tutti i file .yaml in /config</code>\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "⚡ <b>COMANDI DIRETTI (eseguiti via SSH sull'host)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "• <code>/ssh cmd: df -h</code> — forza SSH host\n"
                "• <code>/ssh cmd: systemctl status hass</code>\n"
                "• <code>/ssh cmd: cat /proc/meminfo</code>\n"
                "• <code>/ssh cmd: ls /homeassistant</code>\n\n"
                "💡 <i>Prefisso <code>cmd:</code> → forza esecuzione SSH sull'host senza AI.</i>\n\n"
                "📖 Scrivi <code>/ssh help</code> per il README completo di tutti i comandi."
            )
            kb = {"inline_keyboard": [
                [{"text": "🖥️ Stato HA",      "callback_data": "menu_cmd:/ha_sistema"},
                 {"text": "📦 Addon",          "callback_data": "menu_cmd:/ha_addons"}],
                [{"text": "🛠️ Tool disponibili","callback_data": "menu_cmd:/tools"},
                 {"text": "🤖 Agente /fai",    "callback_data": "menu_cmd:/agent"}],
                [{"text": "📚 Tutti i comandi","callback_data": "menu_cmd:/comandi full"}],
                [{"text": "🏠 Menu",            "callback_data": "menu_back"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return


        if quick == "__HA_SYSTEM__":
            await self._typing(chat_id)
            try:
                res = await self._ha_terminal.host_resources()
                if not res.get("success"):
                    await self._send(chat_id,
                        f"⚠️ Info sistema non disponibili: {res.get('message','?')}")
                    return
                body = HATerminal.format_resources(res["data"])
                kb = {"inline_keyboard": [
                    [{"text": "📦 Addon", "callback_data": "menu_cmd:/ha_addons"}],
                    [{"text": "🔄 Aggiorna", "callback_data": "menu_cmd:/ha_sistema"}],
                    [{"text": "🏠 Menu", "callback_data": "menu_back"},
                     {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, body, kb)
            except Exception as e:
                logger.exception("ha_system")
                await self._send(chat_id, f"⚠️ Errore: {str(e)[:200]}")
            return

        # ── HA Host: help ───────────────────────────────────────────────
        
        if quick == "__SSH_RUN__":
            raw = text.strip()
            _SSH_STRIP = (
                "/ssh ", "ssh ", "/host ", "host ", "/ha ", "/shell ", "shell ",
                "/shh ", "/sssh ", "/shs ", "/ssg ", "/sch ",  # typo frequenti
            )
            for prefix in _SSH_STRIP:
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            user_req = raw.strip()

            # ── Rileva "salva in <path>" / "→ <path>" ───────────────────────
            save_path = None
            _save_patterns = [
                r'\\s+salva\\s+(?:il\\s+)?(?:risultato\\s+)?in\\s+(\\S+)',
                r'\\s+scrivi\\s+(?:il\\s+)?(?:risultato\\s+)?in\\s+(\\S+)',
                r'\\s+salvalo\\s+in\\s+(\\S+)',
                r'\\s*→\\s*(\\S+)',
                r'\\s+>\\s*(\\S+\\.(?:md|txt|log|json|yaml|csv))',
            ]
            for _pat in _save_patterns:
                _m2 = re.search(_pat, user_req, re.IGNORECASE)
                if _m2:
                    save_path = _normalize_user_path(_m2.group(1))
                    user_req  = user_req[:_m2.start()].strip()
                    break

            # ── Modalità cmd: diretta ─────────────────────────────────────────
            if user_req.lower().startswith("cmd:"):
                direct_cmd = user_req[4:].strip()
                if not direct_cmd:
                    await self._send(chat_id, "⚠️ Uso: <code>/ssh cmd: &lt;comando&gt;</code>")
                    return
                await self._send(chat_id, f"🖥️ <i>SSH:</i> <code>{_html_escape(direct_cmd[:200])}</code>")
                try:
                    # Intercetta ha/systemctl → Supervisor API
                    _dc = direct_cmd.strip()
                    if _dc.startswith("ha ") or _dc.startswith("hassio "):
                        res = await self._ha_terminal.ha_cli(_dc)
                        out = res.get("result", res.get("message", ""))
                        kb_ha = {"inline_keyboard": [
                            [{"text": "💾 Salva output", "callback_data": "ssh_save_last"}],
                            [{"text": "🏠 Menu", "callback_data": "menu_back"},
                             {"text": "🗑",      "callback_data": "msg_delete"}],
                        ]}
                        if not hasattr(self, "_last_ssh_output"):
                            self._last_ssh_output = {}
                        self._last_ssh_output[chat_id] = {
                            "text": re.sub(r"<[^>]+>", "", out)[:8000],
                            "cmd": direct_cmd[:200], "channel": "Supervisor API"}
                        await self._send_with_keyboard(chat_id,
                            f"📡 <b>Supervisor API</b>\n\n{out[:4000]}", kb_ha)
                        return
                    res = await self._ha_terminal.ssh_exec(direct_cmd, timeout=30)
                    out = (res.get("stdout") or "").strip()
                    err = (res.get("stderr") or "").strip()
                    via = res.get("via", "SSH")
                    output_text = out or err or "(nessun output)"
                    body = f"📡 <b>{via}</b>\\n\\n"
                    if out:
                        body += f"<pre>{_html_escape(out[:3500])}</pre>"
                    if err:
                        body += f"\\n⚠️ <pre>{_html_escape(err[:800])}</pre>"
                    if save_path:
                        _md = f"# `{direct_cmd}`\\n\\n```\\n{output_text}\\n```\\n"
                        wr = _tools.tool_scrittura(save_path, _md)
                        body += f"\\n\\n💾 <b>Salvato:</b> <code>/config/{wr.get('path', save_path)}</code>"
                        kb = {"inline_keyboard": [
                            [{"text": "📂 Leggi", "callback_data": f"menu_cmd:/leggi {save_path}"}],
                            [{"text": "🏠 Menu",  "callback_data": "menu_back"}],
                        ]}
                    else:
                        if not hasattr(self, "_last_ssh_output"):
                            self._last_ssh_output = {}
                        self._last_ssh_output[chat_id] = {
                            "text": output_text[:8000], "cmd": direct_cmd[:200], "channel": via}
                        kb = {"inline_keyboard": [
                            [{"text": "💾 Salva output", "callback_data": "ssh_save_last"}],
                            [{"text": "🏠 Menu", "callback_data": "menu_back"},
                             {"text": "🗑",      "callback_data": "msg_delete"}],
                        ]}
                    await self._send_with_keyboard(chat_id, body, kb)
                except Exception as e:
                    await self._send(chat_id, f"⚠️ SSH errore: {str(e)[:300]}")
                return

            if not user_req:
                await self._send(chat_id,
                    "⚠️ Specifica cosa vuoi fare:\\n"
                    "• <code>/ssh mostrami ram e cpu</code>\\n"
                    "• <code>/ssh cmd: df -h</code> (SSH diretto)\\n"
                    "• <code>/ssh cerca file yaml in /config</code>\\n\\n"
                    "Scrivi solo <code>/ssh</code> per il menu.")
                return

            await self._send(chat_id, f"🤖 <i>Elaboro:</i> {_html_escape(user_req[:200])}")

            output_text = ""
            channel_lbl = ""
            result_ok   = False

            # ── Pre-routing: comandi HA CLI diretti (ha .../hassio ...) ─────────
            # Intercetta PRIMA del run_natural per evitare che vengano mal-interpretati
            _ur_low = user_req.strip().lower()
            if _ur_low.startswith("ha ") or _ur_low.startswith("hassio "):
                _ha_res = await self._ha_terminal.ha_cli(user_req.strip())
                _ha_out = _ha_res.get("result", _ha_res.get("message", ""))
                _ha_ok  = _ha_res.get("success", False)
                kb_ha = {"inline_keyboard": [
                    [{"text": "💾 Salva output", "callback_data": "ssh_save_last"}],
                    [{"text": "🏠 Menu", "callback_data": "menu_back"},
                     {"text": "🗑",      "callback_data": "msg_delete"}],
                ]}
                if not hasattr(self, "_last_ssh_output"):
                    self._last_ssh_output = {}
                self._last_ssh_output[chat_id] = {
                    "text": re.sub(r"<[^>]+>", "", _ha_out)[:8000],
                    "cmd": user_req[:200], "channel": "Supervisor API"}
                _icon = "📡" if _ha_ok else "⚠️"
                await self._send_with_keyboard(
                    chat_id, f"{_icon} <b>Supervisor API</b>\n\n{_ha_out[:4000]}", kb_ha)
                return

            # ── Pre-routing: eliminazione file/cartella con conferma ────────
            # Intercetta: "rm path", "elimina path", "cancella path",
            # "rimuovi path", "delete path" — chiede conferma con bottone
            import re as _re_del
            _DELETE_RE = re.compile(
                r"^(?:rm|del|delete|elimina|cancella|rimuovi|togli|remove)"
                r"(?:\s+-[rf]+)?\s+(.+)$",
                re.IGNORECASE
            )
            # Linguaggio naturale: "elimina il file X", "cancella la cartella Y"
            _DELETE_NL_RE = re.compile(
                r"^(?:elimina|cancella|rimuovi|togli|remove|delete)"
                r"(?:\s+(?:il|la|lo|i|le|gli))?"
                r"(?:\s+(?:file|cartella|directory|folder|dir))?"
                r"\s+(.+)$",
                re.IGNORECASE
            )
            _del_match = _DELETE_RE.match(user_req.strip()) or _DELETE_NL_RE.match(user_req.strip())
            if _del_match:
                _del_path_raw = _del_match.group(1).strip()
                # Rimuovi prefissi residui tipo "il file X", "la cartella X"
                _del_path_raw = re.sub(
                    r"^(?:il|la|lo|i|le|gli)\s+(?:file|cartella|directory|folder|dir)?\s+",
                    "", _del_path_raw, flags=re.IGNORECASE
                ).strip()
                _del_path_raw = re.sub(
                    r"^(?:file|cartella|directory|folder|dir)\s+",
                    "", _del_path_raw, flags=re.IGNORECASE
                ).strip()
                # Normalizza path (aggiungi /config/ se manca)
                _del_path = _normalize_user_path(_del_path_raw)
                # Imposta pending e mostra bottoni conferma
                if not hasattr(self, "_tool_pending"):
                    self._tool_pending = {}
                self._tool_pending[chat_id] = {"action": "delete", "path": _del_path}
                _kb_del = {"inline_keyboard": [
                    [{"text": "✅ Sì, elimina", "callback_data": "tool_del_ok"},
                     {"text": "❌ Annulla",      "callback_data": "tool_del_no"}],
                ]}
                await self._send_with_keyboard(
                    chat_id,
                    f"⚠️ <b>Confermi eliminazione?</b>\n\n"
                    f"<code>{_del_path}</code>",
                    _kb_del
                )
                return

            # ── Pre-routing: operazioni file/container → bypass SSH ──────────
            # ── Comandi bash diretti → SSH host senza AI ─────────────────────
            # Riconosce comandi shell comuni e li esegue direttamente via SSH
            _DIRECT_BASH_RE = re.compile(
                r"^(ls|ll|la|cat|tail|head|grep|find|df|du|ps|top|htop|free|"
                r"pwd|whoami|id|uname|hostname|uptime|w|who|last|lsof|"
                r"netstat|ss|ip|ping|traceroute|curl|wget|systemctl|"
                r"journalctl|dmesg|mount|lsblk|fdisk|chmod|chown|"
                r"mkdir|rm|mv|cp|touch|echo|env|printenv|which|whereis|"
                r"apt|pip|python|python3|bash|sh|zsh)\b",
                re.IGNORECASE
            )
            if _DIRECT_BASH_RE.match(user_req.strip()):
                try:
                    # Normalizza il comando prima dell'esecuzione SSH
                    _raw_cmd = user_req.strip()
                    # Fix comandi interattivi → versione batch/non-interattiva
                    _CMD_REPLACEMENTS = {
                        "top":    "top -bn1 | head -30",
                        "htop":   "top -bn1 | head -30",
                    }
                    _cmd_parts = _raw_cmd.split()
                    _base_cmd  = _cmd_parts[0].lower() if _cmd_parts else ""
                    if _raw_cmd.lower() in _CMD_REPLACEMENTS:
                        _exec_cmd = _CMD_REPLACEMENTS[_raw_cmd.lower()]
                    else:
                        # Fix path noti senza slash iniziale:
                        # "ls config" → "ls /config"
                        # "cat etc/passwd" → "cat /etc/passwd"
                        _KNOWN_ROOTS = ("config", "etc", "home", "var", "tmp",
                                        "usr", "bin", "sbin", "proc", "sys",
                                        "dev", "run", "opt", "mnt", "media")
                        _args = _cmd_parts[1:]
                        _fixed_args = []
                        for _arg in _args:
                            # Se inizia con un root noto senza / → aggiungi /
                            _root = _arg.lstrip("-").split("/")[0]
                            if _root in _KNOWN_ROOTS and not _arg.startswith("/"):
                                _fixed_args.append("/" + _arg)
                            else:
                                _fixed_args.append(_arg)
                        _exec_cmd = _base_cmd + (" " + " ".join(_fixed_args) if _fixed_args else "")
                    _bash_res = await self._ha_terminal.ssh_exec(_exec_cmd, timeout=15)
                    _display_cmd = _exec_cmd  # mostra il comando effettivo eseguito
                    _bout = (_bash_res.get("stdout") or "").strip()
                    _berr = (_bash_res.get("stderr") or "").strip()
                    _brc  = _bash_res.get("returncode", 0)
                    if _bout or _berr:
                        _btext = f"<pre>{_html_escape((_bout or _berr)[:4000])}</pre>"
                    else:
                        _btext = "✅ Comando eseguito (nessun output)"
                    if not hasattr(self, "_last_ssh_output"):
                        self._last_ssh_output = {}
                    self._last_ssh_output[chat_id] = {
                        "text": (_bout or _berr)[:8000],
                        "cmd": _exec_cmd[:200], "channel": "SSH host"}
                    kb_bash = {"inline_keyboard": [
                        [{"text": "💾 Salva output", "callback_data": "ssh_save_last"}],
                        [{"text": "🏠 Menu", "callback_data": "menu_back"},
                         {"text": "🗑",      "callback_data": "msg_delete"}],
                    ]}
                    _icon = "✅" if _brc == 0 else "⚠️"
                    _cmd_note = (f" <i>(→ <code>{_html_escape(_exec_cmd)}</code>)</i>"
                                 if _exec_cmd != _raw_cmd else "")
                    await self._send_with_keyboard(
                        chat_id,
                        f"🖥️ <b>SSH — host</b>\n\n🖥️ HOST: <code>{_html_escape(_raw_cmd)}</code>{_cmd_note}\n"
                        f"\n{_icon} Comando OK\n{_btext}", kb_bash)
                    return
                except Exception as _be:
                    logger.debug("direct bash failed: %s — fallback run_natural", _be)

            # ── Intercetta richieste backup NL → Supervisor API ──────────────
            _BACKUP_RE = re.compile(
                r"(?:mostra(?:mi)?|elenca|lista|ultimi|dammi|vedi|show|list)"
                r".*?(?:backup|backups|copie\s+di\s+sicurezza)",
                re.IGNORECASE
            )
            if _BACKUP_RE.search(user_req) and not result_ok:
                # Estrai numero opzionale (es "ultimi 3 backup" → 3)
                _n_match = re.search(r"(\d+)", user_req)
                _n_bk = int(_n_match.group(1)) if _n_match else None
                try:
                    _bk_res = await self._ha_terminal.ha_cli("ha backups list")
                    if _bk_res.get("success"):
                        _bk_items = _bk_res.get("data", [])
                        if isinstance(_bk_items, list) and _bk_items:
                            # Ordina per data (campo "date") decrescente
                            try:
                                _bk_items = sorted(
                                    _bk_items,
                                    key=lambda x: x.get("date", ""),
                                    reverse=True
                                )
                            except Exception:
                                pass
                            if _n_bk:
                                _bk_items = _bk_items[:_n_bk]
                            _bk_lines = []
                            for _bk in _bk_items:
                                _bk_name = _bk.get("name", _bk.get("slug", "?"))
                                _bk_date = _bk.get("date", "")[:10]
                                _bk_type = "🔒" if _bk.get("protected") else "🔓"
                                _bk_size = _bk.get("size", 0)
                                try:
                                    # Il campo "size" da HA è già in MB
                                    _bk_sz_str = f"{float(_bk_size):.1f} MB" if _bk_size else ""
                                except Exception:
                                    _bk_sz_str = str(_bk_size)
                                _bk_lines.append(
                                    f"{_bk_type} <b>{_html_escape(_bk_name)}</b>"
                                    + (f"  <i>{_bk_date}</i>" if _bk_date else "")
                                    + (f"  <i>({_bk_sz_str})</i>" if _bk_sz_str else "")
                                )
                            _bk_suffix = f" — ultimi {_n_bk}" if _n_bk else ""
                            _bk_header = "\U0001f4be <b>Backup" + _bk_suffix + "</b>  (" + str(len(_bk_items)) + " trovati)\n"
                            output_text = _bk_header + "\n".join(_bk_lines)
                            channel_lbl = "📦 Supervisor"
                            result_ok = True
                        else:
                            output_text = "💾 Nessun backup trovato."
                            channel_lbl = "📦 Supervisor"
                            result_ok = True
                except Exception as _bk_ex:
                    logger.debug("backup intercept failed: %s", _bk_ex)

                        # ── Intercetta "mostra contenuto/lista/elenca X" → ls diretto ──
            _SHOW_RE = re.compile(
                r"^(?:mostra(?:mi)?|elenca|lista|vedi|visualizza|apri|show|list)"
                r"(?:\s+(?:il|la|lo|i|le|gli))?"
                r"(?:\s+(?:contenuto|lista))?"
                r"(?:\s+(?:della|del|di|in))?"
                r"(?:\s+(?:cartella|directory|dir))?"
                r"(?:\s+(?:della|del|di|in))?"
                r"(?:\s+(?:file\s+in|file))?"
                r"\s+(/[\w./\-]*|/|ago/[\w./\-]*|config(?:/[\w./\-]*)?|[\w./\-]+(?:/[\w./\-]*)*)"
                r"$",
                re.IGNORECASE
            )
            _show_m = _SHOW_RE.match(user_req.strip())
            if _show_m:
                _show_path = _show_m.group(1).strip()
                # Normalizza path:
                # "/" → "/"  (radice — lascia invariata)
                # "/config/..." → "/config/..."  (già corretto, lascia invariato)
                # "/ago/..."   → "/config/ago/..." (ago è dentro /config)
                # "config/..." → "/config/..."
                # "ago/..."    → "/config/ago/..."
                # altro        → "/config/..."
                if _show_path == "/":
                    pass  # root, lascia invariato
                elif _show_path.startswith("/config/") or _show_path == "/config":
                    pass  # già assoluto e corretto
                elif _show_path.startswith("/ago/") or _show_path == "/ago":
                    # /ago → /config/ago
                    _show_path = "/config" + _show_path
                elif _show_path.startswith("/"):
                    # altro path assoluto non /config → lascia invariato (es /etc, /var)
                    pass
                elif _show_path.startswith("config"):
                    _show_path = "/" + _show_path
                elif _show_path.startswith("ago/") or _show_path == "ago":
                    _show_path = "/config/" + _show_path
                else:
                    # Path relativo senza slash (es. "progetti", "risultati")
                    # Prova prima come sottocartella del default da regole,
                    # poi come sottocartella di /config/ago, poi /config
                    import os as _os
                    _base = _get_default_path_from_rules()
                    _candidate = _base.rstrip("/") + "/" + _show_path
                    if not _os.path.isdir(_candidate):
                        _candidate2 = "/config/ago/" + _show_path
                        if _os.path.isdir(_candidate2):
                            _candidate = _candidate2
                        else:
                            _candidate = "/config/" + _show_path
                    _show_path = _candidate
                # Usa sempre slash finale + -L per seguire symlink (es /config → /homeassistant)
                _show_path_ls = _show_path.rstrip("/") + "/"
                _show_cmd = f"ls -laL {_show_path_ls}"
                try:
                    _sr = await self._ha_terminal.ssh_exec(_show_cmd, timeout=10)
                    _sout = (_sr.get("stdout") or "").strip()
                    _serr = (_sr.get("stderr") or "").strip()
                    # Se -L fallisce (path non è dir), riprova senza slash
                    if _serr and ("Not a directory" in _serr or "No such file" in _serr):
                        _show_cmd = f"ls -laL {_show_path}"
                        _sr = await self._ha_terminal.ssh_exec(_show_cmd, timeout=10)
                        _sout = (_sr.get("stdout") or "").strip()
                        _serr = (_sr.get("stderr") or "").strip()
                    if _sout:
                        # Formatta output: separa dir e file con emoji
                        _lines_raw = _sout.splitlines()
                        _dirs = []
                        _files = []
                        for _ln in _lines_raw:
                            _parts = _ln.split()
                            if len(_parts) < 9:
                                continue
                            _perms = _parts[0]
                            _name_raw = " ".join(_parts[8:])
                            # Gestisci symlink: "nome -> destinazione" → prendi solo "nome"
                            if " -> " in _name_raw:
                                _name = _name_raw.split(" -> ")[0].strip()
                                _is_link = True
                            else:
                                _name = _name_raw
                                _is_link = False
                            if _name in (".", ".."):
                                continue
                            if _perms.startswith("d") or (_is_link and _perms.startswith("l")):
                                # Distingui dir da symlink a dir
                                _icon = "🔗" if _is_link else "📁"
                                _dirs.append(f"{_icon} <code>{_html_escape(_name)}/</code>")
                            else:
                                try:
                                    _sz_kb = int(_parts[4]) / 1024
                                    _sz_str = f"{_sz_kb:.1f} KB" if _sz_kb >= 1 else f"{_parts[4]} B"
                                except Exception:
                                    _sz_str = _parts[4]
                                _link_note = " 🔗" if _is_link else ""
                                _files.append(f"📄 <code>{_html_escape(_name)}</code>{_link_note}  <i>({_sz_str})</i>")
                        _tot = len(_dirs) + len(_files)
                        _formatted = _dirs + _files
                        if _formatted:
                            _header = f"📂 <b>{_html_escape(_show_path)}</b>  <i>({_tot} elementi)</i>"
                            output_text = _header + "\n" + "\n".join(_formatted)
                        else:
                            output_text = f"📂 <b>{_html_escape(_show_path)}</b>  <i>(vuota)</i>"
                        channel_lbl = "💻 Container"
                        result_ok = True
                    elif _serr and "Not a directory" in _serr:
                        # È un file → cat
                        _cat_r = await self._ha_terminal.ssh_exec(f"cat {_show_path}", timeout=10)
                        _cout = (_cat_r.get("stdout") or "").strip()
                        if _cout:
                            output_text = f"<pre>{_html_escape(_cout[:4000])}</pre>"
                            channel_lbl = "💻 Container"
                            result_ok = True
                except Exception:
                    pass  # fallback normale

            _FILE_KW = [
                "copia ", "sposta ", "rinomina ", "cerca file", "trova file",
                "elenca file", "lista file", "cerca.*\\.yaml", "cerca.*\\.json",
                "cerca.*\\.md", "estrai ", "comprimi ", "unzip ", "tar ",
                "info file", "dimensione file",
            ]
            _is_file_op = (
                any(kw in user_req.lower() for kw in [
                    "copia ", "sposta ", "rinomina ", "cerca file", "trova file",
                    "elenca file", "lista file", "estrai ", "comprimi ",
                    "unzip ", "info file",
                ]) or
                re.search(r"cerca.*\\.(yaml|json|md|txt|log)", user_req, re.IGNORECASE) is not None
            )
            _has_local_path = (
                not result_ok and (  # skip se _SHOW_RE ha già gestito
                re.search(r"^/", user_req.strip()) is not None or "ago/" in user_req or
                re.search(r"\\.(?:yaml|json|md|txt|log)\\b", user_req) is not None
                )
            )

            if _is_file_op or _has_local_path:
                try:
                    res_c = await _tools.tool_natural_shell(user_req, ai_cb=self.ai_cb)
                    if res_c.get("success") or res_c.get("stdout"):
                        _fm = " 🧠" if res_c.get("from_memory") else ""
                        _ag = " ✨" if res_c.get("ai_generated") else ""
                        channel_lbl = f"💻 Container{_fm}{_ag}"
                        output_text = res_c.get("message", "") + (
                            f"\\n\\n<pre>{_html_escape(res_c['stdout'][:3000])}</pre>"
                            if res_c.get("stdout") else "")
                        result_ok = True
                except Exception as _ce:
                    logger.debug("container_shell direct failed: %s", _ce)

            # ── SSH / Supervisor sull\\'host HA ─────────────────────────────────
            if not result_ok:
                try:
                    res_host = await self._ha_terminal.run_natural(user_req, ai_cb=self.ai_cb)
                    if res_host.get("success") or res_host.get("channel") not in (None, "error", ""):
                        ch = res_host.get("channel", "?")
                        channel_lbl = {
                            "host_info":                "📊 Supervisor — info sistema",
                            "addons_list":              "📦 Supervisor — addon",
                            "addon_stats":              "📊 Supervisor — stats",
                            "shell_command":            "💻 HA shell_command",
                            "ha_service":               "🔧 HA service",
                            "host_bash":                "🖥️ SSH — host",
                            "ssh":                      "🔐 SSH — host",
                            "container_shell":          "💻 Container",
                            "container_shell_fallback": "💻 Container (fallback)",
                            "ping":                     "🌐 Ping",
                            "portscan":                 "🔍 Port scan",
                            "error":                    "⚠️ Errore",
                        }.get(ch, ch)
                        output_text = res_host.get("result") or res_host.get("stdout") or "(nessun output)"
                        result_ok = True
                except Exception as _e_host:
                    logger.debug("SSH run_natural fallito: %s — provo container", _e_host)

            # ── Fallback: container shell ────────────────────────────────────
            if not result_ok:
                res_c = await _tools.tool_natural_shell(user_req, ai_cb=self.ai_cb)

                if res_c.get("package_missing"):
                    missing = res_c["package_missing"]
                    pkg_map = {
                        "ping": "iputils-ping", "ping6": "iputils-ping",
                        "traceroute": "traceroute", "nslookup": "bind-tools",
                        "dig": "bind-tools", "ip": "iproute2",
                        "ifconfig": "net-tools", "arp": "net-tools",
                        "nc": "netcat-openbsd", "git": "git", "tree": "tree",
                        "zip": "zip", "unzip": "unzip", "7z": "p7zip",
                        "jq": "jq", "rsync": "rsync",
                    }
                    pkg = pkg_map.get(missing, missing)
                    if not hasattr(self, "_pkg_install_pending"):
                        self._pkg_install_pending = {}
                    self._pkg_install_pending[chat_id] = {
                        "package": pkg, "original_request": user_req, "missing_cmd": missing,
                    }
                    await self._send_with_keyboard(chat_id,
                        f"⚠️ <b>Manca il comando</b> <code>{missing}</code>\\n"
                        f"📦 Pacchetto: <code>{pkg}</code>\\n<i>Installo e riprovo?</i>",
                        {"inline_keyboard": [
                            [{"text": f"📦 Installa {pkg}", "callback_data": "pkg_install_yes"},
                             {"text": "❌ No",              "callback_data": "pkg_install_no"}],
                        ]})
                    return

                _fm = " 🧠" if res_c.get("from_memory") else ""
                _ag = " ✨" if res_c.get("ai_generated") else ""
                channel_lbl = f"💻 Container{_fm}{_ag}"
                output_text = res_c.get("message", "") + (
                    f"\\n\\n<pre>{_html_escape(res_c['stdout'][:2500])}</pre>"
                    if res_c.get("stdout") else "") + (
                    f"\\n⚠️ <pre>{_html_escape(res_c['stderr'][:500])}</pre>"
                    if res_c.get("stderr") and not res_c.get("success") else "")
                result_ok = True

            # ── Assembla risposta ────────────────────────────────────────────
            body = f"📡 <b>{channel_lbl}</b>\\n\\n{output_text}"

            if save_path:
                _clean = re.sub(r"<[^>]+>", "", output_text)
                _md_content = (
                    f"# /ssh {user_req}\\n\\n"
                    f"_Eseguito: {datetime.now().strftime('%Y-%m-%d %H:%M')} — {channel_lbl}_\\n\\n"
                    f"```\\n{_clean[:8000]}\\n```\\n"
                )
                wr = _tools.tool_scrittura(save_path, _md_content)
                _rp = "/config/" + wr.get("path", save_path).lstrip("/")
                body += f"\\n\\n💾 <b>Salvato in:</b> <code>{_rp}</code>"
                kb = {"inline_keyboard": [
                    [{"text": "📂 Leggi file", "callback_data": f"menu_cmd:/leggi {save_path}"}],
                    [{"text": "🏠 Menu", "callback_data": "menu_back"}],
                ]}
            else:
                if not hasattr(self, "_last_ssh_output"):
                    self._last_ssh_output = {}
                _clean2 = re.sub(r"<[^>]+>", "", output_text)
                self._last_ssh_output[chat_id] = {
                    "text": _clean2[:8000], "cmd": user_req[:200], "channel": channel_lbl}
                kb = {"inline_keyboard": [
                    [{"text": "💾 Salva output", "callback_data": "ssh_save_last"}],
                    [{"text": "🏠 Menu", "callback_data": "menu_back"},
                     {"text": "🗑",      "callback_data": "msg_delete"}],
                ]}

            await self._send_with_keyboard(chat_id, body[:4000], kb)
            return


        if quick == "__HA_ADDONS_LIST__":
            await self._typing(chat_id)
            try:
                res = await self._ha_terminal.addons_list()
                if not res.get("success"):
                    await self._send(chat_id, f"⚠️ {res.get('message','?')}")
                    return
                body = HATerminal.format_addons(res["data"])
                kb = {"inline_keyboard": [
                    [{"text": "🖥️ Sistema", "callback_data": "menu_cmd:/ha_sistema"}],
                    [{"text": "🏠 Menu", "callback_data": "menu_back"},
                     {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, body, kb)
            except Exception as e:
                logger.exception("ha_addons")
                await self._send(chat_id, f"⚠️ Errore: {str(e)[:200]}")
            return

        # ── Lista comandi shell appresi ─────────────────────────────────
        if quick == "__LEARNED_LIST__":
            learned = _tools.list_learned_commands(limit=30)
            if not learned:
                await self._send(chat_id,
                    "📋 <i>Nessun comando memorizzato.</i>\n\n"
                    "<i>Usa <code>/ssh</code> con un'intent per memorizzare comandi.</i>")
                return
            body = f"📋 <b>Comandi memorizzati ({len(learned)})</b>\n\n"
            for item in learned:
                body += (f"  • <i>{_html_escape(item['intent'][:60])}</i>\n"
                         f"    <code>{_html_escape(item['command'][:120])}</code>\n\n")
            kb = {"inline_keyboard": [
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return

        # ── Task agent help ─────────────────────────────────────────────
        if quick == "__TASK_AGENT_HELP__":
            body = (
                "🤖 <b>Programma Task Agente</b>\n\n"
                "Esegue automaticamente task agentici a un orario specifico.\n\n"
                "<b>Uso:</b>\n"
                "<code>/task_agent &lt;quando&gt;: &lt;task agente&gt;</code>\n\n"
                "<b>Esempi:</b>\n\n"
                "📅 <code>/task_agent ogni giorno alle 19: cerca classifica Serie A salva in ago/classifica.md</code>\n\n"
                "📅 <code>/task_agent domani alle 8: scarica github.com/user/repo in ago/progetto e crea riassunto</code>\n\n"
                "📅 <code>/task_agent ogni lunedì alle 9: elenca sensori energia e scrivi report in note/energia.md</code>\n\n"
                "<i>Il task viene eseguito come agente autonomo (max 8 step).</i>"
            )
            kb = {"inline_keyboard": [
                [{"text": "🤖 Test agent ora", "callback_data": "menu_cmd:/agent"}],
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return

        # ── Task agent create ───────────────────────────────────────────
        if quick == "__TASK_AGENT_CREATE__":
            raw = text.strip()
            for prefix in ("/task_agent ", "task agente "):
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            # Splitta quando:task — gestisce HH:MM nell'orario
            # Strategia: dopo aver "consumato" un pattern HH:MM, il primo ":" rimasto è il separatore
            import re as _re_split
            # Maschera HH:MM con placeholder, poi splitta sul ":" rimasto
            _masked = _re_split.sub(r"(\d{1,2}):(\d{2})", lambda m: m.group(1) + "\x00" + m.group(2), raw)
            if ":" not in _masked:
                await self._send(chat_id,
                    "⚠️ Formato: <code>/task_agent &lt;quando&gt;: &lt;task&gt;</code>\n\n"
                    "Es: <code>/task_agent alle ore 12:35: scarica https://github.com/ago19800/HomeMind ago/progetti</code>\n"
                    "Es: <code>/task_agent ogni giorno alle 19: cerca classifica salva in ago/calcio.md</code>")
                return
            _w_masked, _t_masked = _masked.split(":", 1)
            # Ripristina HH:MM originale
            when_part = _w_masked.replace("\x00", ":").strip()
            task_part = _t_masked.replace("\x00", ":").strip()
            if not when_part or not task_part:
                await self._send(chat_id, "⚠️ Quando e task non possono essere vuoti.")
                return

            # Determina se ricorrente o singolo
            when_lower = when_part.lower()
            is_recurring = any(w in when_lower for w in
                ("ogni", "tutti i", "every", "lunedì", "martedì", "mercoledì",
                 "giovedì", "venerdì", "sabato", "domenica", "weekend"))

            agent_command = f"__AGENT__:{task_part}"
            label = f"🤖 Agent: {task_part[:40]}"

            try:
                if is_recurring and self._recurring_task_scheduler:
                    # Parsa quando per ricorrente — semplificato
                    import re as _re
                    h_match = _re.search(r"alle\s+(\d{1,2})(?::(\d{2}))?", when_lower)
                    if not h_match:
                        await self._send(chat_id,
                            "⚠️ Specifica orario, es. 'ogni giorno alle 19'")
                        return
                    hour = int(h_match.group(1))
                    minute = int(h_match.group(2)) if h_match.group(2) else 0
                    # Day of week
                    days_map = {"lunedì":0, "martedì":1, "mercoledì":2,
                                "giovedì":3, "venerdì":4, "sabato":5, "domenica":6}
                    dow = None
                    for d, v in days_map.items():
                        if d in when_lower:
                            dow = v
                            break
                    self._recurring_task_scheduler.add_task(
                        label=label, command=agent_command,
                        hour=hour, minute=minute, day_of_week=dow,
                        chat_id=chat_id
                    )
                    await self._send(chat_id,
                        f"✅ <b>Task agente ricorrente programmato</b>\n\n"
                        f"⏰ {self._recurring_task_scheduler._dow_label(dow)} alle {hour:02d}:{minute:02d}\n"
                        f"🤖 Task: {_html_escape(task_part[:200])}")
                elif self._task_scheduler:
                    # Task singolo — usa parse data esistente
                    res = self._task_scheduler.add_task_from_natural(
                        when=when_part, command=agent_command,
                        label=label, chat_id=chat_id
                    )
                    if res.get("success"):
                        await self._send(chat_id,
                            f"✅ <b>Task agente programmato</b>\n\n"
                            f"⏰ {res.get('when_str', when_part)}\n"
                            f"🤖 Task: {_html_escape(task_part[:200])}")
                    else:
                        await self._send(chat_id,
                            f"⚠️ {res.get('message', 'Errore programmazione')}")
                else:
                    await self._send(chat_id, "⚠️ Task scheduler non disponibile.")
            except Exception as e:
                logger.exception("task_agent_create")
                await self._send(chat_id, f"⚠️ Errore: {str(e)[:200]}")
            return

        # ── Task shell create ───────────────────────────────────────────
        if quick == "__TASK_SHELL_CREATE__":
            raw = text.strip()
            for prefix in ("/task_shell ", "task shell "):
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            _masked2 = _re_split.sub(r"(\d{1,2}):(\d{2})", lambda m: m.group(1) + "\x00" + m.group(2), raw)
            if ":" not in _masked2:
                await self._send(chat_id,
                    "⚠️ Formato: <code>/task_shell &lt;quando&gt;: &lt;comando&gt;</code>")
                return
            _w2, _c2 = _masked2.split(":", 1)
            when_part = _w2.replace("\x00", ":").strip()
            cmd_part  = _c2.replace("\x00", ":").strip()
            # Verifica sicurezza pre-programmazione
            safe, reason = _tools._is_command_safe(cmd_part)
            if not safe:
                await self._send(chat_id,
                    f"⚠️ Comando non sicuro: {reason}\n\n"
                    f"Vedi <code>/comandi_appresi</code> per esempi.")
                return
            shell_command = f"__SHELL__:{cmd_part}"
            label = f"💻 Shell: {cmd_part[:40]}"
            try:
                when_lower = when_part.lower()
                is_recurring = any(w in when_lower for w in
                    ("ogni", "tutti i", "every"))
                if is_recurring and self._recurring_task_scheduler:
                    import re as _re
                    h_match = _re.search(r"alle\s+(\d{1,2})(?::(\d{2}))?", when_lower)
                    if not h_match:
                        await self._send(chat_id, "⚠️ Specifica orario")
                        return
                    hour = int(h_match.group(1))
                    minute = int(h_match.group(2)) if h_match.group(2) else 0
                    self._recurring_task_scheduler.add_task(
                        label=label, command=shell_command,
                        hour=hour, minute=minute, day_of_week=None,
                        chat_id=chat_id
                    )
                    await self._send(chat_id,
                        f"✅ <b>Task shell ricorrente</b>\n⏰ alle {hour:02d}:{minute:02d}\n"
                        f"💻 <code>{_html_escape(cmd_part[:200])}</code>")
                elif self._task_scheduler:
                    res = self._task_scheduler.add_task_from_natural(
                        when=when_part, command=shell_command,
                        label=label, chat_id=chat_id
                    )
                    if res.get("success"):
                        await self._send(chat_id,
                            f"✅ <b>Task shell programmato</b>\n"
                            f"⏰ {res.get('when_str', when_part)}\n"
                            f"💻 <code>{_html_escape(cmd_part[:200])}</code>")
                    else:
                        await self._send(chat_id, f"⚠️ {res.get('message', 'errore')}")
            except Exception as e:
                logger.exception("task_shell_create")
                await self._send(chat_id, f"⚠️ Errore: {str(e)[:200]}")
            return

        # ── Agent: esecuzione ───────────────────────────────────────────
        if quick == "__AGENT_RUN__":
            raw = text.strip()
            for prefix in ("/agent ", "agent ", "/fai ", "fai ", "/agente "):
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            task = raw.strip()
            if not task:
                await self._send(chat_id, "⚠️ Uso: <code>/fai &lt;task&gt;</code>")
                return

            # Avvio
            await self._send(chat_id,
                f"🤖 <b>Agente avviato</b>\n\n"
                f"<i>Task:</i> {_html_escape(task[:500])}\n\n"
                f"<i>Procedo con i tool in autonomia. Ti avviso ad ogni step.</i>")

            # Progress callback: mostra ogni step
            async def _progress(step, tool, args, thought, result):
                if result is None:
                    # Inizio step (prima dell'esecuzione)
                    short_args = json.dumps(args, ensure_ascii=False)[:200]
                    msg = (f"<b>🔧 Step {step}</b> — <code>{tool}</code>\n"
                           f"<i>{_html_escape(thought[:300])}</i>\n"
                           f"<code>{_html_escape(short_args)}</code>")
                    await self._send(chat_id, msg)
                else:
                    # Risultato (post esecuzione)
                    # Se il tool richiede conferma → mostra bottoni e attendi
                    if result.get("needs_confirm") and result.get("confirm_action"):
                        conf_msg = result.get("result", "⚠️ Conferma richiesta")
                        confirmed = await _confirm(conf_msg)
                        if confirmed:
                            # Esegui l'azione confermata
                            _ca = result["confirm_action"]
                            _rest = self._rest_client
                            if _rest:
                                try:
                                    await _rest.call_service(
                                        _ca["domain"], _ca["service"], _ca.get("data", {})
                                    )
                                    await self._send(chat_id,
                                        f"✅ Eseguito: <code>{_ca['domain']}.{_ca['service']}</code>")
                                except Exception as _ce:
                                    await self._send(chat_id, f"❌ Errore: {_ce}")
                        else:
                            await self._send(chat_id, "❌ Operazione annullata.")
                        return
                    icon = "✅" if result.get("success") else "⚠️"
                    res_txt = str(result.get("result", ""))[:1500]
                    if len(res_txt) > 100:
                        # Risultato lungo → invia come blocco code
                        await self._send(chat_id,
                            f"{icon} <i>step {step} — output:</i>\n"
                            f"<pre>{_html_escape(res_txt)}</pre>")

            # Confirmation callback (per delete e simili)
            async def _confirm(question: str) -> bool:
                """Mostra bottoni Sì/No e attende risposta utente."""
                import asyncio as _aio
                fut = _aio.get_event_loop().create_future()
                self._agent_confirm[chat_id] = fut
                kb = {"inline_keyboard": [
                    [{"text": "✅ Sì",     "callback_data": "agent_yes"},
                     {"text": "❌ No",     "callback_data": "agent_no"}],
                ]}
                await self._send_with_keyboard(chat_id, question, kb)
                try:
                    return await _aio.wait_for(fut, timeout=120)
                except _aio.TimeoutError:
                    return False
                finally:
                    self._agent_confirm.pop(chat_id, None)

            # Context per agent
            ctx = {
                "ai_cb":           self.ai_cb,
                "state_cache_cb":  self.state_cache_cb,
                "confirmation_cb": _confirm,
                "ha_terminal":     self._ha_terminal,
                "rest_client":     self._rest_client,
            }

            try:
                result = await _agent.run_agent(
                    task, ctx,
                    progress_cb=_progress,
                    max_steps=10
                )
                # Messaggio finale
                if result["success"]:
                    final = (f"✅ <b>Task completato</b>\n\n"
                             f"{_html_escape(str(result['final_message'])[:2000])}\n\n"
                             f"<i>Step eseguiti: {len(result['steps'])}</i>")
                else:
                    final = (f"⚠️ <b>Task non completato</b>\n\n"
                             f"{_html_escape(str(result['final_message'])[:2000])}\n\n"
                             f"<i>Motivo: {result.get('stopped_reason','?')}</i>\n"
                             f"<i>Step: {len(result['steps'])}</i>")
                kb = {"inline_keyboard": [
                    [{"text": "🤖 Altro task", "callback_data": "menu_cmd:/agent"}],
                    [{"text": "🏠 Menu", "callback_data": "menu_back"},
                     {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, final, kb)
            except Exception as e:
                logger.exception("agent run")
                await self._send(chat_id, f"⚠️ Errore agente: {str(e)[:300]}")
            return

        # ── Tool: help ───────────────────────────────────────────────────
        if quick == "__TOOL_HELP__":
            body = (
                "🧰 <b>Strumenti diretti</b>\n\n"
                "Comandi disponibili:\n\n"
                "📝 <code>/scrivi &lt;path&gt; &lt;contenuto&gt;</code>\n"
                "   Scrive un file. Es: <code>/scrivi note/test.txt Ciao mondo</code>\n\n"
                "📖 <code>/leggi &lt;path&gt;</code>\n"
                "   Legge un file. Es: <code>/leggi note/test.txt</code>\n\n"
                "📁 <code>/ls [path]</code>\n"
                "   Elenca contenuto cartella. Es: <code>/ls custom_components</code>\n\n"
                "📂 <code>/mkdir &lt;path&gt;</code>\n"
                "   Crea cartella. Es: <code>/mkdir prova/ago</code>\n\n"
                "🗑️ <code>/elimina &lt;path&gt;</code>\n"
                "   Elimina file/cartella (con check protezione)\n\n"
                "⬇️ <code>/scarica &lt;url&gt; &lt;dest&gt;</code>\n"
                "   Scarica un URL. Es: <code>/scarica https://... prova/file.zip</code>\n\n"
                "📦 <code>/clona &lt;repo&gt; &lt;dest&gt;</code>\n"
                "   Clona repo Git. Es: <code>/clona owner/repo prova/progetto</code>\n\n"
                "🔍 <code>/cerca &lt;query&gt; [→ &lt;path&gt;]</code>\n"
                "   Ricerca web. Con <code>→ path</code> salva risultato in file.\n"
                "   Es: <code>/cerca node-red template HA → ricerche/nodered.md</code>\n\n"
                "<i>⚠️ Tutti i path sono relativi a /config. File protetti "
                "(configuration.yaml, secrets.yaml, .storage) non si possono "
                "modificare/eliminare con questi tool — usa /modifica per quelli.</i>"
            )
            kb = {"inline_keyboard": [
                [{"text": "📁 Esplora /config",   "callback_data": "menu_cmd:/ls"}],
                [{"text": "📄 Leggi config",      "callback_data": "menu_cmd:/leggi_config"},
                 {"text": "🔗 GitHub",            "callback_data": "menu_cmd:/github"}],
                [{"text": "🏠 Menu",              "callback_data": "menu_back"},
                 {"text": "🗑 Cancella",          "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return

        # ── Tool: scrivi file ───────────────────────────────────────────
        if quick == "__TOOL_WRITE__":
            # /scrivi <path> <contenuto multi-riga>
            raw = text.strip()
            for prefix in ("/scrivi ", "scrivi "):
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            # Split path + contenuto (primo spazio o newline)
            sep_idx = -1
            for c in (" ", "\n"):
                idx = raw.find(c)
                if idx > 0 and (sep_idx == -1 or idx < sep_idx):
                    sep_idx = idx
            if sep_idx <= 0:
                await self._send(chat_id,
                    "⚠️ Uso: <code>/scrivi &lt;path&gt; &lt;contenuto&gt;</code>")
                return
            path_arg = _normalize_user_path(raw[:sep_idx])
            content_arg = raw[sep_idx+1:].strip()
            if not content_arg:
                await self._send(chat_id, "⚠️ Contenuto vuoto.")
                return
            result = _tools.tool_scrittura(path_arg, content_arg)
            kb = {"inline_keyboard": [
                [{"text": "📖 Leggi", "callback_data": f"menu_cmd:/leggi {path_arg}"}],
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]} if result["success"] else {"inline_keyboard": [
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, result["message"], kb)
            return

        # ── Tool: leggi file ────────────────────────────────────────────
        if quick == "__TOOL_READ__":
            raw = text.strip()
            for prefix in ("/leggi ", "leggi "):
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            path_arg = _normalize_user_path(raw.strip())
            if not path_arg:
                await self._send(chat_id, "⚠️ Uso: <code>/leggi &lt;path&gt;</code>")
                return
            result = _tools.tool_lettura(path_arg)
            if not result["success"]:
                await self._send(chat_id, result["message"])
                return
            header = f"📖 <b>{result['path']}</b>  <i>({result['size']} bytes)</i>"
            await self._send(chat_id, header)
            await _send_long_file(self, chat_id, result['path'], result["content"])
            kb = {"inline_keyboard": [
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id,
                "<i>Fine file</i>" + ("\n⚠️ <i>Contenuto troncato</i>" if result.get("truncated") else ""),
                kb)
            return

        # ── Tool: ls ────────────────────────────────────────────────────
        if quick == "__TOOL_LS__":
            raw = text.strip()
            for prefix in ("/ls ", "/ls", "ls"):
                if raw.lower() == prefix.strip() or raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            path_arg = _normalize_user_path(raw.strip()) or "."
            result = _tools.tool_ls(path_arg)
            body = _tools.format_ls_for_display(result)
            kb = {"inline_keyboard": [
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return

        # ── Tool: mkdir ─────────────────────────────────────────────────
        if quick == "__TOOL_MKDIR__":
            raw = text.strip()
            for prefix in ("/mkdir ", "mkdir "):
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            path_arg = _normalize_user_path(raw.strip())
            if not path_arg:
                await self._send(chat_id, "⚠️ Uso: <code>/mkdir &lt;path&gt;</code>")
                return
            result = _tools.tool_mkdir(path_arg)
            kb = {"inline_keyboard": [
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, result["message"], kb)
            return

        # ── Tool: delete ─────────────────────────────────────────────────
        if quick == "__TOOL_DELETE__":
            raw = text.strip()
            for prefix in ("/elimina ", "elimina file ", "/rm "):
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            path_arg = _normalize_user_path(raw.strip())
            if not path_arg:
                await self._send(chat_id, "⚠️ Uso: <code>/elimina &lt;path&gt;</code>")
                return
            # Conferma esplicita per delete
            self._tool_pending = getattr(self, "_tool_pending", {})
            self._tool_pending[chat_id] = {"action": "delete", "path": path_arg}
            kb = {"inline_keyboard": [
                [{"text": "✅ Sì, elimina", "callback_data": "tool_del_ok"},
                 {"text": "❌ Annulla",      "callback_data": "tool_del_no"}],
            ]}
            await self._send_with_keyboard(chat_id,
                f"⚠️ <b>Confermi eliminazione?</b>\n<code>{path_arg}</code>", kb)
            return

        # ── Tool: download ──────────────────────────────────────────────
        if quick == "__TOOL_DOWNLOAD__":
            raw = text.strip()
            for prefix in ("/scarica ", "scarica ", "/download "):
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            parts = raw.split(maxsplit=1)
            if len(parts) < 1 or not parts[0].strip():
                await self._send(chat_id, "⚠️ Uso: <code>/scarica &lt;url&gt; [dest]</code>")
                return
            url_arg = parts[0].strip()
            if len(parts) >= 2 and parts[1].strip():
                dest_arg = _normalize_user_path(parts[1].strip())
            else:
                dest_arg = _get_default_path_from_rules()
                await self._send(chat_id,
                    f"📂 Percorso non specificato — uso default: <code>{dest_arg}</code>")
            # Rilevamento GitHub → usa clone invece di download
            if "github.com" in url_arg and not url_arg.endswith((".zip", ".tar.gz", ".tgz")):
                await self._send(chat_id, f"⏳ GitHub rilevato — uso git clone su {url_arg[:80]}...")
                result = await _tools.tool_github_clone(url_arg, dest_arg)
            else:
                await self._send(chat_id, f"⏳ Scaricando da {url_arg[:80]}...")
                result = await _tools.tool_download(url_arg, dest_arg)
            kb = {"inline_keyboard": [
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, result["message"], kb)
            return

        # ── Tool: clona ─────────────────────────────────────────────────
        if quick == "__TOOL_CLONE__":
            raw = text.strip()
            for prefix in ("/clona ", "clona ", "/clone "):
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break
            parts = raw.split(maxsplit=1)
            if len(parts) < 1 or not parts[0].strip():
                await self._send(chat_id, "⚠️ Uso: <code>/clona &lt;repo&gt; [dest]</code>")
                return
            repo_arg = parts[0].strip()
            if len(parts) >= 2 and parts[1].strip():
                dest_arg = _normalize_user_path(parts[1].strip())
            else:
                # Nessun dest specificato → usa default da regole.md
                dest_arg = _get_default_path_from_rules()
                await self._send(chat_id,
                    f"📂 Percorso non specificato — uso default: <code>{dest_arg}</code>")
            await self._send(chat_id, f"⏳ Clonando {repo_arg}...")
            result = await _tools.tool_github_clone(repo_arg, dest_arg)
            kb = {"inline_keyboard": [
                [{"text": "📁 Esplora", "callback_data": f"menu_cmd:/ls {dest_arg}"}],
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, result["message"], kb)
            return

        # ── Tool: search web (con scrittura opzionale in file) ──────────
        if quick == "__TOOL_SEARCH__":
            raw = text.strip()
            for prefix in ("/cerca ", "cerca web ", "/search ", "cerca "):
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):]
                    break

            # Parser intelligente: estrai output_path dalla query
            # Supporta: "→ path", "-> path", "salva in path", "scrivi in path",
            #          "salvami in path", "su path", "in path"
            output_path = None
            query = raw.strip()

            # Pattern di estrazione (in ordine di priorità)
            # Liberali: cerchiamo qualsiasi cosa che assomiglia a un path con estensione
            extract_patterns = [
                # Esplicito con frecce
                r'\s*[→]\s*(\S+)\s*$',
                r'\s*->\s*(\S+)\s*$',
                # Verbi di salvataggio + preposizione + path
                r'\s+(?:e\s+)?(?:salva(?:mi|lo|re)?|scrivi(?:lo|mi|re)?|metti|aggiungi)\s+(?:in|su|nel(?:la)?|a|verso|al)?\s*(\S+)\s*$',
                # Preposizione + path con estensione (anche embedded markdown link)
                r'\s+(?:in|nel(?:la)?|su|a|verso|al)\s+(\S*[\w\-./\[\]()]+\.(?:md|txt|yaml|yml|json|html|csv))\s*$',
                # Solo path con estensione alla fine
                r'\s+(\S*[\w\-./\[\]()]+\.(?:md|txt|yaml|yml|json|html|csv))\s*$',
            ]
            for pat in extract_patterns:
                m = re.search(pat, query, re.IGNORECASE)
                if m:
                    output_path = m.group(1).strip().strip('"\'')
                    query = query[:m.start()].strip()
                    break

            # Pulizia path: gestisci markdown link auto-generati da Telegram
            # es. /ago/[classifica.md](http://classifica.md) → /ago/classifica.md
            if output_path:
                output_path = _normalize_user_path(output_path)
                if not output_path:
                    output_path = None

            if not query:
                await self._send(chat_id, "⚠️ Uso: <code>/cerca &lt;query&gt; [salva in &lt;path&gt;]</code>")
                return

            # Detection: "ricetta", "guida", "tutorial", "spiegazione" → AI genera contenuto
            # invece di mostrare solo link
            content_intents = [
                "ricetta", "ricette", "spiega", "spiegami", "spiegazione", "tutorial",
                "guida", "come si fa", "come fare", "come faccio",
                "cos\'è", "cosa è", "cos\'", "definizione", "significato",
                "esempio", "esempi", "classifica", "classifiche", "risultati",
                "notizie", "novità", "ultime", "info su", "informazioni",
                "biografia", "storia di", "elenco", "lista",
            ]
            # Per default consideriamo content_intent se l\'utente vuole salvare un file
            # (cioè se output_path è specificato). L\'AI darà comunque contenuto strutturato.
            is_content_intent = (output_path is not None) or any(
                it in query.lower() for it in content_intents
            )

            await self._send(chat_id, f"🔍 <i>Cerco:</i> {_html_escape(query)}" +
                              (f"\n📝 <i>Salverò in:</i> <code>{output_path}</code>" if output_path else ""))

            # 1. Web search per avere fonti
            result = await _tools.tool_search_web(query, max_results=8)
            web_data = ""
            if result.get("success") and result.get("results"):
                # Passo 1: snippet di tutti
                for i, r in enumerate(result["results"][:8], 1):
                    web_data += (f"\n## Fonte {i}: {r.get('title','')}\n"
                                 f"URL: {r.get('url','')}\n"
                                 f"{r.get('snippet','')}\n")
                # Passo 2: scarica contenuto reale dei primi 2 (per dare freschezza)
                # Solo se è content_intent, perché serve solo per ricette/classifiche/etc
                if is_content_intent:
                    fetched_data = ""
                    fetched_count = 0
                    for r in result["results"][:4]:
                        if fetched_count >= 2:
                            break
                        url = r.get("url", "")
                        if not url:
                            continue
                        page = await _tools.tool_fetch_page(url, max_chars=3500)
                        if page.get("success") and page.get("text"):
                            fetched_data += (f"\n\n=== Contenuto da {url} ===\n"
                                             f"{page['text'][:3500]}\n")
                            fetched_count += 1
                    if fetched_data:
                        web_data += f"\n\n## Contenuto pagine (estratto):{fetched_data}"

            # 2. AI: genera contenuto vero (ricetta/guida/spiegazione completa)
            #    usando le fonti trovate come riferimento
            final_content = ""
            if self.ai_cb:
                await self._typing(chat_id)
                if is_content_intent:
                    # Genera CONTENUTO completo (ricetta, guida, spiegazione)
                    sys = (
                        "Sei HomeMind, assistente AI esperto e preciso.\n"
                        "REGOLE FONDAMENTALI:\n"
                        "1. Rispondi SEMPRE in italiano.\n"
                        "2. Usa SEMPRE formato Markdown strutturato (## titoli, tabelle, elenchi puntati).\n"
                        "3. Dai CONTENUTO REALE non link: classifiche → tabella completa; "
                        "ricette → ingredienti+procedimento; guide → passi numerati.\n"
                        "4. Classifiche sportive: tabella Markdown con colonne "
                        "Pos | Squadra | G | V | P | S | GF | GS | Diff | Pt\n"
                        "5. Usa i dati delle fonti web per essere accurato e aggiornato.\n"
                        "6. Niente introduzioni inutili. Vai subito al contenuto."
                    )
                    usr = (
                        f"## Richiesta\n{query}\n\n"
                        f"## Fonti web{web_data or chr(10)+'(nessuna, usa conoscenza aggiornata)'}\n\n"
                        "Genera il contenuto completo e ben formattato in Markdown."
                    )
                else:
                    # Modalità riassunto fonti
                    sys = (
                        "Sei HomeMind. Riassumi la ricerca in italiano in Markdown strutturato "
                        "(titolo, sezioni, bullet, link). Niente fronzoli. Rispondi in italiano."
                    )
                    usr = f"Query: {query}\n\nRisultati:\n{web_data}"
                try:
                    ai_text = await self.ai_cb(sys, usr, None)
                    if ai_text:
                        final_content = ai_text
                except Exception as e:
                    logger.warning("AI search formatting failed: %s", e)

            # Fallback se AI non disponibile o errore
            if not final_content:
                body_parts = [f"# {query}\n"]
                for r in result.get("results", [])[:8]:
                    body_parts.append(f"\n## {r.get('title','')}")
                    body_parts.append(f"{r.get('snippet','')}")
                    body_parts.append(f"\n🔗 {r.get('url','')}")
                final_content = "\n".join(body_parts)

            # 3. Mostra anteprima (truncata se necessario) all'utente
            preview = final_content
            if len(preview) > 2500:
                preview = preview[:2500] + "\n\n<i>... (anteprima troncata, contenuto completo nel file)</i>"

            # 4. Se richiesto, scrivi nel file (con append automatico se esiste)
            if output_path:
                # Uso _tools._safe_path per coerenza con tool_scrittura/tool_append
                # (entrambi normalizzano allo stesso modo dentro CONFIG_DIR)
                try:
                    target_check = _tools._safe_path(output_path)
                    file_existed = target_check.exists()
                    old_size = target_check.stat().st_size if file_existed else 0
                except Exception as _e_path:
                    logger.warning("safe_path fallito, uso fallback: %s", _e_path)
                    from pathlib import Path as _P
                    target_check = _P("/config") / output_path.lstrip("/")
                    file_existed = target_check.exists()
                    old_size = target_check.stat().st_size if file_existed else 0

                logger.info("Search output: path=%s resolved=%s exists=%s size=%d",
                            output_path, target_check, file_existed, old_size)

                # Rileva se l\'utente ha chiesto esplicitamente di sovrascrivere
                _overwrite_kws = ("sovrascrivi", "sovrascri", "sovrascrivi tutto",
                                  "cancella e riscrivi", "resetta", "ricrea",
                                  "overwrite", "rimpiazza", "rifai il file")
                _force_overwrite = any(kw in raw.lower() for kw in _overwrite_kws)

                if file_existed and not _force_overwrite:
                    # APPEND: aggiunge sezione sotto con header
                    from datetime import datetime as _dt
                    ts = _dt.now().strftime("%d/%m/%Y %H:%M")
                    section_header = f"\n\n---\n\n## 🔍 {query}  \n<sub>{ts}</sub>\n\n"
                    write_result = _tools.tool_append(
                        output_path,
                        section_header + final_content,
                        separator=""
                    )
                    new_size = write_result.get("size", 0)
                    _resolved2 = "/config/" + write_result.get("path", output_path).lstrip("/")
                    action_lbl = (f"➕ <b>Aggiunto sotto a:</b> <code>{_resolved2}</code> "
                                  f"({old_size} → {new_size} bytes)")
                elif file_existed and _force_overwrite:
                    # SOVRASCRITTURA esplicita
                    write_result = _tools.tool_scrittura(output_path, final_content, overwrite=True)
                    new_size = write_result.get("size", 0)
                    _raw_path3 = write_result.get("path", output_path)
                    _raw_path3 = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", str(_raw_path3))
                    _resolved3 = "/config/" + _raw_path3.lstrip("/")
                    action_lbl = f"♻️ <b>File sovrascritto: <code>{_resolved3}</code></b> ({new_size} bytes)"
                else:
                    # CREA NUOVO
                    write_result = _tools.tool_scrittura(output_path, final_content)
                    new_size = write_result.get("size", 0)
                    _raw_path = write_result.get("path", output_path)
                    # Pulisci markdown link tipo [file.md](http://file.md) → file.md
                    _raw_path = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", str(_raw_path))
                    _resolved = "/config/" + _raw_path.lstrip("/")
                    action_lbl = f"✅ <b>File creato:</b> <code>{_resolved}</code> ({new_size} bytes)"
                # Mostra preview + conferma scrittura
                if len(preview) > 100:
                    await self._send(chat_id, preview[:3500])
                msg_final = (f"\n{action_lbl}\n"
                             f"💾 {write_result['message']}")
                # Usa il path reale restituito dal tool — pulito da markdown link
                _leggi_path = _resolved if '_resolved' in dir() else (_resolved3 if '_resolved3' in dir() else output_path)
                _leggi_path = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", str(_leggi_path))
                # Bottone sovrascrittura se file già esisteva e non è stato sovrascritto
                kb_rows = [
                    [{"text": "📖 Leggi file", "callback_data": f"menu_cmd:/leggi {_leggi_path}"}],
                ]
                if file_existed and not _force_overwrite:
                    kb_rows.append([{
                        "text": "♻️ Sovrascrivi (cancella vecchio)",
                        "callback_data": f"menu_cmd:/cerca sovrascrivi {query} salva in {output_path}"
                    }])
                kb_rows.append([
                    {"text": "🏠 Menu", "callback_data": "menu_back"},
                    {"text": "🗑 Cancella", "callback_data": "msg_delete"},
                ])
                kb = {"inline_keyboard": kb_rows}
                # Mostra quale AI ha generato il contenuto
                _ai_label = ""
                if hasattr(self, "_ai_provider_ref") and self._ai_provider_ref and hasattr(self._ai_provider_ref, "last_used_name"):
                    _ai_label = f"\n<i>🤖 Generato da: {self._ai_provider_ref.last_used_name}</i>"
                await self._send_with_keyboard(chat_id, msg_final + _ai_label, kb)
            else:
                # Solo mostra contenuto
                if len(final_content) > 3500:
                    await self._send(chat_id, "<i>Contenuto lungo, invio come file</i>")
                    await _send_long_file(self, chat_id,
                        f"ricerca_{query[:30].replace(' ','_')}.md", final_content)
                else:
                    await self._send(chat_id, final_content[:3900])
                kb = {"inline_keyboard": [
                    [{"text": "🏠 Menu", "callback_data": "menu_back"},
                     {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, "<i>Fine</i>", kb)
            return

        # ── Config editor: lista backup ─────────────────────────────────
        if quick == "__CONFIG_BACKUPS__":
            try:
                backups = self._config_mgr.list_backups(limit=15)
                if not backups:
                    await self._send(chat_id, "💾 Nessun backup presente.")
                    return
                body = "💾 <b>Backup disponibili</b> (più recenti prima)\n\n"
                for b in backups:
                    body += f"  • <code>{b}</code>\n"
                body += f"\n<i>Totale: {len(backups)} backup in /config/homemind_patches/</i>"
                kb = {"inline_keyboard": [
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
                     {"text": "🗑 Cancella",         "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, body, kb)
            except Exception as e:
                await self._send(chat_id, f"⚠️ Errore: {str(e)[:200]}")
            return

        if quick == "__AI_MODE_MENU__":
            current = self._ai_mode.get(chat_id, "domotica")
            emoji_cur = "🏠" if current == "domotica" else "💬"
            label_cur = "Domotica" if current == "domotica" else "Libera"
            text = (
                f"🤖 <b>Modalità AI</b>\n"
                f"━━━━━━━━━━━━━━━━━\n\n"
                f"Attuale: {emoji_cur} <b>{label_cur}</b>\n\n"
                f"🏠 <b>Domotica</b>\n"
                f"<i>HomeMind controlla la tua casa: accende/spegne luci, "
                f"legge stati, crea task, legge sensori, esegue comandi.</i>\n\n"
                f"💬 <b>Libera</b>\n"
                f"<i>Chat AI generica: fai domande di qualsiasi tipo "
                f"(ricette, codice, idee, curiosità). Niente controllo casa.</i>"
            )
            kb = {"inline_keyboard": [
                [{"text": ("✅ 🏠 Domotica" if current == "domotica" else "🏠 Domotica"),
                  "callback_data": "aimode_set:domotica"},
                 {"text": ("✅ 💬 Libera" if current == "libera" else "💬 Libera"),
                  "callback_data": "aimode_set:libera"}],
                [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella",         "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, text, kb)
            return

        if isinstance(quick, str) and quick.startswith("__AI_MODE_SET__:"):
            mode = quick.split(":", 1)[1]
            if mode not in ("domotica", "libera"):
                mode = "domotica"
            self._ai_mode[chat_id] = mode
            if mode == "domotica":
                msg = ("✅ <b>Modalità Domotica attivata</b>\n\n"
                       "🏠 Ora posso controllare la tua casa.\n"
                       "<i>Prova: \"accendi luce salotto\" o \"che temperatura fa?\"</i>")
            else:
                msg = ("✅ <b>Modalità Libera attivata</b>\n\n"
                       "💬 Ora posso rispondere a qualsiasi domanda generica.\n"
                       "<i>Prova: \"dammi una ricetta veloce\" o \"spiegami X\"</i>\n\n"
                       "Per tornare al controllo casa: /ai_domotica")
            await self._send(chat_id, msg)
            return

        if quick == "__EMAIL_MENU__":
            await self._email_show_menu(chat_id)
            return

        if quick == "__EMAIL_LIST__":
            await self._email_show_inbox(chat_id)
            return

        if quick == "__EMAIL_EMPTY_TRASH__":
            await self._email_empty_folder_tg(chat_id, "[Gmail]/Trash")
            return

        if quick == "__EMAIL_EMPTY_SPAM__":
            await self._email_empty_folder_tg(chat_id, "[Gmail]/Spam")
            return

        if quick == "__EMAIL_CHECK_NOW__":
            await self._send(chat_id, "⚡ <i>Controllo email in corso…</i>")
            try:
                # Accede al checker globale tramite import lazy
                import main as _main_mod
                checker = getattr(_main_mod, "email_checker", None)
                if checker:
                    await checker._run_check()
                    await self._send(chat_id, "✅ Controllo completato.")
                else:
                    await self._send(chat_id, "⚠️ EmailChecker non attivo.")
            except Exception as e:
                await self._send(chat_id, f"❌ Errore: {e}")
            return

        if quick and quick.startswith("__EMAIL_NEW_PREFILL__:"):
            payload = quick[len("__EMAIL_NEW_PREFILL__:"):]
            parts = payload.split("|", 1)
            _to_addr = parts[0].strip() if parts else ""
            _to_name = parts[1].strip() if len(parts) > 1 else ""
            await self._email_start_new_prefilled(chat_id, _to_addr, _to_name)
            return

        if quick == "__BRIEFING_NOW__":
            await self._send(chat_id, t("briefing_loading"))
            try:
                if self.briefing_cb:
                    await self.briefing_cb()
                    # Dopo il briefing manda scorciatoie
                    kb = {"inline_keyboard": [
                        [{"text": "🏡 Stato casa",     "callback_data": "menu_cmd:/stato"},
                         {"text": "📊 Energia oggi",   "callback_data": "menu_cmd:/energia"}],
                        [{"text": "🗑️ Spazzatura",     "callback_data": "menu_cmd:/spazzatura"},
                         {"text": "🔄 Routine",        "callback_data": "menu_cmd:/routine"}],
                        [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
                         {"text": "🗑 Cancella",        "callback_data": "msg_delete"}],
                    ]}
                    await self._send_with_keyboard(chat_id,
                        "🎩 <i>Briefing inviato sopra. Scorciatoie:</i>", kb)
                else:
                    await self._send(chat_id, t("briefing_unavailable"))
            except Exception as e:
                await self._send(chat_id, t("error_short", msg=str(e)[:100]))
            return

        # ── Comandi allarme inline (cambio modalità via Telegram) ──────────
        if isinstance(quick, str) and quick.startswith("__ALARM_MODE__:"):
            await self._handle_alarm_mode_cmd(chat_id, quick[len("__ALARM_MODE__:"):])
            return

        if quick == "__README_INDEX__":
            await self._send(chat_id, await self._readme(""))
            return
        if quick and quick.startswith("__README__"):
            await self._send(chat_id, await self._readme(quick[10:]))
            return
        if quick is not None:
            await self._send(chat_id, quick)
            return
        await self._ai_reply(chat_id, text)

    def _quick_command(self, text):
        cmd = text.lower().strip()

        if cmd in ("/start", "start", "ciao", "hello", "help", "/help"):
            return "__START_SCREEN__"

        if cmd in ("/readme", "readme"):
            return "__README_INDEX__"
        if cmd.startswith("/readme ") or cmd.startswith("readme "):
            return "__README__" + (text.split(" ", 1)[1].strip() if " " in text else "")
        # ── Switch modalità AI: Domotica ↔ Libera ──────────────────────────
        if cmd in ("/ai_mode", "ai mode", "modalità ai", "modalita ai",
                   "switch ai", "cambia ai"):
            return "__AI_MODE_MENU__"

        # ── Config editor ─────────────────────────────────────────────────
        # /crea_sensore <descrizione> → crea sensore/template leggendo config esistente
        if (cmd.startswith("/crea_sensore ") or cmd.startswith("crea sensore ") or
                cmd.startswith("/modifica_config ") or cmd.startswith("modifica config ") or
                cmd.startswith("/modifica ") or cmd.startswith("modifica file ")):
            return "__CONFIG_CREATE_SENSOR__"
        if cmd in ("/crea_sensore", "crea sensore"):
            return "__CONFIG_CREATE_SENSOR_HELP__"
        # ── GitHub Installer ────────────────────────────────────────────
        if cmd in ("/github", "github", "installa da github", "/install_github",
                   "install github"):
            return "__GITHUB_MENU__"

        # ── Tool System ──────────────────────────────────────────────────
        if cmd.startswith("/scrivi ") or cmd.startswith("scrivi "):
            return "__TOOL_WRITE__"
        if cmd.startswith("/leggi ") or cmd.startswith("leggi "):
            # Distinguilo da /leggi_config (già gestito sopra)
            # Non bloccare path che contengono /config/ — quelli sono file legittimi
            _leggi_raw = cmd.split(None, 1)[1].strip() if " " in cmd else ""
            if not _leggi_raw.lower().startswith("config") or "/" in _leggi_raw:
                return "__TOOL_READ__"
        if cmd.startswith("/ls ") or cmd in ("/ls", "ls"):
            return "__TOOL_LS__"
        if cmd.startswith("/mkdir ") or cmd.startswith("mkdir "):
            return "__TOOL_MKDIR__"
        if cmd.startswith("/scarica ") or cmd.startswith("scarica ") or cmd.startswith("/download "):
            return "__TOOL_DOWNLOAD__"
        if cmd.startswith("/clona ") or cmd.startswith("clona ") or cmd.startswith("/clone "):
            return "__TOOL_CLONE__"
        # NON intercettare "elimina automazione" qui — va gestito dall'handler automazioni
        _is_auto_delete = bool(re.match(
            r"^/?(elimina|cancella|rimuovi|delete|remove)\s+automazion[ei]",
            cmd, re.IGNORECASE))
        if (cmd.startswith("/elimina ") or cmd.startswith("elimina file ") or cmd.startswith("/rm ")) \
                and not _is_auto_delete:
            return "__TOOL_DELETE__"
        if cmd.startswith("/cerca ") or cmd.startswith("cerca web ") or cmd.startswith("/search "):
            return "__TOOL_SEARCH__"
        if cmd in ("/tools", "tools", "strumenti"):
            return "__TOOL_HELP__"

        if cmd.startswith("/dbtest"):
            return "__DBTEST__"

        # ── Agentic mode ────────────────────────────────────────────────
        if cmd.startswith("/agent ") or cmd.startswith("agent ") or \
           cmd.startswith("/fai ") or cmd.startswith("fai ") or \
           cmd.startswith("/agente "):
            return "__AGENT_RUN__"
        if cmd in ("/agent", "/agente", "agente", "/fai"):
            return "__AGENT_HELP__"

        # ── Task agente (programmazione di task agentici) ──────────────
        if cmd.startswith("/task_agent ") or cmd.startswith("task agente "):
            return "__TASK_AGENT_CREATE__"
        if cmd in ("/task_agent", "task agente"):
            return "__TASK_AGENT_HELP__"

        # ── Task shell (programmazione comandi shell) ──────────────────
        if cmd.startswith("/task_shell ") or cmd.startswith("task shell "):
            return "__TASK_SHELL_CREATE__"

        # ── Comandi shell appresi ───────────────────────────────────────
        if cmd in ("/comandi_appresi", "comandi appresi", "/learned"):
            return "__LEARNED_LIST__"
        # ── HA System Info (via Supervisor REST) ────────────────────────
        if cmd in ("/ha_sistema", "/sistema", "/ha_info", "ha sistema",
                   "info sistema", "stato sistema", "/system_info"):
            return "__HA_SYSTEM__"
        if cmd in ("/ha_addons", "/lista_addons", "elenca addons", "lista addons"):
            return "__HA_ADDONS_LIST__"
        # ── HA Host: comandi naturali su sistema HA ─────────────────────
        # ── /ssh — unico punto di ingresso per comandi host + shell ──────────
        # /ssh help → README comandi
        if cmd in ("/ssh help", "ssh help", "/ssh -help", "ssh -help",
                   "/ssh --help", "/comandi ssh", "comandi ssh"):
            return "__SSH_COMMANDS_README__"
        # Typo comuni per /ssh: /shh, /ssh, /sssh, /sh ecc.
        _SSH_PREFIXES = (
            "/ssh ", "ssh ", "/host ", "host ", "/ha ", "/shell ", "shell ",
            "/shh ", "/sssh ", "/shs ", "/ssg ", "/sch ",  # typo frequenti
        )
        if any(cmd.startswith(p) for p in _SSH_PREFIXES):
            return "__SSH_RUN__"
        if cmd in ("/ssh", "/host", "/ha", "/shell", "shell", "/shh", "/sssh"):
            return "__SSH_HELP__"
        if cmd in ("/leggi_config", "leggi config", "leggi configurazione",
                   "mostra configurazione", "mostra config",
                   "/mostra_config", "mostra_config"):
            return "__CONFIG_READ__"
        if cmd in ("/backups_config", "backups config", "lista backup",
                   "/lista_backup"):
            return "__CONFIG_BACKUPS__"
        if cmd in ("/files_config", "files config", "lista file config",
                   "/lista_file", "tutti i file", "file config"):
            return "__CONFIG_FILES__"
        if cmd in ("/ai_domotica", "ai domotica", "modalità domotica"):
            return "__AI_MODE_SET__:domotica"
        if cmd in ("/ai_libera", "ai libera", "modalità libera", "chat libera"):
            return "__AI_MODE_SET__:libera"

        if cmd in ("/tools", "tools", "/strumenti", "strumenti", "/lista tools",
                   "lista tools", "/tool list", "mostra tools"):
            return "__TOOLS_LIST__"
        if cmd in ("/comandi full", "comandi full", "/help full", "/tutti i comandi",
                   "tutti i comandi", "/comandi tutti"):
            return "__COMANDI_FULL__"
        if cmd in ("/comandi", "comandi", "/aiuto", "aiuto", "/commands", "commands",
                   "/help it", "/help en", "lista comandi", "elenco comandi",
                   "cosa sai fare", "cosa puoi fare", "quali comandi", "che comandi",
                   "what can you do", "list commands", "show commands"):
            return "__MENU_MAIN__"

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

        if cmd in ("/routine reset", "routine reset", "azzera routine",
                   "resetta routine", "cancella routine", "/routine_reset"):
            return "__ROUTINE_RESET__"
        if cmd in ("/routine rileggi", "routine rileggi", "rileggi routine",
                   "forza backfill", "/routine_backfill"):
            return "__ROUTINE_BACKFILL__"
        if cmd.startswith("/routine leggi ") or cmd.startswith("routine leggi "):
            return "__ROUTINE_READ__:" + cmd.split("leggi ", 1)[-1].strip()
        if cmd in ("/routine aggiorna", "routine aggiorna", "aggiorna routine",
                   "aggiorna file routine", "/routine_md"):
            return "__ROUTINE_MD__"
        if cmd in ("/routine", "routine", "mia routine", "le mie abitudini",
                   "cosa hai imparato", "abitudini", "/abitudini"):
            return "__ROUTINE__"

        if cmd in ("/db", "db stats", "database", "statistiche db",
                   "db info", "homemind db"):
            return "__DB_STATS__"

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

        if cmd in ("/task_ripetuti", "/tasks_ripetuti", "task ripetuti",
                   "lista task ripetuti", "task ricorrenti", "cosa si ripete",
                   "recurring tasks", "what repeats"):
            return "__RECURRING_TASK_LIST__"

        # /task_alexa — avvia wizard creazione task Alexa (singolo)
        if cmd in ("/task_alexa", "task alexa", "nuovo task alexa", "alexa task"):
            return "__ALEXA_TASK_NEW__"
        # /task_alexa_ripetuto — avvia wizard task Alexa ricorrente
        if cmd in ("/task_alexa_ripetuto", "/task_alexa_ricorrente",
                   "task alexa ripetuto", "task alexa ricorrente"):
            return "__ALEXA_TASK_NEW_RECURRING__"
        # /task_alexa_cancella [N] — cancella task Alexa
        if cmd in ("/task_alexa_cancella", "cancella task alexa"):
            return "__ALEXA_TASK_LIST__"
        _alx_cancel = re.match(r'^/?(task_alexa_cancella|cancel_alexa_task)\s+(\d+)$', cmd)
        if _alx_cancel:
            return f"__ALEXA_TASK_CANCEL__{_alx_cancel.group(2)}"

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

        if cmd in ("/cancella_task_ripetuto tutti", "cancella tutti task ripetuti",
                   "svuota task ripetuti", "clear all recurring tasks",
                   "cancella tutti i task ripetuti"):
            return "__RECURRING_TASK_CLEAR__"

        # /cancella_task_ripetuto N
        _rcancel_m = re.match(r'^/?(cancella_task_ripetuto|cancel_recurring_task)\s+(\d+)$', cmd)
        if _rcancel_m:
            return f"__RECURRING_TASK_CANCEL__{_rcancel_m.group(2)}"

        # /cancella_task_ripetuto (senza numero → mostra lista)
        if cmd in ("/cancella_task_ripetuto", "cancella task ripetuto",
                   "cancel recurring task"):
            return "__RECURRING_TASK_LIST__"

        if cmd in ("/regole", "regole", "le mie regole", "mostra regole",
                   "lista regole", "show rules"):
            return "__RULES__"

        if cmd in ("/memoria", "memoria", "cosa sai", "cosa ricordi",
                   "cosa sai di me", "memory", "/memory"):
            return "__MEMORY__"

        if cmd in ("/memoria reset", "memoria reset", "dimentica tutto",
                   "cancella memoria", "reset memoria", "memory reset"):
            return "__MEMORY_RESET__"

        # "dimentica alias" senza argomento → mostra help
        if cmd in ("dimentica alias", "/dimentica alias"):
            n = len(self._shortcuts._shortcuts)
            if n == 0:
                return "⚠️ Nessun alias da eliminare.\n\nCrea alias con:\n  <code>memorizza che info energia = /energia</code>"
            lines = ["🗑️ <b>Quale alias vuoi rimuovere?</b>\n"]
            type_icons = {"sensor": "📡", "command": "⚡", "state": "🔌"}
            for i, s in enumerate(self._shortcuts._shortcuts, 1):
                icon = type_icons.get(s["action_type"], "🔗")
                kw = s["keyword"]
            lines.append(f"  <b>{i}.</b> {icon} \"{kw}\"  → <code>{s['action_value']}</code>")
            lines.append("\n<i>Scrivi: <code>dimentica alias 1</code> oppure <code>dimentica alias info energia</code></i>")
            return "\n".join(lines)

        if cmd.startswith("/dimentica ") or cmd.startswith("dimentica "):
            query = (text.split(" ", 1)[1] if " " in text else "").strip()
            # Intercetta "dimentica alias N" o "dimentica alias keyword" PRIMA della memoria
            import re as _re_da
            _m_da = _re_da.match(r'alias\s+(.+)', query.lower())
            if _m_da:
                return self._shortcuts.remove_shortcut(_m_da.group(1).strip())
            return f"__MEMORY_FORGET__{query}"

        # ── Alias / Shortcuts deterministici ───────────────────────────────
        if cmd in ("/alias", "/shortcuts", "alias", "i miei alias", "my aliases",
                   "lista alias", "mostra alias", "show aliases", "show shortcuts",
                   "comandi personalizzati", "shortcuts", "le mie scorciatoie",
                   "scorciatoie", "i miei comandi rapidi", "comandi rapidi"):
            return self._shortcuts.get_display()

        # Reset alias — gestisce typo e varianti ("cancella tuti alias", ecc.)
        _ALIAS_REMOVE_VERBS = ("cancell", "rimuov", "elimina", "svuota", "reset", "clear")
        _ALIAS_KEYWORDS     = ("alias", "shortcut", "scorciatoi")
        _cmd_is_reset_alias = (
            any(cmd.startswith(v) for v in _ALIAS_REMOVE_VERBS)
            and any(kw in cmd for kw in _ALIAS_KEYWORDS)
        ) or cmd in ("reset alias", "/alias reset", "clear aliases", "alias reset")
        if _cmd_is_reset_alias:
            return self._shortcuts.reset()

        # "dimentica alias batteria solare" / "rimuovi alias xxx"
        import re as _re_alias
        _m_alias = _re_alias.match(
            r'(?:dimentica|rimuovi|elimina|cancella|remove|delete|forget)\s+alias\s+(.+)', cmd)
        if _m_alias:
            return self._shortcuts.remove_shortcut(_m_alias.group(1).strip())

        # "memorizza che X = sensor.yyy" / "alias X = /energia"
        _MEMORIZE_TRIGGERS = [
            "memorizza che ", "memorizza: ", "memorizza quando ",
            "memorizza se ", "memorizza sempre ", "memorizza ",
            "alias ", "quando dico ", "memorize ", "remember "
        ]
        if any(cmd.startswith(tr) for tr in _MEMORIZE_TRIGGERS):
            _parsed = self._shortcuts.parse_memorize_request(text)
            if _parsed:
                return self._shortcuts.add_shortcut(
                    _parsed["keyword"], _parsed["action_type"], _parsed["action_value"]
                )
            # Non parsato → lascia passare all'AI


        if cmd in ("/solare", "solare", "surplus", "fotovoltaico", "solar",
                   "ottimizzatore", "/solar", "energia solare"):
            return "__SOLAR__"

        if cmd in ("/elettrodomestici", "elettrodomestici", "stato elettrodomestici",
                   "/appliances", "appliances", "tutti gli elettrodomestici"):
            return "__APPLIANCES__"

        # Richiesta singolo elettrodomestico — estrai il nome
        import re as _re_app
        _m_app = _re_app.match(
            r"^(?:stato\s+|status\s+)?/?(lavatrice|lavastoviglie|asciugatrice|forno|lavabiancheria|dishwasher|washer|dryer|oven)$",
            cmd.lower().strip())
        if _m_app:
            return f"__APPLIANCE_SINGLE:{_m_app.group(1)}__"

        if cmd in ("/debug_elettrodomestici", "debug elettrodomestici",
                   "/debug_appliances", "test elettrodomestici", "test lavatrice"):
            return "__APPLIANCES_DEBUG__"

        if cmd in ("/db_fix", "db fix", "fix db", "pulisci db", "cancella cicli db",
                   "gestisci cicli", "modifica cicli db"):
            return "__DB_FIX__"

        # /db_fix_show:NomeElettrodomestico
        if cmd.startswith("/db_fix_show:"):
            ap = cmd[len("/db_fix_show:"):]
            return f"__DB_FIX_SHOW:{ap}"

        # /db_fix_del:ID
        if cmd.startswith("/db_fix_del:"):
            cid = cmd[len("/db_fix_del:"):]
            return f"__DB_FIX_DEL:{cid}"

        # /db_fix_all  oppure  /db_fix_all:NomeElettrodomestico
        if cmd.startswith("/db_fix_all"):
            suffix = cmd[len("/db_fix_all"):]
            return f"__DB_FIX_ALL{suffix}"

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

        # ── Comandi modalità allarme ────────────────────────────────────────
        # Rileva frasi tipo "imposta allarme notte", "antifurto casa", ecc.
        _ALARM_PATTERNS = [
            # armed_night
            (["allarme notte", "antifurto notte", "modalità notte", "night mode",
              "alarm night", "notturno", "notte allarme"], "armed_night"),
            # armed_home
            (["allarme casa", "antifurto casa", "modalità casa", "home mode",
              "alarm home", "perimetrali", "in casa allarme", "allarme in casa",
              "armed home", "arm home"], "armed_home"),
            # armed_away
            (["allarme fuori", "antifurto fuori", "modalità fuori", "away mode",
              "alarm away", "fuori casa allarme", "allarme fuori casa",
              "armed away", "arm away", "arma fuori"], "armed_away"),
            # armed_vacation
            (["allarme vacanza", "modalità vacanza", "vacation mode",
              "alarm vacation", "vacanza"], "armed_vacation"),
        ]
        # Riconosci anche "modalità automatica / notify / disabilitato"
        _ALARM_AUTO_PATTERNS = [
            (["alarm auto", "allarme automatico", "antifurto automatico",
              "modalità auto", "gestione automatica", "auto alarm"], "auto"),
            (["alarm notify", "allarme notify", "chiedi conferma", "conferma telegram",
              "chiedi prima", "modalità notify"], "notify"),
            (["disabilita allarme", "disabilita antifurto", "alarm disabled",
              "nessun allarme", "disattiva allarme", "modalità disabilitata",
              "alarm off"], "disabled"),
        ]
        for keywords, mode in _ALARM_PATTERNS:
            if any(k in cmd for k in keywords):
                return f"__ALARM_MODE__:arm_mode:{mode}"
        for keywords, auto_mode in _ALARM_AUTO_PATTERNS:
            if any(k in cmd for k in keywords):
                return f"__ALARM_MODE__:auto_arm:{auto_mode}"

        if cmd in ("/briefing", "briefing", "buongiorno", "riassunto", "morning briefing"):
            return "__BRIEFING_NOW__"

        if cmd in ("/email", "email", "posta", "leggi email", "leggi posta"):
            return "__EMAIL_MENU__"

        if cmd in ("/email_inbox", "inbox email", "leggi inbox"):
            return "__EMAIL_LIST__"

        if cmd in ("/svuota_cestino", "svuota cestino", "empty trash", "/empty_trash"):
            return "__EMAIL_EMPTY_TRASH__"

        if cmd in ("/svuota_spam", "svuota spam", "empty spam", "/empty_spam"):
            return "__EMAIL_EMPTY_SPAM__"

        if cmd in ("/controlla_email", "controlla email", "check email", "controlla posta"):
            return "__EMAIL_CHECK_NOW__"

        # ── Email NLU: rileva intenzione di inviare email da linguaggio naturale ──
        import re as _re_email
        _EMAIL_SEND_TRIGGERS = [
            r"manda\s+(?:una\s+)?email",
            r"invia\s+(?:una\s+)?email",
            r"scrivi\s+(?:una\s+)?email",
            r"componi\s+(?:una\s+)?email",
            r"voglio\s+mandare\s+(?:una\s+)?email",
            r"voglio\s+inviare\s+(?:una\s+)?email",
            r"voglio\s+scrivere\s+(?:una\s+)?email",
            r"apri\s+(?:la\s+)?email",
            r"nuova\s+email",
            r"new\s+email",
            r"send\s+(?:an?\s+)?email",
            r"write\s+(?:an?\s+)?email",
        ]
        _is_email_send = any(_re_email.search(p, text, _re_email.IGNORECASE) for p in _EMAIL_SEND_TRIGGERS)
        # Rileva indirizzo email nel testo
        _email_addr_match = _re_email.search(r"[\w.+-]+@[\w.-]+\.\w{2,}", text)
        # Rileva "manda email a Nome" o "email per Nome"
        _email_to_name = _re_email.search(r"(?:email|mail)\s+(?:a|per|to)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]{1,30}?)(?:\s|$|,|\.)", text, _re_email.IGNORECASE)

        if _is_email_send or (_email_addr_match and any(w in cmd for w in ["email","mail","manda","invia","scrivi"])):
            # Costruisci payload pre-compilato per il wizard
            _to = _email_addr_match.group(0) if _email_addr_match else ""
            _name = _email_to_name.group(1).strip() if _email_to_name and not _to else ""
            payload = f"{_to}|{_name}"
            return f"__EMAIL_NEW_PREFILL__:{payload}"

        if cmd in ("/allarme", "allarme", "stato allarme", "allarme stato", "/alarm", "alarm", "alarm status"):
            return "__ALARM_INTERACTIVE__"

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
            # Leggi whitelist da person_config.json se configurata
            _temp_whitelist = []
            try:
                _tp = Path("/config/homemind_patches/person_config.json")
                if _tp.exists():
                    _tc = json.loads(_tp.read_text(encoding="utf-8-sig"))
                    _temp_whitelist = _tc.get("temperature_sensors", [])
            except Exception:
                pass

            if _temp_whitelist:
                # Mostra solo i sensori esplicitamente configurati
                temp_show = [(eid, cache[eid]) for eid in _temp_whitelist
                             if eid in cache and
                             cache[eid].get("state") not in ("unavailable", "unknown", "")]
            else:
                # Fallback automatico: tutti i sensori °C con filtro esclusione
                temp_sensors = [(eid, s) for eid, s in cache.items()
                                if eid.startswith("sensor.") and
                                s.get("attributes", {}).get("unit_of_measurement") == "°C" and
                                s.get("state") not in ("unavailable", "unknown")]
                TEMP_EXCLUDE = ("cpu", "processor", "system", "proxmox", "cpu_temp",
                                "raspberry", "board", "soc", "thermal",
                                "battery", "batteria", "apparent", "zewnętrzna",
                                "outside", "esterno_clima", "inside_temperature",
                                "outside_temperature", "meteo.lt", "weather",
                                "sm-", "samsung", "tablet", "phone", "telefon")
                temp_filtered = [(eid, s) for eid, s in temp_sensors
                                 if not any(k in eid.lower() or
                                            k in s.get("attributes",{}).get("friendly_name","").lower()
                                            for k in TEMP_EXCLUDE)]
                temp_show = temp_filtered if temp_filtered else temp_sensors[:8]

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
        Supporta modifiche semplici (con conferma) e wizard multi-step.
        """
        if not self._config_editor:
            return False
        import re as _wre
        text_low = text.lower()

        # Wizard triggers (modifiche interattive multi-step)
        WIZARD_RE = [
            r"aggiungi\s+proximity",
            r"nuova\s+proximity",
            r"configura\s+proximity",
            r"add\s+proximity",
            r"aggiungi.*power.?guard",
            r"add.*power.?guard",
            r"aggiungi\s+(?:forno|scaldabagno|asciugatrice|lavatrice|lavastoviglie)\s+a\s+power",
            r"aggiungi\s+elettrodomestico",
            r"add\s+appliance",
            r"monitora\s+nuov",
        ]
        is_wizard = any(_wre.search(pat, text_low) for pat in WIZARD_RE)
        if is_wizard:
            wizard = self._config_editor.detect_wizard(text)
            if wizard:
                self._config_editor.start_wizard(wizard)
                wtype = wizard["type"]
                step  = wizard["step"]
                data  = wizard.get("data", {})
                if wtype == "proximity_add" and step == "person":
                    await self._send(chat_id,
                        "⚙️ <b>Wizard: Aggiungi Proximity</b>\n\n"
                        "Scrivi l\'entity_id della persona:\n"
                        "<code>person.mario</code>\n\n"
                        "Scrivi <b>annulla</b> per uscire")
                elif wtype == "proximity_add" and step == "sensor" and data.get("person"):
                    await self._send(chat_id,
                        f"⚙️ <b>Wizard: Proximity per {data.get('person','?')}</b>\n\n"
                        "Scrivi il sensore di distanza:\n"
                        "<code>sensor.casa_mario_distance</code>")
                elif wtype == "power_guard_appliance_add":
                    if step == "switch" and data.get("name"):
                        # Nome già estratto dal testo, chiedi subito l'entity_id
                        await self._send(chat_id,
                            f"⚙️ <b>Wizard: Aggiungi a Power Guard</b>\n\n"
                            f"✅ Nome: <b>{data['name']}</b>\n\n"
                            f"Scrivi l'entity_id dello switch o del climatizzatore:\n"
                            f"Switch: <code>switch.presa_forno</code>\n"
                            f"Clima:  <code>climate.condizionatore_sala</code>\n\n"
                            f"Scrivi <b>annulla</b> per uscire")
                    else:
                        await self._send(chat_id,
                            "⚙️ <b>Wizard: Aggiungi a Power Guard</b>\n\n"
                            "Come si chiama l\'elettrodomestico?\n"
                            "Esempio: <b>Forno</b>, <b>Scaldabagno</b>\n\n"
                            "Scrivi <b>annulla</b> per uscire")
                elif wtype == "appliance_add":
                    await self._send(chat_id,
                        "⚙️ <b>Wizard: Aggiungi Elettrodomestico</b>\n\n"
                        "Come si chiama?\n"
                        "Esempio: <b>Forno</b>, <b>Asciugatrice</b>\n\n"
                        "Scrivi <b>annulla</b> per uscire")
                return True

        # Modifiche semplici
        CONFIG_TRIGGERS = [
            "aggiungi person.", "add person.",
            "escludi person.", "blacklist person.",
            "rimuovi person.", "remove person.",
            "soglia enel", "soglia power", "enel watt",
            "cambia soglia", "imposta soglia", "setta soglia",
            "change threshold", "set threshold",
            "powerguard",
            "notifica spazzatura", "trash notification",
            "soglia proximity", "proximity threshold",
            "temperatura massima clima", "max temp clima",
            "cambia lingua", "change language",
            "rimuovi proximity", "elimina proximity", "cancella proximity",
            "rimuovi delay", "elimina delay", "cancella delay",
            "rimuovi elettrodomestico", "elimina elettrodomestico",
            "aggiungi al briefing", "rimuovi dal briefing",
            "al briefing", "dal briefing", "nel briefing",
            "escludi dal briefing", "mostra nel briefing",
            "saluto briefing", "briefing alle",
            "ripristina briefing", "reset briefing", "azzera briefing",
            "energia al briefing", "meteo al briefing", "spazzatura al briefing",
            "aggiungi energia", "mostra energia", "aggiungi meteo",
            "rimuovi energia", "escludi energia", "rimuovi meteo",
            # elimina/svuota/cancella/pulisci + briefing
            "elimina briefing", "briefing elimina",
            "svuota briefing", "briefing svuota",
            "cancella briefing", "briefing cancella",
            "pulisci briefing", "briefing pulisci",
            "elimina extra", "svuota extra", "cancella extra", "pulisci extra",
            "elimina nota briefing", "elimina le note", "elimina sezioni",
            "rimuovi nota briefing", "rimuovi note briefing",
            # DND
            "silenzio notturno", "dnd", "do not disturb", "ore silenziose",
            "attiva silenzio", "disattiva silenzio", "fascia notturna",
            "notifiche notturne", "night mode", "silenzio notte",
            "quiet hours", "dnd start", "dnd end", "disturb start",
            "silenzio dalle", "silenzio alle", "dalle ore", "quiet start",
            # Consiglio / Tip / News briefing
            "disabilita consiglio", "abilita consiglio", "consiglio del giorno",
            "disabilita tip", "abilita tip", "abilita news", "disabilita news",
            "notizie briefing", "news briefing", "briefing news", "briefing notizie",
            "disable tip", "enable tip", "enable news", "disable news",
            # Meteo esterno briefing
            "meteo briefing", "briefing meteo", "imposta meteo",
            "al posto del consiglio", "invece del consiglio", "sostituisci consiglio",
            "abilita sport", "sport briefing", "notizie sportive", "eventi sportivi",
            "risultati sportivi", "calcio briefing", "briefing sport",
            "weather briefing", "briefing weather", "set weather",
        ]
        # Pattern regex per frasi config più complesse
        import re as _cre
        CONFIG_RE = [
            r"power.?guard.*\d+.*min",          # power guard X minuti
            r"\d+.*min.*power.?guard",          # X minuti power guard
            r"aspetta.*\d+.*min.*notif",        # aspetta N min notifica
            r"aspetta.*\d+.*min",               # aspetta N minuti
            r"attendi.*\d+.*min",               # attendi N minuti
            r"ritardo.*\d+.*min",               # ritardo N minuti
            r"delay.*\d+.*min",                 # delay N minuti
            r"modalit.*power.?guard",            # modalità power guard
            r"power.?guard.*modalit",            # power guard modalità
            r"soglia.*\d+.*[wW]",               # soglia NNN W
            r"\d+.*[wW].*(?:soglia|enel|power|guard|threshold)", # NNN W soglia
            r"cambia.*\d+.*[wW]",               # cambia NNN W
            r"rimuovi.*power.?guard",             # rimuovi da power guard
            r"rimuovi.*proximit",                 # rimuovi proximity
            r"briefing.*\d+.*(?:ora|h|ore)",       # briefing alle N
            r"aggiungi.*briefing|briefing.*aggiungi",
            r"rimuovi.*briefing|briefing.*rimuovi",
            r"escludi.*briefing|briefing.*escludi",
            r"elimina.*briefing|briefing.*elimina",
            r"svuota.*briefing|briefing.*svuota",
            r"cancella.*briefing|briefing.*cancella",
            r"(?:elimina|svuota|cancella|pulisci).*(?:extra|note|sezioni).*briefing",
            r"briefing.*(?:extra|note|sezioni).*(?:elimina|svuota|cancella)",
            r"(?:disabilita|abilita|attiva|disattiva|enable|disable).{0,20}(?:consiglio|tip|news|notizie)",
            r"(?:imposta|set|usa|cambia).{0,20}meteo.{0,20}briefing",
            r"meteo.{0,20}briefing.{0,20}(?:a|in|per|city|città)\s+\w+",
        ]
        is_config_re = any(_cre.search(pat, text_low) for pat in CONFIG_RE)
        has_trigger  = any(trigger in text_low for trigger in CONFIG_TRIGGERS)
        if not has_trigger and not is_config_re:
            return False

        intent = self._config_editor.detect_intent(text)
        if not intent:
            # Il trigger è stato trovato ma il formato non è chiaro
            # NON passare all'AI per evitare automazioni indesiderate
            if is_config_re or has_trigger:
                from translations import get_lang as _gl
                _lang = _gl()
                _hint = (
                    "⚙️ Non ho capito esattamente la modifica.\n\n"
                    "Esempi corretti:\n"
                    "  • <i>Cambia soglia Power Guard a 3000W</i>\n"
                    "  • <i>Power Guard modalità auto</i>\n"
                    "  • <i>Power Guard aspetta 5 minuti prima di notificare</i>\n"
                    "  • <i>Aggiungi person.mario alla whitelist</i>\n"
                    "  • <i>Aggiungi energia al briefing</i>\n"
                    "  • <i>Escludi meteo dal briefing</i>\n"
                    "  • <i>Aggiungi al briefing temperatura cucina sensor.temp_xxx</i>\n\n"
                    "Oppure scrivi <b>/config</b> per vedere la configurazione attuale."
                ) if _lang == "it" else (
                    "⚙️ I didn't understand the change.\n\n"
                    "Correct examples:\n"
                    "  • <i>Change Power Guard threshold to 3000W</i>\n"
                    "  • <i>Power Guard mode auto</i>\n"
                    "  • <i>Power Guard wait 5 minutes before notifying</i>\n\n"
                    "Or type <b>/config</b> to see current configuration."
                )
                await self._send(chat_id, _hint)
                return True  # gestito — non passare all'AI
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
        text_stripped = text.strip()

        # ── GUARD 1: ignora comandi slash espliciti ───────────────────────────
        # I comandi come /fai, /agent, /ssh, /task_agent, /task_shell ecc. sono
        # richieste esplicite dell'utente e NON devono essere intercettate dal
        # rilevatore di scheduling, anche se contengono parole come "alle 23"
        # o "accendi" — tipicamente perché l'utente sta riferendosi al NOME di
        # un'automazione esistente (es. /fai modifica l'automazione "Accendi
        # luce Mario alle 23" da 23 a 22).
        if text_stripped.startswith("/"):
            return False

        # ── GUARD 2: rimuovi stringhe quotate prima di cercare pattern ────────
        # Se l'utente cita il nome di un'entità/automazione tra virgolette
        # (es. "Accendi luce Mario alle 23"), quel testo è un IDENTIFICATORE,
        # non l'orario richiesto. Lo rimuoviamo dall'analisi temporale per
        # evitare falsi positivi.
        text_for_match = _re.sub(r'"[^"]*"|\'[^\']*\'|«[^»]*»|“[^”]*”', " ", text_stripped)
        text_low = text_for_match.lower().strip()

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

        # ── GUARD 3: ignora richieste di MODIFICA configurazione ──────────────
        # Pattern come "modifica/cambia/correggi ... .yaml" o riferimenti a
        # "automazione/automation" sono richieste di edit di file di config,
        # non di scheduling. Lasciali passare all'agente.
        CONFIG_EDIT_PATTERNS = [
            r'\b(modifica|modificare|cambia|cambiare|correggi|correggere|'
            r'aggiorna|aggiornare|edita|editare|sostituisci|sostituire|'
            r'rinomina|rinominare)\b.*\.(yaml|yml|json|md|py|js|html|css|txt)\b',
            r'\b(modify|change|edit|update|fix|rename|replace)\b.*\.(yaml|yml|json|md|py|js|html|css|txt)\b',
            r'\b(modifica|cambia|correggi|aggiorna|edita|rinomina)\b.{0,40}\b(automazion[ei]|automation)\b',
            r'\b(modify|change|edit|update|fix|rename)\b.{0,40}\b(automation)\b',
        ]
        if any(_re.search(p, text_low) for p in CONFIG_EDIT_PATTERNS):
            return False

        # Controlla se è un promemoria puro (ricordami, avvisami, remind)
        REMINDER_WORDS = ['ricordami', 'ricorda', 'avvisami', 'avvisa',
                          'remind me', 'remind', 'promemoria', 'nota',
                          'remember', 'alert me', 'notificami', 'notifica']
        is_reminder = any(w in text_low for w in REMINDER_WORDS)

        # Controlla che ci sia anche un'azione domotica (non solo un'ora)
        ACTION_WORDS_IT = ['accendi', 'spegni', 'imposta', 'avvia', 'ferma',
                          'abbassa', 'alza', 'apri', 'chiudi', 'arma', 'disarma']
        ACTION_WORDS_EN = ['turn on', 'turn off', 'set', 'start', 'stop',
                          'lower', 'raise', 'open', 'close', 'arm', 'disarm']
        all_actions = ACTION_WORDS_IT + ACTION_WORDS_EN
        has_action = any(w in text_low for w in all_actions)

        # Se non è né un promemoria né un'azione → lascia passare all'AI
        if not has_action and not is_reminder:
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

        # Per promemoria puri → il comando è solo la notifica, non un'azione HA
        if is_reminder and not has_action:
            cmd_text = f"__REMINDER__:{cmd_text or label}"

        # Se il regex ha svuotato troppo il testo, usa l'originale
        final_cmd = cmd_text if (cmd_text and len(cmd_text) >= 5) else text
        self._task_scheduler.add_task(
            execute_at = execute_at,
            label      = label,
            command    = final_cmd,
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

    async def _try_schedule_recurring(self, chat_id: str, text: str) -> bool:
        """
        Controlla se il messaggio è un task RICORRENTE (ogni giorno / ogni lunedì ecc.).
        Se sì, lo schedula e ritorna True. Altrimenti ritorna False.
        """
        import re as _re

        # Strippa eventuale prefisso /task_ripetuti (l'utente può usarlo come prefisso)
        working_text = text.strip()
        _prefix_pattern = r'^/task_ripetuti\s+'
        _had_explicit_prefix = bool(_re.match(_prefix_pattern, working_text, _re.IGNORECASE))
        if _had_explicit_prefix:
            working_text = _re.sub(_prefix_pattern, '', working_text, flags=_re.IGNORECASE).strip()

        # ── GUARD 1: ignora altri comandi slash espliciti ─────────────────────
        # Se il testo inizia con / ma NON è /task_ripetuti, è un altro comando
        # (es. /fai, /agent, /ssh) e NON deve essere intercettato.
        if not _had_explicit_prefix and working_text.startswith("/"):
            return False

        # ── GUARD 2: rimuovi stringhe quotate (nomi di automazioni/entità) ───
        working_text_clean = _re.sub(
            r'"[^"]*"|\'[^\']*\'|«[^»]*»|“[^”]*”', " ", working_text
        )
        text_low = working_text_clean.lower().strip()

        # Pattern che indicano ricorrenza
        RECURRING_PATTERNS = [
            r'ogni\s+giorno',
            r'tutti\s+i\s+giorni',
            r'ogni\s+mattina',
            r'ogni\s+sera',
            r'ogni\s+notte',
            r'tutte\s+le\s+mattine',
            r'tutte\s+le\s+sere',
            r'ogni\s+(lunedì|lunedi|martedì|martedi|mercoledì|mercoledi|'
            r'giovedì|giovedi|venerdì|venerdi|sabato|domenica)',
            r'every\s+day',
            r'daily',
            r'every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        ]
        is_recurring = any(_re.search(p, text_low) for p in RECURRING_PATTERNS)
        if not is_recurring:
            return False

        # Deve anche avere un orario e un'azione o promemoria
        has_time = bool(_re.search(
            r'alle\s+\d{1,2}|ore\s+\d{1,2}|at\s+\d{1,2}', text_low
        ))
        if not has_time:
            return False

        ACTION_WORDS = ['accendi', 'spegni', 'imposta', 'avvia', 'ferma',
                        'abbassa', 'alza', 'apri', 'chiudi', 'arma', 'disarma',
                        'turn on', 'turn off', 'set', 'start', 'stop',
                        'open', 'close', 'arm', 'disarm']
        REMINDER_WORDS = ['ricordami', 'ricorda', 'avvisami', 'promemoria',
                          'remind', 'remember', 'notificami']
        has_action   = any(w in text_low for w in ACTION_WORDS)
        is_reminder  = any(w in text_low for w in REMINDER_WORDS)

        if not has_action and not is_reminder:
            return False

        # Estrai orario e tipo ricorrenza
        time_info = self._recurring_task_scheduler.parse_recurring_time(working_text)
        if not time_info:
            return False

        hour   = time_info["hour"]
        minute = time_info["minute"]
        dow    = time_info.get("day_of_week", None)  # None = ogni giorno

        # Costruisci label leggibile
        dow_label = self._recurring_task_scheduler._dow_label(dow)
        time_label = f"{hour:02d}:{minute:02d}"
        label = working_text[:80] if len(working_text) <= 80 else working_text[:77] + "..."

        # Pulisci il comando dalle parole di ricorrenza e orario
        cmd_text = _re.sub(
            r'ogni\s+giorno|tutti\s+i\s+giorni|ogni\s+mattina|ogni\s+sera|'
            r'ogni\s+notte|tutte\s+le\s+mattine|tutte\s+le\s+sere|'
            r'ogni\s+\w+(?:ì|i)?\s*|every\s+day|daily|every\s+\w+\s*|'
            r'alle\s+ore\s+\d{1,2}:\d{2}|alle\s+ore\s+\d{1,2}|'
            r'alle\s+\d{1,2}:\d{2}|alle\s+\d{1,2}(?!\s*:)|'
            r'ore\s+\d{1,2}:\d{2}|ore\s+\d{1,2}|'
            r'at\s+\d{1,2}:\d{2}|at\s+\d{1,2}(?!\s*:)',
            '', working_text, flags=_re.IGNORECASE
        ).strip()
        cmd_text = _re.sub(r'\s{2,}', ' ', cmd_text).strip()

        # Promemoria puro
        if is_reminder and not has_action:
            cmd_text = f"__REMINDER__:{cmd_text or label}"

        # Se il regex ha svuotato troppo il testo, usa l'originale
        final_cmd_r = cmd_text if (cmd_text and len(cmd_text) >= 5) else working_text
        self._recurring_task_scheduler.add_task(
            hour       = hour,
            minute     = minute,
            label      = label,
            command    = final_cmd_r,
            chat_id    = chat_id,
            day_of_week = dow,
        )

        # Conferma
        from translations import get_lang
        lang = get_lang()
        if lang == "en":
            confirm = (
                f"🔁 <b>Recurring task scheduled!</b>\n"
                f"{label}\n"
                f"🕐 Will execute <b>{dow_label}</b> at <b>{time_label}</b>\n\n"
                f"Use /task_ripetuti to see all recurring tasks."
            )
        else:
            confirm = (
                f"🔁 <b>Task ripetuto schedulato!</b>\n"
                f"{label}\n"
                f"🕐 Eseguirò <b>{dow_label}</b> alle <b>{time_label}</b>\n\n"
                f"Usa /task_ripetuti per vedere tutti i task ripetuti."
            )
        await self._send(chat_id, confirm)
        return True

    async def _typing(self, chat_id):
        try:
            await self._api("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        except Exception:
            pass

    async def _readme(self, query: str) -> str:
        """Manuale interattivo HomeMind — risponde a domande di configurazione."""
        import logging
        _log = logging.getLogger("homemind.tgbot")
        MANUALE = '## 👤 FILTRI PERSONE\nConfigura chi HomeMind monitora.\n- <b>person_whitelist</b>: solo queste persone tracciate\n- <b>person_blacklist</b>: persone ignorate (es. persona.mqtt)\n<pre>{"person_whitelist": ["person.mario", "person.anna"],\n "person_blacklist": ["person.mqtt"]}</pre>\nTrova gli entity_id: HA → Strumenti sviluppatore → Stati → cerca <code>person.</code>\n\n## 🚶 FILTRI SENSORI MOVIMENTO\n- <b>motion_whitelist</b>: solo questi sensori (modalità esclusiva)\n- <b>motion_blacklist</b>: sensori ignorati\n<pre>{"motion_whitelist": ["binary_sensor.ingresso_occupancy"],\n "motion_blacklist": ["binary_sensor.cast"]}</pre>\n\n## 🚪 FILTRI PORTE E FINESTRE\n<pre>{"contact_blacklist": ["binary_sensor.porta_falsa"]}</pre>\n\n## 🌡️ SENSORI TEMPERATURA\n<pre>{"temperature_sensors": ["sensor.temp_soggiorno", "sensor.temp_cucina"]}</pre>\n\n## ⚡ ENERGIA (FV, consumo, rete)\n<pre>{"energy_sensors": {\n  "produzione_fv": "sensor.fv_tot1",\n  "consumo_casa": "sensor.daily_energy",\n  "rete_enel": "sensor.enel"\n}}</pre>\n\n## 📊 FASCIA ORARIA F1/F2/F3\n1. Crea utility_meter in HA con tariffe F1/F2/F3 + automazione per cambio fascia\n2. Configura HomeMind:\n<pre>{"fascia_sensors": {\n  "daily_source": "sensor.enel",\n  "oggi_f1": "sensor.energia_oggi_f1_f1",\n  "oggi_f2": "sensor.energia_oggi_f1_f2",\n  "oggi_f3": "sensor.energia_oggi_f1_f3",\n  "oggi_tot": "sensor.energia_oggi_totale",\n  "mese_f1": "sensor.energia_mese_f1_f1",\n  "mese_f2": "sensor.energia_mese_f1_f2",\n  "mese_f3": "sensor.energia_mese_f1_f3",\n  "mese_tot": "sensor.energia_mese_totale"\n}}</pre>\nComandi: <code>consumi fascia oggi</code>, <code>consumi fascia questo mese</code>\n\n## 📍 PROXIMITY GPS — Rilevamento Presenza\\n<b>Solo GPS (default, nessuna modifica):</b>\\n<pre>{"proximity_sensors": {"person.mario": {"sensor": "sensor.casa_mario_distance", "threshold_m": 100}}}</pre>\\n\\n<b>Zona gialla (anti-falsi armamenti):</b>\\nZona intermedia dove HomeMind aspetta N minuti prima di armare.\\n<code>"zone_yellow_m": 500, "zone_yellow_wait_min": 5</code>\\n→ Uscito a 200m? HomeMind aspetta 5 min. Se rientri: nulla. Se vai al lavoro: arma.\\n\\n<b>WiFi tracker + multi-fonte:</b>\\nRichiede N fonti concordi per armare. Se una è offline, scala automaticamente.\\n<code>"wifi_tracker": "device_tracker.sm_wifi", "require": 2</code>\\n<b>require:1</b>=solo GPS | <b>require:2</b>=GPS+WiFi | <b>require:3</b>=GPS+WiFi+Proximity\\n\\nTutto configurabile dalla pagina web ⚙️ → tab 📍 Proximity. Nessun JSON da toccare.\n\n## 📱 LOCATION TRACKER\n<pre>{"location_tracker": {\n  "mario": "device_tracker.sm_s931b"\n}}</pre>\n\n## 🔔 ALLARME\nConfigura il pannello allarme e la modalità di gestione automatica.\n\n<b>Pannello principale:</b>\n<pre>{"alarm_panel": "alarm_control_panel.home_alarm"}</pre>\n\n<b>Multi-partizione</b> (Paradox, DSC):\n<pre>{"alarm_panel": "alarm_control_panel.partizione1",\n "alarm_extra_panels": ["alarm_control_panel.partizione2"]}</pre>\n\n<b>alarm_auto_arm</b> — modalità armamento:\n<pre>{"alarm_auto_arm": "auto"}</pre>\nValori:\n· <code>auto</code> (default) — arma/disarma automaticamente quando tutti escono\n· <code>notify</code> — chiede conferma Telegram con bottoni prima di armare\n· <code>disabled</code> — non tocca mai il sistema allarme\n\n<b>alarm_disable_entities</b> — (solo con disabled) switch Spegni entità:\n<pre>{"alarm_disable_entities": true}</pre>\n· <code>true</code> (default) — spegne luci/clima all\'uscita anche con allarme disabled\n· <code>false</code> — non spegne niente, attiva il secondo switch notifica\n\n<b>alarm_disable_notify</b> — (solo con disabled + alarm_disable_entities: false) switch Notifica:\n<pre>{"alarm_disable_notify": true}</pre>\n· <code>true</code> (default) — manda notifica Telegram &#39;Casa vuota&#39; all\'uscita\n· <code>false</code> — silenzio totale: nessuna notifica, nessuna azione\n\n<b>Riepilogo combinazioni modalità disabled:</b>\n· disable_entities=ON → spegne entità all\'uscita (nessuna notifica allarme)\n· disable_entities=OFF, disable_notify=ON → solo notifica Telegram &#39;Casa vuota&#39;\n· disable_entities=OFF, disable_notify=OFF → silenzio totale, HomeMind non fa nulla\n\n<b>alarm_arm_mode</b> — modalità di armamento:\n<pre>{"alarm_arm_mode": "armed_away"}</pre>\nValori: armed_away · armed_home · armed_night · armed_vacation\n\n<b>Esempio completo:</b>\n<pre>{\n  "alarm_panel": "alarm_control_panel.home_alarm",\n  "alarm_auto_arm": "notify",\n  "alarm_arm_mode": "armed_away"\n}</pre>\n\n<b>alarm_on_leave</b> \u2014 entit\u00e0 da spegnere/chiudere all\'uscita:\n<pre>{\"alarm_on_leave\": [\"light.soggiorno\", \"switch.caldaia\", \"cover.tapparella_ingresso\", \"climate.termostato\"]}</pre>\nSe vuoto o assente: HomeMind spegne automaticamente tutte le luci accese e i termostati (comportamento default).\nSe configurato: gestisce <b>solo</b> le entit\u00e0 elencate.\nEntit\u00e0 supportate: <code>light.*</code> \u00b7 <code>switch.*</code> \u00b7 <code>cover.*</code> \u00b7 <code>climate.*</code> \u00b7 <code>media_player.*</code>\nConfigurabile dalla pagina web \u2699\ufe0f → tab \U0001f514 Allarme → sezione Entit\u00e0 da spegnere all\'uscita.\n\n## 🌡️ TERMOSTATO / CLIMA\n<pre>{"climate": {\n  "climate.termostato": {\n    "name": "Termostato", "switch": "switch.caldaia",\n    "min_temp": 16, "max_temp": 28\n  }\n}}</pre>\nEscludi valvole TRV che causano errori:\n<pre>{"climate_auto_off": false,\n "climate_exclude": ["climate.valvola_camera"]}</pre>\n\n## 🏠 ELETTRODOMESTICI\nModalità <b>power</b> (sensore W):\n<pre>{"appliances": {"lavatrice": {\n  "enabled": true, "name": "Lavatrice", "icon": "🫧",\n  "mode": "power", "power_sensor": "sensor.lavatrice_power",\n  "power_on_threshold": 50, "power_off_threshold": 10,\n  "min_cycle_minutes": 20, "max_idle_minutes": 5\n}}}</pre>\nModalità <b>smart</b> (Home Connect):\n<pre>{"appliances": {"lavastoviglie": {\n  "enabled": true, "name": "Lavastoviglie", "icon": "🍽️",\n  "mode": "smart", "state_sensor": "sensor.homeconnect_status",\n  "running_states": ["Run"], "done_states": ["Finished", "Ready"]\n}}}</pre>\n\n## ⚡ POWER GUARD (sovraccarico)\n<pre>{"power_guard": {\n  "enabled": true, "threshold_w": 3000,\n  "mode": "ask",\n  "power_sensor": "sensor.shellyem_power",\n  "appliances_priority": [{"name": "Lavatrice", "switch": "switch.lavatrice"}],\n  "delay_minutes": 5\n}}</pre>\n<b>mode</b>: <code>ask</code> chiede prima | <code>auto</code> spegne | <code>notify</code> avvisa solo\n\n## ☀️ SOLAR OPTIMIZER (surplus FV)\n<pre>{"solar_optimizer": {\n  "enabled": true, "min_surplus_w": 500,\n  "confirm_minutes": 5,\n  "battery_soc_sensor": "sensor.inverter_battery_capacity_percent",\n  "battery_full_threshold": 95,\n  "appliances": {\n    "lavatrice": {"enabled": true, "switch": "switch.lavatrice", "min_surplus_w": 800}\n  }\n}}</pre>\n\n## 🎩 BRIEFING MATTUTINO\nComandi da Telegram:\n<code>briefing alle 8</code> · <code>saluto briefing Buongiorno! ☀️</code>\n<code>disabilita consiglio</code> · <code>abilita news del giorno</code>\n<code>abilita sport briefing</code> · <code>imposta meteo briefing Roma</code>\n<code>escludi spazzatura dal briefing</code> · <code>ripristina briefing</code>\n\nConfig manuale:\n<pre>{"custom_briefing": {\n  "briefing_hour": 7,\n  "tip_mode": "tip",\n  "weather_city": "Roma",\n  "exclude_sections": ["spazzatura"],\n  "custom_greeting": "Buongiorno! ☀️"\n}}</pre>\n<b>tip_mode</b>: <code>tip</code> (AI) · <code>news</code> (ANSA) · <code>sports</code> (sport) · <code>disabled</code>\n\n## 🗑️ SPAZZATURA\nFile <code>/config/homemind_patches/spazzatura_calendario.json</code>:\n<pre>{"2026-04-07": ["Plastica"], "2026-04-08": ["Carta"]}</pre>\n<pre>{"spazzatura_notify_enabled": true, "spazzatura_notify_hour": 20}</pre>\n\n## 📹 FRIGATE NVR\n<pre>{"frigate": {\n  "enabled": true, "host": "192.168.1.119", "port": 5000,\n  "snapshot_on_alarm": true,\n  "cameras": {"ingresso": "binary_sensor.sensore_ingresso_occupancy"}\n}}</pre>\n\n## 🤖 PROVIDER AI\n<pre>{"ai_providers": [\n  {"name": "gemini", "model": "gemini-2.0-flash-lite", "api_key": "TUA_KEY"},\n  {"name": "groq", "model": "llama-3.3-70b-versatile", "api_key": "TUA_KEY"},\n  {"name": "mistral", "model": "mistral-small-latest", "api_key": "TUA_KEY"}\n]}</pre>\nProvider disponibili: gemini · groq · cerebras · mistral · openai · anthropic · deepseek\n\n## ⚡ ALIAS / COMANDI RAPIDI\n<code>memorizza che temp = sensor.temp_soggiorno</code>\n<code>memorizza che energia = /energia</code>\n<code>dimentica alias temp</code> · <code>cancella tutti gli alias</code> · <code>/alias</code>\n\n## 🔕 DO NOT DISTURB\n<code>silenzio dalle 23 alle 7</code> · <code>attiva silenzio notturno</code> · <code>disattiva silenzio</code>\n<pre>{"dnd": {"enabled": true, "start_hour": 23, "end_hour": 7}}</pre>\n\n## ❌ ERRORI COMUNI\n<b>alarm_panel non trovato</b>: cambia <code>alarm_panel</code> nel config con l\'entity_id reale, oppure rimuovila riga.\n<b>Sensore non trovato</b>: controlla l\'entity_id in HA → Strumenti sviluppatore → Stati.\n<b>Provider AI timeout</b>: normale, HomeMind passa al provider successivo automaticamente.\n'
        INDEX   = '📖 <b>HomeMind — Manuale di configurazione</b>\n\nScrivi <code>/readme</code> seguito da quello che cerchi:\n  /readme proximity\n  /readme fascia oraria\n  /readme elettrodomestici\n  /readme briefing\n  /readme errori\n\n📋 <b>Argomenti disponibili:</b>\n  👤 persone  🚶 movimento  🚪 contatti  🌡️ temperatura\n  ⚡ energia  📊 fascia  📍 proximity  📱 tracker\n  🔔 allarme  🌡️ clima  🏠 elettrodomestici  ⚡ power guard\n  ☀️ solar optimizer  🎩 briefing  🗑️ spazzatura\n  📹 frigate  🤖 provider AI  ⚡ alias  🔕 DND  ❌ errori\\n  🔁 task ripetuti\n  🤖 automazioni homemind'
        if not query:
            return INDEX
        try:
            if not self.ai_cb:
                raise RuntimeError("AI non disponibile")
            sysp = (
                "Sei l'assistente tecnico di HomeMind (addon Home Assistant).\n"
                "Rispondi SOLO basandoti sulla documentazione seguente.\n"
                "Mostra sempre esempi JSON copiabili.\n"
                "Usa HTML Telegram per formattare: <b>, <code>, <pre>.\n"
                "Rispondi in italiano, sii conciso e pratico.\n\n"
                "=== DOCUMENTAZIONE ===\n" + MANUALE
            )
            risposta = await self.ai_cb(sysp, f"Domanda: {query}", [])
            return f"📖 <b>README</b> · <i>{query[:50]}</i>\n\n{risposta}"
        except Exception as exc:
            _log.warning("readme error: %s", exc)
            # Fallback testuale: cerca le sezioni che matchano
            q = query.lower()
            hits = [s.strip() for s in MANUALE.split("\n## ") if q in s.lower()]
            if hits:
                preview = hits[0][:800]
                return f"📖 <b>README</b> · <i>{query[:50]}</i>\n\n<pre>{preview}</pre>"
            return (
                f"⚠️ Nessun risultato per <i>{query}</i>\n\n"
                f"Prova /readme per vedere tutti gli argomenti disponibili."
            )

    async def _handle_callback_query(self, cbq: dict):
        """Gestisce la pressione di un bottone inline (callback_query)."""
        cb_id   = cbq.get("id", "")
        data    = cbq.get("data", "")
        chat_id = str(cbq.get("message", {}).get("chat", {}).get("id", ""))
        msg_id  = cbq.get("message", {}).get("message_id")
        user    = cbq.get("from", {}).get("first_name", "?")

        logger.info("TG callback_query: data=%r chat=%s user=%s", data, chat_id, user)

        # Risponde subito a Telegram per togliere lo spinner
        try:
            await self._api("answerCallbackQuery", {"callback_query_id": cb_id})
        except Exception as e:
            logger.warning("answerCallbackQuery FAIL: %s", e)

        # Autorizzazione
        if self.allowed and chat_id not in self.allowed:
            logger.warning("TG callback: accesso negato chat_id=%s", chat_id)
            return

        # ── Salva file in cartella: scelta della cartella con i bottoni ────────
        if data.startswith("fi:"):
            try:
                await self._file_inbox_callback(chat_id, msg_id, data)
            except Exception as _fce:
                logger.warning("file_inbox callback errore: %s", _fce)
            return

        # ── Gestione conferma antifurto ────────────────────────────────────
        if data in ("alarm_confirm", "alarm_reject"):
            confirmed = (data == "alarm_confirm")

            # Risolvi il Future per questo chat (e per tutti gli altri chat autorizzati
            # che hanno ricevuto la richiesta — il primo a rispondere vince)
            resolved_any = False
            for cid, fut in list(self._pending_alarm_confirm.items()):
                if not fut.done():
                    fut.set_result(confirmed)
                    resolved_any = True
            self._pending_alarm_confirm.clear()

            if resolved_any:
                # Modifica il messaggio per mostrare la scelta fatta
                icon = "✅" if confirmed else "❌"
                label = "Antifurto ATTIVATO" if confirmed else "Antifurto NON attivato"
                try:
                    orig_text = cbq.get("message", {}).get("text", "")
                    await self._api("editMessageText", {
                        "chat_id":    chat_id,
                        "message_id": msg_id,
                        "text":       orig_text + f"\n\n{icon} <b>{label}</b> — risposta di {user}",
                        "parse_mode": "HTML",
                    })
                except Exception as e:
                    logger.debug("editMessageText FAIL (non critico): %s", e)
            return

        # ── Gestione callback Menu interattivo ─────────────────────────────
        if data.startswith("menu_cat:"):
            cat_id = data[len("menu_cat:"):]
            await self._show_category(chat_id, msg_id, cat_id)
            return
        if data == "menu_back":
            await self._show_main_menu_edit(chat_id, msg_id)
            return

        # ── Elimina regola singola o tutte ──────────────────────────────
        if data.startswith("rule_del:"):
            idx = int(data[len("rule_del:"):])
            rules = _get_active_rules()
            if 0 <= idx < len(rules):
                removed = rules.pop(idx)
                _save_active_rules(rules)
                msg_text = f"✅ Regola eliminata:\n<i>{_html_escape(removed)}</i>"
                if rules:
                    msg_text += f"\n\n📋 <b>Regole rimanenti: {len(rules)}</b>\n"
                    for i, r in enumerate(rules, 1):
                        msg_text += f"\n  <b>{i}.</b> {_html_escape(r)}"
                    msg_text += "\n\n<i>Usa /regole per gestirle</i>"
                else:
                    msg_text += "\n\n<i>Nessuna regola attiva.</i>"
                await self._send(chat_id, msg_text)
            else:
                await self._send(chat_id, "⚠️ Regola non trovata.")
            return
        if data == "rule_del_all":
            _save_active_rules([])
            await self._send(chat_id, "🗑️ Tutte le regole sono state eliminate.")
            return

        # ── Salva ultimo output SSH ──────────────────────────────────────
        if data == "ssh_save_last":
            last = getattr(self, "_last_ssh_output", {}).get(chat_id)
            if not last:
                return
            from datetime import datetime as _dt2
            _ts = _dt2.now().strftime("%Y%m%d_%H%M")
            _spath = f"ago/risultati/ssh_{_ts}.md"
            _md = (
                f"# SSH: {last['cmd']}\n\n"
                f"_Salvato: {_dt2.now().strftime('%Y-%m-%d %H:%M')} | Canale: {last['channel']}_\n\n"
                f"```\n{last['text'][:7000]}\n```\n"
            )
            wr = _tools.tool_scrittura(_spath, _md)
            _rp = "/config/" + wr.get("path", _spath).lstrip("/")
            kb2 = {"inline_keyboard": [
                [{"text": "📂 Leggi", "callback_data": f"menu_cmd:/leggi {_spath}"}],
                [{"text": "🏠 Menu",  "callback_data": "menu_back"}],
            ]}
            await self._send_with_keyboard(chat_id, f"💾 <b>Salvato:</b> <code>{_rp}</code>", kb2)
            return

        # ── Config editor: apri file specifico da bottone ────────────────
        if data.startswith("cfg_read:"):
            requested = data[len("cfg_read:"):]
            try:
                content = self._config_mgr.read_file(requested)
                analysis = self._config_mgr.analyze_yaml_structure(content)
                sections = ", ".join(analysis["sections"][:20]) or "(nessuna)"
                header = (
                    f"📄 <b>{requested}</b>\n"
                    f"<i>{analysis['num_lines']} righe · {len(analysis['sections'])} sezioni</i>\n\n"
                    f"📋 {sections}"
                )
                await self._send(chat_id, header)
                await _send_long_file(self, chat_id, requested, content)
                # Bottone "Modifica con AI" passa il file specifico
                kb = {"inline_keyboard": [
                    [{"text": f"🛠️ Modifica {requested} con AI",
                      "callback_data": f"cfg_mod_target:{requested}"}],
                    [{"text": "📁 Altri file",      "callback_data": "menu_cmd:/files_config"},
                     {"text": "💾 Backup",          "callback_data": "menu_cmd:/backups_config"}],
                    [{"text": "🏠 Menu",             "callback_data": "menu_back"},
                     {"text": "🗑 Cancella",         "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, "<i>Fine file</i>", kb)
            except FileNotFoundError:
                await self._send(chat_id, f"⚠️ Non trovato: <code>{requested}</code>")
            except Exception as e:
                await self._send(chat_id, f"⚠️ Errore: {str(e)[:250]}")
            return

        # ── Config editor: imposta file target per modifica AI ─────────
        if data.startswith("cfg_mod_target:"):
            target_file = data[len("cfg_mod_target:"):]
            try:
                # Verifica che il file esista
                self._config_mgr.read_file(target_file)
            except Exception as e:
                await self._send(chat_id, f"⚠️ File non accessibile: {str(e)[:150]}")
                return
            # Salva il target nello stato chat
            self._modify_target[chat_id] = target_file
            body = (
                f"🛠️ <b>Modifica AI di {target_file}</b>\n\n"
                f"<i>Scrivi cosa vuoi modificare/aggiungere in questo file.</i>\n\n"
                f"<b>Esempi:</b>\n"
                f"• aggiungi un sensore template per la temperatura media\n"
                f"• crea utility_meter giornaliero per consumo lavatrice\n"
                f"• aggiungi automazione: alle 22 spegni tutte le luci\n\n"
                f"<i>HomeMind leggerà il file, capirà la struttura esistente, "
                f"genererà il codice e ti chiederà conferma prima di applicare. "
                f"Backup automatico in /config/homemind_patches/ a ogni modifica.</i>"
            )
            kb = {"inline_keyboard": [
                [{"text": "❌ Annulla", "callback_data": "cfg_mod_cancel"}],
                [{"text": "🏠 Menu", "callback_data": "menu_back"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return

        if data == "cfg_mod_cancel":
            self._modify_target.pop(chat_id, None)
            await self._send(chat_id, "❌ Modifica annullata.")
            return

        # ── GitHub Wizard: scelta tipo ────────────────────────────────
        if data.startswith("gh_type:"):
            install_type = data[len("gh_type:"):]
            type_labels = {
                "addon":     "📦 Add-on Repository",
                "component": "🧩 Custom Component",
                "card":      "🎴 Card Lovelace",
            }
            type_descriptions = {
                "addon":     ("Aggiunge un repository di add-on a Home Assistant. "
                              "Dopo l'aggiunta, gli addon appariranno nello Store."),
                "component": ("Clona il repository in /config/custom_components/. "
                              "Dopo il riavvio HA, l'integrazione sarà disponibile."),
                "card":      ("Scarica i file .js della card in /config/www/community/. "
                              "Devi poi registrarla nelle risorse Lovelace."),
            }
            if install_type not in type_labels:
                await self._send(chat_id, "⚠️ Tipo non valido.")
                return
            self._github_pending[chat_id] = {"step": "url", "type": install_type}
            body = (
                f"🔗 <b>{type_labels[install_type]}</b>\n\n"
                f"<i>{type_descriptions[install_type]}</i>\n\n"
                f"<b>Incolla l\'URL GitHub del repository.</b>\n\n"
                f"Esempi accettati:\n"
                f"• <code>https://github.com/owner/repo</code>\n"
                f"• <code>github.com/owner/repo</code>\n"
                f"• <code>owner/repo</code>"
            )
            kb = {"inline_keyboard": [
                [{"text": "❌ Annulla", "callback_data": "gh_cancel"}],
                [{"text": "🏠 Menu",    "callback_data": "menu_back"}],
            ]}
            await self._send_with_keyboard(chat_id, body, kb)
            return

        if data == "gh_cancel":
            self._github_pending.pop(chat_id, None)
            await self._send(chat_id, "❌ Installazione annullata.")
            return

        if data.startswith("gh_confirm:"):
            install_type = data[len("gh_confirm:"):]
            pending = self._github_pending.get(chat_id)
            if not pending or pending.get("type") != install_type:
                await self._send(chat_id, "⚠️ Sessione scaduta.")
                return
            url = pending.get("url")
            self._github_pending.pop(chat_id, None)
            await self._send(chat_id, f"⏳ <i>Installazione in corso...</i>\n<code>{_html_escape(url)}</code>")
            try:
                if install_type == "addon":
                    result = await self._github_installer.add_addon_repository(url)
                elif install_type == "component":
                    result = await self._github_installer.install_custom_component(url)
                elif install_type == "card":
                    result = await self._github_installer.install_lovelace_card(url)
                else:
                    result = {"success": False, "message": "Tipo non valido"}

                if result["success"]:
                    # Mostra subito conferma installazione
                    await self._send(chat_id, result["message"])

                    # Memorizza dati per "Genera card pronta" se è una card
                    if install_type == "card":
                        self._github_pending[chat_id] = {
                            "step":           "card_ready",
                            "type":           "card",
                            "card_type":      result.get("card_type", result.get("card_name")),
                            "card_name":      result.get("card_name"),
                            "js_filename":    result.get("js_filename"),
                            "readme":         result.get("readme", ""),
                            "github_url":     result.get("github_url", ""),
                        }

                    # Genera guida AI dal README
                    readme = result.get("readme", "")
                    github_url = result.get("github_url", "")
                    inst_type = result.get("type", install_type)

                    if readme and self.ai_cb:
                        await self._typing(chat_id)
                        try:
                            type_label = {
                                "addon":     "addon Home Assistant",
                                "component": "custom component HA",
                                "card":      "card Lovelace",
                            }.get(inst_type, inst_type)

                            sys_prompt = (
                                f"Sei un esperto Home Assistant. L'utente ha appena installato un "
                                f"{type_label} dal repository {github_url}. "
                                f"Sotto trovi il README del progetto.\n\n"
                                f"Scrivi una GUIDA RAPIDA in italiano, max 800 parole, con:\n"
                                f"1. Cosa fa il progetto (1-2 frasi)\n"
                                f"2. Configurazione minima necessaria (con esempio YAML se serve)\n"
                                f"3. Come usarlo (passi pratici)\n"
                                f"4. Eventuali note importanti / requisiti\n\n"
                                f"USA HTML Telegram (<b>, <i>, <code>, <pre>) NON markdown. "
                                f"Sii concreto, niente fronzoli, esempi reali."
                            )
                            user_prompt = (
                                f"Tipo: {type_label}\n"
                                f"Repo: {github_url}\n\n"
                                f"README:\n{readme[:6000]}"
                            )
                            guide = await self.ai_cb(sys_prompt, user_prompt, None)
                            if guide:
                                await self._send(chat_id,
                                    f"📖 <b>Guida rapida</b>\n\n{guide[:3500]}")
                        except Exception as e:
                            logger.warning("AI guide generation failed: %s", e)

                    # Bottoni finali (con "Genera card pronta" se è card)
                    rows = []
                    if install_type == "card":
                        rows.append([{"text": "🎴 Genera card pronta",
                                      "callback_data": "gh_card_generate"}])
                    rows.append([{"text": "🔗 Altra installazione",
                                  "callback_data": "menu_cmd:/github"}])
                    rows.append([
                        {"text": "🏠 Menu",     "callback_data": "menu_back"},
                        {"text": "🗑 Cancella", "callback_data": "msg_delete"},
                    ])
                    await self._send_with_keyboard(chat_id,
                        "<i>Cosa vuoi fare ora?</i>", {"inline_keyboard": rows})
                else:
                    body = f"⚠️ <b>Installazione fallita</b>\n\n{result['message']}"
                    kb = {"inline_keyboard": [
                        [{"text": "🔗 Riprova",  "callback_data": "menu_cmd:/github"}],
                        [{"text": "🏠 Menu",     "callback_data": "menu_back"},
                         {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                    ]}
                    await self._send_with_keyboard(chat_id, body, kb)
            except Exception as e:
                logger.exception("github install")
                await self._send(chat_id, f"⚠️ Errore: {str(e)[:300]}")
            return

        # ── GitHub Wizard: genera card YAML pronta ────────────────────
        if data == "gh_card_generate":
            pending = self._github_pending.get(chat_id, {})
            if not pending or pending.get("type") != "card":
                await self._send(chat_id,
                    "⚠️ Sessione card scaduta. Reinstalla la card per rigenerare.")
                return
            card_type = pending.get("card_type", pending.get("card_name", ""))
            card_name = pending.get("card_name", "")
            readme    = pending.get("readme", "")
            github_url = pending.get("github_url", "")

            await self._typing(chat_id)

            # Estrai entità HA per dare contesto all'AI
            cache = self.state_cache_cb() if self.state_cache_cb else {}
            # Lista compatta delle entità più usate
            ent_lines = []
            for eid, s in list(cache.items())[:80]:
                fname = (s.get("attributes") or {}).get("friendly_name", "")
                ent_lines.append(f"  • {eid} ({fname})")
            entities_ctx = "\n".join(ent_lines) if ent_lines else "(no entities)"

            # Prompt AI
            sys_prompt = (
                "Sei un esperto Lovelace Home Assistant. L'utente ha appena installato "
                "una custom card e vuole un YAML pronto da incollare nella sua dashboard.\n\n"
                "REGOLE:\n"
                "1. Usa le entità HA esistenti dell'utente (sotto), non inventarle.\n"
                "2. Scegli entità coerenti con il tipo di card.\n"
                "3. Rispondi SOLO con YAML valido (configurazione card), niente testo extra "
                "e niente markdown.\n"
                "4. Se la card supporta opzioni avanzate dal README, includile come esempio.\n"
                "5. Inizia con `type: custom:<card-type>`.\n"
            )
            user_prompt = (
                f"Card installata: {card_name}\n"
                f"card-type: custom:{card_type}\n"
                f"Repo: {github_url}\n\n"
                f"README (per documentazione opzioni):\n{readme[:5000]}\n\n"
                f"Entità HA disponibili:\n{entities_ctx}\n\n"
                f"Genera un YAML di configurazione card pronto da copiare nella dashboard."
            )

            try:
                if not self.ai_cb:
                    await self._send(chat_id, "⚠️ AI non disponibile.")
                    return
                yaml_out = await self.ai_cb(sys_prompt, user_prompt, None)
                if not yaml_out:
                    await self._send(chat_id, "⚠️ AI non ha risposto.")
                    return

                yaml_clean = _extract_yaml(yaml_out)
                # Garantisci che inizi con type: custom:
                if "type:" not in yaml_clean[:120]:
                    # Forza prefix
                    yaml_clean = f"type: custom:{card_type}\n" + yaml_clean

                self._github_pending.pop(chat_id, None)

                body = (
                    f"🎴 <b>Card YAML pronta</b>\n\n"
                    f"<i>Copia il blocco e incollalo nel tuo dashboard:</i>\n"
                    f"<i>(Modifica → Aggiungi card → Manual)</i>"
                )
                await self._send(chat_id, body)
                await _send_long_file(self, chat_id, f"card_{card_name}.yaml", yaml_clean)

                kb = {"inline_keyboard": [
                    [{"text": "🔗 Altra installazione", "callback_data": "menu_cmd:/github"}],
                    [{"text": "🏠 Menu",                "callback_data": "menu_back"},
                     {"text": "🗑 Cancella",            "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, "<i>Fatto!</i>", kb)
            except Exception as e:
                logger.exception("gh_card_generate")
                await self._send(chat_id, f"⚠️ Errore generazione card: {str(e)[:300]}")
            return

        # ── Install pacchetto Alpine (callback bottoni) ─────────────────
        if data == "pkg_install_yes":
            pending = getattr(self, "_pkg_install_pending", {}).get(chat_id)
            if not pending:
                await self._send(chat_id, "⚠️ Sessione install scaduta.")
                return
            pkg = pending.get("package")
            original_req = pending.get("original_request", "")
            self._pkg_install_pending.pop(chat_id, None)

            await self._send(chat_id, f"📦 <i>Installo {pkg}...</i>")
            try:
                inst = await _tools.tool_install_package(pkg)
                if not inst.get("success"):
                    body = f"⚠️ {inst.get('message','install fallita')}"
                    if inst.get("stderr"):
                        body += f"\n<pre>{_html_escape(inst['stderr'][:1500])}</pre>"
                    kb = {"inline_keyboard": [
                        [{"text": "🏠 Menu", "callback_data": "menu_back"},
                         {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                    ]}
                    await self._send_with_keyboard(chat_id, body, kb)
                    return
                # Install OK → riprova comando originale
                await self._send(chat_id,
                    f"✅ {inst['message']}\n\n"
                    f"<i>Riprovo:</i> {_html_escape(original_req[:200])}")
                res = await _tools.tool_natural_shell(original_req, ai_cb=self.ai_cb)
                body  = f"💻 <code>{_html_escape(res.get('command','')[:200])}</code>\n\n"
                body += res.get("message", "")
                if res.get("stdout"):
                    body += f"\n\n<pre>{_html_escape(res['stdout'][:2500])}</pre>"
                kb = {"inline_keyboard": [
                    [{"text": "📋 Comandi appresi", "callback_data": "menu_cmd:/comandi_appresi"}],
                    [{"text": "🏠 Menu", "callback_data": "menu_back"},
                     {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, body, kb)
            except Exception as e:
                logger.exception("pkg_install_yes")
                await self._send(chat_id, f"⚠️ Errore: {str(e)[:200]}")
            return

        if data == "pkg_install_no":
            getattr(self, "_pkg_install_pending", {}).pop(chat_id, None)
            await self._send(chat_id, "❌ Installazione annullata.")
            return

        # ── Agent: conferma utente per operazioni distruttive ──────────
        if data == "agent_yes":
            fut = self._agent_confirm.get(chat_id)
            if fut and not fut.done():
                fut.set_result(True)
            await self._send(chat_id, "✅ Confermato, l\'agente procede...")
            return
        if data == "agent_no":
            fut = self._agent_confirm.get(chat_id)
            if fut and not fut.done():
                fut.set_result(False)
            await self._send(chat_id, "❌ Operazione rifiutata")
            return

        # ── Tool delete: conferma ───────────────────────────────────────
        if data == "tool_del_ok":
            pending = getattr(self, "_tool_pending", {}).get(chat_id)
            if not pending or pending.get("action") != "delete":
                await self._send(chat_id, "⚠️ Sessione scaduta.")
                return
            result = _tools.tool_delete(pending["path"])
            self._tool_pending.pop(chat_id, None)
            kb = {"inline_keyboard": [
                [{"text": "🏠 Menu", "callback_data": "menu_back"},
                 {"text": "🗑 Cancella", "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id, result["message"], kb)
            return

        if data == "tool_del_no":
            getattr(self, "_tool_pending", {}).pop(chat_id, None)
            await self._send(chat_id, "❌ Eliminazione annullata.")
            return

        # ── Config editor: applica / annulla / diff ──────────────────────
        if data == "config_apply":
            pending = self._config_pending.get(chat_id)
            if not pending:
                await self._send(chat_id, "⚠️ Nessuna modifica in attesa.")
                return
            try:
                backup_path = self._config_mgr.write_file(
                    pending["file"], pending["new_content"],
                    validate_yaml=True, do_backup=True
                )
                self._config_pending.pop(chat_id, None)
                msg = (
                    f"✅ <b>Modifica applicata</b>\n\n"
                    f"📄 File: <code>{pending['file']}</code>\n"
                    f"📦 Sezione: <code>{pending['section']}</code>\n"
                    f"💾 Backup: <code>{backup_path}</code>\n\n"
                    f"<i>Riavvia Home Assistant per caricare la modifica:\n"
                    f"Impostazioni → Sistema → Riavvia</i>"
                )
                kb = {"inline_keyboard": [
                    [{"text": "🔄 Controlla config HA", "callback_data": "menu_cmd:/riparazioni"}],
                    [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
                     {"text": "🗑 Cancella",         "callback_data": "msg_delete"}],
                ]}
                await self._send_with_keyboard(chat_id, msg, kb)

                # ── Azioni extra post-apply (write + read) ───────────────
                _ew_path  = pending.get("extra_write_path")
                _er_after = pending.get("extra_read_after", False)
                _yaml_added = pending.get("yaml_added", "")

                if _ew_path:
                    # Normalizza il path
                    if not _ew_path.startswith("/"):
                        _ew_path = "/config/" + _ew_path.lstrip("/")
                    # Contenuto da scrivere: il YAML generato con intestazione
                    _write_content = (
                        f"# Sensore generato da HomeMind\n"
                        f"# Descrizione: {pending.get('description', '')}\n"
                        f"# File target: {pending.get('file', '')}\n"
                        f"# Sezione: {pending.get('section', '')}\n\n"
                        f"```yaml\n{_yaml_added}\n```\n"
                    )
                    try:
                        import os as _os
                        _os.makedirs(_os.path.dirname(_ew_path), exist_ok=True)
                        with open(_ew_path, "w", encoding="utf-8") as _wf:
                            _wf.write(_write_content)
                        await self._send(chat_id,
                            f"📝 Risultato scritto in <code>{_ew_path}</code>")
                        if _er_after:
                            await self._send(chat_id,
                                f"<b>📖 Contenuto di {_ew_path}:</b>\n\n"
                                f"<pre>{_html_escape(_write_content[:3000])}</pre>")
                    except Exception as _we:
                        await self._send(chat_id, f"⚠️ Errore scrittura extra: {_we}")
                elif _er_after and _yaml_added:
                    # Nessun path specificato ma "mostra/leggi" → mostra YAML direttamente
                    await self._send(chat_id,
                        f"<b>📖 YAML generato e applicato:</b>\n\n"
                        f"<pre>{_html_escape(_yaml_added[:3000])}</pre>")

            except Exception as e:
                logger.exception("config_apply FAIL")
                await self._send(chat_id, f"⚠️ Errore scrittura: {str(e)[:300]}")
            return

        if data == "config_cancel":
            self._config_pending.pop(chat_id, None)
            await self._send(chat_id, "❌ Modifica annullata. Nessun file è stato toccato.")
            return

        if data == "config_diff":
            pending = self._config_pending.get(chat_id)
            if not pending:
                await self._send(chat_id, "⚠️ Nessuna modifica in attesa.")
                return
            # Rigenera diff
            try:
                existing = self._config_mgr.read_file(pending["file"])
                diff_txt = self._config_mgr._make_diff(existing, pending["new_content"], max_lines=50)
                body = (
                    f"📊 <b>Diff proposto</b>\n\n"
                    f"<pre>{_html_escape(diff_txt[:3000])}</pre>"
                )
                kb = {"inline_keyboard": [
                    [{"text": "✅ Applica", "callback_data": "config_apply"},
                     {"text": "❌ Annulla",  "callback_data": "config_cancel"}],
                ]}
                await self._send_with_keyboard(chat_id, body, kb)
            except Exception as e:
                await self._send(chat_id, f"⚠️ Errore diff: {str(e)[:200]}")
            return

        # ── Cancellazione messaggio (pulizia chat) ────────────────────────
        if data == "msg_delete":
            # Cancella la risposta del bot
            try:
                await self._api("deleteMessage", {
                    "chat_id": chat_id,
                    "message_id": msg_id,
                })
            except Exception as e:
                logger.debug("deleteMessage bot FAIL: %s — fallback edit", e)
                try:
                    await self._api("editMessageText", {
                        "chat_id": chat_id, "message_id": msg_id,
                        "text": "🗑 <i>Messaggio rimosso</i>",
                        "parse_mode": "HTML",
                    })
                except Exception as e2:
                    logger.debug("editMessageText placeholder FAIL: %s", e2)
            # Cancella anche l'ultimo messaggio dell'utente (quello che ha generato la risposta)
            user_msg_id = self._last_user_msg_id.get(chat_id)
            if user_msg_id:
                try:
                    await self._api("deleteMessage", {
                        "chat_id": chat_id,
                        "message_id": user_msg_id,
                    })
                except Exception as e:
                    logger.debug("deleteMessage user FAIL (ignoro): %s", e)
                # Rimuovi dall'cache (evita tentativi su messaggi già cancellati)
                self._last_user_msg_id.pop(chat_id, None)
            return

        # ── Switch modalità AI dai bottoni ────────────────────────────────
        if data.startswith("aimode_set:"):
            mode = data.split(":", 1)[1]
            if mode not in ("domotica", "libera"):
                mode = "domotica"
            self._ai_mode[chat_id] = mode
            if mode == "domotica":
                msg = ("✅ <b>Modalità Domotica attivata</b>\n\n"
                       "🏠 Ora posso controllare la tua casa.\n"
                       "<i>Prova: \"accendi luce salotto\" o \"che temperatura fa?\"</i>")
            else:
                msg = ("✅ <b>Modalità Libera attivata</b>\n\n"
                       "💬 Ora posso rispondere a qualsiasi domanda generica.\n"
                       "<i>Prova: \"dammi una ricetta\" o \"spiegami X\"</i>\n\n"
                       "Per tornare al controllo casa: /ai_domotica")
            try:
                await self._api("editMessageText", {
                    "chat_id": chat_id, "message_id": msg_id,
                    "text": msg, "parse_mode": "HTML",
                    "reply_markup": {"inline_keyboard": [[
                        {"text": "🏠 Menu principale", "callback_data": "menu_back"},
                        {"text": "🗑 Cancella",         "callback_data": "msg_delete"},
                    ]]},
                })
            except Exception:
                await self._send(chat_id, msg)
            return
        # ── Email callbacks ────────────────────────────────────────────────────
        if data == "__EMAIL_MENU__":
            await self._email_show_menu(chat_id)
            return

        if data == "__EMAIL_LIST__":
            await self._email_show_inbox(chat_id)
            return

        if data.startswith("__EMAIL_OPEN__:"):
            idx = int(data.split(":", 1)[1])
            await self._email_open(chat_id, idx)
            return

        if data.startswith("__EMAIL_DELETE__:"):
            idx = int(data.split(":", 1)[1])
            await self._email_delete(chat_id, idx)
            return

        if data.startswith("__EMAIL_REPLY__:"):
            idx = int(data.split(":", 1)[1])
            await self._email_start_reply(chat_id, idx)
            return

        if data == "__EMAIL_NEW__":
            await self._email_start_new(chat_id)
            return

        if data.startswith("__EMAIL_STYLE__:"):
            style = data.split(":", 1)[1]
            await self._email_set_style(chat_id, style)
            return

        if data == "__EMAIL_SEND_NOW__":
            await self._email_send_now(chat_id)
            return

        if data == "__EMAIL_SEND_SCHEDULE__":
            await self._email_ask_schedule(chat_id)
            return

        if data == "__EMAIL_DRAFT_REGEN__":
            await self._email_regen_draft(chat_id)
            return

        if data == "__EMAIL_ADD_ATTACH__":
            # Metti il wizard in modalità attesa allegato
            wz = self._email_wizard.get(chat_id, {})
            if wz:
                wz["step"] = "attach"
                self._email_wizard[chat_id] = wz
            await self._send(chat_id,
                "📎 <b>Invia il file da allegare:</b>\n"
                "• Foto → invia direttamente come foto o come file\n"
                "• PDF / Word / Excel → invia come documento\n\n"
                "<i>Puoi inviare più file uno alla volta.</i>")
            return

        if data == "__EMAIL_CLEAR_ATTACH__":
            wz = self._email_wizard.get(chat_id, {})
            if wz:
                wz.pop("attachments", None)
                self._email_wizard[chat_id] = wz
            await self._send(chat_id, "🗑️ Allegati rimossi.")
            return

        # ── Cambio stato allarme dai bottoni inline ───────────────────────
        if data.startswith("__ALARM_MODE__:"):
            target_state = data[len("__ALARM_MODE__:"):]
            # Mapping stato → servizio HA
            service_map = {
                "armed_away":     "alarm_arm_away",
                "armed_home":     "alarm_arm_home",
                "armed_night":    "alarm_arm_night",
                "armed_vacation": "alarm_arm_vacation",
                "disarmed":       "alarm_disarm",
            }
            service = service_map.get(target_state)
            if not service:
                await self._send(chat_id, "⚠️ Comando allarme non riconosciuto.")
                return
            # Trova il pannello allarme dalla cache
            if not self.state_cache_cb:
                await self._send(chat_id, "⚠️ Stato casa non disponibile.")
                return
            cache = self.state_cache_cb()
            alarm = next(
                (eid for eid in cache if eid.startswith("alarm_control_panel.")),
                None
            )
            if not alarm:
                await self._send(chat_id, "⚠️ Nessun pannello allarme trovato.")
                return
            # Strategia multi-fallback su REST + WebSocket
            # Alcuni pannelli custom (Alarmo, Manual) rifiutano REST ma accettano WS
            if not self._rest_client and not self._ws_client:
                await self._send(chat_id, "⚠️ Nessun client HA disponibile.")
                return

            code = (self._alarm_code or "").strip()
            attempts = []  # lista di (label, transport, data)
            if self._rest_client:
                if code:
                    attempts.append((f"REST con codice '{code}'", "rest",
                                     {"entity_id": alarm, "code": code}))
                attempts.append(("REST senza codice", "rest",
                                 {"entity_id": alarm}))
            if self._ws_client:
                if code:
                    attempts.append((f"WS con codice '{code}'", "ws",
                                     {"entity_id": alarm, "code": code}))
                attempts.append(("WS senza codice", "ws",
                                 {"entity_id": alarm}))

            last_error = None
            success = False
            for attempt_label, transport, svc_data in attempts:
                try:
                    if transport == "rest":
                        await self._rest_client.call_service(
                            "alarm_control_panel", service, svc_data
                        )
                    else:
                        result = await self._ws_client.call_service(
                            "alarm_control_panel", service, svc_data
                        )
                        if isinstance(result, dict) and result.get("success") is False:
                            raise RuntimeError(str(result.get("error", result))[:200])
                    success = True
                    logger.info("ALARM_MODE OK (%s): %s", attempt_label, service)
                    break
                except Exception as e:
                    last_error = e
                    logger.warning("ALARM_MODE %s failed: %s", attempt_label, str(e)[:200])
                    continue

            if success:
                state_icons = {
                    "armed_away":     "🔒 Armato (fuori)",
                    "armed_home":     "🏠 Armato (in casa)",
                    "armed_night":    "🌙 Armato (notte)",
                    "armed_vacation": "✈️ Armato (vacanza)",
                    "disarmed":       "🔓 Disarmato",
                }
                lbl = state_icons.get(target_state, target_state)
                await self._send(chat_id, f"✅ <b>Allarme → {lbl}</b>")
            else:
                # Nessun tentativo ha funzionato — messaggio dettagliato
                err_summary = str(last_error)[:250] if last_error else "errore sconosciuto"
                msg = (
                    f"⚠️ <b>Impossibile cambiare stato allarme</b>\n\n"
                    f"Pannello: <code>{alarm}</code>\n"
                    f"Servizio: <code>alarm_control_panel.{service}</code>\n\n"
                    f"Ultimo errore:\n<code>{_html_escape(err_summary)}</code>\n\n"
                    f"<i>Possibili cause:\n"
                    f"• Pannello personalizzato che richiede formato diverso\n"
                    f"• Entità non accessibile via REST API\n"
                    f"• Codice errato o obbligatorio non riconosciuto\n\n"
                    f"Verifica con il comando vocale o dall'app HA.</i>"
                )
                await self._send(chat_id, msg)
            return

        # ── dbfix: callback — gestione cicli DB (bypass message flow) ────────
        if data.startswith("dbfix:"):
            parts = data.split(":", 2)   # ["dbfix", action, payload]
            action  = parts[1] if len(parts) > 1 else ""
            payload = parts[2] if len(parts) > 2 else ""

            if not self._db:
                await self._send(chat_id, "❌ DB non disponibile.")
                return

            if action == "show":
                # Mostra cicli di un elettrodomestico specifico
                ap_name = payload
                cycles = self._db.get_cycles_for_fix(appliance=ap_name, limit=15)
                if not cycles:
                    await self._send(chat_id, f"🗄️ Nessun ciclo trovato per <b>{ap_name}</b>.")
                    return
                lines = [f"🗄️ <b>{ap_name} — cicli nel DB</b> (ultimi {len(cycles)})\n"]
                kb_rows = []
                for c in cycles:
                    cid  = c["id"]
                    st   = (c.get("start_time") or "?")[:16].replace("T", " ")
                    en   = (c.get("end_time")   or "")[:16].replace("T", " ") or "?"
                    dur  = c.get("duration_min", 0) or 0
                    dstr = f"{dur//60}h {dur%60}m" if dur >= 60 else f"{dur}m"
                    lines.append(f"• <code>#{cid}</code>  {st} → {en}  ({dstr})")
                    kb_rows.append([{
                        "text": f"🗑 Cancella #{cid}  ({dstr})",
                        "callback_data": f"dbfix:del:{cid}"
                    }])
                kb_rows.append([
                    {"text": f"🗑 Cancella TUTTI {ap_name}", "callback_data": f"dbfix:all:{ap_name}"},
                ])
                kb_rows.append([
                    {"text": "↩️ Torna lista", "callback_data": "menu_cmd:/db_fix"},
                    {"text": "🗑 Chiudi",       "callback_data": "msg_delete"},
                ])
                kb = {"inline_keyboard": kb_rows}
                await self._send_with_keyboard(chat_id, "\n".join(lines), kb)
                return

            if action == "del":
                # Cancella ciclo singolo per ID
                try:
                    cycle_id = int(payload)
                except ValueError:
                    await self._send(chat_id, "❌ ID ciclo non valido.")
                    return
                ok = self._db.delete_cycle_by_id(cycle_id)
                if ok:
                    await self._send(chat_id, f"✅ Ciclo <code>#{cycle_id}</code> cancellato.")
                else:
                    await self._send(chat_id, f"⚠️ Ciclo <code>#{cycle_id}</code> non trovato (già cancellato?).")
                return

            if action == "all":
                # Cancella tutti i cicli (payload vuoto = tutti, altrimenti filtro per nome)
                ap_name = payload.strip() or None
                deleted = self._db.delete_cycles_filter(appliance=ap_name)
                if ap_name:
                    await self._send(chat_id, f"✅ Cancellati <b>{deleted}</b> cicli di <b>{ap_name}</b> dal DB.")
                else:
                    await self._send(chat_id, f"✅ Cancellati <b>{deleted}</b> cicli totali dal DB.")
                return

            await self._send(chat_id, f"⚠️ Azione DB fix sconosciuta: {action}")
            return

        if data.startswith("menu_cmd:"):
            # Esegui il comando selezionato dal menu come se l'utente lo avesse scritto
            executed_cmd = data[len("menu_cmd:"):]
            try:
                chat_id_int = int(chat_id) if str(chat_id).lstrip("-").isdigit() else chat_id
                fake_update = {
                    "message": {
                        "chat": {"id": chat_id_int},
                        "text": executed_cmd,
                        "from": {"id": chat_id_int, "username": "menu"},
                    }
                }
                await self._handle_update(fake_update)
            except Exception as e:
                logger.warning("menu_cmd dispatch FAIL: %s", e)
                await self._send(chat_id, f"⚠️ Impossibile eseguire: scrivi <code>{executed_cmd}</code>")
            return

        # ── Cancellazione task singolo dalla lista ────────────────────────
        if data.startswith("task_del:"):
            try:
                n = int(data.split(":")[1])
                if self._task_scheduler:
                    task = self._task_scheduler.cancel_by_index(n)
                    if task:
                        await self._send(chat_id, f"✅ Task cancellato: <b>{task['label']}</b>")
                    else:
                        await self._send(chat_id, f"⚠️ Nessun task numero {n}.")
            except Exception as e:
                logger.warning("task_del FAIL: %s", e)
                await self._send(chat_id, "⚠️ Errore nella cancellazione.")
            return

        if data == "task_clear_all":
            if self._task_scheduler:
                self._task_scheduler.clear_all()
                await self._send(chat_id, "🗑 Tutti i task sono stati cancellati.")
            return

        # ── Cancellazione task ricorrente ─────────────────────────────────
        if data.startswith("rtask_del:"):
            try:
                n = int(data.split(":")[1])
                if self._recurring_task_scheduler:
                    task = self._recurring_task_scheduler.cancel_by_index(n)
                    if task:
                        await self._send(chat_id, f"✅ Task ricorrente cancellato: <b>{task['label']}</b>")
                    else:
                        await self._send(chat_id, f"⚠️ Nessun task ricorrente numero {n}.")
            except Exception as e:
                logger.warning("rtask_del FAIL: %s", e)
                await self._send(chat_id, "⚠️ Errore nella cancellazione.")
            return

        if data == "rtask_clear_all":
            if self._recurring_task_scheduler:
                self._recurring_task_scheduler._tasks = []
                self._recurring_task_scheduler._save()
                await self._send(chat_id, "🗑 Tutti i task ricorrenti sono stati cancellati.")
            return

        # ── Cancellazione task Alexa (lista unificata) ────────────────────
        if data.startswith("alxtask_del:"):
            try:
                n = int(data.split(":")[1])
                # Ricostruisci la lista unificata nello stesso ordine mostrato
                unified = []
                if self._task_scheduler:
                    for _tk in sorted(self._task_scheduler._tasks, key=lambda x: x["execute_at"]):
                        if _tk.get("command", "").startswith("__ALEXA_TTS__:"):
                            unified.append(("single", _tk))
                if self._recurring_task_scheduler:
                    for _tk in self._recurring_task_scheduler._sorted():
                        if _tk.get("command", "").startswith("__ALEXA_TTS__:"):
                            unified.append(("recurring", _tk))
                if n < 1 or n > len(unified):
                    await self._send(chat_id, f"⚠️ Nessun task Alexa numero {n}.")
                    return
                kind, task = unified[n - 1]
                if kind == "single":
                    self._task_scheduler.cancel_task(task["id"])
                else:
                    self._recurring_task_scheduler._tasks = [
                        x for x in self._recurring_task_scheduler._tasks if x["id"] != task["id"]
                    ]
                    self._recurring_task_scheduler._save()
                await self._send(chat_id, f"✅ Task Alexa cancellato: <b>{task['label']}</b>")
            except Exception as e:
                logger.warning("alxtask_del FAIL: %s", e)
                await self._send(chat_id, "⚠️ Errore nella cancellazione.")
            return

        # ── Gestione callback Alexa Task (selezione speaker) ──────────────
        if data.startswith("alexa_sp:") or data == "alexa_sp_done" or data == "alexa_sp_cancel":
            state = self._alexa_task_pending.get(chat_id)
            if not state:
                return
            if data == "alexa_sp_cancel":
                self._alexa_task_pending.pop(chat_id, None)
                self._alexa_speakers_cache.pop(chat_id, None)
                try:
                    await self._api("editMessageText", {
                        "chat_id": chat_id, "message_id": msg_id,
                        "text": "❌ <b>Creazione task Alexa annullata.</b>",
                        "parse_mode": "HTML",
                    })
                except Exception:
                    pass
                return
            if data == "alexa_sp_done":
                selected = state.get("speakers", [])
                if not selected:
                    await self._send(chat_id, "⚠️ Seleziona almeno uno speaker prima.")
                    return
                # Avanza al prossimo step: volume
                state["step"] = "volume"
                try:
                    await self._api("editMessageText", {
                        "chat_id": chat_id, "message_id": msg_id,
                        "text": f"📻 <b>Speaker selezionati:</b> {len(selected)}\n\n🔊 Ora scrivimi il volume (0-100):",
                        "parse_mode": "HTML",
                    })
                except Exception:
                    await self._send(chat_id, "🔊 Scrivimi il volume (0-100):")
                return
            # toggle speaker
            eid = data[len("alexa_sp:"):]
            sel = state.setdefault("speakers", [])
            if eid in sel:
                sel.remove(eid)
            else:
                sel.append(eid)
            # Ricostruisci tastiera con stato aggiornato
            try:
                kb = self._build_alexa_speaker_keyboard(chat_id)
                await self._api("editMessageReplyMarkup", {
                    "chat_id": chat_id, "message_id": msg_id,
                    "reply_markup": kb,
                })
            except Exception as _e:
                logger.debug("edit keyboard FAIL: %s", _e)
            return

    # ─────────────────────────────────────────────────────────────────────
    # Task Alexa — flusso creazione conversazionale
    # ─────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────
    # UI Interattiva — Menu principale a categorie
    # ─────────────────────────────────────────────────────────────────────

    def _categories_definition(self):
        """Definisce le categorie del menu principale e i comandi di ogni categoria."""
        return [
            ("tasks", "⏰ Task e promemoria", [
                ("/task", "📋 Lista task in coda"),
                ("/task_ripetuti", "🔁 Lista task ricorrenti"),
                ("/task_alexa", "🔊 Nuovo annuncio Alexa"),
                ("/task_alexa_ripetuto", "🔊🔁 Annuncio Alexa ricorrente"),
                ("/task_alexa_cancella", "🗑️ Lista/cancella task Alexa"),
            ]),
            ("status", "🏠 Stato casa", [
                ("/stato", "🏡 Stato generale della casa"),
                ("/allarme", "🔔 Stato allarme"),
                ("/briefing", "🎩 Briefing mattutino"),
                ("/elettrodomestici", "🫧 Stato elettrodomestici"),
                ("/routine", "🔄 Routine rilevate"),
                ("/routine reset", "♻️ Azzera routine"),
            ]),
            ("energy", "⚡ Energia e solare", [
                ("/energia", "📊 Consumi/produzione oggi"),
                ("/ieri", "📉 Energia di ieri"),
                ("/energia_analisi", "🔍 Analisi approfondita"),
                ("/solare", "☀️ Surplus FV"),
                ("/powerguard", "⚡ Power Guard"),
            ]),
            ("memory", "🧠 Memoria e alias", [
                ("/memoria", "💭 Cosa so su di te"),
                ("/alias", "🔗 I tuoi alias"),
                ("/dimentica", "🗑️ Reset conversazione AI"),
            ]),
            ("trash", "🗑️ Spazzatura", [
                ("/spazzatura", "🗑️ Calendario spazzatura"),
                ("/ricarica_spazzatura", "🔄 Ricarica calendario"),
            ]),
            ("system", "🛠️ Sistema", [
                ("/ai_mode", "🤖 Modalità AI (domotica/libera)"),
                ("/github",   "🔗 Installa da GitHub (addon/card/component)"),
                ("/agent",       "🤖 Agente autonomo (esegue task complessi)"),
                ("/task_agent",  "📅 Programma task agente"),
                ("/ssh",         "🔐 Terminale unificato (host SSH + container)"),
                ("/comandi_appresi", "📋 Comandi shell memorizzati"),
                ("/tools",       "🧰 Strumenti diretti (scrivi/leggi/ls/clona/cerca)"),
                ("/crea_sensore", "🛠️ Crea sensore/template"),
                ("/files_config", "📁 Tutti i file config HA"),
                ("/leggi_config", "📄 Leggi configuration.yaml"),
                ("/backups_config", "💾 Lista backup config"),
                ("/providers", "🧠 Stato provider AI"),
                ("/aggiornamenti", "🔄 Controlla aggiornamenti"),
                ("/riparazioni", "🛠️ Problemi HA"),
                ("/lingua", "🌐 Lingua"),
                ("/automazioni", "🏗️ Automazioni HA"),
                ("/crea_card", "🎨 Crea card Lovelace"),
                ("/config", "⚙️ Configurazione"),
            ]),
        ]

    async def _send_start_screen(self, chat_id: str):
        """Schermata di benvenuto con pulsanti cliccabili."""
        text = (
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎩 <b>HomeMind</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "Il tuo assistente per Home Assistant.\n\n"
            "Posso gestire allarme, luci, clima, energia, "
            "annunci vocali, promemoria e molto altro.\n\n"
            "<b>Scegli una categoria per iniziare:</b>"
        )
        await self._send_category_menu(chat_id, text)

    async def _send_main_menu(self, chat_id: str):
        """Menu /comandi — mostra tutte le categorie."""
        text = (
            "📋 <b>Menu comandi</b>\n\n"
            "Tocca una categoria per vedere i comandi disponibili.\n"
            "<i>Puoi anche scrivere direttamente il comando (es. /energia).</i>"
        )
        await self._send_category_menu(chat_id, text)

    async def _send_category_menu(self, chat_id: str, text: str):
        """Invia il messaggio con la tastiera delle categorie."""
        cats = self._categories_definition()
        rows = []
        # Due categorie per riga
        for i in range(0, len(cats), 2):
            row = []
            for cid, label, _ in cats[i:i+2]:
                row.append({"text": label, "callback_data": f"menu_cat:{cid}"})
            rows.append(row)
        await self._api("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": rows},
        })

    async def _show_category(self, chat_id: str, msg_id: int, cat_id: str):
        """Mostra i comandi di una categoria specifica (edit del messaggio)."""
        cats = self._categories_definition()
        cat = next((c for c in cats if c[0] == cat_id), None)
        if not cat:
            await self._send(chat_id, "⚠️ Categoria non trovata.")
            return
        _, label, commands = cat
        header = f"━━━━━━━━━━━━━━━━━━━\n<b>{label}</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
        lines = [header, "Tocca un comando per eseguirlo:\n"]
        rows = []
        for cmd, desc in commands:
            rows.append([{"text": desc, "callback_data": f"menu_cmd:{cmd}"}])
        rows.append([{"text": "◀️ Menu principale", "callback_data": "menu_back"}, {"text": "🗑 Cancella", "callback_data": "msg_delete"}])
        try:
            await self._api("editMessageText", {
                "chat_id": chat_id, "message_id": msg_id,
                "text": "".join(lines),
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": rows},
            })
        except Exception as e:
            logger.debug("editMessageText menu FAIL: %s", e)

    async def _show_main_menu_edit(self, chat_id: str, msg_id: int):
        """Edit del messaggio esistente per tornare al menu principale."""
        cats = self._categories_definition()
        text = (
            "📋 <b>Menu comandi</b>\n\n"
            "Tocca una categoria per vedere i comandi disponibili."
        )
        rows = []
        for i in range(0, len(cats), 2):
            row = []
            for cid, lbl, _ in cats[i:i+2]:
                row.append({"text": lbl, "callback_data": f"menu_cat:{cid}"})
            rows.append(row)
        try:
            await self._api("editMessageText", {
                "chat_id": chat_id, "message_id": msg_id,
                "text": text, "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": rows},
            })
        except Exception as e:
            # Edit fallito (es. messaggio contiene già quel testo, o troppo lungo)
            # Fallback: invia un nuovo messaggio menu
            logger.debug("editMessageText back FAIL: %s — fallback sendMessage", e)
            try:
                await self._api("sendMessage", {
                    "chat_id": chat_id,
                    "text": text, "parse_mode": "HTML",
                    "reply_markup": {"inline_keyboard": rows},
                })
            except Exception as e2:
                logger.warning("Menu back fallback FAIL: %s", e2)

    def _get_alexa_speakers(self) -> list:
        """Ritorna lista media_player TTS-capable dalla state_cache.
        Include sia Alexa Media Player (HACS) sia Alexa Devices (ufficiale).
        """
        if not self.state_cache_cb:
            return []
        cache = self.state_cache_cb() or {}
        try:
            from alexa_tts import list_alexa_capable_media_players
            return list_alexa_capable_media_players(cache)
        except Exception as e:
            logger.warning("alexa_tts import FAIL: %s — fallback legacy", e)
            out = []
            for eid, s in cache.items():
                if not eid.startswith("media_player."):
                    continue
                st = s.get("state", "unknown")
                if st in ("unavailable",):
                    continue
                name = s.get("attributes", {}).get("friendly_name", eid)
                out.append({"eid": eid, "name": name, "state": st, "is_alexa": True})
            out.sort(key=lambda x: x["name"].lower())
            return out

    def _build_alexa_speaker_keyboard(self, chat_id: str) -> dict:
        """Costruisce la tastiera inline con i checkbox per gli speaker."""
        state = self._alexa_task_pending.get(chat_id, {})
        selected = set(state.get("speakers", []))
        speakers = self._alexa_speakers_cache.get(chat_id, [])
        rows = []
        for sp in speakers:
            mark = "✅" if sp["eid"] in selected else "⬜"
            # Badge 🟢 per speaker riconosciuti come Alexa, 🔵 per altri media_player
            badge = "🟢" if sp.get("is_alexa") else "🔵"
            rows.append([{
                "text": f"{mark} {badge} {sp['name']}",
                "callback_data": f"alexa_sp:{sp['eid']}"
            }])
        rows.append([
            {"text": "✔️ Fatto", "callback_data": "alexa_sp_done"},
            {"text": "❌ Annulla", "callback_data": "alexa_sp_cancel"},
        ])
        return {"inline_keyboard": rows}

    async def _start_alexa_task(self, chat_id: str, is_recurring: bool = False):
        """Avvia il flusso creazione /task_alexa (o /task_alexa_ripetuto)."""
        self._alexa_task_pending[chat_id] = {
            "step": "message",
            "message": "",
            "when": "",
            "speakers": [],
            "volume": 0.5,
            "recurring": is_recurring,
        }
        label = "ricorrente" if is_recurring else "singolo"
        await self._send(chat_id,
            f"🔊 <b>Nuovo task Alexa {label}</b>\n\n"
            f"💬 Scrivimi il <b>messaggio</b> da riprodurre sugli speaker.\n\n"
            f"<i>Oppure scrivi /annulla per uscire.</i>")

    async def _handle_alexa_task_step(self, chat_id: str, text: str) -> bool:
        """Gestisce i passi successivi del wizard. Ritorna True se gestito."""
        state = self._alexa_task_pending.get(chat_id)
        if not state:
            return False
        if text.strip().lower() in ("/annulla", "annulla", "/cancel", "cancel"):
            self._alexa_task_pending.pop(chat_id, None)
            self._alexa_speakers_cache.pop(chat_id, None)
            await self._send(chat_id, "❌ Task Alexa annullato.")
            return True

        step = state.get("step")

        if step == "message":
            state["message"] = text.strip()
            state["step"] = "when"
            if state.get("recurring"):
                prompt = ("📅 <b>Quando deve ripetersi?</b>\n\n"
                          "Esempi:\n"
                          "  • <code>ogni giorno alle 19:00</code>\n"
                          "  • <code>ogni lunedì alle 8</code>\n"
                          "  • <code>ogni sera alle 22:30</code>")
            else:
                prompt = ("📅 <b>Quando?</b>\n\n"
                          "Esempi:\n"
                          "  • <code>oggi alle 16</code>\n"
                          "  • <code>domani alle 19</code>\n"
                          "  • <code>tra 2 ore</code>\n"
                          "  • <code>venerdì alle 20</code>")
            await self._send(chat_id, prompt)
            return True

        if step == "when":
            state["when"] = text.strip()
            # Valida il parsing del tempo
            if state.get("recurring"):
                if not self._recurring_task_scheduler:
                    self._alexa_task_pending.pop(chat_id, None)
                    await self._send(chat_id, "⚠️ Scheduler ricorrente non disponibile.")
                    return True
                tinfo = self._recurring_task_scheduler.parse_recurring_time(text.strip())
                if not tinfo:
                    await self._send(chat_id,
                        "⚠️ Non ho capito l'orario ricorrente. Riprova (es. <code>ogni giorno alle 19</code>):")
                    return True
                state["_tinfo"] = tinfo
            else:
                if not self._task_scheduler:
                    self._alexa_task_pending.pop(chat_id, None)
                    await self._send(chat_id, "⚠️ Scheduler non disponibile.")
                    return True
                ts = self._task_scheduler.parse_time(text.strip())
                if not ts:
                    await self._send(chat_id,
                        "⚠️ Non ho capito l'orario. Riprova (es. <code>oggi alle 16</code>):")
                    return True
                state["_ts"] = ts

            # Step successivo: mostra picker speaker
            speakers = self._get_alexa_speakers()
            if not speakers:
                self._alexa_task_pending.pop(chat_id, None)
                await self._send(chat_id,
                    "⚠️ Nessuno speaker Alexa disponibile. "
                    "Installa l'integrazione Alexa Media Player in Home Assistant.")
                return True
            self._alexa_speakers_cache[chat_id] = speakers
            state["step"] = "speakers"
            kb = self._build_alexa_speaker_keyboard(chat_id)
            await self._api("sendMessage", {
                "chat_id": chat_id,
                "text": ("📻 <b>Seleziona gli speaker</b>\n\n"
                         "Clicca su ognuno per aggiungerlo/rimuoverlo, poi premi <b>Fatto</b>."),
                "parse_mode": "HTML",
                "reply_markup": kb,
            })
            return True

        if step == "volume":
            # Parse volume 0-100
            try:
                val = int(''.join(ch for ch in text if ch.isdigit()))
                val = max(0, min(100, val))
            except Exception:
                await self._send(chat_id, "⚠️ Scrivi un numero da 0 a 100 (es. 60):")
                return True
            state["volume"] = val / 100.0
            # Crea il task
            await self._finalize_alexa_task(chat_id)
            return True

        return False

    async def _finalize_alexa_task(self, chat_id: str):
        """Crea il task Alexa (singolo o ricorrente) con i dati raccolti."""
        import json as _j
        state = self._alexa_task_pending.pop(chat_id, {})
        self._alexa_speakers_cache.pop(chat_id, None)
        message  = state.get("message", "")
        speakers = state.get("speakers", [])
        volume   = float(state.get("volume", 0.5))
        recurring = state.get("recurring", False)

        payload = _j.dumps({
            "message": message,
            "speakers": speakers,
            "volume": volume,
        }, ensure_ascii=False)
        command = "__ALEXA_TTS__:" + payload
        label_short = (message[:40] + "…") if len(message) > 40 else message
        label = f"🔊 {label_short}"

        if recurring:
            tinfo = state.get("_tinfo")
            if not tinfo or not self._recurring_task_scheduler:
                await self._send(chat_id, "⚠️ Errore: dati ricorrenza mancanti.")
                return
            h, m, dow = tinfo["hour"], tinfo["minute"], tinfo.get("day_of_week")
            self._recurring_task_scheduler.add_task(
                hour=h, minute=m, day_of_week=dow,
                label=label, command=command, chat_id=chat_id
            )
            sched = self._recurring_task_scheduler._dow_label(dow) + f" alle {h:02d}:{m:02d}"
            sp_names = []
            cache = self.state_cache_cb() if self.state_cache_cb else {}
            for sp in speakers:
                nm = cache.get(sp, {}).get("attributes", {}).get("friendly_name", sp)
                sp_names.append(nm)
            await self._send(chat_id,
                f"✅ <b>Task Alexa ricorrente creato</b>\n"
                f"💬 {message}\n"
                f"📅 {sched}\n"
                f"📻 {', '.join(sp_names)}\n"
                f"🔊 Volume: {int(volume*100)}%")
        else:
            ts = state.get("_ts")
            if not ts or not self._task_scheduler:
                await self._send(chat_id, "⚠️ Errore: orario mancante.")
                return
            from datetime import datetime as _dt
            self._task_scheduler.add_task(
                execute_at=ts, label=label, command=command, chat_id=chat_id
            )
            when_str = _dt.fromtimestamp(ts).strftime("%d/%m alle %H:%M")
            sp_names = []
            cache = self.state_cache_cb() if self.state_cache_cb else {}
            for sp in speakers:
                nm = cache.get(sp, {}).get("attributes", {}).get("friendly_name", sp)
                sp_names.append(nm)
            await self._send(chat_id,
                f"✅ <b>Task Alexa creato</b>\n"
                f"💬 {message}\n"
                f"📅 {when_str}\n"
                f"📻 {', '.join(sp_names)}\n"
                f"🔊 Volume: {int(volume*100)}%")

    async def ask_alarm_confirm(self, question: str, timeout: int = 300) -> bool:
        """
        Invia una domanda con bottoni Sì/No a tutti i chat autorizzati.
        Attende la risposta per max `timeout` secondi.
        Restituisce True se confermato, False se rifiutato o scaduto.
        """
        import asyncio as _aio

        if not self.allowed:
            logger.warning("ask_alarm_confirm: nessun chat autorizzato")
            return True  # fallback sicuro

        loop = _aio.get_event_loop()
        fut  = loop.create_future()

        # Registra il Future per ogni chat autorizzato
        for cid in self.allowed:
            self._pending_alarm_confirm[cid] = fut

        # Invia il messaggio con bottoni inline a tutti i chat autorizzati
        keyboard = {
            "inline_keyboard": [[
                {"text": "✅ Sì, attiva antifurto", "callback_data": "alarm_confirm"},
                {"text": "❌ No, lascia disarmato",  "callback_data": "alarm_reject"},
            ]]
        }
        for cid in self.allowed:
            try:
                await self._api("sendMessage", {
                    "chat_id":      cid,
                    "text":         question,
                    "parse_mode":   "HTML",
                    "reply_markup": keyboard,
                    "disable_web_page_preview": True,
                })
            except Exception as e:
                logger.warning("ask_alarm_confirm send FAIL (chat %s): %s", cid, e)

        # Attendi risposta o timeout
        try:
            result = await _aio.wait_for(fut, timeout=timeout)
            logger.info("ask_alarm_confirm: risposta ricevuta → %s", result)
            return result
        except _aio.TimeoutError:
            logger.info("ask_alarm_confirm: timeout (%ds) — considero come rifiuto", timeout)
            self._pending_alarm_confirm.clear()
            # Notifica il timeout
            for cid in self.allowed:
                try:
                    await self._api("sendMessage", {
                        "chat_id":    cid,
                        "text":       "⏱️ <b>Nessuna risposta ricevuta</b> — antifurto NON attivato (timeout).",
                        "parse_mode": "HTML",
                    })
                except Exception:
                    pass
            return False

    async def _ai_reply(self, chat_id, user_msg):
        # ── Intercetta automazioni con regex flessibile ─────────────────
        msg_low = user_msg.lower().strip()

        def _is_create(t):
            return bool(re.match(r"^(crea|nuova|aggiungi|create|fai)\s+automazion[ei]", t, re.IGNORECASE))
        def _is_modify(t):
            return bool(re.match(r"^(modifica|cambia|aggiorna|edit)\s+automazion[ei]", t, re.IGNORECASE))
        def _is_delete(t):
            return bool(re.match(r"^/?(elimina|cancella|rimuovi|delete|remove)\s+automazion[ei]", t, re.IGNORECASE))
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
            body = re.sub(r"^/?(elimina|cancella|rimuovi|delete|remove)\s+automazion[ei]\s*",
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

        # ── CONSUMI PER FASCIA ORARIA ──────────────────────────────────────
        # Intercetta PRIMA dell'AI: "fascia oraria", "fasce orarie", "consumi a fascia"
        _fascia_kw = (
            "fascia oraria", "fasce orarie", "fasce orarie", "consumi a fascia",
            "consumo a fascia", "consumi per fascia", "consumo per fascia",
            "quanta energia fascia", "energia per fascia", "di questo mese fascia",
        )
        _fascia_hit = any(k in msg_low for k in _fascia_kw)
        # Anche "di questo mese" / "N giorni" / "oggi" se arriva da contesto fascia
        if not _fascia_hit:
            # Rileva "dimmi consumi a fascia orario oggi/N giorni/mese..."
            import re as _fre
            _fascia_hit = bool(_fre.search(
                r'(consumi?|energia|kwh|fascia).{0,30}(fascia|orari[ao]|f1|f2|f3)|'
                r'(fascia|orari[ao]).{0,30}(consumi?|energia|kwh)',
                msg_low
            ))
        if _fascia_hit and self.history_client:
            await self._typing(chat_id)
            # Estrai il periodo dalla richiesta
            import re as _fre2
            _per = msg_low
            # Determina person_name dal config
            _pname_display = "Agostino"
            try:
                import json as _pjson
                from pathlib import Path as _PPath
                _pcfg = _PPath("/config/homemind_patches/person_config.json")
                if _pcfg.exists():
                    _pd = _pjson.loads(_pcfg.read_text(encoding="utf-8-sig"))
                    _wl = [e for e in _pd.get("person_whitelist", [])
                           if isinstance(e, str) and e.startswith("person.") and "_comment" not in e]
                    if _wl:
                        _pname_display = _wl[0].split(".")[-1].capitalize()
            except Exception:
                pass
            result = await self.history_client.energy_by_fascia(period=_per, person_name=_pname_display)
            await self._send(chat_id, result + "\n" + self._ai_footer())
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
                # Data specifica ("il 5 ottobre", "5/10", "ieri"): finestra 00:00–24:00 di quel giorno
                _day, _day_label = None, None
                try:
                    from datetime import date as _dt_date, datetime as _dt_dt, timedelta as _dt_td
                    from utils.timezone_helper import now_local as _nl_loc
                    _now_l = _nl_loc()
                    _today = _now_l.date()
                    _MESI = ["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio",
                             "agosto","settembre","ottobre","novembre","dicembre"]
                    _dm = _re.search(r"\b(\d{1,2})\s*(" + "|".join(_MESI) + r")\s*(\d{4})?", msg_low)
                    _dn = (_re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", msg_low)
                           or _re.search(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b", msg_low))
                    _d = _m = _y = None
                    if _dm:
                        _d, _m, _y = int(_dm.group(1)), _MESI.index(_dm.group(2)) + 1, _dm.group(3)
                    elif _dn:
                        _d, _m, _y = int(_dn.group(1)), int(_dn.group(2)), _dn.group(3)
                    if _d is not None:
                        _yy = int(_y) + (2000 if _y and len(_y) == 2 else 0) if _y else _today.year
                        _cand = _dt_date(_yy, _m, _d)           # ValueError se data impossibile
                        if not _y and _cand > _today:           # senza anno e nel futuro → anno scorso
                            _cand = _dt_date(_yy - 1, _m, _d)
                        _day = _cand
                    elif any(k in msg_low for k in ["ieri", "yesterday"]):
                        _day = _today - _dt_td(days=1)
                    if _day is not None:
                        _day_label = f"{_day.day} {_MESI[_day.month - 1]}" + (f" {_day.year}" if _day.year != _today.year else "")
                        if _day == _today - _dt_td(days=1) and not (_dm or _dn):
                            _day_label = "ieri, " + _day_label
                except (ValueError, TypeError):
                    _day = None   # data non valida: ignora e usa il comportamento classico

                if _day is not None and _day > _today:
                    await self._send(chat_id, f"📅 {_day_label} è una data futura: non ho ancora nessuna posizione.")
                    return
                if _day is not None and (_today - _day).days > 30:
                    await self._send(chat_id, f"📅 Posso risalire al massimo a 30 giorni fa: {_day_label} è troppo indietro.")
                    return

                if _day is not None:
                    _d0 = _dt_dt.combine(_day, _dt_dt.min.time(), tzinfo=_now_l.tzinfo)
                    _hours = max(1, min(int((_now_l - _d0).total_seconds() // 3600) + 2, 720))
                elif _hours_match:
                    _hours = max(1, min(int(_hours_match.group(1)), 168))  # 1h min, 7gg max
                elif any(k in msg_low for k in ["settimana","week","7 giorni"]):
                    _hours = 168
                else:
                    _hours = 24
                # "tutti i posti" / "anche le soste brevi" → soglia più bassa
                _min_stop = 3 if _re.search(r"\btutt[ei]\b|\banche\s+(?:le\s+)?brev[ei]\b", msg_low) else 10
                _stops = await get_person_stops(
                    self._rest_client,
                    _pname, hours=_hours, min_stop_min=_min_stop, day=_day
                )
                await self._send(chat_id, format_stops_message(
                    _stops, _pname.capitalize(), _hours, _min_stop, period_label=_day_label
                ))
            except Exception as _e:
                logger.warning("location_tracker error: %s", _e)
                await self._send(chat_id, f"⚠️ Errore: {_e}")
            return

        # ── TARGHE (Frigate LPR) — risposta diretta, senza AI ──────────────────────
        # Si attiva solo se Frigate è configurato e il messaggio parla di targhe
        # (e non è una richiesta di modifica config). Altrimenti passa all'AI come prima.
        try:
            if self._is_plates_query(msg_low):
                if await self._handle_plates_query(chat_id, user_msg, msg_low):
                    return
        except Exception as _pe:
            logger.warning("plates query error: %s", _pe)

        # ── RILEVAMENTI FRIGATE (persone, cani, gatti, auto, pacchi...) ────────────
        # Solo se Frigate è pronto e il messaggio parla di rilevamenti/oggetti
        # (le frasi tipo "chi è a casa" NON vengono intercettate → vanno all'AI).
        try:
            if self._is_detection_query(msg_low):
                if await self._handle_detection_query(chat_id, user_msg, msg_low):
                    return
        except Exception as _de:
            logger.warning("detection query error: %s", _de)

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
                # ── Se l'utente ha scelto modalità Libera → prompt differente ──
                if self._ai_mode.get(chat_id) == "libera":
                    sys_prompt = (
                        "Sei un'AI amichevole e disponibile. "
                        "Rispondi a qualsiasi domanda generica (ricette, codice, curiosità, consigli, idee). "
                        "NON hai accesso al controllo della casa in questa modalità. "
                        "Se l'utente chiede di controllare luci, sensori, allarme, energia o domotica, "
                        "ricordagli che deve tornare alla modalità Domotica con /ai_domotica.\n"
                        + _lang_instruction + "\n"
                        "Rispondi in modo chiaro e conciso."
                    )
                    reply = await self.ai_cb(sys_prompt, user_msg, ai_history)
                    mem.append(("user",      user_msg, _now))
                    mem.append(("assistant", reply,    _now))
                    mem = mem[-(_MAX_TURNS * 2):]
                    self._conv_memory[chat_id] = mem
                    await self._send(chat_id, "💬 " + reply)
                    return
                sys_prompt = (
                    "Sei HomeMind, assistente AI per la domotica.\n"
                    + _lang_instruction + "\n"
                    + _mem_note
                    + (_memory_block + "\n" if _memory_block else "")
                    # Le regole vengono iniettate automaticamente dal wrapper _make_rules_ai_cb
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
                    "Formato: [GET_HISTORY:entity_id:ore] oppure [GET_HISTORY:entity_id:ore:text] per testuale / [GET_HISTORY:entity_id:ore:chart] per grafico.\n"
                    "Se utente dice 'testuale' usa :text — se dice 'grafico' usa :chart — altrimenti ometti il formato.\n"
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
                # ── Fallback al parser locale ──────────────────────────────
                # Tutti i provider AI hanno fallito → prova a gestire il comando localmente
                if self._local_parser:
                    try:
                        local_result = await self._local_parser.handle(user_msg)
                        if local_result:
                            logger.info("LocalParser: gestito localmente '%s'", user_msg[:40])
                            await self._send(chat_id, local_result)
                            return
                    except Exception as _le:
                        logger.debug("LocalParser error: %s", _le)
                # Parser locale non ha gestito il comando
                await self._send(chat_id,
                    "⚠️ <b>AI non disponibile</b> (tutti i provider offline)\n\n"
                    "Puoi ancora usare i comandi diretti:\n"
                    "  💡 <code>accendi/spegni luce [stanza]</code>\n"
                    "  🪟 <code>apri/chiudi tapparelle [stanza]</code>\n"
                    "  🏠 <code>stato casa</code>\n"
                    "  🔒 <code>arma/disarma allarme</code>\n"
                    "  🔗 I tuoi alias funzionano sempre\n\n"
                    f"<i>Errore: {str(e)[:100]}</i>"
                )


    # ── Targhe rilevate da Frigate (LPR) ────────────────────────────────────
    _PLATE_KW_RE = re.compile(r"\b(targ[ah]e?|targhe|license\s*plates?|plates?|lpr)\b", re.IGNORECASE)
    _PLATE_EDIT_RE = re.compile(
        r"\b(aggiungi|modifica|crea|imposta|configura|elimina|cancella|rimuovi|"
        r"abilita|disabilita|attiva|disattiva|installa|add|edit|create|delete|remove|enable|disable)\b",
        re.IGNORECASE)

    def _is_plates_query(self, msg_low: str) -> bool:
        """True se il messaggio chiede di targhe E Frigate è pronto."""
        fc = getattr(self, "_frigate_client", None)
        if not fc or not fc.is_ready():
            return False
        if msg_low.startswith("/"):
            return False
        if not self._PLATE_KW_RE.search(msg_low):
            return False
        if self._PLATE_EDIT_RE.search(msg_low):
            return False
        return True

    async def _handle_plates_query(self, chat_id: str, user_msg: str, msg_low: str) -> bool:
        """Risponde con le targhe rilevate da Frigate. Restituisce True se ha risposto."""
        import html as _html
        from datetime import timedelta
        from utils.timezone_helper import local_tz, now_local

        fc = self._frigate_client
        await self._typing(chat_id)

        # ── Periodo richiesto ──────────────────────────────────────────────
        now = now_local()
        after_ts, until_ts, label = self._parse_detection_period(msg_low, now)

        # ── Filtro camera (se citata) e targa specifica (se citata) ─────────
        camera = None
        for cam in fc.all_cameras():
            if re.search(r"\b" + re.escape(cam.lower()) + r"\b", msg_low):
                camera = cam
                break

        wanted = None
        m_it = re.search(r"\b([A-Za-z]{2})\s?(\d{3})\s?([A-Za-z]{2})\b", user_msg)
        if m_it:
            wanted = (m_it.group(1) + m_it.group(2) + m_it.group(3)).upper()
        else:
            m_g = re.search(r"targa\s+([A-Za-z0-9]{5,8})\b", user_msg, re.IGNORECASE)
            if m_g and re.search(r"\d", m_g.group(1)) and re.search(r"[A-Za-z]", m_g.group(1)):
                wanted = m_g.group(1).upper()

        limit = 300 if (now.timestamp() - after_ts) <= 2 * 86400 else 1000
        plates = await fc.get_recent_plates(after_ts=after_ts, camera=camera, limit=limit)
        if plates is None:
            await self._send(chat_id,
                "⚠️ <b>Frigate non raggiungibile</b>: non riesco a leggere le targhe in questo momento.")
            return True

        if until_ts is not None:
            plates = [p for p in plates if p["time"] < until_ts]
        if wanted:
            plates = [p for p in plates if p["plate"].replace(" ", "") == wanted]

        scope = f" — camera <b>{_html.escape(camera)}</b>" if camera else ""

        if not plates:
            if wanted:
                txt = (f"🔎 La targa <b>{_html.escape(wanted)}</b> non risulta rilevata "
                       f"({label}){scope}.")
            else:
                txt = (f"🚗 Nessuna targa rilevata ({label}){scope}.\n"
                       f"<i>Se ti aspettavi delle targhe, verifica che il riconoscimento targhe (LPR) "
                       f"sia attivo in Frigate sulla camera.</i>")
            await self._send(chat_id, txt)
            return True

        tz = local_tz()

        def _fmt(ts: float) -> str:
            d = datetime.fromtimestamp(ts, tz)
            if d.date() == now.date():
                return f"oggi {d:%H:%M}"
            if d.date() == (now - timedelta(days=1)).date():
                return f"ieri {d:%H:%M}"
            return f"{d:%d/%m %H:%M}"

        # Raggruppa per targa (già ordinate dalla più recente)
        groups: dict = {}
        for p in plates:
            g = groups.setdefault(p["plate"], {
                "count": 0, "last": p["time"], "first": p["time"],
                "cams": [], "best": None, "known": None,
            })
            g["count"] += 1
            g["first"] = min(g["first"], p["time"])
            if p["camera"] not in g["cams"]:
                g["cams"].append(p["camera"])
            if p["score"] is not None and (g["best"] is None or p["score"] > g["best"]):
                g["best"] = p["score"]
            if p.get("known_name") and not g["known"]:
                g["known"] = p["known_name"]

        ordered = sorted(groups.items(), key=lambda kv: kv[1]["last"], reverse=True)
        lines = [f"🚗 <b>Targhe rilevate</b> — {label}{scope}",
                 f"<i>{len(ordered)} {'targa diversa' if len(ordered) == 1 else 'targhe diverse'}, "
                 f"{len(plates)} {'rilevamento' if len(plates) == 1 else 'rilevamenti'}</i>\n"]
        for plate, g in ordered[:15]:
            known = f" · 👤 {_html.escape(g['known'])}" if g["known"] else ""
            conf = f" · ~{int(round(g['best'] * 100))}%" if g["best"] is not None else ""
            cams = ", ".join(_html.escape(c) for c in g["cams"])
            times = f"ultima {_fmt(g['last'])}"
            if g["count"] > 1:
                times = f"{g['count']}× · prima {_fmt(g['first'])} · ultima {_fmt(g['last'])}"
            lines.append(f"• <code>{_html.escape(plate)}</code>{known}\n   📍 {cams} · {times}{conf}")
        if len(ordered) > 15:
            lines.append(f"\n…e altre {len(ordered) - 15} targhe")
        await self._send(chat_id, "\n".join(lines))

        # Foto dell'ultimo rilevamento (best effort: se fallisce, la lista è già inviata)
        try:
            last = plates[0]
            if last.get("event_id"):
                img = await fc.get_event_snapshot(last["event_id"])
                if img:
                    await self.send_photo(
                        chat_id, img,
                        f"📷 Ultima: {last['plate']} — {last['camera']} ({_fmt(last['time'])})")
        except Exception as _se:
            logger.debug("plates snapshot error: %s", _se)
        return True

    # ── Rilevamenti oggetti Frigate (persone, animali, veicoli, pacchi) ──────
    # etichetta Frigate → (emoji, singolare, plurale, regex parole chiave)
    _DET_OBJECTS = {
        "person":     ("👤", "persona",   "persone",
                       r"\b(person[ae]|gente|qualcuno|people|persons?|uomo|uomini|donn[ae]|ladri|ladro|intrus[oi])\b"),
        "dog":        ("🐕", "cane",      "cani",   r"\b(can[ei]|dogs?|animal[ei]|animals?)\b"),
        "cat":        ("🐈", "gatto",     "gatti",  r"\b(gatt[oi]|cats?|animal[ei]|animals?)\b"),
        "car":        ("🚗", "auto",      "auto",   r"\b(auto|macchin[ae]|veicol[oi]|cars?|vehicles?)\b"),
        "motorcycle": ("🏍️", "moto",      "moto",   r"\b(moto|motorini?|scooter|motorcycles?)\b"),
        "bicycle":    ("🚲", "bici",      "bici",   r"\b(bici|biciclett[ae]|bicycles?)\b"),
        "package":    ("📦", "pacco",     "pacchi", r"\b(pacc[oh]i?|packages?|corriere)\b"),
        "bird":       ("🐦", "uccello",   "uccelli", r"\b(uccell[oi]|birds?|animal[ei]|animals?)\b"),
    }
    _DET_GENERIC_RE = re.compile(
        r"(cosa|che cosa|chi)\s+(hai|ha|hanno)?\s*(rilevat|visto|ripres)|"
        r"\b(chi|cosa)\s+(è|e|era|sono)\s+(passat|entrat|stat)|"
        r"\brilevament[io]\b|\bdetections?\b", re.IGNORECASE)
    _DET_CONTEXT_RE = re.compile(
        r"(rilevat|rilevament|\bvist[oaie]\b|passat|ripres|telecamer|videocamer|frigate|"
        r"detect|sono entrat|è entrat|e entrat|ha attraversat)", re.IGNORECASE)
    # frasi che parlano di presenza in casa (gestite dall'AI/contesto, NON da Frigate)
    _DET_HOME_RE = re.compile(r"\b(a|in|di)\s+casa\b|\bpresent[ei]\b|\bhome\b|\bwhitelist\b|\bblacklist\b", re.IGNORECASE)

    def _detection_labels(self, msg_low: str) -> list:
        """Etichette Frigate citate nel messaggio (es. ['person','dog'])."""
        return [lab for lab, (_e, _s, _p, rx) in self._DET_OBJECTS.items()
                if re.search(rx, msg_low, re.IGNORECASE)]

    # espressione di periodo ("ultima ora", "ultimi 30 minuti", "oggi", "ieri"...)
    _DET_PERIOD_RE = re.compile(
        r"(ultim[aeio]\s+(?:ora|ore|minut\w*|giorn\w*|settiman\w*|mese|\d+|un\b|una\b|due|tre|mezz|quarto)|"
        r"\b\d+\s*(?:h|ore|ora|min|minuti|giorni|giorno)\b|"
        r"\b(?:un|una|due|tre|quattro|cinque|sei|dieci)['’]?\s*(?:ora|ore|minuti|giorni)\b|"
        r"mezz.?\s*ora|quarto\s+d.?\s*ora|\boggi\b|\bieri\b|\bstanotte\b|last\s+hour)", re.IGNORECASE)
    # oggetti per cui "oggetto + periodo" basta a intendere i rilevamenti Frigate
    # (auto/moto/bici esclusi: "ricarica auto oggi" non è una richiesta a Frigate)
    _DET_PERIOD_OK = {"person", "dog", "cat", "bird", "package"}
    _DET_ANIMALS   = {"dog", "cat", "bird"}
    _DET_ACTION_RE = re.compile(r"\b(accendi|spegni|apri|chiudi|arma|disarma|imposta|metti|alza|abbassa)\b", re.IGNORECASE)

    def _is_detection_query(self, msg_low: str) -> bool:
        fc = getattr(self, "_frigate_client", None)
        if not fc or not fc.is_ready():
            return False
        if msg_low.startswith("/"):
            return False
        if self._PLATE_EDIT_RE.search(msg_low):
            return False
        if self._DET_GENERIC_RE.search(msg_low):
            return True
        if self._DET_HOME_RE.search(msg_low):
            return False
        labels = self._detection_labels(msg_low)
        if not labels:
            return False
        if self._DET_CONTEXT_RE.search(msg_low):
            return True
        # "persone ultima ora", "cani oggi": oggetto affidabile + periodo
        if self._DET_PERIOD_RE.search(msg_low) and any(l in self._DET_PERIOD_OK for l in labels):
            return True
        # messaggio brevissimo solo sugli animali ("animali", "cani ieri"): rilevamenti Frigate
        if (set(labels) <= self._DET_ANIMALS and len(msg_low.split()) <= 4
                and not self._DET_ACTION_RE.search(msg_low)):
            return True
        return False

    @staticmethod
    def _parse_detection_period(msg_low: str, now):
        """(after_ts, until_ts|None, etichetta) dal testo. Default: ultime 24 ore.
        Capisce: 'ultima ora', 'ultimi 30 minuti', 'mezz'ora', 'quarto d'ora',
        'ultime 2/due ore', 'ultimi 3 giorni', 'ieri', 'oggi', 'settimana', 'mese'."""
        from datetime import timedelta
        W = {"un": 1, "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5,
             "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10, "dodici": 12}
        NUM = r"(\d+|un|uno|una|due|tre|quattro|cinque|sei|sette|otto|nove|dieci|dodici)"

        def _n(tok):
            return int(tok) if tok.isdigit() else W.get(tok, 1)

        t_now = now.timestamp()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # minuti
        m = re.search(r"\b" + NUM + r"\s*(?:min\b|minut[oi]\b|minutes?\b)", msg_low)
        if m:
            n = max(1, min(_n(m.group(1)), 24 * 60))
            return t_now - n * 60, None, ("ultimo minuto" if n == 1 else f"ultimi {n} minuti")
        if re.search(r"\b(?:ultimo|last)\s+minut[oi]?\b|\bminuto\s+scorso\b", msg_low):
            return t_now - 60, None, "ultimo minuto"
        if re.search(r"quarto\s+d.?\s*ora", msg_low):
            return t_now - 15 * 60, None, "ultimi 15 minuti"
        if re.search(r"mezz.?\s*ora|mezza\s+ora|half\s+an?\s+hour", msg_low):
            return t_now - 30 * 60, None, "ultimi 30 minuti"
        # ore (cifra o parola) e "ultima ora"
        m = re.search(r"\b" + NUM + r"['’]?\s*(?:h\b|ore\b|ora\b|hours?\b)", msg_low)
        if m:
            n = max(1, min(_n(m.group(1)), 24 * 30))
            return t_now - n * 3600, None, ("ultima ora" if n == 1 else f"ultime {n} ore")
        if re.search(r"\b(?:ultima|ultimo|last)\s+ora\b|\bora\s+scorsa\b|\blast\s+hour\b", msg_low):
            return t_now - 3600, None, "ultima ora"
        # giorni
        m = re.search(r"\b" + NUM + r"\s*(?:giorni|giorno|days?)\b", msg_low)
        if m:
            n = max(1, min(_n(m.group(1)), 30))
            return t_now - n * 86400, None, ("ultime 24 ore" if n == 1 else f"ultimi {n} giorni")
        if "ieri" in msg_low or "yesterday" in msg_low:
            return (midnight - timedelta(days=1)).timestamp(), midnight.timestamp(), "ieri"
        if "settimana" in msg_low or "week" in msg_low:
            return t_now - 7 * 86400, None, "ultimi 7 giorni"
        if "mese" in msg_low or "month" in msg_low:
            return t_now - 30 * 86400, None, "ultimi 30 giorni"
        if "oggi" in msg_low or "today" in msg_low:
            return midnight.timestamp(), None, "oggi"
        return t_now - 24 * 3600, None, "ultime 24 ore"

    async def _handle_detection_query(self, chat_id: str, user_msg: str, msg_low: str) -> bool:
        """Elenca i rilevamenti Frigate per tipo di oggetto. True se ha risposto."""
        import html as _html
        from datetime import timedelta
        from utils.timezone_helper import local_tz, now_local

        fc = self._frigate_client
        await self._typing(chat_id)

        now = now_local()
        after_ts, until_ts, label = self._parse_detection_period(msg_low, now)
        labels = self._detection_labels(msg_low)          # [] = tutti gli oggetti

        camera = None
        for cam in fc.all_cameras():
            cl = re.escape(cam.lower())
            # Se il nome camera coincide con una parola-oggetto (es. camera "auto"),
            # lo consideriamo camera solo se introdotto da "camera/dalla/sul/nel..."
            if any(re.search(rx, cam.lower(), re.IGNORECASE)
                   for (_e, _s, _p, rx) in self._DET_OBJECTS.values()):
                pat = (r"\b(camera|cam|telecamera|videocamera|dalla|dal|della|sulla|sul|nella|nel)\s+"
                       + cl + r"\b")
            else:
                pat = r"\b" + cl + r"\b"
            if re.search(pat, msg_low):
                camera = cam
                break

        limit = 300 if (now.timestamp() - after_ts) <= 2 * 86400 else 1000
        dets = await fc.get_recent_detections(labels=labels or None, camera=camera,
                                              after_ts=after_ts, limit=limit)
        if dets is None:
            await self._send(chat_id,
                "⚠️ <b>Frigate non raggiungibile</b>: non riesco a leggere i rilevamenti in questo momento.")
            return True
        if until_ts is not None:
            dets = [d for d in dets if d["time"] < until_ts]

        def _meta(lab):
            if lab in self._DET_OBJECTS:
                e, s_, p_, _ = self._DET_OBJECTS[lab]
                return e, s_, p_
            return "🔹", lab, lab

        what = ", ".join(_meta(l)[2] for l in labels) if labels else "oggetti"
        scope = f" — camera <b>{_html.escape(camera)}</b>" if camera else ""

        if not dets:
            await self._send(chat_id,
                f"🔎 Nessun rilevamento di <b>{_html.escape(what)}</b> ({label}){scope}.\n"
                f"<i>Frigate registra solo gli oggetti tracciati nella sua configurazione "
                f"(objects → track).</i>")
            return True

        tz = local_tz()

        def _fmt(ts: float) -> str:
            d = datetime.fromtimestamp(ts, tz)
            if d.date() == now.date():
                return f"oggi {d:%H:%M}"
            if d.date() == (now - timedelta(days=1)).date():
                return f"ieri {d:%H:%M}"
            return f"{d:%d/%m %H:%M}"

        # Riepilogo per tipo di oggetto (già ordinati dal più recente)
        by_label: dict = {}
        for d in dets:
            g = by_label.setdefault(d["label"], {"n": 0, "cams": {}})
            g["n"] += 1
            g["cams"][d["camera"]] = g["cams"].get(d["camera"], 0) + 1

        lines = [f"🎥 <b>Rilevamenti Frigate</b> — {label}{scope}", ""]
        for lab, g in sorted(by_label.items(), key=lambda kv: kv[1]["n"], reverse=True):
            e, _s, p_ = _meta(lab)
            cams = ", ".join(f"{_html.escape(str(c))} {n}" for c, n in
                             sorted(g["cams"].items(), key=lambda kv: kv[1], reverse=True))
            lines.append(f"{e} <b>{_html.escape(p_.capitalize())}</b>: {g['n']}  <i>({cams})</i>")

        MAX_EV = 10
        lines.append("\n<b>Ultimi rilevamenti</b>")
        for d in dets[:MAX_EV]:
            e, s_, _p = _meta(d["label"])
            name = f" · {_html.escape(d['name'])}" if d["name"] else ""
            conf = f" · ~{int(round(d['score'] * 100))}%" if d["score"] is not None else ""
            lines.append(f"• {e} {_html.escape(s_.capitalize())}{name} · "
                         f"📍 {_html.escape(str(d['camera']))} · {_fmt(d['time'])}{conf}")
        if len(dets) > MAX_EV:
            lines.append(f"…e altri {len(dets) - MAX_EV} rilevamenti")
        await self._send(chat_id, "\n".join(lines))

        # Foto di TUTTI i rilevamenti con snapshot, in album da 10 (best effort:
        # se qualcosa fallisce la lista testuale è già stata inviata).
        try:
            MAX_PHOTOS = 40   # tetto di sicurezza (anti-flood Telegram)
            with_snap = [d for d in dets if d.get("event_id") and d.get("has_snapshot") is not False]
            chosen = with_snap[:MAX_PHOTOS]
            if chosen:
                sem = asyncio.Semaphore(5)

                async def _grab(d):
                    async with sem:
                        return d, await fc.get_event_snapshot(d["event_id"])

                got = await asyncio.gather(*[_grab(d) for d in chosen], return_exceptions=True)
                items = []
                for r in got:
                    if isinstance(r, Exception) or not r[1]:
                        continue
                    d, img = r
                    e, s_, _p = _meta(d["label"])
                    nm = f" · {d['name']}" if d["name"] else ""
                    cf = f" · ~{int(round(d['score'] * 100))}%" if d["score"] is not None else ""
                    items.append((img, f"{e} {s_.capitalize()}{nm} · {d['camera']} · {_fmt(d['time'])}{cf}"))
                for k in range(0, len(items), 10):
                    await self.send_media_group(chat_id, items[k:k + 10])
                    if k + 10 < len(items):
                        await asyncio.sleep(2)   # rispetta i limiti di Telegram
                if len(with_snap) > MAX_PHOTOS:
                    await self._send(chat_id,
                        f"📷 Inviate le ultime {MAX_PHOTOS} foto su {len(with_snap)} disponibili.")
        except Exception as _se:
            logger.warning("detection snapshots error: %s", _se)
        return True

    # ── Salva i file ricevuti in una cartella (agent/file_inbox.py) ──────────
    def _fi_state(self) -> dict:
        st = getattr(self, "_fi_st", None)
        if st is None:
            st = {"groups": {}, "pending": {}, "gpend": {}, "sums": {}, "locks": {}}
            self._fi_st = st
        return st

    def _fi_purge(self, st: dict):
        import time as _t
        now = _t.time()
        for k in [k for k, v in st["groups"].items() if now - v["ts"] > 600]:
            st["groups"].pop(k, None)
        for k in [k for k, v in st["pending"].items() if now - v["ts"] > 3600]:
            st["gpend"].pop(st["pending"][k].get("gkey"), None)
            st["pending"].pop(k, None)
        for k in [k for k, v in st["sums"].items() if now - v["ts"] > 600]:
            st["sums"].pop(k, None)
            st["locks"].pop(k, None)

    async def _file_inbox_handle(self, chat_id: str, msg: dict) -> bool:
        """Gestisce un messaggio con file. True = gestito (il flusso normale si ferma)."""
        from agent import file_inbox as fi
        import time as _t, uuid as _uuid

        media = fi.extract_media(msg)
        if not media:
            return False
        if self.allowed and chat_id not in self.allowed:
            return False                                   # la gestione standard rifiuta
        if (getattr(self, "_email_wizard", None) or {}).get(chat_id, {}).get("step") == "attach":
            return False                                   # allegato email: priorità al wizard
        cfg = fi.load_settings()
        if not cfg["enabled"]:
            # Funzione spenta/non configurata. Il comportamento di sempre resta, TRANNE quando la
            # didascalia chiede esplicitamente di salvare in una cartella: allora lo spieghiamo.
            caption0 = (msg.get("caption") or "").strip()
            if fi.looks_like_save_request(caption0):
                logger.info("FileInbox: file ricevuto con richiesta di salvataggio (%r) ma la funzione non è attiva "
                            "(interruttore=%s, cartelle=%d)", caption0, "ON" if cfg.get("switch_on") else "OFF",
                            len(cfg["folders"]))
                if cfg.get("switch_on") and not cfg["folders"]:
                    why = "L'interruttore è acceso ma <b>non c'è nessuna cartella</b> con un percorso."
                else:
                    why = "L'interruttore <b>Abilita il salvataggio dei file</b> è spento."
                await self._send(chat_id,
                    f"📁 <b>Il salvataggio dei file non è attivo.</b>\n{why}\n"
                    f"Apri la pagina web di HomeMind → scheda <b>📁 File</b>, attiva l'interruttore, "
                    f"aggiungi almeno una cartella (nome + percorso) e premi <b>Salva</b>.")
                return True
            return False

        st = self._fi_state()
        self._fi_purge(st)
        folders = cfg["folders"]
        caption = (msg.get("caption") or "").strip()
        mgid = msg.get("media_group_id")
        gkey = (chat_id, str(mgid)) if mgid else None

        # Album (più file insieme): la decisione presa sul primo vale per tutti
        idx, triggered = None, False
        if gkey and gkey in st["groups"]:
            idx = st["groups"][gkey]["idx"]
            triggered = idx is not None
        if not triggered:
            triggered, idx = fi.detect_trigger(caption, folders)
            if triggered and idx is None:
                idx = fi.default_index(folders)

        # Vocali/audio senza una didascalia di salvataggio: restano comandi vocali
        if media["kind"] in ("voice", "audio") and not triggered:
            return False
        # Video-messaggi/GIF senza didascalia: non intervengo
        if media["kind"] in ("animation", "video_note") and not triggered:
            return False

        logger.info("FileInbox: file %s, didascalia=%r → %s", media["kind"], caption,
                    (f"salva in '{folders[idx]['name']}'" if triggered and idx is not None else "chiedo la cartella"))
        if triggered and idx is not None:
            if gkey:                                       # prima di qualunque await
                st["groups"][gkey] = {"idx": idx, "ts": _t.time()}
            await self._fi_save_one(chat_id, msg, media, folders[idx], cfg, gkey)
            return True

        # Cartella non decisa: chiedi con i bottoni (un solo messaggio per album)
        item = {"msg_id": msg.get("message_id"), "media": media}
        if gkey and st["gpend"].get(gkey) in st["pending"]:
            st["pending"][st["gpend"][gkey]]["files"].append(item)
            return True
        token = _uuid.uuid4().hex[:8]
        st["pending"][token] = {"chat": chat_id, "files": [item], "ts": _t.time(), "gkey": gkey}
        if gkey:
            st["gpend"][gkey] = token
        rows = [[{"text": f"📁 {f['name']}", "callback_data": f"fi:{token}:{i}"}] for i, f in enumerate(folders)]
        rows.append([{"text": "✖️ Annulla", "callback_data": f"fi:{token}:x"}])
        await self._send_with_keyboard(
            chat_id,
            "📁 <b>Dove salvo questo file?</b>\n<i>Per allegarlo a un'email avvia prima /email.</i>",
            {"inline_keyboard": rows})
        return True

    async def _file_inbox_callback(self, chat_id: str, kb_msg_id, data: str):
        """Bottone "📁 cartella" premuto: salva i file in attesa e cancella la tastiera."""
        from agent import file_inbox as fi
        parts = data.split(":")
        if len(parts) != 3:
            return
        st = self._fi_state()
        pend = st["pending"].pop(parts[1], None)
        if not pend or pend["chat"] != chat_id:
            await self._send(chat_id, "⌛ Richiesta scaduta: rimanda il file.")
            return
        if pend.get("gkey"):
            st["gpend"].pop(pend["gkey"], None)
        if kb_msg_id:
            try:
                await self._api("deleteMessage", {"chat_id": chat_id, "message_id": kb_msg_id})
            except Exception:
                pass
        if parts[2] == "x":
            return
        cfg = fi.load_settings()
        try:
            idx = int(parts[2])
            folder = cfg["folders"][idx]
        except (ValueError, IndexError):
            await self._send(chat_id, "⚠️ Cartella non più disponibile: controlla la pagina web.")
            return
        gkey = pend.get("gkey")
        if gkey:
            import time as _t
            st["groups"][gkey] = {"idx": idx, "ts": _t.time()}
        files = pend["files"]
        agg = gkey or (("cb", parts[1]) if len(files) > 1 else None)
        for f in files:
            await self._fi_save_one(chat_id, {"message_id": f["msg_id"]}, f["media"], folder, cfg, agg)

    async def _fi_save_one(self, chat_id: str, msg: dict, media: dict, folder: dict, cfg: dict, gkey=None):
        """Scarica un file, lo salva e SOLO se è andato a buon fine cancella il messaggio da Telegram."""
        from agent import file_inbox as fi
        mid = msg.get("message_id")
        name, dest, err = "", None, None
        try:
            if media.get("size") and media["size"] > fi.MAX_BYTES:
                raise ValueError("file troppo grande: i bot Telegram scaricano file fino a 20 MB")
            data, tg_name, mime = await self._tg_download_file(media["file_id"])
            if not data:
                raise ValueError("download da Telegram non riuscito")
            name = fi.choose_filename(media, tg_name, mime)
            dest = await fi.save_to_folder(folder["path"], name, data)
        except Exception as e:
            err = str(e)
            if "too big" in err.lower():
                err = "file troppo grande: i bot Telegram scaricano file fino a 20 MB"
            elif isinstance(e, (PermissionError, OSError)):
                err = (f"{e}. Controlla che la cartella esista ed sia scrivibile "
                       f"(su Home Assistant l'addon vede /config, /share e /media)")
            logger.warning("FileInbox: salvataggio fallito (%s → %s): %s", name or media.get("kind"), folder.get("path"), e)

        deleted = None
        if dest is not None and cfg.get("delete_after", True) and mid:
            try:
                await self._api("deleteMessage", {"chat_id": chat_id, "message_id": mid})
                deleted = True
            except Exception as e:
                deleted = False
                logger.info("FileInbox: messaggio non eliminato: %s", e)
        if dest is not None:
            logger.info("FileInbox: salvato %s (%s)", dest, fi.human_size(len(data)))

        await self._fi_report(chat_id, gkey, folder, dest, len(data) if dest is not None else 0, err, deleted, name)

    async def _fi_report(self, chat_id, gkey, folder, dest, size, err, deleted, name):
        """Conferma all'utente: un messaggio per file, oppure un solo riepilogo aggiornato per gli album."""
        import html as _h, time as _t
        from agent import file_inbox as fi
        fname = _h.escape(dest.name if dest is not None else (name or "file"))
        fold = _h.escape(folder["name"])
        if gkey is None:
            if dest is not None:
                txt = (f"✅ <b>Salvato</b> in <b>{fold}</b>\n📄 <code>{fname}</code> · {fi.human_size(size)}\n"
                       f"📂 <code>{_h.escape(str(dest.parent))}</code>")
                if deleted is True:
                    txt += "\n🗑️ Messaggio eliminato da Telegram"
                elif deleted is False:
                    txt += "\n⚠️ Non sono riuscito a eliminare il messaggio da Telegram"
            else:
                txt = f"❌ <b>Non salvato</b>: {_h.escape(err or 'errore sconosciuto')}\n<i>Il messaggio non è stato eliminato.</i>"
            await self._send(chat_id, txt)
            return

        st = self._fi_state()
        import asyncio as _a
        lock = st["locks"].setdefault(gkey, _a.Lock())
        async with lock:
            sm = st["sums"].setdefault(gkey, {"msg_id": None, "ts": _t.time(), "ok": [], "err": [],
                                              "deleted": 0, "folder": fold,
                                              "path": str(dest.parent) if dest is not None else ""})
            sm["ts"] = _t.time()
            if dest is not None:
                sm["ok"].append((dest.name, size))
                sm["path"] = str(dest.parent)
                if deleted is True:
                    sm["deleted"] += 1
            else:
                sm["err"].append(err or "errore sconosciuto")
            lines = []
            if sm["ok"]:
                lines.append(f"✅ <b>Salvati {len(sm['ok'])} file</b> in <b>{sm['folder']}</b>\n"
                             f"📂 <code>{_h.escape(sm['path'])}</code>")
                lines += [f"• <code>{_h.escape(n)}</code> · {fi.human_size(sz)}" for n, sz in sm["ok"][:15]]
                if len(sm["ok"]) > 15:
                    lines.append(f"…e altri {len(sm['ok']) - 15}")
                if sm["deleted"]:
                    lines.append(f"🗑️ {sm['deleted']} messaggi eliminati da Telegram")
            for e in sm["err"][:3]:
                lines.append(f"❌ Non salvato: {_h.escape(e)}")
            text = "\n".join(lines)
            try:
                if sm["msg_id"] is None:
                    res = await self._api("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
                    sm["msg_id"] = res.get("result", {}).get("message_id")
                else:
                    await self._api("editMessageText", {"chat_id": chat_id, "message_id": sm["msg_id"],
                                                        "text": text, "parse_mode": "HTML"})
            except Exception as e:
                logger.debug("FileInbox: riepilogo album non aggiornato: %s", e)

    async def _handle_alarm_mode_cmd(self, chat_id: str, payload: str):
        """Gestisce comandi modalità allarme via Telegram.
        payload: "arm_mode:armed_night" | "auto_arm:notify" | ecc.
        Aggiorna person_config.json e notifica la UI.
        """
        import json as _json
        from pathlib import Path as _Path

        config_path = _Path("/config/homemind_patches/person_config.json")
        try:
            cfg = _json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.exists() else {}
        except Exception:
            cfg = {}

        parts = payload.split(":", 1)
        field = parts[0]   # "arm_mode" o "auto_arm"
        value = parts[1]   # es. "armed_night" o "notify"

        mode_labels = {
            "armed_away":    "🔒 Fuori casa (armed_away)",
            "armed_home":    "🏠 In casa — perimetrali (armed_home)",
            "armed_night":   "🌙 Notte — perimetrali (armed_night)",
            "armed_vacation":"✈️ Vacanza (armed_vacation)",
            "auto":          "🤖 Automatico — arma/disarma senza conferma",
            "notify":        "🔔 Notify — chiede conferma Telegram prima di armare",
            "disabled":      "🚫 Disabilitato — HomeMind non tocca l'allarme",
        }
        label = mode_labels.get(value, value)

        if field == "arm_mode":
            cfg["alarm_arm_mode"] = value
            # Aggiorna anche in memoria se home_model è accessibile
            try:
                if self.state_cache_cb:
                    # Passa il cambio al security manager via rest_client se disponibile
                    pass
            except Exception:
                pass
            msg = (
                f"🔒 <b>Modalità allarme aggiornata</b>\n"
                f"Quando HomeMind armerà automaticamente userà: <b>{label}</b>\n\n"
                f"<i>Salvato in person_config.json — riavvia HomeMind per applicare</i>"
            )
        elif field == "auto_arm":
            cfg["alarm_auto_arm"] = value
            msgs_map = {
                "auto":     (
                    "🤖 <b>Gestione allarme: Automatica</b>\n"
                    "HomeMind armerà/disarmerà automaticamente quando tutti escono/rientrano.\n"
                    "Nessuna conferma richiesta."
                ),
                "notify":   (
                    "🔔 <b>Gestione allarme: Notify</b>\n"
                    "HomeMind chiederà conferma su Telegram prima di armare.\n"
                    "Rispondi sì/no quando ricevi la notifica."
                ),
                "disabled": (
                    "🚫 <b>Gestione allarme: Disabilitata</b>\n"
                    "HomeMind non toccherà mai l'allarme automaticamente.\n"
                    "Potrai comunque armarlo manualmente da HA."
                ),
            }
            msg = msgs_map.get(value, f"⚙️ alarm_auto_arm → {value}")
        else:
            await self._send(chat_id, "⚠️ Comando non riconosciuto")
            return

        # Salva config
        try:
            config_path.write_text(
                _json.dumps(cfg, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            await self._send(chat_id, msg + "\n\n✅ <i>Config salvato</i>")
        except Exception as e:
            await self._send(chat_id, f"❌ Errore salvataggio config: {e}")

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

    async def _do_ai_modify_file(self, chat_id, target_file: str, description: str):
        """Pipeline modifica file con AI: legge → AI → smart merge → preview con conferma.

        Riusabile da:
        - /crea_sensore <descr>     (file = configuration.yaml)
        - /modifica --file X <descr> (file specificato)
        - Wizard "Modifica con AI" da menu file picker (target già impostato)
        """
        if not description:
            await self._send(chat_id, "⚠️ Descrizione vuota.")
            return
        await self._typing(chat_id)
        try:
            # 1. Legge file esistente
            existing = self._config_mgr.read_file(target_file)
            analysis = self._config_mgr.analyze_yaml_structure(existing)

            # 2. Contesto entità HA pertinenti (smart match)
            cache = self.state_cache_cb() if self.state_cache_cb else {}
            matches = _smart_entity_match(cache, description, max_results=50)
            entities_ctx = _format_entities_for_ai(matches)

            # 3. Sezioni esistenti per AI
            sections_list = ", ".join(analysis["sections"][:20]) or "(vuota)"
            includes_txt = ""
            for inc in analysis["includes"][:10]:
                includes_txt += f"\n  - {inc['key']} viene da {inc['path']} ({inc['type']})"

            # 4. Prompt AI specifico per il file
            file_hint = ""
            if target_file == "automations.yaml":
                file_hint = ("Il file è automations.yaml: il contenuto deve essere una "
                             "LISTA YAML di automazioni (ognuna inizia con `- id:`).")
            elif target_file == "scripts.yaml":
                file_hint = "Il file è scripts.yaml: contiene un dict di script HA."
            elif target_file == "scenes.yaml":
                file_hint = "Il file è scenes.yaml: lista YAML di scene."
            elif target_file.startswith("packages/"):
                file_hint = "Il file è un package: può contenere qualsiasi sezione HA top-level."
            elif target_file == "secrets.yaml":
                file_hint = ("Il file è secrets.yaml: contiene SOLO coppie chiave: valore. "
                             "ATTENZIONE: i secret sono dati sensibili.")
            elif target_file == "ui-lovelace.yaml":
                file_hint = "Il file è ui-lovelace.yaml: contiene la dashboard Lovelace."

            system_prompt = (
                f"Sei un esperto Home Assistant. L'utente vuole modificare il file "
                f"<{target_file}>.\n\n"
                f"{file_hint}\n\n"
                "REGOLE STRETTE:\n"
                "1. Rispondi SOLO con YAML valido, niente markdown, niente testo extra.\n"
                "2. Il YAML deve essere coerente col tipo di file (top-level corretto).\n"
                "3. ⚠️ USA SOLO ed ESCLUSIVAMENTE gli entity_id forniti nella lista "
                "'Entità HA disponibili' qui sotto. NON inventare entity_id. "
                "Se l'entità che ti serve non è nella lista, scegli la più simile.\n"
                "4. Rispetta la sintassi HA moderna.\n"
                "5. Niente commenti eccessivi."
            )
            user_prompt = (
                f"Richiesta: {description}\n\n"
                f"Sezioni esistenti in {target_file}: {sections_list}\n"
                f"File inclusi:{includes_txt or ' (nessuno)'}\n\n"
                f"Entità HA pertinenti:\n{entities_ctx}\n\n"
                f"Genera SOLO il YAML da aggiungere."
            )

            if not self.ai_cb:
                await self._send(chat_id, "⚠️ AI non disponibile.")
                return

            ai_response = await self.ai_cb(system_prompt, user_prompt, None)
            if not ai_response:
                await self._send(chat_id, "⚠️ AI non ha risposto.")
                return

            yaml_snippet = _extract_yaml(ai_response)
            if not yaml_snippet:
                await self._send(chat_id,
                    f"⚠️ AI ha risposto ma non ho trovato YAML valido:\n\n"
                    f"<pre>{_html_escape(ai_response[:1500])}</pre>")
                return

            # Validazione entità (anti-hallucination)
            invented = _validate_entities_in_yaml(yaml_snippet, cache)
            invented_warning = ""
            if invented:
                invented_warning = (
                    f"\n\n⚠️ <b>ATTENZIONE — entity_id inventate dall\'AI:</b>\n"
                    + "\n".join(f"  • <code>{e}</code>" for e in invented[:8])
                    + "\n\n<i>Verifica e correggi manualmente prima di applicare.</i>"
                )

            # 5. Smart insert
            result = self._config_mgr.smart_insert(existing, yaml_snippet)

            if not result["success"]:
                if result.get("strategy") == "include_warning":
                    warn_msg = (
                        f"⚠️ <b>Attenzione</b>\n\n{result['warning']}\n\n"
                        f"<b>YAML generato:</b>\n<pre>{_html_escape(yaml_snippet[:2000])}</pre>"
                    )
                    await self._send(chat_id, warn_msg)
                else:
                    await self._send(chat_id, f"⚠️ {result.get('error', 'Errore sconosciuto')}")
                return

            # 6. Pending + preview con bottoni
            self._config_pending[chat_id] = {
                "file":        target_file,
                "new_content": result["new_content"],
                "description": description,
                "section":     result["section"],
                "strategy":    result["strategy"],
                "yaml_added":  yaml_snippet,
            }
            strategy_lbl = ("🔄 Merge in sezione esistente"
                           if result["strategy"] == "merged"
                           else "➕ Nuova sezione in fondo")
            header = (
                f"🛠️ <b>Proposta modifica</b>\n"
                f"<i>File:</i> <code>{target_file}</code>\n"
                f"<i>Sezione:</i> <code>{result['section']}</code>\n"
                f"<i>Strategia:</i> {strategy_lbl}"
                f"{invented_warning}\n\n"
                f"<b>📝 YAML ({len(yaml_snippet.splitlines())} righe):</b>"
            )
            await self._send(chat_id, header)
            await _send_long_file(self, chat_id, f"Nuovo YAML → {target_file}", yaml_snippet)
            footer = ("💾 Se procedi, backup automatico in "
                      "<code>/config/homemind_patches/</code>")
            kb = {"inline_keyboard": [
                [{"text": "✅ Applica modifica", "callback_data": "config_apply"}],
                [{"text": "📊 Mostra diff",     "callback_data": "config_diff"}],
                [{"text": "❌ Annulla",          "callback_data": "config_cancel"}],
            ]}
            await self._send_with_keyboard(chat_id, footer, kb)
        except Exception as e:
            logger.exception("_do_ai_modify_file")
            await self._send(chat_id, f"⚠️ Errore: {str(e)[:300]}")

    async def _send_document(self, chat_id, file_path: str, caption: str = "",
                              filename_override: str = None):
        """Invia un file come documento Telegram (per contenuti lunghi).

        Args:
            chat_id: chat destinatario
            file_path: percorso assoluto o relativo a /config
            caption: caption opzionale (max 1024 char)
            filename_override: nome file mostrato al destinatario (default: nome originale)
        """
        import aiohttp
        from pathlib import Path as _P
        try:
            # Risolvi path
            p = _P(file_path)
            if not p.is_absolute():
                p = _P("/config") / file_path
            if not p.exists():
                await self._send(chat_id, f"⚠️ File non trovato: <code>{file_path}</code>")
                return
            filename = filename_override or p.name
            url = f"https://api.telegram.org/bot{self.token}/sendDocument"
            form = aiohttp.FormData()
            form.add_field("chat_id", str(chat_id))
            if caption:
                form.add_field("caption", caption[:1024])
                form.add_field("parse_mode", "HTML")
            form.add_field("document", p.read_bytes(),
                           filename=filename, content_type="text/plain")
            async with self._session.post(url, data=form) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("sendDocument FAIL %s: %s", resp.status, body[:200])
                    await self._send(chat_id, f"⚠️ Errore invio file: {resp.status}")
        except Exception as e:
            logger.exception("send_document")
            await self._send(chat_id, f"⚠️ Errore invio: {str(e)[:200]}")

    def _format_routine_for_telegram(self, name: str, md_content: str) -> str:
        """Converte il file .md della routine in messaggio Telegram leggibile.
        Parser line-by-line robusto che non dipende dalla gerarchia ## vs ###."""
        import re as _re
        _coord_re = _re.compile(r"^\(\d+\.\d+,\s*\d+\.\d+\)")
        lines = md_content.splitlines()
        out = [f"👤 <b>Routine di {name}</b>\n"]

        # ── Scan linea per linea identificando le sezioni ──
        mode = None  # "orari" | "luoghi" | "soste" | None
        current_date = None
        luoghi_rows = []
        soste_by_date = {}   # date → [righe]
        soste_dates_order = []

        for raw in lines:
            line = raw.strip()

            # Aggiornamento header
            if line.startswith("> Aggiornato:"):
                out.append(f"<i>{line[2:].strip()}</i>")
                continue

            # Sezioni principali
            if "Orari abituali" in line and line.startswith("#"):
                mode = "orari"; continue
            if "Luoghi più frequentati" in line and line.startswith("#"):
                mode = "luoghi"; continue
            if "Soste recenti" in line and line.startswith("#"):
                mode = "soste"; current_date = None; continue
            if "Diario settimanale" in line and line.startswith("#"):
                mode = None; continue
            if "Ultime uscite" in line and line.startswith("#"):
                mode = None; continue
            if "Note personali" in line and line.startswith("#"):
                mode = None; continue
            if line.startswith("---"):
                continue

            if mode == "orari":
                if "|" in line and "---" not in line and "Evento" not in line:
                    parts = [p.strip().strip("*") for p in line.split("|") if p.strip()]
                    if len(parts) >= 3:
                        out.append(f"  {parts[0]}  →  {parts[1]}  (±{parts[2]})")

            elif mode == "luoghi":
                if "|" in line and "---" not in line and "Luogo" not in line and "#" not in line:
                    parts = [p.strip().strip("*") for p in line.split("|") if p.strip()]
                    if len(parts) >= 5:
                        luogo = parts[1]
                        # Salta righe con solo coordinate
                        if not _coord_re.match(luogo):
                            luoghi_rows.append((parts[0], luogo, parts[2], parts[3], parts[4]))

            elif mode == "soste":
                # Data: **2026-05-04**
                dm = _re.match(r"\*\*?(\d{4}-\d{2}-\d{2})\*\*?", line)
                if dm:
                    current_date = dm.group(1)
                    if current_date not in soste_by_date:
                        soste_by_date[current_date] = []
                        soste_dates_order.append(current_date)
                    continue
                # Sosta: - indirizzo — HH:MM–HH:MM (N min)
                if line.startswith("- ") and current_date:
                    content = line[2:].strip()
                    # Salta pure coordinate
                    if not _coord_re.match(content):
                        soste_by_date[current_date].append(content)

        # ── Orari: titolo solo se ci sono dati ──
        orari_lines = [l for l in out[1:] if "→" in l]
        if orari_lines:
            # Inserisci titolo prima delle righe orari
            idx = out.index(orari_lines[0]) if orari_lines[0] in out else -1
            if idx > 0:
                out.insert(idx, "⏰ <b>Orari abituali</b>")
                out.insert(idx + len(orari_lines) + 1, "")
        else:
            out.append("⏰ <b>Orari abituali</b>")
            out.append("  <i>Dati insufficienti — serve qualche giorno in più</i>")
            out.append("")

        # ── Luoghi frequentati ──
        if luoghi_rows:
            out.append("📍 <b>Luoghi più frequentati</b>")
            for i, (num, luogo, visite, tempo, orario) in enumerate(luoghi_rows[:8], 1):
                out.append(f"  {i:>2}. <b>{luogo}</b>")
                out.append(f"      {visite} · {tempo} · tipico {orario}")
            out.append("")
        else:
            out.append("📍 <b>Luoghi frequentati</b>")
            out.append("  <i>Nessun dato GPS — configura location_tracker</i>")
            out.append("")

        # ── Soste recenti ──
        if soste_dates_order:
            out.append("📅 <b>Soste recenti</b>")
            total = 0
            for date_str in soste_dates_order:
                stops = soste_by_date.get(date_str, [])
                if not stops:
                    continue
                out.append(f"\n<b>{date_str}</b>")
                for s in stops:
                    out.append(f"  • {s}")
                    total += 1
            if total == 0:
                out.append("  <i>Nessuna sosta con indirizzo reale ancora</i>")
            out.append("")

        result = "\n".join(out)
        if len(result) > 3900:
            result = result[:3800] + "\n<i>... (troncato)</i>"
        return result

    async def _send_with_keyboard(self, chat_id, text, keyboard):
        """Invia un messaggio con tastiera inline personalizzata.

        Usa editMessageText quando possibile (da callback_query), altrimenti sendMessage.
        """
        try:
            await self._api("sendMessage", {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": keyboard,
            })
        except Exception as e:
            # Fallback plain text senza keyboard
            try:
                import re as _r
                plain = _r.sub(r"<[^>]+>", "", text)
                await self._api("sendMessage", {
                    "chat_id": chat_id,
                    "text": plain[:4000],
                    "reply_markup": keyboard,
                })
            except Exception as e2:
                logger.warning("TG send_with_keyboard fail: %s / %s", e, e2)

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

        # Bottone navigazione: aggiunto solo all'ultimo chunk
        _menu_kb = {
            "inline_keyboard": [[
                {"text": "🏠 Menu principale", "callback_data": "menu_back"},
                {"text": "🗑 Cancella",         "callback_data": "msg_delete"},
            ]]
        }
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            is_last = (i == len(chunks) - 1)
            _params = {
                "chat_id":    chat_id,
                "text":       chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            if is_last:
                _params["reply_markup"] = _menu_kb
            try:
                await self._api("sendMessage", _params)
            except Exception as e:
                # Fallback plain text (senza keyboard per massima compatibilità)
                try:
                    plain = re.sub(r"<[^>]+>", "", chunk)
                    fb_params = {
                        "chat_id": chat_id, "text": plain[:4000],
                        "disable_web_page_preview": True,
                    }
                    if is_last:
                        fb_params["reply_markup"] = _menu_kb
                    await self._api("sendMessage", fb_params)
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

    async def send_media_group(self, chat_id: str, photos: list) -> bool:
        """Manda fino a 10 foto come album. photos = [(jpeg_bytes, caption), ...].
        Con 1 sola foto usa send_photo (sendMediaGroup richiede almeno 2 elementi)."""
        if not photos:
            return False
        if len(photos) == 1:
            return await self.send_photo(chat_id, photos[0][0], photos[0][1])
        photos = photos[:10]
        for attempt in (1, 2):
            try:
                url = f"{TG_API}/bot{self.token}/sendMediaGroup"
                data = aiohttp.FormData()
                data.add_field("chat_id", str(chat_id))
                media = []
                for i, (b, cap) in enumerate(photos):
                    media.append({"type": "photo", "media": f"attach://f{i}",
                                  "caption": (cap or "")[:1024]})
                    data.add_field(f"f{i}", b, filename=f"snap{i}.jpg", content_type="image/jpeg")
                data.add_field("media", json.dumps(media))
                timeout = aiohttp.ClientTimeout(total=60)
                async with self._session.post(url, data=data, timeout=timeout) as r:
                    result = await r.json()
                if result.get("ok"):
                    logger.info("Album di %d foto inviato su Telegram chat %s", len(photos), chat_id)
                    return True
                # Rate limit Telegram: attende quanto richiesto e riprova una volta
                wait = (result.get("parameters") or {}).get("retry_after")
                if attempt == 1 and wait and int(wait) <= 30:
                    await asyncio.sleep(int(wait) + 1)
                    continue
                logger.error("Errore invio album Telegram: %s", result)
                return False
            except Exception as e:
                logger.error("send_media_group errore: %s", e)
                return False
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


    # ═══════════════════════════════════════════════════════════════════════
    async def _email_accounts(self) -> list:
        """Carica account email abilitati."""
        try:
            from agent.email_manager import _load_accounts
            return [a for a in _load_accounts() if a.get("enabled", True)]
        except Exception:
            return []

    async def _email_show_menu(self, chat_id: str):
        """Menu principale email con bottoni inline."""
        accounts = await self._email_accounts()
        if not accounts:
            kb = {"inline_keyboard": [
                [{"text": "⚙️ Configura account", "callback_data": "menu_back"}],
            ]}
            await self._send_with_keyboard(chat_id,
                "📧 <b>Email</b>\n\n⚠️ Nessun account Gmail configurato.\n"
                "Apri la pagina <b>📧 Email</b> dall'interfaccia web → tab <b>⚙️ Account</b>.",
                kb)
            return

        acc_labels = "\n".join(f"  • {a.get('label') or a['address']}" for a in accounts)
        kb = {"inline_keyboard": [
            [{"text": "📥 Leggi inbox",      "callback_data": "__EMAIL_LIST__"},
             {"text": "✍️ Nuova risposta",   "callback_data": "__EMAIL_NEW__"}],
            [{"text": "🏠 Menu principale",  "callback_data": "menu_back"},
             {"text": "🗑 Cancella",          "callback_data": "msg_delete"}],
        ]}
        await self._send_with_keyboard(chat_id,
            f"📧 <b>Email Manager</b>\n\nAccount configurati:\n{acc_labels}\n\n"
            f"Cosa vuoi fare?", kb)

    async def _email_show_inbox(self, chat_id: str):
        """Mostra le ultime email dell'inbox con classificazione AI."""
        accounts = await self._email_accounts()
        if not accounts:
            await self._send(chat_id, "⚠️ Nessun account configurato.")
            return
        await self._send(chat_id, "📥 <i>Caricamento email…</i>")
        all_emails = []
        for acc in accounts[:2]:  # max 2 account su Telegram
            try:
                from agent.email_manager import fetch_emails
                import asyncio as _aio
                emails = await _aio.to_thread(fetch_emails, acc, "INBOX", 8)
                all_emails.extend(emails)
            except Exception as e:
                await self._send(chat_id, f"⚠️ Errore {acc['address']}: {e}")
        if not all_emails:
            await self._send(chat_id, "📭 Nessuna email trovata.")
            return
        # Salva lista in stato wizard per riferimento indice
        self._email_wizard[chat_id] = {"step": "list", "emails": all_emails}
        lines = ["📧 <b>Email recenti:</b>\n"]
        for i, em in enumerate(all_emails[:8]):
            icon = "🔵" if not em.get("seen") else "⚪"
            lines.append(f"{icon} <b>{i+1}.</b> {em['sender'][:30]}\n   📌 {em['subject'][:45]}")
        buttons = []
        row = []
        for i in range(min(len(all_emails), 8)):
            row.append({"text": f"{i+1}", "callback_data": f"__EMAIL_OPEN__:{i}"})
            if len(row) == 4:
                buttons.append(row); row = []
        if row:
            buttons.append(row)
        buttons.append([
            {"text": "✍️ Nuova risposta", "callback_data": "__EMAIL_NEW__"},
            {"text": "❌ Chiudi",         "callback_data": "msg_delete"},
        ])
        await self._send_with_keyboard(chat_id, "\n".join(lines),
                                        {"inline_keyboard": buttons})

    async def _email_open(self, chat_id: str, idx: int):
        """Apre e mostra il testo completo di una email."""
        state = self._email_wizard.get(chat_id, {})
        emails = state.get("emails", [])
        if idx >= len(emails):
            await self._send(chat_id, "⚠️ Email non trovata."); return
        em = emails[idx]
        # Carica body completo
        accounts = await self._email_accounts()
        acc = next((a for a in accounts if a["address"] == em.get("account_address")), None)
        body = em.get("body_text", "")
        if acc and not body:
            try:
                from agent.email_manager import fetch_emails
                import asyncio as _aio
                full = await _aio.to_thread(fetch_emails, acc, em.get("folder","INBOX"), 200)
                match = next((e for e in full if e["uid"] == em["uid"]), None)
                if match:
                    body = match.get("body_text", "")
                    emails[idx] = {**em, **match}
                    self._email_wizard[chat_id]["emails"] = emails
            except Exception:
                pass
        # AI summary se disponibile
        summary = ""
        if self.ai_cb:
            try:
                from agent.email_manager import ai_summarize_email
                ai_cb = lambda p: self.ai_cb("Sei un assistente email. Rispondi in italiano.", p, [])
                summary = await ai_summarize_email(emails[idx], ai_cb)
            except Exception:
                pass
        text = (
            f"📧 <b>{em['subject']}</b>\n"
            f"👤 Da: {em['sender']}\n"
            f"📅 {em.get('date','')}\n\n"
        )
        if summary:
            text += f"🤖 <i>Sommario AI:</i>\n{summary}\n\n"
        text += f"📝 <b>Testo:</b>\n{body[:800]}{'…' if len(body)>800 else ''}"
        kb = {"inline_keyboard": [
            [{"text": "✍️ Rispondi con AI", "callback_data": f"__EMAIL_REPLY__:{idx}"},
             {"text": "🗑️ Cestino",         "callback_data": f"__EMAIL_DELETE__:{idx}"}],
            [{"text": "◀️ Lista",            "callback_data": "__EMAIL_LIST__"},
             {"text": "❌ Chiudi",           "callback_data": "msg_delete"}],
        ]}
        await self._send_with_keyboard(chat_id, text, kb)

    async def _email_delete(self, chat_id: str, idx: int):
        """Sposta email nel cestino."""
        state = self._email_wizard.get(chat_id, {})
        emails = state.get("emails", [])
        if idx >= len(emails):
            await self._send(chat_id, "⚠️ Email non trovata."); return
        em = emails[idx]
        accounts = await self._email_accounts()
        acc = next((a for a in accounts if a["address"] == em.get("account_address")), None)
        if not acc:
            await self._send(chat_id, "⚠️ Account non trovato."); return
        try:
            from agent.email_manager import delete_email
            import asyncio as _aio
            ok = await _aio.to_thread(delete_email, acc, em["uid"], em.get("folder","INBOX"))
            if ok:
                await self._send(chat_id, f"🗑️ Email <i>{em['subject'][:50]}</i> spostata nel cestino.")
                emails.pop(idx)
                self._email_wizard[chat_id]["emails"] = emails
                if emails:
                    await self._email_show_inbox(chat_id)
            else:
                await self._send(chat_id, "❌ Errore durante la cancellazione.")
        except Exception as e:
            await self._send(chat_id, f"❌ Errore: {e}")

    async def _email_start_reply(self, chat_id: str, idx: int):
        """Avvia wizard risposta AI su email esistente (passo 1: scelta stile)."""
        state = self._email_wizard.get(chat_id, {})
        emails = state.get("emails", [])
        if idx >= len(emails):
            await self._send(chat_id, "⚠️ Email non trovata."); return
        em = emails[idx]
        self._email_wizard[chat_id] = {
            "step": "style",
            "emails": emails,
            "reply_idx": idx,
            "subject": em["subject"],
            "to": em["sender"],
            "orig_body": em.get("body_text", ""),
            "msg_id": em.get("msg_id", ""),
            "account": em.get("account_address", ""),
            "mode": "reply",
        }
        import re as _re3
        m = _re3.search(r"<([^>]+)>", em["sender"])
        self._email_wizard[chat_id]["to"] = m.group(1) if m else em["sender"]
        await self._email_ask_style(chat_id)

    async def _email_start_new(self, chat_id: str):
        """Avvia wizard nuova email (passo 1: chiede destinatario)."""
        accounts = await self._email_accounts()
        if not accounts:
            await self._send(chat_id, "⚠️ Nessun account configurato."); return
        self._email_wizard[chat_id] = {
            "step": "new_to",
            "account": accounts[0]["address"],
            "mode": "new",
        }
        await self._send(chat_id,
            "✉️ <b>Nuova email</b>\n\nInserisci l'indirizzo del destinatario:\n"
            "<i>(oppure /annulla per uscire)</i>")

    async def _email_ask_style(self, chat_id: str):
        """Chiede stile di risposta."""
        kb = {"inline_keyboard": [
            [{"text": "💼 Professionale", "callback_data": "__EMAIL_STYLE__:professionale"},
             {"text": "😊 Amichevole",    "callback_data": "__EMAIL_STYLE__:amichevole"}],
            [{"text": "🎩 Formale",       "callback_data": "__EMAIL_STYLE__:formale"},
             {"text": "⚡ Breve",         "callback_data": "__EMAIL_STYLE__:breve"}],
            [{"text": "❌ Annulla",       "callback_data": "msg_delete"}],
        ]}
        state = self._email_wizard.get(chat_id, {})
        subj = state.get("subject", "")
        await self._send_with_keyboard(chat_id,
            f"✍️ <b>Wizard risposta AI</b>\n📌 <i>{subj[:60]}</i>\n\n"
            f"<b>Passo 1/3</b> — Scegli lo stile della risposta:", kb)

    async def _email_set_style(self, chat_id: str, style: str):
        """Imposta stile e chiede istruzioni."""
        if chat_id not in self._email_wizard:
            await self._send(chat_id, "⚠️ Wizard scaduto. Riprova."); return
        self._email_wizard[chat_id]["style"] = style
        self._email_wizard[chat_id]["step"] = "instructions"
        style_emoji = {"professionale":"💼","amichevole":"😊","formale":"🎩","breve":"⚡"}.get(style,"✉️")
        await self._send(chat_id,
            f"✍️ <b>Wizard risposta AI</b> — <b>Passo 2/3</b>\n"
            f"Stile scelto: {style_emoji} <i>{style}</i>\n\n"
            f"Scrivi le <b>istruzioni per l'AI</b>:\n"
            f"<i>Es: 'Dì che sono disponibile giovedì, proponi di sentirci alle 15'</i>\n\n"
            f"<i>(/annulla per uscire)</i>")

    async def _handle_email_wizard_step(self, chat_id: str, text: str) -> bool:
        """Gestisce i passi testuali del wizard email. Ritorna True se gestito."""
        state = self._email_wizard.get(chat_id, {})
        step = state.get("step", "")

        if step == "new_to":
            state["to"] = text.strip()
            state["step"] = "new_subj"
            self._email_wizard[chat_id] = state
            await self._send(chat_id, "📌 <b>Oggetto email:</b>")
            return True

        if step == "new_subj":
            state["subject"] = text.strip()
            state["step"] = "new_body"
            self._email_wizard[chat_id] = state
            await self._send(chat_id,
                "📝 <b>Testo email</b> (oppure scrivi 'ai: <istruzioni>' per generarla con l'AI):\n"
                "<i>Es: 'ai: Scrivi una email per chiedere un preventivo'</i>")
            return True

        if step == "new_body":
            body_text = text.strip()
            if body_text.lower().startswith("ai:"):
                # Genera con AI
                instructions = body_text[3:].strip()
                state["step"] = "instructions"
                state["orig_body"] = ""
                state["instructions"] = instructions
                self._email_wizard[chat_id] = state
                await self._email_generate_draft(chat_id)
                return True
            else:
                state["body"] = body_text
                state["step"] = "confirm_new"
                self._email_wizard[chat_id] = state
                await self._email_confirm(chat_id)
                return True

        if step == "instructions":
            state["instructions"] = text.strip()
            state["step"] = "generating"
            self._email_wizard[chat_id] = state
            await self._send(chat_id, "🤖 <i>Generazione bozza AI in corso…</i>")
            await self._email_generate_draft(chat_id)
            return True

        if step == "edit_draft":
            # Comando testuale per allegare file (alternativa al bottone)
            if text.strip().lower() in ("allega", "allegato", "/allega", "📎", "attach"):
                state["step"] = "attach"
                self._email_wizard[chat_id] = state
                await self._send(chat_id,
                    "📎 <b>Invia il file da allegare:</b>\n"
                    "• Foto → invia direttamente\n"
                    "• PDF/Word/Excel → invia come documento\n"
                    "<i>Puoi aggiungerne più di uno.</i>")
                return True
            state["draft"] = text.strip()
            state["step"] = "confirm"
            self._email_wizard[chat_id] = state
            await self._email_confirm(chat_id)
            return True

        if step == "schedule_time":
            # Interpreta data/ora libera con AI
            await self._email_process_schedule(chat_id, text)
            return True

        return False

    async def _email_generate_draft(self, chat_id: str):
        """Genera bozza AI e mostra step 3 (conferma/modifica)."""
        state = self._email_wizard.get(chat_id, {})
        if not self.ai_cb:
            await self._send(chat_id, "⚠️ AI non disponibile."); return
        try:
            from agent.email_manager import ai_generate_reply
            em_fake = {
                "sender": state.get("to", ""),
                "subject": state.get("subject", ""),
                "body_text": state.get("orig_body", ""),
            }
            instructions = state.get("instructions", "Rispondi in modo cortese.")
            style = state.get("style", "professionale")
            ai_cb = lambda p: self.ai_cb("Sei un assistente email. Rispondi in italiano.", p, [])
            draft = await ai_generate_reply(em_fake, instructions, ai_cb, style=style)
            state["draft"] = draft
            state["step"] = "confirm"
            self._email_wizard[chat_id] = state
            await self._email_confirm(chat_id)
        except Exception as e:
            await self._send(chat_id, f"❌ Errore AI: {e}")
            self._email_wizard.pop(chat_id, None)

    async def _email_confirm(self, chat_id: str):
        """Mostra bozza e chiede conferma/modifica/invio."""
        state = self._email_wizard.get(chat_id, {})
        draft = state.get("draft") or state.get("body", "")
        atts = state.get("attachments", [])
        att_txt = f"\n📎 {len(atts)} allegato/i" if atts else ""
        kb = {"inline_keyboard": [
            [{"text": "✅ Invia subito",      "callback_data": "__EMAIL_SEND_NOW__"},
             {"text": "🕐 Programma",         "callback_data": "__EMAIL_SEND_SCHEDULE__"}],
            [{"text": "📎 Aggiungi allegato", "callback_data": "__EMAIL_ADD_ATTACH__"}],
            [{"text": "🔄 Rigenera",          "callback_data": "__EMAIL_DRAFT_REGEN__"}],
            [{"text": "❌ Annulla",            "callback_data": "msg_delete"}],
        ]}
        await self._send_with_keyboard(chat_id,
            f"✍️ <b>Passo 3/3 — Bozza email:</b>\n\n"
            f"📬 A: <code>{state.get('to','')}</code>\n"
            f"📌 Oggetto: <i>{state.get('subject','')}</i>{att_txt}\n\n"
            f"<pre>{draft[:600]}{'…' if len(draft)>600 else ''}</pre>\n\n"
            f"<i>Invia direttamente, programma l'invio, aggiungi allegati o scrivi modifiche.</i>",
            kb)
        # Permetti modifica testuale
        state["step"] = "edit_draft"
        self._email_wizard[chat_id] = state

    async def _email_ask_schedule(self, chat_id: str):
        """Chiede orario programmato in linguaggio naturale."""
        if chat_id not in self._email_wizard:
            return
        self._email_wizard[chat_id]["step"] = "schedule_time"
        await self._send(chat_id,
            "🕐 <b>Quando vuoi inviare?</b>\n\n"
            "Scrivi data e ora in modo naturale:\n"
            "<i>Es: 'domani alle 9', 'lunedì mattina alle 10', 'tra 2 ore'</i>")

    async def _email_process_schedule(self, chat_id: str, text: str):
        """Interpreta orario naturale con AI e salva task programmato."""
        state = self._email_wizard.get(chat_id, {})
        from datetime import datetime as _dt
        now_str = _dt.now().strftime("%Y-%m-%d %H:%M")
        if self.ai_cb:
            try:
                prompt = (
                    f"Oggi è {now_str}. L'utente vuole programmare un'azione per: '{text}'.\n"
                    f"Rispondi SOLO con la data/ora in formato ISO 8601: YYYY-MM-DDTHH:MM:SS\n"
                    f"Nessun altro testo."
                )
                iso = await self.ai_cb("", prompt, [])
                iso = iso.strip().strip('"').strip("'")
                # Valida formato
                _dt.fromisoformat(iso)
            except Exception:
                await self._send(chat_id, "⚠️ Non ho capito l'orario. Usa formato: 'domani alle 9'"); return
        else:
            await self._send(chat_id, "⚠️ AI non disponibile per interpretare l'orario."); return

        accounts = await self._email_accounts()
        acc_addr = state.get("account") or (accounts[0]["address"] if accounts else "")
        draft = state.get("draft") or state.get("body", "")
        try:
            from agent.email_manager import schedule_email
            task = schedule_email(acc_addr, state.get("to",""), state.get("subject",""), draft, iso)
            await self._send(chat_id,
                f"🕐 <b>Email programmata!</b>\n"
                f"📬 A: {state.get('to','')}\n"
                f"📌 {state.get('subject','')}\n"
                f"⏰ Invio: {iso.replace('T',' ')}")
        except Exception as e:
            await self._send(chat_id, f"❌ Errore programmazione: {e}")
        self._email_wizard.pop(chat_id, None)

    async def _email_regen_draft(self, chat_id: str):
        """Rigenera la bozza AI."""
        if chat_id not in self._email_wizard:
            await self._send(chat_id, "⚠️ Wizard scaduto."); return
        self._email_wizard[chat_id]["step"] = "instructions"
        await self._send(chat_id,
            "🔄 <b>Rigenera bozza</b>\n\nDai nuove istruzioni all'AI:\n"
            "<i>Es: 'Sii più conciso e professionale'</i>")

    async def _email_empty_folder_tg(self, chat_id: str, folder: str):
        """Svuota cestino o spam da Telegram."""
        accounts = await self._email_accounts()
        if not accounts:
            await self._send(chat_id, "⚠️ Nessun account configurato."); return
        label = {"[Gmail]/Trash": "Cestino", "[Gmail]/Spam": "Spam"}.get(folder, folder)
        await self._send(chat_id, f"🗑️ <i>Svuoto {label} in corso…</i>")
        total = 0
        for acc in accounts:
            try:
                from agent.email_manager import empty_folder
                import asyncio as _aio
                result = await _aio.to_thread(empty_folder, acc, folder)
                total += result.get("deleted", 0)
            except Exception as e:
                await self._send(chat_id, f"⚠️ Errore {acc['address']}: {e}")
        await self._send(chat_id, f"✅ <b>{label} svuotato!</b> Eliminate {total} email.")

    # ═══════════════════════════════════════════════════════════════════════
    # 📎 ALLEGATI EMAIL — download da Telegram e attach
    # ═══════════════════════════════════════════════════════════════════════

    async def _tg_download_file(self, file_id: str) -> tuple[bytes, str, str]:
        """
        Scarica un file da Telegram dato il file_id.
        Ritorna (bytes, filename, mimetype)
        """
        # Ottieni info file
        file_info = await self._api("getFile", {"file_id": file_id})
        file_path = file_info["result"]["file_path"]
        file_url  = f"https://api.telegram.org/file/bot{self.token}/{file_path}"

        async with self._session.get(file_url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Download fallito HTTP {resp.status}")
            data = await resp.read()

        # Ricava nome file e mimetype dal path
        import os
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        MIME_MAP = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".txt": "text/plain",
            ".zip": "application/zip",
        }
        mimetype = MIME_MAP.get(ext, "application/octet-stream")
        return data, filename, mimetype

    async def _email_handle_attachment(self, chat_id: str, msg: dict):
        """
        Scarica foto o documento da Telegram e lo aggiunge agli allegati email in corso.
        """
        state = self._email_wizard.get(chat_id, {})
        if not state:
            await self._send(chat_id, "⚠️ Nessun wizard email attivo."); return

        try:
            photo   = msg.get("photo")
            doc     = msg.get("document")

            if photo:
                # Prendi la foto più grande (ultima in lista)
                best = sorted(photo, key=lambda p: p.get("file_size", 0))[-1]
                file_id  = best["file_id"]
                data, fname, mime = await self._tg_download_file(file_id)
                # Rinomina con timestamp se nome generico
                if fname.endswith(".jpg") and not fname.startswith("photo"):
                    from datetime import datetime
                    fname = f"foto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            elif doc:
                file_id  = doc["file_id"]
                doc_name = doc.get("file_name", "allegato")
                data, fname, mime = await self._tg_download_file(file_id)
                fname = doc_name  # usa il nome originale del documento
            else:
                await self._send(chat_id, "⚠️ Tipo file non supportato."); return

            size_kb = len(data) / 1024
            if size_kb > 20 * 1024:  # 20 MB limite
                await self._send(chat_id, f"❌ File troppo grande ({size_kb/1024:.1f} MB). Max 20 MB."); return

            # Salva allegato nello stato wizard
            atts = state.setdefault("attachments", [])
            atts.append({"filename": fname, "data": data, "mimetype": mime})
            state["attachments"] = atts

            tot_size = sum(len(a["data"]) for a in atts) / 1024
            await self._send(chat_id,
                f"📎 <b>Allegato aggiunto:</b> {fname} ({size_kb:.0f} KB)\n"
                f"📦 Totale allegati: {len(atts)} ({tot_size:.0f} KB)\n\n"
                f"Invia altri file oppure digita qualcosa per continuare.")

            # Mostra pulsanti per procedere o aggiungere altri
            kb = {"inline_keyboard": [
                [{"text": "✅ Procedi con l'invio", "callback_data": "__EMAIL_SEND_NOW__"},
                 {"text": "🕐 Programma",           "callback_data": "__EMAIL_SEND_SCHEDULE__"}],
                [{"text": "➕ Aggiungi altro allegato", "callback_data": "__EMAIL_ADD_ATTACH__"}],
                [{"text": "🗑️ Rimuovi allegati",    "callback_data": "__EMAIL_CLEAR_ATTACH__"},
                 {"text": "❌ Annulla",              "callback_data": "msg_delete"}],
            ]}
            await self._send_with_keyboard(chat_id,
                f"📋 <b>Riepilogo email:</b>\n"
                f"📬 A: <code>{state.get('to','')}</code>\n"
                f"📌 {state.get('subject','')}\n"
                f"📎 {len(atts)} allegato/i", kb)

        except Exception as e:
            logger.error("_email_handle_attachment: %s", e)
            await self._send(chat_id, f"❌ Errore download allegato: {e}")

    async def _email_send_now(self, chat_id: str):
        """Invia email immediatamente, con eventuali allegati."""
        state = self._email_wizard.get(chat_id, {})
        accounts = await self._email_accounts()
        acc_addr = state.get("account") or (accounts[0]["address"] if accounts else "")
        acc = next((a for a in accounts if a["address"] == acc_addr), None)
        if not acc:
            await self._send(chat_id, "⚠️ Account non trovato."); return
        draft = state.get("draft") or state.get("body", "")
        attachments = state.get("attachments", [])
        try:
            import asyncio as _aio
            if attachments:
                from agent.email_manager import send_email_with_attachments
                ok = await _aio.to_thread(send_email_with_attachments, acc,
                                          state.get("to",""), state.get("subject",""),
                                          draft, attachments, state.get("msg_id",""))
            else:
                from agent.email_manager import send_email
                ok = await _aio.to_thread(send_email, acc,
                                          state.get("to",""), state.get("subject",""),
                                          draft, state.get("msg_id",""))
            if ok:
                att_txt = f" + {len(attachments)} allegato/i" if attachments else ""
                await self._send(chat_id,
                    f"✅ <b>Email inviata!</b>{att_txt}\n"
                    f"📬 A: {state.get('to','')}\n"
                    f"📌 {state.get('subject','')}")
            else:
                await self._send(chat_id, "❌ Errore invio. Controlla le credenziali Gmail.")
        except Exception as e:
            await self._send(chat_id, f"❌ Errore: {e}")
        self._email_wizard.pop(chat_id, None)

    async def _email_start_new_prefilled(self, chat_id: str, to_addr: str = "", to_name: str = ""):
        """
        Avvia wizard nuova email con destinatario pre-compilato da NLU.
        Se to_addr è noto → salta step destinatario.
        Se to_name ma non to_addr → cerca in rubrica email recenti.
        """
        accounts = await self._email_accounts()
        if not accounts:
            await self._send(chat_id, "⚠️ Nessun account Gmail configurato.\nVai su 📧 Email → ⚙️ Account.")
            return

        self._email_wizard[chat_id] = {
            "step": "new_to",
            "account": accounts[0]["address"],
            "mode": "new",
            "attachments": [],
        }

        # Caso 1: indirizzo completo già rilevato
        if to_addr and "@" in to_addr:
            self._email_wizard[chat_id]["to"] = to_addr
            self._email_wizard[chat_id]["step"] = "new_subj"
            await self._send(chat_id,
                f"✉️ <b>Nuova email</b>\n"
                f"📬 A: <code>{to_addr}</code> ✅\n\n"
                f"📌 <b>Oggetto</b> dell'email:")
            return

        # Caso 2: nome rilevato ma no indirizzo → chiedi conferma/completamento
        if to_name:
            await self._send(chat_id,
                f"✉️ <b>Nuova email</b>\n\n"
                f"Ho capito che vuoi scrivere a <b>{to_name}</b>.\n"
                f"Inserisci l'indirizzo email completo:\n"
                f"<i>(oppure /annulla)</i>")
            return

        # Caso 3: nessun destinatario rilevato → wizard standard
        await self._email_start_new(chat_id)
