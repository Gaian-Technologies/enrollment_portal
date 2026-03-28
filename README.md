# enrollment_portal

`enrollment_portal` is a small public-facing service that issues
single-use `data_hub` `enrollment_token` values after email verification.

It is intentionally separate from `data_hub`.

The supported workflow is:

1. user opens the portal page
2. user enters an email address and optional name
3. portal sends a verification email through Amazon SES
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
- `AWS_REGION`
- `ENROLLMENT_PORTAL_SES_FROM_EMAIL`

The supported delivery path is Amazon SES using the standard AWS credential
chain.

On EC2, the portal should use the instance role.
For local Docker testing, provide standard AWS credentials to the container
only if you need to send test emails before moving to EC2.

The verification flow does not work until all of these are true:

- the SES identity is verified
- the AWS region matches the SES identity region
- the portal has AWS permission to send mail
- `ENROLLMENT_PORTAL_SES_FROM_EMAIL` uses a verified SES identity

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

Before testing email delivery, replace the placeholder SES values in `.env`
with the real SES region and verified sender address.

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

The SES infrastructure is scaffolded in:

- [`/ssd2/Gaian/Workspace/infra/aws_cdk`](/ssd2/Gaian/Workspace/infra/aws_cdk)

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
