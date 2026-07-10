#!/usr/bin/env python3
"""
CassadyNet - Story Clustering
Groups related high-scoring stories by topic.
Only clusters stories that are ALREADY high-ranked (score >= 25).
Deduplicates similar stories - only unique angles/sources.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

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

# Minimum stories to form a cluster (must be truly different stories)
MIN_CLUSTER_SIZE = 2
TARGET_CLUSTERS = 2
MIN_SCORE = 25


def get_top_stories(hours: int = 48, min_score: int = MIN_SCORE) -> list:
    """Get top scored stories from recent hours"""
    conn = sqlite3.connect(DB_FILE)
    
    stories = conn.execute("""
        SELECT id, title, url, source, summary, published, score, headline
        FROM stories
        WHERE score >= ?
        AND published > datetime('now', ? || ' hours')
        ORDER BY score DESC
        LIMIT 100
    """, (min_score, f"-{hours}")).fetchall()
    
    conn.close()
    
    return [
        {
            'id': s[0],
            'title': s[1],
            'url': s[2],
            'source': s[3],
            'summary': s[4],
            'published': s[5],
            'score': s[6],
            'headline': s[7]
        }
        for s in stories
    ]


def cluster_stories_with_ai(stories: list) -> dict:
    """Use Claude to identify topic clusters"""
    
    if not stories:
        return {'clusters': [], 'unclustered': []}
    
    client = Anthropic()
    
    # Prepare story list for AI - limit to top 50 to avoid token issues
    top_stories = stories[:50]
    story_list = "\n".join([
        f"[{i}] (score:{s['score']}, source:{s['source']}) {s['headline'] or s['title']}"
        for i, s in enumerate(top_stories)
    ])
    
    prompt = f"""Analyze these AI news headlines and group them into 2 topic clusters.

GOAL: Find the 2 BIGGEST news themes from these headlines.

RULES:
1. A cluster = 2 or more stories about the SAME GENERAL TOPIC
2. Stories about the same company/product/issue belong together
3. Pick the 2 most significant/newsworthy topic themes
4. Each cluster should have 2-5 stories

Examples of valid clusters:
- "Nvidia China Chips" theme: tariffs, export rules, China response
- "OpenAI Business" theme: spending, ads, restructuring  
- "AI Regulation" theme: EU rules, US policy, lawsuits

Stories:
{story_list}

Find 2 clusters. Respond with ONLY valid JSON, no other text:
{{
    "clusters": [
        {{
            "topic": "Short topic name",
            "description": "One sentence on why this matters",
            "story_indices": [0, 3, 7]
        }},
        {{
            "topic": "Second topic name",
            "description": "One sentence on why this matters", 
            "story_indices": [1, 5, 9]
        }}
    ],
    "unclustered_indices": [2, 4, 6, 8]
}}

You MUST return exactly 2 clusters with at least 2 stories each."""

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse response
    response_text = response.content[0].text
    logger.info(f"AI Response: {response_text[:500]}...")
    
    # Extract JSON from response
    try:
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        json_str = response_text[start:end]
        result = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse AI response: {e}")
        logger.error(f"Response: {response_text}")
        return {'clusters': [], 'unclustered': stories}
    
    # Build final clusters with full story data
    clusters = []
    used_indices = set()
    
    for cluster in result.get('clusters', []):
        indices = cluster.get('story_indices', [])
        
        if len(indices) >= MIN_CLUSTER_SIZE:
            cluster_stories = []
            for idx in indices:
                if 0 <= idx < len(top_stories) and idx not in used_indices:
                    cluster_stories.append(top_stories[idx])
                    used_indices.add(idx)
            
            if len(cluster_stories) >= MIN_CLUSTER_SIZE:
                clusters.append({
                    'topic': cluster['topic'],
                    'description': cluster.get('description', ''),
                    'stories': sorted(cluster_stories, key=lambda x: x['score'], reverse=True),
                    'top_score': max(s['score'] for s in cluster_stories),
                    'story_count': len(cluster_stories)
                })
    
    # Sort clusters by top score
    clusters.sort(key=lambda x: x['top_score'], reverse=True)
    
    # Collect unclustered stories
    unclustered = [
        s for i, s in enumerate(top_stories) 
        if i not in used_indices
    ]
    
    # Add remaining stories not in top 50
    unclustered.extend(stories[50:])
    
    return {
        'clusters': clusters,
        'unclustered': unclustered,
        'generated_at': datetime.now().isoformat()
    }


def save_clusters(cluster_data: dict):
    """Save cluster data to JSON file"""
    CLUSTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CLUSTERS_FILE, 'w') as f:
        json.dump(cluster_data, f, indent=2)
    logger.info(f"Saved clusters to {CLUSTERS_FILE}")


def load_clusters() -> dict:
    """Load existing cluster data"""
    if CLUSTERS_FILE.exists():
        with open(CLUSTERS_FILE, 'r') as f:
            return json.load(f)
    return {'clusters': [], 'unclustered': []}


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Cluster related stories by topic")
    parser.add_argument("--hours", type=int, default=48, help="Hours of stories to analyze")
    parser.add_argument("--min-score", type=int, default=MIN_SCORE, help="Minimum story score")
    parser.add_argument("--dry-run", action="store_true", help="Show results without saving")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("CassadyNet Story Clustering")
    logger.info("=" * 60)
    
    # Get top stories
    stories = get_top_stories(hours=args.hours, min_score=args.min_score)
    logger.info(f"Found {len(stories)} high-ranked stories (score >= {args.min_score}, last {args.hours}h)")
    
    if not stories:
        logger.info("No stories to cluster")
        return
    
    # Cluster with AI
    logger.info("Analyzing stories for topic clusters...")
    cluster_data = cluster_stories_with_ai(stories)
    
    # Load active polls to check for 24-hour protection
    active_polls_file = BASE_DIR / "data" / "active_polls.json"
    archived_polls_file = BASE_DIR / "data" / "archived_polls.json"
    protected_clusters = []
    cooldown_topics = []  # Topics that can't be featured for 7 days
    
    if active_polls_file.exists():
        with open(active_polls_file, 'r') as f:
            active_polls_data = json.load(f)
            active_polls = active_polls_data.get('polls', [])
        
        now = datetime.now()
        for poll in active_polls:
            created_at = poll.get('created_at', '')
            if created_at:
                try:
                    poll_time = datetime.fromisoformat(created_at)
                    age_hours = (now - poll_time).total_seconds() / 3600
                    if age_hours < 24:
                        protected_clusters.append(poll['topic'])
                        logger.info(f"  Protected cluster (age {age_hours:.1f}h): {poll['topic']}")
                except:
                    pass
    
    # Load archived polls to check for 7-day cooldown
    if archived_polls_file.exists():
        with open(archived_polls_file, 'r') as f:
            archived_polls_data = json.load(f)
            archived_polls = archived_polls_data.get('polls', [])
        
        now = datetime.now()
        for poll in archived_polls:
            archived_at = poll.get('archived_at', '')
            if archived_at:
                try:
                    archive_time = datetime.fromisoformat(archived_at)
                    age_days = (now - archive_time).total_seconds() / 86400  # seconds in a day
                    if age_days < 7:
                        cooldown_topics.append(poll['topic'])
                        logger.info(f"  Cooldown topic (archived {age_days:.1f} days ago): {poll['topic']}")
                except:
                    pass
    
    # Load existing clusters to preserve protected ones
    existing_data = load_clusters()
    existing_clusters = existing_data.get('clusters', [])
    
    # Build final cluster list: keep protected clusters, add new ones
    final_clusters = []
    
    # First, keep any existing clusters that are protected
    for existing in existing_clusters:
        for protected_topic in protected_clusters:
            if existing['topic'] == protected_topic or protected_topic.lower() in existing['topic'].lower() or existing['topic'].lower() in protected_topic.lower():
                if existing not in final_clusters:
                    final_clusters.append(existing)
                    logger.info(f"  Keeping protected cluster: {existing['topic']}")
                break
    
    # Then add new clusters to fill up to 2 slots (but skip cooldown topics)
    for new_cluster in cluster_data['clusters']:
        if len(final_clusters) >= 2:
            break
        # Check if this topic is already in final_clusters
        already_exists = False
        for existing in final_clusters:
            if new_cluster['topic'].lower() in existing['topic'].lower() or existing['topic'].lower() in new_cluster['topic'].lower():
                already_exists = True
                break
        
        # Check if this topic is in cooldown
        in_cooldown = False
        for cooldown_topic in cooldown_topics:
            if new_cluster['topic'].lower() in cooldown_topic.lower() or cooldown_topic.lower() in new_cluster['topic'].lower():
                in_cooldown = True
                logger.info(f"  Skipping cooldown topic: {new_cluster['topic']}")
                break
        
        if not already_exists and not in_cooldown:
            final_clusters.append(new_cluster)
            logger.info(f"  Adding new cluster: {new_cluster['topic']}")
    
    cluster_data['clusters'] = final_clusters[:2]
    
    # Report results
    logger.info("-" * 60)
    logger.info(f"Final clusters: {len(cluster_data['clusters'])}")
    for cluster in cluster_data['clusters']:
        logger.info(f"  • {cluster['topic']} ({cluster['story_count']} stories)")
        for story in cluster['stories']:
            logger.info(f"      - [{story['source']}] {(story['headline'] or story['title'])[:50]}...")
    
    logger.info(f"Unclustered stories: {len(cluster_data['unclustered'])}")
    
    if not args.dry_run:
        save_clusters(cluster_data)
    else:
        logger.info("DRY RUN - clusters not saved")


if __name__ == "__main__":
    main()
