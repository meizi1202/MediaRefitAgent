"""
视频智能缩编模块 - FunClip 调度层

提供视频智能缩编的统一入口，实际处理委托给 FunClip
"""
import os
import logging
from pathlib import Path
from typing import Optional, Callable
from settings import FFMPEG_PRESET_TRANSFORM, FFMPEG_CRF_TRANSFORM, FFMPEG_AUDIO_BITRATE, FFMPEG_DIR

logger = logging.getLogger(__name__)

# FFmpeg 配置
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")


class CondensationError(Exception):
    """缩编异常"""
    pass


class CondensationResult:
    """缩编结果"""

    def __init__(
        self,
        success: bool,
        input_path: str = "",
        output_path: str = "",
        strategy: str = "",
        duration_before: float = 0.0,
        duration_after: float = 0.0,
        segments: list[dict] = None,
        transcript: str = "",
        subtitle_path: str = "",
        error: Optional[str] = None,
    ):
        self.success = success
        self.input_path = input_path
        self.output_path = output_path
        self.strategy = strategy
        self.duration_before = duration_before
        self.duration_after = duration_after
        self.segments = segments or []
        self.transcript = transcript
        self.subtitle_path = subtitle_path
        self.error = error

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "strategy": self.strategy,
            "duration_before": self.duration_before,
            "duration_after": self.duration_after,
            "compression_ratio": (
                self.duration_before / self.duration_after
                if self.duration_after > 0 else 0
            ),
            "segments": self.segments,
            "transcript": self.transcript,
            "subtitle_path": self.subtitle_path,
            "error": self.error,
        }


def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）"""
    import subprocess
    import json

    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path
        ],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    return 0.0


def condense_video(
    video_path: str,
    output_path: str,
    strategy: str = "content_condense",
    target_duration: float = 60.0,
    language: str = "zh",
    target_ratio: float = 9 / 16,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    llm_model: str = None,
    api_key: str = None,
) -> CondensationResult:
    """
    视频缩编统一入口 - FunClip 调度

    Args:
        video_path: 输入视频路径
        output_path: 输出视频路径
        strategy: 策略 (当前仅支持 content_condense)
        target_duration: 目标时长（秒）
        language: 语音语言
        target_ratio: 目标比例（用于 smart_crop）
        progress_callback: 进度回调
        llm_model: LLM 模型名（如 minimax/xxxtoken）
        api_key: API Key

    Returns:
        CondensationResult
    """
    os.makedirs(os.path.dirname(output_path) or "./output", exist_ok=True)

    if strategy == "content_condense":
        return _condense_with_funclip(
            video_path,
            output_path,
            target_duration=target_duration,
            language=language,
            progress_callback=progress_callback,
            llm_model=llm_model,
            api_key=api_key,
        )
    elif strategy == "smart_compress":
        return _smart_compress(video_path, output_path, progress_callback)
    elif strategy == "smart_crop":
        return _smart_crop(video_path, output_path, target_ratio, progress_callback)
    else:
        return CondensationResult(success=False, error=f"Unknown strategy: {strategy}")


def _condense_with_funclip(
    video_path: str,
    output_path: str,
    target_duration: float = 60.0,
    language: str = "zh",
    progress_callback: Optional[Callable[[float, str], None]] = None,
    llm_model: str = None,
    api_key: str = None,
) -> CondensationResult:
    """
    使用 FunClip 进行内容缩编

    FunClip 工作流：
    1. ASR 语音识别（Whisper/Paraformer）
    2. LLM 智能选段（可选）
    3. FFmpeg 裁剪拼接
    """
    base_dir = os.path.dirname(output_path) or "./output"
    video_name = Path(video_path).stem

    def _progress(p: float, m: str):
        if progress_callback:
            progress_callback(p, m)

    _progress(0.05, "Initializing FunClip...")

    # FunClip 调度层 - 直接使用 Whisper + FFmpeg，无需导入 FunClip 源码

    try:
        # 使用 Whisper ASR（已验证可用）
        import whisper
        _progress(0.1, "Loading Whisper model...")

        # Step 1: 提取音频
        _progress(0.15, "Extracting audio...")
        audio_path = os.path.join(base_dir, f"{video_name}_audio.wav")

        import subprocess
        result = subprocess.run(
            [
                "ffmpeg", "-i", video_path,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                audio_path, "-y"
            ],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return CondensationResult(success=False, error=f"Audio extraction failed: {result.stderr}")

        # Step 2: Whisper 识别
        _progress(0.25, "Running speech recognition...")
        model = whisper.load_model("base")
        asr_result = model.transcribe(audio_path, language=language if language != "zh" else None)

        full_text = asr_result["text"]
        segments = [
            {"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()}
            for seg in asr_result["segments"]
        ]

        if not segments:
            return CondensationResult(success=False, error="No speech detected")

        # Step 3: 生成 SRT
        _progress(0.7, "Generating subtitle...")
        srt_content = _segments_to_srt(segments)
        subtitle_path = os.path.join(base_dir, f"{video_name}_condensed.srt")

        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        # Step 4: LLM 智能选段（如果配置了）
        selected_segments = segments
        if llm_model and api_key:
            _progress(0.75, "LLM analyzing segments...")
            selected_segments = _llm_select_segments(
                segments, full_text, target_duration,
                llm_model, api_key, progress_callback
            )
        else:
            # 默认：按能量评分选择
            _progress(0.75, "Scoring segments by energy...")
            selected_segments = _energy_based_selection(
                segments, audio_path, target_duration
            )

        # Step 5: 裁剪拼接（使用重新编码确保兼容性）
        _progress(0.85, f"Cutting {len(selected_segments)} segments...")
        temp_files = []
        for i, seg in enumerate(selected_segments):
            temp_path = os.path.join(base_dir, f"temp_seg_{i}.mp4")
            start = seg["start"]
            end = min(seg["end"], start + target_duration)

            result = subprocess.run(
                [
                    "ffmpeg", "-i", video_path,
                    "-ss", str(start), "-to", str(end),
                    "-c:v", "libx264", "-preset", FFMPEG_PRESET_TRANSFORM, "-crf", str(FFMPEG_CRF_TRANSFORM),
                    "-c:a", "aac", "-b:a", FFMPEG_AUDIO_BITRATE,
                    "-movflags", "+faststart",
                    temp_path, "-y"
                ],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                temp_files.append(temp_path)
            # 每 5 个片段或最后一个才发送进度，避免频繁通信
            if (i + 1) % 5 == 0 or i == len(selected_segments) - 1:
                _progress(0.85 + 0.1 * (i + 1) / len(selected_segments), f"Cutting clip {i+1}/{len(selected_segments)}")

        if not temp_files:
            return CondensationResult(success=False, error="Failed to cut segments")

        _progress(0.95, "Concatenating clips...")
        success = _concatenate_segments(temp_files, output_path)
        if not success:
            return CondensationResult(success=False, error="Concatenation failed")

        # 清理临时文件
        for f in temp_files:
            try:
                os.remove(f)
            except:
                pass
        try:
            os.remove(audio_path)
        except:
            pass

        # 过滤字幕只保留选中片段
        if selected_segments != segments:
            filtered_srt = _filter_srt_by_ranges(srt_content, [(s["start"], s["end"]) for s in selected_segments])
            with open(subtitle_path, "w", encoding="utf-8") as f:
                f.write(filtered_srt)

        duration_before = get_video_duration(video_path)
        duration_after = get_video_duration(output_path)

        _progress(1.0, "Complete!")

        return CondensationResult(
            success=True,
            input_path=video_path,
            output_path=output_path,
            strategy="content_condense",
            duration_before=duration_before,
            duration_after=duration_after,
            segments=selected_segments,
            transcript=full_text,
            subtitle_path=subtitle_path,
        )

    except Exception as e:
        logger.error(f"Condensation failed: {e}")
        return CondensationResult(success=False, error=str(e))


def _llm_select_segments(
    segments: list[dict],
    transcript: str,
    target_duration: float,
    llm_model: str,
    api_key: str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> list[dict]:
    """使用 LLM 智能选择片段"""
    import requests
    import re

    segments_text = "\n".join([
        f"[{i}] {seg['start']:.1f}s - {seg['end']:.1f}s: {seg['text']}"
        for i, seg in enumerate(segments)
    ])

    system_prompt = """你是一个专业的视频剪辑师。给定一段视频的字幕时间戳内容，
请选出最精彩、最有价值的片段组成一个短视频。
要求：
1. 总时长控制在目标时长内
2. 优先选择有信息量、有情感、有动作的画面
3. 确保片段之间有逻辑连贯性
4. 返回 JSON 数组格式：[{"start": 15.5, "end": 25.0}, ...]"""

    user_prompt = f"""分析以下字幕，选出最精彩的片段（目标时长：{target_duration}秒）：

{segments_text}

返回 JSON 数组："""

    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        if progress_callback:
            progress_callback(0.5, "Calling LLM API...")

        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()

        choices = result.get("choices", [])
        if not choices:
            return segments

        content = choices[0].get("message", {}).get("content", "")
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            selected = json.loads(json_match.group())
            return [
                {**seg, "text": seg["text"], "llm_selected": True}
                for seg in segments
                for item in selected
                if abs(seg["start"] - item["start"]) < 0.5 and abs(seg["end"] - item["end"]) < 0.5
            ]
    except Exception as e:
        logger.warning(f"LLM selection failed, falling back: {e}")

    return segments


def _energy_based_selection(
    segments: list[dict],
    audio_path: str,
    target_duration: float,
) -> list[dict]:
    """基于音频能量选择片段"""
    import numpy as np
    import soundfile as sf

    try:
        data, sr = sf.read(audio_path)
        if len(data.shape) > 1:
            data = data[:, 0]

        scored = []
        for seg in segments:
            start_sample = int(seg["start"] * sr)
            end_sample = int(seg["end"] * sr)
            chunk = data[start_sample:end_sample]

            rms = np.sqrt(np.mean(chunk ** 2))
            energy_db = 20 * np.log10(rms + 1e-10)
            score = max(0, min(1, (energy_db + 60) / 60))

            scored.append({**seg, "energy_score": score})

        # 按分数排序，选择高分片段
        sorted_segs = sorted(scored, key=lambda x: x["energy_score"], reverse=True)
        selected = []
        total = 0.0

        for seg in sorted_segs:
            dur = seg["end"] - seg["start"]
            if total + dur <= target_duration:
                selected.append(seg)
                total += dur

        # 按时间排序
        selected = sorted(selected, key=lambda x: x["start"])
        return selected

    except Exception as e:
        logger.warning(f"Energy scoring failed: {e}")
        return segments[:int(target_duration / 3)]  # 默认选前几个


def _smart_compress(
    video_path: str,
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> CondensationResult:
    """智能压缩 - FFmpeg 重编码"""
    import subprocess

    def _progress(p: float, m: str):
        if progress_callback:
            progress_callback(p, m)

    _progress(0.1, "Analyzing video...")

    duration_before = get_video_duration(video_path)

    _progress(0.3, "Encoding with H.265...")

    result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-c:v", "libx265", "-crf", "23",
            "-c:a", "aac", "-b:a", FFMPEG_AUDIO_BITRATE,
            output_path, "-y"
        ],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return CondensationResult(success=False, error=f"Encoding failed: {result.stderr[-200:]}")

    duration_after = get_video_duration(output_path)

    return CondensationResult(
        success=True,
        input_path=video_path,
        output_path=output_path,
        strategy="smart_compress",
        duration_before=duration_before,
        duration_after=duration_after,
    )


def _smart_crop(
    video_path: str,
    output_path: str,
    target_ratio: float,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> CondensationResult:
    """智能裁剪 - YOLO 主体检测"""
    def _progress(p: float, m: str):
        if progress_callback:
            progress_callback(p, m)

    _progress(0.1, "Initializing YOLO...")

    try:
        from ml.smart_cropper import SmartCropper, YOLO_AVAILABLE
        if not YOLO_AVAILABLE:
            return CondensationResult(success=False, error="YOLO not available, install: pip install ultralytics")
    except ImportError:
        return CondensationResult(success=False, error="SmartCrop requires ultralytics")

    _progress(0.3, "Detecting objects...")

    try:
        cropper = SmartCropper()
        crop_result = cropper.crop_video_frames(video_path, target_ratio=target_ratio, sample_frames=10)
    except Exception as e:
        return CondensationResult(success=False, error=f"Detection failed: {e}")

    _progress(0.7, f"Applying crop filter...")

    import subprocess
    crop_filter = f"crop={crop_result.crop_width}:{crop_result.crop_height}:{crop_result.crop_x}:{crop_result.crop_y}"

    ff_result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vf", crop_filter,
            "-c:v", "libx264", "-preset", FFMPEG_PRESET_TRANSFORM, "-crf", str(FFMPEG_CRF_TRANSFORM),
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_path, "-y"
        ],
        capture_output=True, text=True
    )

    if ff_result.returncode != 0:
        return CondensationResult(success=False, error=f"Crop failed: {ff_result.stderr[-200:]}")

    duration_before = get_video_duration(video_path)
    duration_after = get_video_duration(output_path)

    return CondensationResult(
        success=True,
        input_path=video_path,
        output_path=output_path,
        strategy="smart_crop",
        duration_before=duration_before,
        duration_after=duration_after,
        segments=[{
            "start": 0,
            "end": duration_after,
            "text": f"Crop: {crop_result.crop_x},{crop_result.crop_y} {crop_result.crop_width}x{crop_result.crop_height}",
        }],
    )


def _segments_to_srt(segments: list[dict]) -> str:
    """将片段列表转换为 SRT 格式"""
    srt_lines = []
    for i, seg in enumerate(segments, 1):
        start = seg["start"]
        end = seg["end"]

        def fmt(t: float) -> str:
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        srt_lines.append(f"{i}\n{fmt(start)} --> {fmt(end)}\n{seg['text']}\n")
    return "\n".join(srt_lines)


def _filter_srt_by_ranges(srt_content: str, ranges: list[tuple[float, float]]) -> str:
    """从 SRT 内容中筛选指定时间范围内的字幕"""
    import re

    blocks = re.split(r'\n\n+', srt_content.strip())
    filtered = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
        if not time_match:
            continue

        start = _srt_time_to_float(time_match.group(1))
        end = _srt_time_to_float(time_match.group(2))

        for r_start, r_end in ranges:
            if start >= r_start - 0.1 and end <= r_end + 0.1:
                filtered.append(block)
                break

    return "\n\n".join(filtered)


def _srt_time_to_float(time_str: str) -> float:
    """SRT 时间字符串转浮点数秒"""
    import re
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
    if match:
        h, m, s, ms = map(int, match.groups())
        return h * 3600 + m * 60 + s + ms / 1000
    return 0.0


def _concatenate_segments(video_paths: list[str], output_path: str) -> bool:
    """拼接多个视频片段 - 使用 filter_complex（Windows 兼容）"""
    if not video_paths:
        return False

    import subprocess

    # 使用绝对路径
    abs_paths = [os.path.abspath(p) for p in video_paths]
    abs_output = os.path.abspath(output_path)

    # 构建 filter_complex 语法
    input_args = []
    filter_parts = []
    for i, path in enumerate(abs_paths):
        input_args.extend(["-i", path])
        filter_parts.append(f"[{i}:v][{i}:a]")

    n = len(abs_paths)
    filter_str = "".join(filter_parts) + f"concat=n={n}:v=1:a=1[outv][outa]"

    result = subprocess.run(
        [
            "ffmpeg",
            *input_args,
            "-filter_complex", filter_str,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", FFMPEG_PRESET_TRANSFORM, "-crf", str(FFMPEG_CRF_TRANSFORM),
            "-c:a", "aac", "-b:a", FFMPEG_AUDIO_BITRATE,
            "-movflags", "+faststart",
            abs_output, "-y",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        logger.error(f"Concat failed: {result.stderr[-300:]}")
        return False

    return True
