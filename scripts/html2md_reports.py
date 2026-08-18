# -*- coding: utf-8 -*-
"""HTML 调研报告 -> Markdown 转换器（保结构：标题/表格/列表/加粗/高亮）"""
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

SRC = Path(r"E:\BaiduNetdiskDownload\工作岗位筛选")
DST = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC

FILES = [
    "AI实习岗位日薪调研报告.html",
    "AI算法岗与开发岗机考力扣要求调研报告.html",
    "AI_Coding岗位机考力扣要求专题报告.html",
    "不需要刷力扣的岗位全梳理.html",
    "大厂技术岗与非技术岗薪资对比.html",
]


def inline_md(node) -> str:
    """递归把行内 HTML 转为 markdown 文本"""
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    name = node.name
    inner = "".join(inline_md(c) for c in node.children)
    if name in ("strong", "b"):
        return f"**{inner.strip()}**" if inner.strip() else ""
    if name in ("em", "i"):
        return f"*{inner.strip()}*" if inner.strip() else ""
    if name == "mark" or (name == "span" and "highlight" in (node.get("class") or [])):
        return f"**{inner.strip()}**" if inner.strip() else ""
    if name == "br":
        return "  \n"
    if name == "code":
        return f"`{inner}`"
    if name == "a":
        href = node.get("href", "")
        if href and href.startswith("http"):
            return f"[{inner.strip()}]({href})"
        return inner
    return inner


def cell_md(cell) -> str:
    text = inline_md(cell).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text.replace("|", "\\|")


def table_md(tbl: Tag) -> str:
    rows = tbl.find_all("tr")
    if not rows:
        return ""
    lines = []
    header_done = False
    for tr in rows:
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue
        row = [cell_md(c) for c in cells]
        lines.append("| " + " | ".join(row) + " |")
        if not header_done:
            lines.append("|" + "|".join([" --- "] * len(row)) + "|")
            header_done = True
    return "\n".join(lines) + "\n"


def list_md(ul: Tag, depth=0) -> str:
    out = []
    ordered = ul.name == "ol"
    for i, li in enumerate(ul.find_all("li", recursive=False), 1):
        # li 内非列表部分
        parts = []
        sub_lists = []
        for c in li.children:
            if isinstance(c, Tag) and c.name in ("ul", "ol"):
                sub_lists.append(c)
            else:
                parts.append(inline_md(c))
        text = re.sub(r"\s+", " ", "".join(parts)).strip()
        marker = f"{i}." if ordered else "-"
        out.append("  " * depth + f"{marker} {text}")
        for sl in sub_lists:
            out.append(list_md(sl, depth + 1))
    return "\n".join(out) + "\n"


def fix_heading(text: str) -> str:
    """修复标题里数字序号与文本粘连（如 '1AI Coding' -> '1. AI Coding'）"""
    return re.sub(r"^(\d+)(?=[^\d\s.、])", r"\1. ", text)


def convert(html_path: Path) -> str:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else html_path.stem
    body = soup.body or soup

    md = [f"# {title}", ""]
    for el in body.children:
        if not isinstance(el, Tag):
            continue
        cls = el.get("class") or []
        cls_str = " ".join(cls)
        if el.name in ("h1", "h2", "h3", "h4", "h5"):
            level = int(el.name[1])
            md.append("#" * min(level + 1, 6) + " " + fix_heading(inline_md(el).strip()))
            md.append("")
        elif el.name == "table":
            md.append(table_md(el))
            md.append("")
        elif el.name in ("ul", "ol"):
            md.append(list_md(el))
            md.append("")
        elif el.name == "p":
            text = inline_md(el).strip()
            if text:
                md.append(text)
                md.append("")
        elif el.name in BLOCK_CONTAINERS:
            # 跳过导航/页头等装饰容器，递归处理内容块
            if _should_skip(cls_str):
                continue
            block = block_md(el)
            if block.strip():
                md.append(block.rstrip())
                md.append("")
        elif el.name == "hr":
            md.append("---")
            md.append("")
    # 合并多余空行
    text = "\n".join(md)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


BLOCK_CONTAINERS = ("div", "section", "article", "main", "aside", "figure", "details", "header", "blockquote")
SKIP_CLASS_HINTS = ("nav", "footer", "toc", "breadcrumb", "toolbar", "progress")


def _should_skip(cls_str: str) -> bool:
    return any(k in cls_str for k in SKIP_CLASS_HINTS)


def block_md(div: Tag, depth=0) -> str:
    """块级容器递归展开（div/section/article 等统一处理）"""
    if depth > 8:
        return inline_md(div)
    out = []
    for el in div.children:
        if not isinstance(el, Tag):
            txt = str(el).strip()
            if txt:
                out.append(txt)
            continue
        cls = el.get("class") or []
        cls_str = " ".join(cls)
        if el.name in ("h1", "h2", "h3", "h4", "h5"):
            level = int(el.name[1])
            out.append("#" * min(level + 1, 6) + " " + fix_heading(inline_md(el).strip()))
            out.append("")
        elif el.name == "table":
            out.append(table_md(el))
            out.append("")
        elif el.name in ("ul", "ol"):
            out.append(list_md(el))
            out.append("")
        elif el.name == "p":
            text = inline_md(el).strip()
            if text:
                out.append(text)
                out.append("")
        elif el.name in BLOCK_CONTAINERS:
            if _should_skip(cls_str):
                continue
            sub = block_md(el, depth + 1)
            if sub.strip():
                out.append(sub.rstrip())
                out.append("")
        elif el.name == "hr":
            out.append("---")
            out.append("")
        else:
            # 行内标签包裹的杂项（span/strong 等）合并为段落
            text = inline_md(el).strip()
            if text:
                out.append(text)
                out.append("")
    return "\n".join(out)


def main():
    DST.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = SRC / name
        if not src.exists():
            print(f"[skip] {name} 不存在")
            continue
        md_name = src.stem + ".md"
        dst = DST / md_name
        dst.write_text(convert(src), encoding="utf-8")
        size = dst.stat().st_size
        print(f"[ok] {md_name} ({size} bytes)")


if __name__ == "__main__":
    main()
