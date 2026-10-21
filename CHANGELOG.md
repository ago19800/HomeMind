# Changelog

All notable changes to HomeMind Orchestrator are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.11.15] — 2026-10-21

### Changed
- **Salva file dalla chat — più chiaro e più tollerante:** capisce gli errori di battitura nel nome della cartella (`invia in documeti`); se la funzione è spenta o senza cartelle e scrivi una didascalia di salvataggio ("invia nella cartella", "salva in documenti"), il bot spiega cosa attivare nella pagina web invece di mostrare il suggerimento sull'email; nuove righe di log `FileInbox: configurazione letta…` e `FileInbox: file …` per vedere cosa è stato deciso. Con didascalie non di salvataggio il comportamento a funzione spenta resta quello di sempre (`agent/file_inbox.py`, `telegram_bot.py`).

---

## [1.11.14] — 2026-10-20

### Added
#### 📁 Salva file dalla chat → cartella
Mandi un file al bot con la didascalia `invia nella cartella` (o `salva in <nome cartella>`): HomeMind lo salva nella cartella scelta e **cancella il messaggio da Telegram**. Le cartelle (nome, percorso, predefinita) e l'opzione "cancella dopo il salvataggio" si impostano nella nuova scheda **📁 File** della pagina web; valgono subito dopo Salva. Senza didascalia il bot mostra i bottoni con le cartelle; gli album (più file insieme) vanno nella stessa cartella con un solo riepilogo. Sicurezza: cartelle definibili solo dalla pagina web, mai sovrascrive (aggiunge ` (1)`), nome file ripulito, cartelle di sistema rifiutate, messaggio cancellato solo a salvataggio riuscito, limite 20 MB (limite Telegram per i bot). Con la funzione spenta (default) il bot risponde esattamente come prima (`agent/file_inbox.py` nuovo; `telegram_bot.py`, `main.py`).

### Changed
- `config.yaml`: l'add-on ora mappa anche `/share` e `/media` (`share:rw`, `media:rw`), oltre a `/config`, così si può salvare anche lì. Dopo l'aggiornamento usa **Aggiorna/Ricostruisci**.

---

## [1.11.13] — 2026-10-20

### Fixed
- **Impostazioni cambiate da chat non applicate fino al riavvio:** dopo una modifica fatta parlando con il bot (ConfigEditor), il ricaricamento della configurazione chiamava un metodo inesistente (`_load_person_config`) e l'errore veniva ignorato in silenzio; il file era salvato ma il modello in memoria restava vecchio. Ora chiama `_load_config` e la modifica vale subito (`main.py`).

### Docs
- README: FAQ "non ricevo più la notifica quando esco" con la tabella dei comportamenti all'uscita e i messaggi di log che spiegano un eventuale silenzio.

---

## [1.11.12] — 2026-10-19

### Fixed
- **Foto Frigate su allarme scartate subito dopo l'avvio della macchina:** il controllo anti-duplicati (60 s) partiva da `0` e usava il tempo di accensione dell'host, quindi nei primi 60 secondi dopo il boot le foto venivano saltate come se fossero appena state inviate. Ora la prima foto parte sempre; la pausa di 60 s tra due invii resta (`agent/security_manager.py`).
- **Avvisi Frigate duplicati dopo un'ora:** se dopo un avviso non arrivavano altri eventi, passata un'ora HomeMind dimenticava l'evento già notificato mentre Frigate lo restituiva ancora nella finestra di ricerca, e rimandava la stessa foto come se fosse nuova (es. avviso delle 7:49 ripetuto alle 8:48). Ora un evento viene dimenticato solo quando Frigate non può più restituirlo (`agent/frigate_alerts.py`).

---

## [1.11.11] — 2026-10-18

### Added

#### 🎯 Confidenza minima per gli avvisi Frigate (meno falsi allarmi)
Nel tab 📹 Frigate, accanto agli switch, nuovo campo **Confidenza minima (%)** (0 = nessun filtro, come prima). Al primo avvistamento Frigate dà lo score più basso (es. ~71%): con il filtro attivo l'avviso resta in attesa e parte solo se lo score sale oltre la soglia; se l'evento finisce (o passano 60 s) sotto soglia viene scartato e la pausa tra avvisi viene rilasciata. L'avviso mostra lo score aggiornato. Il log di avvio riporta ora `build 1.11.11` per verificare quale versione è in esecuzione (`agent/frigate_alerts.py`, `agent/frigate_client.py: get_event`, `main.py`: campo UI + `getFgConfig`).

### Fixed
- **"Dove era X il 5 ottobre":** il gestore generico delle soste ignorava le date e rispondeva con le *ultime 24 ore* senza avvisare. Ora legge `5 ottobre`, `5/10`, `05-10-2026` e `ieri` (giorno esatto 00:00–24:00, prima "ieri" mostrava 48 ore), mostra le soste di quel giorno in ordine cronologico e, se Home Assistant non ha più i dati, lo dice chiaramente. Nuovo: `tutti i posti` / `anche le brevi` abbassa la soglia delle soste a 3 minuti (`location_tracker.py`: parametro opzionale `day`, etichetta `period_label`).
- **Tracciamento posizioni:** il "rinfresco" delle soste GPS prima di rispondere a domande tipo *"dove è stato X il 5 ottobre"* non partiva mai (`now_local` non importato; l'errore veniva nascosto a livello debug). Ora l'import è presente.
- **`ha_terminal.py`:** mancava `import asyncio` (un errore HTTP/timeout nel tool API produceva un `NameError` invece del messaggio) e `_tools` non era importato nei canali `ping` e `portscan`.
- **Docker:** aggiunto `.env.example` (era citato nelle istruzioni ma non esisteva); corretto l'URL in `INSTALL_DOCKER.md`.

### Docs
- Nuovo `README.md` completo (Frigate, targhe, avvisi per oggetto, antifurto GPS, tracciamento, email, aggiornamento). Il vecchio file si chiamava `README .md` (con uno spazio) e non veniva letto da GitHub/Home Assistant.

---

## [1.11.10] — 2026-10-17

### Added

#### 🚗 Targhe rilevate da Frigate (LPR) interrogabili da Telegram
Se Frigate è abilitato, il bot risponde direttamente (senza AI) a domande sulle targhe: `che targhe hai rilevato?`, `targhe ieri`, `targhe garage oggi`, `targhe ultime 6 ore`, `targhe ultimi 3 giorni`, `hai visto la targa AB123CD?`. Mostra targhe raggruppate con numero di passaggi, camera, orari, confidenza e nome (se targa nota in Frigate), più la foto dell'ultimo rilevamento. Nessuna nuova configurazione: usa `host`/`port`/`cameras` già presenti nella sezione `frigate`. Richiede Frigate ≥ 0.16 con LPR attivo. Il comportamento antifurto/snapshot esistente è invariato (`frigate_client.py`: `get_recent_plates`, `get_event_snapshot`; `telegram_bot.py`: `_handle_plates_query`).

#### 🕐 Periodi e categorie più flessibili nelle richieste Frigate
Targhe e rilevamenti ora capiscono `ultima ora`, `ultimi 30 minuti`, `mezz'ora`, `quarto d'ora`, `ultime due ore`, oltre a ore/giorni/oggi/ieri/settimana/mese (prima "ultima ora" ricadeva sulle 24 ore). Nuova categoria `animali` = cani + gatti + uccelli. Basta anche una frase breve come `persone ultima ora` o `animali`; auto/moto/bici richiedono parole come "rilevate/visto" per non confondersi con altri comandi (es. ricarica auto).

#### 🔔 Avvisi istantanei Frigate per oggetto (switch nella pagina web)
Nel tab **📹 Frigate** della pagina web ci sono switch per tipo di oggetto (persone, cani, gatti, auto, moto, bici, pacchi, uccelli): se attivo, appena Frigate rileva quell'oggetto la foto arriva subito su Telegram, indipendentemente dall'allarme. Opzione "pausa tra due avvisi" (default 60 s, 0 = ogni rilevamento) per evitare raffiche sulla stessa camera. Gli switch valgono subito dopo il salvataggio, senza riavvio. Tutti spenti (default) = modulo inattivo, nessuna richiesta a Frigate. All'avvio gli eventi già esistenti non generano avvisi. Il salvataggio non cancella gli avvisi se la pagina era aperta con una versione precedente (`agent/frigate_alerts.py` nuovo; `main.py`: UI, `getFgConfig`, avvio watcher).

#### 🎥 Rilevamenti Frigate di persone, cani, gatti, auto, moto, bici, pacchi
Stesso meccanismo delle targhe: `hai visto persone oggi?`, `che cani hai rilevato?`, `cosa hai rilevato ieri`, `chi è passato dal garage`, `gatti ultimi 3 giorni`. Riepilogo per tipo e camera, ultimi 10 rilevamenti con orario/confidenza (e nome se Frigate ha riconosciuto un volto), più le foto di tutti i rilevamenti con snapshot, inviate in album da 10 (massimo 40 foto per richiesta, con avviso se ce ne sono di più). Se una camera ha lo stesso nome di un oggetto (es. camera `auto`), conta come camera solo se introdotta da `camera/dalla/sul/nel…`. Le frasi di presenza in casa (`chi è a casa`, `persone presenti`) e le richieste di modifica config non vengono intercettate e proseguono verso l'AI come prima (`frigate_client.py`: `get_recent_detections`; `telegram_bot.py`: `_handle_detection_query`).

---

## [1.11.9] — 2026-05-01

### Fixed

#### 🛠️ /fai non veniva passato all'agente quando conteneva pattern temporali nel testo
I comandi `/fai` con orari nel testo (es. nei nomi delle automazioni tra virgolette) venivano intercettati dallo scheduler invece di essere passati all'agente. Aggiunto guard early-return su comandi slash espliciti, rimozione preventiva di stringhe quotate prima del matching, e pattern di rilevamento delle richieste di edit configurazione (`telegram_bot.py`).

#### 📝 ai_edit_file riscrittura completa con modalità patch sicura
Riscritto `ai_edit_file` per usare ESCLUSIVAMENTE patch JSON `{old, new}` invece di chiedere il file intero all'AI. Vantaggi:
- Funziona con file grandi senza sforare context window dei provider AI
- Impossibile inventare contenuto su file vuoti (GUARD anti-invenzione)
- Verifica nomi citati esistano nel file prima di modificare
- Backup automatici centralizzati in `/config/homemind_patches/backups/`
- Anti-drift: rifiuta patch che cambiano la dimensione del file di > 30%
- Estrazione contestuale TF-IDF + scoring per finestre rilevanti

#### 📂 _safe_path normalizza il prefisso config/ senza slash
`_safe_path` ora tratta `config/X` (senza slash iniziale) come `/config/X`, evitando di creare sottocartelle indesiderate `/config/config/`. Aggiunto sanity check anti-`/config/config/` in `ai_edit_file` (`tools_system.py`, `agentic_executor.py`).

#### 👥 Aggiunto tool ha_list_users
Sostituisce il pattern errato `ha_call_service(domain="person", service="list_users")` (servizio non esistente in HA) con un tool dedicato che legge direttamente le entità `person.*` via REST. Accetta 6 alias (`ha_list_users`, `ha_list_persons`, `list_users`, `list_persons`, `ha_users`, `ha_persons`) (`agentic_executor.py`).

#### ✅ finish ora gestito anche dentro execute_tool
Il tool `finish` era documentato nel prompt ma gestito solo nel loop esterno: se l'AI lo chiamava da dentro un plan/parallel_steps, riceveva "Tool sconosciuto". Ora ritorna successo con il messaggio anche dal dispatcher (`agentic_executor.py`).

#### 🔀 /ssh routing deterministico file ops → container
`/ssh elimina prova` (e simili) eseguivano `rm -rf prova` sull'host invece che nel container, dove vivono i file in `/config`. Aggiunto pre-routing deterministico: richieste con verbi file-op + path utente sono ora forzate a `container_shell` senza coinvolgere l'AI. Aggiornato anche il prompt di `run_natural` con esempi chiari host vs container (`ha_terminal.py`).

#### 📖 Help /ssh — sezioni gestione addon e Home Assistant
Aggiunte due nuove sezioni nel `/ssh help`: comandi per gestione addon (`ha addons stop/start/restart/info/logs`) e gestione HA core (`ha core restart/stop/check`), con nota sullo slug senza spazi (`telegram_bot.py`).

---

## [1.5.8] — 2026-04-15

### Added

#### 🔓 Welcome notification with alarm status
When arriving home while the alarm was armed, the welcome Telegram message now includes the alarm disarm status:
```
🏠 HomeMind: Bentornato!
Agostino rientrato/a
In casa: Agostino, Rosa
Ora: 18:32
🔓 Antifurto disarmato (era: 🏃 via da casa)
```

#### 🤖 AI Automations in natural language
Create Home Assistant automations directly from Telegram using natural language:
> *"Crea automazione: quando sensore scala rileva movimento alle 23, accendi luce esterna e mandami notifica Telegram"*

HomeMind generates valid YAML, uses real entity IDs from the **EntityRegistry**, and saves the automation to `automations.yaml` with automatic reload.

**How it works:**
- `EntityRegistry` scans all HA entities every 15 minutes and builds a local catalogue
- Motion sensors are enriched with their zone (e.g. `[zona:cucina]`, `[zona:scala]`) so the AI can match natural language to the correct `entity_id`
- Telegram notifications use `telegram_bot.send_message` with the configured `chat_id` (the legacy `notify.telegram` service is deprecated in HA 2026+)
- If an automation with the same `id` already exists, it is **replaced** (upsert) instead of duplicated — preventing reload errors

#### ⏱️ Configurable delay between alarm partitions (`alarm_extra_delay`)
For multi-partition systems (EvoHD, Paradox, DSC) that reject commands sent too quickly, a configurable delay is now applied between each partition during both arming and disarming:

```json
"alarm_extra_panels": [
  "alarm_control_panel.evohd_partition_esterno",
  "alarm_control_panel.evohd_partition_riv_est_1_piano"
],
"alarm_extra_delay": 2
```

Default is `1` second. Can be set from the web UI under **Antifurto → ⏱️ Delay tra partizioni extra**.

### Fixed

#### 🚫 `alarm_auto_arm: disabled` now blocks disarm too
Previously, `disabled` mode only prevented HomeMind from **arming** the alarm. On return, HomeMind would still **disarm** it automatically. Now `disabled` is a full hands-off mode — HomeMind never touches the alarm in either direction.

#### 👋 Welcome notification after HomeMind restart
`_was_away` (the flag that gates welcome notifications) was reset to `False` on every restart. If HomeMind restarted while you were away, no welcome would be sent on return. **Fixed:** `startup_check` and the 2-minute rebuild loop now re-initialise `_was_away = True` for anyone the GPS shows as away.

#### 🔁 Proximity near/far transition — welcome trigger
The "proximity becomes near → trigger welcome" logic was firing on every proximity sensor update (even when stationary at 0m). **Fixed:** the trigger now only fires on a genuine **far→near transition** (previous value > threshold, new value ≤ threshold), preventing duplicate welcome notifications when a second person arrives home.

#### 📍 Entity IDs in AI automations
Previously the AI could invent entity IDs (e.g. `light.luce_mario`) instead of using real ones. **Fixed:** the `EntityRegistry` now feeds the AI a structured catalogue:
```
[light] Luce Mario → light.yeelight_ct_bulb_0x536fe64 (off)
[binary_sensor] Sensore occupancy [zona:scala] → binary_sensor.0x00158d000224fa71_occupancy (off)
```

---

## [1.5.7] — previous release

See git history.
