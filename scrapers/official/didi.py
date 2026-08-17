"""滴滴招聘抓取器——talent.didiglobal.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class DiDiScraper(BrowserAPIScraper):
    """滴滴专用抓取器。"""

    source_platform = "didi_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
