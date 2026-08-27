"""
视频内容理解模块 - 基于 MiniMax-VL 多模态模型

深度分析视频内容：场景、人物、事件、情绪等
"""
import os
import math
import base64
import re
from pathlib import Path
from typing import Optional, Literal

from video.platforms import PLATFORM_SETTINGS
from settings import FFMPEG_PRESET_ANALYSIS


class VideoAnalyzer:
    """视频内容分析器"""

    # 视频场景分类
    SCENE_CATEGORIES = [
        "日常记录", "风景自然", "城市建筑", "人物访谈",
        "美食烹饪", "运动健身", "教育培训", "游戏电竞",
        "音乐舞蹈", "影视剪辑", "新闻资讯", "电商带货",
        "科技产品", "旅行日记", "宠物动物", "其他"
    ]

    # 情绪标签
    EMOTION_TAGS = [
        "欢快", "温馨", "浪漫", "紧张", "悬疑",
        "搞笑", "感人", "震撼", "平静", "焦虑",
        "愤怒", "悲伤", "兴奋", "神秘"
    ]

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化视频分析器

        Args:
            api_key: MiniMax API Key，默认从环境变量读取
        """
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.api_base = "https://api.minimax.chat/v1"

    def extract_frames(self, video_path: str, num_frames: int = 8) -> list[str]:
        """
        从视频中提取关键帧

        Args:
            video_path: 视频文件路径
            num_frames: 提取帧数

        Returns:
            帧图片路径列表
        """
        import ffmpeg
        import tempfile

        try:
            # 获取视频时长
            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])

            # 计算采样时间点
            interval = duration / (num_frames + 1)
            timestamps = [interval * (i + 1) for i in range(num_frames)]

            frames = []
            temp_dir = tempfile.mkdtemp()

            for i, ts in enumerate(timestamps):
                output_path = os.path.join(temp_dir, f"frame_{i:03d}.jpg")

                # 提取单帧
                stream = ffmpeg.input(video_path, ss=ts)
                stream = ffmpeg.output(stream, output_path, vframes=1, format='image2', vcodec='mjpeg')
                ffmpeg.run(stream, overwrite_output=True, quiet=True)

                if os.path.exists(output_path):
                    frames.append(output_path)

            return frames

        except Exception as e:
            print(f"Extract frames error: {e}")
            return []

    def encode_image(self, image_path: str) -> Optional[str]:
        """将图片编码为 base64"""
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"Encode image error: {e}")
            return None

    def analyze_with_minimax_vl(self, video_path: str, num_frames: int = 4) -> dict:
        """
        使用 MiniMax-VL 分析视频内容

        Args:
            video_path: 视频文件路径
            num_frames: 分析使用的帧数

        Returns:
            分析结果 {
                "scene": str,           # 场景分类
                "emotion": str,         # 情绪标签
                "description": str,     # 内容描述
                "highlights": list,     # 高光时刻
                "tags": list,           # 标签
                "suitable_platforms": list  # 适合的平台
            }
        """
        if not self.api_key:
            return self._fallback_analysis(video_path)

        try:
            import requests

            # 提取帧
            frames = self.extract_frames(video_path, num_frames)
            if not frames:
                return self._fallback_analysis(video_path)

            # 选择中间帧进行分析（通常最能代表视频内容）
            mid_frame = frames[len(frames) // 2]
            frame_base64 = self.encode_image(mid_frame)

            if not frame_base64:
                return self._fallback_analysis(video_path)

            # 调用 MiniMax VL API
            # 注意：这是通用调用方式，实际使用时需要确认 API 格式
            prompt = """请分析这张视频截图的内容：

1. 这是什么类型的视频？（场景分类）
2. 视频传达什么情绪/氛围？
3. 适合什么平台发布？（抖音/快手/B站/视频号）
4. 用3-5个标签描述内容

请用JSON格式返回：
{
    "scene": "场景分类",
    "emotion": "主要情绪",
    "description": "简短描述",
    "suitable_platforms": ["平台列表"],
    "tags": ["标签列表"]
}"""

            # 构建请求
            # MiniMax VL 具体 API 格式需要参考官方文档，这里使用通用格式
            payload = {
                "model": "MiniMax-VL-01",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame_base64}"}}
                        ]
                    }
                ],
                "max_tokens": 500
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return self._parse_analysis_result(content)
            else:
                print(f"API error: {response.status_code} - {response.text}")
                return self._fallback_analysis(video_path)

        except Exception as e:
            print(f"Minimax VL error: {e}")
            return self._fallback_analysis(video_path)

    def _parse_analysis_result(self, content: str) -> dict:
        """解析 API 返回的分析结果"""
        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                import json
                return json.loads(json_match.group())
        except Exception:
            pass

        # 解析失败，返回原始内容
        return {
            "scene": "其他",
            "emotion": "未知",
            "description": content[:200],
            "suitable_platforms": ["抖音", "快手"],
            "tags": ["视频"]
        }

    def _fallback_analysis(self, video_path: str) -> dict:
        """
        回退分析（无 API 或 API 失败时使用规则方法）

        Args:
            video_path: 视频文件路径

        Returns:
            基于规则的简单分析结果
        """
        import ffmpeg

        try:
            # 获取视频基本信息
            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])
            width = int(probe['streams'][0]['width'])
            height = int(probe['streams'][0]['height'])

            # 根据视频比例初步判断
            aspect_ratio = width / height if height > 0 else 1.0

            # 竖屏视频通常是短视频平台内容
            if aspect_ratio < 1.0:
                platforms = ["抖音", "快手", "视频号"]
                scene = "短视频内容"
            else:
                platforms = ["B站", "YouTube"]
                scene = "横屏视频"

            return {
                "scene": scene,
                "emotion": "未知",
                "description": f"视频时长{duration:.0f}秒，{width}x{height}分辨率",
                "highlights": [],
                "tags": ["视频"],
                "suitable_platforms": platforms,
                "duration": duration,
                "resolution": f"{width}x{height}",
                "aspect_ratio": aspect_ratio
            }

        except Exception as e:
            return {
                "scene": "其他",
                "emotion": "未知",
                "description": "视频分析失败",
                "highlights": [],
                "tags": ["视频"],
                "suitable_platforms": ["抖音"]
            }

    def analyze_video(
        self,
        video_path: str,
        use_api: bool = True,
        num_frames: int = 4,
        progress_callback=None
    ) -> dict:
        """
        完整视频分析

        Args:
            video_path: 视频文件路径
            use_api: 是否使用 API（False 则只用规则）
            num_frames: 分析帧数
            progress_callback: 进度回调

        Returns:
            完整分析结果
        """
        if progress_callback:
            progress_callback(0.1)

        if use_api and self.api_key:
            result = self.analyze_with_minimax_vl(video_path, num_frames)
        else:
            result = self._fallback_analysis(video_path)

        if progress_callback:
            progress_callback(1.0)

        return result


class PlatformAdapter:
    """平台适配器 - 输出不同平台的最佳格式"""

    # 从公共模块导入平台配置
    PLATFORMS = PLATFORM_SETTINGS

    @classmethod
    def get_recommended_settings(cls, platform: str) -> dict:
        """获取平台推荐设置"""
        return cls.PLATFORMS.get(platform.lower(), cls.PLATFORMS["douyin"])

    @classmethod
    def check_video_compatibility(cls, video_path: str, platform: str) -> dict:
        """
        检查视频是否兼容目标平台

        Args:
            video_path: 视频文件路径
            platform: 平台名称

        Returns:
            兼容性检查结果 {
                "compatible": bool,
                "issues": list,      # 不兼容问题列表
                "recommendations": list,  # 建议
                "current_settings": dict,  # 当前设置
                "target_settings": dict    # 目标平台设置
            }
        """
        import ffmpeg

        try:
            settings = cls.get_recommended_settings(platform)
            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])
            file_size = int(probe['format']['size'])
            stream = probe['streams'][0]
            width = int(stream['width'])
            height = int(stream['height'])
            aspect_ratio = width / height if height > 0 else 1.0

            issues = []
            recommendations = []

            # 检查时长
            if duration > settings["max_duration"]:
                issues.append(f"视频时长{duration:.0f}秒超过平台限制{settings['max_duration']}秒")
                recommendations.append("建议剪辑或分段")

            # 检查文件大小
            if file_size > settings["max_file_size"]:
                issues.append(f"文件大小{file_size/1024/1024:.0f}MB超过平台限制{settings['max_file_size']/1024/1024/1024:.0f}GB")
                recommendations.append("建议压缩或降低画质")

            # 检查比例
            target_ratios = [r[0]/r[1] for r in settings["aspect_ratios"]]
            if not any(abs(aspect_ratio - r) < 0.1 for r in target_ratios):
                # 将小数比例转换为分数形式显示
                def ratio_to_fraction(r):
                    for i in range(1, 20):
                        for j in range(1, 20):
                            if abs(i/j - r) < 0.01:
                                return f"{i}:{j}"
                    return f"{r:.2f}"
                current_ratio_str = ratio_to_fraction(aspect_ratio)
                issues.append(f"视频比例{current_ratio_str}不是平台推荐比例")
                # 找到最接近的推荐比例
                closest_ratio = min(target_ratios, key=lambda r: abs(aspect_ratio - r))
                # 找到对应的原始比例元组
                idx = target_ratios.index(closest_ratio)
                ratio_str = f"{int(settings['aspect_ratios'][idx][0])}:{int(settings['aspect_ratios'][idx][1])}"
                recommendations.append(f"建议转换为 {settings['recommended_resolution'][0]}x{settings['recommended_resolution'][1]} ({ratio_str})")

            return {
                "compatible": len(issues) == 0,
                "issues": issues,
                "recommendations": recommendations,
                "current_settings": {
                    "duration": duration,
                    "file_size_mb": file_size / 1024 / 1024,
                    "resolution": f"{width}x{height}",
                    "aspect_ratio": f"{width}x{height} ({width//math.gcd(width,height)}:{height//math.gcd(width,height)})" if width and height else "1:1"
                },
                "target_settings": {
                    "max_duration": settings["max_duration"],
                    "max_file_size_gb": settings["max_file_size"] / 1024 / 1024 / 1024,
                    "recommended_resolution": f"{settings['recommended_resolution'][0]}x{settings['recommended_resolution'][1]}",
                    "aspect_ratio": f"{int(settings['aspect_ratios'][0][0])}:{int(settings['aspect_ratios'][0][1])}",
                    "bitrate": settings["bitrate"] / 1000000
                }
            }

        except Exception as e:
            return {
                "compatible": False,
                "issues": [f"检查失败: {str(e)}"],
                "recommendations": [],
                "current_settings": {},
                "target_settings": {}
            }

    @classmethod
    def adapt_video(
        cls,
        video_path: str,
        output_path: str,
        platform: str,
        progress_callback=None
    ) -> bool:
        """
        适配视频到目标平台格式

        Args:
            video_path: 输入视频路径
            output_path: 输出视频路径
            platform: 目标平台
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            settings = cls.get_recommended_settings(platform)

            if progress_callback:
                progress_callback(0.1)

            # 获取输入视频信息
            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])
            stream = probe['streams'][0]
            input_width = int(stream['width'])
            input_height = int(stream['height'])

            # 计算目标分辨率
            target_width, target_height = settings["recommended_resolution"]

            if progress_callback:
                progress_callback(0.3)

            # 构建 FFmpeg 命令
            stream = ffmpeg.input(video_path)

            # 视频滤镜：缩放和填充
            vf = f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"

            output = ffmpeg.output(
                stream,
                output_path,
                vf=vf,
                vcodec='libx264',
                acodec='aac',
                b=settings["bitrate"],
                r=settings["fps"],
                preset=FFMPEG_PRESET_ANALYSIS,
                crf=23
            )

            ffmpeg.run(output, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return True

        except Exception as e:
            print(f"Adapt video error: {e}")
            return False


class CoverGenerator:
    """封面生成器 - 从视频提取精彩帧作为封面"""

    @staticmethod
    def extract_cover_frame(
        video_path: str,
        output_path: str,
        timestamp: Optional[float] = None,
        progress_callback=None
    ) -> bool:
        """
        提取封面帧

        Args:
            video_path: 视频文件路径
            output_path: 输出图片路径
            timestamp: 指定时间点（秒），None 则自动选择
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            if progress_callback:
                progress_callback(0.1)

            # 如果没有指定时间，使用视频的 1/4 处（通常是开场后的精彩内容）
            if timestamp is None:
                probe = ffmpeg.probe(video_path)
                duration = float(probe['format']['duration'])
                timestamp = duration * 0.25

            if progress_callback:
                progress_callback(0.3)

            # 提取帧
            stream = ffmpeg.input(video_path, ss=timestamp)
            stream = ffmpeg.output(stream, output_path, vframes=1, format='image2', vcodec='mjpeg', q=2)
            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return os.path.exists(output_path)

        except Exception as e:
            print(f"Extract cover error: {e}")
            return False

    @staticmethod
    def extract_multiple_candidates(
        video_path: str,
        output_dir: str,
        num_candidates: int = 5,
        progress_callback=None
    ) -> list[str]:
        """
        提取多个候选封面帧

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            num_candidates: 候选数量
            progress_callback: 进度回调

        Returns:
            候选封面路径列表
        """
        import ffmpeg
        import tempfile

        try:
            if progress_callback:
                progress_callback(0.1)

            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])

            # 在视频的不同位置采样：开头、中间、结尾附近
            positions = [0.1, 0.25, 0.4, 0.6, 0.75, 0.9]
            timestamps = [duration * p for p in positions[:num_candidates]]

            candidates = []
            os.makedirs(output_dir, exist_ok=True)

            for i, ts in enumerate(timestamps):
                output_path = os.path.join(output_dir, f"cover_candidate_{i+1}.jpg")

                if progress_callback:
                    progress_callback(0.1 + 0.8 * (i / len(timestamps)))

                stream = ffmpeg.input(video_path, ss=ts)
                stream = ffmpeg.output(stream, output_path, vframes=1, format='image2', vcodec='mjpeg', q=2)
                ffmpeg.run(stream, overwrite_output=True, quiet=True)

                if os.path.exists(output_path):
                    candidates.append(output_path)

            if progress_callback:
                progress_callback(1.0)

            return candidates

        except Exception as e:
            print(f"Extract candidates error: {e}")
            return []


class TitleGenerator:
    """片头片尾生成器"""

    # 片头模板
    OPENING_TEMPLATES = {
        "default": {
            "duration": 3.0,
            "text": "即将播出",
            "style": "fade_in"
        },
        "dynamic": {
            "duration": 2.5,
            "text": "START",
            "style": "slide"
        },
        "cinematic": {
            "duration": 4.0,
            "text": "",
            "style": "black"
        }
    }

    # 片尾模板
    ENDING_TEMPLATES = {
        "default": {
            "duration": 3.0,
            "text": "感谢观看",
            "style": "fade_out"
        },
        "subscribe": {
            "duration": 5.0,
            "text": "关注不迷路",
            "style": "subscribe"
        },
        "copyright": {
            "duration": 2.0,
            "text": "© 2024",
            "style": "simple"
        }
    }

    @staticmethod
    def create_opening(
        output_path: str,
        template: str = "default",
        duration: Optional[float] = None,
        text: Optional[str] = None,
        progress_callback=None
    ) -> bool:
        """
        创建片头

        Args:
            output_path: 输出视频路径
            template: 模板名称
            duration: 自定义时长
            text: 自定义文字
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            if progress_callback:
                progress_callback(0.1)

            tmpl = TitleGenerator.OPENING_TEMPLATES.get(template, TitleGenerator.OPENING_TEMPLATES["default"])
            dur = duration or tmpl["duration"]
            txt = text or tmpl["text"]

            # 创建纯色/文字片头
            if txt:
                # 使用 FFmpeg drawtext 创建文字片头
                stream = ffmpeg.input(f'color=c=black:s=1080x1920:d={dur}', f='lavfi')
                stream = ffmpeg.filter(stream, 'drawtext',
                                       text=txt,
                                       fontfile='C:/Windows/Fonts/simhei.ttf',
                                       fontsize=72,
                                       fontcolor='white',
                                       x='(w-text_w)/2',
                                       y='(h-text_h)/2',
                                       enable=f'between(t,0,{dur})')
            else:
                stream = ffmpeg.input(f'color=c=black:s=1080x1920:d={dur}', f='lavfi')

            output = ffmpeg.output(stream, output_path, vcodec='libx264', t=dur, an=None)
            ffmpeg.run(output, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return os.path.exists(output_path)

        except Exception as e:
            print(f"Create opening error: {e}")
            return False

    @staticmethod
    def create_ending(
        output_path: str,
        template: str = "default",
        duration: Optional[float] = None,
        text: Optional[str] = None,
        progress_callback=None
    ) -> bool:
        """
        创建片尾

        Args:
            output_path: 输出视频路径
            template: 模板名称
            duration: 自定义时长
            text: 自定义文字
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            if progress_callback:
                progress_callback(0.1)

            tmpl = TitleGenerator.ENDING_TEMPLATES.get(template, TitleGenerator.ENDING_TEMPLATES["default"])
            dur = duration or tmpl["duration"]
            txt = text or tmpl["text"]

            # 创建片尾
            stream = ffmpeg.input(f'color=c=black:s=1080x1920:d={dur}', f='lavfi')
            if txt:
                stream = ffmpeg.filter(stream, 'drawtext',
                                       text=txt,
                                       fontfile='C:/Windows/Fonts/simhei.ttf',
                                       fontsize=72,
                                       fontcolor='white',
                                       x='(w-text_w)/2',
                                       y='(h-text_h)/2')

            output = ffmpeg.output(stream, output_path, vcodec='libx264', t=dur, an=None)
            ffmpeg.run(output, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return os.path.exists(output_path)

        except Exception as e:
            print(f"Create ending error: {e}")
            return False

    @staticmethod
    def add_opening_to_video(
        video_path: str,
        output_path: str,
        opening_path: str,
        progress_callback=None
    ) -> bool:
        """
        将片头添加到视频

        Args:
            video_path: 原始视频路径
            output_path: 输出路径
            opening_path: 片头视频路径
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            if progress_callback:
                progress_callback(0.1)

            # 使用 concat 合并
            stream = ffmpeg.concat(
                ffmpeg.input(opening_path),
                ffmpeg.input(video_path),
                n=2,
                v=1,
                a=0
            )

            output = ffmpeg.output(stream, output_path, vcodec='copy', acodec='copy')
            ffmpeg.run(output, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return os.path.exists(output_path)

        except Exception as e:
            print(f"Add opening error: {e}")
            return False

    @staticmethod
    def add_watermark(
        video_path: str,
        output_path: str,
        watermark_text: str = "",
        watermark_position: str = "bottom_right",
        progress_callback=None
    ) -> bool:
        """
        添加水印

        Args:
            video_path: 视频路径
            output_path: 输出路径
            watermark_text: 水印文字
            watermark_position: 位置 (top_left/top_right/bottom_left/bottom_right/center)
            progress_callback: 进度回调

        Returns:
            是否成功
        """
        import ffmpeg

        try:
            if progress_callback:
                progress_callback(0.1)

            # 位置坐标
            positions = {
                "top_left": "10:10",
                "top_right": "W-tw-10:10",
                "bottom_left": "10:H-th-10",
                "bottom_right": "W-tw-10:H-th-10",
                "center": "(w-tw)/2:(h-th)/2"
            }

            pos = positions.get(watermark_position, positions["bottom_right"])

            stream = ffmpeg.input(video_path)
            stream = ffmpeg.filter(stream, 'drawtext',
                                   text=watermark_text,
                                   fontfile='C:/Windows/Fonts/simhei.ttf',
                                   fontsize=36,
                                   fontcolor='white@0.5',
                                   x=pos.split(':')[0],
                                   y=pos.split(':')[1] if ':' in pos else pos,
                                   enable='between(t,0,99999)')

            output = ffmpeg.output(stream, output_path, vcodec='libx264', acodec='copy', preset=FFMPEG_PRESET_ANALYSIS)
            ffmpeg.run(output, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback(1.0)

            return os.path.exists(output_path)

        except Exception as e:
            print(f"Add watermark error: {e}")
            return False


# 便捷函数
def analyze_video_content(video_path: str, use_api: bool = True) -> dict:
    """分析视频内容"""
    analyzer = VideoAnalyzer()
    return analyzer.analyze_video(video_path, use_api)


def check_platform_compatibility(video_path: str, platform: str) -> dict:
    """检查平台兼容性"""
    return PlatformAdapter.check_video_compatibility(video_path, platform)


def extract_video_cover(video_path: str, output_path: str, timestamp: float = None) -> bool:
    """提取视频封面"""
    return CoverGenerator.extract_cover_frame(video_path, output_path, timestamp)
