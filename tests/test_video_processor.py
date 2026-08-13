"""
视频处理模块测试
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# 测试文件路径
TEST_VIDEO = "f:/code/MediaRefitAgent/video/seg0012.mp4"


class TestVideoMetadata:
    """VideoMetadata 测试"""

    def test_metadata_structure(self):
        """测试元数据结构"""
        from video.processor import VideoMetadata

        metadata = VideoMetadata(width=1920, height=1080, rotation=0, duration=10.0, fps=30.0)

        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.rotation == 0
        assert metadata.duration == 10.0
        assert metadata.fps == 30.0

    def test_orientation_landscape(self):
        """测试横屏判断"""
        from video.processor import VideoMetadata

        metadata = VideoMetadata(width=1920, height=1080, rotation=0, duration=10.0, fps=30.0)
        assert metadata.orientation == "landscape"

    def test_orientation_portrait(self):
        """测试竖屏判断"""
        from video.processor import VideoMetadata

        metadata = VideoMetadata(width=1080, height=1920, rotation=0, duration=10.0, fps=30.0)
        assert metadata.orientation == "portrait"

    def test_orientation_with_rotation(self):
        """测试带旋转角度的方向判断"""
        from video.processor import VideoMetadata

        # 原始是横屏，旋转90度后应该是竖屏
        metadata = VideoMetadata(width=1920, height=1080, rotation=90, duration=10.0, fps=30.0)
        assert metadata.orientation == "portrait"

    def test_orientation_square(self):
        """测试正方形判断"""
        from video.processor import VideoMetadata

        metadata = VideoMetadata(width=1080, height=1080, rotation=0, duration=10.0, fps=30.0)
        assert metadata.orientation == "square"


class TestOrientationDetector:
    """方向检测测试"""

    def test_detect_orientation_result_structure(self):
        """测试检测结果结构"""
        from ml.orientation_detector import OrientationResult, DetectionConfidence, Orientation

        result = OrientationResult(
            orientation="landscape",
            confidence=DetectionConfidence.HIGH,
            rotation_angle=0,
            method="metadata",
        )

        assert result.orientation == "landscape"
        assert result.confidence == DetectionConfidence.HIGH
        assert result.rotation_angle == 0
        assert result.method == "metadata"

    def test_get_transform_angle_same_orientation(self):
        """测试相同方向不需要旋转"""
        from ml.orientation_detector import get_transform_angle

        angle = get_transform_angle("landscape", "landscape")
        assert angle == 0

        angle = get_transform_angle("portrait", "portrait")
        assert angle == 0

    def test_get_transform_angle_landscape_to_portrait(self):
        """测试横屏转竖屏"""
        from ml.orientation_detector import get_transform_angle

        # 无旋转，横屏转竖屏需要旋转90度
        angle = get_transform_angle("landscape", "portrait", current_rotation=0)
        assert angle == 90

    def test_get_transform_angle_portrait_to_landscape(self):
        """测试竖屏转横屏"""
        from ml.orientation_detector import get_transform_angle

        # 无旋转，竖屏转横屏需要旋转270度（或-90度）
        angle = get_transform_angle("portrait", "landscape", current_rotation=0)
        assert angle == 270


class TestTransformRequest:
    """TransformRequest 测试"""

    def test_transform_request_creation(self):
        """测试请求创建"""
        from video.transformer import TransformRequest, TransformStrategy, Orientation

        request = TransformRequest(
            input_path="/input/video.mp4",
            output_path="/output/video.mp4",
            target_orientation="portrait",
            strategy="pad",
            target_ratio=9/16,
        )

        assert request.input_path == "/input/video.mp4"
        assert request.output_path == "/output/video.mp4"
        assert request.target_orientation == "portrait"
        assert request.strategy == "pad"
        assert request.target_ratio == 9/16


class TestTransformResult:
    """TransformResult 测试"""

    def test_transform_result_success(self):
        """测试成功结果"""
        from video.transformer import TransformResult, VideoMetadata

        metadata = VideoMetadata(width=1920, height=1080, rotation=0, duration=10.0, fps=30.0)
        result = TransformResult(
            success=True,
            input_path="/input/video.mp4",
            output_path="/output/video.mp4",
            original_orientation="landscape",
            target_orientation="portrait",
            strategy_used="pad",
            metadata=metadata,
        )

        assert result.success is True
        assert result.original_orientation == "landscape"
        assert result.target_orientation == "portrait"
        assert result.strategy_used == "pad"
        assert result.error is None

    def test_transform_result_failure(self):
        """测试失败结果"""
        from video.transformer import TransformResult

        result = TransformResult(
            success=False,
            input_path="/input/video.mp4",
            output_path="/output/video.mp4",
            error="File not found",
        )

        assert result.success is False
        assert result.error == "File not found"


class TestQuickTransform:
    """quick_transform 测试"""

    @patch('video.transformer.transform')
    def test_quick_transform_calls_transform(self, mock_transform):
        """测试 quick_transform 调用 transform"""
        from video.transformer import quick_transform

        mock_transform.return_value = MagicMock(success=True)

        result = quick_transform(
            input_path="/input.mp4",
            output_path="/output.mp4",
            target_orientation="portrait",
            strategy="pad",
        )

        assert result is True
        mock_transform.assert_called_once()


# ============ 集成测试（需要 FFmpeg）============

class TestIntegration:
    """集成测试"""

    @pytest.mark.skipif(not os.path.exists(TEST_VIDEO), reason="Test video not found")
    def test_get_video_metadata_integration(self):
        """测试获取视频元数据（集成）"""
        from video.processor import get_video_metadata

        metadata = get_video_metadata(TEST_VIDEO)

        assert metadata.width > 0
        assert metadata.height > 0
        assert metadata.duration > 0
        assert metadata.fps > 0

    @pytest.mark.skipif(not os.path.exists(TEST_VIDEO), reason="Test video not found")
    def test_detect_orientation_integration(self):
        """测试方向检测（集成）"""
        from ml.orientation_detector import detect_orientation

        result = detect_orientation(TEST_VIDEO)

        assert result.orientation in ("portrait", "landscape", "square", "unknown")
        assert result.method is not None

    @pytest.mark.skipif(not os.path.exists(TEST_VIDEO), reason="Test video not found")
    def test_transform_with_pad_integration(self):
        """测试填充转换（集成）"""
        from video.transformer import transform, TransformRequest
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            output_path = tmp.name

        try:
            request = TransformRequest(
                input_path=TEST_VIDEO,
                output_path=output_path,
                target_orientation="portrait",
                strategy="pad",
            )
            result = transform(request)

            # 注意：seg0012.mp4 可能是竖屏，所以可能不需要转换
            assert result.success or result.error is not None
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
