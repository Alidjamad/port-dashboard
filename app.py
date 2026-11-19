# Tableau de bord du complexe portuaire de San Pedro Bay (Los Angeles + Long Beach)
# Pour : le responsable des opérations d'un transitaire.
# Lancer : python -m streamlit run app.py
#
# Le tableau de bord ne fait AUCUN appel aux API : il lit uniquement les fichiers préparés par
#   - scripts/clean.py         -> data/clean/ (volumes, CPPI, CNUCED)
#   - scripts/fetch_weather.py -> data/live/meteo*.csv
#   - scripts/fetch_ais.py     -> data/live/ais_*.csv
# Si un fichier manque, un message clair s'affiche et le reste du tableau de bord fonctionne.

import subprocess
import sys
import warnings
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

warnings.filterwarnings("ignore")  # messages techniques de statsmodels, sans importance ici

SEUIL_RAFALES = 30    # nœuds : seuil d'alerte indicatif (pas une règle officielle du port)
SEUIL_VAGUES = 2.5    # mètres : seuil d'alerte indicatif
FUSEAU_PORT = ZoneInfo("America/Los_Angeles")

# Couleurs du tableau de bord
BLEU, ORANGE, GRIS, ROUGE, VERT = "#3b8eea", "#f28e2b", "#9aa7b8", "#e5484d", "#3fb950"
TEXTE, TEXTE_DOUX = "#e6edf3", "#9fb0c3"

st.set_page_config(page_title="San Pedro Bay — tableau de bord", layout="wide",
                   initial_sidebar_state="collapsed")

# =============================================================== Style de la page (CSS)
st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1500px;}
header[data-testid="stHeader"] {background: transparent;}
.entete {display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;
         border-bottom:1px solid #22385a; padding-bottom:12px; margin-bottom:14px;}
.entete h1 {font-size:1.55rem; margin:0; padding:0; color:#e6edf3;}
.entete p {margin:2px 0 0 0; color:#9fb0c3;}
.entete .date {text-align:right; color:#e6edf3; font-size:1rem;}
.entete .date span {color:#9fb0c3; font-size:.85rem;}
.bandeau {border-radius:10px; padding:12px 18px; font-weight:700; font-size:1.15rem; margin-bottom:14px;
          display:flex; align-items:center; gap:12px;}
.bandeau.alerte {background:#b3261e; color:#fff;}
.bandeau.calme {background:#123524; color:#7ee2a0; border:1px solid #1f6f43; font-size:1rem;}
.tuile {background:#11223a; border:1px solid #22385a; border-radius:12px; padding:14px 16px;
        height:100%; min-height:172px;}
.tuile .tete {display:flex; align-items:center; gap:10px; color:#e6edf3; font-weight:600; font-size:.95rem;}
.tuile .valeur {font-size:1.75rem; font-weight:700; color:#fff; margin:10px 0 4px 0; line-height:1.15;}
.tuile .ref {color:#9fb0c3; font-size:.85rem;}
.tuile .maj {color:#9fb0c3; font-size:.78rem; margin-top:8px;}
.hausse-bonne, .baisse-bonne {color:#3fb950; font-weight:600;}
.hausse-mauvaise, .baisse-mauvaise {color:#ff7b72; font-weight:600;}
.titre-bloc {display:flex; align-items:center; gap:10px; color:#e6edf3; font-weight:600; font-size:1.02rem;
             margin:0 0 2px 0;}
.sous-titre {color:#9fb0c3; font-size:.8rem; margin:0 0 4px 0;}
.note {background:#1b2d47; border-radius:8px; padding:6px 12px; color:#c9d4e2; font-size:.82rem; text-align:center;}
.legende span {display:inline-flex; align-items:center; gap:6px; margin-right:14px; color:#c9d4e2; font-size:.82rem;}
.legende i {width:11px; height:11px; border-radius:50%; display:inline-block;}
.reco {background:#1d4ed8; background:linear-gradient(90deg,#1e4fbf,#2563eb); border-radius:12px;
       padding:14px 20px; color:#fff; font-size:1.02rem; display:flex; gap:14px; align-items:flex-start; margin-top:6px;}
.reco b {color:#fff;}
.pied {color:#7f91a7; font-size:.75rem; margin-top:10px;}
div[data-testid="stVerticalBlockBorderWrapper"] {background:#0f1f35; border-color:#22385a !important; border-radius:12px;}
</style>
""", unsafe_allow_html=True)

# Petites icônes dessinées en SVG (aucune image externe)
def icone(nom, couleur=BLEU, taille=22):
    traits = {
        "navire": "M3 17l2 4h14l2-4H3zm3-3h12l1 3H5l1-3zm3-6h6v6H9V8zm2-4h2v4h-2V4z",
        "courbe": "M3 20h18M4 16l5-5 4 3 7-8M17 6h3v3",
        "trophee": "M8 4h8v5a4 4 0 01-8 0V4zM8 6H5a3 3 0 003 4M16 6h3a3 3 0 01-3 4M12 13v4M8 20h8M10 17h4",
        "horloge": "M12 3a9 9 0 100 18 9 9 0 000-18zM12 7v5l3 2",
        "ancre": "M12 5a2 2 0 100-4 2 2 0 000 4zM12 5v16M5 13a7 7 0 0014 0M8 9h8",
        "vent": "M3 8h11a3 3 0 10-3-3M3 12h15a3 3 0 11-3 3M3 16h8",
        "alerte": "M12 3l10 18H2L12 3zM12 10v4M12 17v.5",
        "globe": "M12 3a9 9 0 100 18 9 9 0 000-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
        "repere": "M12 21s-7-6.5-7-12a7 7 0 0114 0c0 5.5-7 12-7 12zM12 11a2 2 0 100-4 2 2 0 000 4z",
        "soleil": "M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5",
        "barres": "M4 20V10M10 20V4M16 20v-7M22 20H2",
        "ampoule": "M9 18h6M10 21h4M12 3a6 6 0 00-3.5 10.9V16h7v-2.1A6 6 0 0012 3z",
        "calendrier": "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
    }
    return (f'<svg width="{taille}" height="{taille}" viewBox="0 0 24 24" fill="none" stroke="{couleur}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="{traits[nom]}"/></svg>')


# =============================================================== Chargement des données
@st.cache_data(ttl=3600)   # relu au maximum une fois par heure
def lire(chemin, **options):
    """Lit un CSV. Renvoie None (au lieu de planter) si le fichier est absent ou illisible."""
    try:
        return pd.read_csv(chemin, **options)
    except Exception:
        return None


volumes = lire("data/clean/volumes.csv", parse_dates=["date"])
cppi = lire("data/clean/cppi.csv")
unctad = lire("data/clean/unctad.csv")
meteo = lire("data/live/meteo.csv", parse_dates=["heure_locale"])
meteo_now = lire("data/live/meteo_actuelle.csv")
ais = lire("data/live/ais_snapshot.csv")
ais_hist = lire("data/live/ais_historique.csv")


# =============================================================== Petites fonctions de mise en forme
def fr(x, decimales=0):
    """Nombre à la française : espace pour les milliers, virgule pour les décimales."""
    return f"{x:,.{decimales}f}".replace(",", " ").replace(".", ",")


def mois_fr(date):
    noms = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
    return f"{noms[date.month - 1]} {date.year}"


def heure_port(texte_utc, format="%d/%m %Hh%M"):
    """Heure UTC enregistrée par les scripts -> heure de Los Angeles."""
    try:
        return pd.Timestamp(texte_utc).tz_convert(FUSEAU_PORT).strftime(format)
    except Exception:
        return "?"


def tendance(ecart, texte, hausse_est_bonne=True):
    """Flèche colorée : vert si l'évolution est favorable, rouge sinon."""
    if round(ecart, 2) == 0:
        return f'<span style="color:#9fb0c3;font-weight:600">→ {texte}</span>'
    fleche = "↗" if ecart > 0 else "↘"
    bonne = (ecart > 0) == hausse_est_bonne
    return f'<span class="{"hausse-bonne" if bonne else "hausse-mauvaise"}">{fleche} {texte}</span>'


def tuile(colonne, nom_icone, titre, valeur, ref, maj, couleur_icone=BLEU):
    colonne.markdown(
        f'<div class="tuile"><div class="tete">{icone(nom_icone, couleur_icone, 26)}{titre}</div>'
        f'<div class="valeur">{valeur}</div><div class="ref">{ref}</div>'
        f'<div class="maj">{icone("horloge", TEXTE_DOUX, 12)} {maj}</div></div>', unsafe_allow_html=True)


def tuile_vide(colonne, nom_icone, titre, message):
    tuile(colonne, nom_icone, titre, "—", message, "source indisponible", GRIS)


def titre_bloc(conteneur, nom_icone, titre, sous_titre=None, couleur=BLEU):
    html = f'<div class="titre-bloc">{icone(nom_icone, couleur, 20)}{titre}</div>'
    if sous_titre:
        html += f'<div class="sous-titre">{sous_titre}</div>'
    conteneur.markdown(html, unsafe_allow_html=True)


def style_graphique(fig, hauteur):
    fig.update_layout(height=hauteur, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#c9d4e2", size=12),
                      margin=dict(l=8, r=8, t=30, b=8),
                      legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(gridcolor="#1f3350", zeroline=False)
    fig.update_yaxes(gridcolor="#1f3350", zeroline=False)
    return fig


# =============================================================== Calcul des indicateurs
ind = {}   # on range ici les valeurs utiles pour les tuiles, les graphiques et la recommandation


@st.cache_data
def prevoir(serie, horizon=3):
    """Prévision ETS (tendance amortie + saisonnalité annuelle) avec intervalle à 95 %."""
    modele = ETSModel(serie, error="add", trend="add", damped_trend=True,
                      seasonal="add", seasonal_periods=12).fit(disp=False)
    prev = modele.get_prediction(start=len(serie), end=len(serie) + horizon - 1).summary_frame(alpha=0.05)
    prev.index = pd.date_range(serie.index[-1] + pd.offsets.MonthBegin(), periods=horizon, freq="MS")
    return prev[["mean", "pi_lower", "pi_upper"]]


# --- 1 & 2. Importations du complexe + prévision avec marge d'incertitude
if volumes is not None:
    complexe = volumes.groupby("date")[["imports", "exports", "vides", "total"]].sum().asfreq("MS")
    dernier = complexe.index.max()
    ind["dernier_mois"] = dernier
    ind["imports"] = complexe.loc[dernier, "imports"]
    ind["imports_n1"] = complexe.loc[dernier - pd.DateOffset(years=1), "imports"]
    ind["imports_var"] = (ind["imports"] / ind["imports_n1"] - 1) * 100

    prev = prevoir(complexe["imports"].astype(float))
    ind["prev"] = prev
    ind["prev_total"] = prev["mean"].sum()
    # Fourchette approchée du cumul : on additionne les bornes mois par mois (prudent, un peu large)
    ind["prev_bas"], ind["prev_haut"] = prev["pi_lower"].sum(), prev["pi_upper"].sum()
    ind["prev_n1"] = complexe.loc[prev.index - pd.DateOffset(years=1), "imports"].sum()
    ind["prev_var"] = (ind["prev_total"] / ind["prev_n1"] - 1) * 100

    # Prévision par port, pour le graphique
    ind["prev_port"] = {p: prevoir(volumes[volumes["port"] == p].set_index("date")["imports"]
                                   .asfreq("MS").astype(float)) for p in ["Los Angeles", "Long Beach"]}

    # Détection d'anomalies : mois dont l'évolution sur un an sort de l'ordinaire (|z-score| > 2)
    evol = complexe["imports"].pct_change(12) * 100
    z = (evol - evol.mean()) / evol.std()
    ind["anomalies"] = [(d, evol[d]) for d in complexe.index[z.abs() > 2]]

# --- 3. CPPI
if cppi is not None:
    editions = sorted(cppi["annee_donnees"].unique())
    recent, ancien = cppi[cppi["annee_donnees"] == editions[-1]], cppi[cppi["annee_donnees"] == editions[0]]
    rang = lambda df, port: int(df.loc[df["port"] == port, "rang"].iloc[0])
    ind["cppi_annee"] = editions[-1]
    for p, cle in [("Los Angeles", "la"), ("Long Beach", "lb"), ("Djibouti", "dj")]:
        ind[f"rang_{cle}"], ind[f"rang_{cle}_avant"] = rang(recent, p), rang(ancien, p)

# --- 4. CNUCED
if unctad is not None:
    derniere = int(unctad.dropna(subset=["temps_median_jours"])["annee"].max())
    u = unctad[unctad["annee"] == derniere].set_index("pays")
    ind["cnuced_annee"] = derniere
    ind["temps_usa"], ind["temps_monde"] = u.loc["États-Unis", "temps_median_jours"], u.loc["Monde", "temps_median_jours"]

# --- 5. Navires en attente (AIS)
if ais is not None and len(ais):
    ind["mouillage"] = int((ais["statut"] == "Au mouillage").sum())
    ind["ais_maj"] = heure_port(ais["releve_utc"].iloc[0])
    ind["mouillage_moy"] = ais_hist["nb_au_mouillage"].mean() if ais_hist is not None else None

# --- 6. Rafales maximales sur les 48 prochaines heures (à partir de maintenant)
maintenant = datetime.now(FUSEAU_PORT)
if meteo is not None:
    debut = pd.Timestamp(maintenant).tz_localize(None).floor("h")
    a_venir = meteo[(meteo["heure_locale"] >= debut) & (meteo["heure_locale"] < debut + pd.Timedelta(hours=48))]
    if a_venir.empty:   # fichier trop ancien : on prend les 48 dernières heures disponibles
        a_venir = meteo.tail(48)
    ind["rafales_max"] = a_venir["rafales_noeuds"].max()
    ind["rafales_heure"] = a_venir.loc[a_venir["rafales_noeuds"].idxmax(), "heure_locale"]
    ind["vagues_max"] = a_venir["vagues_m"].max()
    ind["meteo_maj"] = heure_port(meteo["recupere_le_utc"].iloc[0])


# =============================================================== En-tête
st.markdown(
    f'<div class="entete"><div style="display:flex;gap:14px;align-items:center">{icone("navire", TEXTE, 40)}'
    f'<div><h1>Tableau de bord — Complexe portuaire de San Pedro Bay (Los Angeles + Long Beach)</h1>'
    f'<p>Pour : responsable des opérations d\'un transitaire</p></div></div>'
    f'<div style="display:flex;gap:10px;align-items:center">{icone("calendrier", TEXTE, 26)}'
    f'<div class="date">{maintenant:%d/%m/%Y}<br><span>{maintenant:%H:%M} (heure de Los Angeles)</span></div></div></div>',
    unsafe_allow_html=True)

with st.sidebar:
    st.header("Actualisation")
    st.write("Les données en direct sont lues depuis `data/live/`.")
    if st.button("Mettre à jour la météo"):
        r = subprocess.run([sys.executable, "scripts/fetch_weather.py"], capture_output=True, text=True)
        st.success("Météo mise à jour.") if r.returncode == 0 else st.error("Météo indisponible.\n\n" + r.stdout)
        st.cache_data.clear()
    st.caption("L'AIS demande 3 minutes d'écoute : il est mis à jour par `scripts/fetch_ais.py`.")

# --- Bandeau d'alerte météo (fonction intelligente)
if "rafales_max" in ind and (ind["rafales_max"] > SEUIL_RAFALES or ind["vagues_max"] > SEUIL_VAGUES):
    st.markdown(f'<div class="bandeau alerte">{icone("alerte", "#fff", 28)} ALERTE : rafales de '
                f'{fr(ind["rafales_max"])} nœuds prévues le {ind["rafales_heure"]:%d/%m à %Hh} '
                f'(seuil {SEUIL_RAFALES}) · vagues jusqu\'à {fr(ind["vagues_max"], 1)} m</div>', unsafe_allow_html=True)
elif "rafales_max" in ind:
    st.markdown(f'<div class="bandeau calme">{icone("soleil", "#7ee2a0", 22)} Pas d\'alerte météo : rafales '
                f'maximales de {fr(ind["rafales_max"])} nœuds prévues sur 48 h (seuil {SEUIL_RAFALES})</div>',
                unsafe_allow_html=True)


# =============================================================== Les 6 tuiles
t = st.columns(6)
if "imports" in ind:
    d = ind["dernier_mois"]
    tuile(t[0], "navire", "Importations (mois)", f'{fr(ind["imports"])} EVP',
          tendance(ind["imports_var"], f'{ind["imports_var"]:+.0f} %') + f' vs {mois_fr(d - pd.DateOffset(years=1))}',
          f'{mois_fr(d)} · LA + LB')
    p = ind["prev"]
    tuile(t[1], "courbe", "Prévision 3 mois", f'{fr(ind["prev_total"] / 1e6, 2)} M EVP',
          f'({fr(ind["prev_bas"] / 1e6, 2)}–{fr(ind["prev_haut"] / 1e6, 2)} M) '
          + tendance(ind["prev_var"], f'{ind["prev_var"]:+.0f} %') + ' vs N-1',
          f'{mois_fr(p.index[0])} à {mois_fr(p.index[-1])}', VERT)
else:
    tuile_vide(t[0], "navire", "Importations (mois)", "lancer scripts/clean.py")
    tuile_vide(t[1], "courbe", "Prévision 3 mois", "lancer scripts/clean.py")

if "rang_la" in ind:
    gain = ind["rang_la_avant"] - ind["rang_la"]
    tuile(t[2], "trophee", "Rang CPPI", f'LA {ind["rang_la"]} / LB {ind["rang_lb"]}',
          tendance(gain, f'LA {gain:+d} places') + f' · Djibouti {ind["rang_dj"]}e',
          f'CPPI {ind["cppi_annee"]} · réf. édition préc.', "#f2c94c")
else:
    tuile_vide(t[2], "trophee", "Rang CPPI", "fichier cppi.csv absent")

if "temps_usa" in ind:
    ecart = ind["temps_usa"] - ind["temps_monde"]
    tuile(t[3], "horloge", "Temps au port (USA)", f'{fr(ind["temps_usa"], 2)} jour',
          tendance(ecart, f'{fr(ecart, 2)} j', hausse_est_bonne=False) + f' vs monde ({fr(ind["temps_monde"], 2)} j)',
          f'CNUCED {ind["cnuced_annee"]} · porte-conteneurs')
else:
    tuile_vide(t[3], "horloge", "Temps au port (USA)", "fichier unctad.csv absent")

if "mouillage" in ind:
    moy = ind["mouillage_moy"]
    ref = (tendance(ind["mouillage"] - moy, f'vs {fr(moy, 1)} en moyenne', hausse_est_bonne=False)
           if moy is not None else "pas encore de moyenne")
    tuile(t[4], "ancre", "Navires en attente", f'{ind["mouillage"]}', ref, f'AIS · relevé {ind["ais_maj"]}', "#b392f0")
else:
    tuile_vide(t[4], "ancre", "Navires en attente", "lancer scripts/fetch_ais.py")

if "rafales_max" in ind:
    ecart = ind["rafales_max"] - SEUIL_RAFALES
    tuile(t[5], "vent", "Rafales prévues 48 h", f'{fr(ind["rafales_max"])} nœuds',
          tendance(ecart, f'{ecart:+.0f}', hausse_est_bonne=False) + f' vs seuil {SEUIL_RAFALES}',
          f'Open-Meteo · {ind["meteo_maj"]}', "#56d4dd")
else:
    tuile_vide(t[5], "vent", "Rafales prévues 48 h", "lancer scripts/fetch_weather.py")

st.write("")

# =============================================================== Ligne 1 : volumes + comparaison mondiale
gauche, droite = st.columns(2)

with gauche.container(border=True):
    if volumes is None:
        st.warning("Volumes indisponibles : lancer `python scripts/clean.py`.")
    else:
        a, b = st.columns([3, 2])
        # --- Importations mensuelles par port + prévision
        titre_bloc(a, "courbe", "Importations mensuelles 2019–2026",
                   "EVP pleins · pointillés : prévision 3 mois · zone : incertitude à 95 %")
        fig = go.Figure()
        for port, couleur, teinte in [("Los Angeles", BLEU, "rgba(110,170,255,.35)"),
                                      ("Long Beach", ORANGE, "rgba(255,170,90,.35)")]:
            d = volumes[volumes["port"] == port]
            fig.add_trace(go.Scatter(x=d["date"], y=d["imports"], name=port, mode="lines",
                                     line=dict(color=couleur, width=2)))
            p = ind["prev_port"][port]
            fig.add_trace(go.Scatter(x=list(p.index) + list(p.index[::-1]),
                                     y=list(p["pi_upper"]) + list(p["pi_lower"][::-1]), fill="toself",
                                     fillcolor=teinte, line=dict(width=0), mode="lines", showlegend=False,
                                     hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=[d["date"].iloc[-1], *p.index], y=[d["imports"].iloc[-1], *p["mean"]],
                                     mode="lines", line=dict(color=couleur, dash="dash", width=2),
                                     name=f"Prévision {port}", showlegend=False))
        style_graphique(fig, 330).update_yaxes(tickformat="~s")
        # Vue par défaut à partir de 2023 pour bien voir la prévision ; double-clic = toute la période depuis 2019
        fig.update_xaxes(range=[pd.Timestamp("2023-01-01"), ind["prev"].index[-1] + pd.Timedelta(days=45)])
        a.plotly_chart(fig, width="stretch")
        a.markdown('<div class="sous-titre">Vue depuis 2023 : double-cliquer sur le graphique pour afficher toute la '
                   'période depuis 2019.</div>', unsafe_allow_html=True)
        if ind["anomalies"]:
            liste = ", ".join(f"{mois_fr(dt)} ({v:+.0f} %)" for dt, v in ind["anomalies"])
            a.markdown(f'<div class="sous-titre">Anomalies détectées (évolution sur un an hors normes) : {liste}</div>',
                       unsafe_allow_html=True)

        # --- Répartition annuelle importations / exportations / vides
        titre_bloc(b, "barres", "Répartition des échanges", "Complexe LA + LB, années complètes")
        annuel = volumes.assign(annee=volumes["date"].dt.year).groupby("annee")[["imports", "exports", "vides"]].sum()
        nb_mois = volumes.groupby(volumes["date"].dt.year)["date"].nunique()
        annuel = annuel[nb_mois == 12].tail(3)   # années complètes (12 mois publiés)
        fig = go.Figure()
        for col, nom, couleur in [("imports", "Importations", BLEU), ("exports", "Exportations", ORANGE),
                                  ("vides", "Vides", GRIS)]:
            fig.add_trace(go.Bar(x=annuel.index.astype(str), y=annuel[col], name=nom, marker_color=couleur))
        total = annuel.sum(axis=1)
        fig.add_trace(go.Scatter(x=annuel.index.astype(str), y=total, mode="text", showlegend=False,
                                 text=[f"{fr(v / 1e6, 1)} M" for v in total], textposition="top center",
                                 textfont=dict(color=TEXTE)))
        style_graphique(fig, 330).update_layout(barmode="stack", bargap=0.35,
                                                legend=dict(orientation="h", y=-0.12, x=0))
        fig.update_yaxes(tickformat="~s", range=[0, total.max() * 1.15])
        b.plotly_chart(fig, width="stretch")

with droite.container(border=True):
    a, b = st.columns([3, 2])
    # --- CPPI
    if cppi is None:
        a.warning("CPPI indisponible.")
    else:
        titre_bloc(a, "trophee", "Rang CPPI : 6 ports, 2 éditions", "Rang mondial · plus bas = meilleur", "#f2c94c")
        ordre = ["Los Angeles", "Long Beach", "Djibouti", "Singapour", "Rotterdam", "Tanger Med"]
        fig = go.Figure()
        for annee, couleur in zip(editions, [BLEU, ORANGE]):
            d = cppi[cppi["annee_donnees"] == annee].set_index("port").loc[ordre]
            fig.add_trace(go.Bar(x=["LA", "LB", "Djibouti", "Singapour", "Rotterdam", "Tanger Med"], y=d["rang"],
                                 name=str(annee), marker_color=couleur, text=d["rang"], textposition="outside",
                                 customdata=d["score"], hovertemplate="Rang %{y}<br>Score %{customdata}<extra></extra>"))
        style_graphique(fig, 330).update_layout(barmode="group", bargap=0.25)
        fig.update_yaxes(range=[0, cppi["rang"].max() * 1.15])
        a.plotly_chart(fig, width="stretch")
    # --- CNUCED
    if unctad is None:
        b.warning("CNUCED indisponible.")
    else:
        titre_bloc(b, "horloge", "Temps médian au port", f"Porte-conteneurs, par pays · {ind['cnuced_annee']}")
        d = unctad[unctad["annee"] == ind["cnuced_annee"]].dropna(subset=["temps_median_jours"])
        d = d.sort_values("temps_median_jours", ascending=False)
        couleurs = [ORANGE if p == "États-Unis" else (GRIS if p == "Monde" else BLEU) for p in d["pays"]]
        fig = go.Figure(go.Bar(x=d["pays"], y=d["temps_median_jours"], marker_color=couleurs,
                               text=[f"{fr(v, 2)} j" for v in d["temps_median_jours"]], textposition="outside",
                               customdata=d["escales"],
                               hovertemplate="%{x}<br>%{y:.2f} jour<br>%{customdata:,} escales<extra></extra>"))
        style_graphique(fig, 330).update_yaxes(range=[0, d["temps_median_jours"].max() * 1.25])
        b.plotly_chart(fig, width="stretch")
        b.markdown('<div class="sous-titre">Djibouti n\'est pas couvert par la CNUCED. '
                   'Nombre d\'escales au survol.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="note">{icone("alerte", "#c9d4e2", 14)} CPPI = score par <b>port</b> ; '
                'CNUCED = chiffres par <b>pays</b> (États-Unis = tous les ports américains) : '
                'ne pas les comparer directement.</div>', unsafe_allow_html=True)

# =============================================================== Ligne 2 : carte + météo
gauche, droite = st.columns(2)

with gauche.container(border=True):
    titre_bloc(st, "repere", "Navires autour du port", "Dernier relevé AIS · couleur = statut", "#3fb9c6")
    if ais is None or not len(ais):
        st.warning("Données AIS indisponibles : lancer `python scripts/fetch_ais.py`.")
    else:
        statuts = {"En route": ([59, 142, 234], BLEU), "Au mouillage": ([242, 142, 43], ORANGE),
                   "À quai": ([63, 185, 80], VERT)}
        ais["couleur"] = ais["statut"].map(lambda s: statuts.get(s, ([154, 167, 184], GRIS))[0])
        couche = pdk.Layer("ScatterplotLayer", data=ais, get_position="[lon, lat]", get_fill_color="couleur",
                           get_radius=140, radius_min_pixels=4, pickable=True, stroked=True,
                           get_line_color=[255, 255, 255], line_width_min_pixels=1)
        st.pydeck_chart(pdk.Deck(layers=[couche], initial_view_state=pdk.ViewState(latitude=33.725, longitude=-118.23, zoom=11),
                                 map_style=None, tooltip={"text": "{nom}\n{type}\n{statut} · {vitesse_noeuds} nœuds"}),
                        height=330)
        legende = "".join(f'<span><i style="background:{c}"></i>{s}</span>' for s, (_, c) in statuts.items())
        st.markdown(f'<div class="legende">{legende}<span><i style="background:{GRIS}"></i>Autre</span></div>'
                    f'<div class="sous-titre">{len(ais)} navires captés · source aisstream.io (couverture gratuite partielle)</div>',
                    unsafe_allow_html=True)

with droite.container(border=True):
    titre_bloc(st, "soleil", "Météo 72 h à l'entrée du port", "Heure de Los Angeles · source Open-Meteo", "#f2c94c")
    if meteo is None or meteo_now is None:
        st.warning("Données météo indisponibles : lancer `python scripts/fetch_weather.py`.")
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=meteo["heure_locale"], y=meteo["vent_noeuds"], name="Vent (nœuds)",
                                 line=dict(color=BLEU, width=2)))
        fig.add_trace(go.Scatter(x=meteo["heure_locale"], y=meteo["rafales_noeuds"], name="Rafales (nœuds)",
                                 line=dict(color=ORANGE, width=2)))
        fig.add_trace(go.Scatter(x=meteo["heure_locale"], y=meteo["vagues_m"], name="Vagues (m)", yaxis="y2",
                                 line=dict(color="#8cc8ff", width=2, dash="dot")))
        fig.add_hline(y=SEUIL_RAFALES, line_dash="dash", line_color=ROUGE,
                      annotation_text=f"Seuil {SEUIL_RAFALES} nœuds", annotation_font_color=ROUGE)
        style_graphique(fig, 330)
        fig.update_layout(yaxis=dict(title="nœuds", range=[0, max(40, meteo["rafales_noeuds"].max() * 1.15)]),
                          yaxis2=dict(title="m", overlaying="y", side="right", showgrid=False,
                                      range=[0, max(4, meteo["vagues_m"].max() * 1.3)]))
        fig.update_xaxes(tickformat="%d/%m\n%Hh")
        st.plotly_chart(fig, width="stretch")
        n = meteo_now.iloc[0]
        st.markdown(f'<div class="sous-titre">Maintenant : vent {fr(n["vent_noeuds"])} nœuds · rafales '
                    f'{fr(n["rafales_noeuds"])} nœuds · vagues {fr(n["vagues_m"], 1)} m · '
                    f'dernier relevé AIS {ind.get("ais_maj", "?")} · météo {ind["meteo_maj"]}</div>',
                    unsafe_allow_html=True)


# =============================================================== Recommandation
phrases = []
if "imports" in ind:
    if ind["prev_var"] > 5:
        phrases.append(f"Le trafic monte (prévision {ind['prev_var']:+.0f} % sur 3 mois) : <b>augmenter dès maintenant "
                       "les contrats de camions et d'entrepôts</b>.")
    elif ind["prev_var"] < -5:
        phrases.append(f"Le trafic baisse (prévision {ind['prev_var']:+.0f} % sur 3 mois) : <b>réduire les contrats</b> "
                       "pour ne pas payer de capacité inutilisée.")
    else:
        phrases.append("Le trafic reste stable : <b>garder les contrats</b> au niveau actuel.")
if "rang_la" in ind and ind["rang_la"] < ind["rang_lb"]:
    phrases.append(f"Los Angeles (rang CPPI {ind['rang_la']}) est bien plus rapide que Long Beach (rang {ind['rang_lb']}) : "
                   "<b>privilégier les services qui accostent à Los Angeles</b>.")
causes = []
if "rafales_max" in ind and ind["rafales_max"] > SEUIL_RAFALES:
    causes.append(f"rafales de {fr(ind['rafales_max'])} nœuds prévues")
if "mouillage" in ind and ind.get("mouillage_moy") and ind["mouillage"] > ind["mouillage_moy"] * 1.5:
    causes.append(f"{ind['mouillage']} navires en attente")
if causes:
    phrases.append(" et ".join(causes).capitalize() + " : <b>décaler les enlèvements de 24 à 48 h</b> et prévenir les clients.")
elif "rafales_max" in ind or "mouillage" in ind:
    phrases.append("Ni congestion ni vent fort annoncés : <b>maintenir les enlèvements prévus</b>.")

if phrases:
    st.markdown(f'<div class="reco">{icone("ampoule", "#fff", 30)}<div><b>Recommandation :</b> '
                + " ".join(phrases) + "</div></div>", unsafe_allow_html=True)

st.markdown('<div class="pied">Sources : Port of Los Angeles · Port of Long Beach (TEUs Archive) · Banque mondiale et '
            'S&P Global (CPPI 2020-2024 et 2025) · CNUCED (UNCTADstat, Port calls, 2019-2023) · aisstream.io · '
            'Open-Meteo. Méthode et limites : voir README.md.</div>', unsafe_allow_html=True)
