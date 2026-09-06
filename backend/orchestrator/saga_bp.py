
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import azure.durable_functions as df
import azure.functions as func

import audit
import store
from domain.scoring_pipeline import score_job
from events.factory import get_bus
from events.handlers import build_envelope
from events.topology import JOB_ASSIGNED, TOPIC, VENDOR_SCORING_REQUESTED

bp = df.Blueprint()

BACKEND_DIR = Path(__file__).resolve().parent.parent
CONFIG = json.loads((BACKEND_DIR / "config" / "scoring_config.json").read_text())
VENDORS = json.loads((BACKEND_DIR / "data" / "vendors.json").read_text())

VENDOR_ACCEPT_TIMEOUT_SECONDS = int(os.environ.get("VENDOR_ACCEPT_TIMEOUT_SECONDS", CONFIG["vendorAcceptTimeoutSeconds"]))
DISPATCHER_REVIEW_TIMEOUT_SECONDS = int(os.environ.get("DISPATCHER_REVIEW_TIMEOUT_SECONDS", CONFIG["dispatcherReviewTimeoutSeconds"]))
MAX_RETRY_ATTEMPTS = int(os.environ.get("MAX_RETRY_ATTEMPTS", CONFIG["maxRetryAttempts"]))
_logger = logging.getLogger("retailfixit.orchestrator")

# Durable orchestrator functions must be deterministic (replay-safe) - all
# I/O, including bus.publish, happens in activities, never inline in
# job_orchestrator itself.
NON_TERMINAL_STATUSES = (df.OrchestrationRuntimeStatus.Running, df.OrchestrationRuntimeStatus.Pending)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _event_object(value) -> dict:
    """Normalize Durable external-event data from dict or JSON string."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _is_non_terminal(status) -> bool:
    return status in NON_TERMINAL_STATUSES or getattr(status, "name", str(status)) in {"Pending", "Running"}


# ---------------------------------------------------------------------------
# 1. Client function - Service Bus trigger on JobCreated -> start_new
# ---------------------------------------------------------------------------

@bp.service_bus_topic_trigger(
    arg_name="msg",
    topic_name=TOPIC,
    subscription_name="orchestrator-start",
    connection="ServiceBusConnection",
    is_sessions_enabled=True,
)
@bp.durable_client_input(client_name="client")
async def job_created_client(msg: func.ServiceBusMessage, client):
    job_event = json.loads(msg.get_body().decode("utf-8"))
    job_id = job_event["jobId"]

    # instanceId = jobId gives free idempotency/dedup - but with the default
    # Azure Storage backend, start_new raises against a live instance rather
    # than no-op'ing, so a redelivered JobCreated must check first.
    existing = await client.get_status(instance_id=job_id)
    if existing is not None and _is_non_terminal(existing.runtime_status):
        return

    await client.start_new("job_orchestrator", instance_id=job_id, client_input=job_event)


# ---------------------------------------------------------------------------
# 2-7. The orchestrator itself
# ---------------------------------------------------------------------------

@bp.orchestration_trigger(context_name="context")
def job_orchestrator(context: df.DurableOrchestrationContext):
    job_event = context.get_input()
    job_id = job_event["jobId"]
    correlation_id = job_event["correlationId"]

    yield context.call_activity("publish_scoring_requested_activity", job_event)
    score_factors = yield context.call_activity("score_job_activity", job_event)
    context.set_custom_status({"stage": "SCORED", "scoringRunId": score_factors["scoringRunId"]})

    if not score_factors["ranked"]:
        yield context.call_activity("escalate_activity", {
            "jobId": job_id, "correlationId": correlation_id, "reason": "NO_ELIGIBLE_VENDORS",
        })
        context.set_custom_status({"stage": "ESCALATED", "reason": "NO_ELIGIBLE_VENDORS"})
        return {"jobId": job_id, "status": "ESCALATED", "reason": "NO_ELIGIBLE_VENDORS"}

    shortlist = score_factors["ranked"]
    attempt = 0
    final_status = None

    while attempt < len(shortlist) and attempt <= MAX_RETRY_ATTEMPTS:
        candidate = shortlist[attempt]
        override_reason_code = None
        note = None

        # --- the gate fork: the single clearest "AI output drives a real
        # workflow decision" moment in the saga ---
        if candidate["automationEligible"]:
            assignment_source = "AUTO"
        else:
            yield context.call_activity("enqueue_manual_review_activity", {
                "jobId": job_id, "correlationId": correlation_id, "candidate": candidate,
            })
            context.set_custom_status({"stage": "PENDING_DISPATCHER_REVIEW", "candidate": candidate["vendorId"]})

            dispatcher_event = context.wait_for_external_event("DispatcherDecision")
            timeout_task = context.create_timer(context.current_utc_datetime + timedelta(seconds=DISPATCHER_REVIEW_TIMEOUT_SECONDS))
            winner = yield context.task_any([dispatcher_event, timeout_task])

            if winner is timeout_task:
                yield context.call_activity("escalate_activity", {
                    "jobId": job_id, "correlationId": correlation_id, "reason": "DISPATCHER_REVIEW_TIMEOUT",
                })
                final_status = "ESCALATED"
                break

            timeout_task.cancel()
            decision = _event_object(dispatcher_event.result)  # {"selectedVendorId", "overrideReasonCode"?, "note"?}
            override_reason_code = decision.get("overrideReasonCode")
            note = decision.get("note")
            if decision.get("selectedVendorId") != candidate["vendorId"]:
                assignment_source = "DISPATCHER_OVERRIDE"
                candidate = next((c for c in shortlist if c["vendorId"] == decision["selectedVendorId"]), candidate)
            else:
                assignment_source = "DISPATCHER_ACCEPT"

        yield context.call_activity("assign_vendor_activity", {
            "jobId": job_id, "correlationId": correlation_id, "vendorId": candidate["vendorId"],
            "assignmentSource": assignment_source, "scoringRunId": score_factors["scoringRunId"],
            "overrideReasonCode": override_reason_code, "note": note,
        })
        context.set_custom_status({"stage": "AWAITING_VENDOR_RESPONSE", "vendorId": candidate["vendorId"]})

        # --- vendor accept/decline, raced against a config-driven timer ---
        vendor_event = context.wait_for_external_event("VendorResponse")
        vendor_timeout_task = context.create_timer(context.current_utc_datetime + timedelta(seconds=VENDOR_ACCEPT_TIMEOUT_SECONDS))
        winner = yield context.task_any([vendor_event, vendor_timeout_task])

        if winner is vendor_event:
            vendor_timeout_task.cancel()
            response = _event_object(vendor_event.result)  # {"accepted": bool}
            if response.get("accepted"):
                final_status = "ASSIGNED"
                break
            # declined - bounded retry, walk the *existing* shortlist, no re-scoring
            attempt += 1
            continue
        else:
            # timed out waiting on the vendor - same bounded retry path as a decline
            attempt += 1
            continue

    if final_status is None:
        # exhausted maxAttempts without an accept
        yield context.call_activity("escalate_activity", {
            "jobId": job_id, "correlationId": correlation_id, "reason": "VENDOR_RETRIES_EXHAUSTED",
        })
        final_status = "ESCALATED"

    yield context.call_activity("complete_orchestration_activity", {
        "jobId": job_id, "correlationId": correlation_id, "status": final_status,
    })
    context.set_custom_status({"stage": "COMPLETE", "status": final_status})
    return {"jobId": job_id, "status": final_status}


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

@bp.activity_trigger(input_name="jobEvent")
def publish_scoring_requested_activity(jobEvent: dict) -> None:
    envelope = build_envelope(
        VENDOR_SCORING_REQUESTED, jobEvent["jobId"], jobEvent["correlationId"], {"job": jobEvent}
    )
    get_bus().publish(TOPIC, envelope)
    audit.log_event(envelope)


@bp.activity_trigger(input_name="jobEvent")
def score_job_activity(jobEvent: dict) -> dict:
    job_id = jobEvent["jobId"]
    correlation_id = jobEvent["correlationId"]
    _logger.info("score_activity_1_started", extra={"custom_dimensions": {"jobId": job_id, "correlationId": correlation_id}})
    try:
        score_factors = score_job(jobEvent, VENDORS, CONFIG)
        _logger.info("score_activity_2_score_job_completed", extra={"custom_dimensions": {
            "jobId": job_id, "scoringRunId": score_factors["scoringRunId"],
            "rankedCount": len(score_factors["ranked"]),
        }})
        audit.log_scoring_run(score_factors, correlation_id=correlation_id)
        _logger.info("score_activity_3_audit_completed", extra={"custom_dimensions": {
            "jobId": job_id, "scoringRunId": score_factors["scoringRunId"],
        }})
        store.put_score_factors(job_id, score_factors)
        _logger.info("score_activity_4_blob_store_completed", extra={"custom_dimensions": {
            "jobId": job_id, "scoringRunId": score_factors["scoringRunId"],
        }})

        recommendation_event = build_envelope(
            "job.recommendation_generated.v1", job_id, correlation_id,
            {"scoreFactors": score_factors},
        )
        get_bus().publish(TOPIC, recommendation_event)
        _logger.info("score_activity_5_recommendation_published", extra={"custom_dimensions": {
            "jobId": job_id, "scoringRunId": score_factors["scoringRunId"],
        }})
        audit.log_event(recommendation_event)
        _logger.info("score_activity_6_completed", extra={"custom_dimensions": {
            "jobId": job_id, "scoringRunId": score_factors["scoringRunId"],
        }})
        return score_factors
    except Exception:
        _logger.exception("score_activity_failed", extra={"custom_dimensions": {"jobId": job_id, "correlationId": correlation_id}})
        raise


@bp.activity_trigger(input_name="payload")
def enqueue_manual_review_activity(payload: dict) -> None:
    """Real deployment: enqueues to the `manual-review` queue for the
    Dispatcher Console. Locally: logged as a decision-pending record so
    the audit trail shows the hand-off happened."""
    audit.log_decision(
        jobId=payload["jobId"], correlationId=payload["correlationId"], scoringRunId=None,
        decision={"stage": "MANUAL_REVIEW_QUEUED", "candidate": payload["candidate"]["vendorId"]},
    )


@bp.activity_trigger(input_name="payload")
def assign_vendor_activity(payload: dict) -> None:
    """Builds the full assignment record (computed here, inside the
    activity, for determinism - never in the orchestrator) and writes it
    to the state store before publishing job.assigned - Durable Functions
    activities are the natural place for that write, since Durable
    already retries a failed activity without any Service Bus round-trip
    needed to get "at-least-once" for this step."""
    assignment = {
        "jobId": payload["jobId"],
        "correlationId": payload["correlationId"],
        "selectedVendorId": payload["vendorId"],
        "overrideReasonCode": payload.get("overrideReasonCode"),
        "note": payload.get("note"),
        "assignmentSource": payload["assignmentSource"],
        "assignedAtUtc": _now_iso(),
    }
    store.put_assignment(payload["jobId"], assignment)

    envelope = build_envelope(JOB_ASSIGNED, payload["jobId"], payload["correlationId"], assignment)
    get_bus().publish(TOPIC, envelope)
    audit.log_event(envelope)
    audit.log_decision(
        jobId=payload["jobId"], correlationId=payload["correlationId"],
        scoringRunId=payload.get("scoringRunId"), decision=assignment,
    )


@bp.activity_trigger(input_name="payload")
def escalate_activity(payload: dict) -> None:

    audit.log_decision(
        jobId=payload["jobId"], correlationId=payload["correlationId"], scoringRunId=None,
        decision={"stage": "ESCALATED", "reason": payload["reason"]},
    )


@bp.activity_trigger(input_name="payload")
def complete_orchestration_activity(payload: dict) -> None:
    """Appends the terminal outcome to the audit log (local stand-in for
    the Blob append in part1-architecture.md's step 14)."""
    audit.log_decision(
        jobId=payload["jobId"], correlationId=payload["correlationId"], scoringRunId=None,
        decision={"stage": "ORCHESTRATION_COMPLETE", "status": payload["status"]},
    )


# ---------------------------------------------------------------------------
# HTTP entry point that raises the external event the saga waits on for a
# vendor's accept/decline. (The DispatcherDecision event is raised from
# api/http_bp.py's create_assignment, which already does everything this
# route would - see that module.)
# ---------------------------------------------------------------------------

@bp.route(route="jobs/{jobId}/vendor-response", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@bp.durable_client_input(client_name="client")
async def submit_vendor_response(req: func.HttpRequest, client) -> func.HttpResponse:
    job_id = req.route_params["jobId"]
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"detail": "Request body must be valid JSON"}),
            status_code=400,
            mimetype="application/json",
        )
    if not isinstance(body, dict) or not isinstance(body.get("accepted"), bool):
        return func.HttpResponse(
            json.dumps({"detail": "accepted must be a boolean"}),
            status_code=422,
            mimetype="application/json",
        )
    status = await client.get_status(instance_id=job_id)
    if status is None or status.runtime_status is None:
        return func.HttpResponse(
            json.dumps({"detail": f"No active orchestration exists for jobId {job_id}"}),
            status_code=409,
            mimetype="application/json",
        )

    runtime_status = status.runtime_status
    if not _is_non_terminal(runtime_status):
        return func.HttpResponse(
            json.dumps({
                "detail": f"Orchestration {job_id} is already {runtime_status.name}; vendor response is no longer accepted",
                "runtimeStatus": runtime_status.name,
                "output": status.output,
            }, default=str),
            status_code=409,
            mimetype="application/json",
        )

    await client.raise_event(job_id, "VendorResponse", body)
    return func.HttpResponse(status_code=202)
