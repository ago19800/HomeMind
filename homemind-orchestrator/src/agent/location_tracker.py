"""
agent/location_tracker.py — Soste significative con indirizzo reale via GPS.

Funzionamento:
  1. Legge history del device_tracker (ha lat/lon reali)
  2. Raggruppa punti GPS vicini (< radius_m metri) → cluster = sosta
  3. Filtra soste brevi (< min_stop_min minuti)
  4. Reverse-geocoding con Nominatim (OpenStreetMap, gratuito)
  5. Ritorna lista soste ordinate per durata

Configurazione in person_config.json:
  "location_tracker": {
    "agostino": "device_tracker.sm_s931b",   ← entity_id device_tracker
    "rosa":     "device_tracker.iphone_rosa"
  }
"""

import asyncio
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import aiohttp

from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.location")

CONFIG_FILE    = Path("/config/homemind_patches/person_config.json")
NOMINATIM_URL  = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_UA   = "HomeMind/1.0 (home-assistant-addon)"

DEFAULT_MIN_STOP_MIN = 8     # minuti minimi — abbassato per non perdere soste brevi
DEFAULT_HOURS        = 24    # ore di storico
DEFAULT_RADIUS_M     = 200   # metri: punti entro questo raggio = stessa sosta (era 150)
MAX_GEOCODE_CALLS    = 10    # limite chiamate Nominatim per risposta
DEFAULT_MAX_GAP_MIN  = 120   # minuti gap GPS tollerato (schermo spento) — era 90


# ─────────────────────────────────────────────────────────────────────────────
# Helpers geometrici

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distanza in metri tra due coordinate GPS."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def _centroid(points: list[tuple]) -> tuple[float, float]:
    """Media lat/lon di un gruppo di punti."""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return sum(lats)/len(lats), sum(lons)/len(lons)


# ─────────────────────────────────────────────────────────────────────────────
# Config

def _get_tracker_eid(person_name: str) -> Optional[str]:
    """Legge device_tracker configurato per questa persona."""
    try:
        cfg = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else {}
        lt  = cfg.get("location_tracker", {})
        # Cerca per nome esatto o parziale
        name_low = person_name.lower()
        for k, v in lt.items():
            if k.lower() == name_low or k.lower() in name_low or name_low in k.lower():
                return v
    except Exception as e:
        logger.warning("location_tracker config: %s", e)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Reverse geocoding

async def _get_home_coords(rest_client) -> Optional[tuple]:
    """Ritorna (lat, lon) della zona home di HA, o None se non disponibile."""
    try:
        states = await rest_client.get_states()
        for s in (states if isinstance(states, list) else []):
            eid = s.get("entity_id", "")
            if eid == "zone.home":
                attrs = s.get("attributes", {})
                lat = attrs.get("latitude")
                lon = attrs.get("longitude")
                if lat and lon:
                    return (float(lat), float(lon))
    except Exception as e:
        logger.debug("_get_home_coords error: %s", e)
    return None


async def _reverse_geocode(lat: float, lon: float, session: aiohttp.ClientSession) -> str:
    """Ritorna indirizzo leggibile da coordinate. Usa Nominatim (OSM)."""
    try:
        params = {
            "lat": lat, "lon": lon,
            "format": "json",
            "zoom": 18,           # livello massimo — numero civico
            "addressdetails": 1,
            "namedetails": 1,
        }
        headers = {"User-Agent": NOMINATIM_UA}
        async with session.get(NOMINATIM_URL, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return f"({lat:.4f}, {lon:.4f})"
            data = await r.json()
            addr = data.get("address", {})

            # Costruisci indirizzo significativo
            # Gestione speciale per zone rurali italiane (Contrada, Località, Frazione)
            parts = []

            # 1. Via / Strada principale (priorità assoluta)
            road = (addr.get("road") or addr.get("pedestrian") or
                    addr.get("footway") or addr.get("path") or
                    addr.get("hamlet") or addr.get("locality") or
                    addr.get("isolated_dwelling") or addr.get("croft"))
            # Nome edificio/attività se presente
            amenity = (addr.get("amenity") or addr.get("shop") or
                       addr.get("tourism") or addr.get("office"))
            if amenity and not road:
                parts.append(amenity)
            if road:
                house = addr.get("house_number", "")
                parts.append(f"{road} {house}".strip())

            # 2. Quartiere / Frazione (solo se diverso dalla via)
            suburb = (addr.get("suburb") or addr.get("neighbourhood") or
                      addr.get("quarter") or addr.get("borough"))
            if suburb and suburb != road:
                parts.append(suburb)

            # 3. Comune
            city = (addr.get("city") or addr.get("town") or
                    addr.get("village") or addr.get("municipality"))
            if city:
                parts.append(city)

            if parts:
                return ", ".join(parts)

            # Fallback: usa display_name di Nominatim troncato
            display = data.get("display_name", "")
            if display:
                # Prendi le prime 2-3 parti prima della provincia
                segments = [s.strip() for s in display.split(",")]
                return ", ".join(segments[:3])
            return f"({lat:.4f}, {lon:.4f})"
    except Exception as e:
        logger.debug("Geocoding error: %s", e)
        return f"({lat:.4f}, {lon:.4f})"


# ─────────────────────────────────────────────────────────────────────────────
# Clustering

def _cluster_gps_points(points: list[dict], radius_m: float,
                        max_gap_min: float = DEFAULT_MAX_GAP_MIN) -> list[dict]:
    """
    Raggruppa punti GPS vicini in soste.
    Ogni punto: {"lat": float, "lon": float, "ts": datetime}
    Ritorna: [{"lat", "lon", "start", "end", "minutes", "point_count"}, ...]

    Gap bridging: se il GPS smette di aggiornarsi mentre la persona è ferma
    (telefono con schermo spento), i punti mancano ma la sosta era reale.
    Se due punti consecutivi sono entro radius_m E il buco temporale è
    < max_gap_min, viene considerato un'unica sosta continua.
    """
    if not points:
        return []

    clusters = []
    i = 0
    while i < len(points):
        p = points[i]
        cluster_pts   = [(p["lat"], p["lon"])]
        cluster_start = p["ts"]
        cluster_end   = p["ts"]
        j = i + 1

        while j < len(points):
            q = points[j]
            clat, clon = _centroid(cluster_pts)
            dist = _haversine_m(clat, clon, q["lat"], q["lon"])

            if dist <= radius_m:
                # Punto vicino → parte della stessa sosta
                cluster_pts.append((q["lat"], q["lon"]))
                cluster_end = q["ts"]
                j += 1
            else:
                # Punto lontano — controlla se c'è un buco GPS prima di rompere
                gap_min = (q["ts"] - cluster_end).total_seconds() / 60
                if gap_min > max_gap_min:
                    # Buco troppo grande → sosta finita davvero
                    break
                # Buco breve → potrebbe essere GPS silenzioso, non un movimento
                # Guarda se il punto DOPO questo lontano torna vicino
                if j + 1 < len(points):
                    r = points[j + 1]
                    dist_r = _haversine_m(clat, clon, r["lat"], r["lon"])
                    if dist_r <= radius_m:
                        # Era un punto anomalo (GPS drift) — salta e continua
                        j += 1
                        continue
                break

        clat, clon = _centroid(cluster_pts)

        # Ultimo cluster ancora in corso?
        is_last_cluster = (j >= len(points))
        now_utc = datetime.now(timezone.utc)
        if is_last_cluster:
            time_since_last = (now_utc - cluster_end).total_seconds() / 60
            if time_since_last < 120:
                cluster_end = now_utc

        duration_min = (cluster_end - cluster_start).total_seconds() / 60

        clusters.append({
            "lat":         clat,
            "lon":         clon,
            "start":       cluster_start,
            "end":         cluster_end,
            "minutes":     duration_min,
            "point_count": len(cluster_pts),
            "is_current":  is_last_cluster and (now_utc - cluster_end).total_seconds() < 60,
        })
        i = j

    # ── Merge cluster vicini nel tempo e nello spazio ─────────────────────
    # Se due soste consecutive sono < radius_m*2 di distanza e il gap
    # temporale tra loro è < max_gap_min, uniscile in una sola.
    merged = True
    while merged and len(clusters) > 1:
        merged = False
        new_clusters = [clusters[0]]
        for c in clusters[1:]:
            prev = new_clusters[-1]
            dist = _haversine_m(prev["lat"], prev["lon"], c["lat"], c["lon"])
            gap_min = (c["start"] - prev["end"]).total_seconds() / 60
            if dist <= radius_m * 2 and 0 <= gap_min <= max_gap_min:
                # Unisci in prev
                merged_end = max(prev["end"], c["end"])
                merged_start = min(prev["start"], c["start"])
                all_pts = [(prev["lat"], prev["lon"]), (c["lat"], c["lon"])]
                mlat, mlon = _centroid(all_pts)
                new_clusters[-1] = {
                    "lat":         mlat,
                    "lon":         mlon,
                    "start":       merged_start,
                    "end":         merged_end,
                    "minutes":     (merged_end - merged_start).total_seconds() / 60,
                    "point_count": prev["point_count"] + c["point_count"],
                    "is_current":  c.get("is_current", False),
                }
                merged = True
            else:
                new_clusters.append(c)
        clusters = new_clusters

    return clusters


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point

async def get_person_stops(
    rest_client,
    person_name: str,
    hours:        int   = DEFAULT_HOURS,
    min_stop_min: int   = DEFAULT_MIN_STOP_MIN,
    radius_m:     float = DEFAULT_RADIUS_M,
    day=None,
) -> list[dict]:
    """
    Ritorna soste significative con indirizzo reale.
    Se `day` (datetime.date locale) è indicato, restituisce solo le soste di quel
    giorno (00:00–24:00 ora locale), in ordine cronologico; `hours` deve coprire
    almeno fino a quel giorno. Senza `day` il comportamento è quello di sempre.
    Usa due fonti:
      1. device_tracker (lat/lon precisi, ma aggiornamenti radi)
      2. person.X (stato zona HA, più affidabile per durate)
    """
    # Trova device_tracker
    tracker_eid = _get_tracker_eid(person_name)
    if not tracker_eid:
        return [{"error": f"Nessun device_tracker configurato per {person_name}. "
                          f"Aggiungi \"location_tracker\": {{\"{person_name.lower()}\": \"device_tracker.XXX\"}} "
                          f"nel person_config.json"}]

    # ── Fonte 1: device_tracker (GPS preciso) ────────────────────────────────
    history = await rest_client.get_history([tracker_eid], hours=hours)
    points_raw = history.get(tracker_eid, [])
    logger.info("location_tracker [%s]: Fonte1 device_tracker → %d record grezzi", person_name, len(points_raw))

    gps_points = []
    for pt in points_raw:
        attrs = pt.get("attributes", {})
        lat = attrs.get("latitude")
        lon = attrs.get("longitude")
        if lat is None or lon is None:
            continue
        ts_str = pt.get("last_changed") or pt.get("last_updated", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        gps_points.append({"lat": float(lat), "lon": float(lon), "ts": ts})
    logger.info("location_tracker [%s]: Fonte1 → %d punti GPS validi (con lat/lon)", person_name, len(gps_points))

    # ── Fonte 2: person.X (zone changes da HA) ──────────────────────────────
    # Legge la history della entity person.X per arricchire i buchi GPS
    person_eid = f"person.{person_name.lower()}"
    try:
        ph = await rest_client.get_history([person_eid], hours=hours)
        person_states = ph.get(person_eid, [])
        logger.info("location_tracker [%s]: Fonte2 person.X → %d record", person_name, len(person_states))
        added_p2 = 0
        # Ogni state ha attributi lat/lon solo quando fuori da zone note
        for pt in person_states:
            attrs = pt.get("attributes", {})
            lat = attrs.get("latitude")
            lon = attrs.get("longitude")
            if lat is None or lon is None:
                continue
            ts_str = pt.get("last_changed") or pt.get("last_updated", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            p = {"lat": float(lat), "lon": float(lon), "ts": ts}
            # Aggiungi solo se non già coperto da device_tracker (evita duplicati)
            is_dup = any(
                abs((gp["ts"] - ts).total_seconds()) < 120 and
                _haversine_m(gp["lat"], gp["lon"], p["lat"], p["lon"]) < radius_m
                for gp in gps_points
            )
            if not is_dup:
                gps_points.append(p)
                added_p2 += 1
        logger.info("location_tracker [%s]: Fonte2 → %d punti aggiuntivi (non duplicati)", person_name, added_p2)
    except Exception as e:
        logger.debug("get_person_stops: person entity history error: %s", e)

    # ── Fonte 3: current state (posizione attuale dal REST) ──────────────────
    # Aggiunge l'ultima posizione nota direttamente dallo stato attuale
    try:
        states = await rest_client.get_states()
        for s in (states if isinstance(states, list) else []):
            if s.get("entity_id") == tracker_eid:
                attrs = s.get("attributes", {})
                lat = attrs.get("latitude")
                lon = attrs.get("longitude")
                ts_str = s.get("last_updated") or s.get("last_changed", "")
                if lat and lon and ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    p = {"lat": float(lat), "lon": float(lon), "ts": ts}
                    is_dup = any(
                        abs((gp["ts"] - ts).total_seconds()) < 300 and
                        _haversine_m(gp["lat"], gp["lon"], p["lat"], p["lon"]) < radius_m
                        for gp in gps_points
                    )
                    if not is_dup:
                        gps_points.append(p)
                        logger.info("location_tracker [%s]: Fonte3 (stato attuale) aggiunto: %.4f,%.4f @ %s",
                                    person_name, float(lat), float(lon), ts_str[:19])
                break
    except Exception as e:
        logger.debug("location_tracker: fonte3 stato attuale error: %s", e)

    if not gps_points:
        return [{"error": f"Il device_tracker {tracker_eid} non ha coordinate GPS nello storico. "
                          f"Potrebbe essere un tracker senza GPS (WiFi/BT only)."}]

    # Ordina per timestamp (le due fonti si mischiano)
    gps_points.sort(key=lambda p: p["ts"])

    # Modalità "giorno specifico": tiene solo i punti di quella data (ora locale)
    if day is not None:
        from datetime import time as _dtime, timedelta as _dtdelta
        from utils.timezone_helper import local_tz as _local_tz
        _d0 = datetime.combine(day, _dtime.min, tzinfo=_local_tz())
        _d1 = _d0 + _dtdelta(days=1)
        gps_points = [p for p in gps_points if _d0 <= p["ts"] < _d1]
        if not gps_points:
            return [{"error": f"Nessun dato GPS di {person_name} per il {day.day}/{day.month}/{day.year}. "
                              f"Home Assistant conserva lo storico solo per un numero limitato di giorni "
                              f"(di default 10, impostazione purge_keep_days del recorder) e HomeMind "
                              f"salva le soste solo da quando è installato."}]

    # Clustering con gap bridging
    clusters = _cluster_gps_points(gps_points, radius_m)

    # Filtra soste brevi
    stops = [c for c in clusters if c["minutes"] >= min_stop_min]
    if not stops:
        return []

    # Ordina per durata (per un giorno specifico: in ordine cronologico)
    if day is not None:
        stops.sort(key=lambda x: x["start"])
    else:
        stops.sort(key=lambda x: x["minutes"], reverse=True)

    # Leggi coordinate casa da HA
    home_coords = await _get_home_coords(rest_client)

    # Reverse geocoding con cache — coordinate uguali (arrotondate a ~100m)
    # non vengono geocodificate due volte. Rispetta rate limit Nominatim (1 req/sec).
    geo_cache: dict = {}  # (lat_round, lon_round) → address

    async with aiohttp.ClientSession() as session:
        for stop in stops:
            # Casa prima
            if home_coords:
                dist_home = _haversine_m(
                    stop["lat"], stop["lon"],
                    home_coords[0], home_coords[1]
                )
                if dist_home <= 200:
                    stop["address"] = "🏠 Casa"
                    continue
            # Cache lookup
            cache_key = (round(stop["lat"], 3), round(stop["lon"], 3))
            if cache_key in geo_cache:
                stop["address"] = geo_cache[cache_key]
            else:
                await asyncio.sleep(0.5)
                addr = await _reverse_geocode(stop["lat"], stop["lon"], session)
                geo_cache[cache_key] = addr
                stop["address"] = addr

    # Aggiungi campi orario locale per routine_manager
    for stop in stops:
        try:
            local_start = stop["start"].astimezone()
            local_end   = stop["end"].astimezone()
            stop["start_local_hour"]   = local_start.hour
            stop["start_local_minute"] = local_start.minute
            stop["end_local_hour"]     = local_end.hour
            stop["end_local_minute"]   = local_end.minute
        except Exception:
            stop.setdefault("start_local_hour", 0)
            stop.setdefault("start_local_minute", 0)
            stop.setdefault("end_local_hour", 0)
            stop.setdefault("end_local_minute", 0)

    return stops


# ─────────────────────────────────────────────────────────────────────────────
# Formattazione messaggio

def _fmt_duration(minutes: float) -> str:
    if minutes < 60:
        return f"{int(minutes)} min"
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h {m}min" if m else f"{h}h"

def format_stops_message(
    stops:        list[dict],
    person_name:  str,
    hours:        int,
    min_stop_min: int,
    period_label: str | None = None,
) -> str:
    ora = now_local().strftime("%H:%M")
    periodo = period_label if period_label else f"ultime {hours}h"

    # Errore
    if stops and "error" in stops[0]:
        return f"⚠️ {stops[0]['error']}"

    if not stops:
        return (
            f"📍 <b>{person_name}</b> — {periodo}\n\n"
            f"Nessuna sosta &gt; {min_stop_min} min trovata."
        )

    lines = [f"📍 <b>Soste di {person_name}</b> — {periodo}\n"]

    now_utc = datetime.now(timezone.utc)
    for i, s in enumerate(stops, 1):
        durata  = _fmt_duration(s["minutes"])
        ora_in  = s["start"].astimezone().strftime("%H:%M")
        ora_out = s["end"].astimezone().strftime("%H:%M")
        ancora  = " <b>← ora qui</b>" if (now_utc - s["end"]).total_seconds() < 180 else ""
        addr    = s.get("address", "—")

        lines.append(f"{i}. 📌 <b>{addr}</b>{ancora}")
        lines.append(f"   ⏱ {durata}  ({ora_in} → {ora_out})")

    lines.append(f"\n<i>Filtro: &gt;{min_stop_min} min, raggio {DEFAULT_RADIUS_M}m — {ora}</i>")
    return "\n".join(lines)
