import math
import requests
import json
import os
from typing import Tuple

# Cache file to avoid spamming Nominatim API
CACHE_FILE = "/Users/aai/Desktop/Rasor/src/data/geocode_cache.json"

# Pre-defined warehouse coordinates (Lat, Lon)
WAREHOUSES = {
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.7041, 77.1025),
    "Bengaluru": (12.9716, 77.5946)
}

def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def _save_cache(cache: dict):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def get_coordinates(city_name: str) -> Tuple[float, float]:
    """Geocodes a city name to Lat/Lon using OpenStreetMap Nominatim API."""
    city_key = city_name.strip().lower()
    
    # Check cache first
    cache = _load_cache()
    if city_key in cache:
        return tuple(cache[city_key])
    
    # Not in cache, call API
    headers = {
        "User-Agent": "RasorCommerceAgent/1.0 (test@example.com)"
    }
    url = f"https://nominatim.openstreetmap.org/search?q={city_name}, India&format=json&limit=1"
    
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                cache[city_key] = [lat, lon]
                _save_cache(cache)
                return (lat, lon)
    except Exception as e:
        print(f"[Logistics] Geocode API error for {city_name}: {e}")
    
    # Fallback default (center of India approx)
    return (22.9, 78.6)

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in KM between two coordinates using Haversine formula."""
    R = 6371.0 # Earth radius in km
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_shipping_days(user_city: str) -> int:
    """Calculates shipping days based on distance to nearest warehouse."""
    if not user_city or user_city.lower() == "not set":
        return 4 # Default standard
        
    user_coords = get_coordinates(user_city)
    
    # Find closest warehouse
    min_dist = float('inf')
    for hub, coords in WAREHOUSES.items():
        dist = haversine(user_coords[0], user_coords[1], coords[0], coords[1])
        if dist < min_dist:
            min_dist = dist
            
    # Calculate days based on distance brackets
    if min_dist < 50:
        return 1   # Same city / Metro express
    elif min_dist < 400:
        return 2   # Regional
    elif min_dist < 1000:
        return 3   # National
    else:
        return 5   # Far reaches (e.g. North East, remote)

