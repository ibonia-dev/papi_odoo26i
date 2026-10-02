/** @odoo-module **/

import PaymentForm from '@payment/js/payment_form';
import { RPCError } from '@web/core/network/rpc';

PaymentForm.include({

    /**
     * Override of `payment` to not display the error of Papi twice.
     *
     * The payment form already shows the error in the "Payment processing failed" dialog, then
     * rejects it again: the website would add a second "Validation Error" notification with the
     * same message.
     *
     * @override
     */
    async _initiatePaymentFlow(providerCode) {
        try {
            return await this._super(...arguments);
        } catch (error) {
            if (providerCode === 'papi' && error instanceof RPCError) {
                return; // The dialog of the payment form is enough.
            }
            throw error;
        }
    },

});
