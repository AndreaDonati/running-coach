"""Test della pipeline su un'attivita' reale.

Non coprono tutto: coprono la classe di errori che ha davvero fatto danni in
questo repository, cioe' il **parsing che fallisce in silenzio**. Tre volte lo
stesso schema: un campo non viene letto, il codice non si lamenta, il valore
diventa None o zero, e finisce in un file che il coach legge come se fosse vero.

  - i pattern del quarter splitter non agganciavano i riassunti del converter:
    summary.md dichiarava 0.0 km su centinaia di sedute
  - `enhanced_speed` non era mappato: la velocita' campione per campione era
    None su ogni attivita'
  - i valori di riepilogo venivano presi indifferentemente da `session` o da un
    `lap`: 272 W invece di 199 su una corsa di 16 lap

Ognuno sarebbe stato intercettato da un'asserzione di tre righe.

    pipeline/.venv/bin/python -m pytest pipeline/tests -q
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "sample_activity.fit"

sys.path.insert(0, str(PIPELINE))
import quarter_split  # noqa: E402


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    """Converte la fixture una volta sola; restituisce (summary, testo_md, json)."""
    d = tmp_path_factory.mktemp("conv")
    md, js = d / "sample.md", d / "sample.json"
    res = subprocess.run(
        [sys.executable, str(PIPELINE / "fit_to_markdown.py"), str(FIXTURE),
         str(md), "--json", str(js)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    assert md.exists(), "il converter non ha prodotto il Markdown"
    full = json.loads(js.read_text())
    return full["summary"], md.read_text(), full


# --- il converter legge davvero il file -------------------------------------

def test_campi_di_riepilogo_valorizzati(converted):
    summary, _, _ = converted
    for campo in ("distance_m", "moving_time_s", "elapsed_time_s",
                  "avg_hr", "max_hr", "calories", "activity_type"):
        assert summary.get(campo) is not None, f"{campo} non estratto"


def test_valori_plausibili(converted):
    summary, _, _ = converted
    assert 10_000 < summary["distance_m"] < 10_200      # 10.09 km
    assert 4000 < summary["moving_time_s"] < 4500       # ~1h12
    assert 100 < summary["avg_hr"] < 200
    assert summary["moving_time_s"] <= summary["elapsed_time_s"]


def test_velocita_presente_nella_timeseries(converted):
    """`enhanced_speed`: i Garmin recenti non scrivono la chiave `speed`."""
    _, _, full = converted
    ts = full["timeseries"]
    con_velocita = sum(1 for t in ts if t.get("speed_m_s"))
    assert con_velocita > len(ts) * 0.5, (
        f"solo {con_velocita}/{len(ts)} campioni hanno la velocita'"
    )


def test_riepilogo_viene_dalla_sessione_non_dai_lap(converted):
    """Un FIT contiene i totali della sessione E di ogni lap, stessi nomi."""
    _, _, full = converted
    laps = full.get("laps") or []
    if len(laps) < 2:
        pytest.skip("fixture con meno di 2 lap")
    somma_lap = sum(l.get("total_distance") or 0 for l in laps)
    # la distanza di sessione deve somigliare alla somma dei lap, non a un lap solo
    assert full["summary"]["distance_m"] > somma_lap * 0.8


# --- il riassunto Markdown e' leggibile dallo splitter ----------------------

def test_lo_splitter_rilegge_il_sidecar(converted, tmp_path):
    """Il contratto fra i due passi: se si rompe, i totali vanno a zero."""
    _, md_text, _ = converted
    f = tmp_path / "activity_1.md"
    f.write_text(md_text)

    a = quarter_split.read_activity_file(f)
    assert a is not None, "lo splitter non riesce a leggere il riassunto"
    assert a["date"] is not None
    assert a["distance_km"] is not None, "distanza non letta: i totali andrebbero a zero"
    assert a["duration_s"] is not None, "durata non letta"
    assert a["calories"] is not None
    assert 10.0 < a["distance_km"] < 10.2


def test_totali_non_a_zero(converted, tmp_path):
    """Il sintomo esatto del bug: tante sedute, totali a zero."""
    _, md_text, _ = converted
    for i in range(3):
        (tmp_path / f"activity_{i}.md").write_text(md_text)
    attivita = [quarter_split.read_activity_file(p) for p in sorted(tmp_path.glob("*.md"))]
    attivita = [a for a in attivita if a]
    assert len(attivita) == 3
    assert sum(a["distance_km"] for a in attivita) > 30
    assert sum(a["duration_s"] for a in attivita) > 12_000


def test_il_tempo_di_riferimento_e_quello_in_movimento(converted, tmp_path):
    _, md_text, _ = converted
    f = tmp_path / "activity_1.md"
    f.write_text(md_text)
    a = quarter_split.read_activity_file(f)
    assert a["duration_s"] == a["elapsed_s"] or a["duration_s"] < a["elapsed_s"]


# --- percorsi ---------------------------------------------------------------

def test_atleta_inesistente_da_errore_utile():
    import paths
    with pytest.raises(SystemExit) as e:
        paths.athlete_dir("nessuno_con_questo_nome")
    assert "non trovato" in str(e.value)


def test_il_template_non_e_un_atleta():
    import paths
    with pytest.raises(SystemExit) as e:
        paths.athlete_dir("_template")
    assert "modello" in str(e.value)


# --- fotografia dell'atleta (profile_stats) ---------------------------------

@pytest.fixture
def atleta_finto(tmp_path, converted, monkeypatch):
    """Un atleta con tre copie della fixture, a tre date diverse."""
    import profile_stats
    _, md_text, _ = converted
    root = tmp_path / "athletes" / "tizio"
    (root / "training_data" / "activities").mkdir(parents=True)
    for i, giorno in enumerate(("2026-09-01", "2026-09-05", "2026-09-10")):
        testo = md_text.replace("2026-04-06T08:36:22", f"{giorno}T08:00:00")
        (root / "training_data" / "activities" / f"activity_{i}.md").write_text(testo)

    import paths
    monkeypatch.setattr(paths, "ATHLETES_DIR", tmp_path / "athletes")
    monkeypatch.setattr(profile_stats.qs.paths, "ATHLETES_DIR", tmp_path / "athletes")
    return profile_stats


def test_fotografia_conta_e_somma(atleta_finto):
    d = atleta_finto.build("tizio")
    assert d["attivita_totali"] == 3
    assert d["periodo"]["da"] == "2026-09-01"
    assert d["periodo"]["a"] == "2026-09-10"
    # ~10 km per attivita', tre in nove giorni -> le 4 settimane non sono a zero
    assert d["volume"]["ultime_4_settimane"]["km_settimana"] > 5
    assert d["volume"]["ultime_4_settimane"]["attivita"] == 3


def test_fotografia_segnala_i_dati_assenti(atleta_finto):
    d = atleta_finto.build("tizio")
    testo = " ".join(d["dati_assenti"]).lower()
    assert "hrv" in testo
    assert "polso" in testo, "l'assenza del controllo sul cardio va dichiarata"


def test_fotografia_si_ancora_all_ultima_attivita(atleta_finto):
    """Le finestre finiscono con l'ultima attivita', non con oggi."""
    d = atleta_finto.build("tizio")
    assert d["periodo"]["ultima_attivita_giorni_fa"] >= 0
    assert d["volume"]["ultime_4_settimane"]["attivita"] == 3


def test_fotografia_senza_dati_da_errore_utile(tmp_path, monkeypatch):
    import paths
    import profile_stats
    (tmp_path / "athletes" / "vuoto").mkdir(parents=True)
    monkeypatch.setattr(paths, "ATHLETES_DIR", tmp_path / "athletes")
    with pytest.raises(SystemExit) as e:
        profile_stats.build("vuoto")
    assert "run_pipeline" in str(e.value), "l'errore deve dire come rimediare"


# --- codici sport sconosciuti ----------------------------------------------

def test_codice_sport_sconosciuto_e_riconoscibile():
    """Garmin usa codici che fitparse non sempre conosce: 'Type: 62' sarebbe
    letto dal coach come se fosse il nome di uno sport."""
    import fit_reader
    assert fit_reader._sport_name(62) == "sconosciuto_62"
    assert fit_reader._sport_name("running") == "running"
    assert fit_reader._sport_name(None) is None


# --- controllo del profilo (profile_check) ---------------------------------

@pytest.fixture
def profilo(tmp_path, monkeypatch):
    """Scrive un profilo e restituisce (check, scrivi)."""
    import paths
    import profile_check
    root = tmp_path / "athletes" / "tizio"
    root.mkdir(parents=True)
    monkeypatch.setattr(paths, "ATHLETES_DIR", tmp_path / "athletes")

    def scrivi(testo):
        (root / "profile.md").write_text(testo)
        return profile_check.check("tizio")

    return scrivi


BASE = """# Profilo — Tizio

## Goals

### Obiettivo Primario
- **Gara**: Una gara
- **Data**: {data}

### Obiettivi Secondari
| Gara | Data |
|------|------|
| altra | 2020-01-01 |

## Notes
- FC da polso: attendibile
- Giorni disponibili: 4
"""


def test_data_futura_va_bene(profilo):
    bloccanti, _ = profilo(BASE.format(data="2099-01-01"))
    assert bloccanti == []


def test_la_primaria_futura_vince_sulle_secondarie_passate(profilo):
    """La sezione Obiettivi contiene anche gare passate: non devono far
    scattare un falso allarme sulla primaria."""
    bloccanti, _ = profilo(BASE.format(data="2099-06-15"))
    assert bloccanti == [], "una secondaria passata non deve bloccare"


def test_tutte_le_date_passate_blocca(profilo):
    bloccanti, _ = profilo(BASE.format(data="2020-05-05"))
    assert len(bloccanti) == 1
    assert "passate" in bloccanti[0]


def test_nessuna_data_blocca(profilo):
    bloccanti, _ = profilo("# Profilo\n\n## Goals\n\n- **Gara**: boh\n")
    assert len(bloccanti) == 1
    assert "YYYY-MM-DD" in bloccanti[0]


def test_i_segnaposti_avvisano_ma_non_bloccano(profilo):
    bloccanti, avvisi = profilo(
        BASE.format(data="2099-01-01") + "\n- **Peso**: [kg]\n- **Sonno**: [ore/notte]\n")
    assert bloccanti == [], "campi opzionali non devono impedire un piano"
    assert any("modello" in a for a in avvisi)


def test_avvisa_se_manca_il_contesto_utile(profilo):
    _, avvisi = profilo("# Profilo\n\n## Goals\n- **Data**: 2099-01-01\n")
    testo = " ".join(avvisi)
    assert "polso" in testo
    assert "giorni" in testo


def test_profilo_assente_da_errore_utile(tmp_path, monkeypatch):
    import paths
    import profile_check
    (tmp_path / "athletes" / "senza").mkdir(parents=True)
    monkeypatch.setattr(paths, "ATHLETES_DIR", tmp_path / "athletes")
    with pytest.raises(SystemExit) as e:
        profile_check.check("senza")
    assert "_template" in str(e.value)


# --- dislivello ------------------------------------------------------------

def test_il_dislivello_viene_dal_dispositivo(converted):
    """Il valore dichiarato dall'orologio e' il riferimento: calcolato col
    barometro, e' meglio di qualunque ricalcolo dai campioni di quota."""
    summary, _, _ = converted
    if summary.get("fit_total_ascent_m") is None:
        pytest.skip("la fixture non dichiara il dislivello")
    assert summary["total_ascent_m_source"] == "device"
    assert summary["total_ascent_m"] == float(summary["fit_total_ascent_m"])


def test_il_ricalcolo_e_nello_stesso_ordine_di_grandezza(converted):
    """Il ripiego non deve essere assurdo: e' quello che usciva prima da
    'smoothed' (circa zero) e da 'raw' (rumore)."""
    summary, _, _ = converted
    dichiarato = summary.get("fit_total_ascent_m")
    stimato = summary.get("ascent_recomputed_m")
    if dichiarato is None or not dichiarato:
        pytest.skip("la fixture non dichiara il dislivello")
    scarto = abs(stimato - dichiarato) / dichiarato
    assert scarto < 0.35, f"ricalcolo fuori scala: {stimato} contro {dichiarato}"


def test_il_valore_stimato_e_dichiarato_tale(tmp_path):
    """Chi legge deve distinguere un dislivello misurato da uno stimato."""
    md, js = tmp_path / "s.md", tmp_path / "s.json"
    res = subprocess.run(
        [sys.executable, str(PIPELINE / "fit_to_markdown.py"), str(FIXTURE),
         str(md), "--json", str(js), "--ascent-method", "recomputed"],
        capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "stimato dai campioni di quota" in md.read_text()
    assert json.loads(js.read_text())["summary"]["total_ascent_m_source"] == "recomputed"


def test_i_picchi_di_quota_non_diventano_dislivello():
    """Un salto di quota impossibile fra due campioni e' un artefatto del
    sensore, non un gradino: perdita di fix GPS, galleria, ascensore."""
    import activity_metrics
    piatto = [{"altitude_m": 100.0} for _ in range(50)]
    piatto[25]["altitude_m"] = 900.0          # picco isolato
    ascesa, discesa = activity_metrics.compute_ascent_from_altitude(piatto)
    assert ascesa < 1.0, f"il picco e' finito nel dislivello: {ascesa} m"
    assert discesa < 1.0


def test_una_salita_vera_viene_contata():
    import activity_metrics
    salita = [{"altitude_m": 100.0 + i} for i in range(101)]   # +100 m regolari
    ascesa, discesa = activity_metrics.compute_ascent_from_altitude(salita)
    assert 99 <= ascesa <= 101, ascesa
    assert discesa < 1.0


def test_quote_mancanti_non_creano_salti():
    import activity_metrics
    con_buchi = [{"altitude_m": 100.0}] + [{"altitude_m": None}] * 20 + [{"altitude_m": 100.0}]
    ascesa, discesa = activity_metrics.compute_ascent_from_altitude(con_buchi)
    assert ascesa == 0.0 and discesa == 0.0


# --- split al chilometro ----------------------------------------------------

def test_gli_split_al_km_hanno_il_dislivello(converted):
    """Il file non contiene un dislivello per chilometro: viene ricalcolato
    sempre, anche outdoor. Se sparisse, il coach perderebbe il profilo della
    salita senza che niente segnali l'assenza."""
    _, _, full = converted
    splits = full.get("splits_km") or []
    if len(splits) < 3:
        pytest.skip("fixture troppo corta")
    con_dislivello = [s for s in splits if s.get("elevation_gain_m") is not None]
    assert len(con_dislivello) == len(splits)
    assert sum(s["elevation_gain_m"] for s in splits) > 0


def test_la_somma_degli_split_torna_col_totale(converted):
    """Gli split sono riscalati sul totale dell'attivita': se divergono, una
    delle due cifre che il coach legge e' sbagliata."""
    summary, _, full = converted
    splits = full.get("splits_km") or []
    totale = summary.get("total_ascent_m")
    if not splits or not totale:
        pytest.skip("dati insufficienti")
    somma = sum(s.get("elevation_gain_m") or 0 for s in splits)
    # gli split coprono i km interi: l'ultimo tratto parziale resta fuori
    assert somma <= totale * 1.1
    assert somma >= totale * 0.6


# --- riepilogo settimanale --------------------------------------------------

def test_il_riepilogo_raggruppa_per_lunedi():
    import weekly_rollup
    from datetime import datetime
    att = [
        {"date": datetime(2026, 9, 9), "distance_km": 10.0, "duration_s": 3600,
         "ascent_m": 100.0, "activity_type": "running"},
        {"date": datetime(2026, 9, 13), "distance_km": 5.0, "duration_s": 1800,
         "ascent_m": 50.0, "activity_type": "running"},
        {"date": datetime(2026, 9, 14), "distance_km": 7.0, "duration_s": 2400,
         "ascent_m": 0.0, "activity_type": "walking"},
    ]
    sett = weekly_rollup.raggruppa(att)
    from datetime import date
    assert set(sett) == {date(2026, 9, 7), date(2026, 9, 14)}
    prima = sett[date(2026, 9, 7)]
    assert prima["n"] == 2 and prima["n_corsa"] == 2
    assert prima["km"] == 15.0 and prima["lunga_km"] == 10.0
    seconda = sett[date(2026, 9, 14)]
    assert seconda["n_corsa"] == 0, "una camminata non e' una corsa"


def test_la_freccia_ha_una_soglia_morta():
    """Senza soglia ogni oscillazione naturale diventa una tendenza."""
    import weekly_rollup
    assert weekly_rollup.freccia(100, None) == " "
    assert weekly_rollup.freccia(103, 100) == "="
    assert weekly_rollup.freccia(120, 100) == "↑"
    assert weekly_rollup.freccia(80, 100) == "↓"


def test_il_riepilogo_segnala_le_settimane_vuote():
    import weekly_rollup
    from datetime import datetime
    att = [
        {"date": datetime(2026, 8, 3), "distance_km": 10.0, "duration_s": 3600,
         "ascent_m": 0.0, "activity_type": "running"},
        {"date": datetime(2026, 8, 24), "distance_km": 10.0, "duration_s": 3600,
         "ascent_m": 0.0, "activity_type": "running"},
    ]
    testo = weekly_rollup.render("tizio", att)
    assert "Settimane senza attività" in testo
    assert "2026-08-10" in testo and "2026-08-17" in testo


# --- controllo del piano settimanale (week_check) --------------------------

SETTIMANA_OK = """# Settimana 3 — Build | Obiettivo: Gara
**Date**: LUN 07/09 – DOM 13/09
**Settimane alla gara**: 9

## Piano Settimanale
| Giorno | Data  | Allenamento      | Distanza | Intensità | Stato |
|--------|-------|------------------|----------|-----------|-------|
| LUN    | 07/09 | Easy             | 6 km     | Z2        | ⬜ |
| MAR    | 08/09 | Soglia 3×10min   | 12 km    | Z4        | ⬜ |
| MER    | 09/09 | Easy recovery    | 6 km     | Z1        | ⬜ |
| GIO    | 10/09 | REST             | —        | —         | ⬜ |
| VEN    | 11/09 | Easy             | 6 km     | Z2        | ⬜ |
| SAB    | 12/09 | Long             | 18 km    | Z2        | ⬜ |
| DOM    | 13/09 | Recovery         | 6–8 km   | Z1        | ⬜ |

**Volume totale previsto**: 55 km
**Razionale**: terza settimana di Build, il blocco di soglia passa da 10 a 15
minuti mantenendo la stessa intensità; il long resta invariato per non sommare
due progressioni nella stessa settimana.

## Log Allenamenti Completati
## Aggiustamenti Attivi
## Chiusura Settimana
"""


@pytest.fixture
def settimana(tmp_path, monkeypatch):
    import paths
    import week_check
    root = tmp_path / "athletes" / "tizio" / "plans" / "weeks"
    root.mkdir(parents=True)
    monkeypatch.setattr(paths, "ATHLETES_DIR", tmp_path / "athletes")
    # senza attivita' convertite il confronto col carico reale si salta
    monkeypatch.setattr(week_check, "carico_recente", lambda p: None)

    def scrivi(testo, nome="week_2026-09-07.md"):
        f = root / nome
        f.write_text(testo)
        return week_check.check("tizio", f)

    return scrivi


def test_una_settimana_ben_fatta_passa(settimana):
    problemi, avvisi = settimana(SETTIMANA_OK)
    assert problemi == [], problemi
    assert avvisi == [], avvisi


def test_giorno_mancante(settimana):
    testo = "\n".join(r for r in SETTIMANA_OK.splitlines() if not r.startswith("| MER"))
    problemi, _ = settimana(testo)
    assert any("MER" in p for p in problemi)


def test_volume_che_non_torna(settimana):
    problemi, _ = settimana(SETTIMANA_OK.replace("previsto**: 55 km", "previsto**: 30 km"))
    assert any("non torna" in p for p in problemi)


def test_scarto_moderato_sul_volume_e_solo_un_avviso(settimana):
    """Il volume dichiarato e' prosa e a volte esclude qualcosa di proposito."""
    problemi, avvisi = settimana(SETTIMANA_OK.replace("previsto**: 55 km", "previsto**: 48 km"))
    assert problemi == []
    assert any("non torna" in a for a in avvisi)


def test_intervallo_di_distanza_vale_la_media():
    import week_check
    assert week_check.km_dalla_cella("6–8 km") == 7.0
    assert week_check.km_dalla_cella("~18 km") == 18.0
    assert week_check.km_dalla_cella("45 min") == 0.0


def test_la_distanza_si_legge_dalla_sua_colonna():
    """Cercando 'N km' in tutta la riga si prendeva anche quello che compare
    nella colonna Intensità, e il totale usciva gonfiato."""
    import week_check
    testo = (
        "| Giorno | Data | Allenamento | Distanza | Intensità | Stato |\n"
        "|---|---|---|---|---|---|\n"
        "| MAR | 08/09 | Ripetute | 12 km | 3×15min a 5 km/h di riferimento | ⬜ |\n"
    )
    righe = week_check.righe_piano(testo)
    assert len(righe) == 1
    assert week_check.km_dalla_cella(righe[0][2]) == 12.0


def test_sedute_intense_consecutive(settimana):
    testo = SETTIMANA_OK.replace("| MER    | 09/09 | Easy recovery    | 6 km     | Z1        | ⬜ |",
                                 "| MER    | 09/09 | Ripetute VO2max  | 8 km     | Z5        | ⬜ |")
    _, avvisi = settimana(testo)
    assert any("consecutive" in a for a in avvisi)


def test_sezione_mancante(settimana):
    problemi, _ = settimana(SETTIMANA_OK.replace("## Chiusura Settimana\n", ""))
    assert any("Chiusura Settimana" in p for p in problemi)


def test_data_fuori_settimana(settimana):
    _, avvisi = settimana(SETTIMANA_OK.replace("| DOM    | 13/09 |", "| DOM    | 20/09 |"))
    assert any("fuori dalla settimana" in a for a in avvisi)


def test_volume_fuori_scala_rispetto_al_carico_reale(tmp_path, monkeypatch):
    import paths
    import week_check
    root = tmp_path / "athletes" / "tizio" / "plans" / "weeks"
    root.mkdir(parents=True)
    monkeypatch.setattr(paths, "ATHLETES_DIR", tmp_path / "athletes")
    monkeypatch.setattr(week_check, "carico_recente", lambda p: 25.0)   # 25 km/sett
    f = root / "week_2026-09-07.md"
    f.write_text(SETTIMANA_OK)                                          # piano da 55 km
    problemi, _ = week_check.check("tizio", f)
    assert any("mediana recente" in p for p in problemi)


def test_il_markdown_e_il_prodotto(tmp_path):
    """Senza --json il converter non deve scrivere il dump da 1.2 MB."""
    md = tmp_path / "out.md"
    res = subprocess.run(
        [sys.executable, str(PIPELINE / "fit_to_markdown.py"), str(FIXTURE), str(md)],
        capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert md.exists() and md.stat().st_size > 500
    assert list(tmp_path.glob("*.json")) == []


# --- tempo per banda di frequenza e distribuzione per zona ------------------

def test_le_bande_fc_sono_pesate_sul_tempo():
    """Il campionamento non e' uniforme: un Instinct registra a 1 Hz, un Venu 2
    in modalita' smart salta a intervalli di 1-8 secondi. Contare i campioni
    darebbe al secondo un peso otto volte piu' basso sugli stessi minuti."""
    import activity_metrics
    from datetime import datetime, timedelta
    t0 = datetime(2026, 9, 1, 8, 0, 0)
    # 100 campioni a 1 Hz a 130 bpm, poi 50 campioni ogni 8 s a 170 bpm
    ts = [{"ts": t0 + timedelta(seconds=i), "heart_rate": 130} for i in range(100)]
    ts += [{"ts": t0 + timedelta(seconds=100 + 8 * i), "heart_rate": 170} for i in range(50)]
    bande = activity_metrics.compute_hr_bands(ts)
    assert bande is not None
    # ~99 s a 130 bpm contro ~392 s a 170: il secondo blocco deve pesare di piu'
    assert bande["130-140"] < bande["170-180"]
    assert 90 < bande["130-140"] < 110
    assert 350 < bande["170-180"] < 400


def test_le_pause_non_diventano_tempo_in_zona():
    import activity_metrics
    from datetime import datetime, timedelta
    t0 = datetime(2026, 9, 1, 8, 0, 0)
    ts = [{"ts": t0 + timedelta(seconds=i), "heart_rate": 150} for i in range(400)]
    # un buco di mezz'ora: non si stava misurando
    ts += [{"ts": t0 + timedelta(seconds=2200 + i), "heart_rate": 150} for i in range(400)]
    bande = activity_metrics.compute_hr_bands(ts)
    assert bande["150-160"] < 850, "il buco e' stato contato come tempo in zona"


def test_senza_frequenza_cardiaca_niente_bande():
    import activity_metrics
    from datetime import datetime, timedelta
    t0 = datetime(2026, 9, 1, 8, 0, 0)
    ts = [{"ts": t0 + timedelta(seconds=i), "heart_rate": None} for i in range(500)]
    assert activity_metrics.compute_hr_bands(ts) is None


def test_le_bande_finiscono_nel_riassunto(converted):
    _, md_text, summary_full = converted
    assert "Tempo per banda FC" in md_text
    assert summary_full["summary"].get("hr_bands_s")


def test_una_banda_a_cavallo_si_divide_fra_le_zone():
    """Una banda da 10 bpm puo' stare a cavallo di due zone: il tempo va diviso
    sulla parte che ricade in ciascuna, non assegnato tutto al bordo basso."""
    import profile_stats
    # FCmax 200 -> Z1 finisce a 144, Z2 parte da 144: la banda 140-150 e' a metà
    zone = profile_stats.bande_in_zone({"140-150": 1000}, 200)
    assert 350 < zone["Z1"] < 450
    assert 550 < zone["Z2"] < 650
    assert sum(zone.values()) == pytest.approx(1000, abs=2)


def test_le_zone_conservano_il_tempo_totale():
    import profile_stats
    bande = {"0-110": 100, "130-140": 400, "150-160": 900, "180+": 200}
    zone = profile_stats.bande_in_zone(bande, 195)
    assert sum(zone.values()) == pytest.approx(sum(bande.values()), abs=3)


def test_la_fc_massima_si_legge_dal_profilo(tmp_path, monkeypatch):
    import paths
    import profile_stats
    root = tmp_path / "athletes" / "tizio"
    root.mkdir(parents=True)
    monkeypatch.setattr(paths, "ATHLETES_DIR", tmp_path / "athletes")
    prof = root / "profile.md"

    prof.write_text("# Profilo\n\n- **FC massima**: 190\n")
    assert profile_stats.leggi_fc_massima("tizio") == 190

    prof.write_text("# Profilo\n\n- **FC massima**: n.d.\n")
    assert profile_stats.leggi_fc_massima("tizio") is None

    prof.write_text("# Profilo\n\n- **Max HR**: 205  <!-- osservata -->\n")
    assert profile_stats.leggi_fc_massima("tizio") == 205

    # valori impossibili: meglio niente che una zona sbagliata
    prof.write_text("# Profilo\n\n- **FC massima**: 45\n")
    assert profile_stats.leggi_fc_massima("tizio") is None


def test_il_riepilogo_dice_perche_mancano_le_zone():
    import weekly_rollup
    from datetime import datetime
    att = [{"date": datetime(2026, 9, 9), "distance_km": 10.0, "duration_s": 3600,
            "ascent_m": 0.0, "activity_type": "running",
            "hr_bands": {"140-150": 1800, "150-160": 1800}}]
    testo = weekly_rollup.render("tizio", att, fc_max=None)
    assert "manca la **FC massima**" in testo
    testo = weekly_rollup.render("tizio", att, fc_max=200)
    assert "Distribuzione per zona (FC massima 200 bpm)" in testo


# --- passo corretto per la pendenza (GAP) -----------------------------------

def _traccia(passo_s_km, gradiente, metri=3000, hr=150):
    """Traccia sintetica: passo costante, pendenza costante."""
    from datetime import datetime, timedelta
    t = datetime(2026, 9, 1, 8, 0, 0)
    pts, d, a = [], 0.0, 100.0
    while d < metri:
        pts.append({"ts": t, "distance_m": d, "altitude_m": a, "heart_rate": hr})
        t += timedelta(seconds=1)
        passo_m_s = 1000.0 / passo_s_km
        d += passo_m_s
        a += passo_m_s * gradiente
    return pts


def test_su_terreno_piatto_il_gap_coincide_col_passo():
    """E' il controllo che rende credibile tutto il resto: senza pendenza la
    correzione non deve correggere niente."""
    import activity_metrics
    seg = activity_metrics.segmenti_corretti(_traccia(300, 0.0))
    gap = activity_metrics.compute_grade_adjusted_pace(seg)
    assert gap == pytest.approx(300, abs=3)


def test_in_salita_il_gap_e_piu_veloce_del_passo():
    import activity_metrics
    seg = activity_metrics.segmenti_corretti(_traccia(420, 0.10))
    gap = activity_metrics.compute_grade_adjusted_pace(seg)
    assert gap < 420, "correndo in salita l'equivalente in piano deve essere piu' rapido"
    # al 10% il costo e' 1.66 volte quello in piano
    assert gap == pytest.approx(420 / 1.658, rel=0.08)


def test_in_discesa_il_gap_e_piu_lento_del_passo():
    import activity_metrics
    seg = activity_metrics.segmenti_corretti(_traccia(260, -0.10))
    gap = activity_metrics.compute_grade_adjusted_pace(seg)
    assert gap > 260, "in discesa si va piu' forte a parita' di costo"


def test_la_curva_ha_il_minimo_in_leggera_discesa():
    """Minetti: correre e' piu' economico attorno al -10%, non in piano."""
    import activity_metrics as F
    costi = {g: F.costo_energetico(g) for g in (-0.30, -0.20, -0.10, -0.05, 0.0, 0.10)}
    assert costi[-0.10] < costi[0.0]
    assert costi[-0.10] < costi[-0.30]
    assert costi[0.10] > costi[0.0]


def test_la_pendenza_e_limitata_all_intervallo_valido():
    """Oltre il 45% la curva di Minetti e' fuori dai dati su cui e' stata
    misurata: estrapolarla darebbe numeri inventati."""
    import activity_metrics as F
    assert F.costo_energetico(0.90) == F.costo_energetico(0.45)
    assert F.costo_energetico(-0.90) == F.costo_energetico(-0.45)


def test_le_soste_non_rallentano_il_passo_corretto():
    """Il GAP usa il tempo in movimento: una sosta dentro un segmento lo faceva
    sembrare piu' lento del passo reale anche in piano."""
    import activity_metrics
    from datetime import timedelta
    pts = _traccia(300, 0.0, metri=2000)
    # due minuti fermi a meta'
    meta = len(pts) // 2
    for q in pts[meta:]:
        q["ts"] += timedelta(seconds=120)
    seg = activity_metrics.segmenti_corretti(pts)
    gap = activity_metrics.compute_grade_adjusted_pace(seg)
    assert gap == pytest.approx(300, abs=15)


def test_il_decoupling_non_esce_su_terreno_ripido():
    """Misurato sull'archivio: col dislivello il decoupling cresce in modo
    monotono (piatto +3.9%, collinare +14.2%, montagna +21.8%), cioe' misura il
    terreno. La correzione metabolica non basta a renderlo confrontabile."""
    import activity_metrics
    seg = activity_metrics.segmenti_corretti(_traccia(420, 0.10, metri=6000))
    assert activity_metrics.compute_decoupling(
        seg, ascent_m=600, distance_m=6000) is None
    # lo stesso sforzo su terreno piatto lo produce
    seg_piatto = activity_metrics.segmenti_corretti(_traccia(300, 0.0, metri=6000))
    assert activity_metrics.compute_decoupling(
        seg_piatto, ascent_m=20, distance_m=6000) is not None


# --- attendibilita' della FC da polso ---------------------------------------

def test_la_attendibilita_del_polso_si_legge_dal_profilo(tmp_path, monkeypatch):
    import paths
    import profile_stats
    root = tmp_path / "athletes" / "tizio"
    root.mkdir(parents=True)
    monkeypatch.setattr(paths, "ATHLETES_DIR", tmp_path / "athletes")
    prof = root / "profile.md"
    for testo, atteso in (("- **FC da polso attendibile**: si\n", True),
                          ("- **FC da polso attendibile**: sì\n", True),
                          ("- **FC da polso attendibile**: no\n", False),
                          ("- **FC da polso attendibile**: n.d.\n", None),
                          ("niente\n", None)):
        prof.write_text("# Profilo\n\n" + testo)
        assert profile_stats.fc_polso_attendibile("tizio") is atteso, testo


def test_le_zone_avvisano_se_la_fc_e_inaffidabile():
    """Su un sensore con cadence lock la ripartizione sovrastima l'intensita':
    chi la legge e' un modello, e non lo sa se non glielo si dice."""
    import weekly_rollup
    from datetime import datetime
    att = [{"date": datetime(2026, 9, 9), "distance_km": 10.0, "duration_s": 3600,
            "ascent_m": 0.0, "activity_type": "running",
            "hr_bands": {"140-150": 1800, "160-170": 1800}}]
    con = weekly_rollup.render("tizio", att, fc_max=190, fc_polso_ok=False)
    assert "sovrastima l'intensità" in con
    senza = weekly_rollup.render("tizio", att, fc_max=190, fc_polso_ok=True)
    assert "sovrastima" not in senza
    # non verificato: avvisa comunque, ma dicendo che il test non e stato fatto
    ignoto = weekly_rollup.render("tizio", att, fc_max=190, fc_polso_ok=None)
    assert "Non è stato verificato" in ignoto
