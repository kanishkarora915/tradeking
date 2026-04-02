"""
TRADEKING Configuration — All settings from environment variables
"""
import os
from dotenv import load_dotenv
from datetime import date, datetime

load_dotenv()


# --- Kite Connect ---
KITE_API_KEY: str = os.getenv("KITE_API_KEY", "")
KITE_API_SECRET: str = os.getenv("KITE_API_SECRET", "")
KITE_ACCESS_TOKEN: str = os.getenv("KITE_ACCESS_TOKEN", "")

# --- Database ---
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///tradeking.db")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

# --- Telegram ---
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Trading Capital ---
TOTAL_CAPITAL: float = float(os.getenv("TOTAL_CAPITAL", "600000"))
MAX_RISK_PER_TRADE_PCT: float = float(os.getenv("MAX_RISK_PER_TRADE_PCT", "15"))
DAILY_LOSS_LIMIT_PCT: float = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "2"))

# --- Engine Settings ---
ENGINE_REFRESH_SECONDS: int = int(os.getenv("ENGINE_REFRESH_SECONDS", "300"))
OTM_SPIKE_MULTIPLIER: float = float(os.getenv("OTM_SPIKE_MULTIPLIER", "3.0"))
BLOCK_TRADE_NIFTY_LOTS: int = int(os.getenv("BLOCK_TRADE_NIFTY_LOTS", "500"))
IVR_GATE_THRESHOLD: float = float(os.getenv("IVR_GATE_THRESHOLD", "60"))
TRAP_MIN_CONDITIONS: int = int(os.getenv("TRAP_MIN_CONDITIONS", "3"))

# --- Expiry Calendar ---
_expiry_str = os.getenv("CURRENT_EXPIRY_DATE", "2026-04-03")
CURRENT_EXPIRY_DATE: date = datetime.strptime(_expiry_str, "%Y-%m-%d").date()

# --- Hard-coded Trading Rules (non-configurable) ---
TRADING_RULES = {
    "expiry_day_block": True,
    "stop_loss_premium_pct": 40,
    "ivr_gate_threshold": 60,
    "min_confluence_to_trade": 5.0,
    "daily_loss_limit_pct": 2,
    "max_risk_per_trade_pct": 15,
}

# --- Index Config ---
INDICES = ["NIFTY", "BANKNIFTY", "SENSEX"]

KITE_INSTRUMENT_TOKENS = {
    "NIFTY": 256265,
    "BANKNIFTY": 260105,
    "SENSEX": 265,
}

KITE_FUTURES_TOKENS = {
    "NIFTY": "NFO:NIFTY{expiry}FUT",
    "BANKNIFTY": "NFO:BANKNIFTY{expiry}FUT",
    "SENSEX": "BFO:SENSEX{expiry}FUT",
}

LOT_SIZES = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "SENSEX": 10,
}

STRIKE_INTERVALS = {
    "NIFTY": 50,
    "BANKNIFTY": 100,
    "SENSEX": 100,
}

# --- Market Hours ---
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30


def is_market_open() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
    market_close = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
    return market_open <= now <= market_close


def is_expiry_day() -> bool:
    return date.today() == CURRENT_EXPIRY_DATE
