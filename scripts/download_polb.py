# Récupère l'archive des volumes mensuels du Port of Long Beach.
# polb.com bloque l'accès direct ; le contenu est servi par thehelm.polb.com
# (WordPress). On essaie plusieurs adresses, directes puis Wayback Machine.

import io
import requests
import pandas as pd

ENTETES = {"User-Agent": "Mozilla/5.0"}

CANDIDATS = [
    # 1. Le tableau d'archive lui-même
    "https://thehelm.polb.com/stellar_custom_table/table100/",
    # 2. Le contenu brut de la page "Port Statistics" (format JSON)
    "https://thehelm.polb.com/wp-json/wp/v2/pages/896",
    # 3. La page Port Statistics sur thehelm
    "https://thehelm.polb.com/port-statistics/",
    # 4. Les mêmes, via la Wayback Machine
    "https://web.archive.org/web/2026id_/https://thehelm.polb.com/stellar_custom_table/table100/",
    "https://web.archive.org/web/2026id_/https://thehelm.polb.com/wp-json/wp/v2/pages/896",
    "https://web.archive.org/web/2026id_/https://thehelm.polb.com/port-statistics/",
]


def extraire_html(reponse):
    """Renvoie le HTML à analyser (si la réponse est du JSON WordPress, on prend le contenu)."""
    if "json" in reponse.headers.get("Content-Type", ""):
        return reponse.json()["content"]["rendered"]
    return reponse.text


trouve = None
for url in CANDIDATS:
    print("Essai :", url)
    try:
        reponse = requests.get(url, headers=ENTETES, timeout=60)
        reponse.raise_for_status()
        html = extraire_html(reponse)
        tableaux = pd.read_html(io.StringIO(html), match="Empties", displayed_only=False)
        tableau = max(tableaux, key=len)
        print(f"  -> OK : le plus grand tableau fait {tableau.shape[0]} lignes")
        print("  -> adresse réellement utilisée :", reponse.url)
        if tableau.shape[0] > 50:
            trouve = tableau
            break
    except Exception as erreur:
        print("  -> échec :", type(erreur).__name__, str(erreur)[:150])

if trouve is None:
    print("\nAucune adresse ne contient l'archive mensuelle.")
else:
    trouve.to_csv("data/raw/polb_archive.csv", index=False)
    print("\nEnregistré : data/raw/polb_archive.csv")
    print("Colonnes :", list(trouve.columns))
    print("\nDébut :")
    print(trouve.head(5))
    print("\nFin :")
    print(trouve.tail(5))