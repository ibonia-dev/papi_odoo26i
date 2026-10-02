# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import time

from odoo.addons.payment.tests.common import PaymentCommon


class PapiCommon(PaymentCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The tests exercise the real processing and post-processing, which the base class of the
        # payment tests skips by default since Odoo 20.
        cls.enable_process_patcher = False
        cls.enable_post_process_patcher = False

        cls.currency_mga = cls._enable_currency('MGA')
        cls.country_madagascar = cls.env.ref('base.mg')

        cls.papi = cls._prepare_provider('papi', update_values={
            'papi_api_key': 'papi-test-api-key-0123456789',
            'papi_webhook_secret': 'pwhsec_' + 'a1' * 32,
            'papi_shop_name': "Test Shop",
        })
        cls.provider = cls.papi
        cls.payment_method = cls.env.ref('payment_papi.payment_method_papi')
        cls.payment_method.active = True
        cls.payment_method_id = cls.payment_method.id
        cls.payment_method_code = cls.payment_method.code

        cls.currency = cls.currency_mga
        cls.amount = 15000
        cls.reference = 'S00042'
        cls.partner.write({'country_id': cls.country_madagascar.id, 'phone': '034 12 345 67'})

        cls.notification_token = '5b8f0c3e-2a7d-4f61-9e0b-7c4d1a2e9f38'
        cls.papi_payment_reference = 'c1f4a5b0-6f5e-4e1b-9f0e-2b7d8a9c3d21'

        cls.link_creation_data = {
            'amount': 15000.0,
            'currency': 'MGA',
            'linkCreationDateTime': 1788065989011,
            'linkExpirationDateTime': 1788281989011,
            'paymentLink': 'https://payment-form.papi.mg/testshop/payments/eyJhbGciOiJIUzI1NiJ9.x',
            'paymentReference': cls.reference,
            'notificationToken': cls.notification_token,
            'isTestMode': True,
        }

    def _link_status_data(self, link_status='PAID', payment_status='SUCCESS', **overrides):
        """ Return the `data` of a payment link status response for the test transaction. """
        data = {
            'linkStatus': link_status,
            'paymentStatus': payment_status,
            'paymentMethod': 'MVOLA' if payment_status else None,
            'currency': 'MGA',
            'amount': 15000.0,
            'merchantPaymentReference': self.reference,
            'papiPaymentReference': self.papi_payment_reference if payment_status else None,
            'notificationToken': self.notification_token,
            'message': None,
            'linkCreationDateTime': 1788065989011,
            'linkExpirationDateTime': 1788281989011,
            'isTestMode': True,
        }
        data.update(overrides)
        return data

    def _notification_body(self, payment_status='SUCCESS', **overrides):
        body = {
            'paymentStatus': payment_status,
            'paymentMethod': 'MVOLA',
            'currency': 'MGA',
            'amount': 15000,
            'merchantPaymentReference': self.reference,
            'paymentReference': self.papi_payment_reference,
            'notificationToken': self.notification_token,
            'message': None,
        }
        body.update(overrides)
        return body

    def _sign(self, raw_body, timestamp=None, secret=None):
        """ Return the `X-Papi-Signature` header value for the given raw body. """
        timestamp = int(time.time()) if timestamp is None else timestamp
        secret = secret or self.provider.papi_webhook_secret
        signature = hmac.new(
            secret.encode(), f'{timestamp}.'.encode() + raw_body, hashlib.sha256
        ).hexdigest()
        return f't={timestamp},v1={signature}'

    def _create_papi_transaction(self, **values):
        """ Create a transaction as it is right after the creation of its payment link. """
        return self._create_transaction('redirect', **{
            'papi_notification_token': self.notification_token,
            'papi_payment_link': self.link_creation_data['paymentLink'],
            'papi_link_expiration': '2099-01-01 00:00:00',
            'papi_link_status': 'ACTIVE',
            **values,
        })
