from __future__ import annotations

import json
import os
import warnings
import zipfile
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import unquote, urldefrag

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


TEXT_TAGS = {"p", "li"}
HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
SKIP_TITLES = {"目录"}


@dataclass
class TocEntry:
    titles: list[str]
    href: str
    fragment: Optional[str] = None


@dataclass
class TocNode:
    title: str
    href: str = ""
    fragment: Optional[str] = None
    paragraphs: list[str] = field(default_factory=list)
    images: list[dict[str, str]] = field(default_factory=list)
    children: dict[str, "TocNode"] = field(default_factory=dict)

    def child(self, title: str) -> "TocNode":
        return self.children.setdefault(title, TocNode(title))


@dataclass
class PackageInfo:
    spine: list[str]
    nav_href: Optional[str]
    ncx_href: Optional[str]


def _read_text(zf: zipfile.ZipFile, path: str) -> str:
    with zf.open(path) as fp:
        return fp.read().decode("utf-8", errors="ignore")


def _norm(text: str) -> str:
    return " ".join(text.split())


def _soup(markup: str) -> BeautifulSoup:
    soup = BeautifulSoup(markup, "xml")
    return soup if soup.find() else BeautifulSoup(markup, "html.parser")


def _resolve(base_dir: str, href: str) -> tuple[str, Optional[str]]:
    file_part, fragment = urldefrag(href or "")
    path = os.path.normpath(os.path.join(base_dir, unquote(file_part))) if file_part else ""
    return path, fragment or None


def _opf_path(zf: zipfile.ZipFile) -> str:
    rootfile = _soup(_read_text(zf, "META-INF/container.xml")).find("rootfile")
    if not rootfile or not rootfile.get("full-path"):
        raise RuntimeError("未找到 container.xml 中的 rootfile 定义")
    return rootfile["full-path"]


def _parse_package(zf: zipfile.ZipFile, opf_path: str) -> PackageInfo:
    opf_dir = os.path.dirname(opf_path)
    soup = _soup(_read_text(zf, opf_path))
    manifest: dict[str, str] = {}
    nav_href = ncx_href = None

    for item in soup.find_all("item"):
        item_id, href = item.get("id"), item.get("href")
        if not item_id or not href:
            continue

        path, _ = _resolve(opf_dir, href)
        manifest[item_id] = path

        if "nav" in (item.get("properties") or "").split():
            nav_href = path
        if (item.get("media-type") or "").lower() == "application/x-dtbncx+xml":
            ncx_href = path

    spine_tag = soup.find("spine")
    toc_id = spine_tag.get("toc") if spine_tag else None
    spine = [
        manifest[idref]
        for itemref in (spine_tag.find_all("itemref") if spine_tag else [])
        if (idref := itemref.get("idref")) in manifest
    ]

    nav_href = nav_href or _find_by_suffix(manifest, "nav.xhtml")
    ncx_href = ncx_href or (manifest.get(toc_id) if toc_id else None)
    return PackageInfo(spine=spine, nav_href=nav_href, ncx_href=ncx_href)


def _find_by_suffix(manifest: dict[str, str], suffix: str) -> Optional[str]:
    suffix = suffix.lower()
    return next((path for path in manifest.values() if path.lower().endswith(suffix)), None)


def _load_toc(zf: zipfile.ZipFile, package: PackageInfo) -> list[TocEntry]:
    if package.nav_href:
        soup = _soup(_read_text(zf, package.nav_href))
        nav = (
            soup.find("nav", attrs={"epub:type": "toc"})
            or soup.find("nav", attrs={"type": "toc"})
            or soup.find("nav", role="doc-toc")
            or soup.find("nav")
        )
        if nav:
            return _collect_nav(nav, os.path.dirname(package.nav_href))

    if package.ncx_href:
        return _collect_ncx(_read_text(zf, package.ncx_href), os.path.dirname(package.ncx_href))

    if package.spine:
        return [TocEntry([f"Document {idx}"], href) for idx, href in enumerate(package.spine, 1)]

    raise RuntimeError("OPF 中未找到 nav.xhtml、toc.ncx 或可用 spine")


def _collect_nav(nav, base_dir: str) -> list[TocEntry]:
    root_list = nav.find(["ol", "ul"])
    entries: list[TocEntry] = []

    def walk(li, chain: list[str]) -> None:
        title = _nav_li_title(li)
        if not title:
            return

        link = li.find("a", recursive=False)
        href, fragment = _resolve(base_dir, link.get("href", "") if link else "")
        titles = chain + [title]
        entries.append(TocEntry(titles, href, fragment))

        child_list = li.find(["ol", "ul"], recursive=False)
        for child in child_list.find_all("li", recursive=False) if child_list else []:
            walk(child, titles)

    for li in root_list.find_all("li", recursive=False) if root_list else []:
        walk(li, [])
    return entries


def _nav_li_title(li) -> str:
    label = li.find(["a", "span"], recursive=False)
    if label:
        return _norm(label.get_text(" ", strip=True))

    text = []
    for child in li.children:
        if getattr(child, "name", None) in {"ol", "ul"}:
            continue
        value = child.get_text(" ", strip=True) if hasattr(child, "get_text") else str(child)
        if value.strip():
            text.append(value)
    return _norm(" ".join(text))


def _collect_ncx(ncx_xml: str, base_dir: str) -> list[TocEntry]:
    nav_map = _soup(ncx_xml).find("navMap")
    entries: list[TocEntry] = []

    def walk(navpoint, chain: list[str]) -> None:
        label = navpoint.find("navLabel")
        text_tag = label.find("text") if label else navpoint.find("text")
        title = _norm(text_tag.get_text(" ", strip=True)) if text_tag else ""
        if not title:
            return

        content = navpoint.find("content")
        href, fragment = _resolve(base_dir, content.get("src", "") if content else "")
        titles = chain + [title]
        entries.append(TocEntry(titles, href, fragment))

        for child in navpoint.find_all("navPoint", recursive=False):
            walk(child, titles)

    for navpoint in nav_map.find_all("navPoint", recursive=False) if nav_map else []:
        walk(navpoint, [])
    return entries


def _infer_level(title: str) -> int:
    if not title.strip():
        return 1
    if "附录" in title or ("第" in title and "章" in title) or title.endswith("章"):
        return 1
    if (("第" in title and "节" in title) or title.endswith("节")) and not any(
        word in title for word in ("关节", "季节")
    ):
        return 2
    return 3


def _build_tree(entries: list[TocEntry]) -> TocNode:
    root = TocNode("ROOT")
    flat_toc = entries and all(len(entry.titles) <= 1 for entry in entries)
    stack: list[tuple[int, TocNode]] = []

    for entry in entries:
        titles = [title for title in entry.titles if title and title not in SKIP_TITLES]
        if not titles:
            continue

        if flat_toc:
            title = titles[-1]
            level = _infer_level(title)
            while stack and stack[-1][0] >= level:
                stack.pop()
            node = (stack[-1][1] if stack else root).child(title)
            stack.append((level, node))
        else:
            node = root
            for title in titles:
                node = node.child(title)

        node.href = entry.href or node.href
        node.fragment = entry.fragment or node.fragment

    return root


def _walk_nodes(root: TocNode):
    for child in root.children.values():
        yield child
        yield from _walk_nodes(child)


def _find_anchor(soup: BeautifulSoup, node: TocNode):
    if node.fragment:
        target = soup.find(id=node.fragment) or soup.find(attrs={"name": node.fragment})
        if target:
            return target

    title = _norm(node.title)
    for tag in soup.find_all(HEADING_TAGS):
        if _norm(tag.get_text(" ", strip=True)) == title:
            return tag

    return soup.body or soup.find()


def _extract_range(start, end, base_dir: str) -> tuple[list[str], list[dict[str, str]]]:
    paragraphs: list[str] = []
    images: list[dict[str, str]] = []
    cursor = start

    while cursor and cursor != end:
        name = getattr(cursor, "name", None)
        if name in TEXT_TAGS and (text := _norm(cursor.get_text(" ", strip=True))):
            paragraphs.append(text)
        elif name == "img" and (src := cursor.get("src")):
            path, _ = _resolve(base_dir, src)
            images.append({"src": path or src, "alt": cursor.get("alt", "")})
        cursor = cursor.next_element

    return paragraphs, images


def _attach_content(root: TocNode, zf: zipfile.ZipFile) -> None:
    by_href: dict[str, list[TocNode]] = {}
    for node in _walk_nodes(root):
        if node.href:
            by_href.setdefault(node.href, []).append(node)

    for href, nodes in by_href.items():
        soup = _soup(_read_text(zf, href))
        anchors = [_find_anchor(soup, node) for node in nodes]

        for idx, node in enumerate(nodes):
            start = anchors[idx]
            end = anchors[idx + 1] if idx + 1 < len(anchors) else None
            if start:
                node.paragraphs, node.images = _extract_range(start, end, os.path.dirname(href))


def _node_to_dict(node: TocNode) -> dict[str, dict]:
    return {
        child.title: {
            "href": os.path.basename(child.href),
            "paragraphs": child.paragraphs,
            "images": child.images,
            "children": _node_to_dict(child),
        }
        for child in node.children.values()
    }


def _search_guide(root: TocNode) -> dict[str, dict[str, list[str]]]:
    return {
        "toc_tree": {
            chapter.title: {
                section.title: list(section.children)
                for section in chapter.children.values()
            }
            for chapter in root.children.values()
        }
    }


def parse_epub(epub_path: str) -> dict[str, dict]:
    """解析 EPUB2/3，返回 book_tree 与 search_guide。"""
    with zipfile.ZipFile(epub_path) as zf:
        package = _parse_package(zf, _opf_path(zf))
        root = _build_tree(_load_toc(zf, package))
        _attach_content(root, zf)

    return {"book_tree": _node_to_dict(root), "search_guide": _search_guide(root)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EPUB 结构化解析器")
    parser.add_argument("--name", nargs="?", default="reason_op")
    args = parser.parse_args()

    epub_path = f"../asset/{args.name}.epub"
    output_path = f"../asset/{args.name}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(parse_epub(epub_path), f, ensure_ascii=False, indent=2)

    print(f"输出已保存到 {output_path}")
