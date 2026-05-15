"""Trades routes."""
from fastapi import APIRouter
router = APIRouter()

@router.get("/trades")
async def get_trades():
    return []

@router.get("/positions")
async def get_positions():
    return []

@router.get("/history")
async def get_history(limit: int = 50):
    return []