"""
anomaly_tracker.py — Persistente tracking anomalie con cooldown.
Evita spam Telegram: notifica max 1 volta ogni N ore per entità.
Persiste su disco per sopravvivere ai riavvii.
"""
import json
import logging
import aiofiles
from pathlib import Path
from datetime import datetime, timedelta
from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.anomaly_tracker")

TRACKER_FILE     = Path("/config/homemind_patches/anomaly_tracker.json")
NOTIFY_COOLDOWN  = timedelta(hours=4)   # Notifica stessa entità max ogni 4h
AUTOFIX_COOLDOWN = timedelta(hours=24)  # Auto-fix stessa entità max ogni 24h


class AnomalyTracker:
    def __init__(self):
        self._data: dict = {}  # {entity_id: {last_notified, last_fixed, reason}}

    async def load(self):
        if TRACKER_FILE.exists():
            try:
                async with aiofiles.open(str(TRACKER_FILE), "r") as f:
                    self._data = json.loads(await f.read())
                logger.info(f"Anomaly tracker loaded: {len(self._data)} entries")
            except Exception as e:
                logger.warning(f"Could not load tracker: {e}")
                self._data = {}

    async def save(self):
        TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with aiofiles.open(str(TRACKER_FILE), "w") as f:
                await f.write(json.dumps(self._data, default=str, indent=2))
        except Exception as e:
            logger.warning(f"Could not save tracker: {e}")

    def should_notify(self, entity_id: str, reason: str) -> bool:
        """True se dobbiamo mandare notifica (rispetta cooldown)."""
        entry = self._data.get(entity_id, {})
        last_str = entry.get("last_notified")
        if not last_str:
            return True
        try:
            last = datetime.fromisoformat(last_str)
            if datetime.utcnow() - last > NOTIFY_COOLDOWN:
                return True
            # Reason cambiata → notifica comunque
            if entry.get("reason", "") != reason[:100]:
                return True
            return False
        except Exception:
            return True

    def should_autofix(self, entity_id: str) -> bool:
        """True se possiamo fare auto-fix (rispetta cooldown più lungo)."""
        entry = self._data.get(entity_id, {})
        last_str = entry.get("last_fixed")
        if not last_str:
            return True
        try:
            last = datetime.fromisoformat(last_str)
            return datetime.utcnow() - last > AUTOFIX_COOLDOWN
        except Exception:
            return True

    async def mark_notified(self, entity_id: str, reason: str):
        if entity_id not in self._data:
            self._data[entity_id] = {}
        self._data[entity_id]["last_notified"] = datetime.utcnow().isoformat()
        self._data[entity_id]["reason"] = reason[:100]
        await self.save()

    async def mark_fixed(self, entity_id: str):
        if entity_id not in self._data:
            self._data[entity_id] = {}
        self._data[entity_id]["last_fixed"] = datetime.utcnow().isoformat()
        await self.save()

    def get_stats(self) -> dict:
        return {
            eid: {
                "last_notified": v.get("last_notified", "mai"),
                "last_fixed":    v.get("last_fixed", "mai"),
            }
            for eid, v in self._data.items()
        }
