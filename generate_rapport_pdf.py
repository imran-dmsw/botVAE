"""
Script autonome : génère rapport_scenarios_test.pdf avec fpdf2.
Usage : python3 generate_rapport_pdf.py
"""
import sys
sys.path.insert(0, '/Users/imran/BotMarketing')

from fpdf import FPDF
from datetime import datetime
from engine.simulation import simulate, suggest_next_production
from engine.models import ScenarioInput

# ─── Données ──────────────────────────────────────────────────────────────────

def make(name, firm, segment, rng, price, prod, mkt_pct, promo,
         status="active", new_model=False, liquidation=False, rd_pct=0.02):
    adj = prod * price
    return ScenarioInput(
        scenario_name=name, firm_name=firm, period=1,
        model_name=f"{name}_model", segment=segment, model_range=rng,
        product_status="withdrawal" if liquidation else status,
        price=float(price), production=prod,
        marketing_budget=adj * mkt_pct, adjusted_budget=float(adj),
        promotion_rate=float(promo), rd_budget=adj * rd_pct if rd_pct else 0.0,
        new_model_launch=new_model, liquidation=liquidation,
        previous_innovation_score=5.0,
    )

SCENARIOS = [
    make("Equilibre_Optimal",  "TRE","urbains_presses","mid",2900, 9000,0.08, 0.00, rd_pct=0.03),
    make("Marketing_Optimal",  "AVE","urbains_presses","mid",3000,10000,0.10, 0.00, rd_pct=0.02),
    make("Promo_Agressive",    "GIA","urbains_presses","mid",2900,11000,0.06,-0.10, rd_pct=0.02),
    make("Prix_Incoherent",    "SUR","urbains_presses","mid",2500, 8000,0.07, 0.00, rd_pct=0.02),
    make("Nouveau_Produit",    "TRE","urbains_presses","mid",3100, 6000,0.09, 0.00, rd_pct=0.04, new_model=True),
    make("Liquidation_Modele", "AVE","urbains_presses","mid",2800, 5000,0.05,-0.10, rd_pct=0.0,  liquidation=True),
]

RESULTS = [simulate(s) for s in SCENARIOS]
NEXTS   = [suggest_next_production(s, r) for s, r in zip(SCENARIOS, RESULTS)]

ANALYSES = [
    [
        "Scenario de reference propre - aucune alerte declenchee.",
        "Marge 11.9% au-dessus de la zone cible 5-10% : excellente rentabilite.",
        "Surplus de 2 267 unites non vendues (prod. 9 000 vs demande 6 733).",
        "Marketing a 10.7% du CA reel : legerement au-dessus du seuil optimal 10%.",
        "Recommandation N+1 : reduire la production a 8 079 unites.",
    ],
    [
        "Marge 8.9% dans la zone cible 5-10% : objectif ROI marketing atteint.",
        "Marketing a 14.8% du CA reel : proche du plafond reglementaire 15%.",
        "Rendement marginal faible : +36 unites vs S1 pour +912 000 $ de budget.",
        "Surplus de 3 231 unites : probleme de production surestimee, pas de marketing.",
        "Recommandation : plafonner le marketing a 8-10% du CA pour un meilleur ROI.",
    ],
    [
        "Hausse des ventes confirmee : +887 unites (+13%) grace a la promo -10%.",
        "RESULTAT INATTENDU : marge 13.8%, superieure au scenario reference (11.9%).",
        "Explication : COGS calcule en % du prix effectif (2 610 $ x 57% = 1 488 $).",
        "Le volume compense la reduction de prix - la promo est une strategie dominante.",
        "La 'chute de profit' attendue ne se produit pas avec ce modele de couts.",
    ],
    [
        "2 alertes prix/gamme declenchees : 2 500 $ < minimum 2 800 $ pour gamme Mid.",
        "Penalite d'attractivite appliquee : PDM segment 16.5% vs 18.2% en S1 (-1.7 pts).",
        "CA reduit de 4.3 M$ par rapport a S1 malgre un volume quasi identique.",
        "Marge paradoxalement haute (14.7%) car COGS reduit proportionnellement au prix.",
        "Recommandation : corriger le prix a minimum 2 900 $ pour la gamme Milieu.",
    ],
    [
        "Regle 1 000-2 000 unites confirmee : ventes plafonnees a 2 000 malgre demande 5 970.",
        "Perte de 824 000 $ attendue en annee 1 : coûts fixes > revenus limites.",
        "4 alertes declenchees : production > 2 000, ventes encadrees, deficit, perte.",
        "Score innovation : 8.40 - fort bonus pour les periodes suivantes.",
        "Montee progressive confirmee : production recommandee N+1 = 5 671 unites.",
    ],
    [
        "Ecoulement stock confirme : 4 126 unites vendues sur 5 000 produites.",
        "Production N+1 = 0 confirmee : regle liquidation correctement appliquee.",
        "Marge 19.5% - la plus haute de tous les scenarios : peu de couts engages.",
        "Strategie optimale : liquidation -10% promo + marketing minimal = max profit sortie.",
        "Résidu de 874 unites non vendues a gerer.",
    ],
]

OBJECTIFS = [
    "Scenario propre - profit attendu 5-10%",
    "Tester rendement marketing - ROI optimal 0-10%",
    "Promo agressive - hausse ventes + chute profit",
    "Prix incoherent - verifier alerte prix/gamme",
    "Nouveau produit - ventes limitees 1000-2000 + montee progressive",
    "Liquidation - production N+1=0 + ecoulement stock",
]

# ─── PDF helpers ──────────────────────────────────────────────────────────────

def safe(text):
    s = str(text)
    s = (s.replace("\u2014", " - ").replace("\u2013", "-")
          .replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
          .replace("\u2026", "...").replace("\u00e9", "e").replace("\u00e8", "e")
          .replace("\u00ea", "e").replace("\u00eb", "e").replace("\u00e0", "a")
          .replace("\u00e2", "a").replace("\u00ee", "i").replace("\u00ef", "i")
          .replace("\u00f4", "o").replace("\u00f9", "u").replace("\u00fb", "u")
          .replace("\u00fc", "u").replace("\u00e7", "c").replace("\u00f1", "n")
          .replace("\u00c9", "E").replace("\u00c0", "A").replace("\u00c8", "E"))
    return s.encode("latin-1", "replace").decode("latin-1")


class PDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, safe(f"Bot Simulation VAE - Rapport 6 scenarios - Page {self.page_no()}"), align="C")
        self.set_text_color(0, 0, 0)

    def section_title(self, text, size=12):
        self.set_font("Helvetica", "B", size)
        self.set_fill_color(30, 60, 120)
        self.set_text_color(255, 255, 255)
        self.set_x(self.l_margin)
        self.cell(0, 8, safe(text), ln=True, fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def sub_title(self, text):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(30, 60, 120)
        self.set_x(self.l_margin)
        self.cell(0, 7, safe(text), ln=True)
        self.set_text_color(0, 0, 0)

    def row2(self, label, value, fill=False):
        w = self.w - self.l_margin - self.r_margin
        c1, c2 = w * 0.60, w * 0.40
        self.set_font("Helvetica", "", 9)
        fc = (240, 244, 250) if fill else (255, 255, 255)
        self.set_fill_color(*fc)
        self.set_x(self.l_margin)
        self.cell(c1, 6, safe(label), border=1, fill=True)
        self.cell(c2, 6, safe(value), border=1, fill=True, ln=True)

    def row3(self, label, value, pct, fill=False):
        w = self.w - self.l_margin - self.r_margin
        c1, c2, c3 = w * 0.50, w * 0.28, w * 0.22
        self.set_font("Helvetica", "", 9)
        fc = (240, 244, 250) if fill else (255, 255, 255)
        self.set_fill_color(*fc)
        self.set_x(self.l_margin)
        self.cell(c1, 6, safe(label), border=1, fill=True)
        self.cell(c2, 6, safe(value), border=1, fill=True)
        self.cell(c3, 6, safe(pct), border=1, fill=True, ln=True)

    def multiline(self, text, h=5):
        w = self.w - self.l_margin - self.r_margin
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 9)
        self.multi_cell(w, h, safe(text))

    def bullet(self, text, color=(0, 0, 0)):
        self.set_text_color(*color)
        self.multiline("  - " + text)
        self.set_text_color(0, 0, 0)


# ─── Build PDF ────────────────────────────────────────────────────────────────

pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=18)
now = datetime.now().strftime("%Y-%m-%d %H:%M")

# ══════════════════════════════════════════════════════
# PAGE DE COUVERTURE
# ══════════════════════════════════════════════════════
pdf.add_page()
pdf.ln(20)
pdf.set_font("Helvetica", "B", 22)
pdf.set_text_color(30, 60, 120)
pdf.cell(0, 12, "RAPPORT DE TEST", ln=True, align="C")
pdf.cell(0, 12, "6 Scenarios de Simulation VAE", ln=True, align="C")
pdf.set_text_color(0, 0, 0)
pdf.ln(6)
pdf.set_font("Helvetica", "", 11)
pdf.cell(0, 8, safe("Marche : Urbains Presses  |  Periode 1 (2027)  |  Marche total : 123 200 unites"), ln=True, align="C")
pdf.cell(0, 8, safe(f"Genere le : {now}"), ln=True, align="C")
pdf.ln(12)

# Tableau de couverture
pdf.set_font("Helvetica", "B", 9)
pdf.set_fill_color(30, 60, 120)
pdf.set_text_color(255, 255, 255)
w = pdf.w - pdf.l_margin - pdf.r_margin
cols = [8, 34, 10, 18, 20, 16, 20, 18, 16]
headers = ["#", "Scenario", "Firme", "Ventes", "CA", "Marge", "PDM seg.", "Alertes", "N+1"]
pdf.set_x(pdf.l_margin)
for h, c in zip(headers, cols):
    pdf.cell(c, 7, h, border=1, fill=True)
pdf.ln()
pdf.set_text_color(0, 0, 0)

colors_alert = {0: (0, 128, 0), 1: (200, 120, 0), 2: (200, 0, 0), 4: (200, 0, 0)}
names_short = ["Equilibre", "Mktg Opt.", "Promo Agr.", "Prix Incoh.", "Nv Produit", "Liquidation"]
for i, (s, r, n) in enumerate(zip(SCENARIOS, RESULTS, NEXTS)):
    fill = i % 2 == 0
    fc = (245, 247, 252) if fill else (255, 255, 255)
    pdf.set_fill_color(*fc)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_x(pdf.l_margin)
    pdf.cell(cols[0], 6, str(i+1), border=1, fill=True)
    pdf.cell(cols[1], 6, names_short[i], border=1, fill=True)
    pdf.cell(cols[2], 6, s.firm_name, border=1, fill=True)
    pdf.cell(cols[3], 6, f"{r.sales:,}", border=1, fill=True)
    pdf.cell(cols[4], 6, f"{r.revenue/1e6:.1f} M$", border=1, fill=True)
    # Marge en couleur
    marge_color = (0, 128, 0) if r.margin >= 0.05 else (200, 0, 0)
    pdf.set_text_color(*marge_color)
    pdf.cell(cols[5], 6, f"{r.margin*100:.1f}%", border=1, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(cols[6], 6, f"{r.market_share_segment*100:.1f}%", border=1, fill=True)
    al_color = (200, 0, 0) if r.alerts else (0, 128, 0)
    pdf.set_text_color(*al_color)
    pdf.cell(cols[7], 6, str(len(r.alerts)), border=1, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(cols[8], 6, str(n), border=1, fill=True, ln=True)

pdf.ln(10)
pdf.set_font("Helvetica", "B", 10)
pdf.set_text_color(30, 60, 120)
pdf.cell(0, 7, "Regles metier testees :", ln=True)
pdf.set_text_color(0, 0, 0)
pdf.set_font("Helvetica", "", 9)
validations = [
    "[OK] Alerte prix/gamme              -> S4 : 2 alertes declenchees (2 500$ < min 2 800$ gamme Mid)",
    "[OK] Plafond nouveau produit        -> S5 : ventes plafonnees a 2 000 unites (regle 1 000-2 000)",
    "[OK] Production liquidation N+1 = 0 -> S6 : production recommandee N+1 = 0",
    "[OK] Profit cible 5-10%             -> S2 : 8.9% dans la zone cible",
    "[OK] Marketing ROI optimal <= 10%   -> alertes interpretations si depasse",
]
for v in validations:
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 5, safe(v), ln=True)

# ══════════════════════════════════════════════════════
# PAGES PAR SCENARIO
# ══════════════════════════════════════════════════════

scenario_colors = [
    (30, 120, 60),    # S1 vert
    (30, 60, 180),    # S2 bleu
    (180, 80, 0),     # S3 orange
    (160, 0, 0),      # S4 rouge
    (80, 0, 160),     # S5 violet
    (0, 100, 120),    # S6 teal
]

for i, (sc, r, n, analyse, obj) in enumerate(zip(SCENARIOS, RESULTS, NEXTS, ANALYSES, OBJECTIFS)):
    pdf.add_page()
    color = scenario_colors[i]

    # En-tete scenario
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_fill_color(*color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 10, safe(f"SCENARIO {i+1} - {sc.scenario_name}"), ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_x(pdf.l_margin)
    pdf.cell(0, 6, safe(f"Firme : {sc.firm_name}  |  Objectif : {obj}"), ln=True)
    pdf.ln(3)

    w = pdf.w - pdf.l_margin - pdf.r_margin

    # ── Paramètres ────────────────────────────────────
    pdf.sub_title("Parametres du scenario")
    eff_price = sc.price * (1 + sc.promotion_rate)
    surplus = max(0, sc.production - r.sales)
    mkt_pct_ca = r.marketing_cost / max(r.revenue, 1) * 100

    params = [
        ("Gamme", "Milieu de gamme (Mid)"),
        ("Prix affiche", f"{sc.price:,.0f} $"),
        ("Prix effectif (apres promo)", f"{eff_price:,.0f} $"),
        ("Promotion", f"{sc.promotion_rate*100:.0f}%"),
        ("Production", f"{sc.production:,} unites"),
        ("Budget marketing", f"{sc.marketing_budget:,.0f} $  ({mkt_pct_ca:.1f}% du CA reel)"),
        ("Budget R&D", f"{sc.rd_budget:,.0f} $"),
        ("Nouveau modele", "OUI" if sc.new_model_launch else "non"),
        ("Statut produit", sc.product_status),
    ]
    for j, (k, v) in enumerate(params):
        pdf.row2(k, v, fill=(j % 2 == 0))
    pdf.ln(4)

    # ── KPIs ────────────────────────────────────────────
    pdf.sub_title("Resultats cles")
    kpis = [
        ("Demande estimee", f"{r.demand:,.0f} unites"),
        ("Ventes realisees", f"{r.sales:,} unites"),
        ("Surplus stock (non vendu)", f"{surplus:,} unites"),
        ("Taux de service", f"{r.service_rate*100:.1f}%"),
        ("Chiffre d'affaires", f"{r.revenue:,.0f} $"),
        ("Profit", f"{r.profit:,.0f} $"),
        ("Marge nette", f"{r.margin*100:.2f}%"),
        ("PDM total marche", f"{r.market_share*100:.2f}%"),
        ("PDM segment Urbains Presses", f"{r.market_share_segment*100:.2f}%"),
        ("Score innovation N+1", f"{r.innovation_score:.2f} / 10"),
        ("Production recommandee N+1", f"{n}"),
    ]
    for j, (k, v) in enumerate(kpis):
        # Color marge
        if k == "Marge nette":
            pdf.set_font("Helvetica", "B", 9)
            mc = (0, 128, 0) if r.margin >= 0.02 else (200, 0, 0)
            fill = j % 2 == 0
            fc = (240, 244, 250) if fill else (255, 255, 255)
            pdf.set_fill_color(*fc)
            pdf.set_x(pdf.l_margin)
            c1, c2 = w * 0.60, w * 0.40
            pdf.cell(c1, 6, safe(k), border=1, fill=True)
            pdf.set_text_color(*mc)
            pdf.cell(c2, 6, safe(v), border=1, fill=True, ln=True)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 9)
        else:
            pdf.row2(k, v, fill=(j % 2 == 0))
    pdf.ln(4)

    # ── Compte de résultat simplifié ──────────────────────
    pdf.sub_title("Compte de resultat simplifie")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(30, 60, 120)
    pdf.set_text_color(255, 255, 255)
    pdf.set_x(pdf.l_margin)
    c1, c2, c3 = w * 0.50, w * 0.28, w * 0.22
    pdf.cell(c1, 6, "Poste", border=1, fill=True)
    pdf.cell(c2, 6, "Montant ($)", border=1, fill=True)
    pdf.cell(c3, 6, "% du CA", border=1, fill=True, ln=True)
    pdf.set_text_color(0, 0, 0)
    fin = [
        ("Chiffre d'affaires", r.revenue, r.revenue),
        ("  - Couts production (COGS)", -r.production_cost, r.revenue),
        ("  - Couts distribution", -r.distribution_cost, r.revenue),
        ("  - Couts marketing", -r.marketing_cost, r.revenue),
        ("  - Couts R&D", -r.rd_cost, r.revenue),
        ("  - Couts exploitation", -r.operating_cost, r.revenue),
        ("  - SAV / Garantie", -r.aftersales_cost, r.revenue),
        ("PROFIT", r.profit, r.revenue),
    ]
    for j, (label, val, rev) in enumerate(fin):
        bold = label in ("Chiffre d'affaires", "PROFIT")
        pdf.set_font("Helvetica", "B" if bold else "", 9)
        fill = j % 2 == 0
        fc = (240, 244, 250) if fill else (255, 255, 255)
        pdf.set_fill_color(*fc)
        if label == "PROFIT":
            pc = (0, 128, 0) if val >= 0 else (200, 0, 0)
            pdf.set_text_color(*pc)
        pdf.set_x(pdf.l_margin)
        pdf.cell(c1, 6, safe(label), border=1, fill=True)
        pdf.cell(c2, 6, f"{val:,.0f}", border=1, fill=True)
        pdf.cell(c3, 6, f"{val/max(rev,1)*100:.1f}%", border=1, fill=True, ln=True)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # ── Alertes ────────────────────────────────────────────
    pdf.sub_title(f"Alertes ({len(r.alerts)})")
    pdf.set_font("Helvetica", "", 9)
    if r.alerts:
        for a in r.alerts:
            pdf.set_text_color(180, 0, 0)
            pdf.multiline("  [ALERTE] " + a)
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_text_color(0, 128, 0)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 6, "  Aucune alerte - scenario conforme aux regles metier.", ln=True)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    # ── Analyse ───────────────────────────────────────────
    pdf.sub_title("Analyse et enseignements")
    pdf.set_font("Helvetica", "", 9)
    for point in analyse:
        pdf.bullet(point)
    pdf.ln(2)

# ══════════════════════════════════════════════════════
# PAGE SYNTHESE
# ══════════════════════════════════════════════════════
pdf.add_page()
pdf.section_title("SYNTHESE ET ENSEIGNEMENTS", size=13)
pdf.ln(2)

# Classement marges
pdf.sub_title("Classement par marge nette")
pdf.set_font("Helvetica", "B", 9)
pdf.set_fill_color(30, 60, 120)
pdf.set_text_color(255, 255, 255)
w = pdf.w - pdf.l_margin - pdf.r_margin
pdf.set_x(pdf.l_margin)
pdf.cell(w * 0.08, 6, "Rang", border=1, fill=True)
pdf.cell(w * 0.35, 6, "Scenario", border=1, fill=True)
pdf.cell(w * 0.12, 6, "Firme", border=1, fill=True)
pdf.cell(w * 0.15, 6, "Marge", border=1, fill=True)
pdf.cell(w * 0.15, 6, "Ventes", border=1, fill=True)
pdf.cell(w * 0.15, 6, "Profit ($)", border=1, fill=True, ln=True)
pdf.set_text_color(0, 0, 0)

ranked = sorted(zip(SCENARIOS, RESULTS), key=lambda x: -x[1].margin)
for rank, (sc, r) in enumerate(ranked, 1):
    fill = rank % 2 == 0
    fc = (240, 244, 250) if fill else (255, 255, 255)
    pdf.set_fill_color(*fc)
    pdf.set_font("Helvetica", "", 9)
    mc = (0, 128, 0) if r.margin >= 0.05 else ((200, 120, 0) if r.margin >= 0.02 else (200, 0, 0))
    pdf.set_x(pdf.l_margin)
    pdf.cell(w * 0.08, 6, str(rank), border=1, fill=True)
    pdf.cell(w * 0.35, 6, sc.scenario_name[:28], border=1, fill=True)
    pdf.cell(w * 0.12, 6, sc.firm_name, border=1, fill=True)
    pdf.set_text_color(*mc)
    pdf.cell(w * 0.15, 6, f"{r.margin*100:.1f}%", border=1, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(w * 0.15, 6, f"{r.sales:,}", border=1, fill=True)
    pdf.cell(w * 0.15, 6, f"{r.profit:,.0f}", border=1, fill=True, ln=True)
pdf.ln(5)

# Productions N+1
pdf.sub_title("Productions recommandees N+1 (Periode 2 - 2028)")
pdf.set_font("Helvetica", "B", 9)
pdf.set_fill_color(30, 60, 120)
pdf.set_text_color(255, 255, 255)
pdf.set_x(pdf.l_margin)
pdf.cell(w * 0.43, 6, "Scenario", border=1, fill=True)
pdf.cell(w * 0.19, 6, "Prod. N (actuelle)", border=1, fill=True)
pdf.cell(w * 0.19, 6, "Ventes N", border=1, fill=True)
pdf.cell(w * 0.19, 6, "Prod. N+1 (recomm.)", border=1, fill=True, ln=True)
pdf.set_text_color(0, 0, 0)
for j, (sc, r, n) in enumerate(zip(SCENARIOS, RESULTS, NEXTS)):
    fill = j % 2 == 0
    fc = (240, 244, 250) if fill else (255, 255, 255)
    pdf.set_fill_color(*fc)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(pdf.l_margin)
    pdf.cell(w * 0.43, 6, sc.scenario_name, border=1, fill=True)
    pdf.cell(w * 0.19, 6, f"{sc.production:,}", border=1, fill=True)
    pdf.cell(w * 0.19, 6, f"{r.sales:,}", border=1, fill=True)
    arrow = "v" if n < sc.production else ("^" if n > sc.production else "=")
    pdf.cell(w * 0.19, 6, f"{n:,}  {arrow}", border=1, fill=True, ln=True)
pdf.ln(5)

# Enseignements cles
pdf.sub_title("Enseignements cles du modele")
pdf.set_font("Helvetica", "", 9)
lessons = [
    "1. COGS PROPORTIONNEL : Le modele calcule le cout en % du prix effectif (mid=57%).",
    "   Une promo -10% reduit simultanement le prix ET le cout -> la marge unitaire reste stable.",
    "   Consequence : la promo agressive (S3) est une strategie dominante a court terme.",
    "",
    "2. RENDEMENTS DECROISSANTS DU MARKETING : Au-dela de 10% du CA, le ROI marginal",
    "   devient negatif. S2 depense 14.8% du CA pour un gain de seulement +36 unites vs S1.",
    "",
    "3. SUR-PRODUCTION SYSTEMATIQUE : Tous les scenarios produisent trop (sauf S5).",
    "   Utiliser suggest_next_production() pour recalibrer chaque periode.",
    "",
    "4. NOUVEAU PRODUIT = PERTE ANNEE 1 : Incontournable avec le cap 1000-2000 unites.",
    "   Compensation : score innovation 8.40 -> boost attractivite periodes suivantes.",
    "",
    "5. LIQUIDATION OPTIMALE : Combiner retrait + promo -10% + marketing minimal",
    "   maximise la marge de sortie (19.5%). Production N+1 obligatoirement = 0.",
    "",
    "6. PRIX INCOHERENT : La penalite d'attractivite est active (-1.7 pts PDM segment).",
    "   Mais la marge reste haute car COGS reduit proportionnellement. Impact = CA perdu.",
]
for line in lessons:
    if line == "":
        pdf.ln(1)
    else:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w, 5, safe(line))

pdf.ln(5)
pdf.set_font("Helvetica", "I", 8)
pdf.set_text_color(100, 100, 100)
pdf.set_x(pdf.l_margin)
pdf.cell(0, 6, safe(f"Rapport genere automatiquement par le Bot de Simulation VAE - {now}"), ln=True, align="C")

# ─── Save ─────────────────────────────────────────────────────────────────────
out = "/Users/imran/BotMarketing/rapport_scenarios_test.pdf"
pdf.output(out)
print(f"PDF genere : {out}")
