from fastapi import APIRouter, HTTPException, BackgroundTasks
from schemas.export import PDFExportRequest, ExportResponse, ExportFormat
from utils.report_generator import generate_pdf_report, generate_csv_export
from cache.redis_cache import get_cached_simulation
import uuid
from datetime import datetime, timedelta
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/pdf", response_model=ExportResponse)
async def export_pdf_report(
    background_tasks: BackgroundTasks,
    request: PDFExportRequest
):
    """
    Generate a PDF mission report with simulation results and map visualization.
    The PDF generation runs in the background and returns a download URL.
    """
    try:
        # Validate simulation exists
        simulation_data = await get_cached_simulation(request.simulation_id)
        if not simulation_data:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        export_id = str(uuid.uuid4())
        
        # Start background PDF generation
        background_tasks.add_task(
            generate_pdf_report,
            export_id=export_id,
            simulation_data=simulation_data,
            request=request
        )
        
        return ExportResponse(
            export_id=export_id,
            download_url=f"/api/report/download/{export_id}",
            file_size_bytes=0,  # Will be updated when generation completes
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )
        
    except Exception as e:
        logger.error(f"PDF export failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@router.post("/csv")
async def export_csv_data(
    simulation_id: str,
    background_tasks: BackgroundTasks
):
    """Export simulation data as CSV for analysis"""
    try:
        simulation_data = await get_cached_simulation(simulation_id)
        if not simulation_data:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        export_id = str(uuid.uuid4())
        
        background_tasks.add_task(
            generate_csv_export,
            export_id=export_id,
            simulation_data=simulation_data
        )
        
        return {
            "export_id": export_id,
            "status": "processing",
            "download_url": f"/api/report/download/{export_id}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV export failed: {str(e)}")

@router.get("/download/{export_id}")
async def download_report(export_id: str):
    """Download generated report file"""
    # This would serve the actual file from storage
    # For now, return a placeholder response
    return {
        "message": "File download endpoint - implementation depends on file storage strategy",
        "export_id": export_id,
        "status": "ready" 
    }

@router.get("/status/{export_id}")
async def get_export_status(export_id: str):
    """Check the status of an export job"""
    # This would check the actual export status from a job queue or database
    return {
        "export_id": export_id,
        "status": "completed",  # completed, processing, failed
        "progress": 100,
        "file_size_bytes": 2048576,
        "created_at": "2025-06-27T00:00:00Z"
    }
