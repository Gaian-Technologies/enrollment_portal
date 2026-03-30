"""Configurable site-metadata field definitions for the public portal."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Literal

import pycountry

FIELD_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SUPPORTED_FIELD_TYPES = {"text", "country", "select"}


class SiteMetadataValidationError(Exception):
    """Raised when submitted site metadata does not satisfy the configured fields."""


@dataclass(slots=True, frozen=True)
class SiteMetadataField:
    """Operator-configured portal field for one site metadata value."""

    key: str
    label: str
    field_type: Literal["text", "country", "select"]
    required: bool = False
    placeholder: str = ""
    description: str = ""
    enable_electricity_reference: bool = False
    options: tuple[str, ...] = ()
    multiple: bool = False
    show_optional_hint: bool = True


COUNTRY_NAMES: tuple[str, ...] = tuple(
    sorted({country.name for country in pycountry.countries}, key=str.casefold)
)


def default_site_metadata_fields() -> tuple[SiteMetadataField, ...]:
    """Return the supported default portal site-metadata fields."""

    return (
        SiteMetadataField(
            key="country",
            label="Country",
            field_type="country",
            required=False,
        ),
    )


def load_site_metadata_fields(raw_value: str) -> tuple[SiteMetadataField, ...]:
    """Parse the env-configured field list or fall back to the supported default."""

    cleaned = raw_value.strip()
    if not cleaned:
        return default_site_metadata_fields()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as err:
        raise ValueError("ENROLLMENT_PORTAL_SITE_METADATA_FIELDS must be valid JSON") from err

    if not isinstance(payload, list):
        raise ValueError("ENROLLMENT_PORTAL_SITE_METADATA_FIELDS must be a JSON list")

    fields: list[SiteMetadataField] = []
    seen_keys: set[str] = set()
    country_field_count = 0
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Each site metadata field must be a JSON object")

        key = str(item.get("key", "")).strip().lower()
        label = str(item.get("label", "")).strip()
        field_type = str(item.get("type", "text")).strip().lower()
        required = bool(item.get("required", False))
        placeholder = str(item.get("placeholder", "")).strip()
        description = str(item.get("description", "")).strip()
        enable_electricity_reference = bool(item.get("enable_electricity_reference", False))
        multiple = bool(item.get("multiple", False))
        show_optional_hint = bool(item.get("show_optional_hint", True))

        if not FIELD_KEY_PATTERN.fullmatch(key):
            raise ValueError("Site metadata field keys must be lower_snake_case")
        if key in seen_keys:
            raise ValueError("Site metadata field keys must be unique")
        if not label:
            raise ValueError("Each site metadata field requires a label")
        if field_type not in SUPPORTED_FIELD_TYPES:
            raise ValueError(f"Unsupported site metadata field type: {field_type}")
        options = item.get("options", [])
        if field_type == "country":
            normalized_type: Literal["text", "country", "select"] = "country"
        elif field_type == "select":
            normalized_type = "select"
        else:
            normalized_type = "text"
        if normalized_type == "country":
            country_field_count += 1
            if country_field_count > 1:
                raise ValueError("Only one country field is supported")
        elif enable_electricity_reference:
            raise ValueError("enable_electricity_reference is only supported on country fields")
        elif multiple and normalized_type != "select":
            raise ValueError("multiple is only supported on select fields")

        normalized_options: tuple[str, ...] = ()
        if normalized_type == "select":
            if not isinstance(options, list) or not options:
                raise ValueError("Select fields require a non-empty options list")
            cleaned_options = tuple(
                str(option).strip()
                for option in options
                if str(option).strip()
            )
            if not cleaned_options:
                raise ValueError("Select fields require at least one non-empty option")
            if len(set(cleaned_options)) != len(cleaned_options):
                raise ValueError("Select field options must be unique")
            normalized_options = cleaned_options

        fields.append(
            SiteMetadataField(
                key=key,
                label=label,
                field_type=normalized_type,
                required=required,
                placeholder=placeholder,
                description=description,
                enable_electricity_reference=enable_electricity_reference,
                options=normalized_options,
                multiple=multiple,
                show_optional_hint=show_optional_hint,
            )
        )
        seen_keys.add(key)

    return tuple(fields)


def normalize_site_metadata(
    fields: tuple[SiteMetadataField, ...],
    raw_values: dict[str, Any],
) -> dict[str, str]:
    """Normalize configured site metadata values into canonical stored strings."""

    normalized: dict[str, str] = {}
    for field in fields:
        if field.field_type == "country":
            raw_value = str(raw_values.get(field.key, "") or "").strip()
            if not raw_value:
                if field.required:
                    raise SiteMetadataValidationError(f"{field.label} is required.")
                continue
            normalized[field.key] = _normalize_country(raw_value)
            continue

        if field.field_type == "select":
            raw_value = raw_values.get(field.key, [])
            normalized_value = _normalize_select(field, raw_value)
            if not normalized_value:
                if field.required:
                    raise SiteMetadataValidationError(f"{field.label} is required.")
                continue
            normalized[field.key] = normalized_value
            continue

        raw_value = str(raw_values.get(field.key, "") or "").strip()
        if not raw_value:
            if field.required:
                raise SiteMetadataValidationError(f"{field.label} is required.")
            continue
        if len(raw_value) > 256:
            raise SiteMetadataValidationError(f"{field.label} must be 256 characters or fewer.")
        normalized[field.key] = raw_value

    return normalized


def get_country_field(fields: tuple[SiteMetadataField, ...]) -> SiteMetadataField | None:
    """Return the configured country field if the portal uses one."""

    for field in fields:
        if field.field_type == "country":
            return field
    return None


def _normalize_country(value: str) -> str:
    try:
        match = pycountry.countries.lookup(value)
    except LookupError as err:
        raise SiteMetadataValidationError("Select a valid country from the list.") from err
    return match.name


def _normalize_select(field: SiteMetadataField, value: Any) -> str:
    if field.multiple:
        if not isinstance(value, list):
            candidates = [str(value).strip()] if str(value).strip() else []
        else:
            candidates = [str(item).strip() for item in value if str(item).strip()]
        if not candidates:
            return ""
        invalid = [item for item in candidates if item not in field.options]
        if invalid:
            raise SiteMetadataValidationError(f"Select valid {field.label.lower()} options.")
        unique_values: list[str] = []
        for item in candidates:
            if item not in unique_values:
                unique_values.append(item)
        return " | ".join(unique_values)

    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    for option in field.options:
        if raw_value == option:
            return option
    raise SiteMetadataValidationError(f"Select a valid {field.label.lower()} option.")
