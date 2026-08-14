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
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from enum import Enum

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
import json

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

output_dir = Path("F:/video")


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
    allow_credentials=True,
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
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(None),
):
    """
    Agent 聊天接口（支持多轮对话）

    上传视频文件并用自然语言描述需求，Agent 会自动处理
    """
    if not LANGGRAPH_AVAILABLE:
        raise HTTPException(status_code=500, detail="LangGraph not available, install: pip install langgraph")

    # 设置 API key 到环境变量
    if api_key:
        os.environ["MINIMAX_API_KEY"] = api_key

    # 保存上传的文件
    suffix = Path(file.filename).suffix if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        agent = get_video_agent()

        # 执行 Agent
        result = agent.process_video(
            user_input=message,
            temp_video_path=tmp_path,
            session_id=session_id,
        )

        if result.get("error"):
            return AgentChatResponse(
                session_id=result.get("session_id", ""),
                message=result.get("error", "Unknown error"),
                success=False,
            )

        # 获取助手的第一条消息（analyze_intent 的 LLM 响应）
        assistant_message = ""
        for msg in result.get("messages", []):
            if msg.get("role") == "assistant":
                assistant_message = msg.get("content", "")
                break

        # 准备响应数据
        data = None
        if result.get("transform_result"):
            tr = result["transform_result"]
            data = {
                "output_path": tr.output_path if hasattr(tr, 'output_path') else None,
                "original_orientation": result.get("original_orientation"),
                "target_orientation": result.get("target_orientation"),
                "strategy_used": tr.strategy_used if hasattr(tr, 'strategy_used') else None,
            }

        return AgentChatResponse(
            session_id=result.get("session_id", ""),
            message=assistant_message or "处理完成",
            success=True,
            data=data,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


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

        # 获取助手的最后一条消息
        assistant_message = ""
        for msg in reversed(result.get("messages", [])):
            if msg.get("role") == "assistant":
                assistant_message = msg.get("content", "")
                break

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


# ============ Main ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
