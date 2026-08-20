"""
共享类型定义

VideoAgentState、ConversationMessage 等类型在多个模块间共享，
因此单独放在一个文件中避免循环导入。
"""
from typing import TypedDict, Optional


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
    current_feature: Optional[str]  # 当前功能类型: convert/compress/trim/concat
    messages: list[ConversationMessage]
    transform_result: Optional[dict]
    error: Optional[str]
    # 多轮对话支持
    session_id: Optional[str]
    history: list[ConversationMessage]
    pending_question: Optional[str]  # 等待用户回答的问题
    # 压缩参数
    compression_level: Optional[str]
    compression_explicit: bool
    # 修剪参数
    start_time: Optional[float]
    end_time: Optional[float]
    start_time_explicit: bool
    end_time_explicit: bool
    # 拼接参数
    keep_audio: bool
    concat_explicit: bool
    # 修剪结果
    trim_result: Optional[dict]
    # ========== 智能剪辑参数 ==========
    # highlight 参数
    target_duration: Optional[int]  # 目标时长（秒）
    target_duration_explicit: bool
    num_clips: Optional[int]  # 片段数量
    num_clips_explicit: bool
    # transition 参数
    transition_type: Optional[str]  # fade/slide/zoom/blur/rotate/dissolve
    transition_type_explicit: bool
    transition_duration: Optional[float]  # 转场时长（秒）
    transition_duration_explicit: bool
