"""
entity_registry.py — Registro entità HA per automazioni.

Mantiene un file JSON aggiornato con tutte le entità disponibili in HA,
raggruppate per tipo con nome amichevole → entity_id.

File: /data/homemind_entities.json
Aggiornamento: ogni 15 minuti + ad ogni riavvio

Struttura JSON:
{
  "updated_at": "2026-04-15T10:00:00",
  "entities": {
    "light": [
      {"id": "light.mario", "name": "Luce Mario", "state": "on"},
      ...
    ],
    "switch": [...],
    "sensor": [...],
    ...
  }
}

Uso nel prompt AI:
  HomeMind cerca nel registro per nome → trova l'entity_id esatto.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("homemind.entity_registry")

REGISTRY_PATH   = Path("/data/homemind_entities.json")
UPDATE_INTERVAL = 900   # 15 minuti

# Domini da includere (filtra quelli inutili)
INCLUDED_DOMAINS = {
    "light", "switch", "cover", "climate", "fan", "media_player",
    "input_boolean", "input_number", "input_select", "input_text",
    "scene", "script", "automation",
    "sensor", "binary_sensor",
    "person", "device_tracker",
    "alarm_control_panel",
    "camera",
}

# Stati da escludere (entità non operative)
EXCLUDED_STATES = {"unavailable", "unknown", "none"}

# Prefissi da escludere nei nomi (browser_mod, ecc.)
EXCLUDED_PREFIXES = (
    "binary_sensor.browser_mod",
    "sensor.browser_mod",
)


class EntityRegistry:
    def __init__(self, state_cache_cb, home=None):
        self._cache_cb = state_cache_cb
        self._home     = home   # HomeModel — per zone sensori movimento
        self._registry: dict = {}
        self._task = None

    @property
    def _cache(self) -> dict:
        return self._cache_cb() if self._cache_cb else {}

    async def start(self):
        """Avvia aggiornamento periodico."""
        await self._update()
        self._task = asyncio.create_task(self._loop(), name="entity_registry")
        logger.info("EntityRegistry avviato — aggiornamento ogni %ds", UPDATE_INTERVAL)

    async def _loop(self):
        while True:
            await asyncio.sleep(UPDATE_INTERVAL)
            await self._update()

    async def _update(self):
        """Aggiorna il registro dal state_cache corrente."""
        try:
            cache = self._cache
            grouped: dict = {}

            for eid, state_obj in cache.items():
                # Filtra dominio
                domain = eid.split(".")[0]
                if domain not in INCLUDED_DOMAINS:
                    continue

                # Filtra prefissi esclusi
                if any(eid.startswith(p) for p in EXCLUDED_PREFIXES):
                    continue

                state = state_obj.get("state", "")
                attrs = state_obj.get("attributes", {})
                name  = attrs.get("friendly_name", "") or eid

                # Arricchisci con zona se disponibile (motion sensors)
                zone = None
                if self._home and domain == "binary_sensor":
                    ms = getattr(self._home, "motion_sensors", {})
                    if eid in ms:
                        zone = ms[eid].get("zone")
                        # Aggiorna il nome con la zona se il nome è generico
                        if zone and zone != "interno":
                            _fn = name if name != eid else ""
                            name = f"{_fn} (zona: {zone})" if _fn else f"Sensore {zone}"

                entry = {
                    "id":    eid,
                    "name":  name,
                    "state": state,
                }
                if zone:
                    entry["zone"] = zone

                if domain not in grouped:
                    grouped[domain] = []
                grouped[domain].append(entry)

            # Ordina per nome dentro ogni gruppo
            for domain in grouped:
                grouped[domain].sort(key=lambda x: x["name"].lower())

            self._registry = grouped
            total = sum(len(v) for v in grouped.values())

            data = {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "total":      total,
                "entities":   grouped,
            }
            REGISTRY_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.info("EntityRegistry aggiornato: %d entità in %d domini",
                        total, len(grouped))

        except Exception as e:
            logger.warning("EntityRegistry update error: %s", e)

    def get_context_for_ai(self, max_per_domain: int = 40) -> str:
        """
        Restituisce testo compatto per il prompt AI.
        Formato:
          [binary_sensor] Sensore occupancy [zona:cucina] → binary_sensor.xxx (off)
          [light] Luce Esterna → light.xxx (off)
        I sensori movimento usano le zone calcolate da HomeMind.
        Le entità non disponibili vengono escluse.
        """
        if not self._registry:
            try:
                if REGISTRY_PATH.exists():
                    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
                    self._registry = data.get("entities", {})
            except Exception:
                pass

        lines = []

        # Sensori movimento con zone da HomeMind (fonte più affidabile)
        motion_known: dict = {}
        if self._home:
            for _eid, _ms in getattr(self._home, "motion_sensors", {}).items():
                _zone  = _ms.get("zone", "")
                _name  = _ms.get("name", _eid)
                _state = _ms.get("state", "?")
                if _state in EXCLUDED_STATES:
                    continue
                _disp = f"{_name} [zona:{_zone}]" if _zone else _name
                motion_known[_eid] = f"[binary_sensor] {_disp} → {_eid} ({_state})"

        # Ordine prioritario dei domini
        priority = [
            "light", "switch", "cover", "climate", "fan", "media_player",
            "scene", "script",
            "sensor", "binary_sensor",
            "input_boolean", "input_number", "input_select",
            "person", "alarm_control_panel",
        ]
        domains_ordered = priority + [d for d in sorted(self._registry) if d not in priority]

        for domain in domains_ordered:
            entries = self._registry.get(domain, [])
            if not entries:
                continue
            for e in entries[:max_per_domain]:
                if e["state"] in EXCLUDED_STATES:
                    continue
                eid = e["id"]
                # binary_sensor: usa motion_known se disponibile (ha zone corrette)
                if domain == "binary_sensor" and eid in motion_known:
                    lines.append(motion_known.pop(eid))
                    continue
                state_str    = f" ({e['state']})"
                display_name = e["name"]
                zone         = e.get("zone")
                if zone and zone not in display_name.lower():
                    display_name = f"{display_name} [zona:{zone}]"
                lines.append(f"[{domain}] {display_name} → {eid}{state_str}")

        # Aggiungi motion sensor non ancora inclusi nel registry
        for _ml in motion_known.values():
            lines.append(_ml)

        return "\n".join(lines)

    def find_entity(self, search: str) -> list[dict]:
        """
        Cerca un'entità per nome o id parziale.
        Utile per debug o suggerimenti.
        """
        results = []
        search_lower = search.lower()
        for domain, entries in self._registry.items():
            for e in entries:
                if (search_lower in e["name"].lower() or
                        search_lower in e["id"].lower()):
                    results.append(e)
        return results
