"""
agent/email_attachments.py — Scarica automaticamente gli allegati delle email e li
smista nelle cartelle configurate, poi manda un riassunto sul bot Telegram.

Esempi di email riconosciute (per oggetto):
    "La nuova Bolletta Web LUCE del 12 ottobre 2026 è online"  → /config/ago/enel
    "La nuova Bolletta Web GAS del 10 ottobre 2026 è online"   → /config/ago/gas
    foto ricevute da familiari / amici                          → /config/ago/foto
    altri documenti (preventivi, referti, contratti…)           → cartella a scelta

Dopo il salvataggio il bot manda un riassunto:
    • bolletta  → importo da pagare + scadenza (letti da PDF e testo dell'email)
    • foto      → indirizzo di chi ha inviato la foto + descrizione
    • documento → mittente, oggetto e breve descrizione

Configurazione (person_config.json → "email_attachments"), scritta dalla pagina /email → 📎 Allegati:
  "email_attachments": {
      "enabled": true,                  # interruttore generale (default: spento)
      "lookback_days": 3,               # quanti giorni indietro cercare le email
      "rules": [
          {"id": "luce", "name": "Bolletta LUCE", "enabled": true, "kind": "bolletta",
           "match": "bolletta web luce",         # parole che devono comparire nell'oggetto
           "sender": "",                          # opzionale: parte dell'indirizzo mittente
           "account": "",                         # opzionale: solo questo account ("" = tutti)
           "folder": "/config/ago/enel",
           "prefix_date": true, "pdf_password": "", "ai_describe": true}
      ]
  }

Sicurezza / affidabilità:
  • non modifica MAI le email (lettura con BODY.PEEK, cartella in sola lettura);
  • ogni email viene elaborata una sola volta (registro in /data, anche dopo un riavvio);
  • un file già presente non viene sovrascritto (si aggiunge " (1)", " (2)"…);
  • il file identico (stesso contenuto) non viene scaricato due volte;
  • nomi file ripuliti, estensioni eseguibili scartate, cartelle di sistema rifiutate;
  • importi e scadenze letti dal testo vengono verificati: l'AI non può "inventare" cifre.
"""

import asyncio
import hashlib
import html as _html
import imaplib
import io
import json
import logging
import os
import re
import ssl
import time
import unicodedata
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("homemind.email_attachments")

CONFIG_PATH = Path("/config/homemind_patches/person_config.json")
STATE_PATH = Path("/data/homemind_email_attachments.json")

KINDS = ("bolletta", "foto", "documento")
DEFAULT_LOOKBACK_DAYS = 3
MAX_LOOKBACK_DAYS = 3650
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024        # per singolo allegato
MAX_TOTAL_BYTES = 60 * 1024 * 1024             # per singola email
MIN_PHOTO_BYTES = 10 * 1024                    # sotto i 10 KB sono loghi/icone, non foto
MAX_PROCESSED = 3000                           # voci ricordate nel registro
MAX_HISTORY = 40
ERROR_NOTIFY_EVERY_S = 6 * 3600                # stesso errore: al massimo un avviso ogni 6 ore

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
VISION_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
# Allegati che non vengono mai salvati (eseguibili / script)
DANGEROUS_EXT = {".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".js", ".jse", ".vbs", ".vbe",
                 ".wsf", ".wsh", ".ps1", ".sh", ".jar", ".msi", ".dll", ".lnk", ".reg", ".apk",
                 ".hta", ".cpl", ".html", ".htm", ".svg"}
_MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTHS_IT = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
              "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}

# cartelle di sistema in cui non si scrive mai (stesso elenco di file_inbox)
_FORBIDDEN = ("/etc", "/proc", "/sys", "/dev", "/root", "/usr", "/bin", "/sbin",
              "/lib", "/lib64", "/boot", "/run")


# ═════════════════════════════ Utilità ═════════════════════════════

def _decode_str(val) -> str:
    """Decodifica intestazioni email (RFC 2047)."""
    if val is None:
        return ""
    try:
        return str(make_header(decode_header(str(val))))
    except Exception:
        return str(val)


def _norm(text: str) -> str:
    """Minuscolo, senza accenti, spazi compattati — per confronti tolleranti."""
    t = unicodedata.normalize("NFKD", str(text or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", t).strip()


def safe_filename(name: str, fallback: str) -> str:
    """Solo il nome (niente percorsi), senza caratteri speciali, max 120 caratteri."""
    n = str(name or "")
    n = n.replace("\\", "/").split("/")[-1]
    n = re.sub(r'[\x00-\x1f<>:"|?*]', "_", n)
    n = re.sub(r"\s+", " ", n).strip().strip(".")
    if not n or n.startswith("."):
        return fallback
    if len(n) > 120:
        stem, ext = os.path.splitext(n)
        n = stem[: 120 - len(ext)] + ext
    return n


def check_folder(folder_path: str) -> Path:
    """Percorso assoluto e non di sistema, altrimenti ValueError."""
    raw = str(folder_path or "").strip()
    if not raw.startswith("/"):
        raise ValueError("il percorso deve essere assoluto (iniziare con /)")
    p = Path(raw).resolve()
    s = str(p)
    if s == "/" or any(s == bad or s.startswith(bad + "/") for bad in _FORBIDDEN):
        raise ValueError(f"cartella di sistema non consentita: {s}")
    return p


def _unique_path(folder: Path, filename: str) -> Path:
    dest = folder / filename
    if not dest.exists():
        return dest
    stem, ext = os.path.splitext(filename)
    for i in range(1, 1000):
        cand = folder / f"{stem} ({i}){ext}"
        if not cand.exists():
            return cand
    return folder / f"{stem}_{int(time.time())}{ext}"


def write_file(folder: Path, filename: str, data: bytes) -> Path:
    """Scrittura atomica (.part poi rinomina), senza mai sovrascrivere."""
    folder.mkdir(parents=True, exist_ok=True)
    dest = _unique_path(folder, filename)
    if dest.resolve().parent != folder.resolve():
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


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n} B"


def _esc(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def _write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


# ═════════════════════════════ Configurazione ═════════════════════════════

def _default_rule_name(kind: str) -> str:
    return {"bolletta": "Bolletta", "foto": "Foto", "documento": "Documento"}.get(kind, "Documento")


def normalize_rule(raw: dict, idx: int = 0) -> dict:
    """Regola con tutti i campi presenti e puliti (usata sia dal salvataggio sia dall'esecuzione)."""
    r = raw if isinstance(raw, dict) else {}
    kind = r.get("kind") if r.get("kind") in KINDS else "documento"
    rid = re.sub(r"[^a-zA-Z0-9_-]", "", str(r.get("id") or "")) or f"r{idx + 1}"
    return {
        "id": rid[:40],
        "name": (str(r.get("name") or "").strip() or _default_rule_name(kind))[:60],
        "enabled": r.get("enabled", True) is not False,
        "kind": kind,
        "match": str(r.get("match") or "").strip()[:200],
        "sender": str(r.get("sender") or "").strip()[:200],
        "account": str(r.get("account") or "").strip()[:200],
        "folder": str(r.get("folder") or "").strip(),
        "prefix_date": r.get("prefix_date", True) is not False,
        "pdf_password": str(r.get("pdf_password") or "")[:100],
        "ai_describe": r.get("ai_describe", True) is not False,
    }


def normalize_config(raw) -> dict:
    r = raw if isinstance(raw, dict) else {}
    try:
        days = int(r.get("lookback_days", DEFAULT_LOOKBACK_DAYS))
    except (TypeError, ValueError):
        days = DEFAULT_LOOKBACK_DAYS
    days = max(1, min(days, MAX_LOOKBACK_DAYS))
    rules = [normalize_rule(x, i) for i, x in enumerate(r.get("rules") or []) if isinstance(x, dict)]
    # id univoci
    seen = set()
    for i, rule in enumerate(rules):
        base = rule["id"]
        n = 2
        while rule["id"] in seen:
            rule["id"] = f"{base}_{n}"
            n += 1
        seen.add(rule["id"])
    return {"enabled": r.get("enabled") is True, "lookback_days": days, "rules": rules,
            "ha_notify": r.get("ha_notify", True) is not False}


def validate_rules(rules: list) -> list:
    """Elenco di problemi (stringhe) che impediscono di salvare; vuoto = tutto ok."""
    problems = []
    for rule in rules:
        label = rule.get("name") or rule.get("id")
        if not rule.get("folder"):
            problems.append(f"«{label}»: manca la cartella di destinazione")
            continue
        try:
            check_folder(rule["folder"])
        except ValueError as e:
            problems.append(f"«{label}»: {e}")
        if rule.get("kind") != "foto" and not rule.get("match") and not rule.get("sender"):
            problems.append(f"«{label}»: indica almeno una parola dell'oggetto o un mittente "
                            f"(altrimenti scaricherebbe gli allegati di TUTTE le email)")
    return problems


def load_config(path: Optional[Path] = None) -> dict:
    path = path or CONFIG_PATH
    try:
        if path.exists():
            full = json.loads(path.read_text(encoding="utf-8-sig"))
            return normalize_config(full.get("email_attachments"))
    except Exception as e:
        logger.warning("email_attachments: lettura config fallita: %s", e)
    return normalize_config(None)


def load_accounts(path: Optional[Path] = None) -> list:
    path = path or CONFIG_PATH
    try:
        if path.exists():
            full = json.loads(path.read_text(encoding="utf-8-sig"))
            return [a for a in (full.get("email_accounts") or [])
                    if isinstance(a, dict) and a.get("address") and a.get("enabled", True)]
    except Exception as e:
        logger.warning("email_attachments: lettura account fallita: %s", e)
    return []


# ═════════════════════════════ Registro (stato) ═════════════════════════════

def load_state() -> dict:
    try:
        if STATE_PATH.exists():
            st = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(st, dict):
                st.setdefault("processed", {})
                st.setdefault("hashes", [])
                st.setdefault("history", [])
                st.setdefault("errors", {})
                st.setdefault("files", {})
                return st
    except Exception as e:
        logger.warning("email_attachments: registro illeggibile (%s) — riparto da zero", e)
    return {"processed": {}, "hashes": [], "history": [], "errors": {}, "files": {}}


def save_state(st: dict) -> None:
    try:
        # limita le dimensioni
        proc = st.get("processed", {})
        if len(proc) > MAX_PROCESSED:
            keep = sorted(proc.items(), key=lambda kv: kv[1].get("ts", 0))[-MAX_PROCESSED:]
            st["processed"] = dict(keep)
        files = st.get("files", {})
        if len(files) > MAX_PROCESSED:
            st["files"] = dict(list(files.items())[-MAX_PROCESSED:])
        st["history"] = st.get("history", [])[-MAX_HISTORY:]
        _write_json_atomic(STATE_PATH, st)
    except Exception as e:
        logger.error("email_attachments: impossibile salvare il registro: %s", e)


def reset_processed() -> int:
    """Dimentica le email già elaborate (non cancella nessun file): al prossimo controllo
    le email ancora nel periodo di ricerca vengono riprocessate."""
    st = load_state()
    n = len(st.get("processed", {}))
    st["processed"] = {}
    st["files"] = {}
    save_state(st)
    return n


def get_history(limit: int = 20) -> list:
    return list(reversed(load_state().get("history", [])))[:limit]


# ═════════════════════════════ Corrispondenza regole ═════════════════════════════

def _split_alternatives(spec: str) -> list:
    return [a.strip() for a in re.split(r"[,;|\n]+", spec or "") if a.strip()]


def subject_matches(spec: str, subject: str) -> bool:
    """spec = frasi separate da virgola; una frase corrisponde se TUTTE le sue parole sono nell'oggetto.
    "bolletta web luce" → vero per «La nuova Bolletta Web LUCE del 12 ottobre 2026 è online»."""
    alts = _split_alternatives(spec)
    if not alts:
        return True
    subj = _norm(subject)
    for alt in alts:
        words = _norm(alt).split()
        if words and all(w in subj for w in words):
            return True
    return False


def sender_matches(spec: str, sender: str) -> bool:
    alts = _split_alternatives(spec)
    if not alts:
        return True
    s = _norm(sender)
    return any(_norm(a) in s for a in alts if _norm(a))


def pick_rule(rules: list, account_addr: str, subject: str, sender: str,
              has_images: bool = True) -> Optional[dict]:
    """Prima regola attiva che corrisponde (l'ordine delle regole conta)."""
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        if rule.get("account") and _norm(rule["account"]) != _norm(account_addr):
            continue
        if not subject_matches(rule.get("match", ""), subject):
            continue
        if not sender_matches(rule.get("sender", ""), sender):
            continue
        if rule.get("kind") == "foto" and not has_images:
            continue
        return rule
    return None


# ═════════════════════════════ Lettura email ═════════════════════════════

def _imap_date(days: int) -> str:
    d = datetime.now() - timedelta(days=days)
    return f"{d.day:02d}-{_MONTHS_EN[d.month - 1]}-{d.year}"      # sempre in inglese (RFC 3501)


def _parse_header_blob(blob: bytes) -> dict:
    msg = message_from_bytes(blob)
    return {
        "subject": _decode_str(msg.get("Subject", "")).replace("\r", " ").replace("\n", " ").strip(),
        "sender": _decode_str(msg.get("From", "")).replace("\r", " ").replace("\n", " ").strip(),
        "msg_id": (msg.get("Message-ID") or "").strip(),
        "date": msg.get("Date", "") or "",
        "ctype": (msg.get("Content-Type") or "").strip(),
    }


def maybe_has_attachments(ctype: str) -> bool:
    """Stima dalle sole intestazioni: l'email può contenere allegati/immagini?
    (text/plain e multipart/alternative semplici non ne hanno: evito di scaricarle per niente)"""
    c = (ctype or "").lower()
    if not c:
        return True                                   # intestazione assente: non escludo
    return any(x in c for x in ("multipart/mixed", "multipart/related", "multipart/signed",
                                "multipart/report", "image/", "application/"))


def list_recent_headers(conn, days: int, folder: str = "INBOX") -> list:
    """[(uid, {subject, sender, msg_id, date})] delle email degli ultimi `days` giorni, dalla più vecchia.
    Usa BODY.PEEK: non cambia lo stato letto/non letto."""
    status, _ = conn.select(f'"{folder}"', readonly=True)
    if status != "OK":
        raise RuntimeError(f"cartella IMAP non selezionabile: {folder}")
    status, data = conn.uid("SEARCH", None, "SINCE", _imap_date(days))
    if status != "OK" or not data or not data[0]:
        return []
    uids = data[0].split()
    out = []
    for i in range(0, len(uids), 150):
        chunk = uids[i:i + 150]
        status, resp = conn.uid("FETCH", b",".join(chunk),
                                "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM MESSAGE-ID DATE CONTENT-TYPE)])")
        if status != "OK" or not resp:
            continue
        for i, item in enumerate(resp):
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            head = item[0] if isinstance(item[0], bytes) else str(item[0]).encode()
            m = re.search(rb"UID (\d+)", head)
            if not m and i + 1 < len(resp) and isinstance(resp[i + 1], bytes):
                m = re.search(rb"UID (\d+)", resp[i + 1])          # alcuni server mettono UID dopo il blocco
            if not m:
                continue
            try:
                out.append((m.group(1).decode(), _parse_header_blob(item[1])))
            except Exception as e:
                logger.debug("header illeggibile uid %s: %s", m.group(1), e)
    out.sort(key=lambda t: int(t[0]))
    return out


def fetch_raw(conn, uid: str) -> bytes:
    status, resp = conn.uid("FETCH", uid, "(BODY.PEEK[])")
    if status != "OK" or not resp:
        raise RuntimeError(f"fetch uid {uid} fallito")
    for item in resp:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])
    raise RuntimeError(f"fetch uid {uid}: risposta vuota")


def extract_body_text(msg) -> str:
    """Testo dell'email (plain, altrimenti html ripulito)."""
    plain, htmls = [], []
    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        if "attachment" in str(part.get("Content-Disposition", "")).lower():
            continue
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            txt = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        (plain if ctype == "text/plain" else htmls).append(txt)
    if plain:
        return "\n".join(plain).strip()
    if htmls:
        t = "\n".join(htmls)
        t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
        t = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", t)
        t = re.sub(r"<[^>]+>", " ", t)
        t = _html.unescape(t)
        t = re.sub(r"[ \t\xa0]+", " ", t)
        t = re.sub(r"\n\s*\n+", "\n", t)
        return t.strip()
    return ""


def extract_attachments(msg) -> list:
    """[{filename, data, mime, ext, inline}] — solo parti con nome file (o immagini non inline)."""
    out = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition", "")).lower()
        fname = part.get_filename()
        if fname:
            fname = _decode_str(fname)
        is_attachment = "attachment" in disp
        is_inline = ("inline" in disp or bool(part.get("Content-ID"))) and not is_attachment
        if not fname:
            # immagine senza nome (alcuni client): la tengo solo se allegata davvero
            if not (is_attachment and ctype.startswith("image/")):
                continue
            fname = "immagine." + (ctype.split("/")[1].replace("jpeg", "jpg"))
        try:
            data = part.get_payload(decode=True)
        except Exception:
            data = None
        if not data:
            continue
        ext = os.path.splitext(fname)[1].lower()
        out.append({"filename": fname, "data": data, "mime": ctype, "ext": ext, "inline": is_inline})
    return out


def select_attachments(kind: str, attachments: list) -> tuple:
    """(da_salvare, scartati[(nome, motivo)]) secondo il tipo di regola."""
    keep, skipped = [], []
    for a in attachments:
        name, ext, size = a["filename"], a["ext"], len(a["data"])
        if ext in DANGEROUS_EXT:
            skipped.append((name, "tipo di file non sicuro"))
            continue
        if size > MAX_ATTACHMENT_BYTES:
            skipped.append((name, f"troppo grande ({human_size(size)})"))
            continue
        is_img = ext in IMAGE_EXT or a["mime"].startswith("image/")
        if kind == "foto":
            if not is_img:
                continue                                  # le foto: solo immagini
            if a["inline"] or size < MIN_PHOTO_BYTES:
                continue                                  # loghi / firme / pixel traccianti
        else:
            if a["inline"] and is_img:
                continue                                  # logo nel corpo dell'email
        keep.append(a)
    total = 0
    final = []
    for a in keep:
        total += len(a["data"])
        if total > MAX_TOTAL_BYTES:
            skipped.append((a["filename"], "limite totale per email superato"))
            continue
        final.append(a)
    return final, skipped


# ═════════════════════════════ Estrazione importi / scadenze ═════════════════════════════

_AMOUNT = r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
_EURO = r"(?:€|eur(?:o)?)"

# (parola chiave, serve il simbolo € accanto all'importo). I primi sono i più specifici.
_AMOUNT_KEYS = [
    (r"totale\s+da\s+pagare", False), (r"importo\s+da\s+pagare", False),
    (r"totale\s+bolletta", False), (r"importo\s+bolletta", False),
    (r"importo\s+totale", False), (r"totale\s+fattura", False), (r"totale\s+documento", False),
    (r"importo\s+fattura", False), (r"totale\s+importo", False), (r"totale\s+complessivo", False),
    (r"da\s+pagare", True), (r"totale", True),
]
_DUE_KEYS = [
    r"data\s+di\s+scadenza", r"scadenza\s+pagamento", r"pagare\s+entro(?:\s+il)?", r"scadenza",
    r"scade\s+il", r"entro\s+il", r"entro\s+(?=\d)",
]
# tra parola chiave e importo possono esserci testo e anche una data («totale da pagare entro il 05/11/2026 € 87,45»)
_GAP = r"(?:[^\d€]|\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}){0,80}?"
_NOT_PAYMENT_DUE = re.compile(r"offerta|contratt|prezz|promo|bonus|agevol|bando|documento d|carta d|validit", re.I)
_DATE_NUM = r"(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4}|\d{2})"
_DATE_IT = r"(\d{1,2})\s+(" + "|".join(_MONTHS_IT) + r")\s+(\d{4})"


def _fmt_date(d: int, m: int, y: int) -> Optional[str]:
    if y < 100:
        y += 2000
    try:
        datetime(y, m, d)
    except ValueError:
        return None
    return f"{d:02d}/{m:02d}/{y}"


def find_dates(text: str) -> list:
    """Date nel testo (formato gg/mm/aaaa) con posizione."""
    found = []
    for m in re.finditer(_DATE_NUM, text):
        s = _fmt_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if s:
            found.append((m.start(), s))
    for m in re.finditer(_DATE_IT, text, flags=re.I):
        s = _fmt_date(int(m.group(1)), _MONTHS_IT[m.group(2).lower()], int(m.group(3)))
        if s:
            found.append((m.start(), s))
    found.sort()
    return found


def extract_amount_regex(text: str) -> Optional[str]:
    """Importo da pagare, in formato italiano «123,45» (senza simbolo). None se non sicuro."""
    t = text or ""
    for key, need_euro in _AMOUNT_KEYS:
        if need_euro:
            pat = re.compile(key + _GAP + r"(?:" + _EURO + r"\s*" + _AMOUNT + r"|" + _AMOUNT + r"\s*" + _EURO + r")",
                             re.I | re.S)
        else:
            pat = re.compile(key + _GAP + r"(?:" + _EURO + r"\s*)?" + _AMOUNT, re.I | re.S)
        m = pat.search(t)
        if m:
            return next(g for g in m.groups() if g)
    # "€ 123,45" isolato: lo accetto solo se in tutto il testo c'è UN SOLO importo in euro
    amounts = set(re.findall(_EURO + r"\s*" + _AMOUNT, t, flags=re.I))
    amounts |= set(re.findall(_AMOUNT + r"\s*" + _EURO, t, flags=re.I))
    if len(amounts) == 1:
        return next(iter(amounts))
    return None


def extract_due_regex(text: str) -> Optional[str]:
    t = text or ""
    dates = find_dates(t)
    if not dates:
        return None
    for key in _DUE_KEYS:
        for km in re.finditer(key, t, flags=re.I):
            if key == r"scadenza" and _NOT_PAYMENT_DUE.search(t[km.end():km.end() + 25]):
                continue                                   # «scadenza offerta/contratto…» non è il pagamento
            for pos, s in dates:
                if km.end() <= pos <= km.end() + 70:
                    return s
    return None


def _amount_in_text(amount: str, text: str) -> bool:
    return bool(amount) and re.search(r"(?<![\d.,])" + re.escape(amount) + r"(?![\d])", text or "") is not None


def _date_in_text(date_str: str, text: str) -> bool:
    """La data (gg/mm/aaaa) compare nel testo in una delle forme comuni."""
    try:
        d, m, y = (int(x) for x in date_str.split("/"))
    except Exception:
        return False
    for _, s in find_dates(text or ""):
        if s == date_str:
            return True
    return False


def clean_amount(raw: str) -> Optional[str]:
    """Porta qualunque risposta ("€ 1.234,5", "87.45 euro") al formato «1.234,50»; None se illeggibile."""
    s = re.sub(r"[^\d.,]", "", str(raw or ""))
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "")
        else:
            s = s.replace(",", "X").replace(".", ",").replace("X", ".")
            s = s.replace(".", "")
    elif "," not in s and "." in s and re.fullmatch(r"\d+\.\d{1,2}", s):
        s = s.replace(".", ",")
    if "," in s:
        ip, dp = s.split(",", 1)
        dp = (dp + "00")[:2]
    else:
        ip, dp = s, "00"
    ip = ip.replace(".", "").lstrip("0") or "0"
    groups = []
    while len(ip) > 3:
        groups.insert(0, ip[-3:])
        ip = ip[:-3]
    groups.insert(0, ip)
    return ".".join(groups) + "," + dp


def pdf_text(data: bytes, password: str = "", max_pages: int = 6) -> tuple:
    """(testo, errore). errore = None se tutto ok."""
    try:
        import pdfplumber
    except ImportError:
        return "", "pdfplumber non installato"
    try:
        kwargs = {"password": password} if password else {}
        with pdfplumber.open(io.BytesIO(data), **kwargs) as pdf:
            parts = []
            for page in pdf.pages[:max_pages]:
                t = page.extract_text() or ""
                if t:
                    parts.append(t)
            text = "\n".join(parts).strip()
        if not text:
            return "", "PDF senza testo (scansione/immagine)"
        return text, None
    except Exception as e:
        name = type(e).__name__
        if "Password" in name or "password" in str(e).lower() or "encrypt" in str(e).lower():
            return "", "PDF protetto da password" + (" (password errata)" if password else "")
        return "", f"PDF non leggibile ({name})"


# ═════════════════════════════ Elaboratore ═════════════════════════════

class EmailAttachmentProcessor:
    """Cerca le email corrispondenti alle regole, salva gli allegati e avvisa sul bot."""

    def __init__(self, ai_cb=None, vision_cb=None, vision_available_cb=None, notify_cb=None, ha_notify_cb=None):
        # ai_cb(prompt) -> str          (testo)
        # vision_cb(bytes, mime, prompt) -> str   (descrizione immagine)
        self.ai_cb = ai_cb
        self.vision_cb = vision_cb
        self.vision_available_cb = vision_available_cb
        self.notify_cb = notify_cb
        self.ha_notify_cb = ha_notify_cb      # async (titolo, testo) -> notifica sulla plancia di Home Assistant
        self._ha_enabled = True
        self._batch = None                    # durante run(): messaggi raccolti e inviati alla fine
        self._lock: Optional[asyncio.Lock] = None
        self.last_run: dict = {}

    # ── pubblico ─────────────────────────────────────────────
    async def run(self, dry_run: bool = False, lookback_days: Optional[int] = None,
                  force_enabled: bool = False) -> dict:
        """Un ciclo completo. dry_run=True: dice cosa scaricherebbe senza scaricare né avvisare."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        if self._lock.locked():
            return {"ok": True, "busy": True, "message": "Un controllo è già in corso"}
        async with self._lock:
            cfg = load_config()
            self._ha_enabled = cfg.get("ha_notify", True)
            result = {"ok": True, "enabled": cfg["enabled"], "dry_run": dry_run, "checked": 0,
                      "matched": [], "downloaded": [], "errors": [], "accounts": 0}
            if not cfg["enabled"] and not force_enabled:
                result["message"] = "Download allegati disattivato"
                return result
            rules = [r for r in cfg["rules"] if r["enabled"]]
            if not rules:
                result["message"] = "Nessuna regola attiva"
                return result
            accounts = load_accounts()
            if not accounts:
                result["message"] = "Nessun account email abilitato"
                return result
            days = lookback_days if lookback_days else cfg["lookback_days"]
            days = max(1, min(int(days), MAX_LOOKBACK_DAYS))
            state = load_state()
            self._batch = [] if not dry_run else None
            for acc in accounts:
                result["accounts"] += 1
                try:
                    await self._process_account(acc, rules, days, state, result, dry_run)
                except Exception as e:
                    logger.error("email_attachments [%s]: %s", acc.get("address"), e)
                    result["errors"].append(f"{acc.get('address')}: {e}")
            if not dry_run:
                save_state(state)
            try:
                await self._flush_batch()
            except Exception as e:
                logger.warning("email_attachments: invio notifiche: %s", e)
            self._batch = None
            self.last_run = {"ts": time.time(), "dry_run": dry_run,
                             "checked": result["checked"], "downloaded": len(result["downloaded"])}
            return result

    # ── interno ──────────────────────────────────────────────
    def _open(self, acc: dict):
        ctx = ssl.create_default_context()
        conn = imaplib.IMAP4_SSL(host=acc.get("imap_host", "imap.gmail.com"),
                                 port=int(acc.get("imap_port", 993)), ssl_context=ctx, timeout=60)
        conn.login(acc["address"], acc["app_password"])
        return conn

    async def _process_account(self, acc, rules, days, state, result, dry_run):
        addr = acc["address"]
        # 1) elenco intestazioni (veloce) — in thread perché imaplib è bloccante
        conn = await asyncio.to_thread(self._open, acc)
        try:
            headers = await asyncio.to_thread(list_recent_headers, conn, days)
            result["checked"] += len(headers)
            candidates = []
            for uid, h in headers:
                key = f"{addr}|{h['msg_id'] or ('uid' + uid)}"
                if key in state["processed"]:
                    if pick_rule(rules, addr, h["subject"], h["sender"]):
                        result.setdefault("already_done", []).append(
                            {"subject": h["subject"], "when": state["processed"][key].get("ts", 0)})
                    continue
                # le regole "foto" richiedono che l'email possa avere allegati (stima dalle intestazioni)
                rule = pick_rule(rules, addr, h["subject"], h["sender"],
                                 has_images=maybe_has_attachments(h.get("ctype", "")))
                if rule:
                    candidates.append((uid, h, rule, key))
            # 2) scarico il messaggio intero solo per i candidati
            for uid, h, rule, key in candidates:
                try:
                    raw = await asyncio.to_thread(fetch_raw, conn, uid)
                except Exception as e:
                    result["errors"].append(f"{h['subject'][:40]}: {e}")
                    continue
                await self._handle_message(addr, uid, h, rule, key, raw, rules, state, result, dry_run)
        finally:
            try:
                await asyncio.to_thread(conn.logout)
            except Exception:
                pass

    async def _handle_message(self, addr, uid, h, rule, key, raw, rules, state, result, dry_run):
        msg = message_from_bytes(raw)
        atts_all = extract_attachments(msg)
        # regola "foto" senza foto vere → riprova con le regole successive (o niente)
        if rule["kind"] == "foto":
            has_img = any((a["ext"] in IMAGE_EXT or a["mime"].startswith("image/"))
                          and not a["inline"] and len(a["data"]) >= MIN_PHOTO_BYTES for a in atts_all)
            if not has_img:
                rule = pick_rule([r for r in rules if r["kind"] != "foto"], addr, h["subject"], h["sender"])
                if not rule:
                    if not dry_run:                                  # esaminata: non la riguardo a ogni ciclo
                        state["processed"][key] = {"ts": time.time(), "subject": h["subject"][:80], "files": 0}
                    return
        to_save, skipped = select_attachments(rule["kind"], atts_all)
        info = {"subject": h["subject"], "sender": h["sender"], "rule": rule["name"],
                "kind": rule["kind"], "files": [a["filename"] for a in to_save]}
        if not to_save:
            info["note"] = "nessun allegato da scaricare"
            result["matched"].append(info)
            if dry_run:
                return
            state["processed"][key] = {"ts": time.time(), "subject": h["subject"][:80], "files": 0}
            if rule["kind"] == "bolletta":
                # niente PDF in allegato (bolletta solo online): avviso comunque con ciò che dice l'email
                body_text = extract_body_text(msg)
                summary = await self._summarize_bill(rule, h, [], body_text, "")
                text = summary["message"].rstrip() + "\nℹ️ <i>L'email non ha allegati: la bolletta è consultabile online.</i>"
                state["history"].append({"ts": int(time.time()), "rule": rule["name"], "kind": rule["kind"],
                                         "subject": h["subject"][:120], "sender": h["sender"][:120], "files": [],
                                         **{k: v for k, v in summary.get("facts", {}).items() if v}})
                result["downloaded"].append({"rule": rule["name"], "subject": h["subject"], "files": [],
                                             **summary.get("facts", {})})
                await self._notify(text)
            return
        result["matched"].append(info)
        if dry_run:
            return

        # ── cartella ──
        try:
            folder = check_folder(rule["folder"])
        except ValueError as e:
            await self._report_error(state, f"folder|{rule['id']}",
                                     f"⚠️ <b>Allegati email</b>: regola «{_esc(rule['name'])}» — "
                                     f"cartella non valida: {_esc(e)}")
            result["errors"].append(f"{rule['name']}: cartella non valida ({e})")
            return

        # ── salvataggio ──
        saved, dups, failed = [], [], []
        date_prefix = ""
        if rule["prefix_date"]:
            try:
                dt = parsedate_to_datetime(h["date"]) if h["date"] else datetime.now()
            except Exception:
                dt = datetime.now()
            date_prefix = dt.strftime("%Y%m%d_")
        for a in to_save:
            digest = hashlib.sha256(a["data"]).hexdigest()
            known = state.setdefault("files", {}).get(digest)
            if known and Path(known).exists():            # stesso contenuto già salvato E ancora presente
                dups.append(a["filename"])
                continue
            name = safe_filename(a["filename"], f"allegato_{int(time.time())}{a['ext'] or '.bin'}")
            if date_prefix and not name.startswith(date_prefix):
                name = date_prefix + name
            try:
                dest = await asyncio.to_thread(write_file, folder, name, a["data"])
                saved.append({"path": str(dest), "name": dest.name, "size": len(a["data"]),
                              "data": a["data"], "ext": a["ext"], "mime": a["mime"]})
                state["files"][digest] = str(dest)
            except Exception as e:
                logger.error("email_attachments: scrittura %s fallita: %s", name, e)
                failed.append((a["filename"], str(e)))
        if failed and not saved:
            await self._report_error(state, f"write|{rule['id']}",
                                     f"⚠️ <b>Allegati email</b>: non riesco a scrivere in "
                                     f"<code>{_esc(rule['folder'])}</code>: {_esc(failed[0][1])}")
            result["errors"].append(f"{rule['name']}: scrittura fallita ({failed[0][1]})")
            return                                                  # non ricordo: riprovo al prossimo ciclo

        state["processed"][key] = {"ts": time.time(), "subject": h["subject"][:80], "files": len(saved)}
        if not saved:
            return                                      # tutti già presenti (duplicati): niente da raccontare

        body_text = extract_body_text(msg)
        summary = await self._summarize(rule, h, saved, body_text)
        hist = {"ts": int(time.time()), "rule": rule["name"], "kind": rule["kind"],
                "subject": h["subject"][:120], "sender": h["sender"][:120],
                "files": [s["path"] for s in saved]}
        hist.update({k: v for k, v in summary.get("facts", {}).items() if v})
        state["history"].append(hist)
        result["downloaded"].append({"rule": rule["name"], "subject": h["subject"],
                                     "files": [s["path"] for s in saved], **summary.get("facts", {})})
        # accessi: avviso Telegram
        msg_html = summary["message"]
        if dups:
            msg_html += f"\n♻️ <i>Già presenti (ignorati): {_esc(', '.join(dups))}</i>"
        if skipped:
            msg_html += f"\n⚠️ <i>Non scaricati: {_esc(', '.join(f'{n} ({why})' for n, why in skipped))}</i>"
        if failed:
            msg_html += f"\n❌ <i>Errore scrittura: {_esc(', '.join(n for n, _ in failed))}</i>"
        await self._notify(msg_html)

    async def _report_error(self, state, key, text):
        now = time.time()
        last = state["errors"].get(key, 0)
        if now - last >= ERROR_NOTIFY_EVERY_S:
            state["errors"][key] = now
            await self._notify(text)

    async def _notify(self, text: str, immediate: bool = False):
        if self._batch is not None and not immediate:
            self._batch.append(text)
            return
        await self._send(text)

    async def _flush_batch(self):
        """Pochi messaggi: uno per uno. Molti (es. ricerca su mesi di posta): riepilogo unico a blocchi."""
        batch, self._batch = self._batch or [], None
        if len(batch) <= 3:
            for t in batch:
                await self._send(t)
            return
        head = f"📎 <b>{len(batch)} documenti scaricati dalle email</b>\n"
        chunk = head
        for t in batch:
            lines = [l for l in t.splitlines() if l.strip()]
            # titolo + oggetto + importo/scadenza (senza il percorso file)
            short = "\n".join(l for l in lines if not l.startswith("📁"))
            if len(chunk) + len(short) > 3500:
                await self._send(chunk)
                chunk = ""
            chunk += "\n" + short + "\n"
        if chunk.strip():
            await self._send(chunk)

    async def _send(self, text: str):
        if self.notify_cb:
            try:
                r = self.notify_cb(text)
                if asyncio.iscoroutine(r) or isinstance(r, asyncio.Future):
                    await r
            except Exception as e:
                logger.warning("email_attachments: notifica Telegram non inviata: %s", e)
        if self.ha_notify_cb and self._ha_enabled:
            try:
                plain = _html.unescape(re.sub(r"<[^>]+>", "", text.replace("</b>", "</b>")))
                lines = [l.strip() for l in plain.splitlines() if l.strip()]
                if lines:
                    await self.ha_notify_cb(lines[0], "\n\n".join(lines[1:]) or lines[0])
            except Exception as e:
                logger.warning("email_attachments: notifica Home Assistant non inviata: %s", e)

    # ── riassunti ────────────────────────────────────────────
    async def _summarize(self, rule: dict, h: dict, saved: list, body_text: str) -> dict:
        kind = rule["kind"]
        sender_name, sender_addr = parseaddr(h["sender"])
        sender_disp = f"{_esc(sender_name)} &lt;{_esc(sender_addr)}&gt;" if sender_name and sender_addr else _esc(h["sender"])
        files_txt = "\n".join(f"📁 <code>{_esc(s['path'])}</code> ({human_size(s['size'])})" for s in saved)
        if kind == "bolletta":
            return await self._summarize_bill(rule, h, saved, body_text, files_txt)
        if kind == "foto":
            return await self._summarize_photo(rule, h, saved, body_text, sender_disp, sender_addr, files_txt)
        return await self._summarize_doc(rule, h, saved, body_text, sender_disp, files_txt)

    @staticmethod
    def _bill_icon(rule: dict) -> str:
        t = _norm(rule["name"] + " " + rule.get("match", ""))
        if "gas" in t:
            return "🔥"
        if "luce" in t or "elettric" in t or "energia" in t:
            return "⚡"
        if "acqua" in t or "idric" in t:
            return "💧"
        if "internet" in t or "telefon" in t or "fibra" in t:
            return "📡"
        return "🧾"

    async def _summarize_bill(self, rule, h, saved, body_text, files_txt) -> dict:
        texts, problems = [], []
        if body_text:
            texts.append(body_text)
        for s in saved:
            if s["ext"] == ".pdf":
                t, err = await asyncio.to_thread(pdf_text, s["data"], rule.get("pdf_password", ""))
                if t:
                    texts.append(t)
                elif err:
                    problems.append(f"{s['name']}: {err}")
        full = "\n".join(texts)
        amount = extract_amount_regex(full)
        due = extract_due_regex(full)
        source = "testo"
        # L'AI interviene solo per i campi mancanti e i suoi risultati sono verificati sul testo
        if (not amount or not due) and self.ai_cb and full.strip():
            try:
                ai_amount, ai_due = await self._ai_extract_bill(full)
                if not amount and ai_amount and _amount_in_text(ai_amount, full):
                    amount, source = ai_amount, "AI verificata"
                if not due and ai_due and _date_in_text(ai_due, full):
                    due, source = ai_due, "AI verificata"
            except Exception as e:
                logger.info("email_attachments: estrazione AI non riuscita: %s", e)
        icon = self._bill_icon(rule)
        lines = [f"{icon} <b>{_esc(rule['name'])} scaricata</b>",
                 f"✉️ {_esc(h['subject'])}"]
        lines.append(f"💶 Importo da pagare: <b>€ {_esc(amount)}</b>" if amount
                     else "💶 Importo: <i>non riesco a leggerlo con sicurezza — controlla il PDF</i>")
        lines.append(f"📅 Scadenza: <b>{_esc(due)}</b>" if due
                     else "📅 Scadenza: <i>non trovata — controlla il PDF</i>")
        if problems:
            lines.append("ℹ️ " + _esc("; ".join(problems)))
        lines.append(files_txt)
        return {"message": "\n".join(lines),
                "facts": {"importo": amount or "", "scadenza": due or ""}}

    async def _ai_extract_bill(self, text: str) -> tuple:
        prompt = (
            "Dal testo di questa bolletta/fattura estrai SOLO due dati e rispondi con un JSON, senza altro testo:\n"
            '{"importo": "<totale da pagare, formato 123,45>", "scadenza": "<gg/mm/aaaa>"}\n'
            "Se un dato non è presente nel testo usa null. Non inventare e non calcolare: "
            "copia solo ciò che è scritto.\n\nTESTO:\n" + text[:7000]
        )
        resp = await self.ai_cb(prompt)
        m = re.search(r"\{.*?\}", resp or "", re.S)
        if not m:
            return None, None
        data = json.loads(m.group(0))
        amount = clean_amount(data.get("importo")) if data.get("importo") else None
        due = None
        if data.get("scadenza"):
            ds = find_dates(str(data["scadenza"]))
            due = ds[0][1] if ds else None
        return amount, due

    @staticmethod
    def _clean_message_text(text: str, limit: int = 220) -> str:
        """Prime righe utili del messaggio, senza citazioni, firme automatiche e link."""
        out = []
        for line in (text or "").splitlines():
            s = line.strip()
            if not s or s.startswith(">"):
                continue
            low = s.lower()
            if re.match(r"^(il giorno|on .* wrote|da:|from:|-----|inviato da|sent from|get outlook|scarica outlook)", low):
                break
            if re.fullmatch(r"https?://\S+", s):
                continue
            out.append(s)
            if len(" ".join(out)) >= limit:
                break
        t = re.sub(r"\s+", " ", " ".join(out)).strip()
        return (t[:limit].rstrip() + "…") if len(t) > limit else t

    async def _summarize_photo(self, rule, h, saved, body_text, sender_disp, sender_addr, files_txt) -> dict:
        n = len(saved)
        desc = self._clean_message_text(body_text)
        ai_desc = ""
        use_ai = (rule.get("ai_describe", True) and self.vision_cb is not None
                  and (self.vision_available_cb is None or self.vision_available_cb()))
        if use_ai:
            for s in saved[:1]:                                      # una chiamata AI per email: la prima foto
                if s["ext"] not in VISION_EXT:
                    continue
                try:
                    jpg = await asyncio.to_thread(_prepare_image, s["data"])
                    if jpg:
                        ai_desc = (await self.vision_cb(
                            jpg, "image/jpeg",
                            "Descrivi in una frase breve, in italiano, cosa mostra questa foto. "
                            "Se vedi un documento, di' che documento è."
                        ) or "").strip()
                except Exception as e:
                    logger.info("email_attachments: descrizione foto non riuscita: %s", e)
        lines = [f"📷 <b>{'Nuova foto ricevuta' if n == 1 else f'{n} nuove foto ricevute'}</b>",
                 f"👤 Da: {sender_disp}"]
        subj = (h["subject"] or "").strip()
        if subj and not re.fullmatch(r"(img|dsc|image|photo|foto|pxl|whatsapp)[\w\s.\-]*", _norm(subj)):
            lines.append(f"✉️ Oggetto: {_esc(subj)}")
        if desc:
            lines.append(f"📝 Messaggio: <i>{_esc(desc)}</i>")
        if ai_desc:
            lines.append(f"🤖 Descrizione: <i>{_esc(ai_desc[:300])}</i>")
        if not desc and not ai_desc:
            lines.append("📝 <i>Nessuna descrizione allegata</i>")
        lines.append(files_txt)
        return {"message": "\n".join(lines),
                "facts": {"da": sender_addr or h["sender"], "descrizione": desc or ai_desc}}

    async def _summarize_doc(self, rule, h, saved, body_text, sender_disp, files_txt) -> dict:
        snippet = self._clean_message_text(body_text, 160)
        ai_sum = ""
        if self.ai_cb:
            texts = [body_text] if body_text else []
            for s in saved:
                if s["ext"] == ".pdf":
                    t, _ = await asyncio.to_thread(pdf_text, s["data"], rule.get("pdf_password", ""), 3)
                    if t:
                        texts.append(t)
            full = "\n".join(texts).strip()
            if full:
                try:
                    ai_sum = (await self.ai_cb(
                        "Riassumi in UNA frase italiana (max 25 parole) di cosa tratta questo documento/email. "
                        "Non inventare nulla che non sia nel testo.\n\n" + full[:5000])).strip()
                except Exception as e:
                    logger.info("email_attachments: riassunto AI non riuscito: %s", e)
        lines = [f"📄 <b>{_esc(rule['name'])}: documento salvato</b>",
                 f"👤 Da: {sender_disp}",
                 f"✉️ {_esc(h['subject'])}"]
        if ai_sum:
            lines.append(f"🤖 {_esc(ai_sum[:300])}")
        elif snippet:
            lines.append(f"📝 <i>{_esc(snippet)}</i>")
        lines.append(files_txt)
        return {"message": "\n".join(lines), "facts": {"descrizione": ai_sum or snippet}}


def _prepare_image(data: bytes, max_side: int = 1400) -> Optional[bytes]:
    """JPEG ridimensionato per l'AI; None se non preparabile (e immagine troppo grande)."""
    try:
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(data)) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((max_side, max_side))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=80)
            return buf.getvalue()
    except Exception as e:
        logger.debug("immagine non preparabile: %s", e)
        return data if len(data) <= 4 * 1024 * 1024 else None
