"""
Shared Farmer Model.

Pydantic model for farmer registration data.
Used across the Coltiva platform.

Usage:
    from shared.models.farmer import Farmer
    
    farmer = Farmer(
        id="farmer_001",
        phone_hash="hash123",
        primary_crop="maize",
        name="John Doe",
        district="Apac",
        sub_county="Akajul",
        farm_size_acres=1.5
    )
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CropType(str, Enum):
    """Supported crop types."""
    MAIZE = "maize"
    SESAME = "sesame"
    SUNFLOWER = "sunflower"
    SORGHUM = "sorghum"
    SOYBEANS = "soybeans"
    CASSAVA = "cassava"


class Farmer(BaseModel):
    """Farmer profile model for registration."""
    
    id: str = Field(..., description="Unique farmer identifier")
    phone_hash: str = Field(..., description="Hashed phone number")
    primary_crop: str = Field(..., description="Primary crop grown")
    name: Optional[str] = Field(None, description="Farmer name")
    district: str = Field(..., description="District of residence")
    sub_county: Optional[str] = Field(None, description="Sub-county")
    village: Optional[str] = Field(None, description="Village")
    soil_ph: float = Field(6.0, ge=4.0, le=9.0, description="Soil pH level")
    farm_size_acres: float = Field(1.0, ge=0.1, le=100.0, description="Farm size in acres")
    registered_at: datetime = Field(default_factory=datetime.utcnow, description="Registration timestamp")
    last_active: Optional[datetime] = Field(None, description="Last active timestamp")
    is_active: bool = Field(True, description="Active status")
    
    @field_validator('primary_crop')
    @classmethod
    def validate_primary_crop(cls, v: str) -> str:
        """Validate primary crop is one of the supported types."""
        valid_crops = [c.value for c in CropType]
        if v not in valid_crops:
            raise ValueError(f"Invalid crop. Must be one of: {valid_crops}")
        return v
    
    @field_validator('district')
    @classmethod
    def validate_district(cls, v: str) -> str:
        """Validate district is not empty."""
        if not v or not v.strip():
            raise ValueError("District is required")
        return v.strip()
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "farmer_001",
                "phone_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "primary_crop": "maize",
                "name": "John Doe",
                "district": "Apac",
                "sub_county": "Akajul",
                "village": "Akajul Village",
                "soil_ph": 6.0,
                "farm_size_acres": 1.5,
                "registered_at": "2025-01-15T10:30:00Z",
                "is_active": True
            }
        }


class FarmerCreateRequest(BaseModel):
    """Request model for farmer registration."""
    
    phone: str = Field(..., min_length=10, max_length=15, description="Phone number")
    name: str = Field(..., min_length=1, max_length=100, description="Farmer name")
    district: str = Field(..., min_length=1, max_length=50, description="District")
    sub_county: Optional[str] = Field(None, max_length=50, description="Sub-county")
    village: Optional[str] = Field(None, max_length=100, description="Village")
    primary_crop: str = Field(..., description="Primary crop")
    farm_size_acres: float = Field(..., ge=0.1, le=100.0, description="Farm size in acres")
    soil_ph: Optional[float] = Field(6.0, ge=4.0, le=9.0, description="Soil pH")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number format."""
        # Remove any spaces or dashes
        v = v.replace(" ", "").replace("-", "")
        if not v.isdigit():
            raise ValueError("Phone must contain only digits")
        return v
    
    @field_validator('primary_crop')
    @classmethod
    def validate_primary_crop(cls, v: str) -> str:
        """Validate primary crop."""
        valid_crops = [c.value for c in CropType]
        if v not in valid_crops:
            raise ValueError(f"Invalid crop. Must be one of: {valid_crops}")
        return v


class FarmerResponse(BaseModel):
    """Response model for farmer data."""
    
    id: str
    name: Optional[str]
    district: str
    sub_county: Optional[str]
    primary_crop: str
    farm_size_acres: float
    soil_ph: float
    is_active: bool
    registered_at: datetime
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True