---
name: onboard
description: Configura da zero un atleta nel running coach, intervistando la persona. Crea la cartella, importa le attività da Garmin, calcola dal dati quello che si può calcolare, chiede solo ciò che i dati non sanno (gara, data, vincoli, infortuni), compila il profilo e chiude con la prima settimana di allenamento. Usare quando qualcuno dice 'come inizio', 'configurami', 'primo avvio', 'aggiungi un atleta', 'setup', o apre il progetto per la prima volta.
---

# Configurazione guidata

Input: `$ARGUMENTS` — il nome dell'atleta, se già lo sai. Altrimenti chiedilo.

## Cosa fare

1. Leggi `coach/workflows/onboard.md` — la procedura completa, passo per passo,
   con le domande da fare e le verifiche da eseguire dopo ognuna.
2. Leggi `coach/coach.md` — principi e struttura dei dati, che ti servono dal
   passo 4 in poi.
3. Conducila tu: una domanda alla volta, calcolando quello che si può calcolare
   invece di chiederlo, e verificando con un numero dopo ogni passo.

La procedura si aggancia a `coach/workflows/sync-run.md` per l'import da Garmin
e a `coach/workflows/start-week.md` per chiudere con la prima settimana.

Questa skill è un involucro: la procedura non è duplicata qui.
