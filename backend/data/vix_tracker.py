"""
TRADEKING — India VIX Live Tracker
"""
import httpx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def fetch_india_vix() -> float:
    """Fetch current India VIX value from NSE."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/",
        }
        async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
            await client.get("https://www.nseindia.com")
            resp = await client.get("https://www.nseindia.com/api/allIndices")
            data = resp.json()

            for idx in data.get("data", []):
                if "VIX" in idx.get("index", "").upper():
                    return float(idx.get("last", 0))
        return 0.0
    except Exception as e:
        logger.error(f"Error fetching India VIX: {e}")
        return 0.0


def interpret_vix(vix: float, vix_change: float, market_change: float) -> dict:
    """Interpret VIX in context of market movement.

    Key rules:
    - VIX falling + market falling = FAKE selloff (bullish)
    - VIX rising + market rising = untrustworthy rally (bearish)
    - VIX < 14 = low fear, trending market
    - VIX > 20 = high fear, expensive options
    """
    interpretation = "NEUTRAL"
    score = 0.0

    if vix_change < 0 and market_change < 0:
        interpretation = "FAKE_SELLOFF"
        score = 1.0
    elif vix_change > 0 and market_change > 0:
        interpretation = "UNTRUSTWORTHY_RALLY"
        score = -1.0
    elif vix_change < 0 and market_change > 0:
        interpretation = "CONFIRMED_RALLY"
        score = 1.5
    elif vix_change > 0 and market_change < 0:
        interpretation = "CONFIRMED_SELLOFF"
        score = -1.5

    # Level-based adjustment
    level = "LOW" if vix < 14 else "HIGH" if vix > 20 else "NORMAL"

    return {
        "vix": vix,
        "vix_change": vix_change,
        "interpretation": interpretation,
        "level": level,
        "score": score,
    }
