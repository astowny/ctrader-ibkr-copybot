"""Connecteur cTrader Open API (Pepperstone et autres brokers cTrader).

S'appuie sur `ctrader_client.CTraderOpenApiClient` (transport asyncio + protobuf).
Le client bas-niveau et le package `ctrader-open-api` sont importés *paresseusement*
dans `connect()` : on peut donc utiliser le bot en mode `paper` sans installer la
dépendance protobuf.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ...config import Settings
from ...core.logging import get_logger
from ...core.models import OrderResult, OrderStatus, Signal
from .base import BaseBroker, BrokerError

log = get_logger("broker.ctrader")


class CTraderBroker(BaseBroker):
    name = "ctrader"

    def __init__(
        self,
        settings: Settings,
        on_position_closed: Callable[[int], Awaitable[None]] | None = None,
    ) -> None:
        self._s = settings
        self._on_position_closed = on_position_closed
        self._client = None  # type: ignore[var-annotated]

    async def connect(self) -> None:
        if not (self._s.ctrader_client_id and self._s.ctrader_access_token and self._s.ctrader_account_id):
            raise BrokerError(
                "identifiants cTrader manquants (CTRADER_CLIENT_ID / _ACCESS_TOKEN / _ACCOUNT_ID — voir .env)"
            )
        try:
            from .ctrader_client import CTraderOpenApiClient  # import paresseux
        except ImportError as exc:  # dépendance optionnelle absente
            raise BrokerError(
                "package 'ctrader-open-api' non installé — `pip install -r requirements-ctrader.txt`"
            ) from exc

        self._client = CTraderOpenApiClient(
            host=self._s.ctrader_host,
            port=self._s.ctrader_port,
            client_id=self._s.ctrader_client_id,
            client_secret=self._s.ctrader_client_secret,
            access_token=self._s.ctrader_access_token,
            account_id=int(self._s.ctrader_account_id),
            on_position_closed=self._on_position_closed,
        )
        log.info("[ctrader] connexion %s:%s (compte %s)",
                 self._s.ctrader_host, self._s.ctrader_port, self._s.ctrader_account_id)
        await self._client.connect()

    async def place_order(self, signal: Signal) -> OrderResult:
        if self._client is None:
            raise BrokerError("client cTrader non connecté")
        report = await self._client.place_market_order(
            symbol=signal.symbol,
            side=signal.side.value,
            lots=signal.volume,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )
        return OrderResult(
            broker=self.name,
            symbol=signal.symbol,
            side=signal.side,
            volume=signal.volume,
            status=OrderStatus.FILLED,
            broker_order_id=str(report.order_id) if report.order_id else None,
            detail=f"{report.execution_type} pos={report.position_id}",
        )

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
