"""Theater scrapers package.

Uses SerpAPI (Google Showtimes) as the unified data source for all theaters.
Individual theater website scrapers have been replaced by the SerpAPI approach
for reliability and zero-maintenance operation.
"""
from .serpapi_scraper import SerpAPIScraper

__all__ = ['SerpAPIScraper']
