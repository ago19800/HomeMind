"""
agent/appliance_monitor.py — Monitoraggio elettrodomestici con notifiche fine ciclo.

OPZIONALE — attivo solo se configurato in person_config.json.

Supporta due modalità per ogni elettrodomestico:

  ① SMART (Bosch, Miele, Siemens, Samsung Home Connect, ecc.)
    L'elettrodomestico espone già i propri sensori in HA tramite integrazione.
    HomeMind legge direttamente lo stato operativo (Run → Finished/Ready).

  ② PRESA (qualsiasi elettrodomestico su presa smart con misura energia)
    HomeMind monitora la potenza assorbita e rileva start/stop dal consumo.
    Funziona con Sonoff S31, Shelly Plug S, NOUS A1, TP-Link Kasa, ecc.

─────────────────────────────────────────────────────────────────────────────
CONFIGURAZIONE in /config/homemind_patches/person_config.json:

{
  "appliances": {
    "lavastoviglie": {
      "name": "Lavastoviglie",
      "icon": "🍽️",
      "mode": "smart",
      "state_sensor": "sensor.bosch_dishwasher_operation_state",
      "running_states": ["Run"],
      "done_states":    ["Finished", "Ready"],
      "program_sensor": "sensor.bosch_dishwasher_selected_program",
      "door_sensor":    "binary_sensor.bosch_dishwasher_door"
    },
    "lavatrice": {
      "name": "Lavatrice",
      "icon": "🫧",
      "mode": "power",
      "power_sensor": "sensor.lavatrice_power",
      "power_on_threshold":   50,
      "power_off_threshold":  10,
      "min_cycle_minutes":    20,
      "max_idle_minutes":      5
    },
    "asciugatrice": {
      "name": "Asciugatrice",
      "icon": "🌀",
      "mode": "power",
      "power_sensor": "sensor.asciugatrice_power",
      "power_on_threshold":  100,
      "power_off_threshold":  15,
      "min_cycle_minutes":    30,
      "max_idle_minutes":      8
    },
    "forno": {
      "name": "Forno",
      "icon": "🔥",
      "mode": "power",
      "power_sensor": "sensor.presa_cucina_power",
      "power_on_threshold":  500,
      "power_off_threshold":  30,
      "min_cycle_minutes":    10,
      "max_idle_minutes":      3
    }
  }
}

─────────────────────────────────────────────────────────────────────────────
SENSORI BOSCH / Home Connect tipici:
  sensor.*_operation_state        → BSH.Common.EnumType.OperationState.*
    valori comuni: Inactive, Ready, DelayedStart, Run, Pause, ActionRequired,
                   Finished, Error, Aborting
  sensor.*_selected_program       → nome programma (es. "Auto 45-65°")
  sensor.*_remaining_program_time → secondi rimanenti
  binary_sensor.*_door            → aperta/chiusa
  sensor.*_power_state            → On / Off / Standby

  Per trovare i tuoi sensori: HA → Strumenti Sviluppo → Stati → cerca "bosch" o il nome del tuo elettrodomestico
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from utils.timezone_helper import now_local
from pathlib import Path
from typing import Optional

logger = logging.getLogger("homemind.appliances")

CONFIG_FILE  = Path("/config/homemind_patches/person_config.json")
POLL_SECONDS = 30   # controlla ogni 30 secondi

# Valori predefiniti per modalità power
DEFAULT_POWER_ON  = 50    # W — sopra = elettrodomestico in funzione
DEFAULT_POWER_OFF = 10    # W — sotto = elettrodomestico fermo
DEFAULT_MIN_CYCLE = 20    # minuti — ciclo più corto accettato
DEFAULT_MAX_IDLE  = 5     # minuti — idle massimo prima di considerarlo spento


class ApplianceState:
    """Stato runtime di un singolo elettrodomestico."""
    def __init__(self, key: str, cfg: dict):
        self.key  = key
        self.cfg  = cfg
        self.name = cfg.get("name", key.capitalize())
        self.icon = cfg.get("icon", "🔌")
        self.mode = cfg.get("mode", "power")   # "smart" | "power"

        # Stato corrente
        self.is_running      = False
        self.cycle_start: Optional[datetime] = None
        self.last_power_high: Optional[datetime] = None  # ultima volta sopra soglia
        self.notified_start  = False
        self.last_done_state = None   # per smart: ultimo done_state visto

    def cycle_duration(self) -> Optional[timedelta]:
        if self.cycle_start:
            return now_local() - self.cycle_start
        return None

    def duration_str(self) -> str:
        d = self.cycle_duration()
        if not d:
            return "durata sconosciuta"
        total_min = int(d.total_seconds() / 60)
        h, m = divmod(total_min, 60)
        if h:
            return f"{h}h {m:02d}min"
        return f"{m} min"


class ApplianceMonitor:
    def __init__(self, notifier=None, state_cache_cb=None, ai=None):
        self.notifier      = notifier
        self._cache_cb     = state_cache_cb
        self.ai            = ai
        self._appliances: dict[str, ApplianceState] = {}
        self._loaded       = False

    @property
    def _state_cache(self) -> dict:
        return self._cache_cb() if self._cache_cb else {}

    # ─────────────────────────────────────────────────────────────────────────
    # Avvio

    async def start(self):
        """Carica config e avvia il monitor. Non fa nulla se non configurato."""
        self._load_config()
        if not self._appliances:
            logger.info("ApplianceMonitor: nessun elettrodomestico configurato, modulo inattivo")
            return
        asyncio.create_task(self._poll_loop(), name="appliance_monitor")
        names = ", ".join(a.name for a in self._appliances.values())
        logger.info("ApplianceMonitor avviato — monitorando: %s", names)

    def _load_config(self):
        """Legge person_config.json e istanzia gli ApplianceState."""
        try:
            if not CONFIG_FILE.exists():
                return
            cfg = json.loads(CONFIG_FILE.read_text())
            appliances_cfg = cfg.get("appliances", {})
            if not appliances_cfg:
                return
            for key, acfg in appliances_cfg.items():
                if not isinstance(acfg, dict):
                    continue
                # "enabled": false → salta senza errori
                if not acfg.get("enabled", True):
                    logger.info("ApplianceMonitor: '%s' disabilitato (enabled=false)", key)
                    continue
                mode = acfg.get("mode", "power")
                # Validazione minima
                # Salta se esplicitamente disabilitato
                if not acfg.get("enabled", True):
                    logger.info("ApplianceMonitor: '%s' disabilitato (enabled: false)", key)
                    continue
                if mode == "smart" and not acfg.get("state_sensor"):
                    logger.warning("ApplianceMonitor: '%s' mode=smart ma state_sensor mancante", key)
                    continue
                if mode == "power" and not acfg.get("power_sensor"):
                    logger.warning("ApplianceMonitor: '%s' mode=power ma power_sensor mancante", key)
                    continue
                self._appliances[key] = ApplianceState(key, acfg)
                logger.info("ApplianceMonitor: '%s' caricato (mode=%s)", key, mode)
        except Exception as e:
            logger.error("ApplianceMonitor config load error: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Loop principale

    async def _poll_loop(self):
        """Controlla lo stato di ogni elettrodomestico ogni POLL_SECONDS."""
        # Attesa iniziale per dare tempo al sistema di caricarsi
        await asyncio.sleep(15)
        cycle = 0
        while True:
            cycle += 1
            try:
                cache = self._state_cache
                for app in self._appliances.values():
                    try:
                        if app.mode == "smart":
                            await self._check_smart(app, cache)
                        else:
                            await self._check_power(app, cache)
                    except Exception as e:
                        logger.warning("ApplianceMonitor check '%s' error: %s", app.key, e)
                # Log diagnostico ogni 10 cicli (~5 min)
                if cycle % 10 == 1:
                    self._log_diagnostic(cache)
            except Exception as e:
                logger.error("ApplianceMonitor poll loop error: %s", e)
            await asyncio.sleep(POLL_SECONDS)

    def _log_diagnostic(self, cache: dict):
        """Log diagnostico — mostra stato sensori configurati."""
        for app in self._appliances.values():
            if app.mode == "power":
                eid = app.cfg.get("power_sensor", "")
                entry = cache.get(eid, {})
                val = entry.get("state", "NON TROVATO")
                in_cache = eid in cache
                logger.info(
                    "ApplianceMonitor [diag] '%s': sensor=%s | in_cache=%s | value=%s | running=%s",
                    app.name, eid, in_cache, val, app.is_running
                )
                if not in_cache:
                    # Cerca sensori simili per aiutare il debug
                    hints = [k for k in cache if "power" in k.lower() or "watt" in k.lower() or "energy" in k.lower()][:5]
                    if hints:
                        logger.warning(
                            "ApplianceMonitor [diag] '%s': sensore '%s' NON in cache! "
                            "Sensori power/energy trovati in HA: %s",
                            app.name, eid, hints
                        )
            elif app.mode == "smart":
                eid = app.cfg.get("state_sensor", "")
                entry = cache.get(eid, {})
                val = entry.get("state", "NON TROVATO")
                in_cache = eid in cache
                logger.info(
                    "ApplianceMonitor [diag] '%s': sensor=%s | in_cache=%s | value=%s | running=%s",
                    app.name, eid, in_cache, val, app.is_running
                )
            self._poll_count = getattr(self, '_poll_count', 0) + 1
            if self._poll_count % 10 == 1:  # log ogni 5 minuti circa
                self._log_status()

    # ─────────────────────────────────────────────────────────────────────────
    # Modalità SMART (Bosch, Miele, ecc.)

    async def _check_smart(self, app: ApplianceState, cache: dict):
        state_eid  = app.cfg.get("state_sensor", "")
        entry      = cache.get(state_eid, {})
        state_val  = entry.get("state", "")

        if not state_val or state_val in ("unavailable", "unknown"):
            return

        running_states = [s.lower() for s in app.cfg.get("running_states", ["run"])]
        done_states    = [s.lower() for s in app.cfg.get("done_states", ["finished", "ready"])]
        state_low      = state_val.lower()

        # Avvio ciclo
        if state_low in running_states and not app.is_running:
            app.is_running   = True
            app.cycle_start  = now_local()
            app.notified_start = False
            app.last_done_state = None
            logger.info("ApplianceMonitor: '%s' avviato (state=%s)", app.name, state_val)
            await self._notify_start(app, cache)

        # Fine ciclo — evita notifica doppia per lo stesso done_state
        elif state_low in done_states and app.is_running and state_val != app.last_done_state:
            app.is_running      = False
            app.last_done_state = state_val
            logger.info("ApplianceMonitor: '%s' terminato (state=%s, durata=%s)",
                        app.name, state_val, app.duration_str())
            await self._notify_done(app, cache, state_val)
            app.cycle_start = None

        # Reset se torna a idle
        elif state_low not in running_states and state_low not in done_states:
            if app.is_running:
                logger.debug("ApplianceMonitor: '%s' tornato idle (state=%s)", app.name, state_val)
            app.is_running = False

    # ─────────────────────────────────────────────────────────────────────────
    # Modalità POWER (presa smart con misura energia)

    async def _check_power(self, app: ApplianceState, cache: dict):
        power_eid = app.cfg.get("power_sensor", "")
        entry     = cache.get(power_eid, {})
        val_str   = entry.get("state", "")

        if not val_str or val_str in ("unavailable", "unknown"):
            logger.warning("ApplianceMonitor '%s': sensore '%s' non disponibile (state=%r) — verifica entity_id nel config",
                           app.name, power_eid, val_str)
            return

        try:
            power_w = float(val_str)
        except (ValueError, TypeError):
            logger.warning("ApplianceMonitor '%s': valore non numerico da '%s': %r", app.name, power_eid, val_str)
            return
        
        on_thresh  = float(app.cfg.get("power_on_threshold",  DEFAULT_POWER_ON))
        off_thresh = float(app.cfg.get("power_off_threshold", DEFAULT_POWER_OFF))
        min_cycle  = int(app.cfg.get("min_cycle_minutes",     DEFAULT_MIN_CYCLE))
        max_idle   = int(app.cfg.get("max_idle_minutes",      DEFAULT_MAX_IDLE))

        logger.debug("ApplianceMonitor '%s': %.1fW (on≥%.0f off≤%.0f running=%s)",
                     app.name, power_w, on_thresh, off_thresh, app.is_running)

        now = now_local()

        # Sopra soglia ON → aggiorna last_power_high
        if power_w >= on_thresh:
            if not app.is_running:
                # Avvio ciclo
                app.is_running   = True
                app.cycle_start  = now
                app.notified_start = False
                logger.info("ApplianceMonitor: '%s' avviato (%.0fW ≥ %.0fW)",
                            app.name, power_w, on_thresh)
                await self._notify_start(app, cache)
            app.last_power_high = now

        # Sotto soglia OFF
        elif power_w <= off_thresh and app.is_running:
            # Controlla da quanto è sotto soglia (anti-rimbalzo per pause ciclo)
            if app.last_power_high:
                idle_seconds = (now - app.last_power_high).total_seconds()
                if idle_seconds >= max_idle * 60:
                    # Ciclo terminato
                    cycle_min = int(app.cycle_duration().total_seconds() / 60) if app.cycle_start else 0
                    if cycle_min >= min_cycle:
                        logger.info(
                            "ApplianceMonitor: '%s' terminato (%.0fW idle da %d min, ciclo %d min)",
                            app.name, power_w, idle_seconds / 60, cycle_min
                        )
                        await self._notify_done(app, cache)
                    else:
                        logger.debug(
                            "ApplianceMonitor: '%s' ciclo troppo corto (%d min < %d min), ignorato",
                            app.name, cycle_min, min_cycle
                        )
                    app.is_running      = False
                    app.cycle_start     = None
                    app.last_power_high = None

    # ─────────────────────────────────────────────────────────────────────────
    # Notifiche

    async def _notify_start(self, app: ApplianceState, cache: dict):
        """Notifica avvio ciclo (opzionale — solo se notify_on_start=true in config)."""
        if not app.cfg.get("notify_on_start", False):
            return
        msg = f"{app.icon} <b>{app.name} avviata</b>"
        # Per smart: aggiungi programma se disponibile
        prog = self._get_program(app, cache)
        if prog:
            msg += f" — {prog}"
        if self.notifier:
            await self.notifier.send_html(msg)

    async def _notify_done(self, app: ApplianceState, cache: dict, state_val: str = ""):
        """Notifica fine ciclo con durata e info extra."""
        duration = app.duration_str()
        prog     = self._get_program(app, cache)
        kwh      = self._get_energy(app, cache)

        # Riga principale
        lines = [f"{app.icon} <b>{app.name} terminata!</b>  ⏱️ {duration}"]

        if prog:
            lines.append(f"   📋 Programma: {prog}")
        if kwh:
            lines.append(f"   ⚡ Consumo ciclo: ~{kwh:.2f} kWh")

        # Per smart: aggiungi avviso porta aperta
        door = self._get_door_state(app, cache)
        if door == "on":   # binary_sensor open = "on"
            lines.append("   🚪 <i>Sportello aperto — puoi svuotare!</i>")

        # Suggerimento AI (solo se configurato)
        if app.cfg.get("ai_tip", False) and self.ai:
            tip = await self._ai_tip(app, duration, kwh)
            if tip:
                lines.append(f"\n🤖 <i>{tip}</i>")

        msg = "\n".join(lines)
        logger.info("ApplianceMonitor notify done: %s", msg.replace("\n", " | "))
        if self.notifier:
            await self.notifier.send_html(msg)

    def _get_program(self, app: ApplianceState, cache: dict) -> Optional[str]:
        """Legge il programma attivo (solo modalità smart)."""
        eid = app.cfg.get("program_sensor", "")
        if not eid:
            return None
        val = cache.get(eid, {}).get("state", "")
        if val and val not in ("unavailable", "unknown", ""):
            return val
        return None

    def _get_door_state(self, app: ApplianceState, cache: dict) -> Optional[str]:
        """Legge stato porta (solo modalità smart con door_sensor)."""
        eid = app.cfg.get("door_sensor", "")
        if not eid:
            return None
        return cache.get(eid, {}).get("state")

    def _get_energy(self, app: ApplianceState, cache: dict) -> Optional[float]:
        """Stima il consumo del ciclo in kWh (solo se c'è energy_sensor)."""
        eid = app.cfg.get("energy_sensor", "")
        if not eid:
            return None
        val = cache.get(eid, {}).get("state", "")
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    async def _ai_tip(self, app: ApplianceState, duration: str, kwh: Optional[float]) -> Optional[str]:
        """Genera un consiglio AI breve (es. "buon momento per la centrifuga extra")."""
        try:
            kwh_txt = f"{kwh:.2f} kWh" if kwh else "consumo non disponibile"
            tip = await self.ai.ask(
                system="Sei HomeMind. Dai un consiglio breve (1 frase, max 15 parole) e utile dopo un ciclo di elettrodomestico. Sii pratico e conciso. Rispondi in italiano.",
                user=f"{app.name} ha terminato. Durata: {duration}. Consumo: {kwh_txt}.",
                max_tokens=60,
            )
            return tip.strip()[:120]
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Status pubblico (per Telegram /elettrodomestici)

    def status_message(self) -> str:
        """Ritorna lo stato attuale di tutti gli elettrodomestici."""
        if not self._appliances:
            return (
                "🔌 <b>Elettrodomestici</b>\n\n"
                "⚙️ Nessun elettrodomestico configurato.\n\n"
                "Aggiungi la sezione <code>\"appliances\"</code> in:\n"
                "<code>/config/homemind_patches/person_config.json</code>\n\n"
                "Vedi la documentazione per il formato."
            )

        running = [a for a in self._appliances.values() if a.is_running]
        idle    = [a for a in self._appliances.values() if not a.is_running]

        lines = ["🔌 <b>Elettrodomestici</b>", "─" * 20]

        if running:
            lines.append("🔄 <b>In funzione:</b>")
            for app in running:
                dur = app.duration_str()
                lines.append(f"  {app.icon} <b>{app.name}</b> — da {dur}")
            lines.append("")

        if idle:
            lines.append("✅ <b>Fermi:</b>")
            for app in idle:
                lines.append(f"  {app.icon} {app.name}")

        lines.append("─" * 20)
        lines.append(f"<i>🕐 {now_local().strftime('%H:%M')}</i>")
        return "\n".join(lines)

    def is_configured(self) -> bool:
        return bool(self._appliances)

    def get_running_state(self, name: str) -> bool:
        """Ritorna True se l'elettrodomestico con questo nome è in funzione."""
        for app in self._appliances.values():
            if app.name.lower() == name.lower():
                return app.is_running
        return False

    def _log_status(self):
        """Log periodico stato sensori — aiuta a diagnosticare problemi."""
        cache = self._state_cache
        for app in self._appliances.values():
            if app.mode == "power":
                eid = app.cfg.get("power_sensor", "")
                entry = cache.get(eid, {})
                val = entry.get("state", "NON TROVATO")
                logger.info("ApplianceMonitor poll '%s': sensor='%s' value=%r running=%s",
                            app.name, eid, val, app.is_running)
            elif app.mode == "smart":
                eid = app.cfg.get("state_sensor", "")
                entry = cache.get(eid, {})
                val = entry.get("state", "NON TROVATO")
                logger.info("ApplianceMonitor poll '%s': sensor='%s' value=%r running=%s",
                            app.name, eid, val, app.is_running)

    def debug_sensor(self) -> str:
        """Ritorna stato debug di tutti i sensori configurati (per Telegram)."""
        cache = self._state_cache
        if not self._appliances:
            return "🔌 Nessun elettrodomestico configurato."

        lines = ["🔧 <b>Debug Elettrodomestici</b>", "─" * 20]
        for app in self._appliances.values():
            lines.append(f"{app.icon} <b>{app.name}</b> (mode: {app.mode})")
            if app.mode == "power":
                eid = app.cfg.get("power_sensor", "❌ mancante")
                entry = cache.get(eid, {})
                val = entry.get("state", "❌ NON TROVATO in HA")
                on_t  = app.cfg.get("power_on_threshold",  DEFAULT_POWER_ON)
                off_t = app.cfg.get("power_off_threshold", DEFAULT_POWER_OFF)
                lines.append(f"   📡 Sensore: <code>{eid}</code>")
                lines.append(f"   ⚡ Valore attuale: <b>{val} W</b>")
                lines.append(f"   🎚 Soglie: ON≥{on_t}W / OFF≤{off_t}W")
                lines.append(f"   🔄 Stato: {'▶️ In funzione' if app.is_running else '⏹ Fermo'}")
                if val == "❌ NON TROVATO in HA":
                    lines.append("   ⚠️ <i>Sensore non trovato — verifica l'entity_id nel config!</i>")
            elif app.mode == "smart":
                eid = app.cfg.get("state_sensor", "❌ mancante")
                entry = cache.get(eid, {})
                val = entry.get("state", "❌ NON TROVATO in HA")
                lines.append(f"   📡 Sensore: <code>{eid}</code>")
                lines.append(f"   📊 Stato HA: <b>{val}</b>")
                lines.append(f"   🔄 Rilevato: {'▶️ In funzione' if app.is_running else '⏹ Fermo'}")
                if val == "❌ NON TROVATO in HA":
                    lines.append("   ⚠️ <i>Sensore non trovato — verifica l'entity_id nel config!</i>")
            lines.append("")

        lines.append(f"<i>🕐 {now_local().strftime('%H:%M:%S')} · poll ogni {POLL_SECONDS}s</i>")
        return "\n".join(lines)
