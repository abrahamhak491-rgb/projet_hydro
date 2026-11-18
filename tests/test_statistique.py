import numpy as np
import pytest
from scipy import stats

from calculs.statistique import (
    ajuster,
    avertissement_extrapolation,
    comparer_lois,
    meilleure_loi,
    positions_empiriques,
)

MU, SIGMA = 80.0, 20.0


@pytest.fixture(scope="module")
def echantillon_gumbel():
    return stats.gumbel_r.rvs(loc=MU, scale=SIGMA, size=3000, random_state=42)


def quantile_theorique(t):
    return MU - SIGMA * np.log(-np.log(1 - 1 / t))


def test_gumbel_retrouve_les_parametres(echantillon_gumbel):
    for methode in ("mv", "moments"):
        aj = ajuster(echantillon_gumbel, "gumbel", methode)
        assert aj.parametres["mu"] == pytest.approx(MU, rel=0.03)
        assert aj.parametres["sigma"] == pytest.approx(SIGMA, rel=0.05)


def test_quantiles_proches_de_la_theorie(echantillon_gumbel):
    for loi in ("gumbel", "gev"):
        aj = ajuster(echantillon_gumbel, loi)
        for t in (10, 100):
            assert aj.quantile(t) == pytest.approx(quantile_theorique(t), rel=0.05)


def test_gev_forme_proche_de_zero_pour_des_donnees_gumbel(echantillon_gumbel):
    aj = ajuster(echantillon_gumbel, "gev")
    assert abs(aj.parametres["xi"]) < 0.06


def test_galton_retrouve_les_parametres():
    x = stats.lognorm.rvs(s=0.3, scale=np.exp(4.4), size=3000, random_state=7)
    for methode in ("mv", "moments"):
        aj = ajuster(x, "galton", methode)
        assert aj.parametres["mu_ln"] == pytest.approx(4.4, abs=0.03)
        assert aj.parametres["sigma_ln"] == pytest.approx(0.3, abs=0.03)


def test_quantile_et_periode_retour_sont_reciproques(echantillon_gumbel):
    aj = ajuster(echantillon_gumbel, "gumbel")
    assert aj.periode_retour(aj.quantile(50)) == pytest.approx(50)
    q = aj.quantile([2, 10, 100])
    assert q[0] < q[1] < q[2]


def test_periode_retour_invalide(echantillon_gumbel):
    with pytest.raises(ValueError):
        ajuster(echantillon_gumbel, "gumbel").quantile(1)


def test_adequation_acceptee_pour_la_bonne_loi(echantillon_gumbel):
    assert ajuster(echantillon_gumbel, "gumbel").accepte


def test_adequation_rejetee_pour_une_mauvaise_loi():
    # Données uniformes : ni Gumbel ni Galton ne conviennent sur un grand échantillon.
    x = np.random.default_rng(3).uniform(50, 150, 1000)
    assert not ajuster(x, "gumbel").accepte
    assert not ajuster(x, "galton").accepte


def test_comparer_lois_sur_serie_realiste():
    x = stats.gumbel_r.rvs(loc=MU, scale=SIGMA, size=30, random_state=11)
    quantiles, tests, ajustements = comparer_lois(x)
    assert list(quantiles.columns) == ["Gumbel", "GEV", "Galton (log-normale)"]
    assert list(quantiles.index) == [2, 5, 10, 20, 50, 100]
    assert (quantiles.diff().dropna() > 0).all().all()  # croissants avec T
    assert len(tests) == 3
    nom, accepte = meilleure_loi(ajustements)
    assert nom in ajustements and accepte


def test_gev_refuse_les_moments(echantillon_gumbel):
    with pytest.raises(ValueError):
        ajuster(echantillon_gumbel, "gev", "moments")


def test_comparer_lois_avec_moments_n_echoue_pas():
    x = stats.gumbel_r.rvs(loc=MU, scale=SIGMA, size=30, random_state=5)
    quantiles, tests, aj = comparer_lois(x, methode="moments")
    assert len(aj) == 3


def test_trop_peu_de_donnees():
    with pytest.raises(ValueError):
        ajuster([80, 90, 100], "gumbel")


def test_galton_refuse_les_valeurs_negatives():
    with pytest.raises(ValueError):
        ajuster([-1, 5, 6, 7, 8, 9], "galton")


def test_positions_empiriques():
    p = positions_empiriques([30, 10, 20, 50, 40])
    assert list(p["valeur"]) == [10, 20, 30, 40, 50]
    assert p["periode_retour"].iloc[-1] == pytest.approx(6.0)  # 1/(1 - 5/6)
    assert (p["periode_retour"].diff().dropna() > 0).all()


def test_avertissement_extrapolation():
    assert avertissement_extrapolation(30, 100) is not None
    assert avertissement_extrapolation(30, 50) is None
