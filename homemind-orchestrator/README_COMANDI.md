# 🏠 HomeMind — Comandi Telegram

> Tutti i comandi utilizzabili via Telegram. Scrivi il comando così com'è, con o senza `/`.

---

## 🔐 SSH & Terminale

| Comando | Descrizione |
|---------|-------------|
| `/ssh` | Menu SSH con esempi completi |
| `/ssh <richiesta>` | Esegui qualsiasi cosa: AI capisce se andare sull'host HA o nel container |
| `/ssh cmd: <comando>` | Esegui **direttamente** via SSH sull'host (nessuna AI, nessuna interpretazione) |
| `/ssh mostrami ram e cpu` | Info sistema host via Supervisor |
| `/ssh lista addon installati` | Lista addon HA |
| `/ssh quanto disco è occupato` | Spazio disco host |
| `/ssh ping 192.168.1.1` | Ping verso un IP |
| `/ssh scansiona porte su 192.168.1.90` | Port scan |
| `/ssh ls /config` | Lista file nel container |
| `/ssh cerca tutti i file .yaml in /config` | Ricerca file nel container |
| `/ssh cmd: df -h` | Spazio disco (SSH diretto) |
| `/ssh cmd: cat /proc/meminfo` | Memoria (SSH diretto) |
| `/ssh cmd: systemctl status homeassistant` | Stato servizio HA |

---

## 🔍 Ricerca & File

| Comando | Descrizione |
|---------|-------------|
| `/cerca <query>` | Cerca sul web e mostra risultato AI |
| `/cerca <query> salva in <path>` | Cerca e salva risultato in un file |
| `/cerca <query> aggiungi in <path>` | Cerca e **aggiunge sotto** in un file esistente |
| `/cerca <query> sovrascrivi <path>` | Cerca e **sovrascrive** il file esistente |
| `/scrivi <path> <contenuto>` | Scrivi testo in un file |
| `/leggi <path>` | Leggi un file |
| `/ls <path>` | Lista file in una cartella |
| `/mkdir <path>` | Crea una cartella |
| `/elimina <path>` | Elimina un file |
| `/scarica <url>` | Scarica un file da URL |
| `/clona <url>` | Clona repository GitHub |

**Esempi path file:**
```
/cerca classifica serie A salva in config/ago/progetti/classifica.md
/cerca meteo Milano aggiungi in config/ago/meteo.md
/scrivi config/ago/note.md Queste sono le mie note
/leggi config/ago/progetti/classifica.md
/ls config/ago/progetti
```

---

## 🏠 Home Assistant

| Comando | Descrizione |
|---------|-------------|
| `/ha_sistema` | Info sistema HA (versione, uptime, memoria) |
| `/ha_addons` | Lista addon installati con stato |
| `/stato` | Stato casa (luci, sensori, allarme) |
| `/allarme` | Stato allarme |
| `/automazioni` | Lista automazioni HA |
| `/crea_card` | Genera card Lovelace con AI |

---

## 🤖 AI & Agente

| Comando | Descrizione |
|---------|-------------|
| `/fai <obiettivo>` | Agente AI che pianifica ed esegue azioni complesse |
| `/agent <obiettivo>` | Alias di `/fai` |
| `/task_agent <quando> <cosa>` | Programma un'azione agente una tantum |
| `/task_shell <quando> <comando>` | Programma un comando shell periodico |
| `/task` | Lista task schedulati |
| `/ai_mode` | Cambia modalità AI (domotica / libera) |
| `/providers` | Gestisci provider AI (Gemini, Groq, Claude...) |

---

## 📁 Configurazione HA

| Comando | Descrizione |
|---------|-------------|
| `/modifica <file.yaml> <istruzione>` | Modifica un file yaml con AI |
| `/crea_sensore <descrizione>` | Crea un sensore template con AI |
| `/leggi_config` | Leggi configuration.yaml |
| `/files_config` | Lista file di configurazione |
| `/backups_config` | Lista backup disponibili |
| `/aggiornamenti` | Controlla aggiornamenti HA e addon |
| `/riparazioni` | Controlla errori e riparazioni HA |

---

## 🧰 Strumenti Diretti

| Comando | Descrizione |
|---------|-------------|
| `/tools` | Menu strumenti con tutti i comandi file |
| `/cerca <query>` | Ricerca web con AI |
| `/comandi_appresi` | Comandi shell memorizzati dall'AI |

---

## ⚡ Energia & Elettrodomestici

| Comando | Descrizione |
|---------|-------------|
| `/energia` | Produzione solare e consumo oggi |
| `/ieri` | Energia di ieri |
| `/energia_analisi` | Analisi dettagliata consumi |
| `/solare` | Stato ottimizzatore solare |
| `/elettrodomestici` | Stato elettrodomestici |
| `/powerguard` | Stato protezione soglia potenza |

---

## 🗣 Utilità

| Comando | Descrizione |
|---------|-------------|
| `/comandi` | Menu completo comandi |
| `/readme` | Questa guida |
| `/briefing` | Morning briefing — riassunto casa |
| `/spazzatura` | Prossima raccolta rifiuti |
| `/memoria` | Cosa ricorda HomeMind di te |
| `/routine` | Routine e abitudini apprese |
| `/alias` | I tuoi alias e scorciatoie |
| `/dimentica` | Cancella una memoria specifica |
| `/config` | Mostra configurazione attuale |
| `/lingua it/en` | Cambia lingua |

---

## 💡 Suggerimenti

- **Path file**: scrivi sempre `config/ago/...` o `/config/ago/...` — HomeMind li interpreta uguale
- **Linguaggio naturale**: quasi tutti i comandi accettano linguaggio naturale oltre al formato preciso
- **Append vs sovrascrittura**: di default HomeMind **aggiunge** se il file esiste. Scrivi `sovrascrivi` per rimpiazzare
- **SSH diretto**: usa il prefisso `cmd:` per saltare l'AI e inviare il comando grezzo all'host
- **Provider AI**: HomeMind usa automaticamente il primo provider disponibile con fallback in cascata. Gestiscili con `/providers`

---
*Generato automaticamente da HomeMind*
