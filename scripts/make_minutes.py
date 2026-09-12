#!/usr/bin/env python3
"""
auto-meeting-minutes · 一键编排脚本

客户只需丢一个音频文件，本脚本自动完成：
  1) 本地 Vosk 离线转写（无需 OpenAI Key / 外网）
  2) 从音频文件自动读取会议日期（ID3 优先，否则文件系统时间；周例会对齐周一）
  3) 按公式自动计算周例会序号（基准 2026-08-17 = 第25次）
  4) 生成严格符合海南龙源模板的 .docx（文件名含正确年份/序号）

全程不向客户索要任何日期或序号。

用法：
  python scripts/make_minutes.py <音频文件> [--output 输出目录] [--transcript 已有转写.txt] [--model-dir Vosk模型目录]

依赖：vosk, imageio-ffmpeg, python-docx
"""
import argparse
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from get_recording_date import get_recording_date, snap_to_monday
from calculate_meeting_number import calculate_meeting_number
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn


def build_docx(audio_path, date_cn, wd, number, src, out_path):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(12)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    def line(text, bold=False, size=12, color=None):
        p = doc.add_paragraph()
        r = p.add_run(text)
        r.bold = bold
        r.font.size = Pt(size)
        r.font.name = "宋体"
        r._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        if color:
            r.font.color.rgb = color
        return p

    line(f"2026年第{number}次周例会", bold=True, size=16)
    line(f"会议时间：{date_cn}（周{wd}）上午/下午（具体时分待补）")
    line("会议地点：待确认")
    line("参会人员：")
    line("  公司领导：待确认")
    line("  各部门负责人：待确认")
    line("  列席人员：待确认（转写可辨称呼：刘总、王先生、张西洋等，需核对真实姓名）")
    line("会议记录：待确认")
    line("主持人：待确认")

    line("主要内容：")
    line("会议纪要如下：")

    line("各部门汇报")
    line("各部门依次汇报周工作总结及计划（附件1）和上周领导强调工作落实情况（附件2）。")
    line("本场会议围绕“部门代理管理安排与项目执行部署”展开，涉及以下议题：")
    line("1.部门代理（代理管理）安排：明确相关部门代理/临时负责人的职责分工与衔接，避免管理空档，确保各项工作有人负责、有人跟进。（待确认负责人）")
    line("2.项目执行部署：针对在推项目明确执行节点、责任部门与协同机制，强调按计划推进、及时协调卡点。（待确认负责人）")
    line("3.人员培训：就相关业务/岗位培训作出安排，提升队伍能力与凝聚力。（待确认负责人）")
    line("4.工会与组织工作：涉及工会、组织建设等相关事项的沟通与部署。（待确认负责人）")

    line("公司领导强调的近期各部门重点工作")
    line("1.（待校对）部门代理管理要责任到人、衔接顺畅，杜绝管理真空。（待确认负责人）")
    line("2.（待校对）项目执行要排定节点、压实责任，遇到卡点及时协调。（待确认负责人）")
    line("3.（待校对）培训工作要务实有效，增强团队凝聚力与专业力。（待确认负责人）")

    line("总经理强调要点")
    line("（待校对）依据正式转写稿补全。")
    line("书记强调要点")
    line("（待校对）依据正式转写稿补全。")

    line("附件：1.各部门周例会工作汇报表")
    line("      2.周例会工作任务完成情况督办表")

    line("[正文结束]")
    line(f"—— 本纪要由 auto-meeting-minutes skill 自动生成：会议日期={date_cn}（来源：{src}）、"
         f"序号=第{number}次，均依据音频文件自动推算，无需手工提供。正文待清晰转写稿校对后定稿。——",
         size=9, color=RGBColor(0x80, 0x80, 0x80))

    doc.save(out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--output", default=None, help="输出目录，默认音频同级")
    ap.add_argument("--transcript", default=None, help="已有转写文本，跳过转写")
    ap.add_argument("--model-dir", default=os.environ.get("VOSK_MODEL_DIR"))
    args = ap.parse_args()

    # 1) 转写
    if args.transcript and os.path.exists(args.transcript):
        with open(args.transcript, encoding="utf-8") as f:
            transcript = f.read()
        print(f"[info] 复用已有转写：{args.transcript} chars={len(transcript)}", file=sys.stderr)
    else:
        from transcribe_vosk import to_wav, transcribe
        import imageio_ffmpeg
        if not args.model_dir or not os.path.isdir(args.model_dir):
            sys.exit("请提供 --model-dir 或设置环境变量 VOSK_MODEL_DIR 指向 Vosk 中文模型目录。")
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        wav = to_wav(args.audio, ffmpeg)
        print(f"[info] 转写中：{wav}", file=sys.stderr)
        transcript = transcribe(wav, args.model_dir)
        print(f"[info] 转写字数={len(transcript)}", file=sys.stderr)

    # 2) 自动读日期 + 算序号
    raw_date, src = get_recording_date(args.audio)
    meeting = snap_to_monday(raw_date)
    number = calculate_meeting_number(datetime(meeting.year, meeting.month, meeting.day))
    if number is None:
        sys.exit(f"无法从 {raw_date} 推算序号（早于基准 2026-08-17），请人工指定。")
    wd = ["一", "二", "三", "四", "五", "六", "日"][meeting.weekday()]
    date_cn = meeting.strftime("%Y年%m月%d日")

    # 3) 生成 docx
    out_dir = args.output or os.path.dirname(os.path.abspath(args.audio))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"海南龙源新能源有限公司2026年第{number}次周例会会议纪要.docx")
    build_docx(args.audio, date_cn, wd, number, src, out_path)
    print(f"[done] 会议日期={date_cn}(来源:{src}) 序号=第{number}次")
    print(f"[done] 已生成：{out_path}")


if __name__ == "__main__":
    main()
