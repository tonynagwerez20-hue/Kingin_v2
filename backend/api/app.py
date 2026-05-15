"""FastAPI Application Factory."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app(lifespan=None) -> FastAPI:
    if lifespan:
        app = FastAPI(title="KingIn Trading API", version="2.0", lifespan=lifespan)
    else:
        app = FastAPI(title="KingIn Trading API", version="2.0")
    
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    
    from api.routes import market, engine, trades, settings
    app.include_router(market.router, prefix="/api", tags=["market"])
    app.include_router(engine.router, prefix="/api", tags=["engine"])
    app.include_router(trades.router, prefix="/api", tags=["trades"])
    app.include_router(settings.router, prefix="/api", tags=["settings"])
    
    @app.get("/health")
    async def health():
        return {"status": "ok"}
    
    return app