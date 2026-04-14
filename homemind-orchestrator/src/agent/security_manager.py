"""security_manager.py v55 — Sicurezza deterministica con cross-referencing."""
import asyncio, logging, time
from datetime import datetime
from utils.timezone_helper import now_local
from agent.home_model import HomeModel

logger = logging.getLogger("homemind.security")

MOTION_DELAY        = 8    # secondi attesa prima di triggerare allarme
STARTUP_DELAY       = 30   # secondi dopo avvio prima del check iniziale
ARM_COOLDOWN        = 180  # secondi minimo tra due armamenti (3 min anti-GPS oscillante)
DISARM_COOLDOWN     = 30

# Cross-referencing: quanti sensori devono scattare entro questa finestra
# per considerare un allarme reale (riduce falsi positivi).
# Se la whitelist ha 1 solo sensore → soglia automaticamente 1.
CROSS_REF_WINDOW    = 45   # secondi: finestra temporale cross-referencing
CROSS_REF_THRESHOLD = 2    # quanti sensori devono scattare (se disponibili ≥ 2)
# Nota: con ≤ 3 sensori la soglia scende automaticamente a 1 (vedi _get_threshold)

# Notifiche movimento anche quando qualcuno è in casa
HOME_MOTION_COOLDOWN = 120  # secondi tra due notifiche dallo stesso sensore (evita spam)


class SecurityManager:
    def __init__(self, home: HomeModel, rest_client, notifier=None, alarm_code="1234", frigate_client=None, tg_bot=None, cache_cb=None):
        self.home       = home
        self.rest       = rest_client
        self.notifier   = notifier
        self.alarm_code = alarm_code
        self._frigate   = frigate_client   # FrigateClient opzionale
        self._tg_bot    = tg_bot           # TelegramBot per send_photo
        self._cache_cb  = cache_cb         # () → state_cache per multi-source WiFi check
        self._lock            = asyncio.Lock()
        self._pending:       dict = {}   # motion tasks
        self._pending_welcome: dict = {}        # person_name → asyncio.Task disarmo
        self._pending_welcome_notify: dict = {} # person_name → asyncio.Task notifica benvenuto
        self._pending_arm:   dict = {}   # person_eid → asyncio.Task armamento ritardato (zona gialla)
        self._last_arm_ts     = 0.0
        self._last_notify_ts  = 0.0   # cooldown notifica "casa vuota" in modalità disabled
        self._home_motion_ts: dict = {}  # eid → timestamp ultima notifica "in casa"
        self._last_disarm_ts  = 0.0
        self._last_arm_notify_ts = 0.0   # cooldown notifica contatti aperti all'armamento
        self._last_welcome_ts: dict = {}   # person_name → timestamp ultimo benvenuto
        self.routine_manager = None        # impostato da main.py dopo init
        self._left_ts: dict = {}    # person_name → timestamp ultima uscita
        self._was_away: dict = {}   # person_name → True se proximity ha visto > soglia (uscita fisica confermata)
        self._last_arrival_trigger: dict = {}  # person_name → timestamp ultimo _someone_arrived
        self._last_gps_home_ts: dict = {}      # person_name → timestamp ultimo GPS=home (rientro)
        # Cross-referencing: sensori scattati di recente (eid → timestamp)
        self._recent_motion:  dict = {}    # eid → timestamp primo scatto
        self._frigate_sent:   dict = {}    # cam_name → timestamp ultimo snapshot inviato
        # Soglia override da config (0 = auto)
        self._threshold_override: int = 0
        # Flag: True se l'ultimo armamento è stato fatto da HomeMind (non manuale)
        # Usato per distinguere armamento automatico da armamento manuale dell'utente
        self._armed_by_homemind: bool = False
        self._arm_notify_in_progress: bool = False  # blocca _all_left mentre aspetta confirm

    def _get_threshold(self) -> int:
        """Soglia cross-ref. Se override > 0 usa quello, altrimenti 1 (ogni sensore triggera)."""
        if self._threshold_override > 0:
            return self._threshold_override
        return 1  # default: ogni sensore triggera indipendentemente

    def set_threshold_override(self, value: int):
        """Permette a home_model/config di impostare soglia manuale."""
        self._threshold_override = max(0, int(value))
        if value > 0:
            logger.info("Security: soglia cross-ref impostata manualmente a %d", value)

    # ── Chiamato da main dopo startup ──────────────────────────────────────────

    async def startup_check(self):
        """
        Controlla lo stato iniziale dopo il riavvio.
        Attende STARTUP_DELAY sec per dare tempo al WS di connettersi e
        aggiornare gli stati, poi agisce se necessario.
        """
        logger.info("Startup check tra %ds...", STARTUP_DELAY)
        await asyncio.sleep(STARTUP_DELAY)

        alarm_eid, alarm_st = self.home.primary_alarm()
        logger.info("Startup check: everyone_away=%s alarm=%s/%s",
                    self.home.everyone_away(), alarm_eid, alarm_st)

        # Usa GPS puro per decidere se armare: proximity stale non deve bloccare
        _gps_away = self.home.everyone_away_gps()
        _prox_away = self.home.everyone_away()
        logger.info("Startup: GPS_away=%s proximity_away=%s alarm=%s", _gps_away, _prox_away, alarm_st)

        if _gps_away:
            if alarm_st == "disarmed":
                if not _prox_away:
                    logger.info("Startup: GPS dice tutti fuori (proximity stale) → armo basandosi su GPS")
                else:
                    logger.info("Startup: casa vuota + allarme disarmato → armo")
                await self._all_left("(riavvio sistema)")
            elif alarm_st in ("armed_away","armed_home","triggered","arming","pending"):
                logger.info("Startup: casa vuota, allarme già %s — nessuna azione", alarm_st)
            else:
                logger.info("Startup: casa vuota + allarme stato sconosciuto (%s) → armo", alarm_st)
                await self._all_left("(riavvio sistema)")
        else:
            in_casa = self.home.who_is_home()
            logger.info("Startup: casa occupata da %s — nessuna azione", in_casa)
            # Se qualcuno è in casa e allarme è armed_away → disarma
            # GUARD: verifica che almeno una persona sia davvero a casa per GPS
            # (proximity potrebbe essere stale → falso positivo)
            if alarm_st in ("armed_away",):
                # Controlla GPS direttamente (non proximity che potrebbe essere stale)
                gps_home = [eid for eid, v in self.home.persons.items()
                            if self.home._is_home_state(v.get("state", ""))]
                if gps_home:
                    logger.info("Startup: GPS conferma %d persone in casa → disarmo", len(gps_home))
                    await self._someone_arrived(", ".join(in_casa))
                else:
                    logger.warning(
                        "Startup: who_is_home=%s ma GPS dice tutti fuori "
                        "(proximity stale?) — NO disarmo emergenza",
                        in_casa
                    )

    # ── Entry point eventi ─────────────────────────────────────────────────────

    async def on_state_changed(self, eid: str, old_st: str, new_st: str):
        domain = eid.split(".")[0]
        self.home.update_state(eid, new_st)

        # ── Aggiorna sensore distanza prossimità ──────────────────────────
        for person_eid, prox in self.home.proximity_sensors.items():
            if prox["sensor"] == eid:
                try:
                    dist_m = float(new_st)
                    prox["current_m"] = dist_m
                    prox["last_seen"] = time.time()
                    is_near = dist_m <= prox["threshold_m"]
                    if is_near:
                        prox["last_near_ts"] = time.time()  # sticky timestamp
                    name = self.home.persons.get(person_eid, {}).get("name", person_eid)
                    gps_st = self.home.persons.get(person_eid, {}).get("state", "?")
                    logger.info("PROXIMITY: %s → %.0fm (soglia %dm) | near=%s | GPS=%s",
                                name, dist_m, prox["threshold_m"], is_near, gps_st)
                    # Aggiorna _was_away: se proximity > soglia → eri fisicamente fuori
                    if not is_near:
                        self._was_away[name] = True
                        logger.debug("📍 %s: _was_away=True (proximity %.0fm > %.0fm)",
                                     name, dist_m, prox["threshold_m"])
                    # Se GPS dice fuori ma sensore dice vicino → tratta come rientro
                    if is_near and not self.home._is_home_state(gps_st):
                        logger.info("📍 Proximity override: %s trattato come IN CASA (%.0fm)", name, dist_m)
                        await self._handle_presence(person_eid, gps_st, "home")
                    # Se GPS dice home E proximity diventa near → benvenuto se non già gestito
                    # Caso: GPS arrivava home mentre proximity era ancora alta, ora si aggiorna
                    elif is_near and self.home._is_home_state(gps_st):
                        _, _alarm_st = self.home.primary_alarm()
                        if not self.home._person_is_home(person_eid):
                            logger.info("📍 Proximity %s: ora vicino (%.0fm) + GPS home → benvenuto", name, dist_m)
                            await self._someone_arrived(name)
                        elif _alarm_st == "armed_away":
                            # Persona già segnata "home" ma allarme ancora armato → disarma
                            logger.warning("📍 Proximity %s: in casa ma allarme ancora armed_away → disarmo forzato", name)
                            await self._someone_arrived(name)
                    # Se GPS dice fuori E sensore dice lontano → logica zone progressive
                    elif not is_near and not self.home._is_home_state(gps_st):
                        if self.home.everyone_away():
                            _, alarm_st = self.home.primary_alarm()
                            if alarm_st in ("armed_away", "armed_home", "arming"):
                                logger.debug(
                                    "📍 Proximity (%.0fm): allarme già %s — nessuna azione",
                                    dist_m, alarm_st
                                )
                            else:
                                zone_yellow_m    = prox.get("zone_yellow_m", None)
                                zone_yellow_wait = int(prox.get("zone_yellow_wait", 5))
                                if zone_yellow_m and dist_m <= zone_yellow_m:
                                    # ZONA GIALLA: schedule arm ritardato se non già attivo
                                    old_arm = self._pending_arm.get(person_eid)
                                    if old_arm and not old_arm.done():
                                        logger.debug("📍 ZONA GIALLA: task già attivo per %s", name)
                                    else:
                                        logger.info(
                                            "📍 ZONA GIALLA: %s a %.0fm (gialla=%dm) — aspetto %dmin",
                                            name, dist_m, zone_yellow_m, zone_yellow_wait
                                        )
                                        task = asyncio.create_task(
                                            self._delayed_arm(
                                                person_eid,
                                                f"proximity ({dist_m:.0f}m)",
                                                zone_yellow_wait
                                            ),
                                            name=f"delayed_arm_{name}"
                                        )
                                        self._pending_arm[person_eid] = task
                                else:
                                    # ZONA ROSSA o nessuna zona: multi-source check
                                    ok, details = self._check_multi_source(person_eid)
                                    if ok:
                                        logger.info(
                                            "📍 Proximity %.0fm + multi-source OK (%s) → armo",
                                            dist_m, details
                                        )
                                        await self._all_left(f"proximity ({dist_m:.0f}m)")
                                    else:
                                        logger.info(
                                            "📍 Proximity %.0fm: multi-source non sufficiente (%s)",
                                            dist_m, details
                                        )
                    # Rientro zona verde → cancella task zona gialla
                    if is_near:
                        old_arm = self._pending_arm.get(person_eid)
                        if old_arm and not old_arm.done():
                            old_arm.cancel()
                            self._pending_arm.pop(person_eid, None)
                            logger.info("📍 %s zona verde (%.0fm) — armamento ritardato annullato", name, dist_m)
                        # Proximity appena near + GPS home → triggera benvenuto
                        # Caso: GPS home da minuti ma proximity > 100m → benvenuto annullato
                        # Ora proximity = 0m → è davvero a casa → invia benvenuto
                        _gps_home_prox = self.home._is_home_state(
                            self.home.persons.get(person_eid, {}).get("state", "")
                        )
                        if _gps_home_prox:
                            logger.info("📍 %s proximity NEAR + GPS home → triggero benvenuto", name)
                            asyncio.create_task(
                                self._someone_arrived(name),
                                name=f"arrived_prox_{name}"
                            )
                except (ValueError, TypeError):
                    # Valore non numerico (es. "unavailable") — NON azzerare current_m
                    # se stale_check=false: mantieni l'ultimo valore buono
                    name = self.home.persons.get(person_eid, {}).get("name", person_eid)
                    if prox.get("stale_check", True):
                        prox["current_m"] = None
                        logger.debug("PROXIMITY: %s valore non numerico (%r) — current_m azzerato", name, new_st)
                    else:
                        logger.debug("PROXIMITY: %s valore non numerico (%r) — stale_check=false, mantengo last current_m=%s",
                                     name, new_st, prox.get("current_m"))

        if domain == "person":
            if new_st != old_st:
                logger.info("PERSON: %s  %s → %s  | everyone_away=%s",
                            eid, old_st, new_st, self.home.everyone_away())
                await self._handle_presence(eid, old_st, new_st)

        elif domain == "alarm_control_panel":
            logger.info("ALARM: %s  %s → %s", eid, old_st, new_st)

            # ── Allarme entra in pending → disarma subito se c'è un rientro in corso
            # Bug: HomeMind aspetta 20s anti-bounce, ma la centrale ha 10s delay ingresso
            # Se c'è già un task di disarmo schedulato (utente sta rientrando)
            # → disarma immediatamente senza aspettare il resto dei 20s
            if new_st == "pending" and self._pending_welcome:
                _who_disarm = list(self._pending_welcome.keys())
                logger.info(
                    "⚡ Allarme pending + rientro in corso (%s) → disarmo immediato",
                    _who_disarm
                )
                # Cancella i task di disarmo programmati
                for _t in list(self._pending_welcome.values()):
                    if not _t.done():
                        _t.cancel()
                self._pending_welcome.clear()
                # Disarma immediatamente
                asyncio.create_task(
                    self._immediate_disarm(_who_disarm[0] if _who_disarm else "rientro"),
                    name="immediate_disarm_pending"
                )

            # Se l'utente disarma manualmente da HA → cancella TUTTI i trigger pendenti
            if new_st == "disarmed" and old_st != "disarmed":
                pending = list(self._pending.keys())
                if pending:
                    logger.info("Allarme disarmato manualmente — cancello %d trigger pendenti: %s",
                                len(pending), pending)
                    for t in list(self._pending.values()):
                        t.cancel()
                    self._pending.clear()
                else:
                    logger.info("Allarme disarmato manualmente — nessun trigger pendente")
                # Reset flag: il prossimo armamento potrebbe essere manuale
                self._armed_by_homemind = False

            # Appena armato → controlla se è stato fatto manualmente o da HomeMind
            elif new_st in ("armed_away", "armed_home", "armed_night", "armed_vacation") \
                    and old_st not in ("armed_away", "armed_home", "armed_night", "armed_vacation"):

                # triggered/pending → armed_away = Paradox/EvoHD che reinserisce codice
                # durante allarme attivo. NON è armamento manuale — il task di disarmo
                # già schedulato gestirà correttamente il disarmo.
                _from_triggered = old_st in ("triggered", "pending")

                if _from_triggered:
                    logger.info(
                        "🔔 Allarme %s → %s da triggered/pending — "
                        "ignorato come armamento manuale (utente ha inserito codice per silenziare)",
                        old_st, new_st
                    )
                    # NON aggiornare config né notificare

                elif not self._armed_by_homemind:
                    # ── Armamento MANUALE dall'utente via HA ──────────────────
                    logger.info(
                        "🔒 Armamento MANUALE rilevato: %s → %s — aggiorno config",
                        old_st, new_st
                    )
                    self.home._alarm_arm_mode = new_st
                    asyncio.create_task(
                        self._sync_alarm_mode_to_config(new_st),
                        name="sync_alarm_mode"
                    )
                else:
                    logger.info("🔒 Armamento da HomeMind (automatico) — nessun aggiornamento config")
                    self._armed_by_homemind = False

                # Controlla contatti aperti solo per armamento reale (non da triggered)
                if not _from_triggered:
                    asyncio.create_task(self._check_open_contacts_on_arm(), name="check_contacts")


        elif domain == "binary_sensor" and eid in self.home.motion_sensors:
            logger.info("MOTION: %s  %s → %s  | everyone_away=%s",
                        eid, old_st, new_st, self.home.everyone_away())
            if new_st == "on":
                await self._schedule_motion(eid)
                # Registra evento cucina per routine learning
                if hasattr(self, "routine_manager") and self.routine_manager:
                    zone = self.home.motion_sensors.get(eid, {}).get("zone", "")
                    if "cucina" in zone.lower():
                        from utils.timezone_helper import now_local as _nl
                        if 5 <= _nl().hour <= 11:
                            self.routine_manager.record_event("kitchen_morning")
            elif new_st == "off":
                self._cancel_motion(eid)

        elif domain == "binary_sensor" and eid in self.home.contact_sensors:
            self.home.contact_sensors[eid]["state"] = new_st
            logger.info("CONTACT: %s  %s → %s  | everyone_away=%s",
                        eid, old_st, new_st, self.home.everyone_away())
            if new_st == "on":  # on = aperto
                await self._handle_contact_open(eid)

    # ── Presenza ──────────────────────────────────────────────────────────────

    async def _handle_presence(self, eid: str, old_st: str, new_st: str):
        async with self._lock:
            name = self.home.persons.get(eid, {}).get("name", eid)

            # Persona uscita
            # is_home_new: usa _person_is_home (GPS + proximity) per lo stato ATTUALE
            # is_home_old: usa _is_home_state sul vecchio stato GPS (non abbiamo il proximity storico)
            is_home_new = self.home._person_is_home(eid)
            is_home_old = self.home._is_home_state(old_st)
            # GPS puro — senza override proximity (per rilevare partenze con proximity stale)
            gps_is_home_new = self.home._is_home_state(new_st)

            logger.info("👤 %s: %s→%s | home_new=%s home_old=%s gps_new=%s",
                        name, old_st, new_st, is_home_new, is_home_old, gps_is_home_new)

            # Registra quando GPS dice "home" → usato per rilevare bounce al rientro
            if gps_is_home_new:
                self._last_gps_home_ts[name] = time.time()


            # Registra partenza basata su GPS anche se proximity override dice "in casa"
            # Questo risolve il caso proximity stale: GPS dice not_home ma proximity 0m
            if is_home_old and not gps_is_home_new:
                self._left_ts[name] = time.time()
                logger.info("👤 %s: partenza GPS registrata (proximity potrebbe essere stale)", name)

            # USCITA: usa GPS puro — la proximity non deve mascherare l'uscita
            # (proximity può restare a 0m per minuti dopo l'uscita fisica)
            # RIENTRO: usa _person_is_home (GPS + proximity) per anticipare il disarmo
            is_leaving  = is_home_old and not gps_is_home_new   # GPS dice fuori
            is_arriving = (is_home_new or gps_is_home_new) and not is_home_old   # GPS O proximity dicono in casa

            if is_leaving:
                # Persona uscita — cancella task disarmo e notifica benvenuto
                welcome_task = self._pending_welcome.get(name)
                if welcome_task and not welcome_task.done():
                    welcome_task.cancel()
                    logger.info("👤 %s uscito durante attesa benvenuto — task CANCELLATO", name)
                notify_task = self._pending_welcome_notify.get(name)
                if notify_task and not notify_task.done():
                    notify_task.cancel()
                    logger.info("👤 %s uscito — notifica benvenuto ANNULLATA", name)
                # Uscita rilevata da GPS puro (proximity potrebbe ancora dire vicino)
                logger.info("👤 %s uscito/a (GPS: %s | proximity potrebbe essere fresh)", name, new_st)
                # Registra per routine learning
                if hasattr(self, "routine_manager") and self.routine_manager:
                    self.routine_manager.record_event("departure", name)
                # Se nessuna proximity configurata → GPS not_home = uscita confermata
                # (per utenti come Rosa che usano solo GPS)
                if eid not in self.home.proximity_sensors:
                    self._was_away[name] = True
                    logger.debug("👤 %s: _was_away=True (GPS, nessuna proximity)", name)
                # Non aggiornare left_ts se GPS è andato a "home" di recente (< 5 min):
                # Questo gestisce il bounce GPS al rientro — sequenza tipica:
                #   1. GPS va a home (rientro reale)
                #   2. GPS torna not_home pochi secondi dopo (bounce)
                # Senza questo fix, left_ts = "10s fa" → away_minutes=0 → no benvenuto
                _last_home_ts = self._last_gps_home_ts.get(name, 0)
                _since_gps_home = time.time() - _last_home_ts
                if _since_gps_home < 300:  # GPS è andato home negli ultimi 5 min → bounce
                    logger.info(
                        "👤 %s: left_ts NON aggiornato — bounce GPS al rientro "
                        "(GPS era home %.0fs fa, preservo ts partenza reale)",
                        name, _since_gps_home
                    )
                else:
                    self._left_ts[name] = time.time()
                # Sleep adattivo: più lungo se proximity è stale (GPS potrebbe rimbalzare)
                # Con proximity stale aspettiamo 30s prima di considerare la casa vuota,
                # dando al GPS più tempo per stabilizzarsi su not_home.
                _prox_d = self.home.proximity_sensors.get(eid, {})
                _ls_d   = _prox_d.get("last_seen")
                _ma_d   = int(_prox_d.get("max_age_min", 30)) * 60
                _cm_d   = _prox_d.get("current_m")
                _thr_d  = _prox_d.get("threshold_m", 100)
                _stale_d    = (_ls_d is None or (time.time() - _ls_d) > _ma_d) if _prox_d else False
                _prox_near  = (_cm_d is not None and float(_cm_d) <= _thr_d
                               and _ls_d is not None and (time.time() - _ls_d) < _ma_d)
                # Sleep adattivo:
                # - proximity dice "in casa" (near, dati freschi) → 30s
                #   (GPS potrebbe rimbalzare: dai tempo al GPS di stabilizzarsi)
                # - proximity stale → 30s
                # - nessun proximity vicino → 8s
                _sleep_sec = 30 if (_stale_d or _prox_near) else 8
                _sleep_reason = (
                    "(proximity near — GPS potrebbe oscillare)" if _prox_near
                    else "(proximity stale)" if _stale_d
                    else ""
                )
                logger.info("👤 %s uscito — attendo %ds prima di verificare casa vuota %s",
                            name, _sleep_sec, _sleep_reason)
                await asyncio.sleep(_sleep_sec)
                # Verifica casa vuota usando GPS puro (non proximity)
                # La proximity potrebbe essere ancora fresh a 0m dopo l'uscita
                _all_away_gps = all(
                    not self.home._is_home_state(v.get("state", ""))
                    for v in self.home.persons.values()
                )
                if _all_away_gps:
                    logger.info("🏠 Casa vuota (GPS) dopo uscita di %s", name)
                    await self._all_left(name)
                else:
                    # Qualcuno ha GPS a "home" → casa ancora occupata
                    _who_gps = [v["name"] for v in self.home.persons.values()
                                if self.home._is_home_state(v.get("state", ""))]
                    logger.info("Casa ancora occupata (GPS): %s", _who_gps)

            elif is_arriving:
                # Persona rientrata
                logger.info("👤 %s rientrato/a", name)
                # Registra per routine learning
                if hasattr(self, "routine_manager") and self.routine_manager:
                    self.routine_manager.record_event("arrival", name)
                await self._someone_arrived(name)

            else:
                # Cambio zona senza entrare/uscire di casa (es. Lavoro→Ufficio)
                logger.debug("👤 %s cambio zona: %s→%s (nessuna azione)", name, old_st, new_st)

    # ── Azioni sicurezza ──────────────────────────────────────────────────────

    def _check_multi_source(self, person_eid: str) -> tuple[bool, str]:
        """
        Verifica che abbastanza fonti concordino sul fatto che la persona è fuori.
        Ritorna (ok: bool, motivo: str).
        Gestisce il fallback se una fonte non è disponibile.
        """
        prox = self.home.proximity_sensors.get(person_eid, {})
        require   = int(prox.get("require", 1))
        wifi_eid  = prox.get("wifi_tracker", "")
        cache     = self._cache_cb() if self._cache_cb else {}

        # Fonte 1: GPS (sempre disponibile)
        gps_st   = self.home.persons.get(person_eid, {}).get("state", "")
        gps_away = not self.home._is_home_state(gps_st)

        # Fonte 2: WiFi tracker (opzionale)
        # Supporta device_tracker (home/not_home) E binary_sensor (on=connesso/off=disconnesso)
        #
        # ⚠️ PARADOSSO WiFi: quando il telefono perde il WiFi di casa, non riesce più
        # ad aggiornare HA via WiFi → il binary_sensor rimane "on" anche se fuori.
        # Fix: se binary_sensor="on" MA non aggiornato da dopo la partenza GPS → STALE → escluso.
        wifi_away = None   # None = non configurata / non disponibile
        if wifi_eid:
            wifi_entry = cache.get(wifi_eid, {})
            wifi_state = wifi_entry.get("state", "")
            if wifi_state in ("", "unavailable", "unknown"):
                wifi_away = None  # non disponibile
                logger.info("MULTI-SOURCE: WiFi %s non disponibile (%r) — escluso", wifi_eid, wifi_state)
            elif wifi_eid.startswith("binary_sensor."):
                # binary_sensor WiFi: on=connesso=in casa, off=disconnesso=fuori
                wifi_away = (wifi_state == "off")
                # Paradosso WiFi: se dice "on" ma non si aggiorna da prima della partenza GPS
                # → il telefono ha perso WiFi prima di poter aggiornare HA → stale → escluso
                if not wifi_away:  # WiFi dice connesso — verifica freschezza
                    person_name = self.home.persons.get(person_eid, {}).get("name", "")
                    left_ts  = self._left_ts.get(person_name, 0)
                    wlc_str  = wifi_entry.get("last_changed", "")
                    if left_ts > 0 and wlc_str:
                        try:
                            wlc_ts = datetime.fromisoformat(
                                wlc_str.replace("Z", "+00:00")
                            ).timestamp()
                            if wlc_ts < left_ts:
                                # Sensor non aggiornato dopo la partenza → stale
                                logger.info(
                                    "MULTI-SOURCE: WiFi binary_sensor %s on=stale "
                                    "(no update da %.0fs, partenza %.0fs fa) → escluso",
                                    wifi_eid,
                                    time.time() - wlc_ts,
                                    time.time() - left_ts
                                )
                                wifi_away = None  # stale → non contarlo
                        except Exception:
                            pass  # impossibile parsare timestamp → mantieni wifi_away=False
                logger.debug("MULTI-SOURCE: binary_sensor WiFi %s=%s → away=%s", wifi_eid, wifi_state, wifi_away)
            else:
                # device_tracker: "home" = in casa, "not_home" = fuori
                wifi_away = (wifi_state not in ("home",))
                logger.debug("MULTI-SOURCE: device_tracker %s=%s → away=%s", wifi_eid, wifi_state, wifi_away)

        # Fonte 3: Proximity
        # Usa _person_is_home() come fonte di verità unica — stessa logica ovunque.
        # Per stale_check=false: current_m è sempre valido se non None.
        # Per stale_check=true: _person_is_home gestisce la scadenza per età.
        prox_away = None
        current_m = prox.get("current_m")
        if current_m is not None:
            threshold = float(prox.get("threshold_m", 100))
            if float(current_m) > threshold:
                # Sensore dice lontano → AWAY sicuro (qualunque stale_check)
                prox_away = True
                logger.info("MULTI-SOURCE: proximity FAR (%.0fm > %.0fm) → away",
                            current_m, threshold)
            else:
                # Sensore dice vicino — usa _person_is_home() come fonte di verità
                _is_home_prox = self.home._person_is_home(person_eid)
                if _is_home_prox:
                    prox_away = False
                    last_seen = prox.get("last_seen")
                    age_str = f"{(time.time()-last_seen)/60:.0f}min" if last_seen else "?"
                    logger.info("MULTI-SOURCE: proximity NEAR (%.0fm, %s) → home",
                                current_m, age_str)
                else:
                    logger.info("MULTI-SOURCE: proximity NEAR ma _person_is_home=False → neutrale")
        else:
            logger.debug("MULTI-SOURCE: proximity non disponibile (current_m=None) → esclusa")

        # Calcola fonti disponibili e quante dicono "fuori"
        sources = [("GPS", gps_away)]
        if wifi_away is not None:
            sources.append(("WiFi", wifi_away))
        if prox_away is not None:
            sources.append(("Proximity", prox_away))

        n_available = len(sources)
        n_away      = sum(1 for _, v in sources if v)

        # Fallback: se require > fonti disponibili, riduci require
        effective_require = min(require, n_available)
        if effective_require < require:
            logger.info(
                "MULTI-SOURCE: require=%d ma solo %d fonti disponibili → uso require=%d",
                require, n_available, effective_require
            )

        ok = n_away >= effective_require
        details = " | ".join(
            f"{name}={'fuori' if v else 'casa'}"
            for name, v in sources
        )
        logger.info(
            "MULTI-SOURCE %s: %s | need %d/%d → %s",
            self.home.persons.get(person_eid, {}).get("name", person_eid),
            details, effective_require, n_available,
            "✅ OK arma" if ok else "❌ non sufficiente"
        )
        return ok, details

    async def _delayed_arm(self, person_eid: str, trigger: str, wait_min: int):
        """
        Armamento ritardato per zona gialla.
        Aspetta wait_min minuti, poi:
        - se la persona è ancora fuori E multi-source ok → arma
        - se è rientrata in zona verde → annulla
        """
        name = self.home.persons.get(person_eid, {}).get("name", person_eid)
        logger.info("⏳ ZONA GIALLA: %s — attendo %d min prima di armare", name, wait_min)
        try:
            await asyncio.sleep(wait_min * 60)
        except asyncio.CancelledError:
            logger.info("⏳ ZONA GIALLA: task annullato per %s (rientrato in zona verde)", name)
            return

        # Ricontrolla: è ancora fuori?
        if not self.home.everyone_away():
            logger.info("⏳ ZONA GIALLA: %s — qualcuno è rientrato, annullo armamento", name)
            return

        # Ricontrolla la distanza attuale
        prox = self.home.proximity_sensors.get(person_eid, {})
        current_m = prox.get("current_m")
        threshold_m = prox.get("threshold_m", 100)
        if current_m is not None and float(current_m) <= threshold_m:
            logger.info("⏳ ZONA GIALLA: %s rientrato in zona verde (%.0fm) — annullo", name, current_m)
            return

        # Multi-source check
        ok, details = self._check_multi_source(person_eid)
        if not ok:
            logger.info(
                "⏳ ZONA GIALLA: multi-source insufficiente per %s (%s) — annullo armamento",
                name, details
            )
            return

        logger.info("⏳ ZONA GIALLA: %s — %.0f min trascorsi, multi-source ok → armo", name, wait_min)
        await self._all_left(f"zona gialla ({wait_min}min) — {trigger}")

    async def _all_left(self, trigger: str):
        if self._arm_notify_in_progress:
            logger.info("Arm SKIP: richiesta confirm già in corso — attendi risposta utente")
            return
        if time.time() - self._last_arm_ts < ARM_COOLDOWN:
            logger.info("Arm SKIP: cooldown attivo")
            return

        # ── Safety net: motion sensor recente = qualcuno è fisicamente in casa ──
        # Indipendente da GPS/WiFi/proximity. Se un sensore di movimento ha
        # scattato negli ultimi 10 minuti → NON armare.
        MOTION_ARM_BLOCK_SEC = 600  # 10 minuti
        for _meid, _mts in self._recent_motion.items():
            if (time.time() - _mts) < MOTION_ARM_BLOCK_SEC:
                logger.warning(
                    "ARM BLOCCATO: motion sensor %s ha scattato %.0fs fa "
                    "(< %ds) — qualcuno è fisicamente in casa",
                    _meid, time.time() - _mts, MOTION_ARM_BLOCK_SEC
                )
                return
        # Controlla anche home_motion_ts (notifiche movimento)
        for _meid, _mts in self._home_motion_ts.items():
            if (time.time() - _mts) < MOTION_ARM_BLOCK_SEC:
                logger.warning(
                    "ARM BLOCCATO: motion %s recente (%.0fs fa) — qualcuno in casa",
                    _meid, time.time() - _mts
                )
                return

        # Multi-source check: se require > 1, verifica che abbastanza fonti confermino
        # Esegui il check per ogni persona che risulta fuori
        for _peid in list(self.home.persons):
            _prox = self.home.proximity_sensors.get(_peid, {})
            if int(_prox.get("require", 1)) > 1:
                _ok, _det = self._check_multi_source(_peid)
                if not _ok:
                    logger.info(
                        "ARM SKIP: multi-source insufficiente per %s (%s)",
                        self.home.persons[_peid].get("name", _peid), _det
                    )
                    return

        # Se l'allarme è già in armed_home o armed_night → NON fare nulla.
        # Queste modalità implicano persone in casa: HomeMind non deve
        # spegnere entità né passare ad armed_away automaticamente.
        # L'utente gestisce queste modalità manualmente da HA.
        alarm_eid_pre, alarm_st_pre = self.home.primary_alarm()
        if alarm_st_pre in ("armed_home", "armed_night", "armed_vacation"):
            logger.info(
                "_all_left SKIP: allarme già in modalità '%s' (persone in casa) — "
                "HomeMind non modifica questo stato",
                alarm_st_pre
            )
            return

        # ── Verifica finale proximity via REST (ultima difesa GPS ballerino) ──
        # SALTATA se require > 1: il multi-source ha già valutato la proximity.
        # Attiva solo con require=1 (GPS puro) come anti-bounce.
        for person_eid, prox in self.home.proximity_sensors.items():
            _req_p = int(prox.get("require", 1))
            if _req_p > 1:
                logger.debug("ARM: REST check skippato per %s (require=%d, multi-source già OK)",
                             self.home.persons.get(person_eid, {}).get("name", person_eid), _req_p)
                continue
            sensor_eid = prox["sensor"]
            try:
                state = await self.rest.get_state(sensor_eid)
                dist_m = float(state.get("state", "99999"))
                threshold = prox["threshold_m"]
                name = self.home.persons.get(person_eid, {}).get("name", person_eid)
                if dist_m <= threshold:
                    logger.warning(
                        "ARM BLOCCATO: %s a soli %.0fm (soglia %dm) — "
                        "proximity REST dice IN CASA, GPS ballerino ignorato",
                        name, dist_m, threshold
                    )
                    return
                else:
                    logger.info("ARM: REST proximity %s = %.0fm → ok fuori", name, dist_m)
            except Exception as e:
                logger.warning("ARM: REST proximity fallita (%s) — procedo", e)

        self._last_arm_ts = time.time()

        done = []

        # ── Controlla se disabled + alarm_disable_entities=false → solo notifica ──
        _arm_mode_cfg_pre = getattr(self.home, "_alarm_auto_arm", "auto")
        _disable_entities = getattr(self.home, "_alarm_disable_entities", True)

        if _arm_mode_cfg_pre == "disabled" and not _disable_entities:
            # Modalità: disabled + alarm_disable_entities=False (switch OFF)
            # → Controlla se la notifica è abilitata (secondo switch)
            _disable_notify = getattr(self.home, "_alarm_disable_notify", True)
            if not _disable_notify:
                # Secondo switch OFF → silenzio totale, nessuna notifica
                logger.info("ARM SKIP (silent): alarm_auto_arm=disabled + alarm_disable_entities=false + alarm_disable_notify=false")
                return
            # Notifica abilitata → manda "casa vuota" UNA SOLA VOLTA per uscita (cooldown 1h)
            NOTIFY_COOLDOWN = 3600  # 1 ora — evita spam su ogni proximity update
            if time.time() - self._last_notify_ts < NOTIFY_COOLDOWN:
                logger.info("ARM SKIP (notify-only): cooldown notifica attivo (%.0f min rimanenti)",
                            (NOTIFY_COOLDOWN - (time.time() - self._last_notify_ts)) / 60)
                return
            logger.info("ARM SKIP (notify-only): alarm_auto_arm=disabled + alarm_disable_entities=false")
            self._last_notify_ts = time.time()
            if self.notifier:
                try:
                    ora = now_local().strftime("%H:%M")
                    who_away = self.home.who_is_away()
                    fuori = ", ".join(who_away) if who_away else "tutti"
                    await self.notifier.send_html(
                        f"🏠 <b>Casa vuota</b> — {ora}\n"
                        f"🚶 Fuori: {fuori}\n"
                        f"ℹ️ <i>Gestione allarme disabilitata — nessuna azione eseguita</i>"
                    )
                except Exception as e:
                    logger.warning("Notifica FAIL: %s", e)
            return

        # 1 & 2. Spegni entità configurate
        _alarm_on_leave = getattr(self.home, "_alarm_on_leave", [])

        if _alarm_on_leave:
            # ── Modalità selettiva: spegni solo le entità scelte dall'utente ──
            logger.info("alarm_on_leave: spegnimento %d entità selezionate", len(_alarm_on_leave))
            for eid in _alarm_on_leave:
                domain = eid.split(".")[0]
                try:
                    if domain == "light":
                        await self.rest.call_service("light", "turn_off", {},
                                                     target={"entity_id": eid})
                        done.append("💡 " + eid.split(".")[-1] + " spenta")
                    elif domain == "switch":
                        await self.rest.call_service("switch", "turn_off", {},
                                                     target={"entity_id": eid})
                        done.append("🔌 " + eid.split(".")[-1] + " spento")
                    elif domain == "climate":
                        await self.rest.call_service("climate", "turn_off", {},
                                                     target={"entity_id": eid})
                        done.append("🌡️ " + eid.split(".")[-1] + " spento")
                    elif domain == "cover":
                        await self.rest.call_service("cover", "close_cover", {},
                                                     target={"entity_id": eid})
                        done.append("🪟 " + eid.split(".")[-1] + " chiusa")
                    elif domain == "media_player":
                        await self.rest.call_service("media_player", "turn_off", {},
                                                     target={"entity_id": eid})
                        done.append("📺 " + eid.split(".")[-1] + " spento")
                    elif domain == "input_boolean":
                        await self.rest.call_service("input_boolean", "turn_off", {},
                                                     target={"entity_id": eid})
                        done.append("🔘 " + eid.split(".")[-1] + " disattivato")
                    else:
                        # Fallback generico: prova turn_off
                        await self.rest.call_service(domain, "turn_off", {},
                                                     target={"entity_id": eid})
                        done.append("⚡ " + eid + " spento")
                    logger.info("alarm_on_leave: %s → spento/chiuso", eid)
                except Exception as e:
                    logger.warning("alarm_on_leave FAIL %s: %s", eid, e)
        else:
            # ── Modalità legacy: spegni tutte le luci + clima auto-off ──
            # Spegni luci
            lights = self.home.lights_on()
            if lights:
                try:
                    await self.rest.call_service("light", "turn_off", {},
                                                 target={"entity_id": lights})
                    done.append("Spente " + str(len(lights)) + " luci")
                    logger.info("Luci spente (legacy): %s", lights)
                except Exception as e:
                    logger.warning("Luci spegni FAIL: %s", e)

            # Spegni clima
            _climate_auto_off = getattr(self.home, "_climate_auto_off", True)
            if _climate_auto_off:
                _climate_exclude = set(getattr(self.home, "_climate_exclude", []))
                for ceid, v in self.home.climate.items():
                    if ceid in _climate_exclude:
                        logger.info("Clima %s escluso (climate_exclude)", ceid)
                        continue
                    if v["state"] not in ("off", "unavailable", "unknown"):
                        try:
                            await self.rest.call_service("climate", "turn_off", {},
                                                         target={"entity_id": ceid})
                            done.append("Clima spento")
                        except Exception as e:
                            logger.warning("Clima spegni FAIL: %s", e)
            else:
                logger.info("Clima auto-off disabilitato (climate_auto_off: false)")

        # 3. Arma allarme
        # Modalità da config: "auto" | "disabled" | "notify"
        _arm_mode_cfg = getattr(self.home, "_alarm_auto_arm", "auto")

        # ── Modalità DISABLED: non tocca mai l'allarme ──────────────────────
        if _arm_mode_cfg == "disabled":
            logger.info("ARM SKIP: alarm_auto_arm=disabled — HomeMind non gestisce l'allarme")
            if self.notifier:
                try:
                    ora = now_local().strftime("%H:%M")
                    who_away = self.home.who_is_away()
                    fuori = ", ".join(who_away) if who_away else "tutti"
                    done_html = "\n".join(f"✅ {d}" for d in done) if done else ""
                    msg = (
                        f"🏠 <b>Casa vuota</b> — {ora}\n"
                        f"🚶 Fuori: {fuori}\n"
                        f"⚠️ <i>Gestione allarme disabilitata</i>"
                        + (f"\n\n{done_html}" if done_html else "")
                    )
                    await self.notifier.send_html(msg)
                except Exception as e:
                    logger.warning("Notifica FAIL: %s", e)
            return

        # ── Modalità NOTIFY: chiede conferma via Telegram prima di armare ───
        if _arm_mode_cfg == "notify":
            # Anti-spam: evita messaggi multipli se GPS oscilla
            NOTIFY_CONFIRM_COOLDOWN = 120  # secondi tra due richieste di conferma
            if time.time() - self._last_arm_notify_ts < NOTIFY_CONFIRM_COOLDOWN:
                logger.info("ARM NOTIFY SKIP: cooldown anti-spam attivo (%.0fs rimanenti)",
                            NOTIFY_CONFIRM_COOLDOWN - (time.time() - self._last_arm_notify_ts))
                return
            self._last_arm_notify_ts = time.time()
            self._arm_notify_in_progress = True  # blocca altri _all_left
            logger.info("ARM NOTIFY: chiedo conferma via Telegram...")
            if self._tg_bot:
                try:
                    who_away = self.home.who_is_away()
                    away_str = ", ".join(who_away) if who_away else "tutti"
                    ora = now_local().strftime("%H:%M")
                    question = (
                        f"🏠 <b>Casa vuota</b> — {ora}\n"
                        f"Fuori: {away_str}\n\n"
                        f"Vuoi attivare l'antifurto?"
                    )
                    confirmed = await self._tg_bot.ask_alarm_confirm(question)
                except Exception as e_ask:
                    logger.warning("ARM NOTIFY: errore richiesta conferma: %s — armo automaticamente", e_ask)
                    confirmed = True  # fallback sicuro
            else:
                logger.warning("ARM NOTIFY: nessun bot Telegram disponibile — armo automaticamente")
                confirmed = True  # fallback sicuro

            self._arm_notify_in_progress = False  # rilascia blocco
            # Aggiorna cooldown dopo risposta (evita spam immediato al rilascio)
            self._last_arm_ts = time.time()
            if not confirmed:
                logger.info("ARM NOTIFY: utente ha rifiutato — antifurto NON attivato")
                if self.notifier:
                    try:
                        await self.notifier.send(
                            "🏠 HomeMind: Casa Vuota",
                            "Trigger: " + trigger + "\n" +
                            "Ora: " + now_local().strftime("%H:%M") + "\n" +
                            "🔕 Antifurto NON attivato (scelta utente)\n" +
                            "\n".join(done)
                        )
                    except Exception as e:
                        logger.warning("Notifica FAIL: %s", e)
                return
            logger.info("ARM NOTIFY: confermato — procedo con armamento")

        alarm_eid, alarm_st = self.home.primary_alarm()
        if not alarm_eid:
            logger.error("ARM FAIL: nessun alarm_control_panel trovato!")
            done.append("ERRORE: nessun allarme configurato")
        elif alarm_st in ("armed_away","armed_home","arming"):
            logger.info("Allarme gia in stato %s — skip", alarm_st)
            done.append("Allarme gia armato (" + alarm_st + ")")
        else:
            try:
                # Usa arm_mode dal config (armed_away, armed_home, ecc.)
                _arm_mode = getattr(self.home, "_alarm_arm_mode", "armed_away")
                _service   = f"alarm_arm_{_arm_mode.replace('armed_', '')}"
                logger.info("Armamento allarme %s modalità %s...", alarm_eid, _arm_mode)
                self._armed_by_homemind = True  # segnala che siamo noi ad armare
                await self.rest.call_service(
                    "alarm_control_panel", _service,
                    {"code": self.alarm_code},
                    target={"entity_id": alarm_eid}
                )
                done.append(f"Allarme ARMATO ({_arm_mode})")
                logger.info("✅ Allarme armato: %s modalità %s", alarm_eid, _arm_mode)
            except Exception as e:
                logger.error("ARM FAIL: %s", e)
                done.append("ERRORE armamento: " + str(e))

            # Arma anche le partizioni extra con delay configurabile
            _extra_panels = getattr(self.home, "_alarm_extra_panels", [])
            _arm_delay    = int(getattr(self.home, "_alarm_extra_delay", 1))
            for _extra_eid in _extra_panels:
                _extra_st = self.home.alarm_panels.get(_extra_eid, {}).get("state", "unknown")
                if _extra_st in ("armed_away", "armed_home", "arming"):
                    logger.info("Partizione extra %s gia armata — skip", _extra_eid)
                    continue
                await asyncio.sleep(_arm_delay)  # delay tra partizioni
                try:
                    await self.rest.call_service(
                        "alarm_control_panel", _service,
                        {"code": self.alarm_code},
                        target={"entity_id": _extra_eid}
                    )
                    logger.info("✅ Partizione extra armata (delay %ds): %s", _arm_delay, _extra_eid)
                except Exception as _ep:
                    logger.warning("Partizione extra ARM FAIL %s: %s", _extra_eid, _ep)

        # 4. Notifica con sirena
        if self.notifier:
            try:
                ora   = now_local().strftime("%H:%M")
                away  = self.home.who_is_away()
                fuori = ", ".join(away) if away else "tutti"
                done_html = "\n".join(
                    f"✅ {d}" for d in done
                ) if done else "ℹ️ Nessuna azione eseguita"
                _arm_cfg = getattr(self.home, "_alarm_auto_arm", "auto")
                if _arm_cfg == "disabled":
                    header = "🏠 <b>Casa vuota</b> — allarme non gestito"
                else:
                    header = "🚨 <b>ANTIFURTO IN ATTIVAZIONE!</b>"
                msg = (
                    f"{header}\n"
                    f"⏰ <b>{ora}</b> — Trigger: {trigger}\n"
                    f"🚶 Fuori: {fuori}\n\n"
                    f"{done_html}"
                )
                await self.notifier.send_html(msg)
            except Exception as e:
                logger.warning("Notifica FAIL: %s", e)

    async def _someone_arrived(self, name: str):
        WELCOME_COOLDOWN  = 3600   # max 1 benvenuto all'ora per persona
        DISARM_BOUNCE_SEC = 20     # attendi solo 20s anti-bounce GPS prima di disarmare
        ARRIVAL_DEDUP_SEC = 30     # ignora _someone_arrived ripetuto entro 30s (GPS+prox race)

        # Anti-duplicazione: GPS e proximity possono triggerare entrambi in pochi secondi
        _last_trig = self._last_arrival_trigger.get(name, 0)
        if time.time() - _last_trig < ARRIVAL_DEDUP_SEC:
            logger.info("👤 %s: _someone_arrived SKIP — trigger duplicato (%.0fs fa)",
                        name, time.time() - _last_trig)
            return
        self._last_arrival_trigger[name] = time.time()

        # Reset cooldown notifica "casa vuota" — al prossimo rientro+uscita notifica di nuovo
        self._last_notify_ts = 0.0

        # Cancella eventuale task benvenuto precedente per questa persona
        old_task = self._pending_welcome.get(name)
        if old_task and not old_task.done():
            old_task.cancel()
            logger.info("👤 %s: task benvenuto precedente cancellato (nuovo rientro)", name)

        # ── DISARMO RAPIDO (20s anti-bounce) ─────────────────────────────────
        # Non aspettiamo 5 minuti per disarmare — sarebbe insopportabile!
        # Aspettiamo solo 20s per escludere rimbalzi GPS, poi disarmiamo subito.
        task = asyncio.create_task(
            self._fast_disarm(name, DISARM_BOUNCE_SEC),
            name=f"disarm_{name}"
        )
        self._pending_welcome[name] = task

        # ── NOTIFICA BENVENUTO (60s separata) ─────────────────────────────────
        # Cancella eventuale notifica benvenuto precedente ancora pendente
        old_notify = self._pending_welcome_notify.get(name)
        if old_notify and not old_notify.done():
            old_notify.cancel()
            logger.info("👤 %s: notifica benvenuto precedente annullata (nuovo rientro)", name)
        last = self._last_welcome_ts.get(name, 0.0)
        elapsed_since_last = time.time() - last
        # Controlla quanto tempo è stato via prima di rientrare
        # Se era via da meno di 5 minuti → rimbalzo GPS, no benvenuto
        # away_minutes: da quando GPS ha registrato l'ultima uscita
        # (non serve più real_departure_ts — _was_away gestisce il controllo uscita)
        left_ts      = self._left_ts.get(name, 0.0)
        away_minutes = (time.time() - left_ts) / 60 if left_ts else 999
        # Se via da più di 30 minuti, ignora il cooldown orario — rientro reale
        cooldown_override = away_minutes >= 30
        # MIN_REPEAT_COOLDOWN: non mandare due benvenuti a distanza < 5 min
        # Questo blocco è assoluto — cooldown_override non lo bypassa.
        # Risolve il doppio benvenuto quando proximity e GPS si aggiornano
        # in rapida successione pochi secondi dopo il primo invio.
        MIN_REPEAT_COOLDOWN = 300   # 5 minuti — mai due benvenuti ravvicinati
        just_welcomed = elapsed_since_last < MIN_REPEAT_COOLDOWN
        # Benvenuto solo se _was_away=True (proximity ha confermato uscita fisica)
        # Persona in casa 24h → proximity sempre 0m → _was_away mai True → no spam
        _was_away_flag = self._was_away.get(name, False)
        can_welcome = (
            not just_welcomed
            and (elapsed_since_last >= WELCOME_COOLDOWN or cooldown_override)
            and away_minutes >= 5
            and _was_away_flag
        )
        if just_welcomed:
            logger.info("👤 %s: benvenuto SKIP — appena inviato (%.0fs fa < %ds)",
                        name, elapsed_since_last, MIN_REPEAT_COOLDOWN)
        elif can_welcome:
            notify_task = asyncio.create_task(
                self._delayed_welcome_notify(name, delay=60),
                name=f"welcome_notify_{name}"
            )
            self._pending_welcome_notify[name] = notify_task
            logger.info("👤 %s: benvenuto schedulato (via %.0f min, ultimo benvenuto %.0f min fa%s)",
                        name, away_minutes, elapsed_since_last/60,
                        " [cooldown override]" if cooldown_override else "")
        elif away_minutes < 5:
            logger.info("👤 %s: benvenuto SKIP — rimbalzo GPS (via solo %.0f min)", name, away_minutes)
        elif not _was_away_flag:
            logger.info("👤 %s: benvenuto SKIP — proximity mai vista > 100m (nessuna uscita fisica)", name)
        elif not just_welcomed:
            logger.info("👤 %s: benvenuto SKIP — cooldown attivo (%.0f min fa)", name, elapsed_since_last/60)
    async def _immediate_disarm(self, name: str):
        """Disarma immediatamente — usato quando allarme va in pending con rientro in corso."""
        # Rispetta alarm_auto_arm=disabled
        if getattr(self.home, "_alarm_auto_arm", "auto") == "disabled":
            logger.info("DISARM SKIP: alarm_auto_arm=disabled")
            return
        alarm_eid, alarm_st = self.home.primary_alarm()
        if not alarm_eid or alarm_st in ("disarmed", "unknown", "unavailable"):
            return
        # Cancella motion triggers pendenti
        for t in list(self._pending.values()):
            t.cancel()
        self._pending.clear()
        self._recent_motion.clear()
        try:
            await self.rest.call_service(
                "alarm_control_panel", "alarm_disarm",
                {"code": self.alarm_code},
                target={"entity_id": alarm_eid}
            )
            logger.info("✅ Disarmo immediato per rientro %s (allarme era pending)", name)
        except Exception as e:
            logger.warning("Disarmo immediato FAIL: %s", e)
        # Disarma anche partizioni extra con delay configurabile
        _extra = getattr(self.home, "_alarm_extra_panels", [])
        _delay = int(getattr(self.home, "_alarm_extra_delay", 1))
        for _eid in _extra:
            await asyncio.sleep(_delay)
            try:
                await self.rest.call_service(
                    "alarm_control_panel", "alarm_disarm",
                    {"code": self.alarm_code},
                    target={"entity_id": _eid}
                )
                logger.info("✅ Partizione extra disarmata (delay %ds): %s", _delay, _eid)
            except Exception as _e:
                logger.warning("Partizione extra DISARM FAIL %s: %s", _eid, _e)

    async def _fast_disarm(self, name: str, bounce_sec: int):
        """
        Disarma l'allarme dopo `bounce_sec` secondi se la persona è ancora a casa.
        Molto più veloce del vecchio _confirm_arrived (300s).
        """
        logger.info("👤 %s rientrato — attendo %ds anti-bounce prima di disarmare",
                    name, bounce_sec)
        try:
            await asyncio.sleep(bounce_sec)
        except asyncio.CancelledError:
            logger.info("👤 %s: disarmo annullato (uscito durante anti-bounce)", name)
            return

        # Verifica che sia ancora a casa — usa GPS + proximity override
        still_home = any(
            self.home._person_is_home(eid)
            for eid, data in self.home.persons.items()
            if data.get("name") == name
        )
        if not still_home:
            logger.info("Disarmo %s ANNULLATO: GPS rimbalzo (non è più a casa dopo %ds)",
                        name, bounce_sec)
            return

        # Se alarm_enabled=False → HomeMind non tocca MAI l'allarme
        if not getattr(self.home, "_alarm_enabled", True):
            logger.info("DISARM SKIP: alarm_enabled=false — HomeMind non gestisce l'allarme")
            return

        # Se alarm_auto_arm=disabled → HomeMind non arma E non disarma
        _auto_arm_mode = getattr(self.home, "_alarm_auto_arm", "auto")
        if _auto_arm_mode == "disabled":
            logger.info("DISARM SKIP: alarm_auto_arm=disabled — HomeMind non gestisce l'allarme")
            return

        alarm_eid, alarm_st = self.home.primary_alarm()
        if not alarm_eid:
            logger.info("Nessun allarme configurato — skip disarmo")
            return

        if alarm_st in ("disarmed", "unknown", "unavailable"):
            logger.info("Allarme già %s — nessun disarmo necessario", alarm_st)
            return

        if time.time() - self._last_disarm_ts < DISARM_COOLDOWN:
            logger.info("Disarmo SKIP: cooldown attivo")
            return

        self._last_disarm_ts = time.time()

        # Cancella motion triggers pendenti (è arrivato il proprietario)
        pending = list(self._pending.keys())
        if pending:
            logger.info("Rientro %s — cancello %d motion trigger pendenti: %s",
                        name, len(pending), pending)
        for t in list(self._pending.values()):
            t.cancel()
        self._pending.clear()
        self._recent_motion.clear()

        try:
            await self.rest.call_service(
                "alarm_control_panel", "alarm_disarm",
                {"code": self.alarm_code},
                target={"entity_id": alarm_eid}
            )
            logger.info("✅ Allarme disarmato per %s (dopo %ds)", name, bounce_sec)
        except Exception as e:
            logger.warning("Disarm FAIL: %s", e)

        # Disarma anche le partizioni extra con delay configurabile
        _extra_panels = getattr(self.home, "_alarm_extra_panels", [])
        _extra_delay  = int(getattr(self.home, "_alarm_extra_delay", 1))
        for _extra_eid in _extra_panels:
            _extra_st = self.home.alarm_panels.get(_extra_eid, {}).get("state", "unknown")
            if _extra_st in ("disarmed", "unavailable", "unknown"):
                logger.info("Partizione extra %s già disarmata — skip", _extra_eid)
                continue
            await asyncio.sleep(_extra_delay)  # delay tra partizioni
            try:
                await self.rest.call_service(
                    "alarm_control_panel", "alarm_disarm",
                    {"code": self.alarm_code},
                    target={"entity_id": _extra_eid}
                )
                logger.info("✅ Partizione extra disarmata (delay %ds): %s", _extra_delay, _extra_eid)
            except Exception as _ep:
                logger.warning("Partizione extra DISARM FAIL %s: %s", _extra_eid, _ep)

    async def _delayed_welcome_notify(self, name: str, delay: int):
        """Invia notifica benvenuto dopo `delay` secondi.
        Regola semplice: GPS home + _was_away=True + proximity <= soglia
        """
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        # 1. GPS deve ancora dire home
        _still_gps_home = any(
            self.home._is_home_state(data.get("state", ""))
            for eid, data in self.home.persons.items()
            if data.get("name") == name
        )
        if not _still_gps_home:
            logger.info("Benvenuto %s ANNULLATO: GPS non più a casa", name)
            return

        # 2. _was_away = True (proximity ha visto uscita fisica)
        if not self._was_away.get(name, False):
            logger.info("Benvenuto %s ANNULLATO: nessuna uscita fisica rilevata", name)
            return

        # 3. Proximity non deve dire lontano (evita benvenuto a 3km con GPS bounce)
        for _peid, _prox in self.home.proximity_sensors.items():
            if self.home.persons.get(_peid, {}).get("name") != name:
                continue
            _cm  = _prox.get("current_m")
            _thr = float(_prox.get("threshold_m", 100))
            if _cm is not None and float(_cm) > _thr:
                logger.info("Benvenuto %s ANNULLATO: proximity = %.0fm > %.0fm",
                            name, _cm, _thr)
                return

        logger.info("✅ %s confermato a casa — invio notifica benvenuto", name)
        self._last_welcome_ts[name] = time.time()
        # Reset _was_away: benvenuto inviato = "tornato a casa"
        # Prossimi bounce GPS non avranno _was_away=True → no spam
        self._was_away[name] = False


        if self.notifier:
            try:
                who = self.home.who_is_home()
                await self.notifier.send(
                    "🏠 HomeMind: Bentornato!",
                    name + " rientrato/a\n"
                    "In casa: " + (", ".join(who) or name) + "\n"
                    "Ora: " + now_local().strftime("%H:%M")
                )
            except Exception as e:
                logger.warning("Notifica benvenuto FAIL: %s", e)

    # ── Movimento ─────────────────────────────────────────────────────────────

    async def _schedule_motion(self, eid: str):
        _, alarm_st = self.home.primary_alarm()
        armed_states   = ("armed_away", "armed_home", "armed_night", "armed_vacation")
        already_active = alarm_st in ("triggered", "pending")

        # In armed_home e armed_night: persone in casa → il movimento è normale.
        # Solo i sensori di CONTATTO (porte/finestre) devono triggerare.
        # Il movimento NON deve triggerare l'allarme in queste modalità.
        if alarm_st in ("armed_home", "armed_night"):
            logger.debug("Motion skip %s: modalità %s — solo perimetrali attivi", eid, alarm_st)
            return

        # In armed_away: casa vuota → il movimento triggera
        if not self.home.everyone_away() and alarm_st not in ("triggered", "pending"):
            logger.debug("Motion skip %s: casa occupata", eid)
            return

        # Permetti notifica anche se allarme già triggered/pending (ma non se disarmato)
        if alarm_st not in armed_states and not already_active:
            logger.info("Motion skip %s: allarme in stato '%s' (non armato)", eid, alarm_st)
            return

        # Registra il sensore come "scattato di recente"
        now = time.time()
        self._recent_motion[eid] = now

        # Pulisci sensori scaduti dalla finestra
        self._recent_motion = {
            e: t for e, t in self._recent_motion.items()
            if now - t <= CROSS_REF_WINDOW
        }

        # ── Notifica IMMEDIATA ad ogni sensore che scatta ──────────────────
        if self.notifier:
            info     = self.home.motion_sensors.get(eid, {})
            name     = info.get("name", eid.split(".")[-1])
            zone     = info.get("zone", "")
            is_night = now_local().hour >= 22 or now_local().hour < 7
            icon     = "🌙" if is_night else "🚨"
            try:
                await self.notifier._telegram(
                    f"{icon} <b>Movimento rilevato: {name}</b>\n"
                    f"🕐 {now_local().strftime('%H:%M:%S')}"
                    + (f"  📍 {zone}" if zone else ""),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning("Notifica immediata FAIL: %s", e)

        # Determina soglia effettiva
        total_sensors = len(self.home.motion_sensors)
        threshold = self._get_threshold()
        active_count = len(self._recent_motion)
        logger.info(
            "MOTION cross-ref: %s scattato | attivi nella finestra: %d/%d (soglia: %d)",
            eid, active_count, total_sensors, threshold
        )

        if active_count < threshold:
            logger.info(
                "Motion %s: %d/%d sensori attivi — sotto soglia (%d), aspetto altri sensori",
                eid, active_count, total_sensors, threshold
            )
        else:
            logger.warning(
                "🚨 Cross-ref CONFERMATO: %d sensori in %ds → avvio allarme",
                active_count, CROSS_REF_WINDOW
            )
        self._cancel_motion(eid)
        self._pending[eid] = asyncio.create_task(
            self._fire_motion(eid), name="mot_" + eid
        )

    def _cancel_motion(self, eid: str):
        t = self._pending.pop(eid, None)
        if t and not t.done():
            t.cancel()

    async def _fire_motion(self, eid: str):
        try:
            await asyncio.sleep(MOTION_DELAY)
        except asyncio.CancelledError:
            return

        alarm_eid, alarm_st = self.home.primary_alarm()
        armed_states  = ("armed_away", "armed_home", "armed_night", "armed_vacation")
        active_states = ("triggered", "pending")

        # In armed_home/armed_night: annulla — il movimento non triggera
        if alarm_st in ("armed_home", "armed_night"):
            logger.info("Motion %s annullato al fire: modalità %s — solo perimetrali", eid, alarm_st)
            self._recent_motion.pop(eid, None)
            return

        if not self.home.everyone_away() and alarm_st not in active_states:
            logger.info("Motion %s annullato: qualcuno rientrato", eid)
            self._recent_motion.pop(eid, None)
            return

        # Controlla che l'allarme sia ancora in uno stato valido
        # (armato O già in pending/triggered — ma NON disarmato)
        if alarm_st not in armed_states and alarm_st not in active_states:
            logger.info("Motion %s annullato: allarme disarmato manualmente (%s)", eid, alarm_st)
            self._recent_motion.pop(eid, None)
            return

        # Verifica cross-referencing finale: quanti sensori sono ancora "freschi"
        now = time.time()
        fresh = {e: t for e, t in self._recent_motion.items() if now - t <= CROSS_REF_WINDOW}
        total_sensors = len(self.home.motion_sensors)
        threshold = self._get_threshold()

        if len(fresh) < threshold:
            logger.info(
                "Motion %s annullato al fire: solo %d/%d sensori freschi (soglia %d)",
                eid, len(fresh), total_sensors, threshold
            )
            return

        async with self._lock:
            info     = self.home.motion_sensors.get(eid, {})
            name     = info.get("name", eid)
            zone     = info.get("zone", "interno")
            is_night = now_local().hour >= 22 or now_local().hour < 7
            sev      = "CRITICO" if is_night else "ALTO"
            # Nomi sensori che hanno confermato
            confirmed_names = [
                self.home.motion_sensors.get(e, {}).get("name", e)
                for e in fresh
            ]

            logger.warning("🚨 INTRUSO confermato: %s zona=%s sev=%s | sensori=%s",
                           eid, zone, sev, confirmed_names)

            alarm_eid, alarm_st = self.home.primary_alarm()
            # Triggera allarme hardware SOLO se non è già triggered/pending
            if alarm_eid and alarm_st not in ("triggered", "pending"):
                try:
                    await self.rest.call_service(
                        "alarm_control_panel", "alarm_trigger",
                        {"code": self.alarm_code},
                        target={"entity_id": alarm_eid}
                    )
                    logger.warning("✅ Allarme TRIGGERED da %s", eid)
                except Exception as e:
                    logger.error("Trigger FAIL: %s", e)
            elif alarm_st in ("triggered", "pending"):
                logger.info("Allarme già %s — solo notifica Telegram per %s", alarm_st, eid)

            if self.notifier:
                try:
                    icon = "🌙" if is_night else "⚠️"
                    away = self.home.who_is_away()
                    sensors_str = ", ".join(confirmed_names) if len(confirmed_names) > 1 else name
                    # Titolo diverso se allarme già attivo
                    if alarm_st in ("triggered", "pending"):
                        title = icon + " MOVIMENTO RILEVATO — " + zone
                    else:
                        title = icon + " ALLARME " + sev + " — " + zone
                    await self.notifier.send(
                        title,
                        "Sensori: " + sensors_str + "\n"
                        "Ora: " + now_local().strftime("%H:%M:%S") + "\n"
                        "Assenti: " + (", ".join(away) or "tutti")
                    )
                except Exception as e:
                    logger.warning("Notifica FAIL: %s", e)

            # ── Snapshot Frigate con cooldown anti-duplicati ─────────────────
            FRIGATE_COOLDOWN = 60  # secondi — non rimanda la stessa camera entro 60s
            if self._frigate and self._frigate.is_ready() and self._tg_bot:
                try:
                    cam = self._frigate.camera_for_sensor(eid)
                    now_ts = asyncio.get_event_loop().time()
                    cams_to_send = []
                    if cam:
                        # Camera specifica associata al sensore
                        last = self._frigate_sent.get(cam, 0)
                        if now_ts - last >= FRIGATE_COOLDOWN:
                            cams_to_send = [cam]
                        else:
                            logger.info("Frigate: cooldown attivo per '%s' (%.0fs fa) — skip", cam, now_ts - last)
                    else:
                        # Nessuna camera associata — fallback su tutte, ma solo quelle non in cooldown
                        if self._frigate.snapshot_on_alarm:
                            for c in self._frigate.all_cameras():
                                last = self._frigate_sent.get(c, 0)
                                if now_ts - last >= FRIGATE_COOLDOWN:
                                    cams_to_send.append(c)
                                else:
                                    logger.info("Frigate: cooldown '%s' — skip", c)
                    for cam_name in cams_to_send:
                        logger.info("Frigate: invio snapshot camera '%s'", cam_name)
                        self._frigate_sent[cam_name] = now_ts
                        for cid in self._tg_bot.allowed:
                            await self._tg_bot.send_frigate_snapshot(
                                cid, cam_name,
                                caption=f"📷 {cam_name} — {now_local().strftime('%H:%M:%S')}"
                            )
                except Exception as e:
                    logger.warning("Frigate snapshot FAIL: %s", e)

            # Pop solo questo sensore (non clear totale) — permette agli altri di notificare
            self._recent_motion.pop(eid, None)

    # ── Contatti (porte/finestre) ──────────────────────────────────────────────

    async def _handle_contact_open(self, eid: str):
        """Gestisce apertura porta/finestra.
        
        Logica per modalità allarme:
        - armed_away:  casa VUOTA → triggera allarme (intrusione esterna)
        - armed_home:  persone IN CASA → triggera allarme (perimetrale violato)
        - armed_night: persone IN CASA di notte → triggera allarme (perimetrale notturno)
        - disarmed:    nessuna azione
        """
        _, alarm_st = self.home.primary_alarm()
        armed_perimeter = ("armed_away", "armed_home", "armed_night", "armed_vacation")
        active_states   = ("triggered", "pending")

        # Non fare nulla se allarme disarmato
        if alarm_st not in armed_perimeter and alarm_st not in active_states:
            logger.debug("CONTACT open %s: allarme %s — nessuna azione", eid, alarm_st)
            return

        info = self.home.contact_sensors.get(eid, {})
        name = info.get("name", eid.split(".")[-1])
        dc   = info.get("device_class", "opening")
        icon = "🚪" if dc == "door" else "🪟" if dc == "window" else "🔓"
        is_night  = now_local().hour >= 22 or now_local().hour < 7
        home_mode = alarm_st in ("armed_home", "armed_night")

        # Modalità armed_home/armed_night: persone in casa ma perimetrale attivo
        if home_mode:
            alert_icon = "🌙" if is_night else "🏠"
            mode_label = "NOTTURNA" if alarm_st == "armed_night" else "CASA"
            logger.warning("🚨 CONTATTO APERTO [%s]: %s (%s) — persone in casa", mode_label, name, eid)

            if self.notifier:
                try:
                    await self.notifier._telegram(
                        f"{alert_icon} <b>{icon} ALLARME {mode_label} — {name}</b>\n"
                        f"🕐 {now_local().strftime('%H:%M:%S')}\n"
                        f"⚠️ Perimetrale violato! Verificate la sicurezza.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning("Contact notify FAIL: %s", e)

            # Triggera allarme hardware anche in armed_home/armed_night
            alarm_eid, alarm_st2 = self.home.primary_alarm()
            if alarm_eid and alarm_st2 not in ("triggered", "pending"):
                try:
                    await self.rest.call_service(
                        "alarm_control_panel", "alarm_trigger",
                        {"code": self.alarm_code},
                        target={"entity_id": alarm_eid}
                    )
                    logger.warning("✅ Allarme TRIGGERED da contatto %s [%s]", eid, mode_label)
                except Exception as e:
                    logger.error("Contact trigger FAIL: %s", e)

        elif self.home.everyone_away():
            # armed_away: casa vuota — comportamento classico
            alert_icon = "🌙" if is_night else "🚨"
            logger.warning("🚨 CONTATTO APERTO con allarme armato: %s (%s)", name, eid)

            if self.notifier:
                try:
                    await self.notifier._telegram(
                        f"{alert_icon} <b>{icon} {dc.upper()} APERTA: {name}</b>\n"
                        f"🕐 {now_local().strftime('%H:%M:%S')}\n"
                        f"⚠️ Allarme in corso di attivazione…",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning("Contact notify FAIL: %s", e)

            alarm_eid, alarm_st2 = self.home.primary_alarm()
            if alarm_eid and alarm_st2 not in ("triggered", "pending"):
                try:
                    await self.rest.call_service(
                        "alarm_control_panel", "alarm_trigger",
                        {"code": self.alarm_code},
                        target={"entity_id": alarm_eid}
                    )
                    logger.warning("✅ Allarme TRIGGERED da contatto %s", eid)
                except Exception as e:
                    logger.error("Contact trigger FAIL: %s", e)
        else:
            # Casa occupata + allarme non in modalità home/night → solo log
            logger.debug("CONTACT open %s: casa occupata, allarme %s — nessuna azione", eid, alarm_st)

    async def _check_open_contacts_on_arm(self):
        """Controlla se ci sono porte/finestre aperte all'armamento. Cooldown 90s anti-doppio."""
        if not self.home.contact_sensors:
            return

        # Cooldown: evita doppia notifica se allarme si riarma rapidamente
        now = time.time()
        if now - self._last_arm_notify_ts < 90:
            logger.info("check_contacts: cooldown attivo (%.0fs) — skip", now - self._last_arm_notify_ts)
            return

        open_contacts = {
            eid: info for eid, info in self.home.contact_sensors.items()
            if info.get("state") == "on"
        }

        if not open_contacts:
            logger.info("✅ Armamento: tutte porte/finestre chiuse")
            return

        self._last_arm_notify_ts = now

        def _icon(name: str, dc: str) -> str:
            nl = name.lower()
            if any(k in nl for k in ("finestra", "window", "vetro", "balcone")):
                return "🪟"
            if any(k in nl for k in ("garage",)):
                return "🏠"
            if dc == "window":
                return "🪟"
            if dc == "garage_door":
                return "🏠"
            return "🚪"

        lines = []
        for eid, info in open_contacts.items():
            icon = _icon(info["name"], info.get("device_class", "door"))
            dc_label = "Finestra" if icon == "🪟" else ("Garage" if icon == "🏠" else "Porta")
            lines.append(f"{icon} {dc_label}: <b>{info['name']}</b>")

        n = len(open_contacts)
        msg = (
            f"⚠️ <b>{n} apertura{'e' if n > 1 else ''} rilevata{'e' if n > 1 else ''} all'armamento:</b>\n"
            + "\n".join(lines)
            + "\n\n<i>L'allarme è armato — controlla prima di uscire.</i>"
        )

        logger.warning("⚠️ Armamento con %d contatti aperti: %s",
                       n, [i["name"] for i in open_contacts.values()])

        if self.notifier:
            try:
                await self.notifier._telegram(msg, parse_mode="HTML")
            except Exception as e:
                logger.warning("Open contacts notify FAIL: %s", e)

    async def _sync_alarm_mode_to_config(self, new_mode: str):
        """
        Quando l'utente arma manualmente da HA, sincronizza la modalità
        nel person_config.json e notifica senza il messaggio di "armamento automatico".
        """
        import json as _json
        from pathlib import Path as _Path

        config_path = _Path("/config/homemind_patches/person_config.json")
        try:
            cfg = {}
            if config_path.exists():
                cfg = _json.loads(config_path.read_text(encoding="utf-8-sig"))

            # Aggiorna alarm_arm_mode nel file
            cfg["alarm_arm_mode"] = new_mode
            # Aggiorna anche alarm_panel se non già impostato
            if not cfg.get("alarm_panel"):
                alarm_eid, _ = self.home.primary_alarm()
                if alarm_eid:
                    cfg["alarm_panel"] = alarm_eid

            config_path.write_text(
                _json.dumps(cfg, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.info("Config aggiornato: alarm_arm_mode=%s", new_mode)
        except Exception as e:
            logger.warning("_sync_alarm_mode_to_config error: %s", e)

        # Notifica discreta — NON il messaggio di "ANTIFURTO IN ATTIVAZIONE"
        if self.notifier:
            mode_labels = {
                "armed_away":    "🔒 Fuori casa",
                "armed_home":    "🏠 In casa (perimetrali)",
                "armed_night":   "🌙 Notte (perimetrali)",
                "armed_vacation": "✈️ Vacanza",
            }
            label = mode_labels.get(new_mode, new_mode)
            try:
                await self.notifier.send_html(
                    f"🔒 <b>Antifurto attivato manualmente</b>\n"
                    f"Modalità: <b>{label}</b>\n"
                    f"🕐 {now_local().strftime('%H:%M')}\n"
                    f"<i>HomeMind ora opera in modalità {label}</i>"
                )
            except Exception as e:
                logger.warning("Notifica armamento manuale FAIL: %s", e)

    def status(self) -> dict:
        ae, ast_ = self.home.primary_alarm()
        total    = len(self.home.motion_sensors)
        threshold = self._get_threshold()
        now = time.time()
        fresh_motion = {e: t for e, t in self._recent_motion.items()
                        if now - t <= CROSS_REF_WINDOW}
        return {
            "everyone_away":    self.home.everyone_away(),
            "who_is_home":      self.home.who_is_home(),
            "who_is_away":      self.home.who_is_away(),
            "alarm_entity":     ae,
            "alarm_state":      ast_,
            "motion_sensors":   total,
            "cross_ref_threshold": threshold,
            "cross_ref_window_sec": CROSS_REF_WINDOW,
            "recent_motion_count": len(fresh_motion),
            "motion_active":    [
                {"eid": e, "zone": v["zone"], "name": v["name"]}
                for e, v in self.home.motion_sensors.items()
                if v["state"] == "on"
            ],
            "pending_triggers": list(self._pending.keys()),
        }
