"""微博招聘抓取器——career.sina.com.cn"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class WeiboScraper(BrowserAPIScraper):
    """微博专用抓取器。"""

    source_platform = "weibo_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
