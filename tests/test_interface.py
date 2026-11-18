from pathlib import Path

from streamlit.testing.v1 import AppTest

from interface import etapes_realisees

from .conftest import fabriquer_etat

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_etapes_realisees(etat_complet):
    assert [ok for _, ok in etapes_realisees({})] == [False] * 6
    assert [ok for _, ok in etapes_realisees(etat_complet)] == [True] * 6
    assert [ok for _, ok in etapes_realisees({"bassin": etat_complet["bassin"], "tc_h": 3.8})] == [True] + [False] * 5


def test_accueil_vide():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert sum(m.value.startswith("####") for m in at.markdown) == 7  # une carte par page
    assert sum("À faire" in m.value for m in at.markdown) == 6


def test_accueil_et_pages_avec_resultats():
    at = AppTest.from_file(APP, default_timeout=120)
    for cle, valeur in fabriquer_etat().items():
        at.session_state[cle] = valeur
    at.run()
    assert not at.exception
    assert sum("Terminée" in m.value for m in at.markdown) == 6
    for page in ("1_Bassin", "2_Donnees_pluie", "3_Ajustement", "4_IDF", "5_Debit_pointe", "6_Hydrogramme", "7_Rapport"):
        at.switch_page(f"pages/{page}.py").run()
        assert not at.exception, page
