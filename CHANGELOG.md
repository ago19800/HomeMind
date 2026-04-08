# HomeMind Orchestrator — Changelog v1.5.3

## 🔒 Sicurezza & Antifurto

### Fix: doppio messaggio di benvenuto al rientro
**Causa:** quando il sensore proximity e il GPS si aggiornano quasi contemporaneamente, `_someone_arrived()` veniva chiamata due volte in rapida successione, schedulando due task di benvenuto separati → due messaggi Telegram.

**Fix:** aggiunto `MIN_REPEAT_COOLDOWN = 300s` come limite assoluto tra due benvenuti per la stessa persona. Non bypassabile dal `cooldown_override`.

---

### Fix: spam messaggi di conferma armamento (modalità `notify`)
**Causa:** in `alarm_auto_arm: notify`, ogni aggiornamento proximity triggerava una nuova richiesta di conferma Telegram anche mentre si aspettava la risposta della precedente.

**Fix:**
- Flag `_arm_notify_in_progress`: blocca `_all_left()` mentre HomeMind aspetta la risposta
- Al termine (risposta o timeout), aggiorna `_last_arm_ts` per impedire richieste immediate
- `ARM_COOLDOWN`: 60s → **180s**
- `NOTIFY_CONFIRM_COOLDOWN = 120s`: ulteriore protezione anti-spam modalità notify

---

### Fix: GPS oscillante con proximity stale genera falsi arm/disarm
**Causa:** con proximity stale (`stale_check: false`), HomeMind cedeva al GPS. Se il GPS oscillava ogni 1-2 minuti, venivano generati continui cicli arm/disarm.

**Fix:** debounce **5 minuti** in `_handle_presence()` — se il proximity è stale, due cambi GPS consecutivi devono distare almeno 5 minuti per essere considerati validi.

---

### Fix: disarmo solo partizione primaria al rientro
**Causa:** `_fast_disarm()` disarmava solo il pannello principale, lasciando le partizioni extra armate.

**Fix:** `_fast_disarm()` ora cicla su tutte le `alarm_extra_panels` e le disarma al rientro.

---

### Fix: disarmo emergenza al riavvio con proximity stale
**Causa:** al riavvio con proximity stale (es. 2494 min fa) e `stale_check: false`, HomeMind impostava lo sticky "vicino" → persona risultava a casa → se l'allarme era `armed_away` scattava disarmo emergenza.

**Fix (doppio):**
1. `home_model.py`: con dati più vecchi di `max_age_min × 2`, `last_near_ts` non viene impostato
2. `startup_check()`: verifica il GPS direttamente prima del disarmo — se il GPS dice "fuori", non disarma

---

### Fix: errore 400 Bad Request nelle notifiche HA (`notify.telegram_bot_*`)
**Causa:** `notifier.send()` passava `title` al servizio HA `telegram_bot`, che non lo accetta.

**Fix:** `send()` salta `_ha_notify()` quando `ha_entity` inizia con `telegram_bot`. La notifica viene inviata direttamente via API Telegram.

---

## ⚡ Energia & Fotovoltaico

### Fix: briefing mostra valore cumulativo FV invece del delta giornaliero
**Causa:** per sensori cumulativi come `sensor.fv_tot1` (totale kWh da installazione), lo snapshot delle 23:30 salvava il valore grezzo (es. 11551 kWh) invece della produzione del giorno.

**Fix:** `_take_snapshot()` rileva sensori cumulativi (valore > 1000 kWh) e salva il **delta rispetto allo snapshot di ieri**.

> **Nota:** il primo giorno dopo l'aggiornamento lo snapshot salverà ancora il raw (nessuno snapshot ieri disponibile). Il giorno successivo funzionerà.

---

### Fix: `/energia` mostra valore grezzo FV di notte
**Causa:** di notte (0–6), nessun campione history con data odierna → `today_vals` vuoto → `fv_oggi_delta = None` → veniva mostrato il totale cumulativo.

**Fix:**
- `hours=20` → **`hours=26`** per coprire sempre mezzanotte + margine DST
- Se `today_vals` è vuoto, usa `max(ieri_vals)` come baseline (= fine giornata ieri = inizio di oggi)
- Delta sempre ≥ 0

---

### Fix: batteria mostrata con unità errata (V invece di % o kWh)
**Causa:** se configurato un sensore tensione come `batteria_wh`, veniva mostrato come "1003.09 kWh".

**Fix:** rilevamento automatico dell'unità:
- `V` → "1003.1 V ⚠️ (tensione, non SOC%)"
- `%` → "85% ████████░░" con barra
- `kWh` → comportamento normale

---

### Fix: `sensor.fv_tot` non appare nella web UI (selezione energia)
**Causa:** il filtro cercava solo unità `kWh/Wh` o nomi con `energy`/`kwh`.

**Fix:** aggiunto riconoscimento per keyword `fv`, `solar`, `produz`, `consumo`, `enel`, `batteria` nell'entity_id.

---

## 🧠 Memoria

### Fix: fatti di automazioni rimosse presenti in memoria
**Causa:** la memoria poteva contenere fatti estratti da conversazioni precedenti che menzionavano comandi ora inesistenti, causando risposte incoerenti.

**Fix:** `MemoryManager._load()` filtra automaticamente all'avvio i fatti con keyword di feature rimosse (`automazioni_hm`, `automazioni intelligenti`, `se allora`, ecc.).

---

## 🗑️ Rimosso: Automazioni Intelligenti HomeMind

Feature completamente rimossa:

- `/automazioni_hm`, `/auto_hm`, `/cancella_automazione N`, `/pausa_automazione N`, `/riprendi_automazione N`, `/dettaglio_automazione N`
- Rimozione dal manuale `/readme` e dalla lista `/comandi` (IT e EN)
- `automation_engine.py` non viene più caricato

**I Task Ripetuti (`/task_ripetuti`) rimangono invariati e funzionanti.**

---

## 🌅 Briefing

### Fix: energia ieri sbagliata nel briefing (sensori daily)
**Causa:** la History API restituiva delta errato per sensori che si resettano a mezzanotte.

**Fix:** il briefing legge lo snapshot di `EnergyAnalyzer` da `/data/homemind_energy_history.json` (salvato alle 23:30). La History API è usata solo come fallback.

---

### Nuovo: elettrodomestici attivi nel briefing
Se almeno un elettrodomestico risulta in funzione al momento del briefing, appare la sezione "⚡ Elettrodomestici attivi".

---

## 📱 Web UI — Nuovi Tab

### ☀️ Solare
Configurazione `solar_optimizer` da interfaccia grafica:
- Parametri generali (surplus minimo, minuti conferma, cooldown, elevazione solare minima)
- Sezione **Batteria**: campo testo libero per `battery_soc_sensor` — qualsiasi entity_id, anche se non in lista
- Sezione **Elettrodomestici**: Nome · Switch (opz.) · Surplus min W · Auto (avvio automatico) · Attivo

### 📱 Tracker
Associa ogni persona a un `device_tracker.*` per la cronologia spostamenti.
- `dove è stato Agostino oggi?` · `percorso di Rosa` · `soste di Mario`

### ⚡ Guard — Appliances Priority
Sezione con righe editabili per le entità da spegnere al superamento soglia: Nome · Entity ID · Priorità.

---

### Fix: web UI non caricava (UnboundLocalError: INP)
Variabili pre-calcolate riordinate per garantire che `INP` sia sempre definita prima di qualsiasi sezione che la utilizza.

---

## ⚙️ Costanti modificate

| Costante | Prima | Dopo |
|---|---|---|
| `ARM_COOLDOWN` | 60s | 180s |
| `MIN_REPEAT_COOLDOWN` (welcome) | — | 300s (nuovo) |
| `GPS_DEBOUNCE_SEC` (proximity stale) | — | 300s (nuovo) |
| `NOTIFY_CONFIRM_COOLDOWN` (notify mode) | — | 120s (nuovo) |
| History FV `hours` | 20 | 26 |
