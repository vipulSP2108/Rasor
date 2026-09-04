"""
Store Query Compilers for Multi-Platform Catalog Execution.

Compiles standardized semantic intent into store-specific query protocols:
  1. BewakoofCompiler: URL slug handle + subclass filter resolution
  2. ShopifyCompiler: Storefront GraphQL products(query:) & search() syntax
  3. UniversalCompiler: In-memory predicate filters
  4. SearchTierCompiler: Progressive relaxation tiers for zero-result prevention
"""

from typing import Any, Dict, List, Optional
from src.mapping.contracts import (
    BewakoofQuerySpec,
    ShopifyQuerySpec,
    UniversalFilterSpec,
    SearchTierConfig,
)
from src.mapping.taxonomy import (
    CATEGORY_SLEEVE_HANDLE_MAP,
    CATEGORY_TAXONOMY,
    DESIGN_HANDLE_MAP,
    FANDOM_HANDLE_MAP,
    GENDER_FALLBACK_MAP,
    NOISE_WORDS,
)


class BewakoofCompiler:
    """Compiles normalized intent into Bewakoof collection handles and API params."""

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
            fl = fandom.lower().replace(" / cartoons", "").strip()
            for key, handle in FANDOM_HANDLE_MAP.items():
                if fl in key or key in fl:
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

        # 3. Design theme priority (typography, printed, washed)
        if design and design.lower() not in ("any", "", "solid"):
            dl = design.lower()
            design_key_map = {
                "oversized fit": "oversized",
                "typography":    "typography",
                "graphic print": "printed",
                "all over print":"printed",
                "washed":        "acid wash",
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
            alias_map = {
                "tshirt": "t-shirt", "tee": "t-shirt", "topwear": "t-shirt",
                "hoodie": "hoodie", "sweatshirt": "sweatshirt", "jacket": "hoodie",
                "joggers": "joggers", "trackpants": "joggers", "sweatpants": "joggers",
                "jeans": "jeans", "denim": "jeans",
                "shirt": "shirt",
                "slider": "sliders", "sandal": "sliders", "slipper": "sliders",
                "shoes": "footwear", "sneakers": "footwear",
            }
            normalized_cat = alias_map.get(cl, cl)

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
        if category and category.lower() not in ("any", "none", "clothing", "all", ""):
            c_def = CATEGORY_TAXONOMY.get(category.lower())
            prod_type = c_def.shopify_product_type if c_def else category.title()
            parts.append(f"product_type:{prod_type}")

        if gender and gender.lower() not in ("any", "unisex", "all", ""):
            parts.append(f"tag:{gender.lower()}")
            tags.append(gender.lower())

        if fandom and fandom.lower() not in ("none", "any", ""):
            parts.append(f"tag:{fandom.lower()}")
            tags.append(fandom.lower())

        if color and color.lower() not in ("any", "all", "multi", ""):
            parts.append(f"tag:{color.lower()}")
            tags.append(color.lower())

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
