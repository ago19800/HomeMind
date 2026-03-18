"""HomeMind Orchestrator v26 — Chat AI avanzata + Sicurezza deterministica"""
import asyncio
from pathlib import Path
import json, logging, os, json, re
from datetime import datetime
from utils.timezone_helper import now_local
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.responses import JSONResponse, HTMLResponse
import uvicorn

from ha_client.websocket_client import HAWebSocketClient
from ha_client.rest_client import HARestClient
from agent.ai_provider import AIProvider, load_ai_provider_from_config


def _he(s: str) -> str:
    """Escape HTML per messaggi Telegram."""
    import html as _html
    return _html.escape(str(s))


from agent.home_model import HomeModel
from agent.security_manager import SecurityManager
from agent.ha_tools import HATools
from agent.log_analyzer import LogAnalyzer
from agent.update_checker import UpdateChecker
from agent.automations_manager import AutomationsManager
from agent.history_client import HistoryClient
from agent.repairs_checker import RepairsChecker
from agent.morning_briefing import MorningBriefing
from agent.live_dashboard import generate_ai_dashboard
from agent.energy_analyzer import EnergyAnalyzer
from agent.appliance_monitor import ApplianceMonitor
from agent.solar_optimizer  import SolarOptimizer
from notifier import Notifier
from telegram_bot import TelegramBot
from spazzatura import SpazzaturaManager

logging.basicConfig(
    level=getattr(logging, os.getenv("HM_LOG_LEVEL","INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("homemind")

HA_TOKEN      = os.getenv("HA_TOKEN","")
AI_PROVIDER   = os.getenv("HM_AI_PROVIDER","claude")
AI_MODEL      = os.getenv("HM_AI_MODEL","claude-sonnet-4-20250514")
AI_API_KEY    = os.getenv("HM_AI_API_KEY","")

# Lista provider costruita da run.sh leggendo le Opzioni addon
_providers_raw = os.getenv("HM_AI_PROVIDERS", "")
try:
    HM_AI_PROVIDERS: list = json.loads(_providers_raw) if _providers_raw.strip() else []
except Exception:
    HM_AI_PROVIDERS = []
NOTIFY_ENTITY = os.getenv("HM_NOTIFY_ENTITY","").strip()
TG_TOKEN      = os.getenv("HM_TELEGRAM_TOKEN","").strip()
TG_CHAT       = os.getenv("HM_TELEGRAM_CHAT","").strip()
ALARM_CODE    = os.getenv("HM_ALARM_CODE","1234")
# Blacklist persone e sensori — configurabile dalle opzioni add-on
PERSON_BLACKLIST = [x.strip() for x in os.getenv("HM_PERSON_BLACKLIST","").split(",") if x.strip()]
MOTION_BLACKLIST = [x.strip() for x in os.getenv("HM_MOTION_BLACKLIST","").split(",") if x.strip()]

ws_client:    HAWebSocketClient = None
rest_client:  HARestClient      = None
ai:           AIProvider        = None
home:         HomeModel         = None
security:     SecurityManager   = None
notifier:     Notifier          = None
tools:        HATools           = None
state_cache:  dict              = {}
CHAT_HISTORY: list              = []
tg_bot:       TelegramBot       = None
spazzatura:   "SpazzaturaManager" = None
update_checker: "UpdateChecker"  = None
log_analyzer:   "LogAnalyzer"    = None
automations_mgr: "AutomationsManager" = None
history_client:  "HistoryClient"      = None
repairs_checker: "RepairsChecker"     = None
morning_briefing: "MorningBriefing"   = None
energy_analyzer: "EnergyAnalyzer"   = None
appliance_monitor: "ApplianceMonitor" = None
solar_optimizer:   "SolarOptimizer"   = None

# ── CSS ────────────────────────────────────────────────────────────────────────
CSS = (
    "*{box-sizing:border-box;margin:0;padding:0}"
    "html,body{height:100%;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0}"
    "#app{display:flex;flex-direction:column;height:100vh;max-width:960px;margin:0 auto}"
    "#hdr{padding:10px 14px;background:#1e293b;border-bottom:1px solid #334155;display:flex;align-items:center;gap:8px;flex-shrink:0}"
    "#hdr h1{font-size:1rem;color:#60a5fa;font-weight:700;letter-spacing:.5px}"
    ".bdg{font-size:.68rem;padding:2px 7px;border-radius:99px;font-weight:700}"
    ".ok{background:#14532d;color:#86efac}.warn{background:#78350f;color:#fcd34d}.alarm{background:#7f1d1d;color:#fca5a5}"
    "#bar{padding:5px 14px;background:#1e293b;border-bottom:1px solid #334155;font-size:.74rem;color:#94a3b8;flex-shrink:0;white-space:nowrap;overflow-x:auto}"
    "#msgs{flex:1;overflow-y:auto;padding:10px 14px;display:flex;flex-direction:column;gap:8px;-webkit-overflow-scrolling:touch}"
    ".msg{max-width:90%;padding:9px 13px;border-radius:12px;line-height:1.55;font-size:.86rem;word-break:break-word}"
    ".mu{align-self:flex-end;background:#1d4ed8;color:#fff;border-bottom-right-radius:4px}"
    ".ma{align-self:flex-start;background:#1e293b;color:#e2e8f0;border-bottom-left-radius:4px;width:100%;max-width:100%}"
    ".ms{align-self:center;background:#0f172a;color:#64748b;font-size:.72rem;padding:3px 8px;border-radius:5px}"
    ".ma pre{background:#0f172a;border-left:3px solid #3b82f6;padding:8px;border-radius:4px;overflow-x:auto;font-size:.74rem;margin:5px 0;white-space:pre-wrap;position:relative}"
    ".cpbtn{position:absolute;top:4px;right:4px;background:#334155;border:none;color:#94a3b8;font-size:.65rem;padding:2px 6px;border-radius:3px;cursor:pointer}"
    ".cpbtn:hover{background:#475569;color:#fff}"
    ".ma code{color:#60a5fa;font-family:monospace;font-size:.84em}"
    ".ma h3{color:#93c5fd;margin:6px 0 3px;font-size:.88rem}"
    ".ma ul{padding-left:18px;margin:3px 0}"
    ".ma li{margin:2px 0}"
    ".typing{display:flex;gap:4px;padding:2px 0}"
    ".dot{width:6px;height:6px;border-radius:50%;background:#60a5fa;animation:bk .9s infinite}"
    ".dot:nth-child(2){animation-delay:.2s}.dot:nth-child(3){animation-delay:.4s}"
    "@keyframes bk{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-6px)}}"
    "#qa{padding:5px 10px 0;display:flex;gap:5px;flex-wrap:wrap;flex-shrink:0}"
    ".qb{background:#1e293b;border:1px solid #334155;color:#94a3b8;border-radius:7px;padding:4px 9px;font-size:.72rem;cursor:pointer;white-space:nowrap}"
    ".qb:active,.qb:hover{background:#334155;color:#e2e8f0}"
    "#ia{padding:8px 10px;background:#1e293b;border-top:1px solid #334155;display:flex;gap:7px;flex-shrink:0;align-items:flex-end}"
    "#tx{flex:1;background:#0f172a;border:1px solid #334155;border-radius:9px;padding:9px 12px;color:#e2e8f0;font-size:.88rem;resize:none;min-height:40px;max-height:100px;overflow-y:auto;line-height:1.4}"
    "#tx:focus{outline:none;border-color:#3b82f6}"
    "#sb{background:#2563eb;border:none;border-radius:9px;width:40px;min-width:40px;height:40px;color:#fff;cursor:pointer;font-size:1rem}"
    "#sb:disabled{background:#334155;cursor:not-allowed}"
    ".warn-box{background:#78350f;border:1px solid #92400e;border-radius:8px;padding:10px 13px;margin:4px 0;font-size:.82rem;color:#fcd34d}"
    ".ok-box{background:#14532d;border:1px solid #166534;border-radius:8px;padding:10px 13px;margin:4px 0;font-size:.82rem;color:#86efac}"
    "#overlay{display:none;position:fixed;inset:0;background:#0f172a;z-index:999;flex-direction:column}"
    "#overlay.open{display:flex}"
    "#ov-hdr{padding:10px 14px;background:#1e293b;border-bottom:1px solid #334155;display:flex;align-items:center;gap:10px;flex-shrink:0}"
    "#ov-hdr h2{font-size:.95rem;color:#60a5fa;flex:1;margin:0}"
    "#ov-close{background:none;border:none;color:#94a3b8;font-size:1.3rem;cursor:pointer;padding:2px 8px;line-height:1}"
    "#ov-body{flex:1;overflow:auto}"
    "#ov-body iframe{width:100%;height:100%;border:none;background:#0f172a}"
    "#ov-content{padding:1rem;overflow:auto;height:100%}"
    ".navbtn{background:none;border:1px solid #33415580;color:#94a3b8;border-radius:6px;padding:3px 9px;font-size:.72rem;cursor:pointer;white-space:nowrap}"
    ".navbtn:hover,.navbtn:active{background:#1e293b;color:#e2e8f0}"
    ".navbtn.blue{border-color:#38bdf840;color:#38bdf8}"
)

JS = r"""
var msgs=document.getElementById('msgs'),
    tx=document.getElementById('tx'),
    sb=document.getElementById('sb');

function esc(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderAI(text){
  // Code blocks with copy button
  var h = text.replace(/```([\w]*)\n?([\s\S]*?)```/g, function(_, lang, code){
    var id = 'cb'+Math.random().toString(36).slice(2,7);
    var escaped = esc(code.trim());
    return '<pre id="'+id+'"><button class="cpbtn" onclick="cp(\''+id+'\')">Copia</button>'+escaped+'</pre>';
  });
  // Inline code
  h = h.replace(/`([^`\n]+)`/g, function(_,c){ return '<code>'+esc(c)+'</code>'; });
  // Bold
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Headers
  h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  // Lists
  h = h.replace(/^- (.+)$/gm, '<li>$1</li>');
  h = h.replace(/(<li>.*<\/li>\n?)+/g, function(m){ return '<ul>'+m+'</ul>'; });
  // Remove action tags
  h = h.replace(/\[CALL_SERVICE:[^\]]+\]/g, '');
  // Newlines
  h = h.replace(/\n/g,'<br>');
  return h;
}

function cp(id){
  var el=document.getElementById(id);
  if(!el)return;
  var txt=el.innerText.replace(/^Copia\s*/,'');
  navigator.clipboard.writeText(txt).then(function(){
    var btn=el.querySelector('.cpbtn');
    if(btn){btn.textContent='✓ Copiato';setTimeout(function(){btn.textContent='Copia';},2000);}
  });
}

function addMsg(text,role){
  var d=document.createElement('div');
  if(role==='ai'){d.className='msg ma';d.innerHTML=renderAI(text);}
  else if(role==='sys'){d.className='msg ms';d.textContent=text;}
  else{d.className='msg mu';d.textContent=text;}
  msgs.appendChild(d);
  msgs.scrollTop=msgs.scrollHeight;
}

function showTyping(){
  var d=document.createElement('div');
  d.className='msg ma';d.id='typ';
  d.innerHTML='<div class="typing"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>';
  msgs.appendChild(d);
  msgs.scrollTop=msgs.scrollHeight;
}

function send(){
  var text=tx.value.trim();
  if(!text||sb.disabled)return;
  tx.value='';tx.style.height='40px';
  addMsg(text,'user');
  sb.disabled=true;
  showTyping();
  var xhr=new XMLHttpRequest();
  xhr.open('POST','chat',true);
  xhr.setRequestHeader('Content-Type','application/json');
  xhr.timeout=60000;
  xhr.onload=function(){
    var t=document.getElementById('typ');if(t)t.remove();
    if(xhr.status===200){
      try{
        var d=JSON.parse(xhr.responseText);
        addMsg(d.reply,'ai');
        if(d.actions&&d.actions.length)addMsg('Eseguito: '+d.actions.join(' | '),'sys');
      }catch(e){addMsg('Errore risposta: '+xhr.responseText.substring(0,120),'sys');}
    }else{addMsg('Errore HTTP '+xhr.status+': '+xhr.responseText.substring(0,100),'sys');}
    sb.disabled=false;tx.focus();
  };
  xhr.onerror=function(){var t=document.getElementById('typ');if(t)t.remove();addMsg('Errore connessione','sys');sb.disabled=false;};
  xhr.ontimeout=function(){var t=document.getElementById('typ');if(t)t.remove();addMsg('Timeout — riprova','sys');sb.disabled=false;};
  xhr.send(JSON.stringify({message:text}));
}

function sendQ(el){
  tx.value=el.getAttribute('data-q')||el.textContent;
  send();
}

tx.addEventListener('keydown',function(e){
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}
});
tx.addEventListener('input',function(){
  tx.style.height='auto';
  tx.style.height=Math.min(tx.scrollHeight,100)+'px';
});

// ── Overlay panel (no new tab, no auth issues) ─────────────────────────
function openPanel(path, title) {
  var ov = document.getElementById('overlay');
  var h2 = document.getElementById('ov-title');
  var body = document.getElementById('ov-content');
  h2.textContent = title;
  body.innerHTML = '<div style="padding:2rem;color:#94a3b8;text-align:center">⏳ Caricamento...</div>';
  ov.classList.add('open');
  // Usa fetch per evitare blocchi CSP sugli iframe in HA Ingress
  var base = location.pathname.replace(/\/$/, '');
  fetch(base + '/' + path)
    .then(function(r){ return r.text(); })
    .then(function(html){
      // Estrai solo il <body> se è una pagina completa, altrimenti usa tutto
      var m = html.match(/<body[^>]*>([\s\S]*)<\/body>/i);
      var content = m ? m[1] : html;
      body.innerHTML = content;
      // Esegui gli script inline (fetch li ignora altrimenti)
      body.querySelectorAll('script').forEach(function(old){
        var s = document.createElement('script');
        s.textContent = old.textContent;
        old.parentNode.replaceChild(s, old);
      });
    })
    .catch(function(e){
      body.innerHTML = '<div style="padding:2rem;color:#f87171">❌ Errore caricamento: ' + e + '</div>';
    });
}
function closePanel() {
  var ov = document.getElementById('overlay');
  var body = document.getElementById('ov-content');
  ov.classList.remove('open');
  body.innerHTML = '';
}
// Close on Escape
document.addEventListener('keydown', function(e){
  if(e.key==='Escape') closePanel();
});
"""

QUICK = [
    ("Stato casa",        "Dimmi lo stato completo della casa"),
    ("Energia",           "Analizza energia: fotovoltaico, batteria, rete Enel"),
    ("Luci ON",           "Quali luci sono accese? Voglio dettagli e entity_id"),
    ("Temperatura",       "Tutte le temperature in casa"),
    ("Sensori movimento", "Elenca tutti i sensori movimento fisici trovati e il loro stato"),
    ("Sicurezza",         "Stato antifurto: persone, allarme, sensori movimento"),
    ("Card energia",      "Genera le card YAML Lovelace per monitorare l energia"),
    ("Card sicurezza",    "Genera le card YAML Lovelace per sicurezza e presenza"),
    ("Cerca entita",      "Cerca tutte le entita relative a: batteria"),
    ("Suggerimenti",      "Suggerisci miglioramenti alla mia configurazione HA"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _startup()
    yield
    await _shutdown()

app = FastAPI(title="HomeMind", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "27"}

@app.get("/api/status")
async def api_status():
    return JSONResponse({
        "ok": True, "version": "27",
        "entities": len(state_cache),
        "home": home.summary() if home else {},
        "security": security.status() if security else {},
        "ws": ws_client._connected if ws_client else False,
        "ai": AI_PROVIDER + "/" + AI_MODEL,
    })

@app.post("/chat")
async def chat_ep(request: Request):
    body = await request.json()
    msg  = body.get("message","").strip()
    if not msg:
        return JSONResponse({"reply":"(vuoto)", "actions":[]})

    CHAT_HISTORY.append({"role":"user","content":msg})
    if len(CHAT_HISTORY) > 40:
        CHAT_HISTORY[:] = CHAT_HISTORY[-40:]

    # Arricchisci la query con contesto fresco
    ctx    = tools.full_context() if tools else "(tools non pronti)"
    system = _system_prompt(ctx)

    # Gestione comandi speciali senza AI (più veloce)
    quick_reply = _handle_quick(msg)
    if quick_reply:
        CHAT_HISTORY.append({"role":"assistant","content":quick_reply})
        return JSONResponse({"reply": quick_reply, "actions":[]})

    try:
        reply = await ai.ask(system, msg, max_tokens=2000, history=CHAT_HISTORY[:-1])
    except Exception as e:
        logger.error("AI error: %s", e, exc_info=True)
        reply = "Errore AI: " + str(e)

    actions = await _exec_actions(reply)

    # Se ci sono dati GET_HISTORY, fai un secondo giro AI per analizzarli
    history_data = [a for a in actions if a.startswith("📊")]
    if history_data:
        history_ctx = "\n\n".join(history_data)
        followup_msg = (
            f"Hai richiesto i seguenti dati storici da Home Assistant:\n\n"
            f"{history_ctx}\n\n"
            f"Ora analizza questi dati e rispondi alla domanda originale "
            f"dell'utente in modo chiaro e utile. "
            f"Se ci sono pattern interessanti, evidenziali."
        )
        try:
            analysis = await ai.ask(system, followup_msg, max_tokens=1000)
            # Sostituisce la risposta con l'analisi
            actions = [a for a in actions if not a.startswith("📊")]
            actions.insert(0, "📊 " + analysis)
        except Exception as e:
            logger.warning("History analysis AI error: %s", e)

    CHAT_HISTORY.append({"role":"assistant","content":reply})
    return JSONResponse({"reply": reply, "actions": actions})

def _handle_quick(msg: str):
    """Gestisce richieste di card/ricerca senza AI (istantaneo)."""
    ml = msg.lower()
    if not tools:
        return None
    if "card energia" in ml or ("card" in ml and "energ" in ml):
        return "Ecco le card YAML per l'energia:\n\n" + tools.make_energy_dashboard_yaml()
    if "card sicurezza" in ml or "card" in ml and ("sicurezza" in ml or "allarme" in ml):
        return "Ecco le card YAML per la sicurezza:\n\n" + tools.make_security_dashboard_yaml()
    if ("card luci" in ml or "card stanze" in ml or "room lights" in ml or
            ("card" in ml and "luc" in ml and "stanz" in ml)):
        return "Ecco il YAML per la <b>Room Lights Graph Card</b>:\n\n" + tools.make_room_lights_graph_card_yaml()
    if msg.lower().startswith("cerca "):
        q = msg[6:].strip()
        return "Risultati ricerca **" + q + "**:\n```\n" + tools.search(q) + "\n```"
    return None

def _system_prompt(ctx: str) -> str:
    return (
        "Sei HomeMind, assistente AI intelligente per la domotica. "
        "Rispondi SEMPRE in italiano. Sei preciso, utile, conciso ma completo.\n\n"

        + ctx + "\n\n"

        "=== COSA PUOI FARE ===\n"
        "1. CONTROLLARE DISPOSITIVI — usa questi tag (li eseguo io automaticamente):\n"
        "   [CALL_SERVICE:light.turn_on:light.faretti]\n"
        "   [CALL_SERVICE:light.turn_on:light.soggiorno:{\"rgb_color\":[255,0,0]}]\n"
        "   [CALL_SERVICE:light.turn_off:light.cucina]\n"
        "   [CALL_SERVICE:switch.turn_on:switch.presa_1]\n"
        "   [CALL_SERVICE:climate.set_temperature:climate.termostato:{\"temperature\":21}]\n"
        "   [CALL_SERVICE:media_player.turn_on:media_player.tv_soggiorno]\n"
        "   [CALL_SERVICE:media_player.volume_set:media_player.tv:{\"volume_level\":0.5}]\n"
        "   REGOLA: metti SOLO l'entity_id nel terzo campo, mai 'entity_id=xxx'\n"
        "   Per PIÙ luci: genera un [CALL_SERVICE] per ogni luce\n"
        "   Per TUTTE le luci: usa [CALL_SERVICE:light.turn_on:all]\n"
        "   Per COLORI RGB: [CALL_SERVICE:light.turn_on:light.faretti:{\"rgb_color\":[255,0,0]}]\n   Per BIANCO/WHITE (usa SEMPRE color_temp_kelvin, non rgb): [CALL_SERVICE:light.turn_on:light.faretti:{\"color_temp_kelvin\":4000,\"brightness\":255}]\n   Per BIANCO CALDO: color_temp_kelvin 2700 | BIANCO NEUTRO: 4000 | BIANCO FREDDO: 6500\n"
        "   [CALL_SERVICE:alarm_control_panel.alarm_arm_away:alarm_control_panel.home_alarm:{\"code\":\"" + ALARM_CODE + "\"}]\n"
        "   [CALL_SERVICE:alarm_control_panel.alarm_disarm:alarm_control_panel.home_alarm:{\"code\":\"" + ALARM_CODE + "\"}]\n\n"

        "2. STORICO ENTITÀ — OBBLIGATORIO quando l'utente chiede cosa è successo in passato:\n"
        "   ⚠️ NON rispondere mai 'non ho accesso ai dati storici' — USA SEMPRE [GET_HISTORY]!\n"
        "   Formato: [GET_HISTORY:entity_id:ore]\n"
        "   Gli entity_id disponibili sono elencati nel contesto sotto 'ENTITY_ID PER GET_HISTORY'.\n"
        "   Esempi di domande → tag da usare:\n"
        "   'quante volte ha scattato il sensore cucina?' → [GET_HISTORY:binary_sensor.xxx_occupancy:24]\n"
        "   'stato allarme ultimi 2 giorni'              → [GET_HISTORY:alarm_control_panel.xxx:48]\n"
        "   'temperatura ieri'                           → [GET_HISTORY:sensor.temperatura_xxx:24]\n"
        "   'quando è arrivato Agostino?'                → [GET_HISTORY:person.agostino:24]\n"
        "   'porta aperta stamattina?'                   → [GET_HISTORY:binary_sensor.xxx_contact:12]\n"
        "   Puoi usare più [GET_HISTORY] nella stessa risposta.\n"
        "   Dopo aver ricevuto i dati, analizzali e rispondi in modo chiaro.\n\n"

        "3. CREARE AUTOMAZIONI — quando l'utente chiede di creare una automazione:\n"
        "   Genera il YAML completo e usa il tag:\n"
        "   [CREATE_AUTOMATION:yaml_content]\n"
        "   Esempio:\n"
        "   [CREATE_AUTOMATION:alias: Luci tramonto\\ntrigger:\\n  - platform: sun\\n    event: sunset\\naction:\\n  - service: light.turn_on\\n    target:\\n      entity_id: light.soggiorno]\n"
        "   IMPORTANTE: prima mostra all'utente il YAML che hai generato e cosa farà,\n"
        "   poi usa il tag [CREATE_AUTOMATION:...] per crearlo.\n"
        "   Se l'utente dice solo 'crea automazione' senza dettagli, chiedi:\n"
        "   - Trigger (quando deve scattare?)\n"
        "   - Azione (cosa deve fare?)\n"
        "   - Condizioni opzionali\n\n"

        "4. GENERARE YAML LOVELACE — quando ti chiede card, genera YAML pronto da incollare:\n"
        "   Usa ```yaml ... ``` per i blocchi di codice\n"
        "   Card supportate: entities, gauge, glance, history-graph, statistic, alarm-panel\n\n"

        "5. ANALIZZARE — energia, consumi, anomalie, suggerimenti ottimizzazione\n\n"

        "6. SUGGERIRE MIGLIORAMENTI — basandoti sugli stati attuali, suggerisci cosa migliorare\n\n"

        "=== REGOLE ===\n"
        "- sensor.sensori_watt negativo = NORMALE (batteria in scarica)\n"
        "- NON modificare configuration.yaml da solo — genera YAML e chiedi conferma\n"
        "- Per le card Lovelace: genera YAML completo pronto da incollare\n"
        "- Se non trovi un'entità specifica, dillo e suggerisci alternative\n"
        "- Usa markdown: **grassetto**, ### titoli, - liste, ```yaml codice```\n"
        "- Per lo storico: usa [GET_HISTORY] invece di inventare dati\n"
    )

async def _exec_actions(reply: str) -> list:
    done = []
    matches = list(re.finditer(r'\[CALL_SERVICE:([^.]+)\.([^:]+):([^\]:]+)(?::(.*))?  \]', reply))
    # Fix regex: allow no-space
    if not matches:
        matches = list(re.finditer(r'\[CALL_SERVICE:([^.]+)\.([^:]+):([^\]:]+)(?::(.*?))?\]', reply))
    if not matches:
        logger.debug("_exec_actions: nessun CALL_SERVICE trovato nella risposta AI")

    def _friendly(eid: str) -> str:
        """Ritorna il nome leggibile dell'entità o l'eid se non trovato."""
        s = state_cache.get(eid, {})
        return s.get("attributes", {}).get("friendly_name", eid)

    for m in matches:
        domain, service, entity = m.group(1), m.group(2), m.group(3).strip()

        # Fix: l'AI a volte genera "entity_id=light.xxx" invece di "light.xxx"
        if entity.startswith("entity_id="):
            entity = entity[len("entity_id="):]

        data = {}
        if m.group(4):
            try: data = json.loads(m.group(4))
            except Exception: pass

        # Fix: "all" non è accettato da HA — espandi nella lista reale del dominio
        if entity.lower() in ("all", "light.all", "switch.all"):
            # Escludi luci virtuali (cast screen, chromecast) e switch non fisici
            EXCLUDE_ALL_KW = (
                "_screen", "cast_screen", "chromecast", "google_cast",
                "fire_tv", "samsung_soundbar",
                "schedule_", "lavastoviglie", "proxmox", "inverter_pipsolar",
                "lc_autofocus", "lc_lampada", "lc_tergicristallo",
                "echo", "alexa", "permit_join",
            )
            entities = [
                eid for eid in state_cache
                if eid.startswith(domain + ".")
                and state_cache[eid].get("state") not in ("unavailable", "unknown")
                and not any(kw in eid.lower() for kw in EXCLUDE_ALL_KW)
            ]
            if not entities:
                done.append("FAIL nessuna entità trovata per dominio " + domain)
                continue
            logger.info("AI action: %s.%s → ALL (%d entità)", domain, service, len(entities))
            names = []
            for eid in entities:
                try:
                    await rest_client.call_service(domain, service, data,
                                                   target={"entity_id": eid})
                    names.append(_friendly(eid))
                except Exception as e:
                    done.append("FAIL " + eid + ": " + str(e)[:40])
            if names:
                verb = "accese" if service == "turn_on" else "spente"
                done.append(str(len(names)) + " luci " + verb + ": " + ", ".join(names))
            continue

        # Verifica entity_id in state_cache — se non trovato, cerca per nome simile
        if entity not in state_cache and entity.lower() not in ("all", f"{domain}.all"):
            keyword = entity.split(".")[-1].lower()  # es: "bagno" da "light.bagno"
            candidates = [
                eid for eid in state_cache
                if eid.startswith(domain + ".")
                and keyword in eid.lower()
                and state_cache[eid].get("state") not in ("unavailable", "unknown")
            ]
            if candidates:
                old_entity = entity
                entity = candidates[0]
                logger.info("AI action: '%s' non trovata → match fuzzy '%s'", old_entity, entity)
            else:
                logger.warning("AI action: entity '%s' non in state_cache, nessun fuzzy match per '%s'", entity, keyword)
                done.append(f"⚠️ Entità <code>{entity}</code> non trovata")
                continue

        # ── Adatta i parametri colore in base a supported_color_modes ──────────
        if domain == "light" and service == "turn_on" and data:
            attrs = state_cache.get(entity, {}).get("attributes", {})
            supported = attrs.get("supported_color_modes", [])
            # Se la luce NON supporta RGB/hs/xy → strip rgb_color / color_name
            has_color = any(m in supported for m in ("rgb", "rgbw", "rgbww", "hs", "xy", "color_temp"))
            if "rgb_color" in data and "rgb" not in " ".join(supported) and "hs" not in supported:
                rgb = data.pop("rgb_color")
                # Converti in color_temp_kelvin se supportato
                if "color_temp" in supported or "color_temp_kelvin" in supported:
                    is_white = (rgb[0] > 200 and rgb[1] > 200 and rgb[2] > 200)
                    is_warm  = (rgb[0] > 200 and rgb[1] < 150 and rgb[2] < 100)   # giallo/arancio
                    if is_white:
                        data.setdefault("color_temp_kelvin", 4000)
                        logger.info("AI action: rgb→color_temp 4000K (luce CT-only): %s", entity)
                    elif is_warm:
                        data.setdefault("color_temp_kelvin", 2700)
                        logger.info("AI action: rgb→color_temp 2700K warm (luce CT-only): %s", entity)
                    else:
                        # Colore reale (rosso, blu, verde...) non supportato → accendi senza colore
                        done.append(f"⚠️ {_friendly(entity)}: questa luce non supporta colori RGB. La accendo in bianco.")
                        data.setdefault("color_temp_kelvin", 4000)
                        logger.warning("AI action: luce CT-only '%s' non supporta RGB, accendo bianco", entity)
            # Strip color_name se non supportato
            if "color_name" in data and not has_color:
                data.pop("color_name")
                logger.info("AI action: color_name rimosso (luce CT-only): %s", entity)

        try:
            await rest_client.call_service(domain, service, data,
                                           target={"entity_id": entity})
            name = _friendly(entity)
            if service == "turn_on":
                extra = ""
                if data.get("rgb_color"):
                    extra = " 🎨"
                elif data.get("color_temp_kelvin"):
                    k = data["color_temp_kelvin"]
                    extra = " ⚪" if k >= 5000 else (" 🟡" if k <= 3000 else " 🔵")
                done.append("✅ " + name + " accesa" + extra)
            elif service == "turn_off":
                done.append("✅ " + name + " spenta")
            else:
                done.append("✅ " + name + " → " + service)
            logger.info("AI action: %s.%s → %s (%s) data=%s", domain, service, entity, name, data)
        except Exception as e:
            err_str = str(e)
            if "400" in err_str and domain == "light":
                # Ultimo tentativo: manda turn_on senza parametri colore
                try:
                    await rest_client.call_service(domain, service, {},
                                                   target={"entity_id": entity})
                    name = _friendly(entity)
                    done.append("✅ " + name + " accesa (parametri colore non supportati)")
                    logger.warning("AI action: retry senza colore per %s", entity)
                except Exception as e2:
                    done.append("FAIL " + str(e2)[:50])
            else:
                done.append("FAIL " + err_str[:50])

    # ── GET_HISTORY ───────────────────────────────────────────────────────────
    for m in re.finditer(r'\[GET_HISTORY:([^\]:]+):(\d+)\]', reply):
        eid  = m.group(1).strip()
        hours = int(m.group(2))
        try:
            history = await rest_client.get_history([eid], hours=hours)
            entries = history.get(eid, [])
            if not entries:
                done.append(f"📊 Storico {eid}: nessun dato nelle ultime {hours}h")
            else:
                # Riassumi: mostra cambiamenti di stato (no duplicati consecutivi)
                name = state_cache.get(eid, {}).get("attributes", {}).get("friendly_name", eid)
                lines = [f"📊 **Storico {name}** (ultime {hours}h — {len(entries)} letture):"]
                prev = None
                shown = 0
                for entry in entries:
                    st = entry.get("state", "")
                    if st in ("unavailable", "unknown"):
                        continue
                    ts_raw = entry.get("last_changed", "")
                    try:
                        from utils.timezone_helper import local_tz
                        ts_dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                        ts = ts_dt.astimezone(local_tz()).strftime("%d/%m %H:%M")
                    except Exception:
                        ts = ts_raw[:16].replace("T", " ")
                    if st != prev:
                        unit = entry.get("attributes", {}).get("unit_of_measurement", "")
                        lines.append(f"  {ts} → **{st}**{' ' + unit if unit else ''}")
                        prev = st
                        shown += 1
                    if shown >= 30:  # max 30 cambiamenti mostrati
                        lines.append(f"  ... (troncato, {len(entries)} letture totali)")
                        break
                done.append("\n".join(lines))
                logger.info("GET_HISTORY %s: %d entries → %d cambiamenti", eid, len(entries), shown)
        except Exception as e:
            done.append(f"FAIL GET_HISTORY {eid}: {str(e)[:60]}")

    # ── CREATE_AUTOMATION ─────────────────────────────────────────────────────
    for m in re.finditer(r'\[CREATE_AUTOMATION:(.*?)\]', reply, re.DOTALL):
        yaml_raw = m.group(1).strip()
        # L'AI potrebbe usare \n letterali — convertiamo
        yaml_content = yaml_raw.replace("\\n", "\n")
        try:
            result = await rest_client.create_automation(yaml_content)
            if result.get("ok"):
                auto_id = result.get("id", "?")
                done.append(f"✅ **Automazione creata!** ID: `{auto_id}`\n"
                            f"Trovala in HA → Impostazioni → Automazioni")
                logger.info("CREATE_AUTOMATION OK: %s", auto_id)
            else:
                err = result.get("error", "errore sconosciuto")
                done.append(f"❌ **Errore creazione automazione:** {err}")
                logger.warning("CREATE_AUTOMATION FAIL: %s", err)
        except Exception as e:
            done.append(f"FAIL CREATE_AUTOMATION: {str(e)[:80]}")

    return done


async def _exec_actions_list(actions: list) -> list:
    """Esegue azioni da lista di dict {domain, service, entity_id}.
    Usato dal fallback AI in telegram_bot."""
    done = []
    for a in actions:
        domain  = a.get("domain", "")
        service = a.get("service", "")
        entity  = a.get("entity_id", "")
        if not domain or not service or not entity:
            continue
        # Espandi "all"
        if entity.lower() in ("all", f"{domain}.all"):
            entities = [eid for eid in state_cache if eid.startswith(domain + ".")]
        else:
            entities = [entity]
        for eid in entities:
            try:
                await rest_client.call_service(domain, service, {}, target={"entity_id": eid})
                name = state_cache.get(eid, {}).get("attributes", {}).get("friendly_name", eid)
                done.append(f"✅ {name}")
                logger.info("action_list: %s.%s → %s", domain, service, eid)
            except Exception as e:
                done.append(f"FAIL {eid}: {str(e)[:40]}")
    return done

@app.get("/dashboard", response_class=HTMLResponse)
async def live_dashboard_page():
    """Pagina placeholder — la dashboard è stata sostituita da /crea_card su Telegram."""
    n_ent   = len(state_cache)
    n_light = sum(1 for e in state_cache if e.startswith("light."))
    n_light_on = sum(1 for e,s in state_cache.items() if e.startswith("light.") and s.get("state")=="on")
    n_motion = sum(1 for e in state_cache if e.endswith("_occupancy"))
    n_contact = sum(1 for e in state_cache if e.endswith("_contact"))
    alarm_st = next((s.get("state","?") for e,s in state_cache.items() if e.startswith("alarm_control_panel.")), "n/d")
    persons  = [s.get("attributes",{}).get("friendly_name",e) for e,s in state_cache.items()
                if e.startswith("person.") and s.get("state")=="home"]
    return HTMLResponse(f"""<!DOCTYPE html><html lang="it">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HomeMind</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',sans-serif;background:#0f1117;color:#e2e8f0;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px}}
.card{{background:#1e2130;border-radius:16px;padding:28px;max-width:420px;width:100%;box-shadow:0 8px 32px rgba(0,0,0,.4)}}
h1{{font-size:1.5rem;font-weight:700;margin-bottom:4px;color:#fff}}
.sub{{color:#64748b;font-size:.85rem;margin-bottom:24px}}
.stat{{display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #2d3148}}
.stat:last-of-type{{border-bottom:none}}
.icon{{font-size:1.5rem;width:36px;text-align:center}}
.label{{flex:1;font-size:.9rem;color:#94a3b8}}
.value{{font-weight:600;color:#e2e8f0}}
.tip{{margin-top:20px;background:#12151f;border-radius:12px;padding:16px;font-size:.82rem;color:#64748b;line-height:1.6}}
.tip code{{background:#1e2130;padding:2px 6px;border-radius:4px;color:#7dd3fc;font-size:.8rem}}
.alarm-ok{{color:#4ade80}}.alarm-no{{color:#f87171}}
</style></head>
<body><div class="card">
<h1>🏠 HomeMind</h1>
<div class="sub">{n_ent} entità monitorate</div>
<div class="stat"><span class="icon">💡</span><span class="label">Luci</span><span class="value">{n_light_on}/{n_light} accese</span></div>
<div class="stat"><span class="icon">🔒</span><span class="label">Allarme</span><span class="value {'alarm-ok' if alarm_st=='disarmed' else 'alarm-no'}">{alarm_st}</span></div>
<div class="stat"><span class="icon">🚶</span><span class="label">Sensori presenza</span><span class="value">{n_motion}</span></div>
<div class="stat"><span class="icon">🚪</span><span class="label">Sensori contatto</span><span class="value">{n_contact}</span></div>
<div class="stat"><span class="icon">👤</span><span class="label">In casa</span><span class="value">{', '.join(persons) or 'nessuno'}</span></div>
<div class="tip">💡 Per creare card Lovelace su Telegram:<br><code>crea card:</code><br>poi incolla il tuo YAML base</div>
</div></body></html>""")


@app.post("/api/states_batch")
async def states_batch(request: Request):
    """Restituisce stati multipli dal cache locale — usato dalla dashboard per polling live."""
    from fastapi.responses import JSONResponse
    try:
        body = await request.json()
        entity_ids = body.get("entity_ids", [])
        result = []
        for eid in entity_ids:
            s = state_cache.get(eid)
            if s:
                result.append({
                    "entity_id": eid,
                    "state": s.get("state", "unavailable"),
                    "attributes": s.get("attributes", {}),
                })
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/briefing", response_class=HTMLResponse)
async def trigger_briefing():
    """Manda subito il morning briefing Telegram (debug/test)."""
    if morning_briefing:
        try:
            txt = await morning_briefing.send_briefing()
            return HTMLResponse(
                f"<pre style='font-family:monospace;padding:1rem'>{txt}</pre>"
            )
        except Exception as e:
            return HTMLResponse(f"<h2>Errore: {e}</h2>", status_code=500)
    return HTMLResponse("<h2>MorningBriefing non inizializzato</h2>", status_code=503)


@app.get("/repairs", response_class=HTMLResponse)
async def repairs_page():
    """Pagina repairs HA."""
    if repairs_checker:
        summary = await repairs_checker.get_repairs_summary()
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;padding:2rem'>"
            f"<pre>{summary}</pre></body></html>"
        )
    return HTMLResponse("<h2>Repairs checker non disponibile</h2>")


@app.get("/providers", response_class=HTMLResponse)
async def providers_page():
    cfg_path = Path("/config/homemind_patches/person_config.json")
    try:
        cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    except Exception:
        cfg = {}

    enabled_list = cfg.get("ai_providers", [])
    if not enabled_list and AI_PROVIDER:
        enabled_list = [{"name": AI_PROVIDER, "model": AI_MODEL, "api_key": AI_API_KEY}]

    ALL_PROVIDERS = [
        {"name":"gemini",     "label":"Google Gemini",   "icon":"🟦", "free":True,  "default_model":"gemini-2.0-flash",                      "url":"https://aistudio.google.com",   "quota":"1.000 req/giorno"},
        {"name":"groq",       "label":"Groq / Llama",    "icon":"⚡",  "free":True,  "default_model":"llama-3.3-70b-versatile",               "url":"https://console.groq.com",      "quota":"14.400 req/giorno"},
        {"name":"openrouter", "label":"OpenRouter",      "icon":"🔀",  "free":True,  "default_model":"meta-llama/llama-3.3-70b-instruct:free","url":"https://openrouter.ai",         "quota":"Modelli free illimitati"},
        {"name":"claude",     "label":"Anthropic Claude","icon":"🟠",  "free":False, "default_model":"claude-3-5-haiku-20241022",             "url":"https://console.anthropic.com", "quota":"A pagamento"},
        {"name":"openai",     "label":"OpenAI GPT",      "icon":"🟢",  "free":False, "default_model":"gpt-4o-mini",                          "url":"https://platform.openai.com",   "quota":"A pagamento"},
        {"name":"mistral",    "label":"Mistral AI",      "icon":"🌊",  "free":False, "default_model":"mistral-small-latest",                 "url":"https://console.mistral.ai",    "quota":"Trial gratuito"},
        {"name":"xai",        "label":"xAI Grok",        "icon":"❌",  "free":False, "default_model":"grok-beta",                            "url":"https://console.x.ai",          "quota":"$25 crediti"},
        {"name":"deepseek",   "label":"DeepSeek",        "icon":"🔵",  "free":False, "default_model":"deepseek-chat",                        "url":"https://platform.deepseek.com", "quota":"Molto economico"},
    ]

    enabled_map = {p["name"]: p for p in enabled_list}

    cards_html = ""
    for ap in ALL_PROVIDERS:
        n    = ap["name"]
        en   = n in enabled_map
        ep   = enabled_map.get(n, {})
        model = ep.get("model", ap["default_model"])
        key   = ep.get("api_key", "")
        chk   = "checked" if en else ""
        order_idx  = next((i+1 for i,p in enumerate(enabled_list) if p.get("name")==n), None)
        order_badge = f'<span class="pv-order">{order_idx}\u00b0</span>' if order_idx else ""
        free_badge  = '<span class="pv-free">GRATIS</span>' if ap["free"] else ""
        expand_cls  = "pv-details open" if en else "pv-details"
        active_cls  = "pv-card active" if en else "pv-card"
        cards_html += (
            f'<div class="{active_cls}" id="card-{n}">'
            f'<div class="pv-row">'
            f'<span class="pv-icon">{ap["icon"]}</span>'
            f'<div class="pv-info"><span class="pv-name">{ap["label"]}</span>'
            f'<span class="pv-sub">{free_badge} {ap["quota"]}</span></div>'
            f'{order_badge}'
            f'<label class="pv-toggle"><input type="checkbox" id="chk-{n}" {chk} onchange="pvToggle(\'{n}\',this.checked)">'
            f'<span class="pv-slider"></span></label>'
            f'</div>'
            f'<div class="{expand_cls}" id="det-{n}">'
            f'<div class="pv-field"><label>Modello</label>'
            f'<input type="text" id="mdl-{n}" value="{model}" placeholder="{ap["default_model"]}"></div>'
            f'<div class="pv-field">'
            f'<label>API Key &nbsp;<a href="{ap["url"]}" target="_blank" class="pv-link">\u2192 Ottieni key</a></label>'
            f'<div class="pv-keyrow">'
            f'<input type="password" id="key-{n}" value="{key}" placeholder="Incolla qui la tua API key" autocomplete="off">'
            f'<button class="pv-eye" onclick="pvEye(\'{n}\')">&#128065;</button>'
            f'<button class="pv-tbtn" id="tbtn-{n}" onclick="pvTest(\'{n}\')">Test</button>'
            f'</div>'
            f'<span class="pv-testresult" id="tres-{n}"></span>'
            f'</div></div></div>'
        )

    enabled_js = json.dumps(enabled_list)
    all_js     = json.dumps([{"name": p["name"], "default_model": p["default_model"]} for p in ALL_PROVIDERS])

    css = (
        "<style>"
        ".pv-wrap{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:.8rem;color:#e2e8f0;max-width:560px}"
        ".pv-title{font-size:1rem;font-weight:700;color:#7dd3fc;margin-bottom:.25rem}"
        ".pv-subtitle{font-size:.74rem;color:#64748b;margin-bottom:.8rem;line-height:1.45}"
        ".pv-card{background:#1e293b;border-radius:10px;padding:.7rem .9rem;margin-bottom:.5rem;border:1px solid #334155;transition:border-color .2s}"
        ".pv-card.active{border-color:#3b82f6}"
        ".pv-row{display:flex;align-items:center;gap:.55rem}"
        ".pv-icon{font-size:1.2rem;flex-shrink:0;width:1.5rem;text-align:center}"
        ".pv-info{flex:1;min-width:0}"
        ".pv-name{font-size:.87rem;font-weight:600;display:block}"
        ".pv-sub{font-size:.71rem;color:#64748b;display:block;margin-top:1px}"
        ".pv-free{background:#064e3b;color:#6ee7b7;border-radius:3px;padding:1px 5px;font-size:.64rem;font-weight:700;margin-right:3px}"
        ".pv-order{background:#1d4ed8;color:#bfdbfe;border-radius:99px;padding:1px 8px;font-size:.71rem;font-weight:700;flex-shrink:0}"
        ".pv-toggle{position:relative;display:inline-block;width:40px;height:22px;flex-shrink:0}"
        ".pv-toggle input{opacity:0;width:0;height:0;position:absolute}"
        ".pv-slider{position:absolute;inset:0;background:#334155;border-radius:99px;cursor:pointer;transition:.25s}"
        ".pv-slider:before{content:'';position:absolute;width:16px;height:16px;left:3px;top:3px;background:#94a3b8;border-radius:50%;transition:.25s}"
        ".pv-toggle input:checked+.pv-slider{background:#2563eb}"
        ".pv-toggle input:checked+.pv-slider:before{transform:translateX(18px);background:#fff}"
        ".pv-details{max-height:0;overflow:hidden;transition:max-height .3s ease,padding .3s;padding:0}"
        ".pv-details.open{max-height:220px;padding:.6rem 0 .1rem 1.8rem}"
        ".pv-field{margin-bottom:.5rem}"
        ".pv-field label{font-size:.71rem;color:#94a3b8;display:block;margin-bottom:.22rem}"
        ".pv-field input{background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:.32rem .55rem;width:100%;font-size:.81rem;box-sizing:border-box}"
        ".pv-field input:focus{outline:none;border-color:#3b82f6}"
        ".pv-keyrow{display:flex;gap:5px;align-items:center}"
        ".pv-keyrow input{flex:1}"
        ".pv-eye,.pv-tbtn{background:#334155;border:none;border-radius:5px;color:#94a3b8;padding:.28rem .5rem;cursor:pointer;font-size:.78rem;flex-shrink:0}"
        ".pv-tbtn{background:#1d4ed8;color:#fff;padding:.28rem .65rem}"
        ".pv-tbtn:disabled{background:#334155;color:#64748b;cursor:not-allowed}"
        ".pv-testresult{font-size:.71rem;margin-top:.22rem;display:block;min-height:.85rem}"
        ".pv-ok{color:#4ade80}.pv-fail{color:#f87171}.pv-wait{color:#fbbf24}"
        ".pv-link{color:#7dd3fc;font-size:.69rem;text-decoration:none}"
        ".pv-link:hover{text-decoration:underline}"
        ".pv-savebtn{background:#7c3aed;border:none;border-radius:8px;color:#fff;padding:.55rem 1.2rem;font-size:.87rem;font-weight:700;width:100%;margin-top:.7rem;cursor:pointer}"
        ".pv-savebtn:hover{background:#8b5cf6}"
        ".pv-savemsg{text-align:center;font-size:.81rem;margin-top:.4rem;min-height:1rem}"
        ".pv-active-bar{background:#1e3a5f;border:1px solid #1d4ed8;border-radius:8px;padding:.4rem .75rem;margin-bottom:.7rem;font-size:.77rem}"
        ".pv-section{font-size:.69rem;color:#475569;margin:.4rem 0 .3rem;text-transform:uppercase;letter-spacing:.05em;font-weight:600}"
        "</style>"
    )

    js = (
        "<script>"
        "(function(){"
        f"var allDef={all_js};"
        "function getDefModel(n){var f=allDef.filter(function(x){return x.name===n;});return f.length?f[0].default_model:'';}"
        "window.pvToggle=function(n,on){"
        "  var det=document.getElementById('det-'+n);"
        "  var card=document.getElementById('card-'+n);"
        "  det.classList.toggle('open',on);"
        "  card.classList.toggle('active',on);"
        "  if(on){var m=document.getElementById('mdl-'+n);if(!m.value)m.value=getDefModel(n);}"
        "  pvUpdateOrder();"
        "};"
        "window.pvEye=function(n){var i=document.getElementById('key-'+n);i.type=i.type==='password'?'text':'password';};"
        "window.pvTest=async function(n){"
        "  var tres=document.getElementById('tres-'+n);"
        "  var btn=document.getElementById('tbtn-'+n);"
        "  tres.textContent='\u23f3 Test in corso...';tres.className='pv-testresult pv-wait';btn.disabled=true;"
        "  var d={name:n,model:document.getElementById('mdl-'+n).value,api_key:document.getElementById('key-'+n).value};"
        "  try{"
        "    var r=await fetch('/api/providers/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});"
        "    var res=await r.json();"
        "    if(res.ok){tres.textContent='\u2705 Connesso \u2014 risposta: '+res.response;tres.className='pv-testresult pv-ok';}"
        "    else{tres.textContent='\u274c '+res.error;tres.className='pv-testresult pv-fail';}"
        "  }catch(e){tres.textContent='\u274c '+String(e);tres.className='pv-testresult pv-fail';}"
        "  btn.disabled=false;"
        "};"
        "function pvGetList(){return Array.from(document.querySelectorAll('.pv-card')).filter(function(c){var n=c.id.replace('card-','');return document.getElementById('chk-'+n).checked;}).map(function(c){var n=c.id.replace('card-','');return{name:n,model:document.getElementById('mdl-'+n).value,api_key:document.getElementById('key-'+n).value};});}"
        "function pvUpdateOrder(){var ord=1;document.querySelectorAll('.pv-card').forEach(function(c){var n=c.id.replace('card-','');var badge=c.querySelector('.pv-order');if(document.getElementById('chk-'+n).checked){if(!badge){badge=document.createElement('span');badge.className='pv-order';c.querySelector('.pv-row').insertBefore(badge,c.querySelector('.pv-toggle'));}badge.textContent=ord+'\u00b0';ord++;}else{if(badge)badge.remove();}});}"
        "window.pvSave=async function(){"
        "  var msg=document.getElementById('pv-savemsg');"
        "  msg.style.color='#94a3b8';msg.textContent='Salvataggio...';"
        "  try{"
        "    var r=await fetch('/api/providers/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({providers:pvGetList()})});"
        "    var res=await r.json();"
        "    if(res.ok){msg.style.color='#4ade80';msg.textContent='\u2705 Salvato! Riavvia HomeMind per applicare.';}"
        "    else{msg.style.color='#f87171';msg.textContent='\u274c '+(res.error||'Errore');}"
        "  }catch(e){msg.style.color='#f87171';msg.textContent='\u274c '+String(e);}"
        "};"
        "(async function(){"
        "  try{"
        "    var r=await fetch('/api/providers/status');var d=await r.json();"
        "    var bar=document.getElementById('pv-activebar');"
        "    if(d.providers&&d.providers.length){"
        "      var M=['\U0001f947','\U0001f948','\U0001f949'];"
        "      bar.innerHTML='<b>Attivi ora:</b> '+d.providers.map(function(p,i){"
        "        return (M[i]||'')+' <b>'+p.name+'</b> <span style=\"color:#94a3b8\">\u2014 '+p.model+'</span>';"
        "      }).join(' \u2192 ');"
        "    }else{bar.textContent='Nessun provider attivo';}"
        "  }catch(e){}"
        "})();"
        "pvUpdateOrder();"
        "})();"
        "</script>"
    )

    body = (
        css
        + "<div class='pv-wrap'>"
        + "<div class='pv-title'>&#129302; AI Providers</div>"
        + "<div class='pv-subtitle'>Attiva i provider nell'ordine che preferisci. Se il primo non &egrave; disponibile, HomeMind usa automaticamente il successivo.</div>"
        + "<div class='pv-active-bar' id='pv-activebar'>&#8987; Caricamento...</div>"
        + "<div class='pv-section'>Provider disponibili</div>"
        + cards_html
        + "<button class='pv-savebtn' onclick='pvSave()'>&#128190; Salva configurazione</button>"
        + "<div class='pv-savemsg' id='pv-savemsg'></div>"
        + "</div>"
        + js
    )
    return HTMLResponse(body)


@app.get("/api/providers/status")
async def providers_status():
    plist = []
    if ai:
        for p in ai._providers:
            plist.append({"name": p.name, "model": p.model, "display": p.display})
    return JSONResponse({"providers": plist})


@app.post("/api/providers/test")
async def providers_test(request: Request):
    from agent.ai_provider import _SingleProvider
    body = await request.json()
    name    = body.get("name", "")
    model   = body.get("model", "")
    api_key = body.get("api_key", "")
    if not name or not api_key:
        return JSONResponse({"ok": False, "error": "name e api_key obbligatori"})
    try:
        p = _SingleProvider(name=name, model=model, api_key=api_key)
        reply = await p.ask(
            system="You are a test assistant. Reply with exactly: OK",
            user="Say OK",
            max_tokens=10,
        )
        return JSONResponse({"ok": True, "response": reply.strip()[:50]})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)[:200]})


@app.post("/api/providers/save")
async def providers_save(request: Request):
    cfg_path = Path("/config/homemind_patches/person_config.json")
    body = await request.json()
    new_providers = body.get("providers", [])
    try:
        cfg = {}
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
        cfg["ai_providers"] = new_providers
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)[:200]})


@app.get("/spazzatura", response_class=HTMLResponse)
async def spazzatura_page():
    """Pagina web per gestire il calendario spazzatura."""
    cal_info = ""
    if spazzatura and spazzatura.calendar:
        total = len(spazzatura.calendar)
        upcoming = spazzatura.get_next_days(7)
        rows = ""
        for date_str, items in upcoming.items():
            from datetime import datetime as _dt
            d = _dt.strptime(date_str, "%Y-%m-%d")
            day_name = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"][d.weekday()]
            rows += f"<tr><td>{day_name} {d.strftime('%d/%m')}</td><td>{', '.join(items)}</td></tr>"
        cal_info = f"""
        <div class="card ok">
            <h3>✅ Calendario attivo — {total} date</h3>
            <table><tr><th>Giorno</th><th>Raccolta</th></tr>{rows}</table>
        </div>"""
    else:
        cal_info = '<div class="card warn"><h3>⚠️ Nessun calendario caricato</h3></div>'

    return """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HomeMind — Spazzatura</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}
h1{color:#38bdf8;margin-bottom:20px}
h2{color:#94a3b8;font-size:1rem;margin-bottom:16px}
.card{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px}
.card.ok{border-left:4px solid #22c55e}
.card.warn{border-left:4px solid #f59e0b}
.card.info{border-left:4px solid #38bdf8}
h3{margin-bottom:12px;font-size:1rem}
table{width:100%;border-collapse:collapse;font-size:0.9rem}
th{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}
td{padding:8px 0;border-bottom:1px solid #1e293b}
label{display:block;color:#94a3b8;font-size:0.85rem;margin-bottom:8px}
input[type=file]{width:100%;padding:10px;background:#0f172a;border:1px dashed #334155;border-radius:8px;color:#e2e8f0;margin-bottom:12px;cursor:pointer}
button{background:#38bdf8;color:#0f172a;border:none;padding:10px 20px;border-radius:8px;font-weight:700;cursor:pointer;font-size:0.9rem}
button:hover{background:#7dd3fc}
.msg{padding:10px 14px;border-radius:8px;margin-top:12px;display:none}
.msg.ok{background:#14532d;color:#86efac}
.msg.err{background:#450a0a;color:#fca5a5}
a{color:#38bdf8;text-decoration:none;font-size:0.85rem}
</style>
</head><body>
<h1>🗑️ HomeMind — Calendario Spazzatura</h1>
""" + cal_info + """
<div class="card info">
    <h3>📤 Carica il tuo calendario</h3>
    <p style="color:#64748b;font-size:0.85rem;margin-bottom:16px">
        Carica un file JSON con il tuo calendario personalizzato.<br>
        Formato: <code style="color:#38bdf8">{"2026-03-07": ["Plastica"], "2026-03-09": ["Organico"]}</code>
    </p>
    <label>Seleziona file JSON calendario:</label>
    <input type="file" id="jsonFile" accept=".json">
    <button onclick="uploadJson()">Carica JSON</button>
    <div class="msg" id="jsonMsg"></div>
</div>

<div class="card" style="border-left:4px solid #8b5cf6">
    <h3>📝 Incolla il calendario JSON</h3>
    <p style="color:#64748b;font-size:0.85rem;margin-bottom:12px">
        Oppure incolla direttamente il JSON qui sotto:
    </p>
    <textarea id="jsonText" rows="8" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#e2e8f0;padding:10px;font-family:monospace;font-size:0.8rem" placeholder='{"2026-03-07":["Plastica e Metalli"],"2026-03-09":["Organico + Pannolini"]}'></textarea>
    <button onclick="uploadText()" style="margin-top:8px">Salva calendario</button>
    <div class="msg" id="textMsg"></div>
</div>

<p style="color:#475569;font-size:0.8rem;margin-top:8px">
    <a href="/">← Torna alla chat</a> &nbsp;|&nbsp;
    Dopo il caricamento scrivi <strong>/ricarica_spazzatura</strong> su Telegram
</p>

<script>
// Legge file come ArrayBuffer e decodifica manualmente strippando il BOM UTF-8 (EF BB BF)
// Funziona anche nei browser embedded di HA Ingress che non strippano il BOM automaticamente
function readFileStripped(file) {
    return new Promise(function(resolve, reject) {
        var reader = new FileReader();
        reader.onload = function(e) {
            var buf = new Uint8Array(e.target.result);
            // Strippa BOM UTF-8: EF BB BF
            var start = 0;
            if (buf.length >= 3 && buf[0] === 0xEF && buf[1] === 0xBB && buf[2] === 0xBF) {
                start = 3;
            }
            var text = new TextDecoder('utf-8').decode(buf.slice(start));
            resolve(text.trim());
        };
        reader.onerror = reject;
        reader.readAsArrayBuffer(file);
    });
}

async function uploadJson() {
    var f = document.getElementById('jsonFile').files[0];
    var msg = document.getElementById('jsonMsg');
    if (!f) { showMsg(msg, 'Seleziona un file prima', 'err'); return; }
    try {
        var text = await readFileStripped(f);
        await sendJson(text, msg);
    } catch(e) {
        showMsg(msg, '❌ Errore lettura file: ' + e, 'err');
    }
}

async function uploadText() {
    var text = document.getElementById('jsonText').value.trim();
    var msg = document.getElementById('textMsg');
    if (!text) { showMsg(msg, 'Incolla il JSON prima', 'err'); return; }
    // Strippa BOM anche dal testo incollato
    if (text.charCodeAt(0) === 0xFEFF) { text = text.slice(1); }
    await sendJson(text, msg);
}

async function sendJson(text, msg) {
    // Validazione JSON lato client
    var cal;
    try {
        cal = JSON.parse(text);
    } catch(e) {
        showMsg(msg, '❌ JSON non valido: ' + e.message, 'err');
        return;
    }
    if (typeof cal !== 'object' || Array.isArray(cal) || Object.keys(cal).length === 0) {
        showMsg(msg, '❌ Formato errato: serve un oggetto {"YYYY-MM-DD": [...]}', 'err');
        return;
    }
    showMsg(msg, '⏳ Caricamento in corso...', 'ok');
    try {
        var r = await fetch('spazzatura/upload', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({data: text})
        });
        var j = await r.json();
        if (j.ok) {
            showMsg(msg, '✅ ' + j.message, 'ok');
            setTimeout(function(){ location.reload(); }, 1500);
        } else {
            showMsg(msg, '❌ ' + j.error, 'err');
        }
    } catch(e) {
        showMsg(msg, '❌ Errore connessione: ' + e.message, 'err');
    }
}

function showMsg(el, text, cls) {
    el.textContent = text; el.className = 'msg ' + cls; el.style.display = 'block';
}
</script>
</body></html>"""

@app.post("/spazzatura/upload")
async def spazzatura_upload(request: Request):
    """Riceve il JSON del calendario e lo salva + ricarica.
    
    BUG FIX 2: salva in /config/homemind_patches/ (path primario)
    invece di /data/ (che non veniva trovato all'avvio successivo).
    """
    try:
        body = await request.json()
        data = body.get("data", "")
        if not data:
            return JSONResponse({"ok": False, "error": "Nessun dato ricevuto"})

        # Strip BOM UTF-8 in tutte le varianti possibili
        # \xef\xbb\xbf = BOM come bytes, \ufeff = BOM come char unicode
        if isinstance(data, bytes):
            if data[:3] == b'\xef\xbb\xbf':
                data = data[3:]
            data = data.decode('utf-8-sig', errors='replace')
        else:
            # Stringa: strippa BOM unicode e qualsiasi whitespace iniziale
            data = data.lstrip('\ufeff\u200b\r\n \t').rstrip()

        # Valida JSON
        try:
            cal = json.loads(data)
        except json.JSONDecodeError as e:
            # Log raw per debug
            logger.warning("Upload JSON decode error: %s | primi 20 chars (hex): %s",
                           e, data[:20].encode('utf-8').hex() if data else 'vuoto')
            return JSONResponse({"ok": False, "error": f"JSON non valido: {e}"})

        if not isinstance(cal, dict) or not cal:
            return JSONResponse({"ok": False, "error": "JSON vuoto o formato errato (atteso oggetto con date)"})

        # Salva nel path primario letto all'avvio
        from spazzatura import CAL_PATH
        CAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CAL_PATH, "w") as f:
            json.dump(cal, f, indent=2, ensure_ascii=False)

        # Backup in /data/
        save_data = Path("/data/spazzatura_calendario.json")
        save_data.parent.mkdir(parents=True, exist_ok=True)
        with open(save_data, "w") as f:
            json.dump(cal, f, indent=2, ensure_ascii=False)

        # Carica immediatamente in memoria
        if spazzatura:
            spazzatura.calendar = cal
            logger.info("Calendario aggiornato via web UI: %d date salvate in %s", len(cal), CAL_PATH)

        return JSONResponse({"ok": True, "message": f"Calendario caricato: {len(cal)} date"})
    except Exception as e:
        logger.error("Errore upload calendario: %s", e, exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)})

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    sec    = security.status() if security else {}
    alst   = sec.get("alarm_state","unknown")
    home_  = sec.get("who_is_home",[])
    motn   = len(sec.get("motion_active",[]))
    has_p  = home.summary().get("has_persons", False) if home else False

    acls = "alarm" if alst in ("triggered","arming","pending") else \
           "ok"    if alst == "disarmed" else "warn"
    albl = {"disarmed":"Disarmato","armed_away":"Away","armed_home":"Home",
            "triggered":"ALLARME","arming":"Armamento","pending":"Pendente"
            }.get(alst, alst)

    pres = ("In casa: " + ", ".join(home_)) if home_ else "Casa vuota"
    mot  = ("Mov.attivi: " + str(motn)) if motn else "Nessun movimento"
    wsd  = "WS:OK" if (ws_client and ws_client._connected) else "WS:OFF"
    enp  = "TG:OK" if (TG_TOKEN and TG_CHAT) else ""

    qhtml = ""
    for lbl, q in QUICK:
        sq = q.replace("&","&amp;").replace('"',"&quot;")
        qhtml += '<button class="qb" data-q="' + sq + '" onclick="sendQ(this)">' + lbl + '</button>'

    # Warning box se mancano person.*
    warn_html = ""
    if not has_p:
        warn_html = (
            "<div class='msg warn-box' style='margin:8px 14px'>"
            "⚠️ <strong>Nessuna entita person.*</strong> trovata — antifurto disabilitato.<br>"
            "Vai in <strong>HA → Impostazioni → Persone</strong> e aggiungi te stesso."
            "</div>"
        )

    return HTMLResponse(
        "<!DOCTYPE html><html lang='it'>"
        "<head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>HomeMind</title>"
        "<style>" + CSS + "</style></head>"
        "<body><div id='app'>"
        "<div id='hdr'>"
          "<h1>HomeMind</h1>"
          "<button class='navbtn blue' onclick='openPanel(\"dashboard\",\"📊 Dashboard Live\")'>📊</button>"
          "<button class='navbtn' onclick='openPanel(\"spazzatura\",\"🗑️ Spazzatura\")'>🗑️</button>"
          "<button class='navbtn' onclick='openPanel(\"providers\",\"🤖 AI Providers\")'>🤖</button>"
          "<span class='bdg " + acls + "'>" + albl + "</span>"
          "<span style='margin-left:auto;font-size:.72rem;color:#64748b' id='ai-active-lbl'>"
            + (ai._providers[0].display if ai and ai._providers else AI_PROVIDER.upper()) +
            " | " + wsd + (" | " + enp if enp else "") +
          "</span>"
        "</div>"
        "<div id='bar'>" + pres + " &nbsp;|&nbsp; " + mot + "</div>"
        + warn_html +
        "<div id='msgs'><div class='msg ms'>HomeMind v58 — scrivi o usa i tasti rapidi</div></div>"
        "<div id='qa'>" + qhtml + "</div>"
        "<div id='ia'>"
          "<textarea id='tx' placeholder='Chiedi qualcosa, es: genera card per i miei sensori' rows='1'></textarea>"
          "<button id='sb' onclick='send()'>&#x27A4;</button>"
        "</div>"
        "</div>"
        "<div id='overlay'>"
          "<div id='ov-hdr'>"
            "<h2 id='ov-title'></h2>"
            "<button id='ov-close' onclick='closePanel()'>✕</button>"
          "</div>"
          "<div id='ov-body'><div id='ov-content'></div></div>"
        "</div>"
        "<script>" + JS + "</script>"
        "</body></html>"
    )

# ── Lifecycle ──────────────────────────────────────────────────────────────────

async def _startup():
    global ws_client, rest_client, ai, home, security, notifier, tools, state_cache, tg_bot, spazzatura, update_checker, log_analyzer, automations_mgr, history_client, repairs_checker, morning_briefing

    logger.info("HomeMind v58 starting")

    # ── Core ───────────────────────────────────────────────────────────────
    rest_client = HARestClient(HA_TOKEN)
    await rest_client.start()

    notifier = Notifier(rest_client, TG_TOKEN, TG_CHAT, NOTIFY_ENTITY)
    await notifier.start()

    ws_client = HAWebSocketClient(HA_TOKEN)
    # Usa provider da Opzioni addon (HM_AI_PROVIDERS) oppure fallback legacy
    if HM_AI_PROVIDERS:
        ai = AIProvider(providers_config=HM_AI_PROVIDERS)
    else:
        ai = load_ai_provider_from_config(
            fallback_provider=AI_PROVIDER,
            fallback_model=AI_MODEL,
            fallback_api_key=AI_API_KEY,
        )
    home      = HomeModel(
        person_blacklist=PERSON_BLACKLIST,
        motion_blacklist=MOTION_BLACKLIST,
    )
    security  = SecurityManager(home, rest_client, notifier, ALARM_CODE)

    # ── Carica stati HA PRIMA di tutti i moduli ────────────────────────────
    all_states  = await rest_client.get_states()
    state_cache = {s["entity_id"]: s for s in all_states}
    home.build_from_cache(state_cache)
    security.set_threshold_override(home.motion_threshold_override)
    tools = HATools(state_cache, home, rest_client)
    await home.save()

    # ── Verifica sensori prossimità — fallback REST se non in cache ────────
    import time as _t
    for person_eid, prox in home.proximity_sensors.items():
        if prox["current_m"] is None:
            sensor_eid = prox["sensor"]
            try:
                st = await rest_client.get_state(sensor_eid)
                raw = st.get("state", "") if st else ""
                dist_m = float(raw)
                prox["current_m"] = dist_m
                prox["last_seen"]  = _t.time()
                is_near = dist_m <= prox["threshold_m"]
                if is_near:
                    prox["last_near_ts"] = _t.time()
                name = home.persons.get(person_eid, {}).get("name", person_eid)
                logger.info("PROXIMITY fallback REST: %s = %.0fm → near=%s%s",
                            name, dist_m, is_near, " [sticky attivato]" if is_near else "")
            except Exception as e:
                logger.warning("PROXIMITY fallback REST FAIL per %s: %s", sensor_eid, e)

    # ── Spazzatura ─────────────────────────────────────────────────────────
    sz_hour    = int(os.getenv("HM_SPAZZATURA_NOTIFY_HOUR", "20"))
    sz_enabled = os.getenv("HM_SPAZZATURA_NOTIFY_ENABLED", "true").lower() not in ("false", "0", "no")
    spazzatura = SpazzaturaManager(ai, notifier, notify_hour=sz_hour, notify_enabled=sz_enabled)
    await spazzatura.start()

    # ── Update checker ─────────────────────────────────────────────────────
    update_checker = UpdateChecker(notifier=notifier)
    await update_checker.start()

    # ── Log analyzer ───────────────────────────────────────────────────────
    auto_fix_enabled = os.getenv("HM_AUTO_FIX", "false").lower() == "true"
    log_analyzer = LogAnalyzer(
        ai=ai, rest_client=rest_client,
        auto_fix=auto_fix_enabled,
        interval=300,
        notifier=notifier,
    )
    asyncio.create_task(log_analyzer.run_forever(), name="log_analyzer")

    # ── Nuovi moduli v58 (PRIMA di tg_bot!) ────────────────────────────────
    automations_mgr = AutomationsManager(ai, rest_client, notifier)
    history_client  = HistoryClient(rest_client, lambda: state_cache)
    repairs_checker = RepairsChecker(rest_client, ai, notifier)
    await repairs_checker.start()

    # ── Morning briefing ───────────────────────────────────────────────────
    morning_briefing = MorningBriefing(
        ai=ai, rest_client=rest_client,
        state_cache_cb=lambda: state_cache,
        notifier=notifier, home=home,
        history_client=history_client,
        repairs_checker=repairs_checker,
        spazzatura=spazzatura,
    )
    await morning_briefing.start()

    # ── Energy Analyzer — anomalie energetiche AI ──────────────────────────
    global energy_analyzer
    energy_analyzer = EnergyAnalyzer(
        ai             = ai,
        history_client = history_client,
        notifier       = notifier,
        state_cache_cb = lambda: state_cache,
    )
    await energy_analyzer.start()

    # ── Appliance Monitor — opzionale, solo se configurato ─────────────────
    global appliance_monitor
    appliance_monitor = ApplianceMonitor(
        notifier       = notifier,
        state_cache_cb = lambda: state_cache,
        ai             = ai,
    )
    await appliance_monitor.start()

    # ── Solar Optimizer — opzionale, solo se solar_optimizer.enabled=true ─
    global solar_optimizer
    solar_optimizer = SolarOptimizer(
        rest_client       = rest_client,
        state_cache_cb    = lambda: state_cache,
        notifier          = notifier,
        appliance_monitor = appliance_monitor,
    )
    await solar_optimizer.start()

    # ── Telegram bot (tutti i moduli già pronti) ────────────────────────────
    tg_allowed = [c.strip() for c in os.getenv("HM_TELEGRAM_CHAT","").split(",") if c.strip()]
    tg_bot = TelegramBot(
        token                = TG_TOKEN,
        allowed_chat_ids     = tg_allowed,
        ai_callback          = lambda sys, msg, hist: ai.ask(sys, msg, max_tokens=1500, history=hist or []),
        action_callback      = _exec_actions,
        context_callback     = lambda: tools.full_context() if tools else "(non pronto)",
        spazzatura_callback  = lambda: spazzatura,
        update_checker       = update_checker,
        automations_mgr      = automations_mgr,
        history_client       = history_client,
        repairs_checker      = repairs_checker,
        state_cache_cb       = lambda: state_cache,
        briefing_cb          = lambda: morning_briefing.send_briefing() if morning_briefing else None,
        genera_dashboard_cb  = lambda yaml_inline=None, mode="html": generate_ai_dashboard(rest_client, ai, state_cache, home, yaml_inline, mode=mode),
        ai_action_cb         = _exec_actions,
        card_luci_cb         = lambda user_yaml="": tools.make_room_lights_graph_card_yaml(user_yaml) if tools else "⚠️ Tools non pronti",
        ai_provider          = ai,
        energy_analyzer      = energy_analyzer,
        appliance_monitor    = appliance_monitor,
        solar_optimizer      = solar_optimizer,
        rest_client          = rest_client,
    )
    await tg_bot.start()

    # WS handler
    async def _on_sc(event: dict):
        data = event.get("data", {})
        eid  = data.get("entity_id","")
        ns   = data.get("new_state")
        os_  = data.get("old_state")
        if ns: state_cache[eid] = ns
        nst = (ns  or {}).get("state","")
        ost = (os_ or {}).get("state","")
        if nst != ost:
            asyncio.create_task(security.on_state_changed(eid, ost, nst))

    ws_client.on_event("state_changed", _on_sc)
    asyncio.create_task(ws_client.connect_and_run(), name="ws")

    # Rebuild periodico
    async def _rebuild():
        while True:
            await asyncio.sleep(120)
            home.build_from_cache(state_cache)
    asyncio.create_task(_rebuild(), name="rebuild")

    # Startup check: arma se casa già vuota
    asyncio.create_task(security.startup_check(), name="startup_check")

    # Notifica avvio
    s = home.summary()
    persons_str = ", ".join(v["name"] for v in home.persons.values()) or "NESSUNA!"
    motions_str = str(len(home.motion_sensors)) + " sensori PIR"
    warn_parts = []
    if not s["has_persons"]:
        warn_parts.append("⚠️ Nessuna person.* — antifurto OFF!")
        warn_parts.append("Crea /config/homemind_patches/person_config.json")
    warn = ("\n" + "\n".join(warn_parts)) if warn_parts else ""
    try:
        await notifier.send(
            "🎩 HomeMind v58 attivo",
            "Entita: " + str(len(state_cache)) +
            "\nPersone: " + persons_str +
            "\nMovimento: " + motions_str +
            "\nAllarme: " + (s["alarm_entity"] or "non trovato") +
            "\nCasa: " + ("vuota" if s["everyone_away"] else "occupata") +
            "\n\n✅ Nuovi comandi disponibili:\n"
            "/energia /ieri /automazioni\n"
            "/riparazioni /briefing\n" +
            warn
        )
    except Exception as e:
        logger.warning("Startup notify: %s", e)

    # ── Check provider AI all'avvio ──────────────────────────────
    # provider check rimosso — usa /providers su Telegram

    logger.info("HomeMind v58 ready — %d entita, %d persone, %d sensori mov.",
                len(state_cache), len(home.persons), len(home.motion_sensors))

async def _shutdown():
    if spazzatura:  await spazzatura.stop()
    if tg_bot:      await tg_bot.stop()
    if notifier:    await notifier.stop()
    if rest_client: await rest_client.stop()
    logger.info("HomeMind shutdown")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8099,
                log_level=os.getenv("HM_LOG_LEVEL","info").lower())
