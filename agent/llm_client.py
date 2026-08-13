"""
MinMax LLM 客户端 - LangChain 集成
"""
import os
import json
import requests
from typing import Optional, List, Any, Dict
from langchain_core.language_models.chat import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration


class MinMaxLLM(BaseChatModel):
    """MinMax 大模型客户端"""

    def __init__(self, api_key: str = None, model: str = "MiniMax-Text-01", base_url: str = "https://api.minimax.chat"):
        super().__init__()
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.model = model
        self.base_url = base_url
        self.api_version = "v1"

    @property
    def _llm_type(self) -> str:
        return "minimax"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> ChatResult:
        """生成回复"""
        # 转换消息格式
        chat_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, SystemMessage):
                role = "system"
            else:
                role = "user"
            chat_messages.append({"role": role, "content": msg.content})

        # API 请求
        url = f"{self.base_url}/{self.api_version}/text/chatcompletion_v2"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.model,
            "messages": chat_messages,
        }

        if stop:
            data["stop"] = stop

        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()

            # 解析响应
            choices = result.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
            else:
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "") or result.get("reply", "")

            message = AIMessage(content=content)
            return ChatResult(generations=[ChatGeneration(message=message)])

        except Exception as e:
            # 返回错误信息
            message = AIMessage(content=f"API调用失败: {str(e)}")
            return ChatResult(generations=[ChatGeneration(message=message)])

    def _llm_invocation_params(self, **kwargs) -> Dict[str, Any]:
        return {"model": self.model, "temperature": kwargs.get("temperature", 0.7)}
