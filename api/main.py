"""FastAPI backend for Rasor Agentic Commerce.
Wraps all existing Python agents/providers with a thin REST layer.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import traceback

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
app = FastAPI(title="Rasor API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Per-session stylist agents (keyed by session_id)
_stylist_agents: Dict[str, StylistAgent] = {}

def get_provider(data_source: str):
    if data_source == "bewakoof_live_api":
        return BewakoofCatalogProvider()
    elif data_source in ["shopify_storefront_live_api", "shopify_storefront_api"]:
        return ShopifyCatalogProvider()
    elif data_source == "google_shopping_scraper":
        return GoogleShoppingScraper()
    else:
        return DevCatalogProvider()

# ── Request/Response Models ───────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    data_source: str = "bewakoof_live_api"
    primary_model: str = "gemini-2.5-flash"
    fallback_model: str = "llama-3.3-70b-versatile"
    max_results: int = 21
    enable_deep_enrichment: bool = True
    max_deep_fetches: int = 10
    enable_vqa_scanner: bool = True
    vqa_strict_filter: bool = True
    truth_hierarchy: bool = True
    enable_semantic_engine: bool = True
    currency: str = "INR"

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []
    session_id: str = "default"
    data_source: str = "bewakoof_live_api"
    primary_model: str = "gemini-3.5-flash"
    fallback_model: str = "llama-3.3-70b-versatile"

class CartCreateRequest(BaseModel):
    variant_gid: str
    quantity: int = 1

class CartAddRequest(BaseModel):
    cart_id: str
    variant_gid: str
    quantity: int = 1

class OrderRequest(BaseModel):
    cart_items: List[Dict[str, Any]]
    currency: str = "INR"
    final_total: float
    customer_id: Optional[str] = None
    cart_id: str = "cart_default"

class S2SRequest(BaseModel):
    cart_items: List[Dict[str, Any]]
    currency: str = "INR"
    final_total: float
    token_id: str
    customer_id: str
    cart_id: str = "cart_s2s"

class VerifyPaymentRequest(BaseModel):
    payment_id: str
    order_id: str

class ShopifySyncRequest(BaseModel):
    cart_items: List[Dict[str, Any]]
    currency: str = "INR"
    final_total: float
    order_id: str
    email: str = "agentic@rasor.test"

class OfferRequest(BaseModel):
    cart_items: Dict[str, int]
    product_lookup: Dict[str, Dict[str, Any]]
    currency: str = "INR"

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "checkout_available": HAS_CHECKOUT}

# ── Search ────────────────────────────────────────────────────────────────────
@app.post("/api/search")
def search(req: SearchRequest):
    try:
        # Force upgrade legacy models sent by stale frontend state
        if req.primary_model in ["gemini-1.5-flash", "gemini-2.5-flash"]:
            req.primary_model = "gemini-3.5-flash"
            
        config = AgentConfig(
            mode=ExecutionMode.LIVE,
            data_source=DataSourceType(req.data_source),
            primary_model=req.primary_model,
            fallback_model=req.fallback_model,
            max_search_results=req.max_results,
            enable_deep_enrichment=req.enable_deep_enrichment,
            max_deep_fetches=req.max_deep_fetches,
            enable_vqa_scanner=req.enable_vqa_scanner,
            vqa_strict_filter=req.vqa_strict_filter,
            truth_hierarchy=req.truth_hierarchy,
            enable_semantic_engine=req.enable_semantic_engine,
            currency=req.currency,
        )
        brain = AgentBrain(
            primary_model=config.primary_model,
            fallback_model=config.fallback_model
        )
        provider = get_provider(req.data_source)

        # Parse canonical query
        multi_query, norm_source = brain.normalize_intent(req.query, budget=config.max_budget)
        if not multi_query or not multi_query.items_to_buy:
            return {"products": [], "status": "No canonical query extracted", "canonical_query": None}
            
        canonical_query = multi_query.items_to_buy[0]
        effective_budget = canonical_query.max_price or config.max_budget

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

        # Deep enrichment
        if config.enable_deep_enrichment and hasattr(provider, "enrich_product"):
            top_to_enrich = raw_products[:config.max_deep_fetches]
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                list(executor.map(provider.enrich_product, top_to_enrich))

        # LLM evaluation
        try:
            validated_products, evaluations = brain.evaluate_candidates(
                req.query, 
                raw_products, 
                canonical=canonical_query,
                vqa_strict_filter=config.vqa_strict_filter,
                enable_vqa_scanner=config.enable_vqa_scanner,
                truth_hierarchy=config.truth_hierarchy
            )
        except Exception as e:
            print(f"Evaluation failed: {e}")
            validated_products, evaluations = raw_products, []

        eval_map = {e.product_id: e for e in evaluations}

        import math
        def bayesian_score(p):
            return (p.rating or 0.0) * math.log10((p.review_count or 0) + 1)
            
        bayesian_scores = [bayesian_score(p) for p in (validated_products if validated_products else raw_products)]
        max_b = max(bayesian_scores, default=1.0) or 1.0

        def composite_score(p):
            llm_score = eval_map.get(p.id).match_score if eval_map.get(p.id) else 0.5
            b_score = bayesian_score(p) / max_b
            return (llm_score * 0.7) + (b_score * 0.3)
            
        final_list = validated_products if validated_products else raw_products
        
        if not config.truth_hierarchy:
            final_list = [p for p in final_list if p.specs.get("truth_match") != False]
            
        final_list.sort(key=composite_score, reverse=True)

        search_results = validated_products[:config.max_search_results]
        displayed_ids = {p.id for p in search_results}
        rejected_products = [p for p in raw_products if p.id not in displayed_ids]
        rejected_products.sort(
            key=lambda p: (eval_map[p.id].match_score if p.id in eval_map else 0.0, bayesian_score(p)),
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
                "merchant": p.merchant,
                "specs": p.specs,
                "relevance_score": score,
                "verdict": "REJECTED" if is_discarded and score < 0.5 else verdict,
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
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── Chat ──────────────────────────────────────────────────────────────────────
@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        # Force upgrade legacy models sent by stale frontend state
        if req.primary_model in ["gemini-1.5-flash", "gemini-2.5-flash"]:
            req.primary_model = "gemini-3.5-flash"
            
        if req.session_id not in _stylist_agents:
            _stylist_agents[req.session_id] = StylistAgent(
                primary_model=req.primary_model,
                fallback_model=req.fallback_model
            )
        agent = _stylist_agents[req.session_id]
        response = agent.process_turn(req.message, req.history)
        return {
            "message": response.message,
            "suggested_options": getattr(response, "suggested_options", []),
            "ready_for_search": getattr(response, "ready_for_search", False),
            "updated_query": getattr(response, "updated_query", None),
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/chat/{session_id}")
def clear_chat(session_id: str):
    _stylist_agents.pop(session_id, None)
    return {"cleared": True}

# ── Compare ───────────────────────────────────────────────────────────────────
class CompareRequest(BaseModel):
    products: List[Dict[str, Any]]
    primary_model: str = "gemini-1.5-flash"
    fallback_model: str = "llama-3.3-70b-versatile"

@app.post("/api/compare")
def compare(req: CompareRequest):
    try:
        brain = AgentBrain(primary_model=req.primary_model, fallback_model=req.fallback_model)
        products = [Product(**p) for p in req.products]
        comparison = brain.compare_products(products)
        if not comparison:
            raise HTTPException(status_code=500, detail="Failed to generate comparison")
        return comparison.model_dump() if hasattr(comparison, "model_dump") else {}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── Cart ──────────────────────────────────────────────────────────────────────
@app.post("/api/cart/create")
def cart_create(req: CartCreateRequest):
    try:
        provider = ShopifyCartProvider()
        result = provider.create_cart(req.variant_gid, req.quantity)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cart/add")
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

@app.post("/api/checkout/order")
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
        result = agent.create_order(cart, customer_id=cid)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/checkout/mandate-order")
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
        result = agent.create_order(cart, customer_id=customer_id)
        result["customer_id"] = customer_id
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/checkout/s2s")
def checkout_s2s(req: S2SRequest):
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        cart = _build_cart(req.cart_items, req.currency, req.final_total, req.cart_id)
        agent = CheckoutAgent()
        result = agent.capture_saved_token(cart, req.token_id, req.customer_id)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/checkout/verify")
def checkout_verify(req: VerifyPaymentRequest):
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    try:
        agent = CheckoutAgent()
        valid = agent.verify_payment(req.payment_id, req.order_id)
        return {"valid": valid}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/shopify/sync")
def shopify_sync(req: ShopifySyncRequest):
    try:
        admin = ShopifyAdminProvider()
        items = [CartItem(
            product_id=i["product_id"],
            title=i["title"],
            merchant=i.get("merchant", "Rasor"),
            unit_price=i["unit_price"],
            quantity=i["quantity"]
        ) for i in req.cart_items]
        result = admin.create_paid_order(items, req.currency, req.final_total, req.order_id, email=req.email)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── Shopify Orders ────────────────────────────────────────────────────────────
@app.get("/api/shopify/orders")
def shopify_orders(limit: int = 5):
    try:
        admin = ShopifyAdminProvider()
        orders = admin.get_recent_orders(limit=limit)
        return {"orders": orders}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ── Audit Ledger ──────────────────────────────────────────────────────────────
@app.get("/api/ledger")
def get_ledger():
    try:
        ledger = AuditLedger()
        entries = ledger.get_entries()
        return {"entries": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/ledger")
def clear_ledger():
    try:
        ledger = AuditLedger()
        if os.path.exists(ledger.file_path):
            os.remove(ledger.file_path)
        return {"cleared": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Config ────────────────────────────────────────────────────────────────────
@app.get("/api/razorpay-key")
def get_razorpay_key():
    from src.config import RAZORPAY_KEY_ID
    return {"key_id": RAZORPAY_KEY_ID or ""}
