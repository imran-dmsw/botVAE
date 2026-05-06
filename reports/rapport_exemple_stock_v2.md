# Rapport de simulation VAE
**Généré le :** 2026-05-05 23:36  |  **Statut :** ✅ Valide

---

## 1. Résumé exécutif

| Indicateur | Valeur |
|---|---|
| Firme | AVE |
| Période | 1 |
| Scénario | Equilibre_Optimal |
| Ventes | 1,500 unités |
| Chiffre d'affaires | 4,704,000 $ |
| Profit | 1,103,070 $ |
| Profit rate | 23.45% (tres_bon) |
| Marge | 23.4% |
| Part de marché totale | 1.22% |
| Part de marché segment (Urbains Pressés) | 4.06% |
| Taux de service | 71.0% |
| Score innovation | 5.2/10 |
| Score durabilité | 4.6/10 |

---

## 2. Hypothèses du scénario

- **Modèle :** AVE-SwiftRide M1 (Milieu de gamme, segment Urbains Pressés)
- **Statut produit :** active
- **Prix :** 3,200 $ (promotion : -2.0%)
- **Production :** 1,500 unités
- **Budget marketing :** 81,600 $ (45.3% du plafond)
  - Digital : 32,000 $
  - Réseaux sociaux : 20,000 $
  - Influenceurs : 12,000 $
  - Affichage : 8,000 $
  - Événements : 8,000 $
- **Budget R&D :** 15,000 $ (15.6% du plafond) | Projets : 0
- **Investissement durabilité :** 0 $
- **Budget ajusté de référence :** 1,200,000 $

---

## 3. Résultats financiers détaillés

| Poste | Montant (CAD) | % du CA |
|---|---|---|
| Chiffre d'affaires | 4,704,000 $ | 100.0% |
| Coûts de production | -2,868,970 $ | 61.0% |
| Coûts de distribution | -423,360 $ | 9.0% |
| Coûts marketing | -81,600 $ | 1.7% |
| Coûts R&D | -15,000 $ | 0.3% |
| Coûts d'exploitation | -140,000 $ | 3.0% |
| SAV / Garantie | -72,000 $ | 1.5% |
| Durabilité | -0 $ | 0.0% |
| **Total coûts** | **-3,600,930 $** | **76.6%** |
| **Profit** | **1,103,070 $** | **23.4%** |

---

## 4. Alertes

- ⚠️ La somme des canaux marketing (80,000 $) ne correspond pas au budget total declare (81,600 $). Les canaux ont ete normalises automatiquement.
- ⚠️ [Stock] Alerte rupture : votre production ne couvre pas suffisamment la demande prévue.
- ⚠️ [Stock] Risque important de ventes perdues et de perte de part de marché (29.0 % de la demande non servie).

---

## 5. Controles metier

- Cohérence prix/gamme : **ok**
- Promo valide : **oui**
- Profit cible 5-10% : **non**
- Efficacite marketing : **0.0184 ventes/$**
- Efficacite production : **100.0%**
- Production recommandee N+1 : **1,848**
- Limite retrait produit : **ok**

---

## 6. Production, demande et gestion du stock

| Indicateur | Valeur scénario |
|---|---|
| Stock disponible prévu | 1,500 unités |
| Taux de couverture prévu | 71.0% |
| Ventes perdues estimées | 611.5 unités |
| Stock final prévu | 0 unités |
| Coût de stockage estimé | 0 $ |

### Tableau principal des seuils d'alerte

| Indicateur | Seuil | Niveau d'alerte | Message à afficher à l'étudiant | Décision possible |
|---|---|---|---|---|
| Taux de couverture prévu | < 90 % | Rouge | Risque élevé de ventes perdues : la production semble insuffisante. Risque important de ventes perdues et de perte de part de marché. | Augmenter la production ou accepter volontairement une stratégie prudente. |
| Taux de couverture prévu | 90 % à 99 % | Orange | Production prudente : risque modéré de rupture si la demande se réalise. | Ajuster légèrement à la hausse si l'objectif est de gagner des parts de marché. |
| Taux de couverture prévu | 100 % à 110 % | Vert | Production équilibrée : bon compromis entre disponibilité et stock. | Maintenir la décision, sauf si le produit est très risqué ou coûteux à stocker. |
| Taux de couverture prévu | 111 % à 120 % | Jaune | Production sécuritaire : stock possible si la demande est plus faible que prévue. | Vérifier le coût de stockage avant de confirmer. |
| Taux de couverture prévu | > 120 % | Rouge | Risque de surproduction : stock final potentiellement élevé (coût de stockage important et risque d'invendus). | Réduire la production, sauf stratégie volontaire de disponibilité élevée. |
| Ventes perdues estimées | > 10 % de la demande prévue | Orange/Rouge | Risque important de ventes perdues et de perte de part de marché. | Augmenter la production si la marge unitaire est attractive. |

### Messages d'alerte à intégrer dans la feuille de résultats

- Alerte rupture : votre production ne couvre pas suffisamment la demande prévue.

---

## 7. Analyse et interprétation

- Excellente rentabilite : marge de 23.4% - au-dessus de la zone cible (5-10%).
- Structure des couts (gamme Milieu de gamme) : COGS 57% du prix net, distribution 9% du CA hors prime ; SAV 6% + frais generaux 5% du budget ajuste (1,200,000 $).
- Budget marketing : 1.7% du CA (dans la cible 0-10%).
- Investissement R&D actif (15,000 $) : score innovation prevu a 5.2/10.
- Taux de service moyen (71%) : envisager d'augmenter la production.
- Promotion de -2% appliquee : impact direct sur la marge brute.
- Annee simulee : 2027 — taille totale du marche : 123,200 unites.
- Stock disponible prévu : 1,500 u. (départ 0 + production 1,500).
- Taux de couverture prévu : 71.0 % — ventes perdues estimées : 611.5 u. — stock final prévu : 0 u.
- Coût de stockage estimé : 0 $ (stock final × coût unitaire × 2.5 %).
- Alerte rupture : votre production ne couvre pas suffisamment la demande prévue.
- Production N+1 = max(ventes N - stock final, 0) x tendance (1.12) x ajustement (1.10) = 1,848.

---

## 8. Reference 2026

- Taille du marche 2026: **110,000** unites
- Baseline prix 2026: **3,500 $**
- Baseline part de marche firme: **1.36%**
- Baseline rentabilite: **23.45%**
- Delta CA scenario vs baseline: **-380,296,000 $**

---

## 9. Recommandations

- Marge elevee: tester une baisse moderee du prix pour gagner en part de marche.
- Le rendement marketing est faible: reallouer les depenses vers les canaux les plus performants.

---
*Rapport généré automatiquement par le Bot de Simulation VAE — 2026-05-05 23:36*