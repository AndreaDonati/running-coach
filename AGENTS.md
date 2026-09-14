# Convenzioni del repository

Per assistenti AI e per chiunque ci metta mano. Per capire cos'e' il progetto,
parti da `README.md`.

## Mappa

| Cartella | Cosa contiene | Si modifica a mano? |
|----------|---------------|---------------------|
| `athletes/<a>/profile.md` | Obiettivi, vincoli, forma, note sul device | **Si'** — e' l'unico input umano |
| `athletes/<a>/raw/` | `.fit` scaricati da Garmin | No — arriva dal download |
| `athletes/<a>/training_data/` | Riassunti, file trimestrali, manifest, summary | **No** — output della pipeline |
| `athletes/<a>/plans/` | Settimane, piani gara, archivio | Si' — lo scrive il coach |
| `coach/` | Istruzioni dell'allenatore | Si' — unica fonte del comportamento |
| `pipeline/` | Script Python | Si' |
| `.github/`, `.claude/` | Involucri per Copilot e Claude Code | Solo per cambiare l'aggancio, non il comportamento |

## Le tre regole

**1. `training_data/` non si edita.** E' generato da `pipeline/`. Un numero
sbagliato li' dentro e' un bug della pipeline: si corregge lo script e si
rigenera con `pipeline/run_pipeline.py <atleta>`. Una correzione a mano viene
cancellata alla prima riesecuzione.

**2. Il coach si cambia in `coach/`.** VS Code Copilot legge da
`.github/agents/` e `.github/prompts/`, Claude Code da `.claude/skills/`: sono
involucri di poche righe che rimandano a `coach/`. Scrivere istruzioni di
coaching dentro quegli involucri fa divergere i due strumenti, e il momento in
cui te ne accorgi e' quando ricevi due piani diversi dalla stessa domanda.

**3. Niente dati personali in git.** Tutto cio' che sta sotto `athletes/`
tranne `_template/` e `README.md` e' escluso da `.gitignore`: `.fit`,
riassunti, profili, piani. Il repository e' il sistema; i dati di chi lo usa
restano sul suo disco. Non aggiungere eccezioni a questa regola senza una
ragione esplicita.

## Identificativo atleta

Il nome della cartella sotto `athletes/` e' l'identificativo usato ovunque:
minuscolo, senza spazi. E' l'argomento degli script (`--person andrea`) e dei
comandi del coach (`/start-week andrea`). `_template` non e' un atleta: e' la
cartella da copiare.

## Convenzioni sui file

- Attivita': `activity_<id>.fit` in `raw/activities/`, `activity_<id>.md` in
  `training_data/activities/`. Lo stesso `<id>` lega i due.
- Settimane: `week_YYYY-MM-DD.md` in `plans/weeks/`, dove la data e' **il
  lunedi'**. Una settimana per file, mai due.
- File trimestrali: `<YYYY>_Q<n>_activities.md`, generati.
- I documenti prodotti dal coach seguono i template in `coach/formats/`.

## Pipeline

Sempre con l'interprete del venv:

```bash
pipeline/.venv/bin/python pipeline/run_pipeline.py <atleta>
```

Con un `python3` di sistema senza `fitparse` la conversione fallisce su ogni
file. C'e' un controllo preventivo che lo dice, ma la forma esplicita evita il
problema in partenza. Dettagli in `pipeline/README.md`.

`pipeline/paths.py` e' l'unico posto in cui e' scritto dove stanno le cose: un
percorso nuovo si aggiunge li', non si ricodifica nello script che serve.

Il converter e' diviso lungo la linea **leggi / calcola / scrivi**:
`fit_reader.py` estrae, `activity_metrics.py` calcola (funzioni pure, nessun
file aperto), `activity_markdown.py` rende, `fit_to_markdown.py` orchestra.

Un calcolo nuovo va in `activity_metrics.py`. Il vantaggio e' concreto: li' lo
si prova con una traccia costruita a mano — passo costante, pendenza costante —
invece di dover trovare un `.fit` che abbia le caratteristiche giuste.

Codici di uscita degli script, per distinguere i casi senza leggere l'output:

| Codice | Significato |
|--------|-------------|
| 0 | fatto |
| 1 | errore |
| 2 | `run_pipeline.py`: nessuna attivita' nuova da scaricare — non e' un errore |
| 3 | `profile_check.py`: il profilo non esiste |
| 4 | `run_pipeline.py`: nessun `.fit` da convertire |
| 5 | `run_pipeline.py`: alcune attivita' non convertite (le altre sono a posto) |

Due controlli meccanici, da lanciare quando si scrive nei file che riguardano:

```bash
pipeline/.venv/bin/python pipeline/profile_check.py <atleta>   # l'ingresso del coach
pipeline/.venv/bin/python pipeline/week_check.py <atleta>      # l'uscita
```

Nessuno dei due giudica la qualita': verificano che il profilo abbia i campi da
cui dipende la prescrizione, e che un piano non sia rotto.

Dopo ogni modifica al converter o allo splitter:

```bash
pipeline/.venv/bin/python -m pytest pipeline/tests -q
```

Meno di tre secondi. Coprono soprattutto il parsing: un campo che non viene
letto non solleva un errore, produce uno zero che finisce in un file e sembra
un dato.

## Cosa non c'e'

Da sapere prima di costruirci sopra:

- `health_status.md` (HRV, sonno, stress) e' citato come input opzionale ma
  **nessuno script lo produce**. Il coach e' istruito a dichiararlo invece di
  assumerlo.
- Il download da Garmin passa da due comandi `curl` copiati dal browser in
  `pipeline/curl.txt`, che scadono. Non c'e' API.
- Il tempo di riferimento e' quello **in movimento**, non l'elapsed: l'elapsed
  include le soste e gonfia i volumi.
- Il dislivello totale e quello dei lap sono dichiarati dall'orologio. Dove il
  file non li dichiara (solo attivita' indoor) vengono ricalcolati e il
  riassunto li etichetta come stimati. Gli **split al chilometro** sono invece
  sempre ricalcolati, anche outdoor: il file non contiene un dislivello per
  chilometro. Validati contro i lap del dispositivo, errore mediano 2.7%.

## Sicurezza

`pipeline/curl.txt` contiene cookie di sessione Garmin in chiaro. E' escluso da
`.gitignore` e non va condiviso: chi ce l'ha entra nell'account finche' la
sessione vale. Il formato sta in `pipeline/curl.txt.example`.

Tutto `athletes/` tranne `_template/` e' fuori da git. Chi clona il repo trova
solo il modello e ci mette i propri dati.
