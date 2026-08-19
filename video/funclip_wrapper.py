"""
FunClip 封装模块

提供语音识别 + 字幕生成 + 智能裁剪的统一接口
支持 Whisper ASR（已验证可用）和 Fun-ASR（依赖问题待解决）
"""
import os
import subprocess
import json
from pathlib import Path
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)

# FFmpeg 配置
FFMPEG_DIR = "C:/ffmpeg/ffmpeg-9.0-essentials_build/bin"
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")

# 模型缓存目录
MODELSCOPE_CACHE = os.environ.get("MODELSCOPE_CACHE", "D:/models_cache")


class FunClipASRResult:
    """ASR 识别结果"""

    def __init__(
        self,
        text: str,
        segments: list[dict],
        srt_content: str,
        duration: float,
    ):
        self.text = text  # 完整文本
        self.segments = segments  # 分段列表，每个包含 start, end, text
        self.srt_content = srt_content  # SRT 格式字幕
        self.duration = duration  # 总时长（秒）


def extract_audio(video_path: str, output_path: str) -> bool:
    """提取音频为 16kHz 单声道 WAV"""
    result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            output_path, "-y"
        ],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        logger.error(f"Audio extraction failed: {result.stderr}")
        return False
    return True


def transcribe_with_whisper(
    audio_path: str,
    model_size: str = "base",
    language: str = "zh",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> FunClipASRResult:
    """
    使用 OpenAI Whisper 进行语音识别

    Args:
        audio_path: 音频文件路径
        model_size: 模型大小 tiny/base/small/medium/large
        language: 语言代码 zh/en/ja 等
        progress_callback: 进度回调

    Returns:
        FunClipASRResult 对象
    """
    import whisper

    if progress_callback:
        progress_callback(0.1)

    # 加载模型
    model = whisper.load_model(model_size)
    if progress_callback:
        progress_callback(0.3)

    # 识别
    result = model.transcribe(audio_path, language=language)
    if progress_callback:
        progress_callback(0.8)

    full_text = result["text"]
    segments = [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"].strip()}
        for seg in result["segments"]
    ]

    # 生成 SRT
    srt_content = _segments_to_srt(segments)
    duration = segments[-1]["end"] if segments else 0.0

    if progress_callback:
        progress_callback(1.0)

    return FunClipASRResult(
        text=full_text,
        segments=segments,
        srt_content=srt_content,
        duration=duration,
    )


def _segments_to_srt(segments: list[dict]) -> str:
    """将片段列表转换为 SRT 格式"""
    srt_lines = []
    for i, seg in enumerate(segments, 1):
        start = seg["start"]
        end = seg["end"]
        text = seg["text"]

        def fmt(t: float) -> str:
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        srt_lines.append(f"{i}\n{fmt(start)} --> {fmt(end)}\n{text}\n")
    return "\n".join(srt_lines)


def escape_path_for_ffmpeg(path: str) -> str:
    """FFmpeg subtitles 滤镜路径转义（自动适配 Windows/Linux）

    - Windows: 将反斜杠转为正斜杠，驱动器路径用双反斜杠转义冒号
    - Linux: 直接返回原路径
    """
    import os
    if os.name != 'nt':
        return path

    # Windows: 先将反斜杠转换为正斜杠
    path = path.replace('\\', '/')
    if len(path) >= 2 and path[1] == ':':
        # 驱动器路径需要双反斜杠转义冒号
        return path[0] + chr(92) * 2 + ':' + path[2:]
    return path


def burn_subtitle(
    video_path: str,
    srt_path: str,
    output_path: str,
    font_path: Optional[str] = None,
) -> bool:
    """
    烧录字幕到视频

    Args:
        video_path: 输入视频
        srt_path: SRT 字幕文件
        output_path: 输出视频
        font_path: 字体文件路径（可选）

    Returns:
        是否成功
    """
    # Windows 上 FFmpeg subtitles 滤镜需要特殊路径转义
    escaped_srt_path = escape_path_for_ffmpeg(srt_path)

    # 构建字幕滤镜
    subtitle_filter = f"subtitles={escaped_srt_path}"

    # 如果指定了字体，添加到滤波器
    if font_path and os.path.exists(font_path):
        subtitle_filter += f":force_style='FontName={Path(font_path).stem}'"

    result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vf", subtitle_filter,
            "-c:a", "copy",
            output_path, "-y"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        logger.error(f"Subtitle burn failed: {result.stderr[-500:]}")
        return False
    return True


def cut_segment(
    video_path: str,
    output_path: str,
    start_time: float,
    end_time: float,
    copy_codec: bool = True,
) -> bool:
    """
    裁剪视频片段

    Args:
        video_path: 输入视频
        output_path: 输出视频
        start_time: 开始时间（秒）
        end_time: 结束时间（秒）
        copy_codec: 是否使用快速复制模式（false 则重新编码）

    Returns:
        是否成功
    """
    codec = ["-c", "copy"] if copy_codec else ["-c:v", "libx264", "-crf", "23"]

    result = subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-ss", str(start_time),
            "-to", str(end_time),
            *codec,
            output_path, "-y"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        logger.error(f"Segment cut failed: {result.stderr[-300:]}")
        return False
    return True


def concatenate_segments(
    video_paths: list[str],
    output_path: str,
) -> bool:
    """
    拼接多个视频片段

    Args:
        video_paths: 视频片段路径列表
        output_path: 输出视频

    Returns:
        是否成功
    """
    if not video_paths:
        return False

    # 创建临时文件列表
    list_file = output_path + ".list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for path in video_paths:
            f.write(f"file '{path}'\n")

    result = subprocess.run(
        [
            "ffmpeg", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path, "-y"
        ],
        capture_output=True,
        text=True
    )

    # 清理临时文件
    try:
        os.remove(list_file)
    except:
        pass

    if result.returncode != 0:
        logger.error(f"Concatenation failed: {result.stderr[-300:]}")
        return False
    return True


def get_audio_duration(audio_path: str) -> float:
    """获取音频时长"""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            audio_path
        ],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    return 0.0


def full_transcribe_pipeline(
    video_path: str,
    output_dir: str,
    model_size: str = "base",
    language: str = "zh",
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Optional[FunClipASRResult]:
    """
    完整的语音转字幕流程

    Args:
        video_path: 视频文件路径
        output_dir: 输出目录
        model_size: Whisper 模型大小
        language: 语言
        progress_callback: 进度回调 (progress: float, message: str)

    Returns:
        FunClipASRResult 或 None
    """
    os.makedirs(output_dir, exist_ok=True)

    audio_path = os.path.join(output_dir, "audio.wav")
    base_name = Path(video_path).stem

    # Step 1: 提取音频
    if progress_callback:
        progress_callback(0.05, "Extracting audio...")

    if not extract_audio(video_path, audio_path):
        return None

    # Step 2: Whisper 识别
    if progress_callback:
        progress_callback(0.15, "Running speech recognition...")

    result = transcribe_with_whisper(
        audio_path,
        model_size=model_size,
        language=language,
        progress_callback=lambda p: progress_callback(0.15 + p * 0.7, "Recognizing speech...") if progress_callback else None,
    )

    # Step 3: 保存 SRT
    if progress_callback:
        progress_callback(0.9, "Saving subtitle file...")

    srt_path = os.path.join(output_dir, f"{base_name}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(result.srt_content)

    # 保存完整文本
    txt_path = os.path.join(output_dir, f"{base_name}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(result.text)

    if progress_callback:
        progress_callback(1.0, "Transcription complete")

    return result
