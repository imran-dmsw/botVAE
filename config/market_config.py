# Market configuration for Canadian e-bike (VAE) simulation
# Source: Simulation VAE VERSION 1.1 (2026-02-27) — Marché fictif canadien

MARKET_CONFIG = {
    # ── Total market ──────────────────────────────────────────────────────────
    "base_market_size": 120_000,   # units/year, period 1 = 2026
    "base_average_price": 3_000,   # CAD, average market price in 2026
    "base_year": 2026,             # year corresponding to period 1

    # Two-phase growth (units)
    "growth_rate_phase1": 0.15,    # 15 %/yr units,  2026-2034 (periods 1-9)
    "growth_rate_phase2": 0.175,   # 17.5%/yr units, 2035-2040 (periods 10-15)
    "price_growth_phase1": 0.07,   # 7 %/yr avg price, 2026-2034
    "price_growth_phase2": 0.08,   # 8 %/yr avg price, 2035-2040
    "phase_change_period": 10,     # first period of phase 2
    "num_periods": 15,             # 2026-2040

    # ── Customer segments (6) ─────────────────────────────────────────────────
    "segments": {
        "urbains_presses": {
            "label": "Urbains Pressés",
            "share": 0.30,
            "reference_price": 2_800,
            "price_elasticity": 1.6,
            "base_attractiveness": 1.0,
            "description": "Navetteurs urbains : efficacité, légèreté et praticité quotidienne",
        },
        "prudentes_confort": {
            "label": "Prudentes Confort",
            "share": 0.15,
            "reference_price": 2_600,
            "price_elasticity": 1.8,
            "base_attractiveness": 1.0,
            "description": "Cyclistes axés confort, sécurité et facilité de prise en main",
        },
        "endurants_performants": {
            "label": "Endurants Performants",
            "share": 0.20,
            "reference_price": 4_200,
            "price_elasticity": 1.0,
            "base_attractiveness": 1.0,
            "description": "Passionnés de performance, longues distances et vitesse",
        },
        "nomades_multimodaux": {
            "label": "Nomades Multimodaux",
            "share": 0.10,
            "reference_price": 3_200,
            "price_elasticity": 1.4,
            "base_attractiveness": 1.0,
            "description": "Usagers multimodaux cherchant polyvalence et intermodalité",
        },
        "familles_cargo": {
            "label": "Familles Cargo",
            "share": 0.15,
            "reference_price": 4_500,
            "price_elasticity": 1.2,
            "base_attractiveness": 1.0,
            "description": "Familles transportant enfants et marchandises au quotidien",
        },
        "aventuriers_tt": {
            "label": "Aventuriers Tout-terrain",
            "share": 0.10,
            "reference_price": 5_000,
            "price_elasticity": 0.9,
            "base_attractiveness": 1.0,
            "description": "Amateurs de hors-piste, endurance et sensations fortes",
        },
    },

    # ── Product types (8 modèles de base du catalogue VAE) ────────────────────
    "product_types": {
        "ville_courte": {
            "label": "Ville courte distance",
            "base_cost": 1_360,
            "target_segments": ["urbains_presses"],
            "default_range": "entry",
        },
        "ville_quotidien": {
            "label": "Ville quotidien+",
            "base_cost": 1_870,
            "target_segments": ["urbains_presses", "prudentes_confort", "nomades_multimodaux"],
            "default_range": "entry",
        },
        "route_connecte": {
            "label": "Vélo de route connecté",
            "base_cost": 2_420,
            "target_segments": ["endurants_performants"],
            "default_range": "mid",
        },
        "vtc_polyvalent": {
            "label": "VTC polyvalent",
            "base_cost": 2_090,
            "target_segments": ["nomades_multimodaux", "prudentes_confort"],
            "default_range": "mid",
        },
        "vtt_exigeant": {
            "label": "VTT exigeant",
            "base_cost": 3_230,
            "target_segments": ["aventuriers_tt"],
            "default_range": "premium",
        },
        "cargo_familial": {
            "label": "Cargo familial",
            "base_cost": 2_550,
            "target_segments": ["familles_cargo"],
            "default_range": "mid",
        },
        "vtt_enduro": {
            "label": "VTT enduro",
            "base_cost": 2_890,
            "target_segments": ["aventuriers_tt", "endurants_performants"],
            "default_range": "premium",
        },
        "speed_pedelec": {
            "label": "Speed pedelec (45 km/h)",
            "base_cost": 2_730,
            "target_segments": ["endurants_performants", "nomades_multimodaux"],
            "default_range": "mid",
        },
    },

    # ── Product options (coût et prix additionnels) ───────────────────────────
    "product_options": {
        "motor_type": {
            "label": "Type de moteur",
            "choices": {
                "standard":   {"label": "Moyeu standard",           "cost_delta": 0,   "price_delta": 0},
                "mid_drive":  {"label": "Moteur central (mid-drive)","cost_delta": 180, "price_delta": 250},
                "high_power": {"label": "Haute puissance (>500 W)", "cost_delta": 320, "price_delta": 450},
            },
            "default": "standard",
        },
        "sensor": {
            "label": "Capteur d'assistance",
            "choices": {
                "cadence": {"label": "Cadence (pédalage)",      "cost_delta": 0,   "price_delta": 0},
                "torque":  {"label": "Couple (torque sensor)", "cost_delta": 110, "price_delta": 150},
            },
            "default": "cadence",
        },
        "battery_capacity": {
            "label": "Capacité batterie",
            "choices": {
                "small":  {"label": "Petite (<400 Wh)",     "cost_delta": 0,   "price_delta": 0},
                "medium": {"label": "Moyenne (400-600 Wh)", "cost_delta": 150, "price_delta": 200},
                "large":  {"label": "Grande (600-800 Wh)",  "cost_delta": 290, "price_delta": 400},
                "xl":     {"label": "XL (>800 Wh)",         "cost_delta": 500, "price_delta": 700},
            },
            "default": "small",
        },
        "battery_type": {
            "label": "Technologie batterie",
            "choices": {
                "nmc": {"label": "NMC (haute densité)", "cost_delta": 0,  "price_delta": 0},
                "lfp": {"label": "LFP (longévité)",    "cost_delta": 70, "price_delta": 100},
            },
            "default": "nmc",
        },
        "weight_class": {
            "label": "Classe de poids",
            "choices": {
                "standard": {"label": "Standard (>20 kg)", "cost_delta": 0,   "price_delta": 0},
                "light":    {"label": "Leger (<20 kg)",    "cost_delta": 220, "price_delta": 300},
            },
            "default": "standard",
        },
        "braking": {
            "label": "Freinage",
            "choices": {
                "v_brake":       {"label": "V-brake mecanique",        "cost_delta": 0,   "price_delta": 0},
                "hydraulic_disc":{"label": "Disque hydraulique",       "cost_delta": 110, "price_delta": 150},
            },
            "default": "v_brake",
        },
        "speed_limit": {
            "label": "Limitation vitesse",
            "choices": {
                "25kmh": {"label": "25 km/h (standard)",      "cost_delta": 0,   "price_delta": 0},
                "45kmh": {"label": "45 km/h (speed pedelec)", "cost_delta": 360, "price_delta": 500},
            },
            "default": "25kmh",
        },
        "warranty": {
            "label": "Garantie",
            "choices": {
                "1yr": {"label": "1 an",  "cost_delta": 0,   "price_delta": 0},
                "2yr": {"label": "2 ans", "cost_delta": 70,  "price_delta": 100},
                "3yr": {"label": "3 ans", "cost_delta": 180, "price_delta": 250},
            },
            "default": "1yr",
        },
        "sav": {
            "label": "Service apres-vente",
            "choices": {
                "standard": {"label": "SAV standard",             "cost_delta": 0,   "price_delta": 0},
                "premium":  {"label": "SAV premium (a domicile)", "cost_delta": 145, "price_delta": 200},
            },
            "default": "standard",
        },
        "cargo_option": {
            "label": "Option cargo",
            "choices": {
                "none":       {"label": "Aucune",                    "cost_delta": 0,   "price_delta": 0},
                "rack":       {"label": "Porte-bagages",             "cost_delta": 110, "price_delta": 150},
                "full_cargo": {"label": "Full cargo (longtail/box)", "cost_delta": 360, "price_delta": 500},
            },
            "default": "none",
        },
    },

    # ── Product ranges (gammes) ───────────────────────────────────────────────
    # target_margin_per_unit = prix cible - cout de base du type de produit
    "ranges": {
        "entry": {
            "label": "Entree de gamme (Base)",
            "target_margin_per_unit": 1_000,
            "unit_production_cost": 1_500,   # fallback si product_type non specifie
            "distribution_rate": 0.08,
            "aftersales_rate": 0.015,
            "operating_rate": 0.05,
            "price_range": (1_800, 3_500),
        },
        "mid": {
            "label": "Milieu de gamme",
            "target_margin_per_unit": 1_300,
            "unit_production_cost": 2_300,
            "distribution_rate": 0.09,
            "aftersales_rate": 0.020,
            "operating_rate": 0.05,
            "price_range": (2_800, 5_500),
        },
        "premium": {
            "label": "Haut de gamme (Premium)",
            "target_margin_per_unit": 1_700,
            "unit_production_cost": 2_900,
            "distribution_rate": 0.10,
            "aftersales_rate": 0.025,
            "operating_rate": 0.05,
            "price_range": (4_000, 9_000),
        },
    },

    # ── Business rule constraints ─────────────────────────────────────────────
    "constraints": {
        "marketing_max_pct": 0.15,
        "rd_max_pct": 0.08,
        "promo_standard_max": -0.05,
        "promo_liquidation_max": -0.20,
        "min_profit_rate": 0.02,
    },

    # ── Marketing channels ────────────────────────────────────────────────────
    "marketing_channels": ["digital", "social_media", "influencers", "display", "events"],

    # ── R&D ──────────────────────────────────────────────────────────────────
    "rd_project_types": ["new_model", "improvement", "sustainability"],

    # ── Product lifecycle ─────────────────────────────────────────────────────
    "product_statuses": ["development", "pre_launch", "active", "withdrawal", "inactive"],
    "product_status_factors": {
        "development": 0.0,
        "pre_launch":  0.15,
        "active":      1.0,
        "withdrawal":  0.55,
        "inactive":    0.0,
    },

    # ── Fixed costs ───────────────────────────────────────────────────────────
    "fixed_overhead": 80_000,   # CAD per period

    # ── Scores ───────────────────────────────────────────────────────────────
    "initial_innovation_score": 5.0,
    "initial_sustainability_score": 5.0,
    "innovation_decay_rate": 0.10,
    "marketing_efficiency_k": 0.4,

    # ── Default competitor attractiveness per segment ──────────────────────────
    # Represents combined attractiveness of all rival firms in the segment
    "default_competitor_attractiveness": {
        "urbains_presses":       18.0,
        "prudentes_confort":     12.0,
        "endurants_performants": 14.0,
        "nomades_multimodaux":   10.0,
        "familles_cargo":        10.0,
        "aventuriers_tt":        10.0,
    },

    # ── Segment criteria weights matrix (6 segments x 9 criteria) ─────────────
    # Criteria: price, performance, comfort, weight, range,
    #           innovation, sustainability, design, brand
    "segment_criteria_weights": {
        "urbains_presses": {
            "price": 0.20, "performance": 0.15, "comfort": 0.12,
            "weight": 0.12, "range": 0.15, "innovation": 0.10,
            "sustainability": 0.05, "design": 0.06, "brand": 0.05,
        },
        "prudentes_confort": {
            "price": 0.25, "performance": 0.05, "comfort": 0.25,
            "weight": 0.10, "range": 0.10, "innovation": 0.05,
            "sustainability": 0.08, "design": 0.07, "brand": 0.05,
        },
        "endurants_performants": {
            "price": 0.10, "performance": 0.30, "comfort": 0.08,
            "weight": 0.15, "range": 0.15, "innovation": 0.10,
            "sustainability": 0.04, "design": 0.05, "brand": 0.03,
        },
        "nomades_multimodaux": {
            "price": 0.18, "performance": 0.12, "comfort": 0.15,
            "weight": 0.15, "range": 0.15, "innovation": 0.10,
            "sustainability": 0.07, "design": 0.05, "brand": 0.03,
        },
        "familles_cargo": {
            "price": 0.20, "performance": 0.08, "comfort": 0.18,
            "weight": 0.08, "range": 0.12, "innovation": 0.05,
            "sustainability": 0.12, "design": 0.07, "brand": 0.10,
        },
        "aventuriers_tt": {
            "price": 0.08, "performance": 0.28, "comfort": 0.10,
            "weight": 0.18, "range": 0.12, "innovation": 0.12,
            "sustainability": 0.05, "design": 0.04, "brand": 0.03,
        },
    },
}
