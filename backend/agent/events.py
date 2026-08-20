"""
SSE 事件队列模块

用于在 Agent 处理过程中实时发送事件到 SSE 客户端
"""
import asyncio
import json
import time
from typing import Optional, Callable, AsyncGenerator
from threading import Lock


class EventQueue:
    """线程安全的事件队列"""

    def __init__(self):
        self._queue: list[str] = []
        self._lock = Lock()
        self._event_callback: Optional[Callable[[str], None]] = None

    def put(self, event_data: dict):
        """添加事件到队列"""
        with self._lock:
            self._queue.append(json.dumps(event_data, ensure_ascii=False))
            # 如果有回调，立即调用
            if self._event_callback:
                self._event_callback(json.dumps(event_data, ensure_ascii=False))

    def get_all(self) -> list[str]:
        """获取所有事件并清空队列"""
        with self._lock:
            events = self._queue.copy()
            self._queue.clear()
            return events

    def set_callback(self, callback: Callable[[str], None]):
        """设置事件回调"""
        self._event_callback = callback


# 全局事件队列
_event_queue: Optional[EventQueue] = None
_queue_lock = Lock()


def get_event_queue() -> EventQueue:
    """获取全局事件队列"""
    global _event_queue
    with _queue_lock:
        if _event_queue is None:
            _event_queue = EventQueue()
        return _event_queue


def send_event(event_type: str, data: dict):
    """发送事件"""
    event_data = {
        "event": event_type,
        "created_at": int(time.time()),
        **data
    }
    queue = get_event_queue()
    queue.put(event_data)


def send_message_chunk(content: str):
    """发送消息片段"""
    send_event("message", {"answer": content})


def send_message_end(conversation_id: str = "", metadata: dict = None):
    """发送消息结束"""
    send_event("message_end", {
        "conversation_id": conversation_id,
        "metadata": metadata or {}
    })


def clear_event_queue():
    """清空事件队列"""
    queue = get_event_queue()
    queue.get_all()  # 消费所有事件


# 异步事件生成器
async def event_generator(queue: EventQueue, timeout: float = 60.0) -> AsyncGenerator[str, None]:
    """异步事件生成器，用于 SSE"""
    last_check = time.time()

    while True:
        # 等待新事件或超时
        events = []
        start_time = time.time()

        # 轮询检查新事件
        while time.time() - start_time < timeout:
            events = queue.get_all()
            if events:
                break
            await asyncio.sleep(0.1)  # 100ms 轮询间隔

        # 发送事件
        for event in events:
            yield f"data: {event}\n\n"

        # 如果没有事件且超时，发送 ping
        if not events:
            yield f"data: {json.dumps({'event': 'ping', 'created_at': int(time.time())})}\n\n"

        # 检查是否结束（通过检查队列是否被清空）
        if hasattr(queue, '_finished') and queue._finished:
            break


class SyncEventQueue:
    """同步模式的事件队列，用于不支持异步的场景"""

    def __init__(self):
        self._queue: list[dict] = []
        self._finished = False

    def put(self, event_data: dict):
        """添加事件"""
        self._queue.append(event_data)

    def get_all(self) -> list[dict]:
        """获取所有事件"""
        events = self._queue.copy()
        self._queue.clear()
        return events

    def finish(self):
        """标记结束"""
        self._finished = True

    @property
    def is_finished(self) -> bool:
        return self._finished
