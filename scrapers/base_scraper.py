"""Base scraper class for theater showtimes."""
import os
import json
import requests
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz


class BaseScraper(ABC):
    """Base class for theater scrapers."""

    def __init__(self, theater_config: Dict[str, Any], tmdb_api_key: Optional[str] = None):
        """
        Initialize scraper with theater configuration.

        Args:
            theater_config: Theater metadata (id, name, url, etc.)
            tmdb_api_key: TMDB API key for movie metadata
        """
        self.theater_id = theater_config['id']
        self.theater_name = theater_config['name']
        self.theater_url = theater_config['url']
        self.theater_address = theater_config.get('address', '')
        self.tmdb_api_key = tmdb_api_key or os.getenv('TMDB_API_KEY')
        self.portland_tz = pytz.timezone('America/Los_Angeles')

    @abstractmethod
    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """
        Fetch showtimes for the theater.

        Args:
            start_date: Start date for showtimes
            num_days: Number of days to fetch (default 7)

        Returns:
            List of movie dictionaries with showtimes
        """
        pass

    def search_tmdb(self, title: str) -> Optional[Dict[str, Any]]:
        """
        Search TMDB for movie metadata.

        Args:
            title: Movie title to search

        Returns:
            Movie metadata dict or None
        """
        if not self.tmdb_api_key:
            print(f"Warning: No TMDB API key, skipping metadata for {title}")
            return None

        try:
            url = "https://api.themoviedb.org/3/search/movie"
            params = {
                "api_key": self.tmdb_api_key,
                "query": title,
                "language": "en-US",
                "page": 1
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get('results'):
                movie = data['results'][0]  # Take first result
                return {
                    'tmdb_id': movie['id'],
                    'title': movie['title'],
                    'overview': movie.get('overview', ''),
                    'poster_path': movie.get('poster_path'),
                    'release_date': movie.get('release_date'),
                    'vote_average': movie.get('vote_average', 0)
                }
        except Exception as e:
            print(f"Error searching TMDB for '{title}': {e}")

        return None

    def download_poster(self, poster_path: str, movie_slug: str) -> Optional[str]:
        """
        Download movie poster from TMDB.

        Args:
            poster_path: TMDB poster path
            movie_slug: Slugified movie title for filename

        Returns:
            Local poster path or None
        """
        if not poster_path:
            return None

        try:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            response = requests.get(poster_url, timeout=10)
            response.raise_for_status()

            # Save to docs/posters/
            poster_filename = f"{movie_slug}.jpg"
            poster_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs', 'posters')
            os.makedirs(poster_dir, exist_ok=True)

            poster_filepath = os.path.join(poster_dir, poster_filename)

            # Only download if doesn't exist
            if not os.path.exists(poster_filepath):
                with open(poster_filepath, 'wb') as f:
                    f.write(response.content)
                print(f"Downloaded poster: {poster_filename}")

            return f"posters/{poster_filename}"

        except Exception as e:
            print(f"Error downloading poster: {e}")
            return None

    def slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-')

    def get_letterboxd_url(self, title: str, tmdb_id: Optional[int] = None) -> str:
        """
        Generate Letterboxd URL for a movie.

        Args:
            title: Movie title
            tmdb_id: TMDB ID if available

        Returns:
            Letterboxd URL
        """
        if tmdb_id:
            return f"https://letterboxd.com/tmdb/{tmdb_id}/"
        else:
            slug = self.slugify(title)
            return f"https://letterboxd.com/film/{slug}/"

    def parse_time(self, time_str: str) -> Optional[str]:
        """
        Parse time string to standardized format.

        Args:
            time_str: Time string (e.g., "7:00 PM", "19:00")

        Returns:
            Standardized time string or None
        """
        try:
            # Try various time formats
            for fmt in ['%I:%M %p', '%I:%M%p', '%H:%M']:
                try:
                    time_obj = datetime.strptime(time_str.strip(), fmt)
                    return time_obj.strftime('%I:%M %p').lstrip('0')
                except ValueError:
                    continue
        except Exception as e:
            print(f"Error parsing time '{time_str}': {e}")

        return time_str  # Return original if parsing fails
