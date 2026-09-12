#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto-meeting-minutes · 模型自动保障模块（零配置）

目标：客户只丢一个音频，本模块确保"有模型可用"，无需任何手工配置。
优先级（命中即返回）：
  1) 环境变量 VOSK_MODEL_DIR 指向的模型目录
  2) skill 自带 models/ 目录下的 vosk-model-cn-0.22（大模型，自带标点，质量最佳）
  3) skill 自带 models/ 目录下的 vosk-model-small-cn-0.22（小模型，兜底可用）
  4) 首次运行自动下载大模型（依次尝试 VOSK_MODEL_URL 自定义镜像 → alphacephei 官方）
  5) 大模型下载失败则自动下载小模型兜底
返回 (model_dir, quality) ；quality ∈ {"large","small"} ；均无则 (None, None)
"""
import os
import sys
import zipfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_MODELS = os.path.join(HERE, "models")

# 国内/国际可用下载源（大模型优先；如需更快镜像，设置环境变量 VOSK_MODEL_URL 即可覆盖）
LARGE_URLS = [
    os.environ.get("VOSK_MODEL_URL"),
    "https://alphacephei.com/vosk/models/vosk-model-cn-0.22.zip",
]
SMALL_URLS = [
    "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip",
]


def _is_model(d: str) -> bool:
    return bool(d) and os.path.isdir(d) and os.path.exists(os.path.join(d, "am", "final.mdl"))


def find_local():
    env = os.environ.get("VOSK_MODEL_DIR")
    if _is_model(env):
        return env, ("small" if "small" in os.path.basename(env) else "large")
    for name in ("vosk-model-cn-0.22", "vosk-model-small-cn-0.22"):
        d = os.path.join(SKILL_MODELS, name)
        if _is_model(d):
            return d, ("small" if "small" in name else "large")
    return None, None


def _download(url: str, dest_zip: str):
    os.makedirs(os.path.dirname(dest_zip), exist_ok=True)
    print(f"[模型下载] 开始 {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=120) as r:
        total = r.headers.get("Content-Length")
        total = int(total) if total else 0
        got = 0
        with open(dest_zip, "wb") as f:
            while True:
                b = r.read(1 << 18)
                if not b:
                    break
                f.write(b)
                got += len(b)
                if total:
                    pct = got / total * 100
                    if got % (1 << 22) < (1 << 18):
                        print(f"[模型下载] {got/1e6:.0f}/{total/1e6:.0f}MB ({pct:.0f}%)", file=sys.stderr)
    # 解压
    out_dir = dest_zip[:-4]  # 去掉 .zip
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    with zipfile.ZipFile(dest_zip, "r") as z:
        z.extractall(os.path.dirname(dest_zip))
    os.remove(dest_zip)
    # 找到解压出的模型目录（可能多一层父目录）
    parent = os.path.dirname(dest_zip)
    for cand in os.listdir(parent):
        cd = os.path.join(parent, cand)
        if _is_model(cd):
            return cd
    raise RuntimeError(f"解压后未找到合法 Vosk 模型目录：{parent}")


def ensure_model(prefer: str = "large"):
    d, q = find_local()
    if d and q == "large":
        return d, "large"
    if d and q == "small" and prefer != "large":
        return d, "small"

    # 尝试下载大模型
    if prefer == "large":
        for url in LARGE_URLS:
            if not url:
                continue
            try:
                cd = _download(url, os.path.join(SKILL_MODELS, "_dl_large.zip"))
                return cd, "large"
            except Exception as e:  # noqa
                print(f"[warn] 大模型下载失败（{url}）：{e}；尝试下一个源/兜底小模型", file=sys.stderr)

    # 兜底小模型
    for url in SMALL_URLS:
        try:
            cd = _download(url, os.path.join(SKILL_MODELS, "_dl_small.zip"))
            return cd, "small"
        except Exception as e:  # noqa
            print(f"[warn] 小模型下载失败（{url}）：{e}", file=sys.stderr)
    return None, None


if __name__ == "__main__":
    d, q = ensure_model()
    print("MODEL_DIR=", d, "QUALITY=", q)
