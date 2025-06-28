from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import uvicorn
from datetime import datetime

# Import API routers
from api import simulate, assets, report, scenario

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SAR Aircraft Disappearance Prediction System",
    description="Advanced search and rescue backend for aircraft disappearance prediction using Monte Carlo simulation, wind drift modeling, and Bayesian analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(simulate.router, prefix="/api/simulate", tags=["Simulation"])
app.include_router(assets.router, prefix="/api/assets", tags=["Asset Management"])
app.include_router(report.router, prefix="/api/report", tags=["Reports & Export"])
app.include_router(scenario.router, prefix="/api/scenario", tags=["Scenario Management"])

@app.get("/", response_model=dict)
async def health_check():
    """System health check and API information"""
    return {
        "status": "operational",
        "service": "SAR Aircraft Prediction Backend",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "simulation": "/api/simulate",
            "assets": "/api/assets", 
            "reports": "/api/report",
            "scenarios": "/api/scenario",
            "documentation": "/docs"
        }
    }

@app.get("/api/status")
async def api_status():
    """Detailed API status information"""
    return {
        "simulation_engine": "active",
        "bayesian_analysis": "active", 
        "wind_drift_model": "active",
        "asset_optimization": "active",
        "report_generation": "active",
        "cache_status": "redis_available",
        "last_updated": datetime.now().isoformat()
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please check logs for details.",
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )