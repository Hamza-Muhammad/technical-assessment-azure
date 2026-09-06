
from __future__ import annotations

from datetime import datetime, timezone

import audit
from events.bus_interface import EventBus
from events.topology import JOB_ASSIGNED, JOB_COMPLETED, JOB_CREATED, TOPIC


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_envelope(event_type: str, job_id: str, correlation_id: str, data: dict) -> dict:
    return {
        "type": event_type,
        "jobId": job_id,
        "sessionId": job_id,
        "correlationId": correlation_id,
        "occurredAtUtc": _now_iso(),
        "data": data,
    }


def publish_job_created(bus: EventBus, job_event: dict) -> str:
    envelope = build_envelope(JOB_CREATED, job_event["jobId"], job_event["correlationId"], job_event["data"])
    message_id = bus.publish(TOPIC, envelope)
    audit.log_event({**envelope, "messageId": message_id})
    return message_id


def publish_job_assigned(bus: EventBus, job_id: str, correlation_id: str, assignment: dict) -> str:
    envelope = build_envelope(JOB_ASSIGNED, job_id, correlation_id, assignment)
    message_id = bus.publish(TOPIC, envelope)
    audit.log_event({**envelope, "messageId": message_id})
    return message_id


def publish_job_completed(bus: EventBus, job_id: str, correlation_id: str, outcome: dict) -> str:
    envelope = build_envelope(JOB_COMPLETED, job_id, correlation_id, outcome)
    message_id = bus.publish(TOPIC, envelope)
    audit.log_event({**envelope, "messageId": message_id})
    return message_id
