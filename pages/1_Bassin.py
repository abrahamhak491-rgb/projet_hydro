"""Page 1 : caractéristiques du bassin versant et temps de concentration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from calculs.bassin import METHODES_TC, Bassin, tc_toutes_methodes

st.set_page_config(page_title="Bassin", page_icon="🌊", layout="wide")

OCCUPATIONS = [
    "Forêt",
    "Savane / prairie",
    "Culture",
    "Zone urbanisée",
    "Sol nu / rocheux",
    "Plan d'eau / marécage",
]

st.title("1. Bassin versant")
st.caption("Saisir les caractéristiques du bassin, puis choisir la méthode du temps de concentration.")

# Valeurs précédentes (conservées quand on revient sur la page).
prec: Bassin | None = st.session_state.get("bassin")

# ---------------------------------------------------------------- saisie
col_gauche, col_droite = st.columns(2)

with col_gauche:
    st.subheader("Caractéristiques")
    nom = st.text_input("Nom du bassin", value=prec.nom if prec else "Bassin exemple")
    surface = st.number_input(
        "Surface A (km²)", min_value=0.01, value=float(prec.surface_km2) if prec else 25.0, step=1.0, format="%.2f"
    )
    longueur = st.number_input(
        "Longueur L du plus long cheminement (km)",
        min_value=0.01,
        value=float(prec.longueur_km) if prec else 9.0,
        step=0.5,
        format="%.2f",
    )
    pente_pct = st.number_input(
        "Pente moyenne S du cheminement (%)",
        min_value=0.01,
        max_value=99.0,
        value=float(prec.pente * 100) if prec else 1.5,
        step=0.1,
        format="%.2f",
        help="Saisie en pourcentage (1,5 pour 1,5 %). Le calcul utilise m/m (0,015).",
    )
    connait_h = st.checkbox(
        "Je connais le dénivelé H (nécessaire pour Giandotti)",
        value=bool(prec and prec.denivele_m),
        help="H = altitude moyenne du bassin moins altitude de l'exutoire.",
    )
    denivele = None
    if connait_h:
        denivele = st.number_input(
            "Dénivelé H (m)",
            min_value=0.1,
            value=float(prec.denivele_m) if prec and prec.denivele_m else 120.0,
            step=5.0,
            format="%.1f",
        )

with col_droite:
    st.subheader("Occupation du sol")
    st.caption("Part de la surface par type de sol (total = 100 %). Facultatif à cette étape : servira au coefficient de ruissellement C et au CN.")
    parts_prec = {k: v * 100 for k, v in (prec.occupation_sol.items() if prec else [])}
    tableau = pd.DataFrame(
        {"Occupation du sol": OCCUPATIONS, "Part (%)": [float(parts_prec.get(o, 0.0)) for o in OCCUPATIONS]}
    )
    edite = st.data_editor(
        tableau,
        hide_index=True,
        width="stretch",
        disabled=["Occupation du sol"],
        column_config={"Part (%)": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, step=1.0, format="%.1f")},
        key="occupation_editor",
    )
    total_pct = float(edite["Part (%)"].sum())
    occupation: dict[str, float] = {}
    if total_pct == 0:
        st.info("Aucune occupation du sol saisie.")
    elif abs(total_pct - 100) <= 1:
        occupation = {r["Occupation du sol"]: r["Part (%)"] / 100 for _, r in edite.iterrows() if r["Part (%)"] > 0}
        st.success(f"Total : {total_pct:.1f} %")
    else:
        st.warning(f"Total : {total_pct:.1f} %. Il doit faire 100 % : l'occupation du sol est ignorée pour l'instant.")

# ---------------------------------------------------------------- calcul
try:
    bassin = Bassin(
        nom=nom.strip() or "Bassin sans nom",
        surface_km2=surface,
        longueur_km=longueur,
        pente=pente_pct / 100,
        denivele_m=denivele,
        occupation_sol=occupation,
    )
except ValueError as erreur:
    st.error(str(erreur))
    st.stop()

st.divider()
st.header("Temps de concentration")

resultats = tc_toutes_methodes(bassin)
lignes = []
for cle, infos in METHODES_TC.items():
    if cle in resultats:
        lignes.append({"Méthode": infos["nom"], "tc (h)": round(resultats[cle], 2), "tc (min)": round(resultats[cle] * 60)})
    else:
        lignes.append({"Méthode": infos["nom"], "tc (h)": None, "tc (min)": None})
table_tc = pd.DataFrame(lignes)

col_table, col_graph = st.columns([1, 1])
with col_table:
    st.dataframe(table_tc, hide_index=True, width="stretch")
    if "giandotti" not in resultats:
        st.caption("Giandotti n'est pas calculé : saisir le dénivelé H.")
with col_graph:
    st.bar_chart(table_tc.dropna().set_index("Méthode")["tc (h)"], y_label="tc (heures)")

if len(resultats) >= 2:
    ecart = max(resultats.values()) / min(resultats.values())
    if ecart >= 2:
        st.warning(
            f"Les méthodes donnent des résultats très différents (rapport de {ecart:.1f} entre la plus grande et la plus petite valeur). "
            "Vérifier que le bassin entre dans le domaine de validité de chaque formule (voir ci-dessous) avant de choisir."
        )
    else:
        st.caption(f"Rapport entre la plus grande et la plus petite valeur : {ecart:.1f}. Cet écart donne une idée de l'incertitude sur tc.")

options = list(resultats)
defaut = st.session_state.get("tc_methode")
choix = st.selectbox(
    "Méthode retenue pour la suite des calculs",
    options,
    index=options.index(defaut) if defaut in options else 0,
    format_func=lambda c: METHODES_TC[c]["nom"],
)
tc_h = resultats[choix]
st.metric(f"Temps de concentration retenu ({METHODES_TC[choix]['nom']})", f"{tc_h:.2f} h", f"{tc_h * 60:.0f} min", delta_color="off")

# Résultats conservés pour les pages suivantes.
st.session_state["bassin"] = bassin
st.session_state["tc_methode"] = choix
st.session_state["tc_h"] = tc_h

# ---------------------------------------------------------------- hypothèses
st.subheader("Hypothèses et domaines de validité")
for cle, infos in METHODES_TC.items():
    with st.expander(infos["nom"], expanded=(cle == choix)):
        st.markdown(f"**Formule** : `{infos['formule']}`")
        st.markdown(f"**Données nécessaires** : {infos['donnees']}")
        st.markdown(f"**Domaine de validité** : {infos['validite']}")
