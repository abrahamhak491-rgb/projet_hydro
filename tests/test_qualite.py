import io

import numpy as np
import pandas as pd

from calculs.qualite import (
    controler_qualite,
    convertir_dates,
    convertir_numerique,
    lire_fichier,
    maxima_annuels,
    nettoyer,
)


def test_lecture_csv_point_virgule_virgule_decimale():
    contenu = "annee;pluie\n2000;85,5\n2001;92,0\n2002;-999\n".encode("utf-8")
    df = lire_fichier(io.BytesIO(contenu), nom="pluies.csv")
    assert list(df.columns) == ["annee", "pluie"]
    valeurs = convertir_numerique(df["pluie"])
    assert valeurs.iloc[0] == 85.5
    assert np.isnan(valeurs.iloc[2])  # -999 = donnée absente


def test_lecture_csv_virgule_et_latin1():
    contenu = "année,pluie\n2000,85.5\n2001,92.0\n".encode("latin-1")
    df = lire_fichier(io.BytesIO(contenu), nom="p.csv")
    assert len(df) == 2


def test_lecture_excel(tmp_path):
    chemin = tmp_path / "pluies.xlsx"
    pd.DataFrame({"annee": [2000, 2001], "pluie": [85.5, 92.0]}).to_excel(chemin, index=False)
    df = lire_fichier(str(chemin))
    assert len(df) == 2


def test_format_non_supporte():
    try:
        lire_fichier(io.BytesIO(b"x"), nom="fichier.pdf")
    except ValueError:
        return
    raise AssertionError("Une ValueError était attendue")


def test_dates_jour_en_premier():
    d = convertir_dates(pd.Series(["03/04/2001", "2002-05-06"]))
    assert d.iloc[0].month == 4 and d.iloc[0].day == 3
    assert d.iloc[1].month == 5 and d.iloc[1].day == 6


def test_maxima_annuels_et_annees_incompletes():
    dates = pd.date_range("2000-01-01", "2002-06-30", freq="D")
    valeurs = pd.Series(np.arange(len(dates), dtype=float) % 50)
    valeurs.iloc[10] = 120.0  # pic en 2000
    res = maxima_annuels(pd.Series(dates), valeurs, min_jours_par_an=300)
    assert list(res["annee"]) == [2000, 2001]  # 2002 est incomplète
    assert res.loc[res["annee"] == 2000, "maximum"].iloc[0] == 120.0
    res_tout = maxima_annuels(pd.Series(dates), valeurs, exclure_incomplets=False)
    assert list(res_tout["annee"]) == [2000, 2001, 2002]


def test_controle_serie_propre():
    rng = np.random.default_rng(0)
    v = pd.Series(rng.gumbel(80, 15, 30))
    r = controler_qualite(v, annees=pd.Series(range(1990, 2020)))
    assert r.utilisable
    assert r.n_valides == 30
    assert r.annees_manquantes == []


def test_controle_detecte_les_problemes():
    v = pd.Series([80, 90, np.nan, -5, 0, 85, 95, 88, 92, 83, 87, 400.0])
    annees = pd.Series([1990, 1991, 1992, 1993, 1994, 1996, 1997, 1998, 1999, 2000, 2000, 2001])
    r = controler_qualite(v, annees=annees)
    assert r.n_manquants == 1
    assert r.n_negatifs == 1
    assert r.n_nuls == 1
    assert 1995 in r.annees_manquantes
    assert r.annees_en_double == [2000]
    assert not r.utilisable  # année en double = erreur bloquante
    assert 11 in r.indices_aberrants  # le 400 mm


def test_serie_trop_courte_bloque():
    r = controler_qualite(pd.Series([80.0, 90.0, 85.0]))
    assert not r.utilisable


def test_serie_courte_avertit_sans_bloquer():
    rng = np.random.default_rng(1)
    r = controler_qualite(pd.Series(rng.gumbel(80, 15, 12)))
    assert r.utilisable
    assert any("courte" in texte for _, texte in r.messages)


def test_nettoyer_ne_supprime_les_aberrants_que_sur_demande():
    v = pd.Series([80, 90, 85, 95, 88, 92, 83, 87, 90, 400.0, np.nan])
    r = controler_qualite(v)
    assert len(nettoyer(v, r)) == 10
    assert len(nettoyer(v, r, exclure_aberrants=True)) == 9
