"""
TRADEKING — Engine 07: Macro Sentiment Engine
Score range: -2 to +2

Monitors:
  - India VIX (live + interpretation)
  - FII Cash Market activity
  - GIFT Nifty pre-market reading
  - FII Futures Net Position (20-day rolling)
"""
import logging
from data.vix_tracker import interpret_vix

logger = logging.getLogger(__name__)


class MacroEngine:
    VIX_LOW = 14
    VIX_HIGH = 20
    FII_CASH_STRONG_BUY = 1000    # Crores
    FII_CASH_STRONG_SELL = -2000  # Crores

    def interpret_vix_level(self, current_vix: float) -> dict:
        """Interpret VIX level."""
        if current_vix < self.VIX_LOW:
            return {"level": "LOW", "meaning": "Low fear, trending market", "options_cost": "CHEAP"}
        elif current_vix > self.VIX_HIGH:
            return {"level": "HIGH", "meaning": "High fear, expensive options", "options_cost": "EXPENSIVE"}
        return {"level": "NORMAL", "meaning": "Normal volatility", "options_cost": "FAIR"}

    def get_gift_nifty_bias(self, gift_nifty: float, nifty_prev_close: float) -> dict:
        """Determine pre-market bias from GIFT Nifty."""
        if nifty_prev_close == 0:
            return {"bias": "NEUTRAL", "gap": 0, "gap_pct": 0}
        gap = gift_nifty - nifty_prev_close
        gap_pct = (gap / nifty_prev_close) * 100

        if gap > 50:
            bias = "BULLISH"
        elif gap < -50:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        return {"bias": bias, "gap": round(gap, 2), "gap_pct": round(gap_pct, 2)}

    def fii_cash_score(self, fii_net_crores: float) -> float:
        """Score FII cash market activity."""
        if fii_net_crores > self.FII_CASH_STRONG_BUY:
            return 1.0
        elif fii_net_crores > 0:
            return 0.5
        elif fii_net_crores > self.FII_CASH_STRONG_SELL:
            return -0.5
        else:
            return -1.0

    def run(self, index: str, vix: float = 0, vix_change: float = 0, market_change: float = 0, fii_cash_net: float = 0, gift_nifty: float = 0, nifty_prev_close: float = 0, fii_futures_net: float = 0) -> dict:
        """Run macro sentiment analysis.

        Returns: {score, vix_info, fii_cash_info, gift_nifty_info, fii_futures_net}
        """
        try:
            if vix == 0 and fii_cash_net == 0 and gift_nifty == 0:
                return self._mock_result(index)

            score = 0.0

            # VIX interpretation
            vix_info = interpret_vix(vix, vix_change, market_change)
            vix_level = self.interpret_vix_level(vix)
            score += vix_info["score"]

            # FII cash activity
            fii_score = self.fii_cash_score(fii_cash_net)
            score += fii_score * 0.5

            # GIFT Nifty bias (only relevant for NIFTY)
            gift_info = self.get_gift_nifty_bias(gift_nifty, nifty_prev_close)
            if gift_info["bias"] == "BULLISH":
                score += 0.5
            elif gift_info["bias"] == "BEARISH":
                score -= 0.5

            score = max(-2.0, min(2.0, score))

            return {
                "score": round(score, 2),
                "vix": vix,
                "vix_change": vix_change,
                "vix_interpretation": vix_info["interpretation"],
                "vix_level": vix_level["level"],
                "fii_cash_net": fii_cash_net,
                "fii_cash_direction": "BUY" if fii_cash_net > 0 else "SELL",
                "gift_nifty": gift_nifty,
                "gift_nifty_bias": gift_info["bias"],
                "gift_nifty_gap": gift_info["gap"],
                "fii_futures_net": fii_futures_net,
            }
        except Exception as e:
            logger.error(f"Macro Engine error for {index}: {e}")
            return {"score": 0, "vix": 0, "error": str(e)}

    def _mock_result(self, index: str) -> dict:
        import random
        vix = round(random.uniform(11, 22), 2)
        return {
            "score": round(random.uniform(-2, 2), 2),
            "vix": vix,
            "vix_change": round(random.uniform(-2, 2), 2),
            "vix_interpretation": random.choice(["CONFIRMED_RALLY", "FAKE_SELLOFF", "NEUTRAL"]),
            "vix_level": "LOW" if vix < 14 else "HIGH" if vix > 20 else "NORMAL",
            "fii_cash_net": round(random.uniform(-3000, 3000), 2),
            "fii_cash_direction": random.choice(["BUY", "SELL"]),
            "gift_nifty": 23500 + random.uniform(-100, 100),
            "gift_nifty_bias": random.choice(["BULLISH", "BEARISH", "NEUTRAL"]),
            "gift_nifty_gap": round(random.uniform(-80, 80), 2),
            "fii_futures_net": random.randint(-60000, 60000),
        }
