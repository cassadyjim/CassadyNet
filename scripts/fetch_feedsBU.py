#!/usr/bin/env python3
"""
AI News Aggregator - RSS Feed Puller
Fetches stories from configured RSS feeds and stores them in SQLite database.
Designed for speed - async fetching of all feeds in parallel.
"""

import asyncio
import aiohttp
import sqlite3
import hashlib
import json
import feedparser
import logging
import re
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from html import unescape

# Configure logging
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


@dataclass
class Story:
    """Represents a news story"""
    id: str  # Hash of URL
    title: str
    url: str
    source: str
    category: str
    published: datetime
    summary: str
    fetched_at: datetime
    tier: int


def clean_html(text: str) -> str:
    """Remove HTML tags and clean up text"""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Unescape HTML entities
    text = unescape(text)
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:1000]  # Limit summary length


def generate_story_id(url: str) -> str:
    """Generate unique ID from URL"""
    return hashlib.md5(url.encode()).hexdigest()[:16]


def parse_date(date_str: str, feed_name: str) -> datetime:
    """Parse various date formats from RSS feeds"""
    if not date_str:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    
    try:
        # Try dateutil parser (handles most formats)
        return date_parser.parse(date_str, fuzzy=True)
    except Exception:
        logger.warning(f"Could not parse date '{date_str}' from {feed_name}, using now")
        return datetime.now(timezone.utc).replace(tzinfo=None)


class Database:
    """SQLite database handler"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
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
                CREATE INDEX IF NOT EXISTS idx_published ON stories(published DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON stories(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source ON stories(source)
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
            conn.commit()
    
    def story_exists(self, story_id: str) -> bool:
        """Check if story already exists"""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "SELECT 1 FROM stories WHERE id = ?", (story_id,)
            ).fetchone()
            return result is not None
    
    def insert_story(self, story: Story) -> bool:
        """Insert story if it doesn't exist. Returns True if inserted."""
        if self.story_exists(story.id):
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO stories (id, title, url, source, category, published, summary, fetched_at, tier)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    story.id,
                    story.title,
                    story.url,
                    story.source,
                    story.category,
                    story.published.isoformat(),
                    story.summary,
                    story.fetched_at.isoformat(),
                    story.tier
                ))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    def update_feed_status(self, feed_name: str, success: bool, error: str = None):
        """Update feed fetch status"""
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            if success:
                conn.execute("""
                    INSERT INTO feed_status (feed_name, last_fetch, last_success, error_count)
                    VALUES (?, ?, ?, 0)
                    ON CONFLICT(feed_name) DO UPDATE SET
                        last_fetch = ?,
                        last_success = ?,
                        error_count = 0,
                        last_error = NULL
                """, (feed_name, now, now, now, now))
            else:
                conn.execute("""
                    INSERT INTO feed_status (feed_name, last_fetch, error_count, last_error)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(feed_name) DO UPDATE SET
                        last_fetch = ?,
                        error_count = error_count + 1,
                        last_error = ?
                """, (feed_name, now, error, now, error))
            conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
            today = conn.execute(
                "SELECT COUNT(*) FROM stories WHERE date(fetched_at) = date('now')"
            ).fetchone()[0]
            by_source = conn.execute("""
                SELECT source, COUNT(*) as cnt 
                FROM stories 
                GROUP BY source 
                ORDER BY cnt DESC 
                LIMIT 10
            """).fetchall()
            by_category = conn.execute("""
                SELECT category, COUNT(*) as cnt 
                FROM stories 
                GROUP BY category 
                ORDER BY cnt DESC
            """).fetchall()
            recent = conn.execute("""
                SELECT title, source, published 
                FROM stories 
                ORDER BY fetched_at DESC 
                LIMIT 5
            """).fetchall()
            
            return {
                "total_stories": total,
                "fetched_today": today,
                "by_source": dict(by_source),
                "by_category": dict(by_category),
                "recent_stories": recent
            }


class FeedAggregator:
    """Async RSS feed aggregator"""
    
    def __init__(self, feeds_file: Path, db: Database):
        self.feeds_file = feeds_file
        self.db = db
        self.feeds = self._load_feeds()
        
    def _load_feeds(self) -> List[Dict]:
        """Load feed configuration"""
        with open(self.feeds_file) as f:
            config = json.load(f)
        return [f for f in config["feeds"] if f.get("enabled", True)]
    
    async def fetch_feed(self, session: aiohttp.ClientSession, feed: Dict) -> List[Story]:
        """Fetch and parse a single RSS feed"""
        stories = []
        feed_name = feed["name"]
        feed_url = feed["url"]
        
        try:
            logger.info(f"Fetching: {feed_name}")
            
            headers = {
                "User-Agent": "AI-News-Aggregator/1.0 (News aggregation service)",
                "Accept": "application/rss+xml, application/xml, text/xml, */*"
            }
            
            async with session.get(feed_url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                content = await response.text()
                
            # Parse RSS/Atom feed
            parsed = feedparser.parse(content)
            
            if parsed.bozo and not parsed.entries:
                raise Exception(f"Feed parse error: {parsed.bozo_exception}")
            
            for entry in parsed.entries:
                # Extract URL
                url = entry.get("link", "")
                if not url:
                    continue
                
                # Extract title
                title = clean_html(entry.get("title", ""))
                if not title:
                    continue
                
                # Extract published date
                published_str = entry.get("published") or entry.get("updated") or ""
                published = parse_date(published_str, feed_name)
                
                # Skip stories older than 7 days
                if published < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7):
                    continue
                
                # Extract summary
                summary = ""
                if entry.get("summary"):
                    summary = clean_html(entry.get("summary"))
                elif entry.get("description"):
                    summary = clean_html(entry.get("description"))
                elif entry.get("content"):
                    content_list = entry.get("content", [])
                    if content_list:
                        summary = clean_html(content_list[0].get("value", ""))
                
                story = Story(
                    id=generate_story_id(url),
                    title=title,
                    url=url,
                    source=feed_name,
                    category=feed.get("category", "uncategorized"),
                    published=published,
                    summary=summary,
                    fetched_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    tier=feed.get("tier", 1)
                )
                stories.append(story)
            
            self.db.update_feed_status(feed_name, success=True)
            logger.info(f"  ✓ {feed_name}: {len(stories)} stories")
            
        except asyncio.TimeoutError:
            error = "Timeout"
            self.db.update_feed_status(feed_name, success=False, error=error)
            logger.warning(f"  ✗ {feed_name}: {error}")
        except Exception as e:
            error = str(e)[:200]
            self.db.update_feed_status(feed_name, success=False, error=error)
            logger.warning(f"  ✗ {feed_name}: {error}")
        
        return stories
    
    async def fetch_all(self) -> Dict[str, int]:
        """Fetch all feeds in parallel"""
        logger.info(f"Starting fetch of {len(self.feeds)} feeds...")
        
        connector = aiohttp.TCPConnector(limit=10)  # Limit concurrent connections
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [self.fetch_feed(session, feed) for feed in self.feeds]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        total_fetched = 0
        total_new = 0
        
        for result in results:
            if isinstance(result, Exception):
                continue
            for story in result:
                total_fetched += 1
                if self.db.insert_story(story):
                    total_new += 1
        
        return {
            "feeds_checked": len(self.feeds),
            "stories_fetched": total_fetched,
            "new_stories": total_new
        }


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("AI NEWS AGGREGATOR - Feed Puller")
    logger.info("=" * 60)
    
    # Initialize database
    db = Database(DB_FILE)
    
    # Initialize aggregator
    aggregator = FeedAggregator(FEEDS_FILE, db)
    
    # Run async fetch
    results = asyncio.run(aggregator.fetch_all())
    
    # Print results
    logger.info("-" * 60)
    logger.info(f"RESULTS:")
    logger.info(f"  Feeds checked:    {results['feeds_checked']}")
    logger.info(f"  Stories fetched:  {results['stories_fetched']}")
    logger.info(f"  New stories:      {results['new_stories']}")
    
    # Print stats
    stats = db.get_stats()
    logger.info("-" * 60)
    logger.info(f"DATABASE STATS:")
    logger.info(f"  Total stories:    {stats['total_stories']}")
    logger.info(f"  Fetched today:    {stats['fetched_today']}")
    logger.info("-" * 60)
    logger.info("Recent stories:")
    for title, source, published in stats["recent_stories"]:
        logger.info(f"  • [{source}] {title[:60]}...")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
