<div align="center">

# 🧠 HomeMind Orchestrator

**[🇮🇹 Italiano](#-italiano) · [🇬🇧 English](#-english)**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![Language](https://img.shields.io/badge/Lingua-Italiano%20%2F%20English-green)]()
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Groq%20%7C%20Cerebras%20%7C%20DeepSeek-orange)]()
[![Version](https://img.shields.io/badge/versione-1.3.9-brightgreen)](https://github.com/ago19800/HomeMind/releases)

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
| ⚠️ **Power Guard** | Protegge dalla soglia contrattuale Enel, spegne in automatico |
| 🔧 **Automazioni da Telegram** | Crea, modifica ed elimina automazioni HA via chat |
| 🩺 **Analisi Log AI** | Legge i log HA, trova errori critici e propone fix |
| 🎨 **Dashboard Lovelace AI** | Genera dashboard Lovelace su misura per le tue entità |
| 🧠 task → lista di tutti i task in coda |
| 🗑️ cancella task → cancella uno specifico |
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

# Ordine di priorità — primo provider disponibile viene usato per primo
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
    "sensor": "sensor.consumo_casa_w",
    "threshold_w": 3000,
    "warning_pct": 90,
    "mode": "ask",
    "appliances": [
      {"name": "Lavatrice",     "switch": "switch.presa_lavatrice",     "priority": 1},
      {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie", "priority": 2},
      {"name": "Scaldabagno",   "switch": "switch.scaldabagno",         "priority": 3}
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

## Power Guard IT

Protegge la tua utenza dalla soglia contrattuale Enel. Quando il consumo si avvicina al limite, HomeMind **notifica** o **spegne automaticamente** gli elettrodomestici meno prioritari.

```json
"power_guard": {
  "enabled": true,
  "sensor": "sensor.consumo_casa_w",
  "threshold_w": 3000,
  "warning_pct": 90,
  "mode": "ask",
  "appliances": [
    {"name": "Lavatrice",     "switch": "switch.presa_lavatrice",     "priority": 1},
    {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie", "priority": 2},
    {"name": "Scaldabagno",   "switch": "switch.scaldabagno",         "priority": 3}
  ]
}
```

| `mode` | Comportamento |
|--------|---------------|
| `warn_only` | Solo notifica, non spegne nulla |
| `ask` | Chiede conferma prima di spegnere **(consigliato)** |
| `auto` | Spegne automaticamente senza chiedere |

**Comandi Telegram:**
```
/powerguard   → stato attuale + elettrodomestici monitorati
/pg           → alias breve
```

> Il cooldown anti-spam è di 10 minuti per evitare messaggi continui.

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

### Task Scheduling (pianificazione attività). È diversa dalle automazioni HA perché le crei parlando in modo naturale e sono temporanee.

```
Come funzionerebbe:
Tu: "Accendi la luce di Mario alle 19:00"
HomeMind: "✅ Schedulato — accendo luce Mario alle 19:00"

Alle 19:00:
HomeMind: "⏰ Eseguito — luce Mario accesa!"
Tu: "Alle 20:30 accendi caldaia e metti 22 gradi"
HomeMind: "✅ Schedulato — caldaia + 22° alle 20:30"

Alle 20:30:
HomeMind esegue i due comandi e ti avvisa

Cosa si può schedulare — qualsiasi cosa:
"Tra 2 ore spegni tutte le luci"
"Domani mattina alle 7 accendi il riscaldamento"
"Ogni venerdì alle 18 avvisami di accendere la lavatrice"
"Tra 30 minuti controlla se la lavatrice è finita"
"Stasera alle 23 arma l'allarme"
```

### Gestione task:
```
/task          → lista di tutti i task in coda
/cancella task → cancella uno specifico

> La memoria cambia le **risposte in chat**, non i comportamenti automatici (allarme, avvisi). Per quelli serve il config JSON.
```
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

## Gestione Automazioni IT

Dalla v1.3xx puoi creare, modificare ed eliminare automazioni HA **direttamente da Telegram**, in linguaggio naturale. HomeMind scrive il YAML nel tuo `automations.yaml` — senza toccare nient'altro.

### Esempi
```
"crea automazione che spenga tutte le luci a mezzanotte"
→ HomeMind genera il YAML, lo salva in automations.yaml e lo attiva subito

"modifica automazione luci notte — falla scattare all'01:00 invece di mezzanotte"
→ HomeMind trova la riga giusta e la aggiorna

"elimina automazione luci notte"
→ Rimuove il blocco e ricarica le automazioni in HA

"mostra le mie automazioni"
→ Lista completa divisa per attive/disattive con nomi friendly
```

### Comandi
```
/automazioni          → lista completa
crea automazione ...  → crea in linguaggio naturale
modifica automazione [nome] — [modifica]
elimina automazione [nome]
```

> Ogni modifica viene salvata con backup automatico in `/config/homemind_patches/`.

---

## Analisi Log e Auto-Fix IT

HomeMind legge i log di Home Assistant ogni 5 minuti, identifica errori critici e ti informa con una spiegazione AI e la soluzione consigliata.

```
HomeMind: "⚠️ Errore critico rilevato in HA:
  [homeassistant.components.mqtt] Cannot connect to MQTT broker

  💡 Soluzione: Il broker MQTT non è raggiungibile. Verifica che
  Mosquitto sia in esecuzione e che l'indirizzo host nel file di
  configurazione sia corretto."
```

**Configurazione** — per ora automatica, nessuna configurazione necessaria. Attivata di default.

> Anti-spam integrato: lo stesso errore viene notificato al massimo **ogni ora**.

---

## Generatore Dashboard Lovelace IT

HomeMind può generare una dashboard Lovelace completa per la tua installazione HA, basandosi sulle entità reali presenti nel sistema e sulla loro frequenza d'uso.

**Come usarlo:**
```
"genera la mia dashboard"
"crea una dashboard lovelace per le mie entità"
```

Il file YAML viene salvato in `/config/homemind_dashboards/` pronto per essere importato in HA. Puoi anche chiedere a HomeMind di caricarlo direttamente con:
```
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
| `/automazioni` | Lista automazioni HA |
| `/powerguard` / `/pg` | Stato Power Guard e consumi |
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
| `/task `→ lista di tutti i task in coda |
| `/cancella task` → cancella uno specifico |
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

**Power Guard notifica continuamente** → Normale se il consumo oscilla attorno alla soglia. Abbassa `warning_pct` o aumenta `threshold_w`.

**L'analisi log non funziona** → Verifica che il log di HA sia accessibile dal container. Controlla i log dell'addon.

**La dashboard generata è vuota** → HomeMind legge le entità in tempo reale — assicurati che l'addon sia in esecuzione e connesso all'API HA.

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
> *"Create an automation to turn off the lights at 11pm"*
> *"Analyze the HA logs and tell me if there are any errors"*

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
| ⚠️ **Power Guard** | Protects against Enel contract threshold, auto-shuts appliances |
| 🔧 **Automations from Telegram** | Create, edit and delete HA automations via chat |
| 🩺 **AI Log Analysis** | Reads HA logs, finds critical errors and proposes fixes |
| 🎨 **Lovelace AI Dashboard** | Generates a custom Lovelace dashboard for your entities |

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
gemini_model:     "gemini-2.0-flash"

groq_api_key:     "gsk_..."     # Free 100k token/day → console.groq.com
groq_model:       "llama-3.3-70b-versatile"

cerebras_api_key: "csk_..."     # Free 1M token/min   → cloud.cerebras.ai
cerebras_model:   "llama3.1-8b"

deepseek_api_key: "sk-..."      # ~Free $0.014/1M tok → platform.deepseek.com
deepseek_model:   "deepseek-chat"

claude_api_key:   "sk-ant-..."  # Paid → console.anthropic.com
claude_model:     "claude-3-5-haiku-20241022"

openai_api_key:   "sk-..."      # Only for voice msg  → platform.openai.com
openai_model:     "gpt-4o-mini"

# Priority order — first available provider is used first
ai_provider_order: "gemini,groq,cerebras,deepseek,claude,openai"
```

| Provider | Cost | Limit | Link |
|----------|------|-------|------|
| 🟦 **Gemini** | Free | 1,500 req/day | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ **Groq** | Free | 100k token/day | [console.groq.com](https://console.groq.com) |
| 🧠 **Cerebras** | Free | 1M token/min | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 **DeepSeek** | ~Free | $0.014/1M token | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟠 **Claude** | Paid | — | [console.anthropic.com](https://console.anthropic.com) |
| 🟢 **OpenAI** | Paid | $0.006/min audio | [platform.openai.com](https://platform.openai.com) |

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
  "power_guard": {
    "enabled": true,
    "sensor": "sensor.home_power_w",
    "threshold_w": 3000,
    "warning_pct": 90,
    "mode": "ask",
    "appliances": [
      {"name": "Washer",      "switch": "switch.washer_plug",      "priority": 1},
      {"name": "Dishwasher",  "switch": "switch.dishwasher_plug",  "priority": 2},
      {"name": "Water heater","switch": "switch.water_heater",     "priority": 3}
    ]
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

## Power Guard EN

Protects your home from exceeding the contract power threshold. When consumption approaches the limit, HomeMind **notifies** you or **automatically shuts off** the lowest-priority appliances.

```json
"power_guard": {
  "enabled": true,
  "sensor": "sensor.home_power_w",
  "threshold_w": 3000,
  "warning_pct": 90,
  "mode": "ask",
  "appliances": [
    {"name": "Washer",      "switch": "switch.washer_plug",      "priority": 1},
    {"name": "Dishwasher",  "switch": "switch.dishwasher_plug",  "priority": 2},
    {"name": "Water heater","switch": "switch.water_heater",     "priority": 3}
  ]
}
```

| `mode` | Behavior |
|--------|----------|
| `warn_only` | Notify only, no shutoffs |
| `ask` | Asks confirmation before shutting off **(recommended)** |
| `auto` | Shuts off automatically without asking |

**Telegram commands:**
```
/powerguard   → current status + monitored appliances
/pg           → short alias
```

> Built-in 10-minute anti-spam cooldown prevents repeated alerts.

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

### Task Scheduling. It is different from HA automations because you create them by speaking naturally and they are temporary.

```
How it would work:
You: "Turn on Mario's light at 7:00 PM"
HomeMind: "✅ Scheduled — turning on Mario's light at 7:00 PM"

At 7:00 PM:
HomeMind: "⏰ Executed — Mario's light turned on!"
You: "At 8:30 PM turn on the boiler and set it to 22 degrees"
HomeMind: "✅ Scheduled — boiler + 22° at 8:30 PM"

At 8:30 PM:
HomeMind executes the two commands and notifies you

What can be scheduled — anything:
"In 2 hours turn off all lights"
"Tomorrow morning at 7 turn on the heating"
"Every Friday at 6 PM remind me to turn on the washing machine"
"In 30 minutes check if the washing machine is finished"
"Tonight at 11 PM arm the alarm"
```

### Task management:
```
/task → list of all tasks in queue
/cancel task → cancel a specific one


```
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

## Automations Manager EN

From v1.3.xxx, you can create, edit and delete HA automations **directly from Telegram**, in plain language. HomeMind writes the YAML directly to your `automations.yaml` — without touching anything else.

### Examples
```
"create automation to turn off all lights at midnight"
→ HomeMind generates YAML, saves it to automations.yaml and activates it immediately

"edit automation night lights — change it to trigger at 01:00 instead of midnight"
→ HomeMind finds the right entry and updates it

"delete automation night lights"
→ Removes the block and reloads automations in HA

"show my automations"
→ Full list split by active/inactive with friendly names
```

### Commands
```
/automations               → full list
create automation ...      → create in plain language
edit automation [name] — [change]
delete automation [name]
```

> Every change is saved with automatic backup in `/config/homemind_patches/`.

---

## Log Analysis and Auto-Fix EN

HomeMind reads Home Assistant logs every 5 minutes, identifies critical errors and notifies you with an AI explanation and recommended solution.

```
HomeMind: "⚠️ Critical error detected in HA:
  [homeassistant.components.mqtt] Cannot connect to MQTT broker

  💡 Solution: The MQTT broker is unreachable. Check that
  Mosquitto is running and that the host address in your
  configuration file is correct."
```

**Configuration** — automatic, no setup needed. Enabled by default.

> Built-in anti-spam: same error is reported at most **once per hour**.

---

## Lovelace Dashboard Generator EN

HomeMind can generate a full Lovelace dashboard for your HA installation, based on the actual entities present in your system and their usage frequency.

**How to use:**
```
"generate my dashboard"
"create a lovelace dashboard for my entities"
```

The YAML file is saved to `/config/homemind_dashboards/` ready to be imported in HA. You can also ask HomeMind to push it directly:
```
"generate dashboard and push to HA"
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
| `/automazioni` | List HA automations |
| `/powerguard` / `/pg` | Power Guard status and consumption |
| `/memory` | What HomeMind knows about you |
| `/forget <text>` | Remove a fact |
| `/memory reset` | Clear all memory |
| `/spazzatura` | Trash collection next 7 days |
| `/aggiornamenti` | HA updates |
| `/riparazioni` | HA issues |
| `/providers` | Active AI providers |
| `/lingua it` / `/lingua en` | Change language |
| `/comandi` | This list |
| `/task` → list of all tasks in the queue |
| `/cancella task` → delete a specific one |
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

**Power Guard notifies constantly** → Normal if consumption oscillates around the threshold. Lower `warning_pct` or increase `threshold_w`.

**Log analysis not working** → Verify that HA logs are accessible from the container. Check the addon logs.

**Generated dashboard is empty** → HomeMind reads entities in real time — make sure the addon is running and connected to the HA API.

**Not receiving Telegram notifications** → Verify `telegram_chat_id` is a number (use @userinfobot).

**Frigate not connecting** → Verify IP and port. Test in browser: `http://IP:5000`.

---

---

## Changelog

**v1.3.7** — Power Guard (protezione soglia contrattuale con 3 modalità: warn/ask/auto), - fix: person.xxxxx, 🧠 Memoria persistente Impara le tue preferenze nel tempo, Task Scheduling (pianificazione attività). È diversa dalle automazioni HA perché le crei parlando in modo naturale e sono temporanee.

**v1.3.6** — Calendario spazzatura builtin 2026 (Lanciano), copia automatica al primo avvio se non presente

**v1.3.5** — Smart Routine Manager: impara orari uscita/rientro, anticipa le partenze, comando `/routine`

**v1.3.4** — Memoria persistente (`/memoria`, `/dimentica`, `/memoria reset`), pannello allarme personalizzato (formato stringa e oggetto, supporto `arm_mode` per Verisure/Ajax), clima personalizzato con switch fisico e range temperatura, switch visibili all'AI, solar optimizer batteria piena + elevazione solare, fix benvenuto proximity+GPS, fix proximity stale 4h, fix temperature in `/stato`

**v1.3.0** — Fix campo `notify_entity` vuoto che bloccava Telegram, foto Frigate duplicate risolte, cooldown anti-spam 60s per camera

**v1.2.x** — Integrazione Frigate NVR, snapshot automatici allarme, tab Frigate nella web UI

**v1.2.0** — Pagina impostazioni web completa (5 tab), merge automatico campi avanzati

**v1.1.x** — Fix tab navigazione, fix UTF-8 BOM, dashboard live

**v1.0.4** — Interfaccia vocale via Whisper

**v1.0.2** — Fix sicurezza: codice allarme, autenticazione Web UI, log senza PII

**v1.0.0** — Release iniziale

---

<div align="center">

**HomeMind Orchestrator** — *La tua casa, finalmente intelligente. / Your home, finally intelligent.*

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

**[paypal.me/ago19800](https://paypal.me/ago19800)**

[🔝 Torna su / Back to top](#-homemind-orchestrator)

</div>
