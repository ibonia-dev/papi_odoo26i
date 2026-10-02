# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.payment_papi import const


class PapiBackendPayWizard(models.TransientModel):
    _name = 'papi.backend.pay.wizard'
    _description = "Pay with Papi from the back-office"

    res_model = fields.Char(string="Document Model", required=True, readonly=True)
    res_id = fields.Integer(string="Document", required=True, readonly=True)
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Customer",
        readonly=True,
    )
    currency_id = fields.Many2one(comodel_name='res.currency', readonly=True)
    amount = fields.Monetary(
        string="Amount to Pay",
        currency_field='currency_id',
    )
    amount_max = fields.Monetary(
        string="Amount Due",
        currency_field='currency_id',
        readonly=True,
    )
    payer_phone = fields.Char(
        string="Payer Mobile Number",
        help="The number of the customer's Mobile Money account, used to prefill the Papi page. "
             "It is not saved on the customer.",
    )
    is_test_mode = fields.Boolean(compute='_compute_is_test_mode')

    #=== COMPUTE METHODS ===#

    @api.model
    def default_get(self, fields_list):
        """ Prefill the wizard with the amounts and the customer of the document to pay. """
        values = super().default_get(fields_list)
        document = self._get_document_from(values.get('res_model'), values.get('res_id'))
        if document and document._papi_backend_is_payable():
            values.update(self._get_payment_defaults(document))
        return values

    @api.model
    def _get_payment_defaults(self, document):
        """ Return the customer, currency, amounts and phone number to prefill for the document. """
        payment_values = document._get_default_payment_link_values()
        partner = self.env['res.partner'].browse(payment_values['partner_id'])
        return {
            'partner_id': partner.id,
            'currency_id': payment_values['currency_id'],
            'amount': payment_values['amount'],
            'amount_max': payment_values['amount_max'],
            'payer_phone': self._get_default_payer_phone(partner),
        }

    def _compute_is_test_mode(self):
        for wizard in self:
            document = wizard._get_document()
            provider = document and document._papi_backend_get_provider(wizard.amount or None)
            wizard.is_test_mode = bool(provider) and provider.state == 'test'

    #=== BUSINESS METHODS ===#

    def _get_document(self):
        """ Return the document to pay, or an empty recordset. """
        self.ensure_one()
        return self._get_document_from(self.res_model, self.res_id)

    @api.model
    def _get_document_from(self, res_model, res_id):
        """ Return the payable document with the given model and id, or an empty recordset. """
        empty = self.env['papi.backend.pay.mixin']
        if not res_model or res_model not in self.env or not res_id:
            return empty
        document = self.env[res_model].browse(res_id).exists()
        if not hasattr(document, '_papi_backend_is_payable'):
            return empty
        return document

    @api.model
    def _get_default_payer_phone(self, partner):
        """ Return the phone number of the partner, if it can be used by Papi. """
        for field_name in ('mobile', 'phone'):
            phone = partner[field_name] if field_name in partner._fields else False
            if phone and self.env['payment.transaction']._papi_format_phone(phone):
                return phone
        return False

    def action_pay(self):
        """ Create the Papi transaction and open the Papi payment page in a new tab.

        The payment is then handled like any other Papi payment: the status is confirmed by the
        notification, the return of the operator and the cron, never by the return alone.

        :return: The action opening the Papi payment page.
        :rtype: dict
        :raise UserError: If the document cannot be paid with Papi.
        """
        self.ensure_one()
        document = self._get_document()
        if not document:
            raise UserError(_("The document to pay does not exist anymore."))
        document.check_access('write')
        if not document._papi_backend_is_payable():
            raise UserError(_("This document cannot be paid at the moment."))
        if not self.currency_id:  # The wizard was created without the defaults of the document.
            self.write({
                key: value for key, value in self._get_payment_defaults(document).items()
                if key != 'payer_phone' or not self.payer_phone
            })

        if document._papi_backend_get_pending_transactions():
            raise UserError(_(
                "A Papi payment is already waiting for confirmation for this document. Check its "
                "status from the payment transactions before creating another one."
            ))
        currency = self.currency_id
        if currency.compare_amounts(self.amount, 0) <= 0 \
                or currency.compare_amounts(self.amount, self.amount_max) > 0:
            raise UserError(_(
                "The amount must be positive and cannot exceed the amount due (%s).",
                self.amount_max,
            ))
        provider = document._papi_backend_get_provider(self.amount)
        if not provider:
            raise UserError(_(
                "Papi is not available for this document. Papi must be enabled, the document must "
                "be in MGA, and the amount must be at least %(minimum)s MGA.",
                minimum=const.MINIMUM_AMOUNT,
            ))
        payment_method = provider.payment_method_ids.filtered(lambda m: m.code == 'papi')[:1]
        if not payment_method:
            raise UserError(_("The Papi payment method is not enabled on the provider."))

        tx_sudo = self._create_transaction(document, provider, payment_method)
        link_values = tx_sudo._get_specific_rendering_values({})
        return {'type': 'ir.actions.act_url', 'url': link_values['api_url'], 'target': 'new'}

    def _create_transaction(self, document, provider, payment_method):
        """ Create the draft transaction linked to the document, in the name of the customer. """
        self.ensure_one()
        Transaction = self.env['payment.transaction'].sudo()
        document_values = document._papi_backend_get_transaction_values()
        values = {
            'provider_id': provider.id,
            'payment_method_id': payment_method.id,
            'reference': Transaction._compute_reference('papi', **document_values),
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'operation': 'online_redirect',
            'tokenize': False,
            'landing_route': document._papi_backend_get_landing_route(),
            'papi_backend_origin': True,
            **document_values,
        }
        tx_sudo = Transaction.create(values)
        if self.payer_phone:
            # The phone number given by the operator replaces the one of the customer on the
            # transaction only (the transaction creation copies the number of the partner).
            tx_sudo.partner_phone = self.payer_phone
        tx_sudo._log_sent_message()
        return tx_sudo
