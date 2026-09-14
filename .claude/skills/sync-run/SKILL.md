---
name: sync-run
description: Scarica da Garmin le attività nuove di un atleta, le converte e le registra nella settimana di allenamento. Gestisce i cookie di sessione Garmin chiedendo all'utente i due comandi cURL quando sono scaduti. Usare quando si dice 'sincronizza', 'scarica le attività', 'ho corso', 'aggiorna i dati', 'logga l'allenamento' seguito da un nome atleta, o quando si passa una curl di Garmin.
---

# Sincronizza e registra

Input: `$ARGUMENTS` — il nome dell'atleta (es. andrea, giorgia)

## Cosa fare

1. Leggi `coach/coach.md` — principi e file dell'atleta.
2. Leggi `coach/workflows/sync-run.md` — la procedura completa, inclusa la
   richiesta dei comandi cURL all'utente quando i cookie sono scaduti.
3. Eseguila. Comprende anche `coach/workflows/log-workout.md` come ultimo
   passo.

**Non stampare mai il contenuto di `pipeline/curl.txt`**: contiene i cookie di
sessione dell'account Garmin dell'utente.

Questa skill e' un involucro: la procedura non e' duplicata qui.
