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


class OperationStep(TypedDict):
    """操作链中的单个步骤"""
    step_id: str
    feature: str
    step_name: str
    params: dict
    status: str  # pending / running / completed / failed
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_seconds: Optional[float]
    result: Optional[dict]
    error: Optional[str]


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
    editor_mode: Optional[str]  # highlight/subtitle/transition/bgm/tts/filter/analyze/cover/title-package
    editor_mode_explicit: bool
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
    # subtitle 参数
    subtitle_style: Optional[str]  # default/minimal
    subtitle_style_explicit: bool
    # bgm 参数
    bgm_mood: Optional[str]  # auto/happy/calm/energetic
    bgm_mood_explicit: bool
    bgm_volume: Optional[float]
    # tts 参数
    tts_voice: Optional[str]
    tts_text: Optional[str]
    # filter 参数
    filter_preset: Optional[str]  # none/vintage/cinematic/fresh/bw/warm/cold
    filter_preset_explicit: bool
    # cover 参数
    cover_mode: Optional[str]  # single/candidates
    cover_mode_explicit: bool
    # platform-check 参数
    platform: Optional[str]  # douyin/kuaishou/bilibili/xiaohongshu
    platform_explicit: bool
    # 流式消息队列（用于 SSE）
    message_queue: Optional[list]
    # 内部字段：用于在 handle_user_response 和 analyze_intent 之间传递合并输入
    combined_input: Optional[str]
    # 内部字段：用于从 process_video 向 handle_user_response 传递新用户输入
    new_user_input: Optional[str]
    # ========== 老视频修复参数 ==========
    restoration_preset: Optional[str]  # basic/film/enhanced
    restoration_preset_explicit: bool

    # ========== 剪映对接参数 ==========
    jianying_mode: Optional[str]  # subtitle/transition/both
    jianying_subtitle_style: Optional[str]  # default/minimal
    jianying_transition_type: Optional[str]  # 星光/叠化/模糊...
    jianying_transition_duration: Optional[int]  # 转场时长（毫秒）
    jianying_text_color: Optional[str]  # #FFFFFF
    jianying_font_size: Optional[int]  # 40
    jianying_font: Optional[str]  # 思源黑体
    jianying_draft_url: Optional[str]

    # ========== 操作链相关 ==========
    operation_chain: Optional[list[OperationStep]]  # 操作队列
    current_step_index: Optional[int]  # 当前执行到的步骤索引
    chain_status: Optional[str]  # idle / running / completed / failed
    operation_mode: Optional[str]  # "single" / "chain"
