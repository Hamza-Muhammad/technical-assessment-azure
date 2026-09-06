"""Request-time derived features - computed fresh per scoring run, never
stored (part1-architecture.md section 5)."""
from __future__ import annotations

from datetime import datetime, timezone

# Rough fixed UTC offsets for the small set of timezones used in fixture
# data. A real system would use a proper tz database; this is a
# deliberate simplification for a take-home-scale demo.
_TZ_OFFSET_HOURS = {
    "America/Chicago": -6,
    "America/New_York": -5,
    "America/Los_Angeles": -8,
    "America/Denver": -7,
    "America/Phoenix": -7,
}


def _parse_utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def is_after_hours(occurred_at_utc: str, timezone_name: str) -> bool:
    dt = _parse_utc(occurred_at_utc)
    offset = _TZ_OFFSET_HOURS.get(timezone_name, 0)
    local_hour = (dt.hour + offset) % 24
    return local_hour < 7 or local_hour >= 18


def sla_hours_remaining(occurred_at_utc: str, resolution_due_utc: str) -> float:
    delta = _parse_utc(resolution_due_utc) - _parse_utc(occurred_at_utc)
    return round(delta.total_seconds() / 3600.0, 1)


def cert_match(job: dict, vendor: dict) -> bool:
    required = set(job["data"]["job"].get("requiresCertification", []))
    held = {c["code"] for c in vendor["compliance"].get("certifications", [])}
    return required.issubset(held)


def build_derived_features(job: dict, vendor: dict, distance_km: float) -> dict:
    site = job["data"]["site"]
    sla = job["data"]["sla"]
    occurred = job["occurredAtUtc"]
    return {
        "distanceKm": distance_km,
        "isAfterHours": is_after_hours(occurred, site["timezone"]),
        "slaHoursRemaining": sla_hours_remaining(occurred, sla["resolutionDueUtc"]),
        "certMatch": cert_match(job, vendor),
    }
