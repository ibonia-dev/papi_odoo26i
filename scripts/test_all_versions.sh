#!/bin/sh
# Install the Papi modules on an empty database and run their tests on Odoo 17, 18, 19 and 20.
# Requires the sources and virtual environments described in README.md (compat/ for 17, 19 and 20,
# odoo18/ and venv18/ for 18) and the database credentials of the matching *.conf files.
# The databases are created and dropped by this script. Usage: scripts/test_all_versions.sh [17|18|19|20]
cd "$(dirname "$0")/.."
export PGPASSWORD=$(awk -F' *= *' '/^db_password/{print $2}' odoo18.conf)
run() {  # run <version> <python> <odoo-bin> <conf>
    db="papi_tests_$1"
    psql -h localhost -U root -d postgres -qc "DROP DATABASE IF EXISTS $db WITH (FORCE)"
    echo "== Odoo $1"
    "$2" "$3" -c "$4" -d "$db" -i payment_papi,payment_papi_sale --without-demo=all \
        --test-tags /payment_papi,/payment_papi_sale --stop-after-init --http-port=8079 2>&1 \
        | grep -E "post-tests in|tests when loading|CRITICAL"
    psql -h localhost -U root -d postgres -qc "DROP DATABASE IF EXISTS $db WITH (FORCE)"
}
[ -z "$1" ] || [ "$1" = 17 ] && run 17 compat/venv17/bin/python compat/odoo17/odoo-bin compat/odoo17.conf
[ -z "$1" ] || [ "$1" = 18 ] && run 18 venv18/bin/python odoo18/odoo-bin odoo18.conf
[ -z "$1" ] || [ "$1" = 19 ] && run 19 compat/venv19/bin/python compat/odoo19/odoo-bin compat/odoo19.conf
[ -z "$1" ] || [ "$1" = 20 ] && run 20 compat/venv20/bin/python compat/odoo20/odoo-bin compat/odoo20.conf
exit 0
