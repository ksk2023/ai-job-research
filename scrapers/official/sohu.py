"""搜狐招聘抓取器——hr.sohu.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class SohuScraper(BrowserAPIScraper):
    """搜狐专用抓取器。"""

    source_platform = "sohu_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
