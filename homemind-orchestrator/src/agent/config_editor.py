"""
agent/config_editor.py — Editor configurazione via chat Telegram.

Permette di modificare person_config.json scrivendo in linguaggio naturale
su Telegram, senza toccare file, senza riavviare HomeMind.

Modifiche supportate:
  - Aggiungere/rimuovere persone (whitelist/blacklist)
  - Cambiare soglia Power Guard
  - Aggiungere/modificare elettrodomestici
  - Cambiare orario notifica spazzatura
  - Aggiungere sensore proximity
  - Cambiare lingua
  - Modificare parametri clima

Flusso:
  1. Utente scrive "HomeMind, aggiungi person.mario alla whitelist"
  2. ConfigEditor riconosce l'intenzione
  3. Mostra l'anteprima della modifica
  4. Aspetta conferma (sì/no)
  5. Applica e conferma

Comandi Telegram:
  /config          — mostra config attuale (leggibile)
  /config reset    — ripristina config di default (con conferma)
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("homemind.config_editor")

CONFIG_PATH  = Path("/config/homemind_patches/person_config.json")
BACKUP_PATH  = Path("/config/homemind_patches/person_config.backup.json")
CONFIRM_TTL  = 120   # secondi per confermare


class ConfigEditor:
    def __init__(self, notifier=None, lang_cb=None, home_reload_cb=None):
        self.notifier        = notifier
        self._lang_cb        = lang_cb
        self._home_reload_cb = home_reload_cb   # callback per ricaricare HomeModel
        self._pending: Optional[dict] = None    # modifica in attesa di conferma
        self._pending_ts     = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Lettura config

    def _load(self) -> dict:
        try:
            if CONFIG_PATH.exists():
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except Exception as e:
            logger.warning("ConfigEditor load error: %s", e)
        return {}

    def _save(self, cfg: dict) -> bool:
        try:
            # Backup prima di salvare
            if CONFIG_PATH.exists():
                BACKUP_PATH.write_text(
                    CONFIG_PATH.read_text(encoding="utf-8-sig"),
                    encoding="utf-8"
                )
            CONFIG_PATH.write_text(
                json.dumps(cfg, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.info("ConfigEditor: config salvato (backup in %s)", BACKUP_PATH)
            return True
        except Exception as e:
            logger.error("ConfigEditor save error: %s", e)
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Riconoscimento intenzione

    def detect_intent(self, text: str) -> Optional[dict]:
        """
        Riconosce se il testo è una richiesta di modifica config.
        Ritorna un dict con {action, params, preview} o None.
        """
        t = text.lower().strip()

        # ── Whitelist persone ─────────────────────────────────────────────
        m = re.search(
            r'aggiungi\s+(person\.\w+)|add\s+(person\.\w+)',
            t
        )
        if m and ('whitelist' in t or 'persona' in t or 'persone' in t or 'person' in t):
            eid = m.group(1) or m.group(2)
            return {
                "action": "whitelist_add",
                "eid": eid,
                "preview": f"Aggiungo <b>{eid}</b> alla whitelist persone"
            }

        # ── Blacklist persone ─────────────────────────────────────────────
        m = re.search(
            r'(escludi|blacklist|ignora|rimuovi)\s+(person\.\w+)|'
            r'(exclude|blacklist|remove)\s+(person\.\w+)',
            t
        )
        if m:
            eid = m.group(2) or m.group(4)
            if eid:
                return {
                    "action": "blacklist_add",
                    "eid": eid,
                    "preview": f"Aggiungo <b>{eid}</b> alla blacklist persone"
                }

        # ── Rimuovi da whitelist ──────────────────────────────────────────
        m = re.search(
            r'(rimuovi|togli|elimina)\s+(person\.\w+)|'
            r'(remove|delete)\s+(person\.\w+)',
            t
        )
        if m and ('whitelist' in t or 'persone' in t):
            eid = m.group(2) or m.group(4)
            if eid:
                return {
                    "action": "whitelist_remove",
                    "eid": eid,
                    "preview": f"Rimuovo <b>{eid}</b> dalla whitelist persone"
                }

        # ── Soglia Power Guard ────────────────────────────────────────────
        m = re.search(
            r'(?:soglia|threshold|limite).*?(\d{3,5})\s*[wW]|'
            r'(\d{3,5})\s*[wW].*(?:soglia|threshold|enel|limite)',
            t
        )
        if m and any(k in t for k in ('power', 'soglia', 'enel', 'guard', 'watt')):
            w = int(m.group(1) or m.group(2))
            if 500 <= w <= 15000:
                return {
                    "action": "power_guard_threshold",
                    "value": w,
                    "preview": f"Cambio soglia Power Guard a <b>{w}W</b>"
                }

        # ── Modalità Power Guard ──────────────────────────────────────────
        for mode in ('auto', 'ask', 'warn_only'):
            if mode in t and any(k in t for k in ('power', 'guard', 'modalit')):
                labels = {
                    'auto': 'automatico (spegne senza chiedere)',
                    'ask': 'chiede conferma prima di spegnere',
                    'warn_only': 'solo notifica, non spegne'
                }
                return {
                    "action": "power_guard_mode",
                    "value": mode,
                    "preview": f"Cambio modalità Power Guard: <b>{labels[mode]}</b>"
                }

        # ── Orario spazzatura ─────────────────────────────────────────────
        m = re.search(
            r'(?:spazzatura|trash|rifiuti).*?(\d{1,2})(?::00)?|'
            r'(\d{1,2})(?::00)?.*(?:spazzatura|trash|rifiuti)',
            t
        )
        if m:
            hour = int(m.group(1) or m.group(2))
            if 0 <= hour <= 23:
                return {
                    "action": "trash_hour",
                    "value": hour,
                    "preview": f"Cambio orario notifica spazzatura alle <b>{hour:02d}:00</b>"
                }

        # ── Lingua ────────────────────────────────────────────────────────
        if re.search(r'\b(lingua|language)\b', t):
            if 'ingles' in t or 'english' in t or ' en' in t:
                return {
                    "action": "language",
                    "value": "en",
                    "preview": "Cambio lingua a <b>English</b>"
                }
            if 'italian' in t or 'italian' in t or ' it' in t:
                return {
                    "action": "language",
                    "value": "it",
                    "preview": "Cambio lingua a <b>Italiano</b>"
                }

        # ── Soglia proximity ──────────────────────────────────────────────
        m = re.search(
            r'(?:soglia|threshold|raggio|distanza).*?(\d+)\s*m\b|'
            r'(\d+)\s*m\b.*(?:soglia|proximity|distanza)',
            t
        )
        if m and 'proximit' in t:
            meters = int(m.group(1) or m.group(2))
            if 10 <= meters <= 1000:
                # Trova la persona
                mp = re.search(r'person\.\w+', t)
                person = mp.group(0) if mp else None
                return {
                    "action": "proximity_threshold",
                    "person": person,
                    "value": meters,
                    "preview": (
                        f"Cambio soglia proximity"
                        f"{' di ' + person if person else ''} a <b>{meters}m</b>"
                    )
                }

        # ── Temperature clima ─────────────────────────────────────────────
        m = re.search(r'(?:max|massima).*?(\d{1,2})\s*°?|(\d{1,2})\s*°?.*(?:max|massima)', t)
        if m and any(k in t for k in ('clima', 'termostato', 'temperatura', 'climate')):
            temp = int(m.group(1) or m.group(2))
            if 15 <= temp <= 35:
                return {
                    "action": "climate_max_temp",
                    "value": temp,
                    "preview": f"Cambio temperatura massima clima a <b>{temp}°C</b>"
                }

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Applicazione modifiche

    def _apply(self, intent: dict) -> tuple[bool, str]:
        """
        Applica la modifica al config.
        Ritorna (success, message).
        """
        cfg = self._load()
        action = intent["action"]

        try:
            if action == "whitelist_add":
                eid = intent["eid"]
                wl = cfg.get("person_whitelist", [])
                if eid in wl:
                    return False, f"⚠️ {eid} è già nella whitelist"
                wl.append(eid)
                cfg["person_whitelist"] = wl
                msg = f"✅ <b>{eid}</b> aggiunto alla whitelist"

            elif action == "blacklist_add":
                eid = intent["eid"]
                bl = cfg.get("person_blacklist", [])
                if eid in bl:
                    return False, f"⚠️ {eid} è già nella blacklist"
                bl.append(eid)
                cfg["person_blacklist"] = bl
                msg = f"✅ <b>{eid}</b> aggiunto alla blacklist"

            elif action == "whitelist_remove":
                eid = intent["eid"]
                wl = cfg.get("person_whitelist", [])
                if eid not in wl:
                    return False, f"⚠️ {eid} non trovato nella whitelist"
                wl.remove(eid)
                cfg["person_whitelist"] = wl
                msg = f"✅ <b>{eid}</b> rimosso dalla whitelist"

            elif action == "power_guard_threshold":
                w = intent["value"]
                if "power_guard" not in cfg:
                    cfg["power_guard"] = {}
                old = cfg["power_guard"].get("threshold_w", "?")
                cfg["power_guard"]["threshold_w"] = w
                msg = f"✅ Soglia Power Guard: {old}W → <b>{w}W</b>"

            elif action == "power_guard_mode":
                mode = intent["value"]
                if "power_guard" not in cfg:
                    cfg["power_guard"] = {}
                old = cfg["power_guard"].get("mode", "?")
                cfg["power_guard"]["mode"] = mode
                labels = {'auto': 'Automatico', 'ask': 'Chiede conferma', 'warn_only': 'Solo notifica'}
                msg = f"✅ Modalità Power Guard: {old} → <b>{labels.get(mode, mode)}</b>"

            elif action == "trash_hour":
                h = intent["value"]
                old = cfg.get("spazzatura_notify_hour", "?")
                cfg["spazzatura_notify_hour"] = h
                msg = f"✅ Notifica spazzatura: {old}:00 → <b>{h:02d}:00</b>"

            elif action == "language":
                lang = intent["value"]
                old = cfg.get("language", "?")
                cfg["language"] = lang
                msg = f"✅ Lingua: {old} → <b>{lang}</b>"

            elif action == "proximity_threshold":
                meters = intent["value"]
                person = intent.get("person")
                proxs = cfg.get("proximity_sensors", {})
                if person and person in proxs:
                    old = proxs[person].get("threshold_m", "?")
                    proxs[person]["threshold_m"] = meters
                    cfg["proximity_sensors"] = proxs
                    msg = f"✅ Soglia proximity {person}: {old}m → <b>{meters}m</b>"
                elif proxs:
                    # Applica alla prima persona trovata
                    first = list(proxs.keys())[0]
                    old = proxs[first].get("threshold_m", "?")
                    proxs[first]["threshold_m"] = meters
                    cfg["proximity_sensors"] = proxs
                    msg = f"✅ Soglia proximity {first}: {old}m → <b>{meters}m</b>"
                else:
                    return False, "⚠️ Nessun sensore proximity configurato"

            elif action == "climate_max_temp":
                temp = intent["value"]
                climate = cfg.get("climate", {})
                if not climate:
                    return False, "⚠️ Nessun clima configurato"
                updated = []
                for eid, clm in climate.items():
                    old = clm.get("max_temp", "?")
                    clm["max_temp"] = temp
                    updated.append(f"{clm.get('name', eid)}: {old}° → {temp}°")
                cfg["climate"] = climate
                msg = "✅ Temperatura massima clima aggiornata:\n" + "\n".join(updated)

            else:
                return False, f"⚠️ Azione non riconosciuta: {action}"

            # Salva
            if self._save(cfg):
                # Ricarica HomeModel se possibile
                if self._home_reload_cb:
                    try:
                        self._home_reload_cb()
                    except Exception as e:
                        logger.warning("ConfigEditor: reload home error: %s", e)
                return True, msg
            else:
                return False, "❌ Errore nel salvataggio del config"

        except Exception as e:
            logger.error("ConfigEditor apply error: %s", e)
            return False, f"❌ Errore: {e}"

    # ─────────────────────────────────────────────────────────────────────────
    # Gestione conferme Telegram

    def set_pending(self, intent: dict):
        self._pending    = intent
        self._pending_ts = time.time()

    async def handle_confirm(self, text: str) -> bool:
        """Intercetta sì/no per conferma modifica. Ritorna True se gestito."""
        if not self._pending:
            return False
        if time.time() - self._pending_ts > CONFIRM_TTL:
            self._pending = None
            return False

        t = text.lower().strip()
        is_yes = t in ("sì", "si", "yes", "ok", "conferma", "applica", "vai")
        is_no  = t in ("no", "annulla", "cancel", "stop", "lascia perdere")

        if not (is_yes or is_no):
            return False

        intent = self._pending
        self._pending = None
        lang = self._lang_cb() if self._lang_cb else "it"

        if is_no:
            msg = "👍 Modifica annullata." if lang == "it" else "👍 Change cancelled."
            if self.notifier:
                await self.notifier.send_html(msg)
            return True

        # Applica
        ok, result_msg = self._apply(intent)
        if self.notifier:
            await self.notifier.send_html(result_msg)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Display /config

    def get_config_display(self) -> str:
        """Mostra il config attuale in formato leggibile."""
        cfg = self._load()
        lang = self._lang_cb() if self._lang_cb else "it"

        if not cfg:
            return "⚠️ Config non trovato."

        lines = ["⚙️ <b>Configurazione HomeMind</b>\n"]

        # Persone
        wl = cfg.get("person_whitelist", [])
        bl = cfg.get("person_blacklist", [])
        lines.append("👤 <b>Persone monitorate:</b>")
        for p in wl:
            lines.append(f"  ✅ {p}")
        if bl:
            lines.append("👤 <b>Persone escluse:</b>")
            for p in bl:
                lines.append(f"  ❌ {p}")

        # Lingua
        lang_val = cfg.get("language", "it")
        lines.append(f"\n🌍 <b>Lingua:</b> {lang_val.upper()}")

        # Clima
        climate = cfg.get("climate", {})
        if climate:
            lines.append("\n🌡️ <b>Clima:</b>")
            for eid, clm in climate.items():
                name = clm.get("name", eid)
                mn = clm.get("min_temp", "?")
                mx = clm.get("max_temp", "?")
                sw = clm.get("switch", "")
                sw_str = f" | switch: {sw}" if sw else ""
                lines.append(f"  • {name}: {mn}°–{mx}°{sw_str}")

        # Power Guard
        pg = cfg.get("power_guard", {})
        if pg and pg.get("enabled"):
            mode_labels = {
                'auto': 'Automatico', 'ask': 'Chiede conferma', 'warn_only': 'Solo notifica'
            }
            mode = mode_labels.get(pg.get("mode", "ask"), pg.get("mode", "?"))
            lines.append(f"\n⚡ <b>Power Guard:</b> {pg.get('threshold_w', '?')}W | {mode}")
            apps = pg.get("appliances_priority") or pg.get("appliances", [])
            for a in apps:
                lines.append(f"  • {a.get('name', '?')}")

        # Spazzatura
        if cfg.get("spazzatura_notify_enabled"):
            h = cfg.get("spazzatura_notify_hour", 20)
            lines.append(f"\n🗑️ <b>Spazzatura:</b> notifica alle {h:02d}:00")

        # Proximity
        proxs = cfg.get("proximity_sensors", {})
        if proxs:
            lines.append("\n📍 <b>Proximity:</b>")
            for person, ps in proxs.items():
                lines.append(f"  • {person}: soglia {ps.get('threshold_m', '?')}m")

        lines.append(
            "\n<i>💡 Puoi modificare la configurazione scrivendo in modo naturale.\n"
            "Esempi:\n"
            "  \"Aggiungi person.mario alla whitelist\"\n"
            "  \"Cambia soglia Enel a 3500W\"\n"
            "  \"Notifica spazzatura alle 21\"</i>"
        )

        return "\n".join(lines)
