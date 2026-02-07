"""Cinemagic Theater scraper.

The Cinemagic uses Squarespace. Movie titles appear as headings, showtimes as
text like "Friday, Feb 6 - 7:00", and ticket links point to
tickets.thecinemagictheater.com.
"""
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import requests
from .base_scraper import BaseScraper


class CinemagicScraper(BaseScraper):
    """Scraper for The Cinemagic (thecinemagictheater.com)."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36'
    }

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes from The Cinemagic."""
        movies = []

        response = requests.get(self.theater_url, timeout=15, headers=self.HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Strategy 1: Find ticket links and extract movie titles from URL slugs
        ticket_links = soup.find_all('a', href=re.compile(r'tickets\.thecinemagictheater\.com/movie/'))
        seen_slugs = set()
        movie_entries = []

        for link in ticket_links:
            href = link['href']
            slug_match = re.search(r'/movie/([^/?]+)', href)
            if not slug_match:
                continue
            slug = slug_match.group(1)
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            # Convert slug to title: "k-pop-demon-hunters" -> "K-Pop Demon Hunters"
            title = slug.replace('-', ' ').title()
            movie_entries.append({'title': title, 'ticket_url': href})

        # Strategy 2: Also scan for movie titles in headings
        if not movie_entries:
            headings = soup.find_all(['h1', 'h2', 'h3'])
            for h in headings:
                text = h.get_text(strip=True)
                if text and len(text) > 2 and len(text) < 80:
                    # Skip navigation/site headings
                    if text.lower() in ('the cinemagic theater', 'events', 'about', 'menu'):
                        continue
                    movie_entries.append({'title': text, 'ticket_url': self.theater_url})

        # Extract showtime text from the full page
        page_text = soup.get_text(separator='\n')
        showtime_pattern = re.compile(
            r'((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*),?\s+'
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2})\s*[-–]\s*(\d{1,2}:\d{2})',
            re.IGNORECASE
        )
        all_showtimes = showtime_pattern.findall(page_text)

        # Build final movie list
        for entry in movie_entries:
            title = entry['title']
            ticket_url = entry['ticket_url']

            # Try to match showtimes to this movie (heuristic: all showtimes are
            # global since Cinemagic is single-screen)
            showtimes = self._build_showtimes(all_showtimes, start_date, num_days, ticket_url)

            if not showtimes:
                # If we can't parse times, include with generic "See website"
                showtimes = [{'time': 'See website', 'url': ticket_url}]

            tmdb_data = self.search_tmdb(title)
            movie_slug = self.slugify(title)
            poster_path = None

            if tmdb_data and tmdb_data.get('poster_path'):
                poster_path = self.download_poster(tmdb_data['poster_path'], movie_slug)

            movies.append({
                'title': title,
                'description': tmdb_data.get('overview', '') if tmdb_data else '',
                'poster': poster_path,
                'theater_id': self.theater_id,
                'theater_url': ticket_url,
                'letterboxd_url': self.get_letterboxd_url(
                    title, tmdb_data.get('tmdb_id') if tmdb_data else None
                ),
                'showtimes': showtimes,
                'tmdb_id': tmdb_data.get('tmdb_id') if tmdb_data else None
            })

        return movies

    def _build_showtimes(self, raw_matches, start_date, num_days, url):
        """Convert regex matches to showtime dicts filtered by date range."""
        showtimes = []
        end_date = start_date + timedelta(days=num_days)

        for _, date_str, time_str in raw_matches:
            try:
                show_date = datetime.strptime(f"{date_str} {start_date.year}", '%b %d %Y')
                if show_date.date() < start_date.date():
                    continue
                if show_date.date() >= end_date.date():
                    continue
                parsed_time = self.parse_time(time_str)
                showtimes.append({
                    'time': parsed_time,
                    'url': url,
                    'date': show_date.strftime('%Y-%m-%d')
                })
            except ValueError:
                continue

        return showtimes
