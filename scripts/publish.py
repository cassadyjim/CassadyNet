#!/usr/bin/env python3
"""
CassadyNet - Homepage Publisher
Generates the homepage HTML with story clusters and uploads to server.
"""

import sqlite3
import json
import re
import difflib
import subprocess
import os
import logging
import requests
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
FEEDS_FILE = BASE_DIR / "feeds" / "sources.json"
TEMPLATE_FILE = BASE_DIR / "scripts" / "homepage_template_v2.html"
TEMPLATE_FILE_FALLBACK = BASE_DIR / "scripts" / "homepage_template.html"
OUTPUT_DIR = BASE_DIR / "output"


def get_paywalled_sources() -> set:
    """Feed names flagged "paywall": true in feeds/sources.json"""
    if not FEEDS_FILE.exists():
        return set()
    with open(FEEDS_FILE) as f:
        data = json.load(f)
    return {f['name'] for f in data.get('feeds', []) if f.get('paywall')}


# feeds/sources.json's category slugs, mapped to the display labels used in
# the homepage "Our Sources" strip. Several small slugs are folded into one
# label so the footer doesn't end up with a dozen near-empty categories.
SOURCE_CATEGORY_LABELS = {
    'tech_news': 'Tech News',
    'research': 'Research & Academic',
    'ai_labs': 'AI Labs & Companies',
    'international': 'Global & International',
    'social': 'Community & Social',
    'business': 'Business & Finance',
    'finance': 'Business & Finance',
    'funding': 'Business & Finance',
    'newsletter': 'Newsletters',
    'ai_safety': 'AI Safety & Policy',
    'policy': 'AI Safety & Policy',
    'developer': 'Developer & Technical',
    'robotics': 'Robotics',
    'healthcare': 'Other',
}


def generate_sources_section() -> str:
    """Builds the dense "Our Sources" strip for the homepage footer directly
    from feeds/sources.json - the same file fetch_feeds.py reads - so this
    list can never drift out of sync with what's actually being pulled,
    the way a hand-copied list would."""
    if not FEEDS_FILE.exists():
        return ''
    with open(FEEDS_FILE) as f:
        data = json.load(f)
    feeds = [f for f in data.get('feeds', []) if f.get('enabled', True) and f.get('name') and f.get('url')]
    if not feeds:
        return ''

    grouped: dict = {}
    for feed in feeds:
        label = SOURCE_CATEGORY_LABELS.get(feed.get('category', ''), 'Other')
        grouped.setdefault(label, []).append(feed)

    categories_html = ""
    for label in sorted(grouped, key=lambda l: -len(grouped[l])):
        items_html = ""
        for feed in sorted(grouped[label], key=lambda f: f['name'].lower()):
            name = escape(feed['name'])
            parsed = urlparse(feed['url'])
            # Link to the outlet's homepage, not the raw RSS/XML feed URL -
            # sources.json only stores the feed endpoint, and the homepage
            # origin is always a valid, working link even when a per-feed
            # category-page URL isn't available to derive.
            link = safe_url(f"{parsed.scheme}://{parsed.netloc}") if parsed.scheme else '#'
            items_html += f'<div class="source-item"><a href="{link}" target="_blank">{name}</a></div>'
        categories_html += f"""
        <div class="source-category">
            <h3 class="source-category-title">{escape(label)}</h3>
            <div class="source-grid">{items_html}</div>
        </div>
        """

    # Numbers are computed live (not the static sources.html page's stale
    # "105+ sources / 15 categories / 12 countries") so this can't go stale
    # the way a hand-written stat would - "countries" is dropped entirely
    # since feeds/sources.json has no country field to back that claim.
    return f"""
    <section class="sources-section">
        <h2 class="sources-title">Our Sources</h2>
        <p class="sources-intro">CassadyNet aggregates AI news from {len(feeds)} sources worldwide. Stories are scored by AI for newsworthiness, and only the top stories make it to our homepage.</p>
        <div class="stats-bar">
            <div class="stat">
                <div class="stat-number">{len(feeds)}</div>
                <div class="stat-label">RSS Feeds</div>
            </div>
            <div class="stat">
                <div class="stat-number">{len(grouped)}</div>
                <div class="stat-label">Categories</div>
            </div>
            <div class="stat">
                <div class="stat-number">2x</div>
                <div class="stat-label">Daily Updates</div>
            </div>
        </div>
        {categories_html}
        <p class="sources-footer-link"><a href="/sources.html">Full list &amp; methodology →</a></p>
    </section>
    """


def dedupe_similar_stories(stories: list, title_threshold: float = 0.6) -> list:
    """Drop stories whose (normalized) title is a close match to one already kept.
    Stories should already be sorted best-first (e.g. by score) so the first of
    each near-duplicate group - the highest-scoring one - is the one kept."""
    kept = []
    kept_norm_titles = []
    for story in stories:
        norm = re.sub(r'[^a-z0-9 ]', '', (story.get('headline') or story['title']).lower())
        if any(difflib.SequenceMatcher(None, norm, seen).ratio() >= title_threshold for seen in kept_norm_titles):
            continue
        kept.append(story)
        kept_norm_titles.append(norm)
    return kept


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


# Thumbnails are a "just a few, like Drudge" accent, not a redesign to a photo
# grid — only "JUST IN" (< 3h old) stories get one, and only up to this many
# per homepage build, so a slow/blocked source can't stall the whole publish.
MAX_IMAGE_FETCHES = 6

OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    re.IGNORECASE,
)


def fetch_og_image(url: str, timeout: float = 4.0) -> str:
    """Best-effort fetch of a story's og:image/twitter:image for a 'JUST IN'
    thumbnail. Returns '' on any failure (blocked, no meta tag, timeout,
    non-HTML response) — callers must treat a missing image as normal, not
    an error."""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; CassadyNetBot/1.0)'},
            stream=True,
        )
        try:
            if resp.status_code != 200 or 'html' not in resp.headers.get('Content-Type', '').lower():
                return ''
            raw = resp.raw.read(200_000, decode_content=True)
        finally:
            resp.close()
        match = OG_IMAGE_RE.search(raw.decode('utf-8', errors='ignore'))
        if not match:
            return ''
        image_url = match.group(1) or match.group(2)
        return image_url if is_safe_url(image_url) else ''
    except Exception:
        return ''


class ImageBudget:
    """Caps the total number of og:image fetches across one homepage build,
    shared across clusters/top-row/headlines so the limit applies site-wide."""

    def __init__(self, limit: int = MAX_IMAGE_FETCHES):
        self.remaining = limit


def get_story_thumb_html(story: dict, is_fresh: bool, image_budget: 'ImageBudget' = None) -> str:
    """Returns an <img> tag for a fresh story's thumbnail, or '' if the story
    isn't fresh, the fetch budget is spent, or no image could be found."""
    if not is_fresh or image_budget is None or image_budget.remaining <= 0:
        return ''
    image_budget.remaining -= 1
    image_url = fetch_og_image(story.get('url', ''))
    if not image_url:
        return ''
    return f'<img class="story-thumb" src="{escape(image_url)}" alt="" loading="lazy" onerror="this.remove()">'


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


# No single category (e.g. "social" / Reddit+HN) may fill more than this
# share of the homepage slate, so high-volume sources can't crowd out
# lower-volume ones like ai_labs or research just by submitting more raw items.
MAX_CATEGORY_SHARE = 0.4


def get_top_stories(limit: int = 50) -> list:
    """Get top scored stories, excluding paywalled sources, capped per category"""
    conn = sqlite3.connect(DB_FILE)

    paywalled = get_paywalled_sources()
    placeholders = ",".join("?" * len(paywalled))
    exclude_clause = f"AND source NOT IN ({placeholders})" if paywalled else ""

    # Pull a wider candidate pool than `limit` so capping a category still
    # leaves enough other stories to fill the slate.
    rows = conn.execute(f"""
        SELECT id, title, url, source, score, headline, published, category
        FROM stories
        WHERE score >= 25
        AND published > datetime('now', '-72 hours')
        {exclude_clause}
        ORDER BY score DESC, published DESC
        LIMIT ?
    """, (*paywalled, limit * 4)).fetchall()

    conn.close()

    candidates = [
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
        for s in rows
    ]

    max_per_category = max(1, int(limit * MAX_CATEGORY_SHARE))
    selected = []
    category_counts = {}
    for story in candidates:
        if category_counts.get(story['category'], 0) >= max_per_category:
            continue
        selected.append(story)
        category_counts[story['category']] = category_counts.get(story['category'], 0) + 1
        if len(selected) >= limit:
            break

    # Backfill with whatever's left (ignoring the cap) if capping left the
    # slate short - a partially-capped homepage beats an incomplete one.
    if len(selected) < limit:
        chosen_ids = {s['id'] for s in selected}
        for story in candidates:
            if story['id'] in chosen_ids:
                continue
            selected.append(story)
            if len(selected) >= limit:
                break

    return selected


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


def generate_cluster_html(cluster: dict, analysis_url: str = None, analysis_type: str = "poll", image_budget: 'ImageBudget' = None) -> str:
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
        thumb = get_story_thumb_html(story, is_fresh, image_budget)

        if thumb:
            stories_html += f"""
            <div class="cluster-story">
                <div class="story-row">
                    {thumb}
                    <div class="story-text">
                        <a href="{url}" target="_blank">{just_in}{title}</a>
                        <span class="cluster-story-meta">{source} · <span class="{time_class}">{time_ago}</span></span>
                    </div>
                </div>
            </div>
        """
        else:
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
            <h3 class="cluster-topic">{topic}</h3>
            <div class="cluster-count">{len(stories)} stories</div>
        </div>
        <div class="cluster-stories">
            {stories_html}
        </div>
        {analysis_button}
    </div>
    """
    
    return html


def generate_story_html(story: dict, image_budget: 'ImageBudget' = None) -> str:
    """Generate HTML for a single story (with XSS protection)"""
    title = escape(story['headline'] or story['title'])
    url = safe_url(story['url'])
    source = escape(story['source'])
    time_ago, is_fresh = format_time_ago(story.get('published', ''))

    just_in = '<span class="just-in-badge">JUST IN</span>' if is_fresh else ''
    time_class = 'time-fresh' if is_fresh else ''
    thumb = get_story_thumb_html(story, is_fresh, image_budget)

    if thumb:
        return f"""
        <div class="story-item">
            <div class="story-row">
                {thumb}
                <div class="story-text">
                    <a href="{url}" target="_blank">{just_in}{title}</a>
                    <span class="story-meta">{source} · <span class="{time_class}">{time_ago}</span></span>
                </div>
            </div>
        </div>
    """
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

    # Strip paywalled stories out of the featured clusters too
    paywalled_sources = get_paywalled_sources()
    for cluster in clusters:
        cluster['stories'] = [s for s in cluster.get('stories', []) if s.get('source') not in paywalled_sources]
        cluster['story_count'] = len(cluster['stories'])

    analysis_index = load_analysis_index()

    logger.info(f"Loaded {len(clusters)} clusters from story_clusters.json")

    # Always pull unclustered stories fresh from the DB so they never go stale.
    # story_clusters.json's unclustered list can be days old if the DB cache
    # in GitHub Actions failed; querying the DB directly gives current data.
    db_stories = get_top_stories(60)

    # Remove any stories that are already covered by a cluster
    cluster_urls = {s['url'] for c in clusters for s in c.get('stories', [])}
    unclustered = [s for s in db_stories if s.get('url') not in cluster_urls]

    # If the DB has nothing fresh (empty or all stale), fall back to JSON
    if not unclustered:
        unclustered = cluster_data.get('unclustered', [])
        logger.info(f"  DB returned no fresh stories — falling back to story_clusters.json unclustered list")
    else:
        logger.info(f"  Using {len(unclustered)} fresh stories from DB")

    # The JSON fallback above can predate the paywall list, so filter here too
    unclustered = [s for s in unclustered if s.get('source') not in paywalled_sources]

    # Drop near-duplicate coverage of the same story (keeps the highest-scored copy)
    before_dedup = len(unclustered)
    unclustered = dedupe_similar_stories(unclustered)
    if before_dedup != len(unclustered):
        logger.info(f"  Deduplicated {before_dedup - len(unclustered)} near-duplicate stories")
    
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
    
    # Find active polls that must stay visible (under 24 hours old)
    protected_polls = []
    for poll in active_polls:
        created_at = poll.get('created_at', '')
        if created_at:
            try:
                poll_time = datetime.fromisoformat(created_at)
                age_hours = (now - poll_time).total_seconds() / 3600
                if age_hours < 24:
                    protected_polls.append(poll)
                    logger.info(f"  Protected topic (age {age_hours:.1f}h): {poll['topic']}")
            except Exception as e:
                logger.warning(f"  Could not parse date for poll: {e}")

    # Build final cluster list: protected first, then fill with new
    final_clusters = []

    for poll in protected_polls:
        protected_topic = poll['topic']
        matched = False

        # Try to find the topic in the freshly-generated clusters
        for cluster in clusters:
            if (cluster['topic'] == protected_topic
                    or protected_topic.lower() in cluster['topic'].lower()
                    or cluster['topic'].lower() in protected_topic.lower()):
                if cluster not in final_clusters:
                    final_clusters.append(cluster)
                    logger.info(f"  Added protected cluster (matched): {cluster['topic']}")
                matched = True
                break

        # If the clustering algorithm renamed or dropped this topic, reconstruct
        # the cluster from the stories we stored in active_polls.json
        if not matched:
            stored_stories = poll.get('cluster_stories', [])
            if stored_stories:
                stub = {
                    'topic': protected_topic,
                    'description': poll.get('description', ''),
                    'stories': stored_stories,
                    'story_count': len(stored_stories)
                }
                final_clusters.append(stub)
                logger.info(f"  Reconstructed protected cluster from stored stories: {protected_topic}")
            else:
                logger.warning(f"  Protected topic '{protected_topic}' not found and no stored stories — skipping")

    # Fill remaining slots with highest-scoring new clusters
    for cluster in clusters:
        if len(final_clusters) >= 2:
            break
        if cluster not in final_clusters:
            final_clusters.append(cluster)
            logger.info(f"  Added new cluster: {cluster['topic']}")

    logger.info(f"Final clusters to display: {len(final_clusters)}")

    # Last-resort fallback: use whatever clusters were generated
    if not final_clusters and clusters:
        final_clusters = clusters[:2]
        logger.info(f"  Fallback: using original clusters")
    
    # If no clusters, fall back to regular story list
    if not final_clusters and not unclustered:
        all_stories = get_top_stories(50)
        unclustered = all_stories
    
    # Shared across the whole page so "JUST IN" thumbnails stay a rare accent
    # rather than a per-section budget that could add up to dozens of fetches.
    image_budget = ImageBudget()

    # Build clusters HTML - LIMIT TO 2 CLUSTERS MAX
    clusters_html = ""
    if final_clusters:
        clusters_html = '<section class="clusters-section"><div class="clusters-grid">'
        for cluster in final_clusters[:2]:  # Only top 2 clusters
            analysis_url, analysis_type = get_analysis_info(cluster['topic'], analysis_index)
            clusters_html += generate_cluster_html(cluster, analysis_url, analysis_type, image_budget)
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
        thumb = get_story_thumb_html(story, is_fresh, image_budget)

        if thumb:
            top_html += f"""
            <div class="top-story">
                <div class="story-row">
                    {thumb}
                    <div class="story-text">
                        <a href="{url}" target="_blank">{just_in}{title}</a>
                        <span class="story-meta">{source} · <span class="{time_class}">{time_ago}</span></span>
                    </div>
                </div>
            </div>
        """
        else:
            top_html += f"""
            <div class="top-story">
                <a href="{url}" target="_blank">{just_in}{title}</a>
                <span class="story-meta">{source} · <span class="{time_class}">{time_ago}</span></span>
            </div>
        """

    # Only show the "Top Stories" header when there's actually a row to label
    top_stories_section = ""
    if top_html:
        top_stories_section = f"""
    <h2 class="top-row-header">Top Stories</h2>
    <section class="top-row">
        {top_html}
    </section>
    """

    # All remaining stories (single grid, no categories)
    all_stories_html = ""
    for story in remaining_stories[3:30]:
        all_stories_html += generate_story_html(story, image_budget)

    # Replace placeholders
    html = template
    html = html.replace('{{MAIN_HEADLINE}}', main_headline)
    html = html.replace('{{MAIN_URL}}', main_url)
    html = html.replace('{{MAIN_SOURCE}}', main_source)
    html = html.replace('{{MAIN_TIME}}', main_time)
    html = html.replace('{{MAIN_TIME_CLASS}}', main_time_class)
    html = html.replace('{{TOP_STORIES_SECTION}}', top_stories_section)
    html = html.replace('{{STORY_CLUSTERS}}', clusters_html)
    html = html.replace('{{ALL_STORIES}}', all_stories_html)
    html = html.replace('{{SOURCES_SECTION}}', generate_sources_section())
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

    # Always log stdout so diagnostics and file lists are visible
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            logger.info(line)

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
    
    def run_step(label, cmd):
        """Run a subprocess step and log clearly if it fails."""
        logger.info(f"Running: {' '.join(str(c) for c in cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            logger.error(f"❌ {label} FAILED with exit code {result.returncode}")
        else:
            logger.info(f"✅ {label} completed successfully")
        return result.returncode

    # Step 1: Fetch feeds
    if not args.skip_fetch and not args.local_only:
        logger.info("Step 1: Fetching feeds...")
        fetch_script = BASE_DIR / "scripts" / "fetch_feeds.py"
        if fetch_script.exists():
            run_step("Fetch feeds", ["python3", str(fetch_script)])

    # Step 2: Score stories
    if not args.skip_score and not args.local_only:
        logger.info("Step 2: Scoring stories...")
        score_script = BASE_DIR / "scripts" / "score_stories.py"
        if score_script.exists():
            rc = run_step("Score stories", ["python3", str(score_script), "--hours", "72", "--limit", "100"])
            if rc != 0:
                logger.error("  → Scoring failed. Check that ANTHROPIC_API_KEY is set in GitHub Secrets.")

    # Step 3: Cluster stories
    if not args.skip_cluster:
        logger.info("Step 3: Clustering stories...")
        cluster_script = BASE_DIR / "scripts" / "cluster_stories.py"
        if cluster_script.exists():
            run_step("Cluster stories", ["python3", str(cluster_script), "--hours", "72"])

    # Step 4: Generate analysis for new clusters
    if not args.skip_analysis:
        logger.info("Step 4: Generating analysis articles...")
        analysis_script = BASE_DIR / "scripts" / "generate_analysis.py"
        if analysis_script.exists():
            run_step("Generate analysis", ["python3", str(analysis_script)])
    
    # Step 5: Generate homepage
    logger.info("Step 5: Generating homepage...")
    generate_homepage()
    
    # Step 6: Generate previous polls page
    logger.info("Step 6: Generating previous polls page...")
    polls_script = BASE_DIR / "scripts" / "generate_polls_page.py"
    if polls_script.exists():
        run_step("Generate polls page", ["python3", str(polls_script)])

    # Step 7: Generate RSS feed
    logger.info("Step 7: Generating RSS feed...")
    rss_script = BASE_DIR / "scripts" / "generate_rss.py"
    if rss_script.exists():
        run_step("Generate RSS", ["python3", str(rss_script)])

    # Step 8: Generate sitemap
    logger.info("Step 8: Generating sitemap...")
    sitemap_script = BASE_DIR / "scripts" / "generate_sitemap.py"
    if sitemap_script.exists():
        run_step("Generate sitemap", ["python3", str(sitemap_script)])
    
    # Step 9: Copy robots.txt if it exists
    robots_src = BASE_DIR / "scripts" / "robots.txt"
    robots_dst = OUTPUT_DIR / "robots.txt"
    if robots_src.exists() and not robots_dst.exists():
        import shutil
        shutil.copy(robots_src, robots_dst)
        logger.info("Copied robots.txt to output")

    # Step 9b: Copy hand-maintained static pages (tracked in git, unlike output/)
    static_dir = BASE_DIR / "scripts" / "static"
    if static_dir.exists():
        import shutil
        for static_file in static_dir.glob("*.html"):
            shutil.copy(static_file, OUTPUT_DIR / static_file.name)
        logger.info("Copied static pages (about/sources/privacy/consent) to output")

    # Step 10: Upload
    if not args.skip_upload and not args.local_only:
        logger.info("Step 10: Uploading to server...")
        upload_site()
    
    logger.info("=" * 60)
    logger.info("Done!")


if __name__ == "__main__":
    main()
