"""
tv.py — Controllo della TV (qualsiasi marca supportata da Home Assistant) a voce e da Telegram.

HomeMind non parla direttamente con la TV: usa l'entità `media_player` che l'integrazione di Home
Assistant ha già creato (LG webOS, Samsung, Sony Bravia, Philips, Android TV…). Quindi non serve
l'IP e non c'è nessun protocollo da gestire qui. Accensione, volume, muto, canale, ingresso e
play/pausa usano i servizi standard `media_player.*`; solo i tasti del telecomando (frecce, numeri
quando il canale non si imposta direttamente) dipendono dalla marca (vedi `_press`).

Comandi (a voce con Alexa, da Telegram con «/tv …» o scrivendo la frase, o dalla dashboard):
  • «accendi / spegni la tv»
  • «alza / abbassa il volume della tv» (di N), «volume della tv a 30», «muto», «riattiva l'audio»
  • «metti canale 35», «canale successivo / precedente», «metti Rai 1» (nomi dal file dei canali)
  • «metti netflix sulla tv», «metti hdmi 2»
  • «metti in pausa la tv», «riprendi»

Voce: Alexa Media Player espone l'ultima frase in `last_called_summary` (come per la dieta).
"""
import asyncio
import html
import json
import logging
import re
import time
import unicodedata
from pathlib import Path

logger = logging.getLogger("homemind.tv")

MAX_JSON_BYTES = 200_000
WAKE_WAIT_S = 25


# ── Marche e tasti del telecomando ───────────────────────────────────────────
# "auto" = riconosciuta dal nome/attributi della TV; se non si riconosce si prova come LG (comportamento storico).
BRANDS = ("auto", "lg", "samsung", "sony", "other")

# Codici interni dei tasti → nome del tasto per marca.
_LG_KEYS = {"UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT", "ENTER": "ENTER", "BACK": "BACK",
            "HOME": "HOME", "MENU": "MENU", "INFO": "INFO", "EXIT": "EXIT", "VOLUP": "VOLUMEUP",
            "VOLDOWN": "VOLUMEDOWN", "CHUP": "CHANNELUP", "CHDOWN": "CHANNELDOWN",
            **{str(d): str(d) for d in range(10)}}
_SAMSUNG_KEYS = {"UP": "KEY_UP", "DOWN": "KEY_DOWN", "LEFT": "KEY_LEFT", "RIGHT": "KEY_RIGHT", "ENTER": "KEY_ENTER",
                 "BACK": "KEY_RETURN", "HOME": "KEY_HOME", "MENU": "KEY_MENU", "INFO": "KEY_INFO", "EXIT": "KEY_EXIT",
                 "VOLUP": "KEY_VOLUP", "VOLDOWN": "KEY_VOLDOWN", "CHUP": "KEY_CHUP", "CHDOWN": "KEY_CHDOWN",
                 **{str(d): f"KEY_{d}" for d in range(10)}}
_SONY_KEYS = {"UP": "Up", "DOWN": "Down", "LEFT": "Left", "RIGHT": "Right", "ENTER": "Confirm", "BACK": "Return",
              "HOME": "Home", "MENU": "Options", "INFO": "Display", "EXIT": "Exit", "VOLUP": "VolumeUp",
              "VOLDOWN": "VolumeDown", "CHUP": "ChannelUp", "CHDOWN": "ChannelDown",
              **{str(d): f"Num{d}" for d in range(10)}}
_REMOTE_KEYS = {"samsung": _SAMSUNG_KEYS, "sony": _SONY_KEYS}      # via remote.send_command

_BRAND_TOKENS = {"lg": {"lg", "webos", "webostv"}, "samsung": {"samsung", "tizen"}, "sony": {"sony", "bravia"}}


# ── Percorsi (stessa cartella persistente di dieta/spazzatura) ───────────────
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


def canali_path() -> Path:
    return _patches_dir() / "tv_canali.json"


DATA_COPY_PATH = Path("/data/tv_canali.json")


def _strip(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ── File dei canali ─────────────────────────────────────────────────────────
def normalize_channels(raw):
    """Accetta {"canali":[{"nome","numero","alias":[..]}]} oppure {"Rai 1":"501", ...}.
    Ritorna (lista, avvisi). Alza ValueError se inutilizzabile."""
    items = raw.get("canali") if isinstance(raw, dict) and "canali" in raw else raw
    out, warnings = [], []
    if isinstance(items, dict):
        items = [{"nome": k, "numero": v} for k, v in items.items()]
    if not isinstance(items, list) or not items:
        raise ValueError('Serve una lista "canali" (nome + numero) oppure un oggetto {"Rai 1": "501", ...}')
    seen = set()
    for it in items:
        if not isinstance(it, dict):
            warnings.append("Voce non valida ignorata")
            continue
        nome = str(it.get("nome") or it.get("name") or "").strip()
        num = str(it.get("numero", it.get("number", ""))).strip()
        if not nome or not re.fullmatch(r"\d{1,4}", num):
            warnings.append(f"«{nome or '?'}»: numero non valido ({num or 'vuoto'}), ignorato")
            continue
        alias = it.get("alias") or []
        alias = [alias] if isinstance(alias, str) else [str(a) for a in alias if str(a).strip()]
        names = {_strip(nome), *(_strip(a) for a in alias)} - {""}
        dup = names & seen
        if dup:
            warnings.append(f"«{nome}»: nome già usato ({', '.join(sorted(dup))}), tengo il primo")
            continue
        seen |= names
        out.append({"nome": nome, "numero": num, "alias": alias, "_names": sorted(names, key=len, reverse=True)})
    if not out:
        raise ValueError("Nessun canale valido nel file")
    return out, warnings


# Azioni ammesse in "comandi_audio" del file canali (nome → azione interna)
_AUDIO_ACTIONS = {"alza_volume": "vol_up", "abbassa_volume": "vol_down", "muto": "mute",
                  "riattiva_audio": "unmute", "attiva_audio": "unmute", "audio_on": "unmute"}


def normalize_audio_commands(raw):
    """Legge "comandi_audio": [{"azione": "alza_volume|abbassa_volume|muto|riattiva_audio", "alias": [...]}].
    Ritorna ({azione_interna: [frasi normalizzate]}, avvisi). Non solleva: il file canali resta valido."""
    out, warnings = {}, []
    items = raw.get("comandi_audio") if isinstance(raw, dict) else None
    if items in (None, [], {}):
        return out, warnings
    if not isinstance(items, list):
        return out, ['"comandi_audio" deve essere una lista: ignorato']
    for it in items:
        if not isinstance(it, dict):
            warnings.append("comandi_audio: voce non valida ignorata")
            continue
        act = _AUDIO_ACTIONS.get(str(it.get("azione") or it.get("action") or "").strip().lower())
        if not act:
            warnings.append(f"comandi_audio: azione «{it.get('azione', '?')}» sconosciuta "
                            f"(ammesse: {', '.join(sorted(_AUDIO_ACTIONS))}), ignorata")
            continue
        alias = it.get("alias") or []
        alias = [alias] if isinstance(alias, str) else alias
        for a in alias:
            n = _strip(str(a))
            if n:
                out.setdefault(act, [])
                if n not in out[act]:
                    out[act].append(n)
    for act in out:
        out[act].sort(key=len, reverse=True)
    return out, warnings


# ── Comprensione delle frasi ────────────────────────────────────────────────
_TV = re.compile(r"\b(tv|tivu|televisione|televisore|tele)\b")
_LEAD = re.compile(r"\b(metti|mettimi|vai su|vai al|passa a|passa al|sintonizza|cambia su|portami su|apri|avvia|accendi)\b")
_EXCLUDE = re.compile(r"\b(musica|canzone|playlist|radio|sveglia|timer|ricordami|prenota|luce|luci|"
                      r"riscaldamento|termostato|condizionatore|clima)\b")


# ── Numeri in lettere (Alexa trascrive «canale trenta tré», non «canale 33») ─────────────
_UNITS = {"zero": 0, "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7,
          "otto": 8, "nove": 9, "dieci": 10, "undici": 11, "dodici": 12, "tredici": 13, "quattordici": 14,
          "quindici": 15, "sedici": 16, "diciassette": 17, "diciotto": 18, "diciannove": 19}
_TENS = {"venti": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50, "sessanta": 60,
         "settanta": 70, "ottanta": 80, "novanta": 90}
_TENS_STEM = {k[:-1]: v for k, v in _TENS.items()}          # vent, trent, … (ventuno, trentotto)


def _word_value(w: str):
    """Valore di UNA parola numerica italiana (anche composta: trentatre, ventuno, duecento), o None."""
    if w in _UNITS:
        return _UNITS[w]
    if w in _TENS:
        return _TENS[w]
    for stem, v in list(_TENS_STEM.items()) + list(_TENS.items()):
        if w.startswith(stem) and w[len(stem):] in _UNITS and 0 < _UNITS[w[len(stem):]] < 10:
            return v + _UNITS[w[len(stem):]]
    m = re.fullmatch(r"(due|tre|quattro|cinque|sei|sette|otto|nove)?cento(.*)", w)   # cento, duecento, centoventi…
    if m:
        base = (_UNITS[m.group(1)] if m.group(1) else 1) * 100
        rest = m.group(2)
        if not rest:
            return base
        for r in (rest, "o" + rest):                       # centottanta = cento + ottanta (elisione)
            if r in _UNITS or r in _TENS or (r not in ("cento",) and "cento" not in r):
                rv = _word_value(r)
                if rv is not None and rv < 100:
                    return base + rv
    return None


def words_to_digits(t: str) -> str:
    """«metti canale trenta tre tv» → «metti canale 33 tv». Lavora su testo già normalizzato da _strip."""
    toks, out, i = t.split(), [], 0
    while i < len(toks):
        v = _word_value(toks[i])
        if v is None:
            out.append(toks[i]); i += 1
            continue
        total, i = v, i + 1
        while i < len(toks):                               # «trenta» «tre» · «cento» «venti» «due»
            n = _word_value(toks[i])
            if n is None:
                break
            if total % 100 == 0 and total >= 100 and n < 100:
                total += n                                 # cento + venti / cento + tre
            elif total % 100 and total % 100 >= 20 and total % 10 == 0 and 0 < n < 10:
                total += n                                 # trenta + tre
            else:
                break
            i += 1
        out.append(str(total))
    return " ".join(out)


class TvManager:
    def __init__(self, rest_client=None, state_getter=None, notifier=None, settings: dict = None):
        self.rest = rest_client
        self.state_fn = state_getter or (lambda eid: None)
        self.notifier = notifier
        self.channels: list = []
        self.channel_warnings: list = []
        self.channels_error = ""
        self._recent: dict = {}       # frase normalizzata -> istante (solo se Alexa non dà il timestamp)
        self._recent_utt: dict = {}   # (frase, timestamp) -> istante: UNA pronuncia, vista da più entità
        self._recent_eid: dict = {}   # frase -> (entità, istante): stessa frase da un'altra entità = doppione
        self.audio_aliases: dict = {}   # frasi personalizzate per volume/muto (dal file canali)
        self._last_ts: dict = {}      # eid -> ultimo last_called_timestamp visto (anti ri-esecuzione)
        self._last_text: dict = {}    # eid -> ultima frase loggata (solo per il log diagnostico)
        self._tasks: set = set()      # riferimenti ai task, altrimenti il GC può cancellarli
        self.apply_settings(settings or {})

    # ── Impostazioni ─────────────────────────────────────────────────────────
    def apply_settings(self, s: dict):
        s = s if isinstance(s, dict) else {}
        ent = str(s.get("entity") or "").strip()
        self.entity = ent if ent.startswith("media_player.") else ""
        self.mac = str(s.get("mac") or "").strip()
        b = str(s.get("brand") or "auto").strip().lower()
        self.brand = b if b in BRANDS else "auto"
        rem = str(s.get("remote_entity") or "").strip()
        self.remote_entity = rem if rem.startswith("remote.") else ""
        self.broadcast_address = str(s.get("broadcast_address") or "").strip()
        self.alexa_enabled = bool(s.get("alexa_enabled", False))
        self.telegram_enabled = bool(s.get("telegram_enabled", False))
        self.confirm_voice = bool(s.get("confirm_voice", False))
        sp = s.get("speakers")
        self.speakers = [x for x in sp if isinstance(x, str)] if isinstance(sp, list) else []
        try:
            self.volume = max(0.0, min(1.0, float(s.get("volume", 0.5))))
        except (TypeError, ValueError):
            self.volume = 0.5
        try:
            self.step = max(1, min(30, int(s.get("step", 5))))
        except (TypeError, ValueError):
            self.step = 5

    def settings_dict(self) -> dict:
        return {"entity": self.entity, "brand": self.brand, "remote_entity": self.remote_entity,
                "mac": self.mac, "broadcast_address": self.broadcast_address,
                "alexa_enabled": self.alexa_enabled, "telegram_enabled": self.telegram_enabled,
                "confirm_voice": self.confirm_voice, "speakers": self.speakers,
                "volume": self.volume, "step": self.step}

    # ── Canali: caricamento / salvataggio ────────────────────────────────────
    def load_channels(self) -> str:
        self.channels_error = ""
        for path in (canali_path(), DATA_COPY_PATH):
            try:
                if not path.exists():
                    continue
                raw = json.loads(path.read_text(encoding="utf-8-sig"))
                self.channels, self.channel_warnings = normalize_channels(raw)
                self.audio_aliases, _aw = normalize_audio_commands(raw)
                self.channel_warnings = list(self.channel_warnings) + _aw
                return f"{len(self.channels)} canali caricati."
            except Exception as e:
                self.channels_error = f"{path}: {e}"
                logger.warning("TV: errore lettura canali %s: %s", path, e)
        if not self.channels_error:
            self.channels, self.channel_warnings = [], []
        return self.channels_error or "Nessun file canali (si può comunque dire «canale 35»)."

    def set_channels_from_json_text(self, text: str):
        if len(text.encode("utf-8", "ignore")) > MAX_JSON_BYTES:
            raise ValueError("File troppo grande (max 200 KB)")
        try:
            raw = json.loads(text.lstrip("\ufeff"))
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON non valido: {e.msg} (riga {e.lineno}, colonna {e.colno})")
        chans, warnings = normalize_channels(raw)
        audio, _aw = normalize_audio_commands(raw)
        warnings = list(warnings) + _aw
        pretty = json.dumps(raw, indent=2, ensure_ascii=False)
        p = canali_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(pretty, encoding="utf-8")
        tmp.replace(p)
        try:
            DATA_COPY_PATH.parent.mkdir(parents=True, exist_ok=True)
            DATA_COPY_PATH.write_text(pretty, encoding="utf-8")
        except Exception as e:
            logger.debug("TV: copia in /data non riuscita: %s", e)
        self.channels, self.channel_warnings, self.channels_error = chans, warnings, ""
        self.audio_aliases = audio
        return chans, warnings

    # ── Stato della TV ───────────────────────────────────────────────────────
    def _st(self) -> dict:
        try:
            return self.state_fn(self.entity) or {}
        except Exception:
            return {}

    def _state(self) -> str:
        return str(self._st().get("state") or "unknown")

    def _attrs(self) -> dict:
        return self._st().get("attributes") or {}

    def _is_on(self) -> bool:
        return self._state() not in ("off", "unavailable", "unknown", "None")

    def detected_brand(self) -> str:
        """Marca effettiva: quella scelta, altrimenti riconosciuta da nome/attributi ('' = non riconosciuta)."""
        if self.brand != "auto":
            return self.brand
        a = self._attrs()
        toks = set(_strip(f"{self.entity} {a.get('friendly_name') or ''}").split())
        if "sound_output" in a:                       # attributo tipico dell'integrazione webOS
            return "lg"
        for brand, keys in _BRAND_TOKENS.items():
            if toks & keys:
                return brand
        return ""

    def _remote_ent(self) -> str:
        """Entità `remote.*` della stessa TV: quella scelta, altrimenti `remote.<stesso nome>` se esiste."""
        if self.remote_entity:
            return self.remote_entity
        cand = "remote." + self.entity.split(".", 1)[1] if "." in self.entity else ""
        try:
            return cand if cand and self.state_fn(cand) else ""
        except Exception:
            return ""

    async def _press(self, code: str) -> tuple:
        """Preme un tasto del telecomando (codici: UP, ENTER, 0-9, VOLUP…). Ritorna (ok, errore).
        errore == 'unsupported' se per questa TV/marca non c'è modo di premerlo.
        LG: servizio webostv.button. Samsung/Sony: remote.send_command sull'entità remote della TV.
        Marca non riconosciuta: prima come LG (comportamento storico), poi il telecomando se c'è."""
        brand = self.detected_brand()
        last_err = "unsupported"
        if brand in ("", "lg") and code in _LG_KEYS:
            try:
                await self._svc("webostv", "button", {"entity_id": self.entity, "button": _LG_KEYS[code]})
                return True, ""
            except Exception as e:
                last_err = str(e)
                if brand == "lg":
                    return False, last_err
        keys = _REMOTE_KEYS.get(brand)
        rem = self._remote_ent()
        if keys and rem and code in keys:
            try:
                await self._svc("remote", "send_command", {"entity_id": rem, "command": keys[code]})
                return True, ""
            except Exception as e:
                return False, str(e)
        return False, last_err

    def sources(self) -> list:
        sl = self._attrs().get("source_list") or []
        return [str(x) for x in sl] if isinstance(sl, list) else []

    # ── Parsing ──────────────────────────────────────────────────────────────
    @staticmethod
    def _is_numtok(tok: str) -> bool:
        return bool(tok) and (tok.isdigit() or _word_value(tok) is not None)

    def _part_of_longer_number(self, t: str, m, name: str) -> bool:
        """True se l'alias finisce (o comincia) con un numero e nella frase quel numero continua in una parola
        numerica vicina: «canale trenta quattro» = 34, NON l'alias «quattro» (Rete 4); «canale venti due» = 22,
        NON l'alias «canale venti» (20 Mediaset)."""
        toks = name.split()
        before = t[:m.start()].split()[-1:]
        after = t[m.end():].split()[:1]
        if self._is_numtok(toks[-1]) and after and self._is_numtok(after[0]):
            return True
        return bool(self._is_numtok(toks[0]) and before and self._is_numtok(before[0]))

    def _find_channel_name(self, t: str):
        best = None
        for ch in self.channels:
            for n in ch["_names"]:
                m = re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", t)
                if m and not self._part_of_longer_number(t, m, n):
                    if best is None or len(n) > best[0]:
                        best = (len(n), ch)
                    break
        return best[1] if best else None

    def _find_source(self, t: str):
        best = None
        for src in self.sources():
            n = _strip(src)
            if n and re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", t):
                if best is None or len(n) > best[0]:
                    best = (len(n), src)
        return best[1] if best else None

    def parse(self, text: str, force: bool = False):
        """Ritorna {"action", ...} oppure None. force=True (Telegram /tv, API, test) non richiede
        la parola «tv» nella frase."""
        t = _strip(text)
        t = re.sub(r"\bt v\b", "tv", t)                      # Alexa scrive «t. v.» → «t v»
        if not t or len(t) > 120 or _EXCLUDE.search(t):
            return None
        tn = words_to_digits(t)                              # «canale trenta tre» → «canale 33»
        tv = bool(_TV.search(t)) or force
        has_chan_word = bool(re.search(r"\bcanale\b|\bcanali\b", t))
        num = re.search(r"\b(\d{1,3})\b", t)

        if force and re.fullmatch(r"\d{1,4}", t):                 # «/tv 35»
            return {"action": "channel", "numero": t, "label": f"canale {t}"}

        if self.audio_aliases and tv:                        # serve «tv» (o /tv): «alza la voce» da sola è dell'Echo
            for act, phrases in self.audio_aliases.items():
                if any(re.search(r"(?<![a-z0-9])" + re.escape(ph) + r"(?![a-z0-9])", tn) for ph in phrases):
                    by = re.search(r"\bdi\s+(\d{1,2})\b", tn)
                    step = int(by.group(1)) if by else self.step
                    if act == "vol_up":
                        return {"action": "vol_rel", "delta": step}
                    if act == "vol_down":
                        return {"action": "vol_rel", "delta": -step}
                    return {"action": act}
        # canale per nome (file canali) — prima del numero: «canale 5» può essere il nome di un canale
        ch = self._find_channel_name(t) or (self._find_channel_name(tn) if tn != t else None)
        if ch and (tv or has_chan_word or _LEAD.search(t)) and not re.search(r"\b(volume|spegni|muto)\b", t):
            return {"action": "channel", "numero": ch["numero"], "label": ch["nome"]}
        t = tn                                               # da qui in poi: numeri in cifre
        num = re.search(r"\b(\d{1,3})\b", t)
        m = re.search(r"\bcanale\s+(?:numero\s+|n\s*)?(\d{1,4})\b", t)
        if m:
            return {"action": "channel", "numero": m.group(1), "label": f"canale {m.group(1)}"}
        if has_chan_word or (tv and re.search(r"\b(prossimo|successivo|precedente|avanti|indietro)\b", t)):
            if re.search(r"\b(precedente|indietro|giu)\b", t) and has_chan_word:
                return {"action": "channel_down"}
            if re.search(r"\b(successivo|prossimo|avanti|su|cambia)\b", t) and has_chan_word:
                return {"action": "channel_up"}

        if not tv and not re.search(r"\bhdmi\b", t):
            return None

        if re.search(r"\b(spegni|disattiva|chiudi)\b", t):
            return {"action": "off"}
        if re.search(r"\b(riattiva|rimetti|togli)\b.*\b(audio|muto|volume)\b", t) or re.search(r"\b(unmute|riattiva audio)\b", t):
            return {"action": "unmute"}
        if re.search(r"\b(muto|silenzio|zittisci|mute)\b", t):
            return {"action": "mute"}
        if re.search(r"\b(alza|aumenta|piu forte)\b", t) and re.search(r"\b(volume|tv|televisione|televisore|tele|audio)\b", t) \
                and not re.search(r"\bvolume\b.*\b(a|al|su)\s+\d", t):
            by = re.search(r"\bdi\s+(\d{1,2})\b", t)
            return {"action": "vol_rel", "delta": int(by.group(1)) if by else self.step}
        if re.search(r"\b(abbassa|diminuisci|riduci|piu piano)\b", t) and re.search(r"\b(volume|tv|televisione|televisore|tele|audio)\b", t):
            by = re.search(r"\bdi\s+(\d{1,2})\b", t)
            return {"action": "vol_rel", "delta": -(int(by.group(1)) if by else self.step)}
        if re.search(r"\bvolume\b", t) and num:
            lvl = int(num.group(1))
            if 0 <= lvl <= 100:
                return {"action": "vol_set", "level": lvl}
        if re.search(r"\b(pausa|ferma|stop)\b", t):
            return {"action": "pause"}
        if re.search(r"\b(riprendi|riproduci|play|continua)\b", t):
            return {"action": "play"}
        src = self._find_source(t)
        if src and (_LEAD.search(t) or tv):
            return {"action": "source", "source": src}
        m = re.search(r"\bhdmi\s*(\d)\b", t)
        if m:
            return {"action": "source", "source": f"HDMI {m.group(1)}", "fuzzy": True}
        if re.search(r"\b(accendi|attiva|avvia|riaccendi)\b", t):
            return {"action": "on"}
        return None

    # ── Esecuzione ───────────────────────────────────────────────────────────
    def _unreachable_msg(self) -> str:
        return ("📺 La TV risulta spenta o non raggiungibile (in Home Assistant è «unavailable»). "
                "Accendila e riprova; per accenderla a distanza inserisci il suo MAC nella scheda 📺 TV.")

    async def _svc(self, domain: str, service: str, data: dict):
        return await self.rest.call_service(domain, service, data)

    async def _wake(self) -> bool:
        """Accende la TV: Wake-on-LAN con il MAC (se c'è), altrimenti media_player.turn_on."""
        if self.mac:
            try:
                data = {"mac": self.mac}
                if self.broadcast_address:
                    data["broadcast_address"] = self.broadcast_address
                await self._svc("wake_on_lan", "send_magic_packet", data)
                return True
            except Exception as e:
                logger.warning("TV: wake_on_lan non disponibile (%s): provo media_player.turn_on", e)
        try:
            await self._svc("media_player", "turn_on", {"entity_id": self.entity})
            return True
        except Exception as e:
            logger.warning("TV: accensione fallita: %s", e)
            return False

    async def _ensure_on(self) -> bool:
        if self._is_on():
            return True
        if not await self._wake():
            return False
        for _ in range(WAKE_WAIT_S):
            await asyncio.sleep(1)
            if self._is_on():
                await asyncio.sleep(2)            # la TV deve finire di avviarsi
                return True
        return False

    async def _set_channel(self, numero: str) -> bool:
        """Prima la chiamata diretta del canale; se la TV non lo trova, i tasti numerici."""
        try:
            await self._svc("media_player", "play_media", {"entity_id": self.entity,
                            "media_content_type": "channel", "media_content_id": numero})
            return True
        except Exception as e:
            logger.info("TV: play_media channel %s non riuscito (%s): provo con i tasti", numero, e)
        for d in list(numero) + ["ENTER"]:
            ok, err = await self._press(d)
            if not ok:
                logger.warning("TV: cambio canale con i tasti fallito (%s): %s", self.detected_brand() or "marca n/d", err)
                return False
            if d != "ENTER":
                await asyncio.sleep(0.35)
        return True

    async def _fresh_attrs(self) -> dict:
        """Attributi aggiornati della TV (REST); se non disponibile, quelli in cache."""
        try:
            st = await self.rest.get_state(self.entity)
            if isinstance(st, dict) and st.get("attributes") is not None:
                return st.get("attributes") or {}
        except Exception:
            pass
        return self._attrs()

    async def _volume_by_keys(self, up: bool, n: int) -> bool:
        """n pressioni del tasto volume: tasto fisico del telecomando se la marca lo permette (funziona anche
        con barra audio/ARC), altrimenti i servizi media_player.volume_up/down."""
        code = "VOLUP" if up else "VOLDOWN"
        ok, _err = await self._press(code)
        if ok:
            for _ in range(n - 1):
                await asyncio.sleep(0.15)
                ok, _err = await self._press(code)
                if not ok:
                    break
            return ok
        svc = "volume_up" if up else "volume_down"
        try:
            for i in range(n):
                await self._svc("media_player", svc, {"entity_id": self.entity})
                if i < n - 1:
                    await asyncio.sleep(0.15)
            return True
        except Exception as e:
            logger.warning("TV: volume con i servizi %s fallito: %s", svc, e)
            return False

    async def _volume_relative(self, delta: int) -> tuple:
        """Alza/abbassa di `delta` punti. Se la TV espone il livello: volume_set e verifica che sia cambiato
        davvero (con uscita audio esterna/ARC la TV accetta il comando ma il volume non si muove): se non
        è cambiato, o se volume_set dà errore, si ripiega sui tasti volume. Senza livello: tasti volume."""
        up = delta > 0
        n = max(1, min(abs(delta), 20))
        word = "alzato" if up else "abbassato"
        cur = self._attrs().get("volume_level")
        if isinstance(cur, (int, float)):
            old_pct = round(cur * 100)
            new = max(0, min(100, old_pct + delta))
            try:
                await self._svc("media_player", "volume_set", {"entity_id": self.entity, "volume_level": new / 100})
            except Exception as ex:
                logger.info("TV: volume_set non riuscito (%s): provo con i tasti volume", str(ex)[:100])
                ok = await self._volume_by_keys(up, n)
                return ok, f"📺 Volume {word}." if ok else "📺 Volume non modificato."
            if new == old_pct:                                   # già al minimo/massimo
                return True, f"📺 Volume {new}%."
            await asyncio.sleep(1.0)
            lvl = (await self._fresh_attrs()).get("volume_level")
            if isinstance(lvl, (int, float)) and abs(lvl - cur) < 0.004:
                logger.info("TV: volume_set accettato ma il livello è rimasto %d%% (uscita audio esterna?): "
                            "uso i tasti volume", old_pct)
                if await self._volume_by_keys(up, n):
                    return True, f"📺 Volume {word}."
            logger.info("TV: volume %d%% → %d%% (volume_set)", old_pct, new)
            return True, f"📺 Volume {new}%."
        ok = await self._volume_by_keys(up, n)
        return ok, f"📺 Volume {word}." if ok else "📺 Volume non modificato."

    async def execute(self, cmd: dict) -> tuple:
        """Esegue il comando. Ritorna (ok, messaggio)."""
        if not self.entity:
            return False, "TV non configurata: scegli l'entità nella scheda 📺 TV."
        if self.rest is None:
            return False, "Home Assistant non raggiungibile."
        a, e = cmd["action"], self.entity
        try:
            if a == "on":
                if self._is_on():
                    return True, "📺 La TV è già accesa."
                if self._state() == "unavailable" and not self.mac:
                    return False, self._unreachable_msg()
                ok = await self._ensure_on()
                return ok, "📺 TV accesa." if ok else "📺 Non riesco ad accendere la TV (controlla MAC / Wake-on-LAN)."
            if a == "off":
                if self._state() == "off":
                    return True, "📺 La TV è già spenta."
                await self._svc("media_player", "turn_off", {"entity_id": e})
                return True, "📺 TV spenta."

            # tutti gli altri comandi richiedono la TV accesa
            if not self._is_on():
                if self._state() == "unavailable" and not self.mac:
                    return False, self._unreachable_msg()          # senza MAC HA non può riaccenderla
                if not self.mac and a not in ("channel", "source"):
                    return False, "📺 La TV è spenta. Dì «accendi la tv»."
                if not await self._ensure_on():
                    return False, "📺 La TV è spenta e non sono riuscito ad accenderla (controlla il MAC / Wake-on-LAN)."

            if a == "channel":
                ok = await self._set_channel(cmd["numero"])
                return ok, f"📺 {cmd['label'].capitalize()}" if ok else "📺 Cambio canale non riuscito."
            if a == "channel_up":
                await self._svc("media_player", "media_next_track", {"entity_id": e})
                return True, "📺 Canale successivo."
            if a == "channel_down":
                await self._svc("media_player", "media_previous_track", {"entity_id": e})
                return True, "📺 Canale precedente."
            if a == "vol_set":
                await self._svc("media_player", "volume_set", {"entity_id": e, "volume_level": cmd["level"] / 100})
                return True, f"📺 Volume {cmd['level']}%."
            if a == "vol_rel":
                return await self._volume_relative(cmd["delta"])
            if a in ("mute", "unmute"):
                await self._svc("media_player", "volume_mute", {"entity_id": e, "is_volume_muted": a == "mute"})
                return True, "📺 Audio disattivato." if a == "mute" else "📺 Audio riattivato."
            if a == "pause":
                await self._svc("media_player", "media_pause", {"entity_id": e})
                return True, "📺 In pausa."
            if a == "play":
                await self._svc("media_player", "media_play", {"entity_id": e})
                return True, "📺 Riproduzione."
            if a == "source":
                src = cmd["source"]
                if cmd.get("fuzzy"):                       # «hdmi 2» → «HDMI 2» o come lo chiama la TV
                    src = next((s for s in self.sources() if _strip(s) == _strip(src)), src)
                await self._svc("media_player", "select_source", {"entity_id": e, "source": src})
                return True, f"📺 {src}"
        except Exception as ex:
            logger.warning("TV: comando %s fallito: %s", a, ex)
            return False, f"📺 Comando non riuscito: {str(ex)[:120]}"
        return False, "📺 Comando non riconosciuto."

    # ── Ingressi: voce, Telegram, API ────────────────────────────────────────
    async def ask(self, text: str, source: str = "api", force: bool = False) -> dict:
        res = {"ok": True, "matched": False, "message": "", "executed": False}
        cmd = self.parse(text, force=force)
        if cmd is None:
            return res
        res["matched"], res["command"] = True, cmd
        ok, msg = await self.execute(cmd)
        res["executed"], res["message"] = ok, msg
        logger.info("TV [%s]: «%s» → %s (%s)", source, text, cmd["action"], "ok" if ok else msg)
        if source == "alexa" and self.telegram_enabled and self.notifier:
            try:
                await self.notifier.send_html(msg, force=True)
            except Exception as e:
                logger.warning("TV: invio Telegram fallito: %s", e)
        if self.confirm_voice and self.speakers and source in ("alexa", "test"):
            try:
                from alexa_tts import speak_on_speakers
                plain = re.sub(r"[^\w\s%,.àèéìòù-]", "", msg).strip()
                r = await speak_on_speakers(self.rest, self.speakers, plain, self.volume)
                res["alexa_ok"] = r.get("ok", 0)
            except Exception as e:
                logger.warning("TV: conferma vocale fallita: %s", e)
        return res

    async def telegram_text(self, text: str):
        """Frase libera o «/tv …» scritta al bot. Ritorna il testo di risposta o None
        (None = non è per la TV: prosegue verso l'AI)."""
        raw = (text or "").strip()
        low = raw.lower()
        if low == "/tv" or low.startswith("/tv "):
            arg = raw[3:].strip()
            if not self.entity:
                return "📺 TV non configurata: scegli l'entità nella scheda 📺 TV delle Impostazioni."
            if not arg:
                return self.help_text()
            r = await self.ask(arg, source="telegram", force=True)
            return r["message"] if r["matched"] else ("📺 Non ho capito. " + self.help_text())
        if not self.entity:
            return None
        r = await self.ask(raw, source="telegram", force=False)
        return r["message"] if r["matched"] else None

    def help_text(self) -> str:
        st = self._state()
        a = self._attrs()
        lines = [f"📺 <b>TV</b> — {st}"]
        if isinstance(a.get("volume_level"), (int, float)):
            lines.append(f"Volume {round(a['volume_level'] * 100)}%" + (" (muto)" if a.get("is_volume_muted") else ""))
        if a.get("source"):
            lines.append(f"Sorgente: {a['source']}")
        lines.append("\nEsempi: /tv accendi · /tv spegni · /tv volume 30 · /tv alza il volume · /tv muto · "
                     "/tv canale 35 · /tv canale successivo · /tv netflix · /tv hdmi 2")
        return "\n".join(lines)

    @staticmethod
    def _ts_age(ts):
        """Età in secondi di un last_called_timestamp (epoch s/ms o ISO), None se non interpretabile."""
        try:
            if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.strip().replace(".", "", 1).isdigit()):
                v = float(ts)
                if v > 1e11:                      # millisecondi
                    v /= 1000.0
                return time.time() - v
            if isinstance(ts, str) and ts.strip():
                from datetime import datetime, timezone
                d = datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))
                if d.tzinfo is None:
                    # senza fuso non si sa se è ora locale o UTC: se in UNA delle due letture la frase è
                    # recente, la si considera recente (meglio eseguire che perdere un comando vero)
                    as_local = time.time() - d.timestamp()
                    as_utc = (datetime.now(timezone.utc) - d.replace(tzinfo=timezone.utc)).total_seconds()
                    return min(as_local, as_utc, key=abs)
                return (datetime.now(timezone.utc) - d).total_seconds()
        except Exception:
            pass
        return None

    def on_state_changed(self, eid: str, new_state: dict):
        """Ascolto delle frasi pronunciate (Alexa Media Player: last_called_summary). Leggero."""
        try:
            if not (self.alexa_enabled and self.entity) or not new_state:
                return
            attrs = new_state.get("attributes") or {}
            text = attrs.get("last_called_summary")
            if not text and eid.startswith("sensor.") and ("last_called" in eid or "last_alexa" in eid):
                text = new_state.get("state")
            if not text or not isinstance(text, str) or text in ("unknown", "unavailable"):
                return
            key = _strip(text)
            if not key:
                return

            # Stessa frase già gestita: l'Echo cambia stato/volume e rimanda lo stesso last_called_summary.
            # Con il timestamp della chiamata si agisce UNA sola volta per frase (e mai su quella vecchia
            # rimasta nell'attributo dopo un riavvio di HomeMind).
            ts = attrs.get("last_called_timestamp")
            if ts not in (None, ""):
                prev = self._last_ts.get(eid)
                if prev == ts:
                    return
                self._last_ts[eid] = ts
                if prev is None:
                    age = self._ts_age(ts)
                    if age is not None and age > 60:
                        logger.info("TV voce: «%s» (%s) è una frase vecchia di %d s, ignorata", text, eid, age)
                        return

            now = time.monotonic()
            for k in [k for k, t0 in self._recent.items() if now - t0 > 10]:
                self._recent.pop(k, None)
            for k in [k for k, t0 in self._recent_utt.items() if now - t0 > 60]:
                self._recent_utt.pop(k, None)
            for k in [k for k, v in self._recent_eid.items() if now - v[1] > 3]:
                self._recent_eid.pop(k, None)
            # Una pronuncia = (frase, timestamp di Alexa). Con il timestamp la STESSA frase detta di nuovo
            # (es. «alza il volume della tv» due volte di fila) è un comando nuovo e viene eseguita; prima
            # veniva scartata per 10 s. Senza timestamp resta il vecchio blocco di 10 s sulla frase.
            utt = (key, str(ts)) if ts not in (None, "") else None
            if utt is not None:
                if utt in self._recent_utt:
                    return                                    # stessa pronuncia già vista (altra entità)
                seen = self._recent_eid.get(key)
                if seen and seen[0] != eid:
                    return                                    # stessa frase, subito dopo, da un'altra entità
            elif key in self._recent:
                return
            cmd = self.parse(text)
            if self._last_text.get(eid) != key:               # una riga di log per frase, non una per evento
                self._last_text[eid] = key
                logger.info("TV voce: frase ricevuta da %s: «%s» → %s", eid, text,
                            cmd["action"] if cmd else "non è un comando TV (ignorata)")
            if cmd is None:
                return
            if utt is not None:
                self._recent_utt[utt] = now
                self._recent_eid[key] = (eid, now)
            else:
                self._recent[key] = now
            task = asyncio.get_running_loop().create_task(self.ask(text, source="alexa"))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        except Exception as e:
            logger.warning("TV on_state_changed: %s", e)

    # ── Telecomando a bottoni (Telegram) ─────────────────────────────────────
    REMOTE_PHRASES = {"telecomando", "il telecomando", "telecomando tv", "tv telecomando", "telecomando della tv",
                      "telecomando televisione", "telecomando della televisione", "apri telecomando",
                      "apri il telecomando", "mostra telecomando", "mostra il telecomando", "mostrami il telecomando",
                      "remote", "tv remote"}
    # codice del bottone Telegram → codice interno del tasto (poi _press lo traduce per marca)
    REMOTE_BUTTONS = {"UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT", "OK": "ENTER", "BACK": "BACK",
                      "HOME": "HOME", "MENU": "MENU", "INFO": "INFO", "EXIT": "EXIT",
                      **{str(d): str(d) for d in range(10)}}

    @classmethod
    def is_remote_request(cls, text: str) -> bool:
        """True solo per la richiesta esatta («telecomando», «/telecomando»…): frasi più lunghe vanno all'AI."""
        return _strip(text) in cls.REMOTE_PHRASES

    def remote_text(self) -> str:
        st = self._state()
        a = self._attrs()
        extra = []
        if isinstance(a.get("volume_level"), (int, float)):
            extra.append(f"🔊 {round(a['volume_level'] * 100)}%" + (" (muto)" if a.get("is_volume_muted") else ""))
        if a.get("source"):
            extra.append(f"📥 {html.escape(str(a['source']))}")
        return f"📺 <b>Telecomando TV</b> — {st}" + (("\n" + " · ".join(extra)) if extra else "")

    def remote_markup(self, page: str = "main") -> dict:
        """Tastiera inline. callback_data = «tvr:<CODICE>» (sempre sotto i 64 byte di Telegram)."""
        def b(label, code):
            return {"text": label, "callback_data": f"tvr:{code}"}
        if page == "num":
            rows = [[b("1", "1"), b("2", "2"), b("3", "3")], [b("4", "4"), b("5", "5"), b("6", "6")],
                    [b("7", "7"), b("8", "8"), b("9", "9")],
                    [b("🔙 Telecomando", "PG_MAIN"), b("0", "0"), b("OK", "OK")]]
        elif page == "src":
            srcs = self.sources()[:24]
            rows = [[b(srcs[i], f"S{i}")] + ([b(srcs[i + 1], f"S{i + 1}")] if i + 1 < len(srcs) else [])
                    for i in range(0, len(srcs), 2)]
            rows.append([b("🔙 Telecomando", "PG_MAIN")])
        else:
            rows = [[b("⏻ On/Off", "PWR"), b("🔇 Muto", "MUTE"), b("🏠 Home", "HOME")],
                    [b("🔉 Vol −", "VOLDOWN"), b("⬆️", "UP"), b("🔊 Vol +", "VOLUP")],
                    [b("⬅️", "LEFT"), b("OK", "OK"), b("➡️", "RIGHT")],
                    [b("↩️ Indietro", "BACK"), b("⬇️", "DOWN"), b("⚙️ Menu", "MENU")],
                    [b("➖ Canale", "CHDOWN"), b("ℹ️ Info", "INFO"), b("➕ Canale", "CHUP")],
                    [b("▶️", "PLAY"), b("⏸", "PAUSE"), b("✖️ Esci", "EXIT")],
                    [b("🔢 Numeri", "PG_NUM"), b("📥 Ingressi", "PG_SRC")]]
        return {"inline_keyboard": rows}

    async def remote_press(self, code: str) -> tuple:
        """Esegue un tasto del telecomando. Ritorna (ok, messaggio d'errore o '')."""
        if not self.entity:
            return False, "📺 TV non configurata: scegli l'entità nella scheda 📺 TV."
        if self.rest is None:
            return False, "Home Assistant non raggiungibile."
        e = self.entity
        try:
            if code == "PWR":
                ok, msg = await self.execute({"action": "off" if self._is_on() else "on"})
                return ok, "" if ok else msg
            if not self._is_on():
                if self._state() == "unavailable":
                    return False, self._unreachable_msg()
                return False, "📺 La TV è spenta: premi ⏻ On/Off per accenderla."
            if code in self.REMOTE_BUTTONS:
                ok, err = await self._press(self.REMOTE_BUTTONS[code])
                if not ok:
                    if err == "unsupported":
                        return False, ("📺 Questo tasto non è disponibile per la tua TV: nella scheda 📺 TV scegli la marca "
                                       "e, se esiste, l'entità «telecomando» (remote.…).")
                    return False, f"📺 Tasto non riuscito: {err[:120]}"
            elif code == "VOLUP":
                await self._svc("media_player", "volume_up", {"entity_id": e})
            elif code == "VOLDOWN":
                await self._svc("media_player", "volume_down", {"entity_id": e})
            elif code == "MUTE":
                muted = bool(self._attrs().get("is_volume_muted"))
                await self._svc("media_player", "volume_mute", {"entity_id": e, "is_volume_muted": not muted})
            elif code == "CHUP":
                await self._svc("media_player", "media_next_track", {"entity_id": e})
            elif code == "CHDOWN":
                await self._svc("media_player", "media_previous_track", {"entity_id": e})
            elif code == "PLAY":
                await self._svc("media_player", "media_play", {"entity_id": e})
            elif code == "PAUSE":
                await self._svc("media_player", "media_pause", {"entity_id": e})
            elif re.fullmatch(r"S\d{1,2}", code):
                srcs = self.sources()
                i = int(code[1:])
                if i >= len(srcs):
                    return False, "📺 Ingresso non più disponibile, riapri l'elenco."
                await self._svc("media_player", "select_source", {"entity_id": e, "source": srcs[i]})
            else:
                return False, "📺 Tasto non riconosciuto."
            return True, ""
        except Exception as ex:
            logger.warning("TV telecomando: tasto %s fallito: %s", code, ex)
            return False, f"📺 Tasto non riuscito: {str(ex)[:120]}"

    # ── Stato per la dashboard ───────────────────────────────────────────────
    def status(self) -> dict:
        a = self._attrs()
        return {
            **self.settings_dict(),
            "tv_state": self._state() if self.entity else "",
            "tv_volume": round(a["volume_level"] * 100) if isinstance(a.get("volume_level"), (int, float)) else None,
            "tv_source": a.get("source") or "",
            "brand_detected": self.detected_brand() if self.entity else "",
            "remote_detected": self._remote_ent() if self.entity else "",
            "sources": self.sources(),
            "channels": [{"nome": c["nome"], "numero": c["numero"], "alias": c["alias"]} for c in self.channels],
            "channel_warnings": self.channel_warnings, "channels_error": self.channels_error,
        }
