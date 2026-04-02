"""
TRADEKING — Engine Scheduler
Fetches REAL data from Kite Connect + NSE, feeds to all 8 engines every 5 minutes.
NO MOCK DATA — returns zeros when data unavailable.
"""
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import ENGINE_REFRESH_SECONDS, INDICES, is_market_open
from engines import ENGINE_REGISTRY
from scoring.confluence import calculate_confluence
from scoring.signal_output import generate_signal_output
from database.db import get_db
from database.oi_history import save_engine_score, save_signal

logger = logging.getLogger(__name__)

# Global state for latest signals
latest_signals: dict[str, dict] = {}
latest_engine_scores: dict[str, dict] = {}


def _fetch_kite_data(index: str) -> dict:
    """Fetch real market data from Kite Connect for an index.
    Returns all data needed by engines.
    """
    from kite_auth import is_authenticated, get_spot_price, get_futures_price, get_options_chain

    data = {
        "spot_price": 0.0,
        "futures_price": 0.0,
        "chain_data": [],
        "price_change_pct": 0.0,
        "authenticated": False,
    }

    if not is_authenticated():
        logger.warning("Kite not authenticated — cannot fetch live data")
        return data

    data["authenticated"] = True

    try:
        data["spot_price"] = get_spot_price(index)
        logger.info(f"{index} spot price: {data['spot_price']}")
    except Exception as e:
        logger.error(f"Error fetching spot price for {index}: {e}")

    try:
        data["futures_price"] = get_futures_price(index)
    except Exception as e:
        logger.error(f"Error fetching futures price for {index}: {e}")

    try:
        raw_chain = get_options_chain(index)
        # Convert to engine-friendly format
        chain_map = {}
        for opt in raw_chain:
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
            if opt.get("type") == "CE":
                row["call_oi"] = opt.get("oi", 0)
                row["call_volume"] = opt.get("volume", 0)
                row["call_ltp"] = opt.get("ltp", 0)
                row["call_bid"] = opt.get("bid", 0)
                row["call_ask"] = opt.get("ask", 0)
            elif opt.get("type") == "PE":
                row["put_oi"] = opt.get("oi", 0)
                row["put_volume"] = opt.get("volume", 0)
                row["put_ltp"] = opt.get("ltp", 0)
                row["put_bid"] = opt.get("bid", 0)
                row["put_ask"] = opt.get("ask", 0)

        data["chain_data"] = sorted(chain_map.values(), key=lambda x: x["strike"])
        logger.info(f"{index} chain: {len(data['chain_data'])} strikes loaded")
    except Exception as e:
        logger.error(f"Error fetching options chain for {index}: {e}")

    # Price change % from spot vs previous close
    if data["spot_price"] > 0:
        try:
            from kite_auth import get_kite
            kite = get_kite()
            if index == "NIFTY":
                symbol = "NSE:NIFTY 50"
            elif index == "BANKNIFTY":
                symbol = "NSE:NIFTY BANK"
            else:
                symbol = "BSE:SENSEX"
            quote = kite.quote([symbol])
            q = quote.get(symbol, {})
            ohlc = q.get("ohlc", {})
            prev_close = ohlc.get("close", 0)
            if prev_close > 0:
                data["price_change_pct"] = ((data["spot_price"] - prev_close) / prev_close) * 100
        except Exception:
            pass

    return data


async def _fetch_macro_data() -> dict:
    """Fetch real macro data from NSE."""
    macro = {
        "vix": 0.0,
        "vix_change": 0.0,
        "fii_cash_net": 0.0,
        "gift_nifty": 0.0,
        "nifty_prev_close": 0.0,
        "fii_futures_net": 0.0,
        "market_change": 0.0,
    }

    try:
        from data.vix_tracker import fetch_india_vix
        macro["vix"] = await fetch_india_vix()
        logger.info(f"India VIX: {macro['vix']}")
    except Exception as e:
        logger.error(f"Error fetching VIX: {e}")

    try:
        from data.nse_scraper import fetch_fii_dii_data
        fii_data = await fetch_fii_dii_data()
        macro["fii_cash_net"] = fii_data.get("fii_net", 0)
    except Exception as e:
        logger.error(f"Error fetching FII/DII: {e}")

    try:
        from data.nse_scraper import fetch_participant_oi
        participant = await fetch_participant_oi()
        macro["fii_futures_net"] = participant.get("fii_futures_net", 0)
    except Exception as e:
        logger.error(f"Error fetching participant OI: {e}")

    return macro


async def run_all_engines() -> dict[str, dict]:
    """Run all 8 engines for all 3 indices with REAL data from Kite + NSE."""
    logger.info(f"=== Engine run at {datetime.now()} ===")

    # Fetch macro data once (shared across indices)
    macro = await _fetch_macro_data()

    for index in INDICES:
        try:
            # Fetch real data from Kite
            kite_data = _fetch_kite_data(index)
            spot = kite_data["spot_price"]
            futures = kite_data["futures_price"]
            chain = kite_data["chain_data"]
            price_change = kite_data["price_change_pct"]

            engine_results = {}

            # --- Engine 01: OI State ---
            try:
                from engines.engine_01_oi_state import OIStateEngine
                e = OIStateEngine()
                engine_results["engine_01_oi_state"] = e.run(
                    index, spot_price=spot, chain_data=chain, price_change_pct=price_change
                )
            except Exception as ex:
                logger.error(f"Engine 01 error {index}: {ex}")
                engine_results["engine_01_oi_state"] = {"score": 0, "state": "ERROR", "error": str(ex)}

            # --- Engine 02: Unusual Flow ---
            try:
                from engines.engine_02_unusual_flow import UnusualFlowEngine
                e = UnusualFlowEngine()
                engine_results["engine_02_unusual_flow"] = e.run(
                    index, chain_data=chain, spot_price=spot
                )
            except Exception as ex:
                logger.error(f"Engine 02 error {index}: {ex}")
                engine_results["engine_02_unusual_flow"] = {"score": 0, "direction": "ERROR", "error": str(ex)}

            # --- Engine 03: Futures Basis ---
            try:
                from engines.engine_03_futures_basis import FuturesBasisEngine
                e = FuturesBasisEngine()
                engine_results["engine_03_futures_basis"] = e.run(
                    index, spot_price=spot, futures_price=futures,
                    fii_net_futures=macro.get("fii_futures_net", 0)
                )
            except Exception as ex:
                logger.error(f"Engine 03 error {index}: {ex}")
                engine_results["engine_03_futures_basis"] = {"score": 0, "error": str(ex)}

            # --- Engine 04: IV Skew ---
            try:
                from engines.engine_04_iv_skew import IVSkewEngine
                e = IVSkewEngine()
                engine_results["engine_04_iv_skew"] = e.run(
                    index, chain_data=chain, spot_price=spot
                )
            except Exception as ex:
                logger.error(f"Engine 04 error {index}: {ex}")
                engine_results["engine_04_iv_skew"] = {"score": 0, "gate_active": False, "error": str(ex)}

            # --- Engine 05: Liquidity Pool ---
            try:
                from engines.engine_05_liquidity_pool import LiquidityPoolEngine
                e = LiquidityPoolEngine()
                engine_results["engine_05_liquidity_pool"] = e.run(
                    index, chain_data=chain, spot_price=spot
                )
            except Exception as ex:
                logger.error(f"Engine 05 error {index}: {ex}")
                engine_results["engine_05_liquidity_pool"] = {"score": 0, "error": str(ex)}

            # --- Engine 06: Microstructure ---
            try:
                from engines.engine_06_microstructure import MicrostructureEngine
                e = MicrostructureEngine()
                engine_results["engine_06_microstructure"] = e.run(index, spot_price=spot)
            except Exception as ex:
                logger.error(f"Engine 06 error {index}: {ex}")
                engine_results["engine_06_microstructure"] = {"score": 0, "error": str(ex)}

            # --- Engine 07: Macro ---
            try:
                from engines.engine_07_macro import MacroEngine
                e = MacroEngine()
                engine_results["engine_07_macro"] = e.run(
                    index, vix=macro["vix"], vix_change=macro["vix_change"],
                    market_change=price_change, fii_cash_net=macro["fii_cash_net"],
                    gift_nifty=macro["gift_nifty"], nifty_prev_close=macro["nifty_prev_close"],
                    fii_futures_net=macro["fii_futures_net"]
                )
            except Exception as ex:
                logger.error(f"Engine 07 error {index}: {ex}")
                engine_results["engine_07_macro"] = {"score": 0, "error": str(ex)}

            # --- Engine 08: Trap ---
            try:
                from engines.engine_08_trap import TrapFingerprintEngine
                e = TrapFingerprintEngine()
                # Trap engine needs breakout context — pass what we have
                engine_results["engine_08_trap"] = e.run(
                    index, current_price=spot,
                    fii_net_futures=macro.get("fii_futures_net", 0),
                )
            except Exception as ex:
                logger.error(f"Engine 08 error {index}: {ex}")
                engine_results["engine_08_trap"] = {"score": 0, "trap_type": None, "error": str(ex)}

            latest_engine_scores[index] = engine_results

            # Calculate confluence
            ivr_gate = engine_results.get("engine_04_iv_skew", {}).get("gate_active", False)
            confluence = calculate_confluence(engine_results, ivr_gate)

            # Generate final signal
            signal_output = generate_signal_output(index, confluence, spot, engine_results)

            latest_signals[index] = {
                "signal": signal_output,
                "confluence": confluence,
                "engines": engine_results,
                "spot_price": spot,
                "timestamp": datetime.now().isoformat(),
            }

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
                        "engine_details": engine_results,
                    })
            except Exception as e:
                logger.error(f"DB save error for {index}: {e}")

            logger.info(f"{index}: {confluence['signal']} (score: {confluence['normalized_score']}, spot: {spot})")

        except Exception as e:
            logger.error(f"Engine run failed for {index}: {e}")

    return latest_signals


def create_scheduler() -> AsyncIOScheduler:
    """Create APScheduler that runs engines every 5 minutes."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_all_engines,
        "interval",
        seconds=ENGINE_REFRESH_SECONDS,
        id="engine_runner",
        replace_existing=True,
    )
    scheduler.add_job(
        _refresh_kite_token,
        "cron",
        hour=8,
        minute=0,
        id="kite_token_refresh",
        replace_existing=True,
    )
    return scheduler


async def _refresh_kite_token():
    try:
        from kite_auth import is_authenticated
        if not is_authenticated():
            logger.warning("Kite token expired — re-login required")
    except Exception as e:
        logger.error(f"Kite token check failed: {e}")


def get_latest_signals() -> dict:
    return latest_signals


def get_latest_engine_scores(index: str) -> dict:
    return latest_engine_scores.get(index, {})
