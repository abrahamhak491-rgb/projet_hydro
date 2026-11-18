"""Page 7 : export du rapport de synthèse (Word), des tableaux (Excel) et des graphiques (PNG)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")

import pandas as pd
import streamlit as st

from calculs.rapport import construire_rapport_word, exporter_excel, exporter_graphiques_zip

st.set_page_config(page_title="Rapport", page_icon="📄", layout="wide")

st.title("7. Rapport et exports")
st.caption("Rassembler tous les résultats dans un rapport de synthèse Word, un classeur Excel et les graphiques en images.")

etat = {cle: st.session_state[cle] for cle in st.session_state.keys()}

# ---------------------------------------------------------------- avancement
etapes = [
    ("1. Bassin versant", etat.get("bassin") is not None and bool(etat.get("tc_h"))),
    ("2. Données de pluie", etat.get("maxima") is not None),
    ("3. Ajustement statistique", bool(etat.get("ajustements"))),
    ("4. Courbes IDF", etat.get("montana") is not None),
    ("5. Débit de pointe", etat.get("debits") is not None and bool(etat.get("debit_projet"))),
    ("6. Hydrogramme", bool(etat.get("hydrogrammes"))),
]
st.subheader("État d'avancement")
st.dataframe(
    pd.DataFrame({"Étape": [n for n, _ in etapes], "État": ["✅ réalisée" if ok else "⬜ à faire" for _, ok in etapes]}),
    hide_index=True,
    width="content",
)
n_faites = sum(ok for _, ok in etapes)
if n_faites == 0:
    st.warning("Aucun résultat à exporter. Commencer par la page **Bassin**.")
    st.stop()
if n_faites < len(etapes):
    st.info("Un rapport partiel peut être exporté : les étapes non réalisées y sont signalées.")

if "fictif" in str(etat.get("source_donnees", "")).lower():
    st.error("Les données de pluie sont **fictives** (fichier d'exemple) : le rapport portera un avertissement et ne doit pas être utilisé comme résultat.")

# ---------------------------------------------------------------- informations du rapport
st.subheader("Informations du rapport")
c1, c2, c3 = st.columns(3)
titre = c1.text_input("Titre", value="Rapport de synthèse hydrologique", key="rapport_titre")
auteurs = c2.text_input("Auteurs", value="", key="rapport_auteurs", placeholder="Noms des membres de l'équipe")
etablissement = c3.text_input("Établissement", value="", key="rapport_etablissement", placeholder="École, filière, année")

# ---------------------------------------------------------------- génération
st.subheader("Exports")
if st.button("Préparer les fichiers", type="primary"):
    with st.spinner("Génération du rapport, des tableaux et des graphiques..."):
        try:
            st.session_state["export_docx"] = construire_rapport_word(
                etat, titre.strip() or "Rapport de synthèse hydrologique", auteurs.strip(), etablissement.strip()
            )
        except Exception as erreur:
            st.error(f"Génération du rapport impossible : {erreur}")
            st.stop()
        # Excel et images sont indépendants : s'il n'y a rien à exporter, on l'indique sans bloquer le reste.
        for cle, fonction in (("export_xlsx", exporter_excel), ("export_zip", exporter_graphiques_zip)):
            try:
                st.session_state[cle] = fonction(etat)
            except ValueError:
                st.session_state[cle] = None

if "export_docx" in st.session_state:
    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "Rapport Word (.docx)",
        data=st.session_state["export_docx"],
        file_name="rapport_hydrologique.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    if st.session_state.get("export_xlsx"):
        d2.download_button(
            "Tableaux Excel (.xlsx)",
            data=st.session_state["export_xlsx"],
            file_name="resultats_hydrologiques.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        d2.caption("Aucun tableau à exporter pour l'instant.")
    if st.session_state.get("export_zip"):
        d3.download_button(
            "Graphiques (.zip de PNG)",
            data=st.session_state["export_zip"],
            file_name="graphiques_hydrologiques.zip",
            mime="application/zip",
        )
    else:
        d3.caption("Aucun graphique à exporter pour l'instant.")
    st.caption(
        "Les fichiers correspondent aux résultats au moment où vous avez cliqué sur « Préparer les fichiers » : "
        "refaire cette étape après toute modification. Pour obtenir un PDF, ouvrir le rapport dans Word et utiliser « Enregistrer sous »."
    )
else:
    st.caption("Cliquer sur « Préparer les fichiers » pour générer le rapport, les tableaux et les graphiques.")

with st.expander("Contenu du rapport"):
    st.markdown(
        """
1. Synthèse des résultats
2. Bassin versant : caractéristiques, occupation du sol, temps de concentration
3. Données pluviométriques : statistiques, contrôle de qualité, graphique
4. Ajustement statistique : tests d'adéquation, quantiles, graphique
5. Courbes IDF : coefficients de Montana, graphique
6. Débit de pointe : coefficients, méthodes rationnelle et SCS-CN, graphique
7. Hydrogramme de crue : caractéristiques, graphique
8. Hypothèses et domaines de validité de chaque méthode
"""
    )
