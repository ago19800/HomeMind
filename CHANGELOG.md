# 🔒 HomeMind 1.0.3 — Security & Bug Fix Release

## Cosa è cambiato

Questa release risolve le vulnerabilità di sicurezza segnalate nella issue [#2](https://github.com/ago19800/HomeMind/issues/2) e include ulteriori correzioni di stabilità.

---

## 🛡️ Fix Sicurezza

### 1. Codice allarme non più esposto all'AI (Critico)
Il PIN dell'allarme veniva inviato in chiaro al provider AI esterno (Gemini, Groq, ecc.) dentro il system prompt.  
**Fix:** Il prompt ora usa un placeholder `__ALARM_CODE__` che viene sostituito con il valore reale solo nel momento della chiamata a Home Assistant — l'AI non riceve mai il codice.  
**File:** `src/main.py`

### 2. Autenticazione sulla Web UI (Alto)
Tutti gli endpoint FastAPI (`/chat`, `/spazzatura/upload`, `/api/status`, ecc.) erano accessibili senza autenticazione.  
**Fix:** Aggiunto middleware di autenticazione. Le richieste via HA Ingress passano automaticamente (già autenticate da HA). Gli accessi diretti alla porta 8099 richiedono il `SUPERVISOR_TOKEN` nell'header `Authorization: Bearer <token>`.  
**File:** `src/main.py`

### 3. Messaggi Telegram non più loggati (Medio)
Il contenuto di ogni messaggio Telegram ricevuto veniva scritto nei log dell'addon, inclusi i nomi utente degli accessi negati.  
**Fix:** I messaggi non vengono più loggati in chiaro. I log mostrano solo la lunghezza (`[23 chars]`). Gli username sono rimossi dai log di accesso negato.  
**File:** `src/telegram_bot.py`

### 4. Parsing YAML automazioni reso robusto (Medio)
Il parser delle automazioni usava regex su stringhe, facilmente ingannabile da alias o descrizioni che contenevano `- id:` o `- alias:`, con rischio di corruzione del file.  
**Fix:** Sostituito con `PyYAML` (`yaml.safe_load`) già presente nelle dipendenze. Il vecchio parser regex rimane come fallback in caso di errore.  
**File:** `src/agent/automations_manager.py`

---

## 🐛 Bug Fix

### 5. Dockerfile — file calendario non trovato al build
Il file `spazzatura_calendario_lanciano_2026.json` era stato rinominato in `spazzatura_calendario_2026.json` ma il `Dockerfile` e `run.sh` cercavano ancora il nome vecchio, causando un errore di build Docker.  
**Fix:** Aggiornati `Dockerfile` e `run.sh` con il nuovo nome del file.  
**File:** `Dockerfile`, `run.sh`

---

## ✅ Verificato su

- Home Assistant OS 2026.3.2
- Addon installato da repository GitHub
- Provider AI: Gemini, Groq, Cerebras
- Test eseguiti: alarm code non esposto nei log, messaggi Telegram mascherati, autenticazione Ingress funzionante, PyYAML attivo senza errori

---

## 📁 File modificati

| File | Modifica |
|------|----------|
| `src/main.py` | Placeholder alarm code, middleware autenticazione, fix upload path |
| `src/telegram_bot.py` | Log messaggi mascherati, username rimosso |
| `src/agent/automations_manager.py` | YAML parsing con PyYAML |
| `Dockerfile` | Nome file calendario aggiornato |
| `run.sh` | Nome file calendario aggiornato |
| `config.yaml` | Versione bump a `1.0.2` |

---

*Grazie a [@peppeg](https://github.com/peppeg) per la segnalazione delle vulnerabilità nella issue #2.*





---

## 📝 Changelog

### v1.1.0 — Bug fix & Miglioramenti (Marzo 2026)

#### 🐛 Bug risolti

**1. Cartella `/config/homemind_patches/` non creata automaticamente**
All'installazione l'addon non creava la cartella necessaria, impedendo l'avvio.
Ora `run.sh` la crea al primo avvio prima di qualsiasi operazione Python.

**2. `spazzatura_calendario.json` non creato automaticamente**
La variabile `CALENDARIO_BUILTIN` non era definita in `spazzatura.py`, causando un `NameError` al primo avvio e impedendo l'addon di partire.
Ora il calendario Lanciano 2026 è embedded nel codice come fallback e viene copiato automaticamente in `/config/homemind_patches/` se il file non esiste.

**3. `person_config.json` non creato automaticamente**
Il file di configurazione personale non veniva creato, lasciando l'utente senza un punto di partenza.
Ora viene copiato automaticamente al primo avvio con tutte le sezioni commentate e pronte da compilare.

**4. Upload calendario JSON dalla pagina web falliva sempre**
L'endpoint `/spazzatura/upload` salvava il file in `/data/` ma all'avvio successivo il codice cercava in `/config/homemind_patches/`. Il file non veniva mai trovato.
Ora viene salvato direttamente nel percorso corretto e anche con backup in `/data/`.

**5. Upload falliva con file salvati da Windows (BOM UTF-8)**
I file JSON salvati con Notepad o altri editor Windows contengono un BOM invisibile (`\xEF\xBB\xBF`) che rompeva il parser JSON con errore `Unexpected non-whitespace character at position 3`.
Fix applicato su tre livelli:
- JavaScript: lettura file via `ArrayBuffer` con rimozione manuale dei byte BOM
- JavaScript: rimozione BOM anche dal testo incollato direttamente nella textarea
- Python: stripping BOM e whitespace sul server prima del parsing

**6. URL fetch errato in HA Ingress**
Il fetch verso `/spazzatura/upload` usava un path assoluto che in HA Ingress (servito sotto `/api/hassio_ingress/xxxx/`) puntava al path sbagliato.
Corretto in URL relativo `spazzatura/upload`.

#### ✨ Nuove funzionalità

**Opzione per abilitare/disabilitare notifiche spazzatura**
Aggiunta opzione `spazzatura_notify_enabled: true/false` nella scheda Configurazione dell'addon.
Impostando `false` le notifiche serali vengono sospese senza dover modificare file.
Lo stato è visibile nel comando `/spazzatura` su Telegram (`🔔 Notifiche attive` / `🔕 Notifiche disabilitate`).

#### 📁 File modificati

| File | Modifica |
|------|----------|
| `run.sh` | Crea automaticamente `/config/homemind_patches/`, `spazzatura_calendario.json` e `person_config.json` al primo avvio |
| `Dockerfile` | Copia `spazzatura_calendario_lanciano_2026.json` e `person_config.default.json` nell'immagine |
| `src/spazzatura.py` | Aggiunto `CALENDARIO_BUILTIN`, fix avvio, nuovo parametro `notify_enabled` |
| `src/main.py` | Fix endpoint upload (path, BOM, URL relativo), lettura nuova opzione `spazzatura_notify_enabled` |
| `config.yaml` | Aggiunta opzione `spazzatura_notify_enabled` con schema `bool` |
| `person_config.default.json` | Nuovo file con tutte le sezioni commentate e pronte da compilare |
