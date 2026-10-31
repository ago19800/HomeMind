"""
Helper TTS unificato per Alexa.

Supporta più integrazioni Home Assistant:
  1) Alexa Media Player (HACS) → notify.alexa_media con type:tts
  2) Alexa Devices (ufficiale)  → notify.send_message su notify.<entity>
  3) Media player generico       → media_player.play_media con announce

Strategia: tenta in cascata. Appena una funziona, si ferma.
Un cache interno ricorda quale strategia funziona per ogni speaker,
così le chiamate successive sono immediate.
"""
import asyncio
import logging

logger = logging.getLogger("homemind.alexa_tts")

# Cache per-speaker della strategia vincente: eid → "media"|"devices"|"play_media"|None
_strategy_cache: dict = {}


async def _try_media_player_hacs(rest, eid: str, message: str) -> bool:
    """Strategia 1: notify.alexa_media (integrazione HACS Alexa Media Player)."""
    try:
        await rest.call_service(
            "notify", "alexa_media",
            {"target": eid, "message": message, "data": {"type": "tts"}}
        )
        return True
    except Exception as e:
        logger.debug("alexa_media FAIL su %s: %s", eid, e)
        return False


async def _try_alexa_devices(rest, eid: str, message: str) -> bool:
    """Strategia 2: integrazione ufficiale Alexa Devices.
    L'entità notify si chiama tipicamente notify.<stessa_parte_dopo_il_dot>.
    Es: media_player.echo_cucina → notify.echo_cucina
    """
    try:
        notify_eid = "notify." + eid.split(".", 1)[1]
        await rest.call_service(
            "notify", "send_message",
            {"message": message},
            target={"entity_id": notify_eid}
        )
        return True
    except Exception as e:
        logger.debug("alexa_devices notify FAIL su %s: %s", eid, e)
        return False


async def _try_play_media_announce(rest, eid: str, message: str) -> bool:
    """Strategia 3: media_player.play_media con TTS URL (fallback universale).
    Funziona con Google Cast, Sonos, speaker generici.
    """
    try:
        # Usa il servizio tts.speak se disponibile, target il media_player
        await rest.call_service(
            "tts", "speak",
            {
                "entity_id": "tts.google_translate_en_com",  # fallback comune
                "media_player_entity_id": eid,
                "message": message,
            }
        )
        return True
    except Exception as e:
        logger.debug("tts.speak FAIL su %s: %s", eid, e)
        return False


async def speak_on_speaker(rest, eid: str, message: str, volume: float = 0.5) -> bool:
    """
    Invia un messaggio TTS su un singolo speaker con strategia automatica.

    Ritorna True se almeno una strategia ha funzionato, False se tutte falliscono.
    """
    if not rest or not eid or not message:
        return False

    # Imposta volume (best effort, non blocca se fallisce)
    try:
        await rest.call_service(
            "media_player", "volume_set",
            {"volume_level": max(0.0, min(1.0, float(volume)))},
            target={"entity_id": eid}
        )
    except Exception as e:
        logger.debug("volume_set FAIL su %s: %s (continuo comunque)", eid, e)

    # Se abbiamo già una strategia cached per questo speaker, la riusiamo
    cached = _strategy_cache.get(eid)
    if cached == "media":
        if await _try_media_player_hacs(rest, eid, message):
            return True
    elif cached == "devices":
        if await _try_alexa_devices(rest, eid, message):
            return True
    elif cached == "play_media":
        if await _try_play_media_announce(rest, eid, message):
            return True

    # Prova cascata completa
    if await _try_media_player_hacs(rest, eid, message):
        _strategy_cache[eid] = "media"
        logger.info("Alexa TTS: %s → strategia=alexa_media (HACS)", eid)
        return True
    if await _try_alexa_devices(rest, eid, message):
        _strategy_cache[eid] = "devices"
        logger.info("Alexa TTS: %s → strategia=notify.send_message (Alexa Devices)", eid)
        return True
    if await _try_play_media_announce(rest, eid, message):
        _strategy_cache[eid] = "play_media"
        logger.info("Alexa TTS: %s → strategia=tts.speak (generico)", eid)
        return True

    logger.warning("Alexa TTS: tutte le strategie fallite per %s", eid)
    return False


async def speak_on_speakers(rest, speakers: list, message: str, volume: float = 0.5) -> dict:
    """
    Invia TTS contemporaneamente su più speaker.

    Ritorna: {"ok": int, "fail": int, "errors": list[str]}
    """
    if not speakers or not message or not rest:
        return {"ok": 0, "fail": 0, "errors": ["parametri mancanti"]}

    results = await asyncio.gather(
        *[speak_on_speaker(rest, sp, message, volume) for sp in speakers],
        return_exceptions=True
    )
    ok = sum(1 for r in results if r is True)
    fail = len(results) - ok
    errors = []
    for sp, r in zip(speakers, results):
        if isinstance(r, Exception):
            errors.append(f"{sp}: {r}")
        elif r is False:
            errors.append(f"{sp}: tutte le strategie fallite")
    return {"ok": ok, "fail": fail, "errors": errors}


def is_likely_alexa(eid: str, attrs: dict) -> bool:
    """Euristica per identificare probabili speaker Alexa dai loro attributi."""
    eid_low = eid.lower()
    if any(k in eid_low for k in ("echo", "alexa", "dot", "show", "fire", "studio")):
        return True
    # Attributi tipici Alexa Media Player
    if attrs.get("last_called_timestamp") is not None:
        return True
    if attrs.get("last_called") is not None:
        return True
    # Integrazione ufficiale
    if "alexa" in str(attrs.get("source", "")).lower():
        return True
    return False

def list_alexa_capable_media_players(state_cache: dict) -> list:
    """Ritorna lista ordinata di media_player candidati come speaker TTS.

    Include stati validi (idle/playing/paused/on/off/standby/home/unavailable).
    Marca con is_alexa=True gli speaker che sembrano essere Amazon Alexa.
    Ritorna: [{"eid": str, "name": str, "state": str, "is_alexa": bool}, ...]
    """
    valid_states = {"idle", "playing", "paused", "on", "off", "standby", "home", "unavailable"}
    out = []
    for eid, s in (state_cache or {}).items():
        if not eid.startswith("media_player."):
            continue
        st = s.get("state", "unknown")
        if st not in valid_states:
            continue
        attrs = s.get("attributes", {}) or {}
        name = attrs.get("friendly_name", eid)
        out.append({
            "eid": eid,
            "name": name,
            "state": st,
            "is_alexa": is_likely_alexa(eid, attrs),
        })
    # Ordina: prima Alexa, poi per nome
    out.sort(key=lambda x: (not x["is_alexa"], x["name"].lower()))
    return out
