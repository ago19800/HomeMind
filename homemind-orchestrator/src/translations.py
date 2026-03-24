"""
translations.py — Supporto multilingua HomeMind (IT / EN)

Uso:
    from translations import t, set_lang, get_lang

    t("start_msg")          → stringa nella lingua corrente
    t("card_style_help", style="mushroom")  → stringa con placeholder
    set_lang("en")          → cambia lingua globale
    get_lang()              → "it" | "en"
"""

_LANG = "it"

STRINGS = {

    # ── Comandi base ──────────────────────────────────────────────────────
    "start_msg": {
        "it": (
            "<b>HomeMind attivo</b>\n\n"
            "Scrivimi in italiano qualsiasi cosa sulla tua casa.\n\n"
            "Scrivi /comandi per vedere tutti i comandi disponibili."
        ),
        "en": (
            "<b>HomeMind active</b>\n\n"
            "Write me anything about your home in English.\n\n"
            "Type /commands to see all available commands."
        ),
    },

    "unauthorized": {
        "it": "Accesso non autorizzato.",
        "en": "Unauthorized access.",
    },

    "module_unavailable": {
        "it": "⚠️ Funzione non disponibile.",
        "en": "⚠️ Feature not available.",
    },

    "ai_unavailable": {
        "it": "❌ Modulo AI non disponibile.",
        "en": "❌ AI module not available.",
    },

    "error_short": {
        "it": "❌ Errore: {msg}",
        "en": "❌ Error: {msg}",
    },

    "ai_error": {
        "it": "❌ Errore AI: {msg}",
        "en": "❌ AI error: {msg}",
    },

    # ── Lingua ────────────────────────────────────────────────────────────
    "lang_changed": {
        "it": "🌍 Lingua impostata: <b>Italiano</b>",
        "en": "🌍 Language set: <b>English</b>",
    },
    "lang_unknown": {
        "it": "⚠️ Lingua non supportata. Usa: <code>/lingua it</code> o <code>/lingua en</code>",
        "en": "⚠️ Unsupported language. Use: <code>/lang it</code> or <code>/lang en</code>",
    },
    "lang_current": {
        "it": "Lingua attuale: <b>Italiano</b> 🇮🇹\nPer cambiare: <code>/lingua en</code>",
        "en": "Current language: <b>English</b> 🇬🇧\nTo change: <code>/lang it</code>",
    },

    # ── Spazzatura ────────────────────────────────────────────────────────
    "trash_loading": {
        "it": "Lettura calendario in corso...",
        "en": "Reading calendar...",
    },
    "trash_unavailable": {
        "it": "Modulo spazzatura non disponibile.",
        "en": "Trash module not available.",
    },

    # ── Aggiornamenti ─────────────────────────────────────────────────────
    "checking_updates": {
        "it": "🔍 <b>Controllo aggiornamenti…</b>",
        "en": "🔍 <b>Checking for updates…</b>",
    },
    "error_update": {
        "it": "❌ Errore controllo: {msg}",
        "en": "❌ Update check error: {msg}",
    },

    # ── Riparazioni ───────────────────────────────────────────────────────
    "checking_repairs": {
        "it": "🔧 <b>Controllo riparazioni HA…</b>",
        "en": "🔧 <b>Checking HA repairs…</b>",
    },

    # ── Briefing ─────────────────────────────────────────────────────────
    "briefing_loading": {
        "it": "🎩 <b>Preparo il briefing…</b>",
        "en": "🎩 <b>Preparing briefing…</b>",
    },
    "briefing_unavailable": {
        "it": "❌ Morning briefing non disponibile.",
        "en": "❌ Morning briefing not available.",
    },

    # ── Card Lovelace ─────────────────────────────────────────────────────
    "card_luci_header": {
        "it": (
            "💡 <b>Room Lights Graph Card</b>\n"
            "Card interattiva con grafo animato delle luci per stanza."
        ),
        "en": (
            "💡 <b>Room Lights Graph Card</b>\n"
            "Interactive card with animated light graph per room."
        ),
    },

    "card_style_help": {
        "it": (
            "🎨 <b>Card stile <code>{style}</code></b>\n\n"
            "Fornisci le entità da includere nella card:\n\n"
            "<code>crea card {style}:\n"
            "type: entities\n"
            "title: Casa\n"
            "entities:\n"
            "  - light.soggiorno\n"
            "  - sensor.temperatura\n"
            "  - binary_sensor.porta_ingresso</code>\n\n"
            "💡 <i>Stili: mushroom · bubble · gauge · tile · energia</i>"
        ),
        "en": (
            "🎨 <b>Card style <code>{style}</code></b>\n\n"
            "Provide the entities to include in the card:\n\n"
            "<code>create card {style}:\n"
            "type: entities\n"
            "title: Home\n"
            "entities:\n"
            "  - light.living_room\n"
            "  - sensor.temperature\n"
            "  - binary_sensor.front_door</code>\n\n"
            "💡 <i>Styles: mushroom · bubble · gauge · tile · energy</i>"
        ),
    },

    "card_generating": {
        "it": "🎨 <b>Genero card {style}…</b> <i>(~20s)</i>",
        "en": "🎨 <b>Generating {style} card…</b> <i>(~20s)</i>",
    },

    "card_ready": {
        "it": (
            "✅ <b>Card {style} pronta!</b>\n"
            "📋 <i>Dashboard HA → ✏️ → + Aggiungi card → Manuale → incolla</i>"
        ),
        "en": (
            "✅ <b>{style} card ready!</b>\n"
            "📋 <i>HA Dashboard → ✏️ → + Add card → Manual → paste</i>"
        ),
    },

    "card_error": {
        "it": "❌ Errore generazione card: {msg}",
        "en": "❌ Card generation error: {msg}",
    },

    # ── Energia ───────────────────────────────────────────────────────────
    "energy_period_today": {
        "it": "oggi",
        "en": "today",
    },
    "energy_period_yesterday": {
        "it": "ieri",
        "en": "yesterday",
    },

    # ── Automazioni ───────────────────────────────────────────────────────
    "automation_creating": {
        "it": "⚙️ <b>Genero e installo l'automazione…</b>",
        "en": "⚙️ <b>Generating and installing automation…</b>",
    },
    "automation_editing": {
        "it": "✏️ <b>Modifico l'automazione…</b>",
        "en": "✏️ <b>Modifying automation…</b>",
    },
    "automation_delete_ask": {
        "it": "Dimmi il nome dell'automazione da eliminare.",
        "en": "Tell me the name of the automation to delete.",
    },

    # ── Stato casa ────────────────────────────────────────────────────────
    "home_status_header": {
        "it": "🏠 <b>Stato Casa</b>",
        "en": "🏠 <b>Home Status</b>",
    },
    "alarm_states": {
        "it": {
            "disarmed":     "🔓 Disarmato",
            "armed_away":   "🔒 Armato — Fuori",
            "armed_home":   "🏠 Armato — In casa",
            "armed_night":  "🌙 Armato — Notte",
            "triggered":    "🚨 ALLARME ATTIVATO",
            "arming":       "⏳ Attivazione...",
            "pending":      "⏳ In attesa...",
        },
        "en": {
            "disarmed":     "🔓 Disarmed",
            "armed_away":   "🔒 Armed Away",
            "armed_home":   "🏠 Armed Home",
            "armed_night":  "🌙 Armed Night",
            "triggered":    "🚨 ALARM TRIGGERED",
            "arming":       "⏳ Arming...",
            "pending":      "⏳ Pending...",
        },
    },
    "lights_on": {
        "it": "💡 <b>Luci accese ({n}):</b> {names}",
        "en": "💡 <b>Lights on ({n}):</b> {names}",
    },
    "lights_all_off": {
        "it": "💡 <b>Luci:</b> tutte spente",
        "en": "💡 <b>Lights:</b> all off",
    },

    # ── Comandi (lista) ───────────────────────────────────────────────────
    "commands_list": {
        "it": (
            "📋 <b>Tutti i comandi HomeMind</b>\n\n"
            "🏠 <b>Info Casa:</b>\n"
            "  /stato — stato completo casa\n"
            "  /energia — fotovoltaico e batteria oggi\n"
            "  /ieri — produzione e consumi di ieri\n\n"
            "⚡ <b>Elettrodomestici:</b>\n"
            "  /elettrodomestici — vedi tutto ciò che hai configurato e cosa sta facendo in questo momento\n\n"
            "📅 <b>Routine:</b>\n"
            "  /routine — cosa ho imparato sulla tua routine\n\n"
            "⚡ <b>Power Guard:</b>\n"
            "  /powerguard — stato e elettrodomestici monitorati\n"
            "  /pg — alias breve\n\n"
            "⏰ <b>Task Programmati:</b>\n"
            "  /task — lista task in coda\n"
            "  /cancella_task N — cancella task numero N\n"
            "  <i>Accendi luce alle 19</i> — programma un'azione\n"
            "  <i>Tra 30 min spegni le luci</i> — timer rapido\n\n"
            "🧠 <b>Memoria:</b>\n"
            "  /memoria — cosa so su di te\n"
            "  /dimentica &lt;testo&gt; — rimuovi un fatto dalla memoria\n"
            "  /memoria reset — cancella tutto e riparte da zero\n\n"
            "⚡ <b>Power Guard:</b>\n"
            "☀️ <b>Solare:</b>\n"
            "  /solare — surplus FV in tempo reale e stato ottimizzatore\n\n"
            "📍 <b>Posizioni:</b>\n"
            "  <i>dove ha sostato Mario</i> — soste significative di oggi\n"
            "  <i>dove è stata Rosa questa settimana</i> — ultimi 7 giorni\n\n"
            "📊 <b>Storico (scrivi in italiano):</b>\n"
            "  <i>Quante volte ha scattato il sensore cucina oggi?</i>\n"
            "  <i>Quando è arrivato Mario ieri?</i>\n\n"
            "⚙️ <b>Automazioni:</b>\n"
            "  /automazioni — lista tutte le automazioni\n"
            "  /automazioni_help — guida con esempi pratici\n\n"
            "🎨 <b>Card Lovelace:</b>\n"
            "  <code>crea card luci</code> → Room Lights Graph Card\n"
            "  <code>crea card energia</code> → produzione/consumo FV\n"
            "  <code>crea card mushroom:</code> → card moderne (HACS)\n"
            "  <code>crea card bubble:</code> → stile iOS (HACS)\n"
            "  <code>crea card gauge:</code> → gauge numerici\n"
            "  <code>crea card tile:</code> → tile native (zero HACS)\n\n"
            "🗑️ <b>Spazzatura:</b>\n"
            "  /spazzatura — raccolta prossimi 7 giorni\n"
            "  /ricarica_spazzatura — rileggi PDF calendario\n\n"
            "🔧 <b>Sistema:</b>\n"
            "  /aggiornamenti — controlla update HA\n"
            "  /riparazioni — problemi ufficiali HA\n"
            "  /briefing — riepilogo mattutino\n"
            "  /providers — provider AI attivi e fallback\n\n"
            "🌍 <b>Lingua:</b>\n"
            "  /lingua it — Italiano\n"
            "  /lingua en — English\n\n"
            "💬 <b>Controllo libero:</b>\n"
            "  <i>Accendi luce cucina</i>\n"
            "  <i>Arma l allarme</i>\n"
            "  <i>Quanta energia ho prodotto oggi?</i>"
        ),
        "en": (
            "📋 <b>All HomeMind commands</b>\n\n"
            "🏠 <b>Home Info:</b>\n"
            "  /stato — full home status\n"
            "  /energia — solar and battery today\n"
            "  /ieri — production and usage yesterday\n\n"
            "⚡ <b>Appliances:</b>\n"
            "  /elettrodomestici — see all configured appliances and what they are doing right now\n\n"
            "📅 <b>Routine:</b>\n"
            "  /routine — what I have learned about your routine\n\n"
            "⚡ <b>Power Guard:</b>\n"
            "  /powerguard — status and monitored appliances\n"
            "  /pg — short alias\n\n"
            "⏰ <b>Scheduled Tasks:</b>\n"
            "  /task — list scheduled tasks\n"
            "  /cancella_task N — cancel task number N\n"
            "  <i>Turn on light at 7pm</i> — schedule an action\n"
            "  <i>In 30 min turn off lights</i> — quick timer\n\n"
            "🧠 <b>Memory:</b>\n"
            "  /memoria — what I know about you\n"
            "  /dimentica &lt;text&gt; — remove a fact from memory\n"
            "  /memoria reset — clear everything and start over\n\n"
            "⚡ <b>Power Guard:</b>\n"
            "☀️ <b>Solar:</b>\n"
            "  /solare — real-time FV surplus and optimizer status\n\n"
            "📍 <b>Locations:</b>\n"
            "  <i>where has Mario been</i> — significant stops today\n"
            "  <i>where was Rosa this week</i> — last 7 days\n\n"
            "📊 <b>History (write in English):</b>\n"
            "  <i>How many times did the kitchen sensor trigger today?</i>\n"
            "  <i>When did Mario arrive yesterday?</i>\n\n"
            "⚙️ <b>Automations:</b>\n"
            "  /automazioni — list all automations\n"
            "  /automazioni_help — guide with examples\n\n"
            "🎨 <b>Lovelace Cards:</b>\n"
            "  <code>create card lights</code> → Room Lights Graph Card\n"
            "  <code>create card energy</code> → solar/consumption\n"
            "  <code>create card mushroom:</code> → modern cards (HACS)\n"
            "  <code>create card bubble:</code> → iOS style (HACS)\n"
            "  <code>create card gauge:</code> → numeric gauges\n"
            "  <code>create card tile:</code> → native tiles (no HACS)\n\n"
            "🗑️ <b>Trash:</b>\n"
            "  /spazzatura — next 7 days collection\n"
            "  /ricarica_spazzatura — re-read PDF calendar\n\n"
            "🔧 <b>System:</b>\n"
            "  /aggiornamenti — check HA updates\n"
            "  /riparazioni — official HA issues\n"
            "  /briefing — morning summary\n"
            "  /providers — active AI providers and fallback chain\n\n"
            "🌍 <b>Language:</b>\n"
            "  /lingua it — Italiano\n"
            "  /lingua en — English\n\n"
            "💬 <b>Free control:</b>\n"
            "  <i>Turn on kitchen light</i>\n"
            "  <i>Arm the alarm</i>\n"
            "  <i>How much energy did I produce today?</i>"
        ),
    },

    "auto_help": {
        "it": (
            "⚙️ <b>Guida Automazioni da Telegram</b>\n"
            "──────────────────────────────\n\n"
            "📋 <b>Lista:</b>\n"
            "  <code>/automazioni</code>\n\n"
            "✅ <b>Creare nuova automazione:</b>\n"
            "  <code>crea automazione [descrizione]</code>\n\n"
            "  Esempi:\n"
            "  → <i>crea automazione che spegne le luci alle 23:00</i>\n"
            "  → <i>crea automazione: accendi luce cucina al tramonto</i>\n\n"
            "✏️ <b>Modificare automazione esistente:</b>\n"
            "  <code>modifica automazione [nome] — [cosa cambiare]</code>\n\n"
            "  Esempi:\n"
            "  → <i>modifica automazione luci sera — aggiungi condizione: solo se Rosa e in casa</i>\n\n"
            "🗑️ <b>Eliminare automazione:</b>\n"
            "  <code>elimina automazione [nome]</code>\n\n"
            "⭕✅ <b>Attivare / Disattivare:</b>\n"
            "  <code>attiva automazione [nome]</code>\n"
            "  <code>disattiva automazione [nome]</code>\n\n"
            "──────────────────────────────\n"
            "💾 <i>Ogni modifica: backup automatico in</i>\n"
            "<code>/config/homemind_patches/</code>"
        ),
        "en": (
            "⚙️ <b>Automations Guide from Telegram</b>\n"
            "──────────────────────────────\n\n"
            "📋 <b>List:</b>\n"
            "  <code>/automations</code>\n\n"
            "✅ <b>Create new automation:</b>\n"
            "  <code>create automation [description]</code>\n\n"
            "  Examples:\n"
            "  → <i>create automation that turns off lights at 11pm</i>\n"
            "  → <i>create automation: turn on kitchen light at sunset</i>\n\n"
            "✏️ <b>Modify existing automation:</b>\n"
            "  <code>modify automation [name] — [what to change]</code>\n\n"
            "  Examples:\n"
            "  → <i>modify automation evening lights — add condition: only if Rosa is home</i>\n\n"
            "🗑️ <b>Delete automation:</b>\n"
            "  <code>delete automation [name]</code>\n\n"
            "⭕✅ <b>Enable / Disable:</b>\n"
            "  <code>enable automation [name]</code>\n"
            "  <code>disable automation [name]</code>\n\n"
            "──────────────────────────────\n"
            "💾 <i>Every change: automatic backup in</i>\n"
            "<code>/config/homemind_patches/</code>"
        ),
    },
}


# ── API pubblica ───────────────────────────────────────────────────────────────

def get_lang() -> str:
    """Restituisce la lingua corrente: 'it' o 'en'."""
    return _LANG


def set_lang(lang: str) -> bool:
    """
    Imposta la lingua globale. Salva in person_config.json se possibile.
    Returns True se la lingua è supportata.
    """
    global _LANG
    lang = lang.lower().strip()
    if lang not in ("it", "en"):
        return False
    _LANG = lang
    # Persisti
    try:
        import json
        from pathlib import Path
        cfg_path = Path("/config/homemind_patches/person_config.json")
        cfg = {}
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
        cfg["language"] = lang
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    except Exception:
        pass
    return True


def load_lang_from_config() -> None:
    """Carica la lingua salvata in person_config.json all'avvio."""
    global _LANG
    try:
        import json
        from pathlib import Path
        cfg_path = Path("/config/homemind_patches/person_config.json")
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            lang = cfg.get("language", "it").lower()
            if lang in ("it", "en"):
                _LANG = lang
    except Exception:
        pass


def t(key: str, **kwargs) -> str:
    """
    Restituisce la stringa tradotta per la lingua corrente.
    Supporta placeholder: t("card_generating", style="mushroom")
    Se la chiave non esiste, ritorna la chiave stessa (fail-safe).
    """
    entry = STRINGS.get(key)
    if entry is None:
        return key  # fail-safe: mostra la chiave
    lang = _LANG if _LANG in ("it", "en") else "it"
    text = entry.get(lang) or entry.get("it") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def alarm_state_label(state: str) -> str:
    """Restituisce l'etichetta localizzata per lo stato allarme."""
    lang = _LANG if _LANG in ("it", "en") else "it"
    mapping = STRINGS["alarm_states"].get(lang, STRINGS["alarm_states"]["it"])
    return mapping.get(state, state)
