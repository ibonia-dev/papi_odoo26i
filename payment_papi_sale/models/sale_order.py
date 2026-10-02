# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from odoo import Command, api, models


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'papi.backend.pay.mixin']

    @api.depends('state', 'amount_total', 'amount_paid', 'currency_id')
    def _compute_papi_backend_payment_available(self):
        super()._compute_papi_backend_payment_available()

    def _papi_backend_is_payable(self):
        # Override of `papi.backend.pay.mixin`.
        self.ensure_one()
        return (
            self.state in ('draft', 'sent', 'sale')
            and self.currency_id.compare_amounts(self.amount_total, self.amount_paid) > 0
        )

    def _papi_backend_get_transaction_values(self):
        # Override of `papi.backend.pay.mixin`.
        return {'sale_order_ids': [Command.set(self.ids)]}

    def _papi_backend_get_pending_transactions(self):
        # Override of `papi.backend.pay.mixin`.
        return self.env['payment.transaction'].sudo().search([
            ('sale_order_ids', 'in', self.ids),
            ('provider_code', '=', 'papi'),
            ('state', '=', 'pending'),
        ])
