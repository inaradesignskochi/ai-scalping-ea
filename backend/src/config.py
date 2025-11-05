"""
Configuration management for AI Scalping EA
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Database
    db_password: str = Field(..., env="DB_PASSWORD")
    postgres_db: str = Field("trading_db", env="POSTGRES_DB")
    postgres_user: str = Field("trader", env="POSTGRES_USER")
    database_url: str = Field(..., env="DATABASE_URL")

    # AI APIs
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")

    # Monitoring
    grafana_password: str = Field(..., env="GRAFANA_PASSWORD")

    # MT4 Connection
    mt4_server_ip: Optional[str] = Field(None, env="MT4_SERVER_IP")
    mt4_login: Optional[str] = Field(None, env="MT4_LOGIN")
    mt4_password: Optional[str] = Field(None, env="MT4_PASSWORD")

    # Free Tier API Keys
    alpaca_api_key: Optional[str] = Field(None, env="ALPACA_API_KEY")
    alpaca_secret_key: Optional[str] = Field(None, env="ALPACA_SECRET_KEY")
    marketaux_api_key: Optional[str] = Field(None, env="MARKETAUX_API_KEY")
    eodhd_api_key: Optional[str] = Field(None, env="EODHD_API_KEY")
    fmp_api_key: Optional[str] = Field(None, env="FMP_API_KEY")
    newsapi_api_key: Optional[str] = Field(None, env="NEWSAPI_API_KEY")
    gdelt_api_key: Optional[str] = Field(None, env="GDELT_API_KEY")

    # Redis
    redis_url: str = Field("redis://redis:6379", env="REDIS_URL")

    # Telegram Notifications
    telegram_bot_token: Optional[str] = Field(None, env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(None, env="TELEGRAM_CHAT_ID")

    # Security
    secret_key: str = Field(..., env="SECRET_KEY")
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")

    # Trading Parameters
    risk_percent: float = Field(0.02, env="RISK_PERCENT")
    max_daily_loss: float = Field(0.05, env="MAX_DAILY_LOSS")
    min_lot_size: float = Field(0.01, env="MIN_LOT_SIZE")
    max_lot_size: float = Field(1.0, env="MAX_LOT_SIZE")
    atr_sl_multiplier: float = Field(1.5, env="ATR_SL_MULTIPLIER")
    magic_number: int = Field(12345, env="MAGIC_NUMBER")

    # AI Parameters
    confidence_threshold: float = Field(0.75, env="CONFIDENCE_THRESHOLD")
    model_update_interval: int = Field(3600, env="MODEL_UPDATE_INTERVAL")
    backtest_period_days: int = Field(365, env="BACKTEST_PERIOD_DAYS")

    # Monitoring
    prometheus_port: int = Field(9090, env="PROMETHEUS_PORT")
    grafana_port: int = Field(3000, env="GRAFANA_PORT")
    streamlit_port: int = Field(8501, env="STREAMLIT_PORT")

    # ZMQ Configuration
    zmq_signal_port: int = Field(5555, env="ZMQ_SIGNAL_PORT")
    zmq_heartbeat_port: int = Field(5556, env="ZMQ_HEARTBEAT_PORT")
    zmq_host: str = Field("0.0.0.0", env="ZMQ_HOST")

    # WebSocket Fallback
    websocket_port: int = Field(8765, env="WEBSOCKET_PORT")
    websocket_host: str = Field("0.0.0.0", env="WEBSOCKET_HOST")

    # Application
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def db_connection_string(self) -> str:
        """Database connection string"""
        return self.database_url

    @property
    def redis_connection_string(self) -> str:
        """Redis connection string"""
        return self.redis_url

    @property
    def zmq_signal_address(self) -> str:
        """ZMQ signal publisher address"""
        return f"tcp://{self.zmq_host}:{self.zmq_signal_port}"

    @property
    def zmq_heartbeat_address(self) -> str:
        """ZMQ heartbeat responder address"""
        return f"tcp://{self.zmq_host}:{self.zmq_heartbeat_port}"

    @property
    def websocket_address(self) -> str:
        """WebSocket server address"""
        return f"{self.websocket_host}:{self.websocket_port}"


# Global settings instance
settings = Settings()