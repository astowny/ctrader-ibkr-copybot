"""Client asynchrone cTrader Open API v2 — sans Twisted.

Réutilise UNIQUEMENT les classes protobuf du package `ctrader-open-api` et pilote
le socket TLS avec `asyncio`. Implémente le protocole filaire vérifié sur les
sources officielles (spotware/openapi-proto-messages + help.ctrader.com) :

  • Framing : préfixe de longueur 4 octets big-endian (>I) + ProtoMessage sérialisé.
  • Enveloppe : ProtoMessage{payloadType, payload, clientMsgId}. clientMsgId est
    renvoyé tel quel sur la réponse → corrélation requête/réponse.
  • Séquence : ApplicationAuth → AccountAuth → liste des symboles.
  • Heartbeat : le client envoie un ProtoHeartbeatEvent vide toutes les ~10 s.
  • Ordres marché : ProtoOANewOrderReq ; suivi via ProtoOAExecutionEvent.
  • Volume : unités × 100, piloté par le lotSize du symbole (EURUSD: 1 lot = 10_000_000).

L'import des messages protobuf nécessite `pip install ctrader-open-api`.
"""

from __future__ import annotations

import asyncio
import itertools
import ssl
import struct
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ...core.logging import get_logger
from .ctrader_volume import lots_to_volume

# --- messages protobuf (dépendance optionnelle ; importée seulement si broker=ctrader) ---
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import (
    ProtoErrorRes,
    ProtoHeartbeatEvent,
    ProtoMessage,
)
from ctrader_open_api.messages.OpenApiMessages_pb2 import (
    ProtoOAAccountAuthReq,
    ProtoOAApplicationAuthReq,
    ProtoOAErrorRes,
    ProtoOAExecutionEvent,
    ProtoOANewOrderReq,
    ProtoOAOrderErrorEvent,
    ProtoOASymbolByIdReq,
    ProtoOASymbolByIdRes,
    ProtoOASymbolsListReq,
    ProtoOASymbolsListRes,
)
from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
    ProtoOAExecutionType,
    ProtoOAOrderType,
    ProtoOAPayloadType,
    ProtoOAPositionStatus,
    ProtoOATradeSide,
)

log = get_logger("broker.ctrader.client")

HEARTBEAT_INTERVAL = 7.0  # marge sous la règle "≤ 10 s" (latence réseau/GC incluse)
REQUEST_TIMEOUT = 30.0


def _enum_name(enum, value) -> str:
    """Nom d'une valeur d'enum protobuf, tolérant aux valeurs inconnues (forward-compat)."""
    try:
        return enum.Name(value)
    except Exception:  # noqa: BLE001
        return str(value)

# Référence rapide des payloadType utilisés en réception.
_PT = ProtoOAPayloadType
_HEARTBEAT_PT = ProtoHeartbeatEvent().payloadType
_COMMON_ERROR_PT = ProtoErrorRes().payloadType


class CTraderError(Exception):
    """Erreur métier renvoyée par le serveur cTrader (auth, ordre, etc.)."""


@dataclass(frozen=True)
class SymbolInfo:
    symbol_id: int
    lot_size: int      # volume protocole d'1 lot (déjà à l'échelle ×100)
    min_volume: int
    max_volume: int
    step_volume: int


@dataclass(frozen=True)
class ExecutionReport:
    execution_type: str
    order_id: int | None
    position_id: int | None
    position_status: str | None
    detail: str = ""


class CTraderOpenApiClient:
    """Client TLS asyncio minimal mais complet pour passer des ordres marché."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        client_id: str,
        client_secret: str,
        access_token: str,
        account_id: int,
        on_position_closed: Callable[[int], Awaitable[None]] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token = access_token
        self._account_id = int(account_id)
        self._on_position_closed = on_position_closed

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._ids = itertools.count(1)
        self._pending: dict[str, tuple[str, asyncio.Future]] = {}
        self._tasks: list[asyncio.Task] = []

        self._symbol_id: dict[str, int] = {}          # "EURUSD" -> id
        self._symbol_info: dict[int, SymbolInfo] = {}  # id -> détails (lotSize…)

    # ------------------------------------------------------------------ connexion
    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port, ssl=ssl.create_default_context()
        )
        self._tasks = [
            asyncio.create_task(self._read_loop(), name="ctrader-read"),
            asyncio.create_task(self._heartbeat_loop(), name="ctrader-heartbeat"),
        ]
        await self._application_auth()
        await self._account_auth()
        await self._load_symbols()
        log.info("[ctrader] authentifié (compte %s), %d symboles chargés",
                 self._account_id, len(self._symbol_id))

    async def disconnect(self) -> None:
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)  # attend la fin réelle
        self._tasks.clear()
        self._fail_pending(CTraderError("connexion fermée"))
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001 - fermeture best-effort
                pass
        self._reader = self._writer = None

    def _fail_pending(self, exc: Exception, *, only_kind: str | None = None) -> None:
        """Fait échouer (et retire) les requêtes en attente — évite les hangs sur déconnexion."""
        for cmid, (kind, fut) in list(self._pending.items()):
            if only_kind is not None and kind != only_kind:
                continue
            if not fut.done():
                fut.set_exception(exc)
            self._pending.pop(cmid, None)

    # ------------------------------------------------------------------ ordres
    async def place_market_order(
        self,
        *,
        symbol: str,
        side: str,
        lots: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> ExecutionReport:
        """Passe un ordre marché et attend l'événement d'exécution terminal."""
        info = await self._symbol_info_for(symbol)
        volume = self._lots_to_volume(lots, info)

        req = ProtoOANewOrderReq(
            ctidTraderAccountId=self._account_id,
            symbolId=info.symbol_id,
            orderType=ProtoOAOrderType.MARKET,
            tradeSide=ProtoOATradeSide.BUY if side == "buy" else ProtoOATradeSide.SELL,
            volume=volume,
        )
        if stop_loss is not None and stop_loss > 0:
            req.stopLoss = stop_loss  # prix absolu
        if take_profit is not None and take_profit > 0:
            req.takeProfit = take_profit  # prix absolu

        result = await self._request(req, kind="order")
        return result  # ExecutionReport

    # ------------------------------------------------------------------ symboles
    async def _symbol_info_for(self, symbol: str) -> SymbolInfo:
        sid = self._symbol_id.get(symbol.upper())
        if sid is None:
            raise CTraderError(f"symbole inconnu sur ce compte: {symbol}")
        if sid not in self._symbol_info:
            res: ProtoOASymbolByIdRes = await self._request(
                ProtoOASymbolByIdReq(ctidTraderAccountId=self._account_id, symbolId=[sid]),
                kind="response",
            )
            s = res.symbol[0]
            self._symbol_info[sid] = SymbolInfo(
                symbol_id=sid,
                lot_size=int(s.lotSize),
                min_volume=int(s.minVolume),
                max_volume=int(s.maxVolume),
                step_volume=int(s.stepVolume) or 1,
            )
        return self._symbol_info[sid]

    @staticmethod
    def _lots_to_volume(lots: float, info: SymbolInfo) -> int:
        """Convertit un nombre de lots en volume protocole et valide les bornes."""
        try:
            return lots_to_volume(
                lots,
                lot_size=info.lot_size,
                min_volume=info.min_volume,
                max_volume=info.max_volume,
                step_volume=info.step_volume,
            )
        except ValueError as exc:
            raise CTraderError(f"{exc} (symbolId={info.symbol_id})") from exc

    async def _load_symbols(self) -> None:
        res: ProtoOASymbolsListRes = await self._request(
            ProtoOASymbolsListReq(ctidTraderAccountId=self._account_id),
            kind="response",
        )
        self._symbol_id = {s.symbolName.upper(): s.symbolId for s in res.symbol if s.symbolName}

    # ------------------------------------------------------------------ auth
    async def _application_auth(self) -> None:
        await self._request(
            ProtoOAApplicationAuthReq(
                clientId=self._client_id, clientSecret=self._client_secret
            ),
            kind="response",
        )

    async def _account_auth(self) -> None:
        await self._request(
            ProtoOAAccountAuthReq(
                ctidTraderAccountId=self._account_id, accessToken=self._access_token
            ),
            kind="response",
        )

    # ------------------------------------------------------------------ transport
    async def _send(self, inner, client_msg_id: str | None = None) -> None:
        if self._writer is None:
            raise CTraderError("non connecté")
        env = ProtoMessage(
            payloadType=inner.payloadType,         # défaut proto = type du message
            payload=inner.SerializeToString(),
            clientMsgId=client_msg_id or "",
        )
        body = env.SerializeToString()
        self._writer.write(struct.pack(">I", len(body)) + body)  # préfixe 4o big-endian
        await self._writer.drain()

    async def _request(self, inner, *, kind: str):
        cmid = str(next(self._ids))
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[cmid] = (kind, fut)
        try:
            await self._send(inner, cmid)
            return await asyncio.wait_for(fut, REQUEST_TIMEOUT)
        finally:
            self._pending.pop(cmid, None)

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self._send(ProtoHeartbeatEvent())
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("[ctrader] heartbeat interrompu: %r", exc)

    async def _read_loop(self) -> None:
        assert self._reader is not None
        try:
            while True:
                header = await self._reader.readexactly(4)
                (length,) = struct.unpack(">I", header)
                body = await self._reader.readexactly(length)
                env = ProtoMessage()
                env.ParseFromString(body)
                await self._dispatch(env)
        except asyncio.IncompleteReadError:
            log.warning("[ctrader] flux fermé par le serveur")
            self._fail_pending(CTraderError("connexion fermée par le serveur"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("[ctrader] erreur read loop: %r", exc)
            self._fail_pending(CTraderError(f"erreur transport: {exc}"))

    async def _dispatch(self, env: ProtoMessage) -> None:
        pt = env.payloadType
        if pt == _HEARTBEAT_PT:
            return

        cmid = env.clientMsgId
        entry = self._pending.get(cmid)

        # --- erreurs ---
        if pt in (_PT.PROTO_OA_ERROR_RES, _COMMON_ERROR_PT, _PT.PROTO_OA_ORDER_ERROR_EVENT):
            msg = ProtoOAErrorRes() if pt == _PT.PROTO_OA_ERROR_RES else (
                ProtoOAOrderErrorEvent() if pt == _PT.PROTO_OA_ORDER_ERROR_EVENT else ProtoErrorRes()
            )
            msg.ParseFromString(env.payload)
            detail = f"{getattr(msg, 'errorCode', '?')}: {getattr(msg, 'description', '')}"
            if entry:
                _, fut = entry
                if not fut.done():
                    fut.set_exception(CTraderError(detail))
            elif pt == _PT.PROTO_OA_ORDER_ERROR_EVENT:
                # erreur d'ordre non corrélée (clientMsgId parfois vide) → on fait
                # échouer l'ordre en vol au lieu d'attendre le timeout de 30 s.
                self._fail_pending(CTraderError(detail), only_kind="order")
            else:
                log.error("[ctrader] erreur non sollicitée: %s", detail)
            return

        # --- événements d'exécution ---
        if pt == _PT.PROTO_OA_EXECUTION_EVENT:
            evt = ProtoOAExecutionEvent()
            evt.ParseFromString(env.payload)
            await self._handle_execution(evt, entry)
            return

        # --- réponses simples (auth, symboles…) : on rend le message parsé ---
        if entry:
            kind, fut = entry
            if kind == "response" and not fut.done():
                fut.set_result(self._parse_inner(pt, env.payload))
            return

        log.debug("[ctrader] message non traité payloadType=%s", pt)

    async def _handle_execution(self, evt: ProtoOAExecutionEvent, entry) -> None:
        et = evt.executionType
        status = None
        if evt.HasField("position"):
            status = _enum_name(ProtoOAPositionStatus, evt.position.positionStatus)

        # fermeture de position côté broker (SL/TP, manuel) -> on notifie pour l'exposition
        if status == "POSITION_STATUS_CLOSED" and self._on_position_closed is not None:
            try:
                await self._on_position_closed(evt.position.positionId)
            except Exception:  # noqa: BLE001
                log.exception("[ctrader] callback position fermée a échoué")

        if entry is None:
            return  # événement non corrélé à un ordre en attente

        kind, fut = entry
        if kind != "order" or fut.done():
            return

        terminal_ok = {ProtoOAExecutionType.ORDER_FILLED, ProtoOAExecutionType.ORDER_PARTIAL_FILL}
        if et in terminal_ok:
            fut.set_result(
                ExecutionReport(
                    execution_type=_enum_name(ProtoOAExecutionType, et),
                    order_id=evt.order.orderId if evt.HasField("order") else None,
                    position_id=evt.position.positionId if evt.HasField("position") else None,
                    position_status=status,
                )
            )
        elif et == ProtoOAExecutionType.ORDER_REJECTED:
            fut.set_exception(CTraderError(f"ordre rejeté: {evt.errorCode}"))
        # ORDER_ACCEPTED : intermédiaire pour un ordre marché -> on attend le FILLED

    @staticmethod
    def _parse_inner(payload_type: int, payload: bytes):
        cls = {
            _PT.PROTO_OA_APPLICATION_AUTH_RES: None,  # pas de champ utile
            _PT.PROTO_OA_ACCOUNT_AUTH_RES: None,
            _PT.PROTO_OA_SYMBOLS_LIST_RES: ProtoOASymbolsListRes,
            _PT.PROTO_OA_SYMBOL_BY_ID_RES: ProtoOASymbolByIdRes,
        }.get(payload_type, None)
        if cls is None:
            return True  # réponse "OK" sans contenu exploité
        msg = cls()
        msg.ParseFromString(payload)
        return msg
