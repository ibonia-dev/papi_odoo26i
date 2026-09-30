# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

import json
import time
from unittest.mock import patch

from werkzeug.exceptions import Forbidden

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.payment.tests.http_common import PaymentHttpCommon
from odoo.addons.payment_papi.controllers.main import PapiController
from odoo.addons.payment_papi.tests.common import PapiCommon


MAKE_REQUEST = 'odoo.addons.payment_papi.models.payment_provider.PaymentProvider._papi_make_request'
HANDLE_NOTIFICATION = (
    'odoo.addons.payment.models.payment_transaction.PaymentTransaction._handle_notification_data'
)


@tagged('post_install', '-at_install')
class TestProcessingFlows(PapiCommon, PaymentHttpCommon):

    def _post_webhook(self, body, signature=None, raw_body=None):
        raw_body = raw_body if raw_body is not None else json.dumps(body).encode()
        headers = {'Content-Type': 'application/json'}
        headers['X-Papi-Signature'] = signature if signature is not None else self._sign(raw_body)
        url = self._build_url(PapiController._webhook_url)
        return self.opener.post(url, data=raw_body, headers=headers)

    #=== Webhook ===#

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_webhook_with_valid_signature_confirms_transaction(self):
        tx = self._create_papi_transaction()
        with patch(MAKE_REQUEST, return_value=self._link_status_data()):
            response = self._post_webhook(self._notification_body())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(tx.state, 'done')
        self.assertTrue(tx.papi_last_notification_date)

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_webhook_status_comes_from_api_not_from_body(self):
        """ A notification claiming success does not confirm a payment that Papi reports failed. """
        tx = self._create_papi_transaction()
        with patch(MAKE_REQUEST, return_value=self._link_status_data('ACTIVE', 'FAILED')):
            self._post_webhook(self._notification_body('SUCCESS'))
        self.assertEqual(tx.state, 'error')

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_repeated_webhook_is_processed_once(self):
        tx = self._create_papi_transaction()
        body = self._notification_body()
        with patch(MAKE_REQUEST, return_value=self._link_status_data()) as request_mock:
            for _i in range(3):
                response = self._post_webhook(body)
                self.assertEqual(response.status_code, 200)
        self.assertEqual(tx.state, 'done')
        self.assertEqual(request_mock.call_count, 1)

    @mute_logger('odoo.addons.payment_papi.controllers.main', 'odoo.http')
    def test_webhook_with_invalid_signature_is_rejected(self):
        tx = self._create_papi_transaction()
        with patch(HANDLE_NOTIFICATION) as handle_mock:
            response = self._post_webhook(self._notification_body(), signature='t=1,v1=dead')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(handle_mock.call_count, 0)
        self.assertEqual(tx.state, 'draft')

    @mute_logger('odoo.addons.payment_papi.controllers.main', 'odoo.http')
    def test_webhook_with_wrong_secret_is_rejected(self):
        self._create_papi_transaction()
        raw_body = json.dumps(self._notification_body()).encode()
        signature = self._sign(raw_body, secret='pwhsec_' + 'b2' * 32)
        with patch(HANDLE_NOTIFICATION) as handle_mock:
            response = self._post_webhook(None, signature=signature, raw_body=raw_body)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(handle_mock.call_count, 0)

    @mute_logger('odoo.addons.payment_papi.controllers.main', 'odoo.http')
    def test_webhook_with_tampered_body_is_rejected(self):
        self._create_papi_transaction()
        raw_body = json.dumps(self._notification_body()).encode()
        signature = self._sign(raw_body)
        tampered_body = raw_body.replace(b'15000', b'15001')
        with patch(HANDLE_NOTIFICATION) as handle_mock:
            response = self._post_webhook(None, signature=signature, raw_body=tampered_body)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(handle_mock.call_count, 0)

    @mute_logger('odoo.addons.payment_papi.controllers.main', 'odoo.http')
    def test_replayed_webhook_is_rejected(self):
        self._create_papi_transaction()
        raw_body = json.dumps(self._notification_body()).encode()
        signature = self._sign(raw_body, timestamp=int(time.time()) - 301)
        with patch(HANDLE_NOTIFICATION) as handle_mock:
            response = self._post_webhook(None, signature=signature, raw_body=raw_body)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(handle_mock.call_count, 0)

    @mute_logger('odoo.addons.payment_papi.controllers.main', 'odoo.http')
    def test_webhook_with_wrong_notification_token_is_rejected(self):
        tx = self._create_papi_transaction()
        with patch(HANDLE_NOTIFICATION) as handle_mock:
            response = self._post_webhook(self._notification_body(notificationToken='forged'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(handle_mock.call_count, 0)
        self.assertEqual(tx.state, 'draft')

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_webhook_for_unknown_reference_is_acknowledged(self):
        response = self._post_webhook(self._notification_body(merchantPaymentReference='nope'))
        self.assertEqual(response.status_code, 200)

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_webhook_with_invalid_json_is_rejected(self):
        response = self._post_webhook(None, raw_body=b'not json')
        self.assertEqual(response.status_code, 400)

    #=== Signature verification ===#

    def test_signature_verification(self):
        raw_body = b'{"a": 1}'
        secret = self.provider.papi_webhook_secret
        now = 1757750400
        valid_header = self._sign(raw_body, timestamp=now)
        self._assert_does_not_raise(
            Forbidden, PapiController._verify_notification_signature,
            raw_body, valid_header, secret, now=now,
        )
        # Extra spaces and several v1 values (secret rotation) are accepted.
        signature = valid_header.split('v1=')[1]
        self._assert_does_not_raise(
            Forbidden, PapiController._verify_notification_signature,
            raw_body, f't={now}, v1=0000, v1={signature}', secret, now=now,
        )

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_signature_verification_failures(self):
        raw_body = b'{"a": 1}'
        secret = self.provider.papi_webhook_secret
        now = 1757750400
        valid_header = self._sign(raw_body, timestamp=now)
        for header, used_secret in (
            (None, secret),
            ('', secret),
            ('v1=abc', secret),
            ('t=abc,v1=abc', secret),
            (valid_header, None),
            (valid_header.replace('v1=', 'v1=0'), secret),
            ('t=%s,v1=é' % now, secret),
        ):
            with self.assertRaises(Forbidden, msg=header):
                PapiController._verify_notification_signature(
                    raw_body, header, used_secret, now=now
                )
        with self.assertRaises(Forbidden):
            PapiController._verify_notification_signature(
                raw_body, valid_header, secret, now=now + 301
            )

    #=== Customer return ===#

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_return_checks_status_and_redirects(self):
        tx = self._create_papi_transaction()
        url = self._build_url(PapiController._return_url)
        params = {'ref': tx.reference, 'access_token': tx._papi_get_return_access_token()}
        with patch(MAKE_REQUEST, return_value=self._link_status_data()):
            response = self.opener.get(url, params=params, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers['Location'].endswith('/payment/status'))
        self.assertEqual(tx.state, 'done')

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_return_without_valid_token_does_not_process(self):
        tx = self._create_papi_transaction()
        url = self._build_url(PapiController._return_url)
        with patch(HANDLE_NOTIFICATION) as handle_mock:
            response = self.opener.get(
                url, params={'ref': tx.reference, 'access_token': 'forged'}, allow_redirects=False
            )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(handle_mock.call_count, 0)

    @mute_logger('odoo.addons.payment_papi.controllers.main')
    def test_return_when_papi_is_unreachable_still_redirects(self):
        tx = self._create_papi_transaction()
        url = self._build_url(PapiController._return_url)
        params = {'ref': tx.reference, 'access_token': tx._papi_get_return_access_token()}
        with patch(MAKE_REQUEST, side_effect=ValidationError("Papi: down")):
            response = self.opener.get(url, params=params, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(tx.state, 'draft')
