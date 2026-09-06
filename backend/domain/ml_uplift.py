"""
Stage 3 - ML uplift. Calls the registered LightGBM classifier
(P(success) = P(slaMet AND firstTimeFix)) and computes TreeSHAP
attributions. This module never decides whether to trust its own
output - that's the blend stage's job (mlTrustFactor).
"""
from __future__ import annotations

from domain.model_registry import LoadedModel

CATEGORICAL_MAPS: dict[str, list[str]] = {
    "dataSufficiency": ["COLD_START", "SPARSE", "SUFFICIENT"],
    "priority": ["P1", "P2", "P3"],
    "riskTier": ["LOW", "MEDIUM", "HIGH"],
    "slaSensitivity": ["ROUTINE", "ELEVATED", "CRITICAL"],
}


def encode_feature(name: str, value) -> float:
    if name in CATEGORICAL_MAPS:
        options = CATEGORICAL_MAPS[name]
        return float(options.index(value)) if value in options else -1.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)


def build_row(features: dict, feature_order: list[str]) -> list[float]:
    return [encode_feature(name, features[name]) for name in feature_order]


_explainer_cache: dict[str, "shap.TreeExplainer"] = {}


def _explainer_for(model: LoadedModel):
    import shap

    cached = _explainer_cache.get(model.version)
    if cached is None:
        cached = shap.TreeExplainer(model.booster)
        _explainer_cache[model.version] = cached
    return cached


def score_vendor(features: dict, model: LoadedModel) -> tuple[float, dict[str, float]]:
    """Returns (mlScore 0-100, {featureName: shapValue}) for one candidate.
    The TreeExplainer is built once per model version and reused - it's
    the expensive part of this call by far, and candidates for the same
    job all share one model."""
    import numpy as np

    feature_order = model.feature_spec["features"]
    row = build_row(features, feature_order)
    x = np.array([row], dtype=float)

    proba = float(model.booster.predict(x)[0])
    ml_score = round(proba * 100.0, 2)

    explainer = _explainer_for(model)
    raw_shap = explainer.shap_values(x)
    # shap_values on a raw Booster with binary objective returns margin-space
    # (log-odds) contributions for the single positive class as a (1, n) array.
    if isinstance(raw_shap, list):
        raw_shap = raw_shap[-1]
    shap_row = raw_shap[0]

    shap_by_feature = {name: float(val) for name, val in zip(feature_order, shap_row)}
    return ml_score, shap_by_feature
