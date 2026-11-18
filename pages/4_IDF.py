"""Page 4 : courbes Intensité-Durée-Fréquence et coefficients de Montana."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from calculs.idf import (
    DUREES_PAR_DEFAUT_H,
    HYPOTHESES_IDF,
    colonnes_durees,
    courbes_idf,
    exposant_depuis_rapport,
    intensite,
    pluies_depuis_courtes_durees,
    pluies_depuis_journalier,
)
from calculs.qualite import convertir_numerique, lire_fichier
from calculs.statistique import NOMS_LOIS

st.set_page_config(page_title="IDF", page_icon="🌧️", layout="wide")

RACINE = Path(__file__).resolve().parent.parent
FICHIER_EXEMPLE_COURT = RACINE / "data" / "exemple_FICTIF_pluies_courte_duree.csv"

st.title("4. Courbes IDF et coefficients de Montana")
st.caption("Relation de Montana : i(t) = a · t^(-b), avec i en mm/h. Une courbe par période de retour.")

ajustement = st.session_state.get("ajustement")
periodes = st.session_state.get("periodes_retour")
if ajustement is None or not periodes:
    st.warning("Aucun ajustement statistique. Passer d'abord par la page **Ajustement** (étape 3).")
    st.stop()

loi_nom = NOMS_LOIS[ajustement.loi]
tc_h = st.session_state.get("tc_h")

# ---------------------------------------------------------------- méthode
methode = st.radio(
    "Données disponibles pour construire les courbes",
    [
        "Pluies journalières seulement (exposant b imposé)",
        "Pluies de courte durée (15 min, 1 h, 6 h, 24 h...)",
    ],
)
journalier = methode.startswith("Pluies journalières")

if journalier:
    # -------------------------------------------------------- méthode 1
    st.info(HYPOTHESES_IDF["journalier"])
    p24 = {float(T): float(ajustement.quantile(T)) for T in periodes}
    st.write(f"Pluies journalières maximales de période de retour T (loi **{loi_nom}**, étape 3) :")
    st.dataframe(
        pd.DataFrame({"T (ans)": list(p24), "P24 (mm)": [round(v, 1) for v in p24.values()]}).set_index("T (ans)").T,
        width="stretch",
    )

    c1, c2 = st.columns(2)
    mode_b = c1.radio("Exposant de Montana b", ["Je connais b", "Je connais le rapport P(1 h) / P(24 h)"])
    if mode_b == "Je connais b":
        b = c1.number_input(
            "b",
            min_value=0.20,
            max_value=0.95,
            value=float(st.session_state.get("b_montana", 0.65)),
            step=0.01,
            help="Valeur indicative par défaut. À remplacer par la valeur du cours ou d'une étude régionale.",
        )
    else:
        rapport = c1.number_input("P(1 h) / P(24 h)", min_value=0.05, max_value=0.90, value=0.35, step=0.01)
        b = exposant_depuis_rapport(rapport)
        c1.metric("b déduit", f"{b:.3f}")
    facteur = c2.number_input(
        "Facteur de correction pluie journalière → pluie sur 24 h",
        min_value=1.0,
        max_value=1.5,
        value=float(st.session_state.get("facteur_24h", 1.00)),
        step=0.01,
        help="1,00 = aucune correction. 1,13 est une valeur classique (Weiss) : à appliquer seulement si le cours le prévoit.",
    )
    c2.caption("Le défaut b = 0,65 est une valeur indicative, pas une donnée du bassin : la remplacer dès que la valeur de référence est connue.")
    durees_choisies = st.multiselect(
        "Durées (heures)", list(DUREES_PAR_DEFAUT_H) + [4.0, 8.0, 18.0], default=list(DUREES_PAR_DEFAUT_H)
    )
    durees = sorted(durees_choisies)
    if len(durees) < 3:
        st.warning("Choisir au moins 3 durées.")
        st.stop()
    pluies = pluies_depuis_journalier(p24, durees, b, facteur)
    methode_cle = "journalier"
    st.session_state["b_montana"] = b
    st.session_state["facteur_24h"] = facteur
else:
    # -------------------------------------------------------- méthode 2
    st.info(HYPOTHESES_IDF["courte_duree"])
    source = st.radio("Source", ["Importer mon fichier", "Utiliser le fichier d'exemple (fictif)"], horizontal=True)
    if source.startswith("Importer"):
        fichier = st.file_uploader(
            "Maxima annuels par durée (CSV ou Excel) : une colonne par durée nommée « 15 min », « 1 h », « 24 h »...",
            type=["csv", "txt", "xlsx"],
        )
        if fichier is None:
            st.stop()
        entree, nom = fichier, fichier.name
    else:
        st.warning("Fichier **fictif**, uniquement pour tester l'application.")
        if not FICHIER_EXEMPLE_COURT.exists():
            st.error("Le fichier d'exemple est introuvable dans le dossier « data ».")
            st.stop()
        entree, nom = str(FICHIER_EXEMPLE_COURT), FICHIER_EXEMPLE_COURT.name
    try:
        df = lire_fichier(entree, nom=nom)
    except Exception as erreur:
        st.error(f"Lecture impossible : {erreur}")
        st.stop()
    colonnes = colonnes_durees(df.columns)
    if len(colonnes) < 3:
        st.error("Il faut au moins 3 colonnes dont le nom est une durée (par exemple « 15 min », « 1 h », « 24 h »).")
        st.stop()
    maxima = {}
    for col, duree in colonnes.items():
        valeurs = convertir_numerique(df[col]).dropna()
        valeurs = valeurs[valeurs > 0]
        if len(valeurs) < 5:
            st.error(f"La durée « {col} » a moins de 5 valeurs exploitables.")
            st.stop()
        maxima[duree] = valeurs.to_numpy()
    st.write(
        "Durées lues : "
        + ", ".join(f"{c} ({len(maxima[d])} valeurs)" for c, d in sorted(colonnes.items(), key=lambda kv: kv[1]))
        + f". Loi utilisée à chaque durée : **{loi_nom}**."
    )
    try:
        pluies = pluies_depuis_courtes_durees(maxima, ajustement.loi, periodes, ajustement.methode)
    except Exception as erreur:
        st.error(f"Ajustement impossible : {erreur}")
        st.stop()
    methode_cle = "courte_duree"

# ---------------------------------------------------------------- courbes IDF
intensites, montana = courbes_idf(pluies)
durees_h = pluies.index.to_numpy(dtype=float)

st.header("Coefficients de Montana")
affichage = montana.copy()
affichage["a (t en h)"] = affichage["a (t en h)"].round(2)
affichage["a (t en min)"] = affichage["a (t en min)"].round(2)
affichage["b"] = affichage["b"].round(3)
affichage["R²"] = affichage["R²"].round(4)
st.dataframe(affichage, hide_index=True, width="stretch")
st.caption(
    "i en mm/h. Deux conventions pour a : durée en heures ou en minutes (la valeur de b est la même). "
    "Vérifier laquelle utilise le cours avant de comparer avec d'autres sources."
)
if not journalier and (montana["R²"] < 0.98).any():
    st.warning("Le R² est inférieur à 0,98 pour certaines périodes de retour : une seule relation de Montana représente mal ces données.")

st.header("Courbes IDF")
fig, ax = plt.subplots(figsize=(9, 5.2))
t_grille = np.geomspace(durees_h.min(), durees_h.max(), 100)
for _, ligne in montana.iterrows():
    T = ligne["Période de retour (ans)"]
    ax.plot(t_grille, intensite(ligne["a (t en h)"], ligne["b"], t_grille), label=f"T = {T:g} ans")
    ax.scatter(durees_h, intensites[T].to_numpy(), s=14, color="black", zorder=3)
if tc_h:
    ax.axvline(tc_h, color="gray", linestyle="--")
    ax.text(tc_h, 0.03, f" tc = {tc_h:.2f} h", transform=ax.get_xaxis_transform(), color="gray")
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Durée (h)")
ax.set_ylabel("Intensité (mm/h)")
ax.set_title("Courbes Intensité-Durée-Fréquence")
ax.grid(alpha=0.3, which="both")
ax.legend()
st.pyplot(fig)
plt.close(fig)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Intensités (mm/h)")
    tab_i = intensites.copy()
    tab_i.columns = [f"T = {c:g}" for c in tab_i.columns]
    st.dataframe(tab_i.round(1), width="stretch")
with c2:
    st.subheader("Hauteurs de pluie (mm)")
    tab_p = pluies.copy()
    tab_p.columns = [f"T = {c:g}" for c in tab_p.columns]
    st.dataframe(tab_p.round(1), width="stretch")

# ---------------------------------------------------------------- intensité de projet
st.header("Intensité de projet")
if not tc_h:
    st.info("Le temps de concentration n'est pas encore calculé (page **Bassin**). Il servira à lire l'intensité de projet.")
else:
    projet = pd.DataFrame(
        {
            "T (ans)": montana["Période de retour (ans)"],
            f"Intensité pour t = tc = {tc_h:.2f} h (mm/h)": [
                round(intensite(r["a (t en h)"], r["b"], tc_h), 1) for _, r in montana.iterrows()
            ],
        }
    )
    st.dataframe(projet, hide_index=True, width="content")
    if tc_h < durees_h.min() or tc_h > durees_h.max():
        st.warning(
            f"tc ({tc_h:.2f} h) est hors de l'intervalle des durées utilisées ({durees_h.min():g} à {durees_h.max():g} h) : "
            "l'intensité de projet est une extrapolation."
        )
    elif journalier and tc_h < 1:
        st.warning("tc est inférieur à 1 h : la relation d'échelle depuis la pluie journalière est peu fiable sous cette durée.")

# Résultats conservés pour les pages suivantes.
st.session_state["montana"] = montana
st.session_state["idf_intensites"] = intensites
st.session_state["idf_pluies"] = pluies
st.session_state["idf_methode"] = methode_cle
