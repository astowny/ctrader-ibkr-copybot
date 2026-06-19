"""Module 1 — Réception des signaux.

Normalise un signal entrant (webhook, flux, Telegram…) puis le publie sur le bus.
"""

from __future__ import annotations

from ..core.bus import SIGNAL_RECEIVED, EventBus
from ..core.logging import get_logger
from ..core.models import Signal

log = get_logger("signals")


class SignalReceiver:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def ingest(self, signal: Signal) -> None:
        """Point d'entrée : valide déjà via Pydantic, journalise, puis publie."""
        log.info(
            "Signal reçu: %s %s vol=%s (source=%s)",
            signal.side.value, signal.symbol, signal.volume, signal.source,
        )
        await self._bus.publish(SIGNAL_RECEIVED, signal)
