"""
agent/shortcuts_manager.py — Alias comandi deterministici.

Permette all'utente di memorizzare parole chiave personalizzate
che attivano azioni precise SENZA passare dall'AI.

Tipi di azione supportati:
  - sensor: leggi valore di un sensore HA  (sensor.xxx)
  - command: esegui un comando HomeMind   (/energia, /solare, ecc.)
  - state:   leggi stato di un'entità     (light.xxx, switch.xxx, cover.xxx)

Comandi Telegram:
  "memorizza che batteria fotovoltaico = sensor.inverter_pipsolar_battery_capacity_percent"
  "memorizza che info energia = /energia"
  "alias" o "i miei alias" → lista alias configurati
  "dimentica alias batteria fotovoltaico" → rimuove alias
  "cancella tutti gli alias" → reset completo
"""

import json
import logging
import re
import time
from pathlib import Path

logger = logging.getLogger("homemind.shortcuts")

SHORTCUTS_PATH = Path("/data/homemind_shortcuts.json")

# Comandi HomeMind validi come destinazione
VALID_COMMANDS = {
    "/energia", "energia", "produzione",
    "/solare", "solare", "fotovoltaico",
    "/config", "config",
    "/briefing", "briefing",
    "/routine", "routine",
    "/memoria", "memoria",
    "/stato", "stato",
    "/powerguard", "powerguard",
    "/repairs", "riparazioni",
    "/spazzatura", "spazzatura",
    "/aggiornamenti", "aggiornamenti",
    "/task", "task",
}


class ShortcutsManager:
    """Gestisce alias comandi deterministici."""

    def __init__(self, state_cache_cb=None):
        self._state_cache_cb = state_cache_cb
        self._shortcuts: list[dict] = []
        self._load()

    # ─────────────────────────────────────────────────────────────────────────
    # Persistenza

    def _load(self):
        try:
            if SHORTCUTS_PATH.exists():
                data = json.loads(SHORTCUTS_PATH.read_text())
                self._shortcuts = data.get("shortcuts", [])
                logger.info("Shortcuts caricati: %d alias", len(self._shortcuts))
            else:
                self._shortcuts = []
        except Exception as e:
            logger.warning("Shortcuts load error: %s", e)
            self._shortcuts = []

    def _save(self):
        try:
            SHORTCUTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SHORTCUTS_PATH.write_text(json.dumps(
                {"shortcuts": self._shortcuts, "updated": time.time()},
                indent=2, ensure_ascii=False
            ))
        except Exception as e:
            logger.warning("Shortcuts save error: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Parsing richiesta di memorizzazione

    def parse_memorize_request(self, text: str):
        """
        Interpreta comandi tipo:
          "memorizza che batteria fotovoltaico = sensor.inverter_pipsolar_battery_capacity_percent"
          "alias info energia = /energia"
          "quando dico batteria solare mostrami sensor.xxx"
        
        Ritorna dict {keyword, action_type, action_value} oppure None.
        """
        t = text.strip()
        t_low = t.lower()

        # Deve iniziare con una parola trigger
        TRIGGERS = [
            "memorizza che", "memorizza quando chiedo", "memorizza quando dico",
            "memorizza quando", "memorizza se chiedo", "memorizza se",
            "memorizza sempre", "memorizza:", "memorizza",
            "alias", "quando dico", "quando chiedo",
            "memorize", "remember",
        ]
        matched_trigger = None
        for tr in TRIGGERS:
            if t_low.startswith(tr):
                matched_trigger = tr
                t = t[len(tr):].strip()
                break
        
        if not matched_trigger:
            return None

        # Rimuovi parole introduttive residue dopo il trigger
        import re as _re_strip
        t = _re_strip.sub(r"^(?:chiedo|dico|si\s+dice|si\s+chiede)\s+", "", t, flags=_re_strip.IGNORECASE).strip()

        # Cerca il separatore = o → o "=" o "mostrami" o "apri"
        sep_patterns = [
            r"(.+?)\s*[=→]\s*(.+)",          # keyword = valore
            r"(.+?)\s+mostrami\s+(.+)",       # keyword mostrami sensor.xxx
            r"(.+?)\s+apri\s+(.+)",           # keyword apri /energia
            r"(.+?)\s+leggi\s+(.+)",          # keyword leggi sensor.xxx
            r"(.+?)\s+dimmi\s+(.+)",          # keyword dimmi sensor.xxx
        ]

        keyword = None
        value = None
        for pat in sep_patterns:
            m = re.match(pat, t, re.IGNORECASE)
            if m:
                keyword = m.group(1).strip().lower()
                value   = m.group(2).strip()
                break

        if not keyword or not value:
            # Prova formato semplice: "keyword sensor.xxx"
            parts = t.strip().split()
            if len(parts) >= 2:
                # Controlla se l'ultimo elemento è un entity_id o comando
                last = parts[-1]
                if "." in last or last.startswith("/"):
                    keyword = " ".join(parts[:-1]).lower().strip()
                    value   = last

        if not keyword or not value:
            return None

        # Rimuovi virgolette attorno alla keyword se presenti
        keyword = keyword.strip("'\"").strip()
        value   = value.strip("'\"").strip()

        if not keyword or not value:
            return None

        # Determina il tipo di azione
        # Controlla se ci sono più entità separate da virgola
        _values = [v.strip() for v in value.split(",") if v.strip()]
        _first  = _values[0] if _values else value

        if _first.startswith("/") or _first.lower() in VALID_COMMANDS:
            action_type = "command"
            value = _first  # i comandi non supportano multi-valore
        elif re.match(r"^(light|switch|cover|climate|media_player|fan|lock|alarm_control_panel)\." + r"\S+$", _first):
            action_type = "state" if len(_values) == 1 else "multi_sensor"
        elif re.match(r"^\S+\.\S+$", _first):  # qualsiasi entity_id con punto
            action_type = "multi_sensor" if len(_values) > 1 else "sensor"
        else:
            action_type = "sensor"  # default

        return {
            "keyword":      keyword,
            "action_type":  action_type,
            "action_value": value,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Gestione alias

    def add_shortcut(self, keyword: str, action_type: str, action_value: str) -> str:
        """Aggiunge un alias. Sostituisce se la keyword esiste già."""
        keyword = keyword.lower().strip()
        
        # Rimuovi eventuale alias esistente con la stessa keyword
        self._shortcuts = [s for s in self._shortcuts if s["keyword"] != keyword]
        
        self._shortcuts.append({
            "keyword":      keyword,
            "action_type":  action_type,
            "action_value": action_value,
            "ts":           time.time(),
        })
        self._save()
        
        n = len(self._shortcuts)
        type_icons = {"sensor": "📡", "command": "⚡", "state": "🔌", "multi_sensor": "📊"}
        icon = type_icons.get(action_type, "🔗")
        eids = [e.strip() for e in action_value.split(",") if e.strip()]
        if len(eids) > 1:
            val_preview = "\n".join(f"    • <code>{e}</code>" for e in eids)
            return (
                f"✅ Alias #{n} memorizzato ({len(eids)} sensori):\n"
                f"  {icon} <b>\"{keyword}\"</b>\n{val_preview}\n\n"
                f"Scrivi <b>{keyword}</b> per leggerli tutti.\n"
                f"Per rimuoverlo: <code>dimentica alias {n}</code>"
            )
        return (
            f"✅ Alias #{n} memorizzato:\n"
            f"  {icon} <b>\"{keyword}\"</b> → <code>{action_value}</code>\n\n"
            f"Scrivi <b>{keyword}</b> per eseguirlo.\n"
            f"Per rimuoverlo: <code>dimentica alias {n}</code>"
        )

    def remove_shortcut(self, keyword: str) -> str:
        """Rimuove un alias per keyword o per numero (es: '1', '2')."""
        keyword = keyword.lower().strip()

        # Rimozione per numero
        if keyword.isdigit():
            idx = int(keyword) - 1  # 1-based
            if 0 <= idx < len(self._shortcuts):
                removed = self._shortcuts.pop(idx)
                self._save()
                return f"✅ Alias #{idx+1} <b>\"{removed['keyword']}\"</b> rimosso."
            return f"⚠️ Numero non valido. Hai {len(self._shortcuts)} alias (usa /alias per vederli)."

        # Rimozione per keyword
        before = len(self._shortcuts)
        self._shortcuts = [s for s in self._shortcuts if s["keyword"] != keyword]
        if len(self._shortcuts) < before:
            self._save()
            return f"✅ Alias <b>\"{keyword}\"</b> rimosso."
        return f"⚠️ Nessun alias trovato per <b>\"{keyword}\"</b>"

    def reset(self) -> str:
        count = len(self._shortcuts)
        self._shortcuts = []
        self._save()
        return f"✅ Rimossi tutti gli alias ({count} totali)."

    def get_display(self) -> str:
        """Testo per /alias o equivalente."""
        if not self._shortcuts:
            return (
                "🔗 <b>Nessun alias configurato</b>\n\n"
                "Puoi memorizzare comandi rapidi personalizzati:\n"
                "  • <code>memorizza che batteria solare = sensor.xxx</code>\n"
                "  • <code>memorizza che info energia = /energia</code>\n"
                "  • <code>alias percentuale batteria = sensor.inverter_pipsolar_battery_capacity_percent</code>"
            )
        
        lines = [f"🔗 <b>I tuoi alias</b> ({len(self._shortcuts)})\n"]
        type_icons = {"sensor": "📡", "command": "⚡", "state": "🔌"}
        for i, s in enumerate(self._shortcuts, 1):
            icon = type_icons.get(s["action_type"], "🔗")
            _eids = [e.strip() for e in s["action_value"].split(",") if e.strip()]
            if len(_eids) > 1:
                # Mostra solo il primo sensore e quanti altri ci sono
                _first_short = _eids[0].split(".")[-1][:25]  # solo la parte dopo il punto
                val_str = f"<code>{_first_short}</code> +{len(_eids)-1} sensori"
            else:
                val_str = f"<code>{s['action_value']}</code>"
            lines.append(f"  <b>{i}.</b> {icon} <b>\"{s['keyword']}\"</b> → {val_str}")
        
        lines.append("\n<i>Usa 'dimentica alias &lt;keyword&gt;' per rimuovere un alias</i>")
        lines.append("<i>Usa 'cancella tutti gli alias' per resettare</i>")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Esecuzione alias

    # Prefissi che indicano gestione alias — NON eseguire come shortcut
    _MGMT_PREFIXES = (
        "memorizza", "alias ", "quando dico", "quando chiedo",
        "dimentica alias", "rimuovi alias", "cancella alias",
        "cancella tutti", "reset alias", "clear alias",
        "remember ", "memorize ",
    )

    def match(self, text: str):
        """
        Controlla se il testo corrisponde a un alias.
        Ritorna il dict shortcut o None.
        Ignora frasi di gestione (memorizza, dimentica alias, ecc.)
        """
        t = text.lower().strip()

        # NON matchare frasi di gestione alias
        if any(t.startswith(p) for p in self._MGMT_PREFIXES):
            return None

        # Prima: match esatto
        for s in self._shortcuts:
            if t == s["keyword"]:
                return s

        # Secondo: la keyword è contenuta nel messaggio come parola intera
        for s in self._shortcuts:
            kw = re.escape(s["keyword"])
            if re.search(rf"\b{kw}\b", t):
                return s

        return None

    async def execute(self, shortcut: dict, state_cache: dict = None) -> str:
        """Esegue un alias e restituisce la risposta pronta."""
        action_type  = shortcut["action_type"]
        action_value = shortcut["action_value"]
        keyword      = shortcut["keyword"]

        if action_type in ("sensor", "multi_sensor"):
            # Supporta più sensori separati da virgola
            eids = [e.strip() for e in action_value.split(",") if e.strip()]
            if len(eids) == 1:
                return self._read_sensor(eids[0], keyword, state_cache)
            else:
                lines = [f"📊 <b>{keyword.title()}</b>\n"]
                for eid in eids:
                    lines.append(self._read_sensor(eid, eid, state_cache))
                return "\n".join(lines)

        elif action_type == "state":
            eids = [e.strip() for e in action_value.split(",") if e.strip()]
            if len(eids) == 1:
                return self._read_state(eids[0], keyword, state_cache)
            else:
                lines = [f"📊 <b>{keyword.title()}</b>\n"]
                for eid in eids:
                    lines.append(self._read_state(eid, eid, state_cache))
                return "\n".join(lines)

        elif action_type == "command":
            # Ritorna il comando come segnale per il bot
            return f"__SHORTCUT_CMD__{action_value}"
        
        return f"⚠️ Tipo azione non supportato: {action_type}"

    def _read_sensor(self, entity_id: str, keyword: str, cache: dict) -> str:
        """Legge il valore di un sensore dalla cache HA."""
        if not cache:
            return f"⚠️ Cache HA non disponibile"
        
        s = cache.get(entity_id)
        if not s:
            return (
                f"⚠️ Sensore <code>{entity_id}</code> non trovato in HA.\n"
                f"Verifica l\'entity_id in HA → Strumenti Sviluppo → Stati"
            )
        
        state = s.get("state", "?")
        attrs = s.get("attributes", {})
        name  = attrs.get("friendly_name", entity_id)
        unit  = attrs.get("unit_of_measurement", "")
        dc    = attrs.get("device_class", "")
        
        if state in ("unavailable", "unknown"):
            return f"⚠️ <b>{name}</b>: {state} (sensore non raggiungibile)"
        
        # Icona in base al device_class
        icons = {
            "battery": "🔋", "power": "⚡", "energy": "⚡",
            "temperature": "🌡️", "humidity": "💧", "voltage": "🔌",
            "current": "🔌", "solar": "☀️",
        }
        icon = icons.get(dc, "📡")
        
        return f"{icon} <b>{name}</b>: <b>{state}{' ' + unit if unit else ''}</b>"

    def _read_state(self, entity_id: str, keyword: str, cache: dict) -> str:
        """Legge lo stato di un'entità."""
        if not cache:
            return f"⚠️ Cache HA non disponibile"
        
        s = cache.get(entity_id)
        if not s:
            return f"⚠️ Entità <code>{entity_id}</code> non trovata in HA"
        
        state = s.get("state", "?")
        name  = s.get("attributes", {}).get("friendly_name", entity_id)
        
        state_map = {
            "on": "✅ acceso", "off": "⭕ spento",
            "open": "🔓 aperto", "closed": "🔒 chiuso",
            "home": "🏠 in casa", "not_home": "🚗 fuori casa",
        }
        readable = state_map.get(state.lower(), state)
        return f"🔌 <b>{name}</b>: {readable}"