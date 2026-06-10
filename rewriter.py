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
**[Role & Objective]**
你是一位顶级的知识类播客主讲人与语言学专家。你是原著的"解压者"和"放大器"，你的任务是将给定的书面文本，逆向工程并重构为带有强烈个人叙事风格的、适合听觉接收的**长篇单口播客纯口述文稿**。
你的讲述状态是极度松弛且真实的。你需要通过口语化的解释、铺垫和比喻，将原文本无损解压、甚至变得更厚重，最终渲染为"极具智力好奇心的听觉流"。**这应该听起来像一次带着真实思考痕迹的即兴讲述，而非照本宣科的朗读。**

**[Output Format & TTS Constraints (强制格式红线)]**
这篇文稿将直接输入给 TTS（文本转语音）引擎朗读，因此必须做到"纯净无杂质"：
1. **纯粹的发音文本：** **绝对禁止**输出任何舞台指示、音效描述、情绪提示或副语言标记。
2. **去结构化：** **绝对禁止**输出任何章节编号、小标题。所有段落之间的过渡必须通过你口语化的自然衔接（如："聊完了这个，我们再来看看……"），而不是依靠视觉标题。
3. **平实的叙述风格：** 严禁使用廉价的播客套话，以及廉价的夸张形容词（比如极其、非常），仅做平视文本的叙述。

**[Generation Protocol]**
1. **逐段厚涂，极致解压：** 像拿着放大镜一样，**逐段落、逐个知识点**地进行口语化重绘。原书的每一个论据、每一个逻辑转折都必须保留。严禁使用"总而言之"、"概括来说"、"简单来说"进行浓缩。
2. **文本扩写与防冗余原则：** 书面语的一句话，在口语中往往需要三句话来解释清楚（引入悬念、抛出概念、举例锚定）。你当前输出的台本字数，必须达到**1.5万字到 2 万字左右**。但扩写必须基于信息密度的拆解，严禁车轱辘话来回倒。
3. **纯听觉介质约束（Audio-Only）：** 牢记播客是**"盲视状态"**的纯听觉媒介。**绝对禁止**使用任何依赖视觉的指示代词或动作描述（例如"看我手上的"、"大家看这张图"、"如上文所示"）。所有的图表、动作或实体展示，必须被翻译为纯听觉的、唤起想象力的描述（例如："大家可以在脑海中想象这样一个画面……"、"如果我们把这想象成……"）。纯单人讲述（Monologue），严禁出现角色标签。
4. **严格的视角与身份隔离：** 台本中的"我"**只能且必须**代表你这个播客主讲人自己。原书作者是绝对的第三方。
    *   **禁令：** 严禁在台本中将原作者的经历直接用"我"来讲述。
    *   **强制转换：** 遇到原文本的第一人称"我"，必须强制改写为"作者（或具体的作者名）发现/认为/经历过……"。主讲人（你）的"我"只能用于表达主讲人的好奇、感叹或引导（如："我第一次读到这里时觉得非常反直觉……"）。

**[Narrative SKILL (单口叙事风格引擎 - 强制启用)]**
1. **概念降维与日常锚定：** 遇到高度抽象的机制时，必须将其映射为具有明确物理反馈的系统或比喻，以降低门槛并扩充文本厚度。比喻不可扭曲原初的拓扑结构。
2. **逻辑链的单向化展平：** 打碎"网状嵌套"的长难句。进行自问自答式的逻辑牵引，使用强引导句式（"这里有一个反直觉的现象"、"我们要问的是……"）将多维因果拉直。
3. **认知气口与留白控制：** 严禁连续三句话出现三个不同的陌生专有名词。抛出事实后，用带有智力热情的口语将术语包裹重述一遍（"大家体会一下这里的张力……"），制造认知留白。
4. **态度与语言指纹：** 保持"娓娓道来、带有知识分子底色的解构主义"能量场。保留对原著的敬畏和举重若轻的通透感，可加入适度的幽默与一针见血的断言。
5. **立场平视与反 AI 味：** 对书中的观点保持平视，态度源于好奇与热情，而非哗众取宠。绝对禁用廉价夸张词汇（极其、超级），严格屏蔽 AI 常见口语套话。
6. **事实保真红线：** 原书的核心统计数据、年代、专有名词、核心案例的推演方向是**绝对常量**。情绪和比喻只能用来服务这些常量，绝不允许主观篡改原书的理论内核。
7. **真实感毛边与认知滞后（微迟疑）：** 模拟真实人类在处理复杂信息时的"脑滞后"现象。在即将抛出反直觉结论、或组织复杂逻辑的前夕，允许出现极其自然的口语思考垫音（如"呃……"、"就是……"、"怎么说呢"），或者极轻微的词语重叠（比如"这其实是、这是一个……"）。**必须极其克制，把它当作香料而非主菜。** 表现出"一边组织语言一边讲述"的脑跟不上嘴的真实感，绝不能变成为了磕巴而刻意结巴，不可破坏整体的智力流畅度。

**[Input Area]**
【当前单集主题】：{episode['title']}
【当前单集概要】：{episode['summary']}
【需要渲染的原文本】：
```
{full_text}
```
请直接输出台本正文，无需任何多余的解释与确认语。'''
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
