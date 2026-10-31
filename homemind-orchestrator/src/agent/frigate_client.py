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

    # ── Riconoscimento targhe (LPR, Frigate >= 0.16) ───────────────────────────

    @staticmethod
    def _extract_plate(ev: dict) -> tuple[str, float | None]:
        """
        Estrae (targa, score) da un evento Frigate. Gestisce più formati:
          - ev["data"]["recognized_license_plate"]  (Frigate 0.16+)
          - ev["recognized_license_plate"]          (campo top-level)
        Restituisce ("", None) se l'evento non ha una targa.
        """
        if not isinstance(ev, dict):
            return "", None
        data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        plate = (
            data.get("recognized_license_plate")
            or ev.get("recognized_license_plate")
            or ""
        )
        score = (
            data.get("recognized_license_plate_score")
            if data.get("recognized_license_plate_score") is not None
            else ev.get("recognized_license_plate_score")
        )
        if isinstance(plate, (list, tuple)):
            plate = plate[0] if plate else ""
        plate = str(plate).strip().upper()
        try:
            score = float(score) if score is not None else None
        except (TypeError, ValueError):
            score = None
        return plate, score

    async def get_recent_plates(
        self,
        hours: float = 24,
        camera: str | None = None,
        after_ts: float | None = None,
        limit: int = 300,
    ) -> list[dict] | None:
        """
        Restituisce le targhe rilevate da Frigate (più recenti per prime).
        Ogni elemento: {plate, score, camera, time, event_id, label, known_name}
        Una stessa targa vista più volte resta come detezioni separate
        (il raggruppamento è fatto da chi formatta la risposta).

        Restituisce None se Frigate non risponde (diverso da lista vuota =
        nessuna targa rilevata nel periodo).
        Endpoint: GET /api/events?after=<ts>&limit=N[&cameras=cam]
        """
        if not self.is_ready():
            return None

        import time as _time
        now = _time.time()
        after = after_ts if after_ts is not None else now - max(0.1, float(hours)) * 3600
        params = {"after": f"{after:.0f}", "limit": str(int(limit)), "include_thumbnails": "0"}
        if camera:
            params["cameras"] = camera

        url = f"{self._base_url}/api/events"
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=12)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.warning("Frigate plates: HTTP %d", resp.status)
                        return None
                    events = await resp.json(content_type=None)
        except Exception as e:
            logger.error("Frigate plates errore: %s", e)
            return None

        if not isinstance(events, list):
            logger.warning("Frigate plates: risposta inattesa (%s)", type(events).__name__)
            return None

        results: list[dict] = []
        for ev in events:
            plate, score = self._extract_plate(ev)
            if not plate:
                continue
            try:
                ts = float(ev.get("start_time") or 0)
            except (TypeError, ValueError):
                ts = 0.0
            results.append({
                "plate":      plate,
                "score":      score,
                "camera":     ev.get("camera", "?"),
                "time":       ts,
                "event_id":   ev.get("id", ""),
                "label":      ev.get("label", ""),
                # In Frigate, se la targa è tra quelle "note" il sub_label ne è il nome
                "known_name": ev.get("sub_label") if isinstance(ev.get("sub_label"), str) else None,
            })
        results.sort(key=lambda r: r["time"], reverse=True)
        logger.info("Frigate plates: %d targhe in %d eventi (%.1fh)", len(results), len(events), hours)
        return results

    async def get_recent_detections(
        self,
        labels: list[str] | None = None,
        camera: str | None = None,
        after_ts: float | None = None,
        hours: float = 24,
        limit: int = 300,
    ) -> list[dict] | None:
        """
        Rilevamenti generici di Frigate (person, dog, cat, car, package, ...),
        più recenti per primi. Ogni elemento:
          {label, camera, time, end, score, event_id, has_snapshot, name}
        `name` = sub_label (es. volto riconosciuto o classificazione) se presente.
        None se Frigate non risponde; lista vuota se nessun rilevamento.
        Endpoint: GET /api/events?after=..&labels=a,b&cameras=cam
        """
        if not self.is_ready():
            return None

        import time as _time
        after = after_ts if after_ts is not None else _time.time() - max(0.1, float(hours)) * 3600
        params = {"after": f"{after:.0f}", "limit": str(int(limit)), "include_thumbnails": "0"}
        if labels:
            params["labels"] = ",".join(labels)
        if camera:
            params["cameras"] = camera

        url = f"{self._base_url}/api/events"
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=12)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.warning("Frigate detections: HTTP %d", resp.status)
                        return None
                    events = await resp.json(content_type=None)
        except Exception as e:
            logger.error("Frigate detections errore: %s", e)
            return None

        if not isinstance(events, list):
            logger.warning("Frigate detections: risposta inattesa (%s)", type(events).__name__)
            return None

        results: list[dict] = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
            try:
                ts = float(ev.get("start_time") or 0)
            except (TypeError, ValueError):
                ts = 0.0
            score = data.get("top_score")
            if score is None:
                score = ev.get("top_score", data.get("score"))
            try:
                score = float(score) if score is not None else None
            except (TypeError, ValueError):
                score = None
            sub = ev.get("sub_label")
            if isinstance(sub, (list, tuple)):
                sub = sub[0] if sub else None
            results.append({
                "label":        str(ev.get("label", "?")),
                "camera":       ev.get("camera", "?"),
                "time":         ts,
                "end":          ev.get("end_time"),
                "score":        score,
                "event_id":     ev.get("id", ""),
                "has_snapshot": ev.get("has_snapshot"),
                "name":         sub if isinstance(sub, str) and sub else None,
            })
        results.sort(key=lambda r: r["time"], reverse=True)
        logger.info("Frigate detections: %d eventi (labels=%s)", len(results), labels)
        return results

    async def get_event(self, event_id: str) -> dict | None:
        """Dettaglio aggiornato di un evento (score, end_time...). None se non disponibile."""
        if not self.is_ready() or not event_id:
            return None
        url = f"{self._base_url}/api/events/{event_id}"
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    ev = await resp.json(content_type=None)
                    return ev if isinstance(ev, dict) else None
        except Exception as e:
            logger.debug("Frigate get_event '%s' errore: %s", event_id, e)
            return None

    async def get_event_snapshot(self, event_id: str) -> bytes | None:
        """Snapshot JPEG di un evento (es. quello di una targa). None se non disponibile."""
        if not self.is_ready() or not event_id:
            return None
        url = f"{self._base_url}/api/events/{event_id}/snapshot.jpg"
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params={"bbox": "1"}) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    logger.warning("Frigate event snapshot '%s': HTTP %d", event_id, resp.status)
                    return None
        except Exception as e:
            logger.error("Frigate event snapshot '%s' errore: %s", event_id, e)
            return None

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
