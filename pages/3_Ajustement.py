"""Page 3 : ajustement statistique des maxima annuels et quantiles de pluie."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from calculs.statistique import (
    HYPOTHESES_STAT,
    NOMS_LOIS,
    PERIODES_RETOUR,
    avertissement_extrapolation,
    comparer_lois,
    meilleure_loi,
    positions_empiriques,
)

st.set_page_config(page_title="Ajustement", page_icon="📈", layout="wide")

st.title("3. Ajustement statistique")
st.caption("Ajuster les lois de Gumbel, GEV et Galton aux maxima annuels, tester leur adéquation et lire les quantiles de pluie.")

serie = st.session_state.get("maxima")
if serie is None:
    st.warning("Aucune donnée de pluie. Passer d'abord par la page **Données de pluie** (étape 2).")
    st.stop()

x = serie.to_numpy(dtype=float)
st.write(
    f"Série utilisée : **{len(x)} maxima annuels** ({int(serie.index.min())} à {int(serie.index.max())}), "
    f"source : {st.session_state.get('source_donnees', 'inconnue')}."
)

# ---------------------------------------------------------------- réglages
c1, c2, c3 = st.columns(3)
choix_methode = c1.radio(
    "Estimation des paramètres",
    ["Maximum de vraisemblance", "Moments"],
    help="La GEV s'ajuste toujours par maximum de vraisemblance.",
)
methode = "mv" if choix_methode.startswith("Maximum") else "moments"
alpha = c2.select_slider("Seuil de signification des tests", options=[0.01, 0.05, 0.10], value=0.05)
periodes = sorted(
    c3.multiselect("Périodes de retour (ans)", [2, 5, 10, 20, 25, 50, 100, 200, 500, 1000], default=list(PERIODES_RETOUR))
)
if not periodes:
    st.warning("Choisir au moins une période de retour.")
    st.stop()
if methode == "moments":
    st.caption("Méthode des moments : appliquée à Gumbel et Galton. La GEV reste ajustée par maximum de vraisemblance.")

# ---------------------------------------------------------------- ajustement
quantiles, tests, ajustements = comparer_lois(x, periodes, methode, alpha)
if not ajustements:
    st.error("Aucune loi n'a pu être ajustée à cette série.")
    st.dataframe(tests, hide_index=True)
    st.stop()

st.header("Tests d'adéquation")
st.dataframe(tests, hide_index=True, width="stretch")
st.caption(
    "Une loi est « acceptée » si aucun test ne la rejette au seuil choisi (p-valeur supérieure au seuil). "
    "La p-valeur de Kolmogorov-Smirnov est un peu trop favorable car les paramètres sont estimés sur les mêmes données. "
    "L'AIC sert à comparer les lois : plus il est petit, mieux la loi décrit les données (à complexité égale)."
)

reco, accepte = meilleure_loi(ajustements)
if accepte:
    st.success(f"Loi conseillée : **{NOMS_LOIS[reco]}** (adéquation acceptée, plus petit AIC parmi les lois acceptées).")
else:
    st.warning(
        f"Aucune loi n'est acceptée au seuil de {alpha:.0%}. La plus proche est **{NOMS_LOIS[reco]}** (plus petit AIC), "
        "mais ses résultats sont à prendre avec beaucoup de réserve : vérifier les données (page 2)."
    )
aic_tries = sorted(a.aic for a in ajustements.values())
if len(aic_tries) >= 2 and aic_tries[1] - aic_tries[0] < 2:
    st.info("Les lois ont des AIC très proches (écart inférieur à 2) : les données ne permettent pas de les départager. Comparer leurs quantiles ci-dessous.")

options = list(ajustements)
precedente = st.session_state.get("loi_retenue")
loi_ret = st.selectbox(
    "Loi retenue pour la suite des calculs",
    options,
    index=options.index(precedente) if precedente in options else options.index(reco),
    format_func=lambda k: NOMS_LOIS[k],
)

# ---------------------------------------------------------------- quantiles
st.header("Quantiles de pluie maximale annuelle")
affichage = quantiles.round(1)
affichage["Écart entre lois (%)"] = ((quantiles.max(axis=1) - quantiles.min(axis=1)) / quantiles.mean(axis=1) * 100).round(0)
st.dataframe(affichage, width="stretch")
st.caption("Pluie en mm. La dernière colonne mesure l'écart entre la loi la plus haute et la plus basse : c'est une première idée de l'incertitude du choix de la loi.")

message = avertissement_extrapolation(len(x), max(periodes))
if message:
    st.warning(message)

# ---------------------------------------------------------------- graphique
fig, ax = plt.subplots(figsize=(9, 5))
emp = positions_empiriques(x)
ax.scatter(emp["variable_reduite_gumbel"], emp["valeur"], color="black", s=22, zorder=3, label="Observations (Weibull)")
t_max = max(max(periodes), 100)
t_grille = np.logspace(np.log10(1.05), np.log10(t_max), 200)
u = lambda t: -np.log(-np.log(1 - 1 / np.asarray(t, dtype=float)))
for cle, a in ajustements.items():
    ax.plot(u(t_grille), a.quantile(t_grille), linewidth=2.8 if cle == loi_ret else 1.3, label=a.nom)
repères = [t for t in (2, 5, 10, 20, 50, 100, 200, 500, 1000) if t <= t_max]
ax.set_xticks(u(repères))
ax.set_xticklabels([str(t) for t in repères])
ax.set_xlabel("Période de retour (ans), échelle de Gumbel")
ax.set_ylabel("Pluie maximale annuelle (mm)")
ax.set_title("Ajustement des lois aux maxima annuels")
ax.grid(alpha=0.3)
ax.legend()
st.pyplot(fig)
plt.close(fig)

# ---------------------------------------------------------------- calculette
with st.expander("Calculette : pluie pour une période de retour, ou l'inverse"):
    k1, k2 = st.columns(2)
    t_saisie = k1.number_input("Période de retour (ans)", min_value=1.01, value=50.0, step=5.0)
    k1.metric(f"Pluie de période de retour {t_saisie:g} ans ({NOMS_LOIS[loi_ret]})", f"{ajustements[loi_ret].quantile(t_saisie):.1f} mm")
    p_saisie = k2.number_input("Pluie (mm)", min_value=1.0, value=float(round(np.median(x))), step=5.0)
    k2.metric("Période de retour correspondante", f"{ajustements[loi_ret].periode_retour(p_saisie):.1f} ans")

# ---------------------------------------------------------------- hypothèses
st.subheader("Hypothèses des lois")
for cle in ajustements:
    with st.expander(NOMS_LOIS[cle], expanded=(cle == loi_ret)):
        st.write(HYPOTHESES_STAT[cle])
        st.write("Paramètres : " + ", ".join(f"{k} = {v:.3f}" for k, v in ajustements[cle].parametres.items()))

# Résultats conservés pour les pages suivantes.
st.session_state["ajustement"] = ajustements[loi_ret]
st.session_state["ajustements"] = ajustements
st.session_state["loi_retenue"] = loi_ret
st.session_state["quantiles"] = quantiles
st.session_state["periodes_retour"] = periodes
