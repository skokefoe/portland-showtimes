"""Clinton Street Theater scraper.

Clinton uses WordPress with The Events Calendar plugin. Events have JSON-LD
structured data and use .tribe-events-calendar-list CSS classes.
"""
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import requests
from .base_scraper import BaseScraper


class ClintonScraper(BaseScraper):
    """Scraper for Clinton Street Theater (cstpdx.com)."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36'
    }

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes from Clinton Street Theater."""
        movies = []

        response = requests.get(self.theater_url, timeout=15, headers=self.HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Strategy 1: Parse JSON-LD structured data (most reliable)
        movies = self._parse_jsonld(soup, start_date, num_days)
        if movies:
            return movies

        # Strategy 2: Parse The Events Calendar HTML structure
        movies = self._parse_tribe_events(soup, start_date, num_days)
        if movies:
            return movies

        # Strategy 3: Generic heading + link parsing
        movies = self._parse_generic(soup, start_date, num_days)
        return movies

    def _parse_jsonld(self, soup, start_date, num_days) -> List[Dict[str, Any]]:
        """Extract events from JSON-LD structured data."""
        movies = []
        end_date = start_date + timedelta(days=num_days)

        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                events = data if isinstance(data, list) else [data]

                for event in events:
                    if event.get('@type') not in ('Event', 'ScreeningEvent'):
                        continue

                    title = event.get('name', '').strip()
                    if not title:
                        continue

                    # Parse start date
                    start_str = event.get('startDate', '')
                    if not start_str:
                        continue

                    try:
                        event_date = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                        if event_date.date() < start_date.date():
                            continue
                        if event_date.date() >= end_date.date():
                            continue
                    except ValueError:
                        continue

                    time_str = event_date.strftime('%I:%M %p').lstrip('0')
                    event_url = event.get('url', self.theater_url)
                    description = event.get('description', '')
                    image = event.get('image', '')

                    movies.append(self._build_movie(
                        title, description, event_url,
                        [{'time': time_str, 'url': event_url, 'date': event_date.strftime('%Y-%m-%d')}]
                    ))

            except (json.JSONDecodeError, TypeError):
                continue

        return movies

    def _parse_tribe_events(self, soup, start_date, num_days) -> List[Dict[str, Any]]:
        """Parse The Events Calendar plugin HTML."""
        movies = []
        end_date = start_date + timedelta(days=num_days)

        # Find event list items
        events = soup.find_all('article', class_=re.compile(r'tribe-events'))
        if not events:
            events = soup.find_all('div', class_=re.compile(r'tribe-events-calendar-list__event'))

        for event in events:
            try:
                # Title from .entry-title or any heading
                title_elem = event.find(class_='tribe-events-calendar-list__event-title')
                if not title_elem:
                    title_elem = event.find(['h1', 'h2', 'h3'], class_='entry-title')
                if not title_elem:
                    title_elem = event.find(['h1', 'h2', 'h3'])
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)

                # Link
                link = title_elem.find('a', href=True)
                if not link:
                    link = event.find('a', href=True)
                event_url = link['href'] if link else self.theater_url

                # Date/time from datetime attribute or text
                time_elem = event.find('time', attrs={'datetime': True})
                date_str = None
                time_str = 'See website'

                if time_elem:
                    dt_val = time_elem['datetime']
                    try:
                        event_dt = datetime.fromisoformat(dt_val.replace('Z', '+00:00'))
                        if event_dt.date() < start_date.date() or event_dt.date() >= end_date.date():
                            continue
                        date_str = event_dt.strftime('%Y-%m-%d')
                        time_str = event_dt.strftime('%I:%M %p').lstrip('0')
                    except ValueError:
                        date_str = start_date.strftime('%Y-%m-%d')

                # Description
                desc_elem = event.find(class_='tribe-events-calendar-list__event-description')
                if not desc_elem:
                    desc_elem = event.find('p')
                description = desc_elem.get_text(strip=True) if desc_elem else ''

                showtimes = [{'time': time_str, 'url': event_url, 'date': date_str or start_date.strftime('%Y-%m-%d')}]
                movies.append(self._build_movie(title, description, event_url, showtimes))

            except Exception as e:
                print(f"      Error parsing Clinton event: {e}")
                continue

        return movies

    def _parse_generic(self, soup, start_date, num_days) -> List[Dict[str, Any]]:
        """Generic fallback: find headings with links."""
        movies = []
        headings = soup.find_all(['h2', 'h3'])

        for h in headings:
            text = h.get_text(strip=True)
            if not text or len(text) < 3 or len(text) > 100:
                continue
            link = h.find('a', href=True)
            url = link['href'] if link else self.theater_url
            if '/event/' in url or '/events/' in url:
                movies.append(self._build_movie(
                    text, '', url,
                    [{'time': 'See website', 'url': url, 'date': start_date.strftime('%Y-%m-%d')}]
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
