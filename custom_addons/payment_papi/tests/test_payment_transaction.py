# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment_papi.tests.common import PapiCommon


MAKE_REQUEST = 'odoo.addons.payment_papi.models.payment_provider.PaymentProvider._papi_make_request'


@tagged('post_install', '-at_install')
class TestPaymentTransaction(PapiCommon):

    #=== Reference ===#

    def test_reference_is_url_safe(self):
        """ Invoice names contain slashes, which are replaced to keep the reference URL-safe. """
        reference = self.env['payment.transaction']._compute_reference(
            'papi', prefix='INV/2026/00001'
        )
        self.assertEqual(reference, 'INV-2026-00001')

    def test_reference_sequence_is_kept(self):
        self._create_transaction('redirect', reference='INV-2026-00001')
        reference = self.env['payment.transaction']._compute_reference(
            'papi', prefix='INV/2026/00001'
        )
        self.assertEqual(reference, 'INV-2026-00001-1')

    def test_reference_of_other_providers_is_untouched(self):
        reference = self.env['payment.transaction']._compute_reference(
            'none', prefix='INV/2026/00001'
        )
        self.assertEqual(reference, 'INV/2026/00001')

    #=== Payment link creation ===#

    def test_payment_link_payload(self):
        tx = self._create_transaction('redirect')
        payload = tx._papi_prepare_payment_link_payload()
        base_url = self.provider.get_base_url()

        self.assertEqual(payload['amount'], 15000)
        self.assertEqual(payload['currency'], 'MGA')
        self.assertEqual(payload['reference'], self.reference)
        self.assertEqual(payload['clientName'], self.partner.name)
        self.assertEqual(payload['payerEmail'], self.partner.email)
        self.assertEqual(payload['payerPhone'], '+261341234567')
        self.assertEqual(payload['notificationUrl'], f'{base_url}/payment/papi/webhook')
        self.assertEqual(payload['successUrl'], payload['failureUrl'])
        self.assertTrue(payload['successUrl'].startswith(f'{base_url}/payment/papi/return?'))
        query = parse_qs(urlparse(payload['successUrl']).query)
        self.assertEqual(query['ref'], [self.reference])
        self.assertTrue(tx._papi_check_return_access_token(query['access_token'][0]))
        self.assertEqual(payload['validDuration'], 1)
        self.assertTrue(payload['isTestMode'])
        for secret in (self.provider.papi_api_key, self.provider.papi_webhook_secret):
            self.assertNotIn(secret, str(payload))

    def test_payment_link_payload_in_production(self):
        self.provider.state = 'enabled'
        payload = self._create_transaction('redirect')._papi_prepare_payment_link_payload()
        self.assertNotIn('isTestMode', payload)

    def test_payment_link_payload_keeps_decimals(self):
        tx = self._create_transaction('redirect', amount=15000.5)
        self.assertEqual(tx._papi_prepare_payment_link_payload()['amount'], 15000.5)

    def test_phone_formatting(self):
        tx_model = self.env['payment.transaction']
        self.assertEqual(tx_model._papi_format_phone('034 12 345 67'), '+261341234567')
        self.assertEqual(tx_model._papi_format_phone('+261 32 11 222 33'), '+261321122233')
        self.assertEqual(tx_model._papi_format_phone('00261331122233'), '+261331122233')
        self.assertIsNone(tx_model._papi_format_phone('0032 12 34 56 78'))
        self.assertIsNone(tx_model._papi_format_phone(False))

    def test_invalid_phone_is_not_sent(self):
        self.partner.phone = '0032 12 34 56 78'
        payload = self._create_transaction('redirect')._papi_prepare_payment_link_payload()
        self.assertNotIn('payerPhone', payload)

    def test_redirect_form_and_stored_link_data(self):
        tx = self._create_transaction('redirect')
        with patch(MAKE_REQUEST, return_value=self.link_creation_data) as request_mock:
            processing_values = tx._get_processing_values()

        self.assertEqual(request_mock.call_args.args[0], 'payment-links')
        form_info = self._extract_values_from_html_form(processing_values['redirect_form_html'])
        self.assertEqual(form_info['action'], self.link_creation_data['paymentLink'])
        self.assertEqual(form_info['method'], 'get')
        self.assertEqual(tx.papi_notification_token, self.notification_token)
        self.assertEqual(tx.papi_payment_link, self.link_creation_data['paymentLink'])
        self.assertEqual(tx.papi_link_status, 'ACTIVE')
        self.assertTrue(tx.papi_link_expiration)

    #=== Status mapping ===#

    def _process(self, tx, link_data):
        with patch(MAKE_REQUEST, return_value=link_data) as request_mock:
            tx._handle_notification_data('papi', {'merchantPaymentReference': tx.reference})
        return request_mock

    def test_paid_link_confirms_transaction(self):
        tx = self._create_papi_transaction()
        request_mock = self._process(tx, self._link_status_data('PAID', 'SUCCESS'))
        self.assertEqual(request_mock.call_args.args[0], f'payment-links/{self.reference}')
        self.assertEqual(request_mock.call_args.kwargs['method'], 'GET')
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, self.papi_payment_reference)
        self.assertEqual(tx.papi_payment_method, 'MVOLA')
        self.assertEqual(tx.papi_link_status, 'PAID')
        self.assertEqual(tx.papi_payment_status, 'SUCCESS')
        self.assertTrue(tx.papi_last_sync_date)

    def test_payment_in_progress_keeps_transaction_pending(self):
        tx = self._create_papi_transaction()
        self._process(tx, self._link_status_data('ACTIVE', 'PENDING'))
        self.assertEqual(tx.state, 'pending')

    def test_unattempted_payment_keeps_transaction_draft(self):
        tx = self._create_papi_transaction()
        self._process(tx, self._link_status_data('ACTIVE', None))
        self.assertEqual(tx.state, 'draft')

    def test_failed_payment_sets_error_and_can_recover(self):
        tx = self._create_papi_transaction()
        self._process(tx, self._link_status_data('ACTIVE', 'FAILED', message="Solde insuffisant"))
        self.assertEqual(tx.state, 'error')
        self.assertIn("Solde insuffisant", tx.state_message)

        # The customer tries again on the same payment link and succeeds.
        self._process(tx, self._link_status_data('PAID', 'SUCCESS'))
        self.assertEqual(tx.state, 'done')

    def test_expired_link_cancels_transaction(self):
        tx = self._create_papi_transaction()
        self._process(tx, self._link_status_data('EXPIRED', None))
        self.assertEqual(tx.state, 'cancel')

    def test_disabled_link_cancels_transaction(self):
        tx = self._create_papi_transaction()
        self._process(tx, self._link_status_data('DISABLED', 'FAILED'))
        self.assertEqual(tx.state, 'cancel')

    @mute_logger('odoo.addons.payment_papi.models.payment_transaction')
    def test_unknown_status_does_not_confirm(self):
        tx = self._create_papi_transaction()
        self._process(tx, self._link_status_data('WEIRD', 'SUCCESS?'))
        self.assertEqual(tx.state, 'draft')
        self.assertIn("WEIRD", tx.papi_message)

    #=== Consistency checks ===#

    @mute_logger('odoo.addons.payment_papi.models.payment_transaction')
    def test_amount_mismatch_does_not_confirm(self):
        tx = self._create_papi_transaction()
        self._process(tx, self._link_status_data('PAID', 'SUCCESS', amount=300.0))
        self.assertEqual(tx.state, 'error')
        self.assertIn("300.0", tx.papi_message)

    @mute_logger('odoo.addons.payment_papi.models.payment_transaction')
    def test_currency_mismatch_does_not_confirm(self):
        tx = self._create_papi_transaction()
        self._process(tx, self._link_status_data('PAID', 'SUCCESS', currency='EUR'))
        self.assertEqual(tx.state, 'error')

    @mute_logger('odoo.addons.payment_papi.models.payment_transaction')
    def test_token_mismatch_does_not_confirm(self):
        tx = self._create_papi_transaction()
        self._process(tx, self._link_status_data('PAID', 'SUCCESS', notificationToken='other'))
        self.assertEqual(tx.state, 'error')

    @mute_logger('odoo.addons.payment_papi.models.payment_transaction')
    def test_reference_mismatch_does_not_confirm(self):
        tx = self._create_papi_transaction()
        self._process(
            tx, self._link_status_data('PAID', 'SUCCESS', merchantPaymentReference='S00099')
        )
        self.assertEqual(tx.state, 'error')

    #=== Idempotency ===#

    def test_repeated_processing_is_idempotent(self):
        tx = self._create_papi_transaction()
        with patch(MAKE_REQUEST, return_value=self._link_status_data()) as request_mock, \
                patch.object(type(tx), '_log_received_message') as log_mock:
            for _i in range(3):
                tx._handle_notification_data('papi', {'merchantPaymentReference': tx.reference})
        self.assertEqual(tx.state, 'done')
        self.assertEqual(request_mock.call_count, 1, "A done transaction is not checked again.")
        self.assertEqual(log_mock.call_count, 1, "The payment is only registered once.")

    #=== Lookup ===#

    def test_find_transaction_by_reference(self):
        tx = self._create_papi_transaction()
        found_tx = self.env['payment.transaction']._get_tx_from_notification_data(
            'papi', {'merchantPaymentReference': self.reference}
        )
        self.assertEqual(found_tx, tx)

    def test_unknown_reference_raises(self):
        with self.assertRaises(ValidationError):
            self.env['payment.transaction']._get_tx_from_notification_data(
                'papi', {'merchantPaymentReference': 'unknown'}
            )

    #=== Cron and diagnosis ===#

    def test_cron_catches_up_lost_notification(self):
        tx = self._create_papi_transaction()
        with patch(MAKE_REQUEST, return_value=self._link_status_data()):
            self.env['payment.transaction']._cron_papi_sync_pending()
        self.assertEqual(tx.state, 'done')

    def test_cron_ignores_transactions_without_link_or_too_old(self):
        tx_without_link = self._create_transaction('redirect', reference='S00043')
        tx_too_old = self._create_papi_transaction(
            reference='S00044', papi_link_expiration='2020-01-01 00:00:00'
        )
        with patch(MAKE_REQUEST) as request_mock:
            self.env['payment.transaction']._cron_papi_sync_pending()
        self.assertEqual(request_mock.call_count, 0)
        self.assertEqual((tx_without_link | tx_too_old).mapped('state'), ['draft', 'draft'])

    @mute_logger('odoo.addons.payment_papi.models.payment_transaction')
    def test_cron_continues_after_error(self):
        tx_failing = self._create_papi_transaction(reference='S00045')
        tx_ok = self._create_papi_transaction()

        def fake_request(provider, endpoint, **kwargs):
            if 'S00045' in endpoint:
                raise ValidationError("Papi: boom")
            return self._link_status_data()

        with patch(MAKE_REQUEST, autospec=True, side_effect=fake_request):
            self.env['payment.transaction']._cron_papi_sync_pending()
        self.assertEqual(tx_failing.state, 'draft')
        self.assertEqual(tx_ok.state, 'done')

    def test_check_status_button(self):
        tx = self._create_papi_transaction()
        with patch(MAKE_REQUEST, return_value=self._link_status_data('ACTIVE', 'PENDING')):
            action = tx.action_papi_check_status()
        self.assertEqual(tx.state, 'pending')
        self.assertEqual(action['tag'], 'display_notification')
