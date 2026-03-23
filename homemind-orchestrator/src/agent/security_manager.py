"""security_manager.py v55 — Sicurezza deterministica con cross-referencing."""
import asyncio, logging, time
from datetime import datetime
from utils.timezone_helper import now_local
from agent.home_model import HomeModel

logger = logging.getLogger("homemind.security")

MOTION_DELAY        = 8    # secondi attesa prima di triggerare allarme
STARTUP_DELAY       = 30   # secondi dopo avvio prima del check iniziale
ARM_COOLDOWN        = 60   # secondi minimo tra due armamenti
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
    def __init__(self, home: HomeModel, rest_client, notifier=None, alarm_code="1234", frigate_client=None, tg_bot=None):
        self.home       = home
        self.rest       = rest_client
        self.notifier   = notifier
        self.alarm_code = alarm_code
        self._frigate   = frigate_client   # FrigateClient opzionale
        self._tg_bot    = tg_bot           # TelegramBot per send_photo
        self._lock            = asyncio.Lock()
        self._pending:       dict = {}   # motion tasks
        self._pending_welcome: dict = {}        # person_name → asyncio.Task disarmo
        self._pending_welcome_notify: dict = {} # person_name → asyncio.Task notifica benvenuto
        self._last_arm_ts     = 0.0
        self._home_motion_ts: dict = {}  # eid → timestamp ultima notifica "in casa"
        self._last_disarm_ts  = 0.0
        self._last_arm_notify_ts = 0.0   # cooldown notifica contatti aperti all'armamento
        self._last_welcome_ts: dict = {}   # person_name → timestamp ultimo benvenuto
        self.routine_manager = None        # impostato da main.py dopo init
        self._left_ts: dict = {}           # person_name → timestamp ultima uscita
        # Cross-referencing: sensori scattati di recente (eid → timestamp)
        self._recent_motion:  dict = {}    # eid → timestamp primo scatto
        self._frigate_sent:   dict = {}    # cam_name → timestamp ultimo snapshot inviato
        # Soglia override da config (0 = auto)
        self._threshold_override: int = 0

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

        if self.home.everyone_away():
            if alarm_st == "disarmed":
                logger.info("Startup: casa vuota + allarme disarmato → armo")
                await self._all_left("(riavvio sistema)")
            elif alarm_st in ("armed_away","armed_home","triggered","arming","pending"):
                logger.info("Startup: casa vuota, allarme già %s — nessuna azione", alarm_st)
            else:
                # unknown o altro → armo comunque
                logger.info("Startup: casa vuota + allarme stato sconosciuto (%s) → armo", alarm_st)
                await self._all_left("(riavvio sistema)")
        else:
            in_casa = self.home.who_is_home()
            logger.info("Startup: casa occupata da %s — nessuna azione", in_casa)
            # Se qualcuno è in casa e allarme è armed_away → disarma
            if alarm_st in ("armed_away",):
                logger.info("Startup: qualcuno in casa ma allarme armed_away → disarmo")
                await self._someone_arrived(", ".join(in_casa))

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
                    # Se GPS dice fuori ma sensore dice vicino → tratta come rientro
                    if is_near and not self.home._is_home_state(gps_st):
                        logger.info("📍 Proximity override: %s trattato come IN CASA (%.0fm)", name, dist_m)
                        await self._handle_presence(person_eid, gps_st, "home")
                    # Se GPS dice home E proximity diventa near → benvenuto se non già gestito
                    # Caso: GPS arrivava home mentre proximity era ancora alta, ora si aggiorna
                    elif is_near and self.home._is_home_state(gps_st):
                        if not self.home._person_is_home(person_eid):
                            logger.info("📍 Proximity %s: ora vicino (%.0fm) + GPS home → benvenuto", name, dist_m)
                            await self._someone_arrived(name)
                    # Se GPS dice fuori E sensore dice lontano → ricontrolla everyone_away
                    # Caso: proximity era stale durante uscita, ora si aggiorna → arma se tutti fuori
                    elif not is_near and not self.home._is_home_state(gps_st):
                        if self.home.everyone_away():
                            _, alarm_st = self.home.primary_alarm()
                            if alarm_st in ("armed_away", "armed_home", "arming"):
                                logger.debug(
                                    "📍 Proximity (%.0fm): allarme già %s — nessuna azione",
                                    dist_m, alarm_st
                                )
                            else:
                                logger.info(
                                    "📍 Proximity aggiornato (%.0fm) + GPS fuori + everyone_away → armo",
                                    dist_m
                                )
                                await self._all_left(f"proximity aggiornato ({dist_m:.0f}m)")
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
            # Appena armato → controlla subito contatti aperti
            elif new_st in ("armed_away", "armed_home", "armed_night", "armed_vacation") \
                    and old_st not in ("armed_away", "armed_home", "armed_night", "armed_vacation"):
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

            # Registra partenza basata su GPS anche se proximity override dice "in casa"
            # Questo risolve il caso proximity stale: GPS dice not_home ma proximity 0m
            if is_home_old and not gps_is_home_new:
                self._left_ts[name] = time.time()
                logger.info("👤 %s: partenza GPS registrata (proximity potrebbe essere stale)", name)

            if not is_home_new and is_home_old:
                # Persona uscita — cancella task disarmo e notifica benvenuto
                welcome_task = self._pending_welcome.get(name)
                if welcome_task and not welcome_task.done():
                    welcome_task.cancel()
                    logger.info("👤 %s uscito durante attesa benvenuto — task CANCELLATO", name)
                notify_task = self._pending_welcome_notify.get(name)
                if notify_task and not notify_task.done():
                    notify_task.cancel()
                    logger.info("👤 %s uscito — notifica benvenuto ANNULLATA", name)
                # Persona uscita (da qualsiasi stato "in casa" a qualsiasi stato "fuori")
                logger.info("👤 %s uscito/a (zona: %s)", name, new_st)
                # Registra per routine learning
                if hasattr(self, "routine_manager") and self.routine_manager:
                    self.routine_manager.record_event("departure", name)
                self._left_ts[name] = time.time()
                await asyncio.sleep(8)   # attendi aggiornamenti ritardati
                if self.home.everyone_away():
                    logger.info("🏠 Casa vuota dopo uscita di %s", name)
                    await self._all_left(name)
                else:
                    logger.info("Casa ancora occupata: %s", self.home.who_is_home())

            elif is_home_new and not is_home_old:
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

    async def _all_left(self, trigger: str):
        if time.time() - self._last_arm_ts < ARM_COOLDOWN:
            logger.info("Arm SKIP: cooldown attivo")
            return

        # ── Verifica finale proximity via REST (ultima difesa GPS ballerino) ──
        for person_eid, prox in self.home.proximity_sensors.items():
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
                    logger.info("ARM: verifica REST proximity %s = %.0fm (soglia %dm) → ok fuori", name, dist_m, threshold)
            except Exception as e:
                logger.warning("ARM: verifica REST proximity fallita (%s) — procedo con armamento", e)

        self._last_arm_ts = time.time()

        done = []

        # 1. Spegni luci
        lights = self.home.lights_on()
        if lights:
            try:
                await self.rest.call_service("light","turn_off",{},
                                             target={"entity_id": lights})
                done.append("Spente " + str(len(lights)) + " luci")
                logger.info("Luci spente: %s", lights)
            except Exception as e:
                logger.warning("Luci spegni FAIL: %s", e)

        # 2. Spegni clima
        for ceid, v in self.home.climate.items():
            if v["state"] not in ("off","unavailable","unknown"):
                try:
                    await self.rest.call_service("climate","turn_off",{},
                                                 target={"entity_id": ceid})
                    done.append("Clima spento")
                except Exception as e:
                    logger.warning("Clima spegni FAIL: %s", e)

        # 3. Arma allarme
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

        # 4. Notifica
        if self.notifier:
            try:
                msg = (
                    "Trigger: " + trigger + "\n"
                    "Ora: " + now_local().strftime("%H:%M") + "\n"
                    + "\n".join(done)
                )
                await self.notifier.send("HomeMind: Casa Vuota", msg)
            except Exception as e:
                logger.warning("Notifica FAIL: %s", e)

    async def _someone_arrived(self, name: str):
        WELCOME_COOLDOWN  = 3600   # max 1 benvenuto all'ora per persona
        DISARM_BOUNCE_SEC = 20     # attendi solo 20s anti-bounce GPS prima di disarmare

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
        left_ts = self._left_ts.get(name, 0.0)
        away_minutes = (time.time() - left_ts) / 60 if left_ts else 999
        # Se via da più di 30 minuti, ignora il cooldown — rientro reale
        cooldown_override = away_minutes >= 30
        can_welcome = (elapsed_since_last >= WELCOME_COOLDOWN or cooldown_override) and away_minutes >= 5
        if can_welcome:
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
        else:
            logger.info("👤 %s: benvenuto SKIP — cooldown attivo (%.0f min fa)", name, elapsed_since_last/60)

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

    async def _delayed_welcome_notify(self, name: str, delay: int):
        """Invia notifica benvenuto dopo `delay` secondi se la persona è ancora a casa."""
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        still_home = any(
            self.home._person_is_home(eid)
            for eid, data in self.home.persons.items()
            if data.get("name") == name
        )
        if not still_home:
            logger.info("Benvenuto %s ANNULLATO: non è più a casa", name)
            return

        logger.info("✅ %s confermato a casa — invio notifica benvenuto", name)
        self._last_welcome_ts[name] = time.time()

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
        if not self.home.everyone_away():
            logger.debug("Motion skip %s: casa occupata", eid)
            return
        # Permetti notifica anche se allarme già triggered/pending (ma non se disarmato)
        _, alarm_st = self.home.primary_alarm()
        armed_states   = ("armed_away", "armed_home", "armed_night", "armed_vacation")
        already_active = alarm_st in ("triggered", "pending")
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

        if not self.home.everyone_away():
            logger.info("Motion %s annullato: qualcuno rientrato", eid)
            self._recent_motion.pop(eid, None)
            return

        # Controlla che l'allarme sia ancora in uno stato valido
        # (armato O già in pending/triggered — ma NON disarmato)
        alarm_eid, alarm_st = self.home.primary_alarm()
        armed_states  = ("armed_away", "armed_home", "armed_night", "armed_vacation")
        active_states = ("triggered", "pending")
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
        """Gestisce apertura porta/finestra: notifica se allarme armato, triggera se fuori casa."""
        if self.home.everyone_away():
            _, alarm_st = self.home.primary_alarm()
            armed_states  = ("armed_away", "armed_home", "armed_night", "armed_vacation")
            active_states = ("triggered", "pending")
            if alarm_st not in armed_states and alarm_st not in active_states:
                return

            info = self.home.contact_sensors.get(eid, {})
            name = info.get("name", eid.split(".")[-1])
            dc   = info.get("device_class", "opening")
            icon = "🚪" if dc == "door" else "🪟" if dc == "window" else "🔓"
            is_night = now_local().hour >= 22 or now_local().hour < 7
            alert_icon = "🌙" if is_night else "🚨"

            logger.warning("🚨 CONTATTO APERTO con allarme armato: %s (%s)", name, eid)

            # Notifica immediata
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

            # Triggera allarme hardware
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
            # Casa occupata: solo log, nessuna notifica
            logger.debug("CONTACT open %s: casa occupata — nessuna azione", eid)

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
