from fastapi import APIRouter, HTTPException, Body
from schemas.export import ScenarioData, SaveScenarioRequest, LoadScenarioResponse
from typing import List
import json
import os
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple file-based storage for scenarios (in production, use a database)
SCENARIOS_DIR = "scenarios"

@router.post("/save")
async def save_scenario(request: SaveScenarioRequest):
    """Save a simulation scenario for later use"""
    try:
        # Ensure scenarios directory exists
        os.makedirs(SCENARIOS_DIR, exist_ok=True)
        
        scenario_file = os.path.join(SCENARIOS_DIR, f"{request.scenario.name}.json")
        
        # Check if file exists and overwrite flag
        if os.path.exists(scenario_file) and not request.overwrite:
            raise HTTPException(
                status_code=409, 
                detail=f"Scenario '{request.scenario.name}' already exists. Use overwrite=true to replace."
            )
        
        # Save scenario to file
        scenario_data = request.scenario.dict()
        scenario_data['created_at'] = datetime.now().isoformat()
        
        with open(scenario_file, 'w') as f:
            json.dump(scenario_data, f, indent=2, default=str)
        
        logger.info(f"Saved scenario: {request.scenario.name}")
        
        return {
            "status": "saved",
            "scenario_name": request.scenario.name,
            "file_path": scenario_file,
            "saved_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to save scenario: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Save failed: {str(e)}")

@router.get("/load/{scenario_name}", response_model=LoadScenarioResponse)
async def load_scenario(scenario_name: str):
    """Load a previously saved scenario"""
    try:
        scenario_file = os.path.join(SCENARIOS_DIR, f"{scenario_name}.json")
        
        if not os.path.exists(scenario_file):
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_name}' not found")
        
        with open(scenario_file, 'r') as f:
            scenario_data = json.load(f)
        
        # Convert back to Pydantic model
        scenario = ScenarioData(**scenario_data)
        
        return LoadScenarioResponse(
            scenario=scenario,
            available_actions=["re_simulate", "modify_parameters", "export", "delete"]
        )
        
    except Exception as e:
        logger.error(f"Failed to load scenario: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Load failed: {str(e)}")

@router.get("/list")
async def list_scenarios():
    """List all saved scenarios"""
    try:
        if not os.path.exists(SCENARIOS_DIR):
            return {"scenarios": []}
        
        scenarios = []
        for filename in os.listdir(SCENARIOS_DIR):
            if filename.endswith('.json'):
                scenario_name = filename[:-5]  # Remove .json extension
                file_path = os.path.join(SCENARIOS_DIR, filename)
                file_stats = os.stat(file_path)
                
                scenarios.append({
                    "name": scenario_name,
                    "created_at": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                    "modified_at": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    "size_bytes": file_stats.st_size
                })
        
        return {"scenarios": scenarios}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list scenarios: {str(e)}")

@router.delete("/{scenario_name}")
async def delete_scenario(scenario_name: str):
    """Delete a saved scenario"""
    try:
        scenario_file = os.path.join(SCENARIOS_DIR, f"{scenario_name}.json")
        
        if not os.path.exists(scenario_file):
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_name}' not found")
        
        os.remove(scenario_file)
        logger.info(f"Deleted scenario: {scenario_name}")
        
        return {
            "status": "deleted",
            "scenario_name": scenario_name,
            "deleted_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to delete scenario: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
