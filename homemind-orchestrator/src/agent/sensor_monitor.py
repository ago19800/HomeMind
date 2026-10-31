"""
agent/sensor_monitor.py — Anomaly detection + Security orchestration.
"""
import asyncio
import json
import logging
import re
from collections import defaultdict
from datetime import datetime

from agent.ai_provider import AIProvider, SYSTEM_ANOMALY_DETECTOR, SYSTEM_PATCH_GENERATOR
from agent.anomaly_tracker import AnomalyTracker
from agent.patch_writer import PatchWriter
from agent.config_reader import ConfigReader
from agent.home_model import HomeModel
from agent.security_manager import SecurityManager

logger = logging.getLogger("homemind.sensor_monitor")

EXCLUDE_ENTITIES = {
    "sensor.date", "sensor.time", "sensor.date_time", "sensor.date_time_utc",
    "sensor.date_time_iso", "sensor.time_date", "sensor.time_utc", "sensor.internet_time",
}
PRIORITY_DOMAINS = {
    "light", "switch", "climate", "cover", "fan", "media_player",
    "person", "device_tracker", "binary_sensor", "alarm_control_panel",
}
SENSOR_DEVICE_CLASSES = {"power", "energy", "temperature", "battery"}
KEEP_ATTRS = {"friendly_name", "device_class", "unit_of_measurement", "battery_level"}
MAX_ENTITIES = 20


class SensorMonitor:
    def __init__(self, ai: AIProvider, ws_client, rest_client,
                 auto_fix: bool = False, poll_interval: int = 30,
                 notifier=None, alarm_code: str = "1234"):
        self.ai            = ai
        self.ws            = ws_client
        self.rest          = rest_client
        self.auto_fix      = auto_fix
        self.poll_interval = poll_interval
        self.notifier      = notifier
        self._state_cache:   dict[str, dict] = {}
        self._usage_counter: dict[str, int]  = defaultdict(int)
        self._last_anomalies: list[dict]     = []
        self._tracker       = AnomalyTracker()
        self._patcher       = PatchWriter()
        self._config_reader = ConfigReader()
        self._home          = HomeModel()
        self._security      = SecurityManager(
            home=self._home, rest_client=rest_client,
            notifier=notifier, alarm_code=alarm_code
        )
        self._cycle_count   = 0

    def register_handlers(self):
        self.ws.on_event("state_changed", self._on_state_changed)
        logger.info("Sensor monitor registered state_changed handler.")

    async def _on_state_changed(self, event: dict):
        data      = event.get("data", {})
        eid       = data.get("entity_id", "")
        new_state = data.get("new_state")
        old_state = data.get("old_state")
        if new_state:
            self._state_cache[eid] = new_state
            self._usage_counter[eid] += 1
        ns = (new_state or {}).get("state", "")
        os = (old_state or {}).get("state", "")
        if ns != os:
            asyncio.create_task(
                self._security.on_state_changed(eid, os, ns),
                name=f"sec_{eid}"
            )

    async def run_forever(self):
        # Load persistent state
        await self._tracker.load()
        await self._config_reader.load()

        # Seed state cache
        logger.info(f"Sensor monitor started (interval={self.poll_interval}s)")
        all_states = await self.rest.get_states()
        for s in all_states:
            self._state_cache[s["entity_id"]] = s

        # Build home model
        self._home.build_from_cache(self._state_cache)
        await self._home.save()

        logger.info(f"Seeded state cache with {len(self._state_cache)} entities.")
        self._log_home_summary()

        while True:
            await asyncio.sleep(self.poll_interval)
            try:
                await self._anomaly_cycle()
            except Exception as e:
                logger.error(f"Anomaly cycle failed: {e}", exc_info=True)

    def _log_home_summary(self):
        s = self._home.summary()
        logger.info(f"🏠 Casa: {'VUOTA' if s['everyone_away'] else 'OCCUPATA'}")
        if s["who_is_home"]:
            logger.info(f"  In casa: {', '.join(s['who_is_home'])}")
        logger.info(f"  Sensori movimento: {s['motion_sensors']}")
        logger.info(f"  Allarme: {s['alarm_entity'] or 'non trovato'} → {s['alarm_state']}")

    # ── Anomaly detection ──────────────────────────────────────────────────────

    def _should_include(self, eid: str, state: dict) -> bool:
        if eid in EXCLUDE_ENTITIES:
            return False
        domain = eid.split(".")[0]
        if state["state"] in ("unavailable", "unknown"):
            return False
        if domain in PRIORITY_DOMAINS:
            return True
        if domain == "sensor":
            dc = state.get("attributes", {}).get("device_class", "")
            return dc in SENSOR_DEVICE_CLASSES
        return False

    async def _anomaly_cycle(self):
        if not self._state_cache:
            return

        self._cycle_count += 1
        # Rebuild home model ogni 20 cicli (~10 min)
        if self._cycle_count % 20 == 0:
            self._home.build_from_cache(self._state_cache)
            await self._home.save()
        # Reload config ogni 10 cicli (~5 min)
        if self._cycle_count % 10 == 0:
            await self._config_reader.load()

        candidates = sorted(
            [(eid, s) for eid, s in self._state_cache.items()
             if self._should_include(eid, s)],
            key=lambda x: self._usage_counter.get(x[0], 0), reverse=True
        )[:MAX_ENTITIES]
        if not candidates:
            return

        snapshot = [
            {"id": eid, "state": s["state"],
             "attrs": {k: v for k, v in s.get("attributes", {}).items() if k in KEEP_ATTRS}}
            for eid, s in candidates
        ]

        known = self._config_reader.get_known_sensors_summary(40)
        system_prompt = SYSTEM_ANOMALY_DETECTOR.replace("{known_sensors}", known)

        try:
            raw = await self.ai.ask(
                system_prompt,
                f"Entities:\n{json.dumps(snapshot, separators=(',',':'))}",
                max_tokens=512, json_mode=True,
            )
        except Exception as e:
            logger.warning(f"AI anomaly call failed: {e}")
            return

        if not raw or not raw.strip():
            return
        clean = re.sub(r"^```[a-z]*\n?", "", raw.strip())
        clean = re.sub(r"\n?```$", "", clean)
        try:
            result = json.loads(clean)
        except json.JSONDecodeError:
            return

        anomalies = result.get("anomalies", [])
        filtered  = []
        for a in anomalies:
            eid    = a.get("entity_id", "")
            reason = a.get("reason", "").lower()
            state  = self._state_cache.get(eid, {})
            unit   = state.get("attributes", {}).get("unit_of_measurement", "")

            if self._config_reader.entity_is_configured(eid):
                logger.debug(f"Skip (configured): {eid}")
                continue
            if any(w in reason for w in ["lowercase","uppercase","capitaliz","case","minuscol","maiuscol"]):
                logger.debug(f"Skip (capitalisation): {eid}")
                continue
            if "voltage" in eid.lower() and unit.lower() in ("kwh","wh") and "voltage" in reason:
                logger.debug(f"Skip (integration sensor): {eid}")
                continue
            filtered.append(a)

        if not filtered:
            logger.debug("No real anomalies.")
            self._last_anomalies = []
            return

        logger.warning(f"⚠️  {len(filtered)} anomalia/e reale/i")
        self._last_anomalies = filtered

        for anomaly in filtered:
            await self._handle_anomaly(anomaly)

    async def _handle_anomaly(self, anomaly: dict):
        eid      = anomaly.get("entity_id", "?")
        reason   = anomaly.get("reason", "")
        severity = anomaly.get("severity", "low")

        patch_yaml = await self._generate_patch(eid, reason, severity)
        if patch_yaml:
            anomaly["patch_yaml"] = patch_yaml

        if self._tracker.should_notify(eid, reason):
            if self.notifier:
                await self.notifier.send_anomaly(anomaly)
            await self._tracker.mark_notified(eid, reason)
        else:
            logger.debug(f"Notifica soppressa (cooldown): {eid}")

        if self.auto_fix and patch_yaml and self._tracker.should_autofix(eid):
            await self._auto_apply(eid, patch_yaml)
            await self._tracker.mark_fixed(eid)

    async def _generate_patch(self, eid: str, reason: str, severity: str) -> str:
        state = self._state_cache.get(eid, {})
        attrs = state.get("attributes", {})
        slug  = eid.replace(".", "_").replace("-", "_")
        uid   = f"{slug.replace('sensor_', '', 1)}_fix_01"
        existing = self._config_reader.get_entity_config(eid)
        ex_note = ""
        if existing:
            ex_note = (
                f"\nEsiste già: unique_id={existing.get('unique_id')} "
                f"name='{existing.get('name')}' — proponi SOLO la modifica necessaria.\n"
            )
        prompt = (
            f"ANOMALIA: entity_id={eid}\n"
            f"  stato={state.get('state','?')} "
            f"device_class={attrs.get('device_class','?')} "
            f"unit={attrs.get('unit_of_measurement','?')}\n"
            f"  problema: {reason}{ex_note}\n"
            f"VINCOLI: unique_id={uid} | states() DEVE usare '{eid}'\n"
            f"Output: SOLO il blocco YAML lista (no template:/sensor: wrapper)."
        )
        try:
            response = await self.ai.ask(SYSTEM_PATCH_GENERATOR, prompt, max_tokens=400)
            fenced = re.findall(r"```ya?ml\n?(.*?)```", response, re.DOTALL)
            if fenced:
                return fenced[0].strip()
            if response.strip().startswith("-") or "unique_id:" in response:
                return response.strip()
        except Exception as e:
            logger.warning(f"Patch gen failed: {e}")
        return ""

    async def _auto_apply(self, eid: str, patch_yaml: str):
        slug = eid.replace(".", "_").replace("-", "_")
        uid  = f"{slug.replace('sensor_', '', 1)}_fix_01"
        try:
            ok, msg = await self._patcher.apply_sensor_patch(uid, patch_yaml)
            if ok:
                logger.info(f"✅ Auto-fix: {eid}")
                try:
                    await self.rest.call_service("homeassistant", "reload_template_entities", {})
                except Exception:
                    pass
                if self.notifier:
                    await self.notifier.send_patch_applied(eid, "homemind_fixes.yaml")
                await self._config_reader.load()
        except Exception as e:
            logger.error(f"Auto-fix failed: {e}", exc_info=True)

    def security_status(self) -> dict:
        return self._security.status()
