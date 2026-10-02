# Questionnaire — usage d'Odoo chez les intégrateurs et marchands

Objectif : combler le point resté ouvert de l'étude technique (« proportion de clients Odoo sur Odoo.sh ou auto-hébergés »), pour lequel **aucune donnée publique fiable n'existe**. À envoyer par l'équipe commerciale aux intégrateurs partenaires et aux marchands Papi déjà sous Odoo. Dix minutes de réponse suffisent.

## Pour les intégrateurs Odoo

1. Combien de clients (bases Odoo) gérez-vous à Madagascar ? Dont combien avec un site e-commerce (`website_sale`) ?
2. Pour ces bases, répartition approximative :
   - Odoo Online (SaaS) : __ %
   - Odoo.sh : __ %
   - Auto-hébergé (VPS, serveur local, cloud) : __ %
3. Versions d'Odoo en production : 16 __ % · 17 __ % · **18** __ % · 19 __ % · autre __ %
4. Édition : Community __ % · Enterprise __ %
5. Vos clients encaissent-ils déjà en ligne ? Avec quel moyen (virement, lien de paiement manuel, autre) ?
6. Seriez-vous prêts à installer un module tiers de paiement ? Préférez-vous qu'il soit sur l'Odoo Apps Store ou fourni par Papi (archive ou dépôt Git) ?
7. Vos clients facturent-ils en MGA ? Quelques-uns en devise étrangère ?
8. Besoins non couverts par la v1 : point de vente, abonnements, remboursements depuis Odoo, autre ?

## Pour les marchands Papi sous Odoo

1. Version d'Odoo et hébergement (Online / Odoo.sh / auto-hébergé) ?
2. Applications utilisées : site e-commerce, facturation seule, point de vente ?
3. Payez-vous des commandes en ligne, des factures du portail, ou les deux ?
4. Qui encaisserait avec Papi depuis Odoo : le client seul, ou aussi un opérateur à la caisse ou au téléphone (bouton « Pay with Papi ») ?

## Comment exploiter les réponses

| Résultat | Décision |
|---|---|
| Majorité Odoo Online | Étudier une solution par lien de paiement externe, distincte de l'intégration native |
| Majorité Odoo.sh ou auto-hébergé | Poursuivre l'intégration native (c'est le cas de la v1) |
| Forte part d'Odoo 17 ou 19 | Prioriser le portage correspondant (voir [compatibilite.md](compatibilite.md)) |
| Demande de point de vente | Chiffrer un module `payment_papi_pos` à part |
