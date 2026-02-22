#!/usr/bin/env python3
"""
CassadyNet - Deep Analysis Generator
Creates debate-style analysis articles for clustered story topics.
Presents two opposing perspectives - lets reader decide.
"""

import sqlite3
import json
import os
import re
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
ANALYSIS_DIR = BASE_DIR / "output" / "analysis"
ANALYSIS_INDEX_FILE = BASE_DIR / "data" / "analysis_index.json"

# Template for analysis pages
ANALYSIS_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{{META_DESCRIPTION}}">
    <meta name="keywords" content="AI news, {{TITLE}}, artificial intelligence, tech analysis">
    <meta name="author" content="CassadyNet">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://cassadynet.com{{PAGE_URL}}">
    <meta property="og:title" content="{{TITLE}} - CassadyNet Poll">
    <meta property="og:description" content="{{META_DESCRIPTION}} Take the poll and share your opinion!">
    <meta property="og:url" content="https://cassadynet.com{{PAGE_URL}}">
    <meta property="og:type" content="article">
    <meta property="og:site_name" content="CassadyNet">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{{TITLE}} - CassadyNet Poll">
    <meta name="twitter:description" content="{{META_DESCRIPTION}}">
    <title>{{TITLE}} - CassadyNet Analysis</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Merriweather:wght@400;700&display=swap" rel="stylesheet">
    
    <!-- JSON-LD Structured Data -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{{TITLE}}",
        "description": "{{META_DESCRIPTION}}",
        "url": "https://cassadynet.com{{PAGE_URL}}",
        "datePublished": "{{ISO_DATE}}",
        "dateModified": "{{ISO_DATE}}",
        "author": {
            "@type": "Organization",
            "name": "CassadyNet"
        },
        "publisher": {
            "@type": "Organization",
            "name": "CassadyNet",
            "url": "https://cassadynet.com"
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": "https://cassadynet.com{{PAGE_URL}}"
        }
    }
    </script>
    
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --text-primary: #0f172a;
            --text-secondary: #64748b;
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
            line-height: 1.8;
            color: var(--text-primary);
            max-width: 800px;
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
        
        .article {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 40px;
            border: 1px solid var(--border);
        }
        
        .back-link {
            display: inline-block;
            margin-bottom: 20px;
            font-size: 14px;
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }
        
        .back-link:hover { text-decoration: underline; }
        
        .analysis-badge {
            display: inline-block;
            background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
            color: white;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 12px;
            border-radius: 20px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 16px;
        }
        
        .article-title {
            font-family: 'Merriweather', Georgia, serif;
            font-size: 32px;
            font-weight: 700;
            line-height: 1.3;
            margin-bottom: 16px;
        }
        
        .article-meta {
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 24px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }
        
        .debate-question {
            background: var(--bg-primary);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
            text-align: center;
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .article-content {
            font-size: 16px;
            line-height: 1.8;
        }
        
        .article-content p {
            margin-bottom: 16px;
            color: #334155;
        }
        
        .article-content ul, .article-content ol {
            margin: 16px 0;
            padding-left: 24px;
        }
        
        .article-content li {
            margin-bottom: 8px;
            padding-left: 8px;
        }
        
        .perspective-box ul, .perspective-box ol {
            margin: 12px 0;
            padding-left: 20px;
        }
        
        .perspective-box li {
            margin-bottom: 6px;
        }
        
        .perspective-box {
            border-radius: 8px;
            padding: 20px;
            margin: 24px 0;
        }
        
        .perspective-box.pro {
            background: rgba(16, 185, 129, 0.1);
            border-left: 4px solid var(--pro-color);
        }
        
        .perspective-box.con {
            background: rgba(239, 68, 68, 0.1);
            border-left: 4px solid var(--con-color);
        }
        
        .perspective-title {
            font-weight: 700;
            font-size: 16px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .perspective-box.pro .perspective-title { color: var(--pro-color); }
        .perspective-box.con .perspective-title { color: var(--con-color); }
        
        .bottom-line {
            background: var(--bg-primary);
            border-radius: 8px;
            padding: 20px;
            margin-top: 24px;
            font-weight: 500;
        }
        
        .bottom-line-title {
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        /* Poll Section */
        .poll-section {
            background: linear-gradient(135deg, #f0f9ff 0%, #f5f3ff 100%);
            border-radius: 12px;
            padding: 28px;
            margin: 32px 0;
            border: 2px solid var(--accent);
        }
        
        .poll-title {
            font-size: 18px;
            font-weight: 700;
            text-align: center;
            margin-bottom: 20px;
            color: var(--text-primary);
        }
        
        .poll-buttons {
            display: flex;
            gap: 16px;
            justify-content: center;
            margin-bottom: 16px;
        }
        
        .poll-btn {
            flex: 1;
            max-width: 200px;
            padding: 16px 24px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .poll-btn.pro {
            background: var(--pro-color);
            color: white;
        }
        
        .poll-btn.pro:hover {
            background: #059669;
            transform: translateY(-2px);
        }
        
        .poll-btn.con {
            background: var(--con-color);
            color: white;
        }
        
        .poll-btn.con:hover {
            background: #dc2626;
            transform: translateY(-2px);
        }
        
        .poll-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        /* Poll Results */
        .poll-results {
            display: none;
        }
        
        .poll-results.show {
            display: block;
        }
        
        .results-bar {
            height: 40px;
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            margin-bottom: 12px;
            background: var(--border);
        }
        
        .results-bar .pro-bar {
            background: var(--pro-color);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 14px;
            transition: width 0.5s ease;
        }
        
        .results-bar .con-bar {
            background: var(--con-color);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 14px;
            transition: width 0.5s ease;
        }
        
        .results-stats {
            display: flex;
            justify-content: space-between;
            font-size: 14px;
            color: var(--text-secondary);
        }
        
        .results-total {
            text-align: center;
            margin-top: 12px;
            font-size: 13px;
            color: var(--text-light);
        }
        
        .poll-message {
            text-align: center;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 16px;
            display: none;
        }
        
        .poll-message.show {
            display: block;
        }
        
        .poll-message.error {
            background: #fef2f2;
            color: var(--con-color);
        }
        
        .poll-message.success {
            background: #f0fdf4;
            color: var(--pro-color);
        }
        
        /* Share Section */
        .share-section {
            background: var(--bg-primary);
            border-radius: 12px;
            padding: 24px;
            margin: 24px 0;
            text-align: center;
        }
        
        .share-title {
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .share-subtitle {
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 16px;
        }
        
        .share-buttons {
            display: flex;
            gap: 12px;
            justify-content: center;
            flex-wrap: wrap;
        }
        
        .share-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
            cursor: pointer;
            border: none;
        }
        
        .share-btn:hover {
            transform: translateY(-2px);
        }
        
        .share-btn.facebook {
            background: #1877f2;
            color: white;
        }
        
        .share-btn.twitter {
            background: #0f1419;
            color: white;
        }
        
        .share-btn.linkedin {
            background: #0a66c2;
            color: white;
        }
        
        .share-btn.copy {
            background: var(--border);
            color: var(--text-primary);
        }
        
        .share-btn.copy.copied {
            background: var(--pro-color);
            color: white;
        }
        
        .sources-section {
            margin-top: 32px;
            padding-top: 24px;
            border-top: 1px solid var(--border);
        }
        
        .sources-section h2 {
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 12px;
        }
        
        .source-item {
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }
        
        .source-item:last-child { border-bottom: none; }
        
        .source-item a {
            color: var(--accent);
            text-decoration: none;
        }
        
        .source-item a:hover { text-decoration: underline; }
        
        .source-meta {
            font-size: 12px;
            color: var(--text-secondary);
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
        
        @media (max-width: 600px) {
            .article { padding: 24px; }
            .article-title { font-size: 24px; }
            .site-title { font-size: 32px; }
            .poll-buttons { flex-direction: column; }
            .poll-btn { max-width: 100%; }
            .share-buttons { flex-direction: column; }
            .share-btn { justify-content: center; }
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
    
    <article class="article">
        <a href="/" class="back-link">← Back to Headlines</a>
        
        <h1 class="article-title">{{TITLE}}</h1>
        
        <div class="article-meta">
            {{STORY_COUNT}} sources · {{DATE}} · 3 min read
        </div>
        
        <div class="debate-question">{{DEBATE_QUESTION}}</div>
        
        <div class="article-content">
            {{CONTENT}}
        </div>
        
        <!-- Poll Section (only for poll-type analyses) -->
        <div class="poll-section" id="pollSection" data-poll-id="{{POLL_ID}}" data-analysis-type="{{ANALYSIS_TYPE}}">
            <div class="poll-title">{{DEBATE_QUESTION}}</div>
            
            <div class="poll-message" id="pollMessage"></div>
            
            <div class="poll-buttons" id="pollButtons">
                <button class="poll-btn pro" onclick="castVote('pro')">👍 {{BUTTON_A}}</button>
                <button class="poll-btn con" onclick="castVote('con')">👎 {{BUTTON_B}}</button>
            </div>
            
            <div class="poll-results" id="pollResults">
                <div class="results-bar">
                    <div class="pro-bar" id="proBar" style="width: 50%">50%</div>
                    <div class="con-bar" id="conBar" style="width: 50%">50%</div>
                </div>
                <div class="results-stats">
                    <span>👍 {{BUTTON_A}}: <strong id="proCount">0</strong></span>
                    <span>👎 {{BUTTON_B}}: <strong id="conCount">0</strong></span>
                </div>
                <div class="results-total">Total votes: <span id="totalVotes">0</span></div>
            </div>
        </div>
        
        <!-- Share Section -->
        <div class="share-section">
            <div class="share-title">Get Your Friends' Opinion</div>
            <div class="share-subtitle">Share this poll and see if they agree with you!</div>
            <div class="share-buttons">
                <a href="#" onclick="shareOnFacebook(); return false;" class="share-btn facebook">
                    <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
                    Facebook
                </a>
                <a href="#" onclick="shareOnTwitter(); return false;" class="share-btn twitter">
                    <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                    X / Twitter
                </a>
                <a href="#" onclick="shareOnLinkedIn(); return false;" class="share-btn linkedin">
                    <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
                    LinkedIn
                </a>
                <button class="share-btn copy" onclick="copyLink()" id="copyBtn">
                    <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
                    Copy Link
                </button>
            </div>
        </div>
        
        <div class="sources-section">
            <h2>Sources</h2>
            {{SOURCES}}
        </div>
    </article>
    
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
    
    <script>
        const POLL_API = '/poll/api.php';
        const pollSection = document.getElementById('pollSection');
        const pollId = pollSection.dataset.pollId;
        const analysisType = pollSection.dataset.analysisType;
        
        // Generate a simple browser fingerprint for additional duplicate detection
        function getFingerprint() {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            ctx.textBaseline = 'top';
            ctx.font = '14px Arial';
            ctx.fillText('CassadyNet', 2, 2);
            const dataUrl = canvas.toDataURL();
            
            const fp = [
                navigator.userAgent,
                navigator.language,
                screen.width + 'x' + screen.height,
                new Date().getTimezoneOffset(),
                dataUrl.slice(-50)
            ].join('|');
            
            // Simple hash
            let hash = 0;
            for (let i = 0; i < fp.length; i++) {
                const char = fp.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash;
            }
            return hash.toString(36);
        }
        
        const fingerprint = getFingerprint();
        
        // Hide poll section for summary-type analyses
        if (analysisType === 'summary') {
            pollSection.style.display = 'none';
        }
        
        // Check if user already voted on page load
        async function checkVoteStatus() {
            if (analysisType === 'summary') return;
            
            try {
                const response = await fetch(`${POLL_API}?poll_id=${encodeURIComponent(pollId)}&fingerprint=${fingerprint}`);
                if (!response.ok) {
                    console.error('Poll API error:', response.status);
                    return;
                }
                const data = await response.json();
                
                if (data.voted) {
                    showResults(data.results);
                }
            } catch (error) {
                console.error('Error checking vote status:', error);
            }
        }
        
        async function castVote(vote) {
            const buttons = document.querySelectorAll('.poll-btn');
            buttons.forEach(btn => btn.disabled = true);
            
            try {
                const response = await fetch(POLL_API, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        poll_id: pollId,
                        vote: vote,
                        fingerprint: fingerprint
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.success) {
                    showMessage('Thanks for voting!', 'success');
                    showResults(data.results);
                } else {
                    showMessage(data.error || 'Something went wrong', 'error');
                    if (data.voted && data.results) {
                        showResults(data.results);
                    } else {
                        buttons.forEach(btn => btn.disabled = false);
                    }
                }
            } catch (error) {
                console.error('Error casting vote:', error);
                showMessage('Unable to submit vote. Please try again later.', 'error');
                buttons.forEach(btn => btn.disabled = false);
            }
        }
        
        function showMessage(text, type) {
            const msg = document.getElementById('pollMessage');
            msg.textContent = text;
            msg.className = 'poll-message show ' + type;
        }
        
        function showResults(results) {
            document.getElementById('pollButtons').style.display = 'none';
            
            const proPercent = results.pro_percent || 50;
            const conPercent = results.con_percent || 50;
            
            document.getElementById('proBar').style.width = proPercent + '%';
            document.getElementById('proBar').textContent = proPercent + '%';
            document.getElementById('conBar').style.width = conPercent + '%';
            document.getElementById('conBar').textContent = conPercent + '%';
            
            document.getElementById('proCount').textContent = results.pro || 0;
            document.getElementById('conCount').textContent = results.con || 0;
            document.getElementById('totalVotes').textContent = results.total || 0;
            
            document.getElementById('pollResults').classList.add('show');
        }
        
        function copyLink() {
            const url = window.location.href;
            navigator.clipboard.writeText(url).then(() => {
                const btn = document.getElementById('copyBtn');
                btn.classList.add('copied');
                btn.innerHTML = '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg> Copied!';
                setTimeout(() => {
                    btn.classList.remove('copied');
                    btn.innerHTML = '<svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg> Copy Link';
                }, 2000);
            });
        }
        
        function shareOnTwitter() {
            const url = encodeURIComponent(window.location.href);
            const text = encodeURIComponent(document.title + ' - Take the poll!');
            window.open('https://twitter.com/intent/tweet?url=' + url + '&text=' + text, '_blank', 'width=550,height=420');
        }
        
        function shareOnFacebook() {
            const url = encodeURIComponent(window.location.href);
            window.open('https://www.facebook.com/sharer/sharer.php?u=' + url, '_blank', 'width=550,height=420');
        }
        
        function shareOnLinkedIn() {
            const url = encodeURIComponent(window.location.href);
            window.open('https://www.linkedin.com/sharing/share-offsite/?url=' + url, '_blank', 'width=550,height=420');
        }
        
        // Check status on load
        checkVoteStatus();
    </script>
</body>
</html>
"""


def load_clusters() -> dict:
    """Load cluster data"""
    if CLUSTERS_FILE.exists():
        with open(CLUSTERS_FILE, 'r') as f:
            return json.load(f)
    return {'clusters': [], 'unclustered': []}


def load_analysis_index() -> dict:
    """Load index of generated analyses"""
    if ANALYSIS_INDEX_FILE.exists():
        with open(ANALYSIS_INDEX_FILE, 'r') as f:
            return json.load(f)
    return {'analyses': []}


def save_analysis_index(index: dict):
    """Save analysis index"""
    ANALYSIS_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ANALYSIS_INDEX_FILE, 'w') as f:
        json.dump(index, f, indent=2)


def slugify(text: str) -> str:
    """Convert text to URL-safe slug"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')[:50]


def generate_analysis_content(cluster: dict) -> tuple:
    """Generate debate-style analysis. Returns (debate_question, content, analysis_type)"""
    
    client = Anthropic()
    
    # Prepare source material
    sources_text = "\n\n".join([
        f"SOURCE: {s['source']}\nTITLE: {s['headline'] or s['title']}\nSUMMARY: {s.get('summary', 'No summary')}"
        for s in cluster['stories']
    ])
    
    prompt = f"""Review the following articles and identify the central theme or real-world issue they collectively highlight. Summarize the shared topic clearly and objectively.

TOPIC: {cluster['topic']}
DESCRIPTION: {cluster['description']}

SOURCE MATERIAL:
{sources_text}

FIRST, decide the type:
- POLL: If there's a genuine debate with two valid sides (privacy vs innovation, regulation vs freedom, corporate vs public interest, etc.)
- SUMMARY: If it's just news without a clear debate (product launch, research findings, company news)

FOR POLL TYPE:
Create one short, neutral poll question that:
- Directly reflects the key issue raised in the articles
- Feels natural and conversational rather than formulaic
- Is concise (ideally under 14 words)
- Is phrased as a QUESTION that presents TWO clear options
- Is suitable for both general readers and tech-savvy audiences
- Is specific to the incident/events described, NOT a generic opinion

Also provide TWO SHORT BUTTON LABELS (1-2 words each) that represent the opposing viewpoints.

CRITICAL BUTTON LABEL RULES:
The button labels MUST directly answer the question asked:
- If the question is "Should X happen?" → Buttons must be "Yes" / "No"
- If the question is "Is this A or B?" → Buttons must be "A" / "B"
- If the question is "Who is responsible, X or Y?" → Buttons must be "X" / "Y"

WRONG: Question "Should Apple remove X?" with buttons "Remove" / "Keep" (doesn't answer the question)
RIGHT: Question "Should Apple remove X?" with buttons "Yes" / "No" (directly answers the question)
RIGHT: Question "Should X stay in app stores or be removed?" with buttons "Stay" / "Remove" (matches the options in question)

Examples of GOOD poll questions with MATCHING button labels:
- Question: "Is OpenAI's massive spending a sign of strength or desperation?"
  Button A: "Strength" | Button B: "Desperation" ✓ (matches "strength or desperation")
- Question: "Should regulators force X to remove Grok?"
  Button A: "Yes" | Button B: "No" ✓ (answers "Should...?")
- Question: "Who bears more responsibility for the UK police AI scandal?"
  Button A: "Microsoft" | Button B: "The Police" ✓ (matches "Who...?")
- Question: "Will OpenAI's restructuring help or hurt AI safety?"
  Button A: "Help" | Button B: "Hurt" ✓ (matches "help or hurt")

The question should split opinion roughly 50/50 - reasonable people should be able to argue either side convincingly.

Then write the analysis:
1. Brief context (2-3 sentences about what specifically happened)
2. THE CASE FOR [Button A label] - Why someone would choose this option, based on the specific facts
3. THE CASE FOR [Button B label] - Why someone would choose this option, based on the specific facts
4. THE BOTTOM LINE - neutral, "You decide"

FOR SUMMARY TYPE:
1. No debate question
2. What happened (2-3 sentences as a paragraph)
3. Why it matters (2-3 sentences as a paragraph)
4. What's next (1-2 sentences as a paragraph)

IMPORTANT FORMATTING RULES:
- Do NOT use bullet points or lists
- Write in flowing paragraphs only
- Keep it SHORT - under 350 words total
- Be punchy and engaging

Output format:
TYPE: [POLL or SUMMARY]
DEBATE_QUESTION: [A thought-provoking question under 14 words, or NONE if summary]
BUTTON_A: [First option label, 1-2 words]
BUTTON_B: [Second option label, 1-2 words]

<p>[Context paragraph explaining what specifically happened]</p>

<div class="perspective-box pro">
<div class="perspective-title">✓ The Case For [Button A]</div>
<p>[Why someone would choose Button A based on these specific facts - as ONE flowing paragraph - no bullets]</p>
</div>

<div class="perspective-box con">
<div class="perspective-title">✗ The Case For [Button B]</div>
<p>[Why someone would choose Button B based on these specific facts - as ONE flowing paragraph - no bullets]</p>
</div>

<div class="bottom-line">
<div class="bottom-line-title">The Bottom Line</div>
<p>[One neutral sentence ending with "You decide." or similar]</p>
</div>"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = response.content[0].text
    
    # Extract type
    analysis_type = "poll"  # default
    if "TYPE: SUMMARY" in content or "TYPE:SUMMARY" in content:
        analysis_type = "summary"
    
    # Extract debate question and button labels
    debate_question = ""
    button_a = "Yes"  # defaults
    button_b = "No"
    
    lines = content.split('\n')
    for line in lines:
        if line.startswith("TYPE:"):
            content = content.replace(line, "").strip()
        elif line.startswith("DEBATE_QUESTION:"):
            dq = line.replace("DEBATE_QUESTION:", "").strip()
            if dq.upper() != "NONE":
                debate_question = dq
            content = content.replace(line, "").strip()
        elif line.startswith("BUTTON_A:"):
            button_a = line.replace("BUTTON_A:", "").strip()
            content = content.replace(line, "").strip()
        elif line.startswith("BUTTON_B:"):
            button_b = line.replace("BUTTON_B:", "").strip()
            content = content.replace(line, "").strip()
    
    # CRITICAL: Extract button labels from the question itself to ensure consistency
    # Pattern: "Is X a sign of A or B?" or "Will X help or hurt?" or "driving A or creating a B?"
    import re
    
    # Try multiple patterns to extract "A or B" options
    button_extracted = False
    
    # Pattern 1: "A or [optional words] B?" - handles hyphenated words like "bubble-driven"
    # Uses [\w-]+ to match hyphenated words
    or_match = re.search(r'([\w-]+)\s+or\s+(?:[\w-]+\s+)*?([\w-]+)\?', debate_question, re.IGNORECASE)

    if or_match:
        option_a = or_match.group(1).strip()
        option_b = or_match.group(2).strip()

        # Filter out common filler words that aren't real options
        filler_words = {'a', 'an', 'the', 'of', 'is', 'are', 'be', 'to', 'for', 'it', 'this', 'that', 'being'}

        if option_a.lower() not in filler_words and option_b.lower() not in filler_words:
            # Capitalize first letter, preserve rest (for hyphenated words)
            button_a = option_a[0].upper() + option_a[1:] if option_a else option_a
            button_b = option_b[0].upper() + option_b[1:] if option_b else option_b
            button_extracted = True
            logger.info(f"  Extracted from question: '{button_a}' or '{button_b}'")
        else:
            logger.info(f"  Filler word detected in '{option_a}' or '{option_b}', trying simpler pattern")

    # Pattern 2: Simple "A or B" without extra words (fallback) - also handles hyphenated words
    if not button_extracted:
        simple_match = re.search(r'([\w-]+)\s+or\s+([\w-]+)', debate_question, re.IGNORECASE)
        if simple_match:
            option_a = simple_match.group(1).strip()
            option_b = simple_match.group(2).strip()

            filler_words = {'a', 'an', 'the', 'of', 'is', 'are', 'be', 'to', 'for', 'it', 'this', 'that', 'being'}

            if option_a.lower() not in filler_words and option_b.lower() not in filler_words:
                # Capitalize first letter, preserve rest (for hyphenated words)
                button_a = option_a[0].upper() + option_a[1:] if option_a else option_a
                button_b = option_b[0].upper() + option_b[1:] if option_b else option_b
                button_extracted = True
                logger.info(f"  Extracted (simple): '{button_a}' or '{button_b}'")
    
    if not button_extracted:
        logger.info(f"  No A/B pattern found, using Yes/No")
    
    # Clean up content
    content = content.strip()
    
    # Replace section titles with actual button labels
    # Find and replace the pro section title
    pro_pattern = r'<div class="perspective-title">✓ The Case For [^<]+</div>'
    pro_replacement = f'<div class="perspective-title">✓ The Case For {button_a}</div>'
    content = re.sub(pro_pattern, pro_replacement, content)
    
    # Find and replace the con section title
    con_pattern = r'<div class="perspective-title">✗ The Case For [^<]+</div>'
    con_replacement = f'<div class="perspective-title">✗ The Case For {button_b}</div>'
    content = re.sub(con_pattern, con_replacement, content)
    
    # Wrap context in paragraph if not already
    if not content.startswith("<"):
        parts = content.split("<div", 1)
        if len(parts) == 2:
            context = parts[0].strip()
            rest = "<div" + parts[1]
            content = f"<p>{context}</p>\n\n{rest}"
    
    return debate_question, content, analysis_type, button_a, button_b


def generate_analysis_page(cluster: dict, existing_poll: dict = None) -> dict:
    """Generate a full analysis page for a cluster.
    If existing_poll is provided, reuse the poll_id and question.
    """
    import re
    
    logger.info(f"Generating analysis for: {cluster['topic']}")
    
    # Check if we should reuse existing poll question
    if existing_poll and existing_poll.get('question'):
        logger.info(f"  Reusing existing poll question: {existing_poll['question'][:50]}...")
        debate_question = existing_poll['question']
        poll_id = existing_poll['poll_id']
        analysis_type = existing_poll.get('analysis_type', 'poll')
        
        # Still generate fresh content for the analysis
        _, content, _, _, _ = generate_analysis_content(cluster)
        
        # ALWAYS extract button labels from the question itself
        button_a = "Yes"  # defaults
        button_b = "No"
    else:
        # Generate new content and question
        debate_question, content, analysis_type, button_a, button_b = generate_analysis_content(cluster)
        
        # Create poll ID from slug and date
        slug = slugify(cluster['topic'])
        poll_id = f"{slug}-{datetime.now().strftime('%Y%m%d')}"
    
    # ALWAYS extract button labels from the question to ensure consistency
    button_extracted = False
    
    # Pattern 1: "A or [optional words] B?" - handles hyphenated words like "bubble-driven"
    or_match = re.search(r'([\w-]+)\s+or\s+(?:[\w-]+\s+)*?([\w-]+)\?', debate_question, re.IGNORECASE)

    if or_match:
        option_a = or_match.group(1).strip()
        option_b = or_match.group(2).strip()

        filler_words = {'a', 'an', 'the', 'of', 'is', 'are', 'be', 'to', 'for', 'it', 'this', 'that', 'being'}

        if option_a.lower() not in filler_words and option_b.lower() not in filler_words:
            # Capitalize first letter, preserve rest (for hyphenated words)
            button_a = option_a[0].upper() + option_a[1:] if option_a else option_a
            button_b = option_b[0].upper() + option_b[1:] if option_b else option_b
            button_extracted = True
            logger.info(f"  Button labels from question: '{button_a}' / '{button_b}'")

    # Pattern 2: Simple "A or B" fallback - also handles hyphenated words
    if not button_extracted:
        simple_match = re.search(r'([\w-]+)\s+or\s+([\w-]+)', debate_question, re.IGNORECASE)
        if simple_match:
            option_a = simple_match.group(1).strip()
            option_b = simple_match.group(2).strip()

            filler_words = {'a', 'an', 'the', 'of', 'is', 'are', 'be', 'to', 'for', 'it', 'this', 'that', 'being'}

            if option_a.lower() not in filler_words and option_b.lower() not in filler_words:
                # Capitalize first letter, preserve rest (for hyphenated words)
                button_a = option_a[0].upper() + option_a[1:] if option_a else option_a
                button_b = option_b[0].upper() + option_b[1:] if option_b else option_b
                logger.info(f"  Button labels (simple): '{button_a}' / '{button_b}'")
    
    # Replace section titles in content with actual button labels
    pro_pattern = r'<div class="perspective-title">✓ The Case For [^<]+</div>'
    pro_replacement = f'<div class="perspective-title">✓ The Case For {button_a}</div>'
    content = re.sub(pro_pattern, pro_replacement, content)
    
    con_pattern = r'<div class="perspective-title">✗ The Case For [^<]+</div>'
    con_replacement = f'<div class="perspective-title">✗ The Case For {button_b}</div>'
    content = re.sub(con_pattern, con_replacement, content)
    
    # Build sources HTML
    sources_html = ""
    for story in cluster['stories']:
        sources_html += f"""
        <div class="source-item">
            <a href="{story['url']}" target="_blank">{story['headline'] or story['title']}</a>
            <div class="source-meta">{story['source']}</div>
        </div>
        """
    
    # Generate page
    slug = slugify(cluster['topic'])
    filename = f"analysis-{slug}-{datetime.now().strftime('%Y%m%d')}.html"
    page_url = f"/analysis/{filename}"
    full_url = f"https://cassadynet.com{page_url}"
    
    # Share text for social - stronger call to action
    share_text = f"I just took this poll - what's your take? {cluster['topic']} | CassadyNet"
    
    html = ANALYSIS_TEMPLATE
    html = html.replace('{{TITLE}}', cluster['topic'])
    html = html.replace('{{META_DESCRIPTION}}', cluster['description'][:160])
    html = html.replace('{{STORY_COUNT}}', str(cluster['story_count']))
    html = html.replace('{{DATE}}', datetime.now().strftime('%B %d, %Y'))
    html = html.replace('{{ISO_DATE}}', datetime.now().strftime('%Y-%m-%dT%H:%M:%S+00:00'))
    html = html.replace('{{DEBATE_QUESTION}}', debate_question or "What's your take?")
    html = html.replace('{{BUTTON_A}}', button_a)
    html = html.replace('{{BUTTON_B}}', button_b)
    html = html.replace('{{CONTENT}}', content)
    html = html.replace('{{SOURCES}}', sources_html)
    html = html.replace('{{POLL_ID}}', poll_id)
    html = html.replace('{{ANALYSIS_TYPE}}', analysis_type)
    html = html.replace('{{PAGE_URL}}', page_url)
    html = html.replace('{{SHARE_URL}}', full_url.replace(':', '%3A').replace('/', '%2F'))
    html = html.replace('{{SHARE_TEXT}}', share_text.replace(' ', '%20'))
    
    # Hide debate question div for summaries
    if analysis_type == "summary":
        html = html.replace('<div class="debate-question">What\'s your take?</div>', '')
    
    # Save file
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = ANALYSIS_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    logger.info(f"  Saved: {filepath}")
    logger.info(f"  Type: {analysis_type}")
    logger.info(f"  Poll ID: {poll_id}")
    logger.info(f"  Buttons: {button_a} / {button_b}")
    
    return {
        'topic': cluster['topic'],
        'description': cluster['description'],
        'question': debate_question,
        'button_a': button_a,
        'button_b': button_b,
        'filename': filename,
        'filepath': str(filepath),
        'url': page_url,
        'story_count': cluster['story_count'],
        'top_score': cluster['top_score'],
        'analysis_type': analysis_type,
        'poll_id': poll_id,
        'generated_at': datetime.now().isoformat()
    }


def main():
    import argparse
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    
    from poll_tracker import (
        load_active_polls, 
        find_matching_active_poll, 
        register_new_poll,
        update_poll_tracking,
        get_archived_polls
    )
    
    parser = argparse.ArgumentParser(description="Generate deep analysis articles")
    parser.add_argument("--topic", type=str, help="Generate for specific topic only")
    parser.add_argument("--all", action="store_true", help="Regenerate all clusters")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("CassadyNet Deep Analysis Generator")
    logger.info("=" * 60)
    
    # Load clusters
    cluster_data = load_clusters()
    clusters = cluster_data.get('clusters', [])
    
    if not clusters:
        logger.info("No clusters found. Run cluster_stories.py first.")
        return
    
    logger.info(f"Found {len(clusters)} topic clusters")
    
    # Load existing analysis index and active polls
    index = load_analysis_index()
    active_polls_data = load_active_polls()
    active_polls = active_polls_data.get('polls', [])
    
    # Determine which clusters to process
    if args.topic:
        clusters = [c for c in clusters if args.topic.lower() in c['topic'].lower()]
        if not clusters:
            logger.error(f"No cluster found matching: {args.topic}")
            return
    
    # Generate analyses
    new_analyses = []
    for cluster in clusters[:2]:  # Only top 2 clusters
        topic = cluster['topic']
        description = cluster.get('description', '')
        
        # Check if this topic matches an existing active poll
        existing_poll = find_matching_active_poll(topic, description, active_polls)
        
        if args.dry_run:
            if existing_poll:
                logger.info(f"Would update (reusing poll): {topic}")
            else:
                logger.info(f"Would generate (new poll): {topic} ({cluster['story_count']} stories)")
            continue
        
        # Generate analysis page (with existing poll info if available)
        analysis = generate_analysis_page(cluster, existing_poll)
        new_analyses.append(analysis)
        
        # Register/update the poll
        register_new_poll(
            topic=topic,
            description=description,
            question=analysis.get('question', ''),
            poll_id=analysis['poll_id'],
            analysis_url=analysis['url'],
            analysis_type=analysis['analysis_type'],
            button_a=analysis.get('button_a', 'Yes'),
            button_b=analysis.get('button_b', 'No')
        )
    
    # Update poll tracking (archive old polls, etc.)
    if not args.dry_run:
        update_poll_tracking(clusters, index)
    
    # Update analysis index
    if new_analyses and not args.dry_run:
        updated_topics = {a['topic'] for a in new_analyses}
        index['analyses'] = [a for a in index.get('analyses', []) if a['topic'] not in updated_topics]
        index['analyses'].extend(new_analyses)
        index['last_updated'] = datetime.now().isoformat()
        save_analysis_index(index)
        
        logger.info("-" * 60)
        logger.info(f"Generated {len(new_analyses)} analysis articles")
        for a in new_analyses:
            logger.info(f"  • {a['topic']}: {a['url']}")


if __name__ == "__main__":
    main()
