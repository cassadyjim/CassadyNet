#!/usr/bin/env python3
"""
CassadyNet - Social Media Post Generator
Generates ready-to-copy posts for Facebook and Instagram.
Just run this script and copy/paste the output into Meta Business Suite.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_FILE = BASE_DIR / "data" / "stories.db"


def get_top_stories(count: int = 5):
    """Get top scored stories from the last 24 hours"""
    conn = sqlite3.connect(DB_FILE)
    
    stories = conn.execute("""
        SELECT title, url, source, score, headline
        FROM stories
        WHERE score >= 30
        AND published > datetime('now', '-24 hours')
        ORDER BY score DESC, published DESC
        LIMIT ?
    """, (count,)).fetchall()
    
    conn.close()
    return stories


def generate_facebook_post(title: str, url: str, source: str, headline: str = None) -> str:
    """Generate a Facebook-formatted post"""
    display_title = headline if headline else title
    
    post = f"""🤖 {display_title}

📰 Source: {source}

🔗 {url}

━━━━━━━━━━━━━━━
Follow CassadyNet for daily AI news
🌐 cassadynet.com
━━━━━━━━━━━━━━━

#AI #ArtificialIntelligence #TechNews #AINews #MachineLearning #CassadyNet"""
    
    return post


def generate_instagram_post(title: str, url: str, source: str, headline: str = None) -> str:
    """Generate an Instagram-formatted post (no clickable links in captions)"""
    display_title = headline if headline else title
    
    post = f"""🤖 {display_title}

📰 Source: {source}

━━━━━━━━━━━━━━━
🔗 Link in bio → cassadynet.com
━━━━━━━━━━━━━━━

Follow @cassadynet for daily AI news curated by AI

#AI #ArtificialIntelligence #TechNews #AINews #MachineLearning #OpenAI #ChatGPT #Tech #Innovation #FutureTech #AIUpdate #TechUpdate #BreakingNews #CassadyNet"""
    
    return post


def generate_short_post(title: str, url: str, source: str, headline: str = None) -> str:
    """Generate a short post for Twitter/X manual sharing"""
    display_title = headline if headline else title
    
    post = f"""{display_title} [{source}]

🔗 {url}

More AI news: cassadynet.com

#AI #TechNews"""
    
    return post


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate social media posts")
    parser.add_argument("--count", type=int, default=3, help="Number of stories (default: 3)")
    parser.add_argument("--platform", choices=["all", "facebook", "instagram", "twitter"], 
                        default="all", help="Platform format (default: all)")
    
    args = parser.parse_args()
    
    stories = get_top_stories(args.count)
    
    if not stories:
        print("No stories found (score >= 30 in last 24h)")
        print("Try running: python3 scripts/score_stories.py --hours 24 --limit 30")
        return
    
    print("=" * 60)
    print(f"CASSADYNET SOCIAL MEDIA POSTS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Stories: {len(stories)}")
    print("=" * 60)
    
    for i, (title, url, source, score, headline) in enumerate(stories, 1):
        print(f"\n{'━' * 60}")
        print(f"STORY {i} (Score: {score})")
        print(f"{'━' * 60}")
        print(f"Original: {title[:80]}...")
        
        if args.platform in ["all", "facebook"]:
            print(f"\n{'─' * 40}")
            print("📘 FACEBOOK (copy below):")
            print("─" * 40)
            print(generate_facebook_post(title, url, source, headline))
        
        if args.platform in ["all", "instagram"]:
            print(f"\n{'─' * 40}")
            print("📸 INSTAGRAM (copy below):")
            print("─" * 40)
            print(generate_instagram_post(title, url, source, headline))
        
        if args.platform in ["all", "twitter"]:
            print(f"\n{'─' * 40}")
            print("🐦 TWITTER/X (copy below):")
            print("─" * 40)
            print(generate_short_post(title, url, source, headline))
    
    print(f"\n{'=' * 60}")
    print("TIP: Copy and paste into Meta Business Suite or your scheduler")
    print("=" * 60)


if __name__ == "__main__":
    main()
