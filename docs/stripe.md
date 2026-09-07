# Stripe

## Testing Locally

Make sure you are in your `Sandbox` environment and go to API keys.

- Copy the `Secret` and `Publishable` key
- Open the respective BOSS app, that needs the integration, and paste those keys e.g. BOSS > Scheduler > Admin > Vendor integrations > Stripe

Install the Stripe CLI to test locally:

```
npm install --global @stripe/cli
```

Log in to Stripe

```
stripe login
```

Navigate through the wizard to select the correct account and environment.

Forward Stripe events to your local server that accepts the hook. Below configures the Scheduler app to recieve the webhook.

```
stripe listen --skip-verify --forward-to https://localhost/api/io.bithead.scheduler/webhooks/payment
```

`--skip-verify` is required when the site is local HTTPS. The CLI is a Go binary and does not trust a certificate that is only in the macOS keychain. The webhook itself is public; this flag is TLS, not BOSS auth.

When you start the listener, it will provide a webhook secret. That must be configured in the respective app's `Webhook secret` field.

## Configuration

BOSS calls the respective Stripe REST calls to generate payment links. It should not be necessary to create a checkout type (Full page, Embedded page).
