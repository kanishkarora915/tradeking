"""
TRADEKING — Engine 04: IV Skew Monitor
Score range: -2 to +2, PLUS IVR Gate

Monitors:
  - IVR (IV Rank): (Current IV - 52W Low) / (52W High - 52W Low) * 100
  - Skew: Put IV - Call IV at same delta
  - Term Structure: Weekly IV / Monthly IV ratio
  - IVR GATE: Blocks all buy signals when IVR > 60
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class IVSkewEngine:
    IVR_BUY_THRESHOLD = 30
    IVR_AVOID_THRESHOLD = 60
    SKEW_BULL_SIGNAL = -5
    SKEW_BEAR_SIGNAL = 5

    def calculate_ivr(self, current_iv: float, iv_52w_high: float, iv_52w_low: float) -> float:
        """Calculate IV Rank (0-100 scale)."""
        if iv_52w_high == iv_52w_low:
            return 50.0
        ivr = (current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low) * 100
        return max(0.0, min(100.0, ivr))

    def ivr_gate(self, ivr: float) -> bool:
        """IVR Gate: if IVR > 60, override all signals to WAIT.
        This is a hard gate, not a score modifier.
        """
        return ivr > self.IVR_AVOID_THRESHOLD

    def calculate_skew(self, chain_data: list[dict], spot_price: float) -> float:
        """Calculate put-call IV skew at ATM strikes.
        Skew = Put IV - Call IV at same strike nearest to ATM.
        Negative skew = call IV higher = aggressive call buying (bullish).
        Positive skew = put IV higher = hedging demand (bearish).
        """
        if not chain_data:
            return 0.0

        closest_strike = None
        min_dist = float("inf")
        for s in chain_data:
            dist = abs(s.get("strike", 0) - spot_price)
            if dist < min_dist:
                min_dist = dist
                closest_strike = s

        if not closest_strike:
            return 0.0

        put_iv = closest_strike.get("put_iv", 0)
        call_iv = closest_strike.get("call_iv", 0)
        return put_iv - call_iv

    def calculate_term_structure(self, weekly_iv: float, monthly_iv: float) -> float:
        """Term structure ratio: Weekly IV / Monthly IV.
        > 1.0 = backwardation (near-term fear)
        < 1.0 = contango (normal)
        """
        if monthly_iv == 0:
            return 1.0
        return weekly_iv / monthly_iv

    def run(self, index: str, chain_data: list[dict] | None = None, spot_price: float = 0, iv_52w_high: float = 0, iv_52w_low: float = 0, current_iv: float = 0, weekly_iv: float = 0, monthly_iv: float = 0) -> dict:
        """Run IV Skew analysis.

        Returns: {score, ivr, skew, term_structure_ratio, gate_active}
        """
        try:
            if not chain_data and current_iv == 0:
                return {"score": 0, "ivr": 0, "current_iv": 0, "skew": 0, "term_structure_ratio": 1.0, "gate_active": False, "iv_level": "NO_DATA", "no_data": True}

            # Calculate IVR
            if current_iv > 0 and iv_52w_high > 0:
                ivr = self.calculate_ivr(current_iv, iv_52w_high, iv_52w_low)
            elif chain_data:
                atm_ivs = []
                for s in chain_data:
                    if abs(s.get("strike", 0) - spot_price) < 200:
                        avg_iv = (s.get("call_iv", 0) + s.get("put_iv", 0)) / 2
                        if avg_iv > 0:
                            atm_ivs.append(avg_iv)
                current_iv = sum(atm_ivs) / len(atm_ivs) if atm_ivs else 15.0
                ivr = self.calculate_ivr(current_iv, iv_52w_high or current_iv * 1.8, iv_52w_low or current_iv * 0.5)
            else:
                ivr = 50.0

            # Gate check
            gate_active = self.ivr_gate(ivr)

            # Skew
            skew = self.calculate_skew(chain_data or [], spot_price) if chain_data else 0.0

            # Term structure
            term_ratio = self.calculate_term_structure(weekly_iv or current_iv, monthly_iv or current_iv)

            # Score calculation
            score = 0.0

            # IVR component (-1 to +1)
            if ivr < self.IVR_BUY_THRESHOLD:
                score += 1.0  # Cheap options = favorable for buying
            elif ivr > self.IVR_AVOID_THRESHOLD:
                score -= 1.0  # Expensive options

            # Skew component (-1 to +1)
            if skew < self.SKEW_BULL_SIGNAL:
                score += 1.0  # Aggressive call buying
            elif skew > self.SKEW_BEAR_SIGNAL:
                score -= 1.0  # Heavy put hedging

            score = max(-2.0, min(2.0, score))

            return {
                "score": round(score, 2),
                "ivr": round(ivr, 1),
                "current_iv": round(current_iv, 2),
                "skew": round(skew, 2),
                "term_structure_ratio": round(term_ratio, 3),
                "gate_active": gate_active,
                "iv_level": "LOW" if ivr < 30 else "HIGH" if ivr > 60 else "NORMAL",
            }
        except Exception as e:
            logger.error(f"IV Skew Engine error for {index}: {e}")
            return {"score": 0, "ivr": 50, "skew": 0, "term_structure_ratio": 1.0, "gate_active": False, "error": str(e)}

