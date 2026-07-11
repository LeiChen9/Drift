"""outline.json + book.json → 台本（draft + audit）"""

import os
from core.config import get_project_config
from core.utils import load_json, read_text, write_text
from script.rewriter import script_rewrite
from script.auditor import audit_script
from script.utils import extract_sections
import pdb

PROJECT = "division_of_labor"  # ← 改这里切换项目


def main():
    cfg = get_project_config(PROJECT)
    cfg.lang = "zh"  # 手动指定：使用翻译版 book_zh
    outline = load_json(cfg.outline_path)
    book_data = load_json(cfg.book_json_path())
    sections = extract_sections(book_data)

    cfg.script_dir.mkdir(parents=True, exist_ok=True)

    for episode in outline["episodes"]:
        ep_id = episode["episode_id"]
        draft_path = cfg.script_dir / f"{ep_id}_draft.txt"
        final_path = cfg.script_dir / f"{ep_id}_final.txt"

        if final_path.exists():
            print(f"已存在最终稿，跳过：{final_path}")
            continue

        if draft_path.exists():
            script_draft = read_text(draft_path)
        else:
            script_draft = script_rewrite(episode, sections)
            write_text(draft_path, script_draft)

        print(f"台本初稿已生成，长度 {len(script_draft)} 字")
        print(f"正在审校台本：{episode['title']}...")
        script_final = audit_script(script_draft)
        write_text(final_path, script_final)
        pdb.set_trace()

    print("脚本生成完成")


if __name__ == "__main__":
    main()
