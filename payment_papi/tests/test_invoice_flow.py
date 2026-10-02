# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import fields
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.payment_papi.tests.common import PapiCommon


MAKE_REQUEST = 'odoo.addons.payment_papi.models.payment_provider.PaymentProvider._papi_make_request'


@tagged('post_install', '-at_install')
class TestInvoiceFlow(PapiCommon):
    """ Payment of an invoice from the portal: the invoice has its own references and flow. """

    def setUp(self):
        # Let the account post-processing run: the payment of the invoice is what is checked.
        self.enable_post_process_patcher = False
        super().setUp()
        self.invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'currency_id': self.currency_mga.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [Command.create({
                'name': "Service",
                'quantity': 1,
                'price_unit': 15000,
                'tax_ids': [Command.clear()],
            })],
        })
        self.invoice.action_post()

    def _pay(self, link_status, payment_status):
        tx = self._create_papi_transaction(
            invoice_ids=[Command.set(self.invoice.ids)],
            reference=self.env['payment.transaction']._compute_reference(
                'papi', invoice_ids=[Command.set(self.invoice.ids)]
            ),
        )
        data = self._link_status_data(
            link_status, payment_status,
            merchantPaymentReference=tx.reference, notificationToken=tx.papi_notification_token,
        )
        with patch(MAKE_REQUEST, return_value=data):
            tx._handle_notification_data('papi', {'merchantPaymentReference': tx.reference})
        tx._post_process()
        return tx

    def test_reference_is_based_on_the_invoice_name_and_url_safe(self):
        tx = self._create_papi_transaction(
            invoice_ids=[Command.set(self.invoice.ids)],
            reference=self.env['payment.transaction']._compute_reference(
                'papi', invoice_ids=[Command.set(self.invoice.ids)]
            ),
        )
        self.assertTrue(tx.reference.startswith(self.invoice.name.replace('/', '-')))
        self.assertNotIn('/', tx.reference)
        self.assertEqual(tx.invoice_ids, self.invoice)

    def test_successful_payment_pays_the_invoice(self):
        tx = self._pay('PAID', 'SUCCESS')
        self.assertEqual(tx.state, 'done')
        self.assertTrue(tx.payment_id)
        self.assertIn(self.invoice.payment_state, ('paid', 'in_payment'))

    def test_failed_payment_leaves_the_invoice_unpaid(self):
        tx = self._pay('ACTIVE', 'FAILED')
        self.assertEqual(tx.state, 'error')
        self.assertFalse(tx.payment_id)
        self.assertEqual(self.invoice.payment_state, 'not_paid')

    def test_pending_payment_leaves_the_invoice_unpaid(self):
        tx = self._pay('ACTIVE', 'PENDING')
        self.assertEqual(tx.state, 'pending')
        self.assertEqual(self.invoice.payment_state, 'not_paid')
