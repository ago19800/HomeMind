"""
Tool System — comandi diretti tipo OpenClaw per HomeMind.

Permette all'AI o all'utente di eseguire operazioni filesystem e download
tramite comandi tool strutturati.

Tool disponibili:
- scrittura     → scrive un file
- lettura       → legge un file
- mkdir         → crea cartella
- ls            → elenca contenuto cartella
- delete        → elimina file/cartella (solo dentro /config)
- download      → scarica da URL
- github_clone  → clona repo github
- search_write  → fa ricerca AI e scrive risultato in file
- exec_safe     → esegue comando shell whitelistato

Tutti i path sono limitati a /config (security).
"""

import os
import re
import shutil
import asyncio
import logging
import urllib.parse
from pathlib import Path
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)

CONFIG_DIR = Path("/config")
# Path che non si possono modificare/eliminare per sicurezza
PROTECTED_PATHS = {
    "configuration.yaml",   # solo via config_file_manager con backup
    "secrets.yaml",
    ".storage",             # storage interno HA
    "home-assistant.log",
    "home-assistant_v2.db",
}


def _safe_path(relative_path: str, allow_outside_config: bool = False) -> Path:
    """Risolve path relativo a /config con security check.

    Normalizza i prefissi più comuni:
    - "/config/foo"   → /config/foo
    - "config/foo"    → /config/foo  (NEW: evita /config/config/foo)
    - "/foo"          → /config/foo
    - "foo"           → /config/foo

    Per accedere intenzionalmente a /config/config/foo (raro), usare il path
    assoluto completo "/config/config/foo".

    Raises: PermissionError se il path tenta di uscire da /config
    """
    if not relative_path or relative_path == ".":
        return CONFIG_DIR
    rp = relative_path
    # Strip prefissi: /config/, config/ (senza slash), o solo /.
    # IMPORTANTE: l'ordine conta. Prima il più specifico.
    if rp.startswith("/config/"):
        rp = rp[len("/config/"):]
    elif rp.startswith("config/"):
        # Senza questo branch, "config/automations.yaml" risolverebbe a
        # /config/config/automations.yaml — quasi sempre NON ciò che si vuole.
        rp = rp[len("config/"):]
    elif rp.startswith("/"):
        rp = rp[1:]

    target = (CONFIG_DIR / rp).resolve()
    if not allow_outside_config:
        if not str(target).startswith(str(CONFIG_DIR.resolve())):
            raise PermissionError(
                f"Accesso negato fuori da /config: {relative_path}"
            )
    return target


def _is_protected(target: Path) -> bool:
    """Verifica se il path è protetto."""
    rel = str(target.relative_to(CONFIG_DIR)) if target.is_relative_to(CONFIG_DIR) else str(target)
    for prot in PROTECTED_PATHS:
        if rel == prot or rel.startswith(prot + "/"):
            return True
    return False


# ══════════════════════════════════════════════════════════════════════
# TOOL: scrittura
# ══════════════════════════════════════════════════════════════════════

def tool_scrittura(path: str, content: str, overwrite: bool = True,
                    append: bool = False) -> dict:
    """Scrive contenuto in un file.

    Args:
        append: se True E il file esiste, aggiunge al fondo (con separatore)
                invece di sovrascrivere.
    """
    try:
        target = _safe_path(path)
        if _is_protected(target):
            return {"success": False,
                    "message": f"⚠️ File protetto, usa /modifica con AI: {path}"}
        target.parent.mkdir(parents=True, exist_ok=True)

        if append and target.exists():
            # Append mode: leggi esistente, aggiungi separatore + nuovo contenuto
            from datetime import datetime as _dt
            existing = target.read_text(encoding="utf-8", errors="replace")
            separator = f"\n\n---\n*Aggiunto il {_dt.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
            full = existing.rstrip() + separator + content
            target.write_text(full, encoding="utf-8")
            return {"success": True,
                    "message": f"➕ Aggiunto {len(content)} bytes a {path} (totale: {len(full)} bytes)",
                    "path": str(target.relative_to(CONFIG_DIR)),
                    "size": len(full),
                    "appended": True}

        if target.exists() and not overwrite:
            return {"success": False,
                    "message": f"❌ File esistente (overwrite=False): {path}"}
        target.write_text(content, encoding="utf-8")
        return {"success": True,
                "message": f"✅ Scritto {len(content)} bytes in {path}",
                "path": str(target.relative_to(CONFIG_DIR)),
                "size": len(content)}
    except PermissionError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.exception("tool_scrittura")
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: lettura
# ══════════════════════════════════════════════════════════════════════

def tool_lettura(path: str, max_chars: int = 30000) -> dict:
    """Legge contenuto di un file."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return {"success": False, "message": f"❌ File non trovato: {path}"}
        if not target.is_file():
            return {"success": False, "message": f"❌ Non è un file: {path}"}
        content = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > max_chars
        return {
            "success": True,
            "content": content[:max_chars],
            "truncated": truncated,
            "size": len(content),
            "path": str(target.relative_to(CONFIG_DIR)),
        }
    except PermissionError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: mkdir
# ══════════════════════════════════════════════════════════════════════

def tool_mkdir(path: str) -> dict:
    """Crea una cartella (e le parent) se non esiste."""
    try:
        target = _safe_path(path)
        if target.exists():
            if target.is_dir():
                return {"success": True,
                        "message": f"📁 Cartella già esistente: {path}"}
            return {"success": False,
                    "message": f"❌ Esiste un file con questo nome: {path}"}
        target.mkdir(parents=True, exist_ok=True)
        return {"success": True, "message": f"✅ Cartella creata: {path}",
                "path": str(target.relative_to(CONFIG_DIR))}
    except PermissionError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: ls
# ══════════════════════════════════════════════════════════════════════

def tool_ls(path: str = ".", show_hidden: bool = False, max_entries: int = 100) -> dict:
    """Elenca il contenuto di una cartella."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return {"success": False, "message": f"❌ Path non trovato: {path}"}
        if not target.is_dir():
            return {"success": False, "message": f"❌ Non è una cartella: {path}"}
        entries = []
        for p in sorted(target.iterdir()):
            if not show_hidden and p.name.startswith("."):
                continue
            try:
                size = p.stat().st_size if p.is_file() else 0
                entries.append({
                    "name": p.name,
                    "type": "dir" if p.is_dir() else "file",
                    "size": size,
                })
                if len(entries) >= max_entries:
                    break
            except Exception:
                continue
        return {"success": True, "entries": entries,
                "path": str(target.relative_to(CONFIG_DIR)),
                "count": len(entries)}
    except PermissionError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: delete
# ══════════════════════════════════════════════════════════════════════

def tool_delete(path: str) -> dict:
    """Elimina file o cartella (con check protezione)."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return {"success": False, "message": f"❌ Non trovato: {path}"}
        if _is_protected(target):
            return {"success": False, "message": f"⚠️ Path protetto: {path}"}
        if target == CONFIG_DIR:
            return {"success": False, "message": "⚠️ Non posso eliminare /config"}
        if target.is_dir():
            shutil.rmtree(target)
            return {"success": True, "message": f"🗑️ Cartella eliminata: {path}"}
        else:
            target.unlink()
            return {"success": True, "message": f"🗑️ File eliminato: {path}"}
    except PermissionError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: download (URL → file)
# ══════════════════════════════════════════════════════════════════════

async def tool_download(url: str, dest_path: str,
                         max_size_mb: int = 50) -> dict:
    """Scarica un URL in un file locale."""
    try:
        # Verifica URL valido
        if not (url.startswith("http://") or url.startswith("https://")):
            return {"success": False, "message": "URL deve iniziare con http(s)://"}
        target = _safe_path(dest_path)
        # Se dest_path è una cartella (o termina con /), deriva il nome file dall'URL
        if target.is_dir() or dest_path.endswith("/"):
            from urllib.parse import urlparse as _urlparse
            _fname = Path(_urlparse(url).path).name or "download"
            if not _fname or _fname == ".":
                _fname = "download"
            target = target / _fname
        if _is_protected(target):
            return {"success": False, "message": f"⚠️ Path protetto: {dest_path}"}
        target.parent.mkdir(parents=True, exist_ok=True)

        max_bytes = max_size_mb * 1024 * 1024
        timeout = aiohttp.ClientTimeout(total=120)

        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url) as r:
                if r.status != 200:
                    return {"success": False,
                            "message": f"HTTP {r.status} su {url}"}
                # Verifica content-length se presente
                cl = r.headers.get("content-length")
                if cl and int(cl) > max_bytes:
                    return {"success": False,
                            "message": f"File troppo grande (>{max_size_mb} MB)"}
                # Stream write con check size
                written = 0
                with open(target, "wb") as fh:
                    async for chunk in r.content.iter_chunked(8192):
                        written += len(chunk)
                        if written > max_bytes:
                            target.unlink(missing_ok=True)
                            return {"success": False,
                                    "message": f"Superato limite {max_size_mb} MB durante download"}
                        fh.write(chunk)
        return {"success": True,
                "message": f"⬇️ Scaricato {written/1024:.1f} KB in {dest_path}",
                "path": str(target.relative_to(CONFIG_DIR)),
                "size": written}
    except Exception as e:
        logger.exception("tool_download")
        return {"success": False, "message": f"Errore download: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: github_clone
# ══════════════════════════════════════════════════════════════════════

async def tool_github_clone(repo_url: str, dest_path: str,
                              branch: Optional[str] = None) -> dict:
    """Scarica un repository GitHub come ZIP e lo estrae (senza git installato).

    Funziona usando l'API GitHub per scaricare il .zip del branch principale,
    poi lo estrae con Python nativo (zipfile).

    Args:
        repo_url: URL GitHub (es. https://github.com/owner/repo)
        dest_path: cartella di destinazione dentro /config
        branch: branch da scaricare (default: main poi master)
    """
    import zipfile as _zf
    import io as _io

    try:
        target = _safe_path(dest_path)
        if _is_protected(target):
            return {"success": False, "message": f"⚠️ Path protetto: {dest_path}"}

        # Se la dest è una cartella esistente, crea sottocartella col nome repo
        from urllib.parse import urlparse as _up
        _path_parts = [p for p in _up(repo_url).path.strip("/").split("/") if p]
        owner = _path_parts[0] if len(_path_parts) > 0 else "unknown"
        repo  = _path_parts[1].replace(".git", "") if len(_path_parts) > 1 else "repo"

        if target.exists() and target.is_dir():
            target = target / repo
        if target.exists():
            return {"success": False,
                    "message": f"❌ Cartella già esistente: {dest_path}/{repo}\n"
                               f"Rinomina o elimina prima la cartella."}

        # ── Prima prova git clone (se git è installato nel container) ─────────
        import shutil as _sh
        if _sh.which("git"):
            branches_git = [branch] if branch else ["main", "master"]
            repo_url_norm = repo_url if repo_url.endswith(".git") else repo_url + ".git"
            for _br in branches_git:
                try:
                    _cmd = ["git", "clone", "--depth", "1", "--branch", _br,
                            repo_url_norm, str(target)]
                    _proc = await asyncio.create_subprocess_exec(
                        *_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _out, _err = await asyncio.wait_for(_proc.communicate(), timeout=60)
                    if _proc.returncode == 0:
                        rel_dest = str(target.relative_to(CONFIG_DIR))
                        return {
                            "success": True,
                            "message": (f"📦 <b>{owner}/{repo}</b> clonato via git (branch: {_br})\n"
                                        f"📁 In: <code>/config/{rel_dest}</code>"),
                            "path": rel_dest,
                            "branch": _br,
                        }
                except Exception as _ge:
                    logger.debug("git clone fallito per branch %s: %s", _br, _ge)
            # git ha fallito → continua con download ZIP
            logger.info("git clone fallito — uso download ZIP per %s/%s", owner, repo)

        # ── Fallback: scarica ZIP da GitHub senza git ─────────────────────────
        # Costruisci URL download ZIP — prova main poi master
        branches_to_try = [branch] if branch else ["main", "master", "HEAD"]
        zip_url = None
        zip_data = None
        used_branch = None

        timeout = aiohttp.ClientTimeout(total=60)
        headers = {"User-Agent": "HomeMind/1.0 (github-downloader)"}

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
            for br in branches_to_try:
                _zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{br}.zip"
                if br == "HEAD":
                    _zip_url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/main"
                try:
                    async with sess.get(_zip_url, allow_redirects=True) as resp:
                        if resp.status == 200:
                            ct = resp.headers.get("content-type", "")
                            data = await resp.read()
                            if len(data) > 100 and (b"PK" in data[:4] or "zip" in ct):
                                zip_data = data
                                used_branch = br
                                zip_url = _zip_url
                                break
                        elif resp.status == 404:
                            continue
                except Exception as _e:
                    logger.debug("branch %s failed: %s", br, _e)
                    continue

        if not zip_data:
            # Fallback: prova API GitHub zipball
            api_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
            try:
                async with aiohttp.ClientSession(timeout=timeout, headers=headers) as sess:
                    async with sess.get(api_url, allow_redirects=True) as resp:
                        if resp.status == 200:
                            zip_data = await resp.read()
                            used_branch = "default"
            except Exception as _e2:
                logger.debug("API zipball failed: %s", _e2)

        if not zip_data:
            return {"success": False,
                    "message": f"❌ Impossibile scaricare {owner}/{repo} da GitHub.\n"
                               f"Verifica che il repository esista e sia pubblico.\n"
                               f"URL tentato: https://github.com/{owner}/{repo}"}

        # Estrai ZIP in memoria → target dir
        target.mkdir(parents=True, exist_ok=True)
        extracted_files = []

        with _zf.ZipFile(_io.BytesIO(zip_data)) as zf:
            members = zf.namelist()
            # GitHub ZIP ha una cartella root tipo "repo-main/" — la saltiamo
            root_prefix = ""
            if members:
                first = members[0]
                if first.endswith("/"):
                    root_prefix = first  # es. "HomeMind-main/"

            for member in members:
                # Salta la cartella root
                rel = member[len(root_prefix):] if root_prefix and member.startswith(root_prefix) else member
                if not rel or rel == "/":
                    continue
                out_path = (target / rel).resolve()
                # Sicurezza path traversal
                if not str(out_path).startswith(str(target.resolve())):
                    continue
                if member.endswith("/"):
                    out_path.mkdir(parents=True, exist_ok=True)
                else:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(out_path, "wb") as dst:
                        dst.write(src.read())
                    extracted_files.append(rel)

        rel_dest = str(target.relative_to(CONFIG_DIR))
        n = len(extracted_files)
        preview = "\n".join(f"  📄 {f}" for f in extracted_files[:8])
        extra = f"\n  ... +{n-8} altri" if n > 8 else ""
        return {
            "success": True,
            "message": (f"📦 <b>{owner}/{repo}</b> scaricato (branch: {used_branch})\n"
                        f"📁 Estratto in: <code>/config/{rel_dest}</code>\n"
                        f"📊 {n} file estratti\n{preview}{extra}"),
            "path": rel_dest,
            "files": extracted_files,
            "branch": used_branch,
        }
    except Exception as e:
        logger.exception("tool_github_clone")
        return {"success": False, "message": f"Errore clone GitHub: {str(e)[:300]}"}


async def tool_ping_python(host: str, count: int = 4, timeout: float = 2.0) -> dict:
    """Ping tramite Python puro — funziona anche senza busybox ping."""
    import asyncio as _aio
    import socket as _sock
    import time as _time

    results = []
    success_count = 0
    try:
        # Risolvi hostname
        addr = _sock.gethostbyname(host)
    except _sock.gaierror as e:
        return {"success": False,
                "message": f"❌ Impossibile risolvere host: {host}\n{e}"}

    for i in range(count):
        t0 = _time.monotonic()
        try:
            # Tenta connessione TCP porta 80 come ping surrogato
            reader, writer = await _aio.wait_for(
                _aio.open_connection(addr, 80), timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            ms = ((_time.monotonic() - t0) * 1000)
            results.append(f"icmp_seq={i+1} ttl=64 time={ms:.1f} ms ✅")
            success_count += 1
        except (_aio.TimeoutError, ConnectionRefusedError):
            # ConnectionRefused = host risponde (porta chiusa ma host up)
            ms = ((_time.monotonic() - t0) * 1000)
            results.append(f"icmp_seq={i+1} host raggiungibile (porta 80 chiusa) time={ms:.1f} ms ✅")
            success_count += 1
        except OSError:
            results.append(f"icmp_seq={i+1} Request timeout ❌")
        await _aio.sleep(0.5)

    pct_loss = int(((count - success_count) / count) * 100)
    lines = "\n".join(results)
    summary = (f"--- {host} ({addr}) ping statistics ---\n"
               f"{count} packets, {success_count} reached, {pct_loss}% loss")
    return {
        "success": success_count > 0,
        "message": f"🌐 PING {host} ({addr}):\n{lines}\n{summary}",
        "host": host, "addr": addr,
        "success_count": success_count, "total": count,
    }


async def tool_portscan_python(host: str, ports: str = "1-1024",
                                timeout: float = 0.5, max_ports: int = 200) -> dict:
    """Scansiona porte aperte tramite Python asyncio — nessun nmap richiesto.

    Args:
        host:  IP o hostname
        ports: range "1-1024", lista "22,80,443", o "common"
        timeout: timeout per porta (secondi)
        max_ports: limite massimo porte scansionate
    """
    import asyncio as _aio
    import socket as _sock

    # Risolvi host
    try:
        addr = _sock.gethostbyname(host)
    except _sock.gaierror as e:
        return {"success": False, "message": f"❌ Host non risolvibile: {host}\n{e}"}

    # Parse porta list
    COMMON_PORTS = [21,22,23,25,53,80,110,143,443,445,
                    3306,3389,5000,5900,6379,8080,8443,8888,9000]
    if ports == "common":
        port_list = COMMON_PORTS
    elif "-" in ports:
        try:
            lo, hi = ports.split("-", 1)
            port_list = list(range(int(lo), min(int(hi)+1, int(lo)+max_ports)))
        except ValueError:
            port_list = COMMON_PORTS
    else:
        try:
            port_list = [int(p.strip()) for p in ports.split(",")][:max_ports]
        except ValueError:
            port_list = COMMON_PORTS

    open_ports = []
    CONCURRENCY = 50

    async def check_port(port: int):
        try:
            _, writer = await _aio.wait_for(
                _aio.open_connection(addr, port), timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            # Prova a identificare servizio
            try:
                svc = _sock.getservbyport(port, "tcp")
            except OSError:
                svc = "unknown"
            open_ports.append((port, svc))
        except Exception:
            pass

    # Scan in parallelo con semaforo
    sem = _aio.Semaphore(CONCURRENCY)

    async def guarded(port):
        async with sem:
            await check_port(port)

    await _aio.gather(*[guarded(p) for p in port_list])
    open_ports.sort()

    if not open_ports:
        msg = (f"🔍 Port scan {host} ({addr}) — {len(port_list)} porte scansionate\n"
               f"❌ Nessuna porta aperta trovata")
    else:
        lines = "\n".join(f"  🟢 {p:5d}/tcp  {s}" for p, s in open_ports)
        msg = (f"🔍 Port scan {host} ({addr}) — {len(port_list)} porte scansionate\n"
               f"Porte aperte ({len(open_ports)}):\n{lines}")

    return {
        "success": True,
        "message": msg,
        "host": host, "addr": addr,
        "open_ports": [{"port": p, "service": s} for p, s in open_ports],
    }


# ══════════════════════════════════════════════════════════════════════
# TOOL: search_web (per search_write)
# ══════════════════════════════════════════════════════════════════════

async def tool_search_web(query: str, max_results: int = 5) -> dict:
    """Ricerca web usando DuckDuckGo HTML (no API key richiesta).

    Fallback semplice: usa l'AI con il proprio sapere se la rete fallisce.
    """
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        timeout = aiohttp.ClientTimeout(total=15)
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; HomeMind) Gecko/20100101 Firefox/120.0",
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
            async with s.post(url, data=params) as r:
                if r.status != 200:
                    return {"success": False,
                            "message": f"DuckDuckGo HTTP {r.status}",
                            "results": []}
                html = await r.text()

        # Parse semplice via regex (no BeautifulSoup)
        results = []
        # Pattern per i risultati DuckDuckGo HTML
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
            r'.*?class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL
        )
        for m in pattern.finditer(html):
            link = m.group(1)
            title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            snippet = re.sub(r'<[^>]+>', '', m.group(3)).strip()
            # Decode URL DDG redirect
            if link.startswith("//duckduckgo.com/l/?uddg="):
                try:
                    qs = urllib.parse.parse_qs(link.split("?", 1)[1])
                    if "uddg" in qs:
                        link = urllib.parse.unquote(qs["uddg"][0])
                except Exception:
                    pass
            elif link.startswith("/l/?uddg="):
                try:
                    qs = urllib.parse.parse_qs(link.split("?", 1)[1])
                    if "uddg" in qs:
                        link = urllib.parse.unquote(qs["uddg"][0])
                except Exception:
                    pass
            results.append({"title": title, "url": link, "snippet": snippet})
            if len(results) >= max_results:
                break
        return {"success": True, "query": query, "results": results,
                "count": len(results)}
    except Exception as e:
        logger.warning("search_web error: %s", e)
        return {"success": False, "message": f"Errore: {str(e)[:200]}",
                "results": []}


# ══════════════════════════════════════════════════════════════════════
# Helper: format ls output
# ══════════════════════════════════════════════════════════════════════

async def tool_fetch_page(url: str, max_chars: int = 8000) -> dict:
    """Scarica una pagina web ed estrae solo testo leggibile.

    Usato dopo tool_search_web per estrarre il contenuto reale.
    """
    try:
        if not (url.startswith("http://") or url.startswith("https://")):
            return {"success": False, "message": "URL non valido", "text": ""}
        timeout = aiohttp.ClientTimeout(total=15)
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; HomeMind) Gecko/20100101 Firefox/120.0",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.5",
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
            async with s.get(url, allow_redirects=True) as r:
                if r.status != 200:
                    return {"success": False, "message": f"HTTP {r.status}", "text": ""}
                ctype = r.headers.get("content-type", "")
                if "html" not in ctype and "text" not in ctype:
                    return {"success": False, "message": f"Content-type non testuale: {ctype}", "text": ""}
                html = await r.text(errors="ignore")
        # Estrai testo leggibile via regex semplice (no BeautifulSoup)
        # 1. Rimuovi script e style
        html = re.sub(r'<script\b[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style\b[^>]*>.*?</style>',  ' ', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<noscript\b[^>]*>.*?</noscript>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        # 2. Strip tag mantenendo line breaks
        html = re.sub(r'<br\s*/?>',     '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</(p|div|h[1-6]|li|tr)\s*>', '\n', html, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', html)
        # 3. HTML entities
        import html as _h
        text = _h.unescape(text)
        # 4. Whitespace cleanup
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        text = text.strip()
        return {"success": True, "url": url, "text": text[:max_chars],
                "truncated": len(text) > max_chars, "size": len(text)}
    except Exception as e:
        logger.warning("fetch_page error: %s", e)
        return {"success": False, "message": f"Errore: {str(e)[:200]}", "text": ""}


def tool_append(path: str, content: str, separator: str = "\n\n---\n\n") -> dict:
    """Appende contenuto a un file esistente. Lo crea se non esiste.

    Garantisce sempre almeno un \n tra contenuto esistente e nuovo per evitare
    fusione di righe.
    """
    try:
        target = _safe_path(path)
        if _is_protected(target):
            return {"success": False,
                    "message": f"⚠️ File protetto: {path}"}
        target.parent.mkdir(parents=True, exist_ok=True)
        was_existing = target.exists()
        if was_existing:
            existing = target.read_text(encoding="utf-8", errors="replace")
            # Garantisci newline finale prima del separator
            existing = existing.rstrip() + "\n"
            new_content = existing + separator + content
        else:
            new_content = content
        # Garantisci newline finale
        if not new_content.endswith("\n"):
            new_content += "\n"
        target.write_text(new_content, encoding="utf-8")
        return {"success": True,
                "message": (f"✅ Appeso {len(content)} bytes a {path} "
                           f"(file ora {len(new_content)} bytes)"),
                "path": str(target.relative_to(CONFIG_DIR)),
                "size": len(new_content),
                "appended": was_existing,
                "was_existing": was_existing}
    except Exception as e:
        logger.exception("tool_append")
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: shell_exec (con memoria/learning)
# ══════════════════════════════════════════════════════════════════════

import json as _json
import shlex as _shlex

LEARNED_DB = Path("/config/homemind_patches/learned_commands.json")

# Whitelist comandi sicuri di sola lettura/info
_SAFE_COMMANDS = {
    # Info filesystem
    "ls", "find", "stat", "file", "du", "df", "tree", "pwd", "wc", "basename", "dirname",
    "realpath", "readlink",
    # Info testo
    "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "awk", "sed",
    "cut", "sort", "uniq", "diff", "tr", "xxd", "hexdump",
    # Info sistema
    "ps", "top", "free", "uptime", "whoami", "id", "uname", "date",
    "hostname", "lsof", "netstat", "ss", "env", "printenv", "which", "whereis",
    "type", "command",
    # Info rete (Alpine usa busybox per ping/traceroute)
    "ping", "ping6", "traceroute", "tracepath", "nslookup", "dig", "host",
    "curl", "wget", "ip", "ifconfig", "arp", "route", "nc", "ncat",
    "busybox",  # Alpine fallback
    # Compressione
    "tar", "zip", "unzip", "gzip", "gunzip", "bzip2", "bunzip2", "xz", "unxz", "7z",
    # Permessi (solo lettura/scrittura)
    "chmod", "chown", "chgrp", "umask", "getfacl", "setfacl",
    # Filesystem ops
    "cp", "mv", "rm", "mkdir", "rmdir", "ln", "touch", "rename",
    # Hash/checksum
    "md5sum", "sha1sum", "sha256sum", "sha512sum", "cksum",
    # Test
    "echo", "true", "false", "test", "[",
    # Editor batch (non interattivo)
    "tac", "rev", "fold", "fmt",
    # Python nativo — per zip, operazioni senza binari
    "python3", "python",
    # Package mgmt (READ-ONLY: list/search/info — install richiede flag esplicito)
    "apk", "dpkg", "dpkg-query", "rpm", "pip", "pip3",
    # Git read-only
    "git",
    # Misc
    "yes", "seq", "tee", "xargs",
}

# Comandi PROIBITI (anche se whitelist sopra li lascia)
# Whitelist pacchetti installabili via apk add (Alpine)
_INSTALLABLE_PACKAGES = {
    "iputils-ping", "iputils", "traceroute", "bind-tools", "iproute2",
    "net-tools", "netcat-openbsd", "nmap-ncat", "tree", "zip", "unzip",
    "p7zip", "xz", "rsync", "jq", "git", "curl", "wget", "openssh-client",
    "openssl", "ca-certificates", "tcpdump", "mtr", "lsof",
}


async def tool_install_package(package: str) -> dict:
    """Installa un pacchetto Alpine via apk se è in whitelist."""
    pkg = package.strip().split()[0]
    if pkg not in _INSTALLABLE_PACKAGES:
        return {"success": False,
                "message": f"⚠️ Pacchetto non in whitelist: <code>{pkg}</code>\n"
                           f"Pacchetti permessi: {', '.join(sorted(_INSTALLABLE_PACKAGES))}"}
    cmd = f"apk add --no-cache {pkg}"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=120)
        rc = proc.returncode
        return {
            "success": rc == 0,
            "message": (f"✅ Pacchetto <code>{pkg}</code> installato"
                        if rc == 0
                        else f"⚠️ Installazione fallita (rc={rc})"),
            "command": cmd,
            "stdout":  out.decode("utf-8", errors="replace")[:2000],
            "stderr":  err.decode("utf-8", errors="replace")[:2000],
            "package": pkg,
        }
    except asyncio.TimeoutError:
        return {"success": False, "message": f"⚠️ Timeout installazione {pkg}"}
    except Exception as e:
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


_BLOCKED_PATTERNS = [
    # Eliminazione distruttiva
    r"\brm\s+(-rf?|-r|-f)\s+/",      # rm -rf /qualsiasi/path assoluto
    r"\brm\s+(-rf?|-r|-f)\s+~",      # rm -rf ~/...
    r"\brm\s+(-rf?|-r)\s+\.",       # rm -r ./* o ./dir
    r"\brm\s+(-rf?|-r|-f)?\s+/config/(ago|homemind_patches|automations|configuration)",  # path critici
    # Device/sistema
    r"\b/etc/shadow\b",
    r"\b/etc/passwd\b",
    r"\bdd\s+of=",
    r":\s*\(\s*\)\s*\{",          # fork bomb
    r">/dev/sd[a-z]",
    r"\bmkfs\b",
    r"\bfdisk\b",
    r"\bparted\b",
    # Sovrascrittura file di sistema
    r">/etc/",
    r"\btruncate\b.*(/config|/etc|/app)",
    # Catena pericolosa con backtick o $()
    r"`rm\b",
    r"\$\(rm\b",
]

# Pattern che richiedono CONFERMA prima di eseguire (non blocco totale)
_CONFIRM_PATTERNS = [
    r"\brm\s+[^-]",               # rm semplice (senza -rf) su file singolo
    r"\bchmod\s+[0-7]{3,4}",      # chmod
    r"\bchown\b",
    r"\bmv\b.*(/config/|ago/)",   # spostamento in cartelle importanti
]


def _load_learned() -> dict:
    """Carica i comandi memorizzati."""
    try:
        if LEARNED_DB.exists():
            return _json.loads(LEARNED_DB.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_learned(db: dict):
    """Salva i comandi memorizzati."""
    try:
        LEARNED_DB.parent.mkdir(parents=True, exist_ok=True)
        LEARNED_DB.write_text(_json.dumps(db, indent=2, ensure_ascii=False),
                               encoding="utf-8")
    except Exception as e:
        logger.warning("save_learned failed: %s", e)


def lookup_learned_command(intent: str) -> Optional[str]:
    """Cerca un comando già imparato per un intent.
    
    Usa solo match esatto o quasi-esatto (≥80% parole in comune).
    Il match parziale generico causava riuso di comandi sbagliati
    (es. "elenca config" → usava "ls -la /config/ssl" appreso prima).
    """
    db = _load_learned()
    intent_norm = intent.lower().strip()
    # 1. Match esatto
    if intent_norm in db:
        return db[intent_norm].get("command")
    # 2. Match per parole chiave: almeno 80% delle parole dell'intent
    #    devono trovarsi nella chiave del DB (non viceversa)
    intent_words = set(w for w in intent_norm.split() if len(w) > 3)
    if not intent_words:
        return None
    best_cmd = None
    best_score = 0.0
    for k, v in db.items():
        k_words = set(w for w in k.split() if len(w) > 3)
        if not k_words:
            continue
        # Quante parole dell'intent sono nella chiave
        common = intent_words & k_words
        score = len(common) / len(intent_words)
        if score > best_score and score >= 0.8:
            best_score = score
            best_cmd = v.get("command")
    return best_cmd


def remember_command(intent: str, command: str, success: bool = True):
    """Memorizza un comando per riuso futuro."""
    db = _load_learned()
    intent_norm = intent.lower().strip()
    if success:
        db[intent_norm] = {
            "command":   command,
            "last_used": _json.dumps(None),  # placeholder
        }
        _save_learned(db)
        logger.info("Comando memorizzato: %s → %s", intent_norm, command)


def _is_command_safe(command: str) -> tuple:
    """Verifica se un comando shell è sicuro.

    Returns: (safe: bool, reason: str)
    """
    import re as _re
    # Pattern bloccati
    for pat in _BLOCKED_PATTERNS:
        if _re.search(pat, command):
            return False, f"Pattern proibito: {pat}"
    # Estrai primo token (eseguibile)
    try:
        tokens = _shlex.split(command)
    except ValueError:
        return False, "Comando malformato (quote sbilanciate)"
    if not tokens:
        return False, "Comando vuoto"
    # Gestisci pipe / redirect: spezza per ;|&
    parts = _re.split(r"[;|&]", command)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        try:
            ts = _shlex.split(p)
        except ValueError:
            return False, f"Sotto-comando malformato: {p[:50]}"
        if not ts:
            continue
        binary = ts[0].split("/")[-1]  # es. /usr/bin/ls → ls
        if binary not in _SAFE_COMMANDS:
            return False, f"Comando non in whitelist: {binary}"
    return True, "OK"


async def tool_shell_exec(command: str, cwd: str = "/config",
                           intent: str = "", timeout: int = 30) -> dict:
    """Esegue un comando shell sicuro.

    Args:
        command: comando da eseguire
        cwd: working directory (default /config)
        intent: descrizione del task (per memorizzazione)
        timeout: timeout secondi
    """
    # Check sicurezza
    safe, reason = _is_command_safe(command)
    if not safe:
        return {"success": False,
                "message": f"⚠️ Comando rifiutato: {reason}",
                "command": command}

    # Limit cwd a /config
    try:
        cwd_p = _safe_path(cwd) if cwd != "/config" else CONFIG_DIR
    except PermissionError as e:
        return {"success": False, "message": str(e)}

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(cwd_p),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False,
                    "message": f"⚠️ Timeout dopo {timeout}s", "command": command}

        out = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace")
        rc = proc.returncode
        success = (rc == 0)

        # Memorizza se intent fornito + successo
        if intent and success:
            remember_command(intent, command, success=True)

        result = {
            "success":  success,
            "command":  command,
            "rc":       rc,
            "stdout":   out[:8000],
            "stderr":   err[:2000],
            "message":  f"{'✅' if success else '⚠️'} comando {('OK' if success else f'fallito (rc={rc})')}",
        }
        return result
    except Exception as e:
        return {"success": False,
                "message": f"Errore esecuzione: {str(e)[:200]}",
                "command": command}


async def tool_natural_shell(natural_request: str, ai_cb=None) -> dict:
    """Esegui un comando shell partendo da richiesta in linguaggio naturale.

    1. Cerca prima nei comandi memorizzati (match parziale)
    2. Se non trova, chiede all\'AI di generare il comando
    3. Esegue
    4. Se fallisce per "command not found" suggerisce installazione
    5. Memorizza per riuso futuro

    Args:
        natural_request: testo NL ("dammi i permessi di /ago/test")
        ai_cb: callback per chiamare l\'AI

    Returns:
        {success, message, command, stdout, stderr, suggestion?}
    """
    # 1. Lookup memoria
    learned = lookup_learned_command(natural_request)
    if learned:
        logger.info("Riuso comando appreso: %s → %s", natural_request[:60], learned)
        result = await tool_shell_exec(learned, intent=natural_request, timeout=30)
        result["from_memory"] = True
        result["natural_request"] = natural_request
        return result

    # 2. AI genera comando
    if not ai_cb:
        return {
            "success": False,
            "message": "AI non disponibile — usa /shell <comando> diretto",
            "natural_request": natural_request,
        }

    # ── Intercetta richieste di estrazione archivi → usa Python nativo ──────
    _nl = natural_request.lower()
    _is_zip = any(k in _nl for k in ["estrai", "extract", "decomprimi", "unzip",
                                      "scompatta", ".zip", "zip -d"])
    _is_tar = any(k in _nl for k in ["tar.gz", ".tgz", ".tar.bz2", "tar xz"])
    if _is_zip or _is_tar:
        import re as _re2
        path_m = _re2.search(
            r"(?:/config/|ago/|config/)[\w./ \-]+\.(?:zip|tar\.gz|tgz|tar\.bz2|tar)",
            natural_request, _re2.IGNORECASE)
        if path_m:
            archive = path_m.group(0)
            dest_m = _re2.search(r"(?:in|nella cartella|dest[a-z]*|cartella)\s+([/\w.\-]+)",
                                  natural_request, _re2.IGNORECASE)
            dest = dest_m.group(1) if dest_m else ""
            if _is_tar or archive.endswith((".tar.gz", ".tgz", ".tar.bz2")):
                return tool_extract_tar_python(archive, dest)
            else:
                return tool_unzip_python(archive, dest)

    # ── Intercetta ping → usa Python socket (busybox ping non disponibile) ──
    import re as _re_net
    _ping_m = _re_net.search(
        r"ping\s+([\w.\-]+)|fai\s+ping\s+(?:a\s+|su\s+)?([\w.\-]+)",
        _nl)
    if _ping_m:
        _host = (_ping_m.group(1) or _ping_m.group(2) or "").strip()
        _count_m = _re_net.search(r"(\d+)\s+volt[ei]|count[=\s]+(\d+)", _nl)
        _count = int(_count_m.group(1) or _count_m.group(2)) if _count_m else 4
        if _host:
            return await tool_ping_python(_host, count=min(_count, 10))

    # ── Intercetta port scan → usa Python asyncio ────────────────────────────
    _scan_kw = ["scansiona port", "scan port", "porte aperte", "port scan",
                "nmap", "open port", "check port"]
    if any(k in _nl for k in _scan_kw):
        _ip_m = _re_net.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", natural_request)
        _host_m = _re_net.search(r"su\s+([\w.\-]+)|(?:host|ip)\s+([\w.\-]+)", _nl)
        _target = ""
        if _ip_m:
            _target = _ip_m.group(1)
        elif _host_m:
            _target = (_host_m.group(1) or _host_m.group(2) or "").strip()
        _ports = "common"
        _range_m = _re_net.search(r"(\d+)\s*[-–]\s*(\d+)", natural_request)
        _port_list_m = _re_net.search(r"port[ie]?\s+([\d,\s]+)", _nl)
        if _range_m:
            _ports = f"{_range_m.group(1)}-{_range_m.group(2)}"
        elif _port_list_m:
            _ports = _port_list_m.group(1).replace(" ", "")
        if _target:
            return await tool_portscan_python(_target, ports=_ports)

    sys_prompt = (
        "Sei un esperto Linux/Alpine. L\'utente è in un container Home Assistant "
        "Docker basato su Alpine Linux con busybox. Il container ha disponibili "
        "questi comandi (whitelist sicura):\n"
        f"{', '.join(sorted(_SAFE_COMMANDS))}\n\n"
        "Genera UN UNICO comando shell che soddisfa la richiesta dell\'utente.\n\n"
        "REGOLE STRETTE:\n"
        "1. Rispondi SOLO col comando, una riga, niente spiegazioni, niente backtick.\n"
        "2. Path relativi a /config (es. /config/ago/file.txt).\n"
        "3. Niente sudo (siamo già root nel container).\n"
        "4. Per ping in Alpine usa: ping -c 3 IP (busybox supporta -c).\n"
        "5. Se la richiesta è ambigua o pericolosa, rispondi: ERRORE: <motivo>\n"
        "6. Per chmod/chown ricorsivi usa -R; per ricorsione default mostra struttura.\n"
        "11. ⚠️ SICUREZZA ASSOLUTA: NON generare MAI rm, rmdir, truncate, mv, chmod su /config.\n"
        "    Per 'mostra/elenca/contenuto/lista' → usa SEMPRE: ls -la /config/PATH\n"
        "    Per 'apri/leggi/visualizza FILE' → usa SEMPRE: cat /config/PATH/FILE\n"
        "    Se non capisci la richiesta → rispondi: ERRORE: richiesta ambigua\n"
        "7. Per .tar.gz: tar czf FILE.tar.gz CARTELLA\n"
        "8. Per .zip: usa python3 -c \"import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])\" ZIP DEST\n"
        "9. NON usare unzip/7z — non disponibili. Per zip usa python3 zipfile.\n"
        "10. top non e interattivo: usa ps aux | head -25\n"
    )
    user_prompt = f"Richiesta: {natural_request}\n\nGenera SOLO il comando shell:"

    ai_command = await ai_cb(sys_prompt, user_prompt, None)
    if not ai_command:
        return {"success": False,
                "message": "AI non ha risposto",
                "natural_request": natural_request}

    # Pulisci risposta AI (rimuovi backtick, prefissi $, fence)
    ai_command = ai_command.strip()
    ai_command = re.sub(r"^```[a-z]*\n?", "", ai_command)
    ai_command = re.sub(r"\n?```\s*$", "", ai_command)
    ai_command = ai_command.strip().strip("`").strip()
    if ai_command.startswith("$ "):
        ai_command = ai_command[2:]
    # Una sola riga
    ai_command = ai_command.split("\n")[0].strip()

    if ai_command.startswith("ERRORE"):
        return {"success": False,
                "message": f"⚠️ {ai_command}",
                "natural_request": natural_request}

    if not ai_command:
        return {"success": False,
                "message": "AI ha generato un comando vuoto",
                "natural_request": natural_request}

    # 3. Controllo sicurezza PRIMA di eseguire
    import re as _re_sec
    for _pat in _BLOCKED_PATTERNS:
        if _re_sec.search(_pat, ai_command, _re_sec.IGNORECASE):
            logger.warning("BLOCKED comando pericoloso: %s (pattern: %s)", ai_command, _pat)
            return {
                "success": False,
                "message": (
                    f"⛔ <b>Comando bloccato per sicurezza</b>\n\n"
                    f"<code>{ai_command}</code>\n\n"
                    f"<i>Questo comando potrebbe causare danni irreversibili.\n"
                    f"Se sei sicuro, usa <code>/ssh cmd: {ai_command}</code> per eseguirlo direttamente.</i>"
                ),
                "natural_request": natural_request,
                "blocked": True,
                "command": ai_command,
            }

    # 4. Esegui
    result = await tool_shell_exec(ai_command, intent=natural_request, timeout=30)
    result["natural_request"] = natural_request
    result["ai_generated"] = True
    result["command"] = ai_command

    # 4. Diagnostica errore "not found"
    if not result.get("success"):
        stderr = result.get("stderr", "") or ""
        # Pattern Alpine/Linux: "ping: not found", "/bin/sh: ping: not found"
        m = re.search(r"(?:^|/)(\w+):\s+(?:not found|command not found)", stderr)
        if m:
            missing = m.group(1)
            # Mappatura nomi pacchetto comuni
            pkg_hints = {
                "ping":       "iputils  (apk add iputils-ping)",
                "traceroute": "traceroute  (apk add traceroute)",
                "nslookup":   "bind-tools  (apk add bind-tools)",
                "dig":        "bind-tools  (apk add bind-tools)",
                "host":       "bind-tools  (apk add bind-tools)",
                "ip":         "iproute2  (apk add iproute2)",
                "ifconfig":   "net-tools  (apk add net-tools)",
                "arp":        "net-tools  (apk add net-tools)",
                "route":      "net-tools  (apk add net-tools)",
                "nc":         "netcat-openbsd  (apk add netcat-openbsd)",
                "ncat":       "nmap-ncat  (apk add nmap-ncat)",
                "git":        "git  (apk add git)",
                "tree":       "tree  (apk add tree)",
                "zip":        "zip  (apk add zip)",
                "unzip":      "unzip  (apk add unzip)",
                "7z":         "p7zip  (apk add p7zip)",
                "xz":         "xz  (apk add xz)",
                "rsync":      "rsync  (apk add rsync)",
                "jq":         "jq  (apk add jq)",
            }
            hint = pkg_hints.get(missing, f"{missing}  (cerca su Alpine package: apk search {missing})")
            result["package_missing"] = missing
            result["install_suggestion"] = f"apk add {pkg_hints.get(missing, missing).split()[0]}"
            result["message"] = (
                f"⚠️ Comando non trovato: <code>{missing}</code>\n"
                f"📦 <b>Pacchetto necessario:</b> {hint}\n\n"
                f"<i>Posso installarlo? Rispondi con il bottone qui sotto.</i>"
            )
            # Anche la fallback: prova alternative built-in busybox
            ALT = {
                "ping":     "busybox ping",
                "tracepath":"busybox tracepath",
                "ip":       "busybox ip",
                "nc":       "busybox nc",
            }
            if missing in ALT:
                alt_cmd = ALT[missing] + ai_command[len(missing):]
                logger.info("Provo alternativa busybox: %s", alt_cmd)
                alt_result = await tool_shell_exec(alt_cmd, intent=natural_request, timeout=30)
                if alt_result.get("success"):
                    alt_result["natural_request"] = natural_request
                    alt_result["alternative_used"] = alt_cmd
                    return alt_result

    return result


def list_learned_commands(limit: int = 30) -> list:
    """Elenca i comandi memorizzati."""
    db = _load_learned()
    items = list(db.items())[:limit]
    return [{"intent": k, "command": v.get("command", "")} for k, v in items]



# ══════════════════════════════════════════════════════════════════════
# TOOL: tool_unzip_python — estrae .zip con Python nativo (nessun unzip)
# ══════════════════════════════════════════════════════════════════════

def tool_unzip_python(archive: str, dest: str = "") -> dict:
    """Estrae un file .zip con Python nativo — nessuna dipendenza esterna.

    Args:
        archive: path del file .zip (relativo a /config o assoluto)
        dest: cartella destinazione. Se vuota, usa la stessa cartella dell'archivio.
    """
    import zipfile as _zf
    try:
        src = _safe_path(archive)
        if not src.exists():
            return {"success": False, "message": f"❌ File non trovato: {archive}"}
        if not src.suffix.lower() == ".zip":
            return {"success": False, "message": f"❌ Non è un file .zip: {archive}"}

        if dest:
            dst = _safe_path(dest)
        else:
            dst = src.parent / src.stem  # cartella col nome dell'archivio senza .zip

        dst.mkdir(parents=True, exist_ok=True)

        extracted = []
        with _zf.ZipFile(src, "r") as zf:
            # Sicurezza: no path traversal
            for member in zf.namelist():
                member_path = (dst / member).resolve()
                if not str(member_path).startswith(str(dst.resolve())):
                    continue  # skip path traversal attempts
            zf.extractall(dst)
            extracted = zf.namelist()

        preview = ", ".join(extracted[:10])
        extra = f" (+{len(extracted)-10} altri)" if len(extracted) > 10 else ""
        return {
            "success": True,
            "message": (f"📦 Estratti {len(extracted)} file in {dest or str(dst.relative_to(CONFIG_DIR))}\n"
                        f"File: {preview}{extra}"),
            "dest": str(dst.relative_to(CONFIG_DIR)),
            "files": extracted,
        }
    except Exception as e:
        logger.exception("tool_unzip_python")
        return {"success": False, "message": f"Errore estrazione zip: {str(e)[:300]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: tool_extract_tar_python — estrae .tar.gz/.tgz/.tar.bz2 con Python
# ══════════════════════════════════════════════════════════════════════

def tool_extract_tar_python(archive: str, dest: str = "") -> dict:
    """Estrae un file .tar.gz / .tgz / .tar.bz2 con Python nativo.

    Args:
        archive: path del file tar (relativo a /config o assoluto)
        dest: cartella destinazione. Se vuota, usa la stessa cartella dell'archivio.
    """
    import tarfile as _tf
    try:
        src = _safe_path(archive)
        if not src.exists():
            return {"success": False, "message": f"❌ File non trovato: {archive}"}
        if not _tf.is_tarfile(str(src)):
            return {"success": False, "message": f"❌ Non è un file tar valido: {archive}"}

        stem = src.name
        for ext in (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar"):
            if stem.lower().endswith(ext):
                stem = stem[:-len(ext)]
                break

        if dest:
            dst = _safe_path(dest)
        else:
            dst = src.parent / stem

        dst.mkdir(parents=True, exist_ok=True)

        extracted = []
        with _tf.open(str(src), "r:*") as tf:
            # Sicurezza: no path traversal
            safe_members = []
            for m in tf.getmembers():
                m_path = (dst / m.name).resolve()
                if str(m_path).startswith(str(dst.resolve())):
                    safe_members.append(m)
                    extracted.append(m.name)
            tf.extractall(dst, members=safe_members)

        preview = ", ".join(extracted[:10])
        extra = f" (+{len(extracted)-10} altri)" if len(extracted) > 10 else ""
        return {
            "success": True,
            "message": (f"📦 Estratti {len(extracted)} file in {dest or str(dst.relative_to(CONFIG_DIR))}\n"
                        f"File: {preview}{extra}"),
            "dest": str(dst.relative_to(CONFIG_DIR)),
            "files": extracted,
        }
    except Exception as e:
        logger.exception("tool_extract_tar_python")
        return {"success": False, "message": f"Errore estrazione tar: {str(e)[:300]}"}



# ══════════════════════════════════════════════════════════════════════
# TOOL: tool_file_info — info su file/cartella (dimensione, data, tipo)
# ══════════════════════════════════════════════════════════════════════


def tool_create_tar_python(source: str, output: str = "") -> dict:
    """Crea un archivio .tar.gz da un file o cartella con Python nativo.

    Args:
        source: path da archiviare (relativo a /config o assoluto)
        output: path del file .tar.gz di output. Se vuoto, usa <source>.tar.gz
    """
    import tarfile as _tf
    try:
        src = _safe_path(source)
        if not src.exists():
            return {"success": False, "message": f"❌ Sorgente non trovata: {source}"}

        if output:
            dst = _safe_path(output)
        else:
            # Aggiungi .tar.gz accanto alla sorgente
            dst = src.parent / (src.name + ".tar.gz")

        dst.parent.mkdir(parents=True, exist_ok=True)

        with _tf.open(str(dst), "w:gz") as tf:
            # arcname=src.name così nel tar i path partono dal nome della cartella/file
            tf.add(str(src), arcname=src.name)

        size_mb = dst.stat().st_size / (1024 * 1024)
        rel_out = str(dst).replace("/config/", "", 1)
        return {
            "success": True,
            "message": f"✅ Archivio creato: {rel_out} ({size_mb:.1f} MB)",
            "path": rel_out,
            "size_bytes": dst.stat().st_size,
        }
    except Exception as e:
        return {"success": False, "message": f"❌ Errore creazione tar: {str(e)[:200]}"}


def tool_file_info(path: str) -> dict:
    """Ritorna info dettagliate su un file o cartella: dimensione, data modifica, tipo, permessi."""
    import datetime as _dt
    try:
        target = _safe_path(path)
        if not target.exists():
            return {"success": False, "message": f"❌ Non trovato: {path}"}
        stat = target.stat()
        size = stat.st_size
        mtime = _dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        kind = "📁 Cartella" if target.is_dir() else "📄 File"
        ext = target.suffix.lower() if target.is_file() else ""
        if target.is_dir():
            items = list(target.iterdir())
            n_files = sum(1 for i in items if i.is_file())
            n_dirs  = sum(1 for i in items if i.is_dir())
            size_str = f"{n_files} file, {n_dirs} cartelle"
        else:
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024**2:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size/1024**2:.1f} MB"
        perms = oct(stat.st_mode)[-3:]
        msg = (f"{kind}: <code>{path}</code>\n"
               f"📏 Dimensione: {size_str}\n"
               f"🕐 Modificato: {mtime}\n"
               f"🔐 Permessi: {perms}"
               + (f"\n📎 Tipo: {ext}" if ext else ""))
        return {"success": True, "message": msg,
                "size": size, "mtime": mtime, "kind": kind, "ext": ext}
    except Exception as e:
        logger.exception("tool_file_info")
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: tool_find_files — cerca file per nome/estensione/contenuto
# ══════════════════════════════════════════════════════════════════════

def tool_find_files(pattern: str, path: str = ".", content_search: str = "",
                    max_results: int = 30) -> dict:
    """Cerca file per nome (glob) o contenuto testuale.

    Args:
        pattern: pattern glob es. "*.yaml", "*.md", "classifica*"
        path: cartella radice di ricerca (relativa a /config)
        content_search: se specificato, cerca anche dentro i file (grep)
        max_results: limite risultati
    """
    import fnmatch as _fn
    try:
        base = _safe_path(path)
        if not base.exists():
            return {"success": False, "message": f"❌ Cartella non trovata: {path}"}
        found = []
        for fp in sorted(base.rglob("*")):
            if not fp.is_file():
                continue
            if _fn.fnmatch(fp.name.lower(), pattern.lower()) or _fn.fnmatch(fp.name, pattern):
                if content_search:
                    try:
                        txt = fp.read_text(encoding="utf-8", errors="ignore")
                        if content_search.lower() not in txt.lower():
                            continue
                    except Exception:
                        continue
                rel = str(fp.relative_to(CONFIG_DIR))
                size = fp.stat().st_size
                found.append((rel, size))
            if len(found) >= max_results:
                break
        if not found:
            q = f" contenente '{content_search}'" if content_search else ""
            return {"success": True, "message": f"🔍 Nessun file trovato con pattern <code>{pattern}</code>{q} in {path}",
                    "files": []}
        lines = [f"🔍 <b>{len(found)} file trovati</b> (pattern: <code>{pattern}</code>)\n"]
        for rel, sz in found:
            sz_s = f"{sz}B" if sz < 1024 else f"{sz//1024}KB"
            lines.append(f"  📄 <code>{rel}</code> ({sz_s})")
        return {"success": True, "message": "\n".join(lines), "files": [f for f, _ in found]}
    except Exception as e:
        logger.exception("tool_find_files")
        return {"success": False, "message": f"Errore ricerca: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: tool_json_read — legge e formatta un file JSON/YAML
# ══════════════════════════════════════════════════════════════════════

def tool_json_read(path: str, key_path: str = "") -> dict:
    """Legge un file JSON o YAML e lo formatta leggibilmente.

    Args:
        path: path del file (relativo a /config)
        key_path: percorso chiave opzionale es. "sensor[0].name" o "homeassistant.customize"
    """
    import json as _json, yaml as _yaml
    try:
        target = _safe_path(path)
        if not target.exists():
            return {"success": False, "message": f"❌ File non trovato: {path}"}
        raw = target.read_text(encoding="utf-8", errors="replace")
        ext = target.suffix.lower()
        try:
            if ext in (".yaml", ".yml"):
                data = _yaml.safe_load(raw)
            else:
                data = _json.loads(raw)
        except Exception as parse_err:
            return {"success": False, "message": f"❌ Errore parsing: {parse_err}"}
        # Navigate key_path
        if key_path:
            import re as _re2
            keys = _re2.split(r'[\.\[\]]', key_path)
            for k in keys:
                if not k:
                    continue
                try:
                    k_int = int(k)
                    data = data[k_int]
                except (ValueError, TypeError):
                    data = data[k]
        pretty = _json.dumps(data, indent=2, ensure_ascii=False, default=str)
        preview = pretty[:3000] + ("\n..." if len(pretty) > 3000 else "")
        return {"success": True,
                "message": f"📋 <code>{path}</code>\n\n<pre>{preview}</pre>",
                "data": data}
    except Exception as e:
        logger.exception("tool_json_read")
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: tool_replace_in_file — trova e sostituisce testo in un file
# ══════════════════════════════════════════════════════════════════════

def tool_replace_in_file(path: str, old_text: str, new_text: str,
                          count: int = 1) -> dict:
    """Trova e sostituisce testo in un file (backup automatico).

    Args:
        path: path file (relativo a /config)
        old_text: testo da trovare
        new_text: testo sostitutivo
        count: quante occorrenze sostituire (0 = tutte)
    """
    try:
        target = _safe_path(path)
        if _is_protected(target):
            return {"success": False, "message": f"⚠️ File protetto: {path}"}
        if not target.exists():
            return {"success": False, "message": f"❌ File non trovato: {path}"}
        original = target.read_text(encoding="utf-8", errors="replace")
        n_found = original.count(old_text)
        if n_found == 0:
            return {"success": False,
                    "message": f"⚠️ Testo non trovato in <code>{path}</code>:\n<code>{old_text[:100]}</code>"}
        # Backup
        backup = target.with_suffix(target.suffix + ".bak")
        backup.write_text(original, encoding="utf-8")
        # Replace
        if count == 0:
            new_content = original.replace(old_text, new_text)
            replaced = n_found
        else:
            new_content = original.replace(old_text, new_text, count)
            replaced = min(count, n_found)
        target.write_text(new_content, encoding="utf-8")
        return {"success": True,
                "message": (f"✅ Sostituito {replaced}/{n_found} occorrenze in <code>{path}</code>\n"
                            f"💾 Backup: <code>{backup.name}</code>")}
    except Exception as e:
        logger.exception("tool_replace_in_file")
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: tool_move_file — sposta o rinomina file/cartella
# ══════════════════════════════════════════════════════════════════════

def tool_move_file(src: str, dst: str) -> dict:
    """Sposta o rinomina un file/cartella dentro /config.

    Args:
        src: path sorgente
        dst: path destinazione (nuovo nome o nuova posizione)
    """
    import shutil as _sh
    try:
        src_p = _safe_path(src)
        dst_p = _safe_path(dst)
        if _is_protected(src_p):
            return {"success": False, "message": f"⚠️ Sorgente protetta: {src}"}
        if not src_p.exists():
            return {"success": False, "message": f"❌ Sorgente non trovata: {src}"}
        if dst_p.is_dir():
            dst_p = dst_p / src_p.name
        if dst_p.exists():
            return {"success": False, "message": f"⚠️ Destinazione già esistente: {dst}"}
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        _sh.move(str(src_p), str(dst_p))
        return {"success": True,
                "message": f"✅ Spostato: <code>{src}</code> → <code>{dst}</code>"}
    except Exception as e:
        logger.exception("tool_move_file")
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════════
# TOOL: tool_copy_file — copia file/cartella
# ══════════════════════════════════════════════════════════════════════

def tool_copy_file(src: str, dst: str) -> dict:
    """Copia un file o cartella dentro /config.

    Args:
        src: path sorgente
        dst: path destinazione
    """
    import shutil as _sh
    try:
        src_p = _safe_path(src)
        dst_p = _safe_path(dst)
        if not src_p.exists():
            return {"success": False, "message": f"❌ Sorgente non trovata: {src}"}
        if dst_p.is_dir():
            dst_p = dst_p / src_p.name
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        if src_p.is_dir():
            _sh.copytree(str(src_p), str(dst_p))
        else:
            _sh.copy2(str(src_p), str(dst_p))
        return {"success": True,
                "message": f"✅ Copiato: <code>{src}</code> → <code>{dst}</code>"}
    except Exception as e:
        logger.exception("tool_copy_file")
        return {"success": False, "message": f"Errore: {str(e)[:200]}"}


def format_ls_for_display(result: dict) -> str:
    """Formatta output di tool_ls per Telegram."""
    if not result.get("success"):
        return result.get("message", "Errore")
    lines = [f"📁 <b>{result['path'] or '/'}</b> ({result['count']} elementi)\n"]
    for e in result["entries"]:
        if e["type"] == "dir":
            lines.append(f"  📁 <code>{e['name']}/</code>")
        else:
            sz_kb = e["size"] / 1024
            sz_str = f"{sz_kb:.1f} KB" if sz_kb >= 1 else f"{e['size']} B"
            lines.append(f"  📄 <code>{e['name']}</code>  <i>({sz_str})</i>")
    return "\n".join(lines)
