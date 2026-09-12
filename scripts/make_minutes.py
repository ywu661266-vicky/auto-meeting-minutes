#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto-meeting-minutes · 一键编排脚本（零配置 · 客户只丢一个音频）

完整流程：
  1) 自动保障 Vosk 中文模型（大模型优先，缺失自动下载；无则小模型兜底）
  2) 本地离线转写（无需 OpenAI Key / 外网）
  3) 二次校对：清洗重复字/噪声 + 分句 + 结构化分段（proofread_transcript）
  4) 从音频文件自动读取会议日期（ID3 优先，否则文件时间；周例会对齐周一）
  5) 按公式自动计算周例会序号（基准 2026-08-17 = 第25次）
  6) 生成严格符合海南龙源模板的 .docx（文件名含正确年份/序号）

容错：任何环节失败都不崩溃，始终产出一份合法、可读、标注清晰的纪要 docx。
全程不向客户索要任何日期或序号。

用法：
  python scripts/make_minutes.py <音频文件> [--output 输出目录] [--transcript 已有转写.txt] [--model-dir 模型目录(可选)]
依赖：vosk, imageio-ffmpeg, python-docx
"""
import argparse
import os
import sys
import traceback
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from get_recording_date import get_recording_date, snap_to_monday
from calculate_meeting_number import calculate_meeting_number
from ensure_model import ensure_model
from proofread_transcript import proofread
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn


def _eastasia(run, font="宋体"):
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)


def build_docx(audio_path, date_cn, wd, number, src, pr, out_path, topic=""):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(12)
    # 正文样式单独设置中文字体（style.font 是 Font 对象，不能走 run 的 _eastasia）
    _rpr = style.element.get_or_add_rPr()
    _rpr.get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")

    def line(text, bold=False, size=12, color=None):
        p = doc.add_paragraph()
        r = p.add_run(text)
        r.bold = bold
        r.font.size = Pt(size)
        _eastasia(r)
        if color:
            r.font.color.rgb = color
        return p

    # 标题区
    line(f"2026年第{number}次周例会", bold=True, size=16)
    line(f"会议时间：{date_cn}（周{wd}）上午/下午（具体时分待补）")
    line("会议地点：待确认")
    line("参会人员：")
    line("  公司领导：待确认")
    line("  各部门负责人：待确认")
    sp = pr.get("speakers") or []
    line("  列席人员：" + (("转写可辨称呼：" + "、".join(sp) + "（需核对真实姓名）") if sp else "待确认"))
    line("会议记录：待确认")
    line("主持人：待确认")

    line("主要内容：")
    line("会议纪要如下：")

    # 议题主题（从文件名/转写推断）
    line("各部门汇报")
    if topic:
        line(f"本场会议围绕“{topic}”展开，各部门依次汇报周工作总结及计划（附件1）和上周领导强调工作落实情况（附件2）。")
    else:
        line("各部门依次汇报周工作总结及计划（附件1）和上周领导强调工作落实情况（附件2）。")

    dept = pr.get("sections", {}).get("部门汇报", [])
    if dept:
        for i, s in enumerate(dept[:6], 1):
            line(f"{i}.{s}")
    else:
        line("（依据正式转写稿补全各部门汇报要点）")

    line("公司领导强调的近期各部门重点工作")
    leader = pr.get("sections", {}).get("领导强调", [])
    if leader:
        for i, s in enumerate(leader[:6], 1):
            line(f"{i}.{s}")
    else:
        line("（依据正式转写稿补全领导强调要点）")

    line("总经理强调要点")
    line("（依据正式转写稿补全）" if not leader else leader[0])
    line("书记强调要点")
    line("（依据正式转写稿补全）" if len(leader) < 2 else leader[1])

    line("附件：1.各部门周例会工作汇报表")
    line("      2.周例会工作任务完成情况督办表")

    line("[正文结束]")
    # 自动生成说明 + 置信度
    conf = pr.get("confidence", "low")
    note = pr.get("note", "")
    color = RGBColor(0x80, 0x80, 0x80) if conf != "low" else RGBColor(0xC0, 0x00, 0x00)
    line(f"—— 本纪要由 auto-meeting-minutes skill 自动生成：会议日期={date_cn}（来源：{src}）、"
         f"序号=第{number}次，均依据音频文件自动推算，无需手工提供。"
         f"转写置信度={conf}。{note} ——", size=9, color=color)

    doc.save(out_path)
    return out_path


def infer_topic(audio_path):
    base = os.path.splitext(os.path.basename(audio_path))[0]
    for junk in ("周例会", "会议纪要", "录音", "会议"):
        base = base.replace(junk, "")
    base = base.strip(" -_")
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--output", default=None, help="输出目录，默认音频同级")
    ap.add_argument("--transcript", default=None, help="已有转写文本，跳过转写")
    ap.add_argument("--model-dir", default=os.environ.get("VOSK_MODEL_DIR"),
                    help="可选：手动指定 Vosk 模型目录（留空则自动保障）")
    args = ap.parse_args()

    audio = args.audio
    if not os.path.exists(audio):
        sys.exit(f"[错误] 音频文件不存在：{audio}")

    # 1) 自动保障模型
    if args.model_dir and os.path.isdir(args.model_dir):
        model_dir, quality = args.model_dir, ("small" if "small" in args.model_dir else "large")
    else:
        try:
            model_dir, quality = ensure_model("large")
        except Exception as e:  # noqa
            print(f"[warn] 模型自动保障失败：{e}", file=sys.stderr)
            model_dir, quality = None, None

    # 2) 转写（失败不崩，转写置空）
    transcript = ""
    if args.transcript and os.path.exists(args.transcript):
        transcript = open(args.transcript, encoding="utf-8").read()
        print(f"[info] 复用已有转写 chars={len(transcript)}", file=sys.stderr)
    elif model_dir:
        try:
            from transcribe_vosk import to_wav, transcribe
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            wav = to_wav(audio, ffmpeg)
            print(f"[info] 转写中：{wav}", file=sys.stderr)
            transcript = transcribe(wav, model_dir)
            print(f"[info] 转写字数={len(transcript)} 模型质量={quality}", file=sys.stderr)
        except Exception as e:
            print(f"[warn] 转写失败：{e}；将产出占位纪要", file=sys.stderr)
            traceback.print_exc()
            transcript = ""
    else:
        print("[warn] 无可用模型，产出占位纪要（请检查网络后重跑以自动下载模型）", file=sys.stderr)

    # 3) 二次校对
    with_punct = (quality == "large")
    try:
        pr = proofread(transcript, with_punct=with_punct)
    except Exception as e:  # noqa
        print(f"[warn] 二次校对异常：{e}", file=sys.stderr)
        pr = {"clean": transcript, "paragraphs": [transcript] if transcript else [],
              "sections": {"部门汇报": [], "领导强调": [], "其他": []},
              "speakers": [], "confidence": "low",
              "note": "二次校对模块异常，已原样保留转写。"}

    # 4) 自动读日期 + 算序号（失败不崩，用占位）
    date_cn, wd, number, src = "待确认", "?", "XX", "unknown"
    try:
        raw_date, src = get_recording_date(audio)
        meeting = snap_to_monday(raw_date)
        num = calculate_meeting_number(datetime(meeting.year, meeting.month, meeting.day))
        if num is None:
            src += "（早于基准，序号待人工指定）"
        else:
            number = num
        wd = ["一", "二", "三", "四", "五", "六", "日"][meeting.weekday()]
        date_cn = meeting.strftime("%Y年%m月%d日")
    except Exception as e:  # noqa
        print(f"[warn] 日期推算失败：{e}；使用占位", file=sys.stderr)

    # 5) 生成 docx
    out_dir = args.output or os.path.dirname(os.path.abspath(audio))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"海南龙源新能源有限公司2026年第{number}次周例会会议纪要.docx")
    try:
        build_docx(audio, date_cn, wd, number, src, pr, out_path, topic=infer_topic(audio))
    except Exception as e:  # noqa
        # 最终兜底：极简合法 docx
        print(f"[warn] 模板渲染异常，产出极简兜底 docx：{e}", file=sys.stderr)
        d = Document()
        d.add_paragraph(f"2026年第{number}次周例会（自动生成失败，请查看转写原文）")
        d.add_paragraph(transcript[:2000])
        d.save(out_path)

    print(f"[done] 会议日期={date_cn}(来源:{src}) 序号=第{number}次 转写置信度={pr.get('confidence')}")
    print(f"[done] 已生成：{out_path}")


if __name__ == "__main__":
    main()
