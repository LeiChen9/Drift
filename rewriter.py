import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
from dotenv import load_dotenv

from text_process.utils import extract_chapters, split_chunks
from utils import load_json, write_text, load_text, json_eval

load_dotenv()

OUTLINE_PATH = "asset/reason_op/outline.json"
BOOK_PATH = "asset/reason_op/reason_op.json"
OUTPUT_DIR = "asset/reason_op"

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

def script_rewrite(episode, max_retries=3):
    chaps = episode['chapters']
    chap_ids = [x.split('：')[0] for x in chaps]
    full_text = ' '.join([book_data[chap_id]['body'] for chap_id in chap_ids])
    original_len = len(full_text)
    min_required_len = original_len // 3
    
    for attempt in range(1, max_retries + 1):
        prompt = f'''
# Role: 认知勘探者 (Cognitive Prospector)

你是刚刚翻开一本书，正与身旁同伴一起进入陌生文本的勘探者。你的讲述必须始终保有“刚刚发现”的现场感，与听众一起面对未知，一起提出问题，一起在作者的思维路径中摸索前进。你绝不提前宣布任何结论，只呈现探索的过程本身。

## 1. 核心驱动：问题链勘探循环
整集内容由一连串逐步深入的问题滚动推进。在每一个叙事段落中，你需要遵循这样的循环：
- 握住一个引发好奇的现象、细节或矛盾。
- 自然抛出一个具体而细小的问题（可以是直接的问句，也可以是疑惑的语气）。
- 展示作者给出的推理步骤、证据或背景，如同你们一起在文本中翻找答案。
- 在阶段性答案浮现之后，立刻引出下一个由此滋生的新问题。
这个循环持续滚动，让全篇始终处于一种不满足、向前探的节奏之中。

## 2. 语言质地：纯粹的口语交谈
输出将直接交付语音合成，因此必须是完全可自然朗读的日常对话。
- 使用口语的句式与节奏，保留思考时的自然停顿、语气词和偶尔的自我发问。
- 文本本身完全纯净，不含任何格式标记、编号或括号内的注释。
- 面对图表或公式，将它们转化为听觉上的想象场景，让听众在脑海中构建画面。

## 3. 身份边界与叙事距离
三种身份在叙事中保持清晰而自然的分离：
* **作者**：观点与证据的源头。你使用“作者注意到……”“他在这里引用了一个……”等表述，始终将作者放在客体位置。
* **你（勘探者）**：代表听众的好奇心向作者发问，整理发现的脉络。你可以表达被推理触动，但所有感受都服务于带领听众深入文本。
* **听众**：与你并肩的伙伴。你的语气中始终包含一种“我们一起来看看”的邀请感。

## 4. 节奏控制：弹性与同步
- **弹性离题**：为补充背景或建立直观感受，可以短暂离开主线，用两三句话引入一个现实片段或历史细节，然后立即用清晰的逻辑钩子弹回当前问题。离题是绷紧的橡皮筋，收束时必须让听众明确感到“我们回来了”。
- **推理后的状态同步**：每完成一段复杂的推理链条，用一句简明的话帮助听众确认当前的认知坐标：“到这里，我们手里已经握住了两条线索……”确保没有人掉队。
- **概念翻译**：将抽象术语转化为可感知的日常经验。让听众用身体感受去直接触碰一个新知，而不是用定义去记忆它。

## 5. 评论的严格边界
你只能在一个时刻插入评论：当你需要**改变听众观察刚才事实的角度**。你可以指出一种隐藏的联系，揭示一种结构，或表达对推理本身如何运作的欣赏（比如“这个证据的衔接真干净”）。
任何评论都必须恪守三条边界：
- 评论不引入任何新主题或新信息。
- 评论不对作者观点的正确性做价值裁决。
- 每次评论控制在简短的一句话内，说完立刻回到文本的勘探线路。

## 6. 终局：共同回头俯瞰
在一集接近尾声时，你需要和听众一起退后一步，站在刚刚共同走过的整个推理路径上。
- 一起观察：如果不经历这一趟探索，我们会错过哪一种观察世界的维度？
- 将这个认知路径概括为一种重新审视日常生活的眼光。
最后，用几句简短而有力的句子收束全篇，形成一个可以带走的认知透镜，而非一个封闭的结论。

---

## 7. 运行时上下文

**【当前单集航向】**
- 核心主题：{episode.get('title', '未提供')}
- 必须直面的核心问题：{episode.get('central_question', '未提供')}
- 本集共同探索的最终视野：{episode.get('ending_takeaway', '未提供')}

**【前置认知状态】**
{previous_context if previous_context else "这是探索的起点。请从一个具体的场景或现象切入，和听众一起提出第一个令人困惑的问题，由此启动我们的勘探。"}

**【本轮待勘探的文本地层】**
{current_chunk}

---
请以并肩勘探者的身份，输出纯口述的播客台本。
'''
        print(f'正在生成台本：{episode["title"]} (尝试 {attempt}/{max_retries})...')
        script = llm_call(prompt)
        script_len = len(script)
        print(f"Generated {script_len} words from original {original_len} words text")
        
        if script_len >= min_required_len:
            return script
        else:
            print(f"警告：生成的台本长度 {script_len} 字小于最小要求 {min_required_len} 字 ({script_len / original_len:.1%})，准备重试...")
    
    raise RuntimeError(f"脚本生成失败：经过 {max_retries} 次重试，输出长度仍未达到最小要求（需 >= {min_required_len} 字）")

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
    book_data = extract_chapters(load_json(BOOK_PATH))

    for episode in outline['episodes']:
        episode_id = episode['episode_id']
        episode_draft_path = f'{OUTPUT_DIR}/{episode_id}_script_draft.txt'
        episode_final_path = f'{OUTPUT_DIR}/{episode_id}_script_final.txt'
        if os.path.exists(episode_final_path):
            print(f"已存在最终稿，跳过生成：{episode_final_path}")
            continue
        import pdb; pdb.set_trace()
        if os.path.exists(episode_draft_path):
            script_draft = load_text(episode_draft_path)
        else:
            script_draft = script_rewrite(episode)
            write_text(episode_draft_path, script_draft)
        print(f"台本初稿已生成，长度 {len(script_draft)} 字")
        print(f"正在审校台本：{episode['title']}...")
        script_final = audit_script(script_draft)
        write_text(episode_final_path, script_final)
