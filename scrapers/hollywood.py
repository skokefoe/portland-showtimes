"""Hollywood Theatre scraper.

Hollywood Theatre returns 403 for automated requests (Cloudflare protection).
This scraper intentionally returns empty results so the fallback scraper
(Google search) handles it instead.
"""
from datetime import datetime
from typing import List, Dict, Any
from .base_scraper import BaseScraper


class HollywoodScraper(BaseScraper):
    """Scraper for Hollywood Theatre - defers to fallback due to 403 blocking."""

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Returns empty list to trigger fallback scraper."""
        print("      Hollywood Theatre blocks automated access (403)")
        print("      Deferring to fallback scraper...")
        return []
