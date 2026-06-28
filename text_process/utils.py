import os
import re
import warnings
from typing import Optional
from urllib.parse import unquote, urldefrag

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

CHAPTER_RE = re.compile(r"第(\d+)章")
SKIP_RE = re.compile(r"版权|书名|目录|序言|附录|自序|第[一二三四五六七八九十百]+单元")


def normalize_chapter_title(title: str) -> str:
    t = title.replace(" ", "").replace("\u3000", "")
    for q in "''\u2018\u2019\u201c\u201d":
        t = t.replace(q, "")
    return t


def make_soup(markup: str) -> BeautifulSoup:
    soup = BeautifulSoup(markup, "xml")
    return soup if soup.find() else BeautifulSoup(markup, "html.parser")


from pathlib import PurePosixPath

def resolve_href(base_dir: str, href: str) -> tuple[str, Optional[str]]:
    file_part, fragment = urldefrag(href or "")
    if not file_part:
        return "", fragment or None
    path = str(PurePosixPath(base_dir.replace("\\", "/"), unquote(file_part)))
    return path, fragment or None


def remove_citations(text: str) -> str:
    text = re.sub(r"\s*\[\s*[\d,\s]+\s*\]\s*", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def remove_references(paragraphs: list[str]) -> list[str]:
    return [text for text in paragraphs if not text.startswith("[ ")]


def extract_text(node: dict) -> list[str]:
    parts = []
    if node.get("paragraphs"):
        parts.append("".join(node["paragraphs"]) + "\n")
    for child in (node.get("children") or {}).values():
        parts += extract_text(child)
    return parts


def _collect_chapters(
    nodes: dict,
    chapters: dict[int, dict],
    order: list[int],
) -> None:
    for key, node in nodes.items():
        if SKIP_RE.search(key.replace(" ", "")):
            if node.get("children"):
                _collect_chapters(node["children"], chapters, order)
            continue

        match = CHAPTER_RE.match(key)
        if match:
            num = int(match.group(1))
            if num in chapters:
                raise ValueError(f"重复章节序号：第{num}章（{key}）")
            paragraphs = extract_text(node)
            body = remove_citations("".join(remove_references(paragraphs)))
            chapters[num] = {
                "title": key,
                "chapter_num": num,
                "order": order[0],
                "body": body,
            }
            order[0] += 1
        elif node.get("children"):
            _collect_chapters(node["children"], chapters, order)


def extract_chapters(book_data: dict) -> dict[int, dict]:
    """从 book_tree 递归提取所有「第N章」节点，按章号索引。"""
    chapters: dict[int, dict] = {}
    _collect_chapters(book_data["book_tree"], chapters, [0])
    return chapters


def get_episode_text(chapters: dict[int, dict], chapter_nums: list[int]) -> str:
    missing = [n for n in chapter_nums if n not in chapters]
    if missing:
        raise KeyError(f"章节不存在: {missing}")
    return "\n\n".join(chapters[n]["body"] for n in sorted(chapter_nums))


def split_chunks(text: str, max_chars: int = 4500) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]

    if len(paragraphs) <= 1:
        sentences = [s.strip() for s in re.split(r"(?<=[。！？!?；;])\s*", text) if s.strip()]
        paragraphs = sentences or [text.strip()]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        if current and current_len + len(paragraph) > max_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph)

    if current:
        chunks.append("\n\n".join(current))
    return chunks
