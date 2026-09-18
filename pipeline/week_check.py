#!/usr/bin/env python3
"""Controlla che un piano settimanale non sia rotto.

**Non giudica se il piano e' buono.** Se una progressione ha senso, se la seduta
di soglia e' quella giusta a nove settimane dalla gara, questo non lo sa e non
puo' saperlo. Verifica le cose meccaniche, quelle su cui un modello linguistico
scivola senza che nessuno se ne accorga: giorni mancanti, date che non tornano,
volume fuori scala rispetto a quello che l'atleta regge davvero, due sedute dure
di fila, sezioni che i comandi successivi si aspettano di trovare.

E' il complemento di `profile_check.py`: quello controlla l'ingresso del coach,
questo l'uscita.

    pipeline/.venv/bin/python pipeline/week_check.py andrea
    pipeline/.venv/bin/python pipeline/week_check.py andrea --file plans/weeks/week_2026-09-07.md

Uscita: 0 a posto (anche con avvisi), 1 problemi da correggere.
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import profile_stats  # noqa: E402

GIORNI = ["LUN", "MAR", "MER", "GIO", "VEN", "SAB", "DOM"]

# Parole con cui il coach nomina una seduta intensa. Serve a contare quante ce
# ne sono e se si toccano: non a giudicarne il contenuto.
QUALITA = re.compile(
    r"soglia|threshold|ripetut|interval|vo2|fartlek|tempo run|progressiv|"
    r"salite|collinar|ritmo gara|race pace", re.I)
RIPOSO = re.compile(r"\brest\b|riposo|scarico", re.I)
VOLUME = re.compile(r"\*\*Volume totale previsto\*\*:?\s*~?([0-9]+(?:[.,][0-9]+)?)\s*km(.*)$",
                    re.I | re.M)

# Parole con cui il coach dichiara che il volume conta **solo una parte** delle
# righe: "~36 km (corsa) + 40min strength", "~15 km corsa + escursione SAB".
# In quel caso la somma della colonna Distanza include anche cio' che la
# dichiarazione esclude di proposito, e confrontarle e' un falso allarme — ne
# ha prodotti due su quattro prima di questo filtro. Un "+ forza" invece non
# restringe niente: aggiunge un'attivita' che in chilometri non si conta.
RESTRINGE = re.compile(r"\bcorsa\b|\bsolo\b|esclus|senza\s", re.I)
KM_CELLA = re.compile(r"([0-9]+(?:[.,][0-9]+)?)(?:\s*[–—-]\s*([0-9]+(?:[.,][0-9]+)?))?\s*km", re.I)

SEZIONI_ATTESE = ["## Piano Settimanale", "## Log Allenamenti Completati",
                  "## Aggiustamenti Attivi", "## Chiusura Settimana"]


def settimana_dal_nome(percorso: Path) -> date | None:
    m = re.search(r"week_(\d{4})-(\d{2})-(\d{2})", percorso.name)
    if not m:
        return None
    try:
        return date(*map(int, m.groups()))
    except ValueError:
        return None


def settimana_attiva(person: str) -> Path | None:
    """Il file la cui settimana contiene oggi; altrimenti il piu' recente."""
    files = sorted(paths.weeks_dir(person).glob("week_*.md"))
    if not files:
        return None
    oggi = date.today()
    for f in files:
        lun = settimana_dal_nome(f)
        if lun and lun <= oggi < lun + timedelta(days=7):
            return f
    return files[-1]


def righe_piano(testo: str) -> list[tuple[str, str, str]]:
    """Righe della tabella del piano, come (giorno, riga intera, cella distanza).

    La distanza va letta dalla **sua colonna**, individuata dall'intestazione.
    Cercando "N km" in tutta la riga si prendeva anche quello che compare nella
    colonna Intensita' (un "15" da "3x15min", un passo, una quota), e il totale
    usciva gonfiato: 64 km su una settimana che ne conta 49.
    """
    col_distanza = None
    out = []
    for riga in testo.splitlines():
        if not riga.startswith("|"):
            continue
        celle = [c.strip() for c in riga.strip("|").split("|")]
        if col_distanza is None:
            for i, c in enumerate(celle):
                if re.fullmatch(r"distanza|distance|dist\.?", c, re.I):
                    col_distanza = i
                    break
        if celle and celle[0].upper() in GIORNI:
            dist = celle[col_distanza] if col_distanza is not None and col_distanza < len(celle) else ""
            out.append((celle[0].upper(), riga, dist))
    return out


def km_dalla_cella(cella: str) -> float:
    """Chilometri di una cella distanza. Un intervallo ('6-8 km') vale la media."""
    m = KM_CELLA.search(cella)
    if not m:
        return 0.0
    basso = float(m.group(1).replace(",", "."))
    alto = float(m.group(2).replace(",", ".")) if m.group(2) else basso
    return (basso + alto) / 2


def carico_recente(person: str, settimana: date | None = None) -> float | None:
    """Mediana dei km delle ultime 6 settimane concluse prima di `settimana`.

    La mediana e non la media: una settimana di gara o una di stop sposterebbero
    la media abbastanza da far passare per normale un piano fuori scala.

    `settimana` e' il lunedi' del piano in esame, e va esclusa dal confronto
    insieme a tutto cio' che viene dopo: quella in corso contiene solo i giorni
    gia' corsi, quindi abbassa la mediana tanto piu' quanto piu' presto nella
    settimana si lancia il controllo, e di lunedi' la falsa quasi al massimo.
    Senza argomento si usa la settimana di oggi.
    """
    try:
        attivita = profile_stats.load(person)
    except SystemExit:
        return None
    if not attivita:
        return None
    import weekly_rollup
    settimane = weekly_rollup.raggruppa(attivita)
    if settimana is None:
        oggi = date.today()
        settimana = oggi - timedelta(days=oggi.weekday())
    chiuse = [k for k in sorted(settimane) if k < settimana]
    ultime = [settimane[k]["km"] for k in chiuse[-6:]]
    return statistics.median(ultime) if len(ultime) >= 3 else None


def check(person: str, percorso: Path) -> tuple[list[str], list[str]]:
    testo = percorso.read_text()
    problemi: list[str] = []
    avvisi: list[str] = []

    # --- sezioni che i comandi successivi si aspettano -----------------------
    for sezione in SEZIONI_ATTESE:
        if sezione not in testo:
            problemi.append(
                f"Manca la sezione `{sezione}`.\n"
                f"     /log-workout e /close-week ci scrivono dentro: senza, non\n"
                f"     sanno dove mettere quello che producono.")

    # --- i sette giorni ------------------------------------------------------
    righe = righe_piano(testo)
    presenti = [g for g, _, _ in righe]
    mancanti = [g for g in GIORNI if g not in presenti]
    if mancanti:
        problemi.append(
            f"Giorni mancanti nel piano: {', '.join(mancanti)}.\n"
            f"     Una settimana ha sette righe, anche quando la riga dice riposo:\n"
            f"     un giorno assente non si distingue da un giorno dimenticato.")
    doppi = [g for g in GIORNI if presenti.count(g) > 1]
    if doppi:
        problemi.append(f"Giorni ripetuti nel piano: {', '.join(doppi)}.")

    # --- le date corrispondono alla settimana del nome file ------------------
    lunedi = settimana_dal_nome(percorso)
    if lunedi is None:
        problemi.append(
            f"Il nome `{percorso.name}` non segue `week_YYYY-MM-DD.md`.\n"
            f"     E' cosi' che il coach trova la settimana attiva.")
    else:
        if lunedi.weekday() != 0:
            problemi.append(
                f"`{percorso.name}` non e' un lunedi' ({lunedi:%A}).\n"
                f"     La convenzione e' la data del lunedi'.")
        attese = {(lunedi + timedelta(days=i)).strftime("%d/%m") for i in range(7)}
        trovate = set(re.findall(r"\b(\d{2}/\d{2})\b", "\n".join(r for _, r, _ in righe)))
        fuori = trovate - attese
        if fuori:
            avvisi.append(
                f"Date nella tabella fuori dalla settimana: {', '.join(sorted(fuori))}.\n"
                f"     Attese {min(attese, key=lambda d: d[3:] + d[:2])}–"
                f"{(lunedi + timedelta(days=6)):%d/%m}.")

    # --- due sedute dure di fila --------------------------------------------
    dure = [bool(QUALITA.search(riga)) and not RIPOSO.search(riga) for _, riga, _ in righe]
    consecutive = [(presenti[i], presenti[i + 1])
                   for i in range(len(dure) - 1) if dure[i] and dure[i + 1]]
    if consecutive:
        coppie = ", ".join(f"{a}+{b}" for a, b in consecutive)
        avvisi.append(
            f"Sedute intense consecutive: {coppie}.\n"
            f"     A volte e' voluto (blocco di carico); se non lo e', e' il modo\n"
            f"     piu' comune di costruire una settimana che non si regge.")

    # --- volume dichiarato e coerente col carico reale ----------------------
    m = VOLUME.search(testo)
    if not m:
        avvisi.append(
            "Manca **Volume totale previsto**.\n"
            "     E' il numero che /close-week confronta con l'effettivo: senza,\n"
            "     l'aderenza non e' calcolabile.")
    else:
        previsto = float(m.group(1).replace(",", "."))
        qualificato = bool(RESTRINGE.search(m.group(2) or ""))
        somma = sum(km_dalla_cella(d) for _, _, d in righe)
        # Severita' graduata: il volume dichiarato e' prosa e a volte esclude
        # qualcosa di proposito ("~41 km + forza"), quindi uno scarto moderato e'
        # un avviso. Sopra un quarto non e' piu' un'approssimazione, ed e' il
        # numero su cui /close-week calcola l'aderenza.
        if somma > 0 and qualificato:
            # La dichiarazione dice cosa conta e cosa no: la somma della colonna
            # non e' il termine di paragone. L'unica cosa verificabile e' che il
            # sottoinsieme non sia piu' grande del totale.
            if previsto > somma * 1.05:
                problemi.append(
                    f"Il volume dichiarato ({previsto:.0f} km) supera la somma della\n"
                    f"     colonna Distanza ({somma:.0f} km), ma la dichiarazione conta solo\n"
                    f"     una parte delle righe: uno dei due numeri e' sbagliato.")
        elif somma > 0:
            scarto = abs(somma - previsto) / max(previsto, 1.0)
            messaggio = (
                f"Il volume dichiarato ({previsto:.0f} km) non torna con la somma\n"
                f"     della colonna Distanza ({somma:.0f} km): {scarto * 100:.0f}% di scarto.\n"
                f"     /close-week calcola l'aderenza sul numero dichiarato.")
            if scarto > 0.25:
                problemi.append(messaggio)
            elif scarto > 0.10:
                avvisi.append(messaggio)

        recente = carico_recente(person, lunedi)
        if recente and recente > 0:
            rapporto = previsto / recente
            if rapporto > 1.5:
                problemi.append(
                    f"Volume previsto {previsto:.0f} km contro una mediana recente di\n"
                    f"     {recente:.0f} km/sett: +{(rapporto - 1) * 100:.0f}%. Un salto simile\n"
                    f"     e' il modo classico di procurarsi un infortunio.")
            elif rapporto > 1.25:
                avvisi.append(
                    f"Volume previsto {previsto:.0f} km contro {recente:.0f} km/sett recenti "
                    f"(+{(rapporto - 1) * 100:.0f}%).\n"
                    f"     Va bene se e' una settimana di carico dichiarata come tale.")
            elif rapporto < 0.5:
                avvisi.append(
                    f"Volume previsto {previsto:.0f} km contro {recente:.0f} km/sett recenti "
                    f"(-{(1 - rapporto) * 100:.0f}%).\n"
                    f"     Atteso in scarico o taper; altrimenti il piano e' tarato basso.")

    # --- il razionale c'e' e dice qualcosa ----------------------------------
    mr = re.search(r"\*\*Razionale\*\*:?\s*(.+?)(?=\n\n|\n##|\Z)", testo, re.S)
    if not mr:
        avvisi.append("Manca il **Razionale**: perche' questo carico, in questa fase.")
    elif len(mr.group(1).strip()) < 80:
        avvisi.append("Il **Razionale** e' di una riga: probabilmente non spiega la scelta.")

    # --- il conto alla rovescia ---------------------------------------------
    if "Settimane alla gara" not in testo:
        avvisi.append(
            "Manca **Settimane alla gara**: e' il numero da cui si deriva la fase.")

    return problemi, avvisi


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("person")
    ap.add_argument("--file", help="File da controllare (default: la settimana attiva)")
    ap.add_argument("--all", action="store_true", help="Controlla tutte le settimane")
    args = ap.parse_args()

    person = args.person.strip().lower()
    paths.athlete_dir(person)

    if args.all:
        files = sorted(paths.weeks_dir(person).glob("week_*.md"))
    elif args.file:
        f = Path(args.file)
        files = [f if f.is_absolute() else paths.REPO_ROOT / f]
    else:
        attiva = settimana_attiva(person)
        if attiva is None:
            raise SystemExit(
                f"Nessun file settimana in {paths.weeks_dir(person)}.\n"
                f"Creane uno con: /start-week {person}")
        files = [attiva]

    uscita = 0
    for f in files:
        if not f.exists():
            print(f"❌ {f} non esiste.")
            uscita = 1
            continue
        problemi, avvisi = check(person, f)
        nome = f.relative_to(paths.REPO_ROOT)
        if not problemi and not avvisi:
            print(f"✅ {nome}")
            continue
        print(f"\n{nome}")
        for x in problemi:
            print(f"  ❌ {x}")
        for x in avvisi:
            print(f"  ⚠️  {x}")
        if problemi:
            uscita = 1

    if uscita == 0 and len(files) > 1:
        print("\nNessun problema bloccante.")
    return uscita


if __name__ == "__main__":
    raise SystemExit(main())
