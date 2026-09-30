# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import json
import logging
import time

from werkzeug.exceptions import Forbidden

from odoo import fields, http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.payment_papi import const


_logger = logging.getLogger(__name__)


class PapiController(http.Controller):
    _return_url = '/payment/papi/return'
    _webhook_url = '/payment/papi/webhook'

    @http.route(_return_url, type='http', methods=['GET'], auth='public')
    def papi_return_from_checkout(self, ref=None, access_token=None, **kwargs):
        """ Process the return of the customer from the Papi payment page.

        Papi uses the same kind of URL after a success or a failure, and has none for cancellations.
        The return itself is never taken as a proof of payment: the status of the transaction is
        read again from the Papi API before redirecting the customer to the status page.

        :param str ref: The reference of the transaction.
        :param str access_token: The token protecting the return URL of the transaction.
        :param dict kwargs: The extra parameters added by Papi, if any. They are ignored.
        """
        tx_sudo = request.env['payment.transaction'].sudo().search(
            [('reference', '=', ref or ''), ('provider_code', '=', 'papi')], limit=1
        )
        if not tx_sudo or not tx_sudo._papi_check_return_access_token(access_token):
            _logger.warning("Papi: received a return with an unknown reference or invalid token.")
        else:
            _logger.info("Papi: customer returned for transaction with reference %s.", ref)
            try:
                tx_sudo._handle_notification_data('papi', {'merchantPaymentReference': ref})
            except ValidationError:
                _logger.exception(
                    "Papi: unable to check the status of transaction with reference %s.", ref
                )
        return request.redirect('/payment/status')

    @http.route(_webhook_url, type='http', methods=['POST'], auth='public', csrf=False)
    def papi_webhook(self):
        """ Process the notification sent by Papi when the status of a payment changes.

        The notification is authenticated with its `X-Papi-Signature` header and with the
        notification token of the transaction. Its content is then only used to find the
        transaction, whose status is read again from the Papi API.

        :return: An empty JSON response to acknowledge the notification.
        :raise Forbidden: If the notification is not authentic.
        """
        raw_body = request.httprequest.get_data()
        try:
            data = json.loads(raw_body)
        except ValueError:
            _logger.warning("Papi: received a notification with an invalid JSON body.")
            return request.make_json_response({}, status=400)
        if not isinstance(data, dict):
            _logger.warning("Papi: received a notification with an unexpected JSON body.")
            return request.make_json_response({}, status=400)

        reference = data.get('merchantPaymentReference')
        _logger.info(
            "Papi: notification received for reference %s with payment status %s.",
            reference, data.get('paymentStatus'),
        )
        try:
            tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
                'papi', data
            )
        except ValidationError:
            # Acknowledge the notification: Papi would not do anything else with an error.
            _logger.exception("Papi: unable to find the transaction of the notification.")
            return request.make_json_response({})

        # Check the origin of the notification.
        self._verify_notification_signature(
            raw_body,
            request.httprequest.headers.get(const.SIGNATURE_HEADER),
            tx_sudo.provider_id.papi_webhook_secret,
        )
        if not tx_sudo._papi_check_notification_token(data.get('notificationToken')):
            _logger.warning(
                "Papi: received a notification with an invalid token for reference %s.", reference
            )
            raise Forbidden()

        # Handle the notification data.
        tx_sudo.papi_last_notification_date = fields.Datetime.now()
        try:
            tx_sudo._handle_notification_data('papi', data)
        except ValidationError:  # Acknowledge the notification; the cron will try again.
            _logger.exception(
                "Papi: unable to handle the notification for reference %s.", reference
            )
        return request.make_json_response({})

    @staticmethod
    def _verify_notification_signature(raw_body, signature_header, secret, now=None):
        """ Check that the signature of the notification is valid and recent.

        The header has the form `t=<unix seconds>,v1=<hex signature>`, where the signature is the
        HMAC-SHA256 of `<t>.<raw body>` keyed with the signing secret (including its `pwhsec_`
        prefix).

        :param bytes raw_body: The raw body of the notification.
        :param str signature_header: The value of the `X-Papi-Signature` header.
        :param str secret: The notification signing secret of the provider.
        :param int now: The current Unix time, for testing purposes.
        :return: None
        :raise Forbidden: If the signature is missing, invalid or too old.
        """
        if not signature_header:
            _logger.warning("Papi: received a notification with a missing signature.")
            raise Forbidden()
        if not secret:
            _logger.warning("Papi: no notification signing secret is configured.")
            raise Forbidden()

        timestamp, signatures = None, []
        for part in signature_header.split(','):
            key, _sep, value = part.strip().partition('=')
            if key == 't':
                timestamp = value
            elif key == 'v1':
                signatures.append(value)
        try:
            timestamp_int = int(timestamp)
        except (TypeError, ValueError):
            _logger.warning("Papi: received a notification with a malformed signature header.")
            raise Forbidden()

        now = int(time.time()) if now is None else now
        if abs(now - timestamp_int) > const.SIGNATURE_TOLERANCE:
            _logger.warning("Papi: received a notification with an expired signature.")
            raise Forbidden()

        signed_message = timestamp.encode() + b'.' + raw_body
        expected_signature = hmac.new(
            secret.encode(), signed_message, hashlib.sha256
        ).hexdigest().encode()
        if not any(
            hmac.compare_digest(signature.lower().encode(), expected_signature)
            for signature in signatures
        ):
            _logger.warning("Papi: received a notification with an invalid signature.")
            raise Forbidden()
