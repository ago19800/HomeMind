"""
GitHub Installer — wizard guidato installazione di:
- Add-on Home Assistant (via supervisor)
- Custom Component (clone in /config/custom_components/)
- Lovelace Card (download in /config/www/community/)
"""

import os
import re
import json
import shutil
import asyncio
import logging
import subprocess
from pathlib import Path
import aiohttp

logger = logging.getLogger(__name__)

CONFIG_DIR              = Path("/config")
CUSTOM_COMPONENTS_DIR   = CONFIG_DIR / "custom_components"
COMMUNITY_DIR           = CONFIG_DIR / "www" / "community"



async def _github_download_zip(owner: str, repo: str,
                                 branch: str = None,
                                 session: aiohttp.ClientSession = None) -> bytes:
    """Scarica un repo GitHub come ZIP senza git (Python + aiohttp).

    Prova in ordine: branch specificato → main → master → API zipball.
    Ritorna bytes del file ZIP, oppure solleva Exception se fallisce.
    """
    import io as _io

    branches = [branch] if branch else ["main", "master"]
    headers  = {"User-Agent": "HomeMind/1.0"}
    timeout  = aiohttp.ClientTimeout(total=90)

    async def _try_download(url, sess):
        async with sess.get(url, allow_redirects=True) as resp:
            if resp.status == 200:
                data = await resp.read()
                if len(data) > 200 and data[:2] == b"PK":  # ZIP magic bytes
                    return data
        return None

    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession(timeout=timeout, headers=headers)

    try:
        for br in branches:
            url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{br}.zip"
            data = await _try_download(url, session)
            if data:
                return data

        # Fallback: API GitHub zipball (usa default branch)
        api_url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
        data = await _try_download(api_url, session)
        if data:
            return data

    finally:
        if own_session:
            await session.close()

    raise RuntimeError(
        f"Impossibile scaricare {owner}/{repo} da GitHub. "
        f"Verifica che il repository esista e sia pubblico."
    )


def _extract_zip_bytes(zip_bytes: bytes, dest_dir: Path, strip_root: bool = True) -> list:
    """Estrae ZIP bytes in dest_dir. Se strip_root=True rimuove la prima cartella root.

    Ritorna lista di file estratti (path relativi a dest_dir).
    """
    import zipfile as _zf
    import io as _io

    extracted = []
    dest_dir.mkdir(parents=True, exist_ok=True)

    with _zf.ZipFile(_io.BytesIO(zip_bytes)) as zf:
        members = zf.namelist()
        root_prefix = ""
        if strip_root and members:
            first = members[0]
            if first.endswith("/"):
                root_prefix = first  # es. "repo-main/"

        for member in members:
            rel = member[len(root_prefix):] if root_prefix and member.startswith(root_prefix) else member
            if not rel:
                continue
            out = (dest_dir / rel).resolve()
            if not str(out).startswith(str(dest_dir.resolve())):
                continue  # path traversal guard
            if member.endswith("/"):
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(out, "wb") as dst:
                    dst.write(src.read())
                extracted.append(rel)
    return extracted


def parse_github_url(url: str) -> dict:
    """Estrae owner/repo/branch da un URL GitHub.

    Esempi accettati:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo/tree/branch
    - github.com/owner/repo
    - owner/repo

    Returns: {owner, repo, branch} o None se non valido
    """
    if not url:
        return None
    url = url.strip()
    # Rimuovi prefisso https://
    url = re.sub(r'^https?://', '', url)
    # Rimuovi github.com/ (con o senza)
    url = re.sub(r'^github\.com/', '', url, flags=re.IGNORECASE)
    # Rimuovi .git finale
    url = re.sub(r'\.git/?$', '', url)
    # Pattern owner/repo[/tree/branch]
    m = re.match(r'^([\w\-.]+)/([\w\-.]+)(?:/tree/([\w\-./]+))?$', url)
    if not m:
        return None
    return {
        "owner":  m.group(1),
        "repo":   m.group(2),
        "branch": m.group(3) or "main",
    }


class GitHubInstaller:
    """Wizard installazione da GitHub."""

    def __init__(self, supervisor_token: str = ""):
        self.supervisor_token = supervisor_token
        CUSTOM_COMPONENTS_DIR.mkdir(parents=True, exist_ok=True)
        COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)

    # ══════════════════════════════════════════════════════════════════
    # README READER (per generare guida AI)
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def find_readme(directory: Path, max_chars: int = 8000) -> str:
        """Cerca README.md nella directory e ritorna i primi max_chars."""
        candidates = [
            "README.md", "Readme.md", "readme.md",
            "README.MD", "README", "README.txt",
        ]
        for name in candidates:
            p = directory / name
            if p.exists():
                try:
                    txt = p.read_text(encoding="utf-8", errors="ignore")
                    return txt[:max_chars]
                except Exception:
                    continue
        # Fallback: rglob su tutto
        for p in directory.rglob("README.md"):
            try:
                return p.read_text(encoding="utf-8", errors="ignore")[:max_chars]
            except Exception:
                continue
        return ""

    @staticmethod
    async def fetch_readme_remote(owner: str, repo: str, branch: str = "main") -> str:
        """Scarica README.md direttamente da GitHub (raw) senza clonare."""
        urls = [
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md",
            f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md",
            f"https://raw.githubusercontent.com/{owner}/{repo}/main/Readme.md",
        ]
        try:
            async with aiohttp.ClientSession() as s:
                for url in urls:
                    try:
                        async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                            if r.status == 200:
                                txt = await r.text()
                                return txt[:8000]
                    except Exception:
                        continue
        except Exception:
            pass
        return ""

    # ══════════════════════════════════════════════════════════════════
    # ADD-ON via Supervisor API
    # ══════════════════════════════════════════════════════════════════

    async def add_addon_repository(self, github_url: str) -> dict:
        """Aggiunge un repository di addon a HA Supervisor.

        Args:
            github_url: URL GitHub del repository addon

        Returns:
            {success: bool, message: str, repo_url: str}
        """
        if not self.supervisor_token:
            return {"success": False, "message": "SUPERVISOR_TOKEN non disponibile"}

        # Normalizza URL
        info = parse_github_url(github_url)
        if not info:
            return {"success": False, "message": f"URL GitHub non valido: {github_url}"}
        full_url = f"https://github.com/{info['owner']}/{info['repo']}"

        # 1. Aggiungi il repository
        url = "http://supervisor/store/repositories"
        headers = {
            "Authorization": f"Bearer {self.supervisor_token}",
            "Content-Type":  "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                # POST /store/repositories — body: {"repository": "https://github.com/..."}
                async with session.post(
                    url, headers=headers,
                    json={"repository": full_url},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status not in (200, 201):
                        body = await resp.text()
                        logger.warning(f"add repo failed {resp.status}: {body}")
                        return {
                            "success": False,
                            "message": f"Supervisor errore {resp.status}: {body[:300]}",
                            "repo_url": full_url,
                        }
                    # Fetch README remoto per la guida AI
                    readme_content = await self.fetch_readme_remote(
                        info['owner'], info['repo'], info.get('branch', 'main')
                    )
                    return {
                        "success":   True,
                        "message":   f"✅ Repository aggiunto.\nVai su: Impostazioni → Add-on → Add-on Store. Troverai i nuovi addon in fondo alla lista.",
                        "repo_url":  full_url,
                        "readme":    readme_content,
                        "github_url": full_url,
                        "type":      "addon",
                    }
        except Exception as e:
            logger.exception("add_addon_repository")
            return {"success": False, "message": f"Errore: {str(e)[:200]}",
                    "repo_url": full_url}

    # ══════════════════════════════════════════════════════════════════
    # CUSTOM COMPONENT via git clone
    # ══════════════════════════════════════════════════════════════════

    async def install_custom_component(self, github_url: str) -> dict:
        """Clona un custom component in /config/custom_components/.

        Cerca la cartella che contiene manifest.json (può essere root o sub-folder).

        Returns:
            {success: bool, message: str, installed_path: str}
        """
        info = parse_github_url(github_url)
        if not info:
            return {"success": False, "message": f"URL non valido: {github_url}"}

        repo_url = f"https://github.com/{info['owner']}/{info['repo']}.git"
        # Cartella temporanea per il clone
        tmp_dir = CONFIG_DIR / "tmp_homemind_clone"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

        try:
            # Clone (shallow)
            zip_bytes = await _github_download_zip(
                info["owner"], info["repo"],
                branch=info.get("branch")
            )
            _extract_zip_bytes(zip_bytes, tmp_dir)
            # Cerca manifest.json — può essere in root o in custom_components/<name>/
            manifest_paths = list(tmp_dir.rglob("manifest.json"))
            # Filtra: solo manifest che hanno "domain" (è un component HA)
            valid_manifests = []
            for mp in manifest_paths:
                try:
                    data = json.loads(mp.read_text(encoding="utf-8"))
                    if "domain" in data:
                        valid_manifests.append((mp, data))
                except Exception:
                    continue

            if not valid_manifests:
                return {
                    "success": False,
                    "message": "Repository non sembra un custom_component "
                               "(nessun manifest.json con 'domain' trovato)",
                }

            # Usa il primo manifest valido
            manifest_path, manifest_data = valid_manifests[0]
            domain = manifest_data["domain"]
            source_dir = manifest_path.parent

            # Copia in /config/custom_components/<domain>/
            target_dir = CUSTOM_COMPONENTS_DIR / domain
            if target_dir.exists():
                # Backup vecchia versione
                backup = CUSTOM_COMPONENTS_DIR / f"{domain}_backup_{int(asyncio.get_event_loop().time())}"
                shutil.move(str(target_dir), str(backup))
                logger.info(f"Vecchia versione di {domain} → {backup}")

            shutil.copytree(source_dir, target_dir)
            logger.info(f"Custom component '{domain}' installato in {target_dir}")

            # Cattura README per generare guida AI dopo
            readme_content = self.find_readme(tmp_dir)
            return {
                "success": True,
                "message": (f"✅ Custom component <b>{domain}</b> installato.\n\n"
                            f"📦 Versione: {manifest_data.get('version', 'N/A')}\n"
                            f"📁 Path: <code>{target_dir.relative_to(CONFIG_DIR)}</code>\n\n"
                            f"⚠️ <b>Riavvia Home Assistant</b> per attivare il component.\n"
                            f"Poi vai su Impostazioni → Dispositivi → Aggiungi Integrazione e cerca '{domain}'."),
                "installed_path": str(target_dir.relative_to(CONFIG_DIR)),
                "domain":         domain,
                "version":        manifest_data.get("version", "N/A"),
                "readme":         readme_content,
                "github_url":     f"https://github.com/{info['owner']}/{info['repo']}",
                "type":           "component",
            }
        finally:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    # ══════════════════════════════════════════════════════════════════
    # LOVELACE CARD
    # ══════════════════════════════════════════════════════════════════

    async def install_lovelace_card(self, github_url: str,
                                     js_filename: str = None) -> dict:
        """Scarica un file .js card Lovelace in /config/www/community/<repo>/.

        Args:
            github_url: URL GitHub del repository
            js_filename: nome del .js da scaricare (default: cerca dist/*.js o release)

        Returns:
            {success, message, installed_path, registration_yaml}
        """
        info = parse_github_url(github_url)
        if not info:
            return {"success": False, "message": f"URL non valido: {github_url}"}

        repo_url = f"https://github.com/{info['owner']}/{info['repo']}.git"
        tmp_dir = CONFIG_DIR / "tmp_homemind_card_clone"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

        try:
            # Clone
            zip_bytes = await _github_download_zip(
                info["owner"], info["repo"],
                branch=None
            )
            _extract_zip_bytes(zip_bytes, tmp_dir)
            # Trova file .js — strategia gerarchica:
            # 1. dist/<repo>.js o dist/<card-name>.js (build prodotti)
            # 2. dist/*.js (qualsiasi nella dist)
            # 3. root/*.js (escludendo file di build)
            # 4. ovunque (.js) — limita per evitare di prendere node_modules
            candidates = []
            repo_lower = info["repo"].lower()
            dist_dir = tmp_dir / "dist"
            if dist_dir.exists():
                # Priorità: file con nome del repo
                preferred = [p for p in dist_dir.glob("*.js")
                             if repo_lower in p.name.lower()]
                if preferred:
                    candidates = preferred
                else:
                    candidates = list(dist_dir.glob("*.js"))
            if not candidates:
                # Cerca .js in root, escludi config e source
                exclude_prefixes = ("rollup", "webpack", "config", "babel", "jest", ".eslintrc")
                exclude_substrings = ("source-map", ".test.", ".spec.")
                candidates = [
                    p for p in tmp_dir.glob("*.js")
                    if not any(p.name.startswith(x) for x in exclude_prefixes)
                    and not any(x in p.name for x in exclude_substrings)
                ]
            if not candidates:
                # Ricerca generica escludendo node_modules / src
                excluded_dirs = {"node_modules", "src", ".git", "test", "tests"}
                for p in tmp_dir.rglob("*.js"):
                    if any(part in excluded_dirs for part in p.parts):
                        continue
                    candidates.append(p)
                    if len(candidates) >= 10:
                        break

            if not candidates:
                return {"success": False,
                        "message": "Nessun file .js trovato nel repository"}

            # Filtra per filename se specificato
            if js_filename:
                filtered = [p for p in candidates if p.name == js_filename]
                if filtered:
                    candidates = filtered

            # Usa il primo (priorità: dist > root)
            js_file = candidates[0]
            card_name = info["repo"].lower()

            # Crea directory community/<repo>
            target_dir = COMMUNITY_DIR / card_name
            target_dir.mkdir(parents=True, exist_ok=True)
            target_js  = target_dir / js_file.name
            shutil.copy2(js_file, target_js)

            # YAML per registrazione in Lovelace
            registration_yaml = f"""resources:
  - url: /local/community/{card_name}/{js_file.name}
    type: module"""

            # Cattura README per AI
            readme_content = self.find_readme(tmp_dir)
            # Estrai card-type dalla card (per generare esempio YAML)
            card_type = card_name  # default
            try:
                js_text = js_file.read_text(encoding="utf-8", errors="ignore")
                m_ct = re.search(r'(?:customElements\.define|"type"\s*:\s*")["\']?(["\']?[\w\-]+)',
                                 js_text)
                if m_ct:
                    card_type = m_ct.group(1).strip("\"\'")
            except Exception:
                pass
            return {
                "success": True,
                "message": (f"✅ Card <b>{card_name}</b> installata.\n\n"
                            f"📁 Path: <code>www/community/{card_name}/{js_file.name}</code>\n\n"
                            f"⚠️ <b>Per usare la card devi registrarla in Lovelace.</b>\n\n"
                            f"<b>Opzione 1 (UI):</b>\n"
                            f"Impostazioni → Dashboard → Risorse → Aggiungi:\n"
                            f"   URL: <code>/local/community/{card_name}/{js_file.name}</code>\n"
                            f"   Tipo: Modulo JavaScript\n\n"
                            f"<b>Opzione 2 (YAML):</b>\n"
                            f"<pre>{registration_yaml}</pre>\n\n"
                            f"Poi ricarica la dashboard."),
                "installed_path":    str(target_js.relative_to(CONFIG_DIR)),
                "registration_yaml": registration_yaml,
                "card_name":         card_name,
                "js_filename":       js_file.name,
                "card_type":         card_type,
                "readme":            readme_content,
                "github_url":        f"https://github.com/{info['owner']}/{info['repo']}",
                "type":              "card",
            }
        finally:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
