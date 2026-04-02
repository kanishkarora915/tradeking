"""
TRADEKING — Signal Output
Final CALL/PUT/WAIT decision with risk management overlay.
"""
import logging
from datetime import datetime
from config import TRADING_RULES, TOTAL_CAPITAL

logger = logging.getLogger(__name__)


def generate_signal_output(
    index: str,
    confluence: dict,
    spot_price: float,
    engine_scores: dict,
) -> dict:
    """Generate final trading signal with risk parameters.

    Applies hard-coded trading rules:
      - Min confluence ±5 to trade
      - Max 15% of capital per trade
      - 40% stop loss on premium
      - 2% daily loss limit
    """
    signal = confluence["signal"]
    score = confluence["normalized_score"]
    confidence = confluence["confidence"]

    # Check minimum confluence threshold
    tradeable = abs(score) >= TRADING_RULES["min_confluence_to_trade"]

    if not tradeable and signal != "WAIT":
        signal = "WAIT"
        confidence = "LOW"

    # Risk calculations
    max_risk_amount = TOTAL_CAPITAL * (TRADING_RULES["max_risk_per_trade_pct"] / 100)
    daily_loss_limit = TOTAL_CAPITAL * (TRADING_RULES["daily_loss_limit_pct"] / 100)
    stop_loss_pct = TRADING_RULES["stop_loss_premium_pct"]

    # Suggested position size based on risk
    # If buying options at premium X, max loss = 40% of X
    # So max premium spend = max_risk_amount / 0.4
    max_premium_spend = max_risk_amount / (stop_loss_pct / 100)

    # Extract key data from engines
    trap = engine_scores.get("engine_08_trap", {})
    iv_data = engine_scores.get("engine_04_iv_skew", {})
    liquidity = engine_scores.get("engine_05_liquidity_pool", {})
    macro = engine_scores.get("engine_07_macro", {})

    output = {
        "index": index,
        "timestamp": datetime.now().isoformat(),
        "signal": signal,
        "direction": "CALL" if score > 0 else "PUT" if score < 0 else "NEUTRAL",
        "score": score,
        "confidence": confidence,
        "tradeable": tradeable and signal != "WAIT",
        "spot_price": spot_price,

        # Risk management
        "risk": {
            "max_risk_amount": round(max_risk_amount, 0),
            "max_premium_spend": round(max_premium_spend, 0),
            "stop_loss_pct": stop_loss_pct,
            "daily_loss_limit": round(daily_loss_limit, 0),
        },

        # Key levels
        "levels": {
            "max_pain": liquidity.get("max_pain", 0),
            "call_wall": liquidity.get("call_wall", 0),
            "put_wall": liquidity.get("put_wall", 0),
            "trapped_level": trap.get("trapped_level", 0),
        },

        # Context
        "context": {
            "trap_active": trap.get("trap_type") is not None,
            "trap_type": trap.get("trap_type"),
            "ivr": iv_data.get("ivr", 0),
            "ivr_gate": confluence.get("ivr_gate", False),
            "expiry_gate": confluence.get("expiry_gate", False),
            "vix": macro.get("vix", 0),
            "fii_stance": engine_scores.get("engine_03_futures_basis", {}).get("fii_stance", "N/A"),
        },

        # Engine summary
        "engines": {
            "bullish": confluence["engines_bullish"],
            "bearish": confluence["engines_bearish"],
            "neutral": confluence["engines_neutral"],
            "top_reason": confluence["top_signal_reason"],
        },
    }

    return output
