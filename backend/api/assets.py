from fastapi import APIRouter, HTTPException, Body
from schemas.asset import AssetRequest, AssetOptimizationResponse, SearchAsset
from services.optimization import optimize_asset_deployment
from typing import List
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/optimize", response_model=AssetOptimizationResponse)
async def optimize_search_assets(
    request: AssetRequest = Body(..., example={
        "assets": [
            {
                "id": "ASSET_001",
                "name": "Coast Guard C-130",
                "asset_type": {
                    "name": "Fixed Wing Aircraft",
                    "speed_knots": 300,
                    "range_nm": 2400,
                    "search_width_nm": 5,
                    "endurance_hours": 8
                },
                "current_location": {"lat": 25.0, "lon": 80.0},
                "fuel_remaining": 85.0,
                "operational_status": "available"
            }
        ],
        "search_zones": [],
        "priority_weights": {
            "high_prob": 0.6,
            "coverage": 0.3,
            "fuel_efficiency": 0.1
        }
    })
):
    """
    Optimize deployment of search and rescue assets across search zones.
    Uses optimization algorithms to maximize coverage and probability of success.
    """
    try:
        logger.info(f"Optimizing deployment for {len(request.assets)} assets")
        
        # Run optimization algorithm
        optimization_result = await optimize_asset_deployment(
            assets=request.assets,
            search_zones=request.search_zones,
            priority_weights=request.priority_weights
        )
        
        return optimization_result
        
    except Exception as e:
        logger.error(f"Asset optimization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

@router.get("/status")
async def get_asset_status():
    """Get status of all registered search assets"""
    # This would typically query a database of assets
    return {
        "total_assets": 0,
        "available": 0,
        "deployed": 0,
        "maintenance": 0,
        "last_updated": "2025-06-27T00:00:00Z"
    }

@router.post("/register")
async def register_asset(asset: SearchAsset):
    """Register a new search asset in the system"""
    try:
        # This would typically save to a database
        logger.info(f"Registering new asset: {asset.name}")
        return {
            "status": "registered",
            "asset_id": asset.id,
            "message": f"Asset {asset.name} successfully registered"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration failed: {str(e)}")

@router.put("/{asset_id}/status")
async def update_asset_status(asset_id: str, status: str):
    """Update the operational status of an asset"""
    valid_statuses = ["available", "deployed", "maintenance", "offline"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    # This would typically update a database
    return {
        "asset_id": asset_id,
        "new_status": status,
        "updated_at": "2025-06-27T00:00:00Z"
    }
