# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

from odoo import api, SUPERUSER_ID

from odoo.addons.payment_papi import const


def migrate(cr, version):
    """ Set the payment method matching the instrument on the existing Papi transactions. """
    env = api.Environment(cr, SUPERUSER_ID, {})
    for instrument, xmlid in const.PAYMENT_METHOD_XMLIDS.items():
        brand_method = env.ref(xmlid, raise_if_not_found=False)
        if brand_method:
            env['payment.transaction'].search([
                ('provider_code', '=', 'papi'),
                ('papi_payment_method', '=', instrument),
            ]).write({'payment_method_id': brand_method.id})
