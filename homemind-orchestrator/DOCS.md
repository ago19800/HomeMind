<div align="center">

# 🧠 HomeMind Orchestrator

**[🇮🇹 Italiano](#-italiano) · [🇬🇧 English](#-english)**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![Language](https://img.shields.io/badge/Lingua-Italiano%20%2F%20English-green)]()
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Groq%20%7C%20Cerebras-orange)]()
[![Version](https://img.shields.io/badge/versione-1.3.5-brightgreen)](https://github.com/ago19800/HomeMind/releases)

☕ **Se questo addon ti è utile, offrimi un caffè! / If this addon is useful, buy me a coffee!**

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

**[paypal.me/ago19800](https://paypal.me/ago19800)**

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

---

# 🇮🇹 Italiano

> 🇬🇧 Looking for the English version? [Click here](#-english)

## 📋 Indice

- [Cos'è HomeMind](#cosè-homemind)
- [Installazione](#installazione)
- [Configurazione Addon](#configurazione-addon-it)
- [Pagina Impostazioni Web](#pagina-impostazioni-web-it)
- [Configurazione BASE](#configurazione-base)
- [Configurazione MEDIA](#configurazione-media)
- [Configurazione AVANZATA](#configurazione-avanzata)
- [Allarme Personalizzato](#allarme-personalizzato)
- [Sensore Prossimità GPS](#sensore-prossimità-gps)
- [Elettrodomestici](#monitor-elettrodomestici)
- [Ottimizzatore Solare](#ottimizzatore-solare)
- [Clima e Riscaldamento](#clima-e-riscaldamento)
- [Memoria Persistente](#memoria-persistente)
- [Routine Intelligente](#routine-intelligente)
- [Telecamere Frigate](#telecamere-frigate-it)
- [Comandi Telegram](#comandi-telegram-it)
- [Interfaccia Vocale](#interfaccia-vocale-it)
- [FAQ](#faq-it)
- [Changelog](#changelog)

---

## Cos'è HomeMind

HomeMind è un **add-on per Home Assistant** che aggiunge un cervello AI alla tua casa. Non è una semplice automazione — è un agente che capisce il contesto, impara la tua routine e ti avvisa solo quando serve davvero.

**Parlagli su Telegram in italiano naturale:**

> *"Accendi la luce del salotto"*
> *"Quanta energia ho prodotto oggi?"*
> *"Arma l'allarme"*
> *"Accendi la caldaia a 22 gradi"*

Puoi anche mandargli un **messaggio vocale** 🎙️ — trascrive la voce e la tratta come un comando normale.

### Cosa fa in automatico

| Funzione | Descrizione |
|----------|-------------|
| 🔒 **Allarme automatico** | Arma quando tutti escono, disarma quando torni |
| 👋 **Benvenuto a casa** | Messaggio su Telegram quando rientri |
| 📷 **Snapshot telecamere** | Foto automatica su Telegram quando scatta l'allarme |
| ⚡ **Monitor elettrodomestici** | Notifica quando lavatrice/lavastoviglie finiscono |
| ☀️ **Ottimizzatore solare** | Ti avvisa quando usare il surplus FV |
| 🔋 **Batteria piena** | Notifica quando la batteria è al 100% e il sole produce |
| 📊 **Analisi energia** | Ogni mattina confronta i consumi con la media storica |
| 🌅 **Briefing mattutino** | Alle 7:00 — meteo, energia, spazzatura, consiglio AI |
| 🗑️ **Spazzatura** | La sera prima ricorda cosa mettere fuori |
| 🧠 **Memoria persistente** | Impara le tue preferenze nel tempo |
| 📅 **Routine intelligente** | Anticipa i tuoi bisogni in base alle abitudini reali |

---

## Installazione

```
1. HA → Impostazioni → Add-on Store → ⋮ → Repositories
   → Incolla: https://github.com/ago19800/HomeMind → Aggiungi

2. Cerca "HomeMind Orchestrator" → Installa

3. Scheda Configurazione → inserisci dati → Salva → Avvia
```

---

## Configurazione Addon IT

### Telegram (obbligatorio)
```yaml
telegram_bot_token: "TOKEN_DA_BOTFATHER"   # @BotFather → /newbot
telegram_chat_id:   "IL_TUO_CHAT_ID"       # @userinfobot → /start → copia numero
alarm_code:         "1234"                 # PIN reale del tuo antifurto
```

### Provider AI (inserisci almeno Gemini + Groq — gratuiti)
```yaml
gemini_api_key:   "AIzaSy..."   # Gratis 1.500 req/giorno → aistudio.google.com
groq_api_key:     "gsk_..."     # Gratis 100k token/giorno → console.groq.com
cerebras_api_key: "csk_..."     # Gratis 1M token/min     → cloud.cerebras.ai
openai_api_key:   "sk-..."      # Solo per messaggi vocali → platform.openai.com
```

---

## Pagina Impostazioni Web IT

Apri HomeMind → clicca **⚙️** in alto. Configura senza toccare file:

- **👤 Persone** — chi monitorare, chi escludere
- **🚶 Sensori** — movimento e porte/finestre
- **🗑️ Spazzatura** — toggle e orario notifica
- **⚡ Energia** — sensori FV, consumo, rete
- **📹 Frigate** — telecamere per snapshot allarme

> I campi avanzati vengono sempre preservati quando salvi dalla pagina web.

---

## Configurazione BASE

```json
{
  "language": "it",
  "person_whitelist": ["person.mario", "person.lucia"],
  "motion_whitelist": [
    "binary_sensor.sensore_ingresso_occupancy",
    "binary_sensor.sensore_soggiorno_occupancy"
  ]
}
```

---

## Configurazione MEDIA

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
      "sensor": "sensor.casa_mario_distance",
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
      "enabled": true, "name": "Lavatrice", "icon": "🫧", "mode": "power",
      "power_sensor": "sensor.presa_lavatrice_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5, "notify_on_start": false
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
  "alarm_panel": "alarm_control_panel.risco_casa",
  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.casa_mario_distance",
      "threshold_m": 100, "stale_check": false
    }
  },
  "energy_sensors": {
    "produzione_fv": "sensor.fv_tot", "consumo_casa": "sensor.consumi_giornalieri",
    "rete_enel": "sensor.enel_giornaliero", "produzione_fv_w": "sensor.fotovoltaica_w",
    "consumo_casa_w": "sensor.inverter_ac_output", "rete_enel_w": "sensor.shelly_power"
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
      "name": "Termostato casa", "switch": "switch.caldaia",
      "min_temp": 15, "max_temp": 30
    }
  },
  "solar_optimizer": {
    "enabled": true, "min_surplus_w": 500, "confirm_minutes": 5, "cooldown_hours": 2,
    "battery_soc_sensor": "sensor.batteria_percentuale",
    "battery_full_threshold": 95, "min_sun_elevation": 10,
    "appliances": {
      "lavatrice": { "enabled": true, "switch": "switch.presa_lavatrice", "min_surplus_w": 800, "auto_start": false }
    }
  },
  "frigate": {
    "enabled": true, "host": "192.168.1.100", "port": 5000, "snapshot_on_alarm": true,
    "cameras": { "ingresso": "binary_sensor.sensore_ingresso_occupancy" }
  }
}
```

---

## Allarme Personalizzato

HomeMind funziona con **qualsiasi antifurto** integrato in HA — Risco, Paradox, Ajax, DSC, Verisure, Bentel e altri.

### Trova il nome del tuo allarme
```
HA → Strumenti Sviluppatori → Stati → cerca "alarm"
```

### Formato semplice (la maggior parte dei casi)
```json
"alarm_panel": "alarm_control_panel.risco_casa"
```

### Formato avanzato (Verisure, Ajax con modalità specifica)
```json
"alarm_panel": {
  "entity": "alarm_control_panel.verisure_casa",
  "arm_mode": "armed_home"
}
```

| `arm_mode` | Quando usarlo |
|------------|---------------|
| `armed_away` | Tutti fuori casa **(default)** |
| `armed_home` | Qualcuno in casa — perimetrale (es. Verisure) |
| `armed_night` | Modalità notte |

### Esempi per marca

| Marca | Configurazione |
|-------|---------------|
| **Risco** | `"alarm_panel": "alarm_control_panel.risco_casa"` |
| **Paradox** | `"alarm_panel": "alarm_control_panel.paradox_mg5050"` |
| **Ajax** | `"alarm_panel": "alarm_control_panel.ajax_hub"` |
| **DSC** | `"alarm_panel": "alarm_control_panel.dsc_alarmo"` |
| **Verisure** | `"alarm_panel": {"entity": "alarm_control_panel.verisure_casa", "arm_mode": "armed_home"}` |
| **HA default** | Non serve configurare nulla |

> HomeMind rilegge il config ogni 2 minuti — non serve riavviare.

---

## Sensore Prossimità GPS

Evita falsi allarmi quando il GPS "salta" — la distanza vince sempre sul GPS.

```json
"proximity_sensors": {
  "person.mario": {
    "sensor": "sensor.casa_mario_distance",
    "threshold_m": 100,
    "stale_check": false
  }
}
```

Se il **benvenuto non arriva** per una persona ma per le altre sì, abbassa la soglia:
```json
"threshold_m": 50
```

---

## Monitor Elettrodomestici

**Modalità POWER** (presa smart — Zigbee, Shelly, Tasmota):
```json
"mode": "power", "power_sensor": "sensor.presa_lavatrice_power",
"power_on_threshold": 50, "power_off_threshold": 10
```

**Modalità SMART** (elettrodomestici connessi — Bosch, Siemens):
```json
"mode": "smart", "state_sensor": "sensor.lavastoviglie_operation_state",
"running_states": ["Run"], "done_states": ["Finished", "Ready"]
```

---

## Ottimizzatore Solare

Monitora il surplus ogni 2 minuti. Rispondi **"sì"** su Telegram per avviare l'elettrodomestico. Funziona anche con batteria piena grazie al controllo elevazione solare.

```json
"solar_optimizer": {
  "enabled": true, "min_surplus_w": 500,
  "battery_soc_sensor": "sensor.batteria_percentuale",
  "battery_full_threshold": 95, "min_sun_elevation": 10
}
```

---

## Clima e Riscaldamento

```json
"climate": {
  "climate.termostato": {
    "name": "Termostato casa",
    "switch": "switch.caldaia",
    "min_temp": 15, "max_temp": 30
  }
}
```

**Esempi su Telegram:**
```
"Accendi la caldaia a 22 gradi"  → accende switch + imposta 22°
"Spegni il riscaldamento"        → spegne switch
"Abbassa a 19 gradi"             → imposta 19° senza toccare lo switch
```

> Se ricevi **FAIL 500**: la temperatura supera il `max_temp` in HA. Allinea il valore nel `configuration.yaml`.

---

## Memoria Persistente

HomeMind impara le tue preferenze e le usa per rispondere in modo sempre più personale.

### Come impara

**Automaticamente** — estrae i fatti utili da solo dopo ogni conversazione:
```
Dici: "fa freddo, metti 22 gradi"
→ Salva: "Preferisce 22°C quando fa freddo"
→ La volta dopo imposta 22° senza che tu lo chieda
```

**Esplicitamente** — gli dici tu cosa ricordare:
```
"Ricordati che il cane si chiama Rex"
"Rosa lavora fuori il martedì e giovedì"
"La finestra del bagno è sempre aperta di proposito"
"Preferiamo luci calde la sera"
"La lavatrice si fa il sabato mattina"
```

### Cosa cambia nella pratica

```
Senza memoria:
Tu: "Dov'è Rosa?"
HomeMind: "Rosa risulta fuori casa"

Con memoria:
Tu: "Dov'è Rosa?"
HomeMind: "Rosa è fuori — di martedì lavora fuori,
           probabilmente è in ufficio"
```

### Comandi
```
/memoria              → mostra tutto ciò che HomeMind sa su di te
/dimentica caldaia    → rimuove i fatti contenenti "caldaia"
/memoria reset        → cancella tutto
```

> La memoria cambia le **risposte in chat**, non i comportamenti automatici (allarme, avvisi). Per quelli serve il config JSON.

---

## Routine Intelligente

Dopo **3 giorni** di osservazione, HomeMind inizia ad anticipare i tuoi bisogni.

```
Mattina — movimento in cucina 20 min prima del tuo orario tipico:

HomeMind: "🏃 Di solito esci alle 08:30 — mancano 20 minuti.
           Vuoi che preparo la casa?
           (abbasso riscaldamento + spengo luci)"

"sì" → HomeMind esegue tutto ✅
"no" → non fa nulla ✅
```

```
/routine → mostra orari tipici appresi
```

---

## Telecamere Frigate IT

```json
"frigate": {
  "enabled": true, "host": "192.168.1.100", "port": 5000,
  "snapshot_on_alarm": true,
  "cameras": {
    "ingresso": "binary_sensor.sensore_ingresso_occupancy",
    "garage":   "binary_sensor.sensore_garage_occupancy"
  }
}
```

Il nome camera deve corrispondere a quello in Frigate (`http://IP:5000`). Cooldown anti-spam: 60s per camera.

---

## Comandi Telegram IT

| Comando | Descrizione |
|---------|-------------|
| `/stato` | Stato completo: persone, allarme, temperature |
| `/briefing` | Briefing mattutino subito |
| `/energia` | Produzione FV e consumi oggi |
| `/ieri` | Energia di ieri |
| `/solare` | Surplus FV e ottimizzatore |
| `/elettrodomestici` | Stato elettrodomestici |
| `/routine` | Routine appresa |
| `/memoria` | Cosa HomeMind sa su di te |
| `/dimentica <testo>` | Rimuovi un fatto |
| `/memoria reset` | Cancella memoria |
| `/spazzatura` | Raccolta prossimi 7 giorni |
| `/ricarica_spazzatura` | Rileggi PDF calendario |
| `/aggiornamenti` | Aggiornamenti HA |
| `/riparazioni` | Problemi HA |
| `/providers` | Provider AI attivi |
| `/lingua it` / `/lingua en` | Cambia lingua |
| `/comandi` | Questa lista |

---

## Interfaccia Vocale IT

Manda un **messaggio vocale** — HomeMind lo trascrive con Whisper e lo tratta come un comando.
**Attivazione:** inserisci `openai_api_key` nella configurazione.

---

## FAQ IT

**L'allarme si arma mentre sono in casa** → Configura `proximity_sensors`.

**HomeMind non controlla il mio Risco/Verisure** → Aggiungi `"alarm_panel"` nel config. Cerca il nome in **Strumenti Sviluppatori → Stati → "alarm"**.

**Il benvenuto non arriva** → Abbassa `threshold_m` a 50.

**Errore FAIL 500 sulla temperatura** → Controlla `max_temp` nel `configuration.yaml` di HA.

**"Accendi caldaia" agisce sul termostato** → Aggiungi il campo `climate` con lo switch fisico.

**La routine non si attiva** → Servono 3 giorni di dati. Controlla con `/routine`.

**Il /stato mostra poche temperature** → Aggiorna alla v1.4.0 — ora le mostra tutte.

**Non ricevo notifiche Telegram** → Verifica `telegram_chat_id` con @userinfobot.

---

---

# 🇬🇧 English

> 🇮🇹 Cerchi la versione italiana? [Clicca qui](#-italiano)

## 📋 Table of Contents

- [What is HomeMind](#what-is-homemind)
- [Installation](#installation)
- [Addon Configuration](#addon-configuration)
- [Web Settings Page](#web-settings-page)
- [BASE Configuration](#base-configuration)
- [MEDIUM Configuration](#medium-configuration)
- [ADVANCED Configuration](#advanced-configuration)
- [Custom Alarm Panel](#custom-alarm-panel)
- [GPS Proximity Sensor](#gps-proximity-sensor)
- [Appliance Monitor](#appliance-monitor)
- [Solar Optimizer](#solar-optimizer)
- [Climate and Heating](#climate-and-heating)
- [Persistent Memory](#persistent-memory)
- [Smart Routine](#smart-routine)
- [Frigate Cameras](#frigate-cameras)
- [Telegram Commands](#telegram-commands)
- [Voice Interface](#voice-interface)
- [FAQ](#faq-en)
- [Changelog](#changelog)

---

## What is HomeMind

HomeMind is a **Home Assistant add-on** that adds an AI brain to your home. It's not a simple automation — it's an agent that understands context, learns your routine and alerts you only when it really matters.

**Talk to it on Telegram in natural language:**

> *"Turn on the living room light"*
> *"How much energy did I produce today?"*
> *"Arm the alarm"*
> *"Turn on the boiler at 22 degrees"*

You can also send **voice messages** 🎙️ — it transcribes the voice and treats it as a normal command.

### What it does automatically

| Feature | Description |
|---------|-------------|
| 🔒 **Automatic alarm** | Arms when everyone leaves, disarms when you return |
| 👋 **Welcome home** | Telegram message when you arrive |
| 📷 **Camera snapshots** | Automatic photo on Telegram when alarm triggers |
| ⚡ **Appliance monitor** | Notifies when washer/dishwasher finish |
| ☀️ **Solar optimizer** | Tells you when to use FV surplus |
| 🔋 **Full battery** | Notifies when battery is 100% and sun still produces |
| 📊 **Energy analysis** | Every morning compares consumption with historical average |
| 🌅 **Morning briefing** | At 7:00 — weather, energy, trash, AI tip |
| 🗑️ **Trash reminder** | The evening before reminds what to put out |
| 🧠 **Persistent memory** | Learns your preferences over time |
| 📅 **Smart routine** | Anticipates your needs based on real habits |

---

## Installation

```
1. HA → Settings → Add-on Store → ⋮ → Repositories
   → Paste: https://github.com/ago19800/HomeMind → Add

2. Search "HomeMind Orchestrator" → Install

3. Configuration tab → enter data → Save → Start
```

---

## Addon Configuration

### Telegram (required)
```yaml
telegram_bot_token: "TOKEN_FROM_BOTFATHER"   # @BotFather → /newbot
telegram_chat_id:   "YOUR_CHAT_ID"           # @userinfobot → /start → copy number
alarm_code:         "1234"                   # real PIN of your alarm system
```

### AI Providers (add at least Gemini + Groq — both free)
```yaml
gemini_api_key:   "AIzaSy..."   # Free 1,500 req/day  → aistudio.google.com
groq_api_key:     "gsk_..."     # Free 100k token/day → console.groq.com
cerebras_api_key: "csk_..."     # Free 1M token/min   → cloud.cerebras.ai
openai_api_key:   "sk-..."      # Only for voice msg  → platform.openai.com
```

---

## Web Settings Page

Open HomeMind → click **⚙️** at the top. Configure without editing files:

- **👤 People** — who to monitor, who to exclude
- **🚶 Sensors** — motion and door/window sensors
- **🗑️ Trash** — toggle and notification time
- **⚡ Energy** — FV, consumption, grid sensors
- **📹 Frigate** — cameras for alarm snapshots

> Advanced fields are always preserved when saving from the web page.

---

## BASE Configuration

```json
{
  "language": "en",
  "person_whitelist": ["person.mario", "person.lucia"],
  "motion_whitelist": [
    "binary_sensor.entrance_sensor_occupancy",
    "binary_sensor.living_room_sensor_occupancy"
  ]
}
```

---

## MEDIUM Configuration

```json
{
  "language": "en",
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.fake_mqtt"],
  "motion_whitelist": ["binary_sensor.entrance_sensor_occupancy"],
  "motion_blacklist": ["binary_sensor.mario_phone_motion"],
  "contact_blacklist": ["binary_sensor.garage_door_contact"],
  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.home_mario_distance",
      "threshold_m": 100,
      "stale_check": false
    }
  },
  "energy_sensors": {
    "produzione_fv": "sensor.fv_total",
    "consumo_casa":  "sensor.daily_consumption",
    "rete_enel":     "sensor.grid_daily"
  },
  "appliances": {
    "washer": {
      "enabled": true, "name": "Washer", "icon": "🫧", "mode": "power",
      "power_sensor": "sensor.washer_plug_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5, "notify_on_start": false
    }
  }
}
```

---

## ADVANCED Configuration

```json
{
  "language": "en",
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.fake_mqtt"],
  "motion_whitelist": ["binary_sensor.entrance_sensor_occupancy"],
  "motion_blacklist": ["binary_sensor.mario_phone_motion"],
  "contact_blacklist": ["binary_sensor.garage_door_contact"],
  "alarm_panel": "alarm_control_panel.risco_home",
  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.home_mario_distance",
      "threshold_m": 100, "stale_check": false
    }
  },
  "energy_sensors": {
    "produzione_fv": "sensor.fv_total", "consumo_casa": "sensor.daily_consumption",
    "rete_enel": "sensor.grid_daily", "produzione_fv_w": "sensor.fv_watts",
    "consumo_casa_w": "sensor.inverter_ac_output", "rete_enel_w": "sensor.shelly_power"
  },
  "appliances": {
    "washer": {
      "enabled": true, "name": "Washer", "icon": "🫧", "mode": "power",
      "power_sensor": "sensor.washer_plug_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5, "notify_on_start": false
    },
    "dishwasher": {
      "enabled": true, "name": "Dishwasher", "icon": "🍽️", "mode": "smart",
      "state_sensor": "sensor.dishwasher_operation_state",
      "running_states": ["Run"], "done_states": ["Finished", "Ready"],
      "notify_on_start": false
    }
  },
  "climate": {
    "climate.thermostat": {
      "name": "Home thermostat", "switch": "switch.boiler",
      "min_temp": 15, "max_temp": 30
    }
  },
  "solar_optimizer": {
    "enabled": true, "min_surplus_w": 500, "confirm_minutes": 5, "cooldown_hours": 2,
    "battery_soc_sensor": "sensor.battery_percentage",
    "battery_full_threshold": 95, "min_sun_elevation": 10,
    "appliances": {
      "washer": { "enabled": true, "switch": "switch.washer_plug", "min_surplus_w": 800, "auto_start": false }
    }
  },
  "frigate": {
    "enabled": true, "host": "192.168.1.100", "port": 5000, "snapshot_on_alarm": true,
    "cameras": { "entrance": "binary_sensor.entrance_sensor_occupancy" }
  }
}
```

---

## Custom Alarm Panel

HomeMind works with **any alarm system** already integrated in HA — Risco, Paradox, Ajax, DSC, Verisure, Bentel and others.

### Find your alarm name
```
HA → Developer Tools → States → search "alarm"
```

### Simple format (works for most systems)
```json
"alarm_panel": "alarm_control_panel.risco_home"
```

### Advanced format (Verisure, Ajax with specific modes)
```json
"alarm_panel": {
  "entity": "alarm_control_panel.verisure_home",
  "arm_mode": "armed_home"
}
```

| `arm_mode` | When to use |
|------------|-------------|
| `armed_away` | Everyone away **(default)** |
| `armed_home` | Someone home — perimeter only (e.g. Verisure) |
| `armed_night` | Night mode |

### Examples by brand

| Brand | Configuration |
|-------|--------------|
| **Risco** | `"alarm_panel": "alarm_control_panel.risco_home"` |
| **Paradox** | `"alarm_panel": "alarm_control_panel.paradox_mg5050"` |
| **Ajax** | `"alarm_panel": "alarm_control_panel.ajax_hub"` |
| **DSC** | `"alarm_panel": "alarm_control_panel.dsc_alarmo"` |
| **Verisure** | `"alarm_panel": {"entity": "alarm_control_panel.verisure_home", "arm_mode": "armed_home"}` |
| **HA default** | No configuration needed |

> HomeMind re-reads the config every 2 minutes — no restart needed.

---

## GPS Proximity Sensor

Prevents false alarms when GPS "jumps" — distance always wins over GPS.

```json
"proximity_sensors": {
  "person.mario": {
    "sensor": "sensor.home_mario_distance",
    "threshold_m": 100,
    "stale_check": false
  }
}
```

If **welcome message doesn't arrive** for one person but does for others, lower the threshold:
```json
"threshold_m": 50
```

---

## Appliance Monitor

**POWER mode** (smart plug — Zigbee, Shelly, Tasmota):
```json
"mode": "power", "power_sensor": "sensor.washer_plug_power",
"power_on_threshold": 50, "power_off_threshold": 10
```

**SMART mode** (connected appliances — Bosch, Siemens):
```json
"mode": "smart", "state_sensor": "sensor.dishwasher_operation_state",
"running_states": ["Run"], "done_states": ["Finished", "Ready"]
```

---

## Solar Optimizer

Monitors surplus every 2 minutes. Reply **"yes"** on Telegram to start the appliance. Also works when battery is full thanks to sun elevation check.

```json
"solar_optimizer": {
  "enabled": true, "min_surplus_w": 500,
  "battery_soc_sensor": "sensor.battery_percentage",
  "battery_full_threshold": 95, "min_sun_elevation": 10
}
```

---

## Climate and Heating

```json
"climate": {
  "climate.thermostat": {
    "name": "Home thermostat",
    "switch": "switch.boiler",
    "min_temp": 15, "max_temp": 30
  }
}
```

**Telegram examples:**
```
"Turn on the boiler at 22 degrees"  → turns on switch + sets 22°
"Turn off heating"                  → turns off switch
"Lower to 19 degrees"               → sets 19° without touching the switch
```

> If you get **FAIL 500**: the temperature exceeds `max_temp` in HA. Update the value in `configuration.yaml`.

---

## Persistent Memory

HomeMind learns your preferences and uses them to respond in an increasingly personal way.

### How it learns

**Automatically** — extracts useful facts on its own after each conversation:
```
You say: "it's cold, set 22 degrees"
→ Saves: "Prefers 22°C when cold"
→ Next time sets 22° without being asked
```

**Explicitly** — you tell it what to remember:
```
"Remember that the dog's name is Rex"
"Rosa works outside on Tuesdays and Thursdays"
"The bathroom window is always open on purpose"
"We prefer warm lights in the evening"
"Laundry is done on Saturday mornings"
```

### What changes in practice

```
Without memory:
You: "Where is Rosa?"
HomeMind: "Rosa is currently away"

With memory:
You: "Where is Rosa?"
HomeMind: "Rosa is out — on Tuesdays she works outside,
           she's probably at the office"
```

### Commands
```
/memory              → shows everything HomeMind knows about you
/forget boiler       → removes facts containing "boiler"
/memory reset        → clears everything
```

> Memory changes **AI chat responses**, not automatic behaviors (alarm, open sensor alerts). For those, use the JSON config.

---

## Smart Routine

After **3 days** of observation, HomeMind starts anticipating your needs.

```
Morning — motion in kitchen 20 min before your typical departure time:

HomeMind: "🏃 You usually leave at 08:30 — 20 minutes to go.
           Shall I prepare the house?
           (lower heating + turn off lights)"

"yes" → HomeMind does everything ✅
"no"  → does nothing ✅
```

```
/routine → shows learned typical times
```

---

## Frigate Cameras

```json
"frigate": {
  "enabled": true, "host": "192.168.1.100", "port": 5000,
  "snapshot_on_alarm": true,
  "cameras": {
    "entrance": "binary_sensor.entrance_sensor_occupancy",
    "garage":   "binary_sensor.garage_sensor_occupancy"
  }
}
```

Camera name must match the name in Frigate (`http://IP:5000`). Anti-spam cooldown: 60s per camera.

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/stato` | Full status: people, alarm, temperatures |
| `/briefing` | Morning briefing right now |
| `/energia` | FV production and today's consumption |
| `/ieri` | Yesterday's energy |
| `/solare` | FV surplus and optimizer |
| `/elettrodomestici` | Appliance status |
| `/routine` | Learned routine |
| `/memory` | What HomeMind knows about you |
| `/forget <text>` | Remove a fact |
| `/memory reset` | Clear all memory |
| `/spazzatura` | Trash collection next 7 days |
| `/aggiornamenti` | HA updates |
| `/riparazioni` | HA issues |
| `/providers` | Active AI providers |
| `/lingua it` / `/lingua en` | Change language |
| `/comandi` | This list |

---

## Voice Interface

Send a **voice message** — HomeMind transcribes it with Whisper and treats it as a normal command.
**Activation:** add `openai_api_key` in the addon configuration.

---

## FAQ EN

**Alarm arms while I'm still home** → Configure `proximity_sensors` with your phone's distance sensor.

**HomeMind doesn't control my Risco/Verisure** → Add `"alarm_panel"` in config. Find exact name in **Developer Tools → States → search "alarm"**.

**Welcome message doesn't arrive** → Lower `threshold_m` to 50.

**FAIL 500 error when setting temperature** → Check `max_temp` in HA's `configuration.yaml`.

**"Turn on boiler" controls thermostat instead of switch** → Add `climate` field in config with your physical switch.

**Routine doesn't trigger** → Needs 3 days of data. Check with `/routine`.

**Morning briefing doesn't arrive** → Type `/briefing` to test it. Check logs for AI provider configuration.

**Not receiving Telegram notifications** → Verify `telegram_chat_id` is a number (use @userinfobot).

**Frigate not connecting** → Verify IP and port. Test in browser: `http://IP:5000`.

---

---

## Changelog

**v1.3.5** — Smart Routine Manager: learns departure/arrival times, anticipates departures, `/routine` command

**v1.3.4** — Persistent memory (`/memoria`, `/dimentica`, `/memoria reset`), custom alarm panel (string and object format, `arm_mode` support for Verisure/Ajax), custom climate with physical switch and temperature range, switches visible to AI, solar optimizer full battery + sun elevation, welcome fix proximity+GPS, 4h proximity stale fix, temperature fix in `/stato`

**v1.3.0** — Fix empty `notify_entity` blocking Telegram, fix duplicate Frigate photos, 60s anti-spam cooldown per camera

**v1.2.x** — Frigate NVR integration, automatic alarm snapshots, Frigate tab in web settings

**v1.2.0** — Full web settings page (5 tabs), automatic merge of advanced fields

**v1.1.x** — Navigation tab fix, UTF-8 BOM fix, live dashboard

**v1.0.4** — Voice interface via Whisper

**v1.0.2** — Security fixes: alarm code, web auth, PII logs

**v1.0.0** — Initial release

---

<div align="center">

**HomeMind Orchestrator** — *La tua casa, finalmente intelligente. / Your home, finally intelligent.*

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

**[paypal.me/ago19800](https://paypal.me/ago19800)**

[🔝 Torna su / Back to top](#-homemind-orchestrator)

</div>
