<div align="center">

# 🧠 HomeMind Orchestrator

**Agente AI autonomo per Home Assistant**  
**Autonomous AI Agent for Home Assistant**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Arch](https://img.shields.io/badge/Arch-amd64%20%7C%20aarch64%20%7C%20armv7-orange)](config.yaml)

---

[🇮🇹 Italiano](#-italiano) · [🇬🇧 English](#-english)

</div>

---

# 🇮🇹 Italiano

HomeMind è un **add-on per Home Assistant** che porta un agente AI nella tua casa. Monitora sensori, anomalie, sicurezza e ti risponde su **Telegram** in linguaggio naturale. Genera card Lovelace, analizza l'energia, gestisce l'allarme e ti manda un briefing ogni mattina.

---

## 📋 Indice

- [Funzionalità](#-funzionalità)
- [Installazione](#-installazione)
- [Configurazione](#-configurazione)
- [Provider AI](#-provider-ai--quale-scegliere)
- [Bot Telegram — comandi](#-bot-telegram--tutti-i-comandi)
- [Filtri persona e sensori](#-filtri-persona-e-sensori)
- [Generare card Lovelace](#-generare-card-lovelace)
- [Calendario spazzatura](#-calendario-spazzatura)
- [Lingua](#-lingua)
- [Esempi pratici](#-esempi-pratici)
- [Struttura file](#-struttura-file)
- [FAQ](#-faq)

---

## ✨ Funzionalità

| Funzione | Descrizione |
|----------|-------------|
| 💬 **Chat AI** | Fai domande sulla tua casa in linguaggio naturale via Telegram |
| 🔒 **Sicurezza** | Arma/disarma allarme automaticamente, notifica movimenti, benvenuto al rientro |
| ⚡ **Energia** | Analisi fotovoltaico, batteria, rete Enel, report giornaliero/ieri |
| 🎨 **Card Lovelace** | Genera YAML per card pronte all'uso (mushroom, gauge, bubble, tile) |
| 🔍 **Anomalie** | Rileva sensori con valori impossibili, luci dimenticate accese, ecc. |
| 🛠️ **Patch YAML** | Genera e applica patch alla configurazione HA per correggere anomalie |
| 🌅 **Briefing mattutino** | Report AI alle 07:00 con energia, meteo, spazzatura, anomalie notturne |
| 🗑️ **Spazzatura** | Carica PDF calendario comunale → notifica serale automatica |
| 🔄 **Aggiornamenti** | Controlla aggiornamenti HA e addon ogni 6 ore |
| 🩺 **Riparazioni** | Verifica problemi ufficiali HA ogni 4 ore |
| 🤖 **Multi-provider AI** | Fallback automatico tra Gemini → Groq → Cerebras → DeepSeek → Claude → OpenAI |
| 🌍 **Multilingua** | Italiano e inglese, cambio al volo con `/lingua en` |
| 📊 **Dashboard web** | Interfaccia chat a `http://IP:8099` con pulsanti rapidi |

---

## 🚀 Installazione

### 1. Aggiungi il repository

In Home Assistant vai su:
**Impostazioni → Add-on → Store → ⋮ → Repository**

Aggiungi l'URL del repository:
```
https://github.com/TUO_UTENTE/homemind-orchestrator
```

### 2. Installa l'add-on

Cerca **HomeMind Orchestrator** nello store e clicca **Installa**.

### 3. Configurazione minima

Vai su **Impostazioni → Add-on → HomeMind Orchestrator → Opzioni** e compila:

```yaml
gemini_api_key: "AIzaSy..."
telegram_bot_token: "123456:ABC..."
telegram_chat_id: "360307101"
```

### 4. Avvia l'add-on

Clicca **Avvia**. Entro 10 secondi ricevi il primo messaggio su Telegram.

---

## ⚙️ Configurazione

### Provider AI

```yaml
gemini_api_key: "AIzaSy..."         # 🟦 Google Gemini — GRATIS 1500/giorno
gemini_model: "gemini-2.0-flash"

groq_api_key: "gsk_..."             # ⚡ Groq — GRATIS 14400/giorno
groq_model: "llama-3.3-70b-versatile"

cerebras_api_key: "csk-..."         # 🧠 Cerebras — GRATIS 1M token/min
cerebras_model: "llama3.1-8b"       # oppure: gpt-oss-120b

deepseek_api_key: "sk-..."          # 🔵 DeepSeek — quasi gratis
deepseek_model: "deepseek-chat"

claude_api_key: "sk-ant-..."        # 🟠 Anthropic Claude — a pagamento
claude_model: "claude-3-5-haiku-20241022"

openai_api_key: "sk-..."            # 🟢 OpenAI — a pagamento
openai_model: "gpt-4o-mini"

ai_provider_order: "gemini,groq,cerebras,deepseek,claude,openai"
```

> Lascia vuoto il campo per disabilitare un provider. HomeMind usa solo quelli con API key.

### Telegram

```yaml
telegram_bot_token: "123456:ABC..."
telegram_chat_id: "360307101"
```

> Ottieni il token da [@BotFather](https://t.me/BotFather). Ottieni il chat_id da [@userinfobot](https://t.me/userinfobot).

### Home Assistant

```yaml
notify_entity: "notify.mobile_app_mio_telefono"
alarm_code: "1234"
spazzatura_notify_hour: "20"
```

### Filtri semplici (nelle Opzioni)

```yaml
person_blacklist: "person.mqtt"
motion_blacklist: "binary_sensor.sm_s931b_motion"
```

---

## 🤖 Provider AI — quale scegliere?

> Consiglio: attiva almeno **Gemini + Groq**. HomeMind passa automaticamente al successivo se uno fallisce.

| Provider | Costo | Limite | Link |
|----------|-------|--------|------|
| 🟦 **Google Gemini** | Gratis | 1.500 req/giorno | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ **Groq** | Gratis | 14.400 req/giorno | [console.groq.com](https://console.groq.com) |
| 🧠 **Cerebras** | Gratis | 1M token/minuto | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 **DeepSeek** | ~Gratis | $0.014/1M token | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟠 **Anthropic Claude** | A pagamento | — | [console.anthropic.com](https://console.anthropic.com) |
| 🟢 **OpenAI GPT** | A pagamento | — | [platform.openai.com](https://platform.openai.com) |

### Come ottenere le API key

**Gemini (consigliato come primario)**
1. Vai su [aistudio.google.com](https://aistudio.google.com)
2. Accedi con Google → **Get API key** → **Create API key**
3. Copia la key `AIzaSy...`

**Groq (consigliato come fallback)**
1. Vai su [console.groq.com](https://console.groq.com)
2. Crea account gratuito → **API Keys** → **Create API Key**
3. Copia la key `gsk_...`

**Cerebras**
1. Vai su [cloud.cerebras.ai](https://cloud.cerebras.ai)
2. Crea account → **API Keys** → **Create**
3. Copia la key `csk-...`
4. Modelli disponibili: `llama3.1-8b` (veloce) · `gpt-oss-120b` (potente)

**DeepSeek**
1. Vai su [platform.deepseek.com](https://platform.deepseek.com)
2. Crea account (ricevi $5 crediti) → **API Keys** → **Create new secret key**

### Verificare i provider

Scrivi `/providers` su Telegram per testare tutti i provider in tempo reale:

```
🤖 Test AI Provider

🥇 ✅ Gemini (Google) 🆓
   gemini-2.0-flash · Risposta: OK

🥈 ✅ Groq/Llama 🆓
   llama-3.3-70b-versatile · Risposta: OK

🥉 ❌ Cerebras 🆓
   llama3.1-8b
   ⚠️ API key non valida — controlla le Opzioni addon
```

---

## 💬 Bot Telegram — tutti i comandi

### Generali

| Comando | Descrizione |
|---------|-------------|
| `/start` · `ciao` | Benvenuto |
| `/comandi` · `/commands` | Lista comandi |
| `/stato` · `/status` | Stato completo della casa |
| `/briefing` · `buongiorno` | Briefing AI immediato |
| `/providers` | Test live di tutti i provider AI |
| `/lingua it` · `/lingua en` | Cambia lingua |

### Sicurezza e presenza

| Comando | Descrizione |
|---------|-------------|
| `/allarme` · `/alarm` | Stato allarme attuale |
| `chi è in casa?` | Persone presenti |
| `dove si trova [nome]?` | Posizione di una persona |

### Energia

| Comando | Descrizione |
|---------|-------------|
| `/energia` · `/energy` | Report energia oggi |
| `/ieri` · `/yesterday` | Report energia ieri |
| `analizza energia` | Analisi AI completa |

### Card Lovelace

| Esempio | Cosa genera |
|---------|-------------|
| `crea card mushroom: sensor.temperatura_soggiorno` | Card moderna per il sensore |
| `crea card gauge: sensor.umidita` | Indicatore circolare |
| `crea card lights` | Card per tutte le luci |
| `crea card energia` | Card fotovoltaico/batteria |
| `crea card security` | Card sicurezza con movimento |
| `crea card tile: tutte le temperature` | Card per tutti i termometri |

### Automazioni

| Comando | Descrizione |
|---------|-------------|
| `/automazioni` · `/automations` | Lista automazioni |
| `crea automazione per...` | Genera YAML automazione |

### Spazzatura

| Comando | Descrizione |
|---------|-------------|
| `/spazzatura` · `/trash` | Prossima raccolta |
| `/ricarica_spazzatura` | Ricarica calendario dal PDF |

### Manutenzione

| Comando | Descrizione |
|---------|-------------|
| `/aggiornamenti` · `/updates` | Controlla aggiornamenti HA |
| `/riparazioni` · `/repairs` | Problemi ufficiali HA |

### Chat libera — esempi

```
Quante luci sono accese?
Qual è la temperatura in soggiorno?
C'è qualcosa di anomalo nei miei sensori?
Analizza i consumi di ieri
Dove si trova Agostino?
Suggerisci come migliorare la configurazione HA
```

---

## 👤 Filtri persona e sensori

### Configurazione base (nelle Opzioni addon)

```yaml
person_blacklist: "person.mqtt,person.guest"
motion_blacklist: "binary_sensor.telefono_motion"
```

### Configurazione avanzata — `person_config.json`

Crea `/config/homemind_patches/person_config.json` per un controllo totale:

```json
{
  "person_whitelist": [
    "person.agostino",
    "person.rosa"
  ],
  "person_blacklist": [
    "person.mqtt"
  ],
  "motion_whitelist": [
    "binary_sensor.0x000d6ffffe1a246d_occupancy",
    "binary_sensor.0x00158d000224fa71_occupancy",
    "binary_sensor.0x00158d000224fb57_occupancy",
    "binary_sensor.0x00158d0001ae9a1b_occupancy"
  ],
  "motion_blacklist": [
    "binary_sensor.sm_s931b_motion",
    "binary_sensor.lc_motion_alarm",
    "binary_sensor.test_sensore_presenza"
  ],
  "contact_blacklist": [
    "binary_sensor.contact_sensor_porta",
    "binary_sensor.lock_pro_3f_porta"
  ],
  "proximity_sensors": {
    "person.agostino": {
      "sensor": "sensor.casa_sm_s931b_distance",
      "threshold_m": 100
    }
  },
  "energy_sensors": {
    "produzione_fv": "sensor.fv_tot",
    "consumo_casa":  "sensor.daily_energy_combined",
    "rete_enel":     "sensor.enel",
    "batteria_wh":   "sensor.batteria_wh"
  },
  "language": "it"
}
```

### Spiegazione di ogni campo

| Campo | Comportamento |
|-------|---------------|
| `person_whitelist` | **Solo** queste persone → sicurezza. Se vuoto = auto-rileva tutto |
| `person_blacklist` | Queste persone vengono **sempre ignorate** |
| `motion_whitelist` | **Solo** questi sensori per l'antifurto. Se vuoto = tutti |
| `motion_blacklist` | Questi sensori vengono **sempre ignorati** (es. smartphone) |
| `contact_blacklist` | Questi sensori contatto/porta esclusi dall'allarme |
| `proximity_sensors` | Sensore distanza casa per sapere se stai arrivando/partendo |
| `energy_sensors` | Mappa i tuoi sensori ai ruoli energia di HomeMind |
| `language` | `"it"` o `"en"` — lingua dell'interfaccia |

### Casi d'uso tipici

**Problema: il sensore del telefono triggera l'allarme**
```json
{ "motion_blacklist": ["binary_sensor.sm_s931b_motion"] }
```

**Problema: persona virtuale/MQTT viene rilevata**
```json
{ "person_blacklist": ["person.mqtt"] }
```

**Voglio usare SOLO i sensori fisici per la sicurezza**
```json
{
  "motion_whitelist": [
    "binary_sensor.pir_ingresso",
    "binary_sensor.pir_salone",
    "binary_sensor.pir_corridoio"
  ]
}
```

**Logica antifurto automatica:**
```
Tutti escono          → HomeMind arma l'allarme
Qualcuno rientra      → HomeMind disarma (dopo 20s anti-rimbalzo)
Tutti via + movimento → ALLARME (servono ≥2 sensori entro 45s per evitare falsi positivi)
Contatti aperti       → Notifica Telegram prima di armare
```

---

## 🎨 Generare card Lovelace

### Stili disponibili

| Stile | Sinonimo IT | Sinonimo EN | Richiede HACS |
|-------|-------------|-------------|----------------|
| `mushroom` | `sicurezza`, `luci` | `lights`, `security` | ✅ Sì |
| `gauge` | `grafico`, `termometro` | `chart`, `graph` | ❌ No |
| `tile` | `minimal` | `minimal` | ❌ No |
| `bubble` | — | — | ✅ Sì |
| `energia` | — | `energy` | ❌ No |

### Esempi di generazione

```
# Sensore singolo con stile gauge
crea card gauge: sensor.temperatura_soggiorno

# Tutte le luci con stile mushroom
crea card lights

# Card energia fotovoltaico
crea card energia

# Tutte le temperature (HomeMind le cerca da solo)
crea card tile: tutte le temperature

# Con YAML personalizzato
crea card mushroom:
  entity: sensor.temperatura_soggiorno
  name: Soggiorno
  icon: mdi:sofa

# Card sicurezza completa
crea card security
```

### Come installare il YAML in HA

1. Copia il blocco YAML dalla risposta Telegram
2. In HA → **Dashboard** → icona matita → **Modifica**
3. **+ Aggiungi card** → **Manuale** → incolla il YAML
4. Salva

> Per mushroom e bubble: installare prima i plugin HACS
> - [mushroom](https://github.com/piitaya/lovelace-mushroom)
> - [bubble-card](https://github.com/Clooos/Bubble-Card)

---

## 🗑️ Calendario spazzatura

### Caricare il PDF

**Metodo 1 — Browser (consigliato)**
1. Apri `http://IP-HA:8099/spazzatura`
2. Trascina il PDF nel riquadro
3. HomeMind lo legge con l'AI e salva il calendario

**Metodo 2 — File diretto**
1. Copia il PDF in `/config/homemind_patches/spazzatura.pdf`
2. Scrivi `/ricarica_spazzatura` su Telegram

### Formato notifica serale

Ogni sera all'orario configurato (default 20:00):

```
🗑️ Domani si raccoglie:
   ♻️ Plastica
   🔩 Metalli
```

### Formato JSON manuale (avanzato)

Se il PDF non viene letto correttamente, crea manualmente:
`/config/homemind_patches/spazzatura_calendario.json`

```json
{
  "2026-03-09": ["Organico"],
  "2026-03-11": ["Carta", "Cartone"],
  "2026-03-13": ["Plastica", "Metalli"],
  "2026-03-16": ["Indifferenziato"],
  "2026-03-18": ["Vetro"],
  "2026-03-20": ["Ingombranti"]
}
```

Formato data: `YYYY-MM-DD`. Tipi riconosciuti con emoji:
`Plastica` ♻️ · `Organico` 🌿 · `Carta` 📄 · `Cartone` 📦 · `Vetro` 🍶 · `Metalli` 🔩 · `Indifferenziato` 🗑️ · `Ingombranti` 🛋️ · `RAEE` 💻

---

## 🌍 Lingua

```
/lingua it    → Passa all'italiano
/lingua en    → Switch to English
/lingua       → Mostra lingua attuale
```

La lingua viene salvata in `person_config.json` e persiste dopo i riavvii.

---

## 📚 Esempi pratici

### Primo avvio

```
Tu:        /start
HomeMind:  Ciao! HomeMind attivo 🧠
           1596 entità caricate, 2 persone trovate.
           Scrivi qualcosa o usa i pulsanti rapidi!
```

### Stato completo della casa

```
Tu:        dimmi lo stato della casa

HomeMind:  🏠 Casa occupata: Agostino (casa), Rosa (fuori)
           🔒 Allarme: Disarmato
           💡 Luci accese: soggiorno, cucina (2 totali)
           🌡️ Temperatura media: 21.5°C
           ⚡ FV: 2.4 kW | Consumo: 1.1 kW | Batteria: 78%
           🤖 via Gemini (Google) 🆓
```

### Generare una card

```
Tu:        crea card gauge: sensor.temperatura_soggiorno

HomeMind:  ✅ Card generata:

           type: gauge
           entity: sensor.temperatura_soggiorno
           name: Temperatura Soggiorno
           min: 0
           max: 40
           severity:
             green: 18
             yellow: 26
             red: 30

           🤖 via Gemini (Google) 🆓
```

### Verifica provider AI

```
Tu:        /providers

HomeMind:  🤖 Test AI Provider

           🥇 ✅ Gemini (Google) 🆓
              gemini-2.0-flash · Risposta: OK

           🥈 ✅ Groq/Llama 🆓
              llama-3.3-70b-versatile · Risposta: OK

           🥉 ✅ Cerebras 🆓
              llama3.1-8b · Risposta: OK

           ⚡ Attivo ora: Gemini (Google) 🆓
```

### Cambio lingua

```
Tu:        /lingua en
HomeMind:  ✅ Language set to English

Tu:        what lights are on?
HomeMind:  💡 Lights on: Living room, Kitchen
           🤖 via Groq/Llama 🆓
```

---

## 📁 Struttura file

```
/config/homemind_patches/           ← Cartella configurazione (creata automaticamente)
├── person_config.json              ← Filtri, energie, lingua (opzionale, vedi sopra)
├── spazzatura.pdf                  ← PDF calendario raccolta rifiuti
├── spazzatura_calendario.json      ← Calendario estratto (auto-generato)
└── *.yaml                          ← Patch configurazione HA (generate da HomeMind)

/data/options.json                  ← Opzioni add-on (gestite da HA)
```

---

## ❓ FAQ

**Il bot non risponde**
→ Verifica `telegram_bot_token` e `telegram_chat_id` nelle Opzioni.
→ Assicurati che il bot sia attivo scrivendo `/start` a @BotFather.
→ Il `telegram_chat_id` si ottiene scrivendo a [@userinfobot](https://t.me/userinfobot).

**"Nessun provider AI disponibile"**
→ Inserisci almeno una API key nelle Opzioni.
→ Usa `/providers` per vedere quale provider ha problemi.

**L'allarme si arma/disarma da solo**
→ È il comportamento corretto. HomeMind arma quando tutti escono.
→ Per disabilitare: aggiungi le tue persone in `person_blacklist`.

**`person.mqtt` viene rilevato come persona**
→ Aggiungilo in `person_blacklist` nelle Opzioni oppure in `person_config.json`.

**La card generata non funziona**
→ Controlla che l'`entity_id` esista (HA → Strumenti di sviluppo → Stati).
→ Per mushroom/bubble installa prima i plugin HACS.

**Il PDF spazzatura non viene letto**
→ Assicurati che il PDF non sia protetto da password.
→ Riprova con `/ricarica_spazzatura`.
→ In alternativa crea manualmente il file JSON.

**HomeMind usa sempre Groq invece di Gemini**
→ Gemini ha raggiunto la quota giornaliera (1.500 req). Si resetta il giorno dopo.
→ Usa `/providers` per vedere l'errore esatto.

---

---

# 🇬🇧 English

HomeMind is a **Home Assistant add-on** that brings an AI agent to your home. It monitors sensors, anomalies, and security, and replies to you on **Telegram** in natural language. It generates Lovelace cards, analyzes energy, manages your alarm, and sends you a morning briefing every day.

---

## 📋 Table of Contents

- [Features](#-features)
- [Installation](#-installation-1)
- [Configuration](#-configuration-1)
- [AI Providers](#-ai-providers--which-one-to-choose)
- [Telegram Bot — Commands](#-telegram-bot--all-commands)
- [Person & Sensor Filters](#-person--sensor-filters)
- [Generating Lovelace Cards](#-generating-lovelace-cards)
- [Waste Collection Calendar](#-waste-collection-calendar)
- [Language](#-language)
- [Practical Examples](#-practical-examples)
- [File Structure](#-file-structure-1)
- [FAQ](#-faq-1)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 💬 **AI Chat** | Ask questions about your home in natural language via Telegram |
| 🔒 **Security** | Auto arm/disarm alarm, motion notifications, welcome-home messages |
| ⚡ **Energy** | Solar, battery, grid analysis, daily/yesterday reports |
| 🎨 **Lovelace Cards** | Generate ready-to-use YAML cards (mushroom, gauge, bubble, tile) |
| 🔍 **Anomaly Detection** | Detects sensors with impossible values, forgotten lights, etc. |
| 🛠️ **YAML Patches** | Generates and applies HA config patches to fix anomalies |
| 🌅 **Morning Briefing** | AI report at 07:00 with energy, weather, trash, nightly anomalies |
| 🗑️ **Waste Collection** | Upload municipal PDF calendar → automatic evening reminders |
| 🔄 **Update Checker** | Checks HA and add-on updates every 6 hours |
| 🩺 **Repairs** | Checks official HA issues every 4 hours |
| 🤖 **Multi-provider AI** | Auto-fallback: Gemini → Groq → Cerebras → DeepSeek → Claude → OpenAI |
| 🌍 **Multilingual** | Italian and English, switch on the fly with `/lang en` |
| 📊 **Web Dashboard** | Chat interface at `http://IP:8099` with quick action buttons |

---

## 🚀 Installation

### 1. Add the repository

In Home Assistant: **Settings → Add-ons → Store → ⋮ → Repositories**

Add your GitHub URL:
```
https://github.com/YOUR_USER/homemind-orchestrator
```

### 2. Install

Search for **HomeMind Orchestrator** and click **Install**.

### 3. Minimum configuration

**Settings → Add-ons → HomeMind → Configuration**:

```yaml
gemini_api_key: "AIzaSy..."
telegram_bot_token: "123456:ABC..."
telegram_chat_id: "360307101"
```

### 4. Start

Click **Start**. Within 10 seconds you'll receive your first Telegram message.

---

## ⚙️ Configuration

### AI Providers

```yaml
gemini_api_key: "AIzaSy..."         # 🟦 Google Gemini — FREE 1500/day
gemini_model: "gemini-2.0-flash"

groq_api_key: "gsk_..."             # ⚡ Groq — FREE 14400/day
groq_model: "llama-3.3-70b-versatile"

cerebras_api_key: "csk-..."         # 🧠 Cerebras — FREE 1M tokens/min
cerebras_model: "llama3.1-8b"       # or: gpt-oss-120b

deepseek_api_key: "sk-..."          # 🔵 DeepSeek — nearly free
deepseek_model: "deepseek-chat"

claude_api_key: "sk-ant-..."        # 🟠 Claude — paid
claude_model: "claude-3-5-haiku-20241022"

openai_api_key: "sk-..."            # 🟢 OpenAI — paid
openai_model: "gpt-4o-mini"

ai_provider_order: "gemini,groq,cerebras,deepseek,claude,openai"
```

### Telegram

```yaml
telegram_bot_token: "..."    # From @BotFather
telegram_chat_id: "..."      # From @userinfobot
```

### Filters

```yaml
person_blacklist: "person.mqtt"
motion_blacklist: "binary_sensor.phone_motion"
```

---

## 🤖 AI Providers — Which One to Choose?

> Recommendation: activate at least **Gemini + Groq**. HomeMind switches automatically if one fails.

| Provider | Cost | Free Limit | Link |
|----------|------|------------|------|
| 🟦 **Google Gemini** | Free | 1,500 req/day | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ **Groq** | Free | 14,400 req/day | [console.groq.com](https://console.groq.com) |
| 🧠 **Cerebras** | Free | 1M tokens/min | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 **DeepSeek** | ~Free | $0.014/1M tokens | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟠 **Claude** | Paid | — | [console.anthropic.com](https://console.anthropic.com) |
| 🟢 **OpenAI** | Paid | — | [platform.openai.com](https://platform.openai.com) |

### How to get free API keys

**Gemini** → [aistudio.google.com](https://aistudio.google.com) → Sign in with Google → **Get API key** → key starts with `AIzaSy...`

**Groq** → [console.groq.com](https://console.groq.com) → Free account → **API Keys** → key starts with `gsk_...`

**Cerebras** → [cloud.cerebras.ai](https://cloud.cerebras.ai) → Free account → **API Keys** → key starts with `csk-...` · Models: `llama3.1-8b` or `gpt-oss-120b`

**DeepSeek** → [platform.deepseek.com](https://platform.deepseek.com) → Account gets $5 free credits → **API Keys**

---

## 💬 Telegram Bot — All Commands

### General

| Command | Description |
|---------|-------------|
| `/start` · `hello` | Welcome message |
| `/commands` | All commands |
| `/status` | Full home status |
| `/briefing` | Immediate AI briefing |
| `/providers` | Live test all AI providers |
| `/lang it` · `/lang en` | Switch language |

### Security

| Command | Description |
|---------|-------------|
| `/alarm` | Current alarm status |
| `who is home?` | People at home |
| `where is [name]?` | Person location |

### Energy

| Command | Description |
|---------|-------------|
| `/energy` | Today's energy report |
| `/yesterday` | Yesterday's report |

### Lovelace Cards

| Example | Generates |
|---------|-----------|
| `create card gauge: sensor.temperature_living` | Gauge card |
| `create card lights` | All lights mushroom card |
| `create card energy` | Solar/battery card |
| `create card security` | Security/motion card |
| `create card tile: all temperatures` | All thermometers |

### Maintenance

| Command | Description |
|---------|-------------|
| `/updates` | Check HA updates |
| `/repairs` | Official HA issues |
| `/trash` | Next waste collection |
| `/reload_trash` | Reload PDF calendar |

### Free chat examples

```
How many lights are on?
What's the temperature in the living room?
Any sensor anomalies?
Analyze yesterday's energy consumption
Where is John?
Suggest HA configuration improvements
```

---

## 👤 Person & Sensor Filters

### Basic (in add-on Options)

```yaml
person_blacklist: "person.mqtt,person.guest"
motion_blacklist: "binary_sensor.phone_motion"
```

### Advanced — `person_config.json`

Create `/config/homemind_patches/person_config.json`:

```json
{
  "person_whitelist": ["person.john", "person.mary"],
  "person_blacklist": ["person.mqtt"],
  "motion_whitelist": [
    "binary_sensor.entrance_pir",
    "binary_sensor.living_room_pir"
  ],
  "motion_blacklist": [
    "binary_sensor.phone_motion",
    "binary_sensor.test_sensor"
  ],
  "contact_blacklist": ["binary_sensor.contact_door"],
  "proximity_sensors": {
    "person.john": {
      "sensor": "sensor.home_distance",
      "threshold_m": 100
    }
  },
  "energy_sensors": {
    "produzione_fv": "sensor.solar_production",
    "consumo_casa":  "sensor.daily_energy",
    "rete_enel":     "sensor.grid_import",
    "batteria_wh":   "sensor.battery_wh"
  },
  "language": "en"
}
```

### Field reference

| Field | Behavior |
|-------|----------|
| `person_whitelist` | **Only** these people are tracked. Empty = auto-detect all |
| `person_blacklist` | Always ignore these (e.g. MQTT virtual persons) |
| `motion_whitelist` | **Only** these sensors used for security. Empty = use all |
| `motion_blacklist` | Always ignore these (e.g. phone sensors) |
| `contact_blacklist` | Exclude these door/contact sensors from alarm |
| `proximity_sensors` | Distance sensor for arrival/departure detection |
| `energy_sensors` | Map your sensors to HomeMind energy roles |

### Alarm logic

```
Everyone leaves        → arm alarm
Someone returns        → disarm (20s debounce)
Everyone away + motion → ALARM (needs ≥2 sensors within 45s)
Open contacts at arm   → Telegram warning
```

---

## 🎨 Generating Lovelace Cards

### Available styles

| Style | Aliases | Requires HACS |
|-------|---------|----------------|
| `mushroom` | `lights`, `security` | ✅ Yes |
| `gauge` | `chart`, `graph` | ❌ No |
| `tile` | `minimal` | ❌ No |
| `bubble` | — | ✅ Yes |
| `energy` | — | ❌ No |

### Examples

```
create card gauge: sensor.temperature_living_room
create card lights
create card energy
create card security
create card tile: all temperatures
```

### Installing the YAML

1. Copy the YAML from Telegram
2. HA → **Dashboard** → pencil icon → **Edit**
3. **+ Add card** → **Manual** → paste YAML → Save

---

## 🗑️ Waste Collection Calendar

### Method 1 — Browser upload

Open `http://HA-IP:8099/spazzatura` → drag and drop your PDF.

### Method 2 — File

Copy PDF to `/config/homemind_patches/spazzatura.pdf` → type `/reload_trash`.

### Evening notification example

```
🗑️ Tomorrow's collection:
   ♻️ Plastic
   🔩 Metals
```

### Manual JSON format

`/config/homemind_patches/spazzatura_calendario.json`:

```json
{
  "2026-03-09": ["Organic"],
  "2026-03-11": ["Paper", "Cardboard"],
  "2026-03-13": ["Plastic", "Metals"],
  "2026-03-16": ["General waste"],
  "2026-03-18": ["Glass"]
}
```

---

## 🌍 Language

```
/lang it   → Switch to Italian
/lang en   → Switch to English
/lang      → Show current language
```

---

## 📚 Practical Examples

### First startup

```
You:       /start
HomeMind:  Hello! HomeMind active 🧠 — 1596 entities, 2 people found.
```

### Home status

```
You:       what's the home status?
HomeMind:  🏠 Home occupied: John (home), Mary (away)
           🔒 Alarm: Disarmed
           💡 Lights on: 2 (living room, kitchen)
           🌡️ Living room: 21.5°C
           ⚡ Solar: 2.4 kW | Usage: 1.1 kW | Battery: 78%
           🤖 via Gemini (Google) 🆓
```

### Exclude a phone motion sensor

```json
{ "motion_blacklist": ["binary_sensor.iphone_motion"] }
```

### Use only specific sensors for security

```json
{
  "motion_whitelist": [
    "binary_sensor.entrance_pir",
    "binary_sensor.living_room_pir"
  ]
}
```

---

## 📁 File Structure

```
/config/homemind_patches/
├── person_config.json         ← Filters, energy, language (optional)
├── spazzatura.pdf             ← Municipal waste PDF
├── spazzatura_calendario.json ← Extracted calendar (auto-generated)
└── *.yaml                     ← HA config patches (auto-generated)
```

---

## ❓ FAQ

**Bot doesn't respond**
→ Check `telegram_bot_token` and `telegram_chat_id` in Options.
→ Get your chat ID from [@userinfobot](https://t.me/userinfobot).

**"No AI provider available"**
→ Enter at least one API key in Options.
→ Use `/providers` to see which provider has issues.

**Alarm arms/disarms by itself**
→ Expected! HomeMind arms when everyone leaves.
→ To disable: add everyone to `person_blacklist`.

**`person.mqtt` detected as a person**
→ Add it to `person_blacklist` in Options or `person_config.json`.

**Generated card doesn't work**
→ Check the `entity_id` exists (Developer Tools → States).
→ Install HACS plugins for mushroom/bubble cards.

**PDF not being read**
→ Make sure the PDF isn't password-protected.
→ Try `/reload_trash` or create the JSON manually.

**Always using Groq instead of Gemini**
→ Gemini hit its daily quota. Resets the next day.
→ Use `/providers` to see the exact error.

---

<div align="center">

Made with ❤️ for Home Assistant

</div>
