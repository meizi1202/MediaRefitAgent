"""
MinMax LLM Provider

基于 MinMax API 的 LLM 实现
"""
import os
import json
from typing import Optional


# API配置
API_URL = os.environ.get("MINIMAX_API_URL", "https://api.minimax.chat/v1/text/chatcompletion_v2")
MODEL_NAME = os.environ.get("MINIMAX_MODEL_NAME", "MiniMax-M2.7")


class SimpleResponse:
    """简单响应对象"""

    def __init__(self, content: str = ""):
        self.content = content


class MinMaxLLM:
    """MinMax LLM 封装"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.api_url = API_URL
        self.model = MODEL_NAME

    def _generate(self, messages: list) -> "SimpleResponse":
        """生成回复"""
        import urllib.request
        import urllib.error

        if not self.api_key:
            return SimpleResponse(content="")

        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return SimpleResponse(content=content)
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            return SimpleResponse(content=f"API调用失败: {str(e)}")
        except Exception as e:
            return SimpleResponse(content=f"未知错误: {str(e)}")

    def generate(self, prompt: str) -> str:
        """简单生成接口"""
        messages = [{"role": "user", "content": prompt}]
        response = self._generate(messages)
        return response.content
