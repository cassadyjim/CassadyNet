#!/usr/bin/env python3
"""
CassadyNet - FTP Upload
Uploads generated HTML files to One.com hosting via FTP.
Analysis files go to /analysis/ subdirectory.
"""

import os
import ftplib
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"

# FTP Configuration
FTP_CONFIG = {
    'host': os.environ.get('SFTP_HOST', 'ftp.cegl4w2or.service.one'),
    'port': int(os.environ.get('SFTP_PORT', 21)),
    'username': os.environ.get('SFTP_USERNAME', 'cegl4w2or_ftp'),
    'password': os.environ.get('SFTP_PASSWORD', ''),
    'remote_dir': os.environ.get('SFTP_REMOTE_DIR', '/'),
}


def ftp_connect(config: dict) -> ftplib.FTP:
    """Create and return an FTP connection"""
    ftp = ftplib.FTP()
    ftp.connect(config['host'], config['port'], timeout=30)
    ftp.login(config['username'], config['password'])
    ftp.set_pasv(True)

    # Change to remote directory if specified
    if config['remote_dir'] and config['remote_dir'] != '/':
        try:
            ftp.cwd(config['remote_dir'])
        except ftplib.error_perm:
            print(f"⚠️  Remote directory {config['remote_dir']} not found, using root")

    return ftp


def ensure_dir(ftp: ftplib.FTP, directory: str):
    """Create directory on FTP server if it doesn't exist"""
    try:
        ftp.cwd(directory)
    except ftplib.error_perm:
        print(f"   Creating directory: {directory}")
        ftp.mkd(directory)
        ftp.cwd(directory)


def upload_files(files: list, config: dict = None, remote_subdir: str = None):
    """Upload files to FTP server"""

    config = config or FTP_CONFIG

    if not config['password']:
        raise ValueError("SFTP_PASSWORD environment variable not set")

    print(f"\n📤 Connecting to {config['host']}:{config['port']}...")

    ftp = ftp_connect(config)

    try:
        # Save root directory to return to it for each call
        root_dir = ftp.pwd()

        # If uploading to subdirectory, create it if needed
        if remote_subdir:
            ensure_dir(ftp, remote_subdir)

        # Upload each file
        for local_path in files:
            local_path = Path(local_path)

            if not local_path.exists():
                print(f"⚠️  File not found: {local_path}")
                continue

            remote_filename = local_path.name
            print(f"   Uploading {local_path.name}...")

            with open(local_path, 'rb') as f:
                ftp.storbinary(f'STOR {remote_filename}', f)

            print(f"   ✅ {remote_filename} uploaded")

        print(f"\n✅ All files uploaded successfully")

    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()


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
    """Test FTP connection without uploading"""

    config = FTP_CONFIG

    if not config['password']:
        print("❌ SFTP_PASSWORD environment variable not set")
        return False

    print(f"\n🔌 Testing connection to {config['host']}:{config['port']}...")

    try:
        ftp = ftp_connect(config)
        print(f"✅ Connected successfully!")
        print(f"\n📂 Remote directory contents:")
        for item in ftp.nlst():
            print(f"   {item}")
        ftp.quit()
        return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload site to One.com via FTP")
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
