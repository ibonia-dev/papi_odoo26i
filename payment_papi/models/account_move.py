# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from odoo import Command, api, models


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'papi.backend.pay.mixin']

    @api.depends('state', 'payment_state', 'amount_residual', 'currency_id', 'move_type')
    def _compute_papi_backend_payment_available(self):
        super()._compute_papi_backend_payment_available()

    def _papi_backend_is_payable(self):
        # Override of `papi.backend.pay.mixin`.
        self.ensure_one()
        return (
            self.move_type == 'out_invoice'
            and self.state == 'posted'
            and self.payment_state in ('not_paid', 'partial')
            and not self.currency_id.is_zero(self.amount_residual)
        )

    def _papi_backend_get_transaction_values(self):
        # Override of `papi.backend.pay.mixin`.
        return {'invoice_ids': [Command.set(self.ids)]}

    def _papi_backend_get_pending_transactions(self):
        # Override of `papi.backend.pay.mixin`.
        return self.env['payment.transaction'].sudo().search([
            ('invoice_ids', 'in', self.ids),
            ('provider_code', '=', 'papi'),
            ('state', '=', 'pending'),
        ])
