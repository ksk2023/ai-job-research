"""360招聘抓取器——hr.360.cn"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class Qihoo360Scraper(BrowserAPIScraper):
    """360专用抓取器。"""

    source_platform = "360_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
