import pandas as pd
import time
import os
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import logging
from datetime import datetime

# Setup Logger
logger = logging.getLogger("CSVProcessor")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - [CSV] - %(levelname)s - %(message)s'))
logger.addHandler(handler)

class CSVBatchProcessor:
    """
    Monitors a specific CSV file for new data matching Sierra Chart export format.
    """
    def __init__(
        self, 
        file_path: str, 
        callback: Callable[[Dict[str, Any]], None],
        columns: list = ["Date", "Time", "Open", "High", "Low", "Close", "Volume", "NumTrades", "BidVol", "AskVol"],
        batch_delay: float = 1.0,
        seek_to_end: bool = False
    ):
        self.file_path = Path(file_path)
        self.callback = callback
        self.columns = columns
        self.batch_delay = batch_delay
        self.seek_to_end = seek_to_end
        self.last_pos = 0
        self._running = False
        
    def start(self):
        """Start the monitoring loop."""
        self._running = True
        logger.info(f"Starting CSV Processor watching: {self.file_path}")
        
        # Initial seek logic
        if self.file_path.exists():
            if self.seek_to_end:
                 self.last_pos = self.file_path.stat().st_size
                 logger.info(f"Seeked to end of file: {self.last_pos} bytes")
            else:
                 # Start from beginning to populate buffers
                 self.last_pos = 0
                 logger.info(f"Starting from beginning of file to populate history.")
        
        while self._running:
            try:
                self._process_updates()
            except Exception as e:
                logger.error(f"Error processing CSV: {e}")
            
            time.sleep(self.batch_delay)
            
    def stop(self):
        self._running = False
        
    def process_file_once(self):
        """Read the entire file once and modify internal state."""
        self.last_pos = 0 # Force start from beginning
        self._process_updates()
        
    def _process_updates(self):
        if not self.file_path.exists():
            return

        current_size = self.file_path.stat().st_size
        
        if current_size < self.last_pos:
            # File truncated (re-downloaded or cleared)
            self.last_pos = 0
            
        if current_size > self.last_pos:
            with open(self.file_path, "r") as f:
                f.seek(self.last_pos)
                new_lines = f.readlines()
                self.last_pos = f.tell()
                
            if new_lines:
                self._parse_lines(new_lines)
                
    def _parse_lines(self, lines):
        """Parse raw CSV lines into structured data objects."""
        # Clean lines
        data_rows = [line.strip().split(",") for line in lines if line.strip()]
        
        if not data_rows:
            return

        # Skip header if it was read as a new line (rare if seeking correctly, but possible)
        if data_rows[0][0] == self.columns[0]:
            data_rows.pop(0)
            
        for row in data_rows:
            if len(row) < 6:
                continue
                
            try:
                # Assuming Standard Formatting: Date, Time, Open, High, Low, Close...
                # Sierra Date: 2024/01/05 or 2024-01-05
                # Sierra Time: 14:00:00
                
                date_str = row[0].strip()
                time_str = row[1].strip()
                
                # Combine date time
                dt_str = f"{date_str} {time_str}"
                
                # Handle Sierra's specific format: 2025-12-9 02:05:00.000000
                try:
                    # pandas handles this format well
                    dt = pd.to_datetime(dt_str)
                    ts = int(dt.timestamp())
                except Exception:
                    # Fallback to current time if parsing fails
                    ts = int(time.time())
                
                # Sierra indices: 2=Open, 3=High, 4=Low, 5=Last (Close), 6=Volume
                candle = {
                    "open": float(row[2]),
                    "high": float(row[3]),
                    "low": float(row[4]),
                    "close": float(row[5]),
                    "volume": float(row[6]) if len(row) > 6 else 0,
                    "time": ts,
                    "symbol": "XAUUSD",
                    "delta": 0.0,
                    "max_delta": 0.0,
                    "min_delta": 0.0
                }
                
                # v4.1: Precise mapping for Sierra Study-Chain Export (70+ columns)
                # Indices (Zero-Based): Delta=18, Max Delta=25, Min Delta=26
                if len(row) >= 27:
                    try:
                        candle["delta"] = float(row[18])
                        candle["max_delta"] = float(row[25])
                        candle["min_delta"] = float(row[26])
                    except ValueError:
                        pass
                elif len(row) == 10:
                    # Standard Sierra Export: 7=Trades, 8=BidVol, 9=AskVol
                    try:
                        bid_vol = float(row[8])
                        ask_vol = float(row[9])
                        candle["delta"] = ask_vol - bid_vol
                        # For historical data without per-tick peaks:
                        candle["max_delta"] = candle["delta"]
                        candle["min_delta"] = candle["delta"]
                    except ValueError:
                        pass
                elif len(row) >= 11:
                    # Legacy CVD (Delta) Parsing: Index 11=Bid Vol, 12=Ask Vol
                    try:
                        bid_vol = float(row[11])
                        ask_vol = float(row[12])
                        candle["delta"] = ask_vol - bid_vol
                    except (ValueError, IndexError):
                        pass
                
                # v3.9: Delta Simulation Fallback (runs if delta is still 0)
                if candle["delta"] == 0 and candle["volume"] > 0:
                    rnge = candle["high"] - candle["low"]
                    if rnge > 0:
                        rel_close = candle["close"] - candle["low"]
                        ratio = rel_close / rnge
                        # Map 0..1 to -1..1
                        approx_factor = (2 * ratio) - 1
                        candle["delta"] = candle["volume"] * approx_factor
                    else:
                         # Doji/Flat bar
                         candle["delta"] = 0
                
                # Trigger callback
                self.callback(candle)
                
            except Exception as e:
                 # More descriptive error for debugging
                 # print(f"[CSVProcessor] Error parsing row in {self.file_path}: {e}") # Reduce noise
                 continue
                 
        print(f"[CSVProcessor] Processed {len(data_rows)} rows from {self.file_path}")

if __name__ == "__main__":
    # Test stub
    def printer(data):
        print(f"Update: {data}")
        
    processor = CSVBatchProcessor("test_data.csv", printer)
    # processor.start()
