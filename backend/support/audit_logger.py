import json
import time
from pathlib import Path
from typing import Dict, Any

class AuditLogger:
    def __init__(self, log_path: str = "storage/logs/audit.json"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(self, module: str, event: str, metadata: Dict[str, Any]):
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "module": module,
            "event": event,
            "metadata": metadata
        }
        
        # Append to file
        try:
            entries = []
            if self.log_path.exists():
                with open(self.log_path, "r") as f:
                    content = f.read().strip()
                    if content:
                        entries = json.loads(content)
            
            entries.append(entry)
            
            with open(self.log_path, "w") as f:
                json.dump(entries[-1000:], f, indent=4) # Keep last 1000 entries
        except Exception as e:
            print(f"[AuditLogger] Error logging event: {e}")
