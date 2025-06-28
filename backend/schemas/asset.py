from pydantic import BaseModel, Field
from typing import List, Optional
from schemas.zone import Coordinate

class AssetType(BaseModel):
    name: str
    speed_knots: float = Field(..., ge=0)
    range_nm: float = Field(..., ge=0)
    search_width_nm: float = Field(..., ge=0)
    endurance_hours: float = Field(..., ge=0)

class SearchAsset(BaseModel):
    id: str
    name: str
    asset_type: AssetType
    current_location: Coordinate
    fuel_remaining: float = Field(..., ge=0, le=100, description="Fuel remaining as percentage")
    operational_status: str = Field("available", description="available, deployed, maintenance")

class AssetRequest(BaseModel):
    assets: List[SearchAsset]
    search_zones: List[dict]  # GeoJSON features
    priority_weights: Optional[dict] = Field(default={"high_prob": 0.6, "coverage": 0.3, "fuel_efficiency": 0.1})

class OptimizedRoute(BaseModel):
    asset_id: str
    waypoints: List[Coordinate]
    search_pattern: str = Field("expanding_square", description="Search pattern type")
    estimated_time_hours: float
    coverage_area_km2: float
    probability_covered: float

class AssetOptimizationResponse(BaseModel):
    routes: List[OptimizedRoute]
    total_coverage: float
    uncovered_high_prob_areas: List[dict]
    optimization_summary: dict
