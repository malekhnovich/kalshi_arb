"""
Lightweight cache for Kalshi and Binance historical data.

Uses SQLite - no external dependencies, survives restarts.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import config

logger = logging.getLogger(__name__)

DB_PATH = config.LOG_DIR / "cache.db"


class DataCache:
    """SQLite-based cache for historical market data."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kalshi_trades_v2 (
                    timestamp INTEGER,
                    ticker TEXT,
                    yes_price REAL,
                    no_price REAL,
                    market_result TEXT,
                    fetched_at TEXT,
                    PRIMARY KEY (timestamp, ticker)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kalshi_candles (
                    timestamp INTEGER,
                    ticker TEXT,
                    yes_price REAL,
                    no_price REAL,
                    market_result TEXT,
                    fetched_at TEXT,
                    PRIMARY KEY (timestamp, ticker)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kalshi_candles (
                    timestamp INTEGER,
                    ticker TEXT,
                    yes_price REAL,
                    no_price REAL,
                    market_result TEXT,
                    fetched_at TEXT,
                    PRIMARY KEY (timestamp, ticker)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS binance_klines (
                    symbol TEXT,
                    timestamp INTEGER,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    fetched_at TEXT,
                    PRIMARY KEY (symbol, timestamp)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kalshi_ts ON kalshi_trades_v2(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kalshi_candles_ts ON kalshi_candles(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_binance_ts ON binance_klines(symbol, timestamp)"
            )
            conn.commit()

    # === Kalshi Trades ===

    def get_kalshi_trades(
        self, tickers: List[str], start_ts: int, end_ts: int
    ) -> Dict[int, List[Dict]]:
        """Get cached Kalshi trades for specific tickers in time range."""
        if not tickers:
            return {}

        result = {}
        batch_size = 900  # SQLite variable limit safety

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            for i in range(0, len(tickers), batch_size):
                batch = tickers[i : i + batch_size]
                placeholders = ",".join("?" for _ in batch)
                query = f"""
                    SELECT timestamp, ticker, yes_price, no_price, market_result
                    FROM kalshi_trades_v2
                    WHERE ticker IN ({placeholders}) AND timestamp BETWEEN ? AND ?
                """
                params = list(batch) + [start_ts, end_ts]

                rows = conn.execute(query, params).fetchall()
                for row in rows:
                    ts = row["timestamp"]
                    if ts not in result:
                        result[ts] = []
                    result[ts].append(
                        {
                            "yes_price": row["yes_price"],
                            "no_price": row["no_price"],
                            "market_ticker": row["ticker"],
                            "market_result": row["market_result"],
                        }
                    )
        return result

    def save_kalshi_trades(self, trades_by_ts: Dict[int, List[Dict]]):
        """Save Kalshi trades to cache."""
        if not trades_by_ts:
            return

        now = datetime.now().isoformat()
        flat_trades = []
        for ts, trade_list in trades_by_ts.items():
            for trade in trade_list:
                flat_trades.append(
                    (
                        ts,
                        trade.get("market_ticker"),
                        trade.get("yes_price"),
                        trade.get("no_price"),
                        trade.get("market_result"),
                        now,
                    )
                )

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO kalshi_trades_v2
                (timestamp, ticker, yes_price, no_price, market_result, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                flat_trades,
            )
            conn.commit()

        logger.info(f"Cached {len(flat_trades)} Kalshi trades")

    # === Kalshi Candles ===

    def get_kalshi_candles(
        self, tickers: List[str], start_ts: int, end_ts: int
    ) -> Dict[int, List[Dict]]:
        """Get cached Kalshi candles for specific tickers in time range."""
        if not tickers:
            return {}

        result = {}
        batch_size = 900  # SQLite variable limit safety

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            for i in range(0, len(tickers), batch_size):
                batch = tickers[i : i + batch_size]
                placeholders = ",".join("?" for _ in batch)
                query = f"""
                    SELECT timestamp, ticker, yes_price, no_price, market_result
                    FROM kalshi_candles
                    WHERE ticker IN ({placeholders}) AND timestamp BETWEEN ? AND ?
                """
                params = list(batch) + [start_ts, end_ts]

                rows = conn.execute(query, params).fetchall()
                for row in rows:
                    ts = row["timestamp"]
                    if ts not in result:
                        result[ts] = []
                    result[ts].append(
                        {
                            "yes_price": row["yes_price"],
                            "no_price": row["no_price"],
                            "market_ticker": row["ticker"],
                            "market_result": row["market_result"],
                        }
                    )
        return result

    def save_kalshi_candles(self, candles_by_ts: Dict[int, List[Dict]]):
        """Save Kalshi candles to cache."""
        if not candles_by_ts:
            return

        now = datetime.now().isoformat()
        flat_candles = []
        for ts, candle_list in candles_by_ts.items():
            for candle in candle_list:
                flat_candles.append(
                    (
                        ts,
                        candle.get("market_ticker"),
                        candle.get("yes_price"),
                        candle.get("no_price"),
                        candle.get("market_result"),
                        now,
                    )
                )

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO kalshi_candles
                (timestamp, ticker, yes_price, no_price, market_result, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                flat_candles,
            )
            conn.commit()

        logger.info(f"Cached {len(flat_candles)} Kalshi candles")

    def get_kalshi_latest_ts(self) -> Optional[int]:
        """Get the latest cached Kalshi timestamp."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT MAX(timestamp) FROM kalshi_trades_v2").fetchone()
            return row[0] if row and row[0] else None

    # === Binance Klines ===

    def get_binance_klines(self, symbol: str, start_ts: int, end_ts: int) -> List[List]:
        """Get cached Binance klines in time range."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT timestamp, open, high, low, close, volume
                FROM binance_klines
                WHERE symbol = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """,
                (symbol, start_ts, end_ts),
            ).fetchall()

        # Return in Binance kline format: [open_time, open, high, low, close, volume, close_time, ...]
        return [
            [
                row["timestamp"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                row["volume"],
                row["timestamp"] + 60000,
            ]
            for row in rows
        ]

    def save_binance_klines(self, symbol: str, klines: List[List]):
        """Save Binance klines to cache."""
        if not klines:
            return

        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO binance_klines
                (symbol, timestamp, open, high, low, close, volume, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    (
                        symbol,
                        int(k[0]),
                        float(k[1]),
                        float(k[2]),
                        float(k[3]),
                        float(k[4]),
                        float(k[5]),
                        now,
                    )
                    for k in klines
                ],
            )
            conn.commit()

        logger.info(f"Cached {len(klines)} Binance klines for {symbol}")

    def get_binance_latest_ts(self, symbol: str) -> Optional[int]:
        """Get the latest cached Binance timestamp for a symbol."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT MAX(timestamp) FROM binance_klines WHERE symbol = ?", (symbol,)
            ).fetchone()
            return row[0] if row and row[0] else None

    # === Utilities ===

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            kalshi_count = conn.execute(
                "SELECT COUNT(*) FROM kalshi_trades_v2"
            ).fetchone()[0]
            try:
                kalshi_candles_count = conn.execute(
                    "SELECT COUNT(*) FROM kalshi_candles"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                kalshi_candles_count = 0
            binance_count = conn.execute(
                "SELECT COUNT(*) FROM binance_klines"
            ).fetchone()[0]
            kalshi_range = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM kalshi_trades_v2"
            ).fetchone()
            binance_range = conn.execute(
                "SELECT MIN(timestamp), MAX(timestamp) FROM binance_klines"
            ).fetchone()

        return {
            "kalshi_trades": kalshi_count,
            "kalshi_candles": kalshi_candles_count,
            "binance_klines": binance_count,
            "kalshi_range": kalshi_range,
            "binance_range": binance_range,
            "db_size_mb": round(self.db_path.stat().st_size / 1024 / 1024, 2)
            if self.db_path.exists()
            else 0,
        }

    def clear(self):
        """Clear all cached data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM kalshi_trades_v2")
            conn.execute("DELETE FROM kalshi_candles")
            conn.execute("DELETE FROM binance_klines")
            conn.execute("DELETE FROM cache_meta")
            conn.commit()
        logger.info("Cache cleared")

    def clear_legacy_trades(self):
        """Clear legacy Kalshi trade data (kalshi_trades_v2) to save space."""
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM kalshi_trades_v2").fetchone()[0]
            if count > 0:
                conn.execute("DELETE FROM kalshi_trades_v2")
                conn.execute("VACUUM")  # Reclaim disk space
                conn.commit()
                logger.info(
                    f"Cleared {count} legacy Kalshi trades and vacuumed database"
                )
            else:
                logger.info("No legacy trades found to clear")


# Singleton instance
_cache: Optional[DataCache] = None


def get_cache() -> DataCache:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        _cache = DataCache()
    return _cache
