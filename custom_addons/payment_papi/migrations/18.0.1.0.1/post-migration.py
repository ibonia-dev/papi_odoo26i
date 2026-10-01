# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

import base64

from odoo import api, SUPERUSER_ID
from odoo.tools import file_open

# The brand payment methods are loaded with `noupdate`: refresh their logos explicitly.
BRAND_LOGOS = {
    'payment_papi.payment_method_papi_mvola': 'payment_papi/static/img/mvola.png',
    'payment_papi.payment_method_papi_orange_money': 'payment_papi/static/img/orange_money.png',
    'payment_papi.payment_method_papi_airtel_money': 'payment_papi/static/img/airtel_money.png',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, path in BRAND_LOGOS.items():
        method = env.ref(xmlid, raise_if_not_found=False)
        if method:
            with file_open(path, 'rb') as logo:
                method.image = base64.b64encode(logo.read())
