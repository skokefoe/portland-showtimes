"""Theater scrapers package."""
from .base_scraper import BaseScraper
from .cinema21 import Cinema21Scraper
from .hollywood import HollywoodScraper
from .cinemagic import CinemagicScraper
from .bagdad import BagdadScraper
from .laurelhurst import LaurelhurstScraper
from .clinton import ClintonScraper
from .livingroom import LivingRoomScraper
from .academy import AcademyScraper
from .fallback_google import GoogleFallbackScraper

__all__ = [
    'BaseScraper',
    'Cinema21Scraper',
    'HollywoodScraper',
    'CinemagicScraper',
    'BagdadScraper',
    'LaurelhurstScraper',
    'ClintonScraper',
    'LivingRoomScraper',
    'AcademyScraper',
    'GoogleFallbackScraper',
]

# Scraper registry: primary scrapers for each theater
SCRAPER_MAP = {
    'cinema21': Cinema21Scraper,
    'hollywood': HollywoodScraper,
    'cinemagic': CinemagicScraper,
    'bagdad': BagdadScraper,
    'laurelhurst': LaurelhurstScraper,
    'clinton': ClintonScraper,
    'livingroom': LivingRoomScraper,
    'academy': AcademyScraper,
}

# Fallback scraper used when a primary scraper fails
FALLBACK_SCRAPER = GoogleFallbackScraper
