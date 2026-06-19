"""Module 2 — Filtre de confirmation technique.

Abonné à `signal.received`, applique une série de règles de validation puis
publie un `signal.confirmed` uniquement si le signal est approuvé.

Les règles ci-dessous sont des points d'extension : on y branchera les
indicateurs réels (tendance, volatilité, exposition, sessions de marché…).
"""

from __future__ import annotations

from ..core.bus import SIGNAL_CONFIRMED, SIGNAL_RECEIVED, EventBus
from ..core.logging import get_logger
from ..core.models import Confirmation, Signal

log = get_logger("filters")


class ConfirmationFilter:
    def __init__(self, bus: EventBus, max_open_positions: int) -> None:
        self._bus = bus
        self._max_open_positions = max_open_positions
        self._open_positions = 0
        bus.subscribe(SIGNAL_RECEIVED, self.on_signal)

    async def on_signal(self, signal: Signal) -> None:
        confirmation = self._evaluate(signal)
        if confirmation.approved:
            log.info("Signal confirmé: %s %s", signal.side.value, signal.symbol)
            await self._bus.publish(SIGNAL_CONFIRMED, confirmation)
        else:
            log.info("Signal rejeté (%s): %s", confirmation.reason, signal.symbol)

    def _evaluate(self, signal: Signal) -> Confirmation:
        # Règle d'exposition maximale.
        if self._open_positions >= self._max_open_positions:
            return Confirmation(
                signal=signal, approved=False, reason="exposition maximale atteinte"
            )

        # TODO: confirmation technique réelle (tendance EMA, ATR, etc.).
        # Placeholder : on approuve si le volume est cohérent.
        if signal.volume <= 0:
            return Confirmation(signal=signal, approved=False, reason="volume invalide")

        return Confirmation(signal=signal, approved=True, reason="ok")

    def register_fill(self) -> None:
        self._open_positions += 1
