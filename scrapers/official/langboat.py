"""澜舟科技招聘抓取器——www.langboat.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class LangboatScraper(BrowserAPIScraper):
    """澜舟科技专用抓取器。"""

    source_platform = "langboat_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
