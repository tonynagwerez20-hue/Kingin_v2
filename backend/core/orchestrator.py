"""Orchestrator — Task manager."""
import asyncio
import time
from typing import Optional

_engine_running = False
_engine_start_time: Optional[float] = None
_orchestrator: Optional["Orchestrator"] = None


class Orchestrator:
    def __init__(self):
        global _orchestrator
        _orchestrator = self
        self._tasks = []
    
    def start(self):
        global _engine_running, _engine_start_time
        if _engine_running:
            return {"status": "already_running"}
        _engine_running = True
        _engine_start_time = time.time()
        self._tasks.append(asyncio.create_task(self._tick_loop()))
        self._tasks.append(asyncio.create_task(self._housekeeping()))
        print("[ORCHESTRATOR] Started")
        return {"status": "started"}
    
    def stop(self):
        global _engine_running
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        _engine_running = False
        print("[ORCHESTRATOR] Stopped")
        return {"status": "stopped"}
    
    async def _tick_loop(self):
        while True:
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
    
    async def _housekeeping(self):
        while True:
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break


def start_engine():
    if _orchestrator:
        return _orchestrator.start()
    return {"status": "no_orchestrator"}


def stop_engine():
    if _orchestrator:
        return _orchestrator.stop()
    return {"status": "no_orchestrator"}


def get_status():
    return {"running": _engine_running, "state": "RUNNING" if _engine_running else "STOPPED", "uptime": time.time() - _engine_start_time if _engine_start_time else 0}