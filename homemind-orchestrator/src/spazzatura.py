"""
spazzatura.py — Gestione calendario raccolta differenziata.

Flusso:
1. L'utente mette il PDF in /config/homemind_patches/spazzatura.pdf
2. All'avvio HomeMind legge il PDF e chiede all'AI di estrarre il calendario
3. Salva il calendario come JSON in /config/homemind_patches/spazzatura_calendario.json
4. Ogni sera alle 20:00 invia notifica Telegram con cosa buttare il giorno dopo

Formato JSON calendario:
{
  "2026-03-07": ["Plastica", "Metalli"],
  "2026-03-09": ["Organico"],
  "2026-03-11": ["Carta", "Cartone"],
  ...
}
"""
import asyncio, json, logging
from datetime import datetime, timedelta
from utils.timezone_helper import now_local
from pathlib import Path

logger = logging.getLogger("homemind.spazzatura")

# ── Calendario builtin Lanciano 2026 (fallback se nessun file trovato) ────────
CALENDARIO_BUILTIN = '''{"2026-01-02": ["Plastica e Metalli"], "2026-01-03": ["Organico + Vetro"], "2026-01-05": ["Indifferenziato"], "2026-01-06": ["Organico + Pannolini"], "2026-01-07": ["Carta"], "2026-01-08": ["Organico"], "2026-01-09": ["Plastica e Metalli"], "2026-01-10": ["Organico + Pannolini"], "2026-01-12": ["Indifferenziato"], "2026-01-13": ["Organico + Pannolini"], "2026-01-14": ["Carta"], "2026-01-15": ["Organico + Vetro"], "2026-01-16": ["Plastica e Metalli"], "2026-01-17": ["Organico + Pannolini"], "2026-01-19": ["Indifferenziato"], "2026-01-20": ["Organico + Pannolini"], "2026-01-21": ["Carta"], "2026-01-22": ["Organico"], "2026-01-23": ["Plastica e Metalli"], "2026-01-24": ["Organico + Pannolini"], "2026-01-26": ["Indifferenziato"], "2026-01-27": ["Organico + Pannolini"], "2026-01-28": ["Carta"], "2026-01-29": ["Organico + Vetro"], "2026-01-30": ["Plastica e Metalli"], "2026-01-31": ["Organico + Pannolini"], "2026-02-02": ["Indifferenziato"], "2026-02-03": ["Organico + Pannolini"], "2026-02-04": ["Carta"], "2026-02-05": ["Organico"], "2026-02-06": ["Plastica e Metalli"], "2026-02-07": ["Organico + Pannolini"], "2026-02-09": ["Indifferenziato"], "2026-02-10": ["Organico + Pannolini"], "2026-02-11": ["Carta"], "2026-02-12": ["Organico + Vetro"], "2026-02-13": ["Plastica e Metalli"], "2026-02-14": ["Organico + Pannolini"], "2026-02-16": ["Indifferenziato"], "2026-02-17": ["Organico + Pannolini"], "2026-02-18": ["Carta"], "2026-02-19": ["Organico"], "2026-02-20": ["Plastica e Metalli"], "2026-02-21": ["Organico + Pannolini"], "2026-02-23": ["Indifferenziato"], "2026-02-24": ["Organico + Pannolini"], "2026-02-25": ["Carta"], "2026-02-26": ["Organico + Vetro"], "2026-02-27": ["Plastica e Metalli"], "2026-02-28": ["Organico + Pannolini"], "2026-03-02": ["Indifferenziato"], "2026-03-03": ["Organico + Pannolini"], "2026-03-04": ["Carta"], "2026-03-05": ["Organico"], "2026-03-06": ["Plastica e Metalli"], "2026-03-07": ["Organico + Pannolini"], "2026-03-09": ["Indifferenziato"], "2026-03-10": ["Organico + Pannolini"], "2026-03-11": ["Carta"], "2026-03-12": ["Organico + Vetro"], "2026-03-13": ["Plastica e Metalli"], "2026-03-14": ["Organico + Pannolini"], "2026-03-16": ["Indifferenziato"], "2026-03-17": ["Organico + Pannolini"], "2026-03-18": ["Carta"], "2026-03-19": ["Organico"], "2026-03-20": ["Plastica e Metalli"], "2026-03-21": ["Organico + Pannolini"], "2026-03-23": ["Indifferenziato"], "2026-03-24": ["Organico + Pannolini"], "2026-03-25": ["Carta"], "2026-03-26": ["Organico + Vetro"], "2026-03-27": ["Plastica e Metalli"], "2026-03-28": ["Organico + Pannolini"], "2026-03-30": ["Indifferenziato"], "2026-03-31": ["Organico + Pannolini"], "2026-04-01": ["Carta"], "2026-04-02": ["Organico"], "2026-04-03": ["Plastica e Metalli"], "2026-04-04": ["Organico + Pannolini"], "2026-04-06": ["Indifferenziato"], "2026-04-07": ["Organico + Pannolini"], "2026-04-08": ["Carta"], "2026-04-09": ["Organico + Vetro"], "2026-04-10": ["Plastica e Metalli"], "2026-04-11": ["Organico + Pannolini"], "2026-04-13": ["Indifferenziato"], "2026-04-14": ["Organico + Pannolini"], "2026-04-15": ["Carta"], "2026-04-16": ["Organico"], "2026-04-17": ["Plastica e Metalli"], "2026-04-18": ["Organico + Pannolini"], "2026-04-20": ["Indifferenziato"], "2026-04-21": ["Organico + Pannolini"], "2026-04-22": ["Carta"], "2026-04-23": ["Organico + Vetro"], "2026-04-24": ["Plastica e Metalli"], "2026-04-25": ["Organico + Pannolini"], "2026-04-27": ["Indifferenziato"], "2026-04-28": ["Organico + Pannolini"], "2026-04-29": ["Carta"], "2026-04-30": ["Plastica e Metalli"], "2026-05-02": ["Organico + Pannolini"], "2026-05-04": ["Indifferenziato"], "2026-05-05": ["Organico + Pannolini"], "2026-05-06": ["Carta"], "2026-05-07": ["Organico + Vetro"], "2026-05-08": ["Plastica e Metalli"], "2026-05-09": ["Organico + Pannolini"], "2026-05-11": ["Indifferenziato"], "2026-05-12": ["Organico + Pannolini"], "2026-05-13": ["Carta"], "2026-05-14": ["Organico"], "2026-05-15": ["Plastica e Metalli"], "2026-05-16": ["Organico + Pannolini"], "2026-05-18": ["Indifferenziato"], "2026-05-19": ["Organico + Pannolini"], "2026-05-20": ["Carta"], "2026-05-21": ["Organico + Vetro"], "2026-05-22": ["Plastica e Metalli"], "2026-05-23": ["Organico + Pannolini"], "2026-05-25": ["Indifferenziato"], "2026-05-26": ["Organico + Pannolini"], "2026-05-27": ["Carta"], "2026-05-28": ["Organico"], "2026-05-29": ["Plastica e Metalli"], "2026-05-30": ["Organico + Pannolini"], "2026-06-01": ["Indifferenziato"], "2026-06-02": ["Organico + Pannolini"], "2026-06-03": ["Carta"], "2026-06-04": ["Organico + Vetro"], "2026-06-05": ["Plastica e Metalli"], "2026-06-06": ["Organico + Pannolini"], "2026-06-08": ["Indifferenziato"], "2026-06-09": ["Organico + Pannolini"], "2026-06-10": ["Carta"], "2026-06-11": ["Organico"], "2026-06-12": ["Plastica e Metalli"], "2026-06-13": ["Organico + Pannolini"], "2026-06-15": ["Indifferenziato"], "2026-06-16": ["Organico + Pannolini"], "2026-06-17": ["Carta"], "2026-06-18": ["Organico + Vetro"], "2026-06-19": ["Plastica e Metalli"], "2026-06-20": ["Organico + Pannolini"], "2026-06-22": ["Indifferenziato"], "2026-06-23": ["Organico + Pannolini"], "2026-06-24": ["Carta"], "2026-06-25": ["Organico"], "2026-06-26": ["Plastica e Metalli"], "2026-06-27": ["Organico + Pannolini"], "2026-06-29": ["Indifferenziato"], "2026-06-30": ["Organico + Pannolini"], "2026-07-01": ["Carta"], "2026-07-02": ["Organico + Vetro"], "2026-07-03": ["Plastica e Metalli"], "2026-07-04": ["Organico + Pannolini"], "2026-07-06": ["Indifferenziato"], "2026-07-07": ["Organico + Pannolini"], "2026-07-08": ["Carta"], "2026-07-09": ["Organico"], "2026-07-10": ["Plastica e Metalli"], "2026-07-11": ["Organico + Pannolini"], "2026-07-13": ["Indifferenziato"], "2026-07-14": ["Organico + Pannolini"], "2026-07-15": ["Carta"], "2026-07-16": ["Organico"], "2026-07-17": ["Plastica e Metalli"], "2026-07-18": ["Organico + Pannolini"], "2026-07-20": ["Indifferenziato"], "2026-07-21": ["Organico + Pannolini"], "2026-07-22": ["Carta"], "2026-07-23": ["Organico"], "2026-07-24": ["Plastica e Metalli"], "2026-07-25": ["Organico + Pannolini"], "2026-07-27": ["Indifferenziato"], "2026-07-28": ["Organico + Pannolini"], "2026-07-29": ["Carta"], "2026-07-30": ["Organico + Vetro"], "2026-07-31": ["Plastica e Metalli"], "2026-08-01": ["Organico + Pannolini"], "2026-08-03": ["Indifferenziato"], "2026-08-04": ["Organico + Pannolini"], "2026-08-05": ["Carta"], "2026-08-06": ["Organico"], "2026-08-07": ["Plastica e Metalli"], "2026-08-08": ["Organico + Pannolini"], "2026-08-10": ["Indifferenziato"], "2026-08-11": ["Organico + Pannolini"], "2026-08-12": ["Carta"], "2026-08-13": ["Organico + Vetro"], "2026-08-14": ["Plastica e Metalli"], "2026-08-15": ["Organico + Pannolini"], "2026-08-17": ["Indifferenziato"], "2026-08-18": ["Organico + Pannolini"], "2026-08-19": ["Carta"], "2026-08-20": ["Organico"], "2026-08-21": ["Plastica e Metalli"], "2026-08-22": ["Organico + Pannolini"], "2026-08-24": ["Indifferenziato"], "2026-08-25": ["Organico + Pannolini"], "2026-08-26": ["Carta"], "2026-08-27": ["Organico + Vetro"], "2026-08-28": ["Plastica e Metalli"], "2026-08-29": ["Organico + Pannolini"], "2026-08-31": ["Indifferenziato"], "2026-09-01": ["Organico + Pannolini"], "2026-09-02": ["Carta"], "2026-09-03": ["Organico"], "2026-09-04": ["Plastica e Metalli"], "2026-09-05": ["Organico + Pannolini"], "2026-09-07": ["Indifferenziato"], "2026-09-08": ["Organico + Pannolini"], "2026-09-09": ["Carta"], "2026-09-10": ["Organico + Vetro"], "2026-09-11": ["Plastica e Metalli"], "2026-09-12": ["Organico + Pannolini"], "2026-09-14": ["Indifferenziato"], "2026-09-15": ["Organico + Pannolini"], "2026-09-16": ["Carta"], "2026-09-17": ["Organico"], "2026-09-18": ["Plastica e Metalli"], "2026-09-19": ["Organico + Pannolini"], "2026-09-21": ["Indifferenziato"], "2026-09-22": ["Organico + Pannolini"], "2026-09-23": ["Carta"], "2026-09-24": ["Organico + Vetro"], "2026-09-25": ["Plastica e Metalli"], "2026-09-26": ["Organico + Pannolini"], "2026-09-28": ["Indifferenziato"], "2026-09-29": ["Organico + Pannolini"], "2026-09-30": ["Carta"], "2026-10-01": ["Organico"], "2026-10-02": ["Plastica e Metalli"], "2026-10-03": ["Organico + Pannolini"], "2026-10-05": ["Indifferenziato"], "2026-10-06": ["Organico + Pannolini"], "2026-10-07": ["Carta"], "2026-10-08": ["Organico + Vetro"], "2026-10-09": ["Plastica e Metalli"], "2026-10-10": ["Organico + Pannolini"], "2026-10-12": ["Indifferenziato"], "2026-10-13": ["Organico + Pannolini"], "2026-10-14": ["Carta"], "2026-10-15": ["Organico"], "2026-10-16": ["Plastica e Metalli"], "2026-10-17": ["Organico + Pannolini"], "2026-10-19": ["Indifferenziato"], "2026-10-20": ["Organico + Pannolini"], "2026-10-21": ["Carta"], "2026-10-22": ["Organico + Vetro"], "2026-10-23": ["Plastica e Metalli"], "2026-10-24": ["Organico + Pannolini"], "2026-10-26": ["Indifferenziato"], "2026-10-27": ["Organico + Pannolini"], "2026-10-28": ["Carta"], "2026-10-29": ["Organico"], "2026-10-30": ["Plastica e Metalli"], "2026-10-31": ["Organico + Pannolini"], "2026-11-02": ["Indifferenziato"], "2026-11-03": ["Organico + Pannolini"], "2026-11-04": ["Carta"], "2026-11-05": ["Organico + Vetro"], "2026-11-06": ["Plastica e Metalli"], "2026-11-07": ["Organico + Pannolini"], "2026-11-09": ["Indifferenziato"], "2026-11-10": ["Organico + Pannolini"], "2026-11-11": ["Carta"], "2026-11-12": ["Organico + Vetro"], "2026-11-13": ["Plastica e Metalli"], "2026-11-14": ["Organico + Pannolini"], "2026-11-16": ["Indifferenziato"], "2026-11-17": ["Organico + Pannolini"], "2026-11-18": ["Carta"], "2026-11-19": ["Organico"], "2026-11-20": ["Plastica e Metalli"], "2026-11-21": ["Organico + Pannolini"], "2026-11-23": ["Indifferenziato"], "2026-11-24": ["Organico + Pannolini"], "2026-11-25": ["Carta"], "2026-11-26": ["Organico + Vetro"], "2026-11-27": ["Plastica e Metalli"], "2026-11-28": ["Organico + Pannolini"], "2026-11-30": ["Indifferenziato"], "2026-12-01": ["Organico + Pannolini"], "2026-12-02": ["Carta"], "2026-12-03": ["Organico + Vetro"], "2026-12-04": ["Plastica e Metalli"], "2026-12-05": ["Organico + Pannolini"], "2026-12-07": ["Indifferenziato"], "2026-12-08": ["Organico + Pannolini"], "2026-12-09": ["Carta"], "2026-12-10": ["Organico"], "2026-12-11": ["Plastica e Metalli"], "2026-12-12": ["Organico + Pannolini"], "2026-12-14": ["Indifferenziato"], "2026-12-15": ["Organico + Pannolini"], "2026-12-16": ["Carta"], "2026-12-17": ["Organico + Vetro"], "2026-12-18": ["Plastica e Metalli"], "2026-12-19": ["Organico + Pannolini"], "2026-12-21": ["Indifferenziato"], "2026-12-22": ["Organico + Pannolini"], "2026-12-23": ["Carta"], "2026-12-24": ["Plastica e Metalli"], "2026-12-26": ["Organico + Pannolini"], "2026-12-28": ["Indifferenziato"], "2026-12-29": ["Organico + Pannolini"], "2026-12-30": ["Carta"], "2026-12-31": ["Organico + Vetro"]}'''


def _find_config_dir() -> Path:
    """Trova la directory config di HA dentro il container."""
    for base in ["/config", "/homeassistant", "/data"]:
        p = Path(base) / "homemind_patches"
        if p.exists():
            return p
    # Crea il path /config (standard HA addon) e crea anche il JSON builtin
    default = Path("/config/homemind_patches")
    default.mkdir(parents=True, exist_ok=True)
    # ── BUG FIX 1: crea spazzatura_calendario.json se non esiste ─────────────
    cal_file = default / "spazzatura_calendario.json"
    if not cal_file.exists():
        try:
            with open(cal_file, "w") as _f:
                _f.write(CALENDARIO_BUILTIN)
            logger.info("Creato spazzatura_calendario.json builtin in %s", default)
        except Exception as _e:
            logger.warning("Impossibile creare spazzatura_calendario.json: %s", _e)
    return default


_PATCHES_DIR = _find_config_dir()
PDF_PATH      = _PATCHES_DIR / "spazzatura.pdf"
CAL_PATH      = _PATCHES_DIR / "spazzatura_calendario.json"
CAL_DATA_PATH = Path("/data/spazzatura_calendario.json")  # salvato dalla web UI


# Emoji per tipo di rifiuto
EMOJI_MAP = {
    "plastica":   "♻️",
    "plastic":    "♻️",
    "metalli":    "🔩",
    "metallo":    "🔩",
    "organico":   "🌿",
    "umido":      "🌿",
    "carta":      "📄",
    "cartone":    "📦",
    "vetro":      "🍶",
    "indifferenziato": "🗑️",
    "secco":      "🗑️",
    "ingombranti":"🛋️",
    "raee":       "💻",
    "elettronici":"💻",
}


class SpazzaturaManager:
    def __init__(self, ai_provider, notifier, notify_hour: int = 20,
                 notify_enabled: bool = True):
        self.ai           = ai_provider
        self.notifier     = notifier
        self.notify_hour  = max(0, min(23, int(notify_hour)))
        # ── BUG FIX 3: opzione per abilitare/disabilitare notifiche ──────────
        self.notify_enabled = notify_enabled
        if self.notify_hour != int(notify_hour):
            logger.warning("notify_hour=%s non valido — uso %d", notify_hour, self.notify_hour)
        self.calendar: dict = {}   # {"2026-03-07": ["Plastica", "Carta"]}
        self._task    = None

    async def start(self):
        logger.info("Spazzatura: patches dir = %s (exists=%s)", _PATCHES_DIR, _PATCHES_DIR.exists())
        logger.info("Spazzatura: CAL_PATH = %s (exists=%s)", CAL_PATH, CAL_PATH.exists())
        logger.info("Spazzatura: PDF_PATH = %s (exists=%s)", PDF_PATH, PDF_PATH.exists())
        logger.info("Spazzatura: notifiche %s", "ABILITATE" if self.notify_enabled else "DISABILITATE")
        """Carica calendario esistente o analizza PDF."""
        if CAL_PATH.exists():
            try:
                with open(CAL_PATH) as f:
                    self.calendar = json.load(f)
                logger.info("Calendario spazzatura caricato: %d giorni", len(self.calendar))
            except Exception as e:
                logger.warning("Errore caricamento calendario: %s", e)

        if not self.calendar:
            if PDF_PATH.exists():
                logger.info("PDF trovato, estraggo calendario con AI...")
                await self.parse_pdf()

        if not self.calendar and CAL_DATA_PATH.exists():
            try:
                with open(CAL_DATA_PATH) as f:
                    self.calendar = json.load(f)
                logger.info("Calendario caricato da /data: %d date", len(self.calendar))
            except Exception as e:
                logger.warning("Errore /data JSON: %s", e)

        if not self.calendar:
            # Fallback: calendario builtin Lanciano 2026
            self.calendar = json.loads(CALENDARIO_BUILTIN)
            logger.info("Calendario builtin Lanciano 2026 caricato: %d date", len(self.calendar))

        if self.calendar:
            logger.info("Spazzatura: %d date in calendario | Notifica ogni sera alle %s:00",
                        len(self.calendar), str(self.notify_hour).zfill(2))
        else:
            logger.info("Spazzatura: nessun calendario — usa /spazzatura su Telegram per istruzioni")

        # Avvia il loop di notifica serale
        self._task = asyncio.create_task(self._notify_loop(), name="spazzatura")

    async def stop(self):
        if self._task:
            self._task.cancel()

    async def parse_pdf(self) -> bool:
        """Legge il PDF e chiede all'AI di estrarre il calendario come JSON."""
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber non installato — impossibile leggere PDF")
            return False

        try:
            text = ""
            with pdfplumber.open(str(PDF_PATH)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"

            if not text.strip():
                logger.error("PDF vuoto o non leggibile (potrebbe essere scansione immagine)")
                return False

            logger.info("PDF estratto: %d caratteri — invio all'AI...", len(text))
            text_trim = text[:6000]

            system = (
                "Sei un assistente che estrae calendari di raccolta rifiuti da testi PDF.\n"
                "Rispondi SOLO con JSON valido, nessun testo aggiuntivo, nessun markdown.\n"
                "Formato output:\n"
                '{"YYYY-MM-DD": ["Tipo1", "Tipo2"], "YYYY-MM-DD": ["Tipo3"]}\n'
                "Regole:\n"
                "- Usa date formato YYYY-MM-DD\n"
                "- Nomi rifiuti in italiano e capitalizzati (es: Plastica, Organico, Carta)\n"
                "- Se una data ha più tipi, mettili tutti nell'array\n"
                "- Includi tutte le date trovate nel documento\n"
                "- Se l'anno non è specificato usa " + str(now_local().year)
            )

            reply = await self.ai.ask(
                system,
                "Estrai il calendario completo di raccolta rifiuti da questo testo:\n\n" + text_trim,
                max_tokens=4000
            )

            clean = reply.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            clean = clean.strip()

            cal = json.loads(clean)
            if not isinstance(cal, dict):
                raise ValueError("Risposta AI non è un dizionario")

            self.calendar = cal
            CAL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CAL_PATH, "w") as f:
                json.dump(cal, f, indent=2, ensure_ascii=False)

            logger.info("Calendario salvato: %d date trovate", len(cal))
            return True

        except json.JSONDecodeError as e:
            logger.error("AI non ha restituito JSON valido: %s\nRisposta: %s", e, reply[:200])
            return False
        except Exception as e:
            logger.error("Errore parsing PDF: %s", e, exc_info=True)
            return False

    async def reload(self) -> str:
        """
        Ricarica il calendario. Priorità:
        1. spazzatura_calendario.json (già pronto)
        2. spazzatura.pdf (lo analizza l'AI)
        3. /data/spazzatura_calendario.json (salvato dalla web UI)
        4. Builtin Lanciano 2026
        """
        logger.info("Cerco calendario in: %s (esiste=%s)", CAL_PATH, CAL_PATH.exists())
        logger.info("Cerco in /data: %s (esiste=%s)", CAL_DATA_PATH, CAL_DATA_PATH.exists())
        logger.info("Cerco PDF in: %s (esiste=%s)", PDF_PATH, PDF_PATH.exists())
        try:
            parent = CAL_PATH.parent
            if parent.exists():
                logger.info("Contenuto %s: %s", parent, list(parent.iterdir()))
        except Exception as e:
            logger.warning("Errore listing dir: %s", e)

        if CAL_PATH.exists():
            try:
                with open(CAL_PATH) as f:
                    self.calendar = json.load(f)
                logger.info("Calendario ricaricato da JSON: %d date", len(self.calendar))
                return "Calendario caricato: " + str(len(self.calendar)) + " date trovate."
            except Exception as e:
                logger.warning("Errore lettura JSON: %s", e)
                return "Errore lettura JSON: " + str(e)

        if PDF_PATH.exists():
            self.calendar = {}
            ok = await self.parse_pdf()
            if ok:
                return "Calendario estratto dal PDF: " + str(len(self.calendar)) + " date trovate."
            return "Errore nel parsing del PDF. Controlla i log."

        if CAL_DATA_PATH.exists():
            try:
                with open(CAL_DATA_PATH) as f:
                    self.calendar = json.load(f)
                # ── Copia anche in CAL_PATH per la prossima volta ────────────
                CAL_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(CAL_PATH, "w") as f2:
                    json.dump(self.calendar, f2, indent=2, ensure_ascii=False)
                logger.info("Calendario caricato da /data e copiato in %s: %d date",
                            CAL_PATH, len(self.calendar))
                return "Calendario caricato: " + str(len(self.calendar)) + " date trovate."
            except Exception as e:
                logger.warning("Errore /data JSON: %s", e)

        # Fallback: calendario builtin Lanciano 2026
        self.calendar = json.loads(CALENDARIO_BUILTIN)
        logger.info("Reload: uso calendario builtin Lanciano 2026 (%d date)", len(self.calendar))
        return "Calendario Lanciano 2026 caricato: " + str(len(self.calendar)) + " date.\n(Sorgente: builtin)"

    async def reload_pdf(self) -> str:
        """Alias per compatibilità."""
        return await self.reload()

    def get_tomorrow(self) -> list:
        """Restituisce i rifiuti da buttare domani."""
        tomorrow = (now_local() + timedelta(days=1)).strftime("%Y-%m-%d")
        return self.calendar.get(tomorrow, [])

    def get_today(self) -> list:
        today = now_local().strftime("%Y-%m-%d")
        return self.calendar.get(today, [])

    def get_next_days(self, n=7) -> dict:
        """Prossimi N giorni con raccolta."""
        result = {}
        for i in range(1, n+1):
            day  = (now_local() + timedelta(days=i)).strftime("%Y-%m-%d")
            items= self.calendar.get(day, [])
            if items:
                result[day] = items
        return result

    def format_notification(self, items: list, day_label: str) -> tuple:
        """Formatta titolo e testo notifica."""
        if not items:
            return None, None

        lines = []
        for item in items:
            emoji = "🗑️"
            for key, em in EMOJI_MAP.items():
                if key in item.lower():
                    emoji = em
                    break
            lines.append(emoji + " " + item)

        title = "🗑️ Domani: " + ", ".join(items)
        body  = (
            "Domani (" + day_label + ") metti fuori:\n"
            + "\n".join(lines) + "\n\n"
            "Ricorda di preparare i sacchi stasera!"
        )
        return title, body

    def telegram_summary(self) -> str:
        """Riepilogo prossimi 7 giorni per Telegram."""
        upcoming = self.get_next_days(7)
        if not upcoming:
            if not self.calendar:
                if CAL_PATH.exists():
                    try:
                        with open(CAL_PATH) as f:
                            self.calendar = json.load(f)
                        upcoming = self.get_next_days(7)
                    except Exception:
                        pass
            if not upcoming:
                if not self.calendar:
                    return (
                        "Nessun calendario caricato.\n\n"
                        "Hai gia il file JSON? Copialo in:\n"
                        "<code>/config/homemind_patches/spazzatura_calendario.json</code>\n"
                        "poi scrivi /ricarica_spazzatura\n\n"
                        "Oppure metti il PDF in:\n"
                        "<code>/config/homemind_patches/spazzatura.pdf</code>"
                    )
                return "Nessuna raccolta nei prossimi 7 giorni."

        lines = ["🗓️ <b>Raccolta rifiuti prossimi 7 giorni:</b>\n"]
        for date_str, items in upcoming.items():
            d = datetime.strptime(date_str, "%Y-%m-%d")
            day_name = ["Lun","Mar","Mer","Gio","Ven","Sab","Dom"][d.weekday()]
            day_str  = day_name + " " + d.strftime("%d/%m")
            emojis   = []
            for item in items:
                for key, em in EMOJI_MAP.items():
                    if key in item.lower():
                        emojis.append(em)
                        break
                else:
                    emojis.append("🗑️")
            lines.append("📅 <b>" + day_str + ":</b> " + " ".join(emojis) + " " + ", ".join(items))

        tomorrow_items = self.get_tomorrow()
        if tomorrow_items:
            lines.insert(1, "⚠️ <b>DOMANI:</b> " + ", ".join(tomorrow_items) + "\n")

        # ── Info stato notifiche ─────────────────────────────────────────────
        lines.append("\n" + ("🔔 Notifiche serali attive alle " + str(self.notify_hour).zfill(2) + ":00"
                              if self.notify_enabled
                              else "🔕 Notifiche serali disabilitate"))

        return "\n".join(lines)

    # ── Loop notifica serale ────────────────────────────────────────────────────

    async def _notify_loop(self):
        """Ogni sera alle notify_hour controlla se domani c'è raccolta."""
        while True:
            try:
                now  = now_local()
                target = now.replace(hour=self.notify_hour, minute=0, second=0, microsecond=0)
                if now >= target:
                    target += timedelta(days=1)
                wait = (target - now).total_seconds()
                logger.info("Spazzatura: prossima notifica alle %02d:00 (tra %.0f min) — %s",
                            self.notify_hour, wait/60,
                            "ATTIVA" if self.notify_enabled else "DISABILITATA")
                await asyncio.sleep(wait)

                # ── BUG FIX 3: controlla se le notifiche sono abilitate ───────
                if not self.notify_enabled:
                    logger.debug("Spazzatura: notifiche disabilitate — skip")
                    continue

                items = self.get_tomorrow()
                if items:
                    tomorrow = (now_local() + timedelta(days=1))
                    day_name = ["Lunedì","Martedì","Mercoledì","Giovedì",
                                "Venerdì","Sabato","Domenica"][tomorrow.weekday()]
                    day_label = day_name + " " + tomorrow.strftime("%d/%m")
                    title, body = self.format_notification(items, day_label)
                    if self.notifier:
                        await self.notifier.send(title, body)
                        logger.info("Notifica spazzatura inviata: %s", items)
                else:
                    logger.debug("Nessuna raccolta domani — notifica non inviata")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Errore notify loop spazzatura: %s", e)
                await asyncio.sleep(3600)
