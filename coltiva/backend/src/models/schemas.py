"""
Pydantic Models for Coltiva Recommendation Chatbot.

All request/response schemas for chat, crops, and farmer endpoints.

Usage:
    from models.schemas import ChatRequest, ChatResponse, CropType
    
    request = ChatRequest(message="When to plant maize?", user_id="user123")
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class CropType(str, Enum):
    """Supported crop types."""
    MAIZE = "maize"
    SESAME = "sesame"
    SUNFLOWER = "sunflower"
    SORGHUM = "sorghum"
    SOYBEANS = "soybeans"
    CASSAVA = "cassava"
    
    @classmethod
    def values(cls) -> List[str]:
        return [c.value for c in cls]


class RecommendationTopic(str, Enum):
    """Recommendation topic areas."""
    PLANTING = "planting"
    FERTILISER = "fertiliser"
    PEST = "pest"
    DISEASE = "disease"
    HARVEST = "harvest"
    VARIETIES = "varieties"
    GENERAL = "general"
    
    @classmethod
    def values(cls) -> List[str]:
        return [t.value for t in cls]


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., min_length=2, max_length=500, description="User's question or message")
    crop: Optional[str] = Field(None, description="Target crop (auto-detected if not provided)")
    user_id: str = Field(..., min_length=1, description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier for conversation tracking")
    include_farmer_context: bool = Field(False, description="Include farmer profile in response")
    
    @field_validator('message')
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()
    
    @field_validator('crop')
    @classmethod
    def validate_crop(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in CropType.values():
            raise ValueError(f"Invalid crop. Must be one of: {CropType.values()}")
        return v


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    answer: str = Field(..., description="Assistant's answer")
    crop_used: str = Field(..., description="Crop that was used")
    sources: List[str] = Field(default_factory=list, description="Data sources used")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the response")
    session_id: Optional[str] = Field(None, description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    follow_up_questions: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    farmer_context: Optional[dict] = Field(None, description="Farmer profile data if requested")


class BatchRecommendationRequest(BaseModel):
    """Request model for batch recommendations."""
    farmer_ids: List[str] = Field(..., max_length=10, description="List of farmer IDs (max 10)")
    crop: str = Field(..., description="Target crop")
    topic: str = Field(..., description="Topic for recommendation")
    
    @field_validator('farmer_ids')
    @classmethod
    def validate_farmer_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one farmer ID required")
        if len(v) > 10:
            raise ValueError("Maximum 10 farmers per batch")
        return v
    
    @field_validator('crop')
    @classmethod
    def validate_crop(cls, v: str) -> str:
        if v not in CropType.values():
            raise ValueError(f"Invalid crop. Must be one of: {CropType.values()}")
        return v


class FeedbackRequest(BaseModel):
    """Request model for feedback submission."""
    session_id: str = Field(..., description="Session identifier")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    comments: Optional[str] = Field(None, max_length=500, description="Optional comments")
    
    @field_validator('comments')
    @classmethod
    def validate_comments(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()
        return v


class FarmerProfile(BaseModel):
    """Farmer profile model."""
    id: str = Field(..., description="Unique identifier")
    phone_hash: str = Field(..., description="Hashed phone number for privacy")
    primary_crop: str = Field(..., description="Primary crop grown")
    name: Optional[str] = Field(None, description="Farmer name")
    district: str = Field(..., description="District")
    sub_county: Optional[str] = Field(None, description="Sub-county")
    village: Optional[str] = Field(None, description="Village")
    soil_ph: float = Field(6.0, ge=4.0, le=9.0, description="Soil pH")
    farm_size_acres: float = Field(1.0, ge=0.1, le=100.0, description="Farm size in acres")
    registered_at: datetime = Field(default_factory=datetime.utcnow, description="Registration timestamp")
    last_active: Optional[datetime] = Field(None, description="Last active timestamp")
    
    @field_validator('primary_crop')
    @classmethod
    def validate_primary_crop(cls, v: str) -> str:
        if v not in CropType.values():
            raise ValueError(f"Invalid crop. Must be one of: {CropType.values()}")
        return v


class CropSummary(BaseModel):
    """Summary model for crop listing."""
    name: str = Field(..., description="Crop name")
    display_name: str = Field(..., description="Display name")
    planting_season: str = Field(..., description="Planting season")
    yield_potential: str = Field(..., description="Yield potential")
    micro_dose_cost: str = Field(..., description="Micro-dose cost per acre")
    yield_increase: str = Field(..., description="Expected yield increase")
    fertiliser_method: str = Field(..., description="Recommended fertiliser method")
    varieties_count: int = Field(..., ge=0, description="Number of varieties available")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="API version")
    architecture: str = Field(..., description="Architecture type")
    crops_loaded: List[str] = Field(..., description="List of loaded crops")
    design_rules: int = Field(..., description="Number of design rules")


class TopicData(BaseModel):
    """Topic-specific data response."""
    topic: str = Field(..., description="Topic name")
    data: dict = Field(..., description="Topic data")


class VarietiesData(BaseModel):
    """Varieties data response."""
    crop: str = Field(..., description="Crop name")
    varieties: dict = Field(..., description="Varieties data")


class MicroDoseInfo(BaseModel):
    """Micro-dose fertiliser information."""
    crop: str = Field(..., description="Crop name")
    method: str = Field(..., description="Application method")
    cost_per_acre: str = Field(..., description="Cost per acre")
    yield_increase: str = Field(..., description="Expected yield increase")
    roi_message: str = Field(..., description="ROI message")
    warning: Optional[str] = Field(None, description="Warning message")


class CompareResponse(BaseModel):
    """Crop comparison response."""
    crop1: dict = Field(..., description="First crop summary")
    crop2: dict = Field(..., description="Second crop summary")


class SuggestionsResponse(BaseModel):
    """Suggested questions response."""
    crop: str = Field(..., description="Crop name")
    suggestions: List[str] = Field(..., description="List of suggested questions")


# =============================================================================
# Configuration for JSON schema generation
# =============================================================================

class Config:
    """Base configuration."""
    json_schema_extra = {
        "examples": [
            {
                "message": "When should I plant maize?",
                "crop": "maize",
                "user_id": "farmer_001",
                "session_id": "sess_abc123",
                "include_farmer_context": False
            },
            {
                "session_id": "sess_abc123",
                "rating": 5,
                "comments": "Very helpful!"
            }
        ]
    }