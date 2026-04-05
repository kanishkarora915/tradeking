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
    get_latest_chain_data,
    latest_signals,
)
from kite_auth import get_login_url, generate_session, is_authenticated
from notifications.telegram_bot import send_signal_alert, send_trap_alert
from vix_websocket import vix_clients, get_latest_vix, start_vix_ticker

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

    result = {}
    for index in INDICES:
        data = signals.get(index, {})
        sig = data.get("signal", {})
        conf = data.get("confluence", {})
        trade = data.get("trade", {})
        iv = data.get("engines", {}).get("engine_04_iv_skew", {})
        liq = data.get("engines", {}).get("engine_05_liquidity_pool", {})
        macro_e = data.get("engines", {}).get("engine_07_macro", {})
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
            "spot_price": data.get("spot_price", 0),
            "prev_close": data.get("prev_close", 0),
            "price_change_pct": data.get("price_change_pct", 0),
            "futures_price": data.get("futures_price", 0),
            "ivr": iv.get("ivr", 0),
            "pcr": 0,
            "vix": macro_e.get("vix", 0),
            "max_pain": liq.get("max_pain", 0),
            "trade": {
                "direction": trade.get("direction"),
                "entry_strike": trade.get("entry_strike", 0),
                "entry_premium": trade.get("entry_premium", 0),
                "stoploss_premium": trade.get("stoploss_premium", 0),
                "target_premium": trade.get("target_premium", 0),
                "risk_reward": trade.get("risk_reward", 0),
                "max_lots": trade.get("max_lots", 0),
                "lot_size": trade.get("lot_size", 0),
                "tradeable": trade.get("tradeable", False),
            },
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
        return {"signal": "WAIT", "score": 0, "message": "No data yet — login to Kite first"}
    return data


@app.get("/api/engines/{index}")
async def get_engines(index: str):
    """Get all 8 engine scores with details for an index."""
    index = index.upper()
    if index not in INDICES:
        return JSONResponse(status_code=400, content={"error": f"Invalid index: {index}"})

    scores = get_latest_engine_scores(index)
    if not scores:
        return {"message": "No engine data yet — login to Kite first"}
    return scores


@app.get("/api/oi-chain/{index}")
async def get_oi_chain(index: str):
    """Get options chain with OI data for heatmap."""
    index = index.upper()
    if index not in INDICES:
        return JSONResponse(status_code=400, content={"error": f"Invalid index: {index}"})

    scores = get_latest_engine_scores(index)
    liquidity = scores.get("engine_05_liquidity_pool", {})
    chain = get_latest_chain_data(index)

    return {
        "index": index,
        "max_pain": liquidity.get("max_pain", 0),
        "call_wall": liquidity.get("call_wall", 0),
        "put_wall": liquidity.get("put_wall", 0),
        "chain": chain,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/macro")
async def get_macro():
    """Get VIX, FII data, GIFT Nifty."""
    scores = get_latest_engine_scores("NIFTY")
    macro = scores.get("engine_07_macro", {})

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


@app.get("/api/vix")
async def get_vix():
    """REST fallback for VIX data + trade signals."""
    return get_latest_vix()


@app.websocket("/ws/vix")
async def vix_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time VIX + trade signals."""
    await websocket.accept()
    vix_clients.add(websocket)
    logger.info(f"VIX WS client connected. Total: {len(vix_clients)}")

    try:
        # Send current state immediately
        data = get_latest_vix()
        if data.get("vix", 0) > 0:
            await websocket.send_json({"type": "vix_update", **data})

        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=60)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        vix_clients.discard(websocket)
        logger.info(f"VIX WS client disconnected. Total: {len(vix_clients)}")
    except Exception as e:
        vix_clients.discard(websocket)


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


# ─── KITE AUTH (Auto login — zero manual steps) ────────────────

@app.get("/api/auth/kite/login")
async def kite_login():
    """Redirect user directly to Zerodha login page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=get_login_url())


@app.get("/api/auth/kite/callback")
async def kite_callback(request_token: str = Query(None), action: str = Query(None)):
    """Auto callback from Zerodha after login.
    Zerodha redirects here with ?request_token=xxx&action=login
    We auto-generate session and redirect to dashboard.
    """
    from fastapi.responses import HTMLResponse
    if not request_token:
        return HTMLResponse("<h2>Login failed — no request token received</h2>", status_code=400)
    try:
        session_data = generate_session(request_token)
        user = session_data.get("user_name", session_data.get("user_id", ""))
        # Trigger engine run + VIX ticker immediately after login
        asyncio.create_task(run_all_engines())
        try:
            from kite_auth import get_kite
            kite = get_kite()
            start_vix_ticker(kite._access_token if hasattr(kite, '_access_token') else session_data.get("access_token", ""))
        except Exception as ve:
            logger.error(f"VIX ticker start failed: {ve}")
        return HTMLResponse(f"""
        <html>
        <head>
            <meta http-equiv="refresh" content="2;url=/" />
            <style>
                body {{ background: #080A0F; color: #F5F5F7; font-family: 'DM Sans', sans-serif;
                       display: flex; align-items: center; justify-content: center; height: 100vh; }}
                .box {{ text-align: center; }}
                .check {{ color: #30D158; font-size: 48px; }}
                h2 {{ margin: 16px 0 8px; }}
                p {{ color: #8E8E93; }}
            </style>
        </head>
        <body>
            <div class="box">
                <div class="check">&#10003;</div>
                <h2>Welcome, {user}!</h2>
                <p>Kite connected successfully. Redirecting to TRADEKING dashboard...</p>
            </div>
        </body>
        </html>
        """)
    except Exception as e:
        return HTMLResponse(f"""
        <html>
        <head><style>body {{ background: #080A0F; color: #FF453A; font-family: sans-serif;
               display: flex; align-items: center; justify-content: center; height: 100vh; }}</style></head>
        <body><div><h2>Login Failed</h2><p>{str(e)}</p><a href="/api/auth/kite/login" style="color:#0A84FF">Try Again</a></div></body>
        </html>
        """, status_code=400)


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
            "spot_price": data.get("spot_price", 0),
            "prev_close": data.get("prev_close", 0),
            "price_change_pct": data.get("price_change_pct", 0),
            "futures_price": data.get("futures_price", 0),
            "trade": data.get("trade", {}),
            "engines": {k: {"score": v.get("score", 0)} for k, v in engines.items()},
            "timestamp": data.get("timestamp", ""),
        }
    return result


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
