"""
COLTIVA BACKEND - MAIN APPLICATION

FastAPI application for AERIS Group's Coltiva Recommendation Chatbot.

Architecture:
- FastAPI on port 8001
- Groq LLM for recommendations
- No RAG, hardcoded knowledge base
- Supabase for farmer registration

Usage:
    cd coltiva/backend
    PYTHONPATH=. uvicorn src.main:app --reload --port 8001
"""

import logging
import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Setup path
_current = Path(__file__).resolve().parent
_root = _current.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import with package prefix - using relative imports for clarity
try:
    from src.api import chat, crops
    from src.core.knowledge_base import get_crop_names
except ImportError:
    # Fallback to absolute from project root
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from src.api import chat, crops
    from src.core.knowledge_base import get_crop_names

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Coltiva backend...")
    logger.info(f"Crops loaded: {get_crop_names()}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Coltiva backend...")


# Create FastAPI app
app = FastAPI(
    title="Coltiva Recommendation API",
    description="Agricultural recommendation chatbot for AERIS Group",
    version="2.1",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# ROUTERS
# =============================================================================

# Register chat router
app.include_router(
    chat.router,
    prefix="/api/v1",
    tags=["chat"]
)

# Register crops router
app.include_router(
    crops.router,
    prefix="/api/v1",
    tags=["crops"]
)


# =============================================================================
# HEALTH ENDPOINT
# =============================================================================


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "coltiva-backend",
        "version": "2.1",
        "crops_available": get_crop_names()
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "coltiva-backend",
        "version": "2.1",
        "endpoint": "/api/v1/chat",
        "docs": "/docs"
    }


# =============================================================================
# METADATA
# =============================================================================

__all__ = ["app"]