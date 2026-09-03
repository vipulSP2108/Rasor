"""
Logistics & Delivery Routing Agent for Rasor E-Commerce.

Utilizes open APIs (Zippopotam & OpenStreetMap Nominatim) with local caching
to resolve Indian postal codes and cities, geocode coordinates, and compute
precise geodesic distances and shipping timelines from multi-hub fulfillment centers.
"""

import math
import requests
import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple

CACHE_FILE = "/Users/aai/Desktop/Rasor/src/data/geocode_cache.json"

# Core Fulfillment Warehouses across India
FULFILLMENT_HUBS = {
    "mumbai_bhandup": {
        "name": "Mumbai Central Hub (Bhandup, MH)",
        "city": "Mumbai",
        "state": "Maharashtra",
        "coords": (19.0760, 72.8777)
    },
    "tirupur_hub": {
        "name": "Tirupur Textile Hub (Tamil Nadu)",
        "city": "Tirupur",
        "state": "Tamil Nadu",
        "coords": (11.1085, 77.3411)
    },
    "delhi_ncr": {
        "name": "Delhi NCR Fulfillment Center (Gurugram)",
        "city": "Delhi NCR",
        "state": "Delhi",
        "coords": (28.7041, 77.1025)
    },
    "surat_garments": {
        "name": "Surat Garment Hub (Gujarat)",
        "city": "Surat",
        "state": "Gujarat",
        "coords": (21.1702, 72.8311)
    },
    "bengaluru_south": {
        "name": "Bengaluru South Hub (Karnataka)",
        "city": "Bengaluru",
        "state": "Karnataka",
        "coords": (12.9716, 77.5946)
    },
    "kolkata_east": {
        "name": "Kolkata East Hub (West Bengal)",
        "city": "Kolkata",
        "state": "West Bengal",
        "coords": (22.5726, 88.3639)
    }
}


def _load_cache() -> Dict[str, Any]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: Dict[str, Any]):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"[LogisticsAgent] Failed to write cache: {e}")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate geodesic distance in kilometers using Haversine formula."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class LogisticsAgent:
    """Agent responsible for geocoding user destinations, warehouse resolution, and shipping estimation."""

    def __init__(self):
        self.headers = {
            "User-Agent": "RasorCommerceAgent/1.0 (logistics@rasor.ai)"
        }

    def resolve_destination(self, query: str) -> Dict[str, Any]:
        """
        Geocodes a pincode (e.g. '400001') or city name (e.g. 'Mumbai') using Open APIs.
        Returns: { 'pincode', 'area', 'city', 'state', 'coords': (lat, lon), 'display_label': str }
        """
        raw = (query or "400001").strip()
        cache_key = raw.lower()
        cache = _load_cache()
        if cache_key in cache:
            return cache[cache_key]

        # 1. Check if query contains a 6-digit Indian pincode
        pin_match = re.search(r"\b([1-9][0-9]{5})\b", raw)
        pincode = pin_match.group(1) if pin_match else None

        result = None

        # Strategy A: Zippopotam Open Pincode API
        if pincode:
            try:
                url = f"https://api.zippopotam.us/in/{pincode}"
                resp = requests.get(url, headers=self.headers, timeout=4)
                if resp.status_code == 200:
                    d = resp.json()
                    places = d.get("places", [])
                    if places:
                        primary_place = places[0]
                        area = primary_place.get("place name") or ""
                        state = primary_place.get("state") or ""
                        lat = float(primary_place.get("latitude") or 19.0760)
                        lon = float(primary_place.get("longitude") or 72.8777)
                        
                        # Format clean city label
                        city_name = area
                        if state: city_name = f"{area}, {state}"

                        result = {
                            "query": raw,
                            "pincode": pincode,
                            "area": area,
                            "city": city_name,
                            "state": state,
                            "coords": [lat, lon],
                            "display_label": f"{area} ({pincode}, {state})",
                            "source": "zippopotam_open_api"
                        }
            except Exception as e:
                print(f"[LogisticsAgent] Zippopotam lookup error for {pincode}: {e}")

        # Strategy B: OpenStreetMap Nominatim Open API
        if not result:
            try:
                search_q = f"postalcode={pincode}&country=India" if pincode else f"q={raw}, India"
                url = f"https://nominatim.openstreetmap.org/search?{search_q}&format=json&limit=1"
                resp = requests.get(url, headers=self.headers, timeout=4)
                if resp.status_code == 200:
                    items = resp.json()
                    if items:
                        first = items[0]
                        lat = float(first.get("lat") or 19.0760)
                        lon = float(first.get("lon") or 72.8777)
                        disp = first.get("display_name", raw)
                        parts = [p.strip() for p in disp.split(",")]
                        area_name = parts[0] if parts else raw
                        state_name = parts[-2] if len(parts) >= 2 else "India"

                        result = {
                            "query": raw,
                            "pincode": pincode or "400001",
                            "area": area_name,
                            "city": f"{area_name}, {state_name}",
                            "state": state_name,
                            "coords": [lat, lon],
                            "display_label": f"{area_name} ({pincode or 'India'})",
                            "source": "osm_nominatim_open_api"
                        }
            except Exception as e:
                print(f"[LogisticsAgent] Nominatim lookup error for {raw}: {e}")

        # Fallback default (Mumbai)
        if not result:
            result = {
                "query": raw,
                "pincode": pincode or "400001",
                "area": "Mumbai Central",
                "city": "Mumbai, Maharashtra",
                "state": "Maharashtra",
                "coords": [19.0760, 72.8777],
                "display_label": f"Mumbai ({pincode or '400001'})",
                "source": "fallback_default"
            }

        cache[cache_key] = result
        if pincode: cache[pincode] = result
        _save_cache(cache)
        return result

    def resolve_product_hub(self, product_specs: Dict[str, Any]) -> Dict[str, Any]:
        """Resolves the exact manufacturing facility & warehouse from live Bewakoof v2 metadata."""
        if not isinstance(product_specs, dict):
            return FULFILLMENT_HUBS["mumbai_bhandup"]

        mfg = str(product_specs.get("manufactured_by") or product_specs.get("packed_by") or "").strip()
        seller = str(product_specs.get("seller_name") or product_specs.get("brand") or "").strip()
        origin_pin = product_specs.get("origin_pincode")
        
        if not origin_pin and mfg:
            pin_match = re.search(r"\b([1-9][0-9]{5})\b", mfg)
            if pin_match:
                origin_pin = pin_match.group(1)

        # 1. If we have an exact origin pincode from live v2, geocode it using Open API!
        if origin_pin:
            dest_info = self.resolve_destination(origin_pin)
            facility_name = seller or (mfg.split(",")[0] if mfg else "Manufacturing Hub")
            clean_origin_name = f"{facility_name} ({dest_info.get('area', '')}, {dest_info.get('state', '')})"
            return {
                "name": clean_origin_name,
                "city": dest_info.get("city", "India"),
                "state": dest_info.get("state", "India"),
                "pincode": origin_pin,
                "coords": dest_info["coords"],
                "source": "live_v2_pdp_manufacturer"
            }

        # 2. Fuzzy address matching for named industrial hubs
        mfg_lower = mfg.lower()
        if "ludhiana" in mfg_lower or "punjab" in mfg_lower:
            return {
                "name": f"{seller or 'Swastik Knitwears'} (Ludhiana, Punjab)",
                "city": "Ludhiana",
                "state": "Punjab",
                "coords": (30.9010, 75.8573),
                "source": "live_v2_pdp_manufacturer"
            }
        elif "bhiwandi" in mfg_lower or "thane" in mfg_lower or "421302" in mfg_lower:
            return {
                "name": "Bewakoof Central Logistics Hub (Bhiwandi, Thane)",
                "city": "Thane / Mumbai",
                "state": "Maharashtra",
                "coords": (19.2967, 73.0631),
                "source": "live_v2_pdp_manufacturer"
            }
        elif "pitampura" in mfg_lower or "rajouri garden" in mfg_lower or "delhi" in mfg_lower:
            return {
                "name": f"{seller or 'Qrioh/Unico'} (Pitampura, New Delhi)",
                "city": "New Delhi",
                "state": "Delhi",
                "coords": (28.7032, 77.1322),
                "source": "live_v2_pdp_manufacturer"
            }
        elif "bhandup" in mfg_lower or "mumbai" in mfg_lower:
            return {
                "name": f"{seller or 'Pagal Awwrat'} (Bhandup, Mumbai)",
                "city": "Mumbai",
                "state": "Maharashtra",
                "coords": (19.1438, 72.9367),
                "source": "live_v2_pdp_manufacturer"
            }
        elif "tirupur" in mfg_lower or "tamil nadu" in mfg_lower:
            return FULFILLMENT_HUBS["tirupur_hub"]
        elif "surat" in mfg_lower or "gujarat" in mfg_lower:
            return FULFILLMENT_HUBS["surat_garments"]

        # Default fallback
        return FULFILLMENT_HUBS["mumbai_bhandup"]

    def calculate_delivery_estimate(
        self,
        product_specs: Dict[str, Any],
        user_location_query: str
    ) -> Dict[str, Any]:
        """Calculates distance in KM, shipping timeline, and transit velocity for a product."""
        dest = self.resolve_destination(user_location_query)
        origin_hub = self.resolve_product_hub(product_specs)

        u_lat, u_lon = dest["coords"]
        o_lat, o_lon = origin_hub["coords"]

        dist_km = round(haversine_km(o_lat, o_lon, u_lat, u_lon))

        if dist_km < 60:
            shipping_days = 1
            speed_label = "⚡ Same-Day / 1-Day Metro Express"
            tier = "metro_express"
        elif dist_km < 450:
            shipping_days = 2
            speed_label = "⚡ 1-2 Days Regional Air Express"
            tier = "regional_express"
        elif dist_km < 1200:
            shipping_days = 3
            speed_label = "✈️ 2-3 Days Fast Air Transit"
            tier = "national_air"
        else:
            shipping_days = 4
            speed_label = "🚚 3-4 Days Standard Surface"
            tier = "standard_surface"

        return {
            "origin_hub": origin_hub["name"],
            "origin_city": origin_hub["city"],
            "destination_display": dest["display_label"],
            "destination_city": dest["city"],
            "destination_state": dest["state"],
            "destination_pincode": dest["pincode"],
            "distance_km": dist_km,
            "shipping_days": shipping_days,
            "speed_label": speed_label,
            "tier": tier
        }
