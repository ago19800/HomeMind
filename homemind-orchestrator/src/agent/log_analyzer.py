"""
agent/log_analyzer.py — Legge log HA, analizza errori critici con AI,
propone soluzioni repair formattate per Telegram.
"""
import asyncio
import logging
import re
import time
import aiofiles
from pathlib import Path
from datetime import datetime
from utils.timezone_helper import now_local

from agent.ai_provider import AIProvider, SYSTEM_LOG_ANALYZER

logger = logging.getLogger("homemind.log_analyzer")

CONFIG_DIR  = Path("/config")
PATCH_DIR   = Path("/config/homemind_patches")

LOG_PATTERN = re.compile(
    r"(?P<level>ERROR|CRITICAL)\s+.*?\[(?P<module>[^\]]+)\]\s+(?P<message>.+)",
    re.IGNORECASE,
)

IGNORE_PATTERNS = [
    r"healthchecks", r"aiohttp\.access", r"asyncio.*cancel",
    r"ConnectionRefusedError.*hc-ping", r"task was destroyed", r"ssl.*certificate",
]

ERROR_COOLDOWN = 3600  # 1 ora tra stessi errori


class LogAnalyzer:
    def __init__(self, ai: AIProvider, rest_client, auto_fix: bool = False,
                 interval: int = 300, notifier=None):
        self.ai        = ai
        self.rest      = rest_client
        self.auto_fix  = auto_fix
        self.interval  = interval
        self.notifier  = notifier
        self._seen:      set     = set()
        self._last_sent: dict    = {}

    async def run_forever(self):
        logger.info("Log analyzer avviato (interval=%ds)", self.interval)
        await asyncio.sleep(180)  # avvia dopo 3 min
        while True:
            try:
                await self._analyze_cycle()
            except Exception as e:
                logger.error("Log cycle fallito: %s", e)
            await asyncio.sleep(self.interval)

    async def _analyze_cycle(self):
        raw_log = await self.rest.get_error_log()
        if not raw_log:
            return
        new_errors = self._extract_new_errors(raw_log)
        if not new_errors:
            return
        logger.info("%d nuovi errori critici", len(new_errors))
        yaml_ctx = await self._load_yaml_context()
        for err in new_errors[:3]:
            await self._handle_error(err, yaml_ctx)

    def _extract_new_errors(self, raw_log: str) -> list:
        errors = []
        for line in raw_log.splitlines():
            if any(re.search(p, line, re.IGNORECASE) for p in IGNORE_PATTERNS):
                continue
            m = LOG_PATTERN.match(line.strip())
            if not m:
                continue
            fp = f"{m.group('module')}::{m.group('message')[:100]}"
            if fp in self._seen:
                continue
            self._seen.add(fp)
            errors.append({
                "level":   m.group("level"),
                "module":  m.group("module"),
                "message": m.group("message"),
                "fp":      fp,
            })
        return errors

    async def _load_yaml_context(self) -> str:
        parts = []
        for fname in ["configuration.yaml", "packages/homemind_fixes.yaml"]:
            fpath = CONFIG_DIR / fname
            if fpath.exists():
                try:
                    async with aiofiles.open(str(fpath), "r") as f:
                        content = await f.read()
                    parts.append(f"### {fname}\n{content[:1500]}")
                except Exception:
                    pass
        return "\n\n".join(parts)

    async def _handle_error(self, error: dict, yaml_ctx: str):
        fp = error["fp"]
        if time.time() - self._last_sent.get(fp, 0) < ERROR_COOLDOWN:
            return

        prompt = (
            f"## Errore HA\n"
            f"- Livello: {error['level']}\n"
            f"- Modulo: {error['module']}\n"
            f"- Messaggio: {error['message']}\n\n"
            f"## Config\n{yaml_ctx}\n\n"
            "Rispondi con:\n"
            "1. CAUSA: spiegazione breve (max 2 righe)\n"
            "2. SOLUZIONE: passi concreti per risolvere\n"
            "3. PATCH: ```yaml solo se serve correzione YAML```\n"
            "Conciso, italiano, pratico."
        )
        try:
            analysis = await self.ai.ask(SYSTEM_LOG_ANALYZER, prompt, max_tokens=700)
            patch = self._extract_yaml_patch(analysis)
            if patch:
                await self._save_patch(patch, error["module"])
            self._last_sent[fp] = time.time()
            if self.notifier:
                await self._notify_rich(error, analysis, patch)
            if self.auto_fix and patch:
                await self._auto_apply(patch, error["module"])
        except Exception as e:
            logger.error("Handle error fallito: %s", e)

    async def _notify_rich(self, error: dict, analysis: str, patch: str):
        level  = error["level"]
        module = error["module"]
        msg    = error["message"]
        icon   = "🔴" if level == "CRITICAL" else "🟠"

        causa = self._extract_section(analysis, "CAUSA")
        soluz = self._extract_section(analysis, "SOLUZIONE")

        lines = [
            f"{icon} <b>Errore {level} in Home Assistant</b>",
            "──────────────────────────",
            f"📦 <b>Modulo:</b> <code>{self._esc(module)}</code>",
            f"❗ {self._esc(msg[:150])}",
            "",
        ]
        if causa:
            lines += [f"🔍 <b>Causa:</b>", f"  {self._esc(causa[:250])}", ""]
        if soluz:
            lines.append("🛠 <b>Come risolvere:</b>")
            for i, step in enumerate(self._split_steps(soluz), 1):
                lines.append(f"  {i}. {self._esc(step)}")
            lines.append("")
        if patch:
            lines.append("📋 <b>Patch YAML generata</b> — aprire HomeMind per applicarla ✅")
        lines += ["──────────────────────────", f"🕐 <i>{now_local().strftime('%H:%M:%S')}</i>"]

        try:
            await self.notifier._telegram("\n".join(lines), parse_mode="HTML")
        except Exception as e:
            logger.warning("Notify error rich fallita: %s", e)

    def _extract_yaml_patch(self, text: str) -> str:
        m = re.search(r"```ya?ml\n(.+?)```", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    def _extract_section(self, text: str, keyword: str) -> str:
        pat = rf"(?:\d+\.\s*)?{keyword}:?\s*(.+?)(?=(?:\d+\.\s*)?(?:CAUSA|SOLUZIONE|PATCH)|$)"
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    def _split_steps(self, text: str) -> list:
        parts = re.split(r"\n[-•]\s*|\n\d+\.\s*|\n\n", text)
        return [p.strip() for p in parts if p.strip()][:5]

    @staticmethod
    def _esc(text: str) -> str:
        return str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

    async def _save_patch(self, patch_yaml: str, module: str):
        PATCH_DIR.mkdir(exist_ok=True)
        ts   = now_local().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9]", "_", module.lower())[:30]
        path = PATCH_DIR / f"patch_{ts}_{slug}.yaml"
        async with aiofiles.open(str(path), "w") as f:
            await f.write(f"# HomeMind Log-Patch — {ts}\n# Modulo: {module}\n\n{patch_yaml}\n")

    async def _auto_apply(self, patch_yaml: str, module: str):
        from agent.patch_writer import PatchWriter
        m = re.search(r"unique_id:\s*(\S+)", patch_yaml)
        uid = m.group(1) if m else f"logfix_{re.sub(r'[^a-z0-9]','_',module.lower())[:40]}_{int(time.time())}"
        try:
            ok, msg = await PatchWriter().apply_sensor_patch(uid, patch_yaml)
            if ok:
                try: await self.rest.call_service("homeassistant","reload_template_entities",{})
                except Exception: pass
        except Exception as e:
            logger.error("Auto-apply fallito: %s", e)
