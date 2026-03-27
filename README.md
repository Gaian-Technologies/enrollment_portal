# enrollment_portal

`enrollment_portal` is a small public-facing service that issues
single-use `data_hub` `enrollment_token` values after email verification.

It is intentionally separate from `data_hub`.

The supported workflow is:

1. user opens the portal page
2. user enters an email address and optional name
3. portal sends a verification email
4. user opens the verification link
5. portal calls the private `data_hub` admin invite API
6. portal shows a single-use short-lived `enrollment_token`

The browser never sees the `data_hub` admin bearer token.

## Required Environment

Copy [`.env.example`](/ssd2/Gaian/Workspace/enrollment_portal/.env.example) to
`.env` and fill the values.

The required values are:

- `ENROLLMENT_PORTAL_PUBLIC_BASE_URL`
- `ENROLLMENT_PORTAL_HUB_ADMIN_API_URL`
- `ENROLLMENT_PORTAL_HUB_ADMIN_TOKEN`
- `ENROLLMENT_PORTAL_SMTP_HOST`
- `ENROLLMENT_PORTAL_SMTP_PORT`
- `ENROLLMENT_PORTAL_SMTP_FROM_EMAIL`

## Start

```bash
cp .env.example .env
docker compose up -d --build
```

Local health check:

```bash
curl -sS http://127.0.0.1:8100/health
```

Open the request page:

```text
http://127.0.0.1:8100/request-access
```

## Deployment Shape

The supported deployment shape is one public Hub domain with Nginx routing:

- `/request-access` -> `enrollment_portal`
- `/verify` -> `enrollment_portal`
- `/api/v1/enrollment` -> `data_hub`

This service should not be exposed directly on a public high port.
Run it on `127.0.0.1:8100` and publish it through the same host Nginx instance
that already fronts `data_hub`.

Before public launch, add:

- CAPTCHA or Turnstile on the request form
- reverse-proxy rate limiting in Nginx

## Data Retention

The service stores:

- request email
- optional name
- client IP
- request timestamps
- issued `invite_id`

It does not store:

- the raw verification token
- the raw `enrollment_token`
- any user password

## Stop

```bash
docker compose down
```
