"""Soste GPS: orari dei punti (last_updated), zone di HA e vista cronologica."""
import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
try:
    import aiohttp  # noqa: F401
except ImportError:                                   # ambiente di test senza aiohttp
    _m = types.ModuleType("aiohttp")
    _m.ClientTimeout = lambda **k: None
    _m.ClientSession = object
    sys.modules["aiohttp"] = _m

try:
    import aiofiles  # noqa: F401
except ImportError:                                   # ambiente di test senza aiofiles
    sys.modules["aiofiles"] = types.ModuleType("aiofiles")

from agent import location_tracker as lt  # noqa: E402

HOME = (42.2300, 14.3900)
WORK = (42.0600, 14.4400)      # ~19 km da casa
SHOP = (42.2400, 14.4000)      # ~1,3 km da casa (fuori dal raggio di casa)


def run(c):
    return asyncio.run(c)


class _Session:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class Rest:
    def __init__(self, points, tracker_last_changed):
        self.points = points
        self.lc = tracker_last_changed

    async def get_history(self, eids, hours=24, full_attributes=False):
        out = {}
        for e in eids:
            if e.startswith("device_tracker."):
                out[e] = [{"state": "not_home", "last_changed": self.lc.isoformat(),
                           "last_updated": ts.isoformat(),
                           "attributes": {"latitude": la, "longitude": lo}} for ts, la, lo in self.points]
        return out

    async def get_states(self):
        return [
            {"entity_id": "zone.home", "attributes": {"latitude": HOME[0], "longitude": HOME[1], "radius": 100, "friendly_name": "Casa"}},
            {"entity_id": "zone.lavoro", "attributes": {"latitude": WORK[0], "longitude": WORK[1], "radius": 150, "friendly_name": "Lavoro"}},
        ]


def _day_points(now):
    """Ogni 10 min: casa fino alle 08:00, lavoro 08:30–17:00, negozio 17:30–18:10, casa dopo le 18:40."""
    t0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    pts = []
    t = t0
    while t <= now:
        h = t.hour + t.minute / 60
        if h < 8: pos = HOME
        elif h < 8.5: pos = (42.15, 14.41)           # in viaggio
        elif h < 17: pos = WORK
        elif h < 17.5: pos = (42.15, 14.41)
        elif h < 18.2: pos = SHOP
        elif h < 18.6: pos = (42.236, 14.395)
        else: pos = HOME
        pts.append((t, pos[0], pos[1]))
        t += timedelta(minutes=10)
    return pts


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(lt, "_get_tracker_eid", lambda p: "device_tracker.tel")
    monkeypatch.setattr(lt.aiohttp, "ClientSession", lambda *a, **k: _Session())
    async def geo(lat, lon, session): return f"Via Test {lat:.2f}"
    monkeypatch.setattr(lt, "_reverse_geocode", geo)


def test_pt_ts_usa_last_updated():
    assert lt._pt_ts({"last_changed": "A", "last_updated": "B"}) == "B"
    assert lt._pt_ts({"last_changed": "A"}) == "A"
    assert lt._pt_ts({}) == ""


def test_soste_giornata_con_last_changed_fermo(setup):
    """Bug: tutti i punti avevano la stessa last_changed → una sola sosta di 24h."""
    now = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
    if now > datetime.now(timezone.utc):
        now -= timedelta(days=1)
    pts = _day_points(now)
    rest = Rest(pts, tracker_last_changed=pts[0][0])           # last_changed fermo a inizio giornata
    stops = run(lt.get_person_stops(rest, "agostino", hours=30, min_stop_min=10, chronological=True))
    names = [s["address"] for s in stops]
    assert len(stops) >= 3, names
    assert "🏠 Casa" in names and "📍 Lavoro" in names             # zone di HA riconosciute
    assert stops == sorted(stops, key=lambda s: s["start"])          # cronologico
    assert max(s["minutes"] for s in stops) < 24 * 60 - 60           # non più un'unica sosta di 24h


def test_vista_cronologica_con_viaggi(setup):
    now = datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0)
    if now > datetime.now(timezone.utc):
        now -= timedelta(days=1)
    pts = _day_points(now)
    rest = Rest(pts, tracker_last_changed=pts[0][0])
    stops = run(lt.get_person_stops(rest, "agostino", hours=30, min_stop_min=10, chronological=True))
    msg = lt.format_stops_message(stops, "Agostino", 30, 10, timeline=True)
    assert "Spostamenti di Agostino" in msg and "🚗" in msg and "km" in msg
    assert msg.index("Casa") < msg.index("Lavoro")                    # ordine della giornata
    # la vista classica resta com'era
    classic = lt.format_stops_message(stops, "Agostino", 30, 10)
    assert "Soste di Agostino" in classic and "🚗" not in classic


def test_match_zone():
    zones = [{"name": "Casa", "lat": HOME[0], "lon": HOME[1], "radius": 100, "is_home": True},
             {"name": "Lavoro", "lat": WORK[0], "lon": WORK[1], "radius": 150, "is_home": False}]
    assert lt._match_zone(*HOME, zones)["name"] == "Casa"
    assert lt._match_zone(*WORK, zones)["name"] == "Lavoro"
    assert lt._match_zone(*SHOP, zones) is None


class _Resp:
    status = 200
    async def json(self): return []
    async def text(self): return ""
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class _Sess:
    def __init__(self): self.urls = []
    def get(self, url, **k):
        self.urls.append(url)
        return _Resp()


def test_get_history_full_attributes_omette_minimal_response():
    """HA tratta minimal_response come flag a presenza (anche =false): per avere lat/lon su TUTTI i punti
    va omesso; gli altri chiamanti restano com'erano."""
    from ha_client.rest_client import HARestClient
    c = HARestClient("tok")
    c._session = _Sess()
    run(c.get_history(["device_tracker.x"], hours=24, full_attributes=True))
    run(c.get_history(["sensor.enel"], hours=24))
    full, legacy = c._session.urls
    assert "minimal_response" not in full and "significant_changes_only=0" in full
    assert "minimal_response=false" in legacy                      # invariato per energia, grafici, ecc.


def test_tracciamento_gps_chiede_gli_attributi_completi(monkeypatch):
    calls = []
    class R:
        async def get_history(self, eids, hours=24, full_attributes=False):
            calls.append((eids[0], full_attributes)); return {}
        async def get_states(self): return []
    monkeypatch.setattr(lt, "_get_tracker_eid", lambda p: "device_tracker.tel")
    run(lt.get_person_stops(R(), "agostino", hours=24))
    assert ("device_tracker.tel", True) in calls and ("person.agostino", True) in calls
