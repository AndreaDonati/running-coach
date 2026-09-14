# Running Coach

Sistema di coaching per la corsa basato sui dati Garmin dell'atleta.
Vedi `README.md` alla root per l'inquadramento generale e `AGENTS.md` per le
convenzioni del repository.

## Per il coaching: `@running-coach`

Tutta la logica di coaching sta in `coach/`. L'agente `@running-coach` la legge
da li'. Non rispondere a richieste di coaching senza aver letto
`coach/coach.md`.

Comandi del ciclo settimanale:

- `/onboard` — configurazione guidata di un atleta da zero (primo avvio)
- `/sync-run <atleta>` — scarica da Garmin, converte e registra nella settimana
- `/start-week <atleta>` — crea la settimana nuova
- `/log-workout <atleta>` — aggiorna la settimana con le attivita' nuove
- `/close-week <atleta>` — consuntivo e direzione per la successiva
- `/plan-workout <atleta>: <seduta>` — dettaglia una singola seduta

## Struttura

```
athletes/<atleta>/   profile.md (scritto a mano), training_data/ (generato), plans/
coach/               istruzioni dell'allenatore: unica fonte
pipeline/            script Python: Garmin .fit -> training_data/
```

## Regole

- `athletes/*/training_data/` e' **output della pipeline**: non modificarlo a
  mano. Se un numero e' sbagliato, si corregge `pipeline/` e si rigenera.
- `pipeline/` non fa parte del coaching: sono strumenti di estrazione dati.
- Tutto sotto `athletes/` tranne `_template/` e' escluso da git: sono dati
  personali. Non proporre di aggiungerli.
