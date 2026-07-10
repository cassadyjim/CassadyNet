#!/usr/bin/env python3
"""
CassadyNet - SFTP Upload
Uploads generated HTML files to One.com hosting via SFTP.
Analysis files go to /analysis/ subdirectory.
"""

import os
import paramiko
from pathlib import Path
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"

# SFTP Configuration
SFTP_CONFIG = {
    'host': os.environ.get('SFTP_HOST', 'ssh.cegl4w2or.service.one'),
    'port': int(os.environ.get('SFTP_PORT', 22)),
    'username': os.environ.get('SFTP_USERNAME', 'cegl4w2or_ssh'),
    'password': os.environ.get('SFTP_PASSWORD', ''),
    'remote_dir': os.environ.get('SFTP_REMOTE_DIR', '/'),
}


def upload_files(files: list, config: dict = None, remote_subdir: str = None):
    """Upload files to SFTP server"""

    config = config or SFTP_CONFIG

    if not config['password']:
        raise ValueError("SFTP_PASSWORD environment variable not set")

    print(f"\n📤 Connecting to {config['host']}...")

    # Create SFTP connection
    transport = paramiko.Transport((config['host'], config['port']))
    transport.connect(username=config['username'], password=config['password'])
    sftp = paramiko.SFTPClient.from_transport(transport)

    try:
        # Diagnostic: show where we land and what's here
        cwd = sftp.getcwd() or '/'
        print(f"🔍 SFTP landed in: {cwd}")
        print(f"🔍 Root contents: {sftp.listdir('.')}")
        # Peek inside webroots if it exists
        try:
            print(f"🔍 webroots/ contents: {sftp.listdir('webroots')}")
        except Exception:
            pass

        # Change to remote directory if specified
        if config['remote_dir'] and config['remote_dir'] != '/':
            try:
                sftp.chdir(config['remote_dir'])
                print(f"🔍 Changed to: {sftp.getcwd()} — contents: {sftp.listdir('.')}")
            except IOError:
                print(f"⚠️  Remote directory {config['remote_dir']} not found, using root")

        # If uploading to subdirectory, create it if needed
        if remote_subdir:
            try:
                sftp.chdir(remote_subdir)
            except IOError:
                # Directory doesn't exist, create it
                print(f"   Creating directory: {remote_subdir}")
                sftp.mkdir(remote_subdir)
                sftp.chdir(remote_subdir)

        # Upload each file
        for local_path in files:
            local_path = Path(local_path)

            if not local_path.exists():
                print(f"⚠️  File not found: {local_path}")
                continue

            remote_filename = local_path.name

            print(f"   Uploading {local_path.name}...")
            sftp.put(str(local_path), remote_filename)
            print(f"   ✅ {remote_filename} uploaded")

        print(f"\n✅ All files uploaded successfully")

    finally:
        sftp.close()
        transport.close()


def upload_site():
    """Upload all site files"""

    # Main site files (go to root)
    main_files = [
        OUTPUT_DIR / "index.html",
        OUTPUT_DIR / "privacy.html",
        OUTPUT_DIR / "about.html",
        OUTPUT_DIR / "sources.html",
        OUTPUT_DIR / "feed.xml",
        OUTPUT_DIR / "polls.html",
        OUTPUT_DIR / "sitemap.xml",
        OUTPUT_DIR / "robots.txt",
    ]

    # Filter to only existing files
    existing_main = [f for f in main_files if f.exists()]

    if existing_main:
        print(f"📁 Main site files:")
        for f in existing_main:
            print(f"   - {f.name}")
        upload_files(existing_main)

    # Analysis files (go to /analysis/ subdirectory)
    analysis_dir = OUTPUT_DIR / "analysis"
    if analysis_dir.exists():
        analysis_files = list(analysis_dir.glob("*.html"))
        if analysis_files:
            print(f"\n📁 Analysis files (→ /analysis/):")
            for f in analysis_files:
                print(f"   - {f.name}")
            upload_files(analysis_files, remote_subdir="analysis")

    return True


def test_connection():
    """Test SFTP connection without uploading"""

    config = SFTP_CONFIG

    if not config['password']:
        print("❌ SFTP_PASSWORD environment variable not set")
        print("\nSet it with:")
        print("  export SFTP_PASSWORD='your_password_here'")
        return False

    print(f"\n🔌 Testing connection to {config['host']}...")

    try:
        transport = paramiko.Transport((config['host'], config['port']))
        transport.connect(username=config['username'], password=config['password'])
        sftp = paramiko.SFTPClient.from_transport(transport)

        print(f"✅ Connected successfully!")
        print(f"\n📂 Remote directory contents:")
        for item in sftp.listdir():
            print(f"   {item}")

        sftp.close()
        transport.close()
        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload site to One.com via SFTP")
    parser.add_argument("--test", action="store_true", help="Test connection only")
    parser.add_argument("--file", type=str, help="Upload a specific file")
    parser.add_argument("--analysis", action="store_true", help="Upload only analysis files")

    args = parser.parse_args()

    if args.test:
        test_connection()
    elif args.file:
        upload_files([args.file])
    elif args.analysis:
        analysis_dir = OUTPUT_DIR / "analysis"
        if analysis_dir.exists():
            analysis_files = list(analysis_dir.glob("*.html"))
            if analysis_files:
                upload_files(analysis_files, remote_subdir="analysis")
            else:
                print("No analysis files found")
        else:
            print("Analysis directory not found")
    else:
        upload_site()
