"""
智能配乐模块

支持根据视频内容/情绪自动匹配合适的背景音乐
"""
import os
import re
import random
from pathlib import Path
from typing import Optional


class MusicMatcher:
    """音乐风格匹配器"""

    # 音乐风格关键词映射
    MOOD_KEYWORDS = {
        "happy": ["happy", "upbeat", "欢快", "轻松", "愉快", "fun", "joy", "positive", "阳光", "活泼"],
        "sad": ["sad", "melancholy", "忧伤", "悲伤", "低沉", "blue", "gloomy", "slow", "抒情"],
        "energetic": ["energetic", "power", "激情", "力量", "热血", "rock", "intense", "强劲", "动感"],
        "calm": ["calm", "peaceful", "安静", "平静", "放松", "relax", "soft", "轻音乐", "舒缓", "背景"],
        "epic": ["epic", "cinematic", "史诗", "宏大", "大气", "trailer", "dramatic", "震撼"],
        "corporate": ["corporate", "business", "商务", "专业", "clean", "modern", "企业", "科技"],
    }

    # 情绪标签对应的推荐时长(秒)和典型bpm
    MOOD_PARAMS = {
        "happy": {"duration_factor": 0.7, "bpm_range": (110, 130), "volume": 0.4},
        "sad": {"duration_factor": 1.5, "bpm_range": (60, 80), "volume": 0.3},
        "energetic": {"duration_factor": 0.5, "bpm_range": (140, 170), "volume": 0.5},
        "calm": {"duration_factor": 1.2, "bpm_range": (70, 90), "volume": 0.25},
        "epic": {"duration_factor": 0.6, "bpm_range": (100, 120), "volume": 0.45},
        "corporate": {"duration_factor": 1.0, "bpm_range": (100, 115), "volume": 0.35},
    }

    def __init__(self, music_dir: Optional[str] = None):
        """
        初始化音乐匹配器

        Args:
            music_dir: 音乐库目录，默认使用用户音乐目录
        """
        self.music_dir = Path(music_dir) if music_dir else self._get_default_music_dir()
        self.music_files = self._scan_music_library()

    def _get_default_music_dir(self) -> Path:
        """获取默认音乐目录"""
        # 尝试常见音乐目录
        possible_dirs = [
            Path.home() / "Music",
            Path.home() / "Music/BGM",
            Path("F:/video/bgm"),
            Path("F:/video/music"),
        ]
        for d in possible_dirs:
            if d.exists():
                return d
        # 返回第一个可用目录
        possible_dirs[0].mkdir(parents=True, exist_ok=True)
        return possible_dirs[0]

    def _scan_music_library(self) -> list[dict]:
        """扫描音乐库，返回音乐文件列表及元数据"""
        music_files = []
        if not self.music_dir.exists():
            return music_files

        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg'}

        for f in self.music_dir.rglob('*'):
            if f.suffix.lower() in audio_extensions:
                mood = self._classify_music(f.name)
                music_files.append({
                    "path": str(f),
                    "name": f.stem,
                    "mood": mood,
                    "size": f.stat().st_size
                })

        return music_files

    def _classify_music(self, filename: str) -> str:
        """根据文件名分类音乐风格"""
        filename_lower = filename.lower()

        for mood, keywords in self.MOOD_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in filename_lower:
                    return mood

        return "calm"  # 默认平静风格

    def match_music(self, mood: str = "auto", duration: Optional[float] = None) -> Optional[dict]:
        """
        匹配音乐

        Args:
            mood: 目标情绪 (happy/sad/energetic/calm/epic/corporate/auto)
            duration: 视频时长，用于选择合适长度的音乐

        Returns:
            匹配的音乐信息，如果没找到返回 None
        """
        if not self.music_files:
            return None

        # 如果是 auto，根据时长推断情绪
        if mood == "auto":
            if duration:
                if duration < 30:
                    mood = "energetic"  # 短视频用动感的
                elif duration < 120:
                    mood = "happy"
                else:
                    mood = "calm"
            else:
                mood = "calm"

        # 筛选同风格的音乐
        candidates = [m for m in self.music_files if m["mood"] == mood]

        # 如果没找到同风格的，随机选一个
        if not candidates:
            candidates = self.music_files

        # 随机选择一个
        return random.choice(candidates) if candidates else None

    def list_moods(self) -> list[str]:
        """列出可用的音乐风格"""
        return list(self.MOOD_KEYWORDS.keys())


class BGMProcessor:
    """BGM 处理器 - 使用 FFmpeg 进行音频混音"""

    @staticmethod
    def mix_audio(
        video_path: str,
        audio_path: str,
        output_path: str,
        video_volume: float = 0.3,
        bgm_volume: float = 0.5,
        fade_out: bool = True,
        fade_duration: float = 3.0,
        progress_callback=None
    ) -> bool:
        """
        混合视频原音和背景音乐

        Args:
            video_path: 视频文件路径
            audio_path: 背景音乐文件路径
            output_path: 输出文件路径
            video_volume: 视频原音音量 (0.0-1.0)
            bgm_volume: BGM 音量 (0.0-1.0)
            fade_out: 是否在结尾淡出
            fade_duration: 淡出时长（秒）
            progress_callback: 进度回调函数

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            if progress_callback:
                progress_callback(0.1)

            # 获取视频时长
            probe = ffmpeg.probe(video_path)
            video_duration = float(probe['format']['duration'])

            # 构建 FFmpeg 命令
            video_stream = ffmpeg.input(video_path)
            audio_stream = ffmpeg.input(audio_path)

            # 调整音量
            video_stream = video_stream.audio.filter('volume', video_volume)
            audio_stream = audio_stream.filter('volume', bgm_volume)

            # 如果音乐比视频长，进行裁剪
            # 先获取音频时长
            try:
                audio_probe = ffmpeg.probe(audio_path)
                audio_duration = float(audio_probe['format']['duration'])
                if audio_duration > video_duration:
                    audio_stream = audio_stream.trim(duration=video_duration)
            except Exception:
                pass

            # 淡出处理
            if fade_out:
                audio_stream = audio_stream.filter('afade', t='out', st=video_duration - fade_duration, d=fade_duration)

            if progress_callback:
                progress_callback(0.3)

            # 混合音频
            output = ffmpeg.output(
                video_stream,
                audio_stream,
                output_path,
                vcodec='copy',  # 保留视频编码
                acodec='aac',
                shortest=None
            )

            # 执行
            ffmpeg.run(output, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return True

        except Exception as e:
            print(f"BGM mix error: {e}")
            return False

    @staticmethod
    def extract_audio(
        video_path: str,
        output_path: str,
        progress_callback=None
    ) -> bool:
        """
        从视频中提取音频

        Args:
            video_path: 视频文件路径
            output_path: 输出音频文件路径
            progress_callback: 进度回调函数

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            stream = ffmpeg.input(video_path)
            stream = ffmpeg.output(stream.audio, output_path, acodec='libmp3lame', q=2)
            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return True
        except Exception as e:
            print(f"Audio extract error: {e}")
            return False

    @staticmethod
    def normalize_audio(
        audio_path: str,
        output_path: str,
        target_loudness: float = -20.0,
        progress_callback=None
    ) -> bool:
        """
        音频音量标准化

        Args:
            audio_path: 音频文件路径
            output_path: 输出文件路径
            target_loudness: 目标响度 (LUFS)
            progress_callback: 进度回调函数

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            stream = ffmpeg.input(audio_path)
            stream = stream.audio.filter('loudnorm', i=target_loudness)
            stream = ffmpeg.output(stream, output_path, acodec='libmp3lame')
            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return True
        except Exception as e:
            print(f"Audio normalize error: {e}")
            return False


# 便捷函数
def find_matching_bgm(mood: str = "auto", duration: Optional[float] = None, music_dir: Optional[str] = None) -> Optional[dict]:
    """
    查找匹配的背景音乐

    Args:
        mood: 目标情绪
        duration: 视频时长
        music_dir: 音乐库目录

    Returns:
        匹配的音乐信息
    """
    matcher = MusicMatcher(music_dir)
    return matcher.match_music(mood, duration)


def add_bgm_to_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    video_volume: float = 0.3,
    bgm_volume: float = 0.5,
    fade_out: bool = True,
    fade_duration: float = 3.0,
    progress_callback=None
) -> bool:
    """
    为视频添加背景音乐

    Args:
        video_path: 视频文件路径
        audio_path: 背景音乐文件路径
        output_path: 输出文件路径
        video_volume: 视频原音音量
        bgm_volume: BGM 音量
        fade_out: 是否淡出
        fade_duration: 淡出时长
        progress_callback: 进度回调

    Returns:
        是否成功
    """
    return BGMProcessor.mix_audio(
        video_path, audio_path, output_path,
        video_volume, bgm_volume, fade_out, fade_duration, progress_callback
    )
