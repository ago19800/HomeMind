"""
agent/automations_manager.py — Gestione completa automazioni HA da Telegram.
Supporta: lista, crea, modifica, elimina, attiva/disattiva.
"""
import logging, re, aiofiles
try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False
from pathlib import Path
from datetime import datetime
from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.automations")

AUTOMATIONS_FILE = Path("/config/automations.yaml")
BACKUP_DIR       = Path("/config/homemind_patches")


class AutomationsManager:
    def __init__(self, ai, rest_client, notifier=None):
        self.ai       = ai
        self.rest     = rest_client
        self.notifier = notifier

    # ══ LISTA ════════════════════════════════════════════════════════════════

    async def list_automations(self, state_cache: dict) -> str:
        autos = [(eid, s) for eid, s in state_cache.items()
                 if eid.startswith("automation.")]
        if not autos:
            return "⚙️ <b>Automazioni</b>\n\nNessuna automazione trovata."

        on  = [(e, s) for e, s in autos if s.get("state") == "on"]
        off = [(e, s) for e, s in autos if s.get("state") != "on"]

        lines = [f"⚙️ <b>Automazioni</b> ({len(autos)} totali)", ""]
        if on:
            lines.append(f"✅ <b>Attive ({len(on)}):</b>")
            for eid, s in on[:15]:
                lines.append(f"  • {s.get('attributes',{}).get('friendly_name', eid)}")
        if off:
            lines.append(f"\n⭕ <b>Disattive ({len(off)}):</b>")
            for eid, s in off[:10]:
                lines.append(f"  • {s.get('attributes',{}).get('friendly_name', eid)}")
        if len(autos) > 25:
            lines.append(f"\n<i>... e altre {len(autos)-25}</i>")
        lines += [
            "", "💬 <i>Comandi:</i>",
            "  <code>crea automazione [descrizione]</code>",
            "  <code>modifica automazione [nome] — [cosa cambiare]</code>",
            "  <code>elimina automazione [nome]</code>",
        ]
        return "\n".join(lines)

    # ══ CREA ═════════════════════════════════════════════════════════════════

    async def create_automation(self, description: str, state_cache: dict) -> str:
        entities_ctx = self._build_entities_context(state_cache)
        system = (
            "Sei un esperto Home Assistant. Genera automazioni YAML valide per HA 2024+.\n"
            "⚠️ REGOLA CRITICA: usa ESCLUSIVAMENTE gli entity_id presenti nel contesto fornito.\n"
            "NON inventare MAI entity_id come 'light.luce_mario' o simili — usa solo quelli reali.\n"
            "Se non trovi un'entità adatta, scrivi una nota e usa il più simile disponibile.\n\n"
            "FORMATO OBBLIGATORIO — lista YAML con un elemento:\n"
            "- id: 'homemind_[slug_univoco]'\n"
            "  alias: 'Nome Leggibile'\n"
            "  description: 'Descrizione'\n"
            "  trigger:\n"
            "    - platform: ...\n"
            "  condition: []\n"
            "  action:\n"
            "    - ...\n"
            "  mode: single\n\n"
            "Rispondi SOLO con il blocco ```yaml```. Niente prosa."
        )
        prompt = (
            f"Crea automazione per: {description}\n\n"
            f"Entità REALI disponibili (usare SOLO questi entity_id):\n{entities_ctx}"
        )
        try:
            response   = await self.ai.ask(system, prompt, max_tokens=1200)
            yaml_block = self._extract_yaml(response)
            if not yaml_block:
                return "❌ L'AI non ha generato YAML valido. Riprova con una descrizione più specifica."

            # ── Validazione entity_id ────────────────────────────────────
            warnings = self._validate_entities(yaml_block, state_cache)

            ok, msg = await self._append_to_file(yaml_block)
            if not ok:
                return f"❌ Errore scrittura file: {msg}"
            await self._reload()

            name    = self._extract_alias(yaml_block)
            preview = yaml_block[:600] + ("…" if len(yaml_block) > 600 else "")
            result  = (
                f"✅ <b>Automazione creata e installata!</b>\n\n"
                f"📌 <b>{self._esc(name)}</b>\n"
                f"📋 Salvata in <code>automations.yaml</code>\n"
                f"🔄 HA ricaricato automaticamente\n"
            )
            if warnings:
                result += f"\n⚠️ <b>Attenzione:</b>\n{warnings}\n"
            result += f"\n<pre>{self._esc(preview)}</pre>"
            return result
        except Exception as e:
            logger.error("create_automation: %s", e)
            return f"❌ Errore: {e}"

    # ══ MODIFICA ══════════════════════════════════════════════════════════════

    async def modify_automation(self, name_query: str, change_desc: str,
                                 state_cache: dict) -> str:
        """Legge YAML corrente, chiede all'AI di modificarlo, riscrive il file."""
        current_yaml = await self._read_block(name_query)
        if not current_yaml:
            # Fallback: prova a trovare per nome friendly in state_cache
            match = self._find_in_cache(name_query, state_cache)
            if match:
                eid, s = match
                fname  = s.get("attributes", {}).get("friendly_name", eid)
                current_yaml = await self._read_block(fname)
            if not current_yaml:
                return (
                    f"❌ Automazione <b>'{self._esc(name_query)}'</b> non trovata nel file.\n"
                    f"Usa /automazioni per vedere i nomi esatti."
                )

        system = (
            "Sei un esperto Home Assistant. Modifica automazioni YAML esistenti.\n"
            "Ricevi il YAML attuale e la modifica richiesta.\n"
            "Rispondi SOLO con il YAML completo modificato nel blocco ```yaml```.\n"
            "Mantieni l'id originale. Niente commenti extra."
        )
        prompt = (
            f"YAML attuale:\n```yaml\n{current_yaml}\n```\n\n"
            f"Modifica richiesta: {change_desc}\n\n"
            f"Entità disponibili:\n{self._build_entities_context(state_cache)}"
        )
        try:
            response  = await self.ai.ask(system, prompt, max_tokens=1200)
            new_yaml  = self._extract_yaml(response)
            if not new_yaml:
                return "❌ L'AI non ha generato YAML valido."

            ok, msg = await self._replace_block(name_query, new_yaml)
            if not ok:
                # Se non trovato nel file, aggiungi comunque
                ok, msg = await self._append_to_file(new_yaml)
            if not ok:
                return f"❌ Errore scrittura: {msg}"

            await self._reload()
            new_name = self._extract_alias(new_yaml)
            preview  = new_yaml[:500] + ("…" if len(new_yaml) > 500 else "")
            return (
                f"✏️ <b>Automazione modificata!</b>\n\n"
                f"📌 <b>{self._esc(new_name)}</b>\n"
                f"🔄 HA ricaricato\n\n"
                f"<pre>{self._esc(preview)}</pre>"
            )
        except Exception as e:
            logger.error("modify_automation: %s", e)
            return f"❌ Errore: {e}"

    # ══ ELIMINA ═══════════════════════════════════════════════════════════════

    async def delete_automation(self, name_query: str, state_cache: dict) -> str:
        """Disattiva in HA e rimuove dal file YAML."""
        # Disattiva prima in HA
        match = self._find_in_cache(name_query, state_cache)
        fname = name_query
        if match:
            eid, s = match
            fname  = s.get("attributes", {}).get("friendly_name", eid)
            try:
                await self.rest.call_service("automation", "turn_off", {},
                                              target={"entity_id": eid})
            except Exception:
                pass

        ok, removed = await self._remove_block(fname)

        if ok and removed:
            await self._reload()
            return (
                f"🗑️ <b>Automazione eliminata!</b>\n\n"
                f"📌 <b>{self._esc(fname)}</b>\n"
                f"📋 Rimossa da <code>automations.yaml</code> · HA ricaricato"
            )
        elif ok and not removed:
            return (
                f"⚠️ <b>'{self._esc(fname)}'</b> non trovata nel file YAML.\n\n"
                f"Potrebbe essere gestita dall'interfaccia grafica HA.\n"
                f"Vai in <b>Impostazioni → Automazioni</b> per eliminarla."
            )
        else:
            return f"❌ Errore eliminazione: {removed}"

    # ══ ATTIVA / DISATTIVA ════════════════════════════════════════════════════

    async def toggle_automation(self, name_or_id: str, state_cache: dict,
                                 force: str = None) -> str:
        match = self._find_in_cache(name_or_id, state_cache)
        if not match:
            return (
                f"❌ Automazione <b>'{self._esc(name_or_id)}'</b> non trovata.\n"
                f"Usa /automazioni per vedere i nomi esatti."
            )
        eid, s = match
        fname  = s.get("attributes", {}).get("friendly_name", eid)
        cur    = s.get("state", "off")

        if force == "on":
            svc = "turn_on"
        elif force == "off":
            svc = "turn_off"
        else:
            svc = "turn_off" if cur == "on" else "turn_on"

        icon  = "✅" if svc == "turn_on" else "⭕"
        label = "attivata" if svc == "turn_on" else "disattivata"
        try:
            await self.rest.call_service("automation", svc, {},
                                          target={"entity_id": eid})
            return f"{icon} <b>{self._esc(fname)}</b> {label}"
        except Exception as e:
            return f"❌ Errore: {e}"

    # ══ FILE I/O ══════════════════════════════════════════════════════════════

    async def _read_file(self) -> str:
        if not AUTOMATIONS_FILE.exists():
            return ""
        async with aiofiles.open(str(AUTOMATIONS_FILE), "r", encoding="utf-8") as f:
            return await f.read()

    async def _write_file(self, content: str) -> None:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        if AUTOMATIONS_FILE.exists():
            ts  = now_local().strftime("%Y%m%d_%H%M%S")
            bak = BACKUP_DIR / f"automations_backup_{ts}.yaml"
            orig = await self._read_file()
            async with aiofiles.open(str(bak), "w", encoding="utf-8") as f:
                await f.write(orig)
        async with aiofiles.open(str(AUTOMATIONS_FILE), "w", encoding="utf-8") as f:
            await f.write(content)

    async def _append_to_file(self, yaml_block: str) -> tuple:
        try:
            original = await self._read_file()
            sep = f"\n\n# HomeMind — {now_local().strftime('%Y-%m-%d %H:%M')}\n"
            await self._write_file(original + sep + yaml_block + "\n")
            return True, "OK"
        except Exception as e:
            return False, str(e)

    async def _read_block(self, name_query: str) -> str:
        content = await self._read_file()
        if not content:
            return ""
        q = name_query.lower()
        for block in self._split_blocks(content):
            if q in self._extract_alias(block).lower() or q in self._extract_id(block).lower():
                return block.strip()
        return ""

    async def _replace_block(self, name_query: str, new_yaml: str) -> tuple:
        try:
            content = await self._read_file()
            if not content:
                return False, "File vuoto"
            q      = name_query.lower()
            blocks = self._split_blocks(content)
            found  = False
            result = []
            for block in blocks:
                if q in self._extract_alias(block).lower() or q in self._extract_id(block).lower():
                    result.append(new_yaml.strip())
                    found = True
                else:
                    result.append(block.strip())
            if not found:
                return False, "Non trovata"
            await self._write_file("\n\n".join(result) + "\n")
            return True, "OK"
        except Exception as e:
            return False, str(e)

    async def _remove_block(self, name_query: str) -> tuple:
        try:
            content = await self._read_file()
            if not content:
                return True, False
            q       = name_query.lower()
            blocks  = self._split_blocks(content)
            result  = []
            removed = False
            for block in blocks:
                if q in self._extract_alias(block).lower() or q in self._extract_id(block).lower():
                    removed = True
                else:
                    result.append(block.strip())
            if removed:
                await self._write_file("\n\n".join(result) + "\n")
            return True, removed
        except Exception as e:
            return False, str(e)

    def _split_blocks(self, content: str) -> list:
        """Divide il file in blocchi per singola automazione.
        Usa PyYAML se disponibile (robusto), altrimenti fallback regex (fragile).
        """
        # ── Metodo robusto: PyYAML ──────────────────────────────────────────
        if _YAML_AVAILABLE:
            try:
                automations = _yaml.safe_load(content)
                if isinstance(automations, list):
                    blocks = []
                    for auto in automations:
                        if isinstance(auto, dict) and ("alias" in auto or "id" in auto):
                            blocks.append(_yaml.dump([auto], allow_unicode=True,
                                                     default_flow_style=False))
                    return blocks
            except Exception as e:
                logger.warning("YAML parse error, uso fallback regex: %s", e)

        # ── Fallback: parsing line-based (legacy) ───────────────────────────
        lines      = content.splitlines()
        blocks     = []
        cur        = []
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("- id:") or stripped.startswith("- alias:"):
                if cur:
                    blocks.append("\n".join(cur))
                cur = [line]
            else:
                cur.append(line)
        if cur:
            blocks.append("\n".join(cur))
        return [b for b in blocks if re.search(r"alias:|id:", b)]

    async def _reload(self):
        try:
            await self.rest.call_service("automation", "reload", {})
        except Exception as e:
            logger.warning("Automation reload: %s", e)

    # ══ UTILITY ═══════════════════════════════════════════════════════════════

    def _find_in_cache(self, query: str, state_cache: dict):
        q    = query.lower()
        best = None
        for eid, s in state_cache.items():
            if not eid.startswith("automation."): continue
            name = s.get("attributes", {}).get("friendly_name", eid).lower()
            if q == name or q == eid.lower():
                return (eid, s)
            if q in name or q in eid.lower():
                best = (eid, s)
        return best

    def _validate_entities(self, yaml_text: str, state_cache: dict) -> str:
        """Controlla che gli entity_id nel YAML esistano in HA. Ritorna stringa warnings o ''."""
        found = re.findall(r"entity_id:\s*([^\s\n#]+)", yaml_text)
        missing = []
        for eid in found:
            eid = eid.strip("'\"")
            # Accetta wildcard e pattern come "light.all"
            if "." not in eid or eid.endswith(".*"):
                continue
            if eid not in state_cache:
                missing.append(eid)
        if missing:
            return "Entity_id non trovati in HA:\n" + "\n".join(f"  ❓ <code>{e}</code>" for e in missing)
        return ""

    def _build_entities_context(self, state_cache: dict) -> str:
        lines   = []
        domains = {"light","switch","climate","sensor","binary_sensor",
                   "input_boolean","media_player","cover","person"}
        for eid, s in state_cache.items():
            if eid.split(".")[0] not in domains: continue
            name  = s.get("attributes", {}).get("friendly_name", eid)
            state = s.get("state", "?")
            if state in ("unavailable", "unknown"): continue
            lines.append(f"{eid} ({name}) = {state}")
            if len(lines) >= 70: break
        return "\n".join(lines)

    def _extract_yaml(self, text: str) -> str:
        m = re.search(r"```ya?ml\n(.+?)```", text, re.DOTALL)
        if m: return m.group(1).strip()
        m2 = re.search(r"(- (?:id|alias):.+)", text, re.DOTALL)
        return m2.group(1).strip() if m2 else ""

    def _extract_alias(self, yaml_text: str) -> str:
        m = re.search(r"alias:\s*['\"]?(.+?)['\"]?\s*$", yaml_text, re.MULTILINE)
        return m.group(1).strip().strip("'\"") if m else "Automazione"

    def _extract_id(self, yaml_text: str) -> str:
        m = re.search(r"(?:^|\n)\s*-?\s*id:\s*['\"]?(.+?)['\"]?\s*$",
                      yaml_text, re.MULTILINE)
        return m.group(1).strip().strip("'\"") if m else ""

    @staticmethod
    def _esc(t: str) -> str:
        return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
