#!/usr/bin/env python3
"""
CassadyNet - Sitemap Generator
Creates sitemap.xml for SEO with all pages.
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
OUTPUT_DIR = BASE_DIR / "output"
ANALYSIS_DIR = OUTPUT_DIR / "analysis"
ANALYSIS_INDEX_FILE = BASE_DIR / "data" / "analysis_index.json"

SITE_URL = "https://cassadynet.com"

# Sitemap template
SITEMAP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
{urls}
</urlset>
"""

URL_TEMPLATE = """  <url>
    <loc>{loc}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>"""


def get_file_mod_time(filepath: Path) -> str:
    """Get file modification time in ISO format"""
    if filepath.exists():
        mtime = filepath.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
    return datetime.now().strftime('%Y-%m-%d')


def generate_sitemap():
    """Generate sitemap.xml with all site pages"""
    
    logger.info("Generating sitemap.xml...")
    
    urls = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Homepage - highest priority, refreshed by the publish pipeline (currently 2x/day)
    urls.append(URL_TEMPLATE.format(
        loc=f"{SITE_URL}/",
        lastmod=today,
        changefreq="daily",
        priority="1.0"
    ))
    
    # Main static pages
    static_pages = [
        ("about.html", "monthly", "0.6"),
        ("sources.html", "monthly", "0.5"),
        ("privacy.html", "yearly", "0.3"),
        ("polls.html", "daily", "0.7"),
        ("archive.html", "daily", "0.7"),
    ]

    for page, freq, priority in static_pages:
        filepath = OUTPUT_DIR / page
        if filepath.exists():
            urls.append(URL_TEMPLATE.format(
                loc=f"{SITE_URL}/{page}",
                lastmod=get_file_mod_time(filepath),
                changefreq=freq,
                priority=priority
            ))

    # Analysis pages - sourced from the persistent analysis_index.json, not the
    # local output/analysis/ directory. In GitHub Actions, output/ is gitignored
    # and starts empty on every run, so a directory glob here only ever picked up
    # that run's handful of new pages — the sitemap has been silently dropping
    # nearly the entire history on every publish. analysis_index.json is git-
    # committed and accumulates every page ever generated, so it's the real source
    # of truth for what URLs exist.
    if ANALYSIS_INDEX_FILE.exists():
        with open(ANALYSIS_INDEX_FILE, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
        analyses = index_data.get('analyses', [])

        # Dedupe by url, keep the newest generated_at per url
        by_url = {}
        for entry in analyses:
            url = entry.get('url')
            if not url:
                continue
            existing = by_url.get(url)
            if not existing or entry.get('generated_at', '') > existing.get('generated_at', ''):
                by_url[url] = entry

        logger.info(f"Found {len(by_url)} analysis pages in analysis_index.json")

        for url, entry in by_url.items():
            generated_at = entry.get('generated_at', '')
            try:
                lastmod = datetime.fromisoformat(generated_at).strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                lastmod = today
            urls.append(URL_TEMPLATE.format(
                loc=f"{SITE_URL}{url}",
                lastmod=lastmod,
                changefreq="monthly",
                priority="0.8"
            ))
    else:
        logger.warning("analysis_index.json not found — falling back to local output/analysis/ glob")
        if ANALYSIS_DIR.exists():
            analysis_files = list(ANALYSIS_DIR.glob("*.html"))
            logger.info(f"Found {len(analysis_files)} analysis pages locally")

            for filepath in analysis_files:
                urls.append(URL_TEMPLATE.format(
                    loc=f"{SITE_URL}/analysis/{filepath.name}",
                    lastmod=get_file_mod_time(filepath),
                    changefreq="monthly",
                    priority="0.8"
                ))
    
    # Generate sitemap
    sitemap_content = SITEMAP_TEMPLATE.format(urls="\n".join(urls))
    
    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sitemap_file = OUTPUT_DIR / "sitemap.xml"
    with open(sitemap_file, 'w', encoding='utf-8') as f:
        f.write(sitemap_content)
    
    logger.info(f"Sitemap saved to {sitemap_file}")
    logger.info(f"Total URLs: {len(urls)}")
    
    return sitemap_file


if __name__ == "__main__":
    generate_sitemap()
