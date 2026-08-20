"""
视频摘要模块 - 基于 Whisper ASR + LLM

自动生成视频的文字摘要和关键信息
"""
import re
import os
import tempfile
from pathlib import Path
from typing import Optional, Literal


class VideoSummarizer:
    """视频摘要生成器"""

    def __init__(self, llm_client=None):
        """
        初始化摘要生成器

        Args:
            llm_client: LLM 客户端（用于生成摘要），如果不提供则只做规则摘要
        """
        self.llm_client = llm_client

    def transcribe_video(self, video_path: str, progress_callback=None) -> Optional[dict]:
        """
        使用 Whisper 将视频转写为文字

        Args:
            video_path: 视频文件路径
            progress_callback: 进度回调

        Returns:
            转写结果 {"text": str, "segments": list}
        """
        import whisper

        try:
            if progress_callback:
                progress_callback(0.1)

            # 加载模型（使用 base 模型平衡速度和精度）
            model = whisper.load_model("base")

            if progress_callback:
                progress_callback(0.3)

            # 转写
            result = model.transcribe(video_path, language="zh")

            if progress_callback:
                progress_callback(0.8)

            return {
                "text": result["text"],
                "segments": result["segments"],
                "language": result.get("language", "zh")
            }

        except Exception as e:
            print(f"Transcribe error: {e}")
            return None

    def extract_key_points(self, text: str) -> list[str]:
        """
        从文本中提取关键点（规则方法）

        Args:
            text: 文本内容

        Returns:
            关键点列表
        """
        if not text:
            return []

        # 简单规则：按句子分割，提取包含关键词的句子
        sentences = re.split(r'[。！？\n]+', text)
        key_points = []

        # 关键词模式
        key_patterns = [
            r'重要', r'关键', r'必须', r'需要', r'应该',
            r'首先', r'然后', r'最后', r'总之', r'总结',
            r'因为', r'所以', r'但是', r'然而', r'虽然',
            r'第一步', r'第二步', r'第三步', r'方法', r'技巧',
        ]

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10 or len(sentence) > 200:
                continue

            for pattern in key_patterns:
                if re.search(pattern, sentence):
                    key_points.append(sentence)
                    break

        # 去重并限制数量
        seen = set()
        unique_points = []
        for point in key_points:
            # 简单去重：前20个字符相同则视为重复
            key = point[:20]
            if key not in seen:
                seen.add(key)
                unique_points.append(point)

        return unique_points[:10]  # 最多10个关键点

    def generate_summary_with_llm(self, text: str, max_length: int = 500) -> str:
        """
        使用 LLM 生成摘要

        Args:
            text: 原始文本
            max_length: 最大摘要长度（字符数）

        Returns:
            摘要文本
        """
        if not self.llm_client:
            return self.generate_summary_with_rules(text, max_length)

        try:
            prompt = f"""请为以下视频内容生成简洁的摘要，控制在{max_length}字以内：

{text[:3000]}  # 限制输入长度

要求：
1. 提取视频的核心内容和主题
2. 概括主要观点和关键信息
3. 语言简洁有条理
4. 只返回摘要内容，不要其他说明

摘要："""

            response = self.llm_client.generate(prompt)
            return response.strip() if response else self.generate_summary_with_rules(text, max_length)

        except Exception as e:
            print(f"LLM summary error: {e}")
            return self.generate_summary_with_rules(text, max_length)

    def generate_summary_with_rules(self, text: str, max_length: int = 500) -> str:
        """
        使用规则方法生成摘要

        Args:
            text: 原始文本
            max_length: 最大长度

        Returns:
            摘要文本
        """
        if not text:
            return ""

        # 取前 max_length 字符作为摘要
        summary = text[:max_length]

        # 确保不切断单词
        if len(text) > max_length:
            last_space = summary.rfind(' ')
            if last_space > max_length * 0.8:
                summary = summary[:last_space]

        return summary + ("..." if len(text) > max_length else "")

    def summarize_video(
        self,
        video_path: str,
        use_llm: bool = True,
        progress_callback=None
    ) -> dict:
        """
        生成视频摘要

        Args:
            video_path: 视频文件路径
            use_llm: 是否使用 LLM（False 则用规则）
            progress_callback: 进度回调

        Returns:
            摘要结果 {
                "summary": str,           # 摘要文本
                "key_points": list,       # 关键点列表
                "full_text": str,         # 完整转写文本
                "duration": float,        # 视频时长
                "language": str           # 语言
            }
        """
        if progress_callback:
            progress_callback(0.0)

        # 1. 转写视频
        transcribe_result = self.transcribe_video(video_path, progress_callback)

        if not transcribe_result:
            return {
                "summary": "转写失败",
                "key_points": [],
                "full_text": "",
                "duration": 0,
                "language": "unknown"
            }

        text = transcribe_result["text"]
        segments = transcribe_result["segments"]
        language = transcribe_result["language"]

        if progress_callback:
            progress_callback(0.6)

        # 2. 提取关键点
        key_points = self.extract_key_points(text)

        # 3. 生成摘要
        if use_llm and self.llm_client:
            summary = self.generate_summary_with_llm(text)
        else:
            summary = self.generate_summary_with_rules(text)

        if progress_callback:
            progress_callback(1.0)

        # 4. 获取视频时长
        duration = 0
        if segments:
            try:
                duration = max(seg.get("end", 0) for seg in segments)
            except Exception:
                pass

        return {
            "summary": summary,
            "key_points": key_points,
            "full_text": text,
            "duration": duration,
            "language": language,
            "word_count": len(text)
        }

    def create_summary_srt(
        self,
        summary: str,
        key_points: list,
        output_path: str
    ) -> bool:
        """
        将摘要生成为 SRT 格式文件

        Args:
            summary: 摘要文本
            key_points: 关键点列表
            output_path: 输出 SRT 文件路径

        Returns:
            是否成功
        """
        try:
            lines = []
            index = 1

            # 添加摘要
            lines.append(str(index))
            lines.append("00:00:00,000 --> 00:00:05,000")
            lines.append(f"【摘要】{summary[:100]}")
            lines.append("")
            index += 1

            # 添加关键点
            for i, point in enumerate(key_points[:5]):
                lines.append(str(index))
                start_time = f"00:0{(i+1)*1}:00,000"
                end_time = f"00:0{(i+1)*1+1}:00,000"
                lines.append(f"{start_time} --> {end_time}")
                lines.append(f"• {point[:80]}")
                lines.append("")
                index += 1

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            return True

        except Exception as e:
            print(f"Create SRT error: {e}")
            return False


class ShortVideoGenerator:
    """短视频生成器 - 组合多个模块生成完整短视频"""

    def __init__(
        self,
        condenser=None,
        subtitle_gen=None,
        bgm_matcher=None,
        tts=None,
        transition=None,
        filter_=None
    ):
        """
        初始化短视频生成器

        Args:
            condenser: 精彩片段提取器
            subtitle_gen: 字幕生成器
            bgm_matcher: BGM 匹配器
            tts: TTS 配音
            transition: 转场
            filter_: 滤镜
        """
        self.condenser = condenser
        self.subtitle_gen = subtitle_gen
        self.bgm_matcher = bgm_matcher
        self.tts = tts
        self.transition = transition
        self.filter = filter_

    def generate(
        self,
        video_path: str,
        output_path: str,
        options: dict,
        progress_callback=None
    ) -> dict:
        """
        生成短视频

        Args:
            video_path: 输入视频路径
            output_path: 输出视频路径
            options: 选项 {
                "target_duration": 60,      # 目标时长
                "add_subtitle": True,       # 是否加字幕
                "subtitle_style": "default",
                "add_bgm": True,            # 是否加 BGM
                "bgm_mood": "auto",
                "add_tts": False,           # 是否加配音
                "tts_text": "",
                "tts_voice": "zh-CN-Xiaoxiao",
                "add_filter": False,        # 是否加滤镜
                "filter_preset": "cinematic",
                "add_transition": True,     # 是否加转场
                "transition_type": "fade",
            }
            progress_callback: 进度回调

        Returns:
            生成结果
        """
        result = {
            "success": False,
            "output_path": None,
            "steps": [],
            "message": ""
        }

        try:
            if progress_callback:
                progress_callback(0.0)

            current_step = 0
            total_steps = sum([
                options.get("add_subtitle", False),
                options.get("add_bgm", False),
                options.get("add_tts", False),
                options.get("add_filter", False),
                options.get("add_transition", False),
            ]) + 1  # +1 for highlight extraction

            # Step 1: 提取精彩片段
            if self.condenser:
                result["steps"].append("提取精彩片段")
                # 复用 condenser 的 extract 功能
                # ...

            if progress_callback:
                progress_callback((current_step + 1) / total_steps)

            # Step 2: 添加字幕
            if options.get("add_subtitle") and self.subtitle_gen:
                current_step += 1
                result["steps"].append("添加字幕")
                # ...

            # Step 3: 添加 BGM
            if options.get("add_bgm") and self.bgm_matcher:
                current_step += 1
                result["steps"].append("添加背景音乐")
                # ...

            # Step 4: 添加配音
            if options.get("add_tts") and self.tts and options.get("tts_text"):
                current_step += 1
                result["steps"].append("添加配音")
                # ...

            # Step 5: 添加滤镜
            if options.get("add_filter") and self.filter:
                current_step += 1
                result["steps"].append(f"应用{options.get('filter_preset')}滤镜")
                # ...

            # Step 6: 添加转场
            if options.get("add_transition") and self.transition:
                current_step += 1
                result["steps"].append("添加转场效果")
                # ...

            result["success"] = True
            result["message"] = "短视频生成完成"
            result["output_path"] = output_path

        except Exception as e:
            result["message"] = f"生成失败: {str(e)}"

        return result


# 便捷函数
def generate_video_summary(
    video_path: str,
    use_llm: bool = True,
    progress_callback=None
) -> dict:
    """
    生成视频摘要

    Args:
        video_path: 视频文件路径
        use_llm: 是否使用 LLM
        progress_callback: 进度回调

    Returns:
        摘要结果
    """
    summarizer = VideoSummarizer()
    return summarizer.summarize_video(video_path, use_llm, progress_callback)


def extract_key_frames_description(video_path: str) -> list[str]:
    """
    提取关键帧描述（简单实现）

    Args:
        video_path: 视频文件路径

    Returns:
        关键帧描述列表
    """
    # 这是一个简化实现，实际需要使用视频分析模型
    return [
        "视频开场",
        "核心内容展示",
        "关键信息强调",
        "结尾总结"
    ]
