#!/usr/bin/env python3
"""
AI News Aggregator - RSS Feed Fetcher
Fetches stories from configured RSS feeds and stores them in SQLite.
"""

import asyncio
import aiohttp
import feedparser
import sqlite3
import json
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
from email.utils import parsedate_to_datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
FEEDS_FILE = BASE_DIR / "feeds" / "sources.json"
DB_FILE = BASE_DIR / "data" / "stories.db"

# Ensure data directory exists
DB_FILE.parent.mkdir(parents=True, exist_ok=True)


def init_database():
    """Initialize the SQLite database with required tables"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stories (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                category TEXT,
                published TIMESTAMP,
                summary TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tier INTEGER DEFAULT 1,
                score REAL DEFAULT 0,
                status TEXT DEFAULT 'new',
                headline TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feed_status (
                feed_name TEXT PRIMARY KEY,
                last_fetch TIMESTAMP,
                last_success TIMESTAMP,
                error_count INTEGER DEFAULT 0,
                last_error TEXT
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stories_published ON stories(published DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stories_source ON stories(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(status)")
        conn.commit()


def load_feeds() -> List[Dict]:
    """Load feed configurations from JSON file"""
    if not FEEDS_FILE.exists():
        logger.error(f"Feeds file not found: {FEEDS_FILE}")
        return []
    
    with open(FEEDS_FILE) as f:
        data = json.load(f)
    
    return data.get("feeds", [])


def generate_story_id(url: str) -> str:
    """Generate a unique ID for a story based on its URL"""
    return hashlib.md5(url.encode()).hexdigest()[:16]


def parse_date(date_input) -> Optional[datetime]:
    """Parse various date formats into a timezone-aware datetime"""
    if date_input is None:
        return None
    
    # If it's already a datetime
    if isinstance(date_input, datetime):
        if date_input.tzinfo is None:
            return date_input.replace(tzinfo=timezone.utc)
        return date_input
    
    # If it's a struct_time (from feedparser)
    if hasattr(date_input, 'tm_year'):
        try:
            dt = datetime(*date_input[:6])
            return dt.replace(tzinfo=timezone.utc)
        except:
            return None
    
    # If it's a string
    if isinstance(date_input, str):
        try:
            return parsedate_to_datetime(date_input)
        except:
            pass
        
        # Try ISO format
        try:
            dt = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except:
            pass
    
    return None


def clean_html(text: str) -> str:
    """Remove HTML tags and clean up text"""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    clean = ' '.join(clean.split())
    return clean[:1000]  # Limit summary length


def update_feed_status(feed_name: str, success: bool, error: str = None):
    """Update the status of a feed in the database"""
    now = datetime.now(timezone.utc).isoformat()
    
    with sqlite3.connect(DB_FILE) as conn:
        if success:
            conn.execute("""
                INSERT INTO feed_status (feed_name, last_fetch, last_success, error_count)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(feed_name) DO UPDATE SET
                    last_fetch = excluded.last_fetch,
                    last_success = excluded.last_success,
                    error_count = 0,
                    last_error = NULL
            """, (feed_name, now, now))
        else:
            conn.execute("""
                INSERT INTO feed_status (feed_name, last_fetch, error_count, last_error)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(feed_name) DO UPDATE SET
                    last_fetch = excluded.last_fetch,
                    error_count = feed_status.error_count + 1,
                    last_error = excluded.last_error
            """, (feed_name, now, error))
        conn.commit()


async def fetch_feed(session: aiohttp.ClientSession, feed: Dict) -> List[Dict]:
    """Fetch and parse a single RSS feed"""
    feed_name = feed["name"]
    feed_url = feed["url"]
    category = feed.get("category", "general")
    
    logger.info(f"Fetching: {feed_name}")
    
    try:
        async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}")
            
            content = await response.text()
        
        # Parse the feed
        parsed = feedparser.parse(content)
        
        if parsed.bozo and not parsed.entries:
            raise Exception(f"Feed parse error: {parsed.bozo_exception}")
        
        stories = []
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)
        
        for entry in parsed.entries:
            try:
                # Get URL
                url = entry.get("link", "")
                if not url:
                    continue
                
                # Get title
                title = entry.get("title", "")
                if not title:
                    continue
                
                # Parse publication date
                published = None
                for date_field in ["published_parsed", "updated_parsed", "created_parsed"]:
                    if hasattr(entry, date_field) and getattr(entry, date_field):
                        published = parse_date(getattr(entry, date_field))
                        if published:
                            break
                
                if not published:
                    for date_field in ["published", "updated", "created"]:
                        if hasattr(entry, date_field) and getattr(entry, date_field):
                            published = parse_date(getattr(entry, date_field))
                            if published:
                                break
                
                # Default to now if no date found
                if not published:
                    published = now
                
                # Skip old stories
                if published < cutoff:
                    continue
                
                # Get summary
                summary = ""
                if hasattr(entry, "summary"):
                    summary = clean_html(entry.summary)
                elif hasattr(entry, "description"):
                    summary = clean_html(entry.description)
                
                story = {
                    "id": generate_story_id(url),
                    "title": clean_html(title),
                    "url": url,
                    "source": feed_name,
                    "category": category,
                    "published": published.isoformat(),
                    "summary": summary,
                }
                stories.append(story)
                
            except Exception as e:
                continue
        
        update_feed_status(feed_name, success=True)
        return stories
        
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"  ✗ {feed_name}: {error_msg}")
        update_feed_status(feed_name, success=False, error=error_msg)
        return []


def save_stories(stories: List[Dict]) -> int:
    """Save stories to the database, returns count of new stories"""
    if not stories:
        return 0
    
    new_count = 0
    now = datetime.now(timezone.utc).isoformat()
    
    with sqlite3.connect(DB_FILE) as conn:
        for story in stories:
            try:
                conn.execute("""
                    INSERT INTO stories (id, title, url, source, category, published, summary, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING
                """, (
                    story["id"],
                    story["title"],
                    story["url"],
                    story["source"],
                    story["category"],
                    story["published"],
                    story["summary"],
                    now
                ))
                
                if conn.total_changes > 0:
                    new_count += 1
                    
            except sqlite3.IntegrityError:
                pass
            except Exception as e:
                logger.error(f"Error saving story: {e}")
        
        conn.commit()
    
    return new_count


async def fetch_all_feeds(feeds: List[Dict], max_concurrent: int = 10) -> List[Dict]:
    """Fetch all feeds concurrently"""
    connector = aiohttp.TCPConnector(limit=max_concurrent)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_feed(session, feed) for feed in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_stories = []
    for result in results:
        if isinstance(result, list):
            all_stories.extend(result)
        elif isinstance(result, Exception):
            logger.error(f"Feed error: {result}")
    
    return all_stories


def get_database_stats() -> Dict:
    """Get statistics about the database"""
    with sqlite3.connect(DB_FILE) as conn:
        total = conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE date(fetched_at) = date('now')"
        ).fetchone()[0]
        
        by_source = conn.execute("""
            SELECT source, COUNT(*) as count 
            FROM stories 
            GROUP BY source 
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()
        
        recent = conn.execute("""
            SELECT title, source, published 
            FROM stories 
            ORDER BY published DESC 
            LIMIT 5
        """).fetchall()
        
    return {
        "total": total,
        "today": today,
        "by_source": by_source,
        "recent": recent
    }


async def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("AI NEWS AGGREGATOR - Feed Puller")
    logger.info("=" * 60)
    
    # Initialize database
    init_database()
    
    # Load feeds
    feeds = load_feeds()
    if not feeds:
        logger.error("No feeds configured")
        return
    
    logger.info(f"Starting fetch of {len(feeds)} feeds...")
    
    # Fetch all feeds
    stories = await fetch_all_feeds(feeds)
    
    # Save to database
    new_count = save_stories(stories)
    
    # Print results
    logger.info("-" * 60)
    logger.info("RESULTS:")
    logger.info(f"  Feeds checked:    {len(feeds)}")
    logger.info(f"  Stories fetched:  {len(stories)}")
    logger.info(f"  New stories:      {new_count}")
    
    # Database stats
    stats = get_database_stats()
    logger.info("-" * 60)
    logger.info("DATABASE STATS:")
    logger.info(f"  Total stories:    {stats['total']}")
    logger.info(f"  Fetched today:    {stats['today']}")
    logger.info("-" * 60)
    logger.info("Recent stories:")
    for title, source, published in stats['recent']:
        logger.info(f"  [{source}] {title[:50]}...")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
