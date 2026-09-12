#!/usr/bin/env python3
"""
自动会议纪要转录工具

使用 OpenAI Whisper API 将音频文件转录为文字稿。

使用方式：
    python transcribe_audio.py <音频文件路径> [选项]

选项：
    --model MODEL      模型大小 (tiny/base/small/medium/large)，默认 medium
    --language LANG    语言代码，默认 zh（中文）
    --output OUTPUT    输出文件路径，默认自动命名为 transcript_<原名>.txt
    --verbose          显示详细进度

环境变量：
    OPENAI_API_KEY     OpenAI API 密钥（必填）
    OPENAI_BASE_URL    自定义 API 端点（可选，用于兼容其他 Whisper 服务）
"""

import argparse
import os
import sys
from pathlib import Path


def transcribe_audio(
    audio_path: str,
    model: str = "medium",
    language: str = "zh",
    output_path: str = None,
    verbose: bool = False
) -> str:
    """
    使用 OpenAI Whisper API 转录音频文件。

    Args:
        audio_path: 音频文件路径
        model: Whisper 模型大小
        language: 语言代码（如 zh, en）
        output_path: 输出文件路径
        verbose: 是否显示详细进度

    Returns:
        转录文本内容
    """
    # 检查依赖
    try:
        import openai
    except ImportError:
        print("错误：需要安装 openai 包", file=sys.stderr)
        print("请运行：pip install openai", file=sys.stderr)
        sys.exit(1)

    # 获取 API 密钥
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("错误：未设置 OPENAI_API_KEY 环境变量", file=sys.stderr)
        print("请运行：export OPENAI_API_KEY='your-api-key'", file=sys.stderr)
        sys.exit(1)

    # 初始化客户端
    client_kwargs = {
        "api_key": api_key,
    }
    base_url = os.environ.get("OPENAI_BASE_URL")
    if base_url:
        client_kwargs["base_url"] = base_url

    client = openai.OpenAI(**client_kwargs)

    # 检查文件是否存在
    audio_file = Path(audio_path)
    if not audio_file.exists():
        print(f"错误：文件不存在 {audio_path}", file=sys.stderr)
        sys.exit(1)

    # 确定输出路径
    if output_path is None:
        output_path = f"transcript_{audio_file.stem}.txt"

    if verbose:
        print(f"正在转录：{audio_path}")
        print(f"模型：{model}，语言：{language}")

    # 调用 API
    try:
        with open(audio_file, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model=model,
                file=f,
                language=language,
                response_format="text",
                timestamp_granularities=["segment"],
            )

        # 保存结果
        output_file = Path(output_path)
        output_file.write_text(transcription, encoding="utf-8")

        if verbose:
            print(f"转录完成，已保存到：{output_file}")
            print(f"文件大小：{len(transcription)} 字符")

        return transcription

    except Exception as e:
        print(f"转录失败：{e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="使用 OpenAI Whisper API 转录音频文件"
    )
    parser.add_argument("audio_path", help="音频文件路径")
    parser.add_argument(
        "--model",
        choices=["tiny", "base", "small", "medium", "large"],
        default="medium",
        help="Whisper 模型大小（默认：medium）"
    )
    parser.add_argument(
        "--language",
        default="zh",
        help="语言代码（默认：zh）"
    )
    parser.add_argument(
        "--output",
        help="输出文件路径（默认：transcript_<原名>.txt）"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细进度"
    )

    args = parser.parse_args()
    transcribe_audio(
        audio_path=args.audio_path,
        model=args.model,
        language=args.language,
        output_path=args.output,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
