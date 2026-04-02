"""
TRADEKING — Zerodha Kite Connect Auth Handler
Auto login: User clicks login → Zerodha → callback auto-captures token → session created.
"""
from kiteconnect import KiteConnect
from datetime import datetime
import logging
import os

from config import KITE_API_KEY, KITE_API_SECRET, KITE_ACCESS_TOKEN

logger = logging.getLogger(__name__)

_kite_instance: KiteConnect | None = None
_access_token: str = ""


def get_kite() -> KiteConnect:
    """Get or create a Kite Connect instance."""
    global _kite_instance, _access_token

    if _kite_instance and _access_token:
        return _kite_instance

    kite = KiteConnect(api_key=KITE_API_KEY)

    if KITE_ACCESS_TOKEN:
        kite.set_access_token(KITE_ACCESS_TOKEN)
        _kite_instance = kite
        _access_token = KITE_ACCESS_TOKEN
        logger.info("Kite initialized with env access token")
        return kite

    raise RuntimeError("Not logged in. Login via /api/auth/kite/login")


def get_login_url() -> str:
    """Get Kite login URL — redirects back to our callback automatically."""
    kite = KiteConnect(api_key=KITE_API_KEY)
    return kite.login_url()


def generate_session(request_token: str) -> dict:
    """Auto generate session from callback request_token."""
    global _kite_instance, _access_token

    kite = KiteConnect(api_key=KITE_API_KEY)
    data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
    access_token = data["access_token"]

    kite.set_access_token(access_token)
    _kite_instance = kite
    _access_token = access_token

    logger.info(f"Kite session created at {datetime.now()} for user {data.get('user_id', '')}")
    return {
        "access_token": access_token,
        "user_id": data.get("user_id", ""),
        "user_name": data.get("user_name", ""),
        "login_time": datetime.now().isoformat(),
    }


def is_authenticated() -> bool:
    """Check if we have a valid Kite session."""
    global _kite_instance
    if not _kite_instance:
        return False
    try:
        _kite_instance.profile()
        return True
    except Exception:
        return False


def get_options_chain(index: str, expiry: str | None = None) -> list[dict]:
    """Fetch full options chain for an index from Kite."""
    kite = get_kite()
    try:
        exchange = "BFO" if index == "SENSEX" else "NFO"
        instruments = kite.instruments(exchange)
        prefix = index.upper()
        options = [
            i for i in instruments
            if i["name"] == prefix
            and i["instrument_type"] in ("CE", "PE")
            and (not expiry or str(i["expiry"]) == expiry)
        ]

        if not options:
            logger.warning(f"No options found for {index}")
            return []

        trading_symbols = [f"{exchange}:{o['tradingsymbol']}" for o in options[:100]]
        quotes = kite.quote(trading_symbols)

        chain = []
        for opt in options[:100]:
            symbol = f"{exchange}:{opt['tradingsymbol']}"
            q = quotes.get(symbol, {})
            chain.append({
                "strike": opt["strike"],
                "type": opt["instrument_type"],
                "oi": q.get("oi", 0),
                "volume": q.get("volume", 0),
                "ltp": q.get("last_price", 0),
                "bid": q.get("depth", {}).get("buy", [{}])[0].get("price", 0),
                "ask": q.get("depth", {}).get("sell", [{}])[0].get("price", 0),
                "tradingsymbol": opt["tradingsymbol"],
                "expiry": str(opt["expiry"]),
            })
        return chain
    except Exception as e:
        logger.error(f"Error fetching options chain for {index}: {e}")
        return []


def get_spot_price(index: str) -> float:
    """Get current spot price for an index."""
    kite = get_kite()
    try:
        if index == "NIFTY":
            symbol = "NSE:NIFTY 50"
        elif index == "BANKNIFTY":
            symbol = "NSE:NIFTY BANK"
        elif index == "SENSEX":
            symbol = "BSE:SENSEX"
        else:
            return 0.0

        quote = kite.quote([symbol])
        return quote[symbol]["last_price"]
    except Exception as e:
        logger.error(f"Error fetching spot price for {index}: {e}")
        return 0.0


def get_futures_price(index: str) -> float:
    """Get current month futures price."""
    kite = get_kite()
    try:
        exchange = "BFO" if index == "SENSEX" else "NFO"
        instruments = kite.instruments(exchange)
        prefix = index.upper()
        futures = [
            i for i in instruments
            if i["name"] == prefix and i["instrument_type"] == "FUT"
        ]
        if not futures:
            return 0.0
        futures.sort(key=lambda x: x["expiry"])
        symbol = f"{exchange}:{futures[0]['tradingsymbol']}"
        quote = kite.quote([symbol])
        return quote[symbol]["last_price"]
    except Exception as e:
        logger.error(f"Error fetching futures price for {index}: {e}")
        return 0.0
