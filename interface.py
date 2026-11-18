"""Habillage de l'application : style visuel, barre latérale d'avancement, style des graphiques."""
import matplotlib
import streamlit as st

BLEU_FONCE = "#0B3C5D"
BLEU = "#0B6EA8"

CSS = f"""
<style>
.block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px; }}
#MainMenu, footer {{ visibility: hidden; }}

h1 {{ color: {BLEU_FONCE}; font-weight: 700; letter-spacing: -0.01em; }}
h2, h3 {{ color: #0B4F78; }}

[data-testid="stMetric"] {{
    background: #F5F9FD; border: 1px solid #D6E4F0; border-radius: 12px; padding: 12px 16px;
}}
[data-testid="stMetricLabel"] {{ color: #4A6478; }}

.stButton > button, .stDownloadButton > button {{ border-radius: 8px; font-weight: 600; }}
[data-testid="stSidebar"] {{ border-right: 1px solid #D6E4F0; }}
[data-testid="stExpander"] {{ border-radius: 10px; }}

.hero {{
    background: linear-gradient(135deg, {BLEU_FONCE} 0%, {BLEU} 100%);
    color: #FFFFFF; border-radius: 16px; padding: 28px 34px; margin-bottom: 1.4rem;
}}
.hero-titre {{ font-size: 2rem; font-weight: 700; line-height: 1.2; margin: 0 0 8px 0; }}
.hero-texte {{ font-size: 1.05rem; opacity: 0.92; margin: 0; }}

.etat-ok {{ color: #1E7B3A; font-weight: 600; font-size: 0.9rem; }}
.etat-afaire {{ color: #8A9BA8; font-size: 0.9rem; }}
</style>
"""

# Palette des graphiques : mêmes couleurs dans l'application et dans le rapport exporté.
STYLE_GRAPHIQUES = {
    "axes.prop_cycle": matplotlib.cycler(color=[BLEU, "#E07A1F", "#2A9D8F", "#8E44AD", "#C0392B", "#7F8C8D"]),
    "axes.spines.top": False,
    "axes.titleweight": "bold",
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "legend.frameon": False,
    "grid.color": "#D9E2EA",
}


def appliquer_style() -> None:
    """Injecte le style de l'application et celui des graphiques (à appeler à chaque exécution)."""
    st.markdown(CSS, unsafe_allow_html=True)
    matplotlib.rcParams.update(STYLE_GRAPHIQUES)


def etapes_realisees(etat) -> list[tuple[str, bool]]:
    """Les six étapes de calcul et leur état, d'après le contenu de st.session_state."""
    return [
        ("Bassin versant", etat.get("bassin") is not None and bool(etat.get("tc_h"))),
        ("Données de pluie", etat.get("maxima") is not None),
        ("Ajustement", bool(etat.get("ajustements"))),
        ("Courbes IDF", etat.get("montana") is not None),
        ("Débit de pointe", etat.get("debits") is not None and bool(etat.get("debit_projet"))),
        ("Hydrogramme", bool(etat.get("hydrogrammes"))),
    ]


def barre_laterale() -> None:
    """Avancement et bassin en cours, sous le menu de navigation."""
    etat = st.session_state
    etapes = etapes_realisees(etat)
    faites = sum(ok for _, ok in etapes)
    with st.sidebar:
        st.divider()
        st.markdown("**Avancement**")
        st.progress(faites / len(etapes), text=f"{faites} étape(s) sur {len(etapes)}")
        bassin = etat.get("bassin")
        if bassin is not None:
            st.caption(f"Bassin en cours : **{bassin.nom}** ({bassin.surface_km2:g} km²)")
        if "fictif" in str(etat.get("source_donnees", "")).lower():
            st.warning("Données de pluie fictives", icon="⚠️")
