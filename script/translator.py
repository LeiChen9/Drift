from pathlib import Path
from typing import Any

from core.llm import llm_call, get_llm_client
from core.utils import json_eval, read_text

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return read_text(PROMPTS_DIR / name)


class TranslationError(Exception):
    pass


class BookTranslator:
    def __init__(
        self,
        target_lang: str = "zh",
        source_lang: str = "en",
        max_retries: int = 3,
        style_guide: str | None = None,
    ):
        self.target_lang = target_lang
        self.source_lang = source_lang
        self.max_retries = max_retries
        self._style_guide = style_guide
        self.client = get_llm_client()
        self.key_map: dict[str, str] = {}
        self.failed_nodes: list[list[str]] = []

    def _get_sample_text(self, book_tree: dict) -> str:
        for key, node in book_tree.items():
            paragraphs = node.get("paragraphs", [])
            if paragraphs:
                return "\n\n".join(paragraphs[:5])
        return ""

    def generate_style_guide(self, book_tree: dict) -> str:
        sample = self._get_sample_text(book_tree)
        if not sample:
            return ""

        template = _load_prompt("translate_style_guide.md")
        prompt = f"{template}\n{sample}"

        print("正在生成翻译风格指南...")
        guide = llm_call(prompt, self.client)
        self._style_guide = guide
        return guide

    def translate_node(
        self, title: str, paragraphs: list[str]
    ) -> tuple[str, list[str]]:
        if not self._style_guide:
            raise TranslationError("style_guide not set, call generate_style_guide first")

        template = _load_prompt("translate_leaf.md")
        paragraphs_text = "\n\n".join(
            f"[{i+1}] {p}" for i, p in enumerate(paragraphs)
        )

        prompt = template.format(
            target_lang=self.target_lang,
            style_guide=self._style_guide,
            original_title=title,
            paragraphs=paragraphs_text,
        )

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"  翻译节点「{title[:40]}...」(尝试 {attempt}/{self.max_retries})")
                response = llm_call(prompt, self.client)
                result = json_eval(response)

                translated_title = result.get("translated_title", "")
                translated_paragraphs = result.get("translated_paragraphs", [])

                if not translated_title:
                    raise TranslationError("translated_title 为空")

                if len(translated_paragraphs) != len(paragraphs):
                    print(
                        f"  警告：段落数不匹配 (输入 {len(paragraphs)}, 输出 {len(translated_paragraphs)})，重试..."
                    )
                    raise TranslationError(
                        f"段落数不匹配: 输入 {len(paragraphs)} != 输出 {len(translated_paragraphs)}"
                    )

                return translated_title, translated_paragraphs

            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    print(f"  失败: {e}, 重试...")

        raise TranslationError(
            f"节点「{title}」翻译失败: {last_error}"
        )

    def translate_toc_tree(self, toc_tree: dict) -> dict:
        return self._translate_toc_recursive(toc_tree)

    def _translate_toc_recursive(self, node: Any) -> Any:
        if not isinstance(node, dict):
            return node
        result = {}
        for key, value in node.items():
            translated_key = self.key_map.get(key, key)
            result[translated_key] = self._translate_toc_recursive(value)
        return result


