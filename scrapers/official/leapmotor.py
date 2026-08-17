"""零点万物(01.AI)招聘抓取器——www.lingyiwanwu.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class LingyiwanwuScraper(BrowserAPIScraper):
    """零点万物专用抓取器。"""

    source_platform = "01ai_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
