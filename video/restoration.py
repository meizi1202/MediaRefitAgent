"""
老视频修复 - 核心数据模型

定义修复套餐、参数选项、请求/响应数据结构
"""
from dataclasses import dataclass, field
from typing import Optional, Literal, Callable
from enum import Enum


class RestorationPreset(str, Enum):
    """修复套餐"""
    BASIC = "basic"        # 基础修复：去噪、去抖动、色彩、对比度
    FILM = "film"          # 胶片修复：基础 + 划痕、闪烁
    ENHANCED = "enhanced"  # 增强版：完整 + 补帧、超分
    CUSTOM = "custom"      # 自定义


class DenoiseLevel(str, Enum):
    """去噪级别"""
    LIGHT = "light"     # 轻度
    MEDIUM = "medium"   # 中度
    STRONG = "strong"   # 强力


class DeblurLevel(str, Enum):
    """去抖动级别"""
    LIGHT = "light"
    MEDIUM = "medium"
    STRONG = "strong"


@dataclass(frozen=True)
class RestorationOptions:
    """修复选项"""
    # 基础修复
    denoise: bool = False
    denoise_level: DenoiseLevel = DenoiseLevel.MEDIUM

    deblur: bool = False
    deblur_level: DeblurLevel = DeblurLevel.MEDIUM

    color_correct: bool = False
    saturation: int = 0  # -100 ~ +100

    contrast_enhance: bool = False
    contrast_level: float = 1.0  # 0.5 ~ 2.0

    # 胶片修复
    scratch_remove: bool = False
    scratch_level: str = "medium"

    flicker_remove: bool = False
    flicker_level: str = "medium"

    # 增强升级
    interpolate: bool = False
    target_fps: int = 60

    super_resolution: bool = False
    scale_factor: int = 2  # 2x or 4x


@dataclass(frozen=True)
class RestorationRequest:
    """修复请求"""
    input_path: str
    output_path: str
    preset: RestorationPreset = RestorationPreset.BASIC
    options: Optional[RestorationOptions] = field(default_factory=RestorationOptions)
    progress_callback: Optional[Callable[[str, float], None]] = None  # (stage, progress) -> None


@dataclass(frozen=True)
class RestorationStageResult:
    """单个修复阶段结果"""
    stage: str
    success: bool
    input_path: str
    output_path: str
    duration: float
    error: Optional[str] = None


@dataclass(frozen=True)
class RestorationResult:
    """修复结果"""
    success: bool
    input_path: str
    output_path: str
    preset: str
    stages: list[RestorationStageResult]
    total_duration: float
    output_size: int
    error: Optional[str] = None


def get_default_options_for_preset(preset: RestorationPreset) -> RestorationOptions:
    """根据套餐返回默认选项"""
    if preset == RestorationPreset.BASIC:
        return RestorationOptions(
            denoise=True,
            denoise_level=DenoiseLevel.MEDIUM,
            deblur=True,
            deblur_level=DeblurLevel.MEDIUM,
            color_correct=True,
            saturation=10,
            contrast_enhance=True,
            contrast_level=1.1,
        )
    elif preset == RestorationPreset.FILM:
        return RestorationOptions(
            denoise=True,
            denoise_level=DenoiseLevel.MEDIUM,
            deblur=True,
            deblur_level=DeblurLevel.MEDIUM,
            color_correct=True,
            saturation=10,
            contrast_enhance=True,
            contrast_level=1.1,
            scratch_remove=True,
            scratch_level="medium",
            flicker_remove=True,
            flicker_level="medium",
        )
    elif preset == RestorationPreset.ENHANCED:
        return RestorationOptions(
            denoise=True,
            denoise_level=DenoiseLevel.MEDIUM,
            deblur=True,
            deblur_level=DeblurLevel.MEDIUM,
            color_correct=True,
            saturation=15,
            contrast_enhance=True,
            contrast_level=1.2,
            scratch_remove=True,
            scratch_level="medium",
            flicker_remove=True,
            flicker_level="medium",
            interpolate=True,
            target_fps=60,
            super_resolution=True,
            scale_factor=2,
        )
    else:  # CUSTOM
        return RestorationOptions()
