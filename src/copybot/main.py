"""Point d'entrée FastAPI : câble les trois modules autour du bus d'événements."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import get_router
from .config import settings
from .core.bus import bus
from .core.logging import configure_logging, get_logger
from .execution.engine import ExecutionEngine, build_broker
from .filters.confirmation import ConfirmationFilter
from .signals.receiver import SignalReceiver

configure_logging(settings.log_level)
log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Câblage des modules (chacun s'abonne aux topics qui le concernent).
    receiver = SignalReceiver(bus)
    ConfirmationFilter(bus, max_open_positions=settings.max_open_positions)
    engine = ExecutionEngine(bus, build_broker(settings))

    app.include_router(get_router(receiver))

    log.info("Démarrage copybot (broker=%s)", settings.broker)
    await engine.start()
    try:
        yield
    finally:
        await engine.stop()
        log.info("Arrêt copybot")


app = FastAPI(title="ctrader-ibkr-copybot", version="0.1.0", lifespan=lifespan)
