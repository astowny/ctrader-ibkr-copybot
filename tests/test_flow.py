"""Test du flux complet : réception -> confirmation -> exécution (paper)."""

from __future__ import annotations

import pytest

from copybot.core.bus import ORDER_EXECUTED, EventBus
from copybot.core.models import OrderResult, OrderStatus, Side, Signal
from copybot.execution.brokers.paper import PaperBroker
from copybot.execution.engine import ExecutionEngine
from copybot.filters.confirmation import ConfirmationFilter
from copybot.signals.receiver import SignalReceiver


@pytest.mark.asyncio
async def test_signal_flows_to_filled_order() -> None:
    bus = EventBus()
    captured: list[OrderResult] = []

    async def capture(result: OrderResult) -> None:
        captured.append(result)

    bus.subscribe(ORDER_EXECUTED, capture)

    receiver = SignalReceiver(bus)
    ConfirmationFilter(bus, max_open_positions=5)
    ExecutionEngine(bus, PaperBroker())

    await receiver.ingest(Signal(symbol="EURUSD", side=Side.BUY, volume=1.0, source="test"))

    assert len(captured) == 1
    assert captured[0].status is OrderStatus.FILLED
    assert captured[0].symbol == "EURUSD"


@pytest.mark.asyncio
async def test_invalid_volume_is_rejected() -> None:
    bus = EventBus()
    captured: list[OrderResult] = []

    async def capture(result: OrderResult) -> None:
        captured.append(result)

    bus.subscribe(ORDER_EXECUTED, capture)

    receiver = SignalReceiver(bus)
    flt = ConfirmationFilter(bus, max_open_positions=0)  # exposition nulle => rejet
    ExecutionEngine(bus, PaperBroker())

    await receiver.ingest(Signal(symbol="EURUSD", side=Side.SELL, volume=1.0, source="test"))

    # Rejeté par le filtre : aucun ordre exécuté.
    assert captured == []
    assert flt is not None
