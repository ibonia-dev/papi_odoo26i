===========================
Payment Provider: Papi
===========================

Fournisseur de paiement Odoo 18 pour `Papi <https://papi.mg>`_ : paiement par MVola, Orange
Money, Airtel Money et carte bancaire (BRED) à Madagascar.

Le module s'intègre au flux de paiement standard d'Odoo :

- étape de paiement du site e-commerce (``website_sale``) ;
- paiement des factures depuis le portail client (``account_payment``) ;
- paiement des devis en ligne (``sale``) et liens de paiement.

Fonctionnement
==============

#. Le client choisit « Papi » à l'étape de paiement.
#. Odoo crée un lien de paiement Papi (``POST /engine/api/payment-links``) et redirige le client.
#. Le client choisit son instrument (MVola, Orange Money, Airtel Money, carte) sur la page Papi.
#. Papi notifie Odoo (``/payment/papi/webhook``, signature HMAC-SHA256) et renvoie le client sur
   ``/payment/papi/return``.
#. Dans tous les cas, Odoo relit le statut réel (``GET /engine/api/payment-links/{référence}``)
   avant de confirmer la commande. Une tâche planifiée rattrape les notifications perdues.

Limites
=======

- **Odoo Online (SaaS) n'est pas supporté** : les modules tiers ne peuvent pas y être installés.
  Seuls Odoo.sh et les installations auto-hébergées sont concernés.
- Devise **MGA** uniquement, montant minimum **300 MGA**.
- Papi n'a pas de sandbox : en mode test, les paiements mobile money sont réels.
- Pas de remboursement ni de tokenisation (non exposés par l'API Papi).

Documentation
=============

- ``doc/etude_technique.md`` : étude technique préalable
- ``doc/installation.md`` : installation et prérequis
- ``doc/configuration.md`` : configuration de Papi
- ``doc/urls_callback.md`` : URLs de retour et de callback
- ``doc/compatibilite.md`` : matrice de compatibilité
- ``doc/diagnostic.md`` : transactions bloquées ou non rapprochées
- ``doc/plan_de_tests.md`` : tests automatisés, recette et validation de production

Tests
=====

.. code-block:: bash

   odoo-bin -c odoo.conf -d test_db -i payment_papi,sale,account_payment \
            --test-tags /payment_papi --stop-after-init
