"""SerpAPI-based showtime scraper.

Uses Google's showtimes data via SerpAPI to get reliable, structured
movie showtime data for all theaters. This replaces the individual
per-theater scrapers that relied on fragile CSS selectors.
"""
import os
import re
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


class SerpAPIScraper:
    """Fetches showtimes for a theater via SerpAPI (Google search results)."""

    SERPAPI_ENDPOINT = "https://serpapi.com/search.json"

    def __init__(self, theater_config: Dict[str, Any], tmdb_api_key: Optional[str] = None,
                 serpapi_key: Optional[str] = None):
        self.theater_id = theater_config['id']
        self.theater_name = theater_config['name']
        self.theater_url = theater_config['url']
        self.theater_address = theater_config.get('address', '')
        self.tmdb_api_key = tmdb_api_key or os.getenv('TMDB_API_KEY')
        self.serpapi_key = serpapi_key or os.getenv('SERPAPI_KEY')

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes for this theater via SerpAPI."""
        if not self.serpapi_key:
            print(f"   ! No SERPAPI_KEY set, skipping {self.theater_name}")
            return []

        query = f"{self.theater_name} showtimes"
        params = {
            "engine": "google",
            "q": query,
            "location": "Portland, Oregon, United States",
            "hl": "en",
            "gl": "us",
            "api_key": self.serpapi_key,
        }

        try:
            response = requests.get(self.SERPAPI_ENDPOINT, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"   ! SerpAPI request failed: {e}")
            return []

        movies = self._parse_showtimes(data, start_date)
        return movies

    def _parse_showtimes(self, data: Dict[str, Any], start_date: datetime) -> List[Dict[str, Any]]:
        """Parse SerpAPI response into our movie format."""
        movies = []
        seen_titles = set()

        showtimes_data = data.get('showtimes', [])
        if not showtimes_data:
            kg = data.get('knowledge_graph', {})
            if kg:
                movies.extend(self._parse_knowledge_graph(kg, start_date))
            return movies

        for day_block in showtimes_data:
            day_label = day_block.get('day', '')
            date_str = self._resolve_date(day_label, day_block.get('date', ''), start_date)

            for movie_entry in day_block.get('movies', []):
                title = self._clean_title(movie_entry.get('name', ''))
                if not title or title.lower() in seen_titles:
                    continue

                showings = movie_entry.get('showing', [])
                showtime_list = []
                for showing in showings:
                    times = showing.get('time', [])
                    show_type = showing.get('type', 'Standard')
                    for t in times:
                        showtime_list.append({
                            'time': self._normalize_time(t),
                            'url': self.theater_url,
                            'date': date_str,
                            'format': show_type,
                        })

                if not showtime_list:
                    continue

                seen_titles.add(title.lower())

                tmdb_data = self._search_tmdb(title)
                poster_path = None
                if tmdb_data and tmdb_data.get('poster_path'):
                    poster_path = self._download_poster(tmdb_data['poster_path'], self._slugify(title))

                movies.append({
                    'title': tmdb_data['title'] if tmdb_data else title,
                    'description': tmdb_data.get('overview', '') if tmdb_data else '',
                    'poster': poster_path,
                    'theater_id': self.theater_id,
                    'theater_url': self.theater_url,
                    'letterboxd_url': self._get_letterboxd_url(
                        title, tmdb_data.get('tmdb_id') if tmdb_data else None
                    ),
                    'showtimes': showtime_list,
                    'tmdb_id': tmdb_data.get('tmdb_id') if tmdb_data else None,
                })

            for theater_entry in day_block.get('theaters', []):
                theater_name = theater_entry.get('name', '')
                if not self._is_our_theater(theater_name):
                    continue

                for movie_entry in theater_entry.get('showing', []):
                    title = self._clean_title(movie_entry.get('name', movie_entry.get('movie', '')))
                    if not title or title.lower() in seen_titles:
                        continue

                    times = movie_entry.get('time', [])
                    show_type = movie_entry.get('type', 'Standard')
                    showtime_list = []
                    for t in times:
                        showtime_list.append({
                            'time': self._normalize_time(t),
                            'url': self.theater_url,
                            'date': date_str,
                            'format': show_type,
                        })

                    if not showtime_list:
                        continue

                    seen_titles.add(title.lower())

                    tmdb_data = self._search_tmdb(title)
                    poster_path = None
                    if tmdb_data and tmdb_data.get('poster_path'):
                        poster_path = self._download_poster(tmdb_data['poster_path'], self._slugify(title))

                    movies.append({
                        'title': tmdb_data['title'] if tmdb_data else title,
                        'description': tmdb_data.get('overview', '') if tmdb_data else '',
                        'poster': poster_path,
                        'theater_id': self.theater_id,
                        'theater_url': self.theater_url,
                        'letterboxd_url': self._get_letterboxd_url(
                            title, tmdb_data.get('tmdb_id') if tmdb_data else None
                        ),
                        'showtimes': showtime_list,
                        'tmdb_id': tmdb_data.get('tmdb_id') if tmdb_data else None,
                    })

        return movies

    def _parse_knowledge_graph(self, kg: Dict[str, Any], start_date: datetime) -> List[Dict[str, Any]]:
        """Try to extract showtimes from the knowledge graph panel."""
        movies = []
        showtimes = kg.get('showtimes', kg.get('movies_showing', []))
        if isinstance(showtimes, list):
            for entry in showtimes:
                title = self._clean_title(entry.get('name', entry.get('title', '')))
                if not title:
                    continue
                times = entry.get('times', entry.get('showtimes', []))
                if isinstance(times, str):
                    times = [times]
                showtime_list = [{
                    'time': self._normalize_time(t),
                    'url': self.theater_url,
                    'date': start_date.strftime('%Y-%m-%d'),
                } for t in times if t]

                if showtime_list:
                    tmdb_data = self._search_tmdb(title)
                    poster_path = None
                    if tmdb_data and tmdb_data.get('poster_path'):
                        poster_path = self._download_poster(tmdb_data['poster_path'], self._slugify(title))

                    movies.append({
                        'title': tmdb_data['title'] if tmdb_data else title,
                        'description': tmdb_data.get('overview', '') if tmdb_data else '',
                        'poster': poster_path,
                        'theater_id': self.theater_id,
                        'theater_url': self.theater_url,
                        'letterboxd_url': self._get_letterboxd_url(
                            title, tmdb_data.get('tmdb_id') if tmdb_data else None
                        ),
                        'showtimes': showtime_list,
                        'tmdb_id': tmdb_data.get('tmdb_id') if tmdb_data else None,
                    })
        return movies

    def _is_our_theater(self, name: str) -> bool:
        """Check if a theater name from search results matches this theater."""
        name_lower = name.lower()
        theater_lower = self.theater_name.lower()
        return (theater_lower in name_lower or
                name_lower in theater_lower or
                self.theater_id in name_lower.replace(' ', ''))

    def _clean_title(self, title: str) -> str:
        """Clean up movie title by removing promotional text."""
        if not title:
            return ''
        patterns = [
            r'\s*\(?\d{4}\)?\s*$',
            r'\s*[-\u2013]\s*Trailer$',
            r'\s*\|\s*.*$',
        ]
        for pat in patterns:
            title = re.sub(pat, '', title, flags=re.IGNORECASE)
        return title.strip()

    def _resolve_date(self, day_label: str, date_hint: str, start_date: datetime) -> str:
        """Convert SerpAPI day/date labels to YYYY-MM-DD format."""
        day_label_lower = day_label.lower()
        if day_label_lower == 'today':
            return start_date.strftime('%Y-%m-%d')
        elif day_label_lower == 'tomorrow':
            return (start_date + timedelta(days=1)).strftime('%Y-%m-%d')

        if date_hint:
            for fmt in ['%b %d', '%B %d']:
                try:
                    parsed = datetime.strptime(date_hint, fmt)
                    return parsed.replace(year=start_date.year).strftime('%Y-%m-%d')
                except ValueError:
                    continue

        days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for i, day_name in enumerate(days_of_week):
            if day_label_lower.startswith(day_name[:3]):
                current_dow = start_date.weekday()
                delta = (i - current_dow) % 7
                if delta == 0 and day_label_lower != 'today':
                    delta = 7
                return (start_date + timedelta(days=delta)).strftime('%Y-%m-%d')

        return start_date.strftime('%Y-%m-%d')

    def _normalize_time(self, time_str: str) -> str:
        """Normalize time string to consistent format."""
        time_str = time_str.strip()
        for fmt in ['%I:%M%p', '%I:%M %p', '%H:%M']:
            try:
                t = datetime.strptime(time_str, fmt)
                return t.strftime('%I:%M %p').lstrip('0')
            except ValueError:
                continue
        return time_str

    def _search_tmdb(self, title: str) -> Optional[Dict[str, Any]]:
        """Search TMDB for movie metadata."""
        if not self.tmdb_api_key:
            return None
        try:
            resp = requests.get(
                "https://api.themoviedb.org/3/search/movie",
                params={"api_key": self.tmdb_api_key, "query": title, "language": "en-US", "page": 1},
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json().get('results', [])
            if results:
                m = results[0]
                return {
                    'tmdb_id': m['id'],
                    'title': m['title'],
                    'overview': m.get('overview', ''),
                    'poster_path': m.get('poster_path'),
                }
        except Exception as e:
            print(f"   TMDB lookup failed for '{title}': {e}")
        return None

    def _download_poster(self, poster_path: str, slug: str) -> Optional[str]:
        """Download poster from TMDB and save locally."""
        if not poster_path:
            return None
        try:
            resp = requests.get(f"https://image.tmdb.org/t/p/w500{poster_path}", timeout=10)
            resp.raise_for_status()
            poster_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'docs', 'posters')
            os.makedirs(poster_dir, exist_ok=True)
            filename = f"{slug}.jpg"
            filepath = os.path.join(poster_dir, filename)
            if not os.path.exists(filepath):
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                print(f"   Downloaded poster: {filename}")
            return f"posters/{filename}"
        except Exception as e:
            print(f"   Poster download failed: {e}")
            return None

    def _get_letterboxd_url(self, title: str, tmdb_id: Optional[int] = None) -> str:
        if tmdb_id:
            return f"https://letterboxd.com/tmdb/{tmdb_id}/"
        return f"https://letterboxd.com/film/{self._slugify(title)}/"

    def _slugify(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-')
