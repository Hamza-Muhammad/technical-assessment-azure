"""
The PII boundary. Per part1-architecture.md section 10: only derived,
non-identifying values may reach the ML model or the LLM prompt. This
module is a whitelist, not a blacklist - callers build the model/LLM
input FROM these functions rather than filtering fields out of the raw
JobEvent/VendorProfile after the fact, so a new PII field added upstream
can't silently leak through by omission.
"""
from __future__ import annotations

from typing import Any


def redact_for_model(job: dict, vendor: dict, derived: dict) -> dict[str, Any]:
    """Feature vector for the ML model. No customerId, no address, no
    vendor tax/bank data, no vendor display name - numeric/categorical
    signal only."""
    perf = vendor["performance"]
    cap = vendor["capacity"]
    j = job["data"]["job"]
    risk = job["data"]["risk"]
    sla = job["data"]["sla"]
    return {
        "slaHitRate": perf["slaHitRate"],
        "firstTimeFixRate": perf["firstTimeFixRate"],
        "acceptanceRate": perf["acceptanceRate"],
        "reworkRate": perf["reworkRate"],
        "avgResponseMinutes": perf["avgResponseMinutes"],
        "csat": perf["csat"],
        "dataSufficiency": perf["dataSufficiency"],
        "utilizationPct": cap["utilizationPct"],
        "openJobs": cap["openJobs"],
        "priority": j["priority"],
        "estimatedLabourHours": j["estimatedLabourHours"],
        "notToExceedUsd": j["notToExceedUsd"],
        "isRecall": j["isRecall"],
        "riskTier": risk["riskTier"],
        "safetyRisk": risk["safetyRisk"],
        "slaSensitivity": sla["sensitivity"],
        "distanceKm": derived["distanceKm"],
        "isAfterHours": derived["isAfterHours"],
        "slaHoursRemaining": derived["slaHoursRemaining"],
        "certMatch": derived["certMatch"],
    }


def redact_for_llm(vendor_display_name: str, factors: list[dict], template: str) -> dict[str, Any]:
    """Whitelisted input to the narration LLM: the vendor's business name
    (not a personal identifier), the deterministic factor/evidence list,
    and the template sentence. No customer data, no free-text job
    description, ever."""
    return {
        "vendorDisplayName": vendor_display_name,
        "factors": [
            {"id": f["id"], "evidence": f["evidence"], "contributionPct": f["contributionPct"]}
            for f in factors
        ],
        "template": template,
    }
