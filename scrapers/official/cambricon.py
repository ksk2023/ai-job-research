"""寒武纪招聘抓取器——www.cambricon.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class CambriconScraper(BrowserAPIScraper):
    """寒武纪专用抓取器。"""

    source_platform = "cambricon_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
