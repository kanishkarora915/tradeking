"""
TRADEKING — Engine 01: OI State Classifier
Score range: -2 to +2

Classifies market state based on price + OI changes:
  Price UP + OI UP = BULLISH (long building)
  Price UP + OI DOWN = SHORT_COVER (shorts exiting)
  Price DOWN + OI UP = BEARISH (short building)
  Price DOWN + OI DOWN = LONG_UNWIND (longs exiting)
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session

from database.db import get_db
from database.oi_history import get_oi_snapshot, get_oi_velocity
from config import STRIKE_INTERVALS

logger = logging.getLogger(__name__)


class OIStateEngine:
    WEIGHTS = {
        "BULLISH": 2.0,
        "SHORT_COVER": 1.0,
        "NEUTRAL": 0.0,
        "LONG_UNWIND": -1.0,
        "BEARISH": -2.0,
    }

    def classify_state(self, price_change_pct: float, oi_change_pct: float) -> str:
        """Classify OI state based on price and OI changes."""
        if abs(price_change_pct) < 0.05 and abs(oi_change_pct) < 1.0:
            return "NEUTRAL"

        if price_change_pct > 0:
            if oi_change_pct > 0:
                return "BULLISH"
            else:
                return "SHORT_COVER"
        else:
            if oi_change_pct > 0:
                return "BEARISH"
            else:
                return "LONG_UNWIND"

    def _get_atm_strikes(self, spot_price: float, index: str, spread: int = 2) -> list[float]:
        """Get ATM and nearby strikes."""
        interval = STRIKE_INTERVALS.get(index, 50)
        atm = round(spot_price / interval) * interval
        return [atm + i * interval for i in range(-spread, spread + 1)]

    def run(self, index: str, spot_price: float = 0, chain_data: list[dict] | None = None, price_change_pct: float = 0) -> dict:
        """Run OI State classification.

        Returns: {score, state, oi_velocity, dominant_strike, signal_strikes}
        """
        try:
            if not chain_data:
                return self._mock_result(index)

            atm_strikes = self._get_atm_strikes(spot_price, index)

            total_call_oi_change = 0
            total_put_oi_change = 0
            dominant_strike = spot_price
            max_oi_change = 0

            for strike_data in chain_data:
                strike = strike_data.get("strike", 0)
                if strike not in atm_strikes:
                    continue

                call_change = strike_data.get("call_oi_change", 0)
                put_change = strike_data.get("put_oi_change", 0)
                total_call_oi_change += call_change
                total_put_oi_change += put_change

                total_change = abs(call_change) + abs(put_change)
                if total_change > max_oi_change:
                    max_oi_change = total_change
                    dominant_strike = strike

            total_oi_change = total_call_oi_change + total_put_oi_change
            base_oi = max(abs(total_oi_change), 1)
            oi_change_pct = (total_oi_change / base_oi) * 100 if base_oi > 1 else 0

            state = self.classify_state(price_change_pct, oi_change_pct)
            score = self.WEIGHTS[state]

            # Apply velocity multiplier: strong moves get full weight
            velocity = abs(oi_change_pct)
            if velocity > 10:
                score *= 1.0
            elif velocity > 5:
                score *= 0.8
            else:
                score *= 0.5

            score = max(-2.0, min(2.0, score))

            return {
                "score": round(score, 2),
                "state": state,
                "oi_velocity": round(oi_change_pct, 2),
                "dominant_strike": dominant_strike,
                "signal_strikes": atm_strikes,
                "call_oi_change": total_call_oi_change,
                "put_oi_change": total_put_oi_change,
            }
        except Exception as e:
            logger.error(f"OI State Engine error for {index}: {e}")
            return {"score": 0, "state": "NEUTRAL", "oi_velocity": 0, "dominant_strike": 0, "signal_strikes": [], "error": str(e)}

    def _mock_result(self, index: str) -> dict:
        """Return mock data for development."""
        import random
        states = list(self.WEIGHTS.keys())
        state = random.choice(states)
        return {
            "score": self.WEIGHTS[state],
            "state": state,
            "oi_velocity": round(random.uniform(-15, 15), 2),
            "dominant_strike": {"NIFTY": 23450, "BANKNIFTY": 51200, "SENSEX": 77800}.get(index, 0),
            "signal_strikes": [],
            "call_oi_change": random.randint(-50000, 50000),
            "put_oi_change": random.randint(-50000, 50000),
        }
