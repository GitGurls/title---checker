from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class WindData(BaseModel):
    speed: float = Field(..., description="Wind speed in knots", ge=0, le=200)
    direction: float = Field(..., description="Wind direction in degrees", ge=0, lt=360)

class TelemetryInput(BaseModel):
    lat: float = Field(..., description="Latitude in decimal degrees", ge=-90, le=90)
    lon: float = Field(..., description="Longitude in decimal degrees", ge=-180, le=180)
    altitude: float = Field(..., description="Altitude in feet", ge=0, le=60000)
    speed: float = Field(..., description="Ground speed in knots", ge=0, le=1000)
    heading: float = Field(..., description="Aircraft heading in degrees", ge=0, lt=360)
    fuel: float = Field(..., description="Remaining fuel in liters", ge=0)
    wind: WindData
    time_since_contact: int = Field(..., description="Time since last contact in seconds", ge=0)
    uncertainty_radius: Optional[float] = Field(1.0, description="Position uncertainty in nautical miles", ge=0)
    
    class Config:
        schema_extra = {
            "example": {
                "lat": 25.4,
                "lon": 87.6,
                "altitude": 35000,
                "speed": 460,
                "heading": 98,
                "fuel": 4000,
                "wind": {
                    "speed": 15,
                    "direction": 110
                },
                "time_since_contact": 900,
                "uncertainty_radius": 1.0
            }
        }

class SimulationResponse(BaseModel):
    simulation_id: str
    geojson: dict
    summary: dict
    timestamp: datetime
    parameters_used: TelemetryInput
