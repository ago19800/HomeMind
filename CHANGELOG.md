
```markdown
# 🛡️ HomeMind Orchestrator - Changelog

<!-- All notable changes to HomeMind Orchestrator are documented here. -->
# Changelog
 
## [1.6.1] — 2026-04-21
 
### Added
 FIX: ALLARME
#### 🔊 Annuncio vocale Alexa per notifiche spazzatura
Nella sezione **Spazzatura** del pannello web, nuova opzione per inviare un annuncio TTS sugli speaker Alexa all'ora configurata, in aggiunta o in alternativa al messaggio Telegram.
 
- **Switch** indipendente per abilitare/disabilitare l'annuncio vocale
- **Selettore speaker** multiplo — l'annuncio parte contemporaneamente su tutti
- **Slider volume** 0–100% applicato automaticamente prima dell'annuncio
- **Pulsante "Test annuncio"** per verificare subito senza aspettare l'orario schedulato
- Speaker non disponibili (`unavailable`/`unknown`) nascosti automaticamente dalla lista
> Richiede l'integrazione **Alexa Media Player** installata in Home Assistant.
 
---
 
## [1.5.8] — 2026-04-17
 
Vedi release precedente.
 



## [1.6.0] —
FIX- VARI

## [1.5.9] —
FIX- VARI

## [1.5.8] — 📅 2026-04-15

### ✨ Aggiunto (Added)

#### 🔓 Notifica di Benvenuto con stato dell'allarme
Quando si rientra in casa e l'allarme era armato, il messaggio Telegram di benvenuto include ora lo stato preciso dello sblocco dell'allarme:


🏠 HomeMind: Bentornato!
Agostino rientrato/a
In casa: Agostino, Rosa
Ora: 18:32
🔓 Antifurto disarmato (era: 🏃 via da casa)
```

#### 🤖 Automazioni IA in linguaggio naturale
È possibile creare automazioni Home Assistant direttamente tramite Telegram usando un semplice linguaggio naturale.

**Esempio di utilizzo:**
> *"Crea automazione: quando sensore scala rileva movimento alle 23, accendi luce esterna e mandami notifica Telegram"*

HomeMind genera YAML valido per HA, utilizzando ID di entità reali dal **Registry delle Entità** (`EntityRegistry`), e salva l'automazione in `automations.yaml` con ricaricamento automatico.

*   **Funzionamento:**
    *   Il `Registry delle Entità` scansiona tutte le entità HA ogni 15 minuti, costruendo un catalogo locale aggiornato.
    *   I sensori di movimento vengono arricchiti anche con la loro zona (es. `[zona:cucina]`, `[zona:scala]`), permettendo all'IA di abbinare il linguaggio naturale all'`entity_id` corretto.
    *   Le notifiche Telegram utilizzano `telegram_bot.send_message` con lo `chat_id` configurato (il servizio legacy `notify.telegram` è deprecato in HA 2026+).
    *   Se un'automazione con lo stesso `id` esiste già, viene **sostituita** (`upsert`) invece di duplicata — prevenendo errori di ricaricamento.

#### ⏱️ Ritardo configurabile tra le partizioni d'allarme (`alarm_extra_delay`)
Per i sistemi multiparticellari (EvoHD, Paradox, DSC) che rifiutano comandi inviati troppo rapidamente, è stato applicato un ritardo configurabile tra ogni partizione, sia durante l'armamento che lo smarramento:

```json
"alarm_extra_panels": [
 "alarm_control_panel.evohd_partition_esterno",
 "alarm_control_panel.evohd_partition_riv_est_1_piano"
],
"alarm_extra_delay": 2
```
*(Default: 1 secondo. Può essere impostato dall'interfaccia web sotto **Antifurto → ⏱️ Ritardo tra partizioni extra**).*

### 🐛 Corretti (Fixed)

#### 🚫 `alarm_auto_arm: disabled` ora blocca anche lo smarramento
Precedentemente, la modalità `disabled` impediva solo a HomeMind di *armare* l'allarme. Al rientro, invece, poteva ancora **disattivarlo** automaticamente. Ora `disabled` è una modalità completamente passiva: HomeMind non tocca l'allarme in nessuna direzione.

#### 👋 Notifica di benvenuto dopo il riavvio di HomeMind
Il flag `_was_away` (che controlla le notifiche di benvenuto) veniva reimpostato su `False` ad ogni riavvio. Se HomeMind si era riavviato mentre eri assente, non veniva inviato nessun benvenuto al tuo rientro. **Corretto:** lo `startup_check` e il ciclo di ricreazione dei 2 minuti re-inizializzano `_was_away = True` per chiunque la posizione GPS mostri come assente.

#### 🔁 Transizione vicinanza/lontananza — trigger benvenuto
La logica "passaggio da vicino a lontano $\rightarrow$ attiva il benvenuto" si attivava ad ogni aggiornamento del sensore di prossimità (anche quando fermi allo 0m). **Corretto:** ora il trigger scatta solo su una genuina transizione **da lontano $\rightarrow$ vicino** (valore precedente > soglia, nuovo valore $\le$ soglia), evitando notifiche duplicate in caso di arrivo simultaneo.

#### 📍 ID Entità nelle automazioni IA
In precedenza, l'IA poteva inventare ID entità (es. `light.luce_mario`) anziché usare quelli reali e corretti. **Corretto:** il `Registry delle Entità` fornisce ora all'IA un catalogo strutturato:

```markdown
[light] Luce Mario → light.yeelight_ct_bulb_0x536fe64 (off)
[binary_sensor] Sensore occupazione [zona:scala] → binary_sensor.0x00158d000224fa71_occupancy (off)
```

---

## [1.5.7] — 🚀 Rilascio precedente

*Consulta la cronologia Git per i dettagli.*
```
