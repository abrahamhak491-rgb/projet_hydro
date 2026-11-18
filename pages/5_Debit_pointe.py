"""Page 5 : débit de pointe par la méthode rationnelle et par la méthode SCS-CN."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from calculs.debit import (
    CN_AMC2,
    C_PAR_OCCUPATION,
    GROUPES_SOL,
    HYPOTHESES_DEBIT,
    c_pondere,
    cn_pondere,
    cn_selon_humidite,
    comparer_debits,
)

st.set_page_config(page_title="Débit de pointe", page_icon="🌊", layout="wide")

st.title("5. Débit de pointe")
st.caption("Deux méthodes appliquées à la pluie de projet : rationnelle et SCS-CN. Leur écart donne une idée de l'incertitude.")

bassin = st.session_state.get("bassin")
tc_h = st.session_state.get("tc_h")
montana = st.session_state.get("montana")
manque = []
if bassin is None or not tc_h:
    manque.append("**Bassin** (étape 1)")
if montana is None:
    manque.append("**IDF** (étape 4)")
if manque:
    st.warning("Il manque : " + " et ".join(manque) + ". Terminer ces étapes d'abord.")
    st.stop()

st.write(
    f"Bassin **{bassin.nom}** : A = {bassin.surface_km2:g} km², tc = {tc_h:.2f} h "
    f"({st.session_state.get('tc_methode', '?')})."
)
st.warning(
    "Les tables de C et de CN proposées sont des **valeurs génériques de la littérature**, pas des valeurs calées sur votre bassin. "
    "Les modifier dans le tableau ci-dessous avec les valeurs du cours ou d'études régionales."
)

# ---------------------------------------------------------------- coefficients
st.header("Coefficients du bassin")
occupation = bassin.occupation_sol
modes = ["Saisir C et CN directement"]
if occupation:
    modes.insert(0, "Calculer à partir de l'occupation du sol")
mode = st.radio("Origine de C et de CN", modes, horizontal=True)

col_a, col_b = st.columns(2)
amc = col_b.selectbox(
    "État d'humidité initiale du sol (méthode SCS)",
    ["II", "I", "III"],
    format_func=lambda k: {"I": "I : sol sec", "II": "II : humidité moyenne (usuel)", "III": "III : sol humide (crue défavorable)"}[k],
)

if mode.startswith("Calculer"):
    groupe = col_a.selectbox("Groupe hydrologique du sol", list(GROUPES_SOL), index=1, format_func=lambda g: GROUPES_SOL[g])
    tableau = pd.DataFrame(
        {
            "Occupation du sol": list(occupation),
            "Part (%)": [round(f * 100, 1) for f in occupation.values()],
            "C": [C_PAR_OCCUPATION[o] for o in occupation],
            "CN (humidité II)": [float(CN_AMC2[o][groupe]) for o in occupation],
        }
    )
    edite = st.data_editor(
        tableau,
        hide_index=True,
        width="stretch",
        disabled=["Occupation du sol", "Part (%)"],
        column_config={
            "C": st.column_config.NumberColumn(min_value=0.01, max_value=1.0, step=0.01, format="%.2f"),
            "CN (humidité II)": st.column_config.NumberColumn(min_value=1.0, max_value=100.0, step=1.0, format="%.0f"),
        },
        key=f"table_coefficients_{groupe}",
    )
    if edite[["C", "CN (humidité II)"]].isna().any().any():
        st.error("Compléter toutes les cases de C et de CN.")
        st.stop()
    try:
        c = c_pondere(occupation, dict(zip(edite["Occupation du sol"], edite["C"])))
        cn_ii = cn_pondere(
            occupation, groupe, {o: {groupe: v} for o, v in zip(edite["Occupation du sol"], edite["CN (humidité II)"])}
        )
    except ValueError as erreur:
        st.error(str(erreur))
        st.stop()
else:
    st.info("Occupation du sol non renseignée sur la page Bassin : saisir C et CN directement." if not occupation else "Valeurs saisies à la main.")
    c = col_a.number_input("Coefficient de ruissellement C", min_value=0.01, max_value=1.0, value=0.30, step=0.01)
    cn_ii = col_a.number_input("CN (humidité II)", min_value=1.0, max_value=100.0, value=75.0, step=1.0)

cn = cn_selon_humidite(cn_ii, amc)
m1, m2, m3 = st.columns(3)
m1.metric("C moyen", f"{c:.2f}")
m2.metric("CN (humidité II)", f"{cn_ii:.1f}")
m3.metric(f"CN utilisé (humidité {amc})", f"{cn:.1f}")

# ---------------------------------------------------------------- options
with st.expander("Options de calcul", expanded=False):
    o1, o2, o3 = st.columns(3)
    majorer = o1.checkbox(
        "Majorer C pour T ≥ 25 ans",
        value=False,
        help="Facteurs de Chow : 1,10 (25 ans), 1,20 (50 ans), 1,25 (100 ans), avec C ≤ 1. À cocher si le cours le prévoit.",
    )
    lam = o2.number_input(
        "Rapport λ = Ia / S", min_value=0.05, max_value=0.30, value=0.20, step=0.05, format="%.2f",
        help="0,20 est la valeur standard du SCS. Des valeurs plus faibles sont parfois retenues en climat tropical.",
    )
    d_defaut = o3.checkbox("Durée de pluie D = tc (usuel)", value=True)
    if d_defaut:
        duree_pluie = tc_h
    else:
        duree_pluie = o3.number_input("Durée D de la pluie de projet (h)", min_value=0.1, value=float(round(tc_h, 2)), step=0.5)

# ---------------------------------------------------------------- calcul
try:
    res = comparer_debits(montana, bassin.surface_km2, tc_h, c, cn, duree_pluie, lam, majorer)
except ValueError as erreur:
    st.error(str(erreur))
    st.stop()

st.header("Débits de pointe")
affichage = res.copy()
for col, nd in [("i(tc) (mm/h)", 1), ("C utilisé", 2), ("Q rationnelle (m³/s)", 1), ("P(D) (mm)", 1), ("Pluie nette (mm)", 1),
                ("Tp (h)", 2), ("Q SCS-CN (m³/s)", 1), ("Rapport SCS / rationnelle", 2), ("Débit spécifique moyen (m³/s/km²)", 3)]:
    affichage[col] = affichage[col].round(nd)
st.dataframe(affichage, hide_index=True, width="stretch")
st.caption(
    "Rationnelle : Q = C · i(tc) · A / 3,6. SCS-CN : pluie P(D) = i·D sur la durée D, convertie en pluie nette puis en débit par l'hydrogramme unitaire triangulaire. "
    "Le débit spécifique moyen (m³/s par km²) sert à juger si les ordres de grandeur sont plausibles."
)

if (res["Pluie nette (mm)"] == 0).any():
    periodes_nulles = ", ".join(f"{t:g}" for t in res.loc[res["Pluie nette (mm)"] == 0, "T (ans)"])
    st.warning(f"Pour T = {periodes_nulles} ans, la pluie est inférieure à l'abstraction initiale : la méthode SCS donne un ruissellement nul. Vérifier le CN.")
if bassin.surface_km2 > 50:
    st.warning(
        f"La surface ({bassin.surface_km2:g} km²) dépasse l'ordre de grandeur habituel de la méthode rationnelle (au plus quelques dizaines de km²) : "
        "vérifier la limite donnée dans le cours et interpréter ce résultat avec prudence."
    )
ecart = res["Rapport SCS / rationnelle"]
if (ecart > 2).any() or (ecart < 0.5).any():
    st.warning("Les deux méthodes diffèrent d'un facteur supérieur à 2 : l'incertitude est grande. Vérifier C, CN, le groupe de sol et le domaine de validité de chaque méthode.")
else:
    st.caption(f"Rapport SCS / rationnelle compris entre {ecart.min():.2f} et {ecart.max():.2f}.")

# ---------------------------------------------------------------- graphique
fig, ax = plt.subplots(figsize=(9, 4.6))
ax.plot(res["T (ans)"], res["Q rationnelle (m³/s)"], marker="o", label="Rationnelle")
ax.plot(res["T (ans)"], res["Q SCS-CN (m³/s)"], marker="s", label="SCS-CN")
ax.fill_between(
    res["T (ans)"],
    res[["Q rationnelle (m³/s)", "Q SCS-CN (m³/s)"]].min(axis=1),
    res[["Q rationnelle (m³/s)", "Q SCS-CN (m³/s)"]].max(axis=1),
    alpha=0.15,
    label="Écart entre méthodes",
)
ax.set_xscale("log")
ax.set_xticks(res["T (ans)"])
ax.set_xticklabels([f"{t:g}" for t in res["T (ans)"]])
ax.minorticks_off()
ax.set_xlabel("Période de retour (ans)")
ax.set_ylabel("Débit de pointe (m³/s)")
ax.set_title("Débit de pointe en fonction de la période de retour")
ax.grid(alpha=0.3)
ax.legend()
st.pyplot(fig)
plt.close(fig)

# ---------------------------------------------------------------- débit de projet
st.header("Débit de projet retenu")
c1, c2 = st.columns(2)
periodes = list(res["T (ans)"])
prec = st.session_state.get("debit_projet", {})
t_choisi = c1.selectbox(
    "Période de retour de projet (ans)",
    periodes,
    index=periodes.index(prec["T"]) if prec.get("T") in periodes else (periodes.index(50.0) if 50.0 in periodes else len(periodes) - 1),
    format_func=lambda t: f"{t:g}",
)
methodes = ["SCS-CN", "Rationnelle", "Moyenne des deux méthodes"]
methode = c2.radio("Méthode retenue", methodes, index=methodes.index(prec["methode"]) if prec.get("methode") in methodes else 0, horizontal=True)
ligne = res[res["T (ans)"] == t_choisi].iloc[0]
q_scs, q_rat = float(ligne["Q SCS-CN (m³/s)"]), float(ligne["Q rationnelle (m³/s)"])
q_retenu = {"SCS-CN": q_scs, "Rationnelle": q_rat}.get(methode, (q_scs + q_rat) / 2)
r1, r2, r3 = st.columns(3)
r1.metric(f"Débit de pointe, T = {t_choisi:g} ans", f"{q_retenu:.1f} m³/s")
r2.metric("Temps de pointe Tp (SCS)", f"{ligne['Tp (h)']:.2f} h")
r3.metric("Pluie nette (SCS)", f"{ligne['Pluie nette (mm)']:.1f} mm")
if methode == "Moyenne des deux méthodes":
    st.caption("La moyenne n'a pas de justification théorique : à utiliser seulement si le cours ou l'enseignant le demande, et à justifier dans le rapport.")

# ---------------------------------------------------------------- hypothèses
st.subheader("Hypothèses et domaines de validité")
with st.expander("Méthode rationnelle"):
    st.write(HYPOTHESES_DEBIT["rationnelle"])
with st.expander("Méthode SCS-CN"):
    st.write(HYPOTHESES_DEBIT["scs"])
    if mode.startswith("Calculer"):
        st.write("CN d'après les tables SCS TR-55 (conditions américaines), moyennés par la surface de chaque occupation.")

# Résultats conservés pour les pages suivantes.
st.session_state["debits"] = res
st.session_state["duree_pluie_h"] = float(duree_pluie)
st.session_state["debit_projet"] = {
    "T": float(t_choisi),
    "methode": methode,
    "Qp": float(q_retenu),
    "Qp_scs": q_scs,
    "Qp_rationnelle": q_rat,
    "Tp_h": float(ligne["Tp (h)"]),
    "pluie_nette_mm": float(ligne["Pluie nette (mm)"]),
    "duree_pluie_h": float(duree_pluie),
    "surface_km2": float(bassin.surface_km2),
    "tc_h": float(tc_h),
    "c": float(c),
    "cn": float(cn),
}
