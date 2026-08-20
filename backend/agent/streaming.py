"""
流式消息支持模块

用于在 Agent 处理过程中实时发送消息到 SSE 客户端
"""
import asyncio
import json
import re
import time
import threading
from typing import Callable, Optional, Any
from datetime import datetime


class StreamQueue:
    """线程安全的流式消息队列"""

    def __init__(self):
        self._queue: list[str] = []
        self._lock = threading.Lock()
        self._event = threading.Event()

    def put(self, content: str):
        """添加消息到队列"""
        with self._lock:
            self._queue.append(content)
        self._event.set()  # 通知有新消息

    def get_all(self):
        """获取所有消息并清空"""
        with self._lock:
            messages = self._queue.copy()
            self._queue.clear()
        return messages

    def wait(self, timeout: float = None) -> bool:
        """等待新消息"""
        return self._event.wait(timeout=timeout)

    def clear_event(self):
        """清除事件状态"""
        self._event.clear()


# 全局流式队列
_stream_queue: Optional[StreamQueue] = None
_streaming_enabled = False


def get_stream_queue() -> StreamQueue:
    """获取全局流式队列"""
    global _stream_queue
    if _stream_queue is None:
        _stream_queue = StreamQueue()
    return _stream_queue


def set_streaming_enabled(enabled: bool):
    """设置是否启用流式输出"""
    global _streaming_enabled
    _streaming_enabled = enabled


def is_streaming_enabled() -> bool:
    """检查是否启用流式输出"""
    return _streaming_enabled


def clear_message_callback():
    """清除消息回调（兼容旧接口）"""
    pass


# ============ Chunk 分块逻辑 ============

# 中文标点符号
CHINESE_PUNCTUATION = '。！？；：、'
# 英文标点符号
ENGLISH_PUNCTUATION = '.!?;:,'


def chunk_text_by_punctuation(text: str) -> list[str]:
    """
    按标点符号分块，保留标点在每块末尾
    保留比例格式（如 9:16, 16:9）不被拆分

    例如: "你好！我是AI。很高兴认识你？请选择比例：9:16 或 16:9"
    -> ["你好！", "我是AI。", "很高兴认识你？", "请选择比例：9:16 或 16:9"]
    """
    if not text:
        return []

    chunks = []
    current = ""
    i = 0

    while i < len(text):
        char = text[i]

        # 检测比例格式（如 9:16, 16:9）
        # 格式：数字:数字
        if char.isdigit() and i + 2 < len(text):
            next_chars = text[i:i+3]
            if text[i+1] == ':' and text[i+2].isdigit():
                # 这是比例格式，保留完整
                current += next_chars
                i += 3
                continue

        current += char
        if char in CHINESE_PUNCTUATION or (char in ENGLISH_PUNCTUATION and char != ':'):
            chunks.append(current)
            current = ""
        i += 1

    # 处理剩余内容
    if current:
        chunks.append(current)

    return chunks


def chunk_text_fixed_size(text: str, chunk_size: int = 10) -> list[str]:
    """
    固定大小分块

    Args:
        text: 待分块文本
        chunk_size: 每块字符数
    """
    if not text:
        return []
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]


def chunk_text_smart(text: str, max_chunk_size: int = 20) -> list[str]:
    """
    智能分块：优先按标点分块，标点间距过长时按固定大小分块
    保留比例格式（如 9:16, 16:9）不被拆分

    Args:
        text: 待分块文本
        max_chunk_size: 最大块大小
    """
    if not text:
        return []

    # 先按标点分块
    punctuation_chunks = chunk_text_by_punctuation(text)

    result = []
    for chunk in punctuation_chunks:
        if len(chunk) <= max_chunk_size:
            result.append(chunk)
        else:
            # 超过最大大小时，按固定大小再分
            result.extend(chunk_text_fixed_size(chunk, max_chunk_size))

    return result


def send_stream_chunk(content: str, delay: float = 0.1):
    """
    发送分块内容到队列（模拟打字机效果）

    Args:
        content: 内容
        delay: 每个分块之间的延迟（秒）
    """
    if not _streaming_enabled:
        return

    queue = get_stream_queue()
    # 使用更小的 chunk_size 实现更流畅的逐字效果
    chunks = chunk_text_smart(content, max_chunk_size=5)

    for chunk in chunks:
        queue.put(chunk)
        time.sleep(delay)


def send_stream_message(content: str):
    """发送流式消息到队列（不分块，直接发送）"""
    if not _streaming_enabled:
        return
    queue = get_stream_queue()
    print(f"[DEBUG] send_stream_message: {content[:50]}...")
    queue.put(content)


def create_stream_message(role: str, content: str) -> dict:
    """创建消息字典"""
    return {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
