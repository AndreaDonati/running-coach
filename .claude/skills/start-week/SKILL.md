---
name: start-week
description: Apre la settimana di allenamento per un atleta: deriva la fase dal conto alla rovescia verso la gara, legge la chiusura della settimana precedente e crea athletes/<atleta>/plans/weeks/week_YYYY-MM-DD.md. Usare quando si dice 'inizia settimana', 'start week', 'nuova settimana' seguito da un nome atleta.
---

# Apertura settimana

Input: `$ARGUMENTS` — il nome dell'atleta (es. andrea, giorgia)

## Cosa fare

1. Leggi `coach/coach.md` — principi, quali file leggere e in che ordine,
   periodizzazione, dati mancanti, limiti.
2. Leggi `coach/workflows/start-week.md` — la procedura, passo per passo.
3. Eseguila.

Questa skill e' un involucro: la procedura non e' duplicata qui, cosi' Claude
Code e VS Code Copilot si comportano allo stesso modo. Per cambiare il
comportamento del coach, modifica i file in `coach/`.
