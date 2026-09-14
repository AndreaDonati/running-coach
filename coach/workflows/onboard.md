# Workflow: onboard

Porta una persona da "ho appena ricevuto questa cartella" a "il coach mi ha
appena scritto la prima settimana", facendo le domande al posto suo.

**Input**: niente, o il nome dell'atleta da creare.
**Output**: un atleta funzionante, con profilo compilato e dati caricati.

## Come condurla

Sei tu a guidare. La persona non sa cosa sia `training_data/`, non deve saperlo,
e non deve aprire un file per capire cosa scriverci.

Tre regole che valgono per tutta la procedura:

1. **Una domanda alla volta.** Non elencare sei domande in un messaggio.
2. **Non chiedere cio' che puoi calcolare.** Volume settimanale, livello, punti
   di forza, sport praticati, periodo coperto dai dati: si ricavano dalle
   attivita'. Chiedere all'utente di stimarli a mano produce risposte peggiori
   dei dati che hai gia'.
3. **Dopo ogni passo, verifica e dillo.** "Fatto" senza un numero non serve:
   *"convertite 293 attivita', dal 21/03/2023 al 13/09/2026"* si'.

Se un passo fallisce, fermati li' e risolvi. Non proseguire con dati a meta':
un profilo mezzo vuoto produce piani inventati, che e' il modo peggiore in cui
questo sistema puo' rompersi.

---

## Passo 0 — Ambiente

Prima di tutto, verifica che ci siano le condizioni. Se manca una di queste,
dillo subito invece di scoprirlo al passo 3:

- **un Garmin**: il sistema legge solo `.fit`. Strava, Polar e Coros no.
- **Python 3.9 o superiore**: `setup_venv.sh` lo controlla e si ferma se manca.
- **macOS o Linux** (su Windows serve WSL).

```bash
./pipeline/setup_venv.sh
pipeline/.venv/bin/python -m pytest pipeline/tests -q
```

I test girano in meno di un secondo e confermano che la pipeline funziona su
questa macchina prima di metterci dentro dati veri. Se falliscono, il problema
e' l'installazione, non i dati: risolvi prima.

## Passo 1 — Chi sei

Chiedi il **nome**. Da li' ricavi l'identificativo della cartella: minuscolo,
senza spazi né accenti (`Giorgia Fondrini` → `giorgia`). Proponilo e conferma.

```bash
cp -R athletes/_template athletes/<id>
```

## Passo 2 — Dove sono i dati

Chiedi: *"Hai già i file `.fit` delle tue attività sul computer, o li
scarichiamo da Garmin adesso?"*

**Li ha già** → falli copiare in `athletes/<id>/raw/activities/` e vai al
passo 3.

**Da scaricare** → esegui `coach/workflows/sync-run.md`, che gestisce i comandi
cURL. Avvisa che la prima volta scarica tutto lo storico e può volerci
qualche minuto.

**Non ha un Garmin** → il sistema oggi legge solo `.fit`. Strava e Polar non
sono supportati. Dillo subito invece di farglielo scoprire dopo: puo' comunque
usare il coach compilando il profilo a mano, ma senza dati il coaching e'
generico e va detto.

## Passo 3 — Genera i dati di allenamento

```bash
pipeline/.venv/bin/python pipeline/run_pipeline.py <id>
```

**Verifica prima di andare avanti:**

```bash
ls athletes/<id>/raw/activities/*.fit | wc -l
ls athletes/<id>/training_data/activities/*.md | wc -l
```

I due numeri devono coincidere. Se non coincidono, guarda
`pipeline/logs/<id>-convert.log`: qualche `.fit` è corrotto o troncato. Di'
quanti e vai avanti — non è bloccante — ma dillo.

Poi leggi `athletes/<id>/training_data/manifest.md` e riporta all'utente:
quante attività, che periodo coprono, quanti trimestri. È il primo momento in
cui vede che il sistema ha capito qualcosa di lui.

## Passo 4 — La fotografia iniziale

```bash
pipeline/.venv/bin/python pipeline/profile_stats.py <id>
```

Restituisce quello che si ricava dai dati: volume delle ultime 4, 12 e 52
settimane, sedute a settimana, ripartizione per sport e terreno, corsa più
lunga, dislivello, e la disponibilità delle metriche avanzate (potenza,
decoupling) su questo orologio.

Riportalo all'utente in forma discorsiva e **chiedi se si riconosce**. È il
controllo più efficace che i dati siano quelli giusti: se dici "circa 30 km a
settimana" e la persona ne fa 60, qualcosa non ha funzionato nell'import.

Con questi numeri compili da solo, in `profile.md`:

- Sport principali, dati disponibili da, volume settimanale tipico, trend
- Livello e focus (argomentati coi numeri, non a sensazione)
- Punti di forza e da migliorare — **con l'evidenza accanto**: non "buona
  resistenza" ma "più uscite sopra le 2h con 700-900 m D+ nel Q4 2025"
- Modello di orologio (chiediglielo) e attendibilità della FC da polso — vedi
  sotto

### Il cardio da polso è attendibile?

Non è una domanda da manuale: se il sensore ottico sbaglia, ogni prescrizione
basata sulla frequenza cardiaca è falsa, e la persona si allena più forte di
quanto crede per mesi.

**Non è deducibile dai dati** — ci ho provato, vedi la nota in
`pipeline/profile_stats.py`: sulle sedute a bassa intensità l'atleta con
*cadence lock* confermato a mano esce indistinguibile da quello col sensore
buono. Quindi si chiede, e si fa verificare con un test che richiede mezzo
minuto:

> Alla prossima corsa, quando sei a ritmo sostenuto, guarda la frequenza sul
> quadrante. Poi **ferma il polso** — braccio disteso e immobile per una
> ventina di secondi, continuando a correre — e riguarda. Se il numero scende
> di 15-20 battiti, stava leggendo la cadenza dei passi: cardio da polso
> inaffidabile. Se resta lì, sta leggendo il battito vero.

Intanto chiedi il **modello di orologio** e se ha mai notato letture strane.

Scrivi nel profilo l'esito con la sua evidenza, e le conseguenze:

- **Inaffidabile** → governare le sedute a **passo e RPE**, non a fascia
  cardiaca. Le medie FC storiche vanno lette al ribasso. Una fascia toracica
  risolve.
- **Attendibile** → si possono usare i tetti di FC nelle prescrizioni.
- **Non ancora verificato** → trattalo come inaffidabile finché il test non
  chiarisce, e ricordaglielo. È l'ipotesi prudente: sbagliare in questa
  direzione costa un allenamento un po' troppo facile, sbagliare nell'altra
  costa mesi passati a correre più forte di quanto si crede.

## Passo 5 — L'obiettivo

Questa è l'unica parte che i dati non possono dirti, ed è quella da cui dipende
tutto il resto.

Chiedi, una per volta:

1. **Che gara hai in programma?** Nome, e se non ce l'ha ancora: *"anche solo
   'una mezza in primavera' va bene, poi la precisiamo"*.
2. **Quando?** → **è il campo più importante del sistema.** Da qui il coach
   calcola le settimane mancanti e ne deriva la fase (Base / Build / Peak /
   Taper). Senza, ogni piano settimanale è campato in aria. Se non c'è una data,
   dillo esplicitamente e proponi un orizzonte convenzionale a 16 settimane,
   segnandolo come provvisorio nel profilo.
3. **Quanto è lunga, e quanto dislivello?** Per un trail il D+ conta quanto la
   distanza.
4. **Che obiettivo ti dai?** Accetta "finirla": è un obiettivo legittimo e
   cambia il piano. Se dà un tempo, verifica con i dati se è plausibile e
   **dillo subito se non lo è** — meglio adesso che alla settimana 12.
5. **Altre gare nel mezzo?** Vanno in obiettivi secondari, con la nota che non
   devono compromettere la preparazione principale.

## Passo 6 — Vincoli

Quattro domande, poi basta:

1. **Quanti giorni a settimana puoi allenarti davvero?** Insisti su *davvero*:
   un piano su 6 giorni per chi ne ha 4 fallisce alla seconda settimana.
2. **Ci sono giorni fissi?** (il lungo la domenica, palestra il martedì)
3. **Infortuni passati o punti fragili da tenere d'occhio?**
4. **Che terreno hai a disposizione?** (strada, trail, pista, tapis)

## Passo 7 — Quello che il sistema non sa

Dillo esplicitamente, non lasciarlo scoprire:

> HRV, sonno e stress non vengono scaricati da Garmin: `health_status.md` non
> esiste. Se hai questi numeri sotto mano posso metterli nel profilo, altrimenti
> lavoro su passo, frequenza cardiaca e sensazione, e te lo dico ogni volta che
> un consiglio ne risentirebbe.

Se li ha, chiedi FC massima e FC a riposo: servono per le zone e sono gli unici
due che cambiano davvero le prescrizioni.

## Passo 8 — Chiudi il profilo e verifica

Scrivi `athletes/<id>/profile.md` completo, poi verifica:

```bash
pipeline/.venv/bin/python pipeline/profile_check.py <id>
```

Blocca su una cosa sola — l'assenza di una data di gara futura — perche' e'
l'unica che rende arbitrario ogni piano. Segnala come avvisi i campi lasciati
al modello, l'attendibilita' del cardio non dichiarata e i giorni disponibili
non detti: il coach funziona lo stesso, ma con meno contesto.

Risolvi i bloccanti prima di andare avanti. Gli avvisi: quelli che riguardano
dati che l'atleta ha (giorni disponibili, infortuni, FC a riposo) vanno
chiusi adesso, quelli su HRV e sonno resteranno aperti finche' la pipeline non
li produrra' — scrivici `n.d.` invece di lasciare le parentesi quadre.

Mostra all'utente il profilo finito e chiedi conferma. È suo, deve riconoscersi.

## Passo 9 — Il primo giro

Non lasciarlo con un profilo e basta. Fai due cose:

1. **Una valutazione della forma** (tipo 1 in `coach/coach.md`): coi suoi numeri
   veri. È la dimostrazione che il sistema funziona.
2. **La prima settimana**: esegui `coach/workflows/start-week.md`.

Poi spiega in quattro righe il giro settimanale, senza rimandarlo a un README:

> Da qui in poi: `/sync-run <id>` dopo che hai corso — scarica e registra;
> `/close-week <id>` la domenica — consuntivo e direzione;
> `/start-week <id>` il lunedì — la settimana nuova;
> `/plan-workout <id>: ...` quando vuoi una seduta dettagliata.

## Se l'atleta esiste già

Se `athletes/<id>/` c'è, non sovrascrivere. Chiedi se vuole aggiornare il
profilo esistente (allora salta ai passi 4-8 rileggendo quello che c'è già) o
creare un atleta diverso con un altro identificativo.
