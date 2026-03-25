#!/bin/bash
# ============================================================
# HomeMind Orchestrator — STANDALONE MODE
# Per Docker/Unraid/NAS/HA Core/HA Container
# 
# Variabili d'ambiente richieste:
#   HA_URL            → http://192.168.1.100:8123
#   HA_TOKEN          → Long-Lived Access Token di HA
#   TELEGRAM_TOKEN    → Token del bot Telegram (@BotFather)
#   TELEGRAM_CHAT_ID  → Il tuo Chat ID (@userinfobot)
#
# Almeno un provider AI (es. Gemini + Groq gratuiti):
#   GEMINI_API_KEY    → da aistudio.google.com
#   GROQ_API_KEY      → da console.groq.com
# ============================================================
set -e

echo "[HomeMind] Avvio in modalità STANDALONE"

# ── Validazione variabili obbligatorie ───────────────────────
if [ -z "$HA_URL" ]; then
    echo "[HomeMind] ERRORE: HA_URL non impostata (es: http://192.168.1.100:8123)"
    exit 1
fi
if [ -z "$HA_TOKEN" ]; then
    echo "[HomeMind] ERRORE: HA_TOKEN non impostato (Long-Lived Access Token)"
    exit 1
fi
if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "[HomeMind] ERRORE: TELEGRAM_TOKEN non impostato"
    exit 1
fi
if [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "[HomeMind] ERRORE: TELEGRAM_CHAT_ID non impostato"
    exit 1
fi

# ── Cartelle dati ────────────────────────────────────────────
# In standalone: /data/homemind è il volume persistente
PATCHES_DIR="${HM_DATA_DIR:-/data/homemind}/homemind_patches"
mkdir -p "$PATCHES_DIR"
echo "[HomeMind] Dati in: $PATCHES_DIR"

# Crea il link /config → /data/homemind per compatibilità con il codice
if [ ! -L /config ] && [ ! -d /config ]; then
    ln -s "${HM_DATA_DIR:-/data/homemind}" /config
fi

# Calendario spazzatura
CAL_FILE="$PATCHES_DIR/spazzatura_calendario.json"
BUILTIN_CAL="/app/spazzatura_calendario_2026.json"
if [ ! -f "$CAL_FILE" ] && [ -f "$BUILTIN_CAL" ]; then
    cp "$BUILTIN_CAL" "$CAL_FILE"
    echo "[HomeMind] Creato calendario spazzatura"
fi

# Config persona default
PERSON_FILE="$PATCHES_DIR/person_config.json"
PERSON_DEFAULT="/app/person_config.default.json"
if [ ! -f "$PERSON_FILE" ] && [ -f "$PERSON_DEFAULT" ]; then
    cp "$PERSON_DEFAULT" "$PERSON_FILE"
    echo "[HomeMind] Creato person_config.json — modificalo con i tuoi dati"
fi

# ── Provider AI — costruisci JSON lista ─────────────────────
ORDER="${AI_PROVIDER_ORDER:-gemini,groq,cerebras,deepseek,claude,openai}"

declare -A KEYS
declare -A MDLS
KEYS[gemini]="${GEMINI_API_KEY:-}"
MDLS[gemini]="${GEMINI_MODEL:-gemini-2.0-flash}"
KEYS[groq]="${GROQ_API_KEY:-}"
MDLS[groq]="${GROQ_MODEL:-llama-3.3-70b-versatile}"
KEYS[cerebras]="${CEREBRAS_API_KEY:-}"
MDLS[cerebras]="${CEREBRAS_MODEL:-llama3.1-8b}"
KEYS[deepseek]="${DEEPSEEK_API_KEY:-}"
MDLS[deepseek]="${DEEPSEEK_MODEL:-deepseek-chat}"
KEYS[claude]="${CLAUDE_API_KEY:-}"
MDLS[claude]="${CLAUDE_MODEL:-claude-3-5-haiku-20241022}"
KEYS[openai]="${OPENAI_API_KEY:-}"
MDLS[openai]="${OPENAI_MODEL:-gpt-4o-mini}"
KEYS[mistral]="${MISTRAL_API_KEY:-}"
MDLS[mistral]="${MISTRAL_MODEL:-mistral-small-latest}"

AI_PROVIDERS_JSON="["
FIRST=1
IFS=',' read -ra NAMES <<< "$ORDER"
for NAME in "${NAMES[@]}"; do
  NAME=$(echo "$NAME" | tr -d ' ')
  KEY="${KEYS[$NAME]:-}"
  MDL="${MDLS[$NAME]:-}"
  [ -z "$KEY" ] && continue
  [ "$FIRST" -eq 0 ] && AI_PROVIDERS_JSON+=","
  AI_PROVIDERS_JSON+="{\"name\":\"$NAME\",\"model\":\"$MDL\",\"api_key\":\"$KEY\"}"
  FIRST=0
done
AI_PROVIDERS_JSON+="]"

if [ "$AI_PROVIDERS_JSON" = "[]" ]; then
    echo "[HomeMind] ERRORE: nessun provider AI configurato!"
    echo "           Imposta almeno GEMINI_API_KEY o GROQ_API_KEY"
    exit 1
fi

export HM_AI_PROVIDERS="$AI_PROVIDERS_JSON"

# Retrocompatibilità
FIRST_NAME=$(echo "$AI_PROVIDERS_JSON" | python3 -c "import sys,json; pl=json.load(sys.stdin); print(pl[0]['name'] if pl else '')" 2>/dev/null || echo "")
FIRST_MDL=$(echo  "$AI_PROVIDERS_JSON" | python3 -c "import sys,json; pl=json.load(sys.stdin); print(pl[0]['model'] if pl else '')" 2>/dev/null || echo "")
FIRST_KEY=$(echo  "$AI_PROVIDERS_JSON" | python3 -c "import sys,json; pl=json.load(sys.stdin); print(pl[0]['api_key'] if pl else '')" 2>/dev/null || echo "")
export HM_AI_PROVIDER="$FIRST_NAME"
export HM_AI_MODEL="$FIRST_MDL"
export HM_AI_API_KEY="$FIRST_KEY"

# ── Variabili HomeMind ───────────────────────────────────────
export HM_TELEGRAM_TOKEN="$TELEGRAM_TOKEN"
export HM_TELEGRAM_CHAT="$TELEGRAM_CHAT_ID"
export HM_ALARM_CODE="${ALARM_CODE:-1234}"
export HM_LOG_LEVEL="${LOG_LEVEL:-info}"
export HM_NOTIFY_ENTITY="${NOTIFY_ENTITY:-}"
export HM_SPAZZATURA_NOTIFY_HOUR="${SPAZZATURA_NOTIFY_HOUR:-20}"
export HM_SPAZZATURA_NOTIFY_ENABLED="${SPAZZATURA_NOTIFY_ENABLED:-true}"

# ── Connessione a Home Assistant ─────────────────────────────
# Normalizza HA_URL: rimuovi trailing slash
HA_URL="${HA_URL%/}"

export HA_HOST="${HA_URL}"
export HA_REST_BASE="${HA_URL}/api"
# WebSocket: converti http→ws, https→wss
export HA_WS_URL=$(echo "$HA_URL" | sed 's|^http://|ws://|; s|^https://|wss://|')"/api/websocket"
export HA_TOKEN="$HA_TOKEN"
export HM_HA_LOG_PATH=""
export HM_STANDALONE_MODE="true"

# ── Riepilogo ────────────────────────────────────────────────
echo "[HomeMind] Modalità: STANDALONE (Docker)"
echo "[HomeMind] HA URL:   $HA_URL"
echo "[HomeMind] HA WS:    $HA_WS_URL"
echo "[HomeMind] Telegram: chat $TELEGRAM_CHAT_ID"
echo "[HomeMind] Provider attivi:"
echo "$AI_PROVIDERS_JSON" | python3 -c "
import sys,json
pl=json.load(sys.stdin)
if not pl:
    print('  ⚠️  Nessun provider! Imposta almeno GEMINI_API_KEY')
for i,p in enumerate(pl):
    print(f'  {i+1}. {p[\"name\"]} — {p[\"model\"]}')
" 2>/dev/null

exec python3 /app/src/main.py
