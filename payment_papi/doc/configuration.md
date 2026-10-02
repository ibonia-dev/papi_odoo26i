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

Papi n'a pas de sandbox : **le mode Test d'Odoo n'est pas proposé pour l'instant**. Le sélecteur d'état n'a que deux choix, et `isTestMode` n'est jamais envoyé à Papi.

| État Odoo | Effet côté Papi |
|---|---|
| **Désactivé** | Papi n'est pas proposé |
| **Activé** | Production : les paiements sont **réels** |

⚠️ **Papi n'a pas de sandbox : les paiements Mobile Money débitent réellement le payeur.** Pour tester sans mouvement d'argent, activer le « Test Mode » de la boutique dans le dashboard Papi et payer avec la carte de test `4000 0000 0000 5126`, exp. `01/2028`, CVV `123`.

*Pour remettre le mode Test, passer `TEST_MODE_ENABLED` à `True` dans `const.py` et retirer le bloc « Papi has no sandbox » de `views/payment_provider_views.xml`.*

Le bouton **Publier / Dépublier** contrôle l'affichage sur le site web (mode de publication).

### Onglet « Configuration »

| Champ | Valeur recommandée |
|---|---|
| Moyens de paiement | « Papi (Mobile Money, carte) », activé automatiquement |
| Devises | **MGA**, préréglé. Papi n'est de toute façon jamais proposé dans une autre devise. |
| Pays | **Madagascar**, préréglé. Vider le champ pour proposer Papi aux clients de tous pays (paiement en MGA uniquement). |
| Montant maximum | Selon le plafond de la boutique Papi |

Le **montant minimum de 300 MGA** est appliqué automatiquement. En dessous, Papi reste **affiché** pour ne pas laisser le client deviner : la page de paiement montre un avertissement (« Papi ne peut pas être utilisé pour ce montant… ») et le paiement est refusé avec un message clair. Dans l'assistant « Pay with Papi » du back-office, le même avertissement apparaît et le bouton refuse le montant.

### Onglet « Configuration » → Journal (si `account_payment` est installé)

Choisir le **journal de paiement** dans lequel Odoo enregistre les paiements Papi (ex. un journal « Papi » de type Banque). Il servira au rapprochement avec les règlements Papi.

## 3. Payer avec Papi depuis le back-office

Un opérateur peut encaisser un paiement à la place du client (client au comptoir, au téléphone…) :

1. Ouvrir une **facture comptabilisée en MGA** (Facturation) ou une **commande / un devis en MGA** (Ventes), puis cliquer sur **« Pay with Papi »**. Le bouton n'apparaît que si Papi est activé, si le document est payable et si le montant est d'au moins 300 MGA.
2. Dans l'assistant, vérifier le montant (modifiable, sans dépasser le montant dû) et saisir le **numéro de mobile du payeur** (compte Mobile Money). Il est transmis à Papi pour préremplir la page ; il n'est pas enregistré sur la fiche client.
3. **« Open Papi Payment Page »** ouvre la page de paiement Papi dans un nouvel onglet. Le client paie avec MVola, Orange Money, Airtel Money ou une carte.
4. Au retour, l'opérateur revient sur le document. Le paiement est confirmé comme pour un paiement en ligne (notification signée, relecture du statut via l'API, tâche planifiée) : la facture passe à **Payé** ou la commande est **confirmée**.

Points d'attention :

- Droits : le bouton des factures exige le groupe *Facturation* ; celui des commandes, le groupe *Ventes : utilisateur*. L'opérateur doit pouvoir modifier le document.
- Un nouveau paiement est refusé tant qu'un paiement Papi du même document est **en attente** (`pending`) : vérifier d'abord son statut avec « Check Papi Status ».
- Les paiements Mobile Money sont **réels** : il n'y a pas de mode Test pour l'instant (voir plus haut).
- Le « Register Payment » standard d'Odoo ne convient pas : il exige un jeton de paiement enregistré et Papi n'en propose pas.
- Les transactions créées ainsi portent la case **« Created from the Back-office »**.

## 4. Vérifier l'URL publique d'Odoo

Papi appelle Odoo sur `https://<votre-domaine>/payment/papi/webhook`. Vérifier que :

- le paramètre système `web.base.url` contient bien l'URL publique HTTPS ;
- `web.base.url.freeze` vaut `True` si l'administrateur se connecte parfois via une autre URL.

Détails dans [urls_callback.md](urls_callback.md).

## 5. Données transmises à Papi

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
