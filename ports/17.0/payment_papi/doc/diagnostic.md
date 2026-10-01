# Diagnostic des transactions bloquées ou non rapprochées

## Où trouver l'information

**Facturation/Comptabilité → Configuration → Transactions de paiement**, ou **Site web → Configuration → Transactions de paiement**. Filtre **« Papi: not final »** pour ne voir que les transactions en brouillon, en attente ou en erreur.

Le groupe **Papi** du formulaire de transaction affiche :

| Champ | Utilité |
|---|---|
| Référence | Référence marchande envoyée à Papi (= `merchantPaymentReference`) |
| Référence du fournisseur | Référence Papi (`papiPaymentReference`, UUID) |
| Statut du lien / Statut du paiement | Dernier statut lu chez Papi |
| Instrument de paiement | MVola, Orange Money, Airtel Money ou carte |
| Message Papi | Motif de refus renvoyé par Papi, ou incohérence détectée par Odoo. **Réservé au marchand** : le client ne voit qu'un message générique. |
| Code d'erreur Papi | Dernière erreur technique : `HTTP <statut> <code Papi>`, `connection_error`, `unexpected_response`, `inconsistent_data`, `unknown_status` ou `paid_after_cancel`. Le filtre « Papi: needs attention » liste les transactions concernées. |
| Expiration du lien | Au-delà, la transaction sera annulée |
| Dernière notification | Date de la dernière notification **signée** reçue |
| Dernière vérification | Date de la dernière lecture du statut via l'API |
| Lien de paiement | Mode développeur uniquement |

Le bouton **« Check Papi Status »** relit immédiatement le statut chez Papi et met la transaction à jour.

## Arbre de décision

| Symptôme | Cause probable | Action |
|---|---|---|
| Le client a payé mais la transaction reste en **brouillon** ou **en attente**, et « Dernière notification » est vide | La notification n'est pas arrivée : URL non publique, pare-feu, `web.base.url` erroné, serveur arrêté au moment de l'envoi | 1. Cliquer sur **Check Papi Status**. 2. Vérifier `web.base.url`. 3. Vérifier que la tâche planifiée est active. 4. Dans le dashboard Papi, **renvoyer la notification**. |
| Transaction **done** mais commande **non confirmée** | Post-traitement pas encore exécuté | Attendre la tâche standard « Payment: Post-process transactions » (≤ 10 min) ou la lancer manuellement. Vérifier aussi que le montant payé couvre le montant de confirmation de la commande. |
| Transaction en **erreur** « montant / devise / référence / jeton ne correspond pas » | Données incohérentes, par exemple un lien modifié ou réutilisé | **Ne pas confirmer manuellement.** Comparer avec le dashboard Papi (même référence) et contacter le support Papi avec la référence et l'UUID Papi. |
| Transaction en **erreur** « refusé par Papi (…) » | Paiement refusé : solde insuffisant, délai de validation dépassé… | Le client peut réessayer. Un succès ultérieur sur le même lien fait passer la transaction en `done`. |
| Transaction **annulée** « lien expiré » alors que le client dit avoir payé | Paiement validé chez l'opérateur après l'expiration | Cliquer sur **Check Papi Status** : si Papi indique SUCCESS, la transaction **reste annulée** (une autre transaction a pu être créée pour le même document, et une double confirmation serait pire) mais le code d'erreur `paid_after_cancel` et un message sont ajoutés à la transaction et au document. **Réconcilier manuellement** : vérifier dans le dashboard Papi, puis enregistrer le paiement sur la facture ou confirmer la commande, en veillant à ne pas payer deux fois. Papi ne propose pas d'API pour désactiver un lien : un client peut encore payer un lien dont la transaction est annulée. |
| Erreur au checkout « Papi : la communication avec l'API a échoué » | Clé API invalide, ou autre erreur HTTP de Papi (le détail n'est pas montré au client) | Lire le **Code d'erreur Papi** de la transaction ou le journal serveur ; pour une clé invalide (`HTTP 401`), onglet Identifiants → **Tester la connexion**, puis corriger la clé |
| Code d'erreur `HTTP 409 PAYMENT_LINK_CONFLICT` | Un lien actif existe déjà pour cette référence avec un autre montant (cas d'une base de recette partageant la boutique de production) | Utiliser une boutique Papi distincte pour la recette |
| Code d'erreur `HTTP 400 CORE_INPUT_400` | Données refusées par Papi (montant < 300, description vide…) | Voir le message détaillé dans le journal serveur |
| Journal : « invalid signature » ou « expired signature » | Secret de signature erroné, horloge du serveur décalée (> 5 min) ou corps modifié par un proxy | Vérifier le secret, synchroniser l'heure (NTP), vérifier la configuration du proxy |
| Journal : « invalid token » | Notification pour un autre lien ou tentative de falsification | Aucune action si isolé. Sinon, contacter Papi. |

## Journaux serveur

Tous les messages du module sont préfixés par `Papi:` et émis par les loggers `odoo.addons.payment_papi.*`. Ils contiennent la référence, les statuts et les codes d'erreur Papi, mais **jamais la clé API, le secret, le jeton de notification ni l'en-tête `Token`**.

```bash
grep "payment_papi" /var/log/odoo/odoo-server.log | grep "S00042"
```

## Rapprochement Odoo ↔ Papi

1. Exporter les transactions Papi d'Odoo (vue liste → Exporter) avec les colonnes Référence, Référence du fournisseur, Montant, État, Statut du paiement Papi et Date.
2. Exporter les paiements depuis le dashboard Papi.
3. Joindre les deux exports sur **Référence Odoo = référence marchande Papi**, ou sur **Référence du fournisseur = UUID Papi**.
4. Écarts à examiner : SUCCESS chez Papi mais pas `done` dans Odoo (utiliser **Check Papi Status**), ou `done` dans Odoo sans paiement chez Papi (impossible par construction : à signaler immédiatement).

## Tâche planifiée de rattrapage

« **Papi: synchronize pending transactions** » s'exécute toutes les 15 minutes. Elle relit par lots de 50 les transactions Papi en brouillon, en attente ou en erreur dont le lien a expiré il y a moins de 24 h. C'est elle qui compense l'envoi unique des notifications par Papi et qui annule les liens expirés.
