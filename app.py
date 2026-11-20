"""Point d'entrée de l'application : lancer avec  python -m streamlit run app.py"""
import streamlit as st

from interface import appliquer_style, barre_laterale, etapes_realisees

st.set_page_config(page_title="Hydrologie des crues", page_icon="🌊", layout="wide")
appliquer_style()

# Cartes de la page d'accueil : (icône, titre, clé de la page, étape suivie ou None, description).
CARTES = [
    ("⛰️", "Bassin versant", "bassin", "Bassin versant", "Surface, pente, occupation du sol et temps de concentration."),
    ("🌧️", "Données de pluie", "pluie", "Données de pluie", "Import du fichier, contrôle de qualité et maxima annuels."),
    ("📈", "Ajustement", "ajustement", "Ajustement", "Lois de Gumbel, GEV et Galton, tests d'adéquation et quantiles."),
    ("📉", "Courbes IDF", "idf", "Courbes IDF", "Courbes Intensité-Durée-Fréquence et coefficients de Montana."),
    ("💧", "Débit de pointe", "debit", "Débit de pointe", "Méthodes rationnelle et SCS-CN, avec comparaison des résultats."),
    ("🌊", "Hydrogramme", "hydrogramme", "Hydrogramme", "Hydrogramme unitaire SCS ou Nash pour la crue de projet."),
    ("📄", "Rapport et exports", "rapport", None, "Export Word, Excel et images de tous les résultats."),
]


def accueil() -> None:
    st.markdown(
        """
<div class="hero">
  <div class="hero-titre">Calcul hydrologique et modélisation des crues</div>
  <p class="hero-texte">Du relevé de pluies à l'hydrogramme de crue : estimer le débit de projet d'un bassin versant,
  comparer plusieurs méthodes et en mesurer l'incertitude.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    if "fictif" in str(st.session_state.get("source_donnees", "")).lower():
        st.warning("Les données de pluie actuelles sont **fictives** (fichier d'exemple) : les résultats n'ont aucune valeur hydrologique.")
    bassin = st.session_state.get("bassin")
    if bassin is not None:
        st.success(f"Bassin en cours : **{bassin.nom}** ({bassin.surface_km2:g} km²).")

    st.subheader("Déroulement")
    st.caption("Suivre les étapes dans l'ordre : chaque page réutilise les résultats de la précédente.")
    etat_des_etapes = dict(etapes_realisees(st.session_state))
    numerotees = list(enumerate(CARTES, start=1))
    for rangee in (numerotees[:4], numerotees[4:]):  # 4 cartes sur la première ligne, 3 sur la seconde
        for colonne, (numero, (icone, titre, cle, etape, description)) in zip(st.columns(4), rangee, strict=False):
            with colonne, st.container(border=True):
                st.markdown(f"#### {icone} {numero}. {titre}")
                st.caption(description)
                if etape is None:
                    st.markdown('<span class="etat-afaire">Export</span>', unsafe_allow_html=True)
                elif etat_des_etapes[etape]:
                    st.markdown('<span class="etat-ok">✔ Terminée</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="etat-afaire">À faire</span>', unsafe_allow_html=True)
                st.page_link(PAGES[cle], label="Ouvrir", icon=":material/arrow_forward:")

    st.page_link(PAGES["guide"], label="Première utilisation ? Ouvrir le manuel d'utilisation et l'exemple complet", icon=":material/menu_book:")

    st.subheader("À savoir avant de commencer")
    c1, c2, c3 = st.columns(3)
    c1.info("**Données** : fichier CSV ou Excel de pluies journalières ou de maxima annuels, avec une série d'au moins 20 à 30 ans.")
    c2.info("**Hypothèses** : chaque méthode rappelle ses hypothèses et son domaine de validité dans son volet « Hypothèses ».")
    c3.warning("**Coefficients** : les tables de C et de CN sont génériques et modifiables. À remplacer par les valeurs du cours ou du contexte local.")


PAGES = {
    "accueil": st.Page(accueil, title="Accueil", icon="🏠", default=True),
    "bassin": st.Page("pages/1_Bassin.py", title="Bassin versant", icon="⛰️"),
    "pluie": st.Page("pages/2_Donnees_pluie.py", title="Données de pluie", icon="🌧️"),
    "ajustement": st.Page("pages/3_Ajustement.py", title="Ajustement", icon="📈"),
    "idf": st.Page("pages/4_IDF.py", title="Courbes IDF", icon="📉"),
    "debit": st.Page("pages/5_Debit_pointe.py", title="Débit de pointe", icon="💧"),
    "hydrogramme": st.Page("pages/6_Hydrogramme.py", title="Hydrogramme", icon="🌊"),
    "rapport": st.Page("pages/7_Rapport.py", title="Rapport et exports", icon="📄"),
    "guide": st.Page("pages/8_Guide.py", title="Manuel d'utilisation", icon="📖"),
}

navigation = st.navigation(
    {
        "": [PAGES["accueil"]],
        "Bassin et données": [PAGES["bassin"], PAGES["pluie"]],
        "Analyse statistique": [PAGES["ajustement"], PAGES["idf"]],
        "Crue de projet": [PAGES["debit"], PAGES["hydrogramme"]],
        "Résultats": [PAGES["rapport"]],
        "Aide": [PAGES["guide"]],
    }
)
barre_laterale()
navigation.run()
