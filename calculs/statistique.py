"""Ajustement statistique des pluies maximales annuelles.

Lois : Gumbel, GEV et Galton (log-normale à 2 paramètres).
Méthodes : maximum de vraisemblance ("mv") pour les trois lois, et méthode des
moments ("moments") pour Gumbel et Galton.
Tests d'adéquation : Kolmogorov-Smirnov et chi², plus le critère AIC pour comparer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import log10, pi, sqrt

import numpy as np
import pandas as pd
from scipy import stats

EULER = 0.5772156649015329
PERIODES_RETOUR = (2, 5, 10, 20, 50, 100)
LOIS = ("gumbel", "gev", "galton")
NOMS_LOIS = {"gumbel": "Gumbel", "gev": "GEV", "galton": "Galton (log-normale)"}
N_PARAMETRES = {"gumbel": 2, "gev": 3, "galton": 2}

# Hypothèses et limites affichées dans l'interface.
HYPOTHESES_STAT = {
    "gumbel": "Loi à 2 paramètres, asymétrique, sans borne supérieure. Cas particulier de la GEV (xi = 0). Hypothèse : observations indépendantes et de même loi.",
    "gev": "Loi généralisée des valeurs extrêmes à 3 paramètres (position mu, échelle sigma, forme xi). Plus souple, mais le paramètre de forme est instable sur les séries courtes (moins de 30 valeurs).",
    "galton": "Loi log-normale : le logarithme des maxima suit une loi normale. 2 paramètres, asymétrique, sans borne supérieure.",
}


@dataclass
class Ajustement:
    loi: str
    methode: str
    n: int
    parametres: dict[str, float]
    dist: object = field(repr=False)  # loi SciPy « gelée » (avec ses paramètres)
    ks_stat: float = np.nan
    ks_p: float = np.nan
    chi2_stat: float | None = None
    chi2_p: float | None = None
    chi2_ddl: int | None = None
    chi2_classes: int | None = None
    aic: float = np.inf
    alpha: float = 0.05

    @property
    def nom(self) -> str:
        return NOMS_LOIS[self.loi]

    @property
    def accepte(self) -> bool:
        """Vrai si aucun test ne rejette la loi au seuil alpha."""
        if not np.isfinite(self.ks_p) or self.ks_p <= self.alpha:
            return False
        if self.chi2_p is not None and self.chi2_p <= self.alpha:
            return False
        return True

    def quantile(self, periode_retour):
        """Valeur de pluie (mm) dépassée en moyenne une fois toutes les T années."""
        t = np.asarray(periode_retour, dtype=float)
        if np.any(t <= 1):
            raise ValueError("La période de retour doit être strictement supérieure à 1 an.")
        resultat = self.dist.ppf(1.0 - 1.0 / t)
        return float(resultat) if np.ndim(resultat) == 0 else resultat

    def periode_retour(self, valeur):
        """Période de retour (ans) d'une pluie donnée."""
        proba_non_depassement = self.dist.cdf(valeur)
        return float(1.0 / (1.0 - proba_non_depassement))


# ----------------------------------------------------------------------------
# Ajustement
# ----------------------------------------------------------------------------
def _verifier(donnees) -> np.ndarray:
    x = np.asarray(donnees, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 5:
        raise ValueError("Il faut au moins 5 valeurs pour ajuster une loi.")
    return x


def _ajuster_gumbel(x: np.ndarray, methode: str):
    if methode == "moments":
        sigma = np.std(x, ddof=1) * sqrt(6.0) / pi
        mu = np.mean(x) - EULER * sigma
    else:
        mu, sigma = stats.gumbel_r.fit(x)
    return stats.gumbel_r(loc=mu, scale=sigma), {"mu": float(mu), "sigma": float(sigma)}


def _ajuster_gev(x: np.ndarray, methode: str):
    if methode != "mv":
        raise ValueError("La GEV s'ajuste seulement par maximum de vraisemblance (méthode « mv »).")
    # Point de départ : la solution Gumbel, plus stable que le point de départ par défaut.
    mu0, sigma0 = stats.gumbel_r.fit(x)
    c, mu, sigma = stats.genextreme.fit(x, 0.0, loc=mu0, scale=sigma0)
    # Convention SciPy : c = -xi. On présente xi (xi > 0 : queue lourde).
    return stats.genextreme(c, loc=mu, scale=sigma), {"mu": float(mu), "sigma": float(sigma), "xi": float(-c)}


def _ajuster_galton(x: np.ndarray, methode: str):
    if np.any(x <= 0):
        raise ValueError("La loi de Galton exige des valeurs strictement positives.")
    if methode == "moments":
        logs = np.log(x)
        mu_ln, sigma_ln = np.mean(logs), np.std(logs, ddof=1)
    else:
        s, _, scale = stats.lognorm.fit(x, floc=0)
        mu_ln, sigma_ln = np.log(scale), s
    return stats.lognorm(sigma_ln, loc=0, scale=np.exp(mu_ln)), {"mu_ln": float(mu_ln), "sigma_ln": float(sigma_ln)}


_AJUSTEURS = {"gumbel": _ajuster_gumbel, "gev": _ajuster_gev, "galton": _ajuster_galton}


def _test_chi2(x: np.ndarray, dist, n_param: int):
    """Chi² avec classes équiprobables sous la loi ajustée.

    Nombre de classes : règle de Sturges, borné pour garder au moins ~5 valeurs
    attendues par classe et un nombre de degrés de liberté positif.
    Degrés de liberté = classes - 1 - nombre de paramètres estimés.
    """
    n = len(x)
    k = int(round(1 + 3.3 * log10(n)))
    k = max(n_param + 2, min(k, n // 5))
    ddl = k - 1 - n_param
    if ddl < 1:
        return None, None, None, k
    bornes = dist.ppf(np.linspace(0, 1, k + 1)[1:-1])
    observes, _ = np.histogram(x, bins=np.concatenate(([-np.inf], bornes, [np.inf])))
    attendu = n / k
    chi2 = float(np.sum((observes - attendu) ** 2 / attendu))
    p = float(stats.chi2.sf(chi2, ddl))
    return chi2, p, ddl, k


def ajuster(donnees, loi: str, methode: str = "mv", alpha: float = 0.05) -> Ajustement:
    """Ajuste une loi (« gumbel », « gev » ou « galton ») aux maxima annuels.

    Attention : la p-valeur de Kolmogorov-Smirnov est calculée avec des paramètres
    estimés sur les mêmes données. Elle est donc un peu trop favorable (trop élevée) :
    à interpréter avec prudence, surtout sur les séries courtes.
    """
    loi = loi.lower()
    if loi not in _AJUSTEURS:
        raise ValueError(f"Loi inconnue : {loi!r}. Choix : {', '.join(LOIS)}.")
    methode = methode.lower()
    if methode not in ("mv", "moments"):
        raise ValueError("Méthode inconnue. Choix : « mv » (maximum de vraisemblance) ou « moments ».")

    x = _verifier(donnees)
    dist, parametres = _AJUSTEURS[loi](x, methode)

    ks = stats.kstest(x, dist.cdf)
    chi2, chi2_p, ddl, classes = _test_chi2(x, dist, N_PARAMETRES[loi])
    log_vrais = float(np.sum(dist.logpdf(x)))
    aic = 2 * N_PARAMETRES[loi] - 2 * log_vrais if np.isfinite(log_vrais) else np.inf

    return Ajustement(
        loi=loi,
        methode=methode,
        n=len(x),
        parametres=parametres,
        dist=dist,
        ks_stat=float(ks.statistic),
        ks_p=float(ks.pvalue),
        chi2_stat=chi2,
        chi2_p=chi2_p,
        chi2_ddl=ddl,
        chi2_classes=classes,
        aic=float(aic),
        alpha=alpha,
    )


def comparer_lois(donnees, periodes=PERIODES_RETOUR, methode: str = "mv", alpha: float = 0.05):
    """Ajuste les trois lois et les compare.

    Renvoie (quantiles, tests, ajustements) :
      quantiles    : DataFrame, une ligne par période de retour, une colonne par loi (mm)
      tests        : DataFrame de synthèse (paramètres, KS, chi², AIC, verdict)
      ajustements  : dict loi -> Ajustement (pour tracer les courbes)
    Une loi qui ne s'ajuste pas est omise et son erreur est notée dans `tests`.
    """
    ajustements: dict[str, Ajustement] = {}
    lignes = []
    for loi in LOIS:
        m = methode if not (loi == "gev" and methode != "mv") else "mv"
        try:
            aj = ajuster(donnees, loi, m, alpha)
        except Exception as erreur:  # une loi en échec ne doit pas bloquer les autres
            lignes.append({"loi": NOMS_LOIS[loi], "verdict": f"échec : {erreur}"})
            continue
        ajustements[loi] = aj
        lignes.append(
            {
                "loi": aj.nom,
                "méthode": aj.methode,
                "paramètres": ", ".join(f"{k} = {v:.3f}" for k, v in aj.parametres.items()),
                "KS (statistique)": round(aj.ks_stat, 4),
                "KS (p-valeur)": round(aj.ks_p, 3),
                "chi² (p-valeur)": None if aj.chi2_p is None else round(aj.chi2_p, 3),
                "AIC": round(aj.aic, 2),
                "verdict": "adéquation acceptée" if aj.accepte else "adéquation rejetée",
            }
        )
    quantiles = pd.DataFrame(
        {aj.nom: [aj.quantile(t) for t in periodes] for aj in ajustements.values()},
        index=pd.Index(periodes, name="Période de retour (ans)"),
    )
    return quantiles, pd.DataFrame(lignes), ajustements


def meilleure_loi(ajustements: dict[str, Ajustement]) -> tuple[str, bool]:
    """Loi conseillée : plus petit AIC parmi les lois acceptées.

    Renvoie (nom de la loi, True si au moins une loi est acceptée). Si aucune loi
    n'est acceptée, on renvoie la plus petite AIC avec False : à signaler à l'utilisateur.
    """
    if not ajustements:
        raise ValueError("Aucun ajustement disponible.")
    acceptees = {k: a for k, a in ajustements.items() if a.accepte}
    pool, ok = (acceptees, True) if acceptees else (ajustements, False)
    return min(pool, key=lambda k: pool[k].aic), ok


def positions_empiriques(donnees) -> pd.DataFrame:
    """Fréquences empiriques de Weibull : p = rang / (n + 1), pour le tracé sur papier de probabilité."""
    x = np.sort(_verifier(donnees))
    n = len(x)
    p = np.arange(1, n + 1) / (n + 1)
    return pd.DataFrame(
        {
            "valeur": x,
            "probabilite": p,
            "periode_retour": 1.0 / (1.0 - p),
            "variable_reduite_gumbel": -np.log(-np.log(p)),
        }
    )


def avertissement_extrapolation(n: int, periode_retour: float) -> str | None:
    """Message si la période de retour demandée dépasse largement la longueur de la série."""
    if periode_retour > 2 * n:
        return (
            f"Une période de retour de {periode_retour:g} ans est une forte extrapolation pour "
            f"une série de {n} ans : l'incertitude sur ce quantile est grande."
        )
    return None
