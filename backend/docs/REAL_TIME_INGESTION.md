# Real-Time Data Ingestion System

## Overview

The SAR Aircraft Disappearance Prediction System includes a comprehensive real-time data ingestion module that fetches live aircraft telemetry and environmental data from free public APIs. This system is designed based on research from major aviation incidents (MH370, AF447) and incorporates SAR best practices.

## 🎯 Research-Based Design

### SAR Research Foundations
- **MH370 Analysis**: Incorporates lessons learned about search zone prioritization and probability modeling
- **Time-Critical Response**: Research shows first 24-48 hours are critical for SAR success
- **Environmental Factors**: Wind drift, ocean currents, and terrain complexity affect search strategies
- **Data Quality Assessment**: Multi-factor validation ensures reliable simulation inputs

## 📡 Data Sources

### 1. Aircraft Telemetry - OpenSky Network
- **API**: `https://opensky-network.org/api/states/all`
- **Cost**: Free, no API key required
- **Rate Limit**: None specified
- **Data Extracted**:
  - Position (latitude/longitude)
  - Altitude (barometric)
  - Speed (ground velocity)
  - Heading (true track)
  - Last contact timestamp

### 2. Weather Data - OpenWeatherMap
- **API**: `https://api.openweathermap.org/data/2.5/weather`
- **Cost**: Free tier (1000 calls/day)
- **Rate Limiting**: Implemented with caching
- **Data Extracted**:
  - Wind speed (m/s)
  - Wind direction (degrees)
  - Atmospheric pressure
  - Weather conditions

### 3. Terrain Elevation - Open-Elevation
- **API**: `https://api.open-elevation.com/api/v1/lookup`
- **Cost**: Free, no API key required
- **Rate Limit**: Reasonable use policy
- **Data Extracted**:
  - Terrain elevation (meters above sea level)

## 🧠 SAR Research Integration

### Aircraft Prioritization Algorithm
The system uses research-based criteria to prioritize aircraft for SAR simulation:

```python
Priority Score = Altitude Factor + Speed Factor + Time Factor + Geographic Factor

Where:
- Altitude Factor: Higher altitude = longer glide distance (0-10 points)
- Speed Factor: Higher speed = larger search radius (0-8 points)  
- Time Factor: Longer since contact = higher urgency (0-15 points)
- Geographic Factor: Ocean/remote areas = higher complexity (0-15 points)
```

### Data Quality Assessment
Multi-dimensional quality scoring:
- **Position Accuracy**: GPS precision and timestamp freshness
- **Telemetry Completeness**: All required parameters present
- **Temporal Validity**: Recency of last contact
- **Consistency Checks**: Validates against known aircraft performance

### SAR Urgency Classification
- **CRITICAL**: >24 hours since contact or emergency conditions
- **HIGH**: >6 hours since contact or over ocean
- **MEDIUM**: >1 hour since contact
- **LOW**: Recent contact, over land

## 🔧 Implementation Details

### Core Classes

#### `RealDataIngestor`
Main ingestion class with research-based prioritization:

```python
class RealDataIngestor:
    def __init__(self, openweather_api_key: Optional[str] = None)
    def build_real_simulation_input(self) -> Optional[Dict[str, Any]]
    def extract_best_sar_aircraft(self, opensky_data) -> Optional[AircraftState]
    def validate_aircraft_for_sar(self, aircraft) -> Dict[str, Any]
```

#### `APIRateLimiter`
Intelligent rate limiting for OpenWeatherMap:
- Daily call tracking (1000 call limit)
- Geographic caching (1-hour TTL)
- Automatic fallback to cached data

### Key Functions

#### `prioritize_aircraft_by_sar_criteria()`
Research-based aircraft prioritization considering:
- Cruise altitude aircraft (higher priority due to longer glide distance)
- High-speed aircraft (larger potential search radius)
- Aircraft over water/remote areas (harder to locate)
- Time since last contact (urgency factor)

#### `validate_aircraft_for_sar()`
Comprehensive data quality validation:
- Position accuracy verification
- Telemetry completeness scoring
- Temporal freshness assessment
- Physics-based consistency checks

## 📊 Output Format

### Standard Simulation Input
```json
{
  "lat": 25.4,
  "lon": 87.6,
  "altitude": 35000,
  "speed": 450,
  "heading": 98,
  "fuel": 4000,
  "time_since_contact": 900,
  "uncertainty_radius": 2.5,
  "wind": {
    "speed": 15.5,
    "direction": 110
  },
  "terrain_elevation": 112,
  "sar_metadata": {
    "urgency_level": "HIGH",
    "data_quality": "Good",
    "quality_score": 87.5,
    "prioritization_factors": {
      "altitude_priority": "HIGH",
      "speed_priority": "HIGH", 
      "location_type": "Indian_Ocean",
      "search_complexity": "VERY_HIGH"
    }
  }
}
```

### Enhanced Metadata
- **SAR Urgency Assessment**: Based on time factors and risk analysis
- **Data Quality Metrics**: Completeness, accuracy, and reliability scores
- **Geographic Classification**: Ocean regions, polar areas, terrain complexity
- **Search Complexity Assessment**: Factors affecting SAR operations

## 🚀 API Endpoints

### Real-Time Simulation
```
POST /api/simulate/real-time
```
Runs simulation with live aircraft data, includes enhanced priority selection.

### Aircraft Monitoring
```
GET /api/simulate/monitor/active-aircraft
```
Returns prioritized list of all active aircraft with SAR assessments.

### Emergency Detection
```
POST /api/simulate/emergency/detect-anomalies
```
Detects potential emergency situations based on flight patterns.

### API Testing
```
GET /api/simulate/test-apis
```
Tests connectivity and functionality of all data sources.

## 🔍 Research-Based Features

### Uncertainty Modeling
Dynamic uncertainty calculation based on:
- **Time Factor**: Uncertainty increases with time since contact
- **Altitude Factor**: Higher altitude = greater position uncertainty
- **Environmental Factors**: Weather conditions affecting position accuracy

```python
uncertainty_radius = base_uncertainty + time_factor + altitude_factor
where:
- base_uncertainty = 1.0 nm
- time_factor = min(hours_since_contact * 0.5, 12.0) nm
- altitude_factor = (altitude_ft / 35000) * 2.0 nm
```

### Geographic Risk Assessment
Location-based search complexity classification:
- **Indian Ocean**: Highest priority (MH370 reference)
- **Atlantic/Pacific**: Very high complexity
- **Polar Regions**: Extreme weather challenges
- **Mountainous**: High terrain complexity
- **Continental**: Lower complexity

### Emergency Detection
Automated anomaly detection based on:
- Emergency squawk codes (7700, 7600, 7500)
- Unusual altitude or speed patterns
- Rapid descent indicators
- Extended communication silence

## 📈 Performance Optimizations

### Caching Strategy
- **Weather Data**: 1-hour geographic caching
- **Elevation Data**: Persistent caching (terrain doesn't change)
- **Aircraft Prioritization**: In-memory caching for repeated requests

### Rate Limiting
- **Smart Limiting**: Respects API quotas while maximizing data freshness
- **Graceful Degradation**: Fallback to cached or estimated data
- **Usage Tracking**: Monitors daily API consumption

### Error Handling
- **Progressive Fallback**: Multiple fallback strategies for each data type
- **Data Validation**: Comprehensive input validation and sanitization
- **Logging**: Detailed logging for debugging and monitoring

## 🧪 Testing and Validation

### Test Functions
```python
test_data_ingestion()           # End-to-end API testing
validate_aircraft_for_sar()     # Data quality validation
prioritize_aircraft_by_sar_criteria()  # Priority algorithm testing
```

### Validation Metrics
- **Data Completeness**: Percentage of required fields present
- **Temporal Validity**: Time since last update
- **Consistency Scores**: Cross-validation between data sources
- **Quality Grades**: Excellent, Good, Fair, Poor

## 🔒 Production Considerations

### Security
- API key management through environment variables
- Rate limiting to prevent abuse
- Input sanitization and validation
- No sensitive data exposure in logs

### Reliability
- Multiple fallback strategies for each data source
- Graceful degradation when APIs are unavailable
- Comprehensive error handling and recovery
- Health monitoring and alerting

### Scalability
- Efficient caching reduces API calls
- Asynchronous processing where possible
- Configurable rate limits and timeouts
- Horizontal scaling support

## 📚 Usage Examples

### Basic Usage
```python
from services.real_data_ingestor import fetch_real_aircraft_data

# Get simulation-ready data
data = fetch_real_aircraft_data(openweather_api_key="your_key")
if data:
    print(f"Aircraft: {data['data_source']['aircraft_callsign']}")
    print(f"Priority: {data['sar_metadata']['urgency_level']}")
```

### Advanced Usage
```python
from services.real_data_ingestor import RealDataIngestor

ingestor = RealDataIngestor(openweather_api_key="your_key")

# Get prioritized aircraft list
opensky_data = ingestor.fetch_opensky_state()
aircraft = ingestor.extract_best_sar_aircraft(opensky_data)

# Validate data quality
validation = ingestor.validate_aircraft_for_sar(aircraft)
print(f"Quality: {validation['quality_grade']} ({validation['quality_score']:.1f}/100)")
```

## 🎯 Future Enhancements

### Planned Features
- **Machine Learning**: Pattern recognition for anomaly detection
- **Historical Analysis**: Trend analysis for improved predictions
- **Multi-Source Fusion**: Integration of additional data sources
- **Real-Time Alerts**: Automated emergency notifications

### Research Integration
- **Advanced Wind Models**: Upper atmosphere wind patterns
- **Ocean Current Data**: Surface drift modeling for water crashes
- **Satellite Integration**: Real-time satellite imagery analysis
- **Radar Data**: Integration with ATC radar feeds

---

*This real-time ingestion system represents a significant advancement in SAR technology, incorporating lessons learned from major aviation incidents and current research in search and rescue operations.*
