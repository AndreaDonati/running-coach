# Workflow: sync-run

Dal "ho corso" al "il coach lo sa", in un giro solo: aggiorna i cookie Garmin,
scarica le attivita' nuove, le converte, le riassume e le registra nella
settimana attiva.

**Input**: nome atleta. Opzionale: i due comandi cURL negli appunti.
**Output**: `training_data/` aggiornato e la settimana attiva aggiornata.

## Procedura

### 1. Capire se servono cookie nuovi

Guarda la data di `pipeline/curl_<atleta>.txt` — **uno per atleta**, perche' i
cookie appartengono a un account Garmin. I cookie durano poche ore: se il file
ha piu' di ~6 ore, vanno riesportati. Se non esiste, vanno esportati e basta.

Se l'atleta non e' quello del sync precedente, i cookie sono quasi certamente
da riesportare: sono di un'altra persona. La sessione va aperta **sull'account
di quell'atleta** (una finestra in incognito evita di buttare fuori l'altro).
Il downloader se ne accorge da solo e si ferma prima di scaricare, confrontando
il cookie `GARMIN-SSO-CUST-GUID` con `athletes/<atleta>/.garmin_guid`.

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

**Non stampare mai il contenuto di `curl_<atleta>.txt` nella conversazione**:
contiene i cookie di sessione dell'account Garmin.

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
- **"Il cURL e' di un altro account Garmin"** — i cookie sono di un altro
  atleta. Non e' un errore della pipeline: e' la guardia che ha impedito di
  scaricare le attivita' di uno nella cartella di un altro. Richiedi i cURL
  con la sessione dell'atleta giusto aperta. Solo se l'account di quell'atleta
  e' cambiato per davvero si cancella il suo `.garmin_guid`.
- **Errori di conversione su alcuni file** — riporta quali e vai avanti con gli
  altri. Un `.fit` troncato non blocca il resto. Il log sta in
  `pipeline/logs/<atleta>-convert.log`.

### 4. Registrare nel piano

Con le attivita' nuove a bordo, esegui `coach/workflows/log-workout.md` per lo
stesso atleta: e' il passo che le confronta col piano e aggiorna la settimana.

Poi riassumi all'utente in poche righe: quante attivita' nuove, quali giorni
sono stati marcati fatti, e se qualcosa nel piano e' cambiato di conseguenza.

## Regole

- Non chiedere i cookie se `curl_<atleta>.txt` e' recente: prova prima, chiedi
  se fallisce.
- Non lanciare `--recreate`: ricostruisce centinaia di file per niente. Serve
  solo dopo una modifica al converter.
- Se l'utente chiede di registrare un allenamento e i `.fit` sono gia' sul
  disco, lancia **senza** `--download`: converte quello che c'e' e salti tutta
  la parte dei cookie. (`--no-download` non esiste: era un errore di questo
  documento.)
