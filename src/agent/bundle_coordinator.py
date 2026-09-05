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
    "lower": ["joggers", "jeans", "trousers", "shorts"],
    "bottomwear": ["joggers", "jeans", "trousers", "shorts"],
    "bottoms": ["joggers", "jeans", "trousers", "shorts"],
    "bottom": ["joggers", "jeans", "trousers", "shorts"],
    "pants": ["trousers", "jeans", "joggers"],
    "uppers": ["t-shirt", "shirt", "polo", "hoodie"],
    "upper": ["t-shirt", "shirt", "polo", "hoodie"],
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
                # Elastic Search Corridor: Allow each candidate pool to search with up to max(allocated * 1.35, 55% of total budget)
                # This enables cross-garment compensatory absorption (e.g. 60/40 or 55/45 splits, and high-value pairings)
                elastic_ceiling = max(allocated_budgets[idx] * 1.35, (budget or 3000.0) * 0.55) if idx < len(allocated_budgets) and budget else (budget or 3000.0)
                sub_b = min(budget or 3000.0, elastic_ceiling)
                
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
        if len(cat_keys) == 0:
            return {"mode": "bundle", "status": "insufficient_categories", "bundles": []}

        # Handle single-category / individual piece coordination (e.g. "get top-tier shirt individually")
        if len(cat_keys) == 1:
            candidates = cat_products_map[cat_keys[0]]
            cat_name = _normalize_category_name(items_to_buy[0].get("category", "t-shirt"))
            if not candidates:
                candidates = self._fetch_candidates_parallel(
                    categories=self.expand_macro_categories(cat_name),
                    max_price=budget,
                    gender=effective_gender,
                    limit=limit_per_category,
                    provider=active_provider
                )

            if not candidates:
                return {"mode": "single", "status": "no_inventory", "bundles": []}

            budget_candidates = [c for c in candidates if not budget or c.get("price", 0) <= budget]
            if not budget_candidates:
                min_p = min(c.get("price", 999) for c in candidates)
                cat_clean = cat_name.replace("categoryenum.", "").replace(".", " ").strip().title()
                b_val = int(round(budget)) if budget else 1500
                return {
                    "mode": "single",
                    "status": "budget_too_low",
                    "budget": budget,
                    "min_total_required": min_p,
                    "alternatives": {
                        "message": f"Our closest quality {cat_clean} starts at ₹{int(round(min_p))}, exceeding your ₹{b_val} cap.",
                        "options": [
                            f"Adjust budget to ₹{int(round(min_p))} for a premium {cat_clean}",
                            "Browse all available catalog options"
                        ],
                        "min_total": min_p
                    },
                    "bundles": []
                }

            valid_bundles = []
            for c in budget_candidates:
                valid_bundles.append({
                    "items": [c],
                    "total_price": c["price"],
                    "budget_savings": round(budget - c["price"], 2) if budget else 0.0,
                    "style_score": 0.95,
                    "overall_rank": round(0.5 + (c.get("rating", 4.0) / 10.0), 2),
                    "pairing_type": "standalone_hero",
                    "sub_scores": {"versatility": 0.95, "color_harmony": 1.0},
                    "rationale": f"Curated premium {c.get('title', 'piece')} selected for standout styling."
                })
            valid_bundles.sort(key=lambda x: x["overall_rank"], reverse=True)

            hero = valid_bundles[0] if valid_bundles else None
            alt = valid_bundles[1] if len(valid_bundles) > 1 else hero
            val = sorted(valid_bundles, key=lambda x: x["budget_savings"], reverse=True)[0] if valid_bundles else hero

            combos = [
                {"id": 1, "title": "Hero Choice", "total_price": hero["total_price"], "style_score": 95, "budget_savings": hero["budget_savings"], "bundle": hero},
            ]
            if alt and alt != hero:
                combos.append({"id": 2, "title": "Stylist Alternative", "total_price": alt["total_price"], "style_score": 92, "budget_savings": alt["budget_savings"], "bundle": alt})
            if val and val != hero and val != alt:
                combos.append({"id": 3, "title": "Best Value", "total_price": val["total_price"], "style_score": 88, "budget_savings": val["budget_savings"], "bundle": val})

            return {
                "mode": "bundle",
                "status": "success",
                "budget": budget,
                "gender": effective_gender,
                "allocated_budgets": {
                    cat_name: budget or hero["total_price"]
                },
                "total_pairs_evaluated": len(budget_candidates),
                "discarded_count": 0,
                "valid_bundle_count": len(valid_bundles),
                "hero_bundle": hero,
                "alternative_bundle": alt,
                "value_bundle": val,
                "combos": combos,
                "all_bundles": valid_bundles[:15],
                "shelves": {
                    "tops": budget_candidates,
                    "bottoms": []
                }
            }

        # Handle 3-category / 3-piece looks (e.g. 2 uppers and 1 lower, or layer + top + bottom)
        if len(cat_keys) >= 3:
            pool0 = cat_products_map[cat_keys[0]]
            pool1 = cat_products_map[cat_keys[1]]
            pool2 = cat_products_map[cat_keys[2]]

            c0_name = _normalize_category_name(items_to_buy[0].get("category", "t-shirt"))
            c1_name = _normalize_category_name(items_to_buy[1].get("category", "t-shirt"))
            c2_name = _normalize_category_name(items_to_buy[2].get("category", "joggers"))

            # Fallback unconstrained fetch if any pool is empty
            if not pool0:
                pool0 = self._fetch_candidates_parallel(self.expand_macro_categories(c0_name), max_price=budget, gender=effective_gender, limit=limit_per_category, provider=active_provider)
            if not pool1:
                pool1 = self._fetch_candidates_parallel(self.expand_macro_categories(c1_name), max_price=budget, gender=effective_gender, limit=limit_per_category, provider=active_provider)
            if not pool2:
                pool2 = self._fetch_candidates_parallel(self.expand_macro_categories(c2_name), max_price=budget, gender=effective_gender, limit=limit_per_category, provider=active_provider)

            if not pool0 or not pool1 or not pool2:
                m0, m1 = self._find_catalog_minimums(c0_name, c1_name, provider=active_provider)
                _, m2 = self._find_catalog_minimums(c1_name, c2_name, provider=active_provider)
                min_total = m0 + m1 + m2
                if budget and budget < min_total:
                    alternatives = {
                        "message": f"Coordinating 3 quality pieces starts at ₹{int(round(min_total))}, exceeding your ₹{int(round(budget))} cap.",
                        "options": [
                            f"Adjust budget to ₹{int(round(min_total))} for 3 pieces",
                            "Switch to 2-piece combination under budget",
                            "Browse best value options"
                        ],
                        "min_total": min_total
                    }
                    return {
                        "mode": "bundle",
                        "status": "budget_too_low",
                        "budget": budget,
                        "min_total_required": min_total,
                        "alternatives": alternatives,
                        "bundles": []
                    }
                return {
                    "mode": "bundle",
                    "status": "insufficient_inventory",
                    "message": "Could not find sufficient in-stock pieces across all 3 requested categories.",
                    "bundles": []
                }

            valid_bundles = []
            discarded_count = 0

            # Cartesian 3-way pairing with strict gender compatibility, distinct items, and budget gate
            for p0 in pool0:
                for p1 in pool1:
                    if p0.get("id") and p1.get("id") and p0["id"] == p1["id"]:
                        discarded_count += 1
                        continue
                    if not check_gender_compatibility(p0, p1):
                        discarded_count += 1
                        continue
                    for p2 in pool2:
                        if p2.get("id") and (p2["id"] == p0.get("id") or p2["id"] == p1.get("id")):
                            discarded_count += 1
                            continue
                        if not check_gender_compatibility(p0, p2) or not check_gender_compatibility(p1, p2):
                            discarded_count += 1
                            continue
                        if effective_gender == "men" and (_detect_gender(p0) == "women" or _detect_gender(p1) == "women" or _detect_gender(p2) == "women"):
                            discarded_count += 1
                            continue
                        if effective_gender == "women" and (_detect_gender(p0) == "men" or _detect_gender(p1) == "men" or _detect_gender(p2) == "men"):
                            discarded_count += 1
                            continue

                        total_p = p0["price"] + p1["price"] + p2["price"]
                        if budget and total_p > budget:
                            discarded_count += 1
                            continue

                        eval_02 = score_garment_pairing(p0, p2, user_skin_depth=user_skin_depth, user_undertone=user_undertone)
                        eval_12 = score_garment_pairing(p1, p2, user_skin_depth=user_skin_depth, user_undertone=user_undertone)
                        if not eval_02["is_compatible"] or not eval_12["is_compatible"]:
                            discarded_count += 1
                            continue

                        style_score = round((eval_02["total_score"] + eval_12["total_score"]) / 2.0, 3)
                        avg_rating = ((p0.get("rating", 4.0) + p1.get("rating", 4.0) + p2.get("rating", 4.0)) / (3.0 * 5.0))
                        overall_rank = round(0.70 * style_score + 0.30 * avg_rating, 3)
                        rationale = f"Curated 3-piece look: {p0.get('title', 'Piece 1')} & {p1.get('title', 'Piece 2')} paired with {p2.get('title', 'Piece 3')} within ₹{int(round(budget)) if budget else total_p}."

                        valid_bundles.append({
                            "items": [p0, p1, p2],
                            "total_price": total_p,
                            "budget_savings": round(budget - total_p, 2) if budget else 0.0,
                            "style_score": style_score,
                            "overall_rank": overall_rank,
                            "pairing_type": "three_piece_ensemble",
                            "sub_scores": eval_02.get("sub_scores", {}),
                            "rationale": rationale
                        })

            if not valid_bundles:
                sorted_0 = sorted(pool0, key=lambda x: x.get("price", 9999))
                sorted_1 = sorted(pool1, key=lambda x: x.get("price", 9999))
                sorted_2 = sorted(pool2, key=lambda x: x.get("price", 9999))
                for p0 in sorted_0:
                    for p1 in sorted_1:
                        if p0.get("id") and p1.get("id") and p0["id"] == p1["id"]: continue
                        if not check_gender_compatibility(p0, p1): continue
                        for p2 in sorted_2:
                            if p2.get("id") and (p2["id"] == p0.get("id") or p2["id"] == p1.get("id")): continue
                            if not check_gender_compatibility(p0, p2) or not check_gender_compatibility(p1, p2): continue
                            total_p = p0.get("price", 0) + p1.get("price", 0) + p2.get("price", 0)
                            if budget and total_p > budget: continue
                            eval_02 = score_garment_pairing(p0, p2, user_skin_depth=user_skin_depth, user_undertone=user_undertone)
                            valid_bundles.append({
                                "items": [p0, p1, p2],
                                "total_price": total_p,
                                "budget_savings": round(budget - total_p, 2) if budget else 0.0,
                                "style_score": 0.75,
                                "overall_rank": 0.72,
                                "pairing_type": "three_piece_essentials",
                                "sub_scores": eval_02.get("sub_scores", {}),
                                "rationale": f"Calibrated 3-piece essentials look: {p0.get('title', 'Upper 1')} and {p1.get('title', 'Upper 2')} with {p2.get('title', 'Lower')} within ₹{int(round(budget)) if budget else total_p}."
                            })
                            if len(valid_bundles) >= 5: break
                        if len(valid_bundles) >= 5: break
                    if len(valid_bundles) >= 5: break

            valid_bundles.sort(key=lambda x: x["overall_rank"], reverse=True)

            if not valid_bundles:
                min_0 = min((p["price"] for p in pool0), default=499.0)
                min_1 = min((p["price"] for p in pool1), default=499.0)
                min_2 = min((p["price"] for p in pool2), default=699.0)
                min_total = min_0 + min_1 + min_2
                return {
                    "mode": "bundle",
                    "status": "budget_too_low",
                    "budget": budget,
                    "min_total_required": min_total,
                    "alternatives": {
                        "message": f"Our closest 3-piece combination starts at ₹{int(round(min_total))}, exceeding your ₹{int(round(budget)) if budget else 3000} cap.",
                        "options": [
                            f"Adjust budget to ₹{int(round(min_total))} for 3 pieces",
                            "Switch to 2-piece combination under budget"
                        ],
                        "min_total": min_total
                    },
                    "bundles": []
                }

            hero = valid_bundles[0]
            alt = valid_bundles[1] if len(valid_bundles) > 1 else hero
            val = sorted(valid_bundles, key=lambda x: x["budget_savings"], reverse=True)[0]

            combos = [
                {
                    "id": "combo-1",
                    "name": "Combo 1: Hero 3-Piece Look",
                    "badge": "Top Stylist Match",
                    "tagline": "Optimal 3-Piece Aesthetic Harmony",
                    "total_price": hero["total_price"],
                    "budget_savings": hero["budget_savings"],
                    "style_score": hero["style_score"],
                    "bundle": hero
                }
            ]
            if alt and alt != hero:
                combos.append({
                    "id": "combo-2",
                    "name": "Combo 2: High Contrast",
                    "badge": "Streetwear Alternative",
                    "tagline": "Distinct Silhouette & Tone",
                    "total_price": alt["total_price"],
                    "budget_savings": alt["budget_savings"],
                    "style_score": alt["style_score"],
                    "bundle": alt
                })
            if val and val != hero and val != alt:
                combos.append({
                    "id": "combo-3",
                    "name": "Combo 3: Best Value",
                    "badge": "Budget Maximizer",
                    "tagline": f"Save ₹{int(val.get('budget_savings', 0))} under budget",
                    "total_price": val["total_price"],
                    "budget_savings": val["budget_savings"],
                    "style_score": val["style_score"],
                    "bundle": val
                })

            return {
                "mode": "bundle",
                "status": "success",
                "budget": budget,
                "gender": effective_gender,
                "allocated_budgets": {
                    c0_name: allocated_budgets[0] if len(allocated_budgets) > 0 else (budget or 1000.0),
                    c1_name: allocated_budgets[1] if len(allocated_budgets) > 1 else (budget or 1000.0),
                    c2_name: allocated_budgets[2] if len(allocated_budgets) > 2 else (budget or 1000.0)
                },
                "total_pairs_evaluated": len(pool0) * len(pool1) * len(pool2),
                "discarded_count": discarded_count,
                "valid_bundle_count": len(valid_bundles),
                "hero_bundle": hero,
                "alternative_bundle": alt,
                "value_bundle": val,
                "combos": combos,
                "all_bundles": valid_bundles[:15],
                "shelves": {
                    "tops": pool0,
                    "second_top": pool1,
                    "bottoms": pool2
                }
            }

        top_candidates = cat_products_map[cat_keys[0]]
        bottom_candidates = cat_products_map[cat_keys[1]]

        cat1_name = _normalize_category_name(items_to_buy[0].get("category", "t-shirt"))
        cat2_name = _normalize_category_name(items_to_buy[1].get("category", "joggers") if len(items_to_buy) > 1 else "joggers")

        # 2. Check for Low Budget Edge Case ($P_min)
        if not top_candidates or not bottom_candidates:
            # Check global catalog minimums
            min_top_price, min_bottom_price = self._find_catalog_minimums(
                cat1_name,
                cat2_name,
                provider=active_provider
            )
            min_total = min_top_price + min_bottom_price

            # Only report budget_too_low IF the user's budget is genuinely below store floor
            if budget and budget < min_total:
                alternatives = self._generate_low_budget_alternatives(
                    budget=budget,
                    min_total=min_total,
                    min_top=min_top_price,
                    min_bottom=min_bottom_price,
                    cat1=cat1_name,
                    cat2=cat2_name
                )
                return {
                    "mode": "bundle",
                    "status": "budget_too_low",
                    "budget": budget,
                    "min_total_required": min_total,
                    "alternatives": alternatives,
                    "bundles": []
                }

            # If budget >= min_total, the budget is NOT too low! Sub-budgets or filters were just too restrictive.
            # Perform a fallback unconstrained fetch up to the user's full budget
            if not top_candidates:
                top_candidates = self._fetch_candidates_parallel(
                    categories=self.expand_macro_categories(cat1_name),
                    max_price=budget,
                    gender=effective_gender,
                    limit=limit_per_category,
                    provider=active_provider
                )
            if not bottom_candidates:
                bottom_candidates = self._fetch_candidates_parallel(
                    categories=self.expand_macro_categories(cat2_name),
                    max_price=budget,
                    gender=effective_gender,
                    limit=limit_per_category,
                    provider=active_provider
                )

            # If still completely empty after relaxing price, it's an inventory deficit, not a budget constraint
            if not top_candidates or not bottom_candidates:
                return {
                    "mode": "bundle",
                    "status": "insufficient_inventory",
                    "message": f"Could not find available {cat1_name if not top_candidates else cat2_name} in stock.",
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

        # If no valid bundles found within initial filters:
        if not valid_bundles:
            min_top = min((t["price"] for t in top_candidates), default=699.0)
            min_bottom = min((b["price"] for b in bottom_candidates), default=899.0)
            min_total = min_top + min_bottom

            # Only return budget_too_low if lowest combination genuinely exceeds budget
            if budget and budget < min_total:
                alternatives = self._generate_low_budget_alternatives(
                    budget=budget,
                    min_total=min_total,
                    min_top=min_top,
                    min_bottom=min_bottom,
                    cat1=cat1_name,
                    cat2=cat2_name
                )
                return {
                    "mode": "bundle",
                    "status": "budget_too_low",
                    "budget": budget,
                    "min_total_required": min_total,
                    "alternatives": alternatives,
                    "bundles": []
                }

            # Otherwise, min_total <= budget! Style filtering was too strict, or pricing combinations missed.
            # Relax pairing by sorting by lowest price to assemble valid budget-conscious combinations
            sorted_tops = sorted(top_candidates, key=lambda x: x.get("price", 9999))
            sorted_bottoms = sorted(bottom_candidates, key=lambda x: x.get("price", 9999))

            for t in sorted_tops:
                for b in sorted_bottoms:
                    if t.get("id") and b.get("id") and t["id"] == b["id"]:
                        continue
                    if not check_gender_compatibility(t, b):
                        continue
                    total_p = t.get("price", 0) + b.get("price", 0)
                    if budget and total_p > budget:
                        continue
                    eval_res = score_garment_pairing(t, b, user_skin_depth=user_skin_depth, user_undertone=user_undertone)
                    valid_bundles.append({
                        "items": [t, b],
                        "total_price": total_p,
                        "budget_savings": round(budget - total_p, 2) if budget else 0.0,
                        "style_score": max(eval_res["total_score"], 70),
                        "overall_rank": 0.70,
                        "pairing_type": "stylist_curated_essentials",
                        "sub_scores": eval_res.get("sub_scores", {}),
                        "rationale": f"Clean coordinated pairing of {t.get('title', 'Upper')} with {b.get('title', 'Lower')} calibrated within your ₹{int(round(budget)) if budget else total_p} budget."
                    })
                    if len(valid_bundles) >= 5:
                        break
                if len(valid_bundles) >= 5:
                    break

        # Sort by overall rank descending
        valid_bundles.sort(key=lambda x: x["overall_rank"], reverse=True)

        if not valid_bundles:
            # Catalog truly cannot produce any pair under budget
            min_top = min((t["price"] for t in top_candidates), default=699.0)
            min_bottom = min((b["price"] for b in bottom_candidates), default=899.0)
            min_total = min_top + min_bottom
            alternatives = self._generate_low_budget_alternatives(
                budget=budget or min_total,
                min_total=min_total,
                min_top=min_top,
                min_bottom=min_bottom,
                cat1=cat1_name,
                cat2=cat2_name
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

        cat1_key = _normalize_category_name(items_to_buy[0].get("category")) if len(items_to_buy) > 0 else "item_1"
        cat2_key = _normalize_category_name(items_to_buy[1].get("category")) if len(items_to_buy) > 1 else "item_2"
        b1_val = allocated_budgets[0] if len(allocated_budgets) > 0 else (budget or 1500.0)
        b2_val = allocated_budgets[1] if len(allocated_budgets) > 1 else 0.0

        return {
            "mode": "bundle",
            "status": "success",
            "budget": budget,
            "gender": effective_gender,
            "allocated_budgets": {
                cat1_key: b1_val,
                cat2_key: b2_val
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
        c1 = _normalize_category_name(cat1).replace("categoryenum.", "").replace(".", " ").strip()
        c2 = _normalize_category_name(cat2).replace("categoryenum.", "").replace(".", " ").strip()
        c1_title = c1.title() if c1 else "Upper"
        c2_title = c2.title() if c2 else "Lower"

        b_val = int(round(budget)) if budget else 1500
        mt_val = int(round(min_total))
        mtop_val = int(round(min_top))
        mbot_val = int(round(min_bottom))

        message = (
            f"With your budget of {curr}{b_val}, coordinating quality {c1_title} and {c2_title} "
            f"pieces exceeds catalog floor prices, as our closest coordinated look starts at {curr}{mt_val} "
            f"({curr}{mtop_val} for {c1_title} + {curr}{mbot_val} for {c2_title})."
        )
        options = [
            f"Adjust budget to {curr}{mt_val} for the complete {c1_title} & {c2_title} outfit",
            f"Use your {curr}{b_val} budget to get a top-tier {c1_title} individually",
            f"Use your {curr}{b_val} budget to get a top-tier {c2_title} individually",
            f"Switch to a lighter combo (e.g. T-Shirt & Shorts) under {curr}{b_val}"
        ]
        return {
            "message": message,
            "options": options,
            "min_total": mt_val,
            "min_item1": mtop_val,
            "min_item2": mbot_val
        }
