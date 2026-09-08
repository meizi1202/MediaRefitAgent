"""
剪映草稿 JSON 生成器

用于生成符合剪映格式的草稿文件，实现方案 E：
系统生成草稿 JSON → 用户导入剪映渲染 → 100% 保留剪映效果

主要功能：
- 从 Whisper ASR 结果生成字幕轨道 JSON
- 支持从剪映模板 JSON 读取字幕样式
- 生成完整的草稿文件结构
"""
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SubtitleStyle:
    """字幕样式配置（对应剪映的字幕样式）"""
    font: str = "新青年体"              # 字体名称
    font_size: int = 10                  # 字号（剪映中的点数）
    color: str = "#70a19c"              # 文字颜色 (RGB hex，无#号)
    background: str = ""                 # 背景颜色 (ARGB hex，无背景则为空)
    stroke_color: str = ""               # 描边颜色
    stroke_width: float = 0              # 描边宽度
    position: str = "center"            # 位置: center / bottom_center / top_center
    letter_spacing: float = 0            # 字间距
    line_spacing: float = 0             # 行间距
    alignment: str = "center"           # 对齐方式: left / center / right
    bold: bool = False                   # 是否加粗
    italic: bool = False                 # 是否斜体

    def to_jap_style(self) -> dict:
        """转换为剪映草稿 JSON 格式"""
        return {
            "font": self.font,
            "font_size": self.font_size,
            "color": self.color,
            "background": self.background,
            "stroke_color": self.stroke_color,
            "stroke_width": self.stroke_width,
            "position": self.position,
            "letter_spacing": self.letter_spacing,
            "line_spacing": self.line_spacing,
            "alignment": self.alignment,
            "bold": self.bold,
            "italic": self.italic,
        }


@dataclass
class SubtitleClip:
    """字幕片段"""
    content: str                          # 字幕文本内容
    start_time_ms: int                   # 开始时间（毫秒）
    end_time_ms: int                    # 结束时间（毫秒）
    style: Optional[SubtitleStyle] = None  # 字幕样式

    def to_jap_clip(self, clip_id: str) -> dict:
        """转换为剪映草稿 JSON 格式"""
        style_dict = self.style.to_jap_style() if self.style else SubtitleStyle().to_jap_style()

        # 剪映文本轨道片段格式
        return {
            "id": clip_id,
            "type": "text",
            "start_time": self.start_time_ms,
            "end_time": self.end_time_ms,
            "content": self.content,
            "style": style_dict,
            # 剪映特有字段
            "animate": {
                "in": "fade",
                "out": "fade",
                "duration": 300
            }
        }


@dataclass
class JianYingDraft:
    """剪映草稿结构"""
    project_id: str = "generated_project"
    name: str = "Generated Draft"
    duration_ms: int = 0                 # 总时长（毫秒）
    aspect_ratio: str = "9:16"          # 画幅
    width: int = 1080                   # 分辨率宽
    height: int = 1920                   # 分辨率高
    subtitle_clips: list[SubtitleClip] = field(default_factory=list)
    text_tracks: list[dict] = field(default_factory=list)  # 已构建的文本轨道

    def build_text_track(self) -> dict:
        """
        构建文本轨道（对应剪映的 text_track）

        剪映的 tracks 结构：
        {
            "type": "text",
            "clips": [...]
        }
        """
        clips = []
        for i, clip in enumerate(self.subtitle_clips):
            clip_id = f"subtitle_{i:03d}"
            clips.append(clip.to_jap_clip(clip_id))

        return {
            "type": "text",
            "id": "text_track_0",
            "clips": clips
        }

    def to_jap_dict(self) -> dict:
        """
        生成完整的剪映草稿 JSON 字典

        返回符合剪映草稿格式的字典结构
        """
        # 构建文本轨道
        text_track = self.build_text_track()

        # 完整草稿结构
        draft = {
            "project_id": self.project_id,
            "name": self.name,
            "duration": self.duration_ms,
            "aspect_ratio": self.aspect_ratio,
            "width": self.width,
            "height": self.height,
            "tracks": [text_track],
            "version": "1.0",
            "generate_time": self._get_timestamp()
        }

        return draft

    def _get_timestamp(self) -> int:
        """获取当前时间戳（毫秒）"""
        import time
        return int(time.time() * 1000)


def generate_subtitle_track_from_asr(
    asr_segments: list[dict],
    style: Optional[SubtitleStyle] = None,
    clip_id_prefix: str = "subtitle"
) -> list[SubtitleClip]:
    """
    从 Whisper ASR 结果生成字幕片段列表

    Args:
        asr_segments: Whisper ASR 返回的片段列表
                      格式: [{"start": 0.0, "end": 5.0, "text": "今天..."}]
        style: 字幕样式（可选，使用默认样式）
        clip_id_prefix: clip ID 前缀

    Returns:
        SubtitleClip 列表
    """
    subtitle_clips = []

    for i, seg in enumerate(asr_segments):
        # 跳过空文本
        text = seg.get("text", "").strip()
        if not text:
            continue

        # 跳过过短的片段（小于 0.3 秒）
        duration = seg["end"] - seg["start"]
        if duration < 0.3:
            continue

        clip = SubtitleClip(
            content=text,
            start_time_ms=int(seg["start"] * 1000),
            end_time_ms=int(seg["end"] * 1000),
            style=style or SubtitleStyle()
        )
        subtitle_clips.append(clip)

    return subtitle_clips


def create_jianying_draft(
    asr_segments: list[dict],
    project_name: str = "Generated Draft",
    style: Optional[SubtitleStyle] = None,
    aspect_ratio: str = "9:16",
    resolution: tuple = (1080, 1920)
) -> JianYingDraft:
    """
    创建剪映草稿（快捷函数）

    Args:
        asr_segments: Whisper ASR 返回的片段列表
        project_name: 项目名称
        style: 字幕样式（可选，使用默认样式）
        aspect_ratio: 画幅 (9:16 / 16:9 / 1:1)
        resolution: 分辨率 (宽, 高)

    Returns:
        JianYingDraft 对象
    """
    # 计算总时长
    max_end = max((seg["end"] for seg in asr_segments), default=0)

    # 生成字幕片段
    subtitle_clips = generate_subtitle_track_from_asr(asr_segments, style)

    # 创建草稿
    draft = JianYingDraft(
        project_id=f"project_{int(max_end * 1000)}",
        name=project_name,
        duration_ms=int(max_end * 1000) + 1000,  # 多加 1 秒缓冲
        aspect_ratio=aspect_ratio,
        width=resolution[0],
        height=resolution[1],
        subtitle_clips=subtitle_clips
    )

    return draft


def export_draft_to_json(draft: JianYingDraft, output_path: str) -> str:
    """
    导出草稿为 JSON 文件

    Args:
        draft: JianYingDraft 对象
        output_path: 输出 JSON 文件路径

    Returns:
        输出文件路径
    """
    jap_dict = draft.to_jap_dict()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(jap_dict, f, indent=2, ensure_ascii=False)

    return output_path


def export_draft_to_jap(
    draft: JianYingDraft,
    output_path: str,
    materials_dir: Optional[str] = None
) -> str:
    """
    导出草稿为 .jap 文件（ZIP 压缩格式）

    Args:
        draft: JianYingDraft 对象
        output_path: 输出 .jap 文件路径
        materials_dir: 素材目录路径（可选，用于复制素材到 jap）

    Returns:
        输出文件路径
    """
    import tempfile
    import shutil

    # 创建临时目录
    temp_dir = tempfile.mkdtemp()

    try:
        # 生成 project.json
        jap_dict = draft.to_jap_dict()
        project_json_path = Path(temp_dir) / "project.json"
        with open(project_json_path, "w", encoding="utf-8") as f:
            json.dump(jap_dict, f, indent=2, ensure_ascii=False)

        # 如果有素材目录，复制到临时目录
        if materials_dir and Path(materials_dir).exists():
            materials_dest = Path(temp_dir) / "material"
            shutil.copytree(materials_dir, materials_dest)

        # 创建 ZIP 文件
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # 添加 project.json
            zipf.write(project_json_path, "project.json")

            # 添加素材目录中的文件
            if materials_dir and Path(materials_dir).exists():
                for file_path in Path(materials_dir).rglob("*"):
                    if file_path.is_file():
                        arcname = f"material/{file_path.name}"
                        zipf.write(file_path, arcname)

        return output_path

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)


def parse_jianying_style_from_json(jap_json: dict) -> SubtitleStyle:
    """
    从剪映草稿 JSON 中提取字幕样式

    Args:
        jap_json: 剪映草稿 JSON 字典

    Returns:
        SubtitleStyle 对象
    """
    # 遍历 tracks 找到 text track
    for track in jap_json.get("tracks", []):
        if track.get("type") == "text" and track.get("clips"):
            # 获取第一个 clip 的样式
            first_clip = track["clips"][0]
            style_dict = first_clip.get("style", {})

            return SubtitleStyle(
                font=style_dict.get("font", "STHeitiMedium"),
                font_size=style_dict.get("font_size", 36),
                color=style_dict.get("color", "#FFFFFF"),
                background=style_dict.get("background", "#00000080"),
                stroke_color=style_dict.get("stroke_color", "#000000"),
                stroke_width=style_dict.get("stroke_width", 1.0),
                bold=style_dict.get("bold", False),
                italic=style_dict.get("italic", False),
            )

    # 默认样式
    return SubtitleStyle()


def load_jap_file(jap_path: str) -> dict:
    """
    加载并解析 .jap 文件

    Args:
        jap_path: .jap 文件路径

    Returns:
        草稿 JSON 字典
    """
    with zipfile.ZipFile(jap_path, "r") as zipf:
        # 查找 JSON 文件
        for name in zipf.namelist():
            if name.endswith(".json"):
                with zipf.open(name) as f:
                    return json.load(f)

    raise ValueError(f"No JSON file found in {jap_path}")


# ============ 便捷函数 ============

def generate_subtitle_json_from_video(
    video_path: str,
    output_json_path: str,
    model_size: str = "base",
    language: str = "zh",
    style: Optional[SubtitleStyle] = None
) -> str:
    """
    从视频生成字幕 JSON（快捷函数）

    完整流程：提取音频 → Whisper 识别 → 生成剪映字幕 JSON

    Args:
        video_path: 视频文件路径
        output_json_path: 输出的 JSON 文件路径
        model_size: Whisper 模型大小
        language: 语言
        style: 字幕样式（可选）

    Returns:
        输出的 JSON 文件路径
    """
    import tempfile
    from .funclip_wrapper import full_transcribe_pipeline

    # 创建临时目录
    temp_dir = tempfile.mkdtemp()

    try:
        # Step 1: 语音识别
        result = full_transcribe_pipeline(
            video_path=video_path,
            output_dir=temp_dir,
            model_size=model_size,
            language=language
        )

        if not result:
            raise RuntimeError("Speech recognition failed")

        # Step 2: 生成剪映草稿
        draft = create_jianying_draft(
            asr_segments=result.segments,
            project_name=Path(video_path).stem,
            style=style
        )

        # Step 3: 导出 JSON
        return export_draft_to_json(draft, output_json_path)

    finally:
        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
