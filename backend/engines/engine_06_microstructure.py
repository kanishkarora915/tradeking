"""
TRADEKING — Engine 06: Microstructure Scanner
Score range: -1 to +1

Analyzes:
  - VWAP: volume-weighted average price
  - Buy Delta: trades at ask / total trades
  - Bid-ask spread monitoring
  - Iceberg order detection
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MicrostructureEngine:
    DELTA_BULL_THRESHOLD = 65
    DELTA_BEAR_THRESHOLD = 35
    SPREAD_ALERT_MULTIPLIER = 3

    def calculate_vwap(self, tick_data: list[dict]) -> float:
        """VWAP = sum(price * volume) / sum(volume) since 9:15 AM."""
        if not tick_data:
            return 0.0
        total_pv = sum(t.get("price", 0) * t.get("volume", 0) for t in tick_data)
        total_vol = sum(t.get("volume", 0) for t in tick_data)
        if total_vol == 0:
            return 0.0
        return total_pv / total_vol

    def calculate_buy_delta(self, tick_data: list[dict]) -> float:
        """Calculate buy-side delta percentage.
        Trades at or above ask = buy-side trades.
        """
        if not tick_data:
            return 50.0

        buy_trades = 0
        total_trades = len(tick_data)

        for tick in tick_data:
            trade_price = tick.get("price", 0)
            ask_price = tick.get("ask", 0)
            if ask_price > 0 and trade_price >= ask_price:
                buy_trades += 1

        if total_trades == 0:
            return 50.0
        return (buy_trades / total_trades) * 100

    def monitor_spread(self, bid: float, ask: float, avg_spread: float) -> dict:
        """Monitor bid-ask spread for unusual widening."""
        current_spread = ask - bid if ask > bid else 0
        spread_ratio = current_spread / avg_spread if avg_spread > 0 else 1.0

        alert = spread_ratio > self.SPREAD_ALERT_MULTIPLIER

        return {
            "current_spread": round(current_spread, 2),
            "avg_spread": round(avg_spread, 2),
            "spread_ratio": round(spread_ratio, 2),
            "alert": alert,
        }

    def detect_iceberg(self, recent_trades: list[dict], window_seconds: int = 120) -> list[dict]:
        """Detect iceberg orders: repeated large trades at same strike within window.
        Pattern: same size, same strike, repeated 3+ times within 2 minutes.
        """
        if not recent_trades:
            return []

        icebergs = []
        trade_groups: dict[str, list] = {}

        for trade in recent_trades:
            key = f"{trade.get('strike', 0)}_{trade.get('size', 0)}"
            if key not in trade_groups:
                trade_groups[key] = []
            trade_groups[key].append(trade)

        for key, trades in trade_groups.items():
            if len(trades) >= 3:
                timestamps = [t.get("timestamp", 0) for t in trades]
                if len(timestamps) >= 2:
                    time_span = max(timestamps) - min(timestamps)
                    if time_span <= window_seconds:
                        parts = key.split("_")
                        icebergs.append({
                            "strike": float(parts[0]) if parts[0] else 0,
                            "size": int(parts[1]) if len(parts) > 1 and parts[1] else 0,
                            "count": len(trades),
                            "time_span_seconds": time_span,
                        })

        return icebergs

    def run(self, index: str, tick_data: list[dict] | None = None, spot_price: float = 0, avg_spread: float = 0, recent_trades: list[dict] | None = None) -> dict:
        """Run microstructure analysis.

        Returns: {score, vwap, buy_delta, spread_info, icebergs, price_vs_vwap}
        """
        try:
            if not tick_data:
                return {"score": 0, "vwap": 0, "buy_delta": 50, "spread_info": {}, "icebergs": [], "price_vs_vwap": "NO_DATA", "no_data": True}

            vwap = self.calculate_vwap(tick_data)
            buy_delta = self.calculate_buy_delta(tick_data)

            # Spread monitoring
            latest = tick_data[-1] if tick_data else {}
            spread_info = self.monitor_spread(
                latest.get("bid", 0),
                latest.get("ask", 0),
                avg_spread or 1.0,
            )

            # Iceberg detection
            icebergs = self.detect_iceberg(recent_trades or [])

            # Score calculation
            score = 0.0

            # Buy delta component
            if buy_delta > self.DELTA_BULL_THRESHOLD:
                score += 0.5
            elif buy_delta < self.DELTA_BEAR_THRESHOLD:
                score -= 0.5

            # Price vs VWAP component
            if vwap > 0 and spot_price > 0:
                if spot_price > vwap:
                    score += 0.25  # Trading above VWAP = bullish
                else:
                    score -= 0.25  # Trading below VWAP = bearish

            # Iceberg detection: neutral signal (just info)
            # Spread alert: subtract if spread is too wide (illiquid)
            if spread_info["alert"]:
                score *= 0.5  # Reduce confidence on wide spreads

            score = max(-1.0, min(1.0, score))

            return {
                "score": round(score, 2),
                "vwap": round(vwap, 2),
                "buy_delta": round(buy_delta, 1),
                "spread_info": spread_info,
                "icebergs": icebergs[:3],
                "price_vs_vwap": "ABOVE" if spot_price > vwap else "BELOW" if spot_price < vwap else "AT",
            }
        except Exception as e:
            logger.error(f"Microstructure Engine error for {index}: {e}")
            return {"score": 0, "vwap": 0, "buy_delta": 50, "spread_info": {}, "icebergs": [], "error": str(e)}

