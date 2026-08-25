"""
Shopify Headless Storefront API Catalog Provider.

Search Strategy (5-tier progressive relaxation):
  1. Structured `products(query:)` with Storefront-valid predicates
     (title, tag, product_type — NOT variants.price, which is Admin API only).
  2. Storefront `search(query:)` with full-text relevance — better for user keywords.
  3. Per-term union search: split query into individual words, OR results together.
  4. Product-type / category only search (broadest structured filter).
  5. Full catalog fallback (all products).

Post-filter pass applied after any fetch:
  color, size, max_price (client-side), fit, design — same as BewakoofCatalogProvider.

Same search_products() signature as Bewakoof & DevCatalog — fully plug-in compatible.
"""

import os
import json
from typing import Any, Dict, List, Optional, Set
from dotenv import load_dotenv
import requests

from src.agent.state import Product
from src.data.base import BaseCatalogProvider

_LOCAL_RATINGS_CACHE: Dict[str, Dict[str, float]] = {}
try:
    with open("/Users/aai/Desktop/Rasor/src/data/ratings_cache.json", "r") as f:
        _LOCAL_RATINGS_CACHE = json.load(f)
except FileNotFoundError:
    pass

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SHOPIFY_API_VERSION = "2024-04"
_SKIP_VALUES: Set[str] = {"any", "all", "general", "none", "", "unknown"}
_NOISE_WORDS: Set[str] = {
    "for", "a", "an", "the", "in", "under", "size", "rs", "inr", "usd",
    "and", "or", "with", "some", "want", "looking", "need", "get", "give",
    "plain", "solid", "basic"  # these are handled separately as design attributes
}
_KNOWN_COLORS = [
    "black", "white", "blue", "red", "green", "grey", "gray",
    "yellow", "orange", "maroon", "beige", "brown", "purple", "pink",
    "navy", "cyan", "volt", "teal", "olive", "coral", "lavender",
]


def _skip(val: Optional[str]) -> bool:
    """Returns True if a value should be ignored (not worth filtering on)."""
    return not val or val.lower().strip() in _SKIP_VALUES


# ---------------------------------------------------------------------------
# Shared GraphQL fragment for product fields (DRY)
# ---------------------------------------------------------------------------
_PRODUCT_FIELDS_FRAGMENT = """
fragment ProductFields on Product {
  id
  handle
  title
  description
  productType
  vendor
  tags
  availableForSale
  variants(first: 30) {
    edges {
      node {
        id
        title
        sku
        price { amount currencyCode }
        compareAtPrice { amount }
        availableForSale
      }
    }
  }
  images(first: 3) {
    edges {
      node { url altText }
    }
  }
}
"""


class ShopifyCatalogProvider(BaseCatalogProvider):
    """
    Live Shopify Storefront GraphQL API catalog provider.

    Uses 5-tier progressive search so queries never silently return 0 results.
    """

    def __init__(self):
        self.domain = os.getenv("SHOPIFY_STORE_DOMAIN", "")
        self.token = os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN", "")

        if not self.domain or not self.token:
            print("[Shopify] WARNING: Missing SHOPIFY_STORE_DOMAIN or SHOPIFY_STOREFRONT_ACCESS_TOKEN in .env")

        self.endpoint = f"https://{self.domain}/api/{SHOPIFY_API_VERSION}/graphql.json"
        self.headers = {
            "X-Shopify-Storefront-Access-Token": self.token,
            "Content-Type": "application/json",
        }
        self.last_status_message: str = "Initialized"
        self.last_used_source: str = "shopify_storefront_api"

    # ------------------------------------------------------------------
    # Network layer
    # ------------------------------------------------------------------

    def _gql(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query and return the parsed JSON."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        try:
            res = requests.post(self.endpoint, headers=self.headers, json=payload, timeout=12)
            res.raise_for_status()
            data = res.json()
            if "errors" in data:
                print(f"[Shopify] GraphQL errors: {data['errors']}")
            return data
        except requests.exceptions.HTTPError as e:
            print(f"[Shopify] HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            print(f"[Shopify] Request error: {e}")
        return {}

    # ------------------------------------------------------------------
    # Search tier implementations
    # ------------------------------------------------------------------

    def _fetch_via_products_query(self, query_str: str, limit: int) -> List[Dict]:
        """
        Tier 1 & 4: Shopify `products(query:...)` — structured predicates.
        Valid predicates: title:, tag:, product_type:, available_for_sale:
        NOTE: variants.price is Admin API only — NOT supported here.
        """
        gql = _PRODUCT_FIELDS_FRAGMENT + """
        query ListProducts($q: String!, $first: Int!) {
          products(first: $first, query: $q, sortKey: RELEVANCE) {
            edges { node { ...ProductFields } }
          }
        }
        """
        data = self._gql(gql, {"q": query_str, "first": limit})
        return [e["node"] for e in data.get("data", {}).get("products", {}).get("edges", [])]

    def _fetch_via_search(self, query_str: str, limit: int) -> List[Dict]:
        """
        Tier 2: Shopify `search(query:...)` — full-text relevance search.
        Best for user keyword queries (supports synonym groups, partial matching).
        """
        gql = _PRODUCT_FIELDS_FRAGMENT + """
        query SearchProducts($q: String!, $first: Int!, $prefix: SearchPrefixQueryType) {
          search(query: $q, types: [PRODUCT], first: $first, prefix: $prefix) {
            totalCount
            edges {
              node {
                ... on Product { ...ProductFields }
              }
            }
          }
        }
        """
        data = self._gql(gql, {"q": query_str, "first": limit, "prefix": "LAST"})
        edges = data.get("data", {}).get("search", {}).get("edges", [])
        return [e["node"] for e in edges if e.get("node")]

    def _fetch_all_products(self, limit: int) -> List[Dict]:
        """Tier 5: Full catalog dump — last resort fallback."""
        return self._fetch_via_products_query("available_for_sale:true", limit)

    # ------------------------------------------------------------------
    # Query builder
    # ------------------------------------------------------------------

    def _build_products_query(
        self,
        keywords: List[str],
        category: Optional[str],
        gender: Optional[str],
        fandom: Optional[str],
        color: Optional[str],
    ) -> str:
        """
        Builds a Storefront API `products(query:)` predicate string.
        Uses only predicates that actually work on the Storefront API:
          - title:TERM
          - tag:TERM  (AND-joined for specificity)
          - product_type:TYPE
          - available_for_sale:true
        """
        parts: List[str] = []

        # Add clean keyword terms (Shopify does full-text across title+desc+tags)
        clean_kw = [w for w in keywords if w not in _NOISE_WORDS and len(w) > 1]
        if clean_kw:
            # Join multiple keywords with AND so Shopify narrows down results
            parts.append(" AND ".join(clean_kw))

        if not _skip(category):
            parts.append(f"product_type:{category}")

        if not _skip(gender):
            parts.append(f"tag:{gender}")

        if not _skip(fandom):
            parts.append(f"tag:{fandom}")

        # Note: color as tag is only useful if merchant actually uses color tags
        # (common on real stores, not on Shopify demo stores)
        if not _skip(color):
            parts.append(f"tag:{color}")

        return " AND ".join(parts) if parts else "available_for_sale:true"

    def _build_search_query(
        self, keywords: List[str], category: Optional[str], gender: Optional[str]
    ) -> str:
        """
        Builds a `search()` query — free text, more forgiving than products(query:).
        Shopify's search engine handles synonyms, stemming, partial matches.
        """
        terms: List[str] = []
        clean_kw = [w for w in keywords if w not in _NOISE_WORDS and len(w) > 1]
        if clean_kw:
            terms.extend(clean_kw)
        if not _skip(category):
            terms.append(category)
        if not _skip(gender):
            terms.append(gender)
        return " ".join(terms) if terms else ""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        gender: Optional[str] = None,
        color: Optional[str] = None,
        size: Optional[str] = None,
        design: Optional[str] = None,
        fandom: Optional[str] = None,
        fit: Optional[str] = None,
        sleeve: Optional[str] = None,
        fabric: Optional[str] = None,
        neck: Optional[str] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        merchant: Optional[str] = None,
        limit: int = 20,
        **kwargs,
    ) -> List[Product]:
        """
        5-tier progressive search — guarantees results even on sparse catalogs.
        """
        # Parse keywords from raw query
        raw_keywords = [w.lower().strip(".,!?") for w in (query or "").split() if len(w) > 1]
        fetch_limit = min(limit * 5, 100)  # Fetch generously for post-filter

        # ── Tier 1: Structured products(query:) ──────────────────────────────
        structured_q = self._build_products_query(
            raw_keywords, category, gender, fandom, color
        )
        print(f"🛍️ [Shopify Tier 1] products(query: '{structured_q}')")
        raw_nodes = self._fetch_via_products_query(structured_q, fetch_limit)

        # ── Tier 2: Storefront search() full-text ────────────────────────────
        if not raw_nodes:
            search_q = self._build_search_query(raw_keywords, category, gender)
            print(f"🛍️ [Shopify Tier 2] search(query: '{search_q}')")
            raw_nodes = self._fetch_via_search(search_q, fetch_limit)

        # ── Tier 3: Per-keyword union (split & OR) ───────────────────────────
        if not raw_nodes:
            print(f"🛍️ [Shopify Tier 3] Per-term union search")
            seen_ids: Set[str] = set()
            union_nodes: List[Dict] = []
            # Try each meaningful keyword individually
            for kw in raw_keywords:
                if kw in _NOISE_WORDS or len(kw) < 3:
                    continue
                batch = self._fetch_via_products_query(kw, 20)
                if not batch:
                    batch = self._fetch_via_search(kw, 20)
                for node in batch:
                    nid = node.get("id", "")
                    if nid not in seen_ids:
                        seen_ids.add(nid)
                        union_nodes.append(node)
            raw_nodes = union_nodes

        # ── Tier 4: Category / product-type only ─────────────────────────────
        if not raw_nodes and not _skip(category):
            print(f"🛍️ [Shopify Tier 4] product_type:{category}")
            raw_nodes = self._fetch_via_products_query(f"product_type:{category}", fetch_limit)

        # ── Tier 5: Full catalog fallback ─────────────────────────────────────
        if not raw_nodes:
            print(f"🛍️ [Shopify Tier 5] Full catalog fallback")
            raw_nodes = self._fetch_all_products(fetch_limit)

        # ── Map to canonical Products ─────────────────────────────────────────
        all_products: List[Product] = []
        for node in raw_nodes:
            p = self._map_to_product(node, raw_keywords, gender=gender, color=color)
            if p:
                all_products.append(p)

        print(f"   → {len(all_products)} mapped before post-filter")

        # ── Post-filter pass (client-side precision) ──────────────────────────

        # Price filter (most important — apply first to reduce set)
        if max_price is not None:
            all_products = [p for p in all_products if p.price <= max_price]

        # Color (check both tags and specs)
        if not _skip(color):
            cl = color.lower()
            filtered = [
                p for p in all_products
                if cl in " ".join(p.tags).lower() or cl in p.specs.get("color", "").lower()
            ]
            if filtered:
                all_products = filtered
            # else: color filter produced 0 — keep all (avoid over-filtering)

        # Size (only filter if sizes are actually populated)
        if size:
            sz = size.upper()
            filtered = [
                p for p in all_products
                if not p.specs.get("available_sizes")  # keep if no size info (can't reject)
                or sz in [s.upper() for s in p.specs.get("available_sizes", [])]
            ]
            if filtered:
                all_products = filtered

        # Fit
        if not _skip(fit):
            fl = fit.lower()
            filtered = [
                p for p in all_products
                if fl in " ".join(p.tags).lower()
                or fl in p.specs.get("fit", "").lower()
                or fl in p.title.lower()
            ]
            if filtered:
                all_products = filtered

        # Design
        if not _skip(design):
            dl = design.lower()
            filtered = [
                p for p in all_products
                if dl in " ".join(p.tags).lower()
                or dl in p.title.lower()
                or dl in (p.description or "").lower()
            ]
            if filtered:
                all_products = filtered

        # ── Status message ────────────────────────────────────────────────────
        filter_parts: List[str] = []
        if not _skip(gender): filter_parts.append(gender.title())
        if not _skip(color): filter_parts.append(color)
        if not _skip(category): filter_parts.append(category)
        if not _skip(fandom): filter_parts.append(f"Theme:{fandom}")
        if size: filter_parts.append(f"Size:{size}")
        if max_price: filter_parts.append(f"≤${max_price:.0f}")

        count = len(all_products)
        if count:
            label = f" [{' | '.join(filter_parts)}]" if filter_parts else ""
            self.last_status_message = (
                f"🟢 {count} products{label} from Shopify '{self.domain}'"
            )
        else:
            self.last_status_message = (
                f"⚠️ 0 products found in Shopify store even after 5-tier progressive search. "
                f"The store may have no products matching '{query}'."
            )

        self.last_used_source = "shopify_storefront_api"
        print(self.last_status_message)
        return all_products[:limit]

    # ------------------------------------------------------------------
    # Single product fetch (for rigorous comparison phase)
    # ------------------------------------------------------------------

    def enrich_product(self, product: Product) -> Product:
        """
        Fetches deep details for a single product. For Shopify, we cross-reference
        the original Bewakoof API using the bewakoof_id to fetch the rich storytelling description.
        """
        bewakoof_id = product.specs.get("bewakoof_id")
        
        # 1. Fetch rich description from Bewakoof if possible
        if bewakoof_id:
            import time
            import requests
            url = f"https://api-prod.bewakoof.com/v2/product/{bewakoof_id}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "App": "ios"
            }
            delay = 0.3
            max_delay = 1.5
            while delay <= max_delay:
                try:
                    resp = requests.get(url, headers=headers, timeout=4)
                    if resp.status_code == 200:
                        data = resp.json()
                        # Override mock rating with true live rating if available!
                        ratings = data.get("ratings")
                        if ratings and isinstance(ratings, dict):
                            product.rating = float(ratings.get("avg") or product.rating)
                            product.review_count = int(ratings.get("count") or product.review_count)
                        
                        desc = data.get("description")
                        if desc and isinstance(desc, dict):
                            product.rich_description = desc.get("heading")
                        break
                    elif resp.status_code in (403, 429, 500, 502, 503, 504):
                        time.sleep(delay)
                        delay *= 2
                    else:
                        break
                except Exception as e:
                    time.sleep(delay)
                    delay *= 2

        # 2. Also try fetching from Shopify Storefront as a fallback or for non-Bewakoof products
        gid = product.specs.get("shopify_gid")
        if not gid:
            raw_id = product.id.replace("SHPF-", "")
            gid = raw_id if raw_id.startswith("gid://") else f"gid://shopify/Product/{raw_id}"

        gql = _PRODUCT_FIELDS_FRAGMENT + """
        query GetProduct($id: ID!) {
          product(id: $id) { ...ProductFields }
        }
        """
        try:
            data = self._gql(gql, {"id": gid})
            node = data.get("data", {}).get("product")
            if node and not product.rich_description:
                desc_html = node.get("descriptionHtml", "")
                if desc_html:
                    import re
                    clean_desc = re.sub('<[^<]+?>', '', desc_html).strip()
                    product.rich_description = clean_desc[:250]
        except Exception as e:
            print(f"[Shopify] Enrich failed for {gid}: {e}")
        
        product.enriched = True
        return product

    # ------------------------------------------------------------------
    # Mapper: Shopify GraphQL node → canonical Product
    # ------------------------------------------------------------------

    def _map_to_product(
        self,
        node: Dict[str, Any],
        query_terms: List[str],
        gender: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Optional[Product]:
        """
        Maps a raw Shopify product GraphQL node to our canonical Product model.
        Specs keys are intentionally identical to BewakoofCatalogProvider for UI compat.
        """
        try:
            raw_id = node.get("id", "")
            prod_id = raw_id.split("/")[-1]  # gid://shopify/Product/12345 → 12345
            handle = node.get("handle", prod_id)
            title = str(node.get("title", "Unknown Product")).strip()
            desc = node.get("description", "") or ""
            brand = node.get("vendor", "Shopify Merchant")
            merchant_name = self.domain.split(".")[0].replace("-", " ").title()

            # Tags — Shopify's primary metadata mechanism
            tags: List[str] = node.get("tags", [])
            tags_lower = " ".join(tags).lower()

            # Variants → prices + available sizes + variant IDs for cart
            variant_edges = node.get("variants", {}).get("edges", [])
            price = 0.0
            mrp = 0.0
            currency = "USD"
            in_stock = node.get("availableForSale", False)
            available_sizes: List[str] = []
            variant_ids: Dict[str, str] = {}  # {"S": "gid://shopify/ProductVariant/123"}
            bewakoof_id: Optional[str] = None

            for v in variant_edges:
                vn = v.get("node", {})
                v_price = float((vn.get("price") or {}).get("amount") or 0)
                v_compare_raw = vn.get("compareAtPrice") or {}
                v_compare = float(v_compare_raw.get("amount") or 0) if v_compare_raw else 0.0
                v_currency = (vn.get("price") or {}).get("currencyCode", "USD")
                v_available = vn.get("availableForSale", False)
                v_title = vn.get("title", "")
                v_id = vn.get("id", "")
                v_sku = vn.get("sku", "")

                if not bewakoof_id and v_sku and "BWK-BEWA-" in v_sku:
                    # BWK-BEWA-1500922-S -> 1500922
                    parts = v_sku.split("-")
                    if len(parts) >= 3:
                        bewakoof_id = parts[2]

                # Use first variant's price as the display price
                if price == 0.0 and v_price > 0:
                    price = v_price
                    mrp = v_compare if v_compare > v_price else v_price
                    currency = v_currency

                # Only include named sizes (skip "Default Title" which is Shopify's placeholder)
                if v_title and v_title.lower() != "default title":
                    if v_available:
                        available_sizes.append(v_title)
                    if v_id:
                        variant_ids[v_title] = v_id
                elif v_id and not variant_ids:
                    # Store the default variant ID even if unnamed (needed for cart)
                    variant_ids["default"] = v_id

            # Images
            image_edges = node.get("images", {}).get("edges", [])
            image_url = image_edges[0].get("node", {}).get("url") if image_edges else None
            all_images = [e["node"]["url"] for e in image_edges if e.get("node", {}).get("url")]

            title_lower = title.lower()

            # ── Attribute inference from tags + title ────────────────────────
            # Color
            color_val = "Multi"
            for c in _KNOWN_COLORS:
                if c in tags_lower or c in title_lower:
                    color_val = c.title()
                    break

            # Design
            design_val = "Solid"
            if any(k in title_lower or k in tags_lower for k in ["graphic", "print", "printed", "artwork"]):
                design_val = "Graphic Print"
            elif any(k in title_lower or k in tags_lower for k in ["typography", "text", "quote", "slogan"]):
                design_val = "Typography"
            elif any(k in title_lower or k in tags_lower for k in ["oversized"]):
                design_val = "Oversized"
            elif any(k in title_lower or k in tags_lower for k in ["washed", "acid"]):
                design_val = "Washed"
            elif any(k in title_lower or k in tags_lower for k in ["abstract", "floral", "camo"]):
                design_val = "Abstract"

            # Fit
            fit_val = "Regular Fit"
            if "oversized" in title_lower or "oversized" in tags_lower:
                fit_val = "Oversized Fit"
            elif "slim" in title_lower or "slim" in tags_lower:
                fit_val = "Slim Fit"
            elif "relaxed" in title_lower or "relaxed" in tags_lower:
                fit_val = "Relaxed Fit"
            elif "boxy" in title_lower or "boxy" in tags_lower:
                fit_val = "Boxy Fit"

            # Sleeve
            sleeve_val = "Half Sleeve"
            if any(k in title_lower or k in tags_lower for k in ["full sleeve", "full-sleeve", "long sleeve"]):
                sleeve_val = "Full Sleeve"
            elif any(k in title_lower or k in tags_lower for k in ["sleeveless", "tank", "vest"]):
                sleeve_val = "Sleeveless"

            # Fandom/partner — scan tags for known franchises
            _fandom_map = {
                "marvel": "Marvel", "dc": "DC", "batman": "Batman", "avengers": "Marvel",
                "spiderman": "Marvel", "spider-man": "Marvel",
                "harry potter": "Harry Potter", "hogwarts": "Harry Potter",
                "disney": "Disney", "friends": "Friends", "looney tunes": "Looney Tunes",
                "anime": "Anime", "naruto": "Naruto",
            }
            partner_val: Optional[str] = None
            for key, display in _fandom_map.items():
                if key in tags_lower or key in title_lower:
                    partner_val = display
                    break

            # Gender from tags or passed arg
            gender_val = "Unisex"
            for g_tag in ["men", "women", "boys", "girls", "unisex", "kids"]:
                if g_tag in tags_lower:
                    gender_val = g_tag.title()
                    break
            if not _skip(gender):
                gender_val = gender.title()

            # Subclass / category
            subclass = node.get("productType") or "Clothing"

            # ── Build canonical specs dict (same keys as Bewakoof for UI compat) ──
            specs: Dict[str, Any] = {
                # Shared keys used by frontend
                "gender":           gender_val,
                "color":            color_val,
                "design":           design_val,
                "fit":              fit_val,
                "fabric":           "Cotton",   # Not in Storefront API — needs metafields
                "neck":             "Round Neck",
                "sleeve":           sleeve_val,
                "subclass":         subclass,
                "fandom_partner":   partner_val,
                "bundle_offers":    [],
                "mrp_inr":          mrp,
                "member_price_inr": None,
                "available_sizes":  available_sizes,
                "image_url":        image_url,
                "all_images":       all_images,
                "discount_offer":   None,
                # Shopify-specific (needed for Phase 2 cart mutations)
                "shopify_gid":      raw_id,
                "variant_ids":      variant_ids,
                "bewakoof_id":      bewakoof_id,
            }

            # Rich description for LLM QA evaluation
            desc_parts = [gender_val, color_val, fit_val, design_val]
            if partner_val:
                desc_parts.append(f"({partner_val})")
            desc_parts.append(title)
            if desc:
                desc_parts.append(f"— {desc[:250]}")
            full_desc = " ".join(desc_parts)

            # Generate deterministic mock ratings based on bewakoof_id for pre-sorting
            import hashlib
            rating_val = 4.2
            review_count = 0
            if bewakoof_id:
                if bewakoof_id in _LOCAL_RATINGS_CACHE:
                    # Use real cached rating!
                    cached = _LOCAL_RATINGS_CACHE[bewakoof_id]
                    rating_val = cached.get("rating", 4.2)
                    review_count = cached.get("review_count", 0)
                else:
                    # Fallback: Hash the ID to get a pseudo-random but consistent number
                    h = int(hashlib.sha256(bewakoof_id.encode('utf-8')).hexdigest(), 16)
                    # Rating between 3.5 and 4.9
                    rating_val = 3.5 + (h % 15) / 10.0
                    # Reviews between 10 and 1500
                    review_count = 10 + (h % 1490)

            return Product(
                id=f"SHPF-{prod_id}",
                title=title,
                brand=brand,
                merchant=merchant_name,
                price=price,
                currency=currency,
                rating=round(rating_val, 1),
                review_count=review_count,
                in_stock=in_stock,
                stock_quantity=10 if in_stock else 0,
                category=subclass,
                description=full_desc,
                tags=tags,
                shipping_days=3,
                shipping_cost=0.0,
                source_url=f"https://{self.domain}/products/{handle}",
                specs=specs,
                discount_codes=[],
            )

        except Exception as e:
            print(f"[Shopify] Error mapping product node: {e}")
            return None
