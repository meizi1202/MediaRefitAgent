"""
视频检测 Node
"""
from datetime import datetime
from pathlib import Path

from agent.types import VideoAgentState, ConversationMessage
from agent.streaming import send_stream_chunk, is_streaming_enabled
from ml.orientation_detector import detect_orientation


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

        # 只在横竖屏转换时显示视频方向信息
        if state.get("current_feature") in (None, "convert", "orient"):
            _append_message(state, "assistant", f"检测到视频是{orientation_display}的。")

        # 如果有待回答的问题，跳过执行让用户补充参数
        if state.get("pending_question"):
            state["current_step"] = "waiting_for_user"
            return state

        # 只有 convert 类型才需要走 select_strategy，其他功能直接执行
        if state.get("current_feature") in (None, "convert"):
            state["current_step"] = "select_strategy"
        elif state.get("current_feature") == "info":
            state["current_step"] = "execute_info"
        elif state.get("current_feature") == "compress":
            state["current_step"] = "execute_compress"
        elif state.get("current_feature") == "trim":
            state["current_step"] = "execute_trim"
        elif state.get("current_feature") == "concat":
            state["current_step"] = "execute_concat"
        elif state.get("current_feature") == "condense":
            state["current_step"] = "execute_condense"
        elif state.get("current_feature") == "restore":
            state["current_step"] = "execute_restore"
        elif state.get("current_feature") == "editor":
            state["current_step"] = "execute_editor"

    except Exception as e:
        state["error"] = f"方向检测失败: {str(e)}"
        state["current_step"] = "confirm_complete"

    return state
