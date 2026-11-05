# CassadyNet — Claude Code Project Guide

## What This Is
CassadyNet (cassadynet.com) is an AI news aggregator that automatically fetches RSS feeds, scores stories with Claude AI, clusters them by topic, generates analysis pages with polls, and publishes to One.com hosting via SFTP. The pipeline runs on GitHub Actions twice daily.

## Pipeline Order
```
fetch_feeds.py → score_stories.py → cluster_stories.py → generate_analysis.py → publish.py → upload_sftp.py
```

All steps are orchestrated by `scripts/publish.py`, which also generates the homepage HTML.

## Key Files

| File | Purpose |
|------|---------|
| `scripts/publish.py` | Main orchestrator — runs all steps, generates homepage HTML |
| `scripts/fetch_feeds.py` | Pulls 104 RSS feeds into SQLite DB |
| `scripts/score_stories.py` | Scores stories via Claude API (batches of 25, max_tokens=8192) |
| `scripts/cluster_stories.py` | Groups top stories into topic clusters via Claude API |
| `scripts/generate_analysis.py` | Generates analysis HTML pages with polls per cluster |
| `scripts/upload_sftp.py` | Uploads output files to One.com via SFTP/paramiko |
| `scripts/poll_tracker.py` | Manages poll lifecycle (active → archived) |
| `scripts/homepage_template_v2.html` | Homepage HTML template (uses `{{PLACEHOLDER}}` syntax) |
| `data/stories.db` | SQLite database (~150MB+, persisted via GitHub Actions cache) |
| `data/active_polls.json` | Currently active poll topics |
| `data/story_clusters.json` | Latest clustering output |
| `data/analysis_index.json` | Index of generated analysis pages |
| `output/` | Generated HTML/XML files ready for upload |
| `.github/workflows/publish.yml` | GitHub Actions workflow (runs twice daily) |

## Database
- SQLite at `data/stories.db`
- Main table: `stories` — columns: `id, title, url, source, category, published, summary, score, headline, status, fetched_at`
- Stories with `score >= 25` appear on homepage
- Status values: `new` → `reviewed` (scored) or `rejected` (score < 20)
- Persisted between GitHub Actions runs via `actions/cache/restore@v4` + `actions/cache/save@v4`

## Claude API Usage
- Model: `claude-sonnet-4-5-20250929` (used in score_stories.py, cluster_stories.py, generate_analysis.py, poll_tracker.py)
- Scoring: 25 stories per batch, max_tokens=8192
- Key env var: `ANTHROPIC_API_KEY` (GitHub Secret)
- **If model returns 404**: the model name has been deprecated — update to the latest claude-sonnet model in all 4 scripts above

## SFTP / Hosting
- Host: `ssh.cegl4w2or.service.one` (One.com)
- Port: 22, Username: `cegl4w2or_ssh`
- **Web root: `webroots/www`** — files must go here, NOT to `/`
- `SFTP_REMOTE_DIR` GitHub Secret = `webroots/www`
- Analysis files go to `webroots/www/analysis/` subdirectory
- **Known issue**: One.com periodically turns off SFTP access. If you see `socket.gaierror: Name or service not known` or `AuthenticationException`, go to One.com control panel → SFTP Administration → verify toggle is On, reset password if needed, update `SFTP_PASSWORD` GitHub Secret.

## GitHub Actions Workflow
File: `.github/workflows/publish.yml`
- Schedule: twice daily (`0 6,18 * * *` — 6 AM and 6 PM UTC)
- Manual trigger: `workflow_dispatch`
- Required secrets: `ANTHROPIC_API_KEY`, `SFTP_PASSWORD`, `SFTP_REMOTE_DIR`
- DB cache key: `stories-db-${{ github.run_number }}` (split restore/save pattern — `save-always` is deprecated)
- Bot commits data files back to repo after each run

## Common Issues & Fixes

### Site not updating
1. Check One.com SFTP toggle is On (goes off periodically)
2. If `AuthenticationException` → reset SFTP password in One.com, update `SFTP_PASSWORD` secret
3. If `Name or service not known` → SFTP is turned off on One.com

### 0 stories scored
- Check `ANTHROPIC_API_KEY` has credits at console.anthropic.com
- Check model name hasn't been deprecated (404 error in logs)
- Scoring uses batches of 25 — if seeing parse errors, check max_tokens

### Git push rejected
```bash
git stash
git pull --rebase origin main
git push origin main
git stash pop
```
GitHub Actions bot commits data files each run, so local is often behind.

### Workflow stopped running
GitHub pauses scheduled workflows after inactivity. Go to Actions tab → check for "disabled" banner → re-enable.

## Output Files Uploaded to Server
- `index.html` — homepage
- `polls.html` — archived polls page
- `feed.xml` — RSS feed
- `sitemap.xml`
- `robots.txt`
- `analysis/*.html` — individual analysis/poll pages

## Local Development
```bash
# Generate homepage locally without uploading
python3 scripts/publish.py --local-only

# Score only recent stories
python3 scripts/score_stories.py --hours 24 --limit 50

# Test SFTP connection
python3 scripts/upload_sftp.py --test
```
Requires: `ANTHROPIC_API_KEY` and `SFTP_PASSWORD` env vars set locally.
