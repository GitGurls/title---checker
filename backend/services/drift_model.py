import numpy as np
import math
from typing import Tuple, List
from schemas.telemetry import TelemetryInput, WindData

# Physical constants
KNOTS_TO_MPS = 0.514444
EARTH_RADIUS_M = 6371000
GRAVITY = 9.81

class WindDriftModel:
    """Advanced wind drift modeling for aircraft debris and survival equipment"""
    
    def __init__(self):
        self.surface_wind_factor = 0.7  # Surface wind is typically 70% of reported wind
        self.wind_shear_layers = [
            (0, 1000),      # Surface layer
            (1000, 5000),   # Boundary layer  
            (5000, 20000),  # Lower atmosphere
            (20000, 40000)  # Upper atmosphere
        ]
    
    async def calculate_drift_vectors(
        self,
        start_lat: float,
        start_lon: float,
        altitude_ft: float,
        wind_data: WindData,
        time_seconds: int,
        object_type: str = "debris"
    ) -> List[Tuple[float, float]]:
        """
        Calculate wind drift for different altitude layers during descent.
        
        Args:
            start_lat: Starting latitude
            start_lon: Starting longitude  
            altitude_ft: Initial altitude in feet
            wind_data: Wind conditions
            time_seconds: Time since last contact
            object_type: Type of drifting object (debris, survival_raft, etc.)
        
        Returns:
            List of (lat, lon) positions showing drift path
        """
        
        positions = [(start_lat, start_lon)]
        current_lat, current_lon = start_lat, start_lon
        current_altitude = altitude_ft
        
        # Object-specific parameters
        descent_rate = self._get_descent_rate(object_type, altitude_ft)
        drag_coefficient = self._get_drag_coefficient(object_type)
        
        # Simulate descent with wind drift
        dt = 60  # 1 minute time steps
        total_time = 0
        
        while current_altitude > 0 and total_time < time_seconds:
            # Get wind conditions for current altitude
            wind_speed, wind_direction = self._get_wind_at_altitude(
                current_altitude, wind_data
            )
            
            # Calculate wind drift for this time step
            drift_lat, drift_lon = self._calculate_drift_step(
                current_lat, current_lon, current_altitude,
                wind_speed, wind_direction, dt, drag_coefficient
            )
            
            current_lat += drift_lat
            current_lon += drift_lon
            current_altitude -= descent_rate * dt
            total_time += dt
            
            positions.append((current_lat, current_lon))
        
        # Continue surface drift if object reaches surface before time limit
        if current_altitude <= 0 and total_time < time_seconds:
            remaining_time = time_seconds - total_time
            surface_positions = self._calculate_surface_drift(
                current_lat, current_lon, wind_data, 
                remaining_time, object_type
            )
            positions.extend(surface_positions)
        
        return positions
    
    def _get_descent_rate(self, object_type: str, altitude_ft: float) -> float:
        """Get descent rate in feet per second based on object type"""
        base_rates = {
            "debris": 50.0,      # General aircraft debris
            "fuselage": 200.0,   # Large fuselage sections
            "survival_raft": 15.0, # Inflated life raft
            "cargo": 100.0,      # Cargo containers
            "fuel_tank": 150.0   # Empty fuel tanks
        }
        
        base_rate = base_rates.get(object_type, 50.0)
        
        # Terminal velocity increases with density (altitude effect)
        altitude_factor = 1.0 + (altitude_ft / 40000) * 0.3
        return base_rate * altitude_factor
    
    def _get_drag_coefficient(self, object_type: str) -> float:
        """Get drag coefficient for wind drift calculations"""
        drag_coefficients = {
            "debris": 1.2,
            "fuselage": 0.8,
            "survival_raft": 2.5,  # High surface area
            "cargo": 1.0,
            "fuel_tank": 0.9
        }
        return drag_coefficients.get(object_type, 1.2)
    
    def _get_wind_at_altitude(
        self, 
        altitude_ft: float, 
        surface_wind: WindData
    ) -> Tuple[float, float]:
        """
        Calculate wind speed and direction at given altitude.
        Uses simplified atmospheric model.
        """
        altitude_m = altitude_ft * 0.3048
        
        # Wind typically increases with altitude up to jet stream
        if altitude_m < 1000:
            # Surface layer - reduced wind
            wind_factor = 0.7
            direction_shift = 0
        elif altitude_m < 5000:
            # Boundary layer - gradual increase
            wind_factor = 0.7 + (altitude_m - 1000) / 4000 * 0.5
            direction_shift = 15  # Backing with altitude
        elif altitude_m < 12000:
            # Lower atmosphere - stronger winds
            wind_factor = 1.2 + (altitude_m - 5000) / 7000 * 0.8
            direction_shift = 30
        else:
            # Upper atmosphere - jet stream effects
            wind_factor = 2.0 + min((altitude_m - 12000) / 8000, 1.0) * 1.5
            direction_shift = 45
        
        wind_speed = surface_wind.speed * wind_factor
        wind_direction = (surface_wind.direction + direction_shift) % 360
        
        return wind_speed, wind_direction
    
    def _calculate_drift_step(
        self,
        lat: float,
        lon: float, 
        altitude_ft: float,
        wind_speed_knots: float,
        wind_direction_deg: float,
        dt_seconds: float,
        drag_coefficient: float
    ) -> Tuple[float, float]:
        """Calculate wind drift for a single time step"""
        
        # Convert wind to m/s
        wind_speed_mps = wind_speed_knots * KNOTS_TO_MPS
        wind_direction_rad = math.radians(wind_direction_deg)
        
        # Calculate wind components (North, East)
        wind_north = wind_speed_mps * math.cos(wind_direction_rad)
        wind_east = wind_speed_mps * math.sin(wind_direction_rad)
        
        # Apply drag coefficient and altitude effects
        altitude_density_factor = math.exp(-altitude_ft * 0.3048 / 8400)  # Atmospheric density
        effective_wind_north = wind_north * drag_coefficient * altitude_density_factor
        effective_wind_east = wind_east * drag_coefficient * altitude_density_factor
        
        # Calculate displacement in meters
        displacement_north = effective_wind_north * dt_seconds
        displacement_east = effective_wind_east * dt_seconds
        
        # Convert to degrees
        lat_displacement = displacement_north / (EARTH_RADIUS_M * math.pi / 180)
        lon_displacement = displacement_east / (
            EARTH_RADIUS_M * math.pi / 180 * math.cos(math.radians(lat))
        )
        
        return lat_displacement, lon_displacement
    
    def _calculate_surface_drift(
        self,
        start_lat: float,
        start_lon: float,
        wind_data: WindData,
        time_seconds: int,
        object_type: str
    ) -> List[Tuple[float, float]]:
        """Calculate surface drift for objects floating on water"""
        
        positions = []
        current_lat, current_lon = start_lat, start_lon
        
        # Surface drift parameters
        surface_wind_factor = 0.03  # 3% of wind speed for surface current
        if object_type == "survival_raft":
            surface_wind_factor = 0.05  # Life rafts drift more
        
        wind_speed_mps = wind_data.speed * KNOTS_TO_MPS * surface_wind_factor
        wind_direction_rad = math.radians(wind_data.direction)
        
        # Add Coriolis effect for long-duration drift
        coriolis_factor = 2 * 7.2921e-5 * math.sin(math.radians(start_lat))
        
        # Simulate surface drift in 1-hour steps
        dt = 3600  # 1 hour
        steps = time_seconds // dt
        
        for step in range(steps):
            # Wind-driven current
            wind_north = wind_speed_mps * math.cos(wind_direction_rad)
            wind_east = wind_speed_mps * math.sin(wind_direction_rad)
            
            # Add Coriolis deflection (90° to the right in Northern Hemisphere)
            if step > 0:  # After first hour, Coriolis becomes significant
                coriolis_deflection = coriolis_factor * dt
                wind_north_corrected = wind_north * math.cos(coriolis_deflection) - wind_east * math.sin(coriolis_deflection)
                wind_east_corrected = wind_north * math.sin(coriolis_deflection) + wind_east * math.cos(coriolis_deflection)
                wind_north, wind_east = wind_north_corrected, wind_east_corrected
            
            # Calculate displacement
            displacement_north = wind_north * dt
            displacement_east = wind_east * dt
            
            # Convert to degrees
            lat_displacement = displacement_north / (EARTH_RADIUS_M * math.pi / 180)
            lon_displacement = displacement_east / (
                EARTH_RADIUS_M * math.pi / 180 * math.cos(math.radians(current_lat))
            )
            
            current_lat += lat_displacement
            current_lon += lon_displacement
            positions.append((current_lat, current_lon))
        
        return positions

# Enhanced wind modeling functions
async def calculate_wind_drift_probability(
    telemetry: TelemetryInput,
    n_simulations: int = 500
) -> List[Tuple[float, float, float]]:
    """
    Calculate probability distribution of wind drift positions.
    
    Returns:
        List of (lat, lon, probability) tuples
    """
    
    drift_model = WindDriftModel()
    all_positions = []
    
    # Run multiple simulations with wind uncertainty
    for _ in range(n_simulations):
        # Add wind uncertainty (±20% speed, ±10° direction)
        wind_speed_var = telemetry.wind.speed * (1 + np.random.normal(0, 0.2))
        wind_dir_var = telemetry.wind.direction + np.random.normal(0, 10)
        
        varied_wind = WindData(
            speed=max(0, wind_speed_var),
            direction=wind_dir_var % 360
        )
        
        # Calculate drift path
        positions = await drift_model.calculate_drift_vectors(
            telemetry.lat,
            telemetry.lon,
            telemetry.altitude,
            varied_wind,
            telemetry.time_since_contact,
            "debris"
        )
        
        # Use final position for probability calculation
        if positions:
            all_positions.append(positions[-1])
    
    # Calculate probability density
    if not all_positions:
        return []
    
    from scipy.stats import gaussian_kde
    
    lats, lons = zip(*all_positions)
    positions_array = np.vstack([lons, lats])
    kde = gaussian_kde(positions_array)
    
    # Generate probability grid
    probability_positions = []
    for lat, lon in all_positions:
        probability = kde.evaluate([[lon], [lat]])[0]
        probability_positions.append((lat, lon, probability))
    
    return probability_positions
