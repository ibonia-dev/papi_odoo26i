# Fiche de publication — Odoo Apps Store

À compléter avant publication. Les éléments marqués ⚠️ dépendent de décisions ou de fichiers que seul Papi peut fournir.

| Champ | Valeur |
|---|---|
| Nom technique | `payment_papi` (+ passerelle `payment_papi_sale`) |
| Titre | Payment Provider: Papi |
| Version | 17.0.1.0.0, 18.0.1.0.0, 19.0.1.0.0 et 20.0.1.0.0 (une page de l'Apps Store par version) |
| Catégorie | Accounting/Payment Providers |
| Licence | LGPL-3 (fichier `LICENSE` à la racine du module) |
| Auteur / site | Papi — https://papi.mg |
| Prix | ⚠️ À définir (gratuit ou payant) |
| Odoo Online | **Non compatible** : les modules tiers ne s'installent pas sur Odoo Online. À afficher en tête de la page commerciale. |

## Résumé court (≤ 140 caractères)

Acceptez MVola, Orange Money, Airtel Money et les cartes à Madagascar avec Papi : e-commerce, portail, back-office.

## Description (page commerciale)

**Un paiement intégré, pas un simple lien.** Papi apparaît comme fournisseur de paiement dans Odoo et suit le processus standard de commande et de facturation.

- **Client** : choisit Papi à l'étape de paiement, est redirigé vers la page Papi (MVola, Orange Money, Airtel Money ou carte), puis revient sur le site avec une confirmation conforme au statut réel.
- **Commande confirmée automatiquement** quand le paiement aboutit ; non confirmée en cas d'échec ; en attente tant que le statut n'est pas définitif.
- **Factures** payables depuis le portail client, et **bouton « Pay with Papi »** pour qu'un opérateur encaisse depuis une facture ou une commande.
- **Sécurité** : notifications signées (HMAC-SHA256), statut toujours relu via l'API Papi, montant et devise contrôlés, traitement idempotent, secrets jamais journalisés.
- **Rapprochement** : référence Papi, statuts Papi et Odoo, dates de notification, code d'erreur et bouton de diagnostic sur chaque transaction.
- Une tâche planifiée rattrape les notifications perdues (Papi n'envoie chaque notification qu'une fois).

**Prérequis** : Odoo 17.0, 18.0, 19.0 ou 20.0 (un paquet par version ; Community testé, Enterprise non testé), Odoo.sh ou auto-hébergé, devise MGA, URL publique HTTPS, compte Papi vérifié.

**Limites de la v1** : MGA uniquement (minimum 300 Ar) ; pas de point de vente, d'abonnement, de remboursement depuis Odoo ni de tokenisation ; Papi n'a pas de bac à sable (voir [configuration.md](configuration.md)).

## Visuels

| Fichier | État |
|---|---|
| `static/description/icon.png` (256×256) | Symbole nuage Papi, centré sur fond transparent (généré à partir du logo fourni) |
| `static/img/papi.png` (149×109, logo du moyen de paiement) | Symbole nuage Papi fourni |
| `static/description/banner.png` (1774×887) | ⚠️ À valider avec Papi |
| Captures d'écran (configuration du fournisseur, choix au checkout, bouton « Pay with Papi », transaction avec statuts Papi) | ⚠️ À réaliser sur une base de recette |

## Historique des versions

| Version | Contenu |
|---|---|
| 17.0 / 18.0 / 19.0 .1.0.0 | Fournisseur Papi (redirection), webhook signé, relecture du statut, tâche de rattrapage, paiement des factures sur le portail, bouton « Pay with Papi » (factures et commandes), diagnostic, documentation en français |

## Liens

Documentation : `doc/` (installation, configuration, prérequis, URLs de callback, compatibilité, plan de tests, diagnostic). Support : https://docs.papi.mg/docs/support/ (déjà indiqué dans la page `static/description/index.html`, qui est en anglais et en français).
