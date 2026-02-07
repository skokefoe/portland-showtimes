"""Academy Theater scraper.

Academy uses Theme UI / CSS-in-JS and renders movie cards dynamically.
We use Playwright to get the rendered HTML, then parse the movie grid.
The site has "Now Playing" and "Coming Soon" tabs.
"""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper


class AcademyScraper(BaseScraper):
    """Scraper for Academy Theater (academytheaterpdx.com) using Playwright."""

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes from Academy Theater."""
        from playwright.sync_api import sync_playwright

        movies = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=(
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ))

            # Try the showtimes page first, then main page
            for url in [f"{self.theater_url}/showtimes", self.theater_url]:
                try:
                    page.goto(url, timeout=30000)
                    page.wait_for_load_state('networkidle', timeout=15000)
                    page.wait_for_timeout(3000)

                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')
                    movies = self._extract_movies(soup, start_date, num_days)
                    if movies:
                        break
                except Exception:
                    continue

            browser.close()

        return movies

    def _extract_movies(self, soup, start_date, num_days) -> List[Dict[str, Any]]:
        """Extract movies from rendered HTML."""
        movies = []
        seen_titles = set()

        # Academy shows movie cards in a grid. Each card has an image and title text.
        # Find elements with movie title text
        for elem in soup.find_all(['h2', 'h3', 'h4', 'a', 'div']):
            title = elem.get_text(strip=True)
            if not title or len(title) < 2 or len(title) > 80:
                continue
            if title.lower() in seen_titles:
                continue

            # Skip navigation/UI elements
            skip_words = ('academy theater', 'now playing', 'coming soon', 'showtimes',
                          'events', 'menu', 'shop', 'more', 'revival films', 'buy tickets',
                          'home', 'about', 'contact', 'gift cards', 'private events')
            if title.lower() in skip_words:
                continue

            # Check if this looks like a movie title (has associated image or is inside a card)
            parent = elem.parent
            has_image = parent and parent.find('img') if parent else False
            is_link = elem.name == 'a' and elem.get('href')

            # If it's a heading with an image nearby, likely a movie
            if not (has_image or (is_link and '/showtimes' not in str(elem.get('href', '')))):
                continue

            movie_url = self.theater_url
            if is_link:
                href = elem['href']
                if href.startswith('/'):
                    href = f"https://www.academytheaterpdx.com{href}"
                movie_url = href
            elif elem.name != 'a':
                link = elem.find('a', href=True)
                if not link and parent:
                    link = parent.find('a', href=True)
                if link:
                    href = link['href']
                    if href.startswith('/'):
                        href = f"https://www.academytheaterpdx.com{href}"
                    movie_url = href

            seen_titles.add(title.lower())

            showtimes = [{'time': 'See website', 'url': movie_url, 'date': start_date.strftime('%Y-%m-%d')}]
            movies.append(self._build_movie(title, '', movie_url, showtimes))

        return movies

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
