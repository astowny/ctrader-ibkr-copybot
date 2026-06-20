"""Framing du client cTrader (préfixe 4 octets big-endian + ProtoMessage).

Ne s'exécute que si `ctrader-open-api` est installé (`pip install -r requirements-ctrader.txt`).
Valide le point le plus facile à casser : l'encodage filaire.
"""

from __future__ import annotations

import struct

import pytest

pytest.importorskip("ctrader_open_api")

from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import (  # noqa: E402
    ProtoHeartbeatEvent,
    ProtoMessage,
)

from copybot.execution.brokers.ctrader_client import CTraderOpenApiClient  # noqa: E402


class _FakeWriter:
    def __init__(self) -> None:
        self.buf = b""

    def write(self, data: bytes) -> None:
        self.buf += data

    async def drain(self) -> None:
        pass


@pytest.mark.asyncio
async def test_send_frames_message_big_endian() -> None:
    c = CTraderOpenApiClient(
        host="h", port=1, client_id="a", client_secret="b", access_token="t", account_id=1
    )
    c._writer = _FakeWriter()  # type: ignore[assignment]

    await c._send(ProtoHeartbeatEvent())

    buf = c._writer.buf  # type: ignore[attr-defined]
    (length,) = struct.unpack(">I", buf[:4])  # préfixe 4 octets big-endian
    assert length == len(buf) - 4

    env = ProtoMessage()
    env.ParseFromString(buf[4:])
    assert env.payloadType == ProtoHeartbeatEvent().payloadType
