# Papi pour Odoo 17.0

Fournisseur de paiement **Papi** (MVola, Orange Money, Airtel Money, carte) pour **Odoo 17.0**, à Madagascar.

Ce dépôt contient deux modules, à installer ensemble :

| Module | Rôle |
|---|---|
| `payment_papi` | Fournisseur de paiement : e-commerce, paiement des factures sur le portail, bouton « Pay with Papi » sur les factures |
| `payment_papi_sale` | Passerelle installée automatiquement avec `sale` : bouton « Pay with Papi » sur les commandes |

Branche : `17.0`. Il y a une branche par version d'Odoo (17.0, 18.0, 19.0, 20.0) : utiliser celle qui correspond à votre Odoo.

## Prérequis

- Odoo 17.0, **auto-hébergé ou Odoo.sh**. **Odoo Online (SaaS) n'est pas supporté** : il n'accepte pas de modules tiers.
- Devise **MGA** ; URL publique en HTTPS (`web.base.url`).
- Un compte Papi avec boutique vérifiée, une clé API et le secret de signature des notifications.

## Installation rapide

1. Copier les dossiers `payment_papi` et `payment_papi_sale` dans un répertoire d'addons et l'ajouter à `addons_path`.
2. Redémarrer Odoo, puis Applications → Mettre à jour la liste → installer **Papi**.
3. Configurer le fournisseur (clé API, secret) et cliquer sur « Tester la connexion ».

Documentation complète (installation, configuration, URLs de callback, diagnostic) : dossier `payment_papi/doc/`.

Licence : LGPL-3.
