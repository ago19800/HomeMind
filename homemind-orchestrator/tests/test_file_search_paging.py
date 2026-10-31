"""La ricerca file mostra il totale reale e si sfoglia a pagine (prima: tetto fisso a 8)."""
import asyncio, pathlib, sys
import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
pytest.importorskip("aiohttp")
import telegram_bot as T  # noqa: E402
from agent import file_search as fs, file_inbox as fi  # noqa: E402


def rows(n):
    return [{"path": f"/docs/Doc_{i}.pdf", "folder": "/docs", "name": f"Doc_{i}.pdf", "kind": "pdf",
             "date_ts": 1.7e9, "size": 1000 + i, "score": 5 - i * 0.01, "matched": 1, "descr": "", "text": ""}
            for i in range(n)]


class FakeIx:
    def __init__(self, n, multi=False): self.n, self.multi, self.limits = n, multi, []
    async def search(self, q, limit=8):
        self.limits.append(limit)
        r = rows(self.n)[:limit]
        return {"query": {"stems": ["document"], "keywords": ["documenti"], "all": False, "folders": [], "periods": []},
                "results": r, "partial": False, "multi": self.multi, "groups": [], "missing": [],
                "stats": {"total": self.n, "pdf_readable": self.n}}


@pytest.fixture
def bot(monkeypatch):
    b = T.TelegramBot.__new__(T.TelegramBot)
    b.sent, b.kbs = [], []
    async def _send(chat, text, *a, **k): b.sent.append(text)
    async def _kb(chat, text, kb, *a, **k): b.kbs.append((text, kb))
    async def _typing(chat): pass
    b._send, b._send_with_keyboard, b._typing = _send, _kb, _typing
    monkeypatch.setattr(fi, "load_settings", lambda: {"search": {"enabled": True}, "folders": [{"path": "/docs", "name": "Documenti"}]})
    return b


def use(monkeypatch, ix):
    monkeypatch.setattr(fs, "get_indexer", lambda: ix)


def test_mostra_il_totale_reale_e_il_bottone_altri(bot, monkeypatch):
    ix = FakeIx(23); use(monkeypatch, ix)
    assert asyncio.run(bot._file_search_try("1", "/file documenti", "/file documenti"))
    text, kb = bot.kbs[0]
    assert "23 file trovati" in text and "Mostro 1–8 di 23" in text and "Doc_7.pdf" in text and "Doc_8.pdf" not in text
    flat = [b for row in kb["inline_keyboard"] for b in row]
    assert any(b["text"] == "➕ Altri 8" and b["callback_data"].endswith(":more:8") for b in flat)
    assert any(b["text"] == "📎 Primi 10" for b in flat)            # non promette 23 se ne manda 10
    assert ix.limits[0] > 8


def test_pagina_successiva_e_ultima(bot, monkeypatch):
    use(monkeypatch, FakeIx(23))
    asyncio.run(bot._file_search_try("1", "/file documenti", "/file documenti"))
    token = bot._fs_state()["pending"].popitem()[0] if False else next(iter(bot._fs_state()["pending"]))
    asyncio.run(bot._file_search_callback("1", 5, f"fs:{token}:more:8"))
    t2, kb2 = bot.kbs[-1]
    assert "Mostro 9–16 di 23" in t2 and "9. " in t2 and "Doc_8.pdf" in t2
    asyncio.run(bot._file_search_callback("1", 5, f"fs:{token}:more:16"))
    t3, kb3 = bot.kbs[-1]
    assert "Mostro 17–23 di 23" in t3
    assert not any("more" in b["callback_data"] for row in kb3["inline_keyboard"] for b in row)   # niente "Altri" in fondo
    # il numero 20 apre il file giusto (indice assoluto)
    sent = []
    async def fake_send_one(chat, row, *a, **k): sent.append(row["name"])
    bot._fs_send_one = fake_send_one
    asyncio.run(bot._file_search_callback("1", 5, f"fs:{token}:19"))
    assert sent == ["Doc_19.pdf"]
    asyncio.run(bot._file_search_callback("1", 5, f"fs:{token}:more:xx"))      # input sporco: ignorato


def test_pochi_risultati_comportamento_invariato(bot, monkeypatch):
    use(monkeypatch, FakeIx(5))
    asyncio.run(bot._file_search_try("1", "/file documenti", "/file documenti"))
    text, kb = bot.kbs[0]
    assert "5 file trovati" in text and "Mostro" not in text
    flat = [b["text"] for row in kb["inline_keyboard"] for b in row]
    assert "📎 Tutti (5)" in flat and not any("Altri" in t for t in flat)


def test_piu_mesi_resta_limite_di_sempre(bot, monkeypatch):
    ix = FakeIx(30, multi=True); use(monkeypatch, ix)
    async def multi(*a, **k): return True
    bot._fs_multi_reply = multi
    asyncio.run(bot._file_search_try("1", "/file bolletta dicembre e gennaio", "/file bolletta dicembre e gennaio"))
    assert ix.limits == [T.TelegramBot.FS_FETCH, 8]


def test_richiesta_scaduta(bot):
    asyncio.run(bot._file_search_callback("1", 5, "fs:zzzz:more:8"))
    assert "scaduta" in bot.sent[-1]


# ── Titolo leggibile ricavato dal contenuto ─────────────────────────────────
@pytest.mark.parametrize("testo,atteso", [
    ("FOGLION. DATI IDENTIFICATIVI AZIENDALI % PART TIME POSIZIONE INAIL POSIZIONE INPS MESE DI RETRIBUZIONE LUGLIO 2026 netto", "Busta paga · Luglio 2026"),
    ("FOGLION. DATI IDENTIFICATIVI AZIENDALI POSIZIONE INPS MESE DI RETRIBUZIONE DICEMBRE 2025 TREDICESIMA MENSILITÀ netto", "Busta paga · Dicembre 2025 (tredicesima)"),
    ("STELLANTISEUROPE SPA N3 1 00 01 000117 REDDITI 2025 06 00377207 Certificazione Unica sostituto d'imposta", "Certificazione Unica · redditi 2025"),
    ("Data: 05/07/2026 Ora: 19.40.19 pag: 1 Segue Visura attuale sintetica per soggetto Catasto fabbricati", "Visura catastale · 05/07/2026"),
    ("Codice Fiscale N° Cliente GAS RSSGTN80L17F839E 111897599 Enel Energia - Mercato Libero del gas dal 01/08/2026 al 30/09/2026", "Bolletta Enel gas · dal 01/08/2026 al 30/09/2026"),
    ("Codice Fiscale N° Cliente RSSGTN80L17F839E 125798093 ENERGIA ELETTRICA Enel Energia - Mercato Libero scadenza: 15/10/2026", "Bolletta Enel luce · scad. 15/10/2026"),
    ("ECOCALENDARIO 2026 LANCIANO ERAIZNEREFFID ORGANICO Scarti di provenienza", ""),     # non riconosciuto: resta l'anteprima
    ("ciao", ""), ("", ""),
])
def test_doc_label(testo, atteso):
    assert fs.doc_label({"text": testo}) == atteso


def test_doc_label_non_esplode_con_dati_sporchi():
    assert fs.doc_label({"text": None}) == "" and fs.doc_label({}) == ""


def test_elenco_usa_il_titolo_e_poi_l_anteprima(bot, monkeypatch):
    class Ix(FakeIx):
        async def search(self, q, limit=8):
            r = await super().search(q, limit)
            r["results"][0]["text"] = "FOGLION. DATI IDENTIFICATIVI AZIENDALI POSIZIONE INPS MESE DI RETRIBUZIONE LUGLIO 2026 netto"
            r["results"][1]["text"] = "ECOCALENDARIO 2026 LANCIANO scarti di provenienza organico raccolta"
            return r
    use(monkeypatch, Ix(12))
    asyncio.run(bot._file_search_try("1", "/file documenti", "/file documenti"))
    text, _ = bot.kbs[0]
    assert "🏷️ <b>Busta paga · Luglio 2026</b>" in text          # titolo sotto il nome del file
    assert "ECOCALENDARIO 2026" in text                           # non riconosciuto: anteprima come prima
