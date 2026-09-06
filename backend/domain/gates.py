"""
automationEligible / blockingGates[] - part1-architecture.md section 8.

Deliberately simplified for this demo build to exactly two checks (down
from Part 1's fuller 7-check design) - a job is auto-assignable only if
BOTH pass. This is the single clearest "AI output drives a real workflow
decision" moment in the repo: the Durable orchestrator's gate fork
(orchestrator/saga_bp.py) reads `automationEligible` straight off this
function's output.

The confidence threshold itself isn't duplicated here - `confidence_band`
is already computed against `config["confidenceBands"]["HIGH"]` in
domain/blend.py:confidence_band(); this function just compares the
resulting band label.
"""
from __future__ import annotations


def evaluate_gates(*, job: dict, confidence_band: str) -> tuple[bool, list[str]]:
    blocking: list[str] = []

    if job["data"]["risk"]["riskTier"] != "LOW":
        blocking.append("RISK_TIER_HIGH")
    if confidence_band != "HIGH":
        blocking.append("LOW_CONFIDENCE")

    return (len(blocking) == 0), blocking
