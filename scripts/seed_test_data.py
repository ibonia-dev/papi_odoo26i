# Test data for the Papi modules, run inside `odoo-bin shell` (see seed_test_data.sh).
# Papi is only offered in MGA, to customers in Madagascar, from 300 MGA: this creates an MGA
# pricelist, a customer in Madagascar using it, and products around the minimum amount
# (published in the shop when website_sale is installed).
# Idempotent: records are found by their internal reference and updated on each run.

from datetime import date

PRODUCTS = [  # (internal reference, name, price in MGA)
    ('PAPI-TEST-00200', "Mofo gasy", 200),  # Below the minimum: Papi is not offered.
    ('PAPI-TEST-00300', "Sachet de thé", 300),  # The minimum amount.
    ('PAPI-TEST-00500', "Baguette de pain", 500),
    ('PAPI-TEST-01000', "Eau minérale 50 cl", 1000),
    ('PAPI-TEST-05000', "Café moulu 250 g", 5000),
    ('PAPI-TEST-50000', "Gousses de vanille Bourbon 100 g", 50000),
]

mga = env.ref('base.MGA')
mga.active = True
madagascar = env.ref('base.mg')
today = date.today()

# Show the pricelist on the quotations.
env['res.config.settings'].create({'group_product_pricelist': True}).execute()

Pricelist = env['product.pricelist']
pricelist = Pricelist.search([('name', '=', "Papi Test (MGA)")], limit=1) \
    or Pricelist.create({'name': "Papi Test (MGA)", 'currency_id': mga.id})
pricelist.currency_id = mga
if 'selectable' in Pricelist._fields:  # website_sale: let the shop visitor pick the MGA prices.
    pricelist.selectable = True

Template = env['product.template']
for ref, name, price in PRODUCTS:
    # The sales price is in the company currency; the MGA pricelist sets the exact MGA price.
    list_price = mga._convert(price, env.company.currency_id, env.company, today)
    vals = {'name': name, 'default_code': ref, 'list_price': list_price, 'sale_ok': True}
    if 'is_published' in Template._fields:  # website_sale: show the product in the shop.
        vals['is_published'] = True
    product = Template.search([('default_code', '=', ref)], limit=1)
    if product:
        product.write(vals)
    else:
        product = Template.create(vals)
    item = pricelist.item_ids.filtered(lambda i, p=product: i.product_tmpl_id == p)
    item_vals = {'applied_on': '1_product', 'product_tmpl_id': product.id,
                 'compute_price': 'fixed', 'fixed_price': price}
    if item:
        item.write(item_vals)
    else:
        pricelist.write({'item_ids': [(0, 0, item_vals)]})

Partner = env['res.partner']
customer = Partner.search([('ref', '=', 'PAPI-TEST')], limit=1) \
    or Partner.create({'name': "Client test Papi", 'ref': 'PAPI-TEST'})
customer.write({
    'city': "Antananarivo",
    'country_id': madagascar.id,
    'email': 'client.test.papi@example.com',
    'property_product_pricelist': pricelist.id,
})

env.cr.commit()
print(f"PAPI_SEED_OK products={len(PRODUCTS)} pricelist={pricelist.id} customer={customer.id}")
