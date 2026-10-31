"""
agent/live_dashboard.py — Dashboard AI-generata che legge le card HA installate.

Flusso:
1. Legge /config/homemind_patches/dashboard_card.yaml (card base dell'utente)
2. Legge lovelace/resources per scoprire card custom installate
3. Legge lovelace/config per capire entità usate nella dashboard reale
4. AI genera HTML usando web components reali + HTML/CSS puro
5. WebSocket live per dati istantanei
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("homemind.dashboard")

# ─── Regole sintassi ESATTA per card custom (da ha-claude card_editor) ────────
# Queste regole vengono iniettate nel prompt AI per evitare errori di formato
# che non possono essere inferiti dai tool descriptions.
CUSTOM_CARD_SYNTAX_RULES = """
REGOLE SINTASSI CUSTOM CARD — rispetta ESATTAMENTE questi formati:

mini-graph-card:
  'entities' DEVE essere una LISTA (MAI 'entity:' singolare):
  type: custom:mini-graph-card
  entities:
    - entity: sensor.temperatura
    - entity: sensor.umidita
  # SBAGLIATO: entity: sensor.temperatura

mushroom (mushroom-entity-card / mushroom-sensor-card / ecc.):
  Usa 'entity' SINGOLARE per l'entità principale:
  type: custom:mushroom-entity-card
  entity: sensor.temperatura
  # Per mushroom-chips-card usa invece 'chips: [...]'

apexcharts-card:
  'series' è una LISTA di oggetti con chiave 'entity':
  type: custom:apexcharts-card
  series:
    - entity: sensor.temperatura
    - entity: sensor.umidita
  # NON usare 'entities:' con apexcharts — usa 'series:'

button-card:
  Usa 'entity' SINGOLARE:
  type: custom:button-card
  entity: light.soggiorno
  # NON usare 'entities:' — usa 'entity:'

bubble-card:
  Richiede 'card_type' obbligatorio:
  type: custom:bubble-card
  card_type: button  # button | separator | cover | media-player | select | pop-up
  entity: light.soggiorno
  # Senza card_type la card non funziona

stack-in-card / layout-card:
  'cards' è una LISTA di sub-card:
  type: custom:stack-in-card
  cards:
    - type: tile
      entity: sensor.temperatura

plotly-graph-card:
  'entities' è una LISTA:
  type: custom:plotly-graph
  entities:
    - entity: sensor.temperatura
"""

CARD_CONFIG_FILE = Path("/config/homemind_patches/dashboard_card.yaml")
CACHE_FILE       = Path("/config/homemind_patches/dashboard_cache.html")


# ─── Helper: validazione entità + suggerimenti alternativi ────────────────────
def _validate_entities(entity_ids: list, state_cache: dict) -> dict:
    """
    Controlla quali entity_id esistono nello state_cache.
    Per quelle mancanti, cerca alternative per keyword/device_class.

    Returns:
        {
          "valid": ["entity.id", ...],
          "missing": [{"requested": "entity.id", "suggestion": "entity.id2|None"}],
        }
    """
    valid = []
    missing = []

    for eid in entity_ids:
        if eid in state_cache:
            valid.append(eid)
        else:
            # Cerca alternativa per keyword (parte finale dell'entity_id)
            keyword = eid.split(".")[-1].lower()
            domain  = eid.split(".")[0].lower()
            best    = None
            best_score = 0
            for candidate, data in state_cache.items():
                if not candidate.startswith(domain + "."):
                    continue
                cname = candidate.split(".")[-1].lower()
                fname = data.get("attributes", {}).get("friendly_name", "").lower()
                # Punteggio: parole in comune
                score = sum(1 for w in keyword.split("_") if w and w in cname)
                score += sum(1 for w in keyword.split("_") if w and w in fname)
                if score > best_score:
                    best_score = score
                    best = candidate
            missing.append({"requested": eid, "suggestion": best if best_score >= 2 else None})

    return {"valid": valid, "missing": missing}


def _smart_entity_search(keywords: list, state_cache: dict, device_class_map: dict = None) -> list:
    """
    Cerca entità in state_cache per keyword o device_class.
    Usato quando l'utente non fornisce YAML ma descrive le entità a parole.

    Returns: lista di {"eid", "name", "state", "unit", "device_class"}
    """
    if device_class_map is None:
        device_class_map = {
            "batteria": ["battery"], "batterie": ["battery"], "battery": ["battery"],
            "temperatura": ["temperature"], "temperature": ["temperature"],
            "umidita": ["humidity"], "umidità": ["humidity"], "humidity": ["humidity"],
            "consumo": ["energy", "power"], "energia": ["energy"], "energy": ["energy"],
            "potenza": ["power"], "power": ["power"],
            "tensione": ["voltage"], "voltage": ["voltage"],
            "luminosita": ["illuminance"], "illuminance": ["illuminance"],
            "movimento": ["motion", "occupancy"], "motion": ["motion"],
            "presenza": ["presence", "occupancy"],
        }

    found = {}
    for kw in keywords:
        kw_low = kw.lower()
        device_classes = device_class_map.get(kw_low, [])

        for eid, data in state_cache.items():
            if eid in found:
                continue
            attrs = data.get("attributes", {})
            dc = attrs.get("device_class", "")
            fname = attrs.get("friendly_name", "")

            # Match per device_class
            if device_classes and dc in device_classes:
                found[eid] = {
                    "eid": eid,
                    "name": fname or eid.split(".")[-1].replace("_", " ").title(),
                    "state": data.get("state", ""),
                    "unit": attrs.get("unit_of_measurement", ""),
                    "device_class": dc,
                }
                continue

            # Match per keyword in entity_id o friendly_name
            if not device_classes:
                if kw_low in eid.lower() or kw_low in fname.lower():
                    found[eid] = {
                        "eid": eid,
                        "name": fname or eid.split(".")[-1].replace("_", " ").title(),
                        "state": data.get("state", ""),
                        "unit": attrs.get("unit_of_measurement", ""),
                        "device_class": dc,
                    }

    return list(found.values())[:60]  # cap a 60 entità


def generate_live_dashboard(state_cache: dict, home) -> str:
    """Fallback statico — usato se la cache AI non esiste ancora."""
    if CACHE_FILE.exists():
        try:
            return CACHE_FILE.read_text()
        except Exception:
            pass
    return _generate_static_dashboard(state_cache, home)


async def generate_ai_dashboard(rest_client, ai_client, state_cache: dict, home, yaml_inline: str = None, mode: str = "html") -> str:
    """
    mode="html" → genera pagina HTML completa (salva in cache, serve /dashboard)
    mode="card"  → genera YAML Lovelace da copiare in HA (ritorna stringa YAML)
    """
    # 1. Card base: prima usa YAML inline da Telegram, poi file fisso
    user_card_yaml = ""
    if yaml_inline:
        user_card_yaml = yaml_inline
        logger.info("dashboard: card YAML da Telegram (%d chars)", len(user_card_yaml))
    elif CARD_CONFIG_FILE.exists():
        try:
            user_card_yaml = CARD_CONFIG_FILE.read_text()
            logger.info("dashboard: card base da file (%d chars)", len(user_card_yaml))
        except Exception as e:
            logger.warning("dashboard: errore lettura card base: %s", e)

    # 2. Card custom installate
    installed_cards = []
    card_names = []
    try:
        async with rest_client._session.get(f"{rest_client.base}/lovelace/resources") as r:
            if r.status == 200:
                data = await r.json()
                for res in data.get("resources", []):
                    url = res.get("url", "")
                    if url:
                        installed_cards.append(url)
        known = {
            "apexcharts": "ApexCharts Card",
            "mini-graph": "Mini Graph Card",
            "button-card": "Button Card",
            "mushroom": "Mushroom Cards",
            "bubble": "Bubble Card",
            "plotly": "Plotly Graph Card",
            "power-flow": "Power Flow Card",
            "energy-flow": "Energy Flow Card",
            "gauge": "Gauge Card",
        }
        for url in installed_cards:
            url_low = url.lower()
            for key, name in known.items():
                if key in url_low:
                    card_names.append({"name": name, "url": url})
                    break
        logger.info("dashboard: %d risorse Lovelace, %d card note", len(installed_cards), len(card_names))
    except Exception as e:
        logger.warning("dashboard: errore lovelace resources: %s", e)

    # 3. Entità dalla dashboard Lovelace reale
    dashboard_entities = []
    try:
        async with rest_client._session.get(f"{rest_client.base}/lovelace/config") as r:
            if r.status == 200:
                cfg = await r.json()
                dashboard_entities = _extract_entities(cfg)[:40]
                logger.info("dashboard: %d entità dalla Lovelace config", len(dashboard_entities))
    except Exception as e:
        logger.warning("dashboard: errore lovelace config: %s", e)

    # 4. Contesto stati
    entities_ctx = _build_state_context(state_cache, home, dashboard_entities)

    # 5. Genera in base al mode
    CARD_MODES = ("card_mushroom", "card_bubble", "card_gauge", "card_tile", "card_energia",
                  "card", "html_card")
    if mode in CARD_MODES:
        return await _ai_generate_card(
            ai_client, user_card_yaml, card_names, installed_cards,
            entities_ctx, state_cache, home, style=mode.replace("card_", "").replace("card", "mushroom")
        )

    html = await _ai_generate_html(
        ai_client, user_card_yaml, card_names, installed_cards,
        entities_ctx, state_cache, home
    )

    # Salva cache
    try:
        CACHE_FILE.write_text(html)
        logger.info("dashboard AI: HTML salvato (%d chars)", len(html))
    except Exception as e:
        logger.warning("dashboard: errore salvataggio cache: %s", e)

    return html


async def _ai_generate_html_card(ai_client, user_card_yaml, entities_ctx, state_cache) -> str:
    """Genera YAML Lovelace bellissimo con mushroom/button-card usando prompt con esempi concreti."""
    import yaml as _yaml, re as _re

    title = "HomeMind"
    user_entities = []
    if user_card_yaml:
        try:
            fixed = _re.sub(r'(?<=[^\s\n])((?:type|title|entities|entity|name|state_color|show_header_toggle):)', r'\n\1', user_card_yaml)
            parsed = _yaml.safe_load(fixed) or {}
            title = parsed.get("title", "HomeMind").strip()
            raw   = parsed.get("entities") or []
            for item in raw:
                if isinstance(item, str):    eid = item
                elif isinstance(item, dict): eid = item.get("entity", item.get("entity_id", ""))
                else: continue
                if not eid: continue
                s     = state_cache.get(eid, {})
                fname = s.get("attributes", {}).get("friendly_name",
                              eid.split(".")[-1].replace("_", " ").title())
                state = s.get("state", "unknown")
                dtype = ("contact"     if "_contact"   in eid else
                         "motion"      if "_occupancy"  in eid else
                         "light"       if eid.startswith("light.") else
                         "temperature" if "temp"        in eid.lower() else
                         eid.split(".")[0])
                user_entities.append({"eid": eid, "name": fname, "state": state, "type": dtype})
        except Exception as e:
            logger.warning("card parse: %s", e)

    if not user_entities:
        return "# Errore: nessuna entita trovata nel YAML"

    ent_lines = "\n".join(
        f"  - entity: {e['eid']}   # {e['name']} | stato: {e['state']} | tipo: {e['type']}"
        for e in user_entities
    )
    n = len(user_entities)

    system_prompt = """Sei un esperto HA Lovelace. Generi YAML per card bellissime con mushroom-cards.

REGOLE FERREE:
1. Output SOLO YAML valido — zero testo, zero commenti, zero markdown
2. Prima riga DEVE essere: type:
3. Usa TUTTE le entità fornite senza eccezioni
4. Usa mushroom-entity-card per ogni sensore

SINTASSI MUSHROOM — copia esattamente questo formato:

Per sensore binario (contatto/porta):
  type: custom:mushroom-entity-card
  entity: binary_sensor.ENTITY_ID
  name: "Nome Sensore"
  icon: mdi:door
  icon_color: green
  secondary_info: state
  tap_action:
    action: more-info

Per sensore presenza/movimento:
  type: custom:mushroom-entity-card
  entity: binary_sensor.ENTITY_ID
  name: "Nome Stanza"
  icon: mdi:motion-sensor
  icon_color: orange
  secondary_info: state
  tap_action:
    action: more-info

Per struttura GRID (metti sempre in griglia):
type: vertical-stack
cards:
  - type: custom:mushroom-title-card
    title: "Titolo"
    subtitle: "N sensori"
  - type: grid
    columns: 2
    square: false
    cards:
      - type: custom:mushroom-entity-card
        entity: binary_sensor.esempio
        name: "Esempio"
        icon: mdi:door
        icon_color: green
        secondary_info: state

ICONE per tipo:
- porta/finestra (_contact): mdi:door o mdi:window-closed
- presenza/movimento (_occupancy): mdi:motion-sensor
- luce (light.): mdi:lightbulb
- temperatura: mdi:thermometer
- allarme: mdi:shield-home

COLORI icon_color in base allo stato:
- contatto off (chiuso): green
- contatto on (aperto): red
- motion on (movimento): orange  
- motion off (quieto): grey
- luce on: yellow
- luce off: grey"""

    user_prompt = (
        f"Crea una card mushroom per queste {n} entita:\n\n"
        f"TITOLO: {title}\n\n"
        f"ENTITA CON STATI:\n{ent_lines}\n\n"
        f"Struttura: vertical-stack con mushroom-title-card + grid 2 colonne con mushroom-entity-card per ogni entita.\n"
        f"Usa icon_color basato sullo stato attuale (on=attivo=colore, off=grigio/verde).\n"
        f"Output: YAML puro che inizia con type: vertical-stack"
    )

    try:
        response = await ai_client.ask(system_prompt, user_prompt, max_tokens=3000)
        out = response.strip()
        # Rimuovi markdown
        if "```" in out:
            for p in out.split("```"):
                c = p.lstrip("yaml\nyml\n").strip()
                if c.startswith("type:"):
                    out = c
                    break
        if not out.startswith("type:"):
            idx = out.find("type:")
            out = out[idx:] if idx >= 0 else out
        # Verifica YAML valido
        import yaml as _y
        _y.safe_load(out)
        logger.info("mushroom card: %d entita, %d chars", n, len(out))
        return out
    except Exception as e:
        logger.error("card error: %s", e)
        # Fallback: genera card di emergenza senza AI
        import yaml as _y
        cards = []
        for ent in user_entities:
            dtype = ent["type"]
            st    = ent["state"]
            if dtype == "contact":
                icon, color = "mdi:door", "red" if st == "on" else "green"
            elif dtype == "motion":
                icon, color = "mdi:motion-sensor", "orange" if st == "on" else "grey"
            elif dtype == "light":
                icon, color = "mdi:lightbulb", "yellow" if st == "on" else "grey"
            else:
                icon, color = "mdi:eye", "primary"
            cards.append({
                "type": "custom:mushroom-entity-card",
                "entity": ent["eid"],
                "name": ent["name"],
                "icon": icon,
                "icon_color": color,
                "secondary_info": "state",
                "tap_action": {"action": "more-info"},
            })
        result = {
            "type": "vertical-stack",
            "cards": [
                {"type": "custom:mushroom-title-card",
                 "title": title,
                 "subtitle": f"{n} sensori"},
                {"type": "grid", "columns": 2, "square": False, "cards": cards}
            ]
        }
        return _y.dump(result, allow_unicode=True, default_flow_style=False, sort_keys=False)


async def _ai_generate_card(ai_client, user_card_yaml, card_names, installed_cards,
                            entities_ctx, state_cache, home, style="mushroom") -> str:
    """Funzione unificata: genera card Lovelace con stile selezionabile."""
    import yaml as _yaml, re as _re

    # ── Parse YAML utente ed estrai entità con stati reali ─────────────────
    title = "HomeMind"
    user_entities = []
    if user_card_yaml:
        try:
            fixed = _re.sub(r'(?<=[^\s\n])((?:type|title|entities|entity|name|state_color|show_header_toggle):)',
                            r'\n\1', user_card_yaml)
            parsed = _yaml.safe_load(fixed) or {}
            title  = parsed.get("title", "HomeMind").strip()
            raw    = parsed.get("entities") or []
            for item in raw:
                if isinstance(item, str):    eid = item
                elif isinstance(item, dict): eid = item.get("entity", item.get("entity_id", ""))
                else: continue
                if not eid: continue
                s     = state_cache.get(eid, {})
                fname = s.get("attributes", {}).get("friendly_name",
                              eid.split(".")[-1].replace("_", " ").title())
                state = s.get("state", "unknown")
                attrs = s.get("attributes", {})
                unit  = attrs.get("unit_of_measurement", "")
                dtype = ("contact"     if "_contact"   in eid else
                         "motion"      if "_occupancy"  in eid else
                         "light"       if eid.startswith("light.") else
                         "temperature" if "temp"        in eid.lower() else
                         "humidity"    if "humid"       in eid.lower() else
                         "power"       if any(k in eid.lower() for k in ("watt","power","energia","energy","fv","solar")) else
                         "alarm"       if eid.startswith("alarm_") else
                         eid.split(".")[0])
                user_entities.append({
                    "eid": eid, "name": fname, "state": state,
                    "type": dtype, "unit": unit
                })
        except Exception as e:
            logger.warning("card parse: %s", e)

    if not user_entities:
        # Controlla se c'è un KEYWORD_HINT (richiesta senza entity_id)
        keyword_hint = ""
        if user_card_yaml and "# KEYWORD_HINT:" in user_card_yaml:
            for line in user_card_yaml.splitlines():
                if "# KEYWORD_HINT:" in line:
                    keyword_hint = line.split("# KEYWORD_HINT:", 1)[-1].strip()
                    break

        if keyword_hint:
            # Smart search: cerca entità per keyword/device_class nello state_cache
            keywords = [w.strip().lower() for w in keyword_hint.replace(",", " ").split() if len(w.strip()) > 3]
            found = _smart_entity_search(keywords, state_cache)
            if found:
                logger.info("_ai_generate_card: smart search trovate %d entità per '%s'", len(found), keyword_hint)
                for item in found:
                    domain = item["eid"].split(".")[0]
                    dc = item.get("device_class", "")
                    dtype = (
                        "contact"     if dc == "door" or "contact" in item["eid"] else
                        "motion"      if dc in ("motion", "occupancy") else
                        "temperature" if dc == "temperature" else
                        "humidity"    if dc == "humidity" else
                        "power"       if dc in ("power", "energy") else
                        "light"       if domain == "light" else
                        domain
                    )
                    user_entities.append({
                        "eid": item["eid"],
                        "name": item["name"],
                        "state": item["state"],
                        "type": dtype,
                        "unit": item.get("unit", ""),
                    })
                title = keyword_hint.title()
            else:
                return f"# Nessuna entità trovata per '{keyword_hint}' in Home Assistant"
        else:
            return "# Errore: nessuna entita trovata nel YAML"

    n = len(user_entities)
    has_mushroom = any("mushroom" in (c.get("url","")).lower() for c in card_names)
    has_bubble   = any("bubble"   in (c.get("url","")).lower() for c in card_names)
    has_apex     = any("apexcharts" in (c.get("url","")).lower() for c in card_names)
    has_mini     = any("mini-graph" in (c.get("url","")).lower() for c in card_names)

    # ── Validazione entità (ispirato a ha-claude card_editor) ─────────────
    all_eids = [e["eid"] for e in user_entities]
    validation = _validate_entities(all_eids, state_cache)
    valid_ids   = set(validation["valid"])
    missing_ids = validation["missing"]

    # Costruisci blocco entità annotato con VALID/NOT FOUND
    ent_lines_parts = []
    for e in user_entities:
        status = "✅ VALID" if e["eid"] in valid_ids else "❌ NOT FOUND"
        ent_lines_parts.append(
            f"  - entity: {e['eid']}  # {e['name']} | stato={e['state']} {e['unit']} | tipo={e['type']} | {status}"
        )
    ent_lines = "\n".join(ent_lines_parts)

    # Aggiungi note sulle entità mancanti con suggerimenti
    missing_notes = ""
    if missing_ids:
        notes = []
        for m in missing_ids:
            if m["suggestion"]:
                notes.append(f"  - {m['requested']} → non trovata, usa invece: {m['suggestion']}")
            else:
                notes.append(f"  - {m['requested']} → non trovata in HA, verifica l'entity_id")
        if notes:
            missing_notes = "\nENTITÀ NON TROVATE — usa i suggerimenti:\n" + "\n".join(notes) + "\n"

    # ── Prompt specifico per stile ─────────────────────────────────────────
    if style == "bubble":
        style_prompt = f"""Usa BUBBLE CARD ({"installata" if has_bubble else "usa come se fosse installata"}).

STRUTTURA:
type: vertical-stack
cards:
  - type: custom:bubble-card
    card_type: separator
    name: "{title}"
  - type: custom:bubble-card
    card_type: button
    entity: binary_sensor.ENTITY
    name: "Nome"
    icon: mdi:ICON
    tap_action:
      action: more-info
  ... (una bubble-card per entità)

bubble-card card_type disponibili: button, separator, cover, media-player, select, pop-up
Per sensori binari usa card_type: button con icon condizionale."""

    elif style == "gauge":
        gauge_card = "custom:apexcharts-card" if has_apex else ("custom:mini-graph-card" if has_mini else "gauge")
        style_prompt = f"""Usa gauge/grafici per sensori con valori numerici.

Card da usare: {gauge_card}
{"" if has_apex else ""}

Se apexcharts disponibile:
  type: custom:apexcharts-card
  entities:
    - entity: sensor.ENTITY
  graph_span: 24h
  header:
    show: true
    title: "Nome"

Se gauge standard HA:
  type: gauge
  entity: sensor.ENTITY
  name: "Nome"
  min: 0
  max: 100
  needle: true
  severity:
    green: 0
    yellow: 60
    red: 80

Per sensori binari (non numerici) usa type: tile invece del gauge.
Struttura finale: vertical-stack con titolo + griglia gauge."""

    elif style == "tile":
        style_prompt = """Usa TILE CARD nativa HA — zero HACS richiesto.

STRUTTURA:
type: vertical-stack
cards:
  - type: markdown
    content: "## {title}"
  - type: grid
    columns: 2
    square: false
    cards:
      - type: tile
        entity: binary_sensor.ENTITY
        name: "Nome"
        icon: mdi:ICON
        color: red/green/orange/yellow/blue/grey
        vertical: true
        tap_action:
          action: more-info

COLORI tile:
- contatto aperto: red | chiuso: green
- movimento attivo: orange | quieto: grey  
- luce accesa: yellow | spenta: grey
- temperatura: deep-orange"""

    elif style == "energia":
        style_prompt = f"""Crea una card DEDICATA ALL'ENERGIA con layout premium.

Usa {"custom:apexcharts-card per grafici," if has_apex else ""} type: statistic, type: gauge, type: tile.

STRUTTURA SUGGERITA:
type: vertical-stack
cards:
  - type: custom:mushroom-title-card (o markdown se no mushroom)
    title: "⚡ Energia"
    subtitle: "Produzione e consumo"
  - type: grid
    columns: 2
    cards:
      - type: gauge  # produzione FV
        entity: sensor.fv_tot
        name: "☀️ Produzione"
        min: 0
        max: 6000
        needle: true
        severity: {{green: 0, yellow: 3000, red: 5000}}
      - type: gauge  # consumo
        entity: sensor.consumo_casa
        name: "🏠 Consumo"
        ...
  - type: statistic  # storico
    entity: sensor.fv_tot
    period:
      calendar:
        period: day
    stat_type: max"""

    else:  # mushroom (default)
        style_prompt = f"""USA MUSHROOM CARDS ({"installate ✓" if has_mushroom else "usa la sintassi mushroom"}).

STRUTTURA OBBLIGATORIA:
type: vertical-stack
cards:
  - type: custom:mushroom-title-card
    title: "{title}"
    subtitle: "{n} sensori"
  - type: grid
    columns: 2
    square: false
    cards:
      - type: custom:mushroom-entity-card
        entity: binary_sensor.ENTITY
        name: "Nome"
        icon: mdi:ICON
        icon_color: green
        secondary_info: state
        tap_action:
          action: more-info
      ... (una mushroom-entity-card per entità)

ICONE MDI per tipo:
- porta/finestra (_contact): mdi:door o mdi:window-closed-variant
- movimento (_occupancy): mdi:motion-sensor
- luce: mdi:lightbulb
- temperatura: mdi:thermometer
- umidità: mdi:water-percent
- energia/potenza: mdi:lightning-bolt
- allarme: mdi:shield-home

ICON_COLOR in base allo stato attuale:
- contatto on (aperto): red | off (chiuso): green
- motion on (movimento): orange | off (quieto): grey
- luce on: yellow | off: grey
- temperatura: deep-orange se >25, blue se <18, green altrimenti"""

    system_prompt = (
        "Sei un esperto HA Lovelace. Generi YAML card per Home Assistant.\n"
        "REGOLE ASSOLUTE:\n"
        "1. Output SOLO YAML RAW — NESSUN testo extra, NESSUN commento, NESSUN backtick markdown\n"
        "2. NESSUNA riga che inizia con tripli backtick o #\n"
        "3. Prima riga DEVE essere: type:\n"
        "4. Includi TUTTE le entità VALID fornite senza eccezioni\n"
        "5. YAML valido e incollabile direttamente in HA\n"
        "6. NON usare template Jinja2 {{ }} a meno che esplicitamente richiesto\n"
        "7. Usa solo entity_id esatti forniti — non inventare entità\n"
        "8. Per entità NOT FOUND: usa il suggerimento alternativo se disponibile, altrimenti omettila\n"
        + CUSTOM_CARD_SYNTAX_RULES
    )

    user_prompt = (
        f"Crea una card stile '{style}' per queste {n} entità:\n\n"
        f"TITOLO: {title}\n\n"
        f"ENTITÀ CON STATI E VALIDAZIONE:\n{ent_lines}\n"
        f"{missing_notes}\n"
        f"ISTRUZIONI STILE:\n{style_prompt}\n\n"
        f"Output: YAML puro, inizia con 'type:'"
    )

    # ── Fallback programmatico (mushroom) se AI fallisce ──────────────────
    def _fallback():
        # Fallback con card native HA — zero HACS richiesto
        cards = []
        for e in user_entities:
            dt, st = e["type"], e["state"]
            if dt == "contact":
                icon, color = "mdi:door", "red" if st == "on" else "green"
            elif dt == "motion":
                icon, color = "mdi:motion-sensor", "orange" if st == "on" else "grey"
            elif dt == "light":
                icon, color = "mdi:lightbulb", "yellow" if st == "on" else "grey"
            elif dt in ("temperature", "humidity"):
                icon, color = "mdi:thermometer", "deep-orange"
            elif dt == "power":
                icon, color = "mdi:lightning-bolt", "amber"
            else:
                icon, color = "mdi:eye", "primary"
            cards.append({
                "type": "tile",
                "entity": e["eid"], "name": e["name"],
                "icon": icon, "color": color,
                "tap_action": {"action": "more-info"},
                "vertical": True,
            })
        result = {
            "type": "vertical-stack",
            "cards": [
                {"type": "markdown", "content": f"## {title}\n_{n} entità_"},
                {"type": "grid", "columns": 2, "square": False, "cards": cards}
            ]
        }
        return _yaml.dump(result, allow_unicode=True, default_flow_style=False, sort_keys=False)

    try:
        response = await ai_client.ask(system_prompt, user_prompt, max_tokens=3000)
        out = response.strip()
        if "```" in out:
            for p in out.split("```"):
                c = p.lstrip("yaml\nyml\n").strip()
                if c.startswith("type:"):
                    out = c
                    break
        if not out.startswith("type:"):
            idx = out.find("type:")
            out = out[idx:] if idx >= 0 else out
        # Verifica YAML valido
        _yaml.safe_load(out)
        logger.info("card [%s]: %d entita, %d chars", style, n, len(out))
        return out
    except Exception as e:
        logger.error("card [%s] error: %s — uso fallback", style, e)
        return _fallback()


async def _ai_generate_lovelace_card(ai_client, user_card_yaml, card_names, installed_cards,
                                      entities_ctx, state_cache, home) -> str:
    """Genera YAML Lovelace WOW da YAML base utente."""

    # Estrai entity_id direttamente dallo YAML utente e risolvi stati reali
    import yaml as _yaml, re as _re
    user_entities = []
    if user_card_yaml:
        try:
            parsed = _yaml.safe_load(user_card_yaml)
            raw = parsed.get("entities") or [] if parsed else []
            for item in raw:
                if isinstance(item, str):
                    eid = item
                elif isinstance(item, dict):
                    eid = item.get("entity", item.get("entity_id", ""))
                else:
                    continue
                if eid and eid in state_cache:
                    s     = state_cache[eid]
                    fname = s.get("attributes", {}).get("friendly_name", eid)
                    state = s.get("state", "?")
                    dtype = "contact" if eid.endswith("_contact") else \
                            "motion"  if eid.endswith("_occupancy") else \
                            eid.split(".")[0]
                    user_entities.append({"eid": eid, "name": fname, "state": state, "type": dtype})
        except Exception as e:
            logger.warning("card: YAML parse error: %s", e)

    # Lista card installate
    cards_list = "\n".join(f"  - {c['name']}" for c in card_names) or "  NESSUNA (usa solo card standard HA)"
    has_mushroom = any("mushroom" in c["name"].lower() for c in card_names)
    has_bubble   = any("bubble"   in c["name"].lower() for c in card_names)
    has_button   = any("button-card" in c["url"].lower() for c in card_names)

    # ── Validazione entità ────────────────────────────────────────────────
    all_eids_lov = [e["eid"] for e in user_entities]
    validation_lov = _validate_entities(all_eids_lov, state_cache)
    valid_ids_lov   = set(validation_lov["valid"])
    missing_ids_lov = validation_lov["missing"]

    # Blocco entità annotato
    if user_entities:
        ent_block = "\n".join(
            f"  {i+1}. entity: {e['eid']}  [{('✅ VALID' if e['eid'] in valid_ids_lov else '❌ NOT FOUND')}]\n"
            f"     name: {e['name']} | state: {e['state']} | type: {e['type']}"
            for i, e in enumerate(user_entities)
        )
    else:
        ent_block = entities_ctx[:1500]

    # Note entità mancanti
    missing_notes_lov = ""
    if missing_ids_lov:
        notes = []
        for m in missing_ids_lov:
            if m["suggestion"]:
                notes.append(f"  - {m['requested']} → sostituisci con: {m['suggestion']}")
            else:
                notes.append(f"  - {m['requested']} → NON TROVATA, ometti dalla card")
        missing_notes_lov = "\nENTITÀ NON TROVATE:\n" + "\n".join(notes) + "\n"

    # Scegli strategia card in base a cosa è installato
    if has_mushroom:
        card_strategy = (
            "USA MUSHROOM CARDS — sono installate!\n"
            "Struttura: type: vertical-stack con:\n"
            "  - header: type: custom:mushroom-title-card (title, subtitle con stato generale)\n"
            "  - griglia: type: grid columns: 2 con custom:mushroom-entity-card per ogni entità\n"
            "mushroom-entity-card supporta: icon_color condizionale, tap_action, hold_action\n"
            "Per sensori binari usa secondary_info: state e card_mod per colori condizionali\n"
        )
    elif has_bubble:
        card_strategy = (
            "USA BUBBLE CARD — è installata!\n"
            "Struttura: type: vertical-stack con custom:bubble-card per ogni entità\n"
            "bubble-card supporta: sub_button, scrolling_effect, live_template\n"
        )
    elif has_button:
        card_strategy = (
            "USA BUTTON CARD — è installata!\n"
            "Struttura: type: grid columns: 2 con custom:button-card per ogni entità\n"
            "Usa styles per colori condizionali basati sullo stato\n"
        )
    else:
        card_strategy = (
            "Usa card standard HA ottimizzate:\n"
            "  - type: tile: moderna, colorata, supporta icon_color e features\n"
            "  - type: grid + tile: layout a griglia responsivo\n"
            "NON usare type: entities base — è vecchio e brutto\n"
        )

    system_prompt = (
        "Sei un esperto HA Lovelace. Generi YAML card PROFESSIONALI e VISIVAMENTE BELLE.\n"
        "REGOLA 1: Restituisci SOLO YAML valido — ZERO testo, ZERO markdown ```, ZERO commenti iniziali\n"
        "REGOLA 2: Il YAML deve iniziare ESATTAMENTE con 'type:' — nient'altro prima\n"
        "REGOLA 3: Includi TUTTE le entità VALID — per quelle NOT FOUND usa il suggerimento o ometti\n"
        "REGOLA 4: NON ripetere lo YAML base identico — TRASFORMALO completamente\n"
        + CUSTOM_CARD_SYNTAX_RULES
    )

    user_prompt = (
        f"Trasforma questo YAML base in una card SPETTACOLARE:\n\n"
        f"YAML BASE DA TRASFORMARE:\n{user_card_yaml or '(non fornito)'}\n\n"
        f"ENTITÀ CON STATI E VALIDAZIONE ({len(user_entities)} trovate):\n{ent_block}\n"
        f"{missing_notes_lov}\n"
        f"CARD INSTALLATE:\n{cards_list}\n\n"
        f"STRATEGIA DA SEGUIRE:\n{card_strategy}\n\n"
        f"COMPORTAMENTI ATTESI:\n"
        f"- Sensori contatto (_contact): 🔒 verde=chiuso, 🔓 rosso=aperto, pulsante lampeggia se aperto\n"
        f"- Sensori presenza (_occupancy): ⚫ grigio=quieto, 🔴 arancio=movimento rilevato\n"
        f"- Luci: 💡 giallo=accesa con dimmer se possibile, grigio=spenta\n"
        f"- Temperature: colore gradiente blu→arancio in base al valore\n\n"
        f"IMPORTANTE: Non restituire lo stesso YAML — genera qualcosa di completamente diverso e più bello.\n"
        f"Inizia direttamente con 'type:'"
    )

    try:
        response = await ai_client.ask(system_prompt, user_prompt, max_tokens=3000)
        yaml_out = response.strip()
        # Rimuovi qualsiasi markdown residuo
        if "```" in yaml_out:
            parts = yaml_out.split("```")
            for p in parts:
                clean = p.lstrip("yaml\n").lstrip("yml\n").strip()
                if clean.startswith("type:"):
                    yaml_out = clean
                    break
        # Assicura inizio con type:
        if not yaml_out.startswith("type:"):
            idx = yaml_out.find("type:")
            yaml_out = yaml_out[idx:] if idx >= 0 else yaml_out
        logger.info("card AI generata: %d chars, %d entità", len(yaml_out), len(user_entities))
        return yaml_out
    except Exception as e:
        logger.error("card AI error: %s", e)
        return f"# Errore generazione card: {e}"

async def _ai_generate_html(ai_client, user_card_yaml, card_names, installed_resources,
                              entities_ctx, state_cache, home) -> str:
    """Chiede all'AI di generare una dashboard HTML FEDELE allo YAML fornito."""
    import yaml as _yaml

    # ── Parsa YAML e risolvi stati reali delle entità ──────────────────────
    card_entities = []   # [{eid, name, state, icon, type}]
    card_title    = ""
    card_type     = ""

    if user_card_yaml:
        try:
            import re as _re
            # ── Pre-processing: ripristina newline se YAML su riga singola ──
            yaml_to_parse = user_card_yaml.strip()
            if "\n" not in yaml_to_parse:
                # 1. newline prima di "  - entity:" e "  - name:"
                yaml_to_parse = _re.sub(r'(?<=[^\n])(  - (?:entity|name):)', r'\n\1', yaml_to_parse)
                # 2. newline prima di "    name:" indentato
                yaml_to_parse = _re.sub(r'(?<=[^\n])(    name:)', r'\n\1', yaml_to_parse)
                # 3. top-level keys — solo quando attaccati a carattere precedente
                for key in ('type:', 'entities:', 'state_color:', 'show_header_toggle:', 'title:'):
                    yaml_to_parse = _re.sub(r'(?<=[^\s\n])(' + _re.escape(key) + ')', r'\n\1', yaml_to_parse)
                yaml_to_parse = yaml_to_parse.strip()
                logger.info("dashboard: YAML ricostruito (%d entita attese)", yaml_to_parse.count('- entity:'))

            parsed = _yaml.safe_load(yaml_to_parse)
            if isinstance(parsed, dict):
                card_title = parsed.get("title", "")
                card_type  = parsed.get("type", "entities")
                raw_ents   = parsed.get("entities") or []
                logger.info("dashboard: YAML parsato — type=%s title=%s entities=%d", card_type, card_title, len(raw_ents))
                for item in raw_ents:
                    if isinstance(item, str):
                        eid = item
                        name = ""
                    elif isinstance(item, dict):
                        eid  = item.get("entity", "")
                        name = item.get("name", "")
                    else:
                        continue
                    if not eid:
                        continue
                    s      = state_cache.get(eid, {})
                    state  = s.get("state", "unavailable")
                    attrs  = s.get("attributes", {})
                    fname  = name or attrs.get("friendly_name", eid.split(".")[-1].replace("_", " ").title())
                    unit   = attrs.get("unit_of_measurement", "")
                    # Tipo sensore
                    domain = eid.split(".")[0]
                    if domain == "binary_sensor":
                        dc = attrs.get("device_class", "")
                        if "contact" in eid or dc == "door" or dc == "window":
                            stype = "contact"
                        else:
                            stype = "motion"
                    elif domain == "sensor":
                        stype = "sensor"
                    elif domain == "alarm_control_panel":
                        stype = "alarm"
                    else:
                        stype = domain
                    card_entities.append({
                        "eid": eid, "name": fname, "state": state,
                        "unit": unit, "type": stype
                    })
                    logger.info("dashboard: entita %s (%s) → state=%s", eid[-20:], stype, state)
        except Exception as e:
            logger.warning("dashboard: YAML parse error: %s", e)

    # ── Costruisci contesto entità per il prompt ────────────────────────────
    if card_entities:
        entity_lines = []
        for e in card_entities:
            st = e["state"]
            if e["type"] == "contact":
                icon = "🔓" if st == "on" else "🔒"
                label = "APERTO" if st == "on" else "chiuso"
            elif e["type"] == "motion":
                icon = "🔴" if st == "on" else "⚫"
                label = "MOVIMENTO" if st == "on" else "quieto"
            else:
                icon = "📊"
                label = f"{st} {e['unit']}".strip()
            entity_lines.append(f"  {icon} {e['name']} ({e['eid']}): {label}")
        entity_block = "\n".join(entity_lines)
    else:
        entity_block = entities_ctx

    # ── Card installate ─────────────────────────────────────────────────────
    cards_list = "\n".join(f"  - {c['name']}: {c['url']}" for c in card_names) or "  (nessuna)"
    resources_imports = "\n".join(
        f'  <script type="module" src="{url}"></script>'
        for url in installed_resources[:15]
    )

    alarm_eid, alarm_st = home.primary_alarm() if home else ("", "disarmed")
    persons_in  = [v["name"] for v in home.persons.values() if v["state"] == "home"] if home else []
    persons_out = [v["name"] for v in home.persons.values() if v["state"] != "home"] if home else []

    # Conta sensori per tipo
    n_contact = sum(1 for e in card_entities if e["type"] == "contact")
    n_motion  = sum(1 for e in card_entities if e["type"] == "motion")
    n_open    = sum(1 for e in card_entities if e["type"] == "contact" and e["state"] == "on")
    n_moving  = sum(1 for e in card_entities if e["type"] == "motion" and e["state"] == "on")

    # Serializza entità come JSON — l'AI li usa come dati iniziali hardcoded nell'HTML
    entities_json = json.dumps([
        {"eid": e["eid"], "name": e["name"], "state": e["state"], "type": e["type"]}
        for e in card_entities
    ], ensure_ascii=False, indent=2)
    eid_js_list = json.dumps([e["eid"] for e in card_entities])

    system_prompt = (
        "Sei un esperto sviluppatore frontend specializzato in dashboard IoT per Home Assistant.\n"
        "Generi HTML COMPLETO, visivamente straordinario, fedele allo YAML dell'utente.\n\n"
        "REGOLE ASSOLUTE:\n"
        "1. Restituisci SOLO il codice HTML (<!DOCTYPE html>...</html>) — ZERO markdown\n"
        "2. CSS in <style>, JS in <script>, tutto inline\n"
        "3. CRITICO: renderizza LA GRIGLIA con TUTTI i sensori di INITIAL_STATES all'avvio — NON usare placeholder 'Nome Sensore'\n"
        "4. Il JS deve fare: INITIAL_STATES.forEach(s => renderCard(s)) nel DOMContentLoaded\n"
        "5. STILE: dark vibrante, glassmorphism, gradienti neon, animazioni fluide\n"
        "6. Font: Google Fonts — Rajdhani 600/700 per titoli/valori, Inter 400 per nomi\n"
        "7. Mobile first, responsive 2 colonne\n"
    )

    user_prompt = (
        f"Costruisci una dashboard per questa card HA:\n\n"
        f"YAML FORNITO:\n"
        f"  title: {card_title or 'Sensori'}\n"
        f"  type: {card_type}\n"
        f"  entità ({len(card_entities)} totali, {n_contact} contatti, {n_motion} movimento):\n"
        f"{entity_block}\n\n"
        f"CARD CUSTOM INSTALLATE IN HA:\n{cards_list}\n\n"
        f"SCRIPT DA IMPORTARE:\n{resources_imports or '  (nessuno)'}\n\n"
        f"STATO SISTEMA:\n"
        f"  Allarme: {alarm_st}\n"
        f"  In casa: {', '.join(persons_in) or 'nessuno'}\n"
        f"  Fuori: {', '.join(persons_out) or 'nessuno'}\n\n"
        "=== LAYOUT RICHIESTO ===\n\n"
        "HEADER (compact, max 60px):\n"
        "  - '🏠 HomeMind' a sinistra (font Rajdhani, gradient text amber→violet)\n"
        f"  - Titolo card '{card_title}' al centro\n"
        "  - Ora live HH:MM:SS a destra, aggiornata ogni secondo\n\n"
        "BANNER SOMMARIO (sotto header, 1 riga colorata):\n"
        f"  - Banner sommario: '{n_open}/{n_contact} contatti aperti  |  {n_moving}/{n_motion} mov. attivi  |  allarme: {alarm_st}'\n"
        f"    Verde se tutto ok, rosso se aperti/attivi\n"
        "  - Allarme stato con emoji: 🔓disarmed 🔒armed 🚨triggered\n\n"
        f"GRIGLIA SENSORI (mostra TUTTI e {len(card_entities)} sensori):\n"
        "  Layout: CSS Grid 2 colonne su mobile, 3 su desktop\n"
        "  Ogni card sensore:\n"
        "    - Nome friendly name (grassetto)\n"
        "    - Stato visualizzato con:\n"
        "      * contatti: 🔒 CHIUSO (sfondo verde scuro) | 🔓 APERTO (sfondo rosso con pulse)\n"
        "      * movimento: ⚫ quieto (sfondo grigio) | 🔴 MOVIMENTO (sfondo arancio con pulse)\n"
        "    - Bordo colorato a sinistra: verde=ok, rosso=aperto/attivo\n"
        "    - Glassmorphism: backdrop-filter:blur(10px), sfondo rgba semitrasparente\n"
        "    - Animazione pulse rossa quando ON\n\n"
        "DATI INIZIALI — HARDCODED nel <script> — USA QUESTI, non inventare placeholder:\n"
        "  ```js\n"
        f"  const INITIAL_STATES = {entities_json};\n"
        "  // OBBLIGATORIO: chiama renderGrid() subito con questi dati\n"
        "  function renderGrid(states) {\n"
        "    const grid = document.getElementById('sensor-grid');\n"
        "    grid.innerHTML = '';\n"
        "    states.forEach(s => {\n"
        "      const isOn = s.state === 'on';\n"
        "      const isContact = s.type === 'contact';\n"
        "      const icon = isContact ? (isOn ? '🔓' : '🔒') : (isOn ? '🔴' : '⚫');\n"
        "      const label = isContact ? (isOn ? 'APERTO' : 'chiuso') : (isOn ? 'MOVIMENTO' : 'quieto');\n"
        "      const cls = isOn ? 'card-on' : 'card-off';\n"
        "      grid.innerHTML += `<div class='sensor-card ${cls}' id='card-${s.eid.replace(/\\./g,\"-\")}'>"\
        "<b>${s.name}</b><span>${icon} ${label}</span></div>`;\n"
        "    });\n"
        "  }\n"
        "  document.addEventListener('DOMContentLoaded', () => renderGrid(INITIAL_STATES));\n"
        "  ```\n\n"
        "AGGIORNAMENTO LIVE (polling REST ogni 8s — più affidabile del WS dentro Ingress HA):\n"
        "  ```js\n"
        f"  const ENTITY_IDS = {eid_js_list};\n"
        "  async function pollStates() {\n"
        "    try {\n"
        "      // Dentro Ingress HA non serve Authorization header\n"
        "      const base = location.pathname.replace(/[/]dashboard[/]?$/, '');\n"
        "      const r = await fetch(base + '/api/states_batch', {method:'POST',\n"
        "        headers:{'Content-Type':'application/json'},\n"
        "        body: JSON.stringify({entity_ids: ENTITY_IDS})});\n"
        "      // Se non esiste /api/states_batch, usa fetch individuale\n"
        "      if (!r.ok) throw new Error('batch not available');\n"
        "      const data = await r.json();\n"
        "      data.forEach(s => updateSensor(s.entity_id, s.state));\n"
        "    } catch(e) {\n"
        "      // Fallback: aggiorna contatori dal DOM senza fetch\n"
        "    }\n"
        "  }\n"
        "  setInterval(pollStates, 8000);\n"
        "  ```\n\n"
        "PALETTE:\n"
        "  sfondo: #050510\n"
        "  card ok: rgba(16,185,129,.15) bordo #10b981 (verde)\n"
        "  card aperta/attiva: rgba(239,68,68,.2) bordo #ef4444 (rosso) + pulse\n"
        "  header gradient: linear-gradient(135deg,#1e1b4b,#312e81)\n"
        "  testo: #f1f5f9 principale, rgba(255,255,255,.5) secondario\n\n"
        "Genera l'HTML COMPLETO iniziando con <!DOCTYPE html>."
    )

    try:
        response = await ai_client.ask(system_prompt, user_prompt, max_tokens=4000)
        html = response.strip()
        # Pulizia markdown
        if "```" in html:
            parts = html.split("```")
            for p in parts:
                clean = p.lstrip("html").lstrip("\n")
                if clean.strip().lower().startswith("<!doctype"):
                    html = clean.strip()
                    break
        if not html.strip().lower().startswith("<!doctype"):
            idx = html.lower().find("<!doctype")
            if idx > 0:
                html = html[idx:]
        if not html.strip().lower().startswith("<!doctype"):
            logger.warning("dashboard AI: risposta non valida, uso fallback")
            return _generate_static_dashboard_from_ctx(entities_ctx, state_cache)
        logger.info("dashboard AI: HTML generato (%d chars, %d entita)", len(html), len(card_entities))
        return html
    except Exception as e:
        logger.error("dashboard AI error: %s", e)
        return _generate_static_dashboard_from_ctx(entities_ctx, state_cache)


def _extract_entities(obj, found=None) -> list:
    """Estrae ricorsivamente entity_id da config Lovelace."""
    if found is None:
        found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "entity" and isinstance(v, str) and "." in v:
                if v not in found:
                    found.append(v)
            elif k == "entities" and isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and "." in item:
                        if item not in found:
                            found.append(item)
                    elif isinstance(item, dict):
                        _extract_entities(item, found)
            else:
                _extract_entities(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _extract_entities(item, found)
    return found


def _build_state_context(state_cache: dict, home, extra_entities: list) -> str:
    """Costruisce contesto testuale degli stati rilevanti."""
    lines = []
    seen = set()

    energy_keys = ["fv", "solar", "enel", "grid", "battery", "batteria",
                   "consumo", "consumption", "energy", "power", "watt", "kwh"]
    for eid, s in state_cache.items():
        if eid in seen:
            continue
        eid_low = eid.lower()
        if any(k in eid_low for k in energy_keys):
            st   = s.get("state", "?")
            unit = s.get("attributes", {}).get("unit_of_measurement", "")
            name = s.get("attributes", {}).get("friendly_name", eid)
            if st not in ("unavailable", "unknown"):
                lines.append(f"{eid} ({name}): {st} {unit}")
                seen.add(eid)

    for eid, s in state_cache.items():
        if eid.startswith("light.") and eid not in seen:
            name = s.get("attributes", {}).get("friendly_name", eid)
            br   = s.get("attributes", {}).get("brightness", "")
            extra = f" brightness={br}" if br else ""
            lines.append(f"{eid} ({name}): {s.get('state')}{extra}")
            seen.add(eid)

    for eid, s in state_cache.items():
        unit = s.get("attributes", {}).get("unit_of_measurement", "")
        if unit in ("°C", "°F") and eid not in seen:
            if s.get("state") not in ("unavailable", "unknown"):
                name = s.get("attributes", {}).get("friendly_name", eid)
                lines.append(f"{eid} ({name}): {s.get('state')}{unit}")
                seen.add(eid)

    for eid in extra_entities:
        if eid in state_cache and eid not in seen:
            s    = state_cache[eid]
            name = s.get("attributes", {}).get("friendly_name", eid)
            unit = s.get("attributes", {}).get("unit_of_measurement", "")
            lines.append(f"{eid} ({name}): {s.get('state','?')} {unit}".strip())
            seen.add(eid)

    return "\n".join(lines[:60]) or "Nessun sensore disponibile"


def _load_energy_sensors_config() -> dict:
    """Legge energy_sensors da person_config.json."""
    cfg_path = Path("/config/homemind_patches/person_config.json")
    try:
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            return cfg.get("energy_sensors", {})
    except Exception:
        pass
    return {}


def _generate_static_dashboard(state_cache: dict, home) -> str:
    ctx = _build_state_context(state_cache, home, [])
    return _generate_static_dashboard_from_ctx(ctx, state_cache)


def _generate_static_dashboard_from_ctx(ctx: str, state_cache: dict) -> str:
    """Pagina di attesa bella con bottone genera e dati base."""
    now = datetime.now().strftime("%H:%M:%S")

    # Leggi sensori configurati da person_config.json
    energy_cfg = _load_energy_sensors_config()

    def get_sensor_val(eid, unit=""):
        if not eid:
            return "—"
        s = state_cache.get(eid, {})
        st = s.get("state", "")
        if st in ("unavailable", "unknown", ""):
            return "—"
        try:
            v = float(st)
            return f"{v:.1f}"
        except Exception:
            return st[:8]

    fv_eid   = energy_cfg.get("produzione_fv", "")
    cons_eid = energy_cfg.get("consumo_casa", "")
    enel_eid = energy_cfg.get("rete_enel", "")
    batt_eid = energy_cfg.get("batteria_wh", "")

    fv   = get_sensor_val(fv_eid)
    cons = get_sensor_val(cons_eid)
    enel = get_sensor_val(enel_eid)
    batt = get_sensor_val(batt_eid)

    # Unità
    def get_unit(eid):
        if not eid: return ""
        return state_cache.get(eid, {}).get("attributes", {}).get("unit_of_measurement", "")

    fv_u   = get_unit(fv_eid)   or "kWh"
    cons_u = get_unit(cons_eid) or "kWh"
    enel_u = get_unit(enel_eid) or "kWh"
    batt_u = get_unit(batt_eid) or "A"

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HomeMind Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#050510;color:#fff;font-family:'Inter',sans-serif;min-height:100vh;
        display:flex;flex-direction:column;align-items:center;justify-content:center;
        background-image:radial-gradient(ellipse at 20% 50%,rgba(99,102,241,.15) 0%,transparent 60%),
                         radial-gradient(ellipse at 80% 20%,rgba(6,182,212,.1) 0%,transparent 60%)}}
  h1{{font-family:'Rajdhani',sans-serif;font-size:2.5rem;font-weight:700;
      background:linear-gradient(135deg,#f59e0b,#ef4444,#8b5cf6);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
      margin-bottom:.5rem;text-align:center}}
  .subtitle{{color:rgba(255,255,255,.4);font-size:.9rem;margin-bottom:3rem;text-align:center}}
  .cards{{display:grid;grid-template-columns:repeat(2,1fr);gap:1rem;margin-bottom:2.5rem;width:100%;max-width:420px}}
  .card{{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
         border-radius:16px;padding:1.2rem;text-align:center;
         backdrop-filter:blur(10px)}}
  .card .val{{font-family:'Rajdhani',sans-serif;font-size:1.8rem;font-weight:700;line-height:1}}
  .card .lbl{{font-size:.7rem;color:rgba(255,255,255,.4);margin-top:.3rem;text-transform:uppercase;letter-spacing:.05em}}
  .card.fv .val{{color:#f59e0b}} .card.cons .val{{color:#ef4444}} .card.enel .val{{color:#06b6d4}} .card.batt .val{{color:#22c55e}}
  .unit{{font-size:.9rem;font-weight:400;opacity:.6}}
  .btn{{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;
        border:none;border-radius:14px;padding:1rem 2.5rem;
        font-family:'Rajdhani',sans-serif;font-size:1.2rem;font-weight:700;
        cursor:pointer;letter-spacing:.05em;
        box-shadow:0 0 30px rgba(99,102,241,.4);
        transition:all .2s;position:relative;overflow:hidden}}
  .btn:hover{{transform:translateY(-2px);box-shadow:0 0 50px rgba(99,102,241,.6)}}
  .btn:active{{transform:translateY(0)}}
  .btn.loading{{opacity:.7;cursor:not-allowed}}
  .btn .spinner{{display:none;width:20px;height:20px;border:3px solid rgba(255,255,255,.3);
                 border-top-color:#fff;border-radius:50%;animation:spin .8s linear infinite;
                 margin:0 auto}}
  @keyframes spin{{to{{transform:rotate(360deg)}}}}
  .status{{margin-top:1.5rem;color:rgba(255,255,255,.4);font-size:.85rem;text-align:center}}
  .status.ok{{color:#22c55e}} .status.err{{color:#ef4444}}
  .ts{{position:fixed;bottom:1rem;right:1rem;color:rgba(255,255,255,.2);font-size:.75rem}}
</style>
</head>
<body>
<h1>🏠 HomeMind</h1>
<p class="subtitle">Dashboard AI non ancora generata</p>

<div class="cards">
  <div class="card fv">
    <div class="val">{fv} <span class="unit">{fv_u}</span></div>
    <div class="lbl">☀️ Produzione FV</div>
  </div>
  <div class="card cons">
    <div class="val">{cons} <span class="unit">{cons_u}</span></div>
    <div class="lbl">🏠 Consumo Casa</div>
  </div>
  <div class="card enel">
    <div class="val">{enel} <span class="unit">{enel_u}</span></div>
    <div class="lbl">⚡ Da Rete</div>
  </div>
  <div class="card batt">
    <div class="val">{batt} <span class="unit">{batt_u}</span></div>
    <div class="lbl">🔋 Batteria</div>
  </div>
</div>

<button class="btn" id="btn" onclick="genera()">
  <span id="btn-label">✨ Genera Dashboard AI</span>
  <div class="spinner" id="spinner"></div>
</button>
<div class="status" id="status">Tocca per generare la dashboard con AI (~20s)</div>

<div class="ts">Aggiornato: {now}</div>

<script>
async function genera() {{
  const btn = document.getElementById('btn');
  const lbl = document.getElementById('btn-label');
  const sp  = document.getElementById('spinner');
  const st  = document.getElementById('status');
  btn.classList.add('loading');
  btn.disabled = true;
  lbl.style.display = 'none';
  sp.style.display = 'block';
  st.textContent = '🤖 AI in corso... leggo card installate e dati live (~20s)';
  st.className = 'status';
  try {{
    const base = location.pathname.replace(/[/]dashboard[/]?$/, '').replace(/[/]$/, '');
    const r = await fetch(base + '/genera_dashboard');
    if (r.ok) {{
      st.textContent = '✅ Dashboard generata! Ricarico...';
      st.className = 'status ok';
      setTimeout(() => location.href = base + '/dashboard', 1000);
    }} else {{
      throw new Error('HTTP ' + r.status);
    }}
  }} catch(e) {{
    st.textContent = '❌ Errore: ' + e.message;
    st.className = 'status err';
    btn.classList.remove('loading');
    btn.disabled = false;
    lbl.style.display = 'block';
    sp.style.display = 'none';
  }}
}}
</script>
</body>
</html>"""
