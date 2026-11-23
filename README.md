# Calcul hydrologique et modélisation des crues d'un bassin versant

Application web qui estime le débit de crue de projet d'un bassin versant : de la série de pluies maximales annuelles jusqu'à l'hydrogramme de crue, avec comparaison de plusieurs méthodes pour mesurer l'incertitude.

Projet 2 du module d'applications numériques en hydraulique (hydrologie de surface, niveau 4).

> **Lien de l'application en ligne :** [à compléter]

## Fonctionnalités

L'application suit le chemin de l'eau en sept étapes, une page par étape :

| Étape | Page | Ce qu'elle fait |
|---|---|---|
| 1 | Bassin versant | Saisie des caractéristiques (surface, longueur, pente, occupation du sol) et temps de concentration par Kirpich, Giandotti ou Passini |
| 2 | Données de pluie | Import CSV ou Excel, contrôle de qualité (valeurs manquantes, aberrantes, années incomplètes) et extraction des maxima annuels |
| 3 | Ajustement | Lois de Gumbel, GEV et Galton, tests d'adéquation (Kolmogorov-Smirnov, chi², AIC) et quantiles par période de retour |
| 4 | Courbes IDF | Relation de Montana, à partir des pluies journalières (exposant b imposé) ou de pluies de courte durée |
| 5 | Débit de pointe | Méthode rationnelle et méthode SCS-CN, avec comparaison des résultats |
| 6 | Hydrogramme | Hydrogramme unitaire SCS (curviligne ou triangulaire) ou de Nash |
| 7 | Rapport et exports | Rapport de synthèse Word, tableaux Excel et graphiques PNG |

Chaque méthode rappelle ses hypothèses et son domaine de validité dans l'interface. Les résultats d'une étape alimentent la suivante.

## Installation locale

Prérequis : **Python 3.10 ou plus récent**.

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

L'application s'ouvre dans le navigateur à l'adresse `http://localhost:8501`.

Si la commande `streamlit` seule n'est pas reconnue (cas fréquent sous Windows), utiliser `python -m streamlit` comme ci-dessus.

## Utilisation

1. Suivre les pages dans l'ordre, depuis le menu de gauche.
2. Importer un fichier de pluies, ou utiliser les fichiers d'exemple du dossier `data/` pour essayer l'application.
3. Exporter les résultats depuis la page **Rapport et exports**.

Les résultats sont conservés pendant la session seulement : actualiser la page les efface.

### Formats de fichiers acceptés

- CSV, TXT ou Excel (`.xlsx`, première feuille). Séparateur et encodage détectés automatiquement.
- Nombres avec virgule ou point décimal. Les codes `-99`, `-999` et `-9999` sont lus comme des données absentes.
- Dates au format `JJ/MM/AAAA` ou `AAAA-MM-JJ`.
- Pluies journalières : une colonne de dates et une colonne de hauteurs de pluie en mm.
- Maxima annuels : une colonne d'années et une colonne de maxima en mm.
- Pluies de courte durée : une colonne par durée, nommée avec son unité (`15 min`, `1 h`, `24 h`).

> **Attention :** les fichiers `data/exemple_FICTIF_*.csv` contiennent des données **simulées** (avec quelques défauts volontaires pour montrer le contrôle de qualité). Ils servent uniquement à tester l'application et ne doivent jamais être présentés comme des résultats.

## Méthodes de calcul

| Étape | Méthode |
|---|---|
| Temps de concentration | Kirpich, Giandotti, Passini |
| Pluies extrêmes | Lois de Gumbel, GEV et Galton ; maximum de vraisemblance ou moments |
| Intensités | Relation de Montana `i = a · t^(-b)` |
| Débit de pointe | Rationnelle `Q = C · i · A / 3,6` ; SCS-CN avec pluie nette `(P − Ia)² / (P − Ia + S)` |
| Hydrogramme | Hydrogramme unitaire SCS (`Qp = 0,208 · A · Q / Tp`) ; cascade de Nash |

Les formules, leurs unités et leurs limites sont détaillées dans le document d'analyse et de conception.

## Structure du projet

```
projet_hydro/
├── app.py                 # point d'entrée : navigation et page d'accueil
├── interface.py           # style visuel, barre latérale d'avancement
├── requirements.txt       # bibliothèques nécessaires
├── .streamlit/
│   └── config.toml        # thème et réglages de l'interface
├── pages/                 # une page par étape
│   ├── 1_Bassin.py
│   ├── 2_Donnees_pluie.py
│   ├── 3_Ajustement.py
│   ├── 4_IDF.py
│   ├── 5_Debit_pointe.py
│   ├── 6_Hydrogramme.py
│   └── 7_Rapport.py
├── calculs/               # logique métier, sans Streamlit
│   ├── bassin.py          # caractéristiques et temps de concentration
│   ├── qualite.py         # import des fichiers, contrôle qualité
│   ├── statistique.py     # ajustement des lois, quantiles, tests
│   ├── idf.py             # relation de Montana, courbes IDF
│   ├── debit.py           # méthode rationnelle, SCS-CN
│   ├── hydrogramme.py     # hydrogramme unitaire SCS et Nash
│   ├── graphiques.py      # figures Matplotlib réutilisables
│   └── rapport.py         # export Word, Excel et images
├── data/                  # fichiers d'exemple fictifs
└── tests/                 # tests automatiques (pytest)
```

L'application est organisée en trois couches : le dossier `calculs/` ne contient aucun code d'interface et peut être testé seul ; `app.py`, `interface.py` et `pages/` appellent ces fonctions et affichent les résultats ; `.streamlit/` et `requirements.txt` fixent le thème et les dépendances.

## Tests

```bash
python -m pytest
```

Les tests vérifient chaque fonction de calcul (comparaison avec des calculs manuels, retrouver les paramètres de lois simulées, conservation du volume de l'hydrogramme), le rapport exporté et le chargement de chaque page.

## Déploiement

L'application est déployée sur [Streamlit Community Cloud](https://share.streamlit.io) à partir de ce dépôt :

1. Pousser le code sur GitHub.
2. Sur Streamlit Community Cloud, créer une application en choisissant le dépôt, la branche et le fichier principal `app.py`.
3. Dans les paramètres avancés, choisir une version de Python récente (3.12 ou 3.13) : le code nécessite Python 3.10 ou plus.

Chaque `git push` met l'application en ligne à jour automatiquement.

## Limites

- Les tables de coefficients C et CN sont **génériques** (Chow, ASCE, SCS TR-55, conditions américaines) et modifiables : pour une étude réelle, les remplacer par des valeurs du contexte local.
- Les formules du temps de concentration sont empiriques et calées sur d'autres régions : l'écart entre elles est affiché pour en mesurer l'incertitude.
- Avec des pluies journalières seulement, l'exposant b de Montana est imposé (valeur par défaut indicative).
- Les p-valeurs de Kolmogorov-Smirnov sont optimistes, et les quantiles de grande période de retour sont des extrapolations à partir d'une série courte.
- La pluie nette est supposée uniforme sur le bassin, et le bassin linéaire et invariant.

## Documentation

- Document d'analyse et de conception : [à compléter]
- Manuel d'utilisation : [à compléter]

## Auteurs

[À compléter : noms de l'équipe, filière, établissement, année]
