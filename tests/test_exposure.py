"""Garde-fou d'exposition : le compteur de positions ouvertes est désormais actif.

Régression du bug où `register_fill` n'était jamais appelé → la limite
`max_open_positions` ne se déclenchait jamais.
"""

from __future__ import annotations

import pytest

from copybot.core.bus import ORDER_EXECUTED, POSITION_CLOSED, EventBus
from copybot.core.models import OrderResult, Side, Signal
from copybot.execution.brokers.paper import PaperBroker
from copybot.execution.engine import ExecutionEngine
from copybot.filters.confirmation import ConfirmationFilter
from copybot.signals.receiver import SignalReceiver


def _wire(max_open: int):
    bus = EventBus()
    captured: list[OrderResult] = []

    async def capture(result: OrderResult) -> None:
        captured.append(result)

    bus.subscribe(ORDER_EXECUTED, capture)
    receiver = SignalReceiver(bus)
    flt = ConfirmationFilter(bus, max_open_positions=max_open)
    ExecutionEngine(bus, PaperBroker())
    return bus, receiver, flt, captured


def _sig() -> Signal:
    return Signal(symbol="EURUSD", side=Side.BUY, volume=1.0, source="test")


@pytest.mark.asyncio
async def test_exposure_cap_blocks_beyond_max() -> None:
    bus, receiver, flt, captured = _wire(max_open=2)

    await receiver.ingest(_sig())  # 1 → rempli, exposition 1
    await receiver.ingest(_sig())  # 2 → rempli, exposition 2
    await receiver.ingest(_sig())  # 3 → rejeté (max atteint)

    assert len(captured) == 2
    assert flt.open_positions == 2


@pytest.mark.asyncio
async def test_position_close_frees_a_slot() -> None:
    bus, receiver, flt, captured = _wire(max_open=2)

    await receiver.ingest(_sig())
    await receiver.ingest(_sig())
    assert flt.open_positions == 2

    # Une position se ferme (SL/TP/manuel) → un créneau se libère.
    await bus.publish(POSITION_CLOSED, 12345)
    assert flt.open_positions == 1

    await receiver.ingest(_sig())  # de nouveau autorisé
    assert len(captured) == 3
    assert flt.open_positions == 2
