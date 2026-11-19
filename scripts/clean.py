# Nettoie les fichiers bruts de data/raw/ et produit 3 tableaux propres dans data/clean/ :
#   - volumes.csv : volumes mensuels (EVP) de Los Angeles et Long Beach, depuis janvier 2019
#   - cppi.csv    : score et rang CPPI des 6 ports, 2 éditions
#   - unctad.csv  : escales et temps médian au port des porte-conteneurs, par pays, 2019-2023
# Les fichiers bruts ne sont jamais modifiés.

import glob
import re

import pandas as pd

DEBUT = "2019-01-01"
MOIS = ["January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December"]


def en_nombre(serie):
    """Convertit un texte comme '429,922.75' en nombre. Ce qui est illisible devient vide (NaN)."""
    return pd.to_numeric(serie.astype(str).str.replace(",", "", regex=False), errors="coerce")


# ---------------------------------------------------------------- 1. Los Angeles
morceaux = []
for fichier in sorted(glob.glob("data/raw/pola_*.csv")):
    annee = int(re.search(r"pola_(\d{4})", fichier).group(1))
    brut = pd.read_csv(fichier, skiprows=1, dtype=str)      # la 1re ligne ne contient que 0,1,2...
    brut = brut.rename(columns={brut.columns[0]: "mois"})
    brut = brut[brut["mois"].isin(MOIS)]                     # on enlève les lignes de totaux
    morceaux.append(pd.DataFrame({
        "date": pd.to_datetime(brut["mois"] + f" {annee}", format="%B %Y"),
        "port": "Los Angeles",
        "imports": en_nombre(brut["Loaded Imports"]),
        "exports": en_nombre(brut["Loaded Exports"]),
        "vides": en_nombre(brut["Empty Imports"]) + en_nombre(brut["Empty Exports"]),
        "total_publie": en_nombre(brut["Total TEUs"]),
    }))
la = pd.concat(morceaux)

# ---------------------------------------------------------------- 2. Long Beach
brut = pd.read_csv("data/raw/polb_archive.csv", thousands=",")
brut["date"] = pd.to_datetime(brut["Date"], format="%b %Y", errors="coerce")   # "Jan-Jul 1987" -> vide
lb = pd.DataFrame({
    "date": brut["date"],
    "port": "Long Beach",
    "imports": brut["Loaded Inbound"],
    "exports": brut["Loaded Outbound"],
    # On garde le total des vides publié : en nov. 2020, Empty Inbound + Empty Outbound
    # ne correspond pas au total publié, alors que le total du mois (783 523) est confirmé par le port.
    "vides": brut["Total Empties"],
    "total_publie": brut["Total"],
})

# ---------------------------------------------------------------- 3. Volumes réunis
vol = pd.concat([la, lb])
vol = vol[(vol["date"] >= DEBUT) & vol["imports"].notna()]          # depuis 2019, mois publiés seulement
vol["total"] = vol["imports"] + vol["exports"] + vol["vides"]        # total recalculé
vol["ecart_total"] = (vol["total"] - vol["total_publie"]).round(0)   # contrôle avec le total publié

# Si le total publié est illisible (ex. LA nov. 2020 : "889.,748.15"), on garde le total recalculé.
anomalies = vol[vol["total_publie"].isna() | (vol["ecart_total"].abs() > 1)]
for col in ["imports", "exports", "vides", "total"]:
    vol[col] = vol[col].round(0).astype(int)
vol = vol.drop(columns=["total_publie", "ecart_total"]).sort_values(["port", "date"])
vol.to_csv("data/clean/volumes.csv", index=False)

# ---------------------------------------------------------------- 4. CPPI
cppi = pd.read_csv("data/raw/cppi_manuel.csv", sep=";")
cppi = cppi[["edition", "annee_donnees", "port", "pays", "score", "rang", "nb_ports_classes"]]
cppi.to_csv("data/clean/cppi.csv", index=False)

# ---------------------------------------------------------------- 5. CNUCED
PAYS = {"World": "Monde", "United States of America": "États-Unis", "China": "Chine",
        "Korea, Republic of": "Corée du Sud", "Netherlands (Kingdom of the)": "Pays-Bas",
        "Singapore": "Singapour", "Djibouti": "Djibouti"}

# 5a. Temps médian au port : un fichier par année, l'année est écrite dans le fichier metadata
# recursive=True : on cherche aussi dans les sous-dossiers de data/raw/ (un dossier par ZIP, par exemple)
fichiers_temps = sorted(glob.glob("data/raw/**/US.PortCalls_*.csv", recursive=True))
fichiers_escales = sorted(glob.glob("data/raw/**/US.PortCallsArrivals_*.csv", recursive=True))
if not fichiers_temps or not fichiers_escales:
    print("Fichiers CNUCED introuvables dans data/raw/ (ou ses sous-dossiers).")
    print("  temps au port (US.PortCalls_*.csv) :", len(fichiers_temps), "fichier(s)")
    print("  escales (US.PortCallsArrivals_*.csv) :", len(fichiers_escales), "fichier(s)")
    print("Vérifie que les ZIP sont bien dézippés (CSV + _metadata.txt).")
    raise SystemExit(1)

temps = []
for fichier in fichiers_temps:
    if fichier.endswith("_metadata.csv"):
        continue
    with open(fichier.replace(".csv", "_metadata.txt"), encoding="utf-8") as f:
        annee = int(re.search(r"Year:\s*(\d{4})", f.read()).group(1))
    d = pd.read_csv(fichier)
    d = d[d["CommercialMarket_Label"] == "Container ships"]
    temps.append(pd.DataFrame({"pays": d["Economy_Label"], "annee": annee,
                               "temps_median_jours": d["Median_time_in_port_days_Value"]}))
temps = pd.concat(temps).drop_duplicates(["pays", "annee"])   # un éventuel doublon (« Copie ») est ignoré

# 5b. Nombre d'escales : un seul fichier, les années sont en colonnes
fichier = fichiers_escales[0]
d = pd.read_csv(fichier)
cols = {c: int(c[:4]) for c in d.columns if c.endswith("_Number_of_port_calls_Value")}
escales = d[["Economy_Label", *cols]].melt(id_vars="Economy_Label", var_name="col", value_name="escales")
escales["annee"] = escales["col"].map(cols)
escales = escales.rename(columns={"Economy_Label": "pays"}).drop(columns="col")

unctad = temps.merge(escales, on=["pays", "annee"], how="outer")
unctad = unctad[unctad["pays"].isin(PAYS)]                    # on retire les régions (Afrique, Asie...)
unctad["pays"] = unctad["pays"].map(PAYS)
unctad["escales"] = unctad["escales"].round(0).astype("Int64")   # nombre entier (vide si non publié)
unctad = unctad.sort_values(["pays", "annee"])
unctad.to_csv("data/clean/unctad.csv", index=False)

# ---------------------------------------------------------------- Résumé
print("volumes.csv :", len(vol), "lignes |", vol["date"].min().date(), "->", vol["date"].max().date())
print(vol.groupby("port")["date"].agg(["count", "min", "max"]))
print("\nContrôle des totaux (écart entre total recalculé et total publié) :")
print(anomalies[["date", "port", "total", "total_publie", "ecart_total"]].to_string(index=False)
      if len(anomalies) else "  aucun écart")
print("\ncppi.csv :", len(cppi), "lignes")
print("\nunctad.csv :", len(unctad), "lignes")
print(unctad.pivot(index="pays", columns="annee", values="temps_median_jours"))