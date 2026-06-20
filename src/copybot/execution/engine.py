"""Module 3 — Moteur d'exécution.

Abonné à `signal.confirmed`, passe l'ordre via le broker sélectionné, journalise
le résultat et publie `order.executed`. La sélection du broker se fait par config.
"""

from __future__ import annotations

from ..config import Settings
from ..core.bus import (
    ORDER_EXECUTED,
    POSITION_CLOSED,
    POSITION_OPENED,
    SIGNAL_CONFIRMED,
    EventBus,
)
from ..core.logging import get_logger
from ..core.models import Confirmation, OrderResult, OrderStatus
from .brokers.base import BaseBroker
from .brokers.ctrader import CTraderBroker
from .brokers.ibkr import IBKRBroker
from .brokers.paper import PaperBroker

log = get_logger("execution")


def build_broker(settings: Settings, bus: EventBus | None = None) -> BaseBroker:
    match settings.broker.lower():
        case "ctrader":
            async def _on_closed(position_id: int) -> None:
                if bus is not None:
                    await bus.publish(POSITION_CLOSED, position_id)

            return CTraderBroker(settings, on_position_closed=_on_closed)
        case "ibkr":
            return IBKRBroker(settings)
        case _:
            return PaperBroker()


class ExecutionEngine:
    def __init__(self, bus: EventBus, broker: BaseBroker) -> None:
        self._bus = bus
        self._broker = broker
        bus.subscribe(SIGNAL_CONFIRMED, self.on_confirmed)

    async def start(self) -> None:
        await self._broker.connect_with_retry()

    async def stop(self) -> None:
        await self._broker.disconnect()

    async def on_confirmed(self, confirmation: Confirmation) -> None:
        signal = confirmation.signal
        try:
            result = await self._broker.place_order(signal)
        except Exception as exc:  # noqa: BLE001 - journaliser toute erreur d'exécution
            log.exception("Échec d'exécution %s %s: %r", signal.side.value, signal.symbol, exc)
            result = OrderResult(
                broker=self._broker.name,
                symbol=signal.symbol,
                side=signal.side,
                volume=signal.volume,
                status=OrderStatus.ERROR,
                detail=str(exc),
            )

        # Journalisation complète des ordres (audit / replay).
        log.info(
            "ORDRE | broker=%s | %s %s vol=%s | status=%s | id=%s | %s",
            result.broker, result.side.value, result.symbol, result.volume,
            result.status.value, result.broker_order_id, result.detail,
        )
        await self._bus.publish(ORDER_EXECUTED, result)

        # Un ordre rempli issu d'un signal ouvre une position → exposition +1.
        # (Les fermetures côté broker — SL/TP/manuel — arrivent via POSITION_CLOSED.)
        if result.status is OrderStatus.FILLED:
            await self._bus.publish(POSITION_OPENED, result)
