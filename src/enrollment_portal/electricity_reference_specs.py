"""Country-specific optional electricity supply identifiers for portal intake."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Callable


class ElectricityReferenceValidationError(Exception):
    """Raised when a submitted country-specific electricity identifier is unusable."""


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
    return _normalize_alphanumeric_reference(value, prefixes=("ICP",))


def _normalize_au_nmi(value: str) -> str:
    return _normalize_alphanumeric_reference(value, prefixes=("NMI",))


def _normalize_ie_mprn(value: str) -> str:
    return _normalize_digit_reference(value, prefixes=("MPRN",))


def _normalize_gb_mpan(value: str) -> str:
    cleaned = _normalize_digit_reference(value, prefixes=("MPAN",))
    if len(cleaned) == 21:
        cleaned = cleaned[-13:]
    return cleaned


def _normalize_pt_cpe(value: str) -> str:
    return _normalize_alphanumeric_reference(value, prefixes=("CPE",))


def _normalize_es_cups(value: str) -> str:
    return _normalize_alphanumeric_reference(value, prefixes=("CUPS",))


def _normalize_it_pod(value: str) -> str:
    return _normalize_alphanumeric_reference(value, prefixes=("POD",))


def _normalize_be_ean(value: str) -> str:
    return _normalize_digit_reference(value, prefixes=("EAN",))


def _normalize_alphanumeric_reference(
    value: str,
    *,
    prefixes: tuple[str, ...] = (),
) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    if len(cleaned) < 4:
        raise ElectricityReferenceValidationError("Enter the identifier shown on your electricity bill.")
    if len(cleaned) > 64:
        raise ElectricityReferenceValidationError("Keep the identifier under 64 characters.")
    return cleaned


def _normalize_digit_reference(
    value: str,
    *,
    prefixes: tuple[str, ...] = (),
) -> str:
    cleaned = _normalize_alphanumeric_reference(value, prefixes=prefixes)
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 4:
        raise ElectricityReferenceValidationError("Enter the identifier shown on your electricity bill.")
    return digits


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
