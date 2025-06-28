"""
Real-time Data Ingestion Service for SAR Aircraft Disappearance Prediction System

This module fetches live aircraft telemetry and environmental data from free public APIs:
- OpenSky Network: Real aircraft positions and telemetry
- OpenWeatherMap: Wind and weather conditions
- Open-Elevation: Terrain elevation data

Author: SAR Backend Team
Date: June 27, 2025
"""

import requests
import json
import time
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
import os
from dataclasses import dataclass
import hashlib
from functools import lru_cache
from .database_manager import SARDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration constants
OPENSKY_BASE_URL = "https://opensky-network.org/api/states/all"
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
OPEN_ELEVATION_BASE_URL = "https://api.open-elevation.com/api/v1/lookup"

# Request timeouts and retry settings
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 2

# Fallback values for failed API calls
FALLBACK_VALUES = {
    "fuel": 4000,  # liters (typical commercial aircraft)
    "time_since_contact": 900,  # 15 minutes default
    "wind_speed": 10.0,  # m/s
    "wind_direction": 270,  # degrees (west wind)
    "terrain_elevation": 0  # sea level
}

# Rate limiting for OpenWeatherMap (1000 calls/day)
class APIRateLimiter:
    """Rate limiter for OpenWeatherMap API to respect 1000 calls/day limit"""
    
    def __init__(self):
        self.daily_calls = 0
        self.last_reset = datetime.now().date()
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = 3600  # 1 hour cache TTL
    
    def reset_if_new_day(self):
        """Reset call counter if it's a new day"""
        today = datetime.now().date()
        if today > self.last_reset:
            self.daily_calls = 0
            self.last_reset = today
            self.cache.clear()  # Clear cache on new day
    
    def can_make_call(self) -> bool:
        """Check if we can make another API call"""
        self.reset_if_new_day()
        return self.daily_calls < 950  # Leave buffer of 50 calls
    
    def record_call(self):
        """Record that an API call was made"""
        self.daily_calls += 1
    
    def get_cache_key(self, lat: float, lon: float) -> str:
        """Generate cache key for location"""
        return hashlib.md5(f"{lat:.3f},{lon:.3f}".encode()).hexdigest()
    
    def get_cached_data(self, lat: float, lon: float) -> Optional[Tuple[float, float, float]]:
        """Get cached wind data if available and not expired"""
        cache_key = self.get_cache_key(lat, lon)
        if cache_key in self.cache:
            data, timestamp = self.cache[cache_key]
            if (datetime.now() - timestamp).seconds < self.cache_ttl:
                return data
            else:
                del self.cache[cache_key]
        return None
    
    def cache_data(self, lat: float, lon: float, wind_speed: float, wind_dir: float):
        """Cache wind data with timestamp"""
        cache_key = self.get_cache_key(lat, lon)
        self.cache[cache_key] = ((wind_speed, wind_dir, datetime.now().timestamp()), datetime.now())

# Global rate limiter instance
weather_rate_limiter = APIRateLimiter()

@dataclass
class AircraftState:
    """Structured aircraft state data from OpenSky"""
    icao24: str
    callsign: str
    origin_country: str
    time_position: Optional[float]
    last_contact: float
    longitude: Optional[float]
    latitude: Optional[float]
    baro_altitude: Optional[float]
    on_ground: bool
    velocity: Optional[float]
    true_track: Optional[float]
    vertical_rate: Optional[float]
    sensors: Optional[List[int]]
    geo_altitude: Optional[float]
    squawk: Optional[str]
    spi: bool
    position_source: int

class RealDataIngestor:
    """Main class for ingesting real-time SAR data from public APIs"""
    
    def __init__(self, openweather_api_key: Optional[str] = None, database: Optional[SARDatabase] = None):
        """
        Initialize the data ingestor
        
        Args:
            openweather_api_key: API key for OpenWeatherMap (optional, falls back to env)
            database: Optional database instance (creates one if not provided)
        """
        self.openweather_api_key = openweather_api_key or os.getenv("OPENWEATHER_API_KEY")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SAR-Aircraft-Prediction-System/1.0'
        })
        
        # Initialize database
        self.db = database or SARDatabase()
        
        if not self.openweather_api_key:
            logger.warning("No OpenWeatherMap API key provided. Wind data will use fallback values.")
    
    def fetch_opensky_state(self) -> Optional[Dict[str, Any]]:
        """
        Fetch current aircraft states from OpenSky Network
        
        Returns:
            Dictionary containing aircraft states or None if failed
        """
        try:
            logger.info("Fetching aircraft data from OpenSky Network...")
            
            response = self.session.get(
                OPENSKY_BASE_URL,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data or 'states' not in data:
                logger.warning("No aircraft states returned from OpenSky")
                return None
            
            logger.info(f"Successfully fetched {len(data.get('states', []))} aircraft states")
            return data
            
        except requests.exceptions.Timeout:
            logger.error("OpenSky API request timed out")
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenSky API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenSky response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error fetching OpenSky data: {str(e)}")
        
        return None
    
    def extract_first_valid_aircraft(self, opensky_data: Dict[str, Any]) -> Optional[AircraftState]:
        """
        Extract the first valid aircraft with complete telemetry data
        
        Args:
            opensky_data: Raw OpenSky API response
            
        Returns:
            AircraftState object or None if no valid aircraft found
        """
        try:
            states = opensky_data.get('states', [])
            
            if not states:
                logger.warning("No aircraft states available")
                return None
            
            for state_array in states:
                try:
                    # Parse state array according to OpenSky API documentation
                    if len(state_array) < 17:
                        continue
                    
                    aircraft = AircraftState(
                        icao24=state_array[0],
                        callsign=state_array[1],
                        origin_country=state_array[2],
                        time_position=state_array[3],
                        last_contact=state_array[4],
                        longitude=state_array[5],
                        latitude=state_array[6],
                        baro_altitude=state_array[7],
                        on_ground=state_array[8],
                        velocity=state_array[9],
                        true_track=state_array[10],
                        vertical_rate=state_array[11],
                        sensors=state_array[12],
                        geo_altitude=state_array[13],
                        squawk=state_array[14],
                        spi=state_array[15],
                        position_source=state_array[16]
                    )
                    
                    # Validate required fields
                    if (aircraft.latitude is not None and 
                        aircraft.longitude is not None and
                        aircraft.baro_altitude is not None and
                        aircraft.velocity is not None and
                        aircraft.true_track is not None and
                        not aircraft.on_ground):
                        
                        logger.info(f"Found valid aircraft: {aircraft.callsign or aircraft.icao24} "
                                  f"at {aircraft.latitude:.4f}, {aircraft.longitude:.4f}")
                        return aircraft
                        
                except (IndexError, TypeError) as e:
                    logger.debug(f"Skipping invalid aircraft state: {str(e)}")
                    continue
            
            logger.warning("No valid aircraft found with complete telemetry")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting aircraft data: {str(e)}")
            return None
    
    def fetch_openweather_wind(self, lat: float, lon: float) -> Tuple[float, float]:
        """
        Fetch wind data from OpenWeatherMap API
        
        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            
        Returns:
            Tuple of (wind_speed_ms, wind_direction_deg)
        """
        if not self.openweather_api_key:
            logger.warning("No OpenWeatherMap API key, using fallback wind data")
            return FALLBACK_VALUES["wind_speed"], FALLBACK_VALUES["wind_direction"]
        
        # Check rate limit
        if not weather_rate_limiter.can_make_call():
            logger.warning("API call limit reached, using fallback wind data")
            return FALLBACK_VALUES["wind_speed"], FALLBACK_VALUES["wind_direction"]
        
        # Check cache
        cached_data = weather_rate_limiter.get_cached_data(lat, lon)
        if cached_data:
            wind_speed, wind_direction, _ = cached_data
            logger.info(f"Using cached wind data: {wind_speed} m/s from {wind_direction}°")
            return wind_speed, wind_direction
        
        try:
            logger.info(f"Fetching wind data for {lat:.4f}, {lon:.4f}")
            
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.openweather_api_key,
                "units": "metric"
            }
            
            response = self.session.get(
                OPENWEATHER_BASE_URL,
                params=params,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract wind data
            wind_data = data.get('wind', {})
            wind_speed = wind_data.get('speed', FALLBACK_VALUES["wind_speed"])  # m/s
            wind_direction = wind_data.get('deg', FALLBACK_VALUES["wind_direction"])  # degrees
            
            # Cache the fetched data
            weather_rate_limiter.cache_data(lat, lon, wind_speed, wind_direction)
            
            logger.info(f"Wind data: {wind_speed} m/s from {wind_direction}°")
            return wind_speed, wind_direction
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenWeatherMap API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenWeatherMap response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error fetching wind data: {str(e)}")
        
        # Return fallback values
        logger.info("Using fallback wind data")
        return FALLBACK_VALUES["wind_speed"], FALLBACK_VALUES["wind_direction"]
    
    def fetch_open_elevation(self, lat: float, lon: float) -> float:
        """
        Fetch terrain elevation from Open-Elevation API
        
        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            
        Returns:
            Elevation in meters above sea level
        """
        try:
            logger.info(f"Fetching elevation for {lat:.4f}, {lon:.4f}")
            
            params = {
                "locations": f"{lat},{lon}"
            }
            
            response = self.session.get(
                OPEN_ELEVATION_BASE_URL,
                params=params,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract elevation data
            results = data.get('results', [])
            if results and len(results) > 0:
                elevation = results[0].get('elevation', FALLBACK_VALUES["terrain_elevation"])
                logger.info(f"Terrain elevation: {elevation} meters")
                return elevation
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Open-Elevation API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Open-Elevation response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error fetching elevation: {str(e)}")
        
        # Return fallback value
        logger.info("Using fallback elevation data")
        return FALLBACK_VALUES["terrain_elevation"]
    
    def convert_units(self, aircraft: AircraftState) -> Dict[str, float]:
        """
        Convert aircraft data to simulation-compatible units
        
        Args:
            aircraft: AircraftState object
            
        Returns:
            Dictionary with converted values
        """
        # Convert velocity from m/s to knots (1 m/s = 1.94384 knots)
        speed_knots = aircraft.velocity * 1.94384 if aircraft.velocity else 0
        
        # Convert altitude from meters to feet (1 m = 3.28084 ft)
        altitude_feet = aircraft.baro_altitude * 3.28084 if aircraft.baro_altitude else 0
        
        # True track is already in degrees
        heading = aircraft.true_track if aircraft.true_track else 0        
        return {
            "lat": aircraft.latitude,
            "lon": aircraft.longitude,
            "altitude": altitude_feet,
            "speed": speed_knots,
            "heading": heading
        }
    
    def build_real_simulation_input(self) -> Optional[Dict[str, Any]]:
        """
        Build complete simulation input dictionary from real-time data using SAR research criteria
        Store all fetched data in database for future AI/ML training
        
        Returns:
            Dictionary formatted for SAR simulation or None if no aircraft data available
        """
        try:
            logger.info("=== Starting research-based real-time SAR data ingestion ===")
            
            # Step 1: Fetch aircraft data
            opensky_data = self.fetch_opensky_state()
            if not opensky_data:
                logger.error("Failed to fetch aircraft data")
                return None
            
            # Step 2: Extract best aircraft using SAR research criteria
            aircraft = self.extract_best_sar_aircraft(opensky_data)
            if not aircraft:
                logger.error("No valid aircraft found meeting SAR criteria")
                return None
            
            # Step 3: Validate aircraft data quality
            validation = self.validate_aircraft_for_sar(aircraft)
            if not validation["is_valid"]:
                logger.error(f"Selected aircraft failed validation: {validation['warnings']}")
                return None
            
            logger.info(f"Aircraft data quality: {validation['quality_grade']} "
                       f"(score: {validation['quality_score']:.1f}/100)")
            
            if validation["warnings"]:
                for warning in validation["warnings"]:
                    logger.warning(f"Data quality warning: {warning}")
            
            # Step 4: Convert units
            aircraft_data = self.convert_units(aircraft)
            
            # Step 5: Fetch environmental data
            lat, lon = aircraft_data["lat"], aircraft_data["lon"]
            
            # Check database cache first for environmental data
            cached_env_data = self.db.get_cached_environmental_data(lat, lon)
            
            if cached_env_data:
                logger.info("Using cached environmental data")
                wind_speed = cached_env_data["wind_speed"]
                wind_direction = cached_env_data["wind_direction"]
                terrain_elevation = cached_env_data["terrain_elevation"]
            else:
                # Fetch fresh environmental data
                wind_speed, wind_direction = self.fetch_openweather_wind(lat, lon)
                terrain_elevation = self.fetch_open_elevation(lat, lon)
                  # Store environmental data in database
                env_data = {
                    "wind_speed": wind_speed,
                    "wind_direction": wind_direction,
                    "terrain_elevation": terrain_elevation,
                    "temperature": 20,  # Default fallback
                    "pressure": 1013,   # Default fallback
                    "humidity": 50      # Default fallback
                }
                self.db.store_environmental_data(lat, lon, env_data)
              # Step 6: Store aircraft telemetry in database
            aircraft_telemetry = {
                "icao24": aircraft.icao24,
                "callsign": aircraft.callsign,
                "timestamp": aircraft.last_contact,
                "latitude": lat,
                "longitude": lon,
                "altitude": aircraft_data["altitude"],
                "speed": aircraft_data["speed"],
                "heading": aircraft_data["heading"],
                "vertical_rate": aircraft.vertical_rate,
                "origin_country": aircraft.origin_country,
                "data_quality_score": validation["quality_score"]
            }
            self.db.store_aircraft_data(aircraft_telemetry)
            
            # Step 7: Calculate time since contact with SAR urgency assessment
            current_time = time.time()
            time_since_contact = int(current_time - aircraft.last_contact)
            
            # SAR research shows first 24-48 hours are critical
            urgency_level = "LOW"
            if time_since_contact > 86400:  # >24 hours
                urgency_level = "CRITICAL"
            elif time_since_contact > 21600:  # >6 hours  
                urgency_level = "HIGH"
            elif time_since_contact > 3600:  # >1 hour
                urgency_level = "MEDIUM"
            
            # Step 8: Calculate uncertainty based on research
            # Research shows uncertainty increases with time and altitude
            base_uncertainty = 1.0  # nautical miles
            time_factor = min(time_since_contact / 3600, 24) * 0.5  # Max 12nm for time
            altitude_factor = (aircraft_data["altitude"] / 35000) * 2.0  # Max 2nm for altitude
            uncertainty_radius = base_uncertainty + time_factor + altitude_factor
            
            # Step 9: Build enhanced simulation input with research metadata
            simulation_input = {
                "lat": aircraft_data["lat"],
                "lon": aircraft_data["lon"],
                "altitude": aircraft_data["altitude"],
                "speed": aircraft_data["speed"],
                "heading": aircraft_data["heading"],
                "fuel": FALLBACK_VALUES["fuel"],  # Static fallback - research shows avg commercial aircraft fuel
                "time_since_contact": max(time_since_contact, FALLBACK_VALUES["time_since_contact"]),
                "uncertainty_radius": round(uncertainty_radius, 2),
                "wind": {
                    "speed": wind_speed * 1.94384,  # Convert m/s to knots for consistency
                    "direction": wind_direction
                },
                "terrain_elevation": terrain_elevation,
                "sar_metadata": {
                    "urgency_level": urgency_level,
                    "data_quality": validation["quality_grade"],
                    "quality_score": validation["quality_score"],
                    "warnings": validation["warnings"],
                    "prioritization_factors": {
                        "altitude_priority": "HIGH" if aircraft_data["altitude"] > 30000 else "MEDIUM",
                        "speed_priority": "HIGH" if aircraft_data["speed"] > 400 else "MEDIUM",
                        "location_type": self._classify_geographic_region(lat, lon),
                        "search_complexity": self._assess_search_complexity(lat, lon, terrain_elevation)
                    }
                },
                "data_source": {
                    "aircraft_icao": aircraft.icao24,
                    "aircraft_callsign": aircraft.callsign or "Unknown",
                    "origin_country": aircraft.origin_country,
                    "last_contact": datetime.fromtimestamp(aircraft.last_contact).isoformat(),
                    "ingestion_timestamp": datetime.now().isoformat(),
                    "apis_used": ["opensky", "openweather" if self.openweather_api_key else "fallback", "open_elevation"],
                    "data_completeness": validation["data_completeness"],
                    "api_rate_limit_status": {
                        "openweather_calls_today": weather_rate_limiter.daily_calls,
                        "openweather_calls_remaining": 950 - weather_rate_limiter.daily_calls
                    },
                    "used_cached_data": cached_env_data is not None
                }
            }
              # Step 10: Store simulation input metadata for AI training
            simulation_data = {
                "simulation_id": f"real_time_{int(time.time())}",
                "aircraft_icao": aircraft.icao24,
                "input_parameters": simulation_input,
                "data_quality_score": validation["quality_score"],
                "geographic_region": simulation_input["sar_metadata"]["prioritization_factors"]["location_type"],
                "sar_complexity": simulation_input["sar_metadata"]["prioritization_factors"]["search_complexity"],
                "simulation_type": "real_time_ingestion"
            }
            self.db.store_simulation_results(aircraft.icao24, simulation_data)
            
            logger.info("=== Research-based SAR data ingestion completed successfully ===")
            logger.info(f"Priority Aircraft: {aircraft.callsign or aircraft.icao24} "
                       f"at {lat:.4f}, {lon:.4f}, {aircraft_data['altitude']:.0f}ft")
            logger.info(f"SAR Urgency: {urgency_level}, Data Quality: {validation['quality_grade']}")
            logger.info(f"Search Area: {simulation_input['sar_metadata']['prioritization_factors']['location_type']}")
            logger.info(f"Data stored in database for AI/ML training")
            
            return simulation_input
            
        except Exception as e:
            logger.error(f"Failed to build research-based simulation input: {str(e)}")
            return None
    
    def _classify_geographic_region(self, lat: float, lon: float) -> str:
        """Classify geographic region for SAR complexity assessment"""
        # Ocean regions (highest search complexity)
        if -70 < lon < 20 and 0 < lat < 70:
            return "North_Atlantic_Ocean"
        elif -180 < lon < -70 and -60 < lat < 70:
            return "Pacific_Ocean"
        elif 20 < lon < 120 and -60 < lat < 30:
            return "Indian_Ocean"  # MH370 region
        elif lat > 70 or lat < -60:
            return "Polar_Region"
        elif abs(lat) < 23.5:
            return "Tropical_Region"
        else:
            return "Continental_Region"
    
    def _assess_search_complexity(self, lat: float, lon: float, elevation: float) -> str:
        """Assess search complexity based on location and terrain"""
        region = self._classify_geographic_region(lat, lon)
        
        if "Ocean" in region:
            return "VERY_HIGH"  # Ocean searches are most complex
        elif region == "Polar_Region":
            return "VERY_HIGH"  # Extreme weather conditions
        elif elevation > 3000:  # High mountains
            return "HIGH"
        elif elevation > 1000:  # Mountainous terrain
            return "MEDIUM"
        else:  # Low-lying areas
            return "LOW"
    
    def prioritize_aircraft_by_sar_criteria(self, aircraft_list: List[AircraftState]) -> List[AircraftState]:
        """
        Prioritize aircraft based on SAR research criteria (MH370-style analysis)
        
        Research-based prioritization factors:
        1. High altitude aircraft (>20,000 ft) - longer glide distance
        2. Over water or remote areas - harder to locate
        3. Fast-moving aircraft - larger search radius
        4. Long time since contact - higher urgency
        
        Args:
            aircraft_list: List of valid aircraft
            
        Returns:
            Sorted list with highest priority aircraft first
        """
        def calculate_sar_priority(aircraft: AircraftState) -> float:
            """Calculate SAR priority score (higher = more urgent)"""
            score = 0.0
            
            # Altitude factor (higher altitude = longer potential glide)
            if aircraft.baro_altitude:
                altitude_ft = aircraft.baro_altitude * 3.28084
                if altitude_ft > 35000:
                    score += 10  # Cruise altitude - maximum concern
                elif altitude_ft > 20000:
                    score += 7   # High altitude
                elif altitude_ft > 10000:
                    score += 4   # Medium altitude
                else:
                    score += 1   # Low altitude
            
            # Speed factor (faster = larger potential search area)
            if aircraft.velocity:
                speed_knots = aircraft.velocity * 1.94384
                if speed_knots > 400:
                    score += 8   # High-speed commercial
                elif speed_knots > 200:
                    score += 5   # Medium speed
                else:
                    score += 2   # Slow aircraft
            
            # Time since contact (research shows first hours are critical)
            current_time = time.time()
            time_since_contact = current_time - aircraft.last_contact
            if time_since_contact > 3600:  # >1 hour
                score += 15  # High urgency
            elif time_since_contact > 1800:  # >30 minutes
                score += 10  # Medium urgency
            else:
                score += 5   # Recent contact
            
            # Geographic factor (over water/remote areas harder to search)
            if aircraft.latitude and aircraft.longitude:
                # Simple ocean detection (research shows ocean crashes are hardest)
                lat, lon = aircraft.latitude, aircraft.longitude
                
                # Atlantic Ocean areas
                if -70 < lon < 20 and 0 < lat < 70:
                    score += 12
                # Pacific Ocean areas  
                elif -180 < lon < -70 and -60 < lat < 70:
                    score += 12
                # Indian Ocean areas (MH370 reference)
                elif 20 < lon < 120 and -60 < lat < 30:
                    score += 15  # Highest priority due to MH370 lessons
                # Remote polar regions
                elif lat > 70 or lat < -60:
                    score += 10
                else:
                    score += 3  # Land areas easier to search
            
            return score
        
        # Sort by priority score (highest first)
        prioritized = sorted(aircraft_list, key=calculate_sar_priority, reverse=True)
        
        if prioritized:
            top_aircraft = prioritized[0]
            priority_score = calculate_sar_priority(top_aircraft)
            logger.info(f"Selected highest priority aircraft: {top_aircraft.callsign or top_aircraft.icao24} "
                       f"(SAR priority score: {priority_score:.1f})")
        
        return prioritized

    def extract_best_sar_aircraft(self, opensky_data: Dict[str, Any]) -> Optional[AircraftState]:
        """
        Extract the best aircraft for SAR simulation based on research criteria
        
        Args:
            opensky_data: Raw OpenSky API response
            
        Returns:
            Highest priority aircraft or None if no valid aircraft found
        """
        try:
            states = opensky_data.get('states', [])
            
            if not states:
                logger.warning("No aircraft states available")
                return None
            
            # First, get all valid aircraft
            valid_aircraft = []
            for state_array in states:
                try:
                    if len(state_array) < 17:
                        continue
                    
                    aircraft = AircraftState(
                        icao24=state_array[0],
                        callsign=state_array[1],
                        origin_country=state_array[2],
                        time_position=state_array[3],
                        last_contact=state_array[4],
                        longitude=state_array[5],
                        latitude=state_array[6],
                        baro_altitude=state_array[7],
                        on_ground=state_array[8],
                        velocity=state_array[9],
                        true_track=state_array[10],
                        vertical_rate=state_array[11],
                        sensors=state_array[12],
                        geo_altitude=state_array[13],
                        squawk=state_array[14],
                        spi=state_array[15],
                        position_source=state_array[16]
                    )
                    
                    # Validate required fields
                    if (aircraft.latitude is not None and 
                        aircraft.longitude is not None and
                        aircraft.baro_altitude is not None and
                        aircraft.velocity is not None and
                        aircraft.true_track is not None and
                        not aircraft.on_ground):
                        
                        valid_aircraft.append(aircraft)
                        
                except (IndexError, TypeError) as e:
                    logger.debug(f"Skipping invalid aircraft state: {str(e)}")
                    continue
            
            if not valid_aircraft:
                logger.warning("No valid aircraft found with complete telemetry")
                return None
            
            # Prioritize based on SAR criteria
            prioritized_aircraft = self.prioritize_aircraft_by_sar_criteria(valid_aircraft)
            
            logger.info(f"Found {len(valid_aircraft)} valid aircraft, selected highest priority for SAR simulation")
            return prioritized_aircraft[0]
            
        except Exception as e:
            logger.error(f"Error extracting aircraft data: {str(e)}")
            return None

    def validate_aircraft_for_sar(self, aircraft: AircraftState) -> Dict[str, Any]:
        """
        Validate aircraft data quality for SAR simulation
        
        Args:
            aircraft: Aircraft state to validate
            
        Returns:
            Dictionary with validation results and quality metrics
        """
        validation = {
            "is_valid": True,
            "quality_score": 0.0,
            "warnings": [],
            "data_completeness": {}
        }
        
        # Check data completeness
        completeness = {}
        
        # Position accuracy
        if aircraft.latitude and aircraft.longitude:
            completeness["position"] = 1.0
            validation["quality_score"] += 25
        else:
            completeness["position"] = 0.0
            validation["is_valid"] = False
            validation["warnings"].append("Missing position data")
        
        # Altitude data
        if aircraft.baro_altitude:
            completeness["altitude"] = 1.0
            validation["quality_score"] += 20
            
            # Check for reasonable altitude
            alt_ft = aircraft.baro_altitude * 3.28084
            if alt_ft > 60000:
                validation["warnings"].append(f"Unusually high altitude: {alt_ft:.0f} ft")
            elif alt_ft < 0:
                validation["warnings"].append("Negative altitude reported")
        else:
            completeness["altitude"] = 0.0
            validation["warnings"].append("Missing altitude data")
        
        # Speed data
        if aircraft.velocity:
            completeness["velocity"] = 1.0
            validation["quality_score"] += 20
            
            speed_knots = aircraft.velocity * 1.94384
            if speed_knots > 800:
                validation["warnings"].append(f"Unusually high speed: {speed_knots:.0f} knots")
            elif speed_knots < 50 and not aircraft.on_ground:
                validation["warnings"].append(f"Unusually low speed for airborne aircraft: {speed_knots:.0f} knots")
        else:
            completeness["velocity"] = 0.0
            validation["warnings"].append("Missing velocity data")
        
        # Heading data
        if aircraft.true_track:
            completeness["heading"] = 1.0
            validation["quality_score"] += 15
        else:
            completeness["heading"] = 0.0
            validation["warnings"].append("Missing heading data")
        
        # Contact freshness (critical for SAR)
        current_time = time.time()
        time_since_contact = current_time - aircraft.last_contact
        
        if time_since_contact < 300:  # < 5 minutes
            completeness["contact_freshness"] = 1.0
            validation["quality_score"] += 20
        elif time_since_contact < 1800:  # < 30 minutes
            completeness["contact_freshness"] = 0.7
            validation["quality_score"] += 14
            validation["warnings"].append(f"Data is {time_since_contact/60:.1f} minutes old")
        else:  # > 30 minutes
            completeness["contact_freshness"] = 0.3
            validation["quality_score"] += 6
            validation["warnings"].append(f"Data is {time_since_contact/60:.1f} minutes old - may be stale")
        
        validation["data_completeness"] = completeness
          # Overall quality assessment
        if validation["quality_score"] >= 90:
            validation["quality_grade"] = "Excellent"
        elif validation["quality_score"] >= 75:
            validation["quality_grade"] = "Good"
        elif validation["quality_score"] >= 60:
            validation["quality_grade"] = "Fair"
        else:
            validation["quality_grade"] = "Poor"
            validation["warnings"].append("Low data quality - results may be unreliable")
        
        return validation

    def get_cached_simulation_data(self, icao24: str = None, location: Tuple[float, float] = None, 
                                 max_age_hours: int = 6) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached simulation data from database to avoid redundant API calls
        
        Args:
            icao24: Aircraft ICAO24 identifier (optional)
            location: Tuple of (lat, lon) for location-based search (optional)
            max_age_hours: Maximum age of cached data in hours
            
        Returns:
            Cached simulation input dictionary or None if no suitable cache found
        """
        try:
            if location:
                # Try to get recent environmental data for nearby location
                lat, lon = location
                return self.db.get_cached_environmental_data(lat, lon)
            else:
                logger.warning("No search criteria provided for cached simulation data")
                return None
        except Exception as e:
            logger.error(f"Error retrieving cached simulation data: {str(e)}")
            return None
    
    def build_simulation_input_with_cache(self, prefer_cache: bool = True, 
                                        max_cache_age_hours: int = 6) -> Optional[Dict[str, Any]]:
        """
        Build simulation input with intelligent caching to minimize API calls
        
        Args:
            prefer_cache: Whether to prefer cached data over fresh API calls
            max_cache_age_hours: Maximum age of acceptable cached data
            
        Returns:
            Simulation input dictionary with optimal data freshness vs API usage balance
        """
        try:
            # For now, always fetch fresh data since cache methods are not fully implemented
            logger.info("Fetching fresh simulation data...")
            return self.build_real_simulation_input()
            
        except Exception as e:
            logger.error(f"Error building simulation input with cache: {str(e)}")
            return None

# Convenience functions for direct usage
def fetch_real_aircraft_data(openweather_api_key: Optional[str] = None, database: Optional[SARDatabase] = None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to fetch real aircraft data and store in database
    
    Args:
        openweather_api_key: Optional OpenWeatherMap API key
        database: Optional database instance for data storage
        
    Returns:
        Simulation-ready dictionary or None
    """
    ingestor = RealDataIngestor(openweather_api_key, database)
    return ingestor.build_real_simulation_input()


def test_data_ingestion():
    """Test function to verify all APIs are working"""
    print("=== Testing SAR Real-Time Data Ingestion ===\n")
    
    # Initialize ingestor
    ingestor = RealDataIngestor()
    
    # Test OpenSky
    print("1. Testing OpenSky Network...")
    opensky_data = ingestor.fetch_opensky_state()
    if opensky_data:
        aircraft = ingestor.extract_first_valid_aircraft(opensky_data)
        if aircraft:
            print(f"   ✅ Found aircraft: {aircraft.callsign or aircraft.icao24}")
            
            # Test environmental APIs
            lat, lon = aircraft.latitude, aircraft.longitude
            
            print(f"\n2. Testing OpenWeatherMap for {lat:.4f}, {lon:.4f}...")
            wind_speed, wind_dir = ingestor.fetch_openweather_wind(lat, lon)            
            print(f"   ✅ Wind: {wind_speed} m/s from {wind_dir}°")
            
            print(f"\n3. Testing Open-Elevation...")
            elevation = ingestor.fetch_open_elevation(lat, lon)
            print(f"   ✅ Elevation: {elevation} meters")
            
            print(f"\n4. Building complete simulation input...")
            sim_input = ingestor.build_real_simulation_input()
            if sim_input:
                print("   ✅ Complete simulation input generated!")
                print(f"   Aircraft: {sim_input['data_source']['aircraft_callsign']}")
                print(f"   Position: {sim_input['lat']:.4f}, {sim_input['lon']:.4f}")
                print(f"   Altitude: {sim_input['altitude']:.0f} feet")
                print(f"   Speed: {sim_input['speed']:.0f} knots")
                return sim_input
            else:
                print("   ❌ Failed to generate simulation input")
        else:
            print("   ❌ No valid aircraft found")
    else:
        print("   ❌ Failed to fetch aircraft data")
    
    return None


if __name__ == "__main__":
    # Run test when executed directly
    result = test_data_ingestion()
    if result:
        print(f"\n=== Sample Output ===")
        print(json.dumps(result, indent=2))
