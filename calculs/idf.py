"""Courbes Intensité-Durée-Fréquence (IDF) et coefficients de Montana.

Relation de Montana :  i(t) = a · t^(-b)
    i : intensité moyenne de la pluie (mm/h)
    t : durée de la pluie (heures dans tout ce module ; voir a_en_minutes pour t en minutes)
    a, b : coefficients de Montana, propres à chaque période de retour

Deux façons d'obtenir les courbes :
  1. À partir de la seule pluie journalière maximale P24(T) et d'un exposant b imposé
     (relation d'échelle P(t) = P24 · (t/24)^(1-b)).
  2. À partir de maxima annuels mesurés pour plusieurs durées (15 min, 1 h, 6 h, 24 h...) :
     on ajuste une loi à chaque durée, puis a et b par régression log-log.
"""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from .statistique import ajuster

DUREES_PAR_DEFAUT_H = (0.25, 0.5, 1.0, 2.0, 3.0, 6.0, 12.0, 24.0)
DUREE_JOURNALIERE_H = 24.0

# Hypothèses et limites affichées dans l'interface.
HYPOTHESES_IDF = {
    "journalier": (
        "Relation d'échelle P(t) = P24 · (t/24)^(1-b) : on déduit les pluies de courte durée de la pluie "
        "journalière maximale. Hypothèse : le même exposant b convient à toutes les durées entre environ 1 h et 24 h. "
        "Au-delà de ce domaine (durées inférieures à 1 h), la relation est une extrapolation. "
        "L'exposant b est un paramètre climatique régional : il doit venir du cours ou d'une étude locale."
    ),
    "courte_duree": (
        "Une loi est ajustée séparément aux maxima annuels de chaque durée, puis a et b sont obtenus par régression "
        "log-log de l'intensité sur la durée. Hypothèse : relation de Montana valable sur l'ensemble des durées fournies. "
        "Un R² bas signale qu'une seule droite log-log représente mal les données (b peut varier avec la durée)."
    ),
}


# ----------------------------------------------------------------------------
# Relation de Montana
# ----------------------------------------------------------------------------
def intensite(a_h: float, b: float, t_h):
    """Intensité (mm/h) pour une durée t en heures : i = a · t^-b."""
    t = np.asarray(t_h, dtype=float)
    if np.any(t <= 0):
        raise ValueError("La durée doit être strictement positive.")
    res = a_h * t ** (-b)
    return float(res) if np.ndim(res) == 0 else res


def a_en_minutes(a_h: float, b: float) -> float:
    """Convertit a (t en heures) en a pour t en MINUTES, avec i toujours en mm/h."""
    return a_h * 60.0**b


def ajuster_montana(durees_h, intensites) -> tuple[float, float, float]:
    """Ajuste i = a·t^-b par régression linéaire sur ln(i) = ln(a) - b·ln(t).

    Renvoie (a pour t en heures, b, R² de la régression log-log).
    """
    t = np.asarray(durees_h, dtype=float)
    i = np.asarray(intensites, dtype=float)
    if t.shape != i.shape or len(t) < 2:
        raise ValueError("Il faut au moins deux durées avec leurs intensités.")
    if np.any(t <= 0) or np.any(i <= 0):
        raise ValueError("Durées et intensités doivent être strictement positives.")
    if len(np.unique(t)) < 2:
        raise ValueError("Il faut au moins deux durées différentes.")
    x, y = np.log(t), np.log(i)
    pente, origine = np.polyfit(x, y, 1)
    y_est = origine + pente * x
    ss_res = float(np.sum((y - y_est) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 if ss_tot == 0 else 1.0 - ss_res / ss_tot
    return float(math.exp(origine)), float(-pente), float(r2)


# ----------------------------------------------------------------------------
# Méthode 1 : à partir de la pluie journalière
# ----------------------------------------------------------------------------
def exposant_depuis_rapport(rapport_1h_sur_24h: float) -> float:
    """Exposant b tel que P(1 h) / P(24 h) = rapport, avec P(t) = P24·(t/24)^(1-b)."""
    if not 0 < rapport_1h_sur_24h < 1:
        raise ValueError("Le rapport P(1 h)/P(24 h) doit être compris entre 0 et 1.")
    return 1.0 + math.log(rapport_1h_sur_24h) / math.log(DUREE_JOURNALIERE_H)


def pluie_depuis_journaliere(p24, t_h, b: float, facteur: float = 1.0):
    """Hauteur de pluie P(t) en mm déduite de la pluie journalière : facteur·P24·(t/24)^(1-b).

    `facteur` corrige la pluie journalière (jour pluviométrique fixe) vers une pluie
    sur 24 h glissantes : 1,13 est une valeur classique (Weiss), 1,00 = aucune correction.
    """
    if not 0 < b < 1:
        raise ValueError("L'exposant de Montana b doit être compris entre 0 et 1.")
    t = np.asarray(t_h, dtype=float)
    if np.any(t <= 0):
        raise ValueError("La durée doit être strictement positive.")
    res = facteur * np.asarray(p24, dtype=float) * (t / DUREE_JOURNALIERE_H) ** (1.0 - b)
    return float(res) if np.ndim(res) == 0 else res


def pluies_depuis_journalier(quantiles_p24: dict[float, float], durees_h, b: float, facteur: float = 1.0) -> pd.DataFrame:
    """Tableau P(t, T) en mm : une ligne par durée, une colonne par période de retour."""
    durees = list(durees_h)
    return pd.DataFrame(
        {float(T): [pluie_depuis_journaliere(p24, t, b, facteur) for t in durees] for T, p24 in quantiles_p24.items()},
        index=pd.Index(durees, name="Durée (h)"),
    )


# ----------------------------------------------------------------------------
# Méthode 2 : à partir de pluies de courte durée
# ----------------------------------------------------------------------------
_MOTIF_DUREE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(min|mn|minutes?|h|heures?)\s*$", re.IGNORECASE)


def lire_duree(nom_colonne: str) -> float | None:
    """Durée en heures d'un nom de colonne comme « 15 min », « 30mn », « 1 h », « 24h ». None sinon."""
    m = _MOTIF_DUREE.match(str(nom_colonne))
    if not m:
        return None
    valeur = float(m.group(1).replace(",", "."))
    unite = m.group(2).lower()
    return valeur / 60.0 if unite.startswith("m") else valeur


def colonnes_durees(colonnes) -> dict[str, float]:
    """Colonnes dont le nom est une durée : {nom de colonne: durée en heures}."""
    resultat = {}
    for c in colonnes:
        d = lire_duree(c)
        if d is not None and d > 0:
            resultat[c] = d
    return resultat


def pluies_depuis_courtes_durees(maxima_par_duree: dict[float, np.ndarray], loi: str, periodes, methode: str = "mv") -> pd.DataFrame:
    """Ajuste la loi à chaque durée et renvoie P(t, T) en mm (une ligne par durée, une colonne par T)."""
    durees = sorted(maxima_par_duree)
    donnees: dict[float, list[float]] = {float(T): [] for T in periodes}
    for duree in durees:
        aj = ajuster(maxima_par_duree[duree], loi, methode)
        for T in periodes:
            donnees[float(T)].append(aj.quantile(T))
    return pd.DataFrame(donnees, index=pd.Index(durees, name="Durée (h)"))


# ----------------------------------------------------------------------------
# Courbes IDF à partir de P(t, T)
# ----------------------------------------------------------------------------
def courbes_idf(pluies: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """À partir de P(t, T) en mm, renvoie (intensités en mm/h, coefficients de Montana).

    Table des coefficients : une ligne par période de retour, avec a (t en h),
    a (t en min), b et le R² de la régression log-log.
    """
    durees = pluies.index.to_numpy(dtype=float)
    intensites = pluies.div(durees, axis=0)
    intensites.index.name = "Durée (h)"
    lignes = []
    for T in pluies.columns:
        a_h, b, r2 = ajuster_montana(durees, intensites[T].to_numpy())
        lignes.append(
            {
                "Période de retour (ans)": T,
                "a (t en h)": a_h,
                "a (t en min)": a_en_minutes(a_h, b),
                "b": b,
                "R²": r2,
            }
        )
    return intensites, pd.DataFrame(lignes)


def intensite_de_projet(montana: pd.DataFrame, periode_retour: float, duree_h: float) -> float:
    """Intensité (mm/h) pour la période de retour et la durée données (typiquement tc)."""
    ligne = montana[np.isclose(montana["Période de retour (ans)"], periode_retour)]
    if ligne.empty:
        raise ValueError(f"Période de retour {periode_retour:g} ans absente des coefficients de Montana.")
    return intensite(float(ligne["a (t en h)"].iloc[0]), float(ligne["b"].iloc[0]), duree_h)
