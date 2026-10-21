"""
agent/repairs_checker.py — Controlla HA Repairs API e notifica Telegram.
"""
import asyncio, logging, time

logger = logging.getLogger("homemind.repairs")

CHECK_INTERVAL  = 3600 * 4   # ogni 4 ore
NOTIFY_COOLDOWN = 3600 * 24  # stessa issue max 1 volta al giorno

SEVERITY_ICON = {"critical": "🔴", "error": "🟠", "warning": "🟡", "information": "🔵"}
SEVERITY_RANK = {"critical": 0, "error": 1, "warning": 2, "information": 3}


class RepairsChecker:
    def __init__(self, rest_client, ai, notifier=None):
        self.rest     = rest_client
        self.ai       = ai
        self.notifier = notifier
        self._last_sent: dict = {}   # issue_id → timestamp

    async def start(self):
        asyncio.create_task(self._run_loop(), name="repairs_checker")
        logger.info("RepairsChecker avviato — check ogni %dh", CHECK_INTERVAL // 3600)

    async def _run_loop(self):
        await asyncio.sleep(300)   # attendi 5 min dopo avvio
        while True:
            try:
                await self._check()
            except Exception as e:
                logger.warning("Repairs check fallito: %s", e)
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check(self):
        issues = await self.rest.get_repairs()
        if not issues:
            logger.debug("Nessun repair issue")
            return

        now = time.time()
        new_issues = [
            i for i in issues
            if now - self._last_sent.get(i.get("issue_id", ""), 0) > NOTIFY_COOLDOWN
        ]
        if not new_issues:
            return

        # Ordina per severità
        new_issues.sort(key=lambda x: SEVERITY_RANK.get(x.get("severity", "warning"), 99))

        for issue in new_issues[:3]:  # max 3 per ciclo
            self._last_sent[issue.get("issue_id", "")] = now
            await self._notify_issue(issue)

    async def _notify_issue(self, issue: dict):
        sev    = issue.get("severity", "warning")
        icon   = SEVERITY_ICON.get(sev, "⚠️")
        title  = issue.get("title", "Problema rilevato")
        descr  = issue.get("description", "")
        domain = issue.get("domain", "?")
        iid    = issue.get("issue_id", "")

        # Chiedi all'AI una soluzione pratica
        solution = await self._get_ai_solution(title, descr, domain)

        lines = [
            f"{icon} <b>Repair HA — {sev.upper()}</b>",
            "──────────────────────────",
            f"🏷 <b>Integrazione:</b> <code>{domain}</code>",
            f"❗ <b>{self._esc(title)}</b>",
            "",
        ]
        if descr:
            lines += [f"📄 {self._esc(descr[:300])}", ""]
        if solution:
            lines += [
                "🛠 <b>Come risolvere:</b>",
                solution,
                "",
            ]
        lines += [
            "💡 Vai a <b>Impostazioni → Sistema → Riparazioni</b>",
            "──────────────────────────",
        ]

        msg = "\n".join(lines)
        try:
            await self.notifier._telegram(msg, parse_mode="HTML")
        except Exception as e:
            logger.warning("Notify repair failed: %s", e)

    async def _get_ai_solution(self, title: str, descr: str, domain: str) -> str:
        try:
            system = (
                "Sei un esperto Home Assistant. Dai soluzioni brevi e pratiche "
                "agli errori di HA. Risposta in italiano, max 3 righe, con passi numerati."
            )
            prompt = f"Repair issue in '{domain}':\nTitolo: {title}\nDescrizione: {descr}\nCome si risolve?"
            answer = await self.ai.ask(system, prompt, max_tokens=200)
            # Formatta come lista HTML
            lines = [l.strip() for l in answer.strip().splitlines() if l.strip()][:4]
            return "\n".join(f"  {l}" for l in lines)
        except Exception:
            return ""

    # ── Chiamate da Telegram ────────────────────────────────────────────────

    async def get_repairs_summary(self) -> str:
        issues = await self.rest.get_repairs()
        if not issues:
            return "✅ <b>Riparazioni HA</b>\n\nNessun problema rilevato! Tutto ok."

        issues.sort(key=lambda x: SEVERITY_RANK.get(x.get("severity", "warning"), 99))
        lines = [f"🔧 <b>Riparazioni HA</b> ({len(issues)} problemi)", ""]

        for issue in issues[:8]:
            sev   = issue.get("severity", "warning")
            icon  = SEVERITY_ICON.get(sev, "⚠️")
            title = issue.get("title", "?")
            dom   = issue.get("domain", "?")
            lines.append(f"{icon} <b>{self._esc(title)}</b>")
            lines.append(f"   <code>{dom}</code>")

        if len(issues) > 8:
            lines.append(f"\n<i>... e altri {len(issues)-8} problemi</i>")
        lines += ["", "💡 /riparazione [numero] per dettagli e soluzione"]
        return "\n".join(lines)

    @staticmethod
    def _esc(text: str) -> str:
        return str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
