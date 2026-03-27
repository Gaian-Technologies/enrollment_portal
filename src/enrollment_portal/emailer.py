"""SMTP email delivery for verification links."""

from __future__ import annotations

from email.message import EmailMessage
import smtplib

from .config import Settings


class EmailDeliveryError(Exception):
    """Raised when a verification email could not be delivered."""


class EmailSender:
    """Send verification emails through the configured SMTP relay."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send_verification_email(self, *, email: str, name: str, verification_url: str) -> None:
        recipient_name = name or "there"
        subject = f"{self._settings.site_name}: verify your email"
        body = (
            f"Hi {recipient_name},\n\n"
            f"Open the link below to receive your Home Assistant enrollment token:\n\n"
            f"{verification_url}\n\n"
            f"This link expires in {self._settings.verification_ttl_minutes} minutes.\n"
        )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._settings.smtp_from_email
        message["To"] = email
        message.set_content(body)

        try:
            with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port, timeout=30) as smtp:
                smtp.ehlo()
                if self._settings.smtp_starttls:
                    smtp.starttls()
                    smtp.ehlo()
                if self._settings.smtp_username:
                    smtp.login(self._settings.smtp_username, self._settings.smtp_password)
                smtp.send_message(message)
        except Exception as err:
            raise EmailDeliveryError("failed_to_deliver_email") from err
