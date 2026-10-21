"""
config_reader.py — Indicizza TUTTA la configurazione HA esistente.
Comprende: template sensor, integration sensor, mqtt sensor,
command_line sensor, platform sensor, utility_meter, ecc.
"""
import logging
import re
import aiofiles
from pathlib import Path

logger = logging.getLogger("homemind.config_reader")

CONFIG_PATH  = Path("/config/configuration.yaml")
PACKAGES_DIR = Path("/config/packages")


class ConfigReader:
    def __init__(self):
        # entity_id → motivo per cui è "già configurato correttamente"
        self._configured: dict[str, str] = {}
        # unique_ids già usati
        self._known_unique_ids: set[str] = set()
        # summary per il prompt AI
        self._summary_lines: list[str] = []

    async def load(self):
        self._configured.clear()
        self._known_unique_ids.clear()
        self._summary_lines.clear()

        files = [CONFIG_PATH]
        if PACKAGES_DIR.exists():
            files += sorted(PACKAGES_DIR.glob("*.yaml"))

        full_content = ""
        for fpath in files:
            try:
                async with aiofiles.open(str(fpath), "r", errors="replace") as f:
                    content = await f.read()
                full_content += f"\n### FILE: {fpath.name} ###\n" + content
            except Exception as e:
                logger.debug(f"Cannot read {fpath}: {e}")

        self._parse_all(full_content)
        logger.info(
            f"Config index: {len(self._configured)} configured entities, "
            f"{len(self._known_unique_ids)} unique_ids"
        )

    def _parse_all(self, content: str):
        """Estrae tutte le entità già configurate dal YAML."""

        # 1. platform: integration sensors  →  producono kWh, sono CORRETTI per design
        for m in re.finditer(
            r"platform:\s*integration.*?name:\s*['\"]?(.+?)['\"]?\s*$.*?unique_id:\s*['\"]?(\S+?)['\"]?",
            content, re.DOTALL | re.MULTILINE
        ):
            name = m.group(1).strip()
            uid  = m.group(2).strip()
            slug = re.sub(r"[^a-z0-9]", "_", name.lower())
            eid  = f"sensor.{slug}"
            self._configured[eid] = f"platform:integration uid={uid}"
            self._configured[f"sensor.{uid.lower()}"] = f"platform:integration uid={uid}"
            self._known_unique_ids.add(uid)

        # Also catch integration blocks where unique_id comes before name
        for m in re.finditer(
            r"platform:\s*integration.*?unique_id:\s*['\"]?(\S+?)['\"]?\s*$.*?name:\s*['\"]?(.+?)['\"]?\s*$",
            content, re.DOTALL | re.MULTILINE
        ):
            uid  = m.group(1).strip()
            name = m.group(2).strip()
            slug = re.sub(r"[^a-z0-9]", "_", name.lower())
            eid  = f"sensor.{slug}"
            self._configured[eid] = f"platform:integration uid={uid}"
            self._configured[f"sensor.{uid.lower()}"] = f"platform:integration uid={uid}"
            self._known_unique_ids.add(uid)

        # 2. template: sensor blocks
        for m in re.finditer(
            r"-\s+unique_id:\s*['\"]?(\S+?)['\"]?\s*\n(.*?)(?=\n\s*-\s+unique_id:|\Z)",
            content, re.DOTALL
        ):
            uid  = m.group(1).strip()
            body = m.group(0)
            self._known_unique_ids.add(uid)

            name_m   = re.search(r"name:\s*['\"]?(.+?)['\"]?\s*$", body, re.MULTILINE)
            dc_m     = re.search(r"device_class:\s*(\S+)", body)
            unit_m   = re.search(r"unit_of_measurement:\s*['\"]?(.+?)['\"]?\s*$", body, re.MULTILINE)
            source_m = re.search(r"states\(['\"]([^'\"]+)['\"]", body)

            name   = name_m.group(1).strip()   if name_m   else uid
            dc     = dc_m.group(1).strip()     if dc_m     else ""
            unit   = unit_m.group(1).strip()   if unit_m   else ""
            source = source_m.group(1).strip() if source_m else ""

            desc = f"template uid={uid} dc={dc} unit={unit}"

            # Register by uid slug
            slug = re.sub(r"[^a-z0-9]", "_", name.lower())
            self._configured[f"sensor.{slug}"] = desc
            if source:
                self._configured[source] = f"{desc} source={source}"
            self._summary_lines.append(
                f"  - {uid}: name='{name}' dc={dc or 'n/a'} unit={unit or 'n/a'}"
                + (f" source={source}" if source else "")
            )

        # 3. mqtt sensor
        for m in re.finditer(
            r"name:\s*['\"]?(.+?)['\"]?\s*\n.*?state_topic:",
            content, re.DOTALL
        ):
            name = m.group(1).strip()
            slug = re.sub(r"[^a-z0-9]", "_", name.lower())
            self._configured[f"sensor.{slug}"] = "mqtt"

        # 4. command_line sensor
        for m in re.finditer(
            r"command_line.*?name:\s*['\"]?(.+?)['\"]?",
            content, re.DOTALL
        ):
            name = m.group(1).strip()
            slug = re.sub(r"[^a-z0-9]", "_", name.lower())
            self._configured[f"sensor.{slug}"] = "command_line"

        # 5. platform: time_date → exclude all time sensors
        for ts in ["sensor.date", "sensor.time", "sensor.date_time",
                   "sensor.date_time_utc", "sensor.date_time_iso",
                   "sensor.time_date", "sensor.time_utc"]:
            self._configured[ts] = "platform:time_date"

        # 6. Catch ALL unique_ids to prevent re-use
        for m in re.finditer(r"unique_id:\s*['\"]?(\S+?)['\"]?\s*$",
                              content, re.MULTILINE):
            self._known_unique_ids.add(m.group(1).strip())

        # 7. utility_meter entries
        for m in re.finditer(r"^\s{2}(\w+):\s*\n\s+source:\s*(sensor\.\S+)",
                              content, re.MULTILINE):
            uid    = m.group(1).strip()
            source = m.group(2).strip()
            self._configured[f"sensor.{uid}"] = f"utility_meter source={source}"

    def entity_is_configured(self, entity_id: str) -> bool:
        """True se l'entità è già gestita da qualsiasi configurazione esistente."""
        eid_lower = entity_id.lower()

        # Direct match
        if entity_id in self._configured:
            return True

        # Case-insensitive match
        for k in self._configured:
            if k.lower() == eid_lower:
                return True

        # Match by slug (sensor.batteria_voltage → batteria_voltage)
        slug = entity_id.replace("sensor.", "").replace("-", "_").lower()
        for k in self._configured:
            k_slug = k.replace("sensor.", "").replace("-", "_").lower()
            if k_slug == slug:
                return True

        # Check if any unique_id matches slug pattern
        uid_candidate = slug + "_fix_01"
        if uid_candidate in self._known_unique_ids:
            return True

        return False

    def get_known_sensors_summary(self, limit: int = 40) -> str:
        lines = self._summary_lines[:limit]
        if not lines:
            return "  (nessun template sensor configurato)"
        return "\n".join(lines)

    def get_all_configured_ids(self) -> list[str]:
        return list(self._configured.keys())
