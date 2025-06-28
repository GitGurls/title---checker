from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from schemas.telemetry import TelemetryInput
from schemas.zone import SearchZone

class ExportFormat(BaseModel):
    format_type: str = Field(..., description="pdf, csv, kml, or geojson")
    include_metadata: bool = Field(True, description="Include simulation metadata")
    include_assets: bool = Field(False, description="Include asset information")

class PDFExportRequest(BaseModel):
    simulation_id: str
    title: Optional[str] = Field("SAR Mission Report", description="Report title")
    mission_id: Optional[str] = Field(None, description="Mission identifier")
    include_map: bool = Field(True, description="Include map visualization")
    include_summary: bool = Field(True, description="Include simulation summary")
    
class ExportResponse(BaseModel):
    export_id: str
    download_url: str
    file_size_bytes: int
    created_at: datetime
    expires_at: datetime

class ScenarioData(BaseModel):
    name: str
    description: Optional[str] = None
    telemetry: TelemetryInput
    search_zone: SearchZone
    assets_deployed: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    tags: Optional[List[str]] = None

class SaveScenarioRequest(BaseModel):
    scenario: ScenarioData
    overwrite: bool = Field(False, description="Overwrite if scenario name exists")

class LoadScenarioResponse(BaseModel):
    scenario: ScenarioData
    available_actions: List[str] = Field(["re_simulate", "modify_parameters", "export"])
