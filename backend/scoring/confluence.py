"""
TRADEKING — Confluence Score Aggregation
Combines all 8 engine scores into a final normalized signal.
"""
import logging
from config import TRADING_RULES, is_expiry_day

logger = logging.getLogger(__name__)

ENGINE_WEIGHTS = {
    "engine_01_oi_state": 1.5,
    "engine_02_unusual_flow": 2.0,
    "engine_03_futures_basis": 1.5,
    "engine_04_iv_skew": 1.0,
    "engine_05_liquidity_pool": 0.5,
    "engine_06_microstructure": 1.0,
    "engine_07_macro": 1.5,
    "engine_08_trap": 3.0,  # HIGHEST WEIGHT
}

# Max possible weighted score for normalization
_MAX_WEIGHTED = sum(
    abs(w) * {"engine_01_oi_state": 2, "engine_02_unusual_flow": 3, "engine_03_futures_basis": 2,
              "engine_04_iv_skew": 2, "engine_05_liquidity_pool": 1, "engine_06_microstructure": 1,
              "engine_07_macro": 2, "engine_08_trap": 3}.get(k, 2)
    for k, w in ENGINE_WEIGHTS.items()
)


def calculate_confluence(engine_scores: dict, ivr_gate_active: bool = False) -> dict:
    """Aggregate all 8 engine scores into final Confluence Score.

    Steps:
      1. Multiply each score by its weight
      2. Sum all weighted scores
      3. Normalize to -10 to +10 scale
      4. Apply IVR Gate: if active, force WAIT
      5. Apply Expiry Gate: if expiry day, force WAIT unless Engine 08 = ±3
      6. Determine signal and confidence

    Signal thresholds (normalized -10 to +10):
      > +5  = STRONG_CALL
      +3 to +5 = CALL
      -3 to +3 = WAIT
      -3 to -5 = PUT
      < -5  = STRONG_PUT
    """
    weighted_sum = 0.0
    engines_bullish = 0
    engines_bearish = 0
    top_score = 0.0
    top_engine = ""

    for engine_name, weight in ENGINE_WEIGHTS.items():
        result = engine_scores.get(engine_name, {})
        score = result.get("score", 0)
        weighted = score * weight
        weighted_sum += weighted

        if score > 0:
            engines_bullish += 1
        elif score < 0:
            engines_bearish += 1

        if abs(weighted) > abs(top_score):
            top_score = weighted
            top_engine = engine_name

    # Normalize to -10 to +10
    if _MAX_WEIGHTED > 0:
        normalized = (weighted_sum / _MAX_WEIGHTED) * 10
    else:
        normalized = 0.0
    normalized = max(-10.0, min(10.0, normalized))

    # Determine raw signal
    if normalized > 5:
        signal = "STRONG_CALL"
    elif normalized > 3:
        signal = "CALL"
    elif normalized < -5:
        signal = "STRONG_PUT"
    elif normalized < -3:
        signal = "PUT"
    else:
        signal = "WAIT"

    # Confidence
    active_engines = engines_bullish + engines_bearish
    if active_engines >= 6 and abs(normalized) > 5:
        confidence = "HIGH"
    elif active_engines >= 4 and abs(normalized) > 3:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    # Top signal reason
    trap_result = engine_scores.get("engine_08_trap", {})
    if trap_result.get("trap_type"):
        top_signal_reason = f"{trap_result['trap_type']} detected at {trap_result.get('trapped_level', 'N/A')}"
    elif top_engine:
        top_signal_reason = f"Top engine: {top_engine} (weighted score: {top_score:+.1f})"
    else:
        top_signal_reason = "No dominant signal"

    # --- GATES ---

    # IVR Gate: force WAIT if IV too expensive
    if ivr_gate_active:
        signal = "WAIT"
        top_signal_reason = "IVR GATE: IV too expensive — WAIT"
        confidence = "HIGH"  # High confidence in the WAIT

    # Expiry Gate: force WAIT on expiry unless Trap Engine confirmed
    expiry_gate = False
    if is_expiry_day() and TRADING_RULES["expiry_day_block"]:
        trap_score = engine_scores.get("engine_08_trap", {}).get("score", 0)
        if abs(trap_score) < 3:
            signal = "WAIT"
            top_signal_reason = "EXPIRY DAY: No trade unless confirmed trap"
            expiry_gate = True

    return {
        "raw_score": round(weighted_sum, 2),
        "normalized_score": round(normalized, 2),
        "signal": signal,
        "confidence": confidence,
        "engines_bullish": engines_bullish,
        "engines_bearish": engines_bearish,
        "engines_neutral": 8 - engines_bullish - engines_bearish,
        "top_signal_reason": top_signal_reason,
        "ivr_gate": ivr_gate_active,
        "expiry_gate": expiry_gate,
        "top_engine": top_engine,
        "weighted_sum": round(weighted_sum, 2),
    }
