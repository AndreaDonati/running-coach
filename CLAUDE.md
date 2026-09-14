# Running Coach

Le convenzioni di questo repository stanno in **`AGENTS.md`**: leggilo prima di
modificare qualsiasi cosa. Per capire cos'e' il progetto, `README.md`.

In breve, le tre cose che si sbagliano piu' facilmente:

1. `athletes/*/training_data/` e' **generato** da `pipeline/`. Non editarlo:
   correggi lo script e rigenera.
2. Il comportamento del coach si cambia in **`coach/`**, non in `.claude/skills/`
   ne' in `.github/`: quelli sono involucri che rimandano li'.
3. **Niente dati personali in git.** Tutto sotto `athletes/` tranne
   `_template/` e' in `.gitignore`. Non aggiungere eccezioni.

## Coaching

Le skill `onboard`, `start-week`, `sync-run`, `log-workout`, `close-week` e
`plan-workout` implementano il ciclo settimanale. Prima di rispondere a una
richiesta di coaching leggi `coach/coach.md`.

## Pipeline

```bash
pipeline/.venv/bin/python pipeline/run_pipeline.py <atleta>
```

Interprete del venv, sempre: con un `python3` di sistema manca `fitparse` e la
conversione fallisce su ogni file.
