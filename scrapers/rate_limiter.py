"""
按域名维度的速率限制器——令牌桶实现。
每个域名独立计数，互不阻塞，避免单个域名的限速影响其他域名抓取。
"""
import asyncio
import time
from urllib.parse import urlparse


class DomainRateLimiter:
    """每域名独立的滑动窗口限速器。

    保证每个域名每分钟请求数不超过 max_per_min，
    不同域名之间互不阻塞。
    """

    def __init__(self):
        self._buckets: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, url: str, max_per_min: int = 20) -> None:
        """获取对指定 URL 所在域名的请求许可。

        如果当前域名在最近 60 秒内已达 max_per_min，则阻塞等待。
        """
        domain = urlparse(url).netloc
        async with self._lock:
            now = time.time()
            bucket = [t for t in self._buckets.get(domain, []) if now - t < 60]
            if len(bucket) >= max_per_min:
                wait = 60 - (now - bucket[0]) + 0.5  # 多等 0.5s 缓冲
                await asyncio.sleep(wait)
            self._buckets[domain] = bucket + [time.time()]

    def stats(self) -> dict[str, int]:
        """返回每个域名当前 60 秒窗口内的请求数（调试用）。"""
        now = time.time()
        return {
            domain: len([t for t in ts if now - t < 60])
            for domain, ts in self._buckets.items()
        }


# 全局单例
rate_limiter = DomainRateLimiter()
