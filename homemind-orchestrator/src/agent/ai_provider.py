"""
agent/ai_provider.py — Multi-provider AI con fallback automatico a cascata.

Provider supportati:
  claude, openai, gemini, groq, openrouter, mistral, xai, together, deepseek

Configurazione in /config/homemind_patches/person_config.json:
  "ai_providers": [
    {"name": "gemini",  "model": "gemini-2.0-flash",           "api_key": "AIza..."},
    {"name": "groq",    "model": "llama-3.3-70b-versatile",    "api_key": "gsk_..."},
    {"name": "claude",  "model": "claude-3-5-haiku-20241022",  "api_key": "sk-ant-..."},
    {"name": "openai",  "model": "gpt-4o-mini",                "api_key": "sk-..."}
  ]
"""
import logging
import json
from pathlib import Path
import anthropic
import openai

logger = logging.getLogger("homemind.ai")

PROVIDER_BASE_URLS = {
    "gemini":     "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq":       "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "cerebras":   "https://api.cerebras.ai/v1",
    "mistral":    "https://api.mistral.ai/v1",
    "xai":        "https://api.x.ai/v1",
    "together":   "https://api.together.xyz/v1",
    "deepseek":   "https://api.deepseek.com/v1",
}

PROVIDER_DEFAULT_MODELS = {
    "claude":     "claude-3-5-haiku-20241022",
    "openai":     "gpt-4o-mini",
    "gemini":     "gemini-2.0-flash",
    "groq":       "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
    "cerebras":   "llama3.1-8b",
    "mistral":    "mistral-small-latest",
    "xai":        "grok-beta",
    "together":   "meta-llama/Llama-3-70b-chat-hf",
    "deepseek":   "deepseek-chat",
}

PROVIDER_DISPLAY = {
    "claude":     "Claude (Anthropic)",
    "openai":     "GPT (OpenAI)",
    "gemini":     "Gemini (Google) 🆓",
    "groq":       "Groq/Llama 🆓",
    "openrouter": "OpenRouter",
    "cerebras":   "Cerebras 🆓",
    "mistral":    "Mistral AI",
    "xai":        "Grok (xAI)",
    "together":   "Together AI",
    "deepseek":   "DeepSeek",
}


class _SingleProvider:
    def __init__(self, name: str, model: str, api_key: str):
        self.name    = name
        self.model   = model or PROVIDER_DEFAULT_MODELS.get(name, "")
        self.display = PROVIDER_DISPLAY.get(name, name)

        if name == "claude":
            self.client   = anthropic.AsyncAnthropic(api_key=api_key)
            self._backend = "claude"
        elif name == "openai":
            self.client   = openai.AsyncOpenAI(
                api_key=api_key,
                max_retries=0,
                timeout=12.0,
            )
            self._backend = "openai"
        elif name in PROVIDER_BASE_URLS:
            extra = {}
            if name == "openrouter":
                extra["default_headers"] = {
                    "HTTP-Referer": "https://homemind.local",
                    "X-Title": "HomeMind",
                }
            self.client   = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=PROVIDER_BASE_URLS[name],
                max_retries=0,        # HomeMind gestisce il fallback da solo
                timeout=12.0,         # 12s max per provider → fallback veloce
                **extra,
            )
            self._backend = "openai"
        else:
            raise ValueError(f"Provider sconosciuto: {name}")

    async def ask(self, system: str, user: str, max_tokens: int = 1024,
                  json_mode: bool = False, history: list = None) -> str:
        if self._backend == "claude":
            sys_p = system
            if json_mode:
                sys_p += "\n\nCRITICAL: Respond ONLY with valid JSON. No markdown, no prose, no backticks."
            messages = []
            if history:
                for h in history[-10:]:
                    messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": user})
            msg = await self.client.messages.create(
                model=self.model, max_tokens=max_tokens,
                system=sys_p, messages=messages,
            )
            return msg.content[0].text
        else:
            msgs = [{"role": "system", "content": system}]
            if history:
                for h in history[-10:]:
                    msgs.append({"role": h["role"], "content": h["content"]})
            msgs.append({"role": "user", "content": user})
            kwargs = dict(model=self.model, max_tokens=max_tokens, messages=msgs)
            if json_mode:
                # Provider che NON supportano response_format: usano solo system prompt
                _NO_JSON_FORMAT = {"cerebras", "xai", "together"}
                if self.name not in _NO_JSON_FORMAT:
                    try:
                        kwargs["response_format"] = {"type": "json_object"}
                        resp = await self.client.chat.completions.create(**kwargs)
                        return resp.choices[0].message.content or ""
                    except Exception as _jm_err:
                        if "response_format" in str(_jm_err).lower() or "400" in str(_jm_err):
                            logger.debug("AI %s: response_format non supportato, uso prompt-only JSON", self.name)
                            kwargs.pop("response_format", None)
                        else:
                            raise
            resp = await self.client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""


class AIProvider:
    """Provider AI con fallback automatico a cascata."""

    def __init__(self, provider: str = None, model: str = None, api_key: str = None,
                 providers_config: list = None):
        self._providers: list = []

        if providers_config:
            for pc in providers_config:
                try:
                    p = _SingleProvider(pc["name"], pc.get("model", ""), pc.get("api_key", ""))
                    self._providers.append(p)
                    logger.info("AI: provider %s (%s)", p.display, p.model)
                except Exception as e:
                    logger.warning("AI: provider '%s' skip: %s", pc.get("name"), e)
        elif provider and api_key:
            p = _SingleProvider(provider, model or "", api_key)
            self._providers.append(p)
        else:
            raise ValueError("Specifica provider+api_key oppure providers_config")

        if not self._providers:
            raise ValueError("Nessun provider AI valido")

    # Compatibilità con codice esistente
    @property
    def provider(self) -> str:
        return self._providers[0].name if self._providers else "none"

    @property
    def model(self) -> str:
        return self._providers[0].model if self._providers else ""

    def status(self) -> str:
        """Lista provider per /stato o /status."""
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, p in enumerate(self._providers):
            m = medals[i] if i < 3 else "  •"
            lines.append(f"{m} {p.display} — <code>{p.model}</code>")
        last = getattr(self, "_last_used", None)
        last_line = f"\n\n⚡ <b>Ultimo a rispondere:</b> {last.display}" if last else ""
        return "🤖 <b>AI Provider configurati:</b>\n" + "\n".join(lines) + last_line

    def full_status_telegram(self) -> str:
        """Messaggio Telegram dettagliato per /providers."""
        medals = ["🥇", "🥈", "🥉"]
        last = getattr(self, "_last_used", None)

        lines = ["🤖 <b>AI Provider attivi</b>\n"]
        for i, p in enumerate(self._providers):
            m = medals[i] if i < 3 else f"  {i+1}."
            is_last = last and last.name == p.name
            star = " ← <b>ha risposto</b>" if is_last else ""
            lines.append(f"{m} <b>{p.display}</b>{star}")
            lines.append(f"   <code>{p.model}</code>")

        if last:
            lines.append(f"\n⚡ <b>Ultimo a rispondere:</b> {last.display}")
        else:
            lines.append("\n⏳ Nessuna chiamata AI ancora effettuata")

        lines.append("\n<i>Se il 1° provider fallisce, HomeMind passa automaticamente al 2°, poi al 3°.</i>")
        return "\n".join(lines)

    async def ask(self, system: str, user: str, max_tokens: int = 1024,
                  json_mode: bool = False, history: list = None) -> str:
        last_error = None
        for i, p in enumerate(self._providers):
            try:
                result = await p.ask(system, user, max_tokens, json_mode, history)
                self._last_used = p  # salva riferimento al provider
                if i == 0:
                    logger.info("AI ✅ %s", p.display)
                else:
                    logger.info("AI ✅ FALLBACK [%d/%d] %s — risposta OK", i + 1, len(self._providers), p.display)
                return result
            except Exception as e:
                last_error = e
                es = str(e).lower()
                reason = (
                    "rate limit"  if "rate_limit" in es or "429" in es else
                    "quota"       if "quota" in es else
                    "API key"     if "invalid_api_key" in es or "401" in es else
                    "modello"     if "model_not_found" in es or "404" in es else
                    str(e)[:60]
                )
                logger.warning("AI ❌ %s [%s] → prossimo provider | dettaglio: %s", p.display, reason, str(e)[:120])

        logger.error("AI: tutti i provider falliti. Ultimo: %s", last_error)
        raise RuntimeError(f"Nessun provider AI disponibile: {last_error}")

    @property
    def last_used_name(self) -> str:
        """Nome display del provider che ha risposto all'ultima chiamata."""
        p = getattr(self, "_last_used", None)
        if p:
            return p.display
        return self._providers[0].display if self._providers else "?"



def load_ai_provider_from_config(
    fallback_provider: str = None,
    fallback_model: str = None,
    fallback_api_key: str = None,
) -> AIProvider:
    """
    Carica provider da person_config.json → chiave 'ai_providers'.
    Se non presente, usa i parametri singoli legacy.
    """
    cfg_path = Path("/config/homemind_patches/person_config.json")
    try:
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            plist = cfg.get("ai_providers", [])
            if plist:
                return AIProvider(providers_config=plist)
    except Exception as e:
        logger.warning("AI config: %s — uso fallback", e)

    if fallback_provider and fallback_api_key:
        return AIProvider(provider=fallback_provider, model=fallback_model, api_key=fallback_api_key)

    raise RuntimeError("Nessun provider AI configurato in person_config.json")


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPTS (invariati)
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_ANOMALY_DETECTOR = """
Sei HomeMind, agente di rilevamento anomalie per Home Assistant.

REGOLA FONDAMENTALE — Segnala SOLO anomalie REALI:
✅ Segnala:
  - Sensore con valore FISICAMENTE IMPOSSIBILE (es. temperatura -999°C, voltaggio negativo)
  - Luce/clima ACCESO con TUTTI i residenti assenti (person = not_home)
  - Dispositivo con consumo ANOMALO (es. lavatrice a 5000W costante per ore)
  - Sensore bloccato su "unavailable" da molto tempo (stato fisso, non transitorio)
  - Sensore di potenza/energia che riporta un'unità completamente sbagliata per il tipo fisico
    (es. un sensore di CORRENTE che riporta kWh invece di A)

❌ NON segnalare (falsi positivi):
  - Differenze di capitalizzazione nelle unità (w vs W, kwh vs kWh) → NON è un errore funzionale
  - Sensori con nomi "strani" ma valori plausibili
  - Template sensor che ridefinisce un sensore esistente → è NORMALE in HA
  - Sensori con "_2", "_3" nel nome → sono duplicati template normali in HA
  - Sensori di integrazione (platform: integration) con unità kWh → CORRETTI per misure di energia
  - Sensori il cui nome contiene "voltage" ma producono kWh → possono essere integration sensor
  - Qualsiasi sensore con unique_id già noto
  - Sensori che usano states() di un altro sensore → NORMALE in template HA
  - Valori numerici plausibili per il tipo di sensore

CONTESTO CONFIGURAZIONE ESISTENTE:
{known_sensors}

Rispondi SOLO con JSON valido:
{{
  "anomalies": [
    {{
      "entity_id": "sensor.xyz",
      "reason": "descrizione precisa del problema REALE in italiano",
      "severity": "high|medium|low",
      "fix_type": "yaml_patch|service_call|none"
    }}
  ]
}}
Se nessuna anomalia REALE: {{"anomalies": []}}
"""

SYSTEM_PATCH_GENERATOR = """
Sei HomeMind, esperto di configurazione Home Assistant 2024+.

REGOLA N.1 — NON duplicare sensori esistenti.
REGOLA N.2 — Formato moderno OBBLIGATORIO:
❌ VIETATO: sensor: - platform: template
✅ OBBLIGATORIO:
   - unique_id: SLUG_fix_01
     name: "Nome"
     device_class: CLASSE
     unit_of_measurement: "UNITA"
     state_class: measurement
     state: >
       {{ states('ENTITY_ID') | float(0) }}

REGOLA N.3 — unique_id e states() IMMUTABILI dall'entity_id originale.

device_class → unità: voltage→V | power→W | energy→kWh | temperature→°C | humidity→% | current→A

Output: SOLO il blocco YAML lista. Nessun wrapper. Nessuna spiegazione.
"""

SYSTEM_LOG_ANALYZER = """
Sei HomeMind, esperto Home Assistant 2024+.
Analizza errori di log, trova la causa, genera patch YAML moderna.
Rispondi in italiano. Patch in blocco ```yaml.
"""

SYSTEM_SECURITY = """
Sei HomeMind SecurityAgent.
Analizza presenza persone e sensori di movimento.

LOGICA:
1. Se TUTTI not_home + movimento → ALLARME
2. Ultima persona esce → arma allarme + spegni luci
3. Persona rientra → disarma allarme
4. Movimento notturno (22-7) con tutti not_home → CRITICO

Rispondi SOLO JSON:
{
  "action": "alarm_on|alarm_off|lights_off|none",
  "reason": "spiegazione italiana",
  "services": [{"domain":"..","service":"..","data":{},"target":{}}],
  "notify_message": "messaggio telegram"
}
"""

SYSTEM_UI_GENERATOR = """
Sei HomeMind, architetto dashboard Lovelace HA 2024+.
Genera YAML dashboard pulita e moderna.
Output SOLO YAML valido, niente prosa, niente markdown.
"""
