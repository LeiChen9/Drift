import json
import re

from core.llm import llm_call, get_llm_client


def review_script(full_text: str, draft: str, client=None) -> list[dict]:
    if client is None:
        client = get_llm_client()

    prompt = _build_review_prompt(full_text, draft)
    response = llm_call(prompt, client)
    issues = _parse_issues(response)
    return issues


def _parse_issues(response: str) -> list[dict]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        text = text[start : end + 1]
    else:
        return []
    return json.loads(text, strict=False)


def _build_review_prompt(full_text: str, draft: str) -> str:
    return f'''你是一名严格的审校编辑。你的任务是对比【原文】和【播客台本】，找出台本中存在的四类问题。

## 四类问题定义

1. **distortion（意思扭曲）**：台本对原文意思表述不准确、曲解了原意。
   例如原文说"A是因为B"，台本说"A是因为C"；或原文的限定条件被忽略导致意思改变。

2. **omission（遗漏）**：原文中作者用来支撑论点的关键论据、推理步骤、重要案例或数据
   在台本中被完全跳过，导致论证链不完整。
   *排除*：原文中啰嗦的修辞重复、过渡填充句等有意精简掉的内容不算遗漏。

3. **unfamiliar（概念陌生）**：原文中出现的目标听众（大一新生，逻辑素养高但专业知识
   薄弱）大概率不掌握的概念、术语、历史背景、人物、实验等，台本中没有宕开解释。

4. **substitution（概念替换）**：台本对某个专业概念做了解释性展开，但展开后的内容
   实际上替代了原文中该概念的精确表述，导致听众不知道原文中这个概念具体叫什么。
   *修复方向*：保留展开解释的同时也要保留原文中的精确术语/概念表述。

## 输出格式

严格按以下 JSON 数组格式输出。如果没有任何问题，输出空数组 []。
不要输出任何其他内容（不要代码块标记）。

[
  {{
    "type": "distortion|omission|unfamiliar|substitution",
    "original": "原文中对应的片段（用于人工核对）",
    "draft": "台本中对应的片段（**必须直接摘录台本原文**，用于程序定位匹配）",
    "severity": "high|medium|low",
    "action": "rewrite|insert_before|insert_after|delete|keep_both",
    "suggestion": "建议的替换文本或补充内容",
    "reasoning": "为什么这是问题，给人看的简短说明（20-50字）"
  }}
]

action 字段的含义：
- **rewrite**: 用 suggestion 替换 draft 片段
- **insert_before**: 在 draft 片段之前插入 suggestion
- **insert_after**: 在 draft 片段之后插入 suggestion
- **delete**: 删除 draft 片段（suggestion 填空字符串 ""）
- **keep_both**: 用 suggestion（应同时包含原文术语和解释）替换 draft 片段

## 规则

- draft 字段**必须直接摘录台本原文**，以便程序能精确定位。不要改写、不要重述。
- 优先报告 high severity 的问题。同一处问题不要重复报告。
- medium 和 low 可以酌情忽略，宁缺毋滥。
- 如果你认为台本与原文完全一致、无明显问题，输出 []。

--- 原文 ---
{full_text}

--- 台本 ---
{draft}'''
