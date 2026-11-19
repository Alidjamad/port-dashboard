# Écoute le flux AIS (aisstream.io) autour du port de San Pedro Bay pendant quelques minutes
# et enregistre la dernière position connue de chaque navire.
# Résultats : data/live/ais_snapshot.csv (navires) et data/live/ais_historique.csv (un résumé par relevé).
# La clé API est lue dans .streamlit/secrets.toml ou dans la variable d'environnement AISSTREAM_API_KEY.

import asyncio
import json
import os
import tomllib
from datetime import datetime, timezone

import pandas as pd
import websockets

URL = "wss://stream.aisstream.io/v0/stream"
DUREE_ECOUTE = 180  # secondes

# Zone autour du port : [[lat_min, lon_min], [lat_max, lon_max]]
ZONE = [[33.55, -118.40], [33.80, -118.05]]

STATUTS = {0: "En route", 1: "Au mouillage", 2: "Non manœuvrant", 3: "Manœuvre restreinte",
           5: "À quai", 7: "En pêche", 8: "En route (voile)"}


def lire_cle():
    """Lit la clé API sans jamais l'écrire dans le code."""
    if os.environ.get("AISSTREAM_API_KEY"):
        return os.environ["AISSTREAM_API_KEY"]
    with open(".streamlit/secrets.toml", "rb") as f:
        return tomllib.load(f)["AISSTREAM_API_KEY"]


def type_navire(code):
    """Traduit le code AIS du type de navire en catégorie lisible."""
    if code is None:
        return "Inconnu"
    if 70 <= code <= 79:
        return "Cargo / porte-conteneurs"
    if 80 <= code <= 89:
        return "Pétrolier"
    if 60 <= code <= 69:
        return "Passagers"
    if code in (31, 32, 52):
        return "Remorqueur"
    if code == 30:
        return "Pêche"
    if code == 50:
        return "Pilote"
    return "Autre"


async def ecouter(cle):
    navires = {}   # MMSI -> dernière position
    types = {}     # MMSI -> code du type de navire
    abonnement = {
        "APIKey": cle,
        "BoundingBoxes": [ZONE],
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }
    horloge = asyncio.get_event_loop()
    fin = horloge.time() + DUREE_ECOUTE
    connexions = 0
    # Tant que la durée d'écoute n'est pas écoulée, on (re)connecte si la connexion coupe
    while horloge.time() < fin and connexions < 10:
        connexions += 1
        try:
            # open_timeout=60 : on laisse 60 s pour ouvrir la connexion (serveur parfois lent)
            # ping_interval=None : pas de "ping" automatique (connexion trop lente pour y répondre à temps)
            async with websockets.connect(URL, open_timeout=60, ping_interval=None) as ws:
                await ws.send(json.dumps(abonnement))
                await lire_messages(ws, fin, horloge, navires, types)
        except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as coupure:
            # La connexion a coupé : on garde ce qu'on a déjà reçu et on se reconnecte
            print(f"Connexion {connexions} coupée ({coupure}) : reconnexion...")
    print(f"Écoute terminée après {connexions} connexion(s).")
    return navires, types


async def lire_messages(ws, fin, horloge, navires, types):
    """Lit les messages reçus jusqu'à la fin de la durée d'écoute."""
    while horloge.time() < fin:
        try:
            brut = await asyncio.wait_for(ws.recv(), timeout=30)
        except asyncio.TimeoutError:
            continue
        msg = json.loads(brut)
        meta = msg.get("MetaData", {})
        mmsi = meta.get("MMSI")
        if msg.get("MessageType") == "PositionReport":
            pos = msg["Message"]["PositionReport"]
            navires[mmsi] = {
                "mmsi": mmsi,
                "nom": (meta.get("ShipName") or "").strip(),
                "lat": meta.get("latitude"),
                "lon": meta.get("longitude"),
                "vitesse_noeuds": pos.get("Sog"),
                "statut_code": pos.get("NavigationalStatus"),
                "heure_message_utc": meta.get("time_utc"),
            }
        elif msg.get("MessageType") == "ShipStaticData":
            types[mmsi] = msg["Message"]["ShipStaticData"].get("Type")


def main():
    heure_releve = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"Écoute du flux AIS pendant {DUREE_ECOUTE} s...")
    try:
        navires, types = asyncio.run(ecouter(lire_cle()))
    except Exception as erreur:
        print("AIS indisponible :", erreur)   # l'ancien fichier reste en place
        raise SystemExit(1)

    df = pd.DataFrame(navires.values())
    if df.empty:
        print("Aucun navire reçu pendant l'écoute (couverture AIS faible ou zone vide).")
        raise SystemExit(1)

    df["type_code"] = df["mmsi"].map(types)
    df["type"] = df["type_code"].apply(lambda c: type_navire(None if pd.isna(c) else int(c)))
    df["statut"] = df["statut_code"].map(STATUTS).fillna("Non renseigné")
    df["releve_utc"] = heure_releve
    df.to_csv("data/live/ais_snapshot.csv", index=False)

    # Résumé du relevé, ajouté à l'historique (sert de référence pour l'indicateur 5)
    resume = pd.DataFrame([{
        "releve_utc": heure_releve,
        "nb_navires": len(df),
        "nb_au_mouillage": int((df["statut_code"] == 1).sum()),
        "nb_a_quai": int((df["statut_code"] == 5).sum()),
        "nb_en_route": int((df["statut_code"] == 0).sum()),
    }])
    fichier_hist = "data/live/ais_historique.csv"
    resume.to_csv(fichier_hist, mode="a", index=False, header=not os.path.exists(fichier_hist))

    print(f"{len(df)} navires reçus")
    print(resume.to_string(index=False))
    print("\nPar type :")
    print(df["type"].value_counts().to_string())
    print("\nExemple :")
    print(df[["nom", "type", "statut", "vitesse_noeuds", "lat", "lon"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()