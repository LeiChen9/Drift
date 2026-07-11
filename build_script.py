"""outline.json + book.json → 台本（draft + review + audit）"""

import os
import sys
from pathlib import Path
from core.config import get_project_config
from core.utils import load_json, read_text, write_text
from script.rewriter import script_rewrite
from script.reviewer import review_script
from script.apply_review import apply_review, write_review_report
from script.auditor import audit_script
from script.utils import extract_sections, get_episode_text
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
        reviewed_path = cfg.script_dir / f"{ep_id}_reviewed.txt"
        final_path = cfg.script_dir / f"{ep_id}_final.txt"

        if final_path.exists():
            print(f"已存在最终稿，跳过：{final_path}")
            continue

        full_text = get_episode_text(sections, episode["chapter_titles"])

        # --- Step 1: Rewriter ---
        if reviewed_path.exists():
            script_draft = read_text(reviewed_path)
            print(f"已存在审校后稿，读取：{reviewed_path}")
        elif draft_path.exists():
            script_draft = read_text(draft_path)
        else:
            fails_dir = cfg.script_dir / "_fails" / ep_id
            success_dir = cfg.script_dir / "_success" / ep_id
            script_draft = script_rewrite(episode, sections, fails_dir=fails_dir, success_dir=success_dir, full_text=full_text)
            write_text(draft_path, script_draft)

        print(f"台本初稿已生成，长度 {len(script_draft)} 字")

        # --- Step 2: Reviewer ---
        if not reviewed_path.exists():
            print(f"正在评审台本：{episode['title']}...")
            issues = review_script(full_text, script_draft)
            print(f"评审完成，发现 {len(issues)} 个问题")

            reviewed_draft, unresolved = apply_review(script_draft, issues)
            write_text(reviewed_path, reviewed_draft)

            if unresolved:
                report_path = cfg.script_dir / f"{ep_id}_review_report.json"
                write_review_report(report_path, unresolved, script_draft)
                print(f"审校完成，{len(unresolved)} 个问题未能自动 apply。")
                print(f"请查看报告手动修改台本：{report_path}")
                print(f"修改后重新运行即可（将跳过已完成的步骤）。")
                sys.exit(1)

            script_draft = reviewed_draft

        # --- Step 3: Auditor ---
        print(f"正在审校台本：{episode['title']}...")
        script_final = audit_script(script_draft)
        write_text(final_path, script_final)
        pdb.set_trace()

    print("脚本生成完成")


if __name__ == "__main__":
    main()
