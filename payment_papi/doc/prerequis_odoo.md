# Prérequis Odoo

## Versions et édition

| Élément | Exigence |
|---|---|
| Odoo | **17.0, 18.0, 19.0 ou 20.0** (un paquet par version). Community testé, Enterprise non testé (voir [compatibilite.md](compatibilite.md)) |
| Python | 3.10 ou plus (testé en 3.11 pour Odoo 17, en 3.12 pour Odoo 18, 19 et 20), dépendances standard d'Odoo (`requests`) |
| PostgreSQL | Version supportée par Odoo 18 |
| Hébergement | Odoo.sh ou auto-hébergé. **Odoo Online (SaaS) ne permet pas d'installer de modules tiers : ce module n'y est pas installable.** |

## Applications Odoo

| Module | Rôle | Installation |
|---|---|---|
| `payment` | Fournisseurs et transactions de paiement | Dépendance |
| `account_payment` | Paiement des factures sur le portail, bouton « Pay with Papi » des factures | Dépendance (installé avec `payment_papi`) |
| `website_sale` | Paiement à l'étape de paiement du site e-commerce | À installer pour l'e-commerce |
| `sale` | Devis et commandes ; ajoute le bouton « Pay with Papi » via `payment_papi_sale` | Optionnel, la passerelle `payment_papi_sale` s'installe seule |

## Configuration Odoo

- **Devise MGA (Ariary)** activée ; le module la réactive à l'installation. Papi n'est proposé que pour des montants en MGA, d'au moins 300 Ar.
- **Liste de prix** en MGA, sélectionnable, pour l'e-commerce (créée automatiquement s'il n'en existe aucune en MGA).
- **`web.base.url`** : URL publique HTTPS. En développement, utiliser un tunnel (par exemple `ngrok http 8069`).
- Derrière un proxy inverse : `proxy_mode = True`, corps de la requête transmis sans modification, en-tête `X-Papi-Signature` conservé.
- Tâche planifiée **« Papi: synchronize pending transactions »** active.
- Un **journal de paiement** (type Banque) pour le fournisseur, afin de rapprocher les paiements Papi.

## Réseau

- Entrant : HTTPS vers `/payment/papi/webhook`, sans filtrage par adresse IP (Papi ne publie pas de plage) et sans blocage du `User-Agent` `PAPI-Callback/1.0`.
- Sortant : HTTPS (443) vers `https://app.papi.mg`.

## Compte Papi

Boutique vérifiée, clé API de la boutique et secret de signature des notifications (voir [configuration.md](configuration.md)).
