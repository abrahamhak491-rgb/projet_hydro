"""Import des séries de pluies et contrôle de qualité des données.

Le module ne supprime jamais une valeur en silence : il signale les problèmes
(valeurs manquantes, négatives, aberrantes, années absentes) et laisse
l'utilisateur décider quoi exclure.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Codes souvent utilisés dans les fichiers pluviométriques pour « donnée absente ».
CODES_MANQUANTS = (-99.0, -999.0, -9999.0)


# ----------------------------------------------------------------------------
# Lecture des fichiers
# ----------------------------------------------------------------------------
def _lire_octets(source) -> bytes:
    if hasattr(source, "read"):  # fichier téléversé (Streamlit) ou fichier ouvert
        donnees = source.read()
        if hasattr(source, "seek"):
            source.seek(0)
        return donnees
    with open(source, "rb") as f:
        return f.read()


def lire_fichier(source, nom: str | None = None) -> pd.DataFrame:
    """Lit un fichier CSV, TXT ou Excel (.xlsx) et renvoie un DataFrame de TEXTE.

    Les colonnes restent en texte volontairement : la conversion en nombres et en
    dates se fait ensuite, avec contrôle (voir convertir_numerique et convertir_dates).
    Le séparateur du CSV (virgule, point-virgule, tabulation) est détecté seul.
    """
    nom_fichier = (nom or getattr(source, "name", None) or str(source)).lower()
    octets = _lire_octets(source)

    if nom_fichier.endswith((".xlsx", ".xlsm")):
        df = pd.read_excel(io.BytesIO(octets), dtype=str)
    elif nom_fichier.endswith((".csv", ".txt", ".tsv")):
        try:
            texte = octets.decode("utf-8-sig")
        except UnicodeDecodeError:
            texte = octets.decode("latin-1")
        df = pd.read_csv(io.StringIO(texte), sep=None, engine="python", dtype=str)
    else:
        raise ValueError("Format non pris en charge. Utiliser un fichier .csv, .txt ou .xlsx.")

    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    if df.empty:
        raise ValueError("Le fichier ne contient aucune ligne de données.")
    return df


def convertir_numerique(
    serie: pd.Series, codes_manquants: tuple[float, ...] = CODES_MANQUANTS
) -> pd.Series:
    """Convertit une colonne de texte en nombres (virgule ou point décimal).

    Le texte illisible et les codes « donnée absente » (-99, -999, -9999) deviennent NaN.
    """
    texte = serie.astype(str).str.strip().str.replace(",", ".", regex=False)
    nombres = pd.to_numeric(texte, errors="coerce")
    return nombres.mask(nombres.isin(codes_manquants))


def convertir_dates(serie: pd.Series) -> pd.Series:
    """Convertit une colonne de texte en dates (jour en premier, format JJ/MM/AAAA)."""
    texte = serie.astype(str).str.strip()
    # Format ISO AAAA-MM-JJ : pas de jour en premier.
    iso = texte.str.match(r"^\d{4}-\d{1,2}-\d{1,2}")
    dates = pd.to_datetime(texte.where(iso), errors="coerce", format="mixed")
    autres = pd.to_datetime(texte.where(~iso), errors="coerce", dayfirst=True, format="mixed")
    return dates.fillna(autres)


def maxima_annuels(
    dates: pd.Series,
    valeurs: pd.Series,
    min_jours_par_an: int = 300,
    exclure_incomplets: bool = True,
) -> pd.DataFrame:
    """Extrait le maximum annuel d'une série de pluies journalières.

    Une année est jugée incomplète si elle compte moins de `min_jours_par_an` jours
    valides : son maximum risque d'être sous-estimé.
    Colonnes renvoyées : annee, maximum, jours_valides, complete.
    """
    df = pd.DataFrame({"date": dates, "valeur": valeurs}).dropna(subset=["date"])
    df["annee"] = df["date"].dt.year
    groupes = df.groupby("annee")["valeur"]
    resultat = pd.DataFrame(
        {
            "maximum": groupes.max(),
            "jours_valides": groupes.count(),
        }
    ).reset_index()
    resultat["complete"] = resultat["jours_valides"] >= min_jours_par_an
    if exclure_incomplets:
        resultat = resultat[resultat["complete"]]
    return resultat.dropna(subset=["maximum"]).reset_index(drop=True)


# ----------------------------------------------------------------------------
# Contrôle de qualité
# ----------------------------------------------------------------------------
@dataclass
class RapportQualite:
    n_total: int
    n_valides: int
    n_manquants: int
    n_negatifs: int
    n_nuls: int
    indices_aberrants: list = field(default_factory=list)
    bornes_aberrants: tuple[float, float] | None = None
    annees_manquantes: list[int] = field(default_factory=list)
    annees_en_double: list[int] = field(default_factory=list)
    messages: list[tuple[str, str]] = field(default_factory=list)  # (niveau, texte)

    @property
    def utilisable(self) -> bool:
        """Faux si une erreur bloquante a été détectée."""
        return not any(niveau == "erreur" for niveau, _ in self.messages)


def controler_qualite(
    valeurs: pd.Series,
    annees: pd.Series | None = None,
    coef_aberrant: float = 3.0,
    serie_minimale: int = 20,
) -> RapportQualite:
    """Contrôle une série de maxima annuels.

    valeurs        : maxima annuels (NaN = manquant)
    annees         : années correspondantes (facultatif, pour détecter les trous et doublons)
    coef_aberrant  : une valeur est signalée si elle sort de [Q1 - k·IQR ; Q3 + k·IQR].
                     k = 3 par défaut (seuil « très éloigné » de Tukey) : en hydrologie,
                     une forte valeur est souvent une vraie crue, donc on SIGNALE
                     sans jamais supprimer automatiquement.
    serie_minimale : longueur en dessous de laquelle on avertit que les quantiles
                     de grande période de retour seront peu fiables.
    """
    v = pd.to_numeric(valeurs, errors="coerce")
    n_total = len(v)
    manquants = v.isna()
    negatifs = v < 0
    nuls = v == 0
    valides = v[~manquants & ~negatifs]

    rapport = RapportQualite(
        n_total=n_total,
        n_valides=len(valides),
        n_manquants=int(manquants.sum()),
        n_negatifs=int(negatifs.sum()),
        n_nuls=int(nuls.sum()),
    )
    msg = rapport.messages

    if n_total == 0:
        msg.append(("erreur", "La série est vide."))
        return rapport

    if rapport.n_manquants:
        msg.append(("avertissement", f"{rapport.n_manquants} valeur(s) manquante(s) ou illisible(s) : ignorée(s) dans les calculs."))
    if rapport.n_negatifs:
        msg.append(("avertissement", f"{rapport.n_negatifs} valeur(s) négative(s), impossible(s) pour une pluie : ignorée(s)."))
    if rapport.n_nuls:
        msg.append(("avertissement", f"{rapport.n_nuls} maximum annuel nul : suspect (année sans pluie ? donnée absente codée 0 ?)."))

    if annees is not None:
        a = pd.to_numeric(annees, errors="coerce").dropna().astype(int)
        doublons = sorted(a[a.duplicated()].unique().tolist())
        rapport.annees_en_double = doublons
        if doublons:
            msg.append(("erreur", f"Année(s) en double : {doublons}. Vérifier le fichier."))
        if len(a):
            attendues = set(range(int(a.min()), int(a.max()) + 1))
            rapport.annees_manquantes = sorted(attendues - set(a.tolist()))
            if rapport.annees_manquantes:
                msg.append(("avertissement", f"Année(s) absente(s) de la série : {rapport.annees_manquantes}."))

    if rapport.n_valides < 5:
        msg.append(("erreur", f"Seulement {rapport.n_valides} valeur(s) valide(s) : un ajustement statistique est impossible (minimum 5, idéalement plus de {serie_minimale})."))
    elif rapport.n_valides < serie_minimale:
        msg.append(("avertissement", f"Série courte ({rapport.n_valides} valeurs, moins de {serie_minimale}) : les quantiles de période de retour élevée seront peu fiables."))

    if rapport.n_valides >= 8:
        q1, q3 = np.percentile(valides, [25, 75])
        iqr = q3 - q1
        bas, haut = q1 - coef_aberrant * iqr, q3 + coef_aberrant * iqr
        rapport.bornes_aberrants = (float(bas), float(haut))
        aberrants = valides[(valides < bas) | (valides > haut)]
        rapport.indices_aberrants = aberrants.index.tolist()
        if len(aberrants):
            msg.append(("avertissement", f"{len(aberrants)} valeur(s) très éloignée(s) des autres (hors de [{bas:.1f} ; {haut:.1f}] mm) : à vérifier (erreur de saisie ou vraie crue exceptionnelle ?)."))

    if not msg:
        msg.append(("info", "Aucun problème détecté."))
    return rapport


def nettoyer(
    valeurs: pd.Series, rapport: RapportQualite, exclure_aberrants: bool = False
) -> pd.Series:
    """Renvoie les valeurs exploitables : sans NaN, sans négatifs et, si demandé, sans aberrants."""
    v = pd.to_numeric(valeurs, errors="coerce")
    v = v[v.notna() & (v >= 0)]
    if exclure_aberrants:
        v = v.drop(index=[i for i in rapport.indices_aberrants if i in v.index])
    return v
