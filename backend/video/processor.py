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


def run_ffmpeg(cmd: list, progress_callback: Optional[Callable[[float], None]] = None, total_duration: Optional[float] = None) -> tuple[bool, str]:
    """
    执行 FFmpeg 命令

    Args:
        cmd: FFmpeg 命令列表
        progress_callback: 进度回调 (0.0 - 1.0)
        total_duration: 视频总时长（秒），用于计算准确的进度百分比

    Returns:
        (是否成功, 错误信息或输出)
    """
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        output = []
        # 使用二进制读取，手动解码，避免编码问题
        while True:
            chunk = process.stderr.read(1024)
            if not chunk:
                break
            try:
                line = chunk.decode('utf-8', errors='replace')
            except:
                line = chunk.decode('gbk', errors='replace')
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
                        # 使用实际视频时长计算进度百分比
                        max_time = total_duration if total_duration else 300
                        progress_callback(min(current_time / max_time, 0.99))
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
        rotate_str = video_stream.get("tags", {}).get("rotate", "")
        if rotate_str and rotate_str.isdigit():
            rotation = int(rotate_str)

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

    metadata = get_video_metadata(input_path)
    success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)
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

    success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)
    if not success:
        raise Exception(f"Pad failed: {error}")
    return True


def crop_to_ratio(
    input_path: str,
    output_path: str,
    target_ratio: float = 9 / 16,
    target_orientation: str = "portrait",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    裁剪到目标比例（从中心裁剪）

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

    # 根据目标方向计算裁剪尺寸
    if target_orientation == "portrait":
        # 目标竖屏：裁剪上下（保持宽度一致）
        crop_width = metadata.width
        crop_height = int(metadata.width / target_ratio)
        x_offset = 0
        y_offset = (metadata.height - crop_height) // 2
    else:
        # 目标横屏：裁剪左右（保持高度一致）
        crop_height = metadata.height
        crop_width = int(metadata.height * target_ratio)
        x_offset = (metadata.width - crop_width) // 2
        y_offset = 0

    # 校验裁剪尺寸是否超出原视频范围
    if crop_width > metadata.width or crop_height > metadata.height:
        raise Exception(
            f"裁剪失败：目标比例 {target_ratio:.3f} 要求裁剪尺寸 {crop_width}x{crop_height}，"
            f"但原视频仅为 {metadata.width}x{metadata.height}。\n"
            f"建议使用「填充黑边」策略代替。"
        )

    # 确保尺寸为偶数（x264 要求）
    crop_width = (crop_width + 1) // 2 * 2
    crop_height = (crop_height + 1) // 2 * 2

    vf = f"crop={crop_width}:{crop_height}:{x_offset}:{y_offset}"

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)
    if not success:
        # 提取真正的错误信息（跳过 banner）
        error_lines = error.strip().split('\n')
        real_error = [l for l in error_lines if not l.startswith('ffmpeg version') and not l.startswith('built with') and not l.startswith('configuration:') and not l.startswith('  ')]
        real_error_msg = real_error[-1] if real_error else error[:200]
        raise Exception(f"Crop failed: {real_error_msg}")
    return True


def stretch_to_ratio(
    input_path: str,
    output_path: str,
    target_ratio: float = 9 / 16,
    target_orientation: str = "portrait",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    拉伸到目标比例（可能变形）

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

    # 根据目标方向计算拉伸尺寸
    # 拉伸填充策略：直接拉伸视频内容到目标比例（可能变形）
    if target_orientation == "portrait":
        # 目标竖屏：宽度不变，高度按比例计算
        target_width = metadata.width
        target_height = int(metadata.width / target_ratio)
    else:
        # 目标横屏：高度不变，宽度按比例计算
        target_height = metadata.height
        target_width = int(metadata.height * target_ratio)

    # 限制最大尺寸防止内存溢出
    max_dimension = 1920
    if target_width > max_dimension:
        scale = max_dimension / target_width
        target_width = max_dimension
        target_height = int(target_height * scale)
    if target_height > max_dimension:
        scale = max_dimension / target_height
        target_height = max_dimension
        target_width = int(target_width * scale)

    # libx264 requires dimensions divisible by 2, round to nearest even number
    target_width = (target_width + 1) // 2 * 2
    target_height = (target_height + 1) // 2 * 2

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", f"scale={target_width}:{target_height},setsar=1",
        "-c:a", "copy",
        "-threads", "1",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)
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
    metadata = get_video_metadata(input_path)
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
            "-preset", "ultrafast",
            "-crf", str(params["crf"]),
            # 内存优化参数（解决大分辨率视频malloc失败）
            "-profile:v", "baseline",
            "-level", "3.1",
            "-refs", "1",
            "-threads", "1",
            # 不使用 -vf scale，保留原始分辨率
            # 不使用 -r，保留原始帧率
            "-c:a", "aac",
            "-b:a", "128k",
            output_path,
        ]

    success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)
    if not success:
        raise Exception(f"Compress failed: {error}")
    return True


def mirror_scroll(
    input_path: str,
    output_path: str,
    target_ratio: float = 9 / 16,
    target_orientation: str = "portrait",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    镜像滚动效果（适合横屏转竖屏）

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

    # 先填充到目标比例
    temp_path = output_path + ".tmp.pad.mp4"
    pad_to_ratio(input_path, temp_path, target_ratio, target_orientation, progress_callback)

    # 镜像翻转
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", temp_path,
        "-vf", "hflip",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)

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
    target_orientation: str = "portrait",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    平移滚动效果（适合横屏转竖屏）

    视频从一侧平滑移动到另一侧

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
    duration = metadata.duration if metadata.duration > 0 else 10

    # 根据目标方向计算目标尺寸（确保尺寸为偶数）
    if target_orientation == "portrait":
        # 目标竖屏：宽度不变，高度按比例计算
        target_width = metadata.width
        target_height = int(metadata.width / target_ratio)
    else:
        # 目标横屏：高度不变，宽度按比例计算
        target_height = metadata.height
        target_width = int(metadata.height * target_ratio)

    # 确保尺寸为偶数（x264 要求）
    target_width = (target_width + 1) // 2 * 2
    target_height = (target_height + 1) // 2 * 2

    # 平移效果：从左到右滚动
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", f"scale={target_width}:{target_height},zoompan=z='min(zoom+0.001,1.5)':d=1:s={target_width}x{target_height},setsar=1",
        "-t", str(duration),
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)
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
        success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)

    if not success:
        raise Exception(f"Pan scroll failed: {error}")
    return True


def trim_video(
    input_path: str,
    output_path: str,
    start_time: float = 0.0,
    end_time: Optional[float] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    裁剪视频到指定时间段

    Args:
        input_path: 输入路径
        output_path: 输出路径
        start_time: 开始时间（秒）
        end_time: 结束时间（秒），None 表示到视频结尾
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    metadata = get_video_metadata(input_path)
    duration = metadata.duration if metadata.duration > 0 else 0

    # 验证时间参数
    if start_time < 0:
        start_time = 0
    if end_time is None or end_time > duration:
        end_time = duration
    if end_time <= start_time:
        raise ValueError("end_time must be greater than start_time")

    # FFmpeg 裁剪命令：-ss 进行快速 seek，-t 指定持续时间
    # 注意：使用 -c copy 可能在某些视频上有时间戳问题，改用重新编码
    trim_duration = end_time - start_time
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-ss", str(start_time),
        "-i", input_path,
        "-t", str(trim_duration),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback, total_duration=trim_duration)
    if not success:
        raise Exception(f"Trim failed: {error}")
    return True


def concat_videos(
    input_paths: list[str],
    output_path: str,
    keep_audio: bool = True,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    拼接多个视频为一个视频

    自动检测视频参数：
    - 如果所有视频编码、分辨率、帧率、像素格式完全一致，使用 concat demuxer（-c copy，无损快速）
    - 否则使用 filter_complex（通用方案，强制转码）

    Args:
        input_paths: 输入文件路径列表（至少2个）
        output_path: 输出文件路径
        keep_audio: 是否保留音轨
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    if len(input_paths) < 2:
        raise ValueError("Need at least 2 input files")

    # 获取所有视频的参数
    metas = [get_video_metadata(p) for p in input_paths]

    # 检查是否所有视频参数一致（可使用快速 concat demuxer）
    first = metas[0]
    all_same = all(
        m.codec == first.codec
        and m.width == first.width
        and m.height == first.height
        and abs(m.fps - first.fps) < 0.01
        for m in metas
    )

    if all_same:
        # 使用 concat demuxer（流复制，无损快速）
        # 需要先创建文件列表
        list_file = output_path + ".txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for p in input_paths:
                # Windows 下使用正斜杠
                f.write(f"file '{p.replace(chr(92), '/')}'\n")

        cmd = [FFMPEG_PATH, "-y", "-f", "concat", "-safe", "0", "-i", list_file]
        if keep_audio:
            cmd.extend(["-c:v", "copy", "-c:a", "copy"])
        else:
            cmd.extend(["-c:v", "copy", "-an"])
        cmd.append(output_path)

        success, error = run_ffmpeg(cmd, progress_callback, total_duration=sum(m.duration for m in metas))
        # 清理临时文件
        if os.path.exists(list_file):
            os.unlink(list_file)
    else:
        # 使用 filter_complex 方案：缩放 + 拼接
        target_w = first.width
        target_h = first.height

        filter_complex = ""
        concat_inputs = ""

        for i, input_file in enumerate(input_paths):
            # 缩放到目标分辨率，添加黑边保持宽高比
            filter_complex += f"[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
            filter_complex += f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2[v{i}];"

            if keep_audio:
                filter_complex += f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}];"
                concat_inputs += f"[v{i}][a{i}]"
            else:
                concat_inputs += f"[v{i}]"

        # 添加 concat 滤镜
        if keep_audio:
            filter_complex += f"{concat_inputs}concat=n={len(input_paths)}:v=1:a=1[outv][outa]"
        else:
            filter_complex += f"{concat_inputs}concat=n={len(input_paths)}:v=1:a=0[outv]"

        # 构建命令
        cmd = [FFMPEG_PATH, "-y"]
        for f in input_paths:
            cmd.extend(["-i", f])
        cmd.extend(["-filter_complex", filter_complex])

        if keep_audio:
            cmd.extend(["-map", "[outv]", "-map", "[outa]"])
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.extend(["-map", "[outv]"])

        cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "23", output_path])

        success, error = run_ffmpeg(cmd, progress_callback, total_duration=sum(m.duration for m in metas))

    if not success:
        raise Exception(f"Concat failed: {error}")
    return True


def add_transition(
    video_path: str,
    output_path: str,
    transition_type: str = "fade",
    duration: float = 1.0,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> dict:
    """
    为视频添加转场效果

    使用 FFmpeg xfade 滤镜实现片段间的转场效果。
    注意：此函数主要用于单视频添加片头片尾淡入淡出，或多视频拼接时的转场。
    对于已有视频的片段间转场，需要先分割视频再拼接。

    Args:
        video_path: 输入文件路径
        output_path: 输出文件路径
        transition_type: 转场类型 (fade/slide/zoom/blur/rotate/dissolve)
        duration: 转场时长（秒）
        progress_callback: 进度回调

    Returns:
        dict: {"success": bool, "message": str}
    """
    # 获取视频时长
    metadata = get_video_metadata(video_path)
    total_duration = metadata.duration

    # 构建 xfade 滤镜参数
    xfade_transitions = {
        "fade": "fade",
        "slide": "slideright",
        "zoom": "zoomin",
        "blur": "hblur",
        "rotate": "rotate",
        "dissolve": "dissolve",
    }

    xfade_name = xfade_transitions.get(transition_type, "fade")

    # 转场公式：offset = 片段时长 - 转场时长
    # 对于片头淡入：start=0, duration
    # 对于片尾淡出：start=total_duration - duration, duration
    # 这里实现片头+片尾淡入淡出

    if transition_type == "fade":
        # 淡入淡出：片头 + duration，片尾 + duration
        filter_str = (
            f"fade=in:st=0:d={duration},"
            f"fade=out:st={total_duration - duration}:d={duration}"
        )
    else:
        # 其他转场效果使用固定滤镜
        filter_str = f"xfade=transition={xfade_name}:duration={duration}:offset=0"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", filter_str,
        "-af", f"afade=in:st=0:d={duration},afade=out:st={total_duration - duration}:d={duration}",
        "-c:a", "aac",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback, total_duration=total_duration)

    if not success:
        return {"success": False, "message": f"转场处理失败: {error}"}

    # 获取输出文件大小
    output_size = os.path.getsize(output_path)

    return {
        "success": True,
        "message": f"转场效果添加完成",
        "output_path": output_path,
        "transition_type": transition_type,
        "transition_duration": duration,
        "duration": total_duration,
        "output_size": output_size,
    }


def burn_subtitle(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    style: str = "default",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    将字幕烧录到视频中

    Args:
        video_path: 输入视频路径
        subtitle_path: SRT 字幕文件路径
        output_path: 输出视频路径
        style: 字幕样式 (default/minimal/emoji)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    metadata = get_video_metadata(video_path)
    # 字幕样式配置
    if style == "minimal":
        # 简洁样式：白色，小字号，底部居中
        fontsize = 24
        fontcolor = "white"
        box = 0
    elif style == "emoji":
        # emoji 样式：支持 emoji 显示
        fontsize = 28
        fontcolor = "white"
        box = 0
    else:
        # 默认样式：白色，中字号，底部居中，带背景
        fontsize = 24
        fontcolor = "white"
        box = 1

    # 使用 FFmpeg drawtext 滤镜烧录字幕
    # Windows 上 FFmpeg 需要特殊路径格式：F\\:/path/to/file
    def escape_path_for_ffmpeg(path):
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

    escaped_subtitle_path = escape_path_for_ffmpeg(subtitle_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles={escaped_subtitle_path}:force_style='FontSize={fontsize},PrimaryColour=&H00FFFFFF&,Outline=2,Shadow=1'",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)

    if not success:
        # 如果 subtitles 滤镜失败，尝试直接用 ass 文件
        ass_path = subtitle_path.replace(".srt", ".ass")
        try:
            # 简单的 srt -> ass 转换（实际可用工具）
            import subprocess
            subprocess.run([
                "ffmpeg", "-y", "-i", subtitle_path, ass_path
            ], capture_output=True)

            if os.path.exists(ass_path):
                escaped_ass_path = escape_path_for_ffmpeg(ass_path)
                cmd = [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-vf", f"ass={escaped_ass_path}",
                    "-c:a", "copy",
                    output_path,
                ]
                success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)
        except Exception:
            pass

    return success


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


# ============ 老视频修复 FFmpeg 滤镜函数 ============

def denoise_video(
    input_path: str,
    output_path: str,
    level: str = "medium",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    视频去噪

    Args:
        input_path: 输入路径
        output_path: 输出路径
        level: 去噪级别 (light/medium/strong)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    # hqdn3d 参数：derez spatial-temporal strength
    # light: 2:1.5:2.5  medium: 4:3:5  strong: 6:4.5:7.5
    level_params = {
        "light": "2:1.5:2.5",
        "medium": "4:3:5",
        "strong": "6:4.5:7.5",
    }
    hqdn3d_param = level_params.get(level, level_params["medium"])
    metadata = get_video_metadata(input_path)

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", f"hqdn3d={hqdn3d_param}",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback, total_duration=metadata.duration)
    if not success:
        raise Exception(f"Denoise failed: {error}")
    return True


def color_correct_video(
    input_path: str,
    output_path: str,
    saturation: float = 1.0,
    contrast: float = 1.0,
    brightness: float = 0.0,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    色彩校正

    Args:
        input_path: 输入路径
        output_path: 输出路径
        saturation: 饱和度 (0.0 ~ 2.0, 1.0为原始)
        contrast: 对比度 (0.5 ~ 2.0, 1.0为原始)
        brightness: 亮度 (-1.0 ~ 1.0, 0为原始)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    # 使用 eq 滤镜进行色彩调整
    vf = f"eq=s={saturation}:c={contrast}:b={brightness}"

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
        raise Exception(f"Color correct failed: {error}")
    return True


def sharpen_video(
    input_path: str,
    output_path: str,
    level: str = "medium",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    视频锐化（去抖动增强）

    Args:
        input_path: 输入路径
        output_path: 输出路径
        level: 锐化级别 (light/medium/strong)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    # unsharp 参数：luma_msize_x:luma_msize_y:luma_amount
    # 正值锐化，负值模糊
    level_params = {
        "light": "5:5:0.5",
        "medium": "5:5:1.0",
        "strong": "7:7:1.5",
    }
    unsharp_param = level_params.get(level, level_params["medium"])

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", f"unsharp={unsharp_param}",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback)
    if not success:
        raise Exception(f"Sharpen failed: {error}")
    return True


def remove_scratch(
    input_path: str,
    output_path: str,
    level: str = "medium",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    划痕修复

    使用 FFmpeg removegrain + deflicker 滤镜减少老胶片瑕疵
    注意：descratch 滤镜在标准 FFmpeg 中不可用，使用替代方案

    Args:
        input_path: 输入路径
        output_path: 输出路径
        level: 修复级别 (light/medium/strong)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    # removegrain 模式：1=轻度去噪, 2=中度去噪, 3=强力去噪
    level_params = {
        "light": "1",
        "medium": "2",
        "strong": "3",
    }
    rg_mode = level_params.get(level, level_params["medium"])

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", f"removegrain={rg_mode}",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback)
    if not success:
        raise Exception(f"Remove scratch failed: {error}")
    return True


def remove_flicker(
    input_path: str,
    output_path: str,
    level: str = "medium",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    闪烁修复

    使用帧间亮度平滑减少闪烁

    Args:
        input_path: 输入路径
        output_path: 输出路径
        level: 修复级别 (light/medium/strong)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    # 使用 fade 滤镜进行亮度平滑
    # 结合 mpdecimate 减少闪烁
    if level == "light":
        # 轻度：仅使用轻微的对比度调整
        vf = "eq=contrast=1.05"
    elif level == "medium":
        # 中度：对比度调整 + 轻微去闪烁
        vf = "eq=contrast=1.1,hqdn3d=2:1.5:2.5"
    else:  # strong
        # 强力：多帧平均 + 对比度调整
        vf = "eq=contrast=1.15,hqdn3d=3:2:3"

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
        raise Exception(f"Remove flicker failed: {error}")
    return True


def interpolate_frames(
    input_path: str,
    output_path: str,
    target_fps: int = 60,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    补帧（帧率提升）

    使用 FFmpeg minterpolate 滤镜进行帧率转换

    Args:
        input_path: 输入路径
        output_path: 输出路径
        target_fps: 目标帧率
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    # 获取原视频帧率
    metadata = get_video_metadata(input_path)
    original_fps = metadata.fps if metadata.fps > 0 else 30

    # minterpolate 参数：fps:mi_mode:block_size
    # mi_mode: scenechange / mci
    vf = f"minterpolate=fps={target_fps}:mi_mode=mci"

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback)
    if not success:
        raise Exception(f"Interpolate frames failed: {error}")
    return True


def super_resolve_video(
    input_path: str,
    output_path: str,
    scale: int = 2,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    视频超分辨率（放大）

    使用 FFmpeg scale 滤镜进行分辨率放大

    Args:
        input_path: 输入路径
        output_path: 输出路径
        scale: 放大倍数 (2 or 4)
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    # 获取原视频分辨率
    metadata = get_video_metadata(input_path)
    original_width = metadata.width
    original_height = metadata.height

    # 计算目标分辨率（确保是偶数）
    target_width = (original_width * scale + 1) // 2 * 2
    target_height = (original_height * scale + 1) // 2 * 2

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", f"scale={target_width}:{target_height}:flags=lanczos",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "20",
        "-c:a", "copy",
        output_path,
    ]

    success, error = run_ffmpeg(cmd, progress_callback)
    if not success:
        raise Exception(f"Super resolve failed: {error}")
    return True


def restore_video(
    input_path: str,
    output_path: str,
    denoise: bool = False,
    denoise_level: str = "medium",
    deblur: bool = False,
    deblur_level: str = "medium",
    color_correct: bool = False,
    saturation: float = 1.0,
    contrast: float = 1.0,
    scratch_remove: bool = False,
    scratch_level: str = "medium",
    flicker_remove: bool = False,
    flicker_level: str = "medium",
    interpolate: bool = False,
    target_fps: int = 60,
    super_resolution: bool = False,
    scale: int = 2,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> bool:
    """
    综合视频修复

    将多个修复操作组合执行

    Args:
        input_path: 输入路径
        output_path: 输出路径
        denoise: 是否去噪
        denoise_level: 去噪级别
        deblur: 是否锐化
        deblur_level: 锐化级别
        color_correct: 是否色彩校正
        saturation: 饱和度
        contrast: 对比度
        scratch_remove: 是否划痕修复
        scratch_level: 划痕级别
        flicker_remove: 是否闪烁修复
        flicker_level: 闪烁级别
        interpolate: 是否补帧
        target_fps: 目标帧率
        super_resolution: 是否超分
        scale: 放大倍数
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    import tempfile
    import shutil
    from pathlib import Path

    # 构建滤镜链
    filters = []

    if denoise:
        # 使用 nlmeans 替代 hqdn3d，质量更好
        level_params = {
            "light": "h=7:p=3:r=7",
            "medium": "h=9:p=5:r=15",
            "strong": "h=11:p=7:r=21",
        }
        nlmeans_param = level_params.get(denoise_level, level_params["medium"])
        filters.append(f"nlmeans={nlmeans_param}")

    if deblur:
        # 使用 cas (Contrast Adaptive Sharpen) 替代 unsharp，效果更好
        level_params = {
            "light": "0.5",
            "medium": "1.0",
            "strong": "1.5",
        }
        cas_param = level_params.get(deblur_level, level_params["medium"])
        filters.append(f"cas={cas_param}")

    if color_correct:
        filters.append(f"eq=saturation={saturation}:contrast={contrast}")

    if scratch_remove:
        # 使用 removegrain 作为替代
        level_params = {
            "light": "1",
            "medium": "2",
            "strong": "3",
        }
        rg_mode = level_params.get(scratch_level, level_params["medium"])
        filters.append(f"removegrain={rg_mode}")

    if flicker_remove:
        # 改进的闪烁修复：使用 deflicker + eq
        if flicker_level == "light":
            filters.append("deflicker")
        elif flicker_level == "medium":
            filters.append("deflicker,eq=contrast=1.05")
        else:
            filters.append("deflicker,eq=contrast=1.1")

    # 如果有滤镜，先处理
    temp_path = input_path
    if filters:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_path = temp_file.name
        temp_file.close()

        vf = ",".join(filters)
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", input_path,
            "-vf", vf,
            "-c:a", "copy",
            temp_path,
        ]

        success, error = run_ffmpeg(cmd, progress_callback)
        if not success:
            raise Exception(f"Restoration filters failed: {error}")

    # 补帧
    if interpolate:
        metadata = get_video_metadata(temp_path)
        original_fps = metadata.fps if metadata.fps > 0 else 30
        if original_fps < target_fps:
            interp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            interp_path = interp_file.name
            interp_file.close()

            vf = f"minterpolate=fps={target_fps}:mi_mode=mci"
            cmd = [
                FFMPEG_PATH,
                "-y",
                "-i", temp_path,
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-c:a", "copy",
                interp_path,
            ]

            success, error = run_ffmpeg(cmd, progress_callback)
            if not success:
                raise Exception(f"Interpolation failed: {error}")

            if temp_path != input_path:
                Path(temp_path).unlink()
            temp_path = interp_path

    # 超分
    if super_resolution:
        metadata = get_video_metadata(temp_path)
        target_width = (metadata.width * scale + 1) // 2 * 2
        target_height = (metadata.height * scale + 1) // 2 * 2

        super_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        super_path = super_file.name
        super_file.close()

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", temp_path,
            "-vf", f"scale={target_width}:{target_height}:flags=lanczos",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "20",
            "-c:a", "copy",
            super_path,
        ]

        success, error = run_ffmpeg(cmd, progress_callback)
        if not success:
            raise Exception(f"Super resolution failed: {error}")

        if temp_path != input_path:
            Path(temp_path).unlink()
        temp_path = super_path

    # 最终输出
    if temp_path != output_path:
        shutil.copy(temp_path, output_path)
        Path(temp_path).unlink()

    return True

