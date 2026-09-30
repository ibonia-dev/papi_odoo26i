# Plan de tests

## 1. Tests automatisés (61 tests, en complément des tests standard d’Odoo)

Lancement :
```bash
odoo-bin -c odoo.conf -d <base_de_test> -i payment_papi,sale,account_payment \
         --test-tags /payment_papi --stop-after-init
```
Résultat attendu : `0 failed, 0 error(s)`. L'API Papi est simulée : aucun appel réel, aucun argent en jeu.

| Fichier | Ce qui est couvert |
|---|---|
| `test_payment_provider.py` | Disponibilité : MGA uniquement, minimum 300 MGA, masqué pour les validations et hors Madagascar. Contraintes de configuration : validité, préfixe du secret, HTTPS. Secrets réservés aux administrateurs. Bouton « Tester la connexion » (404 → OK, 401 → clé refusée, réseau). **Aucun secret dans les journaux ni dans les messages d'erreur.** |
| `test_payment_transaction.py` | Références compatibles avec les URLs (factures `INV/…` → `INV-…`). Contenu de la requête de création de lien (montant, référence, URLs, téléphone, `isTestMode` selon l'état). Formulaire de redirection. **Table de correspondance complète des statuts.** Refus sur incohérence de montant, devise, référence ou jeton. **Idempotence** : 3 traitements, 1 seul enregistrement. Rattrapage par la tâche planifiée, avec reprise après erreur. Bouton de diagnostic. |
| `test_processing_flows.py` | Webhook : signature valide → `done` ; **statut relu via l'API et non pris dans le corps** ; **notification répétée 3 fois → 1 seul traitement**. Rejets : signature invalide, mauvais secret, corps modifié, rejeu > 300 s, mauvais `notificationToken`, JSON invalide. Retour client : jeton valide ou invalide, API injoignable. |
| `test_sale_flow.py` | **Paiement abouti → commande confirmée**, paiement échoué ou en attente → commande non confirmée, référence de commande reprise. |

## 2. Recette fonctionnelle (environnement de test)

Prérequis : Odoo joignable en HTTPS public, module installé, boutique Papi en **Test Mode** (cartes) et fournisseur Papi en état **Test**.

| # | Scénario | Étapes | Résultat attendu |
|---|---|---|---|
| R1 | Configuration | Saisir la clé et le secret, puis cliquer sur « Tester la connexion » | Notification verte |
| R2 | Clé invalide | Saisir une clé erronée, puis « Tester la connexion » | Notification rouge |
| R3 | Visibilité | Panier en MGA ≥ 300 Ar, connecté en interne | Papi proposé à l'étape de paiement |
| R4 | Montant minimum | Panier à 200 Ar | Papi non proposé |
| R5 | Autre devise | Liste de prix en EUR | Papi non proposé |
| R6 | Paiement carte réussi | Payer avec la carte de test 4000 0000 0000 5126 | Retour sur `/payment/status` avec « paiement confirmé ». Transaction `done` avec l'UUID Papi en référence fournisseur et l'instrument « Card (BRED) ». **Commande confirmée**, dernière notification renseignée. |
| R7 | Paiement échoué | Carte refusée ou abandon sur erreur | Transaction « erreur » avec le motif ; commande **non confirmée** |
| R8 | Abandon | Revenir au site sans payer | Transaction en brouillon ; le client peut relancer un paiement. Après expiration du lien (1 h) et passage de la tâche planifiée : **annulée**. |
| R9 | Notification perdue | Bloquer temporairement `/payment/papi/webhook` (proxy), puis payer | Au retour client, ou au passage suivant de la tâche planifiée, transaction `done` |
| R10 | Rejeu | Renvoyer la notification depuis le dashboard Papi | Aucun doublon de paiement ni d'e-mail ; journal « already done; skipping » |
| R11 | Facture portail | Installer `account_payment`, envoyer une facture en MGA, puis payer depuis `/my/invoices` | Transaction `INV-AAAA-NNNNN` `done`, facture **payée** |
| R12 | Journaux | Parcourir les journaux serveur de R1 à R11 | Aucune clé API, aucun secret `pwhsec_`, aucun jeton de notification |
| R13 | Diagnostic | Transaction en attente, puis bouton « Check Papi Status » | Statut mis à jour et notification affichée |

## 3. Validation en production (obligatoire avant ouverture)

⚠️ Mouvements d'argent réels. Utiliser de petits montants (≥ 300 Ar), payés par l'équipe.

| # | Scénario | Résultat attendu |
|---|---|---|
| P1 | Passer le fournisseur en **Activé**, puis vérifier « Tester la connexion » | OK |
| P2 | Commande de 500 Ar payée en **MVola** | Commande confirmée ; montant visible dans le dashboard Papi sous la même référence |
| P3 | Commande de 500 Ar payée en **Orange Money** | Idem |
| P4 | Commande de 500 Ar payée en **Airtel Money** | Idem |
| P5 | Paiement MVola refusé (solde insuffisant ou refus sur le téléphone) | Commande non confirmée |
| P6 | Paiement d'une facture depuis le portail | Facture payée |
| P7 | Rapprochement : export Odoo ↔ export Papi | Toutes les transactions `done` sont présentes chez Papi, avec le même montant et la même référence |

Consigner pour chaque test la date, la référence Odoo, l'UUID Papi et le résultat. Ce tableau vaut procès-verbal de validation de production (critère d'acceptation « un scénario complet de production a été validé »).
