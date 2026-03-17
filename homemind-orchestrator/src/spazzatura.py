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

_BUILTIN_FILE = Path(__file__).parent.parent / "spazzatura_calendario_lanciano_2026.json"
CALENDARIO_BUILTIN = _BUILTIN_FILE.read_text(encoding="utf-8") if _BUILTIN_FILE.exists() else "{}"
logger = logging.getLogger("homemind.spazzatura")

def _find_config_dir() -> Path:
    """Trova la directory config di HA dentro il container."""
    # HA addon: /config è il path standard, ma prova anche /homeassistant
    for base in ["/config", "/homeassistant", "/data"]:
        p = Path(base) / "homemind_patches"
        if p.exists():
            return p
    # Crea il path /config (standard HA addon)
    default = Path("/config/homemind_patches")
    default.mkdir(parents=True, exist_ok=True)
    return default

_PATCHES_DIR = _find_config_dir()
PDF_PATH      = _PATCHES_DIR / "spazzatura.pdf"
CAL_PATH      = _PATCHES_DIR / "spazzatura_calendario.json"
CAL_DATA_PATH = Path("/data/spazzatura_calendario.json")  # salvato dalla web UI


# Orario notifica serale — letto da env (impostato dalle opzioni add-on)

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
    def __init__(self, ai_provider, notifier, notify_hour: int = 20):
        self.ai           = ai_provider
        self.notifier     = notifier
        self.notify_hour  = max(0, min(23, int(notify_hour)))  # clamp 0-23
        if self.notify_hour != int(notify_hour):
            logger.warning("notify_hour=%s non valido — uso %d", notify_hour, self.notify_hour)
        self.calendar: dict = {}   # {"2026-03-07": ["Plastica", "Carta"]}
        self._task    = None

    async def start(self):
        logger.info("Spazzatura: patches dir = %s (exists=%s)", _PATCHES_DIR, _PATCHES_DIR.exists())
        logger.info("Spazzatura: CAL_PATH = %s (exists=%s)", CAL_PATH, CAL_PATH.exists())
        logger.info("Spazzatura: PDF_PATH = %s (exists=%s)", PDF_PATH, PDF_PATH.exists())
        """Carica calendario esistente o analizza PDF."""
        if CAL_PATH.exists():
            try:
                with open(CAL_PATH) as f:
                    self.calendar = json.load(f)
                logger.info("Calendario spazzatura caricato: %d giorni", len(self.calendar))
            except Exception as e:
                logger.warning("Errore caricamento calendario: %s", e)

        if not self.calendar:
            # 1. Prova file esterno
            if CAL_PATH.exists():
                try:
                    with open(CAL_PATH) as f:
                        self.calendar = json.load(f)
                    logger.info("Calendario caricato da JSON esterno: %d date", len(self.calendar))
                except Exception as e:
                    logger.warning("Errore JSON esterno: %s", e)
            elif PDF_PATH.exists():
                logger.info("PDF trovato, estraggo calendario con AI...")
                await self.parse_pdf()

        if not self.calendar and CAL_DATA_PATH.exists():
            # 2. Prova /data/ (salvato dalla web UI)
            try:
                with open(CAL_DATA_PATH) as f:
                    self.calendar = json.load(f)
                logger.info("Calendario caricato da /data: %d date", len(self.calendar))
            except Exception as e:
                logger.warning("Errore /data JSON: %s", e)

        if not self.calendar:
            # 3. Fallback: calendario builtin Lanciano 2026
            self.calendar = json.loads(CALENDARIO_BUILTIN)
            logger.info("Calendario builtin Lanciano 2026 caricato: %d date", len(self.calendar))

        if not PDF_PATH.exists() and not self.calendar:
            logger.info("Nessun PDF spazzatura trovato in %s — puoi creare manualmente %s", PDF_PATH, CAL_PATH)

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

            # Limita a 6000 char per non sforare il contesto
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

            # Pulisci e parsa JSON
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
        """
        # Log path effettivi per debug
        logger.info("Cerco calendario in: %s (esiste=%s)", CAL_PATH, CAL_PATH.exists())
        logger.info("Cerco in /data: %s (esiste=%s)", CAL_DATA_PATH, CAL_DATA_PATH.exists())
        logger.info("Cerco PDF in: %s (esiste=%s)", PDF_PATH, PDF_PATH.exists())
        try:
            parent = CAL_PATH.parent
            if parent.exists():
                logger.info("Contenuto %s: %s", parent, list(parent.iterdir()))
            else:
                logger.warning("Directory %s non esiste!", parent)
        except Exception as e:
            logger.warning("Errore listing dir: %s", e)

        # Prima prova il JSON già pronto
        if CAL_PATH.exists():
            try:
                with open(CAL_PATH) as f:
                    self.calendar = json.load(f)
                logger.info("Calendario ricaricato da JSON: %d date", len(self.calendar))
                return "Calendario caricato: " + str(len(self.calendar)) + " date trovate."
            except Exception as e:
                logger.warning("Errore lettura JSON: %s", e)
                return "Errore lettura JSON: " + str(e)

        # Poi prova PDF
        if PDF_PATH.exists():
            self.calendar = {}
            ok = await self.parse_pdf()
            if ok:
                return "Calendario estratto dal PDF: " + str(len(self.calendar)) + " date trovate."
            return "Errore nel parsing del PDF. Controlla i log."

        # Prova /data/ (salvato dalla web UI)
        if CAL_DATA_PATH.exists():
            try:
                with open(CAL_DATA_PATH) as f:
                    self.calendar = json.load(f)
                logger.info("Calendario caricato da /data: %d date", len(self.calendar))
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
                # Ultima chance: rileggi dal disco
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

        # Domani in evidenza
        tomorrow_items = self.get_tomorrow()
        if tomorrow_items:
            lines.insert(1, "⚠️ <b>DOMANI:</b> " + ", ".join(tomorrow_items) + "\n")

        return "\n".join(lines)

    # ── Loop notifica serale ────────────────────────────────────────────────────

    async def _notify_loop(self):
        """Ogni sera alle 20:00 controlla se domani c'è raccolta."""
        while True:
            try:
                now  = now_local()
                # Calcola secondi fino alle 20:00 di oggi (o domani se già passate)
                target = now.replace(hour=self.notify_hour, minute=0, second=0, microsecond=0)
                if now >= target:
                    target += timedelta(days=1)
                wait = (target - now).total_seconds()
                logger.info("Spazzatura: prossima notifica alle %02d:00 (tra %.0f min)",
                            self.notify_hour, wait/60)
                await asyncio.sleep(wait)

                # È le 20:00 — controlla domani
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
