"""book.json → 翻译为指定语言，按同格式存储到 asset/book/{project}/"""

import argparse
import concurrent.futures
import threading
from pathlib import Path

from core.config import get_project_config
from core.utils import load_json, write_json
from script.translator import BookTranslator

PROGRESS_VERSION = 1


def output_path(cfg, target_lang: str) -> Path:
    return cfg.book_dir / f"{cfg.name}.{target_lang}.json"


def progress_path(cfg, target_lang: str) -> Path:
    return cfg.book_dir / f".{cfg.name}.{target_lang}.progress.json"


def _collect_leaves(tree: dict, prefix: str = "") -> list[tuple[str, str, dict]]:
    leaves = []
    for key, node in tree.items():
        leaf_key = f"{prefix} > {key}" if prefix else key
        paragraphs = node.get("paragraphs", [])
        if paragraphs:
            leaves.append((leaf_key, key, node))
        if node.get("children"):
            leaves.extend(_collect_leaves(node["children"], leaf_key))
    leaves.sort(key=lambda x: len(x[0].split(" > ")), reverse=True)
    return leaves


def _rebuild_tree(orig_tree: dict, key_map: dict, node_results: dict, prefix: str = "") -> dict:
    result = {}
    for key, node in orig_tree.items():
        leaf_key = f"{prefix} > {key}" if prefix else key
        t_key = key_map.get(key, key)

        entry = node_results.get(leaf_key)
        if entry and entry["status"] == "success":
            t_node = {
                "href": node.get("href", ""),
                "images": node.get("images", []),
                "paragraphs": entry["paragraphs"],
            }
        else:
            t_node = {
                "href": node.get("href", ""),
                "images": node.get("images", []),
                "paragraphs": node.get("paragraphs", []),
            }

        if node.get("children"):
            t_node["children"] = _rebuild_tree(
                node["children"], key_map, node_results, leaf_key
            )

        result[t_key] = t_node
    return result


def main():
    parser = argparse.ArgumentParser(description="翻译 book.json 为指定语言")
    parser.add_argument("project", nargs="?", help="项目名")
    parser.add_argument("--target", default="zh", help="目标语言代码 (默认 zh)")
    parser.add_argument("--source", default="en", help="源语言代码 (默认 en)")
    parser.add_argument("--retry-failed", action="store_true", help="只重试上次失败的节点")
    parser.add_argument("--resume", action="store_true", help="从进度文件恢复")
    parser.add_argument("-j", "--concurrency", type=int, default=5, help="并发数 (默认 5)")
    args = parser.parse_args()

    if args.project:
        project = args.project
    else:
        from build_book import PROJECT as DEFAULT_PROJECT
        project = DEFAULT_PROJECT

    cfg = get_project_config(project)
    source_path = cfg.book_json_path()
    out_path = output_path(cfg, args.target)

    if not source_path.exists():
        print(f"源文件不存在: {source_path}")
        return

    print(f"项目: {project}")
    print(f"目标: {source_path.name} → {out_path.name}")

    book_data = load_json(str(source_path))
    translator = BookTranslator(target_lang=args.target, source_lang=args.source)

    node_results: dict[str, dict] = {}

    if args.resume or args.retry_failed:
        p_path = progress_path(cfg, args.target)
        if p_path.exists():
            prog = load_json(str(p_path))
            translator._style_guide = prog.get("style_guide")
            translator.key_map = prog.get("key_map", {})
            node_results = prog.get("node_results", {})
            ok = sum(1 for r in node_results.values() if r["status"] == "success")
            fail = sum(1 for r in node_results.values() if r["status"] == "failed")
            print(f"恢复进度: {ok} 成功, {fail} 失败")
        else:
            print(f"进度文件未找到: {p_path}")
            return

    if not translator._style_guide:
        translator.generate_style_guide(book_data["book_tree"])

    leaves = _collect_leaves(book_data["book_tree"])
    to_translate = []

    for leaf_key, orig_key, node in leaves:
        existing = node_results.get(leaf_key)

        if args.retry_failed:
            if existing and existing["status"] == "success":
                continue
        elif args.resume:
            if existing:
                continue

        to_translate.append((leaf_key, orig_key, node))

    total = len(to_translate)
    done_count = len([r for r in node_results.values() if r["status"] == "success"])
    print_lock = threading.Lock()

    def translate_one(leaf_key: str, orig_key: str, paras: list[str]) -> tuple:
        try:
            t_title, t_paras = translator.translate_node(orig_key, paras)
            return leaf_key, orig_key, t_title, t_paras, None
        except Exception as e:
            return leaf_key, orig_key, None, None, str(e)

    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = [pool.submit(translate_one, lk, ok, node.get("paragraphs", []))
                for lk, ok, node in to_translate]

        for fut in concurrent.futures.as_completed(futs):
            leaf_key, orig_key, t_title, t_paras, err = fut.result()

            if err:
                with print_lock:
                    print(f"✗ {orig_key[:60]} → {err}")
                node_results[leaf_key] = {"status": "failed", "title": "", "paragraphs": []}
            else:
                translator.key_map[orig_key] = t_title
                node_results[leaf_key] = {
                    "status": "success", "title": t_title, "paragraphs": t_paras,
                }
                with print_lock:
                    print(f"✓ {t_title[:60]}")

            completed += 1
            if completed % 10 == 0 or completed == total:
                _save_progress(progress_path(cfg, args.target), translator, node_results)
                done = len([r for r in node_results.values() if r["status"] == "success"])
                print(f"[{done_count + completed}/{done_count + total}] {done} 成功, "
                      f"{completed - done} 失败")

    translated_tree = _rebuild_tree(
        book_data["book_tree"], translator.key_map, node_results
    )

    translated_toc = {}
    if "toc_tree" in book_data.get("search_guide", {}):
        translated_toc["toc_tree"] = translator.translate_toc_tree(
            book_data["search_guide"]["toc_tree"]
        )

    result_data = {
        "book_tree": translated_tree,
        "search_guide": translated_toc,
    }

    write_json(str(out_path), result_data)
    print(f"\n✓ 输出: {out_path}")

    failed = [k for k, v in node_results.items() if v["status"] == "failed"]
    if failed:
        print(f"\n⚠ {len(failed)} 个节点失败:")
        for f in failed:
            print(f"  {f}")
        print(f"重试: python build_translate.py {project} --target {args.target} --retry-failed")
    else:
        print("全部成功 ✓")


def _save_progress(path: Path, translator: BookTranslator, node_results: dict):
    write_json(str(path), {
        "version": PROGRESS_VERSION,
        "style_guide": translator._style_guide,
        "key_map": translator.key_map,
        "node_results": node_results,
    })


if __name__ == "__main__":
    main()
