"""Amazon SES email delivery for verification links."""

from __future__ import annotations

import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .config import Settings

LOGGER = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when a verification email could not be delivered."""


class EmailSender:
    """Send verification emails through Amazon SES using the AWS credential chain."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = boto3.client("sesv2", region_name=settings.aws_region)

    def send_verification_email(self, *, email: str, name: str, verification_url: str) -> None:
        recipient_name = name or "there"
        subject = f"{self._settings.site_name}: verify your email"
        body = (
            f"Hi {recipient_name},\n\n"
            f"Open the link below to receive your Home Assistant enrollment token:\n\n"
            f"{verification_url}\n\n"
            f"This link expires in {self._settings.verification_ttl_minutes} minutes.\n"
        )

        request: dict[str, object] = {
            "FromEmailAddress": self._settings.ses_from_email,
            "Destination": {
                "ToAddresses": [email],
            },
            "Content": {
                "Simple": {
                    "Subject": {
                        "Data": subject,
                    },
                    "Body": {
                        "Text": {
                            "Data": body,
                        }
                    },
                }
            },
        }
        if self._settings.ses_configuration_set:
            request["ConfigurationSetName"] = self._settings.ses_configuration_set

        try:
            self._client.send_email(**request)
        except (BotoCoreError, ClientError) as err:
            LOGGER.exception(
                "Failed to deliver verification email via SES region=%s from_email=%s configuration_set=%s",
                self._settings.aws_region,
                self._settings.ses_from_email,
                self._settings.ses_configuration_set or "<none>",
            )
            raise EmailDeliveryError("failed_to_deliver_email") from err
