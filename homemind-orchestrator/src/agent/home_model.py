"""
home_model.py v27

PROBLEMA RILEVATO:
- "Mqtt" viene riconosciuto come persona → everyone_away() mai True → allarme mai scatta
- 45 "sensori fisici" = filtro troppo debole

SOLUZIONE:
1. PERSONE: solo person.* con nome umano (esclude Mqtt, router, device, bot, ecc.)
2. MOVIMENTO: solo binary_sensor con device_class=motion E nome/eid che contiene
   parole tipiche di sensori PIR fisici. Tutto il resto escluso.
3. Override config: /config/homemind_patches/person_config.json (opzionale)
"""
import logging, json, aiofiles
from pathlib import Path

logger     = logging.getLogger("homemind.model")
MODEL_FILE  = Path("/config/homemind_patches/home_model.json")
CONFIG_FILE = Path("/config/homemind_patches/person_config.json")

# ── Persone: parole che identificano NON-umani ────────────────────────────────
# Se il nome o entity_id contiene una di queste → NON è una persona
PERSON_EXCLUDE = {
    "mqtt", "bot", "router", "gateway", "bridge", "hub", "switch",
    "esp", "esp32", "esp8266", "tasmota", "shelly", "sonoff", "zigbee",
    "z-wave", "zwave", "wifi", "wlan", "lan", "network",
    "camera", "cam", "telecamera", "doorbell", "sensor", "sensore",
    "printer", "tv", "televisore", "chromecast", "fire", "roku",
    "alexa", "google_home", "echo", "homepod",
    "device", "tracker", "unknown", "none",
}

# ── Movimento: SOLO device_class=motion con queste parole nel nome/eid ────────
# Approccio WHITELIST: se il testo NON contiene almeno una di queste → escluso
MOTION_WHITELIST = {
    "motion", "movimento", "pir", "detect", "intrus",
    "mov_", "_mov", "sensor_mov",
}

# Parole che ESCLUDONO sempre (alta priorità)
MOTION_BLACKLIST = {
    # app telefono
    "sm_s", "sm_a", "sm_g", "sm_n",   # Samsung model numbers
    "iphone", "ipad", "phone", "mobile", "cellulare",
    "android", "companion", "app_",
    # telecamere
    "camera", "cam_", "_cam", "imou", "hikvision", "dahua", "reolink",
    "amcrest", "arlo", "ring", "doorbell", "loft", "garage_cam",
    "cortile", "mainstream", "profile",  # nomi tipici stream cam
    # rete
    "router", "wifi", "wlan", "bt_", "bluetooth", "beacon", "ble_",
    # altri non fisici
    "charging", "battery_state", "connectivity", "network", "update",
    "signal", "rssi", "lqi", "link_quality",
    # sensori ambientali non PIR
    "occupancy_timeout", "no_presence_duration",
}

def _is_human_person(name: str, eid: str) -> bool:
    """True se l'entità sembra una persona reale."""
    text = (name + " " + eid).lower().replace(".", " ").replace("_", " ")
    for kw in PERSON_EXCLUDE:
        if kw in text:
            logger.debug("Person EXCLUDE %s (kw=%s)", eid, kw)
            return False
    # Deve avere almeno un token alfabetico che sembri un nome
    parts = [p for p in text.split() if len(p) >= 2 and p.isalpha()]
    return bool(parts)

def _is_uuid_eid(eid: str) -> bool:
    """True se entity_id ha nome hex casuale tipo 'ed19d1b5_809d029f' (entità zombie)."""
    import re
    # Prende la parte dopo il dominio
    local = eid.split(".", 1)[-1] if "." in eid else eid
    # Pattern: almeno 6 caratteri hex seguiti da _ o alla fine
    hex_blocks = re.findall(r'[0-9a-f]{6,}', local.lower())
    # Se più di metà del nome è hex → probabilmente UUID/zombie
    if hex_blocks:
        hex_len = sum(len(b) for b in hex_blocks)
        if hex_len >= len(local) * 0.6:
            return True
    return False


def _is_real_pir(name: str, eid: str, dc: str) -> bool:
    """True solo se è un sensore PIR fisico reale."""
    # Escludi entity_id con nomi UUID/esadecimali (entità zombie/non configurate)
    if _is_uuid_eid(eid):
        logger.debug("Motion SKIP %s (UUID/zombie eid)", eid)
        return False

    # Solo device_class=motion è considerato affidabile come PIR fisico
    # occupancy/presence possono essere sensori mmWave, telefono, camera → troppo rumore
    if dc not in ("motion",):
        # vibration ok se ha il nome giusto
        if dc == "vibration":
            return True
        logger.debug("Motion SKIP %s (dc=%s non è motion/vibration)", eid, dc)
        return False

    text = (name + " " + eid).lower()

    # Blacklist ha priorità assoluta
    for kw in MOTION_BLACKLIST:
        if kw in text:
            logger.debug("Motion BLACKLIST %s (kw=%s)", eid, kw)
            return False

    # Per device_class=motion: accetta SE ha keyword fisico O se non ha nomi sospetti
    has_whitelist = any(kw in text for kw in MOTION_WHITELIST)
    if has_whitelist:
        return True

    # device_class=motion senza keyword specifico: accetta solo se eid non ha
    # pattern di telefono (es: "binary_sensor.sm_s931b_xxx")
    phone_patterns = ["sm_", "iph", "oneplus", "pixel", "xiaomi", "redmi",
                      "huawei", "oppo", "realme", "poco"]
    for p in phone_patterns:
        if p in text:
            logger.debug("Motion PHONE %s", eid)
            return False

    # Accetta — è motion e non è sospetto
    return True


class HomeModel:
    def __init__(self, person_blacklist: list = None, motion_blacklist: list = None):
        self.persons:          dict = {}
        self.motion_sensors:   dict = {}
        self.contact_sensors:  dict = {}   # porte/finestre (device_class: door/window)
        self.lights:           dict = {}
        self.climate:          dict = {}
        self.alarm_panels:     dict = {}
        self._alarm_panel_override: str = ""  # da person_config.json
        self._alarm_extra_panels: list = []   # partizioni extra da armare insieme
        self._alarm_arm_mode: str = "armed_away"  # modalità armamento
        self._alarm_enabled:  bool = True         # False = HomeMind non tocca mai l'allarme
        self._alarm_auto_arm:  str  = "auto"         # "auto"|"disabled"|"notify"
        self._alarm_disable_entities: bool = True  # disabled: True=spegne entità, False=solo notifica
        self._alarm_disable_notify:   bool = True  # disabled+no entità: True=manda notifica, False=silenzio totale
        self._alarm_on_leave: list = []         # entity_id da spegnere all'uscita
        self._climate_config: dict = {}        # da person_config.json
        # Do Not Disturb
        self.quiet_hours_start: int | None = None
        self.quiet_hours_end:   int | None = None
        # Clima auto-off quando casa vuota
        self._climate_auto_off: bool = True   # default: spegne clima all'uscita
        self._climate_exclude:  list = []     # entità clima da NON spegnere mai
        self.cameras:          dict = {}
        self.covers:           dict = {}
        self.switches:         dict = {}
        # Valori BASE dalle opzioni add-on (non vengono mai azzerati)
        self._base_person_blacklist: list = list(person_blacklist or [])
        self._base_motion_blacklist: list = list(motion_blacklist or [])
        # Liste effettive (base + eventuale file config)
        self._person_whitelist:  list = []
        self._person_blacklist:  list = list(self._base_person_blacklist)
        self._motion_whitelist:  list = []
        self._motion_blacklist:  list = list(self._base_motion_blacklist)
        self._contact_whitelist: list = []   # vuota = tutti i contatti accettati
        self._contact_blacklist: list = []
        self.motion_threshold_override: int = 0   # 0 = auto (gestito da SecurityManager)
        # Sensori distanza per override GPS: {person_eid: {sensor, threshold_m, current_m}}
        self.proximity_sensors: dict = {}
        logger.info("Blacklist da opzioni add-on: persone=%s movimento=%s",
                    self._base_person_blacklist, self._base_motion_blacklist)
        self._load_config()
        if self._motion_blacklist:
            logger.info("Motion blacklist attiva: %s", self._motion_blacklist)

    def _load_config(self):
        """Carica override manuali da /config/homemind_patches/person_config.json"""
        if not CONFIG_FILE.exists():
            logger.info("Nessun config override trovato in %s", CONFIG_FILE)
            return
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)

            def clean(lst):
                # Rimuove commenti e stringhe non valide come entity_id
                return [x for x in lst
                        if isinstance(x, str)
                        and not x.startswith("_comment")
                        and "." in x]  # entity_id valido ha sempre un punto

            # Merge: aggiungi al file quelli già passati via env/parametro
            for x in clean(cfg.get("person_whitelist", [])):
                if x not in self._person_whitelist: self._person_whitelist.append(x)
            for x in clean(cfg.get("person_blacklist", [])):
                if x not in self._person_blacklist: self._person_blacklist.append(x)
            for x in clean(cfg.get("motion_whitelist", [])):
                if x not in self._motion_whitelist: self._motion_whitelist.append(x)
            for x in clean(cfg.get("motion_blacklist", [])):
                if x not in self._motion_blacklist: self._motion_blacklist.append(x)
            for x in clean(cfg.get("contact_whitelist", [])):
                if x not in self._contact_whitelist: self._contact_whitelist.append(x)
            for x in clean(cfg.get("contact_blacklist", [])):
                if x not in self._contact_blacklist: self._contact_blacklist.append(x)

            self.motion_threshold_override = int(cfg.get("motion_threshold", 0))

            # Pannello allarme personalizzato (opzionale)
            # alarm_panel: accetta sia stringa che oggetto {entity, arm_mode}
            _ap_raw = cfg.get("alarm_panel", "")
            if isinstance(_ap_raw, dict):
                alarm_panel = _ap_raw.get("entity", "").strip()
                arm_mode    = _ap_raw.get("arm_mode", "armed_away")
                self._alarm_arm_mode = arm_mode
            elif isinstance(_ap_raw, str):
                alarm_panel = _ap_raw.strip()
                self._alarm_arm_mode = "armed_away"
            else:
                alarm_panel = ""
                self._alarm_arm_mode = "armed_away"
            if alarm_panel and "." in alarm_panel:
                self._alarm_panel_override = alarm_panel
                logger.info("  alarm_panel: %s (personalizzato, arm_mode=%s)",
                            alarm_panel, self._alarm_arm_mode)
            else:
                self._alarm_panel_override = ""

            # Gestione allarme abilitato/disabilitato
            # alarm_enabled: true (default) = HomeMind arma/disarma automaticamente
            #                false          = HomeMind NON tocca mai l'allarme
            self._alarm_enabled = bool(cfg.get("alarm_enabled", True))
            if not self._alarm_enabled:
                logger.info("  alarm_enabled: FALSE — HomeMind NON gestirà l'allarme")

            # alarm_auto_arm — tre modalità:
            #   "auto"     (default) → arma/disarma automaticamente
            #   "disabled"           → non tocca mai l'allarme
            #   "notify"             → chiede conferma via Telegram prima di armare
            # Backward compat: alarm_enabled=false → "disabled"
            _raw_mode = cfg.get("alarm_auto_arm", None)
            if _raw_mode in ("auto", "disabled", "notify"):
                self._alarm_auto_arm = _raw_mode
            elif not self._alarm_enabled:
                self._alarm_auto_arm = "disabled"
            else:
                self._alarm_auto_arm = "auto"
            logger.info("  alarm_auto_arm: %s", self._alarm_auto_arm)

            # alarm_disable_entities: solo per modalità "disabled"
            # True (default) = spegne comunque le entità configurate all'uscita
            # False = solo notifica "casa vuota", non tocca niente
            self._alarm_disable_entities = bool(cfg.get("alarm_disable_entities", True))
            # alarm_disable_notify: solo per modalità "disabled" + alarm_disable_entities=False
            # True (default) = manda notifica "casa vuota" su Telegram
            # False = silenzio totale, nessuna notifica
            self._alarm_disable_notify = bool(cfg.get("alarm_disable_notify", True))
            if self._alarm_auto_arm == "disabled":
                logger.info("  alarm_disable_entities: %s", self._alarm_disable_entities)
                logger.info("  alarm_disable_notify: %s", self._alarm_disable_notify)

            # alarm_on_leave — lista entity_id da spegnere/chiudere quando tutti escono
            # Se vuoto/assente → comportamento legacy (spegni tutte le luci + clima auto-off)
            _aol = cfg.get("alarm_on_leave", [])
            self._alarm_on_leave = [e for e in _aol if isinstance(e, str) and e.strip()] if isinstance(_aol, list) else []
            if self._alarm_on_leave:
                logger.info("  alarm_on_leave: %d entità configurate", len(self._alarm_on_leave))

            # Partizioni extra (Paradox multi-partition, ecc.)
            _extra = cfg.get("alarm_extra_panels", [])
            if isinstance(_extra, list):
                self._alarm_extra_panels = [e for e in _extra if isinstance(e, str) and "." in e]
                if self._alarm_extra_panels:
                    logger.info("  alarm_extra_panels: %s", self._alarm_extra_panels)

            # Configurazione clima personalizzata
            climate_cfg = cfg.get("climate", {})
            if climate_cfg:
                self._climate_config = climate_cfg
                logger.info("  climate: %d entità configurate", len(climate_cfg))
            else:
                self._climate_config = {}

            # Sensori prossimità: {"person.agostino": {"sensor": "sensor.xxx", "threshold_m": 100}}
            # oppure lista: [{"person": "person.agostino", "sensor": "sensor.xxx", "threshold_m": 100}]
            prox_cfg = cfg.get("proximity_sensors", {})
            if isinstance(prox_cfg, list):
                prox_cfg = {p["person"]: p for p in prox_cfg if "person" in p}
            self.proximity_sensors.clear()
            for person_eid, pcfg in prox_cfg.items():
                if isinstance(pcfg, str):
                    # formato breve: "person.agostino": "sensor.distanza"
                    pcfg = {"sensor": pcfg}
                sensor_eid   = pcfg.get("sensor", "")
                threshold_m  = int(pcfg.get("threshold_m", 100))
                max_age_min  = int(pcfg.get("max_age_min", 30))
                stale_check  = bool(pcfg.get("stale_check", True))  # False = mai disattivare per dati vecchi
                if sensor_eid:
                    self.proximity_sensors[person_eid] = {
                        "sensor":       sensor_eid,
                        "threshold_m":  threshold_m,
                        "max_age_min":  max_age_min,
                        "stale_check":  stale_check,
                        "current_m":    None,   # aggiornato live
                        "last_seen":    None,   # timestamp ultimo aggiornamento live
                        "last_near_ts": None,   # timestamp ultimo "vicino" — sticky 5min
                    }

            # ── Do Not Disturb ───────────────────────────────────────────
            qh = cfg.get("quiet_hours", {})
            if isinstance(qh, dict) and qh.get("enabled", False):
                qs = int(qh.get("start", 23))
                qe = int(qh.get("end",   7))
                if 0 <= qs <= 23 and 0 <= qe <= 23:
                    self.quiet_hours_start = qs
                    self.quiet_hours_end   = qe
                    logger.info("  DND: %02d:00 → %02d:00 (attivo)", qs, qe)
                else:
                    logger.warning("  DND: valori non validi — disabilitato")
                    self.quiet_hours_start = None
                    self.quiet_hours_end   = None
            else:
                self.quiet_hours_start = None
                self.quiet_hours_end   = None

            # ── Clima auto-off ───────────────────────────────────────────
            self._climate_auto_off = bool(cfg.get("climate_auto_off", True))
            if not self._climate_auto_off:
                logger.info("  climate_auto_off: DISABILITATO — il clima NON viene spento all'uscita")
            _excl = cfg.get("climate_exclude", [])
            if isinstance(_excl, list):
                self._climate_exclude = [e for e in _excl if isinstance(e, str) and "." in e]
                if self._climate_exclude:
                    logger.info("  climate_exclude: %s", self._climate_exclude)

            logger.info("Config caricato da %s:", CONFIG_FILE)
            logger.info("  person_whitelist: %s", self._person_whitelist)
            logger.info("  person_blacklist: %s", self._person_blacklist)
            logger.info("  motion_whitelist: %s", self._motion_whitelist)
            logger.info("  motion_blacklist: %s", self._motion_blacklist)
            if self._contact_whitelist:
                logger.info("  contact_whitelist: %s", self._contact_whitelist)
            if self._contact_blacklist:
                logger.info("  contact_blacklist: %s", self._contact_blacklist)
            if self.proximity_sensors:
                for p, v in self.proximity_sensors.items():
                    logger.info("  proximity: %s → %s (soglia %dm)", p, v["sensor"], v["threshold_m"])
            if self.motion_threshold_override:
                logger.info("  motion_threshold: %d (manuale)", self.motion_threshold_override)
        except json.JSONDecodeError as e:
            logger.error("Config JSON non valido: %s — override IGNORATI", e)
        except Exception as e:
            logger.warning("Config load failed: %s", e)

    def build_from_cache(self, cache: dict):
        self._load_config()
        self.persons.clear(); self.motion_sensors.clear()
        self.lights.clear();  self.climate.clear()
        self.alarm_panels.clear(); self.cameras.clear()
        self.covers.clear();  self.switches.clear()
        self.contact_sensors.clear()

        excluded_persons = []
        excluded_motion  = []

        for eid, state in cache.items():
            domain = eid.split(".")[0]
            attrs  = state.get("attributes", {})
            name   = attrs.get("friendly_name", eid)
            st     = state.get("state", "unknown")
            dc     = attrs.get("device_class", "")

            if domain == "person":
                logger.info("Controllo person: %s | blacklist=%s | in_blacklist=%s",
                            eid, self._person_blacklist, eid in self._person_blacklist)
                if eid in self._person_blacklist:
                    excluded_persons.append(eid + " (blacklist)")
                    continue
                if eid in self._person_whitelist or _is_human_person(name, eid):
                    self.persons[eid] = {"name": name, "state": st}
                else:
                    excluded_persons.append(eid + " (non umano: " + name + ")")

            elif domain == "binary_sensor" and dc in ("motion","occupancy","presence","vibration"):
                if eid in self._motion_blacklist:
                    excluded_motion.append(eid + " (blacklist)")
                    continue
                # Se whitelist definita → modalità ESCLUSIVA: solo sensori in lista
                if self._motion_whitelist:
                    if eid in self._motion_whitelist:
                        zone = self._zone(name, eid)
                        self.motion_sensors[eid] = {
                            "name": name, "zone": zone, "state": st, "device_class": dc
                        }
                    else:
                        excluded_motion.append(eid + " (non in whitelist)")
                else:
                    # Nessuna whitelist → filtro automatico
                    if _is_real_pir(name, eid, dc):
                        zone = self._zone(name, eid)
                        self.motion_sensors[eid] = {
                            "name": name, "zone": zone, "state": st, "device_class": dc
                        }
                    else:
                        excluded_motion.append(eid)

            elif domain == "binary_sensor" and dc in ("door", "window", "opening", "garage_door"):
                # Escludi sensori NON di sicurezza per nome (elettrodomestici, ecc.)
                IGNORE_NAMES = ("lavastoviglie", "lavatrice", "lavasciuga", "frigorifero",
                                "dishwasher", "washing", "fridge", "freezer", "oven", "microwave")
                name_low = name.lower()
                if any(k in name_low or k in eid.lower() for k in IGNORE_NAMES):
                    continue
                # Escludi unavailable/unknown
                if st in ("unavailable", "unknown"):
                    continue
                contact_wl = getattr(self, "_contact_whitelist", [])
                contact_bl = getattr(self, "_contact_blacklist", [])
                if eid in contact_bl:
                    continue
                if not contact_wl or eid in contact_wl:
                    zone = self._zone(name, eid)
                    # Inferisci device_class da nome se HA non lo distingue
                    if dc not in ("door", "window", "garage_door"):
                        name_l = name.lower() + " " + eid.lower()
                        if any(k in name_l for k in ("finestra", "window", "vetro")):
                            dc = "window"
                        elif any(k in name_l for k in ("garage",)):
                            dc = "garage_door"
                        else:
                            dc = "door"
                    self.contact_sensors[eid] = {
                        "name": name, "zone": zone, "state": st, "device_class": dc
                    }

            elif domain == "light":
                self.lights[eid] = {"name": name, "state": st}
            elif domain == "climate":
                self.climate[eid] = {"name": name, "state": st}
            elif domain == "alarm_control_panel":
                self.alarm_panels[eid] = {"name": name, "state": st}
            elif domain == "camera":
                self.cameras[eid] = {"name": name}
            elif domain == "cover":
                _cover_attrs = cache.get(eid, {}).get("attributes", {})
                _position    = _cover_attrs.get("current_position")  # 0=chiuso, 100=aperto
                _tilt        = _cover_attrs.get("current_tilt_position")
                self.covers[eid] = {
                    "name":     name,
                    "state":    st,
                    "position": _position,   # None se non disponibile
                    "tilt":     _tilt,
                }
            elif domain == "switch":
                self.switches[eid] = {"name": name, "state": st}

        # ── Log dettagliato ──────────────────────────────────────────────────
        logger.info("=== HOME MODEL BUILD v34 ===")
        logger.info("PERSONE ACCETTATE (%d):", len(self.persons))
        for eid, v in self.persons.items():
            logger.info("  ✅ %s = %s (%s)", eid, v["state"], v["name"])
        if excluded_persons:
            logger.info("PERSONE ESCLUSE (%d):", len(excluded_persons))
            for e in excluded_persons:
                logger.info("  ❌ %s", e)

        logger.info("SENSORI MOVIMENTO ACCETTATI (%d)%s:", len(self.motion_sensors),
                    " [WHITELIST ESCLUSIVA]" if self._motion_whitelist else " [filtro auto]")
        for eid, v in self.motion_sensors.items():
            logger.info("  ✅ %s = %s (zona=%s)", eid, v["state"], v["zone"])
        if excluded_motion:
            logger.info("SENSORI ESCLUSI (%d) — vedi log DEBUG per dettagli", len(excluded_motion))

        if self.contact_sensors:
            logger.info("SENSORI CONTATTO (%d):", len(self.contact_sensors))
            for eid, v in self.contact_sensors.items():
                icon = "🔓" if v["state"] == "on" else "🔒"
                logger.info("  %s %s = %s (%s)", icon, eid, v["state"], v["name"])

        # ── Inizializza current_m dei sensori prossimità dalla cache ──────────
        from datetime import datetime, timezone as _tz
        for person_eid, prox in self.proximity_sensors.items():
            sensor_eid = prox["sensor"]
            if sensor_eid in cache:
                raw      = cache[sensor_eid].get("state", "")
                last_upd = cache[sensor_eid].get("last_updated", "")
                try:
                    dist_m = float(raw)
                    # Calcola età dell'ultimo aggiornamento
                    age_min = None
                    if last_upd:
                        try:
                            upd_dt  = datetime.fromisoformat(last_upd.replace("Z", "+00:00"))
                            age_min = (datetime.now(_tz.utc) - upd_dt).total_seconds() / 60
                        except Exception:
                            pass

                    max_age = int(prox.get("max_age_min", 30))  # default 30 min
                    do_stale = prox.get("stale_check", True)    # False = mai considerare stale
                    stale   = do_stale and age_min is not None and age_min > max_age
                    person_name = self.persons.get(person_eid, {}).get("name", person_eid)

                    if stale:
                        logger.warning("PROXIMITY init: %s = %.0fm ma dati VECCHI (%.0f min fa, max %d min) "
                                       "— override DISATTIVATO per sicurezza",
                                       person_name, dist_m, age_min, max_age)
                        prox["current_m"] = None  # disattiva override
                    elif not do_stale and age_min is not None and age_min > max_age:
                        # stale_check=false: mantieni valore numerico per calcoli distanza
                        # MA non impostare sticky (last_near_ts) se i dati sono troppo vecchi
                        # Questo evita falsi "in casa" quando il sensore è fermo da ore
                        import time as _t
                        prox["current_m"] = dist_m
                        prox["last_seen"] = _t.time() - (age_min * 60) if age_min else None
                        is_near = dist_m <= prox["threshold_m"]
                        # Sticky solo se dati non troppo vecchi (max 2x max_age)
                        if is_near and age_min <= (max_age * 2):
                            prox["last_near_ts"] = _t.time()
                        else:
                            prox["last_near_ts"] = None  # dati stale → no sticky
                        _sticky_note = " [sticky]" if (is_near and age_min <= max_age * 2) else " [stale→no sticky]"
                        logger.info("PROXIMITY init: %s = %.0fm (dati %.0f min fa) — stale_check=false → near=%s%s",
                                    person_name, dist_m, age_min, is_near, _sticky_note)
                    else:
                        prox["current_m"] = dist_m
                        import time as _t
                        # Imposta last_seen basandosi su last_updated della cache
                        prox["last_seen"] = _t.time() - (age_min * 60) if age_min else _t.time()
                        is_near  = dist_m <= prox["threshold_m"]
                        if is_near:
                            prox["last_near_ts"] = _t.time()  # sticky attivo da subito
                        age_str  = f"{age_min:.0f} min fa" if age_min is not None else "età ignota"
                        logger.info("PROXIMITY init: %s = %.0fm (soglia %dm) → near=%s [aggiornato %s]",
                                    person_name, dist_m, prox["threshold_m"], is_near, age_str)

                except (ValueError, TypeError):
                    prox["current_m"] = None
                    logger.warning("PROXIMITY init: %s stato non numerico (%r) — ignorato",
                                   sensor_eid, raw)
            else:
                logger.warning("PROXIMITY init: sensore %s NON trovato in cache — "
                               "override disattivo fino al primo aggiornamento. "
                               "Verifica che l'entity_id sia corretto.", sensor_eid)

        alarm_eid, alarm_st = self.primary_alarm()
        logger.info("ALLARME: %s = %s", alarm_eid or "NON TROVATO", alarm_st)
        logger.info("everyone_away = %s", self.everyone_away())

        if not self.persons:
            logger.warning(
                "⚠️  NESSUNA PERSONA TROVATA — antifurto disabilitato!\n"
                "   Verifica: HA → Impostazioni → Persone\n"
                "   Oppure crea %s con person_whitelist:[\"person.xxx\"]",
                str(CONFIG_FILE)
            )
        logger.info("========================")

    def _zone(self, name: str, eid: str) -> str:
        kw = {
            "garage":"garage","giardino":"esterno","cortile":"esterno",
            "ingresso":"ingresso","entrata":"ingresso","porta":"ingresso",
            "cucina":"cucina","salotto":"salotto","soggiorno":"salotto",
            "camera":"camera_da_letto","letto":"camera_da_letto",
            "bagno":"bagno","ufficio":"ufficio","studio":"ufficio",
            "living":"salotto","kitchen":"cucina","bedroom":"camera_da_letto",
        }
        text = (name + " " + eid).lower()
        for k, z in kw.items():
            if k in text:
                return z
        return "interno"

    def update_state(self, eid: str, new_st: str, attrs: dict = None):
        for d in [self.persons, self.motion_sensors, self.contact_sensors, self.lights,
                  self.climate, self.alarm_panels, self.switches]:
            if eid in d:
                d[eid]["state"] = new_st
                return
        # Cover: aggiorna anche position
        if eid in self.covers:
            self.covers[eid]["state"] = new_st
            if attrs:
                pos = attrs.get("current_position")
                if pos is not None:
                    self.covers[eid]["position"] = pos

    @staticmethod
    def _is_home_state(state: str) -> bool:
        """
        True se la persona è IN CASA.
        HA usa "home" oppure il nome della zona home (es: "Casa", "Home").
        Tutto il resto (not_home, away, Lavoro, Ufficio, ecc.) = fuori.
        """
        s = state.lower().strip()
        return s in ("home", "casa", "home_zone", "zona_casa", "at_home")

    def _is_near(self, person_eid: str) -> bool:
        """True se il sensore distanza dice che la persona è vicino/in casa.
        Sticky: se era vicino negli ultimi 5 minuti, considera ancora vicino
        anche se il valore attuale è rimbalzato temporaneamente."""
        import time as _time
        prox = self.proximity_sensors.get(person_eid)
        if not prox:
            return False

        now = _time.time()

        # ── Sticky: era vicino negli ultimi 5 minuti → override attivo ────
        last_near = prox.get("last_near_ts")
        if last_near is not None and (now - last_near) < 300:
            logger.debug("PROXIMITY sticky: %s era vicino %.0fs fa — override attivo",
                         person_eid, now - last_near)
            return True

        if prox["current_m"] is None:
            return False
        try:
            last_seen = prox.get("last_seen")
            if last_seen is not None:
                age_min = (now - last_seen) / 60
                max_age = int(prox.get("max_age_min", 30))
                if age_min > max_age:
                    logger.debug("PROXIMITY stale (%.0f min fa, max %d) — override ignorato", age_min, max_age)
                    return False
            is_near = float(prox["current_m"]) <= prox["threshold_m"]
            if is_near:
                prox["last_near_ts"] = now   # salva timestamp ultimo "vicino"
            return is_near
        except (ValueError, TypeError):
            return False

    def _person_is_home(self, person_eid: str) -> bool:
        """True se la persona è a casa — sensore distanza ha priorità su GPS.

        Se proximity ha un valore valido → vince SEMPRE sul GPS:
          - dist ≤ threshold → a casa  (anche se GPS dice away)
          - dist > threshold → fuori   (anche se GPS dice home) ← fix bug
        Se proximity non configurato o senza dati → solo GPS.
        """
        import time as _t
        v    = self.persons.get(person_eid, {})
        gps  = self._is_home_state(v.get("state", ""))
        prox = self.proximity_sensors.get(person_eid)

        if prox:
            current_m = prox.get("current_m")
            last_near = prox.get("last_near_ts")
            last_seen = prox.get("last_seen")
            do_stale  = prox.get("stale_check", True)

            # Se abbiamo un valore fresco (aggiornato entro 5 min) → VINCE SEMPRE
            # Un valore fresco è affidabile sia per casa che per fuori
            reading_fresh = (last_seen is not None and (_t.time() - last_seen) < 300)

            if current_m is not None and reading_fresh:
                is_near = float(current_m) <= prox["threshold_m"]
                if is_near:
                    prox["last_near_ts"] = _t.time()  # aggiorna sticky
                else:
                    prox["last_near_ts"] = None        # pulisci sticky: uscita confermata dal sensore
                if is_near != gps:
                    logger.info("Proximity override %s: dist=%.0fm → a_casa=%s (GPS=%s)",
                                person_eid, current_m, is_near, gps)
                return is_near

            # Nessun valore fresco — usa sticky per proteggere da rimbalzi GPS
            # stale_check=false: sticky 2h (GPS ballerino)
            # stale_check=true:  sticky 5 min
            if last_near is not None:
                sticky_sec = 7200 if not do_stale else 300
                if (_t.time() - last_near) < sticky_sec:
                    logger.debug("Proximity sticky %s: ultimo vicino %.0fs fa", person_eid, _t.time() - last_near)
                    return True

            # Nessun dato fresco e sticky scaduto → usa valore corrente se disponibile
            # Ma con un limite: se i dati sono più vecchi di 4 ore, anche con
            # stale_check=false non possiamo fidarci → cede al GPS
            MAX_STALE_SEC = 14400  # 4 ore = limite assoluto per current_m
            data_age = (_t.time() - last_seen) if last_seen else 999999
            if current_m is not None and data_age < MAX_STALE_SEC:
                is_near = float(current_m) <= prox["threshold_m"]
                if is_near != gps:
                    logger.info("Proximity override %s (dati vecchi %.0fmin): dist=%.0fm → a_casa=%s (GPS=%s)",
                                person_eid, data_age/60, current_m, is_near, gps)
                return is_near
            elif current_m is not None:
                logger.info("Proximity %s: dati troppo vecchi (%.0fmin > 240min) → cedo al GPS (%s)",
                            person_eid, data_age/60, gps)


        # Nessun proximity o nessun dato → solo GPS
        return gps

    def everyone_away(self) -> bool:
        if not self.persons:
            return False
        states = {v["name"]: v["state"] for v in self.persons.values()}
        result = all(not self._person_is_home(eid) for eid in self.persons)
        logger.debug("everyone_away=%s | %s", result, states)
        return result

    def someone_home(self) -> bool:
        return any(self._person_is_home(eid) for eid in self.persons)

    def who_is_home(self) -> list:
        return [v["name"] for eid, v in self.persons.items()
                if self._person_is_home(eid)]

    def who_is_away(self) -> list:
        return [v["name"] + " (" + v["state"] + ")"
                for eid, v in self.persons.items()
                if not self._person_is_home(eid)]

    def lights_on(self) -> list:
        return [eid for eid, v in self.lights.items() if v["state"] == "on"]

    def primary_alarm(self) -> tuple:
        if not self.alarm_panels:
            return ("", "unknown")
        # 1. Override da person_config.json → alarm_panel
        if self._alarm_panel_override:
            eid = self._alarm_panel_override
            if eid in self.alarm_panels:
                return (eid, self.alarm_panels[eid]["state"])
            else:
                logger.warning("alarm_panel configurato (%s) non trovato in HA — uso automatico", eid)
        # 2. Preferisce home_alarm (default HA)
        for eid in self.alarm_panels:
            if "home_alarm" in eid:
                return (eid, self.alarm_panels[eid]["state"])
        # 3. Primo disponibile
        eid = next(iter(self.alarm_panels))
        return (eid, self.alarm_panels[eid]["state"])

    def any_motion_active(self) -> list:
        return [eid for eid, v in self.motion_sensors.items() if v["state"] == "on"]

    def summary(self) -> dict:
        ae, ast_ = self.primary_alarm()
        return {
            "everyone_away": self.everyone_away(),
            "who_is_home":   self.who_is_home(),
            "who_is_away":   self.who_is_away(),
            "lights_on":     self.lights_on(),
            "alarm_entity":  ae,
            "alarm_state":   ast_,
            "motion_active": self.any_motion_active(),
            "motion_total":  len(self.motion_sensors),
            "has_persons":   bool(self.persons),
            "persons":       {e: {"name": v["name"], "state": v["state"]}
                              for e, v in self.persons.items()},
        }

    async def save(self):
        MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = self.summary()
            # Aggiungi lista sensori per debug
            data["motion_sensors_list"] = {
                e: {"name": v["name"], "zone": v["zone"], "state": v["state"]}
                for e, v in self.motion_sensors.items()
            }
            async with aiofiles.open(str(MODEL_FILE), "w") as f:
                await f.write(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.debug("save: %s", e)
