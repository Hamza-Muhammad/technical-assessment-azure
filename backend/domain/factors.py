"""
Maps ML feature names to a stable factor id + a deterministic, data-driven
`evidence` string. The LLM (domain/rationale.py) never invents these -
it only ever rephrases evidence strings that were built here from the
same numbers that appear in ScoreFactors, which is what the groundedness
check verifies.

Only features with a human-legible story get a factor id. Features left
out (priority, notToExceedUsd, estimatedLabourHours, slaSensitivity,
certMatch) still feed the model but aren't surfaced as named factors -
their SHAP contribution is real but not narrated per-feature.
"""
from __future__ import annotations

from typing import Callable

RISK_LABELS = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
SUFFICIENCY_LABELS = {0: "COLD_START", 1: "SPARSE", 2: "SUFFICIENT"}


def _sla_history(raw: float, ctx: dict) -> str:
    return f"{raw * 100:.1f}% on-time across {ctx['jobsCompleted']} jobs in the last {ctx['windowDays']} days"


def _proximity(raw: float, ctx: dict) -> str:
    return f"{raw:.1f} km from job site"


def _first_time_fix(raw: float, ctx: dict) -> str:
    return f"{raw * 100:.1f}% first-time-fix rate over {ctx['jobsCompleted']} jobs"


def _current_load(raw: float, ctx: dict) -> str:
    return f"{raw * 100:.1f}% utilised, {ctx['openJobs']} open jobs"


def _rework_rate(raw: float, ctx: dict) -> str:
    return f"{raw * 100:.1f}% rework rate over the trailing {ctx['windowDays']} days"


def _csat(raw: float, ctx: dict) -> str:
    return f"{raw:.2f}/5.0 average customer rating"


def _response_time(raw: float, ctx: dict) -> str:
    return f"averages {raw:.0f} min to respond to a dispatch"


def _acceptance_rate(raw: float, ctx: dict) -> str:
    return f"{raw * 100:.1f}% historical job-acceptance rate"


def _sla_pressure(raw: float, ctx: dict) -> str:
    return f"{raw:.1f} hours remain until the SLA deadline"


def _after_hours(raw: float, ctx: dict) -> str:
    return "Requested window falls outside standard business hours" if raw else "Within standard business hours"


def _recall(raw: float, ctx: dict) -> str:
    return "This is a recall job" if raw else "Not a recall job"


def _data_sufficiency(raw, ctx: dict) -> str:
    return f"Vendor performance history classified {raw}"


FACTOR_DEFS: dict[str, dict[str, Callable | str]] = {
    "slaHitRate": {"id": "SLA_HISTORY", "evidence": _sla_history},
    "distanceKm": {"id": "PROXIMITY", "evidence": _proximity},
    "firstTimeFixRate": {"id": "FIRST_TIME_FIX", "evidence": _first_time_fix},
    "utilizationPct": {"id": "CURRENT_LOAD", "evidence": _current_load},
    "reworkRate": {"id": "REWORK_RATE", "evidence": _rework_rate},
    "csat": {"id": "CUSTOMER_SATISFACTION", "evidence": _csat},
    "avgResponseMinutes": {"id": "RESPONSE_TIME", "evidence": _response_time},
    "acceptanceRate": {"id": "ACCEPTANCE_RATE", "evidence": _acceptance_rate},
    "slaHoursRemaining": {"id": "SLA_TIME_PRESSURE", "evidence": _sla_pressure},
    "isAfterHours": {"id": "AFTER_HOURS", "evidence": _after_hours},
    "isRecall": {"id": "RECALL_JOB", "evidence": _recall},
    "dataSufficiency": {"id": "DATA_SUFFICIENCY", "evidence": _data_sufficiency},
}


def build_context(vendor: dict, derived: dict) -> dict:
    perf = vendor["performance"]
    return {
        "jobsCompleted": perf["jobsCompleted"],
        "windowDays": perf["windowDays"],
        "openJobs": vendor["capacity"]["openJobs"],
    }
