# enrollment_portal

`enrollment_portal` is a small public-facing service that issues
single-use `data_hub` `enrollment_token` values after email verification.

It is intentionally separate from `data_hub`.

The supported workflow is:

1. user opens the portal page
2. user enters an email address, an optional name, and optional site metadata such as country
3. portal sends a verification code through Amazon SES
4. user enters that code in the portal
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
- `ENROLLMENT_PORTAL_TURNSTILE_SITE_KEY`
- `ENROLLMENT_PORTAL_TURNSTILE_SECRET_KEY`

The supported delivery path is Amazon SES using the standard AWS credential
chain.

The supported container runtime is a Linux host with Docker host networking.
The portal binds to `127.0.0.1:8100`, stays local-only, and reaches the
private Hub admin API on `127.0.0.1:8000`.

On EC2, the portal should use the instance role.
For local Docker testing, the supported path is a read-only mount of the
operator's `~/.aws` directory with `AWS_PROFILE` set to a deployment-capable
named profile such as `deployment`.

The verification flow does not work until all of these are true:

- the SES identity is verified
- the AWS region matches the SES identity region
- the portal has AWS permission to send mail
- `ENROLLMENT_PORTAL_SES_FROM_EMAIL` uses a verified SES identity
- Turnstile site and secret keys are configured

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

The example environment file uses Cloudflare's official Turnstile test keys so
the request form can be validated locally. Replace them with a real Turnstile
widget before public rollout.

## Turnstile Setup

Create one Cloudflare Turnstile widget for the public Hub hostname.

The validated public setup uses:

- widget mode: `managed`
- hostname: `hub.example.com`

Then copy the real widget keys into:

- `ENROLLMENT_PORTAL_TURNSTILE_SITE_KEY`
- `ENROLLMENT_PORTAL_TURNSTILE_SECRET_KEY`

in [`.env`](/ssd2/Gaian/Workspace/enrollment_portal/.env) and restart the
service:

```bash
docker compose up -d --build
```

The exact setup sequence is:

1. create the Turnstile widget in Cloudflare
2. set the hostname to `hub.example.com`
3. keep the widget mode as `managed`
4. copy the real site key and secret key into `.env`
5. rebuild the portal container
6. test the public flow at `https://hub.example.com/request-access`

The validated browser flow is:

1. open `https://hub.example.com/request-access`
2. complete the Turnstile challenge
3. submit email and any optional site details
4. receive the email verification code
5. open `https://hub.example.com/verify`
6. paste the code
7. copy the issued `enrollment_token`

For local Docker testing before EC2, also set:

- `AWS_PROFILE=deployment`
- `ENROLLMENT_PORTAL_BIND_HOST=127.0.0.1`
- `ENROLLMENT_PORTAL_HUB_ADMIN_API_URL=http://127.0.0.1:8000/api/v1/admin/invites`

and make sure that named profile exists in `~/.aws/credentials` and
`~/.aws/config` on the host running Docker Compose.

## Deployment Shape

The supported deployment shape is one public Hub domain with Nginx routing:

- `GET/POST /request-access` -> `enrollment_portal`
- `GET/POST /verify` -> `enrollment_portal`
- `GET /static/*` -> `enrollment_portal`
- `/api/v1/enrollment` -> `data_hub`

This service should not be exposed directly on a public high port.
Run it on `127.0.0.1:8100` with host networking and publish it through the
same host Nginx instance that already fronts `data_hub`.

Before public launch, add:

- reverse-proxy rate limiting in Nginx

The supported public posture is:

- Nginx edge rate limits on `/request-access` and `/verify`
- application-level limits in `enrollment_portal` per IP and per email
- Turnstile on request submission

The SES infrastructure is scaffolded in:

- [`/ssd2/Gaian/Workspace/infra/aws_cdk`](/ssd2/Gaian/Workspace/infra/aws_cdk)

The public Hub Nginx vhost must allow:

- `GET/POST /request-access`
- `GET/POST /verify`
- `GET /static/*`

The matching Nginx template lives at:

- [`/ssd2/Gaian/Workspace/data_hub/config/nginx/hub.public.conf.example`](/ssd2/Gaian/Workspace/data_hub/config/nginx/hub.public.conf.example)

## Data Retention

The service stores:

- request email
- optional name
- optional site metadata such as country
- client IP
- request timestamps
- issued `invite_id`

It does not store:

- the raw verification code
- the raw `enrollment_token`
- any user password

## Stop

```bash
docker compose down
```
