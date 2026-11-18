"""Caractéristiques du bassin versant et temps de concentration.

Trois formules empiriques sont proposées (Kirpich, Giandotti, Passini).
Toutes les durées renvoyées par ce module sont en HEURES.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt


@dataclass
class Bassin:
    """Caractéristiques physiques d'un bassin versant.

    surface_km2   : surface A du bassin (km²)
    longueur_km   : longueur L du plus long cheminement hydraulique (km)
    pente         : pente moyenne S du cheminement (m/m, par exemple 0.02 pour 2 %)
    denivele_m    : H, différence entre l'altitude moyenne du bassin et celle de
                    l'exutoire (m). Nécessaire seulement pour Giandotti.
    occupation_sol: part de la surface par type de sol, en fractions dont la
                    somme vaut 1 (ex. {"forêt": 0.3, "culture": 0.5, "urbain": 0.2}).
                    Utilisée plus tard pour C (rationnelle) et CN (SCS).
    """

    nom: str
    surface_km2: float
    longueur_km: float
    pente: float
    denivele_m: float | None = None
    occupation_sol: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.surface_km2 <= 0:
            raise ValueError("La surface du bassin doit être strictement positive.")
        if self.longueur_km <= 0:
            raise ValueError("La longueur du cheminement doit être strictement positive.")
        if not (0 < self.pente < 1):
            raise ValueError(
                "La pente doit être comprise entre 0 et 1 (en m/m, par exemple 0.02 pour 2 %)."
            )
        if self.denivele_m is not None and self.denivele_m <= 0:
            raise ValueError("Le dénivelé H doit être strictement positif.")
        if self.occupation_sol:
            if any(f < 0 for f in self.occupation_sol.values()):
                raise ValueError("Les fractions d'occupation du sol doivent être positives.")
            total = sum(self.occupation_sol.values())
            if abs(total - 1.0) > 0.01:
                raise ValueError(
                    f"Les fractions d'occupation du sol doivent totaliser 1 (actuellement {total:.2f})."
                )


def tc_kirpich(longueur_km: float, pente: float) -> float:
    """Kirpich : tc (min) = 0,0195 · L^0,77 · S^-0,385, avec L en mètres. Retour en heures."""
    l_m = longueur_km * 1000.0
    tc_min = 0.0195 * l_m**0.77 * pente**-0.385
    return tc_min / 60.0


def tc_giandotti(surface_km2: float, longueur_km: float, denivele_m: float) -> float:
    """Giandotti : tc (h) = (4·√A + 1,5·L) / (0,8·√H)."""
    return (4.0 * sqrt(surface_km2) + 1.5 * longueur_km) / (0.8 * sqrt(denivele_m))


def tc_passini(surface_km2: float, longueur_km: float, pente: float) -> float:
    """Passini : tc (h) = 0,108 · (A·L)^(1/3) / √S."""
    return 0.108 * (surface_km2 * longueur_km) ** (1.0 / 3.0) / sqrt(pente)


# Hypothèses et domaines de validité affichés dans l'interface.
# À confronter avec les valeurs données dans le cours avant la soutenance.
METHODES_TC: dict[str, dict[str, str]] = {
    "kirpich": {
        "nom": "Kirpich",
        "formule": "tc (min) = 0,0195 · L^0,77 · S^-0,385  (L en m, S en m/m)",
        "donnees": "Longueur L et pente S du plus long cheminement",
        "validite": (
            "Établie sur de petits bassins ruraux agricoles du Tennessee (États-Unis), "
            "à pentes de l'ordre de 3 à 10 %. Elle sous-estime souvent tc sur des bassins "
            "plus grands, plats ou fortement urbanisés."
        ),
    },
    "giandotti": {
        "nom": "Giandotti",
        "formule": "tc (h) = (4·√A + 1,5·L) / (0,8·√H)  (A en km², L en km, H en m)",
        "donnees": "Surface A, longueur L et dénivelé H (altitude moyenne moins altitude de l'exutoire)",
        "validite": (
            "Formule empirique calée sur des bassins italiens. Elle est plutôt utilisée pour des "
            "bassins de taille moyenne à grande, avec un relief marqué. Vérifier la plage "
            "de surface donnée dans le cours."
        ),
    },
    "passini": {
        "nom": "Passini",
        "formule": "tc (h) = 0,108 · (A·L)^(1/3) / √S  (A en km², L en km, S en m/m)",
        "donnees": "Surface A, longueur L et pente S",
        "validite": (
            "Formule empirique d'origine italienne, souvent employée pour des bassins de taille "
            "moyenne à pente modérée. Vérifier la plage de surface donnée dans le cours."
        ),
    },
}


def temps_concentration(bassin: Bassin, methode: str) -> float:
    """Temps de concentration (en heures) pour la méthode demandée."""
    methode = methode.lower()
    if methode == "kirpich":
        return tc_kirpich(bassin.longueur_km, bassin.pente)
    if methode == "giandotti":
        if bassin.denivele_m is None:
            raise ValueError("Giandotti nécessite le dénivelé H du bassin (altitude moyenne moins exutoire).")
        return tc_giandotti(bassin.surface_km2, bassin.longueur_km, bassin.denivele_m)
    if methode == "passini":
        return tc_passini(bassin.surface_km2, bassin.longueur_km, bassin.pente)
    raise ValueError(f"Méthode inconnue : {methode!r}. Choix : kirpich, giandotti, passini.")


def tc_toutes_methodes(bassin: Bassin) -> dict[str, float]:
    """Calcule tc (heures) par toutes les méthodes dont les données sont disponibles."""
    resultats: dict[str, float] = {}
    for methode in METHODES_TC:
        try:
            resultats[methode] = temps_concentration(bassin, methode)
        except ValueError:
            continue
    return resultats
