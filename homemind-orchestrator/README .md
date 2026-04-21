<div align="center">

# 🧠 HomeMind Orchestrator

**[🇮🇹 Italiano](#-italiano) · [🇬🇧 English](#-english)**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![Language](https://img.shields.io/badge/Lingua-Italiano%20%2F%20English-green)]()
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Groq%20%7C%20Cerebras%20%7C%20DeepSeek%20%7C%20Mistral%20%7C%20Claude%20%7C%20OpenAI-orange)]()

☕ **Se questo addon ti è utile, offrimi un caffè! / If this addon is useful, buy me a coffee!**

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

</div>

---

# 🇮🇹 Italiano

## Cos'è HomeMind

HomeMind è un **add-on per Home Assistant** che aggiunge un cervello AI alla tua casa. Non è una semplice automazione — è un agente che capisce il contesto, impara la tua routine e ti avvisa solo quando serve davvero.

**Parlagli su Telegram in italiano naturale:**
> *"Accendi la luce del salotto"* · *"Quanta energia ho prodotto oggi?"* · *"Apri le tapparelle al 70%"*

Puoi anche mandargli un **messaggio vocale** 🎙️ — trascrive la voce e la tratta come un comando normale.

---

## Cosa fa in automatico

| Funzione | Descrizione |
|----------|-------------|
| 🔒 **Allarme automatico** | Arma quando tutti escono, disarma quando torni — 3 modalità configurabili (`auto`, `notify`, `disabled`) |
| 🔔 **Notifica antifurto** | Con `alarm_auto_arm: notify`, manda un messaggio Telegram con bottoni ✅/❌ prima di armare |
| 👋 **Benvenuto a casa** | Messaggio su Telegram quando rientri — include stato antifurto se era armato (es. "🔓 Antifurto disarmato") |
| 📷 **Snapshot telecamere** | Foto automatica su Telegram quando scatta l'allarme (richiede Frigate) |
| 🤖 **Automazioni in linguaggio naturale** | Crea automazioni HA direttamente da Telegram: *"accendi luce esterna quando scala rileva movimento alle 23"* |
| ⚡ **Monitor elettrodomestici** | Notifica quando lavatrice/lavastoviglie finiscono |
| ☀️ **Ottimizzatore solare** | Avvisa quando usare il surplus FV — con conferma o auto |
| 🔕 **Do Not Disturb** | Blocca notifiche non critiche nelle ore notturne |
| 🌡️ **Filtri temperatura/umidità** | Scegli esattamente quali sensori HomeMind usa per briefing e risposte AI |
| 📍 **Proximity GPS** | Rileva avvicinamento/allontanamento da casa con soglia personalizzabile in metri |
| 🔗 **Alias comandi rapidi** | Parole chiave personalizzate → azioni garantite senza AI, anche offline |
| 🔌 **Modalità offline** | Luci, tapparelle, allarme funzionano anche senza AI |
| 📊 **Analisi energia** | Ogni mattina confronta i consumi con la media storica |
| 🌅 **Briefing mattutino** | Personalizzabile via Telegram: sensori, orario, sezioni, saluto, meteo città |
| 🌤️ **Meteo esterno** | Previsioni 3 giorni via open-meteo.com — nessuna API key |
| 🗑️ **Spazzatura** | La sera prima ricorda cosa mettere fuori |
| 🧠 **Memoria persistente** | Impara le tue preferenze nel tempo, aggiorna senza duplicati |
| 📅 **Routine intelligente** | Anticipa i tuoi bisogni in base alle abitudini reali |
| ⚠️ **Power Guard** | Protegge dalla soglia contrattuale Enel — 3 modalità |
| ⏰ **Task programmati** | Schedula azioni future in linguaggio naturale |
| 📊 **Fascia oraria F1/F2/F3** | Consumi suddivisi per fascia ARERA |
| 🤖 **Multi-AI con fallback** | 7 provider AI con cambio automatico in cascata |
| 🔧 **Automazioni da Telegram** | Crea, modifica ed elimina automazioni HA via chat |
| 🩺 **Analisi Log AI** | Legge i log HA, trova errori e propone fix |
| 🎨 **Dashboard Lovelace AI** | Genera dashboard Lovelace su misura |
| 📖 **Manuale interattivo** | `/readme <domanda>` cerca nel manuale direttamente da Telegram |

---

## Installazione Addon HAOS

> Per **Home Assistant OS** o **Home Assistant Supervised**

```
1. HA → Impostazioni → Add-on Store → ⋮ → Repository
   → Incolla: https://github.com/ago19800/HomeMind → Aggiungi

2. Cerca "HomeMind Orchestrator" → Installa

3. Scheda Configurazione → inserisci i tuoi dati → Salva → Avvia
```

**Configurazione addon:**
```yaml
telegram_bot_token: "TOKEN_DA_BOTFATHER"
telegram_chat_id:   "IL_TUO_CHAT_ID"
alarm_code:         "1234"
openai_api_key:     "sk-..."   # solo per messaggi vocali
```

---

## 🐳 Installazione Docker

```bash
mkdir ~/homemind && cd ~/homemind
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/docker-compose.yml
cp .env.example .env && nano .env
docker-compose up -d
```

**File .env:**
```env
HA_URL=http://192.168.1.100:8123
HA_TOKEN=eyJhbGciOiJ...
TELEGRAM_TOKEN=1234567890:AABBCCDDee...
TELEGRAM_CHAT_ID=123456789
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
```

| | Addon HAOS | Docker |
|--|--|--|
| person_config.json | `/config/homemind_patches/` | `~/homemind_data/homemind_patches/` |
| Dashboard web | ✅ | ✅ porta 8099 |
| Aggiornamenti | Add-on Store | `docker-compose pull && up -d` |

---

## Provider AI e Fallback automatico 🤖

HomeMind usa **più provider AI in cascata**. Se uno non risponde, passa automaticamente al successivo.

```
Messaggio → Gemini → quota? → Groq → rate limit? → Cerebras → ... → Modalità Offline
```

**Groq Free** ha ~12.000 token/min. Il contesto di HomeMind pesa 7.000–9.000 token: due messaggi ravvicinati lo saturano. Configura almeno **Gemini + Groq + Cerebras** (tutti gratuiti).

**In person_config.json:**
```json
"ai_providers": [
  {"name": "gemini",   "model": "gemini-2.0-flash",        "api_key": "AIzaSy..."},
  {"name": "groq",     "model": "llama-3.3-70b-versatile",  "api_key": "gsk_..."},
  {"name": "cerebras", "model": "llama3.1-8b",              "api_key": "csk_..."},
  {"name": "mistral",  "model": "mistral-small-latest",     "api_key": "..."}
]
```

| Provider | Costo | Limite | Link |
|----------|-------|--------|------|
| 🟦 Gemini | **Gratis** | 1.500 req/giorno | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ Groq | **Gratis** | 12.000 token/min | [console.groq.com](https://console.groq.com) |
| 🧠 Cerebras | **Gratis** | 1M token/min ⚡ | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 DeepSeek | ~Gratis | $0.014/1M token | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟣 Mistral | Gratis (tier) | — | [console.mistral.ai](https://console.mistral.ai) |
| 🟠 Claude | A pagamento | — | [console.anthropic.com](https://console.anthropic.com) |
| 🟢 OpenAI | A pagamento | necessario per voce | [platform.openai.com](https://platform.openai.com) |

---

## Geolocalizzazione GPS 📍

### Passo 1 — Installa la Companion App

- Android → [Google Play](https://play.google.com/store/apps/details?id=io.homeassistant.companion.android)
- iOS → [App Store](https://apps.apple.com/app/home-assistant/id1099568401)

Accedi al tuo HA dall'app e concedi i permessi di localizzazione su **Sempre**.

### Passo 2 — Verifica le entità create

HA crea automaticamente:
- `person.nome_tuo` — presenza (home / not_home)
- `sensor.nome_tuo_telefono_distance` — distanza da casa in metri

**HA → Strumenti Sviluppo → Stati** → cerca `person.` e `sensor.` con il tuo nome.

### Passo 3 — Configura

```json
{
  "person_whitelist": ["person.mario", "person.lucia"],
  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.mario_sm_s24_distance",
      "threshold_m": 100,
      "stale_check": false
    }
  }
}
```

---

## Location Tracker — Dove è stato? 📍🗺️

Funzione opzionale: chiedi a HomeMind dove si è trovata una persona nelle ultime ore, con indirizzi reali (OpenStreetMap, gratuito).

```json
"location_tracker": {
  "agostino": "device_tracker.sm_s931b",
  "rosa":     "device_tracker.sm_a166b"
}
```

**Come trovare il device_tracker:** HA → Strumenti Sviluppo → Stati → cerca `device_tracker.`

**Comandi:** `dove è stato Agostino oggi?` · `percorso di Rosa` · `soste di Agostino`

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
  "person_blacklist": ["person.tablet_finto"],
  "motion_whitelist": ["binary_sensor.sensore_ingresso_occupancy"],
  "contact_blacklist": ["binary_sensor.porta_garage_contact"],

  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.mario_sm_s24_distance",
      "threshold_m": 100,
      "stale_check": false
    }
  },

  "temperature_sensors": [
    "sensor.temp_soggiorno",
    "sensor.temp_camera"
  ],
  "humidity_sensors": [
    "sensor.umidita_soggiorno"
  ],

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
      "min_cycle_minutes": 20, "max_idle_minutes": 5
    }
  },

  "quiet_hours": {
    "enabled": true,
    "start": 23,
    "end": 7
  }
}
```

---

## Configurazione AVANZATA

```json
{
  "language": "it",
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.tablet_finto"],
  "motion_whitelist": ["binary_sensor.sensore_ingresso_occupancy"],
  "motion_blacklist": ["binary_sensor.sensore_cellulare"],
  "contact_blacklist": ["binary_sensor.porta_garage_contact"],

  "temperature_sensors": [
    "sensor.temp_soggiorno",
    "sensor.temp_camera",
    "sensor.temp_cucina",
    "sensor.temp_esterna"
  ],
  "humidity_sensors": [
    "sensor.umidita_soggiorno",
    "sensor.umidita_bagno"
  ],

  "alarm_panel": "alarm_control_panel.risco_casa",
  "alarm_auto_arm": "notify",
  "alarm_arm_mode": "armed_away",

  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.mario_sm_s24_distance",
      "threshold_m": 100,
      "stale_check": false
    }
  },

  "energy_sensors": {
    "produzione_fv": "sensor.fv_tot",
    "consumo_casa": "sensor.consumi_giornalieri",
    "rete_enel": "sensor.enel_giornaliero",
    "batteria_wh": "sensor.batteria_percentuale"
  },

  "climate": {
    "climate.termostato": {
      "name": "Termostato casa",
      "switch": "switch.caldaia",
      "min_temp": 15,
      "max_temp": 30
    }
  },
  "climate_auto_off": true,
  "climate_exclude": [],

  "appliances": {
    "lavatrice": {
      "enabled": true, "name": "Lavatrice", "icon": "🫧",
      "mode": "power",
      "power_sensor": "sensor.presa_lavatrice_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5
    },
    "lavastoviglie": {
      "enabled": true, "name": "Lavastoviglie", "icon": "🍽️",
      "mode": "smart",
      "state_sensor": "sensor.lavastoviglie_operation_state",
      "running_states": ["Run"],
      "done_states": ["Finished", "Ready"]
    }
  },

  "solar_optimizer": {
    "enabled": true,
    "min_surplus_w": 500,
    "battery_soc_sensor": "sensor.batteria_percentuale",
    "battery_full_threshold": 95,
    "battery_full_min_fv_w": 300,
    "min_sun_elevation": 10,
    "confirm_minutes": 5,
    "cooldown_hours": 2,
    "appliances": {
      "lavatrice": {
        "enabled": true,
        "switch": "switch.presa_lavatrice",
        "min_surplus_w": 800,
        "auto_start": false
      }
    }
  },

  "power_guard": {
    "enabled": true,
    "power_sensor": "sensor.consumo_casa_w",
    "threshold_w": 3000,
    "warning_pct": 90,
    "mode": "ask",
    "delay_minutes": 1,
    "appliances_priority": [
      {"name": "Lavatrice",     "switch": "switch.presa_lavatrice"},
      {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie"}
    ]
  },

  "quiet_hours": {
    "enabled": true,
    "start": 23,
    "end": 7
  }
}
```

---

## Configurazione COMPLETA

Tutte le opzioni disponibili. Rimuovi le sezioni che non usi.

```json
{
  "language": "it",
  "timezone": "Europe/Rome",

  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.tablet_finto", "person.mqtt_finto"],
  "motion_whitelist": [
    "binary_sensor.sensore_ingresso_occupancy",
    "binary_sensor.sensore_soggiorno_occupancy",
    "binary_sensor.sensore_cucina_occupancy"
  ],
  "motion_blacklist": ["binary_sensor.sensore_cellulare_mario"],
  "contact_blacklist": ["binary_sensor.porta_garage_contact"],

  "temperature_sensors": [
    "sensor.temp_soggiorno",
    "sensor.temp_camera",
    "sensor.temp_cucina",
    "sensor.temp_esterna"
  ],
  "humidity_sensors": [
    "sensor.umidita_soggiorno",
    "sensor.umidita_bagno"
  ],

  "alarm_panel": "alarm_control_panel.risco_casa",
  "alarm_extra_panels": [
    "alarm_control_panel.paradox_partizione_2",
    "alarm_control_panel.paradox_partizione_3"
  ],
  "alarm_extra_delay": 2,
  "alarm_auto_arm": "notify",
  "alarm_arm_mode": "armed_away",

  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.mario_sm_s24_distance",
      "threshold_m": 100,
      "stale_check": false
    },
    "person.lucia": {
      "sensor": "sensor.lucia_iphone_distance",
      "threshold_m": 150,
      "stale_check": false
    }
  },

  "energy_sensors": {
    "produzione_fv": "sensor.fv_tot",
    "consumo_casa":  "sensor.consumi_giornalieri",
    "rete_enel":     "sensor.enel_giornaliero",
    "batteria_wh":   "sensor.batteria_percentuale"
  },

  "fascia_sensors": {
    "daily_source": "sensor.enel",
    "oggi_f1": "sensor.energia_oggi_f1_f1",
    "oggi_f2": "sensor.energia_oggi_f1_f2",
    "oggi_f3": "sensor.energia_oggi_f1_f3",
    "oggi_tot": "sensor.energia_oggi_totale",
    "mese_f1": "sensor.energia_mese_f1_f1",
    "mese_f2": "sensor.energia_mese_f1_f2",
    "mese_f3": "sensor.energia_mese_f1_f3",
    "mese_tot": "sensor.energia_mese_totale"
  },

  "climate": {
    "climate.termostato": {
      "name": "Termostato casa",
      "switch": "switch.caldaia",
      "min_temp": 15,
      "max_temp": 30
    },
    "climate.sala_clima": {
      "name": "Clima Sala",
      "type": "smartir"
    }
  },
  "climate_auto_off": true,
  "climate_exclude": [
    "climate.valvola_cucina",
    "climate.valvola_camera",
    "climate.valvola_bagno"
  ],

  "appliances": {
    "lavatrice": {
      "enabled": true, "name": "Lavatrice", "icon": "🫧",
      "mode": "power",
      "power_sensor": "sensor.presa_lavatrice_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5,
      "notify_on_start": false
    },
    "lavastoviglie": {
      "enabled": true, "name": "Lavastoviglie", "icon": "🍽️",
      "mode": "smart",
      "state_sensor": "sensor.lavastoviglie_operation_state",
      "running_states": ["Run"],
      "done_states": ["Finished", "Ready"],
      "notify_on_start": false
    },
    "asciugatrice": {
      "enabled": false, "name": "Asciugatrice", "icon": "🌀",
      "mode": "power",
      "power_sensor": "sensor.presa_asciugatrice_power",
      "power_on_threshold": 100, "power_off_threshold": 10,
      "min_cycle_minutes": 30, "max_idle_minutes": 5
    }
  },

  "solar_optimizer": {
    "enabled": true,
    "min_surplus_w": 500,
    "battery_soc_sensor": "sensor.batteria_percentuale",
    "battery_full_threshold": 95,
    "battery_full_min_fv_w": 300,
    "min_sun_elevation": 10,
    "confirm_minutes": 5,
    "cooldown_hours": 2,
    "appliances": {
      "lavatrice": {
        "enabled": true,
        "switch": "switch.presa_lavatrice",
        "min_surplus_w": 800,
        "auto_start": false
      }
    }
  },

  "power_guard": {
    "enabled": true,
    "power_sensor": "sensor.consumo_casa_w",
    "threshold_w": 3000,
    "warning_pct": 90,
    "mode": "ask",
    "delay_minutes": 1,
    "appliances_priority": [
      {"name": "Lavatrice",     "switch": "switch.presa_lavatrice"},
      {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie"},
      {"name": "Scaldabagno",   "switch": "switch.presa_scaldabagno"}
    ]
  },

  "frigate": {
    "enabled": true,
    "host": "192.168.1.100",
    "port": 5000,
    "snapshot_on_alarm": true,
    "cameras": {
      "ingresso": "binary_sensor.sensore_ingresso_occupancy",
      "giardino": "binary_sensor.sensore_giardino_occupancy"
    }
  },

  "quiet_hours": {
    "enabled": true,
    "start": 23,
    "end": 7
  },

  "spazzatura_notify_enabled": true,
  "spazzatura_notify_hour": 20,

  "location_tracker": {
    "mario":    "device_tracker.sm_s931b",
    "lucia":    "device_tracker.sm_a166b"
  },

  "custom_briefing": {
    "briefing_hour": 7,
    "tip_mode": "sports",
    "weather_city": "Roma",
    "custom_greeting": "Buongiorno! ☀️",
    "exclude_sections": []
  },

  "ai_providers": [
    {"name": "gemini",   "model": "gemini-2.0-flash",        "api_key": "AIzaSy..."},
    {"name": "groq",     "model": "llama-3.3-70b-versatile",  "api_key": "gsk_..."},
    {"name": "cerebras", "model": "llama3.1-8b",              "api_key": "csk_..."}
  ]
}
```

---

## Allarme — tutte le opzioni 🔒

### Trovare l'entity_id del tuo allarme

```
HA → Strumenti Sviluppo → Stati → cerca "alarm_control_panel"
```

### Configurazione semplice

```json
"alarm_panel": "alarm_control_panel.home_alarm"
```

### Configurazione con modalità di armamento

```json
"alarm_panel": {
  "entity": "alarm_control_panel.risco_casa",
  "arm_mode": "armed_away"
}
```

### alarm_auto_arm — come si comporta HomeMind quando tutti escono

```json
"alarm_auto_arm": "notify"
```

| Valore | Comportamento |
|--------|---------------|
| `"auto"` | **(default)** HomeMind arma l'allarme automaticamente, senza chiedere |
| `"notify"` | Manda un messaggio Telegram con bottoni **✅ Sì, arma** / **❌ No** prima di armare. Se non rispondi entro 5 minuti, non arma |
| `"disabled"` | HomeMind non tocca mai l'allarme. Spegne solo luci e clima |

**Esempio messaggio che ricevi con modalità `notify`:**
```
🏠 Casa vuota — 19:32
Fuori: Mario, Lucia

Vuoi attivare l'antifurto?

[✅ Sì, attiva antifurto]  [❌ No, lascia disarmato]
```

### alarm_arm_mode — modalità di armamento

```json
"alarm_arm_mode": "armed_away"
```

| Valore | Quando usarlo |
|--------|---------------|
| `armed_away` | Tutti fuori — perimetrale + volumetrico **(default)** |
| `armed_home` | Qualcuno in casa — solo perimetrale |
| `armed_night` | Modalità notte |
| `armed_vacation` | Vacanza |

### Multi-partizione (Paradox, DSC, ecc.)

```json
"alarm_panel": "alarm_control_panel.partizione_principale",
"alarm_extra_panels": [
  "alarm_control_panel.partizione_garage",
  "alarm_control_panel.partizione_esterno"
]
```

HomeMind usa la partizione **principale** per leggere lo stato. Le **extra** vengono armate tutte insieme quando tutti escono.

---

## Clima e Riscaldamento ❄️🔥

### Termostato standard con caldaia

```json
"climate": {
  "climate.termostato_principale": {
    "name": "Termostato casa",
    "switch": "switch.caldaia",
    "min_temp": 15,
    "max_temp": 30
  }
}
```

### Climatizzatori SmartIR

```json
"climate": {
  "climate.sala_clima": {
    "name": "Clima Sala",
    "type": "smartir"
  }
}
```

### Comportamento all'uscita

Le valvole termostatiche (Netatmo, TRV) non supportano `turn_off` → errori 500. 

**Disabilita completamente:**
```json
"climate_auto_off": false
```

**Escludi solo le valvole problematiche:**
```json
"climate_auto_off": true,
"climate_exclude": ["climate.valvola_cucina", "climate.valvola_camera"]
```

---

## Do Not Disturb — Ore di silenzio 🔕

Blocca notifiche non critiche di notte. **Gli allarmi di sicurezza passano sempre.**

```json
"quiet_hours": {
  "enabled": true,
  "start": 23,
  "end": 7
}
```

**Via Telegram:**
```
attiva silenzio notturno 23 7
disattiva silenzio
```

| 🔕 Bloccato | ✅ Passa sempre |
|-------------|----------------|
| Lavatrice finita · Surplus solare · Spazzatura | Allarme scattato · Intrusione |
| Power Guard soglia · Briefing (se in orario DND) | Casa vuota · Qualcuno rientra |

---

## Filtri sensori Temperatura e Umidità 🌡️💧

Scegli quali sensori HomeMind usa per briefing, risposte AI e stato casa. Senza configurazione usa tutti i sensori rilevati automaticamente.

```json
"temperature_sensors": [
  "sensor.temp_soggiorno",
  "sensor.temp_camera",
  "sensor.temp_cucina",
  "sensor.temperatura_esterna"
]
```

```json
"humidity_sensors": [
  "sensor.umidita_soggiorno",
  "sensor.umidita_bagno"
]
```

Configurabili anche dalla **pagina web** dell'addon (tab 🌡️ Temp/Umid).

---

## Proximity GPS 📍

Permette a HomeMind di sapere quando una persona si avvicina a casa — più preciso del semplice `home/not_home` di HA, evita falsi armamenti.

```json
"proximity_sensors": {
  "person.mario": {
    "sensor": "sensor.mario_sm_s24_distance",
    "threshold_m": 100,
    "stale_check": false,
    "stale_minutes": 10
  }
}
```

| Campo | Significato |
|-------|-------------|
| `sensor` | Sensore distanza creato dalla Companion App |
| `threshold_m` | Metri sotto cui sei "vicino a casa" — se sei sotto soglia HomeMind non arma |
| `stale_check` | `false` = usa sempre il dato GPS anche se vecchio (consigliato); `true` = ignora dati più vecchi di `stale_minutes` |

---

## Monitor Elettrodomestici ⚡

### Modalità POWER — presa smart con sensore di potenza

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

| Campo | Significato |
|-------|-------------|
| `power_on_threshold` | Watt sopra cui il ciclo è "in corso" |
| `power_off_threshold` | Watt sotto cui il ciclo è "finito" |
| `min_cycle_minutes` | Durata minima ciclo — evita falsi positivi |
| `max_idle_minutes` | Minuti di basso consumo prima di confermare fine |
| `notify_on_start` | `true` = notifica anche all'accensione |

### Modalità SMART — elettrodomestici connessi (Home Connect)

```json
"lavastoviglie": {
  "enabled": true, "name": "Lavastoviglie", "icon": "🍽️",
  "mode": "smart",
  "state_sensor": "sensor.lavastoviglie_operation_state",
  "running_states": ["Run"],
  "done_states": ["Finished", "Ready"],
  "program_sensor": "sensor.lavastoviglie_selected_program",
  "door_sensor": "binary_sensor.lavastoviglie_door"
}
```

---

## Ottimizzatore Solare ☀️

```json
"solar_optimizer": {
  "enabled": true,
  "min_surplus_w": 500,
  "battery_soc_sensor": "sensor.inverter_battery_capacity_percent",
  "battery_full_threshold": 95,
  "battery_full_min_fv_w": 300,
  "min_sun_elevation": 10,
  "confirm_minutes": 5,
  "cooldown_hours": 2,
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

| Campo | Significato |
|-------|-------------|
| `min_surplus_w` | Surplus minimo (W) per notificare |
| `battery_soc_sensor` | Sensore percentuale batteria |
| `battery_full_threshold` | % sopra cui la batteria è "piena" |
| `battery_full_min_fv_w` | FV minimo quando batteria piena — filtra notifiche notturne |
| `min_sun_elevation` | Elevazione solare minima in gradi |
| `confirm_minutes` | Minuti di surplus stabile prima di notificare |
| `cooldown_hours` | Ore di attesa tra due notifiche consecutive |
| `auto_start` | `true` = accende automaticamente; `false` = chiede conferma |

---

## Power Guard ⚠️

```json
"power_guard": {
  "enabled": true,
  "power_sensor": "sensor.consumo_casa_w",
  "threshold_w": 3000,
  "warning_pct": 90,
  "mode": "ask",
  "delay_minutes": 1,
  "appliances_priority": [
    {"name": "Lavatrice",     "switch": "switch.presa_lavatrice"},
    {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie"}
  ]
}
```

| Campo | Significato |
|-------|-------------|
| `threshold_w` | Soglia contrattuale in Watt |
| `warning_pct` | % della soglia per avviso preventivo (90 = avvisa a 2700W su 3000W) |
| `delay_minutes` | Minuti sopra soglia prima di intervenire |
| `mode` | `warn_only` = solo avviso · `ask` = chiede conferma · `auto` = spegne automaticamente |

---

## Telecamere Frigate 📷

Richiede [Frigate NVR](https://frigate.video/) installato sulla rete locale.

```json
"frigate": {
  "enabled": true,
  "host": "192.168.1.100",
  "port": 5000,
  "snapshot_on_alarm": true,
  "cameras": {
    "ingresso": "binary_sensor.sensore_ingresso_occupancy",
    "giardino": "binary_sensor.sensore_giardino_occupancy"
  }
}
```

| Campo | Significato |
|-------|-------------|
| `host` | IP di Frigate sulla rete locale |
| `port` | Porta HTTP di Frigate (default 5000) |
| `snapshot_on_alarm` | `true` = snapshot automatico su Telegram quando scatta l'allarme |
| `cameras` | Nome camera → sensore movimento HA associato |

---

## Fascia Oraria F1/F2/F3 📊

### Passo 1 — Crea utility_meter in HA (configuration.yaml)

```yaml
utility_meter:
  energia_oggi_f1:
    source: sensor.enel_giorno
    cycle: daily
    tariffs: [F1, F2, F3]
  energia_mese_f1:
    source: sensor.enel_giorno
    cycle: monthly
    tariffs: [F1, F2, F3]
  energia_oggi_totale:
    source: sensor.enel_giorno
    cycle: daily
  energia_mese_totale:
    source: sensor.enel_giorno
    cycle: monthly
```

### Passo 2 — Configura HomeMind

```json
"fascia_sensors": {
  "daily_source": "sensor.enel",
  "oggi_f1": "sensor.energia_oggi_f1_f1",
  "oggi_f2": "sensor.energia_oggi_f1_f2",
  "oggi_f3": "sensor.energia_oggi_f1_f3",
  "oggi_tot": "sensor.energia_oggi_totale",
  "mese_f1": "sensor.energia_mese_f1_f1",
  "mese_f2": "sensor.energia_mese_f1_f2",
  "mese_f3": "sensor.energia_mese_f1_f3",
  "mese_tot": "sensor.energia_mese_totale"
}
```

**Comandi:** `consumi fascia oggi` · `consumi fascia questo mese` · `consumi fascia 10 giorni`

---

## Alias / Comandi Rapidi 🔗

Comandi **garantiti**: HomeMind li esegue direttamente senza AI, sempre e anche offline.

```
memorizza che batteria fotovoltaico = sensor.inverter_battery_capacity_percent
memorizza che info energia = /energia
memorizza che info batteria = sensor.batteria_pct, sensor.batteria_corrente, sensor.batteria_tensione
/alias                              → vedi tutti
dimentica alias 2                   → rimuovi per numero
cancella tutti gli alias            → reset completo
```

---

## Briefing Mattutino 🌅

```json
"custom_briefing": {
  "briefing_hour": 7,
  "tip_mode": "sports",
  "weather_city": "Roma",
  "custom_greeting": "Buongiorno! ☀️",
  "exclude_sections": []
}
```

| `tip_mode` | Contenuto |
|------------|-----------|
| `tip` | Consiglio AI del giorno |
| `news` | Notizie ANSA |
| `sports` | Notizie sportive ANSA |
| `disabled` | Nessun consiglio |

**Via Telegram:** `Briefing alle 8` · `Saluto briefing Buongiorno! ☀️` · `Imposta meteo briefing Roma` · `Ripristina briefing`

---

## Comandi Telegram 📱

| Comando | Descrizione |
|---------|-------------|
| `/stato` | Stato completo: persone, allarme, temperature, tapparelle |
| `/briefing` | Briefing mattutino adesso |
| `/energia` | Produzione FV e consumi oggi |
| `/ieri` | Energia di ieri |
| `/solare` | Surplus FV e ottimizzatore |
| `/elettrodomestici` | Stato di tutti gli elettrodomestici |
| `/routine` | Routine appresa |
| `/automazioni` | Lista automazioni HA |
| `/powerguard` / `/pg` | Stato Power Guard |
| `/task` | Lista task programmati |
| `/cancella_task N` | Cancella task numero N |
| `/config` | Configurazione attuale |
| `/alias` | Comandi rapidi personalizzati |
| `/memoria` | Cosa HomeMind sa su di te |
| `/dimentica <testo>` | Rimuovi un fatto |
| `/memoria reset` | Cancella tutta la memoria |
| `/spazzatura` | Raccolta prossimi 7 giorni |
| `/providers` | Provider AI attivi e stato fallback |
| `/readme` | Manuale interattivo |
| `/readme <argomento>` | Cerca nel manuale (es. `/readme proximity`) |
| `/lingua it` / `/lingua en` | Cambia lingua |
| `/comandi` | Questa lista completa |

---

## FAQ ❓

**L'allarme si arma mentre sono ancora in casa** → Configura `proximity_sensors` con il sensore distanza dalla Companion App.

**Voglio la notifica di conferma prima di armare** → Imposta `"alarm_auto_arm": "notify"` nel config. Ricevi un messaggio Telegram con bottoni ✅/❌.

**HomeMind non controlla il mio allarme** → Aggiungi `alarm_panel` con l'entity_id corretto (HA → Strumenti Sviluppo → cerca `alarm_control_panel.`).

**Il messaggio di benvenuto non arriva** → Abbassa `threshold_m` a 50. Verifica che la Companion App aggiorni il sensore distanza in background.

**I termostati si spengono quando esco** → `"climate_auto_off": false` o aggiungi le valvole a `climate_exclude`.

**Errore 500 sul clima** → Le valvole TRV (Netatmo, ecc.) non supportano `turn_off`. Aggiungile a `climate_exclude`.

**L'antifurto Paradox arma solo 1 partizione** → Usa `alarm_extra_panels` con le entity_id delle altre partizioni.

**HomeMind risponde solo la prima volta poi va in errore** → Groq Free ha limite token/min. Configura Cerebras (gratuito, 1M token/min) come fallback.

**SmartIR — errori 400** → Aggiungi `"type": "smartir"` nel blocco climate.

**Docker — HomeMind non si connette a HA** → Usa `http://host.docker.internal:8123` se HA gira sullo stesso host.

---

# 🇬🇧 English

## What is HomeMind

HomeMind is a **Home Assistant add-on** that adds an AI brain to your home. It understands context, learns your routine and alerts you only when it truly matters.

**Talk to it on Telegram in natural language** — or send a voice message 🎙️.

### What it does automatically

| Feature | Description |
|---------|-------------|
| 🔒 **Automatic alarm** | Arms when everyone leaves, disarms when you return — 3 modes: `auto`, `notify`, `disabled` |
| 🔔 **Alarm confirmation** | With `alarm_auto_arm: notify`, sends Telegram message with ✅/❌ buttons before arming |
| 👋 **Welcome home** | Telegram message when you arrive |
| 📷 **Camera snapshots** | Auto photo on Telegram when alarm triggers |
| ⚡ **Appliance monitor** | Notifies when washer/dishwasher finish |
| ☀️ **Solar optimizer** | Alerts when to use FV surplus |
| 🔕 **Do Not Disturb** | Blocks non-critical notifications at night |
| 🌡️ **Temperature/humidity filters** | Choose exactly which sensors HomeMind uses |
| 📍 **Proximity GPS** | Detects arrival/departure with configurable meter threshold |
| 🔗 **Quick command aliases** | Custom keywords → guaranteed actions, even offline |
| 🔌 **Offline mode** | Lights, blinds, alarm work even without AI |
| ⚠️ **Power Guard** | Protects against contract power threshold — 3 modes |
| 🤖 **Multi-AI fallback** | 7 AI providers with automatic cascade switching |
| 📖 **Interactive manual** | `/readme <question>` searches the manual from Telegram |

---

## Installation

**HAOS Addon:**
```
HA → Add-on Store → Add repository: https://github.com/ago19800/HomeMind
→ Install "HomeMind Orchestrator" → Configure → Start
```

**Docker:**
```bash
mkdir ~/homemind && cd ~/homemind
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/docker-compose.yml
cp .env.example .env && nano .env && docker-compose up -d
```

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
  "person_blacklist": ["person.fake_tablet"],
  "motion_whitelist": ["binary_sensor.entrance_sensor_occupancy"],

  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.mario_pixel_distance",
      "threshold_m": 100,
      "stale_check": false
    }
  },

  "temperature_sensors": ["sensor.temp_living", "sensor.temp_outdoor"],
  "humidity_sensors": ["sensor.humidity_living"],

  "appliances": {
    "washer": {
      "enabled": true, "name": "Washer", "icon": "🫧",
      "mode": "power",
      "power_sensor": "sensor.washer_plug_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5
    }
  },

  "quiet_hours": {"enabled": true, "start": 23, "end": 7}
}
```

---

## ADVANCED Configuration

```json
{
  "language": "en",
  "person_whitelist": ["person.mario", "person.lucia"],
  "motion_whitelist": ["binary_sensor.entrance_sensor_occupancy"],

  "temperature_sensors": ["sensor.temp_living", "sensor.temp_outdoor"],
  "humidity_sensors": ["sensor.humidity_living", "sensor.humidity_bathroom"],

  "alarm_panel": "alarm_control_panel.risco_home",
  "alarm_auto_arm": "notify",
  "alarm_arm_mode": "armed_away",

  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.mario_pixel_distance",
      "threshold_m": 100,
      "stale_check": false
    }
  },

  "climate": {
    "climate.main_thermostat": {
      "name": "Home thermostat", "switch": "switch.boiler",
      "min_temp": 15, "max_temp": 30
    }
  },
  "climate_auto_off": true,
  "climate_exclude": [],

  "power_guard": {
    "enabled": true,
    "power_sensor": "sensor.home_power_w",
    "threshold_w": 3000, "warning_pct": 90, "mode": "ask",
    "appliances_priority": [
      {"name": "Washer", "switch": "switch.washer_plug"}
    ]
  },

  "quiet_hours": {"enabled": true, "start": 23, "end": 7}
}
```

---

## FULL Configuration

```json
{
  "language": "en",
  "timezone": "Europe/London",

  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.fake_tablet"],
  "motion_whitelist": ["binary_sensor.entrance_sensor_occupancy"],
  "contact_blacklist": ["binary_sensor.garage_door_contact"],

  "temperature_sensors": ["sensor.temp_living", "sensor.temp_outdoor"],
  "humidity_sensors": ["sensor.humidity_living", "sensor.humidity_bathroom"],

  "alarm_panel": "alarm_control_panel.risco_home",
  "alarm_extra_panels": [
    "alarm_control_panel.paradox_partition_2",
    "alarm_control_panel.paradox_partition_3"
  ],
  "alarm_auto_arm": "notify",
  "alarm_arm_mode": "armed_away",

  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.mario_pixel_distance",
      "threshold_m": 100,
      "stale_check": false
    },
    "person.lucia": {
      "sensor": "sensor.lucia_iphone_distance",
      "threshold_m": 150,
      "stale_check": false
    }
  },

  "energy_sensors": {
    "produzione_fv": "sensor.solar_total",
    "consumo_casa":  "sensor.daily_consumption",
    "rete_enel":     "sensor.grid_daily",
    "batteria_wh":   "sensor.battery_percentage"
  },

  "climate": {
    "climate.main_thermostat": {
      "name": "Home thermostat", "switch": "switch.boiler",
      "min_temp": 15, "max_temp": 30
    }
  },
  "climate_auto_off": true,
  "climate_exclude": ["climate.trv_kitchen", "climate.trv_bedroom"],

  "appliances": {
    "washer": {
      "enabled": true, "name": "Washer", "icon": "🫧",
      "mode": "power",
      "power_sensor": "sensor.washer_plug_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5
    },
    "dishwasher": {
      "enabled": true, "name": "Dishwasher", "icon": "🍽️",
      "mode": "smart",
      "state_sensor": "sensor.dishwasher_operation_state",
      "running_states": ["Run"],
      "done_states": ["Finished", "Ready"]
    }
  },

  "solar_optimizer": {
    "enabled": true,
    "min_surplus_w": 500,
    "battery_soc_sensor": "sensor.battery_percentage",
    "battery_full_threshold": 95,
    "min_sun_elevation": 10,
    "confirm_minutes": 5,
    "cooldown_hours": 2
  },

  "power_guard": {
    "enabled": true,
    "power_sensor": "sensor.home_power_w",
    "threshold_w": 3000, "warning_pct": 90, "mode": "ask",
    "appliances_priority": [
      {"name": "Washer",     "switch": "switch.washer_plug"},
      {"name": "Dishwasher", "switch": "switch.dishwasher_plug"}
    ]
  },

  "frigate": {
    "enabled": true, "host": "192.168.1.100", "port": 5000,
    "snapshot_on_alarm": true,
    "cameras": {"entrance": "binary_sensor.entrance_sensor_occupancy"}
  },

  "quiet_hours": {"enabled": true, "start": 23, "end": 7},

  "location_tracker": {
    "mario": "device_tracker.pixel_7",
    "lucia": "device_tracker.iphone_lucia"
  },

  "ai_providers": [
    {"name": "gemini",   "model": "gemini-2.0-flash",        "api_key": "AIzaSy..."},
    {"name": "groq",     "model": "llama-3.3-70b-versatile",  "api_key": "gsk_..."},
    {"name": "cerebras", "model": "llama3.1-8b",              "api_key": "csk_..."}
  ]
}
```

---

## Alarm — all options 🔒

```json
"alarm_panel": "alarm_control_panel.home_alarm",
"alarm_auto_arm": "notify",
"alarm_arm_mode": "armed_away"
```

| `alarm_auto_arm` | Behavior |
|-----------------|----------|
| `"auto"` | **(default)** Arms automatically when everyone leaves |
| `"notify"` | Sends Telegram message with ✅/❌ buttons before arming. No response in 5 min → does not arm |
| `"disabled"` | Never touches the alarm. Only turns off lights and climate |

**Multi-partition:**
```json
"alarm_panel": "alarm_control_panel.main_partition",
"alarm_extra_panels": [
  "alarm_control_panel.garage_partition",
  "alarm_control_panel.exterior_partition"
]
```

---

## Telegram Commands 📱

| Command | Description |
|---------|-------------|
| `/stato` | Full status |
| `/briefing` | Morning briefing now |
| `/energia` | Solar and consumption today |
| `/ieri` | Yesterday's energy |
| `/solare` | Solar surplus |
| `/elettrodomestici` | All appliance status |
| `/powerguard` | Power Guard status |
| `/task` | Scheduled tasks |
| `/config` | Current configuration |
| `/alias` | Custom quick commands |
| `/memory` | What HomeMind knows about you |
| `/providers` | Active AI providers |
| `/readme` | Interactive manual |
| `/readme <topic>` | Search in manual |
| `/comandi` | Full command list |

---

## FAQ ❓

**Alarm arms while I'm still home** → Configure `proximity_sensors` with your distance sensor.

**I want confirmation before arming** → Set `"alarm_auto_arm": "notify"`.

**Paradox alarm only arms 1 partition** → Use `alarm_extra_panels`.

**Thermostats turn off when I leave** → `"climate_auto_off": false` or use `climate_exclude`.

**TRV 500 errors** → Add them to `climate_exclude`.

**Rate limit errors** → Configure Cerebras as additional free fallback (1M token/min).

---

<div align="center">

**HomeMind Orchestrator** — *La tua casa, finalmente intelligente. / Your home, finally intelligent.*

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

[🔝 Torna su / Back to top](#-homemind-orchestrator)

</div>
