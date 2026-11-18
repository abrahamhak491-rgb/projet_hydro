import math

import pytest

from calculs.bassin import (
    Bassin,
    tc_giandotti,
    tc_kirpich,
    tc_passini,
    tc_toutes_methodes,
    temps_concentration,
)


def test_kirpich_calcul_manuel():
    # L = 5 km, S = 0,02 : 0,0195 * 5000^0,77 * 0,02^-0,385 = 61,96 min
    attendu_min = 0.0195 * (5000**0.77) * (0.02**-0.385)
    assert tc_kirpich(5, 0.02) == pytest.approx(attendu_min / 60)
    assert tc_kirpich(5, 0.02) * 60 == pytest.approx(61.96, abs=0.05)


def test_giandotti_calcul_manuel():
    # A = 100 km², L = 20 km, H = 400 m : (4*10 + 30) / (0,8*20) = 4,375 h
    assert tc_giandotti(100, 20, 400) == pytest.approx(4.375)


def test_passini_calcul_manuel():
    # A = 100, L = 20, S = 0,01 : 0,108 * 2000^(1/3) / 0,1
    attendu = 0.108 * 2000 ** (1 / 3) / 0.1
    assert tc_passini(100, 20, 0.01) == pytest.approx(attendu)


def test_tc_diminue_quand_la_pente_augmente():
    assert tc_kirpich(5, 0.05) < tc_kirpich(5, 0.01)
    assert tc_passini(10, 5, 0.05) < tc_passini(10, 5, 0.01)


def test_giandotti_demande_le_denivele():
    b = Bassin("test", 10, 5, 0.02)
    with pytest.raises(ValueError):
        temps_concentration(b, "giandotti")
    assert set(tc_toutes_methodes(b)) == {"kirpich", "passini"}


def test_toutes_methodes_avec_denivele():
    b = Bassin("test", 10, 5, 0.02, denivele_m=120)
    assert set(tc_toutes_methodes(b)) == {"kirpich", "giandotti", "passini"}


def test_methode_inconnue():
    with pytest.raises(ValueError):
        temps_concentration(Bassin("t", 10, 5, 0.02), "inconnue")


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(surface_km2=0, longueur_km=5, pente=0.02),
        dict(surface_km2=10, longueur_km=-1, pente=0.02),
        dict(surface_km2=10, longueur_km=5, pente=0),
        dict(surface_km2=10, longueur_km=5, pente=2),  # pente en % saisie par erreur
    ],
)
def test_donnees_invalides(kwargs):
    with pytest.raises(ValueError):
        Bassin("t", **kwargs)


def test_occupation_du_sol_doit_totaliser_un():
    Bassin("t", 10, 5, 0.02, occupation_sol={"forêt": 0.4, "culture": 0.6})
    with pytest.raises(ValueError):
        Bassin("t", 10, 5, 0.02, occupation_sol={"forêt": 0.4, "culture": 0.4})
