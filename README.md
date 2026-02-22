# CassadyNet - AI News Aggregator

A fully-automated, Drudge Report-style AI news aggregation platform designed for **pure speed** and **global breadth**. Aggregates news from 105+ RSS feeds, scores stories using Claude AI, and generates a static HTML site.

## Features

- **Automated Pipeline** - Fetches, scores, and publishes news hourly via cron/launchd
- **AI-Powered Curation** - Claude Sonnet scores stories on 5 criteria with bonuses for underreported regions
- **105+ RSS Sources** - Tech news, AI labs, research, international, business, and more
- **Async Feed Fetching** - Parallel I/O reduces fetch time from ~10 min to ~30 sec
- **Story Clustering** - Groups related stories into themed clusters with polls/summaries
- **Static HTML Output** - Fast, no server required, works with cheap shared hosting
- **Social Media Integration** - Optional posting to Twitter/X and Bluesky
- **Cost-Effective** - ~$10-12/month total (Claude API + hosting)

## Quick Start

```bash
# 1. Install dependencies
cd "Scripts/ai_news_aggregator 2"
pip3 install -r requirements.txt

# 2. Set up environment variables
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export SFTP_HOST="ssh.yoursite.com"
export SFTP_USERNAME="yoursite.com"
export SFTP_PASSWORD="your_password"

# 3. Test the pipeline locally
python3 scripts/publish.py --local-only

# 4. Run full pipeline (fetch -> score -> cluster -> generate -> upload)
python3 scripts/publish.py
```

## Project Structure

```
ai_news_aggregator/
├── feeds/
│   └── sources.json           # 105 RSS feed configurations
├── scripts/
│   ├── publish.py             # Master orchestration pipeline
│   ├── fetch_feeds.py         # Async RSS feed fetcher
│   ├── score_stories.py       # Claude API story scorer
│   ├── cluster_stories.py     # Story clustering engine
│   ├── generate_analysis.py   # Generates polls/summaries for clusters
│   ├── generate_homepage.py   # HTML generation (Drudge-style)
│   ├── generate_rss.py        # RSS feed generator
│   ├── generate_sitemap.py    # Sitemap generator
│   ├── generate_polls_page.py # Previous polls archive page
│   ├── upload_sftp.py         # SFTP deployment to hosting
│   ├── db_tools.py            # Database CLI utilities
│   ├── twitter_post.py        # Twitter/X integration
│   ├── bluesky_post.py        # Bluesky integration
│   ├── social_posts.py        # Social posting orchestrator
│   └── homepage_template*.html # HTML templates
├── data/
│   ├── stories.db             # SQLite database
│   ├── story_clusters.json    # Current story clusters
│   ├── analysis_index.json    # Index of generated analyses
│   └── active_polls.json      # Currently active polls
├── output/                    # Generated static site files
│   ├── index.html             # Main homepage
│   ├── feed.xml               # RSS feed
│   ├── sitemap.xml            # Sitemap
│   ├── polls.html             # Previous polls page
│   ├── about.html             # About page
│   ├── privacy.html           # Privacy policy
│   ├── sources.html           # Feed sources list
│   └── analysis/              # Generated analysis pages
├── logs/                      # Pipeline execution logs
├── requirements.txt
├── README.md
└── SETUP.md                   # Detailed setup guide
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              EXTERNAL DATA SOURCES (105 RSS feeds)          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │   fetch_feeds.py (Async)     │
            │  • 10 concurrent connections │
            │  • 7-day story filter        │
            └──────────────────────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  stories.db (SQLite)         │
            └──────────────────────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │   score_stories.py (Claude)  │
            │  • 5-criteria scoring        │
            │  • Headline generation       │
            └──────────────────────────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │   cluster_stories.py         │
            │  • Groups related stories    │
            └──────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
       HTML Gen       RSS Gen       Analysis Gen
            │              │              │
            ▼              ▼              ▼
      index.html      feed.xml      /analysis/*.html
            │
            ▼
      upload_sftp.py -> One.com hosting -> cassadynet.com
```

## Main Components

### publish.py - Master Pipeline

The orchestrator that runs the entire pipeline:

```bash
# Full pipeline
python3 scripts/publish.py

# Pipeline options
python3 scripts/publish.py --skip-fetch      # Don't fetch new stories
python3 scripts/publish.py --skip-score      # Don't call Claude API
python3 scripts/publish.py --skip-cluster    # Don't cluster stories
python3 scripts/publish.py --skip-analysis   # Don't generate analysis
python3 scripts/publish.py --skip-upload     # Don't upload to server
python3 scripts/publish.py --local-only      # Just regenerate HTML locally
```

**Pipeline Steps:**
1. Fetch RSS feeds (parallel async)
2. Score stories with Claude API
3. Cluster related stories
4. Generate analysis/polls for clusters
5. Generate homepage HTML
6. Generate previous polls page
7. Generate RSS feed
8. Generate sitemap
9. Copy robots.txt
10. Upload to server via SFTP

### fetch_feeds.py - RSS Fetcher

Async parallel feed fetching with 10 concurrent connections.

```bash
python3 scripts/fetch_feeds.py
```

**Features:**
- Async I/O with aiohttp (10 concurrent)
- 7-day story cutoff (skips older content)
- URL-based deduplication (MD5 hash)
- HTML tag stripping from summaries
- Feed health tracking (success/error counts)
- Automatic database initialization

### score_stories.py - AI Scorer

Uses Claude Sonnet to evaluate story newsworthiness.

```bash
python3 scripts/score_stories.py --hours 24 --limit 50
python3 scripts/score_stories.py --dry-run --limit 5  # Test without DB update
```

**Scoring Criteria (1-10 each):**
1. **Breaking** - Is this fresh news?
2. **Impact** - How significant?
3. **Exclusivity** - Are we adding value?
4. **Credibility** - Can we trust this?
5. **Headline Potential** - Will this drive clicks?

**Bonuses/Penalties:**
- China/Asia AI news: +5
- EU/regulatory: +3
- First English coverage: +5
- Research papers (no news angle): cap at 25
- Opinion pieces: -5
- PR fluff: cap at 15

### db_tools.py - Database Utilities

CLI for database inspection and management.

```bash
# Statistics
python3 scripts/db_tools.py stats

# Recent stories
python3 scripts/db_tools.py recent -n 30
python3 scripts/db_tools.py recent -c research      # Filter by category
python3 scripts/db_tools.py recent -s "TechCrunch"  # Filter by source

# Search
python3 scripts/db_tools.py search "OpenAI"
python3 scripts/db_tools.py search "GPT-5" -n 50

# Export
python3 scripts/db_tools.py export --hours 24 -o stories.json

# Cleanup
python3 scripts/db_tools.py cleanup --days 14 --dry-run
python3 scripts/db_tools.py cleanup --days 14
```

### upload_sftp.py - Deployment

Uploads generated files to hosting via SFTP.

```bash
python3 scripts/upload_sftp.py              # Upload all site files
python3 scripts/upload_sftp.py --test       # Test connection only
python3 scripts/upload_sftp.py --analysis   # Upload only analysis files
python3 scripts/upload_sftp.py --file path  # Upload specific file
```

## Configuration

### Environment Variables

```bash
# Claude API (required)
export ANTHROPIC_API_KEY="sk-ant-xxxxx"

# SFTP for deployment (required for upload)
export SFTP_HOST="ssh.yoursite.com"
export SFTP_PORT="22"
export SFTP_USERNAME="yoursite.com"
export SFTP_PASSWORD="your_password"
export SFTP_REMOTE_DIR="/"

# Optional: Social media
export TWITTER_API_KEY="..."
export BLUESKY_HANDLE="..."
export BLUESKY_APP_PASSWORD="..."
```

### Feed Configuration

Edit `feeds/sources.json` to manage RSS sources:

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
| Category | Description |
|----------|-------------|
| `ai_labs` | Official AI company blogs (OpenAI, Anthropic, Google, etc.) |
| `tech_news` | Tech publications (TechCrunch, Verge, Wired, etc.) |
| `research` | Academic sources (arXiv, university labs) |
| `international` | Global sources (Nikkei, SCMP, etc.) |
| `social` | Community sources (Reddit, Hacker News) |
| `funding` | VC and startup news |
| `newsletter` | AI newsletters |
| `business` | Business/finance coverage |
| `robotics` | Robotics coverage |
| `ai_safety` | AI safety and alignment |
| `policy` | Policy and regulation |

**Tiers:**
- `1` - Primary sources (check multiple times daily)
- `2` - Secondary sources (check daily)

## Database Schema

### stories table

```sql
CREATE TABLE stories (
    id TEXT PRIMARY KEY,           -- MD5 hash of URL (16 chars)
    title TEXT NOT NULL,           -- Original article title
    url TEXT UNIQUE NOT NULL,      -- Source URL
    source TEXT NOT NULL,          -- Feed name
    category TEXT,                 -- Feed category
    published TIMESTAMP,           -- Original publication time
    summary TEXT,                  -- Cleaned excerpt (max 1000 chars)
    fetched_at TIMESTAMP,          -- When we fetched it
    tier INTEGER DEFAULT 1,        -- Feed tier
    score REAL DEFAULT 0,          -- AI-assigned score (0-50+)
    status TEXT DEFAULT 'new',     -- new/reviewed/published/rejected
    headline TEXT                  -- AI-generated Drudge-style headline
);
```

### feed_status table

```sql
CREATE TABLE feed_status (
    feed_name TEXT PRIMARY KEY,
    last_fetch TIMESTAMP,
    last_success TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    last_error TEXT
);
```

## Automation

### Option A: Using cron

```bash
# Edit crontab
crontab -e

# Add hourly job (adjust paths)
0 * * * * cd /path/to/ai_news_aggregator && /usr/local/bin/python3 scripts/publish.py >> logs/publish.log 2>&1
```

**Recommended:** Create a wrapper script (`run_publish.sh`) to handle environment variables:

```bash
#!/bin/bash
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export SFTP_HOST="ssh.yoursite.com"
export SFTP_USERNAME="yoursite.com"
export SFTP_PASSWORD="your_password"

cd /path/to/ai_news_aggregator
/usr/local/bin/python3 scripts/publish.py >> logs/publish.log 2>&1
```

### Option B: Using launchd (macOS)

Create `~/Library/LaunchAgents/com.cassadynet.publish.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cassadynet.publish</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/path/to/ai_news_aggregator/scripts/publish.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/ai_news_aggregator</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>ANTHROPIC_API_KEY</key>
        <string>sk-ant-xxxxx</string>
        <key>SFTP_HOST</key>
        <string>ssh.yoursite.com</string>
        <key>SFTP_USERNAME</key>
        <string>yoursite.com</string>
        <key>SFTP_PASSWORD</key>
        <string>your_password</string>
    </dict>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>/path/to/ai_news_aggregator/logs/publish.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/ai_news_aggregator/logs/publish_error.log</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

Load/unload:
```bash
launchctl load ~/Library/LaunchAgents/com.cassadynet.publish.plist
launchctl unload ~/Library/LaunchAgents/com.cassadynet.publish.plist
```

## Cost Estimate

| Component | Cost |
|-----------|------|
| Claude API | ~$7.50/month (50 stories/hour x 24 hours x $0.015/50) |
| One.com hosting | ~$3-5/month (static HTML) |
| **Total** | **~$10-12/month** |

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
Export the environment variable or add it to your wrapper script/launchd plist.

### "SFTP connection failed"
1. Verify SFTP is enabled in your hosting control panel
2. Test credentials with FileZilla or similar
3. Run `python3 scripts/upload_sftp.py --test`

### "Not enough scored stories"
The pipeline needs at least 10 scored stories (score >= 25). Wait for more feeds to be fetched or check feed health with `db_tools.py stats`.

### Feed returning 0 stories
- Check `python3 scripts/db_tools.py stats` for feed errors
- Some sites block automated requests - may need custom User-Agent
- Verify the RSS URL is still valid

### Stories not appearing on site
```bash
# Check database
python3 scripts/db_tools.py stats
python3 scripts/db_tools.py recent -n 20

# Check scores (need >= 25 to appear)
sqlite3 data/stories.db "SELECT title, score FROM stories ORDER BY fetched_at DESC LIMIT 10"
```

### Memory issues
- Run cleanup more frequently: `python3 scripts/db_tools.py cleanup --days 7`
- Consider archiving old stories

## Volume Expectations

With 105 feeds:
- **Daily volume:** 500-1000+ stories fetched
- **Target curation:** ~25 high-impact stories/day (score >= 25)
- **Database growth:** ~30,000 stories/month before cleanup

## Dependencies

```
feedparser>=6.0.0      # RSS parsing
aiohttp>=3.9.0         # Async HTTP
aiosqlite>=0.19.0      # Async SQLite (optional)
python-dateutil>=2.8.0 # Date parsing
anthropic>=0.40.0      # Claude API
paramiko>=3.4.0        # SFTP
tabulate>=0.9.0        # CLI tables
python-dotenv>=1.0.0   # .env file support
```

## License

Private project - CassadyNet
