#!/usr/bin/env python3
"""Controlla che il profilo di un atleta sia compilato dove conta.

Il modo peggiore in cui questo sistema si rompe non e' un errore: e' un profilo
lasciato a meta'. Il coach legge `[Check from health_status.md]` come "dato non
disponibile", non protesta, e produce un piano argomentato su niente — che e'
esattamente il tipo di output che sembra buono.

Questo controllo non giudica il contenuto: verifica che i campi da cui dipende
la prescrizione ci siano davvero.

    pipeline/.venv/bin/python pipeline/profile_check.py andrea

Uscita: 0 a posto, 1 mancano campi essenziali, 3 il profilo non esiste.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

# Un segnaposto del modello: parentesi quadre che non siano un link Markdown
# ne' una casella di spunta.
PLACEHOLDER_RE = re.compile(r"\[([^\]\n]{3,})\](?!\()")
ISO_DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")


def find_placeholders(testo: str) -> list[tuple[int, str]]:
    out = []
    for n, riga in enumerate(testo.splitlines(), 1):
        for m in PLACEHOLDER_RE.finditer(riga):
            contenuto = m.group(1)
            if contenuto.lower() in ("x", " ", "ok"):
                continue
            out.append((n, contenuto))
    return out


def sezione(testo: str, *titoli: str) -> str:
    """Testo della sezione di **secondo livello** col primo titolo che combacia.

    Il livello conta: cercando genericamente "Obiettivi" si agganciava
    `### Obiettivi Secondari` invece di `## Goals`, e il controllo sulla data
    guardava solo le gare secondarie — dichiarando scaduto un obiettivo primario
    che era a due mesi di distanza. Un controllo che da' falsi allarmi viene
    ignorato, quindi vale la pena essere precisi.
    """
    for titolo in titoli:
        m = re.search(rf"^##\s*{re.escape(titolo)}.*$", testo, re.I | re.M)
        if not m:
            continue
        resto = testo[m.end():]
        fine = re.search(r"^##\s", resto, re.M)  # prossima sezione di pari livello
        return resto[: fine.start()] if fine else resto
    return ""


def check(person: str) -> tuple[list[str], list[str]]:
    """Restituisce (bloccanti, avvisi)."""
    percorso = paths.profile(person)
    if not percorso.exists():
        raise SystemExit(
            f"{percorso} non esiste.\n"
            f"Crealo copiando il modello:  cp -R athletes/_template athletes/{person}"
        )
    testo = percorso.read_text()
    bloccanti: list[str] = []
    avvisi: list[str] = []

    # --- la data della gara: il campo da cui il coach deriva la fase ---------
    obiettivi = sezione(testo, "Obiettivi", "Goals", "Obiettivo") or testo
    date_trovate = ISO_DATE_RE.findall(obiettivi)
    if not date_trovate:
        bloccanti.append(
            "Nessuna data di gara in formato YYYY-MM-DD nella sezione Obiettivi.\n"
            "     Senza, il coach non puo' calcolare le settimane mancanti e quindi\n"
            "     non puo' derivare la fase: ogni piano settimanale sarebbe arbitrario."
        )
    else:
        future = []
        for a, m, g in date_trovate:
            try:
                d = date(int(a), int(m), int(g))
            except ValueError:
                continue
            if d >= date.today():
                future.append(d)
        if not future:
            passate = ", ".join(f"{a}-{m}-{g}" for a, m, g in date_trovate)
            bloccanti.append(
                f"Tutte le date di gara sono passate ({passate}).\n"
                f"     Il coach userebbe un conto alla rovescia negativo. Aggiorna\n"
                f"     l'obiettivo primario con la gara successiva."
            )
        else:
            prossima = min(future)
            settimane = (prossima - date.today()).days // 7
            if settimane < 2:
                avvisi.append(
                    f"La gara primaria e' fra {settimane} settimane: resta solo il taper.")

    # --- segnaposti del modello rimasti ------------------------------------
    residui = find_placeholders(testo)
    if residui:
        elenco = "\n".join(f"       riga {n}: [{c}]" for n, c in residui[:8])
        extra = f"\n       ... e altri {len(residui) - 8}" if len(residui) > 8 else ""
        messaggio = (
            f"{len(residui)} campi sono ancora quelli del modello. Il coach li legge\n"
            f"     come 'dato non disponibile' e ci costruisce sopra lo stesso:\n"
            f"{elenco}{extra}"
        )
        # Sempre un avviso, mai bloccante: campi opzionali non compilati
        # peggiorano il piano, non lo rendono arbitrario. L'unica cosa che lo
        # rende arbitrario e' l'assenza della data di gara.
        avvisi.append(messaggio)

    # --- attendibilita' del cardio: cambia come si governano le sedute ------
    testo_l = testo.lower()
    if not any(k in testo_l for k in ("polso", "cadence lock", "fascia cardio", "hrm")):
        avvisi.append(
            "Non e' detto se la FC da polso e' attendibile su questo atleta.\n"
            "     Se il sensore sbaglia, ogni prescrizione a frequenza cardiaca e'\n"
            "     falsa. Il test da mezzo minuto e' in coach/workflows/onboard.md."
        )

    # --- FC massima: l'unico campo che uno script legge dal profilo ---------
    import profile_stats
    if profile_stats.leggi_fc_massima(person) is None:
        avvisi.append(
            "Manca la **FC massima** (riga `- **FC massima**: <bpm>`).\n"
            "     Senza, la distribuzione del tempo per zona non si calcola: il\n"
            "     coach vede la FC media di ogni seduta ma non se la settimana e'\n"
            "     stata polarizzata o tutta in mezzo.")

    # --- vincoli reali: un piano su giorni che non ci sono fallisce ---------
    if not re.search(r"giorni (disponibili|a settimana)|days available", testo_l):
        avvisi.append(
            "Non e' detto quanti giorni a settimana l'atleta puo' allenarsi.\n"
            "     E' il vincolo che fa fallire i piani alla seconda settimana."
        )

    return bloccanti, avvisi


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("person")
    ap.add_argument("--strict", action="store_true",
                    help="Considera bloccanti anche gli avvisi")
    args = ap.parse_args()

    person = args.person.strip().lower()
    paths.athlete_dir(person)
    bloccanti, avvisi = check(person)

    if not bloccanti and not avvisi:
        print(f"✅ {person}: il profilo ha tutto quello che serve al coach.")
        return 0

    for b in bloccanti:
        print(f"❌ {b}")
    for a in avvisi:
        print(f"⚠️  {a}")

    print()
    if bloccanti:
        print(f"{len(bloccanti)} problemi da risolvere prima di generare un piano.")
        return 1
    print(f"{len(avvisi)} avvisi: il coach funziona, ma con meno contesto di quanto potrebbe.")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
