"""Rapport de synthèse : export Word (.docx), tableaux Excel (.xlsx) et graphiques (.png dans un zip).

Toutes les fonctions reçoivent `etat`, un dictionnaire contenant les résultats des étapes
(en pratique le contenu de st.session_state). Une étape non réalisée est signalée dans le
rapport au lieu de provoquer une erreur : on peut donc exporter un rapport partiel.
"""
from __future__ import annotations

import datetime
import io
import zipfile

import numpy as np
import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .bassin import METHODES_TC, tc_toutes_methodes
from .debit import HYPOTHESES_DEBIT
from .graphiques import en_png, toutes_les_figures
from .hydrogramme import HYPOTHESES_HYDROGRAMME
from .idf import HYPOTHESES_IDF
from .statistique import HYPOTHESES_STAT

BLEU = "1F4E79"
GRIS_CLAIR = "EAF1F8"
CLE_DUREE_HYDROGRAMME = "Durée de l'hydrogramme (h)"  # clé produite par calculs.hydrogramme.proprietes
LARGEUR_TEXTE_CM = 16.0


# ----------------------------------------------------------------------------
# Mise en forme des nombres et du document
# ----------------------------------------------------------------------------
def _n(valeur, decimales: int = 1) -> str:
    """Nombre au format français : 1 234,5. Un tiret pour une valeur absente."""
    if valeur is None or (isinstance(valeur, float) and np.isnan(valeur)):
        return "—"
    return f"{valeur:,.{decimales}f}".replace(",", "\u202f").replace(".", ",")


def _ombrage(cellule, couleur: str) -> None:
    propr = cellule._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")  # « clear » : une teinte pleine « solid » s'afficherait en noir
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), couleur)
    propr.append(shd)


def _repeter_entete(ligne) -> None:
    propr = ligne._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    propr.append(el)


def _champ_numero_de_page(paragraphe) -> None:
    run = paragraphe.add_run()
    debut = OxmlElement("w:fldChar")
    debut.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = "PAGE"
    fin = OxmlElement("w:fldChar")
    fin.set(qn("w:fldCharType"), "end")
    for el in (debut, instruction, fin):
        run._r.append(el)


class _Rapport:
    """Petit utilitaire qui regroupe la mise en forme du document Word."""

    def __init__(self) -> None:
        self.doc = Document()
        self.n_figure = 0
        self.n_tableau = 0
        self._styles()
        self._page()

    def _styles(self) -> None:
        normal = self.doc.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(11)
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.line_spacing = 1.1
        for nom, taille, avant, apres in (("Heading 1", 16, 18, 6), ("Heading 2", 13, 12, 4), ("Title", 24, 0, 6)):
            s = self.doc.styles[nom]
            s.font.name = "Calibri"
            s.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
            s.element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
            s.element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
            s.font.size = Pt(taille)
            s.font.bold = True
            s.font.color.rgb = RGBColor.from_string(BLEU)
            s.paragraph_format.space_before = Pt(avant)
            s.paragraph_format.space_after = Pt(apres)
            s.paragraph_format.keep_with_next = True

    def _page(self) -> None:
        section = self.doc.sections[0]
        section.page_width, section.page_height = Cm(21.0), Cm(29.7)  # A4
        section.left_margin = section.right_margin = Cm(2.5)
        section.top_margin = section.bottom_margin = Cm(2.2)
        pied = section.footer.paragraphs[0]
        pied.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _champ_numero_de_page(pied)

    # -- texte ---------------------------------------------------------------
    def titre1(self, texte: str) -> None:
        self.doc.add_heading(texte, level=1)

    def titre2(self, texte: str) -> None:
        self.doc.add_heading(texte, level=2)

    def para(self, texte: str, gras: bool = False, italique: bool = False, couleur: str | None = None, taille: float | None = None):
        p = self.doc.add_paragraph()
        r = p.add_run(texte)
        r.bold, r.italic = gras, italique
        if couleur:
            r.font.color.rgb = RGBColor.from_string(couleur)
        if taille:
            r.font.size = Pt(taille)
        return p

    def puces(self, textes) -> None:
        for t in textes:
            self.doc.add_paragraph(t, style="List Bullet")

    # -- tableaux ------------------------------------------------------------
    def tableau(self, entetes: list[str], lignes: list[list[str]], largeurs_cm: list[float], legende: str | None = None) -> None:
        if legende:
            self.n_tableau += 1
            p = self.para(f"Tableau {self.n_tableau} : {legende}", gras=True, taille=10)
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_after = Pt(3)
        total = sum(largeurs_cm)
        largeurs = [w * LARGEUR_TEXTE_CM / total for w in largeurs_cm] if total > LARGEUR_TEXTE_CM else largeurs_cm
        t = self.doc.add_table(rows=1, cols=len(entetes))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        for i, texte in enumerate(entetes):
            c = t.rows[0].cells[i]
            c.width = Cm(largeurs[i])
            _ombrage(c, BLEU)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(texte)
            r.bold, r.font.size, r.font.color.rgb = True, Pt(9.5), RGBColor(255, 255, 255)
        _repeter_entete(t.rows[0])
        for k, ligne in enumerate(lignes):
            cellules = t.add_row().cells
            for i, texte in enumerate(ligne):
                cellules[i].width = Cm(largeurs[i])
                if k % 2 == 1:
                    _ombrage(cellules[i], GRIS_CLAIR)
                p = cellules[i].paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if i == 0 else WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_after = Pt(0)
                p.add_run(str(texte)).font.size = Pt(9.5)
        # Tableau d'un seul tenant : aucune ligne coupée, et chaque ligne reste liée à la suivante.
        for k, ligne in enumerate(t.rows):
            trpr = ligne._tr.get_or_add_trPr()
            trpr.append(OxmlElement("w:cantSplit"))
            if k < len(t.rows) - 1:
                for cellule in ligne.cells:
                    for p in cellule.paragraphs:
                        p.paragraph_format.keep_with_next = True
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    # -- figures -------------------------------------------------------------
    def figure(self, fig, legende: str) -> None:
        self.n_figure += 1
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(io.BytesIO(en_png(fig)), width=Cm(15.5))
        c = self.para(f"Figure {self.n_figure} : {legende}", italique=True, taille=10)
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def octets(self) -> bytes:
        tampon = io.BytesIO()
        self.doc.save(tampon)
        return tampon.getvalue()


# ----------------------------------------------------------------------------
# Rapport Word
# ----------------------------------------------------------------------------
def _source_fictive(etat: dict) -> bool:
    return "fictif" in str(etat.get("source_donnees", "")).lower()


def _etape_absente(r: _Rapport, nom: str) -> None:
    r.para(f"Étape non réalisée : {nom}.", italique=True, couleur="C00000")


def construire_rapport_word(etat: dict, titre: str = "Rapport de synthèse hydrologique", auteurs: str = "", etablissement: str = "") -> bytes:
    """Construit le rapport de synthèse au format Word et renvoie le fichier (octets)."""
    r = _Rapport()
    bassin = etat.get("bassin")
    tc_h = etat.get("tc_h")

    # ---------------------------------------------------------------- page de titre
    r.doc.add_paragraph(titre, style="Title")
    if bassin:
        r.para(f"Bassin versant : {bassin.nom}", taille=14)
    if etablissement:
        r.para(etablissement)
    if auteurs:
        r.para(auteurs)
    r.para(f"Généré le {datetime.date.today().strftime('%d/%m/%Y')} par l'application de calcul hydrologique.", italique=True, taille=10)
    if _source_fictive(etat):
        r.para(
            "ATTENTION : ce rapport a été produit avec des données FICTIVES (fichier d'exemple). "
            "Les résultats n'ont aucune valeur hydrologique et ne doivent pas être utilisés.",
            gras=True,
            couleur="C00000",
        )

    # ---------------------------------------------------------------- synthèse
    r.titre1("1. Synthèse des résultats")
    synthese: list[list[str]] = []
    if bassin:
        synthese.append(["Surface du bassin", f"{_n(bassin.surface_km2, 2)} km²"])
    if tc_h:
        synthese.append(["Temps de concentration retenu", f"{_n(tc_h, 2)} h ({METHODES_TC.get(etat.get('tc_methode', ''), {}).get('nom', '?')})"])
    ajustement = etat.get("ajustement")
    if ajustement is not None:
        synthese.append(["Loi statistique retenue", f"{ajustement.nom} ({ajustement.n} maxima annuels)"])
    projet = etat.get("debit_projet")
    if projet:
        synthese.append(["Période de retour de projet", f"{_n(projet['T'], 0)} ans"])
        synthese.append(["Débit de pointe, méthode rationnelle", f"{_n(projet['Qp_rationnelle'], 1)} m³/s"])
        synthese.append(["Débit de pointe, méthode SCS-CN", f"{_n(projet['Qp_scs'], 1)} m³/s"])
        synthese.append(["Débit de projet retenu", f"{_n(projet['Qp'], 1)} m³/s ({projet['methode']})"])
    props, t_p = etat.get("hydro_proprietes"), etat.get("hydro_periode")
    if props and t_p in props:
        p = props[t_p]
        synthese.append([f"Hydrogramme ({etat.get('hydro_methode', '')}), T = {_n(t_p, 0)} ans", f"pointe {_n(p['Qp (m³/s)'], 1)} m³/s à {_n(p['Temps de pointe (h)'], 2)} h ; volume {_n(p['Volume écoulé (m³)'] / 1e6, 3)} Mm³"])
    if synthese:
        r.tableau(["Résultat", "Valeur"], synthese, [7.0, 9.0], "Résultats principaux")
    else:
        r.para("Aucun résultat disponible : réaliser d'abord les étapes de l'application.", italique=True)

    # ---------------------------------------------------------------- bassin
    r.titre1("2. Bassin versant")
    if not bassin:
        _etape_absente(r, "caractéristiques du bassin")
    else:
        lignes = [
            ["Nom", bassin.nom],
            ["Surface A", f"{_n(bassin.surface_km2, 2)} km²"],
            ["Longueur du plus long cheminement L", f"{_n(bassin.longueur_km, 2)} km"],
            ["Pente moyenne S", f"{_n(bassin.pente * 100, 2)} % ({_n(bassin.pente, 4)} m/m)"],
            ["Dénivelé H", f"{_n(bassin.denivele_m, 1)} m" if bassin.denivele_m else "non renseigné"],
        ]
        r.tableau(["Caractéristique", "Valeur"], lignes, [8.0, 8.0], "Caractéristiques physiques du bassin")
        if bassin.occupation_sol:
            r.tableau(
                ["Occupation du sol", "Part de la surface"],
                [[k, f"{_n(v * 100, 1)} %"] for k, v in bassin.occupation_sol.items()],
                [8.0, 8.0],
                "Occupation du sol",
            )
        r.titre2("Temps de concentration")
        resultats = tc_toutes_methodes(bassin)
        lignes = []
        for cle, infos in METHODES_TC.items():
            if cle in resultats:
                marque = " (retenu)" if cle == etat.get("tc_methode") else ""
                lignes.append([infos["nom"] + marque, _n(resultats[cle], 2), _n(resultats[cle] * 60, 0)])
            else:
                lignes.append([infos["nom"], "non calculé", "non calculé"])
        r.tableau(["Méthode", "tc (h)", "tc (min)"], lignes, [6.0, 5.0, 5.0], "Temps de concentration par méthode")
        if len(resultats) >= 2:
            r.para(f"Le rapport entre la plus grande et la plus petite valeur est de {_n(max(resultats.values()) / min(resultats.values()), 1)} : cet écart traduit l'incertitude liée au choix de la formule empirique.")

    # ---------------------------------------------------------------- pluies
    r.titre1("3. Données pluviométriques")
    maxima = etat.get("maxima")
    if maxima is None:
        _etape_absente(r, "import et contrôle des données de pluie")
    else:
        r.para(f"Source : {etat.get('source_donnees', 'non précisée')}. Série de {len(maxima)} maxima annuels, de {int(maxima.index.min())} à {int(maxima.index.max())}.")
        s = maxima.astype(float)
        lignes = [
            ["Nombre d'années", str(len(s))],
            ["Moyenne", f"{_n(s.mean(), 1)} mm"],
            ["Écart-type", f"{_n(s.std(ddof=1), 1)} mm"],
            ["Minimum / maximum", f"{_n(s.min(), 1)} / {_n(s.max(), 1)} mm"],
            ["Coefficient de variation", _n(s.std(ddof=1) / s.mean(), 2)],
            ["Coefficient d'asymétrie", _n(float(s.skew()), 2)],
        ]
        r.tableau(["Indicateur", "Valeur"], lignes, [8.0, 8.0], "Statistiques des maxima annuels")
        qualite = etat.get("rapport_qualite")
        if qualite:
            r.titre2("Contrôle de qualité")
            r.puces([texte for _, texte in qualite.messages])
        r.figure(toutes_les_figures({"maxima": maxima})["01_maxima_annuels"], "Maxima annuels de pluie retenus pour l'analyse")

    # ---------------------------------------------------------------- ajustement
    r.titre1("4. Ajustement statistique")
    ajustements = etat.get("ajustements")
    if not ajustements:
        _etape_absente(r, "ajustement statistique")
    else:
        lignes = []
        for a in ajustements.values():
            lignes.append(
                [
                    a.nom + (" (retenue)" if a.loi == etat.get("loi_retenue") else ""),
                    ", ".join(f"{k} = {_n(v, 2)}" for k, v in a.parametres.items()),
                    _n(a.ks_p, 3),
                    _n(a.chi2_p, 3) if a.chi2_p is not None else "—",
                    _n(a.aic, 1),
                    "acceptée" if a.accepte else "rejetée",
                ]
            )
        r.tableau(["Loi", "Paramètres", "p KS", "p χ²", "AIC", "Adéquation"], lignes, [3.2, 5.0, 1.8, 1.8, 1.8, 2.4], "Lois ajustées et tests d'adéquation")
        r.para(
            f"Le seuil de signification des tests est de {_n(next(iter(ajustements.values())).alpha * 100, 0)} %. "
            "La p-valeur de Kolmogorov-Smirnov est un peu trop favorable, car les paramètres sont estimés sur les mêmes données. "
            "L'AIC compare les lois entre elles : plus il est petit, mieux la loi décrit les données."
        )
        quantiles = etat.get("quantiles")
        if quantiles is not None:
            lignes = [[_n(float(t), 0)] + [_n(v, 1) for v in ligne] for t, ligne in zip(quantiles.index, quantiles.to_numpy())]
            r.tableau(["T (ans)"] + list(quantiles.columns), lignes, [3.0] + [4.0] * len(quantiles.columns), "Quantiles de pluie maximale annuelle (mm)")
        figs = toutes_les_figures({"maxima": maxima, "ajustements": ajustements, "loi_retenue": etat.get("loi_retenue"), "periodes_retour": etat.get("periodes_retour")}) if maxima is not None else {}
        if "02_ajustement_lois" in figs:
            r.figure(figs["02_ajustement_lois"], "Ajustement des lois aux maxima annuels (échelle de Gumbel)")

    # ---------------------------------------------------------------- IDF
    r.titre1("5. Courbes Intensité-Durée-Fréquence")
    montana = etat.get("montana")
    if montana is None:
        _etape_absente(r, "courbes IDF")
    else:
        cle = etat.get("idf_methode", "journalier")
        if cle == "journalier":
            r.para(
                f"Les pluies de courte durée sont déduites de la pluie journalière maximale par la relation d'échelle P(t) = P24·(t/24)^(1-b), "
                f"avec b = {_n(etat.get('b_montana', float('nan')), 3)} et un facteur de correction jour-pluviométrique de {_n(etat.get('facteur_24h', 1.0), 2)}."
            )
        else:
            r.para("Une loi a été ajustée aux maxima annuels de chaque durée, puis les coefficients de Montana ont été obtenus par régression log-log.")
        r.para(HYPOTHESES_IDF.get(cle, ""), italique=True, taille=10)
        lignes = [[_n(m["Période de retour (ans)"], 0), _n(m["a (t en h)"], 2), _n(m["a (t en min)"], 2), _n(m["b"], 3), _n(m["R²"], 4)] for _, m in montana.iterrows()]
        r.tableau(["T (ans)", "a (t en h)", "a (t en min)", "b", "R²"], lignes, [3.0, 3.5, 3.5, 3.0, 3.0], "Coefficients de Montana, i = a·t^(-b), i en mm/h")
        if etat.get("idf_intensites") is not None:
            r.figure(toutes_les_figures({"montana": montana, "idf_intensites": etat["idf_intensites"], "tc_h": tc_h})["03_courbes_idf"], "Courbes IDF pour les périodes de retour étudiées")

    # ---------------------------------------------------------------- débits
    r.titre1("6. Débit de pointe")
    debits = etat.get("debits")
    if debits is None or not projet:
        _etape_absente(r, "calcul du débit de pointe")
    else:
        r.para(
            f"Coefficient de ruissellement C = {_n(projet['c'], 2)} (méthode rationnelle) ; CN = {_n(projet['cn'], 1)} (méthode SCS-CN). "
            f"La pluie de projet a une durée D = {_n(projet['duree_pluie_h'], 2)} h."
        )
        r.para("Ces coefficients proviennent de tables génériques de la littérature (Chow, ASCE, SCS TR-55), modifiables dans l'application : ils doivent être confrontés aux valeurs du contexte local.", italique=True, taille=10)
        lignes = [
            [_n(d["T (ans)"], 0), _n(d["i(tc) (mm/h)"], 1), _n(d["C utilisé"], 2), _n(d["Q rationnelle (m³/s)"], 1), _n(d["Pluie nette (mm)"], 1), _n(d["Tp (h)"], 2), _n(d["Q SCS-CN (m³/s)"], 1), _n(d["Rapport SCS / rationnelle"], 2)]
            for _, d in debits.iterrows()
        ]
        r.tableau(
            ["T (ans)", "i(tc) (mm/h)", "C", "Q rat. (m³/s)", "Pluie nette (mm)", "Tp (h)", "Q SCS (m³/s)", "SCS / rat."],
            lignes,
            [1.6, 2.1, 1.4, 2.2, 2.2, 1.6, 2.3, 1.9],
            "Débits de pointe par les deux méthodes",
        )
        r.figure(toutes_les_figures({"debits": debits})["04_debits_de_pointe"], "Débit de pointe en fonction de la période de retour")
        r.para(
            f"Débit de projet retenu : {_n(projet['Qp'], 1)} m³/s pour une période de retour de {_n(projet['T'], 0)} ans (méthode : {projet['methode']}). "
            "L'écart entre les deux méthodes donne une première idée de l'incertitude de l'estimation."
        )

    # ---------------------------------------------------------------- hydrogramme
    r.titre1("7. Hydrogramme de crue")
    hydros = etat.get("hydrogrammes")
    if not hydros or not props or t_p not in hydros:
        _etape_absente(r, "hydrogramme de crue")
    else:
        p = props[t_p]
        r.para(f"Méthode : hydrogramme unitaire {etat.get('hydro_methode', '')}. Période de retour détaillée : {_n(t_p, 0)} ans.")
        lignes = [
            ["Débit de pointe", f"{_n(p['Qp (m³/s)'], 1)} m³/s"],
            ["Temps de pointe", f"{_n(p['Temps de pointe (h)'], 2)} h"],
            ["Volume écoulé", f"{_n(p['Volume écoulé (m³)'], 0)} m³"],
            ["Volume de pluie nette", f"{_n(p['Volume de pluie nette (m³)'], 0)} m³"],
            ["Rapport des volumes", _n(p["Rapport des volumes"], 3)],
            ["Durée de l'hydrogramme", f"{_n(p[CLE_DUREE_HYDROGRAMME], 1)} h"],
        ]
        r.tableau(["Caractéristique", "Valeur"], lignes, [8.0, 8.0], "Caractéristiques de l'hydrogramme de projet")
        figs = toutes_les_figures({"hydrogrammes": hydros, "hydro_proprietes": props, "hydro_periode": t_p, "debits": debits, "duree_pluie_h": etat.get("duree_pluie_h"), "bassin": bassin, "hydro_methode": etat.get("hydro_methode", "")})
        if "05_hydrogramme" in figs:
            r.figure(figs["05_hydrogramme"], "Hydrogramme de crue et pluie nette")

    # ---------------------------------------------------------------- hypothèses
    r.titre1("8. Hypothèses et limites")
    r.puces(
        [
            f"Temps de concentration, {infos['nom']} : {infos['validite']}" for infos in METHODES_TC.values()
        ]
        + [f"Loi {nom} : {texte}" for nom, texte in (("de Gumbel", HYPOTHESES_STAT["gumbel"]), ("GEV", HYPOTHESES_STAT["gev"]), ("de Galton", HYPOTHESES_STAT["galton"]))]
        + [
            f"Méthode rationnelle : {HYPOTHESES_DEBIT['rationnelle']}",
            f"Méthode SCS-CN : {HYPOTHESES_DEBIT['scs']}",
            f"Hydrogramme SCS : {HYPOTHESES_HYDROGRAMME['scs']}",
            f"Hydrogramme de Nash : {HYPOTHESES_HYDROGRAMME['nash']}",
        ]
    )
    return r.octets()


# ----------------------------------------------------------------------------
# Excel et images
# ----------------------------------------------------------------------------
def tableaux_pour_excel(etat: dict) -> dict[str, pd.DataFrame]:
    """Tableaux de résultats disponibles (nom de feuille Excel -> DataFrame)."""
    feuilles: dict[str, pd.DataFrame] = {}
    bassin = etat.get("bassin")
    if bassin:
        lignes = [("Nom", bassin.nom), ("Surface (km²)", bassin.surface_km2), ("Longueur (km)", bassin.longueur_km), ("Pente (m/m)", bassin.pente)]
        if bassin.denivele_m:
            lignes.append(("Dénivelé (m)", bassin.denivele_m))
        if etat.get("tc_h"):
            lignes.append(("tc retenu (h)", etat["tc_h"]))
        for k, v in bassin.occupation_sol.items():
            lignes.append((f"Occupation : {k} (%)", v * 100))
        feuilles["Bassin"] = pd.DataFrame(lignes, columns=["Caractéristique", "Valeur"])
    maxima = etat.get("maxima")
    if maxima is not None:
        feuilles["Maxima annuels"] = pd.DataFrame({"Année": maxima.index.astype(int), "Maximum (mm)": maxima.to_numpy()})
    if etat.get("quantiles") is not None:
        feuilles["Quantiles"] = etat["quantiles"].reset_index()
    if etat.get("montana") is not None:
        feuilles["Montana"] = etat["montana"]
    if etat.get("idf_intensites") is not None:
        feuilles["Intensités IDF"] = etat["idf_intensites"].reset_index()
    if etat.get("debits") is not None:
        feuilles["Débits de pointe"] = etat["debits"]
    hydros = etat.get("hydrogrammes")
    if hydros:
        for t, h in hydros.items():
            feuilles[f"Hydrogramme T{t:g}"[:31]] = h
    return feuilles


def exporter_excel(etat: dict) -> bytes:
    """Classeur Excel (.xlsx) regroupant les tableaux de résultats, une feuille par tableau."""
    feuilles = tableaux_pour_excel(etat)
    if not feuilles:
        raise ValueError("Aucun résultat à exporter.")
    tampon = io.BytesIO()
    with pd.ExcelWriter(tampon, engine="openpyxl") as ecrivain:
        for nom, df in feuilles.items():
            df.to_excel(ecrivain, sheet_name=nom, index=False)
            ws = ecrivain.sheets[nom]
            for col in ws.columns:
                largeur = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(12, largeur + 2), 45)
    return tampon.getvalue()


def exporter_graphiques_zip(etat: dict) -> bytes:
    """Archive .zip contenant un fichier PNG par graphique disponible."""
    figures = toutes_les_figures(etat)
    if not figures:
        raise ValueError("Aucun graphique à exporter.")
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        for nom, fig in figures.items():
            z.writestr(f"{nom}.png", en_png(fig, dpi=200))
    return tampon.getvalue()
