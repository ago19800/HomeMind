"""
agent/morning_briefing.py — IL MAGGIORDOMO AI 🎩
Ogni mattina alle 07:30 invia un briefing completo della giornata:
- Meteo
- Energia di ieri vs oggi  
- Anomalie notturne rilevate
- Riparazioni HA pendenti
- Prossima raccolta spazzatura
- Consigli AI personalizzati sulla giornata
"""
import asyncio, json, logging, re
from datetime import datetime, timedelta
import xml.etree.ElementTree as _ET
from pathlib import Path

CONFIG_FILE = Path("/config/homemind_patches/person_config.json")

logger = logging.getLogger("homemind.briefing")

BRIEFING_HOUR_DEFAULT   = 7
BRIEFING_MINUTE_DEFAULT = 0


class MorningBriefing:
    def __init__(self, ai, rest_client, state_cache_cb,
                 notifier=None, home=None,
                 history_client=None, repairs_checker=None,
                 spazzatura=None):
        self.ai              = ai
        self.rest            = rest_client
        self.state_cache_cb  = state_cache_cb   # callable → state_cache dict
        self.notifier        = notifier
        self.home            = home
        self.history_client  = history_client
        self.repairs_checker = repairs_checker
        self.spazzatura      = spazzatura
        self.routine_manager    = None  # impostato da main.py
        self.appliance_monitor  = None  # impostato da main.py

    def _get_briefing_hour(self) -> tuple[int, int]:
        """Legge l'ora del briefing dal config ogni volta — così i cambi via Telegram
        vengono applicati senza riavviare l'addon.
        """
        try:
            if CONFIG_FILE.exists():
                cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
                cb  = cfg.get("custom_briefing", {})
                h   = int(cb.get("briefing_hour", BRIEFING_HOUR_DEFAULT))
                if 0 <= h <= 23:
                    return h, BRIEFING_MINUTE_DEFAULT
        except Exception:
            pass
        return BRIEFING_HOUR_DEFAULT, BRIEFING_MINUTE_DEFAULT

    async def start(self):
        asyncio.create_task(self._scheduler(), name="morning_briefing")
        h, m = self._get_briefing_hour()
        logger.info("MorningBriefing schedulato alle %02d:%02d", h, m)

    async def _scheduler(self):
        """Aspetta la prossima ora del briefing e lo manda ogni giorno.
        Rilegge l'ora dal config a ogni ciclo: i cambi via Telegram
        vengono applicati automaticamente senza riavviare l'addon.
        """
        # Controlla se oggi il briefing era previsto e non è ancora stato mandato
        bh, bm = self._get_briefing_hour()
        now    = datetime.now()
        target = now.replace(hour=bh, minute=bm, second=0, microsecond=0)

        # Se siamo entro 90 minuti DOPO l'orario previsto → briefing perso, manda subito
        seconds_after = (now - target).total_seconds()
        if 0 < seconds_after < 5400:
            logger.warning("Briefing PERSO (riavvio dopo %02d:%02d) — invio immediato", bh, bm)
            await asyncio.sleep(15)
            try:
                await self.send_briefing()
            except Exception as e:
                logger.error("Briefing immediato fallito: %s", e)

        while True:
            # Rilegge l'ora a ogni ciclo — applica subito le modifiche via Telegram
            bh, bm = self._get_briefing_hour()
            now    = datetime.now()
            target = now.replace(hour=bh, minute=bm, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            logger.info("Prossimo briefing tra %.0f min (%02d:%02d)", wait / 60, bh, bm)
            # Sleep in blocchi da 5 minuti per rilevare cambi di orario
            slept = 0.0
            while slept < wait:
                chunk = min(300.0, wait - slept)  # blocchi da 5 min
                await asyncio.sleep(chunk)
                slept += chunk
                # Rilegge ora: se l'utente l'ha cambiata, ricalcola il target
                new_bh, new_bm = self._get_briefing_hour()
                if new_bh != bh or new_bm != bm:
                    logger.info("Briefing: ora cambiata da %02d:%02d a %02d:%02d — aggiorno schedule",
                                bh, bm, new_bh, new_bm)
                    break  # esci e ricalcola nel ciclo esterno
            else:
                # Sleep completato senza interruzioni → manda il briefing
                try:
                    await self.send_briefing()
                except Exception as e:
                    logger.error("Briefing fallito: %s", e)

    async def send_briefing(self) -> str:
        """Genera e invia il briefing mattutino. Ritorna il testo per debug."""
        cache = self.state_cache_cb()
        now   = datetime.now()
        dow   = ["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"][now.weekday()]

        sections = []

        # ── HEADER ────────────────────────────────────────────────────────
        sections.append(
            f"🎩 <b>Buongiorno! Briefing del {dow} {now.strftime('%d/%m/%Y')}</b>\n"
            f"──────────────────────────────"
        )

        # ── METEO ─────────────────────────────────────────────────────────
        # Controlla se c'è una città configurata per il meteo esterno
        _cfg_b = {}
        try:
            import json as _json_m
            from pathlib import Path as _Path_m
            _cfg_file = _Path_m("/config/homemind_patches/person_config.json")
            if _cfg_file.exists():
                _cfg_b = _json_m.loads(_cfg_file.read_text(encoding="utf-8-sig"))
        except Exception:
            pass
        _cb_m      = _cfg_b.get("custom_briefing", {})
        _wx_city   = _cb_m.get("weather_city", "").strip()
        _tip_mode  = _cb_m.get("tip_mode", "tip")   # "tip" | "disabled" | "news"

        weather = None
        _wx_added = False
        if _wx_city:
            # Meteo esterno via open-meteo — con fallback al sensore HA
            try:
                from agent.weather_external import get_weather_for_city as _get_wx
                _wx_result = await _get_wx(_wx_city, None)  # crea sessione interna
                # Considera valido solo se non è un messaggio di errore
                _is_error = any(kw in _wx_result.lower() for kw in
                               ("non riesco", "non trovata", "non ho trovato", "errore", "error"))
                if _wx_result and not _is_error:
                    sections.append(_wx_result)
                    _wx_added = True
                else:
                    logger.warning("Briefing: meteo esterno per '%s' fallito, uso sensore HA", _wx_city)
            except Exception as _wxe:
                logger.warning("Briefing meteo esterno error: %s", _wxe)
        # Se meteo esterno non è stato aggiunto (non configurato o fallito) → usa sensore HA
        if not _wx_added:
            weather = await self.rest.get_weather()
        if weather:
            attrs = weather.get("attributes", {})
            temp  = attrs.get("temperature", "?")
            cond  = weather.get("state", "?")
            hum   = attrs.get("humidity", "?")
            wind  = attrs.get("wind_speed", "?")
            cond_icon = {
                "sunny": "☀️", "clear-night": "🌙", "cloudy": "☁️",
                "partlycloudy": "⛅", "rainy": "🌧️", "snowy": "❄️",
                "lightning": "⛈️", "fog": "🌫️", "windy": "💨",
                "pouring": "🌊",
            }.get(cond, "🌤️")

            forecast_lines = []
            for f in attrs.get("forecast", [])[:3]:
                day_name = datetime.fromisoformat(f["datetime"]).strftime("%a") if "datetime" in f else "?"
                lo = f.get("templow", "?"); hi = f.get("temperature", "?")
                fc = f.get("condition", "")
                fi = {"sunny":"☀️","cloudy":"☁️","rainy":"🌧️","partlycloudy":"⛅"}.get(fc,"🌤️")
                forecast_lines.append(f"  {fi} {day_name}: {lo}°→{hi}°")

            sections.append(
                f"{cond_icon} <b>Meteo</b>\n"
                f"  🌡️ {temp}°C  💧 {hum}%  💨 {wind} km/h\n"
                + ("\n".join(forecast_lines) if forecast_lines else "")
            )

        # ── ENERGIA IERI ───────────────────────────────────────────────────
        # Prima tenta lo storico EnergyAnalyzer (snapshot 23:30, più affidabile)
        # poi fallback a History API
        _energy_added = False
        try:
            from pathlib import Path as _EPath
            import json as _ejson
            from datetime import date as _edate
            _hist_path = _EPath("/data/homemind_energy_history.json")
            if _hist_path.exists():
                _hist = _ejson.loads(_hist_path.read_text())
                _ieri_str = (_edate.today().replace(day=_edate.today().day - 1)
                             if _edate.today().day > 1
                             else None)
                # Uso corretto: timedelta
                from datetime import timedelta as _etd
                _ieri_str = (_edate.today() - _etd(days=1)).isoformat()
                _snap = _hist.get(_ieri_str, {})
                if _snap:
                    _icons  = {"produzione_fv": "☀️", "consumo_casa": "🏠",
                               "rete_enel": "🔌", "batteria_wh": "🔋"}
                    _labels = {"produzione_fv": "Produzione FV", "consumo_casa": "Consumo casa",
                               "rete_enel": "Da rete (Enel)", "batteria_wh": "Batteria"}
                    _elines = [f"⚡ <b>Energia ieri ({_ieri_str})</b>", "─" * 18]
                    _vals = {}
                    for _cat, _val in _snap.items():
                        _ico = _icons.get(_cat, "📊")
                        _lbl = _labels.get(_cat, _cat)
                        _elines.append(f"{_ico} <b>{_lbl}:</b> {_val:.2f} kWh")
                        _vals[_cat] = _val
                    # Autosufficienza
                    if "produzione_fv" in _vals and "consumo_casa" in _vals and _vals["consumo_casa"] > 0:
                        _perc = min(100, round(_vals["produzione_fv"] / _vals["consumo_casa"] * 100))
                        _bar  = "█" * (_perc // 10) + "░" * (10 - _perc // 10)
                        _elines.append(f"\n📊 <b>Autosufficienza:</b> {_perc}%")
                        _elines.append(f"   {_bar}")
                    _elines.append("─" * 18)
                    sections.append("\n".join(_elines))
                    _energy_added = True
                    logger.info("Briefing: energia ieri da snapshot EnergyAnalyzer (%s)", _ieri_str)
        except Exception as _ee:
            logger.warning("Briefing: snapshot energia ieri errore: %s", _ee)

        # Fallback: History API (meno affidabile per sensori daily che si resettano)
        if not _energy_added and self.history_client:
            try:
                energy = await self.history_client.energy_summary("ieri")
                if "Nessun sensore energia" not in energy:
                    sections.append(energy.replace("Energia — Ieri", "Energia ieri"))
            except Exception:
                pass

        # ── STATO CASA ────────────────────────────────────────────────────
        if self.home:
            who = self.home.who_is_home()
            alarm_eid, alarm_st = self.home.primary_alarm()
            alarm_label = {
                "armed_away": "🔒 Armato (away)",
                "armed_home": "🏠 Armato (home)",
                "disarmed":   "🔓 Disarmato",
                "triggered":  "🚨 TRIGGERED!",
            }.get(alarm_st, alarm_st or "?")

            sections.append(
                f"🏠 <b>Stato Casa</b>\n"
                f"  👤 In casa: {', '.join(who) or 'Nessuno'}\n"
                f"  🔒 Allarme: {alarm_label}"
            )

        # ── ELETTRODOMESTICI IN FUNZIONE ─────────────────────────────────────
        if self.appliance_monitor:
            try:
                _running = self.appliance_monitor.get_all_running()
                if _running:
                    _appl_lines = ["⚡ <b>Elettrodomestici attivi:</b>"]
                    for _an, _ast in _running.items():
                        _appl_lines.append(f"  🔄 <b>{_an.capitalize()}</b> — in funzione")
                    sections.append("\n".join(_appl_lines))
            except Exception:
                pass

        # ── RIPARAZIONI ───────────────────────────────────────────────────
        if self.repairs_checker:
            try:
                issues = await self.rest.get_repairs()
                crit   = [i for i in issues if i.get("severity") in ("critical", "error")]
                if crit:
                    sections.append(
                        f"⚠️ <b>Problemi HA da risolvere ({len(crit)}):</b>\n"
                        + "\n".join(f"  🔴 {i.get('title','?')}" for i in crit[:3])
                        + "\n  → /riparazioni per dettagli"
                    )
            except Exception:
                pass

        # ── SPAZZATURA OGGI ────────────────────────────────────────────────
        if self.spazzatura and hasattr(self.spazzatura, "calendar") and self.spazzatura.calendar:
            today = datetime.now().strftime("%Y-%m-%d")
            tmr   = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            today_items = self.spazzatura.calendar.get(today, [])
            tmr_items   = self.spazzatura.calendar.get(tmr, [])
            if today_items:
                sections.append(f"🗑️ <b>Spazzatura OGGI:</b> {', '.join(today_items)}")
            elif tmr_items:
                sections.append(f"🗑️ <b>Spazzatura domani:</b> {', '.join(tmr_items)}")

        # ── CUSTOM BRIEFING da person_config.json ───────────────────────
        try:
            cfg_b = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig")) if CONFIG_FILE.exists() else {}
            cb    = cfg_b.get("custom_briefing", {})
            exclude        = [s.lower() for s in cb.get("exclude_sections", [])]
            extra_sections = cb.get("extra_sections", [])
            custom_greeting = cb.get("custom_greeting", "")

            # Saluto personalizzato — prominente in cima
            # Normalizza: se è solo nome lowercase, aggiungi "Buongiorno"
            if custom_greeting:
                _gw = custom_greeting.split()
                _gkw = {"buongiorno","ciao","hello","good","salve","hey","benvenuto","morning","🌅","🌄","☀️"}
                if _gw and _gw[0].lower().strip("☀️🌅") not in _gkw and len(_gw) <= 3:
                    custom_greeting = f"Buongiorno {custom_greeting.title()}! ☀️"
            if custom_greeting:
                sections[0] = (
                    f"\n🌅 <b>{custom_greeting}</b>\n"
                    f"\n🎩 <b>Briefing del {dow} {now.day:02d}/{now.month:02d}/{now.year}</b>\n"
                    "──────────────────────────────"
                )

            # Rimuovi sezioni escluse
            # Mappa ID sezione → keyword che appaiono nel testo generato
            # Mappa: keyword esclusione → testi UNIVOCI della sezione (NO emoji condivise!)
            _exclude_map = {
                "energia":    ["produzione fv", "consumo casa", "da rete (enel)", "autosufficienza",
                               "energia — ieri", "energia ieri"],
                "energy":     ["produzione fv", "consumo casa", "da rete"],
                "meteo":      ["meteo</b>", "weather</b>", "previsioni</b>",
                               "km/h\n", "% 💨", "💧 ", "🌡️ "],
                "stato_casa": ["stato casa</b>", "in casa:", "allarme:"],
                "stato casa": ["stato casa</b>", "in casa:", "allarme:"],  # alias
                "riparazioni":["problemi ha", "riparazioni", "da risolvere"],
                "spazzatura": ["spazzatura oggi", "spazzatura domani", "spazzatura</b>"],
                "consiglio":  ["consiglio del giorno"],
                "routine":    ["routine"],
            }
            if exclude:
                filtered = []
                for sec in sections:
                    sec_low = sec.lower()
                    skip = False
                    for ex in exclude:
                        ex_low = ex.lower()
                        # Controlla per ID sezione o keyword diretta
                        keywords = _exclude_map.get(ex_low, [ex_low])
                        if any(kw in sec_low for kw in keywords):
                            skip = True
                            break
                    if not skip:
                        filtered.append(sec)
                sections = filtered

            # Sezioni extra — supporta {sensor.entity_id} inline
            def _resolve_sensor(m):
                eid  = m.group(1)
                st   = cache.get(eid, {}).get("state", "?")
                unit = cache.get(eid, {}).get("attributes", {}).get("unit_of_measurement", "")
                name = cache.get(eid, {}).get("attributes", {}).get("friendly_name", "")
                val  = f"<b>{st}{unit}</b>"
                return f"{val} ({name})" if name else val

            GREETING_PREFIXES = ("saluto ", "greeting ", "intestazione ")
            for extra_sec in extra_sections:
                # Salta sezioni aggiunte per errore (es. "saluto buongiorno X")
                if any(extra_sec.lower().startswith(p) for p in GREETING_PREFIXES):
                    continue
                resolved = re.sub(r"\{([^}]+)\}", _resolve_sensor, extra_sec)
                sections.append(f"📌 <b>Nota:</b> {resolved}")

        except Exception as e_cb:
            logger.warning("custom_briefing error: %s", e_cb)

        # ── CONSIGLIO / NEWS / NULLA ──────────────────────────────────────
        if _tip_mode == "disabled":
            pass  # nessun consiglio
        elif _tip_mode == "news":
            try:
                _news = await self._get_top_news()
                if _news:
                    sections.append(_news)
            except Exception as _ne:
                logger.warning("Briefing news error: %s", _ne)
        elif _tip_mode == "sports":
            try:
                _sports = await self._get_sports_news()
                if _sports:
                    sections.append(_sports)
            except Exception as _se:
                logger.warning("Briefing sports error: %s", _se)
        else:  # "tip" (default)
            try:
                ai_tip = await self._get_ai_daily_tip(cache, weather)
                if ai_tip:
                    sections.append(f"💡 <b>Consiglio del giorno:</b>\n  {ai_tip}")
            except Exception:
                pass

        # ── FOOTER ────────────────────────────────────────────────────────
        # ── Routine del giorno ─────────────────────────────────────────
        if self.routine_manager:
            routine_summary = self.routine_manager.get_routine_summary()
            if routine_summary:
                sections.append(routine_summary)

        sections.append("──────────────────────────────\n<i>HomeMind — Il tuo maggiordomo AI 🎩</i>")

        full_msg = "\n\n".join(sections)
        try:
            await self.notifier._telegram(full_msg, parse_mode="HTML")
            logger.info("Morning briefing inviato")
        except Exception as e:
            logger.error("Briefing send failed: %s", e)
        return full_msg

    async def _get_top_news(self) -> str:
        """Recupera le notizie del giorno via RSS ANSA (gratuito, no API key)."""
        RSS_FEEDS = [
            ("https://www.ansa.it/sito/ansait_rss.xml",   "ANSA"),
            ("https://www.raiplay.it/dl/RaiPlay/live/catalog/channels-v4.json", None),  # fallback
        ]
        try:
            import aiohttp as _aio
            async with _aio.ClientSession() as _sess:
                for feed_url, source in RSS_FEEDS:
                    if source is None:
                        continue
                    try:
                        async with _sess.get(feed_url, timeout=_aio.ClientTimeout(total=6)) as resp:
                            if resp.status != 200:
                                continue
                            xml_text = await resp.text()
                            root = _ET.fromstring(xml_text)
                            items = root.findall(".//item")[:5]
                            if not items:
                                continue
                            lines = [f"📰 <b>News del giorno ({source}):</b>"]
                            for item in items:
                                title = (item.findtext("title") or "").strip()
                                if title:
                                    lines.append(f"  • {title}")
                            if len(lines) > 1:
                                return "\n".join(lines)
                    except Exception:
                        continue
        except Exception as e:
            logger.warning("_get_top_news error: %s", e)
        return ""

    async def _get_sports_news(self) -> str:
        """Recupera i risultati sportivi del giorno via RSS ANSA Sport."""
        SPORTS_FEEDS = [
            "https://www.ansa.it/sito/notizie/sport/sport_rss.xml",
            "https://www.gazzetta.it/rss/home.xml",
        ]
        try:
            import aiohttp as _aio
            async with _aio.ClientSession() as _sess:
                for feed_url in SPORTS_FEEDS:
                    try:
                        async with _sess.get(feed_url, timeout=_aio.ClientTimeout(total=6)) as resp:
                            if resp.status != 200:
                                continue
                            xml_text = await resp.text()
                            root = _ET.fromstring(xml_text)
                            items = root.findall(".//item")[:5]
                            if not items:
                                continue
                            source = "ANSA Sport" if "ansa" in feed_url else "Gazzetta"
                            lines = [f"⚽ <b>Sport ({source}):</b>"]
                            for item in items:
                                title = (item.findtext("title") or "").strip()
                                if title:
                                    lines.append(f"  • {title}")
                            if len(lines) > 1:
                                return "\n".join(lines)
                    except Exception:
                        continue
        except Exception as e:
            logger.warning("_get_sports_news error: %s", e)
        return ""

    async def _get_ai_daily_tip(self, cache: dict, weather: dict | None) -> str:
        """Genera un consiglio AI contestualizzato."""
        ctx_parts = []

        if weather:
            attrs = weather.get("attributes", {})
            ctx_parts.append(
                f"Meteo: {weather.get('state','?')}, {attrs.get('temperature','?')}°C, "
                f"umidità {attrs.get('humidity','?')}%"
            )

        # Ore del giorno, giorno settimana
        now = datetime.now()
        ctx_parts.append(f"Giorno: {['Lun','Mar','Mer','Gio','Ven','Sab','Dom'][now.weekday()]}")

        # Sensori energia
        for eid in ["sensor.inverter_pipsolar_pv1_charging_power", "sensor.sensori_watt"]:
            if eid in cache:
                v = cache[eid].get("state","?")
                ctx_parts.append(f"{eid}: {v}")

        system = (
            "Sei HomeMind, assistente AI per la casa. "
            "Genera UN SOLO consiglio pratico e utile per la giornata, "
            "basato sul meteo e sulla domotica della casa. "
            "Max 2 righe. Italiano. Niente emoji. Diretto e concreto."
        )
        ctx = " | ".join(ctx_parts)
        answer = await self.ai.ask(system, ctx, max_tokens=300)
        return answer.strip()[:500]
