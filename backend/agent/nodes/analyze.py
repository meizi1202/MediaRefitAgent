"""
意图分析 Node
"""
from datetime import datetime
from typing import Optional
import os

from agent.types import VideoAgentState, ConversationMessage
from agent.streaming import send_stream_chunk, is_streaming_enabled
from langchain_core.messages import HumanMessage


def _append_message(state: VideoAgentState, role: str, content: str):
    """添加消息并发送流式消息"""
    msg = ConversationMessage(
        role=role,
        content=content,
        timestamp=datetime.now().isoformat(),
    )
    state["messages"].append(msg)
    if is_streaming_enabled():
        send_stream_chunk(content)


class IntentParser:
    """意图解析器"""

    # 方向关键词
    ORIENTATION_KEYWORDS = {
        "portrait": ["竖屏", "portrait", "垂直", "竖", "9:16", "9/16", "4:5", "4/5", "1:1", "1/1", "2:3", "2/3", "短视频", "抖音", "快手", "Instagram", "IG"],
        "landscape": ["横屏", "landscape", "水平", "横", "16:9", "16/9", "21:9", "21/9", "4:3", "4/3", "3:2", "3/2", "横版", "电影"],
    }

    # 策略关键词（按优先级排序：更具体的在前）
    STRATEGY_KEYWORDS = {
        "smart_crop": ["智能裁剪", "smart", "AI裁剪", "ai crop", "智能", "AI"],
        "stretch": ["拉伸填充", "拉伸", "stretch"],
        "mirror_scroll": ["镜像滚动", "镜像", "mirror"],
        "pan_scroll": ["平移运镜", "平移", "运镜", "pan"],
        "crop": ["裁剪", "crop", "切", "截"],
        "pad": ["填充", "pad", "黑边", "留边", "保持完整"],
        "rotate": ["旋转", "rotate", "旋转90度", "rotate90"],
    }

    # 压缩级别关键词
    COMPRESSION_KEYWORDS = {
        "low": ["高质量", "low", "低压缩", "大文件", "保持质量"],
        "medium": ["中等质量", "medium", "平衡", "中等"],
        "high": ["高质量小文件", "high", "小文件", "高压缩", "压缩率高"],
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
        return None, False

    @classmethod
    def parse_ratio(cls, text: str) -> tuple[Optional[float], bool]:
        """解析比例参数，返回 (比例, 是否明确指定)"""
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
    def parse_compression(cls, text: str) -> tuple[Optional[str], bool]:
        """解析压缩级别，返回 (级别, 是否明确指定)"""
        text_lower = text.lower()
        for level, keywords in cls.COMPRESSION_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return level, True
        return None, False

    @classmethod
    def parse(cls, text: str) -> dict:
        """解析用户输入"""
        orientation, orientation_explicit = cls.parse_orientation(text)
        strategy, strategy_explicit = cls.parse_strategy(text)
        ratio, ratio_explicit = cls.parse_ratio(text)
        compression, compression_explicit = cls.parse_compression(text)
        return {
            "orientation": orientation,
            "orientation_explicit": orientation_explicit,
            "strategy": strategy,
            "strategy_explicit": strategy_explicit,
            "ratio": ratio,
            "ratio_explicit": ratio_explicit,
            "compression": compression,
            "compression_explicit": compression_explicit,
        }


def _parse_ui_params(user_input: str) -> dict:
    """解析前端UI选择的参数格式 [用户已选择参数：功能=横竖屏转换，目标方向=竖屏 9:16，转换策略=填充黑边]"""
    import re
    result = {"found": False}

    # 检查是否包含UI参数格式
    if "[用户已选择参数：" not in user_input:
        return result

    # 解析功能类型
    feature_match = re.search(r'功能\s*=\s*([^，,\]]+)', user_input)
    if feature_match:
        feature_text = feature_match.group(1).strip()
        feature_map = {
            "横竖屏转换": "convert",
            "视频压缩": "compress",
            "视频修剪": "trim",
            "视频拼接": "concat",
            "智能缩编": "condense",
            "老视频修复": "restore",
            "智能剪辑": "editor",
            "视频信息获取": "info",
        }
        for name, feat in feature_map.items():
            if name in feature_text:
                result["feature"] = feat
                result["found"] = True
                break

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

    # 解析修剪时间
    trim_time_match = re.search(r'从(\d+\.?\d*)秒到(\d+\.?\d*)秒', user_input)
    if trim_time_match:
        result["start_time"] = float(trim_time_match.group(1))
        result["end_time"] = float(trim_time_match.group(2))
        result["start_time_explicit"] = True
        result["end_time_explicit"] = True
        result["found"] = True

    return result


def analyze_intent(state: VideoAgentState) -> VideoAgentState:
    """分析用户意图 - 使用 LLM 生成响应"""
    import os

    user_input = state["user_input"]

    llm_response = ""
    all_params_provided = False

    # 优先解析UI选择参数格式 [用户已选择参数：...]
    ui_params = _parse_ui_params(user_input)
    if ui_params.get("found"):
        feature = ui_params.get("feature", "convert")
        state["current_feature"] = feature

        # 根据功能类型设置状态
        if feature == "convert":
            target_orientation = ui_params.get("target_orientation")
            strategy = ui_params.get("strategy")
            ratio = ui_params.get("target_ratio")
            state["target_orientation"] = target_orientation
            state["strategy"] = strategy
            state["target_ratio"] = ratio
            state["orientation_explicit"] = True
            state["strategy_explicit"] = True
            state["ratio_explicit"] = True
            all_params_provided = True
            llm_response = f"好的，我把视频转换为{'竖屏' if target_orientation == 'portrait' else '横屏'}（{ui_params.get('ratio_text', '9:16')}），使用{ui_params.get('strategy_text', '填充黑边')}策略。"
        elif feature == "compress":
            compression_level = ui_params.get("compression_level")
            state["compression_level"] = compression_level
            state["compression_explicit"] = True
            all_params_provided = True
            llm_response = f"好的，我将把视频压缩为{ui_params.get('compression_level_text', '中等')}质量。"
        elif feature == "info":
            all_params_provided = True
            llm_response = "好的，我来获取视频的详细信息。"
        elif feature == "trim":
            # 修剪需要时间参数
            start_time = ui_params.get("start_time")
            end_time = ui_params.get("end_time")
            start_explicit = ui_params.get("start_time_explicit", False)
            end_explicit = ui_params.get("end_time_explicit", False)
            if start_time is not None:
                state["start_time"] = start_time
            if end_time is not None:
                state["end_time"] = end_time
            state["start_time_explicit"] = start_explicit
            state["end_time_explicit"] = end_explicit
            all_params_provided = start_explicit and end_explicit
            if all_params_provided:
                llm_response = f"好的，我来修剪视频从{start_time}秒到{end_time}秒。"
            else:
                llm_response = "好的，我来处理视频修剪。"
        elif feature == "concat":
            all_params_provided = True
            llm_response = "好的，我来拼接视频。"
        elif feature == "condense":
            all_params_provided = True
            llm_response = "好的，我来处理智能缩编。"
        elif feature == "restore":
            all_params_provided = True
            llm_response = "好的，我来处理老视频修复。"
        elif feature == "editor":
            all_params_provided = True
            llm_response = "好的，我来处理智能剪辑。"
        else:
            all_params_provided = True
            llm_response = f"好的，我来处理。"

        state["all_params_provided"] = all_params_provided
        _append_message(state, "assistant", llm_response)
        return state

    # 优先使用 LLM 意图解析（如果可用）
    # 同时做本地解析作为降级
    local_parsed = IntentParser.parse(user_input)

    LLM_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
    llm_parse_intent = None

    def _get_llm_parse_intent():
        nonlocal llm_parse_intent
        if llm_parse_intent is None:
            api_key = os.environ.get("MINIMAX_API_KEY", "")
            if api_key:
                try:
                    from agent.langchain_agent import parse_intent as llm_parse_intent_impl
                    llm_parse_intent = llm_parse_intent_impl
                except ImportError:
                    llm_parse_intent = None
        return llm_parse_intent

    _llm_parse_intent = _get_llm_parse_intent()
    if _llm_parse_intent:
        try:
            from agent.langchain_agent import MinMaxLLM
            from agent.memory import get_conversation_history
            llm = MinMaxLLM(api_key=LLM_API_KEY)
            # 优先使用当前会话中已累积的消息（state["messages"]），因为它们已经被添加
            # 只有当 state["messages"] 为空时，才尝试从 LangChain Memory 获取
            session_id = state.get("session_id")
            state_messages = state.get("messages", [])
            if session_id and len(state_messages) > 0:
                # 当前会话已有消息，直接使用
                history = []
                for m in state_messages:
                    if isinstance(m, dict):
                        role = "user" if m.get("role") in ("user", "human") else "assistant"
                        history.append({"role": role, "content": m.get("content", "")})
                    else:
                        # LangChain message object
                        role = "user" if isinstance(m, HumanMessage) else "assistant"
                        history.append({"role": role, "content": m.content})
            elif session_id:
                # 当前会话暂无消息，尝试从 LangChain Memory 获取
                chat_history = get_conversation_history(session_id)
                history = [{"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                          for m in chat_history.messages]
            else:
                history = []
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
            # highlight 参数
            target_duration = parsed.get("target_duration", 60)
            target_duration_explicit = parsed.get("target_duration_explicit", False)
            num_clips = parsed.get("num_clips", 5)
            num_clips_explicit = parsed.get("num_clips_explicit", False)
            # transition 参数
            transition_type = parsed.get("transition_type", "fade")
            transition_type_explicit = parsed.get("transition_type_explicit", False)
            transition_duration = parsed.get("transition_duration", 1.0)
            transition_duration_explicit = parsed.get("transition_duration_explicit", False)
            llm_response = parsed.get("response", "")
            all_params_provided = parsed.get("all_params_provided", False)

            # 如果是压缩请求
            if target_feature == "compress":
                # 本地解析降级（如果 LLM 没有解析出压缩级别）
                if not compression_explicit and local_parsed.get("compression_explicit"):
                    compression_level = local_parsed.get("compression")
                    compression_explicit = True
                state["current_feature"] = "compress"
                state["compression_level"] = compression_level
                state["compression_explicit"] = compression_explicit
                state["all_params_provided"] = compression_explicit and bool(compression_level)
                state["pending_question"] = None if state["all_params_provided"] else "请选择压缩级别"
                if state["all_params_provided"]:
                    level_str = {"low": "高质量", "medium": "中等质量", "high": "高质量小文件"}.get(compression_level, "")
                    llm_response = f"好的，将视频压缩为{level_str}。"
                _append_message(state, "assistant", llm_response)
                return state

            # 如果是视频信息请求
            if target_feature == "info":
                state["current_feature"] = "info"
                state["all_params_provided"] = all_params_provided
                state["pending_question"] = None
                _append_message(state, "assistant", llm_response or "好的，我来获取视频的详细信息。")
                return state

            # 如果是视频修剪请求
            if target_feature == "trim":
                start_time = parsed.get("start_time")
                end_time = parsed.get("end_time")
                start_time_explicit = parsed.get("start_time_explicit", False)
                end_time_explicit = parsed.get("end_time_explicit", False)

                state["current_feature"] = "trim"
                if start_time is not None:
                    try:
                        state["start_time"] = float(start_time)
                    except (ValueError, TypeError):
                        state["start_time"] = start_time
                if end_time is not None:
                    try:
                        state["end_time"] = float(end_time)
                    except (ValueError, TypeError):
                        state["end_time"] = end_time
                state["start_time_explicit"] = start_time_explicit
                state["end_time_explicit"] = end_time_explicit
                state["all_params_provided"] = start_time_explicit and end_time_explicit
                if not state["all_params_provided"]:
                    missing = []
                    if not start_time_explicit:
                        missing.append("开始时间")
                    if not end_time_explicit:
                        missing.append("结束时间")
                    state["pending_question"] = f"请提供{'和'.join(missing)}"
                else:
                    state["pending_question"] = None
                    state["current_step"] = "execute_trim"

                _append_message(state, "assistant", llm_response)
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

    # 使用本地关键词解析补充 LLM 结果（如果用户明确提到则覆盖）
    if local_parsed.get("orientation_explicit"):
        target_orientation = local_parsed["orientation"]
        orientation_explicit = True
    if local_parsed.get("strategy_explicit"):
        strategy = local_parsed["strategy"]
        strategy_explicit = True
    if local_parsed.get("ratio_explicit"):
        ratio = local_parsed["ratio"]
        ratio_explicit = True

    # 更新 all_params_provided
    all_params_provided = orientation_explicit and strategy_explicit

    # 如果本地解析补充了参数且参数完整，生成正确的回复
    if all_params_provided and (local_parsed.get("orientation") or local_parsed.get("strategy") or local_parsed.get("ratio")):
        orientation_str = "竖屏" if target_orientation == "portrait" else "横屏"
        ratio_str = "9:16" if ratio and ratio < 1 else ("16:9" if ratio and ratio > 1 else "")
        strategy_str = {"pad": "填充黑边", "crop": "中心裁剪", "smart_crop": "智能裁剪", "stretch": "拉伸填充", "mirror_scroll": "镜像滚动", "pan_scroll": "平移运镜"}.get(strategy, strategy or "")
        llm_response = f"好的，使用{ratio_str}{orientation_str}和{strategy_str}策略，正在为您转换..."
        print(f"[DEBUG] Local fallback generated response: {llm_response}")

# 更新状态
    if target_orientation:
        state["target_orientation"] = target_orientation
    if strategy:
        state["strategy"] = strategy
    if ratio:
        state["target_ratio"] = ratio

    # 确保 current_feature 被设置（如果之前未设置）
    if not state.get("current_feature") and target_feature:
        state["current_feature"] = target_feature

    # 记录参数是否明确指定
    state["orientation_explicit"] = orientation_explicit
    state["strategy_explicit"] = strategy_explicit
    state["ratio_explicit"] = ratio_explicit
    state["all_params_provided"] = all_params_provided

    state["current_step"] = "detect_video"

    # 添加 LLM 的响应消息
    if llm_response:
        _append_message(state, "assistant", llm_response)

    return state
