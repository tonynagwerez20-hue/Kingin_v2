"""
Crops API Routes for Coltiva Recommendation Chatbot.

Endpoints:
- GET /crops - List all crops with summary
- GET /crops/{crop} - Complete knowledge for a crop
- GET /crops/{crop}/{topic} - Specific topic (planting, fertiliser, etc.)
- GET /crops/{crop}/micro-dose - Micro-dose fertiliser info
- GET /crops/compare/{crop1}/{crop2} - Compare two crops

Usage:
    from api import crops
    
    app.include_router(crops.router, prefix="/api/v1")
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException

from core.knowledge_base import (
    get_crop_names,
    get_crop_descriptions,
    get_crop_summary,
    get_topic_for_crop,
    get_micro_dose_info,
    compare_crops
)
from models.schemas import (
    CropSummary,
    TopicData,
    MicroDoseInfo,
    CompareResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# CROPS ENDPOINTS
# =============================================================================


@router.get("/crops", response_model=List[CropSummary])
async def list_crops() -> List[CropSummary]:
    """List all crops with summary information.
    
    Returns:
        List of crop summaries
    """
    summaries = []
    
    for crop_name in get_crop_names():
        summary = get_crop_summary(crop_name)
        
        summaries.append(CropSummary(
            name=summary.get("name", crop_name),
            display_name=summary.get("display_name", crop_name),
            planting_season=summary.get("planting_season", "N/A"),
            yield_potential=summary.get("yield_potential", "N/A"),
            micro_dose_cost=summary.get("micro_dose_cost", "N/A"),
            yield_increase=summary.get("yield_increase", "N/A"),
            fertiliser_method=summary.get("fertiliser_method", ""),
            varieties_count=summary.get("varieties_count", 0)
        ))
    
    return summaries


@router.get("/crops/{crop}", response_model=dict)
async def get_crop_detail(crop: str) -> dict:
    """Get complete knowledge for a crop.
    
    Includes all topics: planting, fertiliser, pest, disease, harvest, varieties.
    
    Args:
        crop: Crop name
        
    Returns:
        Complete crop knowledge
    """
    # Validate crop
    if crop not in get_crop_names():
        raise HTTPException(
            status_code=404,
            detail=f"Crop '{crop}' not found. Available: {get_crop_names()}"
        )
    
    # Get all topic data
    return {
        "crop": crop,
        "display_name": get_crop_descriptions().get(crop, crop),
        "planting": get_topic_for_crop(crop, "planting"),
        "fertiliser": get_topic_for_crop(crop, "fertiliser"),
        "pest": get_topic_for_crop(crop, "pest"),
        "disease": get_topic_for_crop(crop, "disease"),
        "harvest": get_topic_for_crop(crop, "harvest"),
        "varieties": get_topic_for_crop(crop, "varieties")
    }


@router.get("/crops/{crop}/micro-dose", response_model=MicroDoseInfo)
async def get_micro_dose(crop: str) -> MicroDoseInfo:
    """Get micro-dose fertiliser information for a crop.
    
    Args:
        crop: Crop name
        
    Returns:
        Micro-dose information
    """
    # Validate crop
    if crop not in get_crop_names():
        raise HTTPException(
            status_code=404,
            detail=f"Crop '{crop}' not found"
        )
    
    # Get micro-dose info
    info = get_micro_dose_info(crop)
    
    return MicroDoseInfo(
        crop=crop,
        method=info.get("method", ""),
        cost_per_acre=info.get("cost_per_acre", ""),
        yield_increase=info.get("yield_increase", ""),
        roi_message=info.get("roi_message", ""),
        warning=info.get("warning")
    )


@router.get("/crops/{crop}/{topic}", response_model=TopicData)
async def get_crop_topic(crop: str, topic: str) -> TopicData:
    """Get specific topic data for a crop.
    
    Args:
        crop: Crop name
        topic: Topic name (planting, fertiliser, pest, disease, harvest, varieties)
        
    Returns:
        Topic data
    """
    # Validate crop
    if crop not in get_crop_names():
        raise HTTPException(
            status_code=404,
            detail=f"Crop '{crop}' not found"
        )
    
    # Validate topic
    valid_topics = ["planting", "fertiliser", "pest", "disease", "harvest", "varieties"]
    if topic not in valid_topics:
        raise HTTPException(
            status_code=404,
            detail=f"Topic '{topic}' not found. Valid: {valid_topics}"
        )
    
    # Get topic data
    data = get_topic_for_crop(crop, topic)
    
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"No data for topic '{topic}' on crop '{crop}'"
        )
    
    return TopicData(
        topic=topic,
        data=data
    )


@router.get("/crops/{crop}/micro-dose", response_model=MicroDoseInfo)
async def get_micro_dose(crop: str) -> MicroDoseInfo:
    """Get micro-dose fertiliser information for a crop.
    
    Args:
        crop: Crop name
        
    Returns:
        Micro-dose information
    """
    # Validate crop
    if crop not in get_crop_names():
        raise HTTPException(
            status_code=404,
            detail=f"Crop '{crop}' not found"
        )
    
    # Get micro-dose info
    info = get_micro_dose_info(crop)
    
    return MicroDoseInfo(
        crop=crop,
        method=info.get("method", ""),
        cost_per_acre=info.get("cost_per_acre", ""),
        yield_increase=info.get("yield_increase", ""),
        roi_message=info.get("roi_message", ""),
        warning=info.get("warning")
    )


@router.get("/crops/compare/{crop1}/{crop2}", response_model=CompareResponse)
async def compare_two_crops(crop1: str, crop2: str) -> CompareResponse:
    """Compare two crops side by side.
    
    Args:
        crop1: First crop name
        crop2: Second crop name
        
    Returns:
        Comparison data
    """
    # Validate crops
    if crop1 not in get_crop_names():
        raise HTTPException(
            status_code=404,
            detail=f"Crop '{crop1}' not found"
        )
    
    if crop2 not in get_crop_names():
        raise HTTPException(
            status_code=404,
            detail=f"Crop '{crop2}' not found"
        )
    
    # Get comparison data
    comparison = compare_crops(crop1, crop2)
    
    return CompareResponse(
        crop1=comparison.get("crop1", {}),
        crop2=comparison.get("crop2", {})
    )


# =============================================================================
# HEALTH ENDPOINT
# =============================================================================


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint.
    
    Returns:
        Service health status
    """
    return {
        "status": "ok",
        "service": "coltiva-backend",
        "version": "2.1",
        "architecture": "no-rag",
        "crops_loaded": get_crop_names(),
        "design_rules": 8
    }