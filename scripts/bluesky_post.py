#!/usr/bin/env python3
"""
CassadyNet - Bluesky Auto-Poster
Posts top AI news stories to Bluesky automatically.

Setup:
1. Create a Bluesky account at https://bsky.app
2. Go to Settings → App Passwords → Add App Password
3. Set environment variables:
   export BLUESKY_HANDLE='yourhandle.bsky.social'
   export BLUESKY_APP_PASSWORD='your_app_password'
"""

import sqlite3
import os
import json
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_FILE = BASE_DIR / "data" / "stories.db"
POSTED_FILE = BASE_DIR / "data" / "posted_bluesky.json"

# Bluesky API credentials (set via environment variables)
BLUESKY_CONFIG = {
    'handle': os.environ.get('BLUESKY_HANDLE', ''),
    'app_password': os.environ.get('BLUESKY_APP_PASSWORD', ''),
}

BLUESKY_API = "https://bsky.social/xrpc"


def load_posted_ids() -> set:
    """Load IDs of already-posted stories"""
    if POSTED_FILE.exists():
        with open(POSTED_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('posted_ids', []))
    return set()


def save_posted_id(story_id: str):
    """Save a posted story ID"""
    posted = load_posted_ids()
    posted.add(story_id)
    
    # Keep only last 1000 IDs to prevent file bloat
    posted_list = list(posted)[-1000:]
    
    POSTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POSTED_FILE, 'w') as f:
        json.dump({'posted_ids': posted_list, 'last_updated': datetime.now().isoformat()}, f)


def get_bluesky_session():
    """Authenticate with Bluesky and get session tokens"""
    if not BLUESKY_CONFIG['handle'] or not BLUESKY_CONFIG['app_password']:
        raise ValueError(
            "Bluesky credentials not set. Please set environment variables:\n"
            "  BLUESKY_HANDLE='yourhandle.bsky.social'\n"
            "  BLUESKY_APP_PASSWORD='your_app_password'"
        )
    
    response = requests.post(
        f"{BLUESKY_API}/com.atproto.server.createSession",
        json={
            "identifier": BLUESKY_CONFIG['handle'],
            "password": BLUESKY_CONFIG['app_password']
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"Bluesky auth failed: {response.status_code} {response.text}")
    
    return response.json()


def get_top_unposted_story():
    """Get the highest-scored story that hasn't been posted yet"""
    conn = sqlite3.connect(DB_FILE)
    posted_ids = load_posted_ids()
    
    # Get recent high-scoring stories
    stories = conn.execute("""
        SELECT id, title, url, source, score, headline
        FROM stories
        WHERE score >= 30
        AND published > datetime('now', '-24 hours')
        ORDER BY score DESC, published DESC
        LIMIT 50
    """).fetchall()
    
    conn.close()
    
    # Find first unposted story
    for story in stories:
        story_id = story[0]
        if story_id not in posted_ids:
            return {
                'id': story_id,
                'title': story[1],
                'url': story[2],
                'source': story[3],
                'score': story[4],
                'headline': story[5]
            }
    
    return None


def create_post_with_link(session: dict, text: str, url: str, title: str) -> dict:
    """Create a Bluesky post with a link card"""
    
    # Find URL position in text for facet
    url_start = text.find(url)
    url_end = url_start + len(url) if url_start >= 0 else 0
    
    # Build the post record
    record = {
        "repo": session["did"],
        "collection": "app.bsky.feed.post",
        "record": {
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "$type": "app.bsky.feed.post",
            "embed": {
                "$type": "app.bsky.embed.external",
                "external": {
                    "uri": url,
                    "title": title[:300],
                    "description": ""
                }
            }
        }
    }
    
    # Add link facet if URL is in text
    if url_start >= 0:
        record["record"]["facets"] = [{
            "index": {
                "byteStart": len(text[:url_start].encode('utf-8')),
                "byteEnd": len(text[:url_end].encode('utf-8'))
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#link",
                "uri": url
            }]
        }]
    
    response = requests.post(
        f"{BLUESKY_API}/com.atproto.repo.createRecord",
        headers={"Authorization": f"Bearer {session['accessJwt']}"},
        json=record
    )
    
    return response


def generate_post_text(story: dict) -> tuple:
    """Generate post text for a story. Returns (text, url, title)"""
    
    # Use AI headline if available, otherwise original title
    title = story['headline'] if story['headline'] else story['title']
    url = story['url']
    source = story['source']
    
    # Bluesky limit is 300 chars
    # Format: "Title [Source]\n\nURL"
    
    max_title_len = 300 - len(f" [{source}]\n\n{url}") - 5  # safety margin
    
    if len(title) > max_title_len:
        title = title[:max_title_len-3] + "..."
    
    text = f"{title} [{source}]\n\n{url}"
    
    return text, url, title


def post_to_bluesky(story: dict, dry_run: bool = False) -> bool:
    """Post a story to Bluesky"""
    
    text, url, title = generate_post_text(story)
    
    logger.info(f"Post ({len(text)} chars):")
    logger.info("-" * 40)
    logger.info(text)
    logger.info("-" * 40)
    
    if dry_run:
        logger.info("DRY RUN - Post not sent")
        return True
    
    try:
        session = get_bluesky_session()
        response = create_post_with_link(session, text, url, story['title'])
        
        if response.status_code == 200:
            result = response.json()
            post_uri = result.get('uri', '')
            # Extract post ID for URL
            parts = post_uri.split('/')
            if len(parts) >= 2:
                post_id = parts[-1]
                handle = BLUESKY_CONFIG['handle']
                logger.info(f"✅ Posted to Bluesky!")
                logger.info(f"   https://bsky.app/profile/{handle}/post/{post_id}")
            else:
                logger.info(f"✅ Posted to Bluesky! URI: {post_uri}")
            
            # Mark as posted
            save_posted_id(story['id'])
            return True
        else:
            logger.error(f"❌ Failed to post: {response.status_code} {response.text}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Failed to post: {e}")
        return False


def post_top_story(dry_run: bool = False):
    """Find and post the top unposted story"""
    
    story = get_top_unposted_story()
    
    if not story:
        logger.info("No unposted stories found (score >= 30 in last 24h)")
        return False
    
    logger.info(f"Selected story (score: {story['score']}):")
    logger.info(f"  {story['title']}")
    
    return post_to_bluesky(story, dry_run=dry_run)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Post top AI news to Bluesky")
    parser.add_argument("--dry-run", action="store_true", help="Generate post but don't send")
    parser.add_argument("--count", type=int, default=1, help="Number of posts to send (default: 1)")
    
    args = parser.parse_args()
    
    logger.info("=" * 50)
    logger.info("CassadyNet Bluesky Bot")
    logger.info("=" * 50)
    
    for i in range(args.count):
        if i > 0:
            logger.info("")
        logger.info(f"Post {i+1}/{args.count}")
        post_top_story(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
