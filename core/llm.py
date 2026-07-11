import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def get_llm_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    # return OpenAI(
    #     api_key=os.environ.get("INFER_DEEPSEEK_KEY"),
    #     base_url="https://inferaichat.com/v1",
    # )


def llm_call(prompt: str, client: OpenAI | None = None) -> str:
    if client is None:
        client = get_llm_client()
    response = client.chat.completions.create(
        model="deepseek-v4-pro", 
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        max_tokens=65536,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    prompt = "请帮我写一首关于春天的诗。"
    result = llm_call(prompt)
    print(result)