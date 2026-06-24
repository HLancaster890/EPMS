"""
EPMS Browser Activity Monitor.
Detects active browser windows across Chrome, Edge, Firefox, and Brave.
Extracts URL, domain, page title, and session info from window titles and
optional browser extension API polling.
"""

import logging
import re
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Browser process names and their identifying patterns
BROWSER_PATTERNS: Dict[str, Dict[str, Any]] = {
    "chrome": {
        "process_names": ["chrome.exe", "google-chrome", "google-chrome-stable", "chromium.exe", "chromium-browser"],
        "title_pattern": r"^(.*)\s*-\s*(Google Chrome|Chromium)$",
        "url_title_separator": " - ",
        "icon": "chrome",
    },
    "edge": {
        "process_names": ["msedge.exe", "microsoft-edge", "microsoftedge.exe"],
        "title_pattern": r"^(.*)\s*-\s*(Microsoft Edge|Edge)$",
        "url_title_separator": " - ",
        "icon": "edge",
    },
    "firefox": {
        "process_names": ["firefox.exe", "firefox", "firefoxdeveloperedition.exe", "nightly.exe"],
        "title_pattern": r"^(.*)\s*[-–]\s*(Mozilla Firefox|Firefox)$",
        "url_title_separator": " — ",
        "icon": "firefox",
    },
    "brave": {
        "process_names": ["brave.exe", "brave-browser", "brave"],
        "title_pattern": r"^(.*)\s*[-–]\s*(Brave|Brave Browser)$",
        "url_title_separator": " - ",
        "icon": "brave",
    },
}

# Known non-page tabs to filter out
FILTERED_TITLES = [
    "New Tab", "New tab", "about:blank", "chrome://", "edge://",
    "about:newtab", "Settings", "Extensions", "Bookmarks",
    "History", "Downloads", "chrome-extension://",
]

# Domain categorization
PRODUCTIVE_DOMAINS = {
    # Development
    "github.com", "gitlab.com", "bitbucket.org", "stackoverflow.com",
    "stackexchange.com", "docs.microsoft.com", "learn.microsoft.com",
    "developer.mozilla.org", "npmjs.com", "pypi.org", "crates.io",
    "docker.com", "hub.docker.com", "kubernetes.io",
    # Work/Communication
    "outlook.com", "outlook.office.com", "mail.google.com",
    "teams.microsoft.com", "slack.com", "discord.com",
    "zoom.us", "meet.google.com", "webex.com",
    # Project Management
    "notion.so", "miro.com", "confluence.com", "atlassian.com",
    "jira.com", "trello.com", "asana.com", "monday.com",
    "clickup.com", "linear.app", "basecamp.com",
    # Cloud
    "aws.amazon.com", "console.aws.amazon.com", "portal.azure.com",
    "console.cloud.google.com", "digitalocean.com", "vercel.com",
    "netlify.com", "heroku.com", "railway.app",
    # AI
    "chat.openai.com", "claude.ai", "github.com/features/copilot",
    "perplexity.ai", "gemini.google.com", "copilot.microsoft.com",
    # Documentation
    "readthedocs.io", "git-scm.com", "dev.to", "medium.com",
}

DISTRACTING_DOMAINS = {
    "facebook.com", "twitter.com", "x.com", "instagram.com",
    "reddit.com", "tiktok.com", "snapchat.com", "pinterest.com",
    "youtube.com", "netflix.com", "hulu.com", "twitch.tv",
    "spotify.com", "disneyplus.com", "primevideo.com",
    "amazon.com", "ebay.com", "walmart.com", "etsy.com",
    "bestbuy.com", "target.com", "aliexpress.com",
}


@dataclass
class BrowserTabInfo:
    """Information about an active browser tab."""
    browser_name: str = ""
    browser_version: str = ""
    url: str = ""
    domain: str = ""
    page_title: str = ""
    tab_id: str = ""
    window_id: str = ""
    is_active: bool = True
    category: str = "uncategorized"
    is_productive: bool = True
    duration_seconds: float = 0.0
    timestamp: str = ""


def detect_browser_from_process(process_name: str) -> Optional[str]:
    """Detect which browser a process name belongs to."""
    proc_lower = process_name.lower()
    for browser_name, config in BROWSER_PATTERNS.items():
        if proc_lower in [p.lower() for p in config["process_names"]]:
            return browser_name
        # Also check partial match (e.g. "chrome.exe" matches "chrome")
        for p in config["process_names"]:
            if p.lower() in proc_lower or proc_lower in p.lower():
                return browser_name
    return None


def extract_domain_from_title(title: str, browser: str) -> str:
    """Attempt to extract a domain from a browser window title."""
    if not title:
        return ""

    # Remove common browser title suffixes
    for browser_name, config in BROWSER_PATTERNS.items():
        separator = config.get("url_title_separator", " - ")
        browser_suffixes = config["process_names"]
        for suffix in browser_suffixes:
            # Try to strip " - Google Chrome", " — Mozilla Firefox", etc.
            idx = title.rfind(separator)
            if idx > 0:
                title_part = title[:idx].strip()
                # Check if the remaining part is a URL or domain
                if _looks_like_domain(title_part):
                    return title_part
                # Try to find domain-like patterns in the title
                domain = _extract_domain_from_text(title_part)
                if domain:
                    return domain

    # Fallback: try regex for domain patterns anywhere in title
    return _extract_domain_from_text(title)


def _looks_like_domain(text: str) -> bool:
    """Check if text looks like a domain name."""
    domain_pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(/[^\s]*)?$'
    return bool(re.match(domain_pattern, text.strip()))


def _extract_domain_from_text(text: str) -> str:
    """Extract domain name from arbitrary text using regex."""
    # Match common URL/domain patterns
    patterns = [
        r'(?:https?://)?(?:www\.)?([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(?:/[^\s]*)?',
        r'([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?\.)+(com|org|net|io|dev|app|ai|co|gov|edu|info)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            domain = match.group(0)
            # Strip protocol and www
            domain = re.sub(r'^https?://(www\.)?', '', domain)
            # Get just the domain (before first /)
            domain = domain.split('/')[0]
            return domain.lower()
    return ""


def classify_domain(domain: str) -> tuple:
    """Classify a domain as productive, distracting, or neutral."""
    if not domain:
        return ("uncategorized", True)

    domain_lower = domain.lower().strip()

    # Check against productive domains
    for prod_domain in PRODUCTIVE_DOMAINS:
        if domain_lower == prod_domain or domain_lower.endswith("." + prod_domain):
            return ("work", True)

    # Check against distracting domains
    for dist_domain in DISTRACTING_DOMAINS:
        if domain_lower == dist_domain or domain_lower.endswith("." + dist_domain):
            return ("distracting", False)

    return ("uncategorized", True)


def is_browser_process(process_name: str) -> bool:
    """Check if a process name corresponds to a known browser."""
    return detect_browser_from_process(process_name) is not None


def get_browser_tab_info(window_title: str, process_name: str) -> BrowserTabInfo:
    """Extract browser tab information from window title and process name."""
    info = BrowserTabInfo()

    browser = detect_browser_from_process(process_name)
    if not browser:
        return info

    info.browser_name = browser.capitalize()

    # Check if title should be filtered out
    title_lower = window_title.lower()
    for filtered in FILTERED_TITLES:
        if filtered.lower() in title_lower:
            info.page_title = window_title
            return info

    # Extract page title and domain
    config = BROWSER_PATTERNS.get(browser, {})
    separator = config.get("url_title_separator", " - ")

    # Try to split by browser's separator pattern
    # Firefox uses " — " (em dash), Chrome uses " - " (en dash)
    for sep in [" — ", " - ", " – ", " | "]:
        if sep in window_title:
            parts = window_title.rsplit(sep, 1)
            if len(parts) == 2:
                info.page_title = parts[0].strip()
                domain_str = parts[1].strip()
                # Check if it's a known browser name suffix
                is_suffix = any(
                    pattern.lower() == domain_str.lower() or
                    pattern.lower().strip('.exe') == domain_str.lower()
                    for pattern in config.get("process_names", [])
                )
                if is_suffix:
                    # The first part contains the meaningful info
                    if _looks_like_domain(info.page_title):
                        info.domain = info.page_title
                        info.url = f"https://{info.domain}"
                        info.page_title = ""
                    else:
                        # Try to extract domain from page title
                        domain = _extract_domain_from_text(info.page_title)
                        if domain:
                            info.domain = domain
                            info.url = f"https://{domain}"
                else:
                    # The suffix might be a domain
                    if _looks_like_domain(domain_str):
                        info.domain = domain_str
                        info.url = f"https://{domain_str}"
                    else:
                        domain = _extract_domain_from_text(domain_str)
                        if domain:
                            info.domain = domain
            break

    # If no domain found yet, try extracting from page title
    if not info.domain and info.page_title:
        domain = _extract_domain_from_text(info.page_title)
        if domain:
            info.domain = domain

    # If still no domain, use a fallback
    if not info.domain:
        info.domain = "unknown"

    # Classify the domain
    category, is_productive = classify_domain(info.domain)
    info.category = category
    info.is_productive = is_productive

    # Generate a synthetic URL if we have a domain
    if info.domain and info.domain != "unknown" and not info.url:
        info.url = f"https://{info.domain}"

    # Set timestamp
    info.timestamp = datetime.now(timezone.utc).isoformat()

    return info


def get_browser_activity_data(window_title: str, process_name: str) -> Dict[str, Any]:
    """Get structured browser activity data for API transmission."""
    tab_info = get_browser_tab_info(window_title, process_name)

    return {
        "timestamp": tab_info.timestamp,
        "browser_name": tab_info.browser_name,
        "domain": tab_info.domain,
        "url": tab_info.url,
        "page_title": tab_info.page_title if tab_info.page_title else window_title,
        "category": tab_info.category,
        "is_productive": tab_info.is_productive,
        "is_active": tab_info.is_active,
    }


# List of all supported browsers for reference
SUPPORTED_BROWSERS = [
    "Google Chrome",
    "Microsoft Edge",
    "Mozilla Firefox",
    "Brave Browser",
]
