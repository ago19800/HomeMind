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
import json
import logging
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
        self._facts: list[dict] = []  # [{text, category, ts, source}]
        self._load()

    # ─────────────────────────────────────────────────────────────────────────
    # Persistenza

    def _load(self):
        try:
            if MEMORY_PATH.exists():
                data = json.loads(MEMORY_PATH.read_text())
                self._facts = data.get("facts", [])
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
        if not self._facts:
            return ""
        lines = ["=== MEMORIA PERSISTENTE ===",
                 "Fatti che hai imparato sull'utente nel tempo — usali per personalizzare le risposte:"]
        for f in self._facts[-30:]:  # ultimi 30 fatti
            lines.append(f"  • {f['text']}")
        lines.append("")
        return "\n".join(lines)

    def get_facts_display(self) -> str:
        """Testo leggibile per il comando /memoria."""
        if not self._facts:
            return "🧠 Non ho ancora memorizzato nulla su di te.\n\nParla con me e imparerò le tue abitudini nel tempo!"

        lines = [f"🧠 <b>Cosa so su di te</b> ({len(self._facts)} fatti)\n"]
        categories = {}
        for f in self._facts:
            cat = f.get("category", "generale")
            categories.setdefault(cat, []).append(f["text"])

        icons = {
            "abitudini": "⏰", "preferenze": "❤️", "casa": "🏠",
            "persone": "👤", "energia": "⚡", "dispositivi": "🔌",
            "generale": "💡"
        }
        for cat, facts in categories.items():
            icon = icons.get(cat, "💡")
            lines.append(f"{icon} <b>{cat.capitalize()}</b>")
            for f in facts:
                lines.append(f"  • {f}")
            lines.append("")

        lines.append("<i>Usa /dimentica &lt;testo&gt; per rimuovere un fatto</i>")
        lines.append("<i>Usa /memoria reset per cancellare tutto</i>")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Scrittura

    def add_fact(self, text: str, category: str = "generale", source: str = "manual"):
        """Aggiunge un fatto manualmente."""
        text = text.strip()[:MAX_FACT_LEN]
        if not text:
            return
        # Evita duplicati simili
        for f in self._facts:
            if f["text"].lower() == text.lower():
                return
        self._facts.append({
            "text":     text,
            "category": category,
            "ts":       time.time(),
            "source":   source
        })
        # Mantieni solo gli ultimi MAX_FACTS
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

    async def extract_from_conversation(self, conversation: list[dict]):
        """
        Analizza una conversazione e estrae fatti utili da memorizzare.
        Chiamata alla fine di ogni sessione di chat.
        conversation: [{"role": "user"/"assistant", "content": "..."}]
        """
        if not self.ai or len(conversation) < 2:
            return

        # Costruisci testo conversazione
        conv_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:300]}"
            for m in conversation[-10:]  # ultimi 10 scambi
        )

        existing = "\n".join(f"- {f['text']}" for f in self._facts[-20:])

        prompt = (
            "Analizza questa conversazione con un sistema domotico e estrai fatti "
            "PERMANENTI e UTILI sull'utente da memorizzare per personalizzare le risposte future.\n\n"
            "CONVERSAZIONE:\n" + conv_text + "\n\n"
            "FATTI GIÀ MEMORIZZATI (non duplicare):\n" + (existing or "nessuno") + "\n\n"
            "REGOLE:\n"
            "- Estrai SOLO fatti duraturi (abitudini, preferenze, nomi, orari abituali)\n"
            "- NON estrarre stati temporanei (es. 'oggi ha acceso la luce')\n"
            "- NON duplicare fatti già memorizzati\n"
            "- Massimo 3 fatti nuovi per conversazione\n"
            "- Se non ci sono fatti utili, rispondi solo: NESSUNO\n\n"
            "Rispondi in formato JSON esatto:\n"
            "[{\"text\": \"fatto\", \"category\": \"abitudini|preferenze|casa|persone|energia|dispositivi|generale\"}]\n"
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
            import re
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if not match:
                return

            facts = json.loads(match.group())
            for f in facts:
                if isinstance(f, dict) and "text" in f:
                    self.add_fact(
                        f["text"],
                        category=f.get("category", "generale"),
                        source="ai_extract"
                    )
            if facts:
                logger.info("Memoria: estratti %d fatti dalla conversazione", len(facts))

        except Exception as e:
            logger.debug("Memoria extract error: %s", e)
