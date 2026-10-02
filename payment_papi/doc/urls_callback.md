# URLs de retour et de callback

Toutes les URLs sont construites automatiquement à partir de `web.base.url` et envoyées à Papi à chaque création de lien. **Aucune configuration n'est nécessaire dans le dashboard Papi.**

| Rôle | Méthode | URL | Authentification |
|---|---|---|---|
| Retour client (succès **et** échec) | GET | `/payment/papi/return?ref=<référence>&access_token=<jeton>` | Jeton HMAC propre à la transaction |
| Notification serveur à serveur | POST | `/payment/papi/webhook` | En-tête `X-Papi-Signature` + `notificationToken` |
| Page de statut affichée au client | GET | `/payment/status` (standard Odoo) | Session du client |

## Retour client — `/payment/papi/return`

- Papi envoie `successUrl` et `failureUrl` par paire, sans URL d'annulation. Les deux pointent vers cette même route.
- **Le retour n'est jamais considéré comme une preuve de paiement.** Odoo interroge `GET /payment-links/{référence}` et applique le statut réellement renvoyé par Papi. Le client est ensuite redirigé vers `/payment/status`, qui affiche :

| Statut réel | Message affiché au client |
|---|---|
| Paiement abouti | Paiement confirmé, commande validée |
| Paiement en cours | Paiement en attente de confirmation |
| Paiement refusé | Paiement refusé, le client peut réessayer. Le motif renvoyé par Papi n'est visible que par le marchand, sur la transaction. |
| Aucune tentative (le client est revenu sans payer) | La transaction reste en brouillon : la page de statut standard d'Odoo s'affiche, sans message propre au module. Le client peut réessayer. |
| Lien expiré ou désactivé | Paiement annulé |

- **Retour de l'opérateur (back-office).** Pour une transaction créée avec le bouton « Pay with Papi » d'une facture ou d'une commande, l'opérateur connecté (utilisateur interne) est ramené sur le document (`/odoo/account.move/<id>` ou `/odoo/sale.order/<id>`) au lieu de `/payment/status`, qui ne connaît que les transactions de la session du client. Le statut est relu via l'API Papi avant la redirection, comme pour un client. Sans session interne, la redirection reste `/payment/status`.
- Un `access_token` invalide ou une référence inconnue n'entraîne aucun traitement. Le client est quand même redirigé vers la page de statut, et une entrée est journalisée.

## Notification — `/payment/papi/webhook`

Papi envoie la notification **une seule fois**. Il attend au plus 10 s pour se connecter et au plus 30 s pour obtenir la réponse. L'en-tête `User-Agent` vaut `PAPI-Callback/1.0`.

Contrôles, dans l'ordre :

1. Le corps doit être un JSON valide. Sinon : **400**.
2. La transaction est recherchée via `merchantPaymentReference`. Si elle est inconnue : **200** (acquittement) et journalisation.
3. **Signature** `X-Papi-Signature: t=<unix>,v1=<hex>`, avec `v1 = HMAC-SHA256(secret, t + "." + corps brut)`, comparée en temps constant. Elle doit dater de moins de **300 s**. Sinon : **403**.
4. Le **`notificationToken`** du corps doit correspondre au jeton reçu à la création du lien. Sinon : **403**.
5. Le statut est **relu via l'API Papi** : le corps sert uniquement à identifier la transaction. Odoo contrôle ensuite la référence, le jeton, la devise et le montant, puis met à jour la transaction.
6. Réponse **200**. En cas d'erreur de traitement (API Papi injoignable, par exemple), la réponse reste 200 : c'est la tâche planifiée qui reprendra.

Le traitement est **idempotent** :

- verrou de ligne `SELECT … FOR UPDATE` sur la transaction ;
- une transaction déjà `done` n'est plus relue ;
- les transitions d'état d'Odoo ignorent un état déjà atteint.

Recevoir la même notification plusieurs fois ne crée donc ni double paiement ni double confirmation.

## Pare-feu et proxy

- Autoriser les requêtes entrantes HTTPS vers `/payment/papi/webhook`. Papi ne publie pas de plage d'adresses IP : ne pas filtrer par IP.
- Derrière Nginx ou Apache, transmettre le corps sans modification : la signature porte sur le corps brut. Transmettre aussi l'en-tête `X-Papi-Signature`.
- Si un WAF est en place, ne pas bloquer le `User-Agent` `PAPI-Callback/1.0`.

## Test local

En développement, exposer Odoo avec un tunnel HTTPS, par exemple `ngrok http 8069`, et mettre l'URL du tunnel dans `web.base.url`. Sans URL publique, les notifications ne parviennent pas à Odoo. Le retour client et la tâche planifiée mettent quand même les transactions à jour.
