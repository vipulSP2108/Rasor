"""Domain models, canonical enums, and state definitions for Rasor Agentic Commerce."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ------------------------------------------------------------------------------
# 1. Canonical Commerce Enums (Standardized Taxonomy)
# ------------------------------------------------------------------------------

class GenderEnum(str, Enum):
    MEN = "men"
    WOMEN = "women"
    UNISEX = "unisex"
    ALL = "all"


class OccasionEnum(str, Enum):
    PARTY = "Party"
    GYM = "Gym"
    CASUAL = "Casual"
    OFFICE = "Office"
    ANY = "Any"


class CategoryEnum(str, Enum):
    TSHIRT = "t-shirt"
    HOODIE = "hoodie"
    SWEATSHIRT = "sweatshirt"
    JOGGERS = "joggers"
    JEANS = "jeans"
    SHIRT = "shirt"
    VEST = "vest"
    SLIDERS = "sliders"
    FOOTWEAR = "footwear"
    ELECTRONICS = "electronics"
    GENERAL = "general"


class ColorEnum(str, Enum):
    BLACK = "Black"
    BLUE = "Blue"
    WHITE = "White"
    RED = "Red"
    GREEN = "Green"
    ORANGE = "Orange"
    GREY = "Grey"
    YELLOW = "Yellow"
    MAROON = "Maroon"
    BEIGE = "Beige"
    BROWN = "Brown"
    NAVY = "Navy"
    CYAN = "Cyan"
    MULTI = "Multi"
    ANY = "Any"


class DesignEnum(str, Enum):
    SOLID = "Solid"                       # Plain, basic, single color
    GRAPHIC_PRINT = "Graphic Print"       # Artwork, prints, anime
    TYPOGRAPHY = "Typography"             # Text, quotes, slogans
    ALL_OVER_PRINT = "All Over Print"     # Patterned across entire garment
    WASHED = "Washed"                     # Acid wash, vintage wash
    CHECKED = "Checked"                   # Plaid, checks
    ANY = "Any"


class FitEnum(str, Enum):
    OVERSIZED = "Oversized Fit"
    REGULAR = "Regular Fit"
    BOYFRIEND = "Boyfriend Fit"
    BAGGY = "Baggy Fit"
    SUPER_BAGGY = "Super Baggy Fit"
    SLIM = "Slim Fit"
    RELAXED = "Relaxed Fit"
    LOOSE = "Loose Fit"
    ANY = "Any"


class SleeveEnum(str, Enum):
    FULL = "Full Sleeve"
    HALF = "Half Sleeve"
    SLEEVELESS = "Sleeveless"
    SHORT = "Short Sleeve"
    ANY = "Any"


class FabricEnum(str, Enum):
    COTTON = "Cotton"
    POLYESTER = "Polyester"
    BLEND = "Blend"
    FLEECE = "Fleece"
    LINEN = "Linen"
    NYLON = "Nylon"
    ANY = "Any"


class NeckEnum(str, Enum):
    ROUND = "Round Neck"
    V_NECK = "V-Neck"
    POLO = "Polo"
    COLLAR = "Collar"
    HOOD = "Hood"
    CREW = "Crew Neck"
    ANY = "Any"


class FandomEnum(str, Enum):
    MARVEL = "Marvel"
    DC = "DC"
    DISNEY = "Disney"
    HARRY_POTTER = "Harry Potter"
    ANIME = "Anime / Cartoons"
    NONE = "None"


# ------------------------------------------------------------------------------
# 2. Canonical Parsed Query Schema
# ------------------------------------------------------------------------------

class CanonicalShoppingQuery(BaseModel):
    """Structured, canonical query normalized by LLM from user free-form speech."""
    original_prompt: str
    cleaned_keywords: str = Field(..., description="Core product search keywords without noise")
    gender: GenderEnum = Field(default=GenderEnum.MEN, description="Target gender")
    category: CategoryEnum = Field(default=CategoryEnum.TSHIRT, description="Target category")
    color: ColorEnum = Field(default=ColorEnum.ANY, description="Target color")
    design: DesignEnum = Field(default=DesignEnum.ANY, description="Specific design theme")
    fit: FitEnum = Field(default=FitEnum.ANY, description="Desired fit")
    sleeve: SleeveEnum = Field(default=SleeveEnum.ANY, description="Sleeve length")
    fabric: FabricEnum = Field(default=FabricEnum.ANY, description="Material fabric")
    neck: NeckEnum = Field(default=NeckEnum.ANY, description="Neckline style")
    occasion: OccasionEnum = Field(default=OccasionEnum.ANY, description="Occasion or vibe for the outfit")
    fandom: FandomEnum = Field(default=FandomEnum.NONE, description="Specific IP or fandom")
    specific_visual_intent: Optional[str] = Field(default=None, description="Verbose description of a specific graphic or visual element (e.g. 'arms crossed Wakanda salute')")
    fast_shipping_requested: bool = Field(default=False, description="True if user wants fast delivery")
    size: Optional[str] = Field(default=None, description="Explicit requested size (e.g. 'L', 'M', 'XL')")
    quantity: int = Field(default=1, description="Quantity of items requested")
    max_price: Optional[float] = Field(default=None, description="Hard budget cap extracted from text")
    min_rating: Optional[float] = Field(default=None, description="Minimum review rating requested")
    negative_keywords: List[str] = Field(default_factory=list, description="Keywords explicitly excluded by user")

    @property
    def has_visual_intent(self) -> bool:
        if not self.specific_visual_intent:
            return False
        val = str(self.specific_visual_intent).lower().strip()
        return val not in ["", "none", "null", "n/a", "not specified", "false"]
class MultiShoppingQuery(BaseModel):
    """A collection of queries representing a multi-item outfit or bundle request."""
    original_prompt: str
    items_to_buy: List[CanonicalShoppingQuery] = Field(default_factory=list, description="Target items to purchase")
    owned_items: List[CanonicalShoppingQuery] = Field(default_factory=list, description="Items the user already owns to match against")

# ------------------------------------------------------------------------------
# 3. Product Model & Relevance Assessment
# ------------------------------------------------------------------------------

class Product(BaseModel):
    id: str = Field(..., description="Unique product identifier or SKU")
    title: str = Field(..., description="Full title of the product")
    brand: str = Field(default="Generic", description="Brand name")
    merchant: str = Field(..., description="Merchant / Store name")
    price: float = Field(..., ge=0.0, description="Unit price")
    currency: str = Field(default="USD", description="Currency code")
    rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Customer rating out of 5.0")
    review_count: int = Field(default=0, ge=0, description="Total review count")
    in_stock: bool = Field(default=True, description="Inventory availability")
    stock_quantity: int = Field(default=10, ge=0, description="Available stock count")
    category: str = Field(default="General", description="Category name")
    description: str = Field(default="", description="Detailed product description")
    tags: List[str] = Field(default_factory=list, description="Search keywords & tags")
    shipping_days: int = Field(default=3, ge=0, description="Estimated delivery days")
    shipping_cost: float = Field(default=0.0, ge=0.0, description="Shipping cost")
    source_url: Optional[str] = Field(default=None, description="Direct URL if scraped/API")
    image_url: Optional[str] = Field(default=None, description="Primary product image CDN URL")
    images: List[str] = Field(default_factory=list, description="List of product image URLs")
    specs: Dict[str, Any] = Field(default_factory=dict, description="Key-value specifications")
    discount_codes: List[str] = Field(default_factory=list, description="Applicable discount codes")
    enriched: bool = Field(default=False, description="Whether single-product deep fetch has been done")
    rich_description: Optional[str] = Field(default=None, description="Detailed product description from single endpoint")


class ProductRelevanceEvaluation(BaseModel):
    """LLM assessment of whether a candidate product strictly satisfies the user's intent."""
    product_id: str
    product_title: str
    is_relevant: bool = Field(..., description="True if product satisfies user intent, False if false positive")
    match_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score from 0.0 to 1.0")
    reason: str = Field(..., description="Brief explanation for accept or reject")


class FeatureComparisonRow(BaseModel):
    feature_name: str = Field(..., description="E.g., Price, Rating, Materials, Shipping Speed, Style Vibe")
    product_values: Dict[str, str] = Field(..., description="Mapping from product title to feature value")

class ProductProsCons(BaseModel):
    product_title: str = Field(..., description="Exact product title")
    pros: List[str] = Field(default_factory=list, description="List of pros")
    cons: List[str] = Field(default_factory=list, description="List of cons")

class ProductComparison(BaseModel):
    quick_summary: str = Field(..., description="2 sentences summarizing the trade-offs")
    feature_matrix: List[FeatureComparisonRow] = Field(..., description="List of comparative features")
    pros_and_cons: List[ProductProsCons] = Field(..., description="Pros and cons per product")
    stylist_recommendation: Dict[str, str] = Field(..., description="Category (e.g. 'Best for Value', 'Best for Premium Quality') mapped to the recommendation text")


# ------------------------------------------------------------------------------
# 4. Cart & Line Items
# ------------------------------------------------------------------------------

class CartItem(BaseModel):
    product_id: str
    title: str
    merchant: str
    unit_price: float
    quantity: int = Field(default=1, ge=1)
    applied_discount: float = Field(default=0.0, ge=0.0)

    @property
    def total_price(self) -> float:
        return max(0.0, (self.unit_price * self.quantity) - self.applied_discount)


class CartStatus(str, Enum):
    ACTIVE = "active"
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    LOCKED = "locked"
    CHECKED_OUT = "checked_out"
    PAID = "paid"
    FAILED = "failed"

class MandateStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"

class Mandate(BaseModel):
    mandate_id: str
    cart_id: str
    max_amount: float
    currency: str = "USD"
    status: MandateStatus = MandateStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    saved_token_id: Optional[str] = None


class Cart(BaseModel):
    cart_id: str
    merchant: str
    items: List[CartItem] = Field(default_factory=list)
    subtotal: float = 0.0
    tax: float = 0.0
    shipping_cost: float = 0.0
    total_discount: float = 0.0
    final_total: float = 0.0
    currency: str = "USD"
    status: CartStatus = CartStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def recalculate(self, tax_rate: float = 0.08, free_shipping_threshold: float = 50.0, default_shipping: float = 5.0) -> None:
        self.subtotal = sum(item.total_price for item in self.items)
        self.tax = round(self.subtotal * tax_rate, 2)
        if self.subtotal >= free_shipping_threshold or len(self.items) == 0:
            self.shipping_cost = 0.0
        else:
            self.shipping_cost = default_shipping
        self.final_total = round(self.subtotal + self.tax + self.shipping_cost, 2)


# ------------------------------------------------------------------------------
# 5. Guardrails & Payments
# ------------------------------------------------------------------------------

class GuardrailViolation(str, Enum):
    NONE = "none"
    BUDGET_EXCEEDED = "budget_exceeded"
    UNAUTHORIZED_MERCHANT = "unauthorized_merchant"
    HITL_REQUIRED = "hitl_required"
    PRICE_MISMATCH = "price_mismatch"


class GuardrailResult(BaseModel):
    passed: bool
    violation: GuardrailViolation = GuardrailViolation.NONE
    message: str = "Validation passed"
    requires_human_approval: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class SharedPaymentToken(BaseModel):
    token_id: str
    authorized_amount: float
    currency: str = "USD"
    merchant: str
    expires_in_seconds: int = 600
    status: str = "active"


class OrderConfirmation(BaseModel):
    order_id: str
    cart_id: str
    transaction_id: str
    merchant: str
    items: List[CartItem]
    total_amount: float
    currency: str
    estimated_delivery: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ThoughtStep(BaseModel):
    step_index: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
