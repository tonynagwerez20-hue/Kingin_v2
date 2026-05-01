import csv
import os
import time
from pathlib import Path
from typing import Dict, Any

class SignalRecorder:
    """
    Utility to record trading signals to a CSV file for MT5 backtesting 
    and Monte Carlo stress testing.
    """
    def __init__(self, output_dir: str = "data", filename: str = "backtest_signals.csv"):
        self.project_root = Path(__file__).parent.parent.parent
        self.output_path = self.project_root / output_dir / filename
        
        # Ensure directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize file with headers if it doesn't exist
        if not self.output_path.exists():
            self._write_headers()

    def _write_headers(self):
        headers = ["Time", "Symbol", "Action", "Price", "SL", "Lots", "Desc", "MagicNumber"]
        with open(self.output_path, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)

    def record(self, signal: Dict[str, Any]):
        """
        Appends a signal dictionary to the CSV file.
        signal format expected: {action, price, sl, lots, desc, symbol, ...}
        """
        try:
            row = [
                time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
                signal.get("symbol", "XAUUSD"),
                signal.get("action"),
                signal.get("price"),
                signal.get("sl"),
                signal.get("lots"),
                signal.get("desc", ""),
                signal.get("magic", 123456)
            ]
            
            with open(self.output_path, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            print(f"[SignalRecorder] Error writing to CSV: {e}")

    def clear(self):
        """Resets the recording file."""
        self._write_headers()

# Singleton instance for easy access
recorder = SignalRecorder()
