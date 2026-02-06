"""Hollywood Theatre scraper."""
from datetime import datetime
from typing import List, Dict, Any
from playwright.sync_api import sync_playwright
from .base_scraper import BaseScraper


class HollywoodScraper(BaseScraper):
    """Scraper for Hollywood Theatre (using Playwright for JS rendering)."""

    def fetch_showtimes(self, start_date: datetime, num_days: int = 7) -> List[Dict[str, Any]]:
        """Fetch showtimes from Hollywood Theatre."""
        movies = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(self.theater_url, timeout=30000)

                # Wait for content to load
                page.wait_for_load_state('networkidle')

                # Extract movie data from the page
                # This will need to be adjusted based on actual HTML structure
                movie_elements = page.query_selector_all('[class*="movie"], [class*="film"], [class*="show"]')

                for element in movie_elements:
                    try:
                        # Extract title
                        title_elem = element.query_selector('h1, h2, h3, h4')
                        if not title_elem:
                            continue

                        title = title_elem.inner_text().strip()

                        # Extract description
                        desc_elem = element.query_selector('[class*="description"], [class*="synopsis"], p')
                        description = desc_elem.inner_text().strip() if desc_elem else ''

                        # Extract link
                        link_elem = element.query_selector('a')
                        movie_url = link_elem.get_attribute('href') if link_elem else self.theater_url
                        if movie_url and not movie_url.startswith('http'):
                            movie_url = f"{self.theater_url.rstrip('/')}/{movie_url.lstrip('/')}"

                        # Extract showtimes
                        time_elements = element.query_selector_all('[class*="time"], time')
                        showtimes = []

                        for time_elem in time_elements:
                            time_text = time_elem.inner_text().strip()
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
                        print(f"Error parsing movie in Hollywood Theatre: {e}")
                        continue

                browser.close()

        except Exception as e:
            print(f"Error fetching Hollywood Theatre showtimes: {e}")

        return movies
