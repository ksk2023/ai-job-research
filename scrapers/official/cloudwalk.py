"""云从科技招聘抓取器——www.cloudwalk.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class CloudWalkScraper(BrowserAPIScraper):
    """云从科技专用抓取器。"""

    source_platform = "cloudwalk_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
