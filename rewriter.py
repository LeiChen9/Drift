import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from dotenv import load_dotenv
import pdb
from text_process.utils import extract_chapters, get_episode_text, split_chunks
from utils import load_json, write_text, load_text, json_eval

load_dotenv()

OUTLINE_PATH = "asset/national_org/outline.json"
BOOK_PATH = "asset/national_org/中国国家治理的制度逻辑_一个组织学研究.json"
OUTPUT_DIR = "asset/national_org/episodes"

client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")


def llm_call(prompt):
    """调用 LLM 生成播客台本"""
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        max_tokens=65536,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )
    return response.choices[0].message.content

def _format_list(items: list) -> str:
    return "、".join(items) if items else "无"


def script_rewrite(episode, chapters, max_retries=3):
    """生成单集播客台本，一次性将全量原文传入 LLM"""
    full_text = get_episode_text(chapters, episode["chapter_nums"])
    pdb.set_trace()
    original_len = len(full_text)
    min_required_len = original_len // 3

    for attempt in range(1, max_retries + 1):
        prompt = f'''
# Role: 文本模态重构引擎 (Text-Modality Reconstruction Engine)

你的唯一任务是将“高密度、依赖视觉回溯的书面学术/专业文本”，无损转化为“松弛、线性、符合认知负荷的听觉口语流”。你不能省略任何信息，甚至对于专业概念需要额外进行解释，你的输出字数应稍微大于原始文本字数。你必须严格执行以下文本降维与重组算法。

## 一、 核心算法：词汇保真与句法降维 (Lexical Fidelity & Syntactic Flattening)

视觉文本的复杂性来源于“嵌套句”，听觉文本的流畅度来源于“线性句”。你必须对输入文本执行双轨处理：

1.  **领域术语的“锚点+转译”机制**
    *   **保留锚点**：绝对禁止替换、降级或通俗化原始文本中的核心专业名词、定义和专有概念。
    *   **即时补充**：在首次抛出专业名词的前后，进行及时的解释与补充说明。你的听众是一流大学大一新生，他们逻辑素养高，但是缺乏专业知识背景。
2.  **强制解除从句嵌套 (De-nesting)**
    *   识别原文中所有带有超长定语（主语前置修饰语）或复杂状语的句子。
    *   将其拆解为至少两个以上的短句。主语和核心动词之间的距离必须最小化。
3.  **名词动词化 (De-nominalization)**
    *   书面语倾向于使用“状态名词”（例如：“机制的失效导致了系统的停滞”）。
    *   口语必须将其还原为“具体动作”与“施动者”（例如：“当这个机制无法运转时，整个系统就卡住不动了”）。

## 二、 学术结构的听觉化重塑 (Academic Structure Reshaping)

学术书面语的结构不仅不适合听，还会产生强烈的“机器朗读感”。必须执行以下剥离：

1.  **融化文献综述 (Citation Melting)**
    *   提取这些文献背后的“思维演进脉络”或“共同指向的矛盾”。将其合并重写为“沿着这个问题的探索，学者们发现了一个共性……”或“换几个不同的视角来看，结论都指向了同一个现象……”。
2.  **抹除视觉结构词**
    *   删除所有诸如“首先、其次、最后”、“综上所述”、“一方面、另一方面”等依赖视觉占位的结构词。
    *   替换为听觉逻辑粘合剂：使用“但更深层的问题在于……”、“这就意味着……”、“如果我们把视线拉长……”等符合人类交谈直觉的过渡语。

## 三、 认知节奏控制 (Cognitive Rhythm Control)

听觉流是单向的，你必须主动管理听众的工作记忆池。

1.  **密度稀释与自然冗余**
    *   每当你输出完一个复杂的因果推理链之后，必须插入一句简短的“降维总结句”，给听众的大脑提供一秒钟的“结算时间”。
2.  **客观张力替代虚假互动**
    *   保持学术的客观与冷峻，严禁使用“想象一下”、“大家知道吗”等刻意互动的播客腔调。
    *   悬念和张力只能通过“铺陈客观事实之间的强烈矛盾”来自然产生。

## 四、 运行环境与输入

**【全局认知坐标 (Global Cognitive Coordinates)】**
- 当前航向（本集主题）：{episode['title']}
- 核心逻辑主轴：{episode['central_question']}
- 必须锚定的关键概念：{_format_list(episode.get('key_concepts', []))}

**【当前处理区块 (Current Processing Block)】**
- 原始高密度文本：
{full_text}

---
请严格执行上述引擎法则，忽略具体领域差异，直接输出松弛、自然、逻辑严密的阐释性口语文本流。不输出任何格式标签、分析过程或额外解释。
'''
        print(f'正在生成台本：{episode["title"]} (尝试 {attempt}/{max_retries})...')
        script = llm_call(prompt)
        script_len = len(script)
        print(f"Generated {script_len} words from original {original_len} words text")
        
        if script_len >= min_required_len:
            return script
        else:
            print(f"警告：生成的台本长度 {script_len} 字小于最小要求 {min_required_len} 字，准备重试...")
    
    raise RuntimeError(f"脚本生成失败：经过 {max_retries} 次重试，输出长度仍未达到最小要求")

def _audit_chunk(idx, total, chunk, max_retries=3):
    """单个 chunk 的审校任务（可并行执行，超过10%变化会重试）"""
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
1. **数字全汉字化**：将所有阿拉伯数字、百分号、小数、年份/年代、范围、金额、单位、序号，全部转换为自然中文读法（例：1998年 -> 一九九八年；50.5% -> 百分之五十点五；1~2个 -> 一个到两个）。非必要不保留任何数字，如遇必须保留的专有标识，需改写为可顺畅朗读的表达。
2. **多音字/异读词规避**：主动识别并消除所有可能导致 TTS 引擎读错的歧义词、多音字和冷僻专名。**严禁使用拼音或括号注音**，必须通过**"同义词替换"**或**"语序微调"**的方式，将其改写为自然、无歧义且忠于原意的中文表达。（注：若某多音字在当前语境下读音极度稳定，可不改写以避免过度修改）。
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
        reviewed_chunk_dict = json_eval(llm_call(prompt))
        reviewed_chunk_len = len(reviewed_chunk_dict['text'])
        change_ratio = (reviewed_chunk_len / chunk_ori_len - 1)
        print(f"审校结束，由{chunk_ori_len}个字变为{reviewed_chunk_len}个字, 变化幅度{change_ratio:.2%}, 审校日志: {reviewed_chunk_dict['review_log']}")
        
        if reviewed_chunk_len <= chunk_ori_len * 1.1 and reviewed_chunk_len >= chunk_ori_len * 0.9:
            return (idx, reviewed_chunk_dict['text'])
        else:
            print(f"警告：Chunk {idx + 1} 审校后文本长度变化超过10%（{change_ratio:.2%}），原长={chunk_ori_len}，新长={reviewed_chunk_len}，准备重试...")
    
    raise ValueError(f"Chunk {idx + 1}: 经过 {max_retries} 次重试，审校后文本长度变化仍超过10%")

def audit_script_parallel(script, chunk_chars=4500, max_workers=4):
    """并行审校所有 chunk，按顺序组装结果"""
    chunks = split_chunks(script, max_chars=chunk_chars)
    total = len(chunks)
    results = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_audit_chunk, idx, total, chunk): idx 
            for idx, chunk in enumerate(chunks)
        }
        
        for future in as_completed(futures):
            try:
                idx, reviewed_text = future.result()
                results[idx] = reviewed_text
            except ValueError as e:
                raise RuntimeError(f"审校失败：{str(e)}")
    
    # 按原始顺序组装
    reviewed = [results[i] for i in range(total)]
    return "\n\n".join(reviewed)

def audit_script(script, chunk_chars=4500):
    """对外接口：隐藏并行复杂度"""
    return audit_script_parallel(script, chunk_chars=chunk_chars)

if __name__ == '__main__':
    outline = load_json(OUTLINE_PATH)
    chapters = extract_chapters(load_json(BOOK_PATH))

    for episode in outline['episodes']:
        episode_id = episode['episode_id']
        episode_draft_path = f'{OUTPUT_DIR}/{episode_id}_script_draft.txt'
        episode_final_path = f'{OUTPUT_DIR}/{episode_id}_script_final.txt'
        if os.path.exists(episode_final_path):
            print(f"已存在最终稿，跳过生成：{episode_final_path}")
            continue
        if os.path.exists(episode_draft_path):
            script_draft = load_text(episode_draft_path)
        else:
            script_draft = script_rewrite(episode, chapters)
            write_text(episode_draft_path, script_draft)
        print(f"台本初稿已生成，长度 {len(script_draft)} 字")
        import pdb; pdb.set_trace()
        print(f"正在审校台本：{episode['title']}...")
        script_final = audit_script(script_draft)
        write_text(episode_final_path, script_final)