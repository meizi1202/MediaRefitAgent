"""
LangChain Agent - 基于 MinMax LLM 的意图解析
"""
import os
import json
from typing import Optional

# API配置
API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"
MODEL_NAME = "MiniMax-M2.7"

# 全局变量控制
LLM_INTENT_AVAILABLE = True


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


class SimpleResponse:
    """简单响应对象"""

    def __init__(self, content: str = ""):
        self.content = content


def parse_intent(user_input: str, llm: MinMaxLLM) -> dict:
    """使用 LLM 解析用户意图，返回参数和响应消息"""
    # 构建消息历史
    system_prompt = """你是一个视频处理助手，有两个主要工具：

【工具1：视频横竖屏转换 transform】
- 功能：转换视频的方向（横屏↔竖屏）和比例
- 参数：目标方向(target_orientation)、转换策略(strategy)
- 方向：portrait(竖屏)、landscape(横屏)
- 策略：pad(填充黑边)、crop(中心裁剪)、smart_crop(智能裁剪)、stretch(拉伸填充)、mirror_scroll(镜像滚动)、pan_scroll(平移运镜)

【工具2：视频压缩 compress】
- 功能：压缩视频文件大小
- 参数：compression_level
- 级别：low(低压缩高质量)、medium(中压缩平衡)、high(高压缩小体积)

分析用户意图步骤：

第一步：识别工具名称
- 如果用户说"转换"、"转成"、"转竖屏"、"转横屏"、"横竖屏" -> target_feature="convert"
- 如果用户说"压缩"、"压一下"、"变小"、"文件太大" -> target_feature="compress"
- 如果无法判断 -> target_feature=null

第二步：根据工具识别对应参数
- transform需要：orientation_explicit、strategy_explicit
- compress需要：compression_explicit

第三步：生成回复
- 如果target_feature=null："抱歉，我没有理解您的需求。您是想转换视频方向还是压缩视频？"
- 如果target_feature=transform但参数不全："好的，您想转换视频方向。请问目标方向是竖屏还是横屏？使用什么转换策略？"
- 如果target_feature=compress但参数不全："好的，您想压缩视频。请问要什么压缩级别？低压缩保留较高质量，中压缩质量和体积平衡，高压缩体积最小。"
- 如果所有参数完整：
  - transform："好的，我把视频转换为{target_orientation}，使用{strategy}策略。"
  - compress："好的，我用{compression_level}级别压缩视频。"

UI选择参数优先：如果用户输入中包含"[用户已选择参数：...]"格式，优先解析其中的参数

JSON格式（必须严格遵守）：
{"target_feature": "transform/compress/null", "target_orientation": "portrait/landscape/null", "strategy": "pad/crop/smart_crop/stretch/mirror_scroll/pan_scroll/null", "compression_level": "low/medium/high/null", "orientation_explicit": true/false, "strategy_explicit": true/false, "compression_explicit": true/false, "response": "你的回复", "all_params_provided": true/false}"""

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
            target_feature = parsed.get("target_feature", "transform")
            compression_level = parsed.get("compression_level")
            compression_explicit = parsed.get("compression_explicit", False)

            # 判断all_params_provided
            if target_feature == "compress":
                all_params_provided = compression_explicit and bool(compression_level)
            elif target_feature == "transform":
                all_params_provided = parsed.get("orientation_explicit", False) and parsed.get("strategy_explicit", False)
            else:
                all_params_provided = False

            return {
                "target_feature": target_feature,
                "target_orientation": parsed.get("target_orientation"),
                "strategy": parsed.get("strategy"),
                "compression_level": compression_level,
                "orientation_explicit": parsed.get("orientation_explicit", False),
                "strategy_explicit": parsed.get("strategy_explicit", False),
                "compression_explicit": compression_explicit,
                "response": parsed.get("response", ""),
                "all_params_provided": all_params_provided
            }

        # JSON 解析失败，返回原始内容作为响应
        return {
            "target_feature": None,
            "target_orientation": None,
            "strategy": None,
            "compression_level": None,
            "orientation_explicit": False,
            "strategy_explicit": False,
            "compression_explicit": False,
            "response": content if content else "无法解析响应",
            "all_params_provided": False
        }

    except Exception as e:
        return {
            "target_feature": None,
            "target_orientation": None,
            "strategy": None,
            "compression_level": None,
            "orientation_explicit": False,
            "strategy_explicit": False,
            "compression_explicit": False,
            "response": f"解析出错：{str(e)}",
            "all_params_provided": False
        }


class VideoTransformAgent:
    """视频转换 Agent（用于直接调用，不通过LangGraph）"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.llm = MinMaxLLM(api_key=self.api_key)

    def chat_with_ai_response(self, user_input: str, file_path: str = None) -> dict:
        """聊天并返回AI响应"""
        parsed = parse_intent(user_input, self.llm)

        result = {
            "success": True,
            "message": parsed.get("response", ""),
            "parsed_params": {
                "target_feature": parsed.get("target_feature"),
                "target_orientation": parsed.get("target_orientation"),
                "strategy": parsed.get("strategy"),
                "compression_level": parsed.get("compression_level"),
                "all_params_provided": parsed.get("all_params_provided"),
            }
        }

        return result


# 简单的 chat 函数
def chat(message: str, api_key: str = "") -> dict:
    """简单的聊天接口"""
    agent = VideoTransformAgent(api_key=api_key)
    return agent.chat_with_ai_response(message)
