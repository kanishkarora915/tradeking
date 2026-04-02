"""
TRADEKING — WebSocket Data Manager
Manages Kite Connect ticker for live market data
"""
from kiteconnect import KiteTicker
from datetime import datetime
from typing import Callable
import logging
import json

from config import KITE_API_KEY, KITE_INSTRUMENT_TOKENS

logger = logging.getLogger(__name__)


class DataFeedManager:
    """Manages real-time data feed from Kite Connect WebSocket."""

    def __init__(self) -> None:
        self.ticker: KiteTicker | None = None
        self.latest_ticks: dict[int, dict] = {}
        self.callbacks: list[Callable] = []
        self.connected = False

    def start(self, access_token: str) -> None:
        """Start the Kite ticker WebSocket connection."""
        self.ticker = KiteTicker(KITE_API_KEY, access_token)

        self.ticker.on_ticks = self._on_ticks
        self.ticker.on_connect = self._on_connect
        self.ticker.on_close = self._on_close
        self.ticker.on_error = self._on_error

        tokens = list(KITE_INSTRUMENT_TOKENS.values())
        self.ticker.connect(threaded=True)
        logger.info("Kite ticker started")

    def _on_connect(self, ws, response) -> None:
        tokens = list(KITE_INSTRUMENT_TOKENS.values())
        ws.subscribe(tokens)
        ws.set_mode(ws.MODE_FULL, tokens)
        self.connected = True
        logger.info(f"Kite ticker connected, subscribed to {len(tokens)} tokens")

    def _on_ticks(self, ws, ticks: list) -> None:
        for tick in ticks:
            token = tick.get("instrument_token")
            if token:
                self.latest_ticks[token] = {
                    "last_price": tick.get("last_price", 0),
                    "volume": tick.get("volume_traded", 0),
                    "oi": tick.get("oi", 0),
                    "high": tick.get("ohlc", {}).get("high", 0),
                    "low": tick.get("ohlc", {}).get("low", 0),
                    "open": tick.get("ohlc", {}).get("open", 0),
                    "close": tick.get("ohlc", {}).get("close", 0),
                    "change_pct": tick.get("change", 0),
                    "buy_depth": tick.get("depth", {}).get("buy", []),
                    "sell_depth": tick.get("depth", {}).get("sell", []),
                    "timestamp": datetime.now().isoformat(),
                }
        for cb in self.callbacks:
            try:
                cb(self.latest_ticks)
            except Exception as e:
                logger.error(f"Tick callback error: {e}")

    def _on_close(self, ws, code, reason) -> None:
        self.connected = False
        logger.warning(f"Kite ticker closed: {code} - {reason}")

    def _on_error(self, ws, code, reason) -> None:
        logger.error(f"Kite ticker error: {code} - {reason}")

    def on_tick(self, callback: Callable) -> None:
        """Register a callback for tick updates."""
        self.callbacks.append(callback)

    def get_latest(self, index: str) -> dict:
        """Get latest tick data for an index."""
        token = KITE_INSTRUMENT_TOKENS.get(index)
        if token and token in self.latest_ticks:
            return self.latest_ticks[token]
        return {}

    def stop(self) -> None:
        if self.ticker:
            self.ticker.close()
            self.connected = False


# Global singleton
data_feed = DataFeedManager()
