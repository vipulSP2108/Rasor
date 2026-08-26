from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from src.data.constants import ACTIVE_OFFERS, MerchantOffer, OfferType, OfferEvaluation

class OfferEngine:
    @staticmethod
    def evaluate_cart(items_in_cart: Dict[str, int], prod_lookup: Dict[str, Any], currency_sym: str = "₹") -> List[OfferEvaluation]:
        """
        Evaluates the current cart contents against all ACTIVE_OFFERS.
        Returns a list of OfferEvaluation objects detailing unlocked savings or proactive upsells.
        """
        evaluations = []
        
        # Calculate raw totals
        raw_total_cost = 0.0
        for pid, qty in items_in_cart.items():
            p = prod_lookup.get(pid)
            if p:
                raw_total_cost += p.price * qty

        for offer in ACTIVE_OFFERS:
            if offer.offer_type == OfferType.BULK_FIXED_PRICE:
                # Count applicable items
                applicable_qty = 0
                applicable_cost = 0.0
                
                for pid, qty in items_in_cart.items():
                    p = prod_lookup.get(pid)
                    if not p:
                        continue
                    
                    # Check if the product explicitly has the offer embedded in its description (from CSV/API)
                    is_applicable = False
                    
                    desc = p.specs.get("description", "")
                    # Construct the expected offer string, e.g. "Buy 3 for 1199"
                    offer_string = f"Buy {offer.min_quantity} for {int(offer.target_price)}"
                    
                    if desc and offer_string in desc:
                        is_applicable = True
                    else:
                        # Fallback to category matching
                        if not offer.applicable_categories:
                            is_applicable = True
                        else:
                            title_lower = p.title.lower()
                            for cat in offer.applicable_categories:
                                if f" {cat.lower()} " in f" {title_lower} " or title_lower.startswith(f"{cat.lower()} ") or title_lower.endswith(f" {cat.lower()}") or title_lower == cat.lower():
                                    is_applicable = True
                                    break
                                
                    if is_applicable:
                        applicable_qty += qty
                        applicable_cost += (p.price * qty)

                # Evaluate Bulk Offer
                if applicable_qty >= offer.min_quantity:
                    # Unlocked! Calculate savings
                    # E.g. Buy 3 for 1199. If they bought 3 items worth 1500, savings = 1500 - 1199 = 301
                    savings = applicable_cost - offer.target_price
                    if savings < 0:
                        savings = 0.0 # Don't apply if somehow the items were cheaper already
                    
                    evaluations.append(OfferEvaluation(
                        offer=offer,
                        is_unlocked=True,
                        estimated_savings=savings,
                        success_message=f"🎉 **{offer.title} Unlocked!** You saved {currency_sym}{savings:.0f}."
                    ))
                elif applicable_qty > 0:
                    # Near Unlock! Show Proactive Upsell
                    qty_away = offer.min_quantity - applicable_qty
                    evaluations.append(OfferEvaluation(
                        offer=offer,
                        is_unlocked=False,
                        quantity_away=qty_away,
                        upsell_message=f"🎁 **Unlock Special Pricing!** You are {qty_away} item(s) away from '{offer.description}'. Add more to save!"
                    ))

        # Evaluate Spend Threshold Offers
        spend_offers = [o for o in ACTIVE_OFFERS if o.offer_type == OfferType.SPEND_THRESHOLD_PERCENT]
        spend_offers.sort(key=lambda x: x.min_spend)
        
        highest_unlocked = None
        closest_locked = None
        
        for offer in spend_offers:
            if raw_total_cost >= offer.min_spend:
                highest_unlocked = offer
            elif raw_total_cost > 0 and closest_locked is None:
                closest_locked = offer
                
        if highest_unlocked:
            savings = raw_total_cost * (highest_unlocked.discount_percent / 100.0)
            evaluations.append(OfferEvaluation(
                offer=highest_unlocked,
                is_unlocked=True,
                estimated_savings=savings,
                success_message=f"🎉 **{highest_unlocked.title} Unlocked!** You saved {currency_sym}{savings:.0f} ({highest_unlocked.discount_percent}% off)."
            ))
            
        if closest_locked:
            amount_away = closest_locked.min_spend - raw_total_cost
            if amount_away < (closest_locked.min_spend * 0.8): # Show if they've spent at least 20% of the threshold
                evaluations.append(OfferEvaluation(
                    offer=closest_locked,
                    is_unlocked=False,
                    amount_away=amount_away,
                    upsell_message=f"🎁 **Almost there!** Spend just {currency_sym}{amount_away:.0f} more to unlock {closest_locked.discount_percent}% off your entire cart!"
                ))
                        
        return evaluations
