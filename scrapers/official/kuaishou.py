"""快手招聘抓取器——campus.kuaishou.cn"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class KuaishouScraper(BrowserAPIScraper):
    """快手专用抓取器。"""

    source_platform = "kuaishou_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
