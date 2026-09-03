import os
import requests
from dotenv import load_dotenv

load_dotenv()

SHOPIFY_API_VERSION = "2024-04"

class ShopifyAdminProvider:
    """Handles order creation and retrieval using Shopify Admin REST API."""
    def __init__(self):
        self.domain = os.getenv("SHOPIFY_DOMAIN", "")
        self.admin_token = os.getenv("SHOPIFY_ADMIN_TOKEN", "")
        
        if not self.domain or not self.admin_token:
            print("WARNING: Missing SHOPIFY_DOMAIN or SHOPIFY_ADMIN_TOKEN in env.")
            
        if not self.domain.startswith("http"):
            self.domain = f"https://{self.domain}"
            
        self.base_url = f"{self.domain}/admin/api/{SHOPIFY_API_VERSION}"
        self.headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.admin_token,
        }

    def create_paid_order(self, cart_items, currency: str, total_amount: float, transaction_id: str, email: str = "agentic@rasor.test", payment_id: str = None) -> dict:
        """
        Creates an order in Shopify directly, marking it as paid.
        cart_items should be a list of CartItem objects.
        """
        # Map our cart items to Shopify line items format
        line_items = []
        for item in cart_items:
            line_items.append({
                "title": item.title,
                "price": str(item.unit_price),
                "quantity": item.quantity,
                "vendor": item.merchant
            })

        note_str = f"Razorpay Payment: {payment_id} | Order: {transaction_id}" if payment_id else f"Razorpay Order: {transaction_id}"

        payload = {
            "order": {
                "email": email,
                "financial_status": "paid",
                "currency": currency,
                "note": note_str,
                "note_attributes": [
                    {"name": "payment_id", "value": str(payment_id or "")},
                    {"name": "razorpay_order_id", "value": str(transaction_id or "")}
                ],
                "line_items": line_items,
                "transactions": [
                    {
                        "kind": "sale",
                        "status": "success",
                        "amount": str(total_amount),
                        "gateway": "razorpay",
                        "authorization": payment_id or transaction_id
                    }
                ],
                "tags": "agentic-commerce, rasor-demo"
            }
        }
        
        try:
            resp = requests.post(f"{self.base_url}/orders.json", headers=self.headers, json=payload, timeout=10)
            if resp.status_code in (200, 201):
                data = resp.json()
                return {"success": True, "order_id": data.get("order", {}).get("id"), "order_name": data.get("order", {}).get("name")}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_recent_orders(self, limit: int = 10) -> list:
        """
        Fetches the most recent orders from the Shopify Admin API to verify the agent's actions.
        """
        try:
            resp = requests.get(f"{self.base_url}/orders.json?status=any&limit={limit}", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("orders", [])
            else:
                print(f"[Shopify Admin] Error fetching orders: {resp.text}")
                return []
        except Exception as e:
            print(f"[Shopify Admin] Exception fetching orders: {e}")
            return []
