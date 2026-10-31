# Changelog

All notable changes to HomeMind Orchestrator are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## 1.15.9
### Fixed
- **TV (voce Alexa): «alza / abbassa il volume della tv» a volte non cambiava il volume.** Tre cause sistemate:
  1. Con una TV collegata a barra audio / ARC / uscita esterna, Home Assistant accetta `volume_set` ma il volume non si muove (e HomeMind rispondeva comunque «Volume 25%»). Ora, dopo `volume_set`, HomeMind rilegge il livello dalla TV: se è rimasto uguale (o se `volume_set` dà errore) preme i **tasti volume del telecomando** (LG: `webostv.button` VOLUMEUP/VOLUMEDOWN, come il telecomando vero; Samsung/Sony: `remote.send_command`; altre marche: `media_player.volume_up/down`). Se il livello è cambiato non preme niente (nessuna doppia applicazione).
  2. TV che non espone il livello del volume: prima si usavano solo `media_player.volume_up/down`, ora per prima cosa i tasti fisici, poi quei servizi. Se nulla funziona la risposta è «Volume non modificato» invece di una conferma falsa.
  3. Dire due volte di fila la stessa frase («alza il volume della tv» … «alza il volume della tv») entro 10 s: la seconda veniva scartata come doppione. Ora una pronuncia è identificata da frase + `last_called_timestamp` di Alexa, quindi la ripetizione viene eseguita; la stessa pronuncia vista da due Echo (anche con timestamp leggermente diversi) conta ancora una volta sola.
- Nel log: `TV: volume_set accettato ma il livello è rimasto N% (uscita audio esterna?): uso i tasti volume` e `TV: volume N% → M% (volume_set)`.
### Added
- **La TV non è più solo LG.** Nella scheda 📺 TV: **Marca** (Automatica, LG webOS, Samsung, Sony Bravia, Altra marca) e **Telecomando (opzionale)** (entità `remote.*`, trovata da sola se ha lo stesso nome della TV). Accensione, volume, muto, canale, ingressi e pausa usano solo i servizi standard `media_player.*` e quindi valgono per ogni TV integrata in Home Assistant; la marca serve solo per i tasti (frecce, OK, numeri, e il cambio canale a cifre quando `play_media` non trova il canale). Marca non riconosciuta → si prova come LG (come prima). Chi aggiorna non deve cambiare nulla: senza i nuovi campi tutto funziona come in 1.15.8.
- **Elenco «Entità della TV» solo con le TV**: Echo/Alexa, Google Nest, Sonos, barre audio, Spotify e altri lettori musicali non compaiono più. Si riconosce dalla `device_class: tv` o dal nome (tv, televisione, lg, samsung, philips, sony/bravia, panasonic, hisense…). La TV già scelta resta sempre visibile; la spunta «Non vedi la tua TV? Mostra tutti i lettori multimediali» riapre l'elenco completo.
- **File d'esempio dei canali** (`tv_canali_esempio.json`, scaricabile dalla scheda e in `config_example/`): 23 canali nazionali del digitale terrestre con numerazione LCN (Rai 1 = 1 … Rai News 24 = 48), alias e una sezione `comandi_audio` con frasi per volume e muto. Si carica senza avvisi; i numeri vanno confrontati con la lista della propria TV.
- Telegram: i tasti del telecomando che non esistono per la marca rispondono «Questo tasto non è disponibile per la tua TV…» invece di un errore generico.
- 31 nuovi test (`tests/test_tv.py`, `tests/test_tv_api.py`).
### Notes
- Provato (test automatici + uso reale dell'autore): LG webOS. Le mappe tasti Samsung (`KEY_*`) e Sony (nomi IRCC) sono scritte secondo la documentazione delle integrazioni ma **non ancora provate su TV reali**.

## 1.15.8
### Fixed
- **TV (voce): «metti canale 34» metteva il 4 e «metti canale 35» il 5.** Alexa trascrive «metti canale trenta quattro» (due parole) e nel file canali «quattro» e «cinque» sono alias di Rete 4 e Canale 5: il parser trovava l'alias dentro la frase prima di capire che era la seconda metà di un numero. Ora un alias che finisce (o comincia) con un numero viene scartato quando nella frase prosegue in un numero più lungo: «trenta quattro» = 34, «trenta cinque» = 35, «venti due» = 22 (non l'alias «canale venti»), mentre «metti canale quattro» = Rete 4, «canale cinque» = Canale 5 e i nomi come «focus» continuano a funzionare. Provato con tutti i 34 canali del file dell'utente (22 nuovi test).

## 1.15.7
### Fixed
- **TV: la sezione `comandi_audio` del file canali non veniva letta.** Le frasi personalizzate («alza la voce», «più alto», «su la voce», «giù la voce», «silenzio», «togli l'audio»…) erano ignorate e valevano solo le regole interne; in particolare «togli l'audio della tv» veniva interpretato come *riattiva* l'audio (l'opposto). Ora `comandi_audio` funziona (azioni: `alza_volume`, `abbassa_volume`, `muto`, `riattiva_audio`) e ha la precedenza sulle regole interne; «di 10» / «di dieci» imposta di quanto. Da voce serve la parola «tv» («alza la voce della tv»): senza, la frase resta all'Echo (altrimenti HomeMind alzerebbe anche la TV a ogni «alza il volume» detto all'Echo); da Telegram con `/tv` non serve. Voci sbagliate nel file generano un avviso nella scheda TV senza invalidare i canali.
- «tv più alto di cinque» non viene più scambiato per il canale 5 (alias «cinque»).
- Controllo «frase vecchia» di Alexa: un orario senza fuso orario veniva letto in un solo modo e poteva far scartare un comando appena detto; ora basta che sia recente in una delle due letture (locale o UTC).
- 6 nuovi test con il file canali reale (`tests/test_tv.py`).

## 1.15.6
### Fixed
- **«AI non disponibile (401 Wrong API Key)» mentre il Test della pagina Provider diceva «ok».** Due cause nel codice: (1) il Test prova la chiave che hai appena digitato nel campo, mentre la chat usa la catena di provider caricata all'avvio: dopo un «Salva» la chat continuava con la chiave vecchia finché non riavviavi; (2) l'errore in Telegram mostrava solo l'ULTIMO provider della catena (spesso un provider diverso da quello che pensavi di aver sistemato, ad esempio uno rimasto nelle Opzioni dell'add-on).
  - «Salva» nella pagina Provider ora applica subito la catena in uso (nessun riavvio): «✅ Salvato e applicato subito».
  - Il Test dice anche se la chiave provata è quella che HomeMind sta usando davvero («⚠️ ma HomeMind sta usando un'ALTRA chiave: premi Salva» / «non ancora in uso»).
### Improved
- Quando tutti i provider falliscono, il messaggio Telegram elenca ogni provider con l'origine (`[dashboard]` o `[opzioni]`) e il motivo: chiave rifiutata (401), limite gratuito raggiunto, quota esaurita, modello non trovato, timeout. Nel log compare anche il suffisso della chiave in uso (solo le ultime 4 cifre).
- 7 nuovi test (`tests/test_ai_provider.py`).

## 1.15.5
### Fixed
- **«Crea un file ago.txt» rispondeva «salvato» ma non creava niente.** Nella chat normale l'AI non ha nessuno strumento per scrivere file (li crea solo l'agente `/fai`), ma rispondeva lo stesso con una conferma e un percorso inventati (`/config/ago/progetti/test`). Ora:
  - la richiesta in linguaggio naturale viene riconosciuta e il file viene creato **davvero** (stessi controlli dell'agente: solo sotto `/config`, file protetti esclusi, mai sovrascritto in silenzio) e verificato sul disco prima di rispondere. Esempi: `crea file utente.md con scritto Ciao`, `crea file note.txt in ago/documenti con scritto la spesa`, `crea un file ago.txt` (file vuoto). Senza cartella usa `ago/progetti` e lo scrive nella risposta;
  - l'AI della chat sa che non può scrivere file e non deve inventare conferme;
  - rete di sicurezza: se per una richiesta di file risponde comunque «file creato», la risposta viene sostituita da un avviso onesto con gli esempi di comando corretti.
- 21 nuovi test (`tests/test_file_create.py`).

## 1.15.4
### Fixed
- **«spostamenti» / «soste di …» mostrava una sola sosta da 24h.** Home Assistant considera `minimal_response` attivo anche scritto `=false`: la history restituiva lat/lon solo per il primo e l'ultimo punto, quindi tutta la giornata diventava un'unica sosta. Ora il tracciamento GPS chiede gli attributi completi (nuova opzione `full_attributes` di `get_history`; tutti gli altri chiamanti — energia, grafici — restano identici). In più l'orario di ogni punto usa `last_updated` (non `last_changed`, che resta fermo finché lo stato home/not_home non cambia).
- La routine (Agostino.md, Rosa.md, luoghi frequenti) usava gli stessi dati sbagliati: al primo avvio HomeMind ricalcola luoghi e soste GPS da zero (parametri v3) con lo storico che Home Assistant conserva. I luoghi frequenti calcolati prima, non affidabili, vengono azzerati e ricostruiti.
### Added
- **Spostamenti più intelligenti**: per «oggi», «ieri», una data o fino a 48 ore la risposta è una giornata in ordine cronologico con i tratti di viaggio (durata e km in linea d'aria) e un riepilogo. Le soste riconoscono tutte le zone definite in Home Assistant (🏠 Casa, Lavoro, Palestra… con il loro nome), non solo casa. Per periodi più lunghi resta la classifica per durata di prima.
- **Memoria per persona**: i fatti possono essere attribuiti a una persona (Agostino, Rosa…) e non si sovrascrivono a vicenda (prima «Rosa vuole 23°» cancellava «Agostino vuole 21°»). `/memoria` li raggruppa per persona; nel prompt l'AI li riferisce solo a chi riguardano.
- **Memoria più affidabile**: i fatti vengono estratti solo da ciò che scrive l'utente (le risposte del bot servono da contesto), e un fatto del tipo «si chiama X» viene scartato se nessuno ha mai scritto quel nome (era così che era finito in memoria «L'utente si chiama Gianni»).
- **Abitudini osservate dai dati reali** (nessuna chiamata AI): orari tipici di uscita/rientro e luoghi frequenti di ogni persona (dalla routine GPS) e, con il nuovo `agent/habit_learner.py`, gli orari ricorrenti di luci, prese e tapparelle dagli ultimi 14 giorni («l'interruttore Macchina caffè si accende di solito verso le 07:05, nei giorni feriali»). Si ricalcolano ogni notte, compaiono in `/memoria` e vengono passate all'AI.
- 26 nuovi test (`tests/test_location_tracker.py`, `tests/test_memory_habits.py`).

## 1.15.3
### Added
- **📺 Telecomando a bottoni su Telegram**: scrivi «telecomando» (o `/telecomando`, «apri il telecomando») e il bot invia un telecomando con i tasti: ⏻ On/Off, Muto, Home, Vol −/+, frecce, OK, Indietro, Menu, Canale −/+, Info, Play/Pausa, Esci. Da lì «🔢 Numeri» apre il tastierino 0-9 e «📥 Ingressi» l'elenco degli ingressi/app della TV (si torna al telecomando dopo la scelta). I tasti usano gli stessi servizi di Home Assistant già usati per la TV (`webostv.button`, `media_player.*`); a TV spenta solo ⏻ risponde, gli altri avvisano. Se un tasto non riesce il bot lo scrive in chat; se va bene resta in silenzio (il messaggio non si riempie).
- Solo la parola esatta apre il telecomando: frasi come «dov'è il telecomando?» continuano ad andare all'AI. Richiede che nella scheda 📺 TV sia scelta l'entità; i chat non autorizzati restano bloccati come per gli altri bottoni.
- 5 nuovi test (`tests/test_tv.py`).

## 1.15.2
### Fixed
- **TV (voce Alexa): «metti canale trenta tré t. v.» non veniva capito.** Alexa Media Player riporta la frase con i numeri in lettere e «tv» scritto «t. v.», mentre il parser cercava «tv» e le cifre. Ora «t. v.» / «tivù» valgono «tv» e i numeri in lettere (trentatré, trenta tre, ventuno, centoventi, duecentocinque…) diventano cifre, per canale, volume («volume della tv a trenta») e ingressi («hdmi due»). I nomi dal file canali hanno la precedenza (es. «canale cinque» = Canale 5 → 505, «rai uno» = Rai 1). Valido anche per le frasi scritte su Telegram.
- TV (voce Alexa): l'ascolto della frase non rieseguiva mai più la stessa frase, ma ogni cambio di stato dell'Echo rimandava il vecchio `last_called_summary` e, dopo 10 s, il comando poteva ripartire (anche dopo un riavvio di HomeMind). Ora si agisce una sola volta per frase, usando `last_called_timestamp`; una frase già vecchia di oltre 60 s al primo avvistamento viene ignorata.
### Improved
- TV (voce Alexa): nel log compare una riga `TV voce: frase ricevuta da … «…» → azione` per ogni frase che Alexa Media Player riporta, anche se non è un comando TV. Se la riga non compare, la frase non arriva a HomeMind (Alexa non l'ha registrata). Gli errori dell'ascolto sono ora a livello WARNING invece di DEBUG, e i task dei comandi non possono più essere raccolti dal garbage collector.

## 1.15.1
### Improved
- TV: se Home Assistant dà la TV come «unavailable» (spenta o non raggiungibile) il messaggio ora lo dice chiaramente e indica cosa fare (accenderla, oppure inserire il MAC per accenderla a distanza), senza attese inutili. Con il MAC prova a riaccenderla e poi esegue il comando. Nell'elenco della scheda, tra le TV, quelle raggiungibili vengono prima.

## 1.15.0
### Added
- **📺 Scheda TV (LG webOS)** nelle Impostazioni. Usa l'entità `media_player` che l'integrazione webOS di Home Assistant ha già creato (nessun IP da inserire). Comandi: accendi/spegni, volume (alza/abbassa di N, imposta a N), muto, canale per numero («metti canale 35», con ripiego sui tasti numerici se la TV non trova il canale), canale successivo/precedente, canale per nome («metti Rai 1», dal file `tv_canali.json`), ingressi e app dalla `source_list` della TV («metti netflix sulla tv», «metti hdmi 2»), pausa/riprendi.
- **Voce (Alexa Media Player)** come la dieta: switch comandi vocali, switch notifica Telegram, conferma a voce sugli speaker scelti. Con la TV spenta e il MAC configurato, «metti canale 35» la accende (Wake-on-LAN) e poi cambia canale.
- **Telegram**: `/tv volume 30`, `/tv canale 35`, `/tv spegni`… oppure la frase libera («metti canale 35», «alza il volume della tv»). Endpoint `POST /api/tv/ask` per routine/automazioni.
- Sicurezza: «alza il volume» senza la parola «tv» NON viene intercettato (resta dell'Echo); frasi con musica, luci, sveglia ecc. escluse. Le impostazioni si salvano nella chiave `tv` di `person_config.json` senza toccare il resto.
- 47 nuovi test (`tests/test_tv.py`, `tests/test_tv_api.py`).

## 1.14.7
### Improved
- Dieta (Alexa/Telegram): più frasi di attivazione, non solo «cosa ho per…»: «spuntino pomeridiano», «cena di domani», «qual è lo spuntino pomeridiano», «dimmi/leggimi/dammi la cena», «che c'è per cena», «cosa devo mangiare a pranzo»… Le frasi di 3 parole o meno con un pasto bastano da sole. Restano escluse quelle con musica, luci, prenotazioni, liste della spesa, ecc.
- Tab Dieta: spiegazione e frasi consigliate per creare le routine Alexa che evitano che Alexa dia prima la sua risposta.
- Cartelle su Telegram: l'elenco numerato compare SEMPRE (anche con pochi file) e non invia nulla finché non tocchi un numero; «📎 Invia tutti» resta come bottone.

## 1.14.6
### Added
- **Cartelle su Telegram**: «Mandami la cartella bollette» / «il contenuto di foto vacanze» invia i file di QUELLA cartella (solo quelli direttamente al suo interno, non le sottocartelle né le altre cartelle). Fino a 10 file li invia subito; con più file mostra l'elenco a pagine con «📎 Invia questi N» e «➕ Altri». Se due cartelle hanno lo stesso nome chiede quale. Funziona anche con **cartelle create dopo**: l'elenco delle cartelle è letto dal disco (aggiornato entro ~10 secondi), non dall'indice. Se nella frase ci sono altre parole o un mese («le bollette di luglio dalla cartella casa») resta la ricerca normale; «tutte le foto della cartella X» invia solo le immagini. Sicurezza: si lavora solo dentro le cartelle configurate nella scheda 📁 File, niente file nascosti.
### Fixed
- «Mandami gas» (verbo + una parola senza parole-chiave note) finiva all'AI. Ora si prova la ricerca e si risponde solo se un file contiene tutte le parole; altrimenti passa all'AI come prima.

## 1.14.5
### Improved
- Ricerca file su Telegram: sotto il nome di ogni file compare un **titolo ricavato dal contenuto** (🏷️ «Busta paga · Luglio 2026», «Bolletta Enel gas · dal … al …», «Visura catastale · 05/07/2026», «Certificazione Unica · redditi 2025»), perché molti file hanno nomi automatici tipo `Doc_1793171838875.pdf` e la stessa intestazione. Se il tipo non è riconosciuto resta l'anteprima di prima. Il titolo compare anche nella didascalia del file inviato. I nomi dei file non vengono modificati.

## 1.14.4
### Fixed
- Ricerca file su Telegram: l'elenco era fisso a 8 risultati e diceva «8 file trovati» anche quando ce n'erano di più. Ora mostra il totale reale, a pagine da 8 con il bottone «➕ Altri», e «Tutti» dichiara che invia i primi 10 (limite invariato). Con più mesi nella frase il comportamento resta quello di prima. Test in `tests/test_file_search_paging.py`.

## 1.14.3
### Improved
- Dieta: «stasera» = cena; su Telegram una frase lunga sul pasto risponde solo se è una domanda («Rosa ha fatto colazione?» va all'AI); anti-doppioni dell'ascolto Alexa ridotto a 10 s.
- Aggiunta suite di test (`tests/`, 54 test): parsing JSON, riconoscimento frasi, risposte, switch Telegram/Alexa, endpoint, persistenza impostazioni, e verifica che il «Salva» generale non cancelli le impostazioni dieta. Esecuzione: `cd src && python -m pytest ../tests -q`.

## 1.14.2
### Fixed
- Dieta su Telegram: dopo «Quale spuntino?» la risposta («pomeriggio», «sera»…) viene capita e non va più all'AI.

## 1.14.1
### Fixed
- Dieta su Telegram: le frasi libere sul pasto («Colazione», «cosa ho per cena domani») rispondono dal piano invece di andare all'AI.

## 1.14.0
### Added
- **🥗 Sezione Dieta** (Impostazioni → tab «🥗 Dieta»). Carichi il piano alimentare in formato **JSON** (si sostituisce quando la dieta cambia; se il file non è valido il piano attuale resta invariato). File d'esempio scaricabile dalla stessa tab (`config_example/dieta_esempio.json`).
- **Risposte vocali Alexa**: «cosa ho per spuntino pomeridiano?», «…spuntino mattina», colazione, pranzo, cena, spuntino serale; anche «domani», «giovedì», «cosa mangio oggi». Risponde sugli speaker selezionati (switch, volume, test come nella spazzatura). La frase viene letta da `last_called_summary` di Alexa Media Player.
- **Switch Notifica Telegram**: se attivo, ogni risposta arriva anche su Telegram.
- Endpoint `POST /api/dieta/ask` (`{"text":"cosa ho per cena"}`) per routine Alexa → `rest_command`, e comando Telegram `/dieta [pasto] [giorno]`.
- Su Telegram anche le frasi libere sul pasto («Colazione», «cosa ho per cena domani») ricevono la risposta dal piano, senza passare dall'AI.
- Nessun file esistente cambia comportamento: le impostazioni dieta stanno nella chiave `dieta` di `person_config.json` e si salvano da sole dalla tab.

## 1.13.1
- Domande sulle buste paga: ferie, malattia e presenze del cedolino sono quelle del MESE PRECEDENTE (es. cedolino di ottobre = dati di settembre). Il bot ora usa quei dati e dice a quale mese si riferiscono, invece di rispondere "dato non trovato".
- Per le buste paga il bot riceve anche la prima pagina con le colonne allineate (etichette sopra ai valori), cosi' abbina meglio FERIE / MALATTIA / PAR alle ore.

## [1.13.0] — 2026-10-28

### Added
- **Domande sul contenuto dei documenti** (tab 📁 File → «Rispondi alle domande sul contenuto dei documenti», spento di default). Il bot risponde leggendo i PDF: «quanto ho preso di stipendio ad agosto?», «quanti giorni di ferie ho fatto a settembre?», «quando devo pagare di gas a novembre?». Sceglie i documenti per mese/anno (nel nome o nel testo) e per argomento (busta paga / bolletta, gas / luce / acqua), rilegge il testo completo, risponde **solo** con ciò che c'è scritto citando il file, e segnala «controlla sul PDF» se un importo della risposta non compare nel testo. Sotto la risposta i bottoni per ricevere i file usati. Se per il mese chiesto non c'è nessun documento lo dice, non risponde a caso. Privacy: il testo dei documenti scelti va al provider AI configurato (`agent/file_qa.py`, `telegram_bot.py`, `main.py`).
- «**busta paga**», «**buste paga**», «**stipendio**» riconosciute come richiesta di file («inviami busta paga di luglio»); se nei PDF si chiama «cedolino»/«retribuzione» la ricerca riprova con i sinonimi.

---

## [1.12.5] — 2026-10-28

### Fixed
- **«Posizione rosa» dava un indirizzo diverso da Home Assistant.** L'indirizzo ora viene preso prima dal sensore *geocoded location* del telefono (quello che vedi in HA), e solo se manca dagli attributi del tracker o dalle coordinate. «posizione <nome>» ora risponde direttamente con i dati reali, senza passare dall'AI che poteva usare ricordi vecchi (`ha_tools.py`, `telegram_bot.py`).

---

## [1.12.4] — 2026-10-28

### Fixed
- **«Mandami la bolletta gas del 8 aprile» veniva schedulata come task alle 08:00** invece di cercare il file: la parola «apri» veniva riconosciuta dentro «apri**le**» (e «set» dentro «set**tembre**», ecc.). Ora le parole-azione e i promemoria si riconoscono solo come parole intere (`telegram_bot.py`).

---

## [1.12.3] — 2026-10-28

### Fixed
- **Allegati email: «Cerca negli ultimi N giorni» accetta fino a 3650 giorni** (prima un valore come 300 veniva ridotto in silenzio a 60). Tutte le email del periodo che corrispondono alle regole vengono scaricate e smistate nelle rispettive cartelle.
- Se in un controllo vengono scaricati più di 3 documenti, su Telegram e Home Assistant arriva **un solo riepilogo** invece di decine di messaggi.

---

## [1.12.2] — 2026-10-28

### Fixed
- **Allegati email: file cancellato = si può riscaricare.** Il controllo anti-duplicati ora vale solo se il file identico è ancora nella cartella. La scheda 📎 Allegati spiega quando un'email corrisponde ma è già stata elaborata e aggiunge **♻️ Dimentica elaborate** per riprocessare le email degli ultimi giorni (non cancella file).

---

## [1.12.1] — 2026-10-28

### Added
- **Allegati email: avviso anche sulla plancia di Home Assistant** (campanella 🔔, `persistent_notification`) con lo stesso riassunto di Telegram. Casella «Avvisa anche sulla plancia di Home Assistant» nella scheda 📎 Allegati (attiva di default).

---

## [1.12.0] — 2026-10-27

### Added
- **📎 Allegati email automatici** (pagina Email → scheda «📎 Allegati»). Con l'interruttore attivo, quando arriva un'email che corrisponde a una regola (es. oggetto «La nuova Bolletta Web LUCE del 12 ottobre 2026 è online», «…GAS…», foto, altri documenti) HomeMind scarica gli allegati nella cartella scelta (es. `/config/ago/enel`, `/config/ago/foto`) e manda un riassunto sul bot: **bolletta** → importo da pagare e scadenza (letti dal PDF e dal testo dell'email; l'AI interviene solo se mancano e i suoi numeri vengono verificati sul testo); **foto** → indirizzo di chi l'ha inviata, messaggio e descrizione AI; **documento** → mittente, oggetto e breve riassunto. Pulsanti «🔍 Prova (non scarica)» e «⬇️ Scarica ora», storico degli ultimi scaricati. Le email non vengono modificate; ogni email è elaborata una sola volta; nessun file sovrascritto né duplicato; eseguibili scartati; cartelle di sistema rifiutate (`agent/email_attachments.py`, `email_manager.py`, `main.py`). Spento di default.

### Fixed
- **Impostazioni (Proximity GPS e altre): «Salva» non scriveva/perdeva dati in `person_config.json`.** Cause trovate e corrette: (1) se HA non elencava il sensore distanza (HA appena riavviato, sensore offline) la riga veniva salvata vuota e **cancellata**; lo stesso per elettrodomestici, sensori energia, liste temperatura/umidità/movimento/persone; (2) righe Proximity in formato breve o a lista sparivano; (3) `stale_check`/`max_age_min` venivano azzerati; (4) campi assenti dal salvataggio (es. `energy_sensors`) venivano cancellati dal file; (5) le liste temperatura/umidità della scheda 🌡️ Clima non venivano mai salvate; (6) un errore nella pagina lasciava «Salvataggio…» muto: ora l'errore è visibile e le righe Proximity incomplete vengono segnalate. Scrittura atomica in UTF-8 con verifica di rilettura e copia `person_config.pre-salvataggio.json`.

---

## [1.11.21] — 2026-10-27

### Added
- **Annuncio vocale Alexa per gli avvisi istantanei Frigate** (tab 📹 Frigate → «🔊 Annuncio vocale Alexa degli avvisi», stesso schema della spazzatura): switch, volume, scelta degli speaker e pulsante **🔊 Test annuncio**. Quando Frigate rileva un oggetto con lo switch attivo, oltre alla foto su Telegram HomeMind pronuncia ad esempio «Attenzione, telecamera balcone ha rilevato un cane» sugli speaker selezionati (persona, cane, gatto, auto, moto, bici, pacco, uccello). Vale per gli stessi oggetti attivati nella pagina, con le stesse pause e la stessa confidenza minima. Si applica subito dopo **Salva**, senza riavvio. La voce parte in parallelo e in background: se Alexa non risponde, la foto su Telegram arriva comunque. Le impostazioni stanno in `frigate.alerts.voice` di `person_config.json`; chi non le usa non vede nessuna differenza (`frigate_alerts.py`, `main.py`).

---

## [1.11.20] — 2026-10-27

### Fixed
- **Ricerca file: «mandami la bolletta di dicembre e gennaio» ora trova i PDF dal loro testo.** Prima si leggeva solo il *primo* mese (gennaio diventava una parola obbligatoria) e il mese si filtrava con la **data di modifica del file**, non col contenuto: una bolletta scaricata a dicembre ma relativa a novembre veniva inviata al posto di quella di dicembre, e quella vera (scaricata dopo) veniva scartata. Ora con uno o più mesi/giorni nella frase il file deve citarli nel nome o **dentro il testo** (es. «dicembre 2025», «01/12/2025») — funziona senza il riconoscimento delle immagini. Con più mesi viene inviato **un file per ciascun mese**; se per un mese non c'è nulla, il bot lo dice ("non ho trovato…") e non invia file a caso. Un file il cui testo parla di *altri* mesi non viene scelto solo perché la sua data coincide. Il nome della cartella configurata (es. `enel`) conta come parola chiave. "maggiore" non viene più letto come il mese "maggio" (`file_search.py`, `telegram_bot.py`).
- **"Non ho trovato il file" spiega il motivo:** cosa è stato cercato (parole, periodo, cartelle), quanti file/PDF leggibili sono indicizzati, se ci sono PDF scansionati senza testo o file ancora in lettura. Nessun file o percorso inventato.
- **Antifurto: la domanda «Casa vuota — Vuoi attivare l'antifurto?» veniva riproposta pochi minuti dopo un NO/timeout**, nonostante «Non verrà più riproposto per questa uscita». Il flag veniva azzerato da qualsiasi «rientro», anche da un rimbalzo del tracker (es. Rosa `not_home → home → not_home`). Ora si azzera solo se qualcuno **resta in casa almeno 10 minuti**; se la casa risulta di nuovo vuota prima, il reset viene annullato (`security_manager.py`). Il log mostra anche chi risulta fuori e con quale stato quando viene fatta la domanda.

### Added
- **`presence_confirm` (opzionale, spento di default):** in `person_config.json` si può indicare una seconda fonte di presenza per chi ha il GPS inaffidabile, es. `"presence_confirm": {"person.rosa": ["device_tracker.rosa_router"]}`. Se quell'entità è `home` (device_tracker) o `on` (binary_sensor) la casa **non** è considerata vuota e non parte né la domanda né l'armamento (`home_model.py`, `security_manager.py`).

---

## [1.11.19] — 2026-10-24

### Fixed
- **"Mandami foto nella cartella foto dove c'è scritto pasquini" finiva all'AI, che inventava:** una richiesta con la sola parola "foto" veniva gestita dalla ricerca solo se trovava qualcosa; altrimenti passava all'AI di riserva, che dichiarava di aver "generato un'immagine e creato uno zip" in un percorso inesistente. Ora sono richieste di file **sicure** le frasi che parlano di cartella/archivio, del nome di una cartella configurata ("in documenti"), o del contenuto ("dove c'è scritto", "che contiene", "che parla di"): il bot risponde sempre, anche con "non ho trovato" e il motivo (es. le immagini non sono ancora state analizzate). Nel prompt dell'AI è stata aggiunta la regola di non inventare file, immagini, zip o percorsi (`telegram_bot.py`).
- **Cartelle una dentro l'altra rielaborate a ogni scansione:** con `archivio` e `archivio/foto` entrambe configurate, i file della cartella interna venivano riassegnati e rianalizzati ogni 30 minuti (sprecando la quota dell'AI per le immagini). Ora una cartella contenuta in un'altra non viene scansionata due volte e il filtro per cartella usa il percorso (`file_search.py`).
- **Il nome di una cartella contava anche come semplice parola** ("foto" in "mandami foto…"): ora conta solo con un riferimento ("nella cartella foto", "in documenti"). Parole come "scritto", "contiene", "dove" non sono più parole chiave della ricerca.

---

## [1.11.18] — 2026-10-23

### Added
#### 🔎 "Mandami il file": ricerca nei file con riconoscimento di data, testo e immagini
Scrivi `mandami la bolletta della luce`, `mandami la foto del 13 febbraio 2026` o `/file contratto affitto`: HomeMind cerca nelle cartelle della scheda 📁 File e ti rimanda il file, anche con nomi come `2026-02-13 07.jpg` o `scan0001.pdf`. Indice SQLite aggiornato in background (`/config/homemind_patches/files_index.db`): data da nome/EXIF/modifica, testo di PDF/Word/txt letto in locale, e — **opzionale e spento di default** — descrizione delle immagini e dei PDF scansionati tramite un provider AI con visione (Gemini, Claude o OpenAI) con tetto giornaliero, pausa di un'ora se la quota è esaurita e priorità ai file più recenti. Servono tutte le parole cercate; se nessun file le contiene mostra i "più simili" senza inviarne uno da solo. Più risultati → elenco con bottoni e "Tutti"; le foto arrivano come foto con il pulsante "Invia come file originale". Sicurezza: solo cartelle configurate, percorso ricontrollato prima dell'invio, file sensibili mai indicizzati, limite 50 MB. Con la ricerca spenta il bot risponde esattamente come prima (`agent/file_search.py` nuovo; `ai_provider.py`: `describe_image`; `file_inbox.py`: sezione `search`; `telegram_bot.py`, `main.py`: scheda, endpoint `/api/files/status` e `/api/files/reindex`).

---

## [1.11.17] — 2026-10-22

### Fixed
- **Provider salvati dalla pagina web ignorati:** la pagina *AI Providers* dice "Salvato! Riavvia per applicare", ma all'avvio, se le Opzioni dell'add-on contenevano almeno un provider, venivano usate **solo** le Opzioni e la configurazione della pagina web era ignorata in silenzio. Da qui il Test della pagina ✅ (prova la chiave scritta nel modulo) contro `/providers` ❌ (prova i provider in uso). Ora i due elenchi vengono **uniti**: prima i provider della pagina web (a parità di nome vince la pagina), poi quelli presenti solo nelle Opzioni come alternativa; il log di avvio mostra la fonte di ognuno (`ai_provider.py: build_ai_provider`, `main.py`).
- **Chiavi con spazi/a-capo:** le API key incollate con spazi o a-capo finali ora vengono ripulite (causa tipica di "API key non valida").
- **Modelli Gemini "preview" spenti:** `gemini-3.1-flash-lite-preview` (spento il 25/5/2026) e `gemini-2.5-flash-lite-preview-09-2025` vengono sostituiti da `gemini-3.1-flash-lite`. Un modello spento può non dare un 404 ma un timeout, per cui la ricerca di alternative "su 404" da sola non bastava.

### Changed
- Il test del bot (`/providers`) mostra la **fonte** di ogni provider ("pagina web" / "Opzioni add-on"), indica dove correggere la chiave e spiega meglio il timeout.
- La pagina *AI Providers* mostra un avviso se le Opzioni contengono altri provider, la fonte accanto ai provider attivi e include **Cerebras** (prima gestibile solo dalle Opzioni). Tolti dalle schede i numeri di quota non verificati.

---

## [1.11.16] — 2026-10-21

### Fixed
- **Provider AI con modelli spenti → "Modalità offline":** i modelli predefiniti erano stati ritirati dai provider (Gemini `gemini-2.0-flash` il 1/6/2026, Groq `llama-3.3-70b-versatile` il 16/8/2026, Cerebras `llama3.1-8b` il 27/5/2026), quindi tutte le chiamate fallivano con 404 `model_not_found`. Aggiornati i predefiniti (`gemini-3.5-flash`, `openai/gpt-oss-120b`, `gpt-oss-120b`, `claude-haiku-5-5`) in `ai_provider.py`, `config.yaml`, `run.sh`, `run.standalone.sh`, `docker-compose.yml` e nel catalogo della pagina web. Una configurazione salvata con un vecchio modello **spento** viene sostituita automaticamente (con avviso nel log); se un modello risponde "non esiste" si provano le alternative dello stesso provider prima di passare al successivo. Per i modelli gpt-oss (che "ragionano") si usa `reasoning_effort=low` e `max_completion_tokens`. Il log dei fallimenti ora riporta il modello (`AI ❌ Cerebras (gpt-oss-120b) [modello] …`).
- **Parser offline — luce sbagliata:** `accendi luce bagno` accendeva "Luce scala" perché il parser riconosceva parole generiche come "luce"; stesso difetto per tapparelle (apriva la prima a caso) e interruttori. Ora conta solo il nome distintivo, e se la stanza non si trova non indovina. Corretti anche: `"on "`/`"su"` cercati dentro altre parole ("con la cucina" accendeva la luce, "consuma" contava come "su"), le **domande** ("com'è la luce del salotto?") eseguite come comandi, e gli interruttori mai raggiunti dai comandi "accendi luce …" (molte luci del bagno sono `switch`) (`agent/local_parser.py`).

---

## [1.11.15] — 2026-10-21

### Changed
- **Salva file dalla chat — più chiaro e più tollerante:** capisce gli errori di battitura nel nome della cartella (`invia in documeti`); se la funzione è spenta o senza cartelle e scrivi una didascalia di salvataggio ("invia nella cartella", "salva in documenti"), il bot spiega cosa attivare nella pagina web invece di mostrare il suggerimento sull'email; nuove righe di log `FileInbox: configurazione letta…` e `FileInbox: file …` per vedere cosa è stato deciso. Con didascalie non di salvataggio il comportamento a funzione spenta resta quello di sempre (`agent/file_inbox.py`, `telegram_bot.py`).

---

## [1.11.14] — 2026-10-20

### Added
#### 📁 Salva file dalla chat → cartella
Mandi un file al bot con la didascalia `invia nella cartella` (o `salva in <nome cartella>`): HomeMind lo salva nella cartella scelta e **cancella il messaggio da Telegram**. Le cartelle (nome, percorso, predefinita) e l'opzione "cancella dopo il salvataggio" si impostano nella nuova scheda **📁 File** della pagina web; valgono subito dopo Salva. Senza didascalia il bot mostra i bottoni con le cartelle; gli album (più file insieme) vanno nella stessa cartella con un solo riepilogo. Sicurezza: cartelle definibili solo dalla pagina web, mai sovrascrive (aggiunge ` (1)`), nome file ripulito, cartelle di sistema rifiutate, messaggio cancellato solo a salvataggio riuscito, limite 20 MB (limite Telegram per i bot). Con la funzione spenta (default) il bot risponde esattamente come prima (`agent/file_inbox.py` nuovo; `telegram_bot.py`, `main.py`).

### Changed
- `config.yaml`: l'add-on ora mappa anche `/share` e `/media` (`share:rw`, `media:rw`), oltre a `/config`, così si può salvare anche lì. Dopo l'aggiornamento usa **Aggiorna/Ricostruisci**.

---

## [1.11.13] — 2026-10-20

### Fixed
- **Impostazioni cambiate da chat non applicate fino al riavvio:** dopo una modifica fatta parlando con il bot (ConfigEditor), il ricaricamento della configurazione chiamava un metodo inesistente (`_load_person_config`) e l'errore veniva ignorato in silenzio; il file era salvato ma il modello in memoria restava vecchio. Ora chiama `_load_config` e la modifica vale subito (`main.py`).

### Docs
- README: FAQ "non ricevo più la notifica quando esco" con la tabella dei comportamenti all'uscita e i messaggi di log che spiegano un eventuale silenzio.

---

## [1.11.12] — 2026-10-19

### Fixed
- **Foto Frigate su allarme scartate subito dopo l'avvio della macchina:** il controllo anti-duplicati (60 s) partiva da `0` e usava il tempo di accensione dell'host, quindi nei primi 60 secondi dopo il boot le foto venivano saltate come se fossero appena state inviate. Ora la prima foto parte sempre; la pausa di 60 s tra due invii resta (`agent/security_manager.py`).
- **Avvisi Frigate duplicati dopo un'ora:** se dopo un avviso non arrivavano altri eventi, passata un'ora HomeMind dimenticava l'evento già notificato mentre Frigate lo restituiva ancora nella finestra di ricerca, e rimandava la stessa foto come se fosse nuova (es. avviso delle 7:49 ripetuto alle 8:48). Ora un evento viene dimenticato solo quando Frigate non può più restituirlo (`agent/frigate_alerts.py`).

---

## [1.11.11] — 2026-10-18

### Added

#### 🎯 Confidenza minima per gli avvisi Frigate (meno falsi allarmi)
Nel tab 📹 Frigate, accanto agli switch, nuovo campo **Confidenza minima (%)** (0 = nessun filtro, come prima). Al primo avvistamento Frigate dà lo score più basso (es. ~71%): con il filtro attivo l'avviso resta in attesa e parte solo se lo score sale oltre la soglia; se l'evento finisce (o passano 60 s) sotto soglia viene scartato e la pausa tra avvisi viene rilasciata. L'avviso mostra lo score aggiornato. Il log di avvio riporta ora `build 1.11.11` per verificare quale versione è in esecuzione (`agent/frigate_alerts.py`, `agent/frigate_client.py: get_event`, `main.py`: campo UI + `getFgConfig`).

### Fixed
- **"Dove era X il 5 ottobre":** il gestore generico delle soste ignorava le date e rispondeva con le *ultime 24 ore* senza avvisare. Ora legge `5 ottobre`, `5/10`, `05-10-2026` e `ieri` (giorno esatto 00:00–24:00, prima "ieri" mostrava 48 ore), mostra le soste di quel giorno in ordine cronologico e, se Home Assistant non ha più i dati, lo dice chiaramente. Nuovo: `tutti i posti` / `anche le brevi` abbassa la soglia delle soste a 3 minuti (`location_tracker.py`: parametro opzionale `day`, etichetta `period_label`).
- **Tracciamento posizioni:** il "rinfresco" delle soste GPS prima di rispondere a domande tipo *"dove è stato X il 5 ottobre"* non partiva mai (`now_local` non importato; l'errore veniva nascosto a livello debug). Ora l'import è presente.
- **`ha_terminal.py`:** mancava `import asyncio` (un errore HTTP/timeout nel tool API produceva un `NameError` invece del messaggio) e `_tools` non era importato nei canali `ping` e `portscan`.
- **Docker:** aggiunto `.env.example` (era citato nelle istruzioni ma non esisteva); corretto l'URL in `INSTALL_DOCKER.md`.

### Docs
- Nuovo `README.md` completo (Frigate, targhe, avvisi per oggetto, antifurto GPS, tracciamento, email, aggiornamento). Il vecchio file si chiamava `README .md` (con uno spazio) e non veniva letto da GitHub/Home Assistant.

---

## [1.11.10] — 2026-10-17

### Added

#### 🚗 Targhe rilevate da Frigate (LPR) interrogabili da Telegram
Se Frigate è abilitato, il bot risponde direttamente (senza AI) a domande sulle targhe: `che targhe hai rilevato?`, `targhe ieri`, `targhe garage oggi`, `targhe ultime 6 ore`, `targhe ultimi 3 giorni`, `hai visto la targa AB123CD?`. Mostra targhe raggruppate con numero di passaggi, camera, orari, confidenza e nome (se targa nota in Frigate), più la foto dell'ultimo rilevamento. Nessuna nuova configurazione: usa `host`/`port`/`cameras` già presenti nella sezione `frigate`. Richiede Frigate ≥ 0.16 con LPR attivo. Il comportamento antifurto/snapshot esistente è invariato (`frigate_client.py`: `get_recent_plates`, `get_event_snapshot`; `telegram_bot.py`: `_handle_plates_query`).

#### 🕐 Periodi e categorie più flessibili nelle richieste Frigate
Targhe e rilevamenti ora capiscono `ultima ora`, `ultimi 30 minuti`, `mezz'ora`, `quarto d'ora`, `ultime due ore`, oltre a ore/giorni/oggi/ieri/settimana/mese (prima "ultima ora" ricadeva sulle 24 ore). Nuova categoria `animali` = cani + gatti + uccelli. Basta anche una frase breve come `persone ultima ora` o `animali`; auto/moto/bici richiedono parole come "rilevate/visto" per non confondersi con altri comandi (es. ricarica auto).

#### 🔔 Avvisi istantanei Frigate per oggetto (switch nella pagina web)
Nel tab **📹 Frigate** della pagina web ci sono switch per tipo di oggetto (persone, cani, gatti, auto, moto, bici, pacchi, uccelli): se attivo, appena Frigate rileva quell'oggetto la foto arriva subito su Telegram, indipendentemente dall'allarme. Opzione "pausa tra due avvisi" (default 60 s, 0 = ogni rilevamento) per evitare raffiche sulla stessa camera. Gli switch valgono subito dopo il salvataggio, senza riavvio. Tutti spenti (default) = modulo inattivo, nessuna richiesta a Frigate. All'avvio gli eventi già esistenti non generano avvisi. Il salvataggio non cancella gli avvisi se la pagina era aperta con una versione precedente (`agent/frigate_alerts.py` nuovo; `main.py`: UI, `getFgConfig`, avvio watcher).

#### 🎥 Rilevamenti Frigate di persone, cani, gatti, auto, moto, bici, pacchi
Stesso meccanismo delle targhe: `hai visto persone oggi?`, `che cani hai rilevato?`, `cosa hai rilevato ieri`, `chi è passato dal garage`, `gatti ultimi 3 giorni`. Riepilogo per tipo e camera, ultimi 10 rilevamenti con orario/confidenza (e nome se Frigate ha riconosciuto un volto), più le foto di tutti i rilevamenti con snapshot, inviate in album da 10 (massimo 40 foto per richiesta, con avviso se ce ne sono di più). Se una camera ha lo stesso nome di un oggetto (es. camera `auto`), conta come camera solo se introdotta da `camera/dalla/sul/nel…`. Le frasi di presenza in casa (`chi è a casa`, `persone presenti`) e le richieste di modifica config non vengono intercettate e proseguono verso l'AI come prima (`frigate_client.py`: `get_recent_detections`; `telegram_bot.py`: `_handle_detection_query`).

---

## [1.11.9] — 2026-05-01

### Fixed

#### 🛠️ /fai non veniva passato all'agente quando conteneva pattern temporali nel testo
I comandi `/fai` con orari nel testo (es. nei nomi delle automazioni tra virgolette) venivano intercettati dallo scheduler invece di essere passati all'agente. Aggiunto guard early-return su comandi slash espliciti, rimozione preventiva di stringhe quotate prima del matching, e pattern di rilevamento delle richieste di edit configurazione (`telegram_bot.py`).

#### 📝 ai_edit_file riscrittura completa con modalità patch sicura
Riscritto `ai_edit_file` per usare ESCLUSIVAMENTE patch JSON `{old, new}` invece di chiedere il file intero all'AI. Vantaggi:
- Funziona con file grandi senza sforare context window dei provider AI
- Impossibile inventare contenuto su file vuoti (GUARD anti-invenzione)
- Verifica nomi citati esistano nel file prima di modificare
- Backup automatici centralizzati in `/config/homemind_patches/backups/`
- Anti-drift: rifiuta patch che cambiano la dimensione del file di > 30%
- Estrazione contestuale TF-IDF + scoring per finestre rilevanti

#### 📂 _safe_path normalizza il prefisso config/ senza slash
`_safe_path` ora tratta `config/X` (senza slash iniziale) come `/config/X`, evitando di creare sottocartelle indesiderate `/config/config/`. Aggiunto sanity check anti-`/config/config/` in `ai_edit_file` (`tools_system.py`, `agentic_executor.py`).

#### 👥 Aggiunto tool ha_list_users
Sostituisce il pattern errato `ha_call_service(domain="person", service="list_users")` (servizio non esistente in HA) con un tool dedicato che legge direttamente le entità `person.*` via REST. Accetta 6 alias (`ha_list_users`, `ha_list_persons`, `list_users`, `list_persons`, `ha_users`, `ha_persons`) (`agentic_executor.py`).

#### ✅ finish ora gestito anche dentro execute_tool
Il tool `finish` era documentato nel prompt ma gestito solo nel loop esterno: se l'AI lo chiamava da dentro un plan/parallel_steps, riceveva "Tool sconosciuto". Ora ritorna successo con il messaggio anche dal dispatcher (`agentic_executor.py`).

#### 🔀 /ssh routing deterministico file ops → container
`/ssh elimina prova` (e simili) eseguivano `rm -rf prova` sull'host invece che nel container, dove vivono i file in `/config`. Aggiunto pre-routing deterministico: richieste con verbi file-op + path utente sono ora forzate a `container_shell` senza coinvolgere l'AI. Aggiornato anche il prompt di `run_natural` con esempi chiari host vs container (`ha_terminal.py`).

#### 📖 Help /ssh — sezioni gestione addon e Home Assistant
Aggiunte due nuove sezioni nel `/ssh help`: comandi per gestione addon (`ha addons stop/start/restart/info/logs`) e gestione HA core (`ha core restart/stop/check`), con nota sullo slug senza spazi (`telegram_bot.py`).

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
