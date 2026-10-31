"""
tv_ui.py — HTML e JavaScript della tab «📺 TV» nelle Impostazioni.
Stringhe normali (non f-string): main.py le inserisce già pronte. Segnaposto __COSÌ__.
"""
import html as _html
import json
import re

TAB_BUTTON = '<button class="tab" data-tab="tv" onclick="showTab(\'tv\')">📺 TV</button>'


_TV_WORDS = {"tv", "tivu", "tele", "televisione", "televisore", "television", "smarttv", "lg", "lgtv"}
_TV_BRANDS = ("samsung", "philips", "bravia", "webos", "panasonic", "hisense", "toshiba", "vizio", "sony", "tizen",
              "oled", "qled", "chromecast", "roku", "televis")
_SPEAKER_WORDS = {"echo", "alexa", "nest", "mini", "cassa", "radio", "musica", "music", "mpd", "speaker"}
_SPEAKER_PARTS = ("sonos", "soundbar", "homepod", "spotify", "speaker", "altoparlant")
BRAND_CHOICES = (("auto", "Automatica (consigliato)"), ("lg", "LG webOS"), ("samsung", "Samsung"),
                 ("sony", "Sony Bravia"), ("other", "Altra marca (Philips, Android TV, …)"))


def is_tv_entity(eid: str, attrs: dict) -> bool:
    """True per le TV, False per Echo/Alexa/Google Home/Sonos/barre audio/lettori musicali.
    device_class «tv» (lo imposta l'integrazione) decide da solo; altrimenti nome/entity_id."""
    a = attrs if isinstance(attrs, dict) else {}
    dc = str(a.get("device_class") or "").lower()
    if dc == "tv":
        return True
    if dc in ("speaker", "receiver"):
        return False
    text = f"{eid} {a.get('friendly_name') or ''}".lower()
    words = set(re.split(r"[^a-z0-9]+", text))
    if words & _SPEAKER_WORDS or any(k in text for k in _SPEAKER_PARTS):
        return False
    return bool(words & _TV_WORDS) or any(k in text for k in _TV_BRANDS)


def _media_players(state_cache: dict) -> list:
    """[(is_tv, unavailable, nome, entity_id, stato)] ordinate: TV disponibili per prime."""
    items = []
    for eid, st in (state_cache or {}).items():
        if not eid.startswith("media_player."):
            continue
        a = (st or {}).get("attributes") or {}
        name = str(a.get("friendly_name") or eid)
        state = str((st or {}).get("state", ""))
        items.append((is_tv_entity(eid, a), state == "unavailable", name, eid, state))
    items.sort(key=lambda i: (not i[0], i[1], i[2].lower(), i[3]))
    return items


def _option(eid: str, name: str, state: str, selected: str) -> str:
    return (f'<option value="{_html.escape(eid)}" {"selected" if eid == selected else ""}>'
            f'{_html.escape(name)} · {_html.escape(eid)} ({_html.escape(state)})</option>')


def entities_options(state_cache: dict, selected: str) -> str:
    """<option> delle sole TV. L'entità già scelta compare sempre (anche se non sembra una TV)."""
    out = ['<option value="">— scegli la TV —</option>']
    seen = set()
    for is_tv, _un, name, eid, state in _media_players(state_cache):
        if is_tv or eid == selected:
            out.append(_option(eid, name, state, selected))
            seen.add(eid)
    if selected and selected not in seen:
        out.insert(1, _option(selected, selected, "non trovata", selected))
    return "".join(out)


def all_entities_json(state_cache: dict) -> str:
    """Tutti i media_player (per «mostra tutti»), come JSON sicuro da mettere in un <script type=application/json>."""
    data = [{"id": eid, "name": name, "state": state, "tv": is_tv}
            for is_tv, _un, name, eid, state in _media_players(state_cache)]
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")     # «<» come \\u003c: mai un tag nel JSON


def remote_options(state_cache: dict, selected: str) -> str:
    """<option> delle entità remote.* (telecomando della TV, opzionale)."""
    out = ['<option value="">— nessuno / automatico —</option>']
    seen = set()
    for eid, st in sorted((state_cache or {}).items(), key=lambda kv: kv[0]):
        if not eid.startswith("remote."):
            continue
        a = (st or {}).get("attributes") or {}
        out.append(_option(eid, str(a.get("friendly_name") or eid), str((st or {}).get("state", "")), selected))
        seen.add(eid)
    if selected and selected not in seen:
        out.insert(1, _option(selected, selected, "non trovata", selected))
    return "".join(out)


def brand_options(selected: str) -> str:
    sel = selected if selected in {k for k, _ in BRAND_CHOICES} else "auto"
    return "".join(f'<option value="{k}" {"selected" if k == sel else ""}>{_html.escape(lbl)}</option>'
                   for k, lbl in BRAND_CHOICES)


_TAB_HTML = """
<div id="tc-tv" class="tc">
  <div class="sec pu">
    <h2>📺 TV</h2>
    <div class="desc">Funziona con la TV che hai già collegato a Home Assistant (LG webOS, Samsung, Sony Bravia, Philips, Android TV…): HomeMind usa la sua entità, niente IP da inserire qui.</div>
    <div class="tl" style="margin-bottom:6px">📺 Entità della TV</div>
    <select id="tv_entity" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px;font-size:.85rem">__ENTITIES__</select>
    <label style="display:flex;gap:6px;align-items:center;margin-top:6px;color:#94a3b8;font-size:.76rem"><input type="checkbox" id="tv_show_all" onchange="tvEntFill(this.checked)"> Non vedi la tua TV? Mostra tutti i lettori multimediali</label>
    <script type="application/json" id="tv_all_json">__ALLJSON__</script>
    <div id="tv_status" class="ts" style="margin-top:6px"></div>
    <div class="tl" style="margin:12px 0 6px">🏷️ Marca</div>
    <select id="tv_brand" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px;font-size:.85rem">__BRANDS__</select>
    <div id="tv_brand_note" class="ts" style="margin-top:6px"></div>
    <div class="ts" style="margin-top:4px">Accensione, volume, muto, canale, ingressi e pausa funzionano con ogni TV. La marca serve solo per i tasti del telecomando (frecce, OK, numeri).</div>
    <div class="tl" style="margin:12px 0 6px">🎛️ Telecomando (opzionale)</div>
    <select id="tv_remote" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px;font-size:.85rem">__REMOTES__</select>
    <div class="ts" style="margin-top:6px">Per Samsung e Sony i tasti passano dall'entità <code>remote.…</code> della TV: di solito la trova da sola, altrimenti sceglila qui. Per LG non serve.</div>
    <div class="tl" style="margin:12px 0 6px">🔌 Accensione (opzionale)</div>
    <div class="ts" style="margin-bottom:6px">Per accendere la TV a distanza serve il suo indirizzo MAC (Wake-on-LAN; nella scheda LG è lo stesso campo). Senza MAC si usa l'accensione già configurata in Home Assistant, se c'è. Con la TV spenta, «metti canale 35» la accende da sola se c'è il MAC.</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <input id="tv_mac" type="text" value="__MAC__" placeholder="AA:BB:CC:DD:EE:FF" style="flex:1;min-width:170px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px;font-size:.85rem">
      <input id="tv_bcast" type="text" value="__BCAST__" placeholder="Broadcast (opzionale, es. 192.168.1.255)" style="flex:1;min-width:170px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px;font-size:.85rem">
    </div>
    <div class="tr" style="margin-top:10px">
      <div><div class="tl">↕️ Passo del volume</div><div class="ts">Di quanto «alza/abbassa il volume» (1–30, di default 5)</div></div>
      <input id="tv_step" type="number" min="1" max="30" value="__STEP__" style="width:70px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px;text-align:center">
    </div>
  </div>

  <div class="sec pu">
    <h2>🔊 Voce e notifiche</h2>
    <div class="desc">Esempi: <i>«alza il volume della tv»</i>, <i>«metti canale 35»</i>, <i>«metti Rai 1»</i>, <i>«metti netflix sulla tv»</i>, <i>«metti la tv muto»</i>. Richiede <b>Alexa Media Player</b>. Su Telegram: <code>/tv volume 30</code>, <code>/tv canale 35</code>, <code>/tv spegni</code>.</div>
    <div class="tr">
      <div><div class="tl">🎙️ Comandi a voce (Alexa)</div><div class="ts">Ascolta le frasi dette ad Alexa e comanda la TV</div></div>
      <label class="sw"><input type="checkbox" id="tv_alexa" __ALEXA__><span class="sl"></span></label>
    </div>
    <div class="tr">
      <div><div class="tl">✈️ Notifica Telegram</div><div class="ts">Manda su Telegram l'esito di ogni comando dato a voce</div></div>
      <label class="sw"><input type="checkbox" id="tv_tg" __TG__><span class="sl"></span></label>
    </div>
    <div class="tr">
      <div><div class="tl">🗣️ Conferma a voce</div><div class="ts">Dopo il comando risponde sugli speaker selezionati («Canale 35»)</div></div>
      <label class="sw"><input type="checkbox" id="tv_confirm" __CONFIRM__><span class="sl"></span></label>
    </div>
    <div class="tr">
      <div style="flex:1"><div class="tl">🔊 Volume della conferma</div></div>
      <input type="range" id="tv_vol" min="0" max="100" step="5" value="__VOL__" style="flex:1;max-width:180px" oninput="document.getElementById('tv_vol_lbl').textContent=this.value+'%'">
      <span id="tv_vol_lbl" style="min-width:40px;text-align:right;color:#94a3b8;font-size:.78rem">__VOL__%</span>
    </div>
    <div style="margin-top:10px">
      <div class="tl" style="margin-bottom:6px">📻 Speaker per la conferma</div>
      <input class="search" type="text" placeholder="🔍 Cerca speaker..." oninput="filt('tv_sp_list',this.value)">
      <div id="tv_sp_list" class="el" style="max-height:220px;overflow-y:auto">__SPEAKERS__</div>
    </div>
    <div style="margin-top:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <button type="button" onclick="tvSave()" style="background:#22c55e;border:none;border-radius:6px;color:#fff;padding:8px 16px;cursor:pointer;font-size:.85rem;font-weight:600">💾 Salva impostazioni TV</button>
      <span id="tv_set_msg" style="color:#94a3b8;font-size:.78rem"></span>
    </div>
    <div class="ts" style="margin-top:6px">Si salvano da qui, subito (non serve il pulsante «Salva» generale).</div>
    <div class="ts" style="margin-top:10px"><b>Alexa risponde prima di HomeMind?</b> Alexa conosce già «accendi/spegni la tv» (skill della tua TV) e per volume e canale risponde che non può. Per far parlare solo HomeMind crea nell'app Alexa una <b>routine</b> per ogni frase che usi (Quando → Voce → la frase, es. <i>metti canale 35</i>) con un'azione silenziosa (es. «Aspetta»). Per i canali con numeri diversi conviene una routine per ciascun nome (<i>metti rai uno</i>).</div>
  </div>

  <div class="sec pu">
    <h2>📡 Canali</h2>
    <div class="desc">Per dire «metti Rai 1» serve la corrispondenza nome → numero della TV (i numeri sono quelli della lista canali della TUA TV: sul digitale terrestre Rai 1 è il <code>1</code>). Senza questo file «metti canale 35» funziona comunque. Formato JSON: <code>{"canali":[{"nome":"Rai 1","numero":"1","alias":["rai uno"]}]}</code> oppure <code>{"Rai 1":"1"}</code>. Il file d'esempio contiene i canali nazionali del digitale terrestre e le frasi per il volume: scaricalo, correggi i numeri e ricaricalo.</div>
    <div id="tv_ch_status" class="ts" style="margin-bottom:8px"></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <input type="file" id="tv_ch_file" accept=".json,application/json" style="display:none" onchange="tvUploadCh(this)">
      <button type="button" onclick="document.getElementById('tv_ch_file').click()" style="background:#22c55e;border:none;border-radius:6px;color:#fff;padding:8px 16px;cursor:pointer;font-size:.85rem;font-weight:600">📤 Carica canali (JSON)</button>
      <a href="#" onclick="this.href=API_BASE+'/api/tv/example'" download="tv_canali_esempio.json" style="color:#38bdf8;font-size:.8rem">⬇️ Scarica file d'esempio</a>
    </div>
    <div id="tv_ch_msg" class="ts" style="margin-top:8px"></div>
    <div id="tv_ch_view" class="ts" style="margin-top:8px"></div>
  </div>

  <div class="sec pu">
    <h2>🧪 Prova un comando</h2>
    <div class="desc">Scrivi quello che diresti. Il comando viene eseguito davvero sulla TV.</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <input id="tv_q" type="text" value="alza il volume della tv" style="flex:1;min-width:200px;background:#0f172a;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:8px;font-size:.85rem">
      <button type="button" onclick="tvTest()" style="background:#0ea5e9;border:none;border-radius:6px;color:#fff;padding:8px 16px;cursor:pointer;font-size:.85rem;font-weight:600">▶️ Esegui</button>
    </div>
    <div id="tv_test_msg" class="ts" style="margin-top:8px;white-space:pre-wrap"></div>
  </div>
</div>
"""

_JS = r"""
function tvMsg(id, ok, txt){var e=document.getElementById(id); if(!e) return; e.style.color= ok===null?'#fbbf24':(ok?'#22c55e':'#ef4444'); e.textContent=txt;}
function tvEsc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
var TV_ALL=null;
function tvEntFill(all){
  var sel=document.getElementById('tv_entity'); if(!sel) return;
  if(TV_ALL===null){try{TV_ALL=JSON.parse(document.getElementById('tv_all_json').textContent)||[];}catch(e){TV_ALL=[];}}
  if(!TV_ALL.length) return;
  var cur=sel.value, h='<option value="">— scegli la TV —</option>', seen=false;
  TV_ALL.forEach(function(x){
    if(all||x.tv||x.id===cur){ if(x.id===cur) seen=true;
      h+='<option value="'+tvEsc(x.id)+'"'+(x.id===cur?' selected':'')+'>'+tvEsc(x.name)+' · '+tvEsc(x.id)+' ('+tvEsc(x.state)+')</option>'; }
  });
  if(cur&&!seen) h+='<option value="'+tvEsc(cur)+'" selected>'+tvEsc(cur)+' (non trovata)</option>';
  sel.innerHTML=h; sel.value=cur;
}
var TV_BRAND_NAMES={lg:'LG webOS',samsung:'Samsung',sony:'Sony Bravia',other:'altra marca'};
function tvRender(st){
  var bn=document.getElementById('tv_brand_note');
  if(bn){ var b=document.getElementById('tv_brand').value;
    bn.textContent=(b==='auto'&&st.entity)?('Marca riconosciuta: '+(TV_BRAND_NAMES[st.brand_detected]||'non riconosciuta (provo come LG)')+(st.remote_detected?(' · telecomando: '+st.remote_detected):'')):''; }
  var s=document.getElementById('tv_status');
  if(!st.entity){s.textContent='Nessuna TV scelta.';}
  else{ s.textContent='Stato: '+(st.tv_state||'sconosciuto')+(st.tv_volume!=null?(' · volume '+st.tv_volume+'%'):'')+(st.tv_source?(' · '+st.tv_source):'')+(st.sources&&st.sources.length?(' · ingressi/app: '+st.sources.join(', ')):''); }
  var c=document.getElementById('tv_ch_status'), v=document.getElementById('tv_ch_view');
  if(st.channels_error){c.textContent='⚠️ Errore nel file salvato: '+st.channels_error;}
  else if(!st.channels.length){c.textContent='📭 Nessun file canali (puoi dire comunque «canale 35»).';}
  else{c.textContent='✅ '+st.channels.length+' canali';}
  var h='';
  if(st.channel_warnings&&st.channel_warnings.length){h+='<div style="color:#fbbf24">⚠️ '+st.channel_warnings.map(tvEsc).join('<br>⚠️ ')+'</div>';}
  if(st.channels.length){h+=st.channels.map(function(x){return tvEsc(x.nome)+' → '+tvEsc(x.numero)+(x.alias&&x.alias.length?(' <span style="color:#94a3b8">('+x.alias.map(tvEsc).join(', ')+')</span>'):'');}).join('<br>');}
  v.innerHTML=h;
}
async function tvLoad(){
  try{var r=await fetch(API_BASE+'/api/tv/state'); tvRender(await r.json());}catch(e){tvMsg('tv_status',false,'❌ '+e);}
}
async function tvSave(){
  tvMsg('tv_set_msg',null,'⏳ Salvo…');
  var body={entity:document.getElementById('tv_entity').value,
            brand:document.getElementById('tv_brand').value,
            remote_entity:document.getElementById('tv_remote').value,
            mac:document.getElementById('tv_mac').value.trim(),
            broadcast_address:document.getElementById('tv_bcast').value.trim(),
            step:parseInt(document.getElementById('tv_step').value)||5,
            alexa_enabled:document.getElementById('tv_alexa').checked,
            telegram_enabled:document.getElementById('tv_tg').checked,
            confirm_voice:document.getElementById('tv_confirm').checked,
            speakers:getSel('tv_sp'),
            volume:(parseInt(document.getElementById('tv_vol').value)||50)/100};
  try{
    var r=await fetch(API_BASE+'/api/tv/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    var res=await r.json();
    if(res.ok){
      var w='';
      if(!body.entity) w=' ⚠️ Scegli prima la TV.';
      else if(body.confirm_voice && body.speakers.length===0) w=' ⚠️ Conferma a voce attiva ma nessuno speaker selezionato.';
      tvMsg('tv_set_msg',true,'✅ Salvato.'+w); tvLoad();
    } else tvMsg('tv_set_msg',false,'❌ '+(res.error||'Errore'));
  }catch(e){tvMsg('tv_set_msg',false,'❌ '+e);}
}
async function tvUploadCh(inp){
  var f=inp.files&&inp.files[0]; if(!f) return;
  tvMsg('tv_ch_msg',null,'⏳ Carico '+f.name+'…');
  try{
    var text=await f.text();
    var r=await fetch(API_BASE+'/api/tv/channels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({json:text})});
    var res=await r.json();
    if(res.ok){tvMsg('tv_ch_msg',true,'✅ '+res.message); tvRender(res.state);}
    else tvMsg('tv_ch_msg',false,'❌ '+(res.error||'Errore')+' — i canali precedenti sono rimasti invariati.');
  }catch(e){tvMsg('tv_ch_msg',false,'❌ '+e);}
  inp.value='';
}
async function tvTest(){
  var q=document.getElementById('tv_q').value.trim(); if(!q) return;
  tvMsg('tv_test_msg',null,'⏳ Eseguo…');
  await tvSave();
  try{
    var r=await fetch(API_BASE+'/api/tv/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:q,test:true})});
    var res=await r.json();
    if(!res.matched){tvMsg('tv_test_msg',false,'❌ Frase non riconosciuta come comando per la TV (serve la parola «tv» o «canale»).'); return;}
    tvMsg('tv_test_msg',!!res.executed,(res.executed?'✅ ':'❌ ')+res.message); tvLoad();
  }catch(e){tvMsg('tv_test_msg',false,'❌ '+e);}
}
window.addEventListener('load',tvLoad);
"""


def build_tab(cfg_tv: dict, entities_block: str, speakers_block: str,
              remotes_block: str = "", all_json: str = "[]") -> str:
    c = cfg_tv if isinstance(cfg_tv, dict) else {}
    try:
        vol = int(max(0.0, min(1.0, float(c.get("volume", 0.5)))) * 100)
    except (TypeError, ValueError):
        vol = 50
    try:
        step = max(1, min(30, int(c.get("step", 5))))
    except (TypeError, ValueError):
        step = 5
    esc = lambda v: _html.escape(str(v or ""), quote=True)  # noqa: E731
    return (_TAB_HTML
            .replace("__ENTITIES__", entities_block)
            .replace("__ALLJSON__", all_json)
            .replace("__BRANDS__", brand_options(str(c.get("brand") or "auto")))
            .replace("__REMOTES__", remotes_block or '<option value="">— nessuno / automatico —</option>')
            .replace("__MAC__", esc(c.get("mac")))
            .replace("__BCAST__", esc(c.get("broadcast_address")))
            .replace("__STEP__", str(step))
            .replace("__ALEXA__", "checked" if c.get("alexa_enabled") else "")
            .replace("__TG__", "checked" if c.get("telegram_enabled") else "")
            .replace("__CONFIRM__", "checked" if c.get("confirm_voice") else "")
            .replace("__VOL__", str(vol))
            .replace("__SPEAKERS__", speakers_block))


def build_js() -> str:
    return _JS
