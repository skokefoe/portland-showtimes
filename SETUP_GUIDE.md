# Setup Guide: Getting Your Site Live

This guide will walk you through the final steps to get your Portland indie showtimes site live on GitHub Pages.

## Step 1: Get a TMDB API Key (5 minutes)

TMDB (The Movie Database) provides free API access for movie posters and metadata.

1. **Create an account** at [themoviedb.org](https://www.themoviedb.org/signup)

2. **Go to API settings**:
   - Click your profile icon (top right)
   - Settings → API
   - Or visit: https://www.themoviedb.org/settings/api

3. **Request an API key**:
   - Click "Request an API Key"
   - Select "Developer"
   - Fill out the form (you can use personal project info)
   - Accept terms

4. **Copy your API key** (v3 auth):
   - It looks like: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`
   - Save this - you'll need it in Step 3

## Step 2: Create GitHub Repository (3 minutes)

1. **Go to GitHub**: [github.com/new](https://github.com/new)

2. **Create repository**:
   - Repository name: `portland-showtimes` (or your preferred name)
   - Description: "Movie showtimes aggregator for Portland indie theaters"
   - **Public** (required for free GitHub Pages)
   - Don't initialize with README (we already have one)

3. **Copy the repository URL**:
   - Should look like: `https://github.com/YOUR-USERNAME/portland-showtimes.git`

## Step 3: Push Your Code to GitHub (2 minutes)

Open Terminal and run these commands:

```bash
# Navigate to your project
cd ~/portland-showtimes

# Add GitHub as remote (replace YOUR-USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR-USERNAME/portland-showtimes.git

# Push your code
git branch -M main
git push -u origin main
```

## Step 4: Add TMDB API Key Secret (2 minutes)

1. **Go to your repository** on GitHub

2. **Navigate to Settings → Secrets and variables → Actions**

3. **Click "New repository secret"**:
   - Name: `TMDB_API_KEY`
   - Value: [paste your TMDB API key from Step 1]
   - Click "Add secret"

## Step 5: Enable GitHub Pages (2 minutes)

1. **In your repository, go to Settings → Pages**

2. **Configure source**:
   - Source: "Deploy from a branch"
   - Branch: `main`
   - Folder: `/docs`
   - Click "Save"

3. **Wait a minute**, then refresh the page
   - You'll see: "Your site is live at `https://YOUR-USERNAME.github.io/portland-showtimes/`"

## Step 6: Run Your First Scrape (1 minute)

1. **Go to the Actions tab** in your repository

2. **Click "Update Showtimes" workflow** (left sidebar)

3. **Click "Run workflow"** button (right side):
   - Branch: main
   - Click green "Run workflow"

4. **Watch it run** (takes 2-3 minutes):
   - Click on the running workflow to see progress
   - Green checkmark = success!

5. **Visit your site**:
   - `https://YOUR-USERNAME.github.io/portland-showtimes/`
   - 🎉 Your showtimes aggregator is live!

## Step 7: Verify Automatic Updates

The site will now automatically update daily at 2 AM PST. To verify:

1. **Check the Actions tab** tomorrow morning
2. You should see a new "Update Showtimes" run
3. The site will reflect the latest showtimes

---

## Troubleshooting

### "Site not found" or 404 error

- Wait 5 minutes after enabling Pages (initial build takes time)
- Verify Pages is set to `/docs` folder (not root)
- Check that your repository is public

### GitHub Actions workflow fails

**Check TMDB_API_KEY:**
- Settings → Secrets → verify it's named exactly `TMDB_API_KEY`
- No spaces, no quotes around the key value

**Check the error in Actions:**
- Click the failed workflow
- Click the red X step to see error details
- Common issues:
  - TMDB key not set (see above)
  - Network timeout (re-run workflow)
  - Scraper issue (theater website changed - this is normal)

### No movies showing on the site

- The first run generates initial data
- If scrapers fail, the site shows "No showtimes found"
- Check Actions logs to see which scrapers succeeded
- Some theaters may require scraper adjustments (see below)

### Adjusting Scrapers

Theater websites change frequently. To fix a broken scraper:

1. **Test locally**:
   ```bash
   cd ~/portland-showtimes
   export TMDB_API_KEY="your-key"
   python scrape.py
   ```

2. **Check error messages** - they show which theater failed

3. **Update the scraper**:
   - Open `scrapers/[theater].py`
   - Adjust CSS selectors or HTML parsing
   - Test again locally

4. **Push fixes**:
   ```bash
   git add scrapers/
   git commit -m "Fix [theater] scraper"
   git push
   ```

---

## Next Steps

### Customize the Look

Edit `docs/index.html` to change:
- Colors (search for `:root` CSS variables)
- Fonts
- Layout

### Add More Theaters

See README.md section "Adding More Theaters"

### Change Update Schedule

Edit `.github/workflows/update-showtimes.yml`:
```yaml
schedule:
  - cron: '0 14 * * *'  # 6 AM PST instead of 2 AM
```

### Share Your Site

- Share the URL with friends
- Add to your browser bookmarks
- Set as your new tab page!

---

## Support

If you run into issues:

1. Check the [README.md](README.md) troubleshooting section
2. Review Actions logs for specific errors
3. Test scrapers locally to identify problems

**Your Portland indie cinema experience is now just a click away! 🎬🍿**
