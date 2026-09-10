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
import math

from agent.types import VideoAgentState, ConversationMessage


def _format_ratio(ratio: float) -> str:
    """将浮点比例格式化为字符串格式（如 16:9）"""
    if ratio is None:
        return "未指定"
    # 用 round 避免浮点精度问题，然后比较差值
    ratio = round(ratio, 4)
    ratio_map = [
        (0.5625, "9:16"),   # 竖屏
        (0.8, "4:5"),
        (1.0, "1:1"),
        (1.3333, "4:3"),
        (1.7778, "16:9"),   # 横屏
        (2.3333, "21:9"),
    ]
    for val, label in ratio_map:
        if abs(ratio - val) < 0.01:
            return label
    # 无法识别，返回原始值
    return str(round(ratio, 2))
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
        msg = f"[PROGRESS:{int(progress * 100)}]"
        print(f"[DEBUG _make_progress_callback] {label} sending: {msg}")
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
            # 更新 temp_video_path 供后续操作使用
            state["temp_video_path"] = result.output_path

            # 转换英文值为中文
            orientation_map = {"portrait": "竖屏", "landscape": "横屏", "square": "正方形"}
            strategy_map = {
                "pad": "填充黑边",
                "crop": "中心裁剪",
                "smart_crop": "智能裁剪",
                "stretch": "拉伸填充",
                "mirror_scroll": "镜像滚动",
                "pan_scroll": "平移运镜",
                "rotate_0": "无需旋转",
                "none (already target orientation)": "无需转换（已是目标方向）",
            }
            target_orientation_cn = orientation_map.get(result.target_orientation, result.target_orientation)
            target_ratio_raw = state.get("target_ratio")
            target_ratio = _format_ratio(target_ratio_raw)
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

        # 更新 temp_video_path 供后续操作使用
        state["temp_video_path"] = output_path

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
    print(f"[DEBUG execute_trim] video_path={video_path}, temp_video_path={state.get('temp_video_path')}")

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

        # 更新 temp_video_path 供后续操作使用
        state["temp_video_path"] = output_path

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


def execute_jianying(state: VideoAgentState) -> VideoAgentState:
    """执行剪映对接 - 添加字幕/转场场景"""
    print(f"[DEBUG execute_jianying] === ENTER ===")

    try:
        from jianying.client import JianyingClient
        from jianying.models import CreateDraftRequest, VideoInfo, CaptionInfo, WordInfo, AddVideosRequest, AddCaptionsRequest, SaveDraftRequest
        from video.summary import VideoSummarizer as Transcriber
        import datetime
        import shutil
        from pathlib import Path

        # 获取视频文件列表
        video_files = state.get("video_files", [])
        single_video_path = state.get("temp_video_path") or state.get("video_path")
        if not video_files and single_video_path:
            video_files = [single_video_path]
        if not video_files:
            raise ValueError("视频文件不存在")

        print(f"[DEBUG execute_jianying] video_files count: {len(video_files)}")

        # Step 0: 将所有视频复制到草稿目录
        jianying_client = JianyingClient()
        draft_video_dir = jianying_client.draft_dir / "_videos"
        draft_video_dir.mkdir(parents=True, exist_ok=True)
        draft_video_paths = []
        for i, video_path in enumerate(video_files):
            video_suffix = Path(video_path).suffix
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            draft_video_path = draft_video_dir / f"{timestamp}_{i}{video_suffix}"
            shutil.copy2(video_path, draft_video_path)
            draft_video_paths.append(str(draft_video_path))
        print(f"[DEBUG execute_jianying] videos copied: {draft_video_paths}")

        # 获取模式
        jianying_mode = state.get("jianying_mode", "subtitle")
        print(f"[DEBUG execute_jianying] mode: {jianying_mode}")
        print(f"[DEBUG execute_jianying] state keys: {[k for k in state.keys() if 'jianying' in k or 'transition' in k]}")
        print(f"[DEBUG execute_jianying] state values: {[(k, state[k]) for k in state.keys() if 'jianying' in k or 'transition' in k]}")

        # 字幕参数
        text_color = state.get("jianying_text_color", "#FFFFFF")
        font_size = state.get("jianying_font_size", 10)
        font = state.get("jianying_font", "思源黑体")

        # 转场参数
        transition_type = state.get("jianying_transition_type", "")
        transition_duration = state.get("jianying_transition_duration", 500)

        _append_message(state, "assistant", "开始处理：获取视频信息...")
        from video.processor import get_video_metadata

        # 使用第一个视频的分辨率作为草稿分辨率
        primary_video_path = draft_video_paths[0]
        metadata = get_video_metadata(primary_video_path)
        width = metadata.width
        height = metadata.height
        print(f"[DEBUG execute_jianying] video info: {width}x{height}, duration={metadata.duration}")

        # Step 1: 创建剪映草稿
        _append_message(state, "assistant", "正在创建剪映草稿...")
        client = JianyingClient()
        create_request = CreateDraftRequest(width=width, height=height)
        create_response = client.create_draft(create_request)
        draft_url = create_response.draft_url
        print(f"[DEBUG execute_jianying] draft created: {draft_url}")

        # Step 2: 添加视频到草稿（按顺序排列，时间轴不重叠）
        _append_message(state, "assistant", "正在添加视频到草稿...")
        print(f"[DEBUG execute_jianying] transition_type={transition_type}, transition_duration={transition_duration}, video_count={len(draft_video_paths)}")
        video_info_list = []
        current_start_us = 0
        for i, draft_video_path in enumerate(draft_video_paths):
            video_meta = get_video_metadata(draft_video_path)
            video_duration_us = int(video_meta.duration * 1_000_000)
            # 最后一个视频不加转场
            has_transition = transition_type and i < len(draft_video_paths) - 1
            video_info = VideoInfo(
                video_url=draft_video_path,
                start=current_start_us,
                end=current_start_us + video_duration_us,
                transition=transition_type if has_transition else None,
                transition_duration=transition_duration * 1000 if has_transition else None,
            )
            print(f"[DEBUG execute_jianying] video[{i}] has_transition={has_transition}, transition={transition_type if has_transition else None}")
            video_info_list.append(video_info)
            current_start_us += video_duration_us
        add_video_request = AddVideosRequest(
            draft_url=draft_url,
            videos=video_info_list,
        )
        add_video_response = client.add_videos(add_video_request)
        print(f"[DEBUG execute_jianying] videos added: {add_video_response}")

        caption_count = 0

        # Step 3: 添加字幕（仅字幕模式或两者模式）
        if jianying_mode in ("subtitle", "both"):
            _append_message(state, "assistant", "正在进行语音识别...")
            transcriber = Transcriber(llm_client=None)
            all_caption_infos = []
            # 对每个视频分别做语音识别，时间轴累加偏移
            current_time_offset_us = 0
            for i, draft_video_path in enumerate(draft_video_paths):
                print(f"[DEBUG execute_jianying] transcribing video[{i}]: {draft_video_path}")
                whisper_result = transcriber.transcribe_video(draft_video_path)
                if not whisper_result:
                    print(f"[DEBUG execute_jianying] video[{i}] whisper failed, skipping")
                    # 累加时间偏移以便下一视频时间轴正确
                    video_meta = get_video_metadata(draft_video_path)
                    current_time_offset_us += int(video_meta.duration * 1_000_000)
                    continue

                segments = whisper_result.get("segments", [])
                print(f"[DEBUG execute_jianying] video[{i}] whisper found {len(segments)} segments, offset={current_time_offset_us}")

                for seg in segments:
                    start_us = int(seg["start"] * 1_000_000) + current_time_offset_us
                    end_us = int(seg["end"] * 1_000_000) + current_time_offset_us
                    words = None
                    if "words" in seg and seg["words"]:
                        words = [WordInfo(word=w["word"], start=w["start"] + current_time_offset_us / 1_000_000, end=w["end"] + current_time_offset_us / 1_000_000) for w in seg["words"]]
                    all_caption_infos.append(CaptionInfo(
                        text=seg["text"],
                        start=start_us,
                        end=end_us,
                        words=words,
                    ))

                video_meta = get_video_metadata(draft_video_path)
                current_time_offset_us += int(video_meta.duration * 1_000_000)

            print(f"[DEBUG execute_jianying] total caption segments: {len(all_caption_infos)}")
            _append_message(state, "assistant", f"正在添加字幕（共 {len(all_caption_infos)} 条）...")

            add_caption_request = AddCaptionsRequest(
                draft_url=draft_url,
                captions=all_caption_infos,
                text_color=text_color,
                font_size=font_size,
                font=font,
                char_level_highlight=False,
            )
            add_caption_response = client.add_captions(add_caption_request)
            print(f"[DEBUG execute_jianying] captions added: {add_caption_response}")
            caption_count = len(all_caption_infos)

        # Step 4: 保存草稿
        _append_message(state, "assistant", "正在保存草稿...")
        save_request = SaveDraftRequest(draft_url=draft_url)
        client.save_draft(save_request)

        # 保存结果到 state
        state["jianying_draft_url"] = draft_url
        state["caption_count"] = caption_count

        # 构建响应文本
        mode_desc = {"subtitle": "字幕", "transition": "转场", "both": "字幕+转场"}.get(jianying_mode, "字幕")
        response_text = f"""剪映草稿创建成功！

📐 分辨率：{width} × {height}
🎬 {mode_desc}已添加
🔗 草稿链接：{draft_url}

请在剪映客户端中打开上述链接进行编辑。"""

        _append_message(state, "assistant", response_text)
        state["current_step"] = "confirm_complete"

    except Exception as e:
        error_msg = str(e)
        print(f"[DEBUG execute_jianying] error: {error_msg}")
        state["error"] = error_msg
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"剪映对接异常: {error_msg}")

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
    # 中文情绪名转英文 key（UI 传入中文时需要映射）
    mood_map = {"自动": "auto", "欢快": "happy", "平静": "calm", "动感": "energetic", "悲伤": "sad", "史诗": "epic", "商务": "corporate"}
    if bgm_mood in mood_map:
        bgm_mood = mood_map[bgm_mood]
    bgm_volume = state.get("bgm_volume", 0.5)
    print(f"[DEBUG BGM] bgm_volume from state: {bgm_volume}, state keys: {list(state.keys())}")
    output_path = str(output_dir / f"bgm_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")

    from video.bgm import find_matching_bgm, add_bgm_to_video
    from settings import MUSIC_LIBRARY_DIR

    # 查找匹配的音乐
    bgm_info = find_matching_bgm(mood=bgm_mood, music_dir=MUSIC_LIBRARY_DIR)
    if not bgm_info:
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"{mode_text}失败：未找到匹配的音乐文件。请在音乐库目录中添加音乐文件。")
        return state

    bgm_path = bgm_info["path"]
    success = add_bgm_to_video(video_path, bgm_path, output_path, video_volume=0.7, bgm_volume=bgm_volume)

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
    from video.video_analysis import CoverGenerator

    # 根据封面模式确定提取数量：单张=1，多张候选=5
    cover_mode = state.get("cover_mode", "single")
    num_candidates = 1 if cover_mode == "single" else 5

    # 提取封面
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_paths = CoverGenerator.extract_cover_frames(video_path, output_dir, input_name, timestamp, num_candidates=num_candidates)

    state["current_step"] = "confirm_complete"
    if output_paths:
        preview_tags = ''.join([f"[PREVIEW:{p}]" for p in output_paths])
        _append_message(state, "assistant", f"{mode_text}完成！\n{preview_tags}")
    else:
        _append_message(state, "assistant", f"{mode_text}失败，请检查视频格式是否支持。")
    return state


def _execute_editor_title_package(state, video_path, output_dir, input_name, suffix, mode_text) -> VideoAgentState:
    """片头片尾模式"""
    import tempfile
    import subprocess
    from video.video_analysis import TitleGenerator

    progress_callback = _make_progress_callback("execute_editor")

    # 获取原视频分辨率
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=width,height', '-of',
             'csv=p=0', video_path],
            capture_output=True, text=True, check=True
        )
        w, h = result.stdout.strip().split(',')
        width, height = int(w), int(h)
        progress_callback(0.1, "获取视频分辨率完成")
    except Exception as e:
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"无法获取视频分辨率: {str(e)}")
        return state

    # 创建临时片头和片尾文件
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_opening:
        opening_path = tmp_opening.name
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_ending:
        ending_path = tmp_ending.name

    try:
        # 生成片头
        progress_callback(0.15, "正在生成片头...")
        opening_ok = TitleGenerator.create_opening(opening_path, width=width, height=height)
        if not opening_ok:
            raise Exception("片头生成失败")
        progress_callback(0.3, "片头生成完成")

        # 生成片尾
        progress_callback(0.4, "正在生成片尾...")
        ending_ok = TitleGenerator.create_ending(ending_path, width=width, height=height)
        if not ending_ok:
            raise Exception("片尾生成失败")
        progress_callback(0.55, "片尾生成完成")

        # 合并片头+视频+片尾
        output_path = str(output_dir / f"titled_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")
        progress_callback(0.65, "正在添加片头片尾...")
        concat_ok = TitleGenerator.add_title_package_to_video(video_path, output_path, opening_path, ending_path)
        if not concat_ok:
            raise Exception("片头片尾添加失败")
        progress_callback(1.0, "片头片尾添加完成")
    except Exception as e:
        state["current_step"] = "confirm_complete"
        _append_message(state, "assistant", f"{mode_text}失败: {str(e)}")
        return state
    finally:
        # 清理临时文件
        import os
        if os.path.exists(opening_path):
            os.remove(opening_path)
        if os.path.exists(ending_path):
            os.remove(ending_path)

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


def execute_chain_step(state: VideoAgentState) -> VideoAgentState:
    """执行操作链中的单个步骤（线性串联）"""
    from datetime import datetime
    from agent.streaming import send_chain_step_start, send_chain_step_complete

    chain = state.get("operation_chain", [])
    current_idx = state.get("current_step_index", 0)

    if current_idx >= len(chain):
        state["current_step"] = "confirm_complete"
        return state

    current_step = chain[current_idx]
    current_step["status"] = "running"
    current_step["started_at"] = datetime.now().isoformat()

    # 获取输入视频路径
    if current_idx == 0:
        input_path = state.get("temp_video_path") or state.get("video_path")
    else:
        prev_step = chain[current_idx - 1]
        input_path = prev_step.get("result", {}).get("output_path") if prev_step.get("result") else None

    if not input_path:
        current_step["status"] = "failed"
        current_step["error"] = "输入视频不存在"
        state["chain_status"] = "failed"
        state["current_step"] = "confirm_complete"
        return state

    # 发送步骤开始事件
    send_chain_step_start(current_idx + 1, len(chain), current_step["step_name"])

    # 调用对应执行器
    feature = current_step["feature"]
    params = current_step["params"]

    # 根据 feature 类型调用对应的执行器
    try:
        result = _execute_feature_for_chain(feature, input_path, params, state)
        current_step["result"] = result
        current_step["status"] = "completed" if result.get("success") else "failed"
        current_step["completed_at"] = datetime.now().isoformat()
        current_step["duration_seconds"] = (
            datetime.fromisoformat(current_step["completed_at"]) -
            datetime.fromisoformat(current_step["started_at"])
        ).total_seconds()

        # 发送步骤完成事件
        send_chain_step_complete(
            current_idx + 1, len(chain), current_step["step_name"],
            current_step["duration_seconds"],
            result  # 传递步骤执行结果
        )

        if result.get("success"):
            output_path = result.get("output_path")
            state["temp_video_path"] = output_path
            state["current_step_index"] = current_idx + 1
        else:
            error_msg = result.get("error", "未知错误")
            current_step["error"] = error_msg
            state["error"] = error_msg
            state["chain_status"] = "failed"
            # 推进索引避免无限循环
            state["current_step_index"] = current_idx + 1

    except Exception as e:
        current_step["status"] = "failed"
        current_step["error"] = str(e)
        current_step["completed_at"] = datetime.now().isoformat()
        current_step["duration_seconds"] = (
            datetime.fromisoformat(current_step["completed_at"]) -
            datetime.fromisoformat(current_step["started_at"])
        ).total_seconds()
        state["error"] = str(e)
        state["chain_status"] = "failed"
        # 推进索引避免无限循环
        state["current_step_index"] = current_idx + 1
        _append_message(state, "assistant", f"第 {current_idx + 1} 步 [{current_step['step_name']}] 异常：{str(e)}")

    state["current_step"] = "chain_router"
    return state


def _execute_feature_for_chain(feature: str, input_path: str, params: dict, state: VideoAgentState) -> dict:
    """为操作链执行单个功能，返回结果字典"""
    from pathlib import Path
    from datetime import datetime

    output_dir = Path("F:/video")
    output_dir.mkdir(exist_ok=True)
    input_name = Path(input_path).stem
    suffix = Path(input_path).suffix

    def make_progress_callback(label: str):
        def callback(progress: float, message: str = ""):
            msg = f"[PROGRESS:{int(progress * 100)}]"
            send_stream_message(msg)
        return callback

    try:
        if feature == "trim":
            from video.processor import trim_video
            start_time = params.get("start_time", 0)
            end_time = params.get("end_time", 30)
            output_path = str(output_dir / f"chain_trim_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")
            result = trim_video(input_path, output_path, start_time, end_time, progress_callback=make_progress_callback("chain_trim"))
            return result

        elif feature == "convert":
            from video.transformer import transform, TransformRequest
            target_orientation = params.get("target_orientation", "portrait")
            strategy = params.get("strategy", "pad")
            target_ratio = params.get("target_ratio", 9/16)
            output_path = str(output_dir / f"chain_convert_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")
            request = TransformRequest(
                input_path=input_path,
                output_path=output_path,
                target_orientation=target_orientation,
                strategy=strategy,
                target_ratio=target_ratio,
            )
            result = transform(request, progress_callback=make_progress_callback("chain_convert"))
            return_dict = {"success": result.success, "output_path": result.output_path, "error": result.error}
            if result.metadata:
                return_dict["metadata"] = {
                    "width": result.metadata.width,
                    "height": result.metadata.height,
                    "orientation": result.target_orientation,
                    "strategy": result.strategy_used,
                }
            return return_dict

        elif feature == "compress":
            from video.processor import compress_video
            compression_level = params.get("compression_level", "medium")
            output_path = str(output_dir / f"chain_compress_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")
            result = compress_video(input_path, output_path, compression_level, progress_callback=make_progress_callback("chain_compress"))
            return result

        elif feature == "editor":
            return _execute_editor_for_chain(input_path, output_dir, input_name, suffix, params, state)

        elif feature == "restore":
            # restore 功能暂时不可用
            return {"success": False, "error": "视频修复功能暂不可用"}

        elif feature == "info":
            from video.processor import get_video_metadata
            metadata = get_video_metadata(input_path)
            return {
                "success": True,
                "output_path": input_path,
                "metadata": {
                    "width": metadata.width,
                    "height": metadata.height,
                    "duration": metadata.duration,
                    "fps": metadata.fps,
                }
            }

        else:
            return {"success": False, "error": f"不支持的操作类型: {feature}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _execute_editor_for_chain(input_path: str, output_dir: Path, input_name: str, suffix: str, params: dict, state: VideoAgentState) -> dict:
    """为操作链执行编辑器功能"""
    from video.processor import get_video_metadata

    editor_mode = params.get("editor_mode", "bgm")
    progress_callback = _make_progress_callback("chain_editor")

    try:
        if editor_mode == "bgm":
            from video.bgm import find_matching_bgm, add_bgm_to_video
            bgm_mood = params.get("bgm_mood", "auto")
            bgm_volume = params.get("bgm_volume", 0.5)
            output_path = str(output_dir / f"chain_bgm_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")
            # 查找匹配的音乐
            bgm_info = find_matching_bgm(mood=bgm_mood)
            if not bgm_info:
                return {"success": False, "error": "未找到匹配的音乐文件"}
            bgm_path = bgm_info["path"]
            success = add_bgm_to_video(input_path, bgm_path, output_path, video_volume=0.7, bgm_volume=bgm_volume, progress_callback=progress_callback)
            return {
                "success": success,
                "output_path": output_path,
                "bgm_name": bgm_info.get("name"),
                "mood": bgm_mood,
            }

        elif editor_mode == "cover":
            from video.processor import generate_cover_images
            output_path = str(output_dir / f"chain_cover_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}")
            result = generate_cover_images(input_path, output_path, progress_callback=progress_callback)
            return {"success": result.get("success", False), "output_path": result.get("output_path")}

        elif editor_mode == "subtitle":
            from video.processor import generate_subtitle_from_video
            output_path = str(output_dir / f"chain_subtitle_{input_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt")
            result = generate_subtitle_from_video(input_path, output_path, progress_callback=progress_callback)
            return {"success": result.get("success", False), "output_path": result.get("output_path")}

        else:
            return {"success": False, "error": f"不支持的编辑器模式: {editor_mode}"}

    except Exception as e:
        return {"success": False, "error": str(e)}
