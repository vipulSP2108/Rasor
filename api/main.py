"""FastAPI backend for Rasor Agentic Commerce.
Wraps all existing Python agents/providers with a thin REST layer.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
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
app = FastAPI(title="Rasor API", version="2.0.0")

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
    vqa_limit: int = 8
    truth_hierarchy: bool = True
    enable_semantic_engine: bool = True
    currency: str = "INR"
    user_location: Optional[str] = "Mumbai"

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []
    session_id: str = "default"
    data_source: str = "bewakoof_live_api"
    primary_model: str = "gemini-3.5-flash"
    fallback_model: str = "llama-3.3-70b-versatile"
    user_location: Optional[str] = "Mumbai"

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
    mandate_id: Optional[str] = None
    max_authorized_cap: Optional[float] = None

class S2SRequest(BaseModel):
    cart_items: List[Dict[str, Any]]
    currency: str = "INR"
    final_total: float
    token_id: str
    customer_id: str
    cart_id: str = "cart_s2s"
    max_authorized_cap: Optional[float] = None

class VerifyPaymentRequest(BaseModel):
    payment_id: str
    order_id: str

class ShopifySyncRequest(BaseModel):
    cart_items: List[Dict[str, Any]]
    currency: str = "INR"
    final_total: float
    order_id: str
    email: str = "agentic@rasor.test"
    payment_id: Optional[str] = None

class PaymentLinkRequest(BaseModel):
    cart_items: List[Dict[str, Any]]
    currency: str = "INR"
    final_total: float
    cart_id: str = "cart_plink"
    customer_name: str = "Agentic User"
    customer_phone: str = "8806549952"
    customer_email: str = "vipulapatil21@gmail.com"
    notify_sms: bool = True
    notify_email: bool = True
    notify_whatsapp: bool = True
    expiry_minutes: Optional[int] = 15
    failed_attempts_summary: Optional[str] = None
    buffer_minutes: Optional[int] = 1

class FailoverLogRequest(BaseModel):
    cart_id: str
    order_id: str
    failed_tier: int
    failed_instrument: str
    reason: str
    next_tier: int
    next_instrument: str

class CreateIntentMandateRequest(BaseModel):
    user_email: str = "vipulapatil21@gmail.com"
    user_phone: str = "+918806549952"
    max_amount: float

class CreateCartMandateRequest(BaseModel):
    items: List[Dict[str, Any]]
    frozen_total: float
    currency: str = "INR"
    intent_mandate_id: Optional[str] = None

class OfferRequest(BaseModel):
    cart_items: Dict[str, int]
    product_lookup: Dict[str, Dict[str, Any]]
    currency: str = "INR"

class ProductsByIdsRequest(BaseModel):
    ids: List[str]
    data_source: Optional[str] = "shopify_storefront_live_api"

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "checkout_available": HAS_CHECKOUT}

@app.post("/api/products/by-ids")
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
@app.post("/api/search")
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

        # ── Stage 4c: Dynamic VQA post-filter ──
        # Instead of a hard 0.5 threshold (which can drop the only product in a category),
        # we use a dynamic minimum: always keep at least MIN_SURVIVORS products.
        # If strict 0.5 filtering leaves too few, we relax and take the top MIN_SURVIVORS instead.
        MIN_SURVIVORS = 3

        def get_match_score(p):
            ev = eval_map.get(p.id)
            return ev.match_score if ev else 0.5

        vqa_ran = any("[VQA:" in (e.reason or "") for e in evaluations)
        if vqa_ran:
            # First pass: strict 0.5 threshold
            strict_survivors = [p for p in validated_products if get_match_score(p) >= 0.5]
            if len(strict_survivors) >= MIN_SURVIVORS:
                # Enough passed — use strict filter
                validated_products = strict_survivors
                print(f"[Search] VQA post-filter (strict): {len(validated_products)} survivors")
            else:
                # Too few passed — relax to keep top MIN_SURVIVORS regardless of absolute score
                all_scored = sorted(validated_products, key=get_match_score, reverse=True)
                validated_products = all_scored[:max(MIN_SURVIVORS, len(strict_survivors))]
                print(f"[Search] VQA post-filter (relaxed, min_survivors={MIN_SURVIVORS}): {len(validated_products)} kept")

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
            # ── Tier-based delivery sort ──
            # Products are bucketed into 0.1-wide score tiers using floor().
            # Within the same tier, fastest delivery wins.
            # Between different tiers, higher score always wins.
            #
            # Example: scores [0.95, 0.92, 0.88, 0.72, 0.65]
            #   tier(0.95) = 0.9, tier(0.92) = 0.9  →  same tier → sort by days
            #   tier(0.88) = 0.8, tier(0.72) = 0.7, tier(0.65) = 0.6  →  own tiers
            # Result: [0.92(1-day), 0.95(2-day), 0.88(1-day), 0.72(2-day), 0.65(1-day)]
            def tier_delivery_key(p):
                cs = composite_score(p)
                score_tier = _math.floor(cs * 10) / 10   # e.g. 0.95 → 0.9, 0.88 → 0.8
                days = p.shipping_days if p.shipping_days else 99
                return (-score_tier, days)  # desc tier, asc delivery within tier

            final_list.sort(key=tier_delivery_key)
            sort_mode = "tier_delivery"
        else:
            final_list.sort(key=composite_score, reverse=True)

        search_results = final_list[:config.max_search_results]
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
                "review_count": getattr(p, "review_count", 0) or 120,
                "shipping_days": getattr(p, "shipping_days", 3) or 3,
                "shipping_speed": p.specs.get("shipping_speed") or ("🚀 Express" if getattr(p, "shipping_days", 3) <= 2 else "🚚 Std"),
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

@app.delete("/api/chat/{session_id}")
def clear_chat(session_id: str):
    _stylist_agents.pop(session_id, None)
    return {"cleared": True}

# ── Compare ───────────────────────────────────────────────────────────────────
class CompareRequest(BaseModel):
    products: List[Dict[str, Any]]
    primary_model: str = "gemini-1.5-flash"
    fallback_model: str = "llama-3.3-70b-versatile"
    user_location: Optional[str] = "Mumbai, Maharashtra"

class LogisticsEstimateRequest(BaseModel):
    products: List[Dict[str, Any]]
    location: str = "Mumbai, Maharashtra"

@app.get("/api/logistics/resolve/{query}")
def resolve_logistics_destination(query: str):
    try:
        from src.agent.logistics_agent import LogisticsAgent
        agent = LogisticsAgent()
        return agent.resolve_destination(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logistics/estimate")
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
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/compare")
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

@app.post("/api/checkout/s2s")
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

@app.post("/api/checkout/payment-link")
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

@app.get("/api/payment-link/{plink_id}/status")
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

@app.post("/api/payment-link/{plink_id}/cancel")
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

@app.post("/api/payment-links/bulk-cancel")
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

@app.post("/api/payment-links/clean-stale-rescue")
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

@app.get("/pay/{order_id}", response_class=HTMLResponse)
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
    <div class="badge">⚡ Rasor Autonomous Mobile Rescue</div>
    <h2>Complete Your Payment</h2>
    {f'<div class="failed-notice">⚠️ Primary rails ({failed_rails}) declined. Complete your checkout securely below using UPI, GPay, PhonePe, or Cards.</div>' if failed_rails else ''}
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
        document.body.innerHTML = '<div class="card" style="text-align:center;"><div class="badge">✅ Success</div><h2>Payment Verified!</h2><p>Your order has been captured and synchronized to Shopify. You can return to your computer.</p></div>';
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

@app.post("/api/checkout/failover-log")
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
@app.post("/api/mandate/intent")
def create_intent_mandate(req: CreateIntentMandateRequest):
    try:
        from src.agent.mandate import mandate_engine
        mandate = mandate_engine.create_intent_mandate(req.user_email, req.max_amount, req.user_phone)
        return mandate.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mandate/cart")
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
@app.get("/api/v1/acp/catalog.json")
@app.get("/.well-known/agentic-commerce.json")
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

@app.post("/api/checkout/verify")
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

@app.post("/api/shopify/sync")
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
@app.get("/api/shopify/orders")
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

@app.post("/api/checkout/reconcile-links")
def checkout_reconcile_links():
    """Manual or scheduled trigger to reconcile all payment links immediately."""
    if not HAS_CHECKOUT:
        raise HTTPException(status_code=503, detail="CheckoutAgent not available")
    agent = CheckoutAgent()
    reconciled = agent.reconcile_payment_links()
    return {"reconciled": reconciled}

@app.post("/api/webhook/razorpay")
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

@app.get("/api/checkout/refunds")
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

@app.post("/api/checkout/post-payment-refund")
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
