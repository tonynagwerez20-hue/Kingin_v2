"""Engine control routes."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/engine/start")
async def start_engine():
    from core.orchestrator import start_engine
    return start_engine()


@router.post("/engine/stop")
async def stop_engine():
    from core.orchestrator import stop_engine
    return stop_engine()


@router.get("/engine/status")
async def get_engine_status():
    from core.orchestrator import get_status
    return get_status()