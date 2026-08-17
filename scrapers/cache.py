"""
增量抓取指纹缓存——避免对同一岗位重复抓取。

指纹 = sha1(company_id + title + location) 前 16 位
已抓指纹存于 data/cache/seen_hashes.txt，每行一个。
"""
import hashlib
import os
from pathlib import Path


class ScraperCache:
    """增量抓取缓存。

    用文件存储已抓岗位的指纹（每行一个 sha1 前 16 位）。
    查询用集合，启动时一次性载入到内存。
    """

    def __init__(self, cache_file: str | Path):
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set()
        if self.cache_file.exists():
            with open(self.cache_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._seen.add(line)

    @staticmethod
    def fingerprint(company_id: str, title: str, location: str | list) -> str:
        """计算岗位指纹。"""
        if isinstance(location, list):
            location = "|".join(location)
        key = f"{company_id}|{title}|{location}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    def seen(self, fp: str) -> bool:
        """是否已抓取过。"""
        return fp in self._seen

    def mark(self, fp: str) -> None:
        """标记为已抓取（同时写入文件）。"""
        if fp not in self._seen:
            self._seen.add(fp)
            with open(self.cache_file, "a", encoding="utf-8") as f:
                f.write(fp + "\n")

    def clear(self) -> None:
        """清空缓存（用于全量重抓）。沙箱环境不支持删除文件，改为清空内容。"""
        self._seen.clear()
        # 清空文件内容而非删除（兼容沙箱环境）
        self.cache_file.write_text("", encoding="utf-8")

    def __len__(self) -> int:
        return len(self._seen)
