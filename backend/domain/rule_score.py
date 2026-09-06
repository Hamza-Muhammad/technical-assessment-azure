"""
Stage 2 - deterministic rule score (0-100), versioned weights in config.
Per part1-architecture.md section 6:

    0.30*slaHitRate + 0.20*proximity + 0.15*firstTimeFix
  + 0.15*costIndex + 0.10*availableCapacity + 0.10*tierBonus

Every input sub-score is normalized to [0, 1] before weighting so the
weights in config sum to 1.0 and the result is a clean 0-100 scale.
"""
from __future__ import annotations

from domain.geo import haversine_km


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def distance_km(job: dict, vendor: dict) -> float:
    site_geo = job["data"]["site"]["geo"]
    home_geo = vendor["coverage"]["homeBaseGeo"]
    return haversine_km(site_geo["lat"], site_geo["lon"], home_geo["lat"], home_geo["lon"])


def rule_score(job: dict, vendor: dict, config: dict) -> tuple[float, float]:
    """Returns (ruleScore 0-100, distanceKm) - distanceKm is returned so
    callers don't recompute it for the ML feature vector / evidence strings."""
    w = config["ruleWeights"]
    perf = vendor["performance"]
    d_km = distance_km(job, vendor)

    proximity_score = _clamp01(1.0 - d_km / config["proximityMaxKm"])
    # costIndex ~1.0 is the network-average cost; below 1.0 is cheaper-than-average.
    cost_score = _clamp01(2.0 - perf["costIndex"])
    capacity_score = _clamp01(1.0 - vendor["capacity"]["utilizationPct"])
    tier_bonus = config["tierBonusPoints"].get(vendor["tier"], 0) / 10.0

    score = 100.0 * (
        w["slaHitRate"] * perf["slaHitRate"]
        + w["proximity"] * proximity_score
        + w["firstTimeFix"] * perf["firstTimeFixRate"]
        + w["costIndex"] * cost_score
        + w["availableCapacity"] * capacity_score
        + w["tierBonus"] * tier_bonus
    )
    return round(score, 2), round(d_km, 1)
