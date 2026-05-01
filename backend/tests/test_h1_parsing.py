import sys
from pathlib import Path
import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from data.csv_processor import CSVBatchProcessor

def test_h1_column_alignment():
    print("--- Testing H1 Column Alignment ---")
    
    # Actual line from sierra_H1.txt
    sample_h1_line = "2025-12-9, 02:00:00.000000, 4192.07, 4195.48, 4190.70, 4194.90, 13556, 13556, 4193.29, 4193.69, 4193.09, 6884, 6672"
    
    # Mock callback
    def mock_callback(candle):
        print("\n[SUCCESS] Parsed H1 Candle:")
        print(f"  Time:   {pd.to_datetime(candle['time'], unit='s')}")
        print(f"  Open:   {candle['open']}")
        print(f"  Close:  {candle['close']}")
        print(f"  Delta:  {candle.get('delta', 'N/A')}")
        
    # Instantiate processor
    processor = CSVBatchProcessor("sierra_H1.txt", mock_callback)
    
    # Prepare data (handle split correctly as the code does)
    # The code does: [line.strip().split(",") for line in lines if line.strip()]
    lines = [sample_h1_line]
    
    print(f"Raw Line Columns: {len(sample_h1_line.split(','))}")
    
    # Manually trigger parsing
    processor._parse_lines(lines)

if __name__ == "__main__":
    test_h1_column_alignment()
