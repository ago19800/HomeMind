"""
agent/weather_external.py — Meteo per qualsiasi città via open-meteo.com (gratuito, no API key)

Usa:
  - geocoding-api.open-meteo.com  → lat/lon da nome città
  - api.open-meteo.com            → previsioni meteo
"""
import logging
import re
from datetime import datetime

logger = logging.getLogger("homemind.weather_ext")

# Codici WMO → descrizione + emoji
WMO_CODES = {
    0:  ("Sereno",           "☀️"),
    1:  ("Prevalentemente sereno", "🌤️"),
    2:  ("Parzialmente nuvoloso", "⛅"),
    3:  ("Nuvoloso",         "☁️"),
    45: ("Nebbia",           "🌫️"),
    48: ("Nebbia con brina", "🌫️"),
    51: ("Pioviggine leggera","🌦️"),
    53: ("Pioviggine",       "🌦️"),
    55: ("Pioviggine intensa","🌧️"),
    61: ("Pioggia leggera",  "🌧️"),
    63: ("Pioggia",          "🌧️"),
    65: ("Pioggia intensa",  "🌧️"),
    71: ("Neve leggera",     "❄️"),
    73: ("Neve",             "❄️"),
    75: ("Neve intensa",     "❄️"),
    80: ("Rovesci leggeri",  "🌦️"),
    81: ("Rovesci",          "🌧️"),
    82: ("Rovesci intensi",  "⛈️"),
    95: ("Temporale",        "⛈️"),
    96: ("Temporale con grandine", "⛈️"),
    99: ("Temporale con grandine intensa", "⛈️"),
}

# Parole che NON sono città
_NOT_CITIES = {
    "rimuovi", "elimina", "cancella", "togli", "aggiungi", "mostra",
    "escludi", "nascondi", "ripristina", "reset", "azzera",
    "a", "di", "per", "il", "la", "lo", "gli", "le",
    "casa", "home", "interno", "esterno",
    "oggi", "domani", "ieri", "adesso", "ora",
    "briefing", "config", "stato", "status", "sensore",
}

def detect_city(text: str) -> str | None:
    """Estrae il nome della città da una frase in linguaggio naturale."""
    t = text.strip()
    patterns = [
        r'(?:meteo|weather|tempo|previsioni)\s+(?:a\s+|di\s+|per\s+)?(.+)',
        r'(?:che\s+tempo\s+fa|come\s+è\s+il\s+tempo)\s+(?:a\s+)?(.+)',
        r'(.+)\s+(?:meteo|weather)',
    ]
    # Parole che non sono città — frasi config, briefing, comandi comuni
    NOT_CITIES = {
        "a", "di", "per", "il", "la", "lo", "le", "i", "gli",
        "casa", "home", "interno", "esterno",
        "rimuovi", "aggiungi", "escludi", "mostra", "ripristina",
        "briefing", "config", "meteo", "weather", "stato",
        "power", "guard", "soglia", "whitelist", "blacklist",
        "lavatrice", "lavastoviglie", "forno", "asciugatrice",
        "energia", "solare", "batteria", "spazzatura",
    }
    for pat in patterns:
        m = re.match(pat, t, re.IGNORECASE)
        if m:
            city = m.group(1).strip().rstrip('?!.,')
            # Rifiuta parole singole che sono comandi o non-città
            if city.lower() in _NOT_CITIES:
                return None
            if (len(city) > 1
                    and (city[0].isupper() or " " in city or len(city) > 6)):
                return city
    return None

async def get_weather_for_city(city: str, session=None) -> str:
    """
    Recupera il meteo per una città esterna via open-meteo.
    session: aiohttp.ClientSession (opzionale — se None viene creata internamente)
    """
    import aiohttp as _aio
    _own_session = session is None
    if _own_session:
        session = _aio.ClientSession()
    try:
        # Step 1: Geocoding
        geo_url = (f"https://geocoding-api.open-meteo.com/v1/search"
                   f"?name={city}&count=1&language=it&format=json")
        async with session.get(geo_url, timeout=8) as r:
            r.raise_for_status()
            geo_data = await r.json()

        results = geo_data.get("results")
        if not results:
            return f"🌍 Non ho trovato <b>{city}</b> — verifica il nome della città."

        loc = results[0]
        lat     = loc["latitude"]
        lon     = loc["longitude"]
        name    = loc.get("name", city)
        country = loc.get("country", "")
        admin1  = loc.get("admin1", "")  # regione/stato

        # Step 2: Meteo attuale + previsioni 3 giorni
        met_url = (f"https://api.open-meteo.com/v1/forecast"
                   f"?latitude={lat}&longitude={lon}"
                   f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
                   f"wind_speed_10m,weather_code"
                   f"&daily=weather_code,temperature_2m_max,temperature_2m_min"
                   f"&timezone=auto&forecast_days=4&language=it")
        async with session.get(met_url, timeout=8) as r:
            r.raise_for_status()
            met_data = await r.json()

        curr    = met_data["current"]
        daily   = met_data.get("daily", {})
        temp    = curr["temperature_2m"]
        feels   = curr.get("apparent_temperature", temp)
        hum     = curr["relative_humidity_2m"]
        wind    = curr["wind_speed_10m"]
        code    = curr["weather_code"]
        desc, emoji = WMO_CODES.get(code, ("", "🌤️"))

        location_str = f"{name}"
        if admin1 and admin1.lower() != name.lower():
            location_str += f", {admin1}"
        if country:
            location_str += f", {country}"

        lines = [
            f"{emoji} <b>Meteo — {location_str}</b>",
            "─────────────────────",
            f"🌡️ Temperatura: <b>{temp}°C</b> (percepita {feels:.0f}°C)",
            f"💧 Umidità: {hum}%",
            f"💨 Vento: {wind} km/h",
        ]
        if desc:
            lines.append(f"☁️ Condizioni: {desc}")

        # Previsioni 3 giorni
        if daily.get("time"):
            lines.append("")
            lines.append("📅 <b>Prossimi giorni:</b>")
            giorni = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"]
            for i, date_str in enumerate(daily["time"][1:4], 1):
                try:
                    dt   = datetime.fromisoformat(date_str)
                    gg   = giorni[dt.weekday()]
                    hi   = daily["temperature_2m_max"][i]
                    lo   = daily["temperature_2m_min"][i]
                    wc   = daily["weather_code"][i]
                    _, em = WMO_CODES.get(wc, ("", "🌤️"))
                    lines.append(f"  {em} <b>{gg}</b>: {lo:.0f}°→{hi:.0f}°")
                except Exception:
                    pass

        lines.append(f"\n<i>🕐 {datetime.now().strftime('%H:%M')} — open-meteo.com</i>")
        return "\n".join(lines)

    except Exception as e:
        logger.warning("weather_external error for '%s': %s", city, e)
        return (f"🌍 Non riesco a recuperare il meteo per <b>{city}</b>.\n"
                f"Prova a scrivere il nome in inglese o verifica la connessione.")
    finally:
        if _own_session and not session.closed:
            await session.close()
