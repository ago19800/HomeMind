"""«Mandami la cartella X»: invia il contenuto di QUELLA cartella (anche create dopo) e riconosce «Mandami gas»."""
import asyncio, pathlib, sys
import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
pytest.importorskip("aiohttp")
import telegram_bot as T  # noqa: E402
from agent import file_search as fs, file_inbox as fi  # noqa: E402


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "Archivio"
    (root / "Bollette").mkdir(parents=True)
    (root / "Casa" / "Bollette").mkdir(parents=True)          # stesso nome, altro posto
    (root / "Foto vacanze").mkdir()
    for i in range(3):
        (root / "Bollette" / f"b{i}.pdf").write_bytes(b"%PDF-1.4 x")
    (root / "Casa" / "Bollette" / "gas.pdf").write_bytes(b"%PDF-1.4 x")
    for i in range(14):
        (root / "Foto vacanze" / f"img{i:02d}.jpg").write_bytes(b"\xff\xd8x")
    (root / "Foto vacanze" / "nota.txt").write_text("ciao")
    (root / "Foto vacanze" / ".nascosto.jpg").write_bytes(b"x")
    (root / "radice.pdf").write_bytes(b"%PDF")
    fs._DIR_CACHE.update(ts=0, key=None, dirs=[])
    return root


FOLDERS = lambda root: [{"path": str(root), "name": "Archivio"}]


def test_find_dirs_serve_il_segnale_esplicito(tree):
    f = FOLDERS(tree)
    assert fs.find_dirs("mandami bollette", f) == []                          # senza «cartella»: ricerca per parole
    assert [d["name"] for d in fs.find_dirs("mandami la cartella foto vacanze", f)] == ["Foto vacanze"]
    assert [d["name"] for d in fs.find_dirs("mandami il contenuto di foto vacanze", f)] == ["Foto vacanze"]
    assert [d["name"] for d in fs.find_dirs("mandami la cartella archivio", f)] == ["Archivio"]   # radice, per nome configurato


def test_stesso_nome_in_due_posti_prima_la_piu_vicina_alla_radice(tree):
    r = fs.find_dirs("cartella bollette", FOLDERS(tree))
    assert len(r) == 2 and r[0]["depth"] < r[1]["depth"]


def test_cartella_creata_dopo_si_trova(tree):
    f = FOLDERS(tree)
    assert fs.find_dirs("cartella nuova", f) == []
    (tree / "Nuova").mkdir(); (tree / "Nuova" / "a.pdf").write_bytes(b"%PDF")
    fs._DIR_CACHE["ts"] = 0                                                    # scade la cache (10 s)
    d = fs.find_dirs("mandami la cartella nuova", f)
    assert d and [r["name"] for r in fs.dir_rows(d[0]["path"], f)] == ["a.pdf"]


def test_dir_rows_solo_file_diretti_niente_nascosti_niente_fuori(tree):
    f = FOLDERS(tree)
    names = [r["name"] for r in fs.dir_rows(str(tree), f)]
    assert names == ["radice.pdf"]                                             # non entra nelle sottocartelle
    assert ".nascosto.jpg" not in [r["name"] for r in fs.dir_rows(str(tree / "Foto vacanze"), f)]
    assert fs.dir_rows("/etc", f) == [] and fs.dir_rows(str(tree) + "2", f) == []


def test_dir_request_solo_cartella_o_ricerca(tree):
    f = FOLDERS(tree); d = fs.find_dirs("cartella foto vacanze", f)
    assert fs.dir_request("mandami la cartella foto vacanze", f, d) == (True, None)
    assert fs.dir_request("mandami tutte le foto della cartella foto vacanze", f, d)[0] is True
    assert fs.dir_request("mandami le bollette di luglio dalla cartella foto vacanze", f, d)[0] is False
    assert fs.dir_request("mandami la fattura idraulico dalla cartella foto vacanze", f, d)[0] is False


# ── Telegram ────────────────────────────────────────────────────────────────
class Ix:
    index = None
    async def search(self, q, limit=8):
        return {"query": {"stems": [], "keywords": [], "all": False, "folders": [], "periods": []},
                "results": [], "partial": False, "multi": False, "groups": [], "missing": [], "stats": {"total": 0, "pdf_readable": 0}}


@pytest.fixture
def bot(monkeypatch, tree):
    b = T.TelegramBot.__new__(T.TelegramBot)
    b.sent, b.kbs, b.files = [], [], []
    async def _send(chat, text, *a, **k): b.sent.append(text)
    async def _kb(chat, text, kb, *a, **k): b.kbs.append((text, kb))
    async def _typing(chat): pass
    async def _one(chat, row, stems, folders, token, **k): b.files.append(row["name"])
    b._send, b._send_with_keyboard, b._typing, b._fs_send_one = _send, _kb, _typing, _one
    monkeypatch.setattr(fi, "load_settings", lambda: {"search": {"enabled": True}, "folders": FOLDERS(tree)})
    monkeypatch.setattr(fs, "get_indexer", lambda: Ix())
    async def _fast(*_a, **_k): return None
    monkeypatch.setattr(T.asyncio, "sleep", _fast)
    return b


def go(b, text):
    return asyncio.run(b._file_search_try("1", text, text.lower()))


def test_cartella_mostra_sempre_i_numeri_e_non_invia_nulla_da_sola(bot):
    assert go(bot, "Mandami la cartella casa") is True        # «casa» = unica, contiene la sottocartella Bollette
    assert bot.sent and "non contiene file" in bot.sent[0] and "Bollette" in bot.sent[0]
    bot.sent.clear()
    go(bot, "Mandami la cartella bollette")                    # due «bollette»: chiede quale
    text, kb = bot.kbs[-1]
    assert "2" in text and any("dir" in b["callback_data"] for b in kb["inline_keyboard"][0])
    token = next(iter(bot._fs_state()["pending"]))
    asyncio.run(bot._file_search_callback("1", 5, f"fs:{token}:dir:0"))
    assert bot.files == []                                      # NIENTE invio automatico, anche con 3 soli file
    text, kb = bot.kbs[-1]
    assert "3 file" in text and "1. " in text and "3. " in text and "b0.pdf" in text
    flat = [b for row in kb["inline_keyboard"] for b in row]
    assert [b["text"] for b in flat[:3]] == ["1", "2", "3"] and any(b["text"] == "📎 Invia tutti (3)" for b in flat)
    new_token = [k for k in bot._fs_state()["pending"] if k != token][-1]
    asyncio.run(bot._file_search_callback("1", 5, f"fs:{new_token}:1"))      # tocco il 2 → solo quello
    assert len(bot.files) == 1 and bot.files[0] in ("b0.pdf", "b1.pdf", "b2.pdf")
    asyncio.run(bot._file_search_callback("1", 5, f"fs:{new_token}:sendp:0"))  # «Invia tutti»
    assert len(bot.files) == 4


def test_cartella_grande_elenco_a_pagine_e_invio_pagina(bot):
    go(bot, "mandami la cartella foto vacanze")
    text, kb = bot.kbs[-1]
    assert "📁" in text and "Foto vacanze" in text and "15 file" in text and "Mostro 1–8 di 15" in text
    flat = [b for row in kb["inline_keyboard"] for b in row]
    assert any(b["text"] == "📎 Invia questi 8" for b in flat) and any("more:8" in b["callback_data"] for b in flat)
    assert bot.files == []                                      # prima di scegliere non invia nulla
    token = next(iter(bot._fs_state()["pending"]))
    asyncio.run(bot._file_search_callback("1", 5, f"fs:{token}:sendp:0"))
    assert len(bot.files) == 8
    asyncio.run(bot._file_search_callback("1", 5, f"fs:{token}:sendp:8"))
    assert len(bot.files) == 15 and len(set(bot.files)) == 15   # nessun doppione, tutti i 15 (14 foto + nota)


def test_solo_le_foto_della_cartella(bot):
    go(bot, "mandami tutte le foto della cartella foto vacanze")
    text, _ = bot.kbs[-1]
    assert "14 file" in text                                    # il .txt è escluso


def test_con_parole_in_piu_resta_la_ricerca(bot):
    go(bot, "mandami la fattura idraulico dalla cartella casa")
    assert not bot.files                                        # nessun invio a tappeto: ricerca normale (qui senza risultati)


# ── classificazione ─────────────────────────────────────────────────────────
def test_mandami_gas_e_una_richiesta_di_file_debole(bot):
    q, strong = bot._fs_classify("Mandami gas")
    assert q == "Mandami gas" and strong is None
    for frase in ["mandami un messaggio a Rosa", "mandami la temperatura", "accendi la luce", "ciao come stai"]:
        assert bot._fs_classify(frase)[0] is None, frase


def test_mandami_gas_senza_corrispondenza_piena_passa_all_ai(bot, monkeypatch):
    class IxP(Ix):
        async def search(self, q, limit=8):
            r = await super().search(q, limit)
            r["results"] = [{"path": "/x/a.pdf", "folder": "/x", "name": "a.pdf", "kind": "pdf", "date_ts": 1.7e9,
                             "size": 10, "score": 1, "matched": 1, "descr": "", "text": ""}]
            r["partial"] = True
            r["query"]["stems"] = ["ga"]
            return r
    monkeypatch.setattr(fs, "get_indexer", lambda: IxP())
    assert go(bot, "Mandami gas") is False                      # solo risultati «simili»: non intercetta, risponde l'AI
    assert not bot.kbs
