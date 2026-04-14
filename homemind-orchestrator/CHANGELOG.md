# Changelog

All notable changes to HomeMind Orchestrator are documented here.

---

## [Unreleased]

### 🆕 Added

#### 🔔 Alarm Auto-Arm Modes (`alarm_auto_arm`)
New field in `person_config.json` that controls how HomeMind handles the alarm when everyone leaves home:

- **`"auto"`** *(default, backward compatible)* — arms automatically without asking, same as before
- **`"notify"`** — sends a Telegram message with inline buttons **✅ Sì, attiva antifurto / ❌ No, lascia disarmato** before arming. If no response within 5 minutes, does not arm and notifies timeout
- **`"disabled"`** — HomeMind never touches the alarm system; only turns off lights and climate on departure

```json
"alarm_auto_arm": "notify",
"alarm_arm_mode": "armed_away"
```

Backward compatible: existing configs with `alarm_enabled: false` automatically map to `"disabled"`.

#### 🌡️ Temperature and Humidity Sensor Filters
New fields `temperature_sensors` and `humidity_sensors` to explicitly select which sensors HomeMind uses for briefing, AI responses and home status. Without configuration, HomeMind auto-detects all sensors from HA (excluding CPU, battery, weather sensors).

```json
"temperature_sensors": ["sensor.temp_soggiorno", "sensor.temp_camera"],
"humidity_sensors": ["sensor.umidita_soggiorno"]
```

Configurable from the web UI (⚙️ Settings → 🌡️ Temp/Umid tab).

#### ⚙️ Web Settings — New tabs
The web settings page (⚙️ icon) now includes:

- **🌡️ Temp/Umid** — select temperature and humidity sensors with search and checkboxes
- **📍 Proximity** — configure proximity sensors with + Add button and device list
- **🏠 Elettrod.** — add and configure appliances (power/smart mode) with sensor dropdown
- **🔔 Allarme** — configure alarm panel, extra partitions, `alarm_auto_arm` mode selector and `alarm_arm_mode`

All tabs save with **safe merge**: fields not managed by the UI (fascia_sensors, solar_optimizer, climate, etc.) are always preserved from the existing config file.

#### 📖 Interactive Manual (`/readme`)
New command available directly on Telegram:

```
/readme                    → index of all topics
/readme proximity          → explains proximity_sensors with JSON examples
/readme antifurto          → explains alarm modes
/readme fascia oraria      → explains F1/F2/F3 setup
/readme errori             → common errors and solutions
```

AI-powered search through the embedded manual. Falls back to text search if AI is unavailable.
Documented in `/comandi` list.

#### 🚀 Startup message simplified
The startup Telegram notification no longer shows "Nuovi comandi disponibili" with a hardcoded list. It now shows:

```
🎩 HomeMind attivo
Entita: 1551
Persone: Agostino, Rosa
Movimento: 4 sensori PIR
Allarme: alarm_control_panel.home_alarm
Casa: occupata

Scrivi /comandi per vedere tutti i comandi.
```

### 🐛 Fixed

- **`split("\n")` in f-string JS** — `getAlarmCfg()` textarea split for extra alarm panels now uses `String.fromCharCode(10)` instead of `"\n"` to avoid Python f-string interpreting it as a literal newline, which caused JS SyntaxError and broke all tab switching in the settings page
- **`removeAppRow` quadruple braces** — `{{{{` in source produced `{{` in generated JS → SyntaxError → all JS died. Fixed to `{{` producing `{`
- **`distances` NameError** — proximity tab referenced `distances` list that was not initialized in `settings_page()`. Added to sensor loop with distance/m/km detection
- **Duplicate `await notifier.send(` line** — startup notify block had a duplicated `await` call after refactoring; removed

---

## Previous releases

### Do Not Disturb (DND)
- Configurable quiet hours in `person_config.json` (`quiet_hours`) or via Telegram
- Non-critical notifications blocked during quiet hours; security alerts always pass through

### Aliases / Quick Commands
- Custom keyword system for guaranteed actions without AI, even offline
- Multi-sensor aliases: one keyword reads multiple sensors at once

### Offline Mode
- When all AI providers fail, basic commands (lights, blinds, alarm, status) handled by local deterministic parser

### Cover / Shutter fix
- HomeMind now reads `current_position` (real 0–100%) instead of HA state string

### Conflict-free memory
- Updating an existing preference updates the fact instead of duplicating it

### Climate auto-off configurable
- `climate_auto_off: false` disables automatic thermostat shutdown
- `climate_exclude` excludes specific entities (Netatmo TRV compatibility)

### Multi-partition alarm
- `alarm_extra_panels` arms multiple alarm partitions together (Paradox, DSC, etc.)

### Multi-AI cascade fallback
- 7 providers with automatic switching: gemini → groq → cerebras → deepseek → mistral → claude → openai
- Configurable in `ai_providers` array in `person_config.json`

### Solar Optimizer
- Notifies when solar surplus is available
- Optional auto-start of appliances when surplus confirmed for `confirm_minutes`

### Power Guard
- Monitors instantaneous consumption
- Three modes: `warn_only`, `ask` (confirm before switching off), `auto`

### Location Tracker
- Ask HomeMind where a person has been during the last N hours
- Real addresses via OpenStreetMap (no API key)

### Morning Briefing
- Fully customizable via Telegram without editing files
- Supports external weather city, custom greeting, tip_mode, exclude_sections

### Frigate NVR Integration
- Automatic snapshot on alarm trigger
- Per-camera sensor association

### Routine Manager
- Learns daily patterns after 3 days of observation
- Anticipates needs based on real habits

### Task Scheduler
- Schedule future actions in natural language
- `/task` to list, `/cancella_task N` to cancel

### Automations Manager
- Create, edit and delete HA automations via Telegram chat

### Log Analyzer
- Reads HA logs every 5 minutes
- Sends Telegram notification with AI analysis and fix proposals on critical errors

---

[Unreleased]: https://github.com/ago19800/HomeMind/compare/HEAD...HEAD
