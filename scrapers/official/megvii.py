"""旷视科技招聘抓取器——megvii.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class MegviiScraper(BrowserAPIScraper):
    """旷视科技专用抓取器。"""

    source_platform = "megvii_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
