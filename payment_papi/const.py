# Part of Papi Odoo integration. See LICENSE file for full copyright and licensing details.

# The default base URL of the Papi API. It is the same for test and production: Papi has no sandbox.
# See https://docs.papi.mg/docs/developper-guide/integration-guide/.
DEFAULT_API_URL = 'https://app.papi.mg/engine/api/'

# The currencies supported by Papi, in ISO 4217 format. Only MGA is settled today.
SUPPORTED_CURRENCIES = ['MGA']

# The minimum amount accepted by Papi when creating a payment link, in MGA.
MINIMUM_AMOUNT = 300

# The maximum length of the payment description accepted by Papi.
DESCRIPTION_MAX_LENGTH = 255

# The bounds of the `validDuration` parameter of the payment link, in hours.
LINK_VALIDITY_MIN = 1
LINK_VALIDITY_MAX = 596

# The name of the header carrying the notification signature, and the prefix of the signing secret.
SIGNATURE_HEADER = 'X-Papi-Signature'
WEBHOOK_SECRET_PREFIX = 'pwhsec_'

# The maximum difference, in seconds, between the signature timestamp and the current time.
SIGNATURE_TOLERANCE = 300

# The number of hours after the expiration of a payment link during which the cron keeps checking
# the status of a transaction that has not reached a final state.
SYNC_GRACE_HOURS = 24

# The number of transactions checked by the synchronization cron per run.
SYNC_BATCH_SIZE = 50

# The link statuses returned by Papi.
LINK_STATUS_ACTIVE = 'ACTIVE'
LINK_STATUS_PAID = 'PAID'
LINK_STATUS_EXPIRED = 'EXPIRED'
LINK_STATUS_DISABLED = 'DISABLED'

# The payment statuses returned by Papi.
PAYMENT_STATUS_SUCCESS = 'SUCCESS'
PAYMENT_STATUS_PENDING = 'PENDING'
PAYMENT_STATUS_FAILED = 'FAILED'

LINK_STATUS_SELECTION = [
    (LINK_STATUS_ACTIVE, "Active"),
    (LINK_STATUS_PAID, "Paid"),
    (LINK_STATUS_EXPIRED, "Expired"),
    (LINK_STATUS_DISABLED, "Disabled"),
]

PAYMENT_STATUS_SELECTION = [
    (PAYMENT_STATUS_SUCCESS, "Success"),
    (PAYMENT_STATUS_PENDING, "Pending"),
    (PAYMENT_STATUS_FAILED, "Failed"),
]

# The payment instruments that Papi can report as used for a payment.
PAYMENT_METHOD_SELECTION = [
    ('MVOLA', "MVola"),
    ('ORANGE_MONEY', "Orange Money"),
    ('AIRTEL_MONEY', "Airtel Money"),
    ('BRED', "Card (BRED)"),
]

# The Odoo payment method (brand of the Papi method) matching each payment instrument reported by
# Papi. It is set on the transaction once the instrument is known, so that Odoo shows the
# instrument actually used (the card provider settles VISA cards).
PAYMENT_METHOD_XMLIDS = {
    'MVOLA': 'payment_papi.payment_method_papi_mvola',
    'ORANGE_MONEY': 'payment_papi.payment_method_papi_orange_money',
    'AIRTEL_MONEY': 'payment_papi.payment_method_papi_airtel_money',
    'BRED': 'payment_papi.payment_method_papi_visa',
}

# The codes of the payment methods to activate when Papi is activated.
DEFAULT_PAYMENT_METHOD_CODES = {
    'papi',
    # Brand payment methods, only displayed as logos next to the Papi method.
    'papi_mvola',
    'papi_orange_money',
    'papi_airtel_money',
    'papi_visa',
}
