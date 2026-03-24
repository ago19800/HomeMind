<div align="center">

# 🧠 HomeMind Orchestrator

**[🇮🇹 Italiano](#-italiano) · [🇬🇧 English](#-english)**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![Language](https://img.shields.io/badge/Lingua-Italiano%20%2F%20English-green)]()
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Groq%20%7C%20Cerebras%20%7C%20DeepSeek-orange)]()
[![Version](https://img.shields.io/badge/versione-1.4.3-brightgreen)](https://github.com/ago19800/HomeMind/releases)

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
- [Power Guard](#power-guard-it)
- [Clima e Riscaldamento](#clima-e-riscaldamento)
- [Climatizzatori SmartIR](#climatizzatori-smartir-it)
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
> *"Spegni scaldabagno alle ore 7:40"*
> *"Crea un'automazione che spenga le luci alle 23"*
> *"Analizza i log di HA e dimmi se ci sono errori"*

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
| ⚠️ **Power Guard** | Protegge dalla soglia contrattuale Enel |
| ⏰ **Task programmati** | Schedula azioni future in linguaggio naturale |
| ⚙️ **Config via chat** | Modifica la configurazione scrivendo su Telegram |
| 🔧 **Automazioni da Telegram** | Crea, modifica ed elimina automazioni HA via chat |
| 🩺 **Analisi Log AI** | Legge i log HA, trova errori e propone fix |
| 🎨 **Dashboard Lovelace AI** | Genera dashboard Lovelace su misura |

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
gemini_model:     "gemini-2.0-flash"

groq_api_key:     "gsk_..."     # Gratis 100k token/giorno → console.groq.com
groq_model:       "llama-3.3-70b-versatile"

cerebras_api_key: "csk_..."     # Gratis 1M token/min     → cloud.cerebras.ai
cerebras_model:   "llama3.1-8b"

deepseek_api_key: "sk-..."      # ~Gratis $0.014/1M token → platform.deepseek.com
deepseek_model:   "deepseek-chat"

claude_api_key:   "sk-ant-..."  # A pagamento → console.anthropic.com
claude_model:     "claude-3-5-haiku-20241022"

openai_api_key:   "sk-..."      # Solo per messaggi vocali → platform.openai.com
openai_model:     "gpt-4o-mini"

ai_provider_order: "gemini,groq,cerebras,deepseek,claude,openai"
```

| Provider | Costo | Limite | Link |
|----------|-------|--------|------|
| 🟦 **Gemini** | Gratis | 1.500 req/giorno | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ **Groq** | Gratis | 100k token/giorno | [console.groq.com](https://console.groq.com) |
| 🧠 **Cerebras** | Gratis | 1M token/min | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 **DeepSeek** | ~Gratis | $0.014/1M token | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟠 **Claude** | A pagamento | — | [console.anthropic.com](https://console.anthropic.com) |
| 🟢 **OpenAI** | A pagamento | $0.006/min audio | [platform.openai.com](https://platform.openai.com) |

> **Fallback automatico:** se Gemini è offline, HomeMind passa a Groq in 12 secondi, poi a Cerebras e così via. Non rimani mai senza risposta.

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
  "power_guard": {
    "enabled": true,
    "power_sensor": "sensor.consumo_casa_w",
    "threshold_w": 3000,
    "warning_pct": 90,
    "mode": "ask",
    "appliances_priority": [
      {"name": "Lavatrice",     "switch": "switch.presa_lavatrice"},
      {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie"},
      {"name": "Scaldabagno",   "switch": "switch.scaldabagno"}
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

| Marca | Configurazione |
|-------|---------------|
| **Risco** | `"alarm_panel": "alarm_control_panel.risco_casa"` |
| **Paradox** | `"alarm_panel": "alarm_control_panel.paradox_mg5050"` |
| **Ajax** | `"alarm_panel": "alarm_control_panel.ajax_hub"` |
| **DSC** | `"alarm_panel": "alarm_control_panel.dsc_alarmo"` |
| **Verisure** | `"alarm_panel": {"entity": "...", "arm_mode": "armed_home"}` |
| **HA default** | Non serve configurare nulla |

---

## Sensore Prossimità GPS

Evita falsi allarmi quando il GPS "salta". Se il **benvenuto non arriva**, abbassa la soglia a 50m.

```json
"proximity_sensors": {
  "person.mario": {
    "sensor": "sensor.casa_mario_distance",
    "threshold_m": 100,
    "stale_check": false
  }
}
```

> Il benvenuto arriva sempre se sei stato via più di 30 minuti, anche se il sensore proximity ha dati vecchi.

---

## Monitor Elettrodomestici

**Modalità POWER** (presa smart):
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

Monitora il surplus ogni 2 minuti. Rispondi **"sì"** su Telegram per avviare l'elettrodomestico.

```json
"solar_optimizer": {
  "enabled": true, "min_surplus_w": 500,
  "battery_soc_sensor": "sensor.batteria_percentuale",
  "battery_full_threshold": 95, "min_sun_elevation": 10
}
```

---

## Power Guard IT

Protegge la tua utenza dalla soglia contrattuale Enel. Quando il consumo si avvicina al limite, HomeMind notifica o spegne automaticamente gli elettrodomestici meno prioritari.

```json
"power_guard": {
  "enabled": true,
  "power_sensor": "sensor.consumo_casa_w",
  "threshold_w": 3000,
  "warning_pct": 90,
  "mode": "ask",
  "appliances_priority": [
    {"name": "Lavatrice",     "switch": "switch.presa_lavatrice"},
    {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie"},
    {"name": "Scaldabagno",   "switch": "switch.scaldabagno"}
  ]
}
```

| `mode` | Comportamento |
|--------|---------------|
| `warn_only` | Solo notifica, non spegne nulla |
| `ask` | Chiede conferma prima di spegnere **(consigliato)** |
| `auto` | Spegne automaticamente senza chiedere |

```
/powerguard   → stato attuale + barra consumo + elettrodomestici
/pg           → alias breve
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

```
"Accendi la caldaia a 22 gradi"  → accende switch + imposta 22°
"Spegni il riscaldamento"        → spegne switch
"Abbassa a 19 gradi"             → imposta 19°
```

---

## Climatizzatori SmartIR IT

HomeMind gestisce automaticamente i climatizzatori SmartIR senza errori 400.

**Rilevamento automatico** — se il clima ha `controller_data` negli attributi HA, funziona subito senza configurazione.

**Override manuale** — se ricevi ancora errori 400:
```json
"climate": {
  "climate.clima_sala": {
    "name": "Clima Sala",
    "type": "smartir"
  },
  "climate.clima_mansarda": {
    "name": "Clima Mansarda",
    "type": "smartir"
  }
}
```

| Tipo | Accendi | Spegni |
|------|---------|--------|
| **SmartIR** | `climate.turn_on` | `climate.turn_off` |
| **Standard** | `climate.set_hvac_mode heat` | `climate.set_hvac_mode off` |
| **Caldaia + switch** | `switch.turn_on` | `switch.turn_off` |

---

## Task Programmati IT

Schedula qualsiasi azione futura parlando in modo naturale su Telegram. I task sono temporanei (diversi dalle automazioni) e sopravvivono al riavvio.

**Come funziona:**
```
Tu: "Accendi faretti alle ore 21:00"
HomeMind: "⏰ Schedulato! Eseguirò alle 21:00"

Alle 21:00:
HomeMind: "⏰ Task eseguito! Accendi faretti alle ore 21:00"
→ faretti accesi ✅
```

**Pattern supportati IT e EN:**
```
"alle 19:00" / "alle ore 21:38"    → oggi o domani
"tra 30 minuti"                    → timer rapido
"tra 2 ore"                        → timer ore
"tra 3 giorni alle 19"             → tra N giorni
"domani alle 7"                    → domani
"venerdì alle 20"                  → giorno della settimana
"sabato mattina alle 8"            → sabato
"il 28 marzo alle 9"               → data specifica

"in 30 minutes" / "at 7pm"         → EN equivalents
"in 3 days at 7pm"                 → EN
"friday at 20:00"                  → EN
"march 28 at 9am"                  → EN
```

**Comandi:**
```
/task              → lista task in coda
/cancella_task 1   → cancella il task numero 1
```

---

## Configurazione via Chat IT

Modifica `person_config.json` scrivendo in linguaggio naturale su Telegram — senza aprire file, senza riavviare HomeMind.

**Comando:**
```
/config   → mostra configurazione attuale
```

**Esempi di modifica:**
```
"Aggiungi person.mario alla whitelist"
"Escludi person.awtrix"
"Cambia soglia Enel a 3500W"
"Power Guard modalità auto"
"Notifica spazzatura alle 21"
"Cambia lingua inglese"
"Soglia proximity 50 metri"
"Temperatura massima clima 28 gradi"
```

HomeMind mostra l'anteprima e chiede conferma:
```
⚙️ Modifica config rilevata:
Aggiungo person.mario alla whitelist persone

Applico questa modifica? (sì/no)
```

Backup automatico in `/config/homemind_patches/person_config.backup.json`.

**Modifiche supportate:**
| Cosa | Esempio |
|------|---------|
| Aggiungere persona | `Aggiungi person.mario alla whitelist` |
| Escludere persona | `Escludi person.awtrix` |
| Soglia Power Guard | `Cambia soglia Enel a 3500W` |
| Modalità Power Guard | `Power Guard modalità auto` |
| Orario spazzatura | `Notifica spazzatura alle 21` |
| Lingua | `Cambia lingua inglese` |
| Soglia proximity | `Soglia proximity 50 metri` |
| Temperatura max clima | `Temperatura massima clima 28 gradi` |

---

## Memoria Persistente

HomeMind impara le tue preferenze nel tempo.

**Automaticamente:**
```
Dici: "fa freddo, metti 22 gradi"
→ Salva: "Preferisce 22°C quando fa freddo"
→ La volta dopo imposta 22° senza che tu lo chieda
```

**Esplicitamente:**
```
"Ricordati che il cane si chiama Rex"
"Rosa lavora fuori il martedì e giovedì"
"Preferiamo luci calde la sera"
```

**Comandi:**
```
/memoria              → tutto ciò che HomeMind sa su di te
/dimentica caldaia    → rimuove i fatti contenenti "caldaia"
/memoria reset        → cancella tutto
```

> La memoria cambia le risposte in chat, non i comportamenti automatici.

---

## Routine Intelligente

Dopo **3 giorni** di osservazione, HomeMind inizia ad anticipare i tuoi bisogni.

```
HomeMind: "🏃 Di solito esci alle 08:30 — mancano 20 minuti.
           Vuoi che preparo la casa?"
"sì" → abbassa riscaldamento + spegne luci ✅
```

```
/routine → mostra orari tipici appresi
```

---

## Gestione Automazioni IT

Crea, modifica ed elimina automazioni HA direttamente da Telegram in linguaggio naturale.

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

HomeMind legge i log HA ogni 5 minuti e ti informa di errori critici con soluzione AI.

```
HomeMind: "⚠️ Errore critico in HA:
  [mqtt] Cannot connect to MQTT broker
  💡 Soluzione: Verifica che Mosquitto sia in esecuzione..."
```

Attivata di default — nessuna configurazione necessaria.

---

## Generatore Dashboard Lovelace IT

```
"genera la mia dashboard"
"crea una dashboard lovelace per le mie entità"
"genera dashboard e caricala su HA"
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
| `/automazioni` | Lista automazioni HA |
| `/powerguard` / `/pg` | Stato Power Guard e consumo |
| `/task` | Lista task programmati |
| `/cancella_task N` | Cancella task numero N |
| `/config` | Configurazione attuale |
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

**HomeMind non controlla il mio Risco/Verisure** → Aggiungi `"alarm_panel"` nel config.

**Il benvenuto non arriva** → Abbassa `threshold_m` a 50. Con la v1.6 funziona anche con proximity stale.

**Errore FAIL 500 sulla temperatura** → Controlla `max_temp` nel `configuration.yaml` di HA.

**SmartIR — errori 400** → Aggiungi `"type": "smartir"` nel blocco climate del config.

**Il task non esegue l'azione** → Verifica che il nome del dispositivo sia presente in HA. HomeMind usa la lista completa degli switch.

**Power Guard mostra app=0** → Usa `appliances_priority` invece di `appliances` e `power_sensor` invece di `sensor`.

**La routine non si attiva** → Servono 3 giorni di dati. Controlla con `/routine`.

**HomeMind non risponde per 30 secondi** → Con la v1.6 il fallback avviene in 12s. Aggiorna.

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
- [Power Guard](#power-guard-en)
- [Climate and Heating](#climate-and-heating)
- [SmartIR Climatizers](#smartir-climatizers-en)
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
> *"Turn on the boiler at 22 degrees"*
> *"Turn off water heater in 2 hours"*

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
| ⚠️ **Power Guard** | Protects against contract power threshold |
| ⏰ **Scheduled tasks** | Schedule future actions in natural language |
| ⚙️ **Config via chat** | Edit configuration by writing on Telegram |
| 🔧 **Automations from Telegram** | Create, edit and delete HA automations via chat |
| 🩺 **AI Log Analysis** | Reads HA logs, finds errors and proposes fixes |
| 🎨 **Lovelace AI Dashboard** | Generates a custom Lovelace dashboard |

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
telegram_bot_token: "TOKEN_FROM_BOTFATHER"
telegram_chat_id:   "YOUR_CHAT_ID"
alarm_code:         "1234"
```

### AI Providers (add at least Gemini + Groq — both free)
```yaml
gemini_api_key:   "AIzaSy..."
gemini_model:     "gemini-2.0-flash"
groq_api_key:     "gsk_..."
groq_model:       "llama-3.3-70b-versatile"
cerebras_api_key: "csk_..."
cerebras_model:   "llama3.1-8b"
openai_api_key:   "sk-..."   # Only for voice messages
ai_provider_order: "gemini,groq,cerebras,deepseek,claude,openai"
```

> **Automatic fallback:** if Gemini is offline, HomeMind switches to Groq in 12 seconds, then Cerebras, etc.

| Provider | Cost | Limit |
|----------|------|-------|
| 🟦 **Gemini** | Free | 1,500 req/day |
| ⚡ **Groq** | Free | 100k token/day |
| 🧠 **Cerebras** | Free | 1M token/min |
| 🔵 **DeepSeek** | ~Free | $0.014/1M token |

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
  "person_blacklist": ["person.fake_mqtt"],
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
  "person_blacklist": ["person.fake_mqtt"],
  "alarm_panel": "alarm_control_panel.risco_home",
  "proximity_sensors": {
    "person.mario": {"sensor": "sensor.home_mario_distance", "threshold_m": 100, "stale_check": false}
  },
  "climate": {
    "climate.thermostat": {"name": "Home thermostat", "switch": "switch.boiler", "min_temp": 15, "max_temp": 30}
  },
  "power_guard": {
    "enabled": true,
    "power_sensor": "sensor.home_power_w",
    "threshold_w": 3000,
    "warning_pct": 90,
    "mode": "ask",
    "appliances_priority": [
      {"name": "Washer",       "switch": "switch.washer_plug"},
      {"name": "Dishwasher",   "switch": "switch.dishwasher_plug"},
      {"name": "Water heater", "switch": "switch.water_heater"}
    ]
  },
  "frigate": {
    "enabled": true, "host": "192.168.1.100", "port": 5000, "snapshot_on_alarm": true,
    "cameras": {"entrance": "binary_sensor.entrance_sensor_occupancy"}
  }
}
```

---

## Custom Alarm Panel

```json
"alarm_panel": "alarm_control_panel.risco_home"
```

Advanced format for Verisure/Ajax:
```json
"alarm_panel": {"entity": "alarm_control_panel.verisure_home", "arm_mode": "armed_home"}
```

| `arm_mode` | When to use |
|------------|-------------|
| `armed_away` | Everyone away **(default)** |
| `armed_home` | Someone home — perimeter only |
| `armed_night` | Night mode |

---

## GPS Proximity Sensor

Prevents false alarms. Lower to 50m if welcome message doesn't arrive.

```json
"proximity_sensors": {
  "person.mario": {"sensor": "sensor.home_mario_distance", "threshold_m": 100, "stale_check": false}
}
```

> Welcome always arrives if you've been away more than 30 minutes, even with stale proximity data.

---

## Appliance Monitor

**POWER mode** (smart plug): `"mode": "power", "power_sensor": "sensor.washer_plug_power"`

**SMART mode** (connected appliances): `"mode": "smart", "state_sensor": "sensor.dishwasher_operation_state"`

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

Protects your home from exceeding the contract power threshold.

```json
"power_guard": {
  "enabled": true,
  "power_sensor": "sensor.home_power_w",
  "threshold_w": 3000,
  "warning_pct": 90,
  "mode": "ask",
  "appliances_priority": [
    {"name": "Washer",       "switch": "switch.washer_plug"},
    {"name": "Dishwasher",   "switch": "switch.dishwasher_plug"},
    {"name": "Water heater", "switch": "switch.water_heater"}
  ]
}
```

| `mode` | Behavior |
|--------|----------|
| `warn_only` | Notify only |
| `ask` | Asks confirmation **(recommended)** |
| `auto` | Shuts off automatically |

```
/powerguard   → status + power bar + appliances
/pg           → short alias
```

---

## Climate and Heating

```json
"climate": {
  "climate.thermostat": {
    "name": "Home thermostat", "switch": "switch.boiler", "min_temp": 15, "max_temp": 30
  }
}
```

---

## SmartIR Climatizers EN

HomeMind automatically handles SmartIR climatizers without 400 errors.

**Auto-detection** — works immediately if the climate entity has `controller_data` attributes.

**Manual override** if you still get 400 errors:
```json
"climate": {
  "climate.living_room_ac": {
    "name": "Living Room AC",
    "type": "smartir"
  }
}
```

| Type | Turn On | Turn Off |
|------|---------|----------|
| **SmartIR** | `climate.turn_on` | `climate.turn_off` |
| **Standard** | `climate.set_hvac_mode heat` | `climate.set_hvac_mode off` |
| **Boiler + switch** | `switch.turn_on` | `switch.turn_off` |

---

## Scheduled Tasks EN

Schedule any future action in natural language. Tasks survive restarts and are different from permanent automations.

**How it works:**
```
You: "Turn on lights at 7pm"
HomeMind: "⏰ Scheduled! Will execute at 19:00"

At 7pm:
HomeMind: "⏰ Task executed! Lights on ✅"
```

**Supported patterns:**
```
"at 7pm" / "at 19:30"            → today or tomorrow
"in 30 minutes"                   → quick timer
"in 2 hours"                      → hour timer
"in 3 days at 7pm"                → in N days
"tomorrow at 7"                   → tomorrow
"friday at 8pm"                   → day of week
"saturday morning at 8"           → saturday
"march 28 at 9am"                 → specific date

Italian equivalents also supported.
```

**Commands:**
```
/task              → list scheduled tasks
/cancella_task 1   → cancel task number 1
```

---

## Config via Chat EN

Edit `person_config.json` by writing in natural language on Telegram — no file editing, no restart needed.

**Command:**
```
/config   → show current configuration
```

**Examples:**
```
"Add person.mario to whitelist"
"Exclude person.awtrix"
"Change Enel threshold to 3500W"
"Power Guard mode auto"
"Trash notification at 9pm"
"Change language to Italian"
"Proximity threshold 50 meters"
"Max climate temperature 28 degrees"
```

HomeMind shows a preview and asks for confirmation:
```
⚙️ Config change detected:
Adding person.mario to whitelist

Apply this change? (yes/no)
```

Automatic backup at `/config/homemind_patches/person_config.backup.json`.

---

## Persistent Memory

HomeMind learns your preferences over time.

**Commands:**
```
/memory              → everything HomeMind knows about you
/forget boiler       → remove facts containing "boiler"
/memory reset        → clear everything
```

---

## Smart Routine

After **3 days** of observation, HomeMind starts anticipating your needs.

```
HomeMind: "🏃 You usually leave at 08:30 — 20 minutes to go.
           Shall I prepare the house?"
"yes" → lower heating + turn off lights ✅
```

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

```
/automations       → full list
/automations_help  → guide with examples
```

---

## Log Analysis and Auto-Fix EN

HomeMind reads HA logs every 5 minutes and notifies you of critical errors with AI solutions. Enabled by default, no configuration needed.

---

## Lovelace Dashboard Generator EN

```
"generate my dashboard"
"create a lovelace dashboard for my entities"
"generate dashboard and push to HA"
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
| `/elettrodomestici` | Appliance status |
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

**Alarm arms while I'm still home** → Configure `proximity_sensors`.

**Welcome message doesn't arrive** → Lower `threshold_m` to 50. With v1.6, works even with stale proximity.

**SmartIR — 400 errors** → Add `"type": "smartir"` to the climate block in config.

**Task executed but action not performed** → Check that the device name exists in HA.

**Power Guard shows app=0** → Use `appliances_priority` instead of `appliances`, and `power_sensor` instead of `sensor`.

**HomeMind doesn't respond for 30 seconds** → Update to v1.6 — fallback now happens in 12s.

**Routine doesn't trigger** → Needs 3 days of data. Check with `/routine`.

**Not receiving Telegram notifications** → Verify `telegram_chat_id` with @userinfobot.

**Frigate not connecting** → Test in browser: `http://IP:5000`.

---

---

## Changelog

**v1.4.3** — Task Scheduler parser esteso (giorni settimana, mesi, N giorni IT+EN), Config Editor via chat (/config), SmartIR auto-detect + override, fallback AI veloce 12s, storico binario leggibile (movimento/luce/persona), rilevamento 🏠 Casa da zone.home, fix benvenuto GPS stale, Power Guard alias config, protezione dashboard azioni accidentali, /stato applica whitelist/blacklist

**v1.4.2** — Smart Routine Manager, Task Scheduler base, Memoria persistente, Config Allarme personalizzato (stringa e oggetto), Clima con switch fisico, Switch visibili all'AI, Solar optimizer batteria piena + elevazione solare, fix benvenuto proximity+GPS

**v1.3.7** — Power Guard (3 modalità: warn/ask/auto), fix persone blacklist, Task Scheduling base

**v1.3.6** — Calendario spazzatura builtin 2026, copia automatica al primo avvio

**v1.3.5** — Smart Routine Manager: impara orari uscita/rientro, anticipa le partenze

**v1.3.4** — Memoria persistente, pannello allarme personalizzato, clima personalizzato, switch visibili all'AI, solar optimizer migliorato

**v1.3.0** — Fix Telegram notify_entity, foto Frigate duplicate, cooldown anti-spam 60s

**v1.2.x** — Integrazione Frigate NVR, snapshot automatici allarme, tab Frigate web UI

**v1.2.0** — Pagina impostazioni web completa (5 tab)

**v1.1.x** — Fix navigazione, fix UTF-8 BOM, dashboard live

**v1.0.4** — Interfaccia vocale via Whisper

**v1.0.2** — Fix sicurezza: codice allarme, autenticazione web, log senza PII

**v1.0.0** — Release iniziale

---

<div align="center">

**HomeMind Orchestrator** — *La tua casa, finalmente intelligente. / Your home, finally intelligent.*

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

**[paypal.me/ago19800](https://paypal.me/ago19800)**

[🔝 Torna su / Back to top](#-homemind-orchestrator)

</div>
