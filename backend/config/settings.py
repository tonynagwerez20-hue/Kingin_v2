"""Config Module."""
from functools import lru_cache
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    
    # MT5
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    
    # ZMQ
    zmq_pub_port: int = 11100
    zmq_req_port: int = 11101
    
    # Risk
    max_daily_loss: float = 500.0
    max_trades_per_day: int = 10
    max_concurrent: int = 3
    risk_percent: float = 1.0
    
    # Trading
    default_symbols: list = ["XAUUSD", "EURUSD"]
    default_lots: float = 0.01
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()