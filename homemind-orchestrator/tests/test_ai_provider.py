"""Catena di provider AI: dettaglio per provider quando falliscono tutti, ricarica senza riavvio."""
import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
for _n in ("openai", "anthropic", "aiohttp", "aiofiles"):          # ambiente di test senza queste librerie
    try:
        __import__(_n)
    except ImportError:
        _m = types.ModuleType(_n)
        _m.AsyncOpenAI = lambda **k: types.SimpleNamespace(**k)
        _m.AsyncAnthropic = lambda **k: types.SimpleNamespace(**k)
        _m.ClientTimeout = lambda **k: None
        _m.ClientSession = object
        sys.modules[_n] = _m

from agent import ai_provider as ap  # noqa: E402


def run(c):
    return asyncio.run(c)


class Fake:
    def __init__(self, display, err=None, reply="ciao", source=""):
        self.display, self.model, self.source, self.key_hint = display, "m", source, "abcd"
        self.err, self.reply = err, reply

    async def ask(self, *a, **k):
        if self.err:
            raise Exception(self.err)
        return self.reply


def chain(*providers):
    c = object.__new__(ap.AIProvider)
    c._providers = list(providers)
    return c


WRONG = "Error code: 401 - {'message': 'Wrong API Key', 'type': 'invalid_request_error'}"
RATE = "Error code: 429 - rate_limit_exceeded: Rate limit reached"


def test_tutti_falliti_dettaglio_per_provider():
    c = chain(Fake("Groq", RATE, source="dashboard"), Fake("Cerebras", WRONG, source="opzioni"))
    with pytest.raises(ap.AllProvidersFailed) as ei:
        run(c.ask("s", "u"))
    e = ei.value
    assert isinstance(e, RuntimeError) and str(e).startswith("Nessun provider AI disponibile")   # compatibile
    assert [f["name"] for f in e.failures] == ["Groq", "Cerebras"]
    assert "troppe richieste" in e.failures[0]["reason"]
    assert "chiave API rifiutata" in e.failures[1]["reason"] and e.failures[1]["source"] == "opzioni"
    txt = ap.describe_failures(e.failures)
    assert "Groq [dashboard]: troppe richieste" in txt and "Cerebras [opzioni]: chiave API rifiutata" in txt


def test_fallback_riuscito_non_solleva():
    c = chain(Fake("Groq", WRONG), Fake("Gemini", reply="ok"))
    assert run(c.ask("s", "u")) == "ok"


def test_reload_chain_sostituisce_stesso_oggetto():
    c = chain(Fake("Vecchio", WRONG))
    holder = c                                                    # chi tiene il riferimento vede il cambio
    n = c.reload_chain([{"name": "groq", "model": "x", "api_key": "gsk_nuovachiave1234"}], {"groq": "dashboard"})
    assert n == 1 and holder._providers[0].name == "groq"
    assert holder._providers[0].source == "dashboard" and holder._providers[0].key_hint == "1234"


def test_reload_chain_non_rompe_se_vuota_o_non_valida():
    c = chain(Fake("Buono", reply="ok"))
    assert c.reload_chain([]) == 0 and c.reload_chain([{"name": "inesistente", "api_key": "k"}]) == 0
    assert run(c.ask("s", "u")) == "ok"                           # catena precedente intatta


def test_key_hint_ignora_spazi_e_non_espone_la_chiave():
    p = ap._SingleProvider("groq", "", "  gsk_segretissima9876 \n")
    assert p.key_hint == "9876" and "segretissima" not in repr(p.key_hint)


def test_telegram_mostra_i_provider():
    from telegram_bot import TelegramBot
    e = ap.AllProvidersFailed("x", [{"name": "Cerebras", "source": "opzioni", "reason": "chiave API rifiutata (401)"}])
    out = TelegramBot._ai_failure_details(e)
    assert "Cerebras [opzioni]" in out and "chiave API rifiutata" in out and "Provider AI" in out
    assert "Errore:" in TelegramBot._ai_failure_details(RuntimeError("boom"))     # errori generici: come prima


def test_pagina_provider_ha_i_nuovi_messaggi():
    src = (Path(__file__).resolve().parents[1] / "src" / "main.py").read_text(encoding="utf-8")
    assert "Salvato e applicato subito" in src and "ALTRA chiave" in src and '"in_use"' in src and '"reloaded"' in src
