#!/bin/bash
set -e

OPTIONS="/data/options.json"
[ ! -f "$OPTIONS" ] && echo "[HomeMind] ERROR: /data/options.json not found" && exit 1

# ── Crea cartella homemind_patches in /config se non esiste ─────────────────
PATCHES_DIR="/config/homemind_patches"
if [ ! -d "$PATCHES_DIR" ]; then
    mkdir -p "$PATCHES_DIR"
    echo "[HomeMind] Creata cartella $PATCHES_DIR"
fi

# ── Crea spazzatura_calendario.json builtin se non esiste ───────────────────
CAL_FILE="$PATCHES_DIR/spazzatura_calendario.json"
BUILTIN_CAL="/app/spazzatura_calendario_lanciano_2026.json"
if [ ! -f "$CAL_FILE" ] && [ -f "$BUILTIN_CAL" ]; then
    cp "$BUILTIN_CAL" "$CAL_FILE"
    echo "[HomeMind] Creato $CAL_FILE (calendario builtin Lanciano 2026)"
fi

# ── Crea person_config.json default se non esiste ───────────────────────────
PERSON_FILE="$PATCHES_DIR/person_config.json"
PERSON_DEFAULT="/app/person_config.default.json"
if [ ! -f "$PERSON_FILE" ] && [ -f "$PERSON_DEFAULT" ]; then
    cp "$PERSON_DEFAULT" "$PERSON_FILE"
    echo "[HomeMind] Creato $PERSON_FILE (configurazione default — modificalo con i tuoi dati)"
fi

# ── Leggi chiavi per ogni provider ──────────────────────────────
GEMINI_KEY=$(jq -r '.gemini_api_key // ""' "$OPTIONS")
GEMINI_MDL=$(jq -r '.gemini_model // "gemini-2.0-flash"' "$OPTIONS")

GROQ_KEY=$(jq -r '.groq_api_key // ""' "$OPTIONS")
GROQ_MDL=$(jq -r '.groq_model // "llama-3.3-70b-versatile"' "$OPTIONS")

CEREBRAS_KEY=$(jq -r '.cerebras_api_key // ""' "$OPTIONS")
CEREBRAS_MDL=$(jq -r '.cerebras_model // "llama3.1-8b"' "$OPTIONS")

DEEPSEEK_KEY=$(jq -r '.deepseek_api_key // ""' "$OPTIONS")
DEEPSEEK_MDL=$(jq -r '.deepseek_model // "deepseek-chat"' "$OPTIONS")

CLAUDE_KEY=$(jq -r '.claude_api_key // ""' "$OPTIONS")
CLAUDE_MDL=$(jq -r '.claude_model // "claude-3-5-haiku-20241022"' "$OPTIONS")

OPENAI_KEY=$(jq -r '.openai_api_key // ""' "$OPTIONS")
OPENAI_MDL=$(jq -r '.openai_model // "gpt-4o-mini"' "$OPTIONS")

ORDER=$(jq -r '.ai_provider_order // "gemini,groq,openrouter,claude,openai"' "$OPTIONS")

# ── Costruisci lista provider JSON in ordine (solo quelli con key) ──
AI_PROVIDERS_JSON="["
FIRST=1
IFS=',' read -ra NAMES <<< "$ORDER"
for NAME in "${NAMES[@]}"; do
  NAME=$(echo "$NAME" | tr -d ' ')
  case "$NAME" in
    gemini)     KEY="$GEMINI_KEY";     MDL="$GEMINI_MDL" ;;
    groq)       KEY="$GROQ_KEY";       MDL="$GROQ_MDL" ;;
    cerebras)   KEY="$CEREBRAS_KEY";   MDL="$CEREBRAS_MDL" ;;
    deepseek)   KEY="$DEEPSEEK_KEY";   MDL="$DEEPSEEK_MDL" ;;
    claude)     KEY="$CLAUDE_KEY";     MDL="$CLAUDE_MDL" ;;
    openai)     KEY="$OPENAI_KEY";     MDL="$OPENAI_MDL" ;;
    *) continue ;;
  esac
  # Salta provider senza API key
  [ -z "$KEY" ] && continue
  [ "$FIRST" -eq 0 ] && AI_PROVIDERS_JSON+=","
  AI_PROVIDERS_JSON+="{\"name\":\"$NAME\",\"model\":\"$MDL\",\"api_key\":\"$KEY\"}"
  FIRST=0
done
AI_PROVIDERS_JSON+="]"

export HM_AI_PROVIDERS="$AI_PROVIDERS_JSON"

# ── Retrocompatibilità: primo provider come HM_AI_PROVIDER ──────
FIRST_NAME=$(echo "$AI_PROVIDERS_JSON" | python3 -c "import sys,json; pl=json.load(sys.stdin); print(pl[0]['name'] if pl else 'claude')" 2>/dev/null || echo "claude")
FIRST_MDL=$(echo  "$AI_PROVIDERS_JSON" | python3 -c "import sys,json; pl=json.load(sys.stdin); print(pl[0]['model'] if pl else '')" 2>/dev/null || echo "")
FIRST_KEY=$(echo  "$AI_PROVIDERS_JSON" | python3 -c "import sys,json; pl=json.load(sys.stdin); print(pl[0]['api_key'] if pl else '')" 2>/dev/null || echo "")

export HM_AI_PROVIDER="$FIRST_NAME"
export HM_AI_MODEL="$FIRST_MDL"
export HM_AI_API_KEY="$FIRST_KEY"

# ── Resto delle opzioni ──────────────────────────────────────────
export HM_NOTIFY_ENTITY=$(jq -r '.notify_entity // ""' "$OPTIONS")
export HM_TELEGRAM_TOKEN=$(jq -r '.telegram_bot_token // ""' "$OPTIONS")
export HM_TELEGRAM_CHAT=$(jq -r '.telegram_chat_id // ""' "$OPTIONS")
export HM_ALARM_CODE=$(jq -r '.alarm_code // "1234"' "$OPTIONS")
export HM_SPAZZATURA_NOTIFY_HOUR=$(jq -r '.spazzatura_notify_hour // "20"' "$OPTIONS")
export HM_SPAZZATURA_NOTIFY_ENABLED=$(jq -r '.spazzatura_notify_enabled // true' "$OPTIONS")
export HM_LOG_LEVEL=$(jq -r '.log_level // "info"' "$OPTIONS")
export HM_PERSON_BLACKLIST=$(jq -r '.person_blacklist // ""' "$OPTIONS")
export HM_MOTION_BLACKLIST=$(jq -r '.motion_blacklist // ""' "$OPTIONS")

export HA_HOST="supervisor"
export HA_REST_BASE="http://supervisor/core/api"
export HA_WS_URL="ws://supervisor/core/websocket"
export HA_TOKEN="${SUPERVISOR_TOKEN}"

HA_LOG=$(find /homeassistant /config /data /share -maxdepth 3 -name "home-assistant.log" 2>/dev/null | head -1)
if [ -n "$HA_LOG" ]; then
    export HM_HA_LOG_PATH="$HA_LOG"
    echo "[HomeMind] Log found: $HA_LOG"
else
    export HM_HA_LOG_PATH=""
    echo "[HomeMind] Log file not found"
fi

echo "[HomeMind] Provider attivi:"
echo "$AI_PROVIDERS_JSON" | python3 -c "
import sys,json
pl=json.load(sys.stdin)
if not pl:
    print('  ⚠️  Nessun provider configurato! Inserisci almeno una API key nelle Opzioni.')
for i,p in enumerate(pl):
    print(f'  {i+1}. {p[\"name\"]} — {p[\"model\"]}')
" 2>/dev/null || echo "  (errore lettura provider)"

exec python3 /app/src/main.py
