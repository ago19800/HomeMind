"""
ha_tools.py — Strumenti informativi che l'AI usa per rispondere.
Genera contesto ricco: energia, luci, sensori, card Lovelace, suggerimenti.
"""
import logging, json
from datetime import datetime
from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.tools")


class HATools:
    def __init__(self, cache: dict, home, rest_client, person_cfg: dict = None):
        self.cache      = cache
        self.home       = home
        self.rest       = rest_client
        self._pcfg      = person_cfg or {}   # person_config.json per energy_sensors

    # ── Contesto principale per il prompt AI ──────────────────────────────────

    def full_context(self) -> str:
        s   = self.home.summary()
        ae, ast_ = self.home.primary_alarm()
        now = now_local()
        parts = [
            "=== STATO CASA " + now.strftime("%d/%m/%Y %H:%M") + " ===",
        ]

        # Presenza
        if not s["has_persons"]:
            parts += [
                "⚠️  PROBLEMA CRITICO: Nessuna entita person.* trovata in HA!",
                "   L antifurto NON funziona. Soluzione:",
                "   1. HA → Impostazioni → Persone → Aggiungi persona",
                "   2. Installa companion app sul telefono e collegala alla persona",
            ]
        else:
            parts += [
                "Presenza: " + ("TUTTI FUORI" if s["everyone_away"] else "OCCUPATA"),
                "In casa: " + (", ".join(s["who_is_home"]) or "nessuno"),
                "Fuori:   " + (", ".join(s["who_is_away"]) or "nessuno"),
            ]
            # Posizione dettagliata per ogni persona
            person_details = self._persons_location_block()
            if person_details:
                parts += ["", person_details]

        parts += [
            "Allarme: " + (ae or "NON CONFIGURATO") + " → " + ast_,
            "",
        ]

        # Energia
        energy = self._energy_block()
        if energy:
            parts += ["--- ENERGIA ---", energy, ""]

        # Temperature
        temps = self._temperatures()
        if temps:
            parts += ["--- TEMPERATURE ---", temps, ""]

        # Luci
        parts += ["--- LUCI ---", self._lights_block(), ""]

        # Sensori movimento
        if self.home.motion_sensors:
            parts += ["--- SENSORI MOVIMENTO (solo fisici) ---",
                      self._motion_block(), ""]

        # Clima
        if self.home.climate:
            parts += ["--- CLIMA ---", self._climate_block(), ""]

        # Sezione entity_id interrogabili con GET_HISTORY
        parts += ["--- ENTITY_ID PER GET_HISTORY ---",
                  self._queryable_entities_block(), ""]

        return "\n".join(parts)

    # ── Blocchi informativi ───────────────────────────────────────────────────

    def _persons_location_block(self) -> str:
        """
        Per ogni persona tracciata costruisce una riga con:
        - stato (home / not_home / zona)
        - indirizzo/via se disponibile da device_tracker companion
        - coordinate GPS se disponibili
        - ultimo aggiornamento
        """
        lines = []
        for person_eid, person_data in self.home.persons.items():
            name  = person_data.get("name", person_eid)
            state = self.cache.get(person_eid, {}).get("state", "unknown")
            attrs = self.cache.get(person_eid, {}).get("attributes", {})

            # Zona leggibile
            if state == "home":
                location_str = "🏠 in casa"
            elif state == "not_home":
                location_str = "🚗 fuori casa"
            else:
                location_str = f"📍 zona: {state}"

            # Cerca device_tracker collegato alla persona
            # HA collega person.X → device_tracker.X_* o device_tracker.nome_*
            person_slug = person_eid.replace("person.", "").lower()
            tracker_eid = None
            tracker_attrs = {}

            for eid, s in self.cache.items():
                if not eid.startswith("device_tracker."):
                    continue
                slug = eid.replace("device_tracker.", "").lower()
                # Match per nome o per entity_id correlato
                if person_slug in slug or slug in person_slug:
                    tracker_eid = eid
                    tracker_attrs = s.get("attributes", {})
                    break

            # Se non trovato con nome, cerca tramite source del person
            if not tracker_eid:
                src = attrs.get("source", "")  # es: "device_tracker.agostino_sm"
                if src and src in self.cache:
                    tracker_eid = src
                    tracker_attrs = self.cache[src].get("attributes", {})

            # Estrai dati dal device_tracker
            lat  = tracker_attrs.get("latitude")
            lon  = tracker_attrs.get("longitude")
            addr = (tracker_attrs.get("friendly_name_address")
                    or tracker_attrs.get("last_known_address")
                    or tracker_attrs.get("address")
                    or tracker_attrs.get("location_name")
                    or attrs.get("friendly_name_address")
                    or attrs.get("last_known_address")
                    or attrs.get("address"))
            gps_acc = tracker_attrs.get("gps_accuracy") or attrs.get("gps_accuracy")
            last_upd = (tracker_attrs.get("last_updated")
                        or tracker_attrs.get("last_seen")
                        or attrs.get("last_updated"))

            # Cerca sensor.*_geocoded_location (HA Companion App)
            # Esempio: sensor.agostino_geocoded_location, sensor.sm_s931b_geocoded_location
            if not addr:
                for eid, s in self.cache.items():
                    if not eid.startswith("sensor."):
                        continue
                    if "geocoded" not in eid.lower() and "address" not in eid.lower():
                        continue
                    # Collega al person se il suo nome/slug è nell'entity_id
                    if person_slug not in eid.lower():
                        # Prova anche col tracker slug
                        if tracker_eid:
                            tr_slug = tracker_eid.replace("device_tracker.", "").lower()
                            if tr_slug not in eid.lower():
                                continue
                        else:
                            continue
                    geo_state = s.get("state", "")
                    if geo_state and geo_state not in ("unknown", "unavailable", ""):
                        addr = geo_state
                        break
                    # Prova anche negli attributi
                    for ak in ("address", "Formatted Address", "formatted_address"):
                        v = s.get("attributes", {}).get(ak, "")
                        if v and v not in ("unknown", "unavailable", ""):
                            addr = v
                            break
                    if addr:
                        break

            # Se ancora nessun indirizzo, cerca sensor.*_geocoded* senza filtro persona
            # (utile se la naming convention è diversa, es. sensor.geocoded_agostino)
            if not addr and lat and lon:
                for eid, s in self.cache.items():
                    if "geocoded" in eid.lower() or "address" in eid.lower():
                        geo_state = s.get("state", "")
                        if geo_state and geo_state not in ("unknown", "unavailable", ""):
                            addr = f"{geo_state} (via {eid})"
                            break

            row = f"👤 {name}: {location_str}"
            if addr:
                row += f" | 📍 {addr}"
            if lat and lon:
                row += f" | GPS: {lat:.5f},{lon:.5f}"
                if gps_acc:
                    row += f" (±{gps_acc}m)"
            if tracker_eid:
                row += f" | tracker: {tracker_eid}"

            lines.append(row)

        if not lines:
            return ""
        return "[ POSIZIONE PERSONE ]\n" + "\n".join(lines)

    def _energy_block(self) -> str:
        """
        Legge sensori energia: prima quelli configurati in person_config.json,
        poi fallback su tutti i sensori energia/potenza presenti in HA.
        """
        power_w   = []
        energy_kwh= []
        battery   = []

        # Se l'utente ha configurato energy_sensors, usali come priorità
        configured = self._pcfg.get("energy_sensors", {})
        configured_eids = set(v for v in configured.values() if isinstance(v, str))

        for eid, s in self.cache.items():
            v = s.get("state","")
            if v in ("", "unavailable", "unknown"):
                continue
            attrs = s.get("attributes", {})
            dc    = attrs.get("device_class","")
            unit  = attrs.get("unit_of_measurement","")
            name  = attrs.get("friendly_name", eid)

            # Sensori energia (kWh) — produzione totale giornaliera ecc.
            if dc == "energy" or (unit and "kwh" in unit.lower()):
                # Escludi sensori chiaramente non energetici
                if any(x in eid.lower() for x in ("battery_voltage","voltage","current")):
                    continue
                energy_kwh.append(name + ": " + v + " " + unit)

            # Sensori potenza (W) — produzione/consumo istantaneo
            elif dc == "power" or (unit in ("W","kW") and dc != "battery"):
                power_w.append(name + ": " + v + " " + unit)

            # Batteria %
            elif dc == "battery" and "%" in unit:
                battery.append(name + ": " + v + unit)

        lines = []
        if energy_kwh:
            lines.append("[ Energia totale (kWh) ]")
            lines += sorted(energy_kwh)
        if power_w:
            lines.append("[ Potenza istantanea (W) ]")
            lines += sorted(power_w)
        if battery:
            lines.append("[ Batteria ]")
            lines += battery

        return "\n".join(lines) if lines else "(nessun sensore energia trovato)"

    def _temperatures(self) -> str:
        lines = []
        for eid, s in self.cache.items():
            if s.get("attributes",{}).get("device_class","") != "temperature":
                continue
            v = s.get("state","")
            if v in ("unavailable","unknown",""):
                continue
            name = s.get("attributes",{}).get("friendly_name", eid)
            u    = s.get("attributes",{}).get("unit_of_measurement","°C")
            lines.append(name + ": " + v + " " + u)
        return "\n".join(lines)

    def _lights_block(self) -> str:
        lines = []
        for eid, v in self.home.lights.items():
            s    = self.cache.get(eid, {})
            name = s.get("attributes",{}).get("friendly_name", v["name"])
            bri  = s.get("attributes",{}).get("brightness")
            bpct = " " + str(round(bri/255*100)) + "%" if bri else ""
            icon = "ON " if v["state"] == "on" else "off"
            lines.append(icon + " " + name + bpct + "  [" + eid + "]")
        return "\n".join(lines) if lines else "(nessuna luce)"

    def _motion_block(self) -> str:
        lines = []
        for eid, v in self.home.motion_sensors.items():
            icon = "ATTIVO" if v["state"] == "on" else "off   "
            lines.append(icon + " " + v["name"] + " (zona=" + v["zone"] + ")  [" + eid + "]")
        return "\n".join(lines)

    def _climate_block(self) -> str:
        lines = []
        for eid, v in self.home.climate.items():
            s     = self.cache.get(eid, {})
            attrs = s.get("attributes", {})
            cur   = attrs.get("current_temperature","?")
            tgt   = attrs.get("temperature","?")
            lines.append(v["name"] + ": " + v["state"] +
                         " | corrente=" + str(cur) + "°  target=" + str(tgt) + "°")
        return "\n".join(lines)

    def _queryable_entities_block(self) -> str:
        """
        Lista entity_id che l'AI può usare con [GET_HISTORY:eid:ore].
        Mostra entità rilevanti: allarme, sensori movimento, persone, temperature, luci.
        """
        ae, _ = self.home.primary_alarm()
        lines = ["Usa questi entity_id esatti nel tag [GET_HISTORY:entity_id:ore]:"]

        if ae:
            lines.append(f"  Allarme: {ae}")

        for eid in self.home.persons:
            name = self.cache.get(eid, {}).get("attributes", {}).get("friendly_name", eid)
            lines.append(f"  Persona '{name}': {eid}")

        for eid, v in self.home.motion_sensors.items():
            lines.append(f"  Movimento '{v['name']}': {eid}")

        for eid, v in self.home.contact_sensors.items():
            lines.append(f"  Contatto '{v['name']}': {eid}")

        for eid, s in self.cache.items():
            attrs = s.get("attributes", {})
            dc = attrs.get("device_class", "")
            if dc == "temperature":
                v = s.get("state", "")
                if v not in ("unavailable", "unknown", ""):
                    name = attrs.get("friendly_name", eid)
                    lines.append(f"  Temperatura '{name}': {eid}")

        for eid, v in list(self.home.lights.items())[:10]:
            lines.append(f"  Luce '{v['name']}': {eid}")

        return "\n".join(lines)

    # ── Ricerca entità libera ─────────────────────────────────────────────────

    def search(self, q: str) -> str:
        q = q.lower()
        found = []
        for eid, s in self.cache.items():
            name = s.get("attributes",{}).get("friendly_name","").lower()
            v    = s.get("state","")
            if v in ("unavailable","unknown"):
                continue
            if q in eid.lower() or q in name:
                u = s.get("attributes",{}).get("unit_of_measurement","")
                fn = s.get("attributes",{}).get("friendly_name","")
                found.append(eid + ": " + v + (" " + u if u else "") +
                             (" (" + fn + ")" if fn else ""))
                if len(found) >= 20:
                    break
        return "\n".join(found) if found else "Nessuna entita trovata per: " + q

    # ── Generazione card Lovelace ─────────────────────────────────────────────

    def make_entities_card(self, entity_ids: list, title: str = "") -> str:
        rows = "\n".join("      - entity: " + e for e in entity_ids)
        t    = ("title: " + title + "\n  ") if title else ""
        return "```yaml\ntype: entities\n  " + t + "entities:\n" + rows + "\n```"

    def make_energy_dashboard_yaml(self) -> str:
        """Card YAML per il pannello energia."""
        yaml = (
            "# Card energia — incolla in Lovelace (modalita YAML)\n"
            "type: vertical-stack\n"
            "cards:\n"
            "  - type: entities\n"
            "    title: \"Fotovoltaico\"\n"
            "    entities:\n"
            "      - entity: sensor.fotovoltaica_totale\n"
            "        name: \"FV Totale\"\n"
            "      - entity: sensor.inverter_pipsolar_pv1_charging_power\n"
            "        name: \"Stringa 1\"\n"
            "      - entity: sensor.inverter_pipsolar_pv2_charging_power\n"
            "        name: \"Stringa 2\"\n"
            "\n"
            "  - type: entities\n"
            "    title: \"Batteria\"\n"
            "    entities:\n"
            "      - entity: sensor.inverter_pipsolar_battery_capacity\n"
            "        name: \"Carica %\"\n"
            "      - entity: sensor.inverter_pipsolar_battery_voltage\n"
            "        name: \"Tensione\"\n"
            "      - entity: sensor.carica_batteria_istantanea\n"
            "        name: \"Carica W\"\n"
            "      - entity: sensor.scarica_batteria_istantanea\n"
            "        name: \"Scarica W\"\n"
            "\n"
            "  - type: entities\n"
            "    title: \"Consumi\"\n"
            "    entities:\n"
            "      - entity: sensor.inverter_pipsolar_ac_output_active_power\n"
            "        name: \"Casa\"\n"
            "      - entity: sensor.shellyem_ec64c9c68991_channel_1_power\n"
            "        name: \"Rete Enel\""
        )
        return (
            "<pre>" + yaml + "</pre>\n\n"
            "📋 <i>Tieni premuto → Copia</i>\n"
            "🔧 Dashboard HA → ✏️ → + Aggiungi card → Manuale → Incolla"
        )

    def make_security_dashboard_yaml(self) -> str:
        """Card YAML per sicurezza."""
        ae, _ = self.home.primary_alarm()
        motion_eids = list(self.home.motion_sensors.keys())
        persons_eids = list(self.home.persons.keys())
        rows_motion  = "\n".join("      - " + e for e in motion_eids)
        rows_persons = "\n".join("      - " + e for e in persons_eids)
        yaml = (
            "type: vertical-stack\ncards:\n"
            "  - type: alarm-panel\n    entity: " + (ae or "alarm_control_panel.home_alarm") + "\n\n"
            "  - type: entities\n    title: \"Presenza\"\n    entities:\n" + rows_persons + "\n\n"
            "  - type: entities\n    title: \"Sensori Movimento (solo fisici)\"\n    entities:\n" + rows_motion
        )
        return (
            "<pre>" + yaml + "</pre>\n\n"
            "📋 <i>Tieni premuto → Copia</i>\n"
            "🔧 Dashboard HA → ✏️ → + Aggiungi card → Manuale → Incolla"
        )

    def make_room_lights_graph_card_yaml(self, user_yaml: str = "") -> str:
        """
        Genera YAML per room-lights-graph-card.
        Se user_yaml è fornito, estrae le entità da quello e le converte nel formato corretto.
        Altrimenti usa le entità della casa con filtri aggressivi anti-spazzatura.
        Output in <pre> per Telegram.
        """

        # ── Filtri anti-spazzatura ────────────────────────────────────────────
        # Luci da escludere: virtual screen (cast/chromecast), entità sconosciute
        LIGHT_EXCLUDE_KW = (
            "_screen", "cast_screen", "chromecast", "screen",
        )
        # Switch da escludere: solo switch fisici utili, non quelli di servizio
        SWITCH_EXCLUDE_KW = (
            "schedule_", "lavastoviglie", "echo", "alexa", "_shuffle", "_repeat",
            "_do_not_disturb", "permit_join", "zigbee2mqtt_bridge",
            "frigate_pre", "proxmox_pre", "proxmox_ve", "output_source_priority",
            "input_voltage_range", "pv_ok_condition", "pv_power_balance",
            "inverter_restart", "inverter_pipsolar",
            "thtr_", "ss_use_wake", "ss_led",
            "loft_detect", "loft_motion", "loft_recording", "loft_snapshot",
            "loft_review", "loft1_", "loft2_",
            "presenza_single", "presenza_bluetooth",
            "power_outage_memory", "do_not_disturb", "child_lock", "led_enable",
            "shellyem", "w20_ubea", "sonoff_1001", "ovunque_",
            "fire_tv", "samsung_soundbar", "soundbar",
            "lc_autofocus", "lc_lampada", "lc_tergicristallo",
            "latched_hidden", "none_tasmota",
        )
        # Temperatura: escludi batterie telefono, batterie watch, sensori dispositivo
        TEMP_EXCLUDE_KW = (
            "battery_temperature", "device_temperature", "echo_dot",
            "battery_temp", "huawei", "galaxy_watch", "samsung",
            "2o_echo", "echo_pop",
        )

        def _light_ok(eid: str) -> bool:
            el = eid.lower()
            return not any(k in el for k in LIGHT_EXCLUDE_KW)

        def _switch_ok(eid: str) -> bool:
            el = eid.lower()
            return not any(k in el for k in SWITCH_EXCLUDE_KW)

        def _temp_ok(eid: str) -> bool:
            el = eid.lower()
            return not any(k in el for k in TEMP_EXCLUDE_KW)

        zone_labels = {
            "cucina":          "Cucina",
            "salotto":         "Soggiorno",
            "camera_da_letto": "Camera da Letto",
            "bagno":           "Bagno",
            "ingresso":        "Ingresso",
            "garage":          "Garage",
            "esterno":         "Esterno",
            "ufficio":         "Ufficio",
            "interno":         "Interno",
        }

        # ── Se l'utente ha passato il suo YAML, estraiamo le entità da lì ────
        if user_yaml.strip():
            import re as _re
            # Estrai tutti gli entity_id dal YAML dell'utente
            found_entities = _re.findall(r'entity:\s*([\w.]+)', user_yaml)
            # Aggiungi anche quelli in formato semplice (- light.xxx o - switch.xxx)
            found_entities += _re.findall(r'-\s*((?:light|switch|sensor)\.\S+)', user_yaml)
            # Deduplicazione mantenendo ordine
            seen = set()
            entities = []
            for e in found_entities:
                e = e.strip()
                if e and e not in seen:
                    seen.add(e)
                    entities.append(e)

            if not entities:
                return "⚠️ Nessuna entità trovata nel YAML. Assicurati che le entità abbiano il formato <code>entity: light.xxx</code>"

            # Genera YAML della card con le entità dell'utente in un'unica stanza "Casa"
            # Se riconosce stanze diverse le separa, altrimenti mette tutto in "Casa"
            rooms: dict = {}
            for eid in entities:
                fn = self.cache.get(eid, {}).get("attributes", {}).get("friendly_name", "")
                zone = self.home._zone(fn, eid)
                rooms.setdefault(zone, {"lights": [], "switches": [], "temps": []})
                if eid.startswith("light."):
                    rooms[zone]["lights"].append((eid, fn))
                elif eid.startswith("switch."):
                    rooms[zone]["switches"].append(eid)
                elif eid.startswith("sensor."):
                    rooms[zone]["temps"].append((eid, fn))

        else:
            # ── Modalità automatica: prendi le entità della casa con filtri ──
            rooms: dict = {}
            for eid, v in self.home.lights.items():
                if not _light_ok(eid):
                    continue
                zone = v.get("zone", "interno")
                rooms.setdefault(zone, {"lights": [], "switches": [], "temps": []})
                rooms[zone]["lights"].append((eid, v.get("name", "")))

            sw_dict = getattr(self.home, "switches", {}) or {}
            for eid, v in sw_dict.items():
                if not _switch_ok(eid):
                    continue
                zone = self.home._zone(v.get("name", ""), eid)
                if zone in rooms:
                    rooms[zone]["switches"].append(eid)

            for eid, s in self.cache.items():
                if not _temp_ok(eid):
                    continue
                attrs = s.get("attributes", {})
                if attrs.get("device_class") != "temperature":
                    continue
                if s.get("state", "") in ("unavailable", "unknown", ""):
                    continue
                name = attrs.get("friendly_name", "")
                zone = self.home._zone(name, eid)
                if zone in rooms:
                    rooms[zone]["temps"].append((eid, name))

        if not rooms:
            return "⚠️ Nessuna entità trovata."

        # ── Costruisci YAML ───────────────────────────────────────────────────
        yaml_lines = [
            "# Room Lights Graph Card",
            "# Installa via HACS: https://github.com/ago19800/room-lights-graph-card",
            "type: custom:room-lights-graph-card",
            "title: Luci Casa",
            "rooms:",
        ]

        for zone, data in sorted(rooms.items()):
            label = zone_labels.get(zone, zone.replace("_", " ").title())
            yaml_lines.append(f"  - name: {label}")

            if data["lights"]:
                yaml_lines.append("    lights:")
                for eid, ha_name in data["lights"]:
                    fn = self.cache.get(eid, {}).get("attributes", {}).get("friendly_name", ha_name)
                    short = fn.split()[-1] if fn else eid.split(".")[-1][:14]
                    yaml_lines.append(f"      - entity: {eid}")
                    yaml_lines.append(f'        name: "{short}"')

            if data["switches"]:
                yaml_lines.append("    switches:")
                for eid in data["switches"]:
                    fn = self.cache.get(eid, {}).get("attributes", {}).get("friendly_name", "")
                    short = fn.split()[-1] if fn else eid.split(".")[-1][:14]
                    yaml_lines.append(f"      - entity: {eid}")
                    yaml_lines.append(f'        name: "{short}"')

            if data["temps"]:
                yaml_lines.append("    temperature_sensors:")
                for eid, tname in data["temps"]:
                    fn = self.cache.get(eid, {}).get("attributes", {}).get("friendly_name", tname)
                    short = fn.split()[-1] if fn else "Temp"
                    yaml_lines.append(f"      - entity: {eid}")
                    yaml_lines.append(f'        name: "{short}"')

        yaml_str = "\n".join(yaml_lines)

        mode_note = (
            "📋 <i>Entità dal tuo YAML</i>\n" if user_yaml.strip()
            else "📋 <i>Entità rilevate automaticamente dalla casa</i>\n"
        )

        return (
            "<pre>" + yaml_str + "</pre>\n\n"
            + mode_note +
            "🔧 Dashboard HA → ✏️ → + Aggiungi card → Manuale → Incolla\n"
            "⚠️ Richiede <b>room-lights-graph-card</b> via HACS"
        )

