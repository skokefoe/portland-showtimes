"""Laurelhurst Theater scraper.

The Laurelhurst website embeds a JavaScript variable `gbl_movies` containing
structured showtime data. We extract this JSON from the page source.
"""
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests
from .base_scraper import BaseScraper


class LaurelhurstScraper(BaseScraper):
    """Scraper for Laurelhurst Theater (laurelhursttheater.com)."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36'
    }

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes by extracting the gbl_movies JS variable."""
        movies = []

        response = requests.get(self.theater_url, timeout=15, headers=self.HEADERS)
        response.raise_for_status()
        html = response.text

        # Extract the gbl_movies JavaScript object
        match = re.search(r'var\s+gbl_movies\s*=\s*(\{.*?\});', html, re.DOTALL)
        if not match:
            print("      Could not find gbl_movies in page source")
            return movies

        try:
            movies_data = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            print(f"      Failed to parse gbl_movies JSON: {e}")
            return movies

        # Build date strings for filtering (format: YYYYMMDD)
        target_dates = set()
        for i in range(num_days):
            d = start_date + timedelta(days=i)
            target_dates.add(d.strftime('%Y%m%d'))

        for film_code, film in movies_data.items():
            title = film.get('title', '').strip()
            if not title:
                continue

            # Collect showtimes across target dates
            schedule = film.get('schedule', {})
            showtimes = []

            for date_key, date_shows in schedule.items():
                if date_key not in target_dates:
                    continue
                if isinstance(date_shows, list):
                    for show in date_shows:
                        time_str = show.get('timeStr', '')
                        if time_str:
                            parsed = self.parse_time(time_str)
                            showtimes.append({
                                'time': parsed,
                                'url': self.theater_url,
                                'date': f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]}"
                            })

            if not showtimes:
                continue

            # Get TMDB metadata
            tmdb_data = self.search_tmdb(title)
            movie_slug = self.slugify(title)
            poster_path = None

            if tmdb_data and tmdb_data.get('poster_path'):
                poster_path = self.download_poster(tmdb_data['poster_path'], movie_slug)
            elif film.get('posterURL'):
                # Use the theater's own poster URL as fallback
                poster_path = film['posterURL']

            description = tmdb_data.get('overview', '') if tmdb_data else ''
            rating = film.get('rating', '')
            length_min = film.get('lengthMin', '')
            if rating or length_min:
                meta = f"Rated {rating}" if rating else ''
                if length_min:
                    meta += f" | {length_min} min" if meta else f"{length_min} min"
                if description:
                    description = f"{meta} — {description}"
                else:
                    description = meta

            movies.append({
                'title': title,
                'description': description,
                'poster': poster_path,
                'theater_id': self.theater_id,
                'theater_url': self.theater_url,
                'letterboxd_url': self.get_letterboxd_url(
                    title, tmdb_data.get('tmdb_id') if tmdb_data else None
                ),
                'showtimes': showtimes,
                'tmdb_id': tmdb_data.get('tmdb_id') if tmdb_data else None
            })

        return movies
