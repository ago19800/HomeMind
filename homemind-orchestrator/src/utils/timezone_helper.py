"""
utils/timezone_helper.py — Timezone locale per tutti i moduli HomeMind.

Uso:
    from utils.timezone_helper import now_local, local_tz
    now_local().strftime("%H:%M")       # ora locale
    now_local().strftime("%d/%m %H:%M") # data+ora locale
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger  = logging.getLogger("homemind.tz")
_CONFIG = Path("/config/homemind_patches/person_config.json")
_DEFAULT = "Europe/Rome"
_tz: ZoneInfo | None = None


def _load_tz() -> ZoneInfo:
    global _tz
    if _tz is not None:
        return _tz
    tz_name = _DEFAULT
    try:
        if _CONFIG.exists():
            cfg = json.loads(_CONFIG.read_text())
            tz_name = cfg.get("timezone", _DEFAULT)
    except Exception:
        pass
    try:
        _tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Timezone '%s' non valida, uso %s", tz_name, _DEFAULT)
        _tz = ZoneInfo(_DEFAULT)
    return _tz


def local_tz() -> ZoneInfo:
    return _load_tz()


def now_local() -> datetime:
    """datetime.now() con timezone locale corretta."""
    return datetime.now(_load_tz())
