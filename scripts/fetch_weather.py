# Récupère la météo à l'entrée du port de San Pedro Bay (Open-Meteo, sans clé API) :
# vent, rafales (nœuds) et vagues (m), maintenant + prévisions heure par heure sur 3 jours.
# Résultat : data/live/meteo.csv (prévisions) et data/live/meteo_actuelle.csv (maintenant).

from datetime import datetime, timezone
import requests
import pandas as pd

LAT, LON = 33.70, -118.25          # entrée du port, côté mer
FUSEAU = "America/Los_Angeles"      # heures locales du port

URL_VENT = "https://api.open-meteo.com/v1/forecast"
URL_VAGUES = "https://marine-api.open-meteo.com/v1/marine"

params_vent = {
    "latitude": LAT, "longitude": LON,
    "current": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
    "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
    "wind_speed_unit": "kn",        # en nœuds, l'unité des marins
    "forecast_days": 3,
    "timezone": FUSEAU,
}
params_vagues = {
    "latitude": LAT, "longitude": LON,
    "current": "wave_height",
    "hourly": "wave_height",
    "forecast_days": 3,
    "timezone": FUSEAU,
}

heure_appel = datetime.now(timezone.utc).isoformat(timespec="seconds")

try:
    vent = requests.get(URL_VENT, params=params_vent, timeout=30).json()
    vagues = requests.get(URL_VAGUES, params=params_vagues, timeout=30).json()
except Exception as erreur:
    # Message clair si la source est indisponible ; l'ancien fichier reste en place.
    print("Météo indisponible :", erreur)
    raise SystemExit(1)

# 1. Prévisions heure par heure : un tableau avec une ligne par heure
prev = pd.DataFrame(vent["hourly"]).merge(pd.DataFrame(vagues["hourly"]), on="time", how="left")
prev = prev.rename(columns={
    "time": "heure_locale",
    "wind_speed_10m": "vent_noeuds",
    "wind_gusts_10m": "rafales_noeuds",
    "wind_direction_10m": "direction_vent_deg",
    "wave_height": "vagues_m",
})
prev["recupere_le_utc"] = heure_appel
prev.to_csv("data/live/meteo.csv", index=False)

# 2. Conditions actuelles : une seule ligne
actuel = pd.DataFrame([{
    "heure_locale": vent["current"]["time"],
    "vent_noeuds": vent["current"]["wind_speed_10m"],
    "rafales_noeuds": vent["current"]["wind_gusts_10m"],
    "direction_vent_deg": vent["current"]["wind_direction_10m"],
    "vagues_m": vagues["current"]["wave_height"],
    "recupere_le_utc": heure_appel,
}])
actuel.to_csv("data/live/meteo_actuelle.csv", index=False)

print("Maintenant :")
print(actuel.to_string(index=False))
print(f"\nPrévisions : {len(prev)} heures enregistrées dans data/live/meteo.csv")
print("Rafale maximale prévue sur 48 h :", prev["rafales_noeuds"].head(48).max(), "nœuds")
print(prev.head(5).to_string(index=False))