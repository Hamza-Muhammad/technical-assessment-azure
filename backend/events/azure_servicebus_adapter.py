
from __future__ import annotations

import json
import os
import uuid

from events.bus_interface import EventBus, Handler

TOPIC_NAME = "job-lifecycle"


class AzureServiceBusBus(EventBus):
    def __init__(self, fully_qualified_namespace: str | None = None):
        from azure.identity import DefaultAzureCredential
        from azure.servicebus import ServiceBusClient

        self._namespace = fully_qualified_namespace or os.environ["SERVICE_BUS_NAMESPACE"]
        self._client = ServiceBusClient(
            fully_qualified_namespace=self._namespace,
            credential=DefaultAzureCredential(),
        )

    def create_subscription(self, topic: str, subscription: str, max_delivery_count: int = 10,
                             filter_types: list[str] | None = None) -> None:
        """Provisioning (topic/subscription/DLQ/max-delivery-count/SQL
        filter) is done declaratively in infra/main.bicep, not at runtime -
        this method exists only so callers can treat both bus
        implementations identically; against the real adapter it's a
        no-op by design."""
        return None

    def publish(self, topic: str, event: dict) -> str:
        from azure.servicebus import ServiceBusMessage

        if "sessionId" not in event:
            raise ValueError("event must carry sessionId (== jobId) for session-ordered delivery")
        message_id = event.get("messageId") or str(uuid.uuid4())
        event = dict(event)
        event["messageId"] = message_id

        with self._client.get_topic_sender(topic_name=topic) as sender:
            msg = ServiceBusMessage(
                json.dumps(event),
                session_id=event["sessionId"],
                message_id=message_id,
                content_type="application/json",
                application_properties={"type": event["type"]},
            )
            sender.send_messages(msg)
        return message_id

    def receive(self, topic: str, subscription: str, handler: Handler, max_messages: int | None = None) -> int:
        """Accepts a session (blocking until one is available), processes
        its messages in order, completes on success or abandons on
        failure - Service Bus itself tracks delivery count per message and
        auto-dead-letters once the subscription's MaxDeliveryCount is
        exceeded, landing it in `subscription/$deadletterqueue`."""
        processed = 0
        with self._client.get_subscription_receiver(
            topic_name=topic, subscription_name=subscription, session_id=None
        ) as receiver:
            for msg in receiver:
                if max_messages is not None and processed >= max_messages:
                    break
                event = json.loads(str(msg))
                try:
                    handler(event)
                    receiver.complete_message(msg)
                    processed += 1
                except Exception:
                    receiver.abandon_message(msg)  # redelivered; DLQ'd automatically past MaxDeliveryCount
        return processed

    def dead_letters(self, topic: str, subscription: str) -> list[dict]:
        results = []
        with self._client.get_subscription_receiver(
            topic_name=topic,
            subscription_name=subscription,
            sub_queue="deadletter",
        ) as receiver:
            for msg in receiver.receive_messages(max_message_count=100, max_wait_time=2):
                results.append(json.loads(str(msg)))
                receiver.complete_message(msg)
        return results
