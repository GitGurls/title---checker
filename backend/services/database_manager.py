"""
Database Management System for SAR Aircraft Prediction System

This module handles:
- Persistent storage of aircraft telemetry and environmental data
- Smart caching to avoid redundant API calls
- Data structure optimization for AI model training
- Historical data analysis for pattern recognition
- Performance metrics tracking

Author: SAR Backend Team
Date: June 27, 2025
"""

import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
import logging
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = "sar_data.db"
CACHE_EXPIRY_HOURS = 6  # Cache environmental data for 6 hours
DEDUPE_RADIUS_KM = 5    # Consider positions within 5km as duplicates

@dataclass
class HistoricalDataPoint:
    """Structured historical data for AI training"""
    id: str
    timestamp: datetime
    aircraft_data: Dict[str, Any]
    environmental_data: Dict[str, Any]
    simulation_results: Optional[Dict[str, Any]]
    actual_outcome: Optional[Dict[str, Any]]  # For training validation
    data_quality_score: float
    geographic_region: str
    sar_complexity: str

class SARDatabase:
    """Main database manager for SAR system"""
    
    def __init__(self, db_path: str = DB_PATH):
        """
        Initialize database connection and create tables
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database tables and indexes"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Aircraft telemetry data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aircraft_telemetry (
                    id TEXT PRIMARY KEY,
                    icao24 TEXT,
                    callsign TEXT,
                    timestamp REAL,
                    latitude REAL,
                    longitude REAL,
                    altitude REAL,
                    speed REAL,
                    heading REAL,
                    vertical_rate REAL,
                    origin_country TEXT,
                    position_hash TEXT,
                    data_quality_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(icao24, position_hash, timestamp)
                )
            """)
            
            # Environmental data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS environmental_data (
                    id TEXT PRIMARY KEY,
                    latitude REAL,
                    longitude REAL,
                    location_hash TEXT,
                    wind_speed REAL,
                    wind_direction REAL,
                    terrain_elevation REAL,
                    weather_conditions TEXT,
                    data_source TEXT,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    UNIQUE(location_hash)
                )
            """)
            
            # Simulation results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS simulation_results (
                    id TEXT PRIMARY KEY,
                    aircraft_id TEXT,
                    simulation_type TEXT,
                    input_parameters TEXT,
                    probability_zones TEXT,
                    search_area_km2 REAL,
                    max_probability REAL,
                    simulation_metadata TEXT,
                    execution_time_ms REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (aircraft_id) REFERENCES aircraft_telemetry (id)
                )
            """)
            
            # Performance metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    simulation_id TEXT,
                    actual_crash_location TEXT,
                    predicted_zones TEXT,
                    accuracy_score REAL,
                    distance_error_km REAL,
                    time_to_find_hours REAL,
                    search_efficiency REAL,
                    lessons_learned TEXT,
                    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (simulation_id) REFERENCES simulation_results (id)
                )
            """)
            
            # AI training features table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_training_features (
                    id TEXT PRIMARY KEY,
                    aircraft_type TEXT,
                    weather_pattern TEXT,
                    geographic_features TEXT,
                    time_factors TEXT,
                    feature_vector TEXT,
                    target_outcome TEXT,
                    training_weight REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_aircraft_position ON aircraft_telemetry (latitude, longitude)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_aircraft_timestamp ON aircraft_telemetry (timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_env_location ON environmental_data (location_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_env_expires ON environmental_data (expires_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_simulation_aircraft ON simulation_results (aircraft_id)")
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def generate_position_hash(self, lat: float, lon: float, precision: int = 3) -> str:
        """
        Generate hash for position-based deduplication
        
        Args:
            lat: Latitude
            lon: Longitude
            precision: Decimal places for rounding
            
        Returns:
            Hash string for position
        """
        rounded_lat = round(lat, precision)
        rounded_lon = round(lon, precision)
        return hashlib.md5(f"{rounded_lat},{rounded_lon}".encode()).hexdigest()[:12]
    
    def store_aircraft_data(self, aircraft_data: Dict[str, Any]) -> str:
        """
        Store aircraft telemetry data with deduplication
        
        Args:
            aircraft_data: Aircraft telemetry dictionary
            
        Returns:
            Unique ID for stored data
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Generate unique ID and position hash
            data_id = hashlib.md5(
                f"{aircraft_data.get('icao24', '')}{aircraft_data.get('timestamp', '')}"
                .encode()
            ).hexdigest()
            
            position_hash = self.generate_position_hash(
                aircraft_data['lat'], aircraft_data['lon']
            )
            
            # Check for existing similar data
            cursor.execute("""
                SELECT id FROM aircraft_telemetry 
                WHERE icao24 = ? AND position_hash = ? 
                AND ABS(timestamp - ?) < 300
            """, (
                aircraft_data.get('icao24', ''),
                position_hash,
                aircraft_data.get('timestamp', 0)
            ))
            
            existing = cursor.fetchone()
            if existing:
                logger.info(f"Similar aircraft data already exists: {existing['id']}")
                return existing['id']
            
            # Store new data
            try:
                cursor.execute("""
                    INSERT INTO aircraft_telemetry (
                        id, icao24, callsign, timestamp, latitude, longitude,
                        altitude, speed, heading, vertical_rate, origin_country,
                        position_hash, data_quality_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data_id,
                    aircraft_data.get('icao24', ''),
                    aircraft_data.get('callsign', ''),
                    aircraft_data.get('timestamp', 0),
                    aircraft_data['lat'],
                    aircraft_data['lon'],
                    aircraft_data['altitude'],
                    aircraft_data['speed'],
                    aircraft_data['heading'],
                    aircraft_data.get('vertical_rate', 0),
                    aircraft_data.get('origin_country', ''),
                    position_hash,
                    aircraft_data.get('quality_score', 0.0)
                ))
                
                conn.commit()
                logger.info(f"Stored aircraft data: {data_id}")
                return data_id
                
            except sqlite3.IntegrityError:
                logger.warning(f"Duplicate aircraft data, returning existing ID")
                return data_id
    
    def get_cached_environmental_data(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached environmental data if available and not expired
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Environmental data dictionary or None
        """
        location_hash = self.generate_position_hash(lat, lon, precision=2)  # Wider area for env data
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM environmental_data 
                WHERE location_hash = ? AND expires_at > datetime('now')
            """, (location_hash,))
            
            result = cursor.fetchone()
            if result:
                logger.info(f"Using cached environmental data for {lat:.3f}, {lon:.3f}")
                return {
                    'wind_speed': result['wind_speed'],
                    'wind_direction': result['wind_direction'],
                    'terrain_elevation': result['terrain_elevation'],
                    'cached': True,
                    'fetched_at': result['fetched_at']
                }
        
        return None
    
    def store_environmental_data(self, lat: float, lon: float, env_data: Dict[str, Any]) -> str:
        """
        Store environmental data with expiration
        
        Args:
            lat: Latitude
            lon: Longitude
            env_data: Environmental data dictionary
            
        Returns:
            Unique ID for stored data
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            location_hash = self.generate_position_hash(lat, lon, precision=2)
            data_id = f"env_{location_hash}_{int(datetime.now().timestamp())}"
            expires_at = datetime.now() + timedelta(hours=CACHE_EXPIRY_HOURS)
            
            cursor.execute("""
                INSERT OR REPLACE INTO environmental_data (
                    id, latitude, longitude, location_hash, wind_speed,
                    wind_direction, terrain_elevation, weather_conditions,
                    data_source, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data_id, lat, lon, location_hash,
                env_data.get('wind_speed', 0),
                env_data.get('wind_direction', 0),
                env_data.get('terrain_elevation', 0),
                json.dumps(env_data.get('weather_conditions', {})),
                env_data.get('data_source', 'unknown'),
                expires_at
            ))
            
            conn.commit()
            logger.info(f"Stored environmental data: {data_id}")
            return data_id
    
    def store_simulation_results(self, aircraft_id: str, simulation_data: Dict[str, Any]) -> str:
        """
        Store simulation results for analysis and training
        
        Args:
            aircraft_id: Aircraft data ID
            simulation_data: Complete simulation results
            
        Returns:
            Simulation ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            sim_id = simulation_data.get('simulation_id', hashlib.md5(
                f"{aircraft_id}{datetime.now().timestamp()}".encode()
            ).hexdigest())
            
            # Calculate summary metrics
            geojson = simulation_data.get('geojson', {})
            features = geojson.get('features', [])
            search_area = sum(f.get('properties', {}).get('area_km2', 0) for f in features)
            max_probability = max(
                f.get('properties', {}).get('probability', 0) for f in features
            ) if features else 0
            
            cursor.execute("""
                INSERT INTO simulation_results (
                    id, aircraft_id, simulation_type, input_parameters,
                    probability_zones, search_area_km2, max_probability,
                    simulation_metadata, execution_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sim_id, aircraft_id, "monte_carlo_bayesian",
                json.dumps(simulation_data.get('parameters_used', {})),
                json.dumps(geojson),
                search_area, max_probability,
                json.dumps(simulation_data.get('summary', {})),
                simulation_data.get('execution_time_ms', 0)
            ))
            
            conn.commit()
            logger.info(f"Stored simulation results: {sim_id}")
            return sim_id
    
    def get_historical_patterns(self, 
                               geographic_region: str = None,
                               aircraft_type: str = None,
                               limit: int = 1000) -> pd.DataFrame:
        """
        Retrieve historical data patterns for AI training
        
        Args:
            geographic_region: Filter by region
            aircraft_type: Filter by aircraft type
            limit: Maximum records to return
            
        Returns:
            DataFrame with historical patterns
        """
        with self.get_connection() as conn:
            query = """
                SELECT 
                    a.id,
                    a.icao24,
                    a.latitude,
                    a.longitude,
                    a.altitude,
                    a.speed,
                    a.heading,
                    a.data_quality_score,
                    e.wind_speed,
                    e.wind_direction,
                    e.terrain_elevation,
                    s.search_area_km2,
                    s.max_probability,
                    s.execution_time_ms,
                    a.created_at
                FROM aircraft_telemetry a
                LEFT JOIN environmental_data e ON 
                    ABS(a.latitude - e.latitude) < 0.1 AND 
                    ABS(a.longitude - e.longitude) < 0.1
                LEFT JOIN simulation_results s ON a.id = s.aircraft_id
                WHERE a.data_quality_score > 0.5
            """
            
            params = []
            if geographic_region:
                # Add geographic filtering based on lat/lon ranges
                pass
            
            if aircraft_type:
                query += " AND a.icao24 LIKE ?"
                params.append(f"%{aircraft_type}%")
            
            query += f" ORDER BY a.created_at DESC LIMIT {limit}"
            
            df = pd.read_sql_query(query, conn, params=params)
            logger.info(f"Retrieved {len(df)} historical data points")
            return df
    
    def generate_ai_training_features(self, data_id: str) -> Dict[str, Any]:
        """
        Generate feature vectors for AI model training
        
        Args:
            data_id: Aircraft data ID
            
        Returns:
            Feature dictionary for ML training
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get complete data for feature engineering
            cursor.execute("""
                SELECT 
                    a.*,
                    e.wind_speed,
                    e.wind_direction, 
                    e.terrain_elevation,
                    s.search_area_km2,
                    s.max_probability
                FROM aircraft_telemetry a
                LEFT JOIN environmental_data e ON 
                    ABS(a.latitude - e.latitude) < 0.1 AND 
                    ABS(a.longitude - e.longitude) < 0.1
                LEFT JOIN simulation_results s ON a.id = s.aircraft_id
                WHERE a.id = ?
            """, (data_id,))
            
            row = cursor.fetchone()
            if not row:
                return {}
            
            # Feature engineering
            features = {
                # Aircraft features
                'altitude_normalized': row['altitude'] / 45000.0,  # Normalize to 0-1
                'speed_normalized': row['speed'] / 600.0,
                'heading_sin': np.sin(np.radians(row['heading'])),
                'heading_cos': np.cos(np.radians(row['heading'])),
                
                # Environmental features
                'wind_speed_normalized': (row['wind_speed'] or 0) / 50.0,
                'wind_direction_sin': np.sin(np.radians(row['wind_direction'] or 0)),
                'wind_direction_cos': np.cos(np.radians(row['wind_direction'] or 0)),
                'terrain_elevation_normalized': (row['terrain_elevation'] or 0) / 9000.0,
                
                # Geographic features
                'latitude_normalized': (row['latitude'] + 90) / 180.0,
                'longitude_normalized': (row['longitude'] + 180) / 360.0,
                
                # Derived features
                'is_over_ocean': 1.0 if self._is_over_ocean(row['latitude'], row['longitude']) else 0.0,
                'is_high_altitude': 1.0 if row['altitude'] > 30000 else 0.0,
                'is_high_speed': 1.0 if row['speed'] > 400 else 0.0,
                
                # Data quality
                'data_quality': row['data_quality_score'] or 0.0,
                
                # Target variables (if available)
                'predicted_search_area': row['search_area_km2'] or 0.0,
                'predicted_max_probability': row['max_probability'] or 0.0
            }
            
            return features
    
    def _is_over_ocean(self, lat: float, lon: float) -> bool:
        """Simple ocean detection for feature engineering"""
        # Simplified ocean detection logic
        # In production, use more sophisticated geographic data
        
        # Major ocean areas
        atlantic = (-70 < lon < 20 and 0 < lat < 70)
        pacific = (-180 < lon < -70 and -60 < lat < 70)
        indian = (20 < lon < 120 and -60 < lat < 30)
        
        return atlantic or pacific or indian    
    def archive_and_preserve_data(self):
        """Archive data for long-term storage and AI training - NO DELETION"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Mark old environmental data as archived but keep for training
            cursor.execute("""
                UPDATE environmental_data 
                SET data_source = data_source || '_ARCHIVED'
                WHERE expires_at < datetime('now') 
                AND data_source NOT LIKE '%_ARCHIVED'
            """)
            archived_count = cursor.rowcount
            
            # Create training dataset snapshots for AI models
            cursor.execute("""
                INSERT OR IGNORE INTO ai_training_features (
                    id, aircraft_type, weather_pattern, geographic_features,
                    time_factors, feature_vector, target_outcome, training_weight
                )
                SELECT 
                    'snapshot_' || a.id || '_' || strftime('%Y%m%d', 'now'),
                    a.origin_country || '_' || CAST(a.altitude/10000 AS INT),
                    'wind_' || CAST(e.wind_speed/5 AS INT) || '_' || CAST(e.wind_direction/45 AS INT),
                    'terrain_' || CAST(e.terrain_elevation/500 AS INT) || '_lat_' || CAST(a.latitude/10 AS INT),
                    'contact_' || CAST((julianday('now') - julianday(a.created_at)) AS INT),
                    json_object(
                        'altitude', a.altitude,
                        'speed', a.speed,
                        'heading', a.heading,
                        'wind_speed', e.wind_speed,
                        'wind_direction', e.wind_direction,
                        'terrain', e.terrain_elevation,
                        'lat', a.latitude,
                        'lon', a.longitude,
                        'quality_score', a.data_quality_score
                    ),
                    json_object(
                        'search_area', s.search_area_km2,
                        'max_probability', s.max_probability,
                        'execution_time', s.execution_time_ms
                    ),
                    1.0
                FROM aircraft_telemetry a
                LEFT JOIN environmental_data e ON 
                    ABS(a.latitude - e.latitude) < 0.1 AND 
                    ABS(a.longitude - e.longitude) < 0.1
                LEFT JOIN simulation_results s ON a.id = s.aircraft_id
                WHERE a.created_at > datetime('now', '-7 days')
                AND a.data_quality_score > 0.3
            """)
            training_count = cursor.rowcount
            
            conn.commit()
            logger.info(f"Archived {archived_count} records and created {training_count} training features - NO DATA DELETED")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics for monitoring"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Aircraft data stats
            cursor.execute("SELECT COUNT(*) as count FROM aircraft_telemetry")
            stats['total_aircraft_records'] = cursor.fetchone()['count']
            
            # Environmental data stats
            cursor.execute("SELECT COUNT(*) as count FROM environmental_data WHERE expires_at > datetime('now')")
            stats['cached_environmental_records'] = cursor.fetchone()['count']
            
            # Simulation stats
            cursor.execute("SELECT COUNT(*) as count FROM simulation_results")
            stats['total_simulations'] = cursor.fetchone()['count']
            
            # Recent activity
            cursor.execute("""
                SELECT COUNT(*) as count FROM aircraft_telemetry 
                WHERE created_at > datetime('now', '-24 hours')
            """)
            stats['aircraft_records_24h'] = cursor.fetchone()['count']
            
            # Data quality distribution
            cursor.execute("""
                SELECT 
                    AVG(data_quality_score) as avg_quality,
                    MIN(data_quality_score) as min_quality,
                    MAX(data_quality_score) as max_quality
                FROM aircraft_telemetry
            """)
            quality_stats = cursor.fetchone()
            stats['data_quality'] = {
                'average': quality_stats['avg_quality'] or 0,
                'minimum': quality_stats['min_quality'] or 0,
                'maximum': quality_stats['max_quality'] or 0
            }
            
            return stats

    async def get_training_data(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
        include_features: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get structured training data for AI model development.
        
        Returns data optimized for machine learning with feature engineering.
        """
        try:
            with self._get_connection() as conn:
                # Build query with date filters
                where_clauses = []
                params = []
                
                if start_date:
                    where_clauses.append("s.created_at >= ?")
                    params.append(start_date.isoformat())
                    
                if end_date:
                    where_clauses.append("s.created_at <= ?")
                    params.append(end_date.isoformat())
                
                where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
                
                query = f"""
                SELECT 
                    a.id as aircraft_id,
                    a.callsign,
                    a.latitude as aircraft_lat,
                    a.longitude as aircraft_lon,
                    a.altitude as aircraft_altitude,
                    a.velocity as aircraft_velocity,
                    a.heading as aircraft_heading,
                    a.fuel_remaining,
                    a.time_since_contact,
                    a.uncertainty_radius,
                    e.wind_speed,
                    e.wind_direction,
                    e.temperature,
                    e.pressure,
                    e.humidity,
                    e.visibility,
                    e.elevation,
                    e.terrain_roughness,
                    s.simulation_id,
                    s.predicted_zones,
                    s.summary_stats,
                    s.method_used,
                    s.n_simulations,
                    s.real_time_data_used,
                    s.created_at
                FROM simulation_results s
                JOIN aircraft_data a ON s.aircraft_id = a.id
                LEFT JOIN environmental_data e ON (
                    ABS(e.latitude - a.latitude) < 0.1 AND 
                    ABS(e.longitude - a.longitude) < 0.1 AND
                    ABS((julianday(e.timestamp) - julianday(a.timestamp)) * 24) < 6
                )
                {where_clause}
                ORDER BY s.created_at DESC
                LIMIT ?
                """
                
                params.append(limit)
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                training_data = []
                for row in rows:
                    data_point = dict(row)
                    
                    # Parse JSON fields
                    if data_point['predicted_zones']:
                        data_point['predicted_zones'] = json.loads(data_point['predicted_zones'])
                    if data_point['summary_stats']:
                        data_point['summary_stats'] = json.loads(data_point['summary_stats'])
                    
                    # Add engineered features if requested
                    if include_features:
                        data_point['features'] = self._engineer_features(data_point)
                    
                    training_data.append(data_point)
                
                logger.info(f"Retrieved {len(training_data)} training data points")
                return training_data
                
        except Exception as e:
            logger.error(f"Failed to get training data: {str(e)}")
            raise
    
    async def get_analytics_summary(self) -> Dict[str, Any]:
        """
        Get analytics summary for model training insights.
        """
        try:
            with self._get_connection() as conn:
                # Get basic statistics
                stats_query = """
                SELECT 
                    COUNT(DISTINCT s.simulation_id) as total_simulations,
                    COUNT(DISTINCT a.id) as unique_aircraft,
                    COUNT(DISTINCT e.id) as environmental_records,
                    MIN(s.created_at) as earliest_simulation,
                    MAX(s.created_at) as latest_simulation,
                    AVG(CAST(json_extract(s.summary_stats, '$.total_area_km2') AS FLOAT)) as avg_search_area,
                    AVG(CAST(json_extract(s.summary_stats, '$.max_probability') AS FLOAT)) as avg_max_probability
                FROM simulation_results s
                JOIN aircraft_data a ON s.aircraft_id = a.id
                LEFT JOIN environmental_data e ON (
                    ABS(e.latitude - a.latitude) < 0.1 AND 
                    ABS(e.longitude - a.longitude) < 0.1
                )
                """
                
                cursor = conn.execute(stats_query)
                stats = dict(cursor.fetchone())
                
                # Calculate data quality score
                quality_query = """
                SELECT 
                    COUNT(*) as total_records,
                    SUM(CASE WHEN real_time_data_used = 1 THEN 1 ELSE 0 END) as real_time_records,
                    SUM(CASE WHEN fuel_remaining > 0 THEN 1 ELSE 0 END) as complete_fuel_records
                FROM simulation_results s
                JOIN aircraft_data a ON s.aircraft_id = a.id
                """
                
                cursor = conn.execute(quality_query)
                quality_data = dict(cursor.fetchone())
                
                # Calculate quality metrics
                data_quality_score = 0.0
                if quality_data['total_records'] > 0:
                    real_time_ratio = quality_data['real_time_records'] / quality_data['total_records']
                    fuel_completeness = quality_data['complete_fuel_records'] / quality_data['total_records']
                    data_quality_score = (real_time_ratio * 0.6 + fuel_completeness * 0.4) * 100
                
                # Feature completeness
                feature_completeness = min(100, (stats['environmental_records'] / max(1, stats['total_simulations'])) * 100)
                
                summary = {
                    **stats,
                    'data_quality_score': round(data_quality_score, 2),
                    'feature_completeness': round(feature_completeness, 2),
                    'real_time_data_ratio': round((quality_data['real_time_records'] / max(1, quality_data['total_records'])) * 100, 2)
                }
                
                return summary
                
        except Exception as e:
            logger.error(f"Failed to get analytics summary: {str(e)}")
            raise
    
    async def cleanup_old_data(self, days_old: int = 30, dry_run: bool = True) -> Dict[str, Any]:
        """
        Clean up old cached data and expired simulation results.
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            with self._get_connection() as conn:
                # Count what would be deleted
                count_queries = {
                    'environmental_data': """
                        SELECT COUNT(*) as count FROM environmental_data 
                        WHERE timestamp < ?
                    """,
                    'simulation_results': """
                        SELECT COUNT(*) as count FROM simulation_results 
                        WHERE created_at < ?
                    """,
                    'aircraft_data': """
                        SELECT COUNT(*) as count FROM aircraft_data 
                        WHERE timestamp < ? AND id NOT IN (
                            SELECT DISTINCT aircraft_id FROM simulation_results 
                            WHERE created_at >= ?
                        )
                    """
                }
                
                cleanup_summary = {}
                
                for table, query in count_queries.items():
                    if table == 'aircraft_data':
                        cursor = conn.execute(query, (cutoff_date.isoformat(), cutoff_date.isoformat()))
                    else:
                        cursor = conn.execute(query, (cutoff_date.isoformat(),))
                    
                    count = cursor.fetchone()['count']
                    cleanup_summary[f'{table}_records_to_delete'] = count
                
                # Perform actual deletion if not dry run
                if not dry_run:
                    delete_queries = {
                        'environmental_data': "DELETE FROM environmental_data WHERE timestamp < ?",
                        'simulation_results': "DELETE FROM simulation_results WHERE created_at < ?",
                        'aircraft_data': """
                            DELETE FROM aircraft_data 
                            WHERE timestamp < ? AND id NOT IN (
                                SELECT DISTINCT aircraft_id FROM simulation_results 
                                WHERE created_at >= ?
                            )
                        """
                    }
                    
                    for table, query in delete_queries.items():
                        if table == 'aircraft_data':
                            cursor = conn.execute(query, (cutoff_date.isoformat(), cutoff_date.isoformat()))
                        else:
                            cursor = conn.execute(query, (cutoff_date.isoformat(),))
                        
                        cleanup_summary[f'{table}_records_deleted'] = cursor.rowcount
                    
                    conn.commit()
                    logger.info(f"Cleaned up data older than {days_old} days")
                else:
                    logger.info(f"Dry run: Would clean up data older than {days_old} days")
                
                cleanup_summary['cutoff_date'] = cutoff_date.isoformat()
                cleanup_summary['total_records_affected'] = sum([
                    v for k, v in cleanup_summary.items() 
                    if k.endswith('_to_delete') or k.endswith('_deleted')
                ])
                
                return cleanup_summary
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {str(e)}")
            raise
    
    def _engineer_features(self, data_point: Dict[str, Any]) -> Dict[str, Any]:
        """
        Engineer features for machine learning from raw data.
        """
        features = {}
        
        # Time-based features
        if data_point.get('time_since_contact'):
            features['urgency_score'] = min(1.0, data_point['time_since_contact'] / 3600)  # Normalize to hours
        
        # Geographic features
        features['geographic_complexity'] = self._calculate_geographic_complexity(
            data_point.get('aircraft_lat', 0),
            data_point.get('aircraft_lon', 0),
            data_point.get('elevation', 0)
        )
        
        # Weather severity
        features['weather_severity'] = self._calculate_weather_severity(
            data_point.get('wind_speed', 0),
            data_point.get('visibility', 10000),
            data_point.get('temperature', 20)
        )
        
        # Flight characteristics
        if data_point.get('aircraft_velocity') and data_point.get('fuel_remaining'):
            features['endurance_ratio'] = data_point['fuel_remaining'] / max(1, data_point['aircraft_velocity'])
        
        # Search complexity
        summary_stats = data_point.get('summary_stats', {})
        if isinstance(summary_stats, dict):
            features['search_complexity'] = summary_stats.get('total_area_km2', 0) / max(1, summary_stats.get('primary_search_zones', 1))
        
        return features
    
    def _calculate_geographic_complexity(self, lat: float, lon: float, elevation: float) -> float:
        """Calculate geographic complexity score (0-1)"""
        # Higher score for mountainous, remote, or challenging terrain
        elevation_factor = min(1.0, elevation / 3000)  # Normalize to 3000m
        
        # Add latitude factor (polar regions more complex)
        latitude_factor = abs(lat) / 90.0
        
        return (elevation_factor * 0.7 + latitude_factor * 0.3)
    
    def _calculate_weather_severity(self, wind_speed: float, visibility: float, temperature: float) -> float:
        """Calculate weather severity score (0-1)"""
        wind_factor = min(1.0, wind_speed / 25)  # Normalize to 25 m/s
        visibility_factor = max(0, (10000 - visibility) / 10000)  # Lower visibility = higher severity
        temp_factor = max(abs(temperature - 20), 0) / 40  # Extreme temperatures
        
        return (wind_factor * 0.5 + visibility_factor * 0.3 + temp_factor * 0.2)
        
# Global database instance
sar_db = SARDatabase()

# Convenience functions
def store_aircraft_telemetry(aircraft_data: Dict[str, Any]) -> str:
    """Store aircraft telemetry data"""
    return sar_db.store_aircraft_data(aircraft_data)

def get_cached_weather(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """Get cached environmental data"""
    return sar_db.get_cached_environmental_data(lat, lon)

def store_environmental_data(lat: float, lon: float, env_data: Dict[str, Any]) -> str:
    """Store environmental data"""
    return sar_db.store_environmental_data(lat, lon, env_data)

def store_simulation(aircraft_id: str, simulation_data: Dict[str, Any]) -> str:
    """Store simulation results"""
    return sar_db.store_simulation_results(aircraft_id, simulation_data)

def get_training_data(region: str = None, limit: int = 1000) -> pd.DataFrame:
    """Get historical data for AI training"""
    return sar_db.get_historical_patterns(geographic_region=region, limit=limit)
