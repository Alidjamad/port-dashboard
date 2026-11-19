# Tableau de bord — Complexe portuaire de San Pedro Bay (Los Angeles + Long Beach)

**Tableau de bord en ligne : https://san-pedro-bay2.streamlit.app/**

Ce tableau de bord montre comment se porte le complexe portuaire de San Pedro Bay (ports de Los Angeles et de Long Beach) et comment il se situe face aux autres ports du monde, dont Djibouti.

- **Pour qui :** le responsable des opérations d'un transitaire qui fait passer des importations de conteneurs par San Pedro Bay.
- **Pour quelles décisions :**
  - **chaque mois**, fixer la taille de ses contrats de camions et d'entrepôts pour les 3 mois suivants ;
  - **chaque jour**, décider quand envoyer ses camions au port et prévenir ses clients en cas de retard.

La fiche de conception (une page et la maquette) est dans `docs/fiche_conception.docx`.

---

## 1. Sources

Le détail complet (adresse, date de récupération, remarques) est dans `docs/sources.csv`.

| Source | Adresse | Récupération | Contenu |
| --- | --- | --- | --- |
| Port of Los Angeles — Container Statistics | https://portoflosangeles.org/business/statistics/Container-Statistics/Historical-TEU-Statistics-{année} | 19/11/2026, par script | EVP mensuels 2019 à oct. 2026 : importations, exportations, vides (import et export), total |
| Port of Long Beach — TEUs Archive | https://polb.com/business/port-statistics/ | 19/11/2026, export CSV manuel | EVP mensuels 1987 à oct. 2026 : Loaded Inbound/Outbound, Empty Inbound/Outbound, Total |
| Banque mondiale et S&P Global — CPPI 2020 to 2024 (5e édition, sept. 2025) | https://hdl.handle.net/10986/43744 | 19/11/2026, PDF | Score et rang 2024 de 403 ports |
| Banque mondiale et S&P Global — CPPI 2025 (6e édition, juin 2026) | https://openknowledge.worldbank.org | 19/11/2026, PDF | Score et rang 2025 |
| CNUCED (UNCTADstat) — Port calls: Performance indicators, annual | https://unctadstat.unctad.org/datacentre/ (US.PortCalls) | 19/11/2026, CSV | Temps médian au port des porte-conteneurs, par pays, 2019-2023 |
| CNUCED (UNCTADstat) — Port calls: Calls by commercial market, annual | https://unctadstat.unctad.org/datacentre/ (US.PortCallsArrivals) | 19/11/2026, CSV | Nombre d'escales de porte-conteneurs, par pays, 2019-2023 |
| Open-Meteo — Forecast API et Marine API | https://api.open-meteo.com/v1/forecast et https://marine-api.open-meteo.com/v1/marine | À chaque exécution (heure enregistrée dans le fichier) | Vent, rafales, direction du vent, vagues ; actuel et 72 h |
| aisstream.io | wss://stream.aisstream.io/v0/stream | À chaque exécution (heure enregistrée dans le fichier) | Position, vitesse, statut et type des navires autour du port |

Ports de comparaison du CPPI : Los Angeles, Long Beach, Djibouti, Singapour, Rotterdam, Tanger Med.
Pays de comparaison de la CNUCED : Monde, États-Unis, Chine, Corée du Sud, Pays-Bas, Singapour.

---

## 2. Organisation du projet et traitements

```
app.py                      le tableau de bord (Streamlit) : lit les fichiers, n'appelle aucune API
scripts/download_pola.py    télécharge les 8 pages annuelles de Los Angeles -> data/raw/pola_AAAA.csv
scripts/clean.py            nettoie et assemble les données historiques -> data/clean/
scripts/fetch_weather.py    récupère la météo -> data/live/meteo.csv, meteo_actuelle.csv
scripts/fetch_ais.py        écoute le flux AIS 3 minutes -> data/live/ais_snapshot.csv, ais_historique.csv
data/raw/                   fichiers bruts, jamais modifiés à la main (PDF CPPI, CSV des ports et de la CNUCED)
data/clean/                 volumes.csv, cppi.csv, unctad.csv
data/live/                  données en direct
docs/                       fiche de conception, sources.csv
```

### Ce que fait `clean.py`

- **Los Angeles** : garde les 12 lignes de mois (retire les totaux annuels et fiscaux), convertit les nombres au format américain, additionne Empty Imports + Empty Exports pour obtenir les vides.
- **Long Beach** : convertit les dates (« Oct 2026 »), garde la période depuis janvier 2019, utilise le Total Empties publié pour les vides.
- **Contrôle de qualité** : pour chaque mois, recalcule importations + exportations + vides et compare au total publié.
- **CPPI** : reprend `data/raw/cppi_manuel.csv`, où chaque valeur a été relevée dans les annexes des deux rapports, avec la page du PDF.
- **CNUCED** : lit l'année dans le fichier `_metadata.txt` de chaque téléchargement, remet les années en lignes, retire les régions et traduit les noms de pays.

Résultat : `volumes.csv` (188 lignes = 94 mois × 2 ports, de janv. 2019 à oct. 2026), `cppi.csv` (12 lignes), `unctad.csv` (30 lignes).

### Anomalies trouvées dans les sources

| Source | Mois | Problème | Traitement |
| --- | --- | --- | --- |
| Los Angeles | nov. 2020 | Total publié illisible : « 889.,748.15 » | Total recalculé : 889 746 EVP, identique au chiffre annoncé par le port |
| Long Beach | nov. 2020 | Empty Inbound + Empty Outbound (253 564) ≠ Total Empties (283 563) | Total Empties publié conservé, car il correspond au total du mois confirmé par le port (783 523 EVP) |

---

## 3. Méthode

### Les six indicateurs (tuiles)

| # | Indicateur | Référence | Décision |
| --- | --- | --- | --- |
| 1 | Importations pleines du mois, LA + LB | Même mois de l'année précédente | Mensuelle |
| 2 | Prévision des importations sur 3 mois, avec fourchette à 95 % | Mêmes mois de l'année précédente | Mensuelle |
| 3 | Rang CPPI de LA et LB | Édition précédente et rang de Djibouti | Mensuelle |
| 4 | Temps médian au port des porte-conteneurs aux États-Unis (CNUCED) | Médiane mondiale | Mensuelle |
| 5 | Navires au mouillage autour du port (AIS) | Moyenne des relevés précédents | Quotidienne |
| 6 | Rafale maximale prévue sur les 48 prochaines heures | Seuil de 30 nœuds | Quotidienne |

Chaque tuile affiche la valeur, la référence, la tendance (flèche verte si l'évolution est favorable, rouge sinon) et la date de la donnée.

### Fonctions intelligentes

- **Prévision avec marge d'incertitude** : modèle de lissage exponentiel ETS (statsmodels) avec erreur additive, tendance amortie et saisonnalité annuelle (12 mois), ajusté sur les importations mensuelles depuis 2019. Il donne la prévision des 3 mois suivants et un intervalle de prédiction à 95 %. La fourchette du cumul sur 3 mois additionne les bornes mois par mois (approximation prudente).
- **Détection d'anomalies** : évolution des importations sur un an, transformée en z-score ; un mois est signalé si |z| > 2. Mois détectés : févr., mars et mai 2021 (reprise après le Covid).
- **Alerte météo** : bandeau rouge si la rafale maximale prévue sur 48 h dépasse 30 nœuds ou si les vagues dépassent 2,5 m.

### Recommandation

Construite automatiquement par des règles :

- **Décision du mois** : prévision supérieure de plus de 5 % à l'an dernier → augmenter les contrats ; inférieure de plus de 5 % → les réduire ; sinon → les garder. Si Los Angeles est mieux classé que Long Beach au CPPI → privilégier les services qui accostent à Los Angeles.
- **Décision du jour** : rafales au-dessus du seuil, ou navires au mouillage supérieurs à 1,5 fois la moyenne → décaler les enlèvements de 24 à 48 h et prévenir les clients ; sinon → maintenir.

### Actualisation et disponibilité des sources

- Le tableau de bord **ne rappelle jamais les API** : il lit les fichiers de `data/`, gardés en mémoire une heure.
- La météo et l'AIS sont récupérés par des scripts séparés (à la main, ou par une tâche programmée).
- Si un fichier manque ou si une API ne répond pas, un message clair s'affiche (« Météo indisponible », « AIS indisponible », « Aucun navire reçu ») et le reste du tableau de bord continue de fonctionner.
- Aucune clé d'API n'est dans le code : la clé aisstream.io est lue dans `.streamlit/secrets.toml` (exclu par `.gitignore`) ou dans les secrets de Streamlit Cloud / de la variable d'environnement `AISSTREAM_API_KEY`.

---

## 4. Limites

**Données**
- Les volumes d'un mois sont publiés environ 2 semaines après la fin du mois ; le CPPI et la CNUCED avec plusieurs mois de retard. La dernière année CNUCED publiée est 2023.
- Le CPPI note des **ports**, la CNUCED donne des chiffres par **pays** (« États-Unis » = tous les ports américains) : les deux ne sont pas comparables directement et sont affichés séparément.
- Djibouti n'est pas couvert par les statistiques d'escales de la CNUCED ; il n'est comparé que via le CPPI. Singapour n'est pas publié par la CNUCED de 2019 à 2021.
- Les pays de comparaison de la CNUCED (Corée du Sud) ne sont pas exactement les mêmes que les ports du CPPI (Tanger Med, Maroc).
- Le site du Port of Long Beach bloque les accès automatiques (erreur 403) et certaines connexions (Access Denied) : l'archive a été exportée manuellement en CSV depuis un téléphone avec VPN. Sa mise à jour ne peut pas être automatisée.
- Un temps au port plus long ne signifie pas forcément un port moins efficace (choix de l'armateur).

**Direct**
- La couverture AIS gratuite est partielle, et le type de navire reste souvent inconnu (fiche envoyée toutes les 6 minutes environ, écoute de 3 minutes).
- Un relevé AIS est un instantané ; la moyenne de référence des navires en attente ne devient fiable qu'avec de nombreux relevés.
- La météo est une prévision de modèle pour un seul point à l'entrée du port.
- Les seuils (30 nœuds, 2,5 m) sont des repères indicatifs, pas des règles officielles du port.

**Méthodes**
- La prévision prolonge la tendance et la saisonnalité passées : elle ne voit pas les chocs (droits de douane, grève, crise).
- La détection d'anomalies s'appuie sur une période (2019-2026) elle-même très perturbée par le Covid.
- La recommandation applique des règles simples : c'est une aide à la décision.

---

## 5. Lancer le projet sur son ordinateur

```
python -m venv .venv
.venv\Scripts\activate          (Windows)   |   source .venv/bin/activate   (Mac / Linux)
python -m pip install -r requirements.txt

python scripts/download_pola.py   # volumes de Los Angeles
python scripts/clean.py           # données propres
python scripts/fetch_weather.py   # météo
python scripts/fetch_ais.py       # navires (nécessite une clé aisstream.io dans .streamlit/secrets.toml)

python -m streamlit run app.py
```

Contenu de `.streamlit/secrets.toml` (à créer, jamais publié) :

```
AISSTREAM_API_KEY = "votre-clé"
```

L'utilisation de l'IA (Claude) a servi à guider le travail et à rédiger une partie du code ; chaque script a été exécuté, testé et corrigé par l'auteur.
