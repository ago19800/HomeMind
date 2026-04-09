# 📍 HomeMind — Nuovo sistema Proximity avanzato

## Rilevamento presenza più intelligente: zone progressive + multi-fonte

Questa versione introduce un sistema di rilevamento presenza completamente ridisegnato per eliminare i falsi armamenti causati da GPS instabile, sensori fermi o telefoni che escono e rientrano rapidamente dalla zona casa.

**Tutto configurabile dalla pagina web ⚙️ → tab 📍 Proximity — senza toccare JSON.**

---

## Il problema che risolve

Con il vecchio sistema basato su una soglia singola (es. 100m), bastava che il GPS oscillasse di 10 metri per triggerare un ciclo uscita/rientro. Risultato: messaggi spam, falsi armamenti, benvenuti doppi.

Con il nuovo sistema puoi dire a HomeMind: *"aspetta 5 minuti prima di armare, e fallo solo se anche il WiFi conferma che sono uscito"*.

---

## Come funziona — tutti i casi

### Caso 1 — Solo GPS (comportamento predefinito, nessuna modifica richiesta)

Se non cambi nulla, HomeMind funziona esattamente come prima.

```json
"proximity_sensors": {
  "person.mario": {
    "sensor": "sensor.casa_mario_distance",
    "threshold_m": 100
  }
}
```

Uscito oltre 100m → HomeMind arma.  
Rientrato entro 100m → HomeMind disarma.

---

### Caso 2 — Zona gialla (anti falsi armamenti da GPS ballerino)

Aggiunge una **zona intermedia** dove HomeMind aspetta N minuti prima di armare. Se torni nella zona verde nel frattempo, annulla tutto silenziosamente.

```json
"person.mario": {
  "sensor": "sensor.casa_mario_distance",
  "threshold_m": 100,
  "zone_yellow_m": 500,
  "zone_yellow_wait_min": 5
}
```

**Come funziona:**

```
Casa ●
  ──── 100m ────  🟢 ZONA VERDE   → in casa, HomeMind non fa nulla
  ──── 500m ────  🟡 ZONA GIALLA  → fuori ma vicino, aspetta 5 minuti
  ────  ∞   ────  🔴 ZONA ROSSA   → definitivamente fuori, arma subito
```

**Esempio pratico:**
- Esci a portare il cane a 200m (zona gialla) → HomeMind avvia timer 5 min
- Torni a casa dopo 3 min → timer annullato, nessun armamento ✅
- Vai al lavoro a 5km (zona rossa) → HomeMind arma subito ✅
- Sei in zona gialla per 5 min senza rientrare → HomeMind arma ✅

**Campi:**
| Campo | Tipo | Default | Descrizione |
|-------|------|---------|-------------|
| `zone_yellow_m` | numero | vuoto (disattivato) | Distanza in metri dove inizia la zona gialla |
| `zone_yellow_wait_min` | numero | 5 | Minuti di attesa in zona gialla prima di armare |

---

### Caso 3 — WiFi tracker (seconda fonte di conferma)

Aggiunge il WiFi del telefono come seconda fonte. HomeMind arma solo se anche il WiFi conferma che sei fuori.

```json
"person.mario": {
  "sensor": "sensor.casa_mario_distance",
  "threshold_m": 100,
  "wifi_tracker": "binary_sensor.sm_s931b_wi_fi_state",
  "require": 2
}
```

HomeMind supporta due tipi di entità WiFi:

- **`binary_sensor.xxx_wi_fi_state`** → `on` = connesso (in casa), `off` = disconnesso (fuori)  
  *(creato dall'app Home Assistant Companion per Android/iOS)*
- **`device_tracker.xxx`** → `home` = in casa, `not_home` = fuori  
  *(creato dall'integrazione router o companion app)*

**Come funziona con `require: 2`:**

| GPS | WiFi | Risultato |
|-----|------|-----------|
| fuori | disconnesso | ✅ Arma — entrambe le fonti concordano |
| fuori | connesso | ⏸️ Non arma — WiFi dice ancora in casa |
| fuori | non disponibile | ⚠️ Scala a require:1, usa solo GPS |

**Campi:**
| Campo | Tipo | Default | Descrizione |
|-------|------|---------|-------------|
| `wifi_tracker` | entity_id | vuoto (disattivato) | Entità WiFi del telefono |
| `require` | 1 / 2 / 3 | 1 | Quante fonti devono concordare per armare |

---

### Caso 4 — Zona gialla + WiFi (massima protezione)

Combina entrambe le funzionalità. Il timer della zona gialla scatta, e al termine ricontrolla anche il multi-fonte. Due filtri in cascata.

```json
"person.mario": {
  "sensor": "sensor.casa_mario_distance",
  "threshold_m": 100,
  "zone_yellow_m": 500,
  "zone_yellow_wait_min": 5,
  "wifi_tracker": "binary_sensor.sm_s931b_wi_fi_state",
  "require": 2
}
```

**Flusso completo:**
1. Esci a 200m → zona gialla → timer 5 min
2. Timer scaduto → ricontrolla: ancora fuori? WiFi disconnesso?
3. Se sì a entrambe → arma
4. Se WiFi ancora connesso → non arma nonostante il timer

---

### Caso 5 — require: 3 (GPS + WiFi + Proximity tutti e tre)

Massima certezza. Tutte e tre le fonti devono dire "fuori" per armare.

```json
"person.mario": {
  "sensor": "sensor.casa_mario_distance",
  "threshold_m": 100,
  "wifi_tracker": "device_tracker.sm_s931b",
  "require": 3
}
```

> ⚠️ Usare `require: 3` solo se tutti e tre i sensori sono affidabili e aggiornati regolarmente. Se uno è spesso offline, usa `require: 2`.

---

### Fallback automatico se una fonte è offline

HomeMind non si blocca mai se una fonte non è disponibile.

```
require: 2, WiFi non disponibile → HomeMind usa require: 1 (solo GPS)
require: 3, Proximity stale     → HomeMind usa require: 2 (GPS + WiFi)
```

Il fallback viene loggato e non richiede alcuna azione dall'utente.

---

## Configurazione dalla pagina web

Vai in ⚙️ Impostazioni → tab **📍 Proximity**.

Per ogni persona vedrai ora:

```
👤 person.mario                                          [✕]
[sensor.casa_mario_distance ▼]  [100] m

🟡 Zona gialla  [500] m  attesa  [5] min

📶 WiFi  [binary_sensor.sm_s931b_wi_fi_state]  Fonti [2 fonti ▼]
```

- **Lascia zona gialla vuota** → funziona come prima
- **Lascia WiFi vuoto** → funziona come prima  
- **Fonti: 1-GPS** → funziona come prima

Clicca **💾 Salva impostazioni** — nessun JSON da toccare.

---

## Trovare i tuoi sensori WiFi in HA

1. Vai in **Home Assistant → Strumenti Sviluppo → Stati**
2. Cerca il nome del tuo telefono
3. Cerca entità che contengono `wi_fi`, `wifi`, `wlan`, `network`

Esempi comuni:
- `binary_sensor.sm_s931b_wi_fi_state` ← app companion Android
- `binary_sensor.iphone_di_mario_wifi_connection` ← app companion iOS
- `device_tracker.mario_telefono` ← integrazione router

---

## Riepilogo campi `person_config.json`

| Campo | Tipo | Default | Descrizione |
|-------|------|---------|-------------|
| `sensor` | entity_id | — | Sensore distanza GPS (obbligatorio) |
| `threshold_m` | numero | 100 | Soglia zona verde/gialla in metri |
| `zone_yellow_m` | numero | vuoto | Limite zona gialla in metri (vuoto = disattivata) |
| `zone_yellow_wait_min` | numero | 5 | Minuti attesa in zona gialla |
| `wifi_tracker` | entity_id | vuoto | Entità WiFi (`binary_sensor.*` o `device_tracker.*`) |
| `require` | 1 / 2 / 3 | 1 | Fonti minime concordi per armare |
| `stale_check` | bool | true | `false` = mantieni proximity attivo anche con dati vecchi |
