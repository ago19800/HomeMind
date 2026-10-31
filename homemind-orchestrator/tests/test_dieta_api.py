"""Test d'integrazione (app FastAPI vera). Scrive in /config/homemind_patches: salva e ripristina i file."""
import asyncio, json, pathlib, sys
import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
pytest.importorskip("fastapi")
import dieta as D  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CFG = pathlib.Path("/config/homemind_patches/person_config.json")
EXAMPLE = (SRC / "dieta_esempio.json").read_text(encoding="utf-8")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "dieta_path", lambda: tmp_path / "dieta.json")
    monkeypatch.setattr(D, "DATA_COPY_PATH", tmp_path / "copy.json")
    backup = CFG.read_bytes() if CFG.exists() else None
    CFG.parent.mkdir(parents=True, exist_ok=True)
    CFG.write_text(json.dumps({"altra_chiave": {"x": 1}, "spazzatura": {"enabled": True}}), encoding="utf-8")
    main.dieta = D.DietaManager()
    yield TestClient(main.app)
    main.dieta = None
    if backup is None:
        CFG.unlink(missing_ok=True)
    else:
        CFG.write_bytes(backup)


def test_upload_state_example(env):
    c = env
    assert c.get("/api/dieta/state").json()["loaded"] is False
    assert c.post("/api/dieta/upload", json={"json": ""}).status_code == 400
    r = c.post("/api/dieta/upload", json={"json": "{rotto"})
    assert r.status_code == 400 and "JSON non valido" in r.json()["error"]
    r = c.post("/api/dieta/upload", json={"json": EXAMPLE}).json()
    assert r["ok"] and r["state"]["persona"] == "Rosa"
    c.post("/api/dieta/upload", json={"json": "{rotto"})                 # non cancella il piano
    assert c.get("/api/dieta/state").json()["loaded"] is True
    ex = c.get("/api/dieta/example")
    assert ex.status_code == 200 and json.loads(ex.text)["giorni"]
    assert c.post("/api/dieta/reload").json()["ok"] is True


def test_settings_persistono_senza_toccare_il_resto(env):
    c = env
    body = {"alexa_enabled": True, "telegram_enabled": True,
            "speakers": ["media_player.echo", "light.non_uno_speaker", 5], "volume": 7}
    assert c.post("/api/dieta/settings", json=body).json()["ok"]
    saved = json.loads(CFG.read_text(encoding="utf-8"))
    assert saved["dieta"] == {"alexa_enabled": True, "telegram_enabled": True,
                              "speakers": ["media_player.echo"], "volume": 1.0}     # filtrati e limitati
    assert saved["altra_chiave"] == {"x": 1} and saved["spazzatura"] == {"enabled": True}
    assert main.dieta.alexa_enabled and main.dieta.alexa_speakers == ["media_player.echo"]


def test_settings_rifiuta_di_riscrivere_un_file_illeggibile(env):
    CFG.write_text("{non json", encoding="utf-8")
    r = env.post("/api/dieta/settings", json={"alexa_enabled": True})
    assert r.status_code == 500 and CFG.read_text() == "{non json"


def test_salva_generale_non_cancella_la_dieta(env):
    c = env
    c.post("/api/dieta/settings", json={"alexa_enabled": True, "telegram_enabled": True,
                                        "speakers": ["media_player.echo"], "volume": 0.4})
    r = c.post("/api/config", json={"persone": {}})        # salvataggio dalla pagina, senza chiave "dieta"
    assert r.status_code == 200, r.text
    assert json.loads(CFG.read_text(encoding="utf-8"))["dieta"]["speakers"] == ["media_player.echo"]


def test_ask_endpoint(env):
    c = env
    c.post("/api/dieta/upload", json={"json": EXAMPLE})
    r = c.post("/api/dieta/ask", json={"text": "cosa ho per cena domani"}).json()
    assert r["matched"] and "cena di domani" in r["speech"] and "grammi" in r["speech"]
    assert c.post("/api/dieta/ask", json={"text": "ciao"}).json()["matched"] is False
    assert c.post("/api/dieta/ask", content=b"non json").status_code == 500


def test_pagina_impostazioni_ha_la_tab(env):
    class U: path = "/settings"
    class R: url = U(); headers = {}; query_params = {}
    main.state_cache["media_player.echo_t"] = {"state": "idle", "attributes": {"friendly_name": "Echo T"}}
    h = asyncio.run(main.settings_page(R())).body.decode()
    assert 'data-tab="dt"' in h and 'id="tc-dt"' in h and "dtLoad" in h and "Echo T" in h
    assert "{dieta_" not in h and "__SPEAKERS__" not in h


def test_telegram_quick_command_end_to_end(env):
    import telegram_bot as T
    c = env
    c.post("/api/dieta/upload", json={"json": EXAMPLE})
    bot = T.TelegramBot.__new__(T.TelegramBot)               # senza avviare rete
    bot.dieta_cb = lambda: main.dieta
    q = bot._quick_command
    # le altre funzioni di _quick_command possono richiedere attributi: ci interessano solo le frasi dieta
    for frase, atteso in [("Colazione", "Colazione"), ("/dieta cena", "Cena"), ("Spuntino oggi", "Quale spuntino")]:
        assert atteso in q(frase), frase
    assert "Spuntino pomeridiano" in q("pomeriggio")
