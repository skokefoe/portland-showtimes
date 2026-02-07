"""Cinema 21 scraper.

Cinema 21 is a Next.js app that renders content client-side.
We use Playwright to get the rendered HTML, then parse with BeautifulSoup.
"""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper


class Cinema21Scraper(BaseScraper):
    """Scraper for Cinema 21 (cinema21.com) using Playwright."""

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes from Cinema 21 using Playwright for JS rendering."""
        from playwright.sync_api import sync_playwright

        movies = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=(
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ))
            page.goto(self.theater_url, timeout=30000)
            page.wait_for_load_state('networkidle', timeout=15000)

            # Give React time to hydrate
            page.wait_for_timeout(3000)

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'html.parser')

        # Look for movie titles and showtimes in the rendered content
        # Try multiple strategies since we don't know exact selectors

        # Strategy 1: Find headings that look like movie titles
        movies = self._extract_from_rendered(soup, start_date, num_days)

        return movies

    def _extract_from_rendered(self, soup, start_date, num_days) -> List[Dict[str, Any]]:
        """Extract movies from Playwright-rendered HTML."""
        movies = []
        seen_titles = set()

        # Find all headings
        for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
            title = heading.get_text(strip=True)
            if not title or len(title) < 2 or len(title) > 100:
                continue
            if title.lower() in seen_titles:
                continue
            # Skip site navigation headings
            if title.lower() in ('cinema 21', 'now showing', 'coming soon', 'special events',
                                  'showtimes', 'about', 'contact', 'menu'):
                continue

            # Look for showtime data near this heading
            parent = heading.parent
            showtimes = self._find_times_nearby(parent, start_date)

            # Check for a link
            link = heading.find('a', href=True)
            if not link:
                link = parent.find('a', href=True) if parent else None
            movie_url = self.theater_url
            if link and link.get('href', '').startswith(('http', '/')):
                href = link['href']
                if href.startswith('/'):
                    href = f"https://www.cinema21.com{href}"
                movie_url = href

            if not showtimes:
                # Still include the movie with "See website" if it looks like a movie
                # (has a nearby image or description)
                has_context = parent and (parent.find('img') or parent.find('p'))
                if not has_context:
                    continue
                showtimes = [{'time': 'See website', 'url': movie_url, 'date': start_date.strftime('%Y-%m-%d')}]

            seen_titles.add(title.lower())
            movies.append(self._build_movie(title, '', movie_url, showtimes))

        return movies

    def _find_times_nearby(self, element, start_date):
        """Search for time patterns in an element and its children."""
        if not element:
            return []

        showtimes = []
        text = element.get_text(separator='\n')
        # Match time patterns: "7:00 PM", "4:30pm", "19:00"
        time_pattern = re.compile(r'\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\b')
        matches = time_pattern.findall(text)

        for match in matches:
            parsed = self.parse_time(match)
            if parsed and parsed != match:  # Only include if it was actually a time
                showtimes.append({
                    'time': parsed,
                    'url': self.theater_url,
                    'date': start_date.strftime('%Y-%m-%d')
                })

        return showtimes

    def _build_movie(self, title, description, url, showtimes) -> Dict[str, Any]:
        tmdb_data = self.search_tmdb(title)
        movie_slug = self.slugify(title)
        poster_path = None

        if tmdb_data and tmdb_data.get('poster_path'):
            poster_path = self.download_poster(tmdb_data['poster_path'], movie_slug)

        return {
            'title': title,
            'description': description or (tmdb_data.get('overview', '') if tmdb_data else ''),
            'poster': poster_path,
            'theater_id': self.theater_id,
            'theater_url': url,
            'letterboxd_url': self.get_letterboxd_url(
                title, tmdb_data.get('tmdb_id') if tmdb_data else None
            ),
            'showtimes': showtimes,
            'tmdb_id': tmdb_data.get('tmdb_id') if tmdb_data else None
        }
