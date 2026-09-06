
from __future__ import annotations

SUFFICIENCY_WEIGHT = {"COLD_START": 0.0, "SPARSE": 0.5, "SUFFICIENT": 1.0}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def blend_scores(rule_score: float, ml_score: float | None, ml_trust_factor: float, config: dict) -> tuple[float, float]:
    """Returns (finalScore, blendWeight w actually applied)."""
    cap = config["blendWeightCap"]
    w = cap * ml_trust_factor if ml_score is not None else 0.0
    final = (1 - w) * rule_score + w * (ml_score or 0.0)
    return round(final, 2), round(w, 4)


def percentile_rank(value: float, population: list[float]) -> float:
    """Fraction of `population` at or below `value` - used to compare rule
    score and ML score on *relative standing within this job's candidate
    pool* rather than raw magnitude, since the two scores are computed on
    different scales (a weighted formula vs. a calibrated probability) and
    a systematic scale gap between them would otherwise look like
    disagreement even when both methods rank the vendor the same way."""
    if not population:
        return 0.5
    return sum(1 for v in population if v <= value) / len(population)


def compute_confidence(
    rule_score: float,
    ml_score: float | None,
    scoring_mode: str,
    data_sufficiency: str,
    ml_trust_factor: float,
    rule_score_population: list[float] | None = None,
    ml_score_population: list[float] | None = None,
) -> float:
    sufficiency_component = SUFFICIENCY_WEIGHT.get(data_sufficiency, 0.0)
    if scoring_mode == "RULES_PLUS_ML" and ml_score is not None and rule_score_population and ml_score_population:
        rule_pct = percentile_rank(rule_score, rule_score_population)
        ml_pct = percentile_rank(ml_score, ml_score_population)
        agreement = 1.0 - abs(rule_pct - ml_pct)
    else:
        agreement = 0.6  # neutral - no second opinion to agree or disagree with
    confidence = 0.35 * sufficiency_component + 0.35 * agreement + 0.30 * ml_trust_factor
    return round(_clamp01(confidence), 3)


def confidence_band(confidence: float, config: dict) -> str:
    bands = config["confidenceBands"]
    if confidence >= bands["HIGH"]:
        return "HIGH"
    if confidence >= bands["MEDIUM"]:
        return "MEDIUM"
    return "LOW"
