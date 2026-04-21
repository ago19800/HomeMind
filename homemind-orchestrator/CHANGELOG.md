# Changelog

All notable changes to HomeMind Orchestrator are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.5.8] — 2026-04-15

### Added

#### 🔓 Welcome notification with alarm status
When arriving home while the alarm was armed, the welcome Telegram message now includes the alarm disarm status:
```
🏠 HomeMind: Bentornato!
Agostino rientrato/a
In casa: Agostino, Rosa
Ora: 18:32
🔓 Antifurto disarmato (era: 🏃 via da casa)
```

#### 🤖 AI Automations in natural language
Create Home Assistant automations directly from Telegram using natural language:
> *"Crea automazione: quando sensore scala rileva movimento alle 23, accendi luce esterna e mandami notifica Telegram"*

HomeMind generates valid YAML, uses real entity IDs from the **EntityRegistry**, and saves the automation to `automations.yaml` with automatic reload.

**How it works:**
- `EntityRegistry` scans all HA entities every 15 minutes and builds a local catalogue
- Motion sensors are enriched with their zone (e.g. `[zona:cucina]`, `[zona:scala]`) so the AI can match natural language to the correct `entity_id`
- Telegram notifications use `telegram_bot.send_message` with the configured `chat_id` (the legacy `notify.telegram` service is deprecated in HA 2026+)
- If an automation with the same `id` already exists, it is **replaced** (upsert) instead of duplicated — preventing reload errors

#### ⏱️ Configurable delay between alarm partitions (`alarm_extra_delay`)
For multi-partition systems (EvoHD, Paradox, DSC) that reject commands sent too quickly, a configurable delay is now applied between each partition during both arming and disarming:

```json
"alarm_extra_panels": [
  "alarm_control_panel.evohd_partition_esterno",
  "alarm_control_panel.evohd_partition_riv_est_1_piano"
],
"alarm_extra_delay": 2
```

Default is `1` second. Can be set from the web UI under **Antifurto → ⏱️ Delay tra partizioni extra**.

### Fixed

#### 🚫 `alarm_auto_arm: disabled` now blocks disarm too
Previously, `disabled` mode only prevented HomeMind from **arming** the alarm. On return, HomeMind would still **disarm** it automatically. Now `disabled` is a full hands-off mode — HomeMind never touches the alarm in either direction.

#### 👋 Welcome notification after HomeMind restart
`_was_away` (the flag that gates welcome notifications) was reset to `False` on every restart. If HomeMind restarted while you were away, no welcome would be sent on return. **Fixed:** `startup_check` and the 2-minute rebuild loop now re-initialise `_was_away = True` for anyone the GPS shows as away.

#### 🔁 Proximity near/far transition — welcome trigger
The "proximity becomes near → trigger welcome" logic was firing on every proximity sensor update (even when stationary at 0m). **Fixed:** the trigger now only fires on a genuine **far→near transition** (previous value > threshold, new value ≤ threshold), preventing duplicate welcome notifications when a second person arrives home.

#### 📍 Entity IDs in AI automations
Previously the AI could invent entity IDs (e.g. `light.luce_mario`) instead of using real ones. **Fixed:** the `EntityRegistry` now feeds the AI a structured catalogue:
```
[light] Luce Mario → light.yeelight_ct_bulb_0x536fe64 (off)
[binary_sensor] Sensore occupancy [zona:scala] → binary_sensor.0x00158d000224fa71_occupancy (off)
```

---

## [1.5.7] — previous release

See git history.
