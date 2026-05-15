"""Market data routes."""
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/ohlc")
async def get_ohlc(tf: str = "M5", limit: int = 500, symbol: str = "XAUUSD"):
    try:
        from data.buffers import _candles_from_memory
        candles = _candles_from_memory(tf, limit, symbol)
        return {"candles": candles, "timeframe": tf, "symbol": symbol}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tick")
async def get_tick(symbol: str = "XAUUSD"):
    from data.buffers import tick_buffer
    return tick_buffer[-1] if tick_buffer else {}


@router.get("/status")
async def get_status():
    from core.orchestrator import get_status
    return get_status()