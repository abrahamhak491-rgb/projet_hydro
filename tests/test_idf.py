import math

import numpy as np
import pytest
from scipy import stats

from calculs.idf import (
    a_en_minutes,
    ajuster_montana,
    colonnes_durees,
    courbes_idf,
    exposant_depuis_rapport,
    intensite,
    intensite_de_projet,
    lire_duree,
    pluie_depuis_journaliere,
    pluies_depuis_courtes_durees,
    pluies_depuis_journalier,
)


def test_a_depuis_journalier_reproduit_p24():
    # P24 = 100 mm, b = 0,65 : l'intensité sur 24 h doit valoir 100/24 mm/h
    assert pluie_depuis_journaliere(100, 24, 0.65) == pytest.approx(100.0)
    a_h = 100 / 24 ** (1 - 0.65)
    assert intensite(a_h, 0.65, 24) == pytest.approx(100 / 24)


def test_courbes_idf_retrouvent_b_impose():
    p24 = {10: 100.0, 50: 140.0}
    pluies = pluies_depuis_journalier(p24, [0.5, 1, 2, 6, 24], b=0.65)
    intensites, montana = courbes_idf(pluies)
    assert montana["b"].tolist() == pytest.approx([0.65, 0.65])
    assert montana["R²"].tolist() == pytest.approx([1.0, 1.0])
    assert montana["a (t en h)"].tolist() == pytest.approx([100 / 24**0.35, 140 / 24**0.35])
    # intensité décroissante avec la durée, croissante avec T
    assert (intensites[10].diff().dropna() < 0).all()
    assert (intensites[50] > intensites[10]).all()


def test_facteur_de_correction():
    assert pluie_depuis_journaliere(100, 24, 0.65, facteur=1.13) == pytest.approx(113.0)


def test_exposant_depuis_rapport():
    b = exposant_depuis_rapport(0.35)
    assert pluie_depuis_journaliere(100, 1, b) == pytest.approx(35.0)
    with pytest.raises(ValueError):
        exposant_depuis_rapport(1.2)


def test_ajuster_montana_loi_puissance_exacte():
    t = np.array([0.25, 1, 3, 12, 24])
    a, b, r2 = ajuster_montana(t, 40 * t**-0.7)
    assert (a, b, r2) == pytest.approx((40, 0.7, 1.0))


def test_a_en_minutes_coherent():
    a_h, b = 30.0, 0.65
    a_min = a_en_minutes(a_h, b)
    assert a_min * 90**-b == pytest.approx(intensite(a_h, b, 1.5))  # 90 min = 1,5 h


def test_parametres_invalides():
    with pytest.raises(ValueError):
        pluie_depuis_journaliere(100, 1, b=1.2)
    with pytest.raises(ValueError):
        pluie_depuis_journaliere(100, 0, b=0.6)
    with pytest.raises(ValueError):
        ajuster_montana([1, 1], [5, 5])
    with pytest.raises(ValueError):
        ajuster_montana([1], [5])


@pytest.mark.parametrize(
    "nom, attendu",
    [("15 min", 0.25), ("30mn", 0.5), ("1 h", 1.0), ("24h", 24.0), ("1,5 h", 1.5), ("Annee", None), ("2", None), ("1440 minutes", 24.0)],
)
def test_lire_duree(nom, attendu):
    assert lire_duree(nom) == (pytest.approx(attendu) if attendu is not None else None)


def test_colonnes_durees_ignore_les_autres_colonnes():
    assert colonnes_durees(["Annee", "15 min", "1 h", "24 h"]) == {"15 min": 0.25, "1 h": 1.0, "24 h": 24.0}


def test_courtes_durees_retrouvent_le_b_simule():
    rng = np.random.default_rng(4)
    p24 = stats.gumbel_r.rvs(loc=75, scale=18, size=400, random_state=8)
    durees = [0.25, 0.5, 1, 2, 6, 24]
    maxima = {t: p24 * (t / 24) ** 0.35 * np.exp(rng.normal(0, 0.03, len(p24))) for t in durees}
    pluies = pluies_depuis_courtes_durees(maxima, "gumbel", [10, 50])
    assert list(pluies.index) == durees and list(pluies.columns) == [10.0, 50.0]
    _, montana = courbes_idf(pluies)
    assert montana["b"].tolist() == pytest.approx([0.65, 0.65], abs=0.03)
    assert (montana["R²"] > 0.99).all()


def test_intensite_de_projet():
    pluies = pluies_depuis_journalier({10: 100.0, 50: 140.0}, [1, 3, 6, 24], b=0.65)
    _, montana = courbes_idf(pluies)
    assert intensite_de_projet(montana, 10, 24.0) == pytest.approx(100 / 24)
    assert intensite_de_projet(montana, 50, 3.0) == pytest.approx(pluie_depuis_journaliere(140, 3, 0.65) / 3)
    with pytest.raises(ValueError):
        intensite_de_projet(montana, 100, 3.0)
