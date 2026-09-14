# L'allenatore

Qui c'è tutto quello che l'allenatore sa e sa fare. Non è codice: sono file di
testo che un assistente AI legge prima di risponderti.

Questo significa che puoi **leggerlo**, e se non sei d'accordo, **cambiarlo**.
Se pensi che tre giorni di corsa a settimana siano pochi, o che il recupero
dopo una seduta dura debba essere di 48 ore e non 24, apri il file e riscrivi
quella riga. Da quel momento l'allenatore la pensa così.

## I file

```
coach.md        i principi: cosa legge, in che ordine, come periodizza,
                cosa non deve fare mai
workflows/      le procedure, una per comando
formats/        la forma dei documenti che produce
```

**Parti da `coach.md`.** In una decina di minuti sai come ragiona: da dove
ricava la fase di allenamento, quali dati usa, quando si ferma e ti chiede
qualcosa invece di tirare a indovinare.

I `workflows/` sono procedure numerate — cosa leggere, cosa scrivere, cosa
verificare — una per ciascun comando (`/start-week`, `/sync-run`,
`/log-workout`, `/close-week`, `/plan-workout`, `/onboard`).

I `formats/` sono i modelli dei documenti: la struttura del file settimana, la
riga di log di un allenamento svolto, il consuntivo di fine settimana, la scheda
di una singola seduta.

## Il ciclo della settimana

```
lunedì            /start-week      scrive la settimana nuova
dopo una corsa    /sync-run        scarica, converte e registra
domenica          /close-week      consuntivo, e direzione per la prossima
quando serve      /plan-workout    una seduta in dettaglio, lap per lap
```

Ogni comando legge il profilo dell'atleta e lo storico degli allenamenti prima
di scrivere qualsiasi cosa. La regola che tiene insieme tutto è che l'allenatore
deve **citare numeri veri**: i passi che prescrive vengono dalle tue sedute
recenti, non da una tabella generica.

## Due cose a cui tiene

**Dire quando non sa.** Se manca un dato — la frequenza a riposo, l'HRV, il
sonno — l'allenatore è tenuto a dichiararlo e a spiegare su cosa si sta basando
invece. Un consiglio costruito su un dato inventato è peggio di nessun consiglio.

**Spiegare il perché.** Ogni settimana contiene un *Razionale*: perché questo
carico, in questa fase, a questa distanza dalla gara. È la parte da leggere per
prima, e quella che ti permette di accorgerti se ha sbagliato.

## Perché sta in una cartella a sé

Le stesse istruzioni servono a due strumenti: VS Code Copilot le prende da
`.github/`, Claude Code da `.claude/`. Quei file sono involucri di poche righe
che rimandano qui.

Se vuoi cambiare come si comporta l'allenatore, il posto è **sempre `coach/`**.
Modificare gli involucri farebbe divergere i due strumenti, che è il modo più
rapido per ritrovarsi con due allenatori diversi che non lo sanno.
