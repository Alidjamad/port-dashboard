# Télécharge les volumes mensuels (EVP) des grands ports américains
# publiés par le Bureau of Transportation Statistics (BTS).
# Utilisé pour Long Beach, car polb.com bloque l'accès depuis notre réseau.

import io
import requests
import pandas as pd

URL = "https://data.transportation.gov/api/views/rd72-aq8r/rows.csv?accessType=DOWNLOAD"

reponse = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
reponse.raise_for_status()

tableau = pd.read_csv(io.StringIO(reponse.text))
tableau.to_csv("data/raw/bts_monthly_teu.csv", index=False)

print("Taille :", tableau.shape[0], "lignes,", tableau.shape[1], "colonnes")
print("\nColonnes :", list(tableau.columns))
print("\nAperçu :")
print(tableau.head(10))