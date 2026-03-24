"""
ha_client/rest_client.py - Async REST client for Home Assistant API.
"""
import os, logging, aiofiles, aiohttp
from datetime import datetime, timezone

logger = logging.getLogger("homemind.rest")


class HARestClient:
    def __init__(self, token: str):
        self.base    = os.getenv("HA_REST_BASE", "http://supervisor/core/api")
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self._session: aiohttp.ClientSession | None = None
        self._log_path     = os.getenv("HM_HA_LOG_PATH", "")
        self._log_endpoint = None

    async def start(self):
        self._session = aiohttp.ClientSession(headers=self.headers)
        if not self._log_path:
            await self._discover_log_endpoint()

    async def _discover_log_endpoint(self):
        for url in [f"{self.base}/logs/error", f"{self.base}/error_log"]:
            try:
                async with self._session.get(url) as r:
                    if r.status == 200:
                        self._log_endpoint = url
                        logger.info("Log endpoint: %s", url)
                        return
            except Exception:
                continue
        logger.warning("No working log endpoint found — log analysis will be skipped.")

    async def stop(self):
        if self._session:
            await self._session.close()

    async def get_states(self) -> list:
        async with self._session.get(f"{self.base}/states") as r:
            r.raise_for_status(); return await r.json()

    async def get_state(self, entity_id: str) -> dict:
        async with self._session.get(f"{self.base}/states/{entity_id}") as r:
            r.raise_for_status(); return await r.json()

    async def call_service(self, domain: str, service: str, data: dict = None, target: dict = None) -> list:
        url     = f"{self.base}/services/{domain}/{service}"
        payload = dict(data or {})
        if target: payload.update(target)
        logger.debug("call_service %s/%s %s", domain, service, payload)
        async with self._session.post(url, json=payload) as r:
            if not r.ok:
                body = await r.text()
                logger.error("SVC FAIL %s %s: %s payload=%s", r.status, url, body, payload)
            r.raise_for_status(); return await r.json()

    async def get_error_log(self) -> str:
        if self._log_path:
            try:
                async with aiofiles.open(self._log_path, "r", errors="replace") as f:
                    c = await f.read()
                return c[-8000:] if len(c) > 8000 else c
            except Exception as e:
                logger.warning("Log file read failed: %s", e)
        if self._log_endpoint:
            try:
                async with self._session.get(self._log_endpoint) as r:
                    if r.status == 200:
                        t = await r.text()
                        return t[-8000:] if len(t) > 8000 else t
            except Exception as e:
                logger.debug("REST log failed: %s", e)
        return ""

    async def get_config(self) -> dict:
        async with self._session.get(f"{self.base}/config") as r:
            r.raise_for_status(); return await r.json()

    async def post_lovelace(self, dashboard_yaml: str) -> dict:
        url = f"{self.base}/lovelace/config"
        async with self._session.post(url, data=dashboard_yaml,
                                       headers={**self.headers, "Content-Type": "application/yaml"}) as r:
            r.raise_for_status(); return await r.json()

    # ── History & Statistics ────────────────────────────────────────────────

    async def get_history(self, entity_ids: list, hours: int = 24) -> dict:
        """
        Ritorna history per una o piu entita.
        {entity_id: [{state, last_changed, ...}, ...]}
        API HA: GET /api/history/period/{start}?filter_entity_id={eids}&end_time={end}
        """
        from datetime import timedelta
        end   = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        fmt   = "%Y-%m-%dT%H:%M:%S.000Z"
        eids  = ",".join(entity_ids)
        url   = (f"{self.base}/history/period/{start.strftime(fmt)}"
                 f"?filter_entity_id={eids}"
                 f"&end_time={end.strftime(fmt)}")
        logger.debug("get_history URL: %s", url[:120])
        try:
            async with self._session.get(url) as r:
                if r.status != 200:
                    body = await r.text()
                    logger.warning("get_history HTTP %d --- %s", r.status, body[:200])
                    return {}
                data = await r.json()
                result = {}
                for group in data:
                    if not group:
                        continue
                    eid = group[0].get("entity_id", "")
                    if not eid:
                        continue
                    result[eid] = group
                    logger.info("get_history %s: %d entries, prima=%s ultima=%s",
                                eid, len(group),
                                group[0].get("last_changed","?")[:19],
                                group[-1].get("last_changed","?")[:19])
                return result
        except Exception as e:
            logger.warning("History fetch failed: %s", e)
            return {}

    async def get_statistics(self, entity_ids: list, period: str = "day", hours: int = 168) -> dict:
        """
        Statistiche long-term (energy kWh ecc.) via HA statistics API.
        period: "hour" | "day" | "month"
        """
        from datetime import timedelta
        end   = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        url   = f"{self.base}/history/statistics"
        payload = {
            "start_time": start.isoformat(),
            "end_time":   end.isoformat(),
            "statistic_ids": entity_ids,
            "period":     period,
            "types":      ["sum", "mean", "min", "max", "state"],
        }
        try:
            async with self._session.post(url, json=payload) as r:
                if r.status != 200:
                    logger.debug("Statistics API %s: %s", r.status, await r.text())
                    return {}
                return await r.json()
        except Exception as e:
            logger.warning("Statistics fetch failed: %s", e)
            return {}

    # ── HA Repairs API ──────────────────────────────────────────────────────

    async def get_repairs(self) -> list:
        """Legge issue/repairs ufficiali HA."""
        try:
            async with self._session.get(f"{self.base}/repairs/issues") as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get("issues", [])
                return []
        except Exception as e:
            logger.warning("Repairs API failed: %s", e)
            return []

    async def dismiss_repair(self, issue_id: str) -> bool:
        """Dismissi un repair issue."""
        try:
            async with self._session.delete(f"{self.base}/repairs/issues/{issue_id}") as r:
                return r.status in (200, 204)
        except Exception:
            return False

    # ── Automations ─────────────────────────────────────────────────────────

    async def get_automations(self) -> list:
        """Lista tutte le automazioni."""
        try:
            async with self._session.get(f"{self.base}/states") as r:
                r.raise_for_status()
                states = await r.json()
                return [s for s in states if s["entity_id"].startswith("automation.")]
        except Exception as e:
            logger.warning("Get automations failed: %s", e)
            return []

    async def trigger_automation(self, entity_id: str) -> bool:
        try:
            await self.call_service("automation", "trigger", {}, target={"entity_id": entity_id})
            return True
        except Exception:
            return False

    async def create_automation(self, yaml_config: str) -> dict:
        """
        Crea una nuova automazione tramite API config di HA.
        Usa POST /api/config/automation/config/<uuid>
        Ritorna {"ok": True, "id": "..."} o {"ok": False, "error": "..."}
        """
        import uuid, yaml as _yaml
        try:
            # Valida YAML prima di inviare
            parsed = _yaml.safe_load(yaml_config)
            if not isinstance(parsed, dict):
                return {"ok": False, "error": "YAML non valido: deve essere un mapping"}

            # Genera ID univoco se non presente
            auto_id = parsed.get("id") or ("homemind_" + str(uuid.uuid4())[:8])
            parsed["id"] = auto_id

            url = f"{self.base}/config/automation/config/{auto_id}"
            async with self._session.post(url, json=parsed) as r:
                body = await r.text()
                if r.status in (200, 201):
                    logger.info("Automazione creata: %s", auto_id)
                    # Ricarica automazioni HA
                    try:
                        await self.call_service("automation", "reload", {})
                    except Exception:
                        pass
                    return {"ok": True, "id": auto_id}
                else:
                    logger.warning("create_automation HTTP %d: %s", r.status, body[:200])
                    return {"ok": False, "error": f"HTTP {r.status}: {body[:150]}"}
        except Exception as e:
            logger.error("create_automation FAIL: %s", e)
            return {"ok": False, "error": str(e)}

    # ── Weather ─────────────────────────────────────────────────────────────

    async def get_weather(self) -> dict | None:
        """Prende il primo weather entity disponibile."""
        try:
            async with self._session.get(f"{self.base}/states") as r:
                r.raise_for_status()
                states = await r.json()
                for s in states:
                    if s["entity_id"].startswith("weather."):
                        return s
        except Exception:
            pass
        return None
