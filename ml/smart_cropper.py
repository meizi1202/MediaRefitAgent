"""
智能裁剪模块 - 基于 YOLO 主体检测
"""
import numpy as np
from typing import Optional, Tuple, List
from pathlib import Path

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

from video.processor import get_video_metadata


class BoundingBox:
    def __init__(self, x1: float, y1: float, x2: float, y2: float, confidence: float = 1.0):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.confidence = confidence

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2


class SmartCropResult:
    def __init__(self, crop_x: int, crop_y: int, crop_width: int, crop_height: int,
                 detections: List[BoundingBox], frame_count: int = 1):
        self.crop_x = crop_x
        self.crop_y = crop_y
        self.crop_width = crop_width
        self.crop_height = crop_height
        self.detections = detections
        self.frame_count = frame_count


class SmartCropper:
    def __init__(self, model_path: Optional[str] = None):
        if not YOLO_AVAILABLE:
            raise ImportError("ultralytics not installed. Install with: pip install ultralytics")
        self.model = YOLO("yolov8n.pt") if not model_path or not Path(model_path).exists() else YOLO(model_path)

    def detect_objects(self, frame: np.ndarray) -> List[BoundingBox]:
        results = self.model(frame, verbose=False)
        boxes = []
        if results and len(results) > 0:
            result = results[0]
            if result.boxes is not None:
                for box in result.boxes:
                    xyxy = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0].cpu().numpy())
                    boxes.append(BoundingBox(x1=xyxy[0], y1=xyxy[1], x2=xyxy[2], y2=xyxy[3], confidence=conf))
        return boxes

    def crop_video_frames(self, video_path: str, target_ratio: float = 9 / 16, sample_frames: int = 5) -> SmartCropResult:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = np.linspace(0, total_frames - 1, sample_frames, dtype=int)

        all_boxes: List[BoundingBox] = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                boxes = self.detect_objects(frame_rgb)
                all_boxes.extend(boxes)

        cap.release()

        metadata = get_video_metadata(video_path)
        frame_width = metadata.width
        frame_height = metadata.height

        crop_params = self._compute_crop(all_boxes, target_ratio, frame_width, frame_height)

        return SmartCropResult(
            crop_x=crop_params[0], crop_y=crop_params[1],
            crop_width=crop_params[2], crop_height=crop_params[3],
            detections=all_boxes, frame_count=sample_frames,
        )

    def _compute_crop(self, boxes: List[BoundingBox], target_ratio: float,
                      frame_width: int, frame_height: int) -> Tuple[int, int, int, int]:
        """
        计算裁剪区域 - 简化算法

        对于横屏转竖屏(16:9 -> 9:16)：
        - 从原视频中选择一个 9:16 的区域
        - 该区域应该包含最多的检测主体
        """
        if not boxes:
            # 无检测结果，使用中心裁剪
            return self._center_crop(target_ratio, frame_width, frame_height)

        # 计算所有检测框的包围盒中心
        min_x = min(box.x1 for box in boxes)
        min_y = min(box.y1 for box in boxes)
        max_x = max(box.x2 for box in boxes)
        max_y = max(box.y2 for box in boxes)

        content_center_x = (min_x + max_x) / 2
        content_center_y = (min_y + max_y) / 2

        # 目标比例
        target_w_h = target_ratio  # width/height

        # 计算裁剪区域尺寸（基于原视频尺寸）
        # 策略：尽量用全宽，按比例计算高度
        crop_width = frame_width
        crop_height = int(frame_width / target_w_h)

        # 如果高度超出，用全高，按比例计算宽度
        if crop_height > frame_height:
            crop_height = frame_height
            crop_width = int(frame_height * target_w_h)

        # 基于主体中心计算裁剪起点
        crop_x = int(content_center_x - crop_width / 2)
        crop_y = int(content_center_y - crop_height / 2)

        # Clamp 到画面边界
        crop_x = max(0, min(crop_x, frame_width - crop_width))
        crop_y = max(0, min(crop_y, frame_height - crop_height))

        # 再次检查并修正
        if crop_x + crop_width > frame_width:
            crop_x = frame_width - crop_width
        if crop_y + crop_height > frame_height:
            crop_y = frame_height - crop_height

        return crop_x, crop_y, crop_width, crop_height

    def _center_crop(self, target_ratio: float, frame_width: int, frame_height: int) -> Tuple[int, int, int, int]:
        crop_width = frame_width
        crop_height = int(frame_width / target_ratio)

        if crop_height > frame_height:
            crop_height = frame_height
            crop_width = int(frame_height * target_ratio)

        crop_x = (frame_width - crop_width) // 2
        crop_y = (frame_height - crop_height) // 2

        return crop_x, crop_y, crop_width, crop_height


def smart_crop(video_path: str, output_path: str, target_ratio: float = 9 / 16, progress_callback=None) -> str:
    if not YOLO_AVAILABLE:
        raise ImportError("ultralytics not installed")

    import subprocess

    if progress_callback:
        progress_callback(0.1)

    cropper = SmartCropper()
    crop_result = cropper.crop_video_frames(video_path, target_ratio)

    if progress_callback:
        progress_callback(0.3)

    # 计算目标分辨率
    if target_ratio < 1:
        target_width = 1080
        target_height = int(1080 / target_ratio)
    else:
        target_height = 1080
        target_width = int(1080 * target_ratio)

    # 裁剪 + 缩放 + 强制 SAR=1:1
    vf = f"crop={crop_result.crop_width}:{crop_result.crop_height}:{crop_result.crop_x}:{crop_result.crop_y},scale={target_width}:{target_height},setsar=1:1"

    cmd = ["ffmpeg", "-i", video_path, "-vf", vf, "-c:a", "copy", "-y", output_path]

    if progress_callback:
        progress_callback(0.4)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr}")

    if progress_callback:
        progress_callback(1.0)

    return output_path
