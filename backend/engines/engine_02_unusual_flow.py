"""
TRADEKING — Engine 02: Unusual Options Flow Detector
Score range: -3 to +3

Detects:
  - OTM Volume Spikes (> 300% of 5-day average)
  - Block Trades (> threshold lots)
  - Ask-side buying (trade >= ask price)
  - Put/Call volume divergence at specific strikes
"""
import logging
from typing import Optional

from config import LOT_SIZES

logger = logging.getLogger(__name__)


class UnusualFlowEngine:
    BLOCK_TRADE_THRESHOLD = {
        "NIFTY": 500,
        "BANKNIFTY": 300,
        "SENSEX": 200,
    }
    OTM_VOLUME_SPIKE_MULTIPLIER = 3.0

    def detect_otm_spike(self, strike_data: dict, avg_volume: float) -> bool:
        """Detect if current volume at a strike is > 300% of average."""
        current_vol = strike_data.get("call_volume", 0) + strike_data.get("put_volume", 0)
        if avg_volume <= 0:
            return current_vol > 1000
        return current_vol > (avg_volume * self.OTM_VOLUME_SPIKE_MULTIPLIER)

    def detect_block_trade(self, volume: int, index: str) -> bool:
        """Detect if a trade qualifies as a block trade."""
        lot_size = LOT_SIZES.get(index, 25)
        lots = volume / lot_size if lot_size > 0 else 0
        threshold = self.BLOCK_TRADE_THRESHOLD.get(index, 500)
        return lots >= threshold

    def detect_ask_side_buying(self, trade_price: float, ask_price: float) -> bool:
        """Detect aggressive buying (trade at or above ask)."""
        return trade_price >= ask_price and ask_price > 0

    def run(self, index: str, chain_data: list[dict] | None = None, spot_price: float = 0, historical_avg: dict | None = None) -> dict:
        """Run unusual flow detection.

        Returns: {score, signals_active, block_trades, otm_spikes, direction}
        """
        try:
            if not chain_data:
                return {"score": 0, "signals_active": 0, "block_trades": [], "otm_spikes": [], "direction": "NO_DATA", "call_unusual_volume": 0, "put_unusual_volume": 0, "no_data": True}

            otm_spikes = []
            block_trades = []
            call_unusual_volume = 0
            put_unusual_volume = 0
            total_signals = 0

            for strike_data in chain_data:
                strike = strike_data.get("strike", 0)
                is_otm_call = strike > spot_price
                is_otm_put = strike < spot_price

                # Check OTM volume spikes
                avg_vol = (historical_avg or {}).get(strike, 500)
                if self.detect_otm_spike(strike_data, avg_vol):
                    otm_spikes.append({
                        "strike": strike,
                        "call_volume": strike_data.get("call_volume", 0),
                        "put_volume": strike_data.get("put_volume", 0),
                        "spike_ratio": (strike_data.get("call_volume", 0) + strike_data.get("put_volume", 0)) / max(avg_vol, 1),
                    })
                    if is_otm_call:
                        call_unusual_volume += strike_data.get("call_volume", 0)
                    if is_otm_put:
                        put_unusual_volume += strike_data.get("put_volume", 0)
                    total_signals += 1

                # Check block trades
                call_vol = strike_data.get("call_volume", 0)
                put_vol = strike_data.get("put_volume", 0)
                if self.detect_block_trade(call_vol, index):
                    block_trades.append({"strike": strike, "type": "CE", "volume": call_vol})
                    call_unusual_volume += call_vol
                    total_signals += 1
                if self.detect_block_trade(put_vol, index):
                    block_trades.append({"strike": strike, "type": "PE", "volume": put_vol})
                    put_unusual_volume += put_vol
                    total_signals += 1

                # Ask-side buying detection
                call_ltp = strike_data.get("call_ltp", 0)
                call_ask = strike_data.get("call_ask", 0)
                put_ltp = strike_data.get("put_ltp", 0)
                put_ask = strike_data.get("put_ask", 0)

                if self.detect_ask_side_buying(call_ltp, call_ask):
                    call_unusual_volume += call_vol
                if self.detect_ask_side_buying(put_ltp, put_ask):
                    put_unusual_volume += put_vol

            # Determine direction from unusual flow
            total_unusual = call_unusual_volume + put_unusual_volume
            if total_unusual == 0:
                direction = "NEUTRAL"
                score = 0.0
            elif call_unusual_volume > put_unusual_volume * 1.5:
                direction = "BULLISH"
                score = min(3.0, total_signals * 0.75)
            elif put_unusual_volume > call_unusual_volume * 1.5:
                direction = "BEARISH"
                score = max(-3.0, -total_signals * 0.75)
            else:
                direction = "MIXED"
                score = 0.0

            return {
                "score": round(score, 2),
                "signals_active": total_signals,
                "block_trades": block_trades[:5],
                "otm_spikes": otm_spikes[:5],
                "direction": direction,
                "call_unusual_volume": call_unusual_volume,
                "put_unusual_volume": put_unusual_volume,
            }
        except Exception as e:
            logger.error(f"Unusual Flow Engine error for {index}: {e}")
            return {"score": 0, "signals_active": 0, "block_trades": [], "otm_spikes": [], "direction": "NEUTRAL", "error": str(e)}

