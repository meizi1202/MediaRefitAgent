"""
路由和用户响应处理 Node
"""
from datetime import datetime
from typing import Literal
import os

from agent.types import VideoAgentState, ConversationMessage
from agent.streaming import send_stream_chunk, is_streaming_enabled
from langchain_core.messages import HumanMessage

# 功能到执行步骤的映射（与 analyze.py 保持一致）
FEATURE_TO_STEP = {
    "compress": "execute_compress",
    "trim": "execute_trim",
    "concat": "execute_concat",
    "condense": "execute_condense",
    "restore": "execute_restore",
    "editor": "execute_editor",
    "info": "execute_info",
}


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


def select_strategy(state: VideoAgentState) -> VideoAgentState:
    """选择转换策略"""
    feature = state.get("current_feature")
    all_params = state.get("all_params_provided", False)

    # 非 convert 功能，参数完整时直接执行
    if feature != "convert" and feature in FEATURE_TO_STEP and all_params:
        state["current_step"] = FEATURE_TO_STEP[feature]
        return state

    # 横竖屏转换
    if feature == "convert":
        # 检查方向是否相同
        if state.get("target_orientation") and state.get("original_orientation"):
            if state["original_orientation"] == state["target_orientation"]:
                _append_message(state, "assistant", "视频方向已经是目标方向，无需转换。")
                state["current_step"] = "confirm_complete"
                return state

        # 如果所有参数都提供了，直接执行转换
        if all_params:
            state["current_step"] = "execute_transform"
            return state

    # 缺少参数
    # 如果刚从 handle_user_response 返回（current_step="waiting_for_user"），不设置 pending_question，让流程结束
    if state.get("current_step") == "waiting_for_user":
        return state
    # 否则设置 pending_question
    state["pending_question"] = "waiting_for_params"
    return state


def handle_user_response(state: VideoAgentState) -> VideoAgentState:
    """处理用户对问题的回答 - 使用 LLM 解析"""
    import os
    user_input = state["user_input"]
    print(f"[DEBUG handle_user_response] called, current_step={state.get('current_step')}, pending_question={state.get('pending_question')}")

    # 重要检查：如果 current_step 不是 "waiting_for_user"（前一轮结束时设置的），
    # 说明这不是用户回答问题的轮次，而是新一轮对话，不应该处理
    if state.get("current_step") != "waiting_for_user":
        # 跳过处理，让流程结束
        # 清除 pending_question 以避免 should_proceed 再次返回 waiting_for_user
        state["pending_question"] = None
        state["current_step"] = "confirm_complete"
        return state

    # 使用 LLM 解析用户的补充信息
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
            # 优先使用当前会话中已累积的消息（state["messages"]）
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
                chat_history = get_conversation_history(session_id)
                history = [{"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
                          for m in chat_history.messages]
            else:
                history = []
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
            start_time = parsed.get("start_time")
            start_time_explicit = parsed.get("start_time_explicit", False)
            end_time = parsed.get("end_time")
            end_time_explicit = parsed.get("end_time_explicit", False)
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

            # 更新状态
            if target_feature == "compress":
                state["current_feature"] = "compress"
                if compression_level:
                    state["compression_level"] = compression_level
                state["compression_explicit"] = compression_explicit
                state["all_params_provided"] = compression_explicit and bool(compression_level)
                if not state["all_params_provided"]:
                    state["pending_question"] = "请选择压缩级别"
                    _append_message(state, "assistant", state["pending_question"])
                else:
                    state["pending_question"] = None
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
                    _append_message(state, "assistant", state["pending_question"])
            elif target_feature == "trim":
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
                    _append_message(state, "assistant", state["pending_question"])
                else:
                    state["pending_question"] = None
                    state["current_step"] = "execute_trim"
            else:
                # convert 或其他
                state["current_feature"] = "convert"
                if target_orientation and orientation_explicit:
                    state["target_orientation"] = target_orientation.lower()
                if strategy and strategy_explicit:
                    state["strategy"] = strategy
                if ratio and ratio_explicit:
                    state["target_ratio"] = ratio

                # 先更新各个标志位
                state["orientation_explicit"] = state.get("orientation_explicit") or orientation_explicit
                state["strategy_explicit"] = state.get("strategy_explicit") or strategy_explicit
                state["ratio_explicit"] = state.get("ratio_explicit") or ratio_explicit
                # 然后重新计算 all_params_provided（使用更新后的值）
                state["all_params_provided"] = all_params_provided or (
                    state["orientation_explicit"] and state["strategy_explicit"]
                )

            # 添加 LLM 响应
            if llm_response:
                _append_message(state, "assistant", llm_response)

        except Exception as e:
            _append_message(state, "assistant", f"解析出错：{str(e)}")
    else:
        # 无 LLM 时的回退
        from agent.nodes.analyze import IntentParser
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
        feature = state.get("current_feature")
        state["current_step"] = FEATURE_TO_STEP.get(feature, "execute_transform")
        return state


def should_proceed(state: VideoAgentState) -> Literal["select_strategy", "execute_transform", "execute_compress", "execute_concat", "execute_trim", "execute_condense", "execute_restore", "execute_info", "execute_editor", "waiting_for_user", "confirm_complete"]:
    """判断下一步"""
    current_step = state.get("current_step")

    # 如果正在执行中，直接继续执行
    if current_step in ("execute_transform", "execute_compress", "execute_concat", "execute_trim", "execute_condense", "execute_restore", "execute_info", "execute_editor"):
        return current_step

    # 如果刚从 handle_user_response 返回（current_step 被设置为 confirm_complete），结束流程
    if current_step == "confirm_complete":
        return "confirm_complete"

    # 如果 current_step 是 waiting_for_user（handle_user_response 还没执行或执行中），结束流程
    if current_step == "waiting_for_user":
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
    # 修剪流程
    if state.get("current_feature") == "trim" and state.get("all_params_provided"):
        return "execute_trim"
    # 所有参数都提供了才执行转换
    if state.get("all_params_provided"):
        return "execute_transform"
    return "select_strategy"
