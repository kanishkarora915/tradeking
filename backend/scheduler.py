"""
TRADEKING — Engine Scheduler
Fetches REAL data from Kite Connect + NSE, feeds to all 8 engines every 5 minutes.
"""
import logging
import traceback
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import ENGINE_REFRESH_SECONDS, INDICES, STRIKE_INTERVALS, LOT_SIZES
from engines.engine_01_oi_state import OIStateEngine
from engines.engine_02_unusual_flow import UnusualFlowEngine
from engines.engine_03_futures_basis import FuturesBasisEngine
from engines.engine_04_iv_skew import IVSkewEngine
from engines.engine_05_liquidity_pool import LiquidityPoolEngine
from engines.engine_06_microstructure import MicrostructureEngine
from engines.engine_07_macro import MacroEngine
from engines.engine_08_trap import TrapFingerprintEngine
from scoring.confluence import calculate_confluence
from scoring.signal_output import generate_signal_output
from database.db import get_db
from database.oi_history import save_signal

logger = logging.getLogger(__name__)

# Global state
latest_signals: dict[str, dict] = {}
latest_engine_scores: dict[str, dict] = {}
latest_chain_data: dict[str, list] = {}  # For OI heatmap API


def _fetch_kite_data(index: str) -> dict:
    """Fetch ALL market data from Kite for an index."""
    from kite_auth import is_authenticated

    data = {
        "spot_price": 0.0,
        "prev_close": 0.0,
        "futures_price": 0.0,
        "chain_data": [],
        "price_change_pct": 0.0,
        "authenticated": False,
    }

    if not is_authenticated():
        logger.warning(f"Kite not authenticated — skipping {index}")
        return data

    data["authenticated"] = True

    try:
        from kite_auth import get_kite
        kite = get_kite()

        # --- SPOT PRICE ---
        spot_symbols = {
            "NIFTY": "NSE:NIFTY 50",
            "BANKNIFTY": "NSE:NIFTY BANK",
            "SENSEX": "BSE:SENSEX",
        }
        symbol = spot_symbols.get(index)
        if symbol:
            quote = kite.quote([symbol])
            q = quote.get(symbol, {})
            data["spot_price"] = q.get("last_price", 0)
            data["prev_close"] = q.get("ohlc", {}).get("close", 0)
            if data["prev_close"] > 0:
                data["price_change_pct"] = ((data["spot_price"] - data["prev_close"]) / data["prev_close"]) * 100
            logger.info(f"{index} spot: {data['spot_price']}, prev_close: {data['prev_close']}, change: {data['price_change_pct']:.2f}%")

        # --- FUTURES PRICE ---
        exchange = "BFO" if index == "SENSEX" else "NFO"
        try:
            instruments = kite.instruments(exchange)
            futures = [i for i in instruments if i["name"] == index and i["instrument_type"] == "FUT"]
            futures.sort(key=lambda x: x["expiry"])
            if futures:
                fut_symbol = f"{exchange}:{futures[0]['tradingsymbol']}"
                fut_quote = kite.quote([fut_symbol])
                data["futures_price"] = fut_quote.get(fut_symbol, {}).get("last_price", 0)
                logger.info(f"{index} futures: {data['futures_price']}")
        except Exception as e:
            logger.error(f"{index} futures fetch error: {e}")

        # --- OPTIONS CHAIN ---
        try:
            all_instruments = kite.instruments(exchange)
            options = [
                i for i in all_instruments
                if i["name"] == index and i["instrument_type"] in ("CE", "PE")
            ]
            # Sort by expiry, take nearest
            options.sort(key=lambda x: x["expiry"])
            if options:
                nearest_expiry = options[0]["expiry"]
                options = [o for o in options if o["expiry"] == nearest_expiry]

            # Filter strikes around ATM (±10 strikes)
            spot = data["spot_price"]
            interval = STRIKE_INTERVALS.get(index, 50)
            if spot > 0:
                atm = round(spot / interval) * interval
                min_strike = atm - 10 * interval
                max_strike = atm + 10 * interval
                options = [o for o in options if min_strike <= o["strike"] <= max_strike]

            if options:
                # Fetch quotes in batches of 50
                chain_map = {}
                for i in range(0, len(options), 50):
                    batch = options[i:i+50]
                    symbols = [f"{exchange}:{o['tradingsymbol']}" for o in batch]
                    try:
                        quotes = kite.quote(symbols)
                        for opt in batch:
                            sym = f"{exchange}:{opt['tradingsymbol']}"
                            q = quotes.get(sym, {})
                            strike = opt["strike"]
                            if strike not in chain_map:
                                chain_map[strike] = {
                                    "strike": strike,
                                    "call_oi": 0, "put_oi": 0,
                                    "call_oi_change": 0, "put_oi_change": 0,
                                    "call_volume": 0, "put_volume": 0,
                                    "call_iv": 0, "put_iv": 0,
                                    "call_ltp": 0, "put_ltp": 0,
                                    "call_bid": 0, "call_ask": 0,
                                    "put_bid": 0, "put_ask": 0,
                                }
                            row = chain_map[strike]
                            depth = q.get("depth", {})
                            buy_depth = depth.get("buy", [{}])
                            sell_depth = depth.get("sell", [{}])
                            bid = buy_depth[0].get("price", 0) if buy_depth else 0
                            ask = sell_depth[0].get("price", 0) if sell_depth else 0

                            if opt["instrument_type"] == "CE":
                                row["call_oi"] = q.get("oi", 0)
                                row["call_oi_change"] = q.get("oi_day_high", 0) - q.get("oi_day_low", 0)  # approx
                                row["call_volume"] = q.get("volume", 0)
                                row["call_ltp"] = q.get("last_price", 0)
                                row["call_bid"] = bid
                                row["call_ask"] = ask
                            else:
                                row["put_oi"] = q.get("oi", 0)
                                row["put_oi_change"] = q.get("oi_day_high", 0) - q.get("oi_day_low", 0)
                                row["put_volume"] = q.get("volume", 0)
                                row["put_ltp"] = q.get("last_price", 0)
                                row["put_bid"] = bid
                                row["put_ask"] = ask
                    except Exception as e:
                        logger.error(f"{index} chain batch error: {e}")

                data["chain_data"] = sorted(chain_map.values(), key=lambda x: x["strike"])
                logger.info(f"{index} chain: {len(data['chain_data'])} strikes loaded from Kite")
            else:
                logger.warning(f"{index}: no options found in {exchange}")
        except Exception as e:
            logger.error(f"{index} chain fetch error: {e}\n{traceback.format_exc()}")

    except Exception as e:
        logger.error(f"Kite data fetch failed for {index}: {e}\n{traceback.format_exc()}")

    return data


async def _fetch_macro_data() -> dict:
    """Fetch macro data from NSE."""
    macro = {
        "vix": 0.0, "vix_change": 0.0,
        "fii_cash_net": 0.0, "gift_nifty": 0.0,
        "nifty_prev_close": 0.0, "fii_futures_net": 0.0,
        "market_change": 0.0,
    }
    try:
        from data.vix_tracker import fetch_india_vix
        macro["vix"] = await fetch_india_vix()
    except Exception as e:
        logger.error(f"VIX fetch error: {e}")

    try:
        from data.nse_scraper import fetch_fii_dii_data
        fii = await fetch_fii_dii_data()
        macro["fii_cash_net"] = fii.get("fii_net", 0)
    except Exception as e:
        logger.error(f"FII/DII fetch error: {e}")

    try:
        from data.nse_scraper import fetch_participant_oi
        p = await fetch_participant_oi()
        macro["fii_futures_net"] = p.get("fii_futures_net", 0)
    except Exception as e:
        logger.error(f"Participant OI fetch error: {e}")

    return macro


def _compute_trade_signal(index: str, confluence: dict, spot: float, chain: list, engine_scores: dict) -> dict:
    """Compute trade entry, stoploss, exit from signal + options chain."""
    signal = confluence.get("signal", "WAIT")
    score = confluence.get("normalized_score", 0)

    trade = {
        "tradeable": False,
        "direction": None,
        "entry_strike": 0,
        "entry_premium": 0.0,
        "stoploss_premium": 0.0,
        "target_premium": 0.0,
        "stoploss_pct": 40,
        "risk_reward": 0.0,
        "lot_size": LOT_SIZES.get(index, 25),
        "max_lots": 0,
        "reason": confluence.get("top_signal_reason", ""),
    }

    if signal == "WAIT" or not chain or spot == 0:
        return trade

    interval = STRIKE_INTERVALS.get(index, 50)
    atm = round(spot / interval) * interval

    if signal in ("CALL", "STRONG_CALL"):
        trade["direction"] = "CALL"
        # Buy ATM or 1 strike OTM call
        target_strike = atm + interval
        for s in chain:
            if s["strike"] == target_strike and s["call_ltp"] > 0:
                trade["entry_strike"] = target_strike
                trade["entry_premium"] = s["call_ltp"]
                break
        if trade["entry_premium"] == 0:
            for s in chain:
                if s["strike"] == atm and s["call_ltp"] > 0:
                    trade["entry_strike"] = atm
                    trade["entry_premium"] = s["call_ltp"]
                    break

    elif signal in ("PUT", "STRONG_PUT"):
        trade["direction"] = "PUT"
        target_strike = atm - interval
        for s in chain:
            if s["strike"] == target_strike and s["put_ltp"] > 0:
                trade["entry_strike"] = target_strike
                trade["entry_premium"] = s["put_ltp"]
                break
        if trade["entry_premium"] == 0:
            for s in chain:
                if s["strike"] == atm and s["put_ltp"] > 0:
                    trade["entry_strike"] = atm
                    trade["entry_premium"] = s["put_ltp"]
                    break

    if trade["entry_premium"] > 0:
        trade["tradeable"] = True
        trade["stoploss_premium"] = round(trade["entry_premium"] * 0.60, 2)  # 40% SL
        trade["target_premium"] = round(trade["entry_premium"] * 1.60, 2)   # 1:1.5 RR
        if trade["entry_premium"] - trade["stoploss_premium"] > 0:
            trade["risk_reward"] = round(
                (trade["target_premium"] - trade["entry_premium"]) /
                (trade["entry_premium"] - trade["stoploss_premium"]), 2
            )
        # Max lots based on risk
        from config import TOTAL_CAPITAL, TRADING_RULES
        max_risk = TOTAL_CAPITAL * TRADING_RULES["max_risk_per_trade_pct"] / 100
        risk_per_lot = (trade["entry_premium"] - trade["stoploss_premium"]) * trade["lot_size"]
        if risk_per_lot > 0:
            trade["max_lots"] = int(max_risk / risk_per_lot)

    return trade


async def run_all_engines() -> dict[str, dict]:
    """Run all 8 engines with REAL Kite data."""
    logger.info(f"\n{'='*60}\nEngine run at {datetime.now()}\n{'='*60}")

    macro = await _fetch_macro_data()
    logger.info(f"Macro: VIX={macro['vix']}, FII Cash={macro['fii_cash_net']}, FII Fut={macro['fii_futures_net']}")

    for index in INDICES:
        try:
            kd = _fetch_kite_data(index)
            spot = kd["spot_price"]
            futures = kd["futures_price"]
            chain = kd["chain_data"]
            pchange = kd["price_change_pct"]

            # Store chain for heatmap API
            latest_chain_data[index] = chain

            logger.info(f"{index}: spot={spot}, futures={futures}, chain_strikes={len(chain)}, change={pchange:.2f}%")

            results = {}

            # Engine 01: OI State
            results["engine_01_oi_state"] = OIStateEngine().run(index, spot_price=spot, chain_data=chain, price_change_pct=pchange)

            # Engine 02: Unusual Flow
            results["engine_02_unusual_flow"] = UnusualFlowEngine().run(index, chain_data=chain, spot_price=spot)

            # Engine 03: Futures Basis
            results["engine_03_futures_basis"] = FuturesBasisEngine().run(index, spot_price=spot, futures_price=futures, fii_net_futures=macro["fii_futures_net"])

            # Engine 04: IV Skew
            results["engine_04_iv_skew"] = IVSkewEngine().run(index, chain_data=chain, spot_price=spot)

            # Engine 05: Liquidity Pool
            results["engine_05_liquidity_pool"] = LiquidityPoolEngine().run(index, chain_data=chain, spot_price=spot)

            # Engine 06: Microstructure (no tick data without WebSocket ticker)
            results["engine_06_microstructure"] = MicrostructureEngine().run(index, spot_price=spot)

            # Engine 07: Macro
            results["engine_07_macro"] = MacroEngine().run(
                index, vix=macro["vix"], vix_change=macro["vix_change"],
                market_change=pchange, fii_cash_net=macro["fii_cash_net"],
                gift_nifty=macro["gift_nifty"], nifty_prev_close=kd["prev_close"],
                fii_futures_net=macro["fii_futures_net"]
            )

            # Engine 08: Trap
            results["engine_08_trap"] = TrapFingerprintEngine().run(
                index, current_price=spot, fii_net_futures=macro["fii_futures_net"]
            )

            # Log engine scores
            for ename, eresult in results.items():
                s = eresult.get("score", 0)
                nd = eresult.get("no_data", False)
                if s != 0 or not nd:
                    logger.info(f"  {ename}: score={s}")

            latest_engine_scores[index] = results

            # Confluence
            ivr_gate = results.get("engine_04_iv_skew", {}).get("gate_active", False)
            confluence = calculate_confluence(results, ivr_gate)

            # Trade signal with entry/SL/exit
            trade = _compute_trade_signal(index, confluence, spot, chain, results)

            # Signal output
            signal_output = generate_signal_output(index, confluence, spot, results)

            latest_signals[index] = {
                "signal": signal_output,
                "confluence": confluence,
                "engines": results,
                "spot_price": spot,
                "prev_close": kd["prev_close"],
                "futures_price": futures,
                "price_change_pct": round(pchange, 2),
                "trade": trade,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f">>> {index}: {confluence['signal']} | score={confluence['normalized_score']} | spot={spot} | trade={trade['direction'] or 'NONE'}")

            # Save to DB
            try:
                with get_db() as session:
                    save_signal(session, {
                        "index_name": index,
                        "signal": confluence["signal"],
                        "raw_score": confluence["raw_score"],
                        "normalized_score": confluence["normalized_score"],
                        "confidence": confluence["confidence"],
                        "engines_bullish": confluence["engines_bullish"],
                        "engines_bearish": confluence["engines_bearish"],
                        "top_signal_reason": confluence["top_signal_reason"],
                        "ivr_gate": confluence["ivr_gate"],
                        "expiry_gate": confluence["expiry_gate"],
                        "engine_details": results,
                    })
            except Exception as e:
                logger.error(f"DB save error: {e}")

        except Exception as e:
            logger.error(f"Engine run failed for {index}: {e}\n{traceback.format_exc()}")

    return latest_signals


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_all_engines, "interval", seconds=ENGINE_REFRESH_SECONDS, id="engine_runner", replace_existing=True)
    return scheduler


def get_latest_signals() -> dict:
    return latest_signals

def get_latest_engine_scores(index: str) -> dict:
    return latest_engine_scores.get(index, {})

def get_latest_chain_data(index: str) -> list:
    return latest_chain_data.get(index, [])
