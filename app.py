"""
Bot de simulation strategique marketing — Simulation VAE (Velos a Assistance Electrique)
Interface Streamlit — 4 modules :
  1. Simulation directe (scenario unique)
  2. Comparaison multi-scenarios
  3. Mode objectif cible (simulation inverse)
  4. Historique
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from config.market_config import MARKET_CONFIG
from engine.models import ScenarioInput, MarketingChannels
from engine.simulation import simulate, simulate_multi, period_to_year, total_market_size
from engine.optimizer import find_parameters_for_target, SUPPORTED_METRICS
from reports.generator import (
    generate_markdown_report,
    generate_word_report,
    generate_pdf_report,
    generate_json_report,
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
    )


# ─── Scenario form widget ─────────────────────────────────────────────────────

def scenario_form(key_prefix: str = "", title: str = "Parametres du scenario"):
    p = key_prefix
    with st.expander(title, expanded=True):
        # ── Identification ──────────────────────────────────────────────────
        col1, col2, col3 = st.columns(3)
        with col1:
            st.text_input("Firme", value="Firme A", key=f"{p}firm_name")
            st.number_input("Periode", min_value=1, max_value=15, value=1, step=1, key=f"{p}period")
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
            st.number_input("Taux de promotion (%)", min_value=-20.0, max_value=0.0,
                            value=0.0, step=1.0, key=f"{p}promo_rate",
                            help="Standard max : -5% | Liquidation max : -20%")
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


# ─── Results display ──────────────────────────────────────────────────────────

def display_results(scenario: ScenarioInput, result, show_export: bool = True):
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

    # Waterfall
    st.subheader("Decomposition financiere")
    fig = _waterfall_chart(result)
    st.plotly_chart(fig, use_container_width=True)

    # Cost pie + detail table
    col_pie, col_cost = st.columns(2)
    with col_pie:
        fig2 = _cost_pie(result)
        st.plotly_chart(fig2, use_container_width=True)

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
        display_results(st.session_state["last_scenario"], st.session_state["last_result"])


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

        st.plotly_chart(_radar_chart(results, names), use_container_width=True)

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
        st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("Details par scenario")
        for i, (sc, res) in enumerate(zip(scenarios, results)):
            with st.expander(f"Details — {res.scenario_name}", expanded=False):
                display_results(sc, res, show_export=True)


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
            display_results(rec, opt.simulation_result, show_export=True)


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
        st.plotly_chart(fig_trend, use_container_width=True)

    if st.button("🗑️ Effacer tout l'historique", type="secondary"):
        clear_history()
        st.success("Historique efface.")
        st.rerun()


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

    if page == "🔬 Simulation directe":
        page_single_simulation()
    elif page == "📊 Multi-scenarios":
        page_multi_scenario()
    elif page == "🎯 Objectif cible":
        page_objective_mode()
    elif page == "📁 Historique":
        page_history()


if __name__ == "__main__":
    main()
