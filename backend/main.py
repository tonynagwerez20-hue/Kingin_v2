"""
KingIn Trading System — Backend Entry Point
Run: python main.py
"""
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from contextlib import asynccontextmanager

from api.app import create_app
from core.orchestrator import Orchestrator
from data.buffers import ohlc_buffers, tick_buffer
from data.poller import start_data_poller
from license.validator import validate_license_or_exit
from license.anti_tamper import anti_tamper_or_exit


@asynccontextmanager
async def lifespan(app):
    """Application lifespan."""
    print("[STARTUP] Validating license...")
    validate_license_or_exit()
    
    print("[STARTUP] Checking security...")
    anti_tamper_or_exit()
    
    print("[STARTUP] Initializing orchestrator...")
    orch = Orchestrator()
    orch.start()
    
    print("[STARTUP] Starting data poller...")
    asyncio.create_task(start_data_poller())
    
    yield
    orch.stop()
    print("[SHUTDOWN] Done.")


def main():
    print("=" * 50)
    print("KingIn Trading System v2.0")
    print("=" * 50)
    
    app = create_app(lifespan)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()