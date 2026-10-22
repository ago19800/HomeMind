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

AUTOMATIONS_FILE   = Path("/config/automations.yaml")
CONFIGURATION_FILE = Path("/config/configuration.yaml")
BACKUP_DIR         = Path("/config/homemind_patches")


class AutomationsManager:
    def __init__(self, ai, rest_client, notifier=None, entity_registry=None, telegram_chat_id: str = ""):
        self.ai               = ai
        self.rest             = rest_client
        self.notifier         = notifier
        self._entity_registry  = entity_registry
        self._telegram_chat_id = telegram_chat_id.strip()

    # ══ SETUP ═══════════════════════════════════════════════════════════════

    async def _ensure_automations_included(self) -> str:
        """
        Verifica che configuration.yaml includa automations.yaml.
        Se mancante crea il file con struttura base e avvisa l'utente.
        Ritorna un warning string se serve attenzione, stringa vuota se ok.
        """
        warnings = []

        # 1. Crea automations.yaml se non esiste
        if not AUTOMATIONS_FILE.exists():
            try:
                AUTOMATIONS_FILE.write_text("# HomeMind automations\n", encoding="utf-8")
                logger.info("AutomationsManager: creato %s", AUTOMATIONS_FILE)
            except Exception as e:
                return f"❌ Impossibile creare {AUTOMATIONS_FILE}: {e}"

        # 2. Controlla configuration.yaml
        if not CONFIGURATION_FILE.exists():
            warnings.append("⚠️ /config/configuration.yaml non trovato.")
            return "\n".join(warnings)

        try:
            cfg_text = CONFIGURATION_FILE.read_text(encoding="utf-8")
        except Exception:
            warnings.append("⚠️ Impossibile leggere configuration.yaml.")
            return "\n".join(warnings)

        # Controlla se automation: !include automations.yaml è presente
        import re as _re
        if not _re.search(r"automation.*!include.*automations\.yaml", cfg_text):
            warnings.append(
                "⚠️ <b>ATTENZIONE:</b> <code>configuration.yaml</code> non include "
                "<code>automations.yaml</code>.\n"
                "Aggiungi questa riga in <code>configuration.yaml</code>:\n"
                "<pre>automation: !include automations.yaml</pre>\n"
                "Poi riavvia HA per applicare le automazioni."
            )

        return "\n".join(warnings)

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
        if self._entity_registry:
            entities_ctx = self._entity_registry.get_context_for_ai(max_per_domain=30)
        else:
            entities_ctx = self._build_entities_context(state_cache)
        tg_chat = self._telegram_chat_id
        chat_id_str = tg_chat if tg_chat else "<inserisci_chat_id>"
        system = (
            "Sei un esperto Home Assistant. Genera automazioni YAML valide per HA 2024+.\n"
            "\n"
            "REGOLA 1 - ENTITY_ID: usa SOLO quelli dal contesto. Non inventare mai.\n"
            "Formato contesto: [tipo] Nome -> entity_id (stato)\n"
            "Esempio: [light] Luce Cucina -> light.cucina_1 (off) -> usa light.cucina_1\n"
            "\n"
            "REGOLA 2 - SE NON TROVI MATCH CERTO:\n"
            "Rispondi con JSON: {\"error\":\"ambiguous\",\"message\":\"Non trovato X\"}\n"
            "RICERCA: cerca [zona:X] e nomi nel contesto. Solo 1 match certo -> YAML.\n"
            "\n"
            "REGOLA 3 - TELEGRAM: NON usare notify.telegram (deprecato HA 2026+).\n"
            "Usa SEMPRE telegram_bot.send_message con questo formato ESATTO:\n"
            "  - service: telegram_bot.send_message\n"
            "    data:\n"
            f"      chat_id: {chat_id_str}\n"
            "      message: 'testo notifica'\n"
            "\n"
            "FORMATO YAML:\n"
            "```yaml\n- id: 'homemind_slug'\n  alias: 'Nome'\n"
            "  trigger:\n    - platform: ...\n  condition: []\n"
            "  action:\n    - ...\n  mode: single\n```\n"
            "Rispondi SOLO con ```yaml``` o JSON error. Niente prosa."
        )
        prompt = (
            f"Crea automazione per: {description}\n\n"
            f"Entità REALI disponibili (usare SOLO questi entity_id):\n{entities_ctx}"
        )
        try:
            response   = await self.ai.ask(system, prompt, max_tokens=1200)
            # Controlla se l'AI ha risposto con JSON error (entità ambigua)
            _err = self._extract_error(response)
            if _err:
                msg  = _err.get("message", "Entità non trovata nel registro.")
                sugg = _err.get("suggestions", [])
                reply = f"❓ <b>{self._esc(msg)}</b>\n\n"
                if sugg:
                    reply += "Entità disponibili simili:\n"
                    for s in sugg[:8]:
                        reply += f"  • <code>{self._esc(s)}</code>\n"
                reply += "\nRiformula la richiesta usando uno di questi nomi."
                return reply
            yaml_block = self._extract_yaml(response)
            if not yaml_block:
                return "❌ L'AI non ha generato YAML valido. Riprova con una descrizione più specifica."

            # ── Verifica configuration.yaml ──────────────────────────────
            cfg_warning = await self._ensure_automations_included()

            # ── Validazione entity_id ─────────────────────────────────────
            warnings = self._validate_entities(yaml_block, state_cache)
            if cfg_warning:
                warnings = (warnings + "\n" + cfg_warning).strip() if warnings else cfg_warning

            # ── Scrivi su file (upsert: sostituisce se stessa id) ─────────
            ok, msg = await self._upsert_to_file(yaml_block)
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


    async def _upsert_to_file(self, yaml_block: str) -> tuple:
        """
        Scrive l'automazione nel file YAML.
        Se un'automazione con lo stesso id esiste già → la sostituisce.
        Genera un ID unico con timestamp se necessario per evitare duplicati.
        """
        import time as _time
        try:
            # 1. Estrai id dal nuovo blocco
            new_id = self._extract_id(yaml_block)
            if not new_id:
                return False, "id mancante nel YAML"

            # 2. Leggi file corrente
            original = await self._read_file()

            # 3. Se YAML disponibile: parse e rimuovi automazione con stesso id
            if _YAML_AVAILABLE and original.strip():
                try:
                    existing = _yaml.safe_load(original) or []
                    if isinstance(existing, list):
                        # Rimuovi eventuale duplicato con stesso id
                        existing = [a for a in existing
                                    if isinstance(a, dict) and a.get("id") != new_id]
                        # Aggiungi la nuova
                        new_auto = _yaml.safe_load(yaml_block)
                        if isinstance(new_auto, list):
                            existing.extend(new_auto)
                        elif isinstance(new_auto, dict):
                            existing.append(new_auto)
                        content = _yaml.dump(existing, allow_unicode=True,
                                             default_flow_style=False, sort_keys=False)
                        await self._write_file(content)
                        logger.info("AutomationsManager: upsert %s (%d automazioni totali)",
                                    new_id, len(existing))
                        return True, "OK"
                except Exception as _ye:
                    logger.warning("AutomationsManager: YAML parse fallito (%s) → append", _ye)

            # 4. Fallback: semplice append con separatore
            sep = f"\n\n# HomeMind — {now_local().strftime('%Y-%m-%d %H:%M')}\n"
            await self._write_file(original + sep + yaml_block + "\n")
            return True, "OK"

        except Exception as e:
            return False, str(e)

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

    def _extract_error(self, text: str) -> dict | None:
        """Estrae JSON error se l'AI non ha trovato l'entità."""
        import json as _json
        t = text.strip()
        # Cerca JSON con "error" nel testo
        m = re.search(r'\{[^{}]*"error"[^{}]*\}', t, re.DOTALL)
        if m:
            try:
                return _json.loads(m.group(0))
            except Exception:
                pass
        return None

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
