"""
TRADEKING — Engine Scheduler
Runs all 8 engines every 5 minutes during market hours.
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


async def run_all_engines() -> dict[str, dict]:
    """Run all 8 engines for all 3 indices and compute confluence scores."""
    if not is_market_open():
        logger.info("Market closed — skipping engine run")
        return latest_signals

    logger.info(f"Running all engines at {datetime.now()}")

    for index in INDICES:
        try:
            engine_results = {}

            # Instantiate and run each engine
            for engine_name, engine_class in ENGINE_REGISTRY.items():
                try:
                    engine = engine_class()
                    result = engine.run(index)
                    engine_results[engine_name] = result

                    # Save to DB
                    with get_db() as session:
                        save_engine_score(session, index, engine_name, result.get("score", 0), result)

                except Exception as e:
                    logger.error(f"Engine {engine_name} failed for {index}: {e}")
                    engine_results[engine_name] = {"score": 0, "error": str(e)}

            latest_engine_scores[index] = engine_results

            # Calculate confluence
            ivr_gate = engine_results.get("engine_04_iv_skew", {}).get("gate_active", False)
            confluence = calculate_confluence(engine_results, ivr_gate)

            # Generate final signal
            spot_price = 0  # Will be filled by data feed
            signal_output = generate_signal_output(index, confluence, spot_price, engine_results)

            latest_signals[index] = {
                "signal": signal_output,
                "confluence": confluence,
                "engines": engine_results,
                "timestamp": datetime.now().isoformat(),
            }

            # Save signal to DB
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

            logger.info(f"{index}: {confluence['signal']} (score: {confluence['normalized_score']}, confidence: {confluence['confidence']})")

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
    # Token refresh at 8:00 AM daily
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
    """Refresh Kite token daily."""
    try:
        from kite_auth import refresh_token_if_needed
        refresh_token_if_needed()
    except Exception as e:
        logger.error(f"Kite token refresh failed: {e}")


def get_latest_signals() -> dict:
    return latest_signals


def get_latest_engine_scores(index: str) -> dict:
    return latest_engine_scores.get(index, {})
