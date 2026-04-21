# Changelog
 
## [1.6.1] — 2026-04-21
 
### Added
  FIX: ALLARME
#### 🔊 Annuncio vocale Alexa per notifiche spazzatura
Nella sezione **Spazzatura** del pannello web, nuova opzione per inviare un annuncio TTS sugli speaker Alexa all'ora configurata, in aggiunta o in alternativa al messaggio Telegram.
 
- **Switch** indipendente per abilitare/disabilitare l'annuncio vocale
- **Selettore speaker** multiplo — l'annuncio parte contemporaneamente su tutti
- **Slider volume** 0–100% applicato automaticamente prima dell'annuncio
- **Pulsante "Test annuncio"** per verificare subito senza aspettare l'orario schedulato
- Speaker non disponibili (`unavailable`/`unknown`) nascosti automaticamente dalla lista
> Richiede l'integrazione **Alexa Media Player** installata in Home Assistant.
 
---
