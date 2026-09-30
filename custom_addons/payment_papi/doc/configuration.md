# Configuration de Papi dans Odoo

## 1. Récupérer les identifiants dans le dashboard Papi

Sur [dashboard.papi.mg](https://dashboard.papi.mg) :

| Donnée | Où la trouver | Format |
|---|---|---|
| **Clé API** | Avatar → **Boutiques** → sélectionner la boutique → onglet **Développeur** | Chaîne opaque. **Une clé = une boutique.** |
| **Secret de signature des notifications** | Page de l'application → onglet **Développeur** → « Secret de signature des notifications (X-Papi-Signature) » | `pwhsec_` suivi de 64 caractères hexadécimaux |

Ces deux valeurs sont **confidentielles**. Dans Odoo, elles ne sont visibles et modifiables que par les administrateurs (groupe *Paramètres*). Elles ne sont jamais écrites dans les journaux.

## 2. Configurer le fournisseur dans Odoo

**Facturation/Comptabilité → Configuration → Fournisseurs de paiement → Papi**, ou **Site web → Configuration → Fournisseurs de paiement**.

### Onglet « Identifiants »

| Champ | Valeur |
|---|---|
| **Boutique Papi** | Nom de la boutique, à titre informatif (ex. « Ma Boutique Tana ») |
| **Clé API** | La clé API de la boutique |
| **Secret de signature des notifications** | Le secret `pwhsec_…` |
| **Validité du lien de paiement (heures)** | De 1 à 596. Par défaut : 1 h. Durée pendant laquelle le client peut payer. Au-delà, la transaction est annulée. |
| **URL de l'API Papi** | Visible en mode développeur uniquement. Par défaut `https://app.papi.mg/engine/api/`. Ne modifier que sur instruction de Papi. |

Cliquer sur **« Tester la connexion »** : un message vert confirme que Papi accepte la clé API. C'est le « statut de la configuration » demandé.

### État (environnement)

| État Odoo | Effet côté Papi |
|---|---|
| **Désactivé** | Papi n'est pas proposé |
| **Test** | Papi n'est proposé qu'aux utilisateurs internes connectés. Les liens sont créés avec `isTestMode=true`. ⚠️ **Papi n'a pas de sandbox : les paiements mobile money en mode test débitent réellement le payeur.** Pour tester sans mouvement d'argent, activer le « Test Mode » de la boutique dans le dashboard Papi et payer avec la carte de test `4000 0000 0000 5126`, exp. `01/2028`, CVV `123`. |
| **Activé** | Production |

Le bouton **Publier / Dépublier** contrôle l'affichage sur le site web (mode de publication).

### Onglet « Configuration »

| Champ | Valeur recommandée |
|---|---|
| Moyens de paiement | « Papi (Mobile Money, carte) », activé automatiquement |
| Devises | **MGA**, préréglé. Papi n'est de toute façon jamais proposé dans une autre devise. |
| Pays | **Madagascar**, préréglé. Vider le champ pour proposer Papi aux clients de tous pays (paiement en MGA uniquement). |
| Montant maximum | Selon le plafond de la boutique Papi |

Le **montant minimum de 300 MGA** est appliqué automatiquement : en dessous, Papi n'est pas proposé.

### Onglet « Configuration » → Journal (si `account_payment` est installé)

Choisir le **journal de paiement** dans lequel Odoo enregistre les paiements Papi (ex. un journal « Papi » de type Banque). Il servira au rapprochement avec les règlements Papi.

## 3. Vérifier l'URL publique d'Odoo

Papi appelle Odoo sur `https://<votre-domaine>/payment/papi/webhook`. Vérifier que :

- le paramètre système `web.base.url` contient bien l'URL publique HTTPS ;
- `web.base.url.freeze` vaut `True` si l'administrateur se connecte parfois via une autre URL.

Détails dans [urls_callback.md](urls_callback.md).

## 4. Données transmises à Papi

Seules les données nécessaires au paiement et au rapprochement sont envoyées :

| Donnée | Source Odoo |
|---|---|
| `amount`, `currency` | Montant et devise de la transaction |
| `reference` | Référence de la transaction Odoo (ex. `S00042`, `INV-2026-00001`) |
| `description` | « Nom de la société - référence » |
| `clientName`, `payerEmail`, `payerPhone` | Nom, e-mail et téléphone du client. Le téléphone n'est envoyé que s'il est au format malgache. |
| `successUrl`, `failureUrl`, `notificationUrl` | URLs Odoo |
| `validDuration` | Paramètre du fournisseur |

Aucune donnée KYC, aucun document marchand et aucune donnée de carte ne transite par Odoo.
