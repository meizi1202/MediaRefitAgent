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
from video.restoration import RestorationRequest


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
    def progress_callback(progress: float, message: str = ""):
        prefix = f"[DEBUG {label}] " if label else "[DEBUG] "
        msg = f"[PROGRESS:{int(progress * 100)}]"
        print(f"{prefix}{msg} {message}")
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
    print(f"[DEBUG execute_condense] === ENTER ===")
    print(f"[DEBUG execute_condense] strategy={state.get('strategy')}, target_duration={state.get('target_duration')}")

    video_path = state.get("temp_video_path") or state.get("video_path")
    strategy = state.get("strategy")
    target_duration = state.get("target_duration")

    if not video_path:
        state["error"] = "视频文件不存在"
        state["current_step"] = "confirm_complete"
        return state

    if not strategy or not target_duration:
        missing = []
        if not strategy:
            missing.append("缩编策略")
        if not target_duration:
            missing.append("目标时长")
        state["error"] = f"缺少必要参数：{'、'.join(missing)}"
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"智能缩编参数不完整，请补充：{'、'.join(missing)}")
        return state

    # 生成输出路径
    output_dir = Path("F:/video")
    output_dir.mkdir(exist_ok=True)
    input_name = Path(video_path).stem
    suffix = Path(video_path).suffix
    output_path = str(output_dir / f"condensed_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    try:
        from video.condenser import condense_video

        progress_callback = _make_progress_callback("execute_condense")
        print(f"[DEBUG execute_condense] 调用 condense_video()...")

        result = condense_video(
            video_path, output_path,
            strategy=strategy,
            target_duration=target_duration,
            progress_callback=progress_callback
        )

        state["current_step"] = "confirm_complete"
        if result.success:
            strategy_names = {
                "content_condense": "内容缩编",
                "smart_compress": "智能压缩",
                "smart_crop": "智能裁剪",
            }
            strategy_text = strategy_names.get(strategy, strategy)
            output_filename = Path(result.output_path).name
            ratio = result.duration_before / result.duration_after if result.duration_after > 0 else 0
            _append_message(state, "assistant", f"智能缩编完成！\n\n缩编策略: {strategy_text}\n原始时长: {result.duration_before:.1f}秒\n缩编后: {result.duration_after:.1f}秒\n压缩比: {ratio:.1f}x\n输出文件: {output_filename}\n[PREVIEW:{result.output_path}]")
        else:
            _append_message(state, "assistant", f"智能缩编失败: {result.error}")

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"智能缩编异常: {str(e)}")

    return state


def execute_restore(state: VideoAgentState) -> VideoAgentState:
    """执行老视频修复"""
    video_path = state.get("temp_video_path") or state.get("video_path")
    preset = state.get("restoration_preset", "basic")
    print(f"[DEBUG execute_restore] restoration_preset from state={state.get('restoration_preset')}, preset={preset}")

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
        from video.restoration import (
            RestorationPreset as RestPreset,
            get_default_options_for_preset,
        )
        from video.restoration_pipeline import RestorationPipeline

        preset_enum = RestPreset(preset) if preset in [p.value for p in RestPreset] else RestPreset.BASIC
        print(f"[DEBUG execute_restore] preset_enum={preset_enum}, input={video_path}, output={output_path}")

        # 进度回调
        def progress_callback(stage: str, progress: float):
            msg = f"[PROGRESS:{int(progress * 100)}]"
            send_stream_message(msg)

        request = RestorationRequest(
            input_path=video_path,
            output_path=output_path,
            preset=preset_enum,
            options=get_default_options_for_preset(preset_enum),
            progress_callback=progress_callback,
        )

        result = RestorationPipeline(request).run()
        print(f"[DEBUG execute_restore] pipeline done, success={result.success}, error={result.error}, stages={len(result.stages) if result.stages else 0}")

        state["current_step"] = "confirm_complete"
        if result.success:
            preset_names = {"basic": "基础修复", "film": "胶片修复", "enhanced": "增强版"}
            preset_text = preset_names.get(preset, preset)
            stage_count = len(result.stages) if result.stages else 0
            _append_message(state, "assistant", f"{preset_text}完成！\n\n套餐: {preset_text}\n处理时长: {result.total_duration:.1f}秒\n处理阶段: {stage_count}个\n[PREVIEW:{result.output_path}]")
        else:
            _append_message(state, "assistant", f"老视频修复失败: {result.error}")

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

    editor_mode = state.get("editor_mode", "highlight")

    # 生成输出路径
    output_dir = Path("F:/video")
    output_dir.mkdir(exist_ok=True)
    input_name = Path(video_path).stem
    suffix = Path(video_path).suffix

    mode_names = {
        "highlight": "精彩片段", "subtitle": "自动字幕", "transition": "添加转场",
        "bgm": "智能配乐", "tts": "配音", "filter": "滤镜",
        "analyze": "内容分析", "cover": "封面生成", "title-package": "片头片尾",
    }
    mode_text = mode_names.get(editor_mode, "智能剪辑")

    try:
        if editor_mode == "highlight":
            return _execute_editor_highlight(state, video_path, output_dir, input_name, suffix, mode_text)
        elif editor_mode == "subtitle":
            return _execute_editor_subtitle(state, video_path, output_dir, input_name, suffix, mode_text)
        elif editor_mode == "transition":
            return _execute_editor_transition(state, video_path, output_dir, input_name, suffix, mode_text)
        elif editor_mode == "bgm":
            return _execute_editor_bgm(state, video_path, output_dir, input_name, suffix, mode_text)
        elif editor_mode == "filter":
            return _execute_editor_filter(state, video_path, output_dir, input_name, suffix, mode_text)
        elif editor_mode == "analyze":
            return _execute_editor_analyze(state, video_path, mode_text)
        elif editor_mode == "cover":
            return _execute_editor_cover(state, video_path, output_dir, input_name, suffix, mode_text)
        elif editor_mode == "title-package":
            return _execute_editor_title_package(state, video_path, output_dir, input_name, suffix, mode_text)
        elif editor_mode == "tts":
            return _execute_editor_tts(state, video_path, output_dir, input_name, suffix, mode_text)
        else:
            state["current_step"] = "confirm_complete"
            _append_message(state, "assistant", f"不支持的剪辑模式：{mode_text}")
            return state

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"智能剪辑异常: {str(e)}")
        return state


def _execute_editor_highlight(state, video_path, output_dir, input_name, suffix, mode_text) -> VideoAgentState:
    """精彩片段模式"""
    from video.processor import trim_video, get_video_metadata, generate_subtitle_from_video

    target_duration = state.get("target_duration", 60)
    subtitle_style = state.get("subtitle_style", "default")
    progress_callback = _make_progress_callback("execute_editor")
    output_path = str(output_dir / f"highlight_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    metadata = get_video_metadata(video_path)
    if metadata.duration > target_duration:
        # 先 trim 到目标时长
        print(f"[DEBUG _execute_editor_highlight] trimming to {target_duration}s")
        trim_output = str(output_dir / f"highlight_trim_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")
        trim_video(video_path, trim_output, 0, target_duration, progress_callback=None)
        print(f"[DEBUG _execute_editor_highlight] trim done, generating subtitle")
        # 生成并烧录字幕
        subtitle_output = str(output_dir / f"highlight_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt")
        result = generate_subtitle_from_video(
            trim_output,
            subtitle_output,
            style=subtitle_style,
            burn_in=True,
            remove_filler=True,
            progress_callback=progress_callback,
        )
        print(f"[DEBUG _execute_editor_highlight] subtitle result: {result}")
        if result["success"] and result.get("output_path"):
            output_path = result["output_path"]
        else:
            output_path = trim_output
    else:
        import shutil
        shutil.copy(video_path, output_path)

    state["current_step"] = "confirm_complete"
    _append_message(state, "assistant", f"{mode_text}完成！\n\n输出文件: {output_path}\n目标时长: {target_duration}秒\n[PREVIEW:{output_path}]")
    return state


def _execute_editor_subtitle(state, video_path, output_dir, input_name, suffix, mode_text) -> VideoAgentState:
    """自动字幕模式"""
    from video.processor import generate_subtitle_from_video

    output_path = str(output_dir / f"subtitle_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt")
    subtitle_style = state.get("subtitle_style", "default")
    progress_callback = _make_progress_callback("execute_editor")

    try:
        result = generate_subtitle_from_video(
            video_path,
            output_path,
            style=subtitle_style,
            burn_in=True,
            remove_filler=True,
            progress_callback=progress_callback,
        )
        state["current_step"] = "confirm_complete"
        if result["success"]:
            sub_path = result.get("subtitle_path", output_path)
            vid_path = result.get("output_path")
            msg = f"{mode_text}完成！\n\n字幕文件: {sub_path}"
            if vid_path:
                msg += f"\n输出文件: {vid_path}\n[PREVIEW:{vid_path}]"
            _append_message(state, "assistant", msg)
        else:
            _append_message(state, "assistant", f"{mode_text}处理失败: {result.get('error', '未知错误')}")
    except Exception as e:
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"{mode_text}处理失败: {str(e)}")
    return state


def _execute_editor_transition(state, video_path, output_dir, input_name, suffix, mode_text) -> VideoAgentState:
    """添加转场模式"""
    raw_type = state.get("transition_type", "fade")
    # 中文字段值 -> FFmpeg 值
    type_map = {"淡入淡出": "fade", "滑动": "slide", "缩放": "zoom", "模糊": "blur"}
    transition_type = type_map.get(raw_type, raw_type)  # 已是英文值时直接用

    output_path = str(output_dir / f"transition_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    from video.processor import add_transition
    result = add_transition(video_path, output_path, transition_type=transition_type)

    state["current_step"] = "confirm_complete"
    trans_names = {"fade": "淡入淡出", "slide": "滑动", "zoom": "缩放", "blur": "模糊"}
    if not result.get("success"):
        _append_message(state, "assistant", f"{mode_text}失败: {result.get('message', '未知错误')}")
        return state

    _append_message(state, "assistant", f"{mode_text}完成！\n\n转场类型: {trans_names.get(transition_type, transition_type)}\n输出文件: {output_path}\n[PREVIEW:{output_path}]")
    return state


def _execute_editor_bgm(state, video_path, output_dir, input_name, suffix, mode_text) -> VideoAgentState:
    """智能配乐模式"""
    bgm_mood = state.get("bgm_mood", "auto")
    bgm_volume = state.get("bgm_volume", 0.5)
    output_path = str(output_dir / f"bgm_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    from video.bgm import find_matching_bgm, add_bgm_to_video

    # 查找匹配的音乐
    bgm_info = find_matching_bgm(mood=bgm_mood)
    if not bgm_info:
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"{mode_text}失败：未找到匹配的音乐文件。请在音乐库目录中添加音乐文件。")
        return state

    bgm_path = bgm_info["path"]
    success = add_bgm_to_video(video_path, bgm_path, output_path, video_volume=0.3, bgm_volume=bgm_volume)

    state["current_step"] = "confirm_complete"
    mood_names = {"auto": "自动", "happy": "欢快", "calm": "平静", "energetic": "动感"}
    if success:
        _append_message(state, "assistant", f"{mode_text}完成！\n\n音乐风格: {mood_names.get(bgm_mood, bgm_mood)}\nBGM文件: {bgm_info['name']}\n输出文件: {output_path}\n[PREVIEW:{output_path}]")
    else:
        _append_message(state, "assistant", f"{mode_text}失败，请检查音乐文件格式是否支持。")
    return state


def _execute_editor_filter(state, video_path, output_dir, input_name, suffix, mode_text) -> VideoAgentState:
    """滤镜模式"""
    filter_preset = state.get("filter_preset", "none")
    output_path = str(output_dir / f"filtered_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    from video.filter import VideoFilter
    success = VideoFilter.apply_filter(video_path, output_path, preset=filter_preset)

    if not success:
        state["error"] = "滤镜处理失败"
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"{mode_text}失败，请检查视频格式是否支持该滤镜。")
        return state

    state["current_step"] = "confirm_complete"
    filter_names = {"none": "无", "vintage": "复古", "cinematic": "电影感", "fresh": "清新", "bw": "黑白", "warm": "暖色", "cold": "冷色"}
    _append_message(state, "assistant", f"{mode_text}完成！\n\n滤镜预设: {filter_names.get(filter_preset, filter_preset)}\n输出文件: {output_path}\n[PREVIEW:{output_path}]")
    return state


def _execute_editor_analyze(state, video_path, mode_text) -> VideoAgentState:
    """内容分析模式"""
    from video.video_analysis import analyze_video_content

    result = analyze_video_content(video_path)
    state["current_step"] = "confirm_complete"

    scene = result.get("scene", "未知")
    emotion = result.get("emotion", "未知")
    platforms = result.get("suitable_platforms", [])
    platform_names = {"douyin": "抖音", "kuaishou": "快手", "bilibili": "B站", "xiaohongshu": "小红书"}
    platforms_cn = [platform_names.get(p, p) for p in platforms]

    msg = f"{mode_text}完成！\n\n场景: {scene}\n情绪: {emotion}\n适合平台: {', '.join(platforms_cn) if platforms_cn else '未知'}"
    _append_message(state, "assistant", msg)
    return state


def _execute_editor_cover(state, video_path, output_dir, input_name, suffix, mode_text) -> VideoAgentState:
    """封面生成模式"""
    output_path = str(output_dir / f"cover_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")

    from video.video_analysis import CoverGenerator
    result = CoverGenerator.extract_cover_frame(video_path, output_path)

    state["current_step"] = "confirm_complete"
    if result:
        _append_message(state, "assistant", f"{mode_text}完成！\n\n封面文件: {output_path}\n[PREVIEW:{output_path}]")
    else:
        _append_message(state, "assistant", f"{mode_text}失败，请检查视频格式是否支持。")
    return state


def _execute_editor_title_package(state, video_path, output_dir, input_name, suffix, mode_text) -> VideoAgentState:
    """片头片尾模式"""
    import tempfile
    from video.video_analysis import TitleGenerator

    # 创建临时片头文件
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        opening_path = tmp.name

    try:
        # 生成片头
        opening_ok = TitleGenerator.create_opening(opening_path)
        if not opening_ok:
            raise Exception("片头生成失败")

        # 将片头添加到原视频
        output_path = str(output_dir / f"titled_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")
        concat_ok = TitleGenerator.add_opening_to_video(video_path, output_path, opening_path)
        if not concat_ok:
            raise Exception("片头添加失败")
    except Exception as e:
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"{mode_text}失败: {str(e)}")
        return state
    finally:
        # 清理临时文件
        import os
        if os.path.exists(opening_path):
            os.remove(opening_path)

    state["current_step"] = "confirm_complete"
    _append_message(state, "assistant", f"{mode_text}完成！\n\n输出文件: {output_path}\n[PREVIEW:{output_path}]")
    return state


def _execute_editor_tts(state, video_path, output_dir, input_name, suffix, mode_text) -> VideoAgentState:
    """配音模式"""
    tts_text = state.get("tts_text")
    tts_voice = state.get("tts_voice", "zh-CN-Xiaoxiao")
    tts_volume = state.get("tts_volume", 1.0)
    original_volume = state.get("original_volume", 0.3)

    if not tts_text:
        state["error"] = "配音文本为空"
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", "请提供配音文本")
        return state

    output_path = str(output_dir / f"tts_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    try:
        from video.tts import add_tts_to_video

        progress_callback = _make_progress_callback("execute_editor")
        success = add_tts_to_video(
            video_path=video_path,
            text=tts_text,
            output_path=output_path,
            voice=tts_voice,
            tts_volume=tts_volume,
            original_volume=original_volume,
            progress_callback=progress_callback
        )

        state["current_step"] = "confirm_complete"
        if success:
            voice_names = {
                "zh-CN-XiaoxiaoNeural": "晓晓（女声）",
                "zh-CN-XiaoyiNeural": "小艺（女声）",
                "zh-CN-YunxiNeural": "云希（男声）",
                "zh-CN-YunyangNeural": "云扬（男声）",
                "zh-CN-liaoning": "辽宁（男声）",
                "zh-CN-shaanxi": "陕西（男声）",
                "en-US-JennyNeural": "Jenny（英文女声）",
                "en-US-GuyNeural": "Guy（英文男声）",
                "en-GB-SoniaNeural": "Sonia（英式女声）",
                # 兼容旧版（无 Neural 后缀）
                "zh-CN-Xiaoxiao": "晓晓（女声）",
                "zh-CN-Xiaoyi": "小艺（女声）",
                "zh-CN-Yunxi": "云希（男声）",
                "zh-CN-Yunyang": "云扬（男声）",
                "en-US-Jenny": "Jenny（英文女声）",
                "en-US-Guy": "Guy（英文男声）",
                "en-GB-Sonia": "Sonia（英式女声）",
            }
            voice_text = voice_names.get(tts_voice, tts_voice)
            _append_message(state, "assistant", f"{mode_text}完成！\n\n配音音色: {voice_text}\n配音文本: {tts_text[:50]}{'...' if len(tts_text) > 50 else ''}\n输出文件: {output_path}\n[PREVIEW:{output_path}]")
        else:
            _append_message(state, "assistant", f"{mode_text}失败，请检查配音文本和音色参数。")

    except Exception as e:
        state["error"] = str(e)
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"{mode_text}异常: {str(e)}")

    return state


def confirm_complete(state: VideoAgentState) -> VideoAgentState:
    """确认完成"""
    # pending_question 由 handle_user_response 清除，不要在这里清除
    return state
