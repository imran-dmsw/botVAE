from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from config.market_config import MARKET_CONFIG


# ─── Enums as string literals ────────────────────────────────────────────────

SEGMENTS = [
    "urbains_presses",
    "prudentes_confort",
    "endurants_performants",
    "nomades_multimodaux",
    "familles_cargo",
    "aventuriers_tt",
]

RANGES = ["entry", "mid", "premium"]

PRODUCT_STATUSES = ["development", "pre_launch", "active", "withdrawal", "inactive"]

MARKETING_CHANNELS = ["digital", "social_media", "influencers", "display", "events"]

PRODUCT_TYPES = [
    "ville_courte",
    "ville_quotidien",
    "route_connecte",
    "vtc_polyvalent",
    "vtt_exigeant",
    "cargo_familial",
    "vtt_enduro",
    "speed_pedelec",
]


# ─── Input models ─────────────────────────────────────────────────────────────

class MarketingChannels(BaseModel):
    digital: float = Field(0.0, ge=0)
    social_media: float = Field(0.0, ge=0)
    influencers: float = Field(0.0, ge=0)
    display: float = Field(0.0, ge=0)
    events: float = Field(0.0, ge=0)

    def total(self) -> float:
        return self.digital + self.social_media + self.influencers + self.display + self.events


class ScenarioInput(BaseModel):
    # ── Identification ──────────────────────────────────────────────────────
    firm_name: str = Field("Firme A", description="Nom de la firme")
    period: int = Field(1, ge=1, le=8, description="Periode de simulation (1=2027 ... 8=2034)")
    scenario_name: str = Field("Scenario 1", description="Nom du scenario")

    # ── Product ─────────────────────────────────────────────────────────────
    model_name: str = Field("AVE-SwiftRide M1", description="Nom du modele")
    product_type: str = Field("ville_quotidien", description="Type de modele (catalogue VAE)")
    segment: str = Field("urbains_presses", description="Segment cible")
    model_range: str = Field("mid", description="Gamme du modele")
    product_status: str = Field("active", description="Statut du produit")

    # ── Marketing ───────────────────────────────────────────────────────────
    marketing_budget: float = Field(0.0, ge=0, description="Budget marketing total (CAD)")
    marketing_channels: MarketingChannels = Field(
        default_factory=MarketingChannels,
        description="Repartition du budget par canal",
    )

    # ── R&D ─────────────────────────────────────────────────────────────────
    rd_budget: float = Field(0.0, ge=0, description="Budget R&D (CAD)")
    rd_projects: int = Field(0, ge=0, description="Nombre de projets R&D actifs")
    new_model_launch: bool = Field(False, description="Lancement d'un nouveau modele")
    rd_project_type: str = Field("improvement", description="Type de projet R&D")

    # ── Sustainability ───────────────────────────────────────────────────────
    sustainability_investment: float = Field(0.0, ge=0, description="Investissement en durabilite (CAD)")
    sustainability_tranches: int = Field(
        0,
        ge=0,
        le=4,
        description="Nombre d'investissements durables (0,5 % du budget ajuste chacun, prime CA si 2-4)",
    )
    sustainability_periods: int = Field(0, ge=0, description="Periodes d'investissement consecutives")

    # ── Commercial ──────────────────────────────────────────────────────────
    price: float = Field(2500.0, gt=0, description="Prix unitaire (CAD)")
    promotion_rate: float = Field(0.0, ge=-0.30, le=0, description="Taux de promotion (negatif, ex: -0.05 = -5%)")
    production: int = Field(1000, ge=0, description="Unites produites")
    withdraw_model: bool = Field(False, description="Retrait du modele du marche")
    liquidation: bool = Field(False, description="Mode liquidation")

    # ── Withdrawal tracking (context across periods) ─────────────────────────
    total_withdrawals_used: int = Field(0, ge=0, description="Nombre de retraits utilises jusqu'ici (simulation)")
    last_withdrawal_period: int = Field(0, ge=0, description="Periode du dernier retrait (0 = aucun)")

    # ── Context (used by engine) ─────────────────────────────────────────────
    adjusted_budget: float = Field(
        1_000_000.0,
        gt=0,
        description="Budget ajuste de reference (ex: CA periode precedente) pour calcul des plafonds",
    )
    previous_innovation_score: float = Field(5.0, ge=0, le=10, description="Score innovation periode precedente")
    previous_sustainability_score: float = Field(5.0, ge=0, le=10, description="Score durabilite periode precedente")
    competitor_attractiveness: float = Field(
        10.0,
        gt=0,
        description="Attractivite totale des concurrents dans le segment",
    )

    # ── Validators ──────────────────────────────────────────────────────────
    @field_validator("segment")
    @classmethod
    def check_segment(cls, v: str) -> str:
        if v not in SEGMENTS:
            raise ValueError(f"Segment doit etre parmi {SEGMENTS}")
        return v

    @field_validator("model_range")
    @classmethod
    def check_range(cls, v: str) -> str:
        if v not in RANGES:
            raise ValueError(f"Gamme doit etre parmi {RANGES}")
        return v

    @field_validator("product_status")
    @classmethod
    def check_status(cls, v: str) -> str:
        if v not in PRODUCT_STATUSES:
            raise ValueError(f"Statut doit etre parmi {PRODUCT_STATUSES}")
        return v

    @field_validator("product_type")
    @classmethod
    def check_product_type(cls, v: str) -> str:
        if v not in PRODUCT_TYPES:
            raise ValueError(f"Type de produit doit etre parmi {PRODUCT_TYPES}")
        return v

    @model_validator(mode="after")
    def check_channel_total(self) -> "ScenarioInput":
        ch_total = self.marketing_channels.total()
        if ch_total > 0 and abs(ch_total - self.marketing_budget) > 1.0:
            if ch_total > 0:
                ratio = self.marketing_budget / ch_total
                mc = self.marketing_channels
                self.marketing_channels = MarketingChannels(
                    digital=mc.digital * ratio,
                    social_media=mc.social_media * ratio,
                    influencers=mc.influencers * ratio,
                    display=mc.display * ratio,
                    events=mc.events * ratio,
                )
        return self

    @model_validator(mode="after")
    def sync_sustainability_tranches(self) -> "ScenarioInput":
        adj = max(self.adjusted_budget, 1.0)
        pct = MARKET_CONFIG["constraints"]["sustainability_tranche_pct"]
        tr = max(0, min(4, int(self.sustainability_tranches)))
        if tr == 0 and self.sustainability_investment > 0:
            inferred = int(round(self.sustainability_investment / (pct * adj)))
            tr = max(0, min(4, inferred))
        self.sustainability_tranches = tr
        self.sustainability_investment = round(tr * pct * adj, 2)
        return self


# ─── Output models ────────────────────────────────────────────────────────────

class SimulationResult(BaseModel):
    # Identification
    firm_name: str
    period: int
    scenario_name: str

    # Sales
    demand: float
    sales: int
    service_rate: float          # sales / demand

    # Financial (revenue = CA reconnu, inclut la prime durabilite sur le CA si applicable)
    revenue: float
    base_revenue_before_premium: float = 0.0
    sustainability_revenue_premium_rate: float = 0.0
    production_cost: float
    distribution_cost: float
    marketing_cost: float
    rd_cost: float
    operating_cost: float
    aftersales_cost: float
    sustainability_cost: float
    total_cost: float
    profit: float
    margin: float                # profit / revenue

    # Market
    market_share: float          # sales / total market
    market_share_segment: float  # sales / segment size

    # Scores
    innovation_score: float
    sustainability_score: float

    # Attractiveness (internal, useful for debug)
    attractiveness: float

    # Diagnostics
    is_valid: bool
    alerts: List[str]
    interpretations: List[str]

    # Extended business indicators
    profit_rate: float = 0.0
    profit_rate_status: str = "faible"
    price_range_consistency_status: str = "unknown"
    marketing_efficiency: float = 0.0
    marketing_marginal_profit_delta: float = 0.0
    production_efficiency: float = 0.0
    next_period_recommended_production: int = 0
    new_product_first_year_flag: bool = False
    withdrawal_limit_status: str = "ok"
    liquidation_next_period_production_flag: bool = False
    baseline_2026_indicator: float = 0.0


class OptimizationResult(BaseModel):
    success: bool
    target_metric: str
    target_value: float
    achieved_value: float
    gap: float
    message: str
    recommended_scenario: ScenarioInput
    simulation_result: SimulationResult
    explanation: List[str]


class MultiScenarioSummary(BaseModel):
    scenarios: List[ScenarioInput]
    results: List[SimulationResult]
    best_profit_index: int
    best_margin_index: int
    best_market_share_index: int
    best_innovation_index: int
    ranking: List[Dict]          # [{rank, name, score, profit, margin, market_share}]
