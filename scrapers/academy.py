"""Academy Theater scraper."""
from datetime import datetime
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import requests
from .base_scraper import BaseScraper


class AcademyScraper(BaseScraper):
    """Scraper for Academy Theater."""

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes from Academy Theater."""
        movies = []

        try:
            response = requests.get(self.theater_url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            movie_containers = soup.find_all(['div', 'article'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['movie', 'film', 'show']
            ))

            for container in movie_containers:
                try:
                    title_elem = container.find(['h1', 'h2', 'h3', 'h4'])
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    desc_elem = container.find('p')
                    description = desc_elem.get_text(strip=True) if desc_elem else ''

                    link_elem = container.find('a', href=True)
                    movie_url = link_elem['href'] if link_elem else self.theater_url
                    if not movie_url.startswith('http'):
                        movie_url = f"{self.theater_url.rstrip('/')}/{movie_url.lstrip('/')}"

                    time_elems = container.find_all(['time', 'span'])
                    showtimes = []

                    for time_elem in time_elems:
                        time_text = time_elem.get_text(strip=True)
                        parsed_time = self.parse_time(time_text)
                        if parsed_time:
                            showtimes.append({'time': parsed_time, 'url': movie_url})

                    if showtimes:
                        tmdb_data = self.search_tmdb(title)
                        movie_slug = self.slugify(title)
                        poster_path = None

                        if tmdb_data and tmdb_data.get('poster_path'):
                            poster_path = self.download_poster(tmdb_data['poster_path'], movie_slug)

                        movies.append({
                            'title': title,
                            'description': description or (tmdb_data.get('overview', '') if tmdb_data else ''),
                            'poster': poster_path,
                            'theater_id': self.theater_id,
                            'theater_url': movie_url,
                            'letterboxd_url': self.get_letterboxd_url(title, tmdb_data.get('tmdb_id') if tmdb_data else None),
                            'showtimes': showtimes,
                            'tmdb_id': tmdb_data.get('tmdb_id') if tmdb_data else None
                        })

                except Exception as e:
                    print(f"Error parsing movie in Academy: {e}")
                    continue

        except Exception as e:
            print(f"Error fetching Academy showtimes: {e}")

        return movies
