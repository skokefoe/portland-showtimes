#!/usr/bin/env python3
"""Main scraper orchestration script."""
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict

from scrapers import SCRAPER_MAP, FALLBACK_SCRAPER


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
    """
    Aggregate movie showtimes by title and date.

    Args:
        all_movies: List of all movies from all theaters
        start_date: Start date for aggregation
        num_days: Number of days to include

    Returns:
        Aggregated data structure
    """
    # Group movies by title (case-insensitive)
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

        # Use first occurrence for metadata
        if not movie_data['title']:
            movie_data['title'] = movie['title']
            movie_data['description'] = movie['description']
            movie_data['poster'] = movie['poster']
            movie_data['letterboxd_url'] = movie['letterboxd_url']
            movie_data['tmdb_id'] = movie['tmdb_id']

        theater_id = movie['theater_id']

        for showtime in movie['showtimes']:
            # Use per-showtime date if available, otherwise default to today
            date_str = showtime.get('date', start_date.strftime('%Y-%m-%d'))
            movie_data['showtimes_by_date'][date_str][theater_id].append({
                'time': showtime['time'],
                'url': showtime['url']
            })

    # Convert to final format
    aggregated_movies = []
    for movie_data in movies_by_title.values():
        # Convert nested defaultdicts to regular dicts
        showtimes = {}
        for date, theaters in movie_data['showtimes_by_date'].items():
            showtimes[date] = dict(theaters)

        aggregated_movies.append({
            'title': movie_data['title'],
            'description': movie_data['description'],
            'poster': movie_data['poster'],
            'letterboxd_url': movie_data['letterboxd_url'],
            'tmdb_id': movie_data['tmdb_id'],
            'showtimes': showtimes
        })

    # Sort by title
    aggregated_movies.sort(key=lambda x: x['title'])

    return {
        'generated_at': datetime.now().isoformat(),
        'start_date': start_date.strftime('%Y-%m-%d'),
        'num_days': num_days,
        'movies': aggregated_movies
    }


def save_data(data: Dict[str, Any], theaters: List[Dict[str, Any]]):
    """Save aggregated data to JSON file."""
    output_dir = 'docs/data'
    os.makedirs(output_dir, exist_ok=True)

    # Save main showtimes data
    output_file = os.path.join(output_dir, 'showtimes.json')
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✓ Saved showtimes to {output_file}")

    # Save theaters metadata
    theaters_file = os.path.join(output_dir, 'theaters.json')
    with open(theaters_file, 'w') as f:
        json.dump({'theaters': theaters}, f, indent=2)

    print(f"✓ Saved theaters metadata to {theaters_file}")


def scrape_theater(theater: Dict[str, Any], start_date: datetime, num_days: int,
                   tmdb_api_key: str) -> List[Dict[str, Any]]:
    """
    Scrape a single theater, falling back to Google if the primary scraper fails.

    Args:
        theater: Theater configuration dict
        start_date: Start date for showtimes
        num_days: Number of days to fetch
        tmdb_api_key: TMDB API key

    Returns:
        List of movie dicts, or empty list if both primary and fallback fail
    """
    theater_id = theater['id']
    theater_name = theater['name']

    # --- Try primary scraper ---
    scraper_class = SCRAPER_MAP.get(theater_id)
    if scraper_class:
        try:
            scraper = scraper_class(theater, tmdb_api_key)
            movies = scraper.fetch_showtimes(start_date, num_days)
            if movies:
                print(f"   ✓ Found {len(movies)} movies (primary)")
                return movies
            else:
                print(f"   ⚠️  Primary scraper returned no results")
        except Exception as e:
            print(f"   ✗ Primary scraper failed: {e}")
    else:
        print(f"   ⚠️  No primary scraper for {theater_id}")

    # --- Try fallback (Google search) ---
    print(f"   ↻ Trying fallback (Google search)...")
    try:
        fallback = FALLBACK_SCRAPER(theater, tmdb_api_key)
        movies = fallback.fetch_showtimes(start_date, num_days)
        if movies:
            print(f"   ✓ Found {len(movies)} movies (fallback)")
            return movies
        else:
            print(f"   ⚠️  Fallback returned no results")
    except Exception as e:
        print(f"   ✗ Fallback failed: {e}")

    return []


def main():
    """Run all theater scrapers and aggregate results."""
    print("🎬 Portland Indie Showtimes Scraper")
    print("=" * 50)

    # Check if the project is enabled
    config = load_config()
    if not config.get('enabled', True):
        print("⏸️  Scraping is PAUSED (config.json: enabled = false)")
        print("   To resume, set 'enabled' to true in config.json")
        print("   or run: python scrape.py --force")
        if '--force' not in sys.argv:
            sys.exit(0)
        print("   --force flag detected, running anyway...")
        print()

    # Load configuration
    theaters = load_theaters_config()
    tmdb_api_key = os.getenv('TMDB_API_KEY')

    if not tmdb_api_key:
        print("⚠️  Warning: TMDB_API_KEY not set. Posters and metadata will be limited.")
        print("   Get your free API key at: https://www.themoviedb.org/settings/api")
        print()

    # Set date range
    start_date = datetime.now()
    num_days = 7

    print(f"Scraping showtimes from {start_date.strftime('%Y-%m-%d')}")
    print(f"Number of days: {num_days}")
    print()

    # Run scrapers (primary + fallback for each theater)
    all_movies = []
    results = {'primary': 0, 'fallback': 0, 'failed': []}

    for theater in theaters:
        theater_name = theater['name']
        print(f"🎭 Scraping {theater_name}...")

        movies = scrape_theater(theater, start_date, num_days, tmdb_api_key)

        if movies:
            all_movies.extend(movies)
            # Track which source succeeded (heuristic: if primary has a scraper and worked)
            scraper_class = SCRAPER_MAP.get(theater['id'])
            if scraper_class:
                results['primary'] += 1
            else:
                results['fallback'] += 1
        else:
            results['failed'].append(theater_name)

        print()

    # Summary
    print("=" * 50)
    total_ok = results['primary'] + results['fallback']
    print(f"✓ Data from {total_ok}/{len(theaters)} theaters")
    if results['fallback'] > 0:
        print(f"   ({results['primary']} primary, {results['fallback']} via fallback)")
    if results['failed']:
        print(f"⚠️  No data: {', '.join(results['failed'])}")
    print(f"📊 Total movies found: {len(all_movies)}")
    print()

    # Always aggregate and save (even if empty, so the frontend has valid JSON)
    print("Aggregating showtimes...")
    aggregated_data = aggregate_showtimes(all_movies, start_date, num_days)

    print(f"✓ Aggregated into {len(aggregated_data['movies'])} unique titles")
    print()

    print("Saving data...")
    save_data(aggregated_data, theaters)
    print()

    if all_movies:
        print("✅ Done! Site data updated.")
    else:
        print("⚠️  No movies found from any source. Empty data saved so site can load.")
        print("   Check scraper implementations or theater website changes.")


if __name__ == '__main__':
    main()
