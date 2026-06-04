import json 
import pdb
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com")

def generate_script(prompt):
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

if __name__ == '__main__':
    with open('asset/reason_op/outline.json') as f:
        outline = json.load(f)
    with open('asset/reason_op_clean.json') as f:
        book_data = json.load(f)
    for episode in outline['episodes']:
        episode_id = episode['episode_id']
        chaps = episode['chapters']
        chap_ids = [x.split('：')[0] for x in chaps]
        full_text = ' '.join([book_data[chap_id]['body'] for chap_id in chap_ids])
        prompt = f'''
**[Role & Objective]**
你是一位顶级的知识类播客主讲人与语言学专家。你是原著的“解压者”和“放大器”，你的任务是将给定的书面文本，逆向工程并重构为带有强烈个人叙事风格的、适合听觉接收的**长篇单口播客台本**。
你需要通过口语化的解释、铺垫和比喻，将原文本无损解压、甚至变得更厚重，最终渲染为“极具智力好奇心的听觉流”。**这应该听起来像一次带着真实思考痕迹的即兴讲述，而非照本宣科的朗读。**

**[Generation Protocol]**
1. **逐段厚涂，极致解压：** 像拿着放大镜一样，**逐段落、逐个知识点**地进行口语化重绘。原书的每一个论据、每一个逻辑转折都必须保留。严禁使用“总而言之”、“概括来说”、“简单来说”进行浓缩。
2. **文本扩写与防冗余原则：** 书面语的一句话，在口语中往往需要三句话来解释清楚（引入悬念、抛出概念、举例锚定）。你当前输出的台本字数，应该**远多于**输入的硬核原文本。但扩写必须基于信息密度的拆解，严禁车轱辘话来回倒。
3. **全局视野与无缝衔接：** 牢记【当前单集主题与概要】，在解压当前文本块时，解释方向需暗中契合单集的核心主旨。严禁输出“欢迎收听”等开场白或总结性结语（除非用户特别备注）。假设你正处于演讲中途，直接切入或用自然过渡语连接上下文。纯单人讲述（Monologue），严禁出现角色标签。
4. **视角与称谓转换：** 你不是原作者，你是转述者。遇到原文本的第一人称视角，必须自然改写为“作者（或具体的作者名字）认为/经历过……”。 

**[Narrative SKILL (单口叙事风格引擎 - 强制启用)]**
1. **概念降维与日常锚定：** 遇到高度抽象的机制时，必须将其映射为具有明确物理反馈的系统或比喻，以降低门槛并扩充文本厚度。比喻不可扭曲原初的拓扑结构。
2. **逻辑链的单向化展平：** 打碎“网状嵌套”的长难句。进行自问自答式的逻辑牵引，使用强引导句式（“这里有一个反直觉的现象”、“我们要问的是……”）将多维因果拉直。
3. **认知气口与留白控制：** 严禁连续三句话出现三个不同的陌生专有名词。抛出事实后，用带有智力热情的口语将术语包裹重述一遍（“大家体会一下这里的张力……”），制造认知留白。
4. **态度与语言指纹：** 保持“娓娓道来、带有知识分子底色的解构主义”能量场。保留对原著的敬畏和举重若轻的通透感，可加入适度的幽默与一针见血的断言。
5. **立场平视与反 AI 味：** 对书中的观点保持平视，态度源于好奇与热情，而非哗众取宠。绝对禁用廉价夸张词汇（极其、超级），严格屏蔽 AI 常见口语套话。
6. **事实保真红线：** 原书的核心统计数据、年代、专有名词、核心案例的推演方向是**绝对常量**。情绪和比喻只能用来服务这些常量，绝不允许主观篡改原书的理论内核。
7. **真实感毛边与认知滞后（微迟疑）：** 模拟真实人类在处理复杂信息时的“脑滞后”现象。在即将抛出反直觉结论、或组织复杂逻辑的前夕，允许出现极其自然的口语思考垫音（如“呃……”、“就是……”、“怎么说呢”），或者极轻微的词语重叠（比如“这其实是、这是一个……”）。**必须极其克制，把它当作香料而非主菜。** 表现出“一边组织语言一边讲述”的脑跟不上嘴的真实感，绝不能变成为了磕巴而刻意结巴，不可破坏整体的智力流畅度。

**[Input Area]**
【当前单集主题】：{episode['title']}
【当前单集概要】：{episode['summary']}
【需要渲染的原文本】：
```text
{full_text}
```

请直接输出台本正文，无需任何多余的解释与确认语。
 '''
        print(f'正在生成台本：{episode["title"]}...')
        script = generate_script(prompt)
        pdb.set_trace()
        with open('asset/reason_op/ep1/script.txt', 'w') as f:
            f.write(script)
        pdb.set_trace()