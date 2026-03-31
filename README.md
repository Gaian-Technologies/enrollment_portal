# enrollment_portal

`enrollment_portal` is a small public-facing service that verifies email
addresses and can either issue a single-use `data_hub` `enrollment_token`
or register interest for later follow-up.

It is intentionally separate from `data_hub`. The Hub stays private on the
host, while this portal handles the public email-verification flow.

If you are discovering the stack from this repo first:

- [`data_hub`](/ssd2/Gaian/Workspace/data_hub) is the server-side API, MQTT, and InfluxDB stack
- [`ha_telemetry`](/ssd2/Gaian/Workspace/ha_telemetry) is the generic Home Assistant integration that uses the issued `enrollment_token`
- [`telemetry_website`](/ssd2/Gaian/Workspace/telemetry_website) is the generic public landing page that can link into this portal

The supported workflow is:

1. user opens the portal page
2. user enters an email address, an optional name, and optional site metadata such as country
3. portal sends a verification code through Amazon SES
4. user enters that code in the portal
5. if the user is ready now, the portal calls the private `data_hub` admin invite API
6. the portal either shows a single-use short-lived `enrollment_token` or confirms that the user's details were recorded for later follow-up

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
- `ENROLLMENT_PORTAL_ENABLE_REGISTER_INTEREST_FLOW`
- `ENROLLMENT_PORTAL_SHOW_HUB_URL_ON_TOKEN_PAGE`
- `ENROLLMENT_PORTAL_SITE_METADATA_FIELDS`

Optional internal-only operator values are:

- `ENROLLMENT_PORTAL_ENABLE_OPERATOR_UI`
- `ENROLLMENT_PORTAL_OPERATOR_USERNAME`
- `ENROLLMENT_PORTAL_OPERATOR_PASSWORD`

The supported delivery path is Amazon SES using the standard AWS credential
chain.

The supported container runtime is a Linux host with Docker host networking.
The portal binds to `127.0.0.1:8100`, stays local-only, and reaches the
private Hub admin API on `127.0.0.1:8000`.

On EC2, the portal should use the instance role.
If `AWS_PROFILE` is blank, the portal ignores it and falls back to the normal
AWS instance credential chain.
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
http://127.0.0.1:8100/enroll
```

Before testing email delivery, replace the placeholder SES values in `.env`
with the real SES region and verified sender address.

The example environment file uses Cloudflare's official Turnstile test keys so
the request form can be validated locally. Replace them with a real Turnstile
widget before public rollout.

Set `ENROLLMENT_PORTAL_ENABLE_REGISTER_INTEREST_FLOW=true` to let verified users
choose between:

- issuing an enrollment token now
- registering interest for later follow-up without issuing a token

`ENROLLMENT_PORTAL_SHOW_HUB_URL_ON_TOKEN_PAGE` defaults to `true`.
Set it to `false` for project-specific deployments where the Home Assistant
integration already knows the fixed Hub URL and only the enrollment token
should be shown.

## Internal Operator Dashboard

The portal also supports one internal-only operator dashboard at:

- `/ops`

It is disabled by default. To enable it, set:

- `ENROLLMENT_PORTAL_ENABLE_OPERATOR_UI=true`
- `ENROLLMENT_PORTAL_OPERATOR_USERNAME=<operator-username>`
- `ENROLLMENT_PORTAL_OPERATOR_PASSWORD=<operator-password>`

The dashboard uses HTTP basic auth and joins:

- portal request records
- Hub site status records

through the shared `invite_id`.

It shows:

- email
- name
- request mode
- request status
- country
- property roles
- site reference data
- linked `site_id`
- connected status
- last telemetry time

It also provides a CSV export at:

- `/ops/export.csv`

This route is operator-facing only. Do not expose it publicly without a
network or reverse-proxy access policy in front of it.

## Turnstile Setup

Create one Cloudflare Turnstile widget for the public site hostname.

The validated public setup uses:

- widget mode: `managed`
- hostname: `example.com`

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
2. set the hostname to `example.com`
3. keep the widget mode as `managed`
4. copy the real site key and secret key into `.env`
5. rebuild the portal container
6. test the public flow at `https://example.com/enroll`

Site metadata fields are configured through:

- `ENROLLMENT_PORTAL_SITE_METADATA_FIELDS`

The supported field types are:

- `text`
- `country`
- `select`

Example:

```dotenv
ENROLLMENT_PORTAL_SITE_METADATA_FIELDS=[{"key":"country","label":"Country","type":"country","required":false},{"key":"study_group","label":"Study group","type":"text","required":false,"description":"Optional study grouping label."},{"key":"property_roles","label":"Property role/s","type":"select","required":false,"multiple":true,"show_optional_hint":false,"description":"Select all that apply.","options":["Owner-occupier","Tenant","Landlord","Property manager","Other"]}]
```

`country` uses a native searchable country picker backed by a canonical list,
rejects invalid values, and stores a canonical country name.
`text` uses a simple text input and stores the trimmed submitted value.
`select` uses a validated dropdown and stores one of the configured option strings.
With `"multiple": true`, the portal accepts multiple selections and stores the
canonical selections as one ` | `-separated string.
Set `"show_optional_hint": false` on any non-required field that should remain
optional in validation without showing `(optional)` in the UI.
Any configured `text` field may also include an optional `description` string.

To add the optional country-specific electricity identifier field, enable it on
the country field itself:

```dotenv
ENROLLMENT_PORTAL_SITE_METADATA_FIELDS=[{"key":"country","label":"Country","type":"country","required":false,"enable_electricity_reference":true}]
```

Only when `enable_electricity_reference` is `true` does the portal reveal the
country-specific secondary field and store it generically as
`site_reference_scheme` and `site_reference_value`.

The initial built-in electricity identifier registry supports:

- New Zealand: `ICP Number`
- Australia: `NMI Number`
- Ireland: `MPRN`
- United Kingdom: `MPAN`
- Portugal: `CPE`
- Spain: `CUPS`
- Italy: `POD`
- Belgium: `EAN Code`

The validated browser flow is:

1. open `https://example.com/enroll`
2. complete the Turnstile challenge
3. submit email and any optional site details
4. if the selected country supports it, optionally enter the electricity
   site reference shown for that country; the portal stores a normalized
   version of what the user enters and does not hard-reject real-world bill
   formatting variations
5. receive the email verification code
6. open `https://example.com/enroll/verify`
7. paste the code
8. either copy the issued `enrollment_token` or finish on the verified
   interest-registration confirmation page

For local Docker testing before EC2, also set:

- `AWS_PROFILE=deployment`
- `ENROLLMENT_PORTAL_BIND_HOST=127.0.0.1`
- `ENROLLMENT_PORTAL_HUB_ADMIN_API_URL=http://127.0.0.1:8000/api/v1/admin/invites`

and make sure that named profile exists in `~/.aws/credentials` and
`~/.aws/config` on the host running Docker Compose.

## Deployment Shape

The supported deployment shape is one public apex domain with one host Nginx
instance routing:

- `GET /` -> static website landing page
- `GET /quicksetup` -> static website quick setup page
- `GET/POST /enroll` -> `enrollment_portal`
- `GET/POST /enroll/verify` -> `enrollment_portal`
- `GET /enroll/static/*` -> `enrollment_portal`
- `POST /api/v1/enrollment` -> `data_hub`

This service should not be exposed directly on a public high port.
Run it on `127.0.0.1:8100` with host networking and publish it through the
same host Nginx instance that already fronts `data_hub`.

Keep reverse-proxy rate limiting in Nginx as part of the supported deployment.

The supported public posture is:

- Nginx edge rate limits on `/enroll` and `/enroll/verify`
- application-level limits in `enrollment_portal` per IP and per email
- Turnstile on request submission

The SES infrastructure is scaffolded in:

- [`/ssd2/Gaian/Workspace/infra/aws_cdk`](/ssd2/Gaian/Workspace/infra/aws_cdk)

The public site Nginx vhost must allow:

- `GET/POST /enroll`
- `GET/POST /enroll/verify`
- `GET /enroll/static/*`

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
