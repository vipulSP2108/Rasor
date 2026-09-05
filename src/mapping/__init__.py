"""
Decoupled Query Intent to Catalog Schema & Semantic Mapping Subsystem.

Public API:
  - Contracts: CatalogMappingInput, ResolvedCatalogIntent, StorePlatformEnum, etc.
  - Core Functions: map_intent_to_catalog, preprocess_prompt, get_semantic_affinity_tier,
                    get_product_color, resolve_handle, parse_requested_sizes
  - Taxonomies: SPELL_CORRECTIONS, SYNONYM_MAP, FANDOM_KNOWLEDGE_GRAPH,
                CHARACTER_ENTITY_MAP, ENTITY_FRANCHISE_MAP, VIBE_MAP,
                CATEGORY_TAXONOMY, COLOR_TAXONOMY, FIT_CANONICAL_MAP,
                SLEEVE_CANONICAL_MAP, CATEGORY_SHOPIFY_TYPE_ALIASES,
                PLUS_SIZE_KEYWORDS, etc.
  - NativeLLMHook: Built-in LLM endpoint accessor for Gemini & Grok/Groq.

See README.md "Changelog" for the catalog audit that drove the additions
below (FIT_CANONICAL_MAP, SLEEVE_CANONICAL_MAP, CATEGORY_SHOPIFY_TYPE_ALIASES,
PLUS_SIZE_KEYWORDS are new; every other table was expanded in place).
"""

from src.mapping.contracts import (
    CatalogMappingInput,
    ResolvedCatalogIntent,
    StorePlatformEnum,
    BewakoofQuerySpec,
    ShopifyQuerySpec,
    UniversalFilterSpec,
    SearchTierConfig,
)
from src.mapping.taxonomy import (
    SPELL_CORRECTIONS,
    SYNONYM_MAP,
    FANDOM_KNOWLEDGE_GRAPH,
    CHARACTER_ENTITY_MAP,
    ENTITY_FRANCHISE_MAP,
    VIBE_MAP,
    CATEGORY_TAXONOMY,
    CATEGORY_SHOPIFY_TYPE_ALIASES,
    MACRO_CATEGORY_EXPANSIONS,
    COLOR_TAXONOMY,
    FANDOM_HANDLE_MAP,
    DESIGN_HANDLE_MAP,
    CATEGORY_SLEEVE_HANDLE_MAP,
    GENDER_FALLBACK_MAP,
    FIT_CANONICAL_MAP,
    SLEEVE_CANONICAL_MAP,
    PLUS_SIZE_KEYWORDS,
    NOISE_WORDS,
)
from src.mapping.compilers import (
    BewakoofCompiler,
    ShopifyCompiler,
    UniversalCompiler,
    SearchTierCompiler,
)
from src.mapping.intent_catalog_mapper import (
    IntentCatalogMapper,
    NativeLLMHook,
    get_product_color,
    get_semantic_affinity_tier,
    map_intent_to_catalog,
    normalize_category,
    normalize_color,
    parse_requested_sizes,
    preprocess_prompt,
    resolve_handle,
)

__all__ = [
    # Contracts
    "CatalogMappingInput",
    "ResolvedCatalogIntent",
    "StorePlatformEnum",
    "BewakoofQuerySpec",
    "ShopifyQuerySpec",
    "UniversalFilterSpec",
    "SearchTierConfig",
    # Core Functions
    "IntentCatalogMapper",
    "map_intent_to_catalog",
    "preprocess_prompt",
    "get_product_color",
    "get_semantic_affinity_tier",
    "resolve_handle",
    "parse_requested_sizes",
    "normalize_color",
    "normalize_category",
    "NativeLLMHook",
    # Compilers
    "BewakoofCompiler",
    "ShopifyCompiler",
    "UniversalCompiler",
    "SearchTierCompiler",
    # Taxonomies
    "SPELL_CORRECTIONS",
    "SYNONYM_MAP",
    "FANDOM_KNOWLEDGE_GRAPH",
    "CHARACTER_ENTITY_MAP",
    "ENTITY_FRANCHISE_MAP",
    "VIBE_MAP",
    "CATEGORY_TAXONOMY",
    "CATEGORY_SHOPIFY_TYPE_ALIASES",
    "MACRO_CATEGORY_EXPANSIONS",
    "COLOR_TAXONOMY",
    "FANDOM_HANDLE_MAP",
    "DESIGN_HANDLE_MAP",
    "CATEGORY_SLEEVE_HANDLE_MAP",
    "GENDER_FALLBACK_MAP",
    "FIT_CANONICAL_MAP",
    "SLEEVE_CANONICAL_MAP",
    "PLUS_SIZE_KEYWORDS",
    "NOISE_WORDS",
]
