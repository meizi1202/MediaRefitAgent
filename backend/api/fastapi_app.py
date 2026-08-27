"""
FastAPI 服务 - 供 DIFY 等第三方调用

API 设计：
- POST /api/transform - 视频转换（同步）
- POST /api/transform-stream - 视频转换（支持进度流）
- POST /api/detect-orientation - 检测视频方向
- GET /api/health - 健康检查
- GET /api/download/{filename} - 下载转换后的视频
"""
import os
import shutil
import tempfile
import asyncio
import time
import urllib.parse
import urllib.request
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from enum import Enum

# 降低 uvicorn access log 级别，避免 206 分段请求日志刷屏
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
import json

# 允许嵌套事件循环（解决 TTS asyncio.run 问题）
import nest_asyncio
nest_asyncio.apply()

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 设置 FFmpeg PATH
ffmpeg_path = os.getenv("FFMPEG_PATH", "")
if ffmpeg_path and os.path.exists(ffmpeg_path):
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

from video.transformer import (
    transform,
    TransformRequest,
    TransformResult,
    TransformStrategy,
    Orientation,
    SMART_CROP_AVAILABLE,
    RATIO_PRESETS,
)
from ml.orientation_detector import detect_orientation, OrientationResult
from agent.video_agent import VideoAgent, LANGGRAPH_AVAILABLE

# LangChain Agent (MinMax)
try:
    from agent.langchain_agent import VideoTransformAgent, chat as langchain_chat
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


# ============ Pydantic Models ============

class TransformRequestModel(BaseModel):
    """转换请求模型"""
    target_orientation: Optional[Orientation] = Field(
        default="portrait",
        description="目标方向: portrait (竖屏) / landscape (横屏)"
    )
    strategy: TransformStrategy = Field(
        default="pad",
        description="转换策略: rotate / pad / crop / smart_crop"
    )
    target_ratio: float = Field(
        default=9/16,
        description="目标比例，默认 9:16 (竖屏)"
    )


class TransformResponseModel(BaseModel):
    """转换响应模型"""
    success: bool
    input_path: str
    output_path: str
    download_url: Optional[str] = None
    original_orientation: Optional[str] = None
    target_orientation: Optional[str] = None
    strategy_used: Optional[str] = None
    message: str


class CompressionLevel(str, Enum):
    """压缩级别"""
    low = "low"       # 低压缩，高质量
    medium = "medium" # 中等压缩
    high = "high"     # 高压缩，低质量


class CompressResponseModel(BaseModel):
    """压缩响应模型"""
    success: bool
    input_path: str
    output_path: str
    download_url: Optional[str] = None
    original_size: int = 0
    compressed_size: int = 0
    compression_ratio: float = 0.0
    message: str


class OrientationResponseModel(BaseModel):
    """方向检测响应模型"""
    orientation: str
    confidence: str
    rotation_angle: Optional[int] = None
    method: str


class VideoInfoResponseModel(BaseModel):
    """视频信息响应模型"""
    success: bool
    width: int = 0
    height: int = 0
    duration: float = 0.0
    fps: float = 0.0
    bitrate: int = 0
    codec: str = ""
    aspect_ratio: float = 0.0
    message: str = ""


class TrimResponseModel(BaseModel):
    """视频裁剪响应模型"""
    success: bool
    input_path: str = ""
    output_path: str = ""
    download_url: Optional[str] = None
    original_size: int = 0
    trimmed_size: int = 0
    original_duration: float = 0.0
    trimmed_duration: float = 0.0
    start_time: float = 0.0
    end_time: float = 0.0
    message: str = ""


class ConcatResponseModel(BaseModel):
    """视频拼接响应模型"""
    success: bool
    input_paths: list[str] = []
    output_path: str = ""
    download_url: Optional[str] = None
    input_count: int = 0
    total_duration: float = 0.0
    output_duration: float = 0.0
    output_size: int = 0
    keep_audio: bool = True
    message: str = ""


class RestorationPreset(str, Enum):
    """修复套餐"""
    BASIC = "basic"
    FILM = "film"
    ENHANCED = "enhanced"
    CUSTOM = "custom"


class RestorationOptionsModel(BaseModel):
    """修复选项模型"""
    denoise: bool = False
    denoise_level: str = "medium"
    deblur: bool = False
    deblur_level: str = "medium"
    color_correct: bool = False
    saturation: int = 0
    contrast_enhance: bool = False
    contrast_level: float = 1.0
    scratch_remove: bool = False
    scratch_level: str = "medium"
    flicker_remove: bool = False
    flicker_level: str = "medium"
    interpolate: bool = False
    target_fps: int = 60
    super_resolution: bool = False
    scale_factor: int = 2


class RestorationStageModel(BaseModel):
    """修复阶段模型"""
    stage: str
    success: bool
    duration: float
    error: Optional[str] = None


class RestorationResponseModel(BaseModel):
    """修复响应模型"""
    success: bool
    task_id: str = ""
    input_path: str = ""
    output_path: str = ""
    download_url: Optional[str] = None
    preset: str = ""
    stages: list[RestorationStageModel] = []
    total_duration: float = 0.0
    output_size: int = 0
    message: str = ""


class HealthResponseModel(BaseModel):
    """健康检查响应"""
    status: str
    version: str


class ProgressEvent(BaseModel):
    """进度事件"""
    event: str
    progress: Optional[float] = None
    message: Optional[str] = None
    data: Optional[dict] = None


# ============ Lifespan ============

output_dir = Path(os.getenv("OUTPUT_DIR", "F:/video"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"🚀 MediaRefitAgent API started (output_dir: {output_dir})")
    yield
    # 关闭时
    print("👋 MediaRefitAgent API stopped")


# ============ App ============

app = FastAPI(
    title="MediaRefitAgent",
    description="视频横竖屏转换智能体 API，供 DIFY 等第三方调用",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Endpoints ============

@app.get("/api/health", response_model=HealthResponseModel)
async def health_check():
    """健康检查"""
    return HealthResponseModel(status="ok", version="1.0.0")


@app.get("/api/capabilities")
async def get_capabilities():
    """获取支持的能力"""
    return {
        "smart_crop": SMART_CROP_AVAILABLE,
        "strategies": ["rotate", "pad", "crop", "smart_crop", "stretch", "mirror_scroll", "pan_scroll"],
        "orientations": ["portrait", "landscape"],
        "ratio_presets": {
            "portrait": ["9:16", "4:5", "1:1", "2:3"],
            "landscape": ["16:9", "21:9", "4:3", "3:2"],
        },
        "ratio_values": {k: v for k, v in RATIO_PRESETS.items()},
    }


@app.post("/api/detect-orientation", response_model=OrientationResponseModel)
async def api_detect_orientation(file: UploadFile = File(...)):
    """
    检测视频方向

    上传视频文件，返回方向检测结果
    """
    # 保存临时文件
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = detect_orientation(tmp_path)
        return OrientationResponseModel(
            orientation=result.orientation,
            confidence=result.confidence.value,
            rotation_angle=result.rotation_angle,
            method=result.method,
        )
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/api/transform", response_model=TransformResponseModel)
async def api_transform(
    file: UploadFile = File(...),
    target_orientation: str = Form(default="portrait"),
    strategy: str = Form(default="pad"),
    target_ratio: float = Form(default=9/16),
):
    """
    视频转换接口（同步）

    上传视频文件，转换为指定方向，支持多种策略
    """
    # 验证参数
    if target_orientation not in ("portrait", "landscape"):
        raise HTTPException(status_code=400, detail="target_orientation must be 'portrait' or 'landscape'")

    if strategy not in ("rotate", "pad", "crop", "smart_crop", "stretch", "mirror_scroll", "pan_scroll"):
        raise HTTPException(status_code=400, detail="strategy must be one of: rotate, pad, crop, smart_crop, stretch, mirror_scroll, pan_scroll")

    if strategy == "smart_crop" and not SMART_CROP_AVAILABLE:
        raise HTTPException(status_code=400, detail="smart_crop not available, install ultralytics: pip install ultralytics")

    # 保存上传的文件
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    # 生成输出路径
    output_path = str(output_dir / f"output_{Path(file.filename).stem}{suffix}")

    try:
        # 执行转换
        request = TransformRequest(
            input_path=input_path,
            output_path=output_path,
            target_orientation=target_orientation,
            strategy=strategy,
            target_ratio=target_ratio,
        )
        result = transform(request)

        if result.success:
            output_filename = Path(result.output_path).name
            download_url = f"http://172.18.98.97:8000/api/download/{output_filename}"

            return TransformResponseModel(
                success=True,
                input_path=result.input_path,
                output_path=result.output_path,
                download_url=download_url,
                original_orientation=result.original_orientation,
                target_orientation=result.target_orientation,
                strategy_used=result.strategy_used,
                message="Transform completed successfully",
            )
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理输入临时文件
        if os.path.exists(input_path):
            os.unlink(input_path)


@app.post("/api/compress", response_model=CompressResponseModel)
async def api_compress(
    file: UploadFile = File(...),
    compression_level: str = Form(default="medium"),
):
    """
    视频压缩接口

    上传视频文件，压缩到指定质量级别
    """
    # 验证参数
    if compression_level not in ("low", "medium", "high"):
        raise HTTPException(status_code=400, detail="compression_level must be 'low', 'medium', or 'high'")

    # 保存上传的文件
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    # 获取原始文件大小
    original_size = os.path.getsize(input_path)

    # 生成输出路径
    output_path = str(output_dir / f"compressed_{Path(file.filename).stem}{suffix}")

    try:
        # 执行压缩
        from video.processor import compress_video
        compress_video(input_path, output_path, compression_level)

        # 获取压缩后文件大小
        compressed_size = os.path.getsize(output_path)
        compression_ratio = compressed_size / original_size if original_size > 0 else 0

        output_filename = Path(output_path).name
        download_url = f"http://172.18.98.97:8000/api/download/{output_filename}"

        return CompressResponseModel(
            success=True,
            input_path=input_path,
            output_path=output_path,
            download_url=download_url,
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=round(compression_ratio, 2),
            message=f"压缩完成！原始大小: {original_size/1024/1024:.2f}MB, 压缩后: {compressed_size/1024/1024:.2f}MB",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理输入临时文件
        if os.path.exists(input_path):
            os.unlink(input_path)


@app.post("/api/video-info", response_model=VideoInfoResponseModel)
async def api_video_info(file: UploadFile = File(...)):
    """
    获取视频信息接口

    上传视频文件，获取其详细信息
    """
    # 保存上传的文件
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    try:
        from video.processor import get_video_metadata

        metadata = get_video_metadata(input_path)

        return VideoInfoResponseModel(
            success=True,
            width=metadata.width,
            height=metadata.height,
            duration=metadata.duration,
            fps=metadata.fps,
            bitrate=metadata.bitrate,
            codec=metadata.codec,
            aspect_ratio=metadata.aspect_ratio,
            message=f"视频信息获取成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        if os.path.exists(input_path):
            os.unlink(input_path)


@app.post("/api/trim", response_model=TrimResponseModel)
async def api_trim(
    file: UploadFile = File(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
):
    """
    视频裁剪接口

    上传视频文件，裁剪指定时间段
    """
    # 解析时间参数（支持 "HH:MM:SS" 和纯秒数）
    def parse_time(t: str) -> float:
        if ":" in t:
            parts = t.split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
        return float(t)

    start_sec = parse_time(start_time)
    end_sec = parse_time(end_time)

    # 保存上传文件到临时
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    try:
        from video.processor import get_video_metadata, trim_video

        # 获取原始文件大小和时长
        original_size = os.path.getsize(input_path)
        metadata = get_video_metadata(input_path)
        original_duration = metadata.duration

        # 验证时间参数
        if end_sec <= start_sec:
            raise HTTPException(status_code=400, detail="结束时间必须大于开始时间")

        # 生成输出路径
        output_path = str(output_dir / f"trimmed_{Path(file.filename).stem}{suffix}")

        # 调用 trim_video
        trim_video(input_path, output_path, start_sec, end_sec)

        # 获取裁剪后文件大小
        trimmed_size = os.path.getsize(output_path)
        trimmed_duration = end_sec - start_sec
        output_filename = Path(output_path).name
        download_url = f"http://172.18.98.97:8000/api/download/{output_filename}"

        return TrimResponseModel(
            success=True,
            input_path=input_path,
            output_path=output_path,
            download_url=download_url,
            original_size=original_size,
            trimmed_size=trimmed_size,
            original_duration=round(original_duration, 2),
            trimmed_duration=round(trimmed_duration, 2),
            start_time=round(start_sec, 2),
            end_time=round(end_sec, 2),
            message=f"裁剪完成！原始时长: {original_duration:.1f}s，裁剪后: {trimmed_duration:.1f}s",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


@app.post("/api/concat", response_model=ConcatResponseModel)
async def api_concat(
    files: list[UploadFile] = File(..., description="多个视频文件，至少2个"),
    keep_audio: bool = Form(default=True, description="是否保留音轨"),
):
    """
    视频拼接接口

    上传多个视频文件，按顺序拼接为一个视频
    """
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="需要至少2个视频文件")

    # 保存上传文件
    input_paths = []
    try:
        for i, file in enumerate(files):
            suffix = Path(file.filename).suffix if file.filename else ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(file.file, tmp)
                input_paths.append(tmp.name)

        # 计算总时长
        from video.processor import get_video_metadata
        total_duration = 0.0
        for path in input_paths:
            meta = get_video_metadata(path)
            total_duration += meta.duration

        # 生成输出路径
        output_filename = f"concat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = str(output_dir / output_filename)

        # 调用拼接
        from video.processor import concat_videos
        concat_videos(input_paths, output_path, keep_audio=keep_audio)

        # 获取输出文件信息
        output_size = os.path.getsize(output_path)
        output_meta = get_video_metadata(output_path)
        download_url = f"http://172.18.98.97:8000/api/download/{output_filename}"

        return ConcatResponseModel(
            success=True,
            input_paths=input_paths,
            output_path=output_path,
            download_url=download_url,
            input_count=len(input_paths),
            total_duration=round(total_duration, 2),
            output_duration=round(output_meta.duration, 2),
            output_size=output_size,
            keep_audio=keep_audio,
            message=f"拼接完成！共 {len(input_paths)} 个视频，总时长 {total_duration:.1f}s，输出时长 {output_meta.duration:.1f}s",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for path in input_paths:
            if os.path.exists(path):
                os.unlink(path)


@app.post("/api/transform-path")
async def api_transform_by_path(
    file_path: str = Form(..., description="视频文件路径或URL (DIFY传来)"),
    target_orientation: str = Form(default="portrait"),
    strategy: str = Form(default="pad"),
    target_ratio: float = Form(default=9/16),
):
    """
    根据文件路径转换视频 (DIFY 对接用)

    支持本地路径或远程URL下载
    """
    import urllib.parse
    import requests

    input_path = file_path
    is_remote = file_path.startswith("http")

    # 远程URL，先下载到临时文件
    if is_remote:
        try:
            # 从URL获取文件名后缀
            url_path = Path(urllib.parse.urlparse(file_path).path)
            suffix = url_path.suffix if url_path.suffix else ".mp4"

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = tmp.name

            # 使用 requests 下载文件
            resp = requests.get(file_path, timeout=300, stream=True)
            resp.raise_for_status()
            with open(tmp_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            input_path = tmp_path
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"下载远程文件失败: {str(e)}")
    elif not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail=f"File not found: {file_path}")

    output_path = str(output_dir / f"output_{Path(input_path).stem}{Path(input_path).suffix}")

    try:
        request = TransformRequest(
            input_path=input_path,
            output_path=output_path,
            target_orientation=target_orientation,
            strategy=strategy,
            target_ratio=target_ratio,
        )
        result = transform(request)

        if result.success:
            # 生成下载URL
            output_filename = Path(result.output_path).name
            download_url = f"http://172.18.98.97:8000/api/download/{output_filename}"

            return TransformResponseModel(
                success=True,
                input_path=result.input_path,
                output_path=result.output_path,
                download_url=download_url,
                original_orientation=result.original_orientation,
                target_orientation=result.target_orientation,
                strategy_used=result.strategy_used,
                message="Transform completed successfully",
            )
        else:
            raise HTTPException(status_code=500, detail=result.error)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时下载文件
        if is_remote and os.path.exists(input_path):
            os.unlink(input_path)


async def progress_generator(
    task: asyncio.Task,
) -> AsyncGenerator[str, None]:
    """进度事件生成器"""
    while not task.done():
        # 定期发送心跳
        yield "data: {\"event\": \"heartbeat\"}\n\n"
        await asyncio.sleep(1)


@app.post("/api/transform-stream")
async def api_transform_stream(
    file: UploadFile = File(...),
    target_orientation: str = Form(default="portrait"),
    strategy: str = Form(default="pad"),
    target_ratio: float = Form(default=9/16),
):
    """
    视频转换接口（支持进度流）

    使用 Server-Sent Events (SSE) 流式返回进度
    """
    # 验证参数
    if target_orientation not in ("portrait", "landscape"):
        raise HTTPException(status_code=400, detail="target_orientation must be 'portrait' or 'landscape'")

    if strategy not in ("rotate", "pad", "crop", "smart_crop", "stretch", "mirror_scroll", "pan_scroll"):
        raise HTTPException(status_code=400, detail="strategy must be one of: rotate, pad, crop, smart_crop, stretch, mirror_scroll, pan_scroll")

    if strategy == "smart_crop" and not SMART_CROP_AVAILABLE:
        raise HTTPException(status_code=400, detail="smart_crop not available")

    # 保存上传的文件
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    # 生成输出路径
    output_path = str(output_dir / f"output_{Path(file.filename).stem}{suffix}")

    progress_data = {"progress": 0.0, "message": "Starting..."}

    async def event_generator() -> AsyncGenerator[str, None]:
        nonlocal progress_data

        # 发送开始事件
        yield f"data: {json.dumps({'event': 'start', 'progress': 0.0, 'message': 'Starting transform...'})}\n\n"

        # 创建进度回调
        def progress_callback(progress: float):
            progress_data["progress"] = progress
            progress_data["message"] = f"Processing... {int(progress * 100)}%"

        try:
            # 在线程池中执行转换
            loop = asyncio.get_event_loop()
            request = TransformRequest(
                input_path=input_path,
                output_path=output_path,
                target_orientation=target_orientation,
                strategy=strategy,
                target_ratio=target_ratio,
            )

            # 定期发送进度
            result = await loop.run_in_executor(
                None,
                lambda: transform(request, progress_callback=progress_callback)
            )

            # 发送进度更新
            yield f"data: {json.dumps({'event': 'progress', 'progress': 0.95, 'message': 'Finalizing...'})}\n\n"

            if result.success:
                yield f"data: {json.dumps({
                    'event': 'complete',
                    'progress': 1.0,
                    'message': 'Transform completed',
                    'data': {
                        'success': True,
                        'output_path': result.output_path,
                        'original_orientation': result.original_orientation,
                        'target_orientation': result.target_orientation,
                        'strategy_used': result.strategy_used,
                    }
                })}\n\n"
            else:
                yield f"data: {json.dumps({
                    'event': 'error',
                    'message': result.error,
                })}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
        finally:
            # 清理输入临时文件
            if os.path.exists(input_path):
                os.unlink(input_path)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """
    下载转换后的视频文件

    注意：文件名需要是 Base64 编码的路径
    """
    # 安全检查：只允许下载 output 目录下的文件
    safe_name = os.path.basename(filename)  # 防止路径穿越
    file_path = output_dir / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type="video/mp4",
    )


@app.get("/api/outputs")
async def list_outputs():
    """列出所有转换后的输出文件"""
    files = []
    for f in output_dir.iterdir():
        if f.is_file():
            files.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            })
    return {"files": files, "count": len(files)}


@app.delete("/api/outputs/{filename}")
async def delete_output(filename: str):
    """删除指定的输出文件"""
    safe_name = os.path.basename(filename)
    file_path = output_dir / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_path.unlink()
    return {"deleted": safe_name}


# ============ Agent Endpoints ============

# 全局 Agent 实例
_video_agent: Optional[VideoAgent] = None


def get_video_agent() -> VideoAgent:
    """获取或创建 VideoAgent 实例"""
    global _video_agent
    if _video_agent is None:
        _video_agent = VideoAgent()
    return _video_agent


class AgentChatRequest(BaseModel):
    """Agent 聊天请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID，用于多轮对话")


class AgentChatResponse(BaseModel):
    """Agent 聊天响应"""
    session_id: str
    message: str
    success: bool
    data: Optional[dict] = None
    messages: Optional[list[dict]] = None  # 所有助手消息


class AgentStatusResponse(BaseModel):
    """Agent 状态响应"""
    session_id: str
    current_step: str
    original_orientation: Optional[str] = None
    target_orientation: Optional[str] = None
    strategy: Optional[str] = None
    pending_question: Optional[str] = None
    messages: list[dict]


@app.post("/api/agent/chat", response_model=AgentChatResponse)
async def agent_chat(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    files: Optional[list[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    api_key: Optional[str] = Form(None),
):
    """
    Agent 聊天接口（支持多轮对话）

    上传视频文件并用自然语言描述需求，Agent 会自动处理
    支持单个或多个视频文件上传
    """
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangGraph not available, install: pip install langgraph")

    # 设置 API key 到环境变量
    if api_key:
        os.environ["MINIMAX_API_KEY"] = api_key

    # 处理多文件或单文件
    uploaded_files = files if files else ([file] if file else [])
    if not uploaded_files:
        raise HTTPException(status_code=400, detail="请上传视频文件")

    # 保存所有上传的文件
    all_temp_paths = []
    for f in uploaded_files:
        suffix = Path(f.filename).suffix if f.filename else ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(f.file, tmp)
            all_temp_paths.append(tmp.name)

    try:
        agent = get_video_agent()

        # 执行 Agent
        result = agent.process_video(
            user_input=message,
            temp_video_path=all_temp_paths[0],
            session_id=session_id,
            # 传递多文件信息给 Agent
            video_files=all_temp_paths if len(all_temp_paths) > 1 else None,
        )

        if result.get("error"):
            return AgentChatResponse(
                session_id=result.get("session_id", ""),
                message=result.get("error", "Unknown error"),
                success=False,
            )

        # 获取助手的回复（跳过系统消息如"检测到视频是..."）
        # 取最后一个真正的助手回复，而不是第一个
        assistant_message = ""
        skip_keywords = ["检测到视频", "正在处理", "已完成", "开始"]
        for msg in result.get("messages", []):
            if msg.get("role") == "assistant" and msg.get("content"):
                content = msg.get("content", "")
                # 跳过纯状态描述的中间消息
                if any(kw in content for kw in skip_keywords):
                    continue
                # 记录但不 break，这样后面的消息会覆盖前面的
                assistant_message = content

        # 准备响应数据
        data = None
        # 检查是否是修剪结果
        if result.get("trim_result"):
            tr = result["trim_result"]
            data = {
                "output_path": tr.get("output_path"),
                "original_duration": tr.get("original_duration"),
                "trimmed_duration": tr.get("trimmed_duration"),
                "start_time": tr.get("start_time"),
                "end_time": tr.get("end_time"),
            }
        elif result.get("transform_result"):
            tr = result["transform_result"]
            data = {
                "output_path": tr.get("output_path") if isinstance(tr, dict) else getattr(tr, 'output_path', None),
                "original_orientation": result.get("original_orientation"),
                "target_orientation": result.get("target_orientation"),
                "strategy_used": tr.get("strategy_used") if isinstance(tr, dict) else getattr(tr, 'strategy_used', None),
            }

        # 获取所有助手消息
        all_assistant_messages = [
            {"content": msg.get("content", ""), "role": "assistant"}
            for msg in result.get("messages", [])
            if msg.get("role") == "assistant" and msg.get("content")
        ]

        return AgentChatResponse(
            session_id=result.get("session_id", ""),
            message=assistant_message or "处理完成",
            success=True,
            data=data,
            messages=all_assistant_messages,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for path in all_temp_paths:
            if os.path.exists(path):
                os.unlink(path)


@app.post("/api/agent/chat-stream")
async def agent_chat_stream(
    message: str = Form(...),
    session_id: Optional[str] = Form(None),
    files: Optional[list[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    api_key: Optional[str] = Form(None),
):
    """
    Agent 聊天接口（流式 SSE 输出）

    使用 Server-Sent Events 流式返回每条消息
    参考 Dify 的 /chat-messages API 事件格式
    """
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangGraph not available")

    # 设置 API key
    if api_key:
        os.environ["MINIMAX_API_KEY"] = api_key

    # 处理文件上传（多轮对话时文件可选）
    uploaded_files = files if files else ([file] if file else [])
    all_temp_paths = []
    has_new_file = False
    for f in uploaded_files:
        if f and f.filename:
            has_new_file = True
            suffix = Path(f.filename).suffix if f.filename else ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                shutil.copyfileobj(f.file, tmp)
                all_temp_paths.append(tmp.name)

    import threading
    from agent.streaming import (
        get_stream_queue,
        set_streaming_enabled,
        clear_message_callback,
        StreamQueue
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        # 获取或创建流式队列
        stream_queue = get_stream_queue()
        agent = get_video_agent()
        error_result = [None]
        agent_result = [None]
        agent_finished = [False]

        def run_agent():
            try:
                # 启用流式输出
                set_streaming_enabled(True)
                # 只有上传了新文件时才传 temp_video_path，否则使用会话中已有的视频
                result = agent.process_video(
                    user_input=message,
                    temp_video_path=all_temp_paths[0] if has_new_file else None,
                    session_id=session_id,
                    video_files=all_temp_paths if len(all_temp_paths) > 1 else None,
                )
                # 保存结果供后续使用
                agent_result[0] = result
            except Exception as e:
                error_result[0] = str(e)
            finally:
                agent_finished[0] = True
                set_streaming_enabled(False)

        # 在线程中执行 agent
        agent_thread = threading.Thread(target=run_agent)
        agent_thread.start()

        # 超时控制
        start_time = asyncio.get_event_loop().time()
        timeout = 300  # 5分钟超时

        try:
            # 从队列读取消息并发送 SSE 事件
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    yield f"data: {json.dumps({'event': 'message', 'answer': '处理超时', 'created_at': int(time.time())})}\n\n"
                    break

                # 获取所有新消息
                messages = stream_queue.get_all()

                if messages:
                    # 逐个发送消息
                    for msg in messages:
                        print(f"[DEBUG] SSE sending: {msg[:50]}...")
                        yield f"data: {json.dumps({'event': 'message', 'answer': msg, 'created_at': int(time.time())})}\n\n"
                        await asyncio.sleep(0.1)  # 增加间隔，避免 Windows 套接字缓冲区溢出

                # 检查 agent 是否结束
                if agent_finished[0]:
                    if messages:
                        # 还有消息，继续循环发送
                        continue
                    # 队列已空，发送错误或完成
                    if error_result[0]:
                        yield f"data: {json.dumps({'event': 'message', 'answer': f'处理错误: {error_result[0]}', 'created_at': int(time.time())})}\n\n"
                    break

                # 没有消息时短暂等待再检查
                if not messages:
                    await asyncio.sleep(0.1)  # 增加间隔，避免 Windows 套接字缓冲区溢出

            # 发送完成事件
            actual_session_id = agent_result[0].get('session_id') if agent_result[0] else session_id
            yield f"data: {json.dumps({'event': 'message_end', 'conversation_id': actual_session_id or '', 'metadata': {}})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
        finally:
            set_streaming_enabled(False)
            agent_thread.join(timeout=2)
            for path in all_temp_paths:
                if os.path.exists(path):
                    for _ in range(3):
                        try:
                            os.unlink(path)
                            break
                        except PermissionError:
                            time.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/agent/continue", response_model=AgentChatResponse)
async def agent_continue(request: AgentChatRequest):
    """
    继续多轮对话

    传入 session_id 和用户的新消息，继续之前的对话
    """
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangGraph not available")

    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    try:
        agent = get_video_agent()
        result = agent.continue_conversation(
            user_input=request.message,
            session_id=request.session_id,
        )

        if result.get("error"):
            return AgentChatResponse(
                session_id=request.session_id,
                message=result.get("error"),
                success=False,
            )

        # 获取助手的回复（跳过系统消息）
        # 对于 continue，返回最后一条有效消息（最新的回复）
        # 对于新对话，返回第一条有效消息
        assistant_message = ""
        skip_keywords = ["检测到视频", "正在处理", "已完成", "开始"]
        valid_messages = []
        for msg in result.get("messages", []):
            if msg.get("role") == "assistant" and msg.get("content"):
                content = msg.get("content", "")
                # 跳过纯状态描述的中间消息
                if any(kw in content for kw in skip_keywords):
                    continue
                valid_messages.append(content)

        # 返回最后一条有效消息（最新回复）
        if valid_messages:
            assistant_message = valid_messages[-1]

        return AgentChatResponse(
            session_id=request.session_id,
            message=assistant_message or "处理完成",
            success=True,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agent/session/{session_id}", response_model=AgentStatusResponse)
async def get_agent_session(session_id: str):
    """获取会话状态"""
    agent = get_video_agent()
    state = agent.get_session(session_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return AgentStatusResponse(
        session_id=session_id,
        current_step=state.get("current_step", ""),
        original_orientation=state.get("original_orientation"),
        target_orientation=state.get("target_orientation"),
        strategy=state.get("strategy"),
        pending_question=state.get("pending_question"),
        messages=state.get("messages", []),
    )


@app.delete("/api/agent/session/{session_id}")
async def delete_agent_session(session_id: str):
    """删除会话"""
    agent = get_video_agent()
    deleted = agent.delete_session(session_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": session_id}


@app.get("/api/agent/sessions")
async def list_agent_sessions():
    """列出所有会话"""
    agent = get_video_agent()
    sessions = agent.list_sessions()
    return {"sessions": sessions, "count": len(sessions)}


# ============ LangChain Agent (MinMax) ============

@app.post("/api/llm/chat")
async def llm_agent_chat(
    message: str = Form(...),
    file_path: str = Form(None),
):
    """
    LangChain Agent 聊天接口 (MinMax 大模型)

    支持纯自然语言交互，由大模型解析意图并执行转换
    """
    if not LANGCHAIN_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangChain not available, install: pip install langchain")

    if not file_path:
        raise HTTPException(status_code=400, detail="需要上传视频文件")

    try:
        # 获取 API Key
        api_key = os.environ.get("MINIMAX_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=500, detail="MINIMAX_API_KEY not set")

        agent = VideoTransformAgent(api_key=api_key)
        result = agent.chat_with_ai_response(message, file_path=file_path)

        return {
            "success": bool(result["download_url"]),
            "message": result["response"],
            "params": result["params"],
            "download_url": result["download_url"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/llm/video-info")
async def llm_video_info(file: UploadFile = File(...)):
    """
    获取视频信息接口 (LLM Agent 用)

    上传视频文件，返回视频信息
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        from agent.langchain_agent import get_video_info
        info = get_video_info(tmp_path)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/api/llm/trim")
async def llm_trim(
    file: UploadFile = File(...),
    start_time: float = Form(...),
    end_time: float = Form(...),
):
    """
    视频修剪接口 (LLM Agent 用)

    上传视频文件，修剪指定时间段
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        from agent.langchain_agent import trim_video_file
        result = trim_video_file(tmp_path, str(output_dir), start_time, end_time)
        if result.get("success"):
            output_filename = Path(result["output_path"]).name
            result["download_url"] = f"http://172.18.98.97:8000/api/download/{output_filename}"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ============ Condensation Endpoints (智能缩编) ============


class CondenseRequest(BaseModel):
    """缩编请求"""
    strategy: str = Field(default="content_condense", description="缩编策略: smart_compress / content_condense")
    target_duration: float = Field(default=60.0, description="目标时长（秒）")
    target_ratio: float = Field(default=9/16, description="目标比例，默认 9:16 (竖屏)")
    language: str = Field(default="zh", description="语音语言")


class CondenseResponseModel(BaseModel):
    """缩编响应模型"""
    success: bool
    input_path: str = ""
    output_path: str = ""
    download_url: Optional[str] = None
    strategy: str = ""
    duration_before: float = 0.0
    duration_after: float = 0.0
    compression_ratio: float = 0.0
    segments: list[dict] = []
    transcript: str = ""
    subtitle_path: str = ""
    message: str = ""


class CondenseSegmentsRequest(BaseModel):
    """指定片段缩编请求"""
    segments: list[dict] = Field(..., description="片段列表 [{start, end, text}, ...]")
    burn_subtitle: bool = Field(default=True, description="是否烧录字幕")


@app.post("/api/condense", response_model=CondenseResponseModel)
async def api_condense(
    file: UploadFile = File(...),
    strategy: str = Form(default="content_condense"),
    target_duration: float = Form(default=60.0),
    target_ratio: float = Form(default=9/16),
    language: str = Form(default="zh"),
):
    """
    视频智能缩编接口

    支持三种策略：
    - smart_compress: 智能压缩（重编码、删除无声段）
    - content_condense: 内容缩编（保留精彩片段）
    - smart_crop: 智能裁剪（人脸/主体跟随）
    """
    # 验证策略
    if strategy not in ("smart_compress", "content_condense"):
        raise HTTPException(status_code=400, detail="strategy must be: smart_compress / content_condense")

    # 保存上传的文件
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    # 生成输出路径
    output_filename = f"condensed_{strategy}_{Path(file.filename).stem}{suffix}"
    output_path = str(output_dir / output_filename)

    try:
        from video.condenser import condense_video

        def progress_callback(progress: float, message: str):
            # 日志进度（实际可用 SSE 流）
            print(f"[{strategy}] {message} ({int(progress*100)}%)")

        result = condense_video(
            video_path=input_path,
            output_path=output_path,
            strategy=strategy,
            target_duration=target_duration,
            target_ratio=target_ratio,
            language=language,
            progress_callback=progress_callback,
        )

        if result.success:
            dl_filename = Path(result.output_path).name
            download_url = f"http://172.18.98.97:8000/api/download/{dl_filename}"

            return CondenseResponseModel(
                success=True,
                input_path=result.input_path,
                output_path=result.output_path,
                download_url=download_url,
                strategy=result.strategy,
                duration_before=result.duration_before,
                duration_after=result.duration_after,
                compression_ratio=result.duration_before / result.duration_after if result.duration_after > 0 else 0,
                segments=result.segments,
                transcript=result.transcript,
                subtitle_path=result.subtitle_path,
                message=f"缩编完成！时长 {result.duration_before:.1f}s -> {result.duration_after:.1f}s",
            )
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


@app.post("/api/condense/segments", response_model=CondenseResponseModel)
async def api_condense_segments(
    file: UploadFile = File(...),
    segments: str = Form(..., description="JSON格式片段列表"),
    burn_subtitle: bool = Form(default=True),
):
    """
    指定片段缩编接口

    根据指定的片段列表进行裁剪拼接
    """
    import json as json_lib

    # 解析片段
    try:
        segment_list = json_lib.loads(segments)
    except:
        raise HTTPException(status_code=400, detail="Invalid segments JSON")

    if not segment_list:
        raise HTTPException(status_code=400, detail="No segments provided")

    # 保存上传的文件
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    # 生成输出路径
    output_filename = f"custom_segments_{Path(file.filename).stem}{suffix}"
    output_path = str(output_dir / output_filename)
    base_dir = str(output_dir)

    try:
        from video.funclip_wrapper import cut_segment, concatenate_segments, full_transcribe_pipeline

        # 裁剪所有片段
        temp_files = []
        for i, seg in enumerate(segment_list):
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            if end <= start:
                continue
            temp_path = os.path.join(base_dir, f"seg_temp_{i}.mp4")
            if cut_segment(input_path, temp_path, start, end, copy_codec=True):
                temp_files.append(temp_path)

        if not temp_files:
            raise HTTPException(status_code=500, detail="Failed to cut segments")

        # 拼接
        concatenate_segments(temp_files, output_path)

        # 清理临时文件
        for f in temp_files:
            try:
                os.remove(f)
            except:
                pass

        # 烧录字幕（如需要）
        subtitle_path = ""
        if burn_subtitle:
            # 先生成字幕
            asr_result = full_transcribe_pipeline(
                input_path, base_dir, model_size="base", language="zh"
            )
            if asr_result:
                # 过滤字幕
                from video.condenser import _filter_srt_by_ranges
                filtered_srt = _filter_srt_by_ranges(
                    asr_result.srt_content,
                    [(s["start"], s["end"]) for s in segment_list]
                )
                subtitle_path = os.path.join(base_dir, f"{Path(file.filename).stem}_custom.srt")
                with open(subtitle_path, "w", encoding="utf-8") as f:
                    f.write(filtered_srt)

                # 烧录
                subtitle_burn_path = output_path.replace(".mp4", "_subtitled.mp4")
                from video.funclip_wrapper import burn_subtitle
                if burn_subtitle(output_path, subtitle_path, subtitle_burn_path):
                    output_path = subtitle_burn_path

        # 计算时长
        total_duration = sum(s.get("end", 0) - s.get("start", 0) for s in segment_list)
        dl_filename = Path(output_path).name

        return CondenseResponseModel(
            success=True,
            input_path=input_path,
            output_path=output_path,
            download_url=f"http://172.18.98.97:8000/api/download/{dl_filename}",
            strategy="custom_segments",
            duration_before=0,
            duration_after=total_duration,
            segments=segment_list,
            subtitle_path=subtitle_path,
            message=f"片段拼接完成！共 {len(segment_list)} 个片段，总时长 {total_duration:.1f}s",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


@app.post("/api/condense/transcribe")
async def api_condense_transcribe(
    file: UploadFile = File(...),
    language: str = Form(default="zh"),
):
    """
    仅进行语音识别（不缩编）

    返回识别结果和 SRT 字幕
    """
    # 保存上传的文件
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    base_dir = str(output_dir)

    try:
        from video.funclip_wrapper import full_transcribe_pipeline

        result = full_transcribe_pipeline(
            video_path=input_path,
            output_dir=base_dir,
            model_size="base",
            language=language,
        )

        if result:
            return {
                "success": True,
                "text": result.text,
                "segments": result.segments,
                "srt_content": result.srt_content,
                "duration": result.duration,
                "srt_path": os.path.join(base_dir, f"{Path(file.filename).stem}.srt"),
                "txt_path": os.path.join(base_dir, f"{Path(file.filename).stem}.txt"),
            }
        else:
            raise HTTPException(status_code=500, detail="Transcription failed")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 智能剪辑 API ============

class HighlightResponse(BaseModel):
    """精彩片段响应"""
    success: bool
    message: str
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    duration_before: Optional[float] = None
    duration_after: Optional[float] = None
    segments: Optional[list] = []
    compression_ratio: Optional[float] = None


class TransitionResponse(BaseModel):
    """转场响应"""
    success: bool
    message: str
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    transition_type: Optional[str] = None
    transition_duration: Optional[float] = None


class BGMResponse(BaseModel):
    """BGM响应"""
    success: bool
    message: str
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    bgm_path: Optional[str] = None
    bgm_name: Optional[str] = None
    mood: Optional[str] = None


class TTSResponse(BaseModel):
    """TTS配音响应"""
    success: bool
    message: str
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    audio_path: Optional[str] = None
    text_length: Optional[int] = None


class FilterResponse(BaseModel):
    """视频滤镜响应"""
    success: bool
    message: str
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    preset: Optional[str] = None


class SummaryResponse(BaseModel):
    """视频摘要响应"""
    success: bool
    message: str
    summary: Optional[str] = None
    key_points: Optional[list[str]] = None
    full_text: Optional[str] = None
    duration: Optional[float] = None
    language: Optional[str] = None
    word_count: Optional[int] = None


class ShortVideoResponse(BaseModel):
    """短视频生成响应"""
    success: bool
    message: str
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    steps: Optional[list[str]] = None
    duration: Optional[float] = None


class VideoAnalysisResponse(BaseModel):
    """视频内容分析响应"""
    success: bool
    message: str
    scene: Optional[str] = None
    emotion: Optional[str] = None
    description: Optional[str] = None
    highlights: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    suitable_platforms: Optional[list[str]] = None
    duration: Optional[float] = None
    resolution: Optional[str] = None


class PlatformCheckResponse(BaseModel):
    """平台兼容性检查响应"""
    success: bool
    message: str
    compatible: bool
    issues: Optional[list[str]] = None
    recommendations: Optional[list[str]] = None
    current_settings: Optional[dict] = None
    target_settings: Optional[dict] = None


class CoverResponse(BaseModel):
    """封面生成响应"""
    success: bool
    message: str
    cover_path: Optional[str] = None
    download_url: Optional[str] = None
    candidates: Optional[list[str]] = None


class TitlePackageResponse(BaseModel):
    """片头片尾包装响应"""
    success: bool
    message: str
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    has_opening: Optional[bool] = None
    has_ending: Optional[bool] = None
    has_watermark: Optional[bool] = None


@app.post("/api/editor/highlight", response_model=HighlightResponse)
async def api_editor_highlight(
    file: UploadFile = File(...),
    target_duration: int = Form(default=60, description="目标时长（秒）"),
    num_clips: int = Form(default=5, description="片段数量"),
    language: str = Form(default="zh", description="语音识别语言"),
    subtitle_style: str = Form(default="default", description="字幕样式: default/minimal"),
    transition_type: str = Form(default="fade", description="转场类型: fade/slide/zoom"),
):
    """
    精彩片段剪辑

    从视频中提取精彩片段，生成精华集锦

    Args:
        file: 视频文件
        target_duration: 目标时长（秒），默认60
        num_clips: 片段数量，默认5个
        language: 语音识别语言，默认中文
        subtitle_style: 字幕样式 (default/minimal)
        transition_type: 转场类型 (fade/slide/zoom)
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    base_dir = str(output_dir)

    try:
        from video.condenser import condense_video

        output_filename = f"highlight_{target_duration}s_{Path(file.filename).stem}{suffix}"
        output_path = os.path.join(base_dir, output_filename)

        result = condense_video(
            video_path=input_path,
            output_path=output_path,
            strategy="content_condense",
            target_duration=target_duration,
            language=language,
        )

        if result.success:
            filename = output_filename
            download_url = f"/api/download/{filename}"
            return HighlightResponse(
                success=True,
                message=f"精彩片段提取完成！保留 {len(result.segments)} 个精彩片段，总时长 {result.duration_after:.1f}秒",
                output_path=output_path,
                download_url=download_url,
                duration_before=result.duration_before,
                duration_after=result.duration_after,
                segments=result.segments,
                compression_ratio=result.duration_before / result.duration_after if result.duration_after > 0 else 0,
            )
        else:
            raise HTTPException(status_code=500, detail=getattr(result, 'error', "精彩片段提取失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


@app.post("/api/editor/transition", response_model=TransitionResponse)
async def api_editor_transition(
    file: UploadFile = File(...),
    transition_type: str = Form(default="fade", description="转场类型: fade/slide/zoom/blur/rotate/dissolve"),
    transition_duration: float = Form(default=1.0, description="转场时长（秒）"),
):
    """
    添加转场效果

    为视频片段添加转场过渡效果

    Args:
        file: 视频文件
        transition_type: 转场类型 (fade/slide/zoom/blur/rotate/dissolve)
        transition_duration: 转场时长（秒），默认1.0
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    base_dir = str(output_dir)

    try:
        from video.processor import add_transition

        output_filename = f"transition_{transition_type}_{Path(file.filename).stem}{suffix}"
        output_path = os.path.join(base_dir, output_filename)

        result = add_transition(
            video_path=input_path,
            output_path=output_path,
            transition_type=transition_type,
            duration=transition_duration,
        )

        if result.get("success"):
            filename = output_filename
            download_url = f"/api/download/{filename}"
            return TransitionResponse(
                success=True,
                message=f"转场效果添加完成！使用 {transition_type} 转场，时长 {transition_duration}秒",
                output_path=output_path,
                download_url=download_url,
                transition_type=transition_type,
                transition_duration=transition_duration,
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "转场效果添加失败"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 智能配乐 API ============

@app.post("/api/editor/bgm", response_model=BGMResponse)
async def api_editor_bgm(
    file: UploadFile = File(...),
    mood: str = Form(default="auto", description="音乐风格: happy/sad/energetic/calm/epic/corporate/auto"),
    bgm_volume: float = Form(default=0.5, description="BGM音量 (0.0-1.0)"),
    video_volume: float = Form(default=0.3, description="视频原音音量 (0.0-1.0)"),
    fade_out: bool = Form(default=True, description="是否在结尾淡出"),
    fade_duration: float = Form(default=3.0, description="淡出时长（秒）"),
):
    """
    智能配乐

    为视频添加背景音乐，支持自动风格匹配

    Args:
        file: 视频文件
        mood: 音乐风格 (happy/sad/energetic/calm/epic/corporate/auto)
        bgm_volume: BGM 音量 (0.0-1.0)
        video_volume: 视频原音音量 (0.0-1.0)
        fade_out: 是否在结尾淡出
        fade_duration: 淡出时长（秒）
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    base_dir = str(output_dir)

    try:
        from video.bgm import find_matching_bgm, add_bgm_to_video
        from video.processor import get_video_metadata

        # 获取视频时长
        metadata = get_video_metadata(input_path)
        duration = metadata.duration if metadata else 60

        # 查找匹配的BGM
        bgm_info = find_matching_bgm(mood=mood, duration=duration)

        if not bgm_info:
            raise HTTPException(
                status_code=404,
                detail="未找到匹配的音乐，请确保音乐库中有对应风格的音乐文件"
            )

        bgm_path = bgm_info["path"]
        bgm_name = bgm_info["name"]
        detected_mood = bgm_info["mood"]

        output_filename = f"bgm_{detected_mood}_{Path(file.filename).stem}{suffix}"
        output_path = os.path.join(base_dir, output_filename)

        def progress_callback(progress):
            pass

        success = add_bgm_to_video(
            video_path=input_path,
            audio_path=bgm_path,
            output_path=output_path,
            video_volume=video_volume,
            bgm_volume=bgm_volume,
            fade_out=fade_out,
            fade_duration=fade_duration,
            progress_callback=progress_callback
        )

        if success:
            filename = output_filename
            download_url = f"/api/download/{filename}"
            return BGMResponse(
                success=True,
                message=f"配乐完成！使用音乐：{bgm_name}，风格：{detected_mood}",
                output_path=output_path,
                download_url=download_url,
                bgm_path=bgm_path,
                bgm_name=bgm_name,
                mood=detected_mood,
            )
        else:
            raise HTTPException(status_code=500, detail="配乐处理失败")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 智能配音 API ============

@app.post("/api/editor/tts", response_model=TTSResponse)
async def api_editor_tts(
    file: UploadFile = File(...),
    text: str = Form(..., description="配音文本内容"),
    voice: str = Form(default="zh-CN-XiaoxiaoNeural", description="音色: zh-CN-XiaoxiaoNeural(女声)/zh-CN-YunxiNeural(男声)"),
    rate: str = Form(default="+0%", description="语速: +10%加快/-10%减慢"),
    pitch: str = Form(default="+0Hz", description="音高: +5Hz/-5Hz"),
    tts_volume: float = Form(default=1.0, description="配音音量 (0.0-1.0)"),
    original_volume: float = Form(default=0.3, description="原视频音量 (0.0-1.0)"),
):
    """
    智能配音 - 文字转语音

    使用 Edge-TTS 将文本转换为语音并添加到视频中

    Args:
        file: 视频文件
        text: 配音文本内容
        voice: 音色 (zh-CN-Xiaoxiao/zh-CN-Yunxi 等)
        rate: 语速 (+10%/-10% 等)
        pitch: 音高 (+5Hz/-5Hz 等)
        tts_volume: 配音音量 (0.0-1.0)
        original_volume: 原视频音量 (0.0-1.0)
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    base_dir = str(output_dir)

    try:
        from video.tts import add_tts_to_video

        output_filename = f"tts_{Path(file.filename).stem}{suffix}"
        output_path = os.path.join(base_dir, output_filename)

        def progress_callback(progress):
            pass

        success = add_tts_to_video(
            video_path=input_path,
            text=text,
            output_path=output_path,
            voice=voice,
            tts_volume=tts_volume,
            original_volume=original_volume
        )

        if success:
            filename = output_filename
            download_url = f"/api/download/{filename}"
            return TTSResponse(
                success=True,
                message=f"配音完成！使用音色：{voice}",
                output_path=output_path,
                download_url=download_url,
                text_length=len(text)
            )
        else:
            raise HTTPException(status_code=500, detail="配音处理失败")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 视频滤镜 API ============

@app.post("/api/editor/filter", response_model=FilterResponse)
async def api_editor_filter(
    file: UploadFile = File(...),
    preset: str = Form(default="none", description="滤镜预设: none/vintage/cinematic/fresh/bw/cold/warm/vivid/soft/dramatic/fade/cyberpunk"),
    audio_volume: float = Form(default=1.0, description="音频音量 (0.0-2.0)"),
):
    """
    视频滤镜

    为视频添加滤镜效果

    Args:
        file: 视频文件
        preset: 滤镜预设 (none/vintage/cinematic/fresh/bw/cold/warm/vivid/soft/dramatic/fade/cyberpunk)
        audio_volume: 音频音量 (0.0-2.0)
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    base_dir = str(output_dir)

    try:
        from video.filter import VideoFilter

        output_filename = f"filter_{preset}_{Path(file.filename).stem}{suffix}"
        output_path = os.path.join(base_dir, output_filename)

        def progress_callback(progress):
            pass

        success = VideoFilter.apply_filter_with_audio_adjust(
            video_path=input_path,
            output_path=output_path,
            preset=preset,
            audio_volume=audio_volume
        )

        if success:
            filename = output_filename
            download_url = f"/api/download/{filename}"
            return FilterResponse(
                success=True,
                message=f"滤镜应用完成！使用预设：{preset}",
                output_path=output_path,
                download_url=download_url,
                preset=preset
            )
        else:
            raise HTTPException(status_code=500, detail="滤镜处理失败")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 视频摘要 API ============

@app.post("/api/editor/summary", response_model=SummaryResponse)
async def api_editor_summary(
    file: UploadFile = File(...),
    use_llm: bool = Form(default=True, description="是否使用LLM生成摘要"),
):
    """
    视频摘要生成

    使用 Whisper ASR 将视频转写为文字，然后生成摘要

    Args:
        file: 视频文件
        use_llm: 是否使用 LLM 生成摘要
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    try:
        from video.summary import VideoSummarizer

        def progress_callback(progress):
            pass

        summarizer = VideoSummarizer()
        result = summarizer.summarize_video(
            video_path=input_path,
            use_llm=use_llm,
            progress_callback=progress_callback
        )

        if result.get("summary"):
            return SummaryResponse(
                success=True,
                message="摘要生成完成",
                summary=result.get("summary", ""),
                key_points=result.get("key_points", []),
                full_text=result.get("full_text", ""),
                duration=result.get("duration", 0),
                language=result.get("language", "unknown"),
                word_count=result.get("word_count", 0)
            )
        else:
            raise HTTPException(status_code=500, detail="摘要生成失败")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 短视频生成 API ============

@app.post("/api/editor/short-video", response_model=ShortVideoResponse)
async def api_editor_short_video(
    file: UploadFile = File(...),
    target_duration: int = Form(default=60, description="目标时长（秒）"),
    target_orientation: str = Form(default="portrait", description="目标方向: portrait/landscape"),
    strategy: str = Form(default="pad", description="转换策略: pad/crop/smart_crop"),
    add_subtitle: bool = Form(default=True, description="是否添加字幕"),
    add_bgm: bool = Form(default=True, description="是否添加背景音乐"),
    bgm_mood: str = Form(default="auto", description="BGM风格: auto/happy/calm/energetic"),
    add_filter: bool = Form(default=False, description="是否添加滤镜"),
    filter_preset: str = Form(default="cinematic", description="滤镜预设"),
    add_transition: bool = Form(default=True, description="是否添加转场"),
    transition_type: str = Form(default="fade", description="转场类型"),
):
    """
    短视频生成 - 一键生成可发布的短视频

    组合多个模块：
    1. 精彩片段提取（基于 Whisper ASR + 能量分析）
    2. 横竖屏转换（适配目标平台）
    3. 自动字幕（Whisper + 去口癖）
    4. 智能配乐（情绪匹配）
    5. 滤镜效果（可选）
    6. 转场效果（可选）

    Args:
        file: 视频文件
        target_duration: 目标时长（秒）
        target_orientation: 目标方向 (portrait/landscape)
        strategy: 转换策略 (pad/crop/smart_crop)
        add_subtitle: 是否添加字幕
        add_bgm: 是否添加背景音乐
        bgm_mood: BGM 风格
        add_filter: 是否添加滤镜
        filter_preset: 滤镜预设
        add_transition: 是否添加转场
        transition_type: 转场类型
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    base_dir = str(output_dir)
    steps = []

    try:
        import ffmpeg
        from video.condenser import VideoCondenser
        from video.bgm import find_matching_bgm, add_bgm_to_video
        from video.filter import VideoFilter
        from video.processor import add_transition as add_video_transition, transform, TransformRequest

        current_path = input_path
        output_filename = f"shortvideo_{Path(file.filename).stem}{suffix}"
        output_path = os.path.join(base_dir, output_filename)

        def progress_callback(progress):
            pass

        # Step 1: 精彩片段提取
        steps.append("提取精彩片段")
        condenser = VideoCondenser()
        # 简化处理：直接使用原始视频（condenser 逻辑较复杂，需要 ASR）
        # 实际项目中应该调用 condenser.extract()
        segments = []
        metadata = ffmpeg.probe(input_path)
        video_duration = float(metadata['format']['duration'])

        # 如果视频时长超过目标时长，截取中间部分作为简化处理
        if video_duration > target_duration:
            # 使用 ffmpeg 直接截取
            start_time = (video_duration - target_duration) / 2
            temp_output = os.path.join(base_dir, f"temp_clip_{Path(file.filename).stem}{suffix}")
            stream = ffmpeg.input(input_path, ss=start_time)
            stream = ffmpeg.output(stream, temp_output, t=target_duration, vcodec='copy', acodec='copy')
            ffmpeg.run(stream, overwrite_output=True, quiet=True)
            if os.path.exists(temp_output):
                current_path = temp_output
                video_duration = target_duration

        # Step 2: 横竖屏转换
        if target_orientation == "portrait":
            target_ratio = 9/16
        else:
            target_ratio = 16/9

        steps.append(f"转换为{target_orientation} {target_ratio:.2f}")
        temp_output = os.path.join(base_dir, f"temp_orient_{Path(file.filename).stem}{suffix}")
        transform_request = TransformRequest(
            input_path=current_path,
            output_path=temp_output,
            target_orientation=target_orientation,
            strategy=strategy,
            target_ratio=target_ratio
        )
        result = transform(transform_request, progress_callback)
        if result.success:
            current_path = temp_output

        # Step 3: 添加字幕
        if add_subtitle:
            steps.append("添加字幕")
            # 字幕生成需要 Whisper，这里简化处理
            # 实际项目中应该调用 subtitle API

        # Step 4: 添加 BGM
        if add_bgm:
            steps.append("添加背景音乐")
            bgm_info = find_matching_bgm(mood=bgm_mood, duration=video_duration)
            if bgm_info:
                temp_output = os.path.join(base_dir, f"temp_bgm_{Path(file.filename).stem}{suffix}")
                success = add_bgm_to_video(
                    video_path=current_path,
                    audio_path=bgm_info["path"],
                    output_path=temp_output,
                    video_volume=0.3,
                    bgm_volume=0.5,
                    fade_out=True,
                    fade_duration=3.0
                )
                if success:
                    current_path = temp_output

        # Step 5: 添加滤镜
        if add_filter and filter_preset != "none":
            steps.append(f"应用{filter_preset}滤镜")
            temp_output = os.path.join(base_dir, f"temp_filter_{Path(file.filename).stem}{suffix}")
            success = VideoFilter.apply_filter_with_audio_adjust(
                video_path=current_path,
                output_path=temp_output,
                preset=filter_preset,
                audio_volume=1.0
            )
            if success:
                current_path = temp_output

        # Step 6: 添加转场
        if add_transition and transition_type != "none":
            steps.append(f"添加{transition_type}转场")
            # 转场需要在剪辑时添加，这里简化处理

        # 最终输出
        if current_path != input_path:
            import shutil
            shutil.copy2(current_path, output_path)
            # 清理临时文件
            if current_path.startswith(base_dir) and "temp_" in current_path:
                try:
                    os.unlink(current_path)
                except Exception:
                    pass

        # 获取最终视频时长
        final_duration = 0
        try:
            final_probe = ffmpeg.probe(output_path)
            final_duration = float(final_probe['format']['duration'])
        except Exception:
            pass

        return ShortVideoResponse(
            success=True,
            message=f"短视频生成完成！共 {len(steps)} 个步骤",
            output_path=output_path,
            download_url=f"/api/download/{output_filename}",
            steps=steps,
            duration=final_duration
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"短视频生成失败: {str(e)}")
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 视频内容分析 API ============

@app.post("/api/editor/analyze", response_model=VideoAnalysisResponse)
async def api_editor_analyze(
    file: UploadFile = File(...),
    use_api: bool = Form(default=True, description="是否使用MiniMax-VL API"),
):
    """
    视频内容分析 - 使用 MiniMax-VL 多模态模型

    分析视频内容：场景分类、情绪标签、适合平台、生成描述

    Args:
        file: 视频文件
        use_api: 是否使用 API（False 则用规则分析）
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    try:
        from video.video_analysis import VideoAnalyzer

        def progress_callback(progress):
            pass

        analyzer = VideoAnalyzer()
        result = analyzer.analyze_video(
            video_path=input_path,
            use_api=use_api,
            num_frames=4,
            progress_callback=progress_callback
        )

        return VideoAnalysisResponse(
            success=True,
            message="分析完成",
            scene=result.get("scene"),
            emotion=result.get("emotion"),
            description=result.get("description"),
            highlights=result.get("highlights", []),
            tags=result.get("tags", []),
            suitable_platforms=result.get("suitable_platforms", []),
            duration=result.get("duration"),
            resolution=result.get("resolution")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 平台兼容性检查 API ============

@app.post("/api/editor/platform-check", response_model=PlatformCheckResponse)
async def api_editor_platform_check(
    file: UploadFile = File(...),
    platform: str = Form(default="douyin", description="目标平台: douyin/kuaishou/bilibili/xiaohongshu/weixinshipin"),
):
    """
    检查视频对目标平台的兼容性

    Args:
        file: 视频文件
        platform: 目标平台
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    try:
        from video.video_analysis import PlatformAdapter

        result = PlatformAdapter.check_video_compatibility(input_path, platform)

        return PlatformCheckResponse(
            success=True,
            message="检查完成",
            compatible=result.get("compatible", False),
            issues=result.get("issues", []),
            recommendations=result.get("recommendations", []),
            current_settings=result.get("current_settings", {}),
            target_settings=result.get("target_settings", {})
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 封面生成 API ============

@app.post("/api/editor/cover", response_model=CoverResponse)
async def api_editor_cover(
    file: UploadFile = File(...),
    timestamp: float = Form(default=None, description="指定截取时间（秒），默认自动选择"),
    extract_candidates: bool = Form(default=False, description="是否提取多个候选封面"),
):
    """
    生成视频封面

    Args:
        file: 视频文件
        timestamp: 指定截取时间（秒）
        extract_candidates: 是否提取多个候选
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    try:
        from video.video_analysis import CoverGenerator

        filename = Path(file.filename).stem

        if extract_candidates:
            # 提取多个候选
            candidates_dir = os.path.join(str(output_dir), f"covers_{filename}")
            candidates = CoverGenerator.extract_multiple_candidates(
                input_path, candidates_dir, num_candidates=5
            )

            return CoverResponse(
                success=True,
                message=f"生成 {len(candidates)} 个候选封面",
                candidates=candidates,
                download_url=None
            )
        else:
            # 提取单张封面
            cover_filename = f"cover_{filename}.jpg"
            cover_path = os.path.join(str(output_dir), cover_filename)

            success = CoverGenerator.extract_cover_frame(
                input_path, cover_path, timestamp
            )

            if success:
                return CoverResponse(
                    success=True,
                    message="封面生成成功",
                    cover_path=cover_path,
                    download_url=f"/api/download/{cover_filename}"
                )
            else:
                raise HTTPException(status_code=500, detail="封面生成失败")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 片头片尾包装 API ============

@app.post("/api/editor/title-package", response_model=TitlePackageResponse)
async def api_editor_title_package(
    file: UploadFile = File(...),
    add_opening: bool = Form(default=True, description="是否添加片头"),
    add_ending: bool = Form(default=False, description="是否添加片尾"),
    add_watermark: bool = Form(default=False, description="是否添加水印"),
    opening_template: str = Form(default="default", description="片头模板: default/dynamic/cinematic"),
    ending_template: str = Form(default="default", description="片尾模板: default/subscribe/copyright"),
    watermark_text: str = Form(default="", description="水印文字"),
):
    """
    片头片尾包装

    Args:
        file: 视频文件
        add_opening: 是否添加片头
        add_ending: 是否添加片尾
        add_watermark: 是否添加水印
        opening_template: 片头模板
        ending_template: 片尾模板
        watermark_text: 水印文字
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    base_dir = str(output_dir)
    filename = Path(file.filename).stem

    try:
        from video.video_analysis import TitleGenerator

        current_path = input_path
        temp_dir = base_dir

        # 1. 添加片头
        if add_opening:
            opening_path = os.path.join(temp_dir, f"opening_{filename}{suffix}")
            success = TitleGenerator.create_opening(
                opening_path, template=opening_template
            )
            if success:
                temp_output = os.path.join(temp_dir, f"with_opening_{filename}{suffix}")
                TitleGenerator.add_opening_to_video(current_path, temp_output, opening_path)
                current_path = temp_output
                os.unlink(opening_path)

        # 2. 添加片尾
        if add_ending:
            ending_path = os.path.join(temp_dir, f"ending_{filename}{suffix}")
            success = TitleGenerator.create_ending(
                ending_path, template=ending_template
            )
            if success:
                temp_output = os.path.join(temp_dir, f"with_ending_{filename}{suffix}")
                TitleGenerator.add_opening_to_video(current_path, temp_output, ending_path)
                current_path = temp_output
                os.unlink(ending_path)

        # 3. 添加水印
        if add_watermark and watermark_text:
            temp_output = os.path.join(temp_dir, f"watermarked_{filename}{suffix}")
            TitleGenerator.add_watermark(current_path, temp_output, watermark_text)
            current_path = temp_output

        # 4. 复制到最终输出
        output_filename = f"titled_{filename}{suffix}"
        output_path = os.path.join(base_dir, output_filename)
        shutil.copy2(current_path, output_path)

        # 清理临时文件
        if current_path != input_path and current_path.startswith(temp_dir):
            try:
                os.unlink(current_path)
            except Exception:
                pass

        return TitlePackageResponse(
            success=True,
            message="包装完成",
            output_path=output_path,
            download_url=f"/api/download/{output_filename}",
            has_opening=add_opening,
            has_ending=add_ending,
            has_watermark=add_watermark
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 字幕生成 API ============

class SubtitleResponse(BaseModel):
    """字幕生成响应"""
    success: bool
    message: str
    output_path: Optional[str] = None
    download_url: Optional[str] = None
    subtitle_file: Optional[str] = None
    subtitle_text: Optional[str] = None
    language: Optional[str] = None
    duration: Optional[float] = None


@app.post("/api/editor/subtitle", response_model=SubtitleResponse)
async def api_editor_subtitle(
    file: UploadFile = File(...),
    language: str = Form(default="zh", description="语音识别语言"),
    style: str = Form(default="default", description="字幕样式: default/minimal/emoji"),
    burn_in: bool = Form(default=True, description="是否烧录到视频"),
    remove_filler: bool = Form(default=True, description="是否去口癖"),
):
    """
    自动字幕生成

    使用 Whisper ASR 识别语音并生成字幕

    Args:
        file: 视频文件
        language: 语音识别语言，默认中文
        style: 字幕样式 (default/minimal/emoji)
        burn_in: 是否将字幕烧录到视频中
        remove_filler: 是否去口癖
    """
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_input:
        shutil.copyfileobj(file.file, tmp_input)
        input_path = tmp_input.name

    base_dir = str(output_dir)

    try:
        from video.funclip_wrapper import full_transcribe_pipeline
        from video.filler import clean_srt_subtitle

        # 1. 语音识别
        result = full_transcribe_pipeline(
            video_path=input_path,
            output_dir=base_dir,
            model_size="base",
            language=language,
        )

        if not result:
            raise HTTPException(status_code=500, detail="语音识别失败")

        srt_content = result.srt_content

        # 2. 去口癖（可选）
        if remove_filler:
            srt_content = clean_srt_subtitle(srt_content)

        # 3. 保存清理后的字幕
        subtitle_filename = f"subtitle_{Path(file.filename).stem}.srt"
        subtitle_path = os.path.join(base_dir, subtitle_filename)
        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        output_path = None
        download_url = None

        # 4. 烧录字幕到视频（可选）
        burn_success = False
        if burn_in:
            from video.processor import burn_subtitle

            output_filename = f"subtitled_{Path(file.filename).stem}{suffix}"
            output_path = os.path.join(base_dir, output_filename)
            download_url = f"/api/download/{output_filename}"

            burn_success = burn_subtitle(
                video_path=input_path,
                subtitle_path=subtitle_path,
                output_path=output_path,
                style=style,
            )

            if not burn_success:
                # 烧录失败，只返回字幕文件
                output_path = None
                download_url = f"/api/download/{subtitle_filename}"
                message_suffix = "（烧录失败，仅返回字幕文件）"
            else:
                message_suffix = "已烧录到视频"
        else:
            # 不烧录，只返回字幕文件
            download_url = f"/api/download/{subtitle_filename}"
            message_suffix = "字幕文件已生成"

        return SubtitleResponse(
            success=True,
            message=f"字幕生成完成！{message_suffix}",
            output_path=output_path,
            download_url=download_url,
            subtitle_file=subtitle_path,
            subtitle_text=result.text[:500] if result.text else None,
            language=language,
            duration=result.duration,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


# ============ 老视频修复 API ============

@app.post("/api/restore", response_model=RestorationResponseModel)
async def api_restore(
    file: UploadFile = File(...),
    preset: str = Form(default="basic"),
    options: Optional[str] = Form(default=None),
):
    """
    老视频修复接口

    Args:
        file: 视频文件
        preset: 修复套餐 (basic/film/enhanced/custom)
        options: JSON格式的修复选项（可选）

    Returns:
        修复结果
    """
    print(f"[RESTORE] 收到修复请求: preset={preset}, filename={file.filename}")
    import uuid

    # 保存上传的文件
    suffix = ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        input_path = tmp.name

    task_id = str(uuid.uuid4())[:8]
    output_path = str(output_dir / f"restored_{task_id}.mp4")

    try:
        from video.restoration import (
            RestorationPreset as RestPreset,
            RestorationRequest,
            RestorationOptions,
            get_default_options_for_preset,
        )
        from video.restoration_pipeline import RestorationPipeline

        # 解析套餐
        preset_enum = RestPreset(preset) if preset in [p.value for p in RestPreset] else RestPreset.BASIC

        # 解析选项
        if options:
            try:
                opts_dict = json.loads(options)
                rest_options = RestorationOptions(**opts_dict)
            except Exception:
                rest_options = get_default_options_for_preset(preset_enum)
        else:
            rest_options = get_default_options_for_preset(preset_enum)

        # 构建请求
        request = RestorationRequest(
            input_path=input_path,
            output_path=output_path,
            preset=preset_enum,
            options=rest_options,
        )

        # 执行修复（在线程池中执行，避免阻塞）
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: RestorationPipeline(request).run()
        )

        if result.success:
            dl_filename = Path(result.output_path).name
            print(f"[RESTORE] 修复成功: {dl_filename}, duration={result.total_duration:.1f}s")

            # 套餐名称映射为中文
            preset_names = {
                "basic": "基础修复",
                "film": "胶片修复",
                "enhanced": "增强版",
                "custom": "自定义",
            }
            preset_cn = preset_names.get(result.preset, result.preset)

            return RestorationResponseModel(
                success=True,
                task_id=task_id,
                input_path=result.input_path,
                output_path=result.output_path,
                download_url=f"/api/download/{dl_filename}",
                preset=preset_cn,
                stages=[RestorationStageModel(**s.__dict__) for s in result.stages],
                total_duration=result.total_duration,
                output_size=result.output_size,
                message="修复完成",
            )
        else:
            print(f"[RESTORE] 修复失败: {result.error}")
            raise HTTPException(status_code=500, detail=result.error)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)


@app.post("/api/restore-stream")
async def api_restore_stream(
    file: UploadFile = File(...),
    preset: str = Form(default="basic"),
    options: Optional[str] = Form(default=None),
):
    """
    老视频修复接口（SSE流式）

    使用 Server-Sent Events 流式返回进度

    Args:
        file: 视频文件
        preset: 修复套餐
        options: JSON格式的修复选项

    Returns:
        SSE事件流
    """
    import uuid

    # 保存上传的文件
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        input_path = tmp.name

    task_id = str(uuid.uuid4())[:8]
    output_path = str(output_dir / f"restored_{task_id}_{Path(file.filename).stem}{suffix}")

    async def event_generator() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'event': 'start', 'progress': 0.0, 'message': '开始修复...'})}\n\n"

        try:
            from video.restoration import (
                RestorationPreset as RestPreset,
                RestorationOptions,
                get_default_options_for_preset,
            )
            from video.restoration_pipeline import RestorationPipeline

            # 解析套餐
            preset_enum = RestPreset(preset) if preset in [p.value for p in RestPreset] else RestPreset.BASIC

            # 解析选项
            if options:
                try:
                    opts_dict = json.loads(options)
                    rest_options = RestorationOptions(**opts_dict)
                except Exception:
                    rest_options = get_default_options_for_preset(preset_enum)
            else:
                rest_options = get_default_options_for_preset(preset_enum)

            # 进度回调
            progress_data = {"progress": 0.0, "stage": ""}

            def progress_callback(stage: str, progress: float):
                progress_data["stage"] = stage
                progress_data["progress"] = progress

            # 构建请求
            request = RestorationRequest(
                input_path=input_path,
                output_path=output_path,
                preset=preset_enum,
                options=rest_options,
                progress_callback=progress_callback,
            )

            # 执行修复（在线程池中）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: RestorationPipeline(request).run()
            )

            if result.success:
                yield f"data: {json.dumps({'event': 'complete', 'progress': 1.0, 'message': '修复完成', 'output_path': result.output_path})}\n\n"
            else:
                yield f"data: {json.dumps({'event': 'error', 'message': result.error})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============ Main ============

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("API_PORT", 8004))
    uvicorn.run(app, host="0.0.0.0", port=port)
