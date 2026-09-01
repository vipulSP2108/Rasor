"""Live Bewakoof.com Authenticated API Catalog Provider.

Uses:
- HandleRegistry (schema_mapper.py) to resolve the most specific collection handle.
- UniversalProductMapper (schema_mapper.py) for store-agnostic JSON -> Product conversion.
- Character-level post-filter for specific character queries (Iron Man within Marvel, etc.)
- Subclass post-filter to prevent category bleed (t-shirts only returns T-Shirts).
"""

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import requests

from src.agent.state import Product
from src.data.base import BaseCatalogProvider
from src.data.schema_mapper import (
    BEWAKOOF_FIELD_MAP,
    UniversalProductMapper,
    resolve_handle,
)

_DEFAULT_TOKEN = os.getenv("BEWAKOOF_CLIENT_DEVICE_TOKEN") or os.getenv("BEWAKOOF_API_TOKEN", "")

# Specific characters within a fandom — used for post-filter (only when explicitly named)
_CHARACTER_KEYWORDS: Dict[str, List[str]] = {
    # Marvel characters
    "iron man":         ["iron man", "tony stark", "ironman"],
    "spider man":       ["spider man", "spiderman", "spider-man", "spidey", "peter parker"],
    "captain america":  ["captain america", "steve rogers", "cap"],
    "thor":             ["thor", "asgard"],
    "deadpool":         ["deadpool", "wade wilson", "dead pool"],
    "hulk":             ["hulk", "bruce banner"],
    "black panther":    ["black panther", "black pantheer", "panther", "pantheer", "wakanda", "t'challa", "tchalla"],
    "wolverine":        ["wolverine", "logan"],
    # DC characters
    "batman":           ["batman", "dark knight", "bruce wayne", "gotham"],
    "superman":         ["superman", "clark kent", "man of steel"],
    "joker":            ["joker"],
    "flash":            ["flash", "barry allen"],
    # Disney characters
    "mickey mouse":     ["mickey", "mickey mouse"],
    "minnie mouse":     ["minnie"],
    "donald duck":      ["donald duck"],
    # Anime characters
    "naruto":           ["naruto", "uzumaki", "hokage"],
    # Friends characters
    "chandler":         ["chandler", "bing"],
    "ross":             ["ross geller", "ross"],
    # General wildcards
    "harry potter":     ["harry potter", "harry", "potter", "hogwarts"],
    "garfield":         ["garfield"],
    "tom jerry":        ["tom and jerry", "tom & jerry", "tom jerry"],
}

def _detect_specific_character(prompt_lower: str) -> Optional[str]:
    """Returns the specific character keyword to filter by, or None if just fandom-level."""
    import re
    # Sort characters by longest keyword first to avoid greedy substring collisions
    for char_name, keywords in _CHARACTER_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", prompt_lower):
                return char_name
    return None


class BewakoofCatalogProvider(BaseCatalogProvider):
    """Live API integration with Bewakoof.com using Handle Registry & Universal Schema Mapper."""

    def __init__(
        self,
        api_token: Optional[str] = None,
        client_device_token: Optional[str] = None,
        fallback_provider: Optional[BaseCatalogProvider] = None,
    ):
        self.api_token = api_token or os.getenv("BEWAKOOF_API_TOKEN", _DEFAULT_TOKEN)
        self.client_device_token = client_device_token or os.getenv("BEWAKOOF_CLIENT_DEVICE_TOKEN", self.api_token)
        self.mapper = UniversalProductMapper(field_map=BEWAKOOF_FIELD_MAP)
        self.last_status_message: str = "Initialized"
        self.last_used_source: str = "bewakoof_live_api"

        # Lazy import fallback to avoid circular imports
        self._fallback_provider = fallback_provider

    @property
    def fallback(self) -> BaseCatalogProvider:
        if self._fallback_provider is None:
            from src.data.dev_catalog import DevCatalogProvider
            self._fallback_provider = DevCatalogProvider()
        return self._fallback_provider

    def _headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "api-token": self.api_token,
            "client-device-token": self.client_device_token,
            "x-client-device-token": self.client_device_token,
            "ab-id": "100",
            "preferred-location": "IN",
            "referer": "https://www.bewakoof.com/",
            "origin": "https://www.bewakoof.com",
            "user-agent": (
                "Mozilla/5.0 (Linux; Android 15; Pixel 9) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Mobile Safari/537.36"
            ),
        }

    def _fetch_collection(self, handle: str, fetch_limit: int = 60) -> List[Dict[str, Any]]:
        """Fetches raw products from a single collection handle."""
        product_fields = (
            "id,name,url,mrp,price,display_image,in_stock,status,"
            "gender,color_name,product_attributes,product_sizes,"
            "cat_designer,offer_tags,subclass,category_info,member_price,ratings_avg,ratings_count"
        )
        url = (
            f"{os.getenv('BEWAKOOF_API_BASE_URL', '')}{os.getenv('BEWAKOOF_COLLECTION_ENDPOINT', '')}/{handle}"
            f"?qf=true&sort=popular&page=1&limit={fetch_limit}&fields=results"
            f"&product_fields={product_fields}"
        )
        resp = requests.get(url, headers=self._headers(), timeout=8)
        if resp.status_code == 200:
            return resp.json().get("products", [])
        if resp.status_code == 404:
            print(f"[Bewakoof] Handle '{handle}' → 404. Will use fallback.")
        else:
            print(f"[Bewakoof] Handle '{handle}' → HTTP {resp.status_code}")
        return []

    def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        gender: Optional[str] = None,
        color: Optional[str] = None,
        size: Optional[str] = None,
        design: Optional[str] = None,
        fandom: Optional[str] = None,
        fit: Optional[str] = None,
        sleeve: Optional[str] = None,
        fabric: Optional[str] = None,
        neck: Optional[str] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        merchant: Optional[str] = None,
        limit: int = 6,
    ) -> List[Product]:

        g = (gender or "men").lower()
        prompt_lower = (query or "").lower()

        # ── Step 1: Resolve most specific collection handle ──────────────────
        handle, needs_subclass_filter = resolve_handle(
            gender=g,
            category=category,
            sleeve=sleeve,
            fandom=fandom,
            design=design,
            fit=fit,
        )
        print(f"📡 [Bewakoof] handle='{handle}' | gender={g} | category={category} | sleeve={sleeve} | fandom={fandom} | design={design} | color={color}")

        # ── Step 2: Fetch from Bewakoof API ───────────────────────────────────
        # NOTE: Bewakoof returns HTTP 400 when limit > the collection's total item count.
        # Most themed/specific collections (men-t-shirts, marvel, batman-merchandise) have ~25-48 items.
        # Hard cap at 48 to stay within safe range for all collection sizes.
        safe_fetch_limit = min(max(limit * 4, 24), 48)
        try:
            raw_products = self._fetch_collection(handle, fetch_limit=safe_fetch_limit)
        except Exception as e:
            self.last_status_message = f"⚠️ Bewakoof request failed: {e}. Fallback triggered."
            self.last_used_source = "fallback_dev_catalog"
            return self.fallback.search_products(query, category, gender, color, size, design, fandom, fit, sleeve, fabric, neck, max_price, min_rating, merchant, limit)

        if not raw_products:
            # Handle 404 or empty — try one level up (gender fallback)
            fallback_handle = f"{g}-clothing"
            print(f"[Bewakoof] '{handle}' empty. Trying '{fallback_handle}'.")
            try:
                raw_products = self._fetch_collection(fallback_handle, fetch_limit=60)
            except Exception:
                pass

        if not raw_products:
            self.last_status_message = "⚠️ No products from API. Fallback triggered."
            self.last_used_source = "fallback_dev_catalog"
            return self.fallback.search_products(query, category, gender, color, size, design, fandom, fit, sleeve, fabric, neck, max_price, min_rating, merchant, limit)

        # ── Step 3: Map raw JSON to canonical Products ────────────────────────
        query_terms = [t for t in prompt_lower.split() if len(t) > 2]
        all_products: List[Product] = []
        for raw in raw_products:
            p = self.mapper.map(raw, query_terms)
            if p:
                all_products.append(p)

        # ── Step 4: Post-filters ──────────────────────────────────────────────

        # 4a. Subclass filter (category bleed prevention)
        #     e.g. men-clothing should only return T-Shirts when user asked for t-shirts
        if needs_subclass_filter and category:
            SUBCLASS_MAP = {
                "t-shirt":  ["T-Shirt", "Tee"],
                "hoodie":   ["Hoodies", "Sweatshirt", "Hoodie"],
                "joggers":  ["Joggers", "Track Pants"],
                "jeans":    ["Jeans", "Denim"],
                "shirt":    ["Shirt"],
                "sliders":  ["Sliders", "Flip Flops & Sliders", "Clogs"],
                "footwear": ["Sliders", "Casual Shoes", "Clogs", "Flip Flops & Sliders"],
            }
            allowed_subclasses = SUBCLASS_MAP.get(category.lower(), [])
            if allowed_subclasses:
                all_products = [
                    p for p in all_products
                    if any(
                        sub.lower() in p.specs.get("subclass", "").lower()
                        for sub in allowed_subclasses
                    )
                ]
            else:
                # Category is not supported in this generic handle (e.g., mobile covers in men-clothing).
                # Empty the list to force a fallback to scraper or dev catalog.
                all_products = []

        # 4b. Color filter
        if color and color.lower() != "any":
            cl = color.lower()
            all_products = [
                p for p in all_products
                if cl in p.specs.get("color", "").lower()
            ]

        # 4c. Design filter
        if design and design.lower() != "any":
            dl = design.lower()
            all_products = [
                p for p in all_products
                if dl in p.specs.get("design", "").lower()
            ]

        # 4d. Fit filter
        if fit and fit.lower() != "any":
            fl = fit.lower()
            all_products = [
                p for p in all_products
                if fl in p.specs.get("fit", "").lower()
            ]

        # 4e. Sleeve filter
        if sleeve and sleeve.lower() != "any":
            sl = sleeve.lower()
            all_products = [
                p for p in all_products
                if sl in p.specs.get("sleeve", "").lower()
            ]

        # 4f. Fabric filter
        if fabric and fabric.lower() != "any":
            fb = fabric.lower()
            all_products = [
                p for p in all_products
                if fb in p.specs.get("fabric", "").lower()
            ]

        # 4g. Neck filter
        if neck and neck.lower() != "any":
            nk = neck.lower()
            all_products = [
                p for p in all_products
                if nk in p.specs.get("neck", "").lower()
            ]

        # 4f. Size filter
        if size:
            sz = size.upper()
            all_products = [
                p for p in all_products
                if sz in [s.upper() for s in p.specs.get("available_sizes", [])]
            ]

        # 4g. Price filter
        if max_price is not None:
            all_products = [p for p in all_products if p.price <= max_price]

        # 4h. Rating filter
        if min_rating is not None:
            all_products = [p for p in all_products if p.rating >= min_rating]

        # 4i. Character-level post-filter
        #     "Iron Man" → Marvel collection → only keep items with "Iron Man" in title
        #     "Batman" → batman-merchandise → keep all (already scoped)
        #     "Marvel" → marvel collection → keep all Marvel items (no specific char)
        specific_char = _detect_specific_character(prompt_lower)
        if specific_char and fandom:
            char_keywords = _CHARACTER_KEYWORDS.get(specific_char, [])
            char_filtered = [
                p for p in all_products
                if any(kw in p.title.lower() for kw in char_keywords)
            ]
            # Only apply if we got results — otherwise keep the full set
            if char_filtered:
                all_products = char_filtered
                print(f"[Bewakoof] Character post-filter '{specific_char}' → {len(char_filtered)} items")

        # ── Step 5: Status & Return ───────────────────────────────────────────
        if all_products:
            filters = [g.title()]
            if color and color != "Any": filters.append(color)
            if design and design != "Any": filters.append(design)
            if fandom and fandom not in ("None", ""): filters.append(f"Theme:{fandom}")
            if specific_char and fandom: filters.append(f"Char:{specific_char}")
            if sleeve and sleeve != "Any": filters.append(sleeve)
            if fabric and fabric != "Any": filters.append(f"Fabric:{fabric}")
            if neck and neck != "Any": filters.append(f"Neck:{neck}")
            if size: filters.append(f"Size:{size}")
            self.last_status_message = f"🟢 {len(all_products)} products [{' | '.join(filters)}] from handle '{handle}'"
        else:
            # If we cleared all_products because the category was completely unsupported in this handle, skip trending.
            is_unsupported_category = needs_subclass_filter and category and not SUBCLASS_MAP.get(category.lower())
            
            if not is_unsupported_category:
                # Relaxed fallback: return top trending items from same handle without attribute filters
                trending = [self.mapper.map(r, query_terms) for r in raw_products[:limit] if self.mapper.map(r, query_terms)]
            else:
                trending = []
                
            if trending:
                self.last_status_message = f"ℹ️ Exact filters matched 0 items. Showing top trending from '{handle}'."
                all_products = trending
            else:
                self.last_status_message = "⚠️ 0 matches even after relaxation. Fallback triggered."
                self.last_used_source = "fallback_dev_catalog"
                return self.fallback.search_products(query, category, gender, color, size, design, fandom, fit, sleeve, fabric, neck, max_price, min_rating, merchant, limit)

        self.last_used_source = "bewakoof_live_api"
        print(self.last_status_message)
        return all_products[:limit]

    def enrich_product(self, product: Product) -> Product:
        # Extract numeric id
        pid = product.id.split("-")[-1] if "-" in product.id else product.id
        url = f"{os.getenv('BEWAKOOF_API_BASE_URL', '')}{os.getenv('BEWAKOOF_PDP_ENDPOINT', '')}/{pid}"
        
        delay = 0.3
        max_delay = 1.5
        
        while delay <= max_delay:
            try:
                resp = requests.get(url, headers=self._headers(), timeout=4)
                if resp.status_code == 200:
                    data = resp.json()
                    ratings = data.get("ratings")
                    if ratings and isinstance(ratings, dict):
                        product.rating = float(ratings.get("avg") or product.rating)
                        product.review_count = int(ratings.get("count") or product.review_count)
                    
                    desc = data.get("description")
                    if desc and isinstance(desc, dict):
                        product.rich_description = desc.get("heading")
                    product.enriched = True
                    break
                elif resp.status_code in (403, 429, 500, 502, 503, 504):
                    print(f"[Bewakoof] Enrich {pid} got HTTP {resp.status_code}. Backing off {delay:.2f}s...")
                    time.sleep(delay)
                    delay *= 2  # 0.3s -> 0.6s -> 1.2s -> exceeds 1.5s
                else:
                    print(f"[Bewakoof] Enrich {pid} got HTTP {resp.status_code}. Proceeding.")
                    break
            except Exception as e:
                print(f"[Bewakoof] Enrich failed for {pid}: {e}. Backing off {delay:.2f}s...")
                time.sleep(delay)
                delay *= 2
                
        return product
