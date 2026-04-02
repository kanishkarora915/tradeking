"""
TRADEKING — OI Snapshot Storage & Retrieval
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
import logging

from database.models import OISnapshot, EngineScore, Signal, MacroData
from database.db import get_db

logger = logging.getLogger(__name__)


def save_oi_snapshot(
    session: Session,
    index_name: str,
    spot_price: float,
    chain_data: list[dict],
) -> None:
    """Save a full options chain snapshot."""
    timestamp = datetime.utcnow()
    snapshots = []
    for strike_data in chain_data:
        snap = OISnapshot(
            timestamp=timestamp,
            index_name=index_name,
            strike=strike_data["strike"],
            call_oi=strike_data.get("call_oi", 0),
            put_oi=strike_data.get("put_oi", 0),
            call_oi_change=strike_data.get("call_oi_change", 0),
            put_oi_change=strike_data.get("put_oi_change", 0),
            call_volume=strike_data.get("call_volume", 0),
            put_volume=strike_data.get("put_volume", 0),
            call_iv=strike_data.get("call_iv", 0.0),
            put_iv=strike_data.get("put_iv", 0.0),
            call_ltp=strike_data.get("call_ltp", 0.0),
            put_ltp=strike_data.get("put_ltp", 0.0),
            spot_price=spot_price,
        )
        snapshots.append(snap)
    session.add_all(snapshots)
    logger.info(f"Saved {len(snapshots)} OI snapshots for {index_name}")


def get_oi_snapshot(
    session: Session,
    index_name: str,
    minutes_ago: int = 0,
) -> list[OISnapshot]:
    """Get OI snapshot from N minutes ago."""
    if minutes_ago > 0:
        cutoff = datetime.utcnow() - timedelta(minutes=minutes_ago)
        return (
            session.query(OISnapshot)
            .filter(
                OISnapshot.index_name == index_name,
                OISnapshot.timestamp <= cutoff,
            )
            .order_by(desc(OISnapshot.timestamp))
            .limit(50)
            .all()
        )
    return (
        session.query(OISnapshot)
        .filter(OISnapshot.index_name == index_name)
        .order_by(desc(OISnapshot.timestamp))
        .limit(50)
        .all()
    )


def get_oi_velocity(
    session: Session,
    index_name: str,
    strike: float,
    lookback_minutes: int = 30,
) -> Optional[float]:
    """Calculate OI velocity for a specific strike."""
    now_snaps = (
        session.query(OISnapshot)
        .filter(OISnapshot.index_name == index_name, OISnapshot.strike == strike)
        .order_by(desc(OISnapshot.timestamp))
        .first()
    )
    cutoff = datetime.utcnow() - timedelta(minutes=lookback_minutes)
    old_snaps = (
        session.query(OISnapshot)
        .filter(
            OISnapshot.index_name == index_name,
            OISnapshot.strike == strike,
            OISnapshot.timestamp <= cutoff,
        )
        .order_by(desc(OISnapshot.timestamp))
        .first()
    )
    if not now_snaps or not old_snaps:
        return None

    total_oi_now = now_snaps.call_oi + now_snaps.put_oi
    total_oi_old = old_snaps.call_oi + old_snaps.put_oi
    if total_oi_old == 0:
        return None
    return (total_oi_now - total_oi_old) / total_oi_old * 100


def save_engine_score(
    session: Session,
    index_name: str,
    engine_name: str,
    score: float,
    details: dict,
) -> None:
    """Save an engine score to database."""
    entry = EngineScore(
        index_name=index_name,
        engine_name=engine_name,
        score=score,
        details=details,
    )
    session.add(entry)


def save_signal(session: Session, signal_data: dict) -> None:
    """Save a computed signal to database."""
    entry = Signal(**signal_data)
    session.add(entry)


def save_macro_data(session: Session, macro: dict) -> None:
    """Save macro data snapshot."""
    entry = MacroData(**macro)
    session.add(entry)
