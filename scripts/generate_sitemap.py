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
    
    # Homepage - highest priority, changes hourly
    urls.append(URL_TEMPLATE.format(
        loc=f"{SITE_URL}/",
        lastmod=today,
        changefreq="hourly",
        priority="1.0"
    ))
    
    # Main static pages
    static_pages = [
        ("about.html", "monthly", "0.6"),
        ("sources.html", "monthly", "0.5"),
        ("privacy.html", "yearly", "0.3"),
        ("polls.html", "daily", "0.7"),
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
    
    # Analysis pages - high priority, fresh content
    if ANALYSIS_DIR.exists():
        analysis_files = list(ANALYSIS_DIR.glob("*.html"))
        logger.info(f"Found {len(analysis_files)} analysis pages")
        
        for filepath in analysis_files:
            urls.append(URL_TEMPLATE.format(
                loc=f"{SITE_URL}/analysis/{filepath.name}",
                lastmod=get_file_mod_time(filepath),
                changefreq="daily",
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
