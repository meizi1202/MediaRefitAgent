"""
视频转换 Agent - 基于 LangGraph

状态机设计：
analyze_intent → detect_video → select_strategy → execute_transform → confirm_complete

支持多轮对话，可以记忆上下文
"""
from typing import Optional, Literal, TypedDict, Annotated
from dataclasses import dataclass, field
from datetime import datetime
import shutil
import tempfile
from pathlib import Path
import json
import os

# 会话目录
SESSIONS_DIR = Path.home() / ".mediarefit" / "sessions"

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

# LangChain Memory imports
try:
    from langchain_core.messages import HumanMessage
except ImportError:
    HumanMessage = None

from video.transformer import transform, TransformRequest, TransformResult
from ml.orientation_detector import detect_orientation, OrientationResult

# LLM-based intent parsing - checked at runtime to allow API key from request
LLM_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
llm_parse_intent = None

# Lazy import for LLM parsing
def _get_llm_parse_intent():
    global llm_parse_intent
    if llm_parse_intent is None:
        api_key = os.environ.get("MINIMAX_API_KEY", "")
        if api_key:
            try:
                from agent.langchain_agent import parse_intent as llm_parse_intent_impl
                llm_parse_intent = llm_parse_intent_impl
            except ImportError:
                llm_parse_intent = None
    return llm_parse_intent


# ============ State Definition ============

class ConversationMessage(TypedDict):
    """对话消息"""
    role: str  # user / assistant / system
    content: str
    timestamp: str


class VideoAgentState(TypedDict):
    """Agent 状态"""
    # 用户输入
    user_input: str
    # 视频信息
    video_path: Optional[str]
    temp_video_path: Optional[str]
    video_files: Optional[list[str]]  # 多文件路径列表（用于拼接）
    original_orientation: Optional[str]
    # 转换参数
    target_orientation: Optional[str]
    strategy: Optional[str]
    target_ratio: float
    # 参数是否明确指定
    orientation_explicit: bool
    strategy_explicit: bool
    ratio_explicit: bool
    all_params_provided: bool
    # 处理状态
    current_step: str
    messages: list[ConversationMessage]
    transform_result: Optional[TransformResult]
    error: Optional[str]
    # 多轮对话支持
    session_id: Optional[str]
    history: list[ConversationMessage]
    pending_question: Optional[str]  # 等待用户回答的问题


# ============ Intent Parser ============

class IntentParser:
    """意图解析器"""

    # 方向关键词
    ORIENTATION_KEYWORDS = {
        "portrait": ["竖屏", "portrait", "垂直", "竖", "9:16", "9/16", "4:5", "4/5", "1:1", "1/1", "2:3", "2/3", "短视频", "抖音", "快手", "Instagram", "IG"],
        "landscape": ["横屏", "landscape", "水平", "横", "16:9", "16/9", "21:9", "21/9", "4:3", "4/3", "3:2", "3/2", "横版", "电影"],
    }

    # 策略关键词
    STRATEGY_KEYWORDS = {
        "smart_crop": ["智能裁剪", "smart", "AI裁剪", "ai crop", "智能", "AI"],
        "crop": ["裁剪", "crop", "切", "截"],
        "pad": ["填充", "pad", "黑边", "留边", "保持完整"],
        "rotate": ["旋转", "rotate", "旋转90度", "rotate90"],
    }

    @classmethod
    def parse_orientation(cls, text: str) -> tuple[Optional[str], bool]:
        """解析目标方向，返回 (方向, 是否明确指定)"""
        text_lower = text.lower()
        for orientation, keywords in cls.ORIENTATION_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return orientation, True
        return None, False

    @classmethod
    def parse_strategy(cls, text: str) -> tuple[Optional[str], bool]:
        """解析转换策略，返回 (策略, 是否明确指定)"""
        text_lower = text.lower()
        for strategy, keywords in cls.STRATEGY_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return strategy, True
        return None, False  # 不再默认返回 "pad"

    @classmethod
    def parse_ratio(cls, text: str) -> tuple[Optional[float], bool]:
        """解析比例参数，返回 (比例, 是否明确指定)"""
        # 支持 9:16, 9/16, 16:9, 16/9 等格式
        import re
        patterns = [
            r'(\d+):(\d+)',
            r'(\d+)/(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                w, h = int(match.group(1)), int(match.group(2))
                if h > 0:
                    return w / h, True
        return None, False

    @classmethod
    def parse(cls, text: str) -> dict:
        """解析用户输入"""
        orientation, orientation_explicit = cls.parse_orientation(text)
        strategy, strategy_explicit = cls.parse_strategy(text)
        ratio, ratio_explicit = cls.parse_ratio(text)
        return {
            "orientation": orientation,
            "orientation_explicit": orientation_explicit,
            "strategy": strategy,
            "strategy_explicit": strategy_explicit,
            "ratio": ratio,
            "ratio_explicit": ratio_explicit,
        }


# ============ Node Functions ============

def _parse_ui_params(user_input: str) -> dict:
    """解析前端UI选择的参数格式 [用户已选择参数：目标方向=竖屏 9:16，转换策略=填充黑边]"""
    import re
    result = {"found": False}

    # 检查是否包含UI参数格式
    if "[用户已选择参数：" not in user_input:
        return result

    # 解析目标方向
    orient_match = re.search(r'目标方向\s*=\s*([^，,\]]+)', user_input)
    if orient_match:
        orient_text = orient_match.group(1).strip()
        if "竖屏" in orient_text:
            result["target_orientation"] = "portrait"
            result["ratio_text"] = orient_text
        elif "横屏" in orient_text:
            result["target_orientation"] = "landscape"
            result["ratio_text"] = orient_text

        # 解析比例
        ratio_map = {"9:16": 0.5625, "4:5": 0.8, "16:9": 1.7778, "21:9": 2.3333, "4:3": 1.3333}
        for ratio_text, ratio_value in ratio_map.items():
            if ratio_text in orient_text:
                result["target_ratio"] = ratio_value
                break

    # 解析转换策略
    strategy_match = re.search(r'转换策略\s*=\s*([^，,\]]+)', user_input)
    if strategy_match:
        strategy_text = strategy_match.group(1).strip()
        strategy_map = {
            "填充黑边": "pad",
            "中心裁剪": "crop",
            "智能裁剪": "smart_crop",
            "拉伸填充": "stretch",
            "镜像滚动": "mirror_scroll",
            "平移运镜": "pan_scroll",
        }
        for name, strategy in strategy_map.items():
            if name in strategy_text:
                result["strategy"] = strategy
                result["strategy_text"] = name
                break

    if result.get("target_orientation") and result.get("strategy"):
        result["found"] = True

    # 解析压缩级别
    compress_match = re.search(r'压缩级别\s*=\s*([^，,\]]+)', user_input)
    if compress_match:
        level_text = compress_match.group(1).strip()
        level_map = {
            "低": "low",
            "中": "medium",
            "高": "high",
        }
        for name, level in level_map.items():
            if name in level_text:
                result["compression_level"] = level
                result["compression_level_text"] = name
                result["found"] = True
                break

    return result


def analyze_intent(state: VideoAgentState) -> VideoAgentState:
    """分析用户意图 - 使用 LLM 生成响应"""
    user_input = state["user_input"]

    llm_response = ""
    all_params_provided = False

    # 优先解析UI选择参数格式 [用户已选择参数：...]
    ui_params = _parse_ui_params(user_input)
    if ui_params["found"]:
        # UI参数解析成功，直接使用
        target_orientation = ui_params.get("target_orientation")
        strategy = ui_params.get("strategy")
        ratio = ui_params.get("target_ratio")
        orientation_explicit = True
        strategy_explicit = True
        ratio_explicit = True
        all_params_provided = True
        llm_response = f"好的，我把视频转换为{target_orientation=='portrait' and '竖屏' or '横屏'}（{ui_params.get('ratio_text', '9:16')}），使用{ui_params.get('strategy_text', '填充黑边')}策略。"

        state["target_orientation"] = target_orientation
        state["strategy"] = strategy
        state["target_ratio"] = ratio
        state["orientation_explicit"] = orientation_explicit
        state["strategy_explicit"] = strategy_explicit
        state["ratio_explicit"] = ratio_explicit
        state["all_params_provided"] = all_params_provided

        msg = ConversationMessage(
            role="assistant",
            content=llm_response,
            timestamp=datetime.now().isoformat(),
        )
        state["messages"].append(msg)
        return state

    # 优先使用 LLM 意图解析（如果可用）
    _llm_parse_intent = _get_llm_parse_intent()
    if _llm_parse_intent:
        try:
            from agent.langchain_agent import MinMaxLLM, get_conversation_history
            llm = MinMaxLLM(api_key=LLM_API_KEY)
            # 尝试从 LangChain Memory 获取历史
            session_id = state.get("session_id")
            if session_id:
                chat_history = get_conversation_history(session_id)
                # 转换为 dict 格式供 parse_intent 使用
                history = [{"role": "human" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                          for m in chat_history.messages]
            else:
                history = state.get("messages", [])
            parsed = _llm_parse_intent(user_input, llm, history=history)

            target_feature = parsed.get("target_feature", "convert")
            compression_level = parsed.get("compression_level")
            compression_explicit = parsed.get("compression_explicit", False)
            target_orientation = parsed.get("target_orientation")
            orientation_explicit = parsed.get("orientation_explicit", False)
            strategy = parsed.get("strategy")
            strategy_explicit = parsed.get("strategy_explicit", False)
            ratio = parsed.get("target_ratio")
            ratio_explicit = parsed.get("ratio_explicit", False)
            llm_response = parsed.get("response", "")
            all_params_provided = parsed.get("all_params_provided", False)

            # 如果是压缩请求
            if target_feature == "compress":
                state["current_feature"] = "compress"
                state["compression_level"] = compression_level
                state["compression_explicit"] = compression_explicit
                state["all_params_provided"] = all_params_provided
                state["pending_question"] = None if all_params_provided else "请选择压缩级别"

                msg = ConversationMessage(
                    role="assistant",
                    content=llm_response,
                    timestamp=datetime.now().isoformat(),
                )
                state["messages"].append(msg)
                return state

            # 如果是转换请求（convert或未识别都走转换流程）
            if target_feature == "convert" or target_feature is None:
                state["current_feature"] = "convert"

            # 转换方向格式
            if target_orientation and isinstance(target_orientation, str):
                target_orientation = target_orientation.lower()
                if target_orientation not in ["portrait", "landscape"]:
                    target_orientation = None
                    orientation_explicit = False

        except Exception as e:
            llm_response = f"LLM 解析出错：{str(e)}"
            target_orientation = None
            orientation_explicit = False
            strategy = None
            strategy_explicit = False
            ratio = None
            ratio_explicit = False
            target_feature = "convert"
    else:
        # 无 LLM 时使用默认响应
        llm_response = "请告诉我您想要做什么：转换视频方向还是压缩视频？"
        target_orientation = None
        orientation_explicit = False
        strategy = None
        strategy_explicit = False
        ratio = None
        ratio_explicit = False
        target_feature = "transform"

    # 更新状态
    if target_orientation:
        state["target_orientation"] = target_orientation
    if strategy:
        state["strategy"] = strategy
    if ratio:
        state["target_ratio"] = ratio

    # 记录参数是否明确指定
    state["orientation_explicit"] = orientation_explicit
    state["strategy_explicit"] = strategy_explicit
    state["ratio_explicit"] = ratio_explicit
    state["all_params_provided"] = all_params_provided

    state["current_step"] = "detect_video"

    # 添加 LLM 的响应消息
    if llm_response:
        msg = ConversationMessage(
            role="assistant",
            content=llm_response,
            timestamp=datetime.now().isoformat(),
        )
        state["messages"].append(msg)

    return state


def detect_video(state: VideoAgentState) -> VideoAgentState:
    """检测视频方向"""
    video_path = state.get("temp_video_path") or state.get("video_path")

    if not video_path or not Path(video_path).exists():
        state["error"] = "视频文件不存在"
        state["current_step"] = "confirm_complete"
        state["pending_question"] = None
        return state

    try:
        result = detect_orientation(video_path)
        state["original_orientation"] = result.orientation

        orientation_display = {
            "portrait": "竖屏",
            "landscape": "横屏",
            "square": "正方形",
            "unknown": "未知",
        }.get(result.orientation, result.orientation)

        msg = ConversationMessage(
            role="assistant",
            content=f"检测到视频是{orientation_display}的。",
            timestamp=datetime.now().isoformat(),
        )
        state["messages"].append(msg)

        state["current_step"] = "select_strategy"

    except Exception as e:
        state["error"] = f"方向检测失败: {str(e)}"
        state["current_step"] = "confirm_complete"

    return state


def select_strategy(state: VideoAgentState) -> VideoAgentState:
    """选择转换策略"""
    # 压缩流程直接执行
    if state.get("current_feature") == "compress" and state.get("all_params_provided"):
        state["current_step"] = "execute_compress"
        return state

    # 检查方向是否相同
    if state.get("target_orientation") and state.get("original_orientation"):
        if state["original_orientation"] == state["target_orientation"]:
            msg = ConversationMessage(
                role="assistant",
                content="视频方向已经是目标方向，无需转换。",
                timestamp=datetime.now().isoformat(),
            )
            state["messages"].append(msg)
            state["current_step"] = "confirm_complete"
            return state

    # LLM 已经在 analyze_intent 中生成了响应消息
    # 如果所有参数都提供了，直接执行转换
    if state.get("all_params_provided"):
        state["current_step"] = "execute_transform"
        return state

    # 缺少参数
    # 如果刚从 handle_user_response 返回（current_step="waiting_for_user"），不设置 pending_question，让流程结束
    if state.get("current_step") == "waiting_for_user":
        return state
    # 否则设置 pending_question
    state["pending_question"] = "waiting_for_params"
    return state


def execute_transform(state: VideoAgentState) -> VideoAgentState:
    """执行转换"""
    video_path = state.get("temp_video_path") or state.get("video_path")

    if not video_path:
        state["error"] = "视频文件不存在"
        state["current_step"] = "confirm_complete"
        return state

    # 生成输出路径
    output_dir = Path("F:/video")
    output_dir.mkdir(exist_ok=True)
    input_name = Path(video_path).stem
    suffix = Path(video_path).suffix
    output_path = str(output_dir / f"{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    try:
        request = TransformRequest(
            input_path=video_path,
            output_path=output_path,
            target_orientation=state.get("target_orientation"),
            strategy=state.get("strategy", "pad"),
            target_ratio=state.get("target_ratio", 9/16),
        )

        def progress_callback(progress: float):
            # 进度回调，可用于更新状态
            pass

        result = transform(request, progress_callback=progress_callback)
        state["transform_result"] = result
        state["current_step"] = "confirm_complete"

        if result.success:
            msg = ConversationMessage(
                role="assistant",
                content=f"转换完成！\n\n输出文件: {result.output_path}\n原始方向: {result.original_orientation}\n目标方向: {result.target_orientation}\n使用策略: {result.strategy_used}",
                timestamp=datetime.now().isoformat(),
            )
            state["messages"].append(msg)
        else:
            state["error"] = result.error
            msg = ConversationMessage(
                role="assistant",
                content=f"转换失败: {result.error}",
                timestamp=datetime.now().isoformat(),
            )
            state["messages"].append(msg)

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        msg = ConversationMessage(
            role="assistant",
            content=f"转换异常: {str(e)}",
            timestamp=datetime.now().isoformat(),
        )
        state["messages"].append(msg)

    return state


def execute_compress(state: VideoAgentState) -> VideoAgentState:
    """执行视频压缩"""
    video_path = state.get("temp_video_path") or state.get("video_path")

    if not video_path:
        state["error"] = "视频文件不存在"
        state["current_step"] = "confirm_complete"
        return state

    # 生成输出路径
    output_dir = Path("F:/video")
    output_dir.mkdir(exist_ok=True)
    input_name = Path(video_path).stem
    suffix = Path(video_path).suffix
    output_path = str(output_dir / f"compressed_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    try:
        from video.processor import compress_video

        compression_level = state.get("compression_level", "medium")

        def progress_callback(progress: float):
            pass

        compress_video(video_path, output_path, compression_level, progress_callback)

        # 获取文件大小信息
        original_size = os.path.getsize(video_path)
        compressed_size = os.path.getsize(output_path)

        state["current_step"] = "confirm_complete"
        msg = ConversationMessage(
            role="assistant",
            content=f"压缩完成！\n\n原始大小: {original_size/1024/1024:.2f}MB\n压缩后: {compressed_size/1024/1024:.2f}MB\n压缩比: {compressed_size/original_size:.1%}",
            timestamp=datetime.now().isoformat(),
        )
        state["messages"].append(msg)

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        msg = ConversationMessage(
            role="assistant",
            content=f"压缩异常: {str(e)}",
            timestamp=datetime.now().isoformat(),
        )
        state["messages"].append(msg)

    return state


def execute_concat(state: VideoAgentState) -> VideoAgentState:
    """执行视频拼接"""
    video_path = state.get("temp_video_path") or state.get("video_path")

    if not video_path:
        state["error"] = "视频文件不存在"
        state["current_step"] = "confirm_complete"
        return state

    # 获取多文件列表
    video_files = state.get("video_files", [video_path])
    if len(video_files) < 2:
        state["error"] = "拼接至少需要2个视频文件"
        state["current_step"] = "confirm_complete"
        return state

    # 生成输出路径
    output_dir = Path("F:/video")
    output_dir.mkdir(exist_ok=True)
    input_name = Path(video_files[0]).stem
    suffix = Path(video_files[0]).suffix
    output_path = str(output_dir / f"concat_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    try:
        from video.processor import concat_videos

        keep_audio = state.get("keep_audio", True)

        def progress_callback(progress: float):
            pass

        concat_videos(video_files, output_path, keep_audio=keep_audio, progress_callback=progress_callback)

        state["current_step"] = "confirm_complete"
        msg = ConversationMessage(
            role="assistant",
            content=f"拼接完成！\n\n输出文件: {output_path}",
            timestamp=datetime.now().isoformat(),
        )
        state["messages"].append(msg)

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        msg = ConversationMessage(
            role="assistant",
            content=f"拼接异常: {str(e)}",
            timestamp=datetime.now().isoformat(),
        )
        state["messages"].append(msg)

    return state


def confirm_complete(state: VideoAgentState) -> VideoAgentState:
    """确认完成"""
    state["pending_question"] = None
    return state


def handle_user_response(state: VideoAgentState) -> VideoAgentState:
    """处理用户对问题的回答 - 使用 LLM 解析"""
    user_input = state["user_input"]

    # 使用 LLM 解析用户的补充信息
    _llm_parse_intent = _get_llm_parse_intent()
    if _llm_parse_intent:
        try:
            from agent.langchain_agent import MinMaxLLM, get_conversation_history
            llm = MinMaxLLM(api_key=LLM_API_KEY)
            # 尝试从 LangChain Memory 获取历史
            session_id = state.get("session_id")
            if session_id:
                chat_history = get_conversation_history(session_id)
                history = [{"role": "human" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                          for m in chat_history.messages]
            else:
                history = state.get("messages", [])
            parsed = _llm_parse_intent(user_input, llm, history=history)

            target_feature = parsed.get("target_feature", state.get("current_feature"))
            compression_level = parsed.get("compression_level")
            compression_explicit = parsed.get("compression_explicit", False)
            target_orientation = parsed.get("target_orientation")
            orientation_explicit = parsed.get("orientation_explicit", False)
            strategy = parsed.get("strategy")
            strategy_explicit = parsed.get("strategy_explicit", False)
            ratio = parsed.get("target_ratio")
            ratio_explicit = parsed.get("ratio_explicit", False)
            llm_response = parsed.get("response", "")
            all_params_provided = parsed.get("all_params_provided", False)

            # 更新状态
            if target_feature == "compress":
                state["current_feature"] = "compress"
                if compression_level:
                    state["compression_level"] = compression_level
                state["compression_explicit"] = compression_explicit
                state["all_params_provided"] = compression_explicit and bool(compression_level)
                state["pending_question"] = None if state["all_params_provided"] else "请选择压缩级别"
            elif target_feature == "concat":
                state["current_feature"] = "concat"
                # 如果上传了多个视频文件，参数就完整了
                video_files = state.get("video_files")
                if video_files and len(video_files) >= 2:
                    state["all_params_provided"] = True
                    state["pending_question"] = None
                    state["current_step"] = "execute_concat"
                else:
                    state["all_params_provided"] = False
                    state["pending_question"] = "请上传至少2个视频文件进行拼接"
            else:
                # convert 或其他
                state["current_feature"] = "convert"
                if target_orientation and orientation_explicit:
                    state["target_orientation"] = target_orientation.lower()
                if strategy and strategy_explicit:
                    state["strategy"] = strategy
                if ratio and ratio_explicit:
                    state["target_ratio"] = ratio

                state["orientation_explicit"] = state.get("orientation_explicit") or orientation_explicit
                state["strategy_explicit"] = state.get("strategy_explicit") or strategy_explicit
                state["ratio_explicit"] = state.get("ratio_explicit") or ratio_explicit
                state["all_params_provided"] = all_params_provided or (
                    state.get("orientation_explicit") and state.get("strategy_explicit")
                )

            # 添加 LLM 响应
            if llm_response:
                msg = ConversationMessage(
                    role="assistant",
                    content=llm_response,
                    timestamp=datetime.now().isoformat(),
                )
                state["messages"].append(msg)

        except Exception as e:
            msg = ConversationMessage(
                role="assistant",
                content=f"解析出错：{str(e)}",
                timestamp=datetime.now().isoformat(),
            )
            state["messages"].append(msg)
    else:
        # 无 LLM 时的回退
        parsed = IntentParser.parse(user_input)
        if parsed.get("orientation_explicit"):
            state["target_orientation"] = parsed.get("orientation")
            state["orientation_explicit"] = True
        if parsed.get("strategy_explicit"):
            state["strategy"] = parsed.get("strategy")
            state["strategy_explicit"] = True
        if parsed.get("ratio_explicit"):
            state["target_ratio"] = parsed.get("ratio")
            state["ratio_explicit"] = True
        state["all_params_provided"] = state.get("orientation_explicit") and state.get("strategy_explicit")

    # 只有在参数完整时才清除 pending_question
    if not state.get("all_params_provided"):
        # 清除 pending_question，避免 should_proceed 再次路由到 waiting_for_user
        state["pending_question"] = None
        # 设置 current_step 为 waiting_for_user，让 should_proceed 返回 select_strategy 结束循环
        state["current_step"] = "waiting_for_user"
        return state
    else:
        state["pending_question"] = None
        # 参数完整时直接设置执行步骤
        if state.get("current_feature") == "compress":
            state["current_step"] = "execute_compress"
        else:
            state["current_step"] = "execute_transform"
        return state


# ============ Route Functions ============

def should_proceed(state: VideoAgentState) -> Literal["select_strategy", "execute_transform", "execute_compress", "execute_concat", "waiting_for_user", "confirm_complete"]:
    """判断下一步"""
    # 如果 current_step 已经是 waiting_for_user，说明刚从 handle_user_response 返回，结束流程
    current_step = state.get("current_step")
    if current_step in ("execute_transform", "execute_compress", "execute_concat"):
        return current_step

    # 如果刚从 handle_user_response 返回，结束流程让用户继续对话
    if current_step == "waiting_for_user":
        # pending_question 会在用户下次发送消息时由 handle_user_response 处理
        # 如果 pending_question 为 None 但 current_feature 已设置，说明参数已完整
        if state.get("current_feature") == "concat" and state.get("all_params_provided"):
            return "execute_concat"
        if state.get("pending_question"):
            return "confirm_complete"
        # 流程结束，等待用户下次输入
        return "confirm_complete"

    # 有待回答问题时等待用户
    if state.get("pending_question"):
        return "waiting_for_user"

    # 压缩流程
    if state.get("current_feature") == "compress" and state.get("all_params_provided"):
        return "execute_compress"
    # 拼接流程（参数由前端提供）
    if state.get("current_feature") == "concat" and state.get("all_params_provided"):
        return "execute_concat"
    # 所有参数都提供了才执行转换
    if state.get("all_params_provided"):
        return "execute_transform"
    return "select_strategy"


# ============ Graph Construction ============

def create_video_agent_graph():
    """创建视频转换 Agent 图"""
    if not LANGGRAPH_AVAILABLE:
        return None

    graph = StateGraph(VideoAgentState)

    # 添加节点
    graph.add_node("analyze_intent", analyze_intent)
    graph.add_node("detect_video", detect_video)
    graph.add_node("select_strategy", select_strategy)
    graph.add_node("execute_transform", execute_transform)
    graph.add_node("execute_compress", execute_compress)
    graph.add_node("execute_concat", execute_concat)
    graph.add_node("confirm_complete", confirm_complete)
    graph.add_node("handle_user_response", handle_user_response)

    # 设置入口
    graph.set_entry_point("analyze_intent")

    # 主流程
    graph.add_edge("analyze_intent", "detect_video")
    graph.add_edge("detect_video", "select_strategy")

    # select_strategy 条件边
    graph.add_conditional_edges(
        "select_strategy",
        should_proceed,
        {
            "select_strategy": "select_strategy",
            "execute_transform": "execute_transform",
            "execute_compress": "execute_compress",
            "execute_concat": "execute_concat",
            "waiting_for_user": "handle_user_response",
            "confirm_complete": "confirm_complete",
        }
    )

    # handle_user_response 条件边
    graph.add_conditional_edges(
        "handle_user_response",
        should_proceed,
        {
            "execute_transform": "execute_transform",
            "execute_compress": "execute_compress",
            "execute_concat": "execute_concat",
            "confirm_complete": "confirm_complete",
        }
    )

    # handle_user_response 处理完后不需要边，should_proceed 会根据 current_step 决定下一步

    graph.add_edge("execute_transform", "confirm_complete")
    graph.add_edge("execute_compress", "confirm_complete")
    graph.add_edge("execute_concat", "confirm_complete")
    graph.add_edge("confirm_complete", END)

    return graph.compile().with_config(recursion_limit=100)


# ============ Agent Runner ============

class VideoAgent:
    """视频转换 Agent"""

    def __init__(self):
        self.graph = create_video_agent_graph()
        self.sessions: dict[str, VideoAgentState] = {}

    def _create_initial_state(
        self,
        user_input: str,
        video_path: Optional[str] = None,
        temp_video_path: Optional[str] = None,
        session_id: Optional[str] = None,
        video_files: Optional[list[str]] = None,
    ) -> VideoAgentState:
        """创建初始状态"""
        return VideoAgentState(
            user_input=user_input,
            video_path=video_path,
            temp_video_path=temp_video_path,
            video_files=video_files,
            original_orientation=None,
            target_orientation=None,
            strategy="pad",
            target_ratio=9/16,
            orientation_explicit=False,
            strategy_explicit=False,
            ratio_explicit=False,
            all_params_provided=False,
            current_step="analyze_intent",
            messages=[],
            transform_result=None,
            error=None,
            session_id=session_id or datetime.now().strftime("%Y%m%d%H%M%S"),
            history=[],
            pending_question=None,
        )

    def run(
        self,
        user_input: str,
        video_path: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> VideoAgentState:
        """
        运行 Agent（单轮）

        Args:
            user_input: 用户输入（自然语言）
            video_path: 视频文件路径
            session_id: 会话 ID（用于多轮对话）

        Returns:
            最终状态
        """
        if not self.graph:
            return {
                "error": "LangGraph 不可用，请安装: pip install langgraph",
                "current_step": "error",
                "messages": [],
            }

        state = self._create_initial_state(
            user_input=user_input,
            video_path=video_path,
            session_id=session_id,
        )

        result = self.graph.invoke(state)
        return result

    def process_video(
        self,
        user_input: str,
        temp_video_path: str,
        session_id: Optional[str] = None,
        video_files: Optional[list[str]] = None,
    ) -> VideoAgentState:
        """
        处理上传的视频（多轮）

        Args:
            user_input: 用户输入
            temp_video_path: 临时视频文件路径
            session_id: 会话 ID
            video_files: 多文件路径列表（用于拼接）

        Returns:
            最终状态
        """
        if not self.graph:
            return {
                "error": "LangGraph 不可用",
                "current_step": "error",
                "messages": [],
            }

        # 如果有 session，继续历史对话
        if session_id and session_id in self.sessions:
            state = self.sessions[session_id]
            state["user_input"] = user_input
            state["temp_video_path"] = temp_video_path
            if video_files:
                state["video_files"] = video_files
        else:
            # 创建会话目录并持久化视频
            actual_session_id = session_id or datetime.now().strftime("%Y%m%d%H%M%S")
            session_dir = SESSIONS_DIR / actual_session_id
            session_dir.mkdir(parents=True, exist_ok=True)

            # 复制主视频到会话目录
            if temp_video_path and Path(temp_video_path).exists():
                dest_path = session_dir / f"video{Path(temp_video_path).suffix}"
                shutil.copy2(temp_video_path, dest_path)
                temp_video_path = str(dest_path)

            # 复制多个视频到会话目录（用于拼接）
            if video_files:
                persisted_files = []
                for i, vf in enumerate(video_files):
                    if Path(vf).exists():
                        dest_path = session_dir / f"video_{i}{Path(vf).suffix}"
                        shutil.copy2(vf, dest_path)
                        persisted_files.append(str(dest_path))
                video_files = persisted_files

            state = self._create_initial_state(
                user_input=user_input,
                temp_video_path=temp_video_path,
                session_id=actual_session_id,
            )
            if video_files:
                state["video_files"] = video_files

        result = self.graph.invoke(state)

        # 使用结果中的 session_id（可能由 _create_initial_state 生成）
        actual_session_id = result.get("session_id")

        # 同步消息到 LangChain Memory
        if actual_session_id:
            self._sync_messages_to_memory(actual_session_id, result.get("messages", []))

        # 保存到 sessions
        if actual_session_id:
            self.sessions[actual_session_id] = result

        return result

    def continue_conversation(
        self,
        user_input: str,
        session_id: str,
    ) -> VideoAgentState:
        """
        继续多轮对话

        Args:
            user_input: 用户输入
            session_id: 会话 ID

        Returns:
            更新后的状态
        """
        if session_id not in self.sessions:
            return {
                "error": "Session not found",
                "current_step": "error",
                "messages": [],
            }

        state = self.sessions[session_id]
        state["user_input"] = user_input

        result = self.graph.invoke(state)

        # 同步消息到 LangChain Memory
        self._sync_messages_to_memory(session_id, result.get("messages", []))

        self.sessions[session_id] = result
        return result

    def get_session(self, session_id: str) -> Optional[VideoAgentState]:
        """获取会话状态"""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[str]:
        """列出所有会话 ID"""
        return list(self.sessions.keys())

    def _sync_messages_to_memory(self, session_id: str, messages: list) -> None:
        """同步消息到 LangChain Memory"""
        from agent.langchain_agent import get_conversation_history
        try:
            chat_history = get_conversation_history(session_id)
            # 获取已存储的消息数量，避免重复添加
            existing_count = len(chat_history.messages)
            # 只添加新消息
            for msg in messages[existing_count:]:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user" or role == "human":
                    chat_history.add_user_message(content)
                elif role == "assistant" or role == "ai":
                    chat_history.add_ai_message(content)
        except Exception:
            pass  # Memory 同步失败不影响主流程


# ============ Convenience Functions ============

def run_video_agent(
    user_input: str,
    video_path: Optional[str] = None,
) -> VideoAgentState:
    """快捷运行函数"""
    agent = VideoAgent()
    return agent.run(user_input, video_path)


def chat_with_agent(
    user_input: str,
    video_path: Optional[str] = None,
) -> str:
    """
    简易聊天接口，返回助手的回复文本

    Args:
        user_input: 用户输入
        video_path: 视频路径

    Returns:
        助手回复文本
    """
    agent = VideoAgent()
    result = agent.run(user_input, video_path)

    if result.get("error"):
        return f"错误: {result['error']}"

    # 返回最后一条助手消息
    for msg in reversed(result.get("messages", [])):
        if msg.get("role") == "assistant":
            return msg.get("content", "")

    return "处理完成"
