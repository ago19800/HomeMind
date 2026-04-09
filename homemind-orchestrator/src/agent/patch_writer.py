"""
patch_writer.py — Scrive patch YAML nel sistema packages di HA.
NON tocca mai configuration.yaml direttamente.
Usa /config/packages/homemind_fixes.yaml che viene auto-incluso.
"""
import logging
import re
import aiofiles
from pathlib import Path
from datetime import datetime
from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.patch_writer")

PACKAGES_DIR  = Path("/config/packages")
FIXES_FILE    = PACKAGES_DIR / "homemind_fixes.yaml"
BACKUP_DIR    = Path("/config/homemind_patches")


class PatchWriter:
    """
    Gestisce il file /config/packages/homemind_fixes.yaml.
    
    Il file ha questa struttura:
    
        homeassistant:
          customize: {}
        
        template:
          - sensor:
              - unique_id: xyz_fix_01
                ...
              - unique_id: abc_fix_01
                ...
    
    Aggiunge SEMPRE nuovi sensori dentro l'unico blocco template:
    esistente, mai crea duplicati.
    """

    async def ensure_file(self):
        """Crea il file packages se non esiste."""
        PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
        if not FIXES_FILE.exists():
            async with aiofiles.open(str(FIXES_FILE), "w") as f:
                await f.write(
                    "# HomeMind Fixes — gestito automaticamente\n"
                    "# NON modificare manualmente\n\n"
                    "template:\n"
                    "  - sensor: []\n"
                )
            logger.info(f"Creato file packages: {FIXES_FILE}")

    async def apply_sensor_patch(self, unique_id: str, sensor_yaml_block: str) -> tuple[bool, str]:
        """
        Aggiunge o aggiorna un sensore nel file packages.
        Se unique_id esiste già → lo aggiorna.
        Se non esiste → lo aggiunge.
        Restituisce (success, message).
        """
        await self.ensure_file()

        async with aiofiles.open(str(FIXES_FILE), "r") as f:
            content = await f.read()

        # Backup prima di ogni modifica
        ts = now_local().strftime("%Y%m%d_%H%M%S")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / f"homemind_fixes_backup_{ts}.yaml"
        async with aiofiles.open(str(backup), "w") as f:
            await f.write(content)

        # Normalizza indentazione del blocco sensore (deve essere a 8 spazi)
        sensor_lines = self._normalize_sensor_block(sensor_yaml_block, unique_id)
        if not sensor_lines:
            return False, "Blocco YAML sensore non valido"

        # Se unique_id già esiste → rimuovi il vecchio blocco
        if unique_id in content:
            content = self._remove_sensor_block(content, unique_id)
            action = "aggiornato"
        else:
            action = "aggiunto"

        # Inserisci il nuovo sensore dentro template: - sensor:
        content = self._insert_sensor(content, sensor_lines)

        async with aiofiles.open(str(FIXES_FILE), "w") as f:
            await f.write(content)

        logger.info(f"Sensore {unique_id} {action} in {FIXES_FILE}")
        return True, f"Sensore {unique_id} {action} nel file packages. Backup: {backup.name}"

    def _normalize_sensor_block(self, raw_yaml: str, unique_id: str) -> str:
        """
        Converte il blocco YAML in formato corretto per il file packages.
        Rimuove il prefisso template:/sensor: se presente,
        e assicura unique_id corretto.
        """
        lines = raw_yaml.strip().splitlines()
        
        # Strip wrapper template: / - sensor: if AI included them
        clean_lines = []
        skip_wrapper = False
        in_sensor_list = False
        sensor_indent = 0
        
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("template:"):
                skip_wrapper = True
                continue
            if skip_wrapper and stripped.startswith("- sensor:"):
                in_sensor_list = True
                skip_wrapper = False
                continue
            if in_sensor_list and stripped.startswith("- unique_id:"):
                # Found the sensor entry
                sensor_indent = len(line) - len(stripped)
                in_sensor_list = False
                clean_lines.append(line)
                continue
            if not in_sensor_list and not skip_wrapper:
                clean_lines.append(line)

        if not clean_lines:
            # Fallback: take as-is if no wrapper detected
            clean_lines = lines

        # Re-indent to 8 spaces (packages template: - sensor: - entry)
        result_lines = []
        if clean_lines:
            # Find minimum indentation
            min_indent = min(
                (len(l) - len(l.lstrip()) for l in clean_lines if l.strip()),
                default=0
            )
            for line in clean_lines:
                if line.strip():
                    result_lines.append("        " + line[min_indent:])
                else:
                    result_lines.append("")

        # Ensure it starts with - unique_id:
        if result_lines and not result_lines[0].strip().startswith("- unique_id:"):
            # Wrap with list marker
            result_lines[0] = "        - " + result_lines[0].strip()
            for i in range(1, len(result_lines)):
                if result_lines[i].strip():
                    # Additional indent for continuation
                    result_lines[i] = "          " + result_lines[i].strip()

        # Force correct unique_id
        for i, line in enumerate(result_lines):
            if "unique_id:" in line:
                indent = len(line) - len(line.lstrip())
                result_lines[i] = " " * indent + f"unique_id: {unique_id}"
                break

        return "\n".join(result_lines)

    def _remove_sensor_block(self, content: str, unique_id: str) -> str:
        """Rimuove il blocco sensore con questo unique_id dal file."""
        lines = content.splitlines()
        result = []
        skip = False
        skip_indent = 0
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            
            if f"unique_id: {unique_id}" in line:
                # Find the start of this sensor block (the - marker)
                # Go back to find the "- unique_id:" or preceding "- " marker
                if result and result[-1].strip().startswith("-"):
                    result.pop()  # remove the list marker line
                skip = True
                skip_indent = indent
                i += 1
                continue
            
            if skip:
                # Skip until we find a line at same or lower indent that starts new entry
                if stripped and indent <= skip_indent and stripped.startswith("-"):
                    skip = False
                    result.append(line)
                elif stripped and indent < skip_indent:
                    skip = False
                    result.append(line)
                # else: still skipping
            else:
                result.append(line)
            i += 1
        
        return "\n".join(result)

    def _insert_sensor(self, content: str, sensor_block: str) -> str:
        """Inserisce il sensore dentro template: - sensor:"""
        lines = content.splitlines()
        result = []
        inserted = False
        
        i = 0
        while i < len(lines):
            line = lines[i]
            result.append(line)
            
            # Find "  - sensor:" inside template block
            if not inserted and line.strip() == "- sensor: []":
                # Replace empty sensor list with our entry
                result[-1] = "  - sensor:"
                result.append(sensor_block)
                inserted = True
            elif not inserted and line.strip() == "- sensor:":
                # Insert after this line, before next entry or end
                result.append(sensor_block)
                inserted = True
            i += 1
        
        if not inserted:
            # template: section not found, append it
            result.append("\ntemplate:")
            result.append("  - sensor:")
            result.append(sensor_block)

        return "\n".join(result)

    async def read_fixes(self) -> str:
        """Leggi il contenuto attuale del file fixes."""
        await self.ensure_file()
        async with aiofiles.open(str(FIXES_FILE), "r") as f:
            return await f.read()
