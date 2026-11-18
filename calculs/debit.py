"""Débit de pointe de crue : méthode rationnelle et méthode SCS-CN.

Unités : surface en km², durées en heures, pluies en mm, intensités en mm/h, débits en m³/s.

ATTENTION : les tables de C et de CN ci-dessous sont des valeurs GÉNÉRIQUES de la
littérature (Chow et ASCE pour C, SCS TR-55 pour CN, conditions américaines). Elles sont
indicatives : l'utilisateur doit pouvoir les modifier et les remplacer par celles du cours
ou d'études régionales, notamment pour les sols et la végétation tropicaux.
"""
from __future__ import annotations

import pandas as pd

# Mêmes noms que ceux de la page « Bassin ».
OCCUPATIONS = [
    "Forêt",
    "Savane / prairie",
    "Culture",
    "Zone urbanisée",
    "Sol nu / rocheux",
    "Plan d'eau / marécage",
]

GROUPES_SOL = {
    "A": "A : sols très perméables (sables, graviers) ; faible ruissellement",
    "B": "B : sols assez perméables (limons sableux)",
    "C": "C : sols peu perméables (limons argileux)",
    "D": "D : sols très peu perméables (argiles, roche affleurante) ; fort ruissellement",
}

# Coefficient de ruissellement C (méthode rationnelle), valeurs médianes indicatives.
C_PAR_OCCUPATION: dict[str, float] = {
    "Forêt": 0.15,
    "Savane / prairie": 0.25,
    "Culture": 0.35,
    "Zone urbanisée": 0.70,
    "Sol nu / rocheux": 0.60,
    "Plan d'eau / marécage": 0.50,
}

# Curve Number CN, condition d'humidité moyenne (AMC II), par groupe hydrologique de sol.
# Source des valeurs : tables SCS TR-55 (couverture : bois en bon état, pâturage en état moyen,
# cultures en lignes en bon état, habitat résidentiel 1/4 acre, sol nu en jachère).
CN_AMC2: dict[str, dict[str, float]] = {
    "Forêt": {"A": 30, "B": 55, "C": 70, "D": 77},
    "Savane / prairie": {"A": 49, "B": 69, "C": 79, "D": 84},
    "Culture": {"A": 67, "B": 78, "C": 85, "D": 89},
    "Zone urbanisée": {"A": 61, "B": 75, "C": 83, "D": 87},
    "Sol nu / rocheux": {"A": 77, "B": 86, "C": 91, "D": 94},
    # Eau libre : CN proche de 98 ; marécage : plus bas. Valeur intermédiaire, à ajuster.
    "Plan d'eau / marécage": {"A": 90, "B": 90, "C": 90, "D": 90},
}

# Majoration de C pour les périodes de retour élevées (Chow et al.) : C·Cf, plafonné à 1.
MAJORATION_T = ((100, 1.25), (50, 1.20), (25, 1.10))

HYPOTHESES_DEBIT = {
    "rationnelle": (
        "Q = C · i · A / 3,6. Hypothèses : pluie uniforme sur le bassin, d'intensité constante pendant une durée égale à tc, "
        "et période de retour du débit égale à celle de la pluie. Méthode conçue pour de petits bassins "
        "(de l'ordre de quelques km² à quelques dizaines de km², selon la source) ; l'incertitude sur C domine le résultat."
    ),
    "scs": (
        "Pluie nette Q = (P − Ia)² / (P − Ia + S), avec S = 25400/CN − 254 et Ia = λ·S. "
        "Débit de pointe par l'hydrogramme unitaire triangulaire du SCS : Qp = 0,208 · A · Q / Tp, avec Tp = D/2 + 0,6·tc. "
        "Méthode établie sur de petits bassins ruraux américains : les CN sont à adapter au contexte tropical, "
        "et le résultat est très sensible au CN."
    ),
}


# ----------------------------------------------------------------------------
# Coefficients pondérés
# ----------------------------------------------------------------------------
def _verifier_fractions(occupation_sol: dict[str, float]) -> None:
    if not occupation_sol:
        raise ValueError("Occupation du sol non renseignée.")
    if abs(sum(occupation_sol.values()) - 1.0) > 0.01:
        raise ValueError("Les fractions d'occupation du sol doivent totaliser 1.")


def coefficient_majoration(periode_retour: float) -> float:
    """Facteur Cf appliqué à C pour les grandes périodes de retour (1 en dessous de 25 ans)."""
    for seuil, cf in MAJORATION_T:
        if periode_retour >= seuil:
            return cf
    return 1.0


def c_pondere(occupation_sol: dict[str, float], table_c: dict[str, float] | None = None) -> float:
    """Coefficient de ruissellement moyen, pondéré par la surface de chaque occupation."""
    _verifier_fractions(occupation_sol)
    table = table_c or C_PAR_OCCUPATION
    manquants = [k for k in occupation_sol if k not in table]
    if manquants:
        raise ValueError(f"Pas de coefficient C pour : {', '.join(manquants)}.")
    c = sum(frac * table[k] for k, frac in occupation_sol.items())
    return float(c)


def cn_pondere(
    occupation_sol: dict[str, float],
    groupe_sol: str,
    table_cn: dict[str, dict[str, float]] | None = None,
) -> float:
    """CN moyen (AMC II), pondéré par la surface de chaque occupation, pour un groupe de sol."""
    _verifier_fractions(occupation_sol)
    if groupe_sol not in GROUPES_SOL:
        raise ValueError(f"Groupe de sol inconnu : {groupe_sol!r}. Choix : A, B, C, D.")
    table = table_cn or CN_AMC2
    manquants = [k for k in occupation_sol if k not in table]
    if manquants:
        raise ValueError(f"Pas de CN pour : {', '.join(manquants)}.")
    return float(sum(frac * table[k][groupe_sol] for k, frac in occupation_sol.items()))


def cn_selon_humidite(cn_ii: float, condition: str) -> float:
    """Corrige le CN (condition moyenne II) pour un sol sec (I) ou saturé (III)."""
    condition = condition.upper()
    if condition == "II":
        return cn_ii
    if condition == "I":
        return 4.2 * cn_ii / (10.0 - 0.058 * cn_ii)
    if condition == "III":
        return 23.0 * cn_ii / (10.0 + 0.13 * cn_ii)
    raise ValueError("Condition d'humidité inconnue. Choix : I (sec), II (moyen), III (humide).")


# ----------------------------------------------------------------------------
# Méthode rationnelle
# ----------------------------------------------------------------------------
def debit_rationnelle(c: float, intensite_mm_h: float, surface_km2: float) -> float:
    """Q (m³/s) = C · i · A / 3,6."""
    if not 0 < c <= 1:
        raise ValueError("Le coefficient de ruissellement C doit être compris entre 0 (exclu) et 1.")
    if intensite_mm_h <= 0 or surface_km2 <= 0:
        raise ValueError("L'intensité et la surface doivent être strictement positives.")
    return c * intensite_mm_h * surface_km2 / 3.6


# ----------------------------------------------------------------------------
# Méthode SCS-CN
# ----------------------------------------------------------------------------
def retention_potentielle(cn: float) -> float:
    """S (mm) = 25400/CN − 254."""
    if not 0 < cn <= 100:
        raise ValueError("Le CN doit être compris entre 0 (exclu) et 100.")
    return 25400.0 / cn - 254.0


def pluie_nette_scs(pluie_mm: float, cn: float, lam: float = 0.2) -> float:
    """Hauteur ruisselée Q (mm) : (P − Ia)² / (P − Ia + S) si P > Ia, sinon 0. Ia = λ·S."""
    if pluie_mm < 0:
        raise ValueError("La pluie doit être positive.")
    if not 0 < lam <= 0.3:
        raise ValueError("Le rapport λ = Ia/S doit être compris entre 0 (exclu) et 0,3.")
    s = retention_potentielle(cn)
    ia = lam * s
    if pluie_mm <= ia:
        return 0.0
    return (pluie_mm - ia) ** 2 / (pluie_mm - ia + s)


def temps_de_pointe_scs(tc_h: float, duree_pluie_h: float) -> float:
    """Tp (h) = D/2 + 0,6·tc, avec 0,6·tc = temps de retard du bassin."""
    if tc_h <= 0 or duree_pluie_h <= 0:
        raise ValueError("tc et la durée de pluie doivent être strictement positifs.")
    return duree_pluie_h / 2.0 + 0.6 * tc_h


def debit_pointe_scs(pluie_nette_mm: float, surface_km2: float, tc_h: float, duree_pluie_h: float) -> tuple[float, float]:
    """Débit de pointe (m³/s) et temps de pointe Tp (h) : Qp = 0,208 · A · Q / Tp."""
    tp = temps_de_pointe_scs(tc_h, duree_pluie_h)
    return 0.208 * surface_km2 * pluie_nette_mm / tp, tp


# ----------------------------------------------------------------------------
# Tableau de synthèse
# ----------------------------------------------------------------------------
def comparer_debits(
    montana: pd.DataFrame,
    surface_km2: float,
    tc_h: float,
    c: float,
    cn: float,
    duree_pluie_h: float | None = None,
    lam: float = 0.2,
    majorer_c: bool = False,
) -> pd.DataFrame:
    """Débits de pointe par les deux méthodes pour chaque période de retour du tableau de Montana.

    montana : tableau produit par calculs.idf.courbes_idf (colonnes « Période de retour (ans) », « a (t en h) », « b »)
    duree_pluie_h : durée D de la pluie de projet pour la méthode SCS (par défaut D = tc)
    """
    d = duree_pluie_h if duree_pluie_h else tc_h
    lignes = []
    for _, m in montana.iterrows():
        t_ret = float(m["Période de retour (ans)"])
        a_h, b = float(m["a (t en h)"]), float(m["b"])
        i_tc = a_h * tc_h ** (-b)  # intensité sur une durée égale à tc
        c_t = min(1.0, c * coefficient_majoration(t_ret)) if majorer_c else c
        q_rat = debit_rationnelle(c_t, i_tc, surface_km2)
        p_d = a_h * d ** (1.0 - b)  # hauteur de pluie sur la durée D : P = i·D
        q_mm = pluie_nette_scs(p_d, cn, lam)
        q_scs, tp = debit_pointe_scs(q_mm, surface_km2, tc_h, d)
        lignes.append(
            {
                "T (ans)": t_ret,
                "i(tc) (mm/h)": i_tc,
                "C utilisé": c_t,
                "Q rationnelle (m³/s)": q_rat,
                "P(D) (mm)": p_d,
                "Pluie nette (mm)": q_mm,
                "Tp (h)": tp,
                "Q SCS-CN (m³/s)": q_scs,
            }
        )
    res = pd.DataFrame(lignes)
    hauts = res[["Q rationnelle (m³/s)", "Q SCS-CN (m³/s)"]]
    res["Rapport SCS / rationnelle"] = res["Q SCS-CN (m³/s)"] / res["Q rationnelle (m³/s)"]
    res["Débit spécifique moyen (m³/s/km²)"] = hauts.mean(axis=1) / surface_km2
    return res
