import re

CHAPTER_RE = re.compile(r"第(\d+)章")
SKIP_RE = re.compile(r"版权|书名|目录|序言|附录|自序|第[一二三四五六七八九十百]+单元")


def normalize_chapter_title(title: str) -> str:
    t = title.replace(" ", "").replace("\u3000", "")
    for q in "''\u2018\u2019\u201c\u201d":
        t = t.replace(q, "")
    return t


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
    chapters: dict[int, dict] = {}
    _collect_chapters(book_data["book_tree"], chapters, [0])
    return chapters


def _collect_sections(
    nodes: dict,
    sections: dict[str, dict],
    order: list[int],
) -> None:
    for key, node in nodes.items():
        norm = normalize_chapter_title(key)
        if norm in sections:
            raise ValueError(f"重复章节标题：{key}")
        paragraphs = extract_text(node)
        body = remove_citations("".join(remove_references(paragraphs)))
        sections[norm] = {
            "title": key,
            "order": order[0],
            "body": body,
        }
        order[0] += 1
        if node.get("children"):
            _collect_sections(node["children"], sections, order)


def extract_sections(book_data: dict) -> dict[str, dict]:
    sections: dict[str, dict] = {}
    _collect_sections(book_data["book_tree"], sections, [0])
    return sections


def get_supplementary_text(sections: dict[str, dict], supplementary: list[dict]) -> str:
    """根据 outline 中的 supplementary_sections 提取对应原文，返回格式化文本。"""
    if not supplementary:
        return ""
    parts: list[str] = []
    for item in supplementary:
        norm = normalize_chapter_title(item["source"])
        if norm not in sections:
            continue
        quote = item.get("quote", "")
        context = item.get("context", "")
        body = sections[norm]["body"]
        parts.append(f"[来源：{item['source']}]")
        if context:
            parts.append(f"[用途：{context}]")
        if quote:
            parts.append(f"[核心引用：{quote}]")
        parts.append(f"[全文]\n{body}")
    return "\n\n---\n\n".join(parts)


def get_episode_text(sections: dict[str, dict], titles: list[str]) -> str:
    missing: list[str] = []
    bodies: list[str] = []
    for title in titles:
        norm = normalize_chapter_title(title)
        if norm not in sections:
            missing.append(title)
        else:
            bodies.append(sections[norm]["body"])
    if missing:
        raise KeyError(f"章节不存在: {missing}")
    return "\n\n".join(bodies)


def split_chunks(text: str, max_chars: int = 4500) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    if len(paragraphs) <= 1:
        sentences = [s.strip() for s in re.split(r"(?<=[。！？!?；;])\s*", text) if s.strip()]
        paragraphs = sentences or [text.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for p in paragraphs:
        if current and current_len + len(p) > max_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(p)
        current_len += len(p)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def format_list(items: list) -> str:
    return "、".join(items) if items else "无"
