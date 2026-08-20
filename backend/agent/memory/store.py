"""
会话历史存储
"""
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import Sequence


class MinMaxChatHistory:
    """基于 MinMaxLLM 的聊天历史，使用 LangChain 内存接口"""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self.messages: list[BaseMessage] = []

    def add_user_message(self, message: str) -> None:
        """添加用户消息"""
        self.messages.append(HumanMessage(content=message))

    def add_ai_message(self, message: str) -> None:
        """添加 AI 消息"""
        self.messages.append(AIMessage(content=message))

    def get_messages(self) -> Sequence[BaseMessage]:
        """获取所有消息"""
        return self.messages

    def clear(self) -> None:
        """清空历史"""
        self.messages = []


class SessionHistoryStore:
    """会话历史存储管理"""

    def __init__(self):
        self._histories: dict[str, MinMaxChatHistory] = {}

    def get_history(self, session_id: str) -> MinMaxChatHistory:
        """获取或创建会话历史"""
        if session_id not in self._histories:
            self._histories[session_id] = MinMaxChatHistory(session_id=session_id)
        return self._histories[session_id]

    def delete_history(self, session_id: str) -> bool:
        """删除会话历史"""
        if session_id in self._histories:
            del self._histories[session_id]
            return True
        return False

    def list_sessions(self) -> list[str]:
        """列出所有会话 ID"""
        return list(self._histories.keys())


# 全局历史存储
_history_store: Optional[SessionHistoryStore] = None


def get_history_store() -> SessionHistoryStore:
    """获取历史存储单例"""
    global _history_store
    if _history_store is None:
        _history_store = SessionHistoryStore()
    return _history_store


def get_conversation_history(session_id: str) -> MinMaxChatHistory:
    """获取会话历史"""
    return get_history_store().get_history(session_id)


def clear_conversation_history(session_id: str) -> bool:
    """清除会话历史"""
    return get_history_store().delete_history(session_id)
