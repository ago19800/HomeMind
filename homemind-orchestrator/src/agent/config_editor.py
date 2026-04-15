"""
agent/config_editor.py — Editor configurazione via chat Telegram.

Permette di modificare person_config.json scrivendo in linguaggio naturale
su Telegram, senza toccare file, senza riavviare HomeMind.

Supporta wizard interattivi multi-step per configurazioni complesse:
  - Aggiungere sensore proximity con entity, soglia, stale_check
  - Aggiungere elettrodomestico a power_guard con tutti i parametri
  - Aggiungere elettrodomestico monitorato (appliances)
  - Modificare delay_minutes power_guard

Modifiche semplici (senza wizard):
  - Aggiungere/rimuovere persone whitelist/blacklist
  - Cambiare soglia/modalità Power Guard
  - Cambiare orario spazzatura
  - Cambiare lingua
  - Temperatura max clima
  - Delay notifica Power Guard

Comandi Telegram:
  /config          — mostra config attuale
  /config reset    — ripristina backup
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
CONFIRM_TTL  = 300   # secondi per completare un wizard


class ConfigEditor:
    def __init__(self, notifier=None, lang_cb=None, home_reload_cb=None):
        self.notifier        = notifier
        self._lang_cb        = lang_cb
        self._home_reload_cb = home_reload_cb
        self._pending: Optional[dict] = None    # modifica semplice in attesa di conferma
        self._pending_ts     = 0.0
        self._wizard: Optional[dict] = None     # wizard multi-step attivo
        self._wizard_ts      = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Lettura / scrittura config

    def _load(self) -> dict:
        try:
            if CONFIG_PATH.exists():
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except Exception as e:
            logger.warning("ConfigEditor load error: %s", e)
        return {}

    def _save(self, cfg: dict) -> bool:
        try:
            if CONFIG_PATH.exists():
                BACKUP_PATH.write_text(
                    CONFIG_PATH.read_text(encoding="utf-8-sig"),
                    encoding="utf-8"
                )
            CONFIG_PATH.write_text(
                json.dumps(cfg, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.info("ConfigEditor: config salvato")
            return True
        except Exception as e:
            logger.error("ConfigEditor save error: %s", e)
            return False

    def _lang(self) -> str:
        return self._lang_cb() if self._lang_cb else "it"

    # ─────────────────────────────────────────────────────────────────────────
    # Rilevamento intenzione (modifiche semplici)

    def detect_intent(self, text: str) -> Optional[dict]:
        t = text.lower().strip()

        # Whitelist
        m = re.search(r'aggiungi\s+(person\.\w+)|add\s+(person\.\w+)', t)
        if m and any(k in t for k in ('whitelist', 'persona', 'persone', 'person')):
            eid = m.group(1) or m.group(2)
            return {"action": "whitelist_add", "eid": eid,
                    "preview": f"Aggiungo <b>{eid}</b> alla whitelist persone"}

        # Blacklist
        m = re.search(r'(escludi|blacklist|ignora)\s+(person\.\w+)|'
                      r'(exclude|blacklist|remove)\s+(person\.\w+)', t)
        if m:
            eid = m.group(2) or m.group(4)
            if eid:
                return {"action": "blacklist_add", "eid": eid,
                        "preview": f"Aggiungo <b>{eid}</b> alla blacklist"}

        # Rimuovi da whitelist
        m = re.search(r'(rimuovi|togli|elimina)\s+(person\.\w+).*whitelist|'
                      r'(remove|delete)\s+(person\.\w+).*whitelist', t)
        if m:
            eid = m.group(2) or m.group(4)
            if eid:
                return {"action": "whitelist_remove", "eid": eid,
                        "preview": f"Rimuovo <b>{eid}</b> dalla whitelist"}

        # Soglia Power Guard
        _soglia_pats = [
            r"soglia[^0-9]*([0-9]{2,5})\s*[wW]",
            r"([0-9]{2,5})\s*[wW][^0-9]*(?:soglia|threshold|enel|power|guard|limite)",
            r"(?:cambia|imposta|setta|metti)\s+soglia[^0-9]*([0-9]{2,5})\s*[wW]",
        ]
        _soglia_m = next((re.search(p, t) for p in _soglia_pats if re.search(p, t)), None)
        if _soglia_m and any(k in t for k in ("power", "soglia", "enel", "guard", "watt", "cambia", "imposta", "threshold")):
            grp = next((g for g in _soglia_m.groups() if g is not None), None)
            if grp:
                w = int(grp)
                if 100 <= w <= 15000:
                    return {"action": "power_guard_threshold", "value": w,
                            "preview": f"Cambio soglia Power Guard a <b>{w}W</b>"}

        # Delay Power Guard — pattern ampio
        m = re.search(r'(?:delay|attendi|aspetta|ritardo|aggiungi|metti)\s*(?:un\s*)?(\d+)\s*(?:min|minut)|'
                      r'(\d+)\s*(?:min|minut).*(?:delay|attesa|prima\s*di\s*notif|power|guard)', t)
        if not m:
            m = re.search(r'power.?guard.*?(\d+)\s*min|(\d+)\s*min.*?power.?guard', t)
        if m:
            mins = int(m.group(1) or m.group(2) or 0)
            if 0 <= mins <= 60:
                return {"action": "power_guard_delay", "value": mins,
                        "preview": f"Power Guard: attendi <b>{mins} minuti</b> prima di notificare"}

        # Modalità Power Guard
        for mode in ('auto', 'ask', 'warn_only'):
            if mode in t and any(k in t for k in ('power', 'guard', 'modalit')):
                labels = {'auto': 'automatico', 'ask': 'chiede conferma', 'warn_only': 'solo notifica'}
                return {"action": "power_guard_mode", "value": mode,
                        "preview": f"Power Guard modalità: <b>{labels[mode]}</b>"}

        # Orario spazzatura
        m = re.search(r'(?:spazzatura|trash|rifiuti).*?(\d{1,2})(?::00)?|'
                      r'(\d{1,2})(?::00)?.*(?:spazzatura|trash|rifiuti)', t)
        if m:
            hour = int(m.group(1) or m.group(2))
            if 0 <= hour <= 23:
                return {"action": "trash_hour", "value": hour,
                        "preview": f"Notifica spazzatura alle <b>{hour:02d}:00</b>"}

        # ── Do Not Disturb ───────────────────────────────────────────────────
        # Disattiva DND (controllo PRIMA per evitare che "disattiva" matchi "attiva")
        # NON matchare se c'è "attiva" prima → quello è enable
        _has_enable_verb = bool(re.search(
            r'\b(?:attiva|abilita|imposta|enable|turn.?on|set)\b', t))
        if not _has_enable_verb and re.search(
            r'(?:disattiva|disabilita|rimuovi|disable|turn.?off|togli).*(?:dnd|silenz|quiet)'
            r'|(?:dnd|silenz|quiet).*(?:off|\bno\b|disattiv)',
            t):
            return {"action": "dnd_disable",
                    "preview": "DND disabilitato — notifiche attive 24h"}

        # Attiva DND: tutte le varianti IT/EN
        # "attiva silenzio 23 7", "dnd start 23 end 7", "Do not disturb start 10 end 12"
        m = re.search(
            r'(?:attiva|abilita|imposta|set|enable|turn.?on).*(?:dnd|silenz|quiet|notturno|notte)'
            r'|(?:dnd|silenz|quiet|do.not.disturb).*(?:start|dalle|from)?\s*(\d{1,2}).*?(?:end|alle|to)\s*(\d{1,2})'
            r'|(?:dnd|silenz|quiet).*(\d{1,2}).*?(\d{1,2})'
            r'|(?:ore|fascia).*(?:silenziose|silenzio|notturne|notte).*(\d{1,2}).*?(\d{1,2})'
            r'|(?:silenzio|quiet).*(?:dalle|from)\s*(\d{1,2}).*?(?:alle|to)\s*(\d{1,2})',
            t)
        if m:
            nums = re.findall(r'\b(\d{1,2})\b', t)
            nums = [int(n) for n in nums if 0 <= int(n) <= 23]
            if len(nums) >= 2:
                start, end = nums[0], nums[1]
                return {"action": "dnd_enable", "start": start, "end": end,
                        "preview": f"DND attivo: <b>{start:02d}:00 → {end:02d}:00</b> (notifiche non critiche bloccate)"}
            else:
                return {"action": "dnd_enable", "start": 23, "end": 7,
                        "preview": "DND attivo: <b>23:00 → 07:00</b> (default notturno)"}

        # Lingua
        if re.search(r'\b(lingua|language)\b', t):
            if any(k in t for k in ('ingles', 'english', ' en')):
                return {"action": "language", "value": "en",
                        "preview": "Cambio lingua a <b>English</b>"}
            if any(k in t for k in ('italian', ' it', 'italiano')):
                return {"action": "language", "value": "it",
                        "preview": "Cambio lingua a <b>Italiano</b>"}

        # Soglia proximity
        m = re.search(r'(?:soglia|threshold|raggio).*?(\d+)\s*m\b|'
                      r'(\d+)\s*m\b.*(?:soglia|proximity|distanza)', t)
        if m and 'proximit' in t:
            meters = int(m.group(1) or m.group(2))
            if 10 <= meters <= 1000:
                mp = re.search(r'person\.\w+', t)
                person = mp.group(0) if mp else None
                return {"action": "proximity_threshold", "person": person, "value": meters,
                        "preview": f"Soglia proximity{' ' + person if person else ''} → <b>{meters}m</b>"}

        # Temperatura max clima
        m = re.search(r'(?:max|massima).*?(\d{1,2})\s*°?|(\d{1,2})\s*°?.*(?:max|massima)', t)
        if m and any(k in t for k in ('clima', 'termostato', 'temperatura', 'climate')):
            temp = int(m.group(1) or m.group(2))
            if 15 <= temp <= 35:
                return {"action": "climate_max_temp", "value": temp,
                        "preview": f"Temperatura massima clima → <b>{temp}°C</b>"}


        # Rimuovi proximity sensore
        m = re.search(r'(rimuovi|elimina|cancella|togli).*?proximit.*?(person\.\w+)|'
                      r'(person\.\w+).*?(rimuovi|elimina|cancella).*?proximit', t)
        if not m:
            m = re.search(r'(remove|delete|cancel).*?proximit.*?(person\.\w+)|'
                          r'(person\.\w+).*?(remove|delete).*?proximit', t)
        if m:
            eid = m.group(2) or m.group(3)
            if eid:
                return {"action": "proximity_remove", "person": eid,
                        "preview": f"Rimuovo proximity per <b>{eid}</b>"}

        # Rimuovi elettrodomestico da power_guard
        m = re.search(r'(rimuovi|elimina|cancella|togli)\s+(\w+).*?power.?guard|'
                      r'power.?guard.*?(rimuovi|elimina|cancella|togli)\s+(\w+)', t)
        if m:
            name = m.group(2) or m.group(4)
            if name and len(name) > 2 and name.lower() not in ("delay", "ritardo", "notif"):
                return {"action": "power_guard_appliance_remove", "name": name.capitalize(),
                        "preview": f"Rimuovo <b>{name.capitalize()}</b> da Power Guard"}

        # Rimuovi elettrodomestico monitorato
        m = re.search(r'(rimuovi|elimina|cancella|togli)\s+(?:elettrodomestico\s+)?(\w+)|'
                      r'(remove|delete)\s+(?:appliance\s+)?(\w+)', t)
        if m and any(k in t for k in ('elettrodomestico', 'appliance', 'monitora')):
            name = m.group(2) or m.group(4)
            if name and len(name) > 2:
                return {"action": "appliance_remove", "name": name,
                        "preview": f"Rimuovo <b>{name}</b> dagli elettrodomestici monitorati"}

        # Rimuovi delay power guard
        if re.search(r'(rimuovi|elimina|cancella|togli|remove).*?delay|delay.*?(rimuovi|elimina|remove)', t):
            if any(k in t for k in ('power', 'guard', 'delay', 'ritardo')):
                return {"action": "power_guard_delay", "value": 0,
                        "preview": "Power Guard: <b>nessun ritardo</b> (notifica immediata)"}



        # ── Briefing: elimina/svuota TUTTE le sezioni extra ───────────────
        _m_clear_extra = re.search(
            r'(?:elimina|svuota|cancella|pulisci|rimuovi|azzera|resetta)'
            r'\s+(?:tutt[ei]\s+)?(?:le\s+)?(?:sezioni?\s+)?extra(?:\s+briefing)?'
            r'|(?:elimina|svuota|cancella|pulisci|rimuovi|azzera)\s+(?:le\s+)?note\s+(?:extra\s+)?(?:del\s+)?briefing'
            r'|briefing\s+(?:elimina|svuota|cancella|pulisci|rimuovi)\s+(?:(?:le\s+)?(?:sezioni?\s+)?extra|note)'
            r'|(?:elimina|svuota|cancella|pulisci)\s+briefing\s+(?:nota|note|extra|sezioni?)', t)
        if _m_clear_extra:
            return {"action": "briefing_extra_remove", "text": "sezione extra",
                    "preview": "Rimuovo <b>tutte</b> le sezioni extra dal briefing"}

        # ── Briefing: aggiungi sezione extra ──────────────────────────────
        m = re.search(
            r'(?:aggiungi|add)\s+(?:al\s+)?briefing\s+(.+)'
            r'|(?:aggiungi|add)\s+(.+?)\s+al\s+briefing'
            r'|briefing.*?(?:aggiungi|add)\s+(.+)', t)
        if m:
            text_sec = (m.group(1) or m.group(2) or m.group(3) or "").strip()
            # Se contiene "saluto" → è un greeting, non una nota
            if text_sec.lower().startswith("saluto "):
                # Usa testo originale per preservare maiuscole nel saluto
                _orig_text = text.strip()
                _m_orig = re.search(
                    r"(?:aggiungi|add)\s+(?:al\s+)?briefing\s+saluto\s+(.+)"
                    r"|saluto\s+briefing\s+(.+)"
                    r"|briefing\s+saluto\s+(.+)", _orig_text, re.IGNORECASE)
                greeting_text = (_m_orig.group(1) or _m_orig.group(2) or _m_orig.group(3) or text_sec[7:]).strip() if _m_orig else text_sec[7:].strip()
                # Se è solo un nome, trasforma in saluto completo
                words = greeting_text.split()
                greeting_keywords = {"buongiorno","ciao","hello","good","salve","hey","benvenuto","morning"}
                if words and words[0].lower() not in greeting_keywords:
                    greeting_text = f"Buongiorno {greeting_text}! ☀️"
                return {"action": "briefing_greeting", "text": greeting_text,
                        "preview": f"Saluto briefing: <b>{greeting_text[:80]}</b>"}
            if len(text_sec) > 3:
                # Non aggiungere come extra se è una sezione standard
                # Se la frase contiene esplicitamente "mostra/ripristina" trattala come exclude_remove
                _is_restore = any(k in t for k in ("mostra", "ripristina", "show", "restore", "visualizza"))
                _std_sections = {"energia", "energy", "meteo", "weather", "spazzatura",
                                  "trash", "rifiuti", "stato", "casa", "riparazioni", "consiglio"}
                _words = set(text_sec.lower().split())
                if _is_restore and (_words & _std_sections):
                    _matched = (_words & _std_sections).pop()
                    return {"action": "briefing_exclude_remove", "section": _matched,
                            "preview": f"Ripristino la sezione <b>{_matched.capitalize()}</b> nel briefing"}
                return {"action": "briefing_extra_add", "text": text_sec, "raw": t,
                        "preview": f"Aggiungo al briefing: <b>{text_sec[:80]}</b>"}
        # ── Briefing: rimuovi/escludi — intelligente ──────────────────────
        # Intercetta: "rimuovi dal briefing X", "escludi X dal briefing"
        _std_sections = {
            "meteo": "meteo", "weather": "meteo",
            "energia": "energia", "energy": "energia",
            "fv": "energia", "solare": "energia", "fotovoltaico": "energia",
            "stato casa": "stato_casa", "casa": "stato_casa",
            "stato": "stato_casa", "allarme": "stato_casa",
            "riparazioni": "riparazioni", "problemi": "riparazioni",
            "spazzatura": "spazzatura", "trash": "spazzatura", "rifiuti": "spazzatura",
            "consiglio": "consiglio", "tip": "consiglio", "suggerimento": "consiglio",
            "routine": "routine",
        }
        _m_rm = re.search(
            r'(?:rimuovi|elimina|togli|remove|nascondi|hide|escludi|exclude)'
            r'\s+(?:dal\s+|da\s+|from\s+)?briefing\s+(.+)'
            r'|(?:rimuovi|elimina|togli|remove|nascondi|hide|escludi|exclude)'
            r'\s+(.+?)\s+(?:dal|da|from)?\s*briefing', t)
        if not _m_rm:
            _m_rm = re.search(
                r'briefing.*?(?:rimuovi|elimina|togli|remove|nascondi|hide|escludi|exclude)\s+(.+)', t)
        if _m_rm:
            _rm_text = (_m_rm.group(1) or _m_rm.group(2) or "").strip()
            if len(_rm_text) > 1:
                # Capisce se è sezione standard o extra personalizzata
                _rm_low = _rm_text.lower()
                _matched_std = None
                for kw, sec_id in _std_sections.items():
                    if kw in _rm_low:
                        _matched_std = sec_id
                        break
                if _matched_std:
                    return {"action": "briefing_exclude_add", "section": _matched_std,
                            "preview": f"Escludo dal briefing la sezione: <b>{_matched_std}</b>"}
                else:
                    return {"action": "briefing_extra_remove", "text": _rm_text,
                            "preview": f"Rimuovo dal briefing la nota: <b>{_rm_text[:80]}</b>"}

        # ── Briefing: escludi sezione standard ────────────────────────────
        m = re.search(
            r'(?:escludi|nascondi|hide|exclude)\s+(.+?)\s+(?:dal|da|from)?\s*briefing'
            r'|briefing.*?(?:escludi|nascondi|hide|exclude)\s+(.+)', t)
        if m:
            sec_name = (m.group(1) or m.group(2) or "").strip()
            if len(sec_name) > 2:
                return {"action": "briefing_exclude_add", "section": sec_name,
                        "preview": f"Escludo dal briefing la sezione: <b>{sec_name}</b>"}

        # ── Briefing: ripristina sezione esclusa ──────────────────────────
        m = re.search(
            r'(?:mostra|ripristina|show|restore)\s+(.+?)\s+(?:nel|nel\s+)?briefing'
            r'|briefing.*?(?:mostra|ripristina|show|restore)\s+(.+)', t)
        if m:
            sec_name = (m.group(1) or m.group(2) or "").strip()
            if len(sec_name) > 2:
                return {"action": "briefing_exclude_remove", "section": sec_name,
                        "preview": f"Ripristino nel briefing la sezione: <b>{sec_name}</b>"}

        # ── Briefing: saluto personalizzato ───────────────────────────────
        m = re.search(
            r'(?:saluto|greeting|intestazione)\s+briefing\s+(.+)'
            r'|briefing\s+(?:saluto|greeting)\s+(.+)', text.strip(), re.IGNORECASE)
        if m:
            greeting = (m.group(1) or m.group(2) or "").strip()
            if len(greeting) > 2:
                # Auto-completa se è solo un nome
                _gwords = greeting.split()
                _gkw = {"buongiorno","ciao","hello","good","salve","hey","benvenuto","morning"}
                if _gwords and _gwords[0].lower() not in _gkw:
                    greeting = f"Buongiorno {greeting}! ☀️"
                return {"action": "briefing_greeting", "text": greeting,
                        "preview": f"Saluto briefing: <b>{greeting[:80]}</b>"}
        m = re.search(r'briefing.*?(\d{1,2})(?::\d{2})?\s*(?:ora|h|ore)?'
                     r'|(\d{1,2})(?::\d{2})?\s*(?:ora|h|ore)?.*briefing', t)
        if m and any(k in t for k in ('briefing', 'mattino', 'morning')):
            hour = int(m.group(1) or m.group(2) or 7)
            if 0 <= hour <= 23:
                return {"action": "briefing_hour", "value": hour,
                        "preview": f"Briefing alle <b>{hour:02d}:00</b>"}


        # ── Briefing: meteo esterno città ──────────────────────────────────
        _wx_m = re.search(
            r'(?:imposta|setta?|set|usa|use|cambia|change)\s+(?:meteo|weather)\s+(?:briefing|del\s+briefing)\s*(?:a\s+|in\s+|per\s+|di\s+|for\s+|to\s+)?(\w[\w\s]*\w|\w)$'
            r'|(?:meteo|weather)\s+(?:briefing|del\s+briefing)\s*(?:a\s+|in\s+|per\s+|di\s+|for\s+|to\s+)?(\w[\w\s]*\w|\w)$'
            r'|(?:briefing|del\s+briefing)\s+(?:meteo|weather)\s+(\w[\w\s]*\w|\w)$',
            t)
        if _wx_m:
            city = (_wx_m.group(1) or _wx_m.group(2) or _wx_m.group(3) or "").strip().title()
            if city:
                return {"action": "briefing_weather_city", "city": city,
                        "preview": f"🌤️ Meteo briefing impostato su <b>{city}</b>"}

        # ── Briefing: tip_mode (consiglio / news / disabilita) ─────────────
        if re.search(r'disabilita.{0,15}consiglio|disabilita.{0,15}tip'
                     r'|rimuovi.{0,15}consiglio|senza.{0,15}consiglio'
                     r'|no.{0,10}consiglio|disable.{0,15}tip', t):
            return {"action": "briefing_tip_mode", "mode": "disabled",
                    "preview": "🔕 Consiglio del giorno <b>disabilitato</b>"}

        if re.search(r'abilita.{0,15}consiglio|attiva.{0,15}consiglio'
                     r'|enable.{0,15}tip|mostra.{0,15}consiglio', t):
            return {"action": "briefing_tip_mode", "mode": "tip",
                    "preview": "💡 Consiglio del giorno <b>abilitato</b>"}

        if re.search(r'news.{0,20}briefing|briefing.{0,20}news'
                     r'|notizie.{0,15}giorno|abilita.{0,10}news'
                     r'|al.posto.del.consiglio.{0,20}news', t):
            return {"action": "briefing_tip_mode", "mode": "news",
                    "preview": "📰 Consiglio del giorno sostituito con <b>News del giorno</b>"}

        if re.search(r'sport.{0,15}briefing|briefing.{0,15}sport'
                     r'|notizie.sport|risultati.sport|eventi.sport'
                     r'|abilita.{0,5}sport|calcio.briefing', t):
            return {"action": "briefing_tip_mode", "mode": "sports",
                    "preview": "⚽ Consiglio del giorno sostituito con <b>Notizie sportive</b>"}

        # ── Briefing: reset completo ──────────────────────────────────────
        if re.search(r'(?:ripristina|reset|azzera|cancella.tutto).*briefing'
                     r'|briefing.*(?:ripristina|reset|azzera|default)', t):
            return {"action": "briefing_reset",
                    "preview": "♻️ <b>Ripristino briefing</b> alle impostazioni predefinite\n"
                              "(saluto personalizzato, sezioni extra e esclusioni verranno rimossi)"}


        # ── Briefing: gestione sezione energia ──────────────────────────
        # "aggiungi energia al briefing", "mostra energia oggi", ecc.
        if re.search(r'(?:aggiungi|mostra|includi|ripristina|add|show).*(?:energia|energy|sensori.energia)'
                     r'|(?:energia|energy).*(?:briefing|aggiungi|mostra)', t):
            # Determina se vogliono oggi, ieri o entrambe
            if any(k in t for k in ("oggi", "today", "corrente", "current")):
                period = "oggi"
            elif any(k in t for k in ("ieri", "yesterday")):
                period = "ieri"
            else:
                period = "ieri"  # default
            # Rimuovi dalle esclusioni se era esclusa
            return {"action": "briefing_exclude_remove", "section": "energia",
                    "preview": f"Ripristino la sezione <b>Energia</b> nel briefing (periodo: {period})"}

        # ── Briefing: escludi/rimuovi sezione energia ─────────────────────
        if re.search(r'(?:rimuovi|escludi|nascondi|togli|remove|hide).*(?:energia|energy)'
                     r'|(?:energia|energy).*(?:rimuovi|escludi|nascondi|briefing)', t):
            return {"action": "briefing_exclude_add", "section": "energia",
                    "preview": "Escludo la sezione <b>Energia</b> dal briefing"}

        # ── Briefing: gestione sezione meteo ─────────────────────────────
        if re.search(r'(?:aggiungi|mostra|includi|ripristina).*(?:meteo|weather|tempo)'
                     r'|(?:meteo|weather).*(?:briefing|aggiungi|mostra)', t):
            return {"action": "briefing_exclude_remove", "section": "meteo",
                    "preview": "Ripristino la sezione <b>Meteo</b> nel briefing"}

        if re.search(r'(?:rimuovi|escludi|nascondi|togli).*(?:meteo|weather)'
                     r'|(?:meteo|weather).*(?:rimuovi|escludi|briefing)', t):
            return {"action": "briefing_exclude_add", "section": "meteo",
                    "preview": "Escludo la sezione <b>Meteo</b> dal briefing"}

        # ── Briefing: gestione sezione spazzatura ────────────────────────
        if re.search(r'(?:aggiungi|mostra|includi|ripristina).*(?:spazzatura|trash|rifiuti)'
                     r'|(?:spazzatura|trash).*(?:briefing|aggiungi|mostra)', t):
            return {"action": "briefing_exclude_remove", "section": "spazzatura",
                    "preview": "Ripristino la sezione <b>Spazzatura</b> nel briefing"}

        if re.search(r'(?:rimuovi|escludi|nascondi|togli).*(?:spazzatura|trash|rifiuti)'
                     r'|(?:spazzatura|trash).*(?:rimuovi|escludi|briefing)', t):
            return {"action": "briefing_exclude_add", "section": "spazzatura",
                    "preview": "Escludo la sezione <b>Spazzatura</b> dal briefing"}

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Rilevamento wizard (configurazioni interattive multi-step)

    def detect_wizard(self, text: str) -> Optional[dict]:
        """Rileva se il testo avvia un wizard interattivo."""
        t = text.lower().strip()

        # Wizard: aggiungi proximity
        if any(p in t for p in ('aggiungi proximity', 'aggiungi sensore proximity',
                                 'add proximity', 'nuova proximity',
                                 'configura proximity')):
            # Estrai persona se già menzionata
            mp = re.search(r'person\.\w+', t)
            person = mp.group(0) if mp else None
            return {
                "type": "proximity_add",
                "step": "person" if not person else "sensor",
                "data": {"person": person},
            }

        # Wizard: aggiungi appliance a power_guard
        if (re.search(r'aggiungi.{0,40}power.?guard', t) or
                re.search(r'add.{0,40}power.?guard', t) or
                re.search(r'aggiungi.{0,40}powerguard', t)):
            # Estrai nome se già nel testo (es: "aggiungi condizionatore a power guard")
            nm = re.search(r'aggiungi\s+(\w+)\s+(?:a\s+)?power', t)
            # Evita di estrarre parole generiche come articoli o "a"
            _skip = {'a', 'al', 'alla', 'il', 'lo', 'la', 'un', 'una', 'nuovo', 'nuova',
                     'elettrodomestico', 'appliance', 'dispositivo'}
            name = None
            if nm:
                candidate = nm.group(1).lower()
                if candidate not in _skip and len(candidate) > 1:
                    name = candidate.capitalize()
            return {
                "type": "power_guard_appliance_add",
                "step": "name" if not name else "switch",
                "data": {"name": name},
            }

        # Wizard: aggiungi elettrodomestico monitorato (appliances)
        if re.search(r'aggiungi\s+(?:elettrodomestico|appliance)|'
                     r'monitora\s+(?:nuovo|nuova)|add\s+appliance', t):
            nm = re.search(r'aggiungi\s+(\w+)\s*(?:agli|alla|al|a)?'
                           r'\s*(?:elettrodomestici|appliance)', t)
            name = nm.group(1).capitalize() if nm else None
            return {
                "type": "appliance_add",
                "step": "name" if not name else "mode",
                "data": {"name": name},
            }

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Applicazione modifiche semplici

    def _apply(self, intent: dict) -> tuple[bool, str]:
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

            elif action == "power_guard_delay":
                mins = intent["value"]
                if "power_guard" not in cfg:
                    cfg["power_guard"] = {}
                old = cfg["power_guard"].get("delay_minutes", 0)
                cfg["power_guard"]["delay_minutes"] = mins
                if mins == 0:
                    msg = f"✅ Power Guard: notifica immediata (nessun delay)"
                else:
                    msg = f"✅ Power Guard: attende <b>{mins} minuti</b> prima di notificare (era {old} min)"

            elif action == "power_guard_mode":
                mode = intent["value"]
                if "power_guard" not in cfg:
                    cfg["power_guard"] = {}
                old = cfg["power_guard"].get("mode", "?")
                cfg["power_guard"]["mode"] = mode
                labels = {'auto': 'Automatico', 'ask': 'Chiede conferma', 'warn_only': 'Solo notifica'}
                msg = f"✅ Power Guard: {old} → <b>{labels.get(mode, mode)}</b>"

            elif action == "trash_hour":
                h = intent["value"]
                old = cfg.get("spazzatura_notify_hour", "?")
                cfg["spazzatura_notify_hour"] = h
                msg = f"✅ Spazzatura: {old}:00 → <b>{h:02d}:00</b>"

            elif action == "dnd_enable":
                start = intent["start"]
                end   = intent["end"]
                if 0 <= start <= 23 and 0 <= end <= 23:
                    cfg["quiet_hours"] = {
                        "enabled": True,
                        "start":   start,
                        "end":     end,
                    }
                    msg = (f"✅ Do Not Disturb attivato\n"
                           f"🔕 Notifiche non critiche bloccate dalle <b>{start:02d}:00</b> alle <b>{end:02d}:00</b>\n"
                           f"<i>Allarmi e sicurezza passano sempre</i>\n\n"
                           f"⚠️ Riavvia l'addon per applicare il cambiamento.")
                else:
                    msg = "❌ Orari non validi (usa valori tra 0 e 23)"

            elif action == "dnd_disable":
                if "quiet_hours" in cfg:
                    cfg["quiet_hours"]["enabled"] = False
                msg = ("✅ Do Not Disturb disabilitato\n"
                       "🔔 Tutte le notifiche sono attive 24h\n\n"
                       "⚠️ Riavvia l'addon per applicare il cambiamento.")

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
                    msg = f"✅ Proximity {person}: {old}m → <b>{meters}m</b>"
                elif proxs:
                    first = list(proxs.keys())[0]
                    old = proxs[first].get("threshold_m", "?")
                    proxs[first]["threshold_m"] = meters
                    cfg["proximity_sensors"] = proxs
                    msg = f"✅ Proximity {first}: {old}m → <b>{meters}m</b>"
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
                msg = "✅ Temperatura massima clima:\n" + "\n".join(updated)


            elif action == "proximity_remove":
                person = intent["person"]
                proxs = cfg.get("proximity_sensors", {})
                if person not in proxs:
                    return False, f"⚠️ Nessuna proximity configurata per <b>{person}</b>"
                del proxs[person]
                cfg["proximity_sensors"] = proxs
                msg = f"✅ Proximity rimossa per <b>{person}</b>"

            elif action == "power_guard_appliance_remove":
                name = intent["name"]
                pg = cfg.get("power_guard", {})
                apps = pg.get("appliances_priority") or pg.get("appliances", [])
                before = len(apps)
                apps = [a for a in apps if a.get("name", "").lower() != name.lower()]
                if len(apps) == before:
                    return False, f"⚠️ <b>{name}</b> non trovato in Power Guard"
                pg["appliances_priority"] = apps
                if "appliances" in pg:
                    del pg["appliances"]
                cfg["power_guard"] = pg
                msg = f"✅ <b>{name}</b> rimosso da Power Guard"

            elif action == "appliance_remove":
                name = intent["name"].lower()
                apps = cfg.get("appliances", {})
                # Cerca per chiave o per campo name
                key_found = None
                for k, v in apps.items():
                    if k.lower() == name or v.get("name", "").lower() == name:
                        key_found = k
                        break
                if not key_found:
                    return False, f"⚠️ Elettrodomestico <b>{name}</b> non trovato"
                display_name = apps[key_found].get("name", key_found)
                del apps[key_found]
                cfg["appliances"] = apps
                msg = f"✅ <b>{display_name}</b> rimosso dagli elettrodomestici monitorati"


            elif action == "briefing_extra_add":
                text = intent["text"]
                # Auto-wrappa entity_id se presenti nel testo originale
                # o nel campo "raw_text" se salvato da detect_intent
                raw = intent.get("raw", text)
                import re as _re_b
                # Trova entity_id nel testo raw (es. "sensor.temp_xxx")
                found_eids = _re_b.findall(r'(?:sensor|binary_sensor|switch|input_number)\.\w+', raw)
                for eid in found_eids:
                    # Se l'entity_id non è già wrappato in {}, wrappalo
                    if "{" + eid + "}" not in text:
                        text = text + " {" + eid + "}"
                cb = cfg.setdefault("custom_briefing", {})
                extras = cb.get("extra_sections", [])
                if text not in extras:
                    extras.append(text)
                cb["extra_sections"] = extras
                cfg["custom_briefing"] = cb
                msg = f"✅ Aggiunto al briefing:\n<i>{text}</i>"

            elif action == "briefing_extra_remove":
                text_r = intent["text"].lower()
                cb = cfg.setdefault("custom_briefing", {})
                extras = cb.get("extra_sections", [])
                # Frase meta → svuota TUTTE le sezioni extra
                _META_CLEAR = ["sezione extra", "sezioni extra", "tutte le note",
                               "tutte le sezioni", "tutto", "extra", "note extra",
                               "le note", "le extra", "tutte"]
                if any(m == text_r.strip() or text_r.strip().startswith(m)
                       for m in _META_CLEAR):
                    cb["extra_sections"] = []
                    cfg["custom_briefing"] = cb
                    msg = "✅ Rimosse tutte le sezioni extra dal briefing"
                else:
                    # Prima prova a rimuovere una specifica extra_section
                    before = len(extras)
                    extras_new = [e for e in extras if text_r not in e.lower()]
                    if len(extras_new) < before:
                        cb["extra_sections"] = extras_new
                        cfg["custom_briefing"] = cb
                        msg = f"✅ Rimosso dalle note extra del briefing: <i>{intent['text']}</i>"
                    else:
                        # Non trovato nelle extra → prova a escludere sezione standard
                        SECTION_MAP = {
                            "energia": "energia", "energy": "energia",
                            "meteo": "meteo", "weather": "meteo",
                            "spazzatura": "spazzatura", "trash": "spazzatura",
                            "stato casa": "stato_casa", "casa": "stato_casa",
                            "riparazioni": "riparazioni", "repairs": "riparazioni",
                            "consiglio": "consiglio", "tip": "consiglio",
                            "routine": "routine",
                            "previsioni": "meteo", "forecast": "meteo",
                        }
                        sec_key = None
                        for kw, sec in SECTION_MAP.items():
                            if kw in text_r:
                                sec_key = sec
                                break
                        if sec_key:
                            excl = list(cb.get("exclude_sections", []))
                            if sec_key not in [e.lower() for e in excl]:
                                excl.append(sec_key)
                            cb["exclude_sections"] = excl
                            cfg["custom_briefing"] = cb
                            msg = (f"✅ Sezione <b>{sec_key}</b> nascosta dal briefing\n"
                                   f"<i>Usa 'Mostra {sec_key} nel briefing' per ripristinarla</i>")
                        else:
                            std = ["meteo", "energia", "stato casa", "riparazioni", "spazzatura", "consiglio", "routine"]
                            extra_list = extras if extras else ["(nessuna)"]
                            hint = ""
                            if extras:
                                hint = (f"\n💡 Per rimuovere tutte: <i>Rimuovi sezioni extra briefing</i>\n"
                                        f"   Per rimuovere una: <i>Rimuovi dal briefing {extras[0][:30]}</i>")
                            return False, (
                                f"⚠️ Non trovato: <b>{intent['text']}</b>\n\n"
                                f"<b>Sezioni standard nascondibili:</b>\n"
                                + "\n".join(f"  • {s}" for s in std) + "\n\n"
                                f"<b>Note extra salvate:</b>\n"
                                + "\n".join(f"  • {e[:50]}" for e in extra_list)
                                + hint
                            )
            elif action == "briefing_exclude_add":
                sec = intent["section"]
                # Mappa nomi utente → keyword sezione
                # ATTENZIONE: le chiavi devono corrispondere esattamente a _exclude_map in morning_briefing.py
                SECTION_MAP = {
                    "energia": "energia", "energy": "energia",
                    "fv": "energia", "solare": "energia",
                    "meteo": "meteo", "weather": "meteo",
                    "previsioni": "meteo", "forecast": "meteo",
                    "spazzatura": "spazzatura", "trash": "spazzatura", "rifiuti": "spazzatura",
                    "stato casa": "stato_casa", "stato_casa": "stato_casa",
                    "casa": "stato_casa", "stato": "stato_casa", "allarme": "stato_casa",
                    "riparazioni": "riparazioni", "repairs": "riparazioni", "problemi": "riparazioni",
                    "consiglio": "consiglio", "tip": "consiglio", "suggerimento": "consiglio",
                    "routine": "routine",
                }
                sec_key = sec.lower()
                for kw, mapped in SECTION_MAP.items():
                    if kw in sec_key:
                        sec_key = mapped
                        break
                cb = cfg.setdefault("custom_briefing", {})
                excl = list(cb.get("exclude_sections", []))  # copia esplicita
                logger.info("briefing_exclude_add: sec_key=%s | excl_prima=%s", sec_key, excl)
                if sec_key not in [e.lower() for e in excl]:
                    excl.append(sec_key)
                cb["exclude_sections"] = excl
                cfg["custom_briefing"] = cb
                logger.info("briefing_exclude_add: excl_dopo=%s", excl)
                msg = f"✅ Sezione <b>{sec_key}</b> nascosta dal briefing"

            elif action == "briefing_exclude_remove":
                sec_r = intent["section"].lower()
                cb = cfg.setdefault("custom_briefing", {})
                excl = cb.get("exclude_sections", [])
                before = len(excl)
                excl = [e for e in excl if sec_r not in e.lower()]
                if len(excl) == before:
                    return False, f"⚠️ Sezione non trovata nelle esclusioni"
                cb["exclude_sections"] = excl
                cfg["custom_briefing"] = cb
                msg = f"✅ Sezione <b>{intent['section']}</b> ripristinata nel briefing"

            elif action == "briefing_greeting":
                greeting = intent["text"]
                cb = cfg.setdefault("custom_briefing", {})
                cb["custom_greeting"] = greeting.strip().capitalize() if len(greeting.split()) == 1 else greeting.strip()
                cfg["custom_briefing"] = cb
                msg = f"✅ Saluto briefing: <b>{greeting}</b>"


            elif action == "briefing_weather_city":
                city = intent["city"]
                cb = cfg.setdefault("custom_briefing", {})
                old_city = cb.get("weather_city", "")
                cb["weather_city"] = city
                cfg["custom_briefing"] = cb
                if old_city:
                    msg = f"✅ Meteo briefing aggiornato: <b>{old_city}</b> → <b>{city}</b>"
                else:
                    msg = (f"✅ Meteo esterno abilitato nel briefing: <b>{city}</b>\n"
                           f"Da domani il briefing mostrerà le previsioni meteo per {city}.")

            elif action == "briefing_tip_mode":
                mode = intent["mode"]
                cb = cfg.setdefault("custom_briefing", {})
                cb["tip_mode"] = mode
                cfg["custom_briefing"] = cb
                mode_labels = {
                    "tip":      "💡 Consiglio del giorno (default)",
                    "disabled": "🔕 Disabilitato",
                    "news":     "📰 News del giorno",
                    "sports":   "⚽ Notizie sportive",
                }
                msg = f"✅ Consiglio/News briefing: {mode_labels.get(mode, mode)}"

            elif action == "briefing_reset":
                cfg.pop("custom_briefing", None)
                msg = "✅ Briefing ripristinato alle impostazioni predefinite\n(saluto, sezioni extra, esclusioni, meteo e consiglio rimossi)"

            elif action == "briefing_hour":
                hour = intent["value"]
                cb = cfg.setdefault("custom_briefing", {})
                old_h = cb.get("briefing_hour", 7)
                cb["briefing_hour"] = hour
                cfg["custom_briefing"] = cb
                msg = f"✅ Briefing: {old_h:02d}:00 → <b>{hour:02d}:00</b>\n⚠️ <i>Cambierà al prossimo riavvio</i>"

            elif action == "wizard_apply":
                # Risultato finale di un wizard — NON ritornare qui,
                # lascia che _save venga eseguito sotto
                ok, msg = self._apply_wizard_result(cfg, intent)
                if not ok:
                    return False, msg
                # msg è già impostato, cade nel _save() comune sotto

            else:
                return False, f"⚠️ Azione sconosciuta: {action}"

            if self._save(cfg):
                if self._home_reload_cb:
                    try:
                        self._home_reload_cb()
                    except Exception:
                        pass
                return True, msg
            return False, "❌ Errore salvataggio"

        except Exception as e:
            logger.error("ConfigEditor apply error: %s", e)
            return False, f"❌ Errore: {e}"

    def _apply_wizard_result(self, cfg: dict, intent: dict) -> tuple[bool, str]:
        """Applica il risultato finale di un wizard."""
        wtype = intent.get("wizard_type")
        data  = intent.get("data", {})

        if wtype == "proximity_add":
            person   = data["person"]
            sensor   = data["sensor"]
            threshold = int(data.get("threshold", 100))
            stale    = data.get("stale_check", False)
            proxs = cfg.setdefault("proximity_sensors", {})
            proxs[person] = {
                "sensor":       sensor,
                "threshold_m":  threshold,
                "stale_check":  stale,
                "stale_minutes": 10,
            }
            cfg["proximity_sensors"] = proxs
            return True, (f"✅ Proximity aggiunta per <b>{person}</b>\n"
                          f"   Sensore: {sensor}\n"
                          f"   Soglia: {threshold}m\n"
                          f"   Stale check: {'sì' if stale else 'no'}")

        elif wtype == "power_guard_appliance_add":
            name    = data["name"]
            switch  = data.get("switch", "")
            climate = data.get("climate", "")
            entity  = switch or climate
            pg = cfg.setdefault("power_guard", {})
            apps = pg.get("appliances_priority") or pg.get("appliances", [])
            # Evita duplicati
            if any(a.get("name", "").lower() == name.lower() for a in apps):
                return False, f"⚠️ <b>{name}</b> già presente in Power Guard"
            entry = {"name": name}
            if climate:
                entry["climate"] = climate
            else:
                entry["switch"] = switch
            apps.append(entry)
            pg["appliances_priority"] = apps
            if "appliances" in pg:
                del pg["appliances"]
            cfg["power_guard"] = pg
            entity_type = "Climate" if climate else "Switch"
            return True, (f"✅ <b>{name}</b> aggiunto a Power Guard\n"
                          f"   {entity_type}: {entity}\n"
                          f"   Priorità: {len(apps)} (ultimo)")

        elif wtype == "appliance_add":
            name   = data["name"]
            mode   = data.get("mode", "power")
            sensor = data.get("sensor", "")
            key    = name.lower().replace(" ", "_")
            apps = cfg.setdefault("appliances", {})
            if key in apps:
                return False, f"⚠️ <b>{name}</b> già presente negli elettrodomestici"
            if mode == "power":
                apps[key] = {
                    "enabled": True, "name": name, "icon": "⚡", "mode": "power",
                    "power_sensor": sensor,
                    "power_on_threshold": int(data.get("on_threshold", 50)),
                    "power_off_threshold": int(data.get("off_threshold", 10)),
                    "min_cycle_minutes": 20, "max_idle_minutes": 5,
                    "notify_on_start": False,
                }
            else:  # smart
                apps[key] = {
                    "enabled": True, "name": name, "icon": "🔌", "mode": "smart",
                    "state_sensor": sensor,
                    "running_states": ["Run"], "done_states": ["Finished", "Ready"],
                    "notify_on_start": False,
                }
            cfg["appliances"] = apps
            return True, (f"✅ <b>{name}</b> aggiunto agli elettrodomestici\n"
                          f"   Modalità: {mode}\n"
                          f"   Sensore: {sensor}")

        return False, "⚠️ Wizard non riconosciuto"

    # ─────────────────────────────────────────────────────────────────────────
    # Gestione wizard interattivo

    def start_wizard(self, wizard: dict):
        self._wizard    = wizard
        self._wizard_ts = time.time()

    def _wizard_expired(self) -> bool:
        return time.time() - self._wizard_ts > CONFIRM_TTL

    async def handle_wizard_step(self, text: str) -> bool:
        """Gestisce il passo corrente del wizard. Ritorna True se gestito."""
        if not self._wizard or self._wizard_expired():
            self._wizard = None
            return False

        t     = text.strip()
        wtype = self._wizard["type"]
        step  = self._wizard["step"]
        data  = self._wizard.setdefault("data", {})
        lang  = self._lang()

        # ── Annulla wizard
        # "no" NON annulla se siamo nello step stale (significa stale_check=False)
        _is_cancel = t.lower() in ("annulla", "cancel", "stop", "esci")
        _is_no_generic = t.lower() == "no" and step not in ("stale",)
        if _is_cancel or _is_no_generic:
            self._wizard = None
            msg = "👍 Configurazione annullata." if lang == "it" else "👍 Configuration cancelled."
            if self.notifier:
                await self.notifier.send_html(msg)
            return True

        # ── WIZARD: Proximity Add ─────────────────────────────────────────
        if wtype == "proximity_add":
            if step == "person":
                # Estrai person entity
                m = re.search(r'person\.\w+', t.lower())
                if not m:
                    await self.notifier.send_html(
                        "⚙️ Scrivi l'entity_id della persona\n"
                        "Esempio: <code>person.mario</code>"
                    )
                    return True
                data["person"] = m.group(0)
                self._wizard["step"] = "sensor"
                await self.notifier.send_html(
                    f"✅ Persona: <b>{data['person']}</b>\n\n"
                    f"⚙️ Ora scrivi il sensore di distanza:\n"
                    f"Esempio: <code>sensor.casa_mario_distance</code>"
                )
                return True

            elif step == "sensor":
                m = re.search(r'sensor\.\w+', t.lower())
                if not m:
                    await self.notifier.send_html(
                        "⚙️ Scrivi l'entity_id del sensore distanza\n"
                        "Esempio: <code>sensor.casa_mario_distance</code>"
                    )
                    return True
                data["sensor"] = m.group(0)
                self._wizard["step"] = "threshold"
                await self.notifier.send_html(
                    f"✅ Sensore: <b>{data['sensor']}</b>\n\n"
                    f"⚙️ Soglia distanza in metri? (default: 100)\n"
                    f"Scrivi un numero o <b>ok</b> per usare 100m"
                )
                return True

            elif step == "threshold":
                if t.lower() in ("ok", "si", "sì", "yes", "default"):
                    data["threshold"] = 100
                else:
                    m = re.search(r'\d+', t)
                    data["threshold"] = int(m.group(0)) if m else 100
                self._wizard["step"] = "stale"
                await self.notifier.send_html(
                    f"✅ Soglia: <b>{data['threshold']}m</b>\n\n"
                    f"⚙️ Abilitare stale check? (controlla se il sensore è aggiornato)\n"
                    f"Rispondi <b>sì</b> o <b>no</b> (consigliato: no)"
                )
                return True

            elif step == "stale":
                data["stale_check"] = t.lower() in ("sì", "si", "yes", "true")
                # Applica
                self._wizard = None
                intent = {"action": "wizard_apply", "wizard_type": "proximity_add", "data": data}
                ok, msg = self._apply(intent)
                if self.notifier:
                    await self.notifier.send_html(msg)
                return True

        # ── WIZARD: Power Guard Appliance Add ─────────────────────────────
        elif wtype == "power_guard_appliance_add":
            if step == "name":
                if len(t) < 2:
                    await self.notifier.send_html(
                        "⚙️ Come si chiama l'elettrodomestico?\n"
                        "Esempio: <b>Forno</b>, <b>Scaldabagno</b>"
                    )
                    return True
                # Se il testo contiene "power guard" è il comando originale ripetuto:
                # estrai solo il nome del dispositivo
                _skip_name = {'a', 'al', 'alla', 'il', 'lo', 'la', 'un', 'una',
                               'nuovo', 'nuova', 'elettrodomestico', 'appliance',
                               'dispositivo', 'aggiungi', 'add'}
                if re.search(r'power.?guard', t.lower()):
                    nm = re.search(r'aggiungi\s+(\w+)\s+(?:a\s+)?power', t.lower())
                    if nm and nm.group(1) not in _skip_name:
                        data["name"] = nm.group(1).capitalize()
                    else:
                        await self.notifier.send_html(
                            "⚙️ Come si chiama l'elettrodomestico?\n"
                            "Esempio: <b>Forno</b>, <b>Condizionatore</b>"
                        )
                        return True
                elif len(t.split()) == 1:
                    data["name"] = t.capitalize()
                else:
                    data["name"] = t.title()
                self._wizard["step"] = "switch"
                await self.notifier.send_html(
                    f"✅ Nome: <b>{data['name']}</b>\n\n"
                    f"⚙️ Entity_id dello switch o del climatizzatore da controllare:\n"
                    f"Switch: <code>switch.presa_forno</code>\n"
                    f"Clima:  <code>climate.condizionatore_sala</code>"
                )
                return True

            elif step == "switch":
                # Accetta switch.xxx oppure climate.xxx
                m_sw  = re.search(r'switch\.\w+', t.lower())
                m_cli = re.search(r'climate\.\w+', t.lower())
                if not m_sw and not m_cli:
                    await self.notifier.send_html(
                        "⚙️ Scrivi l'entity_id dello switch o del clima da controllare\n"
                        "Switch: <code>switch.presa_forno</code>\n"
                        "Clima:  <code>climate.condizionatore_sala</code>"
                    )
                    return True
                if m_sw:
                    data["switch"] = m_sw.group(0)
                else:
                    data["climate"] = m_cli.group(0)
                # Applica
                self._wizard = None
                intent = {"action": "wizard_apply", "wizard_type": "power_guard_appliance_add", "data": data}
                ok, msg = self._apply(intent)
                if self.notifier:
                    await self.notifier.send_html(msg)
                return True

        # ── WIZARD: Appliance Add ─────────────────────────────────────────
        elif wtype == "appliance_add":
            if step == "name":
                if len(t) < 2:
                    await self.notifier.send_html(
                        "⚙️ Come si chiama l'elettrodomestico?\n"
                        "Esempio: <b>Forno</b>, <b>Asciugatrice</b>"
                    )
                    return True
                data["name"] = t.capitalize()
                self._wizard["step"] = "mode"
                await self.notifier.send_html(
                    f"✅ Nome: <b>{data['name']}</b>\n\n"
                    f"⚙️ Modalità di rilevamento?\n"
                    f"  <b>power</b> — presa smart con sensore potenza\n"
                    f"  <b>smart</b> — elettrodomestico connesso (Bosch, Siemens...)"
                )
                return True

            elif step == "mode":
                mode = "smart" if "smart" in t.lower() else "power"
                data["mode"] = mode
                self._wizard["step"] = "sensor"
                if mode == "power":
                    await self.notifier.send_html(
                        f"✅ Modalità: <b>power</b>\n\n"
                        f"⚙️ Entity_id del sensore di potenza (Watt):\n"
                        f"Esempio: <code>sensor.presa_forno_power</code>"
                    )
                else:
                    await self.notifier.send_html(
                        f"✅ Modalità: <b>smart</b>\n\n"
                        f"⚙️ Entity_id del sensore di stato:\n"
                        f"Esempio: <code>sensor.forno_operation_state</code>"
                    )
                return True

            elif step == "sensor":
                m = re.search(r'sensor\.\w+', t.lower())
                if not m:
                    await self.notifier.send_html(
                        "⚙️ Scrivi l'entity_id del sensore\n"
                        "Esempio: <code>sensor.presa_forno_power</code>"
                    )
                    return True
                data["sensor"] = m.group(0)

                if data.get("mode") == "power":
                    self._wizard["step"] = "threshold"
                    await self.notifier.send_html(
                        f"✅ Sensore: <b>{data['sensor']}</b>\n\n"
                        f"⚙️ Soglia accensione in Watt? (default: 50)\n"
                        f"Scrivi il valore o <b>ok</b> per usare 50W"
                    )
                else:
                    # Smart mode: applica direttamente
                    self._wizard = None
                    intent = {"action": "wizard_apply", "wizard_type": "appliance_add", "data": data}
                    ok, msg = self._apply(intent)
                    if self.notifier:
                        await self.notifier.send_html(msg)
                return True

            elif step == "threshold":
                if t.lower() in ("ok", "si", "sì", "yes", "default"):
                    data["on_threshold"] = 50
                    data["off_threshold"] = 10
                else:
                    m = re.search(r'\d+', t)
                    data["on_threshold"] = int(m.group(0)) if m else 50
                    data["off_threshold"] = max(5, data["on_threshold"] // 5)
                # Applica
                self._wizard = None
                intent = {"action": "wizard_apply", "wizard_type": "appliance_add", "data": data}
                ok, msg = self._apply(intent)
                if self.notifier:
                    await self.notifier.send_html(msg)
                return True

        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Gestione conferme semplici

    def set_pending(self, intent: dict):
        self._pending    = intent
        self._pending_ts = time.time()

    async def handle_confirm(self, text: str) -> bool:
        """Intercetta sì/no per conferma modifica semplice."""
        if not self._pending:
            return False
        if time.time() - self._pending_ts > CONFIRM_TTL:
            self._pending = None
            return False

        t      = text.lower().strip()
        is_yes = t in ("sì", "si", "yes", "ok", "conferma", "applica", "vai")
        is_no  = t in ("no", "annulla", "cancel", "stop", "lascia perdere")
        if not (is_yes or is_no):
            return False

        intent = self._pending
        self._pending = None
        lang = self._lang()

        if is_no:
            msg = "👍 Modifica annullata." if lang == "it" else "👍 Change cancelled."
            if self.notifier:
                await self.notifier.send_html(msg)
            return True

        ok, result_msg = self._apply(intent)
        if self.notifier:
            await self.notifier.send_html(result_msg)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Display /config

    def get_config_display(self) -> str:
        cfg  = self._load()
        lang = self._lang()
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
        lines.append(f"\n🌍 <b>Lingua:</b> {cfg.get('language','it').upper()}")

        # Proximity
        proxs = cfg.get("proximity_sensors", {})
        if proxs:
            lines.append("\n📍 <b>Proximity:</b>")
            for person, ps in proxs.items():
                lines.append(f"  • {person}: {ps.get('threshold_m','?')}m — {ps.get('sensor','?')}")

        # Clima
        climate = cfg.get("climate", {})
        if climate:
            lines.append("\n🌡️ <b>Clima:</b>")
            for eid, clm in climate.items():
                sw = f" | switch: {clm['switch']}" if clm.get("switch") else ""
                ctype = f" | tipo: {clm['type']}" if clm.get("type") else ""
                lines.append(f"  • {clm.get('name',eid)}: {clm.get('min_temp','?')}°–{clm.get('max_temp','?')}°{sw}{ctype}")

        # Power Guard
        pg = cfg.get("power_guard", {})
        if pg and pg.get("enabled"):
            mode_l = {'auto': 'Automatico', 'ask': 'Chiede conferma', 'warn_only': 'Solo notifica'}
            delay  = pg.get("delay_minutes", 0)
            delay_str = f" | delay: {delay}min" if delay > 0 else ""
            lines.append(f"\n⚡ <b>Power Guard:</b> {pg.get('threshold_w','?')}W"
                         f" | {mode_l.get(pg.get('mode','ask'), '?')}{delay_str}")
            apps = pg.get("appliances_priority") or pg.get("appliances", [])
            for i, a in enumerate(apps, 1):
                lines.append(f"  {i}. {a.get('name','?')} → {a.get('switch','?')}")

        # Elettrodomestici
        appl = cfg.get("appliances", {})
        enabled_apps = {k: v for k, v in appl.items() if v.get("enabled")}
        if enabled_apps:
            lines.append("\n⚡ <b>Elettrodomestici monitorati:</b>")
            for k, v in enabled_apps.items():
                lines.append(f"  • {v.get('name',k)} ({v.get('mode','?')})")

        # Spazzatura
        if cfg.get("spazzatura_notify_enabled"):
            h = cfg.get("spazzatura_notify_hour", 20)
            lines.append(f"\n🗑️ <b>Spazzatura:</b> notifica alle {h:02d}:00")

        # Do Not Disturb
        qh = cfg.get("quiet_hours", {})
        if isinstance(qh, dict) and qh.get("enabled"):
            qs = qh.get("start", 23)
            qe = qh.get("end", 7)
            lines.append(f"\n🔕 <b>Do Not Disturb:</b> {qs:02d}:00 → {qe:02d}:00 (notifiche non critiche bloccate)")
        else:
            lines.append("\n🔔 <b>Do Not Disturb:</b> disabilitato (notifiche attive 24h)")

        # Briefing personalizzato
        cb = cfg.get("custom_briefing", {})
        extras   = cb.get("extra_sections", [])
        excl     = cb.get("exclude_sections", [])
        greeting = cb.get("custom_greeting", "")
        b_hour   = cb.get("briefing_hour", 7)
        b_wx_city = cb.get("weather_city", "")
        b_tip_mode = cb.get("tip_mode", "tip")
        lines.append(f"\n🎩 <b>Briefing mattutino:</b> alle {b_hour:02d}:00")
        if greeting:
            _gw = greeting.split()
            _gkw = {"buongiorno","ciao","hello","good","salve","hey","benvenuto","morning"}
            _display_greeting = greeting
            if _gw and _gw[0].lower().strip("☀️🌅 ") not in _gkw and len(_gw) <= 3:
                _display_greeting = f"Buongiorno {greeting.title()}! ☀️"
            lines.append(f"  💬 Saluto: <i>{_display_greeting}</i>")
        # Meteo esterno
        if b_wx_city:
            lines.append(f"  🌤️ Meteo: <b>{b_wx_city}</b> (esterno)")
        else:
            lines.append("  🌤️ Meteo: sensore HA interno")
        # Consiglio / News
        _tip_labels = {"tip": "💡 Consiglio del giorno", "disabled": "🔕 Disabilitato", "news": "📰 News del giorno", "sports": "⚽ Notizie sportive"}
        lines.append(f"  🎯 Fine briefing: {_tip_labels.get(b_tip_mode, b_tip_mode)}")
        if extras:
            lines.append("  ➕ Sezioni extra:")
            for e in extras:
                lines.append(f"    • {e[:60]}")
        if excl:
            lines.append("  ➖ Sezioni escluse: " + ", ".join(excl))
        std_visible = [s for s in ["meteo","energia","stato casa","riparazioni","spazzatura","consiglio","routine"]
                        if s not in [e.lower() for e in excl]]
        lines.append("  📋 Sezioni attive: " + ", ".join(std_visible))

        lines.append(
            "\n<i>💡 Esempi di modifica:\n"
            "  ➕ \"Aggiungi proximity per person.mario\"\n"
            "  ➕ \"Aggiungi forno a power guard\"\n"
            "  ➕ \"Aggiungi elettrodomestico asciugatrice\"\n"
            "  ✏️ \"Power Guard aspetta 5 minuti prima di notificare\"\n"
            "  ✏️ \"Cambia soglia Enel a 3500W\"\n"
            "  ➖ \"Rimuovi proximity per person.mario\"\n"
            "  ➖ \"Rimuovi lavatrice da power guard\"\n"
            "  ➖ \"Rimuovi delay power guard\"\n"
            "  ➖ \"Rimuovi elettrodomestico asciugatrice\"\n"
"\n"
"🎩 <b>Briefing:</b>\n"
"  ➕ \"Aggiungi al briefing temperatura esterna {sensor.temp_ext}\"\n"
"  ➕ \"Aggiungi al briefing Ricorda di annaffiare le piante\"\n"
"  ➖ \"Rimuovi dal briefing temperatura esterna\"\n"
"  🚫 \"Escludi spazzatura dal briefing\"\n"
"  ✅ \"Mostra energia nel briefing\"\n"
"  ⏰ \"Briefing alle 8 ore\"\n"
"  💬 \"Saluto briefing Buongiorno famiglia! ☀️\"\n"
"  🌤️ \"Imposta meteo briefing Roma\" — meteo esterno nel briefing\n"
"  🔕 \"Disabilita consiglio del giorno\"\n"
"  📰 \"Abilita news del giorno\" — notizie ANSA al posto del consiglio\n"
"  ⚽ \"Abilita sport briefing\" — notizie sportive al posto del consiglio\n"
"  💡 \"Abilita consiglio del giorno\" — torna al consiglio AI\n"
"  ♻️ \"Ripristina briefing\" — rimuove tutto e torna ai default</i>"
        )
        return "\n".join(lines)
