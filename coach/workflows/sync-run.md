# Workflow: sync-run

Dal "ho corso" al "il coach lo sa", in un giro solo: aggiorna i cookie Garmin,
scarica le attivita' nuove, le converte, le riassume e le registra nella
settimana attiva.

**Input**: nome atleta. Opzionale: i due comandi cURL negli appunti.
**Output**: `training_data/` aggiornato e la settimana attiva aggiornata.

## Procedura

### 1. Capire se servono cookie nuovi

Guarda la data di `pipeline/curl.txt`. I cookie Garmin durano poche ore: se il
file ha piu' di ~6 ore, vanno riesportati. Se non esiste, vanno esportati e
basta.

Quando servono, chiedili all'utente con queste istruzioni testuali:

> Servono i due comandi cURL da Garmin Connect, con la sessione aperta:
> 1. apri connect.garmin.com, vai alle Attività
> 2. DevTools (F12) → scheda Network
> 3. ricarica la pagina, trova la richiesta a `activitylist-service/...`
>    → tasto destro → Copy → **Copy as cURL**
> 4. scarica una attività in .fit, trova la richiesta a
>    `download-service/files/activity/<id>` → Copy as cURL
> 5. copiali **entrambi** negli appunti (uno sotto l'altro) e dimmi "fatto"

Non serve che l'utente li incolli in chat: restano negli appunti. Se li incolla
lo stesso, salvali in un file e usa `--curl-file`.

**Non stampare mai il contenuto di `curl.txt` nella conversazione**: contiene i
cookie di sessione dell'account Garmin.

### 2. Sincronizzare

```bash
# cookie nuovi negli appunti
pipeline/.venv/bin/python pipeline/run_pipeline.py <atleta> --curl-from-clipboard

# cookie ancora validi
pipeline/.venv/bin/python pipeline/run_pipeline.py <atleta> --download

# i .fit sono già sul disco: converte e basta
pipeline/.venv/bin/python pipeline/run_pipeline.py <atleta>
```

Lo script riconosce da solo quale cURL e' l'elenco e quale il download, anche
se sono in ordine inverso.

Codici di uscita: `0` fatto, `2` nessuna attivita' nuova (non e' un errore),
`1` errore.

### 3. Interpretare l'esito

- **Uscita 2** — di' che non c'e' niente di nuovo e fermati. Non lanciare il
  log.
- **"session expired" / uscita 1 sul download** — i cookie sono scaduti: torna
  al punto 1 e richiedili. Le attivita' gia' scaricate non si riscaricano,
  quindi riprovare non fa danni.
- **Errori di conversione su alcuni file** — riporta quali e vai avanti con gli
  altri. Un `.fit` troncato non blocca il resto. Il log sta in
  `pipeline/logs/<atleta>-convert.log`.

### 4. Registrare nel piano

Con le attivita' nuove a bordo, esegui `coach/workflows/log-workout.md` per lo
stesso atleta: e' il passo che le confronta col piano e aggiorna la settimana.

Poi riassumi all'utente in poche righe: quante attivita' nuove, quali giorni
sono stati marcati fatti, e se qualcosa nel piano e' cambiato di conseguenza.

## Regole

- Non chiedere i cookie se `curl.txt` e' recente: prova prima, chiedi se
  fallisce.
- Non lanciare `--recreate`: ricostruisce centinaia di file per niente. Serve
  solo dopo una modifica al converter.
- Se l'utente chiede di registrare un allenamento e i `.fit` sono gia' sul
  disco, usa `--no-download` e salti tutta la parte dei cookie.
