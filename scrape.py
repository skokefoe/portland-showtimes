#!/usr/bin/env python3
"""Main scraper orchestration script.

Uses SerpAPI to fetch Google's showtime data for each Portland theater.
This approach is more reliable than scraping individual theater websites,
which have different formats, may block scrapers, and can change anytime.
"""
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict
from zoneinfo import ZoneInfo

from scrapers.serpapi_scraper import SerpAPIScraper


def load_config() -> Dict[str, Any]:
    """Load project configuration."""
    config_path = 'config.json'
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {'enabled': True}


def load_theaters_config() -> List[Dict[str, Any]]:
    """Load theater configuration from JSON file."""
    with open('theaters.json', 'r') as f:
        data = json.load(f)
    return data['theaters']


def aggregate_showtimes(all_movies: List[Dict[str, Any]], start_date: datetime, num_days: int = 7) -> Dict[str, Any]:
    """Aggregate movie showtimes by title and date."""
    movies_by_title = defaultdict(lambda: {
        'title': '',
        'description': '',
        'poster': None,
        'letterboxd_url': '',
        'tmdb_id': None,
        'showtimes_by_date': defaultdict(lambda: defaultdict(list))
    })

    for movie in all_movies:
        title_key = movie['title'].lower()
        movie_data = movies_by_title[title_key]

        # Use first occurrence for metadata, but prefer entries with TMDB data
        if not movie_data['title'] or (not movie_data['tmdb_id'] and movie.get('tmdb_id')):
            movie_data['title'] = movie['title']
            movie_data['description'] = movie.get('description', '')
            movie_data['poster'] = movie.get('poster')
            movie_data['letterboxd_url'] = movie.get('letterboxd_url', '')
            movie_data['tmdb_id'] = movie.get('tmdb_id')

        theater_id = movie['theater_id']

        for showtime in movie.get('showtimes', []):
            date_str = showtime.get('date', start_date.strftime('%Y-%m-%d'))
            entry = {'time': showtime['time'], 'url': showtime.get('url', '')}
            fmt = showtime.get('format')
            if fmt and fmt != 'Standard':
                entry['format'] = fmt
            # Avoid duplicate time entries for the same theater/date
            existing_times = [e['time'] for e in movie_data['showtimes_by_date'][date_str][theater_id]]
            if entry['time'] not in existing_times:
                movie_data['showtimes_by_date'][date_str][theater_id].append(entry)

    aggregated_movies = []
    for movie_data in movies_by_title.values():
        showtimes = {}
        for date, theaters in movie_data['showtimes_by_date'].items():
            showtimes[date] = dict(theaters)

        aggregated_movies.append({
            'title': movie_data['title'],
            'description': movie_data['description'],
            'poster': movie_data['poster'],
            'letterboxd_url': movie_data['letterboxd_url'],
            'tmdb_id': movie_data['tmdb_id'],
            'showtimes': showtimes,
        })

    aggregated_movies.sort(key=lambda x: x['title'])

    return {
        'generated_at': datetime.now().isoformat(),
        'start_date': start_date.strftime('%Y-%m-%d'),
        'num_days': num_days,
        'movies': aggregated_movies,
    }


def save_data(data: Dict[str, Any], theaters: List[Dict[str, Any]]):
    """Save aggregated data to JSON files."""
    output_dir = 'docs/data'
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, 'showtimes.json')
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved showtimes to {output_file}")

    theaters_file = os.path.join(output_dir, 'theaters.json')
    with open(theaters_file, 'w') as f:
        json.dump({'theaters': theaters}, f, indent=2)
    print(f"Saved theaters metadata to {theaters_file}")


def main():
    """Run SerpAPI-based scrapers for all theaters."""
    print("Portland Indie Showtimes Scraper")
    print("=" * 50)

    config = load_config()
    if not config.get('enabled', True):
        print("Scraping is PAUSED (config.json: enabled = false)")
        if '--force' not in sys.argv:
            sys.exit(0)
        print("--force flag detected, running anyway...")

    theaters = load_theaters_config()
    tmdb_api_key = os.getenv('TMDB_API_KEY')
    serpapi_key = os.getenv('SERPAPI_KEY')

    if not serpapi_key:
        print("ERROR: SERPAPI_KEY not set.")
        print("  Get your free API key at: https://serpapi.com")
        print("  Then set it as a repository secret named SERPAPI_KEY")
        sys.exit(1)

    if not tmdb_api_key:
        print("Warning: TMDB_API_KEY not set. Posters and metadata will be limited.")
        print()

    # Use Pacific time since all theaters are in Portland
    pacific = ZoneInfo('America/Los_Angeles')
    start_date = datetime.now(pacific)
    num_days = 7

    print(f"Date (Pacific): {start_date.strftime('%Y-%m-%d %I:%M %p %Z')}")
    print(f"Theaters: {len(theaters)}")
    print(f"Data source: SerpAPI (Google Showtimes)")
    print()

    all_movies = []
    succeeded = 0
    failed_theaters = []

    for theater in theaters:
        print(f"  {theater['name']}...")
        scraper = SerpAPIScraper(theater, tmdb_api_key, serpapi_key)
        try:
            movies = scraper.fetch_showtimes(start_date, num_days)
            if movies:
                all_movies.extend(movies)
                print(f"   Found {len(movies)} movies")
                succeeded += 1
            else:
                print(f"   No showtimes found")
                failed_theaters.append(theater['name'])
        except Exception as e:
            print(f"   Error: {e}")
            failed_theaters.append(theater['name'])
        print()

    print("=" * 50)
    print(f"Data from {succeeded}/{len(theaters)} theaters")
    if failed_theaters:
        print(f"No data: {', '.join(failed_theaters)}")
    print(f"Total movies found: {len(all_movies)}")
    print()

    print("Aggregating showtimes...")
    aggregated = aggregate_showtimes(all_movies, start_date, num_days)
    print(f"Aggregated into {len(aggregated['movies'])} unique titles")
    print()

    print("Saving data...")
    save_data(aggregated, theaters)
    print()

    if all_movies:
        print("Done! Site data updated.")
    else:
        print("No movies found. Empty data saved so site can still load.")


if __name__ == '__main__':
    main()
