import csv
import random
import time
from pathlib import Path

def generate_dummy_signals(filename="data/backtest_signals.csv", count=50):
    project_root = Path(__file__).parent.parent
    file_path = project_root / filename
    
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    headers = ["Time", "Symbol", "Action", "Price", "SL", "Lots", "Desc", "MagicNumber"]
    
    with open(file_path, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        balance = 10000.0
        price = 2000.0
        
        for _ in range(count):
            action = random.choice(["LONG", "SHORT"])
            price += random.uniform(-5, 5)
            sl = price - 5 if action == "LONG" else price + 5
            desc = "Dummy Trade for Stress Test"
            
            row = [
                time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
                "XAUUSD",
                action,
                round(price, 2),
                round(sl, 2),
                0.1,
                desc,
                123456
            ]
            writer.writerow(row)
            
    print(f"Generated {count} dummy signals in {file_path}")

if __name__ == "__main__":
    generate_dummy_signals()
