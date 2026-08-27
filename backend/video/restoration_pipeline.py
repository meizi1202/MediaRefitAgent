"""
老视频修复 - 流水线编排

将多个修复步骤串联执行，支持进度回调
"""
import time
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from video.processor import (
    denoise_video,
    color_correct_video,
    sharpen_video,
    remove_scratch,
    remove_flicker,
    interpolate_frames,
    super_resolve_video,
    get_video_metadata,
)
from video.restoration import (
    RestorationRequest,
    RestorationResult,
    RestorationStageResult,
    RestorationOptions,
    get_default_options_for_preset,
)


class RestorationPipeline:
    """
    修复流水线编排器

    按顺序执行修复步骤：
    1. 去噪、去抖动、色彩校正
    2. 划痕修复、闪烁修复
    3. 补帧
    4. 超分辨率
    """

    def __init__(
        self,
        request: RestorationRequest,
        temp_dir: Optional[str] = None,
    ):
        self.request = request
        # 如果没有提供 options 或 options 为空，则使用套餐默认值
        if request.options is None or self._is_options_empty(request.options):
            self.options = get_default_options_for_preset(request.preset)
        else:
            self.options = request.options
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="restoration_")
        self.stage_results: list[RestorationStageResult] = []

    def _is_options_empty(self, options: RestorationOptions) -> bool:
        """检查 options 是否为空（所有功能都未启用）"""
        return not (
            options.denoise
            or options.deblur
            or options.color_correct
            or options.contrast_enhance
            or options.scratch_remove
            or options.flicker_remove
            or options.interpolate
            or options.super_resolution
        )

    def run(self) -> RestorationResult:
        """
        执行完整修复流水线

        Returns:
            RestorationResult: 修复结果
        """
        start_time = time.time()
        current_input = self.request.input_path

        try:
            # 阶段1: 基础修复（去噪、去抖动、色彩校正）
            if self._needs_basic_restoration():
                current_input = self._run_stage(
                    "basic_restoration",
                    current_input,
                    self._run_basic_restoration,
                )
                if not current_input:
                    return self._error_result(start_time, "基础修复失败")

            # 阶段2: 胶片修复（划痕、闪烁）
            if self._needs_film_restoration():
                current_input = self._run_stage(
                    "film_restoration",
                    current_input,
                    self._run_film_restoration,
                )
                if not current_input:
                    return self._error_result(start_time, "胶片修复失败")

            # 阶段3: 补帧
            if self.options.interpolate:
                current_input = self._run_stage(
                    "frame_interpolation",
                    current_input,
                    self._run_interpolation,
                )
                if not current_input:
                    return self._error_result(start_time, "补帧失败")

            # 阶段4: 超分辨率
            if self.options.super_resolution:
                current_input = self._run_stage(
                    "super_resolution",
                    current_input,
                    self._run_super_resolution,
                )
                if not current_input:
                    return self._error_result(start_time, "超分辨率失败")

            # 最终输出
            output_path = self.request.output_path
            if current_input != output_path:
                shutil.copy(current_input, output_path)

            # 清理临时文件
            self._cleanup()

            total_duration = time.time() - start_time
            output_size = Path(output_path).stat().st_size if Path(output_path).exists() else 0

            return RestorationResult(
                success=True,
                input_path=self.request.input_path,
                output_path=output_path,
                preset=self.request.preset.value,
                stages=self.stage_results,
                total_duration=total_duration,
                output_size=output_size,
            )

        except Exception as e:
            self._cleanup()
            return RestorationResult(
                success=False,
                input_path=self.request.input_path,
                output_path=self.request.output_path,
                preset=self.request.preset.value,
                stages=self.stage_results,
                total_duration=time.time() - start_time,
                output_size=0,
                error=str(e),
            )

    def _needs_basic_restoration(self) -> bool:
        """检查是否需要基础修复"""
        return (
            self.options.denoise
            or self.options.deblur
            or self.options.color_correct
            or self.options.contrast_enhance
        )

    def _needs_film_restoration(self) -> bool:
        """检查是否需要胶片修复"""
        return self.options.scratch_remove or self.options.flicker_remove

    def _needs_interpolation(self) -> bool:
        """检查是否需要补帧"""
        return self.options.interpolate

    def _needs_super_resolution(self) -> bool:
        """检查是否需要超分辨率"""
        return self.options.super_resolution

    def _run_stage(
        self,
        stage_name: str,
        input_path: str,
        stage_func,
        stage_weight: float = 1.0,
    ) -> Optional[str]:
        """执行单个阶段

        Args:
            stage_name: 阶段名称
            input_path: 输入文件路径
            stage_func: 阶段执行函数
            stage_weight: 阶段权重（占整体进度的比例），0.0-1.0
        """
        stage_start = time.time()

        # 计算当前阶段的起始进度（基于已完成阶段的权重）
        completed_weight = sum(
            s.duration for s in self.stage_results if s.success
        )
        # 计算总阶段数和阶段权重
        all_stages = [n for n in ["basic_restoration", "film_restoration", "interpolation", "super_resolution"] if self._stage_enabled(n)]
        total_stages = len(all_stages)
        # 每个阶段的进度权重（均分）
        stage_weight = 1.0 / max(total_stages, 1)
        # 已完成的进度
        completed_ratio = len([s for s in self.stage_results if s.success]) * stage_weight
        base_progress = completed_ratio

        # 包装回调：将阶段的 0-1 进度映射到整体进度
        def stage_progress_callback(progress: float):
            if self.request.progress_callback:
                overall = base_progress + progress * stage_weight
                self.request.progress_callback(stage_name, overall)

        try:
            # 将包装后的回调传递给 stage_func
            output_path = stage_func(input_path, stage_progress_callback)

            self.stage_results.append(RestorationStageResult(
                stage=stage_name,
                success=True,
                input_path=input_path,
                output_path=output_path,
                duration=time.time() - stage_start,
            ))

            return output_path

        except Exception as e:
            self.stage_results.append(RestorationStageResult(
                stage=stage_name,
                success=False,
                input_path=input_path,
                output_path=input_path,
                duration=time.time() - stage_start,
                error=str(e),
            ))

            # 阶段失败时继续使用输入（避免中断流水线）
            return input_path

    def _stage_enabled(self, stage_name: str) -> bool:
        """检查某阶段是否启用"""
        if stage_name == "basic_restoration":
            return self._needs_basic_restoration()
        elif stage_name == "film_restoration":
            return self._needs_film_restoration()
        elif stage_name == "interpolation":
            return self._needs_interpolation()
        elif stage_name == "super_resolution":
            return self._needs_super_resolution()
        return False

    def _run_basic_restoration(self, input_path: str, progress_callback=None) -> str:
        """执行基础修复"""
        from video.processor import restore_video

        output_path = Path(self.temp_dir) / f"basic_{Path(input_path).stem}.mp4"

        # 使用综合修复函数
        restore_video(
            input_path=input_path,
            output_path=str(output_path),
            denoise=self.options.denoise,
            denoise_level=self.options.denoise_level.value,
            deblur=self.options.deblur,
            deblur_level=self.options.deblur_level.value,
            color_correct=self.options.color_correct,
            saturation=self.options.saturation / 100.0 + 1.0,  # 转换到 0.9-1.1 范围
            contrast=self.options.contrast_level,
            progress_callback=progress_callback,
        )

        return str(output_path)

    def _run_film_restoration(self, input_path: str, progress_callback=None) -> str:
        """执行胶片修复"""
        output_path = Path(self.temp_dir) / f"film_{Path(input_path).stem}.mp4"

        if self.options.scratch_remove and self.options.flicker_remove:
            # 两者都启用时，先划痕后闪烁
            temp_path = Path(self.temp_dir) / f"scratch_{Path(input_path).stem}.mp4"

            remove_scratch(
                input_path,
                str(temp_path),
                level=self.options.scratch_level,
                progress_callback=progress_callback,
            )

            remove_flicker(
                str(temp_path),
                str(output_path),
                level=self.options.flicker_level,
                progress_callback=progress_callback,
            )

            if temp_path.exists():
                temp_path.unlink()

        elif self.options.scratch_remove:
            remove_scratch(
                input_path,
                str(output_path),
                level=self.options.scratch_level,
                progress_callback=progress_callback,
            )

        elif self.options.flicker_remove:
            remove_flicker(
                input_path,
                str(output_path),
                level=self.options.flicker_level,
                progress_callback=progress_callback,
            )
        else:
            # 没有启用任何胶片修复，直接复制
            shutil.copy(input_path, str(output_path))

        return str(output_path)

    def _run_interpolation(self, input_path: str, progress_callback=None) -> str:
        """执行补帧"""
        output_path = Path(self.temp_dir) / f"interp_{Path(input_path).stem}.mp4"

        interpolate_frames(
            input_path,
            str(output_path),
            target_fps=self.options.target_fps,
            progress_callback=progress_callback,
        )

        return str(output_path)

    def _run_super_resolution(self, input_path: str, progress_callback=None) -> str:
        """执行超分辨率"""
        output_path = Path(self.temp_dir) / f"super_{Path(input_path).stem}.mp4"

        super_resolve_video(
            input_path,
            str(output_path),
            scale=self.options.scale_factor,
            progress_callback=progress_callback,
        )

        return str(output_path)

    def _cleanup(self):
        """清理临时文件"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _error_result(self, start_time: float, error_msg: str) -> RestorationResult:
        """生成错误结果"""
        return RestorationResult(
            success=False,
            input_path=self.request.input_path,
            output_path=self.request.output_path,
            preset=self.request.preset.value,
            stages=self.stage_results,
            total_duration=time.time() - start_time,
            output_size=0,
            error=error_msg,
        )


def restore(request: RestorationRequest) -> RestorationResult:
    """
    快捷修复函数

    Args:
        request: 修复请求

    Returns:
        修复结果
    """
    pipeline = RestorationPipeline(request)
    return pipeline.run()
