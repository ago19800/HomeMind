"""
agent/history_client.py — Statistiche e storico energetico da HA.
Risponde a domande tipo "quanta energia ho prodotto ieri?"
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger("homemind.history")

CONFIG_FILE = Path("/config/homemind_patches/person_config.json")

# Mapping sensori energia — candidati in ordine di priorità
# L'utente può sovrascriverli in person_config.json → "energy_sensors": {...}
DEFAULT_ENERGY_SENSORS = {
    "produzione_fv":  [
        "sensor.fv_tot1", "sensor.fotovoltaica_totale", "sensor.fv_tot",
        "sensor.energy_production_today", "sensor.solare_oggi",
        "sensor.inverter_energy_today", "sensor.pv_energy_today",
    ],
    "consumo_casa": [
        "sensor.consumi_casa", "sensor.daily_energy_combined",
        "sensor.consumo_oggi", "sensor.energy_consumption_today",
        "sensor.home_energy_today",
    ],
    "rete_enel": [
        "sensor.enel_giorno", "sensor.enel", "sensor.grid_import_today",
        "sensor.energia_rete_oggi", "sensor.prelievo_oggi",
    ],
    "batteria_wh": [
        "sensor.batteria_voltage", "sensor.battery_energy_today",
        "sensor.batteria_oggi", "sensor.battery_charge_today",
    ],
}


def _load_energy_sensors(state_cache: dict) -> dict:
    """
    Carica entity_id da person_config.json se presenti,
    altrimenti usa i DEFAULT. Poi verifica quali esistono davvero in state_cache.
    """
    sensors = {k: list(v) for k, v in DEFAULT_ENERGY_SENSORS.items()}
    try:
        if CONFIG_FILE.exists():
            cfg = json.loads(CONFIG_FILE.read_text())
            overrides = cfg.get("energy_sensors", {})
            for cat, eids in overrides.items():
                if isinstance(eids, str):
                    eids = [eids]
                if cat in sensors:
                    sensors[cat] = eids + sensors[cat]  # override ha priorità
                else:
                    sensors[cat] = eids
    except Exception as e:
        logger.warning("energy_sensors config load: %s", e)
    return sensors


class HistoryClient:
    def __init__(self, rest_client, state_cache_cb):
        """
        state_cache_cb: callable () → dict  (per avere sempre lo stato aggiornato)
        """
        self.rest         = rest_client
        self._cache_cb    = state_cache_cb

    @property
    def state_cache(self) -> dict:
        return self._cache_cb()

    async def energy_summary(self, period: str = "oggi") -> str:
        """
        'oggi': valore attuale (sensori daily resettati a mezzanotte).
        'ieri': delta tramite History API con correzione UTC→locale.
        """
        state_cache = self.state_cache
        ENERGY_SENSORS = _load_energy_sensors(state_cache)

        icons  = {"produzione_fv": "☀️", "consumo_casa": "🏠",
                  "rete_enel": "🔌", "batteria_wh": "🔋"}
        labels = {"produzione_fv": "Produzione FV", "consumo_casa": "Consumo casa",
                  "rete_enel": "Da rete (Enel)", "batteria_wh": "Batteria"}

        # ── Trova sensori presenti in state_cache ─────────────────────────
        available = {}
        for category, candidates in ENERGY_SENSORS.items():
            for eid in candidates:
                if eid in state_cache:
                    st = state_cache[eid].get("state", "")
                    if st not in ("unavailable", "unknown", ""):
                        available[category] = eid
                        logger.info("energy_sensors: %s → %s = %s", category, eid, st)
                        break

        if not available:
            # Fallback automatico: cerca sensori kWh daily noti per nomi
            daily_kws = ("oggi", "today", "giornaliero", "daily", "solare", "solar",
                         "enel", "grid", "consumo", "consumption", "batteria", "battery")
            for eid, s in state_cache.items():
                attrs = s.get("attributes", {})
                if attrs.get("unit_of_measurement") == "kWh":
                    eid_low = eid.lower()
                    if any(k in eid_low for k in daily_kws):
                        # Categorizza per nome
                        if any(k in eid_low for k in ("solare","solar","fv","pv","produz")):
                            available.setdefault("produzione_fv", eid)
                        elif any(k in eid_low for k in ("consumo","consumption","casa","home")):
                            available.setdefault("consumo_casa", eid)
                        elif any(k in eid_low for k in ("enel","grid","rete","prelievo","import")):
                            available.setdefault("rete_enel", eid)
                        elif any(k in eid_low for k in ("batteria","battery")):
                            available.setdefault("batteria_wh", eid)
            if available:
                logger.info("energy_sensors fallback automatico: %s", available)

        if not available:
            eids_hint = [e for e in state_cache if "kwh" in e.lower() or
                         state_cache[e].get("attributes",{}).get("unit_of_measurement","") == "kWh"][:5]
            return (
                "⚡ <b>Energia</b>\n\n"
                "❌ Nessun sensore energia trovato.\n\n"
                "<b>Aggiungi in person_config.json:</b>\n"
                '<code>"energy_sensors": {\n'
                '  \"produzione_fv\": \"sensor.ENTITY_FV\",\n'
                '  \"consumo_casa\": \"sensor.ENTITY_CONSUMO\"\n'
                '}</code>\n\n'
                + (f"<i>Sensori kWh trovati: {', '.join(eids_hint)}</i>" if eids_hint else "")
            )

        lines  = [f"⚡ <b>Energia — {period.capitalize()}</b>", "─" * 18]
        values = {}

        if period.lower() == "ieri":
            # ── IERI: calcola delta via History API con correzione UTC ────
            from datetime import date
            # HA salva timestamps in UTC — convertiamo per trovare "ieri locale"
            try:
                local_tz = datetime.now().astimezone().tzinfo
            except Exception:
                local_tz = timezone(timedelta(hours=1))  # CET fallback

            ieri_local = datetime.now(local_tz).date() - timedelta(days=1)
            logger.info("energy_summary ieri: cerco dati per %s (locale)", ieri_local)

            try:
                history = await self.rest.get_history(list(available.values()), hours=50)
                found_any = False
                for cat, eid in available.items():
                    series   = history.get(eid, [])
                    day_vals = []
                    for entry in series:
                        ts_raw = entry.get("last_changed", entry.get("last_updated", ""))
                        if not ts_raw:
                            continue
                        # Parse timestamp UTC e converti a locale
                        try:
                            if ts_raw.endswith("Z"):
                                ts_raw = ts_raw[:-1] + "+00:00"
                            ts_utc  = datetime.fromisoformat(ts_raw)
                            ts_loc  = ts_utc.astimezone(local_tz)
                            if ts_loc.date() == ieri_local:
                                v = float(entry.get("state", ""))
                                day_vals.append((ts_loc, v))
                        except (ValueError, TypeError):
                            pass

                    unit = state_cache[eid].get("attributes", {}).get("unit_of_measurement", "kWh")
                    icon = icons.get(cat, "📊")
                    lbl  = labels.get(cat, cat)
                    logger.info("energy ieri %s: %d campioni trovati", eid, len(day_vals))

                    if len(day_vals) >= 2:
                        found_any = True
                        day_vals.sort(key=lambda x: x[0])
                        v_start = day_vals[0][1]
                        v_end   = day_vals[-1][1]
                        v_max   = max(v for _, v in day_vals)
                        delta   = v_end - v_start
                        if delta < 0:
                            # Sensore si è resettato a mezzanotte → usa il massimo
                            delta = v_max
                        elif v_start < 1.0:
                            # Sensore daily (parte da 0) → il massimo è il totale del giorno
                            delta = v_max
                        values[cat] = round(delta, 2)
                        lines.append(f"{icon} <b>{lbl}:</b> {delta:.2f} {unit}")
                    elif len(day_vals) == 1:
                        found_any = True
                        v = day_vals[0][1]
                        values[cat] = v
                        lines.append(f"{icon} <b>{lbl}:</b> {v:.2f} {unit} <i>(1 campione)</i>")
                    else:
                        lines.append(f"{icon} <b>{lbl}:</b> <i>nessun dato</i>")

                if not found_any:
                    lines.append(
                        "\n⚠️ <i>History API non ha restituito dati per ieri.\n"
                        "Possibili cause:\n"
                        "• I sensori si resettano a mezzanotte (già azzerati)\n"
                        "• HA Recorder non registra questi sensori\n"
                        "• Entity_id errati — configura energy_sensors in person_config.json</i>"
                    )
            except Exception as e:
                logger.warning("energy_summary ieri error: %s", e)
                lines.append(f"❌ Errore History API: {e}")
        else:
            # ── OGGI / default: valore attuale ───────────────────────────
            for cat, eid in available.items():
                s    = state_cache.get(eid, {})
                v    = s.get("state", "?")
                u    = s.get("attributes", {}).get("unit_of_measurement", "")
                icon = icons.get(cat, "📊")
                lbl  = labels.get(cat, cat)
                try:
                    fv = float(v)
                    values[cat] = fv
                    lines.append(f"{icon} <b>{lbl}:</b> {fv:.2f} {u}".strip())
                except (ValueError, TypeError):
                    lines.append(f"{icon} <b>{lbl}:</b> {v} {u}".strip())

        # Autosufficienza
        if "produzione_fv" in values and "consumo_casa" in values:
            try:
                fv  = values["produzione_fv"]
                con = values["consumo_casa"]
                if con > 0:
                    perc = min(100, round(fv / con * 100))
                    bar  = "█" * (perc // 10) + "░" * (10 - perc // 10)
                    lines.append(f"\n📊 <b>Autosufficienza:</b> {perc}%")
                    lines.append(f"   {bar}")
            except Exception:
                pass

        lines.append("─" * 18)
        lines.append(f"🕐 <i>Aggiornato: {datetime.now().strftime('%H:%M:%S')}</i>")
        return "\n".join(lines)


    async def sensor_history_summary(self, entity_id: str, hours: int = 24) -> str:
        """Statistiche min/max/media per un sensore nelle ultime N ore."""
        history = await self.rest.get_history([entity_id], hours=hours)
        points  = history.get(entity_id, [])

        if not points:
            return f"❌ Nessun dato storico per <code>{entity_id}</code> nelle ultime {hours}h."

        values = []
        for p in points:
            try: values.append(float(p.get("state", "")))
            except: pass

        if not values:
            return f"❌ Nessun valore numerico per <code>{entity_id}</code>."

        s    = self.state_cache.get(entity_id, {})
        name = s.get("attributes", {}).get("friendly_name", entity_id)
        unit = s.get("attributes", {}).get("unit_of_measurement", "")

        mn  = min(values)
        mx  = max(values)
        avg = sum(values) / len(values)
        cur = values[-1]

        return (
            f"📈 <b>{name}</b>\n"
            f"──────────────────\n"
            f"⬇️ Minimo:  {mn:.2f} {unit}\n"
            f"⬆️ Massimo: {mx:.2f} {unit}\n"
            f"📊 Media:   {avg:.2f} {unit}\n"
            f"🔵 Attuale: {cur:.2f} {unit}\n"
            f"──────────────────\n"
            f"🕐 <i>Ultime {hours} ore — {len(values)} campioni</i>"
        )

    async def quick_stats(self, state_cache: dict) -> str:
        """Snapshot rapido dei sensori più importanti."""
        lines = ["📊 <b>Statistiche Casa</b>", "──────────────────"]

        # Temperatura
        temps = []
        for eid, s in state_cache.items():
            if s.get("attributes", {}).get("device_class") == "temperature":
                v = s.get("state", "")
                try:
                    name = s.get("attributes", {}).get("friendly_name", eid)
                    if "cpu" not in name.lower() and "proxmox" not in name.lower():
                        temps.append((name, float(v)))
                except: pass
        if temps:
            lines.append("🌡️ <b>Temperature:</b>")
            for name, v in sorted(temps, key=lambda x: x[1], reverse=True)[:5]:
                lines.append(f"  {name}: {v:.1f}°C")

        # Luci accese
        lights_on = [(eid, s) for eid, s in state_cache.items()
                     if eid.startswith("light.") and s.get("state") == "on"]
        if lights_on:
            names = [s.get("attributes", {}).get("friendly_name", e) for e, s in lights_on[:8]]
            lines.append(f"\n💡 <b>Luci accese ({len(lights_on)}):</b>")
            lines.append("  " + ", ".join(names))

        # Consumo istantaneo
        for eid in ["sensor.inverter_pipsolar_ac_output_active_power", "sensor.consumi_casa"]:
            if eid in state_cache:
                v = state_cache[eid].get("state", "")
                try:
                    lines.append(f"\n🏠 <b>Consumo:</b> {float(v):.0f} W")
                    break
                except: pass

        lines.append("──────────────────")
        return "\n".join(lines)
