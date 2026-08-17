"""依图科技招聘抓取器——www.yitutech.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class YituScraper(BrowserAPIScraper):
    """依图科技专用抓取器。"""

    source_platform = "yitu_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
