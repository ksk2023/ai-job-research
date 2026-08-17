"""海康威视招聘抓取器——campushr.hikvision.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class HikvisionScraper(BrowserAPIScraper):
    """海康威视专用抓取器。"""

    source_platform = "hikvision_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
