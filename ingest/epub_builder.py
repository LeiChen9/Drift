import os
import shutil
import tempfile
import uuid
from collections import OrderedDict
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape


def build_epub(
    book_data: dict,
    output_path: str | Path,
    title: str | None = None,
    lang: str = "zh",
):
    book_tree = book_data.get("book_tree", {})
    if not book_tree:
        raise ValueError("book_tree is empty")

    title = title or _guess_title(book_tree)
    uid = str(uuid.uuid4())

    groups = _group_by_href(book_tree)

    tmpdir = Path(tempfile.mkdtemp(suffix="_epub"))
    try:
        _write_mimetype(tmpdir)
        _write_container(tmpdir)
        oebps = tmpdir / "OEBPS"
        oebps.mkdir(parents=True)

        href_file_map = _write_pages(oebps, groups, lang)
        _write_nav(oebps, book_tree, title, href_file_map, lang)
        _write_opf(oebps, title, lang, uid, list(href_file_map.values()))

        _zip_epub(tmpdir, output_path)
    finally:
        shutil.rmtree(tmpdir)


def _guess_title(tree: dict) -> str:
    for key in tree:
        return key
    return "Untitled"


def _group_by_href(tree: dict) -> OrderedDict:
    groups: OrderedDict[str, list[dict]] = OrderedDict()

    def walk(nodes: dict, depth: int = 0):
        for key, node in nodes.items():
            href = node.get("href", "")
            groups.setdefault(href, []).append({
                "title": key,
                "depth": depth,
                "paragraphs": node.get("paragraphs", []),
                "images": node.get("images", []),
            })
            if node.get("children"):
                walk(node["children"], depth + 1)

    walk(tree)
    return groups


def _write_mimetype(tmpdir: Path):
    (tmpdir / "mimetype").write_text("application/epub+zip", encoding="utf-8")


def _write_container(tmpdir: Path):
    meta_inf = tmpdir / "META-INF"
    meta_inf.mkdir()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
    (meta_inf / "container.xml").write_text(xml, encoding="utf-8")


def _write_pages(oebps: Path, groups: OrderedDict, lang: str = "zh") -> dict[str, str]:
    href_file_map: dict[str, str] = {}

    for href, sections in groups.items():
        if not href:
            continue
        fname = _xhtml_name(href, list(href_file_map.values()))

        parts = []
        for sec in sections:
            depth = min(sec["depth"] + 1, 6)
            parts.append(f'<h{depth}>{xml_escape(sec["title"])}</h{depth}>')
            for para in sec["paragraphs"]:
                parts.append(f"<p>{xml_escape(para)}</p>")
            for img in sec["images"]:
                src = img.get("src", "")
                alt = xml_escape(img.get("alt", ""))
                parts.append(f'<p><img src="{xml_escape(src)}" alt="{alt}"/></p>')

        html = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{xml_escape(lang)}" lang="{xml_escape(lang)}">
<head>
<title>{xml_escape(sections[0]["title"])}</title>
</head>
<body>
{''.join(parts)}
</body>
</html>"""
        (oebps / fname).write_text(html, encoding="utf-8")
        href_file_map[href] = fname

    return href_file_map


def _xhtml_name(href: str, existing: list[str]) -> str:
    name = href
    if not name.endswith(".xhtml") and not name.endswith(".html"):
        name += ".xhtml"
    if name in existing:
        base, ext = os.path.splitext(name)
        i = 1
        while f"{base}_{i}{ext}" in existing:
            i += 1
        name = f"{base}_{i}{ext}"
    return name


def _write_nav(oebps: Path, tree: dict, title: str, href_file_map: dict[str, str], lang: str = "zh"):
    items = _nav_items(tree, href_file_map)
    nav_lis = "\n".join(items)

    html = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops"
      xml:lang="{xml_escape(lang)}" lang="{xml_escape(lang)}">
<head>
<title>{xml_escape(title)}</title>
</head>
<body>
  <nav epub:type="toc">
    <h1>{xml_escape(title)}</h1>
    <ol>
{nav_lis}
    </ol>
  </nav>
</body>
</html>"""
    (oebps / "nav.xhtml").write_text(html, encoding="utf-8")


def _nav_items(tree: dict, href_file_map: dict[str, str], indent: int = 2) -> list[str]:
    lines = []
    sp = "  " * indent
    for key, node in tree.items():
        href = node.get("href", "")
        actual = href_file_map.get(href, "") if href else ""
        href_attr = f' href="{xml_escape(actual)}"' if actual else ""
        lines.append(f'{sp}<li><a{href_attr}>{xml_escape(key)}</a>')
        children = node.get("children")
        if children:
            lines.append(f"{sp}<ol>")
            lines.extend(_nav_items(children, href_file_map, indent + 2))
            lines.append(f"{sp}</ol>")
        lines.append(f"{sp}</li>")
    return lines


def _write_opf(oebps: Path, title: str, lang: str, uid: str, page_refs: list[str]):
    manifest_items = []

    def add_item(id_: str, href: str, mtype: str, props: str = ""):
        attr = f' properties="{props}"' if props else ""
        manifest_items.append(f'    <item id="{id_}" href="{href}" media-type="{mtype}"{attr}/>')

    add_item("nav", "nav.xhtml", "application/xhtml+xml", props="nav")
    for idx, ref in enumerate(page_refs, 1):
        add_item(f"p{idx}", ref, "application/xhtml+xml")

    manifest = "\n".join(manifest_items)

    spine = "\n".join(
        f'    <itemref idref="p{idx}"/>' for idx in range(1, len(page_refs) + 1)
    )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns:dcterms="http://purl.org/dc/terms/"
         version="3.0" unique-identifier="book-id">
  <metadata>
    <dc:identifier id="book-id">{xml_escape(uid)}</dc:identifier>
    <dc:title>{xml_escape(title)}</dc:title>
    <dc:language>{xml_escape(lang)}</dc:language>
    <meta property="dcterms:modified">{_now()}</meta>
  </metadata>
  <manifest>
{manifest}
  </manifest>
  <spine>
    <itemref idref="nav" linear="no"/>
{spine}
  </spine>
</package>"""
    (oebps / "content.opf").write_text(xml, encoding="utf-8")


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _zip_epub(src_dir: Path, output_path: str | Path):
    import zipfile

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                fpath = Path(root) / fname
                arcname = str(fpath.relative_to(src_dir))
                if arcname == "mimetype":
                    continue
                zf.write(fpath, arcname)
