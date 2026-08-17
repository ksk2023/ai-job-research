"""商汤科技招聘抓取器——hr.sensetime.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class SenseTimeScraper(BrowserAPIScraper):
    """商汤科技专用抓取器。"""

    source_platform = "sensetime_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
