# La pipeline

Trasforma i file dell'orologio in qualcosa che un allenatore possa leggere.

Un `.fit` è un formato binario con migliaia di campioni al secondo: illeggibile
per una persona e ingestibile per un modello linguistico. La pipeline lo riduce
a un paio di chili di testo per attività — i totali, il profilo chilometro per
chilometro, i lap — e poi raggruppa tutto per trimestre e per settimana.

```
Garmin  →  raw/activities/*.fit  →  training_data/activities/*.md
                                 →  trimestrali, manifest, summary, weekly
```

## Prima volta

```bash
./pipeline/setup_venv.sh
```

Crea l'ambiente Python e installa le due dipendenze. Serve **Python 3.9 o
superiore**; lo script controlla e si ferma con un messaggio chiaro se la
versione non basta. Per usare un interprete diverso da `python3`:

```bash
PYTHON=/percorso/di/python3.12 ./pipeline/setup_venv.sh
```

Usa sempre l'interprete dell'ambiente, in forma esplicita:

```bash
pipeline/.venv/bin/python pipeline/run_pipeline.py <atleta>
```

Non è pedanteria: la conversione lancia un processo per file usando lo stesso
Python con cui l'hai avviata. Con un `python3` di sistema mancano le dipendenze
e non converte niente.

## Il comando

```bash
PY=pipeline/.venv/bin/python

# hai appena copiato dal browser i due comandi per Garmin:
# aggiorna le credenziali, scarica il nuovo, converte, riassume
$PY pipeline/run_pipeline.py andrea --curl-from-clipboard

# credenziali ancora valide
$PY pipeline/run_pipeline.py andrea --download

# i .fit sono già sul disco
$PY pipeline/run_pipeline.py andrea

# ricostruisce tutti i riassunti da zero
$PY pipeline/run_pipeline.py andrea --recreate
```

Alla fine controlla che i `.fit` e i riassunti siano allineati: un download
interrotto a metà lascerebbe uno storico incompleto senza dirlo a nessuno.

Codici di uscita: `0` fatto, `1` errore, `2` niente di nuovo da scaricare,
`4` nessun `.fit` da convertire, `5` alcune attività non convertite.

## Scaricare da Garmin

Garmin non offre un'API aperta per i propri dati. La pipeline aggira il problema
rigiocando due richieste copiate dal browser: una per l'elenco delle attività,
una per scaricarne una.

Si esportano così, con la sessione Garmin aperta:

1. apri le tue Attività su connect.garmin.com
2. apri gli strumenti per sviluppatori (F12) → scheda **Network**
3. ricarica: trova la richiesta a `activitylist-service/...` →
   tasto destro → **Copy as cURL**
4. scarica un'attività in `.fit`: trova la richiesta a
   `download-service/files/activity/...` → **Copy as cURL**
5. copiali entrambi e lancia con `--curl-from-clipboard`

Lo script riconosce da solo quale è quale, anche se li incolli al contrario.

Finiscono in `pipeline/curl_<atleta>.txt`, che **contiene le credenziali della
tua sessione**: è escluso dal controllo di versione e non va passato a nessuno.
Il formato è in `curl.txt.example`.

Scadono nel giro di ore. Quando il download si ferma, si riesportano e si
rilancia: le attività già scaricate vengono saltate.

### Un file per atleta, e un controllo su chi è

I cookie appartengono a un **account Garmin**, non al repository. Con due atleti
su due account diversi serve un file per ciascuno, altrimenti ogni sync
sovrascrive la sessione dell'altro — ed è il problema minore. Quello grosso è
che dal file non si capisce di chi sia la sessione dentro, quindi
`run_pipeline.py giorgia` con i cookie di Andrea scarica le attività di Andrea
in `athletes/giorgia/`, e l'unico modo di accorgersene sono le date.

Per questo il downloader legge il cookie `GARMIN-SSO-CUST-GUID`, che identifica
l'account, e lo confronta con quello registrato in
`athletes/<atleta>/.garmin_guid`. La prima volta lo registra, dopo lo verifica:

```
❌ Il cURL e' di un altro account Garmin. Sembra la sessione di 'andrea'.
   atteso per 'giorgia': 76587ed1-...
   trovato nel cURL:     5d1ee7dc-...
```

Se l'account di un atleta cambia davvero, si cancella il suo `.garmin_guid` e si
rilancia. Se il cURL non contiene quel cookie il controllo viene saltato con un
avviso: è una verifica in più, non un requisito del formato.

Un `pipeline/curl.txt` preesistente continua a funzionare come ripiego per
qualunque atleta, finché non esiste il file suo; il primo
`--curl-from-clipboard` scrive su `curl_<atleta>.txt` e la questione si chiude.

## Cosa finisce in un riassunto

Oltre a distanza, tempo, frequenza cardiaca e dislivello:

| Campo | Quando c'è | A cosa serve |
|-------|------------|--------------|
| Terreno | `sub_sport` dichiarato | Distingue trail, tapis e strada. Sul tapis il passo non è attendibile, e l'allenatore deve saperlo |
| Potenza (media, normalizzata, massima) | Orologi che la misurano | In salita il passo non dice niente, la potenza sì |
| Cadenza media e massima | Quasi sempre | Serve anche a riconoscere un cardio da polso che legge i passi invece del battito |
| Escursione altimetrica | Con altimetro | Quota minima e massima |
| Tempo per banda di frequenza | Con cardio | La materia prima della distribuzione per zona |
| Passo corretto per la pendenza | Con quota e distanza | Il passo equivalente in piano |
| Decoupling | Sedute piatte oltre 20 min | Quanto è salito il costo cardiaco a parità di andatura |

### Il passo corretto per la pendenza

7:49/km con 775 metri di dislivello e 7:49/km in pianura sono due sforzi
diversi. Il passo corretto è quello che, corso in piano, costerebbe la stessa
energia — 6:32/km, nel caso di sopra. È quello che rende confrontabile un lungo
in montagna con una seduta su strada.

Usa la curva di **Minetti et al. 2002**, che misura il costo energetico della
corsa in funzione della pendenza: pubblicata e misurata in laboratorio, non
tarata a occhio. Il fattore vale 1,66 al +10% e 0,60 al −10%, con il minimo
attorno al −10% — correre in leggera discesa costa meno che in piano.

Su terreno piatto coincide col passo reale entro un paio di secondi al
chilometro, che è il controllo che conta. La riga compare solo quando i due
valori differiscono in modo apprezzabile.

### Il decoupling, e perché solo sul piatto

Il decoupling confronta il rapporto andatura/frequenza fra prima e seconda metà
di una seduta: se nella seconda la stessa andatura costa più battiti, la seduta
è andata oltre il ritmo sostenibile.

Su percorso vario il confronto non regge — la prima metà è in salita e la
seconda in discesa, e il numero che esce segue la pendenza invece della fatica.
Vale anche correggendo il passo per la pendenza, e anche usando la potenza al
posto del passo: entrambe le correzioni sono a loro volta modelli, e si rompono
dove il terreno è estremo.

Quindi viene prodotto solo sotto i 10 metri di dislivello per chilometro. Per
misurare la tenuta in salita serve una seduta costruita apposta — la stessa
salita ripetuta a inizio e a fine allenamento — non un calcolo su una seduta
qualsiasi.

### Tempo in zona

Ogni riassunto riporta i secondi passati in ciascuna banda di frequenza da
10 bpm:

```
- **Tempo per banda FC (bpm):** 130-140 6:58 · 140-150 8:24 · 150-160 18:09
```

Le bande sono indipendenti dall'atleta. La traduzione in zone Z1-Z5 avviene nel
riepilogo settimanale, che legge la frequenza massima dal profilo: così
correggere quel numero non obbliga a riconvertire tutto lo storico. Se il
profilo non la dichiara, il file lo scrive invece di inventarsi un riferimento.

Il tempo è pesato sugli intervalli fra campioni, non sul loro numero: alcuni
orologi registrano ogni secondo, altri saltano a intervalli variabili, e
contare i campioni darebbe ai secondi pesi diversi.

Le soglie delle zone stanno in `profile_stats.py`, costante `ZONE`: Z1 <72%,
Z2 72-82%, Z3 82-87%, Z4 87-92%, Z5 >92% della frequenza massima. È una
convenzione fra le tante, scritta lì perché sia una scelta modificabile.

### Il dislivello

Il totale dell'attività e quello dei singoli lap li dichiara l'orologio, che li
calcola col proprio barometro: sono i valori migliori disponibili e vengono usati
così come sono.

Gli **split al chilometro** sono un caso a parte: il file non contiene un
dislivello per chilometro, quindi vanno ricalcolati dai campioni di quota. La
stima è buona — confrontata coi lap dell'orologio su percorsi con giro
automatico ogni chilometro, l'errore mediano è sotto i tre metri — e viene poi
riscalata perché la somma torni col totale dell'attività.

Quando nemmeno il totale è dichiarato (succede al chiuso: tapis, palestra,
piscina) il riassunto lo etichetta come stimato, così chi legge sa cosa ha in
mano.

## I file

| File | Cosa fa |
|------|---------|
| `run_pipeline.py` | Il comando: credenziali → scarico → conversione → riassunti |
| `paths.py` | Dove stanno le cose. Unico posto in cui è scritta la convenzione dei percorsi |
| `download_garmin.py` | Scarica i `.fit` mancanti |
| `fit_to_markdown.py` | Converte una singola attività |
| `fit_reader.py` | Legge il `.fit`. Solo estrazione |
| `activity_metrics.py` | I calcoli: dislivello, pendenza, zone, split. Funzioni pure |
| `activity_markdown.py` | La resa in Markdown |
| `batch_convert.py` | Converte in parallelo tutte le attività di un atleta |
| `quarter_split.py` | Raggruppa per trimestre, rigenera manifest e summary |
| `weekly_rollup.py` | Il quadro settimana per settimana |
| `profile_stats.py` | La fotografia di un atleta: volumi, sport, estremi |
| `profile_check.py` | Verifica che il profilo abbia i campi che servono |
| `week_check.py` | Verifica che un piano settimanale non sia rotto |
| `tests/` | I test |

Il converter è diviso lungo la linea **leggi / calcola / scrivi**. La ragione è
pratica: i calcoli isolati dall'I/O si verificano con tracce costruite a mano,
ed è così che i test controllano per esempio che su terreno piatto la correzione
di pendenza non corregga niente.

## Test

```bash
pipeline/.venv/bin/python -m pytest pipeline/tests -q
```

Sessanta test su un'attività reale, meno di tre secondi. Coprono soprattutto il
**parsing**, che è il punto in cui gli errori passano inosservati: un campo che
non viene letto non produce un errore, produce uno zero che finisce in un file
e sembra un dato.

Lanciali dopo ogni modifica al converter o allo splitter.

## Cosa non fa

I dati di salute — frequenza a riposo, HRV, sonno, stress — non passano da qui.
Garmin li espone per altre vie, ma non attraverso quella che usiamo. Finché non
ci passano, o si scrivono a mano nel profilo o l'allenatore lavora senza e lo
dichiara.
