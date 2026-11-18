"""Fixture commune : un état de session complet, comme celui que laisse l'application après les 6 étapes."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest
from scipy import stats

from calculs.bassin import Bassin
from calculs.debit import c_pondere, cn_pondere, cn_selon_humidite, comparer_debits
from calculs.hydrogramme import hydrogramme_scs, proprietes
from calculs.idf import courbes_idf, pluies_depuis_journalier
from calculs.qualite import controler_qualite
from calculs.statistique import PERIODES_RETOUR, comparer_lois, meilleure_loi


def fabriquer_etat(source="station_X.csv") -> dict:
    x = stats.gumbel_r.rvs(loc=75, scale=18, size=28, random_state=5)
    maxima = pd.Series(x, index=range(1991, 2019))
    quantiles, _, aj = comparer_lois(x)
    loi, _ = meilleure_loi(aj)
    occ = {"Forêt": 0.2, "Savane / prairie": 0.3, "Culture": 0.4, "Zone urbanisée": 0.1}
    bassin = Bassin("Mayo Exemple", 25, 9, 0.015, 120, occ)
    p24 = {float(t): float(aj[loi].quantile(t)) for t in PERIODES_RETOUR}
    intensites, montana = courbes_idf(pluies_depuis_journalier(p24, [0.25, 0.5, 1, 2, 3, 6, 12, 24], 0.65))
    c, cn = c_pondere(occ), cn_selon_humidite(cn_pondere(occ, "B"), "II")
    debits = comparer_debits(montana, 25, 3.82, c, cn, 3.82)
    ligne = debits[debits["T (ans)"] == 50.0].iloc[0]
    hydros, props = {}, {}
    for t in (10.0, 50.0):
        pn = float(debits.loc[debits["T (ans)"] == t, "Pluie nette (mm)"].iloc[0])
        hydros[t] = hydrogramme_scs(pn, 25, 3.82, 3.82)
        props[t] = proprietes(hydros[t], 25, pn)
    return {
        "bassin": bassin, "tc_h": 3.82, "tc_methode": "giandotti",
        "maxima": maxima, "rapport_qualite": controler_qualite(maxima, annees=pd.Series(maxima.index)), "source_donnees": source,
        "ajustements": aj, "ajustement": aj[loi], "loi_retenue": loi, "quantiles": quantiles, "periodes_retour": list(PERIODES_RETOUR),
        "montana": montana, "idf_intensites": intensites, "idf_methode": "journalier", "b_montana": 0.65, "facteur_24h": 1.0,
        "debits": debits, "duree_pluie_h": 3.82,
        "debit_projet": {
            "T": 50.0, "methode": "SCS-CN", "Qp": float(ligne["Q SCS-CN (m³/s)"]), "Qp_scs": float(ligne["Q SCS-CN (m³/s)"]),
            "Qp_rationnelle": float(ligne["Q rationnelle (m³/s)"]), "Tp_h": float(ligne["Tp (h)"]),
            "pluie_nette_mm": float(ligne["Pluie nette (mm)"]), "duree_pluie_h": 3.82, "surface_km2": 25.0, "tc_h": 3.82, "c": c, "cn": cn,
        },
        "hydrogramme": hydros[50.0], "hydrogrammes": hydros, "hydro_proprietes": props, "hydro_methode": "SCS curviligne", "hydro_periode": 50.0,
    }


@pytest.fixture(scope="session")
def etat_complet() -> dict:
    return fabriquer_etat()
