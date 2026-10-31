"""Memoria per persona, abitudini osservate dai dati reali, apprendimento d'uso dei dispositivi."""
import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
for _name in ("aiohttp", "aiofiles"):            # ambiente di test senza queste librerie
    try:
        __import__(_name)
    except ImportError:
        _m = types.ModuleType(_name)
        _m.ClientTimeout = lambda **k: None
        _m.ClientSession = object
        sys.modules[_name] = _m

from agent import memory_manager as mem          # noqa: E402
from agent import habit_learner as hl            # noqa: E402
from agent import routine_manager as rm          # noqa: E402


def run(c):
    return asyncio.run(c)


class FakeAI:
    def __init__(self, reply): self.reply, self.prompts = reply, []
    async def ask(self, system, prompt, max_tokens=0):
        self.prompts.append(prompt)
        return self.reply


@pytest.fixture
def mm(tmp_path, monkeypatch):
    monkeypatch.setattr(mem, "MEMORY_PATH", tmp_path / "mem.json")
    def make(ai=None, persons=("Agostino", "Rosa")):
        m = mem.MemoryManager(ai=ai)
        m.persons_cb = lambda: list(persons)
        return m
    return make


# ── memoria per persona ──────────────────────────────────────────────────────
def test_fatti_di_persone_diverse_non_si_sostituiscono(mm):
    m = mm()
    m.add_fact("Preferisce la casa a 21 gradi", "preferenze", person="Agostino")
    m.add_fact("Preferisce la casa a 23 gradi", "preferenze", person="Rosa")
    assert len(m._facts) == 2                                         # prima Rosa avrebbe cancellato Agostino
    m.add_fact("Preferisce la casa a 22 gradi", "preferenze", person="Rosa")
    assert len(m._facts) == 2 and "22" in [f for f in m._facts if f.get("person") == "rosa"][0]["text"]


def test_prompt_e_display_mostrano_la_persona(mm):
    m = mm()
    m.add_fact("Si sveglia alle 6:30", "abitudini", person="Rosa")
    m.add_fact("Il cane si chiama Rex", "persone")
    p = m.get_memory_prompt()
    assert "[Rosa] Si sveglia alle 6:30" in p and "Il cane si chiama Rex" in p
    d = m.get_facts_display()
    assert "Rosa" in d and "Casa / tutti" in d


def test_compatibile_con_vecchio_file_senza_person(tmp_path, monkeypatch):
    import json
    f = tmp_path / "old.json"
    f.write_text(json.dumps({"facts": [{"text": "Preferisce 21°C", "category": "preferenze", "ts": 1, "source": "x"}]}))
    monkeypatch.setattr(mem, "MEMORY_PATH", f)
    m = mem.MemoryManager()
    assert "Preferisce 21°C" in m.get_memory_prompt() and "Preferisce 21°C" in m.get_facts_display()


# ── estrazione AI: solo ciò che dice l'utente ───────────────────────────────
CONV = [{"role": "user", "content": "Rosa vuole sempre 23 gradi in camera"},
        {"role": "assistant", "content": "Ok! Ciao Gianni, ricordo che sei del 1980"},
        {"role": "user", "content": "grazie"}, {"role": "assistant", "content": "prego"}]


def test_estrazione_scarta_nomi_inventati_e_attribuisce_persona(mm):
    ai = FakeAI('[{"text":"L\'utente si chiama Gianni","category":"persone","person":null},'
                '{"text":"Preferisce 23 gradi in camera","category":"preferenze","person":"Rosa"},'
                '{"text":"Preferisce il the","category":"preferenze","person":"Mario"}]')
    m = mm(ai)
    run(m.extract_from_conversation(CONV))
    texts = [f["text"] for f in m._facts]
    assert not any("Gianni" in t for t in texts)                         # mai detto dall'utente
    rosa = [f for f in m._facts if f["text"].startswith("Preferisce 23")][0]
    assert rosa["person"] == "rosa"
    the = [f for f in m._facts if "the" in f["text"]][0]
    assert "person" not in the                                           # Mario non è della casa → non attribuito
    assert "BOT (solo contesto" in ai.prompts[0] and "PERSONE DELLA CASA: Agostino, Rosa" in ai.prompts[0]


def test_nome_detto_dall_utente_e_accettato(mm):
    ai = FakeAI('[{"text":"Il cane si chiama Rex","category":"persone","person":null}]')
    m = mm(ai)
    run(m.extract_from_conversation([{"role": "user", "content": "il mio cane si chiama Rex"},
                                     {"role": "assistant", "content": "bello"}]))
    assert [f["text"] for f in m._facts] == ["Il cane si chiama Rex"]


def test_senza_frasi_dell_utente_non_estrae(mm):
    ai = FakeAI('[{"text":"qualcosa","category":"generale"}]')
    m = mm(ai)
    run(m.extract_from_conversation([{"role": "assistant", "content": "a"}, {"role": "assistant", "content": "b"}]))
    assert m._facts == [] and ai.prompts == []


# ── abitudini osservate (routine GPS) ───────────────────────────────────────
def test_habit_lines_dalle_routine(tmp_path, monkeypatch):
    monkeypatch.setattr(rm, "ROUTINE_PATH", tmp_path / "r.json")
    r = rm.RoutineManager()
    r._patterns = {"per_person": {
        "agostino": {"days_observed": 12, "departure_times": [7.5, 7.6, 7.4, 7.55], "arrival_times": [18.0, 18.2, 17.9],
                     "kitchen_morning": [6.0],
                     "frequent_places": {"a": {"addr": "📍 Lavoro", "visit_count": 9, "total_min": 4500, "hours": [8, 8, 9]},
                                         "b": {"addr": "Via X", "visit_count": 1, "total_min": 20, "hours": [10]}}},
        "rosa": {"days_observed": 1, "departure_times": [8, 8, 8]},                     # pochi giorni: ignorata
        "sconosciuto": {"days_observed": 50, "departure_times": [1, 1, 1]}}}
    lines = r.get_habit_lines()
    assert any("Agostino di solito esce di casa verso le 07:30" in l for l in lines)
    assert any("rientra a casa" in l for l in lines)
    assert any("frequenta Lavoro (9 giorni" in l for l in lines)
    assert not any("Via X" in l for l in lines) and not any("Rosa" in l for l in lines) and not any("Sconosciuto" in l for l in lines)
    assert not any("cucina" in l for l in lines)                                        # 1 sola osservazione
    r.home = types.SimpleNamespace(persons={"person.rosa": {"name": "Rosa"}})
    assert "Rosa" in r.person_names()


def test_memoria_include_abitudini_osservate(mm):
    m = mm()
    m.set_habits_provider(lambda: ["Agostino di solito esce di casa verso le 07:30"])
    assert "OSSERVATE dai dati reali" in m.get_memory_prompt()
    assert "Abitudini osservate" in m.get_facts_display()
    m.set_habits_provider(lambda: 1 / 0)                              # un provider rotto non rompe la memoria
    assert m.get_memory_prompt()


# ── apprendimento d'uso dei dispositivi ─────────────────────────────────────
def _ev(day_offsets, hh, mm_, jitter=0):
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    return [(base + timedelta(days=d)).replace(hour=hh, minute=mm_) + timedelta(minutes=(i * 7) % (jitter + 1))
            for i, d in enumerate(day_offsets)]


def test_abitudine_quotidiana():
    h = hl.find_habits(_ev(range(12), 19, 10, jitter=20))
    assert len(h) == 1 and h[0]["days"] == 12 and abs(h[0]["minute"] - (19 * 60 + 10)) <= 20 and h[0]["daytype"] == ""


def test_abitudine_a_cavallo_di_mezzanotte():
    h = hl.find_habits(_ev(range(10), 23, 55) + _ev(range(10), 0, 5))        # 23:55 e 00:05 = stesso orario
    assert len(h) == 1 and h[0]["days"] >= 10


def test_solo_feriali_e_weekend():
    base = datetime(2026, 10, 5, tzinfo=timezone.utc)                         # lunedì
    fer = [base + timedelta(days=d, hours=7) for d in (0, 1, 2, 3, 4, 7, 8, 9)]
    assert hl.find_habits(fer)[0]["daytype"] == "nei giorni feriali"
    we = [base + timedelta(days=d, hours=10) for d in (5, 6, 12, 13, 19, 20)]
    h = hl.find_habits(we, observed_days=14)
    assert len(h) == 1 and h[0]["daytype"] == "nel weekend"


def test_rumore_non_e_abitudine():
    import random
    random.seed(1)
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    casuali = [base + timedelta(days=d, minutes=random.randint(0, 1439)) for d in range(14)]
    assert hl.find_habits(casuali) == []                                      # orari sparsi
    assert hl.find_habits(_ev(range(3), 19, 0)) == []                         # solo 3 giorni
    sfarfalla = [base + timedelta(days=d, hours=h) for d in range(10) for h in range(10)]
    assert hl.find_habits(sfarfalla) == []                                    # 10 accensioni al giorno


def test_eventi_dalla_history_ignora_stato_iniziale():
    rows = [{"entity_id": "light.x", "state": "on", "last_changed": "2026-10-01T00:00:00+00:00"},   # già accesa all'inizio
            {"state": "off", "last_changed": "2026-10-01T05:00:00+00:00"},
            {"state": "on", "last_changed": "2026-10-01T17:10:00+00:00"},
            {"state": "unavailable", "last_changed": "2026-10-01T18:00:00+00:00"}]
    ev = hl.events_from_rows(rows, "light", timezone.utc)
    assert [e.hour for e in ev] == [17]


def test_filtro_dispositivi_tecnici():
    st = lambda n, s="off": {"state": s, "attributes": {"friendly_name": n}}
    got = hl.eligible_entities({
        "light.cucina": st("Luce LED cucina"), "switch.presa_remota": st("Presa remota"),
        "switch.child_lock": st("Child lock"), "switch.lampada_led": st("Led indicatore"),
        "switch.zigbee2mqtt_permit_join": st("Permit join"), "light.rotta": st("Rotta", "unavailable"),
        "sensor.temp": st("T"), "cover.tapparella_salotto": st("Tapparella salotto"),
        "switch.macchina_caffe": st("Macchina caffè")})
    assert set(got) == {"light.cucina", "switch.presa_remota", "cover.tapparella_salotto", "switch.macchina_caffe"}


def test_linea_abitudine_leggibile():
    l = hl.habit_line("switch", "Macchina caffè", {"minute": 7 * 60 + 5, "std": 12, "days": 11, "daytype": "nei giorni feriali"})
    assert l == "L'interruttore «Macchina caffè» si accende di solito verso le 07:05 (±12 min, 11 giorni su 14, nei giorni feriali)"
