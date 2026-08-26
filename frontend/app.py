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
import src.agent.state
import src.agent.parser
import src.agent.brain
import src.agent.stylist
import src.data.bewakoof_api
import src.data.shopify_api
importlib.reload(src.config)
importlib.reload(src.agent.state)
importlib.reload(src.agent.parser)
importlib.reload(src.agent.brain)
importlib.reload(src.agent.stylist)
importlib.reload(src.data.bewakoof_api)
importlib.reload(src.data.shopify_api)

from src.config import (
    AgentConfig,
    ExecutionMode,
    DataSourceType,
    UIMode,
)
from src.agent.stylist import StylistAgent
from src.agent.state import CanonicalShoppingQuery, ProductRelevanceEvaluation
from src.agent.brain import AgentBrain
from src.data.dev_catalog import DevCatalogProvider
from src.data.scraper import GoogleShoppingScraper
from src.data.bewakoof_api import BewakoofCatalogProvider
from src.data.shopify_api import ShopifyCatalogProvider

@st.cache_resource
def get_kokoro_model():
    """Cache the ONNX TTS model in memory globally so it doesn't reload on every interaction."""
    model_path = "src/models/kokoro/kokoro-v0_19.onnx"
    voices_path = "src/models/kokoro/voices.bin"
    if os.path.exists(model_path) and os.path.exists(voices_path):
        try:
            from kokoro_onnx import Kokoro
            return Kokoro(model_path, voices_path)
        except ImportError:
            return None
    return None

st.set_page_config(
    page_title="Rasor — Agentic Commerce",
    page_icon="🛍️",
    layout="wide"
)

# ------------------------------------------------------------------------------
# 1. State Management (Decoupled Session State)
# ------------------------------------------------------------------------------
# Hotfix for backward compatibility with active session state (Pydantic blocks dynamic field assignment)
if "config" in st.session_state and not hasattr(st.session_state.config, 'truth_hierarchy'):
    del st.session_state["config"]

if "config" not in st.session_state:
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

if "last_status" not in st.session_state:
    st.session_state.last_status = "Waiting for search..."

# Cart Tracking State
if "shopify_cart_id" not in st.session_state:
    st.session_state.shopify_cart_id = None
if "shopify_checkout_url" not in st.session_state:
    st.session_state.shopify_checkout_url = None
if "cart_quantity" not in st.session_state:
    st.session_state.cart_quantity = 0
if "cart_total_cost" not in st.session_state:
    st.session_state.cart_total_cost = 0.0
if "items_in_cart" not in st.session_state or isinstance(st.session_state.items_in_cart, set):
    st.session_state.items_in_cart = {}

if "grid_columns" not in st.session_state:
    st.session_state.grid_columns = 3

if "compare_list" not in st.session_state:
    st.session_state.compare_list = {}

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Welcome to Rasor! I'm your AI personal stylist. How can I help you today?"}]

if "chat_ready_for_search" not in st.session_state:
    st.session_state.chat_ready_for_search = False

if "current_user_prompt" not in st.session_state:
    st.session_state.current_user_prompt = None

if "stylist_agent" not in st.session_state:
    st.session_state.stylist_agent = StylistAgent()

from src.data.shopify_cart import ShopifyCartProvider

@st.dialog("⚖️ Compare Products", width="large")
def compare_products_dialog():
    if len(st.session_state.compare_list) < 2:
        st.warning("Please select at least 2 products to compare.")
        return
    if len(st.session_state.compare_list) > 5:
        st.warning("You can compare a maximum of 5 products at once.")
        return
    products = list(st.session_state.compare_list.values())
    
    # Render Images Side-by-Side
    img_cols = st.columns(len(products))
    for i, p in enumerate(products):
        with img_cols[i]:
            with st.container(border=True):
                img_url = p.specs.get("display_image") or p.specs.get("image_url")
                if img_url:
                    st.image(img_url, use_container_width=True)
                st.markdown(f"**{p.title[:30]}...**" if len(p.title) > 30 else f"**{p.title}**")
                st.caption(f"**₹{p.price:.0f}** | ⭐ {p.rating:.1f}")

    st.divider()

    with st.spinner("🤖 Stylist is analyzing the selected products..."):
        from src.agent.brain import AgentBrain
        brain = AgentBrain(primary_model=st.session_state.config.primary_model, fallback_model=st.session_state.config.fallback_model)
        comparison = brain.compare_products(products)
        
        if comparison:
            st.info(f"💡 **Quick Summary**\n\n{comparison.quick_summary}")
            
            st.markdown("### 📊 Feature Matrix")
            # Build dataframe for st.dataframe
            df_data = {"Feature": [r.feature_name for r in comparison.feature_matrix]}
            for p in products:
                df_data[p.title] = [r.product_values.get(p.title, "N/A") for r in comparison.feature_matrix]
            st.dataframe(df_data, use_container_width=True, hide_index=True)
            
            st.markdown("### ⚖️ Pros & Cons")
            pc_cols = st.columns(len(products))
            for i, p in enumerate(products):
                with pc_cols[i]:
                    pc = next((x for x in comparison.pros_and_cons if x.product_title == p.title), None)
                    if pc:
                        for pro in pc.pros:
                            st.markdown(f"✅ {pro}")
                        for con in pc.cons:
                            st.markdown(f"❌ {con}")
            
            st.markdown("### 🎯 Stylist Recommendation")
            rec_cols = st.columns(len(comparison.stylist_recommendation))
            for i, (cat, rec) in enumerate(comparison.stylist_recommendation.items()):
                with rec_cols[i]:
                    st.success(f"**{cat}**\n\n{rec}")
        else:
            st.error("Failed to generate product comparison. Please try again.")
    st.divider()
    if st.button("Clear Comparison List", use_container_width=True):
        st.session_state.compare_list = {}
        st.rerun()

@st.dialog("🛒 Add to Cart")
def add_to_cart_dialog(product):
    st.markdown(f"<h3 style='margin-top: 0; padding-top: 0; font-size: 1.2em; font-weight: 600;'>{product.title}</h3>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1.2])
    with col1:
        img_url = product.specs.get("image_url") or product.specs.get("display_image")
        if img_url:
            st.image(img_url, use_container_width=True)
            
        if product.id in st.session_state.items_in_cart:
            qty = st.session_state.items_in_cart[product.id]
            if qty >= 1000000:
                fmt_qty = f"{qty/1000000:.1f}M".replace(".0M", "M")
            elif qty >= 1000:
                fmt_qty = f"{qty/1000:.1f}k".replace(".0k", "k")
            else:
                fmt_qty = str(qty)
                
            st.markdown(f"<div style='background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); padding: 6px 12px; border-radius: 8px; text-align: center; font-size: 0.9em; font-weight: 500; margin-top: 8px;'>🛒 In Cart: {fmt_qty}</div>", unsafe_allow_html=True)
    
    with col2:
        curr_sym = "₹" if st.session_state.config.currency == "INR" else "$"
        st.markdown(f"<div style='font-size: 1.8em; font-weight: 800; margin-bottom: 12px; color: #10b981;'>{curr_sym}{product.price:.0f}</div>", unsafe_allow_html=True)
        
        variant_ids = product.specs.get("variant_ids", {})
        sizes = list(variant_ids.keys())
        
        if not sizes:
            st.error("This product has no available variants to add to cart.")
            if st.button("Close"):
                st.rerun()
            return

        # Defaults from canonical query
        cq = st.session_state.canonical_query
        req_size = None
        req_quantity = 1
        if cq:
            if hasattr(cq, 'items_to_buy') and len(cq.items_to_buy) > 0:
                req_size = cq.items_to_buy[0].size
                req_quantity = cq.items_to_buy[0].quantity
            elif hasattr(cq, 'size'):
                req_size = cq.size
                req_quantity = getattr(cq, 'quantity', 1)

        default_size_idx = 0
        if req_size:
            # Try to find an exact or case-insensitive match for the requested size
            try:
                # First try exact match
                default_size_idx = sizes.index(req_size)
            except ValueError:
                # Then try case-insensitive
                lower_sizes = [s.lower() for s in sizes]
                if req_size.lower() in lower_sizes:
                    default_size_idx = lower_sizes.index(req_size.lower())
                else:
                    st.warning(f"⚠️ You asked for size '{req_size}', but it's not available. Please choose another.")

        if len(sizes) <= 6:
            selected_size = st.segmented_control("Select Size", options=sizes, default=sizes[default_size_idx])
            if not selected_size:
                selected_size = sizes[default_size_idx] # Fallback if user unselects
        else:
            selected_size = st.selectbox("Select Size", options=sizes, index=default_size_idx)
            
        quantity = st.number_input("Quantity", min_value=1, max_value=10, value=int(req_quantity))
        item_cost = product.price * quantity
        st.markdown(f"<div style='margin-top: 12px; color: #94a3b8; font-size: 0.95em;'>Item Estimate: <strong style='color: #fff;'>{curr_sym}{item_cost:.0f}</strong></div>", unsafe_allow_html=True)
        
    # --- Full Width Section (Below Image) ---
    new_cart_total = st.session_state.cart_total_cost + item_cost
    
    with st.expander(f"🛒 **New Cart Total:** {curr_sym}{new_cart_total:.0f}", expanded=False):
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span style="color: #94a3b8;">Current Cart ({st.session_state.cart_quantity} items):</span>
            <span>{curr_sym}{st.session_state.cart_total_cost:.0f}</span>
        </div>
        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px; margin-bottom: 8px;">
            <span style="color: #94a3b8;">This Addition:</span>
            <span style="color: #10b981;">+{curr_sym}{item_cost:.0f}</span>
        </div>
        <div style="display: flex; justify-content: space-between; font-weight: bold;">
            <span>New Total:</span>
            <span style="color: #10b981;">{curr_sym}{new_cart_total:.0f}</span>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.cart_quantity > 0:
            st.divider()
            st.markdown("<div style='margin-bottom: 8px; font-weight: 600; color: #94a3b8; font-size: 0.85em; text-transform: uppercase;'>Currently in Cart:</div>", unsafe_allow_html=True)
            
            # Lookup product titles from memory
            prod_lookup = {}
            if "multi_search_results" in st.session_state:
                for res in st.session_state.multi_search_results:
                    for p in res.get("search_results", []):
                        prod_lookup[p.id] = p
                        
            for cart_pid, cart_qty in list(st.session_state.items_in_cart.items()):
                cart_p = prod_lookup.get(cart_pid)
                title = cart_p.title if cart_p else f"Item #{cart_pid[:6]}..."
                
                price_str = f"{curr_sym}{cart_p.price:.0f}" if cart_p else "N/A"
                
                st.markdown(f"<div style='font-size: 0.9em; font-weight: 500; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{title}</div>", unsafe_allow_html=True)
                
                c_price, c_qty, c_rem = st.columns([2.5, 4, 1.5])
                with c_price:
                    st.markdown(f"<div style='padding-top: 8px; color: #94a3b8; font-size: 0.9em;'>{price_str}</div>", unsafe_allow_html=True)
                with c_qty:
                    new_q = st.number_input("Qty", min_value=1, max_value=99, value=cart_qty, key=f"q_{cart_pid}", label_visibility="collapsed")
                    if new_q != cart_qty:
                        diff = new_q - cart_qty
                        st.session_state.items_in_cart[cart_pid] = new_q
                        if cart_p:
                            st.session_state.cart_total_cost = max(0.0, st.session_state.cart_total_cost + (cart_p.price * diff))
                        st.session_state.cart_quantity = max(0, st.session_state.cart_quantity + diff)
                        st.rerun()
                with c_rem:
                    if st.button("❌", key=f"rem_{cart_pid}", help="Remove"):
                        del st.session_state.items_in_cart[cart_pid]
                        if cart_p:
                            st.session_state.cart_total_cost = max(0.0, st.session_state.cart_total_cost - (cart_p.price * cart_qty))
                        else:
                            st.session_state.cart_total_cost = 0.0 # Safety fallback
                        st.session_state.cart_quantity = sum(st.session_state.items_in_cart.values())
                        if st.session_state.cart_quantity == 0:
                            st.session_state.shopify_cart_id = None
                        st.rerun()
                        
            st.divider()
            if st.button("🗑️ Empty Entire Cart", use_container_width=True):
                st.session_state.shopify_cart_id = None
                st.session_state.cart_quantity = 0
                st.session_state.cart_total_cost = 0.0
                st.session_state.items_in_cart = {}
                st.rerun()
    
    # Financial Guardrail Check
    if new_cart_total > st.session_state.config.max_budget:
        st.error(f"⚠️ Exceeds Hard Maximum Budget of {curr_sym}{st.session_state.config.max_budget:.0f}. Cannot proceed.")
        can_add = False
    elif new_cart_total > st.session_state.config.max_cost_hitl:
        st.markdown(f"""
        <div style="background-color: rgba(245, 158, 11, 0.1); border-left: 4px solid #f59e0b; padding: 16px; border-radius: 4px; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 1.2em; margin-right: 8px;">⚠️</span>
                <strong style="color: #f59e0b;">HITL Approval Required</strong>
            </div>
            <div style="color: #d1d5db; font-size: 0.9em;">
                This addition exceeds your auto-approval threshold of {curr_sym}{st.session_state.config.max_cost_hitl:.0f}.
                Please manually confirm before proceeding.
            </div>
        </div>
        """, unsafe_allow_html=True)
        can_add = st.checkbox("I approve this high-value addition")
    else:
        can_add = True
            
    if st.button("Confirm Add to Cart", type="primary", disabled=not can_add, use_container_width=True):
        with st.spinner("Connecting to Shopify Cart API..."):
            cart_provider = ShopifyCartProvider()
            variant_gid = variant_ids[selected_size]
            
            if st.session_state.shopify_cart_id:
                res = cart_provider.add_to_cart(st.session_state.shopify_cart_id, variant_gid, quantity)
            else:
                res = cart_provider.create_cart(variant_gid, quantity)
                
            if res.get("success"):
                st.session_state.shopify_cart_id = res["cart_id"]
                st.session_state.shopify_checkout_url = res["checkout_url"]
                st.session_state.cart_quantity = res.get("total_quantity", 0)
                st.session_state.cart_total_cost = float(res.get("cost", 0.0))
                
                # Track quantity per product
                current_qty = st.session_state.items_in_cart.get(product.id, 0)
                st.session_state.items_in_cart[product.id] = current_qty + quantity
                
                st.success("✅ Added to cart successfully!")
                import time
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Failed to add to cart: {res.get('errors')}")

if "normalization_source" not in st.session_state:
    st.session_state.normalization_source = ""

# Initialize Brain
brain = AgentBrain(
    primary_model=st.session_state.config.primary_model,
    fallback_model=st.session_state.config.fallback_model
)

# Inject custom CSS for premium UI, including Horizontal Scroll (Carousel)
st.markdown("""
<style>
/* Make Segmented Control match st.button height and stretch full width */
[data-testid="stSegmentedControl"] {
    width: 100% !important;
}
[data-testid="stSegmentedControl"] > div {
    min-height: 44px !important;
    height: 44px !important;
    width: 100% !important;
    display: flex !important;
    align-items: stretch !important;
}
[data-testid="stSegmentedControl"] label {
    flex: 1 !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    height: 100% !important;
    margin: 0 !important;
}
/* Make standard columns horizontally scrollable like a Carousel */
[data-testid="stHorizontalBlock"] {
    overflow-x: auto;
    flex-wrap: nowrap;
    padding-bottom: 10px;
}
[data-testid="column"] {
    min-width: 280px;
    flex: 0 0 auto !important;
}
/* Hide scrollbar for a cleaner Tinder-like feel */
[data-testid="stHorizontalBlock"]::-webkit-scrollbar {
    display: none;
}
[data-testid="stHorizontalBlock"] {
    -ms-overflow-style: none;
    scrollbar-width: none;
}
/* Chat Bubble Styling */
[data-testid="chatAvatarIcon-user"] {
    background-color: #059669;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background-color: rgba(5, 150, 105, 0.1);
    border-radius: 12px;
    padding: 10px;
    margin-bottom: 10px;
}
[data-testid="chatAvatarIcon-assistant"] {
    background-color: #6366f1;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background-color: rgba(99, 102, 241, 0.1);
    border-radius: 12px;
    padding: 10px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 2. Sidebar Configuration
# ------------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ System Configuration")
    
    # UI Mode
    ui_choice = st.radio(
        "UI Paradigm",
        options=["Standard (One-Shot)", "Chat (Stylist Agent)", "Voice (Coming Soon)"],
        index=0 if st.session_state.config.ui_mode == UIMode.CHAT else (0 if st.session_state.config.ui_mode == UIMode.STANDARD else 2),
        help="Switch between classic one-shot search and the new multi-turn conversational AI."
    )
    if "Chat" in ui_choice:
        st.session_state.config.ui_mode = UIMode.CHAT
    elif "Standard" in ui_choice:
        st.session_state.config.ui_mode = UIMode.STANDARD
    else:
        st.session_state.config.ui_mode = UIMode.VOICE
        
    if st.session_state.config.ui_mode in (UIMode.CHAT, UIMode.VOICE):
        st.session_state.tts_engine = st.selectbox(
            "🗣️ Voice Options",
            options=["System Native (Fast)", "Kokoro Python Repo (Local)", "Kokoro-82M (High Quality)", "Web Speech API (Browser Native)"],
            index=0,
            help="Select the Text-to-Speech engine used for Voice Mode."
        )

    st.divider()
    
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
            index=2
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
    

    st.session_state.config.max_search_results = st.slider(
        "Max Search Results (Top K)",
        min_value=5, max_value=40,
        value=st.session_state.config.max_search_results,
        help="Number of products to show in the carousel."
    )
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

    st.session_state.config.enable_vqa_scanner = st.toggle(
        "Enable VQA Scanner",
        value=st.session_state.config.enable_vqa_scanner,
        help="Master switch to allow the LLM to use the Vision model to scan graphics on shirts."
    )

    st.session_state.config.vqa_strict_filter = st.toggle(
        "Strict VQA Filtering",
        value=st.session_state.config.vqa_strict_filter,
        help="If enabled, only products that strictly pass the Text evaluation are visually scanned. If disabled, partial matches are 'rescued' and visually scanned."
    )

    st.session_state.config.truth_hierarchy = st.toggle(
        "Truth Hierarchy Override",
        value=st.session_state.config.truth_hierarchy,
        help="Prioritizes the Product Title over contradicting backend specs to prevent false rejections (e.g., when a title says 'Polo' but specs incorrectly say 'Round Neck')."
    )

    st.divider()
    st.subheader("🚚 Shipping & Logistics")
    st.session_state.config.user_location = st.selectbox(
        "Destination City (Fast Shipping)",
        options=["Not Set", "Mumbai", "Delhi", "Bengaluru", "New York", "London"],
        index=1,
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
st.title("🛍️ Rasor Conversational Commerce")

if st.session_state.cart_quantity > 0:
    c_info, c_btn = st.columns([4, 1])
    with c_info:
        st.info(f"🛒 **Cart:** {st.session_state.cart_quantity} items added. [Checkout Now]({st.session_state.shopify_checkout_url})")
    with c_btn:
        if st.button("🗑️ Clear Cart", use_container_width=True):
            st.session_state.shopify_cart_id = None
            st.session_state.shopify_checkout_url = None
            st.session_state.cart_quantity = 0
            st.session_state.cart_total_cost = 0.0
            st.session_state.items_in_cart = {}
            st.rerun()

st.caption(
    f"Active Mode: **{st.session_state.config.mode.value.upper()}** | "
    f"Data Provider: **{st.session_state.config.data_source.value}** | "
    f"HITL Trigger: **>{curr_sym}{st.session_state.config.max_cost_hitl:.2f}** | "
    f"Budget: **{curr_sym}{st.session_state.config.max_budget:.2f}**"
)

# Display Status Banner
if "last_status" in st.session_state and st.session_state.last_status:
    if "FALLBACK TRIGGERED" in st.session_state.last_status:
        st.warning(f"**Data Pipeline Notification:**\n\n{st.session_state.last_status}")
    else:
        st.success(f"**Data Source Status:** {st.session_state.last_status}")

search_clicked = False

if st.session_state.config.ui_mode == UIMode.STANDARD:
    # ------------------------------------------------------------------------------
    # 3. Standard Interface (One-Shot)
    # ------------------------------------------------------------------------------
    # Natural Language Prompt Input
    col_prompt, col_btn = st.columns([5, 1])

    with col_prompt:
        user_prompt = st.text_input(
            "Enter your natural shopping intent:",
            value="Solid plain black t-shirt for men",
            placeholder="e.g. Solid plain black t-shirt for men",
            label_visibility="collapsed"
        )

    with col_btn:
        search_clicked = st.button("🚀 Run Agent", type="primary", use_container_width=True)

    if search_clicked and user_prompt:
        st.session_state.chat_ready_for_search = True
        
elif st.session_state.config.ui_mode == UIMode.CHAT:
    # ------------------------------------------------------------------------------
    # 3. Chat Interface (Stylist Agent)
    # ------------------------------------------------------------------------------
    if "pending_user_input" not in st.session_state:
        st.session_state.pending_user_input = None

    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # If it's the very last message in the list and from the assistant, render chips
            if i == len(st.session_state.messages) - 1 and msg["role"] == "assistant" and msg.get("suggested_options"):
                cols = st.columns(len(msg["suggested_options"]) + 1)
                for idx, opt in enumerate(msg["suggested_options"]):
                    with cols[idx]:
                        if st.button(opt, key=f"chip_{i}_{idx}", use_container_width=True):
                            st.session_state.pending_user_input = opt
                            st.rerun()
            
    prompt = st.chat_input("What are you looking for today?")
    if prompt:
        st.session_state.pending_user_input = prompt
        
    if st.session_state.pending_user_input:
        user_text = st.session_state.pending_user_input
        st.session_state.pending_user_input = None
        
        st.session_state.messages.append({"role": "user", "content": user_text})
        with st.chat_message("user"):
            st.markdown(user_text)
            
        with st.chat_message("assistant"):
            with st.spinner("Stylist is thinking..."):
                response = st.session_state.stylist_agent.process_turn(user_text, st.session_state.messages[:-1])
                st.markdown(response.message)
                st.session_state.messages.append({"role": "assistant", "content": response.message, "suggested_options": response.suggested_options})
                
                if response.ready_for_search:
                    st.session_state.current_user_prompt = response.updated_query
                    st.session_state.chat_ready_for_search = True
                    search_clicked = True
                    
                    # Force rerun to cleanly reset the input and render search outside the prompt block
                    st.rerun()
                else:
                    st.session_state.chat_ready_for_search = False
                    search_clicked = False
                    st.session_state.current_user_prompt = None
                    st.rerun()
                    
    user_prompt = st.session_state.current_user_prompt

elif st.session_state.config.ui_mode == UIMode.VOICE:
    if "current_user_prompt" not in st.session_state:
        st.session_state.current_user_prompt = None
        
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    import streamlit.components.v1 as components
    
    # Declare the custom VAD component
    try:
        vad_mic = components.declare_component("vad_mic", path="frontend/components/vad_mic")
    except Exception as e:
        st.error(f"Could not load custom component: {e}")
        vad_mic = None
        
    # Inject CSS to make the VAD component float at the bottom above the chat input
    st.markdown("""
        <style>
        iframe[title="frontend.components.vad_mic.vad_mic"] {
            position: fixed;
            bottom: 85px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 999999;
            width: 300px !important;
            height: 70px !important;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.1);
            background-color: rgba(30, 30, 30, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0px 10px 30px rgba(0,0,0,0.5);
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Play queued TTS audio from the previous run
    if "tts_audio_bytes" in st.session_state:
        st.audio(st.session_state.tts_audio_bytes, format="audio/wav", autoplay=True)
        del st.session_state.tts_audio_bytes
        
    tts_wait_ms = st.session_state.get("tts_wait_ms", 0)
    if tts_wait_ms > 0:
        st.session_state.tts_wait_ms = 0
        
    force_stop_mic = st.session_state.get("force_stop_mic", False)
    if force_stop_mic:
        st.session_state.force_stop_mic = False
        
    vad_state = vad_mic(wait_ms=tts_wait_ms, force_stop=force_stop_mic, key="vad_mic") if vad_mic else None
    prompt = st.chat_input("Or type here...")
    
    new_prompt = None
    if vad_state and vad_state.get("audio"):
        import base64
        import tempfile
        import os
        
        audio_data = base64.b64decode(vad_state["audio"])
        current_audio_hash = hash(audio_data)
        
        if st.session_state.get("last_audio_hash") != current_audio_hash:
            st.session_state.last_audio_hash = current_audio_hash
            with st.spinner("Local STT active..."):
                try:
                    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                        f.write(audio_data)
                        tmp_path = f.name
                        
                    try:
                        import whisper
                        model = whisper.load_model("tiny.en")
                        result = model.transcribe(tmp_path)
                        new_prompt = result["text"].strip()
                    except ImportError:
                        st.error("OpenAI Whisper is not installed locally. Please run `pip install openai-whisper` on your Mac.")
                        new_prompt = "Looking for a black t-shirt" # Fallback
                    finally:
                        try: os.remove(tmp_path)
                        except: pass
                except Exception as e:
                    st.error(f"STT failed: {e}")
                    
    if prompt:
        new_prompt = prompt
        
    search_clicked = False
    
    # Render TTS for the very first greeting if it hasn't been played
    if "greeting_played" not in st.session_state and len(st.session_state.messages) > 0:
        st.session_state.greeting_played = True
        greeting_msg = st.session_state.messages[0]["content"]
        import os
        try:
            if st.session_state.get("tts_engine") == "System Native (Fast)":
                import subprocess
                subprocess.Popen(["say", greeting_msg])
                duration_ms = int(len(greeting_msg.split()) / 2.5 * 1000)
                st.session_state.tts_wait_ms = duration_ms + 1000
                st.rerun()
            else:
                import soundfile as sf
                import base64
                import os
                
                k_model = get_kokoro_model()
                if k_model:
                    samples, sample_rate = k_model.create(
                        greeting_msg, voice="af_bella", speed=1.0, lang="en-us"
                    )
                    sf.write("greeting.wav", samples, sample_rate)
                    with open("greeting.wav", "rb") as f:
                        st.session_state.tts_audio_bytes = f.read()
                    os.remove("greeting.wav")
                    
                    duration_ms = int((len(samples) / sample_rate) * 1000)
                    st.session_state.tts_wait_ms = duration_ms + 1000
                    st.rerun()
        except Exception as e:
            print("Greeting TTS Error:", e)
            
    if new_prompt:
        st.session_state.messages.append({"role": "user", "content": new_prompt})
        with st.chat_message("user"):
            st.markdown(new_prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("Stylist is thinking..."):
                response = st.session_state.stylist_agent.process_turn(new_prompt, st.session_state.messages[:-1])
                st.markdown(response.message)
                st.session_state.messages.append({"role": "assistant", "content": response.message})
                
                if response.ready_for_search:
                    st.session_state.current_user_prompt = response.updated_query
                    st.session_state.chat_ready_for_search = True
                    search_clicked = True
                    st.session_state.force_stop_mic = True
                else:
                    st.session_state.chat_ready_for_search = False
                    search_clicked = False
                    st.session_state.current_user_prompt = None
                    
                # TTS Generation
                try:
                    if st.session_state.get("tts_engine") == "System Native (Fast)":
                        import subprocess
                        subprocess.Popen(["say", response.message])
                        duration_ms = int(len(response.message.split()) / 2.5 * 1000)
                        st.session_state.tts_wait_ms = duration_ms + 1000
                        st.rerun()
                    else:
                        import os
                        import soundfile as sf
                        
                        k_model = get_kokoro_model()
                        if k_model:
                            samples, sample_rate = k_model.create(
                                response.message, voice="af_bella", speed=1.0, lang="en-us"
                            )
                            sf.write("response.wav", samples, sample_rate)
                            with open("response.wav", "rb") as f:
                                st.session_state.tts_audio_bytes = f.read()
                            os.remove("response.wav")
                            
                            duration_ms = int((len(samples) / sample_rate) * 1000)
                            st.session_state.tts_wait_ms = duration_ms + 1000
                            st.rerun()
                        else:
                            st.error("Kokoro model files not found. Did you download them?")
                except Exception as e:
                    print("Local TTS Error:", e)

    user_prompt = st.session_state.current_user_prompt


# ------------------------------------------------------------------------------
# 4. Multi-Stage Pipeline Execution
# ------------------------------------------------------------------------------
# Run the pipeline if search is ready, OR if we have cached results for the current prompt.
# In Chat mode, we only run stage 1-3 if search_clicked was true OR if it's a rerun.
# Actually, the logic below handles caching inside the providers/brain, but we rely on st.session_state.search_results.
if (search_clicked or st.session_state.get("chat_ready_for_search")) and user_prompt:
    
    if st.session_state.config.ui_mode == UIMode.CHAT:
        assistant_chat = st.chat_message("assistant")
    else:
        import contextlib
        assistant_chat = contextlib.nullcontext()
        
    with assistant_chat:
        with st.spinner("🤖 Stage 1: LLM Normalizing prompt into Canonical Enums..."):
            multi_query, norm_source = brain.normalize_intent(user_prompt, budget=st.session_state.config.max_budget)
            st.session_state.canonical_query = multi_query
            st.session_state.normalization_source = norm_source

        # Store multiple result sets here
        st.session_state.multi_search_results = []
        
        if st.session_state.config.data_source == DataSourceType.BEWAKOOF_LIVE_API:
            provider = BewakoofCatalogProvider()
        elif st.session_state.config.data_source == DataSourceType.SHOPIFY_STOREFRONT_LIVE_API:
            provider = ShopifyCatalogProvider()
        elif st.session_state.config.data_source == DataSourceType.GOOGLE_SHOPPING_SCRAPER:
            provider = GoogleShoppingScraper(max_retries=3)
        else:
            provider = DevCatalogProvider()
            
        import math
        def bayesian_score(p):
            return p.rating * math.log10(p.review_count + 1)
            
        for idx, canonical in enumerate(multi_query.items_to_buy):
            with st.spinner(f"📡 Stage 2: Querying {st.session_state.config.data_source.value} for {canonical.category.value.title()}..."):
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
                    limit=40
                )
        
            stage3_text = f"🧠 Stage 3: Validating {canonical.category.value.title()} relevance..."
            if st.session_state.config.enable_vqa_scanner and canonical.has_visual_intent:
                stage3_text = f"👁️ Stage 3: Exhaustive VQA Scanning for {canonical.category.value.title()}..."
    
            with st.spinner(stage3_text):
                raw_candidates.sort(key=bayesian_score, reverse=True)
                llm_candidates = raw_candidates[:]
                
                # Deep Enrichment
                if st.session_state.config.enable_deep_enrichment:
                    with st.spinner(f"🔍 Deep Enriching top {st.session_state.config.max_deep_fetches} candidates..."):
                        import concurrent.futures
                        top_to_enrich = llm_candidates[:st.session_state.config.max_deep_fetches]
                        current_location = st.session_state.config.user_location
                        
                        def enrich(prod):
                            provider.enrich_product(prod)
                            if canonical.fast_shipping_requested and current_location != "Not Set":
                                from src.data.logistics import calculate_shipping_days
                                prod.shipping_days = calculate_shipping_days(current_location)
                                prod.specs["fast_delivery_available"] = (prod.shipping_days <= 2)
                            return prod
                            
                        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                            list(executor.map(enrich, top_to_enrich))
                
                # Aggressive Text-First Negation Filter
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
        
                validated_products, evaluations = brain.evaluate_candidates(
                    user_prompt, 
                    llm_candidates, 
                    canonical=canonical,
                    vqa_strict_filter=st.session_state.config.vqa_strict_filter,
                    enable_vqa_scanner=st.session_state.config.enable_vqa_scanner,
                    truth_hierarchy=st.session_state.config.truth_hierarchy
                )
                
                eval_map = {e.product_id: e for e in evaluations}
                bayesian_scores = [bayesian_score(p) for p in validated_products]
                max_b = max(bayesian_scores, default=1.0) or 1.0
                
                def composite_score(p):
                    llm_score = eval_map[p.id].match_score if p.id in eval_map else 0.5
                    b_score = bayesian_score(p) / max_b
                    return llm_score * 0.7 + b_score * 0.3
                
                validated_products.sort(key=composite_score, reverse=True)
                search_results = validated_products[:st.session_state.config.max_search_results]
                
                displayed_ids = {p.id for p in search_results}
                rejected_products = [p for p in raw_candidates if p.id not in displayed_ids]
                rejected_products.sort(
                    key=lambda p: (eval_map[p.id].match_score if p.id in eval_map else 0.0, bayesian_score(p)),
                    reverse=True
                )
                
                st.session_state.multi_search_results.append({
                    "canonical": canonical,
                    "search_results": search_results,
                    "rejected_products": rejected_products,
                    "evaluations": evaluations
                })
        
        if hasattr(provider, "last_status_message"):
            st.session_state.last_status = provider.last_status_message
        else:
            st.session_state.last_status = "🟢 Loaded directly from Dev Mock Catalog."
            
        st.session_state.chat_ready_for_search = False

# ------------------------------------------------------------------------------
# 5. Intent Normalization Inspector (Stage 1 Visualization)
# ------------------------------------------------------------------------------
if st.session_state.canonical_query:
    multi_q = st.session_state.canonical_query
    
    with st.expander(f"🤖 Stage 1: LLM Normalized Taxonomy ({st.session_state.normalization_source})", expanded=True):
        st.write(f"**Extracted {len(multi_q.items_to_buy)} Target Items**")
        for idx, q in enumerate(multi_q.items_to_buy):
            st.write(f"--- **Item {idx+1}: {q.category.value.title()}** ---")
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
            with col1: st.metric("👤 Gender", q.gender.value.title())
            with col2: st.metric("🏷️ Category", q.category.value.title())
            with col3: st.metric("🎉 Occasion", getattr(q, "occasion", "Any").value.title() if hasattr(q, "occasion") and hasattr(getattr(q, "occasion", None), "value") else "Any")
            with col4: st.metric("🎨 Color", q.color.value)
            with col5: st.metric("🎨 Design Pattern", q.design.value)
            with col6: st.metric("📏 Size", q.size if q.size else "Any")
            with col7: st.metric("👕 Fit", q.fit.value.replace(" Fit", ""))
            with col8: st.metric("💰 Budget Cap", f"{curr_sym}{q.max_price:.0f}" if q.max_price else "No Cap")
            
        if multi_q.owned_items:
            st.write(f"**Owned Items Context:** {len(multi_q.owned_items)} items detected.")

# ------------------------------------------------------------------------------
# 6. Validated Products Visualizer (Stage 3 Output)
# ------------------------------------------------------------------------------
if st.session_state.get("multi_search_results"):
    
    if "carousel_indices" not in st.session_state:
        st.session_state.carousel_indices = {}
        
    for item_idx, result_set in enumerate(st.session_state.multi_search_results):
        canonical = result_set["canonical"]
        search_results = result_set["search_results"]
        evaluations = result_set["evaluations"]
        
        st.subheader(f"🔥 Top {canonical.category.value.title()} Picks ({len(search_results)} Matches)")
        
        dict_key = f"carousel_index_{item_idx}"
        if dict_key not in st.session_state.carousel_indices:
            st.session_state.carousel_indices[dict_key] = 0
            
        idx = st.session_state.carousel_indices[dict_key]
        
        # Navigation Row
        nav_col1, nav_col2, nav_spacer, nav_col3, nav_col4 = st.columns([1.5, 2.5, 4, 1.5, 1.5])
        with nav_col1:
            if st.button(f"⬅️ Prev", key=f"prev_{item_idx}", disabled=(idx == 0), use_container_width=True):
                st.session_state.carousel_indices[dict_key] -= st.session_state.grid_columns
                st.rerun()
        with nav_col2:
            if st.button(f"⚖️ Compare ({len(st.session_state.compare_list)})", key=f"compare_btn_{item_idx}", use_container_width=True):
                compare_products_dialog()
        with nav_col3:
            grid_opts = {2: "||", 3: "|||", 4: "||||"}
            new_grid = st.segmented_control(
                "Grid Size",
                options=[2, 3, 4],
                format_func=lambda x: grid_opts[x],
                default=st.session_state.grid_columns,
                key=f"grid_size_{item_idx}",
                label_visibility="collapsed"
            )
            if new_grid and new_grid != st.session_state.grid_columns:
                st.session_state.grid_columns = new_grid
                st.rerun()
        with nav_col4:
            if st.button(f"Next ➡️", key=f"next_{item_idx}", disabled=(idx + st.session_state.grid_columns >= len(search_results)), use_container_width=True):
                st.session_state.carousel_indices[dict_key] += st.session_state.grid_columns
                st.rerun()
                
        items_per_page = st.session_state.grid_columns
        cols = st.columns(items_per_page)
        eval_map = {e.product_id: e for e in evaluations}
        
        current_view = search_results[idx : idx + items_per_page]

        for i, prod in enumerate(current_view):
            with cols[i]:
                with st.container(border=True):
                    img_url = prod.specs.get("image_url") or prod.specs.get("display_image") or "https://via.placeholder.com/400x500"
                    
                    ev = eval_map.get(prod.id)
                    match_pct = int(ev.match_score * 100) if ev else 0
                    badge_color = "#10b981" if match_pct >= 70 else ("#f59e0b" if match_pct >= 40 else "#ef4444")
                    
                    mrp_val = prod.specs.get("mrp_inr")
                    mrp_html = f"<span style='text-decoration: line-through; color: #9ca3af; font-size: 0.85em; margin-left: 8px;'>{curr_sym}{mrp_val:.0f}</span>" if mrp_val and mrp_val > prod.price else ""
                    
                    hitl_badge = ""
                    if prod.price > st.session_state.config.max_cost_hitl:
                        hitl_badge = '<div style="position: absolute; bottom: 12px; left: 12px; background: rgba(239, 68, 68, 0.9); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8em; font-weight: bold; z-index: 2; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.2);">⚠️ Requires Approval</div>'
                    
                    raw_html = f"""<div style="position: relative; border-radius: 16px; overflow: hidden; margin-bottom: 12px; background: rgba(30, 30, 30, 0.4); border: 1px solid rgba(255, 255, 255, 0.1); transition: transform 0.2s;">
<div style="position: absolute; top: 12px; right: 12px; background: {badge_color}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8em; font-weight: bold; z-index: 2; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
🧠 {match_pct}% Match
</div>
<div style="height: 380px; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; background: #000;">
<img src="{img_url}" style="width: 100%; height: 100%; object-fit: cover;" />
{hitl_badge}
</div>
<div style="padding: 16px;">
<h4 style="margin: 0 0 8px 0; font-size: 1.05em; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; opacity: 0.9;">{prod.title}</h4>
<div style="font-size: 1.3em; font-weight: bold; margin-bottom: 6px;">
{curr_sym}{prod.price:.0f} {mrp_html}
</div>
<div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.9em; opacity: 0.7;">
<span>⭐ {prod.rating:.1f} ({prod.review_count})</span>
<span>{("🚀 Express" if prod.shipping_days <= 2 else "🚚 Std") if hasattr(prod, 'shipping_days') and prod.shipping_days else ""}</span>
</div>
</div>
</div>"""
                    st.markdown(raw_html.replace('\n', '').strip(), unsafe_allow_html=True)

                        
                    is_compared = prod.id in st.session_state.compare_list
                    if st.checkbox("⚖️ Compare", value=is_compared, key=f"cmp_{item_idx}_{prod.id}"):
                        st.session_state.compare_list[prod.id] = prod
                    elif prod.id in st.session_state.compare_list:
                        del st.session_state.compare_list[prod.id]
                        
                    if prod.id in st.session_state.items_in_cart:
                        btn_label = f"✅ {st.session_state.items_in_cart[prod.id]} In Cart"
                    else:
                        btn_label = "🛒 Add to Cart"
                        
                    colX, colY = st.columns(2)
                    with colX:
                        if st.button(btn_label, key=f"add_{item_idx}_{prod.id}", use_container_width=True):
                            add_to_cart_dialog(prod)
                    with colY:
                        if prod.source_url:
                            st.link_button("View ↗", prod.source_url, use_container_width=True)

        
        # Page Indicator Dots
        total_pages = (len(search_results) + items_per_page - 1) // items_per_page if items_per_page > 0 else 1
        current_page = idx // items_per_page
        dots = ["●" if p == current_page else "○" for p in range(total_pages)]
        st.markdown(f"<div style='text-align: center; font-size: 1.5em; letter-spacing: 5px; opacity: 0.6; margin-top: 10px; margin-bottom: 20px;'>{''.join(dots)}</div>", unsafe_allow_html=True)

    with st.expander("🔍 Inspect Raw Canonical Query & Evaluations"):
        st.json({
            "multi_canonical_query": st.session_state.canonical_query.model_dump() if st.session_state.canonical_query else None,
            "results": [{
                "category": r["canonical"].category.value,
                "products_returned": [p.model_dump() for p in r["search_results"]]
            } for r in st.session_state.multi_search_results]
        })


# 7. Discarded Products Visualizer (Extra products that failed QA / overflow)
# ------------------------------------------------------------------------------
if st.session_state.get("multi_search_results"):
    # Flatten rejected products and evaluations from all items
    all_rejected = []
    local_eval_map = {}
    for rs in st.session_state.multi_search_results:
        all_rejected.extend(rs.get("rejected_products", []))
        if rs.get("evaluations"):
            for e in rs["evaluations"]:
                local_eval_map[e.product_id] = e
                
    if all_rejected:
        st.markdown("---")
        rejected = all_rejected
        
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
                                
                                if prod.id in st.session_state.items_in_cart:
                                    btn_label_rej = f"✅ {st.session_state.items_in_cart[prod.id]} In Cart - Add More"
                                else:
                                    btn_label_rej = "🛒 Add to Cart"
                                    
                                if st.button(btn_label_rej, key=f"add_rej_{prod.id}", use_container_width=True):
                                    add_to_cart_dialog(prod)
                                if prod.source_url:
                                    st.link_button("View ↗", prod.source_url, use_container_width=True)



# ------------------------------------------------------------------------------
# 7. Discarded Products Visualizer (Extra products that failed QA / overflow)
# ------------------------------------------------------------------------------
if st.session_state.get("multi_search_results"):
    # Flatten rejected products from all items
    all_rejected = []
    for rs in st.session_state.multi_search_results:
        all_rejected.extend(rs.get("rejected_products", []))
        
    if all_rejected:
        with st.expander(f"🗑️ View Discarded / Low Relevance Candidates ({len(all_rejected)})"):
            st.markdown("These products were fetched but ranked poorly by the LLM (score < 50%) or were overflow candidates.")
            
            # Simple grid
            rej_cols = st.columns(4)
            for i, p in enumerate(all_rejected):
                with rej_cols[i % 4]:
                    img = p.specs.get("image_url") or p.specs.get("display_image") or "https://via.placeholder.com/200"
                    st.markdown(f"""
                    <div style="margin-bottom: 15px; border: 1px solid #333; padding: 8px; border-radius: 8px; opacity: 0.7;">
                        <img src="{img}" style="width: 100%; height: 120px; object-fit: cover; border-radius: 4px;" />
                        <div style="font-size: 0.8em; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{p.title}</div>
                        <div style="font-size: 0.9em; font-weight: bold;">{curr_sym}{p.price:.0f}</div>
                    </div>
                    """, unsafe_allow_html=True)
