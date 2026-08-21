"""
路由和用户响应处理 Node

新增技能步骤：
1. 在 execute.py 添加 execute_xxx 函数
2. 在 analyze.py FEATURE_TO_STEP 添加 "xxx": "execute_xxx"
3. 在 routing.py FEATURE_TO_STEP 添加 "xxx": "execute_xxx"
4. 在 frontend/src/stores/app.ts formatSelectedParams() 添加参数格式化
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
    "convert": "execute_transform",
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
    if feature and feature != "convert" and all_params:
        state["current_step"] = FEATURE_TO_STEP.get(feature, "confirm_complete")
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

    # 缺少参数，结束让用户补充
    return state


def handle_user_response(state: VideoAgentState) -> VideoAgentState:
    """处理用户追问 - 简单合并到上下文后重新分析

    核心思路：
    - handle_user_response 只负责把用户的追问内容合并到上下文
    - 所有业务逻辑（意图识别、参数解析、状态设置）都在 analyze_intent 中处理
    """
    user_input = state["user_input"]
    pending_question = state.get("pending_question")

    print(f"[DEBUG handle_user_response] pending_question={pending_question}, user_input={user_input[:50]}")

    # 简单拼接用户的回答和之前的问题，然后重新进入 analyze_intent
    if pending_question:
        combined_input = f"{pending_question}\n用户回答：{user_input}"
        state["user_input"] = combined_input

    # 清除 pending_question，避免影响新的分析流程
    state["pending_question"] = None

    # 重新进入 analyze_intent 处理所有业务逻辑
    from agent.nodes.analyze import analyze_intent
    return analyze_intent(state)


def should_proceed(state: VideoAgentState) -> Literal["execute_transform", "execute_compress", "execute_concat", "execute_trim", "execute_condense", "execute_restore", "execute_info", "execute_editor", "waiting_for_user", "confirm_complete"]:
    """判断下一步"""
    current_step = state.get("current_step")
    print(f"[DEBUG should_proceed] current_step={current_step}, pending_question={state.get('pending_question')}, current_feature={state.get('current_feature')}")

    # 如果正在执行中，直接继续执行
    if current_step in ("execute_transform", "execute_compress", "execute_concat", "execute_trim", "execute_condense", "execute_restore", "execute_info", "execute_editor"):
        return current_step

    # 如果刚从 handle_user_response 返回（current_step 被设置为 confirm_complete），结束流程
    if current_step == "confirm_complete":
        return "confirm_complete"

    # 如果 current_step 是 waiting_for_user，路由到 handle_user_response 处理用户回答
    if current_step == "waiting_for_user":
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
    # 横竖屏转换：参数完整时执行，否则结束让用户补充
    if state.get("current_feature") == "convert":
        if state.get("all_params_provided"):
            return "execute_transform"
        if state.get("pending_question"):
            return "confirm_complete"
        return "confirm_complete"
    # 其他功能：参数完整时执行
    if state.get("all_params_provided"):
        return "execute_transform"
    # 参数不完整，结束让用户补充
    return "confirm_complete"
