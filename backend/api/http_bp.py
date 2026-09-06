
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import azure.durable_functions as df
import azure.functions as func
from pydantic import ValidationError

import audit
import store
from contracts.models import JobEventData
from events.factory import get_bus
from events.handlers import publish_job_assigned, publish_job_completed, publish_job_created

bp = df.Blueprint()

BACKEND_DIR = Path(__file__).resolve().parent.parent
CONFIG = json.loads((BACKEND_DIR / "config" / "scoring_config.json").read_text())
VENDORS = json.loads((BACKEND_DIR / "data" / "vendors.json").read_text())


_bus = None


def _get_bus():
    global _bus
    if _bus is None:
        _bus = get_bus()
    return _bus


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_response(payload, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(payload, default=str), status_code=status_code, mimetype="application/json")


def _error_response(status_code: int, detail: str) -> func.HttpResponse:
    return _json_response({"detail": detail}, status_code)


def _status_of(job_id: str) -> str:
    assignment = store.get_assignment(job_id)
    if assignment is not None:
        return "AUTO_ASSIGNED" if assignment["assignmentSource"] == "AUTO" else "ASSIGNED"
    factors = store.get_score_factors(job_id)
    if factors is None:
        return "UNSCORED"
    return "PENDING_REVIEW" if factors["ranked"] else "NO_ELIGIBLE_VENDORS"


@bp.route(route="jobs", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def create_job(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_json()
    try:
        job_data = JobEventData(**body["data"]).model_dump()
    except (KeyError, ValidationError) as exc:
        return _error_response(422, str(exc))

    job_id = body.get("jobId") or f"JOB-{uuid.uuid4().hex[:10].upper()}"
    correlation_id = body.get("correlationId") or str(uuid.uuid4())
    job_event = {
        "type": "job.created.v1",
        "jobId": job_id,
        "correlationId": correlation_id,
        "occurredAtUtc": body.get("occurredAtUtc") or _now_iso(),
        "data": job_data,
    }
    store.put_job(job_id, job_event)
    publish_job_created(_get_bus(), job_event)

    return _json_response({"jobId": job_id, "correlationId": correlation_id, "status": "UNSCORED", "scoringRunId": None}, 201)


@bp.route(route="jobs", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def list_jobs(req: func.HttpRequest) -> func.HttpResponse:
    jobs = store.list_jobs()
    result = [
        {"jobId": j["jobId"], **{k: v for k, v in j.items() if k != "data"}, "status": _status_of(j["jobId"])}
        for j in jobs
    ]
    return _json_response(result)


@bp.route(route="jobs/{jobId}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_job(req: func.HttpRequest) -> func.HttpResponse:
    job_id = req.route_params["jobId"]
    job = store.get_job(job_id)
    if job is None:
        return _error_response(404, f"unknown jobId {job_id}")
    return _json_response(job)


@bp.route(route="jobs/{jobId}/recommendation", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_recommendation(req: func.HttpRequest) -> func.HttpResponse:
    job_id = req.route_params["jobId"]
    factors = store.get_score_factors(job_id)
    if factors is None:
        return _error_response(404, f"no scoring run yet for jobId {job_id}")
    return _json_response(factors)


@bp.route(route="jobs/{jobId}/assignment", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@bp.durable_client_input(client_name="client")
async def create_assignment(req: func.HttpRequest, client) -> func.HttpResponse:
    job_id = req.route_params["jobId"]
    body = req.get_json()
    job = store.get_job(job_id)
    factors = store.get_score_factors(job_id)
    if job is None or factors is None:
        return _error_response(404, f"unknown jobId {job_id}")

    selected_vendor_id = body.get("selectedVendorId")
    if not selected_vendor_id:
        return _error_response(422, "selectedVendorId is required")
    override_reason_code = body.get("overrideReasonCode")
    note = body.get("note")

    recommended_vendor_id = factors["ranked"][0]["vendorId"] if factors["ranked"] else None
    is_override = selected_vendor_id != recommended_vendor_id or override_reason_code is not None
    if is_override and override_reason_code is None:
        return _error_response(422, "overrideReasonCode is required when selecting a vendor other than the top recommendation")

    assignment = {
        "jobId": job_id,
        "correlationId": job["correlationId"],
        "selectedVendorId": selected_vendor_id,
        "overrideReasonCode": override_reason_code,
        "note": note,
        "assignmentSource": "DISPATCHER_OVERRIDE" if is_override else "DISPATCHER_ACCEPT",
        "assignedAtUtc": _now_iso(),
    }
    store.put_assignment(job_id, assignment)
    publish_job_assigned(_get_bus(), job_id, job["correlationId"], assignment)
    audit.log_decision(jobId=job_id, correlationId=job["correlationId"], scoringRunId=factors["scoringRunId"], decision=assignment)

    try:
    
        await client.raise_event(job_id, "DispatcherDecision", {
            "selectedVendorId": selected_vendor_id, "overrideReasonCode": override_reason_code, "note": note,
        })
    except Exception:
        pass

    return _json_response(assignment)


@bp.route(route="jobs/{jobId}/completion", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def complete_job(req: func.HttpRequest) -> func.HttpResponse:
    job_id = req.route_params["jobId"]
    job = store.get_job(job_id)
    if job is None:
        return _error_response(404, f"unknown jobId {job_id}")
    outcome = req.get_json()
    publish_job_completed(_get_bus(), job_id, job["correlationId"], outcome)
    return _json_response({"jobId": job_id, "recorded": True})


@bp.route(route="jobs/{jobId}/audit", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_audit(req: func.HttpRequest) -> func.HttpResponse:
    job_id = req.route_params["jobId"]
    job = store.get_job(job_id)
    if job is None:
        return _error_response(404, f"unknown jobId {job_id}")
    return _json_response({
        "jobId": job_id,
        "job": job,
        "scoreFactors": store.get_score_factors(job_id),
        "assignment": store.get_assignment(job_id),
        "events": store.read_audit("events", job_id),
        "decisions": store.read_audit("decisions", job_id),
    })


@bp.route(route="vendors", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def list_vendors(req: func.HttpRequest) -> func.HttpResponse:
    return _json_response(VENDORS)


@bp.route(route="jobs/{jobId}/replay", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def replay_job(req: func.HttpRequest) -> func.HttpResponse:
    """Re-publishes JobCreated for an already-known job, so its event-bus
    behavior can be exercised on demand without recreating the job."""
    job_id = req.route_params["jobId"]
    job_event = store.get_job(job_id)
    if job_event is None:
        return _error_response(404, f"unknown jobId {job_id}")
    publish_job_created(_get_bus(), job_event)
    return _json_response({"jobId": job_id, "status": "UNSCORED", "scoringRunId": None})


@bp.route(route="admin/seed", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def seed_fixture_jobs(req: func.HttpRequest) -> func.HttpResponse:
  
    jobs = json.loads((BACKEND_DIR / "data" / "jobs.json").read_text())
    seeded = []
    for job_event in jobs:
        job_id = job_event["jobId"]
        store.put_job(job_id, job_event)
        publish_job_created(_get_bus(), job_event)
        seeded.append({"jobId": job_id, "dispatched": True})
    return _json_response({"seeded": seeded})


@bp.route(route="jobs/{jobId}/dispatch", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def dispatch_job_to_saga(req: func.HttpRequest) -> func.HttpResponse:
    
    job_id = req.route_params["jobId"]
    job_event = store.get_job(job_id)
    if job_event is None:
        return _error_response(404, f"unknown jobId {job_id}")
    publish_job_created(_get_bus(), job_event)
    return _json_response({"jobId": job_id, "dispatched": True})


@bp.route(route="jobs/{jobId}/orchestration", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
@bp.durable_client_input(client_name="client")
async def get_orchestration_status(req: func.HttpRequest, client) -> func.HttpResponse:
    job_id = req.route_params["jobId"]
    status = await client.get_status(job_id)
    if status is None or status.runtime_status is None:
        return _error_response(404, f"no orchestration instance for jobId {job_id}")
    return _json_response({
        "jobId": job_id,
        "runtimeStatus": status.runtime_status.name,
        "customStatus": status.custom_status,
        "createdTime": status.created_time.isoformat() if status.created_time else None,
        "lastUpdatedTime": status.last_updated_time.isoformat() if status.last_updated_time else None,
        "output": status.output,
    })
