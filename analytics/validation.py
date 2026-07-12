from __future__ import annotations
from datetime import date, datetime
from analytics.exceptions import ValidationError

def validate_positive_id(value: int, field_name: str) -> int:
    """Ensure a database identifier is a positive integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValidationError(f"{field_name} must be greater than zero.")

    return value

def validate_season(season: int) -> int:
    """Validate a baseball season."""
    if isinstance(season, bool) or not isinstance(season, int):
        raise ValidationError("season must be an integer.")

    if season < 1876 or season > 2100:
        raise ValidationError(
            f"season must be between 1876 and 2100. Received {season}."
        )

    return season

def validate_limit(limit: int, maximum: int = 5000) -> int:
    """Validate a result limit."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValidationError("limit must be an integer.")

    if limit < 1 or limit > maximum:
        raise ValidationError(
            f"limit must be between 1 and {maximum}."
        )

    return limit

def validate_date(
    value: date | datetime | str | None,
    field_name: str,
) -> date | None:
    """Convert a supported date value to a date object."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValidationError(
                f"{field_name} must use YYYY-MM-DD format."
            ) from exc

    raise ValidationError(
        f"{field_name} must be a date, datetime, ISO date string, or None."
    )

def validate_date_range(
    start_date: date | datetime | str | None,
    end_date: date | datetime | str | None,
) -> tuple[date | None, date | None]:
    """Validate an optional start and end date range."""
    parsed_start = validate_date(start_date, "start_date")
    parsed_end = validate_date(end_date, "end_date")

    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise ValidationError(
            "start_date cannot be later than end_date."
        )

    return parsed_start, parsed_end