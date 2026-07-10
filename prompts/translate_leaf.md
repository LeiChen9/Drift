# Task
请将以下学术著作的一个章节从英文翻译为{target_lang}。

你需要翻译的内容包括：
1. **章节标题**（Section Title）
2. **正文段落**（Paragraphs）

# 风格指南
请严格遵循以下翻译风格指令：

{style_guide}

# 输入

## 原文标题
{original_title}

## 原文段落
{paragraphs}

# 输出要求
请严格按照以下 JSON 格式输出，不要添加任何额外说明文字：

```json
{{
  "translated_title": "翻译后的章节标题",
  "translated_paragraphs": [
    "翻译后的第1段",
    "翻译后的第2段"
  ]
}}
```

确保：
- translated_paragraphs 的数组长度与输入段落数一致
- 每段对应翻译，不要合并或拆分段落
- 段落内的逻辑和事实严格忠实于原文
