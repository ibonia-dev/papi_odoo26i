# Matrice de compatibilité

| | Odoo 16.0 | Odoo 17.0 | **Odoo 18.0** | Odoo 19.0 | Odoo 20.0 |
|---|---|---|---|---|---|
| Module `payment_papi` | ❌ | ✅ **17.0.1.0.2** | ✅ **18.0.1.0.2** | ✅ **19.0.1.0.2** | ✅ **20.0.1.0.0** |
| Installation sur base vide | – | ✅ | ✅ | ✅ | ✅ |
| Tests automatisés (95) | – | ✅ 0 échec | ✅ 0 échec | ✅ 0 échec | ✅ 0 échec |
| Community | – | ✅ testé | ✅ testé | ✅ testé | ✅ testé |
| Enterprise | – | ⚠️ non testé | ⚠️ non testé | ⚠️ non testé | ⚠️ non testé |

Un paquet par version d'Odoo : `payment_papi-17.0.1.0.0.zip`, `payment_papi-18.0.1.0.0.zip`, `payment_papi-19.0.1.0.0.zip`, `payment_papi-20.0.1.0.0.zip` (dossier `dist/`), chacun avec le module passerelle `payment_papi_sale`. **Il ne faut pas installer la mauvaise version** : les API `payment` diffèrent entre versions (voir ci-dessous). Le module n'utilise que l'API publique du module `payment`, mais le code Enterprise n'étant pas disponible, aucun test n'a été fait sur Enterprise.

### Différences entre les versions

| Sujet | 17.0 | 18.0 | 19.0 | 20.0 |
|---|---|---|---|---|
| Traitement des données Papi | `_get_tx_from_notification_data`, `_process_notification_data` | idem | `_extract_reference`, `_extract_amount_data`, `_apply_updates` ; entrée `_process` | `_record` (file d'attente `payment.data`, traitée par une tâche planifiée), `_extract_reference`, `_apply_updates` ; les écritures sur la transaction exigent `payment_safe_write` |
| Post-traitement | `_finalize_post_processing` (transactions `done` seulement) | `_post_process` | `_post_process` | `_post_process` (tâche `payment.post_processing_cron`) |
| Rapport de disponibilité des fournisseurs (`report`) | absent | présent | présent | présent, via `_find_available_providers` (remplace `_get_compatible_providers`) |
| Contrôle d'accès | `check_access_rights` + `check_access_rule` | `check_access` | `check_access` | `check_access` |
| Retour de l'opérateur (back-office) | `/web#id=…&model=…&view_type=form` | `/odoo/<modèle>/<id>` | `/odoo/<modèle>/<id>` | `/odoo/<modèle>/<id>` |
| Lien de paiement d'une facture | `/payment/pay` | page de la facture sur le portail | page de la facture sur le portail | page de la facture sur le portail |
| Lien de paiement d'une commande | `/payment/pay` | `/payment/pay` | page de la commande sur le portail (`/my/orders/<id>`) | page de la commande sur le portail (`/my/orders/<id>`) |
| Moyen de paiement : `support_refund` | valeurs `full_only` / `partial` | valeur `none` possible | valeur `none` possible | valeur `none` possible |
| Paiement d'une commande à signer | confirme la commande | confirme la commande | **ne confirme pas** une commande qui doit encore être signée (comportement standard d'Odoo 19) | **ne confirme pas** une commande qui doit encore être signée (comportement standard d'Odoo 19 et 20) |

**Spécificités d'Odoo 20 :** l'état du fournisseur (`state` : désactivé / activé / test) est remplacé par `active` et `is_live` (mode test = `not is_live`) ; les moyens de paiement sont propres à un fournisseur (`provider_id` obligatoire) ; les droits d'accès sont dans `security/ir.access.csv` ; les champs à renseigner (`required_if_provider`) ne sont exigés qu'en mode production.

*Testé avec : Odoo 17.0, 19.0 et 20.0 (archives GitHub du 01/10/2026), Odoo 18.0 (commit `87872ab5f9`), Python 3.11 (17), 3.12 (18, 19 et 20), PostgreSQL, Community.*

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
| Bouton « Pay with Papi » sur les factures et les commandes (l'opérateur paie à la place du client) | ✅ | Factures : `account_payment` (dépendance). Commandes : module passerelle `payment_papi_sale`, installé automatiquement avec `sale`. |
| Assistant standard « Générer un lien de paiement » | ✅ | Vérifié par des tests : Papi est proposé sur la page du lien (facture ou commande) |
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

