"""Bus d'événements asynchrone reliant les trois modules découplés.

Un simple pub/sub basé sur asyncio : chaque module publie sur un *topic* et
s'abonne à ceux qui l'intéressent, sans dépendance directe entre modules.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from .logging import get_logger

log = get_logger("bus")

Handler = Callable[[Any], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subscribers[topic].append(handler)
        log.debug("Abonnement à '%s' -> %s", topic, handler.__qualname__)

    async def publish(self, topic: str, payload: Any) -> None:
        handlers = self._subscribers.get(topic, [])
        if not handlers:
            log.warning("Aucun abonné pour le topic '%s'", topic)
            return
        # Les handlers sont isolés : l'échec de l'un n'interrompt pas les autres.
        results = await asyncio.gather(
            *(h(payload) for h in handlers), return_exceptions=True
        )
        for handler, result in zip(handlers, results):
            if isinstance(result, Exception):
                log.exception(
                    "Handler '%s' a échoué sur '%s': %r",
                    handler.__qualname__, topic, result,
                )


# Topics
SIGNAL_RECEIVED = "signal.received"
SIGNAL_CONFIRMED = "signal.confirmed"
ORDER_EXECUTED = "order.executed"
POSITION_OPENED = "position.opened"  # une position vient d'être ouverte (exposition +1)
POSITION_CLOSED = "position.closed"  # une position s'est fermée (SL/TP/manuel) → exposition -1

bus = EventBus()
