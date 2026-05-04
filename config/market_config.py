# Market configuration for Canadian e-bike (VAE) simulation
# Primary workbook (paramètres alignés bot): VAE_tout_inclus_01_05_2026_Final1.xlsx
# Fiche équipes (saisie par équipe): Fiche_saisie_equipes_simulation_VAE_ Final.xlsx
# Références pédagogiques cohorte mars 2026 (PDF / chiffrier / liste des décisions) :
#   Simulation VAE 12032026 Final.pdf
#   VAE_tout_inclus_12_03_2026_ajuste_periodes final.xlsx
#   Décisions à prendre par les étudiants à chaque période.docx  (voir data/pedagogie_references.txt)
# Reference year: 2026 | Decision periods: 1-8 (2027-2034)

MARKET_CONFIG = {
    # ── Total market ──────────────────────────────────────────────────────────
    "base_market_size": 110_000,   # units in reference year 2026 (Excel PARAM)
    "base_average_price": 3_500,   # CAD, average market price 2026
    "base_year": 2027,             # Period 1 = 2027 (first decision year)
    "growth_rate": 0.12,           # 12%/yr market growth (Excel PARAM)
    "price_inflation_rate": 0.07,  # 7%/yr price inflation (Excel PARAM)
    "num_periods": 8,              # 8 decision periods (2027-2034)

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
            "label": "Loisirs Polyvalents",
            "share": 0.10,
            "reference_price": 3_200,
            "price_elasticity": 1.4,
            "base_attractiveness": 1.0,
            "description": "Usagers multimodaux cherchant polyvalence et intermodalité",
        },
        "familles_cargo": {
            "label": "Familial",
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

    # ── 9 competing firms (Excel FIRMS sheet) ─────────────────────────────────
    "firms": {
        "AVE": {
            "label": "AVE", "base_rep": 7.5, "units_ref": 13_500,
            "default_segment": "urbains_presses", "default_range": "mid",
        },
        "CAN": {
            "label": "CAN", "base_rep": 8.2, "units_ref": 14_800,
            "default_segment": "endurants_performants", "default_range": "mid",
        },
        "EBI": {
            "label": "EBI", "base_rep": 6.8, "units_ref": 11_200,
            "default_segment": "prudentes_confort", "default_range": "entry",
        },
        "GIA": {
            "label": "GIA", "base_rep": 7.0, "units_ref": 12_400,
            "default_segment": "familles_cargo", "default_range": "mid",
        },
        "PED": {
            "label": "PED", "base_rep": 6.5, "units_ref": 10_800,
            "default_segment": "prudentes_confort", "default_range": "mid",
        },
        "RID": {
            "label": "RID", "base_rep": 7.8, "units_ref": 13_200,
            "default_segment": "aventuriers_tt", "default_range": "premium",
        },
        "SUR": {
            "label": "SUR", "base_rep": 6.0, "units_ref": 9_800,
            "default_segment": "nomades_multimodaux", "default_range": "mid",
        },
        "TRE": {
            "label": "TRE", "base_rep": 8.5, "units_ref": 15_300,
            "default_segment": "urbains_presses", "default_range": "mid",
        },
        "VEL": {
            "label": "VEL", "base_rep": 6.3, "units_ref": 9_800,
            "default_segment": "endurants_performants", "default_range": "entry",
        },
    },

    # ── COGS ratios by range (Excel PARAM: Bas=60%, Moyen=57%, Haut=55%) ─────
    "cogs_ratios": {
        "entry":   0.60,   # 60% of effective selling price
        "mid":     0.57,   # 57% of effective selling price
        "premium": 0.55,   # 55% of effective selling price
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
                "standard":   {"label": "Moyeu standard",            "cost_delta": 0,   "price_delta": 0},
                "mid_drive":  {"label": "Moteur central (mid-drive)", "cost_delta": 180, "price_delta": 250},
                "high_power": {"label": "Haute puissance (>500 W)",  "cost_delta": 320, "price_delta": 450},
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
                "light":    {"label": "Léger (<20 kg)",    "cost_delta": 220, "price_delta": 300},
            },
            "default": "standard",
        },
        "braking": {
            "label": "Freinage",
            "choices": {
                "v_brake":        {"label": "V-brake mécanique",  "cost_delta": 0,   "price_delta": 0},
                "hydraulic_disc": {"label": "Disque hydraulique", "cost_delta": 110, "price_delta": 150},
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
            "label": "Service après-vente",
            "choices": {
                "standard": {"label": "SAV standard",             "cost_delta": 0,   "price_delta": 0},
                "premium":  {"label": "SAV premium (à domicile)", "cost_delta": 145, "price_delta": 200},
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
    "ranges": {
        "entry": {
            "label": "Entrée de gamme (Base)",
            "price_multiplier": 0.92,         # Excel: Bas = 0.92 × ref price
            "target_margin_per_unit": 1_000,
            "unit_production_cost": 1_500,
            "distribution_rate": 0.08,
            "aftersales_rate": 0.015,
            "operating_rate": 0.05,
            "price_range": (2_835, 4_355),
        },
        "mid": {
            "label": "Milieu de gamme",
            "price_multiplier": 1.00,          # Excel: Moyen = 1.00 × ref price
            "target_margin_per_unit": 1_300,
            "unit_production_cost": 2_300,
            "distribution_rate": 0.09,
            "aftersales_rate": 0.020,
            "operating_rate": 0.05,
            "price_range": (3_895, 5_500),
        },
        "premium": {
            "label": "Haut de gamme (Premium)",
            "price_multiplier": 1.12,          # Excel: Haut = 1.12 × ref price
            "target_margin_per_unit": 1_700,
            "unit_production_cost": 2_900,
            "distribution_rate": 0.10,
            "aftersales_rate": 0.025,
            "operating_rate": 0.05,
            "price_range": (5_485, 6_505),
        },
    },

    # ── Business rule constraints ─────────────────────────────────────────────
    "constraints": {
        # Budget caps
        "marketing_max_pct": 0.15,          # max 15% of adjusted budget
        "rd_max_pct": 0.08,                 # max 8% of adjusted budget

        # Promotions (absolute discount %, stored as negative in ScenarioInput)
        "promo_standard_max": -0.05,        # standard promo: max 5% discount
        "promo_liquidation_max": -0.20,     # liquidation promo: max 20% (PARAM Max_Liquidation_Promo)

        # Profitability
        "min_profit_rate": 0.02,            # hard minimum: 2% of revenue
        "profit_target_min": 0.05,          # sweet spot: 5-10%
        "profit_target_max": 0.10,

        # Price/range coherence thresholds
        "price_coherence_warning_pct": 0.10,  # warning if >10% outside range bounds
        "price_coherence_error_pct": 0.20,    # error if >20% outside range bounds

        # Withdrawal rules (Excel game rules)
        "withdrawal_max_total": 4,            # max 4 withdrawals over full simulation
        "withdrawal_min_periods_between": 2,  # min 2 periods between withdrawals

        # New product launch
        "new_product_min_units": 1_000,       # year 1 launch: min 1,000 units sold
        "new_product_max_units": 2_000,       # year 1 launch: max 2,000 units sold

        # Référence Excel bot : coûts sur budget de référence ajusté (pas % CA pour ces postes)
        "aftersales_ref_budget_pct": 0.06,    # SAV = 6 % du budget ajusté
        "operating_ref_budget_pct": 0.05,     # autres frais d'exploitation = 5 % du budget ajusté
        "sustainability_tranche_pct": 0.005,   # chaque investissement durable = 0,5 % du budget ajusté
        # Prime sur le CA uniquement (n'impacte pas le prix / attractivité)
        "sustainability_revenue_premium_by_tranches": {
            2: 0.001,
            3: 0.003,
            4: 0.005,
        },
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
    "fixed_overhead": 80_000,

    # ── Scores ───────────────────────────────────────────────────────────────
    "initial_innovation_score": 5.0,
    "initial_sustainability_score": 5.0,
    "innovation_decay_rate": 0.10,
    "marketing_efficiency_k": 0.4,

    # ── Default competitor attractiveness per segment ──────────────────────────
    "default_competitor_attractiveness": {
        "urbains_presses":       18.0,
        "prudentes_confort":     12.0,
        "endurants_performants": 14.0,
        "nomades_multimodaux":   10.0,
        "familles_cargo":        10.0,
        "aventuriers_tt":        10.0,
    },

    # ── Segment criteria weights matrix ───────────────────────────────────────
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

    # ── Plan d'action 2026/2027 (tests structurés) ───────────────────────────
    "plan_2026": {
        # Seuils d'entree
        "price_coherence_reference": {"warning_pct": 0.10, "error_pct": 0.20},
        "promotion_test_rates": [0.0, -0.02, -0.03, -0.04, -0.05, -0.10],
        "marketing_yield_rates": [0.00, 0.05, 0.10],
        "profit_target_band": [0.05, 0.10],
        "new_product_first_year_units": [1000, 2000],

        # Politiques de renouvellement
        # A: maximum 1 lancement/an ; B: un lancement toutes les 2 periodes.
        "renewal_policies": {
            "A_max_one_per_year": {"launch_periods": [1, 3, 5, 7]},
            "B_every_two_periods": {"launch_periods": [2, 4, 6, 8]},
        },
    },
}
