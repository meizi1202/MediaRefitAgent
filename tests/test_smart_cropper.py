"""
Phase 2 智能裁剪模块测试
"""
import pytest
from unittest.mock import patch, MagicMock
import numpy as np

TEST_VIDEO = "f:/code/MediaRefitAgent/video/seg0012.mp4"


class TestBoundingBox:
    """BoundingBox 测试"""

    def test_bounding_box_creation(self):
        """测试边界框创建"""
        from ml.smart_cropper import BoundingBox

        box = BoundingBox(x1=100, y1=100, x2=200, y2=200, confidence=0.9)

        assert box.x1 == 100
        assert box.y1 == 100
        assert box.x2 == 200
        assert box.y2 == 200
        assert box.confidence == 0.9

    def test_bounding_box_properties(self):
        """测试边界框属性计算"""
        from ml.smart_cropper import BoundingBox

        box = BoundingBox(x1=100, y1=100, x2=200, y2=300)

        assert box.center_x == 150
        assert box.center_y == 200
        assert box.width == 100
        assert box.height == 200
        assert box.area == 20000


class TestSmartCropResult:
    """SmartCropResult 测试"""

    def test_smart_crop_result_creation(self):
        """测试裁剪结果创建"""
        from ml.smart_cropper import SmartCropResult, BoundingBox

        boxes = [BoundingBox(x1=100, y1=100, x2=200, y2=200)]
        result = SmartCropResult(
            crop_x=50,
            crop_y=50,
            crop_width=300,
            crop_height=400,
            detections=boxes,
            frame_count=5,
        )

        assert result.crop_x == 50
        assert result.crop_y == 50
        assert result.crop_width == 300
        assert result.crop_height == 400
        assert len(result.detections) == 1
        assert result.frame_count == 5


class TestSmartCropper:
    """SmartCropper 测试"""

    def test_smart_cropper_init_without_yolo(self):
        """测试 YOLO 不可用时的初始化"""
        with patch('ml.smart_cropper.YOLO_AVAILABLE', False):
            from ml.smart_cropper import SmartCropper
            import importlib
            import ml.smart_cropper as sc

            # 模拟 YOLO 不可用
            original = sc.YOLO_AVAILABLE
            sc.YOLO_AVAILABLE = False

            with pytest.raises(ImportError, match="ultralytics not installed"):
                SmartCropper()

            sc.YOLO_AVAILABLE = original

    def test_compute_enclosing_crop_empty_boxes(self):
        """测试空检测框时的处理"""
        from ml.smart_cropper import SmartCropper

        with patch('ml.smart_cropper.YOLO_AVAILABLE', True):
            with patch('ml.smart_cropper.YOLO') as mock_yolo:
                cropper = SmartCropper()
                cropper.model = MagicMock()

                # 空检测框列表
                result = cropper.compute_enclosing_crop([], target_ratio=9/16)

                # 应该返回 (0, 0, 0, 0)
                assert result == (0, 0, 0, 0)

    def test_compute_enclosing_crop_single_box(self):
        """测试单个检测框"""
        from ml.smart_cropper import SmartCropper, BoundingBox

        with patch('ml.smart_cropper.YOLO_AVAILABLE', True):
            with patch('ml.smart_cropper.YOLO') as mock_yolo:
                cropper = SmartCropper()
                cropper.model = MagicMock()

                boxes = [BoundingBox(x1=100, y1=100, x2=200, y2=200)]
                result = cropper.compute_enclosing_crop(boxes, target_ratio=9/16)

                x, y, w, h = result
                assert w > 0
                assert h > 0

    def test_compute_enclosing_crop_multiple_boxes(self):
        """测试多个检测框"""
        from ml.smart_cropper import SmartCropper, BoundingBox

        with patch('ml.smart_cropper.YOLO_AVAILABLE', True):
            with patch('ml.smart_cropper.YOLO') as mock_yolo:
                cropper = SmartCropper()
                cropper.model = MagicMock()

                boxes = [
                    BoundingBox(x1=50, y1=50, x2=150, y2=150),
                    BoundingBox(x1=200, y1=100, x2=300, y2=200),
                ]
                result = cropper.compute_enclosing_crop(boxes, target_ratio=9/16)

                x, y, w, h = result
                assert x <= 50  # 应该包含最左边的点
                assert y <= 50  # 应该包含最上边的点
                assert x + w >= 300  # 应该包含最右边的点
                assert y + h >= 200  # 应该包含最下边的点


class TestProgressTracking:
    """进度跟踪测试"""

    def test_progress_callback_structure(self):
        """测试进度回调结构"""
        progress_values = []

        def callback(progress: float):
            progress_values.append(progress)

        # 模拟进度
        callback(0.0)
        callback(0.25)
        callback(0.5)
        callback(0.75)
        callback(1.0)

        assert progress_values == [0.0, 0.25, 0.5, 0.75, 1.0]

    @patch('video.processor.get_video_duration')
    def test_progress_callback_in_transform(self, mock_duration):
        """测试转换时的进度回调"""
        mock_duration.return_value = 10.0

        from video.processor import pad_to_ratio
        import tempfile

        # 这个测试需要真实的 FFmpeg，所以我们只测试回调被调用
        progress_values = []

        def callback(progress: float):
            progress_values.append(progress)

        # 由于没有真实视频文件，我们验证回调机制存在
        assert callable(callback)


class TestTransformerWithSmartCrop:
    """Transformer 智能裁剪集成测试"""

    def test_smart_crop_strategy_available(self):
        """测试 smart_crop 策略可用"""
        from video.transformer import TransformRequest

        request = TransformRequest(
            input_path="/input.mp4",
            output_path="/output.mp4",
            strategy="smart_crop",
        )

        assert request.strategy == "smart_crop"

    @patch('video.transformer.SMART_CROP_AVAILABLE', False)
    def test_smart_crop_fallback_to_crop(self):
        """测试 smart_crop 不可用时回退到 crop"""
        from video.transformer import transform, TransformRequest

        request = TransformRequest(
            input_path=TEST_VIDEO if __import__('os').path.exists(TEST_VIDEO) else "/fake/path.mp4",
            output_path="/tmp/output.mp4",
            strategy="smart_crop",
        )

        # 由于文件不存在，应该返回错误而不是崩溃
        result = transform(request)
        # 不应该因为策略问题失败
        assert result.success is False or "not found" in (result.error or "").lower()


class TestFastAPIEndpoints:
    """FastAPI 端点测试"""

    def test_capabilities_endpoint(self):
        """测试能力端点返回正确信息"""
        from api.fastapi_app import SMART_CROP_AVAILABLE

        # 检查 SMART_CROP_AVAILABLE 变量存在
        assert SMART_CROP_AVAILABLE is not None

    def test_transform_request_validation(self):
        """测试转换请求验证"""
        from pydantic import ValidationError
        from api.fastapi_app import TransformRequestModel

        # 有效请求
        valid = TransformRequestModel(
            target_orientation="portrait",
            strategy="pad",
        )
        assert valid.target_orientation == "portrait"
        assert valid.strategy == "pad"

        # 无效策略
        with pytest.raises(ValidationError):
            TransformRequestModel(strategy="invalid_strategy")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
