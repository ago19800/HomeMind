"""
dieta_ui.py — HTML e JavaScript della tab «🥗 Dieta» nelle Impostazioni.

Sono stringhe normali (non f-string): main.py le inserisce già pronte nella pagina,
così non servono le graffe doppie. I segnaposto __COSÌ__ vengono sostituiti qui.
"""
import html as _html

TAB_BUTTON = '<button class="tab" data-tab="dt" onclick="showTab(\'dt\')">🥗 Dieta</button>'


def speakers_html(all_speakers: list, selected: set, state_cache: dict, field: str = "dt_sp") -> str:
    """Elenco speaker con checkbox (stesso aspetto della spazzatura)."""
    spk = [dict(s) for s in (all_speakers or [])]
    have = {s["eid"] for s in spk}
    for eid in selected:
        if eid not in have:
            c = (state_cache or {}).get(eid, {})
            n = (c.get("attributes") or {}).get("friendly_name", eid)
            spk.append({"eid": eid, "name": n, "state": c.get("state", "unknown"),
                        "is_alexa": any(k in (n + eid).lower() for k in ("echo", "alexa", "amazon"))})
    out = []
    for s in spk:
        st = s["state"]
        col = ("#22c55e" if st in ("idle", "playing", "paused", "on", "standby")
               else "#ef4444" if st == "unavailable" else "#94a3b8")
        name = _html.escape(str(s["name"]))
        eid = _html.escape(str(s["eid"]))
        out.append(
            f'<label class="ei" data-s="{(name + " " + eid).lower()}">'
            f'<input type="checkbox" name="{field}" value="{eid}" {"checked" if s["eid"] in selected else ""}>'
            f'<div class="en"><div class="enm">{name}{" 🟢 Alexa" if s.get("is_alexa") else ""}</div>'
            f'<div class="eid">{eid}</div></div>'
            f'<span class="est" style="color:{col}">{_html.escape(str(st))}</span></label>')
    return "".join(out) or ('<div class="empty">Nessun media_player trovato. '
                            'Installa l\'integrazione Alexa Media Player in HA.</div>')


_TAB_HTML = """
<div id="tc-dt" class="tc">
  <div class="sec pu">
    <h2>🥗 Piano alimentare</h2>
    <div class="desc">Carica il piano in formato <b>JSON</b>. Quando la dieta cambia basta caricare il nuovo file: sostituisce il precedente. Se il file non è valido il piano attuale resta com'è.</div>
    <div id="dt_status" class="ts" style="margin-bottom:8px">⏳ Caricamento…</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <input type="file" id="dt_file" accept=".json,application/json" style="display:none" onchange="dtUpload(this)">
      <button type="button" onclick="document.getElementById('dt_file').click()" style="background:#22c55e;border:none;border-radius:6px;color:#fff;padding:8px 16px;cursor:pointer;font-size:.85rem;font-weight:600">📤 Carica dieta (JSON)</button>
      <button type="button" onclick="dtReload()" style="background:#334155;border:none;border-radius:6px;color:#e2e8f0;padding:8px 14px;cursor:pointer;font-size:.85rem">🔄 Ricarica da disco</button>
      <a href="#" onclick="this.href=API_BASE+'/api/dieta/example'" download="dieta_esempio.json" style="color:#38bdf8;font-size:.8rem">⬇️ Scarica file d'esempio</a>
    </div>
    <div id="dt_msg" class="ts" style="margin-top:8px"></div>
    <div id="dt_view" style="margin-top:10px"></div>
  </div>

  <div class="sec pu">
    <h2>🔔 Risposte</h2>
    <div class="desc">Chiedi ad Alexa <i>«cosa ho per spuntino pomeridiano?»</i> (anche colazione, pranzo, cena, spuntino mattina / serale, «domani», «giovedì», «cosa mangio oggi»). HomeMind risponde a voce sugli speaker scelti. Richiede <b>Alexa Media Player</b> in Home Assistant.</div>
    <div class="tr">
      <div><div class="tl">🔊 Risposta vocale Alexa</div><div class="ts">Ascolta le domande sulla dieta e risponde sugli speaker selezionati</div></div>
      <label class="sw"><input type="checkbox" id="dt_alexa" __ALEXA__><span class="sl"></span></label>
    </div>
    <div class="tr">
      <div><div class="tl">✈️ Notifica Telegram</div><div class="ts">Manda su Telegram anche il testo di ogni risposta</div></div>
      <label class="sw"><input type="checkbox" id="dt_tg" __TG__><span class="sl"></span></label>
    </div>
    <div class="tr">
      <div style="flex:1"><div class="tl">🔊 Volume risposta</div><div class="ts">Impostato automaticamente prima di parlare</div></div>
      <input type="range" id="dt_vol" min="0" max="100" step="5" value="__VOL__" style="flex:1;max-width:180px" oninput="document.getElementById('dt_vol_lbl').textContent=this.value+'%'">
      <span id="dt_vol_lbl" style="min-width:40px;text-align:right;color:#94a3b8;font-size:.78rem">__VOL__%</span>
    </div>
    <div style="margin-top:10px">
      <div class="tl" style="margin-bottom:6px">📻 Speaker Alexa (selezione multipla)</div>
      <input class="search" type="text" placeholder="🔍 Cerca speaker..." oninput="filt('dt_sp_list',this.value)">
      <div id="dt_sp_list" class="el" style="max-height:260px;overflow-y:auto">__SPEAKERS__</div>
    </div>
    <div style="margin-top:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <button type="button" onclick="dtSaveSettings()" style="background:#22c55e;border:none;border-radius:6px;color:#fff;padding:8px 16px;cursor:pointer;font-size:.85rem;font-weight:600">💾 Salva impostazioni dieta</button>
      <span id="dt_set_msg" style="color:#94a3b8;font-size:.78rem"></span>
    </div>
    <div class="ts" style="margin-top:6px">Queste impostazioni si salvano da qui, subito (non serve il pulsante «Salva» generale).</div>
  </div>

  <div class="sec pu">
    <h2>🧪 Prova una frase</h2>
    <div class="desc">Scrivi quello che diresti ad Alexa. Il test usa le impostazioni salvate sopra: parla sugli speaker selezionati e manda su Telegram se lo switch è attivo.</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <input id="dt_q" type="text" value="cosa ho per spuntino pomeridiano" style="flex:1;min-width:200px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px;font-size:.85rem">
      <button type="button" onclick="dtTest()" style="background:#0ea5e9;border:none;border-radius:6px;color:#fff;padding:8px 16px;cursor:pointer;font-size:.85rem;font-weight:600">▶️ Prova</button>
    </div>
    <div id="dt_test_msg" class="ts" style="margin-top:8px"></div>
    <div class="ts" style="margin-top:10px"><b>Alexa parte con la sua risposta e poi si interrompe?</b> È normale: Alexa risponde da sola alla frase e HomeMind la sente qualche secondo dopo. Per far parlare solo HomeMind, nell'app Alexa crea una <b>routine</b> per ogni frase che usi (Quando → Voce → scrivi la frase, es. <i>cosa ho per spuntino pomeridiano</i>) con un'azione silenziosa (es. «Aspetta»). Con la routine Alexa non dà più la sua risposta, mentre HomeMind continua a sentire la frase. Frasi consigliate: <i>cosa ho per colazione · spuntino mattina · pranzo · spuntino pomeridiano · cena · spuntino serale</i>.</div>
    <div class="ts" style="margin-top:10px"><b>Se Alexa non risponde</b>: HomeMind legge la frase dall'attributo <code>last_called_summary</code> di Alexa Media Player. In alternativa crea una routine Alexa che chiama uno script di HA con un <code>rest_command</code> verso <code>POST /api/dieta/ask</code> con <code>{"text":"cosa ho per cena"}</code>.</div>
  </div>
</div>
"""

_JS = r"""
function dtMsg(id, ok, txt){var e=document.getElementById(id); if(!e) return; e.style.color= ok===null?'#fbbf24':(ok?'#22c55e':'#ef4444'); e.textContent=txt;}
function dtEsc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function dtRender(st){
  var s=document.getElementById('dt_status'), v=document.getElementById('dt_view');
  if(!st.loaded){
    s.textContent = st.error ? ('⚠️ Errore nel file salvato: '+st.error) : '📭 Nessun piano caricato.';
    v.innerHTML=''; return;
  }
  s.textContent='✅ '+(st.titulo||'Piano alimentare')+(st.persona?(' — '+st.persona):'')+(st.valido_da?(' (dal '+st.valido_da+')'):'')+' · '+st.giorni.length+' giorni';
  var h='';
  if(st.warnings&&st.warnings.length){h+='<div class="ts" style="color:#fbbf24;margin-bottom:6px">⚠️ '+st.warnings.map(dtEsc).join('<br>⚠️ ')+'</div>';}
  st.giorni.forEach(function(g){
    h+='<details style="margin-bottom:6px"><summary style="cursor:pointer;font-weight:600">'+dtEsc(g.label)+(g.tipo?(' <span style="color:#94a3b8;font-weight:400">· '+dtEsc(g.tipo)+'</span>'):'')+'</summary><div style="padding:6px 0 6px 12px">';
    g.pasti.forEach(function(p){
      h+='<div style="margin-top:6px"><b>'+dtEsc(p.label)+'</b>'+(p.facoltativo?' <i style="color:#94a3b8">(facoltativo)</i>':'')+'<div class="ts">'+
        p.alimenti.map(function(a){return dtEsc(a.nome)+(a.quantita?(' — '+dtEsc(a.quantita)):'')+(a.nota?(' ('+dtEsc(a.nota)+')'):'');}).join('<br>')+'</div></div>';
    });
    h+='</div></details>';
  });
  v.innerHTML=h;
}
async function dtLoad(){
  try{
    var r=await fetch(API_BASE+'/api/dieta/state'); dtRender(await r.json());
  }catch(e){dtMsg('dt_status',false,'❌ '+e);}
}
async function dtUpload(inp){
  var f=inp.files&&inp.files[0]; if(!f) return;
  dtMsg('dt_msg',null,'⏳ Carico '+f.name+'…');
  try{
    var text=await f.text();
    var r=await fetch(API_BASE+'/api/dieta/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({json:text})});
    var res=await r.json();
    if(res.ok){dtMsg('dt_msg',true,'✅ '+res.message); dtRender(res.state);}
    else{dtMsg('dt_msg',false,'❌ '+(res.error||'Errore')+' — il piano precedente è rimasto invariato.');}
  }catch(e){dtMsg('dt_msg',false,'❌ '+e);}
  inp.value='';
}
async function dtReload(){
  dtMsg('dt_msg',null,'⏳ Ricarico…');
  try{
    var r=await fetch(API_BASE+'/api/dieta/reload',{method:'POST'}); var res=await r.json();
    dtMsg('dt_msg',!!res.ok,(res.ok?'✅ ':'❌ ')+(res.message||res.error||'')); if(res.state) dtRender(res.state);
  }catch(e){dtMsg('dt_msg',false,'❌ '+e);}
}
async function dtSaveSettings(){
  dtMsg('dt_set_msg',null,'⏳ Salvo…');
  var body={alexa_enabled:document.getElementById('dt_alexa').checked,
            telegram_enabled:document.getElementById('dt_tg').checked,
            speakers:getSel('dt_sp'),
            volume:(parseInt(document.getElementById('dt_vol').value)||50)/100};
  try{
    var r=await fetch(API_BASE+'/api/dieta/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    var res=await r.json();
    if(res.ok){
      var warn = (body.alexa_enabled && body.speakers.length===0) ? ' ⚠️ Nessuno speaker selezionato.' : '';
      dtMsg('dt_set_msg',true,'✅ Salvato.'+warn);
    } else dtMsg('dt_set_msg',false,'❌ '+(res.error||'Errore'));
  }catch(e){dtMsg('dt_set_msg',false,'❌ '+e);}
}
async function dtTest(){
  var q=document.getElementById('dt_q').value.trim(); if(!q) return;
  dtMsg('dt_test_msg',null,'⏳ Invio…');
  await dtSaveSettings();
  try{
    var r=await fetch(API_BASE+'/api/dieta/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:q,test:true})});
    var res=await r.json();
    if(!res.matched){dtMsg('dt_test_msg',false,'❌ Non ho riconosciuto un pasto in questa frase.'); return;}
    var t='💬 '+res.speech;
    if(res.alexa_total) t+='\n🔊 Alexa '+res.alexa_ok+'/'+res.alexa_total;
    if(res.alexa_error) t+='\n⚠️ Alexa: '+res.alexa_error;
    if(res.telegram_ok) t+='\n✈️ Telegram inviato';
    if(res.telegram_error) t+='\n⚠️ Telegram: '+res.telegram_error;
    var e=document.getElementById('dt_test_msg'); e.style.color='#22c55e'; e.style.whiteSpace='pre-wrap'; e.textContent=t;
  }catch(e){dtMsg('dt_test_msg',false,'❌ '+e);}
}
window.addEventListener('load',dtLoad);
"""


def build_tab(cfg_dieta: dict, speakers_block: str, api_base_js: str = "API_BASE") -> str:
    """HTML della tab. cfg_dieta = person_config['dieta'] (può essere vuoto)."""
    c = cfg_dieta if isinstance(cfg_dieta, dict) else {}
    try:
        vol = int(max(0.0, min(1.0, float(c.get("volume", 0.5)))) * 100)
    except (TypeError, ValueError):
        vol = 50
    return (_TAB_HTML
            .replace("__ALEXA__", "checked" if c.get("alexa_enabled") else "")
            .replace("__TG__", "checked" if c.get("telegram_enabled") else "")
            .replace("__VOL__", str(vol))
            .replace("__SPEAKERS__", speakers_block))


def build_js() -> str:
    return _JS
