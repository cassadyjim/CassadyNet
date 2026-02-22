# CassadyNet - Setup & Automation Guide

## Overview

CassadyNet is an automated AI news aggregation system that:
1. Fetches stories from 35+ RSS feeds
2. Scores stories using Claude API
3. Generates a Drudge-style HTML homepage
4. Uploads to your One.com hosting via SFTP

## Directory Structure

```
ai_news_aggregator/
├── data/
│   └── stories.db          # SQLite database
├── feeds/
│   └── sources.json        # RSS feed configuration
├── logs/                   # Log files
├── output/                 # Generated HTML files
├── scripts/
│   ├── fetch_feeds.py      # RSS fetcher
│   ├── score_stories.py    # Claude API scorer
│   ├── generate_homepage.py # Manual HTML generator
│   ├── upload_sftp.py      # SFTP uploader
│   ├── publish.py          # Master orchestration script
│   ├── homepage_template.html
│   └── db_tools.py         # Database utilities
└── requirements.txt
```

## Initial Setup

### 1. Install Dependencies

```bash
cd ai_news_aggregator
pip3 install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file or export these variables:

```bash
# Claude API (get from console.anthropic.com)
export ANTHROPIC_API_KEY="sk-ant-xxxxx"

# One.com SFTP (get from One.com Control Panel → SSH & SFTP)
export SFTP_HOST="ssh.cassadynet.com"      # Check your control panel
export SFTP_PORT="22"
export SFTP_USERNAME="cassadynet.com"       # Usually your domain
export SFTP_PASSWORD="your_sftp_password"
export SFTP_REMOTE_DIR="/"                  # Usually root for One.com
```

### 3. Get Your One.com SFTP Credentials

1. Log in to One.com Control Panel
2. Go to Advanced Settings → SSH & SFTP
3. Enable SSH & SFTP access
4. Click "Send" to get a password reset email
5. Set your SFTP password
6. Note your connection details (host, port, username)

### 4. Test Each Component

```bash
# Test RSS fetching
python3 scripts/fetch_feeds.py

# Test SFTP connection
python3 scripts/upload_sftp.py --test

# Test scoring (requires ANTHROPIC_API_KEY)
python3 scripts/score_stories.py --dry-run --limit 5

# Test full pipeline locally (no upload)
python3 scripts/publish.py --local-only
```

## Running the Pipeline

### Manual Run

```bash
# Full pipeline: fetch → score → generate → upload
python3 scripts/publish.py

# Skip certain steps
python3 scripts/publish.py --skip-fetch      # Don't fetch new stories
python3 scripts/publish.py --skip-score      # Don't call Claude API
python3 scripts/publish.py --skip-upload     # Don't upload to server
python3 scripts/publish.py --local-only      # Just regenerate HTML
```

### Automated Hourly Updates (Mac)

#### Option A: Using cron

1. Open Terminal and edit crontab:
```bash
crontab -e
```

2. Add this line (adjust paths):
```cron
0 * * * * cd /Users/yourname/ai_news_aggregator && /usr/local/bin/python3 scripts/publish.py >> logs/publish.log 2>&1
```

3. Make sure environment variables are available. Create a wrapper script:

```bash
#!/bin/bash
# save as: run_publish.sh

export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export SFTP_HOST="ssh.cassadynet.com"
export SFTP_USERNAME="cassadynet.com"
export SFTP_PASSWORD="your_password"

cd /Users/yourname/ai_news_aggregator
/usr/local/bin/python3 scripts/publish.py >> logs/publish.log 2>&1
```

Then in crontab:
```cron
0 * * * * /Users/yourname/ai_news_aggregator/run_publish.sh
```

#### Option B: Using launchd (Mac native, more reliable)

1. Create a plist file at `~/Library/LaunchAgents/com.cassadynet.publish.plist`:

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
        <string>/Users/yourname/ai_news_aggregator/scripts/publish.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/yourname/ai_news_aggregator</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>ANTHROPIC_API_KEY</key>
        <string>sk-ant-xxxxx</string>
        <key>SFTP_HOST</key>
        <string>ssh.cassadynet.com</string>
        <key>SFTP_USERNAME</key>
        <string>cassadynet.com</string>
        <key>SFTP_PASSWORD</key>
        <string>your_password</string>
    </dict>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>/Users/yourname/ai_news_aggregator/logs/publish.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/yourname/ai_news_aggregator/logs/publish_error.log</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

2. Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.cassadynet.publish.plist
```

3. To stop:
```bash
launchctl unload ~/Library/LaunchAgents/com.cassadynet.publish.plist
```

## Cost Estimate

### Claude API Costs

- Model: Claude 3.5 Sonnet
- ~50 stories scored per hour = ~2,000 input tokens + ~1,500 output tokens
- Per run: ~$0.01
- Per day (24 runs): ~$0.25
- Per month: ~$7.50

### One.com Hosting

- Basic hosting: ~$3-5/month (static HTML only)

**Total monthly cost: ~$10-12**

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
Make sure you've exported the environment variable or added it to your wrapper script.

### "SFTP connection failed"
1. Check that SFTP is enabled in One.com Control Panel
2. Verify your credentials
3. Try connecting with FileZilla first to test

### "Not enough scored stories"
The pipeline needs at least 10 scored stories. Wait for more feeds to be fetched or lower the score threshold.

### Stories not appearing
Check the database:
```bash
python3 scripts/db_tools.py stats
python3 scripts/db_tools.py recent -n 20
```

## Manual Operations

### View database stats
```bash
python3 scripts/db_tools.py stats
```

### Search stories
```bash
python3 scripts/db_tools.py search "OpenAI"
```

### Export stories to JSON
```bash
python3 scripts/db_tools.py export --hours 24 -o stories.json
```

### Clean old stories
```bash
python3 scripts/db_tools.py cleanup --days 14
```

## Adding New RSS Feeds

Edit `feeds/sources.json`:

```json
{
  "name": "New Feed Name",
  "url": "https://example.com/feed.xml",
  "category": "tech_news"
}
```

Categories: `ai_labs`, `tech_news`, `research`, `international`, `social`, `funding`, `robotics`, `business`
