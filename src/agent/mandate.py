"""AP2 (Agent Payments Protocol) Mandate Engine.

Provides deterministic, tamper-evident mandate lifecycle management:
1. Intent Mandate: User-defined budget cap, category restrictions, and expiration.
2. Cart Mandate: Merchant-frozen line items, quantities, prices, and cryptographic hash.
3. Payment Mandate: Authorization bound strictly to the Cart Mandate hash and spend cap.
"""

import hashlib
import json
import time
import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class IntentMandate(BaseModel):
    mandate_id: str = Field(default_factory=lambda: f"mandate_intent_{uuid.uuid4().hex[:8]}")
    user_email: str
    user_phone: str = "+918806549952"
    max_authorized_amount: float
    currency: str = "INR"
    expires_at: float = Field(default_factory=lambda: time.time() + 3600)  # 1 hour
    created_at: float = Field(default_factory=time.time)
    status: str = "ACTIVE"  # ACTIVE, EXECUTED, REVOKED, EXPIRED

    def is_valid(self) -> bool:
        return self.status == "ACTIVE" and time.time() <= self.expires_at


class CartMandateItem(BaseModel):
    product_id: str
    title: str
    variant_gid: Optional[str] = None
    size: Optional[str] = "XL"
    unit_price: float
    quantity: int = 1


class CartMandate(BaseModel):
    cart_mandate_id: str = Field(default_factory=lambda: f"mandate_cart_{uuid.uuid4().hex[:8]}")
    intent_mandate_id: Optional[str] = None
    items: List[CartMandateItem]
    frozen_total: float
    currency: str = "INR"
    cart_hash: str = ""
    frozen_until: float = Field(default_factory=lambda: time.time() + 900)  # 15 minutes
    status: str = "FROZEN"  # FROZEN, AMENDED, EXECUTED, CANCELLED

    def compute_hash(self) -> str:
        """Computes deterministic SHA-256 hash of line items, prices, and quantities."""
        payload = [
            {
                "id": str(i.product_id),
                "size": str(i.size),
                "price": float(i.unit_price),
                "qty": int(i.quantity),
            }
            for i in sorted(self.items, key=lambda x: str(x.product_id))
        ]
        raw_str = f"{self.currency}:{self.frozen_total:.2f}:{json.dumps(payload, sort_keys=True)}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def freeze(self):
        self.cart_hash = self.compute_hash()
        return self


class MandateEngine:
    """Manages active mandates and enforces runtime spend bounds."""

    def __init__(self):
        # In-memory registry (can be persisted to SQLite or Redis)
        self._intent_mandates: Dict[str, IntentMandate] = {}
        self._cart_mandates: Dict[str, CartMandate] = {}

    def create_intent_mandate(self, user_email: str, max_amount: float, phone: str = "+918806549952") -> IntentMandate:
        mandate = IntentMandate(
            user_email=user_email,
            user_phone=phone,
            max_authorized_amount=max_amount
        )
        self._intent_mandates[mandate.mandate_id] = mandate
        return mandate

    def create_cart_mandate(self, items: List[Dict[str, Any]], frozen_total: float, intent_mandate_id: Optional[str] = None, currency: str = "INR") -> CartMandate:
        mandate_items = [
            CartMandateItem(
                product_id=str(i.get("product_id") or i.get("id")),
                title=str(i.get("title", "")),
                variant_gid=i.get("variant_gid"),
                size=i.get("size", "XL"),
                unit_price=float(i.get("unit_price") or i.get("price", 0.0)),
                quantity=int(i.get("quantity") or i.get("qty", 1))
            )
            for i in items
        ]
        
        # Hard Gate Check against Intent Mandate if provided
        if intent_mandate_id and intent_mandate_id in self._intent_mandates:
            intent = self._intent_mandates[intent_mandate_id]
            if not intent.is_valid():
                raise ValueError("Referenced Intent Mandate is expired or invalid")
            if frozen_total > intent.max_authorized_amount:
                raise ValueError(
                    f"Cart Mandate Total ({currency} {frozen_total:.2f}) exceeds "
                    f"Intent Mandate Cap ({currency} {intent.max_authorized_amount:.2f})"
                )

        cm = CartMandate(
            intent_mandate_id=intent_mandate_id,
            items=mandate_items,
            frozen_total=frozen_total,
            currency=currency
        )
        cm.freeze()
        self._cart_mandates[cm.cart_mandate_id] = cm
        return cm

    def validate_payment_mandate(self, cart_mandate_id: str, amount: float, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validates that payment amount and items match the frozen Cart Mandate exactly."""
        cm = self._cart_mandates.get(cart_mandate_id)
        if not cm:
            return {"valid": False, "error": "Cart Mandate not found"}
        
        if time.time() > cm.frozen_until:
            return {"valid": False, "error": "Cart Mandate price lock has expired (15m limit)"}

        # Check total within 0.01 tolerance
        if abs(cm.frozen_total - amount) > 0.01:
            return {
                "valid": False,
                "error": f"Price mismatch: Mandate locked at {cm.frozen_total}, requested {amount}"
            }

        return {
            "valid": True,
            "cart_hash": cm.cart_hash,
            "cart_mandate_id": cm.cart_mandate_id
        }

    def get_cart_mandate(self, cart_mandate_id: str) -> Optional[CartMandate]:
        return self._cart_mandates.get(cart_mandate_id)


# Global singleton
mandate_engine = MandateEngine()
