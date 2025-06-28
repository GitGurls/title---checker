import os

class Settings:
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    SIMULATION_CACHE_EXPIRE = 3600  # 1 hour
    MONTE_CARLO_SIMULATIONS = 2000
    FUEL_DENSITY = 0.8  # kg/L
    FUEL_FLOW_RATE = 0.05  # kg/s per engine

settings = Settings()