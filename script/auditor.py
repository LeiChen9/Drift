from concurrent.futures import ThreadPoolExecutor, as_completed

from core.llm import llm_call, get_llm_client
from core.utils import json_eval
from script.utils import split_chunks


def _audit_chunk(idx, total, chunk, max_retries=3, client=None):
    if client is None:
        client = get_llm_client()

    chunk_ori_len = len(chunk)

    for attempt in range(1, max_retries + 1):
        print(f"audit: chunk {idx + 1}/{total}, chars={chunk_ori_len}, 尝试 {attempt}/{max_retries}")
        prompt = f'''
**[Role & Objective]**
你是一名顶级的中文播客台本编辑。你需要深入阅读理解传入的【播客台本片段】，对其进行内容审校，并输出经过审阅与纠偏的【完整台本片段】。

请严格执行以下两大模块的编辑任务：

### 模块一：身份视角校准（内容编审）
当前片段可能混淆了"播客主播"与"原书作者"的身份。在没有任何外部背景信息的情况下，你必须依靠文本内的逻辑线索进行精准切割：
1. **剥离作者身份**：原书作者的经历、写作行为、职业背景、亲身观察、个人判断与遭遇，**绝对不能**以"我"的第一人称出现。请将其转换为自然的第三方表述（如"作者写道"、"作者回忆"、"书中提到"、"这位作者指出"等，请根据语境灵活遣词）。
2. **保留主播身份**：只有播客主讲人的阅读感受、讲述引导、互动提问、转场串词等，才可以保留"我"的自称。
3. **精准打击**：切忌机械替换全篇的"我"，必须逐句推敲每一个"我"的真实指代。

### 模块二：TTS 朗读纯净度（后期制作）
将文本转化为"听觉友好"的极致口语状态：
1. **数字全汉字化**：将所有阿拉伯数字、百分号、小数、年份/年代、范围、金额、单位、序号，全部转换为自然中文读法。非必要不保留任何数字。
2. **多音字/异读词规避**：主动识别并消除所有可能导致 TTS 引擎读错的歧义词、多音字和冷僻专名。**严禁使用拼音或括号注音**，必须通过**"同义词替换"**或**"语序微调"**的方式改写。英文词汇不属于异读词范畴，保持英文原文不变，不要做汉化或同义词替换。
3. **视觉符号清理**：清除括号注、无法朗读的标点及视觉排版格式，保留适合语音停顿的自然标点。

### ⚠️ 绝对禁忌（Guardrails）
- 不要压缩摘要，不要扩写发散。
- 严禁改变原有的事实逻辑与讲述顺序。
- 严禁破坏台本内容和表达，仅做上面两个模块的校正，其余保持原样。

【当前片段】
{chunk}

### 输出规范
请严格按照以下 JSON 格式返回，不要包含任何 Markdown 代码块标记（如 ```json），直接返回纯 JSON 字符串：
{{
    "text": "经过审校纠正的台本",
    "review_log": "纠偏的记录，逐条说明做了哪些修改。若无需修改，请填写'未发现问题'"
}}
'''
        reviewed_chunk_dict = json_eval(llm_call(prompt, client))
        reviewed_chunk_len = len(reviewed_chunk_dict["text"])
        change_ratio = (reviewed_chunk_len / chunk_ori_len - 1)
        print(f"审校结束，由{chunk_ori_len}个字变为{reviewed_chunk_len}个字, 变化幅度{change_ratio:.2%}, 审校日志: {reviewed_chunk_dict['review_log']}")

        if reviewed_chunk_len <= chunk_ori_len * 1.1 and reviewed_chunk_len >= chunk_ori_len * 0.9:
            return (idx, reviewed_chunk_dict["text"])
        print(f"警告：Chunk {idx + 1} 审校后文本长度变化超过10%（{change_ratio:.2%}），准备重试...")

    raise ValueError(f"Chunk {idx + 1}: 经过 {max_retries} 次重试，审校后文本长度变化仍超过10%")


def audit_script(script: str, chunk_chars: int = 4500, max_workers: int = 4, client=None) -> str:
    if client is None:
        client = get_llm_client()

    chunks = split_chunks(script, max_chars=chunk_chars)
    total = len(chunks)
    results: dict[int, str] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_audit_chunk, idx, total, chunk, 3, client): idx
            for idx, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            try:
                idx, reviewed_text = future.result()
                results[idx] = reviewed_text
            except ValueError as e:
                raise RuntimeError(f"审校失败：{str(e)}")

    reviewed = [results[i] for i in range(total)]
    return "\n\n".join(reviewed)
