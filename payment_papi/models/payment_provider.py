# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

import logging
import uuid

import requests
from werkzeug.urls import url_join

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.const import REPORT_REASONS_MAPPING
from odoo.addons.payment_papi import const


_logger = logging.getLogger(__name__)


class PapiApiError(ValidationError):
    """ An error returned by the Papi API.

    The message can safely be displayed to the customer. The technical detail (HTTP status and
    error code returned by Papi) is only kept in the `papi_error_code` attribute, in the logs and
    on the transaction.
    """

    def __init__(self, message, papi_error_code=None):
        super().__init__(message)
        self.papi_error_code = papi_error_code


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('papi', "Papi")], ondelete={'papi': 'set default'}
    )
    papi_api_key = fields.Char(
        string="Papi API Key",
        help="The API key of the Papi shop, available in the Papi dashboard under Shops > "
             "Developer. One API key identifies one Papi shop.",
        required_if_provider='papi',
        groups='base.group_system',
    )
    papi_webhook_secret = fields.Char(
        string="Papi Notification Signing Secret",
        help="The secret used to verify the X-Papi-Signature header of notifications. It starts "
             "with 'pwhsec_'.",
        required_if_provider='papi',
        groups='base.group_system',
    )
    papi_shop_name = fields.Char(
        string="Papi Shop",
        help="The name of the Papi shop linked to the API key. Informational only: the shop is "
             "determined by the API key.",
    )
    papi_link_validity = fields.Integer(
        string="Payment Link Validity (hours)",
        help="How long the customer can use the Papi payment link before it expires.",
        default=const.LINK_VALIDITY_MIN,
    )

    #=== CONSTRAINT METHODS ===#

    @api.constrains('papi_link_validity')
    def _check_papi_link_validity(self):
        for provider in self.filtered(lambda p: p.code == 'papi'):
            validity = provider.papi_link_validity
            if not const.LINK_VALIDITY_MIN <= validity <= const.LINK_VALIDITY_MAX:
                raise ValidationError(_(
                    "The Papi payment link validity must be between %(min)s and %(max)s hours.",
                    min=const.LINK_VALIDITY_MIN, max=const.LINK_VALIDITY_MAX,
                ))

    @api.constrains('papi_webhook_secret')
    def _check_papi_webhook_secret(self):
        for provider in self.sudo().filtered(lambda p: p.code == 'papi' and p.papi_webhook_secret):
            if not provider.papi_webhook_secret.startswith(const.WEBHOOK_SECRET_PREFIX):
                raise ValidationError(_(
                    "The Papi notification signing secret must start with '%s'.",
                    const.WEBHOOK_SECRET_PREFIX,
                ))

    #=== BUSINESS METHODS ===#

    @api.model
    def _get_compatible_providers(
        self, company_id, partner_id, amount, *args, is_validation=False, report=None, **kwargs
    ):
        """ Override of `payment` to filter out Papi providers for validation operations, for
        currencies other than MGA and for amounts below the minimum accepted by Papi.

        The currency is checked here as well because the generic filter only relies on the
        `available_currency_ids` field, which the merchant may leave empty.
        """
        providers = super()._get_compatible_providers(
            company_id, partner_id, amount, *args,
            is_validation=is_validation, report=report, **kwargs
        )

        currency = self.env['res.currency'].browse(kwargs.get('currency_id')).exists()
        if currency and currency.name not in const.SUPPORTED_CURRENCIES:
            unfiltered_providers = providers
            providers = providers.filtered(lambda p: p.code != 'papi')
            payment_utils.add_to_report(
                report,
                unfiltered_providers - providers,
                available=False,
                reason=REPORT_REASONS_MAPPING['incompatible_currency'],
            )

        if is_validation:
            unfiltered_providers = providers
            providers = providers.filtered(lambda p: p.code != 'papi')
            payment_utils.add_to_report(
                report,
                unfiltered_providers - providers,
                available=False,
                reason=REPORT_REASONS_MAPPING['validation_not_supported'],
            )
        elif amount and amount < const.MINIMUM_AMOUNT:
            unfiltered_providers = providers
            providers = providers.filtered(lambda p: p.code != 'papi')
            payment_utils.add_to_report(
                report,
                unfiltered_providers - providers,
                available=False,
                reason=_("minimum amount of %s MGA not reached", const.MINIMUM_AMOUNT),
            )

        return providers

    @api.model
    def _papi_post_init_setup(self):
        """ Prepare Odoo so that Papi can actually be proposed to customers.

        Papi only accepts MGA (Ariary), which is archived by default in a standard Odoo database.
        If the eCommerce is installed, customers also need a *selectable* pricelist in MGA, since
        `_get_compatible_providers` filters Papi out for any other currency. This method makes both
        true without touching anything else: it only unarchives the currency if it is archived, and
        it only flips `selectable` on an existing MGA pricelist or creates a new one when none
        exists yet. It never changes a pricelist's currency, name, rules or website assignment.

        This method is idempotent and called both at installation and at every update of the
        module (see ``data/payment_provider_setup.xml``), so that it also fixes a database where
        the module was already installed before this method existed, or where an MGA pricelist was
        created without being made selectable.

        :return: None
        """
        mga = self.env['res.currency'].with_context(active_test=False).search(
            [('name', '=', 'MGA')], limit=1
        )
        if not mga:
            return  # Not expected on a standard Odoo database, but better safe than sorry.
        if not mga.active:
            mga.action_unarchive()
            _logger.info("Papi: activated the MGA currency.")

        if 'product.pricelist' not in self.env:
            return  # Neither `product` nor `website_sale` is installed.
        pricelist_sudo = self.env['product.pricelist'].sudo()
        if 'website_id' not in pricelist_sudo._fields:
            return  # The eCommerce is not installed; invoices use their own currency directly.

        mga_pricelists = pricelist_sudo.search([('currency_id', '=', mga.id)])
        unselectable_pricelists = mga_pricelists.filtered(lambda pl: not pl.selectable)
        if unselectable_pricelists:
            unselectable_pricelists.write({'selectable': True})
            _logger.info(
                "Papi: made %s existing MGA pricelist(s) selectable.", len(unselectable_pricelists)
            )

        if not mga_pricelists:
            websites = self.env['website'].sudo().search([])
            for website in websites:
                pricelist_sudo.create({
                    'name': _("Ariary (Papi)"),
                    'currency_id': mga.id,
                    'selectable': True,
                    'website_id': website.id,
                })
            if websites:
                _logger.info("Papi: created an MGA pricelist for %s website(s).", len(websites))

    def _get_supported_currencies(self):
        """ Override of `payment` to return the supported currencies. """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'papi':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        """ Override of `payment` to return the default payment method codes. """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'papi':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _papi_send_request(self, endpoint, payload=None, method='POST'):
        """ Send a request to the Papi API and return the raw response.

        The API key is only sent in the `Token` header and is never logged.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request, relative to the API URL.
        :param dict payload: The JSON payload of the request, for POST requests.
        :param str method: The HTTP method of the request.
        :return: The response of the request.
        :rtype: requests.Response
        :raise PapiApiError: If the API cannot be reached.
        """
        self.ensure_one()

        url = url_join(const.DEFAULT_API_URL, endpoint)
        headers = {
            'Token': self.sudo().papi_api_key or '',
            'Accept': 'application/json',
        }
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("Unable to reach Papi endpoint at %s", url)
            raise PapiApiError(
                "Papi: " + _("Could not establish the connection to the API."),
                papi_error_code='connection_error',
            )
        return response

    def _papi_make_request(self, endpoint, payload=None, method='POST'):
        """ Make a request to the Papi API and return the `data` part of the response.

        Only the URL, the HTTP status and the error code/message returned by Papi are logged. The
        error displayed to the customer does not contain any technical detail: the error code is
        only available in the `papi_error_code` attribute of the raised exception.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request, relative to the API URL.
        :param dict payload: The JSON payload of the request, for POST requests.
        :param str method: The HTTP method of the request.
        :return: The `data` part of the JSON-formatted content of the response.
        :rtype: dict
        :raise PapiApiError: If an HTTP error occurs.
        """
        response = self._papi_send_request(endpoint, payload=payload, method=method)
        content = self._papi_parse_response(response)
        if not response.ok:
            error = content.get('error') or {}
            _logger.error(
                "Papi API request %s %s failed with status %s: %s - %s",
                method, response.url, response.status_code,
                error.get('code'), error.get('message'),
            )
            raise PapiApiError(
                "Papi: " + _("The communication with the API failed. Please try again later."),
                papi_error_code=f"HTTP {response.status_code}"
                                f"{' ' + str(error['code']) if error.get('code') else ''}",
            )
        data = content.get('data')
        if not isinstance(data, dict):
            _logger.error(
                "Papi API request %s %s returned an unexpected response.", method, response.url
            )
            raise PapiApiError(
                "Papi: " + _("The API returned an unexpected response."),
                papi_error_code='unexpected_response',
            )
        return data

    @staticmethod
    def _papi_parse_response(response):
        """ Return the JSON content of the response, or an empty dict if it is not valid JSON. """
        try:
            content = response.json()
        except ValueError:
            return {}
        return content if isinstance(content, dict) else {}

    def action_papi_test_connection(self):
        """ Check that the API key is accepted by Papi and display the result.

        Papi has no dedicated endpoint for this: we read a payment link with a reference that
        cannot exist. A 404 answer means that the API key was accepted; a 401 means it was refused.

        Note: self.ensure_one()

        :return: The notification action.
        :rtype: dict
        """
        self.ensure_one()
        endpoint = f'payment-links/odoo-connection-check-{uuid.uuid4().hex}'
        try:
            response = self._papi_send_request(endpoint, method='GET')
        except ValidationError as error:
            return self._papi_notification(str(error), 'danger')

        if response.status_code in (200, 404):
            message = _("The connection to Papi succeeded: the API key is valid.")
            notification_type = 'success'
        elif response.status_code == 401:
            message = _("Papi refused the API key. Check that it is the key of the right shop.")
            notification_type = 'danger'
        else:
            error = self._papi_parse_response(response).get('error') or {}
            _logger.warning(
                "Papi connection check returned status %s: %s",
                response.status_code, error.get('code'),
            )
            message = _(
                "Papi answered with an unexpected status (HTTP %(status)s, code %(code)s).",
                status=response.status_code, code=error.get('code') or '-',
            )
            notification_type = 'warning'
        return self._papi_notification(message, notification_type)

    @staticmethod
    def _papi_notification(message, notification_type):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Papi",
                'message': message,
                'type': notification_type,
                'sticky': False,
            },
        }
