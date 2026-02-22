#!/usr/bin/env python3
"""
CassadyNet - Twitter/X Auto-Poster
Posts top AI news stories to Twitter/X automatically.

Setup:
1. Create a Twitter Developer account: https://developer.twitter.com
2. Create a project and app with OAuth 1.0a (Read and Write permissions)
3. Generate Access Token and Secret
4. Set environment variables:
   export TWITTER_API_KEY='your_api_key'
   export TWITTER_API_SECRET='your_api_secret'
   export TWITTER_ACCESS_TOKEN='your_access_token'
   export TWITTER_ACCESS_SECRET='your_access_secret'
"""

import sqlite3
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import tweepy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_FILE = BASE_DIR / "data" / "stories.db"
POSTED_FILE = BASE_DIR / "data" / "posted_tweets.json"

# Twitter API credentials (set via environment variables)
TWITTER_CONFIG = {
    'api_key': os.environ.get('TWITTER_API_KEY', ''),
    'api_secret': os.environ.get('TWITTER_API_SECRET', ''),
    'access_token': os.environ.get('TWITTER_ACCESS_TOKEN', ''),
    'access_secret': os.environ.get('TWITTER_ACCESS_SECRET', ''),
}

# Hashtags to add based on content
HASHTAG_KEYWORDS = {
    'openai': '#OpenAI',
    'chatgpt': '#ChatGPT',
    'gpt-4': '#GPT4',
    'gpt-5': '#GPT5',
    'anthropic': '#Anthropic',
    'claude': '#Claude',
    'google': '#Google',
    'gemini': '#Gemini',
    'deepmind': '#DeepMind',
    'meta': '#MetaAI',
    'llama': '#Llama',
    'microsoft': '#Microsoft',
    'copilot': '#Copilot',
    'nvidia': '#NVIDIA',
    'robot': '#Robotics',
    'china': '#ChinaTech',
    'regulation': '#AIRegulation',
    'safety': '#AISafety',
}


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


def get_twitter_client():
    """Initialize Twitter API client"""
    if not all(TWITTER_CONFIG.values()):
        raise ValueError(
            "Twitter credentials not set. Please set environment variables:\n"
            "  TWITTER_API_KEY\n"
            "  TWITTER_API_SECRET\n"
            "  TWITTER_ACCESS_TOKEN\n"
            "  TWITTER_ACCESS_SECRET"
        )
    
    client = tweepy.Client(
        consumer_key=TWITTER_CONFIG['api_key'],
        consumer_secret=TWITTER_CONFIG['api_secret'],
        access_token=TWITTER_CONFIG['access_token'],
        access_token_secret=TWITTER_CONFIG['access_secret']
    )
    
    return client


def get_top_unposted_story():
    """Get the highest-scored story that hasn't been posted yet"""
    posted_ids = load_posted_ids()

    # Get recent high-scoring stories
    with sqlite3.connect(DB_FILE) as conn:
        stories = conn.execute("""
            SELECT id, title, url, source, score, headline
            FROM stories
            WHERE score >= 30
            AND published > datetime('now', '-24 hours')
            ORDER BY score DESC, published DESC
            LIMIT 50
        """).fetchall()

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


def generate_tweet_text(story: dict) -> str:
    """Generate tweet text for a story"""
    
    # Use AI headline if available, otherwise original title
    title = story['headline'] if story['headline'] else story['title']
    url = story['url']
    source = story['source']
    
    # Find relevant hashtags (max 2)
    hashtags = []
    title_lower = title.lower()
    for keyword, hashtag in HASHTAG_KEYWORDS.items():
        if keyword in title_lower and len(hashtags) < 2:
            hashtags.append(hashtag)
    
    # Always add #AI
    if '#AI' not in hashtags and len(hashtags) < 3:
        hashtags.append('#AI')
    
    hashtag_str = ' '.join(hashtags)
    
    # Build tweet (max 280 chars)
    # Format: "Title [Source] URL #hashtags"
    # URL counts as 23 chars on Twitter
    
    max_title_len = 280 - 23 - len(f" [{source}] ") - len(hashtag_str) - 5  # 5 for safety margin
    
    if len(title) > max_title_len:
        title = title[:max_title_len-3] + "..."
    
    tweet = f"{title} [{source}]\n\n{url}\n\n{hashtag_str}"
    
    return tweet.strip()


def post_tweet(story: dict, dry_run: bool = False) -> bool:
    """Post a tweet for the given story"""
    
    tweet_text = generate_tweet_text(story)
    
    logger.info(f"Tweet ({len(tweet_text)} chars):")
    logger.info("-" * 40)
    logger.info(tweet_text)
    logger.info("-" * 40)
    
    if dry_run:
        logger.info("DRY RUN - Tweet not posted")
        return True
    
    try:
        client = get_twitter_client()
        response = client.create_tweet(text=tweet_text)
        
        tweet_id = response.data['id']
        logger.info(f"✅ Tweet posted! ID: {tweet_id}")
        logger.info(f"   https://twitter.com/i/web/status/{tweet_id}")
        
        # Mark as posted
        save_posted_id(story['id'])
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to post tweet: {e}")
        return False


def post_top_story(dry_run: bool = False):
    """Find and post the top unposted story"""
    
    story = get_top_unposted_story()
    
    if not story:
        logger.info("No unposted stories found (score >= 30 in last 24h)")
        return False
    
    logger.info(f"Selected story (score: {story['score']}):")
    logger.info(f"  {story['title']}")
    
    return post_tweet(story, dry_run=dry_run)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Post top AI news to Twitter")
    parser.add_argument("--dry-run", action="store_true", help="Generate tweet but don't post")
    parser.add_argument("--count", type=int, default=1, help="Number of tweets to post (default: 1)")
    
    args = parser.parse_args()
    
    logger.info("=" * 50)
    logger.info("CassadyNet Twitter Bot")
    logger.info("=" * 50)
    
    for i in range(args.count):
        if i > 0:
            logger.info("")
        logger.info(f"Tweet {i+1}/{args.count}")
        post_top_story(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
