"""
dieta.py — Piano alimentare: carichi un JSON e puoi chiedere cosa preparare.

Flusso:
1. Carichi il JSON dalla dashboard (Impostazioni → 🥗 Dieta) oppure lo copi in
   /config/homemind_patches/dieta.json e premi «Ricarica».
2. Chiedi ad Alexa «cosa ho per spuntino pomeridiano?» (o colazione, pranzo,
   cena, spuntino mattina, spuntino serale; anche «domani», «giovedì»…).
3. HomeMind risponde a voce sugli speaker Alexa selezionati e, se lo switch è
   attivo, manda lo stesso messaggio anche su Telegram.

Come HomeMind "sente" la domanda: Alexa Media Player (HACS) espone l'ultima
frase pronunciata nell'attributo `last_called_summary`. In più c'è l'endpoint
POST /api/dieta/ask (per routine Alexa → script/rest_command di HA) e il
comando Telegram /dieta.

Formato JSON: vedi config_example/dieta_esempio.json
"""
import json
import html as _html
import logging
import re
import time
import unicodedata
from datetime import timedelta
from pathlib import Path

from utils.timezone_helper import now_local

logger = logging.getLogger("homemind.dieta")

GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
GIORNI_LABEL = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

PASTI = ["colazione", "spuntino_mattina", "pranzo",
         "spuntino_pomeridiano", "cena", "spuntino_serale"]
PASTI_LABEL = {
    "colazione": "Colazione",
    "spuntino_mattina": "Spuntino mattina",
    "pranzo": "Pranzo",
    "spuntino_pomeridiano": "Spuntino pomeridiano",
    "cena": "Cena",
    "spuntino_serale": "Spuntino serale",
}
# Come lo dice Alexa: "Per ____ di oggi hai: ..."
PASTI_VOCE = {
    "colazione": "la colazione",
    "spuntino_mattina": "lo spuntino di mattina",
    "pranzo": "il pranzo",
    "spuntino_pomeridiano": "lo spuntino del pomeriggio",
    "cena": "la cena",
    "spuntino_serale": "lo spuntino serale",
}
PASTI_EMOJI = {
    "colazione": "☕", "spuntino_mattina": "🍎", "pranzo": "🍽️",
    "spuntino_pomeridiano": "🥜", "cena": "🌙", "spuntino_serale": "🥛",
}

MAX_JSON_BYTES = 500_000


# ── Percorsi ────────────────────────────────────────────────────────────────

def _patches_dir() -> Path:
    for base in ("/config", "/homeassistant", "/data"):
        p = Path(base) / "homemind_patches"
        if p.exists():
            return p
    p = Path("/config/homemind_patches")
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


def dieta_path() -> Path:
    return _patches_dir() / "dieta.json"


DATA_COPY_PATH = Path("/data/dieta.json")   # copia di riserva


# ── Testo ───────────────────────────────────────────────────────────────────

def _esc(s) -> str:
    return _html.escape(str(s), quote=False)


def _strip(s) -> str:
    """minuscolo, senza accenti, solo lettere/numeri separati da singoli spazi."""
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_SNACK = r"(?:spuntin\w*|merend\w*|snack)"


def meal_from_text(text: str):
    """Riconosce il pasto da una frase/chiave. Ritorna una chiave di PASTI,
    "spuntino" (generico, ambiguo) oppure None."""
    t = _strip(text)
    if not t:
        return None
    if re.search(rf"\b{_SNACK}\b.*\b(mattin\w*|mezza mattina)\b", t) or \
       re.search(rf"\b(mattin\w*)\b.*\b{_SNACK}\b", t):
        return "spuntino_mattina"
    if re.search(rf"\b{_SNACK}\b.*\b(pomerid\w*|pomeriggio|pom|pre wo|pre workout|preworkout)\b", t) or \
       re.search(rf"\b(pomerid\w*|pomeriggio)\b.*\b{_SNACK}\b", t):
        return "spuntino_pomeridiano"
    if re.search(rf"\b{_SNACK}\b.*\b(seral\w*|sera|serata|notte)\b", t) or \
       re.search(rf"\b(seral\w*)\b.*\b{_SNACK}\b", t):
        return "spuntino_serale"
    if re.search(r"\bcolazion\w*\b", t):
        return "colazione"
    if re.search(r"\bpranz\w*\b", t):
        return "pranzo"
    if re.search(r"\bcena\b", t) or re.search(r"\b(stasera|questa sera)\b", t):
        return "cena"
    if re.search(r"\bmerend\w*\b", t):
        return "spuntino_pomeridiano"          # «merenda» da sola = pomeriggio
    if re.search(rf"\b{_SNACK}\b", t):
        return "spuntino"                      # generico: quale?
    return None


def _day_from_key(key: str):
    k = _strip(key)
    for i, g in enumerate(GIORNI):
        if k == g or k.startswith(g + " ") or k.startswith(g[:3] + " ") or k == g[:3]:
            return i
    return None


# ── Normalizzazione del JSON ────────────────────────────────────────────────

def _norm_item(x):
    """Un alimento → {"nome","quantita","nota"} oppure None."""
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return None
        nome, sep, q = s.partition(":")
        return {"nome": nome.strip(), "quantita": q.strip() if sep else "", "nota": ""}
    if isinstance(x, dict):
        nome = x.get("nome") or x.get("alimento") or x.get("name") or x.get("cibo")
        if not nome:
            return None
        q = x.get("quantita", x.get("qta", x.get("quantity", "")))
        return {"nome": str(nome).strip(),
                "quantita": ("" if q is None else str(q).strip()),
                "nota": str(x.get("nota") or "").strip()}
    return None


def _norm_meal(val):
    """Valore di un pasto → {"alimenti":[...], "facoltativo":bool, "nota":str} o None."""
    facoltativo, nota = False, ""
    items = val
    if isinstance(val, dict):
        facoltativo = bool(val.get("facoltativo", False))
        nota = str(val.get("nota") or "").strip()
        items = val.get("alimenti", val.get("items", val.get("cibi", [])))
    if isinstance(items, str):
        items = [items]
    if not isinstance(items, list):
        return None
    out = []
    for it in items:
        if isinstance(it, str) and "|" in it:           # «Olio EVO: 10g | Verdure: 150g»
            parts = [p for p in it.split("|") if p.strip()]
        else:
            parts = [it]
        for p in parts:
            n = _norm_item(p)
            if n:
                out.append(n)
    if not out:
        return None
    return {"alimenti": out, "facoltativo": facoltativo, "nota": nota}


def normalize_diet(raw):
    """Valida e normalizza il JSON. Ritorna (diet, warnings). Alza ValueError (in italiano)
    se il file non è utilizzabile."""
    if not isinstance(raw, dict):
        raise ValueError("La radice del JSON deve essere un oggetto { ... }")
    giorni_raw = raw.get("giorni")
    if not isinstance(giorni_raw, dict) or not giorni_raw:
        raise ValueError('Manca la sezione "giorni" (un oggetto con lunedi, martedi, ...)')

    warnings, giorni = [], {}
    for k, v in giorni_raw.items():
        idx = _day_from_key(k)
        if idx is None:
            warnings.append(f'Giorno «{k}» non riconosciuto: ignorato')
            continue
        if not isinstance(v, dict):
            warnings.append(f'{GIORNI_LABEL[idx]}: formato non valido, ignorato')
            continue
        pasti_raw = v.get("pasti", {k2: v2 for k2, v2 in v.items() if k2 != "tipo"})
        if not isinstance(pasti_raw, dict):
            warnings.append(f'{GIORNI_LABEL[idx]}: "pasti" non è un oggetto, ignorato')
            continue
        pasti = {}
        for pk, pv in pasti_raw.items():
            m = meal_from_text(pk)
            if m in (None, "spuntino"):
                warnings.append(f'{GIORNI_LABEL[idx]}: pasto «{pk}» non riconosciuto, ignorato')
                continue
            nm = _norm_meal(pv)
            if nm is None:
                warnings.append(f'{GIORNI_LABEL[idx]}: «{pk}» vuoto o non valido, ignorato')
                continue
            if m in pasti:
                warnings.append(f'{GIORNI_LABEL[idx]}: «{pk}» duplicato, tengo il primo')
                continue
            pasti[m] = nm
        if not pasti:
            warnings.append(f'{GIORNI_LABEL[idx]}: nessun pasto valido, ignorato')
            continue
        tipo = _strip(v.get("tipo", ""))
        tipo = "allenamento" if tipo.startswith(("allen", "workout", "wo")) else \
               "riposo" if tipo.startswith(("ripos", "rest")) else ""
        giorni[GIORNI[idx]] = {"tipo": tipo, "pasti": pasti}

    if not giorni:
        raise ValueError("Nessun giorno valido trovato nel JSON")
    missing = [GIORNI_LABEL[i] for i, g in enumerate(GIORNI) if g not in giorni]
    if missing:
        warnings.append("Giorni mancanti: " + ", ".join(missing))

    note = raw.get("note", [])
    if isinstance(note, str):
        note = [note]
    diet = {
        "persona": str(raw.get("persona") or "").strip(),
        "titolo": str(raw.get("titolo") or "Piano alimentare").strip(),
        "valido_da": str(raw.get("valido_da") or "").strip(),
        "obiettivi": raw.get("obiettivi") if isinstance(raw.get("obiettivi"), dict) else {},
        "note": [str(n).strip() for n in note if str(n).strip()] if isinstance(note, list) else [],
        "giorni": giorni,
    }
    return diet, warnings


# ── Testo per la voce ───────────────────────────────────────────────────────

def _speech_clean(s: str) -> str:
    s = str(s or "")
    s = re.sub(r"\bEVO\b", "extravergine", s)
    s = re.sub(r"\bs/glutine\b", "senza glutine", s, flags=re.I)
    s = re.sub(r"\bs/lattosio\b", "senza lattosio", s, flags=re.I)
    s = re.sub(r"(\d+)\s*-\s*(\d+)", r"da \1 a \2", s)
    s = re.sub(r"(\d)\s*kg\b", r"\1 chili", s)
    s = re.sub(r"(\d)\s*ml\b", r"\1 millilitri", s)
    s = re.sub(r"(\d)\s*g\b", r"\1 grammi", s)
    s = s.replace("/", " o ")
    return re.sub(r"\s+", " ", s).strip()


def _speech_item(it: dict) -> str:
    out = _speech_clean(it["nome"])
    if it.get("quantita"):
        out += ", " + _speech_clean(it["quantita"])
    if it.get("nota"):
        out += ", " + _speech_clean(it["nota"])
    return out


def _fmt_item_html(it: dict) -> str:
    s = "• " + _esc(it["nome"])
    if it.get("quantita"):
        s += " — <b>" + _esc(it["quantita"]) + "</b>"
    if it.get("nota"):
        s += " <i>(" + _esc(it["nota"]) + ")</i>"
    return s


# ── Manager ─────────────────────────────────────────────────────────────────

_TRIGGER = re.compile(r"\b(cosa|che|cos|qual|quale|quali|quanto|come|dimmi|dimmelo|dici|dammi|leggi|leggimi|"
                      r"dettami|ripeti|ricordami cosa|dieta|menu|piano|programma|previsto|tocca|spetta|"
                      r"preparo|preparare|mangio|mangiare|mangiato|devo|ho|ce|c e|sapere)\b")
_DAY_SUMMARY = re.compile(r"\b(dieta|menu|mangio|mangiare|giornata|piano alimentare)\b")
_EXCLUDE = re.compile(r"\b(accendi|spegni|imposta|sveglia|timer|ricordami|prenota|ordina|ricetta|ricette|"
                      r"metti|suona|riproduci|musica|playlist|canzone|radio|volume|chiama|apri|chiudi|"
                      r"ristorante|pizzeria|tavolo|luce|luci|meteo|aggiungi|lista|spesa)\b")
_SHORT_MAX_WORDS = 3     # «spuntino pomeridiano», «cena di domani»: bastano da sole se brevi


class DietaManager:
    def __init__(self, notifier=None, rest_client=None,
                 telegram_enabled: bool = False,
                 alexa_enabled: bool = False,
                 alexa_speakers: list = None,
                 alexa_volume: float = 0.5):
        self.notifier = notifier
        self.rest = rest_client
        self.telegram_enabled = bool(telegram_enabled)
        self.alexa_enabled = bool(alexa_enabled)
        self.alexa_speakers = list(alexa_speakers) if alexa_speakers else []
        self.alexa_volume = max(0.0, min(1.0, float(alexa_volume)))
        self.diet: dict = {}
        self.warnings: list = []
        self.load_error: str = ""
        self._pending = None        # domanda «quale spuntino?» in attesa di risposta
        self._recent: dict = {}     # testo normalizzato → timestamp (anti-doppioni)

    # ── Caricamento / salvataggio ────────────────────────────────────────────
    def load(self) -> str:
        """Carica il piano da disco. Ritorna un messaggio di stato."""
        self.load_error = ""
        for path in (dieta_path(), DATA_COPY_PATH):
            try:
                if not path.exists():
                    continue
                raw = json.loads(path.read_text(encoding="utf-8-sig"))
                self.diet, self.warnings = normalize_diet(raw)
                logger.info("Dieta caricata da %s: %d giorni", path, len(self.diet["giorni"]))
                return f"Piano caricato: {len(self.diet['giorni'])} giorni."
            except Exception as e:
                self.load_error = f"{path}: {e}"
                logger.warning("Dieta: errore lettura %s: %s", path, e)
        if not self.load_error:
            self.diet, self.warnings = {}, []
        return self.load_error or "Nessun piano alimentare caricato."

    def set_from_json_text(self, text: str):
        """Valida il JSON caricato dalla dashboard e lo salva. Ritorna (diet, warnings).
        Alza ValueError se non valido: in quel caso il piano attuale NON viene toccato."""
        if len(text.encode("utf-8", "ignore")) > MAX_JSON_BYTES:
            raise ValueError("File troppo grande (max 500 KB)")
        try:
            raw = json.loads(text.lstrip("\ufeff"))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON non valido: {e.msg} (riga {e.lineno}, colonna {e.colno})")
        diet, warnings = normalize_diet(raw)          # alza ValueError se inutilizzabile
        pretty = json.dumps(raw, indent=2, ensure_ascii=False)
        p = dieta_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(pretty, encoding="utf-8")
        tmp.replace(p)
        try:
            DATA_COPY_PATH.parent.mkdir(parents=True, exist_ok=True)
            DATA_COPY_PATH.write_text(pretty, encoding="utf-8")
        except Exception as e:
            logger.debug("Dieta: copia in /data non riuscita: %s", e)
        self.diet, self.warnings, self.load_error = diet, warnings, ""
        logger.info("Dieta aggiornata dalla dashboard: %d giorni, %d avvisi",
                    len(diet["giorni"]), len(warnings))
        return diet, warnings

    def raw_json_text(self) -> str:
        try:
            return dieta_path().read_text(encoding="utf-8-sig")
        except Exception:
            return ""

    # ── Riconoscimento della domanda ─────────────────────────────────────────
    def parse_query(self, text: str, require_trigger: bool = True):
        """Ritorna dict {meal|None, day, delta, whole_day, ambiguous} oppure None
        se la frase non riguarda la dieta."""
        t = _strip(text)
        if not t or len(t) > 160:
            return None
        if _EXCLUDE.search(t):
            return None
        meal = meal_from_text(t)
        whole = False
        if meal is None:
            has_day = re.search(r"\b(oggi|domani|dopodomani|ieri|" + "|".join(GIORNI) + r")\b", t)
            if not _DAY_SUMMARY.search(t) and (require_trigger or not has_day):
                return None            # né pasto, né «dieta/menu/mangio», né un giorno: non è per noi
            whole = True
        elif require_trigger and not _TRIGGER.search(t) and len(t.split()) > _SHORT_MAX_WORDS:
            return None

        today = now_local()
        delta, day_idx, explicit_weekday = 0, today.weekday(), False
        if re.search(r"\bdopodomani\b", t):
            delta = 2
        elif re.search(r"\bdomani\b", t):
            delta = 1
        elif re.search(r"\bieri\b", t):
            delta = -1
        else:
            for i, g in enumerate(GIORNI):
                if re.search(rf"\b{g}\b", t):
                    day_idx, explicit_weekday = i, True
                    break
        if not explicit_weekday:
            day_idx = (today + timedelta(days=delta)).weekday()
        return {"meal": None if whole else meal, "day": day_idx, "delta": delta,
                "weekday_named": explicit_weekday, "whole_day": whole,
                "ambiguous": meal == "spuntino"}

    @staticmethod
    def _day_phrase(q: dict) -> str:
        if q["weekday_named"]:
            return GIORNI_LABEL[q["day"]].lower()
        return {-1: "ieri", 0: "oggi", 1: "domani", 2: "dopodomani"}.get(q["delta"], GIORNI_LABEL[q["day"]].lower())

    # ── Costruzione risposte ─────────────────────────────────────────────────
    def _day(self, q):
        return (self.diet.get("giorni") or {}).get(GIORNI[q["day"]])

    def build_answer(self, q: dict) -> tuple:
        """Ritorna (testo_voce, html_telegram)."""
        if not self.diet:
            msg = "Non ho ancora un piano alimentare. Caricalo dalla sezione Dieta di HomeMind."
            return msg, "🥗 " + msg
        dayphrase = self._day_phrase(q)
        daylabel = GIORNI_LABEL[q["day"]]
        day = self._day(q)

        if q.get("ambiguous"):
            msg = "Quale spuntino? Mattina, pomeriggio o sera?"
            return msg, "🥗 " + msg
        if not day:
            msg = f"Nel piano non c'è nulla per {dayphrase}."
            return msg, "🥗 " + msg

        tipo_txt = {"allenamento": "giorno di allenamento", "riposo": "giorno di riposo"}.get(day["tipo"], "")

        if q["whole_day"]:
            speech = [f"Ecco il piano di {dayphrase}" + (f", {tipo_txt}." if tipo_txt else ".")]
            hl = [f"🥗 <b>Piano di {_esc(dayphrase)}</b>" + ("" if q["weekday_named"] else f" — {daylabel}") +
                  (f" <i>({tipo_txt})</i>" if tipo_txt else "")]
            for m in PASTI:
                meal = day["pasti"].get(m)
                if not meal:
                    continue
                fac = " (facoltativo)" if meal["facoltativo"] else ""
                speech.append(f"{PASTI_LABEL[m]}{fac}: " + ". ".join(_speech_item(i) for i in meal["alimenti"]) + ".")
                hl.append(f"\n{PASTI_EMOJI[m]} <b>{PASTI_LABEL[m]}</b>" +
                          (" <i>(facoltativo)</i>" if meal["facoltativo"] else ""))
                hl.extend(_fmt_item_html(i) for i in meal["alimenti"])
                if meal["nota"]:
                    hl.append("<i>" + _esc(meal["nota"]) + "</i>")
            return " ".join(speech), "\n".join(hl)

        meal = day["pasti"].get(q["meal"])
        if not meal:
            msg = f"Per {PASTI_VOCE[q['meal']]} di {dayphrase} non è previsto nulla."
            return msg, "🥗 " + msg
        fac = " Questo spuntino è facoltativo." if meal["facoltativo"] else ""
        speech = (f"Per {PASTI_VOCE[q['meal']]} di {dayphrase} hai: "
                  + ". ".join(_speech_item(i) for i in meal["alimenti"]) + ".")
        if meal["nota"]:
            speech += " " + _speech_clean(meal["nota"]) + "."
        speech += fac
        dl = _esc(dayphrase) if q["weekday_named"] else f"{_esc(dayphrase)} ({daylabel})"
        hl = [f"{PASTI_EMOJI[q['meal']]} <b>{PASTI_LABEL[q['meal']]} — {dl}</b>"
              + (" <i>(facoltativo)</i>" if meal["facoltativo"] else "")]
        hl.extend(_fmt_item_html(i) for i in meal["alimenti"])
        if meal["nota"]:
            hl.append("<i>" + _esc(meal["nota"]) + "</i>")
        if tipo_txt:
            hl.append(f"\n<i>{tipo_txt.capitalize()}</i>")
        return speech, "\n".join(hl)

    # ── Telegram (comando /dieta) ────────────────────────────────────────────
    def telegram_reply(self, arg: str = "") -> str:
        """Risposta testuale al comando /dieta [pasto] [giorno]. Non parla su Alexa."""
        if not self.diet:
            return ("🥗 Nessun piano alimentare caricato.\n"
                    "Caricalo da Impostazioni → 🥗 Dieta (file JSON).")
        q = self.parse_query(arg, require_trigger=False) if arg.strip() else None
        if q is None:
            q = self.parse_query("dieta oggi", require_trigger=False)
        if q is None:
            return "🥗 Non ho capito. Esempi: /dieta, /dieta cena, /dieta spuntino pomeridiano domani"
        return self.build_answer(q)[1]

    def telegram_free_text(self, text: str):
        """Frase libera scritta al bot («Colazione», «cosa ho per cena domani»).
        Ritorna l'HTML della risposta se è una domanda sul piano, altrimenti None
        (e il messaggio prosegue verso l'AI). Se non c'è un piano caricato non intercetta."""
        try:
            if not self.diet:
                return None
            t = _strip(text)
            if not t or len(t) > 80 or len(t.split()) > 8:
                return None
            if _EXCLUDE.search(t):
                return None
            # risposta a «Quale spuntino?» (valida 2 minuti): «pomeriggio», «di sera»…
            pend, self._pending = self._pending, None
            if pend and time.monotonic() - pend["ts"] <= 120 and len(t.split()) <= 3:
                m = ("spuntino_mattina" if re.search(r"\bmattin\w*", t) else
                     "spuntino_pomeridiano" if re.search(r"\b(pomerid\w*|pomeriggio|pom)\b", t) else
                     "spuntino_serale" if re.search(r"\b(seral\w*|sera|serata)\b", t) else None)
                if m:
                    q = dict(pend["q"], meal=m, ambiguous=False)
                    return self.build_answer(q)[1]
            q = self.parse_query(t, require_trigger=False)
            if q is None:
                return None
            if len(t.split()) > 3 and not (_TRIGGER.search(t) or _DAY_SUMMARY.search(t)):
                return None        # «Rosa ha fatto colazione?» non è una domanda sul piano
            if q["meal"] is None and not _DAY_SUMMARY.search(t):
                return None        # nessun pasto e nessuna parola «dieta/menu/mangio»
            if q["ambiguous"]:
                self._pending = {"q": q, "ts": time.monotonic()}
            return self.build_answer(q)[1]
        except Exception as e:
            logger.debug("Dieta telegram_free_text: %s", e)
            return None

    # ── Domanda (da Alexa / API / test) ──────────────────────────────────────
    async def ask(self, text: str, force: bool = False, source: str = "api") -> dict:
        """Gestisce una domanda. force=True salta il controllo «sembra una domanda sulla dieta»
        (usato da API/test) e risponde anche se lo switch Alexa è spento."""
        res = {"ok": True, "matched": False, "speech": "", "telegram_ok": False,
               "alexa_ok": 0, "alexa_total": 0}
        q = self.parse_query(text, require_trigger=not force)
        if q is None:
            return res
        res["matched"] = True
        speech, html_msg = self.build_answer(q)
        res["speech"] = speech
        logger.info("Dieta [%s]: «%s» → %s", source, text, speech[:120])

        if self.telegram_enabled and self.notifier:
            try:
                await self.notifier.send_html(html_msg, force=True)
                res["telegram_ok"] = True
            except Exception as e:
                logger.warning("Dieta: invio Telegram fallito: %s", e)
                res["telegram_error"] = str(e)[:200]

        if (self.alexa_enabled or (force and source == "test")) and self.alexa_speakers and self.rest:
            try:
                from alexa_tts import speak_on_speakers
                r = await speak_on_speakers(self.rest, self.alexa_speakers, speech, self.alexa_volume)
                res["alexa_ok"] = r.get("ok", 0)
                res["alexa_total"] = r.get("ok", 0) + r.get("fail", 0)
                if res["alexa_ok"] == 0:
                    errs = r.get("errors", [])
                    res["alexa_error"] = (errs[0] if errs else "0 speaker OK")[:200]
            except Exception as e:
                logger.warning("Dieta: annuncio Alexa fallito: %s", e)
                res["alexa_error"] = str(e)[:200]
        elif self.alexa_enabled and not self.alexa_speakers:
            logger.warning("Dieta: Alexa abilitato ma nessuno speaker selezionato")
        return res

    # ── Ascolto delle frasi pronunciate (Alexa Media Player) ─────────────────
    def on_state_changed(self, eid: str, new_state: dict):
        """Chiamato per ogni state_changed: deve essere leggero. Se un'entità riporta
        una nuova frase pronunciata ad Alexa, la gira a ask()."""
        try:
            if not (self.alexa_enabled and self.diet) or not new_state:
                return
            attrs = new_state.get("attributes") or {}
            text = attrs.get("last_called_summary")
            if not text and eid.startswith("sensor.") and ("last_called" in eid or "last_alexa" in eid):
                text = new_state.get("state")
            if not text or not isinstance(text, str) or text in ("unknown", "unavailable"):
                return
            key = _strip(text)
            now = time.monotonic()
            for k in [k for k, ts in self._recent.items() if now - ts > 10]:
                self._recent.pop(k, None)
            if key in self._recent:
                return
            q = self.parse_query(text, require_trigger=True)
            if q is None:
                return
            self._recent[key] = now
            import asyncio
            asyncio.get_running_loop().create_task(self.ask(text, source="alexa"))
        except Exception as e:
            logger.debug("Dieta on_state_changed: %s", e)

    # ── Stato per la dashboard ───────────────────────────────────────────────
    def status(self) -> dict:
        d = self.diet or {}
        giorni = []
        for i, g in enumerate(GIORNI):
            day = (d.get("giorni") or {}).get(g)
            if not day:
                continue
            giorni.append({
                "key": g, "label": GIORNI_LABEL[i], "tipo": day["tipo"],
                "pasti": [{"key": m, "label": PASTI_LABEL[m],
                           "facoltativo": day["pasti"][m]["facoltativo"],
                           "alimenti": [{"nome": a["nome"], "quantita": a["quantita"], "nota": a["nota"]}
                                        for a in day["pasti"][m]["alimenti"]],
                           "nota": day["pasti"][m]["nota"]}
                          for m in PASTI if m in day["pasti"]],
            })
        return {
            "loaded": bool(d),
            "persona": d.get("persona", ""), "titolo": d.get("titolo", ""),
            "valido_da": d.get("valido_da", ""),
            "obiettivi": d.get("obiettivi", {}), "note": d.get("note", []),
            "giorni": giorni, "warnings": self.warnings, "error": self.load_error,
            "telegram_enabled": self.telegram_enabled, "alexa_enabled": self.alexa_enabled,
            "speakers": self.alexa_speakers, "volume": self.alexa_volume,
        }
