# Télécharge les volumes mensuels du Port of Los Angeles (2019 à 2026)
# et enregistre chaque année dans data/raw/ sans rien modifier.

import io
import requests
import pandas as pd

ANNEES = range(2019, 2027)
URL = "https://portoflosangeles.org/business/statistics/Container-Statistics/Historical-TEU-Statistics-{}"

for annee in ANNEES:
    adresse = URL.format(annee)  # le {} est remplacé par l'année
    reponse = requests.get(adresse, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    reponse.raise_for_status()

    # On ne garde que les tableaux qui contiennent le mot "January"
    tableaux = pd.read_html(io.StringIO(reponse.text), match="January")
    tableau = tableaux[0]

    fichier = f"data/raw/pola_{annee}.csv"
    tableau.to_csv(fichier, index=False)
    print(annee, "|", adresse)
    print("  ->", fichier, "|", tableau.shape[0], "lignes,", tableau.shape[1], "colonnes")
    print(tableau.head(3), "\n")