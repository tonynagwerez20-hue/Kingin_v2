import sys
import os
from pathlib import Path
import pandas as pd
import time

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from data.csv_processor import CSVBatchProcessor

def test_parsing():
    print("--- Testing Sierra CSV Parsing Logic ---")
    
    # Sample line from sierra_M5.txt
    sample_line = "2025-12-9, 02:05:00.000000, 4192.22, 4193.74, 4191.51, 4191.92, 738, 738, 4192.35, 4192.39, 4192.63, 419, 319, 0.00, 5.00, -11.00, 0.00, 0.00, -100, 738, -45, 9, 109, 319, 419, 7, -100, -155, -0, 738, 738, 311, 1, 16, 0, 1, -155, 53, -48, -155, -107, 0, 5, 27, 1, 107, 0, 0, 3, 3, 0, 0, 2, 0, 0, -55, 1165, 2, 4193, 30, 130, 3, 0, -53, 378, 360, 18, 1, 1, 1, 1"
    
    # Mock callback
    def mock_callback(candle):
        print("\n[SUCCESS] Parsed Candle:")
        print(f"  Time:   {pd.to_datetime(candle['time'], unit='s')} ({candle['time']})")
        print(f"  Open:   {candle['open']}")
        print(f"  High:   {candle['high']}")
        print(f"  Low:    {candle['low']}")
        print(f"  Close:  {candle['close']}")
        print(f"  Volume: {candle['volume']}")
        print(f"  Delta:  {candle.get('delta', 'N/A')}")
        
    # Pass as raw line string (mimicking readlines())
    lines = [sample_line]
    
    # Instantiate processor
    processor = CSVBatchProcessor("dummy.txt", mock_callback)
    
    # Manually trigger parsing
    processor._parse_lines(lines)

if __name__ == "__main__":
    test_parsing()
