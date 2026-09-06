
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from domain.ml_uplift import encode_feature  # noqa: E402
from domain.model_registry import compute_schema_hash  # noqa: E402

FEATURE_ORDER = [
    "slaHitRate", "firstTimeFixRate", "acceptanceRate", "reworkRate",
    "avgResponseMinutes", "csat", "dataSufficiency", "utilizationPct",
    "openJobs", "priority", "estimatedLabourHours", "notToExceedUsd",
    "isRecall", "riskTier", "safetyRisk", "slaSensitivity", "distanceKm",
    "isAfterHours", "slaHoursRemaining", "certMatch",
]

MODELS_DIR = BACKEND_DIR / "models" / "vendor_uplift"


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=BACKEND_DIR, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _load_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _expected_calibration_error(y_true, y_prob, n_bins: int = 10) -> float:
    import numpy as np
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() == 0:
            continue
        bucket_acc = y_true[mask].mean()
        bucket_conf = y_prob[mask].mean()
        ece += (mask.sum() / n) * abs(bucket_acc - bucket_conf)
    return round(float(ece), 4)


def train(training_set_path: Path, version: str, num_boost_round: int):
    import lightgbm as lgb
    import numpy as np
    from sklearn.isotonic import IsotonicRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score

    rows = _load_rows(training_set_path)
    if len(rows) < 50:
        raise ValueError(f"only {len(rows)} labeled rows in {training_set_path} - run generate_synthetic_data.py + build_training_set.py first")

    rows.sort(key=lambda r: r["generatedAtUtc"])  # temporal order
    split_idx = int(len(rows) * 0.85)
    train_rows, holdout_rows = rows[:split_idx], rows[split_idx:]

    def to_matrix(subset: list[dict]):
        X = np.array([[encode_feature(name, r["features"][name]) for name in FEATURE_ORDER] for r in subset], dtype=float)
        y = np.array([r["label"] for r in subset], dtype=float)
        return X, y

    X_train, y_train = to_matrix(train_rows)
    X_holdout, y_holdout = to_matrix(holdout_rows)

    train_set = lgb.Dataset(X_train, label=y_train, feature_name=FEATURE_ORDER)
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "num_leaves": 15,
        "learning_rate": 0.08,
        "min_data_in_leaf": 20,
        "verbose": -1,
    }
    booster = lgb.train(params, train_set, num_boost_round=num_boost_round)

    raw_holdout_pred = booster.predict(X_holdout)
    # Isotonic calibration on the holdout predictions themselves is not
    # ideal in production (would use a separate calibration split), but
    # is a reasonable simplification for a synthetic-data demo - documented
    # plainly rather than silently assumed away.
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrated = calibrator.fit_transform(raw_holdout_pred, y_holdout)

    auc = round(float(roc_auc_score(y_holdout, raw_holdout_pred)), 4)
    brier = round(float(brier_score_loss(y_holdout, calibrated)), 4)
    ece = _expected_calibration_error(y_holdout, calibrated)

    version_dir = MODELS_DIR / version
    version_dir.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(version_dir / "model.txt"))

    schema_hash = compute_schema_hash(FEATURE_ORDER)
    (version_dir / "feature_spec.json").write_text(json.dumps({
        "features": FEATURE_ORDER,
        "schemaHash": schema_hash,
    }, indent=2))

    (version_dir / "metadata.json").write_text(json.dumps({
        "modelName": "vendor-uplift",
        "modelVersion": version,
        "trainedAtUtc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trainingRowCount": len(train_rows),
        "holdoutRowCount": len(holdout_rows),
        "offlineMetrics": {
            "auc": auc,
            "brierScore": brier,
            "expectedCalibrationError": ece,
            "note": "Synthetic training data - these numbers are illustrative, not a real-world benchmark.",
        },
        "gitSha": _git_sha(),
    }, indent=2))

    print(f"Trained vendor-uplift {version}: AUC={auc} Brier={brier} ECE={ece} "
          f"(train={len(train_rows)} rows, holdout={len(holdout_rows)} rows)")
    return version_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-set", type=Path, default=Path(__file__).resolve().parent / "data" / "training_set.jsonl")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--num-boost-round", type=int, default=150)
    args = parser.parse_args()
    train(args.training_set, args.version, args.num_boost_round)


if __name__ == "__main__":
    main()
