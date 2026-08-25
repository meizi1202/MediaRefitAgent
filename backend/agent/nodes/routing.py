"""
路由和用户响应处理 Node

新增技能步骤：
1. 在 execute.py 添加 execute_xxx 函数
2. 在 analyze.py FEATURE_TO_STEP 添加 "xxx": "execute_xxx"
3. 在 routing.py FEATURE_TO_STEP 添加 "xxx": "execute_xxx"
4. 在 frontend/src/stores/app.ts formatSelectedParams() 添加参数格式化
"""
from typing import Literal

from agent.types import VideoAgentState

# pending_question 中缺失的参数映射（可扩展配置）
# key: pending_question 中包含的关键词，value: 对应的参数名列表
PENDING_QUESTION_PARAMS = {
    "convert": {
        "比例": ["ratio", "orientation"],
        "策略": ["strategy"],
    },
    "compress": {
        "压缩级别": ["compression_level"],
    },
    "trim": {
        "时间": ["start_time", "end_time"],
    },
}

# 功能到执行步骤的映射
FEATURE_TO_EXECUTE = {
    "convert": "execute_transform",
    "compress": "execute_compress",
    "trim": "execute_trim",
    "concat": "execute_concat",
    "condense": "execute_condense",
    "restore": "execute_restore",
    "editor": "execute_editor",
    "info": "execute_info",
}


def _parse_answer_params(user_input: str, feature: str) -> dict:
    """解析用户回答中的参数，返回 {param_name: value}"""
    # 清理引号和空白
    text = user_input.strip().strip('"\'').lower()
    result = {}

    if feature == "convert":
        # 解析比例
        ratio_map = {
            "9:16": (0.5625, "portrait"), "4:5": (0.8, "portrait"), "1:1": (1.0, "portrait"),
            "16:9": (1.7778, "landscape"), "21:9": (2.3333, "landscape"), "4:3": (1.3333, "landscape"),
        }
        for ratio_text, (ratio_val, orient) in ratio_map.items():
            if ratio_text in text:
                result["target_ratio"] = ratio_val
                result["target_orientation"] = orient
                result["ratio_explicit"] = True
                result["orientation_explicit"] = True
                break

        # 解析策略
        # 注意：更具体的关键词要放在前面，避免被更短的通用词匹配
        strategy_map = [
            # 拉伸策略（优先级最高，用户明确说要拉伸）
            ("拉伸填充", "stretch"),
            ("拉伸", "stretch"),
            ("不要填充", "stretch"),  # "不要填充黑边" → stretch
            ("不要黑边", "stretch"),   # "不要黑边" → stretch
            # 填充策略
            ("填充黑边", "pad"),
            ("留边", "pad"),
            ("保持完整", "pad"),
            ("pad", "pad"),
            # 裁剪策略
            ("中心裁剪", "crop"),
            ("crop", "crop"),
            # 智能裁剪
            ("智能裁剪", "smart_crop"),
            ("ai裁剪", "smart_crop"),
            ("AI裁剪", "smart_crop"),
        ]
        for kw, strat in strategy_map:
            if kw in text:
                result["strategy"] = strat
                result["strategy_explicit"] = True
                break

    elif feature == "compress":
        level_map = {"低": "low", "中": "medium", "高": "high"}
        for kw, lvl in level_map.items():
            if kw in text:
                result["compression_level"] = lvl
                result["compression_explicit"] = True
                break

    return result


def _get_missing_params(feature: str, state: VideoAgentState) -> list[str]:
    """根据实际状态判断需要补全哪些参数"""
    if feature == "convert":
        missing = []
        if not state.get("orientation_explicit"):
            missing.append("orientation")
        if not state.get("ratio_explicit"):
            missing.append("ratio")
        if not state.get("strategy_explicit"):
            missing.append("strategy")
        return missing
    elif feature == "compress":
        if not state.get("compression_explicit"):
            return ["compression_level"]
    elif feature == "trim":
        missing = []
        if not state.get("start_time_explicit"):
            missing.append("start_time")
        if not state.get("end_time_explicit"):
            missing.append("end_time")
        return missing
    return []


def _check_all_params_provided(feature: str, state: VideoAgentState) -> bool:
    """检查某功能所需参数是否全部提供"""
    if feature == "convert":
        return (state.get("orientation_explicit") and
                state.get("ratio_explicit") and
                state.get("strategy_explicit"))
    elif feature == "compress":
        return bool(state.get("compression_explicit") and state.get("compression_level"))
    elif feature == "trim":
        return bool(state.get("start_time_explicit") and state.get("end_time_explicit"))
    elif feature == "concat":
        return state.get("concat_explicit", False)
    elif feature == "restore":
        return state.get("restoration_preset_explicit", False)
    return True


def handle_user_response(state: VideoAgentState) -> VideoAgentState:
    """处理用户追问 - 预解析参数后直接执行或继续 LLM 解析

    核心思路：
    - 用 IntentParser 预解析用户回答中的关键词，设置 explicit 标志
    - 若所有缺失参数都被关键词命中，直接路由到 execute_* 跳过 LLM 解析
    - 否则设置 current_step = "analyze_intent"，继续 LLM 解析
    """
    user_input = state.get("new_user_input") or state["user_input"]
    pending_question = state.get("pending_question")
    feature = state.get("current_feature")

    print(f"[DEBUG handle_user_response] ENTER user_input={user_input}, pending_question={pending_question}, feature={feature}")
    print(f"[DEBUG handle_user_response] state: orient_explicit={state.get('orientation_explicit')}, ratio_explicit={state.get('ratio_explicit')}, strategy_explicit={state.get('strategy_explicit')}")

    if not pending_question or not feature:
        # pending_question 不存在但 state 中已有明确参数
        # 说明是 execute_* 后用户修改参数，应该走预解析而非 LLM
        has_explicit_params = (
            state.get("orientation_explicit") or state.get("ratio_explicit")
            or state.get("strategy_explicit") or state.get("compression_explicit")
        )
        if not has_explicit_params:
            # 没有任何明确参数，退回到 analyze_intent 继续 LLM 解析
            print(f"[DEBUG handle_user_response] -> analyze_intent (no explicit params)")
            state["current_step"] = "analyze_intent"
            return state
        # 有明确参数，继续走预解析流程
        print(f"[DEBUG handle_user_response] -> continue parsing (has explicit params)")

    # 1. 始终用关键词预解析用户回答（支持用户修改已有参数）
    parsed = _parse_answer_params(user_input, feature)
    print(f"[DEBUG handle_user_response] parsed={parsed}")

    # 2. 将解析结果写入 state
    for key, val in parsed.items():
        state[key] = val

    # 3. 重新计算缺失参数（基于更新后的 state）
    remaining_missing = _get_missing_params(feature, state)
    print(f"[DEBUG handle_user_response] remaining_missing={remaining_missing}")

    # 4. 检查参数是否完整
    all_params_check = _check_all_params_provided(feature, state)
    print(f"[DEBUG handle_user_response] all_params_check={all_params_check}, orientation_explicit={state.get('orientation_explicit')}, ratio_explicit={state.get('ratio_explicit')}, strategy_explicit={state.get('strategy_explicit')}")
    if all_params_check:
        # 参数完整，直接路由到执行节点
        state["pending_question"] = None  # 清除待问问题
        execute_node = FEATURE_TO_EXECUTE.get(feature)
        if execute_node:
            state["current_step"] = execute_node
            print(f"[DEBUG handle_user_response] -> {execute_node} (all params provided)")
            # 清除 combined_input 和 new_user_input
            state["combined_input"] = None
            state["new_user_input"] = None
            return state

    # 5. 更新 pending_question 为剩余缺失参数
    from agent.types import ConversationMessage
    from datetime import datetime
    if remaining_missing and feature == "convert":
        missing_labels = []
        # 只有当参数在 state 中也是缺失时，才加入追问列表
        if "orientation" in remaining_missing and not state.get("orientation_explicit"):
            missing_labels.append("方向")
        if "ratio" in remaining_missing and not state.get("ratio_explicit"):
            missing_labels.append("比例")
        if "strategy" in remaining_missing and not state.get("strategy_explicit"):
            missing_labels.append("策略")

        # 计算之前的 pending_question 对应的缺失参数列表（用于比较）
        pending_question_missing_labels = []
        if pending_question:
            if "比例" in pending_question or "方向" in pending_question:
                pending_question_missing_labels.append("方向")
            if "比例" in pending_question:
                pending_question_missing_labels.append("比例")
            if "策略" in pending_question:
                pending_question_missing_labels.append("策略")

        if missing_labels:
            # 如果追问的参数和之前一样（没有新参数被提供），直接进入执行而非追问
            if set(missing_labels) == set(pending_question_missing_labels):
                # pending_question 没变化，用户只修改了其中一个参数
                # 直接认为参数已完整
                state["pending_question"] = None
                execute_node = FEATURE_TO_EXECUTE.get(feature)
                if execute_node:
                    state["current_step"] = execute_node
                    state["combined_input"] = None
                    state["new_user_input"] = None
                    return state
            else:
                state["pending_question"] = f"请选择{'/'.join(missing_labels)}"
                ask_msg = f"已收到您的选择。请问选择哪个{'/'.join(missing_labels)}？"
                print(f"[DEBUG handle_user_response] sending ask_msg: {ask_msg}")
                msg = ConversationMessage(role="assistant", content=ask_msg, timestamp=datetime.now().isoformat())
                state["messages"].append(msg)
                from agent.streaming import send_stream_chunk, is_streaming_enabled
                if is_streaming_enabled():
                    send_stream_chunk(ask_msg)
    else:
        # 所有参数都已提供，清除 pending_question
        state["pending_question"] = None

    # 设置 current_step
    state["new_user_input"] = None
    state["current_step"] = "waiting_for_user"

    return state


def should_proceed(state: VideoAgentState) -> Literal["analyze_intent", "execute_transform", "execute_compress", "execute_concat", "execute_trim", "execute_condense", "execute_restore", "execute_info", "execute_editor", "handle_user_response", "waiting_for_user", "confirm_complete"]:
    """判断下一步"""
    current_step = state.get("current_step")
    pending_question = state.get("pending_question")
    all_params = state.get("all_params_provided", False)
    feature = state.get("current_feature")

    print(f"[DEBUG should_proceed] current_step={current_step}, pending_question={pending_question}, all_params={all_params}, feature={feature}")

    # 如果 current_step 是 waiting_for_user，路由到 handle_user_response 处理用户回答
    if current_step == "waiting_for_user":
        print(f"[DEBUG should_proceed] -> waiting_for_user, return handle_user_response")
        return "handle_user_response"

    # 如果正在执行中，直接继续执行
    if current_step in ("execute_transform", "execute_compress", "execute_concat", "execute_trim", "execute_condense", "execute_restore", "execute_info", "execute_editor"):
        print(f"[DEBUG should_proceed] -> executing node, return {current_step}")
        return current_step

    # 如果 current_step 是 analyze_intent，检查是否有待处理的用户回答
    # combined_input 存在说明是用户回答了 pending_question，需要先经过 handle_user_response 预解析
    if current_step == "analyze_intent":
        if state.get("combined_input"):
            print(f"[DEBUG should_proceed] -> handle_user_response (combined_input exists)")
            return "handle_user_response"
        # 有 pending_question 说明参数不完整，需要等待用户下一轮回答
        if pending_question:
            print(f"[DEBUG should_proceed] -> waiting_for_user (pending_question exists)")
            return "waiting_for_user"
        print(f"[DEBUG should_proceed] -> analyze_intent, return analyze_intent")
        return "analyze_intent"

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

    # 参数不完整时，如果有 pending_question，等待用户回答
    if pending_question:
        return "waiting_for_user"

    # 参数不完整，结束让用户补充
    return "confirm_complete"
