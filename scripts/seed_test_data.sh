#!/bin/sh
# Add the Papi test data (MGA pricelist, customer in Madagascar, products from 200 to 50 000 MGA)
# to the papi_verif_<version> databases of Odoo 17, 18, 19 and 20. Safe to run again.
# Usage: scripts/seed_test_data.sh [17|18|19|20] [database]   (default database: papi_verif_<version>)
cd "$(dirname "$0")/.."
run() {  # run <version> <python> <odoo-bin> <conf>
    db="${DB:-papi_verif_$1}"
    echo "== Odoo $1 ($db)"
    "$2" "$3" shell -c "$4" -d "$db" --no-http < scripts/seed_test_data.py 2>&1 \
        | grep -E "PAPI_SEED_OK|Error|CRITICAL"
}
DB="$2"
[ -z "$1" ] || [ "$1" = 17 ] && run 17 compat/venv17/bin/python compat/odoo17/odoo-bin compat/odoo17.conf
[ -z "$1" ] || [ "$1" = 18 ] && run 18 venv18/bin/python odoo18/odoo-bin odoo18.conf
[ -z "$1" ] || [ "$1" = 19 ] && run 19 compat/venv19/bin/python compat/odoo19/odoo-bin compat/odoo19.conf
[ -z "$1" ] || [ "$1" = 20 ] && run 20 compat/venv20/bin/python compat/odoo20/odoo-bin compat/odoo20.conf
exit 0
