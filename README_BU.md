# AI News Aggregator

A Drudge Report-style AI news aggregation system designed for **pure speed** and **global breadth**.

## Quick Start

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Fetch stories from all feeds
python3 scripts/fetch_feeds.py

# 3. View stats and recent stories
python3 scripts/db_tools.py stats
python3 scripts/db_tools.py recent -n 20
```

> **Note:** On Mac, use `pip3` and `python3`. On Windows/Linux, `pip` and `python` usually work.

## Project Structure

```
ai_news_aggregator/
├── feeds/
│   └── sources.json      # RSS feed configuration (35+ sources)
├── scripts/
│   ├── fetch_feeds.py    # Main feed aggregator (async, parallel fetching)
│   └── db_tools.py       # Database viewer and utilities
├── data/
│   └── stories.db        # SQLite database (created on first run)
├── requirements.txt
└── README.md
```

## Scripts

### fetch_feeds.py

The main workhorse. Fetches all configured RSS feeds in parallel using async I/O.

```bash
# Run once
python3 scripts/fetch_feeds.py

# Run via cron every 15 minutes (Mac)
*/15 * * * * cd /path/to/ai_news_aggregator && python3 scripts/fetch_feeds.py >> logs/fetch.log 2>&1
```

**Features:**
- Async parallel fetching (10 concurrent connections)
- Automatic deduplication by URL hash
- Skips stories older than 7 days
- Tracks feed health (success/error counts)
- Cleans HTML from summaries

### db_tools.py

Database utilities for viewing and managing stories.

```bash
# Show statistics
python3 scripts/db_tools.py stats

# Recent stories
python3 scripts/db_tools.py recent -n 30
python3 scripts/db_tools.py recent -c research        # Filter by category
python3 scripts/db_tools.py recent -s "TechCrunch"   # Filter by source

# Search stories
python3 scripts/db_tools.py search "OpenAI"
python3 scripts/db_tools.py search "GPT-5" -n 50

# Export to JSON
python3 scripts/db_tools.py export --hours 24 -o daily_stories.json

# Cleanup old stories
python3 scripts/db_tools.py cleanup --days 30 --dry-run
python3 scripts/db_tools.py cleanup --days 30
```

## Feed Configuration

Edit `feeds/sources.json` to add/remove/modify feeds:

```json
{
  "name": "TechCrunch AI",
  "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
  "category": "tech_news",
  "tier": 1,
  "enabled": true
}
```

**Categories:**
- `ai_labs` - Official AI company blogs (OpenAI, Anthropic, Google, etc.)
- `tech_news` - Tech publications (TechCrunch, Verge, Wired, etc.)
- `research` - Academic sources (arXiv, university labs)
- `international` - Global sources (Nikkei, SCMP, etc.)
- `social` - Community sources (Reddit, Hacker News)
- `funding` - VC and startup news
- `newsletter` - AI newsletters
- `robotics` - Robotics coverage

**Tiers:**
- `1` - Primary sources (check multiple times daily)
- `2` - Secondary sources (check daily)

## Database Schema

```sql
stories (
    id TEXT PRIMARY KEY,           -- MD5 hash of URL
    title TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,          -- Feed name
    category TEXT,
    published TIMESTAMP,           -- Original publish date
    summary TEXT,                  -- Cleaned excerpt (max 1000 chars)
    fetched_at TIMESTAMP,          -- When we fetched it
    tier INTEGER DEFAULT 1,
    score REAL DEFAULT 0,          -- For AI scoring (future)
    status TEXT DEFAULT 'new',     -- new/reviewed/published/rejected
    headline TEXT                  -- Drudge-style headline (future)
)

feed_status (
    feed_name TEXT PRIMARY KEY,
    last_fetch TIMESTAMP,
    last_success TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    last_error TEXT
)
```

## Recommended Cron Schedule (Mac)

```bash
# Fetch feeds every 15 minutes
*/15 * * * * cd /path/to/ai_news_aggregator && python3 scripts/fetch_feeds.py >> logs/fetch.log 2>&1

# Cleanup stories older than 14 days (run weekly)
0 3 * * 0 cd /path/to/ai_news_aggregator && python3 scripts/db_tools.py cleanup --days 14

# Export daily digest (optional)
0 6 * * * cd /path/to/ai_news_aggregator && python3 scripts/db_tools.py export --hours 24 -o exports/$(date +\%Y\%m\%d).json
```

> **Mac Tip:** Use `crontab -e` to edit your cron jobs. Make sure to use the full path to python3 if needed (run `which python3` to find it).

## Next Steps

1. **Add more feeds** - Edit `sources.json` to add more sources from the master list
2. **Build evaluation prompt** - Score stories for newsworthiness
3. **Build the site** - Drudge-style HTML generator
4. **Add headline rewriting** - Generate punchy headlines

## Volume Expectations

With 35 feeds at current configuration:
- **Daily volume:** 200-500 stories (varies by news cycle)
- **Target curation:** 20 stories/day
- **Database growth:** ~15,000 stories/month before cleanup

## Troubleshooting

**Feed returning 0 stories?**
- Check `db_tools.py stats` for feed errors
- Some sites block automated requests - may need custom User-Agent

**Duplicate stories?**
- Dedup is by URL - same story from different sources will both appear
- Consider adding title similarity detection

**Memory issues with large database?**
- Run cleanup more frequently
- Consider archiving old stories to separate DB
