"""Live Bewakoof.com Authenticated API Catalog Provider with multi-attribute styling and fandom routing."""

import os
import json
import re
from typing import Any, Dict, List, Optional
import requests
from src.agent.state import Product
from src.data.base import BaseCatalogProvider
from src.data.dev_catalog import DevCatalogProvider

_DEFAULT_TOKEN = os.getenv("BEWAKOOF_CLIENT_DEVICE_TOKEN") or os.getenv("BEWAKOOF_API_TOKEN", "")
_IMAGE_BASE_URL = "https://images.bewakoof.com/t640/"

_KNOWN_COLORS = [
    "black", "blue", "white", "red", "green", "grey", "gray", "yellow", 
    "orange", "maroon", "beige", "brown", "purple", "pink", "navy", "olive", "lavender"
]


class BewakoofCatalogProvider(BaseCatalogProvider):
    """Direct live API integration with Bewakoof.com with design, fandom, bundle offer, and fit routing."""

    def __init__(
        self,
        api_token: Optional[str] = None,
        client_device_token: Optional[str] = None,
        fallback_provider: Optional[BaseCatalogProvider] = None
    ):
        self.api_token = api_token or os.getenv("BEWAKOOF_API_TOKEN", _DEFAULT_TOKEN)
        self.client_device_token = client_device_token or os.getenv("BEWAKOOF_CLIENT_DEVICE_TOKEN", self.api_token)
        self.fallback = fallback_provider or DevCatalogProvider()
        self.last_status_message: str = "Initialized"
        self.last_used_source: str = "bewakoof_live_api"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "api-token": self.api_token,
            "client-device-token": self.client_device_token,
            "x-client-device-token": self.client_device_token,
            "ab-id": "100",
            "x-ab-id": "100",
            "preferred-location": "IN",
            "referer": "https://www.bewakoof.com/",
            "origin": "https://www.bewakoof.com",
            "sec-ch-ua-platform": '"Android"',
            "sec-ch-ua-mobile": "?1",
            "user-agent": (
                "Mozilla/5.0 (Linux; Android 15; Pixel 9) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Mobile Safari/537.36"
            )
        }

    def _map_to_product(self, raw: Dict[str, Any], query_terms: List[str]) -> Optional[Product]:
        """Maps a Bewakoof raw JSON item to our unified Pydantic Product model with rich overlays."""
        try:
            prod_id = str(raw.get("id") or raw.get("legacy_id", "BWKF-UNKNOWN"))
            title = raw.get("name") or raw.get("custom_name", "Bewakoof Item")
            price = float(raw.get("price") or raw.get("sp") or 0.0)
            mrp = float(raw.get("mrp") or price)
            member_price = raw.get("member_price")

            # Attributes & Overlays
            attrs = raw.get("product_attributes", {})
            gender_val = str(raw.get("gender") or "Unisex").title()
            color_val = str(raw.get("color_name") or attrs.get("color") or "Multi").title()
            design_val = str(attrs.get("design") or ("Graphic Print" if "graphic" in title.lower() or "print" in title.lower() else "Solid")).title()
            fit_val = str(raw.get("fit") or attrs.get("fit") or "Regular Fit")
            fabric_val = str(raw.get("fabric") or attrs.get("fabric") or "Cotton")
            neck_val = str(raw.get("neck") or attrs.get("neck") or "Round Neck")
            sleeve_val = str(raw.get("sleeve") or attrs.get("sleeve") or "Half Sleeve")
            partner_val = attrs.get("merchandise_partner") or raw.get("cat_designer") or None
            bundle_offers = raw.get("offer_tags", [])

            # Ratings
            rating_val = float(raw.get("ratings_avg") or raw.get("average_rating") or (raw.get("ratings", {}).get("avg") if isinstance(raw.get("ratings"), dict) else 4.5))
            rating_count = int(raw.get("ratings_count") or (raw.get("ratings", {}).get("count") if isinstance(raw.get("ratings"), dict) else 50))

            # Stock & sizes
            in_stock = bool(raw.get("in_stock", 1)) and bool(raw.get("stock_status", True))
            available_sizes = [s.get("name") for s in raw.get("product_sizes", []) if s.get("stock_status", True)]

            # Images & URL
            display_img = raw.get("display_image") or (raw.get("images", [None])[0] if raw.get("images") else None)
            full_img_url = f"{_IMAGE_BASE_URL}{display_img}" if display_img else None
            slug = raw.get("url", "")
            product_url = f"https://www.bewakoof.com/p/{slug}" if slug else "https://www.bewakoof.com/"

            # Specifications Dictionary
            specs = {
                "gender": gender_val,
                "color": color_val,
                "design": design_val,
                "fit": fit_val,
                "fabric": fabric_val,
                "neck": neck_val,
                "sleeve": sleeve_val,
                "fandom_partner": partner_val,
                "bundle_offers": bundle_offers,
                "mrp_inr": mrp,
                "member_price_inr": member_price,
                "available_sizes": available_sizes,
                "discount_offer": raw.get("offer") or raw.get("product_discount"),
                "image_url": full_img_url
            }

            # Tags
            tags = [t.lower() for t in query_terms] + [
                "bewakoof",
                gender_val.lower(),
                color_val.lower(),
                design_val.lower(),
                fit_val.lower(),
                str(partner_val).lower() if partner_val else "",
                str(raw.get("category_info", {}).get("subclass") or "clothing").lower() if isinstance(raw.get("category_info"), dict) else "clothing",
            ]

            # Dynamic descriptive headline
            desc_parts = [gender_val, color_val, fit_val, design_val]
            if partner_val:
                desc_parts.append(f"({partner_val})")
            desc_parts.append(title)
            if bundle_offers:
                desc_parts.append(f"| Bundle: {', '.join(bundle_offers)}")
            
            description_str = " ".join(desc_parts)

            return Product(
                id=f"BWKF-{prod_id}",
                title=title,
                brand="Bewakoof®",
                merchant="Bewakoof",
                price=price,
                currency="INR",
                rating=rating_val,
                review_count=rating_count,
                in_stock=in_stock,
                stock_quantity=20 if in_stock else 0,
                category=raw.get("parent_category") or raw.get("type") or "Apparel",
                description=description_str,
                tags=[t for t in set(tags) if t],
                shipping_days=3,
                shipping_cost=0.0 if price > 499 else 50.0,
                source_url=product_url,
                specs=specs,
                discount_codes=["TRIBE10", "WELCOME100"] if member_price else []
            )
        except Exception as e:
            print(f"[Bewakoof Mapper] Error mapping item: {e}")
            return None

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
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        merchant: Optional[str] = None,
        limit: int = 6
    ) -> List[Product]:
        """Queries the live Bewakoof collections with multi-attribute filtering."""
        q_lower = query.lower()
        
        # 1. Resolve Target Gender
        target_gender = gender.lower() if gender else ("women" if "women" in q_lower else "men")

        # 2. Resolve Target Color
        target_color = color.lower() if color else None
        if not target_color:
            for c in _KNOWN_COLORS:
                if re.search(rf"\b{c}\b", q_lower):
                    target_color = c
                    break

        # 3. Resolve Collection Handle
        cat_lower = (category or query).lower()
        if "jogger" in cat_lower or "trackpant" in cat_lower:
            handle = f"{target_gender}-joggers"
        elif "hoodie" in cat_lower or "jacket" in cat_lower or "sweatshirt" in cat_lower:
            handle = f"{target_gender}-hoodies-sweatshirts"
        elif "jeans" in cat_lower or "denim" in cat_lower:
            handle = f"{target_gender}-jeans"
        else:
            handle = f"{target_gender}-clothing"

        url = (
            f"{os.getenv('BEWAKOOF_API_BASE_URL', '')}{os.getenv('BEWAKOOF_COLLECTION_ENDPOINT', '')}/{handle}"
            f"?qf=true&sort=popular&page=1&limit={max(limit*5, 50)}&fields=results"
            f"&product_fields=id,name,url,mrp,price,flip_image,display_image,in_stock,status,product_type,color_name,category_info,offer,gender,ratings_avg,ratings_count,member_price,fit,fabric,product_sizes,product_attributes,cat_designer,offer_tags"
        )

        try:
            print(f"📡 [Bewakoof Live API] handle='{handle}', gender='{target_gender}', color='{target_color}', design='{design}', fandom='{fandom}'...")
            resp = requests.get(url, headers=self._get_headers(), timeout=8)

            if resp.status_code != 200:
                self.last_status_message = f"⚠️ Bewakoof API returned HTTP {resp.status_code}. Fallback triggered."
                self.last_used_source = "fallback_dev_catalog"
                return self.fallback.search_products(query, category, gender, color, size, design, fandom, fit, sleeve, max_price, min_rating, merchant, limit)

            data = resp.json()
            raw_products = data.get("products", [])

            if not raw_products:
                self.last_status_message = "⚠️ Bewakoof API returned empty products array. Fallback triggered."
                self.last_used_source = "fallback_dev_catalog"
                return self.fallback.search_products(query, category, gender, color, size, design, fandom, fit, sleeve, max_price, min_rating, merchant, limit)

            query_terms = [t for t in q_lower.split() if t not in ["men", "women", "clothing", "buy", "find", "get", "tshirt", "t-shirt", "shirt"] and t not in _KNOWN_COLORS]
            
            matched_products: List[Product] = []

            for raw in raw_products:
                prod = self._map_to_product(raw, query_terms)
                if not prod:
                    continue

                # Filter by Category (e.g. Ensure T-Shirt doesn't return Jeans/Joggers)
                if category:
                    prod_subclass = str(raw.get("subclass") or raw.get("category_info", {}).get("subclass") or raw.get("type") or "").lower()
                    prod_title_lower = prod.title.lower()
                    if category == "t-shirt" and ("t-shirt" not in prod_subclass and "tshirt" not in prod_subclass and "t-shirt" not in prod_title_lower and "tshirt" not in prod_title_lower and "tee" not in prod_title_lower):
                        continue
                    elif category == "hoodie" and ("hoodie" not in prod_subclass and "sweatshirt" not in prod_subclass and "hoodie" not in prod_title_lower):
                        continue
                    elif category == "joggers" and ("jogger" not in prod_subclass and "trackpant" not in prod_subclass and "jogger" not in prod_title_lower):
                        continue
                    elif category == "jeans" and ("jean" not in prod_subclass and "denim" not in prod_subclass and "jean" not in prod_title_lower):
                        continue

                # Filter by Price
                if max_price is not None and prod.price > max_price:
                    continue

                # Filter by Rating
                if min_rating is not None and prod.rating < min_rating:
                    continue

                # Filter by Size
                if size:
                    available_sizes = [s.upper() for s in prod.specs.get("available_sizes", [])]
                    if size.upper() not in available_sizes:
                        continue

                # Filter by Color
                prod_color = str(prod.specs.get("color", "")).lower()
                if target_color and target_color not in prod_color and prod_color not in target_color:
                    continue

                # Filter by Design Pattern (Graphic Print, Typography, Solid, Washed)
                if design:
                    prod_design = str(prod.specs.get("design", "")).lower()
                    if design.lower() not in prod_design and prod_design not in design.lower():
                        continue

                # Filter by Fandom / Merchandise Partner (Marvel, DC, Harry Potter, Disney, Anime)
                if fandom:
                    prod_partner = str(prod.specs.get("fandom_partner", "")).lower()
                    prod_title = prod.title.lower()
                    fandom_kw = fandom.lower()
                    if fandom_kw not in prod_partner and fandom_kw not in prod_title:
                        continue

                # Filter by Fit (Oversized, Boyfriend, Regular)
                if fit:
                    prod_fit = str(prod.specs.get("fit", "")).lower()
                    if fit.lower() not in prod_fit:
                        continue

                # Filter by Sleeve (Half, Full, Sleeveless)
                if sleeve:
                    prod_sleeve = str(prod.specs.get("sleeve", "")).lower()
                    if sleeve.lower() not in prod_sleeve:
                        continue

                matched_products.append(prod)
                if len(matched_products) >= limit:
                    break

            # Fallback to general list if ultra-narrow combo had 0 hits
            if not matched_products and raw_products:
                for raw in raw_products[:limit]:
                    p = self._map_to_product(raw, query_terms)
                    if p:
                        matched_products.append(p)
                self.last_status_message = f"ℹ️ Exact combo not found in top batch. Showing trending {target_gender.title()} items."
            else:
                filters_desc = [target_gender.title()]
                if target_color: filters_desc.append(target_color.title())
                if design: filters_desc.append(design)
                if fandom: filters_desc.append(f"Theme: {fandom}")
                if fit: filters_desc.append(fit)
                if size: filters_desc.append(f"Size {size.upper()}")
                self.last_status_message = f"🟢 Retrieved {len(matched_products)} live products [{' | '.join(filters_desc)}] from Bewakoof.com!"

            self.last_used_source = "bewakoof_live_api"
            print(self.last_status_message)
            return matched_products[:limit]

        except Exception as e:
            self.last_status_message = f"⚠️ Bewakoof API request failed ({str(e)}). Fallback triggered."
            self.last_used_source = "fallback_dev_catalog"
            print(self.last_status_message)
            return self.fallback.search_products(query, category, gender, color, size, design, fandom, fit, sleeve, max_price, min_rating, merchant, limit)

    def get_product_details(self, product_id: str) -> Optional[Product]:
        return self.fallback.get_product_details(product_id)
