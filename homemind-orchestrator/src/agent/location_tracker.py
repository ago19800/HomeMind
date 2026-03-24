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

DEFAULT_MIN_STOP_MIN = 10    # minuti minimi per non essere transito
DEFAULT_HOURS        = 24    # ore di storico
DEFAULT_RADIUS_M     = 150   # metri: punti entro questo raggio = stessa sosta
MAX_GEOCODE_CALLS    = 10    # limite chiamate Nominatim per risposta


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

def _cluster_gps_points(points: list[dict], radius_m: float) -> list[dict]:
    """
    Raggruppa punti GPS vicini in soste.
    Ogni punto: {"lat": float, "lon": float, "ts": datetime}
    Ritorna: [{"lat", "lon", "start", "end", "minutes", "point_count"}, ...]
    """
    if not points:
        return []

    clusters = []
    i = 0
    while i < len(points):
        p = points[i]
        # Inizia cluster
        cluster_pts  = [(p["lat"], p["lon"])]
        cluster_start = p["ts"]
        cluster_end   = p["ts"]
        j = i + 1

        while j < len(points):
            q = points[j]
            clat, clon = _centroid(cluster_pts)
            dist = _haversine_m(clat, clon, q["lat"], q["lon"])
            if dist <= radius_m:
                cluster_pts.append((q["lat"], q["lon"]))
                cluster_end = q["ts"]
                j += 1
            else:
                break

        clat, clon = _centroid(cluster_pts)

        # Se è l'ultimo cluster E non ci sono punti successivi → la sosta
        # potrebbe essere ancora in corso: estendi "end" fino ad adesso
        is_last_cluster = (j >= len(points))
        now_utc = datetime.now(timezone.utc)
        if is_last_cluster:
            time_since_last = (now_utc - cluster_end).total_seconds() / 60
            # Se l'ultimo punto è recente (< 2h) → persona probabilmente ancora lì
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

    return clusters


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point

async def get_person_stops(
    rest_client,
    person_name: str,
    hours:        int   = DEFAULT_HOURS,
    min_stop_min: int   = DEFAULT_MIN_STOP_MIN,
    radius_m:     float = DEFAULT_RADIUS_M,
) -> list[dict]:
    """
    Ritorna soste significative con indirizzo reale.
    """
    # Trova device_tracker
    tracker_eid = _get_tracker_eid(person_name)
    if not tracker_eid:
        return [{"error": f"Nessun device_tracker configurato per {person_name}. "
                          f"Aggiungi \"location_tracker\": {{\"{person_name.lower()}\": \"device_tracker.XXX\"}} "
                          f"nel person_config.json"}]

    # Scarica history
    history = await rest_client.get_history([tracker_eid], hours=hours)
    points_raw = history.get(tracker_eid, [])

    if not points_raw:
        return [{"error": f"Nessun dato GPS per {tracker_eid} nelle ultime {hours}h"}]

    # Estrai punti con GPS valido
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

    if not gps_points:
        return [{"error": f"Il device_tracker {tracker_eid} non ha coordinate GPS nello storico. "
                          f"Potrebbe essere un tracker senza GPS (WiFi/BT only)."}]

    # Clustering
    clusters = _cluster_gps_points(gps_points, radius_m)

    # Filtra soste brevi
    stops = [c for c in clusters if c["minutes"] >= min_stop_min]
    if not stops:
        return []

    # Ordina per durata
    stops.sort(key=lambda x: x["minutes"], reverse=True)

    # Leggi coordinate casa da HA
    home_coords = await _get_home_coords(rest_client)

    # Reverse geocoding (max MAX_GEOCODE_CALLS, poi coordinate raw)
    async with aiohttp.ClientSession() as session:
        for i, stop in enumerate(stops):
            # Controlla se la sosta è a casa (entro 200m)
            if home_coords:
                dist_home = _haversine_m(
                    stop["lat"], stop["lon"],
                    home_coords[0], home_coords[1]
                )
                if dist_home <= 200:
                    stop["address"] = "🏠 Casa"
                    continue
            if i < MAX_GEOCODE_CALLS:
                await asyncio.sleep(0.5)  # rispetta rate limit Nominatim (1 req/sec)
                stop["address"] = await _reverse_geocode(stop["lat"], stop["lon"], session)
            else:
                stop["address"] = f"({stop['lat']:.4f}, {stop['lon']:.4f})"

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
) -> str:
    ora = now_local().strftime("%H:%M")

    # Errore
    if stops and "error" in stops[0]:
        return f"⚠️ {stops[0]['error']}"

    if not stops:
        return (
            f"📍 <b>{person_name}</b> — ultime {hours}h\n\n"
            f"Nessuna sosta &gt; {min_stop_min} min trovata."
        )

    lines = [f"📍 <b>Soste di {person_name}</b> — ultime {hours}h\n"]

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
