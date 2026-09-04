"""Multi-Item Bundle Coordinator & Unified Outfit Matching Engine.

Unifies:
1. Multi-Item Bundle Coordination (Both Item A and Item B are non-constant, gated by budget).
2. 'Match My Outfit' (Item A is held CONSTANT, Item B candidates are evaluated against it).
3. Dynamic Category-Weighted Budget Scaling.
4. Macro-Category Taxonomy Expansion (Uppers, Lowers, Pullovers, Footwear).
5. Style Collision Matrix Filtering & Budget Hard Gate.
6. Low-Budget Proactive LLM Alternatives ($P_min calculation).
"""

import math
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from src.agent.semantic_color_engine import (
    check_style_collision,
    generate_stylist_rationale,
    score_garment_pairing,
)
from src.agent.state import CanonicalShoppingQuery, MultiShoppingQuery, Product

# ---------------------------------------------------------------------------
# Gender Detection & Strict Harmony Checking
# ---------------------------------------------------------------------------
def _detect_gender(item: Dict[str, Any]) -> str:
    """Detects whether an item is 'men', 'women', or 'unisex'."""
    if not item:
        return "unisex"
    
    # Check explicit fields
    g = str(item.get("gender") or "").lower().strip()
    if g in ["men", "male", "boys", "man", "mens"]:
        return "men"
    if g in ["women", "female", "girls", "woman", "ladies", "womens"]:
        return "women"
    if g in ["unisex", "all"]:
        return "unisex"
        
    specs = item.get("specs") or {}
    spec_g = str(specs.get("gender") or "").lower().strip()
    if spec_g in ["men", "male", "boys", "man", "mens"]:
        return "men"
    if spec_g in ["women", "female", "girls", "woman", "ladies", "womens"]:
        return "women"
        
    # Check title / name
    title = str(item.get("title") or item.get("name") or "").lower()
    if re.search(r"\b(women|woman|ladies|girls|female|womens)\b", title):
        return "women"
    if re.search(r"\b(men|man|guys|boys|male|mens)\b", title):
        return "men"
        
    return "unisex"


def check_gender_compatibility(item1: Dict[str, Any], item2: Dict[str, Any]) -> bool:
    """Ensures Men's and Women's products are never cross-paired."""
    g1 = _detect_gender(item1)
    g2 = _detect_gender(item2)
    if g1 == "men" and g2 == "women":
        return False
    if g1 == "women" and g2 == "men":
        return False
    return True


# ---------------------------------------------------------------------------
# 1. Category Base Cost Weights & Dynamic Budget Allocator
# ---------------------------------------------------------------------------
CATEGORY_WEIGHTS: Dict[str, float] = {
    "outerwear": 1.00,
    "hoodie": 1.00,
    "sweatshirt": 0.90,
    "jacket": 1.00,
    "jeans": 0.95,
    "trousers": 0.85,
    "joggers": 0.80,
    "cargo pants": 0.85,
    "shirt": 0.65,
    "polo": 0.60,
    "t-shirt": 0.50,
    "vest": 0.40,
    "shorts": 0.45,
    "sliders": 0.35,
    "footwear": 0.55,
    "sneakers": 0.70,
    "general": 0.50,
}

# ---------------------------------------------------------------------------
# 2. Macro-Category Taxonomy Mapping
# ---------------------------------------------------------------------------
MACRO_CATEGORY_MAP: Dict[str, List[str]] = {
    "lowers": ["joggers", "jeans", "trousers", "shorts"],
    "bottomwear": ["joggers", "jeans", "trousers", "shorts"],
    "bottoms": ["joggers", "jeans", "trousers", "shorts"],
    "pants": ["trousers", "jeans", "joggers"],
    "uppers": ["t-shirt", "shirt", "polo", "hoodie"],
    "topwear": ["t-shirt", "shirt", "polo", "hoodie"],
    "tops": ["t-shirt", "shirt", "polo"],
    "pullovers": ["hoodie", "sweatshirt", "jacket"],
    "layers": ["hoodie", "sweatshirt", "jacket", "overshirt"],
    "footwear": ["sliders", "sneakers"],
}


def _normalize_category_name(cat: Any) -> str:
    """Safely extracts clean lowercase category string from str or Enum."""
    if hasattr(cat, "value"):
        return str(cat.value).lower().strip()
    c = str(cat or "").lower().strip()
    if "tshirt" in c or "t-shirt" in c or "tee" in c:
        return "t-shirt"
    if "hoodie" in c:
        return "hoodie"
    if "jogger" in c:
        return "joggers"
    if "jean" in c:
        return "jeans"
    if "shirt" in c and "t-shirt" not in c and "tshirt" not in c:
        return "shirt"
    if "slider" in c:
        return "sliders"
    if "footwear" in c or "shoe" in c or "sneaker" in c:
        return "footwear"
    if "sweatshirt" in c:
        return "sweatshirt"
    if "." in c:
        c = c.split(".")[-1].lower()
    return c


class DynamicBudgetAllocator:
    """Calculates deterministic, category-weighted sub-budgets."""

    @staticmethod
    def allocate_sub_budgets(
        items: List[Dict[str, Any]],
        total_budget: float,
        min_floor: float = 299.0
    ) -> List[float]:
        n = len(items)
        if n == 0:
            return []
        if n == 1 or not total_budget:
            return [total_budget or 2000.0]

        # 1. Proportional allocation by weight
        weights = [CATEGORY_WEIGHTS.get(_normalize_category_name(it.get("category", "")), 0.50) for it in items]
        total_weight = sum(weights) or 1.0
        
        raw_shares = [total_budget * (w / total_weight) for w in weights]
        
        # 2. Deterministic boundary clamping
        max_cap_ratio = 0.70 if n == 2 else min(0.60, 1.4 / n)
        max_cap = total_budget * max_cap_ratio
        
        allocated = []
        for share in raw_shares:
            clamped = max(min_floor, min(max_cap, share))
            allocated.append(round(clamped))
            
        # Ensure total allocated equals total budget
        current_sum = sum(allocated)
        if current_sum != total_budget and current_sum > 0:
            scale = total_budget / current_sum
            allocated = [round(max(min_floor, a * scale)) for a in allocated]
            
        return allocated


class BundleCoordinator:
    """Coordinates multi-item searches, basketing, and outfit matching."""

    def __init__(self, catalog_provider=None):
        self.provider = catalog_provider

    def expand_macro_categories(self, raw_category: str) -> List[str]:
        """Expands colloquial macro terms (lowers, uppers, pullovers) to valid subcategories."""
        cat_lower = _normalize_category_name(raw_category)
        for macro, subcats in MACRO_CATEGORY_MAP.items():
            if macro == cat_lower or macro in cat_lower:
                return subcats
        return [cat_lower]

    def coordinate_bundle(
        self,
        query: str = "",
        budget: Optional[float] = 2500.0,
        items_to_buy: Optional[List[Dict[str, Any]]] = None,
        owned_items: Optional[List[Dict[str, Any]]] = None,
        user_skin_depth: Optional[int] = None,
        user_undertone: Optional[str] = None,
        gender: Optional[str] = None,
        limit_per_category: int = 12,
        provider: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Executes unified outfit coordination with strict gender consistency and multi-combo choices."""
        active_provider = provider or self.provider
        if not active_provider:
            from src.data.bewakoof_api import BewakoofCatalogProvider
            active_provider = BewakoofCatalogProvider()

        items_to_buy = items_to_buy or []
        owned_items = owned_items or []

        if not items_to_buy and not owned_items and query:
            from src.agent.brain import AgentBrain
            brain = AgentBrain()
            mq, _ = brain.normalize_intent(query, budget=budget)
            if mq:
                items_to_buy = [it.model_dump() for it in mq.items_to_buy]
                owned_items = [it.model_dump() for it in mq.owned_items]

        # Expand items with quantity > 1 (e.g. "give me 2 shirts", "2 uppers", "3 t-shirts")
        expanded_items = []
        for it in items_to_buy:
            qty = it.get("quantity", 1) or 1
            if qty > 1:
                sub_price = (it.get("max_price") or budget or 2500.0) / qty
                for q_idx in range(qty):
                    clone = dict(it)
                    clone["quantity"] = 1
                    clone["max_price"] = sub_price
                    expanded_items.append(clone)
            else:
                expanded_items.append(it)
        items_to_buy = expanded_items

        # If user query requested 2+ items but items_to_buy only has 1 item (e.g. "give me 2 shirts"):
        if len(items_to_buy) == 1 and not owned_items:
            q_l = (query or "").lower()
            if re.search(r"\b(?:2|two)\s*(?:shirts?|uppers?|tops?|tees?|t-?shirts?|hoodies?|lowers?|bottoms?|pants?)\b", q_l):
                it0 = items_to_buy[0]
                clone = dict(it0)
                sub_price = (it0.get("max_price") or budget or 2500.0) / 2
                it0["max_price"] = sub_price
                clone["max_price"] = sub_price
                items_to_buy.append(clone)

        is_match_my_outfit = len(owned_items) > 0

        # Determine effective gender
        effective_gender = gender
        if not effective_gender:
            if is_match_my_outfit and owned_items:
                effective_gender = _detect_gender(owned_items[0])
            elif query:
                q_l = query.lower()
                if re.search(r"\b(women|woman|ladies|girls|female|womens)\b", q_l):
                    effective_gender = "women"
                elif re.search(r"\b(men|man|guys|boys|male|mens)\b", q_l):
                    effective_gender = "men"
            if not effective_gender and items_to_buy:
                for it in items_to_buy:
                    g = it.get("gender")
                    if g and str(g).lower() not in ["all", "any", "unisex", ""]:
                        effective_gender = str(g).lower()
                        break
        if not effective_gender or effective_gender in ["all", "any"]:
            effective_gender = "men"

        # ----------------------------------------------------------------------
        # Case A: "Match My Outfit" (Item A is CONSTANT)
        # ----------------------------------------------------------------------
        if is_match_my_outfit:
            constant_item = owned_items[0]
            target_item = items_to_buy[0] if items_to_buy else {"category": "joggers", "color": "Any"}
            
            # Check if target is a macro-term
            target_cat = target_item.get("category", "joggers")
            expanded_cats = self.expand_macro_categories(target_cat)
            
            # Retrieve candidate products for expanded categories in parallel with gender filter
            target_budget = target_item.get("max_price") or budget or 2500.0
            candidate_products = self._fetch_candidates_parallel(
                categories=expanded_cats,
                color=target_item.get("color"),
                fit=target_item.get("fit"),
                max_price=target_budget,
                gender=effective_gender,
                limit=limit_per_category,
                provider=active_provider
            )

            # Score each candidate against the CONSTANT Item A
            scored_candidates = []
            for prod in candidate_products:
                prod_dict = prod if isinstance(prod, dict) else prod.model_dump()
                if not check_gender_compatibility(constant_item, prod_dict):
                    continue
                eval_res = score_garment_pairing(
                    constant_item,
                    prod_dict,
                    user_skin_depth=user_skin_depth,
                    user_undertone=user_undertone
                )
                if not eval_res["is_compatible"]:
                    continue  # Style collision banned
                    
                bayesian_rating = ((prod_dict.get("rating") or 4.0) / 5.0)
                overall_rank = round(0.70 * eval_res["total_score"] + 0.30 * bayesian_rating, 3)
                rationale = generate_stylist_rationale(constant_item, prod_dict, eval_res)
                
                scored_candidates.append({
                    "product": prod_dict,
                    "style_score": eval_res["total_score"],
                    "overall_rank": overall_rank,
                    "sub_scores": eval_res["sub_scores"],
                    "pairing_type": eval_res["pairing_type"],
                    "rationale": rationale
                })

            scored_candidates.sort(key=lambda x: x["overall_rank"], reverse=True)

            return {
                "mode": "match_my_outfit",
                "constant_item": constant_item,
                "target_category": target_cat,
                "gender": effective_gender,
                "total_candidates": len(candidate_products),
                "matched_results": scored_candidates[:12],
                "top_recommendation": scored_candidates[0] if scored_candidates else None,
                "shelves": {
                    "alternatives": [sc["product"] for sc in scored_candidates[:12]]
                }
            }

        # ----------------------------------------------------------------------
        # Case B: Multi-Item Bundle Coordinator (Non-Constant + Non-Constant)
        # ----------------------------------------------------------------------
        if len(items_to_buy) < 2:
            # Fallback if only 1 item
            sub_budget = budget or 2000.0
            allocated_budgets = [sub_budget]
            items_to_buy[0]["allocated_budget"] = sub_budget
        else:
            allocated_budgets = DynamicBudgetAllocator.allocate_sub_budgets(
                items_to_buy,
                total_budget=budget or 3000.0
            )
            for idx, item in enumerate(items_to_buy):
                item["allocated_budget"] = allocated_budgets[idx]

        # 1. Parallel fetch for all items to buy
        cat_products_map: Dict[str, List[Dict[str, Any]]] = {}
        with ThreadPoolExecutor(max_workers=len(items_to_buy)) as executor:
            future_map = {}
            for idx, item in enumerate(items_to_buy):
                cat = _normalize_category_name(item.get("category", "t-shirt"))
                color = item.get("color")
                if hasattr(color, "value"):
                    color = color.value
                sub_b = min(budget or 3000.0, allocated_budgets[idx] * 1.30) if idx < len(allocated_budgets) and budget else budget
                
                expanded = self.expand_macro_categories(cat)
                future = executor.submit(
                    self._fetch_candidates_parallel,
                    categories=expanded,
                    color=color,
                    fit=item.get("fit"),
                    max_price=sub_b,
                    gender=effective_gender,
                    limit=limit_per_category,
                    provider=active_provider
                )
                future_map[f"cat_{idx}_{cat}"] = future

            for key, future in future_map.items():
                cat_products_map[key] = future.result()

        cat_keys = list(cat_products_map.keys())
        if len(cat_keys) < 2:
            if len(cat_keys) == 1 and len(cat_products_map[cat_keys[0]]) >= 2:
                top_candidates = cat_products_map[cat_keys[0]]
                bottom_candidates = list(cat_products_map[cat_keys[0]])
            else:
                return {"mode": "bundle", "status": "insufficient_categories", "bundles": []}
        else:
            top_candidates = cat_products_map[cat_keys[0]]
            bottom_candidates = cat_products_map[cat_keys[1]]

        # 2. Check for Low Budget Edge Case ($P_min)
        if not top_candidates or not bottom_candidates:
            # Find global minimums across store without budget cap to explain alternatives
            min_top_price, min_bottom_price = self._find_catalog_minimums(
                _normalize_category_name(items_to_buy[0].get("category", "t-shirt")),
                _normalize_category_name(items_to_buy[1].get("category", "joggers")),
                provider=active_provider
            )
            min_total = min_top_price + min_bottom_price
            
            alternatives = self._generate_low_budget_alternatives(
                budget=budget,
                min_total=min_total,
                min_top=min_top_price,
                min_bottom=min_bottom_price,
                cat1=_normalize_category_name(items_to_buy[0].get("category", "top")),
                cat2=_normalize_category_name(items_to_buy[1].get("category", "bottom"))
            )
            
            return {
                "mode": "bundle",
                "status": "budget_too_low",
                "budget": budget,
                "min_total_required": min_total,
                "alternatives": alternatives,
                "bundles": []
            }

        # 3. Cartesian Pairing, Hard Gate, Gender Check, and Scoring
        valid_bundles = []
        discarded_count = 0

        for t in top_candidates:
            for b in bottom_candidates:
                # If pairing from the same pool, ensure distinct items
                if t.get("id") and b.get("id") and t["id"] == b["id"] and len(top_candidates) > 1:
                    discarded_count += 1
                    continue

                # Strict Gender Matching Check
                if not check_gender_compatibility(t, b):
                    discarded_count += 1
                    continue
                if effective_gender == "men" and (_detect_gender(t) == "women" or _detect_gender(b) == "women"):
                    discarded_count += 1
                    continue
                if effective_gender == "women" and (_detect_gender(t) == "men" or _detect_gender(b) == "men"):
                    discarded_count += 1
                    continue

                total_p = t["price"] + b["price"]
                
                # Hard Budget Gate
                if budget and total_p > budget:
                    discarded_count += 1
                    continue
                    
                # Style Collision Filter
                eval_res = score_garment_pairing(
                    t, b,
                    user_skin_depth=user_skin_depth,
                    user_undertone=user_undertone
                )
                if not eval_res["is_compatible"]:
                    discarded_count += 1
                    continue
                    
                # Ranking: 70% Style Score + 30% Bayesian Rating
                avg_rating = ((t.get("rating", 4.0) + b.get("rating", 4.0)) / (2.0 * 5.0))
                overall_rank = round(0.70 * eval_res["total_score"] + 0.30 * avg_rating, 3)
                rationale = generate_stylist_rationale(t, b, eval_res)
                
                valid_bundles.append({
                    "items": [t, b],
                    "total_price": total_p,
                    "budget_savings": round(budget - total_p, 2) if budget else 0.0,
                    "style_score": eval_res["total_score"],
                    "overall_rank": overall_rank,
                    "pairing_type": eval_res["pairing_type"],
                    "sub_scores": eval_res["sub_scores"],
                    "rationale": rationale
                })

        # Sort by overall rank descending
        valid_bundles.sort(key=lambda x: x["overall_rank"], reverse=True)

        # If all combinations exceeded budget:
        if not valid_bundles:
            min_top = min(t["price"] for t in top_candidates)
            min_bottom = min(b["price"] for b in bottom_candidates)
            min_total = min_top + min_bottom
            alternatives = self._generate_low_budget_alternatives(
                budget=budget,
                min_total=min_total,
                min_top=min_top,
                min_bottom=min_bottom,
                cat1=items_to_buy[0].get("category", "top"),
                cat2=items_to_buy[1].get("category", "bottom")
            )
            return {
                "mode": "bundle",
                "status": "budget_too_low",
                "budget": budget,
                "min_total_required": min_total,
                "alternatives": alternatives,
                "bundles": []
            }

        # 4. Form Curated Bundle Tiers & Distinct Combinations
        hero_bundle = valid_bundles[0] if valid_bundles else None
        hero_top_id = hero_bundle["items"][0].get("id") if hero_bundle else None
        hero_bottom_id = hero_bundle["items"][1].get("id") if hero_bundle else None

        # Alternative Bundle: Highest scoring bundle with distinct products from hero
        alternative_bundle = None
        for b in valid_bundles[1:]:
            b_top_id = b["items"][0].get("id")
            b_bottom_id = b["items"][1].get("id")
            if b_top_id != hero_top_id and b_bottom_id != hero_bottom_id:
                alternative_bundle = b
                break
        if not alternative_bundle and len(valid_bundles) > 1:
            alternative_bundle = valid_bundles[1]

        # Best Value Bundle: Max budget savings among bundles with different piece
        value_bundle = None
        candidates_for_value = sorted(valid_bundles, key=lambda x: x["budget_savings"], reverse=True)
        for b in candidates_for_value:
            if b != hero_bundle and b != alternative_bundle:
                value_bundle = b
                break
        if not value_bundle and candidates_for_value:
            value_bundle = candidates_for_value[0]

        # Assemble multiple distinct styled combinations for the user to choose from
        combos = []
        if hero_bundle:
            combos.append({
                "id": "combo-1",
                "name": "Combo 1: Hero Coordinated",
                "badge": "Top Stylist Match",
                "tagline": "Optimal Perceptual Harmony",
                "total_price": hero_bundle["total_price"],
                "budget_savings": hero_bundle["budget_savings"],
                "style_score": hero_bundle["style_score"],
                "bundle": hero_bundle
            })
        if alternative_bundle and alternative_bundle != hero_bundle:
            combos.append({
                "id": "combo-2",
                "name": "Combo 2: High Contrast",
                "badge": "Streetwear Alternative",
                "tagline": "Distinct Silhouette & Tone",
                "total_price": alternative_bundle["total_price"],
                "budget_savings": alternative_bundle["budget_savings"],
                "style_score": alternative_bundle["style_score"],
                "bundle": alternative_bundle
            })
        if value_bundle and value_bundle != hero_bundle and value_bundle != alternative_bundle:
            combos.append({
                "id": "combo-3",
                "name": "Combo 3: Best Value",
                "badge": "Budget Maximizer",
                "tagline": f"Save ₹{int(value_bundle.get('budget_savings', 0))} under budget",
                "total_price": value_bundle["total_price"],
                "budget_savings": value_bundle["budget_savings"],
                "style_score": value_bundle["style_score"],
                "bundle": value_bundle
            })

        return {
            "mode": "bundle",
            "status": "success",
            "budget": budget,
            "gender": effective_gender,
            "allocated_budgets": {
                _normalize_category_name(items_to_buy[0].get("category")): allocated_budgets[0],
                _normalize_category_name(items_to_buy[1].get("category")): allocated_budgets[1]
            },
            "total_pairs_evaluated": len(top_candidates) * len(bottom_candidates),
            "discarded_count": discarded_count,
            "valid_bundle_count": len(valid_bundles),
            "hero_bundle": hero_bundle,
            "alternative_bundle": alternative_bundle,
            "value_bundle": value_bundle,
            "combos": combos,
            "all_bundles": valid_bundles[:15],
            "shelves": {
                "tops": top_candidates,
                "bottoms": bottom_candidates
            }
        }

    # --------------------------------------------------------------------------
    # Helper Methods
    # --------------------------------------------------------------------------

    def _fetch_candidates_parallel(
        self,
        categories: List[str],
        color: Optional[str] = None,
        fit: Optional[str] = None,
        max_price: Optional[float] = None,
        gender: Optional[str] = None,
        limit: int = 12,
        provider: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for cat in categories:
            try:
                cat_val = cat if cat != "general" else None
                color_val = color if color and color != "Any" else None
                prods = provider.search_products(
                    query=cat,
                    category=cat_val,
                    gender=gender,
                    color=color_val,
                    fit=fit if fit and fit != "Any" else None,
                    max_price=max_price,
                    limit=limit
                )
                for p in prods:
                    p_dict = p if isinstance(p, dict) else p.model_dump()
                    p_gen = _detect_gender(p_dict)
                    if gender == "men" and p_gen == "women":
                        continue
                    if gender == "women" and p_gen == "men":
                        continue
                    results.append(p_dict)
            except Exception as e:
                print(f"[BundleCoordinator] Search error for {cat}: {e}")
                
        # Deduplicate by ID
        seen = set()
        unique_results = []
        for r in results:
            if r.get("id") not in seen:
                seen.add(r.get("id"))
                unique_results.append(r)
        return unique_results[:limit]


    def _find_catalog_minimums(self, cat1: str, cat2: str, provider: Any) -> Tuple[float, float]:
        """Finds lowest priced product in store for given categories without budget constraint."""
        def get_min(c):
            try:
                prods = provider.search_products(query=c, category=c, limit=5)
                if prods:
                    return min((p if isinstance(p, dict) else p.model_dump())["price"] for p in prods)
            except Exception:
                pass
            return 499.0
            
        return get_min(cat1), get_min(cat2)

    def _generate_low_budget_alternatives(
        self,
        budget: float,
        min_total: float,
        min_top: float,
        min_bottom: float,
        cat1: str,
        cat2: str
    ) -> Dict[str, Any]:
        """Generates proactive 3-path guidance for impossible budgets."""
        curr = "₹"
        message = (
            f"With your budget of {curr}{budget}, getting both a quality {cat1} and {cat2} "
            f"isn't feasible as our closest coordinated combination starts at {curr}{min_total} "
            f"({curr}{min_top} for {cat1} + {curr}{min_bottom} for {cat2})."
        )
        options = [
            f"Adjust budget to {curr}{min_total} for the complete {cat1} & {cat2} outfit",
            f"Use your {curr}{budget} budget to get a top-tier {cat1} individually",
            f"Use your {curr}{budget} budget to get a top-tier {cat2} individually",
            f"Switch to a lighter combo (e.g. T-Shirt & Shorts) under {curr}{budget}"
        ]
        return {
            "message": message,
            "options": options,
            "min_total": min_total,
            "min_item1": min_top,
            "min_item2": min_bottom
        }
