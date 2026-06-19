"""Connecteur Interactive Brokers (TWS / IB Gateway).

Squelette : l'implémentation réelle utilisera l'API IB (ex. `ib_insync` ou
`ibapi`) au-dessus de TWS/Gateway — connexion socket, qualification du
contrat, envoi d'ordre et suivi des statuts d'exécution.
"""

from __future__ import annotations

from ...config import Settings
from ...core.logging import get_logger
from ...core.models import OrderResult, Signal
from .base import BaseBroker, BrokerError

log = get_logger("broker.ibkr")


class IBKRBroker(BaseBroker):
    name = "ibkr"

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._connected = False

    async def connect(self) -> None:
        # TODO: ib.connectAsync(host, port, clientId) via ib_insync.
        log.info("[ibkr] connexion %s:%s (clientId=%s)",
                 self._s.ibkr_host, self._s.ibkr_port, self._s.ibkr_client_id)
        raise BrokerError("Connexion IBKR à implémenter (TWS/Gateway requis)")

    async def place_order(self, signal: Signal) -> OrderResult:
        # TODO: qualifyContracts + placeOrder + suivi des trades.
        raise NotImplementedError("Passage d'ordre IBKR à implémenter")

    async def disconnect(self) -> None:
        self._connected = False
