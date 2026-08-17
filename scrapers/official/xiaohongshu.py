"""小红书招聘抓取器——job.xiaohongshu.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class XiaohongshuScraper(BrowserAPIScraper):
    """小红书专用抓取器。"""

    source_platform = "xiaohongshu_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
