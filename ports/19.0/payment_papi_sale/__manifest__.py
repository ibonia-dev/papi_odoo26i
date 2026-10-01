# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

{
    'name': "Papi: Sales Orders",
    'version': '19.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': "Let an operator pay a sales order with Papi from the back-office.",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'author': "Papi",
    'website': "https://papi.mg",
    'depends': ['payment_papi', 'sale'],
    'data': [
        'views/sale_order_views.xml',
    ],
    'auto_install': True,
    'installable': True,
    'license': 'LGPL-3',
}
