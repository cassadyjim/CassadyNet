#!/usr/bin/env python3
"""
CassadyNet - Generate Archive Page
Creates a full index of every analysis page ever published, grouped by month.

Why this exists: the homepage only shows recent stories and polls.html only
shows the last 20 archived polls, so older analysis pages had no durable
on-site link pointing to them. This page is a permanent discovery path for
both search engines and readers, sourced from data/analysis_index.json
(the persistent record), not the ephemeral local output/ directory.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
ANALYSIS_INDEX_FILE = BASE_DIR / "data" / "analysis_index.json"
OUTPUT_DIR = BASE_DIR / "output"

SITE_URL = "https://cassadynet.com"

ARCHIVE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Full archive of every AI news analysis and poll published on CassadyNet, organized by month.">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://cassadynet.com/archive.html">
    <meta property="og:title" content="Archive - CassadyNet">
    <meta property="og:description" content="Full archive of every AI news analysis and poll published on CassadyNet, organized by month.">
    <meta property="og:url" content="https://cassadynet.com/archive.html">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="CassadyNet">
    <meta property="og:image" content="https://cassadynet.com/logo.png">
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="Archive - CassadyNet">
    <meta name="twitter:description" content="Full archive of every AI news analysis and poll published on CassadyNet, organized by month.">
    <meta name="twitter:image" content="https://cassadynet.com/logo.png">
    <title>Archive - CassadyNet</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Merriweather:wght@400;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        :root {{
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --text-primary: #0f172a;
            --text-secondary: #64748b;
            --text-light: #94a3b8;
            --accent: #3b82f6;
            --border: #e2e8f0;
            --gradient-start: #3b82f6;
            --gradient-end: #8b5cf6;
        }}

        body {{
            background-color: var(--bg-primary);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 16px;
            line-height: 1.6;
            color: var(--text-primary);
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}

        .header {{
            text-align: center;
            padding: 20px 0;
            margin-bottom: 24px;
        }}

        .site-logo-link {{
            display: inline-flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
        }}

        .site-logo {{
            width: 42px;
            height: 42px;
            border-radius: 8px;
        }}

        .site-title {{
            font-size: 42px;
            font-weight: 900;
            background: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-end) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-decoration: none;
            letter-spacing: -2px;
        }}

        .page-title {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
            color: var(--text-primary);
        }}

        .page-subtitle {{
            font-size: 16px;
            color: var(--text-secondary);
            margin-bottom: 32px;
        }}

        .back-link {{
            display: inline-block;
            margin-bottom: 24px;
            font-size: 14px;
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }}

        .back-link:hover {{ text-decoration: underline; }}

        .month-jump {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }}

        .month-jump a {{
            font-size: 13px;
            color: var(--accent);
            text-decoration: none;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            padding: 4px 10px;
            border-radius: 6px;
        }}

        .month-jump a:hover {{ text-decoration: underline; }}

        .month-group {{
            margin-bottom: 36px;
        }}

        .month-heading {{
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 14px;
            padding-bottom: 8px;
            border-bottom: 2px solid var(--border);
        }}

        .archive-list {{
            list-style: none;
        }}

        .archive-item {{
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 16px;
        }}

        .archive-item a {{
            color: var(--text-primary);
            text-decoration: none;
            font-weight: 500;
            font-size: 15px;
        }}

        .archive-item a:hover {{ color: var(--accent); text-decoration: underline; }}

        .archive-date {{
            font-size: 13px;
            color: var(--text-light);
            white-space: nowrap;
            flex-shrink: 0;
        }}

        .footer {{
            text-align: center;
            padding: 30px;
            margin-top: 30px;
            font-size: 13px;
            color: var(--text-secondary);
        }}

        .footer a {{ color: var(--accent); text-decoration: none; }}
        .footer-links a {{ margin: 0 12px; }}

        @media (max-width: 600px) {{
            .site-title {{ font-size: 32px; }}
            .archive-item {{ flex-direction: column; gap: 2px; }}
        }}
    </style>
    <script data-goatcounter="https://cassadynet.goatcounter.com/count"
            async src="//gc.zgo.at/count.js"></script>
</head>
<body>
    <header class="header">
        <a href="/" class="site-logo-link">
            <img src="/logo.png" alt="CassadyNet" class="site-logo">
            <span class="site-title">CassadyNet</span>
        </a>
    </header>

    <a href="/" class="back-link">← Back to Headlines</a>

    <h1 class="page-title">Full Archive</h1>
    <p class="page-subtitle">Every AI news analysis and poll CassadyNet has published, {total} in all</p>

    <nav class="month-jump">
{month_jump}
    </nav>

{month_groups}

    <footer class="footer">
        <div>CassadyNet · AI-Powered News Analysis</div>
        <div class="footer-links">
            <a href="/">Home</a>
            <a href="/polls.html">Previous Polls</a>
            <a href="/about.html">About</a>
            <a href="/sources.html">Sources</a>
            <a href="/privacy.html">Privacy</a>
        </div>
    </footer>
</body>
</html>
"""


def load_analyses() -> list:
    if not ANALYSIS_INDEX_FILE.exists():
        return []
    with open(ANALYSIS_INDEX_FILE, 'r') as f:
        data = json.load(f)
    return data.get('analyses', [])


def month_key_and_label(iso_date: str):
    try:
        dt = datetime.fromisoformat(iso_date)
    except (ValueError, TypeError):
        dt = datetime.min
    return dt.strftime('%Y-%m'), dt.strftime('%B %Y'), dt


def generate_archive_page():
    logger.info("Generating archive page...")

    analyses = load_analyses()

    # Dedupe by url, keep newest generated_at per url
    by_url = {}
    for entry in analyses:
        url = entry.get('url')
        if not url:
            continue
        existing = by_url.get(url)
        if not existing or entry.get('generated_at', '') > existing.get('generated_at', ''):
            by_url[url] = entry

    entries = sorted(by_url.values(), key=lambda e: e.get('generated_at', ''), reverse=True)

    groups = defaultdict(list)
    labels = {}
    for entry in entries:
        key, label, dt = month_key_and_label(entry.get('generated_at', ''))
        groups[key].append((entry, dt))
        labels[key] = label

    month_keys_sorted = sorted(groups.keys(), reverse=True)

    month_jump_html = "\n".join(
        f'        <a href="#{key}">{labels[key]}</a>' for key in month_keys_sorted
    )

    month_groups_html = []
    for key in month_keys_sorted:
        items = []
        for entry, dt in groups[key]:
            topic = entry.get('topic', 'Untitled')
            url = entry.get('url', '#')
            date_str = dt.strftime('%b %d') if dt != datetime.min else ''
            items.append(
                f'            <li class="archive-item">'
                f'<a href="{url}">{topic}</a>'
                f'<span class="archive-date">{date_str}</span>'
                f'</li>'
            )
        month_groups_html.append(
            f'    <section class="month-group" id="{key}">\n'
            f'        <h2 class="month-heading">{labels[key]} <span style="color:var(--text-light); font-weight:400; font-size:15px;">({len(items)})</span></h2>\n'
            f'        <ul class="archive-list">\n' + "\n".join(items) + "\n        </ul>\n"
            f'    </section>'
        )

    html = ARCHIVE_TEMPLATE.format(
        total=f"{len(entries):,} pages",
        month_jump=month_jump_html,
        month_groups="\n\n".join(month_groups_html),
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "archive.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"Archive page saved to {output_file}")
    logger.info(f"Total analysis pages indexed: {len(entries)}")

    return output_file


if __name__ == "__main__":
    generate_archive_page()
