from enum import Enum
from typing import List, Dict, Any
from pydantic import BaseModel, Field

class OfferType(str, Enum):
    BULK_FIXED_PRICE = "bulk_fixed_price"
    SPEND_THRESHOLD_PERCENT = "spend_threshold_percent"

class MerchantOffer(BaseModel):
    id: str
    title: str
    description: str
    offer_type: OfferType
    
    min_quantity: int = 0
    min_spend: float = 0.0
    applicable_categories: List[str] = Field(default_factory=list)
    
    target_price: float = 0.0
    discount_percent: float = 0.0

class OfferEvaluation(BaseModel):
    offer: MerchantOffer
    is_unlocked: bool
    amount_away: float = 0.0
    quantity_away: int = 0
    estimated_savings: float = 0.0
    upsell_message: str = ""
    success_message: str = ""

# ==============================================================================
# Rasor E-Commerce Constants & Offers
# This file serves as a centralized dictionary for all campaign constants,
# merchant configurations, and active offers.
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. Active Merchant Offers
# ------------------------------------------------------------------------------
# These offers are dynamically parsed by the OfferEngine inside the Cart module.
# Categories match product titles using a case-insensitive sub-string search.

ACTIVE_OFFERS: List[MerchantOffer] = [
    # Bulk / Bundle Deals
    MerchantOffer(
        id="OFFER_POLO_3_FOR_1199",
        title="Polo Pack Deal",
        description="Buy 3 Polo T-Shirts for just ₹1199!",
        offer_type=OfferType.BULK_FIXED_PRICE,
        min_quantity=3,
        applicable_categories=["Polo"],
        target_price=1199.0
    ),
    MerchantOffer(
        id="OFFER_HOODIE_2_FOR_1599",
        title="Winter Vibe Bundle",
        description="Buy 2 Hoodies or Sweatshirts for just ₹1599!",
        offer_type=OfferType.BULK_FIXED_PRICE,
        min_quantity=2,
        applicable_categories=["Hoodie", "Sweatshirt", "Jacket"],
        target_price=1599.0
    ),
    MerchantOffer(
        id="OFFER_SNEAKERS_2_FOR_2499",
        title="Sneakerhead Special",
        description="Grab any 2 pairs of Sneakers for ₹2499!",
        offer_type=OfferType.BULK_FIXED_PRICE,
        min_quantity=2,
        applicable_categories=["Sneaker", "Shoe", "High-Top"],
        target_price=2499.0
    ),
    
    # Spend Threshold Deals
    MerchantOffer(
        id="OFFER_SPEND_1500_10PCT",
        title="Cart Saver 10% Off",
        description="Spend over ₹1500 to get 10% off your entire cart!",
        offer_type=OfferType.SPEND_THRESHOLD_PERCENT,
        min_spend=1500.0,
        discount_percent=10.0
    ),
    MerchantOffer(
        id="OFFER_SPEND_3000_20PCT",
        title="Big Spender 20% Off",
        description="Spend over ₹3000 to get 20% off your entire cart!",
        offer_type=OfferType.SPEND_THRESHOLD_PERCENT,
        min_spend=3000.0,
        discount_percent=20.0
    ),
    MerchantOffer(
        id="OFFER_SPEND_5000_FLAT_1000",
        title="Super Saver Flat Off",
        description="Spend over ₹5000 and get a flat ₹1000 discount!",
        offer_type=OfferType.SPEND_THRESHOLD_PERCENT, # Assuming percent for now, could add FLAT_DISCOUNT type
        min_spend=5000.0,
        discount_percent=20.0 # 1000 is 20% of 5000. We can add a FLAT discount type later.
    )
]

# ------------------------------------------------------------------------------
# 2. Category Taxonomies & Weights
# ------------------------------------------------------------------------------
# Can be used later for Vibe mappings or Multi-item budget allocations

CATEGORY_WEIGHTS: Dict[str, float] = {
    "T-shirt": 0.5,
    "Polo": 0.6,
    "Shirt": 0.8,
    "Hoodie": 1.2,
    "Jacket": 1.5,
    "Jeans": 1.2,
    "Joggers": 1.0,
    "Sneakers": 2.0,
    "Accessories": 0.3
}

# ------------------------------------------------------------------------------
# 3. Complementary Mapping
# ------------------------------------------------------------------------------
# Defines what categories pair well with others for cross-selling recommendations.
# Used by the RecommenderEngine to bridge Spend Threshold gaps.

COMPLEMENTARY_MAP: Dict[str, List[str]] = {
    "T-shirt": ["Jeans", "Joggers", "Accessories", "Sneakers"],
    "Polo": ["Jeans", "Joggers", "Accessories", "Sneakers"],
    "Shirt": ["Jeans", "Accessories", "Sneakers"],
    "Hoodie": ["Joggers", "Jeans", "Sneakers"],
    "Jacket": ["Jeans", "T-shirt", "Sneakers"],
    "Jeans": ["T-shirt", "Polo", "Shirt", "Hoodie", "Sneakers"],
    "Joggers": ["T-shirt", "Hoodie", "Sneakers"],
    "Sneakers": ["Jeans", "Joggers", "Accessories"],
    "Accessories": ["T-shirt", "Shirt", "Jeans"]
}

# ------------------------------------------------------------------------------
# 4. Vibe Mappings
# ------------------------------------------------------------------------------
# Translates abstract aesthetic styles into concrete search metadata

AESTHETIC_VIBE_MAP: Dict[str, Dict[str, Any]] = {
    "streetwear": {
        "fit": ["Oversized Fit", "Baggy Fit", "Super Baggy Fit"],
        "design": ["Graphic Print", "Typography", "Washed"],
        "brands": ["Bewakoof", "Urban", "Street"]
    },
    "minimalist": {
        "fit": ["Regular Fit", "Slim Fit"],
        "design": ["Solid", "Basic"],
        "colors": ["White", "Black", "Grey", "Navy", "Beige"]
    },
    "gym": {
        "fit": ["Slim Fit", "Regular Fit"],
        "fabric": ["Polyester", "Blend", "Nylon"],
        "category": ["T-shirt", "Joggers", "Shorts", "Vest"]
    }
}
