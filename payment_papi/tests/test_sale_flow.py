# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.payment_papi.tests.common import PapiCommon


MAKE_REQUEST = 'odoo.addons.payment_papi.models.payment_provider.PaymentProvider._papi_make_request'


@tagged('post_install', '-at_install')
class TestSaleFlow(PapiCommon):
    """ End-to-end checks of the order confirmation. Skipped when `sale` is not installed. """

    def setUp(self):
        super().setUp()
        if 'sale_order_ids' not in self.env['payment.transaction']._fields:
            self.skipTest("The sale module is not installed.")

        pricelist = self.env['product.pricelist'].create({
            'name': "MGA pricelist",
            'currency_id': self.currency_mga.id,
        })
        product = self.env['product.product'].create({
            'name': "Vary amin'anana",
            'list_price': 15000,
            'taxes_id': [Command.clear()],
        })
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'pricelist_id': pricelist.id,
            # In 19.0, a payment does not confirm an order that still has to be signed.
            'require_signature': False,
            'order_line': [Command.create({
                'product_id': product.id,
                'price_unit': 15000,
                'tax_ids': [Command.clear()],
            })],
        })
        self.assertEqual(self.order.currency_id, self.currency_mga)
        self.assertEqual(self.order.amount_total, 15000)

    def _pay(self, link_status, payment_status):
        tx = self._create_papi_transaction(sale_order_ids=[Command.set(self.order.ids)])
        with patch(MAKE_REQUEST, return_value=self._link_status_data(link_status, payment_status)):
            tx._papi_process({'merchantPaymentReference': tx.reference})
        tx.with_context(payment_safe_write=True)._post_process()
        return tx

    def test_successful_payment_confirms_order(self):
        tx = self._pay('PAID', 'SUCCESS')
        self.assertEqual(tx.state, 'done')
        self.assertEqual(self.order.state, 'sale')

    def test_failed_payment_does_not_confirm_order(self):
        tx = self._pay('ACTIVE', 'FAILED')
        self.assertEqual(tx.state, 'error')
        self.assertIn(self.order.state, ('draft', 'sent'))

    def test_pending_payment_does_not_confirm_order(self):
        tx = self._pay('ACTIVE', 'PENDING')
        self.assertEqual(tx.state, 'pending')
        self.assertIn(self.order.state, ('draft', 'sent'))

    def test_order_reference_is_used(self):
        reference = self.env['payment.transaction']._compute_reference(
            'papi', sale_order_ids=[Command.set(self.order.ids)]
        )
        self.assertEqual(reference, self.order.name)
