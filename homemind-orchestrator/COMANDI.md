# 🧠 HomeMind — Tutti i Comandi Telegram

> Documentazione completa. Richiamabile con `/comandi full` o `/tools`.

---

## 🔐 SSH & Terminale

| Comando | Descrizione |
|---------|-------------|
| `/ssh` | Menu SSH con esempi e pulsanti rapidi |
| `/ssh help` | Stessa cosa — alias |
| `/ssh <testo>` | Esegue su HA via SSH o container (AI sceglie) |
| `/ssh cmd: <comando>` | SSH diretto senza AI — es. `/ssh cmd: df -h` |
| `/ssh mostrami ram e cpu` | Info RAM/CPU host HA |
| `/ssh quanto disco è occupato` | Uso disco |
| `/ssh lista addon installati` | Addon HA attivi |
| `/ssh riavvia addon mosquitto` | Riavvia addon |
| `/ssh mostrami il log di homeassistant` | Log HA |
| `/ssh ping 192.168.1.1` | Ping diretto |
| `/ssh scansiona porte 192.168.1.90` | Scansione porte |
| `/ssh ls /config` | Lista file in /config |
| `/ssh temperatura cpu` | Temperatura CPU host |

### 💾 Salvataggio output SSH
Aggiungi `salva in <path>` o `→ <path>` a qualsiasi comando SSH:
```
/ssh dimmi ram e cpu → ago/progetti/sistema.md
/ssh cmd: df -h salva in ago/disco.md
/ssh lista addon → ago/addons.md
```

---

## 🔍 Ricerca Web & File

| Comando | Descrizione |
|---------|-------------|
| `/cerca <query>` | Cerca sul web con AI |
| `/cerca <query> salva in <path>` | Cerca e salva risultato in file |
| `/cerca <query> → <path>` | Alias con freccia |
| `/cerca <query> sovrascrivi <path>` | Sovrascrive file esistente |

**Comportamento file:**
- Se il file **non esiste** → viene creato
- Se il file **esiste già** → il contenuto viene aggiunto sotto (append)
- Per sovrascrivere usa la parola `sovrascrivi`

**Esempi:**
```
/cerca classifica serie A → ago/progetti/classifica.md
/cerca meteo lanciano → ago/note/meteo.md
/cerca sovrascrivi classifica serie A → ago/progetti/classifica.md
```

---

## 🤖 Agente AI (/fai)

| Comando | Descrizione |
|---------|-------------|
| `/fai <obiettivo>` | Agente autonomo multi-step |
| `/fai leggi ago/sistema.md e inviamelo formattato` | Legge e formatta file |
| `/fai elenca sensori energia e crea ago/energia.md` | Crea file con dati HA |
| `/fai aggiungi automazione accendi luci alle 19` | Modifica configuration.yaml |
| `/fai controlla se mosquitto è attivo` | Verifica stato addon |
| `/agent` | Menu agente con esempi |

---

## 🛠️ Tool disponibili (/tools)

| Tool | Descrizione |
|------|-------------|
| `tool_scrittura` | Crea/sovrascrive un file |
| `tool_lettura` | Legge un file (max 30k chars) |
| `tool_append` | Aggiunge testo in coda a un file |
| `tool_mkdir` | Crea cartella con parent |
| `tool_ls` | Lista contenuto cartella |
| `tool_delete` | Elimina file o cartella |
| `tool_search_web` | Ricerca DuckDuckGo |
| `tool_fetch_page` | Scarica testo pagina web |
| `tool_download` | Scarica file da URL |
| `tool_ping_python` | Ping a host/IP |
| `tool_portscan_python` | Scansione porte aperte |
| `tool_github_clone` | Clona repository GitHub |
| `tool_shell_exec` | Esegue shell nel container |
| `tool_natural_shell` | Linguaggio naturale → comando AI |
| `tool_install_package` | Installa pacchetto Alpine |
| `remember_command` | Memorizza comando per intent |
| `HATerminal.ssh_exec` | Comando SSH su host HA |
| `HATerminal.run_natural` | NL → SSH/Supervisor automatico |

---

## 📁 File & Config HA

| Comando | Descrizione |
|---------|-------------|
| `/scrivi <path> <contenuto>` | Scrive testo direttamente |
| `/leggi <path>` | Legge e mostra un file |
| `/ls [path]` | Lista file/cartelle in /config |
| `/mkdir <path>` | Crea una cartella |
| `/elimina <path>` | Elimina un file |
| `/scarica <url> <path>` | Scarica file da URL |
| `/clona <url>` | Clona repo GitHub in /config |
| `/modifica <file> <descr>` | Modifica file con AI |
| `/crea_sensore <descr>` | Crea sensor in configuration.yaml |
| `/leggi_config` | Mostra configuration.yaml |
| `/files_config` | Lista tutti i file in /config |

---

## 🏠 Home Assistant

| Comando | Descrizione |
|---------|-------------|
| `/stato` | Stato casa (luci, persone, sensori) |
| `/ha_sistema` | Info sistema HA (versione, uptime, RAM) |
| `/ha_addons` | Lista addon installati |
| `/aggiornamenti` | Controlla aggiornamenti |
| `/riparazioni` | Problemi e riparazioni HA |
| `/automazioni` | Lista automazioni |
| `/allarme` | Stato sistema allarme |

---

## 🚗 Targhe (Frigate LPR)

Scrivi in linguaggio naturale (richiede Frigate abilitato con riconoscimento targhe):

| Messaggio | Risultato |
|---|---|
| `che targhe hai rilevato?` | Targhe delle ultime 24 ore |
| `targhe oggi` / `targhe ieri` | Targhe di oggi / ieri |
| `targhe ultime 6 ore` · `targhe ultimi 3 giorni` | Periodo personalizzato |
| `targhe garage oggi` | Solo la camera indicata |
| `hai visto la targa AB123CD?` | Cerca una targa specifica |

---

## 📁 Salva file dalla chat

Prima configura le cartelle nella pagina web (tab 📁 File) e abilita la funzione. Poi invia un file al bot con una didascalia:

| Didascalia | Risultato |
|---|---|
| `invia nella cartella` · `salva` | Salva nella cartella predefinita e cancella il messaggio da Telegram |
| `salva in documenti` · `metti in foto` | Salva nella cartella con quel nome |
| *(nessuna didascalia)* | Bottoni per scegliere la cartella |

Non sovrascrive mai i file esistenti; limite 20 MB; il messaggio si cancella solo se il salvataggio riesce.

---

## 🎥 Rilevamenti Frigate (persone, animali, veicoli)

| Messaggio | Risultato |
|---|---|
| `cosa hai rilevato ieri` | Tutti gli oggetti rilevati |
| `hai visto persone oggi?` | Solo persone |
| `che cani hai rilevato?` · `gatti ultimi 3 giorni` | Animali |
| `chi è passato dal garage` | Filtra per camera |
| `persone ultima ora` · `cani ultimi 30 minuti` · `animali oggi` | Periodo: minuti, ore, giorni, oggi, ieri (senza periodo = ultime 24 ore) |
| `auto / moto / bici / pacchi rilevati` | Veicoli e pacchi |

Funzionano solo per gli oggetti tracciati in Frigate (`objects → track`).

---

## ⚡ Energia & Fotovoltaico

| Comando | Descrizione |
|---------|-------------|
| `/energia` | Consumo e produzione oggi |
| `/ieri` | Energia di ieri |
| `/solare` | Stato fotovoltaico |
| `/elettrodomestici` | Elettrodomestici rilevati |
| `/powerguard` | Soglia ENEL e protezione consumi |

---

## 📅 Task & Automazioni

| Comando | Descrizione |
|---------|-------------|
| `/task` | Lista task in coda |
| `/task_agent <descr>` | Programma task AI |
| `/task_shell <cmd>` | Programma task shell |
| `/task_alexa <testo>` | Invia messaggio Alexa TTS |
| `/cancella_task` | Cancella tutti i task |

---

## 🤖 AI & Providers

| Comando | Descrizione |
|---------|-------------|
| `/providers` | Provider AI configurati e attivi |
| `/ai_domotica` | Modalità focalizzata HA |
| `/ai_libera` | Chat generica |

---

## 🧠 Memoria & Alias

| Comando | Descrizione |
|---------|-------------|
| `/memoria` | Cosa HomeMind sa di te |
| `/memoria reset` | Cancella memoria |
| `/alias` | Lista alias configurati |
| `/comandi_appresi` | Comandi SSH memorizzati da /ssh |
| `/routine` | Abitudini apprese |

---

## 📚 Aiuto & Navigazione

| Comando | Descrizione |
|---------|-------------|
| `/help` | Start screen |
| `/comandi` | Menu principale |
| `/comandi full` | Questa documentazione completa |
| `/tools` | Lista tutti i tool disponibili |
| `/ssh` | Menu SSH con esempi |
| `/readme` | Documentazione configurazione |
| `/briefing` | Morning briefing immediato |
| `/spazzatura` | Raccolta rifiuti |

---

> 💡 **Tip:** Quasi tutti i comandi funzionano in linguaggio naturale.
>
> 🔀 **AI fallback:** se Gemini non risponde, passa automaticamente a Groq → Cerebras.
>
> 💾 **Salva sempre l'output:** aggiungi `→ ago/cartella/file.md` a qualsiasi comando.


---

## 🔗 Tool combinati (pipeline) — /fai

HomeMind può combinare tool in sequenza per task complessi:

| Tool | Descrizione |
|------|-------------|
| `fetch_url` | Scarica pagina web e opzionalmente salva in file |
| `read_and_summarize` | Legge file e lo riassume con AI |
| `download_and_read` | Scarica file da URL e lo analizza |
| `multi_step` | Esegue più tool in sequenza (output del passo N → input passo N+1) |

**Esempi pipeline:**
```
/fai scarica https://example.com/contratto.pdf in ago/contratto.pdf e fammi un riassunto

/fai leggi ago/progetti/classifica.md e inviami i primi 5 posti formattati

/fai scarica https://it.wikipedia.org/wiki/Roma leggilo e salvami un riassunto in ago/note/roma.md

/fai leggi /config/customize.yaml trovami tutte le entità con "luce" nel nome e listale
```

## 🖥️ Comandi HA CLI via SSH

L'addon Terminal & SSH usa `ago` come utente — i comandi HA sono disponibili via Supervisor API:

```
/ssh cmd: ha backups list       → lista backup HA
/ssh cmd: ha core info          → info versione HA
/ssh cmd: ha addons list        → lista addon installati
/ssh cmd: ha supervisor info    → info Supervisor
/ssh cmd: ha os info            → info OS
/ssh cmd: ha host info          → info host hardware
/ssh cmd: df -h                 → disco (bash diretto)
/ssh cmd: free -h               → RAM (bash diretto)
/ssh cmd: top -bn1              → processi (bash diretto)
```

> ⚠️ `systemctl` e `ha` non sono disponibili via SSH con utente `ago`.
> HomeMind intercetta automaticamente `ha <cmd>` e usa la Supervisor API.

