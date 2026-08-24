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
    pending_question = state.get("pending_question")

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

        # 如果有待回答的问题，设置 current_step 让下次用户输入时进入 handle_user_response
        if pending_question:
            state["current_step"] = "waiting_for_user"
            return state

    # 缺少参数，结束让用户补充
    return state


def handle_user_response(state: VideoAgentState) -> VideoAgentState:
    """处理用户追问 - 拼接上下文后重新分析

    核心思路：
    - 将 pending_question 和用户回答拼接，让 LLM 理解用户是在回答哪个问题
    - 不再直接调用 analyze_intent，而是设置 current_step 让条件边路由到 analyze_intent
    """
    user_input = state["user_input"]
    pending_question = state.get("pending_question")

    # 拼接用户的回答和之前的问题
    # 这样 LLM 可以根据上下文理解用户是在回答哪个问题
    combined_input = user_input
    if pending_question:
        combined_input = f"{pending_question}\n用户回答：{user_input}"
        # 清除 pending_question，防止在下一步中再次循环
        state["pending_question"] = None

    # 保存原始 user_input
    original_user_input = state["user_input"]
    # 设置合并后的输入，让下一步的 analyze_intent 处理
    state["user_input"] = combined_input

    # 设置 current_step 为 analyze_intent，让条件边路由到 analyze_intent
    # 注意：不在这里调用 analyze_intent，避免同一步中多次更新 state
    state["current_step"] = "analyze_intent"

    # 恢复原始 user_input（analyze_intent 会读取 combined_input 进行处理）
    state["user_input"] = original_user_input

    return state


def should_proceed(state: VideoAgentState) -> Literal["analyze_intent", "execute_transform", "execute_compress", "execute_concat", "execute_trim", "execute_condense", "execute_restore", "execute_info", "execute_editor", "waiting_for_user", "confirm_complete"]:
    """判断下一步"""
    current_step = state.get("current_step")
    pending_question = state.get("pending_question")
    all_params = state.get("all_params_provided", False)
    feature = state.get("current_feature")

    print(f"[DEBUG should_proceed] current_step={current_step}, pending_question={pending_question}, all_params={all_params}, feature={feature}")

    # 如果 current_step 是 analyze_intent（刚从 handle_user_response 返回），继续分析意图
    # 返回 select_strategy，因为边 detect_video -> select_strategy 已存在，会自动流转
    if current_step == "analyze_intent":
        print(f"[DEBUG should_proceed] -> analyze_intent, return select_strategy")
        return "select_strategy"

    # 如果正在执行中，直接继续执行
    if current_step in ("execute_transform", "execute_compress", "execute_concat", "execute_trim", "execute_condense", "execute_restore", "execute_info", "execute_editor"):
        print(f"[DEBUG should_proceed] -> executing node, return {current_step}")
        return current_step

    # 如果 current_step 是 waiting_for_user，路由到 handle_user_response 处理用户回答
    if current_step == "waiting_for_user":
        # 直接路由到 handle_user_response，让它处理用户的输入
        print(f"[DEBUG should_proceed] -> waiting_for_user, return waiting_for_user")
        return "waiting_for_user"

    # 横竖屏转换：参数完整时执行，否则询问用户
    if feature == "convert":
        # 参数完整时执行
        if all_params:
            print(f"[DEBUG should_proceed] -> convert all_params, return execute_transform")
            return "execute_transform"
        # 如果有待回答的问题，等待用户回答
        if pending_question:
            print(f"[DEBUG should_proceed] -> convert with_pending, return waiting_for_user")
            return "waiting_for_user"
        # 参数不完整，等待用户补充
        print(f"[DEBUG should_proceed] -> convert no_params, return waiting_for_user")
        return "waiting_for_user"

    # 如果刚从 handle_user_response 返回（current_step 被设置为 confirm_complete），结束流程
    if current_step == "confirm_complete":
        print(f"[DEBUG should_proceed] -> confirm_complete, return confirm_complete")
        return "confirm_complete"

    # 其他功能的判断
    if feature == "compress" and all_params:
        return "execute_compress"
    if feature == "concat" and all_params:
        return "execute_concat"
    if feature == "trim" and all_params:
        return "execute_trim"
    if all_params:
        return "execute_transform"

    # 参数不完整，结束让用户补充
    return "confirm_complete"
