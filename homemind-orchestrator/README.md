# 🧠 HomeMind Orchestrator

**[🇮🇹 Italiano](#-italiano) · [🇬🇧 English](#-english)**

[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024%2B-blue)](https://www.home-assistant.io/)
[![Language](https://img.shields.io/badge/Lingua-Italiano%20%2F%20English-green)](https://github.com/ago19800/HomeMind)
[![AI](https://img.shields.io/badge/AI-Gemini%20%7C%20Groq%20%7C%20Cerebras%20%7C%20DeepSeek%20%7C%20Mistral%20%7C%20Claude%20%7C%20OpenAI-orange)](https://github.com/ago19800/HomeMind)
[![Version](https://img.shields.io/badge/versione-1.11.15-informational)](CHANGELOG.md)

☕ **Se questo addon ti è utile, offrimi un caffè! / If this addon is useful, buy me a coffee!**

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

📱 **Seguimi anche su TikTok e GitHub! / Follow me on TikTok and GitHub!**

[![TikTok](https://img.shields.io/badge/TikTok-@marioago3-000000?logo=tiktok&style=for-the-badge)](https://www.tiktok.com/@marioago3)
[![GitHub](https://img.shields.io/badge/GitHub-ago19800-181717?logo=github&style=for-the-badge)](https://github.com/ago19800)

---

# 🇮🇹 Italiano

## Indice

1. [Cos'è HomeMind](#cosè-homemind)
2. [Funzionalità](#funzionalità)
3. [Installazione e aggiornamento](#installazione-e-aggiornamento)
4. [Primo avvio](#primo-avvio)
5. [Dove si configura tutto](#dove-si-configura-tutto)
6. [Persone, GPS e Proximity](#persone-gps-e-proximity-)
7. [Tracciamento telefoni — "Dove è stato?"](#tracciamento-telefoni--dove-è-stato-)
8. [Antifurto automatico](#antifurto-automatico-)
9. [📹 Frigate: telecamere, targhe, persone, cani](#-frigate-telecamere-targhe-persone-cani)
10. [📧 Email](#-email)
11. [📁 Salva file dalla chat](#-salva-file-dalla-chat)
12. [Energia, elettrodomestici, solare, Power Guard](#energia-elettrodomestici-solare-power-guard-)
13. [Clima, Do Not Disturb, filtri sensori](#clima-do-not-disturb-filtri-sensori)
14. [Briefing, spazzatura, memoria, alias, task](#briefing-spazzatura-memoria-alias-task)
15. [Provider AI e fallback](#provider-ai-e-fallback-)
16. [Agente, SSH e strumenti avanzati](#agente-ssh-e-strumenti-avanzati-)
17. [Comandi Telegram](#comandi-telegram-)
18. [Pagina web](#pagina-web-)
19. [Esempi di configurazione completa](#esempi-di-configurazione)
20. [FAQ e risoluzione problemi](#faq-e-risoluzione-problemi-)

---

## Cos'è HomeMind

HomeMind è un **add-on per Home Assistant** che aggiunge un cervello AI alla tua casa. Non è una semplice automazione: capisce il contesto, impara la tua routine e ti avvisa solo quando serve davvero.

**Parlagli su Telegram in italiano naturale:**

> *"Accendi la luce del salotto"* · *"Quanta energia ho prodotto oggi?"* · *"Apri le tapparelle al 70%"* · *"Hai visto persone nell'ultima ora?"* · *"Che targhe sono passate oggi?"*

Puoi anche mandargli un **messaggio vocale** 🎙️ (serve una API key OpenAI): lo trascrive e lo tratta come un comando normale.

---

## Funzionalità

Le voci marcate 🆕 sono le più recenti (versioni 1.11.10 – 1.11.15).

| Funzione | Descrizione |
|---|---|
| 🔒 **Allarme automatico GPS** | Arma quando tutti escono, disarma quando torni. 3 modalità: `auto`, `notify`, `disabled` |
| 🔔 **Conferma antifurto** | Con `notify` ricevi su Telegram i bottoni ✅/❌ prima di armare |
| 📍 **Proximity GPS** | Rileva avvicinamento/allontanamento da casa con soglia in metri, zona gialla, controllo su più fonti (GPS + WiFi + distanza) |
| 🗺️ **Tracciamento telefoni** | "Dove è stato Agostino oggi?" → soste con indirizzo reale (OpenStreetMap) |
| 👋 **Benvenuto a casa** | Messaggio su Telegram quando rientri |
| 📷 **Snapshot su allarme** | Foto delle telecamere Frigate su Telegram quando scatta l'allarme |
| 🆕 🚗 **Targhe da Telegram** | "Che targhe hai rilevato?" → elenco targhe lette da Frigate (LPR) con camera, orari, confidenza e foto |
| 🆕 👤 **Persone, cani, gatti, auto da Telegram** | "Hai visto persone nell'ultima ora?" / "animali" / "cani ieri" → rilevamenti Frigate filtrati per tipo e periodo, con album di foto |
| 🆕 🔔 **Avvisi istantanei Frigate** | Switch nella pagina web per tipo di oggetto: se attivo ricevi subito la foto su Telegram |
| 🆕 🎯 **Confidenza minima** | Filtra i falsi allarmi: invia la foto solo se Frigate è sicuro almeno al X% |
| 🆕 📁 **Salva file dalla chat** | Mandi un file al bot con "invia nella cartella": lo salva nella cartella scelta nella pagina web e cancella il messaggio da Telegram |
| 📧 **Email** | Gmail multi-account: lettura, riassunto AI, risposta guidata, auto-risposta con regole, invio programmato, pulizia spam |
| ⚡ **Monitor elettrodomestici** | Notifica quando lavatrice/lavastoviglie finiscono |
| ☀️ **Ottimizzatore solare** | Avvisa quando usare il surplus fotovoltaico |
| ⚠️ **Power Guard** | Protegge dalla soglia contrattuale — 3 modalità |
| 📊 **Analisi energia e fasce F1/F2/F3** | Confronto con la media storica, consumi per fascia ARERA |
| 🔕 **Do Not Disturb** | Blocca le notifiche non critiche di notte |
| 🌅 **Briefing mattutino** | Personalizzabile: sensori, orario, sezioni, saluto, meteo città |
| 🗑️ **Spazzatura** | La sera prima ricorda cosa mettere fuori |
| 🧠 **Memoria e routine** | Impara preferenze e abitudini, anticipa i bisogni |
| 🔗 **Alias comandi rapidi** | Parole chiave → azioni garantite, anche senza AI |
| 🔌 **Modalità offline** | Luci, tapparelle e allarme funzionano anche senza AI |
| 🤖 **Multi-AI con fallback** | Più provider in cascata, cambio automatico |
| 🔧 **Automazioni e config da chat** | Crea/modifica automazioni e file di configurazione via Telegram |
| 🩺 **Analisi log AI** | Legge i log di HA, trova errori e propone fix |
| 🎨 **Dashboard Lovelace AI** | Genera dashboard su misura |
| 🖥️ **SSH, agente `/fai`, tool** | Terminale e agente autonomo da Telegram |

---

## Installazione e aggiornamento

### Opzione A — Add-on Home Assistant (HAOS / Supervised) da repository GitHub

1. **Impostazioni → Add-on → Add-on Store → ⋮ (in alto a destra) → Repository**
2. Incolla `https://github.com/ago19800/HomeMind` → **Aggiungi**
3. Cerca **HomeMind Orchestrator** → **Installa**
4. Scheda **Configurazione**: inserisci token Telegram, chat id e almeno una API key AI → **Salva** → **Avvia**

### Opzione B — Add-on locale (cartella `/addons`)

1. Copia il contenuto della cartella `homemind-orchestrator` in `/addons/homemind-orchestrator` (condivisione Samba `addons` o SSH).
   Dentro devono esserci direttamente `config.yaml`, `Dockerfile`, `run.sh` e la cartella `src` (non una cartella dentro l'altra).
2. **Add-on Store → ⋮ → Controlla aggiornamenti**
3. Apri **HomeMind Orchestrator** (sezione *Add-on locali*) → **Installa** → configura → **Avvia**

### Opzione C — Docker (Home Assistant Core / Container / NAS / Unraid)

```bash
mkdir ~/homemind && cd ~/homemind
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/docker-compose.yml
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/.env.example
cp .env.example .env && nano .env
docker-compose up -d
```

File `.env` (serve almeno una chiave AI; l'elenco completo è in `.env.example`):

```
HA_URL=http://192.168.1.100:8123
HA_TOKEN=eyJhbGciOiJ...          # Long-Lived Access Token di HA
TELEGRAM_TOKEN=1234567890:AABBCC...
TELEGRAM_CHAT_ID=123456789
ALARM_CODE=1234
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
```

|  | Add-on HAOS | Docker |
|---|---|---|
| `person_config.json` | `/config/homemind_patches/` | nel volume Docker `homemind_data`, percorso `/data/homemind/homemind_patches/` |
| Pagina web | ✅ (menu laterale di HA) | ✅ porta 8099 |
| Aggiornamento | Add-on Store | `docker-compose pull && docker-compose up -d` |

Se HA gira sullo stesso host di Docker usa `http://host.docker.internal:8123` come `HA_URL`.

### ⬆️ Aggiornare HomeMind

Home Assistant propone l'aggiornamento **solo se la versione in `config.yaml` cambia**. Ogni release di HomeMind ha una versione nuova (vedi [CHANGELOG](CHANGELOG.md)).

- **Da repository GitHub:** Add-on Store → ⋮ → **Controlla aggiornamenti** → apri HomeMind → **Aggiorna**.
- **Add-on locale:** sostituisci **tutti** i file nella cartella `/addons/homemind-orchestrator`, poi Add-on Store → ⋮ → **Controlla aggiornamenti** → HomeMind → **Aggiorna** (o **Ricostruisci** se la versione non cambia).
- Un semplice **Riavvia non applica le modifiche al codice**: il codice è dentro l'immagine dell'add-on, serve Aggiorna/Ricostruisci.

**Come verificare quale versione è in esecuzione:** nella scheda *Info* dell'add-on vedi la versione; nel log di avvio cerca la riga
`FrigateAlertWatcher avviato — build 1.11.15`.

Le tue impostazioni (`person_config.json`, memoria, database) stanno in `/config/homemind_patches/` e **non vengono toccate** dagli aggiornamenti.

---

## Primo avvio

### 1. Crea il bot Telegram

1. Su Telegram cerca **@BotFather** → `/newbot` → scegli nome e username → copia il **token**.
2. Per sapere il tuo **chat id** scrivi a **@userinfobot** (o `@RawDataBot`) e copia il numero.
3. Scrivi almeno un messaggio al tuo nuovo bot (altrimenti non può risponderti).

Nella *Configurazione* dell'add-on:

```yaml
telegram_bot_token: "1234567890:AABBCC..."
telegram_chat_id:   "123456789"
alarm_code:         "1234"          # codice del tuo antifurto
```

> Solo le chat elencate in `telegram_chat_id` sono autorizzate a comandare HomeMind (anche più chat, separate da virgola).

### 2. Aggiungi almeno un provider AI (gratuito)

Nella *Configurazione* dell'add-on inserisci almeno una chiave, per esempio **Gemini** (gratis, [aistudio.google.com](https://aistudio.google.com)) e **Groq** (gratis, [console.groq.com](https://console.groq.com)). Dettagli nella sezione [Provider AI](#provider-ai-e-fallback-).

### 3. Verifica che funzioni

Scrivi al bot `/stato`: deve rispondere con persone, allarme e sensori. Poi apri la **pagina web** di HomeMind (voce *HomeMind* nel menu laterale di HA) per configurare persone, allarme, Frigate, ecc.

---

## Dove si configura tutto

HomeMind ha due livelli di configurazione:

| Dove | Cosa contiene |
|---|---|
| **Scheda Configurazione dell'add-on** (HA) | Chiavi AI, token Telegram, chat id, codice allarme, livello log, blacklist iniziali |
| **Pagina web di HomeMind** (`/settings`) | Tutto il resto: persone, allarme, sensori, energia, Frigate, elettrodomestici, proximity, clima, Power Guard, email… |
| **`person_config.json`** | Il file dove la pagina web salva tutto. Lo puoi modificare a mano: `/config/homemind_patches/person_config.json` |

Le impostazioni della pagina web si applicano **dopo aver premuto Salva**. Le sezioni che non usi puoi lasciarle vuote.

---

## Persone, GPS e Proximity 📍

### Passo 1 — Companion App sul telefono

- Android: [Google Play](https://play.google.com/store/apps/details?id=io.homeassistant.companion.android)
- iOS: [App Store](https://apps.apple.com/app/home-assistant/id1099568401)

Accedi al tuo HA e concedi la posizione **Sempre**. In *Impostazioni → Companion app → Gestisci sensori* abilita **Posizione in background** e il sensore **Distanza da casa** (se disponibile).

### Passo 2 — Controlla le entità

In **Strumenti per sviluppatori → Stati** cerca il tuo nome: devono esistere

- `person.nome` (stato `home` / `not_home`)
- `device_tracker.nome_telefono`
- `sensor.nome_telefono_distance` (distanza da casa in metri — se non esiste, crealo con un sensore "Distanza" di HA oppure usa solo il GPS)

### Passo 3 — Scegli chi è una persona (pagina web → 👤 Persone)

```json
"person_whitelist": ["person.mario", "person.lucia"],
"person_blacklist": ["person.tablet_finto"]
```

La whitelist è esclusiva: se la compili, solo quelle persone contano per l'antifurto.

### Passo 4 — Proximity (pagina web → 📍 Proximity)

La distanza dal sensore GPS rende l'armamento molto più affidabile del solo `home/not_home`, che può "rimbalzare".

```json
"proximity_sensors": {
  "person.mario": {
    "sensor": "sensor.mario_sm_s24_distance",
    "threshold_m": 100,
    "stale_check": false,
    "zone_yellow_m": 500,
    "zone_yellow_wait": 5,
    "wifi_tracker": "binary_sensor.mario_wifi_state",
    "require": 2
  }
}
```

| Campo | Significato |
|---|---|
| `sensor` | Sensore distanza (metri) della Companion App |
| `threshold_m` | Sotto questa distanza sei "in casa": l'allarme non arma e può disarmare |
| `stale_check` | `false` (consigliato) = il dato di distanza è sempre valido; `true` = ignorato se più vecchio di `max_age_min` (default 30 min) |
| `zone_yellow_m` / `zone_yellow_wait` | **Zona gialla**: se sei tra la soglia e questa distanza, HomeMind aspetta N minuti prima di armare (utile se esci a buttare la spazzatura). Se rientri nella zona verde prima, annulla |
| `wifi_tracker` | Opzionale: entità WiFi del telefono (`device_tracker` o `binary_sensor`) come seconda fonte |
| `require` | Quante fonti devono confermare che sei fuori prima di armare (GPS, WiFi, distanza). Default `1`. Se ne imposti più di quelle disponibili, HomeMind usa quelle che ci sono |

HomeMind gestisce da solo i casi tipici: GPS che rimbalza al rientro (anti-bounce 5 minuti), dati WiFi "fermi" quando il telefono perde la rete, sensori che diventano `unavailable`.

---

## Tracciamento telefoni — "Dove è stato?" 🗺️

Chiedi a HomeMind dove si è trovata una persona, con **indirizzi reali** (OpenStreetMap/Nominatim, gratuito, nessuna API key).

### Configurazione (pagina web → 📱 Tracker)

```json
"location_tracker": {
  "agostino": "device_tracker.sm_s931b",
  "rosa":     "device_tracker.sm_a166b"
}
```

Il `device_tracker` lo trovi in **Strumenti per sviluppatori → Stati** (cerca `device_tracker.`). Deve avere latitudine/longitudine (tracker GPS della Companion App, non solo WiFi).

### Come funziona

1. Legge lo storico GPS del telefono da HA.
2. Raggruppa i punti vicini (raggio 200 m) in **soste**; tollera i buchi di segnale (schermo spento, fino a 120 min).
3. Scarta le soste brevi (sotto 8 minuti).
4. Riconosce **🏠 Casa** dalla zona home di HA e converte le altre coordinate in indirizzo.

### Comandi

```
dove è stato Agostino oggi?          → ultime 24 ore
percorso di Rosa                     → ultime 24 ore
dove era Agostino ultime 5 ore       → ultime 5 ore
soste di Agostino ieri               → ieri, dalle 00:00 alle 24:00
dove era Rosa il 5 ottobre           → quel giorno (anche "5/10" o "05-10-2026")
tutti i posti di Agostino oggi       → include anche le soste brevi (da 3 minuti)
```

Senza una data il risultato è ordinato per durata; con una data (o "ieri") è in **ordine cronologico**, così vedi il giro della giornata. Di default vengono mostrate le soste di almeno 10 minuti (scrivi "tutti" o "anche le brevi" per scendere a 3).

> ℹ️ **Quanto indietro si può andare?** Per i giorni passati HomeMind legge lo storico di Home Assistant, che di default conserva solo **10 giorni** (`purge_keep_days` del *recorder*). Se chiedi un giorno che non ha più dati, HomeMind te lo dice chiaramente ("Nessun dato GPS per il 5/10/2026") invece di mostrarti altro. Per tenere più storico aggiungi in `configuration.yaml` di HA:
>
> ```yaml
> recorder:
>   purge_keep_days: 30
> ```
>
> HomeMind salva inoltre le soste di ogni giorno nel proprio database (`/config/homemind_patches/db/homemind.db`) mentre è in esecuzione, e all'avvio recupera fino a 30 giorni dallo storico disponibile. Il limite massimo per una singola richiesta è di 30 giorni.

---

## Antifurto automatico 🔒

HomeMind può armare e disarmare il tuo allarme di Home Assistant in base alla presenza.

### Trovare l'entità dell'allarme

**Strumenti per sviluppatori → Stati → `alarm_control_panel`**

```json
"alarm_panel": "alarm_control_panel.home_alarm"
```

oppure, scegliendo la modalità di armamento:

```json
"alarm_panel": { "entity": "alarm_control_panel.risco_casa", "arm_mode": "armed_away" }
```

### Come si comporta: `alarm_auto_arm`

| Valore | Comportamento |
|---|---|
| `"auto"` | **(default)** Arma da solo quando tutti sono fuori |
| `"notify"` | Ti chiede conferma su Telegram con i bottoni **✅ Sì, attiva antifurto / ❌ No, lascia disarmato**. Hai **10 minuti** per rispondere: se rispondi *No* (o non rispondi) non arma e non lo ripropone per quell'uscita; viene riproposto alla prossima uscita |
| `"disabled"` | Non tocca mai l'allarme. Gestisce solo luci/clima (vedi sotto) |

Esempio del messaggio in modalità `notify`:

```
🏠 Casa vuota — 19:32
Fuori: Mario, Lucia

Vuoi attivare l'antifurto?
Hai 10 minuti per rispondere.

[✅ Sì, attiva antifurto]  [❌ No, lascia disarmato]
```

### Altre opzioni

| Opzione | Significato |
|---|---|
| `alarm_arm_mode` | `armed_away` (default) · `armed_home` · `armed_night` · `armed_vacation` |
| `alarm_extra_panels` | Partizioni aggiuntive (Paradox, DSC…) armate/disarmate insieme alla principale, con 1 s di pausa fra l'una e l'altra |
| `alarm_on_leave` | Lista di entità da spegnere/chiudere all'uscita (luci, switch, clima, tapparelle, media player, input_boolean). Se vuota: spegne tutte le luci e il clima |
| `alarm_disable_entities` | Solo con `disabled`: `true` = spegne comunque le entità, `false` = solo notifica |
| `alarm_disable_notify` | Solo con `disabled` e `alarm_disable_entities: false`: `false` = silenzio totale |

```json
"alarm_panel": "alarm_control_panel.partizione_principale",
"alarm_auto_arm": "notify",
"alarm_arm_mode": "armed_away",
"alarm_extra_panels": ["alarm_control_panel.garage", "alarm_control_panel.esterno"],
"alarm_on_leave": ["light.sala", "switch.tv", "cover.tapparella_cucina"]
```

### Le protezioni integrate (perché non arma "a caso")

- **Uscita:** HomeMind aspetta 8 secondi (30 se la distanza dice che sei ancora vicino o il dato è vecchio) e poi ricontrolla che *tutti* siano fuori.
- **GPS ballerino:** prima di armare rilegge la distanza reale; se qualcuno è sotto la soglia (`threshold_m`), **non arma**.
- **Movimento in casa:** se un sensore di movimento è scattato negli ultimi **10 minuti**, **non arma** (qualcuno è fisicamente in casa).
- **Allarme già in `armed_home`/`armed_night`/`armed_vacation`:** non lo modifica mai (l'utente lo gestisce a mano).
- **Cooldown** fra due armamenti e fra due disarmi per evitare ripetizioni.
- **Multi-fonte** (`require` > 1): arma solo se abbastanza fonti concordano.

### Rientro e disarmo

Quando rientri (GPS o distanza sotto soglia), HomeMind attende **20 secondi** anti-rimbalzo, controlla che tu sia ancora a casa e **disarma** (anche le partizioni extra). Se l'allarme va in *pending* mentre stai rientrando, disarma subito.

Il **messaggio di benvenuto** parte solo se eri via da almeno 5 minuti e la distanza ha confermato un'uscita fisica (così non ti arriva se sei sempre rimasto in casa), al massimo uno ogni 5 minuti.

### Quando scatta l'allarme

Se l'allarme va in *pending/triggered*, HomeMind ti manda una notifica Telegram e le **foto delle telecamere Frigate** (vedi sotto, `snapshot_on_alarm`).

---

## 📹 Frigate: telecamere, targhe, persone, cani

HomeMind si collega a **Frigate NVR** (rete locale) e offre tre cose: (1) foto quando scatta l'allarme, (2) domande in chat su cosa ha rilevato (persone, animali, auto, **targhe**), (3) **avvisi istantanei** con foto per i tipi di oggetto che scegli tu. **Non serve MQTT.**

### Cosa serve

- Frigate raggiungibile da HomeMind (es. `http://192.168.1.100:5000`).
- Per le **targhe**: Frigate **0.16 o successivo** con riconoscimento targhe (LPR) attivo.
- Gli oggetti che vuoi rilevare devono essere **tracciati** da Frigate. Esempio minimo nel `config.yml` di Frigate:

```yaml
objects:
  track:
    - person
    - dog
    - cat
    - car
    - motorcycle
    - bicycle
    - package
    - bird

lpr:
  enabled: true     # riconoscimento targhe (Frigate 0.16+) — vedi docs.frigate.video
```

> Per i dettagli su LPR (requisiti, camere dedicate, `license_plate`) segui la documentazione ufficiale di Frigate. HomeMind legge i risultati dall'API di Frigate (`/api/events`): se Frigate le salva, HomeMind le mostra.

### Configurazione in HomeMind (pagina web → 📹 Frigate)

```json
"frigate": {
  "enabled": true,
  "host": "192.168.1.100",
  "port": 5000,
  "snapshot_on_alarm": true,
  "cameras": {
    "ingresso": "binary_sensor.sensore_ingresso_occupancy",
    "giardino": "binary_sensor.sensore_giardino_occupancy"
  },
  "alerts": {
    "labels": { "person": true, "dog": true, "car": false },
    "cooldown_s": 60,
    "min_score_pct": 80
  }
}
```

| Campo | Significato |
|---|---|
| `host`, `port` | IP e porta HTTP di Frigate (default 5000) |
| `snapshot_on_alarm` | `true` = foto Telegram quando scatta l'allarme |
| `cameras` | `nome camera Frigate` → `sensore di movimento HA`. Se scatta quel sensore, la foto è della camera associata |
| `alerts.labels` | Gli **switch per nome** (vedi sotto) |
| `alerts.cooldown_s` | Pausa fra due avvisi per lo stesso oggetto sulla stessa camera |
| `alerts.min_score_pct` | Confidenza minima (0 = nessun filtro) |

Il nome della camera deve essere **identico** a quello in Frigate. Dopo aver salvato dalla pagina web, un riavvio non è necessario per gli avvisi; per host/porta/camere conviene riavviare l'add-on.

### 🚗 Domande in chat: targhe

Scrivi al bot in linguaggio naturale:

| Messaggio | Risultato |
|---|---|
| `che targhe hai rilevato?` | Targhe delle ultime 24 ore |
| `targhe oggi` · `targhe ieri` | Targhe di oggi / ieri |
| `targhe ultima ora` · `targhe ultimi 30 minuti` | Periodo personalizzato |
| `targhe garage oggi` | Solo la camera indicata |
| `hai visto la targa AB123CD?` | Cerca una targa specifica |

Per ogni targa vedi quante volte è passata, su quali camere, primo e ultimo passaggio, la confidenza e (se la targa è "nota" in Frigate) il nome. In fondo arriva la foto dell'ultimo rilevamento.

### 👤🐕🚗 Domande in chat: persone, animali, veicoli

| Messaggio | Risultato |
|---|---|
| `hai visto persone nell'ultima ora?` · `persone ultima ora` | Persone dell'ultima ora |
| `persone ultimi 30 minuti` · `persone mezz'ora` | Ultimi 30 minuti |
| `che cani hai rilevato?` · `cani ieri` | Solo cani |
| `animali` · `animali oggi` | Cani + gatti + uccelli |
| `cosa hai rilevato ieri` | Tutti gli oggetti |
| `chi è passato dal garage` | Filtro per camera |
| `auto rilevate oggi` · `pacchi oggi` | Veicoli, pacchi |

**Periodi riconosciuti:** `ultima ora`, `ultimi N minuti`, `mezz'ora`, `quarto d'ora`, `ultime 2/due ore`, `ultimi N giorni`, `oggi`, `ieri`, `settimana`, `mese`. **Senza periodo si usano le ultime 24 ore** (scritto nella prima riga della risposta).

**Foto:** dopo la lista arrivano le foto dei rilevamenti in **album da 10**, fino a un massimo di **40 per richiesta** (se ce ne sono di più, il bot lo scrive).

**Tipi riconosciuti:** persone, cani, gatti, auto, moto, bici, pacchi, uccelli, `animali`.

**Note:**
- Per `auto`, `moto` e `bici` scrivi anche "rilevate/visto" (es. `auto rilevate oggi`), altrimenti frasi come "ricarica auto oggi" verrebbero scambiate per una richiesta a Frigate.
- Le frasi di presenza in casa (`chi è a casa?`) restano gestite dall'AI/GPS, non da Frigate.
- Se una camera ha lo stesso nome di un tipo di oggetto (es. camera chiamata `auto`), scrivi `persone dalla camera auto` per filtrare la camera.

### 🔔 Avvisi istantanei con foto (switch per nome)

Nella pagina web, tab **📹 Frigate**, sezione **Avvisi istantanei per oggetto**: uno switch per ognuno di
👤 Persone · 🐕 Cani · 🐈 Gatti · 🚗 Auto · 🏍️ Moto · 🚲 Bici · 📦 Pacchi · 🐦 Uccelli.

Con lo switch **attivo**, appena Frigate rileva quell'oggetto ricevi **subito la foto** su Telegram, con camera, orario e confidenza (es. `👤 Persona — cucina · 04:25:49 · ~88%`).

- **Tutti spenti di default.** Finché sono tutti spenti il modulo non fa nessuna richiesta a Frigate.
- Funzionano **subito dopo Salva**, senza riavvio.
- HomeMind controlla Frigate ogni **4 secondi**: la foto arriva in pochi secondi.
- All'avvio, o quando accendi uno switch, **gli eventi già esistenti non generano avvisi**.
- È **indipendente dall'allarme** e dalle foto su allarme.

**Pausa tra due avvisi (`cooldown_s`, default 60 s):** per lo stesso tipo di oggetto sulla stessa camera, dopo un avviso aspetta N secondi. Metti `0` per ricevere ogni rilevamento.

**🎯 Confidenza minima (`min_score_pct`, default 0 = spento):** serve a eliminare i falsi allarmi (una sedia o un'ombra scambiata per persona, tipicamente a ~70%). Frigate dà il punteggio più basso proprio al primo avvistamento; con il filtro attivo HomeMind **aspetta che il punteggio salga**: se supera la soglia manda la foto (con il punteggio aggiornato), se l'evento finisce o passano 60 secondi sotto soglia lo **scarta**. Consiglio: parti da **80** e regola. Gli avvisi veri possono arrivare con qualche secondo di ritardo.

> ℹ️ Gli avvisi istantanei **non rispettano** l'ora di silenzio (Do Not Disturb), come le foto su allarme: se non li vuoi di notte, spegni gli switch che non ti servono.

### Verifica e risoluzione problemi Frigate

| Problema | Cosa fare |
|---|---|
| "Frigate non raggiungibile" | Controlla `host`/`port`; apri `http://IP:5000` dal browser; HomeMind e Frigate devono vedersi in rete |
| Nessuna targa/oggetto | Verifica che Frigate tracci quell'oggetto (`objects → track`) e, per le targhe, che LPR sia attivo. Controlla `http://IP:5000/api/events?limit=5`: le targhe sono nel campo `recognized_license_plate` dentro `data` |
| Troppe foto "a caso" | Alza `min_score_pct` (es. 80) e/o `cooldown_s`; spegni lo switch dell'oggetto che sbaglia |
| Non arriva nessun avviso | Nel log all'avvio cerca `FrigateAlerts: attivo — switch: …`. Se manca, nessuno switch è acceso o Frigate è disabilitato |
| La risposta usa sempre 24 ore | Stai usando una versione vecchia: aggiorna (vedi [Aggiornare HomeMind](#️-aggiornare-homemind)) e cerca `build 1.11.15` nel log |

Righe utili nel log: `homemind.frigate` (richieste a Frigate) e `homemind.frigate_alerts` (avvisi istantanei).

---

## 📧 Email

HomeMind gestisce **più account Gmail** (IMAP/SMTP) con lettura, riassunto AI, risposta guidata e auto-risposta.

### Configurazione account

1. Sull'account Google attiva la **verifica in due passaggi**.
2. Crea una **password per le app**: Account Google → Sicurezza → *Password per le app* → copia i 16 caratteri.
3. Apri la pagina **`/email`** di HomeMind → tab **⚙️ Account** → inserisci etichetta, indirizzo e password per le app → Salva.

```json
"email_accounts": [
  {
    "label": "Casa",
    "address": "nome@gmail.com",
    "app_password": "xxxx xxxx xxxx xxxx",
    "imap_host": "imap.gmail.com", "imap_port": 993,
    "smtp_host": "smtp.gmail.com", "smtp_port": 587,
    "enabled": true
  }
],
"email_check_interval_min": 30
```

> La password per le app **non** è la password di Google. Per altri provider cambia host e porte IMAP/SMTP.

### La pagina `/email`

📥 **Inbox** · 🔍 **Cerca** · 🚫 **Spam/Pulizia** (rileva e cancella spam, svuota cestino/spam) · ✍️ **Rispondi AI** (bozza guidata da AI) · 🕐 **Programmati** (invii a orario) · 🤖 **Auto-risposta** · ⚙️ **Account**

### Controllo in tempo reale

HomeMind usa **IMAP IDLE**: Gmail lo avvisa subito quando arriva una mail nuova; un controllo periodico (ogni `email_check_interval_min` minuti) fa da backup.

### Auto-risposta con regole

Una regola risponde da sola alle mail che contengono una parola chiave:

```json
"email_auto_reply_rules": [
  {
    "enabled": true,
    "keyword": "preventivo",
    "account": "nome@gmail.com",
    "match_in": "oggetto",
    "whole_word": true,
    "style": "professionale",
    "instruction": "Ringrazia e di' che risponderò entro 24 ore."
  }
]
```

| Campo | Significato |
|---|---|
| `keyword` | Parola da cercare (obbligatoria) |
| `account` | Indirizzo dell'account che risponde |
| `match_in` | `oggetto` (default) · `corpo` · `entrambi` |
| `whole_word` | `true` = parola intera (default), `false` = anche dentro altre parole |
| `style` / `instruction` | Tono e istruzioni date all'AI per scrivere la risposta |

HomeMind **non risponde mai** a indirizzi no-reply/di sistema.

### Comandi Telegram per le email

| Comando | Cosa fa |
|---|---|
| `/email` · `posta` | Menu email |
| `/email_inbox` | Ultime email |
| `/controlla_email` | Controlla subito |
| `/svuota_spam` · `/svuota_cestino` | Pulizia cartelle |
| `manda una email a Mario…` | Avvia la scrittura guidata in linguaggio naturale |

---

## 📁 Salva file dalla chat

Mandi un file al bot (documento, foto, video…), lui lo **salva in una cartella** del tuo Home Assistant e poi **cancella il messaggio da Telegram**. Comodo per bollette, PDF, foto da archiviare o file da passare a un'altra app.

### Configurazione (pagina web → 📁 File)

1. Attiva **Abilita il salvataggio dei file**.
2. Con **+ Aggiungi cartella** inserisci un **nome** (es. `documenti`) e un **percorso** (es. `/share/documenti`). La cartella viene creata se non esiste.
3. Spunta **predef.** sulla cartella da usare di solito.
4. Lascia acceso **Cancella il messaggio da Telegram dopo il salvataggio** (se lo spegni, il file resta nella chat).
5. Premi **Salva**: vale subito, senza riavvio.

```json
"file_inbox": {
  "enabled": true,
  "delete_after": true,
  "folders": [
    { "name": "documenti", "path": "/share/documenti", "default": true },
    { "name": "foto",      "path": "/media/foto" }
  ]
}
```

**Percorsi che l'add-on può scrivere:** `/config` (es. `/config/www/inbox`, visibile in HA come `/local/inbox/…`), `/share` e `/media`. Gli ultimi due sono disponibili dalla versione 1.11.15 (aggiunti alla mappa dell'add-on in `config.yaml`): dopo l'aggiornamento usa **Aggiorna/Ricostruisci**, non solo Riavvia.
Con **Docker** monta la cartella di destinazione come volume nel `docker-compose.yml`, per esempio `- /mnt/archivio:/share` e poi usa `/share/...` come percorso.

### Come si usa

Scrivi la **didascalia** del file (il testo che puoi aggiungere quando lo invii):

| Didascalia | Cosa succede |
|---|---|
| `invia nella cartella` | Salva nella cartella **predefinita** |
| `salva in documenti` · `metti in foto` | Salva nella cartella con quel **nome** |
| `invia questa foto nella cartella foto` | Idem (vince il nome indicato dopo "cartella") |
| `salva` | Cartella predefinita |
| *(nessuna didascalia)* | Il bot mostra i bottoni **📁 documenti · 📁 foto · ✖️ Annulla** |

Dopo il salvataggio ricevi una conferma con nome del file e cartella, e il messaggio con il file sparisce dalla chat.

- **Più file insieme (album):** scrivi la didascalia sul primo; tutti vanno nella stessa cartella e ricevi **un solo riepilogo**.
- **Se due cartelle e nessuna predefinita:** il bot ti chiede con i bottoni invece di indovinare.
- **Una didascalia qualunque** (es. "ecco la ricevuta") **non salva nulla da sola**: compaiono i bottoni. Anche frasi come "manda questa foto a Mario via email" non vengono scambiate per un salvataggio.
- **Foto:** Telegram le comprime. Per tenere l'originale invia l'immagine come **File** (graffetta → *File*).
- I **messaggi vocali** continuano a essere trascritti come comandi.
- **Errori di battitura:** `invia in documeti` viene capito lo stesso (per nomi di cartella di almeno 4 lettere).
- **Per capire cosa succede, guarda il log:** all'avvio e a ogni salvataggio dalla pagina compare `FileInbox: configurazione letta — interruttore=ON, cartelle=documenti→/config/ago/documenti`; a ogni file ricevuto compare `FileInbox: file document, didascalia=… → salva in 'documenti'` (oppure `chiedo la cartella`). Se non vedi nessuna riga `FileInbox`, l'add-on in esecuzione è una versione precedente alla 1.11.14.

### Sicurezza e limiti

- Le cartelle si definiscono **solo dalla pagina web**, mai dalla chat. Funziona solo per le chat autorizzate (`telegram_chat_id`).
- **Non sovrascrive mai**: se esiste già `Bolletta.pdf`, salva `Bolletta (1).pdf`.
- Il nome del file viene ripulito (niente percorsi o `../`) e il file è scritto prima in un `.part`, poi rinominato.
- Rifiuta cartelle di sistema (`/etc`, `/usr`, `/root`…) e percorsi non assoluti.
- Il messaggio viene cancellato **solo se il salvataggio è riuscito**. In caso di errore il file resta nella chat e ricevi il motivo.
- **Limite 20 MB** per file (è il limite di Telegram per i bot).
- La cancellazione funziona nella **chat privata** con il bot (in un gruppo il bot deve essere amministratore).

| Problema | Cosa fare |
|---|---|
| "Non salvato … non scrivibile" | Controlla che il percorso sia sotto `/config`, `/share` o `/media` e di aver aggiornato l'add-on alla 1.11.14 o successiva |
| "file troppo grande" | Telegram permette ai bot solo file fino a 20 MB |
| Ricevo il messaggio *"Hai inviato un file. Per allegarlo a un'email…"* | È la risposta di sempre del bot: significa che il salvataggio file **non è attivo**. Nella scheda 📁 File accendi **Abilita il salvataggio dei file**, controlla che almeno una cartella abbia un percorso e premi **Salva**. Se scrivi una didascalia tipo "invia in documenti" a funzione spenta, il bot te lo dice esplicitamente |
| Non succede nulla | Verifica che l'interruttore sia acceso e di aver premuto Salva; il file deve avere una didascalia oppure compaiono i bottoni |
| Il messaggio non sparisce | Funziona solo in chat privata (o bot admin nel gruppo) e solo se `Cancella il messaggio…` è acceso |

---

## Energia, elettrodomestici, solare, Power Guard ⚡

### Sensori energia

```json
"energy_sensors": {
  "produzione_fv": "sensor.fv_tot",
  "consumo_casa":  "sensor.consumi_giornalieri",
  "rete_enel":     "sensor.enel_giornaliero",
  "batteria_wh":   "sensor.batteria_percentuale"
}
```

Ogni mattina HomeMind confronta i consumi con la media storica e segnala anomalie. Comandi: `/energia` · `/ieri`.

### Fasce orarie F1/F2/F3

Crea gli `utility_meter` in HA (`configuration.yaml`):

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

poi, nella pagina web (⚡ Energia):

```json
"fascia_sensors": {
  "daily_source": "sensor.enel",
  "oggi_f1": "sensor.energia_oggi_f1_f1", "oggi_f2": "sensor.energia_oggi_f1_f2", "oggi_f3": "sensor.energia_oggi_f1_f3",
  "oggi_tot": "sensor.energia_oggi_totale",
  "mese_f1": "sensor.energia_mese_f1_f1", "mese_f2": "sensor.energia_mese_f1_f2", "mese_f3": "sensor.energia_mese_f1_f3",
  "mese_tot": "sensor.energia_mese_totale"
}
```

Comandi: `consumi fascia oggi` · `consumi fascia questo mese` · `consumi fascia 10 giorni`.

### Monitor elettrodomestici (🏠 Elettrod.)

**Modalità `power`** — presa smart con sensore di potenza:

```json
"lavatrice": {
  "enabled": true, "name": "Lavatrice", "icon": "🫧", "mode": "power",
  "power_sensor": "sensor.presa_lavatrice_power",
  "power_on_threshold": 50, "power_off_threshold": 10,
  "min_cycle_minutes": 20, "max_idle_minutes": 5,
  "notify_on_start": false
}
```

**Modalità `smart`** — elettrodomestici connessi (es. Home Connect):

```json
"lavastoviglie": {
  "enabled": true, "name": "Lavastoviglie", "icon": "🍽️", "mode": "smart",
  "state_sensor": "sensor.lavastoviglie_operation_state",
  "running_states": ["Run"], "done_states": ["Finished", "Ready"]
}
```

### Ottimizzatore solare ☀️

```json
"solar_optimizer": {
  "enabled": true,
  "min_surplus_w": 500,
  "battery_soc_sensor": "sensor.batteria_percentuale",
  "battery_full_threshold": 95, "battery_full_min_fv_w": 300,
  "min_sun_elevation": 10, "confirm_minutes": 5, "cooldown_hours": 2,
  "appliances": {
    "lavatrice": { "enabled": true, "switch": "switch.presa_lavatrice", "min_surplus_w": 800, "auto_start": false }
  }
}
```

`auto_start: true` accende da solo; `false` chiede conferma.

### Power Guard ⚠️ (soglia contrattuale)

```json
"power_guard": {
  "enabled": true,
  "power_sensor": "sensor.consumo_casa_w",
  "threshold_w": 3000, "warning_pct": 90, "mode": "ask", "delay_minutes": 1,
  "appliances_priority": [
    {"name": "Lavatrice",     "switch": "switch.presa_lavatrice"},
    {"name": "Lavastoviglie", "switch": "switch.presa_lavastoviglie"}
  ]
}
```

`mode`: `warn_only` (solo avviso) · `ask` (chiede conferma) · `auto` (spegne da solo, in ordine di priorità). Comando: `/powerguard`.

---

## Clima, Do Not Disturb, filtri sensori

### Clima all'uscita

```json
"climate": {
  "climate.termostato": { "name": "Termostato casa", "switch": "switch.caldaia", "min_temp": 15, "max_temp": 30 },
  "climate.sala_clima": { "name": "Clima Sala", "type": "smartir" }
},
"climate_auto_off": true,
"climate_exclude": ["climate.valvola_cucina"]
```

Le valvole termostatiche (Netatmo, TRV) non supportano `turn_off` e danno errore 500: aggiungile a `climate_exclude` oppure metti `"climate_auto_off": false`. I climatizzatori SmartIR vogliono `"type": "smartir"`.

### 🔕 Do Not Disturb

```json
"quiet_hours": { "enabled": true, "start": 23, "end": 7 }
```

oppure da Telegram: `attiva silenzio notturno 23 7` · `disattiva silenzio`.

| 🔕 Bloccato di notte | ✅ Passa sempre |
|---|---|
| Lavatrice finita · surplus solare · spazzatura · soglia Power Guard | Allarme scattato · intrusione · casa vuota · qualcuno rientra |

### 🌡️ Filtri temperatura/umidità

```json
"temperature_sensors": ["sensor.temp_soggiorno", "sensor.temp_camera", "sensor.temperatura_esterna"],
"humidity_sensors":    ["sensor.umidita_soggiorno", "sensor.umidita_bagno"]
```

Senza configurazione HomeMind usa tutti quelli che trova. Si imposta anche dalla pagina web (🌡️ Temp/Umid).

---

## Briefing, spazzatura, memoria, alias, task

### 🌅 Briefing mattutino

```json
"custom_briefing": {
  "briefing_hour": 7, "tip_mode": "sports",
  "weather_city": "Roma", "custom_greeting": "Buongiorno! ☀️", "exclude_sections": []
}
```

`tip_mode`: `tip` (consiglio AI) · `news` (ANSA) · `sports` (ANSA sport) · `disabled`. Da Telegram: `Briefing alle 8` · `Saluto briefing Buongiorno!` · `Imposta meteo briefing Roma` · `Ripristina briefing`. Meteo a 3 giorni da open-meteo.com (nessuna chiave).

### 🗑️ Spazzatura

Carica il calendario dalla pagina **🗑️ Spazzatura** in formato **JSON** `{"AAAA-MM-GG": ["Tipo di rifiuto"]}` (esempio: `spazzatura_calendario_2026.json` nella cartella dell'add-on) e HomeMind ti avvisa la sera prima. `spazzatura_notify_hour` e `spazzatura_notify_enabled` nella configurazione dell'add-on.

### 🧠 Memoria

`/memoria` mostra cosa sa di te · `/dimentica <testo>` · `/memoria reset`. Impara le preferenze dalle conversazioni, senza duplicati.

### 🔗 Alias (comandi garantiti, anche offline)

```
memorizza che batteria fotovoltaico = sensor.inverter_battery_capacity_percent
memorizza che info energia = /energia
/alias                     → elenco
dimentica alias 2          → rimuove
cancella tutti gli alias   → reset
```

### ⏰ Task programmati

Scrivi in linguaggio naturale: `domani alle 7 accendi la caldaia` · `ogni giorno alle 19 accendi le luci`. Elenco: `/task`; cancella: `/cancella_task N`.

---

## Provider AI e fallback 🤖

HomeMind usa **più provider in cascata**: se uno è senza quota o in errore passa al successivo.

```
Messaggio → Gemini → (quota?) → Groq → (rate limit?) → Cerebras → … → modalità offline
```

Chiavi nella configurazione dell'add-on (si usano solo i provider con chiave) e ordine in `ai_provider_order`:

```yaml
gemini_api_key:   "AIzaSy..."
groq_api_key:     "gsk_..."
cerebras_api_key: "csk_..."
deepseek_api_key: ""
claude_api_key:   ""
openai_api_key:   ""        # serve anche per i messaggi vocali
ai_provider_order: "gemini,groq,cerebras,deepseek,claude,openai"
```

| Provider | Costo | Limite | Link |
|---|---|---|---|
| 🟦 Gemini | Gratis | ~1.500 richieste/giorno | [aistudio.google.com](https://aistudio.google.com) |
| ⚡ Groq | Gratis | ~12.000 token/min | [console.groq.com](https://console.groq.com) |
| 🧠 Cerebras | Gratis | 1M token/min | [cloud.cerebras.ai](https://cloud.cerebras.ai) |
| 🔵 DeepSeek | ~Gratis | $0.014/1M token | [platform.deepseek.com](https://platform.deepseek.com) |
| 🟠 Claude | A pagamento | — | [console.anthropic.com](https://console.anthropic.com) |
| 🟢 OpenAI | A pagamento | necessario per la voce | [platform.openai.com](https://platform.openai.com) |

Provider aggiuntivi (Mistral, OpenRouter, xAI, Together) si aggiungono in `person_config.json`:

```json
"ai_providers": [
  {"name": "gemini",   "model": "gemini-2.0-flash",       "api_key": "AIzaSy..."},
  {"name": "mistral",  "model": "mistral-small-latest",   "api_key": "..."}
]
```

> **Consiglio:** il contesto di HomeMind pesa 7.000–9.000 token e Groq gratuito arriva a ~12.000/min: configura almeno **Gemini + Groq + Cerebras** per evitare errori di rate limit. Comando: `/providers`.

---

## Agente, SSH e strumenti avanzati 🛠️

| Comando | Cosa fa |
|---|---|
| `/fai <obiettivo>` | Agente autonomo multi-step (leggi/scrivi file, controlla addon, ecc.) |
| `/ssh <testo>` · `/ssh cmd: <comando>` | Esegue comandi sull'host HA via SSH (configura SSH dalla pagina web) |
| `/cerca <query>` | Ricerca web con AI; `→ percorso` salva il risultato in un file |
| `/leggi` · `/scrivi` · `/ls` · `/modifica` | File di `/config` |
| `/automazioni` | Elenco; crea/modifica/elimina automazioni in linguaggio naturale |
| `/aggiornamenti` · `/riparazioni` · `/ha_sistema` | Stato di HA |
| `/readme <domanda>` | Cerca nel manuale integrato |

Elenco completo in [COMANDI.md](homemind-orchestrator/COMANDI.md) (`/comandi full`).

> ⚠️ `/ssh`, `/fai` e i tool sui file danno **accesso reale** al tuo sistema: tieni il bot privato e limita `telegram_chat_id` solo alle persone fidate.

---

## Comandi Telegram 📱

| Comando | Descrizione |
|---|---|
| `/stato` | Stato casa: persone, allarme, temperature, tapparelle |
| `/briefing` | Briefing adesso |
| `/energia` · `/ieri` · `/solare` | Energia, ieri, surplus FV |
| `/elettrodomestici` | Stato elettrodomestici |
| `/allarme` | Stato dell'allarme |
| `/routine` · `/task` · `/cancella_task N` | Routine e task programmati |
| `/powerguard` (`/pg`) | Stato Power Guard |
| `/config` · `/alias` · `/memoria` | Configurazione, alias, memoria |
| `/spazzatura` | Raccolta dei prossimi 7 giorni |
| `/providers` | Provider AI attivi |
| `/email` | Email |
| `/lingua it` · `/lingua en` | Lingua |
| `/readme [argomento]` | Manuale interattivo |
| `/comandi` | Elenco completo |

**In linguaggio naturale** (non servono comandi): luci, tapparelle, clima, allarme, energia, *"dove è stato Agostino?"*, *"targhe oggi"*, *"persone ultima ora"*, *"animali"*, *"manda una email a…"*.

---

## Pagina web 🌐

Si apre dal menu laterale di HA (*HomeMind*) oppure su `http://IP:8099` (Docker). Pagine principali:

| Pagina | A cosa serve |
|---|---|
| `/settings` | Configurazione: 👤 Persone · 🔔 Allarme · 🚶 Sensori · 🗑️ Spazzatura · ⚡ Energia · 📹 **Frigate** · 🏠 Elettrod. · 🌡️ Temp/Umid · 📍 Proximity · 📱 Tracker · 🌡️ Clima · ⚡ Guard · 📁 **File** |
| `/email` | Gestione email |
| `/providers` | Stato dei provider AI |
| `/dashboard` · `/briefing` · `/repairs` · `/regole` | Dashboard, briefing, riparazioni, regole |

---

## Esempi di configurazione

### Minima

```json
{
  "language": "it",
  "person_whitelist": ["person.mario", "person.lucia"],
  "motion_whitelist": ["binary_sensor.sensore_ingresso_occupancy"]
}
```

### Casa con antifurto GPS + Frigate (consigliata)

```json
{
  "language": "it",
  "person_whitelist": ["person.mario", "person.lucia"],
  "alarm_panel": "alarm_control_panel.home_alarm",
  "alarm_auto_arm": "notify",
  "alarm_arm_mode": "armed_away",
  "proximity_sensors": {
    "person.mario": { "sensor": "sensor.mario_sm_s24_distance", "threshold_m": 100, "stale_check": false },
    "person.lucia": { "sensor": "sensor.lucia_distance", "threshold_m": 100, "stale_check": false }
  },
  "location_tracker": { "mario": "device_tracker.sm_s24", "lucia": "device_tracker.sm_a16" },
  "frigate": {
    "enabled": true, "host": "192.168.1.100", "port": 5000, "snapshot_on_alarm": true,
    "cameras": { "ingresso": "binary_sensor.sensore_ingresso_occupancy" },
    "alerts": { "labels": { "person": true, "dog": false }, "cooldown_s": 60, "min_score_pct": 80 }
  },
  "quiet_hours": { "enabled": true, "start": 23, "end": 7 }
}
```

Tutte le altre sezioni (energia, solare, Power Guard, elettrodomestici, clima, email, briefing…) sono descritte sopra e si combinano nello stesso file.

---

## FAQ e risoluzione problemi ❓

**L'allarme si arma mentre sono ancora in casa** → configura `proximity_sensors` con il sensore distanza e una `threshold_m` adatta (es. 100). Controlla anche che non ci sia stato movimento negli ultimi 10 minuti (blocca l'armamento).

**Voglio la conferma prima di armare** → `"alarm_auto_arm": "notify"`: ricevi i bottoni ✅/❌ e hai 10 minuti.

**Non ricevo più nessuna notifica quando esco (arriva solo quella di rientro)** → controlla in pagina web → 🔔 Allarme → *Comportamento all'uscita*. Se c'è **🚫 Disabled** con i due interruttori spenti, HomeMind è **silenzioso per scelta**: non arma, non chiede conferma e non manda nemmeno "casa vuota". Nel log di avvio lo vedi dalle righe `alarm_auto_arm: disabled`, `alarm_disable_entities: False`, `alarm_disable_notify: False`. Scegli **🔔 Notify** (chiede conferma su Telegram) oppure **🤖 Auto** e premi Salva: si applica subito, senza riavvio.

| Impostazione | All'uscita di tutti |
|---|---|
| 🤖 Auto | Arma da solo e ti avvisa |
| 🔔 Notify | Ti chiede conferma con i bottoni ✅/❌ |
| 🚫 Disabled + entità ON | Non arma, spegne le entità, manda "Casa vuota" |
| 🚫 Disabled + entità OFF + notifica ON | Solo "Casa vuota" (al massimo una volta all'ora) |
| 🚫 Disabled + entità OFF + notifica OFF | **Silenzio totale** |

Se la modalità è giusta ma la domanda non arriva, nel log cerca le righe `ARM NOTIFY …` e `ARM SKIP …`: dicono il motivo (hai già risposto *No* per quell'uscita, c'è stato movimento negli ultimi 10 minuti, un telefono risulta ancora vicino, ecc.). Se esce un solo telefono su due, la domanda non parte: serve che **tutti** i telefoni configurati siano fuori.

**Non controlla il mio allarme** → imposta `alarm_panel` con l'entity_id esatto (`alarm_control_panel.…`).

**Il benvenuto non arriva** → abbassa `threshold_m` (es. 50) e verifica che la Companion App aggiorni la distanza in background (batteria: escludi l'app dal risparmio energetico). Arriva solo se sei stato via almeno 5 minuti.

**Paradox/DSC arma una sola partizione** → usa `alarm_extra_panels`.

**I termostati si spengono quando esco / errore 500 sul clima** → `climate_auto_off: false` o `climate_exclude` (valvole TRV).

**SmartIR errore 400** → aggiungi `"type": "smartir"` al blocco climate.

**Risponde solo la prima volta poi dà errore** → rate limit di Groq gratuito: aggiungi Cerebras e Gemini come fallback.

**"Dove è stato X?" non risponde** → configura `location_tracker` con un `device_tracker` che abbia le coordinate GPS (non solo WiFi).

**"Dove era X il 5 ottobre" dice che non ci sono dati** → Home Assistant ha già cancellato quel giorno (di default tiene 10 giorni): aumenta `purge_keep_days` nel *recorder*. Vale solo per i giorni futuri: quelli già cancellati non si recuperano.

**"Dove è stato X" mostra una sola sosta (🏠 Casa)** → di solito è corretto: se il telefono è rimasto a casa tutto il periodo, c'è una sola sosta. Prova con `tutti i posti` per vedere anche quelle brevi.

**Non vedo le novità dopo aver copiato i file** → vedi [Aggiornare HomeMind](#️-aggiornare-homemind): serve Aggiorna/Ricostruisci, non basta Riavvia. Controlla `build 1.11.15` nel log.

**Docker non si connette a HA** → usa `http://host.docker.internal:8123` se sono sullo stesso host, e verifica il token.

---

# 🇬🇧 English

## What is HomeMind

HomeMind is a **Home Assistant add-on** that adds an AI brain to your home. It understands context, learns your routine, controls your devices from natural-language Telegram messages (voice too), and only alerts you when it matters.

## Features (new in 1.11.10 – 1.11.15 marked 🆕)

- 🔒 **GPS-based alarm**: arms when everyone leaves, disarms when you return. Modes: `auto`, `notify` (✅/❌ buttons, 10-minute timeout), `disabled`. Safety nets: GPS bounce protection, real-distance re-check, 10-minute motion block, multi-source confirmation, yellow zone.
- 🗺️ **Phone tracking**: "Where has Agostino been today?" → stops with real addresses (OpenStreetMap, free).
- 📷 **Frigate**: camera snapshots on alarm.
- 🆕 🚗 **License plates via Telegram**: "what plates did you detect?", "plates last hour", "did you see plate AB123CD?" (Frigate ≥ 0.16 with LPR).
- 🆕 👤🐕🚗 **People / pets / vehicles via Telegram**: "people last hour", "animals", "dogs yesterday" — filtered by type, camera and period (`last hour`, `30 minutes`, `today`, `yesterday`…), with photo albums (up to 40).
- 🆕 🔔 **Instant Frigate alerts**: per-object switches in the web UI (person, dog, cat, car, motorcycle, bicycle, package, bird) → photo on Telegram within seconds. Cooldown and 🆕 **minimum confidence** (%) to cut false positives.
- 🆕 📁 **Save files from chat**: send a file to the bot with the caption "invia nella cartella" (or "salva in <folder>"); HomeMind saves it into a folder you set in the web UI (tab 📁 File) and deletes the message from Telegram. No caption → folder buttons. Never overwrites, 20 MB limit, albums supported.
- 📧 **Email**: multi-account Gmail (IMAP IDLE), AI summaries, guided replies, rule-based auto-reply, scheduled sending, spam cleanup.
- ⚡ Energy analysis, F1/F2/F3 bands, appliance monitor, solar optimizer, Power Guard.
- 🌅 Morning briefing, trash reminders, memory, routines, aliases, scheduled tasks.
- 🤖 Multi-AI with automatic fallback (Gemini, Groq, Cerebras, DeepSeek, Claude, OpenAI; Mistral/OpenRouter/xAI/Together via config).
- 🖥️ SSH terminal, autonomous agent (`/fai`), file tools, automation editing from chat.

## Installation

- **HAOS add-on:** Add-on Store → ⋮ → Repositories → `https://github.com/ago19800/HomeMind` → Install **HomeMind Orchestrator** → Configure (Telegram token + chat id + at least one AI key) → Start.
- **Local add-on:** copy `homemind-orchestrator` into `/addons`, then Add-on Store → ⋮ → Check for updates.
- **Docker:** see the Italian section (`docker-compose.yml` + `.env`).

**Updating:** Home Assistant only offers an update when the `version` in `config.yaml` changes. For local add-ons replace **all** files, then Check for updates → **Update/Rebuild**. A plain **Restart does not apply code changes**. Check the log for `FrigateAlertWatcher avviato — build 1.11.15`.

## Frigate quick start

1. In Frigate's `config.yml` track the objects you need (`objects → track: [person, dog, cat, car]`) and, for plates, enable `lpr` (Frigate 0.16+).
2. In HomeMind's web UI → **📹 Frigate**: set `host`/`port`, map each camera to a motion sensor, turn on the switches you want, set the **pause** (default 60 s) and the **minimum confidence** (try 80), then **Save**.
3. Ask on Telegram: `plates today`, `people last hour`, `animals`.

Config keys: `frigate.enabled`, `host`, `port`, `snapshot_on_alarm`, `cameras`, `alerts.labels`, `alerts.cooldown_s`, `alerts.min_score_pct`.

> Instant alerts do not honor Do Not Disturb hours (same as alarm snapshots).

## Telegram basics

`/stato` status · `/energia` energy · `/briefing` briefing · `/email` email · `/providers` AI providers · `/readme <topic>` manual · `/comandi` full list. Natural language works for lights, covers, climate, alarm, energy, tracking and Frigate queries.

---

**HomeMind Orchestrator** — *La tua casa, finalmente intelligente. / Your home, finally intelligent.*

[![PayPal](https://img.shields.io/badge/PayPal-Dona%20Ora-00457C?logo=paypal&style=for-the-badge)](https://paypal.me/ago19800)

[🔝 Torna su / Back to top](#-homemind-orchestrator)
