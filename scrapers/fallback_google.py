"""
Fallback scraper that uses Google search results for showtimes.

When a theater's direct website scraper fails, this scraper searches Google
for "[theater name] showtimes" and parses the structured showtime data that
Google displays in its search results.
"""
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
import requests

from .base_scraper import BaseScraper


class GoogleFallbackScraper(BaseScraper):
    """Fallback scraper that extracts showtimes from Google search results."""

    # Polite delay between Google requests (seconds)
    REQUEST_DELAY = 2.0

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes via Google search results."""
        movies = []

        try:
            query = quote_plus(f"{self.theater_name} Portland OR showtimes")
            url = f"https://www.google.com/search?q={query}&hl=en"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9',
            }

            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Google showtime results appear in structured containers.
            # Look for common patterns Google uses.
            movies = self._parse_google_showtimes(soup)

            # Be polite to Google
            time.sleep(self.REQUEST_DELAY)

        except Exception as e:
            print(f"   [fallback] Google search failed for {self.theater_name}: {e}")

        return movies

    def _parse_google_showtimes(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse showtime data from Google search results HTML."""
        movies = []

        # Google uses various containers for showtimes.
        # Strategy: look for movie title + time patterns in the results.

        # Pattern 1: Look for structured showtime blocks
        # These often appear as divs with movie names and time links
        showtime_blocks = soup.find_all('div', attrs={'data-movie-name': True})

        for block in showtime_blocks:
            try:
                title = block.get('data-movie-name', '').strip()
                if not title:
                    continue

                times = []
                time_links = block.find_all('a', href=True)
                for link in time_links:
                    time_text = link.get_text(strip=True)
                    if re.match(r'\d{1,2}:\d{2}\s*(AM|PM|am|pm)?', time_text):
                        parsed = self.parse_time(time_text)
                        if parsed:
                            times.append({
                                'time': parsed,
                                'url': self.theater_url
                            })

                if title and times:
                    movies.append(self._build_movie_entry(title, times))

            except Exception as e:
                print(f"   [fallback] Error parsing block: {e}")
                continue

        # Pattern 2: Text-based extraction as broader fallback
        if not movies:
            movies = self._text_based_extraction(soup)

        return movies

    def _text_based_extraction(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract movie/showtime pairs from page text as a last resort."""
        movies = []

        # Look for text blocks that contain time patterns near movie-like titles
        # This is heuristic-based and less reliable
        all_text = soup.get_text(separator='\n')
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]

        current_title = None
        current_times = []

        # Time pattern: 1:00 PM, 7:30PM, etc
        time_pattern = re.compile(r'^(\d{1,2}:\d{2}\s*(AM|PM|am|pm))$')
        # Title heuristic: lines without times that aren't too short or too long
        title_pattern = re.compile(r'^[A-Z][\w\s\':,\-!\.]{3,60}$')

        for line in lines:
            time_match = time_pattern.match(line)

            if time_match:
                parsed = self.parse_time(line)
                if parsed:
                    current_times.append({
                        'time': parsed,
                        'url': self.theater_url
                    })
            elif title_pattern.match(line) and not any(skip in line.lower() for skip in
                    ['google', 'search', 'sign in', 'settings', 'tools', 'about',
                     'privacy', 'terms', 'feedback', 'portland']):
                # Save previous movie if we had one
                if current_title and current_times:
                    movies.append(self._build_movie_entry(current_title, current_times))

                current_title = line
                current_times = []

        # Don't forget last movie
        if current_title and current_times:
            movies.append(self._build_movie_entry(current_title, current_times))

        return movies

    def _build_movie_entry(self, title: str, showtimes: List[Dict]) -> Dict[str, Any]:
        """Build a standard movie entry dict with TMDB metadata."""
        tmdb_data = self.search_tmdb(title)
        movie_slug = self.slugify(title)
        poster_path = None

        if tmdb_data and tmdb_data.get('poster_path'):
            poster_path = self.download_poster(tmdb_data['poster_path'], movie_slug)

        return {
            'title': title,
            'description': tmdb_data.get('overview', '') if tmdb_data else '',
            'poster': poster_path,
            'theater_id': self.theater_id,
            'theater_url': self.theater_url,
            'letterboxd_url': self.get_letterboxd_url(
                title,
                tmdb_data.get('tmdb_id') if tmdb_data else None
            ),
            'showtimes': showtimes,
            'tmdb_id': tmdb_data.get('tmdb_id') if tmdb_data else None
        }
