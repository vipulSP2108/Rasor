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

PINCODE_MAP = {
    "11": ("Delhi Hub (North Fulfillment Center)", (28.7041, 77.1025)),
    "12": ("Gurugram / Haryana Hub", (28.4595, 77.0266)),
    "40": ("Mumbai Central Warehouse (Bhandup Hub)", (19.0760, 72.8777)),
    "41": ("Pune Fulfillment Center", (18.5204, 73.8567)),
    "56": ("Bengaluru Hub (South Fulfillment Center)", (12.9716, 77.5946)),
    "60": ("Chennai Hub", (13.0827, 80.2707)),
    "70": ("Kolkata East Hub", (22.5726, 88.3639)),
    "50": ("Hyderabad Hub", (17.3850, 78.4867)),
    "38": ("Ahmedabad / Gujarat Hub", (23.0225, 72.5714)),
    "64": ("Tirupur Textile Hub (TN)", (11.1085, 77.3411)),
}

def resolve_product_origin(product_specs: dict) -> Tuple[str, Tuple[float, float]]:
    """Detects manufacturing/warehouse location from product specs."""
    if not isinstance(product_specs, dict):
        return "Mumbai Main Warehouse (Bhandup, MH)", (19.0760, 72.8777)
        
    mfg = (product_specs.get("manufactured_by") or product_specs.get("packed_by") or "").lower()
    brand = (product_specs.get("brand") or "").lower()
    
    if "bhandup" in mfg or "mumbai" in mfg or "pagal awwrat" in brand or "bewakoof" in brand:
        return "Mumbai Central Hub (Bhandup, MH)", (19.0760, 72.8777)
    elif "tirupur" in mfg or "tamil nadu" in mfg:
        return "Tirupur Textile Hub (Tamil Nadu)", (11.1085, 77.3411)
    elif "surat" in mfg or "gujarat" in mfg or "ahmedabad" in mfg:
        return "Surat / Gujarat Hub", (21.1702, 72.8311)
    elif "delhi" in mfg or "noida" in mfg or "gurugram" in mfg or "haryana" in mfg:
        return "Delhi NCR Hub", (28.7041, 77.1025)
    elif "bangalore" in mfg or "bengaluru" in mfg:
        return "Bengaluru Hub", (12.9716, 77.5946)
    
    return "Mumbai Main Warehouse (Bhandup, MH)", (19.0760, 72.8777)

def calculate_detailed_product_shipping(product_specs: dict, user_location_or_pincode: str) -> dict:
    """Calculates origin hub, user destination coords, distance in KM, and transit time."""
    origin_name, origin_coords = resolve_product_origin(product_specs)
    dest_name = user_location_or_pincode or "Mumbai, Maharashtra"
    
    # Check pincode prefix
    pin_clean = "".join(filter(str.isdigit, str(dest_name)))
    dest_coords = None
    if len(pin_clean) >= 2 and pin_clean[:2] in PINCODE_MAP:
        area_label, coords = PINCODE_MAP[pin_clean[:2]]
        dest_coords = coords
        dest_name = f"{dest_name} ({area_label.split('(')[0].strip()})"
    
    if not dest_coords:
        dest_coords = get_coordinates(dest_name)
    
    dist_km = round(haversine(origin_coords[0], origin_coords[1], dest_coords[0], dest_coords[1]))
    
    if dist_km < 60:
        days = 1
        speed_label = "1 Day"
    elif dist_km < 450:
        days = 2
        speed_label = "2 Days"
    elif dist_km < 1200:
        days = 3
        speed_label = "3 Days"
    else:
        days = 4
        speed_label = "4 Days"
        
    return {
        "origin_hub": origin_name,
        "destination": dest_name,
        "distance_km": dist_km,
        "shipping_days": days,
        "speed_label": speed_label
    }

