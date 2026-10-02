# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.payment_papi.controllers.main import PapiController
from odoo.addons.payment_papi.tests.common import PapiCommon


MAKE_REQUEST = 'odoo.addons.payment_papi.models.payment_provider.PaymentProvider._papi_make_request'


@tagged('post_install', '-at_install')
class TestBackendFlow(PapiCommon, PaymentHttpCommon):
    """ The operator pays an invoice (or an order) with Papi from the back-office. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.papi.payment_method_ids = [Command.link(cls.payment_method.id)]
        cls.operator = cls.env['res.users'].create({
            'name': "Papi Operator",
            'login': 'papi_operator',
            'password': 'papi_operator_password',
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

    def setUp(self):
        # Let the account post-processing run: the payment of the invoice is what is checked.
        self.enable_reconcile_after_done_patcher = False
        super().setUp()

    def _open_wizard(self, document=None, **values):
        document = document or self.invoice
        return self.env['papi.backend.pay.wizard'].with_user(self.operator).with_context(
            default_res_model=document._name, default_res_id=document.id
        ).create(values)

    def _pay(self, wizard):
        with patch(MAKE_REQUEST, return_value=self.link_creation_data) as request_mock:
            action = wizard.action_pay()
        return action, request_mock

    #=== Availability ===#

    def test_button_available_for_posted_unpaid_invoice_in_mga(self):
        self.assertTrue(self.invoice.papi_backend_payment_available)

    def test_button_hidden_when_papi_is_disabled(self):
        self.papi.state = 'disabled'
        self.invoice.invalidate_recordset(['papi_backend_payment_available'])
        self.assertFalse(self.invoice.papi_backend_payment_available)

    def test_button_hidden_for_draft_invoice(self):
        draft = self.invoice.copy()
        self.assertFalse(draft.papi_backend_payment_available)

    def test_button_hidden_for_other_currency(self):
        usd_invoice = self.invoice.copy({'currency_id': self.env.ref('base.USD').id})
        usd_invoice.action_post()
        self.assertFalse(usd_invoice.papi_backend_payment_available)

    #=== Wizard ===#

    def test_wizard_defaults_come_from_the_invoice(self):
        wizard = self._open_wizard()
        self.assertEqual(wizard.partner_id, self.partner)
        self.assertEqual(wizard.currency_id, self.currency_mga)
        self.assertEqual(wizard.amount, 15000)
        self.assertEqual(wizard.amount_max, 15000)
        self.assertEqual(wizard.payer_phone, '034 12 345 67')
        self.assertTrue(wizard.is_test_mode)

    def test_pay_creates_transaction_linked_to_the_invoice_only(self):
        wizard = self._open_wizard(payer_phone='032 11 222 33')
        action, request_mock = self._pay(wizard)

        tx = self.env['payment.transaction'].search([('invoice_ids', '=', self.invoice.id)])
        self.assertEqual(len(tx), 1)
        self.assertEqual(tx.provider_code, 'papi')
        self.assertEqual(tx.amount, 15000)
        self.assertEqual(tx.currency_id, self.currency_mga)
        self.assertTrue(tx.papi_backend_origin)
        self.assertEqual(tx.landing_route, f'/web#id={self.invoice.id}&model=account.move&view_type=form')
        self.assertEqual(tx.papi_payment_link, self.link_creation_data['paymentLink'])
        self.assertTrue(tx.reference.startswith('INV-'), tx.reference)
        self.assertEqual(
            action,
            {'type': 'ir.actions.act_url', 'url': self.link_creation_data['paymentLink'],
             'target': 'new'},
        )
        payload = request_mock.call_args.kwargs['payload']
        self.assertEqual(payload['payerPhone'], '+261321122233')
        self.assertEqual(payload['amount'], 15000)
        self.assertEqual(payload['reference'], tx.reference)
        self.assertEqual(self.partner.phone, '034 12 345 67')  # The customer is not modified.

    def test_pay_rejects_amount_above_amount_due(self):
        wizard = self._open_wizard(amount=20000)
        with self.assertRaises(UserError):
            wizard.action_pay()

    def test_pay_rejects_amount_below_papi_minimum(self):
        wizard = self._open_wizard(amount=100)
        with self.assertRaises(UserError):
            wizard.action_pay()

    def test_pay_rejects_when_papi_is_not_available(self):
        wizard = self._open_wizard()
        self.papi.state = 'disabled'
        with self.assertRaises(UserError):
            wizard.action_pay()

    def test_pay_rejects_when_a_payment_is_already_pending(self):
        self._create_papi_transaction(
            invoice_ids=[Command.set(self.invoice.ids)], state='pending'
        )
        with self.assertRaises(UserError):
            self._open_wizard().action_pay()

    def test_pay_requires_write_access_on_the_document(self):
        reader = self.env['res.users'].create({
            'name': "Reader", 'login': 'papi_reader', 'password': 'papi_reader_password',
            'groups_id': [Command.set([self.env.ref('base.group_user').id])],
        })
        wizard = self.env['papi.backend.pay.wizard'].with_user(reader).create(
            {'res_model': 'account.move', 'res_id': self.invoice.id}
        )
        with self.assertRaises(AccessError):
            wizard.action_pay()

    def test_wizard_ignores_models_that_are_not_payable(self):
        wizard = self.env['papi.backend.pay.wizard'].create(
            {'res_model': 'res.partner', 'res_id': self.partner.id}
        )
        with self.assertRaises(UserError):
            wizard.action_pay()

    #=== Return and confirmation ===#

    def _create_backend_transaction(self):
        wizard = self._open_wizard()
        self._pay(wizard)
        return self.env['payment.transaction'].search([('invoice_ids', '=', self.invoice.id)])

    def test_successful_payment_marks_the_invoice_as_paid(self):
        tx = self._create_backend_transaction()
        data = self._link_status_data(
            merchantPaymentReference=tx.reference, notificationToken=tx.papi_notification_token
        )
        with patch(MAKE_REQUEST, return_value=data):
            tx._handle_notification_data('papi', {'merchantPaymentReference': tx.reference})
        if tx.state == 'done':  # In 17.0, only done transactions are post-processed.
            tx._finalize_post_processing()  # Named `_post_process` in 18.0.
        self.assertEqual(tx.state, 'done')
        self.assertIn(self.invoice.payment_state, ('paid', 'in_payment'))

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_return_sends_the_operator_back_to_the_document(self):
        tx = self._create_backend_transaction()
        self.authenticate('papi_operator', 'papi_operator_password')
        data = self._link_status_data(
            merchantPaymentReference=tx.reference, notificationToken=tx.papi_notification_token
        )
        url = self._build_url(PapiController._return_url)
        params = {'ref': tx.reference, 'access_token': tx._papi_get_return_access_token()}
        with patch(MAKE_REQUEST, return_value=data):
            response = self.opener.get(url, params=params, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(
            response.headers['Location'].endswith(f'/web#id={self.invoice.id}&model=account.move&view_type=form')
        )
        self.assertEqual(tx.state, 'done')

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_return_of_an_anonymous_user_goes_to_the_status_page(self):
        tx = self._create_backend_transaction()
        url = self._build_url(PapiController._return_url)
        params = {'ref': tx.reference, 'access_token': tx._papi_get_return_access_token()}
        data = self._link_status_data(
            merchantPaymentReference=tx.reference, notificationToken=tx.papi_notification_token
        )
        with patch(MAKE_REQUEST, return_value=data):
            response = self.opener.get(url, params=params, allow_redirects=False)
        self.assertTrue(response.headers['Location'].endswith('/payment/status'))

    #=== Sales order ===#

    def test_sale_order_can_be_paid_with_papi(self):
        if 'sale_order_ids' not in self.env['payment.transaction']._fields \
                or 'papi_backend_payment_available' not in self.env['sale.order']._fields:
            self.skipTest("The sale bridge (payment_papi_sale) is not installed.")
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
        self.assertTrue(order.papi_backend_payment_available)
        wizard = self.env['papi.backend.pay.wizard'].with_context(
            default_res_model='sale.order', default_res_id=order.id
        ).create({})
        self._pay(wizard)
        tx = order.transaction_ids
        self.assertEqual(len(tx), 1)
        self.assertFalse(tx.invoice_ids)
        self.assertEqual(tx.landing_route, f'/web#id={order.id}&model=sale.order&view_type=form')
        self.assertTrue(tx.reference.startswith(order.name))
