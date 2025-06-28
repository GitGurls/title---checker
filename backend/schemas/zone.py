from pydantic import BaseModel, Field
from typing import List, Dict, Any
from datetime import datetime

class Coordinate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)

class ZonePolygon(BaseModel):
    coordinates: List[List[List[float]]]  # GeoJSON Polygon coordinates
    probability: float = Field(..., ge=0, le=1, description="Probability score for this zone")
    area_km2: float = Field(..., ge=0, description="Area of the zone in square kilometers")

class SearchZone(BaseModel):
    type: str = "FeatureCollection"
    features: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class HeatmapData(BaseModel):
    simulation_id: str
    zones: List[ZonePolygon]
    center_point: Coordinate
    total_area: float
    max_probability: float
    created_at: datetime

class ProbabilityGrid(BaseModel):
    grid_size: float = Field(0.1, description="Grid cell size in degrees")
    bounds: Dict[str, float]  # {min_lat, max_lat, min_lon, max_lon}
    probabilities: List[List[float]]  # 2D probability matrix
