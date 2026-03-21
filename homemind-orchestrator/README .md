# 🧠 HomeMind Orchestrator

**L'agente AI che trasforma Home Assistant in una casa davvero intelligente**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![Language](https://img.shields.io/badge/Lingua-Italiano%20%2F%20English-green)]()
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Groq%20%7C%20Cerebras-orange)]()
[![Version](https://img.shields.io/badge/versione-1.3.0-brightgreen)]()

<div align="center">
☕ Supporta il Progetto

**Se questo addon ti è utile, offrimi un caffè!**

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

**[paypal.me/ago19800](https://paypal.me/ago19800)**

*Ogni donazione mi aiuta a continuare a sviluppare e migliorare questo addon!* 🙏
</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_100118_Telegram.jpg" width="260">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_100210_Telegram.jpg" width="260">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_100254_Telegram.jpg" width="260">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_100347_Telegram.jpg" width="260">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_103252_Telegram.jpg" width="260">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_103806_Telegram.jpg" width="260">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260316_110137_Telegram.jpg" width="260">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260319_123749_Home Assistant.jpg" width="260">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260319_123738_Home Assistant.jpg" width="260">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260319_123729_Home Assistant.jpg" width="260">
</p>

---

## 📋 Indice

- [Cos'è HomeMind](#-cosè-homemind)
- [Installazione](#-installazione)
- [Configurazione Addon](#configurazione-addon)
- [Pagina Impostazioni Web](#pagina-impostazioni-web)
- [Configurazione Avanzata via File](#configurazione-avanzata-via-file)
- [Configurazione BASE](#configurazione-base)
- [Configurazione MEDIA](#configurazione-media)
- [Configurazione AVANZATA](#configurazione-avanzata)
- [Moduli e funzionalità](#moduli-e-funzionalità)
- [Telecamere Frigate](#telecamere-frigate)
- [Comandi Telegram](#comandi-telegram)
- [Interfaccia Vocale](#interfaccia-vocale-telegram)
- [Sicurezza](#sicurezza)
- [FAQ](#faq-e-problemi-comuni)

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
| 📷 **Snapshot telecamere** | Foto automatica su Telegram quando scatta l'allarme |
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

## Configurazione Addon

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

Inserisci almeno **Gemini + Groq** per avere un sistema con fallback automatico.

```yaml
gemini_api_key: "AIzaSy..."          # 🟦 Google Gemini — GRATIS 1.500 req/giorno
gemini_model: "gemini-2.0-flash"

groq_api_key: "gsk_..."              # ⚡ Groq — GRATIS 100.000 token/giorno
groq_model: "llama-3.3-70b-versatile"

cerebras_api_key: "csk_..."          # 🧠 Cerebras — GRATIS 1M token/min
cerebras_model: "llama3.1-8b"

openai_api_key: "sk-..."             # 🟢 OpenAI — solo per messaggi vocali
openai_model: "gpt-4o-mini"

ai_provider_order: "gemini,groq,cerebras,deepseek,claude,openai"
```

| Provider | Costo | Limite | Link |
|----------|-------|--------|------|
| 🟦 **Google Gemini** | Gratis | 1.500 req/giorno | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ **Groq** | Gratis | 100.000 token/giorno | [console.groq.com](https://console.groq.com) |
| 🧠 **Cerebras** | Gratis | 1M token/min | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 **DeepSeek** | ~Gratis | $0.014/1M token | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟢 **OpenAI** | A pagamento | $0.006/min audio | [platform.openai.com](https://platform.openai.com) |

---

## Pagina Impostazioni Web

Dalla versione 1.2.0 puoi configurare HomeMind direttamente dall'interfaccia web **senza modificare nessun file**.

### Come accedere

Apri l'addon HomeMind dal pannello HA → clicca il pulsante **⚙️** nella barra in alto.

La pagina è divisa in 5 tab:

**👤 Persone** — seleziona chi monitorare e chi escludere con un semplice click

**🚶 Sensori** — sensori di movimento da usare o ignorare, porte/finestre da escludere

**🗑️ Spazzatura** — toggle on/off e orario notifica, si applicano subito senza riavvio

**⚡ Energia** — seleziona i sensori per fotovoltaico, consumo e rete

**📹 Frigate** — configura le telecamere per gli snapshot automatici (vedi sezione dedicata)

> Quando salvi, i campi avanzati (`proximity_sensors`, `solar_optimizer`, `appliances` ecc.) vengono **preservati automaticamente** — non vengono mai cancellati.

---

## Configurazione Avanzata via File

Per GPS preciso, ottimizzatore solare ed elettrodomestici dettagliati, modifica il file:

```
/config/homemind_patches/person_config.json
```

Usa l'addon **File Editor** o **Studio Code Server** in HA per aprirlo.

---

## Configurazione BASE

```json
{
  "language": "it",
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": [],
  "motion_whitelist": [
    "binary_sensor.sensore_ingresso",
    "binary_sensor.sensore_soggiorno"
  ],
  "motion_blacklist": []
}
```

---

## Configurazione MEDIA

```json
{
  "language": "it",
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.mqtt_finto"],
  "motion_whitelist": [
    "binary_sensor.sensore_ingresso_occupancy",
    "binary_sensor.sensore_soggiorno_occupancy"
  ],
  "motion_blacklist": ["binary_sensor.telefono_mario_motion"],
  "contact_blacklist": ["binary_sensor.porta_garage_contact"],
  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.casa_telefono_mario_distance",
      "threshold_m": 100,
      "stale_check": false
    }
  },
  "energy_sensors": {
    "produzione_fv": "sensor.fv_tot",
    "consumo_casa":  "sensor.consumi_giornalieri",
    "rete_enel":     "sensor.enel_giornaliero"
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
    }
  }
}
```

---

## Configurazione AVANZATA

```json
{
  "language": "it",
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.mqtt_finto"],
  "motion_whitelist": ["binary_sensor.sensore_ingresso_occupancy"],
  "motion_blacklist": ["binary_sensor.telefono_mario_motion"],
  "contact_blacklist": ["binary_sensor.porta_garage_contact"],
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
    "produzione_fv_w": "sensor.fotovoltaica_totale_w",
    "consumo_casa_w":  "sensor.inverter_ac_output_power",
    "rete_enel_w":     "sensor.shelly_channel_1_power"
  },
  "appliances": {
    "lavatrice": {
      "enabled": true, "name": "Lavatrice", "icon": "🫧", "mode": "power",
      "power_sensor": "sensor.presa_lavatrice_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5, "notify_on_start": false
    },
    "lavastoviglie": {
      "enabled": true, "name": "Lavastoviglie", "icon": "🍽️", "mode": "smart",
      "state_sensor": "sensor.lavastoviglie_operation_state",
      "running_states": ["Run"], "done_states": ["Finished", "Ready"],
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
      }
    },
    "battery_soc_sensor": "sensor.batteria_percentuale",
    "battery_full_threshold": 95,
    "min_sun_elevation": 10
  },
  "location_tracker": {
    "mario": "device_tracker.telefono_mario"
  },
  "frigate": {
    "enabled": true,
    "host": "192.168.1.100",
    "port": 5000,
    "snapshot_on_alarm": true,
    "cameras": {
      "ingresso": "binary_sensor.sensore_ingresso_occupancy",
      "garage":   "binary_sensor.sensore_garage_occupancy"
    }
  }
}
```

---

## Moduli e funzionalità

### 🔒 Sicurezza & Allarme

HomeMind gestisce l'allarme automaticamente in base alla presenza.

```
Tutti escono → attesa 30s → allarme armato
Qualcuno si avvicina → HomeMind rileva → disarma prima che entri
Allarme armato + movimento → notifica Telegram + foto telecamera
```

### 👤 Presenza & Prossimità GPS

Con il sensore distanza configurato, la distanza vince sempre sul GPS — risolve il problema del GPS che "salta" e arma l'allarme mentre sei ancora in casa.

| Campo | Descrizione |
|-------|-------------|
| `sensor` | Entity ID del sensore distanza in metri |
| `threshold_m` | Distanza soglia "a casa" (default: 100m) |
| `stale_check` | `false` = usa sempre l'ultimo valore anche se vecchio |

### ⚡ Monitor Elettrodomestici

**Modalità POWER** — presa smart con misura potenza (Zigbee, Shelly):
```json
"mode": "power",
"power_sensor": "sensor.presa_lavatrice_power",
"power_on_threshold": 50,
"power_off_threshold": 10
```

**Modalità SMART** — elettrodomestici connessi (Bosch Home Connect ecc.):
```json
"mode": "smart",
"state_sensor": "sensor.lavastoviglie_operation_state",
"running_states": ["Run"],
"done_states": ["Finished", "Ready"]
```

### ☀️ Ottimizzatore Solare

Monitora il surplus FV ogni 2 minuti. Quando c'è abbastanza surplus ti avvisa su Telegram — rispondi "sì" per avviare l'elettrodomestico, oppure imposta `auto_start: true` per partenza automatica.

### 🌅 Briefing Mattutino

Ogni giorno alle **7:00**: meteo, energia di ieri, raccolta rifiuti, consiglio AI. Scrivi `/briefing` per riceverlo subito.

### 🗑️ Calendario Spazzatura

Carica il PDF del calendario in `/config/homemind_patches/spazzatura.pdf`, poi scrivi `/ricarica_spazzatura` su Telegram. HomeMind lo legge con AI e crea il calendario automaticamente.

---

## Telecamere Frigate

HomeMind si integra con **Frigate NVR** per mandare uno snapshot su Telegram ogni volta che scatta l'allarme. Funziona anche se Frigate è installato su un **PC diverso** nella stessa rete — basta che siano connessi allo stesso router.

### Come funziona

```
Sensore movimento rileva intruso
        ↓
HomeMind chiama Frigate via rete locale
        ↓
Frigate risponde con la foto della camera
        ↓
📷 Foto arriva su Telegram in pochi secondi
```

La foto viene presa dalla RAM di Frigate — **nessun video salvato su disco** per questa funzione.

### Configurazione dalla pagina web

1. Apri **Impostazioni ⚙️** → tab **📹 Frigate**
2. Attiva il toggle **Abilita Frigate**
3. Inserisci l'**IP** del PC dove gira Frigate (es. `192.168.1.100`) e la **porta** (default `5000`)
4. Clicca **+ Aggiungi camera** per ogni telecamera
5. Inserisci il **nome della camera** come appare in Frigate (es. `ingresso`)
6. Seleziona dal menù il **sensore movimento** corrispondente
7. Clicca **💾 Salva** — riavvia l'addon

### Configurazione via file JSON

```json
"frigate": {
  "enabled": true,
  "host": "192.168.1.100",
  "port": 5000,
  "snapshot_on_alarm": true,
  "cameras": {
    "ingresso": "binary_sensor.sensore_ingresso_occupancy",
    "garage":   "binary_sensor.sensore_garage_occupancy",
    "giardino": "binary_sensor.sensore_giardino_occupancy"
  }
}
```

**Dove trovo il nome della camera?** Apri Frigate nel browser (`http://IP:5000`) — il nome è quello che appare sopra ogni video.

**Cosa succede se un sensore non ha una camera associata?** HomeMind manda automaticamente le foto di tutte le camere configurate.

**Cooldown anti-spam:** la stessa camera non manda più di uno snapshot ogni 60 secondi, anche se più sensori scattano in rapida successione.

---

## Comandi Telegram

| Comando | Descrizione |
|---------|-------------|
| `/stato` | Stato completo: persone, sensori, allarme |
| `/briefing` | Ricevi subito il briefing mattutino |
| `/energia` | Produzione FV e consumi di oggi |
| `/ieri` | Produzione e consumi di ieri |
| `/solare` | Surplus FV e ottimizzatore |
| `/elettrodomestici` | Stato lavatrice, lavastoviglie ecc. |
| `/lavatrice` | Stato rapido lavatrice |
| `/lavastoviglie` | Stato rapido lavastoviglie |
| `/spazzatura` | Raccolta prossimi 7 giorni |
| `/ricarica_spazzatura` | Rileggi PDF calendario |
| `/aggiornamenti` | Controlla aggiornamenti HA |
| `/riparazioni` | Problemi segnalati da HA |
| `/providers` | Provider AI attivi |
| `/lingua it` | Passa all'italiano |
| `/lingua en` | Switch to English |
| `/comandi` | Questa lista |

---

## Interfaccia Vocale Telegram

Manda un **messaggio vocale** — HomeMind lo trascrive con Whisper e lo tratta come un comando normale.

**Attivazione:** inserisci `openai_api_key` nella configurazione addon.

| Durata vocale | Costo |
|---------------|-------|
| ~3 secondi | $0.0003 |
| ~5 secondi | $0.0005 |

Con $5 di crediti OpenAI hai circa 10.000 comandi vocali. La risposta AI usa sempre Gemini/Groq gratuiti.

---

## Sicurezza

- **Codice allarme protetto** — mai esposto all'AI né ai log
- **Log senza dati personali** — messaggi Telegram loggati solo come `[N chars]`
- **YAML parsing sicuro** — con PyYAML e fallback controllato

---

## FAQ e Problemi comuni

**L'allarme si arma mentre sono ancora in casa**  
→ Aggiungi il sensore GPS in `proximity_sensors`.

**Non ricevo notifiche Telegram**  
→ Verifica che `telegram_chat_id` sia un numero (usa @userinfobot). Lascia **vuoto** il campo `notify_entity` nelle Opzioni addon.

**Il campo `notify_entity` diventa rosso obbligatorio**  
→ Aggiorna alla v1.3.0 — il campo è ora opzionale. Nel frattempo lascialo vuoto o scrivi `placeholder`.

**Il briefing non arriva**  
→ Scrivi `/briefing` per testarlo. Verifica nei log che il provider AI sia configurato.

**Frigate non si connette**  
→ Verifica che l'IP e la porta siano corretti e che Frigate sia raggiungibile dalla rete (`http://IP:5000`).

**Ricevo foto duplicate di Telegram**  
→ Aggiorna alla v1.3.0 — il cooldown anti-duplicati è incluso.

**La pagina Impostazioni non mostra le entità**  
→ Aprila qualche secondo dopo l'avvio, quando il log mostra `HomeMind ready`.

**Salvo dalla pagina web ma i campi avanzati spariscono**  
→ Aggiorna alla v1.2.0 — il merge automatico è incluso.

---

## Changelog

**v1.3.0** — Fix `notify_entity` vuoto che bloccava Telegram, campo ora opzionale, fix foto duplicate Frigate  
**v1.2.x** — Integrazione Frigate NVR, snapshot automatici su allarme, tab 📹 nella pagina impostazioni  
**v1.2.0** — Pagina Impostazioni web completa, merge automatico campi avanzati  
**v1.1.x** — Fix tab navigazione, fix BOM UTF-8, dashboard live  
**v1.0.4** — Interfaccia vocale Telegram (Whisper)  
**v1.0.2** — Fix sicurezza: alarm code, autenticazione web, log PII  
**v1.0.0** — Release iniziale

---

**HomeMind Orchestrator** — *La tua casa, finalmente intelligente.*

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

**[paypal.me/ago19800](https://paypal.me/ago19800)**
