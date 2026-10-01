# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

{
    'name': "Payment Provider: Papi",
    'version': '19.0.1.0.2',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': "Accept Mobile Money (MVola, Orange Money, Airtel Money) and card payments in "
               "Madagascar through Papi.",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'author': "Papi",
    'website': "https://papi.mg",
    'depends': ['account_payment'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_papi_templates.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
        'views/account_move_views.xml',
        'wizards/papi_backend_pay_wizard_views.xml',

        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
        'data/ir_cron.xml',
        'data/payment_provider_setup.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_papi/static/src/scss/payment_form.scss',
        ],
    },
    'images': ['static/description/banner.png'],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'license': 'LGPL-3',
}
