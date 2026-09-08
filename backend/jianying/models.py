"""
剪映对接数据模型
"""
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class CreateDraftRequest:
    width: int = 1920
    height: int = 1080


@dataclass
class CreateDraftResponse:
    draft_url: str
    draft_id: str


@dataclass
class SaveDraftRequest:
    draft_url: str


@dataclass
class SaveDraftResponse:
    success: bool


@dataclass
class VideoInfo:
    video_url: str
    start: int  # 微秒
    end: int    # 微秒
    transition: Optional[str] = None
    transition_duration: Optional[int] = None  # 微秒


@dataclass
class AddVideosRequest:
    draft_url: str
    videos: List[VideoInfo]


@dataclass
class AddVideosResponse:
    success: bool
    message: str


@dataclass
class CaptionInfo:
    text: str
    start: int  # 微秒
    end: int    # 微秒
    words: Optional[List["WordInfo"]] = None


@dataclass
class WordInfo:
    word: str
    start: float  # 秒
    end: float    # 秒


@dataclass
class AddCaptionsRequest:
    draft_url: str
    captions: List[CaptionInfo]
    text_color: str = "#FFFFFF"
    font_size: int = 10
    font: str = "思源黑体"
    char_level_highlight: bool = False


@dataclass
class AddCaptionsResponse:
    success: bool
    message: str


@dataclass
class GetDraftResponse:
    draft_url: str
    draft_id: str
