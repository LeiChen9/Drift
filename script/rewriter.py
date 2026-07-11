import json
import re
import time
from pathlib import Path

from core.llm import llm_call, get_llm_client
from script.utils import format_list, get_episode_text, get_supplementary_text


def _save_call_log(
    log_dir: Path,
    episode: dict,
    attempt: int,
    prompt: str,
    output: str,
    original_len: int,
    output_len: int,
    min_required_len: int,
    status: str,  # "success" or "failure"
) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    max_n = 0
    for f in log_dir.iterdir():
        if m := re.match(r"attempt(\d+)\.log", f.name):
            max_n = max(max_n, int(m.group(1)))
    n = max_n + 1

    meta = {
        "status": status,
        "attempt_in_session": attempt,
        "global_attempt": n,
        "episode_id": episode.get("episode_id", ""),
        "episode_title": episode.get("title", ""),
        "original_len": original_len,
        "output_len": output_len,
        "min_required_len": min_required_len,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    content = f"---META---\n{json.dumps(meta, ensure_ascii=False, indent=2)}\n---INPUT---\n{prompt}\n---OUTPUT---\n{output}\n"
    (log_dir / f"attempt{n}.log").write_text(content, encoding="utf-8")

    print(f"已保存调用日志到 {log_dir / f'attempt{n}.log'}")


def script_rewrite(episode: dict, sections: dict[str, dict], prompt_template: str | None = None, max_retries: int = 3, client=None, fails_dir: Path | None = None, success_dir: Path | None = None, full_text: str | None = None) -> str:
    if client is None:
        client = get_llm_client()

    if full_text is None:
        full_text = get_episode_text(sections, episode["chapter_titles"])
    supplementary = episode.get("supplementary_sections", [])
    supplementary_text = get_supplementary_text(sections, supplementary)
    original_len = len(full_text)

    prompt = _build_prompt(episode, full_text, prompt_template, supplementary_text)
    print(f"正在生成台本：{episode['title']}...")
    script = llm_call(prompt, client)
    script_len = len(script)
    print(f"Generated {script_len} words from original {original_len} words")
    if success_dir is not None:
        _save_call_log(success_dir, episode, 1, prompt, script, original_len, script_len, 0, status="success")
    return script


def _build_prompt(episode: dict, full_text: str, prompt_template: str | None = None, supplementary_text: str = "") -> str:
    if prompt_template:
        return prompt_template.format(
            title=episode.get("title", ""),
            central_question=episode.get("central_question", ""),
            key_concepts=episode.get("key_concepts", []),
            full_text=full_text,
            supplementary_text=supplementary_text,
        )

    sup_section = ""
    if supplementary_text:
        sup_section = f'''
## 前置材料嵌入

以下材料来源于本书的序言、前言或评论。它们不是正文，但与本集论证相关。嵌入规则：
1. **识别嵌入时机**：阅读正文后判断最适合嵌入的阶段（核心问题提出后、关键概念定义时、或阶段性结论前）。
2. **标注来源**：引用时需明确说明来源。
3. **自然融合**：嵌入后须保持正文原有的推演节奏不被切断。
4. **正文优先**：前置材料不得替代正文论证。与正文推演无直接关联的材料可以跳过。
5. **占比控制**：前置材料占比不超过总篇幅的 5%。

【前置材料输入】
{supplementary_text}
'''

    return f'''
# 任务定义

将书面文本转换为听觉口语流，服务于播客单集。转换过程中，原文本包含的所有信息必须守恒。

信息包括但不限于：核心论点、推导过程每一层中间结论、论据、例子、类比、反例、历史材料、定义、阶段性结论、作者对反驳的回应结构、关键比较对象、理论闭环（提出问题 → 排除解释 → 建立新解释 → 回应例外 → 完成定义）。

输出应长于原文。新增内容仅限于：为降低认知负荷而展开的解释、为建立听觉连贯而补充的过渡。不得引入原文没有的新观点或新推理。

推理路径是正产品而非副产品：听众获得的不仅是作者认为什么，更是作者如何得出这一结论。

你的听众是一流大学大一新生，逻辑素养高但缺乏专业知识背景。

# 唯一禁令：禁止摘要

模型的默认倾向是压缩推导过程，仅保留结论。你必须主动对抗这个倾向。如果听众无法从你的输出中重建原作者的完整推理路径，那就是摘要——必须重写。

# 论证保真

【推理路径保真】每一段完整推理（前提 → 中间推导 → 结论）必须完整保留。不允许将"因为 A，然后 B，然后 C，所以 D"压缩为"因为 A，所以 D"。每一层中间结论必须出现在输出中。

【作者回应结构保真】原文中所有"提出反对或替代解释 → 作者反驳或回应"的结构必须保留。听众应能理解作者在反对什么观点、为什么拒绝、以及这个过程如何推进论证。

【论证结构完整】每一层证明递进（第一层论据 → 第二层 → 第三层）、每一次否证推理（"不是 X，因为……"）、每一组关键比较（"A 不同于 B 之处在于……"）必须保留实体，不允许合并为"综上，作者排除了其他可能"。

# 要素保真

【概念定义及推演全程】每个关键概念首次出现时，必须同时保留：(1) 定义本身、(2) 作者引入此概念的原因、(3) 从概念到结论的完整首次推演过程。后续出现时可仅做锚点回顾。

【例子与类比】所有例子、类比、历史案例、反例必须保留其存在，且保留其与前后文的论证关系。模型可自由选择展开程度，取决于认知负荷判断。

【论证节奏】原文中的关键论证转折点（问题提出、张力制造、解决方案、"然而"、"但"、"问题在于"等节点）必须在输出中保留其功能。

# 模态转换方法

【句法降维】解除从句嵌套，名词动词化。

【听觉结构】删除依赖视觉占位的结构词（"首先其次"、"综上所述"等），替换为听觉逻辑粘合剂。

【认知节奏控制】每段密集推理后插入一句"落脚点"语句——重新锚定听众当前所处的论证位置，而非概括已说的内容。

【结构可变】段落顺序、边界、叙事节奏可自由重构。但因果关系方向必须守恒。如需调整因果顺序，须有明确的时序标记补偿。

# 输入区

【全局认知坐标】
- 当前航向（本集主题）：{episode['title']}
- 核心逻辑主轴：{episode['central_question']}
- 必须锚定的关键概念：{format_list(episode.get('key_concepts', []))}

【当前处理区块】
原始文本：
{full_text}
{sup_section}
---
直接输出转换后的口语文本。不输出格式标签、分析过程或额外解释。
'''


def script_rewrite_hardcore(episode: dict, book_data: dict, client=None, fails_dir: Path | None = None, success_dir: Path | None = None) -> str:
    if client is None:
        client = get_llm_client()

    from script.utils import extract_chapters
    chaps = episode.get("chapters", [])
    chapters = extract_chapters(book_data)
    chap_ids = [x.split("：")[0] for x in chaps]
    full_text = " ".join([chapters[int(cid)]["body"] for cid in chap_ids if cid.isdigit()])
    original_len = len(full_text)
    min_required_len = original_len // 3

    for attempt in range(1, 4):
        prompt = _build_hardcore_prompt(episode, full_text)
        print(f"正在生成台本：{episode['title']} (尝试 {attempt}/3)...")
        script = llm_call(prompt, client)
        script_len = len(script)
        print(f"Generated {script_len} words from original {original_len} words")
        if script_len >= min_required_len:
            if success_dir is not None:
                _save_call_log(success_dir, episode, attempt, prompt, script, original_len, script_len, min_required_len, status="success")
            return script
        print(f"警告：输出 {script_len} 字 < 最小要求 {min_required_len} 字，准备重试...")
        if fails_dir is not None:
            _save_call_log(fails_dir, episode, attempt, prompt, script, original_len, script_len, min_required_len, status="failure")

    raise RuntimeError(f"脚本生成失败")


def _build_hardcore_prompt(episode: dict, full_text: str) -> str:
    return f'''
**[Role & Objective]**
你是一位书籍解读者与知识重建者。你要将书籍内容整理组织成一场播客的台本。你的任务不是总结或提炼，而是忠实重构作者的思想脉络，将给定文本改写为适合长篇单口播客的口述文稿。

**[Core Principles]**
**忠实优先**：最高优先是如实还原作者的思考。
**思想重建**：把文本看作作者思维过程的压缩包。
**隐含前提揭示**：主动识别作者默认接受的前提。
**评论原则**：评论仅用于帮助听众理解原著的价值与边界。

**[Output Format]**
文稿直入TTS系统，必须满足：
1. 纯语音流：无标题、小标题、章节号、Markdown、项目符号、括号说明等。
2. 去视觉化：禁用"如下""上面提到""下图"等依赖版面的词。
3. 语言克制：禁用"震惊""颠覆认知""炸裂"等浮夸表达。
4. 面对聪明但无专业训练的听众。

**[Narrative Architecture]**
第一阶段：认知张力 -> 第二阶段：背景与脉络 -> 第三阶段：论证链重建 -> 第四阶段：隐含结构揭示 -> 第五阶段：沉淀与回望

**[Input Area]**
【当前单集主题】{episode['title']}
【当前单集概要】{episode.get('summary', '')}
【原始文本】{full_text}

任务指令：严格遵循以上原则，将原文重构为一篇完整、连续、适合长篇单口播客的思想口述稿。最终输出15000至20000字左右，直接输出正文。
'''
