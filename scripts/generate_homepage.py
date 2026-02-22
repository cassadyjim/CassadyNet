#!/usr/bin/env python3
"""
AI News Aggregator - Homepage Generator
Generates a Drudge Report-style HTML page from scored stories.
"""

import sqlite3
import json
import argparse
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_FILE = BASE_DIR / "data" / "stories.db"
OUTPUT_DIR = BASE_DIR / "output"

# =============================================================================
# HTML TEMPLATE - Drudge Report Style
# =============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="AI News Report - Breaking AI news from around the globe. Fast. Comprehensive. No fluff.">
    <title>AI NEWS REPORT</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Georgia&family=Arial&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            background-color: #ffffff;
            font-family: Arial, Helvetica, sans-serif;
            font-size: 14px;
            line-height: 1.4;
            color: #000000;
            max-width: 1000px;
            margin: 0 auto;
            padding: 10px;
        }}
        
        /* Header */
        .header {{
            text-align: center;
            padding: 15px 0;
            border-bottom: 2px solid #000;
            margin-bottom: 15px;
        }}
        
        .site-title {{
            font-size: 36px;
            font-weight: bold;
            font-family: Georgia, serif;
            letter-spacing: 2px;
            color: #000;
            text-decoration: none;
        }}
        
        .site-title:hover {{
            color: #cc0000;
        }}
        
        .tagline {{
            font-size: 11px;
            color: #666;
            margin-top: 5px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .last-updated {{
            font-size: 11px;
            color: #999;
            margin-top: 8px;
        }}
        
        /* Main headline */
        .main-headline {{
            text-align: center;
            padding: 20px 10px;
            border-bottom: 1px solid #ccc;
            margin-bottom: 15px;
        }}
        
        .main-headline a {{
            font-size: 28px;
            font-weight: bold;
            color: #cc0000;
            text-decoration: none;
            font-family: Georgia, serif;
            line-height: 1.2;
        }}
        
        .main-headline a:hover {{
            text-decoration: underline;
        }}
        
        .main-headline .source {{
            font-size: 11px;
            color: #666;
            margin-top: 8px;
            text-transform: uppercase;
        }}
        
        /* Top stories row */
        .top-row {{
            display: flex;
            justify-content: space-around;
            padding: 15px 0;
            border-bottom: 1px solid #ccc;
            margin-bottom: 15px;
        }}
        
        .top-story {{
            flex: 1;
            text-align: center;
            padding: 0 15px;
        }}
        
        .top-story a {{
            font-size: 18px;
            font-weight: bold;
            color: #000;
            text-decoration: none;
            font-family: Georgia, serif;
        }}
        
        .top-story a:hover {{
            color: #cc0000;
        }}
        
        .top-story .source {{
            font-size: 10px;
            color: #666;
            margin-top: 5px;
            text-transform: uppercase;
        }}
        
        /* Three column layout */
        .columns {{
            display: flex;
            gap: 20px;
        }}
        
        .column {{
            flex: 1;
        }}
        
        .column-header {{
            font-size: 12px;
            font-weight: bold;
            color: #cc0000;
            border-bottom: 2px solid #cc0000;
            padding-bottom: 5px;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        /* Story links */
        .story {{
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px dotted #ddd;
        }}
        
        .story:last-child {{
            border-bottom: none;
        }}
        
        .story a {{
            color: #0000cc;
            text-decoration: none;
            font-size: 13px;
            line-height: 1.3;
        }}
        
        .story a:hover {{
            color: #cc0000;
            text-decoration: underline;
        }}
        
        .story a.breaking {{
            color: #cc0000;
            font-weight: bold;
        }}
        
        .story a.exclusive {{
            color: #006600;
        }}
        
        .story .meta {{
            font-size: 10px;
            color: #888;
            margin-top: 3px;
        }}
        
        /* Sidebar */
        .sidebar-section {{
            background-color: #f5f5f5;
            padding: 10px;
            margin-top: 15px;
            border: 1px solid #ddd;
        }}
        
        .sidebar-section .column-header {{
            color: #333;
            border-bottom-color: #333;
        }}
        
        /* Footer */
        .footer {{
            text-align: center;
            padding: 20px;
            margin-top: 20px;
            border-top: 2px solid #000;
            font-size: 11px;
            color: #666;
        }}
        
        .footer a {{
            color: #0000cc;
        }}
        
        /* Mobile responsive */
        @media (max-width: 768px) {{
            .columns {{
                flex-direction: column;
            }}
            
            .top-row {{
                flex-direction: column;
                gap: 15px;
            }}
            
            .main-headline a {{
                font-size: 22px;
            }}
            
            .site-title {{
                font-size: 28px;
            }}
        }}
        
        /* Breaking news banner */
        .breaking-banner {{
            background-color: #cc0000;
            color: white;
            text-align: center;
            padding: 8px;
            font-weight: bold;
            font-size: 12px;
            letter-spacing: 2px;
            margin-bottom: 10px;
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.8; }}
        }}
        
        /* Category badges */
        .badge {{
            display: inline-block;
            font-size: 9px;
            padding: 2px 5px;
            border-radius: 2px;
            margin-right: 5px;
            text-transform: uppercase;
            font-weight: bold;
        }}
        
        .badge-china {{ background: #ff6b6b; color: white; }}
        .badge-policy {{ background: #4ecdc4; color: white; }}
        .badge-security {{ background: #f39c12; color: white; }}
        .badge-funding {{ background: #9b59b6; color: white; }}
        .badge-research {{ background: #3498db; color: white; }}
    </style>
</head>
<body>
    {breaking_banner}
    
    <header class="header">
        <a href="/" class="site-title">AI NEWS REPORT</a>
        <div class="tagline">Breaking AI News • Global Coverage • No Fluff</div>
        <div class="last-updated">Last Updated: {last_updated}</div>
    </header>
    
    <section class="main-headline">
        <a href="{main_story_url}" target="_blank">{main_headline}</a>
        <div class="source">{main_source}</div>
    </section>
    
    <section class="top-row">
        {top_stories_html}
    </section>
    
    <section class="columns">
        <div class="column">
            <div class="column-header">🔬 Labs & Products</div>
            {column1_html}
        </div>
        
        <div class="column">
            <div class="column-header">💼 Business & Policy</div>
            {column2_html}
        </div>
        
        <div class="column">
            <div class="column-header">🌍 Global & Research</div>
            {column3_html}
        </div>
    </section>
    
    <section class="sidebar-section">
        <div class="column-header">📡 More Headlines</div>
        <div class="columns">
            {sidebar_html}
        </div>
    </section>
    
    <footer class="footer">
        <p>AI NEWS REPORT • Curated by AI, for AI enthusiasts</p>
        <p>Stories aggregated from {source_count} sources worldwide</p>
        <p>Updated every 15 minutes • <a href="/about">About</a> • <a href="/sources">Sources</a></p>
    </footer>
</body>
</html>
"""

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_safe_url(url: str) -> bool:
    """Validate that a URL is safe to use in href (http/https only)"""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and parsed.netloc
    except Exception:
        return False


def safe_url(url: str) -> str:
    """Return URL if safe, otherwise return '#' placeholder"""
    return url if is_safe_url(url) else '#'


def format_story_link(story: Dict, show_source: bool = True, css_class: str = "") -> str:
    """Format a single story as an HTML link"""
    headline = escape(story.get('headline') or story.get('suggested_headline') or story['title'])
    url = safe_url(story['url'])
    source = escape(story.get('source', ''))
    
    # Add badges based on content
    badges = ""
    headline_lower = headline.lower()
    if 'china' in headline_lower or 'chinese' in headline_lower or 'alibaba' in headline_lower or 'deepseek' in headline_lower:
        badges += '<span class="badge badge-china">CHINA</span>'
    if 'senate' in headline_lower or 'trump' in headline_lower or 'regulation' in headline_lower or 'policy' in headline_lower:
        badges += '<span class="badge badge-policy">POLICY</span>'
    if 'security' in headline_lower or 'vulnerable' in headline_lower or 'attack' in headline_lower:
        badges += '<span class="badge badge-security">SECURITY</span>'
    if '$' in headline and ('m' in headline.lower() or 'million' in headline_lower or 'raises' in headline_lower):
        badges += '<span class="badge badge-funding">FUNDING</span>'
    
    class_attr = f' class="{css_class}"' if css_class else ''
    
    html = f'<div class="story">'
    if badges:
        html += badges
    html += f'<a href="{url}" target="_blank"{class_attr}>{headline}</a>'
    if show_source:
        html += f'<div class="meta">{source}</div>'
    html += '</div>'
    
    return html


def format_top_story(story: Dict) -> str:
    """Format a top story for the top row"""
    headline = escape(story.get('headline') or story.get('suggested_headline') or story['title'])
    url = safe_url(story['url'])
    source = escape(story.get('source', ''))
    
    return f'''<div class="top-story">
        <a href="{url}" target="_blank">{headline}</a>
        <div class="source">{source}</div>
    </div>'''


def generate_homepage(stories: List[Dict], output_path: Path = None) -> str:
    """Generate the full homepage HTML from scored stories"""
    
    if not stories or len(stories) < 5:
        raise ValueError("Need at least 5 stories to generate homepage")
    
    # Sort by score
    sorted_stories = sorted(stories, key=lambda x: x.get('total_score', x.get('score', 0)), reverse=True)
    
    # Assign stories to sections
    main_story = sorted_stories[0]
    top_stories = sorted_stories[1:3]
    column1_stories = sorted_stories[3:7]
    column2_stories = sorted_stories[7:11]
    column3_stories = sorted_stories[11:15]
    sidebar_stories = sorted_stories[15:24]
    
    # Generate HTML sections (with XSS protection)
    main_headline = escape(main_story.get('headline') or main_story.get('suggested_headline') or main_story['title'])
    main_url = safe_url(main_story['url'])
    main_source = escape(main_story.get('source', ''))
    
    top_stories_html = "\n".join([format_top_story(s) for s in top_stories])
    
    column1_html = "\n".join([format_story_link(s) for s in column1_stories])
    column2_html = "\n".join([format_story_link(s) for s in column2_stories])
    column3_html = "\n".join([format_story_link(s) for s in column3_stories])
    
    # Sidebar in two columns
    mid = len(sidebar_stories) // 2
    sidebar_left = "\n".join([format_story_link(s, show_source=False) for s in sidebar_stories[:mid]])
    sidebar_right = "\n".join([format_story_link(s, show_source=False) for s in sidebar_stories[mid:]])
    sidebar_html = f'<div class="column">{sidebar_left}</div><div class="column">{sidebar_right}</div>'
    
    # Breaking banner if top story is very fresh
    breaking_banner = ""
    if main_story.get('total_score', 0) >= 40:
        breaking_banner = '<div class="breaking-banner">⚡ BREAKING NEWS ⚡</div>'
    
    # Count unique sources
    source_count = len(set(s.get('source', '') for s in stories))
    
    # Generate final HTML
    html = HTML_TEMPLATE.format(
        breaking_banner=breaking_banner,
        last_updated=datetime.now().strftime("%B %d, %Y at %I:%M %p EST"),
        main_headline=main_headline,
        main_story_url=main_url,
        main_source=main_source,
        top_stories_html=top_stories_html,
        column1_html=column1_html,
        column2_html=column2_html,
        column3_html=column3_html,
        sidebar_html=sidebar_html,
        source_count=source_count
    )
    
    # Save to file if path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ Homepage generated: {output_path}")
    
    return html


def load_evaluation_results(json_path: Path) -> List[Dict]:
    """Load stories from evaluation results JSON"""
    with open(json_path) as f:
        data = json.load(f)
    
    # Combine all story lists
    stories = []
    
    # Add lead stories
    for s in data.get('lead_stories', []):
        stories.append(s)
    
    # Add publish stories
    for s in data.get('publish_stories', []):
        stories.append(s)
    
    # Add maybe stories (for sidebar)
    for s in data.get('maybe_stories', []):
        stories.append(s)
    
    return stories


def load_from_top20(json_path: Path) -> List[Dict]:
    """Load from the top_20_for_homepage array, fetching URLs from database"""
    with open(json_path) as f:
        data = json.load(f)
    
    top20 = data.get('top_20_for_homepage', [])
    
    # Get story IDs to look up
    story_ids = [item['story_id'] for item in top20]
    
    # Fetch URLs and sources from database
    db_stories = {}
    if DB_FILE.exists():
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            placeholders = ','.join(['?' for _ in story_ids])
            query = f"SELECT id, title, url, source, category FROM stories WHERE id IN ({placeholders})"
            rows = conn.execute(query, story_ids).fetchall()
            for row in rows:
                db_stories[row['id']] = dict(row)
    
    # Also build lookup from JSON data
    json_stories = {}
    for s in data.get('lead_stories', []):
        json_stories[s['story_id']] = s
    for s in data.get('publish_stories', []):
        json_stories[s['story_id']] = s
    for s in data.get('maybe_stories', []):
        json_stories[s['story_id']] = s
    
    # Build final list with headlines from top20, URLs from DB
    result = []
    for item in top20:
        story_id = item['story_id']
        
        story = {
            'story_id': story_id,
            'headline': item['headline'],
            'total_score': item['score'],
        }
        
        # Get URL and source from database
        if story_id in db_stories:
            story['url'] = db_stories[story_id]['url']
            story['source'] = db_stories[story_id]['source']
            story['title'] = db_stories[story_id]['title']
            story['category'] = db_stories[story_id]['category']
        elif story_id in json_stories:
            # Fallback to JSON data if URL is there
            js = json_stories[story_id]
            story['url'] = js.get('url', '#')
            story['source'] = js.get('source', 'Unknown')
            story['title'] = js.get('title', item['headline'])
        else:
            # Last resort
            story['url'] = '#'
            story['source'] = 'Unknown'
            story['title'] = item['headline']
        
        result.append(story)
    
    return result


def get_stories_from_db(min_score: float = 25, limit: int = 25) -> List[Dict]:
    """Get top stories directly from database (if scores are stored there)"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        
        query = """
            SELECT id as story_id, title, url, source, category, published, 
                   summary, score as total_score, headline
            FROM stories 
            WHERE score >= ?
            ORDER BY score DESC, published DESC
            LIMIT ?
        """
        
        rows = conn.execute(query, (min_score, limit)).fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate Drudge-style homepage")
    parser.add_argument("--input", "-i", type=Path, help="Evaluation results JSON file")
    parser.add_argument("--output", "-o", type=Path, default=OUTPUT_DIR / "index.html", 
                        help="Output HTML file path")
    parser.add_argument("--from-db", action="store_true", help="Load scored stories from database")
    parser.add_argument("--min-score", type=float, default=25, help="Minimum score (for --from-db)")
    
    args = parser.parse_args()
    
    # Load stories
    if args.input:
        print(f"📂 Loading stories from: {args.input}")
        stories = load_from_top20(args.input)
    elif args.from_db:
        print(f"📂 Loading stories from database (min score: {args.min_score})")
        stories = get_stories_from_db(min_score=args.min_score)
    else:
        print("❌ Please provide --input JSON file or use --from-db")
        return
    
    if not stories:
        print("❌ No stories found!")
        return
    
    print(f"📰 Found {len(stories)} stories")
    
    # Generate HTML
    html = generate_homepage(stories, args.output)
    
    print(f"\n🌐 Open in browser: file://{args.output.absolute()}")


if __name__ == "__main__":
    main()
