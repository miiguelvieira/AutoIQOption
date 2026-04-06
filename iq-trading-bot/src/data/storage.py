"""Armazenamento e consulta de candles em SQLite via SQLAlchemy + Pandas."""

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("asset", "timeframe", "timestamp", name="uq_candle"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset = Column(String, nullable=False, index=True)
    timeframe = Column(Integer, nullable=False, index=True)  # minutos
    timestamp = Column(DateTime, nullable=False, index=True)

    # OHLCV
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)

    # Price analysis
    spread = Column(Float, nullable=False)      # high - low
    body = Column(Float, nullable=False)         # close - open (positivo = bullish)
    body_pct = Column(Float, nullable=False)     # |body| / spread (proporção do corpo)
    upper_shadow = Column(Float, nullable=False)  # high - max(open, close)
    lower_shadow = Column(Float, nullable=False)  # min(open, close) - low
    direction = Column(String, nullable=False)    # "bull", "bear" ou "doji"


class CandleStorage:
    def __init__(self, db_path: str = "data/candles/candles.db"):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    @staticmethod
    def _parse_raw(asset: str, timeframe: int, raw: dict) -> dict:
        """Converte um candle cru da API IQ Option em registro para o banco."""
        o = raw["open"]
        h = raw["max"]
        l = raw["min"]
        c = raw["close"]
        spread = h - l
        body = c - o
        top = max(o, c)
        bot = min(o, c)

        if spread > 0:
            body_pct = abs(body) / spread
        else:
            body_pct = 0.0

        if abs(body) < spread * 0.01:
            direction = "doji"
        elif body > 0:
            direction = "bull"
        else:
            direction = "bear"

        return {
            "asset": asset,
            "timeframe": timeframe,
            "timestamp": datetime.fromtimestamp(raw["from"], tz=timezone.utc),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": raw["volume"],
            "spread": round(spread, 6),
            "body": round(body, 6),
            "body_pct": round(body_pct, 4),
            "upper_shadow": round(h - top, 6),
            "lower_shadow": round(bot - l, 6),
            "direction": direction,
        }

    def save_candles(self, asset: str, timeframe: int, candles: list[dict]) -> int:
        """Salva candles no banco. Ignora duplicatas. Retorna quantidade inserida."""
        session = self.Session()
        inserted = 0
        try:
            for raw in candles:
                parsed = self._parse_raw(asset, timeframe, raw)
                exists = (
                    session.query(Candle.id)
                    .filter_by(
                        asset=parsed["asset"],
                        timeframe=parsed["timeframe"],
                        timestamp=parsed["timestamp"],
                    )
                    .first()
                )
                if exists:
                    continue
                session.add(Candle(**parsed))
                inserted += 1
            session.commit()
            logger.info(f"{inserted}/{len(candles)} candles salvos — {asset} M{timeframe}")
        except Exception:
            session.rollback()
            logger.exception("Erro ao salvar candles")
            raise
        finally:
            session.close()
        return inserted

    def get_candles(self, asset: str, timeframe: int, limit: int = 500) -> pd.DataFrame:
        """Retorna os últimos N candles como DataFrame, ordenados por timestamp."""
        session = self.Session()
        try:
            rows = (
                session.query(Candle)
                .filter_by(asset=asset, timeframe=timeframe)
                .order_by(Candle.timestamp.desc())
                .limit(limit)
                .all()
            )
        finally:
            session.close()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame([{
            "timestamp": r.timestamp,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume,
            "spread": r.spread,
            "body": r.body,
            "body_pct": r.body_pct,
            "upper_shadow": r.upper_shadow,
            "lower_shadow": r.lower_shadow,
            "direction": r.direction,
        } for r in rows])

        return df.sort_values("timestamp").reset_index(drop=True)

    def check_if_exists(self, asset: str, timeframe: int, date: datetime) -> bool:
        """Verifica se já existe um candle para o asset/timeframe/data."""
        session = self.Session()
        try:
            return (
                session.query(Candle.id)
                .filter_by(asset=asset, timeframe=timeframe, timestamp=date)
                .first()
            ) is not None
        finally:
            session.close()
