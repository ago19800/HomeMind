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
import asyncio, logging
from datetime import datetime, timedelta

logger = logging.getLogger("homemind.briefing")

BRIEFING_HOUR   = 7
BRIEFING_MINUTE = 0


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

    async def start(self):
        asyncio.create_task(self._scheduler(), name="morning_briefing")
        logger.info("MorningBriefing schedulato alle %02d:%02d", BRIEFING_HOUR, BRIEFING_MINUTE)

    async def _scheduler(self):
        """Aspetta la prossima BRIEFING_HOUR:MINUTE e manda il briefing ogni mattina.
        Se al riavvio l'orario è già passato oggi, manda subito (missed briefing)."""
        # Controlla se oggi il briefing era previsto e non è ancora stato mandato
        now    = datetime.now()
        target = now.replace(hour=BRIEFING_HOUR, minute=BRIEFING_MINUTE, second=0, microsecond=0)

        # Se siamo entro 90 minuti DOPO l'orario previsto → briefing perso, manda subito
        seconds_after = (now - target).total_seconds()
        if 0 < seconds_after < 5400:   # 0..90 minuti dopo
            logger.warning("Briefing PERSO (riavvio dopo %02d:%02d) — invio immediato",
                           BRIEFING_HOUR, BRIEFING_MINUTE)
            await asyncio.sleep(15)    # piccolo delay per dare tempo al sistema di inizializzarsi
            try:
                await self.send_briefing()
            except Exception as e:
                logger.error("Briefing immediato fallito: %s", e)

        while True:
            now    = datetime.now()
            target = now.replace(hour=BRIEFING_HOUR, minute=BRIEFING_MINUTE, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            logger.info("Prossimo briefing tra %.0f min (%02d:%02d)",
                        wait / 60, BRIEFING_HOUR, BRIEFING_MINUTE)
            await asyncio.sleep(wait)
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
        if self.history_client:
            try:
                energy = await self.history_client.energy_summary("ieri")
                # Versione compatta per il briefing
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

        # ── CONSIGLIO AI PERSONALIZZATO ────────────────────────────────────
        try:
            ai_tip = await self._get_ai_daily_tip(cache, weather)
            if ai_tip:
                sections.append(f"💡 <b>Consiglio del giorno:</b>\n  {ai_tip}")
        except Exception:
            pass

        # ── FOOTER ────────────────────────────────────────────────────────
        sections.append("──────────────────────────────\n<i>HomeMind — Il tuo maggiordomo AI 🎩</i>")

        full_msg = "\n\n".join(sections)
        try:
            await self.notifier._telegram(full_msg, parse_mode="HTML")
            logger.info("Morning briefing inviato")
        except Exception as e:
            logger.error("Briefing send failed: %s", e)
        return full_msg

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
        answer = await self.ai.ask(system, ctx, max_tokens=100)
        return answer.strip()[:200]
