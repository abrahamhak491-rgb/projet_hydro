"""Hydrogramme de crue par hydrogramme unitaire : SCS (triangulaire ou curviligne) et Nash.

Hypothèse commune : la pluie nette est un bloc uniforme de hauteur Q (mm) et de durée D (h).
Le temps t = 0 est le début de la pluie nette. Surface en km², débits en m³/s, durées en heures.

Conservation du volume : le volume écoulé doit être égal à Q × A (Q en mm, A en km² : 1 mm sur 1 km² = 1000 m³).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import special, stats

_trapeze = getattr(np, "trapezoid", None) or np.trapz  # compatible numpy 1 et 2

# Hydrogramme unitaire adimensionnel du SCS (courbe curviligne) : (t/Tp, q/qp).
HU_SCS = np.array(
    [
        (0.0, 0.000), (0.1, 0.030), (0.2, 0.100), (0.3, 0.190), (0.4, 0.310), (0.5, 0.470),
        (0.6, 0.660), (0.7, 0.820), (0.8, 0.930), (0.9, 0.990), (1.0, 1.000), (1.1, 0.990),
        (1.2, 0.930), (1.3, 0.860), (1.4, 0.780), (1.5, 0.680), (1.6, 0.560), (1.7, 0.460),
        (1.8, 0.390), (1.9, 0.330), (2.0, 0.280), (2.2, 0.207), (2.4, 0.147), (2.6, 0.107),
        (2.8, 0.077), (3.0, 0.055), (3.5, 0.025), (4.0, 0.011), (4.5, 0.005), (5.0, 0.000),
    ]
)
BASE_TRIANGULAIRE = 2.67  # Tb / Tp pour le triangle du SCS (facteur de pointe 484)
FACTEUR_QP = 0.208  # Qp = 0,208 · A · Q / Tp  (A km², Q mm, Tp h, Qp m³/s)

HYPOTHESES_HYDROGRAMME = {
    "scs": (
        "Hydrogramme unitaire du SCS : Qp = 0,208 · A · Q / Tp avec Tp = D/2 + 0,6·tc, et forme adimensionnelle "
        "tabulée (curviligne) ou triangulaire (base 2,67·Tp). Hypothèses : pluie nette uniforme sur le bassin et "
        "constante sur la durée D, bassin linéaire et invariant (la réponse est proportionnelle à la pluie nette)."
    ),
    "nash": (
        "Modèle de Nash : cascade de n réservoirs linéaires identiques de constante K. Hydrogramme unitaire "
        "instantané : u(t) = (1/(K·Γ(n)))·(t/K)^(n-1)·exp(-t/K). Ici K est déduit de n pour que le temps de retard "
        "n·K soit égal à 0,6·tc (le temps de retard du SCS), sauf si K est saisi à la main. "
        "Mêmes hypothèses de bassin linéaire et de pluie nette uniforme."
    ),
}


def temps_de_pointe_scs(tc_h: float, duree_pluie_h: float) -> float:
    """Tp (h) = D/2 + 0,6·tc."""
    if tc_h <= 0 or duree_pluie_h <= 0:
        raise ValueError("tc et la durée de pluie doivent être strictement positifs.")
    return duree_pluie_h / 2.0 + 0.6 * tc_h


def pas_automatique(tp_h: float) -> float:
    """Pas de temps (h) adapté : environ Tp/15, arrondi à 1, 2, 5, 10, 15, 30 ou 60 min (le plus grand sous cette valeur)."""
    cible_min = tp_h * 60.0 / 15.0
    choix = [m for m in (1, 2, 5, 10, 15, 30, 60) if m <= cible_min]
    return (choix[-1] if choix else 1) / 60.0


def _verifier(pluie_nette_mm: float, surface_km2: float, duree_pluie_h: float, pas_h: float | None) -> None:
    if pluie_nette_mm < 0:
        raise ValueError("La pluie nette ne peut pas être négative.")
    if surface_km2 <= 0 or duree_pluie_h <= 0:
        raise ValueError("La surface et la durée de pluie doivent être strictement positives.")
    if pas_h is not None and pas_h <= 0:
        raise ValueError("Le pas de temps doit être strictement positif.")


def _frame(t: np.ndarray, q: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"Temps (h)": t, "Débit (m³/s)": q})


# ----------------------------------------------------------------------------
# Hydrogramme unitaire du SCS
# ----------------------------------------------------------------------------
def hydrogramme_scs(
    pluie_nette_mm: float,
    surface_km2: float,
    tc_h: float,
    duree_pluie_h: float,
    forme: str = "curviligne",
    pas_h: float | None = None,
) -> pd.DataFrame:
    """Hydrogramme de crue par l'hydrogramme unitaire du SCS (forme « curviligne » ou « triangulaire »)."""
    _verifier(pluie_nette_mm, surface_km2, duree_pluie_h, pas_h)
    forme = forme.lower()
    if forme not in ("curviligne", "triangulaire"):
        raise ValueError("Forme inconnue. Choix : « curviligne » ou « triangulaire ».")
    tp = temps_de_pointe_scs(tc_h, duree_pluie_h)
    qp = FACTEUR_QP * surface_km2 * pluie_nette_mm / tp
    pas = pas_h or pas_automatique(tp)
    base = HU_SCS[-1, 0] if forme == "curviligne" else BASE_TRIANGULAIRE
    n = int(np.ceil(base * tp / pas)) + 1
    t = np.arange(n + 1) * pas
    x = t / tp
    if forme == "curviligne":
        q = qp * np.interp(x, HU_SCS[:, 0], HU_SCS[:, 1], right=0.0)
    else:
        q = qp * np.interp(x, [0.0, 1.0, BASE_TRIANGULAIRE], [0.0, 1.0, 0.0], right=0.0)
    return _frame(t, q)


# ----------------------------------------------------------------------------
# Modèle de Nash
# ----------------------------------------------------------------------------
def k_depuis_retard(n: float, tc_h: float) -> float:
    """K (h) tel que le temps de retard n·K vaut 0,6·tc."""
    if n <= 0 or tc_h <= 0:
        raise ValueError("n et tc doivent être strictement positifs.")
    return 0.6 * tc_h / n


def hydrogramme_nash(
    pluie_nette_mm: float,
    surface_km2: float,
    duree_pluie_h: float,
    n: float,
    k_h: float,
    pas_h: float | None = None,
) -> pd.DataFrame:
    """Hydrogramme de crue par la cascade de Nash (n réservoirs de constante K).

    Pour un bloc de pluie nette d'intensité ie = Q/D :  q(t) = (A·ie/3,6)·[S(t) − S(t−D)],
    où S est la courbe en S : S(t) = P(n, t/K), fonction gamma incomplète régularisée.
    """
    _verifier(pluie_nette_mm, surface_km2, duree_pluie_h, pas_h)
    if n <= 0 or k_h <= 0:
        raise ValueError("n et K doivent être strictement positifs.")
    pas = pas_h or pas_automatique(duree_pluie_h / 2.0 + n * k_h)
    t_fin = duree_pluie_h + float(stats.gamma.ppf(0.999, n, scale=k_h))  # 99,9 % du volume écoulé
    t = np.arange(int(np.ceil(t_fin / pas)) + 2) * pas
    s = special.gammainc(n, t / k_h)
    s_retard = np.where(t > duree_pluie_h, special.gammainc(n, np.maximum(t - duree_pluie_h, 0.0) / k_h), 0.0)
    ie = pluie_nette_mm / duree_pluie_h  # mm/h
    q = (surface_km2 * ie / 3.6) * (s - s_retard)
    return _frame(t, q)


# ----------------------------------------------------------------------------
# Caractéristiques de l'hydrogramme
# ----------------------------------------------------------------------------
def proprietes(hydro: pd.DataFrame, surface_km2: float, pluie_nette_mm: float) -> dict[str, float]:
    """Débit de pointe, temps de pointe, volume écoulé et contrôle de conservation du volume."""
    t = hydro["Temps (h)"].to_numpy()
    q = hydro["Débit (m³/s)"].to_numpy()
    i = int(np.argmax(q))
    volume = float(_trapeze(q, t) * 3600.0)
    theorique = pluie_nette_mm * surface_km2 * 1000.0
    return {
        "Qp (m³/s)": float(q[i]),
        "Temps de pointe (h)": float(t[i]),
        "Volume écoulé (m³)": volume,
        "Volume de pluie nette (m³)": theorique,
        "Rapport des volumes": volume / theorique if theorique > 0 else float("nan"),
        "Durée de l'hydrogramme (h)": float(t[-1]),
    }
