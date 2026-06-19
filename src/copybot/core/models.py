"""Modèles de données partagés entre les modules."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class Signal(BaseModel):
    """Signal brut normalisé après ingestion (module 1)."""

    symbol: str
    side: Side
    volume: float = Field(gt=0)
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    source: str = "unknown"
    received_at: datetime = Field(default_factory=_utcnow)
    meta: dict = Field(default_factory=dict)


class Confirmation(BaseModel):
    """Verdict du filtre de confirmation technique (module 2)."""

    signal: Signal
    approved: bool
    reason: str = ""


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    REJECTED = "rejected"
    ERROR = "error"


class OrderResult(BaseModel):
    """Résultat d'un passage d'ordre (module 3)."""

    broker: str
    symbol: str
    side: Side
    volume: float
    status: OrderStatus
    broker_order_id: str | None = None
    detail: str = ""
    executed_at: datetime = Field(default_factory=_utcnow)
