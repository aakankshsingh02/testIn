from pydantic import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    DB_URL: str = "sqlite:///trading.db"
    MIN_SIGNAL_STRENGTH: float = 0.7
    MAX_POSITION_SIZE: int = 100
    MARKET_OPEN_HOUR: int = 9
    MARKET_CLOSE_HOUR: int = 15
    SCAN_INTERVAL: int = 5  # seconds
    
    # Risk management
    MAX_DAILY_LOSS_PERCENT: float = 1.0
    MAX_POSITION_SIZE_PERCENT: float = 5.0
    
    # Groww credentials
    GROWW_EMAIL: str = os.getenv("GROWW_EMAIL", "")
    GROWW_PASSWORD: str = os.getenv("GROWW_PASSWORD", "")
    
    class Config:
        env_file = ".env"

settings = Settings()