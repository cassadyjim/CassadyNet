#!/usr/bin/env python3
"""
CassadyNet - RSS Feed Generator
Generates an RSS feed from the top scored stories.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

# Paths
BASE_DIR = Path(__file__).parent.parent
DB_FILE = BASE_DIR / "data" / "stories.db"
OUTPUT_DIR = BASE_DIR / "output"

def generate_rss(num_stories: int = 30) -> str:
    """Generate RSS feed XML from top stories"""
    
    conn = sqlite3.connect(DB_FILE)
    
    # Get top scored stories from the last 48 hours
    stories = conn.execute("""
        SELECT title, url, source, summary, published, score, headline
        FROM stories
        WHERE score >= 25
        AND published > datetime('now', '-48 hours')
        ORDER BY score DESC, published DESC
        LIMIT ?
    """, (num_stories,)).fetchall()
    
    conn.close()
    
    # Build RSS XML
    rss = Element('rss', version='2.0')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
    
    channel = SubElement(rss, 'channel')
    
    # Channel metadata
    SubElement(channel, 'title').text = 'CassadyNet - AI News'
    SubElement(channel, 'link').text = 'https://cassadynet.com'
    SubElement(channel, 'description').text = 'Breaking AI news from around the globe. Curated by AI, delivered fast.'
    SubElement(channel, 'language').text = 'en-us'
    SubElement(channel, 'lastBuildDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')
    SubElement(channel, 'ttl').text = '60'  # Time to live in minutes
    
    # Atom self-link (for feed validators)
    atom_link = SubElement(channel, 'atom:link')
    atom_link.set('href', 'https://cassadynet.com/feed.xml')
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')
    
    # Image
    image = SubElement(channel, 'image')
    SubElement(image, 'url').text = 'https://cassadynet.com/logo.png'
    SubElement(image, 'title').text = 'CassadyNet'
    SubElement(image, 'link').text = 'https://cassadynet.com'
    
    # Add stories as items
    for title, url, source, summary, published, score, headline in stories:
        item = SubElement(channel, 'item')
        
        # Use AI-generated headline if available, otherwise original title
        display_title = headline if headline else title
        SubElement(item, 'title').text = display_title
        SubElement(item, 'link').text = url
        SubElement(item, 'guid', isPermaLink='true').text = url
        
        # Description - include source attribution
        desc = f"[{source}] "
        if summary:
            desc += summary[:500]
        else:
            desc += title
        SubElement(item, 'description').text = desc
        
        # Source
        source_elem = SubElement(item, 'source', url='https://cassadynet.com/feed.xml')
        source_elem.text = 'CassadyNet'
        
        # Publication date
        if published:
            try:
                pub_dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
                SubElement(item, 'pubDate').text = pub_dt.strftime('%a, %d %b %Y %H:%M:%S +0000')
            except (ValueError, TypeError):
                SubElement(item, 'pubDate').text = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    # Pretty print
    xml_str = tostring(rss, encoding='unicode')
    pretty_xml = minidom.parseString(xml_str).toprettyxml(indent='  ')
    
    # Remove extra XML declaration line that minidom adds
    lines = pretty_xml.split('\n')
    if lines[0].startswith('<?xml'):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    
    return '\n'.join(lines)


def main():
    """Generate and save RSS feed"""
    
    print("📡 Generating RSS feed...")
    
    # Generate feed
    rss_content = generate_rss(30)
    
    # Save to output directory
    output_file = OUTPUT_DIR / "feed.xml"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rss_content)
    
    print(f"✅ RSS feed saved to {output_file}")
    print(f"   URL: https://cassadynet.com/feed.xml")


if __name__ == "__main__":
    main()
