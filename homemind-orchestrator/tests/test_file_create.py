"""«crea un file ago.txt»: il file va creato davvero, e l'AI non deve inventare conferme."""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
for _n in ("aiohttp", "aiofiles"):                  # ambiente di test senza queste librerie
    try:
        __import__(_n)
    except ImportError:
        _m = types.ModuleType(_n)
        _m.ClientTimeout = lambda **k: None
        _m.ClientSession = object
        sys.modules[_n] = _m

import file_create as fc          # noqa: E402
import tools_system as ts         # noqa: E402


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(ts, "CONFIG_DIR", tmp_path)
    return tmp_path


@pytest.mark.parametrize("frase,path,content", [
    ("Crea un file ago.txt", "ago/progetti/ago.txt", ""),
    ("crea il file utente.md", "ago/progetti/utente.md", ""),
    ("crea utente.md", "ago/progetti/utente.md", ""),
    ("Crea file note.txt con scritto la spesa: latte e pane", "ago/progetti/note.txt", "la spesa: latte e pane"),
    ("crea un file ciao.md in ago/documenti con scritto \"Buongiorno\"", "ago/documenti/ciao.md", "Buongiorno"),
    ("crea file ago/documenti/x.json con {\"a\": 1}", "ago/documenti/x.json", "{\"a\": 1}"),
    ("scrivi un file chiamato Agostino.md", "ago/progetti/Agostino.md", ""),
    ("crea file a.txt nella cartella /config/ago/foto", "ago/foto/a.txt", ""),
])
def test_parse(frase, path, content):
    assert fc.parse(frase) == {"path": path, "content": content}


@pytest.mark.parametrize("frase", [
    "crea card luci", "crea sensore temperatura", "accendi la luce", "crea un file", "crea un file senza estensione",
    "dimmi cosa c'è nel file ago.txt", "crea una automazione", "",
])
def test_parse_non_e_creazione_file(frase):
    assert fc.parse(frase) is None


def test_run_crea_davvero_e_verifica(root):
    msg = fc.run(fc.parse("crea file utente.md con scritto Ciao Agostino"))
    f = root / "ago/progetti/utente.md"
    assert f.is_file() and f.read_text() == "Ciao Agostino"
    assert "✅ Creato" in msg and "/config/ago/progetti/utente.md" in msg and "byte" in msg


def test_run_file_vuoto(root):
    msg = fc.run(fc.parse("crea un file ago.txt"))
    assert (root / "ago/progetti/ago.txt").is_file() and "file vuoto" in msg


def test_run_non_sovrascrive(root):
    f = root / "ago/progetti/utente.md"
    f.parent.mkdir(parents=True); f.write_text("IMPORTANTE")
    msg = fc.run(fc.parse("crea file utente.md con scritto altro"))
    assert f.read_text() == "IMPORTANTE" and "esiste già" in msg


def test_run_file_protetto_e_fuori_da_config(root):
    assert "❌" in fc.run({"path": "configuration.yaml", "content": "x"})
    assert not (root / "configuration.yaml").exists()
    msg = fc.run({"path": "../../tmp/evil.txt", "content": "x"})
    assert "❌" in msg and not (root.parent / "tmp/evil.txt").exists()


def test_rete_di_sicurezza():
    assert fc.has_file_intent("Crea un file ago.txt")
    assert not fc.has_file_intent("accendi la luce")
    for reply in ("Il file Agostino.md è stato salvato correttamente in `/config/ago/progetti/test`. 💾",
                  "Il file ago.txt è stato creato e salvato in /config/ago/progetti/test.",
                  "Ho creato il file per te"):
        assert fc.claims_file_saved(reply), reply
    for reply in ("Non posso creare file da qui.", "La luce è accesa", "Ho acceso la luce del salotto"):
        assert not fc.claims_file_saved(reply), reply
