"""华为招聘抓取器——career.huawei.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class HuaweiScraper(BrowserAPIScraper):
    """华为专用抓取器。"""

    source_platform = "huawei_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
