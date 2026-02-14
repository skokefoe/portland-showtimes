"""Showtimes.com scraper.

Scrapes theater pages on showtimes.com for accurate, complete showtime data.
Each theater has a dedicated page with movie listings, dates, and times.
Uses cloudscraper to handle anti-bot protections (Cloudflare, etc.).
"""
import os
import re
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False


class ShowtimesComScraper:
    """Scrapes showtimes from showtimes.com theater pages."""

    USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )

    def __init__(self, theater_config: Dict[str, Any], tmdb_api_key: Optional[str] = None):
        self.theater_id = theater_config['id']
        self.theater_name = theater_config['name']
        self.theater_url = theater_config['url']
        self.showtimes_com_url = theater_config.get('showtimes_com_url', '')
        self.tmdb_api_key = tmdb_api_key or os.getenv('TMDB_API_KEY')
        self._tmdb_cache: Dict[str, Optional[Dict[str, Any]]] = {}

    def _get_session(self):
        """Create an HTTP session with anti-bot protection handling."""
        if HAS_CLOUDSCRAPER:
            scraper = cloudscraper.create_scraper(
                browser={'browser': 'chrome', 'platform': 'linux', 'desktop': True}
            )
            # Explicitly exclude Brotli encoding — the brotli C extension
            # may not be available on all runners, and gzip/deflate work fine.
            scraper.headers['Accept-Encoding'] = 'gzip, deflate'
            return scraper
        else:
            print("   ! cloudscraper not installed, using plain requests")
            session = requests.Session()
            session.headers.update({
                'User-Agent': self.USER_AGENT,
                'Accept-Encoding': 'gzip, deflate',
            })
            return session

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes for this theater from showtimes.com."""
        if not self.showtimes_com_url:
            print(f"   ! No showtimes.com URL for {self.theater_name}")
            return []

        session = self._get_session()

        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }

        # Fetch this week
        movies = self._fetch_page(session, headers, {'date': 'week'}, start_date)

        # Fetch next week if requesting more than 7 days
        if num_days > 7:
            next_week_start = start_date + timedelta(days=7)
            next_date_str = next_week_start.strftime('%m/%d/%Y')
            print(f"   Fetching next week ({next_date_str})...")
            next_movies = self._fetch_page(session, headers, {'date': next_date_str}, start_date)
            if next_movies:
                movies.extend(next_movies)
                print(f"   Next week: {len(next_movies)} movies")
            else:
                print(f"   Next week: no additional data")

        return movies

    def _fetch_page(self, session, headers, cookies, start_date):
        """Fetch and parse a single page of showtimes."""
        try:
            response = session.get(
                self.showtimes_com_url,
                headers=headers,
                cookies=cookies,
                timeout=30
            )
            response.raise_for_status()
            content_enc = response.headers.get('Content-Encoding', 'none')
            print(f"   HTTP {response.status_code}, {len(response.text)} chars, encoding={content_enc}")
        except requests.RequestException as e:
            print(f"   ! Failed to fetch {self.showtimes_com_url}: {e}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')

        # Diagnostic logging
        title_tag = soup.find('title')
        page_title = title_tag.get_text(strip=True) if title_tag else '(no title)'
        movie_items = soup.select('li.movie-info-box')
        print(f"   Page: {page_title}")
        print(f"   Movie elements found: {len(movie_items)}")

        if not movie_items:
            body = soup.find('body')
            if body:
                body_text = body.get_text(strip=True)[:200]
                print(f"   Body preview: {body_text}")
            else:
                print(f"   No <body> found, response preview: {response.text[:200]}")

        movies = self._parse_page(soup, start_date)
        return movies

    def _parse_page(self, soup: BeautifulSoup, start_date: datetime) -> List[Dict[str, Any]]:
        """Parse the theater page HTML into movie data."""
        movies = []
        movie_items = soup.select('li.movie-info-box')

        for item in movie_items:
            movie = self._parse_movie(item, start_date)
            if movie:
                movies.append(movie)

        return movies

    def _parse_movie(self, item, start_date: datetime) -> Optional[Dict[str, Any]]:
        """Parse a single movie listing."""
        heading = item.select_one('h2.media-heading')
        if not heading:
            return None
        title_link = heading.find('a', recursive=False)
        if not title_link:
            return None
        title = ''.join(title_link.find_all(string=True, recursive=False)).strip()
        if not title:
            title = title_link.get_text(strip=True)
            trailer_span = title_link.find('span', class_='watch-trailer')
            if trailer_span:
                title = title.replace(trailer_span.get_text(), '').strip()
        if not title:
            return None

        # Poster
        poster_img = item.select_one('div.media-left img, div.media-top img')
        poster_url = None
        if poster_img:
            poster_url = poster_img.get('src') or poster_img.get('data-src')

        # Showtimes
        showtimes = self._parse_showtimes(item, start_date)
        if not showtimes:
            return None

        # TMDB enrichment
        tmdb_data = self._search_tmdb(title)
        poster_path = None
        if poster_url and poster_url.startswith('http'):
            poster_path = self._download_poster_from_url(poster_url, self._slugify(title))
        elif tmdb_data and tmdb_data.get('poster_path'):
            poster_path = self._download_tmdb_poster(tmdb_data['poster_path'], self._slugify(title))

        return {
            'title': tmdb_data['title'] if tmdb_data else title,
            'description': tmdb_data.get('overview', '') if tmdb_data else '',
            'poster': poster_path,
            'theater_id': self.theater_id,
            'theater_url': self.theater_url,
            'letterboxd_url': self._get_letterboxd_url(
                title, tmdb_data.get('tmdb_id') if tmdb_data else None
            ),
            'showtimes': showtimes,
            'tmdb_id': tmdb_data.get('tmdb_id') if tmdb_data else None,
        }

    def _parse_showtimes(self, item, start_date: datetime) -> List[Dict[str, Any]]:
        """Parse showtime buttons from a movie listing."""
        showtimes = []
        ticket_div = item.select_one('div.ticketicons')
        if not ticket_div:
            return showtimes

        current_date = None

        for el in ticket_div.children:
            if not hasattr(el, 'name') or el.name is None:
                continue

            if el.name == 'button':
                text = el.get_text(strip=True)
                text_clean = text.rstrip(':')
                if self._looks_like_date_label(text_clean):
                    resolved = self._resolve_date(text_clean, start_date)
                    if resolved:
                        current_date = resolved
                elif current_date and self._looks_like_time(text):
                    showtimes.append({
                        'time': self._normalize_time(text),
                        'url': self.theater_url,
                        'date': current_date,
                    })

            elif el.name == 'a':
                time_btn = el.select_one('button')
                if time_btn and current_date:
                    time_text = time_btn.get_text(strip=True)
                    if self._looks_like_time(time_text):
                        ticket_url = el.get('href', self.theater_url)
                        showtimes.append({
                            'time': self._normalize_time(time_text),
                            'url': ticket_url if ticket_url.startswith('http') else self.theater_url,
                            'date': current_date,
                        })

        return showtimes

    def _looks_like_date_label(self, text: str) -> bool:
        """Check if text looks like a date label."""
        text = text.strip().rstrip(':')
        return bool(re.match(
            r'(Today|Tomorrow|Mon|Tue|Wed|Thu|Fri|Sat|Sun)',
            text, re.IGNORECASE
        ))

    def _resolve_date(self, date_text: str, start_date: datetime) -> Optional[str]:
        """Parse a date string like 'Thu, Feb 12' into YYYY-MM-DD."""
        date_text = date_text.strip().rstrip(':')
        for fmt in ['%a, %b %d', '%A, %B %d', '%b %d', '%B %d']:
            try:
                parsed = datetime.strptime(date_text, fmt)
                result = parsed.replace(year=start_date.year)
                if result.month < start_date.month - 1:
                    result = result.replace(year=start_date.year + 1)
                return result.strftime('%Y-%m-%d')
            except ValueError:
                continue

        lower = date_text.lower()
        if 'today' in lower:
            return start_date.strftime('%Y-%m-%d')
        if 'tomorrow' in lower:
            return (start_date + timedelta(days=1)).strftime('%Y-%m-%d')

        return None

    def _looks_like_time(self, text: str) -> bool:
        """Check if a string looks like a showtime."""
        return bool(re.match(r'\d{1,2}:\d{2}\s*(am|pm|AM|PM)', text.strip()))

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

    # --- TMDB helpers ---

    def _search_tmdb(self, title: str) -> Optional[Dict[str, Any]]:
        """Search TMDB for movie metadata (with caching)."""
        title_key = title.lower()
        if title_key in self._tmdb_cache:
            return self._tmdb_cache[title_key]

        if not self.tmdb_api_key:
            self._tmdb_cache[title_key] = None
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
                data = {
                    'tmdb_id': m['id'],
                    'title': m['title'],
                    'overview': m.get('overview', ''),
                    'poster_path': m.get('poster_path'),
                }
                self._tmdb_cache[title_key] = data
                return data
        except Exception as e:
            print(f"   TMDB lookup failed for '{title}': {e}")

        self._tmdb_cache[title_key] = None
        return None

    def _download_poster_from_url(self, url: str, slug: str) -> Optional[str]:
        """Download poster from a direct URL."""
        try:
            resp = requests.get(url, timeout=10, headers={'User-Agent': self.USER_AGENT})
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

    def _download_tmdb_poster(self, poster_path: str, slug: str) -> Optional[str]:
        """Download poster from TMDB."""
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
