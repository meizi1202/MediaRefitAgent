"""
FFmpeg 视频处理封装

提供视频元数据获取、方向检测、各种转换策略的 FFmpeg 命令封装
"""
import os
import re
import subprocess
import json
from pathlib import Path
from typing import Optional, Callable, Literal

Orientation = Literal["portrait", "landscape", "square", "unknown"]

# FFmpeg 配置
FFMPEG_DIR = "C:/ffmpeg/ffmpeg-9.0-essentials_build/bin"
FFMPEG_PATH = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
FFPROBE_PATH = os.path.join(FFMPEG_DIR, "ffprobe.exe")
os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
os.environ["FFMPEG_BINARY"] = FFMPEG_PATH
os.environ["FFPROBE_BINARY"] = FFPROBE_PATH

# 比例预设
RATIO_PRESETS = {
    "portrait": {
        "9:16": 9 / 16,   # 0.5625 - 短视频标准
        "4:5": 4 / 5,     # 0.8 - Instagram
        "1:1": 1 / 1,     # 1.0 - 正方形
        "2:3": 2 / 3,     # 0.6667 - 照片
    },
    "landscape": {
        "16:9": 16 / 9,   # 1.7778 - 标准
        "21:9": 21 / 9,   # 2.3333 - 电影
        "4:3": 4 / 3,     # 1.3333 - 电视
        "3:2": 3 / 2,     # 1.5 - 照片
    },
}


class VideoMetadata:
    """视频元数据"""

    def __init__(
        self,
        width: int,
        height: int,
        duration: float,
        fps: float,
        bitrate: int,
        rotation: int = 0,
        codec: str = "",
    ):
        self.width = width
        self.height = height
        self.duration = duration
        self.fps = fps
        self.bitrate = bitrate
        self.rotation = rotation
        self.codec = codec

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height > 0 else 0

    def __repr__(self):
        return f"VideoMetadata({self.width}x{self.height}, {self.fps}fps, {self.duration}s)"


def run_ffmpeg(cmd: list, progress_callback: Optional[Callable[[float], None]] = None) -> tuple[bool, str]:
    """
    执行 FFmpeg 命令

    Args:
        cmd: FFmpeg 命令列表
        progress_callback: 进度回调 (0.0 - 1.0)

    Returns:
        (是否成功, 错误信息或输出)
    """
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        output = []
        for line in process.stderr:
            output.append(line)
            if progress_callback and "time=" in line:
                # 解析进度
                try:
                    time_match = re.search(r"time=(\d+):(\d+):(\d+)", line)
                    if time_match:
                        hours = int(time_match.group(1))
                        minutes = int(time_match.group(2))
                        seconds = int(time_match.group(3))
                        current_time = hours * 3600 + minutes * 60 + seconds
                        progress_callback(min(current_time / 300, 0.99))  # 假设最大 5 分钟
                except:
                    pass

        process.wait()
        success = process.returncode == 0
        error = "".join(output) if not success else ""

        return success, error

    except Exception as e:
        return False, str(e)


def get_video_metadata(file_path: str) -> VideoMetadata:
    """
    获取视频元数据

    Args:
        file_path: 视频文件路径

    Returns:
        VideoMetadata 对象
    """
    cmd = [
        FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise Exception(result.stderr)

        data = json.loads(result.stdout)

        # 找到视频流
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break

        if not video_stream:
            raise Exception("No video stream found")

        # 解析旋转角度
        rotation = 0
        for tag in video_stream.get("tags", {}).get("rotate", ""):
            rotation = int(tag) if tag.isdigit() else 0

        # 获取时长
        duration = float(data.get("format", {}).get("duration", 0))

        # 获取帧率
        fps_str = video_stream.get("r_frame_rate", "0/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = int(num) / int(den) if int(den) != 0 else 0
        else:
            fps = float(fps_str)

        return VideoMetadata(
            width=video_stream.get("width", 0),
            height=video_stream.get("height", 0),
            duration=duration,
            fps=fps,
            bitrate=int(data.get("format", {}).get("bit_rate", 0)),
            rotation=rotation,
            codec=video_stream.get("codec_name", ""),
        )

    except Exception as e:
        # 返回默认值
        return VideoMetadata(width=0, height=0, duration=0, fps=0, bitrate=0)


def rotate_video(
    input_path: str,
    output_path: str,
    degrees: int = 90,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    旋转视频

    Args:
        input_path: 输入路径
        output_path: 输出路径
        degrees: 旋转角度 (90, 180, 270)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    # transpose: 0=90°CW, 1=90°CCW, 2=180°
    transpose_map = {90: "1", 180: "2", 270: "0"}
    transpose = transpose_map.get(degrees, "1")

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", f"transpose={transpose}",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback)
    if not success:
        raise Exception(f"Rotate failed: {error}")
    return True


def pad_to_ratio(
    input_path: str,
    output_path: str,
    target_ratio: float = 9 / 16,
    target_orientation: str = "portrait",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    填充黑边到目标比例

    Args:
        input_path: 输入路径
        output_path: 输出路径
        target_ratio: 目标比例 (height/width)
        target_orientation: 目标方向 (portrait/landscape)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    metadata = get_video_metadata(input_path)
    original_ratio = metadata.width / metadata.height if metadata.height > 0 else 1

    if abs(original_ratio - target_ratio) < 0.01:
        # 比例相同，直接复制
        import shutil
        shutil.copy(input_path, output_path)
        return True

    # 计算目标尺寸
    if target_orientation == "portrait":
        # 目标竖屏：宽 < 高，宽度是限制因素
        target_width = metadata.width
        target_height = int(target_width / target_ratio)
        pad_top = (target_height - metadata.height) // 2
        pad_bottom = target_height - metadata.height - pad_top
        vf = f"pad={target_width}:{target_height}:0:{pad_top}:black"
    else:
        # 目标横屏：高 < 宽，高度是限制因素
        target_height = metadata.height
        target_width = int(target_height * target_ratio)
        pad_left = (target_width - metadata.width) // 2
        pad_right = target_width - metadata.width - pad_left
        vf = f"pad={target_width}:{target_height}:{pad_left}:0:black"

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-profile:v", "baseline",
        "-level", "3.1",
        "-refs", "1",
        "-threads", "1",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback)
    if not success:
        raise Exception(f"Pad failed: {error}")
    return True


def crop_to_ratio(
    input_path: str,
    output_path: str,
    target_ratio: float = 9 / 16,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    裁剪到目标比例（从中心裁剪）

    Args:
        input_path: 输入路径
        output_path: 输出路径
        target_ratio: 目标比例 (height/width)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    metadata = get_video_metadata(input_path)
    original_ratio = metadata.width / metadata.height if metadata.height > 0 else 1

    if abs(original_ratio - target_ratio) < 0.01:
        import shutil
        shutil.copy(input_path, output_path)
        return True

    # 计算裁剪尺寸
    if original_ratio > target_ratio:
        # 视频更宽，裁剪左右
        crop_width = int(metadata.height * target_ratio)
        crop_height = metadata.height
        x_offset = (metadata.width - crop_width) // 2
        y_offset = 0
    else:
        # 视频更高，裁剪上下
        crop_width = metadata.width
        crop_height = int(metadata.width / target_ratio)
        x_offset = 0
        y_offset = (metadata.height - crop_height) // 2

    vf = f"crop={crop_width}:{crop_height}:{x_offset}:{y_offset}"

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback)
    if not success:
        raise Exception(f"Crop failed: {error}")
    return True


def stretch_to_ratio(
    input_path: str,
    output_path: str,
    target_ratio: float = 9 / 16,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    拉伸到目标比例（可能变形）

    Args:
        input_path: 输入路径
        output_path: 输出路径
        target_ratio: 目标比例 (height/width)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    metadata = get_video_metadata(input_path)
    target_width = metadata.width
    target_height = int(metadata.width / target_ratio)
    # libx264 requires dimensions divisible by 2, round to nearest even number
    target_height = (target_height + 1) // 2 * 2

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", f"scale={target_width}:{target_height}",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback)
    if not success:
        raise Exception(f"Stretch failed: {error}")
    return True


def compress_video(
    input_path: str,
    output_path: str,
    compression_level: str = "medium",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    压缩视频（保留原始分辨率、帧率、像素格式）

    Args:
        input_path: 输入路径
        output_path: 输出路径
        compression_level: 压缩级别 (low/medium/high)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    if compression_level == "low":
        # low: 直接复制流，不重新编码，最小化质量损失
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-c:v", "copy",
            "-c:a", "copy",
            output_path,
        ]
    else:
        # medium/high: 重新编码以减小体积
        # 保留原始编码格式 (h265 -> libx265, h264 -> libx264)
        metadata = get_video_metadata(input_path)
        codec_map = {"h264": "libx264", "h265": "libx265", "hevc": "libx265"}
        original_codec = codec_map.get(metadata.codec, "libx264") if metadata.codec else "libx264"

        # 压缩级别参数映射
        # CRF: 值越大质量越低文件越小 (18-35 范围)
        # low=直接复制, medium=CRF28(中等压缩), high=CRF32(高压缩)
        level_params = {
            "medium": {"crf": 28, "preset": "medium", "description": "中等压缩"},
            "high": {"crf": 32, "preset": "slow", "description": "高压缩"},
        }
        params = level_params.get(compression_level, level_params["medium"])

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-c:v", original_codec,
            "-preset", params["preset"],
            "-crf", str(params["crf"]),
            # 不使用 -vf scale，保留原始分辨率
            # 不使用 -r，保留原始帧率
            "-c:a", "aac",
            "-b:a", "128k",
            output_path,
        ]

    success, error = run_ffmpeg(cmd, progress_callback)
    if not success:
        raise Exception(f"Compress failed: {error}")
    return True


def mirror_scroll(
    input_path: str,
    output_path: str,
    target_ratio: float = 9 / 16,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    镜像滚动效果（适合竖屏转横屏）

    Args:
        input_path: 输入路径
        output_path: 输出路径
        target_ratio: 目标比例 (height/width)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    metadata = get_video_metadata(input_path)

    # 先填充到目标比例
    temp_path = output_path + ".tmp.pad.mp4"
    pad_to_ratio(input_path, temp_path, target_ratio, progress_callback)

    # 镜像翻转
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", temp_path,
        "-vf", "hflip",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback)

    # 清理临时文件
    if Path(temp_path).exists():
        Path(temp_path).unlink()

    if not success:
        raise Exception(f"Mirror scroll failed: {error}")
    return True


def pan_scroll(
    input_path: str,
    output_path: str,
    target_ratio: float = 9 / 16,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    平移滚动效果（适合竖屏转横屏）

    视频从一侧平滑移动到另一侧

    Args:
        input_path: 输入路径
        output_path: 输出路径
        target_ratio: 目标比例 (height/width)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    metadata = get_video_metadata(input_path)

    # 计算目标尺寸
    target_height = metadata.height
    target_width = int(metadata.height / target_ratio)

    # 平移效果：从左到右滚动
    # 使用 zoompan 和 hstack 实现
    duration = metadata.duration if metadata.duration > 0 else 10

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", f"scale={target_width}:{target_height},zoompan=z='min(zoom+0.001,1.5)':d=1:s={target_width}x{target_height},setsar=1",
        "-t", str(duration),
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback)
    if not success:
        # 如果 zoompan 失败，使用简单的 scale
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-vf", f"scale={target_width}:{target_height}",
            "-c:a", "copy",
            output_path,
        ]
        success, error = run_ffmpeg(cmd, progress_callback)

    if not success:
        raise Exception(f"Pan scroll failed: {error}")
    return True


def transform_video(
    input_path: str,
    output_path: str,
    target_orientation: str = "portrait",
    strategy: str = "pad",
    target_ratio: float = 9 / 16,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    通用视频转换接口

    Args:
        input_path: 输入路径
        output_path: 输出路径
        target_orientation: 目标方向 (portrait/landscape)
        strategy: 转换策略 (pad/crop/smart_crop/stretch/mirror_scroll/pan_scroll/rotate)
        target_ratio: 目标比例
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    if strategy == "pad":
        return pad_to_ratio(input_path, output_path, target_ratio, progress_callback)
    elif strategy == "crop":
        return crop_to_ratio(input_path, output_path, target_ratio, progress_callback)
    elif strategy == "stretch":
        return stretch_to_ratio(input_path, output_path, target_ratio, progress_callback)
    elif strategy == "mirror_scroll":
        return mirror_scroll(input_path, output_path, target_ratio, progress_callback)
    elif strategy == "pan_scroll":
        return pan_scroll(input_path, output_path, target_ratio, progress_callback)
    elif strategy == "rotate":
        return rotate_video(input_path, output_path, 90, progress_callback)
    else:
        raise Exception(f"Unknown strategy: {strategy}")
