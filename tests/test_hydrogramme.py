import numpy as np
import pytest

from calculs.hydrogramme import (
    HU_SCS,
    hydrogramme_nash,
    hydrogramme_scs,
    k_depuis_retard,
    pas_automatique,
    proprietes,
    temps_de_pointe_scs,
)

A, TC, D, Q = 25.0, 3.82, 3.82, 52.3  # surface (km²), tc (h), durée de pluie (h), pluie nette (mm)


def test_table_scs_est_coherente():
    t, q = HU_SCS[:, 0], HU_SCS[:, 1]
    assert (np.diff(t) > 0).all()
    assert q.max() == 1.0 and t[np.argmax(q)] == 1.0
    assert q[0] == 0 and q[-1] == 0
    # aire sous la courbe = 2,67 / 2 (facteur de pointe 484), à 0,5 % près
    assert (getattr(np, "trapezoid", None) or np.trapz)(q, t) == pytest.approx(2.67 / 2, rel=0.005)


@pytest.mark.parametrize("forme", ["curviligne", "triangulaire"])
def test_scs_pointe_et_volume(forme):
    h = hydrogramme_scs(Q, A, TC, D, forme)
    p = proprietes(h, A, Q)
    tp = temps_de_pointe_scs(TC, D)
    qp = 0.208 * A * Q / tp
    assert p["Qp (m³/s)"] == pytest.approx(qp, rel=0.02)   # le pas de temps peut manquer la pointe exacte de peu
    assert p["Temps de pointe (h)"] == pytest.approx(tp, abs=0.2)
    assert p["Rapport des volumes"] == pytest.approx(1.0, abs=0.02)
    assert h["Débit (m³/s)"].iloc[0] == 0
    assert (h["Débit (m³/s)"] >= 0).all()


def test_scs_pas_fin_donne_la_pointe_exacte():
    tp = temps_de_pointe_scs(TC, D)
    h = hydrogramme_scs(Q, A, TC, D, "triangulaire", pas_h=tp / 50)  # pas qui tombe exactement sur Tp
    assert proprietes(h, A, Q)["Qp (m³/s)"] == pytest.approx(0.208 * A * Q / tp, rel=1e-6)


def test_scs_proportionnel_a_la_pluie_nette():
    p1 = proprietes(hydrogramme_scs(20, A, TC, D), A, 20)["Qp (m³/s)"]
    p2 = proprietes(hydrogramme_scs(40, A, TC, D), A, 40)["Qp (m³/s)"]
    assert p2 == pytest.approx(2 * p1)


def test_nash_conserve_le_volume():
    n = 3.0
    h = hydrogramme_nash(Q, A, D, n, k_depuis_retard(n, TC))
    p = proprietes(h, A, Q)
    assert p["Rapport des volumes"] == pytest.approx(1.0, abs=0.01)
    assert (h["Débit (m³/s)"] >= 0).all() and h["Débit (m³/s)"].iloc[0] == 0


def test_nash_reservoir_lineaire_pointe_a_la_fin_de_la_pluie():
    # n = 1 : le débit croît pendant la pluie, puis décroît : pointe à t = D
    h = hydrogramme_nash(Q, A, D, 1.0, 1.0, pas_h=0.01)
    assert proprietes(h, A, Q)["Temps de pointe (h)"] == pytest.approx(D, abs=0.02)


def test_nash_pointe_plus_basse_et_plus_tardive_avec_k_plus_grand():
    h1 = proprietes(hydrogramme_nash(Q, A, D, 3, 0.5), A, Q)
    h2 = proprietes(hydrogramme_nash(Q, A, D, 3, 1.5), A, Q)
    assert h2["Qp (m³/s)"] < h1["Qp (m³/s)"]
    assert h2["Temps de pointe (h)"] > h1["Temps de pointe (h)"]


def test_nash_et_scs_ont_des_pointes_du_meme_ordre():
    n = 3.0
    q_nash = proprietes(hydrogramme_nash(Q, A, D, n, k_depuis_retard(n, TC)), A, Q)["Qp (m³/s)"]
    q_scs = proprietes(hydrogramme_scs(Q, A, TC, D), A, Q)["Qp (m³/s)"]
    assert 0.6 < q_nash / q_scs < 1.4


def test_pluie_nette_nulle_donne_un_hydrogramme_nul():
    assert (hydrogramme_scs(0, A, TC, D)["Débit (m³/s)"] == 0).all()
    assert (hydrogramme_nash(0, A, D, 3, 0.7)["Débit (m³/s)"] == 0).all()


def test_pas_automatique():
    assert pas_automatique(4.2) == pytest.approx(15 / 60)
    assert pas_automatique(0.2) == pytest.approx(1 / 60)
    assert pas_automatique(100) == pytest.approx(1.0)


def test_valeurs_invalides():
    with pytest.raises(ValueError):
        hydrogramme_scs(-1, A, TC, D)
    with pytest.raises(ValueError):
        hydrogramme_scs(Q, A, TC, D, forme="ronde")
    with pytest.raises(ValueError):
        hydrogramme_nash(Q, A, D, 0, 1)
    with pytest.raises(ValueError):
        hydrogramme_nash(Q, A, D, 3, 1, pas_h=0)
    with pytest.raises(ValueError):
        k_depuis_retard(0, TC)
