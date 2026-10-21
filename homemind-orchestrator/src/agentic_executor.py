"""
Agentic Executor v2 - orchestratore autonomo con pianificazione libera.
"""
import os
import re
import json
import shutil
import asyncio
import logging
from pathlib import Path
import tools_system as _tools

logger = logging.getLogger(__name__)

CONFIG_DIR = Path("/config")
_RULES_PATH_AE = Path("/config/homemind_patches/regole.md")

def _load_user_rules_ae() -> str:
    """Carica le regole utente da regole.md per iniettarle nel planning prompt."""
    try:
        if not _RULES_PATH_AE.exists():
            return ""
        lines = _RULES_PATH_AE.read_text(encoding="utf-8").splitlines()
        rules = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
        if not rules:
            return ""
        return "\n".join(rules)
    except Exception:
        return ""
MAX_STEPS = 15              # safety: max tool call per task
MAX_TOOL_RESULT_LEN = 4000  # tronca output tool prima di rimettere in contesto AI


# ════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY - descrizione completa per l'AI
# ════════════════════════════════════════════════════════════════════════

TOOLS_DESCRIPTION = """
Sei un agente autonomo focalizzato sul task dell'utente. Esegui SOLO ciò che viene richiesto.

════════════════════════════════════════════════
FORMATO RISPOSTA - SEMPRE JSON PURO:
{"thought": "ragionamento", "tool": "nome", "args": {...}}

NESSUN testo fuori dal JSON. NESSUN markdown fence. Solo JSON.
════════════════════════════════════════════════

REGOLE CORE:
1. Rispondi SEMPRE con JSON valido contenente thought/tool/args.
2. PATH ASSOLUTI: usa sempre /config/file.yaml, NON "file.yaml" da solo.
3. Usa path relativi SOLO nel formato "ago/..." (che mappa su /config/ago/...).
4. Quando il task è completato usa `finish` immediatamente — non aggiungere step extra.
5. Se un tool fallisce per path sbagliato → correggi il path, NON cambiare approccio.
6. NON usare tool non elencati qui sotto. NON inventare tool.
7. NON fare operazioni non richieste (clone, mkdir, download, delete) a meno che esplicitamente chiesto.
8. Puoi usare `parallel_steps` per operazioni indipendenti simultanee.
9. Nelle args puoi riferire output precedenti con {step_N} (N = numero step).

════════════ TOOL DISPONIBILI ════════════

📁 FILE E CARTELLE:
- ls(path)
  Elenca cartella. → {"tool":"ls","args":{"path":"ago/progetti"}}

- read(path, max_chars=8000)
  Legge file. → {"tool":"read","args":{"path":"ago/note.md"}}

- write(path, content, append=false)
  Scrive file (sovrascrive se esiste, o appende se append=true).
  Usa per "scrivi cosa hai fatto", "scrivi un log", "scrivi riassunto installazione".
  Il content viene scritto ESATTAMENTE come specificato — puoi mettere markdown.
  → {"tool":"write","args":{"path":"ago/fatto.md","content":"## Cosa ho fatto\n- Clonato HomeMind\n- Creato archivio tar.gz"}}
  → {"tool":"write","args":{"path":"ago/riassunto.md","content":"## Installazione HomeMind\n1. Aggiungi repo...\n2. Installa addon..."}}

- append(path, content)
  Aggiunge contenuto a un file esistente.

- mkdir(path)
  Crea cartella (ricorsiva).

- move(src, dst) / copy(src, dst) / delete(path)
  Operazioni filesystem. delete richiede conferma utente.

📦 ARCHIVI - CREAZIONE:
- archive(source, output?)  alias: create_tar, tar
  Crea archivio .tar.gz da file o cartella.
  source: path da comprimere, output: path .tar.gz (opzionale)
  → {"tool":"archive","args":{"source":"ago/progetti/HomeMind","output":"ago/progetti/HomeMind.tar.gz"}}

- create_zip(source, output?)  alias: zip
  Crea archivio .zip da file o cartella.
  → {"tool":"create_zip","args":{"source":"ago/progetti/HomeMind","output":"ago/HomeMind.zip"}}

📥 SCARICA E CLONA:
- download(url, dest)
  Scarica URL in file. → {"tool":"download","args":{"url":"https://...","dest":"ago/file.zip"}}

- clone(repo, dest)
  Clona repo GitHub. Accetta "owner/name" O "https://github.com/owner/repo".
  → {"tool":"clone","args":{"repo":"https://github.com/ago19800/HomeMind","dest":"ago/progetti"}}

- clone_and_summarize(repo, dest, output, prompt?)
  ⭐ Clona repo, legge README, genera riassunto AI, salva file.
  → {"tool":"clone_and_summarize","args":{"repo":"https://github.com/ago19800/HomeMind",
     "dest":"ago/progetti","output":"ago/progetti/riassunto.md"}}

- unzip_file(archive, dest)
  Estrae ZIP con Python nativo.

- extract_tar(archive, dest)
  Estrae .tar.gz/.tgz con Python nativo.

- fetch_url(url, save_to?)
  Scarica testo pagina web. Opzionalmente salva in file.
  → {"tool":"fetch_url","args":{"url":"https://...","save_to":"ago/pagina.md"}}

🤖 AI E TESTO:
- ai_generate(prompt)
  Chiede all'AI di generare testo/codice da zero.
  → {"tool":"ai_generate","args":{"prompt":"Scrivi un README per questo progetto..."}}

- ai_edit_file(path, instruction)  ⭐ USA QUESTO per modificare file — 1 SOLO STEP
  Legge il file AUTONOMAMENTE (NON serve read() prima), applica patch chirurgica,
  salva con backup automatico. Usa path ASSOLUTO: /config/automations.yaml
  → {"tool":"ai_edit_file","args":{"path":"/config/automations.yaml","instruction":"cambia orario automazione X da 22:00 a 13:00"}}
- read_and_summarize(path, prompt?)
  Legge file e lo riassume con AI.
  → {"tool":"read_and_summarize","args":{"path":"ago/doc.md","prompt":"elenca i requisiti"}}

- download_and_read(url, dest?, summarize?)
  Scarica e legge/riassume file da URL.

🔗 COMPOSIZIONE - ⭐ POWER FEATURES:
- plan(steps)
  ⭐ DICHIARA UN PIANO COMPLETO che verrà eseguito passo per passo.
  Ogni step ha: tool, args, label (opzionale, mostrata all'utente).
  Nelle args puoi usare {step_N} per riferire l'output dello step N.
  IDEALE per task multi-azione descritti dall'utente in linguaggio libero.
  Esempio: "scarica repo, scrivi riassunto, mostrami il file"
  → {"tool":"plan","args":{"steps":[
      {"tool":"clone","args":{"repo":"https://github.com/ago19800/HomeMind","dest":"ago/progetti"},"label":"📥 Clono il repo"},
      {"tool":"read_and_summarize","args":{"path":"{step_1_path}/README.md"},"label":"📋 Leggo README"},
      {"tool":"write","args":{"path":"ago/progetti/riassunto.md","content":"{step_2}"},"label":"💾 Salvo riassunto"},
      {"tool":"read","args":{"path":"ago/progetti/riassunto.md"},"label":"📖 Mostro il risultato"}
    ]}}

- parallel_steps(steps, labels?)
  ⭐ Esegue più tool CONTEMPORANEAMENTE (asyncio.gather).
  Perfetto per operazioni indipendenti: scarica più file, leggi più file, ecc.
  Ogni step: {tool, args, label?}
  → {"tool":"parallel_steps","args":{"steps":[
      {"tool":"fetch_url","args":{"url":"https://site1.com"},"label":"Scarico sito 1"},
      {"tool":"fetch_url","args":{"url":"https://site2.com"},"label":"Scarico sito 2"}
    ]}}

🖥️ SHELL E SISTEMA:
- shell_natural(request)
  ⭐ Comando shell in linguaggio naturale - l'AI genera ed esegue.
  → {"tool":"shell_natural","args":{"request":"mostrami i file più grandi in ago/"}}

- shell_exec(command, intent, cwd)
  Esegue comando shell esatto.

- ping(host, count=4)
  Ping Python puro - funziona sempre.

- portscan(host, ports="common")
  Scansione porte Python - funziona sempre.

- install_package(package)
  Installa pacchetto Alpine.

🏠 HOME ASSISTANT:
- ha_system_info()   → Info RAM/CPU/disco/OS via Supervisor
- ha_addons_list()   → Lista addon installati
- ha_addon_stats(slug) → CPU/RAM di un addon specifico
- ha_call_service(domain, service, data) → Chiama servizio HA
  ⚠️ Solo servizi REALI di HA (light.turn_on, switch.toggle, automation.reload, ecc.)
  NON inventare servizi tipo "person/list_users" — non esistono.
- ha_list_users() → Elenca utenti/persone registrate (entità person.*)
  Usa QUESTO per "lista utenti" / "trova utenti registrati", NON ha_call_service.
- ha_natural(request) → Comandi HA in linguaggio naturale
- list_entities(filter) → Elenca entità HA filtrate (es. filter="person", "light", "binary_sensor")

🌐 WEB:
- search_web(query, max_results=5) → Ricerca web
- fetch_page(url) → Scarica testo pagina

✅ FINE TASK:
- finish(message)
  Termina con messaggio riassuntivo per l'utente.
  → {"tool":"finish","args":{"message":"Ho clonato il repo, scritto il riassunto e mostrato il contenuto."}}

════════════ REGOLE SPECIALI ════════════

PER TASK MULTI-STEP LIBERI (es. "scarica X, scrivi Y, mostrami Z"):
  → USA `plan` per pianificare tutto in anticipo in un solo JSON.
  → L'agente eseguirà ogni step e mostrerà l'output all'utente.
  → {step_N} nelle args accede all'output dello step N già eseguito.

PER OPERAZIONI INDIPENDENTI:
  → USA `parallel_steps` - eseguono contemporaneamente, risparmia tempo.

PER PING/PORTSCAN:
  → USA `ping` o `portscan` - MAI shell_natural("ping...") o shell_natural("nmap...")

PER ARCHIVI:
  → .zip: tool="unzip_file", args={"archive":"path/file.zip","dest":"dest/"}
  → .tar.gz/.tgz: tool="extract_tar", args={"archive":"path/file.tar.gz","dest":"dest/"}
  → MAI usare tool="extract_tar"  # o "unzip_file" per .zip o shell_natural("unzip...")

RICORDA:
  → `clone` accetta sia "owner/name" che URL completo GitHub
  → Path sono sempre relativi a /config - scrivi "ago/file.md" non "/config/ago/file.md"
  → Se devi mostrare un file all'utente, usa `read` come ultimo step
"""


def _safe_path(rel: str) -> Path:
    """Risolve path con security check."""
    if rel.startswith("/config/"):
        rel = rel[len("/config/"):]
    elif rel.startswith("/"):
        rel = rel[1:]
    target = (CONFIG_DIR / rel).resolve()
    if not str(target).startswith(str(CONFIG_DIR.resolve())):
        raise PermissionError(f"path fuori da /config: {rel}")
    return target


# ════════════════════════════════════════════════════════════════════════
# INTERPOLAZIONE VARIABILI {step_N}
# ════════════════════════════════════════════════════════════════════════

def _interpolate(value, step_outputs: dict):
    """Sostituisce {step_N} e {step_N_path} con output degli step precedenti."""
    if not isinstance(value, str):
        return value
    result = value

    # {step_N} → output testuale dello step N
    for match in re.findall(r'\{step_(\d+)\}', value):
        n = int(match)
        replacement = step_outputs.get(n, {}).get("result", "")
        result = result.replace(f"{{step_{n}}}", str(replacement)[:3000])

    # {step_N_path} → path (data.path) restituito dallo step N (es. clone → path cartella)
    for match in re.findall(r'\{step_(\d+)_path\}', value):
        n = int(match)
        path_val = step_outputs.get(n, {}).get("data", {})
        if isinstance(path_val, dict):
            path_val = path_val.get("path", path_val.get("clone_path", ""))
        result = result.replace(f"{{step_{n}_path}}", str(path_val))

    # {prev_output} → output ultimo step
    if "{prev_output}" in result and step_outputs:
        last_n = max(step_outputs.keys())
        replacement = step_outputs[last_n].get("result", "")
        result = result.replace("{prev_output}", str(replacement)[:3000])

    return result


def _interpolate_args(args: dict, step_outputs: dict) -> dict:
    """Interpola ricorsivamente tutti i valori stringa negli args."""
    if not args:
        return args
    result = {}
    for k, v in args.items():
        if isinstance(v, str):
            result[k] = _interpolate(v, step_outputs)
        elif isinstance(v, dict):
            result[k] = _interpolate_args(v, step_outputs)
        elif isinstance(v, list):
            result[k] = [
                _interpolate_args(item, step_outputs) if isinstance(item, dict)
                else _interpolate(item, step_outputs) if isinstance(item, str)
                else item
                for item in v
            ]
        else:
            result[k] = v
    return result


# ════════════════════════════════════════════════════════════════════════
# TOOL DISPATCHER
# ════════════════════════════════════════════════════════════════════════

async def execute_tool(tool: str, args: dict, context: dict) -> dict:
    """Esegue un tool e ritorna {success, result, data}."""
    try:

        # ── plan - esegue lista di step in sequenza con interpolazione ────────
        if tool == "plan":
            steps_def = args.get("steps", [])
            if not steps_def:
                return {"success": False, "result": "args: {steps: [{tool,args,label?}]} richiesto"}
            progress_cb = context.get("_progress_cb")
            step_outputs = {}   # {1: {result, data}, 2: ...}
            summary_lines = []
            all_ok = True
            for i, step_def in enumerate(steps_def[:20], start=1):
                step_tool  = step_def.get("tool", "")
                step_args  = _interpolate_args(dict(step_def.get("args", {})), step_outputs)
                step_label = step_def.get("label", f"Step {i}: {step_tool}")
                stop_on_err = step_def.get("stop_on_error", True)

                # Notifica utente - step iniziato
                if progress_cb:
                    try:
                        await progress_cb(f"plan_{i}", step_tool, step_args,
                                          step_label, None)
                    except Exception:
                        pass

                r = await execute_tool(step_tool, step_args, context)
                step_outputs[i] = r

                ok_icon = "✅" if r.get("success") else "❌"
                summary_lines.append(f"{ok_icon} {step_label}")

                # Notifica utente - risultato step
                if progress_cb:
                    try:
                        await progress_cb(f"plan_{i}", step_tool, step_args,
                                          step_label, r)
                    except Exception:
                        pass

                if not r.get("success") and stop_on_err:
                    summary_lines.append(f"  ⚠️ Fermato: {r.get('result','')[:200]}")
                    all_ok = False
                    break

            last_result = step_outputs.get(len(step_outputs), {})
            return {
                "success": all_ok,
                "result": "\n".join(summary_lines) + f"\n\n{last_result.get('result','')[:3000]}",
                "data": {f"step_{k}": v for k, v in step_outputs.items()}
            }

        # ── parallel_steps - esegue più tool contemporaneamente ───────────────
        # ── Alias per nomi sbagliati usati dall'AI ──────────────────────────────
        def _resolve_alias(t, a):
            """Risolve alias comuni tool → nome reale."""
            _map = {
                "extract": lambda: "extract_tar" if str(a.get("archive","") or a.get("source","") or a.get("path","") or a.get("file","")).endswith(
                    (".tar.gz",".tgz",".tar.bz2",".tar")) else "unzip_file",
                "unzip": "unzip_file",
                "tar_extract": "extract_tar",
                "tar": "extract_tar",
                "read_file": "read",
                "write_file": "write",
                "list": "ls",
                "list_files": "ls",
                "list_dir": "ls",
                "search": "search_web",
                "web_search": "search_web",
                "fetch": "fetch_page",
                "wget": "download",
                "curl": "fetch_page",
                "move_file": "move",
                "copy_file": "copy",
                "delete_file": "delete",
                "rm": "delete",
                "cp": "copy",
                "mv": "move",
                "mkdir_p": "mkdir",
                "make_dir": "mkdir",
                "shell": "shell_exec",
                "bash": "shell_exec",
                "run": "shell_exec",
                "run_command": "shell_exec",
                "execute": "shell_exec",
                "ha_service": "ha_call_service",
                "call_service": "ha_call_service",
                "ha_info": "ha_system_info",
                "system_info": "ha_system_info",
                "ha_addons": "ha_addons_list",
                "addons": "ha_addons_list",
                "generate": "ai_generate",
                "summarize": "read_and_summarize",
                "summary": "read_and_summarize",
                "get_url": "fetch_url",
                "get_page": "fetch_url",
                "clone_repo": "clone",
                "git_clone": "clone",
                "json": "shell_natural",  # AI usa "json" per parsing → reindirizza
                "parse": "shell_natural",
                "parse_json": "shell_natural",
            }
            v = _map.get(t)
            if v is None:
                return t
            return v() if callable(v) else v

        tool = _resolve_alias(tool, args)

        if tool == "parallel_steps":
            steps_def = args.get("steps", [])
            if not steps_def:
                return {"success": False, "result": "args: {steps: [{tool,args,label?}]} richiesto"}
            progress_cb = context.get("_progress_cb")

            # Notifica avvio parallelo
            if progress_cb:
                labels = [s.get("label", s.get("tool","?")) for s in steps_def]
                try:
                    await progress_cb("parallel", "parallel_steps", args,
                                      f"⚡ Eseguo in parallelo: {', '.join(labels)}", None)
                except Exception:
                    pass

            tasks = [
                execute_tool(s.get("tool",""), dict(s.get("args",{})), context)
                for s in steps_def[:10]
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            lines = []
            all_data = {}
            for i, (s, r) in enumerate(zip(steps_def, results), start=1):
                label = s.get("label", s.get("tool","?"))
                if isinstance(r, Exception):
                    r = {"success": False, "result": str(r)}
                icon = "✅" if r.get("success") else "❌"
                lines.append(f"{icon} {label}")
                all_data[f"step_{i}"] = r

            combined = "\n".join(lines)
            # Aggiungi output di ogni step
            for i, (s, r) in enumerate(zip(steps_def, results), start=1):
                if not isinstance(r, Exception) and r.get("result"):
                    combined += f"\n\n── {s.get('label', s.get('tool','?'))} ──\n{r['result'][:1000]}"

            # Notifica completamento
            if progress_cb:
                try:
                    await progress_cb("parallel", "parallel_steps", args,
                                      "parallel_steps", {"success": True, "result": combined})
                except Exception:
                    pass

            return {"success": True, "result": combined, "data": all_data}

        # ── ls ────────────────────────────────────────────────────────────────
        if tool == "ls":
            r = _tools.tool_ls(args.get("path", "."))
            if r["success"]:
                lines = []
                for e in r["entries"]:
                    icon = "📁" if e["type"] == "dir" else "📄"
                    lines.append(f"  {icon} {e['name']} ({e['size']}B)" if e["type"] == "file"
                                 else f"  {icon} {e['name']}/")
                return {"success": True,
                        "result": f"Contenuto di {r['path']} ({r['count']} elementi):\n" + "\n".join(lines),
                        "data": r["entries"]}
            return {"success": False, "result": r["message"]}

        # ── read ──────────────────────────────────────────────────────────────
        if tool == "read":
            max_chars = args.get("max_chars", 8000)
            r = _tools.tool_lettura(args.get("path", ""), max_chars=max_chars)
            if r["success"]:
                trunc = " (TRONCATO)" if r.get("truncated") else ""
                return {"success": True,
                        "result": f"File {r['path']} ({r['size']} bytes){trunc}:\n\n{r['content']}",
                        "data": r["content"]}
            return {"success": False, "result": r["message"]}

        # ── write ─────────────────────────────────────────────────────────────
        if tool == "write":
            path    = args.get("path", "")
            content = args.get("content", "")
            if args.get("append", False):
                r = _tools.tool_append(path, content)
            else:
                r = _tools.tool_scrittura(path, content, overwrite=True)
            return {"success": r["success"], "result": r["message"]}

        # ── append ────────────────────────────────────────────────────────────
        if tool == "append":
            r = _tools.tool_append(args.get("path", ""), args.get("content", ""))
            return {"success": r["success"], "result": r["message"]}

        # ── mkdir ─────────────────────────────────────────────────────────────
        if tool == "mkdir":
            r = _tools.tool_mkdir(args.get("path", ""))
            return {"success": r["success"], "result": r["message"]}

        # ── move ──────────────────────────────────────────────────────────────
        if tool == "move":
            try:
                src = _safe_path(args.get("src", ""))
                dst = _safe_path(args.get("dst", ""))
                if not src.exists():
                    return {"success": False, "result": f"src non esiste: {args.get('src')}"}
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                return {"success": True, "result": f"✅ Spostato {args.get('src')} → {args.get('dst')}"}
            except Exception as e:
                return {"success": False, "result": f"Errore move: {str(e)[:200]}"}

        # ── copy ──────────────────────────────────────────────────────────────
        if tool == "copy":
            try:
                src = _safe_path(args.get("src", ""))
                dst = _safe_path(args.get("dst", ""))
                if not src.exists():
                    return {"success": False, "result": f"src non esiste: {args.get('src')}"}
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
                return {"success": True, "result": f"✅ Copiato {args.get('src')} → {args.get('dst')}"}
            except Exception as e:
                return {"success": False, "result": f"Errore copy: {str(e)[:200]}"}

        # ── delete ────────────────────────────────────────────────────────────
        if tool == "delete":
            confirmation_cb = context.get("confirmation_cb")
            path = args.get("path", "")
            if confirmation_cb:
                confirmed = await confirmation_cb(
                    f"⚠️ L'agente vuole eliminare:\n<code>{path}</code>\nConfermi?"
                )
                if not confirmed:
                    return {"success": False, "result": "❌ Eliminazione rifiutata dall'utente"}
            r = _tools.tool_delete(path)
            return {"success": r["success"], "result": r["message"]}

        # ── download ──────────────────────────────────────────────────────────
        if tool == "download":
            r = await _tools.tool_download(args.get("url", ""), args.get("dest", ""))
            return {"success": r["success"], "result": r["message"],
                    "data": {"path": r.get("path", "")}}

        # ── ping ──────────────────────────────────────────────────────────────
        if tool == "ping":
            host  = args.get("host", "") or args.get("ip", "")
            count = int(args.get("count", 4))
            if not host:
                return {"success": False, "result": "args: {host} richiesto"}
            r = await _tools.tool_ping_python(host, count=min(count, 10))
            return {"success": r["success"], "result": r["message"]}

        # ── portscan ──────────────────────────────────────────────────────────
        if tool == "portscan":
            host  = args.get("host", "") or args.get("ip", "")
            ports = args.get("ports", "common")
            if not host:
                return {"success": False, "result": "args: {host} richiesto"}
            r = await _tools.tool_portscan_python(host, ports=str(ports))
            return {"success": r["success"], "result": r["message"]}

        # ── unzip_file ────────────────────────────────────────────────────────
        if tool == "unzip_file":
            archive = args.get("archive", "") or args.get("path", "") or args.get("source", "") or args.get("file", "") or args.get("src", "")
            dest    = args.get("dest", "") or args.get("destination", "")
            if not archive:
                return {"success": False, "result": "args: {archive} richiesto"}
            r = _tools.tool_unzip_python(archive, dest)
            if r["success"] and r.get("files"):
                preview = "\n".join(f"  📄 {f}" for f in r["files"][:15])
                extras = f"\n  ... e altri {len(r['files'])-15}" if len(r['files']) > 15 else ""
                return {"success": True,
                        "result": f"{r['message']}\n\nFile estratti:\n{preview}{extras}"}
            return {"success": r["success"], "result": r["message"]}

        # ── extract_tar ───────────────────────────────────────────────────────
        if tool == "extract_tar":
            archive = args.get("archive", "") or args.get("path", "") or args.get("source", "") or args.get("file", "") or args.get("src", "")
            dest    = args.get("dest", "") or args.get("destination", "")
            if not archive:
                return {"success": False, "result": "args: {archive} richiesto"}
            r = _tools.tool_extract_tar_python(archive, dest)
            if r["success"] and r.get("files"):
                preview = "\n".join(f"  📄 {f}" for f in r["files"][:15])
                extras = f"\n  ... e altri {len(r['files'])-15}" if len(r['files']) > 15 else ""
                return {"success": True,
                        "result": f"{r['message']}\n\nFile estratti:\n{preview}{extras}"}
            return {"success": r["success"], "result": r["message"]}

        # ── clone ─────────────────────────────────────────────────────────────
        if tool == "clone":
            repo_arg = args.get("repo", "")
            dest_arg = args.get("dest", "").strip()
            if not dest_arg:
                return {"success": False,
                        "result": "⚠️ Percorso di destinazione non specificato.\n"
                                  "Indica dove vuoi salvare il repo (es: <code>ago/progetti</code>, "
                                  "<code>download</code>, <code>miei_progetti</code>).\n"
                                  "Tutti i percorsi sono relativi a <code>/config/</code>."}
            if repo_arg and not repo_arg.startswith("http"):
                repo_arg = f"https://github.com/{repo_arg.rstrip('/').removesuffix('.git')}"
            r = await _tools.tool_github_clone(repo_arg, dest_arg)
            return {"success": r["success"], "result": r["message"],
                    "data": {"path": r.get("path", dest_arg)}}

        # ── clone_and_summarize ───────────────────────────────────────────────
        if tool == "clone_and_summarize":
            repo_arg   = args.get("repo", "")
            dest_arg   = args.get("dest", "").strip()
            if not dest_arg:
                return {"success": False,
                        "result": "⚠️ Percorso di destinazione non specificato.\n"
                                  "Indica dove vuoi salvare il repo (es: <code>ago/progetti</code>).\n"
                                  "Tutti i percorsi sono relativi a <code>/config/</code>."}
            output     = args.get("output", "")
            prompt_ext = args.get("prompt", "")
            if not repo_arg or not dest_arg:
                return {"success": False, "result": "args: {repo, dest} richiesti"}
            if not repo_arg.startswith("http"):
                repo_arg = f"https://github.com/{repo_arg.rstrip('/').removesuffix('.git')}"
            rc = await _tools.tool_github_clone(repo_arg, dest_arg)
            if not rc["success"]:
                return {"success": False, "result": rc["message"]}
            clone_path = rc.get("path", dest_arg)
            readme_content = ""
            for readme_name in ("README.md", "readme.md", "README.rst", "README.txt", "DOCS.md"):
                rr = _tools.tool_lettura(f"{clone_path}/{readme_name}")
                if rr.get("success"):
                    readme_content = rr.get("content", "")
                    break
            if not readme_content:
                rl = _tools.tool_ls(clone_path)
                readme_content = "(Nessun README trovato)\n\nFile presenti:\n"
                if rl.get("success"):
                    readme_content += "\n".join(e["name"] for e in rl.get("entries", [])[:30])
            ai_cb = context.get("ai_cb")
            if not ai_cb:
                return {"success": False, "result": "AI non disponibile"}
            base_prompt = (
                "Scrivi un riassunto di installazione e utilizzo per questo progetto. "
                "Includi: scopo, requisiti, passi di installazione, configurazione, comandi. "
                "Usa Markdown con emoji. Sii conciso ma completo. Rispondi in italiano."
            )
            if prompt_ext:
                base_prompt += f"\n\nIstruzione: {prompt_ext}"
            summary = await ai_cb(
                base_prompt,
                f"Progetto: {repo_arg}\n\nREADME:\n{readme_content[:8000]}",
                None
            )
            if not summary:
                return {"success": False, "result": "AI non ha generato il riassunto"}
            if output:
                _tools.tool_mkdir(str(Path(output).parent))
                _tools.tool_scrittura(output, summary, overwrite=True)
                saved_note = f"\n💾 Salvato in: <code>/config/{output}</code>"
            else:
                saved_note = ""
            return {
                "success": True,
                "result": f"✅ {rc['message']}\n\n📋 Riassunto generato:{saved_note}\n\n{summary[:2000]}",
                "data": {"clone_path": clone_path, "summary": summary, "saved_to": output}
            }

        # ── search_web ────────────────────────────────────────────────────────
        if tool == "search_web":
            r = await _tools.tool_search_web(args.get("query", ""),
                                              max_results=args.get("max_results", 5))
            if r.get("success") and r.get("results"):
                lines = [f"Ricerca: {args.get('query')}"]
                for i, item in enumerate(r["results"][:5], 1):
                    lines.append(f"\n{i}. {item.get('title','')}")
                    lines.append(f"   URL: {item.get('url','')}")
                    lines.append(f"   {item.get('snippet','')[:200]}")
                return {"success": True, "result": "\n".join(lines), "data": r["results"]}
            return {"success": False, "result": r.get("message", "ricerca fallita")}

        # ── fetch_page ────────────────────────────────────────────────────────
        if tool == "fetch_page":
            r = await _tools.tool_fetch_page(args.get("url", ""), max_chars=6000)
            if r.get("success"):
                return {"success": True,
                        "result": f"Contenuto da {r.get('url')}:\n\n{r.get('text', '')}",
                        "data": r.get("text")}
            return {"success": False, "result": r.get("message", "fetch fallito")}

        # ── fetch_url ─────────────────────────────────────────────────────────
        if tool == "fetch_url":
            url  = args.get("url", "")
            path = args.get("save_to", "")
            if not url:
                return {"success": False, "result": "args: {url} richiesto"}
            r = _tools.tool_fetch_page(url)
            if not r.get("success"):
                return r
            text = r.get("content", r.get("text", ""))[:15000]
            result = {"success": True, "result": text, "url": url}
            if path:
                wr = _tools.tool_scrittura(path, f"# {url}\n\n{text}")
                result["saved_to"] = wr.get("path", path)
            return result

        # ── list_entities ─────────────────────────────────────────────────────
        if tool == "list_entities":
            state_cb = context.get("state_cache_cb")
            if not state_cb:
                return {"success": False, "result": "state_cache non disponibile"}
            cache = state_cb() or {}
            filt = (args.get("filter") or "").lower()
            matches = []
            for eid, s in cache.items():
                if filt and filt not in eid.lower():
                    fname = ((s.get("attributes") or {}).get("friendly_name") or "").lower()
                    if filt not in fname:
                        continue
                attrs = s.get("attributes") or {}
                matches.append(f"  • {eid} = {s.get('state','')} [{attrs.get('friendly_name','')}]")
                if len(matches) >= 30:
                    break
            return {"success": True,
                    "result": f"Entità trovate ({len(matches)}):\n" + "\n".join(matches),
                    "data": matches}

        # ── ai_generate ───────────────────────────────────────────────────────
        if tool == "ai_generate":
            ai_cb = context.get("ai_cb")
            if not ai_cb:
                return {"success": False, "result": "AI non disponibile"}
            prompt = args.get("prompt", "")
            sys = ("Sei un assistente esperto. Rispondi in modo diretto e conciso. "
                   "Se l'utente chiede codice, rispondi SOLO con il codice (no markdown, no spiegazioni). "
                   "Se chiede testo, rispondi in modo strutturato.")
            content = await ai_cb(sys, prompt, None)
            if not content:
                return {"success": False, "result": "AI non ha risposto"}
            return {"success": True, "result": content[:MAX_TOOL_RESULT_LEN], "data": content}

        # ── ai_edit_file ──────────────────────────────────────────────────────
        # Modalità SOLO PATCH (str_replace) — sicura, robusta, no allucinazioni.
        #
        # Vecchio approccio "rewrite completo" (rimosso): chiedeva all'AI di
        # rigurgitare l'intero file modificato. Problemi:
        #   1) supera context limit per file grandi (Groq 8K token)
        #   2) AI può inventare contenuto se il file è vuoto/sbagliato
        #   3) AI può troncare silenziosamente file lunghi
        # Il nuovo approccio chiede all'AI SOLO un piccolo patch JSON
        # {edits:[{old, new}]} e applichiamo le modifiche localmente con
        # str.replace, validando che ogni 'old' esista ed sia univoco.
        if tool == "ai_edit_file":
            ai_cb = context.get("ai_cb")
            if not ai_cb:
                return {"success": False, "result": "AI non disponibile"}
            path = args.get("path", "")
            instruction = args.get("instruction", "")
            if not path or not instruction:
                return {"success": False, "result": "args: {path, instruction} richiesti"}

            r_read = _tools.tool_lettura(path, max_chars=200000)
            if not r_read.get("success"):
                return {"success": False, "result": r_read.get("message", "read fallito")}
            original = r_read["content"]

            import json as _json
            import re as _re
            import time as _time

            # ── GUARD 0: sanity check sul path risolto ───────────────────────
            # Se il path risolto contiene "/config/config/", è quasi certo che
            # l'utente o l'AI ha scritto "config/foo" senza slash iniziale,
            # creando una path duplicata. Anche se la nuova _safe_path normalizza
            # questi casi, manteniamo questo controllo come difesa in profondità
            # (es. se qualcuno usa "/config/config/foo" esplicitamente).
            try:
                _resolved = _tools._safe_path(path)
                _resolved_str = str(_resolved)
                if "/config/config/" in _resolved_str:
                    return {"success": False,
                            "result": (f"⚠️ Path sospetto: '{path}' risolve a "
                                       f"'{_resolved_str}'. Probabilmente intendi "
                                       f"'/config/{path.lstrip('/').removeprefix('config/')}'. "
                                       f"Riprova con il path corretto.")}
            except Exception:
                pass  # se _safe_path fallisce qui, ci penserà tool_lettura

            # ── GUARD 1: file praticamente vuoto ─────────────────────────────
            # Se il file è quasi vuoto, NON lasciamo che l'AI inventi contenuto.
            # È quasi certamente il path sbagliato (es. "automations.yaml" senza
            # /config/ → file diverso o non esistente).
            stripped = original.strip()
            if len(stripped) < 30 or stripped in ("", "[]", "{}", "---", "null", "~"):
                return {"success": False,
                        "result": (f"⚠️ {path} è praticamente vuoto "
                                   f"({len(stripped)} char, contenuto: {stripped[:60]!r}). "
                                   f"NON modifico per non inventare contenuto. "
                                   f"Verifica il path: forse devi usare '/config/automations.yaml' "
                                   f"(path assoluto) o le tue automazioni sono in /config/automations/ "
                                   f"(cartella) o gestite dalla UI di Home Assistant "
                                   f"(in tal caso non sono in un file YAML).")}

            # ── GUARD 2: i nomi citati devono esistere nel file ──────────────
            # Se l'istruzione cita un nome SPECIFICO tra virgolette
            # (es. "Accendi luce Mario alle 23"), quel nome DEVE comparire nel
            # file. Altrimenti l'AI tenderebbe a INVENTARE l'oggetto richiesto.
            # Per le quote singole '...' siamo restrittivi (apostrofi italiani).
            quoted_refs = []
            for m in _re.finditer(r'"([^"]{5,})"|«([^»]{5,})»|“([^”]{5,})”', instruction):
                ref = next((g for g in m.groups() if g), "")
                if ref:
                    quoted_refs.append(ref)
            for m in _re.finditer(r"(?:^|\s)'([^']{5,})'(?=\s|[,.;!?]|$)", instruction):
                ref = m.group(1)
                if ref:
                    quoted_refs.append(ref)

            if quoted_refs:
                orig_low = original.lower()
                missing = [q for q in quoted_refs if q.lower() not in orig_low]
                if len(missing) == len(quoted_refs):
                    return {"success": False,
                            "result": (f"⚠️ Nessuno dei riferimenti specifici dell'istruzione "
                                       f"({', '.join(repr(q) for q in quoted_refs[:3])}) è stato "
                                       f"trovato in {path} (file ha {len(original)} char / "
                                       f"{len(original.splitlines())} righe). NON modifico per non "
                                       f"inventare contenuto. Possibili cause: path errato (usa "
                                       f"'/config/automations.yaml' invece di 'automations.yaml'), "
                                       f"automazione gestita dalla UI HA (non in YAML), o nome "
                                       f"diverso da quello citato.")}

            # ── ESTRAZIONE CONTESTO RILEVANTE ────────────────────────────────
            # Anche per file piccoli passiamo dalla modalità patch (sicura),
            # ma usiamo l'intero file come "contesto" se sta nei 6000 char.
            lines = original.splitlines()
            MAX_CTX = 6000

            if len(original) <= MAX_CTX:
                # File piccolo: passa intero file numerato come contesto
                context_text = "\n".join(f"{i+1:>5}: {ln}" for i, ln in enumerate(lines))
                keywords_used = ["(file intero)"]
            else:
                # File grande: estrai keyword dall'istruzione e seleziona
                # finestre rilevanti
                STOP_IT = {"cambia","cambiare","modifica","modificare","sostituisci",
                           "sostituire","aggiorna","aggiornare","correggi","correggere",
                           "rinomina","rinominare","nell","nella","nello","della","dello",
                           "delle","degli","dell","con","per","alla","alle","allo","agli",
                           "che","del","dei","sul","sui","sulla","sulle","una","uno","gli",
                           "ora","orario","tempo","valore","file","automazione","automazioni",
                           "trigger","istruzione","chiamata","chiamato"}
                STOP_EN = {"change","modify","edit","update","replace","fix","rename",
                           "the","that","this","with","from","into","value","time","file",
                           "called","named"}
                STOPWORDS = STOP_IT | STOP_EN

                instruction_flat = _re.sub(r'["\'«»“”]', " ", instruction)
                tokens = _re.findall(
                    r'[A-Za-zÀ-ÿ_][A-Za-zÀ-ÿ0-9_]{2,}|\d{1,4}:\d{2}(?::\d{2})?|\d{3,5}',
                    instruction_flat
                )
                keywords = []
                for t in tokens:
                    tk = t.lower()
                    if not tk or tk in STOPWORDS:
                        continue
                    if tk not in keywords:
                        keywords.append(tk)

                # TF-IDF: scarta keyword che matchano > 30% delle righe
                if keywords:
                    n_lines = max(len(lines), 1)
                    kw_doc_freq = {kw: sum(1 for ln in lines if kw in ln.lower())
                                   for kw in keywords}
                    useful = [kw for kw in keywords
                              if 0 < kw_doc_freq[kw] / n_lines < 0.3]
                    if not useful:
                        candidate = sorted(
                            [(kw, kw_doc_freq[kw]) for kw in keywords if kw_doc_freq[kw] > 0],
                            key=lambda x: x[1]
                        )
                        useful = [kw for kw, _ in candidate[:5]]
                    keywords = useful
                keywords_used = list(keywords)

                # Trova righe con score (numero keyword distinte matchate)
                hit_scored = []
                for i, ln in enumerate(lines):
                    ln_low = ln.lower()
                    score = sum(1 for kw in keywords if kw in ln_low)
                    if score > 0:
                        hit_scored.append((i, score))
                if len(hit_scored) > 120:
                    hit_scored.sort(key=lambda x: (-x[1], x[0]))
                    hit_scored = sorted(hit_scored[:80], key=lambda x: x[0])
                hit_idx = {i for i, _ in hit_scored}

                if not hit_idx:
                    # Nessun match → mostra solo le prime 200 righe come fallback
                    context_text = "\n".join(
                        f"{i+1:>5}: {ln}" for i, ln in enumerate(lines[:200])
                    )
                else:
                    # Costruisci finestre indipendenti (non si fondono se hit
                    # distanti più di MIN_GAP righe)
                    WINDOW = 15
                    MIN_GAP = 10
                    ranges = []
                    prev_hit = None
                    for i in sorted(hit_idx):
                        if prev_hit is not None and (i - prev_hit) <= MIN_GAP:
                            ranges[-1] = (ranges[-1][0], min(len(lines) - 1, i + WINDOW))
                        else:
                            a = max(0, i - WINDOW)
                            b = min(len(lines) - 1, i + WINDOW)
                            ranges.append((a, b))
                        prev_hit = i

                    # Score per finestra: max_score (riga più ricca) + sum_score
                    score_by_line = {idx: s for idx, s in hit_scored}
                    ranges_scored = []
                    for a, b in ranges:
                        scores = [score_by_line.get(n, 0) for n in range(a, b + 1)]
                        ranges_scored.append((max(scores) if scores else 0,
                                              sum(scores), a, b))
                    ranges_scored.sort(key=lambda x: (-x[0], -x[1], x[2]))

                    # Selezione greedy entro budget MAX_CTX
                    selected = []
                    total = 0
                    for _max_s, _sum_s, a, b in ranges_scored:
                        marker_overhead = len(f"# righe {a+1}-{b+1}\n") + 2
                        block_lines = []
                        block_size = marker_overhead
                        for n in range(a, b + 1):
                            ln_text = f"{n+1:>5}: {lines[n]}"
                            if total + block_size + len(ln_text) + 1 > MAX_CTX:
                                break
                            block_lines.append(ln_text)
                            block_size += len(ln_text) + 1
                        if block_lines:
                            selected.append((a, a + len(block_lines) - 1, "\n".join(block_lines)))
                            total += block_size
                        if total >= MAX_CTX:
                            break
                    selected.sort(key=lambda x: x[0])
                    snippets = [f"# righe {a+1}-{b+1}\n{txt}" for a, b, txt in selected]
                    context_text = "\n\n".join(snippets)

            # ── PROMPT PATCH ─────────────────────────────────────────────────
            patch_sys = (
                "Sei un assistente che produce PATCH precisi su file di testo.\n\n"
                "Ti vengono dati: (1) il NOME del file, (2) FRAMMENTI rilevanti "
                "del file (con numero di riga), (3) un'ISTRUZIONE di modifica.\n\n"
                "Devi rispondere SOLO con un JSON valido del tipo:\n"
                '  {"edits":[{"old":"...","new":"..."}, ...]}\n\n'
                "REGOLE FERREE:\n"
                "1. Ogni 'old' deve essere una stringa LETTERALE che appare ESATTAMENTE "
                "una volta nel file (copiala esatta dai frammenti, comprese indentazioni e "
                "newline). Includi abbastanza contesto da renderla unica.\n"
                "2. NON includere il prefisso del numero di riga (es. '   42: ') in 'old' "
                "o 'new'. Quel prefisso è solo visualizzazione, NON è parte del file.\n"
                "3. 'new' è la stringa che sostituirà 'old'. Cambia SOLO ciò che richiede "
                "l'istruzione, lascia tutto il resto identico.\n"
                "4. Usa il MINIMO numero di edits possibile.\n"
                "5. NON inventare contenuto non presente nei frammenti. Se serve qualcosa "
                "che non vedi, restituisci edits vuoto con error.\n"
                "6. Se l'istruzione è ambigua o non trovi il punto giusto, restituisci "
                '{"edits":[],"error":"motivo breve"}.\n'
                "7. Rispondi SOLO con il JSON, niente markdown fence, niente spiegazioni."
            )
            patch_usr = (
                f"FILE: {path}\n"
                f"RIGHE TOTALI: {len(lines)}\n\n"
                f"=== FRAMMENTI ===\n{context_text}\n=== FINE FRAMMENTI ===\n\n"
                f"ISTRUZIONE: {instruction}\n\n"
                f"Rispondi con il JSON degli edits."
            )
            raw = await ai_cb(patch_sys, patch_usr, None)
            if not raw:
                return {"success": False, "result": "AI non ha risposto"}

            # Pulisci eventuali fence markdown
            raw = _re.sub(r"^```(?:json)?\s*\n?", "", raw.strip())
            raw = _re.sub(r"\n?```\s*$", "", raw).strip()

            try:
                parsed = _json.loads(raw)
            except Exception as e:
                m = _re.search(r"\{.*\}", raw, _re.DOTALL)
                if not m:
                    return {"success": False,
                            "result": f"AI non ha restituito JSON valido: {str(e)[:120]}. "
                                      f"Risposta: {raw[:200]!r}"}
                try:
                    parsed = _json.loads(m.group(0))
                except Exception as e2:
                    return {"success": False,
                            "result": f"AI JSON non parsabile: {str(e2)[:120]}"}

            if parsed.get("error") and not parsed.get("edits"):
                return {"success": False,
                        "result": f"AI non ha trovato il punto: {parsed['error'][:200]}"}

            edits = parsed.get("edits") or []
            if not edits:
                return {"success": False,
                        "result": "AI non ha proposto nessuna modifica (lista edits vuota)"}

            # ── APPLICA EDITS con validazione robusta ────────────────────────
            modified = original
            applied = []
            for idx, ed in enumerate(edits, 1):
                old = ed.get("old", "")
                new = ed.get("new", "")
                if not old:
                    return {"success": False,
                            "result": f"Edit #{idx}: 'old' vuoto, abortito"}

                # Difesa: l'AI a volte include comunque il prefisso "  N: ".
                # Se 'old' inizia con un pattern stile " 42: " e quella forma
                # non esiste nel file ma la versione senza prefisso sì,
                # rimuovi il prefisso da ogni riga di old e new.
                if modified.count(old) == 0:
                    cleaned_old = _re.sub(r"(?m)^\s*\d+:\s?", "", old)
                    cleaned_new = _re.sub(r"(?m)^\s*\d+:\s?", "", new)
                    if cleaned_old != old and modified.count(cleaned_old) >= 1:
                        old, new = cleaned_old, cleaned_new

                count = modified.count(old)
                if count == 0:
                    return {"success": False,
                            "result": (f"Edit #{idx}: 'old' non trovato nel file. "
                                       f"AI ha proposto: {old[:120]!r}. "
                                       f"File NON modificato.")}
                if count > 1:
                    return {"success": False,
                            "result": (f"Edit #{idx}: 'old' compare {count} volte nel file "
                                       f"(deve essere unico). Stringa: {old[:120]!r}. "
                                       f"File NON modificato.")}
                if old == new:
                    continue
                modified = modified.replace(old, new, 1)
                applied.append((old, new))

            if not applied:
                return {"success": False,
                        "result": "Nessuna modifica applicata (old == new in tutti gli edits)"}

            # ── GUARD ANTI-DRIFT: verifica che la differenza sia "ragionevole" ─
            # Se il file modificato differisce drasticamente dall'originale
            # senza giustificazione, rifiuta. È un controllo di sanità sul
            # caso patologico in cui l'AI propone edit con 'new' enorme.
            orig_n = len(original)
            mod_n = len(modified)
            delta = abs(mod_n - orig_n)
            # Tolleranza: 30% del file o 200 char, qualsiasi sia maggiore
            tolerance = max(int(orig_n * 0.3), 200)
            if delta > tolerance:
                return {"success": False,
                        "result": (f"⚠️ Differenza file inattesa: "
                                   f"{orig_n} char → {mod_n} char (Δ={delta}, "
                                   f"tolleranza={tolerance}). Patch rifiutato per "
                                   f"prevenire corruzione del file.")}

            # ── BACKUP automatico prima di scrivere ──────────────────────────
            # Salviamo i backup in una cartella centralizzata
            # /config/homemind_patches/backups/ per consultazione facile e
            # per non lasciare file .bak.* sparsi accanto agli originali.
            backup_info = ""
            try:
                from pathlib import Path as _Path
                target_p = _tools._safe_path(path)
                backup_dir = _Path("/config/homemind_patches/backups")
                backup_dir.mkdir(parents=True, exist_ok=True)
                # Nome backup: <relpath_safe>.<timestamp>.bak
                # Sostituisci '/' con '__' per non creare sottocartelle
                try:
                    rel = target_p.relative_to(_Path("/config"))
                    rel_str = str(rel).replace("/", "__")
                except ValueError:
                    rel_str = target_p.name
                bak_filename = f"{rel_str}.{int(_time.time())}.bak"
                bak_path = backup_dir / bak_filename
                bak_path.write_text(original, encoding="utf-8")
                backup_info = f" 💾 Backup: homemind_patches/backups/{bak_filename}"
            except Exception as _be:
                backup_info = f" ⚠️ Backup fallito: {str(_be)[:80]}"

            # ── SCRITTURA FILE ──────────────────────────────────────────────
            r_write = _tools.tool_scrittura(path, modified)
            if not r_write["success"]:
                return r_write

            summary = ", ".join(
                f"{(o[:25] + '…') if len(o) > 25 else o!r} → "
                f"{(n[:25] + '…') if len(n) > 25 else n!r}"
                for o, n in applied
            )
            orig_lines_count = len(original.splitlines())
            new_lines_count = len(modified.splitlines())
            return {"success": True,
                    "result": (f"✅ {path} modificato con patch: {len(applied)} edit. "
                               f"Righe: {orig_lines_count}→{new_lines_count}, "
                               f"Char: {orig_n}→{mod_n}.{backup_info} {summary[:250]}")}

        # ── read_and_summarize ────────────────────────────────────────────────
        if tool == "read_and_summarize":
            path   = args.get("path", "")
            prompt = args.get("prompt", "Riassumi questo documento in italiano.")
            if not path:
                return {"success": False, "result": "args: {path} richiesto"}
            r = _tools.tool_lettura(path)
            if not r.get("success"):
                return {"success": False, "result": r.get("message", "")}
            content_text = r.get("content", "")
            ai_cb = context.get("ai_cb")
            if ai_cb and content_text:
                _sys = "Sei un assistente preciso. Rispondi in italiano. Sii conciso ma completo."
                summary = await ai_cb(
                    _sys,
                    f"{prompt}\n\nContenuto:\n{content_text[:8000]}",
                    None
                )
                return {"success": True, "result": summary or content_text[:3000], "path": path}
            return {"success": True, "result": content_text[:3000], "path": path}

        # ── download_and_read ─────────────────────────────────────────────────
        if tool == "download_and_read":
            url       = args.get("url", "")
            dest      = args.get("dest", "ago/download_temp")
            summarize = args.get("summarize", False)
            if not url:
                return {"success": False, "result": "args: {url} richiesto"}
            rd = await _tools.tool_download(url, dest)
            if not rd.get("success"):
                return rd
            saved_path = rd.get("path", dest)
            rr = _tools.tool_lettura(saved_path)
            content_text = rr.get("content", "")[:10000]
            if summarize and context.get("ai_cb"):
                _sys = "Sei un assistente preciso. Rispondi in italiano."
                summary = await context["ai_cb"](
                    _sys,
                    f"Riassumi questo documento in italiano:\n\n{content_text[:8000]}",
                    None
                )
                return {"success": True, "result": summary, "downloaded_to": saved_path}
            return {"success": True, "result": content_text, "downloaded_to": saved_path}

        # ── shell_exec ────────────────────────────────────────────────────────
        if tool == "shell_exec":
            command = args.get("command", "")
            intent  = args.get("intent", "")
            cwd     = args.get("cwd", "/config")
            r = await _tools.tool_shell_exec(command, cwd=cwd, intent=intent)
            output = ""
            if r.get("stdout"):
                output += f"STDOUT:\n{r['stdout'][:2500]}\n"
            if r.get("stderr"):
                output += f"STDERR:\n{r['stderr'][:1500]}\n"
            output += f"RC={r.get('rc','?')}"
            return {"success": r.get("success", False),
                    "result": f"{r.get('message','')}\n{output}", "data": r}

        # ── shell_natural ─────────────────────────────────────────────────────
        if tool == "shell_natural":
            request = args.get("request", "")
            if not request:
                return {"success": False, "result": "args.request richiesto"}
            ai_cb = context.get("ai_cb")
            r = await _tools.tool_natural_shell(request, ai_cb=ai_cb)
            output = f"Comando: {r.get('command','?')}\n"
            if r.get("from_memory"):
                output = "🧠 (da memoria) " + output
            if r.get("stdout"):
                output += f"\nSTDOUT:\n{r['stdout'][:2500]}\n"
            if r.get("stderr") and not r.get("success"):
                output += f"\nSTDERR:\n{r['stderr'][:1000]}"
            if r.get("package_missing") and r.get("install_suggestion"):
                pkg = r["install_suggestion"].replace("apk add ", "").strip().split()[0]
                if pkg in _tools._INSTALLABLE_PACKAGES:
                    install_r = await _tools.tool_install_package(pkg)
                    if install_r.get("success"):
                        retry_r = await _tools.tool_natural_shell(request, ai_cb=ai_cb)
                        if retry_r.get("success"):
                            output = (f"📦 Auto-installato: {pkg}\nComando: {retry_r.get('command','?')}\n")
                            if retry_r.get("stdout"):
                                output += f"\nSTDOUT:\n{retry_r['stdout'][:2500]}\n"
                            return {"success": True, "result": f"✅ Eseguito dopo installazione\n{output}", "data": retry_r}
            return {"success": r.get("success", False),
                    "result": f"{r.get('message','')}\n{output}", "data": r}

        # ── install_package ───────────────────────────────────────────────────
        if tool == "install_package":
            pkg = args.get("package", "")
            if not pkg:
                return {"success": False, "result": "args.package richiesto"}
            r = await _tools.tool_install_package(pkg)
            return {"success": r.get("success", False), "result": r.get("message", ""), "data": r}

        # ── ha_system_info ────────────────────────────────────────────────────
        if tool == "ha_system_info":
            ha_term = context.get("ha_terminal")
            if not ha_term:
                return {"success": False, "result": "HATerminal non disponibile"}
            r = await ha_term.host_resources()
            if not r.get("success"):
                return {"success": False, "result": r.get("message","?")}
            from ha_terminal import HATerminal as _HAT
            return {"success": True, "result": _HAT.format_resources(r["data"]), "data": r["data"]}

        # ── ha_addons_list ────────────────────────────────────────────────────
        if tool == "ha_addons_list":
            ha_term = context.get("ha_terminal")
            if not ha_term:
                return {"success": False, "result": "HATerminal non disponibile"}
            r = await ha_term.addons_list()
            if not r.get("success"):
                return {"success": False, "result": r.get("message","?")}
            from ha_terminal import HATerminal as _HAT
            return {"success": True, "result": _HAT.format_addons(r["data"]), "data": r["data"]}

        # ── ha_addon_stats ────────────────────────────────────────────────────
        if tool == "ha_addon_stats":
            ha_term = context.get("ha_terminal")
            if not ha_term:
                return {"success": False, "result": "HATerminal non disponibile"}
            slug = args.get("slug", "")
            if not slug:
                return {"success": False, "result": "args.slug richiesto"}
            r = await ha_term.addon_stats(slug)
            if not r.get("success"):
                return {"success": False, "result": r.get("message","?")}
            data = r["data"]
            cpu = data.get("cpu_percent", 0)
            mem = data.get("memory_percent", 0)
            mem_mb = data.get("memory_usage", 0) / (1024**2)
            return {"success": True,
                    "result": f"📊 Addon {slug}: CPU={cpu:.1f}% RAM={mem:.1f}% ({mem_mb:.0f}MB)", "data": data}

        # ── ha_call_service ───────────────────────────────────────────────────
        if tool == "ha_call_service":
            ha_term = context.get("ha_terminal")
            rest    = context.get("rest_client")
            domain  = args.get("domain", "")
            service = args.get("service", "")
            data    = args.get("data", {})
            if not domain or not service:
                return {"success": False, "result": "args: {domain, service} richiesti"}

            # ── Gate conferma per operazioni pericolose ───────────────────────
            _DANGEROUS = {
                # Addon
                "hassio": {"addon_stop", "addon_restart", "addon_uninstall",
                           "addon_update", "host_reboot", "host_shutdown"},
                # HA core
                "homeassistant": {"stop", "restart", "check_config"},
                # Automazioni/script distruttivi
                "automation": {"delete"},
                "script":     {"delete"},
            }
            _needs_confirm = service in _DANGEROUS.get(domain, set())

            # Controlla anche le regole utente per conferma esplicita
            if not _needs_confirm:
                try:
                    _rp = Path("/config/homemind_patches/regole.md")
                    if _rp.exists():
                        _rtxt = _rp.read_text(encoding="utf-8").lower()
                        _kw = ("chiedi conferma", "ask confirm", "conferma prima")
                        if any(k in _rtxt for k in _kw):
                            # La regola chiede conferma generica — applica ai servizi che modificano
                            _MODIFYING = {"turn_off", "turn_on", "toggle", "set_temperature",
                                          "lock", "unlock", "open", "close", "stop", "start"}
                            if service in _MODIFYING or domain in ("hassio", "homeassistant"):
                                _needs_confirm = True
                except Exception:
                    pass

            if _needs_confirm:
                # Restituisce una richiesta di conferma invece di eseguire
                _svc_str = f"{domain}.{service}"
                _data_str = f"\nDati: `{data}`" if data else ""
                return {
                    "success":        False,
                    "needs_confirm":  True,
                    "confirm_action": {"domain": domain, "service": service, "data": data},
                    "result": (
                        f"⚠️ <b>Conferma richiesta</b>\n\n"
                        f"Sto per eseguire: <code>{_svc_str}</code>{_data_str}\n\n"
                        f"Rispondi <b>sì</b> per confermare o <b>no</b> per annullare."
                    ),
                }

            try:
                if rest:
                    await rest.call_service(domain, service, data)
                    return {"success": True, "result": f"✅ {domain}.{service} chiamato"}
                if domain == "shell_command" and ha_term:
                    r = await ha_term.call_shell_command(service, data)
                    return {"success": r.get("success", False), "result": r.get("message", "")}
                return {"success": False, "result": "Nessun client disponibile"}
            except Exception as e:
                return {"success": False, "result": f"Errore: {str(e)[:200]}"}

        # ── ha_natural ────────────────────────────────────────────────────────
        if tool == "ha_natural":
            ha_term = context.get("ha_terminal")
            ai_cb   = context.get("ai_cb")
            if not ha_term:
                return {"success": False, "result": "HATerminal non disponibile"}
            req = args.get("request", "")
            if not req:
                return {"success": False, "result": "args.request richiesto"}
            r = await ha_term.run_natural(req, ai_cb=ai_cb)
            return {"success": r.get("success", False),
                    "result": f"[canale={r.get('channel','?')}]\n{r.get('result','')}", "data": r}

        # ── finish ────────────────────────────────────────────────────────────
        # Il loop esterno gestisce 'finish' come segnale di fine task (vedi
        # poco sotto). Ma se l'AI lo chiama da DENTRO un plan/parallel_steps,
        # arriva qui come tool normale: lo trasformiamo in un no-op di successo
        # con il messaggio passato come 'data', così non diventa un errore.
        if tool == "finish":
            msg = (args.get("message") or args.get("text") or
                   args.get("summary") or "Task completato.")
            return {"success": True, "result": msg, "data": msg}

        # ── ha_list_users / ha_list_persons ───────────────────────────────────
        # Elenca le entità "person" registrate in HA. Sostituisce il servizio
        # "person/list_users" che NON esiste in HA e che le AI tendono a
        # inventare. Il nome del tool è generoso negli alias così le AI
        # possono chiamarlo in vari modi senza fallire.
        if tool in ("ha_list_users", "ha_list_persons", "list_users",
                    "list_persons", "ha_users", "ha_persons"):
            rest = context.get("rest_client")
            if not rest:
                return {"success": False, "result": "REST client non disponibile"}
            try:
                states = await rest.get_states()
            except Exception as e:
                return {"success": False, "result": f"Errore get_states: {str(e)[:200]}"}
            persons = [s for s in states
                       if isinstance(s, dict)
                       and s.get("entity_id", "").startswith("person.")]
            if not persons:
                return {"success": True,
                        "result": "Nessuna entità person.* registrata in Home Assistant.",
                        "data": []}
            lines = []
            data = []
            for p in persons:
                eid = p.get("entity_id", "")
                attrs = p.get("attributes", {}) or {}
                name = attrs.get("friendly_name") or eid.replace("person.", "").title()
                state = p.get("state", "?")
                lines.append(f"- {name} ({eid}) — stato: {state}")
                data.append({"entity_id": eid, "name": name, "state": state,
                             "user_id": attrs.get("user_id")})
            txt = "Utenti registrati in Home Assistant:\n" + "\n".join(lines)
            return {"success": True, "result": txt, "data": data}

        # ── archive (crea .tar.gz) ────────────────────────────────────────────
        if tool in ("archive", "create_tar", "tar"):
            source = (args.get("source") or args.get("src") or
                      args.get("path") or args.get("input") or "")
            output = (args.get("output") or args.get("dest") or
                      args.get("destination") or args.get("out") or "")
            if not source:
                return {"success": False, "result": "args: {source} richiesto"}
            r = _tools.tool_create_tar_python(source, output)
            return {"success": r["success"], "result": r["message"],
                    "data": {"path": r.get("path", "")}}

        # ── create_zip ────────────────────────────────────────────────────────
        if tool in ("create_zip", "zip"):
            source = (args.get("source") or args.get("src") or
                      args.get("path") or args.get("input") or "")
            output = (args.get("output") or args.get("dest") or
                      args.get("destination") or args.get("out") or "")
            if not source:
                return {"success": False, "result": "args: {source} richiesto"}
            try:
                import zipfile as _zf
                from pathlib import Path as _P2
                src2 = (_P2("/config") / source).resolve()
                if not src2.exists():
                    return {"success": False, "result": f"❌ Sorgente non trovata: {source}"}
                out2 = (_P2("/config") / output).resolve() if output else src2.parent / (src2.name + ".zip")
                out2.parent.mkdir(parents=True, exist_ok=True)
                with _zf.ZipFile(str(out2), "w", _zf.ZIP_DEFLATED) as zf:
                    if src2.is_dir():
                        for fp in src2.rglob("*"):
                            zf.write(fp, fp.relative_to(src2.parent))
                    else:
                        zf.write(src2, src2.name)
                size_mb = out2.stat().st_size / (1024 * 1024)
                rel = str(out2).replace("/config/", "", 1)
                return {"success": True,
                        "result": f"✅ ZIP creato: {rel} ({size_mb:.1f} MB)",
                        "data": {"path": rel}}
            except Exception as e:
                return {"success": False, "result": f"❌ Errore ZIP: {str(e)[:200]}"}

        # ── json/parse — tool inventato dall'AI per leggere/parsare JSON ─────
        if tool in ("json", "parse", "parse_json"):
            fpath = args.get("path", "") or args.get("file", "")
            if fpath:
                return await execute_tool("read", {"path": fpath}, context)
            return {"success": False, "result": "Tool 'json': specifica args.path"}

        return {"success": False, "result": f"Tool sconosciuto: '{tool}'. Usa solo i tool elencati nel prompt."}

    except Exception as e:
        logger.exception(f"execute_tool {tool}")
        return {"success": False, "result": f"Eccezione in {tool}: {str(e)[:200]}"}


# ════════════════════════════════════════════════════════════════════════
# JSON EXTRACTOR
# ════════════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> dict:
    """Estrae il primo blocco JSON valido dalla risposta AI."""
    if not text:
        return None
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = text.replace('```', '').strip()
    depth = 0
    start = -1
    for i, c in enumerate(text):
        if c == '{':
            if depth == 0:
                start = i
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and start != -1:
                blob = text[start:i+1]
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    continue
    return None


# ════════════════════════════════════════════════════════════════════════
# PRE-PLANNING
# ════════════════════════════════════════════════════════════════════════


def _try_auto_memory(history: list, user_request: str):
    """Memorizza comandi shell riusciti per riuso futuro."""
    try:
        for step in history:
            tool = step.get("tool")
            if tool not in ("shell_natural", "shell_exec"):
                continue
            if not step.get("success"):
                continue
            data = step.get("data") or {}
            command = data.get("command") or step.get("args", {}).get("command", "")
            if not command:
                continue
            intent = (
                step.get("args", {}).get("request")
                or step.get("args", {}).get("intent")
                or user_request
            )
            _tools.remember_command(intent, command, success=True)
    except Exception as e:
        logger.warning("_try_auto_memory: %s", e)


PLANNING_PROMPT = """
Sei un pianificatore di task per un assistente domotica.

Analizza la richiesta utente e rispondi SOLO con JSON valido (nessun testo fuori):
{
  "is_multi_step": true/false,
  "steps_count": N,
  "plan_summary": "descrizione breve",
  "plan_steps": [
    {"tool": "...", "args": {...}, "label": "emoji + descrizione"},
    ...
  ]
}


════════ QUANDO LASCIARE plan_steps VUOTO (loop adattivo) ════════
⚠️ Rispondi con "plan_steps":[] per questi task — l'agente adattivo li gestisce meglio:

❌ NON PIANIFICARE MAI:
- Task di ricerca/interrogazione HA: "utenti", "entità", "ram", "cpu", "stati",
  "chi è connesso", "automazioni", "log", "errori", "mostrami X in HA"
- Task dove il path del file non è esplicitamente fornito dall'utente
- Task con verbi: "mostrami", "dimmi", "elenca", "quanti", "chi", "qual è",
  "controlla", "verifica", "cerca", "trova" — salvo path esplicito noto
- Qualsiasi ha_natural, ha_system_info, list_entities, shell_natural esplorativo

✅ PIANIFICA SOLO per questi pattern (usa 1 step quando possibile):

❶❶ MODIFICA FILE (YAML/JSON/testo) → 1 SOLO STEP ai_edit_file:
   'modifica/cambia/aggiorna X nel file Y'
   → {"steps":[{"tool":"ai_edit_file","args":{"path":"/config/automations.yaml",
      "instruction":"cambia orario automazione Accendi Luce Mario da 22:00 a 13:00"},"label":"✏️ Modifica"}]}
   ⚠️ NON aggiungere step read() prima o validate dopo. ai_edit_file è autosufficiente.

════════ MAPPA PATTERN → TOOL (segui ESATTAMENTE) ════════

❶ "scarica/clona [URL_GITHUB] [DEST] scrivi/genera riassunto [FILE_OUTPUT]"
   → 1 SOLO step: clone_and_summarize
   Args OBBLIGATORI: repo=URL, dest=DEST, output=FILE_OUTPUT, prompt=istruzione_utente
   ⛔ NON usare: clone + write separati, read_and_summarize, url/path come chiavi

   ESEMPIO ESATTO:
   Input: "scarica https://github.com/ago19800/HomeMind ago/progetti scrivi un riassunto breve di come installare ago/progetti/riassunto.md"
   {
     "is_multi_step": true, "steps_count": 1,
     "plan_summary": "Clona HomeMind e genera riassunto installazione",
     "plan_steps": [{
       "tool": "clone_and_summarize",
       "args": {
         "repo": "https://github.com/ago19800/HomeMind",
         "dest": "ago/progetti",
         "output": "ago/progetti/riassunto.md",
         "prompt": "scrivi un riassunto breve di come installare"
       },
       "label": "📥 Clono repo e scrivo riassunto.md"
     }]
   }

❷ "scarica [URL_GITHUB] [DEST] scrivi riassunto [FILE] mostrami [FILE]"
   → 2 step: clone_and_summarize + read
   [{tool:"clone_and_summarize", args:{repo:URL,dest:DEST,output:FILE,prompt:ISTRUZIONE}},
    {tool:"read", args:{path:FILE}}]

❸ "scarica/clona [URL_GITHUB] [DEST]" (senza riassunto)
   → 1 step: clone(repo=URL, dest=DEST)

❹ "leggi/mostra/apri [FILE]"
   → 1 step: read(path=FILE)

❺ "scarica [URL_NON_GITHUB] in [FILE]"
   → 1 step: download(url=URL, dest=FILE)

❻ operazioni indipendenti (leggi A e B, scarica X e Y contemporaneamente)
   → parallel_steps

════════ REGOLE CRITICHE ════════
⚠️ clone_and_summarize args: SEMPRE "repo" (mai "url"), SEMPRE "dest" (mai "path")
⚠️ "scrivi riassunto su file X" = output=X in clone_and_summarize, NON step write separato
⚠️ NON usare read_and_summarize per riassumere repo GitHub - usa clone_and_summarize
⚠️ Path relativi a /config: "ago/riassunto.md" non "/config/ago/riassunto.md"

❼ "crea archivio/comprimere [CARTELLA] in .tar.gz" → archive(source=CARTELLA, output=OUTPUT)
❽ "crea zip di [CARTELLA]" → create_zip(source=CARTELLA, output=OUTPUT)

══════ PATTERN MULTI-STEP CONCATENATI ══════
Quando la richiesta contiene PIÙ operazioni sequenziali distinte, pianifica TUTTI
gli step in un unico piano. Non fermarti al primo step.

ESEMPIO: "scarica X in dest / crea archivio / scrivi cosa hai fatto in file / leggi file"
→ 4 step in sequenza:
{
  "is_multi_step": true, "steps_count": 4,
  "plan_summary": "Clona repo, crea archivio, scrivi log, mostra risultato",
  "plan_steps": [
    {"tool":"clone","args":{"repo":"URL","dest":"ago/progetti"},"label":"📥 Clono repo"},
    {"tool":"archive","args":{"source":"ago/progetti/HomeMind","output":"ago/progetti/HomeMind.tar.gz"},"label":"🗜️ Creo archivio"},
    {"tool":"write","args":{"path":"ago/progetti/fatto.md","content":"## Cosa ho fatto\n- Clonato repo HomeMind in ago/progetti\n- Creato archivio HomeMind.tar.gz"},"label":"📝 Scrivo log"},
    {"tool":"read","args":{"path":"ago/progetti/fatto.md"},"label":"👁️ Leggo il file"}
  ]
}

REGOLE per piani multi-step:
- Includi SEMPRE tutti gli step richiesti — non fermarti a metà
- "scrivi cosa hai fatto" = tool write con content che descrive gli step precedenti
- "leggi FILE" come ultimo step = tool read per mostrare il risultato
- "scrivi riassunto installazione" → usa write con content generato dall'AI
- Gli step si eseguono in ordine, uno dopo l'altro
- Massimo 8 step in un piano (se ne servono di più, usa loop adattivo)

❾ "estrai/decomprimi [FILE.tar.gz] [in DEST]"
   → extract_tar(archive=FILE, dest=DEST)
   ⚠️ arg OBBLIGATORIO: "archive" (MAI "source"/"path"/"file"), "dest" facoltativo
   ESEMPIO: {"tool":"extract_tar","args":{"archive":"ago/progetti/HomeMind.tar.gz","dest":"ago/progetti"}}

❿ "estrai/decomprimi [FILE.zip] [in DEST]"
   → unzip_file(archive=FILE, dest=DEST)
   ⚠️ arg OBBLIGATORIO: "archive" (MAI "source"/"path"/"file"), "dest" facoltativo
   ESEMPIO: {"tool":"unzip_file","args":{"archive":"ago/file.zip","dest":"ago/progetti"}}
"""


async def _pre_plan(user_request: str, ai_cb) -> dict | None:
    """
    Fase 0: chiede all'AI di analizzare il task e proporre un piano.
    Ritorna il piano se ha plan_steps validi, None altrimenti.
    """
    try:
        # Inietta le regole utente nel contesto di pianificazione
        _user_rules = _load_user_rules_ae()
        _plan_request = (
            f"REGOLE UTENTE — rispettale sempre nella pianificazione:\n{_user_rules}\n\nRICHIESTA UTENTE:\n{user_request}"
            if _user_rules else
            f"RICHIESTA UTENTE:\n{user_request}"
        )
        response = await ai_cb(
            PLANNING_PROMPT,
            _plan_request,
            None
        )
        if not response:
            logger.warning("pre-plan: AI non ha risposto")
            return None
        logger.debug("pre-plan risposta AI: %s", response[:300])
        plan = _extract_json(response)
        if not plan:
            logger.warning("pre-plan: JSON non estratto. Risposta: %s", response[:400])
            return None
        # Usa il piano SOLO se contiene tool deterministici (non esplorativi)
        _DETERMINISTIC_TOOLS = {
            "clone", "clone_and_summarize", "download", "read", "write", "append",
            "mkdir", "move", "copy", "delete", "archive", "create_zip",
            "extract_tar", "unzip_file", "parallel_steps", "ai_generate",
            "ai_edit_file", "read_and_summarize", "fetch_url", "search_web",
            "download_and_read",  # alias comuni
        }
        _EXPLORATORY_TOOLS = {
            "shell_natural", "shell_exec", "ha_natural", "ha_system_info",
            "ha_addons_list", "ha_addon_stats", "ha_call_service", "list_entities",
            "ha_list_users", "ha_list_persons", "list_users", "list_persons",
            "ha_users", "ha_persons",
            "ha_natural", "ping", "portscan",
        }
        steps = plan.get("plan_steps", [])
        if steps:
            tools_used = {s.get("tool", "") for s in steps}
            # Rifiuta se usa tool esplorativi O tool sconosciuti/inventati
            has_exploratory = bool(tools_used & _EXPLORATORY_TOOLS)
            has_unknown = bool(tools_used - _DETERMINISTIC_TOOLS - _EXPLORATORY_TOOLS)
            if has_exploratory or has_unknown:
                logger.info("pre-plan SCARTATO (tool esplorativi/sconosciuti: %s) → loop classico", tools_used)
                return None
            # Se usa "read" su un path non menzionato esplicitamente nella richiesta → scarta
            req_lower = user_request.lower()
            for s in steps:
                if s.get("tool") == "read":
                    fpath = s.get("args", {}).get("path", "")
                    # Se il path non appare nella richiesta (neanche parzialmente) → AI ha inventato
                    fname = fpath.split("/")[-1].lower() if fpath else ""
                    if fname and fname not in req_lower and fpath.lower() not in req_lower:
                        logger.info("pre-plan SCARTATO (read su path inventato '%s') → loop classico", fpath)
                        return None
            logger.info("pre-plan OK: %d step, tools=%s - %s", len(steps),
                        tools_used, plan.get("plan_summary", ""))
            return plan
        logger.info("pre-plan: plan_steps vuoto → loop classico")
    except Exception as e:
        logger.warning("pre-plan fallito con eccezione: %s", e)
    return None


# ════════════════════════════════════════════════════════════════════════
# AGENT LOOP
# ════════════════════════════════════════════════════════════════════════

async def run_agent(user_request: str, context: dict,
                    progress_cb=None, max_steps: int = MAX_STEPS) -> dict:
    """
    Esegue il loop agentico con pre-planning.

    Flow:
      1. Pre-planning: analizza il task e propone un piano
      2. Se multi-step → esegue `plan` direttamente senza loop AI
      3. Se single-step → loop classico tool-by-tool

    Returns: {success, final_message, steps, stopped_reason}
    """
    ai_cb = context.get("ai_cb")
    if not ai_cb:
        return {"success": False, "final_message": "AI non disponibile",
                "steps": [], "stopped_reason": "no_ai"}

    # Inietta progress_cb nel context per tool composti
    context["_progress_cb"] = progress_cb

    # ── FASE 0: Pre-planning ─────────────────────────────────────────────────
    pre_plan = await _pre_plan(user_request, ai_cb)

    if pre_plan and pre_plan.get("plan_steps"):
        plan_summary = pre_plan.get("plan_summary", "")
        steps_list   = pre_plan["plan_steps"]
        n_steps      = len(steps_list)

        # Notifica piano all'utente
        if progress_cb:
            try:
                await progress_cb(
                    0, "plan", {"steps": steps_list},
                    f"📋 Piano: {plan_summary} ({n_steps} step)", None
                )
            except Exception:
                pass

        # Esegui il piano
        result = await execute_tool("plan", {"steps": steps_list}, context)

        history = [{"step": 0, "tool": "plan", "args": {"steps": steps_list},
                    "thought": plan_summary,
                    "result": result.get("result", "")[:MAX_TOOL_RESULT_LEN],
                    "success": result.get("success", False)}]

        # Auto-memory per shell commands
        _try_auto_memory(history, user_request)

        final_msg = result.get("result", "Task completato.")
        return {"success": result.get("success", False),
                "final_message": final_msg,
                "steps": history,
                "stopped_reason": "plan_executed"}

    # ── FASE 1: Loop classico tool-by-tool ───────────────────────────────────
    history = []
    history_text = ""

    for step in range(1, max_steps + 1):
        sys_prompt = TOOLS_DESCRIPTION
        usr_prompt = (
            f"TASK UTENTE:\n{user_request}\n\n"
            f"════ REGOLE ASSOLUTE — LEGGI PRIMA DI DECIDERE ════\n"
            f"1. FOCUS: esegui SOLO il task richiesto. NON fare operazioni extra non richieste.\n"
            f"2. PATH ASSOLUTI: usa /config/automations.yaml NON 'automations.yaml' da solo.\n"
            f"   Path relativi VALIDI: 'ago/file.md' (mappa su /config/ago/file.md).\n"
            f"3. TOOL REALI: usa SOLO i tool elencati nel prompt sistema. NON inventare tool.\n"
            f"4. STOP: appena il task è fatto usa 'finish'. NON aggiungere step extra.\n"
            f"5. ERRORE PATH: se fallisce per 'file not found' → correggi il path (aggiungi /config/).\n"
            f"6. ai_edit_file legge il file DA SOLO. NON fare read() prima. 1 step solo: ai_edit_file con path ASSOLUTO.\n"
            f"   Se fallisce 'riferimento non trovato' → usa shell_natural per cercare il testo esatto nel file.\n"
            f"7. NON clonare/mkdir/scaricare/eliminare se NON esplicitamente richiesto nel task.\n"
            f"════════════════════════════════════════════════════\n\n"
            f"CRONOLOGIA AZIONI:\n{history_text or '(nessuna ancora)'}\n\n"
            f"Decidi il prossimo tool. Rispondi SOLO con JSON:\n"
            f'{{"thought": "...", "tool": "...", "args": {{...}}}}'
        )

        ai_response = await ai_cb(sys_prompt, usr_prompt, None)
        if not ai_response:
            return {"success": False, "final_message": "AI non ha risposto",
                    "steps": history, "stopped_reason": "ai_silent"}

        decision = _extract_json(ai_response)
        if not decision or "tool" not in decision:
            if step < max_steps:
                history_text += (f"\n[STEP {step}] Risposta non JSON: {ai_response[:200]}")
                continue
            return {"success": False,
                    "final_message": f"AI non ha risposto in JSON:\n{ai_response[:500]}",
                    "steps": history, "stopped_reason": "no_json"}

        tool      = decision.get("tool")
        args      = decision.get("args", {}) or {}
        thought   = decision.get("thought", "")

        if progress_cb:
            try:
                await progress_cb(step, tool, args, thought, None)
            except Exception as e:
                logger.warning("progress_cb failed: %s", e)

        result = await execute_tool(tool, args, context)
        if result is None:  # sicurezza: execute_tool non dovrebbe mai restituire None
            result = {"success": False, "result": f"Tool '{tool}' ha restituito None"}
        history.append({
            "step": step, "tool": tool, "args": args,
            "thought": thought,
            "result": result.get("result", "")[:MAX_TOOL_RESULT_LEN],
            "success": result.get("success", False),
        })

        if progress_cb:
            try:
                await progress_cb(step, tool, args, thought, result)
            except Exception as e:
                logger.warning("progress_cb result failed: %s", e)

        history_text += (
            f"\n[STEP {step}] {thought}\n"
            f"  → tool: {tool}({json.dumps(args, ensure_ascii=False)[:200]})\n"
            f"  → risultato: {result.get('result','')[:500]}\n"
        )

        # ── Verifica finish ──────────────────────────────────────────────────
        if tool == "finish":
            _try_auto_memory(history, user_request)
            return {"success": True,
                    "final_message": result.get("data", "Task completato."),
                    "steps": history, "stopped_reason": "finish"}

        # ── Tronca cronologia se troppo lunga ─────────────────────────────────
        if len(history_text) > 12000:
            keep_steps = history[-3:]
            history_text = "\n".join(
                f"[STEP {h['step']}] {h['thought']}\n  tool: {h['tool']}\n  result: {h['result'][:300]}"
                for h in keep_steps
            )

    return {"success": False,
            "final_message": f"Limite di {max_steps} step raggiunto. Task non completato.",
            "steps": history, "stopped_reason": "max_steps"}
