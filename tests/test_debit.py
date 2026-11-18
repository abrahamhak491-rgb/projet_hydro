from pathlib import Path

import pandas as pd
import pytest

from calculs.debit import (
    CN_AMC2,
    C_PAR_OCCUPATION,
    GROUPES_SOL,
    OCCUPATIONS,
    c_pondere,
    cn_pondere,
    cn_selon_humidite,
    coefficient_majoration,
    comparer_debits,
    debit_pointe_scs,
    debit_rationnelle,
    pluie_nette_scs,
    retention_potentielle,
    temps_de_pointe_scs,
)
from calculs.idf import courbes_idf, pluies_depuis_journalier


def test_rationnelle_calcul_manuel():
    # 0,3 * 30 mm/h * 25 km² / 3,6 = 62,5 m³/s
    assert debit_rationnelle(0.3, 30, 25) == pytest.approx(62.5)


def test_scs_calcul_manuel():
    # CN = 75 : S = 84,667 mm, Ia = 16,933 mm ; P = 114,6 mm
    assert retention_potentielle(75) == pytest.approx(84.6667, abs=1e-3)
    q = pluie_nette_scs(114.6, 75)
    assert q == pytest.approx((114.6 - 16.9333) ** 2 / (114.6 - 16.9333 + 84.6667), rel=1e-6)
    assert q == pytest.approx(52.3, abs=0.1)
    # Tp = D/2 + 0,6 tc ; avec D = tc = 3,82 h : 4,202 h
    assert temps_de_pointe_scs(3.82, 3.82) == pytest.approx(1.1 * 3.82)
    qp, tp = debit_pointe_scs(q, 25, 3.82, 3.82)
    assert qp == pytest.approx(0.208 * 25 * q / tp)


def test_pas_de_ruissellement_sous_labstraction_initiale():
    assert pluie_nette_scs(10.0, 75) == 0.0  # Ia = 16,9 mm
    assert pluie_nette_scs(0.0, 75) == 0.0


def test_pluie_nette_croit_avec_p_et_cn():
    assert pluie_nette_scs(100, 80) > pluie_nette_scs(60, 80)
    assert pluie_nette_scs(100, 85) > pluie_nette_scs(100, 70)
    assert pluie_nette_scs(100, 100) == pytest.approx(100.0)  # surface imperméable : tout ruisselle


def test_cn_selon_humidite():
    assert cn_selon_humidite(75, "II") == 75
    assert cn_selon_humidite(75, "I") == pytest.approx(4.2 * 75 / (10 - 0.058 * 75))
    assert cn_selon_humidite(75, "I") < 75 < cn_selon_humidite(75, "III")
    with pytest.raises(ValueError):
        cn_selon_humidite(75, "IV")


def test_moyennes_ponderees():
    occ = {"Forêt": 0.5, "Culture": 0.5}
    assert c_pondere(occ) == pytest.approx(0.5 * 0.15 + 0.5 * 0.35)
    assert cn_pondere(occ, "B") == pytest.approx(0.5 * 55 + 0.5 * 78)
    assert c_pondere(occ, {"Forêt": 0.2, "Culture": 0.4}) == pytest.approx(0.3)  # table personnalisée


def test_pondere_exige_des_fractions_valides():
    with pytest.raises(ValueError):
        c_pondere({})
    with pytest.raises(ValueError):
        c_pondere({"Forêt": 0.5})
    with pytest.raises(ValueError):
        cn_pondere({"Forêt": 1.0}, "Z")


def test_majoration_de_c():
    assert [coefficient_majoration(t) for t in (2, 10, 25, 50, 100, 500)] == [1.0, 1.0, 1.1, 1.2, 1.25, 1.25]


def test_tables_completes_et_coherentes():
    assert set(C_PAR_OCCUPATION) == set(OCCUPATIONS) == set(CN_AMC2)
    for occ, groupes in CN_AMC2.items():
        assert set(groupes) == set(GROUPES_SOL)
        valeurs = [groupes[g] for g in "ABCD"]
        assert valeurs == sorted(valeurs), f"CN doit croître de A à D pour {occ}"
    assert all(0 < c <= 1 for c in C_PAR_OCCUPATION.values())


def test_occupations_identiques_a_la_page_bassin():
    page = (Path(__file__).resolve().parent.parent / "pages" / "1_Bassin.py")
    if not page.exists():
        pytest.skip("page Bassin absente")
    texte = page.read_text(encoding="utf-8")
    for nom in OCCUPATIONS:
        assert f'"{nom}"' in texte, f"« {nom} » absent de la page Bassin"


def test_valeurs_invalides():
    with pytest.raises(ValueError):
        debit_rationnelle(1.5, 30, 25)
    with pytest.raises(ValueError):
        debit_rationnelle(0.3, 0, 25)
    with pytest.raises(ValueError):
        retention_potentielle(0)
    with pytest.raises(ValueError):
        pluie_nette_scs(100, 75, lam=0.5)


def test_comparer_debits_coherent_avec_les_formules():
    pluies = pluies_depuis_journalier({10.0: 100.0, 100.0: 140.0}, [0.5, 1, 3, 6, 24], b=0.65)
    _, montana = courbes_idf(pluies)
    res = comparer_debits(montana, surface_km2=25, tc_h=3.82, c=0.3, cn=75)
    assert list(res["T (ans)"]) == [10.0, 100.0]
    i10 = montana.loc[0, "a (t en h)"] * 3.82 ** (-0.65)
    assert res.loc[0, "Q rationnelle (m³/s)"] == pytest.approx(0.3 * i10 * 25 / 3.6)
    # débits croissants avec la période de retour, pour les deux méthodes
    assert res.loc[1, "Q rationnelle (m³/s)"] > res.loc[0, "Q rationnelle (m³/s)"]
    assert res.loc[1, "Q SCS-CN (m³/s)"] > res.loc[0, "Q SCS-CN (m³/s)"]
    # majoration de C : T = 100 ans multiplie C par 1,25, T = 10 ans reste inchangé
    maj = comparer_debits(montana, 25, 3.82, 0.3, 75, majorer_c=True)
    assert maj.loc[0, "C utilisé"] == pytest.approx(0.3)
    assert maj.loc[1, "C utilisé"] == pytest.approx(0.375)
    # C plafonné à 1
    assert comparer_debits(montana, 25, 3.82, 0.9, 75, majorer_c=True).loc[1, "C utilisé"] == 1.0


def test_duree_de_pluie_modifie_la_methode_scs_seulement():
    pluies = pluies_depuis_journalier({10.0: 100.0}, [0.5, 1, 3, 6, 24], b=0.65)
    _, montana = courbes_idf(pluies)
    r1 = comparer_debits(montana, 25, 3.0, 0.3, 75, duree_pluie_h=3.0)
    r2 = comparer_debits(montana, 25, 3.0, 0.3, 75, duree_pluie_h=6.0)
    assert r1.loc[0, "Q rationnelle (m³/s)"] == pytest.approx(r2.loc[0, "Q rationnelle (m³/s)"])
    assert r2.loc[0, "Pluie nette (mm)"] > r1.loc[0, "Pluie nette (mm)"]
    assert r2.loc[0, "Tp (h)"] > r1.loc[0, "Tp (h)"]
