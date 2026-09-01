"""
全局配置 - 统一管理 .env 配置项

所有模块应从此文件导入配置，而非直接读取 .env 或硬编码默认值
"""
import os
import platform
import shutil
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（项目根目录）
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)


def _get_str(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    return int(val) if val else default


def _get_float(key: str, default: float) -> float:
    val = os.getenv(key)
    return float(val) if val else default


def _get_ffmpeg_bin() -> tuple[str, str]:
    """
    获取 FFmpeg 和 FFprobe 的完整路径（跨平台）

    优先级：
    1. 环境变量 FFMPEG_DIR
    2. PATH 中的 ffmpeg（通过 shutil.which）
    3. 常见系统路径（Linux/macOS）
    """
    # 确定文件扩展名
    ext = ".exe" if platform.system() == "Windows" else ""

    # 1. 优先使用环境变量 FFMPEG_DIR
    ffmpeg_dir = os.getenv("FFMPEG_DIR", "")
    if ffmpeg_dir:
        ffmpeg_path = Path(ffmpeg_dir) / f"ffmpeg{ext}"
        ffprobe_path = Path(ffmpeg_dir) / f"ffprobe{ext}"
        if ffmpeg_path.exists():
            return str(ffmpeg_path), str(ffprobe_path)
        # 如果目录存在但文件不在这里，也检查 which
        if shutil.which(str(ffmpeg_path)):
            return str(ffmpeg_path), str(ffprobe_path)

    # 2. 直接使用命令名（ffmpeg 已在 PATH 中）
    if shutil.which("ffmpeg"):
        return "ffmpeg", "ffprobe"

    # 3. 常见系统路径（Linux/macOS）
    system_paths = ["/usr/bin", "/usr/local/bin"]
    if platform.system() == "Darwin":  # macOS
        system_paths.append("/opt/homebrew/bin")

    for sys_path in system_paths:
        ffmpeg_full = Path(sys_path) / f"ffmpeg{ext}"
        if ffmpeg_full.exists():
            return str(ffmpeg_full), str(Path(sys_path) / f"ffprobe{ext}")

    # 最后回退到命令名（依赖 PATH）
    return f"ffmpeg{ext}", f"ffprobe{ext}"


# =================== FFmpeg 编码参数 ===================
# 用途说明：
#   - ultrafast: 实时处理、大文件、低内存环境（如老旧机器/高分辨率视频）
#   - fast:     普通转码，平衡速度与质量
#   - medium:   质量优先，速度较慢
#   - slow:     最高质量，编码耗时较长

# 通用视频编码 preset（filter 滤镜、转码默认使用）
FFMPEG_PRESET_TRANSFORM = _get_str("FFMPEG_PRESET_TRANSFORM", "ultrafast")

# 拼接场景的 preset（多段视频合并，质量要求相对不高）
FFMPEG_PRESET_CONCAT = _get_str("FFMPEG_PRESET_CONCAT", "ultrafast")

# 分析场景的 preset（封面生成、内容分析等）
FFMPEG_PRESET_ANALYSIS = _get_str("FFMPEG_PRESET_ANALYSIS", "medium")

# 默认 CRF（质量参数，18-28 较合理，值越大文件越小）
FFMPEG_CRF_TRANSFORM = _get_int("FFMPEG_CRF_TRANSFORM", 23)

# FFmpeg 配置（通过 _get_ffmpeg_bin() 获取跨平台路径）
# FFmpeg bin 目录（用于设置 PATH），空字符串表示使用 PATH 中的 ffmpeg
FFMPEG_DIR = _get_str("FFMPEG_DIR", "")

# 预计算的 FFmpeg/FFprobe 完整路径（跨平台）
FFMPEG_PATH, FFPROBE_PATH = _get_ffmpeg_bin()

# 音频码率（拼接场景使用）
FFMPEG_AUDIO_BITRATE = _get_str("FFMPEG_AUDIO_BITRATE", "128k")

# =================== 音乐库配置 ===================
# BGM 音乐库目录（跨平台支持）
# Linux: /home/user/music/bgm
# macOS: /Users/user/Music/bgm
# Windows: F:/video/bgm
MUSIC_LIBRARY_DIR = _get_str("MUSIC_LIBRARY_DIR", "")
