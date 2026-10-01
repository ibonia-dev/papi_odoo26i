# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from unittest.mock import Mock, patch

import requests

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment_papi.tests.common import PapiCommon


@tagged('post_install', '-at_install')
class TestPaymentProvider(PapiCommon):

    def _get_compatible(self, amount, currency=None, **kwargs):
        return self.env['payment.provider']._get_compatible_providers(
            self.company_id, self.partner.id, amount,
            currency_id=(currency or self.currency_mga).id, **kwargs
        )

    def test_compatible_with_mga_above_minimum(self):
        self.assertIn(self.papi, self._get_compatible(15000))

    def test_incompatible_below_minimum_amount(self):
        self.assertNotIn(self.papi, self._get_compatible(299))

    def test_minimum_amount_is_inclusive(self):
        self.assertIn(self.papi, self._get_compatible(300))

    def test_incompatible_with_other_currencies(self):
        self.papi.available_currency_ids = False  # Rely on the supported currencies only.
        self.assertNotIn(self.papi, self._get_compatible(15000, currency=self.currency_euro))
        self.assertEqual(self.papi._get_supported_currencies().mapped('name'), ['MGA'])

    def test_incompatible_for_validation(self):
        self.assertNotIn(self.papi, self._get_compatible(0, is_validation=True))

    def test_incompatible_outside_madagascar(self):
        self.partner.country_id = self.country_france
        self.assertNotIn(self.papi, self._get_compatible(15000))

    def test_default_payment_method_codes(self):
        self.assertEqual(self.papi._get_default_payment_method_codes(), {'papi'})

    def test_post_init_setup_activates_mga(self):
        self.currency_mga.active = False
        self.env['payment.provider']._papi_post_init_setup()
        self.assertTrue(self.currency_mga.active)

    def test_post_init_setup_is_idempotent_on_currency(self):
        self.env['payment.provider']._papi_post_init_setup()
        self.assertTrue(self.currency_mga.active)  # Running it twice does not raise or toggle it.
        self.env['payment.provider']._papi_post_init_setup()
        self.assertTrue(self.currency_mga.active)

    def test_post_init_setup_creates_pricelist_when_ecommerce_installed(self):
        Pricelist = self.env['product.pricelist']
        if 'website_id' not in Pricelist._fields:
            self.skipTest("The eCommerce is not installed.")
        Pricelist.search([('currency_id', '=', self.currency_mga.id)]).unlink()

        self.env['payment.provider']._papi_post_init_setup()

        pricelists = Pricelist.search([('currency_id', '=', self.currency_mga.id)])
        self.assertTrue(pricelists)
        self.assertTrue(all(pl.selectable for pl in pricelists))

        # A second run must not create a duplicate.
        self.env['payment.provider']._papi_post_init_setup()
        self.assertEqual(
            Pricelist.search_count([('currency_id', '=', self.currency_mga.id)]), len(pricelists)
        )

    def test_post_init_setup_fixes_unselectable_pricelist(self):
        """ A pricelist created by hand (or by an older version of this method) without ticking
        "Selectable" must be fixed in place, not duplicated. """
        Pricelist = self.env['product.pricelist']
        if 'website_id' not in Pricelist._fields:
            self.skipTest("The eCommerce is not installed.")
        Pricelist.search([('currency_id', '=', self.currency_mga.id)]).unlink()
        pricelist = Pricelist.create({
            'name': "Ariary",
            'currency_id': self.currency_mga.id,
            'selectable': False,
        })

        self.env['payment.provider']._papi_post_init_setup()

        self.assertTrue(pricelist.selectable)
        self.assertEqual(Pricelist.search_count([('currency_id', '=', self.currency_mga.id)]), 1)

    def test_post_init_setup_skips_pricelist_without_ecommerce(self):
        if 'website_id' in self.env['product.pricelist']._fields:
            self.skipTest("The eCommerce is installed.")
        self._assert_does_not_raise(
            Exception, self.env['payment.provider']._papi_post_init_setup
        )

    def test_link_validity_bounds(self):
        with self.assertRaises(ValidationError):
            self.papi.papi_link_validity = 0
        with self.assertRaises(ValidationError):
            self.papi.papi_link_validity = 597
        self.papi.papi_link_validity = 596

    def test_webhook_secret_prefix(self):
        with self.assertRaises(ValidationError):
            self.papi.papi_webhook_secret = 'not-a-papi-secret'

    def test_api_url_must_be_https(self):
        with self.assertRaises(ValidationError):
            self.papi.papi_api_url = 'http://app.papi.mg/engine/api/'

    def test_secrets_restricted_to_system_group(self):
        for field_name in ('papi_api_key', 'papi_webhook_secret'):
            self.assertEqual(self.papi._fields[field_name].groups, 'base.group_system')
        self.assertEqual(
            self.env['payment.transaction']._fields['papi_notification_token'].groups,
            'base.group_system',
        )

    def _mock_response(self, status_code, content):
        response = Mock(spec=requests.Response)
        response.status_code = status_code
        response.ok = status_code < 400
        response.url = 'https://app.papi.mg/engine/api/payment-links'
        response.json.return_value = content
        return response

    def test_connection_check_accepts_404(self):
        response = self._mock_response(404, {'error': {'code': 'CORE_404', 'message': '...'}})
        with patch('requests.get', return_value=response) as get_mock:
            action = self.papi.action_papi_test_connection()
        self.assertEqual(action['params']['type'], 'success')
        self.assertEqual(get_mock.call_args.kwargs['headers']['Token'], self.papi.papi_api_key)

    @mute_logger('odoo.addons.payment_papi.models.payment_provider')
    def test_connection_check_reports_invalid_key(self):
        response = self._mock_response(401, {'error': {'code': 'CORE_PERM_0001'}})
        with patch('requests.get', return_value=response):
            action = self.papi.action_papi_test_connection()
        self.assertEqual(action['params']['type'], 'danger')

    @mute_logger('odoo.addons.payment_papi.models.payment_provider')
    def test_connection_check_reports_network_error(self):
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError()):
            action = self.papi.action_papi_test_connection()
        self.assertEqual(action['params']['type'], 'danger')

    def test_failed_request_never_logs_or_shows_secrets(self):
        response = self._mock_response(
            400, {'error': {'code': 'CORE_INPUT_400', 'message': "Montant invalide"}}
        )
        with patch('requests.post', return_value=response), \
                self.assertLogs('odoo.addons.payment_papi', level='DEBUG') as logs, \
                self.assertRaises(ValidationError) as error:
            self.papi._papi_make_request('payment-links', payload={'amount': 1})
        output = '\n'.join(logs.output) + str(error.exception)
        self.assertIn('CORE_INPUT_400', output)
        self.assertNotIn(self.papi.papi_api_key, output)
        self.assertNotIn(self.papi.papi_webhook_secret, output)

    @mute_logger('odoo.addons.payment_papi.models.payment_provider')
    def test_api_error_shown_to_the_customer_has_no_technical_detail(self):
        response = self._mock_response(
            400, {'error': {'code': 'CORE_INPUT_400', 'message': "Montant invalide"}}
        )
        with patch('requests.post', return_value=response), \
                self.assertRaises(ValidationError) as error:
            self.papi._papi_make_request('payment-links', payload={'amount': 1})
        message = str(error.exception)
        for detail in ('CORE_INPUT_400', 'HTTP', '400', 'Montant invalide'):
            self.assertNotIn(detail, message)
        # The detail stays available to the merchant.
        self.assertEqual(error.exception.papi_error_code, 'HTTP 400 CORE_INPUT_400')
