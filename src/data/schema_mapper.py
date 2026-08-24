"""
Bewakoof Collection Handle Registry & Universal Product Schema Mapper.

This module is designed to be:
  - Store-agnostic: The UniversalProductMapper uses a configurable FieldMap
    so adding a new store (Myntra, Flipkart, Amazon) only requires a new FieldMap config.
  - Robust: The HandleRegistry resolves any user intent combination to the most specific
    valid Bewakoof collection handle, avoiding overly broad or wrong results.
  - Scalable: Both the HandleRegistry and FieldMap are data-driven dicts, not code logic.
    New handles or field aliases can be added without modifying parsing logic.
"""

from typing import Any, Dict, List, Optional
from src.agent.state import Product

# ---------------------------------------------------------------------------
# 1. Bewakoof Handle Registry
#    Hierarchy: fandom > sleeve+category > category+fit > category > fallback
#
# Format: (gender, primary_key) -> handle
# primary_key priority order: fandom > sleeve > fit > category > "all"
# ---------------------------------------------------------------------------

# Fandom-specific handles (most specific — hit these first)
FANDOM_HANDLE_MAP: Dict[str, str] = {
    "marvel":       "marvel",
    "dc":           "batman-merchandise",
    "batman":       "batman-merchandise",
    "harry potter": "harry-potter-merchandise",
    "hogwarts":     "harry-potter-merchandise",
    "disney":       "disney-merchandise",
    "looney tunes": "looney-tunes-merchandise",
    "tom and jerry":"looney-tunes-merchandise",
    "scooby doo":   "scooby-doo-merchandise",
    "friends":      "friends-merchandise",
}

# Design-theme specific handles (second priority — flat design themes)
DESIGN_HANDLE_MAP: Dict[str, str] = {
    "typography":   "typography-t-shirts",
    "oversized":    "oversized-t-shirts",
    "printed":      "printed-t-shirts",
    "graphic print":"printed-t-shirts",
    "acid wash":    "acid-wash-t-shirts",
    "washed":       "acid-wash-t-shirts",
}

# Gender + Category + Sleeve matrix (third priority)
# Keys: (gender, category, sleeve_type) -> handle
# sleeve_type: "full", "half", None
CATEGORY_SLEEVE_HANDLE_MAP: Dict[tuple, str] = {
    ("men",   "t-shirt", "full"):    "men-full-sleeve-t-shirts",
    ("women", "t-shirt", "full"):    "women-full-sleeve-t-shirts",  # may 404 — falls back
    ("men",   "t-shirt", "half"):    "men-t-shirts",
    ("women", "t-shirt", "half"):    "women-t-shirts",
    ("men",   "t-shirt", None):      "men-t-shirts",
    ("women", "t-shirt", None):      "women-t-shirts",
    ("men",   "hoodie",  None):      "men-hoodies-sweatshirts",
    ("women", "hoodie",  None):      "women-hoodies-sweatshirts",
    ("men",   "sweatshirt", None):   "men-hoodies-sweatshirts",
    ("women", "sweatshirt", None):   "women-hoodies-sweatshirts",
    ("men",   "joggers", None):      "men-joggers",
    ("women", "joggers", None):      "women-joggers",
    ("men",   "sliders", None):      "men-sliders",
    ("men",   "sandals", None):      "men-sliders",
    ("men",   "footwear", None):     "men-footwear",
    ("women", "footwear", None):     "women-footwear",
    ("men",   "jeans",   None):      "jeans-for-men",
    ("women", "jeans",   None):      "jeans-for-women",
    ("men",   "shirt",   None):      "men-shirts",
    ("women", "shirt",   None):      "women-shirts",
}

# Gender-only fallback
GENDER_FALLBACK_MAP: Dict[str, str] = {
    "men":   "men-clothing",
    "women": "women-clothing",
    "unisex":"men-clothing",
    "all":   "men-clothing",
}

def resolve_handle(
    gender: str,
    category: Optional[str],
    sleeve: Optional[str],
    fandom: Optional[str],
    design: Optional[str],
    fit: Optional[str],
) -> tuple:
    """
    Returns (handle, needs_subclass_filter: bool).
    Logic:
      1. If fandom is set → fandom handle (most targeted).
      2. If design theme is set (typography, oversized, etc.) → design handle.
      3. Category + sleeve matrix.
      4. Gender fallback.
    """
    g = (gender or "men").lower()

    # 1. Fandom (e.g. "marvel", "dc", "disney")
    if fandom and fandom.lower() not in ("none", ""):
        fl = fandom.lower().replace(" / cartoons", "").strip()
        for key, handle in FANDOM_HANDLE_MAP.items():
            if fl in key or key in fl:
                return handle, False

    # 2. Design theme (e.g. "oversized", "typography", "acid wash")
    if design and design.lower() not in ("any", ""):
        dl = design.lower()
        # Map DesignEnum values to keys
        design_key_map = {
            "oversized fit": "oversized",
            "typography":    "typography",
            "graphic print": "printed",
            "all over print":"printed",
            "washed":        "acid wash",
        }
        mapped = design_key_map.get(dl, dl)
        if mapped in DESIGN_HANDLE_MAP:
            return DESIGN_HANDLE_MAP[mapped], False

    # Check if fit is oversized and category is t-shirt → oversized-t-shirts handle
    if fit and "oversized" in fit.lower() and category and "t-shirt" in (category or "").lower():
        return "oversized-t-shirts", False

    # 3. Category + sleeve matrix
    if category:
        cl = category.lower().replace("-", "").replace(" ", "")
        # Normalize category aliases
        alias_map = {
            "tshirt": "t-shirt", "tee": "t-shirt", "topwear": "t-shirt",
            "hoodie": "hoodie", "sweatshirt": "sweatshirt", "jacket": "hoodie",
            "joggers": "joggers", "trackpants": "joggers", "sweatpants": "joggers",
            "jeans": "jeans", "denim": "jeans",
            "shirt": "shirt",
            "slider": "sliders", "sandal": "sliders", "slipper": "sliders",
            "shoes": "footwear", "sneakers": "footwear",
        }
        normalized_cat = alias_map.get(cl, cl)
        
        # Normalize sleeve
        sleeve_key = None
        if sleeve:
            sl = sleeve.lower()
            if "full" in sl:
                sleeve_key = "full"
            elif "half" in sl or "short" in sl:
                sleeve_key = "half"

        # Try exact match first
        key = (g, normalized_cat, sleeve_key)
        if key in CATEGORY_SLEEVE_HANDLE_MAP:
            handle = CATEGORY_SLEEVE_HANDLE_MAP[key]
            needs_subclass = handle in ("men-clothing", "women-clothing")
            return handle, needs_subclass
        
        # Try without sleeve
        key_no_sleeve = (g, normalized_cat, None)
        if key_no_sleeve in CATEGORY_SLEEVE_HANDLE_MAP:
            handle = CATEGORY_SLEEVE_HANDLE_MAP[key_no_sleeve]
            needs_subclass = handle in ("men-clothing", "women-clothing")
            return handle, needs_subclass

    # 4. Gender fallback
    return GENDER_FALLBACK_MAP.get(g, "men-clothing"), True


# ---------------------------------------------------------------------------
# 2. Universal Product Schema Mapper (Store-Agnostic)
#
# FieldMap defines how any store's raw JSON keys map to our canonical Product fields.
# To support a new store (e.g. Myntra), create a new MYNTRA_FIELD_MAP and pass it in.
# ---------------------------------------------------------------------------

class FieldMap:
    """Configurable mapping from a store's raw JSON to our canonical Product schema."""
    def __init__(
        self,
        id_field: str = "id",
        title_field: str = "name",
        price_field: str = "price",
        mrp_field: str = "mrp",
        in_stock_field: str = "in_stock",
        gender_field: str = "gender",
        color_field: str = "color_name",
        image_field: str = "display_image",
        url_field: str = "url",
        rating_field: str = "ratings_avg",
        review_count_field: str = "ratings_count",
        product_sizes_field: str = "product_sizes",
        attributes_field: str = "product_attributes",
        designer_field: str = "cat_designer",
        offer_tags_field: str = "offer_tags",
        subclass_field: str = "subclass",
        member_price_field: str = "member_price",
        image_base_url: str = "https://images.bewakoof.com/t640/",
        store_base_url: str = "https://www.bewakoof.com/p/",
        currency: str = "INR",
        brand: str = "Bewakoof®",
        merchant: str = "Bewakoof",
    ):
        self.id_field = id_field
        self.title_field = title_field
        self.price_field = price_field
        self.mrp_field = mrp_field
        self.in_stock_field = in_stock_field
        self.gender_field = gender_field
        self.color_field = color_field
        self.image_field = image_field
        self.url_field = url_field
        self.rating_field = rating_field
        self.review_count_field = review_count_field
        self.product_sizes_field = product_sizes_field
        self.attributes_field = attributes_field
        self.designer_field = designer_field
        self.offer_tags_field = offer_tags_field
        self.subclass_field = subclass_field
        self.member_price_field = member_price_field
        self.image_base_url = image_base_url
        self.store_base_url = store_base_url
        self.currency = currency
        self.brand = brand
        self.merchant = merchant


# Default Bewakoof FieldMap (can be overridden per provider)
BEWAKOOF_FIELD_MAP = FieldMap()


class UniversalProductMapper:
    """
    Maps raw store JSON to our canonical Product Pydantic model.
    Configurable via FieldMap — add a new store by creating a new FieldMap config.
    """

    def __init__(self, field_map: FieldMap = BEWAKOOF_FIELD_MAP):
        self.fm = field_map

    def map(self, raw: Dict[str, Any], query_terms: List[str] = None) -> Optional[Product]:
        """Safely maps one raw JSON record to a canonical Product. Returns None on failure."""
        try:
            fm = self.fm
            attrs: Dict[str, Any] = raw.get(fm.attributes_field, {}) or {}
            cat_info = raw.get("category_info", {}) if isinstance(raw.get("category_info"), dict) else {}

            # Core identifiers
            prod_id = str(raw.get(fm.id_field) or raw.get("legacy_id", "UNKNOWN"))
            title = str(raw.get(fm.title_field) or "Unknown Product").strip()

            # Pricing
            price = float(raw.get(fm.price_field) or raw.get("sp") or 0.0)
            mrp = float(raw.get(fm.mrp_field) or price)
            member_price = raw.get(fm.member_price_field)

            # Attributes
            gender_val = str(raw.get(fm.gender_field) or attrs.get("gender") or "Unisex").strip().title()
            color_val = str(raw.get(fm.color_field) or attrs.get("color") or "Multi").strip().title()
            design_raw = attrs.get("design") or ""
            # Infer design from title if missing
            title_lower = title.lower()
            if not design_raw:
                if any(k in title_lower for k in ["graphic", "print", "printed"]):
                    design_raw = "Graphic Print"
                elif any(k in title_lower for k in ["typography", "text", "quote"]):
                    design_raw = "Typography"
                elif any(k in title_lower for k in ["solid", "plain", "basic"]):
                    design_raw = "Solid"
                elif "washed" in title_lower or "acid" in title_lower:
                    design_raw = "Washed"
                else:
                    design_raw = "Solid"

            fit_val = str(attrs.get("fit") or raw.get("fit") or "Regular Fit").strip()
            fabric_val = str(attrs.get("fabric") or raw.get("fabric") or "Cotton").strip()
            neck_val = str(attrs.get("neck") or raw.get("neck") or "Round Neck").strip()
            sleeve_val = str(attrs.get("sleeve") or raw.get("sleeve") or "Half Sleeve").strip()
            
            # Fandom/partner
            partner_val = (
                attrs.get("merchandise_partner") or
                raw.get(fm.designer_field) or
                cat_info.get("cat_designer") or
                None
            )
            if partner_val:
                partner_val = str(partner_val).strip()

            # Offers
            bundle_offers: List[str] = raw.get(fm.offer_tags_field) or []
            
            # Subclass (T-Shirt, Hoodie, Sliders, etc.)
            subclass_val = (
                raw.get(fm.subclass_field) or
                cat_info.get("subclass") or
                raw.get("type") or
                "Clothing"
            )

            # Rating
            rating_raw = raw.get(fm.rating_field) or raw.get("average_rating")
            if isinstance(raw.get("ratings"), dict):
                rating_raw = rating_raw or raw["ratings"].get("avg")
            rating_val = float(rating_raw or 4.5)
            rating_count = int(raw.get(fm.review_count_field) or 50)

            # Stock & sizes
            in_stock = bool(raw.get(fm.in_stock_field, True))
            raw_sizes = raw.get(fm.product_sizes_field, []) or []
            available_sizes = [
                str(s.get("name", "")) for s in raw_sizes
                if isinstance(s, dict) and s.get("stock_status", True)
            ]

            # Image & URL
            display_img = raw.get(fm.image_field)
            full_img_url = f"{fm.image_base_url}{display_img}" if display_img else None
            slug = raw.get(fm.url_field, "")
            product_url = f"{fm.store_base_url}{slug}" if slug else f"https://{fm.merchant.lower()}.com/"

            # Build rich description
            desc_parts = [gender_val, color_val, fit_val, design_raw]
            if partner_val:
                desc_parts.append(f"({partner_val})")
            desc_parts.append(title)
            if bundle_offers:
                desc_parts.append(f"| Bundle: {', '.join(bundle_offers)}")
            description_str = " ".join(desc_parts)

            # Tags
            tags = list({
                fm.merchant.lower(), gender_val.lower(), color_val.lower(),
                design_raw.lower(), fit_val.lower(), subclass_val.lower(),
                *(partner_val.lower().split() if partner_val else []),
                *((query_terms or []))
            })

            # Specs dict — single source of truth for all attributes
            specs = {
                "gender":          gender_val,
                "color":           color_val,
                "design":          design_raw,
                "fit":             fit_val,
                "fabric":          fabric_val,
                "neck":            neck_val,
                "sleeve":          sleeve_val,
                "subclass":        subclass_val,
                "fandom_partner":  partner_val,
                "bundle_offers":   bundle_offers,
                "mrp_inr":         mrp,
                "member_price_inr":member_price,
                "available_sizes": available_sizes,
                "image_url":       full_img_url,
                "discount_offer":  raw.get("offer") or raw.get("product_discount"),
            }

            return Product(
                id=f"{fm.merchant.upper()[:4]}-{prod_id}",
                title=title,
                brand=fm.brand,
                merchant=fm.merchant,
                price=price,
                currency=fm.currency,
                rating=min(5.0, rating_val),
                review_count=rating_count,
                in_stock=in_stock,
                stock_quantity=20 if in_stock else 0,
                category=subclass_val,
                description=description_str,
                tags=[t for t in tags if t],
                shipping_days=3,
                shipping_cost=0.0 if price > 499 else 50.0,
                source_url=product_url,
                specs=specs,
                discount_codes=["TRIBE10", "WELCOME100"] if member_price else []
            )

        except Exception as e:
            print(f"[UniversalMapper] Error mapping product: {e}")
            return None
