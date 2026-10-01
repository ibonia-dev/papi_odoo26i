-- disable papi payment provider
UPDATE payment_provider
   SET papi_api_key = NULL,
       papi_webhook_secret = NULL;
