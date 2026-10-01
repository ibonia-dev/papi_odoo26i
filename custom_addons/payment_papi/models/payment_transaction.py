# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

from werkzeug import urls

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import consteq, email_normalize
from odoo.tools.misc import hmac as hmac_tool

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_papi import const


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    papi_notification_token = fields.Char(
        string="Papi Notification Token",
        help="The token returned by Papi when the payment link was created. Papi sends it back in "
             "every notification.",
        readonly=True,
        copy=False,
        groups='base.group_system',
    )
    papi_payment_link = fields.Char(string="Papi Payment Link", readonly=True, copy=False)
    papi_link_expiration = fields.Datetime(
        string="Papi Link Expiration", readonly=True, copy=False
    )
    papi_link_status = fields.Selection(
        string="Papi Link Status", selection=const.LINK_STATUS_SELECTION, readonly=True, copy=False
    )
    papi_payment_status = fields.Selection(
        string="Papi Payment Status",
        selection=const.PAYMENT_STATUS_SELECTION,
        readonly=True,
        copy=False,
    )
    papi_payment_method = fields.Selection(
        string="Papi Payment Instrument",
        selection=const.PAYMENT_METHOD_SELECTION,
        readonly=True,
        copy=False,
    )
    papi_message = fields.Char(
        string="Papi Message",
        help="The last failure reason reported by Papi, or the last error detected by Odoo.",
        readonly=True,
        copy=False,
    )
    papi_last_notification_date = fields.Datetime(
        string="Papi Last Notification",
        help="When Odoo last received a signed notification from Papi for this transaction.",
        readonly=True,
        copy=False,
    )
    papi_error_code = fields.Char(
        string="Papi Error Code",
        help="The last error code returned by the Papi API, or detected by Odoo (for instance "
             "'inconsistent_data' or 'paid_after_cancel'). Used to diagnose blocked transactions.",
        readonly=True,
        copy=False,
    )
    papi_backend_origin = fields.Boolean(
        string="Created from the Back-office",
        help="Whether an operator created the transaction with the \"Pay with Papi\" button of an "
             "invoice or a sales order, instead of the customer from the checkout or the portal.",
        readonly=True,
        copy=False,
    )
    papi_last_sync_date = fields.Datetime(
        string="Papi Last Status Check",
        help="When Odoo last read the status of this transaction from the Papi API.",
        readonly=True,
        copy=False,
    )

    #=== BUSINESS METHODS - PAYMENT FLOW ===#

    @api.model
    def _compute_reference(self, provider_code, prefix=None, separator='-', **kwargs):
        """ Override of `payment` to satisfy Papi requirements for references.

        The reference is sent to Papi as the merchant reference and then used in the path of the
        status URL (`payment-links/{reference}`). Characters such as `/` (invoice names) or spaces
        are therefore replaced by `-` so that the reference stays readable and URL-safe.

        :param str provider_code: The code of the provider handling the transaction.
        :param str prefix: The custom prefix used to compute the full reference.
        :param str separator: The custom separator used to separate the prefix from the suffix.
        :return: The unique reference for the transaction.
        :rtype: str
        """
        if provider_code == 'papi':
            if not prefix:
                # Compute the prefix here, as `super` would only do it for an empty prefix and the
                # result would not be sanitized.
                prefix = self.sudo()._compute_reference_prefix(
                    provider_code, separator, **kwargs
                ) or None
            if prefix:
                prefix = unicodedata.normalize('NFKD', prefix).encode('ascii', 'ignore').decode()
                prefix = re.sub(r'[^A-Za-z0-9_.-]+', '-', prefix).strip('-')
            prefix = prefix or payment_utils.singularize_reference_prefix(separator=separator)
        return super()._compute_reference(
            provider_code, prefix=prefix, separator=separator, **kwargs
        )

    def _get_specific_rendering_values(self, processing_values):
        """ Override of `payment` to create the Papi payment link and return its URL.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific rendering values.
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'papi':
            return res

        if self.amount < const.MINIMUM_AMOUNT:
            # The payment forms only filter on the amount due: a partial amount chosen by the
            # customer (e.g. on the invoice portal) can still be below the minimum of Papi.
            raise ValidationError("Papi: " + _(
                "The minimum amount for a Papi payment is %s MGA.", const.MINIMUM_AMOUNT
            ))

        payload = self._papi_prepare_payment_link_payload()
        link_data = self.provider_id._papi_make_request('payment-links', payload=payload)
        payment_link = link_data.get('paymentLink')
        if not payment_link:
            _logger.error(
                "Papi returned no payment link for transaction with reference %s.", self.reference
            )
            raise ValidationError("Papi: " + _("The API returned an unexpected response."))

        self.write({
            'papi_notification_token': link_data.get('notificationToken'),
            'papi_payment_link': payment_link,
            'papi_link_expiration': self._papi_parse_timestamp(
                link_data.get('linkExpirationDateTime')
            ),
            'papi_link_status': const.LINK_STATUS_ACTIVE,
        })
        _logger.info(
            "Papi payment link created for transaction with reference %s (expires on %s).",
            self.reference, self.papi_link_expiration,
        )
        return {'api_url': payment_link}

    def _papi_prepare_payment_link_payload(self):
        """ Prepare the payload of the payment link creation request.

        Only the data needed to process and reconcile the payment are sent.

        Note: self.ensure_one()

        :return: The request payload.
        :rtype: dict
        """
        self.ensure_one()
        provider = self.provider_id
        base_url = provider.get_base_url()
        return_url = urls.url_join(base_url, '/payment/papi/return') + '?' + urlencode({
            'ref': self.reference,
            'access_token': self._papi_get_return_access_token(),
        })
        amount = self.currency_id.round(self.amount)
        description = f"{self.company_id.name} - {self.reference}"[:const.DESCRIPTION_MAX_LENGTH]

        payload = {
            'amount': int(amount) if float(amount).is_integer() else amount,
            'currency': self.currency_id.name,
            'reference': self.reference,
            'clientName': self.partner_name or self.partner_email or self.partner_id.display_name
                          or _("Customer"),
            'description': description,
            'successUrl': return_url,
            'failureUrl': return_url,
            'notificationUrl': urls.url_join(base_url, '/payment/papi/webhook'),
            'validDuration': provider.papi_link_validity or const.LINK_VALIDITY_MIN,
        }
        email = email_normalize(self.partner_email or '')
        if email:
            payload['payerEmail'] = email
        phone = self._papi_format_phone(self.partner_phone)
        if phone:
            payload['payerPhone'] = phone
        if provider.state == 'test':
            payload.update(isTestMode=True, testReason="Odoo test")
        return payload

    @staticmethod
    def _papi_format_phone(phone):
        """ Return the phone number in the international Malagasy format, or None.

        Papi rejects the whole request if the phone number is invalid. As the phone number is
        optional, we only send the numbers we can confidently format.

        :param str phone: The phone number of the customer.
        :return: The formatted phone number (e.g. `+261340000000`), or None.
        :rtype: str | None
        """
        digits = re.sub(r'[^\d+]', '', phone or '')
        if digits.startswith('+261'):
            digits = digits[4:]
        elif digits.startswith('00261'):
            digits = digits[5:]
        elif digits.startswith('261') and len(digits) == 12:
            digits = digits[3:]
        elif digits.startswith('0') and len(digits) == 10:
            digits = digits[1:]
        else:
            return None
        if re.fullmatch(r'3\d{8}', digits):
            return f'+261{digits}'
        return None

    def _papi_get_return_access_token(self):
        """ Return the token protecting the return URL of the transaction.

        Note: self.ensure_one()
        """
        self.ensure_one()
        return hmac_tool(self.env(su=True), 'payment_papi_return', self.reference)

    def _papi_check_return_access_token(self, access_token):
        """ Return whether the access token of the return URL is valid for the transaction. """
        self.ensure_one()
        return bool(access_token) and consteq(access_token, self._papi_get_return_access_token())

    @staticmethod
    def _papi_parse_timestamp(timestamp_ms):
        """ Convert a Papi epoch timestamp in milliseconds to a naive UTC datetime. """
        if not timestamp_ms:
            return False
        try:
            timestamp = datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc)
            return timestamp.replace(tzinfo=None)
        except (TypeError, ValueError, OverflowError):
            return False

    #=== BUSINESS METHODS - NOTIFICATION PROCESSING ===#

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of `payment` to find the transaction based on Papi data.

        :param str provider_code: The code of the provider that handled the transaction.
        :param dict notification_data: The notification data sent by the provider.
        :return: The transaction if found.
        :rtype: recordset of `payment.transaction`
        :raise ValidationError: If the data match no transaction.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'papi' or len(tx) == 1:
            return tx

        reference = notification_data.get('merchantPaymentReference') \
            or notification_data.get('reference')
        if not reference:
            raise ValidationError("Papi: " + _("Received data with missing reference."))

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'papi')])
        if not tx:
            raise ValidationError(
                "Papi: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_notification_data(self, notification_data):
        """ Override of `payment` to process the transaction based on Papi data.

        The notification data are only used to find the transaction: its status is always read
        again from the Papi API, which is the only source of truth. The transaction row is locked
        so that the webhook, the customer return and the cron never process it concurrently.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider.
        :return: None
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'papi':
            return

        self.env.cr.execute(
            'SELECT id FROM payment_transaction WHERE id = %s FOR UPDATE', [self.id]
        )
        self.invalidate_recordset()
        if self.state == 'done':
            _logger.info(
                "Papi: transaction with reference %s is already done; skipping.", self.reference
            )
            return

        link_data = self.provider_id._papi_make_request(
            f'payment-links/{quote(self.reference, safe="")}', method='GET'
        )
        self._papi_apply_link_data(link_data)

    def _papi_apply_link_data(self, link_data):
        """ Check the payment link data read from Papi and update the transaction accordingly.

        Note: self.ensure_one()

        :param dict link_data: The `data` part of the payment link status response.
        :return: None
        """
        self.ensure_one()
        link_status = link_data.get('linkStatus')
        payment_status = link_data.get('paymentStatus')
        payment_method = link_data.get('paymentMethod')
        message = link_data.get('message')
        values = {
            'papi_last_sync_date': fields.Datetime.now(),
            'papi_link_status': link_status if link_status in dict(const.LINK_STATUS_SELECTION)
                                else False,
            'papi_payment_status': payment_status
                                   if payment_status in dict(const.PAYMENT_STATUS_SELECTION)
                                   else False,
            'papi_message': message or False,
            'papi_error_code': False,
        }
        for status, allowed in (
            (link_status, const.LINK_STATUS_SELECTION), (payment_status, const.PAYMENT_STATUS_SELECTION)
        ):
            if status and status not in dict(allowed):
                _logger.warning(
                    "Papi: unrecognized status %s for transaction with reference %s.",
                    status, self.reference,
                )
                values['papi_message'] = _(
                    "Unrecognized status received from Papi: %s.", status
                )
                values['papi_error_code'] = 'unknown_status'
        if self.papi_error_code == 'paid_after_cancel':
            # Keep the warning until the merchant has reconciled the payment.
            values.pop('papi_message')
            values.pop('papi_error_code')
        if payment_method in dict(const.PAYMENT_METHOD_SELECTION):
            values['papi_payment_method'] = payment_method
            brand_method = self.env.ref(
                const.PAYMENT_METHOD_XMLIDS[payment_method], raise_if_not_found=False
            )
            if brand_method:
                values['payment_method_id'] = brand_method.id
        if link_data.get('papiPaymentReference'):
            values['provider_reference'] = link_data['papiPaymentReference']
        if link_data.get('linkExpirationDateTime'):
            values['papi_link_expiration'] = self._papi_parse_timestamp(
                link_data['linkExpirationDateTime']
            )
        self.write(values)

        # Check that the data match the transaction.
        inconsistency = self._papi_find_inconsistency(link_data)
        if inconsistency:
            _logger.warning(
                "Papi: inconsistent data for transaction with reference %s: %s",
                self.reference, inconsistency,
            )
            self.write({'papi_message': inconsistency, 'papi_error_code': 'inconsistent_data'})
            self._set_error(_(
                "Your payment could not be verified. Please contact us with the reference %s.",
                self.reference,
            ))
            return

        # A payment made on a link whose transaction was cancelled (for instance because the link
        # had expired) is not confirmed automatically: another transaction may have been created
        # for the same document in the meantime, and a second confirmation would be a double
        # processing. The merchant reconciles it manually.
        if payment_status == const.PAYMENT_STATUS_SUCCESS and self.state == 'cancel':
            self._papi_flag_payment_after_cancel()
            return

        # Update the payment state.
        _logger.info(
            "Papi: transaction with reference %s has link status %s and payment status %s.",
            self.reference, link_status, payment_status,
        )
        is_link_active = link_status == const.LINK_STATUS_ACTIVE
        if payment_status == const.PAYMENT_STATUS_SUCCESS and link_status in (
            const.LINK_STATUS_PAID, const.LINK_STATUS_ACTIVE
        ):
            self._set_done()
            # Confirm the order or pay the invoice right away, rather than on the next cron run.
            self.env.ref('payment.cron_post_process_payment_tx')._trigger()
        elif is_link_active and payment_status == const.PAYMENT_STATUS_PENDING:
            self._set_pending()
        elif is_link_active and not payment_status:
            pass  # The customer has not tried to pay yet; the transaction stays in draft.
        elif is_link_active and payment_status == const.PAYMENT_STATUS_FAILED:
            self._set_error(_("Your payment was refused by Papi. Please try again."))
        elif link_status == const.LINK_STATUS_EXPIRED:
            self._set_canceled(_("The Papi payment link has expired."))
        elif link_status == const.LINK_STATUS_DISABLED:
            self._set_canceled(_("The Papi payment link has been disabled."))
        else:
            _logger.error(
                "Papi: unknown status combination for transaction with reference %s: link status "
                "%s, payment status %s.", self.reference, link_status, payment_status,
            )
            self.write({
                'papi_error_code': 'unknown_status',
                'papi_message': _(
                    "Unknown status received from Papi (link: %(link)s, payment: %(payment)s).",
                    link=link_status, payment=payment_status,
                ),
            })

    def _papi_flag_payment_after_cancel(self):
        """ Flag a transaction that Papi reports as paid although it was cancelled in Odoo.

        The transaction is not confirmed. The merchant is warned on the transaction and on the
        linked documents, once, and reconciles the payment manually (see `doc/diagnostic.md`).

        Note: self.ensure_one()
        """
        self.ensure_one()
        if self.papi_error_code == 'paid_after_cancel':
            return
        message = _(
            "Papi reports a successful payment for transaction %s, which had been cancelled in "
            "Odoo. It was not confirmed automatically: check the document and reconcile the "
            "payment manually.", self.reference,
        )
        _logger.warning(
            "Papi: transaction with reference %s was paid after having been cancelled.",
            self.reference,
        )
        self.write({'papi_error_code': 'paid_after_cancel', 'papi_message': message})
        self._log_message_on_linked_documents(message)

    def _papi_record_error(self, error):
        """ Keep on the transaction the technical error that prevented reading its status.

        :param Exception error: The error raised while reading the status from Papi.
        """
        self.ensure_one()
        self.sudo().write({
            'papi_error_code': getattr(error, 'papi_error_code', False) or 'api_error',
            'papi_message': str(error),
        })

    def _papi_find_inconsistency(self, link_data):
        """ Return a description of the first mismatch between the Papi data and the transaction.

        Note: self.ensure_one()

        :param dict link_data: The payment link data read from Papi.
        :return: The description of the inconsistency, or None if the data are consistent.
        :rtype: str | None
        """
        self.ensure_one()
        if link_data.get('merchantPaymentReference') != self.reference:
            return _("The reference returned by Papi does not match the transaction.")

        stored_token = self.sudo().papi_notification_token
        received_token = link_data.get('notificationToken') or ''
        if stored_token and not consteq(received_token, stored_token):
            return _("The notification token returned by Papi does not match the transaction.")

        currency = link_data.get('currency')
        if currency != self.currency_id.name:
            return _(
                "The currency returned by Papi (%(received)s) does not match the transaction "
                "(%(expected)s).", received=currency, expected=self.currency_id.name,
            )

        try:
            amount = float(link_data.get('amount'))
        except (TypeError, ValueError):
            return _("The amount returned by Papi is missing or invalid.")
        if self.currency_id.compare_amounts(amount, self.amount) != 0:
            return _(
                "The amount returned by Papi (%(received)s) does not match the transaction "
                "(%(expected)s).", received=amount, expected=self.amount,
            )
        return None

    def _papi_check_notification_token(self, notification_token):
        """ Return whether the token received in a notification matches the stored one. """
        self.ensure_one()
        stored_token = self.sudo().papi_notification_token
        return bool(stored_token and notification_token) \
            and consteq(str(notification_token), stored_token)

    #=== ACTIONS AND CRONS ===#

    def action_papi_check_status(self):
        """ Read the status of the transaction from Papi and update it.

        Used by the back-office button to diagnose blocked or unreconciled transactions.

        Note: self.ensure_one()

        :return: The notification action.
        :rtype: dict
        """
        self.ensure_one()
        self.check_access('read')
        tx_sudo = self.sudo()
        try:
            tx_sudo._handle_notification_data('papi', {'merchantPaymentReference': self.reference})
        except ValidationError as error:
            tx_sudo._papi_record_error(error)
            return self.provider_id._papi_notification(str(error), 'danger')
        return self.provider_id._papi_notification(_(
            "Papi status: link %(link)s, payment %(payment)s. Odoo status: %(state)s.",
            link=tx_sudo.papi_link_status or '-',
            payment=tx_sudo.papi_payment_status or '-',
            state=dict(self._fields['state']._description_selection(self.env))[tx_sudo.state],
        ), 'info')

    @api.model
    def _cron_papi_sync_pending(self):
        """ Read from Papi the status of the transactions that have not reached a final state.

        Papi sends each notification only once. This cron catches up with the notifications that
        were lost (server down, network error...) and with the payment links that expired.

        :return: None
        """
        limit_date = fields.Datetime.now() - timedelta(hours=const.SYNC_GRACE_HOURS)
        txs = self.search([
            ('provider_code', '=', 'papi'),
            ('state', 'in', ('draft', 'pending', 'error')),
            ('papi_payment_link', '!=', False),
            ('papi_link_expiration', '>=', limit_date),
        ], order='papi_last_sync_date asc nulls first, id asc', limit=const.SYNC_BATCH_SIZE)
        for tx in txs:
            try:
                with self.env.cr.savepoint():
                    tx._handle_notification_data('papi', {'merchantPaymentReference': tx.reference})
            except Exception as error:  # noqa: BLE001 - One failing transaction must not block the others.
                _logger.exception(
                    "Papi: unable to synchronize transaction with reference %s.", tx.reference
                )
                tx._papi_record_error(error)
