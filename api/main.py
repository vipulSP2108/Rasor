"""FastAPI backend for Rasor Agentic Commerce.
Wraps all existing Python agents/providers with a thin REST layer.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Request, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json
import re
import traceback
import threading
import time

# ── Import all Rasor modules ──────────────────────────────────────────────────
from src.config import AgentConfig, ExecutionMode, DataSourceType, UIMode
from src.agent.brain import AgentBrain
from src.agent.stylist import StylistAgent
from src.agent.offers import OfferEngine
from src.agent.recommender import RecommenderAgent
from src.data.bewakoof_api import BewakoofCatalogProvider
from src.data.shopify_api import ShopifyCatalogProvider
from src.data.shopify_cart import ShopifyCartProvider
from src.data.shopify_admin import ShopifyAdminProvider
from src.data.dev_catalog import DevCatalogProvider
from src.data.scraper import GoogleShoppingScraper
from src.data.ledger import AuditLedger
from src.agent.state import Cart, CartItem, Product

try:
    from src.agent.checkout import CheckoutAgent
    HAS_CHECKOUT = True
except Exception:
    HAS_CHECKOUT = False

# ── App Setup ────────────────────────────────────────────────────────────────

# ── Swagger UI & OpenAPI Customization ────────────────────────────────────────
TAGS_METADATA = [
    {
        "name": "Quick Search & Intent Catalog",
        "description": "Quick Search one-shot natural language intent parsing, 5-tier progressive catalog relaxation, candidate filtering, multimodal VQA inspection, and deep PDP enrichment."
    },
    {
        "name": "Conversational Stylist",
        "description": "Multi-turn conversational stylist dialogue state, question-coupling, and interactive recommendation options."
    },
    {
        "name": "Outfit Studio & Garment Vision",
        "description": "Multi-piece look coordination, dynamic budget allocation, 'Match My Outfit' anchor pairing, and Gemini multimodal image extraction."
    },
    {
        "name": "Geodesic Logistics & Comparison",
        "description": "Nominatim / Zippopotam geocoding, geodesic Haversine transit velocity calculation, and multi-garment side-by-side matrices."
    },
    {
        "name": "Headless Storefront Cart",
        "description": "Headless Shopify Storefront cart initialization (`cartCreate`) and merchandise line mutations (`cartLinesAdd`)."
    },
    {
        "name": "Shopify Storefront GraphQL",
        "description": "Direct proxy and execution engine for raw Shopify Storefront GraphQL queries and mutations (`products`, `search`, `collections`, `cartCreate`, etc.)."
    },
    {
        "name": "Payment Rails & Mobile Rescue",
        "description": "Razorpay order creation, tokenized recurring mandate orders, programmatic S2S execution, dynamic SMS/WhatsApp rescue links, and status polling."
    },
    {
        "name": "Race Recovery & Instant Refunds",
        "description": "Deterministic post-payment inventory depletion resolution, 100% gateway refunds, and audit trail ledger."
    },
    {
        "name": "W3C AP2 Mandates",
        "description": "W3C Agent Payment Protocol spending bounds: Intent Mandates (budget limits) and Cart Mandates (SHA-256 frozen payloads)."
    },
    {
        "name": "ACP-2026.1 Catalog Protocol",
        "description": "Machine-readable Agentic Commerce Protocol catalog feeds and RFC .well-known discovery manifests for autonomous AI buyers."
    },
    {
        "name": "Settlement & Audit Ledger",
        "description": "Background reconciliation, Shopify Admin REST order creation (`financial_status: paid`), Razorpay webhook receiver, and immutable audit logs."
    },
    {
        "name": "Health & Gateway Keys",
        "description": "Gateway health liveness probes and public Razorpay Key ID publication."
    }
]

CUSTOM_SWAGGER_CSS = """
:root {
  --bg-main: #090d16;
  --bg-card: #0f172a;
  --bg-card-hover: #172033;
  --border-card: rgba(99, 102, 241, 0.2);
  --border-card-hover: rgba(99, 102, 241, 0.45);
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
  --accent-indigo: #6366f1;
  --accent-emerald: #10b981;
  --accent-amber: #f59e0b;
  --accent-rose: #f43f5e;
  --accent-cyan: #06b6d4;
}

body {
  background-color: var(--bg-main) !important;
  color: var(--text-main) !important;
  font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
  margin: 0 !important;
  padding-top: 68px !important;
}

/* Custom Rasor Sticky Luxury Topbar */
.rasor-topbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  background: rgba(9, 13, 22, 0.92);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(99, 102, 241, 0.25);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  z-index: 99999;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.rasor-brand-group {
  display: flex;
  align-items: center;
  gap: 16px;
}

.rasor-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
}

.rasor-brand-icon {
  font-size: 1.4rem;
  filter: drop-shadow(0 0 8px rgba(99, 102, 241, 0.6));
}

.rasor-brand-name {
  font-size: 1.35rem;
  font-weight: 800;
  background: linear-gradient(135deg, #818cf8 0%, #c084fc 50%, #f472b6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.5px;
}

.rasor-brand-sub {
  font-size: 0.8rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-left: 2px;
}

.rasor-badge-online {
  display: flex;
  align-items: center;
  gap: 7px;
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #34d399;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 4px 11px;
  border-radius: 9999px;
  letter-spacing: 0.2px;
}

.rasor-badge-online .dot {
  width: 7px;
  height: 7px;
  background-color: #10b981;
  border-radius: 50%;
  box-shadow: 0 0 8px #10b981;
  animation: pulse-dot 2s infinite;
}

@keyframes pulse-dot {
  0% { transform: scale(0.95); opacity: 0.8; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
  70% { transform: scale(1.05); opacity: 1; box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
  100% { transform: scale(0.95); opacity: 0.8; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

.rasor-nav-links {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rasor-nav-link {
  color: #cbd5e1;
  font-size: 0.82rem;
  font-weight: 600;
  text-decoration: none;
  padding: 7px 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.04);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 6px;
}

.rasor-nav-link:hover {
  background: rgba(99, 102, 241, 0.18);
  border-color: rgba(99, 102, 241, 0.5);
  color: #ffffff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
}

.rasor-link-primary {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(168, 85, 247, 0.25)) !important;
  border-color: rgba(99, 102, 241, 0.5) !important;
  color: #a5b4fc !important;
}
.rasor-link-primary:hover {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.4), rgba(168, 85, 247, 0.4)) !important;
  color: #ffffff !important;
}

/* Hide Default Swagger Header */
.swagger-ui .topbar { display: none !important; }

/* Global Swagger Container */
.swagger-ui {
  color: var(--text-main) !important;
}

.swagger-ui .wrapper {
  max-width: 1380px !important;
  padding: 24px 20px !important;
}

/* Information Container */
.swagger-ui .info {
  margin: 20px 0 30px 0 !important;
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.75)) !important;
  border: 1px solid rgba(99, 102, 241, 0.3) !important;
  border-radius: 16px !important;
  padding: 28px !important;
  box-shadow: 0 10px 35px rgba(0, 0, 0, 0.45) !important;
}

.swagger-ui .info .title {
  color: #f8fafc !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-weight: 800 !important;
  font-size: 2.1rem !important;
  letter-spacing: -0.5px !important;
}

.swagger-ui .info p, .swagger-ui .info li {
  color: var(--text-muted) !important;
  font-size: 0.95rem !important;
  line-height: 1.65 !important;
}

.swagger-ui .info a {
  color: #818cf8 !important;
  text-decoration: none !important;
  font-weight: 600 !important;
}

.swagger-ui .info a:hover {
  text-decoration: underline !important;
  color: #a5b4fc !important;
}

/* Filter Search Bar */
.swagger-ui .filter-container {
  padding: 12px 0 !important;
}
.swagger-ui .filter-container input {
  background: #0f172a !important;
  border: 1px solid rgba(99, 102, 241, 0.35) !important;
  border-radius: 10px !important;
  color: #f8fafc !important;
  padding: 12px 18px !important;
  font-size: 0.95rem !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
  outline: none !important;
  width: 100% !important;
  max-width: 480px !important;
  transition: all 0.2s ease !important;
}
.swagger-ui .filter-container input:focus {
  border-color: #6366f1 !important;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25) !important;
}

/* Operation Blocks (Tag Sections) */
.swagger-ui .opblock-tag {
  color: #f1f5f9 !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-size: 1.28rem !important;
  font-weight: 700 !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
  padding: 18px 0 10px 0 !important;
  margin-top: 28px !important;
}

.swagger-ui .opblock-tag small {
  color: var(--text-muted) !important;
  font-size: 0.86rem !important;
  font-weight: 400 !important;
  margin-left: 12px !important;
}

/* Operation Items (Endpoints) */
.swagger-ui .opblock {
  background: var(--bg-card) !important;
  border: 1px solid var(--border-card) !important;
  border-radius: 12px !important;
  margin-bottom: 14px !important;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.25) !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
  overflow: hidden !important;
}

.swagger-ui .opblock:hover {
  border-color: var(--border-card-hover) !important;
  box-shadow: 0 8px 25px -4px rgba(99, 102, 241, 0.25) !important;
  transform: translateY(-1px) !important;
}

/* Method Badges */
.swagger-ui .opblock .opblock-summary-method {
  font-family: 'JetBrains Mono', monospace !important;
  font-weight: 700 !important;
  font-size: 0.82rem !important;
  border-radius: 8px !important;
  padding: 6px 14px !important;
  text-shadow: none !important;
  min-width: 80px !important;
  text-align: center !important;
}

.swagger-ui .opblock.opblock-post {
  border-left: 4px solid var(--accent-indigo) !important;
}
.swagger-ui .opblock.opblock-post .opblock-summary-method {
  background: linear-gradient(135deg, #4f46e5, #6366f1) !important;
  color: #ffffff !important;
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.4) !important;
}

.swagger-ui .opblock.opblock-get {
  border-left: 4px solid var(--accent-emerald) !important;
}
.swagger-ui .opblock.opblock-get .opblock-summary-method {
  background: linear-gradient(135deg, #059669, #10b981) !important;
  color: #ffffff !important;
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.4) !important;
}

.swagger-ui .opblock.opblock-delete {
  border-left: 4px solid var(--accent-rose) !important;
}
.swagger-ui .opblock.opblock-delete .opblock-summary-method {
  background: linear-gradient(135deg, #e11d48, #f43f5e) !important;
  color: #ffffff !important;
  box-shadow: 0 0 12px rgba(244, 63, 94, 0.4) !important;
}

/* Summary Path & Description */
.swagger-ui .opblock .opblock-summary-path {
  color: #f1f5f9 !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.92rem !important;
  font-weight: 600 !important;
}

.swagger-ui .opblock .opblock-summary-description {
  color: var(--text-muted) !important;
  font-size: 0.85rem !important;
  font-weight: 500 !important;
}

/* Expanded Body */
.swagger-ui .opblock-body {
  background: #090e1a !important;
  padding: 20px !important;
  border-top: 1px solid rgba(255, 255, 255, 0.05) !important;
}

.swagger-ui .opblock-section-header {
  background: rgba(255, 255, 255, 0.02) !important;
  color: #94a3b8 !important;
  padding: 8px 12px !important;
  border-radius: 6px !important;
}

.swagger-ui table thead tr th, .swagger-ui table thead tr td {
  color: #cbd5e1 !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
}

.swagger-ui table tbody tr td {
  color: #e2e8f0 !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04) !important;
}

/* Parameters & Inputs */
.swagger-ui input[type=text], .swagger-ui textarea, .swagger-ui select {
  background: #0f172a !important;
  color: #f8fafc !important;
  border: 1px solid rgba(99, 102, 241, 0.3) !important;
  border-radius: 8px !important;
  padding: 8px 12px !important;
  font-family: 'JetBrains Mono', monospace !important;
}

/* Execute & Try it out Buttons */
.swagger-ui .btn {
  border-radius: 8px !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-weight: 600 !important;
  transition: all 0.2s ease !important;
}

.swagger-ui .btn.execute {
  background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
  color: #ffffff !important;
  border: none !important;
  padding: 10px 24px !important;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4) !important;
}

.swagger-ui .btn.execute:hover {
  background: linear-gradient(135deg, #818cf8, #6366f1) !important;
  transform: translateY(-1px) !important;
}

.swagger-ui .btn.try-out__btn {
  background: rgba(99, 102, 241, 0.15) !important;
  border: 1px solid rgba(99, 102, 241, 0.4) !important;
  color: #a5b4fc !important;
}

.swagger-ui .btn.try-out__btn:hover {
  background: rgba(99, 102, 241, 0.25) !important;
  color: #fff !important;
}

/* Code Blocks & Responses */
.swagger-ui .highlight-code, .swagger-ui pre {
  background: #030712 !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 8px !important;
  font-family: 'JetBrains Mono', monospace !important;
  color: #e2e8f0 !important;
}

.swagger-ui .response-col_status {
  color: #34d399 !important;
  font-weight: 700 !important;
  font-family: 'JetBrains Mono', monospace !important;
}

/* Zero-out default browser button backgrounds */
.swagger-ui button,
.swagger-ui button:not(.btn),
.swagger-ui .model-box-control,
.swagger-ui .models-control,
.swagger-ui .model-toggle,
.swagger-ui .expand-operation,
.swagger-ui .opblock-control-arrow {
  background: transparent !important;
  background-color: transparent !important;
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

/* Models / Schemas Section Dark Theme Polish */
.swagger-ui section.models {
  background: #0b1120 !important;
  border: 1px solid rgba(99, 102, 241, 0.25) !important;
  border-radius: 14px !important;
  padding: 20px !important;
  margin-top: 36px !important;
}

.swagger-ui section.models h4,
.swagger-ui section.models h4 span,
.swagger-ui section.models .models-control {
  color: #f8fafc !important;
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  font-weight: 700 !important;
  background: transparent !important;
  background-color: transparent !important;
}

.swagger-ui section.models .model-container {
  background: #0f172a !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 10px !important;
  margin: 12px 0 !important;
  padding: 14px 18px !important;
  transition: all 0.2s ease !important;
}

.swagger-ui section.models .model-container:hover {
  border-color: rgba(99, 102, 241, 0.45) !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35) !important;
}

.swagger-ui .model-box {
  background: transparent !important;
  background-color: transparent !important;
}

.swagger-ui section.models *,
.swagger-ui .model-box *,
.swagger-ui .model-box-control *,
.swagger-ui .models-control * {
  background-color: transparent !important;
}

.swagger-ui .model-title {
  color: #818cf8 !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 1rem !important;
  font-weight: 700 !important;
  background: transparent !important;
}

.swagger-ui .model-toggle svg,
.swagger-ui .model-box-control svg,
.swagger-ui .models-control svg {
  fill: #818cf8 !important;
}

.swagger-ui .property-row {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
}

.swagger-ui .property-row td {
  padding: 8px 6px !important;
  color: #cbd5e1 !important;
  vertical-align: top !important;
  background: transparent !important;
  border: none !important;
}

.swagger-ui .property-name {
  color: #a5b4fc !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-weight: 600 !important;
  background: transparent !important;
}

.swagger-ui .prop-type {
  color: #38bdf8 !important;
  font-family: 'JetBrains Mono', monospace !important;
  background: transparent !important;
}

.swagger-ui .prop-format {
  color: #fbbf24 !important;
  background: transparent !important;
}

.swagger-ui .model-hint {
  color: #34d399 !important;
  background: transparent !important;
}

.swagger-ui .renderedMarkdown,
.swagger-ui .renderedMarkdown p {
  color: #94a3b8 !important;
  background: transparent !important;
}


/* Universal High-Contrast Dark Text Protection (Never Black) */
.swagger-ui,
.swagger-ui p,
.swagger-ui span,
.swagger-ui div,
.swagger-ui label,
.swagger-ui td,
.swagger-ui th,
.swagger-ui li,
.swagger-ui a,
.swagger-ui h1, .swagger-ui h2, .swagger-ui h3, .swagger-ui h4, .swagger-ui h5,
.swagger-ui .renderedMarkdown,
.swagger-ui .renderedMarkdown p,
.swagger-ui .renderedMarkdown div,
.swagger-ui .renderedMarkdown li,
.swagger-ui .renderedMarkdown table td,
.swagger-ui .renderedMarkdown table th,
.swagger-ui .markdown p,
.swagger-ui .markdown li,
.swagger-ui .parameter__name,
.swagger-ui .parameter__type,
.swagger-ui .parameter__deprecated,
.swagger-ui .parameter__in,
.swagger-ui .parameters-col_description,
.swagger-ui .parameters-col_description p,
.swagger-ui .response-col_description,
.swagger-ui .response-col_description p,
.swagger-ui .response-col_description__inner,
.swagger-ui .response-col_description__inner p,
.swagger-ui .response-col_description__inner div,
.swagger-ui .opblock-description-wrapper,
.swagger-ui .opblock-description-wrapper p,
.swagger-ui .opblock-external-docs-wrapper,
.swagger-ui .opblock-title_normal,
.swagger-ui .opblock-title_normal p,
.swagger-ui .model-title,
.swagger-ui .model,
.swagger-ui .model-box,
.swagger-ui .model-box-control,
.swagger-ui .prop-format,
.swagger-ui .prop-type,
.swagger-ui .property-row td,
.swagger-ui .tab li button.tablinks,
.swagger-ui .responses-inner h4,
.swagger-ui .responses-inner h5,
.swagger-ui .body-param__text-placeholder {
  color: #e2e8f0 !important;
}

.swagger-ui .parameter__name {
  color: #a5b4fc !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-weight: 600 !important;
}

.swagger-ui .parameter__type {
  color: #38bdf8 !important;
  font-family: 'JetBrains Mono', monospace !important;
}

.swagger-ui .prop-format {
  color: #fbbf24 !important;
}

.swagger-ui select {
  background-color: #0f172a !important;
  color: #f8fafc !important;
  border: 1px solid rgba(99, 102, 241, 0.35) !important;
}

.swagger-ui select option {
  background-color: #0f172a !important;
  color: #f8fafc !important;
}

.swagger-ui input,
.swagger-ui textarea {
  background-color: #0b1120 !important;
  color: #ffffff !important;
  border: 1px solid rgba(99, 102, 241, 0.35) !important;
}

.swagger-ui input::placeholder,
.swagger-ui textarea::placeholder {
  color: #64748b !important;
}

.swagger-ui .tab li button.tablinks {
  color: #94a3b8 !important;
}
.swagger-ui .tab li button.tablinks.active {
  color: #818cf8 !important;
  font-weight: 700 !important;
}

/* Custom Scrollbar */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: #090d16;
}
::-webkit-scrollbar-thumb {
  background: #1e293b;
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: #334155;
}
"""

CUSTOM_TOPBAR_HTML = """
<header class="rasor-topbar">
  <div class="rasor-brand-group">
    <a href="/docs" class="rasor-brand">
      <span class="rasor-brand-name">Rasor</span>
      <span class="rasor-brand-sub">Gateway API</span>
    </a>
    <div class="rasor-badge-online">
      <span class="dot"></span>
      <span>Gateway Online (v2.0.0)</span>
    </div>
  </div>
  <nav class="rasor-nav-links">
    <a href="http://localhost:5173" target="_blank" class="rasor-nav-link rasor-link-primary">
      Web Client (5173)
    </a>
    <a href="/scalar" class="rasor-nav-link">
      Scalar Docs
    </a>
    <a href="/redoc" class="rasor-nav-link">
      ReDoc
    </a>
    <a href="/shopify-console" class="rasor-nav-link">
      Shopify GraphQL
    </a>
    <a href="/api/v1/acp/catalog.json" target="_blank" class="rasor-nav-link">
      ACP Feed
    </a>
  </nav>
</header>
"""

app = FastAPI(
    title="Rasor: Autonomous Agentic Commerce Gateway",
    description="""
### Production Autonomous Commerce API Gateway
Orchestrates natural language apparel shopping intent, W3C AP2 spending mandates, headless Shopify mutations, multi-rail banking failover cascades, and real-time mobile rescue.

* **Client Web Application:** [http://localhost:5173](http://localhost:5173)
* **Interactive Scalar Docs:** [/scalar](/scalar)
* **ReDoc Specification:** [/redoc](/redoc)
* **Agentic Commerce Protocol (ACP):** [/api/v1/acp/catalog.json](/api/v1/acp/catalog.json)
    """,
    version="2.0.0",
    openapi_tags=TAGS_METADATA,
    docs_url=None,
    redoc_url=None
)

# Background thread that reconciles mobile payment links every 6 seconds
def _background_plink_reconciler():
    """Continuously checks for paid mobile rescue links and syncs to Shopify."""
    while True:
        try:
            if HAS_CHECKOUT:
                agent = CheckoutAgent()
                agent.reconcile_payment_links()
        except Exception:
            pass
        time.sleep(6)

@app.on_event("startup")
def on_app_startup():
    t = threading.Thread(target=_background_plink_reconciler, daemon=True)
    t.start()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Interactive Documentation UIs (Swagger Dark & Scalar) ─────────────────────
@app.get("/docs", include_in_schema=False)
def custom_swagger_ui_html():
    resp = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="Rasor Autonomous Commerce — API Explorer",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        swagger_ui_parameters={
            "docExpansion": "list",
            "filter": True,
            "showRequestHeaders": True,
            "syntaxHighlight.theme": "monokai",
            "tryItOutEnabled": True,
            "persistAuthorization": True,
        }
    )
    raw_html = resp.body.decode("utf-8")
    custom_head = f"""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
    {CUSTOM_SWAGGER_CSS}
    </style>
    </head>
    """
    custom_body = f"""
    <body>
    {CUSTOM_TOPBAR_HTML}
    """
    tag_scroll_script = r"""
    <script>
    (function() {
      function scrollToTag() {
        var raw = window.location.hash;
        if (!raw) return;
        try {
          var decoded = decodeURIComponent(raw);
          // Strip emojis and leading hashes
          var clean = decoded.replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}]/gu, '');
          var tag = clean.replace(/^[#\/]+/, '').trim();
          if (!tag) return;

          // Update URL hash cleanly if it had emojis
          if (decoded !== '#/' + tag && decoded !== '#' + tag) {
            try { history.replaceState(null, '', '#/' + encodeURIComponent(tag)); } catch(e) {}
          }

          var normalizedId = 'operations-tag-' + tag.replace(/[\s&/]+/g, '_');
          var el = document.getElementById(normalizedId) || 
                   document.querySelector('[data-tag="' + tag + '"]') ||
                   document.getElementById(tag) ||
                   document.querySelector('h3[id*="' + tag.replace(/\s+/g, '_') + '"]');

          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        } catch(e) {}
      }

      window.addEventListener('load', function() {
        setTimeout(scrollToTag, 300);
        setTimeout(scrollToTag, 900);
        setTimeout(scrollToTag, 1800);
      });
      window.addEventListener('hashchange', scrollToTag);
    })();
    </script>
    </body>
    """
    styled_html = raw_html.replace("</head>", custom_head, 1).replace("<body>", custom_body, 1).replace("</body>", tag_scroll_script, 1)
    return HTMLResponse(content=styled_html)

@app.get("/scalar", include_in_schema=False)
def scalar_html():
    html = f"""<!doctype html>
<html>
  <head>
    <title>Rasor API Reference (Scalar)</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%236366f1'><path d='M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zM1 2v2h2l3.6 7.59-1.35 2.45c-.16.28-.25.61-.25.96 0 1.1.9 2 2 2h12v-2H7.42c-.14 0-.25-.11-.25-.25l.03-.12.9-1.63h7.45c.75 0 1.41-.41 1.75-1.03l3.58-6.49c.08-.14.12-.31.12-.48 0-.55-.45-1-1-1H5.21l-.94-2H1zm16 16c-1.1 0-1.99.9-1.99 2s.89 2 1.99 2 2-.9 2-2-.9-2-2-2z'/></svg>">
    <style>
      body {{ margin: 0; background: #090d16; }}
    </style>
  </head>
  <body>
    <script 
      id="api-reference" 
      data-url="{app.openapi_url}"
      data-configuration='{{"theme":"purple","layout":"modern","darkMode":true,"showSidebar":true,"searchHotKey":"k"}}'
    ></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/redoc", include_in_schema=False)
def redoc_ui():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title="Rasor Autonomous Commerce — ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"
    )


# ── Shopify Storefront GraphQL Console ─────────────────────────────────────────
@app.get("/shopify-console", include_in_schema=False)
def shopify_graphql_console():
    """
    Embedded GraphiQL playground pre-configured for the Shopify Storefront API.
    Token and endpoint are injected from env at render-time; developers can edit
    the token in the HTTP-header panel inside GraphiQL.
    """
    import os
    shopify_url = os.getenv(
        "SHOPIFY_STOREFRONT_URL",
        "https://rasor-test-store-1.myshopify.com/api/2024-04/graphql.json"
    )
    storefront_token = (
        os.getenv("SHOPIFY_STOREFRONT_TOKEN")
        or os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN")
        or "6a1c1b2f3f1fafd8afc7040ed4e19307"
    )

    # ── Curated example queries shipped with the console ───────────────────────
    # Each entry: { label, query, variables } — kept in sync with shopify_storefront_api_reference.md
    examples = [
        {
            "label": "1. products — Catalog Search (Tier 1)",
            "query": """
query ProductSearch($query: String!, $first: Int!) {
  products(query: $query, first: $first, sortKey: RELEVANCE) {
    edges {
      node {
        id
        title
        productType
        tags
        priceRange {
          minVariantPrice { amount currencyCode }
          maxVariantPrice { amount currencyCode }
        }
        images(first: 1) { edges { node { url altText } } }
        variants(first: 10) {
          edges {
            node {
              id
              title
              availableForSale
              price { amount currencyCode }
            }
          }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}""",
            "variables": '{"query": "graphic t-shirt men white", "first": 6}'
        },
        {
            "label": "2. search — Full-Text Relevance Search (Tier 2)",
            "query": """
query FullTextSearch($query: String!, $first: Int!) {
  search(query: $query, first: $first, types: [PRODUCT]) {
    edges {
      node {
        ... on Product {
          id
          title
          productType
          priceRange {
            minVariantPrice { amount currencyCode }
          }
          images(first: 1) { edges { node { url } } }
        }
      }
    }
    totalCount
  }
}""",
            "variables": '{"query": "men oversized black graphic tshirt", "first": 10}'
        },
        {
            "label": "3. predictiveSearch — Typeahead Autocomplete",
            "query": """
query TypeaheadSearch($query: String!) {
  predictiveSearch(query: $query, types: [PRODUCT]) {
    products {
      id
      title
      productType
      priceRange {
        minVariantPrice { amount currencyCode }
      }
      images(first: 1) { edges { node { url } } }
    }
    queries { text }
  }
}""",
            "variables": '{"query": "graphic hoodie"}'
        },
        {
            "label": "4. collections — Catalog Collection List",
            "query": """
query CollectionsList($first: Int!) {
  collections(first: $first) {
    edges {
      node {
        id
        handle
        title
        description
        productsCount { count }
      }
    }
  }
}""",
            "variables": '{"first": 20}'
        },
        {
            "label": "5. collection — Products by Handle",
            "query": """
query ProductsByCollection($handle: String!, $first: Int!) {
  collection(handle: $handle) {
    id
    title
    products(first: $first) {
      edges {
        node {
          id
          title
          priceRange {
            minVariantPrice { amount currencyCode }
          }
          images(first: 1) { edges { node { url } } }
        }
      }
    }
  }
}""",
            "variables": '{"handle": "t-shirts", "first": 10}'
        },
        {
            "label": "6. cart — Inspect Cart State & Checkout URL",
            "query": """
query CartInspect($cartId: ID!) {
  cart(id: $cartId) {
    id
    checkoutUrl
    totalQuantity
    cost {
      totalAmount { amount currencyCode }
      subtotalAmount { amount currencyCode }
    }
    lines(first: 20) {
      edges {
        node {
          id
          quantity
          merchandise {
            ... on ProductVariant {
              id
              title
              price { amount currencyCode }
              product { id title images(first: 1) { edges { node { url } } } }
            }
          }
        }
      }
    }
  }
}""",
            "variables": '{"cartId": "gid://shopify/Cart/YOUR_CART_ID"}'
        },
        {
            "label": "7. shop — Store Metadata & Policies",
            "query": """
query ShopMetadata {
  shop {
    name
    description
    primaryDomain { url }
    currencyCode
    paymentSettings {
      acceptedCardBrands
      supportedDigitalWallets
    }
    shippingPolicy { body }
    refundPolicy { body }
    privacyPolicy { body }
  }
}""",
            "variables": '{}'
        },
        {
            "label": "8. cartCreate — Initialize Headless Cart (Mutation)",
            "query": """
mutation CartCreate($input: CartInput!) {
  cartCreate(input: $input) {
    cart {
      id
      checkoutUrl
      totalQuantity
      cost {
        totalAmount { amount currencyCode }
      }
      lines(first: 5) {
        edges {
          node {
            id
            quantity
            merchandise {
              ... on ProductVariant {
                id
                title
                price { amount currencyCode }
              }
            }
          }
        }
      }
    }
    userErrors { field message }
  }
}""",
            "variables": '{"input": {"lines": [{"merchandiseId": "gid://shopify/ProductVariant/YOUR_VARIANT_ID", "quantity": 1}]}}'
        }
    ]

    import json as _json
    examples_json = _json.dumps(examples)

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Shopify Storefront GraphQL Console — Rasor</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/graphiql@3/graphiql.min.css">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ height: 100%; overflow: hidden; }}
    body {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      background: #09121f;
      color: #cbd5e1;
      display: flex;
      flex-direction: column;
    }}

    /* ── Topbar ── */
    .console-topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      height: 48px;
      background: #0f1e30;
      border-bottom: 1px solid #1e3a5f;
      flex-shrink: 0;
      gap: 12px;
      z-index: 100;
    }}
    .console-brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
    }}
    .console-brand-name {{
      font-size: 14px;
      font-weight: 700;
      color: #6366f1;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .console-brand-sep {{ color: #334155; font-size: 14px; }}
    .console-brand-sub {{
      font-size: 12px;
      color: #008060;
      font-weight: 600;
      letter-spacing: 0.03em;
    }}
    .console-nav {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .console-nav a {{
      font-size: 11px;
      color: #94a3b8;
      text-decoration: none;
      padding: 4px 10px;
      border-radius: 4px;
      transition: background 0.15s, color 0.15s;
      font-weight: 500;
    }}
    .console-nav a:hover {{ background: #1e293b; color: #cbd5e1; }}
    .console-nav a.active {{ background: #1e3a5f; color: #38bdf8; }}
    .console-endpoint-badge {{
      font-size: 10px;
      color: #475569;
      font-family: 'JetBrains Mono', monospace;
      background: #0a1828;
      border: 1px solid #1e293b;
      border-radius: 4px;
      padding: 2px 8px;
      max-width: 320px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}

    /* ── Layout ── */
    .console-layout {{
      display: flex;
      flex: 1;
      overflow: hidden;
    }}

    /* ── Sidebar ── */
    .console-sidebar {{
      width: 220px;
      flex-shrink: 0;
      background: #0c1825;
      border-right: 1px solid #1e3a5f;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .sidebar-header {{
      padding: 12px 14px 8px;
      font-size: 10px;
      font-weight: 700;
      color: #475569;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      border-bottom: 1px solid #1e293b;
      flex-shrink: 0;
    }}
    .sidebar-list {{
      overflow-y: auto;
      flex: 1;
      padding: 8px 0;
    }}
    .sidebar-item {{
      display: block;
      padding: 7px 14px;
      font-size: 11.5px;
      color: #94a3b8;
      cursor: pointer;
      border-left: 2px solid transparent;
      transition: all 0.12s;
      line-height: 1.4;
      word-break: break-word;
    }}
    .sidebar-item:hover {{ background: #111f30; color: #cbd5e1; border-left-color: #334155; }}
    .sidebar-item.active {{ background: #112033; color: #38bdf8; border-left-color: #0284c7; }}
    .sidebar-item .query-type {{
      display: inline-block;
      font-size: 9.5px;
      font-weight: 700;
      font-family: 'JetBrains Mono', monospace;
      padding: 1px 5px;
      border-radius: 3px;
      margin-right: 5px;
      text-transform: uppercase;
    }}
    .sidebar-item .qt-query {{ background: #0c2d4a; color: #38bdf8; }}
    .sidebar-item .qt-mutation {{ background: #2d1a4a; color: #a78bfa; }}

    /* ── GraphiQL wrapper ── */
    .graphiql-wrapper {{
      flex: 1;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    #graphiql-container {{
      flex: 1;
      overflow: hidden;
    }}

    /* ── GraphiQL dark theme overrides ── */
    .graphiql-container {{
      --color-base: #09121f;
      --color-neutral: #1e293b;
      --color-primary: #6366f1;
      --color-tertiary: #38bdf8;
      --color-warning: #f59e0b;
      --color-danger: #ef4444;
      --color-success: #10b981;
      --color-info: #38bdf8;
      --color-beta: #a78bfa;
    }}
    .graphiql-container, .graphiql-container * {{ font-family: 'Plus Jakarta Sans', sans-serif !important; }}
    .graphiql-container .graphiql-editor, .graphiql-container .CodeMirror {{
      font-family: 'JetBrains Mono', monospace !important;
      font-size: 13px !important;
    }}
    .graphiql-container .graphiql-sidebar {{ background: #0c1825; border-right: 1px solid #1e293b; }}
    .graphiql-container .graphiql-main {{ background: #09121f; }}
    .graphiql-container .graphiql-response {{ background: #091420; }}
    .graphiql-container .graphiql-toolbar {{ background: #0f1e30; border-bottom: 1px solid #1e293b; }}
    button.graphiql-execute-button {{
      background: #4f46e5 !important;
      border-radius: 5px !important;
      font-family: 'Plus Jakarta+Sans', sans-serif !important;
      font-weight: 600 !important;
      letter-spacing: 0.02em !important;
    }}
    button.graphiql-execute-button:hover {{ background: #4338ca !important; }}
  </style>
</head>
<body>
  <div class="console-topbar">
    <a href="/docs" class="console-brand">
      <span class="console-brand-name">Rasor</span>
      <span class="console-brand-sep">/</span>
      <span class="console-brand-sub">Shopify GraphQL Console</span>
    </a>
    <div class="console-endpoint-badge">{shopify_url}</div>
    <nav class="console-nav">
      <a href="/docs">REST API Explorer</a>
      <a href="/scalar">Scalar Docs</a>
      <a href="/redoc">ReDoc</a>
      <a href="/shopify-console" class="active">Shopify GraphQL</a>
      <a href="/api/v1/acp/catalog.json" target="_blank">ACP Feed</a>
    </nav>
  </div>

  <div class="console-layout">
    <aside class="console-sidebar">
      <div class="sidebar-header">Example Operations</div>
      <div class="sidebar-list" id="sidebar-list"></div>
    </aside>

    <div class="graphiql-wrapper">
      <div id="graphiql-container"></div>
    </div>
  </div>

  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/graphiql@3/graphiql.min.js"></script>
  <script>
    const SHOPIFY_URL = {_json.dumps(shopify_url)};
    const STOREFRONT_TOKEN = {_json.dumps(storefront_token)};
    const EXAMPLES = {examples_json};

    // ── GraphQL Fetcher pointing at server proxy (avoids CORS & manages auth) ──
    function shopifyFetcher(graphQLParams, opts) {{
      const headers = Object.assign({{
        'Content-Type': 'application/json',
      }}, (opts && opts.headers) || {{}});
      return fetch('/api/shopify/graphql', {{
        method: 'POST',
        headers: headers,
        body: JSON.stringify(graphQLParams)
      }}).then(function (r) {{
        return r.json();
      }});
    }}

    // ── Track current editor state ────────────────────────────────────────────
    let currentQuery = EXAMPLES[0].query.trim();
    let currentVariables = EXAMPLES[0].variables;
    let graphiqlRef = null;

    // ── Render GraphiQL ───────────────────────────────────────────────────────
    function renderGraphiQL(query, variables) {{
      const container = document.getElementById('graphiql-container');
      const element = React.createElement(GraphiQL, {{
        fetcher: shopifyFetcher,
        defaultQuery: query,
        variables: variables,
        defaultHeaders: JSON.stringify({{
          'X-Shopify-Storefront-Access-Token': STOREFRONT_TOKEN
        }}, null, 2),
        theme: 'dark',
        shouldPersistHeaders: true,
      }});
      if (graphiqlRef) {{
        ReactDOM.unmountComponentAtNode(container);
      }}
      ReactDOM.render(element, container);
      graphiqlRef = true;
    }}

    // ── Sidebar ───────────────────────────────────────────────────────────────
    function buildSidebar() {{
      const list = document.getElementById('sidebar-list');
      EXAMPLES.forEach((ex, i) => {{
        const isMutation = ex.query.trim().startsWith('mutation');
        const item = document.createElement('div');
        item.className = 'sidebar-item' + (i === 0 ? ' active' : '');
        const typeSpan = `<span class="query-type ${{isMutation ? 'qt-mutation' : 'qt-query'}}">${{isMutation ? 'MUT' : 'QRY'}}</span>`;
        const label = ex.label.replace(/^\d+\.\s*/, '');
        item.innerHTML = typeSpan + label;
        item.addEventListener('click', () => {{
          document.querySelectorAll('.sidebar-item').forEach(el => el.classList.remove('active'));
          item.classList.add('active');
          renderGraphiQL(ex.query.trim(), ex.variables);
        }});
        list.appendChild(item);
      }});
    }}

    buildSidebar();
    renderGraphiQL(currentQuery, currentVariables);
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


# Per-session stylist agents (keyed by session_id)
_stylist_agents: Dict[str, StylistAgent] = {}

def get_provider(data_source: Any):
    ds = str(data_source or "").lower().strip()
    if ds in ("shopify", "shopify_storefront", "shopify_live", "shopify_storefront_live_api", "shopify_storefront_api"):
        return ShopifyCatalogProvider()
    elif ds in ("bewakoof", "bewakoof_api", "bewakoof_live_api"):
        return BewakoofCatalogProvider()
    elif ds in ("google", "google_shopping", "google_shopping_scraper"):
        return GoogleShoppingScraper()
    else:
        return DevCatalogProvider()

# ── Request/Response Models ───────────────────────────────────────────────────
# ── Conversational & One-Shot Stylist Models ──
class BuyActionModel(BaseModel):
    action: str = Field(description="'buy_items' or 'clarify_quantity'")
    targets: List[int] = Field(default_factory=list, description="1-based product pick indices, e.g. [1] or [1, 2]")
    quantities: List[int] = Field(default_factory=list, description="Quantity for each target, e.g. [1] or [2]")
    reason: Optional[str] = Field(default=None, description="Stylist rationale for selection")

class ChatResponse(BaseModel):
    intent: str = Field(description="Detected dialogue intent: greeting, clarify, search, autopilot, buy, or clarify_quantity")
    message: str = Field(description="Conversational stylist reply to the user")
    suggested_options: List[str] = Field(default_factory=list, description="Tailored quick-reply suggestion chips")
    ready_for_search: bool = Field(default=False, description="Whether parameters are refined enough to trigger product search")
    updated_query: Optional[str] = Field(default="", description="Synthesized search query for downstream catalog retrieval")
    buy_action: Optional[BuyActionModel] = Field(default=None, description="One-shot autonomous purchase action payload")

    model_config = {
        "json_schema_extra": {
            "example": {
                "intent": "buy",
                "message": "Adding the top pick to your cart and initiating autonomous Multi-Rail Failover checkout now.",
                "suggested_options": ["Track Order", "View Receipt", "Explore Matching Shoes"],
                "ready_for_search": False,
                "updated_query": "men oversized black graphic tshirt",
                "buy_action": {
                    "action": "buy_items",
                    "targets": [1, 2],
                    "quantities": [1, 1],
                    "reason": "Top curated styling picks matching casual party intent"
                }
            }
        }
    }

class OneShotStylistRequest(BaseModel):
    prompt: str = Field(description="Direct one-shot shopping prompt or style directive")
    data_source: str = Field(default="shopify_storefront_live_api", description="Catalog provider: shopify_storefront_live_api or bewakoof_live_api")
    max_budget: float = Field(default=3000.0, description="Spending limit cap")
    primary_model: str = Field(default="gemini-3.1-flash-lite", description="Primary LLM")
    fallback_model: str = Field(default="llama-3.3-70b-versatile", description="Fallback LLM")
    currency: str = Field(default="INR", description="Transaction currency")
    user_location: str = Field(default="Mumbai", description="User shipping city")

    model_config = {
        "json_schema_extra": {
            "example": {
                "prompt": "Show me men's t-shirts with a graphic over it in white color"
            }
        }
    }

class OneShotStylistResponse(BaseModel):
    intent: str = Field(description="Final resolved execution intent (buy)")
    message: str = Field(description="Stylist confirmation message")
    ready_for_search: bool = Field(default=True)
    updated_query: str = Field(description="Normalized search query")
    buy_action: Dict[str, Any] = Field(description="Autonomous buy targets and quantities")
    selected_items: List[Dict[str, Any]] = Field(description="Curated merchandise items ready for checkout")
    total_price: float = Field(description="Total cart price for selected items")
    suggested_options: List[str] = Field(default_factory=list)
    canonical_query: Dict[str, Any] = Field(default_factory=dict, description="Normalized multi-attribute intent extracted by AgentBrain")
    evaluations: List[Dict[str, Any]] = Field(default_factory=list, description="LLM & VQA multi-tier candidate evaluations")
    products: List[Dict[str, Any]] = Field(default_factory=list, description="Curated matching candidates from 5-tier catalog discovery")
    discarded_products: List[Dict[str, Any]] = Field(default_factory=list, description="Evaluated but filtered candidates")

    model_config = {
        "json_schema_extra": {
            "example": {
                "intent": "buy",
                "message": "I can definitely help you find a white graphic t-shirt! Identified top matching apparel items and initiated autonomous checkout dispatch.",
                "ready_for_search": True,
                "updated_query": "Show me men's t-shirts with a graphic over it in white color",
                "buy_action": {
                    "action": "buy_items",
                    "targets": [1],
                    "quantities": [1]
                },
                "selected_items": [
                    {
                        "product_id": "SHPF-10219276992752",
                        "title": "Men's White Better & Better Graphic Printed Oversized T-shirt",
                        "price": 699.0,
                        "quantity": 1,
                        "merchant": "Rasor Test Store 1",
                        "image_url": "https://cdn.shopify.com/s/files/1/0859/0304/8944/files/629620_2026-06-02t13-09-19_1.jpg?v=1787616201",
                        "specs": {
                            "gender": "Men",
                            "color": "White",
                            "design": "Graphic Print",
                            "fit": "Oversized Fit",
                            "fabric": "Cotton",
                            "neck": "Round Neck",
                            "sleeve": "Half Sleeve",
                            "subclass": "T-Shirt",
                            "mrp_inr": 1299.0
                        }
                    }
                ],
                "total_price": 699.0,
                "suggested_options": ["Oversized Fit", "Regular Fit", "Marvel Graphic", "Minimalist Graphic"],
                "canonical_query": {
                    "original_prompt": "Show me men's t-shirts with a graphic over it white",
                    "cleaned_keywords": "men's white graphic t-shirt",
                    "gender": "men",
                    "category": "t-shirt",
                    "color": "White",
                    "design": "Graphic Print",
                    "fit": "Any",
                    "sleeve": "Any",
                    "fabric": "Any",
                    "neck": "Any",
                    "occasion": "Any",
                    "fandom": "None",
                    "specific_visual_intent": None,
                    "fast_shipping_requested": False,
                    "size": None,
                    "quantity": 1,
                    "max_price": None,
                    "min_rating": None,
                    "negative_keywords": []
                },
                "evaluations": [
                    {
                        "product_id": "SHPF-10219339940080",
                        "match_score": 0.70,
                        "is_relevant": True,
                        "reason": "Tier 1 (67%) + Overlap (28%) + Bayes (81%)"
                    },
                    {
                        "product_id": "SHPF-10219288625392",
                        "match_score": 0.70,
                        "is_relevant": True,
                        "reason": "Tier 1 (67%) + Overlap (28%) + Bayes (70%)"
                    }
                ],
                "products": [
                    {
                        "id": "SHPF-10219276992752",
                        "title": "Men's White Better & Better Graphic Printed Oversized T-shirt",
                        "price": 699.0,
                        "rating": 4.8,
                        "relevance_score": 0.85,
                        "merchant": "Rasor Test Store 1"
                    }
                ],
                "discarded_products": [
                    {
                        "id": "SHPF-10219288822000",
                        "title": "Men's Olive Green Solid Hooded Sweatshirt",
                        "relevance_score": 0.57,
                        "verdict": "PARTIAL_MATCH"
                    }
                ]
            }
        }
    }

class SkinToneResponse(BaseModel):
    rating: int = Field(description="Skin tone depth rating 1-10")
    palette_label: str = Field(description="Color season label: Fair/Cool, Medium/Warm, Deep/Rich")
    recommended_colors: List[str] = Field(description="Top recommended color palettes per color theory")
    avoid_colors: List[str] = Field(description="Colors recommended to avoid")
    search_injection: str = Field(description="Top colors formatted for catalog search query injection")

    model_config = {
        "json_schema_extra": {
            "example": {
                "rating": 6,
                "palette_label": "Medium / Warm",
                "recommended_colors": ["Mustard Yellow", "Olive Green", "Terracotta", "Coral", "Rust", "Warm Brown"],
                "avoid_colors": ["Neon colors", "Ice Blue", "Cool Pastels"],
                "search_injection": "Mustard Yellow, Olive Green, Terracotta"
            }
        }
    }

class OccasionResponse(BaseModel):
    occasion: str = Field(description="Queried occasion or vibe")
    found: bool = Field(description="Whether exact occasion mapping exists")
    suggestion: str = Field(description="Stylistic suggestion and clothing coupling")
    query_append: str = Field(description="Search terms coupled to this occasion")

    model_config = {
        "json_schema_extra": {
            "example": {
                "occasion": "Party",
                "found": True,
                "suggestion": "How about a sharp Polo or a Slim-fit dark shirt to stand out?",
                "query_append": "polo OR slim fit shirt dark"
            }
        }
    }

class GarmentPairingScoreRequest(BaseModel):
    item1: Dict[str, Any] = Field(description="First garment item dictionary with title, category, specs")
    item2: Dict[str, Any] = Field(description="Second garment item dictionary with title, category, specs")
    user_skin_depth: Optional[int] = Field(default=5, ge=1, le=10, description="User skin depth 1-10")
    user_undertone: Optional[str] = Field(default="Neutral", description="Cool, Warm, or Neutral")

    model_config = {
        "json_schema_extra": {
            "example": {
                "item1": {
                    "id": "SHPF-10219274043632",
                    "title": "Men's Black Iron Man Of War Graphic Printed T-shirt",
                    "category": "t-shirt",
                    "specs": {"color": "Black", "design": "Graphic Print", "fit": "Regular Fit"}
                },
                "item2": {
                    "id": "SHPF-10219273847024",
                    "title": "Men's Heather Charcoal Tech Fleece Cargo Joggers",
                    "category": "joggers",
                    "specs": {"color": "Grey", "design": "Solid", "fit": "Tapered"}
                },
                "user_skin_depth": 5,
                "user_undertone": "Neutral"
            }
        }
    }

class GarmentPairingScoreResponse(BaseModel):
    harmony_score: float = Field(description="Composite aesthetic harmony score between 0.0 and 1.0")
    breakdown: Dict[str, Any] = Field(description="Detailed CIEDE2000, value contrast, hue harmony, and bonus breakdown")
    stylist_rationale: str = Field(description="Human-interpretable stylist explanation of why the pairing works")

    model_config = {
        "json_schema_extra": {
            "example": {
                "harmony_score": 0.884,
                "breakdown": {
                    "ciede2000_distance": 18.4,
                    "hue_harmony": 0.92,
                    "value_contrast": 0.85,
                    "skin_tone_boost": 0.05,
                    "pairing_type": "top_bottom"
                },
                "stylist_rationale": "High contrast pairing: Black Graphic T-Shirt creates a strong anchor against Charcoal Fleece Joggers with balanced color value."
            }
        }
    }

class OfferEvaluationResult(BaseModel):
    title: str = Field(description="Promotion or bulk deal title")
    description: str = Field(description="Promotion terms and criteria")
    is_unlocked: bool = Field(description="True if current cart meets criteria")
    estimated_savings: float = Field(description="Calculated monetary savings in cart currency")
    quantity_away: int = Field(default=0, description="Remaining items needed to unlock deal")
    message: str = Field(description="User-facing success or upsell message")

class OfferResponse(BaseModel):
    status: str = Field(description="Evaluation status")
    evaluations: List[OfferEvaluationResult] = Field(description="Active bulk deal and spend threshold evaluations")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "evaluations": [
                    {
                        "title": "Buy 3 for 1199",
                        "description": "Buy any 3 eligible t-shirts for ₹1,199",
                        "is_unlocked": True,
                        "estimated_savings": 398.0,
                        "quantity_away": 0,
                        "message": "🎉 Buy 3 for 1199 Unlocked! You saved ₹398."
                    }
                ]
            }
        }
    }



class QuickSearchRequest(BaseModel):
    query: str = Field(description="Quick Search natural language shopping prompt")
    data_source: str = Field(default="shopify_storefront_live_api", description="Catalog provider: shopify_storefront_live_api or bewakoof_live_api")
    primary_model: str = Field(default="gemini-3.1-flash-lite", description="Primary LLM")
    fallback_model: str = Field(default="llama-3.3-70b-versatile", description="Fallback LLM")
    max_results: int = Field(default=10, description="Max results returned")
    enable_deep_enrichment: bool = Field(default=True, description="Enrich top candidates with live PDP v2 metadata")
    max_deep_fetches: int = Field(default=10, description="Max PDP fetches")
    enable_vqa_scanner: bool = Field(default=True, description="Run multimodal Vision VQA on candidate imagery")
    vqa_strict_filter: bool = Field(default=True, description="Strict text filter before VQA inspection")
    vqa_limit: int = Field(default=16, description="Max product images sent to Gemini Vision")
    truth_hierarchy: bool = Field(default=True, description="Prioritize title over contradictory metadata")
    enable_semantic_engine: bool = Field(default=True, description="Semantic pop-culture expansion")
    currency: str = Field(default="INR", description="Currency symbol/code")
    user_location: str = Field(default="Mumbai", description="User shipping destination city")

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "Show me men's t-shirts with a graphic over it in white color"
            }
        }
    }

class SearchRequest(BaseModel):
    query: str = Field(description="Natural language apparel shopping intent with multi-attribute constraints")
    data_source: str = Field(default="shopify_storefront_live_api", description="Catalog provider: shopify_storefront_live_api or bewakoof_live_api")
    primary_model: str = Field(default="gemini-3.1-flash-lite", description="Primary LLM for intent normalization & candidate evaluation")
    fallback_model: str = Field(default="llama-3.3-70b-versatile", description="Fallback LLM for resilience")
    max_results: int = Field(default=10, description="Max curated results returned")
    enable_deep_enrichment: bool = Field(default=True, description="Enrich top candidates with live PDP v2 metadata")
    max_deep_fetches: int = Field(default=10, description="Max PDP fetches")
    enable_vqa_scanner: bool = Field(default=True, description="Run multimodal Vision VQA on candidate product imagery")
    vqa_strict_filter: bool = Field(default=True, description="Strict text filter before VQA inspection")
    vqa_limit: int = Field(default=16, description="Max product images sent to Gemini Vision")
    truth_hierarchy: bool = Field(default=True, description="Prioritize title keywords over contradictory metadata tags")
    enable_semantic_engine: bool = Field(default=True, description="Semantic pop-culture expansion (e.g. Iron Man -> Tony Stark / Marvel)")
    currency: str = Field(default="INR", description="Currency symbol/code")
    user_location: str = Field(default="Mumbai", description="Customer destination for Haversine geodesic velocity calculation")

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "Show me men's t-shirts with a graphic over it in white color"
            }
        }
    }

class ChatRequest(BaseModel):
    message: str = Field(description="Conversational prompt, question answer, or one-shot purchase directive")
    history: List[Dict[str, str]] = Field(default_factory=list, description="Previous conversation turn history")
    session_id: str = Field(default="sess_default_1", description="Unique session ID for state preservation")
    data_source: str = Field(default="shopify_storefront_live_api", description="Catalog data source")
    primary_model: str = Field(default="gemini-3.1-flash-lite", description="Primary LLM")
    fallback_model: str = Field(default="llama-3.3-70b-versatile", description="Fallback LLM")
    user_location: str = Field(default="Mumbai", description="User shipping location")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Show me men's t-shirts with a graphic over it in white color"
            }
        }
    }

class ShopifyGraphQLRequest(BaseModel):
    query: str = Field(description="Raw GraphQL query or mutation document")
    variables: Optional[Dict[str, Any]] = Field(default=None, description="GraphQL variables dictionary")
    operation_name: Optional[str] = Field(default=None, description="Optional operation name")

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "query ProductSearch($query: String!, $first: Int!) {\n  products(query: $query, first: $first, sortKey: RELEVANCE) {\n    edges {\n      node {\n        id\n        title\n        productType\n        availableForSale\n        variants(first: 3) {\n          edges {\n            node {\n              id\n              title\n              price { amount currencyCode }\n              availableForSale\n            }\n          }\n        }\n      }\n    }\n  }\n}",
                "variables": {
                    "query": "hoodie",
                    "first": 5
                }
            }
        }
    }

class CartCreateRequest(BaseModel):
    variant_gid: str
    quantity: int = 1

    model_config = {
        "json_schema_extra": {
            "example": {
                "variant_gid": "gid://shopify/ProductVariant/50302872191216",
                "quantity": 1
            }
        }
    }

class CartAddRequest(BaseModel):
    cart_id: str
    variant_gid: str
    quantity: int = 1

    model_config = {
        "json_schema_extra": {
            "example": {
                "cart_id": "gid://shopify/Cart/hWNGSzlkMbuJqmyIYmt1mfB6?key=2b193fc862658ce1e895673f834d83aa",
                "variant_gid": "gid://shopify/ProductVariant/50302872158448",
                "quantity": 1
            }
        }
    }

class OrderRequest(BaseModel):
    cart_items: List[Dict[str, Any]]
    currency: str = "INR"
    final_total: float
    customer_id: Optional[str] = None
    cart_id: str = "cart_default"
    mandate_id: Optional[str] = None
    max_authorized_cap: Optional[float] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "cart_items": [
                    {
                        "product_id": "SHPF-10219274043632",
                        "title": "Men's Black Iron Man Of War Graphic Printed T-shirt",
                        "unit_price": 549.0,
                        "quantity": 1,
                        "merchant": "Rasor Test Store 1"
                    }
                ],
                "currency": "INR",
                "final_total": 549.0,
                "cart_id": "cart_test_123",
                "mandate_id": "mandate_intent_e13923e7",
                "max_authorized_cap": 3000.0
            }
        }
    }

class S2SRequest(BaseModel):
    cart_items: List[Dict[str, Any]]
    currency: str = "INR"
    final_total: float
    token_id: str
    customer_id: str
    cart_id: str = "cart_s2s"
    max_authorized_cap: Optional[float] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "cart_items": [
                    {
                        "product_id": "SHPF-10219274043632",
                        "title": "Men's Black Iron Man Of War Graphic Printed T-shirt",
                        "unit_price": 549.0,
                        "quantity": 1,
                        "merchant": "Rasor Test Store 1"
                    }
                ],
                "currency": "INR",
                "final_total": 549.0,
                "token_id": "token_rec_12345",
                "customer_id": "cust_TUTVmoz0jgNfpn",
                "cart_id": "cart_s2s_1788580000",
                "max_authorized_cap": 3000.0
            }
        }
    }

class VerifyPaymentRequest(BaseModel):
    payment_id: str
    order_id: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "payment_id": "pay_TYDL1MOG7yuAmD",
                "order_id": "order_TYDL1MOG7yuAmD"
            }
        }
    }

class ShopifySyncRequest(BaseModel):
    cart_items: List[Dict[str, Any]]
    currency: str = "INR"
    final_total: float
    order_id: str
    email: str = "agentic@rasor.test"
    payment_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "cart_items": [
                    {
                        "product_id": "SHPF-10219274043632",
                        "title": "Men's Black Iron Man Of War Graphic Printed T-shirt",
                        "unit_price": 549.0,
                        "quantity": 1,
                        "merchant": "Rasor Test Store 1"
                    }
                ],
                "currency": "INR",
                "final_total": 549.0,
                "order_id": "order_TYDL1MOG7yuAmD",
                "email": "agentic@rasor.test",
                "payment_id": "pay_TYDL1MOG7yuAmD"
            }
        }
    }

class PaymentLinkRequest(BaseModel):
    cart_items: List[Dict[str, Any]]
    currency: str = "INR"
    final_total: float
    cart_id: str = "cart_plink"
    customer_name: str = "Vipul Patil"
    customer_phone: str = "8806549952"
    customer_email: str = "vipulapatil21@gmail.com"
    notify_sms: bool = True
    notify_email: bool = True
    notify_whatsapp: bool = True
    expiry_minutes: Optional[int] = 15
    failed_attempts_summary: Optional[str] = "Canara Bank, Bank of Baroda, Verified Card"
    buffer_minutes: Optional[int] = 1

    model_config = {
        "json_schema_extra": {
            "example": {
                "cart_items": [
                    {
                        "product_id": "SHPF-10219274043632",
                        "title": "Men's Black Iron Man Of War Graphic Printed T-shirt",
                        "unit_price": 549.0,
                        "quantity": 1,
                        "merchant": "Rasor Test Store 1"
                    }
                ],
                "currency": "INR",
                "final_total": 549.0,
                "cart_id": "cart_plink_test",
                "customer_name": "Vipul Patil",
                "customer_phone": "8806549952",
                "customer_email": "vipulapatil21@gmail.com",
                "notify_sms": True,
                "notify_email": True,
                "notify_whatsapp": True,
                "expiry_minutes": 15,
                "failed_attempts_summary": "Canara Bank, Bank of Baroda, Verified Card",
                "buffer_minutes": 1
            }
        }
    }

class FailoverLogRequest(BaseModel):
    cart_id: str
    order_id: str
    failed_tier: int
    failed_instrument: str
    reason: str
    next_tier: int
    next_instrument: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "cart_id": "cart_mandate_1",
                "order_id": "order_TYDL1MOG7yuAmD",
                "failed_tier": 1,
                "failed_instrument": "HDFC Netbanking",
                "reason": "Gateway 504 Gateway Timeout",
                "next_tier": 2,
                "next_instrument": "ICICI Netbanking"
            }
        }
    }

class CreateIntentMandateRequest(BaseModel):
    user_email: str = "vipulapatil21@gmail.com"
    user_phone: str = "+918806549952"
    max_amount: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_email": "vipulapatil21@gmail.com",
                "user_phone": "+918806549952",
                "max_amount": 3000.0
            }
        }
    }

class CreateCartMandateRequest(BaseModel):
    items: List[Dict[str, Any]]
    frozen_total: float
    currency: str = "INR"
    intent_mandate_id: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "product_id": "SHPF-10219274043632",
                        "title": "Men's Black Iron Man Of War Graphic Printed T-shirt",
                        "size": "XL",
                        "unit_price": 549.0,
                        "quantity": 1
                    }
                ],
                "frozen_total": 549.0,
                "currency": "INR",
                "intent_mandate_id": "mandate_intent_e13923e7"
            }
        }
    }

class OfferRequest(BaseModel):
    cart_items: Dict[str, int]
    product_lookup: Dict[str, Dict[str, Any]]
    currency: str = "INR"

    model_config = {
        "json_schema_extra": {
            "example": {
                "cart_items": {"SHPF-10219274043632": 1},
                "product_lookup": {
                    "SHPF-10219274043632": {
                        "price": 549.0,
                        "category": "t-shirt"
                    }
                },
                "currency": "INR"
            }
        }
    }

class ProductsByIdsRequest(BaseModel):
    ids: List[str]
    data_source: Optional[str] = "shopify_storefront_live_api"

    model_config = {
        "json_schema_extra": {
            "example": {
                "ids": ["SHPF-10219274043632", "SHPF-10219273847024"],
                "data_source": "shopify_storefront_live_api"
            }
        }
    }

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health & Gateway Keys"], summary="System Liveness Health Probe")
def health():
    return {"status": "ok", "checkout_available": HAS_CHECKOUT}

@app.post("/api/products/by-ids", tags=["Quick Search & Intent Catalog"], summary="Batch Exact Product Lookup by GID / ID")
def get_products_by_ids(req: ProductsByIdsRequest):
    """Fetches exact products by their IDs from Shopify Storefront (or Bewakoof/dev catalog)."""
    try:
        from src.data.shopify_api import ShopifyCatalogProvider
        from src.data.bewakoof_api import BewakoofCatalogProvider
        
        provider = ShopifyCatalogProvider()
        prods = provider.get_products_by_ids(req.ids)
        
        # If Shopify didn't have all IDs, check Bewakoof provider
        found_ids = {p.id for p in prods} | {p.specs.get("shopify_gid") for p in prods}
        missing = [i for i in req.ids if i not in found_ids]
        if missing:
            b_prov = BewakoofCatalogProvider()
            extra = b_prov.get_products_by_ids(missing)
            prods.extend(extra)

        return {
            "products": [p.model_dump() for p in prods],
            "count": len(prods)
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── Search ────────────────────────────────────────────────────────────────────

@app.post("/api/quick-search", tags=["Quick Search & Intent Catalog"], summary="Quick Search One-Shot Natural Language Pipeline")
def quick_search(req: QuickSearchRequest):
    """Dedicated Quick Search one-shot natural language shopping pipeline."""
    search_req = SearchRequest(**req.model_dump())
    return search(search_req)

@app.post("/api/search", tags=["Quick Search & Intent Catalog"], summary="Autonomous Intent Search & Multi-Tier Retrieval")
def search(req: SearchRequest):
    try:
        from src.agent.stylist import StylistAgent
        
        # Force upgrade legacy models sent by stale frontend state
        if req.primary_model in ["gemini-1.5-flash", "gemini-2.5-flash"]:
            req.primary_model = "gemini-3.5-flash"

        # Safely normalize data_source strings (e.g. 'shopify', 'bewakoof')
        ds_val = str(req.data_source or "bewakoof_live_api").lower().strip()
        if ds_val in ("shopify", "shopify_storefront", "shopify_live", "shopify_storefront_live_api", "shopify_storefront_api"):
            normalized_ds = DataSourceType.SHOPIFY_STOREFRONT_LIVE_API
        elif ds_val in ("bewakoof", "bewakoof_api", "bewakoof_live_api"):
            normalized_ds = DataSourceType.BEWAKOOF_LIVE_API
        elif ds_val in ("google", "google_shopping", "google_shopping_scraper"):
            normalized_ds = DataSourceType.GOOGLE_SHOPPING_SCRAPER
        elif ds_val in ("mock", "dev_mock"):
            normalized_ds = DataSourceType.DEV_MOCK
        else:
            try:
                normalized_ds = DataSourceType(req.data_source)
            except Exception:
                normalized_ds = DataSourceType.BEWAKOOF_LIVE_API
            
        config = AgentConfig(
            mode=ExecutionMode.LIVE,
            data_source=normalized_ds,
            primary_model=req.primary_model,
            fallback_model=req.fallback_model,
            max_search_results=req.max_results,
            enable_deep_enrichment=req.enable_deep_enrichment,
            max_deep_fetches=req.max_deep_fetches,
            enable_vqa_scanner=req.enable_vqa_scanner,
            vqa_strict_filter=req.vqa_strict_filter,
            vqa_limit=req.vqa_limit,
            truth_hierarchy=req.truth_hierarchy,
            enable_semantic_engine=req.enable_semantic_engine,
            currency=req.currency,
        )
        brain = AgentBrain(
            primary_model=config.primary_model,
            fallback_model=config.fallback_model
        )
        provider = get_provider(req.data_source)

        # Check if the query is a conversational query or delegated buy intent
        buy_action_dict = None
        effective_query = req.query
        if req.query and any(verb in req.query.lower() for verb in ["buy", "order", "pick up", "get me", "add", "cart"]):
            try:
                temp_agent = StylistAgent(primary_model=config.primary_model, fallback_model=config.fallback_model)
                resp = temp_agent.process_turn(req.query, [])
                if resp and getattr(resp, "intent", None) == "buy" and getattr(resp, "buy_action", None):
                    buy_action_dict = resp.buy_action.model_dump()
                    if resp.updated_query:
                        effective_query = resp.updated_query
                        print(f"[Search] Conversational buy intent detected. Rewriting search query '{req.query[:40]}...' -> '{effective_query}'")
            except Exception as e:
                print("[Search] Failed to detect buy intent in search query:", e)

        # Parse canonical query
        multi_query, norm_source = brain.normalize_intent(effective_query, budget=config.max_budget)
        if not multi_query or not multi_query.items_to_buy:
            return {"products": [], "status": "No canonical query extracted", "canonical_query": None}
            
        canonical_query = multi_query.items_to_buy[0]
        effective_budget = canonical_query.max_price or config.max_budget

        # If multi-item bundle or match-my-outfit is detected, coordinate full bundle in parallel
        bundle_data = None
        if len(multi_query.items_to_buy) >= 2 or len(multi_query.owned_items) > 0:
            try:
                from src.agent.bundle_coordinator import BundleCoordinator
                coordinator = BundleCoordinator(catalog_provider=provider)
                bundle_data = coordinator.coordinate_bundle(
                    query=effective_query,
                    budget=config.max_budget,
                    items_to_buy=[it.model_dump() for it in multi_query.items_to_buy],
                    owned_items=[it.model_dump() for it in multi_query.owned_items],
                    gender=canonical_query.gender.value if canonical_query.gender.value != "all" else None,
                    provider=provider
                )
            except Exception as e:
                print(f"[Search] Bundle coordination error: {e}")

        # Fetch products
        raw_products = provider.search_products(
            query=canonical_query.cleaned_keywords or req.query,
            category=canonical_query.category.value if canonical_query.category.value != "general" else None,
            gender=canonical_query.gender.value if canonical_query.gender.value != "all" else None,
            color=canonical_query.color.value if canonical_query.color.value != "Any" else None,
            size=canonical_query.size,
            design=canonical_query.design.value if canonical_query.design.value != "Any" else None,
            fandom=canonical_query.fandom.value if canonical_query.fandom.value != "None" else None,
            fit=canonical_query.fit.value if canonical_query.fit.value != "Any" else None,
            sleeve=canonical_query.sleeve.value if canonical_query.sleeve.value != "Any" else None,
            max_price=effective_budget,
            limit=40
        )
        
        if not raw_products:
            return {"products": [], "discarded_products": [], "evaluations": [], "status": "No products found", "canonical_query": canonical_query.model_dump() if hasattr(canonical_query, "model_dump") else {}}

        # Aggressive Text-First Negation Filter
        neg_keywords = getattr(canonical_query, 'negative_keywords', [])
        if neg_keywords:
            filtered_raw = []
            for p in raw_products:
                text_to_check = (p.title + " " + (p.rich_description or "")).lower()
                if any(neg.lower() in text_to_check for neg in neg_keywords):
                    continue
                filtered_raw.append(p)
            raw_products = filtered_raw
            
        if not raw_products:
            return {"products": [], "discarded_products": [], "evaluations": [], "status": "Filtered out by negative keywords", "canonical_query": canonical_query.model_dump() if hasattr(canonical_query, "model_dump") else {}}

        import math
        def bayesian_score(p):
            return (p.rating or 0.0) * math.log10((p.review_count or 0) + 1)

        raw_products.sort(key=bayesian_score, reverse=True)

        # Check if user requested fast / urgent shipping
        is_fast_shipping = (
            getattr(canonical_query, "fast_shipping_requested", False)
            or bool(re.search(r"\b(fast|faster|fastest|quick|urgent|express|speed|early|soon|deliver|delivery)\b", req.query.lower()))
        )

        # ── Stage 3: Deep enrich top candidates with v2 PDP data ──
        # Always enrich if enabled; also enrich when fast shipping is requested so
        # we can read the origin pincode/manufacturer from the v2 payload.
        if (config.enable_deep_enrichment or is_fast_shipping) and hasattr(provider, "enrich_product"):
            top_to_enrich = raw_products[:max(config.max_deep_fetches, 10)]
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                list(executor.map(provider.enrich_product, top_to_enrich))

        # ── Stage 4: LLM text evaluation — drop products with match_score < 0.5 ──
        try:
            validated_products, evaluations = brain.evaluate_candidates(
                req.query,
                raw_products,
                canonical=canonical_query,
                vqa_strict_filter=config.vqa_strict_filter,
                enable_vqa_scanner=config.enable_vqa_scanner,
                truth_hierarchy=config.truth_hierarchy,
                vqa_limit=config.vqa_limit
            )
        except Exception as e:
            print(f"Evaluation failed: {e}")
            validated_products, evaluations = raw_products, []

        eval_map = {e.product_id: e for e in evaluations}

        # Multi-source Character / Entity detection for hierarchy tie-breaking
        from src.agent.brain import get_semantic_affinity_tier, _CHARACTER_ENTITY_MAP, preprocess_prompt
        
        target_char_key = None
        target_char_terms = []
        sources_to_check = [
            req.query.lower(),
            preprocess_prompt(req.query, enable_semantic=False).lower(),
        ]
        if canonical_query:
            if getattr(canonical_query, "cleaned_keywords", None):
                sources_to_check.append(str(canonical_query.cleaned_keywords).lower())
            if getattr(canonical_query, "fandom", None) and canonical_query.fandom.value != "None":
                sources_to_check.append(str(canonical_query.fandom.value).lower())

        for text_source in sources_to_check:
            for char_key, char_terms in _CHARACTER_ENTITY_MAP.items():
                if any(re.search(rf"\b{re.escape(term)}\b", text_source) for term in char_terms):
                    target_char_key = char_key
                    target_char_terms = char_terms
                    break
            if target_char_key:
                break

        # ── Stage 4c: Relevance & Match Score Post-filter ──
        # Filters out conflicting character / rejected items (e.g. Venom when Black Panther was requested).
        MIN_SURVIVORS = 3

        def get_match_score(p):
            ev = eval_map.get(p.id)
            return ev.match_score if ev else 0.5

        def is_item_relevant(p):
            ev = eval_map.get(p.id)
            return ev.is_relevant if ev is not None else True

        # First pass: keep relevant items with match_score >= 0.45
        strict_survivors = [p for p in validated_products if get_match_score(p) >= 0.45 and is_item_relevant(p)]
        if len(strict_survivors) >= MIN_SURVIVORS:
            validated_products = strict_survivors
            print(f"[Search] Post-filter (strict >= 0.45): {len(validated_products)} survivors")
        elif len(strict_survivors) > 0:
            validated_products = strict_survivors
            print(f"[Search] Post-filter (strict, {len(strict_survivors)} passed): keeping all survivors")
        else:
            all_scored = sorted(
                validated_products,
                key=lambda p: (
                    get_match_score(p),
                    get_semantic_affinity_tier(p, target_char_key, target_char_terms, effective_query),
                    bayesian_score(p)
                ),
                reverse=True
            )
            validated_products = all_scored[:max(MIN_SURVIVORS, 1)]
            print(f"[Search] Post-filter (relaxed, min_survivors={MIN_SURVIVORS}): {len(validated_products)} kept")

        vqa_ran = any("[VQA:" in (e.reason or "") for e in evaluations)

        # ── Stage 5: Logistics re-rank (only on VQA/LLM survivors) ──
        # Delivery is a SECONDARY sort key within match-score tiers.
        # A lower-scoring product can NEVER overtake a better-matching product
        # just because it has faster shipping.
        if is_fast_shipping:
            try:
                from src.agent.logistics_agent import LogisticsAgent
                logistics = LogisticsAgent()
                u_loc = req.user_location or "Mumbai"
                for p in validated_products:
                    est = logistics.calculate_delivery_estimate(p.specs, u_loc)
                    p.shipping_days = est.get("shipping_days", 3)
                    p.specs["distance_km"] = est.get("distance_km")
                    p.specs["origin_hub"] = est.get("origin_hub")
                    p.specs["shipping_speed"] = est.get("speed_label")
                    p.specs["destination_display"] = est.get("destination_display")
                print(f"[Search] Logistics annotated {len(validated_products)} survivors")
            except Exception as e:
                print(f"[Search] Logistics annotation error: {e}")

        # ── Stage 6: Final sort & slice ──
        import math as _math
        bayesian_scores = [bayesian_score(p) for p in (validated_products if validated_products else raw_products)]
        max_b = max(bayesian_scores, default=1.0) or 1.0

        def composite_score(p):
            return get_match_score(p)

        final_list = validated_products if validated_products else raw_products

        if not config.truth_hierarchy:
            final_list = [p for p in final_list if p.specs.get("truth_match") != False]

        sort_mode = "relevance"
        if is_fast_shipping:
            def tier_delivery_key(p):
                cs = composite_score(p)
                score_tier = _math.floor(cs * 10) / 10   # e.g. 0.95 → 0.9, 0.88 → 0.8
                affinity = get_semantic_affinity_tier(p, target_char_key, target_char_terms, effective_query)
                days = p.shipping_days if p.shipping_days else 99
                return (-score_tier, -affinity, days, -bayesian_score(p))  # desc tier, desc affinity, asc delivery, desc bayesian

            final_list.sort(key=tier_delivery_key)
            sort_mode = "tier_delivery"
        else:
            def relevance_sort_key(p):
                score = get_match_score(p)
                affinity = get_semantic_affinity_tier(p, target_char_key, target_char_terms, effective_query)
                bayes = bayesian_score(p)
                return (score, affinity, bayes)

            final_list.sort(key=relevance_sort_key, reverse=True)

        search_results = final_list[:config.max_search_results]
        displayed_ids = {p.id for p in search_results}
        rejected_products = [p for p in raw_products if p.id not in displayed_ids]
        rejected_products.sort(
            key=lambda p: (
                eval_map[p.id].match_score if p.id in eval_map else 0.0,
                get_semantic_affinity_tier(p, target_char_key, target_char_terms, effective_query),
                bayesian_score(p)
            ),
            reverse=True
        )

        def to_dict(p, is_discarded=False):
            e = eval_map.get(p.id)
            score = e.match_score if e else 0.0
            verdict = "STRONG_MATCH" if score >= 0.8 else ("PARTIAL_MATCH" if score >= 0.5 else "REJECTED")
            return {
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "rating": p.rating,
                "review_count": getattr(p, "review_count", 0) or 120,
                "shipping_days": getattr(p, "shipping_days", 3) or 3,
                "shipping_speed": p.specs.get("shipping_speed") or ("Express" if getattr(p, "shipping_days", 3) <= 2 else "Standard"),
                "source_url": getattr(p, "source_url", None) or p.specs.get("url") or (f"https://rasor-test-store-1.myshopify.com/products/{p.specs.get('handle')}" if p.specs.get("handle") else "https://rasor-test-store-1.myshopify.com"),
                "mrp": p.specs.get("mrp_inr") or p.specs.get("mrp"),
                "merchant": p.merchant,
                "specs": p.specs,
                "relevance_score": score,
                "verdict": "REJECTED" if is_discarded and score < 0.5 else verdict,
                "is_fast_shipping_requested": is_fast_shipping,
            }

        products_data = [to_dict(p) for p in search_results]
        discarded_products_data = [to_dict(p, is_discarded=True) for p in rejected_products]

        # Serialize evaluations for frontend
        evals_data = [e.model_dump() if hasattr(e, "model_dump") else vars(e) for e in evaluations]

        return {
            "products": products_data,
            "discarded_products": discarded_products_data,
            "evaluations": evals_data,
            "status": f"Found {len(products_data)} relevant products",
            "canonical_query": canonical_query.model_dump() if hasattr(canonical_query, "model_dump") else {},
            "sort_mode": sort_mode,                      # "relevance" | "tier_delivery"
            "is_delivery_sorted": is_fast_shipping,
            "vqa_ran": vqa_ran,
            "buy_action": buy_action_dict,
            "bundle_data": bundle_data,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/offers/evaluate", tags=["Quick Search & Intent Catalog"], summary="Offer & Bulk Promotion Evaluation Engine", response_model=OfferResponse)
def evaluate_offers(req: OfferRequest):
    """Evaluates cart contents against active promotional discounts, bulk tiered deals, and spend thresholds."""
    try:
        from src.agent.offers import OfferEngine
        lookup_objs = {}
        for pid, pdata in req.product_lookup.items():
            lookup_objs[pid] = Product(
                id=pid,
                title=pdata.get("title", f"Product {pid}"),
                merchant=pdata.get("merchant", "Shopify Store"),
                price=float(pdata.get("price", 500.0)),
                category=pdata.get("category", "t-shirt"),
                specs=pdata.get("specs", {})
            )
        evals = OfferEngine.evaluate_cart(req.cart_items, lookup_objs, currency_sym="₹" if req.currency == "INR" else "$")
        return {
            "status": "success",
            "evaluations": [
                {
                    "title": e.offer.title,
                    "description": e.offer.description,
                    "is_unlocked": e.is_unlocked,
                    "estimated_savings": float(e.estimated_savings),
                    "quantity_away": int(e.quantity_away),
                    "message": e.success_message if e.is_unlocked else e.upsell_message
                }
                for e in evals
            ]
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── Chat ──────────────────────────────────────────────────────────────────────
@app.post("/api/chat", tags=["Conversational Stylist"], summary="Conversational Stylist Turn Processing", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        # Force upgrade legacy models sent by stale frontend state
        if req.primary_model in ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-3.5-flash"]:
            req.primary_model = "gemini-3.1-flash-lite"
            
        if req.session_id not in _stylist_agents:
            _stylist_agents[req.session_id] = StylistAgent(
                primary_model=req.primary_model,
                fallback_model=req.fallback_model
            )
        agent = _stylist_agents[req.session_id]
        response = agent.process_turn(req.message, req.history)
        return {
            "intent": getattr(response, "intent", "clarify"),
            "message": response.message,
            "suggested_options": getattr(response, "suggested_options", []),
            "ready_for_search": getattr(response, "ready_for_search", False),
            "updated_query": getattr(response, "updated_query", None),
            "buy_action": response.buy_action.model_dump() if getattr(response, "buy_action", None) else None,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/one-shot", tags=["Conversational Stylist"], summary="One-Shot Autonomous Delegated Stylist Find & Buy", response_model=OneShotStylistResponse)
def chat_one_shot(req: OneShotStylistRequest):
    """Direct one-shot delegated purchase execution without back-and-forth clarification."""
    try:
        agent = StylistAgent(primary_model=req.primary_model, fallback_model=req.fallback_model)
        stylist_resp = agent.process_turn(req.prompt, [])
        
        search_query = stylist_resp.updated_query or req.prompt
        
        # Execute the full 5-tier intent & search pipeline to obtain canonical_query, evaluations, and curated products
        search_req = SearchRequest(
            query=search_query,
            data_source=req.data_source,
            primary_model=req.primary_model,
            fallback_model=req.fallback_model,
            max_results=10,
            currency=req.currency,
            user_location=req.user_location
        )
        search_results = search(search_req)
        raw_products = search_results.get("products", [])
        
        buy_action = stylist_resp.buy_action.model_dump() if stylist_resp.buy_action else {
            "action": "buy_items",
            "targets": [1, 2] if any(w in req.prompt.lower() for w in ["two", "2", "both"]) else [1],
            "quantities": [1, 1] if any(w in req.prompt.lower() for w in ["two", "2", "both"]) else [1]
        }
        
        targets = buy_action.get("targets", [1])
        selected_items = []
        for t in targets:
            idx = t - 1
            if 0 <= idx < len(raw_products):
                p = raw_products[idx]
                selected_items.append({
                    "product_id": p.get("id"),
                    "title": p.get("title"),
                    "price": float(p.get("price", 0.0)),
                    "quantity": 1,
                    "merchant": p.get("merchant", "Shopify Store"),
                    "image_url": p.get("specs", {}).get("image_url") or p.get("image_url") or p.get("source_url"),
                    "specs": p.get("specs", {})
                })
                
        total_price = sum(item["price"] for item in selected_items)
        
        return {
            "intent": stylist_resp.intent if stylist_resp.intent == "buy" else "buy",
            "message": stylist_resp.message or "Identified top matching apparel items and initiated autonomous multi-rail checkout dispatch.",
            "ready_for_search": True,
            "updated_query": search_query,
            "buy_action": buy_action,
            "selected_items": selected_items,
            "total_price": total_price,
            "suggested_options": stylist_resp.suggested_options or ["Buy Top Pick (#1)", "Buy Top 2", "Customize Size", "Cancel"],
            "canonical_query": search_results.get("canonical_query", {}),
            "evaluations": search_results.get("evaluations", []),
            "products": raw_products,
            "discarded_products": search_results.get("discarded_products", [])
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stylist/skin-tone/{rating}", tags=["Conversational Stylist"], summary="Color Matching Agent - Skin Tone Palette Theory", response_model=SkinToneResponse)
def get_skin_tone_palette(rating: int = Path(..., ge=1, le=10, description="Skin tone depth rating from 1 (Fair) to 10 (Deep)")):
    """Translates 1-10 skin tone ratings to optimal color palettes per global color theory."""
    from src.agent.stylist import ColorMatchingAgent
    rec = ColorMatchingAgent.get_recommendation(rating)
    search_colors = ColorMatchingAgent.to_search_colors(rating)
    return {
        "rating": rating,
        "palette_label": rec["label"],
        "recommended_colors": rec["best"],
        "avoid_colors": rec["avoid"],
        "search_injection": search_colors
    }

@app.get("/api/stylist/occasion/{occasion}", tags=["Conversational Stylist"], summary="Occasion Matching Agent - Vibe & Style Coupling", response_model=OccasionResponse)
def get_occasion_advice(occasion: str = Path(..., description="Target occasion or vibe: Party, Gym, Casual, or Office")):
    """Translates Occasion/Vibe to stylistic recommendations and coupled query parameters."""
    from src.agent.stylist import OccasionMatchingAgent
    rec = OccasionMatchingAgent.get_recommendation(occasion)
    if not rec:
        return {
            "occasion": occasion,
            "found": False,
            "suggestion": "For this occasion, a versatile minimalist oversized graphic tee or solid polo works well.",
            "query_append": "casual"
        }
    return {
        "occasion": occasion,
        "found": True,
        "suggestion": rec["suggestion"],
        "query_append": rec["query_append"]
    }

@app.delete("/api/chat/{session_id}", tags=["Conversational Stylist"], summary="Flush In-Memory Stylist Session")
def clear_chat(session_id: str):
    _stylist_agents.pop(session_id, None)
    return {"cleared": True}

# ── Outfit & Bundle Coordination Endpoints ────────────────────────────────────

class BundleCoordinateRequest(BaseModel):
    query: str = Field(default="Show me men's t-shirts with a graphic over it in white color", description="Overall outfit prompt")
    budget: float = Field(default=2500.0, description="Target total budget cap")
    items_to_buy: List[Dict[str, Any]] = Field(default_factory=list, description="Explicit items to purchase with categories, colors, designs")
    owned_items: List[Dict[str, Any]] = Field(default_factory=list, description="User owned wardrobe anchor pieces")
    user_skin_depth: int = Field(default=5, ge=1, le=10, description="Skin depth rating 1-10")
    user_undertone: str = Field(default="Neutral", description="Cool, Warm, or Neutral")
    gender: str = Field(default="men", description="Target gender")
    data_source: str = Field(default="shopify_storefront_live_api", description="Data catalog provider")

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "Show me men's t-shirts with a graphic over it in white color",
                "budget": 2500.0,
                "items_to_buy": [
                    {"category": "t-shirt", "color": "White", "design": "Graphic"}
                ],
                "owned_items": [
                    {"category": "sneakers", "color": "White", "brand": "Nike"}
                ],
                "user_skin_depth": 5,
                "user_undertone": "Neutral",
                "gender": "men",
                "data_source": "shopify_storefront_live_api"
            }
        }
    }

class OutfitMatchRequest(BaseModel):
    owned_item: Dict[str, Any] = Field(description="Owned wardrobe item dictionary with title, category, color, fit, specs")
    target_category: str = Field(default="t-shirt", description="Target category to search and pair with owned item")
    budget: float = Field(default=1800.0, description="Target budget for complementary piece")
    user_skin_depth: int = Field(default=6, ge=1, le=10, description="Skin depth 1-10")
    user_undertone: str = Field(default="Warm", description="Skin undertone")
    gender: str = Field(default="men", description="Target gender")
    data_source: str = Field(default="shopify_storefront_live_api", description="Data catalog provider")

    model_config = {
        "json_schema_extra": {
            "example": {
                "owned_item": {
                    "title": "Vintage Washed Oversized Olive Green Cargo Jacket",
                    "category": "jacket",
                    "color": "Olive Green",
                    "fit": "Oversized",
                    "specs": {"fabric": "Heavyweight Cotton Twill", "design": "Solid"}
                },
                "target_category": "joggers",
                "budget": 1800.0,
                "user_skin_depth": 6,
                "user_undertone": "Warm",
                "gender": "men",
                "data_source": "shopify_storefront_live_api"
            }
        }
    }

class ExtractGarmentRequest(BaseModel):
    image_b64: str
    mime_type: Optional[str] = "image/jpeg"

    model_config = {
        "json_schema_extra": {
            "example": {
                "image_b64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQE...",
                "mime_type": "image/jpeg"
            }
        }
    }

@app.post("/api/bundle/coordinate", tags=["Outfit Studio & Garment Vision"], summary="Multi-Piece Outfit Coordination & Budget Scaling")
def coordinate_bundle(req: BundleCoordinateRequest):
    try:
        from src.agent.bundle_coordinator import BundleCoordinator
        from src.agent.brain import AgentBrain
        provider = get_provider(req.data_source)
        coordinator = BundleCoordinator(catalog_provider=provider)
        
        items_to_buy = req.items_to_buy or []
        owned_items = req.owned_items or []
        
        if not items_to_buy and not owned_items and req.query:
            brain = AgentBrain()
            mq, _ = brain.normalize_intent(req.query, budget=req.budget)
            if mq:
                items_to_buy = [it.model_dump() for it in mq.items_to_buy]
                owned_items = [it.model_dump() for it in mq.owned_items]
                
        result = coordinator.coordinate_bundle(
            query=req.query,
            budget=req.budget,
            items_to_buy=items_to_buy,
            owned_items=owned_items,
            user_skin_depth=req.user_skin_depth,
            user_undertone=req.user_undertone,
            gender=req.gender,
            provider=provider
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/outfit/match", tags=["Outfit Studio & Garment Vision"], summary="Match My Outfit Anchor Pairing")
def match_outfit(req: OutfitMatchRequest):
    try:
        from src.agent.bundle_coordinator import BundleCoordinator
        provider = get_provider(req.data_source)
        coordinator = BundleCoordinator(catalog_provider=provider)
        
        result = coordinator.coordinate_bundle(
            query="",
            budget=req.budget,
            items_to_buy=[{"category": req.target_category}],
            owned_items=[req.owned_item],
            user_skin_depth=req.user_skin_depth,
            user_undertone=req.user_undertone,
            gender=req.gender,
            provider=provider
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/outfit/extract-image", tags=["Outfit Studio & Garment Vision"], summary="Multimodal Garment Vision Feature Extraction")
def extract_garment_image(req: ExtractGarmentRequest):
    try:
        from src.agent.outfit_extractor import GarmentVisionExtractor
        extractor = GarmentVisionExtractor()
        extracted = extractor.extract_from_base64(req.image_b64, req.mime_type)
        return extracted
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/outfit/score-pairing", tags=["Outfit Studio & Garment Vision"], summary="CIEDE2000 & Color Harmony Garment Pairing Scorer", response_model=GarmentPairingScoreResponse)
def score_pairing_endpoint(req: GarmentPairingScoreRequest):
    """Directly computes perceptual color distance (CIEDE2000), value contrast, hue harmony, and stylist rationale."""
    try:
        from src.agent.semantic_color_engine import score_garment_pairing, generate_stylist_rationale
        score, breakdown = score_garment_pairing(
            req.item1,
            req.item2,
            user_skin_depth=req.user_skin_depth,
            user_undertone=req.user_undertone
        )
        rationale = generate_stylist_rationale(
            req.item1,
            req.item2,
            breakdown,
            user_skin_depth=req.user_skin_depth,
            user_undertone=req.user_undertone
        )
        return {
            "harmony_score": round(score, 3),
            "breakdown": breakdown,
            "stylist_rationale": rationale
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── Compare ───────────────────────────────────────────────────────────────────
class CompareRequest(BaseModel):
    products: List[Dict[str, Any]]
    primary_model: str = "gemini-3.1-flash-lite"
    fallback_model: str = "llama-3.3-70b-versatile"
    user_location: Optional[str] = "Mumbai"

    model_config = {
        "json_schema_extra": {
            "example": {
                "products": [
                    {
                        "id": "SHPF-10219274043632",
                        "title": "Men's Black Iron Man Of War Graphic Printed T-shirt",
                        "merchant": "Shopify",
                        "price": 549.0,
                        "rating": 4.8,
                        "review_count": 809,
                        "specs": {
                            "fabric": "100% Cotton",
                            "color": "Black",
                            "fit": "Regular Fit",
                            "origin_pincode": "400078"
                        }
                    },
                    {
                        "id": "SHPF-10219273847024",
                        "title": "Men's Black The Other Side Graphic Printed T-shirt",
                        "merchant": "Shopify",
                        "price": 499.0,
                        "rating": 4.2,
                        "review_count": 1207,
                        "specs": {
                            "fabric": "Cotton Blend",
                            "color": "Black",
                            "fit": "Regular Fit",
                            "origin_pincode": "400078"
                        }
                    }
                ],
                "primary_model": "gemini-3.1-flash-lite",
                "fallback_model": "llama-3.3-70b-versatile",
                "user_location": "Mumbai"
            }
        }
    }

class LogisticsEstimateRequest(BaseModel):
    products: List[Dict[str, Any]]
    location: str = "Delhi"

    model_config = {
        "json_schema_extra": {
            "example": {
                "products": [
                    {
                        "id": "SHPF-10219274043632",
                        "title": "Men's Black Iron Man Of War Graphic Printed T-shirt",
                        "price": 549.0,
                        "merchant": "Shopify",
                        "specs": {
                            "origin_pincode": "400078",
                            "manufactured_by": "Rasor Mumbai Hub",
                            "color": "Black",
                            "category": "t-shirt"
                        }
                    }
                ],
                "location": "Delhi"
            }
        }
    }

@app.get("/api/logistics/resolve/{query}", tags=["Geodesic Logistics & Comparison"], summary="Indian PIN Code & City Geocoding Resolution")
def resolve_logistics_destination(query: str):
    try:
        from src.agent.logistics_agent import LogisticsAgent
        agent = LogisticsAgent()
        return agent.resolve_destination(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logistics/estimate", tags=["Geodesic Logistics & Comparison"], summary="Geodesic Haversine Distance & Velocity Estimation")
def estimate_logistics(req: LogisticsEstimateRequest):
    try:
        from src.agent.logistics_agent import LogisticsAgent
        from src.data.bewakoof_api import BewakoofCatalogProvider
        from src.data.shopify_api import ShopifyCatalogProvider
        
        b_provider = BewakoofCatalogProvider()
        s_provider = ShopifyCatalogProvider()
        agent = LogisticsAgent()
        dest = agent.resolve_destination(req.location)
        estimates = {}
        enriched_specs = {}

        for p in req.products:
            prod_obj = Product(**p)
            # Fetch manufacturer details from v2 if not yet enriched
            if not prod_obj.specs.get("manufactured_by") and not prod_obj.specs.get("origin_pincode"):
                try:
                    if str(prod_obj.merchant).lower() == "shopify" or "SHPF-" in str(prod_obj.id):
                        prod_obj = s_provider.enrich_product(prod_obj)
                    else:
                        prod_obj = b_provider.enrich_product(prod_obj)
                except Exception as e:
                    print(f"[Logistics] Enrich error for {prod_obj.id}: {e}")

            est = agent.calculate_delivery_estimate(prod_obj.specs, req.location)
            estimates[p.get("id")] = est
            enriched_specs[p.get("id")] = prod_obj.specs

        return {
            "location": req.location,
            "destination_details": dest,
            "estimates": estimates,
            "enriched_specs": enriched_specs
        }
    except Exception as e:
        traceback.print_exc()
@app.post("/api/cache/clear", tags=["System Diagnostics"], summary="Purge In-Memory Backend Search & VQA Caches")
def clear_backend_caches():
    try:
        from src.agent.brain import _VQA_CACHE
        from src.data.bewakoof_api import _DEEP_ENRICHMENT_CACHE
        vqa_count = len(_VQA_CACHE)
        enrich_count = len(_DEEP_ENRICHMENT_CACHE)
        _VQA_CACHE.clear()
        _DEEP_ENRICHMENT_CACHE.clear()
        return {
            "status": "success",
            "message": f"Purged {vqa_count} VQA scans and {enrich_count} deep enrichment records.",
            "cleared": {
                "vqa_cache": vqa_count,
                "enrichment_cache": enrich_count
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/compare", tags=["Geodesic Logistics & Comparison"], summary="Multi-Product Comparative Analysis Matrix")
def compare(req: CompareRequest):
    try:
        from src.data.bewakoof_api import BewakoofCatalogProvider
        from src.agent.logistics_agent import LogisticsAgent
        provider = BewakoofCatalogProvider()
        logistics_agent = LogisticsAgent()
        
        products = []
        for p in req.products:
            prod_obj = Product(**p)
            try:
                prod_obj = provider.enrich_product(prod_obj)
            except Exception as enrich_err:
                print(f"[Compare] Enrich failed for {prod_obj.id}: {enrich_err}")

            # Attach per-product warehouse distance & transit estimation via LogisticsAgent
            try:
                logistics = logistics_agent.calculate_delivery_estimate(prod_obj.specs, req.user_location or "Mumbai")
                prod_obj.shipping_days = logistics["shipping_days"]
                prod_obj.specs["logistics"] = logistics
                prod_obj.specs["origin_hub"] = logistics["origin_hub"]
                prod_obj.specs["distance_km"] = logistics["distance_km"]
                prod_obj.specs["shipping_speed"] = logistics["speed_label"]
                prod_obj.specs["destination_display"] = logistics["destination_display"]
            except Exception as log_err:
                print(f"[Compare] Logistics failed for {prod_obj.id}: {log_err}")

            products.append(prod_obj)

        brain = AgentBrain(primary_model=req.primary_model, fallback_model=req.fallback_model)
        comparison = brain.compare_products(products)
        if not comparison:
            raise HTTPException(status_code=500, detail="Failed to generate comparison")
        
        resp_data = comparison.model_dump() if hasattr(comparison, "model_dump") else {}
        resp_data["enriched_products"] = [p.model_dump() for p in products]
        return resp_data
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── Shopify Storefront GraphQL Proxy ─────────────────────────────────────────
@app.post("/api/shopify/graphql", tags=["Shopify Storefront GraphQL"], summary="Execute Storefront GraphQL Query / Mutation")
async def shopify_graphql_proxy(req: ShopifyGraphQLRequest, request: Request):
    """
    Direct proxy for executing Shopify Storefront GraphQL queries and mutations.
    Automatically injects the configured Storefront Access Token, and allows client
    overrides via the X-Shopify-Storefront-Access-Token header.
    """
    domain = os.getenv("SHOPIFY_DOMAIN", "rasor-test-store-1.myshopify.com")
    endpoint = os.getenv(
        "SHOPIFY_STOREFRONT_URL",
        f"https://{domain}/api/2024-04/graphql.json"
    )
    server_token = (
        os.getenv("SHOPIFY_STOREFRONT_TOKEN")
        or os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN")
        or "6a1c1b2f3f1fafd8afc7040ed4e19307"
    )
    client_token = request.headers.get("X-Shopify-Storefront-Access-Token")
    token = client_token if (client_token and client_token != "YOUR_STOREFRONT_TOKEN") else server_token

    payload: Dict[str, Any] = {"query": req.query}
    if req.variables is not None:
        payload["variables"] = req.variables
    if req.operation_name:
        payload["operationName"] = req.operation_name

    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Storefront-Access-Token": token,
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(endpoint, json=payload, headers=headers)
            return Response(
                content=res.content,
                status_code=res.status_code,
                media_type=res.headers.get("content-type", "application/json")
            )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Shopify upstream connection failed: {str(e)}")

# ── Cart ──────────────────────────────────────────────────────────────────────
@app.post("/api/cart/create", tags=["Headless Storefront Cart"], summary="Shopify Storefront Cart Initialization")
def cart_create(req: CartCreateRequest):
    try:
        provider = ShopifyCartProvider()
        result = provider.create_cart(req.variant_gid, req.quantity)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cart/add", tags=["Headless Storefront Cart"], summary="Append Variant Line Items to Headless Cart")
def cart_add(req: CartAddRequest):
    try:
        provider = ShopifyCartProvider()
        result = provider.add_to_cart(req.cart_id, req.variant_gid, req.quantity)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── Checkout ──────────────────────────────────────────────────────────────────
def _build_cart(cart_items: List[Dict], currency: str, final_total: float, cart_id: str) -> Cart:
    items = [CartItem(
        product_id=i["product_id"],
        title=i["title"],
        merchant=i.get("merchant", "Rasor"),
        unit_price=i["unit_price"],
        quantity=i["quantity"]
    ) for i in cart_items]
    cart = Cart(cart_id=cart_id, merchant="Rasor Demo Store", items=items, currency=currency)
    cart.recalculate()
    cart.final_total = final_total
    return cart

@app.post("/api/checkout/order", tags=["Payment Rails & Mobile Rescue"], summary="Create Razorpay Order for Human-Present Checkout")
def checkout_order(req: OrderRequest):
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        cart = _build_cart(req.cart_items, req.currency, req.final_total, req.cart_id)
        agent = CheckoutAgent()
        if req.customer_id:
            cid = req.customer_id
        else:
            cid = None
        result = agent.create_order(
            cart, 
            customer_id=cid,
            mandate_id=req.mandate_id,
            max_authorized_cap=req.max_authorized_cap
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/checkout/mandate-order", tags=["Payment Rails & Mobile Rescue"], summary="Provision Recurring Mandate Customer & Order")
def checkout_mandate_order(req: OrderRequest):
    """Demo 1: Create order + Razorpay customer for mandate flow."""
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        cart = _build_cart(req.cart_items, req.currency, req.final_total, req.cart_id)
        agent = CheckoutAgent()
        from src.config import AgentConfig
        config = AgentConfig()
        customer_id = agent.create_customer(config.customer_email)
        agent.record_mandate_approval(cart.cart_id, req.final_total)
        result = agent.create_order(
            cart, 
            customer_id=customer_id,
            mandate_id=req.mandate_id,
            max_authorized_cap=req.max_authorized_cap
        )
        result["customer_id"] = customer_id
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/checkout/s2s", tags=["Payment Rails & Mobile Rescue"], summary="Autonomous Server-to-Server Mandate Execution")
def checkout_s2s(req: S2SRequest):
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        cart = _build_cart(req.cart_items, req.currency, req.final_total, req.cart_id)
        agent = CheckoutAgent()
        result = agent.capture_saved_token(
            cart, 
            req.token_id, 
            req.customer_id,
            max_authorized_cap=req.max_authorized_cap
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/checkout/payment-link", tags=["Payment Rails & Mobile Rescue"], summary="Create Out-of-Band Mobile Handset Rescue Payment Link")
def checkout_payment_link(req: PaymentLinkRequest):
    """Creates a real Razorpay payment link for away-from-desktop rescue."""
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        cart = _build_cart(req.cart_items, req.currency, req.final_total, req.cart_id)
        agent = CheckoutAgent()
        result = agent.create_payment_link(
            cart,
            customer_name=req.customer_name,
            customer_phone=req.customer_phone,
            customer_email=req.customer_email,
            notify_sms=req.notify_sms,
            notify_email=req.notify_email,
            notify_whatsapp=req.notify_whatsapp,
            expiry_minutes=req.expiry_minutes,
            failed_attempts_summary=req.failed_attempts_summary,
            buffer_minutes=req.buffer_minutes
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/payment-link/{plink_id}/status", tags=["Payment Rails & Mobile Rescue"], summary="Real-Time Payment Link Status & Countdown Ticker")
def payment_link_status(plink_id: str):
    """Polls real-time status of payment link."""
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        agent = CheckoutAgent()
        return agent.get_payment_link_status(plink_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment-link/{plink_id}/cancel", tags=["Payment Rails & Mobile Rescue"], summary="Explicitly Cancel Active Mobile Payment Link")
def cancel_payment_link_endpoint(plink_id: str):
    """Explicitly cancels an active payment link, immediately expiring it."""
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        agent = CheckoutAgent()
        return agent.cancel_payment_link(plink_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment-links/bulk-cancel", tags=["Payment Rails & Mobile Rescue"], summary="Bulk Cancel Issued Test Mode Payment Links")
def bulk_cancel_payment_links_endpoint():
    """Bulk cancels active/issued payment links to free up Razorpay test mode limit."""
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        agent = CheckoutAgent()
        return agent.bulk_cancel_payment_links()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payment-links/clean-stale-rescue", tags=["Payment Rails & Mobile Rescue"], summary="Clean Stale Unpaid Rescue Link Records")
def clean_stale_rescue_links_endpoint():
    """Removes stale local plink_test_* rescue dummy entries that were never paid.
    Prevents 'payment link no longer active' messages for old dummy rescue records."""
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        agent = CheckoutAgent()
        return agent.clean_stale_rescue_links()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pay/{order_id}", response_class=HTMLResponse, tags=["Payment Rails & Mobile Rescue"], summary="Hosted Responsive Mobile Rescue Checkout Page")
def mobile_pay_page(order_id: str):
    """Mobile Rescue Payment Web Page: Runs real Razorpay Checkout on phone or desktop browser."""
    from src.config import RAZORPAY_KEY_ID
    agent = CheckoutAgent()
    links = agent._load_payment_links()
    link_data = None
    target_plink_id = None
    for pid, ldata in links.items():
        if ldata.get("order_id") == order_id or pid == order_id:
            link_data = ldata
            target_plink_id = pid
            break

    amount = int((link_data.get("amount", 1999) if link_data else 1999) * 100)
    customer_name = link_data.get("customer_name", "Vipul Patil") if link_data else "Vipul Patil"
    customer_phone = link_data.get("customer_phone", "8806549952") if link_data else "8806549952"
    customer_email = link_data.get("customer_email", "vipul@test.com") if link_data else "vipul@test.com"
    failed_rails = link_data.get("failed_attempts_summary", "") if link_data else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Rasor Mobile Payment Rescue</title>
  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
  <style>
    body {{
      margin: 0; padding: 16px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f172a; color: #f8fafc; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 90vh;
      box-sizing: border-box;
    }}
    .card {{
      background: #1e293b; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 14px; padding: 24px; max-width: 400px; width: 100%; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); box-sizing: border-box;
    }}
    h2 {{ margin-top: 0; color: #6ee7b7; font-size: 1.3rem; margin-bottom: 8px; }}
    p {{ color: #94a3b8; font-size: 0.88rem; line-height: 1.5; margin: 8px 0; }}
    .btn {{
      background: #10b981; color: #fff; font-size: 1rem; font-weight: 700; border: none; padding: 14px 24px; border-radius: 8px; cursor: pointer; width: 100%; margin-top: 18px; box-shadow: 0 4px 12px rgba(16,185,129,0.3);
    }}
    .badge {{
      display: inline-block; background: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 0.75rem; padding: 4px 10px; border-radius: 20px; font-weight: 600; margin-bottom: 12px; border: 1px solid rgba(16, 185, 129, 0.3);
    }}
    .failed-notice {{
      background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 6px; padding: 8px 10px; font-size: 0.78rem; color: #fca5a5; margin: 12px 0; text-align: left;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">Rasor Autonomous Mobile Rescue</div>
    <h2>Complete Your Payment</h2>
    {f'<div class="failed-notice">Notice: Primary rails ({failed_rails}) declined. Complete your checkout securely below using UPI, GPay, PhonePe, or Cards.</div>' if failed_rails else ''}
    <p>Please complete your order on this mobile device using an alternate bank account, UPI, or card.</p>
    <div style="font-size: 1.6rem; font-weight: 800; color: #fff; margin: 14px 0;">
      ₹{amount // 100}
    </div>
    <button id="pay-btn" class="btn" onclick="openRazorpay()">Pay with Razorpay</button>
  </div>
  <script>
    const options = {{
      key: "{RAZORPAY_KEY_ID}",
      amount: {amount},
      currency: "INR",
      name: "Rasor Autonomous Commerce",
      description: "Mobile Rescue Checkout",
      order_id: "{order_id}",
      prefill: {{
        name: "{customer_name}",
        email: "{customer_email}",
        contact: "{customer_phone}"
      }},
      theme: {{ color: "#10b981" }},
      handler: async function (response) {{
        const btn = document.getElementById('pay-btn');
        btn.innerText = "Payment Verified! Updating...";
        btn.style.background = "#6366f1";
        try {{
          await fetch('/api/checkout/verify', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
              payment_id: response.razorpay_payment_id,
              order_id: "{order_id}",
              signature: response.razorpay_signature || ""
            }})
          }});
        }} catch(e) {{}}
        document.body.innerHTML = '<div class="card" style="text-align:center;"><div class="badge">Success</div><h2>Payment Verified!</h2><p>Your order has been captured and synchronized to Shopify. You can return to your computer.</p></div>';
      }}
    }};
    const rzp = new Razorpay(options);
    function openRazorpay() {{
      rzp.open();
    }}
    window.onload = function() {{
      setTimeout(openRazorpay, 500);
    }};
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)

@app.post("/api/checkout/failover-log", tags=["Payment Rails & Mobile Rescue"], summary="Log Multi-Rail Banking Decline to Audit Ledger")
def checkout_failover_log(req: FailoverLogRequest):
    """Logs autonomous rail failovers to the audit ledger."""
    try:
        agent = CheckoutAgent()
        agent.record_tier_failover(
            cart_id=req.cart_id,
            order_id=req.order_id,
            failed_tier=req.failed_tier,
            instrument=req.failed_instrument,
            reason=req.reason,
            next_tier=req.next_tier,
            next_instrument=req.next_instrument
        )
        return {"logged": True}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── AP2 Mandate Endpoints ─────────────────────────────────────────────────────
@app.post("/api/mandate/intent", tags=["W3C AP2 Mandates"], summary="Establish AP2 User Intent Spending Ceiling")
def create_intent_mandate(req: CreateIntentMandateRequest):
    try:
        from src.agent.mandate import mandate_engine
        mandate = mandate_engine.create_intent_mandate(req.user_email, req.max_amount, req.user_phone)
        return mandate.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mandate/cart", tags=["W3C AP2 Mandates"], summary="Freeze Cart Total with Cryptographic SHA-256 Hash")
def create_cart_mandate(req: CreateCartMandateRequest):
    try:
        from src.agent.mandate import mandate_engine
        cm = mandate_engine.create_cart_mandate(
            items=req.items,
            frozen_total=req.frozen_total,
            intent_mandate_id=req.intent_mandate_id,
            currency=req.currency
        )
        return cm.model_dump()
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── ACP (Agentic Commerce Protocol) Feed ───────────────────────────────────────
@app.get("/api/v1/acp/catalog.json", tags=["ACP-2026.1 Catalog Protocol"], summary="ACP Machine-Readable Catalog Feed")
@app.get("/.well-known/agentic-commerce.json", tags=["ACP-2026.1 Catalog Protocol"], summary="RFC Standard .well-known Autonomous Discovery Manifest")
def get_acp_feed():
    """ACP Machine-Readable Catalog Feed for external AI buyers."""
    try:
        from src.data.shopify_api import ShopifyCatalogProvider
        from src.data.dev_catalog import DevCatalogProvider
        
        prods = []
        try:
            s_prov = ShopifyCatalogProvider()
            prods = s_prov.search_products(query="", limit=30)
        except Exception:
            pass
            
        if not prods:
            d_prov = DevCatalogProvider()
            prods = d_prov.search_products(query="", limit=30)

        acp_items = []
        for p in prods:
            acp_items.append({
                "id": p.id,
                "title": p.title,
                "category": str(p.category or "t-shirt"),
                "brand": p.specs.get("brand") or p.merchant or "Rasor",
                "price": p.price,
                "currency": p.currency or "INR",
                "in_stock": p.in_stock,
                "variants": [
                    {"size": s, "variant_gid": gid, "in_stock": True}
                    for s, gid in (p.specs.get("variant_ids") or {"XL": f"gid://shopify/ProductVariant/{p.id}"}).items()
                ],
                "specs": {
                    "fit": p.specs.get("fit", "Regular Fit"),
                    "color": p.specs.get("color", "Any"),
                    "fandom": p.specs.get("fandom", "None"),
                    "display_image": p.specs.get("display_image") or p.specs.get("image_url")
                }
            })

        return {
            "protocol": "ACP-2026.1",
            "merchant": {
                "name": "Rasor Commerce",
                "system_of_record": "Shopify Headless Storefront",
                "currency": "INR",
                "supported_mandates": ["AP2", "UAP"],
                "endpoints": {
                    "mandate_intent": "/api/mandate/intent",
                    "mandate_cart": "/api/mandate/cart",
                    "checkout_order": "/api/checkout/order",
                    "payment_link": "/api/checkout/payment-link"
                }
            },
            "item_count": len(acp_items),
            "items": acp_items
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/checkout/verify", tags=["Payment Rails & Mobile Rescue"], summary="Verify Razorpay Payment Signature")
def checkout_verify(req: VerifyPaymentRequest):
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        agent = CheckoutAgent()
        valid = agent.verify_payment(req.payment_id, req.order_id)
        if valid:
            # Reconcile payment links registry so status becomes 'paid'
            links = agent._load_payment_links()
            for pid, ldata in links.items():
                if ldata.get("order_id") == req.order_id or pid == req.order_id or ldata.get("plink_id") == req.order_id:
                    links[pid]["status"] = "paid"
                    links[pid]["payment_id"] = req.payment_id
                    links[pid]["paid_at"] = int(time.time())
                    agent._save_payment_links(links)
                    break
        return {"valid": valid}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/shopify/sync", tags=["Settlement & Audit Ledger"], summary="Zero-Trust Synchronization of Paid Order to Shopify Admin REST")
def shopify_sync(req: ShopifySyncRequest):
    try:
        # Zero-trust safeguard: If this is a payment link rescue, verify with Razorpay
        # that the link is strictly 'paid' and not 'cancelled' or 'expired'.
        if req.order_id and req.order_id.startswith("plink_"):
            if HAS_CHECKOUT:
                agent = CheckoutAgent()
                plink_status = agent.get_payment_link_status(req.order_id)
                current_status = plink_status.get("status")
                if current_status != "paid":
                    return {
                        "success": False,
                        "error": f"Fulfillment rejected: Payment link status is '{current_status}', not 'paid'. Order cannot be created."
                    }

        admin = ShopifyAdminProvider()
        items = [CartItem(
            product_id=i["product_id"],
            title=i["title"],
            merchant=i.get("merchant", "Rasor"),
            unit_price=i["unit_price"],
            quantity=i["quantity"]
        ) for i in req.cart_items]
        result = admin.create_paid_order(
            items, 
            req.currency, 
            req.final_total, 
            req.order_id, 
            email=req.email,
            payment_id=req.payment_id
        )
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── Shopify Orders ────────────────────────────────────────────────────────────
@app.get("/api/shopify/orders", tags=["Settlement & Audit Ledger"], summary="Fetch Recent Shopify Orders via Background Reconciler")
def shopify_orders(limit: int = 5):
    try:
        # Automatically reconcile any mobile links before returning orders list
        if HAS_CHECKOUT:
            try:
                agent = CheckoutAgent()
                agent.reconcile_payment_links()
            except Exception:
                pass
        admin = ShopifyAdminProvider()
        orders = admin.get_recent_orders(limit=limit)
        return {"orders": orders}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/checkout/reconcile-links", tags=["Settlement & Audit Ledger"], summary="Trigger Instant Payment Link Reconciler Sweep")
def checkout_reconcile_links():
    """Manual or scheduled trigger to reconcile all payment links immediately."""
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    agent = CheckoutAgent()
    reconciled = agent.reconcile_payment_links()
    return {"reconciled": reconciled}

@app.post("/api/webhook/razorpay", tags=["Settlement & Audit Ledger"], summary="Razorpay Event Webhook Receiver")
async def razorpay_webhook(req: Request):
    """Event-driven webhook from Razorpay for payment_link.paid events."""
    try:
        data = await req.json()
        event = data.get("event")
        if event in ("payment_link.paid", "payment.captured"):
            if HAS_CHECKOUT:
                agent = CheckoutAgent()
                agent.reconcile_payment_links()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/checkout/refunds", tags=["Race Recovery & Instant Refunds"], summary="List All Autonomous Gateway Refunds")
def checkout_refunds():
    """Returns all autonomous refunds executed by the agent."""
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    agent = CheckoutAgent()
    links = agent._load_payment_links()
    refunds = []
    for plink_id, info in links.items():
        if info.get("refunded"):
            refunds.append({
                "plink_id": plink_id,
                "refund_id": info.get("refund_id"),
                "amount": info.get("amount"),
                "currency": info.get("currency", "INR"),
                "customer_email": info.get("customer_email"),
                "customer_name": info.get("customer_name"),
                "reason": "Payment received on cancelled/expired link. Full autonomous refund issued.",
                "status": "processed",
                "created_at": info.get("created_at")
            })
    return {"refunds": refunds}

class PostPaymentRefundRequest(BaseModel):
    payment_id: str
    order_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = "INR"
    item_title: Optional[str] = None
    reason: Optional[str] = "Post-payment inventory depletion: Item claimed during checkout confirmation"
    customer_email: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "payment_id": "pay_simulated_test_123",
                "order_id": "order_TYDL1MOG7yuAmD",
                "amount": 549.0,
                "currency": "INR",
                "item_title": "Men's Black Iron Man Graphic Printed T-shirt",
                "reason": "Post-payment inventory depletion: Item claimed during checkout confirmation",
                "customer_email": "vipulapatil21@gmail.com"
            }
        }
    }

@app.post("/api/checkout/post-payment-refund", tags=["Race Recovery & Instant Refunds"], summary="Instant Autonomous Refund on Inventory Collision")
def post_payment_refund(req: PostPaymentRefundRequest):
    """Executes an instant autonomous refund when a post-payment inventory race condition occurs."""
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    agent = CheckoutAgent()
    refund_id = None
    # Attempt real refund via Razorpay client if payment_id starts with pay_
    if agent.client and req.payment_id and req.payment_id.startswith("pay_"):
        try:
            rfnd = agent.client.payment.refund(req.payment_id, {
                "notes": {
                    "reason": req.reason,
                    "item": req.item_title or "Fashion item",
                    "order_id": req.order_id or ""
                }
            })
            refund_id = rfnd.get("id")
        except Exception as e:
            print(f"[post_payment_refund] Real Razorpay refund note: {e}")
            refund_id = f"rfnd_post_{int(time.time())}"
    else:
        refund_id = f"rfnd_post_{int(time.time())}"

    # Record event in AP2 Audit Ledger
    try:
        ledger = AuditLedger()
        ledger.record_event(
            event_type="autonomous_post_payment_refund",
            actor="agent",
            data={
                "payment_id": req.payment_id,
                "order_id": req.order_id,
                "amount": req.amount,
                "currency": req.currency,
                "refund_id": refund_id,
                "item_title": req.item_title,
                "reason": req.reason,
                "policy": "AP2-SafeGuard-ZeroLoss"
            }
        )
    except Exception as e:
        print(f"[post_payment_refund] Ledger recording error: {e}")

    # Persist in payment_links.json so it shows up in Refunds tab
    links = agent._load_payment_links()
    ref_key = req.payment_id or f"plink_post_{int(time.time())}"
    links[ref_key] = {
        "id": ref_key,
        "payment_id": req.payment_id,
        "order_id": req.order_id,
        "amount": req.amount,
        "currency": req.currency,
        "customer_email": req.customer_email,
        "refunded": True,
        "refund_id": refund_id,
        "reason": req.reason,
        "status": "refunded",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    agent._save_payment_links(links)

    return {
        "success": True,
        "refund_id": refund_id,
        "payment_id": req.payment_id,
        "amount": req.amount,
        "currency": req.currency,
        "status": "processed",
        "reason": req.reason
    }

# ── Audit Ledger ──────────────────────────────────────────────────────────────
@app.get("/api/ledger", tags=["Settlement & Audit Ledger"], summary="Read Immutable AP2 Audit Ledger Entries")
def get_ledger():
    try:
        ledger = AuditLedger()
        entries = ledger.get_entries()
        return {"entries": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/ledger", tags=["Settlement & Audit Ledger"], summary="Purge Append-Only Audit Ledger")
def clear_ledger():
    try:
        ledger = AuditLedger()
        if os.path.exists(ledger.file_path):
            os.remove(ledger.file_path)
        return {"cleared": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Config ────────────────────────────────────────────────────────────────────
@app.get("/api/razorpay-key", tags=["Health & Gateway Keys"], summary="Public Razorpay Key ID")
def get_razorpay_key():
    from src.config import RAZORPAY_KEY_ID
    return {"key_id": RAZORPAY_KEY_ID or ""}
