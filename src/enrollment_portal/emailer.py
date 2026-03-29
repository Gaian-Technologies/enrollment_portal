"""Amazon SES email delivery for verification codes."""

from __future__ import annotations

import logging
import os

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
        # Docker Compose may inject AWS_PROFILE as an empty string on EC2 when the
        # supported deployment intentionally uses the instance role instead.
        if not os.getenv("AWS_PROFILE", "").strip():
            os.environ.pop("AWS_PROFILE", None)
        self._client = boto3.client("sesv2", region_name=settings.aws_region)

    def send_verification_email(
        self,
        *,
        email: str,
        name: str,
        verification_code: str,
        verification_page_url: str,
    ) -> None:
        recipient_name = name or "there"
        subject = f"{self._settings.site_name}: your verification code"
        body = (
            f"Hi {recipient_name},\n\n"
            f"Enter this verification code in the portal to receive your Home Assistant enrollment token:\n\n"
            f"{verification_code}\n\n"
            f"Verification page:\n"
            f"{verification_page_url}\n\n"
            f"This code expires in {self._settings.verification_ttl_minutes} minutes.\n"
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
