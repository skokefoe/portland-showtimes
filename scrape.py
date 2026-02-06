#!/usr/bin/env python3
"""Main scraper orchestration script."""
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict

from scrapers import SCRAPER_MAP


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

        # Group showtimes by date (for now, assume all are for "today")
        # In a real implementation, we'd parse dates from the scrapers
        date_str = start_date.strftime('%Y-%m-%d')
        theater_id = movie['theater_id']

        for showtime in movie['showtimes']:
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


def main():
    """Run all theater scrapers and aggregate results."""
    print("🎬 Portland Indie Showtimes Scraper")
    print("=" * 50)

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

    # Run scrapers
    all_movies = []
    successful_scrapers = 0
    failed_scrapers = []

    for theater in theaters:
        theater_id = theater['id']
        theater_name = theater['name']

        print(f"🎭 Scraping {theater_name}...")

        try:
            # Get scraper class
            scraper_class = SCRAPER_MAP.get(theater_id)
            if not scraper_class:
                print(f"   ⚠️  No scraper found for {theater_id}")
                failed_scrapers.append(theater_name)
                continue

            # Initialize and run scraper
            scraper = scraper_class(theater, tmdb_api_key)
            movies = scraper.fetch_showtimes(start_date, num_days)

            if movies:
                all_movies.extend(movies)
                successful_scrapers += 1
                print(f"   ✓ Found {len(movies)} movies")
            else:
                print(f"   ⚠️  No movies found")
                failed_scrapers.append(theater_name)

        except Exception as e:
            print(f"   ✗ Error: {e}")
            failed_scrapers.append(theater_name)

        print()

    # Aggregate and save
    print("=" * 50)
    print(f"✓ Successfully scraped {successful_scrapers}/{len(theaters)} theaters")

    if failed_scrapers:
        print(f"⚠️  Failed: {', '.join(failed_scrapers)}")

    print(f"📊 Total movies found: {len(all_movies)}")
    print()

    if all_movies:
        print("Aggregating showtimes...")
        aggregated_data = aggregate_showtimes(all_movies, start_date, num_days)

        print(f"✓ Aggregated into {len(aggregated_data['movies'])} unique titles")
        print()

        print("Saving data...")
        save_data(aggregated_data, theaters)
        print()

        print("✅ Done! Site data updated.")
    else:
        print("❌ No movies found. Check scraper implementations.")
        sys.exit(1)


if __name__ == '__main__':
    main()
