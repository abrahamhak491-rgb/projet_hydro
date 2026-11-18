import io
import zipfile

import pandas as pd
from docx import Document

from calculs.graphiques import toutes_les_figures
from calculs.rapport import construire_rapport_word, exporter_excel, exporter_graphiques_zip

from .conftest import fabriquer_etat


def _texte(doc: Document) -> str:
    morceaux = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for ligne in t.rows:
            morceaux.extend(c.text for c in ligne.cells)
    return "\n".join(morceaux)


def test_rapport_complet(etat_complet):
    octets = construire_rapport_word(etat_complet, titre="Rapport test", auteurs="A. Étudiant", etablissement="ENSP")
    doc = Document(io.BytesIO(octets))
    titres = [p.text for p in doc.paragraphs if p.style.name == "Heading 1"]
    assert titres == [
        "1. Synthèse des résultats", "2. Bassin versant", "3. Données pluviométriques", "4. Ajustement statistique",
        "5. Courbes Intensité-Durée-Fréquence", "6. Débit de pointe", "7. Hydrogramme de crue", "8. Hypothèses et limites",
    ]
    assert len(doc.inline_shapes) == 5          # une figure par étape de calcul
    assert len(doc.tables) >= 10
    texte = _texte(doc)
    assert "Rapport test" in texte and "A. Étudiant" in texte and "Mayo Exemple" in texte
    assert "Étape non réalisée" not in texte
    assert "FICTIVES" not in texte               # données non fictives : pas d'avertissement
    # format français des nombres : virgule décimale
    assert "25,00 km²" in texte
    s = doc.sections[0]
    assert round(s.page_width.cm, 1) == 21.0     # A4


def test_donnees_fictives_signalees():
    doc = Document(io.BytesIO(construire_rapport_word(fabriquer_etat(source="exemple fictif"))))
    assert "FICTIVES" in _texte(doc)


def test_rapport_partiel_ne_plante_pas(etat_complet):
    partiel = {"bassin": etat_complet["bassin"], "tc_h": 3.82, "tc_methode": "kirpich"}
    doc = Document(io.BytesIO(construire_rapport_word(partiel)))
    texte = _texte(doc)
    assert texte.count("Étape non réalisée") == 5  # pluies, ajustement, IDF, débit, hydrogramme
    assert "Kirpich" in texte
    assert len(doc.inline_shapes) == 0


def test_rapport_completement_vide():
    doc = Document(io.BytesIO(construire_rapport_word({})))
    assert "Aucun résultat disponible" in _texte(doc)


def test_figures_disponibles(etat_complet):
    assert sorted(toutes_les_figures(etat_complet)) == [
        "01_maxima_annuels", "02_ajustement_lois", "03_courbes_idf", "04_debits_de_pointe", "05_hydrogramme",
    ]
    assert toutes_les_figures({}) == {}
    assert sorted(toutes_les_figures({"maxima": etat_complet["maxima"]})) == ["01_maxima_annuels"]


def test_export_zip_de_graphiques(etat_complet):
    with zipfile.ZipFile(io.BytesIO(exporter_graphiques_zip(etat_complet))) as z:
        noms = z.namelist()
        assert len(noms) == 5 and all(n.endswith(".png") for n in noms)
        assert z.read(noms[0])[:8] == b"\x89PNG\r\n\x1a\n"


def test_export_excel(etat_complet):
    classeur = pd.ExcelFile(io.BytesIO(exporter_excel(etat_complet)))
    assert {"Bassin", "Maxima annuels", "Quantiles", "Montana", "Intensités IDF", "Débits de pointe", "Hydrogramme T50"} <= set(classeur.sheet_names)
    debits = classeur.parse("Débits de pointe")
    assert list(debits["T (ans)"]) == [2, 5, 10, 20, 50, 100]
    assert len(classeur.parse("Maxima annuels")) == 28


def test_exports_vides_refuses():
    import pytest
    with pytest.raises(ValueError):
        exporter_excel({})
    with pytest.raises(ValueError):
        exporter_graphiques_zip({})
