"""Broker de simulation (paper trading) — utile en dev et pour les tests.

N'effectue aucun appel réseau : remplit immédiatement chaque ordre.
"""

from __future__ import annotations

import itertools

from ...core.logging import get_logger
from ...core.models import OrderResult, OrderStatus, Signal
from .base import BaseBroker

log = get_logger("broker.paper")


class PaperBroker(BaseBroker):
    name = "paper"

    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def place_order(self, signal: Signal) -> OrderResult:
        order_id = f"paper-{next(self._ids)}"
        log.info("[paper] ordre rempli %s %s vol=%s", signal.side.value, signal.symbol, signal.volume)
        return OrderResult(
            broker=self.name,
            symbol=signal.symbol,
            side=signal.side,
            volume=signal.volume,
            status=OrderStatus.FILLED,
            broker_order_id=order_id,
            detail="simulé",
        )

    async def disconnect(self) -> None:
        self._connected = False
