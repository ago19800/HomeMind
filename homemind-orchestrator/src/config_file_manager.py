"""
Configuration File Manager — gestione file Home Assistant stile OpenClaw.

Permette di leggere, modificare e fare backup intelligente di configuration.yaml e
altri file HA. Supporta merge intelligente: rileva sezioni esistenti e inserisce
nuovo codice in modo coerente.

Backup salvati in /config/homemind_patches/ (stessa cartella dei backup automazioni).
"""

import os
import re
import yaml
import json
import shutil
import difflib
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Stessa cartella dove vengono salvati i backup delle automazioni
BACKUP_DIR = Path("/config/homemind_patches")

class HALoader(yaml.SafeLoader):
    """YAML Loader che gestisce i tag custom di Home Assistant.

    Senza questo loader, yaml.safe_load() fallisce su !include, !secret, ecc.
    I tag vengono preservati come oggetti "placeholder" per non perdere info.
    """
    pass

class _HAIncludePlaceholder:
    """Placeholder per tag HA come !include, !secret. Mantiene il riferimento."""
    def __init__(self, tag: str, value):
        self.tag = tag
        self.value = value
    def __repr__(self):
        return f"{self.tag} {self.value}"

def _ha_constructor(loader, tag_suffix, node):
    """Costruttore generico per tag HA: !include, !secret, !env_var, !input, ecc."""
    if isinstance(node, yaml.ScalarNode):
        val = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        val = loader.construct_sequence(node, deep=True)
    elif isinstance(node, yaml.MappingNode):
        val = loader.construct_mapping(node, deep=True)
    else:
        val = None
    return _HAIncludePlaceholder(f"!{tag_suffix}", val)

# Registra i tag HA più comuni
for tag in ["include", "include_dir_list", "include_dir_merge_list",
            "include_dir_named", "include_dir_merge_named", "secret",
            "env_var", "input"]:
    HALoader.add_constructor(f"!{tag}",
        lambda loader, node, t=tag: _ha_constructor(loader, t, node))
# Anche multi_constructor per tag non previsti
HALoader.add_multi_constructor("!", _ha_constructor)

def ha_safe_load(content: str):
    """Wrapper su yaml.load con HALoader (supporta tag HA)."""
    return yaml.load(content, Loader=HALoader)

class ConfigFileManager:
    """Gestione file di configurazione Home Assistant con smart merge."""

    def __init__(self, ha_config_dir: str = "/config"):
        self.config_dir = Path(ha_config_dir)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════════════════════════
    # FILE I/O
    # ══════════════════════════════════════════════════════════════════

    def read_file(self, relative_path: str) -> str:
        """Legge un file dalla directory config HA."""
        file_path = self.config_dir / relative_path

        # Security: impedisci uscita da /config
        if not str(file_path.resolve()).startswith(str(self.config_dir.resolve())):
            raise PermissionError(f"Accesso negato fuori da /config")

        if not file_path.exists():
            raise FileNotFoundError(f"File non trovato: {relative_path}")

        return file_path.read_text(encoding="utf-8")

    def backup_file(self, relative_path: str) -> str:
        """Crea backup di un file con timestamp nella stessa cartella delle automazioni.

        Returns: Path relativo del backup creato
        """
        file_path = self.config_dir / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"File non trovato: {relative_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"
        backup_path = BACKUP_DIR / backup_name

        shutil.copy2(file_path, backup_path)
        logger.info(f"Backup creato: {backup_path}")
        return str(backup_path.relative_to(self.config_dir))

    def write_file(self, relative_path: str, content: str,
                   validate_yaml: bool = True, do_backup: bool = True) -> str:
        """Scrive contenuto in un file. Fa backup automatico se do_backup=True.

        Returns: Path del backup creato (se do_backup) o stringa vuota
        """
        file_path = self.config_dir / relative_path

        if not str(file_path.resolve()).startswith(str(self.config_dir.resolve())):
            raise PermissionError(f"Accesso negato fuori da /config")

        if validate_yaml and file_path.suffix in [".yaml", ".yml"]:
            try:
                ha_safe_load(content)
            except Exception as e:
                raise ValueError(f"YAML non valido: {e}")

        backup_path = ""
        if do_backup and file_path.exists():
            backup_path = self.backup_file(relative_path)

        file_path.write_text(content, encoding="utf-8")
        logger.info(f"File scritto: {relative_path} (backup: {backup_path})")
        return backup_path

    def list_config_files(self) -> list:
        """Elenca i file di configurazione HA principali, con dimensione.

        Returns: lista di dict {path, size, lines, exists}
        """
        targets = [
            "configuration.yaml",
            "automations.yaml",
            "scripts.yaml",
            "scenes.yaml",
            "groups.yaml",
            "customize.yaml",
            "secrets.yaml",
            "ui-lovelace.yaml",
        ]
        # Aggiungi packages/*.yaml se esiste
        packages_dir = self.config_dir / "packages"
        if packages_dir.exists() and packages_dir.is_dir():
            for pkg_file in sorted(packages_dir.glob("*.yaml")):
                targets.append(f"packages/{pkg_file.name}")
        # Aggiungi includes/*.yaml se esiste
        includes_dir = self.config_dir / "includes"
        if includes_dir.exists() and includes_dir.is_dir():
            for inc_file in sorted(includes_dir.glob("*.yaml")):
                targets.append(f"includes/{inc_file.name}")

        result = []
        for rel in targets:
            full = self.config_dir / rel
            if full.exists() and full.is_file():
                try:
                    content = full.read_text(encoding="utf-8", errors="ignore")
                    result.append({
                        "path":   rel,
                        "size":   full.stat().st_size,
                        "lines":  len(content.split("\n")),
                        "exists": True,
                    })
                except Exception as e:
                    result.append({"path": rel, "size": 0, "lines": 0,
                                   "exists": True, "error": str(e)})
        return result

    def list_backups(self, limit: int = 20) -> list:
        """Elenca backup, più recenti prima."""
        backups = sorted(BACKUP_DIR.glob("*_backup_*.yaml"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        return [str(b.relative_to(self.config_dir)) for b in backups[:limit]]

    # ══════════════════════════════════════════════════════════════════
    # SMART MERGE YAML
    # ══════════════════════════════════════════════════════════════════

    def analyze_yaml_structure(self, content: str) -> dict:
        """Analizza struttura YAML HA: sezioni top-level e !include."""
        lines = content.split("\n")
        sections = []
        includes = []

        try:
            parsed = ha_safe_load(content) or {}
            if isinstance(parsed, dict):
                sections = list(parsed.keys())
        except yaml.YAMLError as e:
            logger.warning(f"YAML parse error in analyze: {e}")
        except Exception as e:
            logger.warning(f"Parse error in analyze: {e}")

        # Rileva !include directives via regex
        include_pattern = re.compile(
            r'^\s*([a-z_][a-z0-9_]*)\s*:\s*(!include(?:_dir_[a-z]+)?)\s+(.+?)\s*$',
            re.IGNORECASE | re.MULTILINE
        )
        for m in include_pattern.finditer(content):
            includes.append({
                "key":  m.group(1),
                "type": m.group(2),
                "path": m.group(3).strip()
            })

        return {
            "sections":     sections,
            "has_includes": len(includes) > 0,
            "includes":     includes,
            "num_lines":    len(lines),
        }

    def find_section_bounds(self, content: str, section_name: str) -> tuple:
        """Trova righe inizio e fine di una sezione top-level."""
        lines = content.split("\n")
        start = -1

        section_re = re.compile(rf'^{re.escape(section_name)}\s*:')
        for i, line in enumerate(lines):
            if section_re.match(line):
                start = i
                break

        if start == -1:
            return (-1, -1)

        for j in range(start + 1, len(lines)):
            line = lines[j]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if line and not line[0].isspace():
                return (start, j - 1)

        return (start, len(lines) - 1)

    def smart_insert(self, existing_content: str, new_yaml_snippet: str,
                     section_hint: str = None) -> dict:
        """Inserisce intelligentemente nuovo YAML in configurazione esistente."""
        try:
            new_parsed = yaml.safe_load(new_yaml_snippet)
        except yaml.YAMLError as e:
            return {"success": False, "error": f"Snippet YAML non valido: {e}"}

        if not isinstance(new_parsed, dict):
            return {"success": False, "error": "Snippet non è un dizionario YAML"}

        new_section_name = list(new_parsed.keys())[0] if new_parsed else None
        if section_hint and not new_section_name:
            new_section_name = section_hint

        if not new_section_name:
            return {"success": False, "error": "Impossibile determinare sezione"}

        analysis = self.analyze_yaml_structure(existing_content)

        # Check !include: se sezione è inclusa altrove, avvisa
        for inc in analysis["includes"]:
            if inc["key"] == new_section_name:
                return {
                    "success": False,
                    "strategy": "include_warning",
                    "section":  new_section_name,
                    "warning":  (f"La sezione '{new_section_name}' è inclusa da "
                                 f"'{inc['path']}' tramite {inc['type']}. "
                                 f"Va modificato il file {inc['path']} invece di "
                                 f"configuration.yaml."),
                    "include_info": inc,
                }

        # Sezione esiste → merge
        if new_section_name in analysis["sections"]:
            start, end = self.find_section_bounds(existing_content, new_section_name)
            if start == -1:
                return self._append_new_section(existing_content, new_yaml_snippet, new_section_name)

            new_lines = new_yaml_snippet.rstrip().split("\n")
            new_body = new_lines[1:] if new_lines and new_lines[0].strip().endswith(":") else new_lines

            lines = existing_content.split("\n")
            insert_at = end + 1
            for k in range(end, start, -1):
                if lines[k].strip():
                    insert_at = k + 1
                    break

            merged_lines = lines[:insert_at] + [""] + new_body + lines[insert_at:]
            new_content = "\n".join(merged_lines)

            try:
                ha_safe_load(new_content)
            except Exception as e:
                return {"success": False, "error": f"YAML risultante non valido: {e}"}

            return {
                "success":     True,
                "new_content": new_content,
                "diff":        self._make_diff(existing_content, new_content),
                "strategy":    "merged",
                "section":     new_section_name,
                "warning":     None,
            }

        # Sezione nuova → appendi
        return self._append_new_section(existing_content, new_yaml_snippet, new_section_name)

    def _append_new_section(self, existing_content: str, new_yaml_snippet: str,
                            section_name: str) -> dict:
        """Aggiunge nuova sezione in fondo con separatore."""
        existing = existing_content.rstrip()
        separator = (f"\n\n# ────────────────────────────────────────\n"
                     f"# {section_name.upper()} — aggiunta da HomeMind "
                     f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                     f"# ────────────────────────────────────────\n")
        new_content = existing + separator + new_yaml_snippet.rstrip() + "\n"

        try:
            ha_safe_load(new_content)
        except Exception as e:
            return {"success": False, "error": f"YAML risultante non valido: {e}"}

        return {
            "success":     True,
            "new_content": new_content,
            "diff":        self._make_diff(existing_content, new_content),
            "strategy":    "appended",
            "section":     section_name,
            "warning":     None,
        }

    def _make_diff(self, before: str, after: str, max_lines: int = 80) -> str:
        """Genera diff umano-leggibile."""
        before_lines = before.split("\n")
        after_lines  = after.split("\n")
        diff = list(difflib.unified_diff(
            before_lines, after_lines,
            fromfile="prima", tofile="dopo", lineterm="", n=2
        ))
        if len(diff) > max_lines:
            diff = diff[:max_lines] + ["...", f"(diff troncato, {len(diff)} righe totali)"]
        return "\n".join(diff)

    # ══════════════════════════════════════════════════════════════════
    # ENTITY DISCOVERY (per AI context)
    # ══════════════════════════════════════════════════════════════════

    def get_entities_context(self, state_cache: dict, domain_filter: str = None,
                             search: str = None, limit: int = 30) -> str:
        """Lista entità per contesto AI."""
        if not state_cache:
            return "(nessuna entità disponibile)"

        filtered = []
        for eid, s in state_cache.items():
            if domain_filter and not eid.startswith(f"{domain_filter}."):
                continue
            if search:
                fname = (s.get("attributes") or {}).get("friendly_name", "")
                if search.lower() not in eid.lower() and search.lower() not in fname.lower():
                    continue
            fname = (s.get("attributes") or {}).get("friendly_name", eid)
            unit = (s.get("attributes") or {}).get("unit_of_measurement", "")
            state = s.get("state", "")
            filtered.append(f"  • {eid} ({fname}) = {state}{' ' + unit if unit else ''}")
            if len(filtered) >= limit:
                break

        if not filtered:
            return "(nessuna entità trovata)"
        return "\n".join(filtered)
