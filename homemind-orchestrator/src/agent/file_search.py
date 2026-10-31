"""
agent/file_search.py — "Mandami il file": ricerca nei file delle cartelle configurate.

Funziona anche quando i file hanno nomi strani ("2026-02-13 07.jpg", "scan0001.pdf"):
  • data del file: da EXIF (foto), dal nome (2026-02-13, 20260213, 13-02-2026) o dalla data di modifica
  • PDF / Word / testo: il TESTO viene letto in locale (nessun dato esce da casa)
  • immagini (opzionale, spento di default): una descrizione fatta da un provider AI con visione
    (Gemini, Claude o OpenAI) → si trovano con parole come "cena", "gatto", "scontrino"
  • PDF scansionati (senza testo): come le immagini, solo se la visione è attiva

Tutto è salvato in un indice SQLite (/config/homemind_patches/files_index.db) aggiornato in
background, a piccoli passi, per non pesare sul sistema. Si cerca SOLO nelle cartelle
configurate nella pagina web (tab 📁 File); i file sensibili (chiavi, secrets…) sono esclusi.

Impostazioni (person_config.json → file_inbox.search):
  {"enabled": false, "subfolders": true, "vision": false, "vision_per_day": 100}
"""

import asyncio
import functools
import io
import json
import logging
import math
import os
import re
import sqlite3
import time
import unicodedata
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger("homemind.file_search")

DB_PATH = Path("/config/homemind_patches/files_index.db")
SCAN_INTERVAL_S = 1800          # riscansione cartelle ogni 30 minuti
MAX_FILES = 20000               # tetto di file indicizzati
MAX_TEXT_CHARS = 20000          # testo massimo salvato per file
MAX_PDF_PAGES = 12
SNIPPET_CHARS = 1500            # testo originale tenuto per le anteprime
VISION_DELAY_S = 4.0            # pausa tra due richieste di visione (rispetta le quote gratuite)
VISION_TIMEOUT_S = 60
MAX_IMAGE_SIDE = 1280           # le immagini inviate all'AI vengono ridimensionate
TELEGRAM_MAX_BYTES = 50 * 1024 * 1024

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
VISION_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}   # HEIC: solo nome/data
PDF_EXT = {".pdf"}
DOC_EXT = {".docx"}
TEXT_EXT = {".txt", ".md", ".csv", ".log"}

_SENSITIVE_NAMES = {"secrets.yaml", "secrets.yml", "known_hosts", "authorized_keys",
                    "id_rsa", "id_ed25519", "person_config.json", "files_index.db"}
_SENSITIVE_EXT = {".pem", ".key", ".p12", ".pfx", ".db", ".sqlite", ".sqlite3", ".kdbx", ".gpg"}
_SKIP_DIRS = {"@eadir", "node_modules", "__pycache__", "lost+found", ".storage", ".git"}

VISION_PROMPT = (
    "Descrivi questa immagine per poterla ritrovare con una ricerca testuale. "
    "Rispondi in italiano, esattamente in questo formato:\n"
    "Descrizione: <1-2 frasi su cosa mostra>.\n"
    "Testo visibile: <titoli, nomi, date, importi importanti; vuoto se non c'è testo>.\n"
    "Parole chiave: <8-12 parole chiave in italiano separate da virgola>.\n"
    "Niente altro."
)
VISION_SYSTEM = "Sei un assistente che cataloga immagini e documenti scansionati per un archivio personale."

_MONTHS = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
           "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}
_MONTH_NAMES = list(_MONTHS)


# ═══════════════════════════ Utilità di testo ═══════════════════════════════

def norm(s: str) -> str:
    """minuscolo, senza accenti, solo lettere/numeri separati da spazio singolo."""
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def stem(w: str) -> str:
    """Radice grossolana: toglie la vocale finale (bollette/bolletta → bollett, luce/luci → luc)."""
    return w[:-1] if len(w) >= 4 and w[-1] in "aeio" else w


def human_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f} MB"
    return f"{max(1, round(n / 1024))} KB"


# ═══════════════════════════ Date dei file ══════════════════════════════════

def _noon(y: int, m: int, d: int):
    try:
        return datetime(y, m, d, 12, 0, 0).timestamp()
    except ValueError:
        return None


_RE_ISO = re.compile(r"(?<!\d)(20\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])(?!\d)")
_RE_DMY = re.compile(r"(?<!\d)(0[1-9]|[12]\d|3[01])[-_.](0[1-9]|1[0-2])[-_.](20\d{2})(?!\d)")


def date_from_name(name: str):
    """Data nel nome ("2026-02-13 07.jpg", "IMG_20260213_0712.jpg", "13-02-2026.pdf") → timestamp, o None."""
    m = _RE_ISO.search(name)
    if m:
        t = _noon(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if t:
            return t
    m = _RE_DMY.search(name)
    if m:
        return _noon(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def exif_date(path: str):
    """Data di scatto dalla foto (EXIF), o None."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            ex = im.getexif()
            v = None
            try:
                sub = ex.get_ifd(0x8769)
                v = sub.get(0x9003) or sub.get(0x9004)
            except Exception:
                v = None
            v = v or ex.get(0x0132)
        if v:
            m = re.match(r"(\d{4}):(\d{2}):(\d{2})", str(v))
            if m and m.group(1) != "0000":
                return _noon(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except Exception:
        pass
    return None


def document_date(path: str, name: str, ext: str, mtime: float) -> float:
    """Priorità: EXIF → nome file → data di modifica."""
    if ext in IMAGE_EXT:
        t = exif_date(path)
        if t:
            return t
    return date_from_name(name) or mtime


# ═══════════════════════════ Estrazione contenuto ═══════════════════════════

def extract_pdf_text(path: str) -> str:
    try:
        import pdfplumber
        parts, total = [], 0
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:MAX_PDF_PAGES]:
                t = page.extract_text() or ""
                parts.append(t)
                total += len(t)
                if total >= MAX_TEXT_CHARS:
                    break
        return "\n".join(parts)[:MAX_TEXT_CHARS]
    except Exception as e:
        logger.debug("PDF non leggibile %s: %s", path, e)
        return ""


def extract_docx_text(path: str) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        xml = re.sub(r"</w:p>", "\n", xml)
        txt = re.sub(r"<[^>]+>", "", xml)
        import html as _h
        return _h.unescape(txt)[:MAX_TEXT_CHARS]
    except Exception as e:
        logger.debug("DOCX non leggibile %s: %s", path, e)
        return ""


def extract_plain_text(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return f.read(MAX_TEXT_CHARS * 2).decode("utf-8", "replace")[:MAX_TEXT_CHARS]
    except Exception:
        return ""


def prepare_image(path: str):
    """(jpeg_bytes, "image/jpeg") ridimensionata per l'AI, oppure (None, None)."""
    try:
        from PIL import Image, ImageOps
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            im = im.convert("RGB")
            im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=80)
            return buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.debug("Immagine non preparabile %s: %s", path, e)
        return None, None


def render_pdf_first_page(path: str):
    """Prima pagina di un PDF come JPEG (per PDF scansionati), oppure (None, None)."""
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(path)
        pil = doc[0].render(scale=1.5).to_pil().convert("RGB")
        pil.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        buf = io.BytesIO()
        pil.save(buf, "JPEG", quality=80)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.debug("PDF non renderizzabile %s: %s", path, e)
        return None, None


# ═══════════════════════════ Scansione cartelle ═════════════════════════════

def kind_of(ext: str) -> str:
    if ext in IMAGE_EXT:
        return "image"
    if ext in PDF_EXT:
        return "pdf"
    if ext in DOC_EXT:
        return "doc"
    if ext in TEXT_EXT:
        return "text"
    return "other"


def is_sensitive(name: str) -> bool:
    n = name.lower()
    return n.startswith(".") or n in _SENSITIVE_NAMES or os.path.splitext(n)[1] in _SENSITIVE_EXT


def scan_folder(root: str, recursive: bool = True) -> list:
    """Elenco dei file della cartella: [{path,name,ext,kind,size,mtime}]. Non segue i link simbolici."""
    out = []
    try:
        base = Path(root).resolve()
    except Exception:
        return out
    if not base.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in _SKIP_DIRS] if recursive else []
        for fn in filenames:
            if is_sensitive(fn):
                continue
            full = os.path.join(dirpath, fn)
            try:
                if os.path.islink(full):
                    continue
                st = os.stat(full)
            except OSError:
                continue
            ext = os.path.splitext(fn)[1].lower()
            out.append({"path": full, "name": fn, "ext": ext, "kind": kind_of(ext),
                        "size": st.st_size, "mtime": st.st_mtime})
            if len(out) >= MAX_FILES:
                return out
    return out


# ═══════════════════════════ Indice SQLite ══════════════════════════════════

class FileIndex:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS files(
                    path TEXT PRIMARY KEY, folder TEXT, name TEXT, ext TEXT, kind TEXT,
                    size INTEGER, mtime REAL, date_ts REAL,
                    name_n TEXT DEFAULT '', text TEXT DEFAULT '', text_n TEXT DEFAULT '',
                    descr TEXT DEFAULT '', descr_n TEXT DEFAULT '',
                    state TEXT DEFAULT 'meta', tries INTEGER DEFAULT 0, indexed_at REAL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS idx_files_folder ON files(folder);
                CREATE INDEX IF NOT EXISTS idx_files_state ON files(state);
                CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
            """)

    def _conn(self):
        c = sqlite3.connect(str(self.db_path), timeout=15)
        c.row_factory = sqlite3.Row
        return c

    # -- scansione -----------------------------------------------------------
    @staticmethod
    def _upsert_rec(c, root_s: str, r: dict):
        """Inserisce/aggiorna UN file (stato iniziale: 'meta' = da leggere, 'done' per i tipi non leggibili)."""
        rel = os.path.relpath(r["path"], root_s)
        date_ts = document_date(r["path"], r["name"], r["ext"], r["mtime"])
        state = "done" if r["kind"] == "other" else "meta"
        c.execute("""INSERT INTO files(path,folder,name,ext,kind,size,mtime,date_ts,name_n,text,text_n,descr,descr_n,state,tries,indexed_at)
                     VALUES(?,?,?,?,?,?,?,?,?,'','','','',?,0,?)
                     ON CONFLICT(path) DO UPDATE SET folder=excluded.folder,name=excluded.name,ext=excluded.ext,
                       kind=excluded.kind,size=excluded.size,mtime=excluded.mtime,date_ts=excluded.date_ts,
                       name_n=excluded.name_n,text='',text_n='',descr='',descr_n='',state=excluded.state,tries=0,
                       indexed_at=excluded.indexed_at""",
                  (r["path"], root_s, r["name"], r["ext"], r["kind"], r["size"], r["mtime"], date_ts,
                   norm(os.path.splitext(rel)[0]), state, time.time()))

    def sync_folder(self, root: str, recs: list):
        """Allinea l'indice con l'elenco file: nuovi/cambiati → 'meta', spariti → eliminati."""
        root_s = str(Path(root).resolve()) if Path(root).exists() else str(root)
        seen = set()
        with self._conn() as c:
            existing = {r["path"]: (r["mtime"], r["size"]) for r in
                        c.execute("SELECT path, mtime, size FROM files WHERE folder=?", (root_s,))}
            for r in recs:
                seen.add(r["path"])
                if existing.get(r["path"]) == (r["mtime"], r["size"]):
                    continue
                self._upsert_rec(c, root_s, r)
            for p in set(existing) - seen:
                c.execute("DELETE FROM files WHERE path=?", (p,))

    def upsert_one(self, root: str, rec: dict):
        """Aggiunge/aggiorna un singolo file (senza toccare gli altri)."""
        root_s = str(Path(root).resolve()) if Path(root).exists() else str(root)
        with self._conn() as c:
            ex = c.execute("SELECT mtime,size FROM files WHERE path=?", (rec["path"],)).fetchone()
            if ex and (ex["mtime"], ex["size"]) == (rec["mtime"], rec["size"]):
                return
            self._upsert_rec(c, root_s, rec)

    def prune_folders(self, valid_roots: list):
        roots = []
        for r in valid_roots:
            try:
                roots.append(str(Path(r).resolve()))
            except Exception:
                roots.append(str(r))
        with self._conn() as c:
            if roots:
                q = ",".join("?" * len(roots))
                c.execute(f"DELETE FROM files WHERE folder NOT IN ({q})", roots)
            else:
                c.execute("DELETE FROM files")

    # -- contenuto -----------------------------------------------------------
    def next_pending(self, vision_usable: bool):
        with self._conn() as c:
            if vision_usable:
                row = c.execute("""SELECT * FROM files WHERE state IN ('meta','novision')
                                   ORDER BY (kind='image' OR state='novision') ASC, date_ts DESC LIMIT 1""").fetchone()
            else:
                # senza visione le immagini restano "in attesa": niente ciclo infinito
                c.execute("UPDATE files SET state='novision' WHERE state='meta' AND kind='image'")
                row = c.execute("SELECT * FROM files WHERE state='meta' ORDER BY date_ts DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    def set_content(self, path: str, text: str = None, descr: str = None, state: str = "done"):
        with self._conn() as c:
            cur = c.execute("SELECT text, text_n, descr, descr_n FROM files WHERE path=?", (path,)).fetchone()
            if not cur:
                return
            t, tn, d, dn = cur["text"], cur["text_n"], cur["descr"], cur["descr_n"]
            if text is not None:
                t, tn = text[:SNIPPET_CHARS], norm(text[:MAX_TEXT_CHARS])
            if descr is not None:
                d, dn = descr[:1500], norm(descr[:1500])
            c.execute("UPDATE files SET text=?,text_n=?,descr=?,descr_n=?,state=?,indexed_at=? WHERE path=?",
                      (t, tn, d, dn, state, time.time(), path))

    def bump_try(self, path: str, give_up_after: int = 3):
        with self._conn() as c:
            c.execute("UPDATE files SET tries=tries+1 WHERE path=?", (path,))
            c.execute("UPDATE files SET state='err' WHERE path=? AND tries>=?", (path, give_up_after))

    # -- contatori visione (per giorno) --------------------------------------
    def vision_used_today(self) -> int:
        key = "vision:" + date.today().isoformat()
        with self._conn() as c:
            r = c.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
            return int(r["v"]) if r else 0

    def vision_inc(self):
        key = "vision:" + date.today().isoformat()
        with self._conn() as c:
            c.execute("INSERT INTO meta(k,v) VALUES(?,'1') ON CONFLICT(k) DO UPDATE SET v=CAST(v AS INTEGER)+1", (key,))
            c.execute("DELETE FROM meta WHERE k LIKE 'vision:%' AND k<>?", (key,))

    # -- statistiche e ricerca -----------------------------------------------
    def stats(self) -> dict:
        with self._conn() as c:
            by_state = {r["state"]: r["n"] for r in c.execute("SELECT state, COUNT(*) n FROM files GROUP BY state")}
            by_kind = {r["kind"]: r["n"] for r in c.execute("SELECT kind, COUNT(*) n FROM files GROUP BY kind")}
            described = c.execute("SELECT COUNT(*) FROM files WHERE kind='image' AND descr<>''").fetchone()[0]
            total = c.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            pdf_readable = c.execute("SELECT COUNT(*) FROM files WHERE kind='pdf' AND text_n<>''").fetchone()[0]
            pdf_scanned = c.execute("SELECT COUNT(*) FROM files WHERE kind='pdf' AND state='novision' "
                                    "AND descr=''").fetchone()[0]
        return {"total": total, "by_state": by_state, "by_kind": by_kind, "described": described,
                "pending": by_state.get("meta", 0), "waiting_vision": by_state.get("novision", 0),
                "pdf_readable": pdf_readable, "pdf_scanned": pdf_scanned}

    def candidates(self, folders: list, stems: list, kind: str = None, date_from=None, date_to=None, limit: int = 600,
                   ranges: list = None, soft_text: bool = False):
        """Righe candidate: filtri SQL grossolani (cartella/tipo/data/parole); il punteggio è in Python.
        ranges=[(da,a),…] sostituisce date_from/date_to; con soft_text=True i PDF/documenti/testi NON vengono
        scartati per la data del file (si decide poi dal loro contenuto)."""
        where, args = [], []
        if folders:                                   # cartelle = radici: filtro sul percorso (gestisce cartelle annidate)
            parts = []
            for r in folders:
                esc = str(r).rstrip(os.sep).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                parts.append("path LIKE ? ESCAPE '\\'"); args.append(esc + os.sep + "%")
            where.append("(" + " OR ".join(parts) + ")")
        if kind:
            where.append("kind=?"); args.append(kind)
        if ranges:
            rparts = []
            for a, b in ranges:
                rparts.append("(date_ts>=? AND date_ts<?)"); args += [a, b]
            if soft_text:
                rparts.append("kind IN ('pdf','doc','text')")
            where.append("(" + " OR ".join(rparts) + ")")
        else:
            if date_from is not None:
                where.append("date_ts>=?"); args.append(date_from)
            if date_to is not None:
                where.append("date_ts<?"); args.append(date_to)
        if stems:
            ors = []
            for s in stems:
                ors.append("(name_n LIKE ? OR descr_n LIKE ? OR text_n LIKE ? OR folder LIKE ?)"); args += [f"%{s}%"] * 4
            where.append("(" + " OR ".join(ors) + ")")
        sql = "SELECT * FROM files" + (" WHERE " + " AND ".join(where) if where else "") + \
              " ORDER BY date_ts DESC LIMIT ?"
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql, args + [limit])]


# ═══════════════════════════ Interpretazione della richiesta ════════════════

_STOP = set("""mandami inviami rimandami rinviami rinvia rimanda manda invia dammi trovami cercami cerca trova recupera
mostrami vorrei voglio puoi potresti per favore piacere il lo la le li gli i un uno una un' del dello della dei degli delle
di da dal dalla dai dalle dallo in nel nella nei nelle nello su sul sulla sui sulle con che e ed a al alla ai alle allo
file files documento documenti foto fotografia fotografie immagine immagini pdf scansione scansioni cartella
mio mia miei mie tutti tutte tutto quello quella quelli quelle ho hai ha c e' era erano sono mi ti ci piu poi anche
ultimo ultima ultimi ultime scorso scorsa questo questa dove dov grazie ciao scusa ora adesso subito jpg jpeg png
scritto scritta scritte scritti contiene contenente contengono parla parlano riguarda riguardano riguardante
relativo relativa relativi relative archivio archivi dentro presente presenti nome chiamato chiamata intitolato
intitolata cosa cose roba nella nelle nello nei negli dall dell nell sull all""".split())

_KIND_WORDS = {"foto": "image", "fotografia": "image", "fotografie": "image", "immagine": "image",
               "immagini": "image", "jpg": "image", "jpeg": "image", "png": "image", "pdf": "pdf"}


def _day_range(d: date):
    a = datetime(d.year, d.month, d.day).timestamp()
    return a, a + 86400


# ── Periodi richiesti ("dicembre", "dicembre e gennaio", "13 febbraio 2026") ──
# Un periodo con content=True (mese o giorno scritto esplicitamente) viene cercato ANCHE dentro il
# testo dei file ("Mese di competenza: dicembre 2025", "01/12/2025"): la data di modifica del file
# (quando l'hai scaricato/copiato) NON è la data della bolletta. ieri/oggi/anno restano sulla data del file.
_MONTH_RE = re.compile(r"(?<![a-z])(" + "|".join(_MONTH_NAMES) + r")(?![a-z])(?: (20\d{2})(?!\d))?")
_TEXT_KINDS = ("pdf", "doc", "text")


def _month_period(mon: int, year, today: date) -> dict:
    if year is None:
        year = today.year if mon <= today.month else today.year - 1
    a = datetime(year, mon, 1).timestamp()
    b = datetime(year + (mon == 12), (mon % 12) + 1, 1).timestamp()
    return {"label": f"{_MONTH_NAMES[mon - 1]} {year}", "from": a, "to": b,
            "month": mon, "year": year, "day": None, "content": True}


def _day_period(d: date) -> dict:
    a, b = _day_range(d)
    return {"label": d.strftime("%d/%m/%Y"), "from": a, "to": b,
            "month": d.month, "year": d.year, "day": d.day, "content": True}


@functools.lru_cache(maxsize=256)
def _period_rx(year: int, month: int, day):
    """Espressioni (su testo normalizzato) che provano che un documento parla di quel mese/giorno."""
    mn = _MONTH_NAMES[month - 1]
    name_only = None
    if day:
        words = [rf"(?<!\d)0?{day} {mn} ?{year}(?!\d)"]
        nums = [rf"(?<!\d)0?{day} 0?{month} {year}(?!\d)", rf"(?<!\d){year} 0?{month} 0?{day}(?!\d)",
                rf"(?<!\d){year}{month:02d}{day:02d}(?!\d)"]
    else:
        words = [rf"(?<![a-z]){mn} ?{year}(?!\d)"]
        nums = [rf"(?<!\d)0?{month} {year}(?!\d)", rf"(?<!\d){year} 0?{month}(?!\d)"]
        # nome file col mese ma senza anno ("Bolletta Dicembre.pdf"); se nel nome c'è un ALTRO anno non vale
        name_only = re.compile(rf"(?<![a-z]){mn}(?![a-z])(?! ?20\d{{2}})")
    return [re.compile(w) for w in words], [re.compile(n) for n in nums], name_only


_ANY_DATE_INFO = re.compile(r"(?<![a-z])(" + "|".join(_MONTH_NAMES) + r")(?![a-z])|(?<!\d)20\d{2}(?!\d)")


def period_evidence(row: dict, p: dict) -> float:
    """Quanto il NOME o il TESTO del file dicono che parla del periodo (0 = nessuna prova)."""
    if not p.get("content") or not p.get("month"):
        return 0.0
    rw, rn, rname = _period_rx(p["year"], p["month"], p.get("day"))
    name, text, descr = row.get("name_n") or "", row.get("text_n") or "", row.get("descr_n") or ""
    s = 0.0
    if any(r.search(name) for r in rw + rn):
        s += 4
    elif rname is not None and rname.search(name):
        s += 3
    s += 2 * min(sum(len(r.findall(text)) for r in rw), 3) + 0.75 * min(sum(len(r.findall(text)) for r in rn), 4)
    if descr and any(r.search(descr) for r in rw + rn):
        s += 2
    return s


def _period_score(row: dict, p: dict):
    """(punteggio, forza) con forza in {"content", "date", "weak", None}.
    weak = solo la data di modifica cade nel mese ma il testo del file (letto) non lo conferma:
    NON basta per inviare un file da soli (potrebbe essere la bolletta di un altro mese)."""
    ev = period_evidence(row, p)
    ts = row.get("date_ts") or 0
    in_range = p["from"] <= ts < p["to"]
    if ev > 0:
        return ev + (1.0 if in_range else 0.0), "content"
    if in_range:
        # file di testo che parla di ALTRE date (mesi/anni) ma non di questo → la data di modifica non basta
        # (es. "bolletta di novembre" scaricata a dicembre). Senza nessuna data nel testo vale la data del file.
        if (p.get("content") and p.get("month") and not p.get("day")
                and row.get("kind") in _TEXT_KINDS and _ANY_DATE_INFO.search(row.get("text_n") or "")):
            return 0.0, "weak"
        return 1.0, "date"
    return 0.0, None


_FOLDER_PREP = (r"(?:in|nella|nel|nello|nelle|nei|negli|dentro|su|sulla|sul|dalla|dal|dallo|dalle|dai|dagli|da|"
                r"dall|nell|sull|tra|fra|cartella|cartelle|folder|directory)")


def named_folders(q: str, folders: list) -> list:
    """Cartelle configurate nominate nella frase (q già normalizzata), solo con contesto
    ("nella cartella foto", "in documenti", "dalla cartella archivio")."""
    out = []
    for f in folders or []:
        n = norm(f.get("name", ""))
        if not n:
            continue
        pat = (r"(?<![a-z0-9])" + _FOLDER_PREP + r"(?: di| del| della| dei| delle)?(?: la| il| lo| le| i| gli)? "
               + re.escape(n) + r"(?![a-z0-9])")
        if re.search(pat, q):
            out.append(f)
    return out


def parse_query(text: str, folders: list, today: date = None) -> dict:
    """Estrae da una frase libera: parole chiave, tipo (foto/pdf), periodo, cartella."""
    today = today or date.today()
    q = norm(text)
    words = q.split()
    kind = None
    for w in words:
        if w in _KIND_WORDS:
            kind = _KIND_WORDS[w]
            break
    periods = []
    consumed = set()
    mentions = list(_MONTH_RE.finditer(q))

    # data esplicita: "13 febbraio 2026", "13/02/2026", "2026-02-13"
    m = re.search(r"(?<!\d)(\d{1,2}) (" + "|".join(_MONTH_NAMES) + r")(?: (20\d{2}))?(?!\d)", q)
    iso = re.search(r"(?<!\d)(20\d{2}) (\d{1,2}) (\d{1,2})(?!\d)", q)
    dmy = re.search(r"(?<!\d)(\d{1,2}) (\d{1,2}) (20\d{2})(?!\d)", q)
    try:
        if m and len(mentions) <= 1:
            y = int(m.group(3)) if m.group(3) else today.year
            d0 = date(y, _MONTHS[m.group(2)], int(m.group(1)))
            if not m.group(3) and d0 > today:
                d0 = date(y - 1, d0.month, d0.day)
            periods.append(_day_period(d0))
            consumed |= set(m.group(0).split())
        elif iso and not mentions:
            periods.append(_day_period(date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))))
        elif dmy and not mentions:
            periods.append(_day_period(date(int(dmy.group(3)), int(dmy.group(2)), int(dmy.group(1)))))
    except ValueError:
        periods = []

    if not periods:
        if mentions:                                    # "di dicembre", "dicembre e gennaio", "febbraio 2026"
            seen = set()
            for mm in mentions:
                mon = _MONTHS[mm.group(1)]
                yr = int(mm.group(2)) if mm.group(2) else None
                consumed.add(mm.group(1))
                if mm.group(2):
                    consumed.add(mm.group(2))
                per = _month_period(mon, yr, today)
                if (per["month"], per["year"]) not in seen:
                    seen.add((per["month"], per["year"]))
                    periods.append(per)
        elif "ieri" in words:
            a, b = _day_range(today - timedelta(days=1)); consumed.add("ieri")
            periods.append({"label": "ieri", "from": a, "to": b, "month": None, "year": None, "day": None, "content": False})
        elif "oggi" in words:
            a, b = _day_range(today); consumed.add("oggi")
            periods.append({"label": "oggi", "from": a, "to": b, "month": None, "year": None, "day": None, "content": False})
        else:
            my = re.search(r"(?<!\d)(20\d{2})(?!\d)", q)
            if my:                                      # solo anno: "documenti del 2025"
                y = int(my.group(1))
                periods.append({"label": str(y), "from": datetime(y, 1, 1).timestamp(),
                                "to": datetime(y + 1, 1, 1).timestamp(), "month": None, "year": y,
                                "day": None, "content": False})
                consumed.add(my.group(1))
    date_from = min((p["from"] for p in periods), default=None)
    date_to = max((p["to"] for p in periods), default=None)

    # cartella nominata: conta solo se introdotta da una preposizione o da "cartella"
    # ("nella cartella foto", "in documenti"); una parola generica come "foto" da sola NON è una cartella
    folder_roots = []
    for f in named_folders(q, folders):
        folder_roots.append(f["path"]); consumed |= set(norm(f["name"]).split())

    wants_all = bool(re.search(r"(?<![a-z])(tutti|tutte)(?![a-z])", q))
    kws = []
    for w in words:
        if w in _STOP or w in consumed or w in _KIND_WORDS or w.isdigit() or len(w) < 3:
            continue
        kws.append(w)
    return {"keywords": kws, "stems": [stem(w) for w in kws], "kind": kind,
            "date_from": date_from, "date_to": date_to, "periods": periods,
            "folders": folder_roots, "all": wants_all}


def effective_roots(folders: list, subfolders: bool = True) -> list:
    """Radici da scansionare. Con le sottocartelle attive, una cartella contenuta in un'altra configurata
    viene già scansionata dalla cartella esterna: scansionarla due volte rielaborerebbe gli stessi file
    a ogni giro (e sprecherebbe la quota dell'AI)."""
    roots, seen = [], set()
    for f in folders or []:
        try:
            r = str(Path(f["path"]).resolve())
        except Exception:
            r = str(f["path"])
        if r not in seen:
            seen.add(r); roots.append(r)
    if not subfolders:
        return roots
    return [r for r in roots
            if not any(o != r and r.startswith(o.rstrip(os.sep) + os.sep) for o in roots)]


def _roots(folders: list) -> list:
    out = []
    for f in folders:
        try:
            out.append(str(Path(f["path"]).resolve()))
        except Exception:
            out.append(str(f["path"]))
    return out


def _score_rows(rows: list, stems: list, need: int) -> list:
    out = []
    for r in rows:
        matched, score, why = 0, 0.0, set()
        fold_n = norm(os.path.basename(str(r.get("folder") or "").rstrip("/\\")))
        for s in stems:
            hit = False
            if s in r["name_n"]:
                score += 3; hit = True; why.add("nome")
            if fold_n and s in fold_n:
                score += 2; hit = True; why.add("cartella")
            if s in r["descr_n"]:
                score += 2; hit = True; why.add("contenuto immagine")
            if s in r["text_n"]:
                score += 1; hit = True; why.add("testo")
            matched += hit
        if stems and matched < need:
            continue
        if stems and matched == len(stems):
            score += 1.5                                  # tutte le parole presenti
        out.append({**r, "score": score, "matched": matched, "why": sorted(why)})
    out.sort(key=lambda x: (x["matched"], x["score"], x["date_ts"] or 0), reverse=True)
    return out


def _rank_periods(rows: list, periods: list) -> list:
    """Per ogni periodo: i file che lo provano (nel nome/testo o per data), dal più al meno pertinente.
    Un file il cui testo parla solo di ALTRI mesi/anni non entra, anche se la sua data di modifica coincide."""
    per = []
    for i, p in enumerate(periods):
        hits = []
        for r in rows:
            ps, strength = _period_score(r, p)
            if not strength or strength == "weak":      # "weak" = il testo del file parla di altri periodi
                continue
            why = set(r["why"])
            why.add({"content": "periodo nel testo", "date": "data del file"}[strength])
            hits.append({**r, "score": r["score"] + ps, "pscore": ps, "pstrength": strength,
                         "period": i, "why": sorted(why)})
        hits.sort(key=lambda x: (x["matched"], x["score"], x["date_ts"] or 0), reverse=True)
        per.append(hits)
    return per


def clear_winner(rows: list, n_stems: int) -> bool:
    """True se il primo risultato è nettamente il migliore (si può inviare senza chiedere)."""
    if not rows:
        return False
    if len(rows) == 1:
        return True
    top, sec = rows[0], rows[1]
    return bool((n_stems > 0 and top["matched"] == n_stems and sec["matched"] < n_stems)
                or (top["score"] >= 3 and top["score"] >= 2 * sec["score"]))


def _clear_group(rows: list, n_stems: int) -> bool:
    """Per un periodo: True se un file vince nettamente. Dopo le parole chiave conta quanto il file parla
    DAVVERO di quel periodo (il mese scritto nel testo pesa più di una data di emissione/scadenza)."""
    if not rows:
        return False
    if len(rows) == 1:
        return True
    top, sec = rows[0], rows[1]
    if n_stems > 0 and top["matched"] == n_stems and sec["matched"] < n_stems:
        return True
    return bool(top["matched"] == sec["matched"] and top["pscore"] >= 3 and top["pscore"] >= 2 * sec["pscore"])


def search(index: FileIndex, text: str, folders: list, limit: int = 8, today: date = None) -> dict:
    """Cerca nei file indicizzati. Ritorna {"query":…, "results":[…], "partial": bool, "multi": bool,
    "groups":[…], "missing":[…]}.
    Servono TUTTE le parole (con 3+ parole: il 60%). Se non c'è nessun file così, ripiega sui file che
    ne contengono almeno una e li segnala come "partial" (il chiamante non li invia da solo).
    Periodi (mesi/giorni scritti nella frase): il file deve citarli nel nome o nel TESTO (anche dentro i PDF);
    con 2+ periodi ("dicembre e gennaio") si cerca il file migliore per ciascuno (groups) e si dichiara
    quelli senza file (missing)."""
    pq = parse_query(text, folders, today)
    roots = _roots(folders)
    if pq["folders"]:
        sel = []
        for p in pq["folders"]:
            try:
                sel.append(str(Path(p).resolve()))
            except Exception:
                sel.append(p)
        roots = [r for r in roots if r in sel] or roots
    periods = pq.get("periods") or []
    stems = pq["stems"]
    n = len(stems)
    need = 0 if n == 0 else (n if n <= 2 else math.ceil(n * 0.6))

    if not periods:                                           # nessuna data nella frase: comportamento di sempre
        rows = index.candidates(roots, stems, pq["kind"], pq["date_from"], pq["date_to"])
        out = _score_rows(rows, stems, need)
        partial = False
        if not out and n >= 2:
            out = _score_rows(rows, stems, 1)
            partial = bool(out)
        return {"query": pq, "results": out[:limit], "partial": partial, "multi": False, "groups": [], "missing": []}

    soft = all(p.get("content") for p in periods)
    rows = index.candidates(roots, stems, pq["kind"], ranges=[(p["from"], p["to"]) for p in periods], soft_text=soft)
    per = _rank_periods(_score_rows(rows, stems, need), periods)
    per_loose = None                                          # (almeno 1 parola) calcolato solo se serve
    groups = []
    for i, p in enumerate(periods):
        rows_i, part = per[i], False
        if not rows_i and n >= 2:
            if per_loose is None:
                per_loose = _rank_periods(_score_rows(rows, stems, 1), periods)
            rows_i = per_loose[i]
            part = bool(rows_i)
        groups.append({"label": p["label"], "rows": rows_i[:limit], "partial": part,
                       "clear": (not part) and _clear_group(rows_i, n)})

    if len(periods) == 1:
        results = groups[0]["rows"]
    else:                                                     # un file (o pochi candidati) per ciascun mese
        results, seen = [], set()
        for g in groups:
            for r in (g["rows"][:1] if g["clear"] else g["rows"][:3]):
                if r["path"] not in seen:
                    seen.add(r["path"]); results.append(r)
        results = results[:max(limit, 3 * len(periods))]
    return {"query": pq, "results": results, "partial": any(g["partial"] for g in groups),
            "multi": len(periods) >= 2, "groups": groups,
            "missing": [g["label"] for g in groups if not g["rows"]]}


def snippet(row: dict, stems: list, width: int = 90) -> str:
    """Breve anteprima del contenuto: descrizione dell'immagine o frase del testo con la parola cercata."""
    d = (row.get("descr") or "").strip()
    if d:
        m = re.search(r"Descrizione:\s*(.+?)(?:\.\s|\n|$)", d, re.S)
        return (m.group(1) if m else d)[:width * 2].strip()
    t = re.sub(r"\s+", " ", row.get("text") or "").strip()
    if not t:
        return ""
    tn = norm(t)
    for s in stems:
        i = tn.find(s)
        if i >= 0:
            # posizione approssimata nel testo originale (la normalizzazione conserva l'ordine)
            j = max(0, min(len(t) - 1, int(i * len(t) / max(1, len(tn)))))
            a = max(0, j - width // 2)
            return ("…" if a else "") + t[a:a + width].strip() + "…"
    return t[:width].strip() + "…"


_MON_ALT = "|".join(_MONTHS)


def _plain(s: str) -> str:
    """minuscolo e senza accenti, ma CON la punteggiatura (serve per leggere date e numeri)."""
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


def _cap_month(m: str, y: str = None) -> str:
    return m.capitalize() + (f" {y}" if y else "")


_SUPPLIERS = ["enel", "eni", "edison", "a2a", "hera", "iren", "acea", "sorgenia", "e.on", "octopus",
              "plenitude", "engie", "illumia", "wekiwi", "acquedotto", "tim", "vodafone", "fastweb",
              "wind", "iliad", "poste"]


def doc_label(row: dict, max_chars: int = 4000) -> str:
    """Titolo leggibile ricavato dal CONTENUTO («Busta paga · Luglio 2026», «Bolletta Enel gas»…).
    Ritorna "" se il tipo di documento non è riconosciuto con sicurezza: in quel caso si usa l'anteprima."""
    try:
        t = _plain((row.get("text") or "")[:max_chars])
        if len(t) < 30:
            return ""
        head = t[:1500]

        # busta paga / cedolino
        if re.search(r"cedolino|busta paga|foglion|dati identificativi aziendali|mese di retribuzione|prospetto paga", t) \
                and re.search(r"inps|inail|retribuzione|trattenute|netto", t):
            m = re.search(r"(?:mese di retribuzione|periodo di (?:paga|retribuzione)|mensilita)\W{0,4}(" + _MON_ALT + r")\W{0,4}(20\d\d)?", t)
            if not m:
                m = re.search(r"\b(" + _MON_ALT + r")\W{0,3}(20\d\d)\b", t[:1200])
            extra = ""
            if re.search(r"tredicesima|13\W{0,2}a? ?mensilita", t):
                extra = " (tredicesima)"
            elif re.search(r"quattordicesima|14\W{0,2}a? ?mensilita", t):
                extra = " (quattordicesima)"
            return "Busta paga" + (" · " + _cap_month(m.group(1), m.group(2)) if m else "") + extra

        # Certificazione Unica / redditi
        if re.search(r"certificazione unica|\bcu 20\d\d\b", t) or re.search(r"\bredditi 20\d\d\b", t):
            y = re.search(r"\bredditi (20\d\d)\b", t)
            cu = bool(re.search(r"certificazione unica|\bcu\b|sostituto d.?imposta", t))
            if cu:
                return "Certificazione Unica" + (f" · redditi {y.group(1)}" if y else "")
            return "Redditi" + (f" {y.group(1)}" if y else "")

        # catasto / visure
        if re.search(r"visura|planimetria|estratto di mappa|elaborato planimetrico|ufficio provinciale\W+territorio|catast", t):
            kind = ("Visura" if "visura" in t else "Planimetria" if "planimetria" in t else
                    "Estratto di mappa" if "estratto di mappa" in t else "Documento")
            cat = " catastale" if re.search(r"catast|territorio|agenzia delle entrate", t) else ""
            d = re.search(r"\bdata:? ?(\d{1,2}[/.-]\d{1,2}[/.-]20\d\d)", head)
            return kind + cat + (f" · {d.group(1)}" if d else "")

        # bollette
        sup = next((x for x in _SUPPLIERS if re.search(r"(?<![a-z])" + re.escape(x) + r"(?![a-z])", head)), None)
        if sup and re.search(r"n\W{0,3}cliente|codice cliente|bolletta|fattura|pod\b|pdr\b|energia elettrica|\bgas\b", head):
            luce = bool(re.search(r"energia elettrica|\bpod\b|\bluce\b", head))
            gas = bool(re.search(r"(?<![a-z])gas(?![a-z])|\bpdr\b", head))
            tipo = "luce e gas" if (luce and gas and re.search(r"dual", head)) else \
                   "luce" if (luce and not gas) else "gas" if (gas and not luce) else \
                   ("luce" if head.find("energia elettrica") != -1 and (head.find("gas") == -1 or head.find("energia elettrica") < head.find("gas")) else "gas")
            per = re.search(r"dal (\d{1,2}[/.]\d{1,2}(?:[/.]20\d\d)?) al (\d{1,2}[/.]\d{1,2}[/.]20\d\d)", t)
            sc = re.search(r"scadenza:? ?(\d{1,2}[/.]\d{1,2}[/.]20\d\d)", t)
            tail = f" · dal {per.group(1)} al {per.group(2)}" if per else (f" · scad. {sc.group(1)}" if sc else "")
            return f"Bolletta {sup.upper() if len(sup) <= 3 else sup.capitalize()} {tipo}{tail}"
    except Exception:
        return ""
    return ""


# ═══════════════════════════ Cartelle (anche quelle create dopo) ═══════════

_DIR_CACHE = {"ts": 0.0, "key": None, "dirs": []}
_DIR_TTL = 10.0           # secondi: una cartella appena creata si trova entro pochi secondi
_DIR_MAX_DEPTH = 6
_DIR_CAP = 4000


def list_dirs(folders: list) -> list:
    """Tutte le cartelle sotto le radici configurate, lette DAL DISCO (non dall'indice), così una cartella
    creata un minuto fa si può già richiamare. [{path, name, aliases:set, depth, root}]."""
    roots = _roots(folders)
    cfg_names = {}
    for f in folders or []:
        try:
            cfg_names[str(Path(f["path"]).resolve())] = norm(f.get("name", ""))
        except Exception:
            pass
    key = tuple(roots)
    now = time.time()
    if _DIR_CACHE["key"] == key and now - _DIR_CACHE["ts"] < _DIR_TTL:
        return _DIR_CACHE["dirs"]
    out = []
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for dirpath, dirnames, _files in os.walk(base, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d.lower() not in _SKIP_DIRS
                                 and not os.path.islink(os.path.join(dirpath, d)))
            rel = os.path.relpath(dirpath, base)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth > _DIR_MAX_DEPTH:
                dirnames[:] = []
                continue
            aliases = {norm(os.path.basename(dirpath))}
            if depth == 0 and cfg_names.get(root):
                aliases.add(cfg_names[root])
            aliases = {a for a in aliases if len(a) >= 3}
            if aliases:
                out.append({"path": dirpath, "name": os.path.basename(dirpath), "aliases": aliases,
                            "depth": depth, "root": root})
            if len(out) >= _DIR_CAP:
                break
    _DIR_CACHE.update(ts=now, key=key, dirs=out)
    return out


_DIR_CUE = re.compile(r"\b(cartella|cartelle|directory|folder)\b")
_DIR_CUE2 = re.compile(r"\b(contenuto|tutto il contenuto|tutti i file|tutti i documenti|tutte le foto|tutto)\s+"
                       r"(?:di|del|dello|della|dei|delle|dentro|in|nella|nel)\b")


def find_dirs(text: str, folders: list) -> list:
    """Cartelle nominate nella frase («la cartella bollette», «il contenuto di Fatture 2026»).
    Serve un segnale esplicito (parola «cartella» o «contenuto di»): senza, «mandami bollette» resta
    una ricerca per parole. Vince il nome più lungo (più specifico); a pari nome, la più vicina alla radice."""
    qn = norm(text)
    if not (_DIR_CUE.search(qn) or _DIR_CUE2.search(qn)):
        return []
    hits = []
    for d in list_dirs(folders):
        for a in d["aliases"]:
            if re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", qn):
                hits.append((len(a), d))
                break
    if not hits:
        return []
    best = max(h[0] for h in hits)
    res = [d for n, d in hits if n == best]
    res.sort(key=lambda d: (d["depth"], d["path"]))
    return res


_DIR_GENERIC = {"cartella", "cartelle", "directory", "folder", "contenuto", "tutto", "tutti", "tutte", "file",
                "files", "mandami", "inviami", "dammi", "manda", "invia", "mostrami", "rimandami"}


def dir_request(text: str, folders: list, dirs: list):
    """La frase chiede solo «il contenuto della cartella»? Ritorna (True, kind|None).
    Se contiene altre parole da cercare o un periodo («bollette di luglio dalla cartella casa») → (False, None):
    in quel caso si fa la ricerca normale (il nome della cartella fa già parte del percorso dei file)."""
    rest = norm(text)
    for d in dirs:                                    # il nome della cartella NON conta come parola da cercare
        for a in sorted(d["aliases"], key=len, reverse=True):
            rest = re.sub(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", " ", rest)
    pq = parse_query(rest, folders)
    resid = [k for k in pq["keywords"] if k not in _DIR_GENERIC]
    if resid or pq.get("periods"):
        return False, None
    return True, pq.get("kind")


def subdir_names(dirpath: str) -> list:
    try:
        return sorted(e.name for e in os.scandir(dirpath)
                      if e.is_dir(follow_symlinks=False) and not e.name.startswith(".")
                      and e.name.lower() not in _SKIP_DIRS)
    except OSError:
        return []


def dir_rows(dirpath: str, folders: list, index=None) -> list:
    """File che stanno DIRETTAMENTE nella cartella (non nelle sottocartelle), letti dal disco, dal più
    recente. Se il file è già nell'indice se ne riusa testo/descrizione (per il titolo leggibile)."""
    dp = str(Path(dirpath).resolve())
    if not any(dp == r or dp.startswith(r.rstrip(os.sep) + os.sep) for r in _roots(folders)):
        return []                                     # fuori dalle cartelle configurate: mai
    recs = scan_folder(dirpath, recursive=False)
    known = {}
    if index is not None:
        try:
            for r in index.candidates([str(Path(dirpath).resolve())], [], limit=5000):
                known[r["path"]] = r
        except Exception:
            pass
    rows = []
    for r in recs:
        k = known.get(r["path"], {})
        rows.append({"path": r["path"], "folder": str(Path(dirpath).resolve()), "name": r["name"], "ext": r["ext"],
                     "kind": r["kind"], "size": r["size"], "mtime": r["mtime"],
                     "date_ts": k.get("date_ts") or document_date(r["path"], r["name"], r["ext"], r["mtime"]),
                     "score": 0, "matched": 0, "descr": k.get("descr", ""), "text": k.get("text", "")})
    rows.sort(key=lambda x: (-(x["date_ts"] or 0), x["name"].lower()))
    return rows


def path_allowed(path: str, folders: list) -> bool:
    """True se il file sta DENTRO una delle cartelle configurate (nessuna uscita via ../ o link)."""
    try:
        p = Path(path).resolve()
    except Exception:
        return False
    for root in _roots(folders):
        try:
            p.relative_to(root)
            return p.is_file() and not is_sensitive(p.name)
        except ValueError:
            continue
    return False


# ═══════════════════════════ Indicizzatore in background ════════════════════

def _is_rate_limit(err: Exception) -> bool:
    es = str(err).lower()
    return any(k in es for k in ("429", "rate limit", "rate_limit", "quota", "resource_exhausted", "too many requests"))


class FileIndexer:
    """Mantiene l'indice aggiornato a piccoli passi. Non fa nulla se la ricerca è spenta."""

    def __init__(self, db_path: Path = DB_PATH, describe_cb=None, settings_cb=None, available_cb=None):
        self.index = FileIndex(db_path)
        self.describe_cb = describe_cb            # async (bytes, mime, prompt) -> str
        self._available_cb = available_cb         # () -> bool: c'è un provider con visione?
        self._settings_cb = settings_cb
        self._rescan = True
        self._queued: set = set()
        self._last_scan = 0.0
        self._vision_pause_until = 0.0
        self._idle = 15.0
        self.status = {"active": False, "scanning": False, "last_scan": 0, "vision_paused": False}

    # -- impostazioni --------------------------------------------------------
    def settings(self) -> dict:
        if self._settings_cb:
            return self._settings_cb()
        from agent import file_inbox as fi
        cfg = fi.load_settings()
        s = dict(cfg.get("search") or {})
        s["folders"] = cfg.get("folders") or []
        return s

    def request_rescan(self):
        self._rescan = True

    def queue_file(self, path: str):
        self._queued.add(str(path))

    def vision_available(self) -> bool:
        try:
            return bool(self.describe_cb and (self._available_cb() if self._available_cb else True))
        except Exception:
            return False

    def vision_usable(self, st: dict) -> bool:
        return bool(st.get("vision") and self.vision_available() and time.time() >= self._vision_pause_until
                    and self.index.vision_used_today() < int(st.get("vision_per_day", 100)))

    # -- ciclo principale ----------------------------------------------------
    async def run(self):
        logger.info("FileIndexer avviato (attivo solo se la ricerca file è abilitata nella pagina web)")
        while True:
            try:
                await self.cycle()
            except asyncio.CancelledError:
                raise
            except Exception as e:                       # non deve MAI fermarsi
                logger.warning("FileIndexer errore: %s", e)
            await asyncio.sleep(self._idle)

    async def cycle(self, time_budget: float = 25.0):
        st = self.settings()
        folders = st.get("folders") or []
        if not (st.get("enabled") and folders):
            self.status["active"] = False
            self._idle = 30.0
            return
        self.status["active"] = True
        now = time.time()
        if self._rescan or now - self._last_scan > SCAN_INTERVAL_S:
            await self._scan(st)
        if self._queued:
            await self._index_queued(st)
        t0 = time.time()
        did = 0
        while time.time() - t0 < time_budget:
            if not await self._process_one(st):
                break
            did += 1
        self._idle = 1.0 if did else 20.0
        self.status["vision_paused"] = time.time() < self._vision_pause_until

    async def _scan(self, st: dict):
        self.status["scanning"] = True
        try:
            roots = effective_roots(st["folders"], bool(st.get("subfolders", True)))
            for root in roots:
                recs = await asyncio.to_thread(scan_folder, root, bool(st.get("subfolders", True)))
                await asyncio.to_thread(self.index.sync_folder, root, recs)
            await asyncio.to_thread(self.index.prune_folders, roots)
            self._last_scan = time.time()
            self._rescan = False
            self.status["last_scan"] = self._last_scan
            s = await asyncio.to_thread(self.index.stats)
            logger.info("FileIndexer: scansione completata — %d file (%d da leggere, %d immagini in attesa di visione)",
                        s["total"], s["pending"], s["waiting_vision"])
        finally:
            self.status["scanning"] = False

    async def _index_queued(self, st: dict):
        paths, self._queued = list(self._queued), set()
        eff = effective_roots(st["folders"], bool(st.get("subfolders", True)))
        for p in paths:
            for root_s in eff:
                f = {"path": root_s}
                try:
                    root = Path(root_s).resolve()
                    Path(p).resolve().relative_to(root)
                except Exception:
                    continue
                name = os.path.basename(p)
                if is_sensitive(name) or not os.path.isfile(p):
                    break
                stt = os.stat(p)
                ext = os.path.splitext(name)[1].lower()
                rec = {"path": str(Path(p).resolve()), "name": name, "ext": ext, "kind": kind_of(ext),
                       "size": stt.st_size, "mtime": stt.st_mtime}
                await asyncio.to_thread(self.index.upsert_one, f["path"], rec)
                break

    async def _process_one(self, st: dict) -> bool:
        """Elabora UN file in attesa. False se non c'è più nulla da fare ora."""
        vis = self.vision_usable(st)
        row = await asyncio.to_thread(self.index.next_pending, vis)
        if not row:
            return False
        path, kind = row["path"], row["kind"]
        try:
            if kind == "pdf":
                if row["state"] == "novision":                     # già senza testo: serve la visione
                    return await self._vision(row, st, pdf=True)
                text = await asyncio.to_thread(extract_pdf_text, path)
                if len(text.strip()) >= 30:
                    await asyncio.to_thread(self.index.set_content, path, text, None, "done")
                else:                                              # PDF scansionato: serve la visione
                    await asyncio.to_thread(self.index.set_content, path, text, None, "novision")
            elif kind == "doc":
                text = await asyncio.to_thread(extract_docx_text, path)
                await asyncio.to_thread(self.index.set_content, path, text, None, "done")
            elif kind == "text":
                text = await asyncio.to_thread(extract_plain_text, path)
                await asyncio.to_thread(self.index.set_content, path, text, None, "done")
            elif kind == "image":
                if row["ext"] not in VISION_EXT:
                    await asyncio.to_thread(self.index.set_content, path, None, None, "done")
                else:
                    return await self._vision(row, st, pdf=False)
            else:
                await asyncio.to_thread(self.index.set_content, path, None, None, "done")
        except Exception as e:
            logger.warning("FileIndexer: %s non elaborato: %s", path, e)
            await asyncio.to_thread(self.index.bump_try, path)
        return True

    async def _vision(self, row: dict, st: dict, pdf: bool) -> bool:
        path = row["path"]
        loader = render_pdf_first_page if pdf else prepare_image
        data, mime = await asyncio.to_thread(loader, path)
        if not data:
            await asyncio.to_thread(self.index.set_content, path, None, None, "done")
            return True
        try:
            desc = await asyncio.wait_for(self.describe_cb(data, mime, VISION_PROMPT), timeout=VISION_TIMEOUT_S)
        except Exception as e:
            if _is_rate_limit(e):
                self._vision_pause_until = time.time() + 3600
                logger.warning("FileIndexer: quota della visione esaurita — riprovo tra un'ora (%s)", str(e)[:100])
            else:
                logger.warning("FileIndexer: visione fallita su %s: %s", os.path.basename(path), str(e)[:120])
                await asyncio.to_thread(self.index.bump_try, path)
            return not _is_rate_limit(e)                      # con rate limit ci si ferma
        await asyncio.to_thread(self.index.set_content, path, None, (desc or "").strip(), "done")
        await asyncio.to_thread(self.index.vision_inc)
        await asyncio.sleep(VISION_DELAY_S)
        return True

    # -- per il bot / la pagina web -----------------------------------------
    async def search(self, text: str, limit: int = 8) -> dict:
        st = self.settings()
        res = await asyncio.to_thread(search, self.index, text, st.get("folders") or [], limit)
        res["stats"] = await asyncio.to_thread(self.index.stats)
        return res

    async def stats(self) -> dict:
        st = self.settings()
        s = await asyncio.to_thread(self.index.stats)
        s.update({"enabled": bool(st.get("enabled")), "vision": bool(st.get("vision")),
                  "vision_per_day": int(st.get("vision_per_day", 100)),
                  "vision_used_today": await asyncio.to_thread(self.index.vision_used_today),
                  "vision_available": self.vision_available(), **self.status})
        return s


# ═══════════════════════════ Singleton ══════════════════════════════════════

_INDEXER = None


def get_indexer():
    return _INDEXER


def start_indexer(describe_cb=None, db_path: Path = DB_PATH, settings_cb=None, create_task: bool = True,
                  available_cb=None):
    """Crea (una sola volta) l'indicizzatore e, di norma, lo avvia come task in background."""
    global _INDEXER
    if _INDEXER is None:
        _INDEXER = FileIndexer(db_path=db_path, describe_cb=describe_cb, settings_cb=settings_cb,
                               available_cb=available_cb)
        if create_task:
            asyncio.create_task(_INDEXER.run(), name="file_indexer")
    return _INDEXER


def queue_file(path) -> None:
    """Segnala un file appena salvato: verrà indicizzato al primo giro utile (best effort)."""
    try:
        if _INDEXER is not None:
            _INDEXER.queue_file(str(path))
    except Exception:
        pass
