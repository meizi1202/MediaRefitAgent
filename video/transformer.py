"""
视频转换核心逻辑

统一入口，组合 metadata 检测、方向检测、FFmpeg 处理
"""
from pathlib import Path
from typing import Optional, Literal, Callable
import shutil

from video.processor import (
    get_video_metadata,
    rotate_video,
    pad_to_ratio,
    crop_to_ratio,
    transform_video as ffmpeg_transform,
    VideoMetadata,
    RATIO_PRESETS,
)
from ml.orientation_detector import (
    detect_orientation,
    get_transform_angle,
    OrientationResult,
    is_video_portrait,
    is_video_landscape,
)

# 延迟导入 smart_crop 以避免 YOLO 不可用时出错
try:
    from ml.smart_cropper import smart_crop as ml_smart_crop, YOLO_AVAILABLE as SMART_CROP_AVAILABLE
except ImportError:
    SMART_CROP_AVAILABLE = False
    ml_smart_crop = None

Orientation = Literal["portrait", "landscape", "square", "unknown"]
TransformStrategy = Literal["rotate", "pad", "crop", "smart_crop", "stretch", "mirror_scroll", "pan_scroll"]


class VideoTransformError(Exception):
    """视频转换异常"""
    pass


class TransformRequest:
    """转换请求"""

    def __init__(
        self,
        input_path: str,
        output_path: str,
        target_orientation: Optional[Orientation] = None,
        strategy: TransformStrategy = "pad",
        target_ratio: float = 9 / 16,
    ):
        self.input_path = input_path
        self.output_path = output_path
        self.target_orientation = target_orientation
        self.strategy = strategy
        self.target_ratio = target_ratio

    def __repr__(self):
        return f"TransformRequest({self.input_path} -> {self.output_path}, target={self.target_orientation}, strategy={self.strategy})"


class TransformResult:
    """转换结果"""

    def __init__(
        self,
        success: bool,
        input_path: str,
        output_path: str,
        original_orientation: Optional[str] = None,
        target_orientation: Optional[str] = None,
        strategy_used: Optional[str] = None,
        metadata: Optional[VideoMetadata] = None,
        orientation_result: Optional[OrientationResult] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.input_path = input_path
        self.output_path = output_path
        self.original_orientation = original_orientation
        self.target_orientation = target_orientation
        self.strategy_used = strategy_used
        self.metadata = metadata
        self.orientation_result = orientation_result
        self.error = error

    def __repr__(self):
        if self.success:
            return f"TransformResult(success, {self.original_orientation} -> {self.target_orientation})"
        else:
            return f"TransformResult(failed: {self.error})"


def transform(
    request: TransformRequest,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> TransformResult:
    """
    执行视频转换

    Args:
        request: 转换请求
        progress_callback: 进度回调 (0.0 - 1.0)

    Returns:
        TransformResult 结果
    """
    try:
        # 1. 检查文件存在
        input_path = Path(request.input_path)
        if not input_path.exists():
            return TransformResult(
                success=False,
                input_path=request.input_path,
                output_path=request.output_path,
                error=f"Input file not found: {request.input_path}",
            )

        # 2. 获取元数据
        metadata = get_video_metadata(str(input_path))

        # 3. 检测方向
        orientation_result = detect_orientation(str(input_path))
        current_orientation = orientation_result.orientation

        # 4. 确定目标方向
        if request.target_orientation:
            target_orientation = request.target_orientation
        else:
            # 如果没指定，根据当前方向取反
            if current_orientation == "portrait":
                target_orientation = "landscape"
            else:
                target_orientation = "portrait"

        # 5. 如果方向相同，直接复制
        if current_orientation == target_orientation:
            if request.input_path != request.output_path:
                shutil.copy(request.input_path, request.output_path)
            return TransformResult(
                success=True,
                input_path=request.input_path,
                output_path=request.output_path,
                original_orientation=current_orientation,
                target_orientation=target_orientation,
                strategy_used="none (already target orientation)",
                metadata=metadata,
                orientation_result=orientation_result,
            )

        # 6. 计算目标比例
        target_ratio = request.target_ratio
        if target_orientation == "portrait":
            target_ratio = 9 / 16
        else:
            target_ratio = 16 / 9

        # stretch 策略需要使用用户指定的确切比例，不要覆盖
        if request.strategy == "stretch" and request.target_ratio:
            target_ratio = request.target_ratio

        # 7. 执行转换
        if progress_callback:
            progress_callback(0.1)

        if request.strategy == "rotate":
            angle = get_transform_angle(
                current_orientation,
                target_orientation,
                metadata.rotation,
            )
            if angle > 0:
                rotate_video(
                    request.input_path,
                    request.output_path,
                    degrees=angle,
                    progress_callback=progress_callback,
                )
            strategy_used = f"rotate_{angle}"
        elif request.strategy == "pad":
            pad_to_ratio(
                request.input_path,
                request.output_path,
                target_ratio=target_ratio,
                target_orientation=target_orientation,
                progress_callback=progress_callback,
            )
            strategy_used = "pad"
        elif request.strategy == "crop":
            crop_to_ratio(
                request.input_path,
                request.output_path,
                target_ratio=target_ratio,
                target_orientation=target_orientation,
                progress_callback=progress_callback,
            )
            strategy_used = "crop"
        elif request.strategy == "smart_crop":
            if SMART_CROP_AVAILABLE and ml_smart_crop:
                ml_smart_crop(
                    request.input_path,
                    request.output_path,
                    target_ratio=target_ratio,
                    progress_callback=progress_callback,
                )
                strategy_used = "smart_crop"
            else:
                # Fallback to regular crop
                crop_to_ratio(
                    request.input_path,
                    request.output_path,
                    target_ratio=target_ratio,
                    target_orientation=target_orientation,
                    progress_callback=progress_callback,
                )
                strategy_used = "smart_crop (fallback to crop)"
        elif request.strategy == "stretch":
            from video.processor import stretch_to_ratio
            stretch_to_ratio(
                request.input_path,
                request.output_path,
                target_ratio=target_ratio,
                target_orientation=target_orientation,
                progress_callback=progress_callback,
            )
            strategy_used = "stretch"
        elif request.strategy == "mirror_scroll":
            from video.processor import mirror_scroll
            mirror_scroll(
                request.input_path,
                request.output_path,
                target_ratio=target_ratio,
                target_orientation=target_orientation,
                progress_callback=progress_callback,
            )
            strategy_used = "mirror_scroll"
        elif request.strategy == "pan_scroll":
            from video.processor import pan_scroll
            pan_scroll(
                request.input_path,
                request.output_path,
                target_ratio=target_ratio,
                target_orientation=target_orientation,
                progress_callback=progress_callback,
            )
            strategy_used = "pan_scroll"
        else:
            return TransformResult(
                success=False,
                input_path=request.input_path,
                output_path=request.output_path,
                error=f"Unknown strategy: {request.strategy}",
            )

        if progress_callback:
            progress_callback(0.95)

        return TransformResult(
            success=True,
            input_path=request.input_path,
            output_path=request.output_path,
            original_orientation=current_orientation,
            target_orientation=target_orientation,
            strategy_used=strategy_used,
            metadata=metadata,
            orientation_result=orientation_result,
        )

    except Exception as e:
        return TransformResult(
            success=False,
            input_path=request.input_path,
            output_path=request.output_path,
            error=str(e),
        )


def quick_transform(
    input_path: str,
    output_path: str,
    target_orientation: Orientation = "portrait",
    strategy: TransformStrategy = "pad",
) -> bool:
    """
    快速转换接口（简化用法）

    Args:
        input_path: 输入路径
        output_path: 输出路径
        target_orientation: 目标方向
        strategy: 转换策略

    Returns:
        是否成功
    """
    request = TransformRequest(
        input_path=input_path,
        output_path=output_path,
        target_orientation=target_orientation,
        strategy=strategy,
    )
    result = transform(request)
    return result.success
