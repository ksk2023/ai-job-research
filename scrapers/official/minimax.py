"""MiniMax招聘抓取器——www.minimaxi.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class MiniMaxScraper(BrowserAPIScraper):
    """MiniMax专用抓取器。"""

    source_platform = "minimax_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
