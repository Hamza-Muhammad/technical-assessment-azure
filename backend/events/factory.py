"""
Constructs the one real event bus implementation - Azure Service Bus - as
a lazy singleton. Everything else in the app only ever imports `get_bus()`
from here, never AzureServiceBusBus directly.
"""
from __future__ import annotations

from events.bus_interface import EventBus
from events.topology import SUBSCRIPTIONS, TOPIC

_bus: EventBus | None = None


def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        from events.azure_servicebus_adapter import AzureServiceBusBus
        _bus = AzureServiceBusBus()
        for name, cfg in SUBSCRIPTIONS.items():
            _bus.create_subscription(TOPIC, name, max_delivery_count=cfg["maxDeliveryCount"], filter_types=cfg["filterTypes"])
    return _bus
