# 📋 Changelog — HomeMind Orchestrator

Tutte le modifiche significative al progetto sono documentate in questo file.

---
## [1.3.4] — 2026-03-21
- Fix: switch

## [1.3.3] — 2026-03-21

### 🔐 Allarme Personalizzato
- Aggiunto supporto per antifurto di qualsiasi marca (Risco, Paradox, Ajax, DSC, Texecom, Bentel ecc.)
- Nuovo campo `alarm_panel` in `person_config.json` — basta aggiungere l'entity ID del proprio antifurto
- Se non configurato, HomeMind continua a funzionare come prima (cerca automaticamente `home_alarm`)
- Se l'entity ID è sbagliato, HomeMind avvisa nel log e torna al comportamento automatico senza bloccarsi

```json
"alarm_panel": "alarm_control_panel.risco_casa"
```

### ☀️ Ottimizzatore Solare — Batteria Piena
- Aggiunto rilevamento surplus quando la batteria è al 100% e l'inverter throttla il FV
- Nuovo campo `battery_soc_sensor` per leggere la percentuale batteria
- Nuovo campo `battery_full_threshold` (default 95%) — soglia per considerare la batteria piena
- Nuovo campo `battery_full_min_fv_w` (default 300W) — produzione FV minima per attivare la notifica
- Nessuna notifica se il sole è tramontato — controllo elevazione solare tramite `sun.sun`
- Nuovo campo `min_sun_elevation` (default 10°) — angolo minimo del sole per attivare le notifiche

### ☀️ Ottimizzatore Solare — Fix calcolo surplus
- Rimossa la media con lo Shelly che distorceva il calcolo
- Il surplus viene ora calcolato solo con FV - consumo (più preciso)
- Lo Shelly rimane disponibile come dato diagnostico nel log

### 🔒 Sicurezza — Fix armamento allarme
- Fix: l'allarme non si armava più quando il sensore GPS non aggiornava per più di 4 ore
- Aggiunto limite massimo di 4 ore per i dati proximity: oltre questa soglia HomeMind usa il GPS
- Fix: notifiche spam "armo" ad ogni aggiornamento GPS quando l'allarme era già in stato `arming`
- Fix: `last_seen` ora viene inizializzato correttamente all'avvio usando `last_updated` dalla cache HA

### 🔒 Sicurezza — Fix notifica benvenuto
- Fix: il benvenuto non arrivava se c'erano stati rimbalzi GPS durante il giorno (cooldown consumato)
- Aggiunto filtro anti-rimbalzo: nessun benvenuto se la persona era via da meno di 5 minuti
- Aggiunto log esplicito del motivo quando il benvenuto viene saltato:
  - `benvenuto SKIP — rimbalzo GPS (via 0 min)`
  - `benvenuto SKIP — cooldown attivo (30 min fa)`
  - `benvenuto schedulato (via 120 min)`

### 📍 Geocoding — Indirizzi rurali italiani
- Migliorato il reverse geocoding per zone rurali (Contrada, Località, Frazione)
- Aggiunto supporto per i campi OSM `hamlet`, `locality`, `isolated_dwelling`
- Fallback migliorato: usa le prime 3 parti del `display_name` invece del quartiere generico

### 💬 Telegram — Comandi spostamenti
- Aggiunte parole chiave naturali per il location tracker:
  - `spostamenti rosa`, `spostamenti agostino`
  - `dove rosa`, `dove agostino`
- Prima funzionava solo con `spostamenti di rosa` (con "di") — ora riconosce frasi senza preposizione

### 💬 Telegram — Comando /solare
- Aggiunto `/solare` alla lista comandi ufficiale (`/comandi`)
- Il comando ora mostra anche la percentuale batteria se `battery_soc_sensor` è configurato

---

## [1.3.0] — precedente

### Fix
- Fix `notify_entity` vuoto che bloccava Telegram — campo ora opzionale
- Fix foto duplicate Frigate — aggiunto cooldown anti-spam 60 secondi per camera

### Funzionalità
- Integrazione Frigate NVR completa
- Snapshot automatici su allarme
- Tab 📹 Frigate nella pagina impostazioni web

---

## [1.2.0] — precedente

### Funzionalità
- Pagina Impostazioni web completa (5 tab: Persone, Sensori, Spazzatura, Energia, Frigate)
- Merge automatico campi avanzati quando si salva dalla pagina web
- I campi `proximity_sensors`, `solar_optimizer`, `appliances` non vengono mai sovrascritti

---

## [1.1.x] — precedente

### Fix
- Fix tab navigazione pagina web
- Fix BOM UTF-8 nei file di configurazione
- Dashboard live

---

## [1.0.4] — precedente

### Funzionalità
- Interfaccia vocale Telegram tramite OpenAI Whisper
- Trascrizione automatica messaggi vocali → comando AI

---

## [1.0.2] — precedente

### Sicurezza
- Codice allarme mai esposto all'AI né ai log
- Autenticazione pagina web
- Log senza dati personali (messaggi Telegram loggati solo come `[N chars]`)

---

## [1.0.0] — release iniziale

- Gestione allarme automatica (arma/disarma in base alla presenza)
- Rilevamento presenza con GPS + sensore prossimità
- Monitor elettrodomestici (modalità power e smart)
- Ottimizzatore solare surplus FV
- Analisi energetica giornaliera con AI
- Briefing mattutino (meteo, energia, spazzatura, consiglio AI)
- Calendario spazzatura da PDF
- Controllo AI via Telegram in linguaggio naturale
- Fallback automatico tra provider AI (Gemini → Groq → Cerebras)
- Supporto italiano e inglese
