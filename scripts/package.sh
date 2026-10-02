#!/bin/sh
# Build the installable archives of the Papi modules, one per Odoo version, in dist/.
# Usage: scripts/package.sh            (all versions)
set -e
cd "$(dirname "$0")/.."
mkdir -p dist
build() {  # build <version> <directory containing payment_papi and payment_papi_sale>
    out="$PWD/dist/payment_papi-$1.1.0.0.zip"
    rm -f "$out"
    (cd "$2" && zip -rq "$out" payment_papi payment_papi_sale \
        -x '*.DS_Store' '*__pycache__*' '*.pyc' \
        'payment_papi/static/description/icosn.png' \
        'payment_papi/static/description/s.png' \
        'payment_papi/static/img/paspi.png')
    echo "$out"
}
build 18.0 custom_addons
build 17.0 ports/17.0
build 19.0 ports/19.0
build 20.0 ports/20.0
