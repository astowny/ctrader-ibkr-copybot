"""Connecteur cTrader Open API (Pepperstone).

Squelette : l'implémentation réelle s'appuiera sur le protocole Open API
(messages Protobuf sur TCP/TLS) — authentification applicative, autorisation
du compte, souscription au flux de cotations, puis envoi d'ordres marché/limite.

Les méthodes lèvent NotImplementedError tant que les identifiants ne sont pas
câblés ; le flux applicatif complet est néanmoins fonctionnel via PaperBroker.
"""

from __future__ import annotations

from ...config import Settings
from ...core.logging import get_logger
from ...core.models import OrderResult, Signal
from .base import BaseBroker, BrokerError

log = get_logger("broker.ctrader")


class CTraderBroker(BaseBroker):
    name = "ctrader"

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._connected = False

    async def connect(self) -> None:
        if not (self._s.ctrader_client_id and self._s.ctrader_access_token):
            raise BrokerError("identifiants cTrader manquants (voir .env)")
        # TODO: ouvrir le socket TLS vers ctrader_host:ctrader_port,
        #       ProtoOAApplicationAuthReq -> ProtoOAAccountAuthReq,
        #       souscrire ProtoOASubscribeSpotsReq.
        log.info("[ctrader] connexion %s:%s (compte %s)",
                 self._s.ctrader_host, self._s.ctrader_port, self._s.ctrader_account_id)
        raise NotImplementedError("Connexion cTrader Open API à implémenter")

    async def place_order(self, signal: Signal) -> OrderResult:
        # TODO: ProtoOANewOrderReq (MARKET/LIMIT) + suivi ProtoOAExecutionEvent.
        raise NotImplementedError("Passage d'ordre cTrader à implémenter")

    async def disconnect(self) -> None:
        self._connected = False
