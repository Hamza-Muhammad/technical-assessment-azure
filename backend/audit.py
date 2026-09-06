
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

LOGS_DIR = Path(__file__).resolve().parent / "logs"
_write_lock = Lock()
_app_insights_logger = logging.getLogger("retailfixit.audit")

STATE_STORE_IMPL = os.environ.get("STATE_STORE_IMPL", "blob")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _append(stream: str, record: dict) -> None:
    _app_insights_logger.info(stream, extra={"custom_dimensions": record})

    if STATE_STORE_IMPL == "blob":
        import store
        store.append_audit(stream, record)
        return

    LOGS_DIR.mkdir(exist_ok=True)
    line = json.dumps(record, default=str)
    with _write_lock:
        with open(LOGS_DIR / f"{stream}.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")


def log_scoring_run(score_factors: dict, correlation_id: str) -> None:
    _append("scoring_runs", {
        "loggedAtUtc": _now_iso(),
        "correlationId": correlation_id,
        "jobId": score_factors["jobId"],
        "scoringRunId": score_factors["scoringRunId"],
        "scoreFactors": score_factors,
    })


def log_event(event: dict) -> None:
    _append("events", {
        "loggedAtUtc": _now_iso(),
        "correlationId": event.get("correlationId"),
        "jobId": event.get("jobId"),
        "scoringRunId": event.get("data", {}).get("scoringRunId"),
        "event": event,
    })


def log_decision(*, jobId: str, correlationId: str, scoringRunId: str | None, decision: dict) -> None:
    _append("decisions", {
        "loggedAtUtc": _now_iso(),
        "correlationId": correlationId,
        "jobId": jobId,
        "scoringRunId": scoringRunId,
        "decision": decision,
    })
