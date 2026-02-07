"""Bagdad Theater & Pub scraper.

McMenamins' Bagdad page has a tabbed interface with "Now Playing" and
"Coming Soon" sections. Movies have titles, ratings, runtimes, synopses,
and showtime buttons with date selectors.
"""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import requests
from .base_scraper import BaseScraper


class BagdadScraper(BaseScraper):
    """Scraper for Bagdad Theater & Pub (mcmenamins.com)."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36'
    }

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes from Bagdad Theater."""
        movies = []

        response = requests.get(self.theater_url, timeout=15, headers=self.HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # McMenamins uses heading + paragraph structure for movies
        # Look for movie sections with titles, ratings, and showtime links

        # Strategy 1: Find movie headings and nearby showtime data
        movie_headings = []
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            text = heading.get_text(strip=True)
            if not text or len(text) < 2:
                continue
            # Look for headings that have siblings with rating/runtime info
            next_sib = heading.find_next_sibling()
            if next_sib:
                sib_text = next_sib.get_text(strip=True) if next_sib else ''
                # McMenamins shows "R, Running time: 113 minutes" after title
                if re.search(r'(Running time|minutes|PG|PG-13|R,|NR)', sib_text):
                    movie_headings.append(heading)

        # Strategy 2: Find links that contain showtime patterns
        showtime_links = soup.find_all('a', href=re.compile(r'mcmenamins\.com.*ticket|showtime', re.I))

        # Strategy 3: Look for "See all dates & showtimes" links
        see_all_links = soup.find_all('a', string=re.compile(r'dates.*showtimes|showtimes', re.I))

        # Build movies from headings
        for heading in movie_headings:
            title = heading.get_text(strip=True)

            # Get description from nearby paragraph
            description = ''
            rating_runtime = ''
            for sibling in heading.find_next_siblings():
                sib_text = sibling.get_text(strip=True)
                if re.search(r'(Running time|minutes)', sib_text):
                    rating_runtime = sib_text
                elif sibling.name == 'p' and len(sib_text) > 20 and not description:
                    description = sib_text
                elif sibling.name in ('h2', 'h3', 'h4'):
                    break  # Next movie

            # Find showtime links near this heading
            showtimes = []
            parent = heading.parent
            if parent:
                time_links = parent.find_all('a', href=True)
                for link in time_links:
                    link_text = link.get_text(strip=True)
                    # Match time patterns like "7:00 PM" or "4:30pm"
                    if re.match(r'\d{1,2}:\d{2}\s*(AM|PM|am|pm)?', link_text):
                        parsed = self.parse_time(link_text)
                        showtimes.append({
                            'time': parsed,
                            'url': link.get('href', self.theater_url),
                            'date': start_date.strftime('%Y-%m-%d')
                        })

            # Find "See all dates" link for this movie
            movie_url = self.theater_url
            for sib in heading.find_next_siblings('a', href=True):
                if 'showtime' in sib.get_text(strip=True).lower() or 'dates' in sib.get_text(strip=True).lower():
                    movie_url = sib['href']
                    if not movie_url.startswith('http'):
                        movie_url = f"https://www.mcmenamins.com{movie_url}"
                    break

            if not showtimes:
                showtimes = [{'time': 'See website', 'url': movie_url, 'date': start_date.strftime('%Y-%m-%d')}]

            if rating_runtime and description:
                description = f"{rating_runtime} — {description}"
            elif rating_runtime:
                description = rating_runtime

            movies.append(self._build_movie(title, description, movie_url, showtimes))

        # If heading-based approach found nothing, try a broader search
        if not movies:
            movies = self._broad_search(soup, start_date)

        return movies

    def _broad_search(self, soup, start_date) -> List[Dict[str, Any]]:
        """Broader search for movie content on the page."""
        movies = []
        page_text = soup.get_text(separator='\n')

        # Look for "Now Playing" section and extract movie names
        now_playing_match = re.search(r'Now Playing(.*?)(?:Coming Soon|Prices|$)', page_text, re.DOTALL | re.IGNORECASE)
        if not now_playing_match:
            return movies

        section = now_playing_match.group(1)
        # Find lines that look like movie titles (capitalized, reasonable length)
        lines = [l.strip() for l in section.split('\n') if l.strip()]

        for line in lines:
            # Skip non-title lines
            if re.search(r'(Running time|minutes|ticket|price|before|after|\$)', line, re.I):
                continue
            if len(line) < 3 or len(line) > 80:
                continue
            # Title heuristic: starts with uppercase, no numbers at start
            if re.match(r'^[A-Z]', line) and not re.match(r'^\d', line):
                movies.append(self._build_movie(
                    line, '', self.theater_url,
                    [{'time': 'See website', 'url': self.theater_url, 'date': start_date.strftime('%Y-%m-%d')}]
                ))

        return movies

    def _build_movie(self, title, description, url, showtimes) -> Dict[str, Any]:
        """Build standard movie dict with TMDB enrichment."""
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
