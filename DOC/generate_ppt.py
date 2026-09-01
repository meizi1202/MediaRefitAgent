"""
生成 MediaRefitAgent PPT
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import re

# 创建演示文稿
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# 颜色定义
TITLE_COLOR = RGBColor(0, 0, 0)
BODY_COLOR = RGBColor(51, 51, 51)

def add_title_slide(prs, title, subtitle=""):
    slide_layout = prs.slide_layouts[6]  # 空白布局
    slide = prs.slides.add_slide(slide_layout)

    # 标题
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(2.5), Inches(12.333), Inches(1.5))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(44)
    p.font.bold = True
    p.alignment = PP_ALIGN.CENTER

    if subtitle:
        sub_box = slide.shapes.add_textbox(Inches(0.5), Inches(4.2), Inches(12.333), Inches(0.8))
        tf = sub_box.text_frame
        p = tf.paragraphs[0]
        p.text = subtitle
        p.font.size = Pt(24)
        p.alignment = PP_ALIGN.CENTER

    return slide

def add_section_slide(prs, title):
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(3), Inches(12.333), Inches(1.5))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(40)
    p.font.bold = True
    p.alignment = PP_ALIGN.CENTER

    return slide

def add_content_slide(prs, title, content_lines):
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # 标题
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.333), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(32)
    p.font.bold = True

    # 内容
    content_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), Inches(12.333), Inches(5.5))
    tf = content_box.text_frame
    tf.word_wrap = True

    for i, line in enumerate(content_lines):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(18)
        p.space_after = Pt(6)

    return slide

def add_table_slide(prs, title, headers, rows):
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # 标题
    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.333), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(32)
    p.font.bold = True

    # 表格
    cols = len(headers)
    table = slide.shapes.add_table(len(rows) + 1, cols, Inches(0.3), Inches(1.3), Inches(12.7), Inches(5.5)).table

    # 表头
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = h
        cell.text_frame.paragraphs[0].font.bold = True
        cell.text_frame.paragraphs[0].font.size = Pt(14)

    # 数据行
    for row_idx, row in enumerate(rows):
        for col_idx, val in enumerate(row):
            cell = table.cell(row_idx + 1, col_idx)
            cell.text = str(val)
            cell.text_frame.paragraphs[0].font.size = Pt(12)

    return slide

# ========== 开始生成 ==========

# 第1页：封面
add_title_slide(prs, "MediaRefitAgent 智能体", "一站式视频智能编辑平台")

# 第2页：一句话定义
add_content_slide(prs, "一句话定义", [
    "一站式视频智能编辑平台",
    "",
    "让视频处理从\"需要学习专业软件\"变成\"说一句话就能搞定\"",
    "",
    "目标受众：广播电视台 / 内容创作者 / 平台运营者"
])

# 第3页：核心技术架构
add_content_slide(prs, "核心技术架构", [
    "┌─────────────────────────────────────────────────────────────┐",
    "│                        用户层                                │",
    "│              Web / APP / 企业内部系统                        │",
    "└─────────────────────┬───────────────────────────────────────┘",
    "                      │",
    "┌─────────────────────▼───────────────────────────────────────┐",
    "│                    Agent 层                                 │",
    "│     LangGraph 状态机  │  MinMax LLM  │  会话 Memory          │",
    "└─────────────────────┬───────────────────────────────────────┘",
    "                      │",
    "┌─────────────────────▼───────────────────────────────────────┐",
    "│                    能力层                                    │",
    "│  YOLO    │   Whisper   │   FFmpeg   │   TTS   │  滤镜/配乐  │",
    "│  智能裁剪 │   语音识别   │   视频处理  │   配音   │   超分辨率  │",
    "└─────────────────────────────────────────────────────────────┘",
])

# 第4页：技术栈
add_table_slide(prs, "技术栈",
    ["技术", "用途"],
    [
        ["FFmpeg", "专业视频编解码"],
        ["LangGraph", "大模型工作流编排"],
        ["FastAPI", "高性能异步微服务"],
        ["MinMax LLM", "自然语言意图解析"],
        ["YOLOv8", "智能主体检测"],
        ["Whisper", "语音识别"],
        ["Edge-TTS", "AI配音"],
    ]
)

# 第5页：核心功能矩阵
add_content_slide(prs, "核心功能矩阵", [
    "🎬 视频转换        │  🎬 智能缩编        │  ✂️ 智能剪辑        │  🔧 修复增强        │  📊 内容分析        │  📦 基础处理",
    "──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────",
    "横竖屏转换          │  内容缩编（高光时刻）│  固定裁剪           │  老视频修复         │  视频摘要          │  视频压缩",
    "7种转换策略         │  智能压缩（大小压缩）│  自动字幕           │  去噪/补帧          │  内容分析          │  视频修剪",
    "YOLO智能裁剪        │  -                  │  智能配乐           │  超分辨率           │  封面生成          │  视频拼接",
    "方向自动检测        │  -                  │  滤镜转场           │  色彩校正           │  平台检查          │  -",
])

# 第6页：横竖屏转换7种策略
add_table_slide(prs, "横竖屏转换 — 7种策略",
    ["策略", "说明", "状态"],
    [
        ["智能裁剪", "YOLO主体检测，AI跟随裁剪", "✅ 已完成"],
        ["填充黑边", "保持所有内容完整", "✅ 已完成"],
        ["中心裁剪", "直接裁剪中间区域", "✅ 已完成"],
        ["拉伸填充", "强行拉伸到目标比例", "✅ 已完成"],
        ["镜像滚动", "特殊视觉效果", "✅ 已完成"],
        ["平移运镜", "平移+滚动效果", "✅ 已完成"],
        ["旋转", "90°/180°/270°旋转", "⚠️ 待添加"],
    ]
)

# 第7页：智能剪辑套件
add_table_slide(prs, "智能剪辑套件",
    ["功能", "说明", "状态"],
    [
        ["固定裁剪", "从视频开头裁剪到目标时长", "✅"],
        ["自动字幕", "语音识别+智能标点", "✅"],
        ["去口癖", "自动删除语气词、停顿", "✅"],
        ["智能配乐", "情绪识别+自动BGM匹配", "✅"],
        ["配音", "AI文字转语音", "✅"],
        ["视频滤镜", "后端12种 / 前端7种", "⚠️ 7/12"],
        ["转场效果", "后端6种 / 前端3种", "✅"],
        ["内容分析", "场景识别、情绪分析、平台适配", "✅"],
        ["封面生成", "智能提取精彩帧", "✅"],
        ["片头片尾", "添加包装元素", "✅"],
    ]
)

# 第8页：智能缩编
add_content_slide(prs, "智能缩编", [
    "包含两种策略：内容缩编和智能压缩",
    "",
    "【内容缩编】Whisper语音识别+音频能量分析，自动选择高光片段到目标时长",
    "【智能压缩】FFmpeg重编码，压缩视频文件大小",
    "",
    "处理流程：",
    "1. Whisper ASR - 语音识别，获取字幕和时间轴",
    "2. 音频能量分析 - 计算每段RMS能量值",
    "3. 能量评分排序 - 归一化评分",
    "4. 智能选段 - 优先选择高分片段达到目标时长",
])

# 第9页：老视频修复
add_content_slide(prs, "老视频修复 — 4合1流水线", [
    "去噪 → 去闪烁 → 补帧 → 超分辨率",
    "",
    "第1阶段：去噪    - 消除老旧胶片噪点",
    "第2阶段：去闪烁  - 稳定画面亮度",
    "第3阶段：补帧    - 提升流畅度至60fps",
    "第4阶段：超分    - 分辨率提升4K",
])

# 第10页：大模型能力
add_table_slide(prs, "大模型能力",
    ["功能", "大模型", "作用"],
    [
        ["自然语言对话", "MinMax", "意图理解、参数提取"],
        ["智能配乐", "MinMax", "情绪识别、BGM匹配"],
        ["视频摘要", "MinMax", "内容总结生成"],
        ["内容分析", "MinMax-M3", "场景/情绪/标签"],
        ["去口癖", "MinMax", "语气词智能识别"],
        ["TTS配音", "MinMax / Edge-TTS", "文字转语音"],
    ]
)

# 第11页：GPU加速支持
add_table_slide(prs, "GPU加速支持",
    ["功能", "CPU", "GPU", "提升"],
    [
        ["YOLO智能裁剪", "~200ms/帧", "~10ms/帧", "20倍"],
        ["老视频补帧", "慢", "光流法", "10倍"],
        ["超分辨率", "很长", "实时", "实时"],
        ["内容分析", "逐帧", "批量", "5-10倍"],
    ]
)

# 第12页：技术亮点
add_table_slide(prs, "技术亮点",
    ["亮点", "说明"],
    [
        ["自然语言驱动", "一句话搞定复杂视频处理"],
        ["多轮对话", "理解上下文，连续对话修正"],
        ["流式输出", "SSE实时进度回传"],
        ["40+ API", "完整RESTful接口"],
        ["AI智能裁剪", "YOLO主体检测，保留画面重点"],
        ["模块化架构", "独立功能，易于扩展"],
    ]
)

# 第13页：客户价值
add_content_slide(prs, "客户价值 — 效率提升", [
    "传统方式                          vs          智能体方式",
    "────────────────────────────────────────────────────────────────",
    "需要学习 PR/AE 等专业软件          →          说话就能完成",
    "参数设置复杂，易出错               →          AI自动适配最优参数",
    "单个视频处理耗时数小时             →          全流程自动化，分钟级完成",
    "多平台适配需要多次导出             →          一键生成多平台版本",
])

# 第14页：展示亮点 Top 6
add_content_slide(prs, "展示亮点（Top 6）", [
    "1️⃣ \"一句话搞定\"",
    "   自然语言指令，无需学习任何专业软件",
    "",
    "2️⃣ \"主体不失真\"",
    "   YOLO智能裁剪，精准跟随画面重点",
    "",
    "3️⃣ \"老片焕新颜\"",
    "   4合1修复流水线，让老旧视频重焕生机",
    "",
    "4️⃣ \"一键成片\"",
    "   从素材到可发布状态，全流程自动化",
    "",
    "5️⃣ \"多轮记忆\"",
    "   理解上下文，连续对话式修正",
    "",
    "6️⃣ \"高光切片\"",
    "   Whisper语音识别+音频能量分析，自动提取精彩片段",
])

# 第15页：API概览
add_table_slide(prs, "API概览 — 40+ 端点覆盖",
    ["类别", "端点数", "代表功能"],
    [
        ["基础处理", "15+", "转换、压缩、裁剪、拼接"],
        ["智能剪辑", "10+", "字幕、配乐、滤镜、转场"],
        ["修复增强", "5+", "去噪、补帧、超分"],
        ["Agent对话", "6+", "聊天、继续、状态管理"],
    ]
)

# 第16页：可增强功能 - YOLO智能裁剪
add_table_slide(prs, "可增强功能 — YOLO智能裁剪",
    ["项目", "当前", "升级后"],
    [
        ["模型", "YOLOv8n (nano)", "YOLOv11x / YOLO-World"],
        ["参数量", "3.2M", "26M+"],
        ["精度(mAP)", "37.4%", "54.7%+"],
        ["推理设备", "CPU", "GPU (昇腾910B / RTX 3060)"],
        ["推理速度", "~200ms/帧", "~5ms/帧"],
        ["GPU显存需求", "-", "2GB+"],
    ]
)

# 第17页：可增强功能 - 语音识别
add_table_slide(prs, "可增强功能 — 语音识别",
    ["项目", "当前", "升级后"],
    [
        ["模型", "Whisper base", "Whisper large-v3 / SenseVoice"],
        ["参数量", "74M", "155M / 200M+"],
        ["语言支持", "中英双语", "100+ 语言"],
        ["识别准确率", "~85%", "~95%+"],
        ["推理设备", "CPU", "GPU (昇腾910B / RTX 3060)"],
    ]
)

# 第18页：可增强功能 - 老视频修复
add_content_slide(prs, "可增强功能 — 老视频修复", [
    "超分辨率：FFmpeg 基础放大  →  Real-ESRGAN / GFPGAN（真实细节重建）",
    "补帧：FFmpeg 插值  →  RIFE / AI 光流（运动连贯）",
    "去噪：FFmpeg hqdn3d  →  DenoiseGAN",
    "色彩增强：基础校正  →  DeOldify（黑白彩色化）",
    "",
    "所需资源：昇腾910B / RTX 3090 + CANN 7.0+ + 5-10GB磁盘空间",
])

# 第19页：升级路线建议
add_content_slide(prs, "升级路线建议", [
    "【视频处理升级 — 必须本地GPU】",
    "阶段一（高优先级）：YOLOv8x 升级 + 补帧(RIFE)",
    "阶段二（高优先级）：超分(Real-ESRGAN) + 去噪GAN",
    "",
    "【AI大模型升级 — 可云端API替代】",
    "阶段三（中优先级）：Whisper large-v3",
    "阶段四（中优先级）：智能配乐",
    "阶段五（低优先级）：多模态视频理解",
])

# 第20页：资源配置说明
add_content_slide(prs, "资源配置说明", [
    "【大模型（LLM）】",
    "云端调用：MinMax API / OpenAI API / Azure OpenAI（仅需网络，无GPU）",
    "本地部署：Qwen2-7B/14B/72B / Yi-34B / ChatGLM3-6B（需GPU）",
    "",
    "【视频智能编辑Agent】",
    "最低配置：4核+ CPU / 8GB内存 / 50GB SSD",
    "推荐配置：8核+ CPU / 16GB+内存 / 200GB+ SSD / GPU可选",
])

# 第21页：一体化部署方案
add_table_slide(prs, "一体化部署方案",
    ["方案", "GPU配置", "适用场景"],
    [
        ["轻量版", "RTX 4090 24GB / 昇腾910B", "中小规模，7B模型+视频处理"],
        ["标准版", "RTX 3090 24GB x2 / 昇腾910B x2", "14B模型+视频处理"],
        ["旗舰版", "A100 80GB / 昇腾910B x4", "72B模型+大规模视频并发"],
    ]
)

# 第22页：结尾
add_title_slide(prs, "谢谢", "MediaRefitAgent — 视频智能编辑，一句话的事儿")

# 保存
output_path = "f:/code/MediaRefitAgent/DOC/MediaRefitAgent_PPT_v1.0.pptx"
prs.save(output_path)
print(f"PPT 已生成：{output_path}")
