"""Abstract base interface for all commerce data providers (Dev Mock, Scraper, API, MCP)."""

from abc import ABC, abstractmethod
from typing import List, Optional
from src.agent.state import Product


class BaseCatalogProvider(ABC):
    """Abstract interface that all catalog sources must implement."""

    @abstractmethod
    def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        gender: Optional[str] = None,
        color: Optional[str] = None,
        size: Optional[str] = None,
        design: Optional[str] = None,
        fandom: Optional[str] = None,
        fit: Optional[str] = None,
        sleeve: Optional[str] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        merchant: Optional[str] = None,
        limit: int = 6
    ) -> List[Product]:
        """Search products matching the criteria across all dimensions."""
        pass

    @abstractmethod
    def get_product_details(self, product_id: str) -> Optional[Product]:
        """Retrieve full details for a specific product ID."""
        pass
