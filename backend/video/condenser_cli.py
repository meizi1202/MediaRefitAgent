"""
视频智能缩编 CLI

用法:
    python -m video.condenser_cli --video path/to/video.mp4
    python -m video.condenser_cli --video path/to/video.mp4 --strategy content_condense --target-duration 60
"""
import argparse
import sys
import os
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from video.condenser import condense_video, CondensationResult


def print_welcome():
    """打印欢迎信息"""
    print("=" * 50)
    print("  MediaRefitAgent - 视频智能缩编")
    print("=" * 50)
    print()
    print("支持三种缩编策略:")
    print("  1. smart_compress   - 智能压缩（重编码、删除无声段）")
    print("  2. content_condense - 内容缩编（保留精彩片段）")
    print("  3. smart_crop       - 智能裁剪（人脸/主体跟随）")
    print()


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="视频智能缩编工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 内容缩编到60秒
  python -m video.condenser_cli --video input.mp4 --strategy content_condense --target-duration 60

  # 智能压缩
  python -m video.condenser_cli --video input.mp4 --strategy smart_compress

  # 仅进行语音识别
  python -m video.condenser_cli --video input.mp4 --transcribe-only

  # 指定输出路径
  python -m video.condenser_cli --video input.mp4 --output output.mp4
"""
    )
    parser.add_argument("--video", "-v", required=True, help="输入视频文件路径")
    parser.add_argument("--output", "-o", help="输出视频文件路径")
    parser.add_argument("--strategy", "-s", default="content_condense",
                        choices=["smart_compress", "content_condense", "smart_crop"],
                        help="缩编策略 (默认: content_condense)")
    parser.add_argument("--target-duration", "-d", type=float, default=60.0,
                        help="目标时长，秒 (默认: 60)")
    parser.add_argument("--language", "-l", default="zh",
                        help="语音语言 (默认: zh)")
    parser.add_argument("--transcribe-only", "-t", action="store_true",
                        help="仅进行语音识别，不缩编")
    parser.add_argument("--list-strategies", action="store_true",
                        help="显示支持的策略列表")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_strategies:
        print_welcome()
        return

    # 检查视频文件
    if not os.path.exists(args.video):
        print(f"错误: 视频文件不存在: {args.video}")
        sys.exit(1)

    input_path = os.path.abspath(args.video)
    input_name = Path(input_path).stem

    # 生成输出路径
    if args.output:
        output_path = args.output
    else:
        output_dir = os.path.dirname(input_path) or "./output"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"condensed_{args.strategy}_{input_name}.mp4")

    print(f"输入视频: {input_path}")
    print(f"输出视频: {output_path}")
    print(f"缩编策略: {args.strategy}")
    print()

    # 进度回调
    def progress_callback(progress: float, message: str):
        bar_width = 30
        filled = int(bar_width * progress)
        bar = "#" * filled + "-" * (bar_width - filled)
        print(f"\r[{bar}] {int(progress*100):3d}% | {message}", end="", flush=True)

    try:
        if args.transcribe_only:
            # 仅语音识别
            print("正在进行语音识别...")
            from video.funclip_wrapper import full_transcribe_pipeline

            output_dir = os.path.dirname(output_path) or "./output"
            result = full_transcribe_pipeline(
                video_path=input_path,
                output_dir=output_dir,
                model_size="base",
                language=args.language,
                progress_callback=lambda p, m: progress_callback(p, m) if progress_callback else None,
            )

            if result:
                print("\n\n语音识别完成!")
                print("=" * 50)
                print(f"识别文本 ({len(result.text)} 字符):")
                print("-" * 50)
                print(result.text[:500] + "..." if len(result.text) > 500 else result.text)
                print("-" * 50)
                print(f"\nSRT 字幕: {output_dir}/{input_name}.srt")
                print(f"文本文件: {output_dir}/{input_name}.txt")
                print(f"片段数: {len(result.segments)}")
            else:
                print("\n\n语音识别失败")
                sys.exit(1)

        else:
            # 完整缩编
            print(f"开始缩编 (目标: {args.target_duration}秒)...")
            print()

            result = condense_video(
                video_path=input_path,
                output_path=output_path,
                strategy=args.strategy,
                target_duration=args.target_duration,
                language=args.language,
                progress_callback=progress_callback,
            )

            print()  # 换行
            print()

            if result.success:
                print("缩编完成!")
                print("=" * 50)
                print(f"  策略: {result.strategy}")
                print(f"  原始时长: {result.duration_before:.1f}s")
                print(f"  缩编后: {result.duration_after:.1f}s")
                print(f"  压缩比: {result.duration_before/result.duration_after:.2f}x")
                if result.segments:
                    print(f"  保留片段: {len(result.segments)} 个")
                print(f"  输出文件: {result.output_path}")
                if result.subtitle_path:
                    print(f"  字幕文件: {result.subtitle_path}")
            else:
                print(f"缩编失败: {result.error}")
                sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n已取消")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
