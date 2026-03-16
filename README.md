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
</p>

---

## 📋 Indice

- [Cos'è HomeMind](#-cosè-homemind)
- [Come funziona](#-come-funziona)
- [Installazione](#-installazione)
- [Il file di configurazione](#-il-file-di-configurazione)
- [Configurazione BASE](#-configurazione-base--partire-in-5-minuti)
- [Configurazione MEDIA](#-configurazione-media--funzionalità-complete)
- [Configurazione AVANZATA](#-configurazione-avanzata--tutto-attivo)
- [Moduli e funzionalità](#-moduli-e-funzionalità)
  - [🔒 Sicurezza & Allarme](#-sicurezza--allarme)
  - [👤 Presenza & Prossimità GPS](#-presenza--prossimità-gps)
  - [⚡ Monitor Elettrodomestici](#-monitor-elettrodomestici)
  - [☀️ Ottimizzatore Solare](#️-ottimizzatore-solare)
  - [📊 Analisi Energetica](#-analisi-energetica)
  - [🌅 Briefing Mattutino](#-briefing-mattutino)
  - [🗑️ Calendario Spazzatura](#️-calendario-spazzatura)
  - [🤖 Controllo AI via Telegram](#-controllo-ai-via-telegram)
- [Comandi Telegram](#-comandi-telegram)
- [FAQ & Problemi comuni](#-faq--problemi-comuni)

---

## 🧠 Cos'è HomeMind

HomeMind è un **add-on per Home Assistant** che aggiunge un cervello AI alla tua casa. Non è una semplice automazione — è un agente che capisce il contesto, impara la tua routine e ti avvisa solo quando serve davvero.

**Parlagli su Telegram in italiano naturale:**
> *"Accendi la luce del salotto"*
> *"Quanta energia ho prodotto oggi?"*
> *"Arma l'allarme"*
> *"Cosa succede in casa?"*

**Lui capisce, risponde e agisce.**

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
| 🚨 **Allarme intrusione** | Rilevamento movimento in casa con allarme armato |

---

## ⚙️ Come funziona

```
Home Assistant  ──→  HomeMind  ──→  Telegram
    (sensori)        (cervello AI)    (tu)
```

HomeMind si connette a Home Assistant tramite WebSocket, legge tutti i sensori in tempo reale, li elabora con AI e ti comunica solo le cose importanti. Non hai bisogno di toccare nulla in HA — tutto avviene tramite HomeMind.

---

## 🚀 Installazione

### 1. Aggiungi il repository

In Home Assistant:
```
Impostazioni → Add-on Store → ⋮ (menu tre puntini) → Repositories
→ Incolla l'URL del repository HomeMind → Aggiungi → https://github.com/ago19800/HomeMind

```

### 2. Installa e configura l'add-on
### Provider AI

```yaml
gemini_api_key: "AIzaSy..."         # 🟦 Google Gemini — GRATIS 1500/giorno
gemini_model: "gemini-2.0-flash"

groq_api_key: "gsk_..."             # ⚡ Groq — GRATIS 14400/giorno
groq_model: "llama-3.3-70b-versatile"

deepseek_api_key: "sk-..."          # 🔵 DeepSeek — quasi gratis
deepseek_model: "deepseek-chat"

cerebras_api_key: "csk-..."         # 🧠 Cerebras — GRATIS 1M token/min
cerebras_model: "llama3.1-8b"       # oppure: gpt-oss-120b

claude_api_key: "sk-ant-..."        # 🟠 Anthropic Claude — a pagamento
claude_model: "claude-3-5-haiku-20241022"

openai_api_key: "sk-..."            # 🟢 OpenAI — a pagamento
openai_model: "gpt-4o-mini"

ai_provider_order: "gemini,groq,cerebras,deepseek,claude,openai"
```

> Lascia vuoto il campo per disabilitare un provider. HomeMind usa solo quelli con API key.

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
Nella scheda **Configurazione** dell'add-on imposta:

```yaml

telegram_token: "token_del_tuo_bot_telegram"
telegram_chat_id: "il_tuo_chat_id"
alarm_code: "1234"
gemini_api_key: "chiave_gemini_opzionale"
```

> **Come ottenere il token HA:** Profilo → Token di accesso a lunga durata → Crea token

> **Come ottenere token Telegram:** Cerca @BotFather su Telegram → `/newbot`

> **Come trovare il tuo Chat ID:** Cerca @userinfobot su Telegram → manda `/start`

### 3. Crea il file di configurazione personale

Crea il file `/config/homemind_patches/person_config.json` — questo è il file dove dici a HomeMind quali sono i **tuoi** dispositivi.

---

## 📁 Il file di configurazione

Il file si chiama `person_config.json` e si trova in:
```
/config/homemind_patches/person_config.json
```

È un file **JSON** — un formato semplice con `{` chiavi `}` e valori. Ogni sezione attiva una funzionalità diversa. Se una sezione manca, quella funzionalità è semplicemente disattivata.

### Come trovare gli entity_id dei tuoi dispositivi

In Home Assistant:
```
Strumenti Sviluppatore → Stati → cerca il nome del dispositivo
```
L'**entity_id** è il codice tipo `sensor.temperatura_soggiorno` o `binary_sensor.porta_ingresso`.

---

## 🟢 Configurazione BASE — Partire in 5 minuti
### 4. Avvia l'add-on

Clicca **Avvia**. Entro 10 secondi ricevi il primo messaggio su Telegram.

---

## ⚙️ Configurazione

La configurazione minima per avere HomeMind funzionante con le funzioni essenziali: presenza, allarme automatico e controllo AI.

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

**Con questa configurazione hai:**
- ✅ HomeMind parla italiano
- ✅ Monitora la presenza di Mario e Lucia
- ✅ Allarme si arma quando tutti escono
- ✅ Allarme si disarma quando qualcuno rientra
- ✅ Rilevamento movimento con allarme armato
- ✅ Controllo AI via Telegram (linguaggio naturale)
- ✅ Briefing mattutino alle 7:00

**Come trovare le persone:**
```
Strumenti Sviluppatore → Stati → cerca "person."
```
Vedrai `person.mario`, `person.lucia` ecc.

**Come trovare i sensori movimento:**
```
Strumenti Sviluppatore → Stati → cerca "occupancy" o "motion"
```

---

## 🟡 Configurazione MEDIA — Funzionalità complete

Aggiunge: prossimità GPS precisa, sensori contatto, elettrodomestici e energia.

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
    "binary_sensor.sensore_movimento_ingresso",
    "binary_sensor.sensore_movimento_soggiorno",
    "binary_sensor.sensore_movimento_cucina"
  ],

  "motion_blacklist": [
    "binary_sensor.telefono_mario_motion",
    "binary_sensor.sensore_test"
  ],

  "contact_blacklist": [
    "binary_sensor.porta_garage"
  ],

  "proximity_sensors": {
    "person.mario": {
      "sensor": "sensor.casa_telefono_mario_distance",
      "threshold_m": 100,
      "stale_check": true
    }
  },

  "energy_sensors": {
    "produzione_fv":   "sensor.fv_tot",
    "consumo_casa":    "sensor.consumi_giornalieri",
    "rete_enel":       "sensor.enel_giornaliero",
    "batteria_wh":     "sensor.batteria_wh"
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

**In più rispetto alla BASE:**
- ✅ **Prossimità GPS** — usa il sensore distanza del telefono per sapere esattamente quando sei vicino a casa, evitando falsi allarmi da GPS che salta
- ✅ **Sensori contatto** — porte e finestre monitorate (con blacklist per quelle sempre aperte)
- ✅ **Monitor lavatrice** — notifica quando finisce
- ✅ **Monitor lavastoviglie** — notifica quando finisce
- ✅ **Analisi energetica** — confronto consumi giornalieri

### Spiegazione dei campi importanti

#### `person_blacklist`
Persone da ignorare completamente — utile per entità "fantasma" create da MQTT o altri sistemi.

#### `motion_blacklist`
Sensori di movimento da ignorare — tipicamente il sensore del telefono (si attiva sempre), sensori di test o telecamere PTZ.

#### `contact_blacklist`
Porte/finestre da NON monitorare — es. garage sempre aperto, finestra tenuta aperta di proposito.

#### `proximity_sensors`
Il sensore distanza GPS più preciso. Se non ce l'hai, HomeMind usa solo il GPS nativo di HA.

| Campo | Descrizione | Default |
|-------|-------------|---------|
| `sensor` | Entity ID del sensore distanza | — |
| `threshold_m` | Distanza in metri per "a casa" | 100 |
| `stale_check` | `true` = smette di considerare il sensore se i dati sono vecchi, `false` = usa sempre l'ultimo valore anche se vecchio | true |

> **`stale_check: false`** è utile se il tuo telefono non aggiorna spesso il GPS — HomeMind userà l'ultimo valore valido anche dopo ore.

#### Modalità elettrodomestici

**`mode: "power"`** — per elettrodomestici su presa smart con misura di potenza:
```json
"power_sensor": "sensor.presa_lavatrice_power",
"power_on_threshold": 50,    ← inizia ciclo quando supera 50W
"power_off_threshold": 10,   ← fine ciclo quando scende sotto 10W
"min_cycle_minutes": 20,     ← ciclo minimo valido (evita falsi start)
"max_idle_minutes": 5        ← tolleranza pause durante il ciclo
```

**`mode: "smart"`** — per elettrodomestici con sensore stato nativo (es. Bosch Home Connect):
```json
"state_sensor": "sensor.lavastoviglie_operation_state",
"running_states": ["Run"],
"done_states": ["Finished", "Ready"]
```

---

## 🔴 Configurazione AVANZATA — Tutto attivo

Aggiunge: ottimizzatore solare con auto-avvio, sensori W istantanei, più elettrodomestici.

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
    "binary_sensor.sensore_movimento_ingresso",
    "binary_sensor.sensore_movimento_soggiorno",
    "binary_sensor.sensore_movimento_cucina",
    "binary_sensor.sensore_movimento_garage"
  ],

  "motion_blacklist": [
    "binary_sensor.telefono_mario_motion",
    "binary_sensor.sensore_test"
  ],

  "contact_blacklist": [
    "binary_sensor.porta_garage"
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
    },
    "forno": {
      "enabled": true,
      "name": "Forno",
      "icon": "🔥",
      "mode": "power",
      "power_sensor": "sensor.presa_forno_power",
      "power_on_threshold": 500,
      "power_off_threshold": 30,
      "min_cycle_minutes": 10,
      "max_idle_minutes": 3,
      "notify_on_start": true
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
      },
      "pompa_piscina": {
        "enabled": true,
        "switch": "switch.pompa_piscina",
        "min_surplus_w": 400,
        "auto_start": true
      }
    }
  }
}
```

**In più rispetto alla MEDIA:**
- ✅ **Sensori W istantanei** — calcolo surplus solare preciso al watt (nessuna derivata)
- ✅ **Ottimizzatore solare attivo** — ti avvisa quando c'è surplus FV
- ✅ **Conferma via Telegram** — rispondi "sì" per avviare
- ✅ **Auto-start** per dispositivi come pompe (partono da soli, senza chiedere)
- ✅ **Asciugatrice e forno** monitorati

---

## 📦 Moduli e funzionalità

### 🔒 Sicurezza & Allarme

HomeMind gestisce l'allarme in modo completamente automatico.

**Armo automatico:**
```
Tutti escono di casa → HomeMind aspetta 30 secondi → Arma l'allarme
```

**Disarmo automatico:**
```
Qualcuno si avvicina a casa → HomeMind rileva → Disarma prima che entri
```

**Rilevamento intrusione:**
```
Allarme armato + movimento rilevato → Notifica immediata su Telegram
```

**Sensori contatto:**
```
Porta/finestra aperta con allarme armato → Avviso
Porta aperta durante armamento → Avviso (non blocca l'armamento)
```

> Le porte in `contact_blacklist` vengono ignorate completamente — utile per porte che restano spesso aperte.

---

### 👤 Presenza & Prossimità GPS

HomeMind sa sempre chi è in casa usando due livelli di rilevamento:

**Livello 1 — GPS nativo HA:** `person.mario` = home / not_home

**Livello 2 — Sensore distanza (opzionale):** Distanza precisa in metri dal telefono

Quando hai il sensore distanza configurato, **la distanza vince sempre sul GPS**. Questo risolve il problema classico del GPS che "salta" e arma l'allarme mentre sei ancora in casa.

```
Sensore dice 45m → sei a casa (anche se GPS dice "not_home")
Sensore dice 1200m → sei fuori (anche se GPS dice "home")
```

**`stale_check`:** controlla se i dati del sensore sono freschi.
- `true` (consigliato per chi ha buon GPS) → dopo 5 minuti senza aggiornamento torna al GPS
- `false` (consigliato se il GPS del telefono è pigro) → usa sempre l'ultimo valore valido

---

### ⚡ Monitor Elettrodomestici

HomeMind sa quando gli elettrodomestici partono e finiscono, e ti avvisa su Telegram.

**Notifica fine ciclo:**
```
Lavatrice finita → "🫧 Lavatrice terminata! Ciclo durato 1h 23min."
```

**Due modalità:**

**POWER** — per prese smart con misura potenza (Zigbee, Shelly, Tasmota):
```json
"mode": "power",
"power_sensor": "sensor.presa_lavatrice_power",
"power_on_threshold": 50,    ← sopra = sta girando
"power_off_threshold": 10,   ← sotto = ha finito
"min_cycle_minutes": 20,     ← ignora accensioni brevi (es. standby)
"max_idle_minutes": 5        ← tolleranza per pause di centrifuga
```

**SMART** — per elettrodomestici connessi (Bosch, Siemens, Miele via Home Connect):
```json
"mode": "smart",
"state_sensor": "sensor.lavastoviglie_operation_state",
"running_states": ["Run"],
"done_states": ["Finished", "Ready"]
```

**`notify_on_start: true`** → ricevi notifica anche all'avvio (default: false)

---

### ☀️ Ottimizzatore Solare

HomeMind monitora il surplus fotovoltaico in tempo reale e ti suggerisce quando è il momento migliore per avviare gli elettrodomestici pesanti.

**Come funziona:**
```
Ogni 2 minuti controlla:
  produzione FV - consumo casa = surplus

Se surplus ≥ soglia per X minuti consecutivi:
  → Notifica Telegram con l'elettrodomestico suggerito

Tu rispondi "sì" → HomeMind accende la presa (se configurata)
```

**Parametri principali:**

| Campo | Descrizione | Default |
|-------|-------------|---------|
| `enabled` | Attiva/disattiva tutto | false |
| `min_surplus_w` | Surplus minimo generale in Watt | 500 |
| `confirm_minutes` | Minuti di surplus stabile prima di notificare | 5 |
| `cooldown_hours` | Ore minime tra una notifica e l'altra | 2 |

**Parametri per singolo elettrodomestico:**

| Campo | Descrizione |
|-------|-------------|
| `enabled` | Includi questo elettrodomestico |
| `switch` | Entity ID presa smart da accendere (null = solo notifica) |
| `min_surplus_w` | Soglia surplus specifica per questo elettrodomestico |
| `auto_start` | `true` = parte da solo, `false` = chiede conferma |

**Sensori W istantanei (raccomandati):**
Se hai sensori che misurano Watt in tempo reale (inverter, Shelly EM), aggiungili nella sezione `energy_sensors` con suffisso `_w`:
```json
"produzione_fv_w": "sensor.fotovoltaica_totale",
"consumo_casa_w":  "sensor.inverter_ac_output_power",
"rete_enel_w":     "sensor.shelly_channel_1_power"
```
Senza di essi HomeMind usa i sensori kWh giornalieri con calcolo a derivata (meno preciso ma funziona).

**Comandi Telegram:**
- `/solare` — mostra surplus attuale, elettrodomestici configurati e conferme in attesa

---

### 📊 Analisi Energetica

Ogni mattina alle 7:15 (dopo il briefing) HomeMind confronta i consumi di ieri con la media storica degli ultimi 30 giorni. Se trova anomalie te lo dice con una spiegazione AI.

**Esempio notifica:**
```
⚡ Analisi energetica ieri

☀️ Produzione FV: 12.4 kWh (+23% rispetto alla media)
🏠 Consumo casa: 18.2 kWh (+45% ⚠️ anomalia)
🔌 Prelievo rete: 8.1 kWh

💡 Il consumo di ieri è stato insolitamente alto.
   Possibile causa: condizionatore acceso tutto il giorno
   o elettrodomestico rimasto in standby inutilmente.
```

**Sensori supportati:**
```json
"energy_sensors": {
  "produzione_fv":   "sensor.nome_sensore_kwh_fv",
  "consumo_casa":    "sensor.nome_sensore_kwh_casa",
  "rete_enel":       "sensor.nome_sensore_kwh_enel",
  "batteria_wh":     "sensor.nome_sensore_batteria"
}
```

---

### 🌅 Briefing Mattutino

Ogni mattina alle 7:00 HomeMind ti manda un riepilogo completo:

```
🌅 Buongiorno Mario!

🌤️ Meteo: Sole, 18°C - massima 24°C
   Nessuna pioggia prevista oggi.

⚡ Energia ieri:
   ☀️ Prodotto: 11.2 kWh
   🏠 Consumato: 7.8 kWh
   ✅ Autosufficienza: 100%

🗑️ Spazzatura stasera: Plastica e metallo

💡 Consiglio del giorno:
   Ottima giornata di sole prevista — 
   considera di avviare la lavatrice tra le 11 e le 14.
```

**Si attiva automaticamente** senza configurazione. Usa i sensori energetici se configurati.

**Per riceverlo subito:** scrivi `/briefing` su Telegram.

---

### 🗑️ Calendario Spazzatura

HomeMind ti ricorda ogni sera alle 12:00 (mezzanotte) cosa mettere fuori per il giorno dopo.

**Per attivarlo:**
1. Carica il file PDF del calendario raccolta nel percorso:
   ```
   /config/homemind_patches/spazzatura.pdf
   ```
2. Scrivi `/ricarica_spazzatura` su Telegram
3. HomeMind legge il PDF con AI e crea il calendario automaticamente

**Oppure** crea manualmente il file JSON:
```
/config/homemind_patches/spazzatura_calendario.json
```

**Comando:** `/spazzatura` — mostra raccolta prossimi 7 giorni.

---

### 🤖 Controllo AI via Telegram

Puoi scrivere qualsiasi cosa in italiano e HomeMind capisce e risponde. Non servono comandi precisi.

**Esempi di controllo:**
```
"Accendi la luce cucina"
"Spegni tutte le luci"
"Metti la temperatura a 21 gradi"
"Arma l'allarme"
"Disarma l'allarme"
"Apri le tapparelle"
```

**Esempi di domande:**
```
"Cosa succede in casa?"
"Chi è a casa?"
"Quanta energia ho prodotto oggi?"
"La lavatrice sta girando?"
"Quando è tornato Mario ieri?"
```

**AI con fallback automatico:**
HomeMind usa fino a 3 provider AI in cascata — se uno non risponde passa automaticamente al prossimo:
1. Gemini (Google) — gratuito
2. Groq/Llama — gratuito
3. Cerebras — gratuito

---

## 📱 Comandi Telegram

Scrivi questi comandi direttamente nella chat con il bot:

### Info Casa
| Comando | Descrizione |
|---------|-------------|
| `/stato` | Stato completo: persone, sensori, allarme |
| `/allarme` | Stato attuale dell'allarme |
| `/energia` | Produzione FV e consumi di oggi |
| `/ieri` | Produzione e consumi di ieri |
| `/solare` | Surplus FV in tempo reale e ottimizzatore |

### Elettrodomestici
| Comando | Descrizione |
|---------|-------------|
| `/elettrodomestici` | Stato di lavatrice, lavastoviglie ecc. |
| `lavatrice` | Stato rapido lavatrice |
| `lavastoviglie` | Stato rapido lavastoviglie |

### Spazzatura
| Comando | Descrizione |
|---------|-------------|
| `/spazzatura` | Raccolta prossimi 7 giorni |
| `/ricarica_spazzatura` | Rileggi PDF calendario |

### Sistema
| Comando | Descrizione |
|---------|-------------|
| `/briefing` | Ricevi subito il briefing mattutino |
| `/aggiornamenti` | Controlla aggiornamenti disponibili HA |
| `/riparazioni` | Problemi segnalati da Home Assistant |
| `/providers` | Provider AI attivi e catena fallback |
| `/comandi` | Questa lista |

### Lingua
| Comando | Descrizione |
|---------|-------------|
| `/lingua it` | Passa all'italiano |
| `/lingua en` | Switch to English |

---

## ❓ FAQ & Problemi comuni

**L'allarme si arma mentre sono ancora in casa**
→ Aggiungi il sensore di prossimità GPS in `proximity_sensors`. Con il sensore distanza HomeMind sa esattamente dove sei.

**HomeMind mi considera assente anche se sono in casa**
→ Controlla che la tua entità `person.nome` sia nella `person_whitelist`. Verifica in HA che lo stato sia "home".

**Il sensore movimento del telefono fa scattare l'allarme**
→ Aggiungi `binary_sensor.nomeTelefono_motion` nella `motion_blacklist`.

**La lavatrice notifica che ha finito troppo presto / tardi**
→ Aggiusta `min_cycle_minutes` (aumenta se notifica troppo presto) e `max_idle_minutes` (aumenta se notifica prima della fine reale).

**Il surplus solare non supera mai la soglia**
→ Abbassa `min_surplus_w` nel `solar_optimizer`. Con pannelli da 3kW e consumi normali, 300-400W è una soglia realistica nei periodi nuvolosi.

**Non ricevo notifiche Telegram**
→ Verifica che il `telegram_chat_id` nella configurazione dell'add-on sia corretto. Usa @userinfobot per trovarlo.

**HomeMind riporta "Finestra bagno sempre aperta"**
→ Aggiungi quel sensore nella `contact_blacklist` per non ricevere avvisi su aperture intenzionali.

**Voglio testare senza che armi l'allarme**
→ In HA, metti l'allarme in modalità "disarmato" manualmente. HomeMind non armerà se è già in uno stato insolito.

---

<div align="center">

**HomeMind Orchestrator** — *La tua casa, finalmente intelligente.*

</div>
<div align="center">
☕ Supporta il Progetto

**Se questo addon ti è utile, offrimi un caffè!**

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

**[paypal.me/ago19800](https://paypal.me/ago19800)**

*Ogni donazione mi aiuta a continuare a sviluppare e migliorare questo addon!* 🙏

</div>
