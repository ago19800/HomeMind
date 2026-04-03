"""
agent/ui_generator.py
Reads entity list + usage stats, calls AI, outputs Lovelace YAML.
"""
import asyncio
import json
import logging
import aiofiles
from pathlib import Path
from datetime import datetime
from utils.timezone_helper import now_local

from agent.ai_provider import AIProvider, SYSTEM_UI_GENERATOR

logger = logging.getLogger("homemind.ui_generator")
OUTPUT_DIR = Path("/config/homemind_dashboards")


class UIGenerator:
    def __init__(self, ai: AIProvider, rest_client, sensor_monitor=None):
        self.ai = ai
        self.rest = rest_client
        self.sensor_monitor = sensor_monitor

    async def generate(self, push_to_ha: bool = False) -> str:
        """Generate a Lovelace dashboard based on current entities and usage."""
        logger.info("Starting Lovelace dashboard generation...")
        states = await self.rest.get_states()
        usage = self.sensor_monitor.get_usage_stats() if self.sensor_monitor else {}

        # Build structured entity list for AI
        entity_list = [
            {
                "entity_id": s["entity_id"],
                "domain": s["entity_id"].split(".")[0],
                "state": s["state"],
                "friendly_name": s.get("attributes", {}).get("friendly_name", ""),
                "device_class": s.get("attributes", {}).get("device_class", ""),
                "usage_events": usage.get(s["entity_id"], 0),
            }
            for s in states
            if s["state"] not in ("unavailable", "unknown")
        ]

        # Sort by usage (most-used first)
        entity_list.sort(key=lambda e: e["usage_events"], reverse=True)

        prompt = f"""
Generate a Lovelace dashboard for these {len(entity_list)} entities.
Prioritize the top 20 by usage frequency.
Group by domain (lights, climate, sensors, media_player, persons).

Entities (JSON):
{json.dumps(entity_list[:50], indent=2)}
"""
        dashboard_yaml = await self.ai.ask(SYSTEM_UI_GENERATOR, prompt, max_tokens=4096)
        await self._save(dashboard_yaml)

        if push_to_ha:
            try:
                await self.rest.post_lovelace(dashboard_yaml)
                logger.info("Dashboard pushed to Home Assistant!")
            except Exception as e:
                logger.error(f"Failed to push dashboard: {e}")

        return dashboard_yaml

    async def _save(self, yaml_content: str):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = now_local().strftime("%Y%m%d_%H%M%S")
        path = OUTPUT_DIR / f"dashboard_{ts}.yaml"
        async with aiofiles.open(path, "w") as f:
            await f.write(yaml_content)
        logger.info(f"Dashboard saved to {path}")
