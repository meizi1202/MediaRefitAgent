"""
视频方向检测模块

策略：
1. 优先使用 FFprobe 元数据（最快，最准确如果有元数据）
2. 如果元数据缺失或不确定，使用简单帧分析
3. 预留 YOLO 主体检测接口（未来扩展）
"""
import numpy as np
from typing import Optional
from enum import Enum

from video.processor import get_video_metadata, Orientation


class DetectionConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OrientationResult:
    """方向检测结果"""

    def __init__(
        self,
        orientation: Orientation,
        confidence: DetectionConfidence,
        rotation_angle: Optional[int] = None,
        method: str = "metadata",
    ):
        self.orientation = orientation
        self.confidence = confidence
        self.rotation_angle = rotation_angle
        self.method = method

    def __repr__(self):
        return f"OrientationResult({self.orientation}, confidence={self.confidence.value}, method={self.method})"


def detect_orientation(video_path: str, use_ml: bool = False) -> OrientationResult:
    """
    检测视频方向

    Args:
        video_path: 视频文件路径
        use_ml: 是否使用 ML 辅助检测（当前未实现）

    Returns:
        OrientationResult 对象
    """
    try:
        metadata = get_video_metadata(video_path)

        # 有旋转元数据的情况
        if metadata.rotation in (90, 270):
            orientation = "portrait" if metadata.height > metadata.width else "landscape"
            return OrientationResult(
                orientation=orientation,
                confidence=DetectionConfidence.HIGH,
                rotation_angle=metadata.rotation,
                method="metadata_rotation",
            )
        elif metadata.rotation == 180:
            return OrientationResult(
                orientation=metadata.orientation,
                confidence=DetectionConfidence.HIGH,
                rotation_angle=metadata.rotation,
                method="metadata_rotation",
            )

        # 无旋转元数据，根据宽高比判断
        if metadata.height > metadata.width:
            orientation = "portrait"
        elif metadata.width > metadata.height:
            orientation = "landscape"
        else:
            orientation = "square"

        if orientation != "unknown":
            return OrientationResult(
                orientation=orientation,
                confidence=DetectionConfidence.HIGH,
                rotation_angle=0,
                method="metadata_aspect_ratio",
            )

        # 确实无法判断
        return OrientationResult(
            orientation="unknown",
            confidence=DetectionConfidence.LOW,
            method="unknown",
        )

    except Exception as e:
        return OrientationResult(
            orientation="unknown",
            confidence=DetectionConfidence.LOW,
            method=f"error: {str(e)}",
        )


def detect_orientation_with_fallback(video_path: str) -> OrientationResult:
    """
    使用混合策略检测方向：
    1. 先尝试元数据
    2. 元数据不确定时使用帧分析
    """
    result = detect_orientation(video_path)

    if result.confidence == DetectionConfidence.LOW and result.orientation == "unknown":
        # TODO: 实现基于帧分析的备用检测
        # 这里可以集成简单的 CNN 分类器
        pass

    return result


def get_transform_angle(
    current_orientation: Orientation,
    target_orientation: Orientation,
    current_rotation: int = 0,
) -> int:
    """
    计算需要旋转的角度

    Args:
        current_orientation: 当前方向
        target_orientation: 目标方向
        current_rotation: 当前旋转角度

    Returns:
        需要旋转的角度 (90, 180, 270, 或 0)
    """
    if current_orientation == target_orientation:
        return 0

    # 横屏转竖屏
    if current_orientation == "landscape" and target_orientation == "portrait":
        # 根据当前旋转方向决定旋转角度
        if current_rotation == 0:
            return 90
        elif current_rotation == 90:
            return 180
        elif current_rotation == 180:
            return 270
        elif current_rotation == 270:
            return 0

    # 竖屏转横屏
    if current_orientation == "portrait" and target_orientation == "landscape":
        if current_rotation == 0:
            return 270
        elif current_rotation == 90:
            return 0
        elif current_rotation == 180:
            return 90
        elif current_rotation == 270:
            return 180

    return 0


def is_video_portrait(video_path: str) -> bool:
    """快速判断视频是否为竖屏"""
    result = detect_orientation(video_path)
    return result.orientation == "portrait"


def is_video_landscape(video_path: str) -> bool:
    """快速判断视频是否为横屏"""
    result = detect_orientation(video_path)
    return result.orientation == "landscape"
