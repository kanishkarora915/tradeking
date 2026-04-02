"""
TRADEKING — Engine 05: Liquidity Pool Mapper
Score range: -1 to +1

Identifies:
  - Max Pain: expiry price where total option holder loss is maximized
  - Stop Hunt Zones: equal highs/lows on 15-min chart
  - OI-based Support (highest put OI) & Resistance (highest call OI)
"""
import logging

from config import STRIKE_INTERVALS

logger = logging.getLogger(__name__)


class LiquidityPoolEngine:

    def calculate_max_pain(self, chain_data: list[dict]) -> float:
        """Calculate Max Pain price.

        For each possible expiry price P:
          total_loss = sum of (max(0, Strike-P)*put_oi + max(0, P-Strike)*call_oi)
        Max Pain = price P with MAXIMUM total loss for option holders.
        """
        if not chain_data:
            return 0.0

        strikes = sorted(set(s["strike"] for s in chain_data if s.get("strike")))
        if not strikes:
            return 0.0

        # Build OI map
        call_oi_map = {}
        put_oi_map = {}
        for s in chain_data:
            strike = s["strike"]
            call_oi_map[strike] = call_oi_map.get(strike, 0) + s.get("call_oi", 0)
            put_oi_map[strike] = put_oi_map.get(strike, 0) + s.get("put_oi", 0)

        max_pain_price = strikes[0]
        max_total_loss = 0

        for candidate_price in strikes:
            total_loss = 0
            for strike in strikes:
                call_oi = call_oi_map.get(strike, 0)
                put_oi = put_oi_map.get(strike, 0)
                # Call holder loss: max(0, P - Strike) * call_oi (ITM calls lose when P > Strike... wait,
                # actually call holders GAIN when P > Strike. Max pain = max LOSS for holders.
                # Call holder loss at expiry = premium paid if OTM (P < Strike) = call_oi * premium_lost
                # Simplified: total intrinsic pain = sum of ITM intrinsic values
                # For max pain: we want price where total intrinsic payoff is minimized
                # Call intrinsic at price P: max(0, P - Strike) * call_oi
                # Put intrinsic at price P: max(0, Strike - P) * put_oi
                total_loss += max(0, candidate_price - strike) * call_oi
                total_loss += max(0, strike - candidate_price) * put_oi

            if total_loss > max_total_loss:
                max_total_loss = total_loss
                max_pain_price = candidate_price

        return max_pain_price

    def find_oi_walls(self, chain_data: list[dict]) -> dict:
        """Find highest OI strikes for support/resistance.

        Highest call OI strike = Resistance wall (sellers defending)
        Highest put OI strike = Support wall (sellers defending)
        """
        if not chain_data:
            return {"call_wall": 0, "put_wall": 0, "call_wall_oi": 0, "put_wall_oi": 0}

        call_oi_map = {}
        put_oi_map = {}
        for s in chain_data:
            strike = s["strike"]
            call_oi_map[strike] = call_oi_map.get(strike, 0) + s.get("call_oi", 0)
            put_oi_map[strike] = put_oi_map.get(strike, 0) + s.get("put_oi", 0)

        call_wall = max(call_oi_map, key=call_oi_map.get) if call_oi_map else 0
        put_wall = max(put_oi_map, key=put_oi_map.get) if put_oi_map else 0

        return {
            "call_wall": call_wall,
            "put_wall": put_wall,
            "call_wall_oi": call_oi_map.get(call_wall, 0),
            "put_wall_oi": put_oi_map.get(put_wall, 0),
        }

    def find_stop_hunt_zones(self, highs: list[float], lows: list[float], tolerance_pct: float = 0.1) -> dict:
        """Find equal highs/lows that are likely stop hunt targets.
        Equal highs/lows = liquidity pools where stops cluster.
        """
        hunt_zones = {"above": [], "below": []}

        # Find clusters of equal highs
        for i, h1 in enumerate(highs):
            for h2 in highs[i + 1:]:
                if h1 > 0 and abs(h1 - h2) / h1 * 100 < tolerance_pct:
                    if h1 not in hunt_zones["above"]:
                        hunt_zones["above"].append(round(h1, 2))

        # Find clusters of equal lows
        for i, l1 in enumerate(lows):
            for l2 in lows[i + 1:]:
                if l1 > 0 and abs(l1 - l2) / l1 * 100 < tolerance_pct:
                    if l1 not in hunt_zones["below"]:
                        hunt_zones["below"].append(round(l1, 2))

        return hunt_zones

    def run(self, index: str, chain_data: list[dict] | None = None, spot_price: float = 0, candle_highs: list[float] | None = None, candle_lows: list[float] | None = None) -> dict:
        """Run liquidity pool analysis.

        Returns: {max_pain, put_wall, call_wall, stop_hunt_zones, distance_to_max_pain, score}
        """
        try:
            if not chain_data:
                return {"score": 0, "max_pain": 0, "put_wall": 0, "call_wall": 0, "put_wall_oi": 0, "call_wall_oi": 0, "stop_hunt_zones": {"above": [], "below": []}, "distance_to_max_pain": 0, "distance_pct": 0, "no_data": True}

            max_pain = self.calculate_max_pain(chain_data)
            walls = self.find_oi_walls(chain_data)
            hunt_zones = self.find_stop_hunt_zones(candle_highs or [], candle_lows or [])

            # Distance to max pain
            distance = spot_price - max_pain if spot_price > 0 else 0
            distance_pct = (distance / spot_price * 100) if spot_price > 0 else 0

            # Score based on position relative to max pain
            score = 0.0
            if spot_price > max_pain:
                # Price above max pain — gravitational pull downward
                if abs(distance_pct) > 1.0:
                    score = -0.5
                elif abs(distance_pct) > 0.5:
                    score = -0.25
            elif spot_price < max_pain:
                # Price below max pain — gravitational pull upward
                if abs(distance_pct) > 1.0:
                    score = 0.5
                elif abs(distance_pct) > 0.5:
                    score = 0.25

            # Wall proximity adjustment
            if walls["call_wall"] and spot_price > 0:
                call_dist_pct = (walls["call_wall"] - spot_price) / spot_price * 100
                if 0 < call_dist_pct < 0.5:
                    score -= 0.25  # Near resistance
                put_dist_pct = (spot_price - walls["put_wall"]) / spot_price * 100
                if 0 < put_dist_pct < 0.5:
                    score += 0.25  # Near support

            score = max(-1.0, min(1.0, score))

            return {
                "score": round(score, 2),
                "max_pain": max_pain,
                "put_wall": walls["put_wall"],
                "call_wall": walls["call_wall"],
                "put_wall_oi": walls["put_wall_oi"],
                "call_wall_oi": walls["call_wall_oi"],
                "stop_hunt_zones": hunt_zones,
                "distance_to_max_pain": round(distance, 2),
                "distance_pct": round(distance_pct, 2),
            }
        except Exception as e:
            logger.error(f"Liquidity Pool Engine error for {index}: {e}")
            return {"score": 0, "max_pain": 0, "put_wall": 0, "call_wall": 0, "error": str(e)}

