
from __future__ import annotations

TOPIC = "job-lifecycle"

JOB_CREATED = "job.created.v1"
VENDOR_SCORING_REQUESTED = "job.scoring_requested.v1"
VENDOR_RECOMMENDATION_GENERATED = "job.recommendation_generated.v1"
JOB_ASSIGNED = "job.assigned.v1"
JOB_COMPLETED = "job.completed.v1"

DEFAULT_MAX_DELIVERY_COUNT = 5

# subscription name -> (event types it receives, max delivery count before DLQ)
SUBSCRIPTIONS: dict[str, dict] = {
    "orchestrator-start": {"filterTypes": [JOB_CREATED], "maxDeliveryCount": DEFAULT_MAX_DELIVERY_COUNT},
    "scoring-function": {"filterTypes": [VENDOR_SCORING_REQUESTED], "maxDeliveryCount": DEFAULT_MAX_DELIVERY_COUNT},
    "orchestrator-recommendation": {"filterTypes": [VENDOR_RECOMMENDATION_GENERATED], "maxDeliveryCount": DEFAULT_MAX_DELIVERY_COUNT},
    "vendor-notify": {"filterTypes": [JOB_ASSIGNED], "maxDeliveryCount": DEFAULT_MAX_DELIVERY_COUNT},
    "outcome-capture": {"filterTypes": [JOB_COMPLETED], "maxDeliveryCount": DEFAULT_MAX_DELIVERY_COUNT},
}
