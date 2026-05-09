"""
Position Tracker for Hedge Trading System.
Tracks open positions with dual storage: in-memory (primary) + database (backup).
"""

import time
from typing import Optional, Dict, Any
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from storage.hedge_db import HedgeDB
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("[PositionTracker] Warning: Database not available, using memory-only mode")


class PositionTracker:
    """
    Tracks current open position with dual storage:
    - Primary: In-memory (fast, lost on restart)
    - Backup: SQLite database (persistent)
    """
    
    def __init__(self, db_path: str = "./data/hedge.db"):
        """
        Initialize position tracker.
        
        Args:
            db_path: Path to SQLite database for backup storage
        """
        # In-memory storage (primary)
        self._position: Optional[Dict[str, Any]] = None
        
        # Database storage (backup)
        self.db = None
        if DB_AVAILABLE:
            try:
                self.db = HedgeDB(db_path)
                self._sync_from_db()
            except Exception as e:
                print(f"[PositionTracker] Database init failed: {e}")
                self.db = None
    
    def open_position(
        self, 
        direction: str, 
        symbol: str,
        entry_price: float, 
        lots: float, 
        sl: float,
        mt5_ticket: int = 0,
        ml_context: Optional[Dict] = None
    ) -> None:
        """
        Record a new open position.
        
        Args:
            direction: "LONG" or "SHORT"
            symbol: Trading symbol
            entry_price: Entry price
            lots: Position size
            sl: Stop loss price
            mt5_ticket: MT5 ticket number (optional)
        """
        self._position = {
            "direction": direction,
            "symbol": symbol,
            "entry_price": entry_price,
            "lots": lots,
            "sl": sl,
            "entry_time": time.time(),
            "mt5_ticket": mt5_ticket,
            "ml_context": ml_context
        }
        
        # Backup to database
        if self.db:
            try:
                self.db.insert_trade(
                    symbol=symbol,
                    entry_price=entry_price,
                    lot_size=lots,
                    risk_amount=0.0,  # Calculated elsewhere
                    notes=f"{direction} position, SL: {sl}"
                )
            except Exception as e:
                print(f"[PositionTracker] DB insert failed: {e}")
        
        print(f"[PositionTracker] Position opened: {direction} {symbol} @ {entry_price}, Lots: {lots}, SL: {sl}")
    
    def close_position(self, exit_price: float = 0.0, profit_loss: float = 0.0) -> None:
        """
        Close the current position.
        
        Args:
            exit_price: Exit price (optional)
            profit_loss: P&L amount (optional)
        """
        if not self._position:
            print("[PositionTracker] Warning: No position to close")
            return
        
        direction = self._position["direction"]
        symbol = self._position["symbol"]
        
        # Update database
        if self.db and exit_price > 0:
            try:
                # Find the most recent open trade
                open_trades = self.db.get_open_trades()
                if open_trades:
                    latest_trade = open_trades[-1]
                    self.db.close_trade(
                        trade_id=latest_trade["id"],
                        exit_price=exit_price,
                        profit_loss=profit_loss
                    )
            except Exception as e:
                print(f"[PositionTracker] DB close failed: {e}")
        
        print(f"[PositionTracker] Position closed: {direction} {symbol} @ {exit_price}, P&L: {profit_loss:.2f}")
        
        # Clear in-memory position
        self._position = None
    
    def has_position(self) -> bool:
        """Check if a position is currently open."""
        return self._position is not None
    
    def get_position_direction(self) -> Optional[str]:
        """Get current position direction (LONG/SHORT/None)."""
        return self._position["direction"] if self._position else None
    
    def get_position_info(self) -> Optional[Dict[str, Any]]:
        """Get full position information."""
        return self._position.copy() if self._position else None
    
    def get_symbol(self) -> Optional[str]:
        """Get current position symbol."""
        return self._position["symbol"] if self._position else None
    
    def get_entry_price(self) -> Optional[float]:
        """Get current position entry price."""
        return self._position["entry_price"] if self._position else None
    
    def get_lots(self) -> Optional[float]:
        """Get current position lot size."""
        return self._position["lots"] if self._position else None
    
    def _sync_from_db(self) -> None:
        """
        Sync position state from database on startup.
        Recovers position if system was restarted with open position.
        """
        if not self.db:
            return
        
        try:
            open_trades = self.db.get_open_trades()
            if open_trades:
                # Take the most recent open trade
                latest = open_trades[-1]
                
                # Reconstruct position from database
                # Note: Direction is stored in notes field
                notes = latest.get("notes", "")
                direction = "LONG" if "LONG" in notes else "SHORT"
                
                self._position = {
                    "direction": direction,
                    "symbol": latest["symbol"],
                    "entry_price": latest["entry_price"],
                    "lots": latest["lot_size"],
                    "sl": 0.0,  # Not stored in DB, will be recalculated
                    "entry_time": latest.get("entry_time", time.time()),
                    "mt5_ticket": 0
                }
                
                print(f"[PositionTracker] Recovered position from DB: {direction} {latest['symbol']}")
        except Exception as e:
            print(f"[PositionTracker] DB sync failed: {e}")
    
    def update_ticket(self, mt5_ticket: int) -> None:
        """
        Update MT5 ticket number for current position.
        
        Args:
            mt5_ticket: MT5 ticket number
        """
        if self._position:
            self._position["mt5_ticket"] = mt5_ticket
            print(f"[PositionTracker] Updated ticket: {mt5_ticket}")
    
    def __repr__(self) -> str:
        """String representation of tracker state."""
        if self._position:
            return f"PositionTracker({self._position['direction']} {self._position['symbol']} @ {self._position['entry_price']})"
        return "PositionTracker(No Position)"


# Singleton instance for global access
_tracker_instance: Optional[PositionTracker] = None

def get_tracker() -> PositionTracker:
    """Get or create the global position tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = PositionTracker()
    return _tracker_instance
