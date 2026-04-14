# 🐳 HomeMind — Installazione Docker Standalone

Per chi usa **Home Assistant Core**, **HA Container**, **Unraid**, **NAS** o qualsiasi sistema Docker.

---

## Prerequisiti

- Docker + Docker Compose installati
- Home Assistant accessibile via rete (es. `http://192.168.1.100:8123`)
- Long-Lived Access Token di HA
- Bot Telegram configurato
- Almeno una API key AI (Gemini o Groq — entrambi gratuiti)

---

## Installazione rapida

```bash
# 1. Crea cartella
mkdir ~/homemind && cd ~/homemind

# 2. Scarica i file
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/homemind-orchestrator/docker-compose.yml
curl -O https://raw.githubusercontent.com/ago19800/HomeMind/main/.env.example

# 3. Crea il tuo .env
cp .env.example .env
nano .env   # compila con i tuoi dati

# 4. Avvia
docker-compose up -d

# 5. Controlla i log
docker-compose logs -f
```

---

## Configurazione .env

```env
# Home Assistant
HA_URL=http://192.168.1.100:8123
HA_TOKEN=eyJhbGciOiJ...   # Long-Lived Token da HA → Profilo → Sicurezza

# Telegram
TELEGRAM_TOKEN=1234567890:AABBCCDDee...
TELEGRAM_CHAT_ID=123456789

# AI (almeno uno obbligatorio)
GEMINI_API_KEY=AIzaSy...    # Gratis: aistudio.google.com
GROQ_API_KEY=gsk_...        # Gratis: console.groq.com
```

### Come ottenere il Long-Lived Token HA
1. HA → clicca sul tuo profilo (in basso a sinistra)
2. Scorri fino a **Sicurezza**
3. **Token di lunga durata** → **Crea token**
4. Dai un nome (es. "HomeMind") e copia il token

---

## Configurazione avanzata

Dopo il primo avvio, HomeMind crea automaticamente:
```
~/homemind_data/
  homemind_patches/
    person_config.json   ← configura qui persone, sensori, allarme, ecc.
    spazzatura_calendario.json
```

Modifica `person_config.json` con le tue entità HA — stessa sintassi dell'addon.

---

## Aggiornamento

```bash
docker-compose pull
docker-compose up -d
```

---

## Unraid

1. Community Applications → cerca "HomeMind" (se disponibile)
   oppure usa **Add Container** manualmente:
   - Repository: `ghcr.io/ago19800/homemind:latest`
   - Volume: `/mnt/user/appdata/homemind:/data/homemind`
   - Aggiungi tutte le variabili d'ambiente dal `.env.example`

---

## Differenze rispetto all'addon HAOS

| Funzione | Addon HAOS | Docker Standalone |
|----------|-----------|-------------------|
| Installazione | Add-on Store | docker-compose |
| Configurazione | UI Addon | file .env |
| person_config.json | /config/homemind_patches/ | volume /data/homemind/homemind_patches/ |
| Tutte le funzioni AI | ✅ | ✅ |
| Dashboard web | ✅ | ✅ (porta 8099) |
| Aggiornamenti auto | ✅ | docker-compose pull |
