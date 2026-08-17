"""月之暗面(Kimi)招聘抓取器——careers.kimi.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class MoonshotScraper(BrowserAPIScraper):
    """月之暗面专用抓取器。"""

    source_platform = "moonshot_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
