"""第四范式招聘抓取器——www.4paradigm.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class Paradigm4Scraper(BrowserAPIScraper):
    """第四范式专用抓取器。"""

    source_platform = "4paradigm_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
