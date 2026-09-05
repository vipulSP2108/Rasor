"""
Store Query Compilers for Multi-Platform Catalog Execution.

Compiles standardized semantic intent into store-specific query protocols:
  1. BewakoofCompiler: URL slug handle + subclass filter resolution
  2. ShopifyCompiler: Storefront GraphQL products(query:) & search() syntax
  3. UniversalCompiler: In-memory predicate filters
  4. SearchTierCompiler: Progressive relaxation tiers for zero-result prevention
"""

from typing import Any, Dict, List, Optional
import re
from src.mapping.contracts import (
    BewakoofQuerySpec,
    ShopifyQuerySpec,
    UniversalFilterSpec,
    SearchTierConfig,
)
from src.mapping.taxonomy import (
    CATEGORY_SHOPIFY_TYPE_ALIASES,
    CATEGORY_SLEEVE_HANDLE_MAP,
    CATEGORY_TAXONOMY,
    DESIGN_HANDLE_MAP,
    FANDOM_HANDLE_MAP,
    GENDER_FALLBACK_MAP,
    NOISE_WORDS,
)


class BewakoofCompiler:
    """Compiles normalized intent into Bewakoof collection handles and API params."""

    # Raw/free-typed category tokens -> canonical CATEGORY_TAXONOMY keys.
    # This is a local safety net independent of normalize_category(): several
    # call sites (including this class's own unit tests) invoke the compiler
    # directly with an un-normalized category string, so it needs its own
    # alias table. Kept in sync with CATEGORY_TAXONOMY's synonym lists.
    _CATEGORY_ALIAS_MAP: Dict[str, str] = {
        "tshirt": "t-shirt", "tee": "t-shirt", "topwear": "t-shirt",
        "hoodie": "hoodie", "sweatshirt": "sweatshirt", "jacket": "hoodie",
        "sweater": "sweater", "sweaters": "sweater", "knitwear": "sweater",
        "joggers": "joggers", "trackpants": "joggers", "trackpant": "joggers",
        "sweatpants": "joggers",
        "jeans": "jeans", "denim": "jeans",
        "shirt": "shirt",
        "dress": "dress", "dresses": "dress",
        "pyjama": "pyjama", "pyjamas": "pyjama", "pajama": "pyjama", "pajamas": "pyjama",
        "nightsuit": "pyjama",
        "boxer": "boxer", "boxers": "boxer",
        "slider": "sliders", "sandal": "sliders", "slipper": "sliders",
        "clog": "clogs", "clogs": "clogs", "crocs": "clogs",
        "shoes": "footwear", "sneakers": "footwear", "sneaker": "footwear",
        "casualshoes": "footwear",
        "mobilecover": "mobile-cover", "mobilecovers": "mobile-cover",
        "mobilecase": "mobile-cover", "phonecase": "mobile-cover",
        "phonecover": "mobile-cover", "phonecases": "mobile-cover",
        "phonecovers": "mobile-cover", "backcover": "mobile-cover",
        "duffelbag": "duffel-bag", "dufflebag": "duffel-bag", "gymbag": "duffel-bag",
        "bag": "duffel-bag", "bags": "duffel-bag", "backpack": "duffel-bag",
        "cap": "cap", "caps": "cap", "hat": "cap",
        "coord": "co-ord", "coords": "co-ord", "coordinateset": "co-ord",
    }

    @staticmethod
    def compile(
        gender: str,
        category: Optional[str],
        sleeve: Optional[str],
        fandom: Optional[str],
        design: Optional[str],
        fit: Optional[str],
    ) -> BewakoofQuerySpec:
        g = (gender or "men").lower()
        cat = (category or "").lower().strip()
        fandom_detected = None

        # 1. Fandom priority (highest specificity)
        if fandom and fandom.lower() not in ("none", "", "any"):
            # Normalize punctuation variants before matching against
            # FANDOM_HANDLE_MAP keys. Real catalog data uses "&" (e.g. the
            # literal "Bewakoof X Tom & Jerry" fandom partner string), while
            # this file's keys use "and" ("tom and jerry") - a plain
            # substring check between the two never matched, silently
            # falling through to the generic gender collection for every
            # Tom & Jerry product (39 in the audited catalog). See README
            # changelog. Also collapse repeated whitespace and periods
            # (e.g. "S.W.Smiley") so minor formatting differences don't
            # cause the same failure for other partners.
            fl = (
                fandom.lower()
                .replace(" / cartoons", "")
                .replace("&", " and ")
                .replace(".", "")
                .strip()
            )
            fl = re.sub(r"\s+", " ", fl)
            for key, handle in FANDOM_HANDLE_MAP.items():
                key_norm = key.replace("&", " and ")
                if fl in key_norm or key_norm in fl:
                    fandom_detected = key.title()
                    return BewakoofQuerySpec(
                        handle=handle,
                        needs_subclass_filter=True if cat else False,
                        target_subclass=CATEGORY_TAXONOMY.get(cat, None).bewakoof_subclass if cat in CATEGORY_TAXONOMY else None,
                        api_relative_path=f"collection/{handle}",
                        fandom_detected=fandom_detected,
                    )

        # 2. Oversized fit + t-shirt (Bewakoof's most popular distinct silhouette collection)
        if fit and "oversized" in fit.lower() and ("t-shirt" in cat or "tshirt" in cat or not cat):
            return BewakoofQuerySpec(
                handle="oversized-t-shirts",
                needs_subclass_filter=False,
                target_subclass="T-Shirt",
                api_relative_path="collection/oversized-t-shirts",
                fandom_detected=None,
            )

        # 3. Design theme priority (typography, printed, washed, and the newer
        #    catalog-verified themes: checked, color block, striped,
        #    embroidered, self design, applique, camouflage, ombre, tie & dye,
        #    all over print - see README changelog)
        if design and design.lower() not in ("any", "", "solid"):
            dl = design.lower()
            design_key_map = {
                "oversized fit": "oversized",
                "typography":    "typography",
                "graphic print": "printed",
                "all over print":"all over print",
                "washed":        "acid wash",
                "checked":       "checked",
                "color block":   "color block",
                "striped":       "striped",
                "embroidered":   "embroidered",
                "self design":   "self design",
                "applique":      "applique",
                "camouflage":    "camouflage",
                "ombre":         "ombre",
                "tie & dye":     "tie & dye",
            }
            mapped = design_key_map.get(dl, dl)
            if mapped in DESIGN_HANDLE_MAP:
                return BewakoofQuerySpec(
                    handle=DESIGN_HANDLE_MAP[mapped],
                    needs_subclass_filter=True if cat and cat != "t-shirt" else False,
                    target_subclass=CATEGORY_TAXONOMY.get(cat, None).bewakoof_subclass if cat in CATEGORY_TAXONOMY else None,
                    api_relative_path=f"collection/{DESIGN_HANDLE_MAP[mapped]}",
                    fandom_detected=None,
                )

        # 3. Category + sleeve matrix
        if cat:
            cl = cat.replace("-", "").replace(" ", "")
            normalized_cat = BewakoofCompiler._CATEGORY_ALIAS_MAP.get(cl, cl)

            sleeve_key = None
            if sleeve:
                sl = sleeve.lower()
                if "full" in sl:
                    sleeve_key = "full"
                elif "half" in sl or "short" in sl:
                    sleeve_key = "half"

            # Check exact sleeve
            key = (g, normalized_cat, sleeve_key)
            if key in CATEGORY_SLEEVE_HANDLE_MAP:
                h = CATEGORY_SLEEVE_HANDLE_MAP[key]
                target_sc = CATEGORY_TAXONOMY.get(normalized_cat, None).bewakoof_subclass if normalized_cat in CATEGORY_TAXONOMY else None
                return BewakoofQuerySpec(
                    handle=h,
                    needs_subclass_filter=h in ("men-clothing", "women-clothing"),
                    target_subclass=target_sc,
                    api_relative_path=f"collection/{h}",
                    fandom_detected=None,
                )

            # Check without sleeve
            key_no_sleeve = (g, normalized_cat, None)
            if key_no_sleeve in CATEGORY_SLEEVE_HANDLE_MAP:
                h = CATEGORY_SLEEVE_HANDLE_MAP[key_no_sleeve]
                target_sc = CATEGORY_TAXONOMY.get(normalized_cat, None).bewakoof_subclass if normalized_cat in CATEGORY_TAXONOMY else None
                return BewakoofQuerySpec(
                    handle=h,
                    needs_subclass_filter=h in ("men-clothing", "women-clothing"),
                    target_subclass=target_sc,
                    api_relative_path=f"collection/{h}",
                    fandom_detected=None,
                )

        # 4. Gender fallback
        fallback_handle = GENDER_FALLBACK_MAP.get(g, "men-clothing")
        target_sc = CATEGORY_TAXONOMY.get(cat, None).bewakoof_subclass if cat in CATEGORY_TAXONOMY else None
        return BewakoofQuerySpec(
            handle=fallback_handle,
            needs_subclass_filter=True,
            target_subclass=target_sc,
            api_relative_path=f"collection/{fallback_handle}",
            fandom_detected=None,
        )


class ShopifyCompiler:
    """Compiles normalized intent into Shopify Storefront GraphQL query strings."""

    @staticmethod
    def compile(
        raw_keywords: List[str],
        category: Optional[str],
        gender: Optional[str],
        fandom: Optional[str],
        color: Optional[str],
    ) -> ShopifyQuerySpec:
        clean_kw = [w.lower().strip(".,!?") for w in raw_keywords if w.lower().strip(".,!?") not in NOISE_WORDS and len(w) > 1]
        parts: List[str] = []
        tags: List[str] = []

        if clean_kw:
            parts.append(" AND ".join(clean_kw))

        prod_type = None
        type_aliases: List[str] = []
        if category and category.lower() not in ("any", "none", "all", ""):
            cat_key = category.lower()
            c_def = CATEGORY_TAXONOMY.get(cat_key)
            # Prefer the full list of real catalog Type values for this
            # category (a category can legitimately span more than one
            # literal Shopify `Type`, e.g. joggers -> Joggers + Track Pant).
            # See README changelog: the previous single-value lookup also
            # forced a `product_type:Clothing` filter for the "general"/
            # unclassified bucket even though no product in the store has
            # that type, which meant every unclassified query returned zero
            # Shopify results. An empty alias list (as "general" now has)
            # means "don't filter by product_type at all".
            type_aliases = CATEGORY_SHOPIFY_TYPE_ALIASES.get(
                cat_key,
                [c_def.shopify_product_type] if (c_def and c_def.shopify_product_type) else [],
            )
            type_aliases = [t for t in type_aliases if t]
            if type_aliases:
                prod_type = type_aliases[0]
                if len(type_aliases) == 1:
                    parts.append(f"product_type:{_quote_if_needed(type_aliases[0])}")
                else:
                    or_clause = " OR ".join(f"product_type:{_quote_if_needed(t)}" for t in type_aliases)
                    parts.append(f"({or_clause})")

        if gender and gender.lower() not in ("any", "unisex", "all", ""):
            parts.append(f"tag:{gender.lower()}")
            tags.append(gender.lower())

        if fandom and fandom.lower() not in ("none", "any", ""):
            f_lower = fandom.lower()
            # Only add tag filter if fandom keywords are not already present in query
            if not any(f_term in " ".join(clean_kw) for f_term in f_lower.split() if f_term not in NOISE_WORDS and len(f_term) > 2):
                tag_clause = f"(tag:{_quote_if_needed(f'Bewakoof X {fandom}')} OR tag:{_quote_if_needed(fandom)})"
                parts.append(tag_clause)
                tags.append(fandom)

        if color and color.lower() not in ("any", "all", "multi", ""):
            parts.append(f"tag:{_quote_if_needed(color.title())}")
            tags.append(color.title())

        products_q = " AND ".join(parts) if parts else "available_for_sale:true"

        # Search syntax (for forgiving storefront search)
        search_terms = list(clean_kw)
        if prod_type:
            search_terms.append(prod_type)
        if gender and gender.lower() not in ("any", "all"):
            search_terms.append(gender.lower())
        search_q = " ".join(search_terms)

        return ShopifyQuerySpec(
            products_query_syntax=products_q,
            search_query_syntax=search_q,
            product_type=prod_type,
            filter_tags=tags,
            keywords_used=clean_kw,
        )


def _quote_if_needed(value: str) -> str:
    """Shopify's search-query grammar requires quoting any value that
    contains a space (e.g. `product_type:'Track Pant'`); single-word values
    are fine unquoted. Centralized here so both the single- and OR-clause
    branches above stay consistent."""
    return f"'{value}'" if " " in value else value


class UniversalCompiler:
    """Compiles normalized intent into generic in-memory predicates."""

    @staticmethod
    def compile(
        category: Optional[str],
        macro_category: Optional[str],
        gender: Optional[str],
        color: Optional[str],
        color_family: Optional[str],
        sizes: List[str],
        fit: Optional[str],
        design: Optional[str],
        fandom: Optional[str],
        max_price: Optional[float],
        min_rating: Optional[float],
        plus_size: Optional[bool] = None,
    ) -> UniversalFilterSpec:
        tags = []
        if gender and gender.lower() not in ("any", "all"):
            tags.append(gender.lower())
        if color:
            tags.append(color.lower())
        if fandom and fandom.lower() not in ("none", "any"):
            tags.append(fandom.lower())
        if design and design.lower() not in ("any", "solid"):
            tags.append(design.lower())
        if plus_size:
            tags.append("plus size")

        return UniversalFilterSpec(
            category=category,
            macro_category=macro_category,
            gender=gender,
            color=color,
            color_family=color_family,
            sizes=sizes,
            fit=fit,
            design=design,
            fandom=fandom,
            max_price=max_price,
            min_rating=min_rating,
            tags_required=tags,
            plus_size=plus_size,
        )


class SearchTierCompiler:
    """Builds progressive relaxation tiers to prevent empty result sets."""

    @staticmethod
    def build_tiers(
        category: str,
        color: Optional[str],
        fit: Optional[str],
        design: Optional[str],
        sizes: List[str],
        max_price: Optional[float],
        color_family: Optional[str] = None,
    ) -> List[SearchTierConfig]:
        tiers = [
            SearchTierConfig(
                tier=1,
                name="Strict Semantic Match",
                description="Matches category, exact color, fit, design, size, and price limit",
                active_predicates={
                    "category": category,
                    "color": color,
                    "fit": fit,
                    "design": design,
                    "sizes": sizes,
                    "max_price": max_price,
                }
            ),
            SearchTierConfig(
                tier=2,
                name="Relaxed Fit & Design",
                description="Preserves category, color, size, and budget; relaxes fit style & print theme",
                active_predicates={
                    "category": category,
                    "color": color,
                    "sizes": sizes,
                    "max_price": max_price,
                }
            ),
            SearchTierConfig(
                tier=3,
                name="Relaxed Color Family",
                description="Preserves category, size, and budget; matches color family or complementary shades",
                active_predicates={
                    "category": category,
                    # Previously this tier dropped color matching entirely
                    # (identical in effect to going straight to Tier 4), even
                    # though its own name/description promise a color-*family*
                    # match rather than no color constraint at all. Now it
                    # actually carries the broader family (e.g. "Blue" instead
                    # of "Navy") so a Navy search can still surface other blue
                    # items here before Tier 4 drops color completely.
                    "color_family": color_family,
                    "sizes": sizes,
                    "max_price": max_price,
                }
            ),
            SearchTierConfig(
                tier=4,
                name="Category Floor Search",
                description="Matches target category strictly within budget constraint",
                active_predicates={
                    "category": category,
                    "max_price": max_price,
                }
            ),
            SearchTierConfig(
                tier=5,
                name="Catalog Fallback",
                description="Broad category search relaxed by 20% budget leeway to prevent zero products",
                active_predicates={
                    "category": category,
                    "max_price": max_price * 1.20 if max_price else None,
                }
            ),
        ]
        return tiers
