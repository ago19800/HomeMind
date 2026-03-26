<div align="center">

# 🧠 HomeMind Orchestrator

**[🇮🇹 Italiano](#-italiano) · [🇬🇧 English](#-english)**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![Language](https://img.shields.io/badge/Lingua-Italiano%20%2F%20English-green)]()
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Groq%20%7C%20Cerebras%20%7C%20DeepSeek%20%7C%20Mistral%20%7C%20Claude%20%7C%20OpenAI-orange)]()
[![Version](https://img.shields.io/badge/versione-1.4.4-brightgreen)](https://github.com/ago19800/HomeMind/releases)

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
- [Installazione Addon HAOS](#installazione-addon-haos)
- [🐳 Installazione Docker (HA Core / Container / Unraid)](#-installazione-docker-ha-core--container--unraid)
- [Configurazione Addon](#configurazione-addon-it)
- [Pagina Impostazioni Web](#pagina-impostazioni-web-it)
- [Configurazione BASE](#configurazione-base)
- [Configurazione MEDIA](#configurazione-media)
- [Configurazione AVANZATA](#configurazione-avanzata)
- [Allarme Personalizzato](#allarme-personalizzato)
- [Sensore Prossimità GPS](#sensore-prossimità-gps)
- [Elettrodomestici](#monitor-elettrodomestici)
- [Ottimizzatore Solare](#ottimizzatore-solare)
- [Power Guard](#power-guard-it)
- [Clima e Riscaldamento](#clima-e-riscaldamento)
- [Climatizzatori SmartIR](#climatizzatori-smartir-it)
- [Briefing Mattutino Personalizzabile](#briefing-mattutino-personalizzabile-it)
- [Meteo Esterno](#meteo-esterno-it)
- [Task Programmati](#task-programmati-it)
- [Configurazione via Chat](#configurazione-via-chat-it)
- [Memoria Persistente](#memoria-persistente)
- [Routine Intelligente](#routine-intelligente)
- [Gestione Automazioni](#gestione-automazioni-it)
- [Analisi Log e Auto-Fix](#analisi-log-e-auto-fix-it)
- [Generatore Dashboard Lovelace](#generatore-dashboard-lovelace-it)
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
> *"Aggiungi temperatura cucina al briefing"*
> *"Escludi meteo dal briefing"*

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
| 🌅 **Briefing mattutino** | Personalizzabile: aggiungi sensori, escludi sezioni, cambio orario |
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

## Installazione Addon HAOS

> Per chi usa **Home Assistant OS** o **Home Assistant Supervised**

```
1. HA → Impostazioni → Add-on Store → ⋮ → Repositories
   → Incolla: https://github.com/ago19800/HomeMind → Aggiungi

2. Cerca "HomeMind Orchestrator" → Installa

3. Scheda Configurazione → inserisci dati → Salva → Avvia
```

---

## 🐳 Installazione Docker (HA Core / Container / Unraid)

> Per chi usa **Home Assistant Core**, **HA Container**, **Unraid**, **NAS Synology/QNAP** o qualsiasi sistema con Docker.

### Cosa ti serve prima di iniziare

- ✅ Docker e Docker Compose installati sul tuo sistema
- ✅ Home Assistant raggiungibile via rete (es. `http://192.168.1.100:8123`)
- ✅ Un bot Telegram (creato con @BotFather)
- ✅ Almeno una chiave AI gratuita (Gemini o Groq — vedi tabella sotto)

---

### Passo 1 — Crea la cartella e scarica i file

```bash
mkdir ~/homemind
cd ~/homemind

# Scarica i due file necessari
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/docker-compose.yml
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/.env.example
```

---

### Passo 2 — Crea il file di configurazione

```bash
cp .env.example .env
nano .env
```

Compila i campi obbligatori nel file `.env`:

```env
# ── Home Assistant ──────────────────────────
HA_URL=http://192.168.1.100:8123        ← IP del tuo HA
HA_TOKEN=eyJhbGciOiJ...                 ← Token (vedi sotto come ottenerlo)

# ── Telegram ────────────────────────────────
TELEGRAM_TOKEN=1234567890:AABBCCDDee... ← da @BotFather
TELEGRAM_CHAT_ID=123456789              ← da @userinfobot

# ── AI — inserisci almeno uno ───────────────
GEMINI_API_KEY=AIzaSy...    # GRATIS → aistudio.google.com
GROQ_API_KEY=gsk_...        # GRATIS → console.groq.com
```

> 💡 **Come ottenere il Token HA:**
> HA → clicca sul tuo nome (in basso a sinistra) → **Sicurezza** → **Token di lunga durata** → **Crea token** → dai un nome (es. "HomeMind") → copia il token

---

### Passo 3 — Avvia HomeMind

```bash
docker-compose up -d
```

Controlla che funzioni:

```bash
docker-compose logs -f
# Dovresti vedere: "HomeMind pronto ✅"
```

---

### Passo 4 — Configura persone e sensori

Dopo il primo avvio, HomeMind crea automaticamente la cartella con i file di configurazione:

```
~/homemind_data/
  homemind_patches/
    person_config.json   ← modifica questo file con le tue entità HA
```

Apri `person_config.json` e aggiungi le tue entità — la sintassi è identica all'addon:

```json
{
  "person_whitelist": ["person.mario", "person.lucia"],
  "motion_whitelist": ["binary_sensor.sensore_ingresso_occupancy"]
}
```

Poi riavvia il container per applicare:

```bash
docker-compose restart
```

---

### Aggiornamento Docker

```bash
docker-compose pull
docker-compose up -d
```

---

### Installazione su Unraid

1. **Community Applications** → cerca "HomeMind" (se disponibile)
   oppure usa **Add Container** manualmente:
   - Repository: `ghcr.io/ago19800/homemind:latest`
   - Aggiungi volume: `/mnt/user/appdata/homemind:/data/homemind`
   - Aggiungi tutte le variabili dal file `.env.example`

---

### Differenze Addon vs Docker

| Funzione | Addon HAOS | Docker Standalone |
|----------|-----------|-------------------|
| Installazione | Add-on Store | docker-compose |
| Configurazione | UI grafica | file `.env` |
| person_config.json | `/config/homemind_patches/` | volume `/data/homemind/homemind_patches/` |
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

### Provider AI (inserisci almeno Gemini + Groq — gratuiti)
```yaml
gemini_api_key:   "AIzaSy..."
gemini_model:     "gemini-2.0-flash"

groq_api_key:     "gsk_..."
groq_model:       "llama-3.3-70b-versatile"

cerebras_api_key: "csk_..."
cerebras_model:   "llama3.1-8b"

deepseek_api_key: "sk-..."
deepseek_model:   "deepseek-chat"

mistral_api_key:  "..."
mistral_model:    "mistral-small-latest"

claude_api_key:   "sk-ant-..."
claude_model:     "claude-3-5-haiku-20241022"

openai_api_key:   "sk-..."   # Solo per messaggi vocali
openai_model:     "gpt-4o-mini"

ai_provider_order: "gemini,groq,cerebras,deepseek,mistral,claude,openai"
```

| Provider | Costo | Limite | Link |
|----------|-------|--------|------|
| 🟦 **Gemini** | Gratis | 1.500 req/giorno | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ **Groq** | Gratis | 100k token/giorno | [console.groq.com](https://console.groq.com) |
| 🧠 **Cerebras** | Gratis | 1M token/min | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 **DeepSeek** | ~Gratis | $0.014/1M token | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟣 **Mistral** | Gratis (tier) | — | [console.mistral.ai](https://console.mistral.ai) |
| 🟠 **Claude** | A pagamento | — | [console.anthropic.com](https://console.anthropic.com) |
| 🟢 **OpenAI** | A pagamento | $0.006/min audio | [platform.openai.com](https://platform.openai.com) |

> **Fallback automatico:** se Gemini è offline, HomeMind passa a Groq in 12 secondi, poi a Cerebras e così via. Non rimani mai senza risposta.

---

## Pagina Impostazioni Web IT

Apri HomeMind → clicca **⚙️** in alto. Configura senza toccare file.

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
  "alarm_panel": "alarm_control_panel.risco_casa",
  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.casa_mario_distance",
      "threshold_m": 100, "stale_check": false
    }
  },
  "energy_sensors": {
    "produzione_fv": "sensor.fv_tot", "consumo_casa": "sensor.consumi_giornalieri",
    "rete_enel": "sensor.enel_giornaliero"
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
  "power_guard": {
    "enabled": true,
    "power_sensor": "sensor.consumo_casa_w",
    "threshold_w": 3000, "warning_pct": 90, "mode": "ask",
    "appliances_priority": [
      {"name": "Lavatrice",     "switch": "switch.presa_lavatrice"},
      {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie"}
    ]
  },
  "frigate": {
    "enabled": true, "host": "192.168.1.100", "port": 5000, "snapshot_on_alarm": true,
    "cameras": { "ingresso": "binary_sensor.sensore_ingresso_occupancy" }
  }
}
```

---

## Allarme Personalizzato

```
HA → Strumenti Sviluppatori → Stati → cerca "alarm"
```

```json
"alarm_panel": "alarm_control_panel.risco_casa"
```

Formato avanzato (Verisure, Ajax):
```json
"alarm_panel": {
  "entity": "alarm_control_panel.verisure_casa",
  "arm_mode": "armed_home"
}
```

| `arm_mode` | Quando usarlo |
|------------|---------------|
| `armed_away` | Tutti fuori casa **(default)** |
| `armed_home` | Qualcuno in casa — perimetrale |
| `armed_night` | Modalità notte |

---

## Sensore Prossimità GPS

```json
"proximity_sensors": {
  "person.mario": {
    "sensor": "sensor.casa_mario_distance",
    "threshold_m": 100,
    "stale_check": false
  }
}
```

> Se il benvenuto non arriva, abbassa `threshold_m` a 50.

---

## Monitor Elettrodomestici

**Modalità POWER** (presa smart):
```json
"mode": "power", "power_sensor": "sensor.presa_lavatrice_power",
"power_on_threshold": 50, "power_off_threshold": 10
```

**Modalità SMART** (elettrodomestici connessi):
```json
"mode": "smart", "state_sensor": "sensor.lavastoviglie_operation_state",
"running_states": ["Run"], "done_states": ["Finished", "Ready"]
```

**Chiedere lo stato di un singolo elettrodomestico:**
```
"stato lavatrice"     → risposta solo sulla lavatrice
"stato lavastoviglie" → risposta solo sulla lavastoviglie
"elettrodomestici"    → tutti insieme
```

---

## Ottimizzatore Solare

```json
"solar_optimizer": {
  "enabled": true, "min_surplus_w": 500,
  "battery_soc_sensor": "sensor.batteria_percentuale",
  "battery_full_threshold": 95, "min_sun_elevation": 10
}
```

---

## Power Guard IT

```json
"power_guard": {
  "enabled": true,
  "power_sensor": "sensor.consumo_casa_w",
  "threshold_w": 3000, "warning_pct": 90, "mode": "ask",
  "appliances_priority": [
    {"name": "Lavatrice",     "switch": "switch.presa_lavatrice"},
    {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie"}
  ]
}
```

| `mode` | Comportamento |
|--------|---------------|
| `warn_only` | Solo notifica |
| `ask` | Chiede conferma **(consigliato)** |
| `auto` | Spegne automaticamente |

---

## Clima e Riscaldamento

```json
"climate": {
  "climate.termostato": {
    "name": "Termostato casa", "switch": "switch.caldaia",
    "min_temp": 15, "max_temp": 30
  }
}
```

---

## Climatizzatori SmartIR IT

**Rilevamento automatico** — funziona subito se il clima ha `controller_data` negli attributi.

**Override manuale** se ricevi errori 400:
```json
"climate": {
  "climate.clima_sala": { "name": "Clima Sala", "type": "smartir" }
}
```

---

## Briefing Mattutino Personalizzabile IT

Il briefing mattutino è completamente personalizzabile via Telegram — nessun file da toccare.

### Aggiungere sezioni extra

Aggiungi qualsiasi testo fisso o il valore di un sensore HA:

```
"Aggiungi al briefing temperatura cucina sensor.temp_cucina"
"Aggiungi al briefing temperatura esterna {sensor.temp_ext}"
"Aggiungi al briefing Ricorda di annaffiare le piante"
"Aggiungi sensori energia al briefing"
```

### Rimuovere sezioni extra

```
"Rimuovi dal briefing temperatura cucina"
"Rimuovi sezioni extra briefing"     ← rimuove tutte le sezioni extra
```

### Nascondere sezioni standard

```
"Escludi meteo dal briefing"
"Escludi energia dal briefing"
"Escludi stato casa dal briefing"
"Escludi spazzatura dal briefing"
```

### Ripristinare sezioni nascoste

```
"Mostra meteo nel briefing"
"Mostra energia nel briefing"
```

### Saluto personalizzato

```
"Saluto briefing Buongiorno Mario! ☀️"
"Saluto briefing Agostino"   ← auto-completato in "Buongiorno Agostino! ☀️"
```

### Orario e reset

```
"Briefing alle 8"           → cambia orario a 08:00
"Ripristina briefing"       → rimuove tutto e torna ai default
```

### Riepilogo comandi briefing

| Comando | Effetto |
|---------|---------|
| `Aggiungi al briefing X {sensor.id}` | Aggiunge sezione con valore sensore |
| `Aggiungi al briefing Testo fisso` | Aggiunge nota fissa |
| `Rimuovi dal briefing X` | Rimuove sezione extra specifica |
| `Rimuovi sezioni extra briefing` | Rimuove TUTTE le sezioni extra |
| `Escludi meteo dal briefing` | Nasconde sezione meteo |
| `Mostra energia nel briefing` | Ripristina sezione energia |
| `Saluto briefing Testo` | Imposta saluto personalizzato |
| `Briefing alle 8` | Cambia orario |
| `Ripristina briefing` | Reset completo ai default |

---

## Meteo Esterno IT

HomeMind recupera automaticamente le previsioni meteo per qualsiasi città — **senza API key**, usando open-meteo.com.

```
"Meteo Roma"
"Che tempo fa a Milano domani?"
"Previsioni Napoli"
```

- Mostra temperatura, umidità, vento, pioggia
- Previsioni per i prossimi 3 giorni
- Funziona anche senza sensori meteo in HA

Per impostare la città predefinita nel briefing:
```
"Imposta meteo briefing Roma"
```

---

## Task Programmati IT

```
"alle 19:00" / "alle ore 21:38"
"tra 30 minuti"
"domani alle 7"
"venerdì alle 20"
"il 28 marzo alle 9"
```

```
/task              → lista task in coda
/cancella_task 1   → cancella il task numero 1
```

---

## Configurazione via Chat IT

```
/config   → mostra configurazione attuale
```

```
"Aggiungi person.mario alla whitelist"
"Cambia soglia Enel a 3500W"
"Power Guard modalità auto"
"Aggiungi proximity per person.mario"     ← wizard interattivo
"Aggiungi elettrodomestico asciugatrice"  ← wizard interattivo
"Rimuovi proximity per person.mario"
```

> Tutte le modifiche chiedono conferma prima di essere applicate e vengono salvate immediatamente su disco.

---

## Memoria Persistente

```
/memoria              → tutto ciò che HomeMind sa su di te
/dimentica caldaia    → rimuove i fatti contenenti "caldaia"
/memoria reset        → cancella tutto
```

---

## Routine Intelligente

Dopo **3 giorni** di osservazione, HomeMind inizia ad anticipare i tuoi bisogni.

```
/routine → mostra orari tipici appresi
```

---

## Gestione Automazioni IT

```
"crea automazione che spenga tutte le luci a mezzanotte"
"modifica automazione luci notte — falla scattare all'01:00"
"elimina automazione luci notte"
```

```
/automazioni          → lista completa
/automazioni_help     → guida con esempi
```

---

## Analisi Log e Auto-Fix IT

Legge i log HA ogni 5 minuti e notifica errori critici con soluzione AI. Attivata di default.

---

## Generatore Dashboard Lovelace IT

```
"genera la mia dashboard"
"crea una dashboard lovelace per le mie entità"
```

---

## Telecamere Frigate IT

```json
"frigate": {
  "enabled": true, "host": "192.168.1.100", "port": 5000,
  "snapshot_on_alarm": true,
  "cameras": {
    "ingresso": "binary_sensor.sensore_ingresso_occupancy"
  }
}
```

---

## Comandi Telegram IT

| Comando | Descrizione |
|---------|-------------|
| `/stato` | Stato completo: persone, allarme, temperature |
| `/briefing` | Briefing mattutino subito |
| `/energia` | Produzione FV e consumi oggi |
| `/ieri` | Energia di ieri |
| `/solare` | Surplus FV e ottimizzatore |
| `/elettrodomestici` | Stato tutti gli elettrodomestici |
| `/routine` | Routine appresa |
| `/automazioni` | Lista automazioni HA |
| `/powerguard` / `/pg` | Stato Power Guard e consumo |
| `/task` | Lista task programmati |
| `/cancella_task N` | Cancella task numero N |
| `/config` | Configurazione attuale |
| `/memoria` | Cosa HomeMind sa su di te |
| `/dimentica <testo>` | Rimuovi un fatto |
| `/memoria reset` | Cancella memoria |
| `/spazzatura` | Raccolta prossimi 7 giorni |
| `/providers` | Provider AI attivi e fallback |
| `/lingua it` / `/lingua en` | Cambia lingua |
| `/comandi` | Questa lista |

---

## Interfaccia Vocale IT

Manda un **messaggio vocale** — HomeMind lo trascrive con Whisper e lo tratta come un comando.
**Attivazione:** inserisci `openai_api_key` nella configurazione.

---

## FAQ IT

**L'allarme si arma mentre sono in casa** → Configura `proximity_sensors`.

**HomeMind non controlla il mio Risco/Verisure** → Aggiungi `"alarm_panel"` nel config.

**Il benvenuto non arriva** → Abbassa `threshold_m` a 50.

**Errore FAIL 500 sulla temperatura** → Controlla `max_temp` nel `configuration.yaml` di HA.

**SmartIR — errori 400** → Aggiungi `"type": "smartir"` nel blocco climate del config.

**Power Guard mostra app=0** → Usa `appliances_priority` e `power_sensor` (non `sensor`).

**Docker — HomeMind non si connette a HA** → Verifica `HA_URL` nel `.env`. Se HA gira su Docker sulla stessa macchina, usa `http://host.docker.internal:8123` al posto dell'IP.

**Docker — dove trovo i log?** → `docker-compose logs -f` dalla cartella `~/homemind`.

**Docker — dove si trova person_config.json?** → Nel volume Docker, di solito `~/homemind_data/homemind_patches/person_config.json`.

---

---

# 🇬🇧 English

> 🇮🇹 Cerchi la versione italiana? [Clicca qui](#-italiano)

## 📋 Table of Contents

- [What is HomeMind](#what-is-homemind)
- [HAOS Addon Installation](#haos-addon-installation)
- [🐳 Docker Installation (HA Core / Container / Unraid)](#-docker-installation-ha-core--container--unraid)
- [Addon Configuration](#addon-configuration)
- [Web Settings Page](#web-settings-page)
- [BASE Configuration](#base-configuration)
- [MEDIUM Configuration](#medium-configuration)
- [ADVANCED Configuration](#advanced-configuration)
- [Custom Alarm Panel](#custom-alarm-panel)
- [GPS Proximity Sensor](#gps-proximity-sensor)
- [Appliance Monitor](#appliance-monitor)
- [Solar Optimizer](#solar-optimizer)
- [Power Guard](#power-guard-en)
- [Climate and Heating](#climate-and-heating)
- [SmartIR Climatizers](#smartir-climatizers-en)
- [Customizable Morning Briefing](#customizable-morning-briefing-en)
- [External Weather](#external-weather-en)
- [Scheduled Tasks](#scheduled-tasks-en)
- [Config via Chat](#config-via-chat-en)
- [Persistent Memory](#persistent-memory)
- [Smart Routine](#smart-routine)
- [Automations Manager](#automations-manager-en)
- [Log Analysis and Auto-Fix](#log-analysis-and-auto-fix-en)
- [Lovelace Dashboard Generator](#lovelace-dashboard-generator-en)
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
> *"Add outside temperature to the briefing"*
> *"Hide weather from briefing"*

You can also send **voice messages** 🎙️ — it transcribes the voice and treats it as a normal command.

### What it does automatically

| Feature | Description |
|---------|-------------|
| 🔒 **Automatic alarm** | Arms when everyone leaves, disarms when you return |
| 👋 **Welcome home** | Telegram message when you arrive |
| 📷 **Camera snapshots** | Automatic photo on Telegram when alarm triggers |
| ⚡ **Appliance monitor** | Notifies when washer/dishwasher finish |
| ☀️ **Solar optimizer** | Tells you when to use FV surplus |
| 🌅 **Morning briefing** | Fully customizable: add sensors, hide sections, change time |
| 🌤️ **External weather** | 3-day forecast via open-meteo.com — no API key needed |
| 🧠 **Persistent memory** | Learns your preferences over time |
| ⚠️ **Power Guard** | Protects against contract power threshold |
| 🤖 **Multi-AI with fallback** | 7 AI providers with automatic switching if one goes offline |
| ⏰ **Scheduled tasks** | Schedule future actions in natural language |
| ⚙️ **Config via chat** | Edit configuration by writing on Telegram |

---

## HAOS Addon Installation

> For **Home Assistant OS** or **Home Assistant Supervised**

```
1. HA → Settings → Add-on Store → ⋮ → Repositories
   → Paste: https://github.com/ago19800/HomeMind → Add

2. Search "HomeMind Orchestrator" → Install

3. Configuration tab → enter data → Save → Start
```

---

## 🐳 Docker Installation (HA Core / Container / Unraid)

> For **Home Assistant Core**, **HA Container**, **Unraid**, **Synology/QNAP NAS** or any Docker system.

### What you need

- ✅ Docker and Docker Compose installed
- ✅ Home Assistant accessible over the network (e.g. `http://192.168.1.100:8123`)
- ✅ A Telegram bot (created with @BotFather)
- ✅ At least one free AI key (Gemini or Groq)

---

### Step 1 — Create folder and download files

```bash
mkdir ~/homemind
cd ~/homemind

curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/docker-compose.yml
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/.env.example
```

---

### Step 2 — Create your config file

```bash
cp .env.example .env
nano .env
```

Fill in the required fields:

```env
# ── Home Assistant ───────────────────────────
HA_URL=http://192.168.1.100:8123     ← your HA IP
HA_TOKEN=eyJhbGciOiJ...              ← token (see below)

# ── Telegram ─────────────────────────────────
TELEGRAM_TOKEN=1234567890:AABBCCDDee...
TELEGRAM_CHAT_ID=123456789

# ── AI — at least one required ───────────────
GEMINI_API_KEY=AIzaSy...    # FREE → aistudio.google.com
GROQ_API_KEY=gsk_...        # FREE → console.groq.com
```

> 💡 **How to get the HA Token:**
> HA → click your name (bottom left) → **Security** → **Long-Lived Access Tokens** → **Create Token** → copy it

---

### Step 3 — Start HomeMind

```bash
docker-compose up -d

# Check logs
docker-compose logs -f
```

---

### Step 4 — Configure people and sensors

After first start, HomeMind creates:
```
~/homemind_data/
  homemind_patches/
    person_config.json   ← edit this with your HA entities
```

Then restart to apply:
```bash
docker-compose restart
```

---

### Update Docker

```bash
docker-compose pull
docker-compose up -d
```

---

### Unraid

1. **Community Applications** → search "HomeMind"
   or use **Add Container** manually:
   - Repository: `ghcr.io/ago19800/homemind:latest`
   - Volume: `/mnt/user/appdata/homemind:/data/homemind`
   - Add all env variables from `.env.example`

---

### Addon vs Docker comparison

| Feature | HAOS Addon | Docker Standalone |
|---------|-----------|-------------------|
| Install | Add-on Store | docker-compose |
| Config | Graphical UI | `.env` file |
| person_config.json | `/config/homemind_patches/` | volume `/data/homemind/homemind_patches/` |
| All AI features | ✅ | ✅ |
| Web dashboard | ✅ | ✅ (port 8099) |
| Updates | Add-on Store | `docker-compose pull` |

---

## Addon Configuration

### Telegram (required)
```yaml
telegram_bot_token: "TOKEN_FROM_BOTFATHER"
telegram_chat_id:   "YOUR_CHAT_ID"
alarm_code:         "1234"
```

### AI Providers (add at least Gemini + Groq — both free)
```yaml
gemini_api_key:   "AIzaSy..."
groq_api_key:     "gsk_..."
cerebras_api_key: "csk_..."
deepseek_api_key: "sk-..."
mistral_api_key:  "..."
claude_api_key:   "sk-ant-..."
openai_api_key:   "sk-..."   # Only for voice messages
ai_provider_order: "gemini,groq,cerebras,deepseek,mistral,claude,openai"
```

> **Automatic fallback:** if Gemini is offline, HomeMind switches to Groq in 12 seconds, then Cerebras, etc.

| Provider | Cost | Limit |
|----------|------|-------|
| 🟦 **Gemini** | Free | 1,500 req/day |
| ⚡ **Groq** | Free | 100k token/day |
| 🧠 **Cerebras** | Free | 1M token/min |
| 🔵 **DeepSeek** | ~Free | $0.014/1M token |
| 🟣 **Mistral** | Free tier | — |
| 🟠 **Claude** | Paid | — |
| 🟢 **OpenAI** | Paid | $0.006/min audio |

---

## Web Settings Page

Open HomeMind → click **⚙️** at the top. Configure without editing files.

---

## BASE Configuration

```json
{
  "language": "en",
  "person_whitelist": ["person.mario", "person.lucia"],
  "motion_whitelist": ["binary_sensor.entrance_sensor_occupancy"]
}
```

---

## MEDIUM Configuration

```json
{
  "language": "en",
  "person_whitelist": ["person.mario", "person.lucia"],
  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.home_mario_distance",
      "threshold_m": 100, "stale_check": false
    }
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
  "alarm_panel": "alarm_control_panel.risco_home",
  "proximity_sensors": {
    "person.mario": {"sensor": "sensor.home_mario_distance", "threshold_m": 100, "stale_check": false}
  },
  "power_guard": {
    "enabled": true, "power_sensor": "sensor.home_power_w",
    "threshold_w": 3000, "warning_pct": 90, "mode": "ask",
    "appliances_priority": [
      {"name": "Washer",     "switch": "switch.washer_plug"},
      {"name": "Dishwasher", "switch": "switch.dishwasher_plug"}
    ]
  }
}
```

---

## Custom Alarm Panel

```json
"alarm_panel": "alarm_control_panel.risco_home"
```

Advanced (Verisure/Ajax):
```json
"alarm_panel": {"entity": "alarm_control_panel.verisure_home", "arm_mode": "armed_home"}
```

---

## GPS Proximity Sensor

```json
"proximity_sensors": {
  "person.mario": {"sensor": "sensor.home_mario_distance", "threshold_m": 100, "stale_check": false}
}
```

---

## Appliance Monitor

**POWER mode:** `"mode": "power", "power_sensor": "sensor.washer_plug_power"`

**SMART mode:** `"mode": "smart", "state_sensor": "sensor.dishwasher_operation_state"`

**Ask for a single appliance status:**
```
"washer status"      → reply only about washer
"dishwasher status"  → reply only about dishwasher
"appliances"         → all together
```

---

## Solar Optimizer

```json
"solar_optimizer": {
  "enabled": true, "min_surplus_w": 500,
  "battery_soc_sensor": "sensor.battery_percentage",
  "battery_full_threshold": 95, "min_sun_elevation": 10
}
```

---

## Power Guard EN

```json
"power_guard": {
  "enabled": true, "power_sensor": "sensor.home_power_w",
  "threshold_w": 3000, "warning_pct": 90, "mode": "ask",
  "appliances_priority": [
    {"name": "Washer",     "switch": "switch.washer_plug"},
    {"name": "Dishwasher", "switch": "switch.dishwasher_plug"}
  ]
}
```

---

## Climate and Heating

```json
"climate": {
  "climate.thermostat": {"name": "Home thermostat", "switch": "switch.boiler", "min_temp": 15, "max_temp": 30}
}
```

---

## SmartIR Climatizers EN

Auto-detection works if the entity has `controller_data` in attributes.

Manual override if you get 400 errors:
```json
"climate": {
  "climate.living_room_ac": {"name": "Living Room AC", "type": "smartir"}
}
```

---

## Customizable Morning Briefing EN

The morning briefing is fully customizable via Telegram chat.

### Add extra sections

```
"Add kitchen temperature to briefing sensor.temp_kitchen"
"Add outside temperature to briefing {sensor.temp_ext}"
"Add to briefing Remember to water the plants"
```

### Remove extra sections

```
"Remove kitchen temperature from briefing"
"Remove all extra sections from briefing"
```

### Hide standard sections

```
"Hide weather from briefing"
"Exclude energy from briefing"
"Hide home status from briefing"
```

### Restore hidden sections

```
"Show weather in briefing"
"Show energy in briefing"
```

### Custom greeting and time

```
"Briefing greeting Good morning family! ☀️"
"Briefing at 8"
"Reset briefing"     ← removes all customizations
```

### Briefing command summary

| Command | Effect |
|---------|--------|
| `Add to briefing X {sensor.id}` | Add section with sensor value |
| `Add to briefing Fixed text` | Add fixed note |
| `Remove from briefing X` | Remove specific extra section |
| `Remove all extra sections from briefing` | Remove ALL extra sections |
| `Hide weather from briefing` | Hide weather section |
| `Show energy in briefing` | Restore energy section |
| `Briefing greeting Text` | Set custom greeting |
| `Briefing at 8` | Change time |
| `Reset briefing` | Full reset to defaults |

---

## External Weather EN

HomeMind fetches weather forecasts for any city — **no API key**, using open-meteo.com.

```
"Weather Rome"
"What's the weather in London tomorrow?"
"Forecast Paris"
```

- Shows temperature, humidity, wind, rain
- 3-day forecast
- Works without any weather sensors in HA

---

## Scheduled Tasks EN

```
"at 7pm" / "at 19:30"
"in 30 minutes"
"tomorrow at 7"
"friday at 8pm"
"march 28 at 9am"
```

```
/task              → list scheduled tasks
/cancella_task 1   → cancel task number 1
```

---

## Config via Chat EN

```
/config   → show current configuration
```

```
"Add person.mario to whitelist"
"Change Enel threshold to 3500W"
"Power Guard mode auto"
"Add proximity for person.mario"       ← interactive wizard
"Add appliance dryer"                  ← interactive wizard
"Remove proximity for person.mario"
```

---

## Persistent Memory

```
/memory              → everything HomeMind knows about you
/forget boiler       → remove facts containing "boiler"
/memory reset        → clear all
```

---

## Smart Routine

After **3 days** of observation, HomeMind starts anticipating your needs.

```
/routine → shows learned typical times
```

---

## Automations Manager EN

```
"create automation to turn off all lights at midnight"
"edit automation night lights — change it to 01:00"
"delete automation night lights"
```

---

## Log Analysis and Auto-Fix EN

Reads HA logs every 5 minutes, notifies of critical errors with AI solutions. Enabled by default.

---

## Lovelace Dashboard Generator EN

```
"generate my dashboard"
"create a lovelace dashboard for my entities"
```

---

## Frigate Cameras

```json
"frigate": {
  "enabled": true, "host": "192.168.1.100", "port": 5000,
  "snapshot_on_alarm": true,
  "cameras": {"entrance": "binary_sensor.entrance_sensor_occupancy"}
}
```

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/stato` | Full status: people, alarm, temperatures |
| `/briefing` | Morning briefing right now |
| `/energia` | FV production and today's consumption |
| `/ieri` | Yesterday's energy |
| `/solare` | FV surplus and optimizer |
| `/elettrodomestici` | All appliance status |
| `/routine` | Learned routine |
| `/automazioni` | List HA automations |
| `/powerguard` / `/pg` | Power Guard status |
| `/task` | List scheduled tasks |
| `/cancella_task N` | Cancel task number N |
| `/config` | Current configuration |
| `/memory` | What HomeMind knows about you |
| `/forget <text>` | Remove a fact |
| `/memory reset` | Clear all memory |
| `/spazzatura` | Trash collection next 7 days |
| `/providers` | Active AI providers and fallback status |
| `/lingua it` / `/lingua en` | Change language |
| `/comandi` | This list |

---

## Voice Interface

Send a **voice message** — HomeMind transcribes it with Whisper and treats it as a normal command.
**Activation:** add `openai_api_key` in the addon configuration.

---

## FAQ EN

**Alarm arms while I'm still home** → Configure `proximity_sensors`.

**Welcome message doesn't arrive** → Lower `threshold_m` to 50.

**SmartIR — 400 errors** → Add `"type": "smartir"` to the climate block.

**Power Guard shows app=0** → Use `appliances_priority` and `power_sensor` (not `sensor`).

**Docker — can't connect to HA** → Check `HA_URL` in `.env`. If HA runs on Docker on the same machine, use `http://host.docker.internal:8123` instead of the IP.

**Docker — where are the logs?** → `docker-compose logs -f` from the `~/homemind` folder.

**Docker — where is person_config.json?** → In the Docker volume, usually `~/homemind_data/homemind_patches/person_config.json`.

---

## Changelog

**v1.4.3** — Briefing mattutino personalizzabile via chat (aggiungi/rimuovi sezioni, escludi/mostra standard, saluto, orario, reset), Meteo esterno open-meteo.com (no API key, previsioni 3 giorni), Docker Standalone (HA Core/Container/Unraid), Multi-AI con fallback automatico a cascata (7 provider: Gemini/Groq/Cerebras/DeepSeek/Mistral/Claude/OpenAI), stato singolo elettrodomestico

**v1.4.1** — Task Scheduler parser esteso, Config Editor via chat (/config), SmartIR auto-detect, fallback AI 12s, storico binario leggibile, fix benvenuto GPS stale, Power Guard alias config

**v1.4.0** — Smart Routine Manager, Task Scheduler, Memoria persistente, Clima con switch fisico, Solar optimizer batteria piena + elevazione solare

**v1.3.7** — Power Guard (3 modalità: warn/ask/auto)

**v1.3.6** — Calendario spazzatura builtin 2026

**v1.2.x** — Integrazione Frigate NVR, snapshot automatici, tab web UI

**v1.2.0** — Pagina impostazioni web completa

**v1.0.4** — Interfaccia vocale via Whisper

**v1.0.0** — Release iniziale

---

<div align="center">

**HomeMind Orchestrator** — *La tua casa, finalmente intelligente. / Your home, finally intelligent.*

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

**[paypal.me/ago19800](https://paypal.me/ago19800)**

[🔝 Torna su / Back to top](#-homemind-orchestrator)

</div>
