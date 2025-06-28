import redis
import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from config import settings

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis cache manager for SAR simulation data"""
    
    def __init__(self):
        self.redis_client = None
        self.fallback_cache = {}  # In-memory fallback
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection with fallback to in-memory cache"""
        try:
            self.redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed: {str(e)}. Using in-memory fallback.")
            self.redis_client = None
    
    async def cache_simulation(self, key: str, data: Dict[str, Any], expire_seconds: int = None) -> bool:
        """Cache simulation data with expiration"""
        try:
            expire_time = expire_seconds or settings.SIMULATION_CACHE_EXPIRE
            serialized_data = json.dumps(data, default=str)
            
            if self.redis_client:
                try:
                    self.redis_client.setex(key, expire_time, serialized_data)
                    logger.info(f"Cached simulation data for key: {key}")
                    return True
                except Exception as e:
                    logger.error(f"Redis cache failed: {str(e)}")
                    # Fall back to in-memory cache
                    self._cache_in_memory(key, data, expire_time)
                    return True
            else:
                # Use in-memory cache
                self._cache_in_memory(key, data, expire_time)
                return True
                
        except Exception as e:
            logger.error(f"Cache operation failed: {str(e)}")
            return False
    
    async def get_cached_simulation(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached simulation data"""
        try:
            if self.redis_client:
                try:
                    cached_data = self.redis_client.get(key)
                    if cached_data:
                        return json.loads(cached_data)
                except Exception as e:
                    logger.error(f"Redis get failed: {str(e)}")
                    # Fall back to in-memory cache
                    return self._get_from_memory(key)
            else:
                # Use in-memory cache
                return self._get_from_memory(key)
                
        except Exception as e:
            logger.error(f"Cache retrieval failed: {str(e)}")
            
        return None
    
    def _cache_in_memory(self, key: str, data: Dict[str, Any], expire_seconds: int):
        """Cache data in memory with expiration"""
        expire_time = datetime.now() + timedelta(seconds=expire_seconds)
        self.fallback_cache[key] = {
            'data': data,
            'expires_at': expire_time
        }
        logger.info(f"Cached in memory: {key}")
    
    def _get_from_memory(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from in-memory cache"""
        if key in self.fallback_cache:
            cached_item = self.fallback_cache[key]
            if datetime.now() < cached_item['expires_at']:
                return cached_item['data']
            else:
                # Expired, remove from cache
                del self.fallback_cache[key]
        return None
    
    async def clear_cache(self, pattern: str = None) -> bool:
        """Clear cache entries matching pattern or all if no pattern"""
        try:
            if self.redis_client:
                if pattern:
                    keys = self.redis_client.keys(pattern)
                    if keys:
                        self.redis_client.delete(*keys)
                else:
                    self.redis_client.flushdb()
            
            # Clear in-memory cache
            if pattern:
                keys_to_remove = [k for k in self.fallback_cache.keys() if pattern in k]
                for k in keys_to_remove:
                    del self.fallback_cache[k]
            else:
                self.fallback_cache.clear()
            
            logger.info(f"Cache cleared with pattern: {pattern}")
            return True
            
        except Exception as e:
            logger.error(f"Cache clear failed: {str(e)}")
            return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "redis_available": self.redis_client is not None,
            "fallback_cache_size": len(self.fallback_cache),
            "timestamp": datetime.now().isoformat()
        }
        
        if self.redis_client:
            try:
                info = self.redis_client.info()
                stats.update({
                    "redis_memory_used": info.get('used_memory_human', 'N/A'),
                    "redis_connected_clients": info.get('connected_clients', 0),
                    "redis_total_connections": info.get('total_connections_received', 0)
                })
            except Exception as e:
                logger.error(f"Failed to get Redis stats: {str(e)}")
                stats["redis_error"] = str(e)
        
        return stats

# Create global cache instance
cache_manager = RedisCache()

# Legacy wrapper functions for backward compatibility
async def cache_simulation(key: str, geojson: dict):
    """Legacy function for backward compatibility"""
    return await cache_manager.cache_simulation(key, geojson)

async def get_cached_simulation(key: str):
    """Legacy function for backward compatibility"""
    return await cache_manager.get_cached_simulation(key)