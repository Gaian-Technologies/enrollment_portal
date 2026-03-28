"""Country-specific optional electricity supply identifiers for portal intake."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Callable


class ElectricityReferenceValidationError(Exception):
    """Raised when a submitted country-specific electricity identifier is invalid."""


@dataclass(slots=True, frozen=True)
class ElectricityReferenceSpec:
    """Optional electricity identifier shown for supported countries."""

    scheme: str
    label: str
    help_text: str
    placeholder: str
    normalizer: Callable[[str], str] = field(repr=False)

    def normalize(self, value: str) -> str:
        return self.normalizer(value)


COMMON_HELP_PREFIX = (
    "Optional for initial enrollment. We will need this identifier later."
)


def _normalize_nz_icp(value: str) -> str:
    cleaned = _strip_space_and_punctuation(value)
    if not re.fullmatch(r"\d{10}[A-Z]{2}\d{3}", cleaned):
        raise ElectricityReferenceValidationError("Enter a valid New Zealand ICP number.")
    return cleaned


def _normalize_au_nmi(value: str) -> str:
    cleaned = _strip_space_and_punctuation(value)
    if not re.fullmatch(r"[A-HJ-NP-Z0-9]{10,11}", cleaned):
        raise ElectricityReferenceValidationError("Enter a valid Australian NMI number.")
    return cleaned


def _normalize_ie_mprn(value: str) -> str:
    cleaned = _digits_only(value)
    if not re.fullmatch(r"10\d{9}", cleaned):
        raise ElectricityReferenceValidationError("Enter a valid Irish MPRN.")
    return cleaned


def _normalize_gb_mpan(value: str) -> str:
    cleaned = _digits_only(value)
    if len(cleaned) == 21:
        cleaned = cleaned[-13:]
    if not re.fullmatch(r"\d{13}", cleaned):
        raise ElectricityReferenceValidationError("Enter a valid Great Britain MPAN.")
    return cleaned


def _normalize_pt_cpe(value: str) -> str:
    cleaned = _strip_space_and_punctuation(value)
    if not re.fullmatch(r"PT[A-Z0-9]{18}", cleaned):
        raise ElectricityReferenceValidationError("Enter a valid Portuguese CPE.")
    return cleaned


def _normalize_es_cups(value: str) -> str:
    cleaned = _strip_space_and_punctuation(value)
    if not re.fullmatch(r"ES[A-Z0-9]{18,20}", cleaned):
        raise ElectricityReferenceValidationError("Enter a valid Spanish CUPS.")
    return cleaned


def _normalize_it_pod(value: str) -> str:
    cleaned = _strip_space_and_punctuation(value)
    if not re.fullmatch(r"IT[A-Z0-9]{12,13}", cleaned):
        raise ElectricityReferenceValidationError("Enter a valid Italian POD.")
    return cleaned


def _normalize_be_ean(value: str) -> str:
    cleaned = _digits_only(value)
    if not re.fullmatch(r"54\d{16}", cleaned):
        raise ElectricityReferenceValidationError("Enter a valid Belgian EAN code.")
    return cleaned


def _strip_space_and_punctuation(value: str) -> str:
    return re.sub(r"[\s\-]", "", value).upper()


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


_SPECS: dict[str, ElectricityReferenceSpec] = {
    "New Zealand": ElectricityReferenceSpec(
        scheme="nz_icp",
        label="ICP Number",
        help_text=(
            f"{COMMON_HELP_PREFIX} This number can often be found on your power bill."
        ),
        placeholder="0000044411DEB15",
        normalizer=_normalize_nz_icp,
    ),
    "Australia": ElectricityReferenceSpec(
        scheme="au_nmi",
        label="NMI Number",
        help_text=(
            f"{COMMON_HELP_PREFIX} This number can often be found on your electricity bill."
        ),
        placeholder="4102001234",
        normalizer=_normalize_au_nmi,
    ),
    "Ireland": ElectricityReferenceSpec(
        scheme="ie_mprn",
        label="MPRN",
        help_text=(
            f"{COMMON_HELP_PREFIX} This 11-digit number can often be found on your electricity bill."
        ),
        placeholder="10000000000",
        normalizer=_normalize_ie_mprn,
    ),
    "United Kingdom": ElectricityReferenceSpec(
        scheme="gb_mpan",
        label="MPAN",
        help_text=(
            f"{COMMON_HELP_PREFIX} This number can often be found on your electricity bill as the supply number."
        ),
        placeholder="1234567890123",
        normalizer=_normalize_gb_mpan,
    ),
    "Portugal": ElectricityReferenceSpec(
        scheme="pt_cpe",
        label="CPE",
        help_text=(
            f"{COMMON_HELP_PREFIX} This code can often be found on your electricity bill."
        ),
        placeholder="PT000200000000000000",
        normalizer=_normalize_pt_cpe,
    ),
    "Spain": ElectricityReferenceSpec(
        scheme="es_cups",
        label="CUPS",
        help_text=(
            f"{COMMON_HELP_PREFIX} This code can often be found on your electricity bill."
        ),
        placeholder="ES0021000000000000AB",
        normalizer=_normalize_es_cups,
    ),
    "Italy": ElectricityReferenceSpec(
        scheme="it_pod",
        label="POD",
        help_text=(
            f"{COMMON_HELP_PREFIX} This code can often be found on your electricity bill."
        ),
        placeholder="IT001E00000000",
        normalizer=_normalize_it_pod,
    ),
    "Belgium": ElectricityReferenceSpec(
        scheme="be_ean",
        label="EAN Code",
        help_text=(
            f"{COMMON_HELP_PREFIX} This code can often be found on your electricity bill."
        ),
        placeholder="541448800000000000",
        normalizer=_normalize_be_ean,
    ),
}


def get_electricity_reference_spec(country: str | None) -> ElectricityReferenceSpec | None:
    """Return the optional electricity reference spec for the selected country."""

    if not country:
        return None
    return _SPECS.get(country)


def electricity_reference_specs_for_template() -> dict[str, dict[str, str]]:
    """Return template-safe metadata for the supported country reference field specs."""

    return {
        country: {
            "scheme": spec.scheme,
            "label": spec.label,
            "help_text": spec.help_text,
            "placeholder": spec.placeholder,
        }
        for country, spec in sorted(_SPECS.items(), key=lambda item: item[0].casefold())
    }


def normalize_country_site_reference(
    country: str | None,
    raw_value: str,
) -> dict[str, str]:
    """Normalize an optional country-specific electricity identifier into generic metadata."""

    cleaned = raw_value.strip()
    if not cleaned:
        return {}

    spec = get_electricity_reference_spec(country)
    if spec is None:
        raise ElectricityReferenceValidationError(
            "No standardized electricity identifier is configured for the selected country."
        )

    return {
        "site_reference_scheme": spec.scheme,
        "site_reference_value": spec.normalize(cleaned),
    }
