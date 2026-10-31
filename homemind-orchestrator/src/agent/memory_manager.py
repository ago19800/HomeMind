"""
agent/memory_manager.py — Memoria persistente tra conversazioni.

HomeMind impara fatti su di te nel tempo e li usa per rispondere
in modo sempre più personale.

Come funziona:
  1. Dopo ogni conversazione, chiede all'AI di estrarre fatti utili
  2. Li salva in /data/homemind_memory.json
  3. Ad ogni nuovo messaggio, inietta i fatti rilevanti nel system prompt
  4. L'utente può vedere/modificare/cancellare la memoria via Telegram

Esempi di fatti memorizzati:
  - "Agostino torna dal lavoro tra le 17:00 e le 18:30"
  - "Rosa preferisce la casa a 21°C"
  - "La lavatrice si fa di solito il sabato mattina"
  - "Il cane si chiama Rex"
  - "Preferisce le luci calde (2700K) la sera"

Comandi Telegram:
  /memoria       → mostra tutto ciò che HomeMind sa
  /dimentica xxx → cancella un fatto specifico
  /memoria reset → cancella tutto
"""

import asyncio
import html
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("homemind.memory")

MEMORY_PATH  = Path("/data/homemind_memory.json")
MAX_FACTS    = 50    # massimo numero di fatti memorizzati
MAX_FACT_LEN = 200   # caratteri massimi per fatto


class MemoryManager:
    """Gestisce la memoria persistente di HomeMind."""

    def __init__(self, ai=None):
        self.ai     = ai
        self._facts: list[dict] = []  # [{text, category, ts, source, person?}]
        # Callback opzionali (impostati da chi crea il manager): niente dipendenze circolari.
        self.habits_providers: list = []   # () -> list[str]  abitudini OSSERVATE dai dati reali
        self.persons_cb = None             # () -> list[str]  nomi delle persone della casa
        self._load()

    def set_habits_provider(self, cb):
        """Registra una funzione che ritorna righe di abitudini calcolate dai dati (non dalle chat)."""
        if cb and cb not in self.habits_providers:
            self.habits_providers.append(cb)

    def observed_habits(self) -> list:
        """Abitudini osservate (routine GPS, uso dei dispositivi…): calcolate, quindi non inventate dall'AI."""
        out = []
        for cb in self.habits_providers:
            try:
                out.extend(str(x) for x in (cb() or []) if x)
            except Exception as e:
                logger.debug("Memoria: provider abitudini errore: %s", e)
        return out

    def known_persons(self) -> list:
        try:
            return [str(n) for n in (self.persons_cb() if self.persons_cb else []) if n]
        except Exception:
            return []

    @staticmethod
    def _person_key(name) -> str:
        return (name or "").strip().lower()

    # ─────────────────────────────────────────────────────────────────────────
    # Persistenza

    # Keyword di feature rimosse — fatti contenenti queste parole vengono
    # eliminati automaticamente al caricamento per evitare comportamenti ghost
    _REMOVED_FEATURES_KW = [
        "automazione_hm", "automazioni_hm", "automazioni intelligenti",
        "smart automation", "se allora", "quando fai",
        "/auto_hm", "cancella_automazione", "pausa_automazione",
    ]

    def _load(self):
        try:
            if MEMORY_PATH.exists():
                data = json.loads(MEMORY_PATH.read_text())
                self._facts = data.get("facts", [])
                # Rimuovi fatti di feature non più presenti
                before = len(self._facts)
                self._facts = [
                    f for f in self._facts
                    if not any(
                        kw in f.get("text", "").lower()
                        for kw in self._REMOVED_FEATURES_KW
                    )
                ]
                removed = before - len(self._facts)
                if removed:
                    logger.info("Memoria: rimossi %d fatti obsoleti (feature rimosse)", removed)
                    self._save()
                logger.info("Memoria caricata: %d fatti", len(self._facts))
            else:
                self._facts = []
        except Exception as e:
            logger.warning("Memoria load error: %s", e)
            self._facts = []

    def _save(self):
        try:
            MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            MEMORY_PATH.write_text(json.dumps(
                {"facts": self._facts, "updated": time.time()},
                indent=2, ensure_ascii=False
            ))
        except Exception as e:
            logger.warning("Memoria save error: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Lettura

    def get_memory_prompt(self) -> str:
        """Restituisce un blocco testo da iniettare nel system prompt."""
        habits = self.observed_habits()
        if not self._facts and not habits:
            return ""
        lines = ["=== MEMORIA PERSISTENTE ===",
                 "Fatti che hai imparato su chi vive in casa — usali per personalizzare le risposte. "
                 "Se un fatto riguarda una persona precisa, riferiscilo SOLO a lei (non all'utente che scrive, "
                 "a meno che non sia lei):"]
        for f in self._facts[-30:]:  # ultimi 30 fatti
            who = f.get("person")
            lines.append(f"  • [{who.capitalize()}] {f['text']}" if who else f"  • {f['text']}")
        if habits:
            lines.append("Abitudini OSSERVATE dai dati reali della casa (affidabili, aggiornate ogni notte):")
            for h in habits[:40]:
                lines.append(f"  • {h}")
        lines.append("")
        return "\n".join(lines)

    def get_facts_display(self) -> str:
        """Testo leggibile per il comando /memoria."""
        habits = self.observed_habits()
        if not self._facts and not habits:
            return "🧠 Non ho ancora memorizzato nulla su di te.\n\nParla con me e imparerò le tue abitudini nel tempo!"

        lines = [f"🧠 <b>Cosa so sulla famiglia</b> ({len(self._facts)} fatti"
                 + (f", {len(habits)} abitudini osservate" if habits else "") + ")\n"]
        icons = {
            "abitudini": "⏰", "preferenze": "❤️", "casa": "🏠",
            "persone": "👤", "energia": "⚡", "dispositivi": "🔌",
            "generale": "💡"
        }
        # raggruppa per persona (chi non è attribuito → «Casa / tutti»)
        by_person: dict = {}
        for f in self._facts:
            by_person.setdefault(f.get("person") or "", []).append(f)
        order = sorted(by_person, key=lambda k: (k == "", k))
        for who in order:
            lines.append(f"👤 <b>{html.escape(who.capitalize())}</b>" if who else "🏠 <b>Casa / tutti</b>")
            cats: dict = {}
            for f in by_person[who]:
                cats.setdefault(f.get("category", "generale"), []).append(f["text"])
            for cat, facts in cats.items():
                for t in facts:
                    lines.append(f"  {icons.get(cat, '💡')} {html.escape(t)}")
            lines.append("")

        if habits:
            lines.append("📊 <b>Abitudini osservate</b> <i>(calcolate dai dati reali)</i>")
            for h in habits[:30]:
                lines.append(f"  • {html.escape(h)}")
            lines.append("")

        lines.append("<i>Usa /dimentica &lt;testo&gt; per rimuovere un fatto</i>")
        lines.append("<i>Usa /memoria reset per cancellare tutto</i>")
        out = "\n".join(lines)
        return out if len(out) <= 3900 else out[:3850] + "\n<i>… (troncato)</i>"

    # ─────────────────────────────────────────────────────────────────────────
    # Scrittura

    # Parole "stop" che non contribuiscono al rilevamento conflitti
    _STOPWORDS = {
        "il","la","lo","i","gli","le","un","una","uno",
        "e","di","da","in","con","su","per","tra","fra",
        "che","qui","ha","ho","si","ci","ne","mi","ti","vi",
        "the","is","are","has","have","of","to","in","at",
    }

    def _find_conflict(self, text: str, category: str, person: str = "") -> "Optional[int]":
        """Cerca un fatto esistente che potrebbe essere una versione precedente
        dello stesso concetto (stesso soggetto + stessa categoria = conflitto).
        Ritorna l'indice del fatto da sostituire, oppure None.
        """
        strip_chars = ".,!?;:"
        words_new = {
            w.lower().strip(strip_chars) for w in text.split()
            if len(w) > 3 and w.lower().strip(strip_chars) not in self._STOPWORDS
        }
        if len(words_new) < 2:
            return None

        for i, f in enumerate(self._facts):
            if f.get("category") != category:
                continue
            if self._person_key(f.get("person")) != person:      # «Rosa vuole 22°» ≠ «Agostino vuole 21°»
                continue
            # Duplicato esatto
            if f["text"].lower() == text.lower():
                return i
            # Overlap semantico: >= 50% delle parole significative in comune
            words_old = {
                w.lower().strip(strip_chars) for w in f["text"].split()
                if len(w) > 3 and w.lower().strip(strip_chars) not in self._STOPWORDS
            }
            if not words_old:
                continue
            overlap = words_new & words_old
            ratio   = len(overlap) / min(len(words_new), len(words_old))
            if ratio >= 0.5:
                logger.debug(
                    "Memoria: conflitto rilevato (overlap %.0f%%) -- OLD: '%s' NEW: '%s'",
                    ratio * 100, f["text"][:50], text[:50]
                )
                return i
        return None

    def add_fact(self, text: str, category: str = "generale", source: str = "manual", person: str = None):
        """Aggiunge un fatto. Se ne trova uno simile (stesso soggetto + stessa categoria),
        lo aggiorna invece di accumulare entrambi.
        """
        text = text.strip()[:MAX_FACT_LEN]
        if not text:
            return

        person = self._person_key(person)
        conflict_idx = self._find_conflict(text, category, person)

        if conflict_idx is not None:
            old_text = self._facts[conflict_idx]["text"]
            if old_text.lower() == text.lower():
                # Duplicato esatto: aggiorna solo il timestamp
                self._facts[conflict_idx]["ts"] = time.time()
                logger.debug("Memoria: fatto gia presente, aggiornato timestamp")
            else:
                # Informazione aggiornata: sostituisci il vecchio
                logger.info(
                    "Memoria: aggiornato fatto [%s]  OLD: %s  NEW: %s",
                    category, old_text[:60], text[:60]
                )
                self._facts[conflict_idx] = {
                    "text":     text,
                    "category": category,
                    "ts":       time.time(),
                    "source":   source,
                    "replaced": old_text[:100],
                    **({"person": person} if person else {}),
                }
            self._save()
            return

        # Nessun conflitto: aggiunge come nuovo fatto
        self._facts.append({
            "text":     text,
            "category": category,
            "ts":       time.time(),
            "source":   source,
            **({"person": person} if person else {}),
        })
        if len(self._facts) > MAX_FACTS:
            self._facts = self._facts[-MAX_FACTS:]
        self._save()
        logger.info("Memoria: aggiunto fatto [%s] %s", category, text[:60])

    def forget(self, query: str) -> int:
        """Rimuove fatti che contengono la query. Ritorna quanti rimossi."""
        query_low = query.lower().strip()
        before = len(self._facts)
        self._facts = [f for f in self._facts
                       if query_low not in f["text"].lower()]
        removed = before - len(self._facts)
        if removed:
            self._save()
            logger.info("Memoria: rimossi %d fatti contenenti '%s'", removed, query)
        return removed

    def reset(self):
        """Cancella tutta la memoria."""
        count = len(self._facts)
        self._facts = []
        self._save()
        logger.info("Memoria: reset completo (%d fatti cancellati)", count)
        return count

    # ─────────────────────────────────────────────────────────────────────────
    # Estrazione automatica AI

    # Nomi «si chiama X»: l'AI tende a inventarli (es. «L'utente si chiama Gianni» senza che nessuno l'abbia detto)
    _NAME_RE = re.compile(r"(?:si chiama(?:no)?|chiamat[oa]|il nome è|il nome e'|nome:)\s+([A-ZÀ-Ý][\wà-ÿ'’-]+)")

    @classmethod
    def _grounded(cls, fact_text: str, user_text: str) -> bool:
        """False se il fatto dichiara un nome che l'utente non ha mai scritto (allucinazione)."""
        low = user_text.lower()
        for name in cls._NAME_RE.findall(fact_text):
            if name.lower() not in low:
                return False
        return True

    async def extract_from_conversation(self, conversation: list[dict]):
        """
        Analizza una conversazione e estrae fatti utili da memorizzare.
        Chiamata alla fine di ogni sessione di chat.
        conversation: [{"role": "user"/"assistant", "content": "..."}]

        Solo ciò che dice l'UTENTE può diventare un fatto: le risposte del bot servono da contesto
        (altrimenti un'ipotesi sbagliata del bot finirebbe in memoria come se fosse vera).
        """
        if not self.ai or len(conversation) < 2:
            return

        recent = conversation[-10:]
        user_text = "\n".join(m["content"] for m in recent if m.get("role") == "user")
        if not user_text.strip():
            return

        # Costruisci testo conversazione
        conv_text = "\n".join(
            (f"UTENTE: {m['content'][:300]}" if m.get("role") == "user"
             else f"BOT (solo contesto, NON estrarre fatti da qui): {m['content'][:200]}")
            for m in recent
        )

        existing = "\n".join(
            f"- {('[' + f['person'].capitalize() + '] ') if f.get('person') else ''}{f['text']}"
            for f in self._facts[-20:]
        )
        persons = self.known_persons()

        prompt = (
            "Analizza questa conversazione con un sistema domotico e estrai fatti "
            "PERMANENTI e UTILI su chi vive in casa, da memorizzare per personalizzare le risposte future.\n\n"
            "CONVERSAZIONE:\n" + conv_text + "\n\n"
            "FATTI GIA MEMORIZZATI:\n" + (existing or "nessuno") + "\n\n"
            "PERSONE DELLA CASA: " + (", ".join(persons) if persons else "non note") + "\n\n"
            "REGOLE:\n"
            "- Estrai SOLO ciò che l'UTENTE ha detto esplicitamente (mai dedurre, mai inventare nomi)\n"
            "- Estrai SOLO fatti duraturi (abitudini, preferenze, nomi, orari abituali)\n"
            "- NON estrarre stati temporanei (es. 'oggi ha acceso la luce')\n"
            "- NON estrarre le abitudini di orari di uscita/rientro/luoghi: le calcolo già dai dati reali\n"
            "- Se il fatto riguarda una persona precisa, indicala in \"person\" (usa uno dei nomi delle "
            "PERSONE DELLA CASA); se vale per tutti o non è chiaro, metti null\n"
            "- Se l'utente AGGIORNA una preferenza (es. cambia temperatura preferita), "
            "  includi il NUOVO valore -- il vecchio verra sostituito automaticamente\n"
            "- NON includere fatti identici a quelli gia memorizzati\n"
            "- Massimo 3 fatti per conversazione\n"
            "- Se non ci sono fatti utili, rispondi solo: NESSUNO\n\n"
            "Rispondi in formato JSON esatto:\n"
            "[{\"text\": \"fatto\", \"category\": \"abitudini|preferenze|casa|persone|energia|dispositivi|generale\", "
            "\"person\": \"Nome oppure null\"}]\n"
            "Oppure: NESSUNO"
        )

        try:
            response = await self.ai.ask(
                "Sei un estrattore di fatti utili. Rispondi solo in JSON o NESSUNO.",
                prompt,
                max_tokens=400
            )

            if not response or "NESSUNO" in response.upper():
                return

            # Parsing JSON robusto
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if not match:
                return

            facts = json.loads(match.group())
            known = {p.lower(): p for p in persons}
            added = 0
            for f in facts:
                if not (isinstance(f, dict) and f.get("text")):
                    continue
                text = str(f["text"])
                if not self._grounded(text, user_text):
                    logger.info("Memoria: scartato fatto non fondato (nome mai detto dall'utente): %s", text[:80])
                    continue
                who = f.get("person")
                who = str(who).strip() if who and str(who).strip().lower() not in ("null", "none", "nessuno", "tutti", "") else ""
                if who and known and who.lower() not in known:
                    who = ""          # nome non della casa → non lo attribuisco a nessuno
                self.add_fact(text, category=f.get("category", "generale"), source="ai_extract", person=who or None)
                added += 1
            if added:
                logger.info("Memoria: estratti %d fatti dalla conversazione", added)

        except Exception as e:
            logger.debug("Memoria extract error: %s", e)
