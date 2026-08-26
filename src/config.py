"""Configuration, defaults, and runtime settings for the Rasor system."""

import os
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class ExecutionMode(str, Enum):
    DEV = "dev"       # Local structured mock data (fast, deterministic)
    LIVE = "live"     # Real-world data via Scraper, API, or MCP


class UIMode(str, Enum):
    STANDARD = "standard"  # Current one-shot input
    CHAT = "chat"          # Conversational Stylist Agent
    VOICE = "voice"        # Conversational + Speech-to-Text Input


class DataSourceType(str, Enum):
    DEV_MOCK = "dev_mock"
    BEWAKOOF_LIVE_API = "bewakoof_live_api"
    SHOPIFY_STOREFRONT_LIVE_API = "shopify_storefront_live_api"
    GOOGLE_SHOPPING_SCRAPER = "google_shopping_scraper"
    SHOPIFY_STOREFRONT_API = "shopify_storefront_api"
    MCP_SERVER = "mcp_server"


class ModelProvider(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"
    OPENAI = "openai"


# ==============================================================================
# System Defaults & Constants
# ==============================================================================
DEFAULT_MAX_COST_HITL: float = 100.00
DEFAULT_MAX_BUDGET: float = 500.00
DEFAULT_CURRENCY: str = "USD"
DEFAULT_TAX_RATE: float = 0.08
DEFAULT_SHIPPING_FLAT_RATE: float = 5.00
DEFAULT_FREE_SHIPPING_THRESHOLD: float = 50.00

DEFAULT_ALLOWED_MERCHANTS: List[str] = [
    "Amazon",
    "BestBuy",
    "Nike",
    "Target",
    "Walmart",
    "B&H Photo",
    "Google Shopping Merchant"
]


class AgentConfig(BaseModel):
    """Runtime configuration passed into the agent loop from the frontend."""
    mode: ExecutionMode = Field(default=ExecutionMode.LIVE)
    ui_mode: UIMode = Field(default=UIMode.CHAT, description="Frontend UX paradigm")
    data_source: DataSourceType = Field(default=DataSourceType.GOOGLE_SHOPPING_SCRAPER)
    primary_model: str = "gemini-2.5-flash"
    fallback_model: str = "llama-3.3-70b-versatile"
    
    # Financial & Guardrail Settings
    max_cost_hitl: float = Field(
        default=DEFAULT_MAX_COST_HITL,
        description="Transactions above this cost pause execution and require human confirmation."
    )
    max_budget: float = Field(
        default=DEFAULT_MAX_BUDGET,
        description="Hard spending limit. Any order exceeding this is strictly aborted."
    )
    currency: str = DEFAULT_CURRENCY
    allowed_merchants: List[str] = Field(default_factory=lambda: list(DEFAULT_ALLOWED_MERCHANTS))
    max_search_results: int = 5
    
    # Enrichment Settings
    enable_deep_enrichment: bool = Field(
        default=True,
        description="If True, fetches single-product details for top candidates before LLM evaluation."
    )
    max_deep_fetches: int = Field(
        default=10,
        description="Maximum number of products to deeply enrich. Limits API calls."
    )
    vqa_strict_filter: bool = Field(
        default=False,
        description="If True, VQA only scans products that perfectly match text constraints. If False, scans partial matches too."
    )
    enable_vqa_scanner: bool = Field(
        default=True,
        description="Master switch to enable or disable the VQA image scanner pipeline."
    )
    
    # Logistics Settings
    user_location: str = Field(
        default="Not Set",
        description="User's current location (e.g., Mumbai, Delhi, New York) for fast shipping calculations."
    )
    
    # Voice UI Settings
    tts_voice: str = Field(
        default="Samantha",
        description="The native macOS voice used for local Text-to-Speech playback."
    )
    
    # Semantic Pop-Culture Engine
    enable_semantic_engine: bool = Field(
        default=True,
        description="If True, expands fandom queries with semantic knowledge graph (e.g., 'Panther' → 'wakanda, t'challa'). May reduce result count but improves relevance."
    )
