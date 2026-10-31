"""
HA Terminal — accesso a info di sistema Home Assistant e comandi via Supervisor.

Tre modalità:
1. **Supervisor API**: info host (RAM, CPU, disco, temperatura, network) — sempre disponibile
2. **Core REST**: chiama qualsiasi servizio HA, incluso shell_command.* configurati dall'utente
3. **Container shell**: tool_natural_shell esistente per il container HomeMind

L'AI capisce la richiesta in NL e sceglie il metodo giusto.
"""

import asyncio
import os
import json
import logging
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)

SUPERVISOR_URL  = "http://supervisor"
CORE_URL        = "http://supervisor/core"


class HATerminal:
    """Accesso info sistema HA + esecuzione comandi via REST."""

    def __init__(self, supervisor_token: str = "", ha_token: str = ""):
        self.supervisor_token = supervisor_token
        self.ha_token = ha_token
        # SSH: legge da person_config.json (UI HomeMind) con fallback su env (run.sh / opzioni HA)
        self._reload_ssh_from_config()

    def _reload_ssh_from_config(self):
        """Ricarica le credenziali SSH da person_config.json (se esistente), poi da env."""
        cfg = {}
        cfg_path = "/config/homemind_patches/person_config.json"
        try:
            with open(cfg_path, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
        except Exception:
            pass
        self.ssh_host     = cfg.get("ssh_host")     or os.getenv("HM_SSH_HOST", "homeassistant")
        self.ssh_port     = int(cfg.get("ssh_port")  or os.getenv("HM_SSH_PORT", "22"))
        self.ssh_username = cfg.get("ssh_username") or os.getenv("HM_SSH_USER", "root")
        self.ssh_password = cfg.get("ssh_password", "") or os.getenv("HM_SSH_PASS", "")
        logger.debug("SSH config: %s@%s:%s", self.ssh_username, self.ssh_host, self.ssh_port)

    # ══════════════════════════════════════════════════════════════════
    # SUPERVISOR API — info host
    # ══════════════════════════════════════════════════════════════════

    async def _supervisor_get(self, path: str) -> dict:
        """GET su Supervisor API."""
        if not self.supervisor_token:
            return {"success": False, "message": "SUPERVISOR_TOKEN non disponibile"}
        url = f"{SUPERVISOR_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.supervisor_token}",
            "Accept": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15)) as r:
                    body = await r.text()
                    if r.status != 200:
                        return {"success": False,
                                "message": f"HTTP {r.status}: {body[:300]}"}
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError:
                        return {"success": False,
                                "message": f"JSON non valido: {body[:200]}"}
                    return {"success": True, "data": data.get("data", data)}
        except Exception as e:
            return {"success": False, "message": f"Errore: {str(e)[:200]}"}

    async def _supervisor_post(self, path: str, payload: dict,
                               timeout: int = 30) -> dict:
        """POST su Supervisor API."""
        import json as _j
        if not self.supervisor_token:
            return {"success": False, "http_status": None,
                    "message": "SUPERVISOR_TOKEN non disponibile"}
        url = f"{SUPERVISOR_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self.supervisor_token}",
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                    body = await r.text()
                    if r.status == 405:
                        return {"success": False, "http_status": 405,
                                "message": f"Endpoint {path} non supportato (HTTP 405)"}
                    if r.status not in (200, 201):
                        return {"success": False, "http_status": r.status,
                                "message": f"HTTP {r.status}: {body[:300]}"}
                    try:
                        data = _j.loads(body)
                        return {"success": True, "data": data.get("data", data),
                                "http_status": r.status}
                    except Exception:
                        return {"success": True, "data": body, "http_status": r.status}
        except asyncio.TimeoutError:
            return {"success": False, "http_status": None,
                    "message": f"Timeout dopo {timeout}s"}
        except Exception as e:
            return {"success": False, "http_status": None,
                    "message": f"Errore: {str(e)[:200]}"}

    async def ssh_exec(self, command: str, timeout: int = 30) -> dict:
        """Esegue comando sull'host via SSH - addon Terminal & SSH porta 22222."""
        try:
            import asyncssh as _ssh
        except ImportError:
            return {"success": False, "via": "ssh", "needs_install": True,
                    "message": "❌ asyncssh non installato — riavvia addon."}

        host = self.ssh_host or "127.0.0.1"
        port = self.ssh_port or 22222
        user = self.ssh_username or "root"
        pwd  = self.ssh_password or ""

        opts = dict(host=host, port=port, username=user,
                    known_hosts=None, connect_timeout=10)
        if pwd:
            opts["password"] = pwd

        try:
            async with _ssh.connect(**opts) as conn:
                # Codifica il comando in base64 per evitare problemi di quoting/glob
                # con qualsiasi shell (zsh, bash, ash) sull'host HA.
                # Senza questo, caratteri come ^ [ ] | ' nel comando vengono
                # interpretati dalla shell remota come glob/history expansion.
                import base64 as _b64
                _cmd_b64 = _b64.b64encode(command.encode()).decode()
                _cmd_wrapped = f"bash -l -c 'eval \"$(echo {_cmd_b64} | base64 -d)\"'"
                res = await conn.run(_cmd_wrapped, timeout=timeout, check=False)
                # Fallback 1: bash senza -l (PATH ridotto ma funziona)
                if res.exit_status == 127 and "bash" in (res.stderr or ""):
                    _cmd_wrapped2 = f"bash -c 'eval \"$(echo {_cmd_b64} | base64 -d)\"'"
                    res = await conn.run(_cmd_wrapped2, timeout=timeout, check=False)
                # Fallback 2: sh (busybox/ash) se bash non disponibile
                if res.exit_status == 127 and "bash" in (res.stderr or ""):
                    _cmd_wrapped3 = f"sh -c 'eval \"$(echo {_cmd_b64} | base64 -d)\"'"
                    res = await conn.run(_cmd_wrapped3, timeout=timeout, check=False)
                return {
                    "success": (res.exit_status or 0) == 0,
                    "stdout":  res.stdout or "",
                    "stderr":  res.stderr or "",
                    "returncode": res.exit_status or 0,
                    "command": command,
                    "via": f"ssh://{host}:{port}",
                }
        except _ssh.PermissionDenied:
            return {"success": False, "via": "ssh",
                    "message": f"❌ SSH: accesso negato {host}:{port} user={user}\nVerifica credenziali nelle opzioni HomeMind."}
        except OSError as e:
            return {"success": False, "via": "ssh",
                    "message": f"❌ SSH: connessione fallita {host}:{port}\n{str(e)[:200]}"}
        except Exception as e:
            return {"success": False, "via": "ssh",
                    "message": f"❌ SSH errore: {str(e)[:300]}"}

    async def ha_cli(self, command: str) -> dict:
        """Esegue comandi HA CLI via Supervisor API (alternativa a 'ha <cmd>' su SSH).
        
        Supporta: ha backups list, ha core info, ha supervisor info, ha addons list, ecc.
        """
        # Mappa comandi ha cli → endpoint Supervisor
        cmd = command.strip().lower()
        # Rimuovi prefisso 'ha ' se presente
        if cmd.startswith("ha "):
            cmd = cmd[3:]
        
        _route_map = {
            "backups list":        ("/backups",              "backups"),
            "backups":             ("/backups",              "backups"),
            "backup list":         ("/backups",              "backups"),
            "core info":           ("/core/info",            None),
            "core update":         ("/core/update",          None),
            "core restart":        ("/core/restart",         None),
            "core logs":           ("/core/logs",            None),
            "supervisor info":     ("/supervisor/info",      None),
            "supervisor logs":     ("/supervisor/logs",      None),
            "supervisor update":   ("/supervisor/update",    None),
            "addons list":         ("/addons",               "addons"),
            "addon list":          ("/addons",               "addons"),
            "os info":             ("/os/info",              None),
            "os update":           ("/os/update",            None),
            "host info":           ("/host/info",            None),
            "host reboot":         ("/host/reboot",          None),
            "host shutdown":       ("/host/shutdown",        None),
            "network info":        ("/network/info",         None),
            "dns info":            ("/dns/info",             None),
            "resolution info":     ("/resolution/info",      None),
        }
        
        endpoint = None
        data_key = None
        for key, (ep, dk) in _route_map.items():
            if cmd.startswith(key):
                endpoint = ep
                data_key = dk
                break
        
        # ── Gestione addon stop/start/restart con risoluzione nome → slug ──────
        for _action in ("addons stop ", "addons start ", "addons restart ",
                        "addon stop ",  "addon start ",  "addon restart "):
            if cmd.startswith(_action):
                _verb       = _action.strip().split()[-1]   # stop/start/restart
                _name_query = cmd[len(_action):].strip()
                _slug       = await self._resolve_addon_slug(_name_query)
                if not _slug:
                    return {"success": False,
                            "message": (f"❌ Addon non trovato: <code>{_name_query}</code>\n"
                                        f"Usa <code>ha addons list</code> per vedere gli slug disponibili.")}
                if _verb == "stop":
                    _r = await self.addon_stop(_slug)
                elif _verb == "start":
                    _r = await self.addon_start(_slug)
                else:
                    _r = await self.addon_restart(_slug)
                if _r.get("success"):
                    _icon = {"stop": "⏹️", "start": "▶️", "restart": "🔄"}[_verb]
                    return {"success": True, "channel": "supervisor_cli",
                            "result": f"{_icon} Addon <b>{_slug}</b>: {_verb} eseguito con successo"}
                else:
                    return {"success": False,
                            "message": f"❌ {_verb} addon <b>{_slug}</b> fallito: {_r.get('message', 'errore')}"}

        if not endpoint:
            return {"success": False,
                    "message": f"⚠️ Comando HA CLI non supportato via API: <code>ha {cmd}</code>\n"
                               f"Comandi supportati: {', '.join(_route_map.keys())}\n"
                               f"Per addon: <code>ha addons stop/start/restart &lt;nome&gt;</code>"}
        
        res = await self._supervisor_get(endpoint)
        if not res.get("success"):
            return res
        
        data = res.get("data", {})
        if data_key and data_key in data:
            items = data[data_key]
            if isinstance(items, list):
                lines = [f"📋 <b>ha {cmd}</b> ({len(items)} elementi)\n"]
                for item in items[:20]:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("slug") or item.get("date") or str(item)[:60]
                        state = item.get("state", item.get("protected", ""))
                        lines.append(f"  • {name}" + (f" — {state}" if state else ""))
                    else:
                        lines.append(f"  • {str(item)[:100]}")
                return {"success": True, "result": "\n".join(lines), "channel": "supervisor_cli", "data": items}
        
        import json as _json
        pretty = _json.dumps(data, indent=2, ensure_ascii=False, default=str)[:3000]
        return {"success": True, "result": f"📋 <b>ha {cmd}</b>\n\n<pre>{pretty}</pre>",
                "channel": "supervisor_cli", "data": data}


    async def host_info(self) -> dict:
        """Info host: kernel, hostname, OS, architettura."""
        return await self._supervisor_get("/host/info")

    async def host_resources(self) -> dict:
        """RAM, CPU, disco — chiamando supervisor stats e core stats."""
        results = {}
        # Stats supervisor
        sup = await self._supervisor_get("/supervisor/stats")
        if sup.get("success"):
            results["supervisor"] = sup["data"]
        # Info OS
        os_info = await self._supervisor_get("/os/info")
        if os_info.get("success"):
            results["os"] = os_info["data"]
        # Stats core
        core = await self._supervisor_get("/core/stats")
        if core.get("success"):
            results["core"] = core["data"]
        # Info host base
        host = await self._supervisor_get("/host/info")
        if host.get("success"):
            results["host"] = host["data"]
        return {"success": bool(results), "data": results}

    async def addons_list(self) -> dict:
        """Elenca tutti gli addon installati."""
        return await self._supervisor_get("/addons")

    async def addon_stats(self, slug: str) -> dict:
        """Stats di un singolo addon (CPU/RAM/network)."""
        return await self._supervisor_get(f"/addons/{slug}/stats")

    async def addon_stop(self, slug: str) -> dict:
        """Ferma un addon via Supervisor API."""
        return await self._supervisor_post(f"/addons/{slug}/stop", {})

    async def addon_start(self, slug: str) -> dict:
        """Avvia un addon via Supervisor API."""
        return await self._supervisor_post(f"/addons/{slug}/start", {})

    async def addon_restart(self, slug: str) -> dict:
        """Riavvia un addon via Supervisor API."""
        return await self._supervisor_post(f"/addons/{slug}/restart", {})

    async def _resolve_addon_slug(self, name_or_slug: str) -> str | None:
        """Risolve un nome addon (anche parziale/approssimato) nel suo slug esatto.
        
        Es: "ai automation generator" → "google_ai_automation"
            "mosquitto"               → "core_mosquitto"
        """
        r = await self._supervisor_get("/addons")
        if not r.get("success"):
            return None
        addons = r.get("data", {}).get("addons", [])
        name_lower = name_or_slug.strip().lower()
        # 1. Match esatto su slug
        for a in addons:
            if a.get("slug", "").lower() == name_lower:
                return a["slug"]
        # 2. Match esatto su nome
        for a in addons:
            if a.get("name", "").lower() == name_lower:
                return a["slug"]
        # 3. Match parziale su slug o nome (tutte le parole devono matchare)
        words = [w for w in name_lower.split() if len(w) > 2]
        if words:
            best_slug = None
            best_score = 0
            for a in addons:
                target = (a.get("name", "") + " " + a.get("slug", "")).lower()
                score = sum(1 for w in words if w in target)
                if score > best_score:
                    best_score = score
                    best_slug = a["slug"]
            if best_score >= max(1, len(words) - 1):  # almeno N-1 parole trovate
                return best_slug
        return None

    async def network_info(self) -> dict:
        """Info network: interfacce, IP, gateway."""
        return await self._supervisor_get("/network/info")

    async def host_bash(self, command: str, timeout: int = 30) -> dict:
        """Esegue comando bash sull'HOST reale HA.
        Strategia a 4 livelli:
        0. Se il comando opera SOLO su /config → esegui nel container (già montato rw)
        1. Supervisor /host/bash (full_access=true)
        2. SSH porta configurata (default 22)
        3. nsenter PID 1 (host_pid=true)
        """
        # ── LIVELLO 0: /config è già montato nel container — esegui localmente ──
        # Evita SSH/nsenter per comandi che non hanno bisogno dell'host reale
        _cmd_stripped = command.strip()
        _config_only_cmds = ("grep", "cat", "find", "ls", "head", "tail",
                              "wc", "diff", "stat", "file", "less", "more",
                              "awk", "sed", "sort", "uniq", "cut", "tr",
                              "cp", "mv", "mkdir", "rm", "touch", "chmod",
                              "echo", "tee", "xargs")
        _first_word = _cmd_stripped.split()[0] if _cmd_stripped else ""
        # Se il comando usa solo path /config/* e non richiede accesso host
        _has_host_path = any(p in _cmd_stripped for p in
                              ("/proc", "/sys", "/run", "/var", "/etc",
                               "/dev", "/boot", "/home", "/root", "/usr",
                               "systemctl", "journalctl", "docker", "nmcli",
                               "ip addr", "ip route", "ps ", "top", "free",
                               "df ", "netstat", "ss "))
        _is_config_cmd = (
            _first_word in _config_only_cmds
            and "/config" in _cmd_stripped
            and not _has_host_path
        )
        if _is_config_cmd:
            try:
                import asyncio as _aio0, subprocess as _sp0
                proc = await _aio0.create_subprocess_exec(
                    "/bin/sh", "-c", _cmd_stripped,
                    stdout=_sp0.PIPE, stderr=_sp0.PIPE)
                try:
                    stdout_b, stderr_b = await _aio0.wait_for(
                        proc.communicate(), timeout=timeout)
                    return {
                        "success": (proc.returncode or 0) == 0,
                        "stdout": stdout_b.decode("utf-8", errors="replace"),
                        "stderr": stderr_b.decode("utf-8", errors="replace"),
                        "returncode": proc.returncode or 0,
                        "command": command,
                        "via": "container_shell",
                    }
                except _aio0.TimeoutError:
                    proc.kill()
                    return {"success": False, "message": "⏱ Timeout comando", "via": "container_shell"}
            except Exception as _e0:
                logger.debug("host_bash livello 0 fallito: %s — continuo con SSH", _e0)

        if not self.supervisor_token:
            return {"success": False, "message": "❌ SUPERVISOR_TOKEN non disponibile"}

        # LIVELLO 1: Supervisor /host/bash
        r1 = await self._supervisor_post("/host/bash",
                                         {"command": command}, timeout=timeout)
        if r1.get("success"):
            d = r1.get("data", {})
            stdout = (d.get("stdout") or d.get("output") or
                      (d if isinstance(d, str) else ""))
            stderr = d.get("stderr", "")
            rc = int(d.get("returncode", d.get("exit_code", 0)))
            return {"success": rc == 0, "stdout": str(stdout),
                    "stderr": str(stderr), "returncode": rc,
                    "command": command, "via": "supervisor_host_bash"}

        if r1.get("http_status") not in (404, 405, None):
            return {"success": False, "message": r1.get("message", "Errore"),
                    "fallback": False}

        # LIVELLO 2: SSH verso host (porta configurata, default 22)
        r_ssh = await self.ssh_exec(command, timeout=timeout)
        if r_ssh.get("success"):
            return r_ssh
        if "connessione fallita" not in r_ssh.get("message", "") and            not r_ssh.get("needs_install"):
            # SSH raggiunto ma comando fallito (rc != 0) — restituisci output
            return r_ssh
        logger.debug("SSH livello 2 fallito: %s", r_ssh.get("message","")[:80])

        # LIVELLO 3: nsenter PID 1 host (richiede host_pid=true nel manifest)
        try:
            import asyncio as _aio2, subprocess as _sp
            ns_cmd = ["nsenter", "-t", "1", "-m", "-u", "-n", "-p",
                      "--", "/bin/sh", "-c", command]
            proc = await _aio2.create_subprocess_exec(
                *ns_cmd, stdout=_sp.PIPE, stderr=_sp.PIPE)
            try:
                stdout_b, stderr_b = await _aio2.wait_for(
                    proc.communicate(), timeout=timeout)
                rc2 = proc.returncode
                if rc2 is not None:
                    return {
                        "success": rc2 == 0,
                        "stdout": stdout_b.decode("utf-8", errors="replace"),
                        "stderr": stderr_b.decode("utf-8", errors="replace"),
                        "returncode": rc2, "command": command,
                        "via": "nsenter_pid1"
                    }
            except _aio2.TimeoutError:
                proc.kill()
        except FileNotFoundError:
            pass  # nsenter non installato
        except Exception:
            pass

        # LIVELLO 4: Fallback informativo
        return {
            "success": False, "fallback": True,
            "message": (
                "❌ Accesso host non disponibile.\n"
                "Soluzione: riavvia l'addon HomeMind — questa versione include\n"
                "full_access=true + host_pid=true nel manifest.\n"
                "Se persiste, installa 'Terminal & SSH' dall'HA Store."
            )
        }

    # ══════════════════════════════════════════════════════════════════
    # CORE REST — shell_command e altri servizi
    # ══════════════════════════════════════════════════════════════════

    async def list_services(self, domain: str = "shell_command") -> dict:
        """Elenca i servizi HA di un dominio (default shell_command)."""
        token = self.ha_token or self.supervisor_token
        if not token:
            return {"success": False, "message": "Token non disponibile"}
        url = f"{CORE_URL}/api/services"
        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status != 200:
                        return {"success": False, "message": f"HTTP {r.status}"}
                    data = await r.json()
                    # data è una lista [{domain, services: {name: meta}}, ...]
                    for item in data:
                        if item.get("domain") == domain:
                            return {"success": True,
                                    "services": list(item.get("services", {}).keys())}
                    return {"success": True, "services": []}
        except Exception as e:
            return {"success": False, "message": f"Errore: {str(e)[:200]}"}

    async def call_shell_command(self, service_name: str,
                                   data: Optional[dict] = None) -> dict:
        """Chiama un servizio shell_command.<name> di HA."""
        token = self.ha_token or self.supervisor_token
        if not token:
            return {"success": False, "message": "Token non disponibile"}
        url = f"{CORE_URL}/api/services/shell_command/{service_name}"
        headers = {"Authorization": f"Bearer {token}",
                   "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, headers=headers,
                        json=data or {},
                        timeout=aiohttp.ClientTimeout(total=30)) as r:
                    body = await r.text()
                    if r.status not in (200, 201):
                        return {"success": False,
                                "message": f"HTTP {r.status}: {body[:300]}"}
                    return {"success": True,
                            "message": f"✅ shell_command.{service_name} eseguito",
                            "response": body[:1500]}
        except Exception as e:
            return {"success": False, "message": f"Errore: {str(e)[:200]}"}

    # ══════════════════════════════════════════════════════════════════
    # FORMATTERS
    # ══════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════
    # NATURAL LANGUAGE ROUTING — l'AI sceglie il canale giusto
    # ══════════════════════════════════════════════════════════════════

    async def run_natural(self, user_request: str, ai_cb=None) -> dict:
        """Riceve richiesta NL, AI decide il canale e esegue.

        Canali disponibili:
        - "host_info": info sistema (RAM/CPU/disco/OS) via Supervisor
        - "addons":    lista addon
        - "addon_stats": stats di un addon specifico
        - "shell_command": chiama un shell_command HA configurato
        - "ha_service": chiama un servizio HA generico

        Returns:
            {success, channel, result, raw}
        """
        if not ai_cb:
            return {"success": False, "result": "AI non disponibile"}

        # ── PRE-ROUTING DETERMINISTICO: file operations su /config ────────────
        # Prima di chiedere all'AI, controlliamo se la richiesta ha la chiara
        # firma di un'operazione su file dell'utente (creazione/cancellazione/
        # lettura/listing di percorsi sotto /config). In quel caso forziamo
        # container_shell senza coinvolgere l'AI: previene il bug del
        # comando rm -rf eseguito sull'host con un path che esiste solo nel
        # container.
        import re as _re_route
        _req_low = user_request.strip().lower()
        # parole chiave file-op (it+en)
        _FILE_VERBS = (r"elimina|cancella|rimuov[io]|rimuovi|cestina|sposta|copia|"
                       r"crea(?!.*addon)|nuova|nuovo|leggi|mostra(?:mi)?|apri|"
                       r"lista|elenca|"
                       r"delete|remove|move|copy|create(?!.*addon)|"
                       r"read|show|open|list")
        # path-like pattern: nome semplice (es. "prova"), nome con / (es. "ago/x"),
        # con estensione (es. "test.md"), o esplicitamente /config/*
        _PATH_PATTERN = (r"(?:/config/[\w./_-]+|"
                         r"(?:ago|progetti|test|prova|backup|notes|appunti|tmp|temp|"
                         r"docs|lovelace|themes|custom_components|www|media|"
                         r"automations|scripts|scenes|configuration|secrets|"
                         r"homemind_patches|integrations|blueprints)[\w./_-]*|"
                         r"\b[\w_-]+\.(?:md|txt|yaml|yml|json|html|py|js|css|sh|conf|log|ini|toml|csv|tsv|bak|tar|zip|gz)\b)")
        _is_file_op = bool(
            _re_route.search(_FILE_VERBS, _req_low) and
            _re_route.search(_PATH_PATTERN, _req_low)
        )
        # Override esplicito: se l'utente menziona /config esplicitamente è
        # SEMPRE container_shell (anche senza verbo riconosciuto)
        _mentions_config = "/config" in _req_low or "config/" in _req_low
        if _is_file_op or _mentions_config:
            # routa direttamente al container, passando la richiesta naturale
            # così l'AI interna a container_shell genera il comando corretto
            from tools_system import tool_natural_shell as _tns, tool_install_package as _tip, _INSTALLABLE_PACKAGES
            r = await _tns(user_request, ai_cb=ai_cb)
            if r.get("package_missing") and r.get("install_suggestion"):
                pkg = r["install_suggestion"].replace("apk add ", "").strip().split()[0]
                if pkg in _INSTALLABLE_PACKAGES:
                    ir = await _tip(pkg)
                    if ir.get("success"):
                        r = await _tns(user_request, ai_cb=ai_cb)
            out = ""
            if r.get("stdout"):
                out += f"<pre>{r['stdout'][:3000]}</pre>"
            if not r.get("success") and r.get("stderr"):
                out += f"<pre>{r['stderr'][:1000]}</pre>"
            return {
                "success": r.get("success", False),
                "channel": "container_shell",
                "result": (f"💻 <code>{r.get('command','')}</code>\n"
                           f"{r.get('message','')}\n{out}").strip(),
                "raw": r,
            }

        # Lista shell_command disponibili dell'utente
        sc_list = await self.list_services("shell_command")
        sc_available = sc_list.get("services", []) if sc_list.get("success") else []

        sc_str = ", ".join(sc_available) if sc_available else "(nessuno configurato)"
        sys_prompt = (
            "Sei un router per Home Assistant. Decidi quale canale usare.\n\n"
            "═══ REGOLA CRITICA: HOST vs CONTAINER ═══\n"
            "I file sotto /config (es. /config/ago, /config/prova, /config/automations.yaml,\n"
            "qualsiasi file dell'utente, qualsiasi cartella creata dall'utente come 'ago',\n"
            "'progetti', 'prova', 'test', ecc.) vivono nel CONTAINER HomeMind.\n"
            "→ Per CREARE/LEGGERE/CANCELLARE/MODIFICARE/COPIARE file dell'utente usa container_shell.\n"
            "→ Per info di sistema (RAM, CPU, processi, rete, addon) usa host_bash.\n"
            "Esempio CORRETTO:\n"
            "  utente: 'elimina la cartella prova'   → container_shell  (è in /config)\n"
            "  utente: 'cancella ago/test.md'        → container_shell  (è in /config)\n"
            "  utente: 'mostra processi'             → host_bash        (info sistema)\n"
            "  utente: 'kill pid 1234'               → host_bash        (controllo sistema)\n\n"
            "Per QUALSIASI altro comando shell/sistema (non file utente) usa host_bash.\n"
            "host_bash esegue comandi bash sull'host HA reale — ha ip, ps, kill, df, ecc.\n\n"
            "CANALI:\n"
            "1. host_bash  comandi bash sull'host HA (ip/ps/kill/df/free/rete/log/qualsiasi shell SISTEMA)\n"
            "   args: {\"command\": \"bash command\"}\n"
            "   ESEMPI: ip server={command:ip addr show}  processi={command:ps aux|head -25}\n"
            "           kill pid={command:kill -9 PID}  ram={command:free -h}  disco={command:df -h}\n"
            "           porte={command:ss -tlnp}  log={command:journalctl -n 30 --no-pager}\n\n"
            "2. ping  test raggiungibilita host/IP\n"
            "   args: {\"host\": \"IP\", \"count\": 4}\n\n"
            "3. portscan  porte aperte su host\n"
            "   args: {\"host\": \"IP\", \"ports\": \"common|1-1024|22,80,443\"}\n\n"
            "4. host_info  info sistema via Supervisor (fallback se host_bash non disponibile)\n\n"
            "5. addons_list  lista addon HA installati\n\n"
            "6. addon_stats  stats cpu/ram addon\n"
            "   args: {\"slug\": \"slug\"}\n\n"
            "7. shell_command  shell_command HA utente\n"
            f"   disponibili: {sc_str}\n"
            "   args: {\"service\": \"nome\", \"data\": {}}\n\n"
            "8. ha_service  servizio HA generico\n"
            "   args: {\"domain\": \"...\", \"service\": \"...\", \"data\": {...}}\n\n"
            "9. container_shell  shell container HomeMind — USALO per TUTTI i file dell'utente in /config\n"
            "   args: {\"request\": \"NL request — passa la richiesta originale o un comando shell esplicito\"}\n"
            "   ESEMPI:\n"
            "     'elimina prova'                  → {request: 'rm -rf /config/prova'}\n"
            "     'cancella ago/test.md'           → {request: 'rm /config/ago/test.md'}\n"
            "     'lista file in ago'              → {request: 'ls -la /config/ago'}\n"
            "     'crea cartella progetti/foo'     → {request: 'mkdir -p /config/progetti/foo'}\n\n"
            "Rispondi SOLO JSON: {\"channel\": \"...\", \"args\": {...}, \"explanation\": \"\"}\n"
        )
        usr_prompt = f"Richiesta utente: {user_request}\n\nRispondi solo con JSON."

        ai_resp = await ai_cb(sys_prompt, usr_prompt, None)
        if not ai_resp:
            return {"success": False, "result": "AI non ha risposto"}

        # Parse JSON
        import json as _json, re as _re
        ai_resp = _re.sub(r"```(?:json)?\s*", "", ai_resp).replace("```", "").strip()
        try:
            decision = _json.loads(ai_resp)
        except _json.JSONDecodeError:
            # Cerca primo JSON balanced
            m = _re.search(r"\{.*\}", ai_resp, _re.DOTALL)
            if m:
                try:
                    decision = _json.loads(m.group(0))
                except Exception:
                    return {"success": False,
                            "result": f"AI risposta non JSON:\n{ai_resp[:500]}"}
            else:
                return {"success": False,
                        "result": f"AI risposta non parsabile:\n{ai_resp[:500]}"}

        channel = decision.get("channel", "")
        args = decision.get("args", {}) or {}
        explanation = decision.get("explanation", "")

        # Esegui canale
        if channel == "error":
            return {"success": False,
                    "channel": "error",
                    "result": f"⚠️ {explanation or 'Richiesta non realizzabile'}",
                    "raw": decision}

        if channel == "host_info":
            r = await self.host_resources()
            if not r.get("success"):
                return {"success": False, "channel": channel,
                        "result": r.get("message", "errore"),
                        "raw": r}
            return {"success": True, "channel": channel,
                    "result": HATerminal.format_resources(r["data"]),
                    "raw": r["data"]}

        if channel == "addons_list":
            r = await self.addons_list()
            if not r.get("success"):
                return {"success": False, "channel": channel,
                        "result": r.get("message", "errore")}
            return {"success": True, "channel": channel,
                    "result": HATerminal.format_addons(r["data"]),
                    "raw": r["data"]}

        if channel == "addon_stats":
            slug = args.get("slug", "")
            if not slug:
                return {"success": False, "channel": channel,
                        "result": "slug addon mancante"}
            r = await self.addon_stats(slug)
            if not r.get("success"):
                return {"success": False, "channel": channel,
                        "result": r.get("message", "errore")}
            data = r["data"]
            cpu = data.get("cpu_percent", 0)
            mem = data.get("memory_percent", 0)
            mem_use = data.get("memory_usage", 0) / (1024**2)
            return {"success": True, "channel": channel,
                    "result": (f"📊 <b>{slug}</b>\n"
                               f"  • CPU: <code>{cpu:.1f}%</code>\n"
                               f"  • RAM: <code>{mem:.1f}%</code> ({mem_use:.0f} MB)"),
                    "raw": data}

        if channel == "shell_command":
            service = args.get("service", "")
            data = args.get("data", {}) or {}
            if not service:
                return {"success": False, "channel": channel,
                        "result": "shell_command name mancante"}
            r = await self.call_shell_command(service, data)
            return {"success": r.get("success", False), "channel": channel,
                    "result": r.get("message", "errore") +
                              (f"\n<pre>{r.get('response','')[:1500]}</pre>"
                               if r.get("response") else ""),
                    "raw": r}

        if channel == "ping":
            host  = args.get("host", "") or args.get("ip", "")
            count = int(args.get("count", 4))
            import tools_system as _tools
            r = await _tools.tool_ping_python(host, count=min(count, 10))
            return {"success": r["success"], "channel": channel, "result": r["message"]}

        if channel == "portscan":
            host  = args.get("host", "") or args.get("ip", "")
            ports = args.get("ports", "common")
            import tools_system as _tools
            r = await _tools.tool_portscan_python(host, ports=str(ports))
            return {"success": r["success"], "channel": channel, "result": r["message"]}

        if channel == "host_bash":
            # Esegue comando bash sull'HOST reale HA via Supervisor API
            raw_cmd = args.get("command", "") or args.get("cmd", "")
            if not raw_cmd:
                return {"success": False, "result": "args: {command} richiesto"}
            # ── Intercetta comandi HA CLI e systemctl → usa Supervisor API ─
            _rc_stripped = raw_cmd.strip()
            _is_ha_cmd = (
                _rc_stripped.startswith("ha ") or
                _rc_stripped.startswith("hassio ") or
                _rc_stripped == "ha" or _rc_stripped == "hassio"
            )
            _is_systemctl = _rc_stripped.startswith("systemctl ")
            if _is_ha_cmd:
                # Usa Supervisor API invece di SSH
                r_ha = await self.ha_cli(_rc_stripped)
                return {**r_ha, "command": _rc_stripped}
            if _is_systemctl:
                # systemctl non esiste su HA OS — suggerisci alternativa
                sc_cmd = _rc_stripped.replace("systemctl ", "").strip()
                if "status" in sc_cmd and "hass" in sc_cmd.lower():
                    r_ha = await self.ha_cli("core info")
                    return {**r_ha, "command": _rc_stripped,
                            "note": "systemctl non disponibile su HA OS — usato ha core info"}
                elif "restart" in sc_cmd:
                    return {"success": False, "channel": "error",
                            "result": f"⚠️ systemctl non disponibile su HA OS.\n"
                                      f"Per riavviare usa:\n"
                                      f"• <code>/ssh cmd: ha core restart</code> — riavvia Home Assistant\n"
                                      f"• <code>/ssh cmd: ha supervisor restart</code> — riavvia Supervisor"}
                return {"success": False, "channel": "error",
                        "result": f"⚠️ systemctl non disponibile su HA OS.\n"
                                  f"Usa <code>/ssh cmd: ha &lt;comando&gt;</code> oppure\n"
                                  f"la Supervisor API via HomeMind."}
            r = await self.host_bash(raw_cmd, timeout=int(args.get("timeout", 30)))
            if r.get("fallback"):
                # /host/bash non supportato → usa container_shell come fallback
                from tools_system import tool_natural_shell as _tns2
                r2 = await _tns2(raw_cmd, ai_cb=ai_cb)
                out2 = (r2.get("stdout") or "").strip()
                return {
                    "success": r2.get("success", False),
                    "channel": "container_shell_fallback",
                    "result": (f"⚠️ host_bash non supportato — container output:\n"
                               f"<pre>{out2[:2000]}</pre>" if out2 else r.get("message", "")),
                }
            out = (r.get("stdout") or "").strip()
            err = (r.get("stderr") or "").strip()
            rc  = r.get("returncode", 0)
            result_parts = []
            if out:
                result_parts.append(f"<pre>{out[:3000]}</pre>")
            if err and rc != 0:
                result_parts.append(f"⚠️ STDERR:\n<pre>{err[:500]}</pre>")
            if not out and not err:
                result_parts.append("✅ Comando eseguito (nessun output)")
            return {
                "success": r.get("success", False),
                "channel": channel,
                "result": f"🖥️ HOST: <code>{raw_cmd}</code>\n" + "\n".join(result_parts),
            }

        if channel == "container_shell":
            # Esegue comando shell NL nel container HomeMind
            from tools_system import tool_natural_shell as _tns, tool_install_package as _tip, _INSTALLABLE_PACKAGES
            request = args.get("request", "")
            if not request:
                return {"success": False, "channel": channel,
                        "result": "request mancante"}
            r = await _tns(request, ai_cb=ai_cb)
            # Auto-install se manca pacchetto
            if r.get("package_missing") and r.get("install_suggestion"):
                pkg = r["install_suggestion"].replace("apk add ", "").strip().split()[0]
                if pkg in _INSTALLABLE_PACKAGES:
                    ir = await _tip(pkg)
                    if ir.get("success"):
                        r = await _tns(request, ai_cb=ai_cb)
            out = ""
            if r.get("stdout"):
                out += f"<pre>{r['stdout'][:3000]}</pre>"
            if not r.get("success") and r.get("stderr"):
                out += f"<pre>{r['stderr'][:1000]}</pre>"
            msg = r.get("message", "")
            cmd = r.get("command", "")
            return {
                "success": r.get("success", False),
                "channel": channel,
                "result": (f"💻 <code>{cmd}</code>\n{msg}\n{out}").strip(),
                "raw": r,
            }

        if channel == "ha_service":
            domain  = args.get("domain", "")
            service = args.get("service", "")
            data    = args.get("data", {}) or {}
            if not domain or not service:
                return {"success": False, "channel": channel,
                        "result": "domain/service mancanti"}
            # Chiamiamo via REST core (autenticato)
            token = self.ha_token or self.supervisor_token
            url = f"{CORE_URL}/api/services/{domain}/{service}"
            headers = {"Authorization": f"Bearer {token}",
                       "Content-Type": "application/json"}
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post(url, headers=headers, json=data,
                            timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        body = await resp.text()
                        if resp.status not in (200, 201):
                            return {"success": False, "channel": channel,
                                    "result": f"HTTP {resp.status}: {body[:300]}"}
                        return {"success": True, "channel": channel,
                                "result": f"✅ {domain}.{service} eseguito\n<pre>{body[:1000]}</pre>",
                                "raw": body}
            except Exception as e:
                return {"success": False, "channel": channel,
                        "result": f"Errore: {str(e)[:200]}"}

        return {"success": False, "channel": channel,
                "result": f"Canale sconosciuto: {channel}"}

    @staticmethod
    def format_resources(data: dict) -> str:
        """Formatta info host per Telegram."""
        lines = ["🖥️ <b>Sistema Home Assistant</b>\n"]

        # Host info
        host = data.get("host", {})
        if host:
            lines.append("📍 <b>Host</b>")
            for k in ("hostname", "operating_system", "kernel", "chassis"):
                if host.get(k):
                    lines.append(f"  • {k}: <code>{host[k]}</code>")
            lines.append("")

        # OS info
        os_info = data.get("os", {})
        if os_info:
            lines.append("💿 <b>Home Assistant OS</b>")
            for k in ("version", "version_latest", "board"):
                if os_info.get(k):
                    lines.append(f"  • {k}: <code>{os_info[k]}</code>")
            lines.append("")

        # Supervisor stats
        sup = data.get("supervisor", {})
        if sup:
            lines.append("🔧 <b>Supervisor</b>")
            cpu = sup.get("cpu_percent")
            mem_pct = sup.get("memory_percent")
            mem_use = sup.get("memory_usage")
            mem_lim = sup.get("memory_limit")
            net_rx = sup.get("network_rx")
            net_tx = sup.get("network_tx")
            if cpu is not None:
                lines.append(f"  • CPU: <code>{cpu:.1f}%</code>")
            if mem_pct is not None:
                lines.append(f"  • RAM: <code>{mem_pct:.1f}%</code>")
            if mem_use and mem_lim:
                lines.append(f"  • Memoria: <code>{mem_use/(1024**2):.0f}MB / {mem_lim/(1024**2):.0f}MB</code>")
            if net_rx is not None:
                lines.append(f"  • Net RX/TX: <code>{net_rx/(1024**2):.1f}MB / {net_tx/(1024**2):.1f}MB</code>")
            lines.append("")

        # Core stats
        core = data.get("core", {})
        if core:
            lines.append("⚙️ <b>Core (Home Assistant)</b>")
            cpu = core.get("cpu_percent")
            mem_pct = core.get("memory_percent")
            mem_use = core.get("memory_usage")
            if cpu is not None:
                lines.append(f"  • CPU: <code>{cpu:.1f}%</code>")
            if mem_pct is not None:
                lines.append(f"  • RAM: <code>{mem_pct:.1f}%</code>")
            if mem_use:
                lines.append(f"  • Memoria: <code>{mem_use/(1024**2):.0f}MB</code>")

        return "\n".join(lines)

    @staticmethod
    def format_addons(data) -> str:
        """Formatta lista addon."""
        if isinstance(data, dict) and "addons" in data:
            addons = data["addons"]
        else:
            addons = data if isinstance(data, list) else []
        if not addons:
            return "📦 Nessun addon installato"
        lines = [f"📦 <b>Addon installati ({len(addons)})</b>\n"]
        for a in addons[:30]:
            name = a.get("name", a.get("slug", "?"))
            ver = a.get("version", "")
            state = a.get("state", "")
            icon = "🟢" if state == "started" else "⚪"
            lines.append(f"  {icon} <b>{name}</b> <code>{ver}</code> "
                         f"<i>({state})</i>")
        return "\n".join(lines)
