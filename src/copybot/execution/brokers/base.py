"""Interface commune à tous les connecteurs broker.

Chaque broker concret implémente connect / place_order / disconnect.
La logique de reconnexion automatique est fournie par `connect_with_retry`.
"""

from __future__ import annotations

import abc
import asyncio

from ...core.logging import get_logger
from ...core.models import OrderResult, Signal

log = get_logger("broker")


class BrokerError(Exception):
    """Erreur générique côté broker."""


class BaseBroker(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def connect(self) -> None:
        """Établit/authentifie la connexion et souscrit aux flux nécessaires."""

    @abc.abstractmethod
    async def place_order(self, signal: Signal) -> OrderResult:
        """Passe un ordre de façon asynchrone et renvoie le résultat."""

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Ferme proprement la connexion."""

    async def connect_with_retry(
        self, max_attempts: int = 0, base_delay: float = 1.0, max_delay: float = 30.0
    ) -> None:
        """Reconnexion automatique avec backoff exponentiel.

        max_attempts=0 → tentatives illimitées (utile pour un service long-running).
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                await self.connect()
                log.info("[%s] connecté (tentative %d)", self.name, attempt)
                return
            except Exception as exc:  # noqa: BLE001 - on veut journaliser toute panne
                if max_attempts and attempt >= max_attempts:
                    raise BrokerError(
                        f"[{self.name}] connexion échouée après {attempt} tentatives"
                    ) from exc
                delay = min(base_delay * 2 ** (attempt - 1), max_delay)
                log.warning(
                    "[%s] connexion échouée (%r), nouvel essai dans %.1fs",
                    self.name, exc, delay,
                )
                await asyncio.sleep(delay)
