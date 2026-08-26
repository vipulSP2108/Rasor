from typing import List, Dict, Any
from src.agent.offers import MerchantOffer
from src.data.constants import COMPLEMENTARY_MAP
from src.agent.state import Product

class RecommenderAgent:
    def __init__(self, provider):
        """
        Takes a reference to a CatalogProvider to execute searches.
        """
        self.provider = provider
        
    def get_fast_bundle_recs(self, offer: MerchantOffer, items_in_cart: Dict[str, int]) -> List[Product]:
        """
        Level 1 Recommendation: Fast cache/direct category search.
        Used to help users quickly fulfill a Bulk Deal (e.g. "Buy 3 Polos").
        """
        if not offer.applicable_categories:
            return []
            
        target_category = offer.applicable_categories[0]
        # Perform a fast search for the target category
        results = self.provider.search_products(target_category)
        
        # Filter out items already in the cart
        recommendations = [p for p in results if p.id not in items_in_cart]
        
        # Return top 3
        return recommendations[:3]
        
    def get_smart_complementary_recs(self, items_in_cart: Dict[str, int], prod_lookup: Dict[str, Product], amount_away: float) -> Dict[str, List[Product]]:
        """
        Level 2 Recommendation: True 2-Layer System.
        Analyzes the cart, determines dominant category and gender.
        Returns a dict with 'same_category' and 'complementary_category' lists.
        """
        if not items_in_cart:
            return {"same_category": [], "complementary_category": []}
            
        # 1. Analyze the cart to find the dominant item
        dominant_product = None
        highest_cost = -1.0
        
        for pid, qty in items_in_cart.items():
            p = prod_lookup.get(pid)
            if p and (p.price * qty) > highest_cost:
                highest_cost = p.price * qty
                dominant_product = p
                
        if not dominant_product:
            return {"same_category": [], "complementary_category": []}
            
        # 2. Determine its category and gender heuristically
        dominant_category = "T-shirt"
        for cat in COMPLEMENTARY_MAP.keys():
            if cat.lower() in dominant_product.title.lower() or cat.lower() in dominant_product.category.lower():
                dominant_category = cat
                break
                
        gender = ""
        lower_title = dominant_product.title.lower()
        if "men" in lower_title or "men's" in lower_title:
            gender = "Men"
        elif "women" in lower_title or "women's" in lower_title:
            gender = "Women"
            
        # 3. Pick a complementary category
        comps = COMPLEMENTARY_MAP.get(dominant_category, [])
        target_comp = comps[0] if comps else "Accessories"
        
        # 4. Formulate Search Queries with Gender Consistency
        same_query = f"{gender} {dominant_category}".strip()
        comp_query = f"{gender} {target_comp}".strip()
        
        # 5. Search for the categories
        same_results = self.provider.search_products(same_query)
        comp_results = self.provider.search_products(comp_query)
        
        # 6. Filter and return
        same_recs = [p for p in same_results if p.id not in items_in_cart]
        comp_recs = [p for p in comp_results if p.id not in items_in_cart]
        
        same_recs.sort(key=lambda p: abs(p.price - amount_away))
        comp_recs.sort(key=lambda p: abs(p.price - amount_away))
        
        return {
            "same_category": same_recs[:4],
            "complementary_category": comp_recs[:4]
        }
