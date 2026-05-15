"""Settings routes."""
from fastapi import APIRouter
router = APIRouter()

@router.get("/settings")
async def get_settings():
    return {"mode": "MANUAL", "risk_percent": 1.0, "max_lots": 1.0}

@router.post("/settings")
async def update_settings(settings: dict):
    return {"status": "saved"}