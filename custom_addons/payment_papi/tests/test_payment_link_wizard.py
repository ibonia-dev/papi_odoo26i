# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import tagged

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.website.tools import MockRequest
from odoo.addons.payment_papi.tests.common import PapiCommon


@tagged('post_install', '-at_install')
class TestPaymentLinkWizard(PapiCommon, PaymentHttpCommon):
    """ The standard "Generate a Payment Link" wizard of Odoo offers Papi on the payment page. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operator = cls.env['res.users'].create({
            'name': "Papi Link Operator",
            'login': 'papi_link_operator',
            'password': 'papi_link_operator_password',
            'groups_id': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('account.group_account_invoice').id,
            ])],
        })
        cls.invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner.id,
            'currency_id': cls.currency_mga.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [Command.create({
                'name': "Service",
                'quantity': 1,
                'price_unit': 15000,
                'tax_ids': [Command.clear()],
            })],
        })
        cls.invoice.action_post()

    def _create_wizard(self, **values):
        with MockRequest(self.env):
            return self.env['payment.link.wizard'].with_context(
                active_model='account.move', active_id=self.invoice.id
            ).create(values)

    def test_payment_link_of_an_invoice_offers_papi(self):
        wizard = self._create_wizard()
        self.assertEqual(wizard.amount, 15000)
        self.assertEqual(wizard.currency_id, self.currency_mga)
        with MockRequest(self.env):
            link = wizard.link
        # For an invoice, the link opens the invoice in the customer portal.
        self.assertIn(f'/my/invoices/{self.invoice.id}', link)

        self.authenticate('papi_link_operator', 'papi_link_operator_password')
        response = self.url_open(link)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-provider-code="papi"', response.text)

    def test_payment_link_of_a_sales_order_offers_papi(self):
        if 'sale.order' not in self.env or 'sale_order_ids' not in self.env['payment.transaction']._fields:
            self.skipTest("The sale module is not installed.")
        pricelist = self.env['product.pricelist'].create(
            {'name': "MGA", 'currency_id': self.currency_mga.id}
        )
        product = self.env['product.product'].create(
            {'name': "Vary", 'list_price': 15000, 'taxes_id': [Command.clear()]}
        )
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'pricelist_id': pricelist.id,
            'order_line': [Command.create({
                'product_id': product.id, 'price_unit': 15000, 'tax_id': [Command.clear()],
            })],
        })
        with MockRequest(self.env):
            wizard = self.env['payment.link.wizard'].with_context(
                active_model='sale.order', active_id=order.id
            ).create({})
            link = wizard.link
        self.assertIn('/payment/pay', link)

        self.authenticate('papi_link_operator', 'papi_link_operator_password')
        response = self.url_open(link)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-provider-code="papi"', response.text)

    def test_amount_below_the_minimum_is_refused_with_a_clear_message(self):
        """ A partial amount typed in the portal can be below the minimum of Papi. """
        tx = self._create_transaction('redirect', amount=100)
        with self.assertRaises(ValidationError) as error:
            tx._get_specific_rendering_values({})
        self.assertIn("300", str(error.exception))

    def _get_pay_page(self, amount):
        values = self._prepare_pay_values(
            amount=amount, currency=self.currency_mga, partner=self.partner
        )
        return self._portal_pay(**values)

    def test_payment_page_warns_when_the_amount_is_below_the_minimum(self):
        """ Papi stays listed below 300 MGA, with a clear message instead of disappearing. """
        response = self._get_pay_page(200)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-provider-code="papi"', response.text)
        self.assertIn('papi_minimum_amount_warning', response.text)
        self.assertIn("Papi cannot be used for this amount.", response.text)

    def test_payment_page_does_not_warn_from_the_minimum(self):
        for amount in (300, 15000):
            response = self._get_pay_page(amount)
            self.assertIn('data-provider-code="papi"', response.text)
            self.assertNotIn('papi_minimum_amount_warning', response.text)
