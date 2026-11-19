# Essaie de télécharger directement la page des statistiques de Long Beach.
import io
import requests
import pandas as pd

URL = "https://polb.com/business/port-statistics/"
ENTETES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

reponse = requests.get(URL, headers=ENTETES, timeout=30)
print("Code de réponse :", reponse.status_code)   # 200 = OK, 403 = refusé
reponse.raise_for_status()

tableaux = pd.read_html(io.StringIO(reponse.text), match="Empties", displayed_only=False)
tableau = max(tableaux, key=len)
tableau.to_csv("data/raw/polb_archive.csv", index=False)
print("Tableau gardé :", tableau.shape[0], "lignes,", tableau.shape[1], "colonnes")
print(tableau.head(5))
print(tableau.tail(5))