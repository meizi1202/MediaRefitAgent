"""
视频滤镜模块 - 基于 FFmpeg

提供多种预设滤镜效果：复古、电影感、清新、黑白等
"""
from typing import Optional, Literal


class VideoFilter:
    """视频滤镜处理器"""

    # 预设滤镜配置
    PRESETS = {
        # 名称: (滤镜链, 说明)
        "none": (
            "",
            "无滤镜"
        ),
        "vintage": (
            "curves=vintage,eq=brightness=0.05:saturation=0.9",
            "复古风格 - 暖色调"
        ),
        "cinematic": (
            "eq=contrast=1.15:saturation=1.1:brightness=-0.02,curves=all='0/0 0.3/0.2 0.7/0.85 1/1',vignette=angle=0.5",
            "电影感 - 高对比、电影曲线、暗角"
        ),
        "fresh": (
            "eq=brightness=0.08:saturation=1.15:contrast=1.05,curves=neutral='0/0.05 0.5/0.55 1/0.95'",
            "清新风格 - 提亮、饱和度适中"
        ),
        "bw": (
            "colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3,contrast=1.1",
            "黑白电影 - 灰度转换"
        ),
        "cold": (
            "eq=saturation=0.9:brightness=-0.02,colorchannelmixer=.9:.1:.1:.1:.9:.1:.1:.1:.9",
            "冷色调 - 蓝色调"
        ),
        "warm": (
            "eq=saturation=1.2:brightness=0.03,colorchannelmixer=1.1:0.1:0:0:1.1:0:0:0:1.1",
            "暖色调 - 橙黄色调"
        ),
        "vivid": (
            "eq=contrast=1.2:saturation=1.4:brightness=0.02",
            "鲜艳模式 - 高饱和、高对比"
        ),
        "soft": (
            "eq=brightness=0.1:saturation=0.8:contrast=0.95,blur=2",
            "柔和风格 - 模糊背景、降低对比"
        ),
        "dramatic": (
            "eq=contrast=1.4:saturation=0.9:brightness=-0.05,curves=neutral='0/0.02 0.5/0.45 1/0.98',vignette=angle=0.7",
            "戏剧风格 - 深色阴影、强烈对比"
        ),
        "fade": (
            "eq=brightness=0.1:contrast=0.9:saturation=0.85,curves=all='0/0.1 1/0.9'",
            "褪色效果 - 降低对比、柔和"
        ),
        "cyberpunk": (
            "colorchannelmixer=0:0:1:0:1:0:1:0:0:0,eq=contrast=1.3:saturation=1.4:brightness=0.02",
            "赛博朋克 - 青色/洋红色调"
        ),
    }

    # 快速滤镜（简单表达式）
    QUICK_FILTERS = {
        "brightness": "eq=brightness={value}",
        "contrast": "eq=contrast={value}",
        "saturation": "eq=saturation={value}",
        "hue": "eq=hue={value}",
        "blur": "boxblur={value}",
        "sharpen": "unsharp=5:5:1.0:5:5:0.0",
        "denoise": "hqdn3d={value}",
        "vignette": "vignette=angle={angle}",
    }

    @classmethod
    def apply_filter(
        cls,
        video_path: str,
        output_path: str,
        preset: str = "none",
        custom_filter: Optional[str] = None,
        progress_callback=None
    ) -> bool:
        """
        应用滤镜

        Args:
            video_path: 输入视频路径
            output_path: 输出视频路径
            preset: 预设名称 (vintage/cinematic/fresh/bw/cold/warm/vivid/soft/dramatic/fade/cyberpunk)
            custom_filter: 自定义滤镜表达式（覆盖 preset）
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            if progress_callback:
                progress_callback(0.1)

            # 确定使用的滤镜
            if custom_filter:
                filter_chain = custom_filter
            elif preset in cls.PRESETS:
                filter_chain = cls.PRESETS[preset][0]
            else:
                filter_chain = ""

            # 如果没有滤镜，直接复制
            if not filter_chain:
                stream = ffmpeg.input(video_path)
                stream = ffmpeg.output(stream, output_path, vcodec='copy', acodec='copy')
                ffmpeg.run(stream, overwrite_output=True, quiet=True)
                if progress_callback:
                    progress_callback(1.0)
                return True

            # 构建命令
            stream = ffmpeg.input(video_path)
            stream = ffmpeg.output(
                stream,
                output_path,
                vf=filter_chain,
                vcodec='libx264',
                acodec='copy',
                preset='fast'  # 快速编码
            )

            if progress_callback:
                progress_callback(0.3)

            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return True

        except Exception as e:
            print(f"Filter error: {e}")
            return False

    @classmethod
    def apply_filter_with_audio_adjust(
        cls,
        video_path: str,
        output_path: str,
        preset: str = "none",
        audio_volume: float = 1.0,
        progress_callback=None
    ) -> bool:
        """
        应用滤镜并调整音量

        Args:
            video_path: 输入视频路径
            output_path: 输出视频路径
            preset: 预设名称
            audio_volume: 音频音量 (0.0-2.0)
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            if progress_callback:
                progress_callback(0.1)

            # 确定滤镜
            if preset in cls.PRESETS:
                filter_chain = cls.PRESETS[preset][0]
            else:
                filter_chain = ""

            # 构建命令
            stream = ffmpeg.input(video_path)

            if filter_chain:
                # 有视频滤镜
                if audio_volume != 1.0:
                    stream = ffmpeg.output(
                        stream,
                        output_path,
                        vf=filter_chain,
                        af=f'volume={audio_volume}',
                        vcodec='libx264',
                        acodec='aac',
                        preset='fast'
                    )
                else:
                    stream = ffmpeg.output(
                        stream,
                        output_path,
                        vf=filter_chain,
                        vcodec='libx264',
                        acodec='copy',
                        preset='fast'
                    )
            else:
                # 无视频滤镜
                stream = ffmpeg.output(
                    stream,
                    output_path,
                    af=f'volume={audio_volume}',
                    vcodec='copy',
                    acodec='aac'
                )

            if progress_callback:
                progress_callback(0.3)

            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return True

        except Exception as e:
            print(f"Filter error: {e}")
            return False

    @classmethod
    def list_presets(cls) -> list[dict]:
        """列出所有预设"""
        return [
            {"name": name, "description": info[1]}
            for name, info in cls.PRESETS.items()
        ]

    @classmethod
    def get_filter_chain(cls, preset: str) -> str:
        """获取预设的滤镜链"""
        if preset in cls.PRESETS:
            return cls.PRESETS[preset][0]
        return ""


class FilterBuilder:
    """滤镜构建器 - 组合多个滤镜效果"""

    def __init__(self):
        self.filters = []

    def brightness(self, value: float) -> 'FilterBuilder':
        """亮度调整 (-1.0 到 1.0)"""
        self.filters.append(f"eq=brightness={value}")
        return self

    def contrast(self, value: float) -> 'FilterBuilder':
        """对比度调整 (0.5 到 2.0)"""
        self.filters.append(f"eq=contrast={value}")
        return self

    def saturation(self, value: float) -> 'FilterBuilder':
        """饱和度调整 (0.0 到 3.0)"""
        self.filters.append(f"eq=saturation={value}")
        return self

    def hue(self, value: float) -> 'FilterBuilder':
        """色调调整 (-180 到 180)"""
        self.filters.append(f"eq=hue={value}")
        return self

    def blur(self, radius: int = 2) -> 'FilterBuilder':
        """模糊"""
        self.filters.append(f"boxblur={radius}")
        return self

    def denoise(self, strength: int = 4) -> 'FilterBuilder':
        """降噪"""
        self.filters.append(f"hqdn3d={strength}")
        return self

    def vignette(self, angle: float = 0.5) -> 'FilterBuilder':
        """暗角"""
        self.filters.append(f"vignette=angle={angle}")
        return self

    def vintage(self) -> 'FilterBuilder':
        """复古"""
        self.filters.append("curves=vintage")
        return self

    def build(self) -> str:
        """构建滤镜链"""
        return ",".join(self.filters)


# 便捷函数
def apply_video_filter(
    video_path: str,
    output_path: str,
    preset: str = "none",
    progress_callback=None
) -> bool:
    """应用视频滤镜"""
    return VideoFilter.apply_filter(video_path, output_path, preset, None, progress_callback)


def apply_custom_filter(
    video_path: str,
    output_path: str,
    filter_chain: str,
    progress_callback=None
) -> bool:
    """应用自定义滤镜"""
    return VideoFilter.apply_filter(video_path, output_path, "none", filter_chain, progress_callback)
