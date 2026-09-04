"""
Data Contracts for Query Intent to Catalog Schema & Semantic Mapping.

Provides strict, validated Pydantic models defining:
  1. CatalogMappingInput: The formal input contract accepted by the mapping engine.
  2. ResolvedCatalogIntent: The formal output contract produced for downstream consumers.
  3. Store-specific query specification models (BewakoofQuerySpec, ShopifyQuerySpec, UniversalFilterSpec).
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StorePlatformEnum(str, Enum):
    BEWAKOOF = "bewakoof"
    SHOPIFY = "shopify"
    DEV_CATALOG = "dev_catalog"
    UNIVERSAL = "universal"


# ------------------------------------------------------------------------------
# 1. Input Contract: CatalogMappingInput
# ------------------------------------------------------------------------------

class CatalogMappingInput(BaseModel):
    """
    Standardized, strongly-typed input contract for the mapping subsystem.
    
    Accepts raw user prompt strings, pre-parsed entities, and domain constraints.
    Can be constructed directly or via helper classmethods (.from_canonical_query, .from_raw_query).
    """
    query_text: str = Field(..., description="Raw or pre-processed search query text from user")
    category: Optional[str] = Field(default=None, description="Explicit or extracted category (e.g., 't-shirt', 'hoodie', 'uppers')")
    gender: Optional[str] = Field(default=None, description="Target gender ('men', 'women', 'unisex', 'all')")
    color: Optional[str] = Field(default=None, description="Target color (e.g., 'black', 'navy', 'olive')")
    size: Optional[str] = Field(default=None, description="Target size or compound size (e.g., 'L', 'XL', 'L/XL', '32')")
    design: Optional[str] = Field(default=None, description="Design theme (e.g., 'solid', 'graphic print', 'typography', 'washed')")
    fit: Optional[str] = Field(default=None, description="Fit style (e.g., 'oversized', 'regular', 'baggy', 'slim')")
    sleeve: Optional[str] = Field(default=None, description="Sleeve length (e.g., 'full', 'half', 'sleeveless')")
    fabric: Optional[str] = Field(default=None, description="Material fabric (e.g., 'cotton', 'polyester', 'blend')")
    neck: Optional[str] = Field(default=None, description="Neckline style (e.g., 'round neck', 'v-neck', 'polo', 'hood')")
    occasion: Optional[str] = Field(default=None, description="Occasion or vibe (e.g., 'casual', 'gym', 'party', 'office')")
    fandom: Optional[str] = Field(default=None, description="Target IP or franchise (e.g., 'marvel', 'dc', 'anime', 'disney')")
    vibe: Optional[str] = Field(default=None, description="Aesthetic vibe (e.g., 'streetwear', 'minimalist', 'y2k', 'retro grunge')")
    max_price: Optional[float] = Field(default=None, description="Maximum price cap in local currency")
    min_rating: Optional[float] = Field(default=None, description="Minimum product rating (0.0 to 5.0)")
    negative_keywords: List[str] = Field(default_factory=list, description="Terms explicitly negated/excluded by the user")
    target_store: StorePlatformEnum = Field(default=StorePlatformEnum.UNIVERSAL, description="Target merchant or platform")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary extension payload (e.g., user profile, session state)")

    @classmethod
    def from_raw_query(
        cls,
        prompt: str,
        budget: Optional[float] = None,
        target_store: StorePlatformEnum = StorePlatformEnum.UNIVERSAL,
        **kwargs
    ) -> "CatalogMappingInput":
        """Convenience builder to map raw text input."""
        return cls(
            query_text=prompt,
            max_price=budget,
            target_store=target_store,
            **kwargs
        )

    @classmethod
    def from_canonical_query(
        cls,
        query: Any,
        target_store: StorePlatformEnum = StorePlatformEnum.UNIVERSAL,
        budget_override: Optional[float] = None
    ) -> "CatalogMappingInput":
        """
        Builds a CatalogMappingInput from a CanonicalShoppingQuery instance
        produced by the agent brain.
        """
        def get_enum_val(obj, default=None):
            if obj is None:
                return default
            return getattr(obj, "value", str(obj))

        gender_val = get_enum_val(getattr(query, "gender", None), "men")
        category_val = get_enum_val(getattr(query, "category", None), "t-shirt")
        color_val = get_enum_val(getattr(query, "color", None), None)
        design_val = get_enum_val(getattr(query, "design", None), None)
        fit_val = get_enum_val(getattr(query, "fit", None), None)
        sleeve_val = get_enum_val(getattr(query, "sleeve", None), None)
        fabric_val = get_enum_val(getattr(query, "fabric", None), None)
        neck_val = get_enum_val(getattr(query, "neck", None), None)
        occasion_val = get_enum_val(getattr(query, "occasion", None), None)
        fandom_val = get_enum_val(getattr(query, "fandom", None), None)

        def sanitize(v):
            if not v or str(v).lower() in ("any", "none", "null", "all"):
                return None
            return v

        return cls(
            query_text=getattr(query, "cleaned_keywords", "") or getattr(query, "original_prompt", ""),
            category=sanitize(category_val),
            gender=sanitize(gender_val) or "men",
            color=sanitize(color_val),
            size=getattr(query, "size", None),
            design=sanitize(design_val),
            fit=sanitize(fit_val),
            sleeve=sanitize(sleeve_val),
            fabric=sanitize(fabric_val),
            neck=sanitize(neck_val),
            occasion=sanitize(occasion_val),
            fandom=sanitize(fandom_val),
            max_price=budget_override if budget_override is not None else getattr(query, "max_price", None),
            min_rating=getattr(query, "min_rating", None),
            negative_keywords=getattr(query, "negative_keywords", []) or [],
            target_store=target_store,
        )


# ------------------------------------------------------------------------------
# 2. Output Sub-Specifications
# ------------------------------------------------------------------------------

class BewakoofQuerySpec(BaseModel):
    """Target query payload for Bewakoof endpoints."""
    handle: str = Field(..., description="Collection URL slug handle (e.g. 'men-t-shirts', 'marvel', 'oversized-t-shirts')")
    needs_subclass_filter: bool = Field(default=False, description="True if handle is broad (like 'men-clothing') requiring client-side subclass filtering")
    target_subclass: Optional[str] = Field(default=None, description="Expected product subclass (e.g. 'T-Shirt', 'Hoodie')")
    api_relative_path: str = Field(..., description="API relative path formatted for Bewakoof client")
    fandom_detected: Optional[str] = Field(default=None, description="Detected fandom if matched to specific brand partner")


class ShopifyQuerySpec(BaseModel):
    """Target query payload for Shopify GraphQL Storefront API."""
    products_query_syntax: str = Field(..., description="Query string for Storefront products(query: ...)")
    search_query_syntax: str = Field(..., description="Query string for Storefront search(query: ...)")
    product_type: Optional[str] = Field(default=None, description="Target Shopify product_type filter")
    filter_tags: List[str] = Field(default_factory=list, description="Tags required for strict narrowing")
    keywords_used: List[str] = Field(default_factory=list, description="Filtered keyword tokens used in the query")


class UniversalFilterSpec(BaseModel):
    """In-memory or SQL predicate specification for mock/local catalogs."""
    category: Optional[str] = None
    macro_category: Optional[str] = None
    gender: Optional[str] = None
    color: Optional[str] = None
    color_family: Optional[str] = None
    sizes: List[str] = Field(default_factory=list)
    fit: Optional[str] = None
    design: Optional[str] = None
    fandom: Optional[str] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    tags_required: List[str] = Field(default_factory=list)


class SearchTierConfig(BaseModel):
    """Definition for a progressive relaxation tier during search execution."""
    tier: int = Field(..., description="Tier index (1 is strictest, 5 is broad fallback)")
    name: str = Field(..., description="Tier human-readable label")
    description: str = Field(..., description="Explanation of what constraints are active in this tier")
    active_predicates: Dict[str, Any] = Field(default_factory=dict, description="Constraints active in this step")


# ------------------------------------------------------------------------------
# 3. Output Contract: ResolvedCatalogIntent
# ------------------------------------------------------------------------------

class ResolvedCatalogIntent(BaseModel):
    """
    Standardized, strongly-typed output contract produced by the mapping subsystem.
    
    Contains:
      - Canonicalized garment categories, macro-category, and synonyms.
      - Normalized physical attributes (colors, sizes, fits, sleeves).
      - Store-specific compiled query specifications (Bewakoof, Shopify, Universal).
      - Progressive search relaxation tiers.
      - Audit trail of mapping decisions and confidence scores.
    """
    original_query: str = Field(..., description="Original query string provided as input")
    canonical_category: str = Field(..., description="Normalized micro-category (e.g. 't-shirt', 'hoodie', 'joggers')")
    macro_category: str = Field(..., description="Macro garment classification ('upper', 'lower', 'outerwear', 'footwear', 'general')")
    category_synonyms: List[str] = Field(default_factory=list, description="List of recognized synonyms and search aliases")
    
    normalized_gender: str = Field(default="men", description="Normalized target gender ('men', 'women', 'unisex')")
    normalized_color: Optional[str] = Field(default=None, description="Recognized specific color (e.g. 'Navy Blue')")
    color_family: Optional[str] = Field(default=None, description="Broader color family (e.g. 'Blue' for 'Navy Blue')")
    hex_anchor: Optional[str] = Field(default=None, description="Hex color code anchor for visual consistency")
    
    normalized_sizes: List[str] = Field(default_factory=list, description="Parsed uppercase size tokens (e.g. ['M', 'L'])")
    normalized_fit: Optional[str] = Field(default=None, description="Standardized fit (e.g. 'Oversized Fit')")
    normalized_design: Optional[str] = Field(default=None, description="Standardized design theme (e.g. 'Graphic Print')")
    normalized_sleeve: Optional[str] = Field(default=None, description="Standardized sleeve (e.g. 'Half Sleeve')")
    normalized_fabric: Optional[str] = Field(default=None, description="Standardized fabric (e.g. 'Cotton')")
    normalized_neck: Optional[str] = Field(default=None, description="Standardized neckline (e.g. 'Round Neck')")
    normalized_fandom: Optional[str] = Field(default=None, description="Standardized franchise or IP partner (e.g. 'Marvel')")
    
    vibe_applied: Optional[str] = Field(default=None, description="Aesthetic vibe detected/applied (e.g. 'streetwear')")
    inferred_vibe_tags: List[str] = Field(default_factory=list, description="Tags inferred from aesthetic vibe")
    
    max_price: Optional[float] = Field(default=None, description="Effective budget cap applied")
    min_rating: Optional[float] = Field(default=None, description="Effective rating threshold applied")
    
    # Store-specific compilation targets
    bewakoof: BewakoofQuerySpec = Field(..., description="Bewakoof-specific query specification")
    shopify: ShopifyQuerySpec = Field(..., description="Shopify Storefront API query specification")
    universal: UniversalFilterSpec = Field(..., description="Universal in-memory filter specification")
    
    # Execution Strategy
    search_tiers: List[SearchTierConfig] = Field(default_factory=list, description="Progressive search execution tiers")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score of the intent mapping")
    mapping_notes: List[str] = Field(default_factory=list, description="Audit trail of conversions, fallbacks, and expansions applied")
