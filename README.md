<div align="center">

# 🧠 HomeMind Orchestrator

**L'agente AI che trasforma Home Assistant in una casa davvero intelligente**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![Language](https://img.shields.io/badge/Lingua-Italiano%20%2F%20English-green)]()
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Groq%20%7C%20Cerebras-orange)]()

</div>
<div align="center">
☕ Supporta il Progetto

**Se questo addon ti è utile, offrimi un caffè!**

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

**[paypal.me/ago19800](https://paypal.me/ago19800)**

*Ogni donazione mi aiuta a continuare a sviluppare e migliorare questo addon!* 🙏

</div>
<p align="center">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_100118_Telegram.jpg" width="260" alt="Foto 1">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_100210_Telegram.jpg" width="260" alt="Foto 2">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_100254_Telegram.jpg" width="260" alt="Foto 3">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_100347_Telegram.jpg" width="260" alt="Foto 4">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_103252_Telegram.jpg" width="260" alt="Foto 5">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_103806_Telegram.jpg" width="260" alt="Foto 6">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_110137_Telegram.jpg" width="260" alt="Foto 7">
</p>

---

## 📋 Indice
 
- [Cos'è HomeMind](#-cosè-homemind)
- [Installazione](#-installazione)
- [Configurazione Addon](#-configurazione-addon)
- [⚙️ Pagina Impostazioni Web](#️-pagina-impostazioni-web-novità-v120)
- [📁 Configurazione Avanzata via File](#-configurazione-avanzata-via-file)
- [Configurazione BASE](#-configurazione-base)
- [Configurazione MEDIA](#-configurazione-media)
- [Configurazione AVANZATA](#-configurazione-avanzata)
- [Moduli e funzionalità](#-moduli-e-funzionalità)
- [Comandi Telegram](#-comandi-telegram)
- [Interfaccia Vocale](#-interfaccia-vocale-telegram)
- [Sicurezza](#-sicurezza)
- [FAQ](#-faq--problemi-comuni)
 
---
 
## 🧠 Cos'è HomeMind
 
HomeMind è un **add-on per Home Assistant** che aggiunge un cervello AI alla tua casa. Non è una semplice automazione — è un agente che capisce il contesto, impara la tua routine e ti avvisa solo quando serve davvero.
 
**Parlagli su Telegram in italiano naturale:**
 
> *"Accendi la luce del salotto"*  
> *"Quanta energia ho prodotto oggi?"*  
> *"Arma l'allarme"*  
> *"Cosa succede in casa?"*
 
**Lui capisce, risponde e agisce.** Puoi anche mandargli un **messaggio vocale** 🎙️ — trascrive la voce e la tratta come un comando normale.
 
### Cosa fa in modo autonomo
 
| Funzione | Descrizione |
|----------|-------------|
| 🔒 **Allarme automatico** | Arma quando tutti escono, disarma quando torni |
| 👋 **Benvenuto a casa** | Ti accoglie con un messaggio quando rientri |
| ⚡ **Monitor elettrodomestici** | Ti avvisa quando lavatrice/lavastoviglie finiscono |
| ☀️ **Ottimizzatore solare** | Ti suggerisce quando avviare elettrodomestici col surplus FV |
| 📊 **Analisi energia** | Ogni mattina ti dice se hai consumato più o meno del solito |
| 🌅 **Briefing mattutino** | Alle 7:00 ti manda meteo, energia, spazzatura e un consiglio AI |
| 🗑️ **Spazzatura** | La sera prima ti ricorda cosa mettere fuori |
| 🚨 **Allarme intrusione** | Rilevamento movimento con allarme armato |
 
---
 
## 🚀 Installazione
 
### 1. Aggiungi il repository
 
```
Impostazioni → Add-on Store → ⋮ → Repositories
→ https://github.com/ago19800/HomeMind → Aggiungi
```
 
### 2. Installa l'addon
 
Cerca **HomeMind Orchestrator** nello store e clicca **Installa**.
 
### 3. Configura e avvia
 
1. Clicca su **HomeMind Orchestrator** per aprire la pagina dell'addon
2. Clicca sulla scheda **Configurazione** (in alto, accanto a Info e Log)
3. Inserisci almeno il token Telegram e il chat ID
4. Clicca **Salva**
5. Torna alla scheda **Info** e clicca **Avvia**
 
```
HomeMind Orchestrator
├── 📋 Info          ← clicca Avvia qui
├── ⚙️ Configurazione ← inserisci le chiavi qui
├── 📄 Log           ← controlla gli errori qui
└── 🔧 Rete
```
 
---
 
## ⚙️ Configurazione Addon
 
Questi campi si trovano nella scheda **Configurazione** dell'addon in Home Assistant.
 
### Telegram (obbligatorio)
 
```yaml
telegram_bot_token: "TOKEN_DA_BOTFATHER"
telegram_chat_id: "IL_TUO_CHAT_ID_NUMERICO"
```
 
> **Token bot:** cerca @BotFather su Telegram → `/newbot`  
> **Chat ID:** cerca @userinfobot su Telegram → manda `/start` → copia il numero
 
### Codice Allarme
 
```yaml
alarm_code: "1234"
```
 
> Il codice viene usato solo per armare/disarmare — non viene mai mostrato nei log o all'AI.
 
### Provider AI
 
Inserisci almeno **Gemini + Groq** per avere un sistema con fallback automatico. HomeMind prova i provider nell'ordine configurato e passa al successivo se uno fallisce.
 
```yaml
gemini_api_key: "AIzaSy..."          # 🟦 Google Gemini — GRATIS 1.500 req/giorno
gemini_model: "gemini-2.0-flash"
 
groq_api_key: "gsk_..."              # ⚡ Groq — GRATIS 14.400 req/giorno
groq_model: "llama-3.3-70b-versatile"
 
cerebras_api_key: "csk_..."          # 🧠 Cerebras — GRATIS 1M token/min
cerebras_model: "llama3.1-8b"
 
deepseek_api_key: "sk-..."           # 🔵 DeepSeek — quasi gratis
deepseek_model: "deepseek-chat"
 
openai_api_key: "sk-..."             # 🟢 OpenAI — per Whisper vocale
openai_model: "gpt-4o-mini"
 
ai_provider_order: "gemini,groq,cerebras,deepseek,claude,openai"
```
 
> Lascia vuoto qualsiasi campo per disabilitare quel provider.
 
### Provider AI — quale scegliere?
 
| Provider | Costo | Limite gratuito | Link |
|----------|-------|----------------|------|
| 🟦 **Google Gemini** | Gratis | 1.500 req/giorno | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ **Groq** | Gratis | 100.000 token/giorno | [console.groq.com](https://console.groq.com) |
| 🧠 **Cerebras** | Gratis | 1M token/min | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 **DeepSeek** | ~Gratis | $0.014/1M token | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟢 **OpenAI** | A pagamento | $0.006/min audio | [platform.openai.com](https://platform.openai.com) |
 
### Notifiche Spazzatura (override opzionale)
 
Questi campi possono essere lasciati vuoti — la spazzatura si configura più comodamente dalla **pagina Impostazioni web**.
 
```yaml
spazzatura_notify_enabled: true
spazzatura_notify_hour: "20"
```
 
---
 
## ⚙️ Pagina Impostazioni Web (Novità v1.2.0)
 
Dalla versione 1.2.0 puoi configurare HomeMind direttamente dall'interfaccia web **senza modificare nessun file**.
 
### Come accedere
 
Apri l'addon HomeMind dal pannello HA → clicca il pulsante **⚙️** nella barra in alto.
 
### Cosa puoi configurare dalla UI
 
La pagina è divisa in 4 tab:
 
**👤 Persone**
- Seleziona le persone da monitorare (whitelist) con un semplice spunto
- Seleziona le persone da escludere (blacklist) — es. bot MQTT, device tracker falsi
- Ogni persona mostra nome, entity_id e stato attuale (home / not_home)
 
**🚶 Sensori**
- Seleziona i sensori di movimento da monitorare (whitelist)
- Esclude automaticamente quelli non disponibili
- Separa i sensori da ignorare (blacklist) — es. sensore del telefono
- Sezione porte/finestre da escludere dal monitoraggio (contact blacklist)
 
> **Nota:** HomeMind monitora **tutte** le porte e finestre automaticamente. La sezione "Porte/finestre" serve solo per **escludere** quelle che vuoi ignorare (es. garage sempre aperto).
 
**🗑️ Spazzatura**
- Toggle on/off notifiche con un interruttore
- Campo orario notifica (0-23)
- Le modifiche si applicano **immediatamente** senza riavviare l'addon
 
**⚡ Energia**
- Selezione sensori fotovoltaico, consumo casa, rete Enel
- Usa radio button — selezione singola per categoria
 
### Come funziona il salvataggio
 
Quando clicchi **💾 Salva impostazioni**:
- I campi base vengono aggiornati nel file `person_config.json`
- I campi avanzati (`proximity_sensors`, `solar_optimizer`, `appliances`, `location_tracker`) vengono **preservati automaticamente** — non vengono mai cancellati
- Le impostazioni spazzatura si applicano subito
- Le altre impostazioni (persone, sensori) si applicano al prossimo riavvio
 
---
 
## 📁 Configurazione Avanzata via File
 
Per le funzioni avanzate — GPS preciso, ottimizzatore solare, elettrodomestici dettagliati — devi modificare direttamente il file:
 
```
/config/homemind_patches/person_config.json
```
 
**Come aprirlo:** in HA usa l'addon **File Editor** o **Studio Code Server**.
 
> Le modifiche dalla pagina web **non cancellano** i campi avanzati che hai impostato nel file — il merge è automatico.
 
### Come trovare gli entity_id
 
```
Home Assistant → Strumenti Sviluppatore → Stati
→ cerca il nome del dispositivo
```
 
L'entity_id è il codice tipo `sensor.temperatura_soggiorno` o `binary_sensor.porta_ingresso_contact`.
 
---
 
## 🟢 Configurazione BASE
 
La configurazione minima per avere HomeMind funzionante: presenza, allarme e AI via Telegram.
 
```json
{
  "language": "it",
 
  "person_whitelist": [
    "person.mario",
    "person.lucia"
  ],
 
  "person_blacklist": [],
 
  "motion_whitelist": [
    "binary_sensor.sensore_movimento_ingresso",
    "binary_sensor.sensore_movimento_soggiorno"
  ],
 
  "motion_blacklist": []
}
```
 
**Con questa configurazione:**
- ✅ HomeMind parla italiano
- ✅ Monitora presenza di Mario e Lucia
- ✅ Allarme automatico (arma/disarma)
- ✅ Rilevamento intrusione con movimento
- ✅ Controllo AI via Telegram
- ✅ Briefing mattutino alle 7:00
 
---
 
## 🟡 Configurazione MEDIA
 
Aggiunge GPS preciso, sensori contatto, elettrodomestici e analisi energetica.
 
```json
{
  "language": "it",
 
  "person_whitelist": [
    "person.mario",
    "person.lucia"
  ],
 
  "person_blacklist": [
    "person.mqtt_finto"
  ],
 
  "motion_whitelist": [
    "binary_sensor.sensore_ingresso_occupancy",
    "binary_sensor.sensore_soggiorno_occupancy",
    "binary_sensor.sensore_cucina_occupancy"
  ],
 
  "motion_blacklist": [
    "binary_sensor.telefono_mario_motion",
    "binary_sensor.sensore_test"
  ],
 
  "contact_blacklist": [
    "binary_sensor.porta_garage_contact"
  ],
 
  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.casa_telefono_mario_distance",
      "threshold_m": 100,
      "stale_check": false
    }
  },
 
  "energy_sensors": {
    "produzione_fv":  "sensor.fv_tot",
    "consumo_casa":   "sensor.consumi_giornalieri",
    "rete_enel":      "sensor.enel_giornaliero",
    "batteria_wh":    "sensor.batteria_wh"
  },
 
  "appliances": {
    "lavatrice": {
      "enabled": true,
      "name": "Lavatrice",
      "icon": "🫧",
      "mode": "power",
      "power_sensor": "sensor.presa_lavatrice_power",
      "power_on_threshold": 50,
      "power_off_threshold": 10,
      "min_cycle_minutes": 20,
      "max_idle_minutes": 5,
      "notify_on_start": false
    },
    "lavastoviglie": {
      "enabled": true,
      "name": "Lavastoviglie",
      "icon": "🍽️",
      "mode": "smart",
      "state_sensor": "sensor.lavastoviglie_operation_state",
      "running_states": ["Run"],
      "done_states": ["Finished", "Ready"],
      "notify_on_start": false
    }
  }
}
```
 
---
 
## 🔴 Configurazione AVANZATA
 
Aggiunge ottimizzatore solare, sensori W istantanei, più elettrodomestici.
 
```json
{
  "language": "it",
 
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.mqtt_finto"],
 
  "motion_whitelist": [
    "binary_sensor.sensore_ingresso_occupancy",
    "binary_sensor.sensore_soggiorno_occupancy"
  ],
  "motion_blacklist": [
    "binary_sensor.telefono_mario_motion"
  ],
  "contact_blacklist": [
    "binary_sensor.porta_garage_contact"
  ],
 
  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.casa_telefono_mario_distance",
      "threshold_m": 100,
      "stale_check": false
    }
  },
 
  "energy_sensors": {
    "produzione_fv":   "sensor.fv_tot",
    "consumo_casa":    "sensor.consumi_giornalieri",
    "rete_enel":       "sensor.enel_giornaliero",
    "batteria_wh":     "sensor.batteria_wh",
    "produzione_fv_w": "sensor.fotovoltaica_totale_w",
    "consumo_casa_w":  "sensor.inverter_ac_output_power",
    "rete_enel_w":     "sensor.shelly_channel_1_power"
  },
 
  "appliances": {
    "lavatrice": {
      "enabled": true,
      "name": "Lavatrice",
      "icon": "🫧",
      "mode": "power",
      "power_sensor": "sensor.presa_lavatrice_power",
      "power_on_threshold": 50,
      "power_off_threshold": 10,
      "min_cycle_minutes": 20,
      "max_idle_minutes": 5,
      "notify_on_start": false
    },
    "lavastoviglie": {
      "enabled": true,
      "name": "Lavastoviglie",
      "icon": "🍽️",
      "mode": "smart",
      "state_sensor": "sensor.lavastoviglie_operation_state",
      "running_states": ["Run"],
      "done_states": ["Finished", "Ready"],
      "notify_on_start": false
    },
    "asciugatrice": {
      "enabled": true,
      "name": "Asciugatrice",
      "icon": "🌀",
      "mode": "power",
      "power_sensor": "sensor.presa_asciugatrice_power",
      "power_on_threshold": 100,
      "power_off_threshold": 15,
      "min_cycle_minutes": 25,
      "max_idle_minutes": 8,
      "notify_on_start": false
    }
  },
 
  "solar_optimizer": {
    "enabled": true,
    "min_surplus_w": 500,
    "confirm_minutes": 5,
    "cooldown_hours": 2,
    "appliances": {
      "lavatrice": {
        "enabled": true,
        "switch": "switch.presa_lavatrice",
        "min_surplus_w": 800,
        "auto_start": false
      },
      "lavastoviglie": {
        "enabled": true,
        "switch": null,
        "min_surplus_w": 500,
        "auto_start": false
      }
    },
    "battery_soc_sensor": "sensor.batteria_percentuale",
    "battery_full_threshold": 95,
    "battery_full_min_fv_w": 300,
    "min_sun_elevation": 10
  },
 
  "location_tracker": {
    "mario": "device_tracker.telefono_mario",
    "lucia": "sensor.telefono_lucia_geocoded_location"
  },
 
  "spazzatura_notify_enabled": true,
  "spazzatura_notify_hour": 20
}
```
 
---
 
## 📦 Moduli e funzionalità
 
### 🔒 Sicurezza & Allarme
 
HomeMind gestisce l'allarme automaticamente in base alla presenza.
 
**Armo automatico:**
```
Tutti escono → attesa 30 secondi → allarme armato
```
 
**Disarmo automatico:**
```
Qualcuno si avvicina → HomeMind rileva → disarma prima che entri
```
 
**Intrusione:**
```
Allarme armato + movimento → notifica immediata su Telegram
```
 
Il codice allarme viene usato solo internamente — non viene mai mostrato nei log o all'AI.
 
---
 
### 👤 Presenza & Prossimità GPS
 
HomeMind usa due livelli di rilevamento:
 
**Livello 1** — GPS nativo HA: `person.mario` = home / not_home  
**Livello 2** — Sensore distanza (opzionale): distanza precisa in metri
 
Con il sensore distanza configurato, **la distanza vince sempre sul GPS**. Questo risolve il problema classico del GPS che "salta" e arma l'allarme mentre sei ancora in casa.
 
```
Sensore dice 45m   → sei a casa (anche se GPS dice "not_home")
Sensore dice 1200m → sei fuori (anche se GPS dice "home")
```
 
**Parametri `proximity_sensors`:**
 
| Campo | Descrizione |
|-------|-------------|
| `sensor` | Entity ID del sensore distanza (in metri) |
| `threshold_m` | Distanza soglia "a casa" in metri (default: 100) |
| `stale_check` | `true` = dopo 5 min senza aggiornamento torna al GPS; `false` = usa sempre l'ultimo valore anche se vecchio |
 
> Usa `stale_check: false` se il GPS del telefono si aggiorna di rado.
 
---
 
### ⚡ Monitor Elettrodomestici
 
HomeMind sa quando gli elettrodomestici partono e finiscono.
 
**Notifica fine ciclo:**
```
🫧 Lavatrice terminata! Ciclo durato 1h 23min.
```
 
**Modalità POWER** — per prese smart con misura potenza:
```json
"mode": "power",
"power_sensor": "sensor.presa_lavatrice_power",
"power_on_threshold": 50,
"power_off_threshold": 10,
"min_cycle_minutes": 20,
"max_idle_minutes": 5
```
 
**Modalità SMART** — per elettrodomestici connessi (Bosch Home Connect, ecc.):
```json
"mode": "smart",
"state_sensor": "sensor.lavastoviglie_operation_state",
"running_states": ["Run"],
"done_states": ["Finished", "Ready"]
```
 
`notify_on_start: true` → notifica anche all'avvio (default: false)
 
---
 
### ☀️ Ottimizzatore Solare
 
Monitora il surplus fotovoltaico ogni 2 minuti e ti avvisa quando è il momento migliore per avviare gli elettrodomestici pesanti.
 
**Come funziona:**
```
Ogni 2 minuti: produzione FV - consumo casa = surplus
 
Se surplus ≥ soglia per X minuti consecutivi
  → Notifica Telegram
 
Rispondi "sì" → HomeMind accende la presa
           oppure auto_start: true → parte da solo
```
 
**Parametri `solar_optimizer`:**
 
| Campo | Descrizione |
|-------|-------------|
| `enabled` | Attiva/disattiva |
| `min_surplus_w` | Surplus minimo in Watt per attivarsi |
| `confirm_minutes` | Minuti di surplus stabile prima di notificare |
| `cooldown_hours` | Ore minime tra una notifica e l'altra |
| `battery_full_threshold` | % batteria sopra cui si considera "piena" |
| `min_sun_elevation` | Elevazione solare minima (evita falsi trigger all'alba) |
 
**Parametri per singolo elettrodomestico:**
 
| Campo | Descrizione |
|-------|-------------|
| `switch` | Entity ID presa da accendere (null = solo notifica) |
| `min_surplus_w` | Soglia surplus specifica per questo elettrodomestico |
| `auto_start` | `true` = parte da solo, `false` = chiede conferma |
 
> **Sensori W istantanei (raccomandati):** aggiungi `produzione_fv_w`, `consumo_casa_w`, `rete_enel_w` in `energy_sensors` per un calcolo del surplus preciso al watt.
 
---
 
### 📊 Analisi Energetica
 
Ogni mattina alle 7:15 confronta i consumi di ieri con la media degli ultimi 30 giorni e ti segnala anomalie.
 
```
energy_sensors:
  produzione_fv:  sensore kWh produzione giornaliera
  consumo_casa:   sensore kWh consumo giornaliero
  rete_enel:      sensore kWh prelievo rete giornaliero
  batteria_wh:    sensore capacità batteria (%)
```
 
---
 
### 🌅 Briefing Mattutino
 
Ogni giorno alle **7:00** ricevi su Telegram:
- Meteo del giorno
- Produzione FV e consumi di ieri
- Raccolta rifiuti del giorno
- Consiglio AI personalizzato
 
Scrivi `/briefing` per riceverlo subito in qualsiasi momento.
 
---
 
### 🗑️ Calendario Spazzatura
 
HomeMind ti avvisa ogni sera prima della raccolta. L'orario si configura dalla **pagina Impostazioni ⚙️** direttamente — nessun riavvio necessario.
 
**Per attivarlo:**
1. Carica il PDF del calendario in `/config/homemind_patches/spazzatura.pdf`
2. Scrivi `/ricarica_spazzatura` su Telegram
3. HomeMind legge il PDF con AI e crea il calendario automaticamente
 
**Parametri notifica** (configurabili anche dalla UI web):
 
| Campo | Descrizione |
|-------|-------------|
| `spazzatura_notify_enabled` | `true` / `false` |
| `spazzatura_notify_hour` | Ora della notifica (0-23, default: 20) |
 
---
 
## 🎙️ Interfaccia Vocale Telegram
 
Manda un **messaggio vocale** al bot Telegram — HomeMind lo trascrive e lo tratta come un comando normale.
 
```
Tu parli → Whisper (OpenAI) trascrive → AI elabora → azione eseguita
```
 
**Attivazione:** inserisci `openai_api_key` nella configurazione addon.
 
**Costi Whisper:**
 
| Durata vocale | Costo |
|---------------|-------|
| ~3 secondi | $0.0003 |
| ~5 secondi | $0.0005 |
| ~15 secondi | $0.0015 |
 
Con $5 di crediti OpenAI hai circa 10.000 comandi vocali da 5 secondi.
 
> La **risposta AI** dopo la trascrizione usa sempre Gemini/Groq (gratuiti). OpenAI viene usato solo per la trascrizione audio.
 
---
 
## 🔐 Sicurezza
 
HomeMind implementa le seguenti protezioni:
 
**Codice allarme protetto** — il codice non viene mai passato al prompt AI. Viene usato solo internamente al momento dell'azione.
 
**Autenticazione Web UI** — la porta `8099` (accesso diretto) richiede il Supervisor Token di HA. Le richieste tramite Ingress di HA passano automaticamente.
 
**Log senza dati personali** — i messaggi Telegram vengono loggati solo come `[N chars]` senza contenuto né username.
 
**YAML parsing sicuro** — le automazioni vengono parsate con PyYAML con fallback controllato.
 
---
 
## 📱 Comandi Telegram
 
| Comando | Descrizione |
|---------|-------------|
| `/stato` | Stato completo: persone, sensori, allarme |
| `/briefing` | Ricevi subito il briefing mattutino |
| `/energia` | Produzione FV e consumi di oggi |
| `/ieri` | Produzione e consumi di ieri |
| `/solare` | Surplus FV e ottimizzatore |
| `/elettrodomestici` | Stato lavatrice, lavastoviglie ecc. |
| `/spazzatura` | Raccolta prossimi 7 giorni |
| `/ricarica_spazzatura` | Rileggi PDF calendario |
| `/aggiornamenti` | Controlla aggiornamenti HA disponibili |
| `/riparazioni` | Problemi segnalati da HA |
| `/providers` | Provider AI attivi |
| `/lingua it` | Passa all'italiano |
| `/lingua en` | Switch to English |
| `/comandi` | Questa lista |
 
Oppure scrivi qualsiasi cosa in italiano naturale — non servono comandi precisi.
 
---
 
## ❓ FAQ & Problemi comuni
 
**L'allarme si arma mentre sono ancora in casa**  
→ Aggiungi il sensore GPS in `proximity_sensors`. Con il sensore distanza HomeMind sa esattamente dove sei.
 
**HomeMind mi considera assente anche se sono in casa**  
→ Controlla che la tua entità `person.nome` sia nella `person_whitelist`. Verifica in HA che lo stato sia "home".
 
**Il sensore del telefono fa scattare l'allarme**  
→ Aggiungi `binary_sensor.nomeTelefono_motion` nella `motion_blacklist`.
 
**Non ricevo notifiche Telegram**  
→ Verifica che `telegram_chat_id` nella configurazione sia un numero (es. `360307101`), non il tuo username. Usa @userinfobot per trovarlo.
 
**Il briefing non arriva**  
→ Verifica nei log che il bot sia connesso: cerca `Telegram bot connesso`. Scrivi `/briefing` per testarlo manualmente.
 
**La lavatrice notifica troppo presto**  
→ Aumenta `min_cycle_minutes`. Se notifica prima della fine reale, aumenta `max_idle_minutes`.
 
**Il surplus solare non supera mai la soglia**  
→ Abbassa `min_surplus_w`. Con pannelli da 3kW una soglia realistica è 300-400W nelle giornate nuvolose.
 
**La pagina Impostazioni non mostra le entità**  
→ Apri la pagina qualche secondo dopo l'avvio dell'addon, quando il log mostra `HomeMind ready — XXXX entita`.
 
**Salvo dalla pagina web ma i campi avanzati spariscono**  
→ Aggiorna alla v1.2.0 — il merge automatico è incluso da quella versione.
 
**Errore `SyntaxError` quando salvo**  
→ Aggiorna alla v1.1.8 o successiva — il problema del BOM UTF-8 è risolto.
 
---
 
## 📝 Changelog
 
**v1.2.0** — Merge automatico: la pagina web preserva i campi avanzati del file JSON  
**v1.1.x** — Pagina Impostazioni web completa con selezione entità da HA  
**v1.0.5** — Fix pulsante Test provider AI  
**v1.0.4** — Interfaccia vocale Telegram (Whisper)  
**v1.0.2** — Fix sicurezza: alarm code, autenticazione web, log PII  
**v1.0.1** — Fix avvio addon, cartelle automatiche, upload calendario  
**v1.0.0** — Release iniziale
 
---
 
**HomeMind Orchestrator** — *La tua casa, finalmente intelligente.*
 
[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)
 
**[paypal.me/ago19800](https://paypal.me/ago19800)**
