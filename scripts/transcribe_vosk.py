#!/usr/bin/env python3
"""
本地 Vosk 离线转写（auto-meeting-minutes 的「路径 E」兜底方案）。

特点：
  - 纯离线，不依赖 OpenAI Key，不依赖外网 API（仅首次需下载模型权重）
  - 不依赖 torch（避免部分机器 Windows 应用控制策略/WDAC 拦截 torch DLL 的问题）
  - 用 imageio-ffmpeg 提供 ffmpeg 二进制，免去系统安装 ffmpeg

依赖安装：
  pip install vosk imageio-ffmpeg

模型准备（二选一）：
  A. 小模型（约 44MB，快、但中文准确率一般，适合草稿）：
     从 GitHub 仓库 jimy7945/vosk-model-cn 下载 zip.part0/1/2 合并解压到模型目录。
  B. 大模型 vosk-model-cn-0.22（约 1.36GB，带标点、准确率高）：
     从 https://alphacephei.com/vosk/models/vosk-model-cn-0.22.zip 下载解压。

模型目录可用环境变量 VOSK_MODEL_DIR 指定，默认：本脚本同级 models/vosk-model-small-cn-0.22

用法：
  python transcribe_vosk.py <音频路径> [--output 输出.txt] [--model-dir 模型目录]
"""
import argparse
import json
import os
import subprocess
import sys

import imageio_ffmpeg
from vosk import KaldiRecognizer, Model

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL_DIR = os.environ.get(
    "VOSK_MODEL_DIR", os.path.join(HERE, "models", "vosk-model-small-cn-0.22")
)


def to_wav(mp3, ffmpeg):
    wav = mp3 + ".16k.wav"
    if os.path.exists(wav):
        return wav
    subprocess.run(
        [ffmpeg, "-nostdin", "-y", "-i", mp3, "-ar", "16000", "-ac", "1", "-f", "wav", wav],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return wav


def transcribe(wav, model_dir):
    import wave
    model = Model(model_dir)
    wf = wave.open(wav, "rb")
    if wf.getnchannels() != 1 or wf.getframerate() != 16000:
        raise SystemExit("wav 必须为 16k 单声道")
    rec = KaldiRecognizer(model, wf.getframerate())
    parts = []
    while True:
        data = wf.readframes(4000)
        if not data:
            break
        if rec.AcceptWaveform(data):
            parts.append(json.loads(rec.Result()).get("text", ""))
    parts.append(json.loads(rec.FinalResult()).get("text", ""))
    return " ".join(p for p in parts if p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--output", default=None)
    ap.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    args = ap.parse_args()

    if not os.path.isdir(args.model_dir):
        sys.exit(f"模型目录不存在：{args.model_dir}\n请先按脚本头部说明下载 Vosk 中文模型。")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    wav = to_wav(args.audio, ffmpeg)
    print(f"[info] transcribing {wav} ...", file=sys.stderr)
    text = transcribe(wav, args.model_dir)
    out = args.output or (os.path.splitext(args.audio)[0] + "_transcript.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[done] saved -> {out}  chars={len(text)}", file=sys.stderr)


if __name__ == "__main__":
    main()
