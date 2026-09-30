# Installation du module Papi pour Odoo

## Prérequis

| Élément | Exigence |
|---|---|
| Odoo | **18.0** Community ou Enterprise (voir [compatibilite.md](compatibilite.md)) |
| Hébergement | **Odoo.sh** ou **auto-hébergé**. **Odoo Online (SaaS) n'est pas supporté** : il n'accepte pas de modules tiers. |
| Python | Dépendances standard d'Odoo uniquement (`requests`) |
| Modules Odoo | `payment` (installé automatiquement). Pour l'usage : `website_sale` (e-commerce) et/ou `account_payment` (paiement des factures sur le portail) |
| Devise | **MGA (Ariary)** activée et utilisée par la liste de prix du site ou par les factures |
| Réseau | Odoo doit être **joignable en HTTPS depuis Internet** (URL de callback). Il doit aussi pouvoir joindre `https://app.papi.mg` en sortie (port 443). |
| Paramètre `web.base.url` | Doit contenir l'URL publique HTTPS (ex. `https://boutique.example.mg`). En cas de proxy inverse, lancer Odoo avec `proxy_mode = True`. |
| Compte Papi | Boutique vérifiée, avec clé API et secret de signature des notifications (voir [configuration.md](configuration.md)) |

## Installation auto-hébergée

1. Copier le dossier `payment_papi` dans un répertoire d'addons, par exemple `/opt/odoo/custom_addons/payment_papi`.
2. Ajouter ce répertoire au paramètre `addons_path` du fichier de configuration Odoo :
   ```ini
   addons_path = /opt/odoo/odoo/addons,/opt/odoo/addons,/opt/odoo/custom_addons
   ```
3. Redémarrer le service Odoo.
4. Dans Odoo : **Applications → Mettre à jour la liste des applications**, rechercher « Papi », puis cliquer sur **Activer**.
   En ligne de commande, l'équivalent est :
   ```bash
   odoo-bin -c odoo.conf -d <base> -i payment_papi --stop-after-init
   ```
5. S'assurer que la tâche planifiée **« Papi: synchronize pending transactions »** est active (Paramètres → Technique → Actions planifiées). Elle est active par défaut.

## Installation sur Odoo.sh

1. Ajouter le module dans le dépôt Git du projet, à la racine ou dans un sous-module :
   ```
   <repo>/payment_papi/
   ```
2. Pousser la branche. Odoo.sh détecte le module automatiquement.
3. Installer le module depuis **Applications** sur la branche de staging, tester, puis fusionner en production.
4. Les bases de staging et de développement sont **neutralisées** automatiquement : la clé API et le secret sont effacés et le fournisseur est désactivé. Saisir une clé de test dans ces bases si nécessaire.

## Mise à jour

```bash
odoo-bin -c odoo.conf -d <base> -u payment_papi --stop-after-init
```
Les données de configuration (clé, secret, boutique) sont conservées : les enregistrements sont déclarés en `noupdate`.

## Désinstallation

La désinstallation remet le fournisseur Papi en état « désactivé » (`code = none`). Les transactions existantes et leurs références Papi restent consultables dans Odoo.
