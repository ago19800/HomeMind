# 📋 Changelog — HomeMind Orchestrator

Tutte le modifiche significative al progetto sono documentate in questo file.

---
## [1.3.8] — 2026-03-23
  - FIX
## [1.3.7] — 2026-03-23
  — ⚡Power Guard (protezione soglia contrattuale con 3 modalità: warn/ask/auto), - fix: person.xxxxx, 🧠 Memoria persistente Impara le tue preferenze nel tempo, Task Scheduling (pianificazione attività). È diversa dalle automazioni HA perché le crei parlando in modo naturale e sono temporanee.
## [1.3.6] — 2026-03-22
- Fix: Lingua : EN
## [1.3.5] — 2026-03-22

### 📅 Smart Routine Manager (NUOVO)
- HomeMind impara la tua routine reale dai dati HA e anticipa i tuoi bisogni
- Osserva ogni giorno: orario di uscita, rientro, attività in cucina al mattino
- Dopo 3 giorni inizia a fare previsioni
- Quando rileva movimento in cucina vicino all'orario tipico di uscita avvisa su Telegram:
  *"Di solito esci alle 08:30 — mancano 20 minuti. Vuoi che preparo la casa?"*
- Risposta "sì" → abbassa riscaldamento e spegne le luci automaticamente
- Risposta "no" → non fa nulla
- Salvataggio pattern in `/data/homemind_routine.json`
- Nuovo comando `/routine` → mostra orari tipici appresi
- Intercetta conferme "sì/no" su Telegram per la routine
- Registrazione automatica eventi cucina mattutini per il learning

### 🧠 Memoria Persistente (NUOVO)
- HomeMind impara le preferenze dell'utente nel tempo e le usa nelle risposte
- Estrazione automatica dei fatti utili dopo ogni conversazione tramite AI
- Salvataggio in `/data/homemind_memory.json` — persiste tra i riavvii
- Massimo 50 fatti memorizzati, organizzati per categoria
- Categorie: abitudini, preferenze, casa, persone, energia, dispositivi
- Nuovi comandi Telegram:
  - `/memoria` → mostra tutto ciò che HomeMind sa sull'utente
  - `/dimentica <testo>` → rimuove i fatti che contengono quel testo
  - `/memoria reset` → cancella tutta la memoria
- La memoria viene iniettata nel system prompt AI ad ogni conversazione
- Esempio: *"Preferisco 22 gradi la sera"* → HomeMind lo imposta automaticamente la volta dopo

---

## [1.3.4] — 2026-03-21

### 🔐 Antifurto Personalizzato
- Nuovo campo `alarm_panel` nel `person_config.json` — supporta qualsiasi marca integrata in HA
- Supporta due formati:
  - Stringa semplice: `"alarm_panel": "alarm_control_panel.risco_casa"`
  - Oggetto avanzato: `"alarm_panel": {"entity": "...", "arm_mode": "armed_home"}`
- Nuovo campo `arm_mode` per scegliere la modalità di armamento:
  - `armed_away` — tutti fuori (default)
  - `armed_home` — perimetrale, qualcuno in casa
  - `armed_night` — modalità notte
- Compatibile con: Risco, Paradox, Ajax, DSC, Texecom, Bentel, Verisure e qualsiasi altro
- Se non configurato → HomeMind trova automaticamente il primo allarme disponibile
- Se entity ID non trovato in HA → warning nel log + fallback automatico senza bloccarsi

### 🌡️ Clima e Riscaldamento Personalizzato
- Nuovo campo `climate` nel `person_config.json`
- Ogni utente dichiara il proprio impianto con switch fisico separato e range temperatura
- L'AI vede gli switch caldaia nel contesto e capisce come usarli correttamente
- Logica differenziata: con switch → `switch.turn_on`; senza switch → `set_hvac_mode` + `set_temperature`
- Rispetta i limiti min/max configurati — avvisa l'utente se fuori range
- Il blocco clima nel contesto AI mostra: stato, temperatura corrente, target, range, switch collegato

### ☀️ Ottimizzatore Solare — Batteria Piena
- Rileva surplus anche quando la batteria è al 100% e l'inverter throttla il FV
- Controllo elevazione solare tramite `sun.sun` — nessuna notifica se il sole è tramontato
- Nuovi campi: `battery_soc_sensor`, `battery_full_threshold`, `battery_full_min_fv_w`, `min_sun_elevation`
- Messaggio differenziato: "Batteria carica — energia solare disponibile!"

### ☀️ Fix Calcolo Surplus
- Rimossa la media con Shelly che distorceva il calcolo
- Surplus calcolato direttamente: FV - consumo (più preciso)

### 🔒 Fix Benvenuto — Proximity + GPS
- Fix: benvenuto non arrivava quando GPS arrivava prima con proximity ancora alta
- Nuovo scenario gestito: proximity diventa "near" mentre GPS è già "home" → benvenuto

### 🔒 Fix Proximity Stale 4 ore
- Aggiunto limite massimo assoluto di 4h per dati proximity vecchi
- Oltre 4h → HomeMind cede al GPS anche con `stale_check: false`
- `last_seen` inizializzato correttamente all'avvio dalla cache HA

### 🔒 Fix Spam Armamento
- Fix: notifiche "armo" ad ogni aggiornamento GPS con allarme già in `arming`
- Aggiunto controllo stato prima di triggerare l'armamento

### 🔒 Fix Benvenuto Anti-rimbalzo GPS
- Aggiunto filtro: nessun benvenuto se via meno di 5 minuti (rimbalzo GPS)
- Log esplicito del motivo skip

### 📍 Geocoding Zone Rurali Italiane
- Supporto campi OSM: `hamlet`, `locality`, `isolated_dwelling`, `croft`
- Fallback migliorato su `display_name` per zone senza indirizzo strutturato

### 💡 Switch Visibili all'AI
- Aggiunto blocco "SWITCH / PRESE" nel contesto passato all'AI
- L'AI ora sceglie correttamente tra switch fisico e termostato
- Filtro automatico switch di servizio/sistema

### 💬 Comandi Telegram Ampliati
- Trigger naturali per spostamenti: "dove rosa", "spostamenti agostino" ecc.
- Trigger per lista comandi: "cosa sai fare", "cosa puoi fare" ecc.
- Aggiunti: `/solare`, `/memoria`, `/routine` alla lista comandi ufficiale

### 📊 Fix Stato Casa — Temperature
- Fix: `/stato` mostrava solo 3 temperature
- Ora mostra tutte, filtrando automaticamente sensori CPU/sistema non utili all'utente

### 📊 Fix Stato Casa — Allarme
- Fix: `/stato` ignorava la configurazione `alarm_panel` e mostrava il primo trovato
- Ora usa sempre l'allarme configurato se presente

---

## [1.3.0] — precedente

### Fix
- Fix `notify_entity` vuoto che bloccava Telegram — campo ora opzionale
- Fix foto duplicate Frigate — cooldown anti-spam 60s per camera

### Funzionalità
- Integrazione Frigate NVR completa
- Snapshot automatici su allarme
- Tab Frigate nella pagina impostazioni web

---

## [1.2.0] — precedente

### Funzionalità
- Pagina Impostazioni web completa (5 tab: Persone, Sensori, Spazzatura, Energia, Frigate)
- Merge automatico campi avanzati quando si salva dalla pagina web

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

---

## [1.0.2] — precedente

### Sicurezza
- Codice allarme mai esposto all'AI né ai log
- Autenticazione pagina web
- Log senza dati personali

---

## [1.0.0] — release iniziale

- Gestione allarme automatica
- Rilevamento presenza con GPS e sensore prossimità
- Monitor elettrodomestici (modalità power e smart)
- Ottimizzatore solare surplus FV
- Analisi energetica giornaliera con AI
- Briefing mattutino
- Calendario spazzatura da PDF
- Controllo AI via Telegram in linguaggio naturale
- Fallback automatico tra provider AI (Gemini, Groq, Cerebras)
- Supporto italiano e inglese
