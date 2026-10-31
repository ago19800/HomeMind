"""
file_create.py — «crea un file ago.txt con scritto ciao» (da Telegram, in linguaggio naturale).

Prima la richiesta arrivava all'AI della chat, che NON ha nessuno strumento per scrivere file ma rispondeva
lo stesso «Il file è stato salvato in …» (conferma inventata). Ora:
  1. parse()  riconosce la richiesta (nome con estensione, cartella e testo facoltativi);
  2. run()    crea DAVVERO il file con gli stessi strumenti e controlli dell'agente (/fai): percorsi solo sotto
              /config, file protetti esclusi, nessuna sovrascrittura silenziosa; poi verifica che esista;
  3. claims_file_saved() / has_file_intent() servono da rete di sicurezza: se l'AI risponde comunque
              «file creato» senza aver fatto nulla, la risposta viene sostituita da un avviso onesto.
"""

import html
import logging
import re
from typing import Optional

import tools_system as _tools

logger = logging.getLogger("homemind.file_create")

DEFAULT_DIR = "ago/progetti"          # cartella usata se non ne indichi una (è sempre scritta nella risposta)
MAX_CONTENT = 20000
_EXT = r"(?:md|txt|json|ya?ml|csv|log|ini|cfg|conf|py|sh|html?|xml|toml)"

_TRIGGER = re.compile(
    r"^\s*/?(?:crea(?:re)?|scrivi|genera|prepara|nuovo)\s+"
    r"(?:per\s+favore\s+|mi\s+)?"
    r"(?:(?:un|il|uno|lo|nuovo)\s+)*"
    r"(?:file\s+)?"
    r"(?:(?:chiamato|di\s+nome|denominato|con\s+nome)\s+)?"
    r"(?P<name>[\w\-./]+?\." + _EXT + r")(?=\s|$|[,;:])"
    r"(?P<rest>.*)$",
    re.I | re.S,
)
_CONTENT = re.compile(
    r"\b(?:con\s+(?:scritto|dentro|il\s+testo|il\s+contenuto|contenuto|testo)|con|contenente|che\s+contiene|"
    r"dentro|scrivendoci|scrivici|scrivendo)\b\s*[:\-–]?\s*",
    re.I,
)
_DIR = re.compile(r"\b(?:in|nella\s+cartella|nel\s+percorso)\s+(?:la\s+cartella\s+|cartella\s+)?(?P<dir>/?[\w\-./]+)", re.I)


def parse(text: str) -> Optional[dict]:
    """{'path', 'content'} oppure None se non è una richiesta di creazione file."""
    m = _TRIGGER.match(text or "")
    if not m:
        return None
    name = m.group("name").strip()
    rest = m.group("rest") or ""
    head, content = rest, ""
    cm = _CONTENT.search(rest)
    if cm:
        head, content = rest[:cm.start()], rest[cm.end():]
    content = content.strip().strip("“”\"'«»").strip()[:MAX_CONTENT]
    dm = _DIR.search(head)
    folder = dm.group("dir").strip() if dm else ""
    if folder.startswith("/config/"):
        folder = folder[len("/config/"):]
    folder = folder.strip("/")
    if folder and "/" not in name:
        path = f"{folder}/{name}"
    elif "/" in name:
        path = name
    else:
        path = f"{DEFAULT_DIR}/{name}"
    return {"path": path.lstrip("/") if not path.startswith("/config/") else path[len("/config/"):], "content": content}


def run(req: dict) -> str:
    """Crea il file e lo verifica. Ritorna il messaggio (HTML) da mandare all'utente: dice SOLO la verità."""
    path, content = req["path"], req["content"]
    shown = html.escape(path)
    try:
        r = _tools.tool_scrittura(path, content, overwrite=False)
    except Exception as e:                                   # mai fingere un successo
        logger.warning("file_create: errore: %s", e)
        return f"❌ Non sono riuscito a creare <code>{shown}</code>: {html.escape(str(e)[:150])}"
    if not r.get("success"):
        msg = str(r.get("message", ""))
        if "esistente" in msg:
            return (f"ℹ️ <code>{shown}</code> esiste già: non l'ho toccato.\n"
                    f"Per cambiarlo scrivi, ad esempio: <code>/fai aggiungi una riga a {shown}</code>")
        return f"❌ Non ho creato <code>{shown}</code>: {html.escape(msg[:200])}"
    try:                                                     # verifica reale sul disco
        real = _tools.CONFIG_DIR / r["path"]
        if not real.is_file():
            return f"❌ Il file <code>{shown}</code> non risulta sul disco: non è stato creato."
        size = real.stat().st_size
    except Exception as e:
        return f"❌ Non riesco a verificare <code>{shown}</code>: {html.escape(str(e)[:150])}"
    full = "/config/" + html.escape(str(r["path"]))
    body = f"✅ Creato <code>{full}</code> ({size} byte)" if size else f"✅ Creato <code>{full}</code> (file vuoto)"
    if content:
        prev = content if len(content) <= 200 else content[:200] + "…"
        body += f"\n<pre>{html.escape(prev)}</pre>"
    return body


# ── rete di sicurezza per la chat AI ────────────────────────────────────────
_INTENT = re.compile(r"\b(?:crea|creare|scrivi|genera|salva|prepara|fai)\b.*\b(?:file|documento|\.md|\.txt)\b", re.I | re.S)
_CLAIM = re.compile(
    r"(?:\bfile\b|\bdocumento\b|\.(?:md|txt|json|ya?ml|csv))[^.\n]{0,90}\b(?:cre|salv|scritt)(?:at[oai]|ato)\b"
    r"|\b(?:cre|salv|scritt)(?:at[oai])\b[^.\n]{0,50}\b(?:file|documento)\b"
    r"|\bho\s+(?:creato|salvato|scritto)\b",
    re.I,
)

NOT_CREATED_MSG = (
    "⚠️ <b>Non ho creato nessun file</b>: da questa chat non posso scrivere sul disco, "
    "e la conferma che stavo per darti sarebbe stata falsa.\n\n"
    "Per crearlo davvero scrivi, ad esempio:\n"
    "<code>crea file utente.md con scritto Ciao</code>\n"
    "<code>crea file note.txt in ago/documenti con scritto la spesa</code>\n"
    "oppure usa l'agente: <code>/fai crea il file ago/utente.md con …</code>"
)


def has_file_intent(user_msg: str) -> bool:
    return bool(_INTENT.search(user_msg or ""))


def claims_file_saved(reply: str) -> bool:
    return bool(_CLAIM.search(reply or ""))
