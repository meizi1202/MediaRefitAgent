"""
智能配音模块 - 基于 Edge-TTS

微软开源 TTS，中文效果好，支持多种音色
"""
import asyncio
import os
import re
from pathlib import Path
from typing import Optional, Literal

# Edge-TTS 音色列表
VOICE_OPTIONS = {
    # 中文女声
    "zh-CN-Xiaoxiao": {"name": "晓晓", "gender": "Female", "lang": "zh-CN"},
    "zh-CN-Xiaoyi": {"name": "小艺", "gender": "Female", "lang": "zh-CN"},
    "zh-CN-Yunxi": {"name": "云希", "gender": "Male", "lang": "zh-CN"},
    "zh-CN-Yunyang": {"name": "云扬", "gender": "Male", "lang": "zh-CN"},
    "zh-CN-liaoning": {"name": "辽宁", "gender": "Male", "lang": "zh-CN"},
    "zh-CN-shaanxi": {"name": "陕西", "gender": "Male", "lang": "zh-CN"},
    # 英文
    "en-US-Jenny": {"name": "Jenny", "gender": "Female", "lang": "en-US"},
    "en-US-Guy": {"name": "Guy", "gender": "Male", "lang": "en-US"},
    "en-GB-Sonia": {"name": "Sonia", "gender": "Female", "lang": "en-GB"},
}

# 预设风格
STYLE_PRESETS = {
    "default": "",
    "advertisement_upbeat": "advertisement_upbeat",
    "affectionate": "affectionate",
    "angry": "angry",
    "assistant": "assistant",
    "calm": "calm",
    "chat": "chat",
    "cheerful": "cheerful",
    "customerservice": "customerservice",
    "depressed": "depressed",
    "disgruntled": "disgruntled",
    "embarrassed": "embarrassed",
    "empathetic": "empathetic",
    "envious": "envious",
    "excited": "excited",
    "fearful": "fearful",
    "friendly": "friendly",
    "gentle": "gentle",
    "hopeful": "hopeful",
    "lyrical": "lyrical",
    "narration": "narration",
    "narration_relaxed": "narration_relaxed",
    "poetry_reading": "poetry_reading",
    "sad": "sad",
    "serious": "serious",
    "whispering": "whispering",
}


class EdgeTTS:
    """Edge TTS 封装"""

    def __init__(self, voice: str = "zh-CN-Xiaoxiao", rate: str = "+0%", pitch: str = "+0Hz"):
        """
        初始化 Edge TTS

        Args:
            voice: 音色 ID，见 VOICE_OPTIONS
            rate: 语速，如 "+10%" 表示加快10%，"-10%"表示减慢10%
            pitch: 音高调整，如 "+5Hz", "-5Hz"
        """
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    async def synthesize(self, text: str, output_path: str) -> bool:
        """
        合成语音

        Args:
            text: 要转换的文本
            output_path: 输出音频文件路径 (.mp3 或 .wav)

        Returns:
            是否成功
        """
        import edge_tts

        try:
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch)
            await communicate.save(output_path)
            return True
        except Exception as e:
            print(f"TTS synthesize error: {e}")
            return False

    def synthesize_sync(self, text: str, output_path: str) -> bool:
        """同步版本"""
        return asyncio.run(self.synthesize(text, output_path))


class TTSProcessor:
    """TTS 处理器 - 与视频混音"""

    @staticmethod
    async def text_to_speech(
        text: str,
        output_path: str,
        voice: str = "zh-CN-Xiaoxiao",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        style: str = "default",
        progress_callback=None
    ) -> bool:
        """
        将文本转换为语音

        Args:
            text: 文本内容
            output_path: 输出音频路径
            voice: 音色
            rate: 语速
            pitch: 音高
            style: 说话风格
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        if progress_callback:
            progress_callback(0.1)

        import edge_tts

        try:
            # 构建 Communicate 对象
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)

            # 应用风格（如果有）
            if style and style != "default" and style in STYLE_PRESETS:
                communicate = edge_tts.Communicate(
                    text, voice, rate=rate, pitch=pitch,
                    prosody={}  # Edge-TTS 风格通过 prosody 参数传递
                )

            await communicate.save(output_path)

            if progress_callback:
                progress_callback(1.0)

            return True

        except Exception as e:
            print(f"TTS error: {e}")
            return False

    @staticmethod
    def text_to_speech_sync(
        text: str,
        output_path: str,
        voice: str = "zh-CN-Xiaoxiao",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        style: str = "default",
        progress_callback=None
    ) -> bool:
        """同步版本"""
        return asyncio.run(TTSProcessor.text_to_speech(
            text, output_path, voice, rate, pitch, style, progress_callback
        ))

    @staticmethod
    def mix_with_video(
        video_path: str,
        audio_path: str,
        output_path: str,
        tts_volume: float = 1.0,
        original_volume: float = 0.3,
        fade_out: bool = True,
        fade_duration: float = 2.0,
        progress_callback=None
    ) -> bool:
        """
        将 TTS 音频与视频混音

        Args:
            video_path: 视频文件路径
            audio_path: TTS 音频文件路径
            output_path: 输出视频路径
            tts_volume: TTS 音量 (0.0-1.0)
            original_volume: 原视频音量 (0.0-1.0)
            fade_out: 是否淡出
            fade_duration: 淡出时长
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            if progress_callback:
                progress_callback(0.2)

            # 获取视频时长
            probe = ffmpeg.probe(video_path)
            video_duration = float(probe['format']['duration'])

            # 获取音频时长
            audio_probe = ffmpeg.probe(audio_path)
            audio_duration = float(audio_probe['format']['duration'])

            # 构建 FFmpeg 命令
            video = ffmpeg.input(video_path)
            tts_audio = ffmpeg.input(audio_path)

            # 调整音量
            tts_audio = tts_audio.audio.filter('volume', tts_volume)
            original_audio = video.audio.filter('volume', original_volume)

            # 如果 TTS 音频比视频短，循环填充
            if audio_duration < video_duration:
                # 计算需要循环的次数
                loops = int(video_duration / audio_duration) + 1
                # 简化的处理：直接截断或淡入淡出
                tts_audio = tts_audio.audio.trim(duration=video_duration)

            # 淡出处理
            if fade_out:
                tts_audio = tts_audio.filter('afade', t='out', st=video_duration - fade_duration, d=fade_duration)

            if progress_callback:
                progress_callback(0.5)

            # 混合音频
            output = ffmpeg.output(
                video,
                tts_audio,
                original_audio,
                output_path,
                vcodec='copy',
                acodec='aac',
                shortest=None
            )

            ffmpeg.run(output, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return True

        except Exception as e:
            print(f"Mix error: {e}")
            return False

    @staticmethod
    def list_voices(lang: Optional[str] = None) -> list[dict]:
        """
        列出可用的音色

        Args:
            lang: 语言筛选，如 "zh-CN", "en-US"

        Returns:
            音色列表
        """
        if lang:
            return [v for v in VOICE_OPTIONS.values() if v["lang"] == lang]
        return list(VOICE_OPTIONS.values())


# 便捷函数
async def synthesize_speech(
    text: str,
    output_path: str,
    voice: str = "zh-CN-Xiaoxiao",
    rate: str = "+0%",
    pitch: str = "+0Hz"
) -> bool:
    """异步合成语音"""
    return await TTSProcessor.text_to_speech(text, output_path, voice, rate, pitch)


def text_to_speech(
    text: str,
    output_path: str,
    voice: str = "zh-CN-Xiaoxiao",
    rate: str = "+0%",
    pitch: str = "+0Hz"
) -> bool:
    """同步合成语音"""
    return TTSProcessor.text_to_speech_sync(text, output_path, voice, rate, pitch)


def add_tts_to_video(
    video_path: str,
    text: str,
    output_path: str,
    voice: str = "zh-CN-Xiaoxiao",
    tts_volume: float = 1.0,
    original_volume: float = 0.3
) -> bool:
    """
    为视频添加配音

    Args:
        video_path: 视频文件路径
        text: 配音文本
        output_path: 输出视频路径
        voice: 音色
        tts_volume: TTS 音量
        original_volume: 原视频音量

    Returns:
        是否成功
    """
    import tempfile

    # 先生成 TTS 音频
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        tts_path = f.name

    try:
        if not TTSProcessor.text_to_speech_sync(text, tts_path, voice):
            return False

        # 混音
        return TTSProcessor.mix_with_video(
            video_path, tts_path, output_path,
            tts_volume=tts_volume,
            original_volume=original_volume
        )
    finally:
        if os.path.exists(tts_path):
            os.unlink(tts_path)
