# Étude technique préalable — Intégration Papi pour Odoo

*Version 1.0 — 30 septembre 2026 — module `payment_papi` 18.0.1.0.0*

Cette étude répond aux cinq « questions préalables » du cahier des charges. Elle s'appuie sur la documentation publique de Papi (docs.papi.mg, consultée le 30/09/2026) et sur le code source d'Odoo 18.0.

---

## 1. Versions Odoo ciblées

| Version | Statut | Justification |
|---|---|---|
| **18.0** | **Cible v1, développée et testée** | Version stable courante, supportée par Odoo S.A. jusqu'à fin 2027. Le module suit exactement l'API `payment` de la 18.0, sur le modèle des modules officiels `payment_flutterwave` et `payment_xendit`. |
| 17.0 | **Porté et testé** (95 tests, 0 échec) | L'API `payment` est quasi identique. Adaptations : contrôle d'accès (`check_access_rights`/`check_access_rule`), pas de rapport de disponibilité (`report`), post-traitement `_finalize_post_processing`, valeurs de `support_refund`, URL de retour du back-office. |
| 19.0 | **Porté et testé** (95 tests, 0 échec) | La 19.0 refond le flux de notification : `_process` / `_extract_reference` / `_apply_updates` à la place de `_handle_notification_data` / `_process_notification_data`, et la signature de `_compute_reference_prefix`. Adaptations de la couche transaction et du contrôleur ; vue de recherche ; un paiement ne confirme plus une commande qui doit être signée. |
| ≤ 16.0 | Non recommandé | Pas de modèle `payment.method` (introduit en 17), donc un flux différent. Le parc Madagascar sur ces versions ne justifie pas l'effort. |

**Réalisé :** la 18.0 (référence), puis les portages 17.0 et 19.0, installés sur base vide et validés par les mêmes 95 tests. Voir [compatibilite.md](compatibilite.md) pour le détail des différences et l'avertissement Enterprise (non testé).

## 2. Fonctionnalités réellement exposées par l'API Papi

| Besoin du cahier des charges | Disponible dans l'API Papi | Utilisation dans le module |
|---|---|---|
| Créer une transaction et rediriger le client | `POST /engine/api/payment-links` → `paymentLink` | Oui : redirection vers `payment-form.papi.mg` |
| Transmettre montant, devise et référence | `amount` (≥ 300), `currency` (MGA seul), `reference` | Oui. La référence Odoo **est** la référence marchande Papi |
| Métadonnées libres | **Non** : pas de champ `metadata` | La référence Odoo est portée par `reference` et rappelée dans `description` |
| Identification client | `clientName`, `payerEmail`, `payerPhone` | Oui (le téléphone n'est envoyé que s'il est au format malgache valide) |
| Choix de l'instrument | `provider` (MVOLA, AIRTEL_MONEY, ORANGE_MONEY, BRED) optionnel | Non envoyé : le client choisit sur la page Papi |
| URL de retour | `successUrl` et `failureUrl` (obligatoirement ensemble) | Une seule route Odoo, `/payment/papi/return` |
| URL d'annulation | **Non** | L'annulation est détectée par l'expiration du lien |
| Callback serveur à serveur | `notificationUrl`, signé HMAC-SHA256 (`X-Papi-Signature`) | Oui : `/payment/papi/webhook` |
| Relance des callbacks | **Non : notification envoyée une seule fois** | Tâche planifiée toutes les 15 min |
| Interrogation du statut | `GET /engine/api/payment-links/{reference}` | Oui : retour client, webhook, cron, bouton manuel |
| Idempotence de la création | Oui, sur `reference`, tant que le lien est actif | Exploitée : un retry renvoie le même lien |
| Environnement de test | **Pas de sandbox.** `isTestMode` marque la transaction mais **l'argent circule** pour le mobile money. Le « Test Mode » de la boutique fonctionne pour les cartes uniquement (carte 4000 0000 0000 5126). | État Odoo « Test » → `isTestMode=true`, avec un avertissement dans le formulaire |
| Remboursement | **Non exposé** | Hors périmètre, à traiter depuis le back-office Papi |
| Liste des boutiques | **Non** : une clé API = une boutique | La boutique est déterminée par la clé ; le champ « Boutique Papi » est informatif |
| Tokenisation / paiement récurrent | Non | Non supporté (masqué pour les validations) |

### Statuts exposés et correspondance Odoo

L'API renvoie deux statuts : `linkStatus` ∈ {ACTIVE, PAID, EXPIRED, DISABLED} et `paymentStatus` ∈ {SUCCESS, PENDING, FAILED, null}.

| linkStatus | paymentStatus | Signification Papi | Transaction Odoo | Commande / facture |
|---|---|---|---|---|
| PAID (ou ACTIVE) | SUCCESS | Paiement abouti | `done` | Confirmée ou payée (post-traitement standard) |
| ACTIVE | PENDING | Paiement en cours chez l'opérateur | `pending` | Non confirmée, devis envoyé |
| ACTIVE | null | Aucune tentative encore | `draft` (inchangé) | Non confirmée |
| ACTIVE | FAILED | Tentative refusée, nouvel essai possible sur le même lien | `error` (récupérable : un SUCCESS ultérieur passe en `done`) | Non confirmée |
| EXPIRED | null ou FAILED | Lien expiré ou abandon | `cancel` | Non confirmée |
| DISABLED | null ou FAILED | Lien désactivé par le marchand | `cancel` | Non confirmée |
| autre | autre | Statut inconnu ou incohérent | Inchangé, erreur journalisée | Non confirmée |
| * | * + incohérence de montant, devise, référence ou token | Données incohérentes | `error`, message explicite | Non confirmée |

## 3. Proportion de clients Odoo sur Odoo.sh ou auto-hébergés

**Aucune donnée publique fiable** ne donne cette répartition, ni au niveau mondial ni pour Madagascar. Odoo S.A. ne publie pas la ventilation Online / Odoo.sh / On-premise. Éléments qualitatifs :

- Odoo Online (SaaS) est l'offre par défaut des petites structures. **Il n'accepte pas de modules tiers.** Ces clients ne sont donc pas adressables par ce module.
- Les intégrateurs malgaches déploient majoritairement en auto-hébergé (VPS local ou OVH/Hetzner) ou sur Odoo.sh. Ce sont précisément les profils e-commerce qui ont besoin d'un fournisseur de paiement local.

**Action proposée :** collecter la donnée côté commercial, avec un questionnaire auprès des intégrateurs partenaires et des marchands Papi déjà sous Odoo, avant de dimensionner l'effort sur une solution Odoo Online.

## 4. Publication sur l'Odoo Apps Store

- **Possible.** Il faut un compte éditeur, un dépôt Git public ou privé relié à apps.odoo.com, une branche par version (`18.0`), un `__manifest__.py` complet (licence, auteur, images) et une page `static/description/index.html`. Ces éléments sont fournis.
- Licence choisie : **LGPL-3**, cohérente avec les modules `payment_*` d'Odoo. Le module peut être gratuit, ce qui est recommandé pour maximiser l'adoption, Papi se rémunérant sur les frais de transaction.
- Odoo teste automatiquement l'installabilité : le module ne dépend que de `payment`.
- `icon.png` et `papi.png` reprennent le symbole nuage du logo Papi fourni. La bannière (`banner.png`) est encore provisoire et **doit être validée par Papi** avant publication.

## 5. Intérêt d'une v1 limitée au e-commerce et aux factures

**Recommandé.** Le module s'appuie sur le socle `payment` d'Odoo, qui est partagé :

- **e-commerce** (`website_sale`) : checkout `/shop/payment` ;
- **factures portail** (`account_payment`) : bouton « Payer » sur `/my/invoices` ;
- **devis en ligne** (`sale`) : paiement à la signature ;
- **liens de paiement** générés depuis le back-office (« Générer un lien de paiement »).

Ces quatre usages fonctionnent **sans code supplémentaire**. Les références restent séparées nativement : `S00042` pour une commande, `INV-2026-00001` pour une facture. Le module remplace `/` par `-` pour rester compatible avec l'URL de statut Papi.

Hors v1 : Point de Vente (flux synchrone différent), remboursements (API absente), abonnements (pas de tokenisation).

## Risques et points à valider avec Papi

1. **Notification unique.** Elle est compensée par la tâche planifiée. Une relance automatique côté Papi serait souhaitable.
2. **Pas de sandbox mobile money.** Les tests de bout en bout en mobile money coûtent de l'argent réel. Demander un environnement de recette à Papi.
3. **Pas d'URL d'annulation.** Un client qui abandonne laisse la transaction en « brouillon » jusqu'à l'expiration du lien (1 h par défaut).
4. **Unicité des références entre bases.** Une base de recette copiée de la production avec la même clé API pourrait réutiliser des références. Odoo.sh neutralise les bases de staging (clé et secret effacés par `data/neutralize.sql`). En auto-hébergé, utiliser une boutique Papi distincte pour la recette.
5. **Amortissement des frais.** Le champ `fee` de la notification n'est pas repris en comptabilité (règlements hors périmètre).
