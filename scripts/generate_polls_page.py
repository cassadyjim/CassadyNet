#!/usr/bin/env python3
"""
CassadyNet - Generate Previous Polls Page
Creates a page showing archived poll results.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
ARCHIVED_POLLS_FILE = BASE_DIR / "data" / "archived_polls.json"
OUTPUT_DIR = BASE_DIR / "output"

# Template for previous polls page
PREVIOUS_POLLS_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Previous poll results from CassadyNet AI news analysis">
    <title>Previous Polls - CassadyNet</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Merriweather:wght@400;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --text-primary: #0f172a;
            --text-secondary: #64748b;
            --text-light: #94a3b8;
            --accent: #3b82f6;
            --border: #e2e8f0;
            --pro-color: #10b981;
            --con-color: #ef4444;
            --gradient-start: #3b82f6;
            --gradient-end: #8b5cf6;
        }
        
        body {
            background-color: var(--bg-primary);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 16px;
            line-height: 1.6;
            color: var(--text-primary);
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            padding: 20px 0;
            margin-bottom: 24px;
        }
        
        .site-logo-link {
            display: inline-flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
        }
        
        .site-logo {
            width: 42px;
            height: 42px;
            border-radius: 8px;
        }
        
        .site-title {
            font-size: 42px;
            font-weight: 900;
            background: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-end) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-decoration: none;
            letter-spacing: -2px;
        }
        
        .page-title {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
            color: var(--text-primary);
        }
        
        .page-subtitle {
            font-size: 16px;
            color: var(--text-secondary);
            margin-bottom: 32px;
        }
        
        .back-link {
            display: inline-block;
            margin-bottom: 24px;
            font-size: 14px;
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }
        
        .back-link:hover { text-decoration: underline; }
        
        .polls-list {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .poll-card {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            border: 1px solid var(--border);
        }
        
        .poll-question {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 16px;
            line-height: 1.4;
        }
        
        .poll-results-bar {
            height: 36px;
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            margin-bottom: 12px;
            background: var(--border);
        }
        
        .poll-results-bar .pro-bar {
            background: var(--pro-color);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 14px;
            min-width: 40px;
        }
        
        .poll-results-bar .con-bar {
            background: var(--con-color);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 14px;
            min-width: 40px;
        }
        
        .poll-stats {
            display: flex;
            justify-content: space-between;
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 16px;
        }
        
        .poll-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 16px;
            border-top: 1px solid var(--border);
        }
        
        .poll-date {
            font-size: 13px;
            color: var(--text-light);
        }
        
        .poll-link {
            font-size: 14px;
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }
        
        .poll-link:hover { text-decoration: underline; }
        
        .no-polls {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }
        
        .total-votes {
            font-size: 13px;
            color: var(--text-light);
            text-align: center;
        }
        
        .footer {
            text-align: center;
            padding: 30px;
            margin-top: 30px;
            font-size: 13px;
            color: var(--text-secondary);
        }
        
        .footer a { color: var(--accent); text-decoration: none; }
        .footer-links a { margin: 0 12px; }
        
        .loading {
            color: var(--text-light);
            font-style: italic;
        }
        
        @media (max-width: 600px) {
            .poll-card { padding: 20px; }
            .poll-question { font-size: 16px; }
            .site-title { font-size: 32px; }
        }
    </style>
</head>
<body>
    <header class="header">
        <a href="/" class="site-logo-link">
            <img src="/logo.png" alt="CassadyNet" class="site-logo">
            <span class="site-title">CassadyNet</span>
        </a>
    </header>
    
    <a href="/" class="back-link">← Back to Headlines</a>
    
    <h1 class="page-title">Previous Polls</h1>
    <p class="page-subtitle">See how readers voted on past AI news topics</p>
    
    <div class="polls-list">
        {{POLLS_LIST}}
    </div>
    
    <footer class="footer">
        <div>CassadyNet · AI-Powered News Analysis</div>
        <div class="footer-links">
            <a href="/">Home</a>
            <a href="/about.html">About</a>
            <a href="/sources.html">Sources</a>
            <a href="/privacy.html">Privacy</a>
        </div>
    </footer>
    
    <script>
        const POLL_API = '/poll/api.php';
        
        // Fetch live results for each poll
        document.querySelectorAll('.poll-card').forEach(card => {
            const pollId = card.dataset.pollId;
            if (!pollId) return;
            
            fetch(`${POLL_API}?poll_id=${pollId}`)
                .then(res => res.json())
                .then(data => {
                    if (data.results) {
                        const results = data.results;
                        const proBar = card.querySelector('.pro-bar');
                        const conBar = card.querySelector('.con-bar');
                        const proCount = card.querySelector('.pro-count');
                        const conCount = card.querySelector('.con-count');
                        const totalVotes = card.querySelector('.total-votes');
                        
                        if (proBar) {
                            proBar.style.width = (results.pro_percent || 50) + '%';
                            proBar.textContent = (results.pro_percent || 50) + '%';
                        }
                        if (conBar) {
                            conBar.style.width = (results.con_percent || 50) + '%';
                            conBar.textContent = (results.con_percent || 50) + '%';
                        }
                        if (proCount) proCount.textContent = results.pro || 0;
                        if (conCount) conCount.textContent = results.con || 0;
                        if (totalVotes) totalVotes.textContent = (results.total || 0) + ' total votes';
                    }
                })
                .catch(err => console.log('Could not fetch results for', pollId));
        });
    </script>
</body>
</html>
"""


def load_archived_polls() -> list:
    """Load archived polls"""
    if ARCHIVED_POLLS_FILE.exists():
        with open(ARCHIVED_POLLS_FILE, 'r') as f:
            data = json.load(f)
            return data.get('polls', [])
    return []


def format_date(iso_date: str) -> str:
    """Format ISO date to readable format"""
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime('%b %d, %Y')
    except (ValueError, TypeError):
        return ""


def generate_poll_card_html(poll: dict) -> str:
    """Generate HTML for a single poll card"""
    
    question = poll.get('question', poll.get('topic', 'Unknown'))
    results = poll.get('results', {'pro': 0, 'con': 0, 'total': 0, 'pro_percent': 50, 'con_percent': 50})
    
    pro_percent = results.get('pro_percent', 50)
    con_percent = results.get('con_percent', 50)
    pro_count = results.get('pro', 0)
    con_count = results.get('con', 0)
    total = results.get('total', 0)
    
    button_a = poll.get('button_a', 'Yes')
    button_b = poll.get('button_b', 'No')
    
    archived_date = format_date(poll.get('archived_at', ''))
    analysis_url = poll.get('analysis_url', '')
    poll_id = poll.get('poll_id', '')
    
    link_html = ""
    if analysis_url:
        link_html = f'<a href="{analysis_url}" class="poll-link">View Analysis →</a>'
    
    return f"""
    <div class="poll-card" data-poll-id="{poll_id}">
        <div class="poll-question">{question}</div>
        <div class="poll-results-bar">
            <div class="pro-bar" style="width: 50%">--%</div>
            <div class="con-bar" style="width: 50%">--%</div>
        </div>
        <div class="poll-stats">
            <span>👍 {button_a}: <strong class="pro-count">--</strong></span>
            <span>👎 {button_b}: <strong class="con-count">--</strong></span>
        </div>
        <div class="total-votes">Loading...</div>
        <div class="poll-meta">
            <span class="poll-date">Closed {archived_date}</span>
            {link_html}
        </div>
    </div>
    """


def generate_previous_polls_page():
    """Generate the previous polls page"""
    
    logger.info("Generating previous polls page...")
    
    polls = load_archived_polls()
    
    if not polls:
        polls_html = '<div class="no-polls">No previous polls yet. Check back soon!</div>'
    else:
        polls_html = ""
        for poll in polls[:20]:  # Limit to 20
            polls_html += generate_poll_card_html(poll)
    
    html = PREVIOUS_POLLS_TEMPLATE.replace('{{POLLS_LIST}}', polls_html)
    
    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "polls.html"
    with open(output_file, 'w') as f:
        f.write(html)
    
    logger.info(f"Previous polls page saved to {output_file}")
    logger.info(f"Total archived polls: {len(polls)}")
    
    return output_file


if __name__ == "__main__":
    generate_previous_polls_page()
