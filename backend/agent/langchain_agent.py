"""
LangChain Agent - 基于 MinMax LLM 的意图解析

文件结构：
- memory/: 会话历史存储
- llm/: LLM provider
- prompts.py: 提示词模板
- langchain_agent.py: 意图解析逻辑
"""
import json
import os
import re
from typing import Optional

from agent.llm import MinMaxLLM, SimpleResponse
from agent import prompts

LLM_INTENT_AVAILABLE = True


def _build_history_context(history: list) -> str:
    """构建历史上下文"""
    if not history:
        return ""
    context = "\n\n【对话历史】\n"
    for msg in history[-20:]:
        role = "用户" if msg["role"] == "user" else "助手"
        content = msg["content"][:200] + "..." if len(msg.get("content", "")) > 200 else msg.get("content", "")
        context += f"{role}：{content}\n"
    return context


def _build_video_info_text(video_info: dict) -> str:
    """构建视频信息文本"""
    if not video_info or not video_info.get("success"):
        return ""
    return f"\n\n当前视频信息：{video_info['message']}"


def _extract_json(content: str) -> dict:
    """从 LLM 输出中提取 JSON"""
    # 方法1：正则提取 JSON 对象
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
    if json_match:
        json_str = json_match.group()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                fixed_json = json_str.replace("'", '"')
                return json.loads(fixed_json)
            except json.JSONDecodeError:
                pass

    # 方法2：提取 response 字段
    response_match = re.search(r'"response"\s*:\s*"([^"]*)"', content)
    if response_match:
        return {"response": response_match.group(1)}

    # 方法3：降级 - 从原始内容中提取关键字段
    result = {}

    # 提取 orientation
    if 'portrait' in content.lower() or '竖屏' in content:
        result['target_orientation'] = 'portrait'
        result['orientation_explicit'] = True
    elif 'landscape' in content.lower() or '横屏' in content:
        result['target_orientation'] = 'landscape'
        result['orientation_explicit'] = True

    # 提取 ratio
    ratio_match = re.search(r'(9:16|4:5|1:1|16:9|21:9|4:3)', content)
    if ratio_match:
        result['target_ratio'] = ratio_match.group(1)
        result['ratio_explicit'] = True

    # 提取 strategy
    if 'pad' in content.lower() or '填充黑边' in content:
        result['strategy'] = 'pad'
        result['strategy_explicit'] = True
    elif 'crop' in content.lower() or '中心裁剪' in content:
        result['strategy'] = 'crop'
        result['strategy_explicit'] = True
    elif 'smart_crop' in content.lower() or 'ai裁剪' in content.lower():
        result['strategy'] = 'smart_crop'
        result['strategy_explicit'] = True
    elif 'stretch' in content.lower() or '拉伸' in content:
        result['strategy'] = 'stretch'
        result['strategy_explicit'] = True

    # 提取 response（尽可能完整）
    if result:
        result['response'] = content.strip()

    return result


def parse_intent(user_input: str, llm: MinMaxLLM, video_info: dict = None, history: list = None) -> dict:
    """使用 LLM 解析用户意图：先识别工具，再解析参数"""
    print(f"[DEBUG parse_intent] called with user_input: {user_input}, history length: {len(history or [])}")

    # 构建上下文
    history_context = _build_history_context(history or [])
    video_info_text = _build_video_info_text(video_info)

    # ===== 第一步：识别工具 =====
    tool_prompt = prompts.TOOL_RECOGNITION_PROMPT.format(
        history_context=history_context or "【无对话历史】",
        user_input=user_input
    )
    print(f"[DEBUG TOOL] tool_prompt:\n{tool_prompt[:800]}")
    tool_result = llm._generate([{"role": "user", "content": tool_prompt}])
    print(f"[DEBUG TOOL] tool_result: {tool_result.content}")
    target_feature = tool_result.content.strip().lower() if tool_result.content else "null"

    # ===== 第二步：根据工具解析参数 =====
    if target_feature not in prompts.TOOL_PROMPTS:
        return {
            "target_feature": None,
            "response": prompts.NULL_RESPONSE,
            "all_params_provided": False,
        }

    # 获取对应工具的提示词模板
    template = prompts.TOOL_PROMPTS[target_feature]

    # 填充模板
    param_prompt = template.format(
        history_context=history_context or "【无对话历史】",
        video_info=video_info_text or "【无视频信息】",
        user_input=user_input,
    )

    # 调用 LLM
    param_result = llm._generate([{"role": "user", "content": param_prompt}])
    param_content = param_result.content or ""

    # 调试日志
    print(f"[DEBUG] param_prompt:\n{param_prompt[:500]}...")
    print(f"[DEBUG] param_content:\n{param_content[:500]}")

    # 解析 JSON
    parsed = _extract_json(param_content)
    print(f"[DEBUG] parsed: {parsed}")

    # 判断 all_params_provided
    all_params_provided = _check_params_provided(target_feature, parsed)

    return _build_response(target_feature, parsed, all_params_provided)


def _check_params_provided(target_feature: str, parsed: dict) -> bool:
    """检查参数是否完整"""
    check_map = {
        "compress": parsed.get("compression_explicit") and parsed.get("compression_level"),
        "convert": parsed.get("orientation_explicit") and parsed.get("strategy_explicit"),
        "info": True,
        "trim": parsed.get("start_time_explicit") and parsed.get("end_time_explicit"),
        "concat": parsed.get("concat_explicit"),
        "restore": parsed.get("preset_explicit"),
        "highlight": True,
        "transition": True,
    }
    return check_map.get(target_feature, False)


def _build_response(target_feature: str, parsed: dict, all_params_provided: bool) -> dict:
    """构建标准响应结构"""
    base_fields = {
        "target_feature": target_feature,
        "all_params_provided": all_params_provided,
        "response": parsed.get("response", ""),
    }

    # 通用字段
    fields = {
        "target_orientation": parsed.get("target_orientation"),
        "strategy": parsed.get("strategy"),
        "compression_level": parsed.get("compression_level"),
        "start_time": parsed.get("start_time"),
        "end_time": parsed.get("end_time"),
        "keep_audio": parsed.get("keep_audio", True),
        "concat_explicit": parsed.get("concat_explicit", False),
        "file_count": parsed.get("file_count", 0),
        "orientation_explicit": parsed.get("orientation_explicit", False),
        "strategy_explicit": parsed.get("strategy_explicit", False),
        "compression_explicit": parsed.get("compression_explicit", False),
        "start_time_explicit": parsed.get("start_time_explicit", False),
        "end_time_explicit": parsed.get("end_time_explicit", False),
    }

    # restore 专用字段
    if target_feature == "restore":
        fields.update({
            "restoration_preset": parsed.get("preset"),
            "restoration_options": {
                "denoise": parsed.get("denoise", False),
                "scratch": parsed.get("scratch", False),
                "flicker": parsed.get("flicker", False),
                "interpolate": parsed.get("interpolate", False),
                "super_resolution": parsed.get("super_resolution", False),
            },
            "restoration_preset_explicit": parsed.get("preset_explicit", False),
        })

    # highlight 专用字段
    if target_feature == "highlight":
        fields.update({
            "target_duration": parsed.get("target_duration", 60),
            "target_duration_explicit": parsed.get("target_duration_explicit", False),
            "num_clips": parsed.get("num_clips", 5),
            "num_clips_explicit": parsed.get("num_clips_explicit", False),
        })

    # transition 专用字段
    if target_feature == "transition":
        fields.update({
            "transition_type": parsed.get("transition_type", "fade"),
            "transition_type_explicit": parsed.get("transition_type_explicit", False),
            "transition_duration": parsed.get("transition_duration", 1.0),
            "transition_duration_explicit": parsed.get("transition_duration_explicit", False),
        })

    return {**base_fields, **fields}


# ============ 辅助函数 ============

def get_video_info(file_path: str) -> dict:
    """获取视频信息"""
    try:
        from video.processor import get_video_metadata
        size_bytes = os.path.getsize(file_path)
        metadata = get_video_metadata(file_path)
        return {
            "success": True,
            "width": metadata.width,
            "height": metadata.height,
            "duration": metadata.duration,
            "fps": metadata.fps,
            "codec": metadata.codec,
            "bitrate": metadata.bitrate,
            "size_mb": round(size_bytes / 1024 / 1024, 2),
            "message": f"视频信息：分辨率 {metadata.width}x{metadata.height}，时长 {metadata.duration:.1f}秒，文件大小 {size_bytes/1024/1024:.2f}MB"
        }
    except Exception as e:
        return {"success": False, "message": f"获取视频信息失败：{str(e)}"}


def trim_video_file(file_path: str, output_dir: str, start_time: float, end_time: float) -> dict:
    """修剪视频"""
    try:
        from video.processor import trim_video
        filename = os.path.basename(file_path)
        output_path = os.path.join(output_dir, f"trimmed_{filename}")
        trim_video(file_path, output_path, start_time, end_time)
        output_size = os.path.getsize(output_path)
        return {
            "success": True,
            "output_path": output_path,
            "original_duration": end_time - start_time,
            "trimmed_duration": end_time - start_time,
            "start_time": start_time,
            "end_time": end_time,
            "output_size_mb": round(output_size / 1024 / 1024, 2),
            "message": f"修剪完成！从 {start_time}秒 到 {end_time}秒，输出文件 {output_size/1024/1024:.2f}MB"
        }
    except Exception as e:
        return {"success": False, "message": f"修剪视频失败：{str(e)}"}


# ============ Agent 类 ============

class VideoTransformAgent:
    """视频转换 Agent（用于直接调用，不通过LangGraph）"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.llm = MinMaxLLM(api_key=self.api_key)

    def chat_with_ai_response(self, user_input: str, file_path: str = None) -> dict:
        """聊天并返回AI响应"""
        parsed = parse_intent(user_input, self.llm)
        return {
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


def chat(message: str, api_key: str = "") -> dict:
    """简单的聊天接口"""
    agent = VideoTransformAgent(api_key=api_key)
    return agent.chat_with_ai_response(message)
