"""
Assembles the `factors[]` array for one ranked vendor, from either the
ML SHAP output (RULES_PLUS_ML) or the rule-score components themselves
(RULES_ONLY / ML fallback) - the ML-fallback scenario must still produce
a fully populated, explained ScoreFactors document, never an empty one.

`contributionPct` for every factor in the returned list is normalized so
the percentages are comparable to each other (100 * |value| share),
regardless of which stage a factor's value originally came from.
"""
from __future__ import annotations

from domain.factors import FACTOR_DEFS, build_context

# TreeSHAP values from the model are in log-odds (margin) space, typically
# a fraction of a point. Scaled purely for display alongside rule-guardrail
# point adjustments (which are already on a 0-100 scale) - this scaling
# affects only the `shap`/contributionPct display fields, never mlScore,
# the blend, or the ranking.
SHAP_DISPLAY_SCALE = 20.0

AFTER_HOURS_RULE_ID = "R-GUARD-011"


def _normalize(items: list[tuple[float, dict]]) -> list[dict]:
    total_abs = sum(abs(v) for v, _ in items) or 1.0
    factors = []
    for value, factor in items:
        factor = dict(factor)
        factor["contributionPct"] = round(100.0 * value / total_abs, 1)
        factors.append(factor)
    return sorted(factors, key=lambda f: -abs(f["contributionPct"]))


def _after_hours_guardrail(is_after_hours: bool, config: dict) -> tuple[float, dict] | None:
    if not is_after_hours:
        return None
    points = config["afterHoursGuardrailPct"]
    return points, {
        "id": "AFTER_HOURS",
        "source": "RULE",
        "ruleId": AFTER_HOURS_RULE_ID,
        "raw": None,
        "evidence": "Requested window is outside standard hours",
    }


def build_ml_factors(shap_by_feature: dict[str, float], features: dict, vendor: dict, config: dict, top_k: int = 5) -> list[dict]:
    ctx = build_context(vendor, features)
    candidates = []
    for name, shap_val in shap_by_feature.items():
        if name not in FACTOR_DEFS:
            continue
        scaled = shap_val * SHAP_DISPLAY_SCALE
        factor_def = FACTOR_DEFS[name]
        raw_value = features[name]
        evidence = factor_def["evidence"](raw_value, ctx)
        candidates.append((scaled, {
            "id": factor_def["id"],
            "source": "ML",
            "shap": round(scaled, 2),
            "raw": raw_value if isinstance(raw_value, (int, float)) else None,
            "evidence": evidence,
        }))

    candidates.sort(key=lambda item: -abs(item[0]))
    items = candidates[:top_k]

    guardrail = _after_hours_guardrail(features.get("isAfterHours", False), config)
    if guardrail:
        items.append(guardrail)

    return _normalize(items)


def build_rule_only_factors(job: dict, vendor: dict, distance_km: float, is_after_hours: bool, config: dict) -> list[dict]:
    w = config["ruleWeights"]
    perf = vendor["performance"]
    ctx = build_context(vendor, {})

    from domain.rule_score import _clamp01

    proximity_score = _clamp01(1.0 - distance_km / config["proximityMaxKm"])
    cost_score = _clamp01(2.0 - perf["costIndex"])
    capacity_score = _clamp01(1.0 - vendor["capacity"]["utilizationPct"])
    tier_bonus = config["tierBonusPoints"].get(vendor["tier"], 0) / 10.0

    items = [
        (w["slaHitRate"] * perf["slaHitRate"], {
            "id": "SLA_HISTORY", "source": "RULE", "raw": perf["slaHitRate"],
            "evidence": FACTOR_DEFS["slaHitRate"]["evidence"](perf["slaHitRate"], ctx),
        }),
        (w["proximity"] * proximity_score, {
            "id": "PROXIMITY", "source": "RULE", "raw": distance_km,
            "evidence": FACTOR_DEFS["distanceKm"]["evidence"](distance_km, ctx),
        }),
        (w["firstTimeFix"] * perf["firstTimeFixRate"], {
            "id": "FIRST_TIME_FIX", "source": "RULE", "raw": perf["firstTimeFixRate"],
            "evidence": FACTOR_DEFS["firstTimeFixRate"]["evidence"](perf["firstTimeFixRate"], ctx),
        }),
        (w["costIndex"] * cost_score, {
            "id": "COST_INDEX", "source": "RULE", "raw": perf["costIndex"],
            "evidence": f"cost index {perf['costIndex']:.2f} (1.00 = network average)",
        }),
        (w["availableCapacity"] * capacity_score, {
            "id": "CURRENT_LOAD", "source": "RULE", "raw": vendor["capacity"]["utilizationPct"],
            "evidence": FACTOR_DEFS["utilizationPct"]["evidence"](vendor["capacity"]["utilizationPct"], ctx),
        }),
        (w["tierBonus"] * tier_bonus, {
            "id": "VENDOR_TIER", "source": "RULE", "raw": None,
            "evidence": f"vendor tier: {vendor['tier']}",
        }),
    ]
    guardrail = _after_hours_guardrail(is_after_hours, config)
    if guardrail:
        items.append(guardrail)
    return _normalize(items)
