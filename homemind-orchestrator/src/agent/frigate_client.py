"""
agent/frigate_client.py — Integrazione Frigate NVR per HomeMind.

Recupera snapshot dalle camere Frigate via API HTTP diretta.
Funziona con Frigate installato su qualsiasi host nella rete locale,
indipendentemente da Home Assistant.

Configurazione in person_config.json:
  "frigate": {
    "enabled": true,
    "host": "192.168.1.119",
    "port": 5000,
    "snapshot_on_alarm": true,
    "cameras": {
      "ingresso": "binary_sensor.0x000d6ffffe1a246d_occupancy",
      "garage":   "binary_sensor.0x00158d0001ae9a1b_occupancy"
    }
  }
"""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger("homemind.frigate")


class FrigateClient:
    """Client per l'API REST di Frigate NVR."""

    def __init__(self, config: dict):
        """
        config è il dict della sezione 'frigate' in person_config.json.
        Esempio:
          {
            "enabled": true,
            "host": "192.168.1.119",
            "port": 5000,
            "snapshot_on_alarm": true,
            "cameras": {
              "ingresso": "binary_sensor.xxx_occupancy",
              "garage":   "binary_sensor.yyy_occupancy"
            }
          }
        """
        self.enabled          = bool(config.get("enabled", False))
        self.host             = config.get("host", "").strip()
        self.port             = int(config.get("port", 5000))
        self.snapshot_on_alarm= bool(config.get("snapshot_on_alarm", True))
        # cameras: { nome_cam_frigate: entity_id_sensore_movimento }
        self.cameras: dict    = config.get("cameras", {})
        self._base_url        = f"http://{self.host}:{self.port}"

        if self.enabled and self.host:
            logger.info(
                "FrigateClient: connessione a %s — %d camere configurate",
                self._base_url, len(self.cameras)
            )
        elif self.enabled and not self.host:
            logger.warning("FrigateClient: enabled=true ma host non configurato — disabilitato")
            self.enabled = False

    # ── API pubblica ───────────────────────────────────────────────────────────

    def is_ready(self) -> bool:
        return self.enabled and bool(self.host)

    def camera_for_sensor(self, sensor_entity_id: str) -> str | None:
        """Restituisce il nome della camera Frigate associata a un sensore movimento."""
        for cam_name, sensor_eid in self.cameras.items():
            if sensor_eid == sensor_entity_id:
                return cam_name
        return None

    def all_cameras(self) -> list[str]:
        """Lista di tutti i nomi camera configurati."""
        return list(self.cameras.keys())

    async def get_snapshot(self, camera_name: str) -> bytes | None:
        """
        Recupera l'ultimo snapshot JPEG di una camera.
        Endpoint Frigate: GET /api/{camera}/latest.jpg
        Non salva nulla su disco — immagine servita dalla RAM di Frigate.
        Restituisce i bytes JPEG o None in caso di errore.
        """
        if not self.is_ready():
            return None

        url = f"{self._base_url}/api/{camera_name}/latest.jpg"
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        logger.info(
                            "Frigate snapshot '%s': %d bytes", camera_name, len(data)
                        )
                        return data
                    else:
                        logger.warning(
                            "Frigate snapshot '%s': HTTP %d", camera_name, resp.status
                        )
                        return None
        except Exception as e:
            logger.error("Frigate snapshot '%s' errore: %s", camera_name, e)
            return None

    async def get_all_snapshots(self) -> dict[str, bytes]:
        """
        Recupera snapshot da tutte le camere configurate in parallelo.
        Restituisce {nome_camera: bytes_jpeg} per quelle riuscite.
        """
        if not self.is_ready() or not self.cameras:
            return {}

        tasks = {
            cam: asyncio.create_task(self.get_snapshot(cam))
            for cam in self.cameras
        }
        results = {}
        for cam, task in tasks.items():
            try:
                data = await task
                if data:
                    results[cam] = data
            except Exception as e:
                logger.error("Frigate get_all_snapshots '%s': %s", cam, e)
        return results

    async def ping(self) -> bool:
        """Verifica che Frigate sia raggiungibile."""
        if not self.is_ready():
            return False
        try:
            import aiohttp
            url = f"{self._base_url}/api/version"
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    ok = resp.status == 200
                    if ok:
                        text = await resp.text()
                        logger.info("Frigate raggiungibile — versione: %s", text.strip())
                    return ok
        except Exception as e:
            logger.warning("Frigate non raggiungibile (%s:%d): %s", self.host, self.port, e)
            return False


def load_frigate_client(person_config: dict) -> FrigateClient | None:
    """
    Legge la sezione 'frigate' da person_config.json e crea il client.
    Restituisce None se la sezione non esiste o enabled=false.
    """
    frigate_cfg = person_config.get("frigate")
    if not frigate_cfg:
        logger.debug("Frigate: sezione 'frigate' non presente in person_config.json — skip")
        return None
    if not frigate_cfg.get("enabled", False):
        logger.info("Frigate: disabled (enabled=false)")
        return None
    return FrigateClient(frigate_cfg)
