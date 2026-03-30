"""FastAPI app for the email-verified enrollment portal."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
from pathlib import Path

from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .config import Settings
from .emailer import EmailDeliveryError
from .electricity_reference_specs import (
    ElectricityReferenceValidationError,
    electricity_reference_specs_for_template,
    get_electricity_reference_spec,
    normalize_country_site_reference,
)
from .hub_client import HubAdminError
from .models import AccessRequestCreate, HealthResponse, VerificationCodeSubmit
from .runtime import PortalRuntime, RateLimitError, VerificationError
from .site_metadata_fields import (
    COUNTRY_NAMES,
    SiteMetadataValidationError,
    get_country_field,
    normalize_site_metadata,
)
from .turnstile import HumanVerificationFailed, HumanVerificationUnavailable

PACKAGE_ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_ROOT / "templates"))


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client is not None else "unknown"


def _render_template(
    request: Request,
    name: str,
    *,
    status_code: int = 200,
    **context,
) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request,
        name,
        {
            "request": request,
            **context,
        },
        status_code=status_code,
    )


def _format_invite_lifetime(hours: int) -> str:
    """Render the configured invite lifetime as simple user-facing text."""

    if hours % 24 == 0:
        days = hours // 24
        unit = "day" if days == 1 else "days"
        return f"{days} {unit}"

    unit = "hour" if hours == 1 else "hours"
    return f"{hours} {unit}"


def _empty_metadata_form_values(settings: Settings) -> dict[str, str]:
    return {field.key: "" for field in settings.site_metadata_fields}


def _request_access_lede(settings: Settings) -> str:
    if settings.enable_register_interest_flow:
        return (
            "Verify your email to continue. If Home Assistant is ready, the portal can issue an "
            "enrollment token now. Otherwise you can just register interest and we will be in touch."
        )
    return (
        "Enter your email address, an optional name, and any optional site details to receive a "
        "one-time verification code and enrollment token."
    )


def _verify_lede(settings: Settings) -> str:
    if settings.enable_register_interest_flow:
        return "Enter the verification code from your email to continue."
    return "Enter the verification code from your email to receive an enrollment token."


def _country_field_key(settings: Settings) -> str | None:
    field = get_country_field(settings.site_metadata_fields)
    return field.key if field is not None else None


def _country_reference_enabled(settings: Settings) -> bool:
    field = get_country_field(settings.site_metadata_fields)
    return field.enable_electricity_reference if field is not None else False


def _country_reference_specs_json() -> str:
    return json.dumps(
        electricity_reference_specs_for_template(),
        sort_keys=True,
        separators=(",", ":"),
    )


def _current_reference_spec(settings: Settings, form_values: dict[str, str]) -> dict[str, str] | None:
    if not _country_reference_enabled(settings):
        return None

    country_field = get_country_field(settings.site_metadata_fields)
    if country_field is None:
        return None

    spec = get_electricity_reference_spec(form_values.get(country_field.key, "").strip())
    if spec is None:
        return None

    return {
        "label": spec.label,
        "help_text": spec.help_text,
        "placeholder": spec.placeholder,
    }


def _request_access_context(
    settings: Settings,
    form_values: dict[str, str],
    *,
    form_error: str | None,
) -> dict[str, object]:
    return {
        "page_title": "Enrollment",
        "site_name": settings.site_name,
        "request_access_lede": _request_access_lede(settings),
        "turnstile_site_key": settings.turnstile_site_key,
        "enable_register_interest_flow": settings.enable_register_interest_flow,
        "metadata_fields": settings.site_metadata_fields,
        "country_options": COUNTRY_NAMES,
        "country_field_key": _country_field_key(settings),
        "country_reference_enabled": _country_reference_enabled(settings),
        "country_reference_specs_json": _country_reference_specs_json() if _country_reference_enabled(settings) else "{}",
        "current_reference_spec": _current_reference_spec(settings, form_values),
        "form_values": form_values,
        "form_error": form_error,
    }


def create_app(settings: Settings) -> FastAPI:
    runtime = PortalRuntime(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await runtime.start()
        yield

    app = FastAPI(title="Enrollment Portal", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.settings = settings
    app.mount("/enroll/static", StaticFiles(directory=str(PACKAGE_ROOT / "static")), name="portal-static")
    # Keep the legacy static path during the public route migration.
    app.mount("/static", StaticFiles(directory=str(PACKAGE_ROOT / "static")), name="legacy-static")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/", response_class=RedirectResponse)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/enroll", status_code=status.HTTP_302_FOUND)

    @app.get("/enroll", response_class=HTMLResponse)
    async def request_access_page(request: Request) -> HTMLResponse:
        form_values = {
            "email": "",
            "name": "",
            "request_mode": "",
            "site_reference_value": "",
            **_empty_metadata_form_values(settings),
        }
        return _render_template(
            request,
            "request_access.html",
            **_request_access_context(settings, form_values, form_error=None),
        )

    @app.post("/enroll", response_class=HTMLResponse)
    async def request_access_submit(request: Request) -> HTMLResponse:
        form = await request.form()
        email = str(form.get("email", "") or "")
        name = str(form.get("name", "") or "")
        request_mode = (
            str(form.get("request_mode", "") or "")
            if settings.enable_register_interest_flow
            else "issue_token_now"
        )
        turnstile_response = str(form.get("cf-turnstile-response", "") or "")
        site_reference_value = str(form.get("site_reference_value", "") or "")
        metadata_values = {
            field.key: str(form.get(field.key, "") or "")
            for field in settings.site_metadata_fields
        }
        form_values = {
            "email": email,
            "name": name,
            "request_mode": request_mode,
            "site_reference_value": site_reference_value,
            **metadata_values,
        }

        if settings.enable_register_interest_flow and request_mode not in {"issue_token_now", "register_interest"}:
            return _render_template(
                request,
                "request_access.html",
                **_request_access_context(
                    settings,
                    form_values,
                    form_error="Choose whether you want an enrollment token now or just want updates for later setup.",
                ),
                status_code=400,
            )

        try:
            normalized_metadata = normalize_site_metadata(settings.site_metadata_fields, metadata_values)
            country_field = get_country_field(settings.site_metadata_fields)
            country_value = (
                normalized_metadata.get(country_field.key)
                if country_field is not None
                else None
            )
            site_reference_metadata = (
                normalize_country_site_reference(country_value, site_reference_value)
                if _country_reference_enabled(settings)
                else {}
            )
            payload = AccessRequestCreate(
                email=email,
                name=name,
                request_mode=request_mode,
                site_metadata={
                    **normalized_metadata,
                    **site_reference_metadata,
                },
            )
            await runtime.submit_request(payload, _client_ip(request), turnstile_response)
        except RateLimitError:
            return _render_template(
                request,
                "request_access.html",
                **_request_access_context(settings, form_values, form_error="Too many requests. Wait and try again later."),
                status_code=429,
            )
        except HumanVerificationFailed:
            return _render_template(
                request,
                "request_access.html",
                **_request_access_context(settings, form_values, form_error="Complete the human verification and try again."),
                status_code=400,
            )
        except HumanVerificationUnavailable:
            return _render_template(
                request,
                "request_access.html",
                **_request_access_context(settings, form_values, form_error="Human verification is temporarily unavailable. Try again shortly."),
                status_code=502,
            )
        except EmailDeliveryError:
            return _render_template(
                request,
                "request_access.html",
                **_request_access_context(
                    settings,
                    form_values,
                    form_error="Could not deliver the verification email. The portal SES configuration or AWS access is unavailable.",
                ),
                status_code=502,
            )
        except SiteMetadataValidationError as err:
            return _render_template(
                request,
                "request_access.html",
                **_request_access_context(settings, form_values, form_error=str(err)),
                status_code=400,
            )
        except ElectricityReferenceValidationError as err:
            return _render_template(
                request,
                "request_access.html",
                **_request_access_context(settings, form_values, form_error=str(err)),
                status_code=400,
            )
        except ValidationError:
            return _render_template(
                request,
                "request_access.html",
                **_request_access_context(settings, form_values, form_error="Enter a valid email address and keep optional fields short."),
                status_code=400,
            )

        return _render_template(
            request,
            "verify_code.html",
            page_title="Enter verification code",
            site_name=settings.site_name,
            heading="Check your email",
            lede="A one-time verification code was sent to your inbox.",
            email=email.strip(),
            form_values={"code": ""},
            form_error=None,
        )

    @app.get("/enroll/verify", response_class=HTMLResponse)
    async def verify_code_page(request: Request) -> HTMLResponse:
        return _render_template(
            request,
            "verify_code.html",
            page_title="Enter verification code",
            site_name=settings.site_name,
            heading="Verify email",
            lede=_verify_lede(settings),
            email=None,
            form_values={"code": ""},
            form_error=None,
        )

    @app.post("/enroll/verify", response_class=HTMLResponse)
    async def verify_request(request: Request, code: str = Form(...)) -> HTMLResponse:
        form_values = {"code": code}
        try:
            payload = VerificationCodeSubmit(code=code)
            outcome = await runtime.verify_request(payload)
        except VerificationError:
            return _render_template(
                request,
                "verify_code.html",
                page_title="Enter verification code",
                site_name=settings.site_name,
                heading="Verify email",
                lede=_verify_lede(settings),
                email=None,
                form_values=form_values,
                form_error="This verification code is invalid, expired, or already used.",
                status_code=400,
            )
        except ValidationError:
            return _render_template(
                request,
                "verify_code.html",
                page_title="Enter verification code",
                site_name=settings.site_name,
                heading="Verify email",
                lede=_verify_lede(settings),
                email=None,
                form_values=form_values,
                form_error="Enter the 12-character verification code from your email.",
                status_code=400,
            )
        except HubAdminError:
            return _render_template(
                request,
                "error.html",
                page_title="Token issuance failed",
                site_name=settings.site_name,
                title="Could not issue enrollment token",
                message="The Hub could not issue an enrollment token right now.",
                status_code=502,
            )

        if outcome.request_mode == "register_interest":
            return _render_template(
                request,
                "interest_registered.html",
                page_title="Details received",
                site_name=settings.site_name,
            )

        return _render_template(
            request,
            "token_issued.html",
            page_title="Enrollment token issued",
            site_name=settings.site_name,
            hub_url=settings.public_base_url,
            enrollment_token=outcome.invite.enrollment_token,
            invite_lifetime=_format_invite_lifetime(settings.invite_expires_hours),
        )

    @app.get("/request-access", response_class=RedirectResponse)
    async def legacy_request_access() -> RedirectResponse:
        return RedirectResponse(url="/enroll", status_code=status.HTTP_308_PERMANENT_REDIRECT)

    @app.post("/request-access", response_class=HTMLResponse)
    async def legacy_request_access_submit(request: Request) -> HTMLResponse:
        return await request_access_submit(request)

    @app.get("/verify", response_class=RedirectResponse)
    async def legacy_verify() -> RedirectResponse:
        return RedirectResponse(url="/enroll/verify", status_code=status.HTTP_308_PERMANENT_REDIRECT)

    @app.post("/verify", response_class=HTMLResponse)
    async def legacy_verify_submit(request: Request, code: str = Form(...)) -> HTMLResponse:
        return await verify_request(request, code)

    return app
