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
from agent.entity_registry import EntityRegistry
from agent.history_client import HistoryClient
from agent.repairs_checker import RepairsChecker
from agent.morning_briefing import MorningBriefing
from agent.live_dashboard import generate_ai_dashboard
from agent.energy_analyzer import EnergyAnalyzer
from agent.appliance_monitor import ApplianceMonitor
from agent.solar_optimizer  import SolarOptimizer
from agent.routine_manager  import RoutineManager
from agent.db_manager       import HomeMindDB
from agent.task_scheduler            import TaskScheduler
from agent.recurring_task_scheduler  import RecurringTaskScheduler
from agent.power_guard      import PowerGuard
from agent.local_parser     import LocalParser
from agent.config_editor    import ConfigEditor
from agent.frigate_client   import load_frigate_client
from agent.email_manager    import EmailChecker
from notifier import Notifier
from telegram_bot import TelegramBot
from translations import get_lang
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
frigate_client = None
notifier:     Notifier          = None
tools:        HATools           = None
state_cache:  dict              = {}
CHAT_HISTORY: list              = []
tg_bot:       TelegramBot       = None
spazzatura:   "SpazzaturaManager" = None
update_checker: "UpdateChecker"  = None
log_analyzer:   "LogAnalyzer"    = None
automations_mgr: "AutomationsManager" = None
entity_registry: "EntityRegistry"     = None
history_client:  "HistoryClient"      = None
repairs_checker: "RepairsChecker"     = None
morning_briefing: "MorningBriefing"   = None
energy_analyzer: "EnergyAnalyzer"   = None
appliance_monitor: "ApplianceMonitor" = None
db_manager: "HomeMindDB"             = None
solar_optimizer:   "SolarOptimizer"   = None
routine_manager:   "RoutineManager"   = None
task_scheduler:            "TaskScheduler"            = None
recurring_task_scheduler:  "RecurringTaskScheduler"  = None
config_editor:     "ConfigEditor"     = None
power_guard:       "PowerGuard"       = None
email_checker:     "EmailChecker"     = None

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
  ov.classList.add('open');
  var base = location.pathname.replace(/\/$/, '');
  // Per settings usa iframe — garantisce JS e CSS corretti
  if (path === 'settings' || path === 'regole' || path === 'email') {
    body.innerHTML = '<iframe src="' + base + '/' + path + '" style="width:100%;height:100%;border:none;background:#0f172a" frameborder="0"></iframe>';
    return;
  }
  body.innerHTML = '<div style="padding:2rem;color:#94a3b8;text-align:center">⏳ Caricamento...</div>';
  fetch(base + '/' + path)
    .then(function(r){ return r.text(); })
    .then(function(html){
      var m = html.match(/<body[^>]*>([\s\S]*)<\/body>/i);
      var content = m ? m[1] : html;
      body.innerHTML = content;
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

# Messaggi dashboard che sono solo query — MAI eseguire azioni
QUICK_QUERY_ONLY = {
    "Dimmi lo stato completo della casa",
    "Analizza energia: fotovoltaico, batteria, rete Enel",
    "Quali luci sono accese? Voglio dettagli e entity_id",
    "Tutte le temperature in casa",
    "Elenca tutti i sensori movimento fisici trovati e il loro stato",
    "Stato antifurto: persone, allarme, sensori movimento",
    "Suggerisci miglioramenti alla mia configurazione HA",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _startup()
    yield
    await _shutdown()

app = FastAPI(title="HomeMind", lifespan=lifespan)

# ── Middleware autenticazione ────────────────────────────────────────────────
# Le richieste via HA Ingress sono già autenticate da HA (header X-Ingress-Path).
# Per accessi diretti alla porta 8099 (fuori da Ingress) verifichiamo il Supervisor token.
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

_SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN", "")
_PUBLIC_PATHS = {"/health"}  # endpoint sempre accessibile (usato da HEALTHCHECK)

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        # Sempre accessibile: health check
        if path in _PUBLIC_PATHS:
            return await call_next(request)
        # Richieste via HA Ingress: HA aggiunge X-Ingress-Path — considerate autenticate
        if request.headers.get("X-Ingress-Path"):
            return await call_next(request)
        # Accesso diretto: verifica Authorization header o query param token
        auth = request.headers.get("Authorization", "")
        token = request.query_params.get("token", "")
        bearer = auth.replace("Bearer ", "").strip()
        valid = bearer or token
        if _SUPERVISOR_TOKEN and valid == _SUPERVISOR_TOKEN:
            return await call_next(request)
        # Se non c'è SUPERVISOR_TOKEN configurato, permetti accesso locale (backward compat)
        if not _SUPERVISOR_TOKEN:
            return await call_next(request)
        logger.warning("Auth: accesso negato a %s", path)
        return StarletteResponse("Unauthorized", status_code=401)

app.add_middleware(AuthMiddleware)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "27"}

@app.get("/api/alarm_status")
async def api_alarm_status():
    """Restituisce lo stato attuale dell'allarme — usato dalla UI per aggiornamento live."""
    alarm_eid, alarm_st = home.primary_alarm() if home else ("", "unknown")
    armed_states = ("armed_away", "armed_home", "armed_night", "armed_vacation")
    mode_labels  = {
        "armed_away":    "🔒 Fuori casa",
        "armed_home":    "🏠 In casa (perimetrali)",
        "armed_night":   "🌙 Notte",
        "armed_vacation":"✈️ Vacanza",
        "disarmed":      "✅ Disarmato",
        "arming":        "⏳ Armamento...",
        "pending":       "⏳ In attesa...",
        "triggered":     "🚨 ALLARME!",
    }
    # Leggi la modalità configurata nel config (preferenza HomeMind)
    _cfg_arm_mode = "armed_away"
    try:
        import json as _j
        from pathlib import Path as _P
        _cp = _P("/config/homemind_patches/person_config.json")
        if _cp.exists():
            _cfg_arm_mode = _j.loads(_cp.read_text(encoding="utf-8-sig")).get(
                "alarm_arm_mode", "armed_away")
    except Exception:
        pass
    return JSONResponse({
        "state":         alarm_st,
        "entity":        alarm_eid,
        "label":         mode_labels.get(alarm_st, alarm_st),
        "is_armed":      alarm_st in armed_states,
        "arm_mode":      alarm_st if alarm_st in armed_states else "",
        "cfg_arm_mode":  _cfg_arm_mode,
    })


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

    # Validazione azioni — uguale per tutti i provider AI
    if _should_block_actions(msg, reply):
        actions = []  # azioni bloccate per sicurezza
    else:
        actions = await _exec_actions(reply, msg)

    # Se ci sono dati GET_HISTORY, mostra grafico + analisi AI
    history_data = [a for a in actions if a.startswith("📊")]
    if history_data:
        # Separa blocchi AI-only (aggregati movimento) da blocchi visualizzabili
        ai_only_blocks  = []  # dati aggregati → solo per contesto AI
        chart_blocks    = []  # grafici/liste esplicite → mostrati all'utente

        for hd in history_data:
            if "__AI_ONLY__" in hd:
                # Rimuovi il marcatore prima di mandare all'AI
                ai_only_blocks.append(hd.replace("__AI_ONLY__\n", "").replace("__AI_ONLY__", ""))
            else:
                chart_blocks.append(hd)

        # Contesto per il followup AI: sia i dati aggregati che gli eventuali grafici
        all_ctx_parts = ai_only_blocks + [
            hd.replace("<pre>", "").replace("</pre>", "").replace("<b>", "").replace("</b>", "")
            for hd in chart_blocks
        ]
        history_ctx = "\n\n".join(all_ctx_parts)

        followup_msg = (
            f"L'utente ha chiesto: \"{msg}\"\n\n"
            f"Dati recuperati da Home Assistant:\n\n"
            f"{history_ctx}\n\n"
            f"ISTRUZIONI RISPOSTA:\n"
            f"- Rispondi in modo NARRATIVO e DIRETTO alla domanda dell'utente\n"
            f"- Domanda generica ('hai rilevato movimenti?', 'situazione normale?', 'cosa è successo?'):\n"
            f"  → Descrivi con parole: quando c'era più attività, se il pattern è normale, eventuali anomalie\n"
            f"  → Esempio: 'Sì, in cucina c'è stata molta attività — principalmente dalla mattina alle 22:00 con picco intorno alle 14:00. Nessuna anomalia notturna.'\n"
            f"- Domanda sul numero ('quante volte?'):\n"
            f"  → Rispondi solo con il numero e zona\n"
            f"- Domanda su un orario specifico ('a che ora?', 'quando?'):\n"
            f"  → Rispondi con l'orario preciso\n"
            f"- NON elencare i singoli timestamp — usa le fasce orarie e i totali\n"
            f"- NON usare tag [CALL_SERVICE] o [GET_HISTORY]\n"
            f"- Massimo 4-5 righe, tono naturale e conversazionale"
        )
        try:
            analysis = await ai.ask(system, followup_msg, max_tokens=400)
            # Rimuovi tutti i blocchi 📊 dalle actions
            actions = [a for a in actions if not a.startswith("📊")]
            # Mostra i grafici/liste esplicite all'utente (se presenti)
            for cb in chart_blocks:
                actions.insert(0, cb)
            # Analisi AI narrativa
            if analysis and analysis.strip():
                actions.append("💬 " + analysis)
        except Exception as e:
            logger.warning("History analysis AI error: %s", e)
            actions = [a for a in actions if not a.startswith("📊")]
            for cb in chart_blocks:
                actions.insert(0, cb)

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
        "   [CALL_SERVICE:switch.turn_on:switch.nome_switch]  ← usa SOLO switch reali dal contesto\n"
        "   [CALL_SERVICE:climate.set_temperature:climate.termostato:{\"temperature\":21}]\n"
        "   [CALL_SERVICE:media_player.turn_on:media_player.tv_soggiorno]\n"
        "   [CALL_SERVICE:media_player.volume_set:media_player.tv:{\"volume_level\":0.5}]\n"
        "   REGOLA: metti SOLO l'entity_id nel terzo campo, mai 'entity_id=xxx'\n"
        "   Per PIÙ luci: genera un [CALL_SERVICE] per ogni luce\n"
        "   Per TUTTE le luci: usa [CALL_SERVICE:light.turn_on:all]\n"
        "   Per COLORI RGB: [CALL_SERVICE:light.turn_on:light.faretti:{\"rgb_color\":[255,0,0]}]\n   Per BIANCO/WHITE (usa SEMPRE color_temp_kelvin, non rgb): [CALL_SERVICE:light.turn_on:light.faretti:{\"color_temp_kelvin\":4000,\"brightness\":255}]\n   Per BIANCO CALDO: color_temp_kelvin 2700 | BIANCO NEUTRO: 4000 | BIANCO FREDDO: 6500\n   ⚠️ IMPORTANTE per elettrodomestici: usa SOLO switch/entità presenti nel contesto ELETTRODOMESTICI.\n   Se un elettrodomestico NON ha uno switch configurato, NON proporre di accenderlo/spegnerlo — di solo lo stato di potenza e il ciclo corrente.\n"
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
        "   'quando è arrivato Mario?'                   → [GET_HISTORY:person.mario:24]\n"
        "   'porta aperta stamattina?'                   → [GET_HISTORY:binary_sensor.xxx_contact:12]\n"
        "   Puoi usare più [GET_HISTORY] nella stessa risposta.\n"
        "   Dopo aver ricevuto i dati, analizzali e rispondi in modo chiaro.\n"
        "   ⚠️ IMPORTANTE — Domande generali su movimento/sicurezza:\n"
        "   Se l'utente chiede 'hai rilevato movimenti?' o 'c'è stato qualcuno?' o domande simili\n"
        "   NON elencare ogni singolo orario — rispondi in modo naturale e sintetico:\n"
        "   'Sì, nella cucina ho rilevato 154 attivazioni dalle 03:39 alle 22:00, con picco al mattino.'\n"
        "   Usa [GET_HISTORY] per tutti i sensori movimento della whitelist se la domanda è generica.\n"
        "   La lista completa degli orari va mostrata SOLO se l'utente chiede esplicitamente\n"
        "   'mostrami tutte le attivazioni' o 'elenca tutti gli orari'.\n\n"

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

        "=== REGOLE FONDAMENTALI (valide per qualsiasi AI) ===\n"
        "\n"
        "⛔ QUANDO NON USARE [CALL_SERVICE]:\n"
        "- L'utente fa una DOMANDA (chi, cosa, quanto, dove, quando, perché)\n"
        "- L'utente chiede lo STATO (quante luci, chi è in casa, che temperatura)\n"
        "- L'utente chiede un'ANALISI o STORICO\n"
        "- L'utente chiede SUGGERIMENTI o MIGLIORAMENTI\n"
        "- L'utente non ha dato un comando esplicito di controllo\n"
        "- NON generare CALL_SERVICE come ESEMPIO — solo per eseguire davvero\n"
        "\n"
        "✅ QUANDO USARE [CALL_SERVICE]:\n"
        "- Comando esplicito: accendi, spegni, imposta, alza, abbassa, arma, disarma\n"
        "- L'utente conferma un'azione (sì, ok, vai, confermo, fallo)\n"
        "\n"
        "📋 REGOLE GENERALI:\n"
        "- sensor negativo watt = NORMALE (batteria in scarica)\n"
        "- NON modificare configuration.yaml — genera YAML e chiedi conferma\n"
        "- Se non trovi un'entità, dillo e suggerisci alternative\n"
        "- Per lo storico: usa [GET_HISTORY] invece di inventare dati\n"
        "- Usa markdown solo per formattazione — non per tag azione\n"
        "- NON inventare entity_id — usa SOLO quelli presenti nel contesto\n"
        "- NON aggiungere CALL_SERVICE nelle risposte informative anche se sembrano utili\n"
        "- Se hai dubbi se eseguire o meno un'azione — NON eseguirla, chiedi prima\n"
    )

# ─────────────────────────────────────────────────────────────────────────
# Validazione azioni — indipendente dal provider AI
# Garantisce comportamento coerente tra Gemini, Groq, Cerebras, OpenAI ecc.
# ─────────────────────────────────────────────────────────────────────────

# Frasi che indicano una domanda informativa — mai eseguire azioni
_QUERY_INDICATORS = (
    "quali luci", "che luci", "luci accese", "luci spente",
    "dimmi lo stato", "stato completo", "quante luci",
    "tutte le temperature", "elenca", "mostrami", "fammi vedere",
    "quali sensori", "stato antifurto", "analizza energia",
    "which lights", "lights on", "tell me", "show me", "list all",
    "what is the status", "how many",
)

def _should_block_actions(user_msg: str, reply: str) -> bool:
    """
    Controlla se le azioni nella risposta AI devono essere bloccate.
    Funziona uguale per tutti i provider AI.
    """
    msg_low = user_msg.lower()
    # 1. Messaggi query-only dalla dashboard
    if user_msg in QUICK_QUERY_ONLY:
        logger.debug("_validate: blocco azioni — messaggio query-only dashboard")
        return True
    # 2. Domande informative riconoscibili
    if any(q in msg_low for q in _QUERY_INDICATORS):
        # Blocca solo se il messaggio NON ha anche un comando esplicito
        ACTION_WORDS = ("accendi", "spegni", "imposta", "arma", "disarma",
                        "turn on", "turn off", "set", "arm", "open", "close")
        if not any(a in msg_low for a in ACTION_WORDS):
            logger.debug("_validate: blocco azioni — domanda informativa senza comando")
            return True
    # 3. Risposta AI che contiene CALL_SERVICE su entità non presenti nel contesto
    #    (ogni AI gestisce diversamente gli entity_id sconosciuti)
    return False


async def _exec_actions(reply: str, user_msg: str = "") -> list:
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

        # ── Clamp temperatura clima entro min/max configurati ────────────────
        if domain == "climate" and service == "set_temperature" and "temperature" in data:
            climate_cfg = getattr(home, "_climate_config", {})
            cfg = climate_cfg.get(entity, {})
            # Leggi anche da attributi HA se disponibili
            attrs_c = state_cache.get(entity, {}).get("attributes", {})
            min_t = cfg.get("min_temp") or attrs_c.get("min_temp", 5)
            max_t = cfg.get("max_temp") or attrs_c.get("max_temp", 35)
            req_t = float(data["temperature"])
            clamped = max(float(min_t), min(float(max_t), req_t))
            if clamped != req_t:
                logger.info("Clima: temperatura %.0f° clamped a %.0f° (range %s°-%s°)",
                            req_t, clamped, min_t, max_t)
                data["temperature"] = clamped
                done.append(f"⚠️ Temperatura richiesta {req_t:.0f}° oltre il limite — impostata a {clamped:.0f}°")

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
    def _ascii_chart(values_ts: list, unit: str = "") -> str:
        """Genera grafico ASCII per valori numerici."""
        if len(values_ts) < 3:
            return ""
        vals  = [v for v, _ in values_ts]
        times = [t for _, t in values_ts]
        mn, mx = min(vals), max(vals)
        if mx == mn:
            return ""
        H = 5   # righe grafico
        W = min(len(vals), 24)
        step    = max(1, len(vals) // W)
        sampled = [(vals[i], times[i]) for i in range(0, len(vals), step)][:W]
        grid    = [[" "] * len(sampled) for _ in range(H)]
        for col, (v, _) in enumerate(sampled):
            row = H - 1 - int((v - mn) / (mx - mn) * (H - 1))
            row = max(0, min(H - 1, row))
            grid[row][col] = "●"
        lines_g = []
        for r, row in enumerate(grid):
            label_val = mx - r * (mx - mn) / (H - 1)
            lines_g.append(f"{label_val:5.1f}{unit}│{''.join(row)}")
        first_t = sampled[0][1]
        last_t  = sampled[-1][1]
        lines_g.append(f"      └{'─' * len(sampled)}")
        lines_g.append(f"       {first_t}  →  {last_t}")
        return "\n".join(lines_g)

    # GET_HISTORY supporta formato: [GET_HISTORY:entity:ore] o [GET_HISTORY:entity:ore:formato]
    for m in re.finditer(r'\[GET_HISTORY:([^\]:]+):(\d+)(?::([a-z]*))?\]', reply):
        eid    = m.group(1).strip()
        hours  = int(m.group(2))
        fmt_override = m.group(3) or ""  # "text", "chart", "grafico", "testuale"
        try:
            history = await rest_client.get_history([eid], hours=hours)
            entries = history.get(eid, [])
            if not entries:
                done.append(f"📊 Storico {eid}: nessun dato nelle ultime {hours}h")
            else:
                name = state_cache.get(eid, {}).get("attributes", {}).get("friendly_name", eid)
                unit = ""
                numeric_vals = []
                changes      = []
                prev         = None
                from utils.timezone_helper import local_tz as _ltz
                for entry in entries:
                    st = entry.get("state", "")
                    if st in ("unavailable", "unknown", ""):
                        continue
                    ts_raw = entry.get("last_changed", "")
                    try:
                        ts_dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                        ts    = ts_dt.astimezone(_ltz()).strftime("%H:%M")
                    except Exception:
                        ts = ts_raw[11:16]
                    unit = entry.get("attributes", {}).get("unit_of_measurement", unit)
                    try:
                        numeric_vals.append((float(st), ts))
                    except (ValueError, TypeError):
                        pass
                    if st != prev:
                        changes.append((ts, st, unit))
                        prev = st
                # Determina tipo sensore
                is_binary = eid.startswith("binary_sensor.") or eid.startswith("input_boolean.")
                is_person  = eid.startswith("person.")
                is_light   = eid.startswith("light.")
                # Deriva force_text / force_chart da fmt_override
                force_text  = fmt_override in ("text", "testuale", "testo")
                force_chart = fmt_override in ("chart", "grafico")

                # Costruisci output
                lines = [f"📊 <b>{name}</b> — ultime {hours}h"]

                # force_text → sempre testuale; force_chart → sempre grafico
                # numeric_vals contiene tuple (float_value, str_timestamp)
                if force_text and len(numeric_vals) >= 2:
                    try:
                        # Estrai solo i float — indice 0 della tupla
                        vals_only = [float(v[0]) for v in numeric_vals]
                        ts_list   = [str(v[1]) for v in numeric_vals]
                        mn_v = min(vals_only)
                        mx_v = max(vals_only)
                        avg  = sum(vals_only) / len(vals_only)
                        trend = "📈" if vals_only[-1] > vals_only[0] else ("📉" if vals_only[-1] < vals_only[0] else "➡️")
                        lines.append(f"{trend} Andamento: da <b>{vals_only[0]:.1f}{unit}</b> a <b>{vals_only[-1]:.1f}{unit}</b>")
                        lines.append(f"⬇️ Min: <b>{mn_v:.1f}{unit}</b>  ⬆️ Max: <b>{mx_v:.1f}{unit}</b>  📊 Media: <b>{avg:.1f}{unit}</b>")
                        if len(vals_only) > 2:
                            lines.append("")
                            lines.append("📅 <b>Variazioni principali:</b>")
                            prev_v = vals_only[0]
                            shown_c = 0
                            for i, val_v in enumerate(vals_only[1:], 1):
                                ts_v = ts_list[i]
                                diff = val_v - prev_v
                                if abs(diff) >= max(0.3, (mx_v - mn_v) * 0.1) and shown_c < 8:
                                    arrow = "📈" if diff > 0 else "📉"
                                    lines.append(f"  {arrow} {ts_v}: {val_v:.1f}{unit} ({diff:+.1f})")
                                    shown_c += 1
                                prev_v = val_v
                        if shown_c == 0:
                            lines.append("  Temperatura stabile, nessuna variazione significativa")
                        lines.append(f"\n🕐 {ts_list[0]} → {ts_list[-1]}  ({len(vals_only)} letture)")
                    except Exception as e_txt:
                        logger.warning("GET_HISTORY force_text error: %s | numeric_vals[0]=%s", e_txt, numeric_vals[0] if numeric_vals else "empty")
                        lines.append(f"❌ Errore formato testuale: {e_txt}")
                elif (is_binary or is_person or is_light) and not numeric_vals and not force_chart:
                    # Formato speciale per sensori on/off
                    activations = [(ts, st) for ts, st, _ in changes if st in ("on", "home", "open")]
                    count_on    = len(activations)
                    count_off   = len([c for c in changes if c[1] in ("off", "not_home", "closed")])

                    if is_binary and "occupancy" in eid:
                        # Sensore movimento
                        # Controlla se l'utente vuole la lista completa esplicitamente
                        _msg_low = user_msg.lower()
                        _wants_full_list = any(w in _msg_low for w in [
                            "tutte le attivazioni", "tutti gli orari", "mostrami tutto",
                            "lista completa", "elenco completo", "fammi vedere tutte",
                            "ogni attivazione", "all activations",
                            "show all", "list all", "elenca tutto", "elenca tutte",
                        ])

                        if count_on == 0:
                            lines.append("🟢 Nessun movimento rilevato")
                        elif count_on == 1:
                            lines.append(f"🚶 Movimento rilevato <b>1 volta</b>")
                            lines.append(f"   📍 alle {activations[0][0]}")
                        elif _wants_full_list:
                            # Lista completa — solo se richiesta esplicitamente
                            lines.append(f"🚶 Movimento rilevato <b>{count_on} volte</b>")
                            lines.append("")
                            lines.append("📅 <b>Orari attivazioni:</b>")
                            for i, (ts_a, _) in enumerate(activations, 1):
                                lines.append(f"  {i:2}. 🟠 {ts_a}")
                            if len(activations) > 1:
                                from datetime import datetime as _dta
                                try:
                                    t0 = _dta.strptime(activations[0][0], "%H:%M")
                                    t1 = _dta.strptime(activations[-1][0], "%H:%M")
                                    span_min = abs((t1-t0).seconds // 60)
                                    avg_interval = span_min // max(1, len(activations)-1)
                                    lines.append(f"")
                                    lines.append(f"⏱ Prima: <b>{activations[0][0]}</b>  Ultima: <b>{activations[-1][0]}</b>")
                                    lines.append(f"📊 Intervallo medio: ~{avg_interval} min")
                                except Exception:
                                    pass
                        else:
                            # Risposta intelligente: calcola aggregati da passare all'AI
                            from datetime import datetime as _dta
                            fascia = {"notte (00-06)": 0, "mattina (06-12)": 0,
                                      "pomeriggio (12-18)": 0, "sera (18-24)": 0}
                            peak_hour_count = {}
                            for ts_a, _ in activations:
                                try:
                                    h = int(ts_a.split(":")[0])
                                    peak_hour_count[h] = peak_hour_count.get(h, 0) + 1
                                    if h < 6:    fascia["notte (00-06)"] += 1
                                    elif h < 12: fascia["mattina (06-12)"] += 1
                                    elif h < 18: fascia["pomeriggio (12-18)"] += 1
                                    else:        fascia["sera (18-24)"] += 1
                                except Exception:
                                    pass
                            peak_h = max(peak_hour_count, key=peak_hour_count.get) if peak_hour_count else None
                            try:
                                t0 = _dta.strptime(activations[0][0], "%H:%M")
                                t1 = _dta.strptime(activations[-1][0], "%H:%M")
                                span_min = abs((t1 - t0).seconds // 60)
                                avg_interval = span_min // max(1, len(activations) - 1)
                            except Exception:
                                avg_interval = None

                            fascia_str = " | ".join(f"{k}: {v}" for k, v in fascia.items() if v > 0)

                            # NON mostrare la lista raw — passa solo dati aggregati all'AI
                            # Il blocco viene marcato come __AI_ONLY__ così viene escluso
                            # dalla visualizzazione diretta ma incluso nel contesto followup
                            lines.append(f"__AI_ONLY__")
                            lines.append(f"🏠 Zona: {name}")
                            lines.append(f"🚶 Totale attivazioni: {count_on}")
                            lines.append(f"⏱ Attivo dalle {activations[0][0]} alle {activations[-1][0]}")
                            lines.append(f"📊 Distribuzione oraria: {fascia_str}")
                            if peak_h is not None:
                                lines.append(f"🔝 Ora più attiva: {peak_h:02d}:00–{peak_h:02d}:59 ({peak_hour_count[peak_h]} passaggi)")
                            if avg_interval is not None:
                                lines.append(f"⏱ Ogni quanto in media: ~{avg_interval} min")
                            # Valutazione automatica intensità
                            if count_on > 100:
                                lines.append("📈 Intensità: ALTA (più di 100 attivazioni)")
                            elif count_on > 40:
                                lines.append("📊 Intensità: MEDIA")
                            else:
                                lines.append("📉 Intensità: BASSA")
                            if fascia.get("notte (00-06)", 0) > 5:
                                lines.append(f"⚠️ Attività notturna insolita: {fascia['notte (00-06)']} attivazioni fra 00:00 e 06:00")
                    elif is_light:
                        # Luce
                        if count_on == 0:
                            lines.append("💡 Luce mai accesa nel periodo")
                        else:
                            lines.append(f"💡 Accesa <b>{count_on} volte</b>")
                            for i, (ts_a, _) in enumerate(activations[:10], 1):
                                lines.append(f"  {i}. 🟡 {ts_a}")
                    elif is_person:
                        # Presenza persona
                        arrivals = [(ts, st) for ts, st, _ in changes if st == "home"]
                        departures = [(ts, st) for ts, st, _ in changes if st == "not_home"]
                        lines.append(f"🏠 Rientri: <b>{len(arrivals)}</b>   🚗 Uscite: <b>{len(departures)}</b>")
                        for ts_a, _ in arrivals[:5]:
                            lines.append(f"  🏠 Rientro: {ts_a}")
                        for ts_d, _ in departures[:5]:
                            lines.append(f"  🚗 Uscita: {ts_d}")
                    else:
                        # Altri sensori binari — contatto, lock ecc.
                        lines.append(f"🔄 Cambiamenti: <b>{len(changes)}</b>")
                        for ts, st, u in changes[:15]:
                            icon = "🟢" if st in ("on","open","unlocked") else "🔴"
                            lines.append(f"  {icon} {ts} → <b>{st}</b>")
                        if len(changes) > 15:
                            lines.append(f"  ... e altri {len(changes)-15} eventi")

                elif len(numeric_vals) >= 3:
                    # Sensori numerici — grafico ASCII
                    try:
                        vals_only = [float(v[0]) for v in numeric_vals]
                        ts_list   = [str(v[1]) for v in numeric_vals]
                        chart = _ascii_chart(numeric_vals, unit)
                        if chart:
                            lines.append("<pre>" + chart + "</pre>")
                        mn_v = min(vals_only)
                        mx_v = max(vals_only)
                        avg  = sum(vals_only) / len(vals_only)
                        if vals_only[-1] > vals_only[0]:
                            trend = "📈"
                        elif vals_only[-1] < vals_only[0]:
                            trend = "📉"
                        else:
                            trend = "➡️"
                        lines.append(
                            f"{trend} Min: <b>{mn_v:.1f}{unit}</b>  "
                            f"Max: <b>{mx_v:.1f}{unit}</b>  "
                            f"Media: <b>{avg:.1f}{unit}</b>"
                        )
                        lines.append(
                            f"🕐 {ts_list[0]} → {ts_list[-1]}"
                            f"  ({len(vals_only)} letture)"
                        )
                    except Exception as e_chart:
                        logger.warning("GET_HISTORY grafico error: %s | numeric_vals[0]=%s", e_chart, numeric_vals[0] if numeric_vals else "empty")
                        lines.append(f"❌ Errore grafico: {e_chart}")
                else:
                    # Fallback generico
                    for ts, st, u in changes[:20]:
                        icon = "🟢" if st in ("on","home","armed") else "🔴"
                        u_str = (" " + u) if u else ""
                        lines.append(f"  {icon} {ts} → <b>{st}</b>{u_str}")
                    if len(changes) > 20:
                        lines.append(f"  ... ({len(changes)} eventi totali)")
                done.append("\n".join(lines))
                logger.info(
                    "GET_HISTORY %s: %d entries → grafico=%s",
                    eid, len(entries), len(numeric_vals) >= 3
                )
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
    # Luci reali: escludi unavailable/unknown e gruppi luce (di solito hanno friendly_name con "Group" o "Gruppo")
    real_lights = [
        (e, s) for e, s in state_cache.items()
        if e.startswith("light.") and s.get("state") not in ("unavailable", "unknown")
    ]
    n_light    = len(real_lights)
    n_light_on = sum(1 for e, s in real_lights if s.get("state") == "on")
    # Lista luci accese con nome leggibile
    lights_on_names = [
        s.get("attributes", {}).get("friendly_name", e.split(".")[-1].replace("_", " ").title())
        for e, s in real_lights if s.get("state") == "on"
    ]
    n_motion  = sum(1 for e in state_cache if e.endswith("_occupancy"))
    n_contact = sum(1 for e in state_cache if e.endswith("_contact"))
    alarm_st  = next((s.get("state", "?") for e, s in state_cache.items() if e.startswith("alarm_control_panel.")), "n/d")
    alarm_label = {"disarmed": "✅ Disarmato", "armed_away": "🔴 Armato (fuori)", "armed_home": "🟡 Armato (casa)", "triggered": "🚨 ALLARME!"}.get(alarm_st, alarm_st)
    persons = [
        s.get("attributes", {}).get("friendly_name", e)
        for e, s in state_cache.items()
        if e.startswith("person.") and s.get("state") == "home"
    ]
    _html = f"""<!DOCTYPE html><html lang="it">
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
<div class="stat"><span class="icon">💡</span><span class="label">Luci accese</span><span class="value">{n_light_on} / {n_light}</span></div>{f'<div class="stat"><span class="icon" style="font-size:.8rem">↳</span><span class="label" style="font-size:.78rem;color:#7dd3fc">' + ", ".join(lights_on_names) + "</span></div>" if lights_on_names else ""}
<div class="stat"><span class="icon">🔒</span><span class="label">Allarme</span><span class="value {'alarm-ok' if alarm_st=='disarmed' else 'alarm-no'}">{alarm_label}</span></div>
<div class="stat"><span class="icon">🚶</span><span class="label">Sensori presenza</span><span class="value">{n_motion}</span></div>
<div class="stat"><span class="icon">🚪</span><span class="label">Sensori contatto</span><span class="value">{n_contact}</span></div>
<div class="stat"><span class="icon">👤</span><span class="label">In casa</span><span class="value">{', '.join(persons) or 'nessuno'}</span></div>
<div class="tip">💡 Per creare card Lovelace su Telegram:<br><code>crea card:</code><br>poi incolla il tuo YAML base</div>
</div></body></html>"""
    return HTMLResponse(_html)


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
        "  var rawKey=document.getElementById('key-'+n).value;"
"  var d={name:n,model:document.getElementById('mdl-'+n).value,api_key:rawKey.trim()};"
"  if(!d.api_key){tres.textContent='\u26a0\ufe0f Inserisci prima la API key';tres.className='pv-testresult pv-wait';btn.disabled=false;return;}"
        "  try{"
        "    var r=await fetch('api/providers/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});"
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
        "    var r=await fetch('api/providers/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({providers:pvGetList()})});"
        "    var res=await r.json();"
        "    if(res.ok){msg.style.color='#4ade80';msg.textContent='\u2705 Salvato! Riavvia HomeMind per applicare.';}"
        "    else{msg.style.color='#f87171';msg.textContent='\u274c '+(res.error||'Errore');}"
        "  }catch(e){msg.style.color='#f87171';msg.textContent='\u274c '+String(e);}"
        "};"
        "(async function(){"
        "  try{"
        "    var r=await fetch('api/providers/status');var d=await r.json();"
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
            cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
        cfg["ai_providers"] = new_providers
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)[:200]})


# ── Regole comportamentali utente ─────────────────────────────────────────────

_RULES_PATH_WEB = Path("/config/homemind_patches/regole.md")

@app.get("/api/regole")
async def api_regole_get():
    """Restituisce il contenuto attuale di regole.md (solo righe non-commento)."""
    try:
        if not _RULES_PATH_WEB.exists():
            return JSONResponse({"ok": True, "content": ""})
        return JSONResponse({"ok": True, "content": _RULES_PATH_WEB.read_text(encoding="utf-8")})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


@app.post("/api/regole")
async def api_regole_post(request: Request):
    """Salva le regole utente aggiungendole in fondo a regole.md (dopo l'header)."""
    try:
        import json as _json
        raw_body = await request.body()
        logger.info("api/regole POST: body len=%d primi 10 bytes: %s",
                    len(raw_body), raw_body[:10].hex())
        # Strip BOM se presente (problema noto con HA Ingress)
        if raw_body[:3] == b'\xef\xbb\xbf':
            raw_body = raw_body[3:]
        body = _json.loads(raw_body.decode("utf-8").lstrip("\ufeff"))
        new_rules_raw = body.get("rules", "").strip()

        # Leggi il file attuale per preservare header/commenti
        if _RULES_PATH_WEB.exists():
            existing = _RULES_PATH_WEB.read_text(encoding="utf-8")
        else:
            existing = ""

        # Trova la sezione REGOLE ATTIVE e sostituisci tutto ciò che viene dopo
        marker = "# REGOLE ATTIVE (scrivi qui sotto le tue regole, una per riga)"
        if marker in existing:
            # File con header completo: preserva i commenti/esempi sopra il marker
            header = existing[:existing.index(marker) + len(marker)]
            new_content = header + "\n\n" + (new_rules_raw + "\n" if new_rules_raw else "")
        else:
            # File senza header (creato manualmente o da versione precedente):
            # salva solo le regole pulite, senza aggiungere testo spazzatura
            new_content = (new_rules_raw + "\n") if new_rules_raw else ""

        _RULES_PATH_WEB.parent.mkdir(parents=True, exist_ok=True)
        _RULES_PATH_WEB.write_text(new_content, encoding="utf-8")
        # Conta regole attive (non commenti) per il log
        active = [l for l in new_content.splitlines()
                  if l.strip() and not l.strip().startswith("#")]
        logger.info("regole.md salvato: %d regole attive", len(active))
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.warning("regole save error: %s", e)
        return JSONResponse({"ok": False, "error": str(e)})


@app.get("/regole", response_class=HTMLResponse)
async def regole_page(request: Request):
    """Pagina regole — regole pre-renderizzate nel HTML, nessun fetch al load."""
    req_path = str(request.url.path)
    logger.info("regole: req_path=%s", req_path)

    # Leggi regole attive dal file e serializza come JSON per il JS
    try:
        if _RULES_PATH_WEB.exists():
            lines = _RULES_PATH_WEB.read_text(encoding="utf-8").splitlines()
            active = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
        else:
            active = []
    except Exception:
        active = []

    rules_json = json.dumps(active, ensure_ascii=False)

    # API base: lato server non sappiamo il prefisso Ingress,
    # ma sappiamo che il path server-side è /regole → usiamo JS window.location
    html = f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HomeMind — Regole</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#0f172a;color:#e2e8f0;padding:16px;min-height:100vh}}
h2{{color:#60a5fa;font-size:1rem;margin-bottom:14px;font-weight:700}}
.card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px;margin-bottom:12px}}
.rule-row{{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #334155}}
.rule-row:last-child{{border-bottom:none}}
.rule-num{{color:#475569;font-size:.75rem;font-weight:700;flex-shrink:0;width:18px;text-align:right}}
.rule-text{{flex:1;font-size:.86rem;color:#e2e8f0;line-height:1.4}}
.del-btn{{background:none;border:1px solid #7f1d1d;color:#ef4444;font-size:.8rem;
          cursor:pointer;padding:3px 7px;border-radius:4px;flex-shrink:0}}
.del-btn:hover{{background:#7f1d1d}}
.empty{{color:#475569;font-size:.84rem;font-style:italic;padding:4px 0}}
.add-row{{display:flex;gap:8px;margin-top:12px}}
.add-input{{flex:1;background:#0f172a;border:1px solid #334155;border-radius:7px;
           color:#e2e8f0;padding:9px 11px;font-size:.86rem;outline:none}}
.add-input:focus{{border-color:#60a5fa}}
.btn{{padding:9px 16px;border:none;border-radius:7px;font-size:.84rem;
      font-weight:600;cursor:pointer;margin-top:10px;width:100%}}
.btn-save{{background:#15803d;color:#fff}}
.btn-save:hover{{background:#16a34a}}
.btn-clear{{background:#1e293b;border:1px solid #7f1d1d;color:#fca5a5;margin-top:6px;padding:8px;font-size:.8rem}}
.chip{{font-size:.76rem;background:#1e3a5f;border:1px solid #2563eb;color:#93c5fd;
       padding:5px 10px;border-radius:20px;cursor:pointer;margin:3px}}
.chip:hover{{background:#1d4ed8;color:#fff}}
.toast{{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
        background:#15803d;color:#fff;padding:10px 20px;border-radius:8px;
        font-size:.84rem;z-index:999;display:none}}
.toast.err{{background:#7f1d1d;color:#fca5a5}}
</style></head>
<body>
<h2>📋 Regole Comportamentali</h2>
<div class="card">
  <div style="font-size:.78rem;color:#64748b;margin-bottom:10px">
    Iniettate nel prompt HomeMind ad ogni messaggio Telegram.
  </div>
  <div id="list"></div>
  <div class="add-row">
    <input id="inp" class="add-input" type="text" placeholder="Scrivi una nuova regola...">
    <button style="background:#1d4ed8;color:#fff;border:none;border-radius:7px;
                   padding:9px 14px;font-size:.84rem;cursor:pointer;flex-shrink:0;margin-top:0"
            onclick="addRule()">➕</button>
  </div>
</div>
<button class="btn btn-save" onclick="saveRules()">💾 Salva regole</button>
<button class="btn btn-clear" onclick="clearAll()">🗑️ Elimina tutte</button>
<div class="card" style="margin-top:12px">
  <div style="font-size:.82rem;color:#64748b;margin-bottom:8px;font-weight:600">💡 Esempi — clicca per aggiungere</div>
  <div id="chips"></div>
</div>
<div id="toast" class="toast"></div>

<script>
var EXAMPLES = [
  "Chiedi sempre conferma prima di eliminare qualsiasi file",
  "Quando esegui /ssh non chiedere conferma, esegui direttamente",
  "Se non specificato usa /config/ago/progetti come percorso",
  "Non riavviare i servizi HA senza conferma esplicita",
  "Prima di modificare automation.yaml fai sempre un backup",
  "Se non specifico una stanza usa il soggiorno come default",
  "Rispondi sempre in italiano"
];

// Regole pre-caricate dal server — nessun fetch necessario
var rules = {rules_json};

// API base: in iframe il pathname contiene il path completo incluso prefisso Ingress
var _p = window.location.pathname;
var API_BASE = window.location.origin + _p.replace(/\\/regole.*$/, '');

function esc(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function render() {{
  var el = document.getElementById('list');
  if (!rules.length) {{
    el.innerHTML = '<div class="empty">Nessuna regola — aggiungine una.</div>';
    return;
  }}
  el.innerHTML = rules.map(function(r,i) {{
    return '<div class="rule-row"><span class="rule-num">'+(i+1)+'</span>'
      +'<span class="rule-text">'+esc(r)+'</span>'
      +'<button class="del-btn" onclick="del('+i+')">🗑</button></div>';
  }}).join('');
}}

function del(i) {{
  rules.splice(i,1);
  render();
}}

function addRule() {{
  var inp = document.getElementById('inp');
  var v = inp.value.trim();
  if (!v) return;
  rules.push(v);
  inp.value = '';
  render();
  inp.focus();
}}

function clearAll() {{
  if (!rules.length) return;
  if (!confirm('Eliminare tutte le '+rules.length+' regole?')) return;
  rules = [];
  render();
  saveRules();
}}

function toast(msg, err) {{
  var t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast'+(err?' err':'');
  t.style.display = 'block';
  setTimeout(function(){{ t.style.display='none'; }}, 2500);
}}

function saveRules() {{
  var xhr = new XMLHttpRequest();
  xhr.open('POST', API_BASE+'/api/regole', true);
  xhr.setRequestHeader('Content-Type','application/json');
  xhr.onload = function() {{
    try {{
      var d = JSON.parse(xhr.responseText);
      if (d.ok) toast('Salvato — '+rules.length+' regole attive');
      else toast('Errore: '+(d.error||'?'), true);
    }} catch(e) {{ toast('Errore risposta', true); }}
  }};
  xhr.onerror = function() {{ toast('Errore di rete', true); }};
  xhr.send(JSON.stringify({{rules: rules.join('\\n')}}));
}}

// Chips esempi
var chips = document.getElementById('chips');
EXAMPLES.forEach(function(e) {{
  var b = document.createElement('span');
  b.className = 'chip';
  b.textContent = e;
  b.onclick = function() {{
    if (rules.indexOf(e) === -1) {{ rules.push(e); render(); }}
  }};
  chips.appendChild(b);
}});

// Enter su input
document.getElementById('inp').onkeydown = function(ev) {{
  if (ev.key === 'Enter') addRule();
}};

render();
</script>
</body></html>"""
    return HTMLResponse(html)


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


@app.post("/api/spazzatura/alexa_test")
async def api_spazzatura_alexa_test(request: Request):
    """Invia un annuncio di prova sugli speaker Alexa selezionati."""
    try:
        data = await request.json()
        speakers = data.get("speakers", []) or []
        volume   = max(0.0, min(1.0, float(data.get("volume", 0.5))))
        if not speakers:
            return JSONResponse({"ok": False, "error": "Nessuno speaker selezionato"}, status_code=400)
        if not rest_client:
            return JSONResponse({"ok": False, "error": "REST client non disponibile"}, status_code=500)

        from alexa_tts import speak_on_speakers, _strategy_cache
        msg = "Questo è un annuncio di prova di HomeMind. Il test è andato a buon fine."
        result = await speak_on_speakers(rest_client, speakers, msg, volume)
        ok_count = result["ok"]
        total    = ok_count + result["fail"]
        errors   = result.get("errors", [])

        if ok_count == 0:
            err_detail = errors[0] if errors else "nessun dettaglio"
            return JSONResponse(
                {"ok": False,
                 "error": f"Nessun servizio TTS funzionante. {err_detail}"},
                status_code=500
            )
        # Mostra strategia usata per ogni speaker (aiuta a capire quale integrazione Alexa è attiva)
        strat_labels = {
            "media": "Alexa Media Player (HACS)",
            "devices": "Alexa Devices (ufficiale)",
            "play_media": "TTS generico",
        }
        used = [strat_labels.get(_strategy_cache.get(sp), "—") for sp in speakers if sp in _strategy_cache]
        strat_str = ", ".join(set(used)) if used else ""
        msg_txt = f"Inviato a {ok_count}/{total} speaker"
        if strat_str:
            msg_txt += f" (via {strat_str})"
        return JSONResponse({"ok": True, "message": msg_txt})
    except Exception as e:
        logger.error("Alexa test endpoint error: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Pagina impostazioni — dati caricati lato server, nessun fetch dal browser."""
    import json as _json

    # Carica config attuale
    cfg_path = Path("/config/homemind_patches/person_config.json")
    try:
        cfg = _json.loads(cfg_path.read_text(encoding="utf-8-sig")) if cfg_path.exists() else {}
    except Exception:
        cfg = {}
    for key in ["person_whitelist","person_blacklist","motion_whitelist",
                "motion_blacklist","contact_blacklist"]:
        if key in cfg:
            cfg[key] = [v for v in cfg[key] if not str(v).startswith("_comment")]
    cfg.setdefault("spazzatura_notify_enabled", True)
    cfg.setdefault("spazzatura_notify_hour", 20)
    for k in ["person_whitelist","person_blacklist","motion_whitelist","motion_blacklist","contact_blacklist"]:
        cfg.setdefault(k, [])

    # Costruisci lista entità dal cache HA
    persons, motions, contacts, powers, energies, distances, temps, humids, lights_all, switches_all, covers_all, climate_all, states_all = [], [], [], [], [], [], [], [], [], [], [], [], []
    logger.info("Settings: state_cache ha %d entità", len(state_cache))
    for eid, state in state_cache.items():
        name = state.get("attributes", {}).get("friendly_name", eid)
        st   = state.get("state", "")
        attrs = state.get("attributes", {})
        dev_class = attrs.get("device_class", "")
        unit = attrs.get("unit_of_measurement", "")
        item = (eid, name, st)
        if eid.startswith("person."):
            persons.append(item)
        elif eid.startswith("binary_sensor."):
            if dev_class in ("motion","occupancy") or "occupancy" in eid or "motion" in eid:
                motions.append(item)
            elif dev_class in ("door","window","opening","contact") or "_contact" in eid:
                contacts.append(item)
        elif eid.startswith("sensor."):
            if unit in ("W","VA") or "power" in eid.lower() or "watt" in eid.lower():
                powers.append(item)
            elif (unit in ("kWh","Wh") or "energy" in eid.lower() or "kwh" in eid.lower()
                  or "fv" in eid.lower() or "solar" in eid.lower()
                  or "produz" in eid.lower() or "consumo" in eid.lower()
                  or "enel" in eid.lower() or "batteria" in eid.lower()):
                energies.append(item)
            elif dev_class == "distance" or unit in ("m","km") or "distance" in eid.lower():
                distances.append(item)
            elif dev_class == "temperature" or unit in ("°C","°F") or "temp" in eid.lower():
                temps.append(item)
            elif dev_class == "humidity" or (unit in ("%", "% RH", "%RH") and ("humid" in eid.lower() or "umid" in eid.lower())):
                humids.append(item)
            elif (unit == "" and dev_class in ("", "enum") and
                  any(k in eid.lower() for k in ("operation_state", "program_state",
                                                   "door_state", "machine_state",
                                                   "run_state", "state", "status",
                                                   "mode", "program"))):
                states_all.append(item)
        elif eid.startswith("light."):
            lights_all.append(item)
        elif eid.startswith("switch."):
            switches_all.append(item)
        elif eid.startswith("cover."):
            covers_all.append(item)
        elif eid.startswith("climate."):
            climate_all.append(item)
    persons.sort(key=lambda x: x[1].lower())
    motions.sort(key=lambda x: x[1].lower())
    contacts.sort(key=lambda x: x[1].lower())
    powers.sort(key=lambda x: x[1].lower())
    energies.sort(key=lambda x: x[1].lower())
    distances.sort(key=lambda x: x[1].lower())
    temps.sort(key=lambda x: x[1].lower())
    humids.sort(key=lambda x: x[1].lower())
    lights_all.sort(key=lambda x: x[1].lower())
    switches_all.sort(key=lambda x: x[1].lower())
    covers_all.sort(key=lambda x: x[1].lower())
    climate_all.sort(key=lambda x: x[1].lower())
    logger.info("Settings categorie: persone=%d mov=%d cont=%d pow=%d ene=%d dist=%d temp=%d hum=%d",
                len(persons), len(motions), len(contacts), len(powers), len(energies),
                len(distances), len(temps), len(humids))

    # Calcola api_base per il salvataggio
    # Quando il path è /settings (accesso diretto o Ingress semplice) api_base = ""
    # Quando il path è /api/hassio_ingress/TOKEN/settings, api_base = /api/hassio_ingress/TOKEN
    req_path = str(request.url.path)
    api_base = req_path.replace("/settings", "").rstrip("/")
    # Se api_base è vuota (path diretto /settings), usiamo "" — i path relativi funzionano
    logger.info("Settings: req_path=%s api_base=%s", req_path, api_base)

    # Helper per generare lista checkbox HTML
    def make_list(items, cfg_key, group_name, hide_unavailable=False):
        selected = cfg.get(cfg_key, [])
        html = []
        for eid, name, st in items:
            # Nascondi unavailable se richiesto (sensori movimento)
            if hide_unavailable and st in ("unavailable", "unknown") and eid not in selected:
                continue
            checked = "checked" if eid in selected else ""
            sc = "#22c55e" if st in ("on","home") else ("#ef4444" if st == "unavailable" else "#64748b")
            # Mostra nome leggibile se diverso dall'entity_id
            display_name = name if name != eid else eid.split(".")[-1].replace("_", " ").title()
            html.append(
                f'<label class="ei" data-s="{(name+" "+eid).lower()}">'
                f'<input type="checkbox" name="{group_name}" value="{eid}" {checked}>'
                f'<div class="en">'
                f'<div class="enm">{display_name}</div>'
                f'<div class="eid">{eid}</div>'
                f'</div>'
                f'<span class="est" style="color:{sc}">{st}</span></label>'
            )
        if not html:
            return '<div class="empty">Nessuna entità disponibile</div>'
        return "".join(html)

    def make_radio(items, cfg_key, group_name):
        if not items:
            return '<div class="empty">Nessuna entità trovata in HA</div>'
        energy_cfg = cfg.get("energy_sensors", {})
        raw = energy_cfg.get(cfg_key, "")
        selected = raw if isinstance(raw, str) else (raw[0] if isinstance(raw, list) and raw else "")
        html = []
        for eid, name, st in items:
            checked = "checked" if eid == selected else ""
            html.append(
                f'<label class="ei" data-s="{(name+" "+eid).lower()}">'
                f'<input type="radio" name="{group_name}" value="{eid}" {checked}>'
                f'<div class="en"><div class="enm">{name}</div>'
                f'<div class="eid">{eid}</div></div></label>'
            )
        return "".join(html)

    # SSH vars from environment (set by run.sh from options)
    ssh_host_val     = os.getenv("HM_SSH_HOST", "homeassistant")
    ssh_port_val     = os.getenv("HM_SSH_PORT", "22222")
    ssh_username_val = os.getenv("HM_SSH_USER", "root")
    ssh_password_val = os.getenv("HM_SSH_PASS", "")

    sz_checked = "checked" if cfg.get("spazzatura_notify_enabled", True) else ""
    sz_hour = int(cfg.get("spazzatura_notify_hour", 20))
    sz_alexa_checked = "checked" if cfg.get("spazzatura_alexa_enabled", False) else ""
    sz_alexa_speakers_sel = set(cfg.get("spazzatura_alexa_speakers", []) or [])
    sz_alexa_volume = float(cfg.get("spazzatura_alexa_volume", 0.5))
    # Lista speaker media_player (filtra per vedere solo Alexa/amazon se possibile)
    from alexa_tts import list_alexa_capable_media_players
    _all_speakers = list_alexa_capable_media_players(state_cache)
    # Aggiungi speaker già selezionati ma non presenti (potrebbero essere offline adesso)
    _present_eids = {s["eid"] for s in _all_speakers}
    for _eid in sz_alexa_speakers_sel:
        if _eid not in _present_eids:
            _st_cached = state_cache.get(_eid, {})
            _name_cached = _st_cached.get("attributes", {}).get("friendly_name", _eid)
            _all_speakers.append({
                "eid": _eid, "name": _name_cached,
                "state": _st_cached.get("state", "unknown"),
                "is_alexa": any(kw in (_name_cached+_eid).lower() for kw in ("echo","alexa","amazon")),
            })
    _alexa_opts_html = []
    for _sp in _all_speakers:
        _eid = _sp["eid"]
        _name = _sp["name"]
        _st = _sp["state"]
        _selected = "checked" if _eid in sz_alexa_speakers_sel else ""
        _sc = ("#22c55e" if _st in ("idle", "playing", "paused", "on", "standby") else
               "#ef4444" if _st == "unavailable" else "#94a3b8")
        _badge = " 🟢 Alexa" if _sp.get("is_alexa") else ""
        _alexa_opts_html.append(
            f'<label class="ei" data-s="{(_name+" "+_eid).lower()}">'
            f'<input type="checkbox" name="sz_alexa_sp" value="{_eid}" {_selected}>'
            f'<div class="en"><div class="enm">{_name}{_badge}</div><div class="eid">{_eid}</div></div>'
            f'<span class="est" style="color:{_sc}">{_st}</span></label>'
        )
    sz_alexa_speakers_html = "".join(_alexa_opts_html) if _alexa_opts_html else \
        '<div class="empty">Nessun media_player trovato. Installa l\'integrazione Alexa Media Player in HA.</div>'
    sz_alexa_vol_pct = int(sz_alexa_volume * 100)

    # Stile CSS comune per input inline — definito qui per essere disponibile a tutti i blocchi
    INP = "background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem"

    # ── Variabili Power Guard pre-compilate lato Python ────────────────────
    _pg         = cfg.get("power_guard", {})
    _pg_en      = "checked" if _pg.get("enabled", False) else ""
    _pg_thr     = str(int(_pg.get("threshold_w", 3000)))
    _pg_warn    = str(int(_pg.get("warning_pct", 90)))
    _pg_mode    = _pg.get("mode", "ask")
    _pg_sen     = _pg.get("power_sensor") or _pg.get("sensor", "")
    _pg_delay   = str(int(_pg.get("delay_minutes", 0)))
    _pg_ask     = "selected" if _pg_mode == "ask"       else ""
    _pg_auto    = "selected" if _pg_mode == "auto"      else ""
    _pg_ntf     = "selected" if _pg_mode == "warn_only" else ""
    _pg_apps     = _pg.get("appliances") or _pg.get("appliances_priority", [])
    _pg_app_rows = ""
    for _idx, _pga in enumerate(_pg_apps):
        if not isinstance(_pga, dict): continue
        _pga_n = _pga.get("name", "")
        _pga_e = _pga.get("switch") or _pga.get("climate") or _pga.get("entity", "")
        _pga_p = str(_pga.get("priority", _idx + 1))
        _pg_app_rows += (
            f'<div class="pga-row" style="display:flex;gap:6px;align-items:center;'
            f'margin-bottom:6px;background:#0f172a;border:1px solid #334155;'
            f'border-radius:8px;padding:8px">'
            f'<input class="pga-name" type="text" value="{_pga_n}" placeholder="Lavatrice"'
            f' style="width:110px;{INP}">'
            f'<input class="pga-eid" type="text" value="{_pga_e}"'
            f' placeholder="switch.xxx" style="flex:1;{INP}">'
            f'<input class="pga-pri" type="number" value="{_pga_p}"'
            f' placeholder="1" style="width:50px;{INP}">'
            f'<button type="button" onclick="removePgRow(this)"'
            f' style="background:#7f1d1d;border:none;border-radius:5px;'
            f'color:#fca5a5;padding:4px 7px;cursor:pointer;flex-shrink:0">&#x2715;</button>'
            f'</div>'
        )

    # ── Variabili alarm_on_leave — entità selezionate all'uscita ───────────
    _aol_selected = set(cfg.get("alarm_on_leave", []))

    # ── Variabili Allarme pre-compilate lato Python ────────────────────────
    _alarm_raw  = cfg.get("alarm_panel", "")
    _alarm_pan  = _alarm_raw.get("entity", "") if isinstance(_alarm_raw, dict) else _alarm_raw
    _alarm_pan  = _alarm_pan if isinstance(_alarm_pan, str) else ""
    _alarm_extra_list = cfg.get("alarm_extra_panels", [])
    _alarm_extra_s     = "\n".join(_alarm_extra_list) if isinstance(_alarm_extra_list, list) else ""
    _alarm_extra_delay_val = int(cfg.get("alarm_extra_delay", 1))
    _aam        = cfg.get("alarm_auto_arm", "auto")
    _alarm_dis_ent = "checked" if cfg.get("alarm_disable_entities", True) else ""
    _alarm_dis_notify = "checked" if cfg.get("alarm_disable_notify", True) else ""
    # Leggi lo stato LIVE dall'allarme HA (priorità su config file)
    # Così la UI riflette sempre lo stato reale corrente
    _live_alarm_st = ""
    try:
        _alarm_eid_live, _live_alarm_st = home.primary_alarm() if home else ("", "")
    except Exception:
        _live_alarm_st = ""
    _armed_states = ("armed_away", "armed_home", "armed_night", "armed_vacation")
    # Il dropdown mostra SEMPRE la modalità configurata nel config,
    # non lo stato live (che è già visibile nel banner allarme).
    # Prima usava lo stato live → confondeva: sembrava che il config non venisse salvato.
    _aarm_mode = cfg.get("alarm_arm_mode", "armed_away")
    _aam_auto   = "selected" if _aam == "auto"     else ""
    _aam_notify = "selected" if _aam == "notify"   else ""
    _aam_dis    = "selected" if _aam == "disabled" else ""
    _aarm_away  = "selected" if _aarm_mode == "armed_away"    else ""
    _aarm_home  = "selected" if _aarm_mode == "armed_home"    else ""
    _aarm_night = "selected" if _aarm_mode == "armed_night"   else ""
    _aarm_vac   = "selected" if _aarm_mode == "armed_vacation" else ""

    # ── Variabili Frigate pre-compilate lato Python ───────────────────────
    _fg         = cfg.get("frigate", {})
    fg_enabled  = "checked" if _fg.get("enabled", False) else ""
    fg_host     = _fg.get("host", "")
    fg_port     = int(_fg.get("port", 5000))
    fg_snap     = "checked" if _fg.get("snapshot_on_alarm", True) else ""
    _fg_cams    = _fg.get("cameras", {})
    # Genera opzioni <option> per i sensori movimento — riutilizza la lista motions già calcolata
    _motion_opts = "<option value=\'\'>-- Seleziona sensore --</option>"
    for _meid, _mname, _mst in motions:
        _motion_opts += f"<option value=\'{_meid}\'>{_mname} ({_mst})</option>"
    # Genera righe camere già configurate con select pre-selezionato
    fg_cam_rows = ""
    for _cn, _se in _fg_cams.items():
        _opts = _motion_opts.replace(f"value=\'{_se}\'", f"value=\'{_se}\' selected")
        fg_cam_rows += (
            f'<div style="display:flex;gap:6px;align-items:center;margin-bottom:4px">'
            f'<input type="text" class="fg-cam-name" value="{_cn}" placeholder="Nome in Frigate" '
            f'style="width:130px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">'
            f'<select class="fg-cam-sensor" style="flex:1;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">'
            f'{_opts}</select>'
            f'<button type="button" onclick="this.parentNode.remove()" style="background:#7f1d1d;border:none;border-radius:5px;color:#fca5a5;padding:5px 8px;cursor:pointer;flex-shrink:0">✕</button>'
            f'</div>'
        )
    # Le opzioni sensori vengono caricate via API /api/entities al click

    # ── Avvisi istantanei Frigate per oggetto (switch per nome) ────────────
    _fg_alerts      = _fg.get("alerts", {}) if isinstance(_fg.get("alerts", {}), dict) else {}
    _fg_alert_on    = _fg_alerts.get("labels", {}) if isinstance(_fg_alerts.get("labels", {}), dict) else {}
    try:
        fg_alert_cd = max(0, min(int(_fg_alerts.get("cooldown_s", 60)), 3600))
    except (TypeError, ValueError):
        fg_alert_cd = 60
    try:
        fg_alert_score = max(0, min(int(_fg_alerts.get("min_score_pct", 0)), 100))
    except (TypeError, ValueError):
        fg_alert_score = 0
    # ── Salva file in cartella (tab 📁 File) ───────────────────────────────
    _fi_cfg = cfg.get("file_inbox", {}) if isinstance(cfg.get("file_inbox", {}), dict) else {}
    fi_en  = "checked" if _fi_cfg.get("enabled") is True else ""
    fi_del = "checked" if _fi_cfg.get("delete_after", True) is not False else ""
    _fi_list = []
    for _f in (_fi_cfg.get("folders") or []):
        if isinstance(_f, dict) and str(_f.get("path", "")).strip():
            _fi_list.append({"name": str(_f.get("name", "")), "path": str(_f.get("path", "")),
                             "default": _f.get("default") is True})
    import json as _json_fi
    fi_init_json = _json_fi.dumps(_fi_list, ensure_ascii=False).replace("</", "<\\/")
    fg_alert_rows = ""
    for _al, _aem, _anm in (
        ("person", "👤", "Persone"), ("dog", "🐕", "Cani"), ("cat", "🐈", "Gatti"),
        ("car", "🚗", "Auto"), ("motorcycle", "🏍️", "Moto"), ("bicycle", "🚲", "Bici"),
        ("package", "📦", "Pacchi"), ("bird", "🐦", "Uccelli"),
    ):
        _ach = "checked" if _fg_alert_on.get(_al) is True else ""
        fg_alert_rows += (
            f'<div class="tr" style="margin-top:6px">'
            f'<div><div class="tl">{_aem} {_anm}</div><div class="ts">Foto su Telegram appena rilevati</div></div>'
            f'<label class="sw"><input type="checkbox" class="fga" data-label="{_al}" {_ach}><span class="sl"></span></label>'
            f'</div>'
        )

    # ── Variabili Temperatura/Umidità pre-compilate lato Python ────────────
    _temp_sel  = cfg.get("temperature_sensors", [])
    _humi_sel  = cfg.get("humidity_sensors", [])

    # ── Variabili Proximity pre-compilate lato Python ──────────────────────
    _prox = cfg.get("proximity_sensors", {})
    # Genera opzioni sensori distanza dal cache HA
    _dist_opts = "<option value=''>-- Seleziona sensore distanza --</option>"
    for _deid, _dname, _dst in distances:
        _dist_opts += f"<option value='{_deid}'>{_dname} ({_dst})</option>"
    # Genera righe proximity già configurate
    prox_rows = ""
    for _ppers, _pconf in _prox.items():
        if not isinstance(_pconf, dict):
            continue
        _psens  = _pconf.get("sensor", "")
        _pthr   = str(_pconf.get("threshold_m", 100))
        _pzy    = str(_pconf.get("zone_yellow_m", ""))  # "" = disattivata
        _pzw    = str(_pconf.get("zone_yellow_wait_min", 5))
        _pwifi  = _pconf.get("wifi_tracker", "")
        _preq   = str(_pconf.get("require", 1))
        _req1   = "selected" if _preq == "1" else ""
        _req2   = "selected" if _preq == "2" else ""
        _req3   = "selected" if _preq == "3" else ""
        _pstale = "checked" if _pconf.get("stale_check", False) else ""
        _pdist_opts_sel = _dist_opts.replace(
            f"value='{_psens}'", f"value='{_psens}' selected"
        ) if _psens else _dist_opts
        prox_rows += (
            f'<div class="prox-row" data-person="{_ppers}" style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px;margin-bottom:8px">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
            f'<span style="font-size:.8rem;color:#94a3b8;flex-shrink:0">👤</span>'
            f'<input class="px-pers" type="text" value="{_ppers}" placeholder="person.mario" style="flex:1;{INP}">'
            f'<button type="button" onclick="removeProxRow(this)" style="background:#7f1d1d;border:none;border-radius:5px;color:#fca5a5;padding:5px 8px;cursor:pointer">✕</button>'
            f'</div>'
            f'<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:6px">'
            f'<select class="px-sen" style="flex:1;min-width:160px;{INP}">{_pdist_opts_sel}</select>'
            f'<input class="px-thr" type="number" value="{_pthr}" title="Soglia in casa (m)" style="width:60px;{INP}">'
            f'<span style="font-size:.72rem;color:#64748b">m</span>'
            f'</div>'
            f'<div style="display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:5px">'
            f'<span style="font-size:.7rem;color:#64748b;flex-shrink:0">🟡Gialla</span>'
            f'<input class="px-zy" type="number" value="{_pzy}" placeholder="500" title="Zona gialla (m) — vuoto=off" style="width:60px;{INP}">'
            f'<span style="font-size:.7rem;color:#64748b">m</span>'
            f'<input class="px-zw" type="number" value="{_pzw}" title="Attesa zona gialla (min)" style="width:46px;{INP}">'
            f'<span style="font-size:.7rem;color:#64748b">min</span>'
            f'</div>'
            f'<div style="display:flex;gap:5px;align-items:center;flex-wrap:wrap">'
            f'<span style="font-size:.7rem;color:#64748b;flex-shrink:0">📶WiFi</span>'
            f'<input class="px-wifi" type="text" value="{_pwifi}" placeholder="device_tracker.xxx (opz.)" style="flex:1;min-width:130px;{INP}">'
            f'<select class="px-req" title="Fonti necessarie" style="width:82px;{INP}">'
            f'<option value="1" {_req1}>1-GPS</option>'
            f'<option value="2" {_req2}>2 fonti</option>'
            f'<option value="3" {_req3}>3 fonti</option>'
            f'</select>'
            f'</div>'
            f'</div>'
        )


    # ── Variabili Location Tracker pre-compilate lato Python ──────────────
    _lt = cfg.get("location_tracker", {})
    lt_rows = ""
    for _ltname, _lteid in _lt.items():
        if not isinstance(_lteid, str):
            continue
        lt_rows += (
            f'<div class="lt-row" style="display:flex;align-items:center;gap:8px;'
            f'margin-bottom:8px;background:#0f172a;border:1px solid #334155;'
            f'border-radius:8px;padding:10px">'
            f'<span style="font-size:.8rem;color:#94a3b8;flex-shrink:0">👤</span>'
            f'<input class="lt-name" type="text" value="{_ltname}"'
            f' placeholder="agostino" style="width:120px;{INP}">'
            f'<span style="font-size:.75rem;color:#94a3b8;flex-shrink:0">→</span>'
            f'<input class="lt-eid" type="text" value="{_lteid}"'
            f' placeholder="device_tracker.sm_s931b" style="flex:1;{INP}">'
            f'<button type="button" onclick="removeLtRow(this)"'
            f' style="background:#7f1d1d;border:none;border-radius:5px;'
            f'color:#fca5a5;padding:5px 8px;cursor:pointer;flex-shrink:0">&#x2715;</button>'
            f'</div>'
        )

    # ── Variabili Elettrodomestici pre-compilate lato Python ─────────────
    _apps = cfg.get("appliances", {})
    _pow_opts = "<option value=''>-- Seleziona sensore (opzionale) --</option>"
    for _peid, _pname, _pst in powers + energies:
        _pow_opts += f"<option value='{_peid}'>{_pname} ({_pst})</option>"
    app_rows = ""
    for _akey, _av in _apps.items():
        if not isinstance(_av, dict): continue
        _en   = "checked" if _av.get("enabled", True) else ""
        _anm  = _av.get("name", _akey)
        _aico = _av.get("icon", "\U0001f3e0")
        _amod = _av.get("mode", "power")
        _apse = _av.get("power_sensor") or _av.get("state_sensor", "")
        _apon = str(_av.get("power_on_threshold", 50))
        _apof = str(_av.get("power_off_threshold", 10))
        _amin = str(_av.get("min_cycle_minutes", 20))
        _am_p = "selected" if _amod == "power" else ""
        _am_s = "selected" if _amod == "smart" else ""
        _apow_opts_sel = _pow_opts.replace(
            f"value='{_apse}'", f"value='{_apse}' selected"
        ) if _apse else _pow_opts
        # Campi extra non visibili nel form (es. running_states, done_states, program_sensor, door_sensor)
        _extra_fields = {k: v for k, v in _av.items()
                         if k not in ('enabled','name','icon','mode',
                                      'power_sensor','state_sensor',
                                      'power_on_threshold','power_off_threshold',
                                      'min_cycle_minutes','max_idle_minutes',
                                      'notify_on_start')}
        _extra_json = _extra_fields and json.dumps(_extra_fields, ensure_ascii=False).replace('"',"&quot;") or ''
        app_rows += (
            f'<div class="app-row" data-key="{_akey}" data-extra="{_extra_json}" style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px;margin-bottom:8px">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
            f'<input class="a-ico" type="text" value="{_aico}" title="Icona emoji" style="width:38px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem;text-align:center;font-size:1.1rem">'
            f'<input class="a-nm" type="text" value="{_anm}" placeholder="Nome" style="flex:1;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">'
            f'<label style="display:flex;align-items:center;gap:5px;font-size:.75rem;color:#94a3b8">'
            f'<input type="checkbox" class="a-en" {_en} style="width:15px;height:15px;accent-color:#22c55e"> Attivo</label>'
            f'<button type="button" onclick=\"removeAppRow(this)\" '
            f'style="background:#7f1d1d;border:none;border-radius:5px;color:#fca5a5;padding:5px 8px;cursor:pointer">✕</button>'
            f'</div>'
            f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
            f'<select class="a-mod" style="width:130px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">'
            f'<option value="power" {_am_p}>⚡ Power (W)</option>'
            f'<option value="smart" {_am_s}>🧠 Smart (stato)</option></select>'
            f'<select class="a-sen" style="flex:1;min-width:180px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">{_apow_opts_sel}</select>'
            f'</div>'
            f'<div style="display:flex;gap:8px;margin-top:6px;align-items:center;font-size:.75rem;color:#94a3b8">'
            f'<span>ON soglia:</span><input class="a-pon" type="number" value="{_apon}" style="width:58px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem"><span>W &nbsp;</span>'
            f'<span>OFF soglia:</span><input class="a-pof" type="number" value="{_apof}" style="width:58px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem"><span>W &nbsp;</span>'
            f'<span>Ciclo min:</span><input class="a-min" type="number" value="{_amin}" style="width:55px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem"></div>'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Impostazioni HomeMind</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:14px;font-size:14px}}
h1{{color:#38bdf8;font-size:1rem;margin-bottom:3px}}
.sub{{color:#64748b;font-size:.75rem;margin-bottom:14px}}
.tabs{{display:flex;gap:4px;margin-bottom:12px;flex-wrap:wrap}}
.tab{{background:#1e293b;border:1px solid #334155;color:#94a3b8;border-radius:6px;padding:5px 10px;font-size:.74rem;cursor:pointer}}
.tab.active{{background:#38bdf8;color:#0f172a;font-weight:700;border-color:#38bdf8}}
.tc{{display:none}}.tc.active{{display:block}}
.sec{{background:#1e293b;border-radius:10px;padding:14px;margin-bottom:10px}}
.sec.bl{{border-left:4px solid #38bdf8}}.sec.gr{{border-left:4px solid #22c55e}}
.sec.or{{border-left:4px solid #f59e0b}}.sec.pu{{border-left:4px solid #8b5cf6}}
h2{{font-size:.85rem;font-weight:700;margin-bottom:8px}}
.desc{{font-size:.72rem;color:#64748b;margin-bottom:10px;line-height:1.5}}
.el-label{{font-size:.74rem;color:#94a3b8;margin-bottom:5px;display:block}}
input.search{{width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 9px;font-size:.8rem;margin-bottom:5px}}
input.search:focus{{outline:none;border-color:#38bdf8}}
.elist{{max-height:180px;overflow-y:auto;background:#0f172a;border:1px solid #334155;border-radius:7px;padding:6px}}
.ei{{display:flex;align-items:center;gap:7px;padding:5px 5px;border-radius:5px;cursor:pointer}}
.ei:hover{{background:#1e293b}}
.ei input{{width:15px;height:15px;accent-color:#38bdf8;flex-shrink:0}}
.en{{flex:1;min-width:0}}
.enm{{font-size:.8rem}}
.eid{{font-size:.66rem;color:#475569;font-family:monospace}}
.est{{font-size:.67rem;padding:1px 5px;border-radius:3px;background:#33415540;flex-shrink:0}}
.empty{{font-size:.76rem;color:#475569;padding:8px}}
.tr{{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #334155}}
.tr:last-child{{border:none}}
.tl{{font-size:.84rem}}.ts{{font-size:.7rem;color:#64748b}}
.sw{{position:relative;display:inline-block;width:42px;height:23px;flex-shrink:0}}
.sw input{{opacity:0;width:0;height:0}}
.sl{{position:absolute;inset:0;background:#334155;border-radius:99px;cursor:pointer;transition:.2s}}
.sl:before{{content:'';position:absolute;width:17px;height:17px;left:3px;top:3px;background:#94a3b8;border-radius:50%;transition:.2s}}
input:checked+.sl{{background:#22c55e}}
input:checked+.sl:before{{transform:translateX(19px);background:#fff}}
.ni{{background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:5px 8px;width:65px;font-size:.84rem;text-align:center}}
.esec{{margin-bottom:10px}}
.sbtn{{background:#22c55e;border:none;border-radius:9px;color:#fff;padding:11px;font-size:.88rem;font-weight:700;width:100%;margin-top:6px;cursor:pointer}}
.sbtn:hover{{background:#16a34a}}
.smsg{{text-align:center;font-size:.8rem;margin-top:7px;min-height:1rem;padding:6px;border-radius:6px}}
.smsg.ok{{background:#14532d;color:#86efac}}.smsg.err{{background:#450a0a;color:#fca5a5}}
</style></head><body>
<h1>⚙️ Impostazioni HomeMind</h1>
<div class="sub">Configura senza modificare file. Dati caricati da Home Assistant.</div>
<div class="tabs">
  <button class="tab active" data-tab="p" onclick="showTab('p')">👤 Persone</button>
  <button class="tab" data-tab="m" onclick="showTab('m')">🔔 Allarme</button>
  <button class="tab" data-tab="s" onclick="showTab('s')">🚶 Sensori</button>
  <button class="tab" data-tab="z" onclick="showTab('z')">🗑️ Spazzatura</button>
  <button class="tab" data-tab="e" onclick="showTab('e')">⚡ Energia</button>
  <button class="tab" data-tab="f" onclick="showTab('f')">📹 Frigate</button>
  <button class="tab" data-tab="a" onclick="showTab('a')">🏠 Elettrod.</button>
  <button class="tab" data-tab="t" onclick="showTab('t')">🌡️ Temp/Umid</button>
  <button class="tab" data-tab="x" onclick="showTab('x')">📍 Proximity</button>
  <button class="tab" data-tab="l" onclick="showTab('l')">📱 Tracker</button>
  <button class="tab" data-tab="c" onclick="showTab('c')">🌡️ Clima</button>
  <button class="tab" data-tab="g" onclick="showTab('g')">⚡ Guard</button>
  <button class="tab" data-tab="i" onclick="showTab('i')">📁 File</button>
</div>

<div id="tc-p" class="tc active">
  <div class="sec bl">
    <h2>👤 Persone monitorate</h2>
    <div class="desc">Seleziona chi HomeMind deve monitorare per la presenza e l'allarme. Escludi bot o entità non umane.</div>
    <div class="esec">
      <span class="el-label">✅ Da monitorare (whitelist)</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('pw',this.value)">
      <div class="elist" id="pw">{make_list(persons, 'person_whitelist', 'pw')}</div>
    </div>
    <div class="esec" style="margin-top:10px">
      <span class="el-label">❌ Da escludere (blacklist)</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('pb',this.value)">
      <div class="elist" id="pb">{make_list(persons, 'person_blacklist', 'pb')}</div>
    </div>
  </div>
</div>

<div id="tc-s" class="tc">
  <div class="sec gr">
    <h2>🚶 Sensori movimento</h2>
    <div class="desc">Whitelist: usati per rilevare intrusioni. Blacklist: ignorati (es. sensore telefono).</div>
    <div class="esec">
      <span class="el-label">✅ Da usare (whitelist)</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('mw',this.value)">
      <div class="elist" id="mw">{make_list(motions, 'motion_whitelist', 'mw', True)}</div>
    </div>
    <div class="esec" style="margin-top:10px">
      <span class="el-label">❌ Da ignorare (blacklist)</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('mb',this.value)">
      <div class="elist" id="mb">{make_list(motions, 'motion_blacklist', 'mb', True)}</div>
    </div>
  </div>
  <div class="sec or" style="margin-top:0">
    <h2>🚪 Porte e finestre monitorate</h2>
    <div class="desc">HomeMind monitora <strong>automaticamente tutte</strong> le porte e finestre. Spunta qui solo quelle che vuoi <strong>escludere</strong> (es. una finestra che tieni sempre aperta).</div>
    <div class="esec">
      <span class="el-label">🚫 Escludi dal monitoraggio</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('cb',this.value)">
      <div class="elist" id="cb">{make_list(contacts, 'contact_blacklist', 'cb', True)}</div>
    </div>
  </div>
</div>

<div id="tc-z" class="tc">
  <div class="sec pu">
    <h2>🗑️ Notifiche spazzatura</h2>
    <div class="desc">Abilita/disabilita le notifiche serali e cambia l'orario — senza riavviare l'addon.</div>
    <div class="tr">
      <div><div class="tl">🔔 Notifiche attive</div><div class="ts">Messaggio Telegram ogni sera</div></div>
      <label class="sw"><input type="checkbox" id="sze" {sz_checked}><span class="sl"></span></label>
    </div>
    <div class="tr">
      <div><div class="tl">🕐 Ora notifica</div><div class="ts">0-23</div></div>
      <input type="number" class="ni" id="szh" min="0" max="23" value="{sz_hour}">
    </div>
  </div>

  <div class="sec pu">
    <h2>🔊 Annuncio vocale Alexa</h2>
    <div class="desc">Oltre al messaggio Telegram, HomeMind può annunciare via voce sugli speaker Alexa alla stessa ora configurata sopra. Richiede l'integrazione <b>Alexa Media Player</b> in Home Assistant.</div>
    <div class="tr">
      <div><div class="tl">🔔 Annuncio vocale attivo</div><div class="ts">Messaggio TTS sugli speaker selezionati</div></div>
      <label class="sw"><input type="checkbox" id="sza" {sz_alexa_checked}><span class="sl"></span></label>
    </div>
    <div class="tr">
      <div style="flex:1"><div class="tl">🔊 Volume annuncio</div><div class="ts">Il volume viene impostato automaticamente prima dell'annuncio</div></div>
      <input type="range" id="szvol" min="0" max="100" step="5" value="{sz_alexa_vol_pct}" style="flex:1;max-width:180px">
      <span id="szvol_lbl" style="min-width:40px;text-align:right;color:#94a3b8;font-size:.78rem">{sz_alexa_vol_pct}%</span>
    </div>
    <div style="margin-top:10px">
      <div class="tl" style="margin-bottom:6px">📻 Speaker Alexa (selezione multipla)</div>
      <div class="ts" style="margin-bottom:8px">L'annuncio parte contemporaneamente su tutti gli speaker selezionati.</div>
      <input class="search" type="text" placeholder="🔍 Cerca speaker..." oninput="filt('sz_alexa_list',this.value)">
      <div id="sz_alexa_list" class="el" style="max-height:260px;overflow-y:auto">{sz_alexa_speakers_html}</div>
    </div>
    <div style="margin-top:12px;display:flex;gap:10px;align-items:center">
      <button type="button" onclick="testAlexa()" style="background:#0ea5e9;border:none;border-radius:6px;color:#fff;padding:8px 16px;cursor:pointer;font-size:.85rem;font-weight:600">🔊 Test annuncio</button>
      <span id="sz_test_msg" style="color:#94a3b8;font-size:.78rem"></span>
    </div>
    <div class="ts" style="margin-top:6px">Il test salva prima le impostazioni correnti e poi invia un annuncio di prova sugli speaker selezionati.</div>
  </div>
</div>

<div id="tc-e" class="tc">
  <div class="sec or">
    <h2>⚡ Sensori energia</h2>
    <div class="desc">Seleziona un sensore per categoria. Usati per briefing mattutino e analisi anomalie.</div>
    <div class="esec">
      <span class="el-label">☀️ Produzione FV (kWh/giorno)</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('efv',this.value)">
      <div class="elist" id="efv">{make_radio(energies+powers, 'produzione_fv', 'efv')}</div>
    </div>
    <div class="esec" style="margin-top:10px">
      <span class="el-label">🏠 Consumo casa (kWh/giorno)</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('eca',this.value)">
      <div class="elist" id="eca">{make_radio(energies+powers, 'consumo_casa', 'eca')}</div>
    </div>
    <div class="esec" style="margin-top:10px">
      <span class="el-label">🔌 Rete Enel (kWh/giorno)</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('eel',this.value)">
      <div class="elist" id="eel">{make_radio(energies+powers, 'rete_enel', 'eel')}</div>
    </div>
  </div>
</div>

<div id="tc-f" class="tc">
  <div class="sec" style="border-left:4px solid #7c3aed">
    <h2 style="color:#a78bfa">📹 Frigate NVR</h2>
    <div class="desc">Connetti HomeMind a Frigate per ricevere snapshot su Telegram quando scatta l'allarme. Funziona anche se Frigate &egrave; su un altro PC nella stessa rete.</div>
    <div class="tr" style="margin-top:10px">
      <div><div class="tl">📹 Abilita Frigate</div><div class="ts">Snapshot automatici su Telegram</div></div>
      <label class="sw"><input type="checkbox" id="fg-en" {fg_enabled}><span class="sl"></span></label>
    </div>
    <div style="margin-top:12px;display:flex;gap:8px">
      <div style="flex:1"><div class="el-label" style="margin-bottom:4px">🌐 IP Frigate</div>
      <input type="text" id="fg-host" value="{fg_host}" placeholder="192.168.1.119" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:7px 10px;font-size:.82rem"></div>
      <div style="width:80px"><div class="el-label" style="margin-bottom:4px">🔌 Porta</div>
      <input type="number" id="fg-port" value="{fg_port}" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:7px 8px;font-size:.82rem;text-align:center"></div>
    </div>
    <div class="tr" style="margin-top:12px">
      <div><div class="tl">📷 Snapshot su allarme</div><div class="ts">Foto di tutte le cam quando scatta l'allarme</div></div>
      <label class="sw"><input type="checkbox" id="fg-snap" {fg_snap}><span class="sl"></span></label>
    </div>
    <div style="margin-top:14px">
      <div class="el-label" style="margin-bottom:6px">🎥 Camere — nome Frigate → sensore movimento</div>
      <div class="desc" style="margin-bottom:10px">Il nome deve corrispondere esattamente a quello in Frigate (es. <code style="background:#1e293b;padding:1px 5px;border-radius:3px;color:#7dd3fc">ingresso</code>).</div>
      <div id="fg-cams" style="display:flex;flex-direction:column;gap:6px">{fg_cam_rows}</div>
      <button type="button" onclick="addFgCam()" style="margin-top:8px;background:#334155;border:none;border-radius:6px;color:#94a3b8;padding:6px 14px;font-size:.78rem;cursor:pointer">+ Aggiungi camera</button>
    </div>
    <div style="margin-top:18px;padding-top:14px;border-top:1px solid #334155">
      <div class="el-label" style="margin-bottom:6px">🔔 Avvisi istantanei per oggetto</div>
      <div class="desc" style="margin-bottom:6px">Con lo switch attivo, appena Frigate rileva quell'oggetto ricevi subito la foto su Telegram (indipendente dall'allarme). Funziona solo per gli oggetti tracciati in Frigate. Salva per applicare.</div>
      <div id="fg-alerts">{fg_alert_rows}</div>
      <div style="margin-top:12px;display:flex;align-items:center;gap:10px">
        <div style="flex:1"><div class="tl">⏱️ Pausa tra due avvisi</div><div class="ts">Stesso oggetto sulla stessa camera: secondi di attesa (0 = ogni rilevamento)</div></div>
        <input type="number" id="fg-alert-cd" min="0" max="3600" value="{fg_alert_cd}" style="width:80px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:7px 8px;font-size:.82rem;text-align:center">
      </div>
      <div style="margin-top:12px;display:flex;align-items:center;gap:10px">
        <div style="flex:1"><div class="tl">🎯 Confidenza minima (%)</div><div class="ts">Scarta i falsi allarmi: invia solo se Frigate è sicuro almeno di questa percentuale (es. 80). 0 = nessun filtro</div></div>
        <input type="number" id="fg-alert-score" min="0" max="100" value="{fg_alert_score}" style="width:80px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:7px 8px;font-size:.82rem;text-align:center">
      </div>
    </div>
  </div>
</div>

<div id="tc-a" class="tc">
  <div class="sec" style="border-left:4px solid #22c55e">
    <h2 style="color:#86efac">🏠 Elettrodomestici monitorati</h2>
    <div class="desc">
      HomeMind notifica quando un ciclo finisce (lavatrice, lavastoviglie, forno…).<br>
      <b>⚡ Power</b>: usa un sensore di potenza in Watt — rileva ON/OFF dalla soglia.<br>
      <b>🧠 Smart</b>: usa il sensore stato (es. Home Connect) — rileva da valori testuali.
    </div>
    <div id="app-list">{app_rows if app_rows else '<div class="empty">Nessun elettrodomestico configurato</div>'}</div>
    <button type="button" onclick="addAppRow()" style="margin-top:10px;background:#334155;border:none;border-radius:6px;color:#94a3b8;padding:7px 16px;font-size:.8rem;cursor:pointer;width:100%">
      + Aggiungi elettrodomestico
    </button>
    <div style="margin-top:14px">
      <div class="el-label" style="margin-bottom:6px;color:#64748b;font-size:.72rem">
        📋 Sensori disponibili da HA (potenza/energia) — selezionali dal menu a tendina sopra
      </div>
      <div style="max-height:200px;overflow-y:auto;background:#0f172a;border:1px solid #334155;border-radius:7px;padding:6px">
        <div id="app-sensor-list">
          {make_list(powers + energies, '__dummy_app__', '_app_dummy_')}
        </div>
      </div>
      <div style="font-size:.7rem;color:#475569;margin-top:5px">
        ℹ️ I sensori qui sopra sono solo a titolo informativo — copia l'entity_id nel menu a tendina della riga dell'elettrodomestico.
      </div>
    </div>
  </div>
</div>

<div id="tc-t" class="tc">
  <div class="sec or">
    <h2 style="color:#fdba74">🌡️ Sensori temperatura</h2>
    <div class="desc">
      HomeMind legge <b>solo</b> i sensori qui selezionati per briefing, stato casa e risposte AI.<br>
      Se nessuno è selezionato usa tutti i sensori temperature trovati in HA (meno quelli CPU, sistema, meteo).
    </div>
    <div class="esec">
      <input class="search" type="text" placeholder="🔍 Cerca sensore..." oninput="filt('etmp',this.value)">
      <div class="elist" id="etmp">{make_list(temps, 'temperature_sensors', 'etmp')}</div>
    </div>
  </div>
  <div class="sec" style="border-left:4px solid #67e8f9;margin-top:0">
    <h2 style="color:#67e8f9">💧 Sensori umidità</h2>
    <div class="desc">
      Sensori umidità inclusi nelle risposte AI e nel briefing.<br>
      Se nessuno è selezionato usa tutti i sensori umidità trovati in HA.
    </div>
    <div class="esec">
      <input class="search" type="text" placeholder="🔍 Cerca sensore..." oninput="filt('ehum',this.value)">
      <div class="elist" id="ehum">{make_list(humids, 'humidity_sensors', 'ehum')}</div>
    </div>
  </div>
</div>

<div id="tc-x" class="tc">
  <div class="sec" style="border-left:4px solid #38bdf8">
    <h2 style="color:#7dd3fc">📍 Proximity GPS</h2>
    <div class="desc">
      Rileva automaticamente quando una persona arriva o parte da casa.<br>
      Installa l'integrazione <b>Proximity</b> in HA per ottenere i sensori distanza.
    </div>
    <div id="prox-list">{prox_rows if prox_rows else '<div class="empty">Nessun proximity configurato</div>'}</div>
    <button type="button" onclick="addProxRow()" style="margin-top:10px;background:#334155;border:none;border-radius:6px;color:#94a3b8;padding:7px 16px;font-size:.8rem;cursor:pointer;width:100%">
      + Aggiungi persona
    </button>
    <div style="margin-top:14px">
      <div class="el-label" style="margin-bottom:6px;color:#64748b;font-size:.72rem">
        📡 Sensori distanza disponibili in HA — selezionali dal menu a tendina sopra
      </div>
      <div style="max-height:200px;overflow-y:auto;background:#0f172a;border:1px solid #334155;border-radius:7px;padding:6px">
        <div id="prox-sensor-list">
          {make_list(distances, '__dummy_prox__', '_prox_dummy_')}
        </div>
      </div>
      <div style="font-size:.7rem;color:#475569;margin-top:5px">
        ℹ️ Se non vedi sensori: installa l'integrazione Proximity in HA → crea sensor.casa_mario_distance
      </div>
    </div>
  </div>
</div>

<div id="tc-l" class="tc">
  <div class="sec" style="border-left:4px solid #a78bfa">
    <h2 style="color:#c4b5fd">📱 Location Tracker</h2>
    <div class="desc">
      Associa ogni persona a un <b>device_tracker</b> di Home Assistant per tracciare i suoi spostamenti.<br>
      Permette di chiedere: <i>"dove è stato Agostino oggi?"</i> — HomeMind risponde con indirizzi reali.<br>
      <b>Differenza da Proximity</b>: Proximity gestisce l'allarme; Tracker traccia la cronologia spostamenti.<br>
      Trova il device_tracker: HA → Strumenti Sviluppo → Stati → cerca
      <code style="background:#1e293b;padding:1px 5px;border-radius:3px;color:#c4b5fd">device_tracker.</code>
    </div>
    <div id="lt-list">{lt_rows if lt_rows else '<div class="empty">Nessun tracker configurato</div>'}</div>
    <button type="button" onclick="addLtRow()"
      style="margin-top:10px;background:#334155;border:none;border-radius:6px;
             color:#94a3b8;padding:7px 16px;font-size:.8rem;cursor:pointer;width:100%">
      + Aggiungi persona
    </button>
    <div style="margin-top:12px;padding:10px;background:#1e293b;border-radius:8px;font-size:.73rem;color:#94a3b8;line-height:1.6">
      <b>Nome</b>: come chiami la persona su Telegram (es. <code>agostino</code>, <code>rosa</code>)<br>
      <b>device_tracker</b>: entity_id del tracker HA (es. <code>device_tracker.sm_s931b</code>)<br>
      <b>Comandi:</b> <code>dove è stato Agostino oggi?</code> · <code>percorso di Rosa</code> · <code>soste di Mario</code>
    </div>
  </div>
</div>

<div id="tc-c" class="tc">
  <div class="sec" style="border-left:4px solid #f59e0b">
    <h2 style="color:#fcd34d">🌡️ Sensori temperatura</h2>
    <div class="desc">
      Seleziona quali sensori temperatura HomeMind mostra nel briefing e nei comandi vocali.
      <br>Se nessuno è selezionato, HomeMind usa il rilevamento automatico (esclude CPU, batterie, meteo).
    </div>
    <div class="esec">
      <input class="search" type="text" placeholder="🔍 Cerca sensore..." oninput="filt('tw',this.value)">
      <div class="elist" id="tw">{make_list(temps, 'temperature_sensors', 'tw')}</div>
    </div>
  </div>
  <div class="sec" style="border-left:4px solid #38bdf8;margin-top:0">
    <h2 style="color:#7dd3fc">💧 Sensori umidità</h2>
    <div class="desc">
      Seleziona i sensori di umidità da usare nel briefing e nei comandi.
      <br>Se nessuno è selezionato, HomeMind usa il rilevamento automatico.
    </div>
    <div class="esec">
      <input class="search" type="text" placeholder="🔍 Cerca sensore..." oninput="filt('hw',this.value)">
      <div class="elist" id="hw">{make_list(humids, 'humidity_sensors', 'hw')}</div>
    </div>
  </div>
</div>

<div id="tc-m" class="tc">
  <div class="sec" style="border-left:4px solid #ef4444">
    <h2 style="color:#fca5a5">🔔 Pannello Allarme</h2>
    <div class="desc">
      Configura il pannello allarme principale e le partizioni extra (es. Paradox, DSC multi-zona).<br>
      Trova l'entity_id in HA → Strumenti sviluppatore → Stati → cerca <code style="background:#1e293b;padding:1px 5px;border-radius:3px;color:#7dd3fc">alarm_control_panel.</code>
    </div>
    <div class="esec">
      <span class="el-label">Entity ID pannello allarme principale</span>
      <input type="text" id="alarm-panel-input" value="{_alarm_pan}" placeholder="alarm_control_panel.home_alarm" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">
    </div>
    <div class="esec" style="margin-top:8px">
      <span class="el-label">Partizioni extra — una per riga (opzionale)</span>
      <textarea id="alarm-extra-input" rows="3" placeholder="alarm_control_panel.garage" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem;resize:vertical">{_alarm_extra_s}</textarea>
    </div>
    <div class="esec" style="margin-top:8px">
      <span class="el-label">⏱️ Delay tra partizioni extra (secondi)</span>
      <span class="el-hint">Attesa tra un comando e l'altro sulle partizioni extra — utile per EvoHD/Paradox multi-zone (default: 1s)</span>
      <input type="number" id="alarm-extra-delay" min="0" max="10" value="{_alarm_extra_delay_val}" style="width:80px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">
    </div>
  </div>
  <div class="sec" style="border-left:4px solid #f87171;margin-top:0">
    <h2 style="color:#fca5a5">⚙️ Modalità armamento automatico</h2>
    <div class="desc">
      Scegli come HomeMind gestisce l'antifurto quando tutti escono di casa.<br>
      <b>Nota:</b> se l'utente arma manualmente da HA, HomeMind rileva la modalità e aggiorna automaticamente il config.
    </div>
    <!-- Stato live allarme HA — aggiornato ogni 5s via JS -->
    <div id="alarm-live-banner" style="margin-bottom:10px;padding:8px 12px;border-radius:8px;font-size:.8rem;background:#1e293b;border:1px solid #334155">
      ⏳ Caricamento stato allarme...
    </div>
    <div class="esec">
      <span class="el-label">Comportamento all'uscita</span>
      <select id="alarm-auto-arm" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">
        <option value="auto" {_aam_auto}>🤖 Auto — arma automaticamente (nessuna conferma)</option>
        <option value="notify" {_aam_notify}>🔔 Notify — chiede conferma su Telegram prima di armare</option>
        <option value="disabled" {_aam_dis}>🚫 Disabled — HomeMind non tocca mai l'allarme</option>
      </select>
    </div>
    <!-- Switch visibile solo quando disabled è selezionato -->
    <div id="alarm-dis-ent-row" class="tr" style="margin-top:8px;display:none">
      <div>
        <div class="tl">🔌 Spegni entità all'uscita</div>
        <div class="ts">
          Se ON: spegne luci/clima configurati anche con allarme disabilitato<br>
          Se OFF: solo notifica "casa vuota", non tocca niente
        </div>
      </div>
      <label class="sw"><input type="checkbox" id="alarm-dis-ent" {_alarm_dis_ent}><span class="sl"></span></label>
    </div>
    <!-- Switch notifica — visibile solo quando disabled + spegni entità è OFF -->
    <div id="alarm-dis-notify-row" class="tr" style="margin-top:8px;display:none">
      <div>
        <div class="tl">🔔 Notifica "Casa vuota" su Telegram</div>
        <div class="ts">
          Se ON: manda notifica Telegram quando tutti escono (ma non fa altro)<br>
          Se OFF: silenzio totale — nessuna notifica, nessuna azione
        </div>
      </div>
      <label class="sw"><input type="checkbox" id="alarm-dis-notify" {_alarm_dis_notify}><span class="sl"></span></label>
    </div>
    <div class="esec" style="margin-top:8px">
      <span class="el-label">Modalità di armamento</span>
      <select id="alarm-arm-mode" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">
        <option value="armed_away" {_aarm_away}>🚪 armed_away — via da casa (default)</option>
        <option value="armed_home" {_aarm_home}>🏠 armed_home — a casa con allarme perimetrale</option>
        <option value="armed_night" {_aarm_night}>🌙 armed_night — notturno</option>
        <option value="armed_vacation" {_aarm_vac}>✈️ armed_vacation — in vacanza</option>
      </select>
    </div>
    <div style="margin-top:10px;padding:10px;background:#1e293b;border-radius:8px;font-size:.73rem;color:#94a3b8;line-height:1.6">
      <b>🤖 Auto</b>: HomeMind arma non appena rileva casa vuota, disarma al rientro.<br>
      <b>🔔 Notify</b>: Quando tutti escono, manda un messaggio Telegram con bottoni ✅ Sì / ❌ No. Se non rispondi entro 5 min, non arma.<br>
      <b>🚫 Disabled</b>: HomeMind spegne solo luci e clima, non tocca mai l'allarme.
    </div>
  </div>
  <div class="sec" style="border-left:4px solid #f97316;margin-top:0">
    <h2 style="color:#fdba74">🏠 Entità da spegnere/chiudere all'uscita</h2>
    <div class="desc">
      Seleziona le entità che HomeMind deve gestire quando <b>tutti escono di casa</b>.<br>
      <b>Se nessuna è selezionata</b>: comportamento automatico — spegne tutte le luci accese e il clima.<br>
      <b>Se selezioni almeno una</b>: HomeMind gestisce <b>solo</b> quelle selezionate (luci, switch, tapparelle, clima).
    </div>
    <div class="esec">
      <span class="el-label">💡 Luci</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('aol_l',this.value)">
      <div class="elist" id="aol_l">{make_list(lights_all, 'alarm_on_leave', 'aol_l')}</div>
    </div>
    <div class="esec" style="margin-top:8px">
      <span class="el-label">🔌 Switch / Prese</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('aol_s',this.value)">
      <div class="elist" id="aol_s">{make_list(switches_all, 'alarm_on_leave', 'aol_s')}</div>
    </div>
    <div class="esec" style="margin-top:8px">
      <span class="el-label">🪟 Tapparelle / Cover</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('aol_c',this.value)">
      <div class="elist" id="aol_c">{make_list(covers_all, 'alarm_on_leave', 'aol_c')}</div>
    </div>
    <div class="esec" style="margin-top:8px">
      <span class="el-label">🌡️ Clima / Termostati</span>
      <input class="search" type="text" placeholder="🔍 Cerca..." oninput="filt('aol_t',this.value)">
      <div class="elist" id="aol_t">{make_list(climate_all, 'alarm_on_leave', 'aol_t')}</div>
    </div>
  </div>
</div>

<div id="tc-g" class="tc">
  <div class="sec" style="border-left:4px solid #f87171">
    <h2 style="color:#fca5a5">⚡ Power Guard</h2>
    <div class="desc">
      Monitora il consumo istantaneo e avvisa (o spegne automaticamente) quando supera la soglia contrattuale.<br>
      <b>Trova il sensore:</b> HA → Strumenti Sviluppo → Stati → cerca il sensore in Watt della tua presa o shelly.
    </div>
    <div class="tr">
      <div><div class="tl">⚡ Abilita Power Guard</div><div class="ts">Monitoraggio consumo attivo</div></div>
      <label class="sw"><input type="checkbox" id="pg-en" {_pg_en}><span class="sl"></span></label>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:10px">
      <div>
        <span class="el-label">Soglia (W)</span>
        <input type="number" id="pg-thr" value="{_pg_thr}" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">
      </div>
      <div>
        <span class="el-label">Avviso a % della soglia</span>
        <input type="number" id="pg-warn" value="{_pg_warn}" min="1" max="100" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">
      </div>
    </div>
    <div style="margin-top:8px">
      <span class="el-label">Modalità</span>
      <select id="pg-mode" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">
        <option value="ask" {_pg_ask}>❓ ask — chiede conferma prima di spegnere</option>
        <option value="auto" {_pg_auto}>🤖 auto — spegne automaticamente</option>
        <option value="warn_only" {_pg_ntf}>🔔 warn_only — avvisa solo, non spegne</option>
      </select>
    </div>
    <div style="margin-top:8px">
      <span class="el-label">Sensore potenza totale (W)</span>
      <input type="text" id="pg-sen" value="{_pg_sen}" placeholder="sensor.shellyem_channel_1_power" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">
    </div>
    <div style="margin-top:8px">
      <span class="el-label">⏱️ Ritardo notifica (minuti) — attende N minuti sopra soglia prima di intervenire</span>
      <input type="number" id="pg-delay" value="{_pg_delay}" min="0" max="60" style="width:80px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">
      <span style="font-size:.72rem;color:#64748b;margin-left:8px">0 = interviene immediatamente</span>
    </div>
    <div style="margin-top:12px">
      <span class="el-label">🔌 Entità da spegnere (priorità, 1 = prima)</span>
      <div class="desc" style="margin-bottom:6px">
        Luci, switch, climatizzatori da spegnere quando si supera la soglia.<br>
        <b>Al rientro sotto soglia</b> HomeMind ti notifica — puoi riaccenderli manualmente.<br>
        Colonne: <b>Nome</b> · <b>Entity ID</b> (switch.xxx / climate.xxx / light.xxx) · <b>Priorità</b>
      </div>
      <div id="pg-app-list">{_pg_app_rows if _pg_app_rows else '<div class="empty">Nessuna entità configurata</div>'}</div>
      <button type="button" onclick="addPgRow()"
        style="margin-top:8px;background:#334155;border:none;border-radius:6px;
               color:#94a3b8;padding:6px 14px;font-size:.8rem;cursor:pointer;width:100%">
        + Aggiungi entità
      </button>
    </div>
    <div style="margin-top:10px;padding:10px;background:#1e293b;border-radius:8px;font-size:.73rem;color:#94a3b8;line-height:1.6">
      <b>Esempio:</b> soglia 3000W, avviso 90%, ritardo 1 min &rarr;<br>
      HomeMind avvisa a 2700W; se rimane sopra 3000W per 1 minuto, interviene secondo la modalità scelta.
    </div>
  </div>
</div>

<div id="tc-i" class="tc">
  <div class="sec" style="border-left:4px solid #38bdf8">
    <h2 style="color:#7dd3fc">📁 Salva file dalla chat</h2>
    <div class="desc">
      Mandi un file al bot con la didascalia <b>"invia nella cartella"</b> (oppure <b>"salva in documenti"</b>, con il nome di una cartella qui sotto):
      HomeMind lo salva nella cartella scelta e poi <b>cancella il messaggio da Telegram</b>.
      Se non scrivi nulla, il bot ti mostra i bottoni con le cartelle.<br>
      <b>Percorsi utili:</b> <code>/share/nome</code>, <code>/media/nome</code>, <code>/config/www/nome</code> (quest'ultima è visibile in HA come <code>/local/nome</code>).
      Un file già esistente non viene mai sovrascritto. Limite di Telegram per i bot: <b>20&nbsp;MB</b>. Per non perdere qualità, invia le foto come <b>File</b> (non come foto).
    </div>
    <div class="tr">
      <div><div class="tl">📁 Abilita il salvataggio dei file</div><div class="ts">Se spento il bot si comporta come sempre</div></div>
      <label class="sw"><input type="checkbox" id="fi-en" {fi_en}><span class="sl"></span></label>
    </div>
    <div class="tr" style="margin-top:6px">
      <div><div class="tl">🗑️ Cancella il messaggio da Telegram dopo il salvataggio</div><div class="ts">Solo se il file è stato salvato davvero</div></div>
      <label class="sw"><input type="checkbox" id="fi-del" {fi_del}><span class="sl"></span></label>
    </div>
    <div class="el-label" style="margin-top:14px;margin-bottom:6px">Cartelle (nome · percorso · predefinita)</div>
    <div id="fi-folders" style="display:flex;flex-direction:column;gap:6px"></div>
    <button type="button" onclick="addFiRow('','',false)" style="margin-top:8px;background:#334155;border:none;border-radius:6px;color:#94a3b8;padding:6px 14px;font-size:.78rem;cursor:pointer">+ Aggiungi cartella</button>
    <div class="desc" style="margin-top:10px">La cartella <b>predefinita</b> è quella usata quando scrivi solo "invia nella cartella". Premi <b>Salva</b> per applicare.</div>
  </div>
</div>

<!-- ═══════════════════════════ SEZIONE SSH ════════════════════════════════ -->
<div class="sec bl" id="sec-ssh">
  <h2>🔐 SSH — Terminal &amp; SSH Addon</h2>
  <div class="desc">
    Credenziali per connettere HomeMind all&apos;addon <b>Terminal &amp; SSH</b> di HA.<br>
    Usa il comando Telegram <code>/ssh</code> per eseguire comandi sull&apos;host HA o nel container HomeMind.
  </div>
  <div style="display:grid;gap:12px;max-width:460px;margin-top:12px">
    <label style="display:flex;flex-direction:column;gap:5px;font-size:.85rem;color:#94a3b8">
      🌐 Host SSH <small style="color:#64748b">(usa <code>homeassistant</code> se HA è in locale)</small>
      <input id="ssh_host" type="text" value="{ssh_host_val}"
        style="background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:8px 11px;border-radius:6px;font-size:.9rem;font-family:monospace">
    </label>
    <label style="display:flex;flex-direction:column;gap:5px;font-size:.85rem;color:#94a3b8">
      🔌 Porta SSH <small style="color:#64748b">(l&apos;addon Terminal &amp; SSH usa <b>22222</b>)</small>
      <input id="ssh_port" type="number" value="{ssh_port_val}"
        style="background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:8px 11px;border-radius:6px;font-size:.9rem;width:120px">
    </label>
    <label style="display:flex;flex-direction:column;gap:5px;font-size:.85rem;color:#94a3b8">
      👤 Username <small style="color:#64748b">(impostato nelle opzioni dell&apos;addon Terminal &amp; SSH)</small>
      <input id="ssh_username" type="text" value="{ssh_username_val}"
        style="background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:8px 11px;border-radius:6px;font-size:.9rem;font-family:monospace">
    </label>
    <label style="display:flex;flex-direction:column;gap:5px;font-size:.85rem;color:#94a3b8">
      🔑 Password SSH
      <input id="ssh_password" type="password" value="{ssh_password_val}"
        style="background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:8px 11px;border-radius:6px;font-size:.9rem">
    </label>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:4px">
      <button onclick="testSSH(event)"
        style="background:#0ea5e9;color:white;border:none;padding:9px 18px;border-radius:6px;cursor:pointer;font-size:.88rem;font-weight:600">
        🔗 Testa connessione SSH
      </button>
      <span id="ssh-test-result" style="font-size:.82rem;color:#94a3b8"></span>
    </div>
  </div>
  <div class="tip" style="margin-top:14px;border-color:#22c55e;background:#052e16;color:#86efac">
    ✅ <b>Nessuna configurazione nelle Opzioni HA necessaria.</b><br>
    Le credenziali vengono salvate nel file <code>/config/homemind_patches/person_config.json</code>
    e si applicano immediatamente — HomeMind le rilegge ad ogni riavvio automaticamente.
  </div>
</div>

<button class="sbtn" onclick="save()">💾 Salva impostazioni</button>
<div class="smsg" id="smsg"></div>

<script>
// Calcola API_BASE in modo robusto per iframe in HA Ingress
// window.location.pathname nell'iframe è /settings
// Dobbiamo risalire al path base dell'addon
var FG_SENSOR_OPTS = null; // caricato via API al primo click su + Aggiungi camera
var _p = window.location.pathname;
var API_BASE = _p.split('/settings')[0];
// Se siamo a /settings direttamente, API_BASE = '' -> usiamo origin assoluto
if (!API_BASE) API_BASE = window.location.origin;
else API_BASE = window.location.origin + API_BASE;
function showTab(n){{
  document.querySelectorAll('.tab').forEach(function(t){{t.classList.remove('active');}});
  document.querySelectorAll('.tc').forEach(function(t){{t.classList.remove('active');}});
  document.querySelector('[data-tab="'+n+'"]').classList.add('active');
  document.getElementById('tc-'+n).classList.add('active');
}}
// Tab switching gestito tramite onclick diretto sui bottoni
function filt(id,q){{
  q=q.toLowerCase();
  document.querySelectorAll('#'+id+' .ei').forEach(function(el){{
    el.style.display=!q||el.dataset.s.includes(q)?'':'none';
  }});
}}
function getSel(name){{
  return Array.from(document.querySelectorAll('[name="'+name+'"]:checked')).map(function(i){{return i.value;}});
}}
// Volume slider label live update
(function(){{
  var _sv=document.getElementById('szvol');
  var _sl=document.getElementById('szvol_lbl');
  if(_sv && _sl){{
    _sv.addEventListener('input', function(){{ _sl.textContent=_sv.value+'%'; }});
  }}
}})();
// Test annuncio Alexa
async function testAlexa(){{
  var msgEl=document.getElementById('sz_test_msg');
  var speakers=getSel('sz_alexa_sp');
  if(speakers.length===0){{
    msgEl.style.color='#ef4444';
    msgEl.textContent='⚠️ Nessuno speaker selezionato';
    return;
  }}
  var vol=(parseInt(document.getElementById('szvol').value)||50)/100;
  msgEl.style.color='#fbbf24';
  msgEl.textContent='⏳ Invio annuncio di prova...';
  try{{
    var r=await fetch(API_BASE+'/api/spazzatura/alexa_test',{{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{speakers:speakers,volume:vol}})
    }});
    var res=await r.json();
    if(res.ok){{
      msgEl.style.color='#22c55e';
      msgEl.textContent='✅ '+(res.message||'Annuncio inviato!');
    }}else{{
      msgEl.style.color='#ef4444';
      msgEl.textContent='❌ '+(res.error||'Errore');
    }}
  }}catch(e){{
    msgEl.style.color='#ef4444';
    msgEl.textContent='❌ '+e;
  }}
}}
function getSelOne(name){{
  var el=document.querySelector('[name="'+name+'"]:checked');
  return el?el.value:'';
}}
function addFiRow(name,path,def){{
  var c=document.getElementById("fi-folders");if(!c)return;
  var d=document.createElement("div");d.className="fi-row";
  d.style.cssText="display:flex;gap:6px;align-items:center";
  var st="background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:7px 10px;font-size:.82rem";
  var n=document.createElement("input");n.type="text";n.className="fi-name";n.placeholder="nome (es. documenti)";n.value=name||"";n.style.cssText=st+";width:30%";
  var p=document.createElement("input");p.type="text";p.className="fi-path";p.placeholder="/share/documenti";p.value=path||"";p.style.cssText=st+";flex:1;min-width:0";
  var l=document.createElement("label");l.style.cssText="font-size:.72rem;color:#94a3b8;white-space:nowrap";
  var r=document.createElement("input");r.type="radio";r.name="fi-def";r.className="fi-def";r.checked=!!def;
  l.appendChild(r);l.appendChild(document.createTextNode(" predef."));
  var x=document.createElement("button");x.type="button";x.textContent="✕";
  x.style.cssText="background:#334155;border:none;border-radius:6px;color:#94a3b8;padding:6px 10px;cursor:pointer";
  x.onclick=function(){{d.remove();}};
  d.appendChild(n);d.appendChild(p);d.appendChild(l);d.appendChild(x);c.appendChild(d);
}}
function getFiConfig(){{
  var rows=[],anyDef=false;
  document.querySelectorAll("#fi-folders .fi-row").forEach(function(r){{
    var pa=r.querySelector(".fi-path").value.trim();if(!pa)return;
    var nm=r.querySelector(".fi-name").value.trim()||pa.split("/").filter(Boolean).pop()||"cartella";
    var df=r.querySelector(".fi-def").checked;if(df)anyDef=true;
    rows.push({{name:nm,path:pa,default:df}});
  }});
  if(rows.length&&!anyDef)rows[0].default=true;
  return {{enabled:document.getElementById("fi-en").checked,delete_after:document.getElementById("fi-del").checked,folders:rows}};
}}
var FI_INIT={fi_init_json};
FI_INIT.forEach(function(f){{addFiRow(f.name,f.path,f.default);}});
async function addFgCam(n,s){{
  var c=document.getElementById("fg-cams");
  var d=document.createElement("div");
  d.style.cssText="display:flex;gap:6px;align-items:center;margin-bottom:4px";
  if(!FG_SENSOR_OPTS){{
    try{{
      var r=await fetch(API_BASE+"/api/entities");
      var data=await r.json();
      var motions=(data.motion||[]);
      FG_SENSOR_OPTS='<option value="">-- Seleziona sensore --</option>';
      motions.forEach(function(m){{
        FG_SENSOR_OPTS+='<option value="'+m.id+'">'+m.name+' ('+m.state+')</option>';
      }});
    }}catch(e){{FG_SENSOR_OPTS='<option value="">Errore caricamento</option>';}}
  }}
  var opts=FG_SENSOR_OPTS;
  if(s)opts=opts.replace('value="'+s+'"','value="'+s+'" selected');
  d.innerHTML='<input type="text" class="fg-cam-name" value="'+(n||'')+'" placeholder="Nome in Frigate" '
    +'style="width:130px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">'
    +'<select class="fg-cam-sensor" style="flex:1;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">'+opts+'</select>'
    +'<button type="button" onclick="this.parentNode.remove()" style="background:#7f1d1d;border:none;border-radius:5px;color:#fca5a5;padding:5px 8px;cursor:pointer;flex-shrink:0">✕</button>';
  c.appendChild(d);
}}
function getFgConfig(){{
  var host=document.getElementById("fg-host").value.trim();
  if(!host)return null;
  var cams={{}};
  document.querySelectorAll("#fg-cams>div").forEach(function(r){{
    var n=r.querySelector(".fg-cam-name").value.trim();
    var sel=r.querySelector(".fg-cam-sensor");
    var s=sel?sel.value.trim():'';
    if(n&&s)cams[n]=s;
  }});
  var alerts={{}};
  document.querySelectorAll("#fg-alerts .fga").forEach(function(c){{alerts[c.getAttribute("data-label")]=c.checked;}});
  var cdEl=document.getElementById("fg-alert-cd");
  var cd=cdEl?parseInt(cdEl.value):60;if(isNaN(cd))cd=60;cd=Math.max(0,Math.min(3600,cd));
  var scEl=document.getElementById("fg-alert-score");
  var ms=scEl?parseInt(scEl.value):0;if(isNaN(ms))ms=0;ms=Math.max(0,Math.min(100,ms));
  return{{enabled:document.getElementById("fg-en").checked,host:host,
    port:parseInt(document.getElementById("fg-port").value)||5000,
    snapshot_on_alarm:document.getElementById("fg-snap").checked,cameras:cams,
    alerts:{{labels:alerts,cooldown_s:cd,min_score_pct:ms}}}};
}}
function removeProxRow(btn){{var p=btn.parentNode;while(p&&!p.classList.contains("prox-row"))p=p.parentNode;if(p)p.remove();}}
function addProxRow(){{
  var c=document.getElementById('prox-list');
  var e=c.querySelector('.empty');if(e)e.remove();
  var d=document.createElement('div');
  d.className='prox-row';
  d.style.cssText='background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px;margin-bottom:8px';
  var s="background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem";
  d.innerHTML=
    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'+
    '<span style="font-size:.8rem;color:#94a3b8;flex-shrink:0">👤</span>'+
    '<input class="px-pers" type="text" placeholder="person.mario" style="flex:1;'+s+'">'+
    '<button type="button" onclick="removeProxRow(this)" style="background:#7f1d1d;border:none;border-radius:5px;color:#fca5a5;padding:5px 8px;cursor:pointer">✕</button>'+
    '</div>'+
    '<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:6px">'+
    '<input class="px-sen" type="text" placeholder="sensor.casa_mario_distance" style="flex:1;min-width:160px;'+s+'">'+
    '<input class="px-thr" type="number" value="100" title="Soglia in casa (m)" style="width:60px;'+s+'">'+
    '<span style="font-size:.72rem;color:#64748b">m</span>'+
    '</div>'+
    '<div style="display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:5px">'+
    '<span style="font-size:.7rem;color:#64748b;flex-shrink:0">🟡Gialla</span>'+
    '<input class="px-zy" type="number" placeholder="500" title="Zona gialla (m) — vuoto=off" style="width:60px;'+s+'">'+
    '<span style="font-size:.7rem;color:#64748b">m</span>'+
    '<input class="px-zw" type="number" value="5" title="Attesa (min)" style="width:46px;'+s+'">'+
    '<span style="font-size:.7rem;color:#64748b">min</span>'+
    '</div>'+
    '<div style="display:flex;gap:5px;align-items:center;flex-wrap:wrap">'+
    '<span style="font-size:.7rem;color:#64748b;flex-shrink:0">📶WiFi</span>'+
    '<input class="px-wifi" type="text" placeholder="device_tracker.xxx (opz.)" style="flex:1;min-width:130px;'+s+'">'+
    '<select class="px-req" title="Fonti necessarie" style="width:82px;'+s+'"><option value="1" selected>1-GPS</option><option value="2">2 fonti</option><option value="3">3 fonti</option></select>'+
    '</div>';
  c.appendChild(d);
}}
function getProxCfg(){{
  var out={{}};
  document.querySelectorAll('#prox-list .prox-row').forEach(function(r){{
    var pers=r.querySelector('.px-pers').value.trim();
    var senEl=r.querySelector('.px-sen');
    var sen=senEl?senEl.value.trim():'';
    var thr=parseInt(r.querySelector('.px-thr').value)||100;
    var zyEl=r.querySelector('.px-zy'); var zy=zyEl?zyEl.value.trim():'';
    var zwEl=r.querySelector('.px-zw'); var zw=parseInt(zwEl?zwEl.value:'5')||5;
    var wfEl=r.querySelector('.px-wifi'); var wf=wfEl?wfEl.value.trim():'';
    var rqEl=r.querySelector('.px-req'); var rq=parseInt(rqEl?rqEl.value:'1')||1;
    if(pers&&sen){{
      var cfg={{sensor:sen,threshold_m:thr,stale_check:false,require:rq}};
      if(zy){{cfg.zone_yellow_m=parseInt(zy);cfg.zone_yellow_wait_min=zw;}}
      if(wf)cfg.wifi_tracker=wf;
      out[pers]=cfg;
    }}
  }});
  return out;
}}
function removeAppRow(btn){{var p=btn.parentNode;while(p&&!p.classList.contains("app-row"))p=p.parentNode;if(p)p.remove();}}
function addAppRow(){{
  var c=document.getElementById('app-list');
  var e=c.querySelector('.empty');if(e)e.remove();
  // Costruisce il dropdown sensori dinamicamente via API
  var d=document.createElement('div');
  d.className='app-row';
  d.dataset.key='new_'+Date.now();
  d.style.cssText='background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px;margin-bottom:8px';
  d.innerHTML=
    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'+
    '<input class="a-ico" type="text" value="🏠" title="Icona emoji" style="width:38px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem;text-align:center;font-size:1.1rem">'+
    '<input class="a-nm" type="text" placeholder="Nome elettrodomestico" style="flex:1;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">'+
    '<label style="display:flex;align-items:center;gap:5px;font-size:.75rem;color:#94a3b8">'+
    '<input type="checkbox" class="a-en" checked style="width:15px;height:15px;accent-color:#22c55e"> Attivo</label>'+
    '<button type="button" onclick=\"removeAppRow(this)\" '+
    'style="background:#7f1d1d;border:none;border-radius:5px;color:#fca5a5;padding:5px 8px;cursor:pointer">✕</button>'+
    '</div>'+
    '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'+
    '<select class="a-mod" style="width:130px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">'+
    '<option value="power">⚡ Power (W)</option>'+
    '<option value="smart">🧠 Smart (stato)</option></select>'+
    '<input class="a-sen" type="text" placeholder="sensor.lavatrice_power — incolla entity_id" style="flex:1;min-width:180px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem">'+
    '</div>'+
    '<div style="display:flex;gap:8px;margin-top:6px;align-items:center;font-size:.75rem;color:#94a3b8">'+
    '<span>ON soglia:</span><input class="a-pon" type="number" value="50" style="width:58px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem"><span>W &nbsp;</span>'+
    '<span>OFF soglia:</span><input class="a-pof" type="number" value="10" style="width:58px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem"><span>W &nbsp;</span>'+
    '<span>Ciclo min:</span><input class="a-min" type="number" value="20" style="width:55px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem"></div>';
  c.appendChild(d);
}}
function getAppsCfg(){{
  var out={{}};
  document.querySelectorAll('#app-list .app-row').forEach(function(r){{
    var k=r.dataset.key;
    if(!k)return;
    var mod=r.querySelector('.a-mod').value;
    // a-sen può essere select o input text
    var senEl=r.querySelector('.a-sen');
    var sen=senEl?senEl.value.trim():'';
    var obj={{
      enabled:r.querySelector('.a-en').checked,
      name:r.querySelector('.a-nm').value.trim(),
      icon:r.querySelector('.a-ico').value.trim()||'🏠',
      mode:mod
    }};
    if(mod==='power'){{
      obj.power_sensor=sen;
      obj.power_on_threshold=parseInt(r.querySelector('.a-pon').value)||50;
      obj.power_off_threshold=parseInt(r.querySelector('.a-pof').value)||10;
      obj.min_cycle_minutes=parseInt(r.querySelector('.a-min').value)||20;
      obj.max_idle_minutes=5;
      obj.notify_on_start=false;
    }}else{{
      obj.state_sensor=sen;
      // Preserva i campi extra (running_states, done_states, program_sensor, ecc.)
      // salvati in data-extra al momento del rendering
      var extraRaw=r.dataset.extra||'';
      if(extraRaw){{try{{var ex=JSON.parse(extraRaw);Object.assign(obj,ex);}}catch(e){{}}}}
      // Assicura defaults se non presenti nell'extra
      if(!obj.running_states)obj.running_states=['Run'];
      if(!obj.done_states)obj.done_states=['Finished','Ready','ActionRequired'];
    }}
    out[k]=obj;
  }});
  return out;
}}
// Mostra/nascondi toggle entità e notifica in base a alarm_auto_arm e stato switch
(function(){{
  var sel      = document.getElementById("alarm-auto-arm");
  var rowEnt   = document.getElementById("alarm-dis-ent-row");
  var rowNot   = document.getElementById("alarm-dis-notify-row");
  var chkEnt   = document.getElementById("alarm-dis-ent");
  if(!sel||!rowEnt) return;
  function toggle(){{
    var isDisabled = sel.value==="disabled";
    rowEnt.style.display = isDisabled ? "flex" : "none";
    // Secondo switch: visibile solo se disabled E primo switch è OFF
    if(rowNot){{
      var entOff = isDisabled && chkEnt && !chkEnt.checked;
      rowNot.style.display = entOff ? "flex" : "none";
    }}
  }}
  toggle();
  sel.addEventListener("change", toggle);
  if(chkEnt) chkEnt.addEventListener("change", toggle);
}})();

function getAlarmCfg(){{
  var panel=document.getElementById("alarm-panel-input").value.trim();
  var extraRaw=document.getElementById("alarm-extra-input").value.trim();
  var extra=extraRaw?extraRaw.split(String.fromCharCode(10)).map(function(s){{return s.trim();}}).filter(Boolean):[];
  var aam=document.getElementById("alarm-auto-arm").value;
  var amode=document.getElementById("alarm-arm-mode").value;
  var dis_ent    = document.getElementById("alarm-dis-ent");
  var dis_notify = document.getElementById("alarm-dis-notify");
  var extra_delay=parseInt(document.getElementById("alarm-extra-delay")?.value)||1;
  return{{alarm_panel:panel,alarm_extra_panels:extra,alarm_extra_delay:extra_delay,
          alarm_auto_arm:aam,alarm_arm_mode:amode,
          alarm_disable_entities: dis_ent ? dis_ent.checked : true,
          alarm_disable_notify: dis_notify ? dis_notify.checked : true}};
}}
function removePgRow(btn){{var p=btn.parentNode;while(p&&!p.classList.contains("pga-row"))p=p.parentNode;if(p)p.remove();}}
function addPgRow(){{
  var c=document.getElementById("pg-app-list");
  var e=c.querySelector(".empty");if(e)e.remove();
  var d=document.createElement("div");
  d.className="pga-row";
  d.style.cssText="display:flex;gap:6px;align-items:center;margin-bottom:6px;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:8px";
  var s="background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem";
  d.innerHTML='<input class="pga-name" type="text" placeholder="Lavatrice" style="'+s+';width:110px">'+'<input class="pga-eid" type="text" placeholder="switch.presa_lavatrice" style="'+s+';flex:1;min-width:160px">'+'<input class="pga-pri" type="number" placeholder="1" style="'+s+';width:50px">'+'<button type="button" onclick="removePgRow(this)" style="background:#7f1d1d;border:none;border-radius:5px;color:#fca5a5;padding:4px 7px;cursor:pointer;flex-shrink:0">&#x2715;</button>';
  c.appendChild(d);
}}
function getPowerGuardCfg(){{
  var apps=[];
  document.querySelectorAll("#pg-app-list .pga-row").forEach(function(r,i){{
    var nm=r.querySelector(".pga-name").value.trim();
    var eid=r.querySelector(".pga-eid").value.trim();
    var pri=parseInt(r.querySelector(".pga-pri").value)||i+1;
    if(nm&&eid)apps.push({{name:nm,switch:eid,priority:pri}});
  }});
  return{{
    enabled:document.getElementById("pg-en").checked,
    threshold_w:parseInt(document.getElementById("pg-thr").value)||3000,
    warning_pct:parseInt(document.getElementById("pg-warn").value)||90,
    mode:document.getElementById("pg-mode").value,
    power_sensor:document.getElementById("pg-sen").value.trim(),
    delay_minutes:parseInt(document.getElementById("pg-delay").value)||0,
    appliances_priority:apps
  }};
}}
function removeLtRow(btn){{var p=btn.parentNode;while(p&&!p.classList.contains("lt-row"))p=p.parentNode;if(p)p.remove();}}
function addLtRow(){{
  var c=document.getElementById("lt-list");
  var e=c.querySelector(".empty");if(e)e.remove();
  var d=document.createElement("div");
  d.className="lt-row";
  d.style.cssText="display:flex;align-items:center;gap:8px;margin-bottom:8px;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px";
  var s="background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 8px;font-size:.78rem";
  d.innerHTML='<span style="font-size:.8rem;color:#94a3b8">👤</span>'+'<input class="lt-name" type="text" placeholder="agostino" style="'+s+';width:120px">'+'<span style="font-size:.75rem;color:#94a3b8">→</span>'+'<input class="lt-eid" type="text" placeholder="device_tracker.sm_s931b" style="'+s+';flex:1;min-width:180px">'+'<button type="button" onclick="removeLtRow(this)" style="background:#7f1d1d;border:none;border-radius:5px;color:#fca5a5;padding:5px 8px;cursor:pointer;flex-shrink:0">&#x2715;</button>';
  c.appendChild(d);
}}
function getLtCfg(){{
  var out={{}};
  document.querySelectorAll("#lt-list .lt-row").forEach(function(r){{
    var nm=r.querySelector(".lt-name").value.trim();
    var eid=r.querySelector(".lt-eid").value.trim();
    if(nm&&eid)out[nm]=eid;
  }});
  return out;
}}
// ── Polling stato allarme live ──────────────────────────────────────────
(function alarmLivePoll(){{
  var colors = {{
    "disarmed":      "#14532d",   // verde
    "armed_away":    "#1d4ed8",   // blu
    "armed_home":    "#78350f",   // arancio
    "armed_night":   "#312e81",   // viola
    "armed_vacation":"#164e63",   // teal
    "arming":        "#78350f",
    "pending":       "#78350f",
    "triggered":     "#7f1d1d",   // rosso
  }};
  var borders = {{
    "disarmed":      "#22c55e",
    "armed_away":    "#3b82f6",
    "armed_home":    "#f59e0b",
    "armed_night":   "#818cf8",
    "armed_vacation":"#22d3ee",
    "arming":        "#f59e0b",
    "pending":       "#f59e0b",
    "triggered":     "#ef4444",
  }};
  async function poll(){{
    try{{
      var r = await fetch(API_BASE + "/api/alarm_status");
      var d = await r.json();
      var banner = document.getElementById("alarm-live-banner");
      if(banner){{
        var bg  = colors[d.state]  || "#1e293b";
        var brd = borders[d.state] || "#334155";
        banner.style.background = bg;
        banner.style.border     = "1px solid " + brd;
        var cfg_label = {{
          "armed_away":"🚪 via da casa","armed_home":"🏠 perimetrale",
          "armed_night":"🌙 notturno","armed_vacation":"✈️ vacanza"
        }};
        var cfgStr = d.cfg_arm_mode ? 
          " &nbsp;<b>|</b>&nbsp; 🔧 <i>Configurato: " + (cfg_label[d.cfg_arm_mode]||d.cfg_arm_mode) + "</i>" : "";
        banner.innerHTML = "<b>Stato HA:</b> " + d.label + cfgStr;
      }}
      // NON aggiornare il select "Modalità di armamento" dal polling:
      // il select mostra la PREFERENZA configurata, non lo stato live.
      // Lo stato live è già visibile nel banner sopra.
    }}catch(e){{}}
    setTimeout(poll, 5000);
  }}
  poll();
}})();

async function save(){{
  var msg=document.getElementById('smsg');
  msg.className='smsg';msg.textContent='⏳ Salvataggio...';
  var cfg={{}};
  cfg.person_whitelist=getSel('pw');
  cfg.person_blacklist=getSel('pb');
  var ac=getAlarmCfg();if(ac.alarm_panel)cfg.alarm_panel=ac.alarm_panel;cfg.alarm_extra_panels=ac.alarm_extra_panels;cfg.alarm_extra_delay=ac.alarm_extra_delay;cfg.alarm_auto_arm=ac.alarm_auto_arm;cfg.alarm_arm_mode=ac.alarm_arm_mode;cfg.alarm_disable_entities=ac.alarm_disable_entities;cfg.alarm_disable_notify=ac.alarm_disable_notify;
  cfg.alarm_on_leave=getSel('aol_l').concat(getSel('aol_s')).concat(getSel('aol_c')).concat(getSel('aol_t'));
  cfg.motion_whitelist=getSel('mw');
  cfg.motion_blacklist=getSel('mb');
  cfg.contact_blacklist=getSel('cb');
  cfg.temperature_sensors=getSel('etmp');
  cfg.humidity_sensors=getSel('ehum');
  cfg.proximity_sensors=getProxCfg();
  cfg.location_tracker=getLtCfg();
  cfg.appliances=getAppsCfg();
  cfg.spazzatura_notify_enabled=document.getElementById('sze').checked;
  cfg.spazzatura_notify_hour=parseInt(document.getElementById('szh').value)||20;
  cfg.spazzatura_alexa_enabled=document.getElementById('sza').checked;
  cfg.spazzatura_alexa_speakers=getSel('sz_alexa_sp');
  cfg.spazzatura_alexa_volume=(parseInt(document.getElementById('szvol').value)||50)/100;
  var fv=getSelOne('efv'),ca=getSelOne('eca'),el=getSelOne('eel');
  if(fv||ca||el){{cfg.energy_sensors={{}};if(fv)cfg.energy_sensors.produzione_fv=fv;if(ca)cfg.energy_sensors.consumo_casa=ca;if(el)cfg.energy_sensors.rete_enel=el;}}
  var fg=getFgConfig();if(fg)cfg.frigate=fg;
  cfg.power_guard=getPowerGuardCfg();
  cfg.file_inbox=getFiConfig();
  // SSH credentials — salvate in person_config.json e lette da run.sh via options
  cfg.ssh_host=document.getElementById('ssh_host')?.value||'';
  cfg.ssh_port=parseInt(document.getElementById('ssh_port')?.value)||22222;
  cfg.ssh_username=document.getElementById('ssh_username')?.value||'';
  cfg.ssh_password=document.getElementById('ssh_password')?.value||'';
  try{{
    var r=await fetch(API_BASE+'/api/config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(cfg)}});
    var res=await r.json();
    if(res.ok){{msg.className='smsg ok';msg.textContent='✅ '+res.message;}}
    else{{msg.className='smsg err';msg.textContent='❌ '+res.error;}}
  }}catch(e){{msg.className='smsg err';msg.textContent='❌ '+e;}}
}}

async function testSSH(ev){{
  var btn=ev?ev.target:document.querySelector('[onclick*=testSSH]');
  var res_div=document.getElementById('ssh-test-result');
  btn.disabled=true;btn.textContent='⏳ Test in corso...';
  res_div.textContent='';
  try{{
    var r=await fetch(API_BASE+'/api/ssh_test',{{method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{
        host:document.getElementById('ssh_host').value,
        port:parseInt(document.getElementById('ssh_port').value)||22222,
        username:document.getElementById('ssh_username').value,
        password:document.getElementById('ssh_password').value
      }})
    }});
    var d=await r.json();
    if(d.ok){{res_div.style.color='#4ade80';res_div.textContent='✅ Connessione OK! '+d.message;}}
    else{{res_div.style.color='#f87171';res_div.textContent='❌ '+d.error;}}
  }}catch(e){{res_div.style.color='#f87171';res_div.textContent='❌ '+e;}}
  btn.disabled=false;btn.textContent='🔗 Testa connessione SSH';
}}
</script>
</body></html>"""
    return HTMLResponse(html)



@app.post("/api/ssh_test")
async def api_ssh_test(request: Request):
    """Testa la connessione SSH verso l'addon Terminal & SSH."""
    try:
        body = await request.json()
        host     = body.get("host", "homeassistant")
        port     = int(body.get("port", 22222))
        username = body.get("username", "root")
        password = body.get("password", "")
        try:
            import asyncssh
        except ImportError:
            return JSONResponse({"ok": False, "error": "asyncssh non installato — riavvia l'addon HomeMind."})
        try:
            opts = dict(host=host, port=port, username=username, known_hosts=None, connect_timeout=8)
            if password:
                opts["password"] = password
            async with asyncssh.connect(**opts) as conn:
                res = await conn.run("echo HomeMind_SSH_OK && hostname", timeout=5, check=False)
                out = (res.stdout or "").strip()
                return JSONResponse({"ok": True, "message": f"Host: {out}"})
        except asyncssh.PermissionDenied:
            return JSONResponse({"ok": False, "error": f"Accesso negato a {host}:{port} (user={username}). Verifica username e password."})
        except OSError as e:
            return JSONResponse({"ok": False, "error": f"Connessione fallita a {host}:{port} — {str(e)[:200]}"})
        except Exception as e:
            return JSONResponse({"ok": False, "error": f"Errore SSH: {str(e)[:200]}"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.get("/api/entities")
async def api_entities():
    """Restituisce tutte le entità HA raggruppate per tipo — usato dalla pagina Impostazioni."""
    domains = {
        "person": [], "motion": [], "contact": [],
        "power": [], "energy": [], "distance": [],
        "light": [], "switch": [],
    }
    for eid, state in state_cache.items():
        name = state.get("attributes", {}).get("friendly_name", eid)
        item = {"id": eid, "name": name, "state": state.get("state", "")}
        attrs  = state.get("attributes", {})
        dev_class = attrs.get("device_class", "")
        unit = attrs.get("unit_of_measurement", "")
        if eid.startswith("person."):
            domains["person"].append(item)
        elif eid.startswith("binary_sensor."):
            if dev_class in ("motion","occupancy") or "occupancy" in eid or "motion" in eid:
                domains["motion"].append(item)
            elif dev_class in ("door","window","opening","contact") or "_contact" in eid:
                domains["contact"].append(item)
        elif eid.startswith("sensor."):
            if unit in ("W","VA") or "power" in eid.lower() or "watt" in eid.lower():
                domains["power"].append(item)
            elif unit in ("kWh","Wh") or "energy" in eid.lower() or "kwh" in eid.lower():
                domains["energy"].append(item)
            elif unit in ("m","km") or "distance" in eid.lower():
                domains["distance"].append(item)
        elif eid.startswith("light."):
            domains["light"].append(item)
        elif eid.startswith("switch."):
            domains["switch"].append(item)
    # Ordina per nome
    for k in domains:
        domains[k].sort(key=lambda x: x["name"].lower())
    return JSONResponse(domains)


@app.get("/api/config")
async def api_config_get():
    """Legge la configurazione corrente da person_config.json."""
    cfg_path = Path("/config/homemind_patches/person_config.json")
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig")) if cfg_path.exists() else {}
    except Exception:
        cfg = {}
    # Pulisci commenti dagli array
    for key in ["person_whitelist","person_blacklist","motion_whitelist",
                 "motion_blacklist","contact_blacklist"]:
        if key in cfg:
            cfg[key] = [v for v in cfg[key] if not str(v).startswith("_comment")]
    # Valori default se non presenti
    cfg.setdefault("spazzatura_notify_enabled", True)
    cfg.setdefault("spazzatura_notify_hour", 20)
    cfg.setdefault("person_whitelist", [])
    cfg.setdefault("person_blacklist", [])
    cfg.setdefault("motion_whitelist", [])
    cfg.setdefault("motion_blacklist", [])
    cfg.setdefault("contact_blacklist", [])
    return JSONResponse(cfg)


@app.post("/api/config")
async def api_config_save(request: Request):
    """Salva la configurazione in person_config.json e aggiorna HomeMind in memoria."""
    cfg_path = Path("/config/homemind_patches/person_config.json")
    try:
        # Leggi il body raw per debug BOM
        raw_body = await request.body()
        logger.info("api/config POST: body len=%d, primi 10 bytes hex: %s",
                    len(raw_body), raw_body[:10].hex())
        # Strip BOM se presente
        if raw_body[:3] == b'\xef\xbb\xbf':
            raw_body = raw_body[3:]
            logger.warning("api/config: BOM rimosso dal body")
        import json as _json
        new_cfg = _json.loads(raw_body.decode('utf-8').lstrip('\ufeff'))
        # ── Merge con config esistente — preserva campi avanzati non gestiti dalla UI ──
        # (proximity_sensors, solar_optimizer, appliances, location_tracker, ecc.)
        if cfg_path.exists():
            try:
                existing = _json.loads(cfg_path.read_text(encoding="utf-8-sig"))
                # Campi gestiti dalla UI — vengono sempre sovrascritti
                UI_FIELDS = {
                    "person_whitelist", "person_blacklist",
                    "motion_whitelist", "motion_blacklist",
                    "contact_blacklist", "spazzatura_notify_enabled",
                    "spazzatura_notify_hour", "spazzatura_alexa_enabled",
                    "spazzatura_alexa_speakers", "spazzatura_alexa_volume",
                    "energy_sensors",
                    "temperature_sensors", "humidity_sensors", "proximity_sensors", "temperature_sensors", "humidity_sensors", "appliances", "ai_providers", "frigate",
                    "alarm_panel", "alarm_extra_panels", "alarm_extra_delay", "alarm_auto_arm", "alarm_arm_mode",
                    "alarm_disable_entities", "alarm_disable_notify",
                    "alarm_on_leave", "power_guard", "location_tracker",
                    "ssh_host", "ssh_port", "ssh_username", "ssh_password"
                }
                # Sicurezza: se whitelist è vuota ma nel file esistente c'era dati,
                # probabilmente la UI ha caricato prima che HA avesse le entità → preserva
                if not new_cfg.get("person_whitelist") and existing.get("person_whitelist"):
                    logger.warning("api_config_save: person_whitelist vuota dalla UI — preservo quella esistente")
                    new_cfg["person_whitelist"] = existing["person_whitelist"]
                # Mantieni tutti i campi esistenti non gestiti dalla UI
                for k, v in existing.items():
                    if k not in UI_FIELDS and k not in new_cfg:
                        new_cfg[k] = v
                logger.info("Merge config: preservati %d campi avanzati",
                            len([k for k in existing if k not in UI_FIELDS]))
                # Pagina web vecchia in cache (senza gli switch Frigate): non perdere gli avvisi già impostati
                try:
                    _nf, _ef = new_cfg.get("frigate"), existing.get("frigate")
                    if (isinstance(_nf, dict) and "alerts" not in _nf
                            and isinstance(_ef, dict) and "alerts" in _ef):
                        _nf["alerts"] = _ef["alerts"]
                except Exception:
                    pass
            except Exception as e_merge:
                logger.warning("Merge config fallito: %s — sovrascrittura completa", e_merge)
        # Aggiorna spazzatura immediatamente senza riavvio
        if spazzatura:
            spazzatura.notify_enabled = bool(new_cfg.get("spazzatura_notify_enabled", True))
            spazzatura.notify_hour    = max(0, min(23, int(new_cfg.get("spazzatura_notify_hour", 20))))
            spazzatura.alexa_enabled  = bool(new_cfg.get("spazzatura_alexa_enabled", False))
            spazzatura.alexa_speakers = list(new_cfg.get("spazzatura_alexa_speakers", []) or [])
            spazzatura.alexa_volume   = max(0.0, min(1.0, float(new_cfg.get("spazzatura_alexa_volume", 0.5))))
            logger.info("Spazzatura aggiornata: enabled=%s hour=%d alexa=%s speakers=%d vol=%.2f",
                        spazzatura.notify_enabled, spazzatura.notify_hour,
                        spazzatura.alexa_enabled, len(spazzatura.alexa_speakers),
                        spazzatura.alexa_volume)
        # ── Aggiorna env SSH in memoria (attivo fino al prossimo riavvio) ──
        if "ssh_host" in new_cfg and new_cfg["ssh_host"]:
            os.environ["HM_SSH_HOST"] = str(new_cfg["ssh_host"])
        if "ssh_port" in new_cfg and new_cfg["ssh_port"]:
            os.environ["HM_SSH_PORT"] = str(new_cfg["ssh_port"])
        if "ssh_username" in new_cfg and new_cfg["ssh_username"]:
            os.environ["HM_SSH_USER"] = str(new_cfg["ssh_username"])
        if "ssh_password" in new_cfg:
            os.environ["HM_SSH_PASS"] = str(new_cfg.get("ssh_password",""))
        # Aggiorna HATerminal nel bot Telegram — rilegge da person_config.json appena scritto
        if tg_bot and hasattr(tg_bot, "_ha_terminal"):
            ht = tg_bot._ha_terminal
            if hasattr(ht, "_reload_ssh_from_config"):
                ht._reload_ssh_from_config()
                logger.info("HATerminal SSH ricaricato: %s@%s:%s", ht.ssh_username, ht.ssh_host, ht.ssh_port)

        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(new_cfg, indent=2, ensure_ascii=False))
        logger.info("Configurazione salvata: %s", cfg_path)
        # Applica IMMEDIATAMENTE le nuove impostazioni senza aspettare il rebuild
        if home:
            home.build_from_cache(state_cache)
            logger.info("api/config: home model ricostruito immediatamente")
        return JSONResponse({"ok": True,
            "message": "✅ Salvato e applicato immediatamente — allarme, sensori e modalità attivi adesso."})
    except Exception as e:
        logger.error("Errore salvataggio config: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


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
          "<button class='navbtn' onclick='openPanel(\"regole\",\"📋 Regole\")'>📋</button>"
          "<button class='navbtn' onclick='openPanel(\"settings\",\"⚙️ Impostazioni\")'>⚙️</button>"
          "<button class='navbtn' onclick='openPanel(\"providers\",\"🤖 AI Providers\")'>🤖</button>"
          "<button class='navbtn' onclick='openPanel(\"email\",\"📧 Email\")'>📧</button>"
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
    global ws_client, rest_client, ai, home, security, notifier, tools, state_cache, tg_bot, spazzatura, update_checker, log_analyzer, automations_mgr, history_client, repairs_checker, morning_briefing, entity_registry

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
    security  = SecurityManager(home, rest_client, notifier, ALARM_CODE)  # frigate/tg_bot aggiunti dopo init tg_bot

    # ── Carica stati HA PRIMA di tutti i moduli ────────────────────────────
    all_states  = await rest_client.get_states()
    state_cache = {s["entity_id"]: s for s in all_states}
    home.build_from_cache(state_cache)
    security.set_threshold_override(home.motion_threshold_override)
    security._cache_cb = lambda: state_cache  # necessario per multi-source WiFi check
    # ── Applica Do Not Disturb dal config ─────────────────────────────
    notifier.set_quiet_hours(home.quiet_hours_start, home.quiet_hours_end)
    # Carica person_config per passarlo a HATools (energy_sensors prioritari)
    _tools_pcfg = {}
    try:
        _pcfg_path = Path("/config/homemind_patches/person_config.json")
        if _pcfg_path.exists():
            import json as _j
            _tools_pcfg = _j.loads(_pcfg_path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    tools = HATools(state_cache, home, rest_client, person_cfg=_tools_pcfg)
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
    # ── Override da person_config.json (ha priorità sulle Opzioni addon) ──────
    _cfg_path = Path("/config/homemind_patches/person_config.json")
    if _cfg_path.exists():
        try:
            _cfg = json.loads(_cfg_path.read_text(encoding="utf-8-sig"))
            if "spazzatura_notify_enabled" in _cfg:
                sz_enabled = bool(_cfg["spazzatura_notify_enabled"])
                logger.info("Spazzatura notify_enabled da person_config.json: %s", sz_enabled)
            if "spazzatura_notify_hour" in _cfg:
                sz_hour = int(_cfg["spazzatura_notify_hour"])
                logger.info("Spazzatura notify_hour da person_config.json: %d", sz_hour)
            # Alexa settings
            sz_alexa_enabled  = bool(_cfg.get("spazzatura_alexa_enabled", False))
            sz_alexa_speakers = _cfg.get("spazzatura_alexa_speakers", []) or []
            sz_alexa_volume   = float(_cfg.get("spazzatura_alexa_volume", 0.5))
            if sz_alexa_enabled:
                logger.info("Spazzatura Alexa: abilitato su %d speaker (vol=%.2f)",
                            len(sz_alexa_speakers), sz_alexa_volume)
        except Exception as _e:
            logger.warning("Errore lettura spazzatura config da person_config: %s", _e)
            sz_alexa_enabled, sz_alexa_speakers, sz_alexa_volume = False, [], 0.5
    else:
        sz_alexa_enabled, sz_alexa_speakers, sz_alexa_volume = False, [], 0.5
    spazzatura = SpazzaturaManager(
        ai, notifier,
        notify_hour=sz_hour, notify_enabled=sz_enabled,
        rest_client=rest_client,
        alexa_enabled=sz_alexa_enabled,
        alexa_speakers=sz_alexa_speakers,
        alexa_volume=sz_alexa_volume,
    )
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
    # EntityRegistry PRIMA di AutomationsManager
    entity_registry = EntityRegistry(lambda: state_cache, home=home)
    await entity_registry.start()
    automations_mgr = AutomationsManager(ai, rest_client, notifier,
                                         entity_registry=entity_registry,
                                         telegram_chat_id=TG_CHAT)
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
    global db_manager
    db_manager = HomeMindDB()

    global energy_analyzer
    energy_analyzer = EnergyAnalyzer(
        ai             = ai,
        history_client = history_client,
        notifier       = notifier,
        state_cache_cb = lambda: state_cache,
        db             = db_manager,
    )
    await energy_analyzer.start()

    # ── Appliance Monitor — opzionale, solo se configurato ─────────────────
    global appliance_monitor
    appliance_monitor = ApplianceMonitor(
        notifier       = notifier,
        state_cache_cb = lambda: state_cache,
        ai             = ai,
        db             = db_manager,
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

    # ── Routine Manager ─────────────────────────────────────────────
    global routine_manager
    routine_manager = RoutineManager(
        home           = home,
        notifier       = notifier,
        rest_client    = rest_client,
        state_cache_cb = lambda: state_cache,
        ai             = ai,
        db             = db_manager,
    )
    await routine_manager.start()

    # ── Task Scheduler ──────────────────────────────────────────────────────
    global task_scheduler
    task_scheduler = TaskScheduler(
        notifier       = notifier,
        rest_client    = rest_client,
        ai             = ai,
        action_cb      = _exec_actions,
        state_cache_cb = lambda: state_cache,
        ha_terminal    = ha_terminal if "ha_terminal" in dir() else None,
    )
    await task_scheduler.start()

    # ── Recurring Task Scheduler ─────────────────────────────────────────────
    global recurring_task_scheduler
    recurring_task_scheduler = RecurringTaskScheduler(
        notifier       = notifier,
        rest_client    = rest_client,
        ai             = ai,
        action_cb      = _exec_actions,
        state_cache_cb = lambda: state_cache,
        ha_terminal    = ha_terminal if "ha_terminal" in dir() else None,
    )
    await recurring_task_scheduler.start()

    # ── Power Guard ─────────────────────────────────────────────────────────
    global power_guard
    power_guard = PowerGuard(
        notifier       = notifier,
        rest_client    = rest_client,
        state_cache_cb = lambda: state_cache,
    )
    await power_guard.start()

    # ── Power Guard ─────────────────────────────────────────────────────────

    # ── Config Editor ───────────────────────────────────────────────────────
    global config_editor
    config_editor = ConfigEditor(
        notifier       = notifier,
        lang_cb        = get_lang,
        home_reload_cb = lambda: home._load_config() if home else None,
    )
    logger.info("ConfigEditor pronto")

    # ── Frigate NVR — opzionale, solo se configurato in person_config.json ──
    global frigate_client
    try:
        _pcfg_path = Path("/config/homemind_patches/person_config.json")
        if _pcfg_path.exists():
            _pcfg = json.loads(_pcfg_path.read_text(encoding="utf-8-sig"))
            frigate_client = load_frigate_client(_pcfg)
            if frigate_client:
                ok = await frigate_client.ping()
                if ok:
                    logger.info("Frigate connesso: %s:%d — %d camere",
                                frigate_client.host, frigate_client.port,
                                len(frigate_client.cameras))
                else:
                    logger.warning("Frigate configurato ma non raggiungibile — snapshot disabilitati")
    except Exception as _fe:
        logger.warning("Frigate init errore: %s", _fe)
        frigate_client = None

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
        routine_manager      = routine_manager,
        task_scheduler             = task_scheduler,
        recurring_task_scheduler   = recurring_task_scheduler,
        power_guard          = power_guard,
        config_editor        = config_editor,
        rest_client          = rest_client,
        frigate_client       = frigate_client,
        alarm_code           = ALARM_CODE,
        supervisor_token     = _SUPERVISOR_TOKEN,
        ws_client            = ws_client,
        db                   = db_manager,
    )
    await tg_bot.start()

    # ── Inizializza parser locale (fallback quando AI offline) ───────────
    tg_bot._local_parser = LocalParser(
        home           = home,
        rest_client    = rest_client,
        state_cache_cb = lambda: state_cache,
    )

    # ── Collega routine_manager a security ──────────────────────────────
    if routine_manager and security:
        security.routine_manager = routine_manager
        routine_manager.home = home
    if morning_briefing and routine_manager:
        morning_briefing.routine_manager   = routine_manager
    if morning_briefing and appliance_monitor:
        morning_briefing.appliance_monitor = appliance_monitor

    # ── Aggiorna security con Frigate e TelegramBot (ora disponibili) ───────
    security._frigate = frigate_client
    security._tg_bot  = tg_bot

    # ── Avvisi istantanei Frigate per oggetto (switch dalla pagina web) ─────
    # Inattivo finché nessuno switch è attivo; non influisce su antifurto/snapshot allarme.
    try:
        from agent.frigate_alerts import FrigateAlertWatcher
        asyncio.create_task(FrigateAlertWatcher(tg_bot).run(), name="frigate_alerts")
    except Exception as _fae:
        logger.warning("FrigateAlertWatcher non avviato: %s", _fae)

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
            try:
                import logging as _log
                _sec_log = _log.getLogger("homemind.security")
                _ae, _ast = home.primary_alarm()

                # ── Check 1: allarme armed_away ma qualcuno a casa (GPS) → disarma
                # MA SOLO SE armato da HomeMind — se l'utente ha armato manualmente
                # sapendo che qualcuno era ancora in casa, non dobbiamo intervenire
                if _ast == "armed_away" and not home.everyone_away():
                    _in_casa = home.who_is_home()
                    _gps_home = [eid for eid, v in home.persons.items()
                                 if home._is_home_state(v.get("state", ""))]
                    if _in_casa and _gps_home:
                        if getattr(security, "_last_arm_was_manual", False):
                            _sec_log.info(
                                "Rebuild: allarme armed_away + %s in casa, ma armamento "
                                "era MANUALE → nessun intervento (l'utente sa cosa fa)",
                                _in_casa
                            )
                        else:
                            _sec_log.warning(
                                "Rebuild: allarme armed_away ma %s in casa (GPS) → disarmo emergenza",
                                _in_casa
                            )
                            await security._someone_arrived(", ".join(_in_casa))

                # ── Check 2: GPS dice tutti fuori ma allarme disarmato → arma
                # Gestisce il caso: partenza avvenuta prima del riavvio, o proximity
                # stale che aveva bloccato l'armamento
                elif _ast == "disarmed" and home.everyone_away_gps():
                    _alarm_mode = getattr(home, "_alarm_auto_arm", "auto")
                    if _alarm_mode != "disabled":
                        _sec_log.info(
                            "Rebuild: GPS tutti fuori + allarme disarmato → armo "
                            "(proximity_away=%s)",
                            home.everyone_away()
                        )
                        await security._all_left("(rebuild periodico)")

                # ── Aggiorna _was_away + safety net benvenuto ────────────
                for _peid, _pdata in home.persons.items():
                    _pname = _pdata.get("name", "")
                    if not _pname:
                        continue
                    _gps_away_now = not home._is_home_state(_pdata.get("state", ""))
                    if _gps_away_now:
                        # Imposta _was_away solo se proximity conferma
                        # (o non c'è proximity configurata per questa persona)
                        _prox = home.proximity_sensors.get(_peid, {})
                        _cm = _prox.get("current_m")
                        _thr = float(_prox.get("threshold_m", 100))
                        # Se non c'è proximity O proximity dice fuori → _was_away OK
                        # Se proximity dice vicino (0m) → NON è davvero uscito, evita falso
                        _prox_confirms_away = (_cm is None) or (float(_cm) > _thr)
                        if _prox_confirms_away and not security._was_away.get(_pname, False):
                            security._was_away[_pname] = True
                    else:
                        # GPS dice home — controlla se benvenuto è mancato
                        # Caso: proximity 0m + _was_away=True ma nessun trigger recente
                        _prox_data = home.proximity_sensors.get(_peid, {})
                        _prox_near = home._person_is_home(_peid)
                        _was_away  = security._was_away.get(_pname, False)
                        if _was_away and _prox_near:
                            _last_trig = security._last_arrival_trigger.get(_pname, 0)
                            import time as _t3
                            if _t3.time() - _last_trig > 300:  # > 5 min senza trigger
                                asyncio.create_task(
                                    security._someone_arrived(_pname),
                                    name=f"arrived_rebuild_{_pname}"
                                )

            except Exception as _re:
                pass
    asyncio.create_task(_rebuild(), name="rebuild")

    # Startup check: arma se casa già vuota
    asyncio.create_task(security.startup_check(), name="startup_check")

    # Notifica avvio — messaggio accattivante
    s = home.summary()
    persons_list = [v["name"] for v in home.persons.values()]
    persons_count = len(persons_list)
    # Separa chi è in casa da chi è fuori
    persons_home = []
    persons_away = []
    for v in home.persons.values():
        st = v.get("state", "")
        if home._is_home_state(st):
            persons_home.append(v["name"])
        else:
            persons_away.append(v["name"])
    motions_n = len(home.motion_sensors)
    contacts_n = len(home.contact_sensors)
    alarm_eid = s["alarm_entity"] or "—"
    # Stato allarme corrente
    _, alarm_st = home.primary_alarm()
    alarm_icons = {
        "armed_away":    "🔒 Armato (fuori)",
        "armed_home":    "🏠 Armato (in casa)",
        "armed_night":   "🌙 Armato (notte)",
        "armed_vacation": "✈️ Armato (vacanza)",
        "disarmed":      "🔓 Disarmato",
        "pending":       "⏳ In attivazione",
        "triggered":     "🚨 IN ALLARME!",
    }
    alarm_lbl = alarm_icons.get(alarm_st, alarm_st or "—")
    if not s["everyone_away"]:
        if persons_home:
            casa_lbl = "🏠 Occupata da " + ", ".join(persons_home)
        else:
            casa_lbl = "🏠 Occupata"
    else:
        casa_lbl = "🚪 Vuota — tutti fuori"
    persons_str = ", ".join(persons_list) if persons_list else "nessuna"
    # Version
    version = "1.5.9"
    try:
        import yaml as _yml, os as _os
        _cfp = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "config.yaml")
        if _os.path.exists(_cfp):
            _cfg = _yml.safe_load(open(_cfp))
            version = _cfg.get("version", version)
    except Exception:
        pass

    warn_parts = []
    if not s["has_persons"]:
        warn_parts.append("⚠️ <b>Nessuna person.*</b> — antifurto OFF")
        warn_parts.append("   <i>Crea /config/homemind_patches/person_config.json</i>")
    warn_block = ("\n\n" + "\n".join(warn_parts)) if warn_parts else ""

    # Provider attivi
    try:
        _providers = getattr(ai, "_providers", [])
        prov_str = " → ".join(p.display.split()[0] for p in _providers[:3]) if _providers else "—"
    except Exception:
        prov_str = "—"

    # Layout minimale senza caratteri box (si deformano su mobile)
    # Usiamo solo emoji + HTML bold/italic + separatori standard
    msg_html = (
        f"🎩 <b>HomeMind</b> <code>v{version}</code>\n"
        f"<i>il tuo maggiordomo AI</i>\n"
        f"\n"
        f"✨ <b>Sistema online</b>\n"
        f"\n"
        f"👥 <b>Famiglia</b> ({persons_count})\n"
        + (f"   🏠 In casa: {', '.join(persons_home)}\n" if persons_home else "")
        + (f"   🚶 Fuori: {', '.join(persons_away)}\n" if persons_away else "")
        + "\n"
        f"🏡 <b>Casa:</b> {casa_lbl}\n"
        f"🛡️ <b>Allarme:</b> {alarm_lbl}\n"
        f"\n"
        f"📡 <b>Sensori</b>\n"
        f"   🚶 {motions_n} movimento\n"
        f"   🚪 {contacts_n} contatti\n"
        f"   🏷️ {len(state_cache)} entità\n"
        f"\n"
        f"🤖 <b>AI domotica:</b> <code>{prov_str}</code>"
        + warn_block + "\n"
        f"\n"
        f"<i>Tocca un pulsante per iniziare</i> 👇"
    )
    kb = {"inline_keyboard": [
        [{"text": "📋 Comandi",  "callback_data": "menu_cmd:/comandi"},
         {"text": "🎩 Briefing", "callback_data": "menu_cmd:/briefing"}],
        [{"text": "🛡️ Allarme",  "callback_data": "menu_cmd:/allarme"},
         {"text": "⚡ Energia",  "callback_data": "menu_cmd:/energia"}],
        [{"text": "🤖 Modalità AI", "callback_data": "menu_cmd:/ai_mode"}],
        [{"text": "🏠 Menu principale", "callback_data": "menu_back"},
         {"text": "🗑 Cancella",          "callback_data": "msg_delete"}],
    ]}
    try:
        sent_ok = False
        if hasattr(notifier, "send_with_keyboard"):
            try:
                await notifier.send_with_keyboard(msg_html, kb, force=True)
                sent_ok = True
            except Exception as e_kb:
                logger.warning("send_with_keyboard FAIL: %s", e_kb)
        if not sent_ok:
            await notifier.send_html(msg_html, force=True)
    except Exception as e:
        logger.warning("Startup notify: %s", e)
    # ── Check provider AI all'avvio ──────────────────────────────
    # provider check rimosso — usa /providers su Telegram

    logger.info("HomeMind v58 ready — %d entita, %d persone, %d sensori mov.",
                len(state_cache), len(home.persons), len(home.motion_sensors))

    # ── Email checker ────────────────────────────────────────────────────────
    global email_checker
    email_checker = EmailChecker(
        ai_cb=_email_ai_cb() if ai else None,
        notify_cb=lambda m: asyncio.create_task(
            tg_bot._send(TG_CHAT, m)
        ) if tg_bot and TG_CHAT else None,
    )
    email_checker.start()

async def _shutdown():
    if spazzatura:  await spazzatura.stop()
    if tg_bot:      await tg_bot.stop()
    if notifier:    await notifier.stop()
    if rest_client: await rest_client.stop()
    if email_checker: email_checker.stop()
    logger.info("HomeMind shutdown")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8099,
                log_level=os.getenv("HM_LOG_LEVEL","info").lower())


# ═══════════════════════════════════════════════════════════════════════════════
# 📧 EMAIL MANAGER — Endpoints API + Pagina Web /email
# ═══════════════════════════════════════════════════════════════════════════════

from agent.email_manager import (
    fetch_emails, delete_email, send_email,
    ai_summarize_email, ai_generate_reply, ai_batch_classify,
    schedule_email, cancel_scheduled_email, get_pending_scheduled,
    search_emails, delete_emails_bulk, empty_folder, ai_detect_spam,
    _load_accounts, _load_config as _em_load_cfg, _save_config as _em_save_cfg,
)

# Helper: ai_cb sicuro per email (usa ai.ask con system vuoto)
def _email_ai_cb():
    if not ai:
        return None
    async def _cb(prompt: str) -> str:
        return await ai.ask("Sei un assistente email. Rispondi in italiano.", prompt, max_tokens=1500)
    return _cb


@app.get("/api/email/accounts")
async def api_email_accounts():
    accounts = _load_accounts()
    safe = []
    for a in accounts:
        s = dict(a)
        if s.get("app_password"):
            s["app_password"] = "••••••••"
        safe.append(s)
    return JSONResponse({"accounts": safe})


@app.post("/api/email/accounts/save")
async def api_email_accounts_save(request: Request):
    body = await request.json()
    incoming = body.get("accounts", [])
    cfg = _em_load_cfg()
    existing = {a["address"]: a for a in cfg.get("email_accounts", [])}
    for acc in incoming:
        addr = acc.get("address", "")
        if acc.get("app_password", "").startswith("•") and addr in existing:
            acc["app_password"] = existing[addr].get("app_password", "")
    cfg["email_accounts"] = incoming
    _em_save_cfg(cfg)
    return JSONResponse({"ok": True})


@app.get("/api/email/list")
async def api_email_list(account: str = "", folder: str = "INBOX",
                          max_count: int = 20, classify: bool = False):
    accounts = _load_accounts()
    if account:
        accounts = [a for a in accounts if a["address"] == account]
    enabled = [a for a in accounts if a.get("enabled", True)]
    if not enabled:
        return JSONResponse({"error": "Nessun account configurato/abilitato"}, status_code=400)
    all_emails, errors = [], []
    for acc in enabled:
        try:
            emails = await asyncio.to_thread(fetch_emails, acc, folder, int(max_count))
            all_emails.extend(emails)
        except Exception as e:
            errors.append({"account": acc["address"], "error": str(e)})
    if classify and all_emails and ai:
        all_emails = await ai_batch_classify(all_emails, _email_ai_cb())
    for em in all_emails:
        em.pop("body_text", None)
    return JSONResponse({"emails": all_emails, "errors": errors})


@app.get("/api/email/read")
async def api_email_read(account: str, uid: str, folder: str = "INBOX", summarize: bool = False):
    accounts = _load_accounts()
    acc = next((a for a in accounts if a["address"] == account and a.get("enabled", True)), None)
    if not acc:
        return JSONResponse({"error": "Account non trovato"}, status_code=404)
    try:
        emails = await asyncio.to_thread(fetch_emails, acc, folder, 200)
        em = next((e for e in emails if e["uid"] == uid), None)
        if not em:
            return JSONResponse({"error": "Email non trovata"}, status_code=404)
        if summarize and ai:
            em["ai_summary"] = await ai_summarize_email(em, _email_ai_cb())
        return JSONResponse(em)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/email/delete")
async def api_email_delete(request: Request):
    body = await request.json()
    accounts = _load_accounts()
    acc = next((a for a in accounts if a["address"] == body.get("account", "")), None)
    if not acc:
        return JSONResponse({"error": "Account non trovato"}, status_code=404)
    ok = await asyncio.to_thread(delete_email, acc, body.get("uid", ""),
                                  body.get("folder", "INBOX"), body.get("permanent", False))
    return JSONResponse({"ok": ok})


@app.post("/api/email/reply_draft")
async def api_email_reply_draft(request: Request):
    body = await request.json()
    account_addr = body.get("account", "")
    uid = body.get("uid", "")
    instructions = body.get("instructions", "Rispondi in modo cortese e professionale.")
    style = body.get("style", "professionale")
    accounts = _load_accounts()
    acc = next((a for a in accounts if a["address"] == account_addr), None)
    if not acc:
        return JSONResponse({"error": "Account non trovato"}, status_code=404)
    try:
        # Se uid è vuoto, costruiamo un email_dict diretto dal body
        if uid:
            emails = await asyncio.to_thread(fetch_emails, acc, body.get("folder", "INBOX"), 200)
            em = next((e for e in emails if e["uid"] == uid), None)
            if not em:
                return JSONResponse({"error": "Email non trovata"}, status_code=404)
        else:
            em = {
                "sender": body.get("_direct_sender", ""),
                "subject": body.get("_direct_subject", ""),
                "body_text": body.get("_direct_body", ""),
                "msg_id": "",
            }
        if not ai:
            return JSONResponse({"error": "AI non disponibile"}, status_code=503)
        lang = body.get("lang", "italiano")
        full_instructions = f"{instructions} Rispondi in {lang}."
        draft = await ai_generate_reply(em, full_instructions, _email_ai_cb(), style=style)
        import re as _re2
        m = _re2.search(r"<([^>]+)>", em.get("sender", ""))
        reply_to = m.group(1) if m else em.get("sender", "")
        return JSONResponse({
            "draft": draft,
            "reply_to": reply_to,
            "subject": "Re: " + em["subject"],
            "msg_id": em.get("msg_id", ""),
            "account": account_addr,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/email/send")
async def api_email_send(request: Request):
    """
    Invia email con o senza allegati.
    Accetta sia JSON (senza allegati) sia multipart/form-data (con allegati).
    """
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        # Multipart: campi testo + file allegati
        form = await request.form()
        account_addr = form.get("account", "")
        to           = form.get("to", "")
        subject      = form.get("subject", "")
        text         = form.get("body", "")
        reply_msg_id = form.get("reply_to_msg_id", "")
        scheduled_at = form.get("scheduled_at", "")
        # Raccogli file allegati
        attachments = []
        for key, val in form.multi_items():
            if key == "attachments" and hasattr(val, "read"):
                data = await val.read()
                if data:
                    import mimetypes
                    mime = val.content_type or mimetypes.guess_type(val.filename or "")[0] or "application/octet-stream"
                    attachments.append({
                        "filename": val.filename or "allegato",
                        "data": data,
                        "mimetype": mime,
                    })
    else:
        # JSON standard
        body         = await request.json()
        account_addr = body.get("account", "")
        to           = body.get("to", "")
        subject      = body.get("subject", "")
        text         = body.get("body", "")
        reply_msg_id = body.get("reply_to_msg_id", "")
        scheduled_at = body.get("scheduled_at", "")
        attachments  = []

    if not all([account_addr, to, subject, text]):
        return JSONResponse({"error": "Campi obbligatori mancanti: account, to, subject, body"}, status_code=400)

    accounts = _load_accounts()
    acc = next((a for a in accounts if a["address"] == account_addr), None)
    if not acc:
        return JSONResponse({"error": "Account non trovato"}, status_code=404)

    if scheduled_at:
        task = schedule_email(account_addr, to, subject, text, scheduled_at)
        return JSONResponse({"ok": True, "scheduled": True, "task_id": task["id"], "send_at": scheduled_at})

    if attachments:
        from agent.email_manager import send_email_with_attachments
        ok = await asyncio.to_thread(send_email_with_attachments, acc, to, subject, text, attachments, reply_msg_id)
    else:
        ok = await asyncio.to_thread(send_email, acc, to, subject, text, reply_msg_id)

    return JSONResponse({"ok": ok, "attachments_sent": len(attachments)})


@app.get("/api/email/scheduled")
async def api_email_scheduled():
    return JSONResponse({"scheduled": get_pending_scheduled()})


@app.post("/api/email/scheduled/cancel")
async def api_email_scheduled_cancel(request: Request):
    body = await request.json()
    ok = cancel_scheduled_email(body.get("task_id", ""))
    return JSONResponse({"ok": ok})


@app.get("/api/email/settings")
async def api_email_settings():
    """Ritorna le impostazioni email (intervallo controllo, ecc.)."""
    cfg = _em_load_cfg()
    return JSONResponse({
        "email_check_interval_min": cfg.get("email_check_interval_min", 30),
    })


@app.post("/api/email/settings/save")
async def api_email_settings_save(request: Request):
    """Salva le impostazioni email nel person_config.json."""
    body = await request.json()
    cfg = _em_load_cfg()
    changed = False
    if "email_check_interval_min" in body:
        val = int(body["email_check_interval_min"])
        if 1 <= val <= 1440:
            cfg["email_check_interval_min"] = val
            changed = True
        else:
            return JSONResponse({"error": "Valore fuori range (1-1440)"}, status_code=400)
    if "email_notify_new" in body:
        cfg["email_notify_new"] = bool(body["email_notify_new"])
        changed = True
    if changed:
        _em_save_cfg(cfg)
    return JSONResponse({"ok": changed})
    return JSONResponse({"rules": _em_load_cfg().get("email_auto_reply_rules", [])})


@app.post("/api/email/check_now")
async def api_email_check_now():
    """Forza un controllo email immediato."""
    if email_checker:
        asyncio.create_task(email_checker._run_check())
        return JSONResponse({"ok": True, "message": "Controllo avviato"})
    return JSONResponse({"error": "EmailChecker non attivo"}, status_code=503)


@app.get("/api/email/auto_rules")
async def api_email_auto_rules():
    cfg = _em_load_cfg()
    rules = cfg.get("email_auto_reply_rules", [])
    # Pulisce automaticamente regole con keyword vuota rimaste da versioni vecchie
    cleaned = [r for r in rules if r.get("keyword", "").strip()]
    if len(cleaned) != len(rules):
        cfg["email_auto_reply_rules"] = cleaned
        _em_save_cfg(cfg)
    return JSONResponse({"rules": cleaned})


@app.post("/api/email/auto_rules/save")
async def api_email_auto_rules_save(request: Request):
    body = await request.json()
    incoming = body.get("rules", [])
    # Salva SOLO regole con keyword valorizzata — blocca keyword vuote
    valid = [r for r in incoming if r.get("keyword", "").strip()]
    skipped = len(incoming) - len(valid)
    cfg = _em_load_cfg()
    cfg["email_auto_reply_rules"] = valid
    _em_save_cfg(cfg)
    return JSONResponse({
        "ok": True,
        "saved": len(valid),
        "skipped_empty_keyword": skipped,
    })


@app.get("/api/email/auto_rules/debug")
async def api_email_rules_debug():
    """Diagnostica: mostra regole salvate nel config con dettagli."""
    cfg = _em_load_cfg()
    rules = cfg.get("email_auto_reply_rules", [])
    return JSONResponse({
        "total_rules": len(rules),
        "active_with_keyword": [r for r in rules if r.get("enabled", True) and r.get("keyword","").strip()],
        "empty_keyword": [r for r in rules if not r.get("keyword","").strip()],
        "disabled": [r for r in rules if not r.get("enabled", True)],
    })


@app.get("/api/email/search")
async def api_email_search(account: str, query: str, folder: str = "INBOX",
                            max_count: int = 20):
    accounts = _load_accounts()
    acc = next((a for a in accounts if a["address"] == account and a.get("enabled", True)), None)
    if not acc:
        return JSONResponse({"error": "Account non trovato"}, status_code=404)
    try:
        emails = await asyncio.to_thread(search_emails, acc, query, folder, int(max_count))
        for em in emails:
            em.pop("body_text", None)
        return JSONResponse({"emails": emails})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/email/delete_bulk")
async def api_email_delete_bulk(request: Request):
    body = await request.json()
    accounts = _load_accounts()
    acc = next((a for a in accounts if a["address"] == body.get("account", "")), None)
    if not acc:
        return JSONResponse({"error": "Account non trovato"}, status_code=404)
    uids = body.get("uids", [])
    folder = body.get("folder", "INBOX")
    result = await asyncio.to_thread(delete_emails_bulk, acc, uids, folder)
    return JSONResponse(result)


@app.post("/api/email/empty_folder")
async def api_email_empty_folder(request: Request):
    body = await request.json()
    accounts = _load_accounts()
    acc = next((a for a in accounts if a["address"] == body.get("account", "")), None)
    if not acc:
        return JSONResponse({"error": "Account non trovato"}, status_code=404)
    folder = body.get("folder", "[Gmail]/Trash")
    result = await asyncio.to_thread(empty_folder, acc, folder)
    return JSONResponse(result)


@app.get("/api/email/spam_detect")
async def api_email_spam_detect(account: str, folder: str = "INBOX", max_count: int = 30):
    accounts = _load_accounts()
    acc = next((a for a in accounts if a["address"] == account and a.get("enabled", True)), None)
    if not acc:
        return JSONResponse({"error": "Account non trovato"}, status_code=404)
    ai_cb = _email_ai_cb()
    if not ai_cb:
        return JSONResponse({"error": "AI non disponibile"}, status_code=503)
    try:
        emails = await asyncio.to_thread(fetch_emails, acc, folder, int(max_count))
        emails = await ai_detect_spam(emails, ai_cb)
        for em in emails:
            em.pop("body_text", None)
        spam = [e for e in emails if e.get("spam_score", 0) >= 7]
        return JSONResponse({"emails": emails, "spam_count": len(spam)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)



@app.get("/email", response_class=HTMLResponse)
async def email_page(request: Request):
    req_path = str(request.url.path)
    api_base = req_path.replace("/email", "").rstrip("/")
    accounts = _load_accounts()
    acc_opts_srv = "".join(
        f'<option value="{a["address"]}">{a.get("label") or a["address"]}</option>'
        for a in accounts if a.get("enabled", True)
    ) or '<option value="">— Nessun account —</option>'

    html = f"""<!DOCTYPE html>
<html lang="it"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>📧 Email — HomeMind</title>
<style>
:root{{--bg:#0f172a;--card:#1e293b;--b:#334155;--acc:#3b82f6;--g:#22c55e;--r:#ef4444;--y:#f59e0b;--t:#f1f5f9;--m:#94a3b8}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--t);font-family:system-ui,sans-serif;padding:12px;font-size:15px}}
h1{{font-size:1.25rem;font-weight:700;margin-bottom:12px}}
.tabs{{display:flex;gap:4px;margin-bottom:12px;flex-wrap:wrap}}
.tab{{padding:7px 13px;border-radius:8px;cursor:pointer;background:var(--card);border:1px solid var(--b);color:var(--m);font-size:.8rem;transition:.15s;white-space:nowrap}}
.tab.active{{background:var(--acc);color:#fff;border-color:var(--acc)}}
.panel{{display:none}}.panel.active{{display:block}}
.card{{background:var(--card);border:1px solid var(--b);border-radius:12px;padding:13px;margin-bottom:11px}}
.card h2{{font-size:.9rem;font-weight:600;margin-bottom:9px;color:var(--acc)}}
input,select,textarea{{background:#0f172a;border:1px solid var(--b);color:var(--t);padding:7px 10px;border-radius:8px;width:100%;font-size:.85rem;margin-bottom:7px}}
input[type=checkbox],input[type=radio]{{width:auto;margin:0}}
textarea{{resize:vertical;min-height:80px}}
button{{padding:7px 13px;border-radius:8px;border:none;cursor:pointer;font-size:.8rem;font-weight:600;transition:.15s}}
.bp{{background:var(--acc);color:#fff}}.bp:hover{{opacity:.85}}
.bd{{background:var(--r);color:#fff}}.bs{{background:var(--g);color:#fff}}
.bw{{background:var(--y);color:#000}}.bg{{background:var(--b);color:var(--t)}}
.bsm{{padding:4px 8px;font-size:.74rem}}
.brow{{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px;align-items:center}}
.elist{{display:flex;flex-direction:column;gap:6px}}
.eitem{{background:#0f172a;border:1px solid var(--b);border-radius:9px;padding:10px;cursor:pointer;transition:.15s;position:relative}}
.eitem:hover{{border-color:var(--acc)}}
.eitem.unread{{border-left:3px solid var(--acc)}}
.eitem.sel{{background:#1e3a5f;border-color:var(--acc)}}
.eitem.spam-hi{{border-left:3px solid var(--r)}}
.esel{{position:absolute;top:10px;right:10px;width:18px;height:18px;border-radius:4px;border:2px solid var(--b);background:var(--bg);cursor:pointer}}
.esel.checked{{background:var(--acc);border-color:var(--acc)}}
.eh{{display:flex;justify-content:space-between;gap:6px;padding-right:24px}}
.ef{{font-weight:600;font-size:.8rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:55%}}
.ed{{font-size:.7rem;color:var(--m);white-space:nowrap}}
.es{{font-size:.84rem;margin:3px 0 2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.ep{{font-size:.73rem;color:var(--m);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.lbl{{font-size:.65rem;padding:1px 6px;border-radius:7px;font-weight:700;display:inline-block}}
.ls{{background:#ef444422;color:var(--r)}}.li{{background:#22c55e22;color:var(--g)}}.ln{{background:#334155;color:var(--m)}}
.spam-bar{{background:#ef444422;border:1px solid #ef4444;border-radius:8px;padding:8px;margin-bottom:8px;font-size:.82rem}}
.modal{{display:none;position:fixed;inset:0;background:#000c;z-index:100;align-items:flex-start;justify-content:center;padding:12px;overflow-y:auto}}
.modal.open{{display:flex}}
.mbox{{background:var(--card);border:1px solid var(--b);border-radius:13px;padding:18px;max-width:640px;width:100%;margin:auto}}
.mbox h3{{font-size:.95rem;font-weight:600;margin-bottom:8px;color:var(--acc);padding-right:24px}}
.meta{{font-size:.76rem;color:var(--m);margin-bottom:4px}}
.btext{{background:#0f172a;border:1px solid var(--b);border-radius:8px;padding:10px;font-size:.8rem;white-space:pre-wrap;max-height:260px;overflow-y:auto;margin-top:8px}}
.sumbox{{background:#1e3a5f;border:1px solid #3b82f6;border-radius:8px;padding:9px;font-size:.8rem;margin:7px 0}}
.wstep{{display:none}}.wstep.active{{display:block}}
.sdots{{display:flex;gap:6px;margin-bottom:12px}}
.sdot{{width:24px;height:24px;border-radius:50%;background:var(--b);color:var(--m);display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;transition:.2s;flex-shrink:0}}
.sdot.active{{background:var(--acc);color:#fff}}.sdot.done{{background:var(--g);color:#fff}}
.rrow{{display:flex;gap:5px;align-items:center;flex-wrap:wrap;background:#0f172a;border:1px solid var(--b);border-radius:8px;padding:8px;margin-bottom:6px}}
.rrow input,.rrow select{{margin-bottom:0;flex:1;min-width:100px}}
.arow{{background:#0f172a;border:1px solid var(--b);border-radius:8px;padding:9px;margin-bottom:7px}}
.arow label{{font-size:.76rem;color:var(--m);display:block;margin-bottom:2px}}
.arow input{{margin-bottom:4px}}
.arow .ah{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.spin{{display:inline-block;width:13px;height:13px;border:2px solid var(--b);border-top-color:var(--acc);border-radius:50%;animation:sp .6s linear infinite;flex-shrink:0}}
@keyframes sp{{to{{transform:rotate(360deg)}}}}
.toast{{position:fixed;bottom:16px;right:16px;background:var(--card);border:1px solid var(--b);border-radius:9px;padding:10px 15px;font-size:.8rem;z-index:999;animation:fi .25s;display:none;max-width:280px}}
@keyframes fi{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1}}}}
.g2{{display:grid;grid-template-columns:1fr 1fr;gap:7px}}
@media(max-width:480px){{.g2{{grid-template-columns:1fr}}}}
.srow{{display:flex;gap:6px;align-items:center;flex-wrap:wrap;background:#0f172a;border:1px solid var(--b);border-radius:8px;padding:8px;margin-bottom:5px;font-size:.79rem}}
.tag{{font-size:.67rem;padding:2px 7px;border-radius:8px;font-weight:600}}
.tp{{background:#f59e0b22;color:var(--y)}}.ts{{background:#22c55e22;color:var(--g)}}
.search-bar{{display:flex;gap:7px;margin-bottom:10px}}
.search-bar input{{flex:1;margin-bottom:0}}
.bulk-bar{{display:flex;gap:6px;align-items:center;padding:8px;background:#0f172a;border-radius:8px;margin-bottom:8px;flex-wrap:wrap}}
.bulk-bar span{{font-size:.8rem;color:var(--m);flex:1}}
.score-pill{{display:inline-block;font-size:.65rem;padding:1px 6px;border-radius:7px;font-weight:700;margin-left:4px}}
.score-hi{{background:#ef444430;color:var(--r)}}.score-lo{{background:#22c55e20;color:var(--g)}}
.folder-btns{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}}
</style></head><body>
<h1>📧 Email Manager</h1>
<div class="tabs">
  <div class="tab active" onclick="switchTab('inbox')">📥 Inbox</div>
  <div class="tab" onclick="switchTab('search')">🔍 Cerca</div>
  <div class="tab" onclick="switchTab('spam')">🚫 Spam/Pulizia</div>
  <div class="tab" onclick="switchTab('wizard')">✍️ Rispondi AI</div>
  <div class="tab" onclick="switchTab('sched')">🕐 Programmati</div>
  <div class="tab" onclick="switchTab('rules')">🤖 Auto-risposta</div>
  <div class="tab" onclick="switchTab('accs')">⚙️ Account</div>
</div>

<!-- ═══ INBOX ═══ -->
<div id="panel-inbox" class="panel active">
 <div class="card">
  <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin-bottom:10px">
   <select id="inb-acc" style="flex:1;min-width:160px;margin-bottom:0">{acc_opts_srv}</select>
   <select id="inb-fold" style="width:130px;margin-bottom:0">
    <option value="INBOX">📥 Inbox</option>
    <option value="[Gmail]/Sent Mail">📤 Inviati</option>
    <option value="[Gmail]/Trash">🗑️ Cestino</option>
    <option value="[Gmail]/Spam">🚫 Spam</option>
   </select>
   <button class="bp" onclick="loadEmails()">🔄 Aggiorna</button>
   <label style="display:flex;align-items:center;gap:4px;font-size:.78rem;color:var(--m)">
    <input type="checkbox" id="inb-cls"> AI
   </label>
  </div>
  <!-- Bulk actions bar -->
  <div class="bulk-bar" id="bulk-bar" style="display:none">
   <span id="bulk-count">0 selezionate</span>
   <button class="bd bsm" onclick="bulkDelete()">🗑️ Cestino</button>
   <button class="bg bsm" onclick="clearSel()">✕ Deseleziona</button>
  </div>
  <div id="inbox-list"><div style="color:var(--m);font-size:.86rem">Seleziona account e premi Aggiorna.</div></div>
 </div>
</div>

<!-- ═══ CERCA ═══ -->
<div id="panel-search" class="panel">
 <div class="card">
  <h2>🔍 Cerca email</h2>
  <div class="search-bar">
   <select id="srch-acc" style="width:160px;margin-bottom:0">{acc_opts_srv}</select>
   <select id="srch-fold" style="width:120px;margin-bottom:0">
    <option value="INBOX">📥 Inbox</option>
    <option value="[Gmail]/Sent Mail">📤 Inviati</option>
    <option value="[Gmail]/All Mail">📦 Tutte</option>
   </select>
  </div>
  <div class="search-bar">
   <input id="srch-q" placeholder="Cerca mittente, oggetto… (es: fattura, mario@)" onkeydown="if(event.key==='Enter')doSearch()">
   <button class="bp" onclick="doSearch()">🔍 Cerca</button>
  </div>
  <div id="srch-list"><div style="color:var(--m);font-size:.86rem">Inserisci un termine di ricerca.</div></div>
 </div>
</div>

<!-- ═══ SPAM / PULIZIA ═══ -->
<div id="panel-spam" class="panel">
 <div class="card">
  <h2>🧹 Pulizia intelligente</h2>
  <p style="font-size:.8rem;color:var(--m);margin-bottom:10px">
   L'AI analizza la tua inbox e identifica spam, newsletter e promozioni da eliminare.
  </p>
  <div style="display:flex;gap:7px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
   <select id="spam-acc" style="flex:1;min-width:160px;margin-bottom:0">{acc_opts_srv}</select>
   <button class="bw" onclick="detectSpam()">🤖 Analizza con AI</button>
  </div>
  <div id="spam-result"></div>
 </div>
 <div class="card">
  <h2>🗑️ Svuota cartelle</h2>
  <p style="font-size:.8rem;color:var(--m);margin-bottom:10px">Libera spazio eliminando definitivamente le email nelle cartelle di sistema.</p>
  <select id="empty-acc" style="margin-bottom:8px">{acc_opts_srv}</select>
  <div class="folder-btns">
   <button class="bd" onclick="emptyFolder('trash')">🗑️ Svuota Cestino</button>
   <button class="bd" onclick="emptyFolder('spam')">🚫 Svuota Spam</button>
  </div>
  <div id="empty-result"></div>
 </div>
</div>

<!-- ═══ WIZARD ═══ -->
<div id="panel-wizard" class="panel">
 <div class="card">
  <h2>✍️ Wizard risposta AI</h2>
  <div class="sdots">
   <div class="sdot active" id="d1">1</div><div class="sdot" id="d2">2</div>
   <div class="sdot" id="d3">3</div><div class="sdot" id="d4">4</div>
  </div>

  <div class="wstep active" id="ws1">
   <p style="color:var(--m);font-size:.8rem;margin-bottom:9px">Apri un'email dall'Inbox → premi Rispondi, oppure compila qui:</p>
   <select id="wz-acc" style="margin-bottom:7px">{acc_opts_srv}</select>
   <input id="wz-to" placeholder="Destinatario (email del mittente)">
   <input id="wz-subj" placeholder="Oggetto della risposta">
   <textarea id="wz-orig" placeholder="Incolla il testo dell'email originale ricevuta…" rows="4"></textarea>
   <button class="bp" onclick="wzNext(1)">Avanti →</button>
  </div>

  <div class="wstep" id="ws2">
   <div class="g2" style="margin-bottom:7px">
    <div>
     <label style="font-size:.76rem;color:var(--m)">Stile risposta</label>
     <select id="wz-style">
      <option value="professionale">💼 Professionale</option>
      <option value="amichevole">😊 Amichevole</option>
      <option value="formale">🎩 Formale</option>
      <option value="breve">⚡ Breve e diretto</option>
     </select>
    </div>
    <div>
     <label style="font-size:.76rem;color:var(--m)">Lingua risposta</label>
     <select id="wz-lang">
      <option value="italiano">🇮🇹 Italiano</option>
      <option value="inglese">🇬🇧 Inglese</option>
      <option value="francese">🇫🇷 Francese</option>
      <option value="spagnolo">🇪🇸 Spagnolo</option>
     </select>
    </div>
   </div>
   <label style="font-size:.76rem;color:var(--m)">Istruzioni all'AI — cosa vuoi dire?</label>
   <textarea id="wz-instr" placeholder="Es: Conferma l'appuntamento per giovedì ma sposta l'ora alle 15:00. Ringrazia per la disponibilità." rows="4"></textarea>
   <div class="brow">
    <button class="bp" id="wz-gen-btn" onclick="wzGenerate()">🤖 Genera bozza</button>
    <button class="bg" onclick="wzGoStep(1)">← Indietro</button>
   </div>
  </div>

  <div class="wstep" id="ws3">
   <p style="color:var(--m);font-size:.8rem;margin-bottom:7px">Rivedi e modifica la bozza generata dall'AI:</p>
   <textarea id="wz-draft" rows="9" placeholder="La bozza apparirà qui…"></textarea>
   <div class="brow">
    <button class="bw" onclick="wzRegenerate()">🔄 Rigenera</button>
    <button class="bp" onclick="wzNext(3)">Avanti →</button>
    <button class="bg" onclick="wzGoStep(2)">← Indietro</button>
   </div>
  </div>

  <div class="wstep" id="ws4">
   <!-- Allegati -->
   <div style="margin-bottom:11px">
    <div id="att-drop" style="border:2px dashed var(--b);border-radius:10px;padding:14px;text-align:center;cursor:pointer;transition:.2s;background:#0a111e"
         onclick="document.getElementById('att-input').click()"
         ondragover="event.preventDefault();this.style.borderColor='var(--acc)'"
         ondragleave="this.style.borderColor='var(--b)'"
         ondrop="event.preventDefault();this.style.borderColor='var(--b)';handleAttDrop(event.dataTransfer.files)">
     <div style="font-size:1.4rem;margin-bottom:4px">📎</div>
     <div style="font-size:.8rem;color:var(--m)">Trascina qui i file oppure <span style="color:var(--acc)">clicca per selezionare</span></div>
     <div style="font-size:.72rem;color:var(--m);margin-top:3px">PDF · Word · Excel · Immagini · ZIP — max 20MB</div>
    </div>
    <input type="file" id="att-input" multiple style="display:none" onchange="handleAttFiles(this.files)">
    <div id="att-list" style="margin-top:7px;display:flex;flex-direction:column;gap:4px"></div>
   </div>
   <!-- Invio -->
   <div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:9px">
    <label style="display:flex;align-items:center;gap:5px;font-size:.84rem;cursor:pointer">
     <input type="radio" name="wz-when" value="now" checked onchange="document.getElementById('wz-schbox').style.display='none'"> 📤 Invia subito
    </label>
    <label style="display:flex;align-items:center;gap:5px;font-size:.84rem;cursor:pointer">
     <input type="radio" name="wz-when" value="sch" onchange="document.getElementById('wz-schbox').style.display='block'"> 🕐 Programma
    </label>
   </div>
   <div id="wz-schbox" style="display:none;margin-bottom:9px">
    <input type="datetime-local" id="wz-sat">
    <p style="font-size:.74rem;color:var(--m);margin-top:3px">HomeMind invierà automaticamente all'orario scelto.</p>
   </div>
   <div style="background:#0f172a;border:1px solid var(--b);border-radius:8px;padding:10px;margin-bottom:9px">
    <div class="meta">📬 A: <b id="wprev-to"></b></div>
    <div class="meta">📌 Oggetto: <b id="wprev-subj"></b></div>
    <div style="font-size:.78rem;white-space:pre-wrap;margin-top:6px;max-height:160px;overflow-y:auto" id="wprev-body"></div>
   </div>
   <div class="brow">
    <button class="bs" onclick="wzSend()">✅ Invia</button>
    <button class="bg" onclick="wzGoStep(3)">← Indietro</button>
   </div>
  </div>
 </div>
</div>

<!-- ═══ PROGRAMMATI ═══ -->
<div id="panel-sched" class="panel">
 <div class="card">
  <h2>🕐 Email programmate</h2>
  <button class="bp" onclick="loadSched()" style="margin-bottom:9px">🔄 Aggiorna</button>
  <div id="sched-list"><div style="color:var(--m)">Nessuna email in coda.</div></div>
 </div>
</div>

<!-- ═══ AUTO-RISPOSTA ═══ -->
<div id="panel-rules" class="panel">
 <div class="card">
  <h2>🤖 Regole auto-risposta</h2>
  <p style="font-size:.78rem;color:var(--m);margin-bottom:9px">Quando arriva un'email con la parola chiave, HomeMind risponde automaticamente.</p>
  <div id="rules-list"></div>
  <div class="brow" style="margin-top:7px;align-items:center">
   <button class="bp" onclick="addRule()">➕ Aggiungi</button>
   <button class="bs" onclick="saveRules()">💾 Salva</button>
   <span id="rules-save-status" style="font-size:.75rem;color:var(--g);margin-left:4px"></span>
  </div>
 </div>
</div>

<!-- ═══ ACCOUNT ═══ -->
<div id="panel-accs" class="panel">
 <div class="card">
  <h2>⚙️ Account Gmail</h2>
  <p style="font-size:.78rem;color:var(--m);margin-bottom:9px">
   Richiede una <b>App Password</b> Gmail.<br>
   Creala su: <a href="https://myaccount.google.com/apppasswords" target="_blank" style="color:var(--acc)">myaccount.google.com/apppasswords</a> → "Altra app" → "HomeMind"
  </p>
  <div id="acc-list"></div>
  <div class="brow" style="margin-top:7px">
   <button class="bp" onclick="addAcc()">➕ Aggiungi</button>
   <button class="bs" onclick="saveAccs()">💾 Salva</button>
  </div>
 </div>
 <div class="card">
  <h2>⏱️ Controllo automatico email</h2>
  <p style="font-size:.78rem;color:var(--m);margin-bottom:10px">
   Ogni quanti minuti HomeMind controlla le email nuove e applica le regole di auto-risposta.
  </p>
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
   <label style="font-size:.85rem;font-weight:600">Controlla ogni</label>
   <input type="number" id="check-interval" min="1" max="1440" value="30"
          style="width:80px;margin-bottom:0;text-align:center;font-size:1rem;font-weight:700">
   <label style="font-size:.85rem;color:var(--m)">minuti</label>
   <button class="bs" onclick="saveInterval()">💾 Salva</button>
  </div>
  <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">
   <button class="bg bsm" onclick="setInterval2(5)">5 min</button>
   <button class="bg bsm" onclick="setInterval2(10)">10 min</button>
   <button class="bg bsm" onclick="setInterval2(15)">15 min</button>
   <button class="bg bsm" onclick="setInterval2(30)">30 min</button>
   <button class="bg bsm" onclick="setInterval2(60)">1 ora</button>
   <button class="bw bsm" onclick="checkNow()" style="margin-left:8px">⚡ Controlla ora</button>
  </div>
  <div style="margin-top:12px;border-top:1px solid var(--b);padding-top:10px">
   <p style="font-size:.82rem;font-weight:600;margin-bottom:8px">🔔 Notifiche Telegram</p>
   <label style="display:flex;align-items:center;gap:8px;font-size:.82rem;cursor:pointer;margin-bottom:6px">
    <input type="checkbox" id="notify-new-emails" style="width:auto;margin:0">
    Notifica nuove email su Telegram
    <span style="color:var(--m);font-size:.74rem">(default: OFF — notifica solo auto-risposte)</span>
   </label>
   <button class="bs bsm" onclick="saveEmailNotifySettings()">💾 Salva</button>
  </div>
  <p id="interval-hint" style="font-size:.74rem;color:var(--m);margin-top:7px">
   💡 Valori bassi garantiscono risposte rapide.
  </p>
 </div>
</div>

<!-- MODAL email -->
<div class="modal" id="emodal">
 <div class="mbox">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
   <h3 id="m-subj"></h3>
   <button onclick="closeMod()" style="background:none;border:none;color:var(--m);font-size:1rem;cursor:pointer;flex-shrink:0;margin-left:8px">✕</button>
  </div>
  <div class="meta">Da: <span id="m-from"></span></div>
  <div class="meta">Data: <span id="m-date"></span></div>
  <div id="m-sum" class="sumbox" style="display:none"></div>
  <div class="btext" id="m-body"></div>
  <div class="brow" style="margin-top:9px">
   <button class="bp bsm" onclick="modReply()">✍️ Rispondi con AI</button>
   <button class="bw bsm" onclick="modSum()">🤖 Sommario</button>
   <button class="bd bsm" onclick="modDel()">🗑️ Cestino</button>
   <button class="bg bsm" onclick="closeMod()">Chiudi</button>
  </div>
 </div>
</div>

<div class="toast" id="toast"></div>

<script>
// ── Init ──────────────────────────────────────────────────────────
var _ep=window.location.pathname;
var _eb=_ep.split('/email')[0];
var EAPI=_eb?(window.location.origin+_eb):'';

let curEmails=[],curEmail=null,wzData={{}},rules=[],accs=[],accsRaw=[];
let selUids=new Set();

// ── Tabs ──────────────────────────────────────────────────────────
function switchTab(t){{
  const names=['inbox','search','spam','wizard','sched','rules','accs'];
  document.querySelectorAll('.tab').forEach((el,i)=>el.classList.toggle('active',names[i]===t));
  names.forEach(n=>document.getElementById('panel-'+n).classList.toggle('active',n===t));
  if(t==='sched')loadSched();
  if(t==='rules')loadRules();
  if(t==='accs')loadAccs();
}}

// ── Utils ─────────────────────────────────────────────────────────
function toast(m,d=3200){{const t=document.getElementById('toast');t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',d);}}
function esc(s){{return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}}
function fdate(s){{try{{return new Date(s).toLocaleString('it-IT',{{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}});}}catch{{return s||'';}}}}

// ── Email list render ─────────────────────────────────────────────
function renderEmailList(emails, container, showCheckbox=true){{
  if(!emails.length){{container.innerHTML='<div style="color:var(--m)">Nessuna email trovata.</div>';return;}}
  const wrap=document.createElement('div');wrap.className='elist';
  emails.forEach((em,i)=>{{
    const lbl=em.ai_label||'';
    const score=em.spam_score||0;
    const scorePill=score>0?`<span class="score-pill ${{score>=7?'score-hi':'score-lo'}}">${{score}}/10</span>`:'';
    const reason=em.spam_reason?`<div style="font-size:.7rem;color:var(--r)">${{esc(em.spam_reason)}}</div>`:'';
    const cls2=['eitem',em.seen?'':'unread',score>=7?'spam-hi':'',em._sel?'sel':''].filter(Boolean).join(' ');
    const d2=document.createElement('div');d2.className=cls2;d2.dataset.idx=i;
    d2.innerHTML=`
      ${{showCheckbox?`<div class="esel${{em._sel?' checked':''}}" onclick="toggleSel(event,${{i}})"></div>`:''}}
      <div class="eh">
       <span class="ef">${{esc(em.sender)}}</span>
       <span class="ed">${{fdate(em.date)}}</span>
      </div>
      <div class="es">${{esc(em.subject)}}${{scorePill}}${{lbl?`<span class="lbl l${{lbl[0]}}">${{lbl}}</span>`:''}}</div>
      <div class="ep">${{esc(em.snippet)}}</div>
      ${{reason}}`;
    d2.addEventListener('click',(e)=>{{if(e.target.classList.contains('esel'))return;openEmail(em);}});
    wrap.appendChild(d2);
  }});
  container.innerHTML='';container.appendChild(wrap);
}}

// ── Selection ─────────────────────────────────────────────────────
function toggleSel(e,i){{
  e.stopPropagation();
  const em=curEmails[i];
  if(!em)return;
  em._sel=!em._sel;
  if(em._sel)selUids.add(em.uid+':'+em.account_address+':'+em.folder);
  else selUids.delete(em.uid+':'+em.account_address+':'+em.folder);
  const el=e.target;el.classList.toggle('checked',em._sel);
  el.closest('.eitem').classList.toggle('sel',em._sel);
  updateBulkBar();
}}
function updateBulkBar(){{
  const n=selUids.size;
  document.getElementById('bulk-bar').style.display=n>0?'flex':'none';
  document.getElementById('bulk-count').textContent=n+' selezionate';
}}
function clearSel(){{
  selUids.clear();curEmails.forEach(e=>e._sel=false);
  document.querySelectorAll('.esel').forEach(el=>el.classList.remove('checked'));
  document.querySelectorAll('.eitem').forEach(el=>el.classList.remove('sel'));
  updateBulkBar();
}}
async function bulkDelete(){{
  if(!selUids.size)return;
  if(!confirm(`Spostare ${{selUids.size}} email nel cestino?`))return;
  // Group by account+folder
  const groups={{}};
  selUids.forEach(k=>{{const[uid,acc,fold]=k.split(':');const gk=acc+'|'+fold;if(!groups[gk])groups[gk]={{acc,fold,uids:[]}};groups[gk].uids.push(uid);}});
  let total=0;
  for(const g of Object.values(groups)){{
    const r=await fetch(`${{EAPI}}/api/email/delete_bulk`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{account:g.acc,uids:g.uids,folder:g.fold}})}});
    const d=await r.json();total+=d.deleted||0;
  }}
  toast(`🗑️ ${{total}} email spostate nel cestino`);
  clearSel();loadEmails();
}}

// ── Inbox ─────────────────────────────────────────────────────────
async function loadEmails(){{
  const acc=document.getElementById('inb-acc').value;
  const fold=document.getElementById('inb-fold').value;
  const cls=document.getElementById('inb-cls').checked;
  const list=document.getElementById('inbox-list');
  list.innerHTML='<div style="display:flex;align-items:center;gap:7px;color:var(--m)"><div class="spin"></div> Caricamento…</div>';
  selUids.clear();updateBulkBar();
  try{{
    const r=await fetch(`${{EAPI}}/api/email/list?account=${{encodeURIComponent(acc)}}&folder=${{encodeURIComponent(fold)}}&max_count=30&classify=${{cls}}`);
    const d=await r.json();
    if(d.error){{list.innerHTML=`<div style="color:var(--r)">❌ ${{esc(d.error)}}</div>`;return;}}
    curEmails=d.emails||[];
    renderEmailList(curEmails,list);
    if(d.errors?.length)toast('⚠️ Errore su alcuni account');
  }}catch(e){{list.innerHTML=`<div style="color:var(--r)">Errore: ${{e.message}}</div>`;}}
}}

// ── Search ────────────────────────────────────────────────────────
async function doSearch(){{
  const acc=document.getElementById('srch-acc').value;
  const fold=document.getElementById('srch-fold').value;
  const q=document.getElementById('srch-q').value.trim();
  if(!q){{toast('⚠️ Inserisci un termine di ricerca');return;}}
  const list=document.getElementById('srch-list');
  list.innerHTML='<div style="display:flex;align-items:center;gap:7px;color:var(--m)"><div class="spin"></div> Ricerca…</div>';
  try{{
    const r=await fetch(`${{EAPI}}/api/email/search?account=${{encodeURIComponent(acc)}}&folder=${{encodeURIComponent(fold)}}&query=${{encodeURIComponent(q)}}`);
    const d=await r.json();
    if(d.error){{list.innerHTML=`<div style="color:var(--r)">❌ ${{esc(d.error)}}</div>`;return;}}
    const emails=d.emails||[];
    if(!emails.length){{list.innerHTML='<div style="color:var(--m)">Nessun risultato per <b>'+esc(q)+'</b></div>';return;}}
    list.innerHTML=`<div style="font-size:.78rem;color:var(--m);margin-bottom:7px">${{emails.length}} risultati per "${{esc(q)}}"</div>`;
    const wrap=document.createElement('div');renderEmailList(emails,wrap,false);list.appendChild(wrap);
    // Override curEmails for openEmail from search
    curEmails=[...emails];
  }}catch(e){{list.innerHTML=`<div style="color:var(--r)">Errore: ${{e.message}}</div>`;}}
}}

// ── Spam / Pulizia ────────────────────────────────────────────────
async function detectSpam(){{
  const acc=document.getElementById('spam-acc').value;
  const res=document.getElementById('spam-result');
  res.innerHTML='<div style="display:flex;align-items:center;gap:7px;color:var(--m)"><div class="spin"></div> Analisi AI in corso (30-60 sec)…</div>';
  try{{
    const r=await fetch(`${{EAPI}}/api/email/spam_detect?account=${{encodeURIComponent(acc)}}&max_count=25`);
    const d=await r.json();
    if(d.error){{res.innerHTML=`<div style="color:var(--r)">❌ ${{esc(d.error)}}</div>`;return;}}
    const emails=d.emails||[];
    const spam=emails.filter(e=>e.spam_score>=7);
    if(!spam.length){{res.innerHTML='<div style="color:var(--g)">✅ Nessuna email sospetta trovata.</div>';return;}}
    res.innerHTML=`<div class="spam-bar">🤖 AI ha trovato <b>${{spam.length}}</b> email sospette su ${{emails.length}} analizzate.</div>`;
    // Set curEmails to spam for selection
    spam.forEach(e=>{{e.account_address=e.account_address||acc;e.folder='INBOX';}});
    const listDiv=document.createElement('div');
    renderEmailList(spam,listDiv,true);
    // Pre-select all spam
    spam.forEach((e,i)=>{{e._sel=true;selUids.add(e.uid+':'+e.account_address+':INBOX');}});
    res.appendChild(listDiv);
    // Show bulk bar
    updateBulkBar();
    const btnDiv=document.createElement('div');btnDiv.className='brow';btnDiv.style.marginTop='8px';
    btnDiv.innerHTML=`<button class="bd" onclick="bulkDeleteSpam(${{JSON.stringify(spam.map(e=>e.uid)).replace(/"/g,'&quot;')}},'${{acc}}')">🗑️ Elimina tutte (${{spam.length}})</button>`;
    res.appendChild(btnDiv);
    curEmails=[...spam];
  }}catch(e){{res.innerHTML=`<div style="color:var(--r)">Errore: ${{e.message}}</div>`;}}
}}

async function bulkDeleteSpam(uids,acc){{
  if(!confirm(`Spostare nel cestino ${{uids.length}} email spam?`))return;
  const r=await fetch(`${{EAPI}}/api/email/delete_bulk`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{account:acc,uids:uids,folder:'INBOX'}})}});
  const d=await r.json();
  toast(`🗑️ ${{d.deleted||0}} spam eliminate`);
  document.getElementById('spam-result').innerHTML='<div style="color:var(--g)">✅ Spam eliminato. Rianalizza per aggiornare.</div>';
}}

async function emptyFolder(folderKey){{
  const FOLDERS={{'trash':'[Gmail]/Trash','spam':'[Gmail]/Spam'}};
  const folder=FOLDERS[folderKey]||folderKey;
  const acc=document.getElementById('empty-acc').value;
  if(!acc){{toast('⚠️ Seleziona un account');return;}}
  const label={{'[Gmail]/Trash':'Cestino','[Gmail]/Spam':'Spam'}}[folder]||folder;
  if(!confirm('Svuotare definitivamente '+label+'? Operazione NON reversibile.'))return;
  document.getElementById('empty-result').innerHTML='<div style="color:var(--m)">⏳ Svuotamento in corso…</div>';
  try{{
    const r=await fetch(`${{EAPI}}/api/email/empty_folder`,{{method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{account:acc,folder:folder}})}});
    const d=await r.json();
    if(d.error){{document.getElementById('empty-result').innerHTML='<div style="color:var(--r)">❌ '+esc(d.error)+'</div>';return;}}
    document.getElementById('empty-result').innerHTML='<div style="color:var(--g)">✅ Eliminate '+(d.deleted||0)+' email da '+label+'.</div>';
  }}catch(e){{document.getElementById('empty-result').innerHTML='<div style="color:var(--r)">Errore: '+e.message+'</div>';}}
}}

// ── Open email modal ──────────────────────────────────────────────
async function openEmail(em){{
  curEmail=em;
  document.getElementById('m-subj').textContent=em.subject||'';
  document.getElementById('m-from').textContent=em.sender||'';
  document.getElementById('m-date').textContent=em.date||'';
  document.getElementById('m-sum').style.display='none';
  document.getElementById('m-body').textContent='Caricamento…';
  document.getElementById('emodal').classList.add('open');
  try{{
    const r=await fetch(`${{EAPI}}/api/email/read?account=${{encodeURIComponent(em.account_address)}}&uid=${{encodeURIComponent(em.uid)}}&folder=${{encodeURIComponent(em.folder||'INBOX')}}`);
    const d=await r.json();curEmail={{...em,...d}};
    document.getElementById('m-body').textContent=d.body_text||'(vuoto)';
  }}catch{{document.getElementById('m-body').textContent='Errore caricamento';}}
}}
function closeMod(){{document.getElementById('emodal').classList.remove('open');}}
async function modSum(){{
  const b=document.getElementById('m-sum');b.style.display='block';b.textContent='🤖 Generazione sommario…';
  try{{
    const r=await fetch(`${{EAPI}}/api/email/read?account=${{encodeURIComponent(curEmail.account_address)}}&uid=${{encodeURIComponent(curEmail.uid)}}&summarize=true`);
    const d=await r.json();b.textContent='📋 '+d.ai_summary;
  }}catch{{b.textContent='Errore sommario';}}
}}
async function modDel(){{
  if(!confirm('Spostare nel Cestino?'))return;
  const r=await fetch(`${{EAPI}}/api/email/delete`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{account:curEmail.account_address,uid:curEmail.uid,folder:curEmail.folder||'INBOX'}})}});
  const d=await r.json();
  if(d.ok){{closeMod();toast('🗑️ Spostata nel cestino');loadEmails();}}else toast('❌ Errore cancellazione');
}}
function modReply(){{
  document.getElementById('wz-acc').value=curEmail.account_address||'';
  const m2=(curEmail.sender||'').match(/<([^>]+)>/);
  document.getElementById('wz-to').value=m2?m2[1]:curEmail.sender||'';
  document.getElementById('wz-subj').value='Re: '+(curEmail.subject||'');
  document.getElementById('wz-orig').value=curEmail.body_text||'';
  wzData.uid=curEmail.uid;wzData.msg_id=curEmail.msg_id||'';
  closeMod();switchTab('wizard');wzGoStep(2);
}}

// ── Wizard ────────────────────────────────────────────────────────
let wzStep=1;
function wzGoStep(n){{
  [1,2,3,4].forEach(i=>{{
    document.getElementById('ws'+i).classList.toggle('active',i===n);
    const dot=document.getElementById('d'+i);
    dot.classList.toggle('active',i===n);dot.classList.toggle('done',i<n);
  }});wzStep=n;
}}
function wzNext(from){{
  if(from===1&&!document.getElementById('wz-to').value){{alert('Inserisci il destinatario');return;}}
  if(from===3){{
    document.getElementById('wprev-to').textContent=document.getElementById('wz-to').value;
    document.getElementById('wprev-subj').textContent=document.getElementById('wz-subj').value;
    document.getElementById('wprev-body').textContent=document.getElementById('wz-draft').value;
  }}
  wzGoStep(from+1);
}}
async function wzGenerate(){{
  const btn=document.getElementById('wz-gen-btn');
  btn.disabled=true;btn.innerHTML='<span class="spin"></span> Generando…';
  try{{
    const body={{
      account:document.getElementById('wz-acc').value,
      uid:wzData.uid||'',
      instructions:document.getElementById('wz-instr').value||'Rispondi in modo cortese e professionale.',
      lang:document.getElementById('wz-lang').value,
      style:document.getElementById('wz-style').value,
      _direct_body:document.getElementById('wz-orig').value,
      _direct_subject:document.getElementById('wz-subj').value,
      _direct_sender:document.getElementById('wz-to').value,
    }};
    const r=await fetch(`${{EAPI}}/api/email/reply_draft`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
    const d=await r.json();
    if(d.error){{toast('❌ '+d.error,5000);}}
    else{{
      document.getElementById('wz-draft').value=d.draft;
      wzData.reply_to=d.reply_to||document.getElementById('wz-to').value;
      wzData.msg_id=d.msg_id||'';
      wzNext(2);
    }}
  }}catch(e){{toast('Errore: '+e.message,5000);}}
  btn.disabled=false;btn.textContent='🤖 Genera bozza';
}}
async function wzRegenerate(){{wzGoStep(2);await wzGenerate();}}
// ── Allegati wizard ──────────────────────────────────────────────
let wzAttachments = []; // Array di File objects

function handleAttFiles(files){{
  for(const f of files){{
    if(f.size > 20*1024*1024){{toast(`❌ ${{f.name}} troppo grande (max 20MB)`);continue;}}
    if(!wzAttachments.find(a=>a.name===f.name&&a.size===f.size)) wzAttachments.push(f);
  }}
  renderAttList();
}}
function handleAttDrop(files){{handleAttFiles(files);}}
function renderAttList(){{
  const el=document.getElementById('att-list');
  if(!el)return;
  if(!wzAttachments.length){{el.innerHTML='';return;}}
  el.innerHTML=wzAttachments.map((f,i)=>{{
    const kb=Math.round(f.size/1024);
    return `
    <div style="display:flex;align-items:center;gap:7px;background:#0f172a;border:1px solid var(--b);border-radius:7px;padding:6px 10px;font-size:.78rem">
     <span style="flex:1">📎 ${{esc(f.name)}} <span style="color:var(--m)">${{kb}} KB</span></span>
     <button class="bd bsm" onclick="wzAttachments.splice(${{i}},1);renderAttList()">✕</button>
    </div>`;
  }}).join('');
}}

async function wzSend(){{
  const when=document.querySelector('[name=wz-when]:checked')?.value;
  const scheduled_at = when==='sch' ? document.getElementById('wz-sat').value : '';
  if(when==='sch' && !scheduled_at){{alert('Seleziona data/ora');return;}}

  const fd = new FormData();
  fd.append('account', document.getElementById('wz-acc').value);
  fd.append('to',      document.getElementById('wz-to').value);
  fd.append('subject', document.getElementById('wz-subj').value);
  fd.append('body',    document.getElementById('wz-draft').value);
  fd.append('reply_to_msg_id', wzData.msg_id||'');
  if(scheduled_at) fd.append('scheduled_at', scheduled_at);
  for(const f of wzAttachments) fd.append('attachments', f, f.name);

  try{{
    const r=await fetch(`${{EAPI}}/api/email/send`,{{method:'POST',body:fd}});
    const d=await r.json();
    if(d.ok){{
      const attTxt = d.attachments_sent ? ` + ${{d.attachments_sent}} allegato/i` : '';
      toast(d.scheduled?`🕐 Programmata per ${{d.send_at}}`:`✅ Email inviata!${{attTxt}}`,4000);
      wzGoStep(1);
      ['wz-to','wz-subj','wz-orig','wz-instr','wz-draft'].forEach(id=>document.getElementById(id).value='');
      wzAttachments=[];renderAttList();wzData={{}};
    }}else toast('❌ '+(d.error||'Errore invio'),5000);
  }}catch(e){{toast('Errore: '+e.message,5000);}}
}}

// ── Scheduled ────────────────────────────────────────────────────
async function loadSched(){{
  const list=document.getElementById('sched-list');
  const r=await fetch(`${{EAPI}}/api/email/scheduled`);
  const d=await r.json();const items=d.scheduled||[];
  if(!items.length){{list.innerHTML='<div style="color:var(--m)">Nessuna email programmata.</div>';return;}}
  list.innerHTML=items.map(i=>`
    <div class="srow">
     <span class="tag t${{i.status[0]}}">${{i.status}}</span>
     <div style="flex:1"><div style="font-weight:600;font-size:.82rem">${{esc(i.to)}}</div>
      <div style="color:var(--m);font-size:.74rem">${{esc(i.subject)}}</div></div>
     <span style="color:var(--acc);font-size:.74rem">🕐 ${{(i.send_at||'').replace('T',' ')}}</span>
     ${{i.status==='pending'?`<button class="bd bsm" onclick="cancelSched('${{i.id}}')">✕</button>`:''}}
    </div>`).join('');
}}
async function cancelSched(id){{
  if(!confirm('Annullare?'))return;
  await fetch(`${{EAPI}}/api/email/scheduled/cancel`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{task_id:id}})}});
  toast('🚫 Annullata');loadSched();
}}

// ── Rules ────────────────────────────────────────────────────────
// ── Autosave debounce ────────────────────────────────────────────
let _rulesSaveTimer=null;
function autoSaveRules(){{
  clearTimeout(_rulesSaveTimer);
  _rulesSaveTimer=setTimeout(async()=>{{
    const valid=rules.filter(r=>r.keyword&&r.keyword.trim());
    if(!valid.length&&rules.length===0)return; // niente da salvare
    try{{
      await fetch(`${{EAPI}}/api/email/auto_rules/save`,{{
        method:'POST',headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{rules:valid}})}});
      // Aggiorna stato di salvataggio silenziosamente
      document.getElementById('rules-save-status').textContent='✅ Salvato';
      setTimeout(()=>{{const el=document.getElementById('rules-save-status');if(el)el.textContent='';}},2500);
    }}catch{{
      document.getElementById('rules-save-status').textContent='⚠️ Errore salvataggio';
    }}
  }},800); // aspetta 800ms di inattività prima di salvare
}}

async function loadRules(){{
  await loadAccs(true);
  try{{
    const r=await fetch(`${{EAPI}}/api/email/auto_rules`);
    const d=await r.json();
    rules=d.rules||[];
  }}catch(e){{
    toast('⚠️ Errore caricamento regole: '+e.message);
  }}
  renderRules();
}}

function renderRules(){{
  const ao=accs.map(a=>`<option value="${{a.address}}">${{a.label||a.address}}</option>`).join('');
  document.getElementById('rules-list').innerHTML=rules.length?rules.map((rule,i)=>`
    <div class="rrow" style="flex-direction:column;gap:6px;${{!rule.keyword?'border:1px solid var(--r);':''}}">
     <div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center">
      <select onchange="rules[${{i}}].account=this.value;autoSaveRules()" style="margin-bottom:0;min-width:140px;flex:1">${{ao.replace('value="'+rule.account+'"','value="'+rule.account+'" selected')}}</select>
      <input placeholder="Parola chiave *" value="${{esc(rule.keyword||'')}}"
             oninput="rules[${{i}}].keyword=this.value.trim();autoSaveRules()"
             onblur="renderRules()"
             style="margin-bottom:0;flex:1;min-width:110px;${{!rule.keyword?'border-color:var(--r)':''}}">
      <label style="display:flex;align-items:center;gap:3px;font-size:.74rem;white-space:nowrap;margin-bottom:0">
       <input type="checkbox" ${{rule.enabled!==false?'checked':''}}
              onchange="rules[${{i}}].enabled=this.checked;autoSaveRules()"> Attiva
      </label>
      <button class="bd bsm" onclick="rules.splice(${{i}},1);renderRules();autoSaveRules()">✕</button>
     </div>
     <div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center">
      <select onchange="rules[${{i}}].match_in=this.value;autoSaveRules()" style="margin-bottom:0;width:140px" title="Dove cercare la keyword">
       <option value="oggetto"${{(rule.match_in||'oggetto')==='oggetto'?' selected':''}}>🔎 Solo oggetto</option>
       <option value="entrambi"${{rule.match_in==='entrambi'?' selected':''}}>🔎 Oggetto+corpo</option>
       <option value="corpo"${{rule.match_in==='corpo'?' selected':''}}>🔎 Solo corpo</option>
      </select>
      <label style="display:flex;align-items:center;gap:3px;font-size:.74rem;white-space:nowrap;margin-bottom:0" title="Cerca la parola intera (non come parte di un'altra parola)">
       <input type="checkbox" ${{rule.whole_word!==false?'checked':''}}
              onchange="rules[${{i}}].whole_word=this.checked;autoSaveRules()"> Parola intera
      </label>
      <select onchange="rules[${{i}}].style=this.value;autoSaveRules()" style="margin-bottom:0;flex:1">
       ${{['professionale','amichevole','formale','breve'].map(s=>`<option${{rule.style===s?' selected':''}} value="${{s}}">${{s}}</option>`).join('')}}
      </select>
     </div>
     <input placeholder="Istruzioni AI — es: Rispondi che sono disponibile dal lunedì al venerdì"
            value="${{esc(rule.instruction||'')}}"
            oninput="rules[${{i}}].instruction=this.value;autoSaveRules()"
            style="margin-bottom:0">
     ${{!rule.keyword?'<div style="font-size:.7rem;color:var(--r)">⚠️ Keyword obbligatoria</div>':''}}
    </div>`).join('')
  :'<div style="color:var(--m);font-size:.8rem">Nessuna regola. Premi ➕ per aggiungerne una.</div>';
}}

function addRule(){{
  const accAddr=accs.length?accs[0].address:'';
  rules.push({{account:accAddr,keyword:'',style:'professionale',instruction:'Rispondi cortesemente.',enabled:true}});
  renderRules();
  // Focus sul campo keyword della nuova riga
  setTimeout(()=>{{
    const inputs=document.querySelectorAll('#rules-list .rrow input[placeholder*="Parola"]');
    if(inputs.length)inputs[inputs.length-1].focus();
    const l=document.getElementById('rules-list');
    l?.lastElementChild?.scrollIntoView({{behavior:'smooth',block:'nearest'}});
  }},60);
}}

async function saveRules(){{
  const empty=rules.filter(r=>r.enabled!==false&&!r.keyword);
  if(empty.length){{
    toast(`⚠️ ${{empty.length}} regola senza parola chiave — compilala o disabilitala`,4000);
    return;
  }}
  try{{
    const r=await fetch(`${{EAPI}}/api/email/auto_rules/save`,{{method:'POST',
      headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{rules}})}});
    const d=await r.json();
    if(d.ok)toast('✅ Regole salvate ('+rules.length+')');
    else toast('❌ Errore salvataggio');
  }}catch(e){{toast('❌ '+e.message);}}
}}

// ── Accounts ────────────────────────────────────────────────────
async function loadAccs(silent=false){{
  const r=await fetch(`${{EAPI}}/api/email/accounts`);
  const d=await r.json();accsRaw=d.accounts||[];accs=accsRaw;
  const opts=accs.length?accs.map(a=>`<option value="${{a.address}}">${{a.label||a.address}} (${{a.address}})</option>`).join('')
                        :'<option value="">— Nessun account —</option>';
  ['inb-acc','wz-acc','srch-acc','spam-acc','empty-acc'].forEach(id=>{{const el=document.getElementById(id);if(el)el.innerHTML=opts;}});
  if(!silent){{renderAccs();loadIntervalSetting();}}
}}
async function loadIntervalSetting(){{
  try{{
    const r=await fetch(`${{EAPI}}/api/email/settings`);
    const d=await r.json();
    const el=document.getElementById('check-interval');
    if(el&&d.email_check_interval_min)el.value=d.email_check_interval_min;
    const cb=document.getElementById('notify-new-emails');
    if(cb)cb.checked=!!d.email_notify_new;
  }}catch{{}}
}}
function setInterval2(min){{
  const el=document.getElementById('check-interval');
  if(el)el.value=min;
}}
async function saveInterval(){{
  const val=parseInt(document.getElementById('check-interval')?.value||'30');
  if(isNaN(val)||val<1||val>1440){{toast('⚠️ Inserisci un valore tra 1 e 1440');return;}}
  const r=await fetch(`${{EAPI}}/api/email/settings/save`,{{method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{email_check_interval_min:val}})}});
  const d=await r.json();
  if(d.ok)toast(`✅ Controllo ogni ${{val}} min — attivo al prossimo ciclo`);
  else toast('❌ Errore: '+(d.error||''));
}}
async function checkNow(){{
  const btn=event.target;btn.disabled=true;btn.textContent='⏳ Controllo…';
  try{{
    const r=await fetch(`${{EAPI}}/api/email/check_now`,{{method:'POST'}});
    const d=await r.json();
    toast(d.ok?'⚡ Controllo avviato! Riceverai notifica Telegram.':'❌ '+(d.error||''),4000);
  }}catch(e){{toast('❌ '+e.message);}}
  setTimeout(()=>{{btn.disabled=false;btn.textContent='⚡ Controlla ora';}},3000);
}}
function renderAccs(){{
  document.getElementById('acc-list').innerHTML=accsRaw.map((a,i)=>`
    <div class="arow">
     <div class="ah"><span style="font-weight:600">${{a.label||'Account '+i}}</span>
      <div style="display:flex;gap:6px;align-items:center">
       <label style="display:flex;align-items:center;gap:3px;font-size:.74rem"><input type="checkbox" ${{a.enabled!==false?'checked':''}} onchange="accsRaw[${{i}}].enabled=this.checked"> Abilitato</label>
       <button class="bd bsm" onclick="accsRaw.splice(${{i}},1);renderAccs()">✕</button>
      </div>
     </div>
     <label>Nome visualizzato</label><input value="${{esc(a.label||'')}}" oninput="accsRaw[${{i}}].label=this.value" placeholder="Es: Casa, Lavoro…">
     <label>Indirizzo Gmail</label><input value="${{esc(a.address||'')}}" oninput="accsRaw[${{i}}].address=this.value" placeholder="nome@gmail.com" type="email">
     <label>App Password Gmail</label><input value="${{esc(a.app_password||'')}}" oninput="accsRaw[${{i}}].app_password=this.value" placeholder="xxxx xxxx xxxx xxxx" type="password">
    </div>`).join('')||'<div style="color:var(--m);font-size:.8rem">Nessun account.</div>';
}}
function addAcc(){{accsRaw.push({{label:'',address:'',app_password:'',imap_host:'imap.gmail.com',imap_port:993,smtp_host:'smtp.gmail.com',smtp_port:587,enabled:true}});renderAccs();}}
async function saveAccs(){{
  await fetch(`${{EAPI}}/api/email/accounts/save`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{accounts:accsRaw}})}});
  toast('✅ Account salvati');await loadAccs(true);
}}

loadAccs(true);
</script></body></html>"""
    return HTMLResponse(html)
