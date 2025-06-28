from fastapi import APIRouter, HTTPException, Body
from schemas.telemetry import TelemetryInput, SimulationResponse
from schemas.zone import HeatmapData
from services.simulation_engine import run_simulation
from services.drift_model import calculate_wind_drift_probability
from services.bayesian import BayesianUpdateEngine
from utils.geojson_exporter import generate_geojson
from cache.redis_cache import cache_simulation, get_cached_simulation
from services.real_data_ingestor import RealDataIngestor, fetch_real_aircraft_data
from services.database_manager import SARDatabase
import uuid
from datetime import datetime
import logging
from typing import Optional, List, Dict
import os

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
sar_db = SARDatabase()
data_ingestor = RealDataIngestor(openweather_api_key=os.getenv('OPENWEATHER_API_KEY'), database=sar_db)

@router.post("", response_model=SimulationResponse)
async def simulate_search_zone(
    telemetry: TelemetryInput = Body(..., example={
        "lat": 25.4,
        "lon": 87.6,
        "altitude": 35000,
        "speed": 460,
        "heading": 98,
        "fuel": 4000,
        "wind": {"speed": 15, "direction": 110},
        "time_since_contact": 900,
        "uncertainty_radius": 1.0
    })
):
    """
    Run comprehensive crash zone prediction simulation with real-time data integration.
    
    This endpoint combines multiple simulation methods with real-world data:
    - Integrates real-time wind and terrain data from APIs
    - Monte Carlo simulation for flight path uncertainty
    - Wind drift modeling for atmospheric effects  
    - Fuel consumption analysis for range estimation
    - Bayesian probability calculations
    - Stores all data for AI/ML training
    
    Returns GeoJSON with prioritized probability zones for search operations.
    """
    try:
        logger.info(f"Starting enhanced simulation for position: {telemetry.lat}, {telemetry.lon}")
        
        # Generate simulation ID
        sim_id = str(uuid.uuid4())
        
        # Store aircraft telemetry data for AI training
        aircraft_data = {
            'callsign': f'SIM_{sim_id[:8]}',
            'latitude': telemetry.lat,
            'longitude': telemetry.lon,
            'altitude': telemetry.altitude,
            'velocity': telemetry.speed * 0.514444,  # Convert to m/s
            'heading': telemetry.heading,
            'vertical_rate': 0,  # Unknown for simulation
            'last_contact': datetime.now(),
            'uncertainty_radius': telemetry.uncertainty_radius,
            'fuel_remaining': telemetry.fuel,
            'time_since_contact': telemetry.time_since_contact
        }
        aircraft_id = await sar_db.store_aircraft_data(aircraft_data)
        
        # Fetch and store real-time environmental data
        try:
            # Try to get cached environmental data first
            cached_env_data = await sar_db.get_cached_environmental_data(
                telemetry.lat, telemetry.lon, radius_km=50
            )
            
            if cached_env_data:
                logger.info("Using cached environmental data")
                wind_data = cached_env_data.get('wind_data', {})
                terrain_data = cached_env_data.get('terrain_data', {})
            else:
                logger.info("Fetching fresh environmental data")
                # Fetch real-time wind data
                wind_data = await data_ingestor.fetch_wind_data(telemetry.lat, telemetry.lon)
                
                # Fetch terrain data
                terrain_data = await data_ingestor.fetch_terrain_data(telemetry.lat, telemetry.lon)
                
                # Store environmental data in database
                env_data = {
                    'latitude': telemetry.lat,
                    'longitude': telemetry.lon,
                    'wind_speed': wind_data.get('speed', telemetry.wind.speed),
                    'wind_direction': wind_data.get('deg', telemetry.wind.direction),
                    'temperature': wind_data.get('temp', 20),
                    'pressure': wind_data.get('pressure', 1013),
                    'humidity': wind_data.get('humidity', 50),
                    'visibility': wind_data.get('visibility', 10000),
                    'elevation': terrain_data.get('elevation', 0),
                    'terrain_roughness': terrain_data.get('roughness', 0.1)
                }
                await sar_db.store_environmental_data(env_data)
                
            # Use real-time data if available, otherwise use provided telemetry
            enhanced_telemetry = telemetry.copy()
            if wind_data:
                enhanced_telemetry.wind.speed = wind_data.get('speed', telemetry.wind.speed)
                enhanced_telemetry.wind.direction = wind_data.get('deg', telemetry.wind.direction)
                
        except Exception as e:
            logger.warning(f"Failed to fetch real-time data, using provided telemetry: {str(e)}")
            enhanced_telemetry = telemetry
        
        # Run core Monte Carlo simulation with enhanced data
        zones = await run_simulation(enhanced_telemetry, n_simulations=2000)
        
        # Calculate wind drift probability
        drift_positions = await calculate_wind_drift_probability(enhanced_telemetry, n_simulations=500)
        
        # Generate comprehensive GeoJSON with metadata
        simulation_metadata = {
            "simulation_id": sim_id,
            "aircraft_id": aircraft_id,
            "method": "monte_carlo_wind_drift_bayesian_realtime",
            "iterations": 2000,
            "drift_simulations": 500,
            "input_parameters": enhanced_telemetry.dict(),
            "real_time_data_used": wind_data is not None,
            "generated_at": datetime.now().isoformat()
        }
        
        geojson = generate_geojson(zones, metadata=simulation_metadata)
        
        # Create summary statistics
        summary = {
            "total_zones": len(zones),
            "max_probability": max([z.get("probability", 0) for z in zones]) if zones else 0,
            "total_area_km2": sum([z.get("area_km2", 0) for z in zones]) if zones else 0,
            "primary_search_zones": len([z for z in zones if z.get("probability", 0) > 0.7]),
            "wind_drift_factor": "included",
            "fuel_endurance_hours": calculate_fuel_endurance(telemetry.fuel, telemetry.speed),
            "position_uncertainty_nm": telemetry.uncertainty_radius,
            "real_time_enhancement": wind_data is not None
        }
        
        # Store simulation results for AI training
        simulation_result = {
            'simulation_id': sim_id,
            'aircraft_id': aircraft_id,
            'input_telemetry': enhanced_telemetry.dict(),
            'predicted_zones': zones,
            'geojson_output': geojson,
            'summary_stats': summary,
            'method_used': 'monte_carlo_wind_drift_bayesian_realtime',
            'n_simulations': 2000,
            'real_time_data_used': wind_data is not None
        }
        await sar_db.store_simulation_result(simulation_result)
        
        # Prepare response
        response_data = {
            "simulation_id": sim_id,
            "geojson": geojson,
            "summary": summary,
            "timestamp": datetime.now(),
            "parameters_used": enhanced_telemetry
        }
        
        # Cache result for later retrieval
        await cache_simulation(sim_id, response_data)
        logger.info(f"Enhanced simulation completed successfully: {sim_id}")
        
        return SimulationResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Enhanced simulation failed: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Enhanced simulation failed: {str(e)}"
        )

@router.get("/heatmap/{sim_id}", response_model=dict)
async def get_heatmap(sim_id: str):
    """Retrieve cached simulation results as heatmap data"""
    try:
        cached_data = await get_cached_simulation(sim_id)
        if not cached_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Simulation {sim_id} not found or expired"
            )
        
        return {
            "simulation_id": sim_id,
            "geojson": cached_data.get("geojson", {}),
            "summary": cached_data.get("summary", {}),
            "retrieved_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Heatmap retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

@router.post("/update", response_model=SimulationResponse) 
async def update_with_evidence(
    sim_id: str,
    evidence: dict = Body(..., example={
        "lat": 25.5,
        "lon": 87.7, 
        "type": "debris",
        "confidence": 0.8,
        "reliability": 0.9,
        "timestamp": "2025-06-27T12:00:00Z"
    })
):
    """
    Update existing simulation with new evidence using Bayesian inference.
    
    Evidence types:
    - debris: Physical wreckage found
    - signal: Emergency beacon or radio signal
    - sighting: Visual confirmation or witness report
    - negative: Searched area with no findings
    """
    try:
        # Retrieve existing simulation
        cached_data = await get_cached_simulation(sim_id)
        if not cached_data:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation {sim_id} not found"
            )
        
        # Extract prior zones from GeoJSON
        prior_zones = cached_data.get("geojson", {}).get("features", [])
        
        # Apply Bayesian update
        bayesian_engine = BayesianUpdateEngine()
        updated_zones = await bayesian_engine.update_probability_with_evidence(
            prior_zones, evidence
        )
        
        # Generate new simulation ID for updated results
        new_sim_id = str(uuid.uuid4())
        
        # Create updated GeoJSON
        update_metadata = {
            "simulation_id": new_sim_id,
            "parent_simulation": sim_id,
            "method": "bayesian_evidence_update",
            "evidence_incorporated": evidence,
            "updated_at": datetime.now().isoformat()
        }
        
        updated_geojson = generate_geojson(updated_zones, metadata=update_metadata)
        
        # Update summary
        updated_summary = {
            "total_zones": len(updated_zones),
            "evidence_type": evidence.get("type", "unknown"),
            "evidence_confidence": evidence.get("confidence", 0),
            "update_method": "bayesian_inference",
            "parent_simulation": sim_id
        }
        
        # Prepare response
        response_data = {
            "simulation_id": new_sim_id,
            "geojson": updated_geojson,
            "summary": updated_summary,
            "timestamp": datetime.now(),
            "parameters_used": cached_data.get("parameters_used", {})
        }
        
        # Cache updated results
        await cache_simulation(new_sim_id, response_data)
        
        logger.info(f"Simulation updated with {evidence.get('type')} evidence: {new_sim_id}")
        return SimulationResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Evidence update failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@router.get("/active")
async def list_active_simulations():
    """List all active simulation IDs and their basic information"""
    # This would typically query the cache or database for active simulations
    # For now, return a placeholder response
    return {
        "active_simulations": [],
        "total_count": 0,
        "cache_status": "operational",
        "message": "No active simulations found"
    }

@router.post("/real-time", response_model=SimulationResponse)
async def simulate_with_real_time_data(
    prefer_cache: bool = True,
    max_cache_age_hours: int = 6
):
    """
    Run SAR simulation using real-time aircraft and environmental data.
    
    This endpoint automatically:
    - Fetches live aircraft data from OpenSky Network
    - Gets current weather/wind data from OpenWeatherMap  
    - Retrieves terrain elevation data
    - Stores all data in database for AI/ML training
    - Uses intelligent caching to minimize API calls
    - Runs full Monte Carlo simulation with real data
    
    Perfect for real SAR operations and data collection.
    """
    try:
        logger.info("Starting real-time SAR simulation")
        
        # Get real-time data with intelligent caching
        real_data = data_ingestor.build_simulation_input_with_cache(
            prefer_cache=prefer_cache,
            max_cache_age_hours=max_cache_age_hours
        )
        
        if not real_data:
            raise HTTPException(
                status_code=503, 
                detail="Unable to fetch real aircraft data. No suitable aircraft found or APIs unavailable."
            )
        
        # Convert to TelemetryInput format
        telemetry = TelemetryInput(
            lat=real_data["lat"],
            lon=real_data["lon"],
            altitude=real_data["altitude"],
            speed=real_data["speed"],
            heading=real_data["heading"],
            fuel=real_data["fuel"],
            wind={
                "speed": real_data["wind"]["speed"],
                "direction": real_data["wind"]["direction"]
            },
            time_since_contact=real_data["time_since_contact"],
            uncertainty_radius=real_data["uncertainty_radius"]
        )
        
        # Generate simulation ID
        sim_id = str(uuid.uuid4())
        
        logger.info(f"Running simulation for real aircraft: {real_data['data_source']['aircraft_callsign']}")
        
        # Run Monte Carlo simulation
        simulation_result = await run_simulation(telemetry, n_simulations=2000)
        
        # Enhanced simulation result with real data metadata
        enhanced_result = {
            **simulation_result,
            "simulation_id": sim_id,
            "simulation_type": "real_time_sar",
            "aircraft_info": {
                "icao24": real_data["data_source"]["aircraft_icao"],
                "callsign": real_data["data_source"]["aircraft_callsign"],
                "origin_country": real_data["data_source"]["origin_country"],
                "last_contact": real_data["data_source"]["last_contact"]
            },
            "sar_metadata": real_data["sar_metadata"],
            "data_quality": {
                "quality_grade": real_data["sar_metadata"]["data_quality"],
                "quality_score": real_data["sar_metadata"]["quality_score"],
                "warnings": real_data["sar_metadata"]["warnings"],
                "data_completeness": real_data["data_source"]["data_completeness"],
                "used_cached_data": real_data["data_source"]["used_cached_data"]
            },
            "environmental_data": {
                "wind_speed_knots": real_data["wind"]["speed"],
                "wind_direction": real_data["wind"]["direction"],
                "terrain_elevation_m": real_data["terrain_elevation"],
                "location_type": real_data["sar_metadata"]["prioritization_factors"]["location_type"],
                "search_complexity": real_data["sar_metadata"]["prioritization_factors"]["search_complexity"]
            },
            "api_status": real_data["data_source"]["api_rate_limit_status"]
        }
        
        # Store simulation result in database for AI training
        try:
            sar_db.store_simulation_result({
                "simulation_id": sim_id,
                "aircraft_icao": real_data["data_source"]["aircraft_icao"],
                "simulation_input": real_data,
                "simulation_output": enhanced_result,
                "timestamp": datetime.now(),
                "simulation_type": "real_time_sar"
            })
        except Exception as db_error:
            logger.warning(f"Failed to store simulation result in database: {str(db_error)}")
        
        logger.info(f"Real-time SAR simulation completed: {sim_id}")
        logger.info(f"Aircraft: {real_data['data_source']['aircraft_callsign']} "
                   f"({real_data['sar_metadata']['urgency_level']} urgency)")
        
        return SimulationResponse(**enhanced_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Real-time simulation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Real-time simulation failed: {str(e)}"
        )

@router.get("/test-apis")
async def test_real_time_apis():
    """
    Test all real-time data APIs to verify connectivity and data availability.
    Useful for system health checks and debugging.
    """
    try:
        ingestor = RealDataIngestor()
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "api_tests": {}
        }
        
        # Test OpenSky Network
        logger.info("Testing OpenSky Network API...")
        opensky_data = ingestor.fetch_opensky_state()
        if opensky_data:
            aircraft = ingestor.extract_first_valid_aircraft(opensky_data)
            results["api_tests"]["opensky"] = {
                "status": "success",
                "total_aircraft": len(opensky_data.get("states", [])),
                "valid_aircraft_found": aircraft is not None,
                "sample_aircraft": {
                    "callsign": aircraft.callsign if aircraft else None,
                    "icao": aircraft.icao24 if aircraft else None,
                    "position": [aircraft.latitude, aircraft.longitude] if aircraft else None
                }
            }
            
            # Test weather API if aircraft found
            if aircraft:
                wind_speed, wind_dir = ingestor.fetch_openweather_wind(aircraft.latitude, aircraft.longitude)
                results["api_tests"]["openweather"] = {
                    "status": "success" if ingestor.openweather_api_key else "fallback",
                    "wind_speed_ms": wind_speed,
                    "wind_direction_deg": wind_dir,
                    "api_key_provided": ingestor.openweather_api_key is not None
                }
                
                # Test elevation API
                elevation = ingestor.fetch_open_elevation(aircraft.latitude, aircraft.longitude)
                results["api_tests"]["open_elevation"] = {
                    "status": "success",
                    "elevation_meters": elevation
                }
        else:
            results["api_tests"]["opensky"] = {
                "status": "failed",
                "error": "No aircraft data available"
            }
        
        return results
        
    except Exception as e:
        logger.error(f"API test failed: {str(e)}")
        return {
            "timestamp": datetime.now().isoformat(),
            "status": "failed", 
            "error": str(e)
        }

def calculate_fuel_endurance(fuel_liters: float, speed_knots: float) -> float:
    """Calculate approximate fuel endurance in hours"""
    try:
        # Simplified fuel consumption calculation
        # Typical consumption: ~200-400 gallons per hour for commercial aircraft
        fuel_gallons = fuel_liters * 0.264172  # Convert liters to gallons
        consumption_rate = 300  # gallons per hour (average)
        
        endurance_hours = fuel_gallons / consumption_rate
        return round(endurance_hours, 2)
        
    except (TypeError, ZeroDivisionError):
        return 0.0

@router.get("/monitor/active-aircraft")
async def monitor_active_aircraft():
    """
    Monitor currently active aircraft for potential SAR scenarios.
    Returns prioritized list of aircraft based on SAR research criteria.
    """
    try:
        ingestor = RealDataIngestor()
        
        # Fetch all aircraft data
        opensky_data = ingestor.fetch_opensky_state()
        if not opensky_data:
            raise HTTPException(
                status_code=503,
                detail="Aircraft tracking data unavailable"
            )
        
        # Get all valid aircraft
        states = opensky_data.get('states', [])
        all_aircraft = []
        
        for state_array in states:
            try:
                if len(state_array) < 17:
                    continue
                
                aircraft = AircraftState(*state_array[:17])
                
                # Only include airborne aircraft with complete data
                if (aircraft.latitude is not None and 
                    aircraft.longitude is not None and
                    aircraft.baro_altitude is not None and
                    aircraft.velocity is not None and
                    aircraft.true_track is not None and
                    not aircraft.on_ground):
                    
                    # Convert to readable format
                    aircraft_info = {
                        "icao24": aircraft.icao24,
                        "callsign": aircraft.callsign or "Unknown",
                        "origin_country": aircraft.origin_country,
                        "position": {
                            "lat": aircraft.latitude,
                            "lon": aircraft.longitude,
                            "altitude_ft": aircraft.baro_altitude * 3.28084,
                        },
                        "velocity": {
                            "speed_knots": aircraft.velocity * 1.94384,
                            "heading": aircraft.true_track,
                            "vertical_rate": aircraft.vertical_rate
                        },
                        "last_contact": datetime.fromtimestamp(aircraft.last_contact).isoformat(),
                        "time_since_contact": int(time.time() - aircraft.last_contact)
                    }
                    
                    # Add SAR priority assessment
                    validation = ingestor.validate_aircraft_for_sar(aircraft)
                    aircraft_info["sar_assessment"] = {
                        "priority_level": _calculate_sar_priority_level(aircraft),
                        "data_quality": validation["quality_grade"],
                        "alerts": _check_aircraft_alerts(aircraft)
                    }
                    
                    all_aircraft.append(aircraft_info)
                    
            except Exception as e:
                logger.debug(f"Skipping aircraft due to error: {str(e)}")
                continue
        
        # Sort by SAR priority (highest first)
        prioritized_aircraft = sorted(
            all_aircraft, 
            key=lambda x: _get_priority_score(x["sar_assessment"]["priority_level"]), 
            reverse=True
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_aircraft_tracked": len(prioritized_aircraft),
            "high_priority_aircraft": len([a for a in prioritized_aircraft if a["sar_assessment"]["priority_level"] in ["HIGH", "CRITICAL"]]),
            "aircraft": prioritized_aircraft[:50],  # Limit to top 50 for performance
            "monitoring_status": "active",
            "data_source": "opensky_network"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Aircraft monitoring failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Monitoring failed: {str(e)}")

@router.post("/emergency/detect-anomalies")
async def detect_aircraft_anomalies():
    """
    Detect potential emergency situations based on aircraft behavior patterns.
    Uses research-based anomaly detection for SAR early warning.
    """
    try:
        ingestor = RealDataIngestor()
        
        # Fetch current aircraft data
        opensky_data = ingestor.fetch_opensky_state()
        if not opensky_data:
            raise HTTPException(
                status_code=503,
                detail="Aircraft data unavailable for anomaly detection"
            )
        
        anomalies = []
        states = opensky_data.get('states', [])
        
        for state_array in states:
            try:
                if len(state_array) < 17:
                    continue
                
                aircraft = AircraftState(*state_array[:17])
                
                if (aircraft.latitude and aircraft.longitude and 
                    aircraft.baro_altitude and not aircraft.on_ground):
                    
                    # Detect various anomaly patterns
                    detected_anomalies = _detect_flight_anomalies(aircraft)
                    
                    if detected_anomalies:
                        anomaly_report = {
                            "aircraft": {
                                "icao24": aircraft.icao24,
                                "callsign": aircraft.callsign or "Unknown",
                                "position": [aircraft.latitude, aircraft.longitude],
                                "altitude_ft": aircraft.baro_altitude * 3.28084,
                                "speed_knots": aircraft.velocity * 1.94384 if aircraft.velocity else 0
                            },
                            "anomalies": detected_anomalies,
                            "severity": _assess_anomaly_severity(detected_anomalies),
                            "recommended_action": _get_recommended_action(detected_anomalies),
                            "detection_time": datetime.now().isoformat()
                        }
                        anomalies.append(anomaly_report)
                        
            except Exception as e:
                logger.debug(f"Error processing aircraft for anomalies: {str(e)}")
                continue
        
        # Sort by severity
        anomalies.sort(key=lambda x: _get_severity_score(x["severity"]), reverse=True)
        
        return {
            "detection_timestamp": datetime.now().isoformat(),
            "total_anomalies_detected": len(anomalies),
            "critical_anomalies": len([a for a in anomalies if a["severity"] == "CRITICAL"]),
            "anomalies": anomalies,
            "status": "monitoring_active"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Anomaly detection failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {str(e)}")

@router.get("/training-data/export", response_model=dict)
async def export_training_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = 1000,
    include_features: bool = True
):
    """
    Export historical simulation and environmental data for AI model training.
    
    Returns structured data optimized for machine learning including:
    - Aircraft telemetry features
    - Environmental conditions
    - Simulation results and outcomes
    - Feature engineering for model training
    """
    try:
        logger.info(f"Exporting training data with limit: {limit}")
        
        # Parse date filters
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None
        
        # Get training data from database
        training_data = await sar_db.get_training_data(
            start_date=start_dt,
            end_date=end_dt,
            limit=limit,
            include_features=include_features
        )
        
        # Generate metadata
        metadata = {
            "export_timestamp": datetime.now().isoformat(),
            "record_count": len(training_data),
            "date_range": {
                "start": start_date,
                "end": end_date
            },
            "features_included": include_features,
            "data_schema": {
                "aircraft_features": [
                    "latitude", "longitude", "altitude", "velocity", "heading",
                    "fuel_remaining", "time_since_contact", "uncertainty_radius"
                ],
                "environmental_features": [
                    "wind_speed", "wind_direction", "temperature", "pressure",
                    "humidity", "visibility", "elevation", "terrain_roughness"
                ],
                "target_variables": [
                    "predicted_zones", "crash_probability", "search_area_km2"
                ]
            }
        }
        
        return {
            "metadata": metadata,
            "training_data": training_data,
            "export_id": str(uuid.uuid4())
        }
        
    except Exception as e:
        logger.error(f"Failed to export training data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export training data: {str(e)}"
        )

@router.get("/analytics/summary", response_model=dict)
async def get_analytics_summary():
    """
    Get analytics summary of stored data for model training insights.
    
    Returns statistics about:
    - Total simulations run
    - Data quality metrics
    - Feature distributions
    - Model training readiness
    """
    try:
        logger.info("Generating analytics summary")
        
        # Get summary statistics from database
        summary = await sar_db.get_analytics_summary()
        
        # Add training readiness assessment
        training_readiness = {
            "sufficient_data": summary.get('total_simulations', 0) >= 100,
            "data_quality_score": summary.get('data_quality_score', 0),
            "feature_completeness": summary.get('feature_completeness', 0),
            "recommendation": "Ready for model training" if summary.get('total_simulations', 0) >= 100 else "Need more training data"
        }
        
        return {
            "summary": summary,
            "training_readiness": training_readiness,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get analytics summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analytics summary: {str(e)}"
        )

@router.post("/data-cleanup", response_model=dict)
async def cleanup_old_data(
    days_old: int = 30,
    dry_run: bool = True
):
    """
    Clean up old cached data and expired simulation results.
    
    Removes data older than specified days to maintain database performance.
    Use dry_run=True to see what would be deleted without actually deleting.
    """
    try:
        logger.info(f"Starting data cleanup - days_old: {days_old}, dry_run: {dry_run}")
        
        # Perform cleanup
        cleanup_result = await sar_db.cleanup_old_data(
            days_old=days_old,
            dry_run=dry_run
        )
        
        return {
            "cleanup_summary": cleanup_result,
            "dry_run": dry_run,
            "cleanup_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cleanup data: {str(e)}"
        )
        
def _calculate_sar_priority_level(aircraft: 'AircraftState') -> str:
    """Calculate SAR priority level based on aircraft characteristics"""
    score = 0
    
    # Altitude factor
    if aircraft.baro_altitude:
        alt_ft = aircraft.baro_altitude * 3.28084
        if alt_ft > 35000:
            score += 3
        elif alt_ft > 20000:
            score += 2
        else:
            score += 1
    
    # Speed factor
    if aircraft.velocity:
        speed_knots = aircraft.velocity * 1.94384
        if speed_knots > 400:
            score += 3
        elif speed_knots > 200:
            score += 2
        else:
            score += 1
    
    # Time since contact
    time_since_contact = time.time() - aircraft.last_contact
    if time_since_contact > 3600:
        score += 4
    elif time_since_contact > 1800:
        score += 2
    else:
        score += 1
    
    # Geographic factor (simplified)
    if aircraft.latitude and aircraft.longitude:
        lat, lon = aircraft.latitude, aircraft.longitude
        # Ocean areas get higher priority
        if (-70 < lon < 20 and 0 < lat < 70) or \
           (-180 < lon < -70 and -60 < lat < 70) or \
           (20 < lon < 120 and -60 < lat < 30):
            score += 3
        else:
            score += 1
    
    if score >= 12:
        return "CRITICAL"
    elif score >= 8:
        return "HIGH"
    elif score >= 5:
        return "MEDIUM"
    else:
        return "LOW"

def _check_aircraft_alerts(aircraft: 'AircraftState') -> List[str]:
    """Check for alert conditions on aircraft"""
    alerts = []
    
    # Check for emergency squawk codes
    if aircraft.squawk:
        if aircraft.squawk == "7700":
            alerts.append("EMERGENCY_SQUAWK")
        elif aircraft.squawk == "7600":
            alerts.append("RADIO_FAILURE")
        elif aircraft.squawk == "7500":
            alerts.append("HIJACK_ALERT")
    
    # Check for unusual altitude
    if aircraft.baro_altitude:
        alt_ft = aircraft.baro_altitude * 3.28084
        if alt_ft > 50000:
            alerts.append("EXCESSIVE_ALTITUDE")
        elif alt_ft < 1000 and not aircraft.on_ground:
            alerts.append("LOW_ALTITUDE")
    
    # Check for unusual speed
    if aircraft.velocity:
        speed_knots = aircraft.velocity * 1.94384
        if speed_knots > 600:
            alerts.append("EXCESSIVE_SPEED")
        elif speed_knots < 100 and not aircraft.on_ground:
            alerts.append("LOW_SPEED")
    
    # Check for rapid descent
    if aircraft.vertical_rate and aircraft.vertical_rate < -3000:
        alerts.append("RAPID_DESCENT")
    
    return alerts

def _detect_flight_anomalies(aircraft: 'AircraftState') -> List[Dict[str, str]]:
    """Detect flight anomalies based on research patterns"""
    anomalies = []
    
    # Emergency squawk detection
    if aircraft.squawk in ["7700", "7600", "7500"]:
        anomalies.append({
            "type": "emergency_squawk",
            "description": f"Emergency squawk code {aircraft.squawk} detected",
            "severity": "CRITICAL"
        })
    
    # Altitude anomalies
    if aircraft.baro_altitude:
        alt_ft = aircraft.baro_altitude * 3.28084
        if alt_ft > 50000:
            anomalies.append({
                "type": "excessive_altitude",
                "description": f"Aircraft at unusually high altitude: {alt_ft:.0f} ft",
                "severity": "HIGH"
            })
        elif alt_ft < 500 and not aircraft.on_ground:
            anomalies.append({
                "type": "very_low_altitude",
                "description": f"Aircraft at very low altitude: {alt_ft:.0f} ft",
                "severity": "HIGH"
            })
    
    # Speed anomalies
    if aircraft.velocity:
        speed_knots = aircraft.velocity * 1.94384
        if speed_knots > 700:
            anomalies.append({
                "type": "excessive_speed",
                "description": f"Aircraft at excessive speed: {speed_knots:.0f} knots",
                "severity": "HIGH"
            })
        elif speed_knots < 80 and not aircraft.on_ground and aircraft.baro_altitude and aircraft.baro_altitude * 3.28084 > 1000:
            anomalies.append({
                "type": "stall_speed",
                "description": f"Aircraft at potential stall speed: {speed_knots:.0f} knots",
                "severity": "CRITICAL"
            })
    
    # Rapid descent detection
    if aircraft.vertical_rate and aircraft.vertical_rate < -4000:
        anomalies.append({
            "type": "rapid_descent",
            "description": f"Rapid descent detected: {aircraft.vertical_rate:.0f} ft/min",
            "severity": "CRITICAL"
        })
    
    # Old contact time
    time_since_contact = time.time() - aircraft.last_contact
    if time_since_contact > 7200:  # 2 hours
        anomalies.append({
            "type": "stale_data",
            "description": f"No contact for {time_since_contact/3600:.1f} hours",
            "severity": "MEDIUM"
        })
    
    return anomalies

def _assess_anomaly_severity(anomalies: List[Dict[str, str]]) -> str:
    """Assess overall severity of detected anomalies"""
    if not anomalies:
        return "NONE"
    
    severities = [a["severity"] for a in anomalies]
    
    if "CRITICAL" in severities:
        return "CRITICAL"
    elif "HIGH" in severities:
        return "HIGH"
    elif "MEDIUM" in severities:
        return "MEDIUM"
    else:
        return "LOW"

def _get_recommended_action(anomalies: List[Dict[str, str]]) -> str:
    """Get recommended action based on anomalies"""
    severity = _assess_anomaly_severity(anomalies)
    
    actions = {
        "CRITICAL": "Immediate SAR response required - contact aviation authorities",
        "HIGH": "Enhanced monitoring and prepare SAR assets",
        "MEDIUM": "Continue monitoring and verify aircraft status",
        "LOW": "Standard monitoring procedures",
        "NONE": "No action required"
    }
    
    return actions.get(severity, "Monitor situation")

def _get_priority_score(priority_level: str) -> int:
    """Convert priority level to numeric score for sorting"""
    scores = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    return scores.get(priority_level, 0)

def _get_severity_score(severity: str) -> int:
    """Convert severity to numeric score for sorting"""
    scores = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}
    return scores.get(severity, 0)

# Import the AircraftState from the ingestor
from services.real_data_ingestor import AircraftState
import time

@router.post("/real-time", response_model=SimulationResponse)
async def simulate_with_real_time_data(
    prefer_cache: bool = True,
    max_cache_age_hours: int = 6
):
    """
    Run SAR simulation using real-time aircraft and environmental data.
    
    This endpoint automatically:
    - Fetches live aircraft data from OpenSky Network
    - Gets current weather/wind data from OpenWeatherMap  
    - Retrieves terrain elevation data
    - Stores all data in database for AI/ML training
    - Uses intelligent caching to minimize API calls
    - Runs full Monte Carlo simulation with real data
    
    Perfect for real SAR operations and data collection.
    """
    try:
        logger.info("Starting real-time SAR simulation")
        
        # Get real-time data with intelligent caching
        real_data = data_ingestor.build_simulation_input_with_cache(
            prefer_cache=prefer_cache,
            max_cache_age_hours=max_cache_age_hours
        )
        
        if not real_data:
            raise HTTPException(
                status_code=503, 
                detail="Unable to fetch real aircraft data. No suitable aircraft found or APIs unavailable."
            )
        
        # Convert to TelemetryInput format
        telemetry = TelemetryInput(
            lat=real_data["lat"],
            lon=real_data["lon"],
            altitude=real_data["altitude"],
            speed=real_data["speed"],
            heading=real_data["heading"],
            fuel=real_data["fuel"],
            wind={
                "speed": real_data["wind"]["speed"],
                "direction": real_data["wind"]["direction"]
            },
            time_since_contact=real_data["time_since_contact"],
            uncertainty_radius=real_data["uncertainty_radius"]
        )
        
        # Generate simulation ID
        sim_id = str(uuid.uuid4())
        
        logger.info(f"Running simulation for real aircraft: {real_data['data_source']['aircraft_callsign']}")
        
        # Run Monte Carlo simulation
        simulation_result = await run_simulation(telemetry, n_simulations=2000)
        
        # Enhanced simulation result with real data metadata
        enhanced_result = {
            **simulation_result,
            "simulation_id": sim_id,
            "simulation_type": "real_time_sar",
            "aircraft_info": {
                "icao24": real_data["data_source"]["aircraft_icao"],
                "callsign": real_data["data_source"]["aircraft_callsign"],
                "origin_country": real_data["data_source"]["origin_country"],
                "last_contact": real_data["data_source"]["last_contact"]
            },
            "sar_metadata": real_data["sar_metadata"],
            "data_quality": {
                "quality_grade": real_data["sar_metadata"]["data_quality"],
                "quality_score": real_data["sar_metadata"]["quality_score"],
                "warnings": real_data["sar_metadata"]["warnings"]
            }
        }
        
        logger.info(f"Real-time SAR simulation completed: {sim_id}")
        
        return SimulationResponse(**enhanced_result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Real-time simulation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Real-time simulation failed: {str(e)}"
        )