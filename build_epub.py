"""translated book.json → epub"""

import argparse
from pathlib import Path

from core.config import get_project_config, ROOT
from core.utils import load_json
from ingest.epub_builder import build_epub


def main():
    parser = argparse.ArgumentParser(description="从 book.json 重建 EPUB")
    parser.add_argument("project", nargs="?", help="项目名")
    parser.add_argument("--lang", default="zh", help="语言后缀 (默认 zh)")
    parser.add_argument("--title", help="EPUB 标题（默认使用第一个章节名）")
    parser.add_argument("--source", help="源 JSON 路径（默认 asset/book/{project}/{project}.{lang}.json）")
    parser.add_argument("-o", "--output", help="输出路径（默认 asset/book/{project}/{project}.{lang}.epub）")
    args = parser.parse_args()

    if args.project:
        project = args.project
    else:
        from build_book import PROJECT as DEFAULT_PROJECT
        project = DEFAULT_PROJECT

    cfg = get_project_config(project)

    source = args.source or cfg.book_dir / f"{cfg.name}.{args.lang}.json"
    output = args.output or cfg.book_dir / f"{cfg.name}.{args.lang}.epub"

    source_path = Path(source)
    if not source_path.exists():
        print(f"源文件不存在: {source_path}")
        return

    print(f"源 JSON: {source_path}")
    print(f"输出 EPUB: {output}")

    book_data = load_json(str(source_path))
    build_epub(book_data, output, title=args.title, lang=args.lang)
    print(f"✓ EPUB 已生成: {output}")


if __name__ == "__main__":
    main()
