# GitHub Actions Setup Guide

Run CassadyNet on GitHub's servers — publishes every hour automatically.

---

## Step 1 — Create a GitHub repository

1. Go to https://github.com/new
2. Name it something like `cassadynet` (can be private)
3. Leave it empty (no README, no .gitignore)
4. Click **Create repository**
5. Copy the repository URL (e.g. `https://github.com/YOURUSERNAME/cassadynet.git`)

---

## Step 2 — Push the project to GitHub

Open Terminal, navigate to the project folder, and run:

```bash
cd "/Users/jamescassady/Desktop/Jims Folder/AI and EDU/News Site/Scripts/ai_news_aggregator 2"

git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOURUSERNAME/cassadynet.git
git push -u origin main
```

> The first push may ask for your GitHub username and password.
> Use a **Personal Access Token** as the password — see:
> https://github.com/settings/tokens (classic token, check the `repo` scope)

---

## Step 3 — Add secrets to GitHub

The workflow needs two secret values that you never commit to the repo.

1. Go to your repo on GitHub
2. Click **Settings → Secrets and variables → Actions**
3. Click **New repository secret** and add each of these:

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `SFTP_PASSWORD` | Your One.com / cassadynet.com SFTP password |

---

## Step 4 — Trigger the first run

1. On GitHub, go to **Actions → Publish CassadyNet**
2. Click **Run workflow → Run workflow**
3. Watch the logs — the full pipeline should run and upload to your server

After that it runs automatically every hour at :00.

---

## How it works

```
GitHub Actions (every hour)
  ↓
Restore stories.db from cache
  ↓
python3 scripts/publish.py
  ├── Fetch 100+ feeds
  ├── Score stories (Anthropic API)
  ├── Cluster stories
  ├── Generate analysis pages
  ├── Generate homepage
  └── Upload via SFTP → cassadynet.com
  ↓
Commit updated data files back to repo
(polls, clusters, analysis index)
  ↓
Save stories.db to cache for next run
```

**Database persistence:** The `stories.db` file (~54MB) is saved in GitHub's
cache between runs. It never touches git history. Cache expires after 7 days
of no use, but with hourly runs it will always be available.

**State files** (polls, clusters, analysis index) are committed back to the
repo after each run so they survive even if the cache is cleared.

---

## Troubleshooting

- **"ANTHROPIC_API_KEY not set"** → Check Step 3 above
- **"SFTP_PASSWORD not set"** → Check Step 3 above
- **Workflow not showing** → Make sure you pushed the `.github/` folder
- **To run manually** → Actions tab → Publish CassadyNet → Run workflow
