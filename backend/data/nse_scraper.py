"""
TRADEKING — NSE Website Scraper
FII/DII data, participant-wise OI, bulk deals
"""
import httpx
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

NSE_BASE = "https://www.nseindia.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


async def _get_nse_session() -> httpx.AsyncClient:
    """Create an NSE session with cookies."""
    client = httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True)
    await client.get(NSE_BASE)
    return client


async def fetch_fii_dii_data() -> dict:
    """Fetch FII/DII cash market activity from NSE."""
    try:
        client = await _get_nse_session()
        resp = await client.get(f"{NSE_BASE}/api/fiidiiTradeReact")
        data = resp.json()
        await client.aclose()

        result = {
            "fii_buy": 0.0,
            "fii_sell": 0.0,
            "fii_net": 0.0,
            "dii_buy": 0.0,
            "dii_sell": 0.0,
            "dii_net": 0.0,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }

        for entry in data:
            category = entry.get("category", "")
            if "FII" in category or "FPI" in category:
                result["fii_buy"] = float(entry.get("buyValue", 0))
                result["fii_sell"] = float(entry.get("sellValue", 0))
                result["fii_net"] = result["fii_buy"] - result["fii_sell"]
            elif "DII" in category:
                result["dii_buy"] = float(entry.get("buyValue", 0))
                result["dii_sell"] = float(entry.get("sellValue", 0))
                result["dii_net"] = result["dii_buy"] - result["dii_sell"]

        return result
    except Exception as e:
        logger.error(f"Error fetching FII/DII data: {e}")
        return {
            "fii_buy": 0, "fii_sell": 0, "fii_net": 0,
            "dii_buy": 0, "dii_sell": 0, "dii_net": 0,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }


async def fetch_participant_oi() -> dict:
    """Fetch participant-wise open interest data (FII futures positions)."""
    try:
        client = await _get_nse_session()
        resp = await client.get(f"{NSE_BASE}/api/reports?archives=%5B%7B%22name%22%3A%22F%26O%20-%20Pair%20wise%20Open%20Interest%22%7D%5D")
        data = resp.json()
        await client.aclose()

        fii_long = 0
        fii_short = 0
        for entry in data:
            if "FII" in str(entry.get("clientType", "")):
                fii_long = int(entry.get("futIdxLong", 0))
                fii_short = int(entry.get("futIdxShort", 0))

        return {
            "fii_futures_long": fii_long,
            "fii_futures_short": fii_short,
            "fii_futures_net": fii_long - fii_short,
        }
    except Exception as e:
        logger.error(f"Error fetching participant OI: {e}")
        return {"fii_futures_long": 0, "fii_futures_short": 0, "fii_futures_net": 0}


async def fetch_option_chain_nse(index: str) -> list[dict]:
    """Fetch options chain directly from NSE (fallback if Kite unavailable)."""
    try:
        symbol = "NIFTY" if index == "NIFTY" else "BANKNIFTY" if index == "BANKNIFTY" else "SENSEX"
        client = await _get_nse_session()
        resp = await client.get(f"{NSE_BASE}/api/option-chain-indices?symbol={symbol}")
        data = resp.json()
        await client.aclose()

        records = data.get("records", {})
        spot = records.get("underlyingValue", 0)
        chain = []
        for row in records.get("data", []):
            strike = row.get("strikePrice", 0)
            ce = row.get("CE", {})
            pe = row.get("PE", {})
            chain.append({
                "strike": strike,
                "call_oi": ce.get("openInterest", 0),
                "put_oi": pe.get("openInterest", 0),
                "call_oi_change": ce.get("changeinOpenInterest", 0),
                "put_oi_change": pe.get("changeinOpenInterest", 0),
                "call_volume": ce.get("totalTradedVolume", 0),
                "put_volume": pe.get("totalTradedVolume", 0),
                "call_iv": ce.get("impliedVolatility", 0),
                "put_iv": pe.get("impliedVolatility", 0),
                "call_ltp": ce.get("lastPrice", 0),
                "put_ltp": pe.get("lastPrice", 0),
                "call_bid": ce.get("bidprice", 0),
                "call_ask": ce.get("askPrice", 0),
                "put_bid": pe.get("bidprice", 0),
                "put_ask": pe.get("askPrice", 0),
                "spot_price": spot,
            })
        return chain
    except Exception as e:
        logger.error(f"Error fetching NSE option chain for {index}: {e}")
        return []
