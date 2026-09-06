from __future__ import annotations

import argparse
import json
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
# Default source is the synthetic bootstrap log (see generate_synthetic_data.py).
# Point --logs-dir at the real logs/ directory to build a training set from
# genuine accumulated job outcomes instead - same script, real feedback loop.
SYNTHETIC_LOGS_DIR = Path(__file__).resolve().parent / "synthetic_logs"
DATA_DIR = Path(__file__).resolve().parent / "data"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_training_set(logs_dir: Path = SYNTHETIC_LOGS_DIR) -> list[dict]:
    scoring_runs = _read_jsonl(logs_dir / "scoring_runs.jsonl")
    events = _read_jsonl(logs_dir / "events.jsonl")

    # Index scoring runs by (jobId, vendorId) - one scoring run logs the
    # feature vector for every candidate vendor considered, keyed the
    # same way the outcome event references it back.
    runs_by_key: dict[tuple[str, str], dict] = {}
    for run in scoring_runs:
        runs_by_key[(run["jobId"], run["vendorId"])] = run

    rows: list[dict] = []
    for event in events:
        if event.get("type") != "job.completed.v1":
            continue
        outcome = event["data"]
        key = (event["jobId"], outcome["vendorId"])
        run = runs_by_key.get(key)
        if run is None:
            continue  # outcome with no matching logged scoring run - can't label, skip

        label = bool(outcome["slaMet"]) and bool(outcome["firstTimeFix"])
        rows.append({
            "jobId": event["jobId"],
            "vendorId": outcome["vendorId"],
            "scoringRunId": run["scoringRunId"],
            "generatedAtUtc": run["generatedAtUtc"],
            "features": run["features"],
            "label": int(label),
            "slaMet": outcome["slaMet"],
            "firstTimeFix": outcome["firstTimeFix"],
            "acceptedWithin15m": outcome["acceptedWithin15m"],
            "actualCostUsd": outcome["actualCostUsd"],
        })

    rows.sort(key=lambda r: r["generatedAtUtc"])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=Path, default=SYNTHETIC_LOGS_DIR)
    parser.add_argument("--out", type=Path, default=DATA_DIR / "training_set.jsonl")
    args = parser.parse_args()

    rows = build_training_set(args.logs_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    matched = len(rows)
    unmatched_events = len(_read_jsonl(args.logs_dir / "events.jsonl")) - matched
    print(f"Wrote {matched} labeled training rows to {args.out}")
    if unmatched_events > 0:
        print(f"{unmatched_events} completed-job events had no matching logged scoring run and were skipped")


if __name__ == "__main__":
    main()
