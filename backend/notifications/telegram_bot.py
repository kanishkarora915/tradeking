"""
TRADEKING — Telegram Alert Bot
Sends trading signals and trap alerts to Telegram.
"""
import httpx
import logging
from datetime import datetime

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


async def send_telegram(message: str) -> bool:
    """Send a message via Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — skipping notification")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram message sent")
                return True
            else:
                logger.error(f"Telegram error: {resp.status_code} — {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
        return False


async def send_signal_alert(signal_data: dict) -> None:
    """Send a trading signal alert."""
    signal = signal_data.get("signal", {})
    index = signal.get("index", "???")
    direction = signal.get("signal", "WAIT")
    score = signal.get("score", 0)
    confidence = signal.get("confidence", "LOW")

    emoji = {"STRONG_CALL": "🟢🟢", "CALL": "🟢", "STRONG_PUT": "🔴🔴", "PUT": "🔴", "WAIT": "⚪"}.get(direction, "⚪")

    msg = (
        f"<b>TRADEKING SIGNAL</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{emoji} <b>{index}: {direction}</b>\n"
        f"Score: {score:+.1f}/10 | Confidence: {confidence}\n"
        f"Spot: {signal.get('spot_price', 0):,.0f}\n"
    )

    context = signal.get("context", {})
    if context.get("trap_active"):
        msg += f"⚠️ <b>{context['trap_type']}</b> detected!\n"

    msg += (
        f"\nEngines: {signal.get('engines', {}).get('bullish', 0)}🟢 "
        f"{signal.get('engines', {}).get('bearish', 0)}🔴 "
        f"{signal.get('engines', {}).get('neutral', 0)}⚪\n"
        f"Reason: {signal.get('engines', {}).get('top_reason', 'N/A')}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🕐 {datetime.now().strftime('%H:%M:%S')}"
    )

    await send_telegram(msg)


async def send_trap_alert(index: str, trap_data: dict) -> None:
    """Send a special alert when trap engine fires."""
    trap_type = trap_data.get("trap_type", "UNKNOWN")
    conditions = trap_data.get("conditions_met", [])
    confidence = trap_data.get("confidence", "PARTIAL")
    trapped_level = trap_data.get("trapped_level", 0)
    signal = trap_data.get("signal", "N/A")

    if trap_type == "BULL_TRAP":
        emoji = "🚨"
        action = "REVERSAL → PUT"
    else:
        emoji = "⚡"
        action = "REVERSAL → CALL"

    msg = (
        f"{emoji} <b>TRAP DETECTED — {index}</b> {emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Type: <b>{trap_type}</b>\n"
        f"Confidence: <b>{confidence}</b>\n"
        f"Trapped Level: {trapped_level:,.0f}\n"
        f"Conditions: {len(conditions)}/5 — {conditions}\n"
        f"Action: <b>{action}</b>\n"
        f"Signal: <b>{signal}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {datetime.now().strftime('%H:%M:%S')}"
    )

    await send_telegram(msg)
