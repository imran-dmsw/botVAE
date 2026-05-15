"""Données tabulaires pédagogiques et libellés pour le rapport VAE révisé (PDF + Excel)."""
from __future__ import annotations

from typing import Any

# Suffixes d'identifiants de scénario (après le code firme) → titre affiché
SCENARIO_TITLE_SUFFIXES: list[tuple[str, str]] = [
    ("_ProdPlus15_P1", "Production +15 % — Période 1"),
    ("_ProdPlus12_P1", "Production +12 % — Période 1"),
    ("_ProdPlus10_P1", "Production +10 % — Période 1"),
    ("_FocalPremium_P1", "Focus Premium — Période 1"),
    ("_Durabilite_2_tranches", "Durabilité 2 tranches — Période 1"),
    ("_Durabilite_2tranches", "Durabilité 2 tranches — Période 1"),
    ("_FocalPremium_P2", "Focus Premium — Période 2"),
    ("_Marketing_Max_P1", "Marketing maximum — Période 1"),
    ("_RD_5pct_P2", "R&D +5 % — Période 2"),
    ("_SousProduction_P1", "Sous-production (−28 %) — Période 1"),
    ("_Figee_P4", "Stratégie figée — Période 4"),
    ("_Prix2500_Promo10_P1", "Prix 2 500 $ + promo 10 % — Période 1"),
    ("_Figee_P8", "Stratégie figée — Période 8 (risque extrême)"),
]

# Suffixes scénarios par modèle (fiches produit : TRE_P040_P2ref, etc.)
MODEL_SCENARIO_TAIL_TITLES: dict[str, str] = {
    "P1": "Référence — Période 1",
    "P2ref": "Référence — Période 2",
    "FigP4": "Stratégie figée — Période 4",
    "FigP8": "Stratégie figée — Période 8",
    "MktMax": "Marketing maximum — Période 1",
    "Promo5": "Promotion −5 % — Période 1",
    "SousProd": "Sous-production — Période 1",
}

# Clé = sous-chaîne unique du titre affiché → (réaction concurrents, risque TRE)
COMPETITOR_REACTION_BY_TITLE_KEY: list[tuple[str, str, str]] = [
    (
        "Production +15 %",
        "AVE / GIA augmentent leur production ; CAN baisse les prix sur le segment 1.",
        "Guerre de volumes — pression sur les marges.",
    ),
    (
        "Focus Premium",
        "RID et AVE renforcent leurs gammes premium.",
        "Perte de PDM sur le milieu de gamme.",
    ),
    (
        "Marketing maximum",
        "AVE / GIA surenchérissent sur le digital et le social.",
        "ROI marketing réduit pour TRE.",
    ),
    (
        "R&D +5 %",
        "RID accélère l'innovation ; GIA baisse les prix.",
        "Risque d'obsolescence produit.",
    ),
    (
        "Sous-production",
        "Les concurrents captent la demande non servie.",
        "Perte de PDM durable.",
    ),
    (
        "Stratégie figée — Période 4",
        "Les firmes ajustent prix et promotions ; TRE perd en visibilité.",
        "Décrochage de PDM.",
    ),
    (
        "Prix 2 500 $ + promo 10 %",
        "Guerre des prix ; marges sectorielles comprimées.",
        "Profit très négatif possible.",
    ),
    (
        "Stratégie figée — Période 8",
        "Les concurrents dominent le marché ; TRE se marginalise.",
        "Risque de sortie de marché.",
    ),
]

# Ventes en ligne (% pédagogique) et tendance — par code firme
FIRM_ONLINE_PCT: dict[str, float] = {
    "AVE": 12.0,
    "TRE": 8.0,
    "GIA": 10.0,
    "CAN": 7.0,
    "RID": 5.0,
    "VEL": 6.0,
    "SUR": 4.0,
    "PED": 3.0,
    "EBI": 2.0,
}

FIRM_ONLINE_TREND: dict[str, str] = {
    "AVE": "↑ forte",
    "TRE": "↑ modérée",
    "GIA": "↑ modérée",
    "CAN": "→ stable",
    "RID": "→ stable",
    "VEL": "↑ légère",
    "SUR": "→ stable",
    "PED": "↓ légère",
    "EBI": "↓ légère",
}

# Notes anomalies portefeuille (TRE — exemples pédagogiques)
PORTFOLIO_ANOMALY_NOTES: dict[str, str] = {
    "P037": "⚠ Prix 5 000 $ > prix préféré seg. 1 (3 800 $) — repositionner.",
    "P038": "⚠ 2 références Basic sur seg. 2 — cannibalisation.",
    "P039": "⚠ 2 références Basic sur seg. 2 — arbitrer ou retirer.",
    "P040": "★ Produit phare — production cible 2 267 u.",
    "P041": "⚠ Basic + Premium sur même segment — différencier.",
    "P042": "⚠ Production 3 734 u. — hors plage cible 1 500–3 000.",
}

CANONICAL_CHANNELS = [
    ("Digital", 1),
    ("Social", 2),
    ("Influenceur", 3),
    ("Affichage", 4),
    ("Événements", 5),
]


def scenario_display_title(scenario_id: str) -> str:
    for suffix, title in SCENARIO_TITLE_SUFFIXES:
        if scenario_id.endswith(suffix) or suffix in scenario_id:
            return title
    parts = scenario_id.split("_")
    if len(parts) >= 3 and parts[0] in (
        "AVE", "CAN", "EBI", "GIA", "PED", "RID", "SUR", "TRE", "VEL", "VAE",
    ):
        model_key = parts[1]
        tail = "_".join(parts[2:])
        for key, title in MODEL_SCENARIO_TAIL_TITLES.items():
            if tail == key:
                return f"{model_key} — {title}"
    return scenario_id.replace("_", " ")


def competitor_reaction_blurb(scenario_id: str, firm_label: str = "TRE", *, max_len: int = 100) -> str:
    """Note courte sur les réactions concurrentes possibles (sans tableau dédié)."""
    disp = scenario_display_title(scenario_id)
    react, _ = competitor_reaction_for_title(disp, firm_label)
    short = react.strip()
    if len(short) > max_len:
        return short[: max_len - 1].rstrip() + "…"
    return short


def competitor_reaction_for_title(display_title: str, firm_label: str = "TRE") -> tuple[str, str]:
    for key, reaction, risk in COMPETITOR_REACTION_BY_TITLE_KEY:
        if key in display_title:
            return reaction, risk.replace("TRE", firm_label)
    return (
        "Réaction concurrentielle non cartographiée pour ce scénario.",
        f"Surveiller PDM et marge ({firm_label}).",
    )


def top3_channels_cell(mm_row: list[str]) -> str:
    """
    mm_row: [seg, d, s, inf, aff, ev] as strings from Excel.
    Returns formatted "Canal (coef) > …" with French decimal comma in display.
    """
    if len(mm_row) < 6:
        return ""
    parts: list[tuple[str, float]] = []
    for name, idx in CANONICAL_CHANNELS:
        try:
            v = float(str(mm_row[idx]).replace(",", "."))
        except (TypeError, ValueError):
            v = 0.0
        parts.append((name, v))
    parts.sort(key=lambda x: -x[1])
    top = parts[:3]
    out: list[str] = []
    for name, v in top:
        out.append(f"{name} ({v:.2f})".replace(".", ","))
    return " > ".join(out)


def canonical_gamme_label(raw: str | None) -> str:
    """Libellé affiché : Basic | Medium | Premium uniquement (Standard → Medium)."""
    s = str(raw or "").strip()
    low = s.lower()
    if low == "standard":
        return "Medium"
    if low in ("bas", "basic"):
        return "Basic"
    if low in ("moyen", "medium"):
        return "Medium"
    if low in ("haut", "premium"):
        return "Premium"
    if not s:
        return "—"
    return s[:1].upper() + s[1:] if len(s) > 1 else s.upper()


def portfolio_anomaly_note(product_key: str) -> str:
    return PORTFOLIO_ANOMALY_NOTES.get(product_key, "")


def production_band_note(units_ref: float) -> str:
    if units_ref < 1500 or units_ref > 3000:
        return "⚠ Hors plage cible 1 500–3 000 (unités réf.)."
    return ""
