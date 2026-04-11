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


class LocalParser:
    """Parser comandi locali deterministici — funziona senza AI."""

    def __init__(self, home, rest_client, state_cache_cb):
        self.home        = home
        self.rest        = rest_client
        self._cache_cb   = state_cache_cb

    @property
    def _cache(self) -> dict:
        return self._cache_cb() if self._cache_cb else {}

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
        turn_on  = any(w in t for w in ("accendi", "accend", "turn on", "on "))
        turn_off = any(w in t for w in ("spegni", "spegn", "turn off", "off "))

        if not turn_on and not turn_off:
            # Cerca anche "luci" + stanza
            if "luc" not in t and "light" not in t:
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
            return (f"⚠️ Non ho trovato quale luce controllare.\n"
                    f"AI non disponibile — specifica il nome esatto del dispositivo.\n"
                    f"<i>Modalità offline</i>")
        return None

    def _find_light_entity(self, t: str) -> Optional[str]:
        """Cerca la luce più probabile in base alle parole chiave."""
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
        # Cerca per zona
        for kw, zone in ZONE_MAP.items():
            if kw in t:
                # Trova prima luce in quella zona
                for eid, v in self.home.lights.items():
                    fn = cache.get(eid, {}).get("attributes", {}).get("friendly_name", "").lower()
                    if zone in fn or kw in fn or kw in eid.lower():
                        return eid
        # Cerca per nome diretto
        for eid, v in self.home.lights.items():
            fn = cache.get(eid, {}).get("attributes", {}).get("friendly_name", "").lower()
            name_words = fn.split()
            for w in name_words:
                if len(w) > 3 and w in t:
                    return eid
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Tapparelle / Cover

    async def _handle_covers(self, t: str) -> Optional[str]:
        OPEN_KW  = ("apri", "alza", "su", "open", "raise", "su le", "tira su")
        CLOSE_KW = ("chiudi", "abbassa", "giu", "giù", "close", "lower", "abbassa")

        open_cmd  = any(k in t for k in OPEN_KW)
        close_cmd = any(k in t for k in CLOSE_KW)

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
        # Match diretto sul nome
        for eid in self.home.covers:
            fn = cache.get(eid, {}).get("attributes", {}).get("friendly_name", "").lower()
            for w in fn.split():
                if len(w) > 3 and w in t:
                    return eid
        return None

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
        for eid, v in self.home.switches.items():
            if any(ex in eid.lower() for ex in EXCLUDE):
                continue
            fn = cache.get(eid, {}).get("attributes", {}).get("friendly_name", "").lower()
            name_parts = fn.replace("_", " ").split()
            for w in name_parts:
                if len(w) > 3 and w in t:
                    return eid
        return None

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
