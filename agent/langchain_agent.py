"""
MinMax LLM 意图解析

直接从 MinMax API 解析用户意图，不依赖 LangChain Agent
"""
import os
import json
import requests
from typing import Optional, List

# API 配置
API_BASE = os.environ.get("API_BASE", "http://172.18.98.97:8000")
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")


class MinMaxLLM:
    """MinMax 大模型客户端"""

    def __init__(self, api_key: str = None, model: str = "MiniMax-M2.7", base_url: str = "https://api.minimax.chat"):
        self.api_key = api_key or MINIMAX_API_KEY
        self.model = model
        self.base_url = base_url
        self.api_version = "v1"

    @property
    def _llm_type(self) -> str:
        return "minimax"

    def _generate(self, messages: list):
        """生成回复，直接返回字典格式"""
        # 转换消息格式（支持字典和对象两种格式）
        chat_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                chat_messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            else:
                content = msg.content if hasattr(msg, 'content') else str(msg)
                msg_type = type(msg).__name__
                if msg_type == "HumanMessage":
                    role = "user"
                elif msg_type == "SystemMessage":
                    role = "system"
                elif msg_type == "AIMessage":
                    role = "assistant"
                else:
                    role = "user"
                chat_messages.append({"role": role, "content": content})

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

            # 返回简单的响应对象
            class SimpleResponse:
                def __init__(self, content):
                    self.content = content
            return SimpleResponse(content=content)

        except Exception as e:
            class ErrorResponse:
                def __init__(self, error):
                    self.content = f"API调用失败: {str(error)}"
            return ErrorResponse(error=e)


# ============ Intent Parser ============

def parse_intent(user_input: str, llm: MinMaxLLM) -> dict:
    """使用 LLM 解析用户意图，返回参数和响应消息"""
    # 构建消息历史
    system_prompt = """你是一个视频转换助手。

请分析用户意图，只返回以下 JSON 格式（不要有任何其他内容）：

参数识别优先级：用户通过UI选择的参数优先于用户文字描述。

方向识别：
- 如果用户说"竖屏"、"转竖屏"、"短视频"、"9:16"、"4:5"、"2:3" -> target_orientation="portrait", orientation_explicit=true
- 如果用户说"横屏"、"转横屏"、"16:9"、"21:9"、"4:3"、"3:2" -> target_orientation="landscape", orientation_explicit=true
- 如果用户没有说方向 -> target_orientation=null, orientation_explicit=false

策略识别：
- 如果用户说"智能裁剪"、"AI裁剪" -> strategy="smart_crop", strategy_explicit=true
- 如果用户说"裁剪"、"切边" -> strategy="crop", strategy_explicit=true
- 如果用户说"填充"、"黑边" -> strategy="pad", strategy_explicit=true
- 如果用户说"拉伸填充"、"拉伸" -> strategy="stretch", strategy_explicit=true
- 如果用户说"镜像滚动"、"镜像" -> strategy="mirror_scroll", strategy_explicit=true
- 如果用户说"平移运镜"、"平移" -> strategy="pan_scroll", strategy_explicit=true
- 如果用户没有说策略 -> strategy=null, strategy_explicit=false

比例识别（返回 float 值）：
- 如果用户说"9:16"、"9/16" -> target_ratio=0.5625, ratio_explicit=true
- 如果用户说"4:5"、"4/5" -> target_ratio=0.8, ratio_explicit=true
- 如果用户说"1:1"、"1/1" -> target_ratio=1.0, ratio_explicit=true
- 如果用户说"2:3"、"2/3" -> target_ratio=0.6667, ratio_explicit=true
- 如果用户说"16:9"、"16/9" -> target_ratio=1.7778, ratio_explicit=true
- 如果用户说"21:9"、"21/9" -> target_ratio=2.3333, ratio_explicit=true
- 如果用户说"4:3"、"4/3" -> target_ratio=1.3333, ratio_explicit=true
- 如果用户说"3:2"、"3/2" -> target_ratio=1.5, ratio_explicit=true
- 如果用户没有说比例，默认竖屏用 9:16 (0.5625)，横屏用 16:9 (1.7778)，ratio_explicit=false

UI选择参数识别：
- 如果用户输入中包含"[用户已选择参数：...]"格式，优先使用其中指定的参数
- "竖屏 9:16" -> target_orientation="portrait", target_ratio=0.5625
- "竖屏 4:5" -> target_orientation="portrait", target_ratio=0.8
- "横屏 16:9" -> target_orientation="landscape", target_ratio=1.7778
- "横屏 21:9" -> target_orientation="landscape", target_ratio=2.3333
- "横屏 4:3" -> target_orientation="landscape", target_ratio=1.3333
- "填充黑边" -> strategy="pad"
- "中心裁剪" -> strategy="crop"
- "智能裁剪" -> strategy="smart_crop"
- "拉伸填充" -> strategy="stretch"
- "镜像滚动" -> strategy="mirror_scroll"
- "平移运镜" -> strategy="pan_scroll"

生成回复：
- 如果缺少参数，必须在回复中说明已使用的默认值，并列出所有可用策略供用户选择
- 例如："我理解了，您想把视频转换为竖屏（默认9:16比例）。请问使用哪种转换策略？支持：1. 智能裁剪 - AI自动裁剪保留主体；2. 中心裁剪 - 直接裁剪可能丢失边缘；3. 填充黑边 - 添加黑边保持所有内容完整。您也可以指定目标比例如9:16、4:5等。4.拉伸填充 - 直接拉伸视频，可能变形。5.镜像滚动 - 适合风景视频，保持内容完整。"
- 如果所有参数都有，回复如："好的，我把视频转换为竖屏（9:16），使用智能裁剪策略。"

JSON格式（必须严格遵守，不要有其他内容）：
{"target_orientation": "portrait/landscape/null", "strategy": "pad/crop/smart_crop/stretch/mirror_scroll/pan_scroll/null", "target_ratio": 0.5625/0.8/1.0/0.6667/1.7778/2.3333/1.3333/1.5/null, "orientation_explicit": true/false, "strategy_explicit": true/false, "ratio_explicit": true/false, "response": "你的回复", "all_params_provided": true/false}"""

    try:
        # 直接使用字典格式的消息
        chat_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]

        result = llm._generate(chat_messages)
        content = result.content if hasattr(result, 'content') else str(result)

        # 提取 JSON
        json_str = None
        for line in content.split('\n'):
            line = line.strip()
            if '{' in line:
                start = line.index('{')
                json_str = line[start:]
            if json_str and '}' in line:
                end = line.index('}') + 1
                json_str = json_str[:end]
                break

        if json_str:
            parsed = json.loads(json_str)
            return {
                "target_orientation": parsed.get("target_orientation"),
                "strategy": parsed.get("strategy"),
                "target_ratio": parsed.get("target_ratio"),
                "orientation_explicit": parsed.get("orientation_explicit", False),
                "strategy_explicit": parsed.get("strategy_explicit", False),
                "ratio_explicit": parsed.get("ratio_explicit", False),
                "response": parsed.get("response", ""),
                "all_params_provided": parsed.get("orientation_explicit", False) and parsed.get("strategy_explicit", False)
            }

        # JSON 解析失败，返回原始内容作为响应
        return {
            "target_orientation": None,
            "strategy": None,
            "target_ratio": None,
            "orientation_explicit": False,
            "strategy_explicit": False,
            "ratio_explicit": False,
            "response": content if content else "无法解析响应",
            "all_params_provided": False
        }

    except Exception as e:
        return {
            "target_orientation": None,
            "strategy": None,
            "target_ratio": None,
            "orientation_explicit": False,
            "strategy_explicit": False,
            "ratio_explicit": False,
            "response": f"抱歉，解析出错：{str(e)}",
            "all_params_provided": False
        }


# ============ 便捷函数 ============

def create_llm(api_key: str = None) -> MinMaxLLM:
    """创建 LLM 实例"""
    return MinMaxLLM(api_key=api_key)


def chat(message: str, file_path: str = None, api_key: str = None) -> str:
    """便捷对话函数"""
    llm = create_llm(api_key=api_key)
    result = parse_intent(message, llm)
    return result.get("response", "")
