/** @odoo-module **/

import { _t } from '@web/core/l10n/translation';
import { RPCError } from '@web/core/network/rpc';
import { patch } from '@web/core/utils/patch';

import { PaymentForm } from '@payment/interactions/payment_form';

// The origin of the Papi payment page, which tells its opener when the payment is over.
const PAPI_ORIGIN = 'https://payment-form.papi.mg';
const POPUP_NAME = 'papi-payment-window';
const POPUP_FEATURES = 'width=500,height=700';
// The time left to the pop-up to send its message when it closes itself.
const POPUP_CLOSE_GRACE_MS = 1000;

patch(PaymentForm.prototype, {

    /**
     * Override of `payment` to open the pop-up window of Papi and to not display the error of Papi
     * twice.
     *
     * The window is opened before the request to the server: browsers only allow it right after a
     * click, and not once the customer has waited for the answer of the server.
     *
     * The payment form already shows the error in the "Payment processing failed" dialog, then
     * rejects it again: the website would add a second "Validation Error" notification with the
     * same message.
     *
     * @override
     */
    async _initiatePaymentFlow(providerCode, ...args) {
        this._papiPopup = null;
        if (providerCode === 'papi') {
            this._papiOpenPopup();
        }
        try {
            return await super._initiatePaymentFlow(providerCode, ...args);
        } catch (error) {
            if (providerCode === 'papi' && error instanceof RPCError) {
                return; // The dialog of the payment form is enough.
            }
            throw error;
        } finally {
            this._papiPopup?.close(); // Still there if the flow stopped before the redirection.
            this._papiPopup = null;
        }
    },

    /**
     * Override of `payment` to display the Papi page in the pop-up window, if there is one.
     *
     * Without pop-up window (redirection chosen in the provider, or window blocked by the
     * browser), the customer is redirected to the Papi page.
     *
     * @override
     */
    _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        const popup = this._papiPopup;
        this._papiPopup = null;
        if (providerCode !== 'papi' || !popup || popup.closed) {
            return super._processRedirectFlow(
                providerCode, paymentOptionId, paymentMethodCode, processingValues
            );
        }
        const div = document.createElement('div');
        div.innerHTML = processingValues['redirect_form_html'];
        const redirectForm = div.querySelector('form');
        popup.location.href = redirectForm.getAttribute('action');
        this._papiWaitForPopup(popup, redirectForm.dataset.papiReturnUrl);
    },

    /**
     * Open an empty pop-up window if the provider displays the Papi page in one.
     *
     * @private
     * @return {void}
     */
    _papiOpenPopup() {
        const checkedRadio = this.el.querySelector('input[name="o_payment_radio"]:checked');
        if (checkedRadio?.dataset.papiCheckoutMode === 'popup') {
            this._papiPopup = window.open('', POPUP_NAME, POPUP_FEATURES); // Null when blocked.
        }
    },

    /**
     * Cover the page with a "payment in progress" overlay until the payment in the pop-up window
     * is over, or until the customer cancels or closes the window.
     *
     * @private
     * @param {Window} popup - The pop-up window displaying the Papi page.
     * @param {string} returnUrl - The URL checking the payment, opened once Papi reports its end.
     * @return {void}
     */
    _papiWaitForPopup(popup, returnUrl) {
        const overlay = this._papiBuildOverlay(() => cancel());
        let finished = false;
        let closedTimeout;

        const stopWaiting = () => {
            window.removeEventListener('message', onMessage);
            clearInterval(closedPoll);
            clearTimeout(closedTimeout);
        };
        const finish = (url) => {
            if (finished) {
                return;
            }
            finished = true;
            stopWaiting();
            popup.close();
            window.location.assign(url); // The overlay stays until the page is left.
        };
        const cancel = () => {
            if (finished) {
                return;
            }
            finished = true;
            stopWaiting();
            popup.close();
            overlay.remove();
            this._enableButton();
        };
        const onMessage = (event) => {
            if (event.source !== popup) {
                return;
            }
            if (event.origin === PAPI_ORIGIN && event.data?.type === 'PAYMENT_STATUS') {
                finish(returnUrl || '/payment/status'); // The status is read again from Papi.
            } else if (event.data?.type === 'PAPI_RETURN') {
                finish('/payment/status'); // The return page of the pop-up has checked the status.
            }
        };
        const closedPoll = setInterval(() => {
            if (popup.closed) {
                clearInterval(closedPoll);
                closedTimeout = setTimeout(cancel, POPUP_CLOSE_GRACE_MS);
            }
        }, 500);

        window.addEventListener('message', onMessage);
        document.body.appendChild(overlay);
        this._enableButton(); // The overlay now blocks the page.
    },

    /**
     * Build the "payment in progress" overlay.
     *
     * @private
     * @param {Function} onCancel - Called when the customer clicks on the cancel button.
     * @return {HTMLElement} The overlay.
     */
    _papiBuildOverlay(onCancel) {
        const overlay = document.createElement('div');
        overlay.className = 'o_papi_pending_overlay d-flex align-items-center justify-content-center';
        const card = document.createElement('div');
        card.className = 'o_papi_pending_card bg-white rounded-4 shadow p-4 text-center';
        card.innerHTML = `
            <div class="spinner-border text-primary mb-3" role="status"></div>
            <h5 class="o_papi_pending_title"></h5>
            <p class="o_papi_pending_message text-muted small"></p>
            <button type="button" class="o_papi_pending_cancel btn btn-outline-secondary btn-sm"></button>
        `;
        card.querySelector('.o_papi_pending_title').textContent = _t("Payment in progress");
        card.querySelector('.o_papi_pending_message').textContent = _t(
            "A payment window has been opened. Complete the payment in that window to continue."
        );
        const cancelButton = card.querySelector('.o_papi_pending_cancel');
        cancelButton.textContent = _t("Cancel");
        cancelButton.addEventListener('click', onCancel);
        overlay.appendChild(card);
        return overlay;
    },

});
