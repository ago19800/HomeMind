# 📋 Changelog — HomeMind Orchestrator

## v1.3.0
- Fix campo `notify_entity` vuoto che causava errore 400 e bloccava tutte le notifiche Telegram
- Campo `notify_entity` ora opzionale — puoi lasciarlo vuoto senza problemi
- Fix snapshot Frigate duplicati — cooldown 60s per camera

## v1.2.x — Frigate NVR + Pagina Impostazioni
- Integrazione Frigate NVR: snapshot automatico su Telegram all'allarme
- Funziona con Frigate su PC separato nella stessa rete
- Tab 📹 Frigate nella pagina Impostazioni con menù a tendina per i sensori
- Pagina ⚙️ Impostazioni web completa: persone, sensori, spazzatura, energia, Frigate
- Merge automatico: salvataggio da UI preserva i campi avanzati del JSON
- Fix tab navigazione pagina impostazioni in HA Ingress
- Fix BOM UTF-8 nei file JSON da Windows
- Dashboard live con luci accese, allarme e persone in casa
- Comandi `/lavatrice` `/lavastoviglie` con slash riconosciuti correttamente

## v1.0.4 — Interfaccia Vocale
- Messaggi vocali su Telegram trascritti con Whisper
- ~$0.0005 per comando da 5 secondi — praticamente gratis

## v1.0.2 — Sicurezza
- Codice allarme mai esposto all'AI
- Autenticazione Web UI
- Log senza dati personali

## v1.0.0 — Release iniziale
- Agente AI per Home Assistant in italiano naturale
- Allarme automatico, monitor elettrodomestici, ottimizzatore solare
- Briefing mattutino, calendario spazzatura
