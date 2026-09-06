
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

Handler = Callable[[dict], None]


class EventBus(ABC):
    @abstractmethod
    def publish(self, topic: str, event: dict) -> str:
        """event must include `sessionId` (== jobId) and `type`. Returns
        the assigned messageId."""

    @abstractmethod
    def create_subscription(self, topic: str, subscription: str, max_delivery_count: int = 10,
                             filter_types: list[str] | None = None) -> None:
        """filter_types=None subscribes to every event type on the topic;
        otherwise only events whose `type` is in the list are delivered -
        mirrors a Service Bus subscription SQL filter on the `type`
        application property."""

    @abstractmethod
    def receive(self, topic: str, subscription: str, handler: Handler, max_messages: int | None = None) -> int:
        """Process up to `max_messages` currently available messages (None
        = drain everything currently queued). Returns count processed
        successfully. Handler exceptions trigger redelivery per session,
        up to the subscription's max delivery count, then dead-letter."""

    @abstractmethod
    def dead_letters(self, topic: str, subscription: str) -> list[dict]:
        ...
