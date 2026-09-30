# Matrice de compatibilité

| | Odoo 16.0 | Odoo 17.0 | **Odoo 18.0** | Odoo 19.0 |
|---|---|---|---|---|
| Module `payment_papi` 18.0.1.0.0 | ❌ | ❌ (portage prévu) | ✅ **Testé** | ❌ (portage à évaluer) |
| Community | – | – | ✅ | – |
| Enterprise | – | – | ✅ | – |

| Hébergement | Supporté | Remarque |
|---|---|---|
| Auto-hébergé (on-premise, VPS) | ✅ | URL publique HTTPS requise pour les notifications |
| Odoo.sh | ✅ | Neutralisation automatique des bases de staging |
| **Odoo Online (SaaS)** | ❌ | **Les modules tiers ne peuvent pas être installés sur Odoo Online.** Seule alternative : des liens de paiement Papi créés depuis le dashboard Papi. Ce n'est pas une intégration native : pas de confirmation automatique de commande. |

| Application Odoo | Supporté en v1 | Remarque |
|---|---|---|
| Site web / e-commerce (`website_sale`) | ✅ | Étape de paiement du checkout |
| Paiement des factures sur le portail (`account_payment`) | ✅ | Référence `INV-AAAA-NNNNN` distincte des commandes |
| Devis en ligne (`sale`) | ✅ | Paiement à la signature |
| Liens de paiement générés depuis le back-office | ✅ | |
| Point de vente (`point_of_sale`) | ❌ | Hors périmètre v1 |
| Abonnements, paiements récurrents | ❌ | Papi ne propose pas de tokenisation |
| Remboursements depuis Odoo | ❌ | Pas d'API de remboursement Papi |
| Multi-société | ✅ | Un fournisseur par société, chacun avec sa propre clé ou boutique |
| Multi-site web | ✅ | Champ standard « Site web » du fournisseur |

| Contrainte Papi | Valeur |
|---|---|
| Devise | MGA uniquement |
| Montant minimum | 300 MGA |
| Validité du lien | 1 à 596 heures |
| Instruments | MVola, Orange Money, Airtel Money, carte (BRED) |

*Testé avec Odoo 18.0 (commit `87872ab5f9`, 29/09/2026), Python 3.12 et PostgreSQL.*
