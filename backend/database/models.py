"""
TRADEKING — SQLAlchemy Models
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, JSON, Text, Index
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class OISnapshot(Base):
    __tablename__ = "oi_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    index_name = Column(String(20), nullable=False, index=True)
    strike = Column(Float, nullable=False)
    call_oi = Column(Integer, default=0)
    put_oi = Column(Integer, default=0)
    call_oi_change = Column(Integer, default=0)
    put_oi_change = Column(Integer, default=0)
    call_volume = Column(Integer, default=0)
    put_volume = Column(Integer, default=0)
    call_iv = Column(Float, default=0.0)
    put_iv = Column(Float, default=0.0)
    call_ltp = Column(Float, default=0.0)
    put_ltp = Column(Float, default=0.0)
    spot_price = Column(Float, nullable=False)

    __table_args__ = (
        Index("idx_oi_snap_ts_index", "timestamp", "index_name"),
    )


class EngineScore(Base):
    __tablename__ = "engine_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    index_name = Column(String(20), nullable=False, index=True)
    engine_name = Column(String(50), nullable=False)
    score = Column(Float, nullable=False)
    details = Column(JSON, default={})


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    index_name = Column(String(20), nullable=False, index=True)
    signal = Column(String(20), nullable=False)  # STRONG_CALL, CALL, WAIT, PUT, STRONG_PUT
    raw_score = Column(Float, nullable=False)
    normalized_score = Column(Float, nullable=False)
    confidence = Column(String(10), nullable=False)
    engines_bullish = Column(Integer, default=0)
    engines_bearish = Column(Integer, default=0)
    top_signal_reason = Column(Text, default="")
    ivr_gate = Column(Boolean, default=False)
    expiry_gate = Column(Boolean, default=False)
    engine_details = Column(JSON, default={})


class TradeLog(Base):
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    index_name = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)  # CALL / PUT
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    target = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    exit_timestamp = Column(DateTime, nullable=True)
    pnl = Column(Float, nullable=True)
    confluence_score = Column(Float, nullable=False)
    status = Column(String(20), default="OPEN")  # OPEN, CLOSED, STOPPED_OUT


class MacroData(Base):
    __tablename__ = "macro_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    india_vix = Column(Float, nullable=True)
    fii_cash_net = Column(Float, nullable=True)  # in crores
    dii_cash_net = Column(Float, nullable=True)
    fii_futures_net = Column(Float, nullable=True)  # contracts
    gift_nifty = Column(Float, nullable=True)
    us_futures_change_pct = Column(Float, nullable=True)
