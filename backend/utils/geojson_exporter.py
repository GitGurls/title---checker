import json
import numpy as np
from typing import List, Dict, Any, Tuple
from datetime import datetime
from shapely.geometry import Polygon, Point
import logging

logger = logging.getLogger(__name__)

def generate_geojson(zones: List[Dict[str, Any]], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Convert probability zones to GeoJSON format with proper nesting and metadata.
    
    Args:
        zones: List of zone dictionaries with coordinates and probability
        metadata: Optional metadata about the simulation
    
    Returns:
        Complete GeoJSON FeatureCollection with probability zones
    """
    features = []
    
    if not zones:
        logger.warning("No zones provided for GeoJSON generation")
        return create_empty_geojson()
    
    # Sort zones by probability (highest first for proper rendering)
    sorted_zones = sorted(zones, key=lambda z: z.get("probability", 0), reverse=True)
    
    for i, zone in enumerate(sorted_zones):
        try:
            # Validate zone structure
            if not validate_zone(zone):
                logger.warning(f"Invalid zone structure at index {i}, skipping")
                continue
            
            probability = zone.get("probability", 0.0)
            coordinates = zone.get("coordinates", [])
            
            # Create feature with comprehensive properties
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coordinates] if coordinates else []
                },
                "properties": {
                    "probability": probability,
                    "risk_level": classify_risk_level(probability),
                    "zone_rank": i + 1,
                    "area_km2": calculate_polygon_area(coordinates) if coordinates else 0,
                    "perimeter_km": calculate_polygon_perimeter(coordinates) if coordinates else 0,
                    "created_at": datetime.now().isoformat()
                }
            }
            
            # Add zone-specific metadata if available
            if 'area_km2' in zone:
                feature["properties"]["calculated_area_km2"] = zone['area_km2']
            if 'evidence_type' in zone:
                feature["properties"]["evidence_type"] = zone['evidence_type']
            
            features.append(feature)
            
        except Exception as e:
            logger.error(f"Error processing zone {i}: {str(e)}")
            continue
    
    # Create comprehensive GeoJSON with metadata
    geojson = {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "total_zones": len(features),
            "max_probability": max([f["properties"]["probability"] for f in features]) if features else 0,
            "total_area_km2": sum([f["properties"]["area_km2"] for f in features]),
            "generated_at": datetime.now().isoformat(),
            "coordinate_system": "WGS84",
            "simulation_metadata": metadata or {}
        },
        "crs": {
            "type": "name",
            "properties": {
                "name": "EPSG:4326"
            }
        }
    }
    
    return geojson

def validate_zone(zone: Dict[str, Any]) -> bool:
    """Validate zone structure and data"""
    if not isinstance(zone, dict):
        return False
    
    # Check required fields
    if "probability" not in zone or "coordinates" not in zone:
        return False
    
    # Validate probability range
    probability = zone.get("probability", 0)
    if not (0 <= probability <= 1):
        return False
    
    # Validate coordinates structure
    coordinates = zone.get("coordinates", [])
    if not isinstance(coordinates, list) or len(coordinates) < 3:
        return False
    
    # Check if coordinates form a valid polygon (at least 3 points)
    try:
        for coord in coordinates:
            if not isinstance(coord, (list, tuple)) or len(coord) != 2:
                return False
            lon, lat = coord
            if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                return False
    except (TypeError, ValueError):
        return False
    
    return True

def classify_risk_level(probability: float) -> str:
    """Classify risk level based on probability"""
    if probability >= 0.8:
        return "critical"
    elif probability >= 0.6:
        return "high"
    elif probability >= 0.4:
        return "medium"
    elif probability >= 0.2:
        return "low"
    else:
        return "minimal"

def calculate_polygon_area(coordinates: List[List[float]]) -> float:
    """Calculate polygon area in km² using Shapely"""
    try:
        if len(coordinates) < 3:
            return 0.0
        
        # Create Shapely polygon
        polygon = Polygon(coordinates)
        
        # Area in square degrees (approximate)
        area_deg2 = polygon.area
        
        # Convert to km² (rough approximation at equator)
        # 1 degree ≈ 111.32 km at equator
        area_km2 = area_deg2 * (111.32 ** 2)
        
        return round(area_km2, 2)
        
    except Exception as e:
        logger.warning(f"Failed to calculate polygon area: {str(e)}")
        return 0.0

def calculate_polygon_perimeter(coordinates: List[List[float]]) -> float:
    """Calculate polygon perimeter in km"""
    try:
        if len(coordinates) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(len(coordinates)):
            # Get current and next point (wrap around)
            p1 = coordinates[i]
            p2 = coordinates[(i + 1) % len(coordinates)]
            
            # Calculate distance using haversine formula
            distance = haversine_distance(p1[1], p1[0], p2[1], p2[0])
            total_distance += distance
        
        return round(total_distance, 2)
        
    except Exception as e:
        logger.warning(f"Failed to calculate polygon perimeter: {str(e)}")
        return 0.0

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate haversine distance between two points in km"""
    import math
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth radius in km
    earth_radius = 6371.0
    return earth_radius * c

def create_empty_geojson() -> Dict[str, Any]:
    """Create empty GeoJSON structure"""
    return {
        "type": "FeatureCollection",
        "features": [],
        "properties": {
            "total_zones": 0,
            "max_probability": 0,
            "total_area_km2": 0,
            "generated_at": datetime.now().isoformat(),
            "status": "no_zones_generated"
        }
    }

def export_geojson_to_file(geojson: Dict[str, Any], filepath: str) -> bool:
    """Export GeoJSON to file"""
    try:
        with open(filepath, 'w') as f:
            json.dump(geojson, f, indent=2)
        
        logger.info(f"GeoJSON exported to {filepath}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to export GeoJSON to file: {str(e)}")
        return False

def validate_geojson(geojson: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate GeoJSON structure and return errors if any"""
    errors = []
    
    # Check basic structure
    if not isinstance(geojson, dict):
        errors.append("GeoJSON must be a dictionary")
        return False, errors
    
    if geojson.get("type") != "FeatureCollection":
        errors.append("GeoJSON type must be 'FeatureCollection'")
    
    features = geojson.get("features", [])
    if not isinstance(features, list):
        errors.append("Features must be a list")
    
    # Validate each feature
    for i, feature in enumerate(features):
        if not isinstance(feature, dict):
            errors.append(f"Feature {i} must be a dictionary")
            continue
            
        if feature.get("type") != "Feature":
            errors.append(f"Feature {i} type must be 'Feature'")
        
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "Polygon":
            errors.append(f"Feature {i} geometry type must be 'Polygon'")
        
        coordinates = geometry.get("coordinates", [])
        if not coordinates:
            errors.append(f"Feature {i} has no coordinates")
    
    return len(errors) == 0, errors

def merge_geojson_features(geojson_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple GeoJSON FeatureCollections into one"""
    merged_features = []
    merged_metadata = {}
    
    for geojson in geojson_list:
        if geojson.get("type") == "FeatureCollection":
            merged_features.extend(geojson.get("features", []))
            
            # Merge metadata
            properties = geojson.get("properties", {})
            for key, value in properties.items():
                if key in merged_metadata:
                    if isinstance(value, (int, float)):
                        merged_metadata[key] += value
                    elif isinstance(value, list):
                        merged_metadata[key].extend(value)
                else:
                    merged_metadata[key] = value
    
    return {
        "type": "FeatureCollection",
        "features": merged_features,
        "properties": merged_metadata
    }