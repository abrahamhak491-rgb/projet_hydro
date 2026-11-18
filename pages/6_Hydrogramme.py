"""Page 6 : hydrogramme de crue par hydrogramme unitaire (SCS ou Nash)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from calculs.hydrogramme import (
    HYPOTHESES_HYDROGRAMME,
    hydrogramme_nash,
    hydrogramme_scs,
    k_depuis_retard,
    pas_automatique,
    proprietes,
    temps_de_pointe_scs,
)

st.set_page_config(page_title="Hydrogramme", page_icon="🌊", layout="wide")

st.title("6. Hydrogramme de crue")
st.caption("Évolution du débit au cours du temps pour la pluie de projet, par hydrogramme unitaire SCS ou Nash.")

bassin = st.session_state.get("bassin")
tc_h = st.session_state.get("tc_h")
debits = st.session_state.get("debits")
projet = st.session_state.get("debit_projet")
if bassin is None or not tc_h or debits is None or projet is None:
    st.warning("Il manque des étapes : terminer le **Bassin** (1), les **IDF** (4) et le **Débit de pointe** (5).")
    st.stop()

surface = bassin.surface_km2
duree_pluie = st.session_state.get("duree_pluie_h", tc_h)
st.write(
    f"Bassin **{bassin.nom}** : A = {surface:g} km², tc = {tc_h:.2f} h, durée de la pluie de projet D = {duree_pluie:.2f} h "
    f"(définie à l'étape 5)."
)
if projet["methode"] == "Rationnelle":
    st.info(
        "L'hydrogramme est construit à partir de la **pluie nette** de la méthode SCS-CN. Le débit de projet retenu à l'étape 5 "
        "est la méthode rationnelle : les deux pointes peuvent donc différer (comparaison plus bas)."
    )

# ---------------------------------------------------------------- réglages
c1, c2 = st.columns(2)
methode = c1.radio("Méthode de l'hydrogramme unitaire", ["SCS", "Nash"], horizontal=True)
if methode == "SCS":
    forme = c1.radio("Forme", ["Curviligne", "Triangulaire"], horizontal=True, help="Courbe tabulée du SCS, ou triangle simplifié (base = 2,67·Tp).")
    st.info(HYPOTHESES_HYDROGRAMME["scs"])
    tp = temps_de_pointe_scs(tc_h, duree_pluie)
    c1.metric("Temps de pointe Tp = D/2 + 0,6·tc", f"{tp:.2f} h")
else:
    n = c1.number_input("Nombre de réservoirs n", min_value=1.0, max_value=10.0, value=3.0, step=0.5, help="Plus n est grand, plus l'hydrogramme est symétrique et pointu.")
    k_auto = k_depuis_retard(n, tc_h)
    k_manuel = c1.checkbox("Saisir K moi-même", value=False)
    k_h = c1.number_input("Constante K (h)", min_value=0.01, value=float(round(k_auto, 3)), step=0.1, format="%.3f") if k_manuel else k_auto
    c1.metric("Constante K", f"{k_h:.3f} h", f"temps de retard n·K = {n * k_h:.2f} h", delta_color="off")
    st.info(HYPOTHESES_HYDROGRAMME["nash"])

options_pas = {"Automatique": None, "5 min": 5 / 60, "10 min": 10 / 60, "15 min": 15 / 60, "30 min": 30 / 60, "1 h": 1.0}
choix_pas = c2.selectbox("Pas de temps", list(options_pas))
pas = options_pas[choix_pas]
periodes = list(debits["T (ans)"])
defaut_t = projet["T"] if projet["T"] in periodes else periodes[-1]
t_comparees = c2.multiselect(
    "Périodes de retour à comparer sur le graphique",
    periodes,
    default=[defaut_t],
    format_func=lambda t: f"{t:g} ans",
)
if not t_comparees:
    st.warning("Choisir au moins une période de retour.")
    st.stop()
t_principale = c2.selectbox(
    "Période de retour détaillée (tableau et export)",
    t_comparees,
    index=t_comparees.index(defaut_t) if defaut_t in t_comparees else 0,
    format_func=lambda t: f"{t:g} ans",
)


# ---------------------------------------------------------------- calcul
def construire(pluie_nette: float) -> pd.DataFrame:
    if methode == "SCS":
        return hydrogramme_scs(pluie_nette, surface, tc_h, duree_pluie, forme.lower(), pas)
    return hydrogramme_nash(pluie_nette, surface, duree_pluie, n, k_h, pas)


hydros, props = {}, {}
try:
    for t in t_comparees:
        pn = float(debits.loc[debits["T (ans)"] == t, "Pluie nette (mm)"].iloc[0])
        hydros[t] = construire(pn)
        props[t] = proprietes(hydros[t], surface, pn)
except ValueError as erreur:
    st.error(str(erreur))
    st.stop()

pn_principale = float(debits.loc[debits["T (ans)"] == t_principale, "Pluie nette (mm)"].iloc[0])
hp = hydros[t_principale]
pp = props[t_principale]

if pn_principale == 0:
    st.warning(f"Pour T = {t_principale:g} ans, la pluie nette est nulle (pluie inférieure à l'abstraction initiale) : l'hydrogramme est nul. Revoir le CN à l'étape 5.")

# ---------------------------------------------------------------- résultats
st.header(f"Hydrogramme de crue, T = {t_principale:g} ans")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Débit de pointe", f"{pp['Qp (m³/s)']:.1f} m³/s")
m2.metric("Temps de pointe", f"{pp['Temps de pointe (h)']:.2f} h")
m3.metric("Volume écoulé", f"{pp['Volume écoulé (m³)'] / 1e6:.3f} Mm³")
duree_hydro = pp["Durée de l'hydrogramme (h)"]
m4.metric("Durée de l'hydrogramme", f"{duree_hydro:.1f} h")

rapport_volumes = pp["Rapport des volumes"]
if pn_principale > 0:
    if abs(rapport_volumes - 1) <= 0.02:
        st.success(f"Volume conservé : le volume écoulé est égal à {rapport_volumes:.1%} du volume de pluie nette (écart dû au pas de temps et à la troncature).")
    else:
        st.warning(f"Le volume écoulé vaut {rapport_volumes:.1%} du volume de pluie nette : essayer un pas de temps plus fin.")

fig, ax = plt.subplots(figsize=(9.5, 5))
for t, h in hydros.items():
    principal = t == t_principale
    ax.plot(h["Temps (h)"], h["Débit (m³/s)"], linewidth=2.6 if principal else 1.4, label=f"T = {t:g} ans")
    if principal and len(hydros) == 1:
        ax.fill_between(h["Temps (h)"], h["Débit (m³/s)"], alpha=0.15)
ax.plot(pp["Temps de pointe (h)"], pp["Qp (m³/s)"], "ko", zorder=3)
ax.annotate(f"{pp['Qp (m³/s)']:.1f} m³/s", (pp["Temps de pointe (h)"], pp["Qp (m³/s)"]), xytext=(8, 4), textcoords="offset points")
ax.set_xlabel("Temps depuis le début de la pluie nette (h)")
ax.set_ylabel("Débit (m³/s)")
ax.set_xlim(left=0)
q_max = max(float(h["Débit (m³/s)"].max()) for h in hydros.values())
ax.set_ylim(0, 1.5 * q_max if q_max > 0 else 1.0)  # place au-dessus des courbes pour la pluie nette
ax.grid(alpha=0.3)
# Hyétogramme de la pluie nette (période de retour détaillée), en haut, axe inversé.
ax2 = ax.twinx()
ie = pn_principale / duree_pluie
ax2.bar(0, ie, width=duree_pluie, align="edge", color="tab:blue", alpha=0.25, label="Pluie nette")
ax2.set_ylim(max(ie * 3.3, 1e-6), 0)
ax2.set_ylabel("Intensité de la pluie nette (mm/h)")
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="center right")
ax.set_title(f"Hydrogramme de crue ({methode}) : {bassin.nom}")
st.pyplot(fig)
plt.close(fig)

# ---------------------------------------------------------------- comparaison des pointes
st.subheader("Comparaison avec le débit de pointe de l'étape 5")
ligne = debits[debits["T (ans)"] == t_principale].iloc[0]
comp = pd.DataFrame(
    {
        "Source": ["Hydrogramme (cette page)", "SCS-CN (étape 5, formule)", "Rationnelle (étape 5)"],
        "Débit de pointe (m³/s)": [round(pp["Qp (m³/s)"], 1), round(float(ligne["Q SCS-CN (m³/s)"]), 1), round(float(ligne["Q rationnelle (m³/s)"]), 1)],
    }
)
st.dataframe(comp, hide_index=True, width="content")
st.caption(
    "L'hydrogramme SCS retrouve la pointe de la formule SCS-CN (à la précision du pas de temps près). "
    "Avec Nash, la pointe diffère car la forme de l'hydrogramme change : c'est une autre estimation, à comparer."
)

# ---------------------------------------------------------------- tableau et export
st.subheader("Ordonnées de l'hydrogramme")
sortie = hp.copy()
sortie["Temps (h)"] = sortie["Temps (h)"].round(4)
sortie["Débit (m³/s)"] = sortie["Débit (m³/s)"].round(3)
col_t, col_b = st.columns([3, 1])
col_t.dataframe(sortie, hide_index=True, width="stretch", height=260)
col_b.download_button(
    "Télécharger en CSV",
    data=sortie.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
    file_name=f"hydrogramme_T{t_principale:g}ans.csv",
    mime="text/csv",
    help="Séparateur point-virgule et virgule décimale : s'ouvre directement dans Excel en français.",
)

# Résultats conservés pour le rapport.
st.session_state["hydrogramme"] = hp
st.session_state["hydrogrammes"] = hydros
st.session_state["hydro_proprietes"] = props
st.session_state["hydro_methode"] = methode if methode == "Nash" else f"SCS {forme.lower()}"
st.session_state["hydro_periode"] = float(t_principale)
