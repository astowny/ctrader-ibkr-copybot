"""Endpoints HTTP : santé + réception de signaux (webhook)."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from ..config import settings
from ..core.models import Signal
from ..signals.receiver import SignalReceiver

router = APIRouter()


def get_router(receiver: SignalReceiver) -> APIRouter:
    """Construit le routeur en injectant le récepteur de signaux."""

    @router.get("/health")
    async def health() -> dict:
        return {"status": "ok", "broker": settings.broker}

    @router.post("/signals", status_code=202)
    async def post_signal(
        signal: Signal, x_webhook_secret: str = Header(default="")
    ) -> dict:
        if x_webhook_secret != settings.signal_webhook_secret:
            raise HTTPException(status_code=401, detail="secret webhook invalide")
        await receiver.ingest(signal)
        return {"accepted": True, "symbol": signal.symbol}

    return router
