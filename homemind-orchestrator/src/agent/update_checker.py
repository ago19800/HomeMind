"""
agent/update_checker.py — Controlla aggiornamenti HA e add-on via Supervisor API.
Notifica Telegram quando ci sono update disponibili.
"""
import asyncio
import logging
import time
import aiohttp
import os

logger = logging.getLogger("homemind.updates")

CHECK_INTERVAL  = 3600 * 6   # ogni 6 ore
NOTIFY_COOLDOWN = 3600 * 12  # max 1 notifica ogni 12h per stesso aggiornamento

SUPERVISOR_BASE = "http://supervisor"


class UpdateChecker:
    def __init__(self, notifier=None):
        self.notifier   = notifier
        self._session:  aiohttp.ClientSession | None = None
        self._token     = os.getenv("SUPERVISOR_TOKEN", "")
        self._headers   = {"Authorization": f"Bearer {self._token}"}
        self._last_sent: dict[str, float] = {}   # key → timestamp ultima notifica

    async def start(self):
        self._session = aiohttp.ClientSession(headers=self._headers)
        logger.info("UpdateChecker avviato — check ogni %dh", CHECK_INTERVAL // 3600)
        asyncio.create_task(self._run_loop(), name="update_checker")

    async def stop(self):
        if self._session:
            await self._session.close()

    async def _run_loop(self):
        # Prima esecuzione: aspetta 2 minuti dopo avvio
        await asyncio.sleep(120)
        while True:
            try:
                await self._check()
            except Exception as e:
                logger.warning("Update check fallito: %s", e)
            await asyncio.sleep(CHECK_INTERVAL)

    async def _check(self):
        updates = []

        # ── 1. Home Assistant Core ─────────────────────────────────────────
        try:
            async with self._session.get(f"{SUPERVISOR_BASE}/core/info") as r:
                if r.status == 200:
                    data = (await r.json()).get("data", {})
                    ver     = data.get("version", "?")
                    latest  = data.get("version_latest", "?")
                    if ver != latest and latest != "?":
                        updates.append({
                            "name":    "Home Assistant",
                            "icon":    "🏠",
                            "current": ver,
                            "latest":  latest,
                            "key":     f"ha:{latest}",
                        })
                        logger.info("HA update: %s → %s", ver, latest)
        except Exception as e:
            logger.debug("HA core info fallito: %s", e)

        # ── 2. Supervisor ──────────────────────────────────────────────────
        try:
            async with self._session.get(f"{SUPERVISOR_BASE}/supervisor/info") as r:
                if r.status == 200:
                    data = (await r.json()).get("data", {})
                    ver    = data.get("version", "?")
                    latest = data.get("version_latest", "?")
                    if ver != latest and latest != "?":
                        updates.append({
                            "name":    "Supervisor",
                            "icon":    "⚙️",
                            "current": ver,
                            "latest":  latest,
                            "key":     f"supervisor:{latest}",
                        })
        except Exception as e:
            logger.debug("Supervisor info fallito: %s", e)

        # ── 3. Add-on installati ───────────────────────────────────────────
        try:
            async with self._session.get(f"{SUPERVISOR_BASE}/addons") as r:
                if r.status == 200:
                    addons = (await r.json()).get("data", {}).get("addons", [])
                    for a in addons:
                        if a.get("update_available"):
                            updates.append({
                                "name":    a.get("name", a.get("slug", "?")),
                                "icon":    "🔌",
                                "current": a.get("version", "?"),
                                "latest":  a.get("version_latest", "?"),
                                "key":     f"addon:{a.get('slug','')}:{a.get('version_latest','')}",
                            })
        except Exception as e:
            logger.debug("Add-on list fallito: %s", e)

        if not updates:
            logger.debug("Nessun aggiornamento disponibile")
            return

        # Filtra già notificati (cooldown)
        now = time.time()
        new_updates = [
            u for u in updates
            if now - self._last_sent.get(u["key"], 0) > NOTIFY_COOLDOWN
        ]

        if not new_updates:
            logger.debug("%d update già notificati in precedenza", len(updates))
            return

        # Segna come notificati
        for u in new_updates:
            self._last_sent[u["key"]] = now

        await self._notify(new_updates)

    async def _notify(self, updates: list):
        if not self.notifier:
            return

        lines = [
            "🆙 <b>Aggiornamenti disponibili!</b>",
            "",
        ]
        for u in updates:
            lines.append(
                f"{u['icon']} <b>{u['name']}</b>\n"
                f"   {u['current']} → <b>{u['latest']}</b>"
            )
        lines += [
            "",
            "💡 Aggiorna da <b>Impostazioni → Sistema → Aggiornamenti</b>",
        ]

        msg = "\n".join(lines)
        logger.info("Notifica %d aggiornamenti", len(updates))

        try:
            # Usa direttamente Telegram con HTML (bypassa il rate-limit generico)
            await self.notifier._telegram(msg, parse_mode="HTML")
        except Exception as e:
            logger.warning("Notifica update fallita: %s", e)

    async def check_now(self) -> str:
        """Chiamato da comando Telegram '/aggiornamenti'."""
        lines = []
        try:
            async with self._session.get(f"{SUPERVISOR_BASE}/core/info") as r:
                if r.status == 200:
                    data = (await r.json()).get("data", {})
                    ver, latest = data.get("version","?"), data.get("version_latest","?")
                    icon = "✅" if ver == latest else "🆙"
                    ha_line = f"🏠 <b>Home Assistant</b>: {ver} {icon}"
                    if ver != latest:
                        ha_line += f" → <b>{latest}</b>"
                    lines.append(ha_line)

            async with self._session.get(f"{SUPERVISOR_BASE}/supervisor/info") as r:
                if r.status == 200:
                    data = (await r.json()).get("data", {})
                    ver, latest = data.get("version","?"), data.get("version_latest","?")
                    icon = "✅" if ver == latest else "🆙"
                    sv_line = f"⚙️ <b>Supervisor</b>: {ver} {icon}"
                    if ver != latest:
                        sv_line += f" → <b>{latest}</b>"
                    lines.append(sv_line)

            async with self._session.get(f"{SUPERVISOR_BASE}/addons") as r:
                if r.status == 200:
                    addons = (await r.json()).get("data", {}).get("addons", [])
                    addon_updates = [a for a in addons if a.get("update_available")]
                    if addon_updates:
                        lines.append(f"\n🔌 <b>Add-on da aggiornare ({len(addon_updates)}):</b>")
                        for a in addon_updates[:10]:
                            lines.append(
                                f"  • {a.get('name','?')}: "
                                f"{a.get('version','?')} → <b>{a.get('version_latest','?')}</b>"
                            )
                    else:
                        lines.append("🔌 <b>Add-on</b>: tutti aggiornati ✅")

        except Exception as e:
            lines.append(f"❌ Errore: {e}")

        return "\n".join(lines)
