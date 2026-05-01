import logging
import threading
import time
from typing import List

class BufferedDiskHandler(logging.Handler):
    """
    Performance-optimized log handler for HDDs.
    Batches log messages in memory and flushes to disk in chunks.
    """
    def __init__(self, filename: str, flush_interval: float = 5.0, buffer_size: int = 50):
        super().__init__()
        self.filename = filename
        self.flush_interval = flush_interval
        self.buffer_size = buffer_size
        self.buffer: List[str] = []
        self.lock = threading.Lock()
        
        # Start background flush thread
        self.stop_event = threading.Event()
        self.flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self.flush_thread.start()

    def emit(self, record):
        try:
            msg = self.format(record)
            with self.lock:
                self.buffer.append(msg)
                if len(self.buffer) >= self.buffer_size:
                    self._flush()
        except Exception:
            self.handleError(record)

    def _flush(self):
        if not self.buffer:
            return
        
        chunk = "\n".join(self.buffer) + "\n"
        self.buffer = []
        
        try:
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write(chunk)
        except Exception as e:
            print(f"Logging error: Failed to write to {self.filename}: {e}")

    def _flush_loop(self):
        while not self.stop_event.is_set():
            time.sleep(self.flush_interval)
            with self.lock:
                self._flush()

    def close(self):
        self.stop_event.set()
        self.flush_thread.join(timeout=2)
        with self.lock:
            self._flush()
        super().close()

def setup_lite_logging(filename: str = "engine_lite.log"):
    """
    Helper to setup the system with optimized logging.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    # Add buffered handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = BufferedDiskHandler(filename)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Also add a simple stream handler for console (minimal overhead)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    return logger
