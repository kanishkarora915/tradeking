"""
TRADEKING — Engine 08: Trap Fingerprint Detector ★ CORE ENGINE ★
Score range: -3 to +3 | Weight: 3.0x

THE PRIMARY EDGE. Detects retail traps where institutions lure and reverse.

A TRAP is CONFIRMED when ALL 5 conditions are met:
  1. Price breaks a key level on above-average volume (>150%)
  2. OI builds at broken strike AFTER breakout (not before)
  3. IV in direction of breakout FALLS (real moves = IV rising)
  4. FII futures positioning is OPPOSITE to breakout direction
  5. Price fails to sustain beyond broken level for 2+ candles (15-min)

BULL TRAP → STRONG PUT signal (score: -3)
BEAR TRAP → STRONG CALL signal (score: +3)
Partial trap (3/5 conditions) → score: ±2
"""
import logging
from datetime import datetime

from config import TRAP_MIN_CONDITIONS

logger = logging.getLogger(__name__)


class TrapFingerprintEngine:

    def check_condition_1_breakout(
        self,
        current_price: float,
        key_level: float,
        current_volume: int,
        avg_volume: int,
        direction: str,
    ) -> dict:
        """Condition 1: Price breaks key level on >150% average volume.

        Args:
            direction: 'UP' or 'DOWN' — which way price is breaking
        """
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        high_volume = volume_ratio > 1.5

        if direction == "UP":
            broke_level = current_price > key_level
        else:
            broke_level = current_price < key_level

        triggered = broke_level and high_volume

        return {
            "triggered": triggered,
            "volume_ratio": round(volume_ratio, 2),
            "key_level": key_level,
            "current_price": current_price,
            "direction": direction,
        }

    def check_condition_2_oi_post_breakout(
        self,
        oi_before_breakout: int,
        oi_after_breakout: int,
        broken_strike: float,
    ) -> dict:
        """Condition 2: OI builds at broken strike AFTER breakout — not before.
        If OI was already there before breakout, it's not a trap.
        Trap = new OI appearing AFTER the breakout (retail jumping in).
        """
        oi_increase = oi_after_breakout - oi_before_breakout
        oi_increase_pct = (oi_increase / max(oi_before_breakout, 1)) * 100

        # Significant new OI = more than 10% increase post-breakout
        triggered = oi_increase_pct > 10

        return {
            "triggered": triggered,
            "oi_before": oi_before_breakout,
            "oi_after": oi_after_breakout,
            "oi_increase_pct": round(oi_increase_pct, 2),
            "broken_strike": broken_strike,
        }

    def check_condition_3_iv_divergence(
        self,
        iv_at_breakout: float,
        iv_current: float,
        breakout_direction: str,
    ) -> dict:
        """Condition 3: If price breaking up but call IV FALLING = fake breakout.
        Real moves: IV rises because of genuine demand.
        Fake moves: IV falls because smart money is selling into the move.
        """
        iv_change = iv_current - iv_at_breakout
        iv_falling = iv_change < -0.5  # IV dropped by more than 0.5 points

        # For upside breakout: call IV should rise. If falling = trap.
        # For downside breakout: put IV should rise. If falling = trap.
        triggered = iv_falling

        return {
            "triggered": triggered,
            "iv_at_breakout": round(iv_at_breakout, 2),
            "iv_current": round(iv_current, 2),
            "iv_change": round(iv_change, 2),
            "breakout_direction": breakout_direction,
        }

    def check_condition_4_fii_opposition(
        self,
        breakout_direction: str,
        fii_net_futures: float,
    ) -> dict:
        """Condition 4: FII positioned OPPOSITE to breakout direction.
        If retail is buying the breakout up, but FII is net short = trap.
        """
        if breakout_direction == "UP":
            # Upside breakout but FII is short
            triggered = fii_net_futures < -10000
        else:
            # Downside breakout but FII is long
            triggered = fii_net_futures > 10000

        return {
            "triggered": triggered,
            "breakout_direction": breakout_direction,
            "fii_net_futures": fii_net_futures,
            "fii_stance": "LONG" if fii_net_futures > 0 else "SHORT",
        }

    def check_condition_5_no_sustain(
        self,
        candle_closes: list[float],
        broken_level: float,
        breakout_direction: str,
        candles_required: int = 2,
    ) -> dict:
        """Condition 5: Price returns below/above broken level within N candles.
        If price broke up but can't hold above for 2 x 15-min candles = failed breakout.
        """
        if len(candle_closes) < candles_required:
            return {"triggered": False, "reason": "insufficient_candles", "candles_checked": len(candle_closes)}

        recent = candle_closes[-candles_required:]

        if breakout_direction == "UP":
            # Check if price fell back below the broken level
            failed = all(c < broken_level for c in recent)
        else:
            # Check if price bounced back above the broken level
            failed = all(c > broken_level for c in recent)

        return {
            "triggered": failed,
            "recent_closes": [round(c, 2) for c in recent],
            "broken_level": broken_level,
            "breakout_direction": breakout_direction,
        }

    def run(
        self,
        index: str,
        current_price: float = 0,
        key_levels: list[float] | None = None,
        current_volume: int = 0,
        avg_volume: int = 0,
        oi_before: int = 0,
        oi_after: int = 0,
        iv_at_breakout: float = 0,
        iv_current: float = 0,
        fii_net_futures: float = 0,
        candle_closes: list[float] | None = None,
        breakout_direction: str = "",
        broken_level: float = 0,
    ) -> dict:
        """Run Trap Fingerprint Detection.

        Returns: {
            score: -3 to +3,
            trap_type: 'BULL_TRAP' | 'BEAR_TRAP' | None,
            conditions_met: [1,2,3,4,5],
            confidence: 'CONFIRMED' | 'PARTIAL' | None,
            trapped_level: float,
            signal: 'STRONG_PUT' | 'STRONG_CALL' | None
        }
        """
        try:
            if current_price == 0 or not breakout_direction:
                return {"score": 0, "trap_type": None, "conditions_met": [], "conditions_total": 0, "confidence": None, "trapped_level": 0, "signal": None, "breakout_direction": "", "condition_details": {}, "no_data": True}

            conditions_met = []
            condition_details = {}

            # Condition 1: Breakout on volume
            c1 = self.check_condition_1_breakout(
                current_price, broken_level or (key_levels[0] if key_levels else current_price),
                current_volume, avg_volume, breakout_direction
            )
            condition_details["c1_breakout"] = c1
            if c1["triggered"]:
                conditions_met.append(1)

            # Condition 2: OI post-breakout
            c2 = self.check_condition_2_oi_post_breakout(oi_before, oi_after, broken_level)
            condition_details["c2_oi_post_breakout"] = c2
            if c2["triggered"]:
                conditions_met.append(2)

            # Condition 3: IV divergence
            c3 = self.check_condition_3_iv_divergence(iv_at_breakout, iv_current, breakout_direction)
            condition_details["c3_iv_divergence"] = c3
            if c3["triggered"]:
                conditions_met.append(3)

            # Condition 4: FII opposition
            c4 = self.check_condition_4_fii_opposition(breakout_direction, fii_net_futures)
            condition_details["c4_fii_opposition"] = c4
            if c4["triggered"]:
                conditions_met.append(4)

            # Condition 5: No sustain
            c5 = self.check_condition_5_no_sustain(candle_closes or [], broken_level, breakout_direction)
            condition_details["c5_no_sustain"] = c5
            if c5["triggered"]:
                conditions_met.append(5)

            # Determine trap type and score
            num_conditions = len(conditions_met)

            if num_conditions >= 5:
                confidence = "CONFIRMED"
                if breakout_direction == "UP":
                    trap_type = "BULL_TRAP"
                    score = -3.0
                    signal = "STRONG_PUT"
                else:
                    trap_type = "BEAR_TRAP"
                    score = 3.0
                    signal = "STRONG_CALL"
            elif num_conditions >= TRAP_MIN_CONDITIONS:
                confidence = "PARTIAL"
                if breakout_direction == "UP":
                    trap_type = "BULL_TRAP"
                    score = -2.0
                    signal = "PUT"
                else:
                    trap_type = "BEAR_TRAP"
                    score = 2.0
                    signal = "CALL"
            else:
                confidence = None
                trap_type = None
                score = 0.0
                signal = None

            return {
                "score": score,
                "trap_type": trap_type,
                "conditions_met": conditions_met,
                "conditions_total": num_conditions,
                "confidence": confidence,
                "trapped_level": broken_level,
                "signal": signal,
                "breakout_direction": breakout_direction,
                "condition_details": condition_details,
            }
        except Exception as e:
            logger.error(f"Trap Engine error for {index}: {e}")
            return {
                "score": 0, "trap_type": None, "conditions_met": [],
                "confidence": None, "trapped_level": 0, "signal": None, "error": str(e),
            }

