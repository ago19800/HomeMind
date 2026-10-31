"""Test del controllo TV (LG webOS via Home Assistant)."""
import asyncio, json, pathlib, sys
import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import tv as V  # noqa: E402

ENT = "media_player.tv_lg"
CH = {"canali": [{"nome": "Rai 1", "numero": "501", "alias": ["rai uno"]}, {"nome": "Canale 5", "numero": "505"},
                 {"nome": "La7", "numero": "507"}]}


class Rest:
    """HA finto. Con `st` simula una TV vera: volume_set cambia davvero il livello (salvo `stuck`, come una TV
    con uscita audio esterna/ARC che accetta il comando ma non cambia volume)."""
    def __init__(self, fail=(), st=None, stuck=False):
        self.calls, self.fail, self.st, self.stuck = [], set(fail), st, stuck
    async def call_service(self, domain, service, data=None, target=None):
        self.calls.append((domain, service, dict(data or {})))
        if (domain, service) in self.fail:
            raise RuntimeError("boom")
        if service == "volume_set" and self.st is not None and not self.stuck:
            self.st[data["entity_id"]]["attributes"]["volume_level"] = data["volume_level"]
        return []


class Notif:
    def __init__(self): self.sent = []
    async def send_html(self, m, force=False): self.sent.append(m)


@pytest.fixture
def make(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "canali_path", lambda: tmp_path / "canali.json")
    monkeypatch.setattr(V, "DATA_COPY_PATH", tmp_path / "copy.json")
    monkeypatch.setattr(V.asyncio, "sleep", lambda *_a, **_k: asyncio.sleep(0) if False else _noop())
    def build(state="on", attrs=None, fail=(), stuck=False, **settings):
        st = {ENT: {"state": state, "attributes": {"volume_level": 0.2, "source_list": ["Netflix", "YouTube", "HDMI 1", "HDMI 2", "Prime Video"], **(attrs or {})}}}
        rest = Rest(fail, st, stuck)
        m = V.TvManager(rest, lambda e: st.get(e), Notif(), {"entity": ENT, **settings})
        m.set_channels_from_json_text(json.dumps(CH))
        m._st_ref, m.rest = st, rest
        return m
    return build


async def _noop(): return None


@pytest.mark.parametrize("frase,azione", [
    ("accendi la tv", "on"), ("spegni la televisione", "off"), ("spegni la tele", "off"),
    ("alza il volume della tv", "vol_rel"), ("abbassa il volume della tv di 10", "vol_rel"),
    ("metti il volume della tv a 30", "vol_set"), ("volume della tv 15", "vol_set"),
    ("metti la tv muto", "mute"), ("riattiva l'audio della tv", "unmute"),
    ("metti canale 35", "channel"), ("cambia canale", "channel_up"), ("canale successivo", "channel_up"),
    ("canale precedente", "channel_down"), ("metti rai uno", "channel"), ("vai su La7", "channel"),
    ("metti canale 5", "channel"),
    ("metti netflix sulla tv", "source"), ("apri youtube sulla tv", "source"), ("metti hdmi 2", "source"),
    ("metti in pausa la tv", "pause"), ("riprendi la tv", "play"),
])
def test_parse_azioni(make, frase, azione):
    assert make().parse(frase)["action"] == azione, frase


@pytest.mark.parametrize("frase", [
    "alza il volume", "abbassa il volume", "spegni", "accendi la luce del salotto", "metti la musica",
    "metti la radio rai 1", "spegni la luce della tv", "che ore sono", "metti la sveglia alle 7",
    "metti netflix", "cosa ho per cena", "ciao",
])
def test_parse_non_deve_scattare(make, frase):
    assert make().parse(frase) is None, frase


def test_nome_canale_ha_la_precedenza_sul_numero(make):
    c = make().parse("metti canale 5")
    assert c["numero"] == "505" and c["label"] == "Canale 5"          # «Canale 5» è un nome nella mappa
    assert make().parse("metti canale 35")["numero"] == "35"
    m = make(); m.channels = []
    assert m.parse("metti canale 5")["numero"] == "5"                  # senza mappa: numero


def test_force_non_richiede_tv(make):
    m = make()
    assert m.parse("volume 30", force=True)["level"] == 30
    assert m.parse("35", force=True)["numero"] == "35"
    assert m.parse("netflix", force=True)["source"] == "Netflix"
    assert m.parse("volume 30") is None


def run(c): return asyncio.run(c)


def test_canale_chiamata_diretta_poi_tasti(make):
    m = make()
    ok, msg = run(m.execute(m.parse("metti canale 35")))
    assert ok and m.rest.calls == [("media_player", "play_media", {"entity_id": ENT, "media_content_type": "channel", "media_content_id": "35"})]
    m = make(fail=[("media_player", "play_media")])                   # la TV non trova il canale → tasti
    ok, _ = run(m.execute(m.parse("metti canale 35")))
    btn = [c[2]["button"] for c in m.rest.calls if c[:2] == ("webostv", "button")]
    assert ok and btn == ["3", "5", "ENTER"]
    m = make(fail=[("media_player", "play_media"), ("webostv", "button")])
    assert run(m.execute(m.parse("metti canale 35")))[0] is False


def test_volume_relativo_assoluto_e_senza_livello(make):
    m = make()                                                       # volume attuale 20%
    run(m.execute(m.parse("alza il volume della tv")))
    assert m.rest.calls[-1][2]["volume_level"] == 0.25
    run(m.execute(m.parse("abbassa il volume della tv di 10")))
    assert m.rest.calls[-1][2]["volume_level"] == 0.15                # 20 → 25 (alza) → 15 (abbassa di 10)
    run(m.execute(m.parse("metti il volume della tv a 30")))
    assert m.rest.calls[-1][2]["volume_level"] == 0.3
    m = make(attrs={"volume_level": None})                          # TV che non espone il livello (LG)
    run(m.execute(m.parse("alza il volume della tv")))
    assert [(c[0], c[1], c[2]["button"]) for c in m.rest.calls] == [("webostv", "button", "VOLUMEUP")] * 5
    m = make(attrs={"volume_level": None}, fail=[("webostv", "button")])   # tasti non disponibili → servizi media_player
    run(m.execute(m.parse("alza il volume della tv")))
    assert [c[1] for c in m.rest.calls if c[0] == "media_player"] == ["volume_up"] * 5
    m = make(attrs={"volume_level": 0.98}); run(m.execute({"action": "vol_rel", "delta": 10}))
    assert m.rest.calls[-1][2]["volume_level"] == 1.0                # non supera 100


def test_muto_sorgente_pausa_canali_su_giu(make):
    m = make()
    run(m.execute(m.parse("metti la tv muto"))); assert m.rest.calls[-1][2]["is_volume_muted"] is True
    run(m.execute(m.parse("riattiva l'audio della tv"))); assert m.rest.calls[-1][2]["is_volume_muted"] is False
    run(m.execute(m.parse("metti netflix sulla tv"))); assert m.rest.calls[-1] == ("media_player", "select_source", {"entity_id": ENT, "source": "Netflix"})
    run(m.execute(m.parse("metti hdmi 2"))); assert m.rest.calls[-1][2]["source"] == "HDMI 2"
    run(m.execute(m.parse("canale successivo"))); assert m.rest.calls[-1][1] == "media_next_track"
    run(m.execute(m.parse("canale precedente"))); assert m.rest.calls[-1][1] == "media_previous_track"
    run(m.execute(m.parse("metti in pausa la tv"))); assert m.rest.calls[-1][1] == "media_pause"


def test_tv_spenta(make):
    m = make(state="off")
    ok, msg = run(m.execute(m.parse("alza il volume della tv")))
    assert not ok and "spenta" in msg and m.rest.calls == []          # senza MAC non accende da sola per il volume
    ok, msg = run(m.execute(m.parse("spegni la tv")))
    assert ok and "già spenta" in msg and m.rest.calls == []
    ok, _ = run(m.execute({"action": "on"}))                          # nessuno stato che cambia → timeout
    assert ok is False and m.rest.calls[0][:2] == ("media_player", "turn_on")


def test_unavailable_messaggio_chiaro_senza_attese(make):
    m = make(state="unavailable")                                     # TV spenta/non raggiungibile in HA, nessun MAC
    for frase in ("metti canale 35", "alza il volume della tv", "accendi la tv", "metti netflix sulla tv"):
        ok, msg = run(m.execute(m.parse(frase)))
        assert not ok and "unavailable" in msg and "MAC" in msg, frase
    assert m.rest.calls == []                                         # nessuna chiamata inutile, nessuna attesa di 25 s


def test_unavailable_con_mac_prova_ad_accendere(make):
    m = make(state="unavailable", mac="AA:BB:CC:DD:EE:FF")
    orig = m.rest.call_service
    async def waking(domain, service, data=None, target=None):
        r = await orig(domain, service, data, target)
        if domain == "wake_on_lan":
            m._st_ref[ENT]["state"] = "on"
        return r
    m.rest.call_service = waking
    assert run(m.execute(m.parse("metti canale 35")))[0] is True
    assert m.rest.calls[0][:2] == ("wake_on_lan", "send_magic_packet")


def test_accensione_con_mac_e_attesa(make):
    m = make(state="off", mac="AA:BB:CC:DD:EE:FF", broadcast_address="192.168.1.255")
    orig = m.rest.call_service
    async def waking(domain, service, data=None, target=None):
        r = await orig(domain, service, data, target)
        if domain == "wake_on_lan":
            m._st_ref[ENT]["state"] = "on"                              # la TV si accende dopo il pacchetto
        return r
    m.rest.call_service = waking
    ok, _ = run(m.execute(m.parse("metti canale 35")))
    assert ok
    assert m.rest.calls[0] == ("wake_on_lan", "send_magic_packet", {"mac": "AA:BB:CC:DD:EE:FF", "broadcast_address": "192.168.1.255"})
    assert m.rest.calls[-1][1] == "play_media"                         # poi cambia canale


def test_wake_on_lan_non_disponibile_ripiega_su_turn_on(make):
    m = make(state="off", mac="AA:BB:CC:DD:EE:FF", fail=[("wake_on_lan", "send_magic_packet")])
    run(m.execute({"action": "on"}))
    assert [c[:2] for c in m.rest.calls[:2]] == [("wake_on_lan", "send_magic_packet"), ("media_player", "turn_on")]


def test_non_configurata_o_senza_ha(make):
    m = make(); m.entity = ""
    assert run(m.execute({"action": "on"}))[1].startswith("TV non configurata")
    m = make(); m.rest = None
    assert "non raggiungibile" in run(m.execute({"action": "on"}))[1]


def test_canali_file(make, tmp_path):
    m = make()
    assert len(m.channels) == 3 and not m.channel_warnings
    m.set_channels_from_json_text(json.dumps({"Rai 1": "501", "Rai 2": "x", "Rai 1 ": "1"}))
    assert [c["nome"] for c in m.channels] == ["Rai 1"] and len(m.channel_warnings) == 2
    for bad in ["{rotto", "[]", '{"canali":[{"nome":"A","numero":"x"}]}', "x" * 300_000]:
        with pytest.raises(ValueError):
            m.set_channels_from_json_text(bad)
    assert [c["nome"] for c in m.channels] == ["Rai 1"]               # file non valido: resta il precedente
    n = V.TvManager(); assert "1 canali" in n.load_channels()


def test_telegram(make):
    m = make()
    assert "Volume 25%" in run(m.telegram_text("/tv alza il volume"))
    assert "Canale 5" in run(m.telegram_text("/tv canale 5"))
    assert "Canale 35" in run(m.telegram_text("/tv 35")) or "canale 35" in run(m.telegram_text("/tv 35")).lower()
    assert "Esempi" in run(m.telegram_text("/tv"))
    assert "Non ho capito" in run(m.telegram_text("/tv blabla"))
    assert run(m.telegram_text("metti canale 12")) is not None
    assert run(m.telegram_text("ciao come stai")) is None             # va all'AI
    assert run(m.telegram_text("alza il volume")) is None
    m.entity = ""
    assert "non configurata" in run(m.telegram_text("/tv"))
    assert run(m.telegram_text("metti canale 12")) is None


def test_voce_alexa_switch_telegram_e_conferma(make):
    m = make(alexa_enabled=True, telegram_enabled=True)
    async def go():
        ev = {"state": "x", "attributes": {"last_called_summary": "Metti canale 35"}}
        m.on_state_changed("media_player.echo", ev)
        m.on_state_changed("sensor.altro", ev)                         # doppione
        m.on_state_changed("sensor.x", {"state": "x", "attributes": {"last_called_summary": "ciao"}})
        await asyncio.sleep(0.05)
    run(go())
    assert [c[1] for c in m.rest.calls] == ["play_media"] and len(m.notifier.sent) == 1
    m2 = make(alexa_enabled=False)
    async def go2():
        m2.on_state_changed("a", {"attributes": {"last_called_summary": "metti canale 35"}})
        await asyncio.sleep(0.05)
    run(go2()); assert m2.rest.calls == []                           # switch spento: ignora
    m3 = make(confirm_voice=True, speakers=["media_player.echo"])
    res = run(m3.ask("metti canale 35", source="test"))
    assert res["executed"] and any(c[0] == "notify" for c in m3.rest.calls)


def test_settings_sporchi(make):
    m = V.TvManager(settings={"entity": "light.x", "volume": "boh", "step": 999, "speakers": "no"})
    assert m.entity == "" and m.volume == 0.5 and m.step == 30 and m.speakers == []


def test_voce_alexa_stessa_frase_non_si_riesegue(make):
    """L'Echo rimanda lo stesso last_called_summary a ogni cambio di stato: si agisce una volta sola."""
    import time
    m = make(alexa_enabled=True)
    ts = int(time.time() * 1000)
    a = {"last_called_summary": "tv canale 33", "last_called_timestamp": ts}
    async def go():
        m.on_state_changed("media_player.echo", {"attributes": dict(a)})
        await asyncio.sleep(0.05)
        m._recent.clear()                                            # come se fossero passati >10 s
        m.on_state_changed("media_player.echo", {"attributes": dict(a)})
        await asyncio.sleep(0.05)
    run(go())
    assert len(m.rest.calls) == 1


def test_voce_alexa_frase_vecchia_al_primo_avvistamento_ignorata(make):
    import time
    m = make(alexa_enabled=True)
    old = {"last_called_summary": "tv canale 33", "last_called_timestamp": int(time.time() * 1000) - 3_600_000}
    async def go():
        m.on_state_changed("media_player.echo", {"attributes": old})
        await asyncio.sleep(0.05)
    run(go())
    assert m.rest.calls == []


@pytest.mark.parametrize("frase,numero", [
    ("metti canale trenta tré t. v.", "33"), ("metti canale trentacinque tv", "35"),
    ("canale ventuno t. v.", "21"), ("metti canale centoventi tv", "120"), ("canale 35 t. v.", "35"),
])
def test_parse_alexa_numeri_in_lettere_e_t_v(make, frase, numero):
    """Alexa trascrive «canale trenta tré t. v.»: numeri in lettere e «t. v.» con i punti."""
    c = make().parse(frase)
    assert c and c["action"] == "channel" and c["numero"] == numero, frase


def test_parse_alexa_t_v_altri_comandi(make):
    m = make()
    assert m.parse("spegni la t. v.")["action"] == "off"
    assert m.parse("alza il volume della t. v.")["action"] == "vol_rel"
    assert m.parse("metti il volume della tv a trenta") == {"action": "vol_set", "level": 30}
    assert m.parse("metti hdmi due sulla t. v.")["source"] == "HDMI 2"
    assert m.parse("accendi la tivù")["action"] == "on"
    assert m.parse("canale cinque t. v.")["numero"] == "505"     # nome dal file canali, non il numero 5
    assert m.parse("metti la musica uno") is None


# ── Telecomando a bottoni (Telegram) ─────────────────────────────────────────
def test_telecomando_trigger_esatto(make):
    m = make()
    for ok in ("telecomando", "Telecomando", "/telecomando", "il telecomando", "apri il telecomando", "/tv telecomando"):
        assert m.is_remote_request(ok), ok
    for no in ("dov'è il telecomando", "cambia le pile al telecomando della tv di mia madre", "metti canale 5", ""):
        assert not m.is_remote_request(no), no


def test_telecomando_tastiera_callback_validi(make):
    m = make()
    for page in ("main", "num", "src"):
        rows = m.remote_markup(page)["inline_keyboard"]
        assert rows
        for row in rows:
            for btn in row:
                assert btn["callback_data"].startswith("tvr:") and len(btn["callback_data"].encode()) <= 64
                assert btn["text"]
    codes = {b["callback_data"][4:] for r in m.remote_markup("main")["inline_keyboard"] for b in r}
    assert {"PWR", "MUTE", "VOLUP", "VOLDOWN", "UP", "DOWN", "LEFT", "RIGHT", "OK", "BACK", "HOME", "PG_NUM", "PG_SRC"} <= codes
    src_codes = [b["callback_data"][4:] for r in m.remote_markup("src")["inline_keyboard"] for b in r]
    assert "S0" in src_codes and "PG_MAIN" in src_codes


def test_telecomando_tasti(make):
    m = make()
    for code, exp in (("UP", ("webostv", "button")), ("OK", ("webostv", "button")), ("7", ("webostv", "button")),
                      ("VOLUP", ("media_player", "volume_up")), ("VOLDOWN", ("media_player", "volume_down")),
                      ("CHUP", ("media_player", "media_next_track")), ("PAUSE", ("media_player", "media_pause"))):
        m.rest.calls.clear()
        ok, err = run(m.remote_press(code))
        assert ok and err == "" and (m.rest.calls[0][0], m.rest.calls[0][1]) == exp, code
    m.rest.calls.clear(); run(m.remote_press("OK"))
    assert m.rest.calls[0][2]["button"] == "ENTER"
    m.rest.calls.clear(); run(m.remote_press("MUTE"))
    assert m.rest.calls[0][1:] == ("volume_mute", {"entity_id": ENT, "is_volume_muted": True})
    m.rest.calls.clear(); ok, _ = run(m.remote_press("S2"))                 # 3° ingresso della source_list
    assert ok and m.rest.calls[0][2]["source"] == "HDMI 1"
    ok, err = run(m.remote_press("S99")); assert not ok and err
    ok, err = run(m.remote_press("ZZZ")); assert not ok


def test_telecomando_tv_spenta_e_onoff(make):
    m = make(state="off")
    ok, err = run(m.remote_press("VOLUP"))
    assert not ok and "spenta" in err and m.rest.calls == []              # nessun tasto a TV spenta
    run(m.remote_press("PWR"))                                            # ⏻ la accende (ci prova)
    assert m.rest.calls and m.rest.calls[0][1] in ("turn_on", "send_magic_packet")
    m2 = make(state="on")
    run(m2.remote_press("PWR"))
    assert m2.rest.calls[0][1] == "turn_off"
    m3 = make(state="unavailable")
    ok, err = run(m3.remote_press("UP")); assert not ok and "raggiungibile" in err


def test_telecomando_errore_servizio_non_solleva(make):
    m = make(fail=[("webostv", "button")])
    ok, err = run(m.remote_press("UP"))
    assert not ok and "non riuscito" in err.lower()


# ── comandi_audio del file canali (frasi personalizzate per volume/muto) ──────
USER_JSON = {
    "canali": [
        {"nome": "Rai 3", "numero": "3", "alias": ["rai tre"]},
        {"nome": "Rete 4", "numero": "4", "alias": ["rete quattro", "quattro"]},
        {"nome": "Canale 5", "numero": "5", "alias": ["canale cinque", "cinque"]},
        {"nome": "TV8", "numero": "8", "alias": ["tv otto", "otto"]},
        {"nome": "20 Mediaset", "numero": "20", "alias": ["venti", "canale venti"]},
        {"nome": "Food Network", "numero": "33", "alias": ["fud netuork"]},
        {"nome": "Cine34", "numero": "34", "alias": ["trentaquattro"]},
    ],
    "comandi_audio": [
        {"azione": "alza_volume", "alias": ["alza la voce", "alza il volume", "più alto", "su la voce", "aumenta il volume"]},
        {"azione": "abbassa_volume", "alias": ["abbassa la voce", "abbassa il volume", "più basso", "giù la voce", "diminuisci il volume"]},
        {"azione": "muto", "alias": ["togli l'audio", "silenzio", "muto"]},
    ],
}


@pytest.fixture
def mu(make):
    m = make()
    m.set_channels_from_json_text(json.dumps(USER_JSON))
    return m


@pytest.mark.parametrize("frase,atteso", [
    ("alza la voce della tv", {"action": "vol_rel", "delta": 5}),
    ("alza la voce della t. v.", {"action": "vol_rel", "delta": 5}),
    ("tv più alto", {"action": "vol_rel", "delta": 5}),
    ("su la voce tv", {"action": "vol_rel", "delta": 5}),
    ("aumenta il volume della tv di dieci", {"action": "vol_rel", "delta": 10}),
    ("tv più alto di cinque", {"action": "vol_rel", "delta": 5}),             # «cinque» NON è il canale 5
    ("abbassa la voce della tv", {"action": "vol_rel", "delta": -5}),
    ("tv giù la voce", {"action": "vol_rel", "delta": -5}),
    ("diminuisci il volume della tv di 15", {"action": "vol_rel", "delta": -15}),
    ("silenzio tv", {"action": "mute"}),
    ("togli l'audio della tv", {"action": "mute"}),                           # prima diventava «riattiva audio»
    ("tv muto", {"action": "mute"}),
])
def test_comandi_audio_personalizzati(mu, frase, atteso):
    assert mu.parse(frase) == atteso, frase


def test_comandi_audio_senza_tv_non_scattano_da_voce(mu):
    """«alza la voce» da sola è dell'Echo: da Alexa serve «tv» (da Telegram /tv no)."""
    for f in ("alza la voce", "silenzio", "più alto", "togli l'audio"):
        assert mu.parse(f) is None, f
    assert mu.parse("alza la voce", force=True) == {"action": "vol_rel", "delta": 5}
    assert mu.parse("togli l'audio", force=True) == {"action": "mute"}


def test_canali_del_file_con_numeri_in_lettere(mu):
    for frase, num in (("metti canale venti t. v.", "20"), ("tv otto", "8"), ("metti rai tre", "3"),
                       ("metti trentaquattro", "34"), ("canale trenta tre t. v.", "33"), ("metti rete quattro", "4")):
        c = mu.parse(frase)
        assert c and c["action"] == "channel" and c["numero"] == num, frase
    assert mu.parse("metti il volume della tv a venti") == {"action": "vol_set", "level": 20}   # non il canale 20


def test_comandi_audio_file_non_valido_non_rompe(make):
    m = make()
    ch, w = m.set_channels_from_json_text(json.dumps({"canali": CH["canali"], "comandi_audio": [
        {"azione": "boh", "alias": ["x"]}, "stringa", {"azione": "muto", "alias": "zitto"}]}))
    assert len(ch) == 3 and any("boh" in x for x in w)
    assert m.parse("zitto tv") == {"action": "mute"}
    m.set_channels_from_json_text(json.dumps({"canali": CH["canali"], "comandi_audio": "rotto"}))
    assert m.audio_aliases == {} and m.parse("tv muto")["action"] == "mute"              # regole interne ancora ok


def test_ts_age_naive_locale_o_utc():
    """Orario senza fuso: se in una delle due letture è recente, non va scartato come «vecchio»."""
    from datetime import datetime, timezone
    import time as _t
    now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    assert abs(V.TvManager._ts_age(now_utc_naive)) < 5
    now_local_naive = datetime.now().isoformat()
    assert abs(V.TvManager._ts_age(now_local_naive)) < 5


# ── numeri detti in due parole («trenta quattro») con alias numerici nel file (quattro, cinque, otto…) ──
_UTENTE_CANALI = [
    ("Rai 1", "1", ["rai uno"]), ("Rai 2", "2", ["rai due"]), ("Rai 3", "3", ["rai tre"]),
    ("Rete 4", "4", ["rete quattro", "quattro"]), ("Canale 5", "5", ["canale cinque", "cinque"]),
    ("Italia 1", "6", ["italia uno"]), ("LA7", "7", ["la sette", "sette"]), ("TV8", "8", ["tv otto", "otto"]),
    ("NOVE", "9", ["nove"]), ("20 Mediaset", "20", ["venti", "canale venti"]), ("Rai 4", "21", ["rai quattro"]),
    ("Iris", "22", []), ("Rai Movie", "24", ["rai muvi"]), ("Rai Premium", "25", []), ("Cielo", "26", []),
    ("Twenty Seven", "27", ["ventisette", "twentyseven"]), ("TV2000", "28", ["tv duemila"]),
    ("LA7d", "29", ["la sette di"]), ("La5", "30", ["la cinque"]), ("Real Time", "31", ["rial taim"]),
    ("QVC", "32", ["quvici"]), ("Food Network", "33", ["fud netuork"]), ("Cine34", "34", ["trentaquattro"]),
    ("Focus", "35", ["focus"]), ("RTL 102.5 TV", "36", ["rtl"]), ("Warner TV", "37", ["uarner tv"]),
    ("Giallo", "38", []), ("Top Crime", "39", ["top craim"]), ("Italia 2", "49", ["italia due"]),
    ("DMAX", "52", ["dimax"]), ("Rai Storia", "54", []), ("Rai Scuola", "57", []), ("Rai Sport", "58", []),
    ("Motor Trend", "59", ["motor trend"]),
]


@pytest.fixture
def mc(make):
    m = make()
    m.set_channels_from_json_text(json.dumps({"canali": [{"nome": n, "numero": num, "alias": a}
                                                         for n, num, a in _UTENTE_CANALI]}))
    return m


@pytest.mark.parametrize("frase,numero", [
    ("metti canale trenta quattro", "34"),          # le frasi esatte trascritte da Alexa nel log dell'utente
    ("metti canale trenta cinque", "35"),
    ("metti canale cinque", "5"),
    ("metti canale quattro", "4"),
    ("metti canale focus", "35"),
    ("metti canale 34", "34"), ("metti canale 35", "35"), ("metti canale trentaquattro", "34"),
    ("metti canale trenta otto", "38"), ("metti canale trenta sette", "37"), ("metti canale trenta due", "32"),
    ("metti canale cinquanta due", "52"), ("metti canale cinquanta nove", "59"),
    ("metti canale venti", "20"), ("metti canale venti due", "22"), ("metti canale venti quattro", "24"),
    ("metti rete quattro", "4"), ("metti rai quattro", "21"), ("tv otto", "8"), ("metti canale nove", "9"),
    ("tv canale trenta quattro", "34"), ("metti canale trenta quattro t. v.", "34"),
])
def test_alias_numerici_non_rubano_i_numeri_a_due_parole(mc, frase, numero):
    c = mc.parse(frase)
    assert c and c["action"] == "channel" and c["numero"] == numero, (frase, c)


# ── Volume: uscita audio esterna, errori, comandi ripetuti ───────────────────────────────
def test_volume_stuck_ripiega_sui_tasti_fisici(make):
    """TV con barra audio/ARC: volume_set 'riesce' ma il livello non cambia → tasti VOLUMEUP/VOLUMEDOWN."""
    m = make(stuck=True)
    ok, msg = run(m.execute(m.parse("alza il volume della tv")))
    assert ok and "alzato" in msg
    assert m.rest.calls[0][1] == "volume_set"
    assert [c[2]["button"] for c in m.rest.calls[1:]] == ["VOLUMEUP"] * 5
    m = make(stuck=True)
    run(m.execute(m.parse("abbassa il volume della tv di 3")))
    assert [c[2]["button"] for c in m.rest.calls[1:]] == ["VOLUMEDOWN"] * 3


def test_volume_funzionante_non_preme_tasti(make):
    m = make()
    run(m.execute(m.parse("alza il volume della tv")))
    assert [c[1] for c in m.rest.calls] == ["volume_set"]             # niente doppia applicazione


def test_volume_set_con_errore_usa_i_tasti(make):
    m = make(fail=[("media_player", "volume_set")])
    ok, _ = run(m.execute(m.parse("alza il volume della tv")))
    assert ok and [c[2]["button"] for c in m.rest.calls[1:]] == ["VOLUMEUP"] * 5


def test_volume_al_massimo_o_minimo_non_ripiega(make):
    m = make(attrs={"volume_level": 1.0}, stuck=True)
    ok, msg = run(m.execute({"action": "vol_rel", "delta": 5}))
    assert ok and "100%" in msg and [c[1] for c in m.rest.calls] == ["volume_set"]


def test_volume_tutto_fallisce_lo_dice(make):
    m = make(attrs={"volume_level": None}, fail=[("webostv", "button"), ("media_player", "volume_up")])
    ok, msg = run(m.execute(m.parse("alza il volume della tv")))
    assert not ok and "non modificato" in msg


def test_voce_alexa_stessa_frase_ripetuta_con_nuovo_timestamp_si_riesegue(make):
    """«alza il volume della tv» due volte di fila (<10 s): sono due comandi, non un doppione."""
    import time
    m = make(alexa_enabled=True)
    t0 = int(time.time() * 1000)
    async def go():
        m.on_state_changed("media_player.echo", {"attributes": {"last_called_summary": "alza il volume della tv", "last_called_timestamp": t0}})
        await asyncio.sleep(0.05)
        m.on_state_changed("media_player.echo", {"attributes": {"last_called_summary": "alza il volume della tv", "last_called_timestamp": t0 + 4000}})
        await asyncio.sleep(0.05)
    run(go())
    assert [c[1] for c in m.rest.calls if c[1] == "volume_set"] == ["volume_set", "volume_set"]
    assert m.rest.calls[0][2]["volume_level"] == 0.25 and m.rest.calls[-1][2]["volume_level"] == 0.3


def test_voce_alexa_stessa_pronuncia_da_due_echo_conta_una_volta(make):
    import time
    m = make(alexa_enabled=True)
    a = {"last_called_summary": "alza il volume della tv", "last_called_timestamp": int(time.time() * 1000)}
    async def go():
        m.on_state_changed("media_player.echo_cucina", {"attributes": dict(a)})
        m.on_state_changed("media_player.echo_salotto", {"attributes": dict(a)})
        await asyncio.sleep(0.05)
    run(go())
    assert len(m.rest.calls) == 1
    # stessa frase subito dopo da un altro Echo con timestamp formattato diversamente: ancora un doppione
    m2 = make(alexa_enabled=True)
    t0 = int(time.time() * 1000)
    async def go2():
        m2.on_state_changed("media_player.echo_cucina", {"attributes": {"last_called_summary": "alza il volume della tv", "last_called_timestamp": t0}})
        m2.on_state_changed("media_player.echo_salotto", {"attributes": {"last_called_summary": "alza il volume della tv", "last_called_timestamp": t0 + 1}})
        await asyncio.sleep(0.05)
    run(go2())
    assert len(m2.rest.calls) == 1


# ── Marche diverse da LG ─────────────────────────────────────────────────────────────────
def _brand_tv(make, ent, brand="auto", name="", remote=None, **kw):
    m = make(brand=brand, **kw)
    m.entity = ent
    m._st_ref[ent] = {"state": "on", "attributes": {"friendly_name": name or ent, "volume_level": 0.2, "source_list": []}}
    if remote:
        m._st_ref[remote] = {"state": "on", "attributes": {}}
    return m


def test_marca_riconosciuta_da_nome_e_attributi(make):
    assert _brand_tv(make, "media_player.samsung_tv_55").detected_brand() == "samsung"
    assert _brand_tv(make, "media_player.salotto", name="Sony Bravia XR").detected_brand() == "sony"
    assert _brand_tv(make, "media_player.tv_lg").detected_brand() == "lg"
    assert _brand_tv(make, "media_player.salotto", attrs=None).detected_brand() == ""          # non riconosciuta
    assert _brand_tv(make, "media_player.salotto", brand="samsung").detected_brand() == "samsung"   # scelta esplicita vince
    m = _brand_tv(make, "media_player.salotto"); m._st_ref["media_player.salotto"]["attributes"]["sound_output"] = "tv_speaker"
    assert m.detected_brand() == "lg"


def test_samsung_usa_remote_send_command_non_webostv(make):
    m = _brand_tv(make, "media_player.samsung_tv", remote="remote.samsung_tv")
    ok, err = run(m.remote_press("UP")); assert ok
    assert m.rest.calls[-1] == ("remote", "send_command", {"entity_id": "remote.samsung_tv", "command": "KEY_UP"})
    run(m.remote_press("OK")); assert m.rest.calls[-1][2]["command"] == "KEY_ENTER"
    m.rest.calls.clear()
    m._st_ref["media_player.samsung_tv"]["attributes"]["volume_level"] = None                   # niente livello → tasti
    run(m.execute({"action": "vol_rel", "delta": 2}))
    assert [(c[0], c[2]["command"]) for c in m.rest.calls] == [("remote", "KEY_VOLUP")] * 2
    assert not any(c[0] == "webostv" for c in m.rest.calls)


def test_canale_samsung_senza_play_media_usa_i_numeri_del_remote(make):
    m = _brand_tv(make, "media_player.samsung_tv", remote="remote.samsung_tv", fail=[("media_player", "play_media")])
    ok, _ = run(m.execute({"action": "channel", "numero": "35", "label": "canale 35"}))
    cmds = [c[2]["command"] for c in m.rest.calls if c[0] == "remote"]
    assert ok and cmds == ["KEY_3", "KEY_5", "KEY_ENTER"]


def test_sony_nomi_tasti_ircc(make):
    m = _brand_tv(make, "media_player.sony_bravia", remote="remote.sony_bravia")
    run(m.remote_press("OK")); assert m.rest.calls[-1][2]["command"] == "Confirm"
    run(m.remote_press("5")); assert m.rest.calls[-1][2]["command"] == "Num5"


def test_marca_senza_tasti_spiega_cosa_fare_e_non_chiama_webostv(make):
    m = _brand_tv(make, "media_player.philips_tv", brand="other")
    ok, err = run(m.remote_press("UP"))
    assert not ok and "non è disponibile" in err and m.rest.calls == []
    # i comandi standard funzionano comunque
    ok, _ = run(m.execute({"action": "vol_set", "level": 30})); assert ok and m.rest.calls[-1][1] == "volume_set"
    ok, _ = run(m.execute({"action": "channel", "numero": "5", "label": "canale 5"})); assert ok
    assert m.rest.calls[-1][1] == "play_media"


def test_marca_non_riconosciuta_prova_come_lg_poi_il_remote(make):
    m = _brand_tv(make, "media_player.salotto")
    run(m.remote_press("UP")); assert m.rest.calls[-1][:2] == ("webostv", "button")           # comportamento storico
    m2 = _brand_tv(make, "media_player.salotto", fail=[("webostv", "button")])
    ok, err = run(m2.remote_press("UP")); assert not ok and "non riuscito" in err.lower()


def test_settings_marca_e_remote_validati(make):
    m = V.TvManager(settings={"entity": "media_player.x", "brand": "SAMSUNG", "remote_entity": "remote.x"})
    assert m.brand == "samsung" and m.remote_entity == "remote.x"
    m = V.TvManager(settings={"entity": "media_player.x", "brand": "boh", "remote_entity": "light.x"})
    assert m.brand == "auto" and m.remote_entity == ""
    assert V.TvManager(settings={}).settings_dict()["brand"] == "auto"


# ── Scheda TV: elenco entità (solo TV), marca, telecomando ───────────────────────────────
def _sc():
    def e(name, state="on", **a): return {"state": state, "attributes": {"friendly_name": name, **a}}
    return {
        "media_player.tv_lg": e("TV LG", device_class="tv"), "media_player.samsung_tv_55": e("Samsung 55", "off"),
        "media_player.philips_salotto": e("Philips Salotto"), "media_player.salotto": e("Salotto", device_class="tv"),
        "media_player.fire_tv_cucina": e("Fire TV Cucina"), "media_player.lg_webos_smart_tv": e("LG webOS Smart TV", "unavailable"),
        "media_player.echo_dot_cucina": e("Echo Dot Cucina", "idle"), "media_player.echo_show_salotto": e("Echo Show Salotto TV", "idle"),
        "media_player.sonos_arc": e("Sonos Arc", "idle"), "media_player.samsung_soundbar": e("Samsung Soundbar", "idle", device_class="speaker"),
        "media_player.google_nest_mini": e("Google Nest Mini", "idle"), "media_player.spotify_ago": e("Spotify Ago", "idle"),
        "media_player.camera_ospiti": e("Camera ospiti"), "remote.samsung_tv_55": e("Samsung 55"), "light.salotto": e("Luce"),
    }


def test_elenco_entita_solo_tv():
    import tv_ui
    opts = tv_ui.entities_options(_sc(), "")
    for ok in ("tv_lg", "samsung_tv_55", "philips_salotto", "salotto", "fire_tv_cucina", "lg_webos_smart_tv"):
        assert f'value="media_player.{ok}"' in opts, ok
    for no in ("echo_dot_cucina", "echo_show_salotto", "sonos_arc", "samsung_soundbar", "google_nest_mini",
               "spotify_ago", "camera_ospiti", "remote.", "light."):
        assert no not in opts, no
    # l'ordine: disponibili prima di unavailable
    assert opts.index("tv_lg") < opts.index("lg_webos_smart_tv")


def test_elenco_entita_scelta_non_tv_resta_visibile_e_mancante_pure():
    import tv_ui
    opts = tv_ui.entities_options(_sc(), "media_player.camera_ospiti")
    assert 'value="media_player.camera_ospiti" selected' in opts            # già scelta: non sparisce
    opts = tv_ui.entities_options(_sc(), "media_player.vecchia_tv")
    assert "media_player.vecchia_tv" in opts and "non trovata" in opts


def test_elenco_tutti_json_valido_e_sicuro():
    import tv_ui
    sc = _sc(); sc["media_player.xss"] = {"state": "on", "attributes": {"friendly_name": "</script><b>x</b>"}}
    j = tv_ui.all_entities_json(sc)
    assert "<" not in j and len(json.loads(j)) == 14
    assert {x["id"] for x in json.loads(j) if x["tv"]} >= {"media_player.tv_lg", "media_player.philips_salotto"}
    assert not any(x["tv"] for x in json.loads(j) if "echo" in x["id"] or "sonos" in x["id"])


def test_tab_html_completa_e_senza_segnaposto():
    import tv_ui
    sc = _sc()
    html = tv_ui.build_tab({"entity": "media_player.tv_lg", "brand": "samsung", "remote_entity": "remote.samsung_tv_55"},
                           tv_ui.entities_options(sc, "media_player.tv_lg"), "<div>sp</div>",
                           tv_ui.remote_options(sc, "remote.samsung_tv_55"), tv_ui.all_entities_json(sc))
    assert "__" not in html.replace("__init__", "")
    assert '<option value="samsung" selected>' in html and 'value="remote.samsung_tv_55" selected' in html
    assert 'id="tv_show_all"' in html and 'id="tv_all_json"' in html and "(LG webOS)" not in html.split("<h2>")[1][:40]
    assert "tvEntFill" in tv_ui.build_js() and "tv_brand" in tv_ui.build_js()
    assert "<option value=\"auto\" selected>" in tv_ui.build_tab({}, "", "")           # default: automatica


def test_file_esempio_canali_valido_senza_avvisi():
    raw = json.loads((SRC / "tv_canali_esempio.json").read_text(encoding="utf-8"))
    assert raw == json.loads((SRC.parent / "config_example" / "tv_canali_esempio.json").read_text(encoding="utf-8"))
    ch, w = V.normalize_channels(raw); au, aw = V.normalize_audio_commands(raw)
    assert len(ch) >= 20 and w == [] and aw == [] and set(au) == {"vol_up", "vol_down", "mute", "unmute"}
    assert {c["nome"]: c["numero"] for c in ch}["Rai 1"] == "1"


def test_file_esempio_si_carica_dalla_tv(make):
    m = make()
    chans, warns = m.set_channels_from_json_text((SRC / "tv_canali_esempio.json").read_text(encoding="utf-8"))
    assert len(chans) >= 20 and warns == []
    assert m.parse("metti rai uno") == {"action": "channel", "numero": "1", "label": "Rai 1"}
    assert m.parse("tv più alto di dieci") == {"action": "vol_rel", "delta": 10}
