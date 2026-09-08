"""
剪映对接客户端 - 直接集成 pyJianYingDraft

无需单独启动 capcut-mate 服务，直接操作草稿 JSON
"""
import os
import sys
import json
import uuid
import datetime
import shutil
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 配置
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)

# 将 capcut-mate-main 添加到 Python 路径
_capcut_mate_path = Path(__file__).parent.parent / "capcut-mate-main"
if str(_capcut_mate_path) not in sys.path:
    sys.path.insert(0, str(_capcut_mate_path))

# 导入 pyJianYingDraft 核心模块
from src.pyJianYingDraft.draft_folder import DraftFolder
from src.pyJianYingDraft.script_file import ScriptFile
from src.pyJianYingDraft.track import TrackType

from .models import (
    CreateDraftRequest, CreateDraftResponse,
    SaveDraftRequest, SaveDraftResponse,
    GetDraftResponse,
    AddVideosRequest, AddVideosResponse,
    AddCaptionsRequest, AddCaptionsResponse,
    VideoInfo, CaptionInfo, WordInfo,
)

# 草稿存储目录（可配置）
DRAFT_DIR = os.environ.get("JIANYING_DRAFT_DIR", None)


class JianyingClient:
    """剪映草稿管理器 - 直接集成 pyJianYingDraft"""

    def __init__(self, draft_dir: Optional[str] = None):
        """
        初始化客户端

        Args:
            draft_dir: 草稿存储目录，默认使用环境变量 JIANYING_DRAFT_DIR
        """
        if draft_dir:
            self.draft_dir = Path(draft_dir)
        elif DRAFT_DIR:
            self.draft_dir = Path(DRAFT_DIR)
        else:
            self.draft_dir = Path(__file__).parent.parent / "capcut-mate-main" / "output" / "draft"

        self.draft_dir.mkdir(parents=True, exist_ok=True)
        self.draft_folder = DraftFolder(str(self.draft_dir))

    def _extract_draft_id(self, draft_url: str) -> Optional[str]:
        """从 draft_url 中提取 draft_id"""
        from src.utils import helper
        draft_id = helper.get_url_param(draft_url, "draft_id")
        return draft_id

    def _generate_draft_id(self) -> str:
        """生成草稿 ID"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{timestamp}{unique_id}"

    def create_draft(self, request: CreateDraftRequest) -> CreateDraftResponse:
        """创建剪映草稿"""
        draft_id = self._generate_draft_id()
        draft_url = f"http://localhost:8080/api/jianying/get_draft?draft_id={draft_id}"

        # 使用 DraftFolder 创建草稿
        script: ScriptFile = self.draft_folder.create_draft(
            draft_name=draft_id,
            width=request.width,
            height=request.height,
            fps=30,
            allow_replace=True,
        )

        # 保存草稿
        script.save()

        return CreateDraftResponse(draft_url=draft_url, draft_id=draft_id)

    def add_videos(self, request: AddVideosRequest) -> AddVideosResponse:
        """添加视频到草稿"""
        draft_id = self._extract_draft_id(request.draft_url)
        if not draft_id:
            return AddVideosResponse(success=False, message="Invalid draft_url")

        try:
            # 加载草稿
            script: ScriptFile = self.draft_folder.load_template(draft_id)

            # 创建视频轨道并添加视频
            track_name = f"video_track_{uuid.uuid4().hex[:8]}"
            script.add_track_ordered(track_type=TrackType.video, track_name=track_name)

            for video_info in request.videos:
                # 构造视频素材
                from src.pyJianYingDraft.local_materials import VideoMaterial
                from src.pyJianYingDraft.video_segment import VideoSegment
                from src.pyJianYingDraft.time_util import Timerange

                # 下载或使用本地视频
                video_path = self._prepare_video(video_info.video_url, draft_id)

                # 创建视频素材
                video_material = VideoMaterial(path=video_path)
                script.add_material(video_material)

                # 创建视频片段
                duration = video_info.end - video_info.start
                t_range = Timerange(start=video_info.start, duration=duration)
                segment = VideoSegment(
                    material=video_material,
                    target_timerange=t_range,
                )

                # 添加转场
                if video_info.transition:
                    from src.pyJianYingDraft.metadata.transition_meta import TransitionType
                    try:
                        trans = TransitionType.from_name(video_info.transition)
                        segment.add_transition(trans, duration=video_info.transition_duration if video_info.transition_duration else 1500000)
                    except:
                        pass

                # 添加到轨道
                script.add_segment(segment, track_name)

            # 保存草稿
            script.save()

            return AddVideosResponse(success=True, message=f"Added {len(request.videos)} videos")

        except Exception as e:
            import traceback
            traceback.print_exc()
            return AddVideosResponse(success=False, message=str(e))

    def _prepare_video(self, video_url: str, draft_id: str) -> str:
        """准备视频文件，返回本地路径"""
        from src.utils.download import download

        # 如果是 file:// URL，直接返回路径
        if video_url.startswith("file://"):
            # 去掉 file:// 前缀，可能是 file:///, file:///, file://// 等
            path = video_url[7:]  # 去掉 file://
            # 去掉开头的 / 或 \\（Windows路径不能以斜杠开头）
            while path.startswith("/") or path.startswith("\\"):
                path = path[1:]
            # 处理 URL 编码的路径
            path = path.replace("/", "\\")
            return os.path.normpath(path)

        # 如果是本地文件，直接返回
        if os.path.exists(video_url):
            return os.path.normpath(video_url)

        # 否则下载
        draft_video_dir = os.path.join(self.draft_dir, draft_id, "assets", "videos")
        os.makedirs(draft_video_dir, exist_ok=True)
        return download(video_url, draft_video_dir)

    def add_captions(self, request: AddCaptionsRequest) -> AddCaptionsResponse:
        """添加字幕到草稿"""
        draft_id = self._extract_draft_id(request.draft_url)
        if not draft_id:
            return AddCaptionsResponse(success=False, message="Invalid draft_url")

        try:
            # 加载草稿
            script: ScriptFile = self.draft_folder.load_template(draft_id)

            # 创建字幕轨道
            track_name = f"text_track_{uuid.uuid4().hex[:8]}"
            script.add_track_ordered(track_type=TrackType.text, track_name=track_name)

            from src.pyJianYingDraft.text_segment import TextSegment, TextStyle
            from src.pyJianYingDraft.time_util import Timerange

            for caption in request.captions:
                # 创建字幕样式
                # 转换 hex 颜色到 RGB 元组
                hex_color = request.text_color.lstrip('#')
                r = int(hex_color[0:2], 16) / 255.0
                g = int(hex_color[2:4], 16) / 255.0
                b = int(hex_color[4:6], 16) / 255.0

                style = TextStyle(
                    size=float(request.font_size),
                    color=(r, g, b),
                )

                # 获取字体
                font = None
                if request.font:
                    from src.pyJianYingDraft.metadata import FontType
                    try:
                        font = FontType.from_name(request.font)
                    except:
                        pass

                # 创建字幕片段，transform_y=-0.8 将字幕移到窗口下方
                from src.pyJianYingDraft.segment import ClipSettings
                clip_settings = ClipSettings(transform_y=-0.8)

                duration = caption.end - caption.start
                t_range = Timerange(start=caption.start, duration=duration)
                segment = TextSegment(
                    text=caption.text,
                    timerange=t_range,
                    font=font,
                    style=style,
                    clip_settings=clip_settings,
                )

                script.add_segment(segment, track_name)

            # 保存草稿
            script.save()

            return AddCaptionsResponse(success=True, message=f"Added {len(request.captions)} captions")

        except Exception as e:
            import traceback
            traceback.print_exc()
            return AddCaptionsResponse(success=False, message=str(e))

    def save_draft(self, request: SaveDraftRequest) -> SaveDraftResponse:
        """保存草稿"""
        draft_id = self._extract_draft_id(request.draft_url)
        if not draft_id:
            return SaveDraftResponse(success=False)

        try:
            script = self.draft_folder.load_template(draft_id)
            script.save()
            return SaveDraftResponse(success=True)
        except Exception as e:
            print(f"Save draft error: {e}")
            return SaveDraftResponse(success=False)

    def get_draft(self, draft_url: str) -> GetDraftResponse:
        """获取草稿信息"""
        draft_id = self._extract_draft_id(draft_url)
        if not draft_id:
            raise ValueError("Invalid draft_url")
        return GetDraftResponse(draft_url=draft_url, draft_id=draft_id)
