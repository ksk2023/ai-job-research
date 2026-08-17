"""科大讯飞招聘抓取器——campus.iflytek.com / talent.iflytek.com"""
from __future__ import annotations

from ..base import BaseScraper
from .browser_api import BrowserAPIScraper


class iFlytekScraper(BrowserAPIScraper):
    """科大讯飞专用抓取器。"""

    source_platform = "iflytek_official"
    source_type = "official"
    needs_browser = True
    rate_limit_per_min = 8
