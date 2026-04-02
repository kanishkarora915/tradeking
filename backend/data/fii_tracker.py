"""
TRADEKING — FII Net Futures Position Tracker
Tracks FII net long/short futures positions over rolling 20-day window
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models import MacroData

logger = logging.getLogger(__name__)


def get_fii_net_futures(session: Session) -> float:
    """Get latest FII net futures position."""
    latest = (
        session.query(MacroData)
        .filter(MacroData.fii_futures_net.isnot(None))
        .order_by(desc(MacroData.timestamp))
        .first()
    )
    return latest.fii_futures_net if latest else 0.0


def get_fii_futures_trend(session: Session, days: int = 20) -> list[dict]:
    """Get FII net futures position history for trend analysis."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    records = (
        session.query(MacroData)
        .filter(
            MacroData.fii_futures_net.isnot(None),
            MacroData.timestamp >= cutoff,
        )
        .order_by(MacroData.timestamp)
        .all()
    )
    return [
        {
            "date": r.timestamp.strftime("%Y-%m-%d"),
            "fii_net": r.fii_futures_net,
        }
        for r in records
    ]


def classify_fii_stance(net_futures: float) -> str:
    """Classify FII stance based on net futures position."""
    if net_futures > 50000:
        return "STRONG_LONG"
    elif net_futures > 20000:
        return "LONG"
    elif net_futures > -20000:
        return "NEUTRAL"
    elif net_futures > -50000:
        return "SHORT"
    else:
        return "STRONG_SHORT"


def fii_direction_score(net_futures: float) -> float:
    """Score FII direction: -2 to +2."""
    if net_futures > 50000:
        return 2.0
    elif net_futures > 20000:
        return 1.0
    elif net_futures > -20000:
        return 0.0
    elif net_futures > -50000:
        return -1.0
    else:
        return -2.0
