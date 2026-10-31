"""
agent/solar_optimizer.py — Ottimizzatore energetico FV in tempo reale.

Funzionamento:
  • Monitora surplus FV ogni 2 minuti (produzione - consumo_casa)
  • Quando c'è surplus sufficiente per X minuti consecutivi → notifica l'utente
  • L'utente risponde "sì" / "avvia lavatrice" via Telegram per autorizzare
  • Se auto_start: true nel config → parte autonomamente (opt-in esplicito)

Configurazione in person_config.json:
  "solar_optimizer": {
    "enabled": true,
    "min_surplus_w": 500,          // surplus minimo per considerare l'avvio (default 500W)
    "confirm_minutes": 5,          // minuti consecutivi di surplus prima di notificare (default 5)
    "cooldown_hours": 2,           // ore minime tra una notifica e l'altra (default 2)
    "appliances": {
      "lavatrice": {
        "enabled": true,
        "switch": "switch.presa_lavatrice",  // opzionale: presa smart da accendere
        "min_surplus_w": 800,                // override soglia per questo elettrodomestico
        "auto_start": false                  // default false — chiede sempre conferma
      },
      "lavastoviglie": {
        "enabled": true,
        "switch": null,
        "auto_start": false
      }
    }
  }
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.solar")

CONFIG_FILE = Path("/config/homemind_patches/person_config.json")


def _load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text()).get("solar_optimizer", {})
    except Exception as e:
        logger.warning("solar_optimizer config load: %s", e)
    return {}


class SolarOptimizer:
    """
    Monitora surplus FV e suggerisce (o avvia automaticamente) elettrodomestici.
    """

    def __init__(self, rest_client, state_cache_cb, notifier=None, appliance_monitor=None):
        self.rest             = rest_client
        self._cache_cb        = state_cache_cb
        self.notifier         = notifier
        self.appliance_monitor = appliance_monitor

        # Stato runtime
        self._surplus_since: float | None = None  # timestamp inizio surplus continuo
        self._kwh_samples: dict = {}               # slot → [(timestamp, kwh), ...]
        self._battery_full_since: float | None = None  # timestamp inizio batteria piena
        self._last_notify_ts: dict = {}            # appliance_name → timestamp ultima notifica
        self._pending_confirm: dict = {}           # appliance_name → {ts, cfg} in attesa risposta
        self._task: asyncio.Task | None = None

    @property
    def _cache(self) -> dict:
        return self._cache_cb() if self._cache_cb else {}

    def is_configured(self) -> bool:
        cfg = _load_config()
        return bool(cfg.get("enabled", False))

    async def start(self):
        if not self.is_configured():
            logger.info("SolarOptimizer: non configurato (solar_optimizer.enabled mancante) — skip")
            return
        self._task = asyncio.create_task(self._monitor_loop(), name="solar_optimizer")
        logger.info("SolarOptimizer avviato — monitoraggio surplus FV ogni 2 min")

    # ─────────────────────────────────────────────────────────────────────────

    async def _monitor_loop(self):
        await asyncio.sleep(30)  # delay iniziale
        while True:
            try:
                await self._check()
            except Exception as e:
                logger.warning("SolarOptimizer errore: %s", e)
            await asyncio.sleep(120)  # check ogni 2 minuti

    async def _check(self):
        cfg = _load_config()
        if not cfg.get("enabled", False):
            return

        now = time.time()
        confirm_min = float(cfg.get("confirm_minutes", 5))

        # ── Modalità batteria piena ──────────────────────────────────────────
        # Quando la batteria è al 100% l'inverter throttla il FV → surplus
        # calcolato = 0W anche se il sole produce molto. Usiamo la SOC come
        # segnale alternativo: batteria piena + FV che produce = energia sprecata.
        battery_surplus = self._get_battery_full_surplus(cfg)
        if battery_surplus is not None:
            if self._battery_full_since is None:
                self._battery_full_since = now
                logger.info("SolarOptimizer: batteria piena + FV attivo (%.0fW disponibili) — avvio timer", battery_surplus)
            elapsed_min = (now - self._battery_full_since) / 60
            if elapsed_min >= confirm_min:
                logger.info("SolarOptimizer: batteria piena per %.0f min — suggerisco elettrodomestici", elapsed_min)
                await self._evaluate_appliances(cfg, battery_surplus, elapsed_min, mode="battery_full")
            # Reset surplus normale — non confondere i due timer
            self._surplus_since = None
            return
        else:
            if self._battery_full_since is not None:
                logger.info("SolarOptimizer: batteria non più piena / FV insufficiente — reset")
            self._battery_full_since = None

        # ── Modalità surplus normale ─────────────────────────────────────────
        surplus_w = self._get_surplus_w(cfg)
        if surplus_w is None:
            logger.debug("SolarOptimizer: sensori FV non disponibili")
            return

        min_surplus = float(cfg.get("min_surplus_w", 500))
        logger.debug("SolarOptimizer: surplus=%.0fW (soglia %.0fW)", surplus_w, min_surplus)

        if surplus_w >= min_surplus:
            if self._surplus_since is None:
                self._surplus_since = now
                logger.info("SolarOptimizer: surplus iniziato (%.0fW)", surplus_w)
            elapsed_min = (now - self._surplus_since) / 60
            if elapsed_min >= confirm_min:
                await self._evaluate_appliances(cfg, surplus_w, elapsed_min)
        else:
            if self._surplus_since is not None:
                elapsed = (now - self._surplus_since) / 60
                logger.info("SolarOptimizer: surplus terminato dopo %.0f min (%.0fW < %.0fW)",
                            elapsed, surplus_w, min_surplus)
            self._surplus_since = None

    def _get_sun_elevation(self) -> float | None:
        """Legge l'elevazione solare da sun.sun (gradi sull'orizzonte)."""
        try:
            state = self._cache.get("sun.sun", {})
            elev = state.get("attributes", {}).get("elevation")
            if elev is not None:
                return float(elev)
        except (ValueError, TypeError):
            pass
        return None

    def _get_battery_full_surplus(self, cfg: dict) -> float | None:
        """
        Ritorna la potenza FV disponibile se:
          - batteria SOC >= battery_full_threshold (default 95%)
          - FV sta producendo >= battery_full_min_fv_w (default 300W)
          - Sole sufficientemente alto (elevation > min_sun_elevation, default 10°)
        Ritorna None se la condizione non è soddisfatta o i sensori mancano.
        """
        soc_eid = cfg.get("battery_soc_sensor", "")
        if not soc_eid:
            return None  # funzione non configurata

        # ── Controllo elevazione solare ──────────────────────────────────────
        # Evita notifiche serali quando la batteria è ancora carica
        # ma il sole è tramontato o quasi (non produce più nulla di utile)
        min_elevation = float(cfg.get("min_sun_elevation", 10))
        elevation = self._get_sun_elevation()
        if elevation is not None:
            if elevation < min_elevation:
                logger.debug(
                    "SolarOptimizer [battery_full]: sole troppo basso (%.1f° < %.1f°) — skip",
                    elevation, min_elevation
                )
                return None
        else:
            # sun.sun non disponibile — usa fallback orario (6:00-20:00)
            from utils.timezone_helper import now_local
            hour = now_local().hour
            if not (6 <= hour <= 20):
                logger.debug("SolarOptimizer [battery_full]: fuori orario solare — skip")
                return None

        cache = self._cache
        # Leggi SOC batteria
        try:
            soc = float(cache.get(soc_eid, {}).get("state", ""))
        except (ValueError, TypeError):
            return None

        threshold = float(cfg.get("battery_full_threshold", 95))
        if soc < threshold:
            return None  # batteria non abbastanza carica

        # Leggi produzione FV attuale
        try:
            raw_cfg = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
            energy_cfg = raw_cfg.get("energy_sensors", {})
        except Exception:
            energy_cfg = {}

        fv_w_eid = energy_cfg.get("produzione_fv_w", "")
        fv_w = None
        if fv_w_eid and fv_w_eid in cache:
            try:
                fv_w = float(cache[fv_w_eid].get("state", ""))
            except (ValueError, TypeError):
                pass

        if fv_w is None:
            return None

        min_fv = float(cfg.get("battery_full_min_fv_w", 300))
        if fv_w < min_fv:
            return None  # sole troppo debole

        elev_str = f"{elevation:.1f}°" if elevation is not None else "n/d"
        logger.debug(
            "SolarOptimizer [battery_full]: SOC=%.0f%% FV=%.0fW elevazione=%s",
            soc, fv_w, elev_str
        )
        return fv_w  # disponibile

    def _get_surplus_w(self, cfg: dict) -> float | None:
        """Calcola surplus FV: produzione - consumo_casa in Watt.

        Priorità:
          1. Sensori W istantanei (produzione_fv_w / consumo_casa_w) — più precisi
          2. Derivata da kWh giornalieri: ΔkWh / Δt → W  — funziona con sensori standard
        """
        cache = self._cache
        now   = time.time()

        try:
            raw_cfg    = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
            energy_cfg = raw_cfg.get("energy_sensors", {})
        except Exception:
            energy_cfg = {}

        fv_eid        = energy_cfg.get("produzione_fv",   "sensor.fv_tot")
        consumo_eid   = energy_cfg.get("consumo_casa",    "sensor.daily_energy_combined")
        fv_w_eid      = energy_cfg.get("produzione_fv_w", "")
        consumo_w_eid = energy_cfg.get("consumo_casa_w",  "")
        enel_w_eid    = energy_cfg.get("rete_enel_w",     "")

        def _read_w_direct(eid):
            """Legge Watt istantanei da sensore W."""
            if eid and eid in cache:
                try:
                    return float(cache[eid].get("state", ""))
                except (ValueError, TypeError):
                    pass
            return None

        def _read_kwh(eid):
            """Legge valore kWh attuale."""
            if eid in cache:
                try:
                    return float(cache[eid].get("state", ""))
                except (ValueError, TypeError):
                    pass
            return None

        def _kwh_to_w(eid, slot: str) -> float | None:
            """
            Converte kWh giornaliero → Watt usando la derivata:
              W = (kWh_now - kWh_prev) / (Δt_ore) * 1000
            Mantiene lo storico in self._kwh_samples[slot].
            Richiede almeno 2 letture a distanza di 1-5 min per essere affidabile.
            """
            kwh_now = _read_kwh(eid)
            if kwh_now is None:
                return None

            samples = self._kwh_samples.setdefault(slot, [])
            # Aggiungi campione corrente
            samples.append((now, kwh_now))
            # Tieni solo gli ultimi 10 min di campioni
            samples[:] = [(t, v) for t, v in samples if now - t < 600]

            if len(samples) < 2:
                return None  # troppo pochi dati

            # Usa il campione più vecchio disponibile (massima finestra per precisione)
            t_old, kwh_old = samples[0]
            delta_h = (now - t_old) / 3600
            if delta_h < 0.005:  # meno di 18 secondi — troppo poco
                return None

            delta_kwh = kwh_now - kwh_old
            # Gestione reset contatore giornaliero (mezzanotte)
            if delta_kwh < -0.5:
                self._kwh_samples[slot] = [(now, kwh_now)]
                return None

            watts = (delta_kwh / delta_h) * 1000
            return max(0.0, watts)  # non può essere negativo

        # ── Calcola FV (W) ──────────────────────────────────────────────────
        fv_w = _read_w_direct(fv_w_eid)
        if fv_w is None:
            fv_w = _kwh_to_w(fv_eid, "fv")

        # ── Calcola Consumo (W) ─────────────────────────────────────────────
        consumo_w = _read_w_direct(consumo_w_eid)
        if consumo_w is None:
            consumo_w = _kwh_to_w(consumo_eid, "consumo")

        if fv_w is None or consumo_w is None:
            logger.debug("SolarOptimizer: dati insufficienti — fv=%s consumo=%s", fv_w, consumo_w)
            return None

        surplus = fv_w - consumo_w

        # Shelly disponibile solo per log diagnostico — non influenza il calcolo
        enel_w = _read_w_direct(enel_w_eid)
        if enel_w is not None:
            logger.debug("SolarOptimizer: fv=%.0fW consumo=%.0fW surplus=%.0fW enel(rete)=%.0fW",
                         fv_w, consumo_w, surplus, enel_w)
        else:
            logger.debug("SolarOptimizer: fv=%.0fW consumo=%.0fW surplus=%.0fW", fv_w, consumo_w, surplus)

        return surplus

    async def _evaluate_appliances(self, cfg: dict, surplus_w: float, elapsed_min: float, mode: str = "surplus"):
        """Valuta quali elettrodomestici suggerire/avviare."""
        appliances_cfg = cfg.get("appliances", {})
        cooldown_h = float(cfg.get("cooldown_hours", 2))
        now = time.time()

        for name, app_cfg in appliances_cfg.items():
            if not app_cfg.get("enabled", True):
                continue

            # Controlla se è già in funzione
            if self.appliance_monitor:
                status = self.appliance_monitor.get_running_state(name)
                if status:
                    logger.debug("SolarOptimizer: %s già in funzione — skip", name)
                    continue

            # Controlla cooldown notifica
            last = self._last_notify_ts.get(name, 0)
            if now - last < cooldown_h * 3600:
                continue

            # Controlla surplus minimo specifico per questo elettrodomestico
            app_min = float(app_cfg.get("min_surplus_w", cfg.get("min_surplus_w", 500)))
            if surplus_w < app_min:
                continue

            auto_start = app_cfg.get("auto_start", False)
            switch_eid = app_cfg.get("switch", None)

            if auto_start and switch_eid:
                # Auto-avvio — agisce direttamente
                await self._auto_start(name, switch_eid, surplus_w, elapsed_min)
            else:
                # Suggerimento — notifica e attende conferma
                await self._suggest(name, app_cfg, surplus_w, elapsed_min, mode=mode)

            self._last_notify_ts[name] = now

    async def _suggest(self, name: str, app_cfg: dict, surplus_w: float, elapsed_min: float, mode: str = "surplus"):
        """Invia notifica di suggerimento all'utente."""
        ora = now_local().strftime("%H:%M")
        nome_display = name.capitalize()
        elapsed_str = f"{elapsed_min:.0f} min" if elapsed_min < 60 else f"{elapsed_min/60:.1f}h"

        if mode == "battery_full":
            msg = (
                f"🔋☀️ <b>Batteria carica — energia solare disponibile!</b>\n\n"
                f"La batteria è al massimo e il sole sta producendo <b>{surplus_w:.0f}W</b> "
                f"che altrimenti andrebbero sprecati.\n"
                f"Buon momento per avviare la <b>{nome_display}</b>.\n\n"
                f"Rispondi <b>sì</b> o <b>avvia {name}</b> per confermare"
            )
        else:
            msg = (
                f"☀️ <b>Surplus solare disponibile!</b>\n\n"
                f"Hai <b>{surplus_w:.0f}W</b> di surplus da {elapsed_str} "
                f"— buon momento per avviare la <b>{nome_display}</b>.\n\n"
                f"Rispondi <b>sì</b> o <b>avvia {name}</b> per confermare"
            )

        if app_cfg.get("switch"):
            msg += f", oppure lo avvio io accendendo la presa."
        else:
            msg += "."

        self._pending_confirm[name] = {
            "ts": time.time(),
            "cfg": app_cfg,
            "surplus_w": surplus_w
        }

        logger.info("SolarOptimizer: suggerisco %s (surplus=%.0fW, elapsed=%.0f min)",
                    name, surplus_w, elapsed_min)

        if self.notifier:
            await self.notifier.send_html(msg)

    async def _auto_start(self, name: str, switch_eid: str, surplus_w: float, elapsed_min: float):
        """Avvia autonomamente l'elettrodomestico (solo se auto_start: true)."""
        ora = now_local().strftime("%H:%M")
        nome_display = name.capitalize()

        logger.info("SolarOptimizer: auto-avvio %s (switch=%s, surplus=%.0fW)",
                    name, switch_eid, surplus_w)
        try:
            await self.rest.call_service(
                "switch", "turn_on", {},
                target={"entity_id": switch_eid}
            )
            msg = (
                f"☀️ <b>{nome_display} avviata automaticamente</b>\n\n"
                f"Surplus solare: <b>{surplus_w:.0f}W</b> — ho acceso la presa alle {ora}."
            )
            if self.notifier:
                await self.notifier.send_html(msg)
        except Exception as e:
            logger.warning("SolarOptimizer: auto-avvio %s FAIL: %s", name, e)

    async def handle_confirm(self, text: str) -> bool:
        """
        Chiamato dal TelegramBot quando l'utente risponde.
        Ritorna True se ha gestito il messaggio (era una conferma).
        """
        text_lower = text.lower().strip()

        # Cerca match con pending confirms
        for name, pending in list(self._pending_confirm.items()):
            # Timeout conferma: 30 minuti
            if time.time() - pending["ts"] > 1800:
                del self._pending_confirm[name]
                continue

            # Solo risposte esplicite positive — MAI il nome dell'elettrodomestico da solo
            is_confirm = text_lower in (
                "sì", "si", "yes", "ok", "avvia", "avvio",
                "vai", "confermo", "conferma", "procedi", "start"
            )
            if not is_confirm:
                continue

            app_cfg   = pending["cfg"]
            switch_eid = app_cfg.get("switch")
            del self._pending_confirm[name]

            if switch_eid:
                try:
                    await self.rest.call_service(
                        "switch", "turn_on", {},
                        target={"entity_id": switch_eid}
                    )
                    msg = f"☀️ <b>{name.capitalize()} avviata!</b> Ho acceso la presa."
                except Exception as e:
                    msg = f"⚠️ Non riesco ad accendere la presa: {e}"
            else:
                msg = (f"☀️ Ok! Ricordati di avviare la <b>{name.capitalize()}</b> — "
                       f"il surplus solare è ancora disponibile.")

            if self.notifier:
                await self.notifier.send_html(msg)

            logger.info("SolarOptimizer: conferma ricevuta per %s", name)
            return True

        return False

    def get_status_message(self) -> str:
        """Testo per comando /solare."""
        cfg = _load_config()
        if not cfg.get("enabled", False):
            return "☀️ Ottimizzatore solare non configurato."

        surplus_w = self._get_surplus_w(cfg)
        ora       = now_local().strftime("%H:%M")
        lines     = [f"☀️ <b>Ottimizzatore Solare</b> — {ora}\n"]

        # Stato batteria
        soc_eid = cfg.get("battery_soc_sensor", "")
        if soc_eid:
            cache = self._cache
            try:
                soc = float(cache.get(soc_eid, {}).get("state", ""))
                threshold = float(cfg.get("battery_full_threshold", 95))
                soc_icon = "🔋" if soc >= threshold else "🪫"
                lines.append(f"{soc_icon} Batteria: <b>{soc:.0f}%</b>"
                             + (" — PIENA ⚡" if soc >= threshold else ""))
            except (ValueError, TypeError):
                lines.append("🔋 Batteria: n/d")

        if surplus_w is None:
            lines.append("⚠️ Sensori FV non disponibili.")
        elif surplus_w > 0:
            lines.append(f"⚡ Surplus attuale: <b>{surplus_w:.0f}W</b>")
            if self._surplus_since:
                elapsed = (time.time() - self._surplus_since) / 60
                lines.append(f"⏱ Attivo da: {elapsed:.0f} min")
            if self._battery_full_since:
                elapsed = (time.time() - self._battery_full_since) / 60
                lines.append(f"⏱ Batteria piena da: {elapsed:.0f} min")
        else:
            lines.append(f"📊 Consumo in eccesso: {abs(surplus_w):.0f}W")

        # Pending confirms
        if self._pending_confirm:
            lines.append("\n⏳ In attesa conferma:")
            for name in self._pending_confirm:
                lines.append(f"  • {name.capitalize()} — rispondi <b>avvia {name}</b>")

        # Elettrodomestici configurati
        appliances = cfg.get("appliances", {})
        if appliances:
            lines.append("\n📋 Elettrodomestici:")
            for name, app_cfg in appliances.items():
                enabled   = app_cfg.get("enabled", True)
                auto      = app_cfg.get("auto_start", False)
                min_w     = app_cfg.get("min_surplus_w", cfg.get("min_surplus_w", 500))
                stato     = "✅" if enabled else "❌"
                modalita  = "auto" if auto else "suggerimento"
                lines.append(f"  {stato} {name.capitalize()} — {modalita}, soglia {min_w}W")

        return "\n".join(lines)
