#!/usr/bin/env python3
"""
CassadyNet - Homepage Publisher
Generates the homepage HTML with story clusters and uploads to server.
"""

import sqlite3
import json
import subprocess
import os
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from html import escape
from pathlib import Path
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_FILE = BASE_DIR / "data" / "stories.db"
CLUSTERS_FILE = BASE_DIR / "data" / "story_clusters.json"
ANALYSIS_INDEX_FILE = BASE_DIR / "data" / "analysis_index.json"
TEMPLATE_FILE = BASE_DIR / "scripts" / "homepage_template_v2.html"
TEMPLATE_FILE_FALLBACK = BASE_DIR / "scripts" / "homepage_template.html"
OUTPUT_DIR = BASE_DIR / "output"


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


def load_clusters() -> dict:
    """Load story clusters"""
    if CLUSTERS_FILE.exists():
        with open(CLUSTERS_FILE, 'r') as f:
            return json.load(f)
    return {'clusters': [], 'unclustered': []}


def load_analysis_index() -> dict:
    """Load analysis index"""
    if ANALYSIS_INDEX_FILE.exists():
        with open(ANALYSIS_INDEX_FILE, 'r') as f:
            return json.load(f)
    return {'analyses': []}


def get_analysis_info(topic: str, analysis_index: dict) -> tuple:
    """Get analysis URL and type for a topic. Returns (url, type)"""
    for a in analysis_index.get('analyses', []):
        if a['topic'] == topic:
            return a.get('url'), a.get('analysis_type', 'poll')
    return None, None


def get_top_stories(limit: int = 50) -> list:
    """Get top scored stories"""
    conn = sqlite3.connect(DB_FILE)
    
    stories = conn.execute("""
        SELECT id, title, url, source, score, headline, published, category
        FROM stories
        WHERE score >= 25
        AND published > datetime('now', '-48 hours')
        ORDER BY score DESC, published DESC
        LIMIT ?
    """, (limit,)).fetchall()
    
    conn.close()
    
    return [
        {
            'id': s[0],
            'title': s[1],
            'url': s[2],
            'source': s[3],
            'score': s[4],
            'headline': s[5],
            'published': s[6],
            'category': s[7]
        }
        for s in stories
    ]


def format_time_ago(published: str) -> tuple:
    """Format published time as relative time. Returns (time_str, is_fresh)"""
    if not published:
        return "", False
    
    try:
        pub_dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        diff = now - pub_dt
        
        hours = int(diff.total_seconds() / 3600)
        minutes = int(diff.total_seconds() / 60)
        
        is_fresh = hours < 3  # Less than 3 hours old
        
        if hours < 1:
            return f"{minutes}m ago", is_fresh
        elif hours < 24:
            return f"{hours}h ago", is_fresh
        else:
            days = int(hours / 24)
            return f"{days}d ago", is_fresh
    except (ValueError, TypeError, AttributeError):
        return "", False


def generate_cluster_html(cluster: dict, analysis_url: str = None, analysis_type: str = "poll") -> str:
    """Generate HTML for a story cluster"""

    topic = escape(cluster['topic'])
    stories = cluster['stories']

    # Build stories HTML (with XSS protection)
    stories_html = ""
    for story in stories[:5]:
        title = escape(story['headline'] or story['title'])
        url = safe_url(story['url'])
        source = escape(story['source'])
        time_ago, is_fresh = format_time_ago(story.get('published', ''))

        just_in = '<span class="just-in-badge">JUST IN</span>' if is_fresh else ''
        time_class = 'time-fresh' if is_fresh else ''

        stories_html += f"""
            <div class="cluster-story">
                <a href="{url}" target="_blank">{just_in}{title}</a>
                <span class="cluster-story-meta">{source} · <span class="{time_class}">{time_ago}</span></span>
            </div>
        """
    
    # Analysis button - "Poll" for debates, "Summary" for news summaries
    analysis_button = ""
    if analysis_url:
        button_label = "Poll" if analysis_type == "poll" else "Summary"
        button_icon = "📊" if analysis_type == "poll" else "📄"
        analysis_button = f"""
            <a href="{analysis_url}" class="analysis-btn">
                <span class="analysis-icon">{button_icon}</span> {button_label}
            </a>
        """
    
    html = f"""
    <div class="story-cluster">
        <div class="cluster-header">
            <div class="cluster-topic">{topic}</div>
            <div class="cluster-count">{len(stories)} stories</div>
        </div>
        <div class="cluster-stories">
            {stories_html}
        </div>
        {analysis_button}
    </div>
    """
    
    return html


def generate_story_html(story: dict) -> str:
    """Generate HTML for a single story (with XSS protection)"""
    title = escape(story['headline'] or story['title'])
    url = safe_url(story['url'])
    source = escape(story['source'])
    time_ago, is_fresh = format_time_ago(story.get('published', ''))

    just_in = '<span class="just-in-badge">JUST IN</span>' if is_fresh else ''
    time_class = 'time-fresh' if is_fresh else ''

    return f"""
        <div class="story-item">
            <a href="{url}" target="_blank">{just_in}{title}</a>
            <span class="story-meta">{source} · <span class="{time_class}">{time_ago}</span></span>
        </div>
    """


def generate_homepage():
    """Generate the homepage HTML"""
    
    logger.info("Generating homepage...")
    
    # Load template
    template_file = TEMPLATE_FILE if TEMPLATE_FILE.exists() else TEMPLATE_FILE_FALLBACK
    with open(template_file, 'r') as f:
        template = f.read()
    
    # Load clusters and analysis index
    cluster_data = load_clusters()
    clusters = cluster_data.get('clusters', [])
    unclustered = cluster_data.get('unclustered', [])
    
    analysis_index = load_analysis_index()
    
    logger.info(f"Loaded {len(clusters)} clusters from story_clusters.json")
    
    # Load active polls to ensure 24-hour minimum display
    active_polls_file = BASE_DIR / "data" / "active_polls.json"
    active_polls = []
    if active_polls_file.exists():
        with open(active_polls_file, 'r') as f:
            active_polls_data = json.load(f)
            active_polls = active_polls_data.get('polls', [])
    
    logger.info(f"Loaded {len(active_polls)} active polls")
    
    # Merge clusters: prioritize active polls under 24 hours, then new clusters
    from datetime import datetime, timedelta
    now = datetime.now()
    
    # Find active polls that must stay (under 24 hours old)
    protected_topics = []
    for poll in active_polls:
        created_at = poll.get('created_at', '')
        if created_at:
            try:
                poll_time = datetime.fromisoformat(created_at)
                age_hours = (now - poll_time).total_seconds() / 3600
                if age_hours < 24:
                    protected_topics.append(poll['topic'])
                    logger.info(f"  Protected topic (age {age_hours:.1f}h): {poll['topic']}")
            except Exception as e:
                logger.warning(f"  Could not parse date for poll: {e}")
    
    # Build final cluster list: protected first, then fill with new
    final_clusters = []
    
    # Add protected clusters first (try fuzzy matching)
    for protected_topic in protected_topics:
        for cluster in clusters:
            # Exact match or partial match
            if cluster['topic'] == protected_topic or protected_topic.lower() in cluster['topic'].lower() or cluster['topic'].lower() in protected_topic.lower():
                if cluster not in final_clusters:
                    final_clusters.append(cluster)
                    logger.info(f"  Added protected cluster: {cluster['topic']}")
                    break
    
    # Fill remaining slots with highest-scoring new clusters
    for cluster in clusters:
        if len(final_clusters) >= 2:
            break
        if cluster not in final_clusters:
            final_clusters.append(cluster)
            logger.info(f"  Added new cluster: {cluster['topic']}")
    
    logger.info(f"Final clusters to display: {len(final_clusters)}")
    
    # If no final_clusters but we have original clusters, use those directly
    if not final_clusters and clusters:
        final_clusters = clusters[:2]
        logger.info(f"  Fallback: using original clusters")
    
    # If no clusters, fall back to regular story list
    if not final_clusters and not unclustered:
        all_stories = get_top_stories(50)
        unclustered = all_stories
    
    # Build clusters HTML - LIMIT TO 2 CLUSTERS MAX
    clusters_html = ""
    if final_clusters:
        clusters_html = '<section class="clusters-section"><div class="clusters-grid">'
        for cluster in final_clusters[:2]:  # Only top 2 clusters
            analysis_url, analysis_type = get_analysis_info(cluster['topic'], analysis_index)
            clusters_html += generate_cluster_html(cluster, analysis_url, analysis_type)
        clusters_html += '</div></section>'
        logger.info(f"Generated HTML for {min(len(final_clusters), 2)} clusters")
    
    # Get main headline (top unclustered story)
    main_story = None
    if unclustered:
        main_story = unclustered[0]
        remaining_stories = unclustered[1:]
    else:
        remaining_stories = []
    
    if main_story:
        main_headline = escape(main_story['headline'] or main_story['title'])
        main_url = safe_url(main_story['url'])
        main_source = escape(main_story['source'])
        main_time, main_is_fresh = format_time_ago(main_story.get('published', ''))
        main_time_class = 'time-fresh' if main_is_fresh else ''
    else:
        main_headline = "Welcome to CassadyNet"
        main_url = "#"
        main_source = ""
        main_time = ""
        main_time_class = ""
    
    # Top stories row (next 3 after main) - with XSS protection
    top_stories = remaining_stories[:3]
    top_html = ""
    for story in top_stories:
        title = escape(story['headline'] or story['title'])
        url = safe_url(story['url'])
        source = escape(story['source'])
        time_ago, is_fresh = format_time_ago(story.get('published', ''))

        just_in = '<span class="just-in-badge">JUST IN</span>' if is_fresh else ''
        time_class = 'time-fresh' if is_fresh else ''

        top_html += f"""
            <div class="top-story">
                <a href="{url}" target="_blank">{just_in}{title}</a>
                <span class="story-meta">{source} · <span class="{time_class}">{time_ago}</span></span>
            </div>
        """
    
    # All remaining stories (single grid, no categories)
    all_stories_html = ""
    for story in remaining_stories[3:30]:
        all_stories_html += generate_story_html(story)
    
    # Replace placeholders
    html = template
    html = html.replace('{{MAIN_HEADLINE}}', main_headline)
    html = html.replace('{{MAIN_URL}}', main_url)
    html = html.replace('{{MAIN_SOURCE}}', main_source)
    html = html.replace('{{MAIN_TIME}}', main_time)
    html = html.replace('{{MAIN_TIME_CLASS}}', main_time_class)
    html = html.replace('{{TOP_STORIES}}', top_html)
    html = html.replace('{{STORY_CLUSTERS}}', clusters_html)
    html = html.replace('{{ALL_STORIES}}', all_stories_html)
    utc_now = datetime.now(timezone.utc)
    et_fallback = utc_now.astimezone(ZoneInfo('America/New_York')).strftime('%I:%M %p ET')
    html = html.replace('{{LAST_UPDATED}}', f'<span class="local-time" data-utc="{utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")}">{et_fallback}</span>')
    
    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "index.html"
    with open(output_file, 'w') as f:
        f.write(html)
    
    logger.info(f"Homepage saved to {output_file}")
    logger.info(f"  Clusters: {len(clusters)}")
    logger.info(f"  Unclustered stories: {len(unclustered)}")
    
    return output_file


def upload_site():
    """Upload site files via SFTP"""
    logger.info("Uploading to server...")
    
    script_path = BASE_DIR / "scripts" / "upload_sftp.py"
    result = subprocess.run(
        ["python3", str(script_path)],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info("Upload complete!")
    else:
        logger.error(f"Upload failed: {result.stderr}")
    
    return result.returncode == 0


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate and publish CassadyNet homepage")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip fetching new stories")
    parser.add_argument("--skip-score", action="store_true", help="Skip scoring stories")
    parser.add_argument("--skip-cluster", action="store_true", help="Skip clustering stories")
    parser.add_argument("--skip-analysis", action="store_true", help="Skip generating analysis")
    parser.add_argument("--skip-upload", action="store_true", help="Skip uploading to server")
    parser.add_argument("--local-only", action="store_true", help="Generate locally, don't upload")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("CassadyNet Publisher")
    logger.info("=" * 60)
    
    # Step 1: Fetch feeds
    if not args.skip_fetch and not args.local_only:
        logger.info("Step 1: Fetching feeds...")
        fetch_script = BASE_DIR / "scripts" / "fetch_feeds.py"
        if fetch_script.exists():
            subprocess.run(["python3", str(fetch_script)])
    
    # Step 2: Score stories
    if not args.skip_score and not args.local_only:
        logger.info("Step 2: Scoring stories...")
        score_script = BASE_DIR / "scripts" / "score_stories.py"
        if score_script.exists():
            subprocess.run(["python3", str(score_script), "--hours", "24", "--limit", "30"])
    
    # Step 3: Cluster stories
    if not args.skip_cluster:
        logger.info("Step 3: Clustering stories...")
        cluster_script = BASE_DIR / "scripts" / "cluster_stories.py"
        if cluster_script.exists():
            subprocess.run(["python3", str(cluster_script), "--hours", "48"])
    
    # Step 4: Generate analysis for new clusters
    if not args.skip_analysis:
        logger.info("Step 4: Generating analysis articles...")
        analysis_script = BASE_DIR / "scripts" / "generate_analysis.py"
        if analysis_script.exists():
            subprocess.run(["python3", str(analysis_script)])
    
    # Step 5: Generate homepage
    logger.info("Step 5: Generating homepage...")
    generate_homepage()
    
    # Step 6: Generate previous polls page
    logger.info("Step 6: Generating previous polls page...")
    polls_script = BASE_DIR / "scripts" / "generate_polls_page.py"
    if polls_script.exists():
        subprocess.run(["python3", str(polls_script)])
    
    # Step 7: Generate RSS feed
    logger.info("Step 7: Generating RSS feed...")
    rss_script = BASE_DIR / "scripts" / "generate_rss.py"
    if rss_script.exists():
        subprocess.run(["python3", str(rss_script)])
    
    # Step 8: Generate sitemap
    logger.info("Step 8: Generating sitemap...")
    sitemap_script = BASE_DIR / "scripts" / "generate_sitemap.py"
    if sitemap_script.exists():
        subprocess.run(["python3", str(sitemap_script)])
    
    # Step 9: Copy robots.txt if it exists
    robots_src = BASE_DIR / "scripts" / "robots.txt"
    robots_dst = OUTPUT_DIR / "robots.txt"
    if robots_src.exists() and not robots_dst.exists():
        import shutil
        shutil.copy(robots_src, robots_dst)
        logger.info("Copied robots.txt to output")
    
    # Step 10: Upload
    if not args.skip_upload and not args.local_only:
        logger.info("Step 10: Uploading to server...")
        upload_site()
    
    logger.info("=" * 60)
    logger.info("Done!")


if __name__ == "__main__":
    main()
