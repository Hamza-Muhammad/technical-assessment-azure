"""
Stage 1 - hard eligibility filter. Boolean, no ML. Pure function over
plain dicts (JobEvent-shaped, VendorProfile-shaped) so it's testable
without any framework or I/O.

trade match AND certifications AND equipment AND in service area AND
compliant AND active AND accepting work AND not customer-excluded AND
not on probation -> candidate set.

Each vendor is excluded for exactly one reason (first match wins, in the
order below) so `candidateSummary.exclusions` counts are a clean partition,
matching the example in part1-architecture.md's ScoreFactors.
"""
from __future__ import annotations

from domain.geo import haversine_km


def _check(job: dict, vendor: dict) -> str | None:
    """Return the exclusion reason code, or None if the vendor is eligible."""
    j = job["data"]
    if vendor["vendorId"] in j["dispatch"].get("excludedVendorIds", []):
        return "CUSTOMER_EXCLUDED"
    if vendor["status"] != "ACTIVE":
        return "NOT_ACTIVE"
    if not vendor["compliance"]["isCompliant"]:
        return "NOT_COMPLIANT"
    if vendor.get("onProbation"):
        return "ON_PROBATION"

    trade = j["job"]["tradeCategory"]
    caps = vendor["capabilities"]
    if trade not in caps["tradeCategories"]:
        return "TRADE_MISMATCH"

    required_certs = set(j["job"].get("requiresCertification", []))
    held_certs = {c["code"] for c in vendor["compliance"].get("certifications", [])}
    if not required_certs.issubset(held_certs):
        return "CERT_MISSING"

    required_equipment = set(j["job"].get("requiresEquipment", []))
    held_equipment = set(caps.get("equipment", []))
    if not required_equipment.issubset(held_equipment):
        return "EQUIPMENT_MISSING"

    site_geo = j["site"]["geo"]
    home_geo = vendor["coverage"]["homeBaseGeo"]
    distance_km = haversine_km(site_geo["lat"], site_geo["lon"], home_geo["lat"], home_geo["lon"])
    if distance_km > vendor["coverage"]["maxTravelKm"]:
        return "OUT_OF_AREA"

    cap = vendor["capacity"]
    if not cap["acceptingNewWork"] or cap["openJobs"] >= caps["maxConcurrentJobs"]:
        return "CAPACITY_FULL"

    return None


def filter_eligible(job: dict, vendors: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Returns (eligible vendors, exclusions dict keyed by reason code)."""
    eligible: list[dict] = []
    exclusions: dict[str, int] = {}
    for vendor in vendors:
        reason = _check(job, vendor)
        if reason is None:
            eligible.append(vendor)
        else:
            exclusions[reason] = exclusions.get(reason, 0) + 1
    return eligible, exclusions
