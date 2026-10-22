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
    Priorità batteria: energy_sensors > solar_optimizer.battery_soc_sensor > default
    """
    sensors = {k: list(v) for k, v in DEFAULT_ENERGY_SENSORS.items()}
    try:
        if CONFIG_FILE.exists():
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
            overrides = cfg.get("energy_sensors", {})
            for cat, eids in overrides.items():
                if isinstance(eids, str):
                    eids = [eids]
                if cat in sensors:
                    sensors[cat] = eids + sensors[cat]  # override ha priorità
                else:
                    sensors[cat] = eids
            # battery_soc_sensor da solar_optimizer ha priorità su default
            # ma solo se non già specificato in energy_sensors
            if "batteria_wh" not in overrides:
                batt_eid = cfg.get("solar_optimizer", {}).get("battery_soc_sensor", "")
                if batt_eid:
                    sensors["batteria_wh"] = [batt_eid] + sensors.get("batteria_wh", [])
                    logger.info("energy_sensors: batteria_wh da solar_optimizer → %s", batt_eid)
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
            # Per sensori cumulativi FV (valore > 1000 kWh), calcola produzione oggi
            # come delta rispetto al valore di mezzanotte
            fv_oggi_delta = None
            if "produzione_fv" in available:
                fv_eid = available["produzione_fv"]
                fv_raw = state_cache.get(fv_eid, {}).get("state", "")
                try:
                    fv_now = float(fv_raw)
                    if fv_now > 1000:  # sensore cumulativo (es. totale kwh da installazione)
                        # Cerca baseline: valore a mezzanotte o ultimo valore di ieri
                        # hours=26 per coprire sempre mezzanotte + margine DST
                        try:
                            from utils.timezone_helper import local_tz as _ltz
                            _tz_l = _ltz()
                            hist_fv = await self.rest.get_history([fv_eid], hours=26)
                            entries_fv = hist_fv.get(fv_eid, [])
                            today_local = datetime.now(_tz_l).date()
                            from datetime import timedelta as _td
                            ieri_local  = today_local - _td(days=1)
                            today_vals = []
                            ieri_vals  = []
                            for e in entries_fv:
                                ts_r = e.get("last_changed", "")
                                try:
                                    ts_dt = datetime.fromisoformat(ts_r.replace("Z","+00:00"))
                                    ts_loc = ts_dt.astimezone(_tz_l)
                                    v_f = float(e.get("state", "nan"))
                                    if ts_loc.date() == today_local:
                                        today_vals.append(v_f)
                                    elif ts_loc.date() == ieri_local:
                                        ieri_vals.append(v_f)
                                except Exception:
                                    pass
                            # Baseline: primo valore di oggi, oppure ultimo di ieri
                            # (di notte today_vals è vuoto perché FV non produce)
                            if today_vals:
                                baseline = min(today_vals)
                                logger.info("FV oggi baseline da today_vals: %.2f (%d campioni)", baseline, len(today_vals))
                            elif ieri_vals:
                                baseline = max(ieri_vals)  # ultimo valore di ieri = inizio di oggi
                                logger.info("FV oggi baseline da ieri_max: %.2f (notte, %d campioni ieri)", baseline, len(ieri_vals))
                            else:
                                baseline = None
                                logger.info("FV oggi: nessuna baseline trovata (sensore fermo?)")
                            if baseline is not None:
                                delta = round(fv_now - baseline, 2)
                                fv_oggi_delta = max(0.0, delta)  # mai negativo
                                logger.info("FV oggi delta: %.2f - %.2f = %.2f kWh", fv_now, baseline, fv_oggi_delta)
                        except Exception as _fe:
                            logger.warning("FV oggi delta error: %s", _fe)
                except (ValueError, TypeError):
                    pass

            for cat, eid in available.items():
                s    = state_cache.get(eid, {})
                v    = s.get("state", "?")
                u    = s.get("attributes", {}).get("unit_of_measurement", "")
                icon = icons.get(cat, "📊")
                lbl  = labels.get(cat, cat)
                try:
                    fv = float(v)
                    # Per FV cumulativo usa il delta di oggi
                    if cat == "produzione_fv" and fv_oggi_delta is not None:
                        values[cat] = fv_oggi_delta
                        lines.append(f"{icon} <b>{lbl}:</b> {fv_oggi_delta:.2f} kWh <i>(oggi)</i>")
                    elif cat == "batteria_wh" and u in ("V", "v", "Volt"):
                        # Sensore tensione configurato come batteria — mostra V non kWh
                        values[cat] = fv
                        lines.append(f"🔋 <b>{lbl}:</b> {fv:.1f} V ⚠️ <i>(tensione, non SOC%)</i>")
                    elif cat == "batteria_wh" and u == "%":
                        # SOC in percentuale — mostra con barra
                        values[cat] = fv
                        bar_soc = "█" * int(fv // 10) + "░" * (10 - int(fv // 10))
                        lines.append(f"🔋 <b>{lbl}:</b> {fv:.0f}%  {bar_soc}")
                    else:
                        values[cat] = fv
                        lines.append(f"{icon} <b>{lbl}:</b> {fv:.2f} {u}".strip())
                except (ValueError, TypeError):
                    lines.append(f"{icon} <b>{lbl}:</b> {v} {u}".strip())

            # Batteria % da solar_optimizer se non in energy_sensors
            if "batteria_wh" not in available:
                try:
                    from pathlib import Path as _Path
                    import json as _json
                    _cfg_p = _Path("/config/homemind_patches/person_config.json")
                    if _cfg_p.exists():
                        _cfg = _json.loads(_cfg_p.read_text(encoding="utf-8-sig"))
                        _batt_eid = _cfg.get("solar_optimizer", {}).get("battery_soc_sensor", "")
                        if _batt_eid and _batt_eid in state_cache:
                            _batt_st = state_cache[_batt_eid].get("state", "")
                            _batt_u  = state_cache[_batt_eid].get("attributes", {}).get("unit_of_measurement", "%")
                            _batt_v  = float(_batt_st)
                            values["batteria_wh"] = _batt_v
                            bar_b = "█" * int(_batt_v // 10) + "░" * (10 - int(_batt_v // 10))
                            lines.append(f"🔋 <b>Batteria:</b> {_batt_v:.0f}{_batt_u}  {bar_b}")
                except Exception:
                    pass

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


    async def energy_by_fascia(self, period: str = "oggi", person_name: str = "Agostino") -> str:
        """
        Consumi Enel per fascia oraria F1/F2/F3.

        Legge i sensori configurati in person_config.json → "fascia_sensors":
          oggi_f1, oggi_f2, oggi_f3, oggi_tot
          mese_f1, mese_f2, mese_f3, mese_tot
          daily_source   → sensore kWh daily per History API (N giorni/ieri)

        Per periodi multi-giorno usa History API sul daily_source.
        """
        import re as _re
        state_cache = self.state_cache
        t_low = period.lower().strip()

        def _val(eid: str) -> float:
            st = state_cache.get(eid, {}).get("state", "")
            if st in ("unavailable", "unknown", "", None):
                return -1.0
            try:
                return float(st)
            except (ValueError, TypeError):
                return -1.0

        # ── Carica configurazione sensori fascia da person_config.json ───────
        fascia_cfg = {}
        try:
            if CONFIG_FILE.exists():
                _cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
                fascia_cfg = _cfg.get("fascia_sensors", {})
        except Exception as e:
            logger.warning("energy_by_fascia: errore lettura fascia_sensors: %s", e)

        def _fs(key: str, *defaults) -> str:
            """Cerca sensore: prima in fascia_cfg, poi nei default, ritorna il primo valido."""
            candidates = [fascia_cfg.get(key, "")] + list(defaults)
            for c in candidates:
                if c and _val(c) >= 0:
                    return c
            return ""

        # Helper: costruisce risposta fascia standard
        def _build_response(label: str, f1: float, f2: float, f3: float,
                             tot: float, fonte: str, fascia_corrente: str = "") -> str:
            def _mark(f): return " ◀ fascia attuale" if fascia_corrente == f else ""
            return (
                f"Ciao {person_name}, ecco i tuoi consumi dalla rete Enel\n"
                f"per il periodo <b>{label}</b> suddivisi per fascia ARERA:\n\n"
                f"ℹ️ Fascia F1 (lun-ven 08:00–19:00): <b>{f1:.2f} kWh</b>{_mark('F1')}\n"
                f"ℹ️ Fascia F2 (lun-sab 07:00–08:00/19:00–23:00): <b>{f2:.2f} kWh</b>{_mark('F2')}\n"
                f"ℹ️ Fascia F3 (notti + dom + festivi): <b>{f3:.2f} kWh</b>{_mark('F3')}\n\n"
                f"⚡ Totale {label}: <b>{tot:.2f} kWh</b>\n\n"
                f"<i>📊 Fonte: {fonte}</i>"
            )

        fascia_corrente = state_cache.get("sensor.fascia_oraria_attuale", {}).get("state", "")

        # ── OGGI ─────────────────────────────────────────────────────────────
        if "oggi" in t_low and "ieri" not in t_low:
            f1_eid = _fs("oggi_f1",
                         "sensor.energia_oggi_f1_f1", "sensor.energia_oggi_f1_F1",
                         "sensor.energia_oggi_f1_fascia_f1")
            f2_eid = _fs("oggi_f2",
                         "sensor.energia_oggi_f1_f2", "sensor.energia_oggi_f1_F2",
                         "sensor.energia_oggi_f1_fascia_f2")
            f3_eid = _fs("oggi_f3",
                         "sensor.energia_oggi_f1_f3", "sensor.energia_oggi_f1_F3",
                         "sensor.energia_oggi_f1_fascia_f3")
            tot_eid = _fs("oggi_tot",
                          "sensor.energia_oggi_totale", "sensor.enel")

            if f1_eid and f2_eid and f3_eid:
                f1  = max(0.0, _val(f1_eid))
                f2  = max(0.0, _val(f2_eid))
                f3  = max(0.0, _val(f3_eid))
                tot = _val(tot_eid) if tot_eid else round(f1 + f2 + f3, 2)
                if tot < 0: tot = round(f1 + f2 + f3, 2)
                logger.info("energy_by_fascia oggi: F1=%s F2=%s F3=%s tot=%s",
                            f1_eid, f2_eid, f3_eid, tot_eid)
                return _build_response("oggi", f1, f2, f3, tot,
                                       "utility_meter giornaliero HA", fascia_corrente)
            logger.warning("energy_by_fascia: sensori fascia oggi non trovati in state_cache\n"
                           "  Configura in person_config.json → fascia_sensors → oggi_f1/f2/f3")

        # ── QUESTO MESE ──────────────────────────────────────────────────────
        if any(k in t_low for k in ("questo mese", "del mese", "mese in corso", "mese attuale")):
            f1_eid = _fs("mese_f1",
                         "sensor.energia_mese_f1_f1", "sensor.energia_mese_f1_F1",
                         "sensor.energia_mese_f1_fascia_f1")
            f2_eid = _fs("mese_f2",
                         "sensor.energia_mese_f1_f2", "sensor.energia_mese_f1_F2",
                         "sensor.energia_mese_f1_fascia_f2")
            f3_eid = _fs("mese_f3",
                         "sensor.energia_mese_f1_f3", "sensor.energia_mese_f1_F3",
                         "sensor.energia_mese_f1_fascia_f3")
            tot_eid = _fs("mese_tot",
                          "sensor.energia_mese_totale")

            if f1_eid and f2_eid and f3_eid:
                f1  = max(0.0, _val(f1_eid))
                f2  = max(0.0, _val(f2_eid))
                f3  = max(0.0, _val(f3_eid))
                tot = _val(tot_eid) if tot_eid else round(f1 + f2 + f3, 2)
                if tot < 0: tot = round(f1 + f2 + f3, 2)
                from datetime import datetime as _dt2
                mese_label = f"questo mese ({_dt2.now().strftime('%B %Y')})"
                logger.info("energy_by_fascia mese: F1=%s F2=%s F3=%s tot=%s",
                            f1_eid, f2_eid, f3_eid, tot_eid)
                return _build_response(mese_label, f1, f2, f3, tot,
                                       "utility_meter mensile HA")
            logger.warning("energy_by_fascia: sensori fascia mese non trovati in state_cache\n"
                           "  Configura in person_config.json → fascia_sensors → mese_f1/f2/f3")

        # ── PERIODI MULTI-GIORNO via History API ─────────────────────────────
        try:
            local_tz = datetime.now().astimezone().tzinfo
        except Exception:
            local_tz = timezone(timedelta(hours=1))
        now_local = datetime.now(local_tz)

        # Sensore daily: usa quello configurato in fascia_sensors.daily_source
        # oppure cerca automaticamente tra i candidati noti
        DAILY_CANDIDATES = [
            fascia_cfg.get("daily_source", ""),     # configurato dall'utente ← priorità
            "sensor.enel",                           # utility_meter daily (tuo setup)
            "sensor.energia_oggi_totale",            # utility_meter daily totale
            "sensor.daily_energy_combined",
            "sensor.enel_giorno",                    # integration cumulativa (ultimo)
        ]
        enel_daily = None
        for c in DAILY_CANDIDATES:
            if not c:
                continue
            v = _val(c)
            if v < 0:
                continue
            u = state_cache.get(c, {}).get("attributes", {}).get("unit_of_measurement", "")
            if u == "kWh":
                enel_daily = c
                logger.info("energy_by_fascia: sensore daily = %s (%.3f kWh)", c, v)
                break

        # Se non trovato daily, usa History su qualsiasi sensore kWh Enel
        if not enel_daily:
            for eid, s in state_cache.items():
                u = s.get("attributes", {}).get("unit_of_measurement", "")
                if u != "kWh":
                    continue
                v = _val(eid)
                if v < 0 or v > 500:  # scarta cumulativi totali
                    continue
                if any(k in eid.lower() for k in ("enel", "grid", "rete", "prelievo", "shelly_energia")):
                    enel_daily = eid
                    logger.info("energy_by_fascia: sensore daily fallback = %s (%.3f kWh)", eid, v)
                    break

        if not enel_daily:
            # Mostra cosa è disponibile per aiutare l'utente
            kwh_list = sorted([
                f"<code>{e}</code> ({_val(e):.2f} kWh)"
                for e in state_cache
                if state_cache[e].get("attributes", {}).get("unit_of_measurement") == "kWh"
                and _val(e) >= 0
            ])[:10]
            hint = "\n".join(kwh_list) if kwh_list else "<i>nessuno trovato</i>"
            return (
                "⚡ <b>Consumi per fascia</b>\n\n"
                "❌ Sensore Enel kWh non trovato.\n\n"
                "Aggiungi in <code>person_config.json</code>:\n"
                "<code>\"energy_sensors\": {\"rete_enel\": [\"sensor.enel_giorno\"]}</code>\n\n"
                f"Sensori kWh disponibili:\n{hint}"
            )

        # Calcola range temporale
        if "ieri" in t_low:
            yesterday = now_local.date() - timedelta(days=1)
            start_local = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, tzinfo=local_tz)
            end_local = start_local + timedelta(hours=24)
            label = "ieri"
            hours_back = 50
            n_days = 1
        elif "mese scorso" in t_low:
            first_this = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month = first_this - timedelta(days=1)
            start_local = last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_local = first_this
            label = f"mese scorso ({start_local.strftime('%B %Y')})"
            hours_back = 62 * 24
            n_days = (end_local - start_local).days
        else:
            m_mesi = _re.search(r'(\d+)\s*mes[ei]', t_low)
            m_giorni = _re.search(r'(\d+)\s*(?:giorni?|day)', t_low)
            if m_mesi:
                n = int(m_mesi.group(1))
                start_local = (now_local - timedelta(days=n * 30)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_local = now_local
                label = f"ultimi {n} {'mese' if n == 1 else 'mesi'}"
                hours_back = n * 30 * 24 + 26
                n_days = n * 30
            elif m_giorni:
                n = int(m_giorni.group(1))
                start_local = (now_local - timedelta(days=n)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_local = now_local
                label = f"ultimi {n} {'giorno' if n == 1 else 'giorni'}"
                hours_back = n * 24 + 26
                n_days = n
            else:
                # Fallback oggi via History
                start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
                end_local = now_local
                label = "oggi"
                hours_back = 26
                n_days = 1

        logger.info("energy_by_fascia: sensore=%s period=%s hours_back=%d", enel_daily, label, hours_back)

        try:
            history = await self.rest.get_history([enel_daily], hours=int(hours_back))
        except Exception as e:
            return f"⚡ <b>Consumi per fascia</b>\n\n❌ Errore History API: {e}"

        series = history.get(enel_daily, [])
        if not series:
            return (
                f"⚡ <b>Consumi per fascia — {label}</b>\n\n"
                "⚠️ Nessun dato storico disponibile.\n"
                "<i>HA Recorder potrebbe non registrare questo sensore.</i>"
            )

        # Parsing: filtra solo il periodo richiesto
        points = []
        for entry in series:
            ts_raw = entry.get("last_changed", entry.get("last_updated", ""))
            if not ts_raw:
                continue
            try:
                if ts_raw.endswith("Z"):
                    ts_raw = ts_raw[:-1] + "+00:00"
                ts_loc = datetime.fromisoformat(ts_raw).astimezone(local_tz)
                if start_local <= ts_loc <= end_local:
                    v = float(entry.get("state", ""))
                    points.append((ts_loc, v))
            except (ValueError, TypeError):
                pass

        if len(points) < 2:
            return (
                f"⚡ <b>Consumi per fascia — {label}</b>\n\n"
                f"⚠️ Dati insufficienti ({len(points)} campioni).\n"
                "<i>Prova con un periodo più ampio.</i>"
            )

        points.sort(key=lambda x: x[0])

        # Algoritmo a cascata per sensore daily (si azzera a mezzanotte)
        # Per ogni giorno:
        #   max(F1) = consumo accumulato entro fine F1
        #   consumo_F2 = max(F2) - max(F1)
        #   consumo_F3 = max(fine giorno) - max(F2)
        # Le fasce seguono le TUO configurazione HA (sensor.fascia_oraria_attuale):
        #   F1: lun-ven 08:00-19:00
        #   F2: lun-ven 07:00-08:00 e 19:00-23:00 / sab 07:00-23:00
        #   F3: 23:00-07:00 + domeniche + festivi
        # Per semplicità usiamo le fasce standard ARERA (più comuni):
        #   F1: lun-ven 08:00-19:00 (esclusi festivi)
        #   F2: lun-ven 07:00-08:00 / 19:00-23:00 + sab 07:00-23:00
        #   F3: tutto il resto (notti + domeniche + festivi)

        FESTIVI = {(1,1),(1,6),(4,25),(5,1),(6,2),(8,15),(11,1),(12,8),(12,25),(12,26)}

        def _fascia_arera(dt: datetime) -> str:
            wd = dt.weekday()  # 0=lun, 6=dom
            h  = dt.hour
            md = (dt.month, dt.day)
            if wd == 6 or md in FESTIVI:
                return "F3"
            if wd == 5:  # sabato
                return "F2" if 7 <= h < 23 else "F3"
            # Lun-ven
            if 8 <= h < 19:
                return "F1"
            elif 7 <= h < 8 or 19 <= h < 23:
                return "F2"
            else:
                return "F3"

        # Determina il tipo di sensore: daily (utility_meter, si azzera) vs cumulativo (integration)
        # utility_meter daily: max_val è tipicamente < 100 kWh (valore di un solo giorno)
        # integration cumulativo: max_val è migliaia di kWh
        current_val = _val(enel_daily)
        is_daily_meter = (current_val >= 0 and current_val < 500)

        from collections import defaultdict
        day_points: dict = defaultdict(list)
        for ts, v in points:
            day_points[ts.date()].append((ts, v))

        fascia_kwh = {"F1": 0.0, "F2": 0.0, "F3": 0.0}
        day_totals = []

        for day_key, dpts in sorted(day_points.items()):
            dpts.sort(key=lambda x: x[0])
            all_vals = [v for _, v in dpts]

            if is_daily_meter:
                # utility_meter daily: parte da 0 a mezzanotte, cresce durante il giorno
                # Il totale del giorno = valore massimo raggiunto (non delta start→end
                # perché a fine giorno il sensore potrebbe già essere al giorno dopo)
                day_total = max(0.0, max(all_vals))
            else:
                # Integration cumulativo: il totale è fine - inizio
                v_start = dpts[0][1]
                v_end   = dpts[-1][1]
                day_total = max(0.0, v_end - v_start)

            day_totals.append((day_key, day_total))

            logger.info("energy_by_fascia [%s] %s: total=%.3f kWh (%d campioni)",
                        "daily" if is_daily_meter else "cumul", day_key, day_total, len(dpts))

            if day_total <= 0:
                continue

            # Distribuisci usando i pesi dei delta per fascia ARERA
            weights = {"F1": 0.0, "F2": 0.0, "F3": 0.0}
            for i in range(1, len(dpts)):
                ts_prev, v_prev = dpts[i - 1]
                ts_curr, v_curr = dpts[i]
                delta = v_curr - v_prev
                if 0 < delta <= 5:  # ignora negativi e salti anomali
                    weights[_fascia_arera(ts_curr)] += delta

            w_tot = sum(weights.values())
            if w_tot > 0:
                for f in ("F1", "F2", "F3"):
                    fascia_kwh[f] = round(fascia_kwh[f] + day_total * (weights[f] / w_tot), 4)
            else:
                # Nessun delta valido → proporzione ore per fascia (8h F1, 4h F2, 12h F3)
                fascia_kwh["F1"] = round(fascia_kwh["F1"] + day_total * 8/24, 4)
                fascia_kwh["F2"] = round(fascia_kwh["F2"] + day_total * 4/24, 4)
                fascia_kwh["F3"] = round(fascia_kwh["F3"] + day_total * 12/24, 4)

        total = round(sum(fascia_kwh.values()), 2)
        unit  = state_cache.get(enel_daily, {}).get("attributes", {}).get("unit_of_measurement", "kWh")
        name  = state_cache.get(enel_daily, {}).get("attributes", {}).get("friendly_name", enel_daily)

        # Riepilogo giornaliero se più giorni
        day_detail = ""
        if len(day_totals) > 1:
            rows = [f"  {dk.strftime('%d/%m')}: {dt:.2f} kWh" for dk, dt in day_totals if dt > 0]
            if rows:
                day_detail = "\n\n<i>📅 Per giorno:\n" + "\n".join(rows) + "</i>"

        return (
            f"Ciao {person_name}, ecco i tuoi consumi dalla rete Enel\n"
            f"per il periodo <b>{label}</b> suddivisi per fascia ARERA:\n\n"
            f"ℹ️ Fascia F1 (lun-ven 08:00–19:00): <b>{fascia_kwh['F1']:.2f} {unit}</b>\n"
            f"ℹ️ Fascia F2 (lun-sab 07:00–08:00/19:00–23:00): <b>{fascia_kwh['F2']:.2f} {unit}</b>\n"
            f"ℹ️ Fascia F3 (notti + dom + festivi): <b>{fascia_kwh['F3']:.2f} {unit}</b>\n\n"
            f"⚡ Totale {label}: <b>{total:.2f} {unit}</b>"
            + day_detail +
            f"\n\n<i>📊 {name} — {len(points)} campioni</i>"
        )



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
