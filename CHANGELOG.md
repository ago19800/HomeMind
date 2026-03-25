# 📋 Changelog — HomeMind Orchestrator

---

## v1.5.0

### 🌅 Briefing Mattutino Personalizzabile

Il briefing mattutino è ora completamente configurabile via Telegram, senza toccare nessun file.

**Come si usa:**

```
# Aggiungere sezioni con valore sensore HA
"Aggiungi al briefing temperatura cucina sensor.temp_cucina"
"Aggiungi al briefing temperatura esterna {sensor.temp_ext}"

# Aggiungere nota fissa
"Aggiungi al briefing Ricorda di annaffiare le piante"

# Rimuovere una sezione extra specifica
"Rimuovi dal briefing temperatura cucina"

# Rimuovere TUTTE le sezioni extra in una volta
"Rimuovi sezioni extra briefing"

# Nascondere sezioni standard
"Escludi meteo dal briefing"
"Escludi energia dal briefing"
"Escludi stato casa dal briefing"
"Escludi spazzatura dal briefing"

# Ripristinare sezioni nascoste
"Mostra meteo nel briefing"
"Mostra energia nel briefing"

# Saluto personalizzato
"Saluto briefing Buongiorno Mario! ☀️"
"Saluto briefing Mario"    ← auto-completato in "Buongiorno Mario! ☀️"

# Cambiare orario
"Briefing alle 8"
"Briefing alle 7:30"

# Reset completo ai default
"Ripristina briefing"
```

Il saluto personalizzato appare in cima al briefing in grassetto, ben separato dal resto.
I sensori HA vengono risolti al momento dell'invio — mostrano sempre il valore attuale.

---

### 🌤️ Meteo Esterno (nessuna API key richiesta)

HomeMind recupera previsioni meteo reali per qualsiasi città usando **open-meteo.com** — completamente gratuito, nessuna registrazione.

**Come si usa:**

```
"Meteo Roma"
"Che tempo fa a Milano?"
"Previsioni Napoli domani"
"Meteo Londra"
```

Mostra: temperatura, umidità, vento (km/h), probabilità pioggia, condizioni generali.
Previsioni disponibili per oggi + 2 giorni successivi.

Per includere il meteo di una città nel briefing mattutino:
```
"Imposta meteo briefing Roma"
```

---

### 🐳 Installazione Docker Standalone

HomeMind ora supporta l'installazione via **Docker Compose** per chi usa:
- Home Assistant Core
- Home Assistant Container
- Unraid
- NAS Synology / QNAP
- Qualsiasi sistema Linux con Docker

**Come si installa:**

```bash
# 1. Crea la cartella
mkdir ~/homemind && cd ~/homemind

# 2. Scarica i file necessari
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/docker-compose.yml
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/.env.example

# 3. Configura
cp .env.example .env
nano .env   ← inserisci HA_URL, HA_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, chiavi AI

# 4. Avvia
docker-compose up -d
```

Tutte le funzionalità dell'addon sono disponibili anche nella versione Docker.
La configurazione avanzata (persone, sensori, allarme ecc.) si fa tramite `person_config.json`
nel volume Docker: `~/homemind_data/homemind_patches/person_config.json` — stessa sintassi dell'addon.

File aggiunti al repository:
- `Dockerfile.standalone` — immagine Docker senza supervisor HAOS
- `docker-compose.yml` — pronto all'uso
- `.env.example` — template con tutte le variabili commentate
- `run.standalone.sh` — script avvio che legge da variabili d'ambiente
- `INSTALL_DOCKER.md` — guida dettagliata installazione

---

### 🤖 Multi-AI con Fallback Automatico a Cascata

HomeMind ora supporta **7 provider AI** configurabili, con cambio automatico se uno è offline o esaurito.

**Provider supportati:**

| Provider | Costo | Come ottenere la chiave |
|----------|-------|------------------------|
| 🟦 Gemini | Gratis (1.500 req/giorno) | aistudio.google.com |
| ⚡ Groq | Gratis (100k token/giorno) | console.groq.com |
| 🧠 Cerebras | Gratis (1M token/min) | cloud.cerebras.ai |
| 🔵 DeepSeek | ~Gratis ($0.014/1M token) | platform.deepseek.com |
| 🟣 Mistral | Gratis (tier) | console.mistral.ai |
| 🟠 Claude | A pagamento | console.anthropic.com |
| 🟢 OpenAI | A pagamento (voce) | platform.openai.com |

**Come funziona:**

HomeMind tenta sempre il primo provider dell'ordine configurato.
Se risponde con errore (rate limit, quota esaurita, offline) in 12 secondi
passa automaticamente al secondo, poi al terzo, e così via.
Non rimani mai senza risposta.

**Configurazione nell'addon:**
```yaml
ai_provider_order: "gemini,groq,cerebras,deepseek,mistral,claude,openai"
```

**Configurazione Docker (.env):**
```env
AI_PROVIDER_ORDER=gemini,groq,cerebras,deepseek,mistral,claude,openai
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
```

Per vedere quale provider ha risposto all'ultima chiamata:
```
/providers
```

---

### 🫧 Stato Singolo Elettrodomestico

Prima, chiedere "stato lavatrice" mostrava tutti gli elettrodomestici insieme.
Ora risponde solo con le informazioni sull'elettrodomestico richiesto.

**Come si usa:**

```
"stato lavatrice"       → solo info sulla lavatrice
"stato lavastoviglie"   → solo info sulla lavastoviglie
"elettrodomestici"      → tutti insieme (comportamento invariato)
/elettrodomestici       → tutti insieme
```

---

## v1.4.1

Task Scheduler parser esteso (giorni settimana, mesi, N giorni IT+EN), Config Editor via chat (/config), SmartIR auto-detect + override manuale, fallback AI veloce 12s, storico binario leggibile, rilevamento Casa da zone.home, Power Guard alias config.

## v1.4.0

Smart Routine Manager, Task Scheduler, Memoria persistente, Allarme personalizzato (stringa e oggetto), Clima con switch fisico, Switch visibili all'AI, Solar optimizer batteria piena + elevazione solare.

## v1.3.7

Power Guard (3 modalità: warn/ask/auto).

## v1.3.6

Calendario spazzatura builtin 2026, copia automatica al primo avvio.

## v1.2.x

Integrazione Frigate NVR, snapshot automatici allarme, tab web UI.

## v1.2.0

Pagina impostazioni web completa (5 tab).

## v1.0.4

Interfaccia vocale via Whisper.

## v1.0.0

Release iniziale.
