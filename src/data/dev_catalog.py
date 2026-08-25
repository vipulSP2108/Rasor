"""Dev mock catalog provider with full attribute filtering."""

import json
import os
import re
from typing import List, Optional
from src.agent.state import Product
from src.data.base import BaseCatalogProvider

_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "mock_products.json")
_KNOWN_COLORS = [
    "black", "blue", "white", "red", "green", "grey", "gray", "yellow", 
    "orange", "maroon", "beige", "brown", "purple", "pink", "navy", "cyan", "volt"
]


class DevCatalogProvider(BaseCatalogProvider):
    """Provides product search against local JSON database for deterministic development."""

    def __init__(self, catalog_path: str = _CATALOG_PATH):
        self.catalog_path = catalog_path
        self._products: List[Product] = self._load()
        self.last_status_message: str = "Loaded from Dev Mock Catalog."
        self.last_used_source: str = "dev_mock"

    def _load(self) -> List[Product]:
        if not os.path.exists(self.catalog_path):
            return []
        with open(self.catalog_path, "r", encoding="utf-8") as f:
            raw_list = json.load(f)
            return [Product(**item) for item in raw_list]

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
        limit: int = 6
    ) -> List[Product]:
        q_lower = query.lower()

        target_color = color.lower() if color else None
        if not target_color:
            for c in _KNOWN_COLORS:
                if re.search(rf"\b{c}\b", q_lower):
                    target_color = c
                    break

        query_terms = [t for t in q_lower.split() if t not in _KNOWN_COLORS]
        matches: List[Product] = []

        for p in self._products:
            if not p.in_stock:
                continue
            if merchant and p.merchant.lower() != merchant.lower():
                continue
            if category and p.category.lower() != category.lower():
                continue
            if max_price is not None and p.price > max_price:
                continue
            if min_rating is not None and p.rating < min_rating:
                continue

            # Size check
            if size:
                prod_size = str(p.specs.get("size", "")).upper()
                if size.upper() != prod_size and size.upper() not in [str(s).upper() for s in p.specs.get("available_sizes", [])]:
                    continue

            # Color check
            prod_color = str(p.specs.get("color", "")).lower()
            specs_str = " ".join(f"{k} {v}" for k, v in p.specs.items()).lower()
            searchable = f"{p.title} {p.brand} {p.category} {p.description} {' '.join(p.tags)} {specs_str}".lower()

            if target_color and (target_color not in prod_color and target_color not in searchable):
                continue

            matches.append(p)

        matches.sort(key=lambda x: (-x.rating, x.price))
        self.last_status_message = f"🟢 Retrieved {len(matches)} products from Dev Mock Catalog."
        return matches[:limit]

    def enrich_product(self, product: Product) -> Product:
        # We don't have deep details in the dev catalog beyond what is already returned.
        product.enriched = True
        return product
