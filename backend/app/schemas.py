from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ItemBase(BaseModel):
    type: str = Field(..., pattern="^(lost|found)$")
    title: str = Field(..., min_length=2, max_length=150)
    description: str = Field(..., min_length=3)
    category: str = Field(..., max_length=50)
    primary_color: Optional[str] = None
    brand: Optional[str] = None
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    location_name: str = Field(..., min_length=2, max_length=200)
    date_occurred: str
    contact_name: str = Field(..., min_length=1, max_length=100)
    contact_email: str = Field(..., max_length=150)
    contact_phone: Optional[str] = None
    custody_location: Optional[str] = None

class ItemCreate(ItemBase):
    pass

class ItemResponse(ItemBase):
    id: int
    image_path: Optional[str] = None
    image_hash: Optional[str] = None
    status: str
    created_at: str

    class Config:
        from_attributes = True

class MatchScoreBreakdown(BaseModel):
    visual_score: float = Field(..., ge=0.0, le=1.0)
    text_score: float = Field(..., ge=0.0, le=1.0)
    geo_score: float = Field(..., ge=0.0, le=1.0)
    composite_score: float = Field(..., ge=0.0, le=1.0)
    distance_meters: Optional[float] = None
    ai_reasoning: str

class MatchResponse(BaseModel):
    id: int
    lost_item: ItemResponse
    found_item: ItemResponse
    visual_score: float
    text_score: float
    geo_score: float
    composite_score: float
    distance_meters: Optional[float]
    ai_reasoning: str
    status: str
    created_at: str

class ClaimCreate(BaseModel):
    match_id: int
    claimant_name: str
    claimant_contact: str
    secret_verification_answer: Optional[str] = None
    proof_details: Optional[str] = None

class ClaimResponse(BaseModel):
    id: int
    match_id: int
    claimant_name: str
    claimant_contact: str
    secret_verification_answer: Optional[str]
    proof_details: Optional[str]
    status: str
    created_at: str

class AIAnalyzeImageResponse(BaseModel):
    suggested_title: str
    suggested_category: str
    primary_color: str
    brand: Optional[str]
    description: str
    tags: List[str]

class SystemStatsResponse(BaseModel):
    total_lost: int
    total_found: int
    active_matches: int
    reunited_items: int
    gemini_ai_active: bool
