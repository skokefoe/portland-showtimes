"""Cinema 21 scraper."""
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import requests
from .base_scraper import BaseScraper


class Cinema21Scraper(BaseScraper):
    """Scraper for Cinema 21."""

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes from Cinema 21."""
        movies = []

        try:
            # Cinema 21 typically has a calendar or now-showing page
            response = requests.get(self.theater_url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for common showtime patterns
            # This is a template - will need adjustment based on actual HTML structure
            movie_containers = soup.find_all(['div', 'article'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['movie', 'film', 'show', 'event']
            ))

            for container in movie_containers:
                try:
                    # Extract title
                    title_elem = container.find(['h1', 'h2', 'h3', 'h4'], class_=lambda x: x and 'title' in str(x).lower())
                    if not title_elem:
                        title_elem = container.find(['h1', 'h2', 'h3', 'h4'])

                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)

                    # Extract description
                    desc_elem = container.find(['p', 'div'], class_=lambda x: x and any(
                        keyword in str(x).lower() for keyword in ['description', 'synopsis', 'summary']
                    ))
                    description = desc_elem.get_text(strip=True) if desc_elem else ''

                    # Extract link
                    link_elem = container.find('a', href=True)
                    movie_url = link_elem['href'] if link_elem else self.theater_url
                    if not movie_url.startswith('http'):
                        movie_url = f"{self.theater_url.rstrip('/')}/{movie_url.lstrip('/')}"

                    # Extract showtimes
                    time_elems = container.find_all(['time', 'span', 'div'], class_=lambda x: x and 'time' in str(x).lower())
                    showtimes = []

                    for time_elem in time_elems:
                        time_text = time_elem.get_text(strip=True)
                        parsed_time = self.parse_time(time_text)
                        if parsed_time:
                            showtimes.append({
                                'time': parsed_time,
                                'url': movie_url
                            })

                    if showtimes:
                        # Get TMDB metadata
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
                            'letterboxd_url': self.get_letterboxd_url(
                                title,
                                tmdb_data.get('tmdb_id') if tmdb_data else None
                            ),
                            'showtimes': showtimes,
                            'tmdb_id': tmdb_data.get('tmdb_id') if tmdb_data else None
                        })

                except Exception as e:
                    print(f"Error parsing movie in Cinema 21: {e}")
                    continue

        except Exception as e:
            print(f"Error fetching Cinema 21 showtimes: {e}")

        return movies
