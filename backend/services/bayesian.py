import numpy as np
from scipy.spatial.distance import cdist
from scipy.interpolate import griddata
from shapely.geometry import Point, Polygon
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

# Optional PyMC3 import for advanced Bayesian modeling
try:
    import pymc3 as pm
    PYMC3_AVAILABLE = True
except ImportError:
    PYMC3_AVAILABLE = False
    logger.warning("PyMC3 not available. Using simplified Bayesian calculations.")

class BayesianUpdateEngine:
    """
    Bayesian inference engine for updating crash probability based on new evidence.
    Implements P(H|E) = P(E|H) * P(H) / P(E) where:
    - H: Hypothesis (crash location)
    - E: Evidence (debris, signals, sightings)
    """
    
    def __init__(self, grid_resolution: int = 100):
        self.grid_resolution = grid_resolution
    
    async def update_probability_with_evidence(
        self,
        prior_zones: List[Dict[str, Any]], 
        new_evidence: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Update crash probability using Bayesian inference with new evidence.
        
        Args:
            prior_zones: Previous probability zones (GeoJSON features)
            new_evidence: {
                'lat': float, 
                'lon': float, 
                'type': 'debris'|'signal'|'sighting',
                'confidence': 0-1,
                'timestamp': str,
                'reliability': 0-1
            }
        
        Returns:
            Updated probability zones with posterior probabilities
        """
        try:
            # Extract bounds from prior zones
            bounds = self._extract_bounds(prior_zones)
            
            # Create probability grid
            lons = np.linspace(bounds['min_lon'], bounds['max_lon'], self.grid_resolution)
            lats = np.linspace(bounds['min_lat'], bounds['max_lat'], self.grid_resolution)
            
            # Convert prior zones to probability grid
            prior_grid = self._create_probability_grid(prior_zones, lons, lats)
            
            # Calculate likelihood based on evidence
            likelihood_grid = self._calculate_likelihood(
                new_evidence, lons, lats
            )
            
            # Apply Bayes' theorem: P(H|E) = P(E|H) * P(H) / P(E)
            # Normalize to prevent numerical issues
            evidence_probability = np.sum(likelihood_grid * prior_grid)
            if evidence_probability == 0:
                logger.warning("Evidence probability is zero, using uniform prior")
                posterior_grid = prior_grid
            else:
                posterior_grid = (likelihood_grid * prior_grid) / evidence_probability
            
            # Normalize posterior to sum to 1
            posterior_grid = posterior_grid / np.sum(posterior_grid)
            
            # Convert back to zones
            updated_zones = self._create_zones_from_grid(
                posterior_grid, lons, lats, evidence_info=new_evidence
            )
            
            logger.info(f"Bayesian update completed with {new_evidence['type']} evidence")
            return updated_zones
            
        except Exception as e:
            logger.error(f"Bayesian update failed: {str(e)}")
            # Return original zones if update fails
            return prior_zones
    
    def _extract_bounds(self, zones: List[Dict[str, Any]]) -> Dict[str, float]:
        """Extract geographic bounds from zones"""
        all_coords = []
        
        for zone in zones:
            if zone.get('geometry', {}).get('type') == 'Polygon':
                coords = zone['geometry']['coordinates'][0]  # Exterior ring
                all_coords.extend(coords)
        
        if not all_coords:
            # Default bounds if no zones provided
            return {
                'min_lon': -180, 'max_lon': 180,
                'min_lat': -90, 'max_lat': 90
            }
        
        lons = [coord[0] for coord in all_coords]
        lats = [coord[1] for coord in all_coords]
        
        # Add buffer around bounds
        lon_buffer = (max(lons) - min(lons)) * 0.2
        lat_buffer = (max(lats) - min(lats)) * 0.2
        
        return {
            'min_lon': min(lons) - lon_buffer,
            'max_lon': max(lons) + lon_buffer,
            'min_lat': min(lats) - lat_buffer,
            'max_lat': max(lats) + lat_buffer
        }
    
    def _create_probability_grid(
        self, 
        zones: List[Dict[str, Any]], 
        lons: np.ndarray, 
        lats: np.ndarray
    ) -> np.ndarray:
        """Convert GeoJSON zones to probability grid using interpolation"""
        
        grid = np.zeros((len(lats), len(lons)))
        
        if not zones:
            # Uniform prior if no zones
            return np.ones_like(grid) / grid.size
        
        # Create meshgrid for interpolation
        lon_mesh, lat_mesh = np.meshgrid(lons, lats)
        grid_points = np.column_stack([lon_mesh.ravel(), lat_mesh.ravel()])
        
        # Collect probability values from zones
        zone_centers = []
        zone_probabilities = []
        
        for zone in zones:
            if zone.get('geometry', {}).get('type') == 'Polygon':
                # Get zone centroid and probability
                coords = zone['geometry']['coordinates'][0]
                polygon = Polygon(coords)
                centroid = polygon.centroid
                
                probability = zone.get('properties', {}).get('probability', 0.5)
                
                zone_centers.append([centroid.x, centroid.y])
                zone_probabilities.append(probability)
        
        if zone_centers:
            # Interpolate probabilities to grid
            interpolated_values = griddata(
                np.array(zone_centers),
                np.array(zone_probabilities),
                grid_points,
                method='linear',
                fill_value=0.1  # Low background probability
            )
            grid = interpolated_values.reshape(grid.shape)
        else:
            # Uniform prior
            grid = np.ones_like(grid) * 0.5
        
        # Normalize
        return grid / np.sum(grid)
    
    def _calculate_likelihood(
        self, 
        evidence: Dict[str, Any], 
        lons: np.ndarray, 
        lats: np.ndarray
    ) -> np.ndarray:
        """Calculate likelihood function based on evidence type and location"""
        
        # Create meshgrid
        lon_mesh, lat_mesh = np.meshgrid(lons, lats)
        
        # Evidence location
        evidence_lon = evidence['lat']
        evidence_lat = evidence['lon']
        confidence = evidence.get('confidence', 1.0)
        reliability = evidence.get('reliability', 1.0)
        
        # Calculate distance from evidence to each grid point
        distances = np.sqrt(
            (lon_mesh - evidence_lon)**2 + (lat_mesh - evidence_lat)**2
        )
        
        # Evidence-specific likelihood parameters
        if evidence['type'] == 'debris':
            # High confidence, concentrated likelihood
            sigma = 0.05 / confidence  # Tighter if more confident
            likelihood = np.exp(-0.5 * (distances / sigma)**2)
            
        elif evidence['type'] == 'signal':
            # Medium spread, could be reflected/scattered
            sigma = 0.1 / confidence
            likelihood = np.exp(-0.5 * (distances / sigma)**2)
            
        elif evidence['type'] == 'sighting':
            # Broader uncertainty due to human observation error
            sigma = 0.2 / confidence
            likelihood = np.exp(-0.5 * (distances / sigma)**2)
            
        elif evidence['type'] == 'negative':
            # Negative evidence (searched area with no findings)
            # Reduces probability in searched area
            sigma = 0.1
            likelihood = 1.0 - 0.8 * np.exp(-0.5 * (distances / sigma)**2)
            
        else:
            # Unknown evidence type, use neutral likelihood
            likelihood = np.ones_like(distances)
        
        # Apply reliability factor
        likelihood = reliability * likelihood + (1 - reliability) * np.ones_like(likelihood)
        
        # Normalize likelihood
        return likelihood / np.sum(likelihood)
    
    def _create_zones_from_grid(
        self, 
        grid: np.ndarray, 
        lons: np.ndarray, 
        lats: np.ndarray,
        evidence_info: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Convert probability grid back to GeoJSON zones using contour levels"""
        
        try:
            from matplotlib import pyplot as plt
            import matplotlib.path as mpath
            
            # Define probability contour levels
            levels = [0.95, 0.75, 0.50, 0.25]
            
            zones = []
            
            # Create contours
            fig, ax = plt.subplots()
            cs = ax.contour(lons, lats, grid, levels=levels)
            plt.close(fig)
            
            # Convert contours to GeoJSON
            for i, level in enumerate(levels):
                try:
                    # Get contour paths for this level
                    contour_paths = cs.collections[i].get_paths()
                    
                    for path in contour_paths:
                        # Convert path to polygon coordinates
                        vertices = path.vertices
                        if len(vertices) > 2:  # Valid polygon
                            # Close the polygon
                            coords = vertices.tolist()
                            if coords[0] != coords[-1]:
                                coords.append(coords[0])
                            
                            # Create GeoJSON feature
                            zone = {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [coords]
                                },
                                "properties": {
                                    "probability": level,
                                    "updated_with_evidence": True,
                                    "evidence_type": evidence_info.get('type') if evidence_info else None,
                                    "confidence": evidence_info.get('confidence') if evidence_info else None
                                }
                            }
                            zones.append(zone)
                            
                except Exception as e:
                    logger.warning(f"Failed to create contour for level {level}: {str(e)}")
                    continue
            
            return zones
            
        except ImportError:
            logger.warning("Matplotlib not available, creating simplified zones")
            return self._create_simplified_zones(grid, lons, lats)
        except Exception as e:
            logger.error(f"Contour creation failed: {str(e)}")
            return self._create_simplified_zones(grid, lons, lats)
    
    def _create_simplified_zones(
        self, 
        grid: np.ndarray, 
        lons: np.ndarray, 
        lats: np.ndarray
    ) -> List[Dict[str, Any]]:
        """Create simplified rectangular zones when contour creation fails"""
        
        # Find peak probability location
        max_idx = np.unravel_index(np.argmax(grid), grid.shape)
        peak_lat = lats[max_idx[0]]
        peak_lon = lons[max_idx[1]]
        
        # Create concentric rectangular zones
        zones = []
        sizes = [0.1, 0.2, 0.4, 0.8]  # Degrees
        probabilities = [0.95, 0.75, 0.50, 0.25]
        
        for size, prob in zip(sizes, probabilities):
            coords = [
                [peak_lon - size, peak_lat - size],
                [peak_lon + size, peak_lat - size],
                [peak_lon + size, peak_lat + size],
                [peak_lon - size, peak_lat + size],
                [peak_lon - size, peak_lat - size]  # Close polygon
            ]
            
            zone = {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords]
                },
                "properties": {
                    "probability": prob,
                    "updated_with_evidence": True,
                    "method": "simplified_rectangular"
                }
            }
            zones.append(zone)
        
        return zones

# Convenience functions for backward compatibility
async def update_probability(prior_zones, new_evidence):
    """Legacy function for backward compatibility"""
    engine = BayesianUpdateEngine()
    return await engine.update_probability_with_evidence(prior_zones, new_evidence)

def create_probability_grid(zones, lons, lats):
    """Legacy function for backward compatibility"""
    engine = BayesianUpdateEngine()
    return engine._create_probability_grid(zones, lons, lats)

def create_zones_from_grid(grid, lons, lats):
    """Legacy function for backward compatibility"""
    engine = BayesianUpdateEngine()
    return engine._create_zones_from_grid(grid, lons, lats)