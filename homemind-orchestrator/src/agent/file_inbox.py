"""
agent/file_inbox.py — Salva in una cartella i file ricevuti su Telegram.

Uso (dalla chat con il bot): invii un file (documento, foto, video, audio…) con la
didascalia "invia nella cartella" / "salva in documenti" e HomeMind lo salva nella
cartella configurata nella pagina web (tab 📁 File), poi cancella il messaggio da Telegram.

Questo modulo contiene SOLO la logica (impostazioni, riconoscimento della didascalia,
nome file sicuro, salvataggio). Le chiamate Telegram stanno in telegram_bot.py.

Configurazione (person_config.json):
  "file_inbox": {
      "enabled": true,
      "delete_after": true,
      "folders": [
          {"name": "documenti", "path": "/share/documenti", "default": true},
          {"name": "foto",      "path": "/media/foto"}
      ]
  }
Il file viene riletto solo quando cambia (mtime): le modifiche valgono subito.

Sicurezza:
  • le cartelle si definiscono SOLO dalla pagina web, mai dalla chat;
  • un file esistente non viene MAI sovrascritto (si aggiunge " (1)", " (2)"…);
  • il nome file viene ripulito (niente percorsi, niente caratteri speciali);
  • cartelle di sistema (/etc, /proc, /usr, …) rifiutate;
  • scrittura "atomica" (file .part poi rinominato).
"""

import asyncio
import difflib
import json
import logging
import os
import re
import time
from pathlib import Path

logger = logging.getLogger("homemind.file_inbox")

CONFIG_PATH = Path("/config/homemind_patches/person_config.json")
MAX_BYTES = 20 * 1024 * 1024          # limite download dei bot Telegram (cloud API)

# verbi che, insieme al nome di una cartella, indicano "salva questo file"
_VERBS = re.compile(r"\b(salva|invia|manda|metti|carica|sposta|copia|save|send|upload|put)\b", re.I)
_FOLDER_WORD = re.compile(r"\b(cartella|folder|directory)\b", re.I)

# cartelle di sistema in cui non si scrive mai
_FORBIDDEN = ("/etc", "/proc", "/sys", "/dev", "/root", "/usr", "/bin", "/sbin",
              "/lib", "/lib64", "/boot", "/run")

_cache: dict = {"path": None, "mtime": None, "data": None}


# ── Impostazioni ──────────────────────────────────────────────────────────────

def load_settings(path: Path = CONFIG_PATH) -> dict:
    """{"enabled": bool, "delete_after": bool, "folders": [{name, path, default}]}.
    Rilegge il file solo se cambia. Mai eccezioni: in caso di problemi → funzione spenta."""
    path = Path(path)
    off = {"enabled": False, "delete_after": True, "folders": [], "switch_on": False}
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return off
    if _cache["path"] == str(path) and _cache["mtime"] == mtime and _cache["data"] is not None:
        return _cache["data"]
    result = off
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig")).get("file_inbox")
        if isinstance(raw, dict):
            folders = []
            for f in raw.get("folders") or []:
                if not isinstance(f, dict):
                    continue
                p = str(f.get("path", "")).strip()
                if not p:
                    continue
                name = str(f.get("name", "")).strip() or (p.rstrip("/").split("/")[-1] or "cartella")
                folders.append({"name": name, "path": p, "default": f.get("default") is True})
            result = {
                "enabled": raw.get("enabled") is True and bool(folders),
                "delete_after": raw.get("delete_after", True) is not False,
                "folders": folders,
                "switch_on": raw.get("enabled") is True,     # solo per messaggi diagnostici
            }
            logger.info("FileInbox: configurazione letta — interruttore=%s, cancella_dopo=%s, cartelle=%s",
                        "ON" if result["switch_on"] else "OFF", result["delete_after"],
                        ", ".join(f"{f['name']}→{f['path']}" for f in folders) or "nessuna")
    except Exception as e:
        logger.warning("FileInbox: lettura config fallita: %s", e)
    _cache.update({"path": str(path), "mtime": mtime, "data": result})
    return result


def default_index(folders: list):
    """Indice della cartella da usare quando la didascalia non ne nomina una:
    quella marcata "default", altrimenti l'unica configurata, altrimenti None (si chiede)."""
    for i, f in enumerate(folders):
        if f.get("default"):
            return i
    return 0 if len(folders) == 1 else None


# ── Riconoscimento della didascalia ───────────────────────────────────────────

_MAILISH = re.compile(r"\b(e-?mail|mail|posta|whatsapp|@)\b|@", re.I)
_PREP = r"(?<!\w)(?:in|nella|nel|nello|dentro|su|sulla|sul|to|into)\s+(?:la\s+|il\s+|lo\s+|l['’]|the\s+)?"
_AFTER_FOLDER = r"(?:cartella|folder|directory)\s+(?:di\s+|dei\s+|delle\s+|degli\s+|del\s+|della\s+|the\s+)?"


def _find_folder(cap: str, folders: list):
    """Indice della cartella nominata nella didascalia, SOLO se il nome è introdotto da
    una preposizione ("in documenti", "nella foto") o da "cartella" ("cartella foto").
    Un nome che compare per caso ("manda questa foto a Mario") non conta. Se più cartelle
    corrispondono, vince quella nominata per ultima ("…nella cartella documenti")."""
    best, best_end = None, -1
    for i, f in enumerate(folders):
        n = re.escape(f["name"].strip().lower())
        if not n:
            continue
        for pat in (_PREP + n + r"(?!\w)", _AFTER_FOLDER + n + r"(?!\w)"):
            m = re.search(pat, cap)
            if m and m.end() > best_end:
                best, best_end = i, m.end()
    if best is None:                                   # tolleranza agli errori di battitura
        best = _find_folder_fuzzy(cap, folders)
    return best


_PREP_WORDS = ("in", "nella", "nel", "nello", "dentro", "su", "sulla", "sul", "to", "into")


def _find_folder_fuzzy(cap: str, folders: list):
    """Come _find_folder ma tollera piccoli errori ("in documeti" → "documenti").
    Solo per nomi di almeno 4 lettere e dopo una preposizione; somiglianza ≥ 0.82."""
    words = re.findall(r"[^\s,.;:!?]+", cap)
    best, best_ratio = None, 0.0
    for i, f in enumerate(folders):
        name = f["name"].strip().lower()
        k = len(name.split())
        if len(name) < 4:
            continue
        for pos, w in enumerate(words):
            if w not in _PREP_WORDS:
                continue
            j = pos + 1
            while j < len(words) and words[j] in ("la", "il", "lo", "l", "the"):
                j += 1
            cand = " ".join(words[j:j + k])
            if not cand:
                continue
            r = difflib.SequenceMatcher(None, cand, name).ratio()
            if r >= 0.82 and r > best_ratio:
                best, best_ratio = i, r
    return best


def looks_like_save_request(caption: str) -> bool:
    """Didascalia che sembra una richiesta di salvataggio in cartella (anche senza cartelle
    configurate): serve solo per dare un messaggio utile quando la funzione è spenta."""
    cap = (caption or "").strip().lower()
    if not cap:
        return False
    if _FOLDER_WORD.search(cap):
        return True
    if _MAILISH.search(cap):
        return False
    if cap in ("salva", "save"):
        return True
    return _VERBS.search(cap) is not None and re.search(r"\b(in|nella|nel|nello|dentro|to|into)\b", cap) is not None


def detect_trigger(caption: str, folders: list):
    """(attivato, indice_cartella|None) dalla didascalia del file.
    Attiva se: nomina "cartella/folder"; oppure verbo (salva/invia…) + "in/nella <nome cartella>";
    oppure la didascalia è esattamente "salva"/"save" o esattamente il nome di una cartella.
    NON attiva: didascalie qualunque ("ecco la ricevuta") né frasi che parlano di email/posta
    senza nominare una cartella ("manda questa foto a Mario via email")."""
    cap = (caption or "").strip().lower()
    if not cap:
        return False, None
    for i, f in enumerate(folders):                       # didascalia = solo il nome cartella
        if cap == f["name"].strip().lower():
            return True, i
    folder_word = _FOLDER_WORD.search(cap) is not None
    if _MAILISH.search(cap) and not folder_word:
        return False, None
    idx = _find_folder(cap, folders)
    triggered = folder_word or (_VERBS.search(cap) is not None and idx is not None) or cap in ("salva", "save")
    return triggered, (idx if triggered else None)


# ── Estrazione del file dal messaggio Telegram ────────────────────────────────

def extract_media(msg: dict):
    """{"kind","file_id","file_name","mime","size"} oppure None se il messaggio non ha file."""
    if not isinstance(msg, dict):
        return None
    d = msg.get("document")
    if isinstance(d, dict) and d.get("file_id"):
        return {"kind": "document", "file_id": d["file_id"], "file_name": d.get("file_name") or "",
                "mime": d.get("mime_type") or "", "size": d.get("file_size") or 0}
    p = msg.get("photo")
    if isinstance(p, list) and p:
        best = sorted((x for x in p if isinstance(x, dict) and x.get("file_id")),
                      key=lambda x: (x.get("file_size") or 0, x.get("width") or 0))
        if best:
            b = best[-1]
            return {"kind": "photo", "file_id": b["file_id"], "file_name": "",
                    "mime": "image/jpeg", "size": b.get("file_size") or 0}
    for kind in ("video", "animation", "audio", "voice", "video_note"):
        v = msg.get(kind)
        if isinstance(v, dict) and v.get("file_id"):
            return {"kind": kind, "file_id": v["file_id"], "file_name": v.get("file_name") or "",
                    "mime": v.get("mime_type") or "", "size": v.get("file_size") or 0}
    return None


# ── Nome file sicuro ──────────────────────────────────────────────────────────

_EXT_BY_KIND = {"photo": ".jpg", "video": ".mp4", "animation": ".mp4", "audio": ".mp3",
                "voice": ".ogg", "video_note": ".mp4", "document": ".bin"}
_EXT_BY_MIME = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png",
                "image/webp": ".webp", "image/gif": ".gif", "video/mp4": ".mp4",
                "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "text/plain": ".txt",
                "application/zip": ".zip"}
_PREFIX = {"photo": "foto", "video": "video", "animation": "animazione", "audio": "audio",
           "voice": "vocale", "video_note": "video", "document": "file"}


def safe_filename(name: str, fallback: str) -> str:
    """Solo il nome (niente percorsi), senza caratteri speciali, max 120 caratteri."""
    n = str(name or "")
    n = n.replace("\\", "/").split("/")[-1]                       # niente cartelle
    n = re.sub(r'[\x00-\x1f<>:"|?*]', "_", n)                      # caratteri vietati
    n = re.sub(r"\s+", " ", n).strip().strip(".")                  # spazi/punti ai bordi
    if not n or n.startswith("."):
        return fallback
    if len(n) > 120:
        stem, ext = os.path.splitext(n)
        n = stem[: 120 - len(ext)] + ext
    return n


def choose_filename(media: dict, tg_path_name: str = "", mime: str = "", now_ts=None) -> str:
    """Nome da dare al file: quello originale se esiste, altrimenti foto_AAAAMMGG_HHMMSS.jpg ecc."""
    kind = media.get("kind", "document")
    ext = os.path.splitext(tg_path_name or "")[1].lower()
    if not ext:
        ext = _EXT_BY_MIME.get((mime or media.get("mime") or "").lower(), _EXT_BY_KIND.get(kind, ".bin"))
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now_ts or time.time()))
    fallback = f"{_PREFIX.get(kind, 'file')}_{stamp}{ext}"
    original = media.get("file_name") or ""
    return safe_filename(original, fallback) if original else fallback


# ── Salvataggio ───────────────────────────────────────────────────────────────

def unique_path(folder: Path, filename: str) -> Path:
    """folder/filename; se esiste già: "nome (1).ext", "nome (2).ext"… Mai sovrascrive."""
    dest = folder / filename
    if not dest.exists():
        return dest
    stem, ext = os.path.splitext(filename)
    for i in range(1, 1000):
        cand = folder / f"{stem} ({i}){ext}"
        if not cand.exists():
            return cand
    return folder / f"{stem}_{int(time.time())}{ext}"


def check_folder(folder_path: str) -> Path:
    """Valida il percorso configurato: assoluto, non una cartella di sistema. Ritorna il Path risolto."""
    raw = str(folder_path or "").strip()
    if not raw.startswith("/"):
        raise ValueError("il percorso deve essere assoluto (iniziare con /)")
    p = Path(raw).resolve()
    s = str(p)
    if s == "/" or any(s == bad or s.startswith(bad + "/") for bad in _FORBIDDEN):
        raise ValueError(f"cartella di sistema non consentita: {s}")
    return p


def _write_sync(folder: Path, filename: str, data: bytes) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    dest = unique_path(folder, filename)
    if dest.resolve().parent != folder.resolve():                   # difesa extra
        raise ValueError("nome file non valido")
    tmp = dest.with_name(dest.name + ".part")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return dest


async def save_to_folder(folder_path: str, filename: str, data: bytes) -> Path:
    """Salva `data` in folder_path/filename (senza sovrascrivere). Ritorna il percorso scritto."""
    folder = check_folder(folder_path)
    return await asyncio.to_thread(_write_sync, folder, filename, data)


def human_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f} MB"
    return f"{max(1, round(n / 1024))} KB"
