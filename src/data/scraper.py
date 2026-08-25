"""Google Shopping scraper with multi-header rotation, selector cascading, retries, and transparent fallback logging."""

import re
import time
import urllib.parse
from typing import List, Optional, Tuple
import requests
from bs4 import BeautifulSoup
from src.agent.state import Product
from src.data.base import BaseCatalogProvider
from src.data.dev_catalog import DevCatalogProvider

# Pool of realistic browser user-agents for rotation
_USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.5 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) "
        "Gecko/20100101 Firefox/128.0"
    )
]

# Multiple Google Shopping selector strategies across different A/B layouts
_CARD_SELECTORS = [
    ".sh-dgr__content",
    ".sh-np__click-target",
    ".KZmu8e",
    "div[data-docid]",
    "div.pla-unit",
    "div.mnr-c",
    "div.xc3Idb"
]

_TITLE_SELECTORS = ["h3", ".tAxDx", ".translate-content", ".Lq5OHe", ".rgHvZc a", "div.BNeawe.vvjwJb.AP7Wnd"]
_PRICE_SELECTORS = [".a8Pemb", ".OFFNJ", "span.HRLxBb", "span.kHxwFf", ".a52qVo", "div.BNeawe.iBp4i.AP7Wnd"]
_MERCHANT_SELECTORS = [".aULzUe", ".IuHnof", ".E5ocAb", ".dD8AGc", ".Q71fv", ".eaLgGf"]


class GoogleShoppingScraper(BaseCatalogProvider):
    """Resilient Google Shopping scraper with retries, header rotation, and transparent error reporting."""

    def __init__(self, fallback_provider: Optional[BaseCatalogProvider] = None, max_retries: int = 3):
        self.fallback = fallback_provider or DevCatalogProvider()
        self.max_retries = max_retries
        self.last_status_message: str = "Initialized"
        self.last_used_source: str = "none"

    def _extract_products_from_soup(self, soup: BeautifulSoup, query: str, max_price: Optional[float], limit: int) -> List[Product]:
        """Tries multiple DOM selector cascades to extract product cards."""
        products: List[Product] = []

        # Find cards matching any of the known card selectors
        cards = []
        for selector in _CARD_SELECTORS:
            found = soup.select(selector)
            if found:
                cards = found
                break

        if not cards:
            return []

        for idx, card in enumerate(cards[:limit * 3]):
            # Extract title
            title = None
            for t_sel in _TITLE_SELECTORS:
                elem = card.select_one(t_sel)
                if elem and elem.get_text(strip=True):
                    title = elem.get_text(strip=True)
                    break

            # Extract price
            price_val = None
            for p_sel in _PRICE_SELECTORS:
                elem = card.select_one(p_sel)
                if elem and elem.get_text(strip=True):
                    raw_price = elem.get_text(strip=True)
                    clean_match = re.search(r"[\d,.]+", raw_price)
                    if clean_match:
                        try:
                            price_val = float(clean_match.group(0).replace(",", ""))
                            break
                        except ValueError:
                            continue

            if not title or price_val is None:
                continue

            if max_price is not None and price_val > max_price:
                continue

            # Extract merchant name
            merchant_name = "Google Shopping Merchant"
            for m_sel in _MERCHANT_SELECTORS:
                elem = card.select_one(m_sel)
                if elem and elem.get_text(strip=True):
                    merchant_name = elem.get_text(strip=True)
                    break

            prod = Product(
                id=f"LIVE-GS-{idx+1}",
                title=title,
                merchant=merchant_name,
                price=price_val,
                currency="USD",
                rating=4.5,
                in_stock=True,
                category="General",
                description=f"Live Google Shopping item from {merchant_name}.",
                tags=[t.lower() for t in query.split()],
                shipping_days=3,
                shipping_cost=0.0
            )
            products.append(prod)
            if len(products) >= limit:
                break

        return products

    def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        merchant: Optional[str] = None,
        limit: int = 5
    ) -> List[Product]:
        encoded_query = urllib.parse.quote_plus(query)
        urls = [
            f"https://www.google.com/search?tbm=shop&q={encoded_query}&hl=en&gl=us",
            f"https://www.google.com/search?q={encoded_query}&tbm=shop&hl=en",
            f"https://www.google.com/search?q={encoded_query}+buy+online&tbm=shop"
        ]

        attempt_errors = []

        # Try multiple attempts with rotated headers and URL variations
        for attempt in range(self.max_retries):
            ua = _USER_AGENTS[attempt % len(_USER_AGENTS)]
            target_url = urls[attempt % len(urls)]
            headers = {
                "User-Agent": ua,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            }

            try:
                print(f"🔄 [Live Scraper] Attempt {attempt+1}/{self.max_retries} for query '{query}'...")
                resp = requests.get(target_url, headers=headers, timeout=8)

                if resp.status_code == 429:
                    attempt_errors.append(f"Attempt {attempt+1}: HTTP 429 (Rate limited by Google)")
                    time.sleep(1.0)
                    continue

                if resp.status_code != 200:
                    attempt_errors.append(f"Attempt {attempt+1}: HTTP status {resp.status_code}")
                    continue

                # Check if Google served a CAPTCHA challenge
                if "sorry/index" in resp.url or "captcha" in resp.text.lower() and "recaptcha" in resp.text.lower():
                    attempt_errors.append(f"Attempt {attempt+1}: Google Bot CAPTCHA challenge triggered")
                    time.sleep(1.0)
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                extracted = self._extract_products_from_soup(soup, query, max_price, limit)

                if extracted:
                    self.last_status_message = f"🟢 Successfully scraped {len(extracted)} live products from Google Shopping (Attempt {attempt+1})."
                    self.last_used_source = "google_shopping_live"
                    print(self.last_status_message)
                    return extracted
                else:
                    attempt_errors.append(f"Attempt {attempt+1}: HTML received but 0 product cards matched known DOM selectors")

            except Exception as e:
                attempt_errors.append(f"Attempt {attempt+1}: Request Exception ({str(e)})")
                time.sleep(0.5)

        # If all retries failed, log explicit detailed reasons and execute fallback
        failure_summary = " | ".join(attempt_errors)
        self.last_status_message = (
            f"⚠️ All {self.max_retries} live Google Shopping attempts failed. "
            f"FALLBACK TRIGGERED: Using local structured catalog.\n"
            f"Exact Reason: {failure_summary}"
        )
        self.last_used_source = "fallback_dev_catalog"
        print(f"\n=======================================================\n{self.last_status_message}\n=======================================================\n")

        return self.fallback.search_products(query, category, max_price, min_rating, merchant, limit)

    def enrich_product(self, product: Product) -> Product:
        return self.fallback.enrich_product(product)
