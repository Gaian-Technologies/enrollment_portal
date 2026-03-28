"""FastAPI app for the email-verified enrollment portal."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from .config import Settings
from .emailer import EmailDeliveryError
from .hub_client import HubAdminError
from .models import AccessRequestCreate, HealthResponse, VerificationCodeSubmit
from .runtime import PortalRuntime, RateLimitError, VerificationError

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


def create_app(settings: Settings) -> FastAPI:
    runtime = PortalRuntime(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await runtime.start()
        yield

    app = FastAPI(title="Enrollment Portal", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory=str(PACKAGE_ROOT / "static")), name="static")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/", response_class=RedirectResponse)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/request-access", status_code=status.HTTP_302_FOUND)

    @app.get("/request-access", response_class=HTMLResponse)
    async def request_access_page(request: Request) -> HTMLResponse:
        return _render_template(
            request,
            "request_access.html",
            page_title="Request access",
            site_name=settings.site_name,
            form_values={"email": "", "name": ""},
            form_error=None,
        )

    @app.post("/request-access", response_class=HTMLResponse)
    async def request_access_submit(
        request: Request,
        email: str = Form(...),
        name: str = Form(default=""),
    ) -> HTMLResponse:
        form_values = {"email": email, "name": name}

        try:
            payload = AccessRequestCreate(email=email, name=name)
            await runtime.submit_request(payload, _client_ip(request))
        except RateLimitError:
            return _render_template(
                request,
                "request_access.html",
                page_title="Request access",
                site_name=settings.site_name,
                form_values=form_values,
                form_error="Too many requests. Wait and try again later.",
                status_code=429,
            )
        except EmailDeliveryError:
            return _render_template(
                request,
                "request_access.html",
                page_title="Request access",
                site_name=settings.site_name,
                form_values=form_values,
                form_error="Could not deliver the verification email. The portal SES configuration or AWS access is unavailable.",
                status_code=502,
            )
        except ValidationError:
            return _render_template(
                request,
                "request_access.html",
                page_title="Request access",
                site_name=settings.site_name,
                form_values=form_values,
                form_error="Enter a valid email address and a short name if provided.",
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

    @app.get("/verify", response_class=HTMLResponse)
    async def verify_code_page(request: Request) -> HTMLResponse:
        return _render_template(
            request,
            "verify_code.html",
            page_title="Enter verification code",
            site_name=settings.site_name,
            heading="Verify email",
            lede="Enter the verification code from your email to receive an enrollment token.",
            email=None,
            form_values={"code": ""},
            form_error=None,
        )

    @app.post("/verify", response_class=HTMLResponse)
    async def verify_request(request: Request, code: str = Form(...)) -> HTMLResponse:
        form_values = {"code": code}
        try:
            payload = VerificationCodeSubmit(code=code)
            invite = await runtime.verify_request(payload)
        except VerificationError:
            return _render_template(
                request,
                "verify_code.html",
                page_title="Enter verification code",
                site_name=settings.site_name,
                heading="Verify email",
                lede="Enter the verification code from your email to receive an enrollment token.",
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
                lede="Enter the verification code from your email to receive an enrollment token.",
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

        return _render_template(
            request,
            "token_issued.html",
            page_title="Enrollment token issued",
            site_name=settings.site_name,
            enrollment_token=invite.enrollment_token,
            expires_at=invite.expires_at,
        )

    return app
