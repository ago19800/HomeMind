"""
agent/email_manager.py — Gestore Email per HomeMind Orchestrator.

Funzionalità:
  - Connessione Gmail via IMAP (SSL) + SMTP (TLS)
  - Account multipli configurabili dalla web UI
  - Lettura email con sommario AI
  - Cancellazione / spostamento spam nel Trash
  - Reply wizard guidato con AI
  - Auto-risposta con regole configurabili
  - Invio programmato (integrato con TaskScheduler)

Configurazione (in person_config.json):
  "email_accounts": [
    {
      "label": "Casa",
      "address": "agostino@gmail.com",
      "app_password": "xxxx xxxx xxxx xxxx",
      "imap_host": "imap.gmail.com",
      "imap_port": 993,
      "smtp_host": "smtp.gmail.com",
      "smtp_port": 587,
      "enabled": true
    }
  ],
  "email_auto_reply_rules": [],
  "email_check_interval_min": 30
"""

import asyncio
import email as _email
import imaplib
import json
import logging
import smtplib
import ssl
import time
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger("homemind.email")

CONFIG_PATH = Path("/config/homemind_patches/person_config.json")
SCHEDULED_PATH = Path("/data/homemind_email_scheduled.json")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _decode_str(val) -> str:
    """Decodifica intestazioni email (possono essere encoded-words RFC 2047)."""
    if val is None:
        return ""
    try:
        return str(make_header(decode_header(val)))
    except Exception:
        return str(val)


def _load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except Exception as e:
        logger.warning("email_manager: errore lettura config: %s", e)
    return {}


def _save_config(cfg: dict):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error("email_manager: errore scrittura config: %s", e)


def _load_accounts() -> list:
    return _load_config().get("email_accounts", [])


def _load_scheduled() -> list:
    try:
        if SCHEDULED_PATH.exists():
            return json.loads(SCHEDULED_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_scheduled(items: list):
    SCHEDULED_PATH.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── IMAP helper ─────────────────────────────────────────────────────────────

class IMAPSession:
    """Context manager per sessione IMAP con SSL."""

    def __init__(self, account: dict):
        self.account = account
        self.conn: Optional[imaplib.IMAP4_SSL] = None

    def __enter__(self):
        acc = self.account
        ctx = ssl.create_default_context()
        self.conn = imaplib.IMAP4_SSL(
            host=acc.get("imap_host", "imap.gmail.com"),
            port=int(acc.get("imap_port", 993)),
            ssl_context=ctx,
        )
        self.conn.login(acc["address"], acc["app_password"])
        return self.conn

    def __exit__(self, *args):
        try:
            if self.conn:
                self.conn.logout()
        except Exception:
            pass


# ─── Core operations ─────────────────────────────────────────────────────────

def fetch_emails(account: dict, folder: str = "INBOX",
                 max_count: int = 20, only_unseen: bool = False) -> list[dict]:
    """
    Recupera le ultime `max_count` email dalla cartella.
    Ritorna lista di dict con: uid, subject, sender, date, snippet, seen, body_text.
    """
    results = []
    try:
        with IMAPSession(account) as conn:
            status, _ = conn.select(f'"{folder}"', readonly=True)
            if status != "OK":
                logger.warning("fetch_emails: impossibile selezionare cartella %s", folder)
                return []

            search_criteria = "(UNSEEN)" if only_unseen else "ALL"
            status, data = conn.uid("SEARCH", None, search_criteria)
            if status != "OK" or not data or not data[0]:
                return []

            uids = data[0].split()
            # Prendi gli ultimi max_count
            uids = uids[-max_count:]

            for uid in reversed(uids):  # Più recenti prima
                try:
                    status, msg_data = conn.uid("FETCH", uid, "(RFC822 FLAGS)")
                    if status != "OK" or not msg_data or not msg_data[0]:
                        continue
                    raw = msg_data[0][1]
                    flags_raw = msg_data[0][0].decode() if isinstance(msg_data[0][0], bytes) else str(msg_data[0][0])
                    seen = "\\Seen" in flags_raw

                    msg = _email.message_from_bytes(raw)
                    subject = _decode_str(msg.get("Subject", "(nessun oggetto)"))
                    sender  = _decode_str(msg.get("From", ""))
                    date_raw = msg.get("Date", "")
                    msg_id  = msg.get("Message-ID", "")

                    # Estrai body testuale
                    body_text = _extract_body(msg)
                    snippet = body_text[:200].replace("\n", " ").strip() + ("…" if len(body_text) > 200 else "")

                    results.append({
                        "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                        "msg_id": msg_id,
                        "subject": subject,
                        "sender": sender,
                        "date": date_raw,
                        "snippet": snippet,
                        "seen": seen,
                        "body_text": body_text,
                        "account_address": account["address"],
                        "folder": folder,
                    })
                except Exception as e:
                    logger.debug("fetch_emails: errore uid %s: %s", uid, e)
                    continue

    except Exception as e:
        logger.error("fetch_emails: errore connessione [%s]: %s", account.get("address"), e)
        raise

    return results


def _extract_body(msg) -> str:
    """Estrae testo plain da un messaggio email (gestisce multipart)."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    return part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    pass
        # Fallback: cerca text/html
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    charset = part.get_content_charset() or "utf-8"
                    html = part.get_payload(decode=True).decode(charset, errors="replace")
                    import re
                    return re.sub(r"<[^>]+>", " ", html)
                except Exception:
                    pass
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            return msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            pass
    return ""


def delete_email(account: dict, uid: str, folder: str = "INBOX", permanent: bool = False) -> bool:
    """
    Sposta l'email nel Trash (Gmail) o cancella definitivamente.
    `permanent=True` → expunge immediato (usa con cautela).
    """
    try:
        with IMAPSession(account) as conn:
            conn.select(f'"{folder}"')
            if permanent:
                conn.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                conn.expunge()
            else:
                # Gmail: sposta in [Gmail]/Trash via COPY + DELETE
                conn.uid("COPY", uid, '"[Gmail]/Trash"')
                conn.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                conn.expunge()
        logger.info("delete_email: uid %s eliminata (permanent=%s)", uid, permanent)
        return True
    except Exception as e:
        logger.error("delete_email: errore uid %s: %s", uid, e)
        return False


def mark_as_read(account: dict, uid: str, folder: str = "INBOX") -> bool:
    """Segna l'email come letta."""
    try:
        with IMAPSession(account) as conn:
            conn.select(f'"{folder}"')
            conn.uid("STORE", uid, "+FLAGS", "(\\Seen)")
        return True
    except Exception as e:
        logger.error("mark_as_read: %s", e)
        return False


def send_email(account: dict, to: str, subject: str, body: str,
               reply_to_msg_id: str = "") -> bool:
    """
    Invia una email via SMTP TLS.
    Se `reply_to_msg_id` è valorizzato, aggiunge In-Reply-To per thread corretto.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = account["address"]
        msg["To"]      = to
        msg["Subject"] = subject
        if reply_to_msg_id:
            msg["In-Reply-To"] = reply_to_msg_id
            msg["References"]  = reply_to_msg_id

        msg.attach(MIMEText(body, "plain", "utf-8"))

        ctx = ssl.create_default_context()
        with smtplib.SMTP(
            host=account.get("smtp_host", "smtp.gmail.com"),
            port=int(account.get("smtp_port", 587)),
        ) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(account["address"], account["app_password"])
            server.sendmail(account["address"], [to], msg.as_bytes())

        logger.info("send_email: inviata a %s [oggetto: %s]", to, subject)
        return True
    except Exception as e:
        logger.error("send_email: errore invio a %s: %s", to, e)
        return False


# ─── AI helpers ──────────────────────────────────────────────────────────────

async def ai_summarize_email(email_dict: dict, ai_cb) -> str:
    """Genera un sommario AI dell'email in italiano."""
    prompt = (
        f"Riassumi questa email in modo conciso (max 3 frasi) in italiano.\n\n"
        f"Da: {email_dict['sender']}\n"
        f"Oggetto: {email_dict['subject']}\n"
        f"Testo:\n{email_dict['body_text'][:3000]}"
    )
    try:
        resp = await ai_cb(prompt)
        return resp.strip()
    except Exception as e:
        logger.error("ai_summarize_email: %s", e)
        return "Impossibile generare sommario."


async def ai_generate_reply(email_dict: dict, user_instructions: str, ai_cb,
                             style: str = "professionale") -> str:
    """
    Genera una bozza di risposta AI all'email.
    `style`: professionale | amichevole | formale | breve
    `user_instructions`: es. "Dì che non posso partecipare ma proponi un'alternativa"
    """
    prompt = (
        f"Scrivi una risposta email in italiano, stile {style}.\n"
        f"Istruzioni specifiche: {user_instructions}\n\n"
        f"Email originale:\n"
        f"Da: {email_dict['sender']}\n"
        f"Oggetto: {email_dict['subject']}\n"
        f"Testo:\n{email_dict['body_text'][:2000]}\n\n"
        f"Scrivi SOLO il corpo della risposta, senza intestazioni email."
    )
    try:
        resp = await ai_cb(prompt)
        return resp.strip()
    except Exception as e:
        logger.error("ai_generate_reply: %s", e)
        return ""


async def ai_batch_classify(emails: list[dict], ai_cb) -> list[dict]:
    """
    Classifica una lista di email come spam/importante/normale.
    Ritorna la stessa lista con campo aggiunto `ai_label`.
    """
    if not emails:
        return emails

    summaries = "\n".join([
        f"{i+1}. Da: {e['sender']} | Oggetto: {e['subject']} | Preview: {e['snippet'][:100]}"
        for i, e in enumerate(emails)
    ])
    prompt = (
        f"Classifica queste {len(emails)} email come: spam, importante, o normale.\n"
        f"Rispondi SOLO con un JSON array, es: [\"spam\",\"importante\",\"normale\",...]\n\n"
        f"{summaries}"
    )
    try:
        resp = await ai_cb(prompt)
        import re
        m = re.search(r"\[.*?\]", resp, re.DOTALL)
        if m:
            labels = json.loads(m.group(0))
            for i, e in enumerate(emails):
                e["ai_label"] = labels[i] if i < len(labels) else "normale"
    except Exception as e:
        logger.error("ai_batch_classify: %s", e)
        for e_ in emails:
            e_["ai_label"] = "normale"
    return emails


# ─── Scheduled email queue ────────────────────────────────────────────────────

def schedule_email(account_address: str, to: str, subject: str, body: str,
                   send_at_iso: str, note: str = "") -> dict:
    """
    Aggiunge una email alla coda di invio programmato.
    `send_at_iso`: datetime ISO 8601, es. "2026-05-13T09:00:00"
    """
    items = _load_scheduled()
    task_id = f"email_{int(time.time())}_{len(items)}"
    task = {
        "id": task_id,
        "account": account_address,
        "to": to,
        "subject": subject,
        "body": body,
        "send_at": send_at_iso,
        "note": note,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    items.append(task)
    _save_scheduled(items)
    logger.info("schedule_email: programmata email a %s per %s", to, send_at_iso)
    return task


def cancel_scheduled_email(task_id: str) -> bool:
    items = _load_scheduled()
    for item in items:
        if item["id"] == task_id:
            item["status"] = "cancelled"
            _save_scheduled(items)
            return True
    return False


def get_pending_scheduled() -> list[dict]:
    return [i for i in _load_scheduled() if i.get("status") == "pending"]


async def process_scheduled_emails():
    """
    Da chiamare periodicamente (es. ogni minuto) per inviare le email programmate.
    """
    now = datetime.now()
    items = _load_scheduled()
    changed = False

    for item in items:
        if item.get("status") != "pending":
            continue
        try:
            send_at = datetime.fromisoformat(item["send_at"])
        except Exception:
            continue

        if now >= send_at:
            accounts = _load_accounts()
            acc = next((a for a in accounts if a["address"] == item["account"]), None)
            if acc and acc.get("enabled", True):
                ok = send_email(acc, item["to"], item["subject"], item["body"])
                item["status"] = "sent" if ok else "error"
                item["processed_at"] = now.isoformat()
                changed = True
                logger.info("process_scheduled_emails: task %s → %s", item["id"], item["status"])
            else:
                logger.warning("process_scheduled_emails: account %s non trovato o disabilitato", item.get("account"))

    if changed:
        _save_scheduled(items)


# ─── Auto-reply engine ────────────────────────────────────────────────────────

# Prefissi mittente a cui NON rispondere mai (bounce, marketing, no-reply, ecc.)
NEVER_REPLY_PREFIXES = (
    "mailer-daemon", "postmaster", "no-reply", "noreply", "no_reply",
    "donotreply", "do-not-reply", "bounce", "bounces", "newsletter",
    "notification", "notify", "automatedreply", "autoresponder",
    "unsubscribe", "listserv", "majordomo",
)


def _is_safe_to_reply(reply_to: str) -> bool:
    """Ritorna True solo se il mittente è una persona reale (non robot/marketing)."""
    local = reply_to.split("@")[0].lower()
    # Blocca prefissi tipici di sistemi automatici
    if any(local.startswith(p) or local == p for p in NEVER_REPLY_PREFIXES):
        return False
    # Blocca se l'indirizzo contiene "noreply" o "no-reply" ovunque
    if "noreply" in local or "no-reply" in local or "donotreply" in local:
        return False
    return True


async def check_auto_reply(emails: list[dict], ai_cb) -> list[dict]:
    """
    Controlla le regole di auto-risposta configurate e invia risposte automatiche.

    Opzioni regola:
      match_in: "oggetto" | "corpo" | "entrambi" (default: "oggetto")
      whole_word: true | false (default: true — cerca parola intera)
    """
    import asyncio as _aio
    import re as _re
    cfg = _load_config()
    rules = cfg.get("email_auto_reply_rules", [])
    accounts = cfg.get("email_accounts", [])
    sent = []

    if not rules:
        logger.debug("check_auto_reply: nessuna regola configurata")
        return sent

    for rule in rules:
        if not rule.get("enabled", True):
            continue
        keyword      = rule.get("keyword", "").lower().strip()
        style        = rule.get("style", "professionale")
        instruction  = rule.get("instruction", "Rispondi in modo cortese.")
        account_addr = rule.get("account", "")
        match_in     = rule.get("match_in", "oggetto")    # oggetto | corpo | entrambi
        whole_word   = rule.get("whole_word", True)        # True = parola intera

        acc = next((a for a in accounts
                    if a["address"] == account_addr and a.get("enabled", True)), None)
        if not acc:
            logger.warning("check_auto_reply: account '%s' non trovato o disabilitato", account_addr)
            continue

        for em in emails:
            if em.get("_auto_replied"):
                continue

            # Estrai mittente prima di tutto (per blocco no-reply)
            m_addr = _re.search(r"<([^>]+)>", em.get("sender", ""))
            reply_to = m_addr.group(1) if m_addr else em.get("sender", "")

            if not reply_to or "@" not in reply_to:
                logger.debug("check_auto_reply: skip '%s' — mittente non valido",
                             em.get("subject","")[:40])
                continue

            # Blocco automatico per indirizzi no-reply/sistema
            if not _is_safe_to_reply(reply_to):
                logger.info("check_auto_reply: 🚫 skip '%s' — mittente no-reply/sistema: %s",
                            em.get("subject","")[:40], reply_to)
                em["_auto_replied"] = True  # evita re-check
                continue

            # Keyword obbligatoria
            if not keyword:
                logger.warning("check_auto_reply: regola senza keyword ignorata")
                continue

            subject_text = (em.get("subject") or "").lower()
            body_text    = (em.get("body_text") or em.get("snippet") or "").lower()

            # Costruisci testo di ricerca in base a match_in
            if match_in == "oggetto":
                search_text = subject_text
            elif match_in == "corpo":
                search_text = body_text
            else:  # entrambi
                search_text = subject_text + " " + body_text

            # Ricerca: parola intera o sottostringa
            if whole_word:
                pattern = r"(?<![a-zA-ZÀ-ÿ0-9_])" + _re.escape(keyword) + r"(?![a-zA-ZÀ-ÿ0-9_])"
                found = bool(_re.search(pattern, search_text))
            else:
                found = keyword in search_text

            if not found:
                logger.debug("check_auto_reply: skip '%s' — keyword '%s' non trovata in [%s]",
                             em.get("subject","")[:40], keyword, match_in)
                continue

            # Log dettagliato
            found_in = []
            if whole_word:
                if _re.search(r"(?<![a-zA-ZÀ-ÿ0-9_])" + _re.escape(keyword) + r"(?![a-zA-ZÀ-ÿ0-9_])", subject_text):
                    found_in.append("oggetto")
                if _re.search(r"(?<![a-zA-ZÀ-ÿ0-9_])" + _re.escape(keyword) + r"(?![a-zA-ZÀ-ÿ0-9_])", body_text):
                    found_in.append("corpo")
            else:
                if keyword in subject_text: found_in.append("oggetto")
                if keyword in body_text:    found_in.append("corpo")
            logger.info("check_auto_reply: ✅ keyword '%s' trovata in [%s] — email: '%s' da %s",
                        keyword, ", ".join(found_in), em.get("subject","")[:45], reply_to)

            if not reply_to or "@" not in reply_to:
                logger.warning("check_auto_reply: mittente non valido: %s", em.get("sender",""))
                continue

            try:
                reply_body = await ai_generate_reply(em, instruction, ai_cb, style=style)
            except Exception as e:
                logger.error("check_auto_reply: errore AI: %s", e)
                continue

            if not reply_body:
                logger.warning("check_auto_reply: AI ha restituito risposta vuota")
                continue

            logger.info("check_auto_reply: invio risposta a %s", reply_to)
            try:
                ok = await _aio.to_thread(
                    send_email, acc,
                    reply_to,
                    "Re: " + (em.get("subject") or ""),
                    reply_body,
                    em.get("msg_id", ""),
                )
                if ok:
                    em["_auto_replied"] = True
                    sent.append({
                        "email_uid":  em["uid"],
                        "to":         reply_to,
                        "reply_sent": reply_body[:120],
                    })
                    logger.info("check_auto_reply: ✅ risposta inviata a %s", reply_to)
                else:
                    logger.error("check_auto_reply: invio fallito a %s", reply_to)
            except Exception as e:
                logger.error("check_auto_reply: errore invio a %s: %s", reply_to, e)

    return sent

class EmailChecker:
    """
    Controlla email in tempo reale via IMAP IDLE + ciclo periodico di backup.
    IMAP IDLE: Gmail notifica immediatamente quando arriva una email nuova.
    Ciclo periodico: backup ogni N minuti in caso IDLE si disconnette.
    """

    def __init__(self, ai_cb=None, notify_cb=None):
        self.ai_cb = ai_cb
        self.notify_cb = notify_cb
        self._task: Optional[asyncio.Task] = None
        self._idle_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self):
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        self._idle_task = asyncio.create_task(self._idle_loop())
        logger.info("EmailChecker: avviato (IDLE + ciclo periodico)")

    def stop(self):
        self._running = False
        for t in [self._task, self._idle_task]:
            if t:
                t.cancel()

    async def _idle_loop(self):
        """
        IMAP IDLE: connessione persistente a Gmail.
        Quando arriva una email nuova, Gmail lo segnala subito
        e HomeMind fa il check immediato — risposta in ~5 secondi.
        """
        import asyncio as _aio
        while self._running:
            try:
                accounts = _load_config().get("email_accounts", [])
                enabled = [a for a in accounts if a.get("enabled", True)]
                if not enabled:
                    await _aio.sleep(60)
                    continue
                acc = enabled[0]  # IDLE sul primo account
                logger.debug("EmailChecker IDLE: avvio su %s", acc.get("address","?"))
                # IMAP IDLE in thread separato (bloccante)
                new_mail = await _aio.to_thread(self._imap_idle_wait, acc)
                if new_mail and self._running:
                    logger.info("EmailChecker IDLE: nuova email rilevata — check immediato")
                    await self._run_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("EmailChecker IDLE: errore (%s) — retry tra 30s", e)
                await _aio.sleep(30)

    def _imap_idle_wait(self, account: dict, timeout_sec: int = 1740) -> bool:
        """
        Blocca il thread finché Gmail segnala nuove email (IDLE) o timeout.
        Ritorna True se ci sono nuove email, False se timeout (normale, circa 29 min).
        timeout_sec=1740 = 29 minuti (Gmail chiude IDLE dopo 30 min).
        """
        import socket
        try:
            ctx = ssl.create_default_context()
            conn = imaplib.IMAP4_SSL(
                host=account.get("imap_host", "imap.gmail.com"),
                port=int(account.get("imap_port", 993)),
                ssl_context=ctx,
            )
            conn.login(account["address"], account["app_password"])
            conn.select("INBOX")
            # Invia comando IDLE
            tag = conn._new_tag().decode()
            conn.send((tag + " IDLE\r\n").encode())
            # Leggi "+" (server ready)
            conn.readline()
            # Aspetta risposta con timeout
            conn.socket().settimeout(timeout_sec)
            response = b""
            try:
                while True:
                    chunk = conn.socket().recv(4096)
                    if not chunk:
                        break
                    response += chunk
                    # EXISTS = nuove email, EXPUNGE = email eliminate
                    if b"EXISTS" in response or b"RECENT" in response:
                        conn.send(b"DONE\r\n")
                        conn.logout()
                        return True
            except socket.timeout:
                pass  # Timeout normale
            try:
                conn.send(b"DONE\r\n")
                conn.logout()
            except Exception:
                pass
            return False
        except Exception as e:
            logger.debug("_imap_idle_wait error: %s", e)
            return False

    async def _loop(self):
        first_run = True
        while self._running:
            try:
                await self._run_check()
            except Exception as e:
                logger.error("EmailChecker loop: %s", e)
            cfg = _load_config()
            interval_min = int(cfg.get("email_check_interval_min", 30))
            if first_run:
                first_run = False
                logger.info("EmailChecker: primo ciclo completato — prossimo tra %d min", interval_min)
            await asyncio.sleep(interval_min * 60)

    async def _run_check(self):
        """Esegue un singolo ciclo di controllo email. Chiamabile anche manualmente."""
        cfg = _load_config()
        await process_scheduled_emails()
        if not self.ai_cb:
            logger.warning("EmailChecker: ai_cb non disponibile — auto-reply disabilitato")
            return
        rules = cfg.get("email_auto_reply_rules", [])
        has_active_rules = any(
            r.get("enabled", True) and r.get("keyword", "").strip()
            for r in rules
        )
        logger.info("EmailChecker: %d regole totali, ha_active_rules=%s, regole con keyword: %s",
                    len(rules),
                    has_active_rules,
                    [r.get("keyword","") for r in rules if r.get("enabled",True) and r.get("keyword","").strip()])
        accounts = [a for a in cfg.get("email_accounts", []) if a.get("enabled", True)]
        for acc in accounts:
            try:
                new_emails = await asyncio.to_thread(fetch_emails, acc, "INBOX", 20, True)
                if not new_emails:
                    continue
                logger.info("EmailChecker [%s]: %d email non lette trovate",
                            acc.get("address", "?"), len(new_emails))
                # Notifica nuove email solo se abilitata esplicitamente nel config
                if self.notify_cb and cfg.get("email_notify_new", False):
                    summary = f"📧 <b>{len(new_emails)} email nuove</b> su {acc['address']}\n"
                    for em in new_emails[:3]:
                        summary += f"• <i>{em['sender'][:40]}</i> — {em['subject'][:50]}\n"
                    if len(new_emails) > 3:
                        summary += f"• …e altre {len(new_emails)-3}\n"
                    await self.notify_cb(summary)
                if has_active_rules:
                    sent = await check_auto_reply(new_emails, self.ai_cb)
                    if sent:
                        logger.info("EmailChecker: auto-risposta inviata a %d email", len(sent))
                        if self.notify_cb:
                            for s in sent:
                                await self.notify_cb(
                                    f"🤖 <b>Auto-risposta inviata</b>\n"
                                    f"📬 A: {s['to']}\n"
                                    f"📝 {s['reply_sent'][:80]}…"
                                )
                else:
                    logger.info("EmailChecker: nessuna regola attiva con keyword — "
                                "email marcate lette senza auto-risposta")
                for em in new_emails:
                    await asyncio.to_thread(mark_as_read, acc, em["uid"])
            except Exception as e:
                logger.error("EmailChecker: errore account %s: %s", acc.get("address"), e)

def search_emails(account: dict, query: str, folder: str = "INBOX",
                  max_count: int = 20) -> list[dict]:
    """
    Cerca email per mittente, oggetto o testo.
    Usa IMAP SEARCH con OR su FROM, SUBJECT, BODY.
    """
    results = []
    try:
        with IMAPSession(account) as conn:
            conn.select(f'"{folder}"', readonly=True)
            # Prova ricerca server-side (FROM + SUBJECT)
            q = query.replace('"', '').strip()
            criteria = f'(OR FROM "{q}" SUBJECT "{q}")'
            status, data = conn.uid("SEARCH", None, criteria)
            if status != "OK" or not data or not data[0]:
                return []
            uids = data[0].split()[-max_count:]
            for uid in reversed(uids):
                try:
                    status2, msg_data = conn.uid("FETCH", uid, "(RFC822 FLAGS)")
                    if status2 != "OK" or not msg_data or not msg_data[0]:
                        continue
                    raw = msg_data[0][1]
                    flags_raw = str(msg_data[0][0])
                    seen = "\\Seen" in flags_raw
                    msg = _email.message_from_bytes(raw)
                    subject = _decode_str(msg.get("Subject", ""))
                    sender  = _decode_str(msg.get("From", ""))
                    date_raw = msg.get("Date", "")
                    body_text = _extract_body(msg)
                    snippet = body_text[:200].replace("\n", " ").strip()
                    results.append({
                        "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                        "msg_id": msg.get("Message-ID", ""),
                        "subject": subject, "sender": sender,
                        "date": date_raw, "snippet": snippet,
                        "seen": seen, "body_text": body_text,
                        "account_address": account["address"], "folder": folder,
                    })
                except Exception:
                    continue
    except Exception as e:
        logger.error("search_emails: %s", e)
        raise
    return results


def delete_emails_bulk(account: dict, uids: list[str],
                       folder: str = "INBOX") -> dict:
    """
    Cancella una lista di email (sposta in Trash).
    Ritorna {"deleted": N, "errors": N}
    """
    deleted, errors = 0, 0
    try:
        with IMAPSession(account) as conn:
            conn.select(f'"{folder}"')
            for uid in uids:
                try:
                    conn.uid("COPY", uid, '"[Gmail]/Trash"')
                    conn.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                    deleted += 1
                except Exception:
                    errors += 1
            conn.expunge()
    except Exception as e:
        logger.error("delete_emails_bulk: %s", e)
    return {"deleted": deleted, "errors": errors}


def empty_folder(account: dict, folder: str) -> dict:
    """
    Svuota completamente una cartella (Spam o Trash).
    Sicuro solo per cartelle di sistema.
    """
    SAFE_FOLDERS = {
        "[Gmail]/Trash", "[Gmail]/Spam",
        "[Gmail]/Bin",   "Spam", "Trash", "Junk",
    }
    if folder not in SAFE_FOLDERS:
        return {"error": f"Cartella '{folder}' non consentita per svuotamento massivo"}
    deleted = 0
    try:
        with IMAPSession(account) as conn:
            status, _ = conn.select(f'"{folder}"')
            if status != "OK":
                return {"error": f"Cartella non trovata: {folder}"}
            status2, data = conn.uid("SEARCH", None, "ALL")
            if status2 != "OK" or not data or not data[0]:
                return {"deleted": 0}
            uids = data[0].split()
            if uids:
                uid_list = b",".join(uids)
                conn.uid("STORE", uid_list, "+FLAGS", "(\\Deleted)")
                conn.expunge()
                deleted = len(uids)
    except Exception as e:
        logger.error("empty_folder [%s]: %s", folder, e)
        return {"error": str(e)}
    return {"deleted": deleted}


async def ai_detect_spam(emails: list[dict], ai_cb) -> list[dict]:
    """
    Analisi AI avanzata: identifica spam, newsletter, promozioni da eliminare.
    Aggiunge campo 'spam_score': 0-10 e 'spam_reason'.
    """
    if not emails:
        return emails
    summaries = "\n".join([
        f"{i+1}. Da:{e['sender'][:50]} | Oggetto:{e['subject'][:60]} | Preview:{e['snippet'][:80]}"
        for i, e in enumerate(emails)
    ])
    prompt = (
        f"Analizza queste {len(emails)} email e assegna uno spam_score 0-10 "
        f"(10=sicuro spam/promozione, 0=email importante personale).\n"
        f"Rispondi SOLO con JSON array: "
        f'[{{"idx":1,"score":8,"reason":"Newsletter promozionale"}}, ...]\n\n'
        f"{summaries}"
    )
    try:
        resp = await ai_cb(prompt)
        import re
        m = re.search(r"\[.*?\]", resp, re.DOTALL)
        if m:
            items = json.loads(m.group(0))
            for item in items:
                idx = item.get("idx", 0) - 1
                if 0 <= idx < len(emails):
                    emails[idx]["spam_score"] = item.get("score", 0)
                    emails[idx]["spam_reason"] = item.get("reason", "")
    except Exception as e:
        logger.error("ai_detect_spam: %s", e)
    return emails


# ─── Invio email con allegati ─────────────────────────────────────────────────

def send_email_with_attachments(account: dict, to: str, subject: str, body: str,
                                 attachments: list[dict],
                                 reply_to_msg_id: str = "") -> bool:
    """
    Invia email con allegati opzionali.
    attachments: [{"filename": str, "data": bytes, "mimetype": str}, ...]
    """
    from email.mime.base import MIMEBase
    from email import encoders as _encoders

    try:
        msg = MIMEMultipart("mixed")
        msg["From"]    = account["address"]
        msg["To"]      = to
        msg["Subject"] = subject
        if reply_to_msg_id:
            msg["In-Reply-To"] = reply_to_msg_id
            msg["References"]  = reply_to_msg_id

        # Corpo testuale
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Allegati
        for att in attachments:
            fname    = att.get("filename", "allegato")
            data     = att.get("data", b"")
            mimetype = att.get("mimetype", "application/octet-stream")
            maintype, subtype = mimetype.split("/", 1) if "/" in mimetype else ("application", "octet-stream")

            part = MIMEBase(maintype, subtype)
            part.set_payload(data)
            _encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment",
                            filename=("utf-8", "", fname))
            msg.attach(part)

        ctx = ssl.create_default_context()
        with smtplib.SMTP(
            host=account.get("smtp_host", "smtp.gmail.com"),
            port=int(account.get("smtp_port", 587)),
        ) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(account["address"], account["app_password"])
            server.sendmail(account["address"], [to], msg.as_bytes())

        logger.info("send_email_with_attachments: inviata a %s con %d allegati", to, len(attachments))
        return True
    except Exception as e:
        logger.error("send_email_with_attachments: %s", e)
        return False
