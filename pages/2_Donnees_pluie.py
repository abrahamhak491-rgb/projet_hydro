"""Page 2 : import des données de pluie et contrôle de qualité."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from calculs.qualite import (
    controler_qualite,
    convertir_dates,
    convertir_numerique,
    lire_fichier,
    maxima_annuels,
    nettoyer,
)

st.set_page_config(page_title="Données de pluie", page_icon="🌧️", layout="wide")

RACINE = Path(__file__).resolve().parent.parent
FICHIER_EXEMPLE = RACINE / "data" / "exemple_FICTIF_pluies_journalieres.csv"


def deviner(colonnes, mots, defaut=0):
    """Position de la première colonne dont le nom contient l'un des mots."""
    for i, c in enumerate(colonnes):
        if any(m in c.lower() for m in mots):
            return i
    return defaut


st.title("2. Données de pluie")
st.caption("Importer la série de pluies, vérifier sa qualité, puis en extraire les maxima annuels.")

# ---------------------------------------------------------------- source
source = st.radio(
    "Source des données",
    ["Importer mon fichier", "Utiliser le fichier d'exemple (fictif)"],
    horizontal=True,
)

if source.startswith("Importer"):
    fichier = st.file_uploader("Fichier de pluies (CSV, TXT ou Excel .xlsx)", type=["csv", "txt", "xlsx"])
    if fichier is None:
        st.info("Choisir un fichier. Excel : la première feuille est lue.")
        st.stop()
    nom_source = fichier.name
    entree = fichier
else:
    st.warning(
        "Ce fichier est **fictif** (données simulées pour tester l'application, avec quelques défauts volontaires). "
        "Il ne doit jamais servir de résultat dans le rapport."
    )
    if not FICHIER_EXEMPLE.exists():
        st.error("Le fichier d'exemple est introuvable dans le dossier « data ».")
        st.stop()
    nom_source = "exemple fictif"
    entree = str(FICHIER_EXEMPLE)

try:
    df = lire_fichier(entree, nom=nom_source if source.startswith("Importer") else FICHIER_EXEMPLE.name)
except Exception as erreur:
    st.error(f"Lecture impossible : {erreur}")
    st.stop()

with st.expander(f"Aperçu du fichier ({len(df)} lignes)", expanded=False):
    st.dataframe(df.head(15), hide_index=True, width="stretch")

# ---------------------------------------------------------------- colonnes
st.subheader("Contenu du fichier")
colonnes = list(df.columns)
type_donnees = st.radio(
    "Que contient le fichier ?",
    ["Pluies journalières (une ligne par jour)", "Maxima annuels (une ligne par année)"],
    horizontal=True,
)
journalier = type_donnees.startswith("Pluies")

if journalier:
    c1, c2 = st.columns(2)
    col_date = c1.selectbox("Colonne des dates", colonnes, index=deviner(colonnes, ("date", "jour")))
    autres = [c for c in colonnes if c != col_date] or colonnes
    col_val = c2.selectbox(
        "Colonne des hauteurs de pluie (mm)",
        autres,
        index=min(deviner(autres, ("pluie", "precip", "rain", "mm", "hauteur", "valeur")), len(autres) - 1),
    )

    dates = convertir_dates(df[col_date])
    brutes = convertir_numerique(df[col_val])
    negatives = brutes < 0
    valeurs_j = brutes.where(~negatives)
    illisibles = int(dates.isna().sum())

    with st.expander("Contrôle des valeurs journalières", expanded=False):
        st.write(
            f"- Lignes lues : **{len(df)}**\n"
            f"- Dates illisibles : **{illisibles}**\n"
            f"- Valeurs manquantes ou illisibles (codes -99, -999 inclus) : **{int((brutes.isna() & dates.notna()).sum())}**\n"
            f"- Valeurs négatives (ignorées) : **{int(negatives.sum())}**"
        )
    if illisibles > len(df) * 0.2:
        st.error("Plus de 20 % des dates sont illisibles : vérifier le choix de la colonne des dates (format attendu : JJ/MM/AAAA).")
        st.stop()

    cc1, cc2 = st.columns(2)
    min_jours = cc1.slider(
        "Jours valides minimum pour retenir une année",
        200,
        365,
        300,
        help="Une année avec trop de jours manquants risque d'avoir un maximum sous-estimé.",
    )
    exclure_incompletes = cc2.checkbox("Exclure les années incomplètes", value=True)

    annuel = maxima_annuels(dates, valeurs_j, min_jours_par_an=min_jours, exclure_incomplets=False)
    incompletes = annuel[~annuel["complete"]]
    if len(incompletes):
        detail = ", ".join(f"{int(r.annee)} ({int(r.jours_valides)} jours)" for r in incompletes.itertuples())
        st.warning(f"Année(s) incomplète(s) : {detail}.")
    retenu = annuel[annuel["complete"]] if exclure_incompletes else annuel
    serie = pd.Series(retenu["maximum"].to_numpy(), index=retenu["annee"].to_numpy().astype(int))
else:
    c1, c2 = st.columns(2)
    col_annee = c1.selectbox("Colonne des années", colonnes, index=deviner(colonnes, ("ann", "year")))
    autres = [c for c in colonnes if c != col_annee] or colonnes
    col_val = c2.selectbox(
        "Colonne des maxima annuels (mm)",
        autres,
        index=min(deviner(autres, ("max", "pluie", "precip", "mm", "valeur")), len(autres) - 1),
    )
    annees = pd.to_numeric(df[col_annee], errors="coerce")
    valeurs = convertir_numerique(df[col_val])
    ok = annees.notna()
    if ok.sum() == 0:
        st.error("Aucune année lisible dans cette colonne.")
        st.stop()
    serie = pd.Series(valeurs[ok].to_numpy(), index=annees[ok].astype(int).to_numpy())

if serie.empty:
    st.error("Aucun maximum annuel n'a pu être extrait.")
    st.stop()
serie = serie.sort_index()

# ---------------------------------------------------------------- contrôle de qualité
st.divider()
st.header("Contrôle de qualité")
rapport = controler_qualite(serie, annees=pd.Series(serie.index))

m1, m2, m3, m4 = st.columns(4)
m1.metric("Valeurs valides", rapport.n_valides)
m2.metric("Manquantes", rapport.n_manquants)
m3.metric("À vérifier", len(rapport.indices_aberrants))
m4.metric("Années absentes", len(rapport.annees_manquantes))

for niveau, texte in rapport.messages:
    if niveau == "erreur":
        st.error(texte)
    elif niveau == "avertissement":
        st.warning(texte)
    else:
        st.success(texte)

if not rapport.utilisable:
    st.error("Corriger le fichier avant de continuer : un problème bloquant a été détecté.")
    st.stop()

exclure_aberrants = False
if rapport.indices_aberrants:
    a_verifier = pd.DataFrame(
        {"Année": rapport.indices_aberrants, "Maximum (mm)": [float(serie.loc[i]) for i in rapport.indices_aberrants]}
    )
    st.dataframe(a_verifier, hide_index=True, width="content")
    exclure_aberrants = st.checkbox(
        "Exclure ces valeurs de l'analyse",
        value=False,
        help="À cocher seulement si la valeur est une erreur (saisie, unité). Une vraie crue exceptionnelle doit être conservée.",
    )

propre = nettoyer(serie, rapport, exclure_aberrants=exclure_aberrants).sort_index()
if len(propre) < 5:
    st.error("Moins de 5 valeurs exploitables : l'ajustement statistique est impossible.")
    st.stop()

# ---------------------------------------------------------------- résumé
st.subheader("Maxima annuels retenus")
g1, g2 = st.columns([2, 1])
with g1:
    st.bar_chart(propre, x_label="Année", y_label="Pluie maximale annuelle (mm)")
with g2:
    resume = pd.DataFrame(
        {
            "Indicateur": ["Nombre d'années", "Moyenne (mm)", "Écart-type (mm)", "Minimum (mm)", "Maximum (mm)", "Coefficient de variation", "Asymétrie"],
            "Valeur": [
                len(propre),
                round(propre.mean(), 1),
                round(propre.std(ddof=1), 1),
                round(propre.min(), 1),
                round(propre.max(), 1),
                round(propre.std(ddof=1) / propre.mean(), 2),
                round(float(propre.skew()), 2),
            ],
        }
    )
    st.dataframe(resume, hide_index=True, width="stretch")

st.session_state["maxima"] = propre
st.session_state["rapport_qualite"] = rapport
st.session_state["source_donnees"] = nom_source
st.success(f"{len(propre)} maxima annuels conservés pour l'ajustement statistique (étape 3).")
