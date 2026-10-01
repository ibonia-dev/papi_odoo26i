# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PapiBackendPayMixin(models.AbstractModel):
    """ Shared logic of the documents that an operator can pay with Papi from the back-office.

    Odoo's "Register Payment" only supports electronic payment methods through saved tokens, and
    Papi has no tokenization. The operator therefore creates a Papi payment link for the document
    (see `papi.backend.pay.wizard`) and pays it on the Papi page, on behalf of the customer.
    """
    _name = 'papi.backend.pay.mixin'
    _description = "Papi Back-office Payment Mixin"

    papi_backend_payment_available = fields.Boolean(
        compute='_compute_papi_backend_payment_available',
        help="Whether the document can be paid with Papi from the back-office.",
    )

    @api.depends_context('company')
    def _compute_papi_backend_payment_available(self):
        for record in self:
            record.papi_backend_payment_available = bool(
                record.id and record._papi_backend_is_payable()
                and record._papi_backend_get_provider()
            )

    def _papi_backend_is_payable(self):
        """ Return whether the state and the amounts of the document allow a payment.

        To be overridden by each payable model.
        """
        return False

    def _papi_backend_get_transaction_values(self):
        """ Return the values linking the transaction to the document, as create values. """
        return {}

    def _papi_backend_get_pending_transactions(self):
        """ Return the Papi transactions of the document that are waiting for a final status. """
        return self.env['payment.transaction']

    def _papi_backend_get_landing_route(self):
        """ Return the back-office route where the operator comes back after the payment. """
        self.ensure_one()
        return f'/odoo/{self._name}/{self.id}'

    def _papi_backend_get_provider(self, amount=None):
        """ Return the Papi provider that can be used to pay the document, if any.

        The same compatibility rules as for the checkout apply: company, country of the customer,
        currency (MGA) and minimum/maximum amounts.

        Note: self.ensure_one()

        :param float amount: The amount to pay; defaults to the amount due.
        :return: The compatible Papi provider, or an empty recordset.
        :rtype: payment.provider
        """
        self.ensure_one()
        values = self._get_default_payment_link_values()
        providers = self.env['payment.provider'].sudo()._get_compatible_providers(
            self.company_id.id,
            values['partner_id'],
            amount or values['amount'],
            currency_id=values['currency_id'],
        )
        return providers.filtered(lambda provider: provider.code == 'papi')[:1]

    def action_papi_pay_backend(self):
        """ Open the wizard to pay the document with Papi. """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Pay with Papi"),
            'res_model': 'papi.backend.pay.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_res_model': self._name, 'default_res_id': self.id},
        }
