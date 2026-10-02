import { RPCError } from '@web/core/network/rpc';
import { patch } from '@web/core/utils/patch';

import { PaymentForm } from '@payment/interactions/payment_form';

patch(PaymentForm.prototype, {

    /**
     * Override of `payment` to not display the error of Papi twice.
     *
     * The payment form already shows the error in the "Payment processing failed" dialog, then
     * rejects it again: the website would add a second "Validation Error" notification with the
     * same message.
     *
     * @override
     */
    async _initiatePaymentFlow(providerCode, ...args) {
        try {
            return await super._initiatePaymentFlow(providerCode, ...args);
        } catch (error) {
            if (providerCode === 'papi' && error instanceof RPCError) {
                return; // The dialog of the payment form is enough.
            }
            throw error;
        }
    },

});
