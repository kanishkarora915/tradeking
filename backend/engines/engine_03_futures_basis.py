"""
TRADEKING — Engine 03: Futures Basis & Rollover Tracker
Score range: -2 to +2

Tracks:
  - Basis = Futures Price - Spot Price
  - 5-day rolling basis trend
  - FII net futures positioning
  - Rollover percentage in last 5 days of expiry
"""
import logging
from datetime import datetime, timedelta

from config import CURRENT_EXPIRY_DATE

logger = logging.getLogger(__name__)


class FuturesBasisEngine:
    FII_STRONG_LONG_THRESHOLD = 50000
    FII_STRONG_SHORT_THRESHOLD = -50000

    def calculate_basis(self, futures_price: float, spot_price: float) -> float:
        """Calculate futures basis (premium/discount)."""
        return futures_price - spot_price

    def basis_pct(self, futures_price: float, spot_price: float) -> float:
        """Basis as percentage of spot."""
        if spot_price == 0:
            return 0.0
        return ((futures_price - spot_price) / spot_price) * 100

    def interpret_basis_trend(self, basis_history: list[float]) -> dict:
        """Interpret 5-day basis trend.

        Expanding positive = bullish conviction (institutions adding longs)
        Collapsing positive = smart money exiting
        Expanding negative = bearish conviction
        Collapsing negative = shorts covering
        """
        if len(basis_history) < 2:
            return {"trend": "INSUFFICIENT_DATA", "direction": "NEUTRAL"}

        recent = basis_history[-1]
        older = basis_history[0]
        change = recent - older

        if recent > 0:
            if change > 0:
                return {"trend": "EXPANDING_PREMIUM", "direction": "BULLISH"}
            else:
                return {"trend": "COLLAPSING_PREMIUM", "direction": "BEARISH"}
        else:
            if change < 0:
                return {"trend": "EXPANDING_DISCOUNT", "direction": "BEARISH"}
            else:
                return {"trend": "COLLAPSING_DISCOUNT", "direction": "BULLISH"}

    def is_rollover_window(self) -> bool:
        """Check if we're in the last 5 days before expiry."""
        today = datetime.now().date()
        days_to_expiry = (CURRENT_EXPIRY_DATE - today).days
        return 0 <= days_to_expiry <= 5

    def calculate_rollover_pct(self, current_month_oi: int, next_month_oi: int) -> float:
        """Calculate rollover percentage."""
        total = current_month_oi + next_month_oi
        if total == 0:
            return 0.0
        return (next_month_oi / total) * 100

    def run(self, index: str, spot_price: float = 0, futures_price: float = 0, fii_net_futures: float = 0, basis_history: list[float] | None = None) -> dict:
        """Run futures basis analysis.

        Returns: {score, basis, basis_pct, trend, fii_stance, rollover_active, rollover_pct}
        """
        try:
            if spot_price == 0 or futures_price == 0:
                return {"score": 0, "basis": 0, "basis_pct": 0, "trend": "NO_DATA", "trend_direction": "NEUTRAL", "fii_stance": "NEUTRAL", "fii_net_futures": 0, "rollover_active": False, "rollover_pct": 0, "no_data": True}

            basis = self.calculate_basis(futures_price, spot_price)
            basis_pct_val = self.basis_pct(futures_price, spot_price)

            # Basis trend
            if basis_history and len(basis_history) >= 2:
                trend_info = self.interpret_basis_trend(basis_history)
            else:
                trend_info = {"trend": "NEUTRAL", "direction": "NEUTRAL"}

            # FII positioning score
            fii_score = 0.0
            fii_stance = "NEUTRAL"
            if fii_net_futures > self.FII_STRONG_LONG_THRESHOLD:
                fii_score = 1.0
                fii_stance = "STRONG_LONG"
            elif fii_net_futures > 20000:
                fii_score = 0.5
                fii_stance = "LONG"
            elif fii_net_futures < self.FII_STRONG_SHORT_THRESHOLD:
                fii_score = -1.0
                fii_stance = "STRONG_SHORT"
            elif fii_net_futures < -20000:
                fii_score = -0.5
                fii_stance = "SHORT"

            # Basis direction score
            basis_score = 0.0
            if trend_info["direction"] == "BULLISH":
                basis_score = 1.0
            elif trend_info["direction"] == "BEARISH":
                basis_score = -1.0

            # Combined score
            score = basis_score + fii_score
            score = max(-2.0, min(2.0, score))

            # Rollover info
            rollover_active = self.is_rollover_window()

            return {
                "score": round(score, 2),
                "basis": round(basis, 2),
                "basis_pct": round(basis_pct_val, 4),
                "trend": trend_info["trend"],
                "trend_direction": trend_info["direction"],
                "fii_stance": fii_stance,
                "fii_net_futures": fii_net_futures,
                "rollover_active": rollover_active,
                "rollover_pct": 0.0,
            }
        except Exception as e:
            logger.error(f"Futures Basis Engine error for {index}: {e}")
            return {"score": 0, "basis": 0, "basis_pct": 0, "trend": "ERROR", "fii_stance": "NEUTRAL", "error": str(e)}

