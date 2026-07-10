#!/usr/bin/env python3
"""
CassadyNet - Poll Tracking System
Tracks active polls, matches topics across updates, and archives closed polls.
"""

import json
import logging
from datetime import datetime, timedelta
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
ACTIVE_POLLS_FILE = BASE_DIR / "data" / "active_polls.json"
ARCHIVED_POLLS_FILE = BASE_DIR / "data" / "archived_polls.json"
CLUSTERS_FILE = BASE_DIR / "data" / "story_clusters.json"
ANALYSIS_INDEX_FILE = BASE_DIR / "data" / "analysis_index.json"

# Minimum hours a poll must be active before it can be archived
MIN_POLL_HOURS = 24


def load_json(filepath: Path) -> dict:
    """Load JSON file or return empty dict"""
    if filepath.exists():
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}


def save_json(filepath: Path, data: dict):
    """Save data to JSON file"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def load_active_polls() -> dict:
    """Load active polls tracking data"""
    data = load_json(ACTIVE_POLLS_FILE)
    if 'polls' not in data:
        data = {'polls': [], 'last_updated': None}
    return data


def save_active_polls(data: dict):
    """Save active polls data"""
    data['last_updated'] = datetime.now().isoformat()
    save_json(ACTIVE_POLLS_FILE, data)


def load_archived_polls() -> dict:
    """Load archived polls"""
    data = load_json(ARCHIVED_POLLS_FILE)
    if 'polls' not in data:
        data = {'polls': []}
    return data


def save_archived_polls(data: dict):
    """Save archived polls"""
    save_json(ARCHIVED_POLLS_FILE, data)


def topics_match(topic1: str, topic2: str, description1: str = "", description2: str = "") -> bool:
    """Use AI to determine if two topics are about the same subject matter"""
    
    client = Anthropic()
    
    prompt = f"""Determine if these two news cluster topics are about the SAME subject matter.

Topic 1: {topic1}
Description 1: {description1}

Topic 2: {topic2}
Description 2: {description2}

They are the SAME if they cover the same underlying news story, event, or issue - even if worded differently.
Examples of SAME:
- "Nvidia China Chip Exports" and "US Approves Nvidia H200 Sales to China" = SAME
- "Microsoft Copilot Police Scandal" and "UK Police AI Mistake" = SAME

Examples of DIFFERENT:
- "Nvidia Chip Exports" and "OpenAI GPT-5 Launch" = DIFFERENT
- "AI Privacy Concerns" and "AI Job Displacement" = DIFFERENT

Respond with only: SAME or DIFFERENT"""

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}]
    )
    
    result = response.content[0].text.strip().upper()
    return "SAME" in result


def find_matching_active_poll(new_topic: str, new_description: str, active_polls: list) -> dict:
    """Find an active poll that matches the new topic"""
    
    for poll in active_polls:
        if topics_match(new_topic, poll['topic'], new_description, poll.get('description', '')):
            logger.info(f"  Topic match found: '{new_topic}' matches existing '{poll['topic']}'")
            return poll
    
    return None


def get_poll_results(poll_id: str) -> dict:
    """Fetch current poll results from the database via PHP API or directly"""
    import sqlite3
    import urllib.request
    import urllib.parse
    import json as json_lib

    # Try to read directly from the polls database if it exists locally
    polls_db = BASE_DIR / "data" / "polls.db"

    if polls_db.exists():
        try:
            conn = sqlite3.connect(polls_db)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT vote, COUNT(*) as count
                FROM votes
                WHERE poll_id = ?
                GROUP BY vote
            """, (poll_id,))

            results = {'pro': 0, 'con': 0}
            for row in cursor.fetchall():
                if row[0] in results:
                    results[row[0]] = row[1]

            conn.close()

            total = results['pro'] + results['con']
            return {
                'pro': results['pro'],
                'con': results['con'],
                'total': total,
                'pro_percent': round((results['pro'] / total) * 100) if total > 0 else 50,
                'con_percent': round((results['con'] / total) * 100) if total > 0 else 50
            }
        except Exception as e:
            logger.warning(f"Could not read local polls.db: {e}")

    # Fallback: fetch live results from the server API
    try:
        encoded_id = urllib.parse.quote(poll_id)
        url = f'https://cassadynet.com/poll/api.php?poll_id={encoded_id}'
        req = urllib.request.Request(url, headers={'User-Agent': 'CassadyNet-Archiver/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json_lib.loads(response.read().decode())
            if 'results' in data:
                logger.info(f"  Fetched live results from API for poll: {poll_id}")
                return data['results']
    except Exception as e:
        logger.warning(f"Could not fetch results from API for {poll_id}: {e}")

    # Return empty results if all methods fail
    return {'pro': 0, 'con': 0, 'total': 0, 'pro_percent': 50, 'con_percent': 50}


def archive_poll(poll: dict, reason: str = "topic_replaced"):
    """Archive a poll with its final results"""
    
    logger.info(f"Archiving poll: {poll['topic']} (reason: {reason})")
    
    # Get final results
    results = get_poll_results(poll['poll_id'])
    
    archived = load_archived_polls()
    
    archived_poll = {
        'topic': poll['topic'],
        'description': poll.get('description', ''),
        'question': poll['question'],
        'button_a': poll.get('button_a', 'Yes'),
        'button_b': poll.get('button_b', 'No'),
        'poll_id': poll['poll_id'],
        'results': results,
        'analysis_url': poll.get('analysis_url', ''),
        'started_at': poll.get('created_at', ''),
        'archived_at': datetime.now().isoformat(),
        'reason': reason
    }
    
    # Add to front of list (most recent first)
    archived['polls'].insert(0, archived_poll)
    
    # Keep only last 50 archived polls
    archived['polls'] = archived['polls'][:50]
    
    save_archived_polls(archived)
    
    return archived_poll


def update_poll_tracking(clusters: list, analysis_index: dict) -> dict:
    """
    Update poll tracking based on current clusters.
    Returns dict with 'active' polls and any newly 'archived' polls.
    """
    
    logger.info("Updating poll tracking...")
    
    active_data = load_active_polls()
    current_active = active_data.get('polls', [])
    
    new_active = []
    archived_this_run = []
    
    # Get analysis info for each cluster
    analysis_map = {a['topic']: a for a in analysis_index.get('analyses', [])}
    
    # Process each current cluster (top 2)
    for cluster in clusters[:2]:
        topic = cluster['topic']
        description = cluster.get('description', '')
        
        # Check if this matches an existing active poll
        matching_poll = find_matching_active_poll(topic, description, current_active)
        
        if matching_poll:
            # Topic continues - keep the same poll
            logger.info(f"  Continuing poll for: {topic}")
            
            # Update the analysis URL if we have a new one
            analysis_info = analysis_map.get(topic, {})
            if analysis_info:
                matching_poll['analysis_url'] = analysis_info.get('url', matching_poll.get('analysis_url', ''))
            
            matching_poll['last_seen'] = datetime.now().isoformat()
            matching_poll['current_topic_name'] = topic  # Track current name even if different
            new_active.append(matching_poll)
            
            # Remove from current_active so we don't process it again
            current_active = [p for p in current_active if p['poll_id'] != matching_poll['poll_id']]
        else:
            # New topic - create new poll entry
            logger.info(f"  New poll topic: {topic}")
            
            analysis_info = analysis_map.get(topic, {})
            
            new_poll = {
                'topic': topic,
                'description': description,
                'question': analysis_info.get('question', ''),  # Will be set by generate_analysis
                'poll_id': analysis_info.get('poll_id', ''),
                'analysis_url': analysis_info.get('url', ''),
                'analysis_type': analysis_info.get('analysis_type', 'poll'),
                'created_at': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            }
            new_active.append(new_poll)
    
    # Archive polls that are no longer in top 2 clusters
    now = datetime.now()
    for old_poll in current_active:
        created_at = datetime.fromisoformat(old_poll.get('created_at', now.isoformat()))
        age_hours = (now - created_at).total_seconds() / 3600
        
        if age_hours >= MIN_POLL_HOURS:
            # Old enough to archive
            archived = archive_poll(old_poll, "topic_replaced")
            archived_this_run.append(archived)
        else:
            # Too young to archive - keep it active but mark as pending
            logger.info(f"  Poll too young to archive ({age_hours:.1f}h < {MIN_POLL_HOURS}h): {old_poll['topic']}")
            old_poll['pending_archive'] = True
            new_active.append(old_poll)
    
    # Save updated active polls
    active_data['polls'] = new_active
    save_active_polls(active_data)
    
    logger.info(f"  Active polls: {len(new_active)}, Archived this run: {len(archived_this_run)}")
    
    return {
        'active': new_active,
        'archived': archived_this_run
    }


def get_active_poll_for_topic(topic: str) -> dict:
    """Get the active poll info for a topic, if it exists"""
    
    active_data = load_active_polls()
    
    for poll in active_data.get('polls', []):
        if poll['topic'] == topic or poll.get('current_topic_name') == topic:
            return poll
    
    # Check if topic matches via AI
    for poll in active_data.get('polls', []):
        if topics_match(topic, poll['topic']):
            return poll
    
    return None


def register_new_poll(topic: str, description: str, question: str, poll_id: str, analysis_url: str, analysis_type: str = "poll", button_a: str = "Yes", button_b: str = "No", cluster_stories: list = None):
    """Register a new poll or update existing one.
    cluster_stories is stored so the cluster can be reconstructed during the
    24-hour protection window even if the clustering algorithm renames the topic.
    """

    active_data = load_active_polls()
    polls = active_data.get('polls', [])

    # Check if poll already exists
    for poll in polls:
        if poll['poll_id'] == poll_id or poll['topic'] == topic:
            # Update existing
            poll['question'] = question or poll.get('question', '')
            poll['button_a'] = button_a or poll.get('button_a', 'Yes')
            poll['button_b'] = button_b or poll.get('button_b', 'No')
            poll['analysis_url'] = analysis_url
            poll['analysis_type'] = analysis_type
            poll['last_seen'] = datetime.now().isoformat()
            # Refresh stored stories so they stay current
            if cluster_stories:
                poll['cluster_stories'] = cluster_stories
            save_active_polls(active_data)
            return poll

    # Create new
    new_poll = {
        'topic': topic,
        'description': description,
        'question': question,
        'button_a': button_a,
        'button_b': button_b,
        'poll_id': poll_id,
        'analysis_url': analysis_url,
        'analysis_type': analysis_type,
        'created_at': datetime.now().isoformat(),
        'last_seen': datetime.now().isoformat(),
        'cluster_stories': cluster_stories or []   # stored for 24h protection fallback
    }
    polls.append(new_poll)
    active_data['polls'] = polls
    save_active_polls(active_data)

    return new_poll


def get_archived_polls(limit: int = 20) -> list:
    """Get list of archived polls for display"""
    
    archived = load_archived_polls()
    return archived.get('polls', [])[:limit]


if __name__ == "__main__":
    # Test the system
    logger.info("Poll Tracking System Test")
    
    active = load_active_polls()
    logger.info(f"Active polls: {len(active.get('polls', []))}")
    
    archived = load_archived_polls()
    logger.info(f"Archived polls: {len(archived.get('polls', []))}")
