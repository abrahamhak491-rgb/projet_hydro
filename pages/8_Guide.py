"""Page 8 : manuel d'utilisation du logiciel, avec un exemple d'application complet."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Manuel d'utilisation", page_icon="📖", layout="wide")

st.title("Manuel d'utilisation")
st.caption("Comment utiliser l'application, étape par étape, avec un exemple complet de la saisie au rapport.")

onglets = st.tabs(["Prise en main", "Pas à pas", "Exemple complet", "Problèmes courants"])

# ======================================================================== 1. PRISE EN MAIN
with onglets[0]:
    st.header("À quoi sert l'application ?")
    st.write(
        "L'application estime le **débit de crue de projet** d'un bassin versant à partir de ses caractéristiques physiques "
        "et d'une série de pluies. Elle compare deux méthodes (rationnelle et SCS-CN), donne une idée de l'incertitude, "
        "construit l'**hydrogramme de crue** et exporte un rapport de synthèse."
    )

    st.subheader("Ce qu'il faut avoir avant de commencer")
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("**Le bassin versant**")
        st.markdown(
            "- Surface A (km²)\n"
            "- Longueur L du plus long cheminement hydraulique (km)\n"
            "- Pente moyenne S de ce cheminement (%)\n"
            "- Dénivelé H en mètres (facultatif, nécessaire seulement pour Giandotti)\n"
            "- Occupation du sol en pourcentages (facultatif, sert à calculer C et CN)"
        )
    with c2, st.container(border=True):
        st.markdown("**Les pluies**")
        st.markdown(
            "- Un fichier **CSV, TXT ou Excel (.xlsx)**, soit de pluies *journalières* (une ligne par jour), "
            "soit de *maxima annuels* (une ligne par année)\n"
            "- Une série d'au moins **20 à 30 ans** (minimum absolu : 5 valeurs)\n"
            "- Facultatif : un fichier de maxima annuels pour plusieurs durées (15 min, 1 h, 24 h…) "
            "pour des courbes IDF plus fiables"
        )

    st.subheader("Lancer l'application")
    st.code("pip install -r requirements.txt\npython -m streamlit run app.py", language="bash")
    st.caption("L'application s'ouvre dans le navigateur. Les données d'exemple sont dans le dossier « data ».")

    st.subheader("Se repérer dans l'interface")
    st.markdown(
        "- **Menu de gauche** : les pages sont regroupées par thème. L'ordre conseillé est celui des numéros 1 à 7.\n"
        "- **Avancement** (sous le menu) : barre indiquant combien d'étapes sur 6 sont terminées, et nom du bassin en cours.\n"
        "- **Accueil** : une carte par étape, avec son état (« Terminée » ou « À faire »).\n"
        "- **Messages colorés** : bleu = information, jaune = avertissement à lire, rouge = problème à corriger avant de continuer.\n"
        "- **Hypothèses et domaines de validité** : en bas de chaque page de calcul, dans des volets repliables."
    )

    st.subheader("Principe de fonctionnement")
    st.markdown(
        "Chaque page réutilise le résultat de la précédente :\n\n"
        "`Bassin` → `Données de pluie` → `Ajustement` → `IDF` → `Débit de pointe` → `Hydrogramme` → `Rapport`\n\n"
        "Si on revient en arrière pour changer une valeur, il faut **repasser par les pages suivantes** pour que leurs résultats soient mis à jour."
    )
    st.warning(
        "**Les résultats sont gardés en mémoire tant que l'onglet du navigateur reste ouvert.** "
        "Recharger la page (F5) ou fermer l'onglet efface tout : exporter le rapport avant de quitter."
    )

# ======================================================================== 2. PAS À PAS
with onglets[1]:
    st.header("Les sept étapes")

    with st.expander("1. Bassin versant", expanded=True):
        st.markdown(
            "**Ce qu'on fait** : décrire le bassin et choisir la formule du temps de concentration tc.\n\n"
            "1. Saisir le nom, la surface A, la longueur L et la pente S. **La pente se saisit en %** (1,5 pour 1,5 %).\n"
            "2. Pour utiliser Giandotti, cocher « Je connais le dénivelé H » et saisir H (altitude moyenne du bassin moins altitude de l'exutoire).\n"
            "3. Remplir le tableau d'occupation du sol (forêt, savane, culture, zone urbanisée, sol nu, plan d'eau). "
            "Le total doit faire 100 % (tolérance de 1 point). Sinon l'occupation est ignorée. Cette partie est facultative ici, "
            "mais elle permet de calculer C et CN automatiquement à l'étape 5.\n"
            "4. Lire le tableau et le graphique des trois méthodes (Kirpich, Giandotti, Passini), puis **choisir la méthode retenue**.\n\n"
            "**À savoir** : si la plus grande valeur de tc est au moins le double de la plus petite, un avertissement apparaît. "
            "Consulter alors les domaines de validité de chaque formule (volets en bas de page) avant de choisir."
        )

    with st.expander("2. Données de pluie"):
        st.markdown(
            "**Ce qu'on fait** : importer la série, la contrôler et en extraire les maxima annuels.\n\n"
            "1. Choisir « Importer mon fichier » (CSV, TXT ou Excel ; pour Excel, la **première feuille** est lue) "
            "ou le fichier d'exemple fictif.\n"
            "2. Indiquer le contenu : *pluies journalières* ou *maxima annuels*, puis choisir les colonnes "
            "(l'application propose celles dont le nom ressemble à « date », « pluie », « année », « max »…).\n"
            "3. Pour des pluies journalières : le format de date attendu est JJ/MM/AAAA (le format AAAA-MM-JJ est aussi reconnu). "
            "Les codes −99, −999 et −9999 sont traités comme valeurs manquantes ; le séparateur de colonnes et la virgule ou le point décimal sont reconnus automatiquement. "
            "Le curseur « Jours valides minimum » (200 à 365, 300 par défaut) décide quelles années sont jugées incomplètes ; "
            "ces années sont exclues si la case est cochée.\n"
            "4. Lire le **contrôle de qualité** : nombre de valeurs valides, manquantes, à vérifier, années absentes.\n\n"
            "**Valeurs « à vérifier »** : une valeur très éloignée des autres est signalée, **jamais supprimée automatiquement**. "
            "Cocher « Exclure ces valeurs » uniquement s'il s'agit d'une erreur (saisie, unité). "
            "Une vraie crue exceptionnelle doit être conservée.\n\n"
            "**Blocages** : moins de 5 valeurs exploitables, années en double, ou plus de 20 % de dates illisibles."
        )

    with st.expander("3. Ajustement statistique"):
        st.markdown(
            "**Ce qu'on fait** : ajuster les lois de Gumbel, GEV et Galton aux maxima annuels et lire les quantiles de pluie.\n\n"
            "1. Choisir l'estimation des paramètres (maximum de vraisemblance ou moments), le seuil de signification des tests "
            "(1, 5 ou 10 %) et les périodes de retour.\n"
            "2. Lire le **tableau des tests d'adéquation** (Kolmogorov-Smirnov, χ², AIC). Une loi est « acceptée » si aucun test ne la rejette. "
            "L'AIC sert à départager : plus il est petit, mieux c'est.\n"
            "3. L'application **conseille une loi** ; on peut en retenir une autre dans la liste « Loi retenue ».\n"
            "4. Lire le **tableau des quantiles** et la colonne « Écart entre lois (%) » : c'est une première mesure de l'incertitude liée au choix de la loi.\n"
            "5. La **calculette** donne la pluie pour une période de retour, ou l'inverse.\n\n"
            "**À savoir** : un avertissement d'extrapolation apparaît quand la plus grande période de retour demandée dépasse "
            "**deux fois la longueur de la série** (par exemple plus de 58 ans pour 29 années de données)."
        )

    with st.expander("4. Courbes IDF et coefficients de Montana"):
        st.markdown(
            "**Ce qu'on fait** : construire les courbes Intensité-Durée-Fréquence, de la forme i(t) = a · t^(−b), i en mm/h.\n\n"
            "Deux méthodes selon les données disponibles :\n\n"
            "- **Pluies journalières seulement** : les pluies de durée plus courte sont déduites de la pluie de 24 h avec un exposant b imposé. "
            "On saisit soit b directement, soit le rapport P(1 h)/P(24 h). La valeur par défaut b = 0,65 est **indicative** : "
            "la remplacer par la valeur du cours ou d'une étude régionale. Un facteur de correction journalière → 24 h est proposé (1,00 = aucune correction).\n"
            "- **Pluies de courte durée** : importer un fichier avec une colonne par durée, nommée par exemple « 15 min », « 1 h », « 24 h » "
            "(au moins 3 durées, avec au moins 5 valeurs chacune). La loi retenue à l'étape 3 est ajustée à chaque durée.\n\n"
            "**Résultats** : coefficients a et b pour chaque période de retour (a est donné pour t en heures *et* pour t en minutes : "
            "vérifier la convention du cours), R², courbes, tableaux d'intensités et de hauteurs de pluie, et **intensité de projet** à t = tc."
        )

    with st.expander("5. Débit de pointe"):
        st.markdown(
            "**Ce qu'on fait** : calculer le débit de pointe par la méthode rationnelle et par la méthode SCS-CN, puis retenir un débit de projet.\n\n"
            "1. Choisir l'origine de C et CN : *à partir de l'occupation du sol* (avec le groupe hydrologique du sol A à D) "
            "ou *saisie directe*. Les tables sont des **valeurs génériques de la littérature** : les modifier dans le tableau "
            "avec les valeurs du cours ou d'études locales.\n"
            "2. Choisir l'état d'humidité initiale du sol (I sec, II moyen, III humide). Le II est l'usage courant.\n"
            "3. Dans « Options de calcul » : majoration de C pour T ≥ 25 ans (si le cours le prévoit), rapport λ = Ia/S (0,20 par défaut), "
            "durée D de la pluie de projet (D = tc par défaut).\n"
            "4. Lire le **tableau comparatif** et le graphique : Q rationnelle, pluie nette, temps de pointe, Q SCS-CN, rapport entre les deux méthodes.\n"
            "5. **Choisir la période de retour de projet et la méthode retenue** (SCS-CN, rationnelle ou moyenne des deux).\n\n"
            "**À savoir** : si les deux méthodes diffèrent d'un facteur supérieur à 2, l'incertitude est grande. "
            "Si la pluie est inférieure à l'abstraction initiale, la méthode SCS donne un ruissellement nul : vérifier le CN. "
            "Au-delà de 50 km², la méthode rationnelle sort de son domaine habituel."
        )

    with st.expander("6. Hydrogramme de crue"):
        st.markdown(
            "**Ce qu'on fait** : tracer l'évolution du débit dans le temps pour la pluie de projet.\n\n"
            "1. Choisir la méthode : **SCS** (forme curviligne ou triangulaire) ou **Nash** (nombre de réservoirs n ; la constante K se déduit du temps de retard, ou se saisit à la main).\n"
            "2. Choisir le pas de temps (automatique par défaut) et les périodes de retour à comparer sur le graphique, "
            "puis celle à détailler dans le tableau et l'export.\n"
            "3. Lire les résultats : débit de pointe, temps de pointe, volume écoulé, durée de l'hydrogramme. "
            "Le **contrôle du volume** compare le volume écoulé au volume de pluie nette : l'écart doit rester inférieur à 2 %.\n"
            "4. Le bouton « Télécharger en CSV » fournit les ordonnées de l'hydrogramme (séparateur point-virgule, virgule décimale : "
            "s'ouvre directement dans Excel en français).\n\n"
            "**À savoir** : l'hydrogramme est construit à partir de la pluie nette de la méthode SCS-CN. "
            "Avec l'hydrogramme SCS, la pointe retrouve celle de l'étape 5 ; avec Nash elle diffère, car la forme change."
        )

    with st.expander("7. Rapport et exports"):
        st.markdown(
            "**Ce qu'on fait** : rassembler les résultats dans des fichiers.\n\n"
            "1. Vérifier le tableau d'avancement. Un rapport **partiel** est possible : les étapes non faites y sont signalées.\n"
            "2. Renseigner le titre, les auteurs et l'établissement.\n"
            "3. Cliquer sur **« Préparer les fichiers »**, puis télécharger :\n"
            "   - le **rapport Word** (.docx) : synthèse, bassin, pluies, ajustement, IDF, débits, hydrogramme, hypothèses ;\n"
            "   - les **tableaux Excel** (.xlsx) ;\n"
            "   - les **graphiques** en images PNG (dans un .zip).\n\n"
            "**À savoir** : les fichiers reflètent l'état au moment du clic. **Refaire « Préparer les fichiers » après toute modification.** "
            "Pour un PDF, ouvrir le rapport dans Word puis « Enregistrer sous ». "
            "Si les données sont fictives, le rapport porte un avertissement."
        )

# ======================================================================== 3. EXEMPLE COMPLET
with onglets[2]:
    st.header("Exemple complet : du fichier de pluies à l'hydrogramme")
    st.warning(
        "**Les données de cet exemple sont fictives** (fichier fourni dans le dossier « data »). "
        "Elles servent à apprendre à utiliser l'application : les résultats n'ont **aucune valeur hydrologique** "
        "et ne doivent pas figurer dans un rapport réel. Les chiffres ci-dessous sont obtenus avec les réglages par défaut ; "
        "modifier un réglage les change."
    )

    st.subheader("Étape 1 : le bassin")
    st.markdown(
        "Sur la page **Bassin versant**, saisir :"
    )
    st.dataframe(
        pd.DataFrame(
            {
                "Champ": ["Nom", "Surface A", "Longueur L", "Pente S", "Dénivelé H", "Occupation du sol"],
                "Valeur": [
                    "Bassin exemple",
                    "25 km²",
                    "9 km",
                    "1,5 %",
                    "120 m (case « Je connais le dénivelé H » cochée)",
                    "Forêt 20 %, Savane / prairie 30 %, Culture 40 %, Zone urbanisée 10 % (total 100 %)",
                ],
            }
        ),
        hide_index=True,
        width="stretch",
    )
    st.markdown("L'application calcule les trois temps de concentration :")
    st.dataframe(
        pd.DataFrame({"Méthode": ["Kirpich", "Giandotti", "Passini"], "tc (h)": [1.81, 3.82, 5.36], "tc (min)": [109, 229, 322]}),
        hide_index=True,
        width="content",
    )
    st.markdown(
        "Le rapport entre la plus grande et la plus petite valeur est d'environ 3 : l'avertissement apparaît. "
        "Ici on retient **Giandotti (tc = 3,82 h)**, car le dénivelé est connu et le bassin est de taille moyenne. "
        "Dans un vrai projet, ce choix se justifie avec les domaines de validité affichés en bas de page."
    )

    st.subheader("Étape 2 : les pluies")
    st.markdown(
        "Sur la page **Données de pluie** :\n\n"
        "1. Source : « Utiliser le fichier d'exemple (fictif) » (fichier de 10 776 lignes, colonnes `Date` et `Pluie_mm`).\n"
        "2. Contenu : « Pluies journalières ». Colonnes : `Date` et `Pluie_mm` (proposées automatiquement).\n"
        "3. Laisser le minimum à 300 jours et « Exclure les années incomplètes » coché.\n\n"
        "L'application signale ce qui suit, volontairement présent dans le fichier d'exemple :"
    )
    st.markdown(
        "- **6 valeurs manquantes** parmi les pluies journalières ;\n"
        "- **l'année 2003 est incomplète** (184 jours valides) : elle est exclue, d'où « Année absente de la série : 2003 » ;\n"
        "- **une valeur à vérifier : 312 mm en 2007**, hors de l'intervalle [−43,6 ; 214,0] mm. "
        "Dans un vrai cas, on chercherait l'origine de cette valeur (erreur de saisie ou vraie crue). "
        "Ici on **la conserve** (case « Exclure ces valeurs » non cochée)."
    )
    st.markdown("Il reste **29 maxima annuels** (1990 à 2019, sans 2003) :")
    st.dataframe(
        pd.DataFrame(
            {
                "Indicateur": ["Nombre d'années", "Moyenne", "Écart-type", "Minimum", "Maximum", "Coefficient de variation", "Asymétrie"],
                "Valeur": ["29", "90,7 mm", "49,6 mm", "47,3 mm", "312,0 mm", "0,55", "3,40"],
            }
        ),
        hide_index=True,
        width="content",
    )

    st.subheader("Étape 3 : l'ajustement statistique")
    st.markdown(
        "Sur la page **Ajustement** : maximum de vraisemblance, seuil de 5 %, périodes de retour par défaut (2, 5, 10, 20, 50 et 100 ans)."
    )
    st.dataframe(
        pd.DataFrame(
            {
                "Loi": ["Gumbel", "GEV", "Galton (log-normale)"],
                "p-valeur KS": [0.572, 0.998, 0.605],
                "p-valeur χ²": [0.468, 0.487, 0.279],
                "AIC": [287.0, 280.6, 286.5],
                "Verdict": ["acceptée", "acceptée", "acceptée"],
            }
        ),
        hide_index=True,
        width="content",
    )
    st.markdown(
        "Les trois lois sont acceptées. L'application conseille la **GEV** (AIC le plus petit, écart de plus de 5 points avec les deux autres). "
        "On la retient. Les quantiles montrent à quel point le choix de la loi compte pour les grandes périodes de retour :"
    )
    st.dataframe(
        pd.DataFrame(
            {
                "T (ans)": [2, 5, 10, 20, 50, 100],
                "Gumbel (mm)": [82.9, 110.6, 128.9, 146.4, 169.2, 186.2],
                "GEV (mm)": [77.3, 107.6, 135.2, 169.2, 227.7, 285.6],
                "Galton (mm)": [83.1, 114.4, 135.2, 155.2, 181.3, 201.0],
            }
        ),
        hide_index=True,
        width="content",
    )
    st.caption(
        "À T = 100 ans, la GEV donne 285,6 mm contre 186,2 mm pour Gumbel : c'est une incertitude à signaler dans le rapport. "
        "Elle vient surtout de la valeur de 312 mm : sans elle (28 valeurs), la GEV donnerait 181,0 mm à 100 ans. "
        "Une seule valeur peut donc changer fortement les grands quantiles, d'où l'importance du contrôle de l'étape 2."
    )
    st.markdown(
        "Comme la plus grande période de retour (100 ans) dépasse deux fois la longueur de la série (29 ans), "
        "l'application affiche aussi l'**avertissement d'extrapolation**."
    )

    st.subheader("Étape 4 : les courbes IDF")
    st.markdown(
        "Sur la page **Courbes IDF** : choisir « Pluies journalières seulement », « Je connais b » avec **b = 0,65**, "
        "facteur de correction 1,00, et les huit durées par défaut (15 min à 24 h)."
    )
    st.dataframe(
        pd.DataFrame(
            {
                "T (ans)": [2, 5, 10, 20, 50, 100],
                "P24 (mm)": [77.3, 107.6, 135.2, 169.2, 227.7, 285.6],
                "a (t en h)": [25.4, 35.4, 44.5, 55.6, 74.9, 93.9],
                "b": [0.65] * 6,
                "Intensité à t = tc (mm/h)": [10.6, 14.8, 18.6, 23.3, 31.3, 39.3],
            }
        ),
        hide_index=True,
        width="content",
    )
    st.caption(
        "Le R² vaut 1 car, avec la pluie journalière seule, les points suivent par construction la relation de Montana : ce n'est pas une preuve de qualité. "
        "Avec un vrai fichier de pluies de courte durée, le R² mesure réellement l'accord."
    )

    st.subheader("Étape 5 : les débits de pointe")
    st.markdown(
        "Sur la page **Débit de pointe** : « Calculer à partir de l'occupation du sol », groupe hydrologique **B**, humidité **II**, "
        "options par défaut (pas de majoration de C, λ = 0,20, D = tc). L'application trouve **C = 0,31** et **CN = 70,4**."
    )
    st.dataframe(
        pd.DataFrame(
            {
                "T (ans)": [2, 5, 10, 20, 50, 100],
                "Q rationnelle (m³/s)": [23.3, 32.4, 40.7, 50.9, 68.5, 85.9],
                "Pluie nette (mm)": [2.9, 8.7, 15.8, 26.2, 47.2, 70.4],
                "Q SCS-CN (m³/s)": [3.7, 10.8, 19.5, 32.4, 58.3, 87.1],
                "Rapport SCS / rationnelle": [0.16, 0.33, 0.48, 0.64, 0.85, 1.01],
            }
        ),
        hide_index=True,
        width="content",
    )
    st.markdown(
        "**Lecture** : pour les petites périodes de retour, la méthode SCS-CN donne beaucoup moins que la rationnelle "
        "(la pluie est en grande partie absorbée par le sol avant que le ruissellement ne commence), "
        "et l'application affiche l'avertissement « facteur supérieur à 2 ». Pour T = 50 et 100 ans, les deux méthodes se rapprochent. "
        "Ce type d'écart est exactement ce que l'application doit faire apparaître : il faut le discuter dans le rapport.\n\n"
        "On retient **T = 50 ans** et la méthode **SCS-CN** : débit de pointe **58,3 m³/s**, temps de pointe Tp = 4,2 h, pluie nette de 47,2 mm."
    )

    st.subheader("Étape 6 : l'hydrogramme")
    st.markdown("Sur la page **Hydrogramme** : méthode SCS, forme curviligne, pas de temps automatique, T = 50 ans.")
    st.dataframe(
        pd.DataFrame(
            {
                "Résultat": ["Débit de pointe", "Temps de pointe", "Volume écoulé", "Durée de l'hydrogramme", "Volume écoulé / volume de pluie nette"],
                "SCS curviligne": ["58,3 m³/s", "4,25 h", "1,181 Mm³", "21,5 h", "100,1 %"],
                "Nash (n = 3, K = 0,76 h)": ["76,8 m³/s", "4,25 h", "1,179 Mm³", "12,75 h", "100,0 %"],
            }
        ),
        hide_index=True,
        width="content",
    )
    st.markdown(
        "Avec SCS, la pointe retrouve celle de l'étape 5 et le volume est conservé (écart de 0,1 %). "
        "Avec Nash, l'hydrogramme est plus pointu et plus court : le débit de pointe est plus élevé pour le même volume. "
        "Cette différence de forme est une source d'incertitude supplémentaire à indiquer. "
        "Télécharger ensuite les ordonnées en CSV si besoin."
    )

    st.subheader("Étape 7 : le rapport")
    st.markdown(
        "Sur la page **Rapport et exports** : saisir un titre, les auteurs et l'établissement, cliquer sur « Préparer les fichiers », "
        "puis télécharger le rapport Word, le classeur Excel et le zip des graphiques. "
        "Comme les données d'exemple sont fictives, le rapport porte un avertissement."
    )

    st.info(
        "**Pour un vrai bassin** : refaire les mêmes étapes avec les caractéristiques mesurées du bassin et un fichier de pluies d'une station réelle "
        "(importé à l'étape 2). Remplacer b, les tables de C et de CN par les valeurs du cours ou d'études locales, "
        "et justifier chaque choix dans le rapport."
    )

# ======================================================================== 4. PROBLÈMES COURANTS
with onglets[3]:
    st.header("Messages fréquents et solutions")
    problemes = pd.DataFrame(
        [
            ("« Aucune donnée de pluie… » ou « Il manque des étapes… »", "On a ouvert une page sans avoir terminé les précédentes, ou la page du navigateur a été rechargée.", "Reprendre dans l'ordre, depuis la page indiquée dans le message."),
            ("« Plus de 20 % des dates sont illisibles »", "Mauvaise colonne de dates, ou format de date inattendu.", "Choisir la bonne colonne ; mettre les dates au format JJ/MM/AAAA."),
            ("« Lecture impossible » ou « Format non pris en charge »", "Fichier abîmé, vide, ou d'un autre format que .csv, .txt ou .xlsx.", "Enregistrer le fichier en CSV ou en .xlsx et vérifier qu'il s'ouvre dans Excel. Le séparateur de colonnes (virgule, point-virgule, tabulation) et la virgule ou le point décimal sont reconnus automatiquement."),
            ("« Année(s) en double »", "Une même année apparaît deux fois dans un fichier de maxima annuels.", "Supprimer ou fusionner les doublons dans le fichier."),
            ("« Moins de 5 valeurs exploitables »", "Série trop courte ou trop de valeurs manquantes.", "Compléter la série ; baisser le minimum de jours valides si c'est justifiable."),
            ("Giandotti n'est pas calculé", "Le dénivelé H n'est pas saisi.", "Cocher « Je connais le dénivelé H » et saisir la valeur."),
            ("« Il doit faire 100 % » (occupation du sol)", "Les parts ne totalisent pas 100 %.", "Corriger le tableau (tolérance : 1 point)."),
            ("« Aucune loi n'est acceptée »", "Série atypique, valeur erronée, ou série trop courte.", "Vérifier les données à l'étape 2 ; les résultats sont à prendre avec beaucoup de réserve."),
            ("« Il faut au moins 3 colonnes dont le nom est une durée »", "Le fichier de courte durée n'a pas des colonnes nommées « 15 min », « 1 h », « 24 h »…", "Renommer les colonnes avec la durée et son unité (min ou h)."),
            ("R² inférieur à 0,98 (IDF)", "Une seule relation de Montana représente mal les données.", "Vérifier les valeurs de courte durée ; signaler la limite dans le rapport."),
            ("Ruissellement nul pour les petites périodes de retour", "La pluie est inférieure à l'abstraction initiale de la méthode SCS.", "Vérifier le CN, le groupe de sol et λ ; ce résultat peut être normal pour de petites crues."),
            ("« Les deux méthodes diffèrent d'un facteur supérieur à 2 »", "C et CN ne sont pas cohérents, ou le bassin sort du domaine d'une méthode.", "Vérifier C, CN, le groupe de sol et les domaines de validité ; discuter l'écart dans le rapport."),
            ("Le rapport ne contient pas mes dernières modifications", "Les fichiers sont générés au clic sur « Préparer les fichiers ».", "Cliquer de nouveau sur « Préparer les fichiers » avant de télécharger."),
        ],
        columns=["Ce qu'on voit", "Cause probable", "Que faire"],
    )
    st.dataframe(problemes, hide_index=True, width="stretch")

    st.subheader("Limites à connaître")
    st.markdown(
        "- Les tables de **C** et de **CN** sont génériques (littérature, conditions américaines pour CN). Les adapter au contexte local.\n"
        "- L'exposant **b = 0,65** est une valeur indicative, pas une donnée du bassin.\n"
        "- La **méthode rationnelle** est conçue pour de petits bassins ; la méthode **SCS-CN** pour de petits bassins ruraux.\n"
        "- Les quantiles de grande période de retour tirés d'une série courte (moins de 30 ans) sont peu fiables.\n"
        "- Les données d'exemple sont **fictives** : ne jamais s'en servir comme résultat."
    )
