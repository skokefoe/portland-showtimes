# 🎬 Portland Indie Showtimes

A beautiful, auto-updating website that aggregates movie showtimes from Portland's independent theaters. Never miss a screening at your favorite indie cinema again!

## Features

- 📅 **7-day calendar view** with clickable dates
- 🎭 **8 Portland indie theaters** including Hollywood Theatre, Cinema 21, and more
- 🎨 **Movie posters** from TMDB API
- 📖 **Letterboxd links** for every film
- 🔄 **Auto-updates daily** via GitHub Actions
- 📱 **Responsive design** works on all devices
- 🌙 **Dark mode** by default (easy on the eyes)

## Theaters Included

1. **Hollywood Theatre** - hollywoodtheatre.org
2. **Cinema 21** - cinema21.com
3. **The Cinemagic** - thecinemagictheater.com
4. **Bagdad Theater & Pub** - mcmenamins.com/bagdad-theater-pub
5. **Laurelhurst Theater** - laurelhursttheater.com
6. **Clinton Street Theater** - cstpdx.com
7. **Living Room Theaters** - pdx.livingroomtheaters.com
8. **Academy Theater** - academytheaterpdx.com

## Setup

### Prerequisites

- Python 3.11+
- [TMDB API Key](https://www.themoviedb.org/settings/api) (free)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR-USERNAME/portland-showtimes.git
   cd portland-showtimes
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Set TMDB API key**
   ```bash
   export TMDB_API_KEY="your-api-key-here"
   ```

4. **Run the scraper**
   ```bash
   python scrape.py
   ```

5. **View the site locally**
   ```bash
   # Open docs/index.html in your browser
   open docs/index.html
   ```

### GitHub Pages Deployment

1. **Create a new repository** on GitHub

2. **Add TMDB API key** as a repository secret:
   - Go to Settings → Secrets and variables → Actions
   - Add new secret: `TMDB_API_KEY`

3. **Enable GitHub Pages**:
   - Go to Settings → Pages
   - Source: Deploy from a branch
   - Branch: `main` → `/docs` folder
   - Save

4. **Push your code**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/portland-showtimes.git
   git push -u origin main
   ```

5. **Wait for the first run**:
   - Go to Actions tab
   - Run "Update Showtimes" workflow manually
   - Your site will be live at `https://YOUR-USERNAME.github.io/portland-showtimes/`

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GitHub Repository                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  │  GitHub Actions  │───▶│   JSON Data      │◀───│  GitHub Pages    │
│  │  (Daily Scraper) │    │   (docs/data/)   │    │  (Static Site)   │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘
└─────────────────────────────────────────────────────────────────────┘
```

### How It Works

1. **GitHub Actions** runs daily at 2 AM PST
2. **Python scrapers** fetch showtimes from each theater's website
3. **TMDB API** provides movie posters and metadata
4. **JSON data** is generated and committed to `/docs/data/`
5. **GitHub Pages** serves the updated static site

## Project Structure

```
portland-showtimes/
├── scrapers/               # Theater scrapers
│   ├── base_scraper.py    # Base class with common functionality
│   ├── cinema21.py        # Cinema 21 scraper
│   ├── hollywood.py       # Hollywood Theatre scraper
│   └── ...                # Other theater scrapers
├── docs/                   # GitHub Pages site
│   ├── index.html         # Main site (with CSS & JS)
│   ├── data/              # Generated JSON data
│   │   ├── showtimes.json # Aggregated showtimes
│   │   └── theaters.json  # Theater metadata
│   └── posters/           # Cached movie posters
├── .github/workflows/      # GitHub Actions
│   └── update-showtimes.yml
├── theaters.json          # Theater configuration
├── scrape.py              # Main orchestration script
└── requirements.txt       # Python dependencies
```

## Customization

### Adding More Theaters

1. Add theater config to `theaters.json`:
   ```json
   {
     "id": "new-theater",
     "name": "New Theater",
     "url": "https://newtheater.com",
     "address": "123 Main St, Portland, OR",
     "scraper_type": "beautifulsoup"
   }
   ```

2. Create scraper in `scrapers/new_theater.py`:
   ```python
   from .base_scraper import BaseScraper

   class NewTheaterScraper(BaseScraper):
       def fetch_showtimes(self, start_date, num_days=7):
           # Implement scraping logic
           pass
   ```

3. Register in `scrapers/__init__.py`:
   ```python
   SCRAPER_MAP = {
       # ...
       'new-theater': NewTheaterScraper,
   }
   ```

### Adjusting Update Schedule

Edit `.github/workflows/update-showtimes.yml`:

```yaml
schedule:
  # Run at 6 AM PST (2 PM UTC) instead
  - cron: '0 14 * * *'
```

## Troubleshooting

### Scrapers Not Finding Movies

Theater websites change frequently. Check the scraper for that theater and update the CSS selectors or HTML parsing logic in `scrapers/[theater].py`.

### TMDB API Rate Limits

The free tier allows 40 requests/second. If you hit limits, the scraper will continue without metadata.

### GitHub Actions Failures

1. Check the Actions tab for error logs
2. Verify TMDB_API_KEY secret is set
3. Test locally with `python scrape.py`

## License

MIT License - feel free to fork and customize for your city!

## Credits

- Built with [Craft Agent](https://agents.craft.do)
- Movie data from [TMDB](https://www.themoviedb.org/)
- Letterboxd integration via their URL structure
- Inspired by Poor Stuart's Portland showtimes aggregator

---

**Enjoy your indie cinema experience! 🍿**
