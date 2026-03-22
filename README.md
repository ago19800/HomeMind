# 🧠 HomeMind Orchestrator

**L'agente AI che trasforma Home Assistant in una casa davvero intelligente**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![Language](https://img.shields.io/badge/Lingua-Italiano%20%2F%20English-green)]()
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Groq%20%7C%20Cerebras-orange)]()
[![Version](https://img.shields.io/badge/versione-1.5.0-brightgreen)](https://github.com/ago19800/HomeMind/releases)

<div align="center">

☕ **Se questo addon ti è utile, offrimi un caffè!**

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
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/567129635-8dbdb604-953d-48ca-b20c-481fe74f8934.jpg" width="260">
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/567129636-e5f57e9e-e6fd-4957-8745-43771da01269.jpg" width="260">
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
- [Allarme Personalizzato](#-allarme-personalizzato)
- [Sensore Prossimità GPS](#-sensore-prossimità-gps)
- [Monitor Elettrodomestici](#-monitor-elettrodomestici)
- [Ottimizzatore Solare](#-ottimizzatore-solare)
- [Clima e Riscaldamento](#-clima-e-riscaldamento)
- [Memoria Persistente](#-memoria-persistente)
- [Routine Intelligente](#-routine-intelligente)
- [Telecamere Frigate](#telecamere-frigate)
- [Comandi Telegram](#comandi-telegram)
- [Interfaccia Vocale](#interfaccia-vocale-telegram)
- [FAQ](#faq-e-problemi-comuni)
- [Changelog](#changelog)

---

## 🧠 Cos'è HomeMind

HomeMind è un **add-on per Home Assistant** che aggiunge un cervello AI alla tua casa. Non è una semplice automazione — è un agente che capisce il contesto, impara la tua routine e ti avvisa solo quando serve davvero.

**Parlagli su Telegram in italiano naturale:**

> *"Accendi la luce del salotto"*
> *"Quanta energia ho prodotto oggi?"*
> *"Arma l'allarme"*
> *"Accendi la caldaia a 22 gradi"*
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
| 🔋 **Batteria piena** | Notifica quando la batteria è al 100% e il sole produce ancora |
| 📊 **Analisi energia** | Ogni mattina ti dice se hai consumato più o meno del solito |
| 🌅 **Briefing mattutino** | Alle 7:00 — meteo, energia, spazzatura e consiglio AI |
| 🗑️ **Spazzatura** | La sera prima ti ricorda cosa mettere fuori |
| 🧠 **Memoria persistente** | Impara le tue preferenze e le usa nelle risposte |
| 📅 **Routine intelligente** | Anticipa i tuoi bisogni in base alle abitudini reali |

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

1. Apri **HomeMind Orchestrator** → scheda **Configurazione**
2. Inserisci almeno token Telegram e chat ID
3. Clicca **Salva**
4. Torna alla scheda **Info** e clicca **Avvia**

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

> Il PIN reale del tuo antifurto fisico. Usato solo per armare/disarmare — mai esposto nei log o all'AI.

### Provider AI

Inserisci almeno **Gemini + Groq** — sono entrambi gratuiti.

```yaml
gemini_api_key: "AIzaSy..."          # 🟦 Google Gemini — GRATIS 1.500 req/giorno
gemini_model: "gemini-2.0-flash"

groq_api_key: "gsk_..."              # ⚡ Groq — GRATIS 100.000 token/giorno
groq_model: "llama-3.3-70b-versatile"

cerebras_api_key: "csk_..."          # 🧠 Cerebras — GRATIS 1M token/min
cerebras_model: "llama3.1-8b"

openai_api_key: "sk-..."             # 🟢 OpenAI — solo per messaggi vocali
openai_model: "gpt-4o-mini"
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

Apri HomeMind dal pannello HA → clicca **⚙️** in alto. Configura tutto senza toccare file:

- **👤 Persone** — chi monitorare e chi escludere
- **🚶 Sensori** — movimento e porte/finestre
- **🗑️ Spazzatura** — toggle e orario notifica
- **⚡ Energia** — sensori FV, consumo, rete
- **📹 Frigate** — telecamere per snapshot allarme

> I campi avanzati (`proximity_sensors`, `solar_optimizer`, `appliances` ecc.) vengono **preservati automaticamente** quando salvi dalla pagina web.

---

## Configurazione Avanzata via File

Per funzioni avanzate modifica il file:

```
/config/homemind_patches/person_config.json
```

Usa l'addon **File Editor** o **Studio Code Server** in HA per aprirlo.

---

## Configurazione BASE

Parti da qui — funziona subito con allarme automatico e briefing mattutino.

```json
{
  "language": "it",
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": [],
  "motion_whitelist": [
    "binary_sensor.sensore_ingresso_occupancy",
    "binary_sensor.sensore_soggiorno_occupancy"
  ],
  "motion_blacklist": []
}
```

---

## Configurazione MEDIA

Aggiunge GPS, energia e monitor elettrodomestici.

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
      "enabled": true, "name": "Lavatrice", "icon": "🫧",
      "mode": "power",
      "power_sensor": "sensor.presa_lavatrice_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5,
      "notify_on_start": false
    }
  }
}
```

---

## Configurazione AVANZATA

Tutto attivo — antifurto personalizzato, clima, solare, Frigate.

```json
{
  "language": "it",
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.mqtt_finto"],
  "motion_whitelist": ["binary_sensor.sensore_ingresso_occupancy"],
  "motion_blacklist": ["binary_sensor.telefono_mario_motion"],
  "contact_blacklist": ["binary_sensor.porta_garage_contact"],

  "alarm_panel": "alarm_control_panel.risco_casa",

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
  "climate": {
    "climate.termostato": {
      "name": "Termostato casa",
      "switch": "switch.caldaia",
      "min_temp": 15,
      "max_temp": 30
    }
  },
  "solar_optimizer": {
    "enabled": true,
    "min_surplus_w": 500, "confirm_minutes": 5, "cooldown_hours": 2,
    "battery_soc_sensor": "sensor.batteria_percentuale",
    "battery_full_threshold": 95, "min_sun_elevation": 10,
    "appliances": {
      "lavatrice": {
        "enabled": true, "switch": "switch.presa_lavatrice",
        "min_surplus_w": 800, "auto_start": false
      }
    }
  },
  "location_tracker": {
    "mario": "device_tracker.telefono_mario"
  },
  "frigate": {
    "enabled": true, "host": "192.168.1.100", "port": 5000,
    "snapshot_on_alarm": true,
    "cameras": {
      "ingresso": "binary_sensor.sensore_ingresso_occupancy",
      "garage":   "binary_sensor.sensore_garage_occupancy"
    }
  }
}
```

---

## 🔐 Allarme Personalizzato

HomeMind funziona con **qualsiasi antifurto** già integrato in HA — Risco, Paradox, Ajax, DSC, Texecom, Bentel, Verisure e qualsiasi altra marca.

```
HomeMind → Home Assistant → integrazione marca → antifurto fisico
```

### Passo 1 — Trova il nome del tuo allarme in HA

```
Strumenti Sviluppatori → Stati → cerca "alarm"
```

Esempi di nomi che potresti vedere:
- `alarm_control_panel.home_alarm` ← quello di default HA
- `alarm_control_panel.risco_casa`
- `alarm_control_panel.verisure_casa`
- `alarm_control_panel.paradox_mg5050`

### Passo 2 — Aggiungi nel config

**Formato semplice** (funziona con la maggior parte dei sistemi):
```json
"alarm_panel": "alarm_control_panel.risco_casa"
```

**Formato avanzato** (per sistemi con modalità specifiche come Verisure):
```json
"alarm_panel": {
  "entity": "alarm_control_panel.verisure_casa",
  "arm_mode": "armed_home"
}
```

Il campo `arm_mode` può essere:

| Valore | Quando usarlo |
|--------|---------------|
| `armed_away` | Armato — tutti fuori casa **(default)** |
| `armed_home` | Armato con qualcuno in casa (es. Verisure perimetrale) |
| `armed_night` | Modalità notte |

### Esempi per marca

| Marca | Configurazione |
|-------|---------------|
| **Risco** | `"alarm_panel": "alarm_control_panel.risco_casa"` |
| **Paradox** | `"alarm_panel": "alarm_control_panel.paradox_mg5050"` |
| **Ajax** | `"alarm_panel": "alarm_control_panel.ajax_hub"` |
| **DSC / Alarmo** | `"alarm_panel": "alarm_control_panel.dsc_alarmo"` |
| **Texecom** | `"alarm_panel": "alarm_control_panel.texecom_premier"` |
| **Verisure** | `"alarm_panel": {"entity": "alarm_control_panel.verisure_casa", "arm_mode": "armed_home"}` |
| **HA default** | Non serve configurare nulla — lo trova automaticamente |

### Passo 3 — Salva e aspetta 2 minuti

HomeMind rilegge il config ogni 2 minuti. Nel log vedrai:
```
INFO homemind.model — alarm_panel: alarm_control_panel.risco_casa (personalizzato)
```

> Se lasci il campo vuoto o non lo configuri, HomeMind cerca automaticamente il primo allarme disponibile in HA. Non si rompe nulla.

---

## 📍 Sensore Prossimità GPS

Il sensore distanza **vince sempre sul GPS** — risolve il problema del GPS che "salta" e arma l'allarme mentre sei ancora in casa.

```json
"proximity_sensors": {
  "person.mario": {
    "sensor": "sensor.casa_telefono_mario_distance",
    "threshold_m": 100,
    "stale_check": false
  }
}
```

| Campo | Descrizione |
|-------|-------------|
| `sensor` | Entity ID del sensore distanza in metri |
| `threshold_m` | Distanza sotto cui sei considerato "a casa" (default 100m) |
| `stale_check` | `false` = usa sempre l'ultimo valore anche se vecchio |

**Problema: il benvenuto non arriva per una persona ma per le altre sì**
Succede quando il sensore proximity aggiorna lentamente e HomeMind pensa che la persona fosse già in casa. Soluzione: abbassa la soglia:
```json
"threshold_m": 50
```

---

## ⚡ Monitor Elettrodomestici

**Modalità POWER** — per prese smart con misura potenza (Zigbee, Shelly, Tasmota):
```json
"lavatrice": {
  "enabled": true, "name": "Lavatrice", "icon": "🫧",
  "mode": "power",
  "power_sensor": "sensor.presa_lavatrice_power",
  "power_on_threshold": 50,
  "power_off_threshold": 10,
  "min_cycle_minutes": 20,
  "max_idle_minutes": 5,
  "notify_on_start": false
}
```

**Modalità SMART** — per elettrodomestici connessi (Bosch, Siemens ecc.):
```json
"lavastoviglie": {
  "enabled": true, "name": "Lavastoviglie", "icon": "🍽️",
  "mode": "smart",
  "state_sensor": "sensor.lavastoviglie_operation_state",
  "running_states": ["Run"],
  "done_states": ["Finished", "Ready"],
  "notify_on_start": false
}
```

---

## ☀️ Ottimizzatore Solare

Monitora il surplus FV ogni 2 minuti. Quando c'è abbastanza energia ti avvisa — rispondi **"sì"** per avviare l'elettrodomestico.

Funziona anche quando la **batteria è piena** — anche se l'inverter throttla il FV, HomeMind lo rileva tramite il livello solare effettivo. Nessuna notifica inutile la sera grazie al controllo elevazione del sole.

```json
"solar_optimizer": {
  "enabled": true,
  "min_surplus_w": 500,
  "confirm_minutes": 5,
  "cooldown_hours": 2,
  "battery_soc_sensor": "sensor.batteria_percentuale",
  "battery_full_threshold": 95,
  "min_sun_elevation": 10,
  "appliances": {
    "lavatrice": {
      "enabled": true,
      "switch": "switch.presa_lavatrice",
      "min_surplus_w": 800,
      "auto_start": false
    }
  }
}
```

Imposta `"auto_start": true` per avvio automatico senza chiedere conferma.

---

## 🌡️ Clima e Riscaldamento

Configura il tuo impianto così HomeMind capisce esattamente come gestirlo.

```json
"climate": {
  "climate.termostato": {
    "name": "Termostato casa",
    "switch": "switch.caldaia",
    "min_temp": 15,
    "max_temp": 30
  }
}
```

| Campo | Descrizione |
|-------|-------------|
| `switch` | Lo switch fisico della caldaia, se presente |
| `min_temp` / `max_temp` | Range temperatura consentito — deve corrispondere a quello in HA |

**Come funziona su Telegram:**
```
"Accendi la caldaia a 22 gradi"
→ Accende switch.caldaia + imposta 22° sul termostato

"Spegni il riscaldamento"
→ Spegne switch.caldaia

"Abbassa a 19 gradi"
→ Imposta 19° senza toccare lo switch
```

> Se ricevi errore **FAIL 500**, la temperatura richiesta supera il `max_temp` configurato in HA. Allinea il valore nel `configuration.yaml` di HA.

---

## 🧠 Memoria Persistente

HomeMind impara le tue preferenze nel tempo e le usa per rispondere in modo sempre più personale. Più parli con lui, più diventa preciso.

### Come impara

**In automatico** — dopo ogni conversazione estrae da solo i fatti utili:
```
Dici: "fa freddo, metti 22 gradi"
→ HomeMind nota che chiedi spesso 22° quando fa freddo
→ Salva: "Preferisce 22°C quando fa freddo"
→ La volta dopo imposta 22° senza che tu lo ripeta
```

**Esplicitamente** — gli dici tu cosa ricordare:
```
Tu: "Ricordati che il cane si chiama Rex"
Tu: "Ricorda che Rosa lavora fuori il martedì"
Tu: "La finestra del bagno è sempre aperta di proposito"
```

### Cosa cambia nella pratica

**Senza memoria:**
```
Tu: "Accendi le luci del salotto"
HomeMind: accende con impostazioni di default
```

**Con memoria** (dopo qualche giorno):
```
Tu: "Accendi le luci del salotto"
HomeMind: accende a luce calda 2700K al 40%
          (sa che la sera preferisci così)
```

**Altro esempio:**
```
Tu: "Dov'è Rosa?"

Senza memoria: "Rosa risulta fuori casa"

Con memoria:   "Rosa è fuori — di martedì lavora fuori,
                probabilmente è in ufficio"
```

### Esempi di cose utili da dirgli

```
"Il cane si chiama Rex"
→ Se i sensori scattano di notte capisce che è il cane

"Rosa lavora fuori il martedì e giovedì"
→ Sa spiegare dove si trova Rosa quei giorni

"La finestra del bagno è sempre aperta di proposito"
→ Non la segnala come anomalia

"Preferiamo luci calde la sera"
→ Imposta sempre 2700K dopo le 20:00

"La lavatrice si fa di sabato mattina"
→ Suggerisce il sabato per il surplus solare

"Mia suocera viene il venerdì"
→ Non si preoccupa per il movimento extra il venerdì

"Preferisco la casa a 21 gradi"
→ La usa come temperatura di default quando chiedi di accendere
```

### Comandi Telegram

```
/memoria              → mostra tutto ciò che HomeMind sa su di te
/dimentica caldaia    → rimuove i fatti che contengono "caldaia"
/memoria reset        → cancella tutto e ricomincia da zero
```

> **Importante:** la memoria personalizza le **risposte AI in chat**. Non cambia il comportamento automatico dell'allarme o degli avvisi di porte aperte — per quello serve il config JSON.

---

## 📅 Routine Intelligente

HomeMind osserva la tua routine reale ogni giorno e dopo soli **3 giorni** inizia ad anticipare i tuoi bisogni.

### Come impara

Ogni giorno registra silenziosamente: a che ora esci, a che ora rientri, quando c'è attività in cucina al mattino.

### Cosa fa in pratica

```
Mattina — rileva movimento in cucina 20 minuti prima del tuo orario tipico:

HomeMind: "🏃 Di solito esci alle 08:30 — mancano 20 minuti.
           Vuoi che preparo la casa?
           (abbasso riscaldamento + spengo luci)"

Rispondi "sì" → HomeMind esegue tutto da solo ✅
Rispondi "no" → non fa nulla ✅
Nessuna risposta → non fa nulla ✅
```

### Comando Telegram

```
/routine → mostra orari tipici appresi (uscita, rientro)
```

Nelle prime 3 giornate risponderà *"Sto ancora imparando la tua routine..."* — è normale.

---

## Telecamere Frigate

HomeMind si integra con **Frigate NVR** per mandare uno snapshot su Telegram ogni volta che scatta l'allarme. Funziona anche se Frigate è su un PC diverso nella stessa rete.

### Configurazione dalla pagina web

1. Apri **Impostazioni ⚙️** → tab **📹 Frigate**
2. Attiva il toggle **Abilita Frigate**
3. Inserisci **IP** e **porta** (default 5000)
4. Aggiungi le camere con nome e sensore corrispondente
5. Salva e riavvia

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

Il nome della camera (es. `ingresso`) deve corrispondere esattamente al nome che vedi in Frigate aprendo `http://IP:5000` nel browser.

**Cooldown anti-spam:** la stessa camera non manda più di uno snapshot ogni 60 secondi.

---

## Comandi Telegram

| Comando | Descrizione |
|---------|-------------|
| `/stato` | Stato completo: persone, sensori, allarme, temperature |
| `/briefing` | Ricevi subito il briefing mattutino |
| `/energia` | Produzione FV e consumi di oggi |
| `/ieri` | Produzione e consumi di ieri |
| `/solare` | Surplus FV e ottimizzatore |
| `/elettrodomestici` | Stato lavatrice, lavastoviglie ecc. |
| `/lavatrice` | Stato rapido lavatrice |
| `/lavastoviglie` | Stato rapido lavastoviglie |
| `/routine` | La tua routine appresa (orari uscita/rientro) |
| `/memoria` | Cosa HomeMind sa su di te |
| `/dimentica <testo>` | Rimuovi un fatto dalla memoria |
| `/memoria reset` | Cancella tutta la memoria |
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
→ Aggiungi il sensore distanza in `proximity_sensors`.

**HomeMind non controlla il mio Risco / Verisure / Paradox**
→ Aggiungi `"alarm_panel"` nel config JSON. Vai in **Strumenti Sviluppatori → Stati → cerca "alarm"** per trovare il nome esatto.

**Il benvenuto non arriva quando rientro**
→ Se hai il sensore proximity, controlla che si aggiorni correttamente. Prova ad abbassare `threshold_m` a 50.

**Errore FAIL 500 quando imposto la temperatura**
→ La temperatura supera il limite `max_temp` del termostato in HA. Controlla il tuo `configuration.yaml` e alza il massimo.

**"Accendi caldaia" agisce sul termostato invece dello switch**
→ Aggiungi il campo `climate` nel config con il tuo switch fisico — HomeMind capirà la differenza.

**La memoria non sembra funzionare**
→ Verifica con `/memoria` cosa è stato salvato. Ricorda che la memoria cambia le **risposte in chat**, non i comportamenti automatici.

**La routine non si attiva**
→ Servono almeno 3 giorni di dati. Controlla con `/routine` quanti giorni ha osservato finora.

**Il /stato mostra poche temperature**
→ HomeMind ora mostra tutte le temperature, filtrando i sensori di sistema (CPU ecc.).

**Non ricevo notifiche Telegram**
→ Verifica che `telegram_chat_id` sia un numero (usa @userinfobot). Lascia vuoto il campo `notify_entity`.

**Il briefing non arriva**
→ Scrivi `/briefing` per testarlo subito. Verifica nei log che il provider AI sia configurato.

**Frigate non si connette**
→ Verifica IP e porta. Testa nel browser: `http://IP:5000`.

**Ricevo foto duplicate**
→ Dalla v1.3.0 c'è il cooldown anti-duplicati — aggiorna l'addon.

**Salvo dalla pagina web ma i campi avanzati spariscono**
→ Dalla v1.2.0 il merge automatico è incluso — aggiorna l'addon.

---

## Changelog

**v1.5.0** — Smart Routine Manager: impara orari uscita/rientro, anticipa partenze, comando `/routine`

**v1.4.0** — Memoria persistente (`/memoria`, `/dimentica`, `/memoria reset`), allarme personalizzato con formato stringa e oggetto (supporto `arm_mode` per Verisure/Ajax), clima personalizzato con switch fisico e range temperatura, switch visibili all'AI, ottimizzatore solare batteria piena + elevazione solare, fix benvenuto proximity+GPS, fix proximity stale 4h, fix temperature nel `/stato`

**v1.3.0** — Fix `notify_entity` vuoto che bloccava Telegram, fix foto duplicate Frigate, cooldown anti-spam 60s per camera

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
