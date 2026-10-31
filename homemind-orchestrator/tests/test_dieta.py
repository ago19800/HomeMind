"""Test del modulo Dieta. Esegui:  cd src && python -m pytest ../tests -q"""
import asyncio, datetime, json, pathlib, sys
import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import dieta as D  # noqa: E402

EXAMPLE = (SRC / "dieta_esempio.json").read_text(encoding="utf-8")
MERCOLEDI = datetime.datetime(2026, 10, 28, 15, 0)       # mercoledì


@pytest.fixture
def dz(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "now_local", lambda: MERCOLEDI)
    monkeypatch.setattr(D, "dieta_path", lambda: tmp_path / "dieta.json")
    monkeypatch.setattr(D, "DATA_COPY_PATH", tmp_path / "copy.json")
    m = D.DietaManager(telegram_enabled=True, alexa_enabled=True, alexa_speakers=["media_player.echo"])
    m.set_from_json_text(EXAMPLE)
    return m


# ── Riconoscimento del pasto ────────────────────────────────────────────────
@pytest.mark.parametrize("frase,atteso", [
    ("colazione", "colazione"), ("Colazione domani mattina", "colazione"),
    ("pranzo", "pranzo"), ("cena", "cena"), ("cosa mangio stasera", "cena"),
    ("spuntino mattina", "spuntino_mattina"), ("spuntino di mattina", "spuntino_mattina"),
    ("spuntino pomeridiano", "spuntino_pomeridiano"), ("spuntino del pomeriggio", "spuntino_pomeridiano"),
    ("Spuntino Pom. (Pre-WO)", "spuntino_pomeridiano"), ("merenda", "spuntino_pomeridiano"),
    ("spuntino serale", "spuntino_serale"), ("spuntino della sera", "spuntino_serale"),
    ("spuntino", "spuntino"), ("che ore sono", None), ("", None),
])
def test_meal_from_text(frase, atteso):
    assert D.meal_from_text(frase) == atteso


# ── Normalizzazione JSON ────────────────────────────────────────────────────
def test_esempio_valido_e_completo(dz):
    st = dz.status()
    assert st["loaded"] and len(st["giorni"]) == 7 and not st["warnings"]
    for g in st["giorni"]:
        assert [p["key"] for p in g["pasti"]] == D.PASTI           # 6 pasti per giorno


def test_tipi_giorno(dz):
    tipi = {g["key"]: g["tipo"] for g in dz.status()["giorni"]}
    assert tipi == {"lunedi": "allenamento", "martedi": "riposo", "mercoledi": "allenamento",
                    "giovedi": "riposo", "venerdi": "allenamento", "sabato": "allenamento", "domenica": "riposo"}


def test_formato_stringhe_accenti_e_pipe():
    raw = {"giorni": {"Lunedì": {"pasti": {"Pranzo": ["Riso: 80g", "Olio EVO: 10g | Verdure: 150g"],
                                           "Spuntino Serale (Fac.)": {"facoltativo": True, "alimenti": ["Skyr: 150g"]}}}}}
    diet, w = D.normalize_diet(raw)
    pranzo = diet["giorni"]["lunedi"]["pasti"]["pranzo"]["alimenti"]
    assert [a["nome"] for a in pranzo] == ["Riso", "Olio EVO", "Verdure"]
    assert diet["giorni"]["lunedi"]["pasti"]["spuntino_serale"]["facoltativo"] is True


@pytest.mark.parametrize("raw,msg", [
    ([], "oggetto"), ({}, "giorni"), ({"giorni": {}}, "giorni"),
    ({"giorni": {"pippo": {"pasti": {"cena": ["a: 1"]}}}}, "Nessun giorno valido"),
    ({"giorni": {"lunedi": {"pasti": {"cena": []}}}}, "Nessun giorno valido"),
])
def test_json_non_utilizzabile(raw, msg):
    with pytest.raises(ValueError, match=msg):
        D.normalize_diet(raw)


def test_avvisi_su_voci_ignorate():
    raw = {"giorni": {"lunedi": {"pasti": {"cena": ["Pollo: 100g"], "brunch": ["x: 1"]}}}}
    _, w = D.normalize_diet(raw)
    assert any("brunch" in x for x in w) and any("mancanti" in x for x in w)


def test_upload_non_valido_non_tocca_il_piano(dz):
    prima = dz.raw_json_text()
    for bad in ["{rotto", '{"a":1}', "x" * 600_000]:
        with pytest.raises(ValueError):
            dz.set_from_json_text(bad)
    assert dz.raw_json_text() == prima and dz.status()["loaded"]


def test_bom_utf8(dz):
    dz.set_from_json_text("\ufeff" + EXAMPLE)
    assert dz.status()["loaded"]


def test_ricarica_da_disco(dz):
    nuovo = D.DietaManager()
    assert "7 giorni" in nuovo.load() and nuovo.status()["loaded"]


# ── Parsing domanda ─────────────────────────────────────────────────────────
def test_giorno_oggi_domani_settimana(dz):
    assert dz.parse_query("cosa ho per cena")["day"] == 2                       # mercoledì
    assert dz.parse_query("cosa ho per cena domani")["day"] == 3
    assert dz.parse_query("cosa ho per cena dopodomani")["day"] == 4
    assert dz.parse_query("cosa ho per pranzo lunedì")["day"] == 0
    assert dz.parse_query("cosa ho per pranzo ieri")["day"] == 1


def test_trigger_e_esclusioni(dz):
    assert dz.parse_query("accendi la luce della cena") is None
    assert dz.parse_query("la cena è pronta") is None                          # niente parola-domanda
    assert dz.parse_query("che temperatura c'è") is None
    assert dz.parse_query("cena", require_trigger=False)["meal"] == "cena"
    assert dz.parse_query("cosa mangio oggi")["whole_day"] is True
    assert dz.parse_query("cosa ho per spuntino")["ambiguous"] is True


# ── Risposte ────────────────────────────────────────────────────────────────
def test_risposta_vocale_unita_e_sigle(dz):
    q = dz.parse_query("cosa ho per cena lunedì")
    v, h = dz.build_answer(q)
    assert "Olio extravergine, 10 grammi" in v and "da 150 a 200 grammi" in v
    assert "EVO" not in v and " g." not in v
    assert "<b>150 g</b>" in h


def test_nota_e_facoltativo(dz):
    v, h = dz.build_answer(dz.parse_query("cosa ho per spuntino pomeridiano lunedì"))
    assert "da 60 a 120 minuti prima" in v
    v, h = dz.build_answer(dz.parse_query("cosa ho per spuntino serale"))
    assert "facoltativo" in v and "(facoltativo)" in h


def test_giorno_intero(dz):
    v, h = dz.build_answer(dz.parse_query("cosa mangio domani"))
    for nome in ("Colazione", "Pranzo", "Cena"):
        assert nome in v and nome in h
    assert "giorno di riposo" in v


def test_pasto_o_giorno_mancante():
    m = D.DietaManager()
    assert "Non ho ancora un piano" in m.build_answer({"meal": "cena", "day": 0, "delta": 0, "weekday_named": False,
                                                       "whole_day": False, "ambiguous": False})[0]


def test_html_escape(dz):
    dz.set_from_json_text(json.dumps({"giorni": {"lunedi": {"pasti": {"cena": [{"nome": "<b>x</b> & y", "quantita": "1"}]}}}}))
    h = dz.build_answer({"meal": "cena", "day": 0, "delta": 0, "weekday_named": True, "whole_day": False, "ambiguous": False})[1]
    assert "<b>x</b>" not in h and "&lt;b&gt;x&lt;/b&gt; &amp; y" in h


# ── Telegram: frasi libere ──────────────────────────────────────────────────
def test_telegram_frasi_libere(dz):
    f = dz.telegram_free_text
    assert "Colazione" in f("Colazione domani mattina")
    assert "Cena" in f("cosa ho per cena domani")
    assert f("Rosa ha fatto colazione da sola oggi") is None        # non è una domanda
    assert f("accendi le luci della cucina") is None
    assert f("come sta la casa oggi?") is None
    assert f("x " * 50) is None


def test_telegram_spuntino_ambiguo_poi_risposta(dz):
    assert "Quale spuntino" in dz.telegram_free_text("Spuntino domani")
    r = dz.telegram_free_text("pomeriggio")
    assert "Spuntino pomeridiano" in r and "domani" in r             # mantiene il giorno
    assert dz.telegram_free_text("pomeriggio") is None               # il pending si consuma


def test_telegram_pending_scade(dz, monkeypatch):
    dz.telegram_free_text("Spuntino")
    t0 = D.time.monotonic()
    monkeypatch.setattr(D.time, "monotonic", lambda: t0 + 200)
    assert dz.telegram_free_text("pomeriggio") is None


def test_senza_piano_non_intercetta():
    assert D.DietaManager().telegram_free_text("colazione") is None


def test_comando_slash(dz):
    assert "Piano di oggi" in dz.telegram_reply("")
    assert "Cena" in dz.telegram_reply("cena domani")


# ── ask(), switch e ascolto Alexa ───────────────────────────────────────────
class FakeNotifier:
    def __init__(self): self.sent = []
    async def send_html(self, m, force=False): self.sent.append(m)


class FakeRest:
    def __init__(self): self.calls = []
    async def call_service(self, *a, **k): self.calls.append(a)


def run(c): return asyncio.run(c)


def test_ask_rispetta_gli_switch(dz):
    dz.notifier, dz.rest = FakeNotifier(), FakeRest()
    dz.telegram_enabled, dz.alexa_enabled = True, False
    r = run(dz.ask("cosa ho per cena", source="alexa"))
    assert r["telegram_ok"] and not dz.rest.calls                    # solo Telegram
    dz.telegram_enabled, dz.alexa_enabled = False, True
    dz.notifier.sent.clear()
    r = run(dz.ask("cosa ho per cena", source="alexa"))
    assert not dz.notifier.sent and dz.rest.calls                    # solo Alexa


def test_ask_non_domanda_e_test_con_alexa_spenta(dz):
    dz.notifier, dz.rest = FakeNotifier(), FakeRest()
    assert run(dz.ask("accendi la luce"))["matched"] is False
    dz.alexa_enabled = False
    run(dz.ask("cena", force=True, source="test"))                   # il pulsante Prova parla comunque
    assert dz.rest.calls
    dz.rest.calls.clear()
    run(dz.ask("cena", force=True, source="api"))                    # l'API no, se Alexa è spenta
    assert not dz.rest.calls


def test_errore_telegram_non_rompe(dz):
    class Boom:
        async def send_html(self, *a, **k): raise RuntimeError("down")
    dz.notifier, dz.rest = Boom(), FakeRest()
    r = run(dz.ask("cena", force=True, source="api"))
    assert r["matched"] and not r["telegram_ok"] and "down" in r["telegram_error"]


def test_ascolto_last_called_summary(dz):
    async def go():
        dz.notifier, dz.rest = FakeNotifier(), FakeRest()
        ev = {"state": "x", "attributes": {"last_called_summary": "Cosa ho per cena domani"}}
        dz.on_state_changed("media_player.echo", ev)
        dz.on_state_changed("sensor.altro", ev)                       # doppione: ignorato
        dz.on_state_changed("sensor.x", {"state": "x", "attributes": {"last_called_summary": "accendi la luce"}})
        dz.on_state_changed("sensor.y", {"state": "x", "attributes": {}})
        dz.on_state_changed("sensor.z", None)
        await asyncio.sleep(0.1)
        return len(dz.notifier.sent)
    assert run(go()) == 1


def test_ascolto_spento_o_senza_piano():
    async def go():
        m = D.DietaManager(alexa_enabled=False)
        m.on_state_changed("a", {"attributes": {"last_called_summary": "cena"}})
        n = D.DietaManager(alexa_enabled=True)                        # nessun piano
        n.on_state_changed("a", {"attributes": {"last_called_summary": "cena"}})
        await asyncio.sleep(0.05)
    run(go())


# ── UI ──────────────────────────────────────────────────────────────────────
def test_ui_escape_e_segnaposto():
    import dieta_ui
    spk = dieta_ui.speakers_html([{"eid": "media_player.e", "name": '<script>x</script>', "state": "idle", "is_alexa": True}], set(), {})
    assert "<script>" not in spk
    html = dieta_ui.build_tab({"alexa_enabled": True, "volume": 0.7, "telegram_enabled": False}, spk)
    assert "__ALEXA__" not in html and "__SPEAKERS__" not in html and 'value="70"' in html
    assert dieta_ui.build_tab({"volume": "boh"}, "")                  # config sporca non esplode


def test_senza_pasto_serve_un_giorno_o_parola_dieta(dz):
    assert dz.parse_query("ciao", require_trigger=False) is None
    assert dz.parse_query("domani", require_trigger=False)["whole_day"] is True
    assert dz.parse_query("giovedì", require_trigger=False)["day"] == 3
    assert dz.parse_query("dieta", require_trigger=False)["whole_day"] is True


@pytest.mark.parametrize("frase", [
    "cosa ho per spuntino pomeridiano", "spuntino pomeridiano", "cena di domani", "qual è lo spuntino pomeridiano",
    "dimmi lo spuntino del pomeriggio", "leggimi la cena", "che c'è per cena", "cosa devo mangiare a pranzo",
    "che spuntino ho al pomeriggio", "mi dici cosa preparo per colazione", "ho spuntino mattina oggi",
    "quanto devo mangiare a cena", "cosa è previsto per lo spuntino serale", "dammi la colazione di domani",
])
def test_piu_frasi_di_attivazione(dz, frase):
    q = dz.parse_query(frase)
    assert q is not None and q["meal"] is not None, frase


@pytest.mark.parametrize("frase", [
    "metti la musica per la cena", "prenota un tavolo per cena", "accendi la luce della cucina per cena",
    "la cena è pronta", "ricordami la cena con i nonni", "aggiungi pasta alla lista della spesa per cena",
    "come sta il tempo oggi",
])
def test_frasi_che_non_devono_attivare(dz, frase):
    assert dz.parse_query(frase) is None, frase
