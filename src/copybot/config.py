"""Configuration centralisée, chargée depuis l'environnement / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Broker actif : ctrader | ibkr | paper
    broker: str = "paper"
    signal_webhook_secret: str = "change-me"

    # cTrader
    ctrader_client_id: str = ""
    ctrader_client_secret: str = ""
    ctrader_access_token: str = ""
    ctrader_account_id: str = ""
    ctrader_host: str = "demo.ctraderapi.com"
    ctrader_port: int = 5035

    # IBKR
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 1

    # Risque
    max_risk_per_trade: float = 0.01
    max_open_positions: int = 5


settings = Settings()
