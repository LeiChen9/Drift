import difflib
from pathlib import Path

from core.utils import write_json


def apply_review(draft: str, issues: list[dict]) -> tuple[str, list[dict]]:
    """
    Apply review issues to draft.
    Returns (modified_draft, unresolved_issues).
    """
    unresolved: list[dict] = []
    current = draft

    for issue in issues:
        pattern = issue["draft"]
        action = issue["action"]
        suggestion = issue.get("suggestion", "")

        result = _try_apply(current, pattern, action, suggestion)
        if result is None:
            issue["_unresolved_reason"] = "无法在台本中定位对应片段"
            unresolved.append(issue)
        else:
            new_text, confidence = result
            current = new_text
            if confidence < 0.9:
                issue["_match_confidence"] = round(confidence, 3)
                issue["_unresolved_reason"] = "匹配置信度不足，请人工验证"
                unresolved.append(issue)

    return current, unresolved


def write_review_report(report_path: str | Path, unresolved: list[dict], context: str) -> None:
    """Write a human-readable review report for unresolved issues."""
    report = {
        "unresolved_count": len(unresolved),
        "issues": [],
        "guide": (
            "以下 issue 未能自动 apply 到台本中。请按以下步骤处理：\n"
            "1. 打开台本文件（在 build_script.py 中为 draft_path）。\n"
            "2. 根据每个 issue 的 [original] 和 [around_context] 定位到原文位置。\n"
            "3. 根据 [action] 和 [suggestion] 手动修改台本。\n"
            "4. 修改完成后重新运行 build_script.py。"
        ),
    }

    for issue in unresolved:
        entry = {
            "type": issue.get("type", ""),
            "severity": issue.get("severity", ""),
            "action": issue.get("action", ""),
            "original": issue.get("original", ""),
            "draft_pattern": issue.get("draft", ""),
            "suggestion": issue.get("suggestion", ""),
            "reasoning": issue.get("reasoning", ""),
            "unresolved_reason": issue.get("_unresolved_reason", ""),
            "match_confidence": issue.get("_match_confidence"),
            "around_context": _get_around_context(context, issue.get("draft", "")),
        }
        report["issues"].append(entry)

    write_json(report_path, report, indent=2)
    print(f"审校报告已写入：{report_path}")


def _get_around_context(text: str, pattern: str, window: int = 200) -> str:
    """Find pattern in text and return surrounding context."""
    idx = text.find(pattern)
    if idx == -1:
        norm_text = " ".join(text.split())
        norm_pattern = " ".join(pattern.split())
        s = difflib.SequenceMatcher(None, norm_text, norm_pattern)
        match = s.find_longest_match(0, len(norm_text), 0, len(norm_pattern))
        if match.size >= len(norm_pattern) * 0.3:
            # Map back approximately
            start = max(0, match.a - window)
            end = min(len(text), match.a + match.size + window)
            return text[start:end]
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(pattern) + window)
    return text[start:end]


def _try_apply(text: str, pattern: str, action: str, suggestion: str) -> tuple[str, float] | None:
    norm_text = " ".join(text.split())
    norm_pattern = " ".join(pattern.split())

    if not norm_pattern:
        return None

    # 1. Exact match on normalized text
    idx = norm_text.find(norm_pattern)
    if idx != -1:
        start = _map_norm_to_orig(text, norm_text, idx)
        end = _map_norm_to_orig(text, norm_text, idx + len(norm_pattern))
        return _do_action(text, start, end, action, suggestion), 1.0

    # 2. Fuzzy match
    s = difflib.SequenceMatcher(None, norm_text, norm_pattern)
    match = s.find_longest_match(0, len(norm_text), 0, len(norm_pattern))
    if match.size < len(norm_pattern) * 0.6:
        return None

    confidence = match.size / len(norm_pattern)
    start = _map_norm_to_orig(text, norm_text, match.a)
    end = _map_norm_to_orig(text, norm_text, match.a + match.size)
    return _do_action(text, start, end, action, suggestion), confidence


def _map_norm_to_orig(orig: str, norm: str, norm_pos: int) -> int:
    """Map a position in the normalized string back to the original string."""
    orig_i = 0
    norm_i = 0

    while norm_i < norm_pos and orig_i < len(orig):
        if orig[orig_i].isspace():
            while orig_i < len(orig) and orig[orig_i].isspace():
                orig_i += 1
            norm_i += 1
        else:
            orig_i += 1
            norm_i += 1

    return orig_i


def _do_action(text: str, start: int, end: int, action: str, suggestion: str) -> str:
    if action == "rewrite":
        return text[:start] + suggestion + text[end:]
    elif action == "delete":
        return text[:start] + text[end:]
    elif action == "insert_before":
        return text[:start] + suggestion + text[start:]
    elif action == "insert_after":
        return text[:end] + suggestion + text[end:]
    elif action == "keep_both":
        return text[:start] + suggestion + text[end:]
    else:
        raise ValueError(f"未知 action: {action}")
