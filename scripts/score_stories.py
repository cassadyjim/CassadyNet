#!/usr/bin/env python3
"""
AI News Aggregator - Story Scorer
Calls Claude API to score stories for newsworthiness.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

try:
    import anthropic
except ImportError:
    print("❌ anthropic package not installed. Run: pip3 install anthropic")
    exit(1)

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_FILE = BASE_DIR / "data" / "stories.db"

# =============================================================================
# EVALUATION PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are an editorial assistant for CassadyNet, an AI news aggregation site.

SITE POSITIONING:
- Pure speed: We want to be FIRST with breaking AI news
- Global breadth: We cover AI stories worldwide, not just Silicon Valley
- Target: ~25 high-impact stories per day
- Audience: AI professionals, investors, and enthusiasts who want rapid signal

YOUR TASK:
Evaluate each story and return scored results as JSON.

SCORING CRITERIA (1-10 each):
1. BREAKING - Is this fresh news? (10=last few hours, 5=this week, 1=old/evergreen)
2. IMPACT - How significant? (10=industry-shifting, 5=moderate interest, 1=minimal)
3. EXCLUSIVITY - Are we adding value? (10=underreported, 5=few outlets, 1=viral rehash)
4. CREDIBILITY - Can we trust this? (10=official source, 6=reputable blog, 2=rumor)
5. HEADLINE_POTENTIAL - Will this drive clicks? (10=dramatic, 5=solid, 1=boring)

BONUSES: China/Asia AI news +5, EU/regulatory +3, First English coverage +5
PENALTIES: Research papers without news angle: cap at 25. Opinion pieces: -5. PR fluff: cap at 15.

HEADLINE STYLE: Short, punchy. Use caps for drama. Examples:
- "PENTAGON DEPLOYS GROK... GLOBAL BACKLASH"
- "DeepSeek's New Model Beats Claude on Coding"
- "Senate Passes AI Deepfake Bill"

OUTPUT FORMAT - Return ONLY valid JSON array:
[
  {
    "story_id": "xxx",
    "scores": {"breaking": X, "impact": X, "exclusivity": X, "credibility": X, "headline_potential": X},
    "bonuses": X,
    "penalties": X,
    "total_score": X,
    "headline": "PUNCHY HEADLINE",
    "skip": false
  }
]

Set "skip": true for stories that are not AI-related or are low quality (score < 20).
Return ONLY the JSON array, no other text."""


def get_unscored_stories(hours: int = 24, limit: int = 100) -> List[Dict]:
    """Get recent stories that haven't been scored yet"""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        
        query = """
            SELECT id, title, url, source, category, published, summary
            FROM stories 
            WHERE fetched_at > datetime('now', ?)
            AND score = 0
            AND status = 'new'
            ORDER BY published DESC
            LIMIT ?
        """
        
        rows = conn.execute(query, (f'-{hours} hours', limit)).fetchall()
        return [dict(row) for row in rows]


def update_story_scores(evaluations: List[Dict]):
    """Update stories in database with scores and headlines"""
    with sqlite3.connect(DB_FILE) as conn:
        for eval in evaluations:
            if eval.get('skip', False):
                # Mark as rejected
                conn.execute(
                    "UPDATE stories SET status = 'rejected', score = ? WHERE id = ?",
                    (eval.get('total_score', 0), eval['story_id'])
                )
            else:
                # Update with score and headline
                conn.execute(
                    """UPDATE stories 
                       SET score = ?, headline = ?, status = 'reviewed'
                       WHERE id = ?""",
                    (eval['total_score'], eval['headline'], eval['story_id'])
                )
        conn.commit()


def score_stories(stories: List[Dict], api_key: str = None) -> List[Dict]:
    """Call Claude API to score stories"""
    
    if not stories:
        print("No stories to score")
        return []
    
    # Get API key
    api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    # Prepare stories for prompt (limit fields to reduce tokens)
    stories_for_prompt = []
    for s in stories:
        stories_for_prompt.append({
            "id": s["id"],
            "title": s["title"],
            "source": s["source"],
            "category": s["category"],
            "published": s["published"],
            "summary": (s["summary"] or "")[:300]  # Truncate summaries
        })
    
    # Build user prompt
    user_prompt = f"""Current time: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

Score these {len(stories_for_prompt)} stories:

{json.dumps(stories_for_prompt, indent=2)}

Return ONLY a JSON array with your evaluations."""

    # Call Claude API
    client = anthropic.Anthropic(api_key=api_key)
    
    print(f"📡 Calling Claude API to score {len(stories)} stories...")
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[
            {"role": "user", "content": user_prompt}
        ],
        system=SYSTEM_PROMPT
    )
    
    # Parse response
    response_text = message.content[0].text
    
    # Clean up response (sometimes Claude adds markdown code blocks)
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    response_text = response_text.strip()
    
    try:
        evaluations = json.loads(response_text)
        print(f"✅ Received {len(evaluations)} evaluations")
        return evaluations
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse API response: {e}")
        print(f"Response was: {response_text[:500]}...")
        return []


def run_scoring(hours: int = 24, limit: int = 50, dry_run: bool = False):
    """Main scoring function"""
    
    print(f"\n{'='*60}")
    print("CASSADYNET STORY SCORER")
    print(f"{'='*60}\n")
    
    # Get unscored stories
    stories = get_unscored_stories(hours=hours, limit=limit)
    
    if not stories:
        print("✅ No new stories to score")
        return []
    
    print(f"📰 Found {len(stories)} unscored stories from last {hours} hours")
    
    # Score stories
    evaluations = score_stories(stories)
    
    if not evaluations:
        print("❌ No evaluations returned")
        return []
    
    # Summary
    scored = [e for e in evaluations if not e.get('skip', False)]
    skipped = [e for e in evaluations if e.get('skip', False)]
    
    print(f"\n📊 Results:")
    print(f"   Scored: {len(scored)}")
    print(f"   Skipped: {len(skipped)}")
    
    if scored:
        top_stories = sorted(scored, key=lambda x: x['total_score'], reverse=True)[:5]
        print(f"\n🔥 Top 5 stories:")
        for i, s in enumerate(top_stories, 1):
            print(f"   {i}. [{s['total_score']}] {s['headline'][:50]}...")
    
    # Update database
    if not dry_run:
        update_story_scores(evaluations)
        print(f"\n✅ Database updated")
    else:
        print(f"\n⚠️  Dry run - database not updated")
    
    return evaluations


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Score stories using Claude API")
    parser.add_argument("--hours", type=int, default=24, help="Hours of history to check (1-168)")
    parser.add_argument("--limit", type=int, default=50, help="Max stories to score (1-200)")
    parser.add_argument("--dry-run", action="store_true", help="Don't update database")

    args = parser.parse_args()

    # Input validation
    if args.hours < 1 or args.hours > 168:
        print("Error: --hours must be between 1 and 168 (1 week)")
        sys.exit(1)
    if args.limit < 1 or args.limit > 200:
        print("Error: --limit must be between 1 and 200")
        sys.exit(1)

    run_scoring(hours=args.hours, limit=args.limit, dry_run=args.dry_run)
