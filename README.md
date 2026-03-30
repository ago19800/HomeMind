<div align="center">

# 🧠 HomeMind Orchestrator

**[🇮🇹 Italiano](#-italiano) · [🇬🇧 English](#-english)**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![Language](https://img.shields.io/badge/Lingua-Italiano%20%2F%20English-green)]()
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Groq%20%7C%20Cerebras%20%7C%20DeepSeek%20%7C%20Mistral%20%7C%20Claude%20%7C%20OpenAI-orange)]()
[![Version](https://img.shields.io/badge/versione-1.4.6-brightgreen)](https://github.com/ago19800/HomeMind/releases)

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
  <img src="https://raw.githubusercontent.com/ago19800/HomeMind/main/images/Screenshot_20260319_123729_Home Assistant.jpg" width="260">
</p>

---

# 🇮🇹 Italiano

> 🇬🇧 Looking for the English version? [Click here](#-english)

## 📋 Indice

- [Cos'è HomeMind](#cosè-homemind)
- [🆕 Novità v1.4.5](#-novità-v145)
- [Installazione Addon HAOS](#installazione-addon-haos)
- [🐳 Installazione Docker](#-installazione-docker)
- [Configurazione Addon](#configurazione-addon-it)
- [Provider AI e Fallback automatico](#provider-ai-e-fallback-automatico-)
- [Geolocalizzazione GPS](#geolocalizzazione-gps-)
- [Configurazione BASE](#configurazione-base)
- [Configurazione MEDIA](#configurazione-media)
- [Configurazione AVANZATA](#configurazione-avanzata)
- [Configurazione COMPLETA](#configurazione-completa)
- [Allarme Personalizzato + Multi-Partizione](#allarme-personalizzato--multi-partizione-)
- [Clima e Riscaldamento](#clima-e-riscaldamento-)
- [Do Not Disturb — Ore di silenzio](#do-not-disturb--ore-di-silenzio-)
- [Alias / Comandi Rapidi](#alias--comandi-rapidi-)
- [Modalità Offline](#modalità-offline-)
- [Tapparelle e Tende](#tapparelle-e-tende-)
- [Memoria Persistente](#memoria-persistente)
- [Briefing Mattutino](#briefing-mattutino-personalizzabile-)
- [Meteo Esterno](#meteo-esterno-)
- [Elettrodomestici](#monitor-elettrodomestici-)
- [Ottimizzatore Solare](#ottimizzatore-solare-)
- [Power Guard](#power-guard-)
- [Task Programmati](#task-programmati-)
- [Configurazione via Chat](#configurazione-via-chat-)
- [Routine Intelligente](#routine-intelligente-)
- [Gestione Automazioni](#gestione-automazioni-)
- [Analisi Log e Auto-Fix](#analisi-log-e-auto-fix-)
- [Dashboard Lovelace AI](#dashboard-lovelace-ai-)
- [Telecamere Frigate](#telecamere-frigate-)
- [Comandi Telegram](#comandi-telegram-)
- [Interfaccia Vocale](#interfaccia-vocale-)
- [FAQ](#faq-)
- [Changelog](#changelog)

---

## Cos'è HomeMind

HomeMind è un **add-on per Home Assistant** che aggiunge un cervello AI alla tua casa. Non è una semplice automazione — è un agente che capisce il contesto, impara la tua routine e ti avvisa solo quando serve davvero.

**Parlagli su Telegram in italiano naturale:**

> *"Accendi la luce del salotto"*
> *"Quanta energia ho prodotto oggi?"*
> *"Apri le tapparelle del salone al 70%"*
> *"Attiva silenzio notturno dalle 23 alle 7"*
> *"Memorizza che batteria solare = sensor.inverter_battery_pct"*
> *"Aggiungi temperatura cucina al briefing"*

Puoi anche mandargli un **messaggio vocale** 🎙️ — trascrive la voce e la tratta come un comando normale.

### Cosa fa in automatico

| Funzione | Descrizione |
|----------|-------------|
| 🔒 **Allarme automatico** | Arma quando tutti escono, disarma quando torni |
| 👋 **Benvenuto a casa** | Messaggio su Telegram quando rientri |
| 📷 **Snapshot telecamere** | Foto automatica su Telegram quando scatta l'allarme |
| ⚡ **Monitor elettrodomestici** | Notifica quando lavatrice/lavastoviglie finiscono |
| ☀️ **Ottimizzatore solare** | Ti avvisa quando usare il surplus FV |
| 🔕 **Do Not Disturb** | Blocca notifiche non critiche nelle ore notturne |
| 🔗 **Alias comandi rapidi** | Parole chiave personalizzate → azioni garantite senza AI |
| 🔌 **Modalità offline** | Comandi base funzionano anche senza AI |
| 📊 **Analisi energia** | Ogni mattina confronta i consumi con la media storica |
| 🌅 **Briefing mattutino** | Personalizzabile via Telegram: aggiungi sensori, orario, sezioni |
| 🌤️ **Meteo esterno** | Previsioni 3 giorni via open-meteo.com — nessuna API key |
| 🗑️ **Spazzatura** | La sera prima ricorda cosa mettere fuori |
| 🧠 **Memoria persistente** | Impara le tue preferenze nel tempo |
| 📅 **Routine intelligente** | Anticipa i tuoi bisogni in base alle abitudini reali |
| ⚠️ **Power Guard** | Protegge dalla soglia contrattuale Enel |
| ⏰ **Task programmati** | Schedula azioni future in linguaggio naturale |
| ⚙️ **Config via chat** | Modifica la configurazione scrivendo su Telegram |
| 🤖 **Multi-AI con fallback** | 7 provider AI con cambio automatico se uno è offline |
| 🔧 **Automazioni da Telegram** | Crea, modifica ed elimina automazioni HA via chat |
| 🩺 **Analisi Log AI** | Legge i log HA, trova errori e propone fix |
| 🎨 **Dashboard Lovelace AI** | Genera dashboard Lovelace su misura |

---

## 🆕 Novità v1.4.5

| Funzione | Descrizione |
|----------|-------------|
| 🔕 **Do Not Disturb (DND)** | Blocca notifiche non critiche nelle ore notturne. Configurabile dal config o via Telegram |
| 🔗 **Alias / Comandi Rapidi** | Parole chiave personalizzate che eseguono azioni **garantite** senza AI, anche offline |
| 📊 **Multi-sensore negli alias** | Un alias può leggere più sensori contemporaneamente (separati da virgola) |
| 🔌 **Modalità Offline** | Se tutti i provider AI falliscono, i comandi base (luci, tapparelle, allarme) funzionano comunque tramite parser locale |
| 🪟 **Fix tapparelle** | HomeMind legge ora `current_position` reale (0–100%) invece dello `state` HA che può essere impreciso |
| 🧠 **Memoria senza conflitti** | Se dici "preferisco 21°C" e poi "preferisco 22°C", HomeMind aggiorna invece di duplicare |
| 🕐 **Briefing dinamico** | Cambio orario via Telegram attivo entro 5 minuti, senza riavviare |
| ❄️ **Clima auto-off configurabile** | Scegli se e quali termostati spegnere quando tutti escono. Nuova opzione `climate_exclude` per le valvole che non supportano `turn_off` (es. Netatmo) |
| 🔒 **Multi-partizione allarme** | Supporto antifurti con più partizioni (Paradox, DSC, ecc.) tramite `alarm_extra_panels` |

---

## Installazione Addon HAOS

> Per **Home Assistant OS** o **Home Assistant Supervised**

```
1. HA → Impostazioni → Add-on Store → ⋮ → Repository
   → Incolla: https://github.com/ago19800/HomeMind → Aggiungi

2. Cerca "HomeMind Orchestrator" → Installa

3. Scheda Configurazione → inserisci i tuoi dati → Salva → Avvia
```

---

## 🐳 Installazione Docker

> Per **Home Assistant Core**, **HA Container**, **Unraid**, **NAS Synology/QNAP** o qualsiasi sistema con Docker.

### Cosa ti serve

- ✅ Docker e Docker Compose installati
- ✅ Home Assistant raggiungibile via rete (es. `http://192.168.1.100:8123`)
- ✅ Un bot Telegram (creato con @BotFather)
- ✅ Almeno una chiave AI gratuita (Gemini o Groq)

### Passo 1 — Scarica i file

```bash
mkdir ~/homemind && cd ~/homemind
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/docker-compose.yml
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/.env.example
cp .env.example .env
nano .env
```

### Passo 2 — Compila il file .env

```env
HA_URL=http://192.168.1.100:8123        ← IP del tuo HA
HA_TOKEN=eyJhbGciOiJ...                 ← Token HA (vedi sotto)
TELEGRAM_TOKEN=1234567890:AABBCCDDee...
TELEGRAM_CHAT_ID=123456789
GEMINI_API_KEY=AIzaSy...                ← GRATIS
GROQ_API_KEY=gsk_...                    ← GRATIS
```

> 💡 **Come ottenere il Token HA:**
> HA → clicca il tuo nome (in basso a sinistra) → **Sicurezza** → **Token di lunga durata** → **Crea token** → copia

### Passo 3 — Avvia e configura

```bash
docker-compose up -d
docker-compose logs -f   # controlla che vedi "HomeMind pronto ✅"
```

Dopo il primo avvio modifica il file di configurazione:
```
~/homemind_data/homemind_patches/person_config.json
```

Poi riavvia per applicare:
```bash
docker-compose restart
```

### Aggiornamento Docker

```bash
docker-compose pull && docker-compose up -d
```

### Confronto Addon vs Docker

| Funzione | Addon HAOS | Docker Standalone |
|----------|-----------|-------------------|
| Installazione | Add-on Store | docker-compose |
| Configurazione | UI grafica | file `.env` |
| person_config.json | `/config/homemind_patches/` | `~/homemind_data/homemind_patches/` |
| Tutte le funzioni AI | ✅ | ✅ |
| Dashboard web | ✅ | ✅ (porta 8099) |
| Aggiornamenti | Add-on Store | `docker-compose pull` |

---

## Configurazione Addon IT

### Telegram (obbligatorio)
```yaml
telegram_bot_token: "TOKEN_DA_BOTFATHER"
telegram_chat_id:   "IL_TUO_CHAT_ID"
alarm_code:         "1234"
```

### OpenAI (solo per messaggi vocali)
```yaml
openai_api_key: "sk-..."
```
> I messaggi vocali usano Whisper di OpenAI — costa circa $0.006 per messaggio da 1 minuto.

---

## Provider AI e Fallback automatico 🤖

HomeMind usa **più provider AI in cascata**. Se il primo non risponde (quota finita, rate limit, offline), passa automaticamente al successivo — tutto in modo trasparente, senza che tu faccia nulla.

### Come funziona il fallback

```
Il tuo messaggio
    ↓
1. Gemini → quota finita o 503? → passa al prossimo
    ↓
2. Groq → rate limit 429? → passa al prossimo
    ↓
3. Cerebras → offline? → passa al prossimo
    ↓
4. DeepSeek / Mistral / Claude / OpenAI → ...
    ↓
5. ⚠️ Tutti falliti → Modalità Offline (parser locale)
```

### Perché si raggiunge il limite

Il provider più comune tra gli utenti è **Groq Free**, che ha un limite di **12.000 token al minuto**. Il contesto di HomeMind (lista di luci, switch, tapparelle, persone...) può pesare 7.000–9.000 token per richiesta. Questo significa che con due messaggi ravvicinati si raggiunge il limite.

**Soluzione:** configura almeno **Gemini + Groq + Cerebras** — sono tutti **gratuiti** e si coprono a vicenda automaticamente. Cerebras ha un limite di 1 milione di token al minuto e raramente va in rate limit.

### Configurazione provider nell'addon

```yaml
gemini_api_key:   "AIzaSy..."       # GRATIS → aistudio.google.com
gemini_model:     "gemini-2.0-flash"

groq_api_key:     "gsk_..."         # GRATIS → console.groq.com
groq_model:       "llama-3.3-70b-versatile"

cerebras_api_key: "csk_..."         # GRATIS → cloud.cerebras.ai
cerebras_model:   "llama3.1-8b"

deepseek_api_key: "sk-..."          # ~GRATIS → platform.deepseek.com
deepseek_model:   "deepseek-chat"

mistral_api_key:  "..."             # GRATIS (tier) → console.mistral.ai
mistral_model:    "mistral-small-latest"

claude_api_key:   "sk-ant-..."      # A PAGAMENTO → console.anthropic.com
claude_model:     "claude-3-5-haiku-20241022"

openai_api_key:   "sk-..."          # A PAGAMENTO (obbligatorio per voce)
openai_model:     "gpt-4o-mini"

ai_provider_order: "gemini,groq,cerebras,deepseek,mistral,claude,openai"
```

### Tabella provider

| Provider | Costo | Limite | Registrazione |
|----------|-------|--------|---------------|
| 🟦 **Gemini** | **Gratis** | 1.500 req/giorno | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ **Groq** | **Gratis** | 12.000 token/min | [console.groq.com](https://console.groq.com) |
| 🧠 **Cerebras** | **Gratis** | 1M token/min ⚡ | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 **DeepSeek** | ~Gratis | $0.014/1M token | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟣 **Mistral** | Gratis (tier) | — | [console.mistral.ai](https://console.mistral.ai) |
| 🟠 **Claude** | A pagamento | — | [console.anthropic.com](https://console.anthropic.com) |
| 🟢 **OpenAI** | A pagamento | $0.006/min audio | [platform.openai.com](https://platform.openai.com) |

> 💡 **Consiglio minimo:** configura **Gemini + Groq + Cerebras** — zero costi e copertura totale.

---

## Geolocalizzazione GPS 📍

La geolocalizzazione permette a HomeMind di sapere quando sei vicino a casa e di gestire l'allarme automaticamente: si arma quando esci, si disarma quando rientri.

### Passo 1 — Installa la Companion App

Installa l'app **Home Assistant** sul tuo telefono:
- Android → [Google Play](https://play.google.com/store/apps/details?id=io.homeassistant.companion.android)
- iOS → [App Store](https://apps.apple.com/app/home-assistant/id1099568401)

Apri l'app, accedi al tuo HA e **concedi i permessi di localizzazione** quando richiesto. Scegli "Sempre" per una copertura completa.

### Passo 2 — Verifica le entità create

Dopo aver configurato la Companion App, HA crea automaticamente:
- `person.nome_tuo` — presenza (home / not_home)
- `sensor.nome_tuo_nome_telefono_distance` — distanza dalla casa in metri

Per trovare i nomi esatti vai in:
**HA → Strumenti Sviluppo → Stati** → cerca `person.` e `sensor.` con il tuo nome

### Passo 3 — Configura person_config.json

```json
{
  "person_whitelist": ["person.mario", "person.lucia"],

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
  }
}
```

| Campo | Significato |
|-------|-------------|
| `sensor` | Entity ID del sensore distanza (dalla Companion App) |
| `threshold_m` | Distanza in metri sotto cui HomeMind ti considera "vicino a casa" |
| `stale_check` | `false` = usa sempre il dato GPS anche se vecchio (consigliato per la maggior parte dei casi) |

### Come funziona nel dettaglio

- Quando **tutte** le persone in whitelist sono `not_home` → HomeMind aspetta 8 secondi (per evitare falsi positivi), poi arma l'allarme, spegne le luci, invia notifica "Casa vuota"
- Quando **qualcuno rientra** → HomeMind disarma l'allarme, invia messaggio di benvenuto
- Se il GPS del telefono non si aggiorna (è stale), con `stale_check: false` HomeMind usa l'ultimo dato noto invece di bloccarsi

> ⚠️ **Problema comune:** il messaggio di benvenuto non arriva → abbassa `threshold_m` a 50 o verifica che la Companion App aggiorni il sensore distanza in background.

## Location Tracker — Dove è stato? 📍🗺️

Il **Location Tracker** è una funzione opzionale che permette di chiedere a HomeMind **dove si è trovata una persona durante le ultime ore**, con indirizzi reali via GPS (OpenStreetMap, gratuito — nessuna API key).

### Differenza rispetto a `proximity_sensors`

| | `proximity_sensors` | `location_tracker` |
|---|---|---|
| **Scopo** | Sapere se la persona è vicino a casa | Sapere dove è stata durante il giorno |
| **Entità usata** | `sensor.nome_distance` | `device_tracker.nome_telefono` |
| **Risposta** | Casa vuota / benvenuto / allarme | Lista soste con indirizzo e durata |
| **Obbligatorio** | Sì (per allarme automatico) | No (opzionale) |

### Come trovare il tuo device_tracker

HA → **Strumenti Sviluppo → Stati** → cerca `device_tracker.`

La Companion App crea automaticamente un `device_tracker` per ogni telefono registrato, solitamente con il nome del modello (es. `device_tracker.sm_s931b`, `device_tracker.iphone_mario`).

### Configurazione in person_config.json

```json
"location_tracker": {
  "agostino": "device_tracker.sm_s931b",
  "rosa":     "device_tracker.sm_a166b"
}
```

Il **nome** (es. `"agostino"`) deve corrispondere a come lo chiami su Telegram. Non serve che coincida esattamente con l'entity_id `person.` — HomeMind fa una ricerca parziale sul nome.

### Come usarlo su Telegram

```
dove è stato Agostino oggi?
dove è stata Rosa nelle ultime 8 ore?
soste di Agostino
percorso di Rosa
dove ha girato Agostino ieri?
```

**Risposta HomeMind:**
```
📍 Soste di Agostino — ultime 24h

🏠 Casa — 7h 23min (partenza 08:15)
🏢 Via Roma 42, Milano — 4h 11min
🛒 Supermercato Esselunga, Viale Brianza — 38min
⛽ Distributore ENI, SP12 — 12min
🏠 Casa — rientro 19:44
```

### Requisiti

- ✅ Companion App installata con permessi di localizzazione su **Sempre**
- ✅ `location_tracker` configurato nel `person_config.json`
- ✅ Il telefono deve aver registrato GPS durante il giorno

> 💡 Se HomeMind risponde "Nessun device_tracker configurato per Agostino", verifica che il nome nel config corrisponda e che l'entity_id del device_tracker sia corretto.


---

## Configurazione BASE

Il minimo indispensabile per far funzionare HomeMind. Sostituisci i nomi con i tuoi entity_id reali.

**Come trovare gli entity_id:** HA → Strumenti Sviluppo → Stati → cerca per nome

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

Aggiunge GPS, elettrodomestici, energia e DND.

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

Aggiunge allarme personalizzato, clima, power guard e ottimizzatore solare.

```json
{
  "language": "it",
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.tablet_finto"],
  "motion_whitelist": ["binary_sensor.sensore_ingresso_occupancy"],

  "temperature_sensors": [
    "sensor.temp_reale_sala",
    "sensor.temp_reale_camera",
    "sensor.temp_reale_cameretta",
    "sensor.temp_reale_studio",
    "sensor.temp_reale_openspace",
    "sensor.temp_reale_camera_mansarda",
    "sensor.temperatura_esterna"
  ],

  "alarm_panel": {
    "entity": "alarm_control_panel.risco_casa",
    "arm_mode": "armed_away"
  },

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
    "rete_enel": "sensor.enel_giornaliero"
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
  },

  "solar_optimizer": {
    "enabled": true,
    "min_surplus_w": 500,
    "battery_soc_sensor": "sensor.batteria_percentuale",
    "battery_full_threshold": 95,
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
      {
        "name": "Lavatrice",
        "switch": "switch.presa_lavatrice"
      },
      {
        "name": "Lavastoviglie",
        "switch": "switch.presa_lavastoviglie"
      }
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

Tutte le opzioni disponibili. Rimuovi o commenta le sezioni che non usi.

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
  "motion_blacklist": [
    "binary_sensor.sensore_cellulare_mario"
  ],
  "contact_blacklist": [
    "binary_sensor.porta_garage_contact"
  ],

  "alarm_panel": {
    "entity": "alarm_control_panel.risco_casa",
    "arm_mode": "armed_away"
  },
  "alarm_extra_panels": [
    "alarm_control_panel.paradox_partizione_2",
    "alarm_control_panel.paradox_partizione_3"
  ],

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
      "min_cycle_minutes": 30, "max_idle_minutes": 5,
      "notify_on_start": false
    }
  },

  "solar_optimizer": {
    "enabled": true,
    "min_surplus_w": 500,
    "battery_soc_sensor": "sensor.batteria_percentuale",
    "battery_full_threshold": 95,
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
  }
}
```

---

## Allarme Personalizzato + Multi-Partizione 🔒

### Come trovare l'entity_id del tuo allarme

```
HA → Strumenti Sviluppo → Stati → cerca "alarm_control_panel"
```

### Configurazione allarme singolo

```json
"alarm_panel": "alarm_control_panel.risco_casa"
```

Oppure con modalità di armamento specifica:

```json
"alarm_panel": {
  "entity": "alarm_control_panel.verisure_casa",
  "arm_mode": "armed_away"
}
```

| `arm_mode` | Quando usarlo |
|------------|---------------|
| `armed_away` | Tutti fuori casa — perimetrale + volumetrico **(default)** |
| `armed_home` | Qualcuno in casa — solo perimetrale |
| `armed_night` | Modalità notte |

### Antifurti multi-partizione (Paradox, DSC, ecc.)

Se il tuo antifurto ha più partizioni (es. "interno", "esterno", "garage"), HomeMind normalmente ne gestisce solo una. Con `alarm_extra_panels` le arma tutte insieme:

```json
"alarm_panel": {
  "entity": "alarm_control_panel.evohd_partition_casa",
  "arm_mode": "armed_away"
},
"alarm_extra_panels": [
  "alarm_control_panel.evohd_partition_esterno",
  "alarm_control_panel.evohd_partition_garage"
]
```

HomeMind usa la partizione **principale** per leggere lo stato e decidere se la casa è vuota. Le partizioni **extra** vengono armate automaticamente insieme, quando tutti escono.

> 💡 Puoi trovare tutti i pannelli allarme disponibili in HA → Strumenti Sviluppo → Stati → cerca `alarm_control_panel.`

---

## Clima e Riscaldamento ❄️🔥

### Termostato standard con caldaia a switch

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

HomeMind rileva automaticamente SmartIR se il dispositivo ha `controller_data` negli attributi. Se ricevi errori 400, forza il tipo manualmente:

```json
"climate": {
  "climate.sala_clima": {
    "name": "Clima Sala",
    "type": "smartir"
  }
}
```

> ⚠️ Con SmartIR **non usare mai** `set_hvac_mode` — HomeMind usa `turn_on`/`turn_off` automaticamente.

### Gestione termostati all'uscita di casa

Per impostazione predefinita, quando tutti escono HomeMind **spegne tutti i termostati** (`climate.turn_off`). Questo comporta problemi con le valvole termostatiche (Netatmo, TRV) che non supportano `turn_off` → errore 500 nei log.

**Opzione 1 — Disabilita completamente lo spegnimento clima:**
```json
"climate_auto_off": false
```

**Opzione 2 — Escludi solo le valvole problematiche:**
```json
"climate_auto_off": true,
"climate_exclude": [
  "climate.valvola_cucina",
  "climate.valvola_camera",
  "climate.valvola_bagno_grande",
  "climate.valvola_bagno_piccolo"
]
```

Le entità in `climate_exclude` non vengono mai toccate da HomeMind.

---

## Do Not Disturb — Ore di silenzio 🔕

Blocca le notifiche non critiche (lavatrice finita, surplus solare, spazzatura, ecc.) durante le ore notturne. **Le notifiche di sicurezza (allarme, intrusione, tutti fuori) passano sempre**, indipendentemente dal DND.

### Configurazione nel person_config.json

```json
"quiet_hours": {
  "enabled": true,
  "start": 23,
  "end": 7
}
```

Questo esempio blocca notifiche dalle **23:00 alle 07:00**.

### Configurazione via Telegram (senza toccare file)

```
attiva silenzio notturno 23 7     ← attiva dalle 23:00 alle 07:00
attiva silenzio notturno 22 8     ← attiva dalle 22:00 alle 08:00
attiva silenzio                   ← usa default 23:00 → 07:00
dnd start 22 end 8                ← formato alternativo

disattiva silenzio
disabilita dnd
disable quiet hours
```

Il cambio via Telegram è immediato — non serve riavviare.

### Cosa viene bloccato / cosa passa sempre

| 🔕 Bloccato dal DND | ✅ Passa sempre |
|---------------------|----------------|
| Lavatrice/lavastoviglie finita | Allarme scattato 🚨 |
| Surplus solare disponibile | Rilevamento intruso |
| Notifica spazzatura | Casa vuota (tutti usciti) |
| Power Guard avviso soglia | Qualcuno rientra |
| Briefing mattutino (se nelle ore DND) | Qualsiasi errore critico |

---

## Alias / Comandi Rapidi 🔗

Gli alias sono **comandi personalizzati garantiti**: HomeMind li esegue direttamente senza passare dall'AI, sempre e anche in modalità offline. Non sono "suggerimenti" per l'AI — sono azioni deterministiche.

### Creare un alias sensore

```
memorizza che batteria fotovoltaico = sensor.inverter_pipsolar_battery_capacity_percent
```

Risposta HomeMind:
```
✅ Alias #1 memorizzato:
  📡 "batteria fotovoltaico" → sensor.inverter_pipsolar_battery_capacity_percent

Scrivi batteria fotovoltaico per eseguirlo.
Per rimuoverlo: dimentica alias 1
```

### Creare un alias per un comando

```
memorizza che info energia = /energia
memorizza quando chiedo fotovoltaico apri /solare
alias stato casa = /stato
```

### Alias con più sensori contemporaneamente

Puoi associare più sensori a una sola parola chiave, separandoli con virgola:

```
memorizza che info batteria = sensor.inverter_pipsolar_battery_capacity_percent, sensor.inverter_pipsolar_battery_discharge_current, sensor.inverter_pipsolar_battery_voltage
```

Quando scrivi `info batteria`:
```
📊 Info Batteria

🔋 Batteria FV: 87 %
🔌 Corrente scarica: 2.5 A
⚡ Tensione batteria: 48.3 V
```

### Tipi di alias supportati

| Icona | Tipo | Esempio valore |
|-------|------|----------------|
| 📡 | Sensore HA | `sensor.inverter_battery_pct` |
| ⚡ | Comando HomeMind | `/energia`, `/solare`, `/stato` |
| 🔌 | Stato entità | `switch.caldaia`, `cover.tapparella` |
| 📊 | Multi-sensore | `sensor.a, sensor.b, sensor.c` |

### Gestire gli alias

```
/alias                              → vedi tutti gli alias con numeri
dimentica alias                     → mostra lista per scegliere quale rimuovere
dimentica alias 2                   → rimuove l'alias numero 2
dimentica alias batteria fotovoltaico → rimuove per keyword
cancella tutti gli alias            → reset completo
```

### Formati accettati per creare alias

```
memorizza che X = valore
memorizza quando chiedo X = valore
memorizza quando dico X apri valore
alias X = valore
```

---

## Modalità Offline 🔌

Se **tutti i provider AI sono irraggiungibili** (quota finita, internet down, rate limit su tutti), HomeMind entra automaticamente in modalità offline invece di restituire un errore.

Ogni risposta in modalità offline mostra `⚠️ Modalità offline` così sai sempre in che stato si trova il sistema.

### Cosa funziona offline

```
accendi luce cucina                    ✅ eseguito
spegni tutte le luci                   ✅ eseguito
apri tapparelle salotto                ✅ eseguito
chiudi tapparelle al 50%               ✅ eseguito
accendi / spegni [nome switch]         ✅ eseguito
stato casa                             ✅ risposta
chi c'è in casa                        ✅ risposta
arma / disarma allarme                 ✅ eseguito
[i tuoi alias personalizzati]          ✅ sempre attivi
```

### Cosa NON funziona offline

```
"analizza i consumi di questa settimana"    ❌ richiede AI
"crea un'automazione che..."               ❌ richiede AI
"che tempo fa domani?"                     ❌ richiede AI
domande complesse e analisi                ❌ richiede AI
```

> 💡 Gli **alias** che hai configurato funzionano **sempre**, anche in modalità offline.

---

## Tapparelle e Tende 🪟

HomeMind riconosce automaticamente tutte le cover (`cover.*`) configurate in HA — non serve nessuna configurazione aggiuntiva.

HomeMind usa sempre **`current_position`** (il valore reale: 0=chiuso, 100=aperto) invece dello `state` HA che può riportare "open" o "closed" in modo impreciso.

```
apri tapparelle salotto
chiudi tapparelle camera
alza le tapparelle al 70%
apri tutte le tapparelle
chiudi tutto
```

---

## Memoria Persistente 🧠

HomeMind impara le tue preferenze nel tempo analizzando le conversazioni.

```
/memoria              → tutto ciò che HomeMind sa su di te
/dimentica caldaia    → rimuove i fatti contenenti "caldaia"
/memoria reset        → cancella tutto e riparte da zero
```

**Risoluzione conflitti automatica (nuovo in v1.5.0):** se dici "preferisco 21°C" e poi "preferisco 22°C", HomeMind aggiorna il fatto esistente invece di tenere entrambi. La memoria rimane pulita e accurata.

---

## Briefing Mattutino Personalizzabile 🌅

Completamente personalizzabile via Telegram senza toccare nessun file.

### Aggiungere sezioni

```
Aggiungi al briefing temperatura cucina sensor.temp_cucina
Aggiungi al briefing temperatura esterna {sensor.temp_esterna}
Aggiungi al briefing Ricorda di annaffiare le piante
```

### Rimuovere e nascondere sezioni

```
Rimuovi dal briefing temperatura cucina
Rimuovi sezioni extra briefing
Escludi meteo dal briefing
Escludi energia dal briefing
Mostra energia nel briefing
```

### Orario e saluto

```
Briefing alle 8
Saluto briefing Buongiorno Mario! ☀️
Ripristina briefing
```

Il cambio di orario è attivo entro **5 minuti**, senza riavviare l'addon.

---

## Meteo Esterno 🌤️

Previsioni meteo per qualsiasi città — **senza API key**, usando open-meteo.com.

```
Meteo Roma
Che tempo fa a Milano domani?
Previsioni Napoli
Imposta meteo briefing Roma
```

---

## Monitor Elettrodomestici ⚡

### Modalità POWER (presa smart con sensore potenza)

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

### Modalità SMART (elettrodomestici connessi Bosch/Siemens/Miele)

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

### Chiedere lo stato

```
stato lavatrice        → risposta solo sulla lavatrice
/elettrodomestici      → tutti insieme
```

---

## Ottimizzatore Solare ☀️

```json
"solar_optimizer": {
  "enabled": true,
  "min_surplus_w": 500,
  "battery_soc_sensor": "sensor.batteria_percentuale",
  "battery_full_threshold": 95,
  "min_sun_elevation": 10,
  "confirm_minutes": 5,
  "cooldown_hours": 2
}
```

---

## Power Guard ⚠️

```json
"power_guard": {
  "enabled": true,
  "power_sensor": "sensor.consumo_casa_w",
  "threshold_w": 3000,
  "warning_pct": 90,
  "mode": "ask",
  "appliances_priority": [
    {"name": "Lavatrice",     "switch": "switch.presa_lavatrice"},
    {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie"}
  ]
}
```

| `mode` | Comportamento |
|--------|---------------|
| `warn_only` | Solo notifica Telegram |
| `ask` | Chiede conferma prima di spegnere **(consigliato)** |
| `auto` | Spegne automaticamente per priorità |

---

## Task Programmati ⏰

```
alle 19:00 spegni le luci del salotto
tra 30 minuti accendi la caldaia
domani alle 7 fai il briefing
venerdì alle 20 avvisami di comprare il pane
```

```
/task              → lista task in coda
/cancella_task 1   → cancella il task numero 1
```

---

## Configurazione via Chat ⚙️

```
/config   → mostra configurazione attuale

Aggiungi person.mario alla whitelist
Cambia soglia Enel a 3500W
Power Guard modalità auto
Aggiungi proximity per person.mario     ← wizard interattivo
Aggiungi elettrodomestico asciugatrice  ← wizard interattivo
```

---

## Routine Intelligente 📅

Dopo **3 giorni** di osservazione HomeMind impara le tue abitudini.

```
/routine → mostra orari tipici appresi
```

---

## Gestione Automazioni 🤖

```
crea automazione che spenga tutte le luci a mezzanotte
modifica automazione luci notte — falla scattare all'01:00
elimina automazione luci notte

/automazioni          → lista completa
/automazioni_help     → guida con esempi
```

---

## Analisi Log e Auto-Fix 🩺

Legge i log HA ogni 5 minuti. Se trova errori critici invia notifica Telegram con analisi AI e proposta di fix. Attiva di default.

---

## Dashboard Lovelace AI 🎨

```
genera la mia dashboard
crea una dashboard lovelace per le mie entità
```

---

## Telecamere Frigate 📷

```json
"frigate": {
  "enabled": true,
  "host": "192.168.1.100",
  "port": 5000,
  "snapshot_on_alarm": true,
  "cameras": {
    "ingresso": "binary_sensor.sensore_ingresso_occupancy"
  }
}
```

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
| `/routine` | Routine appresa negli ultimi giorni |
| `/automazioni` | Lista automazioni HA |
| `/powerguard` / `/pg` | Stato Power Guard e consumo attuale |
| `/task` | Lista task programmati |
| `/cancella_task N` | Cancella task numero N |
| `/config` | Configurazione attuale |
| `/alias` | I tuoi comandi rapidi personalizzati |
| `/memoria` | Cosa HomeMind sa su di te |
| `/dimentica <testo>` | Rimuovi un fatto dalla memoria |
| `/memoria reset` | Cancella tutta la memoria |
| `/spazzatura` | Raccolta prossimi 7 giorni |
| `/providers` | Provider AI attivi e stato fallback |
| `/lingua it` / `/lingua en` | Cambia lingua |
| `/comandi` | Questa lista completa |

---

## Interfaccia Vocale 🎙️

Manda un **messaggio vocale** su Telegram — HomeMind lo trascrive con Whisper di OpenAI e lo tratta come un comando normale.

**Attivazione:** inserisci `openai_api_key` nelle opzioni addon.
**Costo:** circa $0.006 per messaggio da 1 minuto (molto economico).

---

## FAQ ❓

**L'allarme si arma mentre sono ancora in casa**
→ Configura `proximity_sensors` con il tuo sensore distanza dalla Companion App.

**HomeMind non controlla il mio Risco/Verisure/Ajax**
→ Aggiungi `alarm_panel` con l'entity_id corretto trovato in HA → Strumenti Sviluppo → Stati.

**Il messaggio di benvenuto non arriva**
→ Abbassa `threshold_m` a 50. Verifica che la Companion App aggiorni il sensore distanza in background.

**I termostati si spengono da soli quando esco**
→ Imposta `"climate_auto_off": false` oppure aggiungi le entità problematiche a `climate_exclude`.

**Errore 500 sul clima all'uscita**
→ Le valvole termostatiche (Netatmo, TRV) non supportano `turn_off`. Aggiungile a `climate_exclude`.

**L'antifurto Paradox arma solo 1 partizione su 3**
→ Usa `alarm_extra_panels` con le entity_id delle altre partizioni (trovale in HA → Strumenti Sviluppo → Stati → cerca `alarm_control_panel.`).

**HomeMind risponde solo la prima volta e poi va in errore**
→ Groq Free ha un limite di token al minuto. Configura anche Cerebras (gratuito, 1 milione token/min) come fallback nella configurazione.

**SmartIR — errori 400**
→ Aggiungi `"type": "smartir"` nel blocco climate del config.

**Gli alias non funzionano dopo un riavvio**
→ Gli alias sono salvati in `/data/homemind_shortcuts.json`. Persistono tra i riavvii. Se scompaiono (es. dopo reinstallazione), riconfigurali.

**Docker — HomeMind non si connette a HA**
→ Se HA gira su Docker sulla stessa macchina, usa `http://host.docker.internal:8123` invece dell'IP.

**Power Guard mostra app=0**
→ Usa `appliances_priority` con `switch` (non `sensor`) e assicurati che `power_sensor` sia corretto.

---

---

# 🇬🇧 English

> 🇮🇹 Cerchi la versione italiana? [Clicca qui](#-italiano)

## 📋 Table of Contents

- [What is HomeMind](#what-is-homemind)
- [🆕 What's new in v1.4.5](#-whats-new-in-v145)
- [HAOS Addon Installation](#haos-addon-installation-1)
- [🐳 Docker Installation](#-docker-installation-1)
- [Addon Configuration](#addon-configuration)
- [AI Providers and Automatic Fallback](#ai-providers-and-automatic-fallback-)
- [GPS Location Tracking](#gps-location-tracking-)
- [BASE Configuration](#base-configuration-1)
- [MEDIUM Configuration](#medium-configuration-1)
- [ADVANCED Configuration](#advanced-configuration-1)
- [FULL Configuration](#full-configuration)
- [Custom Alarm + Multi-Partition](#custom-alarm--multi-partition-)
- [Climate and Heating](#climate-and-heating-)
- [Do Not Disturb](#do-not-disturb-)
- [Aliases / Quick Commands](#aliases--quick-commands-)
- [Offline Mode](#offline-mode-)
- [Shutters and Blinds](#shutters-and-blinds-)
- [Persistent Memory](#persistent-memory-1)
- [Morning Briefing](#customizable-morning-briefing-)
- [External Weather](#external-weather-)
- [Appliances](#appliance-monitor-)
- [Solar Optimizer](#solar-optimizer-)
- [Power Guard](#power-guard--1)
- [Scheduled Tasks](#scheduled-tasks-)
- [Config via Chat](#config-via-chat-)
- [Smart Routine](#smart-routine-)
- [Automations Manager](#automations-manager-)
- [Log Analysis](#log-analysis-and-auto-fix-)
- [Lovelace Dashboard](#lovelace-dashboard-ai-)
- [Frigate Cameras](#frigate-cameras-)
- [Telegram Commands](#telegram-commands-)
- [Voice Interface](#voice-interface-)
- [FAQ](#faq--1)
- [Changelog](#changelog)

---

## What is HomeMind

HomeMind is a **Home Assistant add-on** that adds an AI brain to your home. It's not a simple automation — it's an agent that understands context, learns your routine and alerts you only when it truly matters.

**Talk to it on Telegram in natural language:**

> *"Turn on the living room light"*
> *"How much energy did I produce today?"*
> *"Open the bedroom blinds to 70%"*
> *"Enable quiet hours from 11pm to 7am"*
> *"Remember battery solar = sensor.inverter_battery_pct"*

You can also send **voice messages** 🎙️ — it transcribes them with Whisper and treats them as normal commands.

### What it does automatically

| Feature | Description |
|---------|-------------|
| 🔒 **Automatic alarm** | Arms when everyone leaves, disarms when you return |
| 👋 **Welcome home** | Telegram message when you arrive |
| 📷 **Camera snapshots** | Auto photo on Telegram when alarm triggers |
| ⚡ **Appliance monitor** | Notifies when washer/dishwasher finish |
| ☀️ **Solar optimizer** | Alerts you when to use FV surplus |
| 🔕 **Do Not Disturb** | Blocks non-critical notifications at night |
| 🔗 **Quick command aliases** | Custom keywords → guaranteed actions without AI |
| 🔌 **Offline mode** | Basic commands work even without AI |
| 🌅 **Morning briefing** | Fully customizable via Telegram |
| 🌤️ **External weather** | 3-day forecast via open-meteo.com — no API key |
| 🧠 **Persistent memory** | Learns your preferences over time |
| ⚠️ **Power Guard** | Protects against contract power threshold |
| 🤖 **Multi-AI with fallback** | 7 AI providers with automatic switching |

---

## 🆕 What's new in v1.4.5

| Feature | Description |
|---------|-------------|
| 🔕 **Do Not Disturb (DND)** | Configurable quiet hours via config or Telegram |
| 🔗 **Aliases / Quick Commands** | Custom keywords → guaranteed direct actions, no AI needed |
| 📊 **Multi-sensor aliases** | One alias can read multiple sensors at once |
| 🔌 **Offline Mode** | When all AI providers fail, basic commands still work |
| 🪟 **Shutter position fix** | Now reads real `current_position` (0–100%) instead of unreliable HA state |
| 🧠 **Conflict-free memory** | Updates existing facts instead of duplicating them |
| 🕐 **Dynamic briefing time** | Time changes via Telegram take effect within 5 min, no restart needed |
| ❄️ **Configurable climate auto-off** | Choose whether and which thermostats to turn off when leaving |
| 🔒 **Multi-partition alarm** | Support for alarms with multiple partitions (Paradox, DSC, etc.) |

---

## HAOS Addon Installation

```
1. HA → Settings → Add-on Store → ⋮ → Repositories
   → Paste: https://github.com/ago19800/HomeMind → Add

2. Search "HomeMind Orchestrator" → Install

3. Configuration tab → enter your data → Save → Start
```

---

## 🐳 Docker Installation

### What you need

- ✅ Docker and Docker Compose installed
- ✅ Home Assistant accessible over the network
- ✅ A Telegram bot (from @BotFather)
- ✅ At least one free AI key (Gemini or Groq)

### Step 1 — Download files

```bash
mkdir ~/homemind && cd ~/homemind
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/docker-compose.yml
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/.env.example
cp .env.example .env
nano .env
```

### Step 2 — Fill in .env

```env
HA_URL=http://192.168.1.100:8123
HA_TOKEN=eyJhbGciOiJ...
TELEGRAM_TOKEN=1234567890:AABBCCDDee...
TELEGRAM_CHAT_ID=123456789
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
```

> 💡 **How to get the HA Token:** HA → click your name (bottom left) → **Security** → **Long-Lived Access Tokens** → **Create Token** → copy it

### Step 3 — Start

```bash
docker-compose up -d
docker-compose logs -f   # check for "HomeMind ready ✅"
```

Edit config at: `~/homemind_data/homemind_patches/person_config.json`

Then restart: `docker-compose restart`

### Update

```bash
docker-compose pull && docker-compose up -d
```

### Addon vs Docker

| Feature | HAOS Addon | Docker Standalone |
|---------|-----------|-------------------|
| Install | Add-on Store | docker-compose |
| Config | Graphical UI | `.env` file |
| person_config.json | `/config/homemind_patches/` | `~/homemind_data/homemind_patches/` |
| All AI features | ✅ | ✅ |
| Web dashboard | ✅ | ✅ (port 8099) |
| Updates | Add-on Store | `docker-compose pull` |

---

## Addon Configuration

```yaml
telegram_bot_token: "TOKEN_FROM_BOTFATHER"
telegram_chat_id:   "YOUR_CHAT_ID"
alarm_code:         "1234"
openai_api_key:     "sk-..."   # only for voice messages
```

---

## AI Providers and Automatic Fallback 🤖

HomeMind uses **multiple AI providers in cascade**. If the first one fails (quota exceeded, rate limit, offline), it automatically switches to the next — transparently, with no action needed from you.

### How the fallback works

```
Your message
    ↓
1. Gemini → quota exceeded or 503? → next
    ↓
2. Groq → rate limit 429? → next
    ↓
3. Cerebras → offline? → next
    ↓
4. DeepSeek / Mistral / Claude / OpenAI → ...
    ↓
5. ⚠️ All failed → Offline Mode (local parser)
```

### Why the limit is reached

Groq Free has a limit of **12,000 tokens per minute**. HomeMind's context (lights, switches, blinds, people list...) can weigh 7,000–9,000 tokens per request. Two consecutive messages can hit the limit.

**Solution:** configure at least **Gemini + Groq + Cerebras** — all **free** and they cover each other automatically. Cerebras has a limit of 1 million tokens per minute and almost never rate-limits.

### Provider configuration

```yaml
gemini_api_key:   "AIzaSy..."       # FREE → aistudio.google.com
gemini_model:     "gemini-2.0-flash"
groq_api_key:     "gsk_..."         # FREE → console.groq.com
groq_model:       "llama-3.3-70b-versatile"
cerebras_api_key: "csk_..."         # FREE → cloud.cerebras.ai
cerebras_model:   "llama3.1-8b"
deepseek_api_key: "sk-..."          # ~FREE → platform.deepseek.com
mistral_api_key:  "..."             # FREE tier → console.mistral.ai
claude_api_key:   "sk-ant-..."      # PAID → console.anthropic.com
openai_api_key:   "sk-..."          # PAID + required for voice messages
ai_provider_order: "gemini,groq,cerebras,deepseek,mistral,claude,openai"
```

| Provider | Cost | Limit | Sign up |
|----------|------|-------|---------|
| 🟦 **Gemini** | **Free** | 1,500 req/day | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ **Groq** | **Free** | 12,000 token/min | [console.groq.com](https://console.groq.com) |
| 🧠 **Cerebras** | **Free** | 1M token/min ⚡ | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 **DeepSeek** | ~Free | $0.014/1M token | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟣 **Mistral** | Free tier | — | [console.mistral.ai](https://console.mistral.ai) |
| 🟠 **Claude** | Paid | — | [console.anthropic.com](https://console.anthropic.com) |
| 🟢 **OpenAI** | Paid | $0.006/min audio | [platform.openai.com](https://platform.openai.com) |

> 💡 **Minimum recommended:** configure **Gemini + Groq + Cerebras** — zero cost, full coverage.

---

## GPS Location Tracking 📍

GPS tracking lets HomeMind know when you're near home and automatically arm/disarm the alarm.

### Step 1 — Install HA Companion App

- Android → [Google Play](https://play.google.com/store/apps/details?id=io.homeassistant.companion.android)
- iOS → [App Store](https://apps.apple.com/app/home-assistant/id1099568401)

Log in to your HA from the app and **grant location permissions** when prompted. Choose "Always" for full coverage.

### Step 2 — Verify created entities

After configuring the app, HA automatically creates:
- `person.your_name` — presence (home / not_home)
- `sensor.your_name_phone_distance` — distance from home in meters

Go to **HA → Developer Tools → States** and search for `person.` and `sensor.` with your name.

### Step 3 — Configure person_config.json

```json
{
  "person_whitelist": ["person.mario", "person.lucia"],

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
  }
}
```

| Field | Meaning |
|-------|---------|
| `sensor` | Distance sensor entity ID from the Companion App |
| `threshold_m` | Distance in meters below which HomeMind considers the person "near home" |
| `stale_check` | `false` = always use GPS data even if old (recommended) |

> ⚠️ **Common issue:** welcome message doesn't arrive → lower `threshold_m` to 50 and make sure the Companion App updates the distance sensor in the background.

## Location Tracker — Where have they been? 📍🗺️

The **Location Tracker** is an optional feature that lets you ask HomeMind **where a person has been during the last few hours**, with real addresses via GPS (OpenStreetMap, free — no API key needed).

### Difference from `proximity_sensors`

| | `proximity_sensors` | `location_tracker` |
|---|---|---|
| **Purpose** | Know if person is near home | Know where they've been during the day |
| **Entity used** | `sensor.name_distance` | `device_tracker.phone_name` |
| **Response** | Home empty / welcome / alarm | List of stops with address and duration |
| **Required** | Yes (for automatic alarm) | No (optional) |

### How to find your device_tracker

HA → **Developer Tools → States** → search `device_tracker.`

### Configuration in person_config.json

```json
"location_tracker": {
  "mario": "device_tracker.pixel_7",
  "lucia": "device_tracker.iphone_lucia"
}
```

### How to use it on Telegram

```
where was Mario today?
stops of Mario
Mario's route today
where did Lucia go yesterday?
```

**HomeMind response:**
```
📍 Mario's stops — last 24h

🏠 Home — 7h 23min (left at 08:15)
🏢 42 Main Street, London — 4h 11min
🛒 Tesco, High Street — 38min
⛽ BP Station, A40 — 12min
🏠 Home — arrived 19:44
```

> 💡 If HomeMind replies "No device_tracker configured for Mario", check the name in config matches how you refer to them on Telegram.


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

  "appliances": {
    "washer": {
      "enabled": true, "name": "Washer", "icon": "🫧",
      "mode": "power",
      "power_sensor": "sensor.washer_plug_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5,
      "notify_on_start": false
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

## ADVANCED Configuration

```json
{
  "language": "en",
  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.fake_tablet"],
  "motion_whitelist": ["binary_sensor.entrance_sensor_occupancy"],

  "alarm_panel": {
    "entity": "alarm_control_panel.risco_home",
    "arm_mode": "armed_away"
  },

  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.mario_pixel_distance",
      "threshold_m": 100,
      "stale_check": false
    }
  },

  "climate": {
    "climate.main_thermostat": {
      "name": "Home thermostat",
      "switch": "switch.boiler",
      "min_temp": 15,
      "max_temp": 30
    }
  },
  "climate_auto_off": true,
  "climate_exclude": [],

  "power_guard": {
    "enabled": true,
    "power_sensor": "sensor.home_power_w",
    "threshold_w": 3000, "warning_pct": 90, "mode": "ask",
    "appliances_priority": [
      {"name": "Washer",     "switch": "switch.washer_plug"},
      {"name": "Dishwasher", "switch": "switch.dishwasher_plug"}
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

## FULL Configuration

```json
{
  "language": "en",
  "timezone": "Europe/London",

  "person_whitelist": ["person.mario", "person.lucia"],
  "person_blacklist": ["person.fake_tablet"],
  "motion_whitelist": ["binary_sensor.entrance_sensor_occupancy"],
  "contact_blacklist": ["binary_sensor.garage_door_contact"],

  "alarm_panel": {
    "entity": "alarm_control_panel.risco_home",
    "arm_mode": "armed_away"
  },
  "alarm_extra_panels": [
    "alarm_control_panel.paradox_partition_2",
    "alarm_control_panel.paradox_partition_3"
  ],

  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.mario_pixel_distance",
      "threshold_m": 100,
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
      "name": "Home thermostat",
      "switch": "switch.boiler",
      "min_temp": 15, "max_temp": 30
    },
    "climate.living_ac": {
      "name": "Living Room AC",
      "type": "smartir"
    }
  },
  "climate_auto_off": true,
  "climate_exclude": [
    "climate.trv_kitchen",
    "climate.trv_bedroom",
    "climate.trv_bathroom"
  ],

  "appliances": {
    "washer": {
      "enabled": true, "name": "Washer", "icon": "🫧",
      "mode": "power",
      "power_sensor": "sensor.washer_plug_power",
      "power_on_threshold": 50, "power_off_threshold": 10,
      "min_cycle_minutes": 20, "max_idle_minutes": 5,
      "notify_on_start": false
    },
    "dishwasher": {
      "enabled": true, "name": "Dishwasher", "icon": "🍽️",
      "mode": "smart",
      "state_sensor": "sensor.dishwasher_operation_state",
      "running_states": ["Run"],
      "done_states": ["Finished", "Ready"],
      "notify_on_start": false
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

  "quiet_hours": {
    "enabled": true,
    "start": 23,
    "end": 7
  },

  "spazzatura_notify_enabled": true,
  "spazzatura_notify_hour": 20,

  "location_tracker": {
    "mario": "device_tracker.pixel_7",
    "lucia": "device_tracker.iphone_lucia"
  }
}
```

---

## Custom Alarm + Multi-Partition 🔒

```json
"alarm_panel": {
  "entity": "alarm_control_panel.verisure_home",
  "arm_mode": "armed_away"
},
"alarm_extra_panels": [
  "alarm_control_panel.partition_exterior",
  "alarm_control_panel.partition_garage"
]
```

HomeMind uses the **main** panel to read home status. **Extra panels** are armed automatically alongside the main one when everyone leaves.

> 💡 Find all available panels: HA → Developer Tools → States → search `alarm_control_panel.`

---

## Climate and Heating ❄️🔥

### Standard thermostat with boiler switch

```json
"climate": {
  "climate.main_thermostat": {
    "name": "Home thermostat",
    "switch": "switch.boiler",
    "min_temp": 15, "max_temp": 30
  }
}
```

### SmartIR air conditioners

```json
"climate": {
  "climate.living_ac": {
    "name": "Living Room AC",
    "type": "smartir"
  }
}
```

### Auto-off when leaving home

By default, HomeMind turns off all thermostats when the house becomes empty. This causes issues with TRVs (Netatmo, etc.) that don't support `turn_off` → 500 errors in the log.

**Disable completely:**
```json
"climate_auto_off": false
```

**Exclude only problematic TRVs:**
```json
"climate_auto_off": true,
"climate_exclude": [
  "climate.trv_kitchen",
  "climate.trv_bedroom",
  "climate.trv_bathroom"
]
```

---

## Do Not Disturb 🔕

Blocks non-critical notifications during night hours. **Security alerts always pass through.**

```json
"quiet_hours": {
  "enabled": true,
  "start": 23,
  "end": 7
}
```

**Configure via Telegram:**
```
enable quiet hours 23 7
dnd start 22 end 8
activate quiet mode      ← default 23:00 → 07:00

disable quiet hours
disable dnd
```

| 🔕 Blocked by DND | ✅ Always passes |
|-------------------|-----------------|
| Washer/dishwasher done | Alarm triggered 🚨 |
| Solar surplus available | Intrusion detected |
| Trash collection reminder | Everyone left home |
| Power Guard threshold warning | Someone arrived home |

---

## Aliases / Quick Commands 🔗

Create **custom guaranteed commands** — HomeMind executes them directly without AI, always and even offline.

### Create a sensor alias

```
memorize battery solar = sensor.inverter_pipsolar_battery_capacity_percent
```

### Create a command alias

```
memorize energy info = /energia
remember when I ask solar open /solare
alias home status = /stato
```

### Multi-sensor alias

```
memorize battery info = sensor.inverter_pipsolar_battery_capacity_percent, sensor.inverter_pipsolar_battery_discharge_current, sensor.inverter_pipsolar_battery_voltage
```

When you write `battery info`:
```
📊 Battery Info

🔋 Battery %: 87 %
🔌 Discharge current: 2.5 A
⚡ Battery voltage: 48.3 V
```

### Manage aliases

```
/alias                          → view all aliases with numbers
forget alias                    → show list to choose which to remove
forget alias 2                  → remove alias number 2
forget alias battery solar      → remove by keyword
clear all aliases               → full reset
```

---

## Offline Mode 🔌

When **all AI providers fail**, HomeMind automatically enters offline mode. Every response shows `⚠️ Offline mode`.

**Works without AI:**
```
turn on/off light kitchen          ✅
turn off all lights                ✅
open/close living room blinds      ✅
close blinds at 50%                ✅
turn on/off [switch name]          ✅
home status                        ✅
who is home                        ✅
arm/disarm alarm                   ✅
[your custom aliases]              ✅ always active
```

**Does NOT work without AI:**
```
"analyze this week's consumption"  ❌ requires AI
"create an automation that..."     ❌ requires AI
"what's the weather tomorrow?"     ❌ requires AI
```

---

## Shutters and Blinds 🪟

HomeMind automatically detects all `cover.*` entities from HA — no configuration needed.

HomeMind always reads **`current_position`** (real value: 0=closed, 100=open).

```
open living room blinds
close bedroom shutters
raise blinds to 70%
open all blinds
close everything
```

---

## Persistent Memory 🧠

```
/memory              → everything HomeMind knows about you
/forget boiler       → remove facts containing "boiler"
/memory reset        → clear all
```

**Conflict resolution (new in v1.5.0):** if you say "I prefer 21°C" and then "I prefer 22°C", HomeMind updates the existing fact instead of keeping both.

---

## Customizable Morning Briefing 🌅

```
Add kitchen temperature to briefing sensor.temp_kitchen
Add to briefing Remember to water the plants
Remove kitchen temperature from briefing
Hide weather from briefing
Show energy in briefing
Briefing at 8
Reset briefing
```

Time changes take effect **within 5 minutes**, no restart needed.

---

## External Weather 🌤️

```
Weather London
What's the weather in Paris tomorrow?
Forecast New York
```

---

## Appliance Monitor ⚡

**POWER mode:**
```json
"mode": "power",
"power_sensor": "sensor.washer_plug_power",
"power_on_threshold": 50,
"power_off_threshold": 10
```

**SMART mode:**
```json
"mode": "smart",
"state_sensor": "sensor.dishwasher_operation_state",
"running_states": ["Run"],
"done_states": ["Finished", "Ready"]
```

---

## Solar Optimizer ☀️

```json
"solar_optimizer": {
  "enabled": true,
  "min_surplus_w": 500,
  "battery_soc_sensor": "sensor.battery_percentage",
  "battery_full_threshold": 95,
  "min_sun_elevation": 10
}
```

---

## Power Guard ⚠️

```json
"power_guard": {
  "enabled": true,
  "power_sensor": "sensor.home_power_w",
  "threshold_w": 3000, "warning_pct": 90, "mode": "ask"
}
```

| `mode` | Behavior |
|--------|----------|
| `warn_only` | Telegram notification only |
| `ask` | Asks before turning off **(recommended)** |
| `auto` | Turns off automatically by priority |

---

## Scheduled Tasks ⏰

```
at 7pm turn off living room lights
in 30 minutes turn on the boiler
tomorrow at 7 send me the briefing
friday at 8pm remind me to buy groceries
```

---

## Config via Chat ⚙️

```
/config   → show current configuration

Add person.mario to whitelist
Change power threshold to 3500W
Power Guard mode auto
Add proximity for person.mario     ← interactive wizard
Add appliance dryer                ← interactive wizard
```

---

## Smart Routine 📅

After **3 days** of observation HomeMind learns your habits.

```
/routine → shows learned typical schedules
```

---

## Automations Manager 🤖

```
create automation to turn off all lights at midnight
edit automation night lights — change it to 01:00
delete automation night lights

/automazioni          → full list
/automazioni_help     → guide with examples
```

---

## Log Analysis and Auto-Fix 🩺

Reads HA logs every 5 minutes. If critical errors are found, sends Telegram notification with AI analysis and fix proposal. Active by default.

---

## Lovelace Dashboard AI 🎨

```
generate my dashboard
create a lovelace dashboard for my entities
```

---

## Frigate Cameras 📷

```json
"frigate": {
  "enabled": true,
  "host": "192.168.1.100",
  "port": 5000,
  "snapshot_on_alarm": true,
  "cameras": {"entrance": "binary_sensor.entrance_sensor_occupancy"}
}
```

---

## Telegram Commands 📱

| Command | Description |
|---------|-------------|
| `/stato` | Full status: people, alarm, temperatures, blinds |
| `/briefing` | Morning briefing right now |
| `/energia` | Solar production and today's consumption |
| `/ieri` | Yesterday's energy |
| `/solare` | Solar surplus and optimizer |
| `/elettrodomestici` | All appliance status |
| `/routine` | Learned routine |
| `/automazioni` | List HA automations |
| `/powerguard` / `/pg` | Power Guard status |
| `/task` | List scheduled tasks |
| `/cancella_task N` | Cancel task number N |
| `/config` | Current configuration |
| `/alias` | Your custom quick commands |
| `/memory` | What HomeMind knows about you |
| `/forget <text>` | Remove a fact |
| `/memory reset` | Clear all memory |
| `/spazzatura` | Trash collection next 7 days |
| `/providers` | Active AI providers and fallback status |
| `/lingua it` / `/lingua en` | Change language |
| `/comandi` | This full list |

---

## Voice Interface 🎙️

Send a **voice message** on Telegram — HomeMind transcribes it with OpenAI Whisper and treats it as a normal command.

**Activation:** add `openai_api_key` in the addon options.
**Cost:** approximately $0.006 per 1-minute message.

---

## FAQ ❓

**Alarm arms while I'm still home** → Configure `proximity_sensors` with your distance sensor from the Companion App.

**Welcome message doesn't arrive** → Lower `threshold_m` to 50. Check that the Companion App updates the distance sensor in the background.

**Thermostats turn off automatically when I leave** → Set `"climate_auto_off": false` or add the problematic entities to `climate_exclude`.

**500 error on climate when leaving** → TRVs (Netatmo, etc.) don't support `turn_off`. Add them to `climate_exclude`.

**Paradox alarm only arms 1 of 3 partitions** → Use `alarm_extra_panels` with the other partition entity IDs.

**HomeMind answers once then goes to error** → Groq Free has a token per minute limit. Configure Cerebras (free, 1M token/min) as additional fallback.

**SmartIR — 400 errors** → Add `"type": "smartir"` to the climate config block.

**Aliases disappear after reinstalling** → Aliases are saved in `/data/homemind_shortcuts.json`. If the addon is fully reinstalled, reconfigure them.

**Docker — can't connect to HA** → If HA runs on Docker on the same machine, use `http://host.docker.internal:8123` instead of the IP.

**Power Guard shows app=0** → Use `appliances_priority` with `switch` and make sure `power_sensor` is correct.

---

## Changelog

### v1.4.5 — 🆕 Ultima versione / Latest version

---

**🇮🇹 Italiano**

**Nuove funzionalità**

- 🔕 **Do Not Disturb (DND)**: ore di silenzio configurabili nel `person_config.json` (`quiet_hours`) oppure direttamente da Telegram (`attiva silenzio notturno 23 7`, `disattiva silenzio`). Le notifiche non critiche vengono bloccate; allarmi e sicurezza passano sempre
- 🔗 **Alias / Comandi Rapidi**: sistema di parole chiave personalizzate che eseguono azioni **garantite** senza passare dall'AI — anche in modalità offline. Supporta sensori, comandi HomeMind, stati entità
- 📊 **Alias multi-sensore**: un alias può leggere più sensori contemporaneamente separandoli con virgola (`memorizza info batteria = sensor.a, sensor.b, sensor.c`) — mostra tutti i valori in una risposta unica
- 🔌 **Modalità Offline**: quando tutti i provider AI falliscono, HomeMind gestisce autonomamente i comandi base (luci, tapparelle, switch, allarme, stato casa) tramite un parser locale deterministico — nessun errore, risposta con `⚠️ Modalità offline`
- 🪟 **Fix tapparelle/cover**: HomeMind legge ora sempre `current_position` (valore reale 0–100%) invece dello `state` HA che può essere "open"/"closed" indipendentemente dalla posizione reale
- 🧠 **Memoria senza conflitti**: se dici "preferisco 21°C" e poi "preferisco 22°C", HomeMind aggiorna il fatto esistente invece di tenerli entrambi — la memoria rimane accurata
- 🕐 **Briefing dinamico**: cambiare orario del briefing via Telegram prende effetto entro 5 minuti senza riavviare l'addon
- ❄️ **Clima auto-off configurabile**: nuova opzione `"climate_auto_off": false` per disabilitare lo spegnimento automatico dei termostati quando la casa si svuota. Nuova opzione `"climate_exclude": [...]` per escludere entità specifiche (es. valvole Netatmo/TRV che restituiscono errore 500 con `turn_off`)
- 🔒 **Multi-partizione allarme**: nuova opzione `alarm_extra_panels` per antifurti con più partizioni (Paradox, DSC, ecc.) — HomeMind arma tutte le partizioni insieme quando tutti escono

**Correzioni bug**

- 🐛 Fix: `dimentica alias N` (rimozione per numero) ora funziona correttamente — era intercettato dal modulo memoria invece che dal gestore alias
- 🐛 Fix: la frase di memorizzazione (`memorizza che X = sensor.yyy`) non triggerava più l'alias appena creato — risolto con exclusion list nel match
- 🐛 Fix: `memorizza quando chiedo X = Y` non veniva parsata correttamente — aggiunto supporto a tutte le varianti ("quando chiedo", "quando dico", "se chiedo")
- 🐛 Fix: `cancella tuti alias` (con typo) ora funziona — rilevamento basato su parola per parola invece di lista fissa
- 🐛 Fix: alias che puntano a comandi (`/energia`, `/solare`) ora funzionano correttamente — corretto `AttributeError: '_handle_message'` → `_handle_update`

---

**🇬🇧 English**

**New features**

- 🔕 **Do Not Disturb (DND)**: configurable quiet hours in `person_config.json` (`quiet_hours`) or directly via Telegram (`enable quiet hours 23 7`, `disable dnd`). Non-critical notifications are blocked; alarms and security always pass through
- 🔗 **Aliases / Quick Commands**: custom keyword system that executes **guaranteed** actions without going through AI — even in offline mode. Supports sensors, HomeMind commands, entity states
- 📊 **Multi-sensor aliases**: one alias can read multiple sensors at once, separated by commas (`memorize battery info = sensor.a, sensor.b, sensor.c`) — shows all values in a single reply
- 🔌 **Offline Mode**: when all AI providers fail, HomeMind autonomously handles basic commands (lights, blinds, switches, alarm, home status) via a local deterministic parser — no error, response includes `⚠️ Offline mode`
- 🪟 **Shutter/cover fix**: HomeMind now always reads `current_position` (real value 0–100%) instead of the HA `state` which can show "open"/"closed" regardless of actual position
- 🧠 **Conflict-free memory**: if you say "I prefer 21°C" and then "I prefer 22°C", HomeMind updates the existing fact instead of keeping both — memory stays accurate
- 🕐 **Dynamic briefing**: changing the briefing time via Telegram takes effect within 5 minutes without restarting the addon
- ❄️ **Configurable climate auto-off**: new option `"climate_auto_off": false` to disable automatic thermostat shutdown when the house empties. New `"climate_exclude": [...]` option to exclude specific entities (e.g. Netatmo TRVs that return 500 error with `turn_off`)
- 🔒 **Multi-partition alarm**: new `alarm_extra_panels` option for alarms with multiple partitions (Paradox, DSC, etc.) — HomeMind arms all partitions together when everyone leaves

**Bug fixes**

- 🐛 Fix: `forget alias N` (remove by number) now works correctly — was being intercepted by the memory module instead of the alias handler
- 🐛 Fix: memorization phrase (`memorize X = sensor.yyy`) no longer triggers the newly created alias — fixed with exclusion list in match
- 🐛 Fix: `memorize when I ask X = Y` was not parsed correctly — added support for all variants ("when I ask", "when I say", "if I ask")
- 🐛 Fix: `clear all aliases` with typos now works — detection based word-by-word instead of fixed list
- 🐛 Fix: aliases pointing to commands (`/energia`, `/solare`) now work correctly — fixed `AttributeError: '_handle_message'` → `_handle_update`

---

**v1.4.3** — Briefing mattutino personalizzabile via chat, Meteo esterno open-meteo.com (no API key), Docker Standalone (HA Core/Container/Unraid), Multi-AI fallback automatico a cascata (7 provider), stato singolo elettrodomestico / Customizable morning briefing, External weather open-meteo.com, Docker Standalone, Multi-AI cascade fallback (7 providers), single appliance status

**v1.4.1** — Task Scheduler parser esteso, Config Editor via chat (/config), SmartIR auto-detect, fix GPS stale, Power Guard / Extended Task Scheduler parser, Config Editor via chat, SmartIR auto-detect, GPS stale fix, Power Guard

**v1.4.0** — Smart Routine Manager, Memoria persistente, Clima con switch fisico, Solar optimizer batteria + elevazione / Smart Routine Manager, Persistent memory, Climate with physical switch, Solar optimizer battery + elevation

**v1.3.7** — Power Guard (3 modalità: warn/ask/auto)

**v1.3.6** — Calendario spazzatura builtin 2026

**v1.2.x** — Integrazione Frigate NVR, snapshot automatici, Web UI

**v1.0.4** — Interfaccia vocale Whisper / Whisper voice interface

**v1.0.0** — Release iniziale / Initial release

---

<div align="center">

**HomeMind Orchestrator** — *La tua casa, finalmente intelligente. / Your home, finally intelligent.*

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

**[paypal.me/ago19800](https://paypal.me/ago19800)**

[🔝 Torna su / Back to top](#-homemind-orchestrator)

</div>
