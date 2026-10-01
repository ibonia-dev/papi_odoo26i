# Papi pour Odoo 17, 18 et 19

Environnement de développement du module de paiement **Papi** (MVola, Orange Money, Airtel Money, carte) pour Odoo 17, 18 et 19.

| Dossier | Contenu |
|---|---|
| `custom_addons/payment_papi/` | Le module pour **Odoo 18** (référence : code, tests, `doc/` en français) |
| `ports/17.0/`, `ports/19.0/` | Les portages pour Odoo 17 et 19 (même documentation) |
| `custom_addons/payment_papi_sale/` | Passerelle installée automatiquement avec `sale` : bouton « Pay with Papi » sur les commandes |
| `odoo18/` | Sources d'Odoo 18 (non modifiées) |
| `odoo18.conf` | Configuration Odoo de développement |
| `dist/` | Archives installables, une par version d'Odoo |
| `scripts/` | `package.sh` (archives) et `test_all_versions.sh` (tests sur 17, 18 et 19) |
| `compat/`, `tools/` | Sources d'Odoo 17 et 19 avec leurs environnements Python, et `wkhtmltopdf` (non versionnés) |

## Démarrer Odoo

Depuis la racine de ce dépôt :

```bash
./venv18/bin/python odoo18/odoo-bin -c odoo18.conf -d papi
```

Puis ouvrir http://localhost:8069. Ajouter `--http-port=8079` si le port 8069 est occupé.

## Tests du module

Sur les trois versions, depuis des bases vides créées puis supprimées par le script : `scripts/test_all_versions.sh` (ou `scripts/test_all_versions.sh 18` pour une seule version). Pour une version à la main, sur une base **sans transaction existante** (le test de la tâche planifiée compte les appels à l'API pour toutes les transactions Papi de la base) :

```bash
./venv18/bin/python odoo18/odoo-bin -c odoo18.conf -d <base_de_test> -i payment_papi,payment_papi_sale \
    --test-tags /payment_papi,/payment_papi_sale --stop-after-init --http-port=8079
```

L'API Papi est simulée : aucun appel réel, aucun argent en jeu.

## Documentation

Voir [`custom_addons/payment_papi/doc/`](custom_addons/payment_papi/doc/) : installation, configuration, prérequis Odoo, URLs de retour et de callback, compatibilité, plan de tests, diagnostic, fiche Apps Store.
