"""Living Room Theaters scraper.

Living Room uses a custom web component (Quasar framework) that renders
showtimes dynamically. We use Playwright to get the rendered content.
"""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper


class LivingRoomScraper(BaseScraper):
    """Scraper for Living Room Theaters (livingroomtheaters.com) using Playwright."""

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes from Living Room Theaters."""
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

            # Wait for the custom web component to load
            page.wait_for_load_state('networkidle', timeout=15000)
            page.wait_for_timeout(5000)  # Extra time for Quasar framework

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'html.parser')
        movies = self._extract_movies(soup, start_date, num_days)

        return movies

    def _extract_movies(self, soup, start_date, num_days) -> List[Dict[str, Any]]:
        """Extract movies from rendered HTML."""
        movies = []
        seen_titles = set()

        # Try Quasar-specific selectors first
        cards = soup.find_all(class_=re.compile(r'q-card|movie|film'))

        for card in cards:
            title_elem = card.find(['h1', 'h2', 'h3', 'h4', 'div'], class_=re.compile(r'title|name|heading'))
            if not title_elem:
                title_elem = card.find(['h1', 'h2', 'h3', 'h4'])
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 2 or title.lower() in seen_titles:
                continue

            seen_titles.add(title.lower())
            movie_url = self.theater_url

            link = card.find('a', href=True)
            if link:
                href = link['href']
                if href.startswith('/'):
                    href = f"{self.theater_url.rstrip('/')}{href}"
                movie_url = href

            # Look for time patterns
            showtimes = self._find_times(card, start_date, movie_url)
            if not showtimes:
                showtimes = [{'time': 'See website', 'url': movie_url, 'date': start_date.strftime('%Y-%m-%d')}]

            movies.append(self._build_movie(title, '', movie_url, showtimes))

        # Fallback: generic heading search
        if not movies:
            for heading in soup.find_all(['h1', 'h2', 'h3']):
                title = heading.get_text(strip=True)
                if not title or len(title) < 3 or len(title) > 80:
                    continue
                if title.lower() in seen_titles:
                    continue
                skip = ('living room', 'now showing', 'coming soon', 'menu', 'about')
                if title.lower() in skip:
                    continue

                parent = heading.parent
                if parent and parent.find('img'):
                    seen_titles.add(title.lower())
                    movies.append(self._build_movie(
                        title, '', self.theater_url,
                        [{'time': 'See website', 'url': self.theater_url, 'date': start_date.strftime('%Y-%m-%d')}]
                    ))

        return movies

    def _find_times(self, element, start_date, url):
        """Extract time patterns from an element."""
        showtimes = []
        text = element.get_text(separator=' ')
        time_pattern = re.compile(r'\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))\b')

        for match in time_pattern.findall(text):
            parsed = self.parse_time(match)
            showtimes.append({
                'time': parsed,
                'url': url,
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
