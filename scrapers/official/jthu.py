"""捷通华声招聘抓取器——www.jthu.cn"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class JTHUScraper(BrowserAPIScraper):
    """捷通华声专用抓取器。"""

    source_platform = "jthu_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
