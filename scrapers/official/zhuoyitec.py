"""追一科技招聘抓取器——www.zhuoyitec.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class ZhuoyiScraper(BrowserAPIScraper):
    """追一科技专用抓取器。"""

    source_platform = "zhuoyi_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
