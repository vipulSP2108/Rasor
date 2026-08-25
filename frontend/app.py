"""Streamlit Frontend UI for Rasor Agentic Commerce.

Featuring:
1. LLM Intent Normalization (Raw Text -> Strict Pydantic Enums).
2. Multi-Model Live Query Execution (Bewakoof API, Scraper, Mock).
3. LLM Candidate Relevance Evaluation & Rejection of False Positives.
"""

import streamlit as st
import os
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import importlib
import src.config
import src.agent.brain
import src.data.bewakoof_api
import src.data.shopify_api
importlib.reload(src.config)
importlib.reload(src.agent.brain)
importlib.reload(src.data.bewakoof_api)
importlib.reload(src.data.shopify_api)

from src.config import (
    AgentConfig,
    ExecutionMode,
    DataSourceType,
)
from src.agent.state import CanonicalShoppingQuery, ProductRelevanceEvaluation
from src.agent.brain import AgentBrain
from src.data.dev_catalog import DevCatalogProvider
from src.data.scraper import GoogleShoppingScraper
from src.data.bewakoof_api import BewakoofCatalogProvider
from src.data.shopify_api import ShopifyCatalogProvider

st.set_page_config(
    page_title="Rasor — Agentic Commerce",
    page_icon="🛍️",
    layout="wide"
)

# ------------------------------------------------------------------------------
# 1. State Management (Decoupled Session State)
# ------------------------------------------------------------------------------
if "config" not in st.session_state or not hasattr(st.session_state.config, "enable_deep_enrichment") or not hasattr(st.session_state.config, "user_location"):
    st.session_state.config = AgentConfig(
        mode=ExecutionMode.LIVE,
        data_source=DataSourceType.BEWAKOOF_LIVE_API,
        max_cost_hitl=800.0,
        max_budget=3000.0,
        currency="INR"
    )

if "search_results" not in st.session_state:
    st.session_state.search_results = []

if "canonical_query" not in st.session_state:
    st.session_state.canonical_query = None

if "evaluations" not in st.session_state:
    st.session_state.evaluations = []

if "normalization_source" not in st.session_state:
    st.session_state.normalization_source = ""

# Initialize Brain
brain = AgentBrain(
    primary_model=st.session_state.config.primary_model,
    fallback_model=st.session_state.config.fallback_model
)

# ------------------------------------------------------------------------------
# 2. Sidebar Configuration
# ------------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ System Configuration")
    
    # Execution Mode (Dev vs Live)
    mode_choice = st.radio(
        "Execution Mode",
        options=["Live (Direct Store API / Scraper)", "Dev (Local Mock Data)"],
        index=0 if st.session_state.config.mode == ExecutionMode.LIVE else 1,
        help="Live mode connects directly to live merchant endpoints. Dev mode uses local deterministic fixtures."
    )
    st.session_state.config.mode = ExecutionMode.LIVE if "Live" in mode_choice else ExecutionMode.DEV

    # Data Source Selection (if Live)
    if st.session_state.config.mode == ExecutionMode.LIVE:
        source_choice = st.selectbox(
            "Live Data Acquisition Source",
            options=["Bewakoof.com (Live Authenticated API)", "Google Shopping (Scraper)", "Shopify Storefront API", "MCP Server"],
            index=0
        )
        if "Bewakoof" in source_choice:
            st.session_state.config.data_source = DataSourceType.BEWAKOOF_LIVE_API
            st.session_state.config.currency = "INR"
        elif "Google" in source_choice:
            st.session_state.config.data_source = DataSourceType.GOOGLE_SHOPPING_SCRAPER
            st.session_state.config.currency = "USD"
        elif "Shopify" in source_choice:
            st.session_state.config.data_source = DataSourceType.SHOPIFY_STOREFRONT_LIVE_API
            st.session_state.config.currency = "USD"
        else:
            st.session_state.config.data_source = DataSourceType.MCP_SERVER
            st.session_state.config.currency = "USD"
    else:
        st.session_state.config.data_source = DataSourceType.DEV_MOCK
        st.session_state.config.currency = "USD"

    st.divider()
    st.subheader("🛡️ Financial Guardrails")
    curr_sym = "₹" if st.session_state.config.currency == "INR" else "$"
    
    # HITL Threshold
    st.session_state.config.max_cost_hitl = st.number_input(
        f"HITL Approval Threshold ({curr_sym})",
        min_value=10.0,
        max_value=20000.0,
        value=float(st.session_state.config.max_cost_hitl),
        step=50.0,
        help="Transactions above this dollar amount pause the agent and require explicit human approval."
    )

    # Max Budget
    st.session_state.config.max_budget = st.number_input(
        f"Hard Maximum Budget ({curr_sym})",
        min_value=float(st.session_state.config.max_cost_hitl),
        max_value=50000.0,
        value=float(st.session_state.config.max_budget),
        step=100.0,
        help="Strict budget ceiling. The agent will refuse any order exceeding this total."
    )

    st.divider()
    st.subheader("🔍 Search & Enrichment")
    
    st.session_state.config.enable_deep_enrichment = st.toggle(
        "Enable Deep Product Enrichment",
        value=st.session_state.config.enable_deep_enrichment,
        help="Hits single-product APIs for richer descriptions, verified ratings, and bundles."
    )
    
    st.session_state.config.max_deep_fetches = st.slider(
        "Max Deep Fetches (Top K)",
        min_value=1,
        max_value=20,
        value=st.session_state.config.max_deep_fetches,
        help="Maximum concurrent API calls made to enrich products."
    )

    st.divider()
    st.subheader("🚚 Shipping & Logistics")
    st.session_state.config.user_location = st.selectbox(
        "Destination City (Fast Shipping)",
        options=["Not Set", "Mumbai", "Delhi", "Bengaluru", "New York", "London"],
        index=0,
        help="Used to estimate delivery times and filter products if 'fast delivery' is requested."
    )

    st.divider()
    st.subheader("🧠 LLM & Fallback Models")
    st.session_state.config.primary_model = st.selectbox(
        "Primary Model",
        options=["gemini-3.1-flash-lite", "gemini-2.5-flash-lite", "gemini-flash-latest"],
        index=0
    )
    st.session_state.config.fallback_model = st.selectbox(
        "Fallback Model (on error/limit)",
        options=["openai/gpt-oss-20b", "qwen/qwen3.6-27b", "groq/compound-mini"],
        index=0
    )

# ------------------------------------------------------------------------------
# 3. Main Interface & Natural Language Prompt
# ------------------------------------------------------------------------------
st.title("🛍️ Rasor: Autonomous Agentic Commerce")
st.caption(
    f"Active Mode: **{st.session_state.config.mode.value.upper()}** | "
    f"Data Provider: **{st.session_state.config.data_source.value}** | "
    f"HITL Trigger: **>{curr_sym}{st.session_state.config.max_cost_hitl:.2f}** | "
    f"Budget: **{curr_sym}{st.session_state.config.max_budget:.2f}**"
)

# Natural Language Prompt Input
col_prompt, col_btn = st.columns([5, 1])

with col_prompt:
    user_prompt = st.text_input(
        "Enter your natural shopping intent:",
        value="Solid plain black t-shirt for men under 600 in size L",
        placeholder="e.g. Solid plain black t-shirt for men under 600 in size L",
        label_visibility="collapsed"
    )

with col_btn:
    search_clicked = st.button("🚀 Run Agent", type="primary", use_container_width=True)

# ------------------------------------------------------------------------------
# 4. Multi-Stage Pipeline Execution
# ------------------------------------------------------------------------------
if (search_clicked or not st.session_state.search_results) and user_prompt:
    with st.spinner("🤖 Stage 1: LLM Normalizing prompt into Canonical Enums..."):
        canonical, norm_source = brain.normalize_intent(user_prompt)
        st.session_state.canonical_query = canonical
        st.session_state.normalization_source = norm_source

    with st.spinner(f"📡 Stage 2: Querying {st.session_state.config.data_source.value} with normalized tokens..."):
        if st.session_state.config.data_source == DataSourceType.BEWAKOOF_LIVE_API:
            provider = BewakoofCatalogProvider()
        elif st.session_state.config.data_source == DataSourceType.SHOPIFY_STOREFRONT_LIVE_API:
            provider = ShopifyCatalogProvider()
        elif st.session_state.config.data_source == DataSourceType.GOOGLE_SHOPPING_SCRAPER:
            provider = GoogleShoppingScraper(max_retries=3)
        else:
            provider = DevCatalogProvider()

        effective_budget = canonical.max_price or st.session_state.config.max_budget

        raw_candidates = provider.search_products(
            query=canonical.cleaned_keywords or user_prompt,
            category=canonical.category.value if canonical.category.value != "general" else None,
            gender=canonical.gender.value if canonical.gender.value != "all" else None,
            color=canonical.color.value if canonical.color.value != "Any" else None,
            size=canonical.size,
            design=canonical.design.value if canonical.design.value != "Any" else None,
            fandom=canonical.fandom.value if canonical.fandom.value != "None" else None,
            fit=canonical.fit.value if canonical.fit.value != "Any" else None,
            sleeve=canonical.sleeve.value if canonical.sleeve.value != "Any" else None,
            max_price=effective_budget,
            limit=40 # Fetch enough products to show in the extra products section
        )

    with st.spinner("🧠 Stage 3: LLM Validating candidate relevance & filtering false positives..."):
        import math
        def bayesian_score(p):
            return p.rating * math.log10(p.review_count + 1)
        
        # Sort raw candidates by Bayesian quality first
        raw_candidates.sort(key=bayesian_score, reverse=True)
        
        # Evaluate ALL candidates — no artificial cap. The LLM will rank them.
        llm_eval_limit = len(raw_candidates)
        llm_candidates = raw_candidates[:]
        
        # Deep Enrichment
        if st.session_state.config.enable_deep_enrichment:
            with st.spinner(f"🔍 Deep Enriching top {st.session_state.config.max_deep_fetches} candidates..."):
                import concurrent.futures
                
                # Take top max_deep_fetches from llm_candidates
                top_to_enrich = llm_candidates[:st.session_state.config.max_deep_fetches]
                
                # Extract session state variables before entering the thread pool
                current_location = st.session_state.config.user_location
                
                def enrich(prod):
                    provider.enrich_product(prod)
                    
                    # Logistics: Fast Shipping Logic
                    if canonical.fast_shipping_requested and current_location != "Not Set":
                        from src.data.logistics import calculate_shipping_days
                        
                        # Use accurate Geocoding & Haversine Distance API logic
                        prod.shipping_days = calculate_shipping_days(current_location)
                        
                        # We could also modify the Bayesian score here to prioritize faster items!
                        # But for now, just tagging it is enough for the LLM to see.
                        prod.specs["fast_delivery_available"] = (prod.shipping_days <= 2)
                        
                    return prod
                    
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    # Enriches in place
                    list(executor.map(enrich, top_to_enrich))
        
        # ── Aggressive Text-First Negation Filter ──
        neg_keywords = getattr(canonical, 'negative_keywords', [])
        if neg_keywords:
            with st.spinner(f"🚫 Applying Negative Filters: {', '.join(neg_keywords)}..."):
                filtered_llm = []
                for p in llm_candidates:
                    text_to_check = (p.title + " " + (p.rich_description or "")).lower()
                    if any(neg.lower() in text_to_check for neg in neg_keywords):
                        continue
                    filtered_llm.append(p)
                llm_candidates = filtered_llm

        # No more "extra_untested" — all products are evaluated
        validated_products, evaluations = brain.evaluate_candidates(
            user_prompt, llm_candidates, canonical=canonical
        )
        
        # Build eval map for fast lookup
        eval_map = {e.product_id: e for e in evaluations}
        
        # ── Composite ranking: LLM match score (70%) + Bayesian quality (30%) ──
        # Normalise bayesian scores to 0-1 range for fair weighting
        bayesian_scores = [bayesian_score(p) for p in validated_products]
        max_b = max(bayesian_scores, default=1.0) or 1.0
        def composite_score(p):
            llm_score = eval_map[p.id].match_score if p.id in eval_map else 0.5
            b_score = bayesian_score(p) / max_b  # normalised 0-1
            return llm_score * 0.7 + b_score * 0.3
        
        validated_products.sort(key=composite_score, reverse=True)
        
        st.session_state.search_results = validated_products[:st.session_state.config.max_search_results]
        
        # Store all rejected/lower-scored products
        displayed_ids = {p.id for p in st.session_state.search_results}
        st.session_state.rejected_products = [p for p in raw_candidates if p.id not in displayed_ids]
        # Sort rejected by the same composite score
        st.session_state.rejected_products.sort(
            key=lambda p: (eval_map[p.id].match_score if p.id in eval_map else 0.0, bayesian_score(p)),
            reverse=True
        )
        
        st.session_state.evaluations = evaluations

        # Capture status message for UI display
        if hasattr(provider, "last_status_message"):
            st.session_state.last_status = provider.last_status_message
        else:
            st.session_state.last_status = "🟢 Loaded directly from Dev Mock Catalog."

# ------------------------------------------------------------------------------
# 5. Intent Normalization Inspector (Stage 1 Visualization)
# ------------------------------------------------------------------------------
if st.session_state.canonical_query:
    q: CanonicalShoppingQuery = st.session_state.canonical_query
    with st.expander(f"🤖 Stage 1: LLM Normalized Taxonomy ({st.session_state.normalization_source})", expanded=True):
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        with col1:
            st.metric("👤 Gender", q.gender.value.title())
        with col2:
            st.metric("🏷️ Category", q.category.value.title())
        with col3:
            st.metric("🎨 Color", q.color.value)
        with col4:
            st.metric("🎨 Design Pattern", q.design.value)
        with col5:
            st.metric("📏 Size", q.size if q.size else "Any")
        with col6:
            st.metric("👕 Fit", q.fit.value.replace(" Fit", ""))
        with col7:
            st.metric("💰 Budget Cap", f"{curr_sym}{q.max_price:.0f}" if q.max_price else "No Cap")

# Display Status Banner
if "last_status" in st.session_state and st.session_state.last_status:
    if "FALLBACK TRIGGERED" in st.session_state.last_status:
        st.warning(f"**Data Pipeline Notification:**\n\n{st.session_state.last_status}")
    else:
        st.success(f"**Data Source Status:** {st.session_state.last_status}")

# ------------------------------------------------------------------------------
# 6. Validated Products Visualizer (Stage 3 Output)
# ------------------------------------------------------------------------------
if st.session_state.search_results:
    st.subheader(f"📦 Validated Product Matches ({len(st.session_state.search_results)} items passed LLM QA)")
    
    cols = st.columns(3)
    eval_map = {e.product_id: e for e in st.session_state.evaluations}

    for idx, prod in enumerate(st.session_state.search_results):
        with cols[idx % 3]:
            with st.container(border=True):
                # Product Image
                img_url = prod.specs.get("image_url")
                if img_url:
                    st.image(img_url, use_container_width=True)
                
                st.markdown(f"#### {prod.title}")
                
                # Attribute Badges
                prod_gender = prod.specs.get("gender") or "Unisex"
                prod_color = prod.specs.get("color") or "Standard"
                prod_design = prod.specs.get("design") or "Standard"
                prod_fit = prod.specs.get("fit") or "Regular Fit"
                st.markdown(f"👤 `{prod_gender}` | 🎨 `{prod_color}` | 🏷️ `{prod_design}`")

                # Fandom & Bundle Offer Badges
                fandom_val = prod.specs.get("fandom_partner")
                if fandom_val:
                    st.markdown(f"⚡ **Collaboration:** `{fandom_val}`")

                bundles = prod.specs.get("bundle_offers", [])
                if bundles:
                    st.info(f"🎁 **Deal:** {', '.join(bundles)}")

                # Pricing details
                mrp_val = prod.specs.get("mrp_inr")
                member_price = prod.specs.get("member_price_inr")
                
                price_text = f"**Price:** `{curr_sym}{prod.price:.0f}`"
                if mrp_val and mrp_val > prod.price:
                    price_text += f" ~`{curr_sym}{mrp_val:.0f}`~"
                st.markdown(price_text)

                if member_price:
                    st.markdown(f"👑 **TriBe Member Price:** `{curr_sym}{member_price:.0f}`")
                
                # Rating and Reviews
                st.markdown(f"⭐ **{prod.rating}** ({prod.review_count} reviews)")
                
                # Rich Description if enriched (hide behind expander to save space)
                if prod.rich_description:
                    with st.expander("📝 View Description"):
                        st.markdown(prod.rich_description, unsafe_allow_html=True)
                
                # Shipping Logistics Display
                if hasattr(prod, 'shipping_days') and prod.shipping_days:
                    delivery_tag = "🚀 **Express Delivery**" if prod.shipping_days <= 2 else "🚚 **Standard Delivery**"
                    st.markdown(f"{delivery_tag}: Arrives in `{prod.shipping_days} days`")

                st.markdown(f"**Fit & Fabric:** `{prod_fit}` | `{prod.specs.get('fabric', 'Cotton')}`")
                
                # LLM QA Score Badge
                ev = eval_map.get(prod.id)
                if ev:
                    st.caption(f"🧠 **LLM Match Score:** `{int(ev.match_score * 100)}%` — *{ev.reason}*")

                # Sizes in stock
                sizes = prod.specs.get("available_sizes")
                if sizes:
                    st.caption(f"Sizes in stock: {', '.join(sizes)}")
                
                # Check HITL condition visually
                if prod.price > st.session_state.config.max_cost_hitl:
                    st.warning(f"⚠️ Price > {curr_sym}{st.session_state.config.max_cost_hitl:.2f} (Triggers HITL)")
                else:
                    st.success("✅ Within Autonomous Limit")

                if prod.source_url:
                    st.link_button("View on Store ↗", prod.source_url, use_container_width=True)

    with st.expander("🔍 Inspect Raw Canonical Query & Evaluations"):
        st.json({
            "canonical_query": st.session_state.canonical_query.model_dump() if st.session_state.canonical_query else None,
            "llm_evaluations": [e.model_dump() for e in st.session_state.evaluations],
            "products_returned": [p.model_dump() for p in st.session_state.search_results]
        })

# ------------------------------------------------------------------------------
# 7. Discarded Products Visualizer (Extra products that failed QA / overflow)
# ------------------------------------------------------------------------------
if "rejected_products" in st.session_state and st.session_state.rejected_products:
    st.markdown("---")
    rejected = st.session_state.rejected_products
    local_eval_map = {e.product_id: e for e in st.session_state.evaluations}

    # Re-sort by composite score so highest partial-matches appear first
    import math as _math
    def _b_score(p):
        return p.rating * _math.log10(p.review_count + 1)
    _all_b = [_b_score(p) for p in rejected]
    _max_b = max(_all_b, default=1.0) or 1.0
    def _composite(p):
        ev = local_eval_map.get(p.id)
        llm_s = ev.match_score if ev else 0.0
        return llm_s * 0.7 + (_b_score(p) / _max_b) * 0.3
    rejected = sorted(rejected, key=_composite, reverse=True)

    with st.expander(f"📦 Additional Catalog Items & Filtered Products ({len(rejected)} items)", expanded=False):
        # Render in rows of 5
        for i in range(0, len(rejected), 5):
            row_cols = st.columns(5)
            for j in range(5):
                if i + j < len(rejected):
                    prod = rejected[i + j]
                    eval_info = local_eval_map.get(prod.id)
                    with row_cols[j]:
                        with st.container(border=True):
                            # Product Image
                            img_url = prod.specs.get("display_image") or prod.specs.get("image_url")
                            if img_url:
                                st.image(img_url, use_container_width=True)
                            else:
                                st.image("https://via.placeholder.com/300x400?text=No+Image", use_container_width=True)

                            # Title & Price
                            st.markdown(f"**{prod.title[:45]}...**" if len(prod.title) > 45 else f"**{prod.title}**")
                            
                            colA, colB = st.columns(2)
                            with colA:
                                st.markdown(f"**{curr_sym}{prod.price:.0f}**")
                            with colB:
                                st.markdown(f"⭐ {prod.rating:.1f}")
                            
                            # Score badge + reason
                            if eval_info:
                                score_pct = int(eval_info.match_score * 100)
                                if score_pct >= 65:
                                    badge = f"🟡 {score_pct}% match"
                                elif score_pct >= 40:
                                    badge = f"🟠 {score_pct}% match"
                                else:
                                    badge = f"🔴 {score_pct}% — Filtered"
                                st.caption(f"{badge}")
                                st.caption(f"*{eval_info.reason}*")
                            else:
                                st.caption("⚡ Not evaluated")
                            
                            if prod.source_url:
                                st.link_button("View ↗", prod.source_url, use_container_width=True)


