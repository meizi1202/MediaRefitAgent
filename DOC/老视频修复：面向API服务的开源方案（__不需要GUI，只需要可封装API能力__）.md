# 老视频修复：面向API服务的开源方案（\*\*不需要GUI，只需要可封装API能力\*\*）

> 你的目标：把老视频修复封装成后端 API（http 接口），输入视频文件，输出修复后的视频；**抛弃所有桌面 GUI 项目（TaTa、Video2X、Klarity 这类全部排除）**。
> 核心业务链路：`视频输入 → [可选：ProPainter划痕霉斑去除] → 时序视频复原RealBasicVSR / RVRT / FlashVSR → ffmpeg编码输出(CRF控制) → 返回结果`
> 
> 

> 注意：原生算法仓库本身**不带 HTTP 接口**，但提供 Python 推理代码，你自己套 FastAPI 就可以对外暴露 API。
> 
> 

## 一、底层算法源码（无 GUI，拿来做 API 内核）

### 1\. RealBasicVSR（优先，档案老视频，低闪烁）

仓库：[https://github\.com/ckkelvinchan/RealBasicVSR](https://github.com/ckkelvinchan/RealBasicVSR)

- 底层基于 BasicSR，原生 Python 推理脚本，无 UI

- 能力：时序视频超分 \+ 降噪，x4；VHS 老录像友好，时序约束抑制帧闪烁

- 输入：视频 / 帧序列；输出修复帧序列

- 不足：**无划痕修复**，划痕需要前置 ProPainter

- 适合 API：可以封装滑动窗口推理，适配长视频；自己封装 FastAPI，调用推理函数，ffmpeg 合成输出 mp4

### 2\. ProPainter（划痕、霉斑、斑点修复，独立模块）

仓库：[https://github\.com/sczhou/ProPainter](https://github.com/sczhou/ProPainter)

- 无 GUI，纯 Python 推理

- 能力：视频 inpainter，消除胶片划痕、污渍；可自动生成瑕疵掩码，也支持传入自定义掩码

- 使用位置：流水线前置步骤；**必须放在超分前面跑**

- 注意：显存开销高；长视频需要分片段滑动推理

### 3\. RVRT（重度噪声、运动模糊老视频备选）

仓库：[https://github\.com/JingyunLiang/RVRT](https://github.com/JingyunLiang/RVRT)

- Recurrent‑Transformer 时序视频复原；无 GUI

- 适合退化严重、运动模糊强的素材；显存 16G\+

- API 集成：推理脚本可复用，长视频做滑动窗口

\#\#\#4\. FlashVSR（CVPR2026，新，速度快，显存友好）
仓库：[https://github\.com/OpenImagingLab/FlashVSR](https://github.com/OpenImagingLab/FlashVSR)

- 流式时序 VSR，长视频友好，速度优于 RealBasicVSR；无 GUI

- 适合 API 批量处理，对 GPU 资源压力更小；较新，工程沉淀略少

\#\#\#5\. SeedVR2（字节，生成式 DiT 大模型，重度损毁）
仓库：[https://github\.com/ByteDance](https://github.com/ByteDance)‑Seed/SeedVR

- 生成式视频修复，会脑补细节；档案场景慎用；20‑24G 显存；推理速度慢，适合做可选高级能力。

## 二、中间层工具箱（减少你重复写代码）

### BasicSR⭐

[https://github\.com/xinntao/BasicSR](https://github.com/xinntao/BasicSR)

- 不是 GUI，是一套**视频 / 图像复原推理、加载权重、滑动窗口推理的工具库**

- RealBasicVSR、BasicVSR\+\+、SwinIR、Real‑ESRGAN 全部基于它实现

- 给你现成：权重加载、tile 分块推理、帧读写工具；**省去大量底层代码**

- 不包含 ProPainter，ProPainter 需要独立引入

> 重要：BasicSR**不做视频的封装读写**，视频拆帧、拼接、CRF 编码全部需要你调用 ffmpeg。
> 
> 

## 三、不推荐用于 API 的项目

1. TaTa、Video2X、RestoraX：RestoraX 虽然有 REST API，但它是为 GUI 设计的大集成壳，依赖重、冗余多，不适合后端服务定制；TaTa/Video2X 是桌面程序，不能当服务内核。

2. 所有桌面 GUI 仓库：内部大量代码是界面逻辑，推理部分耦合 UI，不适合剥离成服务。

## 四、后端 API 架构参考（FastAPI）

整体解耦，各个模型独立模块，可开关：

```Plain Text
HTTP接口层(FastAPI)
    ↓
任务调度（异步任务队列 Celery，长视频耗时大，不能同步阻塞http）
    ↓
【流水线模块，可配置开关】
├─可选步骤1：ProPainter 划痕霉斑去除（可关闭）
├─步骤2：时序视频复原 RealBasicVSR / RVRT / FlashVSR（必选）
└─可选步骤3：CodeFormer人脸局部增强（可关闭）
    ↓
FFmpeg工具模块：帧序列合成mp4，设置CRF，音频拷贝
    ↓
返回输出视频URL/路径
```

> 关键点：长视频推理耗时很长，**不能同步 http 接口直接返回，要用异步任务队列，轮询任务状态**。
> 
> 

## 五、开发时必须自己实现的部分（算法库不提供）

1. 视频输入：ffmpeg 拆视频为帧序列

2. 长视频滑动窗口推理（防止 OOM 显存溢出）

3. 帧序列合成视频，保留原音频，CRF 编码参数控制

4. 文件管理、任务状态、异常处理

5. HTTP 接口封装

## 六、选型建议

1. **标准老视频修复 API（保真优先）**：ProPainter \(可选\) \+ RealBasicVSR，基于 BasicSR 做内核，FastAPI \+ Celery 搭建服务。

2. **追求更快处理速度**：替换 RealBasicVSR 为 FlashVSR。

3. **素材噪声 / 运动模糊极重**：RVRT。

4. **重度损毁，允许 AI 脑补细节**：SeedVR2 作为可选高级接口。

如果你需要，我可以给一份极简 FastAPI 伪代码骨架，只保留 API 结构，不含 GUI。

> (Note: May contain AI-generated content.)
