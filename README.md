# Running Coach

Un allenatore di corsa che conosce i tuoi allenamenti.

Gli dici che gara vuoi fare e quando. Lui legge tutto quello che hai corso —
ogni seduta, passo per passo, chilometro per chilometro — e ti scrive la
settimana di allenamento. Poi la segue: quando corri registra com'è andata,
confronta col previsto, e a fine settimana tira le somme e imposta la
successiva.

Non è un'app e non è un sito. È una cartella di file di testo sul tuo computer,
che apri con un assistente AI — Claude Code o GitHub Copilot. I tuoi dati non
vanno da nessuna parte.

## Che aspetto ha

Ogni corsa diventa un riassunto che l'allenatore sa leggere:

```markdown
# Activity Summary

- **Type:** running          - **Terrain:** trail
- **Date:** 2026-04-06       - **Distance:** 10.09 km
- **Moving time:** 1:12:35   - **Total ascent:** 297 m
- **Avg HR:** 158 bpm        - **Avg power:** 214 W
- **Tempo per banda FC:** 130-140 6:58 · 150-160 18:09 · 160-170 28:11
- **Passo corretto per la pendenza:** 6:32/km (reale 7:12/km)

**Per-km splits:**
|km|durata|FC media|dislivello|
|1 | 6:39 |   132  |  +10 m   |
|2 | 8:30 |   155  |  +42 m   |
|3 | 8:28 |   153  |  +27 m   |
```

E la tua settimana è un file che cresce mentre la vivi:

```markdown
# Settimana 12 — Build | Obiettivo: Mezza di primavera
**Settimane alla gara**: 9

| Giorno | Allenamento              | Distanza | Intensità        | Stato |
| LUN    | Easy                     | 6 km     | Z2 / FC <148     | ✅    |
| MAR    | Soglia — 3×10min         | 12 km    | 5:40/km, FC ≤165 | ✅    |
| MER    | Recovery                 | 6 km     | Z1               | ⬜    |
| ...    |                          |          |                  |       |

**Razionale**: terza settimana di Build, il blocco di soglia passa da 10 a 15
minuti mantenendo la stessa intensità: il progresso è la durata, non il passo.

## Log Allenamenti Completati
### MAR 08/09 — Soglia 12.1 km
- **Effettivo**: 12.1 km, 5:38/km, FC media 161, D+ 45 m
- **Delta**: +0.1 km, −2 sec/km sul previsto
- **Note coach**: tenuta buona, FC sotto il tetto. Il blocco si può allungare.
```

## Come si usa

Quattro comandi, che scrivi all'assistente come fossero messaggi:

| Quando | Comando | Cosa fa |
|--------|---------|---------|
| Lunedì | `/start-week` | Scrive la settimana, calcolata sulla fase in cui sei |
| Dopo una corsa | `/sync-run` | Scarica da Garmin, converte, registra nel piano |
| Domenica | `/close-week` | Consuntivo e direzione per la settimana dopo |
| Quando vuoi | `/plan-workout` | Una singola seduta in dettaglio, lap per lap |

`/plan-workout` restituisce anche la tabella da copiare sull'orologio, un lap
alla volta, con passo e frequenza cardiaca di ogni ripetuta.

## Cosa ti serve

- **Un orologio Garmin.** Il sistema legge i file `.fit`. Strava, Polar e Coros
  non sono supportati.
- **Un assistente AI con accesso ai file**: [Claude
  Code](https://claude.com/claude-code) o VS Code con GitHub Copilot. È lui che
  legge i dati e scrive i piani. Entrambi sono a pagamento.
- **Python 3.9 o superiore**, per la parte che converte i file dell'orologio.
- **macOS o Linux** (su Windows, WSL).

## Come si parte

Apri la cartella con l'assistente e scrivi:

```
/onboard
```

Da lì in poi guida lui: ti fa le domande una alla volta, importa le tue attività
da Garmin, ricava da solo quello che i dati già dicono — quanto corri, su che
terreno, com'è andato l'ultimo anno — e chiede solo quello che i dati non
possono sapere: che gara vuoi fare, quando, quanti giorni a settimana hai
davvero. Finisce compilando il tuo profilo e scrivendoti la prima settimana.

Ci vogliono una ventina di minuti, la maggior parte dei quali è il primo
scaricamento dello storico.

<details>
<summary>Preferisci fare a mano</summary>

```bash
# ambiente Python, e verifica che funzioni
./pipeline/setup_venv.sh
pipeline/.venv/bin/python -m pytest pipeline/tests -q

# crea il tuo atleta e mettici dentro i .fit
cp -R athletes/_template athletes/<nome>
#   → copia i file in athletes/<nome>/raw/activities/
#     (per scaricarli da Garmin: pipeline/README.md)

# converti
pipeline/.venv/bin/python pipeline/run_pipeline.py <nome>

# guarda cosa ne è uscito
pipeline/.venv/bin/python pipeline/profile_stats.py <nome>

# compila athletes/<nome>/profile.md, poi verifica che non manchi niente
pipeline/.venv/bin/python pipeline/profile_check.py <nome>
```

</details>

## I tuoi dati restano tuoi

Nel repository c'è **il sistema**, non i dati di chi lo usa: tutto quello che
riguarda un atleta — i file dell'orologio, i riassunti, il profilo, i piani —
è escluso da git e resta sul tuo disco. Puoi pubblicare una tua versione senza
pubblicare quanto corri, quanto pesi e dove abiti.

Se hai clonato il repository di qualcun altro, la cartella `athletes/` ti arriva
vuota: c'è solo il modello da copiare. E quando chi te l'ha passato lo migliora,
`git pull` aggiorna il sistema senza toccare niente di tuo.

## Cosa non fa

Meglio saperlo prima di provarci.

- **Non legge i dati di salute.** HRV, sonno e stress non arrivano dall'orologio:
  o li scrivi a mano nel profilo, o l'allenatore lavora senza — e in quel caso
  te lo dice, invece di far finta di saperli.
- **Lo scarico da Garmin è manuale.** Non esiste un'API aperta: si copiano due
  comandi dal browser, e le credenziali scadono nel giro di ore. `/sync-run` te
  li richiede quando servono.
- **Non sa se un piano è buono.** Un controllo automatico verifica che una
  settimana non sia rotta — sette giorni, date coerenti, volume in scala col
  carico che reggi davvero — ma se una progressione non ha senso, nessuno se ne
  accorge al posto tuo. Per questo ogni settimana contiene un **Razionale**:
  è lì che l'allenatore deve giustificare quello che ti ha scritto. Leggilo.
- **Non misura la tenuta sui lunghi in montagna.** Su percorso vario il calo di
  efficienza fra prima e seconda metà risulta legato alla pendenza più che alla
  fatica, quindi non viene prodotto. Sui percorsi piatti sì.
- **Non fa niente da solo.** Nessuna automazione, nessuna notifica: ogni passo
  parte da te.

## Prima di iniziare

Questo strumento scrive piani di allenamento usando i tuoi dati e un modello
linguistico. Non è un medico e non è un preparatore: può sbagliare, e quando
sbaglia lo fa in modo plausibile, che è il modo peggiore.

L'allenatore è istruito a non dare consigli medici, a non farti allenare
attraverso un infortunio e a dichiarare quando un dato gli manca invece di
inventarlo. Resta software. Se hai un dolore che non passa, un problema
cardiaco, o stai ricominciando dopo un lungo stop, parlane con qualcuno che ti
può visitare.

E il carico che ti propone va sempre letto col tuo giudizio: se una settimana ti
sembra troppo, lo è.

## Com'è organizzato

```
athletes/<nome>/   il tuo profilo, i tuoi dati, i tuoi piani
coach/             cosa sa e come ragiona l'allenatore
pipeline/          gli script che convertono i file dell'orologio
.github/ .claude/  l'aggancio a Copilot e a Claude Code
```

| Per sapere | Leggi |
|------------|-------|
| Come aggiungere un atleta | [`athletes/README.md`](athletes/README.md) |
| Cosa sa e cosa fa l'allenatore | [`coach/README.md`](coach/README.md) |
| Come funzionano gli script | [`pipeline/README.md`](pipeline/README.md) |
| Come contribuire senza rompere niente | [`AGENTS.md`](AGENTS.md) |

Licenza MIT: fanne quello che vuoi.
