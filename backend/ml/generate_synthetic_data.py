"""
Generates synthetic scoring-run + outcome logs with a deliberately
planted signal, so a model trained on them produces SHAP attributions
that tell a sensible story (SLA history, proximity, and rework rate
should dominate; unrelated fields should not).

Writes two independent logs, mirroring what real production would
already have flowing:
  logs/scoring_runs.jsonl  - one row per (job, vendor) candidate scored,
                             with the exact feature vector at scoring time
  logs/events.jsonl        - simulated job.completed.v1 outcome events

ml/build_training_set.py then joins these back together - it never sees
the ground-truth probability function used here, exactly like a real
retraining pipeline only ever sees logged features + logged outcomes.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from domain.ml_uplift import CATEGORICAL_MAPS  # noqa: E402

# Bootstrap/training data lives under ml/synthetic_logs, kept separate from
# logs/ (which is reserved for genuine demo-run audit output) so the two
# concerns - "data used to train the model" vs. "what the running app did"
# - are never visually mixed together.
LOGS_DIR = Path(__file__).resolve().parent / "synthetic_logs"

RISK_TIERS = CATEGORICAL_MAPS["riskTier"]
PRIORITIES = CATEGORICAL_MAPS["priority"]
SENSITIVITIES = CATEGORICAL_MAPS["slaSensitivity"]
SUFFICIENCIES = CATEGORICAL_MAPS["dataSufficiency"]


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _random_features(rng: random.Random) -> dict:
    sufficiency = rng.choices(SUFFICIENCIES, weights=[0.08, 0.22, 0.70])[0]
    return {
        "slaHitRate": rng.betavariate(9, 2),
        "firstTimeFixRate": rng.betavariate(8, 2),
        "acceptanceRate": rng.betavariate(7, 2),
        "reworkRate": rng.betavariate(2, 20),
        "avgResponseMinutes": rng.uniform(20, 220),
        "csat": rng.uniform(3.2, 5.0),
        "dataSufficiency": sufficiency,
        "utilizationPct": rng.uniform(0.1, 0.98),
        "openJobs": rng.randint(0, 25),
        "priority": rng.choices(PRIORITIES, weights=[0.25, 0.45, 0.30])[0],
        "estimatedLabourHours": rng.uniform(1, 8),
        "notToExceedUsd": rng.uniform(400, 9000),
        "isRecall": rng.random() < 0.08,
        "riskTier": rng.choices(RISK_TIERS, weights=[0.55, 0.30, 0.15])[0],
        "safetyRisk": rng.random() < 0.06,
        "slaSensitivity": rng.choices(SENSITIVITIES, weights=[0.5, 0.3, 0.2])[0],
        "distanceKm": rng.uniform(1, 90),
        "isAfterHours": rng.random() < 0.2,
        "slaHoursRemaining": rng.uniform(2, 48),
        "certMatch": True,
    }


def _planted_success_probability(f: dict) -> float:
    """Ground truth the demo model is asked to recover. Deliberately
    dominated by slaHitRate, reworkRate, distanceKm, firstTimeFixRate,
    utilizationPct - the factors the README/README table calls out as
    the expected top SHAP drivers."""
    suff_bonus = {"COLD_START": -0.6, "SPARSE": -0.2, "SUFFICIENT": 0.15}[f["dataSufficiency"]]
    z = (
        4.2 * (f["slaHitRate"] - 0.85)
        + 3.0 * (f["firstTimeFixRate"] - 0.85)
        - 6.0 * f["reworkRate"]
        - 0.022 * (f["distanceKm"] - 30)
        - 1.4 * (f["utilizationPct"] - 0.5)
        + 0.35 * (f["csat"] - 4.2)
        - 0.006 * (f["avgResponseMinutes"] - 100)
        + suff_bonus
        - (0.5 if f["isRecall"] else 0.0)
        - (0.3 if f["riskTier"] == "HIGH" else 0.0)
    )
    return _sigmoid(z)


def generate(n_rows: int, seed: int) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    scoring_runs, outcome_events = [], []
    base_time = datetime(2026, 3, 1, tzinfo=timezone.utc)

    for i in range(n_rows):
        job_id = f"JOB-SYN-{i:06d}"
        vendor_id = f"VEN-SYN-{rng.randint(0, 400):04d}"
        scoring_run_id = f"SCR-{uuid.uuid4().hex[:17].upper()}"
        generated_at = base_time + timedelta(minutes=i * 7)

        features = _random_features(rng)
        p_success = _planted_success_probability(features)

        sla_met = rng.random() < p_success
        first_time_fix = rng.random() < (p_success * 0.95 + 0.02)
        accepted_within_15m = rng.random() < features["acceptanceRate"]
        actual_cost = round(features["notToExceedUsd"] * rng.uniform(0.4, 0.95), 2)

        scoring_runs.append({
            "scoringRunId": scoring_run_id,
            "jobId": job_id,
            "vendorId": vendor_id,
            "generatedAtUtc": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "features": features,
        })
        outcome_events.append({
            "type": "job.completed.v1",
            "jobId": job_id,
            "correlationId": str(uuid.uuid4()),
            "occurredAtUtc": (generated_at + timedelta(hours=rng.uniform(1, 30))).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {
                "vendorId": vendor_id,
                "scoringRunId": scoring_run_id,
                "slaMet": sla_met,
                "firstTimeFix": first_time_fix,
                "acceptedWithin15m": accepted_within_15m,
                "actualCostUsd": actual_cost,
            },
        })

    return scoring_runs, outcome_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=6000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    LOGS_DIR.mkdir(exist_ok=True)
    scoring_runs, outcome_events = generate(args.rows, args.seed)

    with open(LOGS_DIR / "scoring_runs.jsonl", "a", encoding="utf-8") as f:
        for row in scoring_runs:
            f.write(json.dumps(row) + "\n")

    with open(LOGS_DIR / "events.jsonl", "a", encoding="utf-8") as f:
        for row in outcome_events:
            f.write(json.dumps(row) + "\n")

    print(f"Appended {len(scoring_runs)} synthetic scoring runs and outcome events to {LOGS_DIR}")


if __name__ == "__main__":
    main()
