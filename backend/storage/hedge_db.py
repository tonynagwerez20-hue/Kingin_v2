"""SQLite database module for Hedge trading application.

Provides persistent storage for candles, buffers, trades, and system state.
"""
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


class HedgeDB:
    """SQLite database manager for hedge trading system."""

    def __init__(self, db_path: str = "./storage/hedge.db"):
        """Initialize database connection and create tables if needed.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        
        # Performance optimizations for low-spec hardware
        try:
            from config.performance_loader import perf_config
            enable_wal = perf_config.get_bool('enable_wal_mode', True)
        except ImportError:
            enable_wal = True
        
        if enable_wal:
            # WAL mode for better concurrency and HDD performance
            self.conn.execute("PRAGMA journal_mode=WAL")
        
        # Additional optimizations
        self.conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
        self.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        self.conn.execute("PRAGMA temp_store=MEMORY")  # Use RAM for temp
        
        self._init_tables()

    def _init_tables(self):
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Candles table (OHLC data for all timeframes)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, timestamp)
            )
        """)
        
        # Buffers table (rolling buffer snapshots)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS buffers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                buffer_data TEXT NOT NULL,
                buffer_size INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Trades table (executed trades)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket INTEGER UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT ,
                entry_price REAL NOT NULL,
                exit_price REAL,
                lot_size REAL NOT NULL,
                risk_amount REAL NOT NULL,
                profit_loss REAL,
                status TEXT DEFAULT 'open',
                entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                exit_time TIMESTAMP,
                notes TEXT
            )
        """)
        
        # System state table (configs, last sync, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Aggregations log (multi-TF aggregations)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aggregations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                source_tf TEXT NOT NULL,
                target_tf TEXT NOT NULL,
                factor INTEGER NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                close_price REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()

    def insert_candle(
        self,
        symbol: str,
        timeframe: str,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        timestamp: int
    ) -> int:
        """Insert a candle into the database.
        
        Args:
            symbol: Trading symbol (e.g., 'XAUUSD')
            timeframe: Timeframe (e.g., 'M5', 'H1')
            open_price: Open price
            high_price: High price
            low_price: Low price
            close_price: Close price
            timestamp: Unix timestamp
            
        Returns:
            Row ID of inserted candle
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO candles 
            (symbol, timeframe, open_price, high_price, low_price, close_price, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (symbol, timeframe, open_price, high_price, low_price, close_price, timestamp))
        self.conn.commit()
        return cursor.lastrowid

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch recent candles.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            limit: Number of candles to fetch
            
        Returns:
            List of candle dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (symbol, timeframe, limit))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def save_buffer_snapshot(
        self,
        symbol: str,
        timeframe: str,
        buffer_data: List[Dict[str, Any]],
        buffer_size: int
    ) -> int:
        """Save a rolling buffer snapshot to database.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            buffer_data: List of candle dicts
            buffer_size: Max buffer size
            
        Returns:
            Row ID
        """
        cursor = self.conn.cursor()
        buffer_json = json.dumps(buffer_data)
        cursor.execute("""
            INSERT INTO buffers (symbol, timeframe, buffer_data, buffer_size)
            VALUES (?, ?, ?, ?)
        """, (symbol, timeframe, buffer_json, buffer_size))
        self.conn.commit()
        return cursor.lastrowid

    def load_buffer_snapshot(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Load latest buffer snapshot from database.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            Buffer data or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT buffer_data FROM buffers
            WHERE symbol = ? AND timeframe = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (symbol, timeframe))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None

    def insert_trade(
        self,
        symbol: str,
        entry_price: float,
        lot_size: float,
        risk_amount: float,
        notes: str = None
    ) -> int:
        """Record a trade entry.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            lot_size: Position size
            risk_amount: Risk amount in account currency
            notes: Optional notes
            
        Returns:
            Trade ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO trades (symbol, entry_price, lot_size, risk_amount, notes, status)
            VALUES (?, ?, ?, ?, ?, 'open')
        """, (symbol, entry_price, lot_size, risk_amount, notes))
        self.conn.commit()
        return cursor.lastrowid

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        profit_loss: float
    ) -> None:
        """Close an open trade.
        
        Args:
            trade_id: Trade ID to close
            exit_price: Exit price
            profit_loss: P&L amount
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE trades
            SET exit_price = ?, profit_loss = ?, status = 'closed', exit_time = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (exit_price, profit_loss, trade_id))
        self.conn.commit()

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Fetch all open trades.
        
        Returns:
            List of open trade dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'open'")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_trade_history(self, symbol: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch closed trades.
        
        Args:
            symbol: Optional filter by symbol
            limit: Number of trades to fetch
            
        Returns:
            List of trade dictionaries
        """
        cursor = self.conn.cursor()
        if symbol:
            cursor.execute("""
                SELECT * FROM trades
                WHERE status = 'closed' AND symbol = ?
                ORDER BY exit_time DESC
                LIMIT ?
            """, (symbol, limit))
        else:
            cursor.execute("""
                SELECT * FROM trades
                WHERE status = 'closed'
                ORDER BY exit_time DESC
                LIMIT ?
            """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def set_state(self, key: str, value: Any) -> None:
        """Store a system state key-value pair.
        
        Args:
            key: State key
            value: State value (will be JSON serialized)
        """
        cursor = self.conn.cursor()
        value_json = json.dumps(value) if not isinstance(value, str) else value
        cursor.execute("""
            INSERT OR REPLACE INTO system_state (key, value)
            VALUES (?, ?)
        """, (key, value_json))
        self.conn.commit()

    def get_state(self, key: str, default: Any = None) -> Any:
        """Retrieve a system state value.
        
        Args:
            key: State key
            default: Default value if not found
            
        Returns:
            State value or default
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                return row[0]
        return default

    def insert_aggregation(
        self,
        symbol: str,
        source_tf: str,
        target_tf: str,
        factor: int,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        timestamp: int
    ) -> int:
        """Log a multi-timeframe aggregation.
        
        Args:
            symbol: Trading symbol
            source_tf: Source timeframe
            target_tf: Target timeframe
            factor: Aggregation factor
            open_price: Aggregated open
            high_price: Aggregated high
            low_price: Aggregated low
            close_price: Aggregated close
            timestamp: Unix timestamp
            
        Returns:
            Row ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO aggregations
            (symbol, source_tf, target_tf, factor, open_price, high_price, low_price, close_price, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol, source_tf, target_tf, factor, open_price, high_price, low_price, close_price, timestamp))
        self.conn.commit()
        return cursor.lastrowid

    def upsert_trade(self, trade_data: Dict[str, Any]) -> None:
        """Insert or update a trade record based on its MT5 ticket ID.
        
        Args:
            trade_data: Dictionary containing trade information (ticket, symbol, action, etc.)
        """
        cursor = self.conn.cursor()
        
        # Standardize status
        status = trade_data.get("status", "open").lower()
        
        cursor.execute("""
            INSERT INTO trades (
                ticket, symbol, action, entry_price, exit_price, lot_size, 
                risk_amount, profit_loss, status, entry_time, exit_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticket) DO UPDATE SET
                exit_price = excluded.exit_price,
                profit_loss = excluded.profit_loss,
                status = excluded.status,
                exit_time = excluded.exit_time
        """, (
            trade_data["ticket"],
            trade_data["symbol"],
            trade_data.get("action", "LONG"),
            trade_data["entry_price"],
            trade_data.get("exit_price"),
            trade_data["lot_size"],
            trade_data.get("risk_amount", 0.0),
            trade_data.get("profit_loss", 0.0),
            status,
            trade_data.get("entry_time"),
            trade_data.get("exit_time")
        ))
        self.conn.commit()

    def get_all_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve all trades from the database.
        
        Returns:
            List of trade dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def stats(self) -> Dict[str, int]:
        """Get database statistics.
        
        Returns:
            Dictionary with table row counts
        """
        cursor = self.conn.cursor()
        stats = {}
        for table in ["candles", "buffers", "trades", "aggregations"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]
        return stats

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
