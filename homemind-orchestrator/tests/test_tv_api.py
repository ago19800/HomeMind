"""Test d'integrazione TV sull'app FastAPI vera (scrive in /config/homemind_patches: salva e ripristina)."""
import asyncio, json, pathlib, sys
import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
pytest.importorskip("fastapi")
import tv as V  # noqa: E402
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

CFG = pathlib.Path("/config/homemind_patches/person_config.json")
ENT = "media_player.tv_lg"


class Rest:
    """HA finto con una TV che cambia davvero volume (HomeMind verifica che il livello si sia mosso)."""
    def __init__(self): self.calls = []
    async def call_service(self, d, s, data=None, target=None):
        self.calls.append((d, s, data))
        if s == "volume_set" and data["entity_id"] in main.state_cache:
            main.state_cache[data["entity_id"]]["attributes"]["volume_level"] = data["volume_level"]
        return []


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "canali_path", lambda: tmp_path / "canali.json")
    monkeypatch.setattr(V, "DATA_COPY_PATH", tmp_path / "copy.json")
    backup = CFG.read_bytes() if CFG.exists() else None
    CFG.parent.mkdir(parents=True, exist_ok=True)
    CFG.write_text(json.dumps({"altra": {"x": 1}, "dieta": {"alexa_enabled": True}}), encoding="utf-8")
    main.state_cache[ENT] = {"state": "on", "attributes": {"friendly_name": "TV LG", "volume_level": 0.3, "source_list": ["Netflix", "HDMI 1"]}}
    main.state_cache["media_player.echo_cucina"] = {"state": "idle", "attributes": {"friendly_name": "Echo Cucina"}}
    rest = Rest()
    main.tv = V.TvManager(rest, lambda e: main.state_cache.get(e), None, {})
    main.tv.rest = rest
    yield TestClient(main.app), rest
    main.tv = None
    main.state_cache.pop(ENT, None); main.state_cache.pop("media_player.echo_cucina", None)
    CFG.unlink(missing_ok=True) if backup is None else CFG.write_bytes(backup)


def test_settings_persistono_e_non_toccano_le_altre_chiavi(env):
    c, _ = env
    body = {"entity": ENT, "mac": "AA:BB:CC:DD:EE:FF", "alexa_enabled": True, "telegram_enabled": True, "confirm_voice": True,
            "speakers": ["media_player.echo_cucina", "light.no", 3], "volume": 9, "step": 99}
    assert c.post("/api/tv/settings", json=body).json()["ok"]
    saved = json.loads(CFG.read_text(encoding="utf-8"))
    assert saved["tv"]["entity"] == ENT and saved["tv"]["speakers"] == ["media_player.echo_cucina"]
    assert saved["tv"]["volume"] == 1.0 and saved["tv"]["step"] == 30
    assert saved["altra"] == {"x": 1} and saved["dieta"] == {"alexa_enabled": True}        # il resto intatto
    assert main.tv.entity == ENT and main.tv.alexa_enabled and main.tv.mac == "AA:BB:CC:DD:EE:FF"


def test_entita_non_valida_viene_scartata(env):
    c, _ = env
    c.post("/api/tv/settings", json={"entity": "light.salotto"})
    assert json.loads(CFG.read_text())["tv"]["entity"] == "" and main.tv.entity == ""


def test_file_illeggibile_non_viene_riscritto(env):
    CFG.write_text("{non json", encoding="utf-8")
    r = env[0].post("/api/tv/settings", json={"entity": ENT})
    assert r.status_code == 500 and CFG.read_text() == "{non json"


def test_salva_generale_non_cancella_tv_ne_dieta(env):
    c, _ = env
    c.post("/api/tv/settings", json={"entity": ENT, "alexa_enabled": True})
    assert c.post("/api/config", json={"persone": {}}).status_code == 200
    saved = json.loads(CFG.read_text(encoding="utf-8"))
    assert saved["tv"]["entity"] == ENT and saved["tv"]["alexa_enabled"] is True


def test_canali_upload_state_example(env):
    c, _ = env
    r = c.post("/api/tv/channels", json={"json": json.dumps({"Rai 1": "501", "Canale 5": "505"})}).json()
    assert r["ok"] and len(r["state"]["channels"]) == 2
    bad = c.post("/api/tv/channels", json={"json": "{rotto"})
    assert bad.status_code == 400 and len(c.get("/api/tv/state").json()["channels"]) == 2     # i canali restano
    assert c.post("/api/tv/channels", json={"json": ""}).status_code == 400
    assert json.loads(c.get("/api/tv/example").text)["canali"]


def test_ask_esegue_sulla_tv_e_state_la_descrive(env):
    c, rest = env
    c.post("/api/tv/settings", json={"entity": ENT})
    r = c.post("/api/tv/ask", json={"text": "alza il volume", "test": True}).json()           # force: niente «tv» richiesto
    assert r["matched"] and r["executed"] and rest.calls[-1][2]["volume_level"] == 0.35
    r = c.post("/api/tv/ask", json={"text": "metti netflix"}).json()
    assert rest.calls[-1][1] == "select_source" and rest.calls[-1][2]["source"] == "Netflix"
    st = c.get("/api/tv/state").json()
    assert st["tv_state"] == "on" and st["tv_volume"] == 35 and "Netflix" in st["sources"]
    assert c.post("/api/tv/ask", json={"text": "ciao"}).json()["matched"] is False
    assert c.post("/api/tv/ask", content=b"x").status_code == 500


def test_pagina_impostazioni_tab_tv(env):
    class U: path = "/settings"
    class R: url = U(); headers = {}; query_params = {}
    h = asyncio.run(main.settings_page(R())).body.decode()
    assert 'data-tab="tv"' in h and 'id="tc-tv"' in h and "tvLoad" in h and 'data-tab="dt"' in h      # la dieta c'è ancora
    tab = h[h.index('id="tc-tv"'):]
    assert "TV LG" in tab and tab.find("TV LG") < tab.find("Echo Cucina")                              # le TV prima degli speaker
    assert 'name="tv_sp"' in h and "{tv_" not in h and "__ENTITIES__" not in h


def test_telegram_flusso_completo(env):
    c, rest = env
    c.post("/api/tv/settings", json={"entity": ENT})
    import telegram_bot as T
    sent = []
    bot = T.TelegramBot.__new__(T.TelegramBot)
    bot.tv_cb = lambda: main.tv
    async def run():
        r = await bot.tv_cb().telegram_text("/tv canale 35")
        sent.append(r)
    asyncio.run(run())
    assert "35" in sent[0] and rest.calls[-1][1] == "play_media"


def test_marca_e_telecomando_persistono_e_vengono_validati(env):
    c, _ = env
    assert c.post("/api/tv/settings", json={"entity": ENT, "brand": "Samsung", "remote_entity": "remote.samsung_tv"}).json()["ok"]
    saved = json.loads(CFG.read_text(encoding="utf-8"))["tv"]
    assert saved["brand"] == "samsung" and saved["remote_entity"] == "remote.samsung_tv"
    assert main.tv.brand == "samsung" and main.tv.remote_entity == "remote.samsung_tv"
    c.post("/api/tv/settings", json={"entity": ENT, "brand": "boh", "remote_entity": "light.x"})
    saved = json.loads(CFG.read_text(encoding="utf-8"))["tv"]
    assert saved["brand"] == "auto" and saved["remote_entity"] == "" and main.tv.brand == "auto"
    c.post("/api/tv/settings", json={"entity": ENT})                                     # vecchio client senza i due campi
    assert json.loads(CFG.read_text(encoding="utf-8"))["tv"]["brand"] == "auto"
    st = c.get("/api/tv/state").json()
    assert st["brand"] == "auto" and st["brand_detected"] == "lg"                         # «tv_lg» → riconosciuta


def test_vecchia_config_senza_marca_funziona_come_prima(env):
    """person_config.json di versioni precedenti: nessun campo brand/remote_entity."""
    _, rest = env
    main.tv.apply_settings({"entity": ENT, "alexa_enabled": True, "step": 5})
    assert main.tv.brand == "auto" and main.tv.remote_entity == ""
    ok, _ = asyncio.run(main.tv.execute({"action": "vol_rel", "delta": 5}))
    assert ok and rest.calls[-1][2]["volume_level"] == 0.35


def test_pagina_impostazioni_elenco_tv_senza_speaker(env):
    class U: path = "/settings"
    class R: url = U(); headers = {}; query_params = {}
    h = asyncio.run(main.settings_page(R())).body.decode()
    sel = h[h.index('id="tv_entity"'):h.index("</select>", h.index('id="tv_entity"'))]
    assert "media_player.tv_lg" in sel and "echo_cucina" not in sel                      # solo TV nel menu a tendina
    assert 'id="tv_brand"' in h and 'id="tv_remote"' in h and 'id="tv_all_json"' in h
    assert "media_player.echo_cucina" in h[h.index('id="tv_all_json"'):h.index("</script>", h.index('id="tv_all_json"'))]
