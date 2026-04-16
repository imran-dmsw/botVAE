"""
Bot de simulation strategique marketing — Simulation VAE (Velos a Assistance Electrique)
Interface Streamlit — 4 modules :
  1. Simulation directe (scenario unique)
  2. Comparaison multi-scenarios
  3. Mode objectif cible (simulation inverse)
  4. Historique
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import pathlib
from typing import Optional

from config.market_config import MARKET_CONFIG
from engine.models import ScenarioInput, MarketingChannels
from engine.simulation import (
    simulate, simulate_multi, period_to_year, total_market_size,
    simulate_full_market, simulate_full_market_all_periods, suggest_next_production,
)
from engine.optimizer import find_parameters_for_target, SUPPORTED_METRICS
from engine.plan_executor import execute_plan_matrix, runs_to_dataframe, compare_policies
from simulation.multi_scenario_runner import (
    run_all_scenarios,
    compare_scenarios as compare_auto_scenarios,
    run_promo_sales_test,
    run_marketing_short_term_test,
)
from simulation.full_market_runner import run_full_market_simulation
from reporting.recommendation_engine import generate_recommendations
from reports.generator import (
    generate_markdown_report,
    generate_word_report,
    generate_pdf_report,
    generate_json_report,
    generate_multi_pdf_report,
)
from data.history import save_scenario, get_summary_df, clear_history

st.set_page_config(
    page_title="Bot VAE — Simulation Marketing",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

CFG = MARKET_CONFIG
SEGMENT_OPTIONS = {v["label"]: k for k, v in CFG["segments"].items()}
RANGE_OPTIONS = {v["label"]: k for k, v in CFG["ranges"].items()}
PRODUCT_TYPE_OPTIONS = {v["label"]: k for k, v in CFG["product_types"].items()}
FIRM_OPTIONS = list(CFG["firms"].keys())   # ["AVE", "CAN", ..., "VEL"]
STATUS_OPTIONS = {
    "Actif": "active",
    "Pre-lancement": "pre_launch",
    "Developpement": "development",
    "Retrait": "withdrawal",
    "Inactif": "inactive",
}

# Default labels for first selectbox values
DEFAULT_SEGMENT_LABEL = list(SEGMENT_OPTIONS.keys())[0]       # "Urbains Presses"
DEFAULT_RANGE_LABEL = list(RANGE_OPTIONS.keys())[1]           # "Milieu de gamme"
DEFAULT_PRODUCT_TYPE_LABEL = list(PRODUCT_TYPE_OPTIONS.keys())[1]  # "Ville quotidien+"


def fmt_cad(v: float) -> str:
    return f"{v:,.0f} $"


def fmt_pct(v: float) -> str:
    return f"{v*100:.1f}%"


def color_margin(margin: float) -> str:
    if margin >= 0.10:
        return "🟢"
    if margin >= 0.02:
        return "🟡"
    return "🔴"


def _default_price_for(product_type_key: str, range_key: str) -> float:
    """Suggest a price = product base cost + range target margin."""
    pt = CFG["product_types"].get(product_type_key, {})
    rng = CFG["ranges"].get(range_key, {})
    base = pt.get("base_cost", 2000)
    margin = rng.get("target_margin_per_unit", 1000)
    return float(base + margin)


def _calc_options_delta(key_prefix: str) -> tuple[float, float]:
    """Return (total_cost_delta, total_price_delta) from selected options."""
    opts = CFG["product_options"]
    total_cost_delta = 0.0
    total_price_delta = 0.0
    for opt_key, opt_cfg in opts.items():
        selected = st.session_state.get(f"{key_prefix}opt_{opt_key}", opt_cfg["default"])
        choice = opt_cfg["choices"].get(selected, {})
        total_cost_delta += choice.get("cost_delta", 0)
        total_price_delta += choice.get("price_delta", 0)
    return total_cost_delta, total_price_delta


def _build_improvement_plan(scenario: ScenarioInput, result) -> list[str]:
    """Build a concise, actionable improvement plan from simulation outcomes."""
    plan = []
    min_margin = CFG["constraints"]["min_profit_rate"]
    mkt_max = scenario.adjusted_budget * CFG["constraints"]["marketing_max_pct"]
    rd_max = scenario.adjusted_budget * CFG["constraints"]["rd_max_pct"]

    if result.margin < min_margin:
        plan.append(
            "Priorite rentabilite : remontez le prix net (ou reduisez la promotion) "
            "et coupez les couts les moins performants jusqu'a repasser au-dessus de 2% de marge."
        )
    elif result.margin < 0.10:
        plan.append(
            "Consolidez la marge : visez une marge >= 10% via un meilleur mix prix/couts "
            "et une allocation budgetaire plus selective."
        )

    if result.service_rate < 0.90:
        target_prod = int(result.demand * 1.05)
        plan.append(
            f"Augmentez la production : le taux de service est faible ({result.service_rate*100:.0f}%). "
            f"Testez environ {target_prod:,} unites pour capter la demande non servie."
        )

    if result.market_share_segment < 0.10 and scenario.marketing_budget < mkt_max * 0.9:
        plan.append(
            "Renforcez la conquete segment : augmentez le budget marketing sur les canaux performants "
            "jusqu'a 90-100% du plafond autorise si le ROI reste positif."
        )

    if result.innovation_score < 6.0 and scenario.rd_budget < rd_max * 0.8:
        plan.append(
            "Montez l'innovation : augmentez progressivement la R&D (jusqu'a 80-100% du plafond) "
            "et priorisez 1-2 projets a fort impact client."
        )

    if result.sustainability_score < 6.0 and scenario.sustainability_investment == 0:
        plan.append(
            "Ajoutez un volet durabilite : demarrez un investissement modere et regulier "
            "pour renforcer l'attractivite long terme."
        )

    if not plan:
        plan.append(
            "Plan actuel solide : maintenez la strategie et lancez un test A/B "
            "sur prix ou mix marketing pour chercher un gain incremental."
        )

    # Always end with a concrete execution cadence.
    plan.append(
        "Execution conseillee : appliquez 1-2 changements a la fois, relancez la simulation, "
        "puis comparez Profit, Marge, PDM et Taux de service."
    )
    return plan


def build_scenario_from_form(key_prefix: str = "") -> ScenarioInput:
    """Read all widget values from session state and build a ScenarioInput."""
    p = key_prefix
    seg_lbl = st.session_state.get(f"{p}segment_lbl", DEFAULT_SEGMENT_LABEL)
    seg_key = SEGMENT_OPTIONS.get(seg_lbl, "urbains_presses")
    return ScenarioInput(
        firm_name=st.session_state.get(f"{p}firm_name", "Firme A"),
        period=st.session_state.get(f"{p}period", 1),
        scenario_name=st.session_state.get(f"{p}scenario_name", "Scenario 1"),
        model_name=st.session_state.get(f"{p}model_name", "Modele X"),
        product_type=PRODUCT_TYPE_OPTIONS.get(
            st.session_state.get(f"{p}product_type_lbl", DEFAULT_PRODUCT_TYPE_LABEL), "ville_quotidien"
        ),
        segment=seg_key,
        model_range=RANGE_OPTIONS.get(
            st.session_state.get(f"{p}range_lbl", DEFAULT_RANGE_LABEL), "mid"
        ),
        product_status=STATUS_OPTIONS.get(
            st.session_state.get(f"{p}status_lbl", "Actif"), "active"
        ),
        marketing_budget=st.session_state.get(f"{p}mkt_budget", 50000.0),
        marketing_channels=MarketingChannels(
            digital=st.session_state.get(f"{p}ch_digital", 0.0),
            social_media=st.session_state.get(f"{p}ch_social", 0.0),
            influencers=st.session_state.get(f"{p}ch_influencers", 0.0),
            display=st.session_state.get(f"{p}ch_display", 0.0),
            events=st.session_state.get(f"{p}ch_events", 0.0),
        ),
        rd_budget=st.session_state.get(f"{p}rd_budget", 0.0),
        rd_projects=st.session_state.get(f"{p}rd_projects", 0),
        new_model_launch=st.session_state.get(f"{p}new_model", False),
        sustainability_investment=st.session_state.get(f"{p}sustain_invest", 0.0),
        sustainability_periods=st.session_state.get(f"{p}sustain_periods", 0),
        price=st.session_state.get(f"{p}price", 3000.0),
        promotion_rate=st.session_state.get(f"{p}promo_rate", 0.0) / 100.0,
        production=st.session_state.get(f"{p}production", 1000),
        liquidation=st.session_state.get(f"{p}liquidation", False),
        adjusted_budget=st.session_state.get(f"{p}adj_budget", 1_000_000.0),
        previous_innovation_score=st.session_state.get(f"{p}prev_innov", 5.0),
        previous_sustainability_score=st.session_state.get(f"{p}prev_sustain", 5.0),
        competitor_attractiveness=st.session_state.get(
            f"{p}comp_attr",
            CFG["default_competitor_attractiveness"].get(seg_key, 12.0),
        ),
        total_withdrawals_used=st.session_state.get(f"{p}total_withdrawals_used", 0),
        last_withdrawal_period=st.session_state.get(f"{p}last_withdrawal_period", 0),
    )


# ─── Scenario form widget ─────────────────────────────────────────────────────

def scenario_form(key_prefix: str = "", title: str = "Parametres du scenario"):
    p = key_prefix
    with st.expander(title, expanded=True):
        # ── Identification ──────────────────────────────────────────────────
        col1, col2, col3 = st.columns(3)
        with col1:
            st.text_input("Firme", value="Firme A", key=f"{p}firm_name")
            st.number_input("Periode", min_value=1, max_value=8, value=1, step=1, key=f"{p}period")
            st.text_input("Nom du scenario", value="Scenario 1", key=f"{p}scenario_name")
        with col2:
            st.text_input("Nom du modele", value="Modele X", key=f"{p}model_name")
            st.selectbox("Segment cible", list(SEGMENT_OPTIONS.keys()), key=f"{p}segment_lbl")
            st.selectbox("Gamme", list(RANGE_OPTIONS.keys()), index=1, key=f"{p}range_lbl")
        with col3:
            st.selectbox("Statut produit", list(STATUS_OPTIONS.keys()), key=f"{p}status_lbl")
            st.number_input("Budget ajuste reference ($)", min_value=10000.0, value=1_000_000.0,
                            step=50000.0, key=f"{p}adj_budget")
            # Period info
            period_val = st.session_state.get(f"{p}period", 1)
            year = period_to_year(period_val)
            mkt = total_market_size(period_val)
            st.caption(f"Annee : **{year}** — Marche : **{mkt:,.0f} unites**")

        # ── Product type & options ──────────────────────────────────────────
        st.markdown("**Type de produit et options**")
        col_pt1, col_pt2 = st.columns([2, 3])
        with col_pt1:
            st.selectbox(
                "Type de modele",
                list(PRODUCT_TYPE_OPTIONS.keys()),
                key=f"{p}product_type_lbl",
                help="Definit le cout de base de fabrication du modele",
            )
            pt_lbl = st.session_state.get(f"{p}product_type_lbl", DEFAULT_PRODUCT_TYPE_LABEL)
            pt_key = PRODUCT_TYPE_OPTIONS.get(pt_lbl, "ville_quotidien")
            pt_cfg = CFG["product_types"][pt_key]
            rng_lbl = st.session_state.get(f"{p}range_lbl", DEFAULT_RANGE_LABEL)
            rng_key = RANGE_OPTIONS.get(rng_lbl, "mid")
            rng_cfg = CFG["ranges"][rng_key]
            target_price = pt_cfg["base_cost"] + rng_cfg["target_margin_per_unit"]
            st.caption(
                f"Cout de base : **{pt_cfg['base_cost']:,} $** | "
                f"Prix cible gamme : **{target_price:,} $** "
                f"(cout + {rng_cfg['target_margin_per_unit']:,} $)"
            )
            # Show target segments
            ts = ", ".join(
                CFG["segments"][s]["label"]
                for s in pt_cfg["target_segments"]
                if s in CFG["segments"]
            )
            st.caption(f"Segments naturels : {ts}")

        with col_pt2:
            # Product options in 2 sub-columns
            opts = CFG["product_options"]
            opt_keys = list(opts.keys())
            half = (len(opt_keys) + 1) // 2
            oc1, oc2 = st.columns(2)
            for i, opt_key in enumerate(opt_keys):
                opt_cfg = opts[opt_key]
                choices_labels = list(opt_cfg["choices"].keys())
                col = oc1 if i < half else oc2
                with col:
                    st.selectbox(
                        opt_cfg["label"],
                        choices_labels,
                        format_func=lambda k, cfg=opt_cfg: cfg["choices"][k]["label"],
                        key=f"{p}opt_{opt_key}",
                    )
            # Show options cost delta
            cost_d, price_d = _calc_options_delta(p)
            if cost_d > 0 or price_d > 0:
                st.caption(
                    f"Options selectionnees : +**{cost_d:,} $** au cout | "
                    f"+**{price_d:,} $** au prix suggere"
                )

        # ── Marketing ───────────────────────────────────────────────────────
        st.markdown("**Marketing**")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.number_input("Budget marketing total ($)", min_value=0.0, value=50000.0,
                            step=5000.0, key=f"{p}mkt_budget")
        with col_m2:
            adj = st.session_state.get(f"{p}adj_budget", 1_000_000.0)
            st.caption(f"Plafond : {adj * 0.15:,.0f} $ (15% du budget ajuste)")

        col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns(5)
        with col_c1:
            st.number_input("Digital ($)", min_value=0.0, value=0.0, step=1000.0, key=f"{p}ch_digital")
        with col_c2:
            st.number_input("Reseaux sociaux ($)", min_value=0.0, value=0.0, step=1000.0, key=f"{p}ch_social")
        with col_c3:
            st.number_input("Influenceurs ($)", min_value=0.0, value=0.0, step=1000.0, key=f"{p}ch_influencers")
        with col_c4:
            st.number_input("Affichage ($)", min_value=0.0, value=0.0, step=1000.0, key=f"{p}ch_display")
        with col_c5:
            st.number_input("Evenements ($)", min_value=0.0, value=0.0, step=1000.0, key=f"{p}ch_events")

        # ── R&D et Innovation ────────────────────────────────────────────────
        st.markdown("**R&D et Innovation**")
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            adj = st.session_state.get(f"{p}adj_budget", 1_000_000.0)
            st.number_input("Budget R&D ($)", min_value=0.0, value=0.0, step=5000.0, key=f"{p}rd_budget",
                            help=f"Plafond : {adj*0.08:,.0f} $ (8%)")
        with col_r2:
            st.number_input("Nombre de projets R&D", min_value=0, value=0, step=1, key=f"{p}rd_projects")
        with col_r3:
            st.checkbox("Lancement nouveau modele", key=f"{p}new_model")

        # ── Durabilite ───────────────────────────────────────────────────────
        st.markdown("**Durabilite**")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.number_input("Investissement durabilite ($)", min_value=0.0, value=0.0,
                            step=5000.0, key=f"{p}sustain_invest")
        with col_s2:
            st.number_input("Periodes d'investissement consecutives", min_value=0, value=0,
                            step=1, key=f"{p}sustain_periods")

        # ── Parametres commerciaux ──────────────────────────────────────────
        st.markdown("**Parametres commerciaux**")
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        with col_p1:
            # Suggest price from product type + range
            pt_key2 = PRODUCT_TYPE_OPTIONS.get(
                st.session_state.get(f"{p}product_type_lbl", DEFAULT_PRODUCT_TYPE_LABEL), "ville_quotidien"
            )
            rng_key2 = RANGE_OPTIONS.get(
                st.session_state.get(f"{p}range_lbl", DEFAULT_RANGE_LABEL), "mid"
            )
            _, price_d2 = _calc_options_delta(p)
            suggested_price = _default_price_for(pt_key2, rng_key2) + price_d2
            st.number_input(
                "Prix unitaire ($)", min_value=500.0, value=suggested_price,
                step=100.0, key=f"{p}price",
                help=f"Prix cible suggere : {suggested_price:,.0f} $ (cout + marge gamme + options)"
            )
        with col_p2:
            st.number_input("Taux de promotion (%)", min_value=-10.0, max_value=0.0,
                            value=0.0, step=1.0, key=f"{p}promo_rate",
                            help="Standard max : -5% | Liquidation max : -10%")
        with col_p3:
            st.number_input("Production (unites)", min_value=0, value=1000, step=100, key=f"{p}production")
        with col_p4:
            st.checkbox("Mode liquidation", key=f"{p}liquidation")

        # ── Contexte ─────────────────────────────────────────────────────────
        st.markdown("**Contexte (periode precedente)**")
        col_ctx1, col_ctx2, col_ctx3 = st.columns(3)
        with col_ctx1:
            st.slider("Score innovation precedent", 0.0, 10.0, 5.0, 0.1, key=f"{p}prev_innov")
        with col_ctx2:
            st.slider("Score durabilite precedent", 0.0, 10.0, 5.0, 0.1, key=f"{p}prev_sustain")
        with col_ctx3:
            seg_key2 = SEGMENT_OPTIONS.get(
                st.session_state.get(f"{p}segment_lbl", DEFAULT_SEGMENT_LABEL), "urbains_presses"
            )
            default_comp = CFG["default_competitor_attractiveness"].get(seg_key2, 12.0)
            st.number_input("Attractivite concurrents (segment)", min_value=0.1, value=default_comp,
                            step=0.5, key=f"{p}comp_attr")

        # ── Suivi des retraits (regles de jeu) ────────────────────────────────
        with st.expander("Suivi des retraits (regles de simulation)", expanded=False):
            wc1, wc2 = st.columns(2)
            with wc1:
                st.number_input(
                    "Retraits deja utilises (cumul)", min_value=0, max_value=4, value=0, step=1,
                    key=f"{p}total_withdrawals_used",
                    help="Regle : max 4 retraits sur toute la simulation",
                )
            with wc2:
                st.number_input(
                    "Derniere periode de retrait (0 = aucun)", min_value=0, max_value=8, value=0, step=1,
                    key=f"{p}last_withdrawal_period",
                    help="Regle : min 2 periodes entre deux retraits",
                )
            st.caption(
                f"Regle : max 4 retraits / simulation | max 1 retrait toutes les 2 periodes | "
                f"Production = 0 la periode suivant une liquidation"
            )


# ─── Results display ──────────────────────────────────────────────────────────

def display_results(
    scenario: ScenarioInput,
    result,
    show_export: bool = True,
    chart_key_prefix: str = "result",
):
    st.markdown("---")
    st.subheader("📊 Resultats")

    # KPI row 1
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Ventes", f"{result.sales:,} u.", delta=None)
    k2.metric("Chiffre d'affaires", fmt_cad(result.revenue))
    k3.metric("Profit", fmt_cad(result.profit))
    k4.metric(f"{color_margin(result.margin)} Marge", fmt_pct(result.margin))
    k5.metric("Part de marche", fmt_pct(result.market_share))

    # KPI row 2
    k6, k7, k8, k9, k10 = st.columns(5)
    k6.metric("PDM segment", fmt_pct(result.market_share_segment))
    k7.metric("Taux de service", fmt_pct(result.service_rate))
    k8.metric("Score innovation", f"{result.innovation_score:.1f}/10")
    k9.metric("Score durabilite", f"{result.sustainability_score:.1f}/10")
    valid_icon = "✅ Valide" if result.is_valid else "❌ Non valide"
    k10.metric("Statut", valid_icon)

    # Profit target zone indicator
    target_min = CFG["constraints"]["profit_target_min"]
    target_max = CFG["constraints"]["profit_target_max"]
    if result.revenue > 0:
        if target_min <= result.margin <= target_max:
            st.success(
                f"✅ Marge dans la zone cible ({target_min*100:.0f}%-{target_max*100:.0f}%) : {result.margin*100:.1f}%"
            )
        elif result.margin > target_max:
            st.info(
                f"📈 Marge au-dessus de la cible ({result.margin*100:.1f}% > {target_max*100:.0f}%) — "
                "excellent, mais verifiez si une reduction de prix augmenterait les parts de marche."
            )
        else:
            st.warning(
                f"⚠️ Marge sous la cible ({result.margin*100:.1f}% < {target_min*100:.0f}%) — "
                "zone cible : 5-10%."
            )

    # Production suggestion for next period
    next_prod = suggest_next_production(scenario, result)
    if next_prod == 0 and (scenario.liquidation or scenario.withdraw_model):
        st.error("🔴 Production periode suivante : **0 unite** (liquidation / retrait — regle obligatoire).")
    else:
        st.info(
            f"🔧 Production suggérée pour la periode suivante : **{next_prod:,} unites** "
            f"(basee sur demande estimee {result.demand:,.0f} u., taux de service {result.service_rate*100:.0f}%)"
        )

    # Waterfall
    st.subheader("Decomposition financiere")
    fig = _waterfall_chart(result)
    st.plotly_chart(fig, use_container_width=True, key=f"{chart_key_prefix}_waterfall")

    # Cost pie + detail table
    col_pie, col_cost = st.columns(2)
    with col_pie:
        fig2 = _cost_pie(result)
        st.plotly_chart(fig2, use_container_width=True, key=f"{chart_key_prefix}_cost_pie")

    with col_cost:
        st.markdown("**Detail des couts**")
        cost_df = pd.DataFrame({
            "Poste": [
                "Production", "Distribution", "Marketing", "R&D",
                "Exploitation", "SAV/Garantie", "Durabilite", "Total"
            ],
            "Montant ($)": [
                result.production_cost, result.distribution_cost,
                result.marketing_cost, result.rd_cost,
                result.operating_cost, result.aftersales_cost,
                result.sustainability_cost, result.total_cost,
            ],
            "% CA": [
                f"{v/max(result.revenue,1)*100:.1f}%"
                for v in [
                    result.production_cost, result.distribution_cost,
                    result.marketing_cost, result.rd_cost,
                    result.operating_cost, result.aftersales_cost,
                    result.sustainability_cost, result.total_cost,
                ]
            ],
        })
        cost_df["Montant ($)"] = cost_df["Montant ($)"].apply(lambda x: f"{x:,.0f}")
        st.dataframe(cost_df, use_container_width=True, hide_index=True)

    # Alerts
    if result.alerts:
        st.subheader("⚠️ Alertes")
        for a in result.alerts:
            st.warning(a)

    # Interpretations
    st.subheader("💡 Interpretation automatique")
    for i in result.interpretations:
        st.info(i)

    # Improvement plan
    st.subheader("🧭 Plan d'amelioration conseille")
    for step in _build_improvement_plan(scenario, result):
        st.write(f"- {step}")

    # Save
    if st.button("💾 Enregistrer dans l'historique", key=f"save_{id(result)}"):
        rec_id = save_scenario(scenario, result)
        st.success(f"Scenario enregistre (ID : {rec_id})")

    # Export
    if show_export:
        st.subheader("📥 Export du rapport")
        ex1, ex2, ex3, ex4 = st.columns(4)
        with ex1:
            md_content = generate_markdown_report(scenario, result)
            st.download_button(
                "📄 Markdown",
                data=md_content.encode("utf-8"),
                file_name=f"rapport_{result.scenario_name.replace(' ','_')}.md",
                mime="text/markdown",
                key=f"download_md_{id(result)}",
            )
        with ex2:
            json_content = generate_json_report(scenario, result)
            st.download_button(
                "📋 JSON",
                data=json_content.encode("utf-8"),
                file_name=f"rapport_{result.scenario_name.replace(' ','_')}.json",
                mime="application/json",
                key=f"download_json_{id(result)}",
            )
        with ex3:
            try:
                word_bytes = generate_word_report(scenario, result)
                st.download_button(
                    "📝 Word",
                    data=word_bytes,
                    file_name=f"rapport_{result.scenario_name.replace(' ','_')}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"download_word_{id(result)}",
                )
            except Exception as e:
                st.caption(f"Word : {e}")
        with ex4:
            try:
                pdf_bytes = generate_pdf_report(scenario, result)
                st.download_button(
                    "📑 PDF",
                    data=pdf_bytes,
                    file_name=f"rapport_{result.scenario_name.replace(' ','_')}.pdf",
                    mime="application/pdf",
                    key=f"download_pdf_{id(result)}",
                )
            except Exception as e:
                st.caption(f"PDF : {e}")


# ─── Charts ───────────────────────────────────────────────────────────────────

def _waterfall_chart(result):
    items = [
        ("CA", result.revenue, "relative"),
        ("- Production", -result.production_cost, "relative"),
        ("- Distribution", -result.distribution_cost, "relative"),
        ("- Marketing", -result.marketing_cost, "relative"),
        ("- R&D", -result.rd_cost, "relative"),
        ("- Exploitation", -result.operating_cost, "relative"),
        ("- SAV", -result.aftersales_cost, "relative"),
        ("- Durabilite", -result.sustainability_cost, "relative"),
        ("Profit", result.profit, "total"),
    ]
    labels = [i[0] for i in items]
    values = [i[1] for i in items]
    measures = [i[2] for i in items]

    fig = go.Figure(go.Waterfall(
        name="",
        orientation="v",
        measure=measures,
        x=labels,
        y=values,
        textposition="outside",
        text=[f"{v:,.0f} $" for v in values],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#2ecc71"}},
        decreasing={"marker": {"color": "#e74c3c"}},
        totals={"marker": {"color": "#3498db"}},
    ))
    fig.update_layout(
        title="Decomposition du profit (CAD)",
        showlegend=False,
        height=400,
    )
    return fig


def _cost_pie(result):
    labels = ["Production", "Distribution", "Marketing", "R&D", "Exploitation", "SAV", "Durabilite"]
    values = [
        result.production_cost, result.distribution_cost,
        result.marketing_cost, result.rd_cost,
        result.operating_cost, result.aftersales_cost,
        result.sustainability_cost,
    ]
    fig = px.pie(
        names=labels,
        values=values,
        title="Repartition des couts",
        hole=0.3,
    )
    fig.update_layout(height=350)
    return fig


def _radar_chart(results, names):
    categories = ["Marge", "PDM", "Service", "Innovation", "Durabilite"]
    fig = go.Figure()
    for res, name in zip(results, names):
        fig.add_trace(go.Scatterpolar(
            r=[
                min(res.margin * 500, 100),
                res.market_share * 1000,
                res.service_rate * 100,
                res.innovation_score * 10,
                res.sustainability_score * 10,
            ],
            theta=categories,
            fill="toself",
            name=name,
        ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="Comparaison des scenarios (radar)",
        height=450,
    )
    return fig


# ─── Market overview panel ────────────────────────────────────────────────────

def _show_market_overview():
    """Show a compact market size table in the sidebar."""
    with st.sidebar.expander("📈 Marche VAE Canada", expanded=False):
        rows = []
        for p in [1, 3, 5, 9, 10, 15]:
            rows.append({
                "Periode": p,
                "Annee": period_to_year(p),
                "Marche (unites)": f"{total_market_size(p):,.0f}",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("Phase 1 (P1-9) : +15%/an | Phase 2 (P10-15) : +17.5%/an")


# ─── Pages ────────────────────────────────────────────────────────────────────

def page_single_simulation():
    st.title("🔬 Simulation directe")
    st.caption("Saisissez les parametres d'un scenario et lancez la simulation.")

    scenario_form(key_prefix="s1_")

    if st.button("▶️ Simuler", type="primary", use_container_width=True):
        try:
            scenario = build_scenario_from_form("s1_")
            with st.spinner("Simulation en cours..."):
                result = simulate(scenario)
            st.session_state["last_scenario"] = scenario
            st.session_state["last_result"] = result
        except Exception as e:
            st.error(f"Erreur lors de la simulation : {e}")
            return

    if "last_result" in st.session_state:
        display_results(
            st.session_state["last_scenario"],
            st.session_state["last_result"],
            chart_key_prefix="single_last",
        )


def page_multi_scenario():
    st.title("📊 Comparaison multi-scenarios")
    st.caption("Definissez jusqu'a 4 scenarios et comparez leurs performances.")

    n_scenarios = st.number_input("Nombre de scenarios a comparer", min_value=2, max_value=4, value=2, step=1)

    tabs = st.tabs([f"Scenario {i+1}" for i in range(n_scenarios)])
    for i, tab in enumerate(tabs):
        with tab:
            scenario_form(key_prefix=f"ms{i+1}_", title=f"Parametres scenario {i+1}")

    if st.button("▶️ Comparer tous les scenarios", type="primary", use_container_width=True):
        scenarios = []
        results = []
        errors = []
        for i in range(n_scenarios):
            try:
                s = build_scenario_from_form(f"ms{i+1}_")
                scenarios.append(s)
                results.append(simulate(s))
            except Exception as e:
                errors.append(f"Scenario {i+1} : {e}")

        if errors:
            for err in errors:
                st.error(err)
            return

        st.session_state["multi_scenarios"] = scenarios
        st.session_state["multi_results"] = results

    if "multi_results" in st.session_state:
        scenarios = st.session_state["multi_scenarios"]
        results = st.session_state["multi_results"]
        names = [r.scenario_name for r in results]

        st.markdown("---")
        st.subheader("Tableau comparatif")

        comp_df = pd.DataFrame({
            "Scenario": names,
            "Ventes": [r.sales for r in results],
            "CA ($)": [f"{r.revenue:,.0f}" for r in results],
            "Profit ($)": [f"{r.profit:,.0f}" for r in results],
            "Marge (%)": [f"{r.margin*100:.1f}%" for r in results],
            "PDM (%)": [f"{r.market_share*100:.2f}%" for r in results],
            "Taux service": [f"{r.service_rate*100:.1f}%" for r in results],
            "Innovation": [f"{r.innovation_score:.1f}/10" for r in results],
            "Durabilite": [f"{r.sustainability_score:.1f}/10" for r in results],
            "Valide": ["✅" if r.is_valid else "❌" for r in results],
        })
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

        best_profit = max(range(len(results)), key=lambda i: results[i].profit)
        best_margin = max(range(len(results)), key=lambda i: results[i].margin)
        best_pdm = max(range(len(results)), key=lambda i: results[i].market_share)

        st.success(
            f"🏆 **Meilleur profit** : {names[best_profit]}  |  "
            f"**Meilleure marge** : {names[best_margin]}  |  "
            f"**Meilleure PDM** : {names[best_pdm]}"
        )

        st.plotly_chart(
            _radar_chart(results, names),
            use_container_width=True,
            key="multi_radar_chart",
        )

        metric = st.selectbox(
            "Metrique a visualiser",
            ["Profit ($)", "Marge (%)", "Ventes", "PDM (%)"],
            key="multi_metric_sel",
        )
        metric_map = {
            "Profit ($)": [r.profit for r in results],
            "Marge (%)": [r.margin * 100 for r in results],
            "Ventes": [r.sales for r in results],
            "PDM (%)": [r.market_share * 100 for r in results],
        }
        fig_bar = px.bar(
            x=names,
            y=metric_map[metric],
            labels={"x": "Scenario", "y": metric},
            title=f"Comparaison — {metric}",
            color=names,
        )
        st.plotly_chart(fig_bar, use_container_width=True, key="multi_metric_bar")

        st.subheader("Details par scenario")
        for i, (sc, res) in enumerate(zip(scenarios, results)):
            with st.expander(f"Details — {res.scenario_name}", expanded=False):
                display_results(sc, res, show_export=True, chart_key_prefix=f"multi_detail_{i}")

        st.subheader("📥 Export global multi-scenarios")
        try:
            multi_pdf_bytes = generate_multi_pdf_report(scenarios, results)
            st.download_button(
                "📑 PDF global (tous les scenarios)",
                data=multi_pdf_bytes,
                file_name="rapport_multi_scenarios.pdf",
                mime="application/pdf",
                key="download_multi_pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"Impossible de generer le PDF global : {e}")


def page_objective_mode():
    st.title("🎯 Mode objectif cible (simulation inverse)")
    st.caption(
        "Definissez un scenario de base et un objectif. "
        "Le bot recherche automatiquement les parametres optimaux pour atteindre cet objectif."
    )

    with st.expander("Scenario de base", expanded=True):
        scenario_form(key_prefix="opt_")

    st.markdown("---")
    st.subheader("Definir l'objectif")

    col_obj1, col_obj2, col_obj3 = st.columns(3)
    with col_obj1:
        metric_label = st.selectbox(
            "Metrique cible",
            list(SUPPORTED_METRICS.values()),
            key="opt_metric_lbl",
        )
        metric_key = [k for k, v in SUPPORTED_METRICS.items() if v == metric_label][0]

    with col_obj2:
        if metric_key in ("margin", "market_share", "market_share_segment"):
            target_raw = st.number_input(
                "Valeur cible (%)",
                min_value=0.0, max_value=100.0, value=10.0, step=0.5,
                key="opt_target_pct",
            )
            target_value = target_raw / 100.0
        elif metric_key in ("innovation_score", "sustainability_score"):
            target_value = st.number_input(
                "Valeur cible (/10)",
                min_value=0.0, max_value=10.0, value=7.0, step=0.1,
                key="opt_target_score",
            )
        else:
            target_value = st.number_input(
                "Valeur cible ($)",
                min_value=0.0, value=100000.0, step=10000.0,
                key="opt_target_cad",
            )

    with col_obj3:
        tolerance = st.slider("Tolerance (%)", 1, 20, 5, key="opt_tolerance") / 100.0
        max_iter = st.select_slider("Precision", [100, 200, 300, 500], value=300, key="opt_maxiter")
        if st.button("🎯 Objectif rapide 8% profit", key="opt_quick_8"):
            st.session_state["opt_metric_lbl"] = SUPPORTED_METRICS["margin"]
            st.session_state["opt_target_pct"] = 8.0

    if st.button("🔍 Rechercher les parametres optimaux", type="primary", use_container_width=True):
        try:
            base_scenario = build_scenario_from_form("opt_")
        except Exception as e:
            st.error(f"Erreur dans le scenario de base : {e}")
            return

        with st.spinner("Optimisation en cours... (peut prendre quelques secondes)"):
            opt_result = find_parameters_for_target(
                base_scenario=base_scenario,
                target_metric=metric_key,
                target_value=target_value,
                tolerance=tolerance,
                max_iter=max_iter,
            )
        st.session_state["opt_result"] = opt_result
        st.session_state["opt_base"] = base_scenario

    if "opt_result" in st.session_state:
        opt = st.session_state["opt_result"]

        st.markdown("---")
        if opt.success:
            st.success(opt.message)
        else:
            st.warning(opt.message)

        st.subheader("📋 Explication")
        for line in opt.explanation:
            st.write(line)

        st.subheader("Parametres recommandes vs base")
        base = st.session_state["opt_base"]
        rec = opt.recommended_scenario
        param_df = pd.DataFrame({
            "Parametre": ["Budget marketing ($)", "Budget R&D ($)", "Prix ($)", "Production (u.)"],
            "Base": [
                f"{base.marketing_budget:,.0f}",
                f"{base.rd_budget:,.0f}",
                f"{base.price:,.0f}",
                f"{base.production:,}",
            ],
            "Recommande": [
                f"{rec.marketing_budget:,.0f}",
                f"{rec.rd_budget:,.0f}",
                f"{rec.price:,.0f}",
                f"{rec.production:,}",
            ],
        })
        st.dataframe(param_df, use_container_width=True, hide_index=True)

        with st.expander("Resultats detailles du scenario optimal", expanded=True):
            display_results(
                rec,
                opt.simulation_result,
                show_export=True,
                chart_key_prefix="objective_optimal",
            )


def page_history():
    st.title("📁 Historique des scenarios")

    df = get_summary_df()
    if df.empty:
        st.info("Aucun scenario enregistre. Lancez une simulation et cliquez sur 'Enregistrer dans l'historique'.")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)

    if len(df) >= 2:
        st.subheader("Evolution dans le temps")
        metric_h = st.selectbox("Metrique", ["Profit ($)", "Marge (%)", "PDM (%)"], key="hist_metric")
        col_map = {"Profit ($)": "Profit ($)", "Marge (%)": "Marge (%)", "PDM (%)": "PDM (%)"}
        fig_trend = px.line(
            df, x="Date", y=col_map[metric_h], color="Scenario",
            markers=True, title=f"Evolution — {metric_h}",
        )
        st.plotly_chart(fig_trend, use_container_width=True, key="history_trend_chart")

    if st.button("🗑️ Effacer tout l'historique", type="secondary"):
        clear_history()
        st.success("Historique efface.")
        st.rerun()


# ─── Marché complet — analyse concurrentielle ────────────────────────────────

def _color_firm(firm: str, user_firm: Optional[str]) -> str:
    return "#f97316" if firm == user_firm else "#6366f1"


def _full_market_ranking_table(firms_data: dict, user_firm: Optional[str]) -> pd.DataFrame:
    rows = []
    for rank, (firm, d) in enumerate(
        sorted(firms_data.items(), key=lambda x: -x[1]["market_share"]), start=1
    ):
        marg = d["margin_estimate"]
        marg_icon = "🟢" if marg >= 0.05 else ("🟡" if marg >= 0.02 else "🔴")
        rows.append({
            "Rang": rank,
            "Firme": f"⭐ {firm}" if firm == user_firm else firm,
            "PDM (%)": f"{d['market_share']*100:.1f}%",
            "Ventes (u.)": f"{d['total_sales']:,}",
            "CA estime ($)": f"{d['total_revenue']:,.0f}",
            "Profit estime ($)": f"{d['profit_estimate']:,.0f}",
            f"Marge": f"{marg_icon} {marg*100:.1f}%",
        })
    return pd.DataFrame(rows)


def _display_full_market_period(mkt: dict):
    """Display one-period full-market result."""
    user_firm = mkt.get("user_firm")
    firms_data = mkt["firms"]
    seg_labels = {k: v["label"] for k, v in CFG["segments"].items()}

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_mkt = mkt["total_market"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Marche total", f"{total_mkt:,.0f} unites")
    if user_firm and user_firm in firms_data:
        ud = firms_data[user_firm]
        rank = sorted(firms_data, key=lambda f: -firms_data[f]["market_share"]).index(user_firm) + 1
        m2.metric(f"{user_firm} — PDM", f"{ud['market_share']*100:.1f}%", delta=f"Rang {rank}/9")
        m3.metric(f"{user_firm} — CA", f"{ud['total_revenue']:,.0f} $")
        m4.metric(f"{user_firm} — Marge est.", f"{ud['margin_estimate']*100:.1f}%")

    st.markdown("---")

    # ── Classement ────────────────────────────────────────────────────────────
    st.subheader("📋 Classement des firmes")
    df_rank = _full_market_ranking_table(firms_data, user_firm)
    st.dataframe(df_rank, use_container_width=True, hide_index=True)

    # ── Charts: PDM pie + CA bar ───────────────────────────────────────────────
    col_pie, col_bar = st.columns(2)
    sorted_firms = sorted(firms_data.items(), key=lambda x: -x[1]["market_share"])

    with col_pie:
        fig_pie = go.Figure(go.Pie(
            labels=[f[0] for f in sorted_firms],
            values=[f[1]["market_share"] * 100 for f in sorted_firms],
            marker_colors=[_color_firm(f[0], user_firm) for f in sorted_firms],
            hole=0.35,
            textinfo="label+percent",
        ))
        fig_pie.update_layout(title="Parts de marche totales (%)", height=370, showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True, key="fm_pie")

    with col_bar:
        sorted_ca = sorted(firms_data.items(), key=lambda x: -x[1]["total_revenue"])
        fig_bar = go.Figure(go.Bar(
            x=[f[0] for f in sorted_ca],
            y=[f[1]["total_revenue"] for f in sorted_ca],
            marker_color=[_color_firm(f[0], user_firm) for f in sorted_ca],
            text=[f"{f[1]['total_revenue']/1e6:.1f}M$" for f in sorted_ca],
            textposition="outside",
        ))
        fig_bar.update_layout(title="CA estime par firme ($)", height=370, showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True, key="fm_bar")

    # ── Segment heatmap ────────────────────────────────────────────────────────
    st.subheader("🗺️ PDM par segment x firme (%)")
    seg_keys = list(mkt["segment_breakdown"].keys())
    firm_keys = [f[0] for f in sorted(firms_data.items(), key=lambda x: -x[1]["market_share"])]

    heatmap_rows = []
    for seg_key in seg_keys:
        row = {"Segment": seg_labels.get(seg_key, seg_key)}
        leader = mkt["segment_leaders"].get(seg_key, "")
        for fk in firm_keys:
            share_pct = mkt["segment_breakdown"][seg_key].get(fk, {}).get("segment_share", 0) * 100
            row[fk] = round(share_pct, 1)
        row["Leader"] = leader
        heatmap_rows.append(row)

    df_heat = pd.DataFrame(heatmap_rows).set_index("Segment")
    # Highlight user firm column
    numeric_cols = [c for c in df_heat.columns if c != "Leader"]
    st.dataframe(
        df_heat[numeric_cols].style.format("{:.1f}%"),
        use_container_width=True,
    )

    # Leader summary
    st.caption("**Leaders par segment :** " + " | ".join(
        f"{seg_labels.get(sk, sk)}: **{ldr}**"
        for sk, ldr in mkt["segment_leaders"].items()
    ))


def _display_full_market_evolution(all_periods: list, user_firm: Optional[str]):
    """Display PDM and revenue evolution across all 8 periods."""
    seg_labels = {k: v["label"] for k, v in CFG["segments"].items()}
    years = [p["year"] for p in all_periods]
    firm_keys = list(all_periods[0]["firms"].keys())

    st.subheader("📈 Evolution des parts de marche sur 8 periodes")

    # PDM evolution line chart
    fig_evo = go.Figure()
    for firm in firm_keys:
        pdm_series = [p["firms"][firm]["market_share"] * 100 for p in all_periods]
        fig_evo.add_trace(go.Scatter(
            x=years, y=pdm_series, name=firm, mode="lines+markers",
            line=dict(width=3 if firm == user_firm else 1.5,
                      color="#f97316" if firm == user_firm else None),
        ))
    fig_evo.update_layout(
        title="PDM totale par firme (%)", height=420,
        xaxis_title="Annee", yaxis_title="PDM (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_evo, use_container_width=True, key="fm_evo_pdm")

    # Market size + total revenue evolution
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        mkt_sizes = [p["total_market"] for p in all_periods]
        fig_mkt = go.Figure(go.Bar(x=years, y=mkt_sizes, marker_color="#6366f1",
                                   text=[f"{v/1000:.0f}k" for v in mkt_sizes],
                                   textposition="outside"))
        fig_mkt.update_layout(title="Taille totale du marche (unites)", height=320)
        st.plotly_chart(fig_mkt, use_container_width=True, key="fm_evo_mkt")

    with col_e2:
        if user_firm:
            rev_series = [p["firms"][user_firm]["total_revenue"] for p in all_periods]
            margin_series = [p["firms"][user_firm]["margin_estimate"] * 100 for p in all_periods]
            fig_rev = go.Figure()
            fig_rev.add_trace(go.Bar(x=years, y=rev_series, name="CA ($)", yaxis="y1",
                                     marker_color="#f97316", opacity=0.75))
            fig_rev.add_trace(go.Scatter(x=years, y=margin_series, name="Marge est. (%)",
                                         yaxis="y2", line=dict(color="#10b981", width=2.5),
                                         mode="lines+markers"))
            fig_rev.update_layout(
                title=f"{user_firm} — CA et marge sur 8 periodes",
                yaxis=dict(title="CA ($)"),
                yaxis2=dict(title="Marge (%)", overlaying="y", side="right",
                            range=[0, max(margin_series) * 1.5 + 1]),
                height=320,
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_rev, use_container_width=True, key="fm_evo_rev")

    # Segment dominance over time for user firm
    if user_firm:
        st.subheader(f"🎯 Position de {user_firm} par segment (PDM %)")
        seg_evo_rows = []
        for p in all_periods:
            row = {"Annee": p["year"]}
            for seg_key in CFG["segments"]:
                seg_share = p["firms"][user_firm]["segments"].get(seg_key, {}).get("share", 0)
                row[seg_labels.get(seg_key, seg_key)] = round(seg_share * 100, 1)
            seg_evo_rows.append(row)
        df_seg_evo = pd.DataFrame(seg_evo_rows).set_index("Annee")
        st.dataframe(
            df_seg_evo.style.format("{:.1f}%"),
            use_container_width=True,
        )


def page_full_market():
    st.title("🌍 Analyse du marche complet")
    st.caption(
        "9 firmes · 6 segments · 8 periodes — Votre strategie (prix, gamme, marketing) "
        "s'applique a l'ensemble du marche."
    )

    # ── Configuration ────────────────────────────────────────────────────────
    with st.expander("⚙️ Configuration", expanded=True):
        col_m1, col_m2 = st.columns([1, 3])
        with col_m1:
            mode = st.radio(
                "Mode",
                ["🏢 Ma firme", "🔭 Neutre"],
                key="fm_mode",
            )
        with col_m2:
            view = st.radio(
                "Vue",
                ["📊 Periode unique", "📈 Evolution 8 periodes"],
                horizontal=True,
                key="fm_view",
            )

        user_firm = None
        user_scenario = None

        if mode == "🏢 Ma firme":
            st.markdown("---")
            cf1, cf2, cf3, cf4, cf5 = st.columns(5)
            with cf1:
                user_firm = st.selectbox("Firme", FIRM_OPTIONS,
                                         index=FIRM_OPTIONS.index("TRE"), key="fm_firm")
            with cf2:
                fm_rng_lbl = st.selectbox("Gamme", list(RANGE_OPTIONS.keys()),
                                          index=1, key="fm_range")
                fm_rng_key = RANGE_OPTIONS[fm_rng_lbl]
            with cf3:
                bounds = CFG["ranges"][fm_rng_key]["price_range"]
                fm_price = st.slider("Prix ($)",
                                     int(bounds[0] * 0.80), int(bounds[1] * 1.20),
                                     int(sum(bounds) / 2), step=50, key="fm_price")
            with cf4:
                fm_mkt = st.slider("Budget marketing ($)",
                                   0, 500_000, 80_000, step=5_000, key="fm_mkt")
            with cf5:
                fm_promo = st.slider("Promotion (%)", -10.0, 0.0, 0.0,
                                     step=1.0, key="fm_promo")

            fm_adj = max(CFG["firms"][user_firm]["units_ref"] * float(fm_price), 100_000.0)

            # Shared template — period overridden per-period in all_periods mode
            user_scenario = ScenarioInput(
                firm_name=user_firm,
                period=1,
                scenario_name=f"{user_firm} marche complet",
                model_name=f"{user_firm} modele",
                segment="urbains_presses",   # overridden per segment inside simulate_full_market
                model_range=fm_rng_key,
                product_status="active",
                price=float(fm_price),
                production=CFG["firms"][user_firm]["units_ref"],
                marketing_budget=float(fm_mkt),
                adjusted_budget=fm_adj,
                promotion_rate=float(fm_promo) / 100.0,
                previous_innovation_score=CFG["firms"][user_firm].get("base_rep", 5.0),
            )

        if view == "📊 Periode unique":
            period = st.selectbox("Periode", list(range(1, 9)), key="fm_period_single")
        else:
            period = None  # will run all 8

    # ── Simulation ────────────────────────────────────────────────────────────
    btn_label = "📊 Analyser cette periode" if view == "📊 Periode unique" else "📈 Analyser les 8 periodes"
    if st.button(btn_label, type="primary", key="fm_run"):
        if view == "📊 Periode unique":
            with st.spinner(f"Simulation P{period} — 9 firmes x 6 segments..."):
                if user_scenario:
                    scenario_p = user_scenario.model_copy(update={"period": period})
                else:
                    scenario_p = None
                mkt = simulate_full_market(period, user_firm, scenario_p)
            st.subheader(f"Periode {mkt['period']} — Annee {mkt['year']}")
            _display_full_market_period(mkt)

        else:
            with st.spinner("Simulation 8 periodes x 9 firmes x 6 segments..."):
                all_periods = simulate_full_market_all_periods(user_firm, user_scenario)
            st.subheader(f"Marche complet — 2027 a 2034")
            # Show final period ranking
            st.markdown("**Classement final (Periode 8 — 2034)**")
            df_final = _full_market_ranking_table(all_periods[-1]["firms"], user_firm)
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            st.markdown("---")
            _display_full_market_evolution(all_periods, user_firm)


# ─── Calculateur rapide (React embarque) ──────────────────────────────────────

def page_calculateur():
    st.title("🧮 Calculateur rapide")
    st.caption(
        "Outil de decision instantane : ajustez les sliders et observez les resultats en temps reel. "
        "Aucune simulation complete necessaire."
    )

    html_path = pathlib.Path(__file__).parent / "calculateur.html"
    if not html_path.exists():
        st.error(
            "Fichier calculateur.html introuvable. "
            "Assurez-vous qu'il est present a la racine du projet."
        )
        return

    html_content = html_path.read_text(encoding="utf-8")

    # Supprimer le header et le body wrapper pour l'integration dans Streamlit
    # On embarque uniquement le contenu utile dans un iframe via components.html
    components.html(html_content, height=820, scrolling=True)


def page_action_plan_2026():
    st.title("🧭 Plan d'action 2026")
    st.caption(
        "Execution automatique du plan : promos, rendement marketing, multi-marches "
        "et comparaison des politiques de renouvellement."
    )

    with st.expander("Scenario de reference", expanded=True):
        scenario_form(key_prefix="plan_")

    if st.button("▶️ Executer le plan complet", type="primary", use_container_width=True):
        try:
            base = build_scenario_from_form("plan_")
            with st.spinner("Execution des scenarios en cours..."):
                runs = execute_plan_matrix(base)
            df = runs_to_dataframe(runs)
            cmp_df = compare_policies(df)
        except Exception as e:
            st.error(f"Erreur lors de l'execution du plan : {e}")
            return

        st.session_state["plan_runs_df"] = df
        st.session_state["plan_cmp_df"] = cmp_df

    if "plan_runs_df" in st.session_state:
        df = st.session_state["plan_runs_df"]
        cmp_df = st.session_state["plan_cmp_df"]

        st.subheader("KPI scenarios")
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("Comparaison politique A vs B")
        st.dataframe(cmp_df, use_container_width=True, hide_index=True)

        best_policy = cmp_df.iloc[0]["Politique"] if not cmp_df.empty else "N/A"
        st.success(f"Politique recommandee : **{best_policy}** (meilleur couple profit/indice 2026).")


def page_auto_scenarios():
    st.title("🧪 Scenarios automatiques")
    st.caption("Lance 6 scenarios tests, compare les resultats et affiche alertes + recommandations.")

    with st.expander("Scenario de base", expanded=True):
        scenario_form(key_prefix="auto_")

    if st.button("🚀 Lancer scenarios test", type="primary", use_container_width=True):
        try:
            base = build_scenario_from_form("auto_")
            outputs = run_all_scenarios(base)
            cmp_rows = compare_auto_scenarios(outputs)
            promo_tests = run_promo_sales_test(base)
            mkt_tests = run_marketing_short_term_test(base)
            full_market = run_full_market_simulation(base.firm_name, base)
        except Exception as e:
            st.error(f"Erreur execution scenarios automatiques: {e}")
            return

        st.session_state["auto_outputs"] = outputs
        st.session_state["auto_cmp_rows"] = cmp_rows
        st.session_state["auto_promo_tests"] = promo_tests
        st.session_state["auto_mkt_tests"] = mkt_tests
        st.session_state["auto_full_market"] = full_market

    if "auto_cmp_rows" in st.session_state:
        cmp_df = pd.DataFrame(st.session_state["auto_cmp_rows"])
        st.subheader("Comparateur de scenarios")
        st.dataframe(cmp_df, use_container_width=True, hide_index=True)

        if not cmp_df.empty:
            best_profit = cmp_df.loc[cmp_df["Profit ($)"].idxmax(), "Scenario"]
            best_profit_rate = cmp_df.loc[cmp_df["Profit rate (%)"].idxmax(), "Scenario"]
            st.success(f"🏆 Meilleur scenario profit: **{best_profit}** | profit_rate: **{best_profit_rate}**")

        st.subheader("Alertes metier")
        for out in st.session_state["auto_outputs"]:
            if out["alerts"]:
                with st.expander(f"Alertes - {out['scenario']}", expanded=False):
                    for alert in out["alerts"][:8]:
                        st.warning(alert)

        st.subheader("Recommandations")
        for out in st.session_state["auto_outputs"]:
            recs = generate_recommendations(out["result"])
            with st.expander(f"Recommandations - {out['scenario']}", expanded=False):
                for rec in recs:
                    st.write(f"- {rec}")

        st.subheader("Test promo (0, -5, -10)")
        promo_df = pd.DataFrame([{
            "Label": r.label, "Ventes": r.sales, "Profit ($)": r.profit
        } for r in st.session_state["auto_promo_tests"] if r.label in ("Taux promotion valide.",)])
        st.dataframe(promo_df, use_container_width=True, hide_index=True)

        st.subheader("Test marketing (0% -> 10%)")
        mkt_df = pd.DataFrame([{
            "Step": r.label,
            "Ventes": r.sales,
            "Profit ($)": r.profit,
            "Profit rate (%)": r.margin * 100,
            "Efficacite marketing": r.marketing_efficiency,
        } for r in st.session_state["auto_mkt_tests"]])
        st.dataframe(mkt_df, use_container_width=True, hide_index=True)

        if not mkt_df.empty:
            best_roi_idx = mkt_df["Efficacite marketing"].idxmax()
            best_step = mkt_df.loc[best_roi_idx, "Step"]
            st.info(f"ROI marketing optimal detecte sur: **{best_step}**")

        st.subheader("Simulation globale (stabilite)")
        full = st.session_state["auto_full_market"]
        final = full[-1]
        total_market = final["total_market"]
        total_sales = sum(f["total_sales"] for f in final["firms"].values())
        coherence_gap = abs(total_sales - total_market)
        st.write(
            f"- Periodes simulees: **{len(full)}** | Marche final: **{total_market:,.0f}** | "
            f"Ventes totales firmes: **{total_sales:,.0f}** | Ecart coherence: **{coherence_gap:,.0f}**"
        )


# ─── Sidebar helpers: analyses, conseils, export ─────────────────────────────

PAGE_ANALYSES = {
    "🔬 Simulation directe": "Analyse un scenario en profondeur (KPI, couts, alertes, plan d'action).",
    "📊 Multi-scenarios": "Compare plusieurs strategies et identifie le meilleur compromis profit/marge/PDM.",
    "🎯 Objectif cible": "Recherche automatiquement les parametres qui atteignent une cible metier.",
    "🧪 Scenarios automatiques": "Lance des tests pedagogiques pour valider les regles metier et les sensibilites.",
    "🧭 Plan d'action 2026": "Evalue un plan multi-tests et compare les politiques de decision.",
    "🌍 Marche complet": "Observe la concurrence globale (9 firmes, 6 segments) et l'evolution sur 8 periodes.",
    "🧮 Calculateur rapide": "Simule rapidement des hypothese sans lancer une simulation complete.",
    "📁 Historique": "Suit la performance des scenarios enregistres dans le temps.",
}

PAGE_TIPS = {
    "🔬 Simulation directe": [
        "Validez d'abord la marge (>=2%), puis optimisez la part de marche.",
        "Ajustez 1-2 variables a la fois pour isoler les effets.",
    ],
    "📊 Multi-scenarios": [
        "Conservez une base commune pour comparer proprement les scenarios.",
        "Ne retenez pas seulement le profit: regardez aussi service et robustesse.",
    ],
    "🎯 Objectif cible": [
        "Fixez une tolerance realiste (5-10%) pour converger plus vite.",
        "Verifiez que la solution recommandee reste conforme aux contraintes metier.",
    ],
    "🧪 Scenarios automatiques": [
        "Utilisez cette vue pour detecter rapidement les zones de risque.",
        "Appuyez vos decisions sur les recommandations par scenario.",
    ],
    "🧭 Plan d'action 2026": [
        "Comparez les politiques par couple profit/indice pour un choix robuste.",
        "Rejouez le plan apres chaque ajustement important du scenario de base.",
    ],
    "🌍 Marche complet": [
        "Testez plusieurs niveaux de prix pour mesurer la reaction concurrentielle.",
        "Surveillez votre rang et votre marge sur toute la trajectoire 8 periodes.",
    ],
    "🧮 Calculateur rapide": [
        "Utilisez cette vue pour pre-qualifier des hypotheses avant simulation detaillee.",
        "Confirmez ensuite les decisions avec Simulation directe ou Multi-scenarios.",
    ],
    "📁 Historique": [
        "Reperez les tendances de marge et PDM avant de changer la strategie.",
        "Nettoyez les scenarios obsoletes pour garder un historique lisible.",
    ],
}


def _sidebar_pdf_export_for_page(page: str):
    st.markdown("**Rapport PDF**")
    try:
        if page == "🔬 Simulation directe":
            scenario = st.session_state.get("last_scenario")
            result = st.session_state.get("last_result")
            if scenario and result:
                pdf_bytes = generate_pdf_report(scenario, result)
                st.download_button(
                    "📑 Exporter PDF (simulation)",
                    data=pdf_bytes,
                    file_name=f"rapport_{result.scenario_name.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    key="sidebar_pdf_single",
                    use_container_width=True,
                )
            else:
                st.caption("Lancez une simulation pour activer l'export PDF.")

        elif page == "📊 Multi-scenarios":
            scenarios = st.session_state.get("multi_scenarios", [])
            results = st.session_state.get("multi_results", [])
            if scenarios and results:
                pdf_bytes = generate_multi_pdf_report(scenarios, results)
                st.download_button(
                    "📑 Exporter PDF global",
                    data=pdf_bytes,
                    file_name="rapport_multi_scenarios.pdf",
                    mime="application/pdf",
                    key="sidebar_pdf_multi",
                    use_container_width=True,
                )
            else:
                st.caption("Lancez la comparaison pour activer l'export PDF.")

        elif page == "🎯 Objectif cible":
            opt = st.session_state.get("opt_result")
            if opt and getattr(opt, "recommended_scenario", None) and getattr(opt, "simulation_result", None):
                pdf_bytes = generate_pdf_report(opt.recommended_scenario, opt.simulation_result)
                st.download_button(
                    "📑 Exporter PDF (objectif)",
                    data=pdf_bytes,
                    file_name=f"rapport_objectif_{opt.simulation_result.scenario_name.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    key="sidebar_pdf_objective",
                    use_container_width=True,
                )
            else:
                st.caption("Lancez une optimisation pour activer l'export PDF.")

        elif page == "🧪 Scenarios automatiques":
            outputs = st.session_state.get("auto_outputs", [])
            if outputs:
                scenarios = [o["scenario_input"] for o in outputs if "scenario_input" in o and "result" in o]
                results = [o["result"] for o in outputs if "scenario_input" in o and "result" in o]
                if scenarios and results:
                    pdf_bytes = generate_multi_pdf_report(scenarios, results)
                    st.download_button(
                        "📑 Exporter PDF scenarios auto",
                        data=pdf_bytes,
                        file_name="rapport_scenarios_automatiques.pdf",
                        mime="application/pdf",
                        key="sidebar_pdf_auto",
                        use_container_width=True,
                    )
                else:
                    st.caption("Aucun resultat exportable detecte.")
            else:
                st.caption("Lancez les scenarios automatiques pour activer l'export PDF.")
        else:
            st.caption("Export PDF non disponible sur cette page.")
    except Exception as e:
        st.caption(f"PDF indisponible: {e}")


def _render_sidebar_context(page: str):
    with st.sidebar.expander("🧠 Analyse du module", expanded=True):
        st.write(PAGE_ANALYSES.get(page, "Analyse non disponible pour cette section."))

    with st.sidebar.expander("💡 Conseils rapides", expanded=False):
        for tip in PAGE_TIPS.get(page, []):
            st.write(f"- {tip}")

    with st.sidebar.expander("📥 Export PDF des rapports", expanded=False):
        _sidebar_pdf_export_for_page(page)


# ─── Sidebar navigation ───────────────────────────────────────────────────────

def main():
    with st.sidebar:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/E-bike_icon.svg/240px-E-bike_icon.svg.png",
            width=80,
        )
        st.title("Bot VAE")
        st.caption("Simulation Marketing — Marche canadien des VAE")
        st.markdown("---")
        page = st.radio(
            "Navigation",
            [
                "🔬 Simulation directe",
                "📊 Multi-scenarios",
                "🎯 Objectif cible",
                "🧪 Scenarios automatiques",
                "🧭 Plan d'action 2026",
                "🌍 Marche complet",
                "🧮 Calculateur rapide",
                "📁 Historique",
            ],
            key="nav_page",
        )
        st.markdown("---")
        st.caption("**Regles cles**")
        st.caption("• Marketing <= 15% budget ajuste")
        st.caption("• R&D <= 8% budget ajuste")
        st.caption("• Promo standard <= -5%")
        st.caption("• Promo liquidation <= -20%")
        st.caption("• Profit min. >= 2% du CA")
        _show_market_overview()
        _render_sidebar_context(page)

    if page == "🔬 Simulation directe":
        page_single_simulation()
    elif page == "📊 Multi-scenarios":
        page_multi_scenario()
    elif page == "🎯 Objectif cible":
        page_objective_mode()
    elif page == "🧪 Scenarios automatiques":
        page_auto_scenarios()
    elif page == "🧭 Plan d'action 2026":
        page_action_plan_2026()
    elif page == "🌍 Marche complet":
        page_full_market()
    elif page == "🧮 Calculateur rapide":
        page_calculateur()
    elif page == "📁 Historique":
        page_history()


main()
