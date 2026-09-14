---
name: log-workout
description: Cerca in training_data/ le attivita' della settimana corrente non ancora registrate e aggiorna il file settimana attivo: marca le sedute fatte, aggiunge le voci di log, adatta i giorni rimanenti. Usare quando si dice 'logga allenamenti', 'aggiorna settimana', 'log workout' seguito da un nome atleta.
---

# Registrazione allenamenti

Input: `$ARGUMENTS` — il nome dell'atleta (es. andrea, giorgia)

## Cosa fare

1. Leggi `coach/coach.md` — principi, quali file leggere e in che ordine,
   periodizzazione, dati mancanti, limiti.
2. Leggi `coach/workflows/log-workout.md` — la procedura, passo per passo.
3. Eseguila.

Questa skill e' un involucro: la procedura non e' duplicata qui, cosi' Claude
Code e VS Code Copilot si comportano allo stesso modo. Per cambiare il
comportamento del coach, modifica i file in `coach/`.
