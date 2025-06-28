import numpy as np
from typing import List, Dict, Any
from schemas.asset import SearchAsset, OptimizedRoute, AssetOptimizationResponse
from schemas.zone import Coordinate
import math
import logging

logger = logging.getLogger(__name__)

async def optimize_asset_deployment(
    assets: List[SearchAsset],
    search_zones: List[dict],
    priority_weights: Dict[str, float]
) -> AssetOptimizationResponse:
    """
    Optimize deployment of search assets using a greedy algorithm with priority weighting.
    This is a simplified implementation - production would use more sophisticated algorithms.
    """
    
    if not assets:
        raise ValueError("No assets provided for optimization")
    
    if not search_zones:
        return AssetOptimizationResponse(
            routes=[],
            total_coverage=0.0,
            uncovered_high_prob_areas=[],
            optimization_summary={"message": "No search zones to cover"}
        )
    
    # Extract high-probability areas from search zones
    high_prob_areas = extract_high_probability_areas(search_zones)
    
    # Filter available assets
    available_assets = [asset for asset in assets if asset.operational_status == "available"]
    
    if not available_assets:
        return AssetOptimizationResponse(
            routes=[],
            total_coverage=0.0,
            uncovered_high_prob_areas=high_prob_areas,
            optimization_summary={"message": "No available assets for deployment"}
        )
    
    # Generate optimized routes for each asset
    routes = []
    covered_areas = []
    
    for asset in available_assets:
        route = generate_asset_route(asset, high_prob_areas, covered_areas, priority_weights)
        if route:
            routes.append(route)
            covered_areas.extend(route.waypoints)
    
    # Calculate coverage metrics
    total_coverage = calculate_total_coverage(routes, high_prob_areas)
    uncovered_areas = identify_uncovered_areas(high_prob_areas, covered_areas)
    
    optimization_summary = {
        "total_assets_deployed": len(routes),
        "coverage_percentage": total_coverage * 100,
        "optimization_method": "greedy_priority_weighted",
        "execution_time_seconds": 0.1  # Placeholder
    }
    
    return AssetOptimizationResponse(
        routes=routes,
        total_coverage=total_coverage,
        uncovered_high_prob_areas=uncovered_areas,
        optimization_summary=optimization_summary
    )

def extract_high_probability_areas(search_zones: List[dict]) -> List[Coordinate]:
    """Extract coordinates of high-probability areas from GeoJSON features"""
    high_prob_areas = []
    
    for zone in search_zones:
        if zone.get("type") == "Feature":
            geometry = zone.get("geometry", {})
            properties = zone.get("properties", {})
            probability = properties.get("probability", 0.0)
            
            # Only consider areas with probability > 0.3
            if probability > 0.3 and geometry.get("type") == "Polygon":
                coordinates = geometry.get("coordinates", [])
                if coordinates:
                    # Get centroid of polygon
                    polygon_coords = coordinates[0]  # Exterior ring
                    centroid = calculate_polygon_centroid(polygon_coords)
                    high_prob_areas.append(Coordinate(lat=centroid[1], lon=centroid[0]))
    
    return high_prob_areas

def calculate_polygon_centroid(coordinates: List[List[float]]) -> List[float]:
    """Calculate centroid of a polygon"""
    if not coordinates:
        return [0.0, 0.0]
    
    x_coords = [coord[0] for coord in coordinates]
    y_coords = [coord[1] for coord in coordinates]
    
    return [sum(x_coords) / len(x_coords), sum(y_coords) / len(y_coords)]

def generate_asset_route(
    asset: SearchAsset,
    high_prob_areas: List[Coordinate],
    covered_areas: List[Coordinate],
    priority_weights: Dict[str, float]
) -> OptimizedRoute:
    """Generate an optimized search route for a single asset"""
    
    if not high_prob_areas:
        return None
    
    # Calculate fuel-limited search time
    max_search_time = calculate_max_search_time(asset)
    
    # Find uncovered areas within asset's range
    reachable_areas = find_reachable_areas(asset, high_prob_areas, covered_areas)
    
    if not reachable_areas:
        return None
    
    # Generate waypoints using a simple traveling salesman approach
    waypoints = generate_search_waypoints(asset, reachable_areas, max_search_time)
    
    # Calculate route metrics
    coverage_area = calculate_coverage_area(waypoints, asset.asset_type.search_width_nm)
    estimated_time = calculate_route_time(waypoints, asset.asset_type.speed_knots)
    probability_covered = calculate_probability_covered(waypoints, high_prob_areas)
    
    return OptimizedRoute(
        asset_id=asset.id,
        waypoints=waypoints,
        search_pattern="expanding_square",
        estimated_time_hours=estimated_time,
        coverage_area_km2=coverage_area,
        probability_covered=probability_covered
    )

def calculate_max_search_time(asset: SearchAsset) -> float:
    """Calculate maximum search time based on fuel and endurance"""
    fuel_time = asset.fuel_remaining / 100.0 * asset.asset_type.endurance_hours
    return min(fuel_time, asset.asset_type.endurance_hours * 0.8)  # 80% safety margin

def find_reachable_areas(
    asset: SearchAsset,
    high_prob_areas: List[Coordinate],
    covered_areas: List[Coordinate]
) -> List[Coordinate]:
    """Find areas within asset's operational range that aren't already covered"""
    reachable = []
    asset_pos = asset.current_location
    max_range_nm = asset.asset_type.range_nm * 0.4  # Reserve fuel for return
    
    for area in high_prob_areas:
        # Check if area is already covered
        if any(distance_nm(area, covered) < 5.0 for covered in covered_areas):
            continue
            
        # Check if area is within range
        distance = distance_nm(asset_pos, area)
        if distance <= max_range_nm:
            reachable.append(area)
    
    return reachable

def distance_nm(coord1: Coordinate, coord2: Coordinate) -> float:
    """Calculate distance between two coordinates in nautical miles"""
    lat1, lon1 = math.radians(coord1.lat), math.radians(coord1.lon)
    lat2, lon2 = math.radians(coord2.lat), math.radians(coord2.lon)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth radius in nautical miles
    earth_radius_nm = 3440.065
    return earth_radius_nm * c

def generate_search_waypoints(
    asset: SearchAsset,
    target_areas: List[Coordinate],
    max_time_hours: float
) -> List[Coordinate]:
    """Generate search waypoints using a nearest-neighbor approach"""
    if not target_areas:
        return []
    
    waypoints = [asset.current_location]
    remaining_areas = target_areas.copy()
    current_pos = asset.current_location
    total_time = 0.0
    
    while remaining_areas and total_time < max_time_hours:
        # Find nearest unvisited area
        nearest_area = min(remaining_areas, key=lambda area: distance_nm(current_pos, area))
        
        # Calculate time to reach this area
        travel_distance = distance_nm(current_pos, nearest_area)
        travel_time = travel_distance / asset.asset_type.speed_knots
        
        if total_time + travel_time > max_time_hours:
            break
            
        waypoints.append(nearest_area)
        remaining_areas.remove(nearest_area)
        current_pos = nearest_area
        total_time += travel_time
    
    return waypoints

def calculate_coverage_area(waypoints: List[Coordinate], search_width_nm: float) -> float:
    """Calculate total area covered by the search pattern"""
    if len(waypoints) < 2:
        return 0.0
    
    total_distance = 0.0
    for i in range(len(waypoints) - 1):
        total_distance += distance_nm(waypoints[i], waypoints[i + 1])
    
    # Convert to km² (1 nm² = 3.43 km²)
    coverage_area_nm2 = total_distance * search_width_nm
    return coverage_area_nm2 * 3.43

def calculate_route_time(waypoints: List[Coordinate], speed_knots: float) -> float:
    """Calculate total time to complete the route"""
    if len(waypoints) < 2:
        return 0.0
    
    total_distance = 0.0
    for i in range(len(waypoints) - 1):
        total_distance += distance_nm(waypoints[i], waypoints[i + 1])
    
    return total_distance / speed_knots

def calculate_probability_covered(waypoints: List[Coordinate], high_prob_areas: List[Coordinate]) -> float:
    """Calculate what percentage of high-probability areas will be covered"""
    if not high_prob_areas:
        return 0.0
    
    covered_count = 0
    for area in high_prob_areas:
        # Check if any waypoint is within search range of this area
        if any(distance_nm(waypoint, area) < 10.0 for waypoint in waypoints):
            covered_count += 1
    
    return covered_count / len(high_prob_areas)

def calculate_total_coverage(routes: List[OptimizedRoute], high_prob_areas: List[Coordinate]) -> float:
    """Calculate overall coverage percentage across all routes"""
    if not high_prob_areas:
        return 1.0
    
    all_waypoints = []
    for route in routes:
        all_waypoints.extend(route.waypoints)
    
    return calculate_probability_covered(all_waypoints, high_prob_areas)

def identify_uncovered_areas(high_prob_areas: List[Coordinate], covered_waypoints: List[Coordinate]) -> List[dict]:
    """Identify high-probability areas that remain uncovered"""
    uncovered = []
    
    for area in high_prob_areas:
        if not any(distance_nm(area, waypoint) < 10.0 for waypoint in covered_waypoints):
            uncovered.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [area.lon, area.lat]
                },
                "properties": {
                    "priority": "high",
                    "reason": "insufficient_asset_coverage"
                }
            })
    
    return uncovered
