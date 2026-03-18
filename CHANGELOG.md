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
