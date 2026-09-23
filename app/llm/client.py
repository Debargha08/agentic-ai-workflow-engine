import os

from langchain_ollama import ChatOllama


def get_llm(num_predict: int = 256):
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
        num_predict=num_predict,
        num_ctx=2048,
        keep_alive="10m",
    )
