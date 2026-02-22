#!/usr/bin/env python3
"""
AI News Aggregator - Database Viewer
View stories, stats, and manage the database.
"""

import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from tabulate import tabulate

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_FILE = BASE_DIR / "data" / "stories.db"


def get_connection():
    """Get database connection"""
    if not DB_FILE.exists():
        print(f"Database not found at {DB_FILE}")
        print("Run fetch_feeds.py first to create it.")
        exit(1)
    return sqlite3.connect(DB_FILE)


def cmd_stats(args):
    """Show database statistics"""
    with get_connection() as conn:
        # Total stories
        total = conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]

        # Stories by time period
        today = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE date(fetched_at) = date('now')"
        ).fetchone()[0]

        last_hour = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE fetched_at > datetime('now', '-1 hour')"
        ).fetchone()[0]

        last_24h = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE fetched_at > datetime('now', '-24 hours')"
        ).fetchone()[0]

        # By source
        by_source = conn.execute("""
            SELECT source, COUNT(*) as cnt
            FROM stories
            GROUP BY source
            ORDER BY cnt DESC
            LIMIT 15
        """).fetchall()

        # By category
        by_category = conn.execute("""
            SELECT category, COUNT(*) as cnt
            FROM stories
            GROUP BY category
            ORDER BY cnt DESC
        """).fetchall()

        # Feed status
        feed_status = conn.execute("""
            SELECT feed_name,
                   datetime(last_success) as last_ok,
                   error_count,
                   last_error
            FROM feed_status
            ORDER BY error_count DESC, last_success DESC
            LIMIT 15
        """).fetchall()

    print("\n" + "="*60)
    print("DATABASE STATISTICS")
    print("="*60)
    print(f"\nTotal stories:     {total:,}")
    print(f"Last hour:         {last_hour:,}")
    print(f"Last 24 hours:     {last_24h:,}")
    print(f"Today:             {today:,}")

    print("\n" + "-"*60)
    print("STORIES BY SOURCE (Top 15)")
    print("-"*60)
    print(tabulate(by_source, headers=["Source", "Count"], tablefmt="simple"))

    print("\n" + "-"*60)
    print("STORIES BY CATEGORY")
    print("-"*60)
    print(tabulate(by_category, headers=["Category", "Count"], tablefmt="simple"))

    print("\n" + "-"*60)
    print("FEED STATUS")
    print("-"*60)
    print(tabulate(feed_status, headers=["Feed", "Last Success", "Errors", "Last Error"], tablefmt="simple"))


def cmd_recent(args):
    """Show recent stories"""
    limit = args.limit or 20
    category = args.category
    source = args.source

    query = """
        SELECT title, source, category,
               datetime(published) as pub_date,
               url
        FROM stories
        WHERE 1=1
    """
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)

    if source:
        query += " AND source LIKE ?"
        params.append(f"%{source}%")

    query += " ORDER BY published DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        stories = conn.execute(query, params).fetchall()

    print("\n" + "="*80)
    print(f"RECENT STORIES (Last {limit})")
    if category:
        print(f"Category filter: {category}")
    if source:
        print(f"Source filter: {source}")
    print("="*80 + "\n")

    for i, (title, src, cat, pub_date, url) in enumerate(stories, 1):
        print(f"{i:2}. [{cat}] {src}")
        print(f"    {title[:75]}{'...' if len(title) > 75 else ''}")
        print(f"    {pub_date}")
        print(f"    {url[:80]}")
        print()


def cmd_search(args):
    """Search stories by keyword"""
    keyword = args.keyword
    limit = args.limit or 20

    with get_connection() as conn:
        stories = conn.execute("""
            SELECT title, source, category,
                   datetime(published) as pub_date,
                   url,
                   summary
            FROM stories
            WHERE title LIKE ? OR summary LIKE ?
            ORDER BY published DESC
            LIMIT ?
        """, (f"%{keyword}%", f"%{keyword}%", limit)).fetchall()

    print("\n" + "="*80)
    print(f"SEARCH RESULTS: '{keyword}' ({len(stories)} found)")
    print("="*80 + "\n")

    for i, (title, source, cat, pub_date, url, summary) in enumerate(stories, 1):
        print(f"{i:2}. [{cat}] {source} - {pub_date}")
        print(f"    {title}")
        if summary:
            print(f"    {summary[:150]}...")
        print(f"    {url}")
        print()


def cmd_export(args):
    """Export stories to JSON"""
    import json

    hours = args.hours or 24
    output = args.output or f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with get_connection() as conn:
        stories = conn.execute("""
            SELECT id, title, url, source, category, published, summary, fetched_at, tier
            FROM stories
            WHERE fetched_at > datetime('now', ?)
            ORDER BY published DESC
        """, (f"-{hours} hours",)).fetchall()

    export_data = {
        "exported_at": datetime.now().isoformat(),
        "hours_covered": hours,
        "story_count": len(stories),
        "stories": [
            {
                "id": s[0],
                "title": s[1],
                "url": s[2],
                "source": s[3],
                "category": s[4],
                "published": s[5],
                "summary": s[6],
                "fetched_at": s[7],
                "tier": s[8]
            }
            for s in stories
        ]
    }

    with open(output, 'w') as f:
        json.dump(export_data, f, indent=2)

    print(f"Exported {len(stories)} stories to {output}")


def cmd_cleanup(args):
    """Remove old stories"""
    days = args.days or 30

    # Validate input
    if days < 1:
        print("Error: --days must be at least 1")
        return

    with get_connection() as conn:
        # Count stories to delete
        count = conn.execute("""
            SELECT COUNT(*) FROM stories
            WHERE fetched_at < datetime('now', ?)
        """, (f"-{days} days",)).fetchone()[0]

        if args.dry_run:
            print(f"Would delete {count} stories older than {days} days")
        else:
            conn.execute("""
                DELETE FROM stories
                WHERE fetched_at < datetime('now', ?)
            """, (f"-{days} days",))
            conn.commit()
            print(f"Deleted {count} stories older than {days} days")


def main():
    parser = argparse.ArgumentParser(description="AI News Aggregator Database Tools")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.set_defaults(func=cmd_stats)
    
    # Recent command
    recent_parser = subparsers.add_parser("recent", help="Show recent stories")
    recent_parser.add_argument("-n", "--limit", type=int, help="Number of stories (default: 20)")
    recent_parser.add_argument("-c", "--category", help="Filter by category")
    recent_parser.add_argument("-s", "--source", help="Filter by source (partial match)")
    recent_parser.set_defaults(func=cmd_recent)
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search stories")
    search_parser.add_argument("keyword", help="Search keyword")
    search_parser.add_argument("-n", "--limit", type=int, help="Max results (default: 20)")
    search_parser.set_defaults(func=cmd_search)
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export stories to JSON")
    export_parser.add_argument("-o", "--output", help="Output file name")
    export_parser.add_argument("--hours", type=int, help="Hours of history (default: 24)")
    export_parser.set_defaults(func=cmd_export)
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Remove old stories")
    cleanup_parser.add_argument("--days", type=int, help="Delete stories older than N days (default: 30)")
    cleanup_parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    cleanup_parser.set_defaults(func=cmd_cleanup)
    
    args = parser.parse_args()
    
    if args.command:
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
