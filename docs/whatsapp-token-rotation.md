# WhatsApp access-token rotation runbook

Use this runbook whenever the Meta WhatsApp Cloud API access token is replaced
or expires. Rotating a token does **not** normally require recreating the WABA
subscription. The helper checks that relationship and only creates it when the
current App is missing.

## Prerequisites

- Generate a new token in the Meta developer dashboard. For this POC, open
  **WhatsApp > Step 1: Try it > Generate token**.
- Authenticate `gcloud` with access to project `enterprise-agent-line-test`.
- Keep these non-secret identifiers in `.env`:

```dotenv
WHATSAPP_BUSINESS_ACCOUNT_ID=1355327990986716
META_APP_ID=4077974739002200
```

- Keep `.env` outside source control. Never pass an access token as a command-line
  argument, paste it into chat, or commit it.

## Recommended rotation

From the repository root, run:

```bash
.venv/bin/python scripts/rotate_whatsapp_token.py
```

Paste the token at the hidden prompt. The helper then:

1. validates the token against Meta Graph API;
2. checks whether this App is subscribed to the configured WABA and subscribes
   it only when missing;
3. updates `WHATSAPP_ACCESS_TOKEN` in the local `.env` atomically;
4. adds a new version to Secret Manager secret
   `eka-whatsapp-access-token` without putting the token in a process argument;
5. creates a Cloud Run revision that uses that exact secret version;
6. verifies Cloud Run health, rejection of an unauthenticated verification
   request, and the HMAC-signed webhook;
7. prints the service URL and the previous secret version for rollback.

If `.env` was updated manually first, run:

```bash
.venv/bin/python scripts/rotate_whatsapp_token.py --from-env
```

To perform read-only Meta checks without changing WABA, Secret Manager, or Cloud
Run state:

```bash
.venv/bin/python scripts/rotate_whatsapp_token.py --from-env --check-only
```

`--check-only` exits with status `2` when the token works but the current App is
not subscribed to the WABA.

## Success criteria

The command must report all of the following:

- `Current Meta App subscribed: true` after the subscription step;
- a new Secret Manager version;
- a ready Cloud Run revision;
- HTTP 200 for health and the signed WhatsApp webhook;
- rejection of a verification request that omits the token.

Finally, send a new text message from a number listed in
`WHATSAPP_ALLOWED_PHONE_NUMBERS`. The helper deliberately does not send a real
message because that final test acts on behalf of a user.

## Rollback

If the new revision fails its smoke tests, switch Cloud Run back to the previous
secret version printed by the helper:

```bash
gcloud run services update enterprise-knowledge-assistant-line \
  --project=enterprise-agent-line-test \
  --region=asia-east1 \
  --update-secrets=WHATSAPP_ACCESS_TOKEN=eka-whatsapp-access-token:PREVIOUS_VERSION
```

Do not roll back to a token that Meta has expired or revoked. In that case,
correct the new token or its permissions and rerun the helper.

## What does not need to be repeated

Routine access-token rotation does not require changing the callback URL,
verify token, App Secret, Phone Number ID, or WABA subscription. The subscription
is only recreated when the App/WABA pair changes or the relationship was removed.
