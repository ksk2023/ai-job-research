"""出门问问招聘抓取器——www.chumenwenwen.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class MobvoiScraper(BrowserAPIScraper):
    """出门问问专用抓取器。"""

    source_platform = "mobvoi_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
