"""Figures Matplotlib de l'application, réutilisées par le rapport et l'export des images.

Les figures sont créées avec `matplotlib.figure.Figure` (sans pyplot) : aucun état global,
aucun problème de fenêtre ou de thread, et la mémoire est libérée dès que la figure n'est plus utilisée.
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from .idf import intensite
from .statistique import positions_empiriques


def _gumbel_u(t):
    return -np.log(-np.log(1 - 1 / np.asarray(t, dtype=float)))


def en_png(fig: Figure, dpi: int = 160) -> bytes:
    """Encode la figure en PNG (octets)."""
    tampon = io.BytesIO()
    fig.savefig(tampon, format="png", dpi=dpi, bbox_inches="tight")
    return tampon.getvalue()


def fig_maxima(serie: pd.Series) -> Figure:
    fig = Figure(figsize=(9, 4))
    ax = fig.subplots()
    ax.bar(serie.index.astype(int), serie.to_numpy(), color="tab:blue", width=0.8)
    ax.set_xlabel("Année")
    ax.set_ylabel("Pluie maximale annuelle (mm)")
    ax.set_title("Maxima annuels retenus")
    ax.grid(alpha=0.3, axis="y")
    return fig


def fig_ajustement(valeurs, ajustements: dict, loi_retenue: str, periodes) -> Figure:
    fig = Figure(figsize=(9, 5))
    ax = fig.subplots()
    emp = positions_empiriques(valeurs)
    ax.scatter(emp["variable_reduite_gumbel"], emp["valeur"], color="black", s=22, zorder=3, label="Observations (Weibull)")
    t_max = max(max(periodes), 100)
    t_grille = np.logspace(np.log10(1.05), np.log10(t_max), 200)
    for cle, a in ajustements.items():
        ax.plot(_gumbel_u(t_grille), a.quantile(t_grille), linewidth=2.8 if cle == loi_retenue else 1.3, label=a.nom)
    reperes = [t for t in (2, 5, 10, 20, 50, 100, 200, 500, 1000) if t <= t_max]
    ax.set_xticks(_gumbel_u(reperes))
    ax.set_xticklabels([str(t) for t in reperes])
    ax.set_xlabel("Période de retour (ans), échelle de Gumbel")
    ax.set_ylabel("Pluie maximale annuelle (mm)")
    ax.set_title("Ajustement des lois aux maxima annuels")
    ax.grid(alpha=0.3)
    ax.legend()
    return fig


def fig_idf(montana: pd.DataFrame, intensites: pd.DataFrame, tc_h: float | None = None) -> Figure:
    fig = Figure(figsize=(9, 5.2))
    ax = fig.subplots()
    durees = intensites.index.to_numpy(dtype=float)
    t_grille = np.geomspace(durees.min(), durees.max(), 100)
    for _, ligne in montana.iterrows():
        t_ret = ligne["Période de retour (ans)"]
        ax.plot(t_grille, intensite(ligne["a (t en h)"], ligne["b"], t_grille), label=f"T = {t_ret:g} ans")
        ax.scatter(durees, intensites[t_ret].to_numpy(), s=14, color="black", zorder=3)
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
    return fig


def fig_debits(debits: pd.DataFrame) -> Figure:
    fig = Figure(figsize=(9, 4.6))
    ax = fig.subplots()
    t = debits["T (ans)"]
    q_rat, q_scs = debits["Q rationnelle (m³/s)"], debits["Q SCS-CN (m³/s)"]
    ax.plot(t, q_rat, marker="o", label="Rationnelle")
    ax.plot(t, q_scs, marker="s", label="SCS-CN")
    ax.fill_between(t, np.minimum(q_rat, q_scs), np.maximum(q_rat, q_scs), alpha=0.15, label="Écart entre méthodes")
    ax.set_xscale("log")
    ax.set_xticks(t)
    ax.set_xticklabels([f"{v:g}" for v in t])
    ax.minorticks_off()
    ax.set_xlabel("Période de retour (ans)")
    ax.set_ylabel("Débit de pointe (m³/s)")
    ax.set_title("Débit de pointe en fonction de la période de retour")
    ax.grid(alpha=0.3)
    ax.legend()
    return fig


def fig_hydrogramme(hydros: dict, t_principale: float, proprietes_principale: dict, pluie_nette_mm: float, duree_pluie_h: float, titre: str) -> Figure:
    fig = Figure(figsize=(9.5, 5))
    ax = fig.subplots()
    for t, h in hydros.items():
        principal = t == t_principale
        ax.plot(h["Temps (h)"], h["Débit (m³/s)"], linewidth=2.6 if principal else 1.4, label=f"T = {t:g} ans")
        if principal and len(hydros) == 1:
            ax.fill_between(h["Temps (h)"], h["Débit (m³/s)"], alpha=0.15)
    tp, qp = proprietes_principale["Temps de pointe (h)"], proprietes_principale["Qp (m³/s)"]
    ax.plot(tp, qp, "ko", zorder=3)
    ax.annotate(f"{qp:.1f} m³/s", (tp, qp), xytext=(8, 4), textcoords="offset points")
    q_max = max(float(h["Débit (m³/s)"].max()) for h in hydros.values())
    ax.set_xlim(left=0)
    ax.set_ylim(0, 1.5 * q_max if q_max > 0 else 1.0)
    ax.set_xlabel("Temps depuis le début de la pluie nette (h)")
    ax.set_ylabel("Débit (m³/s)")
    ax.grid(alpha=0.3)
    ax2 = ax.twinx()
    ie = pluie_nette_mm / duree_pluie_h
    ax2.bar(0, ie, width=duree_pluie_h, align="edge", color="tab:blue", alpha=0.25, label="Pluie nette")
    ax2.set_ylim(max(ie * 3.3, 1e-6), 0)
    ax2.set_ylabel("Intensité de la pluie nette (mm/h)")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="center right")
    ax.set_title(titre)
    return fig


def toutes_les_figures(etat: dict) -> dict[str, Figure]:
    """Figures disponibles d'après l'état de la session (clés : nom de fichier sans extension)."""
    figures: dict[str, Figure] = {}
    maxima = etat.get("maxima")
    if maxima is not None:
        figures["01_maxima_annuels"] = fig_maxima(maxima)
        aj, loi, periodes = etat.get("ajustements"), etat.get("loi_retenue"), etat.get("periodes_retour")
        if aj and loi and periodes:
            figures["02_ajustement_lois"] = fig_ajustement(maxima.to_numpy(dtype=float), aj, loi, periodes)
    if etat.get("montana") is not None and etat.get("idf_intensites") is not None:
        figures["03_courbes_idf"] = fig_idf(etat["montana"], etat["idf_intensites"], etat.get("tc_h"))
    if etat.get("debits") is not None:
        figures["04_debits_de_pointe"] = fig_debits(etat["debits"])
    hydros, props, t_p = etat.get("hydrogrammes"), etat.get("hydro_proprietes"), etat.get("hydro_periode")
    debits, d = etat.get("debits"), etat.get("duree_pluie_h")
    if hydros and props and t_p in hydros and debits is not None and d:
        pn = float(debits.loc[debits["T (ans)"] == t_p, "Pluie nette (mm)"].iloc[0])
        bassin = etat.get("bassin")
        titre = f"Hydrogramme de crue ({etat.get('hydro_methode', '')})" + (f" : {bassin.nom}" if bassin else "")
        figures["05_hydrogramme"] = fig_hydrogramme(hydros, t_p, props[t_p], pn, d, titre)
    return figures
