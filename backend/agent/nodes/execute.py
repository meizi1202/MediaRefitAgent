"""
执行类 Node Functions

新增技能步骤：
1. 在 execute.py 添加 execute_xxx 函数
2. 在 analyze.py FEATURE_TO_STEP 添加 "xxx": "execute_xxx"
3. 在 routing.py FEATURE_TO_STEP 添加 "xxx": "execute_xxx"
4. 在 frontend/src/stores/app.ts formatSelectedParams() 添加参数格式化
"""
import json
from datetime import datetime
from pathlib import Path
import os

from agent.types import VideoAgentState, ConversationMessage
from agent.streaming import send_stream_chunk, send_stream_message, is_streaming_enabled
from video.transformer import transform, TransformRequest


def _append_message(state: VideoAgentState, role: str, content: str):
    """添加消息并发送流式消息"""
    msg = ConversationMessage(
        role=role,
        content=content,
        timestamp=datetime.now().isoformat(),
    )
    state["messages"].append(msg)
    # 发送流式消息（仅在启用流式模式时，使用分块发送）
    if is_streaming_enabled():
        send_stream_chunk(content)


def _make_progress_callback(label: str = ""):
    """生成统一的进度回调函数"""
    def progress_callback(progress: float):
        prefix = f"[DEBUG {label}] " if label else "[DEBUG] "
        msg = f"[PROGRESS:{int(progress * 100)}]"
        print(f"{prefix}{msg}")
        send_stream_message(msg)
    return progress_callback


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
        print(f"[DEBUG execute_transform] 开始转换, video_path={video_path}, output_path={output_path}")
        request = TransformRequest(
            input_path=video_path,
            output_path=output_path,
            target_orientation=state.get("target_orientation"),
            strategy=state.get("strategy", "pad"),
            target_ratio=state.get("target_ratio", 9/16),
        )

        progress_callback = _make_progress_callback("execute_transform")
        print(f"[DEBUG execute_transform] 调用 transform()...")
        result = transform(request, progress_callback=progress_callback)
        print(f"[DEBUG execute_transform] 转换完成, success={result.success}")
        state["transform_result"] = {
            "success": result.success,
            "input_path": result.input_path,
            "output_path": result.output_path,
            "original_orientation": result.original_orientation,
            "target_orientation": result.target_orientation,
            "strategy_used": result.strategy_used,
            "error": result.error,
        }
        state["current_step"] = "confirm_complete"

        if result.success:
            # 转换英文值为中文
            orientation_map = {"portrait": "竖屏", "landscape": "横屏", "square": "正方形"}
            strategy_map = {"pad": "填充黑边", "crop": "中心裁剪", "smart_crop": "智能裁剪", "stretch": "拉伸填充", "mirror_scroll": "镜像滚动", "pan_scroll": "平移运镜"}
            # 比例映射：float -> string
            ratio_map = {0.5625: "9:16", 0.8: "4:5", 1.0: "1:1", 1.7778: "16:9", 2.3333: "21:9", 1.3333: "4:3"}
            target_orientation_cn = orientation_map.get(result.target_orientation, result.target_orientation)
            target_ratio_raw = state.get("target_ratio")
            if target_ratio_raw:
                target_ratio = ratio_map.get(target_ratio_raw, str(target_ratio_raw))
            else:
                target_ratio = "未指定"
            strategy_used_cn = strategy_map.get(result.strategy_used, result.strategy_used)
            output_filename = Path(result.output_path).name

            _append_message(state, "assistant", f"转换完成！\n\n输出文件: {output_filename}\n目标方向: {target_orientation_cn}\n目标比例: {target_ratio}\n使用策略: {strategy_used_cn}\n[PREVIEW:{result.output_path}]")
        else:
            state["error"] = result.error
            _append_message(state, "assistant", f"转换失败: {result.error}")

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"转换异常: {str(e)}")

    return state


def execute_compress(state: VideoAgentState) -> VideoAgentState:
    """执行视频压缩"""
    print(f"[DEBUG execute_compress] CALLED, current_step={state.get('current_step')}")
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
        progress_callback = _make_progress_callback("execute_compress")
        compress_video(video_path, output_path, compression_level, progress_callback)

        # 获取文件大小信息
        original_size = os.path.getsize(video_path)
        compressed_size = os.path.getsize(output_path)

        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"压缩完成！\n\n原始大小: {original_size/1024/1024:.2f}MB\n压缩后: {compressed_size/1024/1024:.2f}MB\n压缩比: {compressed_size/original_size:.1%}\n[PREVIEW:{output_path}]")

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"压缩异常: {str(e)}")

    return state


def execute_trim(state: VideoAgentState) -> VideoAgentState:
    """执行视频修剪"""
    video_path = state.get("temp_video_path") or state.get("video_path")

    if not video_path:
        state["error"] = "视频文件不存在"
        state["current_step"] = "confirm_complete"
        return state

    start_time = state.get("start_time")
    end_time = state.get("end_time")

    if start_time is None or end_time is None:
        state["error"] = "修剪时间参数不完整"
        state["current_step"] = "confirm_complete"
        return state

    # 生成输出路径
    output_dir = Path("F:/video")
    output_dir.mkdir(exist_ok=True)
    input_name = Path(video_path).stem
    suffix = Path(video_path).suffix
    output_path = str(output_dir / f"trimmed_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    try:
        from video.processor import trim_video, get_video_metadata

        metadata = get_video_metadata(video_path)
        original_duration = metadata.duration
        original_size = os.path.getsize(video_path)

        progress_callback = _make_progress_callback("execute_trim")
        trim_video(video_path, output_path, start_time, end_time, progress_callback=progress_callback)

        trimmed_size = os.path.getsize(output_path)
        trimmed_duration = end_time - start_time

        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"视频修剪完成！\n\n原始时长: {original_duration:.1f}秒\n原始大小: {original_size/1024/1024:.2f}MB\n修剪后时长: {trimmed_duration:.1f}秒\n修剪后大小: {trimmed_size/1024/1024:.2f}MB\n开始时间: {start_time}秒\n结束时间: {end_time}秒\n[PREVIEW:{output_path}]")

        # 保存结果供预览使用
        state["trim_result"] = {
            "output_path": output_path,
            "original_duration": original_duration,
            "original_size": original_size,
            "trimmed_duration": trimmed_duration,
            "trimmed_size": trimmed_size,
            "start_time": start_time,
            "end_time": end_time,
        }

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"修剪异常: {str(e)}")

    return state


def execute_concat(state: VideoAgentState) -> VideoAgentState:
    """执行视频拼接"""
    video_path = state.get("temp_video_path") or state.get("video_path")

    if not video_path:
        state["error"] = "视频文件不存在"
        state["current_step"] = "confirm_complete"
        return state

    # 获取多文件列表
    video_files = state.get("video_files") or [video_path]
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

        keep_audio = state.get("keep_audio")
        progress_callback = _make_progress_callback("execute_concat")
        concat_videos(video_files, output_path, keep_audio=keep_audio, progress_callback=progress_callback)

        state["current_step"] = "confirm_complete"
        output_filename = Path(output_path).name
        _append_message(state, "assistant", f"拼接完成！\n\n输出文件: {output_filename}\n[PREVIEW:{output_path}]")

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"拼接异常: {str(e)}")

    return state


def execute_info(state: VideoAgentState) -> VideoAgentState:
    """获取视频信息"""
    video_path = state.get("temp_video_path") or state.get("video_path")

    if not video_path:
        state["error"] = "视频文件不存在"
        state["current_step"] = "confirm_complete"
        return state

    try:
        from video.processor import get_video_metadata

        metadata = get_video_metadata(video_path)
        file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0

        # 构建视频信息文本
        info_text = f"""视频信息：
- 分辨率：{metadata.width} × {metadata.height}
- 时长：{metadata.duration:.1f} 秒
- 文件大小：{file_size / 1024 / 1024:.1f} MB
- 帧率：{metadata.fps:.1f} fps"""

        if hasattr(metadata, 'bitrate') and metadata.bitrate:
            info_text += f"\n- 码率：{metadata.bitrate} kbps"

        msg = ConversationMessage(
            role="assistant",
            content=info_text,
            timestamp=datetime.now().isoformat(),
        )
        _append_message(state, "assistant", info_text)

        # 保存视频信息到 state
        state["video_info"] = {
            "width": metadata.width,
            "height": metadata.height,
            "duration": metadata.duration,
            "fps": metadata.fps,
            "file_size": file_size,
        }

        state["current_step"] = "confirm_complete"

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"获取视频信息异常: {str(e)}")

    return state


def execute_condense(state: VideoAgentState) -> VideoAgentState:
    """执行智能缩编"""
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
    output_path = str(output_dir / f"condensed_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    try:
        from video.condenser import condense_video

        target_duration = state.get("target_duration", 60)
        _cb = _make_progress_callback("execute_condense")
        result = condense_video(
            video_path, output_path,
            target_duration=target_duration,
            progress_callback=lambda p, s="": _cb(p)
        )

        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"智能缩编完成！\n\n输出文件: {output_path}\n目标时长: {target_duration}秒")

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"智能缩编异常: {str(e)}")

    return state


def execute_restore(state: VideoAgentState) -> VideoAgentState:
    """执行老视频修复"""
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
    output_path = str(output_dir / f"restored_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    try:
        from video.processor import restore_video

        progress_callback = _make_progress_callback("execute_restore")
        # 基础修复选项（不需要高级滤镜）
        success = restore_video(
            video_path, output_path,
            color_correct=True,
            saturation=1.1,
            contrast=1.05,
            progress_callback=progress_callback
        )

        state["current_step"] = "confirm_complete"
        if success:
            _append_message(state, "assistant", f"老视频修复完成！\n\n输出文件: {output_path}")
        else:
            _append_message(state, "assistant", f"老视频修复失败")

    except Exception as e:
        error_msg = str(e)
        state["error"] = error_msg
        state["current_step"] = "confirm_complete"
        # 如果是FFmpeg滤镜问题，提供友好提示
        if "Option not found" in error_msg or "filter" in error_msg.lower():
            _append_message(state, "assistant", f"老视频修复失败：当前FFmpeg版本不支持部分高级滤镜。建议使用完整版FFmpeg。")
        else:
            _append_message(state, "assistant", f"老视频修复异常: {error_msg}")

    return state


def execute_editor(state: VideoAgentState) -> VideoAgentState:
    """执行智能剪辑"""
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
    output_path = str(output_dir / f"edited_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    try:
        from video.processor import trim_video, get_video_metadata

        target_duration = state.get("target_duration", 60)
        progress_callback = _make_progress_callback("execute_editor")
        # 简单处理：直接trim到目标时长
        metadata = get_video_metadata(video_path)
        if metadata.duration > target_duration:
            start_time = 0
            end_time = target_duration
            trim_video(video_path, output_path, start_time, end_time, progress_callback=progress_callback)
        else:
            # 时长不足，直接复制
            import shutil
            shutil.copy(video_path, output_path)

        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"智能剪辑完成！\n\n输出文件: {output_path}\n目标时长: {target_duration}秒")

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"智能剪辑异常: {str(e)}")

    return state


def confirm_complete(state: VideoAgentState) -> VideoAgentState:
    """确认完成"""
    # pending_question 由 handle_user_response 清除，不要在这里清除
    return state
