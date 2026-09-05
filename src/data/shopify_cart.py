import os
import requests
from dotenv import load_dotenv

load_dotenv()

SHOPIFY_API_VERSION = "2024-04"

class ShopifyCartProvider:
    """Handles cart operations using Shopify Storefront API."""
    def __init__(self):
        self.domain = os.getenv("SHOPIFY_DOMAIN", "rasor-test-store-1.myshopify.com")
        self.storefront_token = (
            os.getenv("SHOPIFY_STOREFRONT_TOKEN")
            or os.getenv("SHOPIFY_STOREFRONT_ACCESS_TOKEN")
            or "6a1c1b2f3f1fafd8afc7040ed4e19307"
        )
        if not self.domain or not self.storefront_token:
            raise ValueError("Missing SHOPIFY_DOMAIN or SHOPIFY_STOREFRONT_TOKEN in env")

        if not self.domain.startswith("http"):
            self.domain = f"https://{self.domain}"
        self.endpoint = f"{self.domain}/api/{SHOPIFY_API_VERSION}/graphql.json"

        self.headers = {
            "Content-Type": "application/json",
            "X-Shopify-Storefront-Access-Token": self.storefront_token,
        }

    def _run_query(self, query: str, variables: dict = None) -> dict:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        resp = requests.post(self.endpoint, headers=self.headers, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[Shopify Cart] HTTP Error: {resp.status_code} - {resp.text}")
            return {}
            
        data = resp.json()
        if "errors" in data:
            print(f"[Shopify Cart] GraphQL Errors: {data['errors']}")
            return {}
            
        return data

    def create_cart(self, variant_id: str, quantity: int = 1) -> dict:
        """Creates a new cart with a single item. Returns cart data or error dict."""
        mutation = """
        mutation cartCreate($input: CartInput) {
          cartCreate(input: $input) {
            cart {
              id
              checkoutUrl
              totalQuantity
              cost {
                totalAmount { amount currencyCode }
              }
              lines(first: 5) {
                edges {
                  node {
                    id
                    quantity
                    merchandise {
                      ... on ProductVariant {
                        id
                        title
                        product { title }
                      }
                    }
                  }
                }
              }
            }
            userErrors { field message }
          }
        }
        """
        variables = {
            "input": {
                "lines": [
                    {
                        "merchandiseId": variant_id,
                        "quantity": quantity
                    }
                ]
            }
        }
        
        res = self._run_query(mutation, variables)
        cart_create_data = res.get("data", {}).get("cartCreate", {})
        
        errors = cart_create_data.get("userErrors", [])
        if errors:
            return {"success": False, "errors": errors}
            
        cart = cart_create_data.get("cart")
        if not cart:
            return {"success": False, "errors": [{"message": "Cart creation failed, no cart object returned"}]}
            
        return {
            "success": True,
            "cart_id": cart.get("id"),
            "checkout_url": cart.get("checkoutUrl"),
            "total_quantity": cart.get("totalQuantity"),
            "cost": cart.get("cost", {}).get("totalAmount", {}).get("amount"),
            "currency": cart.get("cost", {}).get("totalAmount", {}).get("currencyCode"),
            "lines": cart.get("lines", {}).get("edges", [])
        }

    def add_to_cart(self, cart_id: str, variant_id: str, quantity: int = 1) -> dict:
        """Adds items to an existing cart."""
        mutation = """
        mutation cartLinesAdd($cartId: ID!, $lines: [CartLineInput!]!) {
          cartLinesAdd(cartId: $cartId, lines: $lines) {
            cart {
              id
              checkoutUrl
              totalQuantity
              cost {
                totalAmount { amount currencyCode }
              }
            }
            userErrors { field message }
          }
        }
        """
        variables = {
            "cartId": cart_id,
            "lines": [{"merchandiseId": variant_id, "quantity": quantity}]
        }
        
        res = self._run_query(mutation, variables)
        cart_add_data = res.get("data", {}).get("cartLinesAdd", {})
        
        errors = cart_add_data.get("userErrors", [])
        if errors:
            return {"success": False, "errors": errors}
            
        cart = cart_add_data.get("cart")
        return {
            "success": True,
            "cart_id": cart.get("id"),
            "checkout_url": cart.get("checkoutUrl"),
            "total_quantity": cart.get("totalQuantity"),
            "cost": cart.get("cost", {}).get("totalAmount", {}).get("amount"),
            "currency": cart.get("cost", {}).get("totalAmount", {}).get("currencyCode"),
        }
