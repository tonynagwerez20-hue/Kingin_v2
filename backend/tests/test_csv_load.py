import asyncio
from pathlib import Path
from data.csv_processor import CSVBatchProcessor

async def test_load():
    files_config = [
        ("H1", "data_feed/sierra_H1.txt"),
        ("M15", "data_feed/sierra_M15.txt"),
        ("M5", "data_feed/sierra_M5.txt")
    ]
    
    print("Testing CSV Loading...")
    for tf, path_str in files_config:
        file_path = Path(path_str)
        if not file_path.exists():
            print(f"Skipping {path_str} - Not found")
            continue
            
        print(f"Loading {path_str}...")
        try:
            def noop_cb(c):
                pass
            
            proc = CSVBatchProcessor(str(file_path), noop_cb)
            proc.process_file_once()
            print(f"Done loading {path_str}")
        except Exception as e:
            print(f"Error loading {path_str}: {e}")

if __name__ == "__main__":
    asyncio.run(test_load())
