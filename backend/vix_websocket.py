"""
TRADEKING — VIX WebSocket Engine
Real-time India VIX streaming via Kite WebSocket + price action trade signals.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from kiteconnect import KiteTicker

from config import KITE_API_KEY

logger = logging.getLogger(__name__)

# VIX instrument token on NSE
VIX_TOKEN = 264969

# Connected VIX WebSocket clients
vix_clients: set[WebSocket] = set()

# Latest cached VIX data
latest_vix: dict = {"vix": 0.0, "timestamp": "", "high": 0.0, "low": 999.0, "open": 0.0, "prev_close": 0.0, "change_pct": 0.0}

# Price action history for trade signals
vix_history: list[float] = []
MAX_HISTORY = 300  # 5 min of 1s ticks

# Index price cache for trade signals
index_prices: dict = {}

# Nifty/BankNifty tokens for price tracking
INDEX_TOKENS = {
    256265: "NIFTY",
    260105: "BANKNIFTY",
}


def start_vix_ticker(access_token: str) -> None:
    """Start Kite WebSocket ticker for VIX + index prices."""
    try:
        ticker = KiteTicker(KITE_API_KEY, access_token)

        def on_connect(ws, response):
            tokens = [VIX_TOKEN] + list(INDEX_TOKENS.keys())
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_FULL, tokens)
            logger.info(f"VIX ticker connected, subscribed to {len(tokens)} tokens")

        def on_ticks(ws, ticks):
            for tick in ticks:
                token = tick.get("instrument_token")
                if token == VIX_TOKEN:
                    _process_vix_tick(tick)
                elif token in INDEX_TOKENS:
                    _process_index_tick(token, tick)

        def on_close(ws, code, reason):
            logger.warning(f"VIX ticker closed: {code} — {reason}")

        def on_error(ws, code, reason):
            logger.error(f"VIX ticker error: {code} — {reason}")

        ticker.on_connect = on_connect
        ticker.on_ticks = on_ticks
        ticker.on_close = on_close
        ticker.on_error = on_error
        ticker.connect(threaded=True)
        logger.info("VIX ticker started")
    except Exception as e:
        logger.error(f"Failed to start VIX ticker: {e}")


def _process_vix_tick(tick: dict) -> None:
    """Process incoming VIX tick."""
    global latest_vix
    vix_value = tick.get("last_price", 0)
    if vix_value <= 0:
        return

    ohlc = tick.get("ohlc", {})
    prev_close = ohlc.get("close", 0)
    change_pct = ((vix_value - prev_close) / prev_close * 100) if prev_close > 0 else 0

    latest_vix = {
        "vix": round(vix_value, 2),
        "timestamp": datetime.now().isoformat(),
        "high": round(max(ohlc.get("high", vix_value), vix_value), 2),
        "low": round(min(ohlc.get("low", vix_value), vix_value), 2),
        "open": round(ohlc.get("open", vix_value), 2),
        "prev_close": round(prev_close, 2),
        "change_pct": round(change_pct, 2),
    }

    # Store history
    vix_history.append(vix_value)
    if len(vix_history) > MAX_HISTORY:
        vix_history.pop(0)

    # Broadcast to all connected clients
    asyncio.get_event_loop().call_soon_threadsafe(
        asyncio.ensure_future, _broadcast_vix()
    )


def _process_index_tick(token: int, tick: dict) -> None:
    """Process index price tick for trade signal engine."""
    index_name = INDEX_TOKENS.get(token, "")
    if not index_name:
        return

    ohlc = tick.get("ohlc", {})
    prev_close = ohlc.get("close", 0)
    last_price = tick.get("last_price", 0)
    change_pct = ((last_price - prev_close) / prev_close * 100) if prev_close > 0 else 0

    if index_name not in index_prices:
        index_prices[index_name] = {"history": [], "trades": []}

    entry = {
        "price": last_price,
        "volume": tick.get("volume_traded", 0),
        "oi": tick.get("oi", 0),
        "high": ohlc.get("high", last_price),
        "low": ohlc.get("low", last_price),
        "open": ohlc.get("open", last_price),
        "prev_close": prev_close,
        "change_pct": round(change_pct, 2),
        "timestamp": datetime.now().isoformat(),
    }

    index_prices[index_name]["latest"] = entry
    index_prices[index_name]["history"].append(last_price)
    if len(index_prices[index_name]["history"]) > MAX_HISTORY:
        index_prices[index_name]["history"].pop(0)


async def _broadcast_vix() -> None:
    """Broadcast VIX data + trade signals to all connected clients."""
    if not vix_clients:
        return

    # Compute trade signals
    trade_signals = compute_trade_signals()

    message = json.dumps({
        "type": "vix_update",
        "vix": latest_vix,
        "trade_signals": trade_signals,
        "index_prices": {k: v.get("latest", {}) for k, v in index_prices.items()},
    })

    disconnected = set()
    for ws in vix_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    vix_clients -= disconnected


def compute_trade_signals() -> list[dict]:
    """Compute live trade signals based on VIX + price action + imbalance."""
    signals = []
    vix = latest_vix.get("vix", 0)
    if vix == 0:
        return signals

    for index_name, data in index_prices.items():
        latest = data.get("latest", {})
        history = data.get("history", [])
        price = latest.get("price", 0)
        prev_close = latest.get("prev_close", 0)
        change_pct = latest.get("change_pct", 0)

        if price == 0 or len(history) < 10:
            continue

        # --- Price Action Analysis ---
        recent_5 = history[-5:]
        recent_20 = history[-20:] if len(history) >= 20 else history

        # Trend: compare current vs 20-bar avg
        avg_20 = sum(recent_20) / len(recent_20)
        trend = "UP" if price > avg_20 else "DOWN"

        # Momentum: rate of change over last 5 ticks
        roc = ((price - recent_5[0]) / recent_5[0] * 100) if recent_5[0] > 0 else 0

        # Micro trend: are last 3 candles rising or falling?
        last_3 = history[-3:]
        micro_up = all(last_3[i] >= last_3[i-1] for i in range(1, len(last_3)))
        micro_down = all(last_3[i] <= last_3[i-1] for i in range(1, len(last_3)))

        # Volatility: range of last 20 ticks vs avg
        if len(recent_20) > 1:
            vol_range = max(recent_20) - min(recent_20)
            avg_range = sum(abs(recent_20[i] - recent_20[i-1]) for i in range(1, len(recent_20))) / (len(recent_20) - 1)
        else:
            vol_range = 0
            avg_range = 0

        # --- VIX + Price Imbalance Detection ---
        # VIX rising + market falling = put signal (real fear)
        # VIX rising + market rising = suspicious rally, potential reversal
        # VIX falling + market falling = fake selloff, potential bounce
        # VIX falling + market rising = confirmed rally

        vix_roc = 0
        if len(vix_history) >= 5:
            vix_5_ago = vix_history[-5]
            vix_roc = ((vix - vix_5_ago) / vix_5_ago * 100) if vix_5_ago > 0 else 0

        vix_rising = vix_roc > 0.3
        vix_falling = vix_roc < -0.3
        market_rising = roc > 0.05
        market_falling = roc < -0.05

        # --- Signal Generation ---
        signal = None

        # STRONG PUT: VIX rising + market falling + VIX > 18
        if vix_rising and market_falling and vix > 18 and micro_down:
            atm = _round_strike(price, index_name)
            entry_strike = atm
            signal = {
                "index": index_name,
                "direction": "BUY PUT",
                "strike": entry_strike,
                "entry": round(price, 2),
                "stoploss": round(price + vol_range * 0.5, 2),
                "target": round(price - vol_range * 1.2, 2),
                "confidence": "HIGH" if vix > 22 else "MEDIUM",
                "reason": f"VIX rising ({vix_roc:+.2f}%) + {index_name} falling ({roc:+.2f}%) — real fear",
                "vix": vix,
                "vix_roc": round(vix_roc, 2),
                "price_roc": round(roc, 2),
                "timestamp": datetime.now().isoformat(),
            }

        # STRONG CALL: VIX falling + market rising + micro trend up
        elif vix_falling and market_rising and micro_up and vix < 22:
            atm = _round_strike(price, index_name)
            entry_strike = atm
            signal = {
                "index": index_name,
                "direction": "BUY CALL",
                "strike": entry_strike,
                "entry": round(price, 2),
                "stoploss": round(price - vol_range * 0.5, 2),
                "target": round(price + vol_range * 1.2, 2),
                "confidence": "HIGH" if vix < 16 else "MEDIUM",
                "reason": f"VIX falling ({vix_roc:+.2f}%) + {index_name} rising ({roc:+.2f}%) — confirmed rally",
                "vix": vix,
                "vix_roc": round(vix_roc, 2),
                "price_roc": round(roc, 2),
                "timestamp": datetime.now().isoformat(),
            }

        # REVERSAL PUT: VIX rising + market rising = suspicious, potential top
        elif vix_rising and market_rising and vix > 16 and abs(vix_roc) > 0.5:
            atm = _round_strike(price, index_name)
            signal = {
                "index": index_name,
                "direction": "BUY PUT",
                "strike": atm,
                "entry": round(price, 2),
                "stoploss": round(price + vol_range * 0.4, 2),
                "target": round(price - vol_range * 0.8, 2),
                "confidence": "LOW",
                "reason": f"VIX rising ({vix_roc:+.2f}%) INTO rally — suspicious, potential reversal",
                "vix": vix,
                "vix_roc": round(vix_roc, 2),
                "price_roc": round(roc, 2),
                "timestamp": datetime.now().isoformat(),
            }

        # BOUNCE CALL: VIX falling + market falling = fake selloff
        elif vix_falling and market_falling and abs(vix_roc) > 0.5 and vix < 20:
            atm = _round_strike(price, index_name)
            signal = {
                "index": index_name,
                "direction": "BUY CALL",
                "strike": atm,
                "entry": round(price, 2),
                "stoploss": round(price - vol_range * 0.4, 2),
                "target": round(price + vol_range * 0.8, 2),
                "confidence": "LOW",
                "reason": f"VIX falling ({vix_roc:+.2f}%) into selloff — fake drop, potential bounce",
                "vix": vix,
                "vix_roc": round(vix_roc, 2),
                "price_roc": round(roc, 2),
                "timestamp": datetime.now().isoformat(),
            }

        if signal:
            signals.append(signal)

    return signals


def _round_strike(price: float, index: str) -> float:
    """Round price to nearest strike."""
    interval = 50 if index == "NIFTY" else 100
    return round(price / interval) * interval


def get_latest_vix() -> dict:
    """REST fallback for VIX data."""
    return {
        **latest_vix,
        "trade_signals": compute_trade_signals(),
        "index_prices": {k: v.get("latest", {}) for k, v in index_prices.items()},
    }
