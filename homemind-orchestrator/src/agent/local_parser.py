"""
agent/local_parser.py — Parser comandi locale senza AI.

Usato come fallback quando TUTTI i provider AI sono non disponibili.
Riconosce i comandi più comuni e li esegue direttamente via HA REST API.

Comandi supportati:
  Luci:       accendi/spegni [stanza|entità|tutto]
  Tapparelle: apri/chiudi/alza/abbassa [stanza|tutto] [N%]
  Switch:     accendi/spegni [nome switch]
  Stato:      stato casa, chi c'è, luci accese, temperatura
  Allarme:    arma/disarma allarme
"""
import logging
import re
from typing import Optional

logger = logging.getLogger("homemind.local_parser")

# Parole che descrivono il TIPO di dispositivo e non quale: non bastano a riconoscerlo.
# (Prima "accendi luce bagno" accendeva la prima luce chiamata "Luce ...", qualunque fosse.)
_GENERIC_WORDS = {
    "luce", "luci", "light", "lights", "lampada", "lampade", "lamp", "lampadina", "led", "faro",
    "tapparella", "tapparelle", "tenda", "tende", "persiana", "persiane", "cover", "shutter",
    "switch", "presa", "prese", "interruttore", "relay", "relè", "plug",
}


def _word_in(text: str, word: str) -> bool:
    """True se `word` compare in `text` come parola intera (non dentro un'altra parola)."""
    return re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) is not None


class LocalParser:
    """Parser comandi locali deterministici — funziona senza AI."""

    def __init__(self, home, rest_client, state_cache_cb):
        self.home        = home
        self.rest        = rest_client
        self._cache_cb   = state_cache_cb

    @property
    def _cache(self) -> dict:
        return self._cache_cb() if self._cache_cb else {}

    def _distinct_words(self, friendly_name: str) -> list:
        """Parole del nome che identificano il dispositivo (esclude "luce", "tapparella"…)."""
        words = re.findall(r"[a-zàèéìòù0-9]+", (friendly_name or "").lower().replace("_", " "))
        return [w for w in words if len(w) > 3 and w not in _GENERIC_WORDS]

    def _best_name_match(self, t: str, entity_ids) -> Optional[str]:
        """Entità il cui nome contiene più parole DISTINTIVE presenti nel testo (None se nessuna)."""
        cache = self._cache
        best, best_key = None, (0, 0.0)
        for eid in entity_ids:
            fn = cache.get(eid, {}).get("attributes", {}).get("friendly_name", "")
            words = self._distinct_words(fn)
            if not words:
                continue
            hit = sum(1 for w in words if w in t)
            if hit == 0:
                continue
            key = (hit, hit / len(words))
            if key > best_key:
                best, best_key = eid, key
        return best

    # ─────────────────────────────────────────────────────────────────────────

    async def handle(self, text: str) -> Optional[str]:
        """
        Prova a gestire il comando localmente.
        Ritorna la risposta HTML se riesce, None se non riconosce il comando.
        """
        t = text.lower().strip()

        # Stato casa
        if self._is_status(t):
            return self._status_reply()

        # Luci
        light_result = await self._handle_lights(t)
        if light_result is not None:
            return light_result

        # Tapparelle / Cover
        cover_result = await self._handle_covers(t)
        if cover_result is not None:
            return cover_result

        # Switch
        switch_result = await self._handle_switch(t)
        if switch_result is not None:
            return switch_result

        # Allarme
        alarm_result = await self._handle_alarm(t)
        if alarm_result is not None:
            return alarm_result

        return None  # non riconosciuto

    # ─────────────────────────────────────────────────────────────────────────
    # Stato casa

    def _is_status(self, t: str) -> bool:
        STATUS_KW = (
            "stato casa", "stato della casa", "chi c'è", "chi è in casa",
            "chi c è", "chi e in casa", "siete in casa", "state in casa",
            "situazione casa", "house status", "who is home",
            "luci accese", "lights on",
        )
        return any(k in t for k in STATUS_KW)

    def _status_reply(self) -> str:
        s = self.home.summary()
        lines = ["🏠 <b>Stato casa</b> (modalità offline)\n"]

        if s["everyone_away"]:
            lines.append("👤 Casa vuota")
        else:
            who = ", ".join(s["who_is_home"]) or "nessuno"
            lines.append(f"👤 In casa: <b>{who}</b>")
            if s["who_is_away"]:
                lines.append(f"🚗 Fuori: {', '.join(s['who_is_away'])}")

        ae, ast_ = self.home.primary_alarm()
        alarm_icons = {
            "disarmed": "🔓", "armed_away": "🔒", "armed_home": "🔐",
            "triggered": "🚨", "arming": "⏳",
        }
        icon = alarm_icons.get(ast_, "❓")
        lines.append(f"\n{icon} Allarme: <b>{ast_}</b>")

        # Luci accese
        lights_on = s.get("lights_on", [])
        if lights_on:
            cache = self._cache
            names = []
            for eid in lights_on[:5]:
                n = cache.get(eid, {}).get("attributes", {}).get("friendly_name", eid)
                names.append(n)
            extra = f" +{len(lights_on)-5}" if len(lights_on) > 5 else ""
            lines.append(f"\n💡 Luci accese: {', '.join(names)}{extra}")
        else:
            lines.append("\n💡 Tutte le luci spente")

        lines.append("\n⚠️ <i>Modalità offline — AI non disponibile</i>")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Luci

    async def _handle_lights(self, t: str) -> Optional[str]:
        # Riconosce: "accendi luci cucina", "spegni tutto", "dimmer 50%", ecc.
        # "on"/"off" solo come parole intere (prima "con la cucina" contava come "accendi")
        turn_on  = any(w in t for w in ("accendi", "accend", "turn on")) or _word_in(t, "on")
        turn_off = any(w in t for w in ("spegni", "spegn", "turn off")) or _word_in(t, "off")

        if not turn_on and not turn_off:
            # Cerca anche "luci" + stanza
            if "luc" not in t and "light" not in t:
                return None
            # Una DOMANDA ("com'è la luce del salotto?") non è un comando: non accendere nulla
            if "?" in t or re.match(r"\s*(com'è|come|qual|quanto|quant|che\b|chi\b|dov|perch|è\b|e'\s|sono\b|c'è|ci sono)", t):
                return None

        # Tutti/tutto
        if any(w in t for w in ("tutto", "tutte", "all", "ogni")):
            service = "light.turn_on" if turn_on else "light.turn_off"
            try:
                if turn_on:
                    await self.rest.call_service("light", "turn_on", {}, target={"entity_id": "all"})
                else:
                    await self.rest.call_service("light", "turn_off", {}, target={"entity_id": "all"})
                icon = "💡" if turn_on else "🌑"
                return f"{icon} <b>Tutte le luci</b> {'accese' if turn_on else 'spente'}\n⚠️ <i>Modalità offline</i>"
            except Exception as e:
                return f"❌ Errore: {e}"

        # Cerca stanza/entità nel testo
        entity = self._find_light_entity(t)
        if entity:
            name = self._cache.get(entity, {}).get("attributes", {}).get("friendly_name", entity)
            # Cerca eventuale percentuale
            pct_m = re.search(r'(\d{1,3})\s*%', t)
            try:
                if turn_on or (not turn_off):
                    params = {}
                    if pct_m:
                        bri = int(int(pct_m.group(1)) * 255 / 100)
                        params["brightness"] = bri
                    await self.rest.call_service("light", "turn_on", params,
                                                  target={"entity_id": entity})
                    pct_str = f" ({pct_m.group(1)}%)" if pct_m else ""
                    return f"💡 <b>{name}</b> accesa{pct_str}\n⚠️ <i>Modalità offline</i>"
                else:
                    await self.rest.call_service("light", "turn_off", {},
                                                  target={"entity_id": entity})
                    return f"🌑 <b>{name}</b> spenta\n⚠️ <i>Modalità offline</i>"
            except Exception as e:
                return f"❌ Errore controllo {name}: {e}"

        if turn_on or turn_off:
            # Molte luci (es. del bagno) sono "switch": prima di arrendersi prova quelli
            sw = await self._handle_switch(t)
            if sw is not None:
                return sw
            return (f"⚠️ Non ho trovato quale luce controllare.\n"
                    f"AI non disponibile — specifica il nome esatto del dispositivo.\n"
                    f"<i>Modalità offline</i>")
        return None

    def _find_light_entity(self, t: str) -> Optional[str]:
        """Cerca la luce giusta. NON indovina: se nomini una stanza che non trova, ritorna None."""
        cache = self._cache
        ZONE_MAP = {
            "cucina": "cucina", "kitchen": "cucina",
            "salotto": "salotto", "salone": "salotto", "living": "salotto",
            "camera": "camera_da_letto", "letto": "camera_da_letto", "bedroom": "camera_da_letto",
            "bagno": "bagno", "bathroom": "bagno",
            "ingresso": "ingresso", "entrata": "ingresso",
            "corridoio": "corridoio",
            "garage": "garage", "esterno": "esterno", "giardino": "esterno",
        }
        zone_mentioned = False
        # Cerca per zona
        for kw, zone in ZONE_MAP.items():
            if kw in t:
                zone_mentioned = True
                # Trova prima luce in quella zona
                for eid, v in self.home.lights.items():
                    fn = cache.get(eid, {}).get("attributes", {}).get("friendly_name", "").lower()
                    if zone in fn or kw in fn or kw in eid.lower():
                        return eid
        # Cerca per nome: solo parole che identificano la luce (non "luce"/"luci"…)
        best = self._best_name_match(t, self.home.lights.keys())
        if best:
            return best
        # Nessuna stanza nominata e una sola luce in casa: è quella
        if not zone_mentioned and len(self.home.lights) == 1:
            return next(iter(self.home.lights))
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Tapparelle / Cover

    async def _handle_covers(self, t: str) -> Optional[str]:
        OPEN_KW  = ("apri", "alza", "open", "raise")
        CLOSE_KW = ("chiudi", "abbassa", "close", "lower")

        # "su"/"giù" solo come parole intere (prima "consuma" o "questo" contavano come "su")
        open_cmd  = any(k in t for k in OPEN_KW) or _word_in(t, "su")
        close_cmd = any(k in t for k in CLOSE_KW) or _word_in(t, "giu") or _word_in(t, "giù")

        if not open_cmd and not close_cmd:
            if not any(k in t for k in ("tappar", "tenda", "cover", "shutter", "finestra")):
                return None

        # Cerca percentuale
        pct_m = re.search(r'(\d{1,3})\s*%', t)
        position = int(pct_m.group(1)) if pct_m else (100 if open_cmd else 0)

        # Tutti/tutto
        if any(w in t for w in ("tutto", "tutte", "all", "ogni")):
            try:
                await self.rest.call_service(
                    "cover", "set_cover_position", {"position": position},
                    target={"entity_id": "all"}
                )
                icon = "🔓" if position > 50 else "🔒"
                action = f"aperte al {position}%" if position > 0 else "chiuse"
                return f"{icon} <b>Tutte le tapparelle</b> {action}\n⚠️ <i>Modalità offline</i>"
            except Exception as e:
                return f"❌ Errore: {e}"

        # Cerca entità specifica
        entity = self._find_cover_entity(t)
        if entity:
            name = self._cache.get(entity, {}).get("attributes", {}).get("friendly_name", entity)
            try:
                await self.rest.call_service(
                    "cover", "set_cover_position", {"position": position},
                    target={"entity_id": entity}
                )
                icon = "🔓" if position > 50 else "🔒"
                action = f"aperta al {position}%" if position > 0 else "chiusa"
                return f"{icon} <b>{name}</b> {action}\n⚠️ <i>Modalità offline</i>"
            except Exception as e:
                return f"❌ Errore controllo {name}: {e}"

        # Nessuna entità trovata ma era un comando cover
        if open_cmd or close_cmd:
            action = "aprire" if open_cmd else "chiudere"
            return (f"⚠️ Non so quale tapparella {action}.\n"
                    f"AI non disponibile — specifica la stanza o il nome.\n"
                    f"<i>Modalità offline</i>")
        return None

    def _find_cover_entity(self, t: str) -> Optional[str]:
        cache = self._cache
        ZONE_KW = {
            "cucina": "cucina", "salotto": "salotto", "salone": "salotto",
            "camera": "camera", "letto": "letto", "bedroom": "camera",
            "bagno": "bagno", "ingresso": "ingresso",
        }
        for kw, zone in ZONE_KW.items():
            if kw in t:
                for eid in self.home.covers:
                    fn = cache.get(eid, {}).get("attributes", {}).get("friendly_name", "").lower()
                    if zone in fn or kw in fn or kw in eid.lower():
                        return eid
        # Match diretto sul nome: solo parole distintive (non "tapparella"/"tenda"…)
        return self._best_name_match(t, self.home.covers)

    # ─────────────────────────────────────────────────────────────────────────
    # Switch

    async def _handle_switch(self, t: str) -> Optional[str]:
        turn_on  = any(w in t for w in ("accendi", "turn on", "attiva", "abilita"))
        turn_off = any(w in t for w in ("spegni", "turn off", "disattiva", "disabilita"))

        if not turn_on and not turn_off:
            return None

        entity = self._find_switch_entity(t)
        if not entity:
            return None

        name = self._cache.get(entity, {}).get("attributes", {}).get("friendly_name", entity)
        try:
            svc = "turn_on" if turn_on else "turn_off"
            await self.rest.call_service("switch", svc, {}, target={"entity_id": entity})
            icon = "✅" if turn_on else "⭕"
            return f"{icon} <b>{name}</b> {'acceso' if turn_on else 'spento'}\n⚠️ <i>Modalità offline</i>"
        except Exception as e:
            return f"❌ Errore controllo {name}: {e}"

    def _find_switch_entity(self, t: str) -> Optional[str]:
        cache = self._cache
        # Esclude switch di servizio
        EXCLUDE = ("non_disturb", "shuffle", "repeat", "autofocus", "lampada_ir",
                   "tergicristallo", "bypassato", "permit_join")
        best, best_score = None, (0, 0.0)
        for eid, v in self.home.switches.items():
            if any(ex in eid.lower() for ex in EXCLUDE):
                continue
            fn = cache.get(eid, {}).get("attributes", {}).get("friendly_name", "")
            words = self._distinct_words(fn)               # solo parole distintive (non "luce"/"presa"…)
            if words and sum(1 for w in words if w in t) >= 1:
                score = (sum(1 for w in words if w in t), sum(1 for w in words if w in t) / len(words))
                if score > best_score:
                    best, best_score = eid, score
        return best

    # ─────────────────────────────────────────────────────────────────────────
    # Allarme

    async def _handle_alarm(self, t: str) -> Optional[str]:
        ARM_KW   = ("arma", "attiva allarme", "arm alarm", "arm away", "arm home")
        DISARM_KW = ("disarma", "disattiva allarme", "disarm", "disinserisci")

        arm   = any(k in t for k in ARM_KW)
        disarm = any(k in t for k in DISARM_KW)

        if not arm and not disarm:
            return None

        ae, ast_ = self.home.primary_alarm()
        if not ae:
            return "⚠️ Nessun pannello allarme configurato"

        try:
            if disarm:
                await self.rest.call_service("alarm_control_panel", "alarm_disarm",
                                              {}, target={"entity_id": ae})
                return f"🔓 <b>Allarme disarmato</b>\n⚠️ <i>Modalità offline</i>"
            else:
                await self.rest.call_service("alarm_control_panel", "alarm_arm_away",
                                              {}, target={"entity_id": ae})
                return f"🔒 <b>Allarme armato</b>\n⚠️ <i>Modalità offline</i>"
        except Exception as e:
            return f"❌ Errore allarme: {e}"
