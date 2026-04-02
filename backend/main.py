"""
TRADEKING — FastAPI Application
Real-time institutional footprint intelligence dashboard API.
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from config import INDICES, is_market_open, is_expiry_day, TRADING_RULES, TOTAL_CAPITAL
from database.db import init_db
from scheduler import (
    create_scheduler,
    run_all_engines,
    get_latest_signals,
    get_latest_engine_scores,
    latest_signals,
)
from kite_auth import get_login_url, generate_session, is_authenticated
from notifications.telegram_bot import send_signal_alert, send_trap_alert

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# WebSocket connection manager
connected_clients: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Startup and shutdown lifecycle."""
    logger.info("TRADEKING starting up...")
    init_db()

    # Start engine scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Engine scheduler started")

    # Run engines once on startup
    await run_all_engines()

    # Start WebSocket broadcast loop
    broadcast_task = asyncio.create_task(ws_broadcast_loop())

    yield

    broadcast_task.cancel()
    scheduler.shutdown()
    logger.info("TRADEKING shutdown complete")


app = FastAPI(
    title="TRADEKING",
    description="Institutional Options Intelligence Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── REST ENDPOINTS ─────────────────────────────────────────────

@app.get("/api/signals")
async def get_signals():
    """Get current signals for all 3 indices."""
    signals = get_latest_signals()
    if not signals:
        # Return mock data if no signals computed yet
        return _mock_signals()

    result = {}
    for index in INDICES:
        data = signals.get(index, {})
        sig = data.get("signal", {})
        conf = data.get("confluence", {})
        result[index] = {
            "index": index,
            "signal": conf.get("signal", "WAIT"),
            "score": conf.get("normalized_score", 0),
            "confidence": conf.get("confidence", "LOW"),
            "engines_bullish": conf.get("engines_bullish", 0),
            "engines_bearish": conf.get("engines_bearish", 0),
            "top_reason": conf.get("top_signal_reason", ""),
            "ivr_gate": conf.get("ivr_gate", False),
            "expiry_gate": conf.get("expiry_gate", False),
            "spot_price": sig.get("spot_price", 0),
            "timestamp": data.get("timestamp", ""),
        }
    return result


@app.get("/api/signals/{index}")
async def get_signal_detail(index: str):
    """Get detailed signal breakdown for specific index."""
    index = index.upper()
    if index not in INDICES:
        return JSONResponse(status_code=400, content={"error": f"Invalid index: {index}"})

    signals = get_latest_signals()
    data = signals.get(index, {})
    if not data:
        return _mock_signal_detail(index)
    return data


@app.get("/api/engines/{index}")
async def get_engines(index: str):
    """Get all 8 engine scores with details for an index."""
    index = index.upper()
    if index not in INDICES:
        return JSONResponse(status_code=400, content={"error": f"Invalid index: {index}"})

    scores = get_latest_engine_scores(index)
    if not scores:
        return _mock_engine_scores(index)
    return scores


@app.get("/api/oi-chain/{index}")
async def get_oi_chain(index: str):
    """Get options chain with OI data for heatmap."""
    index = index.upper()
    if index not in INDICES:
        return JSONResponse(status_code=400, content={"error": f"Invalid index: {index}"})

    # Try to get from engine 05 liquidity pool data
    scores = get_latest_engine_scores(index)
    liquidity = scores.get("engine_05_liquidity_pool", {})

    return {
        "index": index,
        "max_pain": liquidity.get("max_pain", 0),
        "call_wall": liquidity.get("call_wall", 0),
        "put_wall": liquidity.get("put_wall", 0),
        "chain": _mock_oi_chain(index),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/macro")
async def get_macro():
    """Get VIX, FII data, GIFT Nifty."""
    scores = get_latest_engine_scores("NIFTY")
    macro = scores.get("engine_07_macro", {})

    if not macro:
        return _mock_macro()

    return {
        "vix": macro.get("vix", 0),
        "vix_change": macro.get("vix_change", 0),
        "vix_level": macro.get("vix_level", "NORMAL"),
        "fii_cash_net": macro.get("fii_cash_net", 0),
        "fii_cash_direction": macro.get("fii_cash_direction", "N/A"),
        "gift_nifty": macro.get("gift_nifty", 0),
        "gift_nifty_bias": macro.get("gift_nifty_bias", "NEUTRAL"),
        "gift_nifty_gap": macro.get("gift_nifty_gap", 0),
        "fii_futures_net": macro.get("fii_futures_net", 0),
        "market_open": is_market_open(),
        "expiry_day": is_expiry_day(),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/weekly-summary")
async def get_weekly_summary():
    """Post-close weekly analysis (available after 3:30 PM)."""
    now = datetime.now()
    if now.hour < 15 or (now.hour == 15 and now.minute < 30):
        return {"available": False, "message": "Weekly summary available after 3:30 PM"}

    signals = get_latest_signals()
    summary = {}
    for index in INDICES:
        data = signals.get(index, {})
        conf = data.get("confluence", {})
        engines = data.get("engines", {})
        trap = engines.get("engine_08_trap", {})

        summary[index] = {
            "final_signal": conf.get("signal", "WAIT"),
            "final_score": conf.get("normalized_score", 0),
            "trap_detected": trap.get("trap_type") is not None,
            "trap_type": trap.get("trap_type"),
            "engines_bullish": conf.get("engines_bullish", 0),
            "engines_bearish": conf.get("engines_bearish", 0),
            "top_reason": conf.get("top_signal_reason", ""),
        }

    return {
        "available": True,
        "date": now.strftime("%Y-%m-%d"),
        "summary": summary,
    }


@app.get("/api/risk")
async def get_risk():
    """Get capital and risk status."""
    return {
        "total_capital": TOTAL_CAPITAL,
        "max_risk_per_trade": TOTAL_CAPITAL * TRADING_RULES["max_risk_per_trade_pct"] / 100,
        "daily_loss_limit": TOTAL_CAPITAL * TRADING_RULES["daily_loss_limit_pct"] / 100,
        "stop_loss_pct": TRADING_RULES["stop_loss_premium_pct"],
        "rules": TRADING_RULES,
    }


# ─── KITE AUTH (API Key + Secret only, no OAuth redirect) ───────

@app.get("/api/auth/kite/login")
async def kite_login():
    """Get Kite login URL. User opens this manually, logs in, copies request_token."""
    return {
        "login_url": get_login_url(),
        "instructions": "Open this URL, login, copy the request_token from the redirected URL, then POST it to /api/auth/kite/session",
    }


@app.post("/api/auth/kite/session")
async def kite_session(request_token: str = Query(...)):
    """Generate Kite session using API key + secret + request_token."""
    try:
        session_data = generate_session(request_token)
        return {"status": "success", **session_data}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.get("/api/auth/status")
async def auth_status():
    """Check if Kite is authenticated."""
    return {"authenticated": is_authenticated()}


# ─── WEBSOCKET ──────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time signal updates."""
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")

    try:
        # Send current state immediately
        signals = get_latest_signals()
        if signals:
            await websocket.send_json({"type": "signals", "data": _serialize_signals(signals)})

        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(connected_clients)}")
    except Exception as e:
        connected_clients.discard(websocket)
        logger.error(f"WebSocket error: {e}")


async def ws_broadcast_loop():
    """Broadcast signals to all connected WebSocket clients every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        signals = get_latest_signals()
        if signals and connected_clients:
            message = json.dumps({"type": "signals", "data": _serialize_signals(signals)})
            disconnected = set()
            for ws in connected_clients:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.add(ws)
            connected_clients -= disconnected


@app.post("/api/run-engines")
async def manual_engine_run():
    """Manually trigger engine run (for testing)."""
    results = await run_all_engines()
    return {"status": "success", "indices": list(results.keys())}


# ─── HELPERS ────────────────────────────────────────────────────

def _serialize_signals(signals: dict) -> dict:
    """Serialize signals for JSON transmission."""
    result = {}
    for index, data in signals.items():
        conf = data.get("confluence", {})
        engines = data.get("engines", {})
        trap = engines.get("engine_08_trap", {})
        iv = engines.get("engine_04_iv_skew", {})
        liquidity = engines.get("engine_05_liquidity_pool", {})
        macro = engines.get("engine_07_macro", {})

        result[index] = {
            "signal": conf.get("signal", "WAIT"),
            "score": conf.get("normalized_score", 0),
            "confidence": conf.get("confidence", "LOW"),
            "engines_bullish": conf.get("engines_bullish", 0),
            "engines_bearish": conf.get("engines_bearish", 0),
            "top_reason": conf.get("top_signal_reason", ""),
            "ivr_gate": conf.get("ivr_gate", False),
            "expiry_gate": conf.get("expiry_gate", False),
            "trap": {
                "active": trap.get("trap_type") is not None,
                "type": trap.get("trap_type"),
                "confidence": trap.get("confidence"),
                "level": trap.get("trapped_level", 0),
            },
            "ivr": iv.get("ivr", 0),
            "pcr": 0,  # Will be computed from OI data
            "vix": macro.get("vix", 0),
            "max_pain": liquidity.get("max_pain", 0),
            "spot_price": data.get("signal", {}).get("spot_price", 0),
            "engines": {k: {"score": v.get("score", 0)} for k, v in engines.items()},
            "timestamp": data.get("timestamp", ""),
        }
    return result


def _mock_signals() -> dict:
    """Return mock signals for development."""
    import random
    mock = {}
    for index in INDICES:
        base = {"NIFTY": 23450, "BANKNIFTY": 51200, "SENSEX": 77800}[index]
        score = round(random.uniform(-8, 8), 1)
        if score > 5:
            signal = "STRONG_CALL"
        elif score > 3:
            signal = "CALL"
        elif score < -5:
            signal = "STRONG_PUT"
        elif score < -3:
            signal = "PUT"
        else:
            signal = "WAIT"

        mock[index] = {
            "index": index,
            "signal": signal,
            "score": score,
            "confidence": "HIGH" if abs(score) > 5 else "MEDIUM" if abs(score) > 3 else "LOW",
            "engines_bullish": random.randint(1, 6),
            "engines_bearish": random.randint(0, 4),
            "top_reason": random.choice([
                f"BEAR_TRAP detected at {base - 50}",
                f"Strong unusual call flow at {base + 100}",
                "FII net long + expanding basis",
                "OI state: BULLISH, velocity +12%",
            ]),
            "ivr_gate": False,
            "expiry_gate": False,
            "spot_price": base + random.randint(-50, 50),
            "ivr": round(random.uniform(15, 55), 1),
            "pcr": round(random.uniform(0.6, 1.4), 2),
            "vix": round(random.uniform(11, 19), 2),
            "timestamp": datetime.now().isoformat(),
        }
    return mock


def _mock_signal_detail(index: str) -> dict:
    """Mock detailed signal for an index."""
    from engines import ENGINE_REGISTRY
    engines = {}
    for name, cls in ENGINE_REGISTRY.items():
        engine = cls()
        engines[name] = engine.run(index)

    from scoring.confluence import calculate_confluence
    ivr_gate = engines.get("engine_04_iv_skew", {}).get("gate_active", False)
    confluence = calculate_confluence(engines, ivr_gate)

    return {
        "signal": confluence,
        "confluence": confluence,
        "engines": engines,
        "timestamp": datetime.now().isoformat(),
    }


def _mock_engine_scores(index: str) -> dict:
    """Mock engine scores for an index."""
    from engines import ENGINE_REGISTRY
    engines = {}
    for name, cls in ENGINE_REGISTRY.items():
        engine = cls()
        engines[name] = engine.run(index)
    return engines


def _mock_oi_chain(index: str) -> list[dict]:
    """Mock OI chain for heatmap."""
    import random
    base = {"NIFTY": 23400, "BANKNIFTY": 51000, "SENSEX": 77500}.get(index, 23000)
    interval = {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100}.get(index, 50)
    chain = []
    for i in range(-10, 11):
        strike = base + i * interval
        chain.append({
            "strike": strike,
            "call_oi": random.randint(50000, 2000000),
            "put_oi": random.randint(50000, 2000000),
            "call_oi_change": random.randint(-100000, 200000),
            "put_oi_change": random.randint(-100000, 200000),
            "call_volume": random.randint(1000, 50000),
            "put_volume": random.randint(1000, 50000),
            "call_iv": round(random.uniform(8, 25), 2),
            "put_iv": round(random.uniform(8, 25), 2),
        })
    return chain


def _mock_macro() -> dict:
    """Mock macro data."""
    import random
    return {
        "vix": round(random.uniform(11, 19), 2),
        "vix_change": round(random.uniform(-1.5, 1.5), 2),
        "vix_level": "NORMAL",
        "fii_cash_net": round(random.uniform(-3000, 3000), 0),
        "fii_cash_direction": random.choice(["BUY", "SELL"]),
        "gift_nifty": 23500 + random.randint(-80, 80),
        "gift_nifty_bias": random.choice(["BULLISH", "NEUTRAL", "BEARISH"]),
        "gift_nifty_gap": round(random.uniform(-60, 60), 0),
        "fii_futures_net": random.randint(-50000, 50000),
        "market_open": is_market_open(),
        "expiry_day": is_expiry_day(),
        "timestamp": datetime.now().isoformat(),
    }


# ─── STATIC FILES (Render deployment) ───────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA — all non-API routes return index.html."""
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
