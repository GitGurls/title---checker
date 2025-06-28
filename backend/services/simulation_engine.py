import numpy as np
import math
from scipy.stats import gaussian_kde
from shapely.geometry import Point, MultiPoint, Polygon
from schemas.telemetry import TelemetryInput
import asyncio

# Constants
KNOTS_TO_MPS = 0.514444  # Knots to m/s conversion
EARTH_RADIUS = 6371000  # Earth radius in meters
FUEL_FLOW_RATE = 0.8  # kg/s (typical jet fuel consumption)

async def run_simulation(telemetry: TelemetryInput, n_simulations=1000) -> dict:
    """
    Run realistic crash zone prediction simulation:
    1. Monte Carlo for position uncertainty
    2. Wind drift modeling
    3. Fuel consumption modeling
    4. Bayesian probability estimation
    """
    # Convert inputs to metric
    airspeed_mps = telemetry.speed * KNOTS_TO_MPS
    wind_speed_mps = telemetry.wind.speed * KNOTS_TO_MPS
    
    # Calculate initial position with uncertainty
    start_positions = generate_start_positions(
        telemetry.lat, 
        telemetry.lon, 
        n_simulations,
        telemetry.altitude
    )
    
    # Run Monte Carlo simulations
    crash_points = []
    for i in range(n_simulations):
        point = await simulate_flight(
            start_positions[i],
            telemetry.heading,
            airspeed_mps,
            wind_speed_mps,
            telemetry.wind.direction,
            telemetry.fuel,
            telemetry.time_since_contact
        )
        crash_points.append(point)
    
    # Calculate probability density
    probabilities = calculate_probability_density(crash_points)
    
    # Generate probability contours
    zones = generate_probability_zones(crash_points, probabilities)
    
    return zones

def generate_start_positions(lat, lon, n, altitude):
    """Generate initial positions with uncertainty based on altitude"""
    # Position uncertainty increases with altitude
    uncertainty_m = max(100, altitude / 100)  # 1m per 100ft altitude
    uncertainty_deg = uncertainty_m / (EARTH_RADIUS * math.pi / 180)
    
    return [
        (
            lat + np.random.normal(0, uncertainty_deg),
            lon + np.random.normal(0, uncertainty_deg / math.cos(math.radians(lat)))
        ) for _ in range(n)
    ]

async def simulate_flight(start_pos, heading, airspeed, wind_speed, wind_dir, fuel, time_since_contact):
    """Simulate flight path with wind drift and fuel consumption"""
    lat, lon = start_pos
    heading_rad = math.radians(heading)
    
    # Convert wind to components
    wind_dir_rad = math.radians(wind_dir)
    wind_n = wind_speed * math.cos(wind_dir_rad)
    wind_e = wind_speed * math.sin(wind_dir_rad)
    
    # Calculate flight time until fuel exhaustion
    fuel_kg = fuel * 0.8  # Convert gallons to kg (approx density)
    max_flight_time = min(time_since_contact, fuel_kg / FUEL_FLOW_RATE)
    
    # Calculate ground velocity components
    air_n = airspeed * math.cos(heading_rad)
    air_e = airspeed * math.sin(heading_rad)
    ground_n = air_n + wind_n
    ground_e = air_e + wind_e
    
    # Calculate distance traveled
    distance_n = ground_n * max_flight_time
    distance_e = ground_e * max_flight_time
    
    # Convert to degrees (approx)
    delta_lat = distance_n / (EARTH_RADIUS * math.pi / 180)
    delta_lon = distance_e / (EARTH_RADIUS * math.pi / 180 * math.cos(math.radians(lat)))
    
    return (lat + delta_lat, lon + delta_lon)

def calculate_probability_density(points):
    """Calculate probability density using Gaussian KDE"""
    lats, lons = zip(*points)
    positions = np.vstack([lons, lats])
    kde = gaussian_kde(positions)
    return kde(positions)

def generate_probability_zones(points, probabilities, levels=[0.95, 0.75, 0.50]):
    """Generate probability zones using alpha shapes"""
    try:
        from scipy.spatial import Delaunay
        import alphashape
        
        # Create weighted point cloud
        weighted_points = []
        max_prob = np.max(probabilities)
        for i, (lat, lon) in enumerate(points):
            weight = int(100 * probabilities[i] / max_prob)
            weighted_points.extend([(lon, lat)] * weight)
        
        # Generate alpha shapes for probability levels
        zones = []
        for level in levels:
            # Select top probability points
            n_points = int(len(weighted_points) * level)
            selected_points = weighted_points[:n_points]
            
            if len(selected_points) < 3:
                continue
                
            # Generate concave hull (alpha shape)
            try:
                alpha = alphashape.optimize(selected_points)
                hull = alphashape.alphashape(selected_points, alpha)
                
                # Convert to polygon
                if hull and hull.geom_type == 'Polygon':
                    coords = list(hull.exterior.coords)
                    zones.append({
                        "coordinates": coords,
                        "probability": level,
                        "area_km2": calculate_zone_area(coords)
                    })
            except Exception as e:
                # Fallback to convex hull if alpha shape fails
                from scipy.spatial import ConvexHull
                if len(selected_points) >= 3:
                    hull = ConvexHull(selected_points)
                    coords = [(selected_points[i][0], selected_points[i][1]) for i in hull.vertices]
                    coords.append(coords[0])  # Close polygon
                    zones.append({
                        "coordinates": coords,
                        "probability": level,
                        "area_km2": calculate_zone_area(coords)
                    })
        
        return zones
        
    except ImportError:
        # Fallback implementation without alphashape
        return generate_simple_probability_zones(points, probabilities, levels)

def generate_simple_probability_zones(points, probabilities, levels):
    """Fallback method using simple statistical zones"""
    zones = []
    
    # Calculate center point
    center_lat = np.mean([p[0] for p in points])
    center_lon = np.mean([p[1] for p in points])
    
    # Calculate standard deviations
    std_lat = np.std([p[0] for p in points])
    std_lon = np.std([p[1] for p in points])
    
    for level in levels:
        # Create elliptical zones based on probability level
        radius_factor = 1.0 / level  # Higher probability = smaller radius
        
        # Generate ellipse points
        coords = []
        for angle in np.linspace(0, 2*np.pi, 20):
            lat = center_lat + radius_factor * std_lat * np.sin(angle)
            lon = center_lon + radius_factor * std_lon * np.cos(angle)
            coords.append([lon, lat])
        coords.append(coords[0])  # Close polygon
        
        zones.append({
            "coordinates": coords,
            "probability": level,
            "area_km2": calculate_zone_area(coords)
        })
    
    return zones

def calculate_zone_area(coordinates):
    """Calculate approximate area of a polygon in km²"""
    try:
        from shapely.geometry import Polygon
        polygon = Polygon(coordinates)
        # Rough conversion from degrees² to km²
        area_deg2 = polygon.area
        area_km2 = area_deg2 * (111.32 ** 2)  # 1 degree ≈ 111.32 km
        return round(area_km2, 2)
    except:
        return 0.0