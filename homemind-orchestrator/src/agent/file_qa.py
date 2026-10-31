"""
agent/file_qa.py — Risponde a DOMANDE sul contenuto dei documenti (buste paga, bollette…).

Esempi:
    "quanto ho preso di stipendio ad agosto?"      → importo netto dalla busta paga di agosto
    "quanti giorni di ferie ho fatto a settembre?" → ferie godute dalla busta paga di settembre
    "quando devo pagare il gas a novembre?"        → importo e scadenza dalla bolletta

Come funziona (nulla viene inventato):
  1. riconosce la domanda (non è una richiesta di inviare il file: quella resta a file_search);
  2. sceglie i documenti giusti nell'indice di file_search (parole + mese/anno nel NOME o nel TESTO);
  3. rilegge il testo completo dei PDF dal disco;
  4. chiede all'AI di rispondere SOLO con ciò che c'è scritto, citando il documento;
  5. controlla che ogni importo scritto nella risposta compaia davvero nel testo dei documenti;
     se no avvisa «controlla sul PDF».

Privacy: il testo dei documenti scelti viene inviato al provider AI configurato → funzione spenta di
default (person_config.json → file_inbox.search.qa = true, interruttore nella scheda 📁 File).
"""

import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Optional

from agent import file_search as fs

logger = logging.getLogger("homemind.file_qa")

MAX_DOCS = 6                    # documenti letti per domanda
MAX_PER_PERIOD = 3
MAX_CHARS_PER_DOC = 9000        # testo inviato all'AI per documento
MAX_CHARS_TOTAL = 26000
MIN_SCORE = 3.0

_SEND_VERBS = re.compile(r"\b(mandami|inviami|rimandami|rinviami|rimanda|rinvia|manda|invia|dammi il file|trovami|"
                         r"cercami|cerca|trova|ritrova|recupera|mostrami|riinvia)\b")
_QUESTION = re.compile(r"\b(quanto|quanti|quante|quanta|quando|qual e|quale|quali|dimmi|che importo|a quanto|"
                       r"di quanto|ho preso|ho guadagnato|devo pagare|ho pagato|ho fatto|mi resta|mi restano|"
                       r"c e scritto|risulta)\b")
# argomenti da documento (una parola sola come "gas" NON basta: potrebbe essere il sensore di Home Assistant)
_PAYROLL = re.compile(r"\b(stipendio|stipendi|busta paga|buste paga|cedolino|cedolini|ferie|permessi|permesso|tfr|"
                      r"tredicesima|quattordicesima|netto in busta|trattenute|irpef|straordinari|straordinario|"
                      r"retribuzione|ore lavorate|guadagnato|contributi inps|inps|malattia|rol)\b")
_BILL = re.compile(r"\b(bolletta|bollette|fattura|fatture|devo pagare|da pagare|scadenza|scadenze|kwh|smc|"
                   r"consumi|consumo|pod|pdr|importo)\b")
_EXCLUDE = re.compile(r"\b(email|e mail|mail|posta|adesso|ora|oggi stesso|in questo momento|telecamera|telecamere|"
                      r"allarme|temperatura|luci|luce accesa|accesa|accese|spenta|spente)\b")
_COMMODITY = {
    "gas": ("gas", "smc", "pdr", "metano"),
    "luce": ("luce", "elettric", "kwh", "pod"),
    "acqua": ("acqua", "idric", "mc"),
}
_PAYROLL_TERMS = ("busta", "paga", "cedolino", "stipendio", "retribuzione", "lavoratore", "ferie", "trattenute")
_BILL_TERMS = ("bolletta", "fattura", "energia", "consumo", "scadenza", "fornitura", "pod", "pdr", "importo")
_FUTURE_PAY = re.compile(r"\b(devo pagare|da pagare|scadenza|scade|scadra|pagare)\b")


# ═════════════════════════ Riconoscimento della domanda ═════════════════════════

def classify(user_msg: str) -> Optional[dict]:
    """None se non è una domanda sui documenti; altrimenti {"topic": "payroll"|"bill", "commodity": …}."""
    raw = (user_msg or "").strip()
    if not raw or raw.startswith("/"):
        return None
    n = fs.norm(raw)
    if _SEND_VERBS.search(n) or _EXCLUDE.search(n):
        return None
    if not (_QUESTION.search(n) or raw.rstrip().endswith("?")):
        return None
    topic = None
    if _PAYROLL.search(n):
        topic = "payroll"
    elif _BILL.search(n):
        topic = "bill"
    if not topic:
        return None
    commodity = None
    for name, words in _COMMODITY.items():
        if re.search(r"\b" + name + r"\b", n):
            commodity = name
            break
    return {"topic": topic, "commodity": commodity, "future": bool(_FUTURE_PAY.search(n))}


# ═════════════════════════ Scelta dei documenti ═════════════════════════

def _doc_rows(rows: list) -> list:
    return [r for r in rows if r.get("kind") in ("pdf", "doc", "text")]


def _score_doc(row: dict, info: dict) -> float:
    terms = _PAYROLL_TERMS if info["topic"] == "payroll" else _BILL_TERMS
    name = (row.get("name_n") or "") + " " + fs.norm(os.path.basename(str(row.get("folder") or "")))
    text = row.get("text_n") or ""
    score = 0.0
    for t in terms:
        if t in name:
            score += 3
        score += min(text.count(t), 4) * 0.5
    if info.get("commodity"):
        words = _COMMODITY[info["commodity"]]
        in_name = any(w in name for w in words)
        cnt = sum(text.count(w) for w in words)
        if in_name:
            score += 6
        score += min(cnt, 6)
        if not in_name and cnt == 0:
            score -= 8                               # es. chiedo "gas" e il documento non lo nomina mai
        # una bolletta della luce può nominare "gas" di sfuggita: pesa chi parla più di gas che di altro
        others = [w for k, ws in _COMMODITY.items() if k != info["commodity"] for w in ws]
        if not in_name and any(w in name for w in others):
            score -= 10                              # il nome dice un'altra fornitura (es. "bolletta luce")
        if sum(text.count(w) for w in others) > 2 * max(cnt, 1) and not in_name:
            score -= 8                               # il testo parla soprattutto d'altro
    return score


def select_docs(index, text: str, folders: list, info: dict, today: Optional[date] = None,
                max_docs: int = MAX_DOCS) -> dict:
    """{"pq": parse_query, "rows": [...], "periods": [...]}: i documenti più pertinenti."""
    today = today or date.today()
    pq = fs.parse_query(text, folders, today)
    periods = pq.get("periods") or []
    # "quando devo pagare a novembre" detto a ottobre = novembre di QUEST'anno, non dell'anno scorso
    fixed = []
    for p in periods:
        if (info.get("future") and p.get("month") and not p.get("day") and not re.search(r"20\d\d", text)
                and p["month"] > today.month and p["year"] == today.year - 1):
            p = fs._month_period(p["month"], today.year, today)
        fixed.append(p)
    periods = fixed
    roots = fs._roots(folders)
    if pq.get("folders"):
        sel = set()
        for p in pq["folders"]:
            try:
                sel.add(str(Path(p).resolve()))
            except Exception:
                sel.add(p)
        roots = [r for r in roots if r in sel] or roots
    if periods:
        rows = index.candidates(roots, [], None, ranges=[(p["from"], p["to"]) for p in periods],
                                soft_text=all(p.get("content") for p in periods), limit=1500)
    else:
        rows = index.candidates(roots, [], None, limit=1500)
    rows = _doc_rows(rows)
    chosen, seen = [], set()
    if periods:
        for p in periods:
            hits = []
            for r in rows:
                base = _score_doc(r, info)
                if base < MIN_SCORE:
                    continue
                ps, strength = fs._period_score(r, p)
                if not strength or strength == "weak":
                    continue
                hits.append((base + ps * 2 + (0.5 if strength == "content" else 0), r))
            hits.sort(key=lambda t: (t[0], t[1].get("date_ts") or 0), reverse=True)
            for sc, r in hits[:MAX_PER_PERIOD]:
                if r["path"] not in seen:
                    seen.add(r["path"]); chosen.append({**r, "qa_score": sc})
    else:
        scored = [(_score_doc(r, info), r) for r in rows]
        scored = [(s, r) for s, r in scored if s >= MIN_SCORE]
        scored.sort(key=lambda t: (t[1].get("date_ts") or 0, t[0]), reverse=True)    # i più recenti
        for sc, r in scored[:MAX_PER_PERIOD]:
            chosen.append({**r, "qa_score": sc})
    return {"pq": pq, "rows": chosen[:max_docs], "periods": periods}


# ═════════════════════════ Lettura e prompt ═════════════════════════

def read_doc_text(row: dict) -> tuple:
    """(testo, errore) — rilegge il documento dal disco (l'indice ne tiene solo un estratto)."""
    path, ext = row["path"], (row.get("ext") or "").lower()
    try:
        if ext == ".pdf":
            t = fs.extract_pdf_text(path)
        elif ext == ".docx":
            t = fs.extract_docx_text(path)
        else:
            t = fs.extract_plain_text(path)
    except Exception as e:
        return "", f"non leggibile ({type(e).__name__})"
    if not t.strip():
        return "", "nessun testo leggibile (PDF scansionato o protetto da password)"
    if ext == ".pdf" and row.get("_layout"):
        lay = pdf_layout_page1(path)
        if lay:
            t = t[:MAX_CHARS_PER_DOC - 5200] + "\n\n--- IMPAGINAZIONE ORIGINALE pagina 1 (colonne allineate) ---\n" + lay
    return t, None


def pdf_layout_page1(path: str, limit: int = 5000) -> str:
    """Prima pagina con le colonne allineate (etichette sopra ai valori): aiuta con le tabelle delle buste paga."""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            t = pdf.pages[0].extract_text(layout=True) or ""
        t = "\n".join(re.sub(r"[ \t]{3,}", "   ", l.rstrip()) for l in t.splitlines() if l.strip())
        return t[:limit]
    except Exception as e:
        logger.debug("layout non disponibile %s: %s", path, e)
        return ""


SYSTEM_PROMPT = (
    "Sei l'assistente di documenti personali di una famiglia italiana. Rispondi alla domanda usando "
    "ESCLUSIVAMENTE il testo dei documenti forniti.\n"
    "Regole ferree:\n"
    "- Non inventare e non stimare: se il dato non è scritto nei documenti, rispondi che non lo trovi.\n"
    "- Copia importi, date e numeri ESATTAMENTE come scritti (stesso formato, es. 1.234,56).\n"
    "- Indica sempre da quale documento (nome file) e periodo hai preso il dato.\n"
    "- Busta paga: «netto» = importo netto da pagare/in busta; «ferie»/«permessi» = guarda le colonne godute/"
    "maturate/residue e di' quale usi; se i documenti non permettono di distinguerle, dillo.\n"
    "- IMPORTANTE busta paga/libro unico: le presenze e assenze (ore lavorate, ferie, malattia, permessi) del "
    "cedolino di un mese sono spesso quelle del MESE PRECEDENTE (diciture come «MESE-1», «mese prec.», «MESE "
    "SETTEMBRE»). Se l'utente chiede «ferie/malattia di ottobre» e il cedolino di ottobre riporta quei dati, "
    "USALI e di' chiaramente a quale mese si riferiscono («nel cedolino di ottobre, riferite a settembre»). "
    "Non rifiutare solo perché il mese di riferimento è diverso: riporta i valori e precisa il periodo.\n"
    "- Il testo di un PDF a tabella può avere le etichette separate dai valori: abbina valori ed etichette con "
    "l'ordine e l'impaginazione originale (se fornita). Le ore vanno in ore; per i giorni dividi solo se il "
    "documento indica le ore per giorno, e dillo. Se l'abbinamento è incerto, elenca i numeri trovati e "
    "spiega l'incertezza invece di scegliere a caso.\n"
    "- Bolletta: importo = totale da pagare; scadenza = data di scadenza del pagamento.\n"
    "- Risposta breve (max 6 righe), in italiano, senza markdown."
)


def build_user_prompt(question: str, docs: list) -> str:
    parts = [f"DOMANDA: {question}\n"]
    budget = MAX_CHARS_TOTAL
    for i, d in enumerate(docs, 1):
        t = d["text"][:min(MAX_CHARS_PER_DOC, budget)]
        budget -= len(t)
        parts.append(f"=== DOCUMENTO {i}: {d['name']} (file del {d['date']}) ===\n{t}\n")
        if budget <= 0:
            break
    return "\n".join(parts)


_MONEY = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*,\d{1,2}|\d+,\d{1,2})(?![\d])")


def unverified_numbers(answer: str, source_text: str) -> list:
    """Importi (formato 1.234,56) scritti nella risposta ma assenti dal testo dei documenti."""
    src = source_text or ""
    src_compact = re.sub(r"\s+", "", src)
    out = []
    for m in _MONEY.finditer(answer or ""):
        v = m.group(1)
        if v in src or v.replace(" ", "") in src_compact:
            continue
        out.append(v)
    return sorted(set(out))


# ═════════════════════════ Orchestrazione ═════════════════════════

async def answer_question(index, ai_cb, question: str, folders: list, info: dict,
                          today: Optional[date] = None) -> dict:
    """{"ok": bool, "text": str (HTML Telegram), "rows": [...file usati...]}"""
    import asyncio
    import html as _h
    sel = await asyncio.to_thread(select_docs, index, question, folders, info, today)
    rows, periods = sel["rows"], sel["periods"]
    if not rows:
        what = ", ".join(p["label"] for p in periods)
        return {"ok": False, "rows": [],
                "text": ("🔎 <b>Non trovo documenti" + (f" di {_h.escape(what)}" if what else "") + "</b> che parlino di "
                         + ("busta paga/stipendio" if info["topic"] == "payroll" else "bolletta/fattura")
                         + (f" ({info['commodity']})" if info.get("commodity") else "")
                         + ".\n<i>Controlla che i PDF siano nelle cartelle della ricerca file e già indicizzati "
                           "(<code>/file stato</code>). Non rispondo a caso.</i>")}
    docs, problems = [], []
    for r in rows:
        if info["topic"] == "payroll":
            r["_layout"] = True
        t, err = await asyncio.to_thread(read_doc_text, r)
        if t:
            docs.append({"name": r["name"], "date": fs.datetime.fromtimestamp(r["date_ts"]).strftime("%d/%m/%Y")
                         if r.get("date_ts") else "?", "text": t, "row": r})
        else:
            problems.append(f"{r['name']}: {err}")
    if not docs:
        return {"ok": False, "rows": rows,
                "text": "⚠️ Ho trovato i documenti ma non riesco a leggerne il testo:\n• " + "\n• ".join(_h.escape(p) for p in problems)}
    prompt = build_user_prompt(question, docs)
    answer = (await ai_cb(SYSTEM_PROMPT, prompt, None) or "").strip()
    if not answer:
        return {"ok": False, "rows": rows, "text": "⚠️ L'AI non ha risposto: riprova tra poco."}
    all_text = "\n".join(d["text"] for d in docs)
    bad = unverified_numbers(answer, all_text)
    lines = ["📄 " + _h.escape(answer)]
    if bad:
        lines.append("⚠️ <i>Controlla sul PDF: non ritrovo nel testo dei documenti il valore " + _h.escape(", ".join(bad)) + ".</i>")
    lines.append("\n<b>Fonti:</b> " + _h.escape(", ".join(d["name"] for d in docs)))
    if problems:
        lines.append("ℹ️ <i>Non letti: " + _h.escape("; ".join(problems)) + "</i>")
    return {"ok": True, "rows": [d["row"] for d in docs], "text": "\n".join(lines)}
