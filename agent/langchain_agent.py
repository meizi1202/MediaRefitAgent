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


# ============ LangChain Memory 集成 ============
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


def get_video_info(file_path: str) -> dict:
    """获取视频信息"""
    try:
        from video.processor import get_video_metadata
        metadata = get_video_metadata(file_path)
        size_bytes = os.path.getsize(file_path)
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
        return {
            "success": False,
            "message": f"获取视频信息失败：{str(e)}"
        }


def trim_video_file(file_path: str, output_dir: str, start_time: float, end_time: float) -> dict:
    """修剪视频"""
    try:
        from video.processor import trim_video
        import os
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
        return {
            "success": False,
            "message": f"修剪视频失败：{str(e)}"
        }


def parse_intent(user_input: str, llm: MinMaxLLM, video_info: dict = None, history: list = None) -> dict:
    """使用 LLM 解析用户意图，两级结构：先识别工具，再解析参数"""

    # 构建历史上下文
    history_context = ""
    if history and len(history) > 0:
        history_context = "\n\n【对话历史】（请结合历史理解用户意图）\n"
        for msg in history[-20:]:  # 最近20条
            role = "用户" if msg["role"] == "user" else "助手"
            # 截断过长的内容
            content = msg["content"][:200] + "..." if len(msg.get("content", "")) > 200 else msg.get("content", "")
            history_context += f"{role}：{content}\n"
        history_context += "【当前输入】\n"

    # ===== 第一步：识别工具 =====
    tool_prompt = f"""{history_context}用户输入：{user_input}

请识别用户想要使用的工具：
- 如果用户说"转换"、"转成"、"转竖屏"、"转横屏"、"横竖屏" -> 返回 "convert"
- 如果用户说"压缩"、"压一下"、"变小"、"文件太大" -> 返回 "compress"
- 如果用户说"视频信息"、"查看视频"、"这个视频多大"、"时长" -> 返回 "info"
- 如果用户说"修剪"、"裁剪"、"截取"、"剪掉"、"切割" -> 返回 "trim"
- 如果用户说"拼接"、"合并"、"连接"、"concat"、"merge" -> 返回 "concat"
- 如果用户说"修复"、"老视频"、"老电影"、"去噪"、"去闪烁"、"划痕"、"补帧"、"超分" -> 返回 "restore"
- 如果用户说"精彩片段"、"高光时刻"、"提取片段"、"精华"、"highlight" -> 返回 "highlight"
- 如果用户说"转场"、"过渡效果"、"添加转场" -> 返回 "transition"
- 如果无法判断 -> 返回 "null"

只返回一个词：convert / compress / info / trim / concat / restore / highlight / transition / null"""

    tool_messages = [{"role": "user", "content": tool_prompt}]
    tool_result = llm._generate(tool_messages)
    target_feature = tool_result.content.strip().lower() if hasattr(tool_result, 'content') else "null"

    # ===== 第二步：根据工具使用专用提示词解析参数 =====
    video_info_text = f"\n\n当前视频信息：{video_info['message']}" if video_info and video_info.get("success") else ""

    if target_feature == "convert":
        # JSON字段：xxx_explicit=true表示用户明确指定了对应参数，false/null表示未指定
        json_example = '''{{"orientation_explicit": true/false, "strategy_explicit": true/false, "ratio_explicit": true/false, "target_orientation": "portrait/landscape/null", "target_ratio": "9:16/4:5/1:1/16:9/21:9/4:3/null", "strategy": "pad/crop/smart_crop/stretch/mirror_scroll/pan_scroll/null", "response": "助手回复"}}'''
        param_prompt = f"""【任务】解析用户视频转换需求

【重要】你必须返回JSON格式，不要返回Markdown或其他格式！

【视频信息】
{video_info_text}

【对话历史】（重要！请结合历史理解用户意图）
{history_context}

【当前输入】
{user_input}

---

【参数说明】
方向：portrait=竖屏，landscape=横屏
比例：
- 竖屏：9:16（短视频标准）、4:5（Instagram）、1:1（正方形）
- 横屏：16:9（标准）、21:9（电影）、4:3（电视）
策略：
- pad=填充黑边（保持所有内容完整，推荐）
- crop=中心裁剪（可能丢失边缘内容）
- smart_crop=智能裁剪（AI保留主体，需YOLO）
- stretch=拉伸填充（会变形）
- mirror_scroll=镜像滚动
- pan_scroll=平移运镜

【解析规则】
1. 查看对话历史，如果助手之前问了某参数（如"选择比例"），用户现在回答了，则：
   - explicit=true
   - 字段值=用户回答的具体值（如"9:16"）
2. 如果用户没有回答某问题，则：
   - explicit=false
   - 字段值=null

【输出格式】
必须返回以下JSON结构，不要返回其他内容：
{json_example}

【示例响应】
{{"orientation_explicit": true, "strategy_explicit": false, "ratio_explicit": false, "target_orientation": "portrait", "target_ratio": null, "strategy": null, "response": "已识别到您想转换为竖屏。请问选择哪个比例？9:16/4:5/1:1"}}
  示例"已识别到您想转换为竖屏。请问选择哪个比例？9:16/4:5/1:1" """

    elif target_feature == "compress":
        json_example = '{{"compression_explicit": true/false, "compression_level": "low/medium/high/null", "response": "助手回复"}}'
        param_prompt = f"""用户想要压缩视频。

{video_info_text}
{history_context}

请解析参数，JSON格式：
{json_example}

【重要】用户的输入可能是在回答上一轮的问题，结合历史上下文理解。

级别：low=低压缩（高质量，文件较大），medium=中压缩（质量和体积平衡），high=高压缩（小体积，质量较低）

如果参数完整，response示例："好的，我用中压缩级别压缩视频。"
如果参数不完整，response示例格式：
1. 先说明已提取到的参数（如有）
2. 再说明缺少哪些参数及可选值et
示例："请问要什么压缩级别？低压缩保留较高质量但文件较大，中压缩质量和体积平衡，高压缩体积最小但质量较低。请选择级别。" """

    elif target_feature == "info":
        param_prompt = f"""用户想要获取视频信息。

{video_info_text}
{history_context}

用户输入：{user_input}

请解析参数，JSON格式：
{{"response": "助手回复"}}

response示例："好的，我来查看视频信息。" """

    elif target_feature == "trim":
        json_example = '{{"start_time_explicit": true/false, "end_time_explicit": true/false, "start_time": "数字或时间格式/null", "end_time": "数字或时间格式/null", "response": "助手回复"}}'
        param_prompt = f"""用户想要修剪视频。

{video_info_text}
{history_context}

【重要】用户的输入可能是在回答上一轮的问题，结合历史上下文理解。

用户输入：{user_input}

请解析参数，JSON格式：
{json_example}

时间格式：支持 "30" (秒) 或 "0:30" (分:秒) 或 "1:30:00" (时:分:秒)

如果参数完整，response示例："好的，我从第10秒修剪到第20秒。"
如果参数不完整，response示例格式：
1. 先说明已提取到的时间参数（如有）
2. 再说明缺少哪些参数
示例："已识别到您想从第10秒开始修剪。还需要指定结束时间（可以是秒数如30，或时间格式如0:30表示30秒）。请问结束时间是？" """

    elif target_feature == "concat":
        json_example = '{{"concat_explicit": true/false, "file_count": 数字, "keep_audio": true/false, "response": "助手回复"}}'
        param_prompt = f"""用户想要拼接多个视频。

{video_info_text}
{history_context}

【重要】用户的输入可能是在回答上一轮的问题，结合历史上下文理解。

用户输入：{user_input}

请解析参数，JSON格式：
{json_example}

注意：拼接至少需要2个视频文件。可以通过用户上传的文件来确定视频数量。

如果参数完整（至少2个视频），response示例："好的，我将拼接这3个视频。"
如果参数不完整，response示例格式：
1. 说明已识别到的信息
2. 询问还需要什么
示例："已识别到您想拼接视频。请上传至少2个视频文件，我会按选择顺序拼接。" """

    elif target_feature == "restore":
        json_example = '{{"preset_explicit": true/false, "preset": "basic/film/enhanced/custom/null", "denoise": true/false, "scratch": true/false, "flicker": true/false, "interpolate": true/false, "super_resolution": true/false, "response": "助手回复"}}'
        param_prompt = f"""【任务】解析用户老视频修复需求

【重要】你必须返回JSON格式，不要返回Markdown或其他格式！

【视频信息】
{video_info_text}

【对话历史】（重要！请结合历史理解用户意图）
{history_context}

【当前输入】
{user_input}

---

【套餐类型】
- basic：基础修复（去噪、去抖动、色彩校正、对比度增强）
- film：胶片修复（基础修复 + 划痕去除、闪烁修复）
- enhanced：增强版（胶片修复 + 补帧、超分辨率）
- custom：自定义（用户指定具体修复项）

【修复选项】
- denoise：去噪（去除画面噪点）
- scratch：划痕修复（去除老胶片划痕）
- flicker：闪烁修复（减少画面闪烁）
- interpolate：补帧（提升流畅度）
- super_resolution：超分辨率（提升清晰度）

【解析规则】
1. 查看对话历史，如果用户之前回答了某参数选择，则explicit=true
2. 如果用户没有回答某问题，则explicit=false，字段值=null
3. 如果用户只说"修复"、"老视频"、"老电影"，默认选择 film 套餐
4. 如果用户明确提到"去噪"、"去划痕"、"补帧"等，则设置对应选项=true

【输出格式】
必须返回以下JSON结构，不要返回其他内容：
{json_example}

【示例响应】
{{"preset_explicit": true, "preset": "film", "denoise": false, "scratch": true, "flicker": true, "interpolate": false, "super_resolution": false, "response": "已识别到您想修复老电影，使用胶片修复套餐去除划痕和闪烁。"}}
  示例"已识别到您想修复老电影，请问选择哪个套餐？基础修复/胶片修复/增强版" """

    elif target_feature == "highlight":
        json_example = '{{"target_duration_explicit": true/false, "target_duration": 60, "num_clips_explicit": true/false, "num_clips": 5, "response": "助手回复"}}'
        param_prompt = f"""【任务】解析用户精彩片段提取需求

【重要】你必须返回JSON格式，不要返回Markdown或其他格式！

【视频信息】
{video_info_text}

【对话历史】（重要！请结合历史理解用户意图）
{history_context}

【当前输入】
{user_input}

---

【参数说明】
- target_duration: 目标时长（秒），如 60 表示一分钟精彩集锦，默认60
- num_clips: 片段数量，默认5个

【解析规则】
1. 如果用户提到具体时长（如"60秒"、"1分钟"、"90秒"），则 explicit=true
2. 如果用户提到片段数量（如"5个"、"10个"），则 explicit=true
3. 如果用户没有指定，则使用默认值

【输出格式】
必须返回以下JSON结构，不要返回其他内容：
{json_example}

【示例响应】
{{"target_duration_explicit": true, "target_duration": 60, "num_clips_explicit": false, "num_clips": 5, "response": "好的，我提取这场演唱会的精彩片段，总时长60秒。"}}
  或示例"已识别到您想提取精彩片段，请问需要多长时间的？（默认60秒）" """

    elif target_feature == "transition":
        json_example = '{{"transition_type_explicit": true/false, "transition_type": "fade/slide/zoom/blur/rotate/dissolve/null", "transition_duration_explicit": true/false, "transition_duration": 1.0, "response": "助手回复"}}'
        param_prompt = f"""【任务】解析用户添加转场效果需求

【重要】你必须返回JSON格式，不要返回Markdown或其他格式！

【视频信息】
{video_info_text}

【对话历史】（重要！请结合历史理解用户意图）
{history_context}

【当前输入】
{user_input}

---

【转场类型】
- fade: 淡入淡出，适合情绪过渡、场景转换
- slide: 滑动，适合平行叙事、对比
- zoom: 缩放，适合强调主体、节奏变化
- blur: 模糊，适合焦点转换
- rotate: 旋转，适合场景切换
- dissolve: 溶解，适合柔和过渡

【参数说明】
- transition_type: 转场类型，如果用户没有指定则默认 fade
- transition_duration: 转场时长（秒），默认1.0秒

【解析规则】
1. 如果用户提到具体转场类型（如"淡入淡出"、"滑动"），则 explicit=true
2. 如果用户提到时长（如"2秒"、"1秒"），则 explicit=true

【输出格式】
必须返回以下JSON结构，不要返回其他内容：
{json_example}

【示例响应】
{{"transition_type_explicit": true, "transition_type": "fade", "transition_duration_explicit": false, "transition_duration": 1.0, "response": "好的，我为视频添加淡入淡出转场效果。"}}
  或示例"已识别到您想添加转场，请问要什么类型？淡入淡出/滑动/缩放" """

    else:
        return {
            "target_feature": None,
            "target_orientation": None,
            "strategy": None,
            "compression_level": None,
            "start_time": None,
            "end_time": None,
            "orientation_explicit": False,
            "strategy_explicit": False,
            "compression_explicit": False,
            "start_time_explicit": False,
            "end_time_explicit": False,
            "response": "抱歉，我没有理解您的需求。您是想转换视频方向、压缩视频、修剪视频还是获取视频信息？",
            "all_params_provided": False
        }

    try:
        param_messages = [{"role": "user", "content": param_prompt}]
        param_result = llm._generate(param_messages)
        param_content = param_result.content if hasattr(param_result, 'content') else ""

        # 调试日志
        print(f"[DEBUG parse_intent] param_content:\n{param_content[:1000]}")

        # 提取 JSON
        import re
        parsed = {}
        llm_response = ""

        # 方法1：正则提取 JSON 对象
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', param_content, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                # 容错：尝试将单引号替换为双引号
                try:
                    fixed_json = json_str.replace("'", '"')
                    parsed = json.loads(fixed_json)
                except json.JSONDecodeError:
                    parsed = {}

        # 方法2：如果 JSON 解析失败，尝试直接提取 response 字段
        if not parsed:
            response_match = re.search(r'"response"\s*:\s*"([^"]*)"', param_content)
            if response_match:
                llm_response = response_match.group(1)
            else:
                # 尝试从文本中提取最后一个 "之后的内容 作为响应
                lines = param_content.strip().split('\n')
                for line in reversed(lines):
                    line = line.strip()
                    if line and not line.startswith('{') and not line.startswith('}'):
                        # 排除 JSON 相关行
                        if '"response"' not in line and '"target_' not in line and '"strategy' not in line:
                            llm_response = line.strip('",。：:「」''""')
                            if llm_response:
                                break

        # 判断 all_params_provided
        if target_feature == "compress":
            all_params_provided = parsed.get("compression_explicit", False) and bool(parsed.get("compression_level"))
        elif target_feature == "convert":
            # 转换需要方向、策略；比例可选
            all_params_provided = parsed.get("orientation_explicit", False) and parsed.get("strategy_explicit", False)
        elif target_feature == "info":
            all_params_provided = True
        elif target_feature == "trim":
            all_params_provided = parsed.get("start_time_explicit", False) and parsed.get("end_time_explicit", False)
        elif target_feature == "concat":
            # 拼接需要至少2个视频（file_count >= 2），由后端根据实际上传文件数量判断
            # LLM 只负责识别意图，file_count 由后端判断
            all_params_provided = parsed.get("concat_explicit", False)
        elif target_feature == "restore":
            # 修复只需要 preset_explicit=True 即可
            all_params_provided = parsed.get("preset_explicit", False)
        elif target_feature == "highlight":
            # 精彩片段：参数可选，有默认值
            all_params_provided = True
        elif target_feature == "transition":
            # 转场：参数可选，有默认值
            all_params_provided = True
        else:
            all_params_provided = False

        return {
            "target_feature": target_feature,
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
            # restore 相关字段
            "restoration_preset": parsed.get("preset"),
            "restoration_options": {
                "denoise": parsed.get("denoise", False),
                "scratch": parsed.get("scratch", False),
                "flicker": parsed.get("flicker", False),
                "interpolate": parsed.get("interpolate", False),
                "super_resolution": parsed.get("super_resolution", False),
            },
            "restoration_preset_explicit": parsed.get("preset_explicit", False),
            # highlight 相关字段
            "target_duration": parsed.get("target_duration", 60),
            "target_duration_explicit": parsed.get("target_duration_explicit", False),
            "num_clips": parsed.get("num_clips", 5),
            "num_clips_explicit": parsed.get("num_clips_explicit", False),
            # transition 相关字段
            "transition_type": parsed.get("transition_type", "fade"),
            "transition_type_explicit": parsed.get("transition_type_explicit", False),
            "transition_duration": parsed.get("transition_duration", 1.0),
            "transition_duration_explicit": parsed.get("transition_duration_explicit", False),
            "response": parsed.get("response", ""),
            "all_params_provided": all_params_provided
        }

    except Exception as e:
        import traceback
        print(f"[DEBUG parse_intent] Exception: {e}")
        print(f"[DEBUG parse_intent] Traceback:\n{traceback.format_exc()}")
        return {
            "target_feature": target_feature,
            "target_orientation": None,
            "strategy": None,
            "compression_level": None,
            "start_time": None,
            "end_time": None,
            "keep_audio": True,
            "concat_explicit": False,
            "file_count": 0,
            "orientation_explicit": False,
            "strategy_explicit": False,
            "compression_explicit": False,
            "start_time_explicit": False,
            "end_time_explicit": False,
            "restoration_preset": None,
            "restoration_options": {},
            "restoration_preset_explicit": False,
            # highlight 相关字段
            "target_duration": 60,
            "target_duration_explicit": False,
            "num_clips": 5,
            "num_clips_explicit": False,
            # transition 相关字段
            "transition_type": "fade",
            "transition_type_explicit": False,
            "transition_duration": 1.0,
            "transition_duration_explicit": False,
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
