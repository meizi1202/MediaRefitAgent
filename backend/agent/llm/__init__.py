"""
LLM 模块

统一 LLM 接口，支持多种 provider
"""
from agent.llm.minimax import MinMaxLLM, SimpleResponse

__all__ = [
    "MinMaxLLM",
    "SimpleResponse",
]
